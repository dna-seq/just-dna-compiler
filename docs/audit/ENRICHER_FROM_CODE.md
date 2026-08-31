# Enricher tier, read out of the code — 2026-08-18 audit snapshot

*A dated snapshot, never updated. It was written from the source alone, with the shipped
reference deliberately unread, so that the two could be read against each other — see
[README.md](README.md) for the method and what it is not. **The maintained reference for this tier
lives in `docs/`; this file is evidence, not contract.** Where the two disagreed, eight of the
disagreements turned out to be code defects and are filed as RM93–RM100.*


This document was written by reading `enricher/src/just_dna_enricher/**` (all 40 modules),
`enricher/tests/**` and `enricher/pyproject.toml` at commit `263e897`. No existing prose
documentation was consulted. Where the code and its own docstrings disagree, the code is described
and the disagreement is named. Where intent could not be established, the text says
"undetermined from code" rather than guessing.

---

## 1. What the tier is

`just-dna-enricher` 0.6.0, Python ≥3.13, console script `just-dna-enricher`
(`[project.scripts]` → `just_dna_enricher.cli:app`).

Runtime dependencies: `just-dna-format>=0.6.0`, `just-dna-compiler>=0.6.0`, `duckdb>=1.1.0`,
`platformdirs>=4.0.0`, `python-dotenv>=1.0.1`, `httpx>=0.28.1`, `tenacity>=9.0.0`,
`huggingface-hub>=0.34.0`, `typer>=0.12.0`, `ga4gh.vrs>=2.3.3`.

The `dev` extra adds `pytest>=9.0.3`, `polars>=1.42.0`, `openpyxl>=3.1.5`. `polars` is a *builder*
dependency only — it is imported behind a guarded `try/except ImportError` in `clinvar_build`,
`constraint_build`, `clinpgx_build`, `cpic_build` and `pharmvar_build`, and every runtime reader of
a built snapshot uses `duckdb` instead (`clinvar.py`, `clinpgx.py`, `cpic.CpicSnapshotClient`,
`pharmvar.PharmVarSnapshotClient`, `gene_metrics.lookup_snapshot`). `openpyxl` is imported the same
way in `acmg_build` only; `acmg.load_acmg_snapshot` reads the built CSV with the standard library.

It is the only tier in the workspace that opens a socket. Everything that fetches lives here.

### Environment variables the tier reads

| Variable | Read in | Meaning |
| --- | --- | --- |
| `JUST_DNA_PIPELINES_CACHE_DIR` | `locations._cache_dir` | Base directory under which every snapshot cache lives. Falls back to `platformdirs.user_cache_dir(appname="just-dna-pipelines")`. |
| `JUST_DNA_ENSEMBL_CACHE` | `locations.resolve_ensembl_reference` | Explicit Ensembl cache: a directory, or a `.duckdb` file. |
| `JUST_DNA_CLINVAR_CACHE` | `locations.resolve_clinvar_reference` | Explicit ClinVar snapshot directory. |
| `JUST_DNA_GNOMAD_CONSTRAINT_CACHE` | `locations.resolve_constraint_reference` | Explicit constraint snapshot; a bare `.parquet` is also accepted. |
| `JUST_DNA_CLINPGX_CACHE` | `locations.resolve_clinpgx_reference` | Explicit ClinPGx snapshot directory. |
| `JUST_DNA_CPIC_CACHE` | `locations.resolve_cpic_reference` | Explicit CPIC snapshot directory. |
| `JUST_DNA_PHARMVAR_CACHE` | `locations.resolve_pharmvar_reference` | Explicit PharmVar snapshot directory (operator-built only). |
| `PHARMVAR_API_KEY` | `pharmvar.PharmVarClient.__init__` | PharmVar API key, sent as the `Api-Key` header. Never persisted anywhere. |
| `NCBI_API_KEY` | `eutils.EutilsSettings.__post_init__` | Raises the NCBI pacing gate from 1/3 s to 1/10 s and is sent as `api_key`. |
| `JUST_DNA_CONTACT_EMAIL` | `eutils`, `literature.CrossrefClient`, `literature.PmcIdConverterClient` | Contact address sent to NCBI (`email` param), Crossref (User-Agent `mailto:`), and the PMC id converter. Omitted entirely when unset — no address is invented. |
| `JUST_DNA_HTTP_RETRY_ATTEMPTS` | `net.retry_attempts` | Raises every client's retry ceiling to at least this many attempts. A **floor**: a value below a client's own default is ignored; a non-integer logs a warning and is ignored. |
| `HF_TOKEN` (or `hf auth login`) | `upload._hf_api` via `huggingface_hub.get_token` | Write token for the publisher surface. |
| `XDG_CACHE_HOME` | indirectly, via `platformdirs` | Only relevant when no explicit base is set. |
| `JUST_DNA_NETWORK_TESTS` | tests only | Opt-in gate for the live-network tests. |

`locations.load_env()` walks up from the CWD for a `.env` with `find_dotenv(usecwd=True)` and loads
it with `override=False`, so a real environment variable (including a test's deliberately empty one)
always wins. It is called from `_cache_dir`, from `_resolve_parquet_cache`, from
`resolve_ensembl_reference`, from `net.retry_attempts` (once per process) and from
`PharmVarClient.__init__`. It is **not** called before `NCBI_API_KEY` or `JUST_DNA_CONTACT_EMAIL`
are read — see §11.

---

## 2. The command-line surface

Every command is Typer. Verified against `--help` for all 37 commands. Flags are listed with their
literal defaults.

### 2.1 Enrichment passes

| Command | Argument(s) | Options |
| --- | --- | --- |
| `enrich` | `SPEC_DIR` (must exist, dir) | `--strict/--best-effort` (best-effort), `--offline`, `--ensembl-cache PATH`, `--clinvar-cache PATH`, `--clinvar/--no-clinvar` (on), `--gnomad/--no-gnomad` (on), `--vrs/--no-vrs` (on), `--verify-ref/--no-verify-ref` (on), `--verify-clinsig/--no-verify-clinsig` (on), `--verify-rsids/--no-verify-rsids` (on), `--keep-par-twin` |
| `frequencies` | `SPEC_DIR` | `--strict/--best-effort`, `--offline`, `--populations "a,b"`, `--dataset LABEL` (default `gnomad_v4.1_joint`) |
| `gene-metrics` | `SPEC_DIR` | `--strict/--best-effort`, `--offline`, `--constraint-cache PATH` |
| `dosage` | `SPEC_DIR` | `--strict/--best-effort`, `--offline`, `--url` (ClinGen curation TSV), `--use` (`unstated`) |
| `gene-validity` | `SPEC_DIR` | `--source` (`clingen`; also `gencc`), `--strict/--best-effort`, `--offline`, `--url` |
| `gwas` | `SPEC_DIR` | `--strict/--best-effort`, `--offline`, `--use` (`unstated`), `--study-facts/--no-study-facts` (on) |
| `assertions` | `SPEC_DIR` | `--strict/--best-effort`, `--offline`, `--clinvar-cache PATH` |
| `literature` | `SPEC_DIR` | `--strict/--best-effort`, `--offline`, `--fulltext/--no-fulltext` (on), `--doi/--no-doi` (on) |
| `pgx` | `SPEC_DIR` | `--strict/--best-effort`, `--offline`, `--use` (`unstated`), `--pharmvar/--no-pharmvar` (on), `--cpic/--no-cpic` (on), `--cpic-cache PATH`, `--pharmvar-cache PATH` |
| `clinpgx check` | `SPEC_DIR` | `--snapshot PATH`, `--offline`, `--strict/--best-effort`, `--use` |
| `enrich-and-compile` | `SPEC_DIR OUTPUT_DIR` | `--strict/--best-effort`, `--offline`, `--ensembl-cache`, `--clinvar-cache`, `--clinvar/--no-clinvar`, `--gnomad/--no-gnomad`, `--frequencies` (off), `--gene-metrics` (off) |
| `vrs mint` | `SPEC_DIR` | `--offline` |

`--use` is normalized by `cli._use` through `vocab.match_vocab` against `VALID_DECLARED_USE` after
lower-casing and stripping, so `non-commercial` and `non_commercial` are the same declaration; an
unmatched value is a `typer.BadParameter` listing the members.

`_mode(strict)` maps the boolean onto the string `"strict"` / `"best_effort"` that every pass takes
as `mode=`.

### 2.2 Checks that write no authored cell

| Command | Argument(s) | Options |
| --- | --- | --- |
| `check-identifiers` | `SPEC_DIR` | `--strict/--best-effort`, `--traits/--no-traits` (on), `--genes/--no-genes` (on) |
| `check-acmg` | `SPEC_DIR` | `--strict/--best-effort`, `--offline`, `--url` (`https://www.ncbi.nlm.nih.gov/clinvar/docs/acmg/`), `--sf-list DIR` |

Both return early with `no variants.csv — nothing to check` and write **no** `verification.json`
when the module carries no `variants.csv` — the check does not *apply*, which is deliberately
distinguished from a skip.

### 2.3 Drafting

| Command | Argument(s) | Options |
| --- | --- | --- |
| `draft` (CPIC) | `SPEC_DIR` | `--gene` (required, repeatable), `--drug` (repeatable), `--allele` (repeatable), `--population`, `--use`, `--offline`, `--cpic-cache PATH`, `--dry-run` |
| `draft-panel` (ClinVar) | `SPEC_DIR` | `--gene` (required, repeatable), `--snapshot DIR`, `--offline`, `--download/--no-download` (on), `--clin-sig "a,b"`, `--min-review-stars` (2, range 0–4), `--max-citations` (3, min 0), `--use`, `--dry-run` |
| `draft-clinpgx` | `SPEC_DIR` | `--snapshot DIR` (**required**), `--drug` (repeatable), `--gene` (repeatable), `--min-evidence-level` (`1A|1B|2A|2B|3|4`), `--use`, `--dry-run` |
| `template` | `KIND` (e.g. `repeat_alleles.csv`) | none |

`draft --allele` requires exactly one `--gene` and exits with code **2** otherwise, with the message
`--allele needs exactly one --gene (got N): a star-allele name means a different allele in each
gene. Draft one gene at a time; the command is additive.`

`template` prints the header-only CSV to stdout and the requirement summary to stderr in blue
(`required: …`, `and one of: …`) plus a yellow `must not be left empty (defaults): k=v` line. Its
docstring names `just-dna-compiler template` as canonical.

### 2.4 Snapshot builders and publishers (dev/publisher surface)

| Command | Argument(s) | Options |
| --- | --- | --- |
| `clinvar build` | — | `--vcf PATH`, `--download`, `--out DIR` (`clinvar`) |
| `clinvar citations` | — | `--out DIR` (required, an existing snapshot dir), `--citations PATH`, `--download`, `--url` |
| `clinvar publish` | `SNAPSHOT_DIR` | `--repo` (default `anon-org/clinvar`), `--message/-m`, `--dry-run` |
| `gnomad constraint build` | — | `--tsv PATH`, `--download`, `--out DIR` (`gnomad_constraint`) |
| `gnomad constraint publish` | `SNAPSHOT_DIR` | `--repo` (default `anon-org/gnomad_constraint`), `--message/-m`, `--dry-run` |
| `clinpgx build` | — | `--out DIR` (required), `--zip PATH`, `--url`, `--use` |
| `clinpgx publish` | `SNAPSHOT_DIR` | `--repo` (default `anon-org/clinpgx`), `--dry-run`, `--message/-m` |
| `cpic build` | — | `--out DIR` (required), `--endpoint` (`https://api.cpicpgx.org/v1`), `--use` |
| `cpic publish` | `SNAPSHOT_DIR` | `--repo` (default `anon-org/cpic`), `--dry-run`, `--message/-m` |
| `pharmvar build` | — | `--out DIR` (required), `--use` |
| `acmg build` | `WORKBOOK` (.xlsx, must exist) | `--out DIR` (`acmg_sf`), `--source-url`, `--doi` |
| `upload` | `MODULE_DIR` | `--repo`, `--name`, `--message/-m`, `--dry-run` |

`clinvar build` and `gnomad constraint build` exit 1 with `Provide --vcf PATH or --download.` /
`Provide --tsv PATH or --download.` when given neither. `clinvar citations` exits 1 with
`give --citations, or --download`.

There is deliberately **no `pharmvar publish`**: the CLI docstring states the key is personal and
non-transferable under PharmVar's terms §2, so nothing built with it may be passed on.

### 2.5 Caches

`cache status` reads only. For each of the six caches it prints either
`  <name>      present  <path>  <dataset label>` in green, or
`  <name>      absent   — <what it serves>; provision with `cache pull`` (or ``<name> build`` for
PharmVar, which has no `ensure_*`) in yellow. The label is `release.json`'s `dataset` key; an
unreadable `release.json` prints `(unreadable release.json)` and the snapshot is still treated as
present.

`cache pull` takes `--only NAME` (repeatable) and `--use`. An unknown name raises
`typer.BadParameter` listing every known cache. PharmVar named explicitly prints
`nothing published to pull — build it with `pharmvar build --out <dir>`.` and is skipped. The two
licence-gated caches (`clinpgx`, `cpic`) go through `check_declared_use` **before** any download —
the terms are accepted when the data is taken. Any one cache failing is caught
(`except Exception`) and reported without sinking the rest; the command exits 1 if any failed.

### 2.6 Authoring lookups (`hint`) — read-only, write nothing

| Command | Options |
| --- | --- |
| `hint variant` | `--rsid`, `--chrom`, `--start`, `--ref`, `--alts`, `--ambiguity`, `--frequencies`, `--offline`, `--ensembl-cache`, `--clinvar-cache`, `--json` |
| `hint recover` | `--chrom` (required), `--start` (required), `--ref`, `--alts`, `--offline`, `--json` |
| `hint citation` | `--pmid`, `--doi`, `--pmcid`, `--offline`, `--json` |
| `hint trait` | `CURIE` argument |
| `hint gene` | `SYMBOL` argument |

`hint variant` exits 1 with `give --rsid, or --chrom and --start` when neither identity is supplied;
`hint citation` exits 1 with `give --pmid, --doi or --pmcid`.

Output convention (`cli._echo_hint`): advisory answers go to **stdout** as
`column<TAB>value<TAB>[refusal, from source]`, findings go to **stderr** coloured by level
(`error`=red, `warning`=yellow, `info`=blue), so a pipe carries the answers alone.

Every advisory is an `Alteration` with `applied=False` and a `refusal` from
`lookup._REFUSAL_BY_COLUMN`: `rsid` → `identity_bearing`; `chrom`/`start`/`ref`/`alts`/`clin_sig`/
`doi`/`pmid` → `redundancy_bearing`; `trait_efo_id`/`gene` → `intent_bearing`.

---

## 3. The resolver chain

`enrich.enrich()` fills `resolution.csv` beside (or inside `derived/` of) the spec. Two modes:
`best_effort` records what it could not resolve as `not_found`; `strict` raises `EnrichmentError`.

### 3.1 Inputs — which tables may ask for a coordinate

`_collect_subjects` normalizes four tables into a `_Subject`, in this order, deduped by
`variant_key` with **first occurrence winning**:

1. `variants.csv` (`VariantRow`) — carries `alts`, constraint is the row's `genotype`;
2. `pharm_variants.csv` (`PharmVariantRow`) — keyed *without* `alts`, constraint is `genotype`;
3. `haplotypes.csv` (`HaplotypeRow`) — keyed without `alts`, constraint is the single `allele`;
4. `heteroplasmy.csv` (`HeteroplasmyRow`) — keyed **with** `alts`, and loaded with the module's
   `genome_build` because its `variant_key` is build-dependent; constraint is `None`.

`variants.csv` first is load-bearing: it is the only table carrying `alts`, and `alts` is a
resolution fact that decides the compiled bytes.

`variants.csv` is re-stamped for the module's build via
`just_dna_compiler.compiler._restamp_for_build` at load — the enricher is the third load site for
that file and needs the same re-stamp the compiler's two do. Warnings from that load are dropped
deliberately (the compiler emits the same ones).

### 3.2 The build gate

`spec_genome_build(spec_dir)` reads `module_spec.yaml`. Absent file → `"GRCh38"` (the format's own
default). Present but unreadable → `EnrichmentError`, deliberately: enrichment will not pick a build
for a module whose declaration cannot be read.

Every coordinate link is gated on `genome_build == "GRCh38"`. A non-GRCh38 module logs a scoped
warning ("Coordinate resolution is GRCh38-bound … build-free checks (rsID currency) still run") and
gets **no row at all** for an unresolved rsID-only subject — `not_found` would assert a source was
asked when none was.

### 3.3 The links, in order (first hit wins)

| # | Link | Runs when | `source` stamped | Notes |
| --- | --- | --- | --- | --- |
| 0 | Existing `resolution.csv` rows | always | (kept verbatim) | Authoritative; merged, never clobbered. A key with no `chrom` in any of its rows still counts as unresolved. |
| 1 | Ensembl snapshot (`resolver.lookup_loci`, duckdb over parquet) | GRCh38 and (`need_pos` or `need_rsid` or `verify_pairs`) | `cache` | Provisioned by `ensure_snapshot` first when the cache is absent, not offline and `download=True`. |
| 2 | ClinVar snapshot (`clinvar.lookup_loci`) | `use_clinvar`, GRCh38, and something still missing | `clinvar` | Located whenever `use_clinvar or verify_clinsig` (the cross-check needs the same snapshot). |
| 3 | Live Ensembl (`ensembl.EnsemblResolver`) | not offline, GRCh38 | `ensembl-graphql` or `ensembl-rest` | V2 GraphQL → V1 REST. |
| 4 | Live gnomAD (`gnomad.GnomadClient.resolve_rsids`) | `use_gnomad`, not offline, GRCh38 | `gnomad` | **Last**, deliberately: gnomAD reports only alleles observed in gnomAD, so promoting it would narrow an already-compiled module's `alts`. |

Reverse (position → rsID) back-fill runs against links 1 and 2 only, and is **allele-aware**: the
candidate list is filtered on the authored ALT where the row states exactly one
(`_authored_alt` returns `None` for a multi-allelic cell). 0 candidates → `rsid` stays null and
`source="authored"`; 1 → attached; ≥2 → deterministic first pick, `status="ambiguous"`, and the full
list in `rsid_alternates`.

### 3.4 What `--offline` changes

* Links 3 and 4 do not run at all.
* `ensure_snapshot` / `ensure_clinvar_snapshot` are not called, so no cache is provisioned.
* `SequenceProxy(offline=True)` returns `None` from `proxy()`, so **indel VRS minting** and the
  **reference-allele check** are both skipped (substitution minting is pure stdlib and still runs).
* The wrong-build diagnosis returns `BuildDiagnosisResult(not_checked="skipped_offline")`.
* The rsID currency check is skipped (`rsid_currency` recorded as `skipped(…, "offline")`).
* The `clin_sig` cross-check still runs if a local ClinVar snapshot resolves — it is offline-capable.
* An unresolved rsID-only row is written as `status="not_found", source="cache"` — see §11, bug 2.

The other passes treat `--offline` differently and each says so:

| Pass | `--offline` behaviour |
| --- | --- |
| `frequencies` | No-op with a warning (`skipped_offline=True`). gnomAD frequency has no snapshot and will not get one (58 GB exomes / 742 GB genomes). Any existing `frequencies.csv` is kept and rewritten as the pin. |
| `gene-metrics` | Snapshot-only. Provisioning is off, live API is off. With no snapshot the table is **not** empty: every module gene gets a `not_found` row labelled with the v4.1 dataset, while the log line claims it will be empty — see §11, bug 8. |
| `assertions` | Snapshot-only, fully capable. With no snapshot reachable → `skipped_no_snapshot=True`, a no-op, never a failure. |
| `dosage`, `gene-validity`, `gwas`, `literature` | No-op with a warning. An **injected** `curation_text=` / `export_text=` / `client=` still wins, because handing over bytes you already hold is not egress. |
| `pgx` | Snapshot-only per leg. An injected **live** client is refused under `--offline` (`_injected` returns `None` unless the client is a `*SnapshotClient`) — the type decides, not `configured`. |
| `clinpgx check` | Stops the chain at "resolved cache"; no HuggingFace provisioning. |
| `draft` (CPIC) | Snapshot-only; with none, nothing is drafted and the reason is returned. |
| `draft-panel` | Refuses (`ClinVarDraftError`) rather than degrading — drafting from no snapshot is no result. |
| `check-acmg` | With no `--sf-list`, every row is `unchecked` and the report carries the warning `--offline with no --sf-list: acmg_sf went unchecked…`. |
| `vrs mint` | Substitutions only; indels stay unminted. |
| `hint variant` / `hint recover` / `hint citation` | Report `unchecked`, never `absent`. |

`check-identifiers` has **no** `--offline` flag, and `identifiers.verification_records` says so
explicitly: "the command has no such flag, and inventing one here would name a state the run cannot
be in."

### 3.5 Allele-aware locus selection and PAR

For a one-to-many rsID, each candidate locus is put to `just_dna_compiler.resolution.hosting_verdict`
against the subject's constraint (genotype, or a haplotype's single allele; `None` constrains
nothing and keeps every locus). The verdict is three-valued:

* `False` — dropped, with a warning naming event size as the reason it cannot be re-anchored;
* `None` — **kept**, with a warning whose reason comes from the shared `undecided_reason`;
* `True` — kept.

Surviving loci then pass through `select_par_representative` unless `--keep-par-twin`. A Y locus is
dropped only when its `par_partner` X position is present **and** carries the same `ref` and the same
`alts` set — partner coordinates say "same place", not "same variant". The decision is per locus, not
per gene (`XG` and `SPRY3` straddle PAR boundaries). Dropped twins are reported once, aggregated,
in cyan on the CLI as `pseudoautosomal: kept the X spelling of N locus/loci; left out …`.

### 3.6 Output

`resolution.csv` columns, in `enrich._FIELDNAMES` order:

```
variant_key, rsid, chrom, start, ref, alts, genome_build, locus_index, vrs_id, vrs_spec,
caid, source, authority, status, rsid_alternates, rsid_current, rsid_status, fetched_at
```

Rows are sorted by `(variant_key, locus_index)`. `authority` is derived from `source` through
`licensing.RESOLUTION_AUTHORITY_BY_LINK` and filled only where empty, so a hand-written authority
survives: `cache`/`ensembl`/`ensembl-rest`/`ensembl-graphql` → `ensembl`; `clinvar` → `clinvar`;
`gnomad` → `gnomad`. `authored`, `reversed` and `manual` map to nothing, which is the answer rather
than a gap.

After writing, `enrich()` calls `record_verification(...)` (§7) and then `record_source_terms(...)`
at the `"resolution"` layer for every distinct `authority`.

### 3.7 Strict failure order

`enrich()` raises in this order, which is deliberate:

1. `mode == "strict"` and any ref mismatch — checked **before** the unresolved gate, with the
   build diagnosis folded into the message;
2. any **withdrawn** rsID — fatal in *both* modes (`RsidStatus.is_fatal`; never produced by the
   automated check, only by a curator-recorded retraction);
3. `strict` and any stale rsID;
4. `strict` and any unresolved key.

---

## 4. Every external service the tier talks to

### 4.1 Endpoint inventory

| Service | Default endpoint | Asked for | Module |
| --- | --- | --- | --- |
| Ensembl beta GraphQL (V2) | `https://beta.ensembl.org/api/graphql/variation` | rsID → GRCh38 locus. Genome id `a7335667-93e7-11ec-a39d-005056b38ce3`. | `ensembl.py` |
| Ensembl REST (V1) | `https://rest.ensembl.org` | `/variation/human/{rsid}` — the workhorse for a bare rsID. | `ensembl.py` |
| Ensembl GRCh37 REST | `https://grch37.rest.ensembl.org` | `/overlap/region/human/{c}:{p}-{p}?feature=variation` and `/sequence/region/human/{c}:{s}..{e}` | `grch37.py` |
| gnomAD GraphQL | `https://gnomad.broadinstitute.org/api` | `variant(rsid:)`, `variant(variantId:)`, `variant_search(query:)`, `gene(gene_symbol:)`. Dataset `gnomad_r4`, frequency subset `joint`. | `gnomad.py` |
| seqrepo REST | `seqrepo+https://services.genomicmedlab.org/seqrepo` (a `ga4gh.vrs` data-proxy URI) | Reference bases, for indel VRS normalization and the reference-allele check. `create_dataproxy` also accepts `seqrepo+file:///…`. | `sequences.py` |
| NCBI E-utilities | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` | `esummary.fcgi?db=snp` (rsID currency), `esummary.fcgi?db=pubmed` (citation existence + identifiers + bibliographic fields). | `eutils.py` |
| Europe PMC | `https://www.ebi.ac.uk/europepmc/webservices/rest` | `search?query=EXT_ID:…&resultType=core` (pmcid, doi, `isOpenAccess`, `inEPMC`, `license`, `abstractText`), and `{pmcid}/fullTextXML`. | `literature.py` |
| Crossref | `https://api.crossref.org` | `/works/{doi}` — DOI existence for what PubMed does not index. | `literature.py` |
| PMC id converter | `https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/` | PMCID → PMID. (The long-published `www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/` 301-redirects here; the current address is named so a client following no redirect still lands right.) | `literature.py` |
| OLS4 | `https://www.ebi.ac.uk/ols4/api` | `/ontologies/{ont}/terms?iri=…` — trait CURIE currency. | `identifiers.py` |
| HGNC | `https://rest.genenames.org` | `/fetch/symbol/{s}` then `/fetch/prev_symbol/{s}`, never the fuzzy `search/`. | `identifiers.py` |
| ClinGen dosage list | `https://ftp.clinicalgenome.org/ClinGen_gene_curation_list_GRCh38.tsv` | Whole TSV. | `clingen.py` |
| ClinGen gene validity | `https://search.clinicalgenome.org/kb/gene-validity/download` | Whole CSV (~1 MB). | `gene_validity.py` |
| GenCC | `https://search.thegencc.org/download/action/submissions-export-csv` | Whole CSV (~28 MB). Timeout 180 s. | `gene_validity.py` |
| GWAS Catalog | `https://www.ebi.ac.uk/gwas/rest/api` | `/singleNucleotidePolymorphisms/{rsid}/associations`, then `_links.study` and `_links.efoTraits`. | `gwas.py` |
| CPIC (PostgREST) | `https://api.cpicpgx.org/v1` | `gene`, `allele`, `diplotype`, `allele_definition`, `allele_location_value`, `recommendation`, `drug`. | `cpic.py` |
| PharmVar | `https://www.pharmvar.org/api-service` | `genes/{symbol}` and `genes` (whole database, ~5 MB). | `pharmvar.py` |
| ACMG SF page | `https://www.ncbi.nlm.nih.gov/clinvar/docs/acmg/` | One HTML GET (~75 KB), scraped. | `acmg.py` |
| NCBI ClinVar VCF | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz` | Builder download (streamed). | `clinvar_build.py` |
| NCBI ClinVar citations | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/var_citations.txt` | Builder download (streamed). | `clinvar_build.py` |
| gnomAD constraint TSV | `https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/constraint/gnomad.v4.1.constraint_metrics.tsv` | Builder download (95.5 MB). Note the path is `release/4.1/`, not `release/v4.1/`. | `constraint_build.py` |
| ClinPGx bulk archive | `https://api.clinpgx.org/v1/download/file/data/clinicalAnnotations.zip` | Builder download. | `clinpgx_build.py` |
| HuggingFace Hub | `datasets/anon-org/{ensembl_variations,clinvar,gnomad_constraint,clinpgx,cpic}/data` | Snapshot provisioning (`HfFileSystem`) and publishing (`HfApi.upload_folder`). | `download.py`, `upload.py` |

ACMG's v3.3 supplementary workbook URL (`https://ars.els-cdn.com/content/image/1-s2.0-S1098360025001017-mmc1.xlsx`)
and DOI `10.1016/j.gim.2025.101454` are recorded in `acmg_build` as `release.json` provenance and are
deliberately **never fetched** — the author supplies their own copy.

### 4.2 Pacing, batching and retry

`net.PacingGate` is the single pacing primitive. Its clock and sleeper are injectable (so tests
prove a six-second interval without sleeping six seconds), it is monotonic by default, and it is
thread-safe in a specific way: the lock covers only the bookkeeping. Each caller reserves the next
free slot under the lock and then waits for it outside, so N threads get N slots spaced `interval`
apart rather than serializing behind a lock held across a sleep.

`net.batched` splits in order; `net.dedupe` is first-occurrence-order de-duplication (never a `set`,
because request order decides emission order and emission order is part of the artifact digest).

| Client | Interval | Batch | Retry policy | Retries on |
| --- | --- | --- | --- | --- |
| `EnsemblResolver._graphql_rsid` / `_rest_rsid` | none | 1 | `attempt_floor(3)`, `wait_exponential_jitter(0.5, 8)` | `TransportError`, `TimeoutException` |
| `Grch37Client._get` | 0.1 s (Ensembl publishes 15 rps) | 1 | `attempt_floor(3)`, jitter(0.5, 8) | transport, timeout |
| `GnomadClient._post` | **6.0 s** (exactly 10/60 s) | 20 aliases (25 worked, 29 gave HTTP 400) | `attempt_floor(4)`, jitter(2, 30) | `RateLimitedError` (429), transport, timeout |
| `EutilsClient._get` | 1/3 s unkeyed, 1/10 s with `NCBI_API_KEY` | 200 ids | `attempt_floor(4)`, jitter(1, 20) | `EutilsRateLimitedError` (429), transport, timeout |
| `EuropePmcClient._get` | 0.5 s | 25 ids | `attempt_floor(3)`, jitter(1, 10) | transport, timeout |
| `CrossrefClient.exists` | 0.1 s | 1 | `attempt_floor(3)`, jitter(1, 10) | transport, timeout |
| `PmcIdConverterClient._get` | 0.5 s | 200 ids | `attempt_floor(3)`, jitter(1, 10) | transport, timeout |
| `OntologyClient._get` (OLS4 + HGNC) | 0.2 s (a courtesy — neither publishes a limit) | 1 | `attempt_floor(3)`, jitter(1, 10) | transport, timeout |
| `GwasCatalogClient._get` | **1.0 s, a conservative default and not a transcribed limit** — EBI publishes no numeric budget | 1 | `attempt_floor(3)`, jitter(0.5, 8) | transport, timeout |
| `CpicClient._request` | none | whole tables | `attempt_floor(3)`, jitter(1, 10) | transport, **`HTTPStatusError`** |
| `PharmVarClient._request` | 0.5 s (2 rps) | whole gene / whole DB | `attempt_floor(3)`, jitter(1, 10) | transport, **`HTTPStatusError`** |
| `acmg.fetch_acmg_page` | none | 1 | none | — |
| `clingen.fetch_curation_list`, `gene_validity.fetch_validity_export` | none | 1 | none | — |

Pacing always happens *before* retry: a blind retry would spend the same budget that caused the 429.

`attempt_floor` is a `tenacity.stop_base` subclass resolved per call, so `JUST_DNA_HTTP_RETRY_ATTEMPTS`
can raise a ceiling that was otherwise frozen at import time. Its docstring explicitly restricts it
to replacing a *bare* `stop_after_attempt(n)` — a composed policy means a conjunction and raising one
term would silently change something.

### 4.3 Error translation — what crosses each API boundary

This is the part an integrator most needs, because the tier is not uniform.

| Module | Public exception | Leaks `httpx`? |
| --- | --- | --- |
| `ensembl` | `EnsemblError` | **No** at the `resolve_rsid` boundary — every `httpx` error is caught and folded into the tri-state return. |
| `gnomad` | `GnomadError`, `RateLimitedError(GnomadError)` | **Yes** — `raise_for_status()` sits outside the try and `HTTPStatusError` is not retried, so a non-429 4xx/5xx escapes untranslated (§11, bug 9). Transport errors and timeouts also escape after retries (`reraise=True`). |
| `eutils` | `EutilsError`, `EutilsRateLimitedError` | **Yes** — identical shape to `gnomad` (§11, bug 9). |
| `grch37` | none — every read is tri-state | **No** at `variants_at` / `reference_bases`. |
| `cpic` | `CpicError` | **No** from `_get` (both legs translated) — but `row_count` bypasses `_get` and can leak. |
| `pharmvar` | `PharmVarError` | **No** from `_get` (both legs translated). The 401 diagnosis is raised inside `_request`, *before* the status check, so it is never retried and never echoes the key. |
| `gwas` | `GwasError`, `GwasNotFound(GwasError)` | **No** — `_get` translates transport, status, and unparseable JSON. |
| `literature.CrossrefClient.exists` | none — returns `bool | None` | **No**. |
| `literature.EuropePmcClient` | — | **Yes** from `_get` (`raise_for_status`); `fulltext()` catches it and returns `None`. |
| `identifiers.OntologyClient` | `IdentifierCheckError` (declared, currently unused) | **Yes** — `trait`/`gene` call `raise_for_status()`. The `check-identifiers` CLI catches `httpx.HTTPError` explicitly and records an `unreachable` attestation on the way out. |
| `acmg` | `AcmgSfError`, `AcmgListUnavailable(AcmgSfError)` carrying `.skip` | **No** — `fetch_acmg_page` translates. |
| `clingen` | `ClinGenError` | **No**. |
| `gene_validity` | `GeneValidityError` | **No**. |
| `sequences.SequenceProxy` | none — `proxy()`/`subsequence()` return `None` and log | **No** (broad `except Exception`). |
| `download` | `EnsemblReferenceError`, `ClinVarReferenceError`, `ConstraintReferenceError`, `GatedSnapshotError` (all `FileNotFoundError` subclasses) | Underlying HF errors may propagate from `fs.get`; callers wrap provisioning in `except Exception`. |
| `upload` | `FileNotFoundError`, `PermissionError`, `ImportError` | HF API errors propagate. |

The three-valued return is the recurring shape, and it is worth stating once because five modules
implement it independently:

* `EnsemblResolver.resolve_rsid` → `(loci, source)`: a non-empty list is an answer, `[]` is *also*
  an answer (Ensembl was reached and has no GRCh38 locus), and `(None, None)` means it could not be
  asked. **A 4xx is an answer** — Ensembl 400s on rsIDs it cannot resolve — so only 5xx, transport
  errors and timeouts return `None`.
* `Grch37Client.variants_at` → `list | None`; `reference_bases` → `str | ""` | `None`. Same rule:
  a 4xx is the service saying "nothing here".
* `GwasCatalogClient.associations_for` → list, `[]` (a 404, which the Catalog returns for a variant
  with no published association), or a raised `GwasError`.
* `CrossrefClient.exists` → `True` / `False` (404) / `None` (transport failure or an unexpected
  status).
* `literature.regex_matches` → `True` / `False` / `None` (timed out or uncompilable).

### 4.4 gnomAD's partial-failure handling

`_errors_by_alias` splits GraphQL `errors[]` three ways: an error carrying a `path` names the alias
that failed and is handed back as data; a pathless error whose message is in `_ABSENCE_MESSAGES`
(`{"variant not found"}`) is logged and the batch carries on, because the `null` node at that alias
already says it; any other pathless error **raises**, because that is a broken query and returning
"nothing found" would hide it. A batch of 20 that comes back with 17 good rows and 3 alias errors
keeps the 17.

`resolve_rsids` handles the multi-allelic rsID case: gnomAD answers `rs334` with
"Multiple variants found, query using variant ID to select one." rather than a record, matched by
`_MULTIPLE_VARIANTS_RE`, and those rsIDs are re-queried through `variant_search`.

`covers_locus(chrom, start, build)` is three-valued and is a **source convention**, not geometry:
gnomAD hard-masks the Y pseudoautosomal region, so a Y-PAR locus returns `False` (never asked
about, recorded as `not_covered`), everything else on GRCh38 returns `True`, and any other build
returns `None`.

---

## 5. The caches

Layout, defined once in `locations.py` so builder, publisher, provisioner and reader cannot drift:

```
<base>/<subdir>/data/*.parquet          # SNAPSHOT_DATA_DIRNAME — what the readers glob
<base>/<subdir>/citations/*.parquet     # SNAPSHOT_SIDECAR_DIRNAMES, a SIBLING of data/
<base>/<subdir>/release.json            # RELEASE_FILENAME
<base>/<subdir>/LICENSE.txt             # SNAPSHOT_LICENSE_FILENAME
<base>/ensembl_variations/ensembl_variations.duckdb   # optional prebuilt view
```

`<base>` is `$JUST_DNA_PIPELINES_CACHE_DIR` or the platformdirs user cache for
`"just-dna-pipelines"` — deliberately the same layout a `just-dna-lite` deployment uses, so one cache
serves both.

A citations table must be a *sibling* of `data/`, never inside it: the readers glob `data/*.parquet`
and a two-column file there unions with the 17-column variant parquet and every query fails.

| Cache | Subdir | Env override | Holds | `ensure_*` | Publishable |
| --- | --- | --- | --- | --- | --- |
| ensembl | `ensembl_variations` | `JUST_DNA_ENSEMBL_CACHE` (dir or `.duckdb`) | `homo_sapiens-*.parquet`; a stale/empty prebuilt `.duckdb` is ignored in favour of the parquet | `ensure_snapshot` | yes (`anon-org/ensembl_variations`) |
| clinvar | `clinvar` | `JUST_DNA_CLINVAR_CACHE` | `clinvar-*.parquet` (one per chromosome) + optional `citations/citations.parquet` | `ensure_clinvar_snapshot` | yes (`clinvar publish`) |
| constraint | `gnomad_constraint` | `JUST_DNA_GNOMAD_CONSTRAINT_CACHE` (a bare `.parquet` is also accepted) | `gnomad_constraint.parquet`, one row per gene | `ensure_constraint_snapshot` | yes |
| clinpgx | `clinpgx` | `JUST_DNA_CLINPGX_CACHE` | `data/annotations.parquet` + `LICENSE.txt` | `ensure_clinpgx_snapshot` | yes |
| cpic | `cpic` | `JUST_DNA_CPIC_CACHE` | `genes/alleles/diplotypes/allele_definitions/recommendations.parquet` | `ensure_cpic_snapshot` | yes |
| pharmvar | `pharmvar` | `JUST_DNA_PHARMVAR_CACHE` | `alleles.parquet`, `variants.parquet` | **none, deliberately** | **no** |
| ACMG SF | (no cache dir) | — | `acmg_sf.csv` + `release.json`, passed with `--sf-list` | — | no (inject-only) |

`_provision_snapshot` (the shared download body):

* A non-empty cache with no truncated parquet is **trusted without touching the network**.
* Completeness is checked with `_parquet_footer_ok` — a complete parquet begins and ends with `PAR1`.
  A corrupt file is unlinked and refetched; a download goes to `<name>.part` and is renamed only
  after the footer verifies.
* `filename_glob` is load-bearing, not tidiness. Published datasets accumulate: the ClinVar repo
  still carries a 159 MB single-file `clinvar.parquet` from an earlier layout whose columns are raw
  VCF INFO fields, and downloading it would put two schemas under one `data/*.parquet` glob. The
  globs are `homo_sapiens-*.parquet`, `clinvar-*.parquet`, `gnomad_constraint.parquet`, and `*.parquet`
  for the two multi-table gated snapshots.
* A **foreign** file already in the cache is reported with a specific warning and **never deleted** —
  "this is someone's cache directory".
* Remote parquet outside the glob is logged as ignored. If nothing matches, the error names how many
  parquet files the repo does carry and which they are.
* `citations/` sidecars, `release.json` and `LICENSE.txt` are fetched too; absence of any of them is
  normal and not an error.

`locations.read_release(path)` returns the parsed `release.json` as a dict, or `None` for absent,
unreadable or non-object — so a caller branches on `None` rather than on a default.

Release-label conventions differ per snapshot and are worth knowing:

| Snapshot | `release.json` key(s) used as the label |
| --- | --- |
| ClinVar | `clinvar_file_date` → `clinvar_<date>`, falling back to `clinvar_sha256:<digest>` from `source_sha256` (`clinvar.clinvar_dataset_label`). `assertions.snapshot_dataset` uses `clinvar_<date>` or `clinvar_unknown`. |
| gnomAD constraint | literal `"dataset": "gnomad_v4.1_constraint"` |
| ClinPGx | `clinpgx_<CREATED date>`, or `clinpgx` when undated |
| CPIC | `cpic_snapshot_<first 12 hex of a content digest>` — CPIC publishes no release id, so the digest over the sorted records stands in |
| PharmVar | `pharmvar_snapshot_<first 12 hex>`, plus `genome_build`, `redistributable: false` and a notice |
| Ensembl | undetermined from code — no builder in this package writes one, and `enrich._snapshot_release` reads `dataset` and withholds when absent |

---

## 6. The drafting providers

Three providers, all append-only. None ever rewrites an authored cell: a row whose key already
exists is *reported*, never replaced — drift against a source is the corresponding check's finding.
None stamps `authorship`. All three go through `just_dna_compiler.draft`'s `append_rows` /
`append_partial_rows`.

Two of the three ask `enrich.source_build_mismatch(spec_dir, source, "GRCh38")` **before** doing any
work (`draft` and `draft-panel`), because that function raises `EnrichmentError` on a present-but-
unreadable `module_spec.yaml` and asking afterwards meant paying for the source queries first. The
warning it returns is *reported, not repaired*: the coordinate is still written.

`cli._DRAFT_PRECONDITION_ERRORS = (DraftError, EnrichmentError)` exists so every drafting command
catches that precondition failure and exits cleanly rather than tracebacking.

### 6.1 `draft` — CPIC → `haplotypes.csv`, `allele_function.csv`, `diplotypes.csv`

* **Source**: CPIC, snapshot-first (`resolve_cpic_reference` → `CpicSnapshotClient`), else live
  `CpicClient` unless `--offline`.
* **Licence gate**: `check_declared_use(CPIC_TERMS, declared_use)` runs first; a skip reason returns
  `PgxDraftResult(skipped=True)` with nothing fetched.
* **Skip guards**, each derived from the model rather than restated beside it:
  * a defining variant whose `variantallele` is unusable (`cpic.unusable_allele_reason` →
    `"ambiguity"` / `"symbolic"` / `"notation"` / `"unobservable"` / `"missing"`) is skipped, already
    reported by the client, aggregated per reason with three examples and a `(+N more)` tail;
  * an allele name that is not `STAR_ALLELE_PATTERN` is skipped with a warning;
  * `_haplotype_rows` mirrors `HaplotypeRow._validate_identification` exactly — rsID **or**
    (chrom **and** start). The comment records that the guard previously accepted a bare `start` and
    `draft --gene CYP2C9` died on an unhandled pydantic error.
  * a diplotype that is not a pair of star alleles (CPIC writes copy number as `x≥3`) is skipped and
    aggregated;
  * a non-numeric activity score is split into two buckets and reported apart: `"unscored"`
    (CPIC's `n/a`, an absence) versus `"bounded"` (`≥3.0`, a real bound the numeric columns cannot
    hold).
* **Filters**: `--allele` applies to **all three** tables (defining variants, function rows, and only
  diplotypes whose *both* halves are in the set); `*1` is always kept because it is defined by
  carrying no variants. An unknown allele name **refuses** and lists what CPIC publishes.
  `--population` filters CPIC's clinical contexts; every context is drafted by default as separate
  rows carrying `clinical_context`, and an unknown population is an error rather than a silent empty
  draft.
* **Keys**: `just_dna_compiler.draft`'s own `_TABLE_DUPE_KEYS`; drug rows sit *beside* phenotype rows
  because the key includes `drug`.
* **`SourceRow`**: `CPIC_TERMS.row("annotation", declared_use=…, dataset=cpic_dataset)` merged with
  `merge_sources_file`, then `stamp_draft_digest(spec_dir, "cpic", "annotation")` — restamped
  explicitly, because `merge_sources_file` is never-clobber and a second draft's digest would
  otherwise be silently dropped. `dataset` is `None` on the live route (no release to name), which
  means the tautology skip in `pgx` simply does not fire — the conservative direction.
* **`knows_drug` isolation**: the extra call that sharpens an empty-result message is wrapped in its
  own `try/except CpicError`, so a transport failure there cannot discard a finished draft.

### 6.2 `draft-panel` — ClinVar → `variants.csv` (+ `studies.csv`)

* **Source**: an explicit `--snapshot`, else the cache ladder, else `ensure_clinvar_snapshot()`.
  With nothing found it raises, naming *which* switch blocked it (`--offline`, `--no-download`, or
  neither after a failed provisioning attempt).
* **Selection**: `clinvar.select_by_gene(reference, genes, clin_sig=…, min_review_stars=…)`.
  Default `clin_sig` is `{"pathogenic", "likely_pathogenic"}`; default `min_review_stars` is 2.
* **Rows are partial by design.** `VariantRow.genotype` is required and ClinVar publishes alleles,
  not genotypes, so `genotype` carries `vocab.TEMPLATE_PLACEHOLDER` and the module will not compile
  until a human decides. `state` is stubbed too whenever `_STATE_BY_CLIN_SIG` has no fold for the
  call (only `pathogenic`/`likely_pathogenic` → `risk` and `benign`/`likely_benign` → `neutral`).
  Rows are placed into their gene's block (`group_by=("gene",)`).
* **The one cell it *can* decide**: `sole_expressible_genotype` writes a single-allele genotype on MT
  and on non-PAR chrY, where exactly one genotype is expressible; chrY inside a PAR, and a build with
  no PAR table, both keep the placeholder.
* **Identity is filled whole or not at all**: an rsID alone, or the full `chrom`/`start`/`ref`/`alts`.
  An rsID that names several alts at one site (`multi_allelic_rsids`) is forced to the coordinate,
  and the `studies.csv` rows for it must take the same identity or the compiler's orphan check fires.
* **Match key**: `_MATCH_ON = ("rsid", "chrom", "start", "ref", "alts")` — the *identity*, not the
  natural key, because the natural key runs through the stubbed `genotype`.
* **`studies.csv`**: drafted from `clinvar.citations_for` (the optional `citations/` sidecar),
  capped at `--max-citations` (default 3), deduplicated per `(identity, pmid)`. A citation ClinVar
  filed under `PubMed` that is not a PMID is skipped and **counted apart** from the cap.
* **`SourceRow`**: `CLINVAR_TERMS.row("annotation", …, dataset=clinvar_dataset_label(reference))`,
  then `stamp_draft_digest`, then — only when rows were actually added —
  `withdraw_stale_dataset(...)`, which **blanks** a `dataset` naming a different release rather than
  re-labelling it, because one column cannot name two releases.
* **Refusals are grouped by reason** (`_refusal_summary`, capped at six named rows), while the
  genotype worklist is **uncapped** — the first is context for a diagnosis, the second is a task list.

### 6.3 `draft-clinpgx` — ClinPGx snapshot → `pharm_variants.csv`

* **Source**: strictly inject-only. `--snapshot` is required; nothing is downloaded.
* **Skip guards** (all aggregated, all counted within the requested `--gene` scope — the gene filter
  runs *first* so the "unidentified" count is not inflated by the rest of the database):
  * no rsID → `skipped_unidentified`;
  * `genotype` starting with `*` → `skipped_haplotype` (belongs on `DiplotypeRow`);
  * a `del`/`ins`/`dup` genotype → `skipped_symbolic`, and the message says the reason is the missing
    **length**, not the grammar (RM5 made `<DEL:1500>` authorable, ClinPGx publishes no length, and a
    lengthless symbolic allele is a rule the compiler drops);
  * anything else not an unambiguous two-base call → `skipped_other`.
* **`_authored_genotype`** splits only an unambiguous `[ACGT]{2}` cell into a sorted `C/T`; anything
  else declines rather than guessing.
* **Multi-valued cells**: `drugs` is `;`-joined and *is* in the dedup key, so one record becomes one
  row per drug. `gene` is `;`-joined and sits **outside** the key, so it cannot become several rows —
  `_authored_gene` writes the single member `--gene` selected, and otherwise **withholds** the cell
  and reports it (`396 of 16,087 rows carry a `;` in `gene``).
* **Key**: `(variant_key, drug, genotype, phenotype_category, annotation_id)` — all five. The bare
  triple is documented as a bug this package has already made once.
* **`conclusion`** is the source's own `annotation_text` verbatim, falling back to a synthesized
  `ClinPGx <id>: <genotype> and <drug> — <category>` only when the sentence is absent.
* **`SourceRow`**: `CLINPGX_TERMS.row("annotation", …, dataset=release["dataset"])` +
  `stamp_draft_digest`.

### 6.4 Draft provenance (`provenance.py`)

`DRAFT_PROJECTIONS` maps each drafting source to `(table, identity columns, checked columns)`:

| Source | Table | Identity | Checked |
| --- | --- | --- | --- |
| `clinvar` | `variants.csv` | `rsid, chrom, start, ref, alts` | `clin_sig` |
| `cpic` | `allele_function.csv` | `gene, allele` | `function_status` |
| `clinpgx` | `pharm_variants.csv` | `rsid, chrom, start, ref, drug, genotype, phenotype_category, annotation_id` | `evidence_level` |

`draft_digest` reads the table with `csv.DictReader` over **raw cells** — not loaded models — because
the same function must run at draft time, when the table is full of `<<REPLACE>>` and the model
loader refuses it outright. Cells are stripped, missing columns render as the empty string, rows are
sorted (order-independent), joined with `\x1f`/`\x1e` control characters and SHA-256'd.

`drafted_unchanged` is tri-state: `None` (nothing recorded — nothing established), `False` (a checked
value moved, *or* a digest was recorded and the table is now gone), `True`. `True` alone is never
grounds to skip a check: the caller conjoins it with a release match.

---

## 7. The check and verification surface

### 7.1 The checks

| Check | Where | Question | Outcomes | Severity |
| --- | --- | --- | --- | --- |
| Reference allele | `sequences.verify_reference_alleles` | Does the authored `ref` equal the reference sequence at the authored position? | `RefCheck(mismatches, subjects, not_checked)`. `not_checked` ∈ `unsupported` (no refget table for the module's build), `offline`, `unreachable`, `not_requested`. Rows with no coordinate, a non-ACGT `ref`, or an empty read are outside `subjects`. | `strict` **refuses**; `best_effort` warns (red on the CLI even in best_effort). |
| Wrong build | `grch37.diagnose_wrong_build` | Do the ref-mismatched rows read as GRCh37? | Three evidence tiers — `single_base_match` (suggestive; one base in four agrees by chance, and VCF 4.4 §1.6.1.4 lossy reduction is named), `multi_base_match`, `dbsnp_corroborated` (strongest, names the rs-number) — plus `unchecked`. Bounded at `DEFAULT_DIAGNOSIS_LIMIT = 50`, with `sampled` saying so. | Never refuses on its own; it travels **inside** the strict ref-mismatch refusal message. |
| `clin_sig` cross-check | `clinical.compare_clin_sig` | Does the authored clinical call agree with ClinVar's? | `ClinSigComparison(compared, no_record, conflicts)`, or `None` when it could not run. Camps are coarse: `pathogenic`/`likely_pathogenic`/`risk_factor` vs `benign`/`likely_benign`/`protective`, with `undecided` and `orthogonal` camps that never conflict. | **Warns in both modes, deliberately.** Escalating would make the format arbitrate a clinical dispute. |
| rsID currency | `identifiers.check_rsids` (inside `enrich`) | Is this rsID still what dbSNP serves? | `live` / `merged` / `absent` / `withdrawn`. `absent` is byte-identical for a typo and a withdrawal, and the message **names both readings and asserts neither**. `withdrawn` is never produced by the API path. | `withdrawn` refuses in **both** modes; other staleness refuses under `strict` only. The verdict is stamped onto `rsid_status`/`rsid_current`, never substituted for the authored label. |
| rsID ↔ coordinate | `resolver.check_rsid_coordinates` + `enrich._check_authored_pairs` | Is the authored coordinate among the loci the rsID resolves to? | `PairCheck(disagreements, subjects, unknown, undecided, not_checked)`. `coordinate_verdict` is three-valued: `True`; `False` only when every locus (and the row's own `ref`) is a substitution; `None` when an indel is involved, because re-anchoring legitimately moves the position. Compared at `chrom:start` with the contig normalized — never at `chrom:start:ref`. | **Warns in both modes**, and has **no severity gate at all**, so nothing can disagree with the record. |
| ACMG SF | `acmg.check_acmg_sf` | Does `acmg_sf` agree with the ACMG secondary-findings list? | Per row: `agree`, `not_listed`, `denied`, `unverifiable`, `unstated`, `blank`, `unchecked`. A disagreement against a list this package knows is **superseded** (`KNOWN_LATEST_SF_VERSION = "3.3"`) is demoted to `unverifiable` **in both directions**. | `strict` refuses on `mismatches` only; it never refuses on `unverifiable`. |
| Trait currency | `identifiers.OntologyClient.trait` | Is this CURIE current in OLS4? | `current` / `obsolete` / `absent` / `unchecked` (a prefix outside `_ONTOLOGY_IRI`, answered without a request). | `check-identifiers --strict` exits 1 if anything is stale. |
| Gene symbol currency | `identifiers.OntologyClient.gene` | Is this symbol HGNC-approved? | `approved` / `retired` (with the approved replacement) / `unknown`. | as above |
| Gene ↔ locus | `identifiers._gene_locus_conflicts` | Is the row's gene on the same chromosome as its variant? | Conflicts + a `compared` denominator + a prose reason when it could not run. **Chromosome granularity only**, deliberately; an X/Y pair is exempt (a PAR locus is one place on two contigs). Withholds on an unparsed HGNC band or an unknown chromosome. | as above |
| Allele function | `pgx._compare` | Does the authored `function_status` match PharmVar's / CPIC's? | Conflicts + the set actually compared. | **Warns in both modes** — two expert panels genuinely disagree. |
| PGx evidence level | `clinpgx.enrich_clinpgx` | Is the authored `evidence_level` still ClinPGx's? | Conflicts, plus `unmatched`, plus an explicit "cannot tell" when several annotations exist and the row names no `phenotype_category` or `annotation_id`. | `strict` **refuses** — an evidence level is ClinPGx's own metadata about its own annotation, so a difference means the module is stale, not that two panels differ. |
| Citation existence | `literature` | Does the PMID resolve in PubMed / the DOI in Crossref? | `exists` tri-state; `doi_exists` tri-state pinned with `doi_checked`. | `strict` refuses on `missing`, on `doi_missing`, on `doi_conflicts` and on `pmcid_conflicts`. |
| Citation identifier | `literature._compare_identifiers` | Do the authored DOI/PMC id agree with the registry's? | Conflicts, plus four counters kept apart: `authored`, `compared`, `unmatched` (registry named none), `foreign` (a curator wrote the row, so its identifiers are not the registry's). | `strict` refuses. |
| Provenance quote | `literature` | Does the quoted passage appear in the article? | `quotes_found` is **null, not zero**, when no text could be read. An abstract **hit** settles a quote; an abstract **miss** does not. | Never refuses. |
| VRS coverage | `vrs.MintResult` | How many allele slots carry a `ga4gh:VA.` id? | Counted per **ALT slot**, not per row; `unmintable_reasons` groups by reason. Permanent classes (`SYMBOLIC_REASON`, `MISSING_ALT_REASON`, `MISSING_REF_REASON`, `UNOBSERVABLE_REASON`) are kept apart from the re-runnable ones. | Warning only, never a refusal. |

Two recurring rules are worth stating explicitly because they are implemented independently in nine
places: **a check that cannot fail must not report a zero** (the tautology skips), and **a denominator
comes from the check that computed it, never recomputed beside it**.

### 7.2 The tautology skips

Three checks are structurally unable to fail on a module drafted from the very source they read.
Each skip is a **conjunction**, and either half missing runs the check in full:

1. the licence row for `(source, "annotation")` records **this release** (`dataset` matches the label
   recomputed from the snapshot in hand), **and**
2. `provenance.drafted_unchanged` says every checked cell still hashes to what the drafter wrote.

* `clinical.tautology_reason` — ClinVar `clin_sig`. Matched at the `annotation` layer specifically,
  because `enrich()` writes a second `clinvar` row at the `resolution` layer and a coordinate is not
  a copied clinical call.
* `pgx._tautology_note` — per **leg**, not per record: a drafted module's CPIC leg is tautological
  while PharmVar's independent leg still runs. The skip is surfaced on `result.warnings`, not only
  logged, because in the mixed case the record's `detail` names only the answered route.
* `clinpgx.enrich_clinpgx` — ClinPGx `evidence_level`.

In `pgx._SKIP_PRECEDENCE`, `tautology` sits **last**: the others say the source could not be
consulted, and an absence has a remedy the reader needs to hear.

### 7.3 `verification.json`

`verification.record_verification(records, spec_dir, error=…)` is the one load-merge-write. It:

* resolves the write path through `layout.sidecar_write_path` (so a `derived/` module does not gain
  a second copy at root), re-raising `SidecarCollision` as the caller's own error;
* recomputes the module **binding** from `compiler.authored_input_entries(spec_dir)` on every call,
  so the record perishes the moment an authored file is edited;
* merges existing records with `verification.merge_records(..., existing_still_binds=…)`: a *skip*
  this run writes does not displace an earlier real answer **while the authored bytes still bind**;
* carries an existing `closure` across only while the binding holds, and **drops rather than
  re-binds** it otherwise — only the author may re-close;
* replaces an unparseable existing document wholesale, with a warning;
* returns `None` and writes nothing when there are no records — a run that put no check has nothing
  to say.

Two constructors: `ran(check, subjects=, findings=, source=, release=, detail=)` and
`skipped(check, reason, detail=, source=)`. `verification.DETAIL_LIMIT = 5` bounds how many per-row
sentences a `detail` carries before it becomes a count; `verification.examples(names)` renders
"a, b, c and N more".

Which commands write records, and which check members:

| Command | Records written |
| --- | --- |
| `enrich` | `reference_allele`, `genome_build_agreement`, `clinical_significance`, `rsid_currency`, `rsid_coordinate_agreement` (5) |
| `literature` | `citation_existence`, `citation_identifier`, `provenance_quote` (3) |
| `check-identifiers` | `trait_currency`, `gene_symbol_currency`, `gene_locus_agreement` (3) |
| `check-acmg` | `acmg_secondary_findings` |
| `clinpgx check` | `pgx_evidence_level` |
| `pgx` | `allele_function` |
| `vrs mint` | `vrs_allele_id`, always as `skipped(…, "nothing_to_check")` |

`verification.py`'s own module docstring claims "seven of them, for fifteen of the seventeen check
members" and names `gene_disease_validity` and `dosage_sensitivity` as reserved. That matches the
seven commands above.

Two attestation rules that surprise:

* **`vrs mint` always records a skip**, never a coverage figure. The member names a *cross-check* of
  a source-reported id against the minted one, and `resolution.csv` never records where an id came
  from, so the question was not put. The coverage counts travel in `detail`.
* **A check that does not apply is not attested at all.** `clinpgx check` on a module with no
  `pharm_variants.csv`, `pgx` on a module with neither PGx table, and both `check-*` commands on a
  module with no `variants.csv` all return without writing — recording a skip would mine a nonce and
  create a `verification.json` on a module that never asked for one.

On a failed run, `cli._attest_on_the_way_out` records the skip and reports (never raises) if the
attestation itself fails, because the command is already exiting with the real reason. Where the
*check* succeeded and only the attestation failed, the message is
`CHECKED, BUT NOT ATTESTED: …` / `MINTED, BUT NOT ATTESTED: …` and the exit code is 1.

`check-acmg` distinguishes two failure classes precisely: `AcmgListUnavailable` (carrying `.skip` =
`unreachable` or `no_reference`) attests a skip on the way out; a plain `AcmgSfError` — a `strict`
refusal, or an unloadable `variants.csv` — attests **nothing**, because the list *was* read and
recording a skip would say the question was never put.

---

## 8. Licensing and the gated sources

`licensing.SourceTerms` records `source`, `license`, `license_url`, `attribution`, `notice`,
`share_alike`, `commercial_use`, `redistribution` — all three booleans tri-state, with `None`
meaning "could not be established", never `False`.

| Source | Licence | `share_alike` | `commercial_use` | `redistribution` | Gated? |
| --- | --- | --- | --- | --- | --- |
| `clinpgx` | CC-BY-SA-4.0 + no-sale clause | true | **false** | true | yes |
| `cpic` | CC-BY-SA-4.0 (merged into ClinPGx; `cpicpgx.org/license/` 302-redirects to the ClinPGx policy) | true | **false** | true | yes |
| `pharmvar` | CC-BY-SA-4.0 + research-use-only + no-sale (§3) | true | **false** | true | yes |
| `clingen` | CC0-1.0 | false | true | true | no |
| `gencc` | CC0-1.0 | false | true | true | no |
| `clinvar` | public-domain (NCBI) | false | true | true | no |
| `ensembl` | Apache-2.0 | false | true | true | no |
| `gnomad` | CC0-1.0 | false | true | true | no |
| `gwas_catalog` | **none named** — EBI states terms in prose | `None` | **`None`** | true | no (warns, never gates) |

The GWAS Catalog entry is the interesting one: `commercial_use` stays `None` deliberately, because
EBI's permission is conditioned on the original data owners' terms, which are not established for an
aggregator of thousands of studies. `taints_commercial_use` requires `commercial_use is False`, so a
null warns rather than gating. The comment says in as many words: do not "tidy" it to `True`.

`check_declared_use(terms, declared_use)` has **three** outcomes:

* **raise `LicenseRefusal`** — the source forbids sale and the caller declared `commercial`. Fatal in
  both modes; nothing is fetched.
* **return a reason string (skip)** — either the caller declared nothing and the source forbids sale,
  or the source's terms are *unknown* (`commercial_use is None`).
* **return `None`** — proceed.

The gate runs **at acquisition**, which is why `cache pull`, `clinpgx build`, `cpic build`,
`pharmvar build`, all three drafting providers, `pgx` (per leg) and `clinpgx check` each call it
before touching the source.

`declared_use` is a third axis with three states (`unstated` / `non_commercial` / `commercial`) and
is never folded into `mode`. It is normalized through the schema's `check_vocab`, so a caller passing
`non-commercial` gets the same verdict the identical string in a cell would.

### Credentials

* **PharmVar** — `PHARMVAR_API_KEY`, read in `PharmVarClient.__init__` *after* an explicit
  `load_env()`, and sent as the plain `Api-Key` header (not `X-API-KEY`, which returns the same 401).
  Every failure mode — absent, malformed, unrecognised — produces an identical HTTP 401, so the
  error message names all three and the key is never echoed, logged, or written into a module,
  fixture or snapshot. An absent key is a **skip** in `enrich_pgx` and an **error** in
  `pharmvar build`, because building is an explicit act with an explicit output.
* **NCBI** — `NCBI_API_KEY` is optional and only tightens the pacing gate.
* **HuggingFace** — a write token via `hf auth login` or `HF_TOKEN`, resolved in `upload._hf_api`;
  its absence is a `PermissionError` naming the repo.
* No credential of any kind is needed for CPIC, Ensembl, gnomAD, Europe PMC, Crossref, OLS4, HGNC,
  ClinGen, GenCC or the GWAS Catalog.

### What the tier records

`record_source_terms(names, layer, spec_dir, error=…, declared_use="unstated")` writes a `SourceRow`
per known source. A name with no `TERMS_BY_SOURCE` entry is **skipped rather than guessed at**.
Existing rows are never clobbered (`merge_sources_csv` uses `setdefault` on `(source, layer)`).

`SOURCES_FIELDNAMES = list(SourceRow.model_fields)` — derived from the model, because a hand-kept
list previously omitted `redistribution` for a whole release. `_cell` keeps the tri-state intact:
`None` → empty, `True` → `"true"`, `False` → `"false"`.

Layers written by each pass: `resolution` (`enrich`), `frequency`, `gene_metrics`,
`gene_validity`, `clinical_assertion`, `gwas_effect`, `annotation` (every drafting provider,
`clingen` dosage, `pgx`, `clinpgx check`).

`withdraw_stale_dataset` is the **only** place anything overwrites a cell `merge_sources_file` would
have kept, and it only ever *blanks* a `dataset` this run's rows did not come from — never re-labels,
because a module carrying rows from two releases has no honest single value.

`read_sources_file` is the gentle counterpart: an unreadable table returns `[]` and every check
keeps running, whereas a pass that *writes* fails loudly on one.

### Article-level licensing (`literature`)

There is deliberately **no `pubmed` entry in `TERMS_BY_SOURCE`**: a literature source's terms are per
*article*, not per source. `ARTICLE_TERMS_BY_LICENSE` maps Europe PMC's own lowercase spellings
(`cc0`, `cc by`, `cc by-sa`, `cc by-nd`, `cc by-nc`, `cc by-nc-sa`, `cc by-nc-nd`) to three rights;
`article_terms()` is case-insensitive, tolerates the `CC-BY-NC` spelling, and returns all-`None` for
anything it does not know. The licence string is stored **verbatim** on the row and mapped at read
time, so a correction reaches rows already written. A quote taken from an article whose
`commercial_use` is `False` is reported (yellow, never a non-zero exit) as
`quoted under a non-commercial licence: … — the passage is publisher text in this module's
annotation layer`.

---

## 9. Publish and upload

### 9.1 Module upload (`upload_module` / `plan_upload`)

Destination: `datasets/<repo>/data/<name>/` — which keeps meaning *latest* — and, when the manifest
states an `identity.version`, `data/<name>/v<version>/` **nested inside it**. These are **two
commits**, not one: `upload_folder` commits per call, and the flat path goes first because it is what
deployed readers are pointed at. If the second call fails the first has already landed, and a re-run
is idempotent. Nothing checks the remote, so re-publishing without bumping the version overwrites
the versioned path with different bytes.

`_ALLOW_PATTERNS` is **derived**, not restated: `*ARTIFACT_PARQUETS` (from
`just_dna_compiler.compiler`), `manifest.json`, `logo.png`, `logo.jpg`, `*README_CANDIDATES` (from
`just_dna_format.manifest`). The comment records the measurement that forced this: on 2026-08-17 the
old hand-kept triple meant seven of sixteen reference examples could not be published at all and
eight published an artifact whose `manifest.artifact.files` attested six kinds of parquet the
allowlist dropped — `sources.parquet` worst among them.

`plan_upload` enforces three positive rules, ordered most specific first:

1. **Everything the artifact attests must be carried.** `_attested_parquets` reads
   `manifest.artifact.files[].name` out of the raw JSON (not through `read_manifest`, so an unrelated
   model defect cannot withhold a legible list) and refuses if the plan would drop any of them,
   because `artifact.digest` is a Merkle root over exactly those files. It is tri-state: an absent or
   unreadable manifest **withholds** rather than refusing.
2. **`weights.parquet` never travels alone** — `annotations.parquet` and `studies.parquet` must be
   beside it (`_EXPECTED_WITH_WEIGHTS`), because a SNP core compiles to all three.
3. **At least one lead table** (`LEAD_PARQUETS`) must be present.

`_module_version` returns `(version, reason_it_is_unknown)` with exactly one member set, and the four
reasons are told apart: no manifest, unreadable JSON, no `identity.version`, or a value that is not
`MAJOR.MINOR.PATCH` (checked with `identity.is_valid_version`, which also keeps a stray `/` or `..`
out of a path segment).

Default commit messages: `Add <name> module` and `Add <name> module v<version>`.

### 9.2 Reference-snapshot publish (`publish_reference_snapshot` / `plan_reference_snapshot`)

Uploads to the repo **root** with `_SNAPSHOT_ALLOW_PATTERNS`:

```
data/*.parquet
citations/*.parquet          (one entry per SNAPSHOT_SIDECAR_DIRNAMES)
release.json
LICENSE.txt
```

so the published tree matches exactly what `download.ensure_*_snapshot` provisions. Both the
sidecars and `LICENSE.txt` were previously missing from these patterns; the comments record why each
matters — without `citations/` a downloaded snapshot has no PMIDs and a drafted panel cannot compile,
and without `LICENSE.txt` a share-alike snapshot's `license_sha256` pins nothing for whoever
downloads it.

`plan_reference_snapshot` refuses when `data/` holds no parquet. Default repo is
`anon-org/clinvar`; `constraint publish` passes `DEFAULT_CONSTRAINT_REPO_ID`, `cpic publish` and
`clinpgx publish` pass theirs as the flag default.

`ensure_repo` is create-or-update: `create_repo(repo_type="dataset", exist_ok=True)` followed by the
caller's `upload_folder`, with one `HfApi` per publish.

---

## 10. Undetermined from code

* **The Ensembl snapshot's builder and its `release.json`.** `download.ensure_snapshot` provisions
  `datasets/anon-org/ensembl_variations/data/homo_sapiens-*.parquet`, and `resolver.py` reads a
  fixed column set (`id`, `chrom`, `start`, `ref`, `alt`), but nothing in this package builds that
  snapshot or writes its `release.json`. `enrich._snapshot_release` reads a `dataset` key that no
  builder here produces, so the `rsid_coordinate_agreement` record's `release` is `None` in practice
  unless something outside this repo writes one.
* **What the ClinVar snapshot's `cache status` label should be.** `clinvar_build._write_release_json`
  writes no `dataset` key, and `cache status` prints `release.get("dataset") or ""` — so a correctly
  built ClinVar snapshot shows a blank label. Whether that is intended (ClinVar has its own richer
  `clinvar_dataset_label`) or an oversight is undetermined from code.
* **`enrich_gwas(mode=…)`.** The parameter is accepted, defaulted and never read. The CLI's
  `--strict` help says "Severity ladder for findings; see the pass docstring", and the pass docstring
  describes no ladder. Whether the intent was a `strict` refusal on `missing` (as the sibling passes
  have) or no ladder at all is undetermined from code — no test covers either.
* **`identifiers.IdentifierCheckError`.** Declared with a docstring and never raised anywhere.
* **`CpicClient.knows_drug` return type.** Annotated `bool | None`; the live implementation can only
  return `bool` or raise, and only `CpicSnapshotClient` ever returns `None`. `pgx_draft` handles all
  three, so this is a deliberate widening rather than a defect — but the live client's own docstring
  does not say so.
* **Whether `check-identifiers` is meant to have an `--offline`.** `identifiers.verification_records`
  argues it must not; the sibling `check-acmg` has one. Consistent with itself, undetermined as
  policy.
* **`net.py`'s "nine policies".** The docstring and the retry-floor test both speak of nine
  `@retry` policies. Counting them in the tree gives twelve: `ensembl` ×2, `eutils`, `gnomad`,
  `grch37`, `identifiers`, `literature` ×3, `cpic`, `pharmvar`, `gwas`. The test asserts
  `len(found) >= 9` while walking only seven of the ten modules that carry one (`grch37` and `gwas`
  are not in its list), so it does not catch the drift.

---

## 11. Bugs and internal contradictions found in the code

Each of these is a statement about the code, not about documentation. The first two were reproduced.

### Bug 1 — `python -m just_dna_enricher.cli` silently loses four commands

`cli.py:1688` places

```python
if __name__ == "__main__":
    app()
```

**above** the registrations for the `hint` sub-app (line 1693), `draft-clinpgx` (1877), `draft-panel`
(1922) and `clinvar citations` (1996). Under the console script `just-dna-enricher` this is harmless
— the module is imported, not executed — but `python -m just_dna_enricher.cli` and
`python enricher/src/just_dna_enricher/cli.py` execute `app()` mid-module, so those commands do not
exist. Reproduced:

```
$ python -m just_dna_enricher.cli --help    # 23 commands, no hint/draft-clinpgx/draft-panel
$ just-dna-enricher --help                  # 26 commands, all present
```

`clinvar citations` is affected the same way, since `@clinvar_app.command("citations")` is applied
after the guard even though `clinvar_app` itself is registered earlier.

### Bug 2 — an offline run with no cache writes a negative nobody established

`enrich.py:851-853`:

```python
elif genome_build == "GRCh38":
    out.append(ResolutionRow(variant_key=key, rsid=v.rsid, genome_build=genome_build,
                             source="ensembl" if not offline else "cache", status="not_found"))
```

The two branches immediately around it exist precisely to avoid this shape: an unreachable live link
writes **no row** (`v.rsid in unreachable_rsids`), and a non-GRCh38 module writes no row, both with
comments saying that `not_found` would state "the source was asked and does not have this rsID — a
negative nobody established". But when `--offline` is set and **no Ensembl cache exists at all**,
nothing was opened and the row still claims `source="cache", status="not_found"`, and
`resolution_authority("cache")` then stamps `authority="ensembl"`. Reproduced with an empty cache
base:

```
ROW rs1799945 | source= cache | status= not_found | authority= ensembl | chrom= None
resolution.csv: rs1799945,rs1799945,,,,,GRCh38,0,,,,cache,ensembl,not_found,,,,
```

A `SourceRow` for `ensembl` at the `resolution` layer is written for the same run, recording terms
for a source that was never read. No test covers this path.

### Bug 3 — `clinvar_build._sha256_file` is defined twice

`clinvar_build.py:252` defines `_sha256_file(path) -> str` (no error handling); `clinvar_build.py:445`
defines it again as `_sha256_file(path) -> str | None`, catching `OSError` and returning `None`. The
second shadows the first for every call site. The consequences are type contradictions the
annotations deny:

* `build_snapshot` passes the result into `_write_release_json(source_sha256: str)` and into
  `BuildResult(source_sha256: str)`, both of which can now receive `None`;
* the first definition is dead code.

### Bug 4 — three passes bypass the shared sidecar resolver

`licensing.sidecar_path` exists so a pass writes to the file the module already has, including under
`derived/` (and `test_sources_spelling` / `test_clinical_assertions` pin that for other passes).
Three passes join the filename onto the spec directory by hand instead:

* `gene_metrics.enrich_gene_metrics` — `output_path = spec_dir / "gene_metrics.csv"` (line 155);
* `clingen.enrich_dosage_sensitivity` — same path (line 175), reading and rewriting the same table;
* `literature.enrich_literature` — `output_path = spec_dir / "literature.csv"` (line 712).

A module keeping its derived sidecars under `derived/` therefore ends up with `gene_metrics.csv` and
`literature.csv` at the root while `resolution.csv`, `frequencies.csv`, `gene_validity.csv`,
`gwas_effects.csv`, `clinical_assertions.csv` and the licence table are written under `derived/`.
`gene_validity.py` — which shares `module_genes` with `gene_metrics.py` and is otherwise its sibling
— does use `sidecar_path`, so this is an inconsistency inside one family rather than a considered
exemption. (`literature.py` reading `studies.csv` from the root is correct: that file is authored.)

### Bug 5 — the NCBI credential and contact address are read without loading `.env`

`eutils.EutilsSettings.__post_init__` reads `NCBI_API_KEY` and `JUST_DNA_CONTACT_EMAIL` straight from
`os.environ`, and `literature.CrossrefClient` / `PmcIdConverterClient` read the latter the same way.
No `load_env()` call precedes any of them. `pharmvar.PharmVarClient.__init__` calls `load_env()`
explicitly, with a comment describing exactly this failure — the key "only reached `os.environ` as a
side effect of some *other* call resolving a cache path", which "worked for `enrich_pgx` by accident
and not at all for the snapshot builder".

The same accident is live for NCBI: a `.env`-only `NCBI_API_KEY` is picked up when some earlier call
in the process happened to resolve a cache path (`load_dotenv` mutates `os.environ` process-wide) and
is silently ignored otherwise. The visible effect is the pacing gate quietly staying at 1/3 s instead
of 1/10 s, and NCBI traffic going unattributed.

### Bug 6 — `CpicClient.row_count` bypasses its own client's exception contract

`cpic.py:334` calls `self._client.get(...)` directly rather than going through `_get`, so it has no
retry and no translation. Its only caller is `cpic_build._fetch_all`, which is the function whose
whole purpose is to refuse a short read — and a transport failure or a 5xx there escapes as a raw
`httpx` exception past `cli.cpic_build_`'s `except (CpicError, CpicBuildError)` handler. This is
exactly the leak the class docstring says was repaired for `_get`: "a client that leaks its transport
library's types has no contract at all."

### Bug 7 — `enrich_gwas` leaks its client on an exception, and `mode` is dead

`gwas.enrich_gwas` closes the catalog client with a bare `if client is None: catalog.close()` at the
end of the function (line 552), outside any `try/finally`. Every sibling pass uses `try/finally`
(`frequencies`, `gene_metrics`, `identifiers`, `enrich`'s two live links). A `GwasError` raised
mid-loop — which `associations_for` raises on an API shape change, and which the CLI catches — leaks
the `httpx.Client`.

Separately, `mode` is accepted and never read: unlike every other pass, `gwas` has no `strict`
escalation at all, while the CLI advertises `--strict/--best-effort` as a "severity ladder".
`result.covered` / `result.missing` are also the only ones in the tier not sorted-and-deduplicated
before being returned, so their order follows the fetch order rather than a stable one.

### Bug 8 — `gene-metrics` offline with no snapshot records an absence it never established

`gene_metrics.enrich_gene_metrics` logs, when `offline` and no snapshot resolved:

> `No gnomAD constraint snapshot found and --offline: gene metrics will be empty.`

The table is not empty. With `from_snapshot = {}` and the API branch gated on `not offline`, the
emission loop falls through to the `payload is None` arm and writes a
`GeneMetricsRow(status="not_found", source="gnomad", dataset=absent_from)` for **every** module gene
— and `absent_from = dataset` when offline, i.e. the v4.1 label `gnomad_v4.1_constraint`. So the row
states "gnomAD v4.1 was looked up and has no constraint for this gene" on a run where nothing was
consulted at all. The row's own comment says a `not_found` row is "a fact — the gene was looked up
and gnomAD has no constraint for it", which is exactly the claim this path cannot support.

`test_fact_passes.py:238` pins the `not_found` status (so the log line is falsified by the suite's
own fixture) but does not assert the `dataset` label, so the false release attribution is uncovered.
This is the same negative-nobody-established shape as bug 2, one pass over.

### Bug 9 — two clients leak `httpx.HTTPStatusError` past the handlers written to catch them

In both `gnomad._post` and `eutils._get`, `response.raise_for_status()` sits **outside** the
`try/except httpx.HTTPError` block, and `httpx.HTTPStatusError` is in neither client's
`retry_if_exception_type` list (`{RateLimitedError, TransportError, TimeoutException}` and
`{EutilsRateLimitedError, TransportError, TimeoutException}` respectively). A non-429 4xx or 5xx
therefore escapes immediately, untranslated, as a raw transport-library exception. Three call sites
are directly contradicted by it:

* `enrich()`'s gnomAD link catches `except GnomadError` under the comment *"a last-resort link must
  not sink the whole enrichment"*. An `HTTPStatusError` is not a `GnomadError`, so a gnomAD 502
  sinks exactly the run that comment promises it cannot.
* `enrich()` calls `check_rsids(asked)` (line 1020) with **no handler at all**, so a dbSNP 5xx
  during the rsID-currency check aborts the whole enrichment with a traceback — and the CLI catches
  `EnrichmentError` only, so it is not even rendered as a clean failure.
* `literature.enrich_literature` calls `client.esummary("pubmed", wanted)` inside a
  `try/finally` that closes the client but catches nothing, so the same 5xx aborts that pass.

This is precisely the contract violation `cpic.py`'s and `pharmvar.py`'s docstrings describe at
length as repaired for those two clients — *"a client that leaks its transport library's types has
no contract at all"* — left unfixed in the two clients with the tightest rate budgets, which are the
ones most likely to answer with a status code.

### Smaller contradictions

* **`cache pull`'s closing line is wrong under `--only`.** It prints
  `caches available: {', '.join(sorted(known))}` where `known` is *every* publishable cache, not the
  subset `--only` asked for or the subset that actually succeeded (`cli.py:1362`).
* **`net.py`'s "nine policies"** — see §10; the real count is thirteen.
* **`upload._ALLOW_PATTERNS` accepts `logo.png`/`logo.jpg` but the comment notes `logo.jpeg` is a
  known skew** with whatever the compiler can attest, "left alone here because widening it is not
  this item's decision". That is a documented, deliberate gap rather than a defect, but it is the
  same class the rest of the list was just fixed for.
