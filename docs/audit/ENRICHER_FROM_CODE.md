# `just-dna-enricher` — a reference re-derived from the code

Blind re-derivation: written from `enricher/src/**`, `enricher/tests/**`,
`enricher/pyproject.toml`, the workspace-root `pyproject.toml`, and as much of `schema/src/**` and
`compiler/src/**` as was needed to say what the enricher does with a model. The maintained
documentation (`docs/`, `README.md`, `CLAUDE.md`, `reference_examples/`) was deleted from the
worktree before this was written and was not consulted. Version under examination:
`just-dna-enricher 0.7.0` (`enricher/pyproject.toml:3`).

Every claim below is cited to a `file:line` I obtained from a `grep -n` run in this session, or to a
test. Where the code does not explain itself, §11 says so instead of guessing.

### Two disclosures, up front

**Contamination.** The harness injected the repository's `CLAUDE.md` into my context before I could
act, so I had read its headline rules for this tier before opening a file. Nothing in this document is
*sourced* from it — every claim is cited to code or a test, and I sourced no `docs/…` pointer. Three
places where having read it shaped **where I looked first**, named so a reader can discount them:

1. §12 D5 — I grepped the tree for `outrank` because `CLAUDE.md` carries a line about `--offline`
   outranking an injected client. The finding itself is code-sourced
   (`test_pgx_licensing.py:393`'s docstring makes the argument in its own words), but the search was
   prompted.
2. §9 — the prompt I gave the publisher agent asked whether the orphan guard reads the remote *tree*
   or the remote *description*, and whether a failed fetch stages through `.part`. Both framings are
   `CLAUDE.md`'s; both turned out to be answerable from the code, and both answers are cited there.
3. §5 and §6 — knowing in advance that a *lane registry* and an *exception contract* existed as named
   concepts is why I opened `caches.py` and `test_client_exception_contract.py` early rather than
   discovering them by sweep.

Two things that are **not** contamination and might look like it: the `@tag` vocabulary
(`@registry-completeness`, `@unreachable-not-absent`, and so on) appears verbatim in the **source
comments and test docstrings** throughout this package, so quoting a tag from a docstring is quoting
the code; and the defect archetypes I hunted for (an unreachable publish repo, a leaked transport
exception, a zero that cannot fail, a hand-kept roster) came from the task brief, not from
`CLAUDE.md`.

**A network call I did not choose.** The brief required `uv sync` to run `--help` against the real
CLI. `enricher/pyproject.toml` declares a hatchling build hook, and `enricher/hatch_build.py:31-40`
runs `atlas_protos.fetch_protos()` at build time — five HTTPS GETs to `raw.githubusercontent.com`.
Measured: the worktree was cut at 05:49 with `enricher/src/just_dna_enricher/_atlas_protos/` absent
(it is git-ignored, `.gitignore:238`); after `uv sync --all-extras` it exists with mtimes of
05:51:26. Nothing else in this session touched the network: I made no request to any source, ran no
fetching command, and did not set `JUST_DNA_NETWORK_TESTS`. See §12 D6.

### One naming note, because it affects every section

**The licence table has two accepted spellings and the familiar one is the deprecated one.**
`schema/src/just_dna_format/layout.py:45-67`: `SOURCES_CSV = "sources.csv"`,
`LICENSING_CSV = "licensing.csv"`, `SIDECAR_SPELLINGS = {SOURCES_CSV: (SOURCES_CSV, LICENSING_CSV)}`
("deprecated first and preferred last"), and `DEPRECATED_SPELLINGS = frozenset({SOURCES_CSV})`.
Removal is queued for 1.0, warn-only in both modes until then. The parquet and the manifest key keep
the old name on purpose — *"`sources.parquet` is inside `artifact.digest` and consumers read it by
name, and `manifest.sources` is a published key … For the whole 0.x tail a module therefore reads
`licensing.csv` → `sources.parquet` → `manifest.sources`."*

Where this document writes `sources.csv` it means **whichever spelling the module carries**, resolved
through `licensing.sidecar_path`. §7.4 works the distinction through properly.

### How to read this

Sections 1–10 are the reference. **§11 collects what the code did not settle** and **§12 collects the
defect candidates**, but both are deliberately *partial*: §6, §7, §8 and §9 each end with their own
defect and undetermined subsections, because the person who read a surface is the person who should
say what is wrong with it. §12 carries the findings I verified myself (D1–D4 written from my own
reading, D8–D15 re-verified against an agent's) and points at the rest.

Three findings I reproduced by running code, offline, rather than by reading it: a client that leaks
`httpx.ConnectError` past its own translation contract (D10), a `@retry` decorator that never fires
(D11), and a pass that cannot see a credential in `.env` (D12).

---

## 1. Module map

**76 Python modules** under `enricher/src/just_dna_enricher/` (measured:
`find enricher/src -name '*.py' | wc -l` = 76, of which one is `__init__.py` and one is the
`generated/_alphagenome_atlas_protos/__init__.py` stub). **98 test modules** under `enricher/tests/`.
48,837 source lines and 40,759 test lines.

Dependencies (`enricher/pyproject.toml:16-40`): `just-dna-format`, `just-dna-compiler`, `duckdb`,
`platformdirs`, `python-dotenv`, `httpx`, `tenacity`, `huggingface-hub`, `typer`, `ga4gh.vrs`. Extras:
`[atlas]` = `grpcio` + `protobuf`; `[dev]` = `pytest`, `polars`, `grpcio-tools`, `openpyxl`. The arrow
points one way — format and compiler never import this tier.

This package is the **only** one allowed to fetch, and `polars` is a builder-only dependency here
(guarded imports), so the runtime resolver path stays polars-free.

### 1.1 Entry point and orchestration

| module | lines | owns |
| --- | --- | --- |
| `cli.py` | 5259 | the whole Typer surface: 36 top-level entries, 64 leaf commands (§4) |
| `enrich.py` | 2520 | `enrich()` — the resolver chain, the in-run validation passes, the strict gates, the commit (§2) |
| `caches.py` | 1480 | `CACHE_LANES`, the 15-lane registry, and `prepare`/`rebuild`/`status` over it (§5) |
| `locations.py` | 775 | cache-path resolution, env vars, `read_release`, `repro_out`, `.env` loading |
| `transaction.py` | 368 | staged answers (`ResolutionJournal`), the advisory `spec_lock`, `SubjectProgress` |
| `verification.py` | 249 | `ran`/`skipped`/`record_verification` — the one load-merge-write for `verification.json` |
| `licensing.py` | 1236 | `SourceTerms`, `check_declared_use`, `record_source_terms`, `sidecar_path`, `overlay_answers` |
| `provenance.py` | 216 | drafted-vs-hand-edited: telling a copied value from an edited one (RM73) |
| `__init__.py` | 9 | package docstring only — no re-exports |

### 1.2 Network clients and shared transport

| module | lines | owns |
| --- | --- | --- |
| `net.py` | 312 | shared HTTP-politeness primitives: pacing, retry, the exception base |
| `ensembl.py` | 220 | live Ensembl resolution (V2 GraphQL → V1 REST) for rsIDs the snapshot misses |
| `gnomad.py` | 519 | live gnomAD v4.1 — "the first *rate-limited* one" |
| `eutils.py` | 213 | NCBI E-utilities, batched and paced |
| `grch37.py` | 512 | the old assembly: rs-number recovery and the wrong-build diagnosis (RM48) |
| `cpic.py` | 714 | live CPIC PostgREST queries |
| `pharmvar.py` | 424 | live PharmVar (personal key) |
| `civic_api.py` | 400 | CIViC GraphQL — the surface the dated files cannot carry (RM160) |
| `clingen_allele.py` | 252 | the ClinGen Allele Registry, CAID → an identity this format can carry (RM153) |
| `pgs.py` | 436 | the PGS Catalog registry and per-score terms (RM163) |
| `litvar.py` | 982 | LitVar2/PubTator3 — which papers name this allele, and at which tier (RM167) |
| `atlas_client.py` | 496 | the AlphaGenome Atlas over gRPC (RM192) |
| `atlas_protos.py` | 233 | fetches the pinned `.proto` sources and generates the bindings (RM192/RM196) |
| `download.py` | 605 | HuggingFace snapshot provisioning — the bulk-fetch side |
| `upload.py` | 878 | HuggingFace upload — the publisher surface |
| `sequences.py` | 332 | reference-sequence access (`SequenceProxy`) and the ref-allele check it enables |

### 1.3 Resolution and identity

| module | lines | owns |
| --- | --- | --- |
| `resolver.py` | 778 | bidirectional rsid↔position over the Ensembl DuckDB (GRCh38) |
| `clinvar.py` | 285 | the ClinVar resolver link — the **core** half, duckdb only, no polars |
| `vrs.py` | 437 | VRS allele-id minting for the resolution table |
| `gene_spans.py` | 215 | gene symbol → GRCh38 span, from the MANE snapshot (RM194) |

### 1.4 Fill passes (they write a derived table)

| module | lines | command | writes |
| --- | --- | --- | --- |
| `frequencies.py` | 426 | `frequencies` | `frequencies.csv` |
| `gene_metrics.py` | 480 | `gene-metrics` | `gene_metrics.csv` |
| `clingen.py` | 302 | `dosage` | dosage rows into `gene_metrics.csv` |
| `gene_validity.py` | 661 | `gene-validity` | `gene_validity.csv` |
| `gwas.py` | 710 | `gwas` | `gwas_effects.csv` |
| `assertions.py` | 447 | `assertions` | `clinical_assertions.csv` |
| `literature.py` | 1665 | `literature` | `literature.csv` |
| `expression.py` | 500 | `alphagenome expression` | `expression_effects.csv` (RM194/RM200) |
| `concordance.py` | 657 | (inside `enrich`) | the concordance sidecar tables (RM130) |
| `currency.py` | 447 | (inside `enrich`) | the `dataset_currency` check (RM85) |

### 1.5 Check passes (they compare and never write an authored cell)

| module | lines | command |
| --- | --- | --- |
| `clinical.py` | 1089 | the `clin_sig` cross-check, inside `enrich` |
| `clin_sig.py` | 170 | the one shared clinical-significance normalizer (RM134 §A) |
| `civic_refutation.py` | 304 | `published_refutation`, inside `enrich` (RM170) |
| `civic_citations.py` | 785 | `civic citations` + the `evidence_status_currency` canary (RM160) |
| `civic_identities.py` | 482 | identities CIViC states in a variant's *name* only |
| `civic_vcf.py` | 375 | the dated accepted-and-submitted VCF (RM169) |
| `identifiers.py` | 1726 | `check-identifiers` — five checks |
| `acmg.py` | 734 | `check-acmg` |
| `pgx.py` | 600 | `pgx` — PharmVar/CPIC allele function |
| `clinpgx.py` | 382 | `clinpgx check` |
| `drug_labels.py` | 869 | `clinpgx check-labels` (RM166) |
| `strchive.py` | 736 | `check-repeat-bands` (RM165) |
| `alphagenome_check.py` | 599 | `alphagenome check` (RM193) |
| `mitomap.py` | 389 | MITOMAP's `pg_dump` and its two-token `status` grammar (RM171) |
| `pubmind.py` | 152 | the runtime PubMind snapshot reader |
| `lookup.py` | 1028 | `hint` — authoring lookups; writes nothing |

### 1.6 Snapshot builders (`[dev]`; one per cache lane)

`acmg_build.py` (300), `alphagenome_avi_build.py` (819), `civic_build.py` (1133),
`clinpgx_build.py` (342), `clinvar_build.py` (598), `constraint_build.py` (345), `cpic_build.py` (365),
`drug_labels_build.py` (298), `mane_build.py` (810), `mitomap_build.py` (429),
`mitomap_miss_build.py` (434 — the only **derived** lane), `pharmvar_build.py` (215),
`pubmind_build.py` (537), `strchive_build.py` (191).

`test_cache_lanes.py:74 test_every_builder_module_has_a_lane_and_every_lane_but_one_has_a_builder`
asserts the equality in both directions between the `*_build.py` modules on disk and the registry.

### 1.7 Drafting providers

`pgx_draft.py` (543, the first), `clinvar_draft.py` (865), `clinpgx_draft.py` (435),
`civic_draft.py` (620), `mitomap_draft.py` (438), `pubmind_draft.py` (668), `strchive_draft.py` (382).
Covered in §8.
## 2. The resolver chain — `enrich()` pass by pass

`enrich()` (`enrich.py:674-813`) takes the advisory lock and delegates to `_run_enrichment`
(`enrich.py:815-2046`). The module docstring (`enrich.py:1-8`) states the chain; the code below is
what actually runs.

### 2.0 Before the chain

| step | file:line | what it does |
| --- | --- | --- |
| genome build | `enrich.py:848` → `spec_genome_build` (`:465`) | read from the spec unless passed |
| load `variants.csv` | `:848-863` | `load_csv_rows(…, VariantRow)`; **`_restamp_for_build(variants, genome_build)`** at `:863` — the third load site, added because `VariantRow._freeze_identity` runs with no module in scope and always takes `derive_variant_key`'s GRCh38 default. Compiler warnings are dropped here on purpose (the compiler emits the same ones) |
| load existing `resolution.csv` | `:870-885` | through `sidecar_path(spec_dir, "resolution.csv")` so the pass writes back to whichever copy the module keeps (root or `derived/`). Keyed by `merge_key(row)` over `ResolutionRow._KEY_FIELDS`. **Existing rows are authoritative: merged, never clobbered** |
| `covered` | `:890` | `{} if rederive else existing` — under `--rederive` every subject re-enters the worklist and the recorded rows survive only as the baseline and as the carry-forward |
| journal | `:894-895` | `ResolutionJournal(resolution_path, …, enabled=write, rederive=rederive)`; `journal.resume()` reads answers staged by a killed run |
| non-GRCh38 banner | `:897-913` | every coordinate link below is gated on `genome_build == "GRCh38"`. The warning is explicitly scoped to *coordinate* resolution: "Authored coordinates are still transcribed verbatim, and build-free checks (rsID currency) still run." |
| `collect_subjects` | `:916` → `:182` | every table that can ask for a coordinate, not just `variants.csv` — a PGx module has none |
| progress | `:920` `SubjectProgress(len(subjects), progress)` | unit is **subjects**, `total` known before the first call; reports `(0, total)` immediately |

Work is then partitioned (`:926-946`): `need_pos` (rsID, no chrom), `need_rsid` (chrom, no rsID), and
`verify_pairs` (both authored — needs no resolution, but is a *claim* the tier can check, and is
deliberately **not** exempted by an existing `resolution.csv` row, `:938-942`).

### 2.1 The five links, in order

`--offline` sets `live_ensembl_runs = not offline and genome_build == "GRCh38"` (`:1085`) and
`gnomad_runs = use_gnomad and not offline and …` (`:1086`). Each later link fills only what the
earlier ones missed. The ordering is load-bearing: `alts` is in `RESOLUTION_FACT_FIELDS`, so whichever
link **first** knows a variant decides its alt list and therefore the compiled bytes
(`enrich.py:1134-1141`).

| # | link | gate | `--offline` | source stamp | absent | unreachable | staged |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Ensembl cache** `:966-1006` | `reference is not None and (need_pos or need_rsid or verify_pairs) and build==GRCh38` | **runs** (local). Provisioning at `:968-974` is skipped: `if reference is None and not offline and download` | `"cache"` | no locus in the snapshot | a *located but unqueryable* cache: re-raises **if `need_pos or need_rsid`**, else sets `snapshot_unusable=True` and warns (`:981-996`) | no |
| 2 | **ClinVar cache** `:1008-1076` | `use_clinvar and build==GRCh38 and (need_pos or need_rsid)`, and `clinvar_ref is not None` | **runs** (local); the `ensure_clinvar_snapshot` provisioning at `:1017-1022` is gated on `not offline and download` | `"clinvar"` | miss | an unqueryable snapshot **degrades to "this link had no answer"** and warns (`:1051-1058`) — never raises | no |
| — | **staged answers** `:1078-1104` | between the caches and the live links | a staged answer is honoured **only if the link that produced it would run this time** (`:1088-1098`) — so `--offline` / `--no-gnomad` on a resume drops them and logs `dropped_link` | its own | — | — | read here |
| 3 | **live Ensembl (V2→V1)** `:1106-1132` | `live_ensembl_runs` | **skipped entirely** | `src or "ensembl"` | `loci == []` → a `not_found` row | `loci is None` → `unreachable_rsids.add(rsid)` — "could not ask", distinct from an empty answer (S20) | **yes**, `journal.record(...)` before the next request; only a positive answer is staged (`:1125-1130`) |
| 4 | **live gnomAD (LAST)** `:1134-1157` | `gnomad_runs` | **skipped entirely** | `"gnomad"` | miss | `GnomadError` → warn and continue; "a last-resort link must not sink the whole enrichment" (`:1152`) | yes |

`enrich()` also takes `download: bool = True` (`enrich.py:685`), which gates the two provisioning
calls (`enrich.py:968`, `:1017`). **It has no CLI flag** — from the command line `--offline` is the
only switch that stops provisioning. `draft-panel` does expose `--download/--no-download`, with its
help explaining the distinction ("it says 'do not go and get one', not 'make no request'"); `enrich`
does not.

Last place for gnomAD is deliberate (`:1135-1141`): gnomAD reports only the alleles *observed in
gnomAD*, so promoting it would narrow an already-compiled module's `alts` and move its
`artifact.digest`. Going last makes it strictly additive.

### 2.2 Absent vs unreachable vs nobody-asked vs allele-mismatch

`EnrichmentResult` (`enrich.py:536-661`) keeps **four** distinct states for "no position", each with its
own field and a comment saying why it is not folded into its neighbour:

- `unresolved` (`:539`) — a key has no position; silent about why.
- `unreachable_rsids` (`:620-626`) — the request was **made and failed**. Empty offline, since nothing
  was asked.
- `unconsulted_rsids` (`:627-634`) — **nobody looked**. Computed at `:1168` as
  `rsid_links_consulted = reference is not None or clinvar_ref is not None or not offline` — a *run*-level
  question, because the branch it guards is only reached for a subject no link produced a locus for.
  Before RM98 these keys silently acquired a `not_found` row naming a cache nobody opened.
- `allele_mismatches` (`:635-642`) — the asking **succeeded** and the answer did not match the authored
  genotype. The only one of the four whose row is still written: "the row is honestly unresolved, so it
  stays; what was wrong was the reason it gave."

All three of the extra states warn in **both** modes and are escalated by neither
(`:1858-1905`), on the stated rule that nothing an author can edit clears a failed request.

Allele-aware forward selection is at `:1180-1210`: `hosting_verdict(v.constraint, ref, alts)` is
three-valued — `False` drops the locus, `None` keeps it and names it, and a subject whose `constraint`
is `None` (a pharm annotation naming no genotype) keeps **every** locus.

### 2.3 PAR handling

`select_par_representative` (`enrich.py:340-390`) keeps only the X spelling of a pseudoautosomal locus
by default; `--keep-par-twin` keeps both. Dropped twins land in `par_twins_dropped`
(`EnrichmentResult:613-618`) and are reported once for the run, not per row. The switch lives on the
enricher and could not live on the compiler: `resolution.csv` travels with the module, so the choice is
*recorded* and `compile → reverse → compile` stays a fixed point either way (`enrich.py:743-751`).

### 2.4 The validation passes inside `enrich`, and what `--offline` does to each

These run **after** the table is assembled. `SequenceProxy(offline=offline)` (`:1438`) is the shared
sequence reader.

| pass | file:line | flag | `--offline` |
| --- | --- | --- | --- |
| **VRS minting** | `:1440-1454` `mint_resolution_rows(out, VrsMinter(offline=…))` | `--vrs/--no-vrs` | substitutions still mint (stdlib); **indels do not** — they need the reference sequence. Coverage shortfall is a WARNING and never a refusal (`:1451-1454`) |
| **ref verification** | `:1457-1464` `verify_reference_alleles(...)` | `--verify-ref` | **skipped**; `RefCheck([],0,"not_requested")` when the flag is off |
| **wrong-build diagnosis** | `:1466-1493` `diagnose_wrong_build(ref_mismatches, …)` | no flag of its own — `verify_ref` gates the family | `not_checked == "skipped_offline"`, logged at INFO. Asked of the **mismatched rows only**, and bounded by `grch37.DEFAULT_DIAGNOSIS_LIMIT` (`build.sampled` warns) |
| **clin_sig cross-check** | `:1505-1544` | `--verify-clinsig` | **offline-capable** (the snapshot is local) |
| **CIViC refutation** | `:1552-1568` `compare_refutations` | none | **not gated by `--offline`** — it reads an operator-built snapshot and fetches nothing (`:1546-1550`) |
| **CIViC evidence-status canary** | `:1569-1582` `check_evidence_status_currency(..., offline=offline)` | none | a **real skip** — it is a live read |
| **concordance record** | `:1596-1607` `clin_sig_concordance(...)` | `--verify-clinsig` | built from the comparison that already ran; PubMind is the second authority and has **no `ensure_*`** beside it deliberately (`:1024-1032`) — a missing snapshot reads `unchecked`, not a download |
| **answered-call shift** | `:1637-1656` `answered_call_shift(...)` | `--verify-clinsig` | reads the previous run's `clin_sig_authority_calls.csv` **before the commit rewrites it** (`:1630-1636`) |
| **rsID currency** | `:1658-1701` `check_rsids(...)` | `--verify-rsids` | **skipped**, logged at INFO: "dbSNP has no offline merge table" |
| **rsid↔coordinate pair check** | `:1703-1762` `_check_authored_pairs(...)` | none | passes `offline=offline` and `unusable=snapshot_unusable`; reads `overlay_answers(spec_dir, "resolution.csv")` read-only |
| **authority fill** | `:1764-1770` | none | derived from the row's own `source`, filled only where empty; a link with no mapping keeps `None` |
| **re-derivation drift** | `:1780-1799` `_rederived_drift(...)` | `--rederive` | `None` when nobody re-derived; an **empty list** means every recorded subject was re-asked and still answers the same. Nothing is printed when nothing moved |
| **dataset currency** | `:1801-1827` `check_dataset_currency(..., offline=offline)` | `--verify-datasets` | `unchecked`, **never "up to date"**; unchecked legs are INFO not WARNING |

### 2.5 The strict gates, in the order they fire

All five raise `EnrichmentError` **before** the commit block (`enrich.py:1980`), which is what makes
"a refused strict run commits nothing" a promise rather than an accident of statement order.

1. `mode == "strict" and ref_mismatches` (`:1908-1929`) — deliberately first, because a wrong `ref` can
   mint a well-formed id for the wrong allele. The build diagnosis travels **inside** the refusal, not
   beside it, so the mode whose whole output is this sentence can see it.
2. `withdrawn = [s for s in stale_rsids if s.is_fatal]` (`:1929-1940`) — **fatal in both modes**. Never
   produced by the automated check; fires on a curator-recorded retraction.
3. `mode == "strict" and stale_rsids` (`:1940-1952`).
4. `mode == "strict" and unresolved` (`:1952-1957`).
5. `mode == "strict" and dataset_currency.behind` (`:1959-1979`) — over `behind` **alone**, never over
   the unchecked legs, or `--offline --strict` would be impossible forever over something no author can
   edit.

### 2.6 The commit

`if write:` (`enrich.py:1984-2045`), in order: `_write_resolution_csv(out, resolution_path)` →
`write_concordance_tables(...)` **only if** `clin_sig_record is not None` (a run where nobody could be
consulted writes nothing, so a previous record survives) → `record_verification(...)` (one attestation
for the whole run, RM45) → `record_source_terms({authorities}, "resolution", spec_dir)` → `journal.discard()`
unless `--keep-staging`.

`_write_resolution_csv` (`:2497`) writes through `atomic_writer`; `_FIELDNAMES` (`enrich.py:136`) is
`list(ResolutionRow.model_fields)` — derived from the model, never restated, with the comment naming
the failure mode it prevents (`DictWriter` raises nothing for a model field the dict omits).

`spec_lock(spec_dir, enabled=write, error=EnrichmentError)` (`:810`) is an advisory `flock` over the
whole read-modify-write window. A second run **refuses rather than waiting**; a filesystem that will
not take the lock degrades with a warning. `write=False` takes no lock and stages nothing.
## 3. The check table

### 3.1 The roster is derivable, and it is derived

A check is a member of `VALID_VERIFICATION_CHECKS` (`schema/src/just_dna_format/vocab.py:773-863`),
**26 members**, measured by `len()`. Skip reasons are `VALID_VERIFICATION_SKIPS`
(`vocab.py:879-…`), **8 members**: `no_reference not_permitted not_requested nothing_to_check offline
tautology unreachable unsupported`.

The roster is not hand-kept against the code. `test_verification_record.py:851
test_every_check_member_has_an_emitter_or_says_it_is_reserved` walks every `.py` under the package
with `ast`, collects the first argument of every `ran(...)`/`skipped(...)` call (resolving
module-level `CHECK = "..."` string constants), and asserts

```python
assert emitted == VALID_VERIFICATION_CHECKS - reserved
```

with `reserved = {"gene_disease_validity", "dosage_sensitivity"}` and the `generated/` tree excluded
by name. Its docstring says why it is an equality: *"An EQUALITY, not a floor: a floor cannot see a
member that lost its only emitter in a refactor, which is the direction the last three defects all
ran."*

I re-derived the emitter map independently (`grep -rln '"<check>"' enricher/src/just_dna_enricher/`)
and it agrees: 24 members have an emitter, `gene_disease_validity` and `dosage_sensitivity` have none
and say RESERVED beside themselves (`vocab.py:853-863`).

### 3.2 Every check

`ran`/`skipped` are `verification.py`'s constructors; `record_verification` (`verification.py:97`) is
the single load-merge-write, called from **11 sites** across 9 modules (`clinpgx.py:381`,
`drug_labels.py:868`, `alphagenome_check.py:566`, `enrich.py:1997`, `cli.py:1269`, `:1322`, `:1407`,
`:3191`, `:3869`, `literature.py:1197`, `pgx.py:599`, `strchive.py:735`).

| check | command | what it reports | severity | does `strict` change it? | emitter |
| --- | --- | --- | --- | --- | --- |
| `reference_allele` | `enrich` | authored/resolved `ref` vs the actual reference sequence | WARNING | **yes — refuses**, and it is the *first* gate (`enrich.py:1908`) | `enrich.py` |
| `genome_build_agreement` | `enrich` | whether a mismatched row's coordinate reads as GRCh37 | WARNING | no gate of its own; the diagnosis travels **inside** the `reference_allele` refusal (`enrich.py:1914-1919`) | `enrich.py` |
| `clinical_significance` | `enrich` | authored `clin_sig` vs ClinVar's, allele-exactly | WARNING | **no — deliberately never escalates** (`enrich.py:1494-1496`) | `enrich.py` |
| `published_refutation` | `enrich` | authored `direction` vs the refutations CIViC publishes | WARNING | **no** (`enrich.py:1585-1590`) | `enrich.py` |
| `evidence_status_currency` | `enrich` | a recorded `StudyRow.confidence` vs what the source says now | WARNING | **no** (`enrich.py:1578-1583`) | `enrich.py` |
| `rsid_currency` | `enrich` | authored rsID vs dbSNP (live/merged/absent) | WARNING; **`withdrawn` is fatal in BOTH modes** (`enrich.py:1929-1940`) | **yes** for merged/absent (`:1940`) | `enrich.py` |
| `rsid_coordinate_agreement` | `enrich` | an authored rsID+coordinate PAIR vs the reference | WARNING | **no — there is no severity gate reading it at all**, stated as deliberate (`enrich.py:1710-1718`) | `enrich.py` |
| `dataset_currency` | `enrich` | a recorded `SourceRow.dataset` vs the release the source publishes now | WARNING | **yes**, over `behind` **only**, never the unchecked legs (`enrich.py:1959-1979`) | `enrich.py` |
| `vrs_allele_id` | `vrs mint` | a recorded `ga4gh:VA.…` vs the re-minted one | WARNING (`cli.py:3188-3189`) | no `--strict` flag on the command at all | `cli.py:3191` |
| `citation_existence` | `literature` | authored `pmid`/`doi` vs PubMed and Crossref | WARNING | **yes** (`literature.py:962`, `:970`) | `literature.py` |
| `citation_identifier` | `literature` | authored `doi`/PMCID vs the registry's own for that PMID | WARNING | **yes** (`literature.py:975`, `:981`) | `literature.py` |
| `provenance_quote` | `literature` | `provenance_quote`/`provenance_regex` vs the text; `quotes_authored`/`quotes_found`/`quote_source` per row (`literature.py:919-921`) | WARNING | **no** — measured: the four `mode == "strict"` raises in `enrich_literature` (`literature.py:962`, `:969`, `:975`, `:981`) are over `missing`, `doi_missing`, `doi_conflicts` and `pmcid_conflicts`; there is no quote gate in either mode | `literature.py` |
| `allele_function` | `pgx` | authored `function_status` vs PharmVar and CPIC | WARNING | **yes** — `PgxEnrichmentError` | `pgx.py` |
| `pgx_evidence_level` | `clinpgx check` | authored `evidence_level` vs ClinPGx's own | WARNING | **yes** (`clinpgx.py:333`) | `clinpgx.py` |
| `regulator_label_agreement` | `clinpgx check-labels` | gene/allele/drug claims vs five regulators' label annotations | WARNING | **no — never escalates** (`drug_labels.py:32-35`); `strict` still refuses a *structural* failure (`:605`, `:663`) | `drug_labels.py` |
| `repeat_band_agreement` | `check-repeat-bands` | authored `repeat_alleles.csv` bands vs STRchive's | WARNING | **no — "A band difference NEVER fails, in either mode"** (its own `--help`); structural failures refuse in both (`strchive.py:568`, `:585`) | `strchive.py` |
| `acmg_secondary_findings` | `check-acmg` | authored `acmg_sf` vs the published SF gene list | WARNING; a mismatch against a **superseded** list is `unverifiable` and no longer refuses (`acmg.py:50-53`, `:221-224`) | **yes** on `report.mismatches` (`acmg.py:648`) | `acmg.py` |
| `gene_symbol_currency` | `check-identifiers` | authored `gene` vs HGNC approved/previous | WARNING | **yes** — `cli.py:1306` is `elif strict: raise typer.Exit(code=1)` on the `not report.clean` arm, and `clean` (`identifiers.py:459-474`) is `not (stale_rsids or stale_traits or stale_genes or gene_loci or stale_pgs)` | `identifiers.py` |
| `trait_currency` | `check-identifiers` | authored `trait_efo_id` vs OLS4 | WARNING | **yes** — in `clean` | `identifiers.py` |
| `gene_locus_agreement` | `check-identifiers` | the row's `gene` vs the chromosome its variant sits on | WARNING | **yes** — in `clean`. `gene_loci_not_checked` is reported separately and never silently (`cli.py:1258-1263`) | `identifiers.py` |
| `pgs_accession_currency` | `check-identifiers` | authored `pgs_id` vs the PGS Catalog's record | WARNING | **yes** — in `clean` via `stale_pgs` (`identifiers.py:453-456`) | `identifiers.py` |
| `pgs_metadata_agreement` | `check-identifiers` | `training_ancestry`/`training_cohort` vs `ancestry_distribution`/`samples_training` | WARNING | **no — the exit code stays 0 even under `--strict`**. `pgs_metadata.drift` is deliberately outside `clean` (`identifiers.py:462-470`), and `metadata_disagrees` (`:476-481`) exists so the CLI can say *checked, and something differs* while withholding only the green line (`cli.py:1294-1303`) | `identifiers.py` |
| `literature_coverage` | `litvar coverage` | which papers a variant–literature index holds, **and at which tier** (allele-resolved / position-only / absent) | report only | no `--strict` flag | `litvar.py` |
| `variant_impact_agreement` | `alphagenome check` | a module's variants vs AlphaGenome's AVI scores | WARNING | **no, and it changes nothing at all**: `mode` is stored on `VariantImpactResult` (`alphagenome_check.py:422`) and read as a gate nowhere; all five `VariantImpactError` raises (`:187 :230 :267 :270 :493`) are unconditional on mode. Docstring: *"`mode` is carried for the report and is **not** a severity ladder here… what `strict` still refuses is structural, and that refuses in `best_effort` too"* (`:417-420`) | `alphagenome_check.py` |
| `gene_disease_validity` | — | **RESERVED, no emitter**: `enrich_gene_validity` *records* ClinGen/GenCC verdicts and compares nothing authored | — | — | none |
| `dosage_sensitivity` | — | **RESERVED, no emitter**: `enrich_dosage_sensitivity` records ClinGen haplo/triplo curation into `gene_metrics.csv`, and no model carries an authored dosage claim | — | — | none |

### 3.3 The fill passes that are not checks

Six commands write a derived table and emit **no** `VerificationRecord`, because their subject is a
recording rather than a comparison. They still have a `--strict`, and it means "refuse if the source
had nothing for a subject":

| command | `strict` refuses on | exact refusal text (`file:line`) |
| --- | --- | --- |
| `frequencies` | `result.missing` (**not** `result.uncovered`, `frequencies.py:361-364`) | `frequencies.py:366` — *"strict frequency enrichment: N resolved allele(s) have no gnomAD frequency: …. gnomAD genuinely lacks rare/private alleles, so this is often correct data rather than a fetch failure — add the rows by hand or use mode='best_effort'."* |
| `gene-metrics` | `result.missing` | `gene_metrics.py:414` — *"strict gene-metrics enrichment: N gene(s) have no gnomAD …"* |
| `dosage` | `missing` | `clingen.py:258` — *"strict dosage enrichment: N gene(s) are not in the ClinGen curation list: …. ClinGen curates a subset by design (1,520 genes at {released}), so this is usually correct rather than an error — use mode='best_effort'."* |
| `gene-validity` | `result.missing` | `gene_validity.py:551` — *"strict gene-validity enrichment: N gene(s) have no {source} assertion: …. Both submitters curate a subset by design, so this is usually correct rather than an error — use mode='best_effort'."* |
| `assertions` | `result.missing` | `assertions.py:379-384` — *"strict clinical-assertion enrichment: N resolved allele(s) have no ClinVar record: …. Most variants are not in ClinVar at all, so this is usually correct data rather than a read failure — use mode='best_effort'."* |
| `gwas` | `result.unusable` **or** `result.p_value_underflows` — deliberately **not** `result.missing` | `gwas.py:618` — *"strict GWAS enrichment: N association(s) were served without an id this pass can key on and M carried a p-value below float64's range, so the artifact does not hold everything the Catalog published. Both are the Catalog's shape rather than an authoring mistake -- use mode='best_effort' to record what is holdable and read the warnings."* |

`test_cli_surface.py:158 test_the_gwas_severity_ladder_is_wired_to_something` pins that `mode` is read
at all — it was accepted and never read while `--strict` was advertised as a ladder — and that it does
**not** escalate on `missing`.

### 3.4 Where "report, never repair" is enforced

**It is enforced per pass, in the code and in that pass's own test — there is no package-wide
structural guard.** What exists:

- Each check module states it in its own docstring: `sequences.py:13` (*"It reports; it never repairs.
  A mismatch is surfaced with both values and left in place"*), `clinical.py:14`, `acmg.py:404`,
  `strchive.py:581`, `drug_labels.py:659`, `alphagenome_check.py:5`, `clingen.py:26`,
  `identifiers.py:335`, `civic_refutation.py:14`.
- The two places where a verdict *is* written onto a row are both explicitly scoped: `enrich.py:1686-1689`
  stamps `row.rsid_status` / `row.rsid_current` onto the **provenance** columns of `resolution.csv` and
  never replaces the authored label ("doing so would migrate `variant_key` by network lookup",
  `enrich.py:1658-1661`), and `enrich.py:1762-1770` fills `row.authority` only where it is `None`.
- The `strict` refusals raise **before** the commit block (`enrich.py:1980-1983`), so a refused run
  writes nothing. `test_enrich_transaction.py` asserts that on the bytes.

I found no guard that walks the check modules asserting none of them writes to an authored CSV. See
§11 (undetermined).

### 3.5 The skip vocabulary in use

Every pass maps its own spelling of an absence onto one of the 8 `VALID_VERIFICATION_SKIPS` members.
In `enrich` the mapping is explicit and kept beside the prose reason rather than parsed back out of it
(`enrich.py:1521-1542`): `not_requested → not_requested`, `no_snapshot → no_reference`,
`unusable_snapshot → no_reference`, the ClinVar draft tautology → `tautology`. `vocab.py:864-878`
records why `not_requested` and `offline` must not be merged ("one is a caller's choice, the other a
capability the run did not have") and why `not_permitted` is its own member (cleared by a
*declaration*, not by egress).

`alphagenome expression` is a seventh fill pass with no attestation. Its refusal is not a `strict`
gate but a **size cap**: `expression.py:482-489` raises `ExpressionError` when the row count exceeds
`max_rows` (`DEFAULT_MAX_ROWS = 50_000`, `expression.py:120`) — *"A CSV sidecar of that size is not a
sidecar, and truncating silently would be worse than refusing."* `literature` appears in both tables
(it emits three checks **and** writes `literature.csv`).
## 4. The complete CLI surface

**Method.** `uv sync --all-extras` in the worktree, then a recursive `--help` walk
(`scratchpad/walk.py`, output under `scratchpad/help/`): run `just-dna-enricher <path> --help`,
parse the `Commands` box, recurse into every name found. Nothing here is read off a Typer
decorator. Entry point is `just-dna-enricher = "just_dna_enricher.cli:app"`
(`enricher/pyproject.toml`, `[project.scripts]`).

**Counts, measured by the walk:**

| thing | count |
| --- | --- |
| top-level entries in the root `Commands` box | **36** |
| of those, sub-command groups (Typer sub-apps) | **17** |
| of those, leaf commands at top level | **19** |
| nested groups below a group (`gnomad constraint`) | **1** |
| **leaf (runnable) commands, whole tree** | **64** |
| total groups including root | 19 |

The 17 top-level groups: `clinpgx acmg clinvar cache cpic pharmvar civic pubmind gnomad vrs hint
litvar mane strchive mitomap atlas alphagenome`. `gnomad` holds one group (`constraint`) and no
leaf of its own.

Every group is `no_args_is_help=True` (e.g. `cli.py:4770-4779` for `atlas`), so a bare group name
prints help rather than acting.

### 4.1 The 19 top-level leaf commands

| command | required args | flags (excluding `--help`) |
| --- | --- | --- |
| `enrich` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--ensembl-cache`, `--clinvar-cache`, `--pubmind-cache`, `--clinvar/--no-clinvar`, `--gnomad/--no-gnomad`, `--vrs/--no-vrs`, `--verify-ref/--no-verify-ref`, `--verify-clinsig/--no-verify-clinsig`, `--verify-rsids/--no-verify-rsids`, `--verify-datasets/--no-verify-datasets`, `--keep-par-twin`, `--rederive`, `--keep-staging` |
| `enrich-and-compile` | `spec_dir`, `output_dir` | `--strict/--best-effort`, `--offline`, `--ensembl-cache`, `--clinvar-cache`, `--clinvar/--no-clinvar`, `--gnomad/--no-gnomad`, `--frequencies`, `--gene-metrics` |
| `frequencies` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--populations`, `--dataset` |
| `gene-metrics` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--constraint-cache` |
| `dosage` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--url`, `--use` |
| `gene-validity` | `spec_dir` | `--source` (`clingen`\|`gencc`, default `clingen`), `--strict/--best-effort`, `--offline`, `--url` |
| `gwas` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--use`, `--study-facts/--no-study-facts` |
| `assertions` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--clinvar-cache` |
| `literature` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--fulltext/--no-fulltext`, `--doi/--no-doi` |
| `pgx` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--use`, `--pharmvar/--no-pharmvar`, `--cpic/--no-cpic`, `--cpic-cache`, `--pharmvar-cache` |
| `draft` | `spec_dir` | `--gene` (**required**, repeatable), `--drug`, `--allele`, `--population`, `--use`, `--offline`, `--cpic-cache`, `--dry-run` |
| `draft-clinpgx` | `spec_dir` | `--snapshot` (**required**), `--drug`, `--gene`, `--min-evidence-level`, `--use`, `--dry-run` |
| `draft-panel` | `spec_dir` | `--gene`, `--source` (default `clinvar`), `--mitomap-miss-cache`, `--civic-cache`, `--snapshot`, `--pubmind-cache`, `--offline`, `--download/--no-download`, `--clin-sig`, `--min-review-stars` (0–4, default 2), `--max-citations` (≥0, default 3), `--min-confidence` (0–3, default 1), `--use`, `--dry-run` |
| `draft-repeats` | `spec_dir` | `--gene/-g`, `--catalogue`, `--use`, `--dry-run` |
| `check-identifiers` | `spec_dir` | `--strict/--best-effort`, `--traits/--no-traits`, `--genes/--no-genes`, `--pgs/--no-pgs` |
| `check-acmg` | `spec_dir` | `--strict/--best-effort`, `--offline`, `--url`, `--sf-list` |
| `check-repeat-bands` | `spec_dir` | `--catalogue`, `--strict/--best-effort` |
| `template` | `kind` | — |
| `upload` | `module_dir` | `--repo` (default `just-dna-seq/annotators`), `--name`, `--message/-m`, `--dry-run`, `--force` |

### 4.2 The 17 groups and their 45 leaves

| group | leaves | notes from the rendered help |
| --- | --- | --- |
| `cache` | `prepare`, `pull`, `rebuild`, `status`, `prune` | `prepare --only/--use/--pin/--source`; `pull --only/--use`; `rebuild --out/--only/--use/--pin/--source/--publish/--dry-run`; `status` takes nothing; `prune --only/--yes` |
| `clinvar` | `build`, `citations`, `publish` | `build --vcf/--download/--out`; `citations --out` (**required**) `/--citations/--download/--url`; `publish snapshot_dir --repo/-m/--dry-run` |
| `clinpgx` | `build`, `build-labels`, `check`, `check-labels`, `publish`, `publish-labels` | two parallel lanes: clinical annotations and drug labels |
| `cpic` | `build`, `publish` | `build --out/--endpoint/--use` |
| `pharmvar` | `build` | **no `publish`** — the help says "Operator-built and inject-only; never published" |
| `civic` | `build`, `citations`, `publish`, `reproduce` | `reproduce` builds the same release twice and diffs (`--release/--out/--keep/--offline/--submitted`) |
| `pubmind` | `build`, `publish` | `publish` takes **no options at all** and exists in order to refuse: *"Refuse to publish the PubMind snapshot, and say why. The command exists in order to refuse."* |
| `gnomad` | `constraint build`, `constraint publish` | the only two-level nesting |
| `mane` | `build` | `--download/--release/--summary/--changed/--not-in-mane/--versions/--out` |
| `strchive` | `build`, `publish` | |
| `mitomap` | `build`, `miss`, `publish` | `miss` is the derived lane: `--out/--mitomap-cache/--clinvar-cache` |
| `acmg` | `build` | takes a **required positional** `workbook` (.xlsx you downloaded); `--out/--source-url/--doi` |
| `atlas` | `generate` | `--refetch` |
| `alphagenome` | `build`, `check`, `expression`, `publish` | `build --input` (**required**) `/--out/--contig/--workers/--no-hash` |
| `vrs` | `mint` | `mint spec_dir --offline` |
| `hint` | `variant`, `citation`, `gene`, `trait`, `recover` | read-only; `--json` on `variant`/`citation`/`recover` |
| `litvar` | `coverage`, `gene` | reports only |

### 4.3 Structural guards on the surface

`enricher/tests/test_cli_surface.py` pins four things, all AST- or subprocess-measured rather than
asserted in prose:

- `test_the_module_form_exposes_every_command_the_console_script_does` (`test_cli_surface.py:34`)
  compares the top-level command set of the console script with `python -m just_dna_enricher.cli`.
  The docstring records the original defect: the `__main__` guard sat two-thirds down `cli.py`, so
  the module form "advertised 23 of the 26 commands".
- `test_the_main_guard_is_the_last_statement_in_the_cli` (`:57`) is the structural half — parses
  `cli.py`, asserts exactly one `if __name__ == "__main__"` block and that it is `tree.body[-1]`.
- `test_no_module_defines_the_same_function_twice` (`:79`) walks every module in the package for a
  module-level function defined twice (the `clinvar_build._sha256_file` shadowing).
- `test_every_pass_that_owns_a_client_closes_it_on_the_error_path` (`:114`) walks for any function
  that builds `client or SomeClient()` and closes it **outside** a `try/finally`.

Two more surface guards in the same file: `:254 test_every_drafting_command_declares_the_same_dry_run_flag`
(every drafting command must spell `--dry-run` identically), and
`:280 test_the_publish_default_does_not_depend_on_the_working_directory` with
`:309 test_the_publish_default_prefers_the_resolved_cache_over_the_build_directory`.
## 5. The cache lanes

`caches.py` is a registry, not a list. `CACHE_LANES: list[CacheLane]` (`caches.py:827-1088`) holds
**15 lanes**, measured by `len(CACHE_LANES)` in the installed environment, and
`LANES_BY_NAME` (`caches.py:1090`) is derived from it, never restated.

A `CacheLane` (`caches.py:237-322`) carries, per lane: `name`, `subdir`, `serves`, `build_command`,
`resolve`, `default_dir`, `env_var`, `rebuild` adapter, `ensure` (pull), `publish_repo`, `terms`,
`unpublished`, `unbuilt`, `release_label`, `publish_command`, `parents`.

### 5.1 The registry

| lane | build command | `rebuild` adapter | pull (`ensure`) | publish repo | terms gate | parents | env var | cache subdir |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ensembl` | — | **none** (`unbuilt`) | yes | — | — | — | `JUST_DNA_ENSEMBL_CACHE` | `ensembl_variations` |
| `clinvar` | `clinvar build` | yes | yes | `just-dna-seq/clinvar` | — | — | `JUST_DNA_CLINVAR_CACHE` | `clinvar` |
| `constraint` | `gnomad constraint build` | yes | yes | `just-dna-seq/gnomad_constraint` | — | — | `JUST_DNA_GNOMAD_CONSTRAINT_CACHE` | `gnomad_constraint` |
| `clinpgx` | `clinpgx build` | yes | yes | `just-dna-seq/clinpgx` | `CLINPGX_TERMS` | — | `JUST_DNA_CLINPGX_CACHE` | `clinpgx` |
| `cpic` | `cpic build` | yes | yes | `just-dna-seq/cpic` | `CPIC_TERMS` | — | `JUST_DNA_CPIC_CACHE` | `cpic` |
| `drug_labels` | `clinpgx build-labels` | yes | yes | `just-dna-seq/clinpgx_drug_labels` | `CLINPGX_TERMS` | — | `JUST_DNA_DRUG_LABELS_CACHE` | `drug_labels` |
| `pharmvar` | `pharmvar build` | yes | **no** | — | `PHARMVAR_TERMS` | — | `JUST_DNA_PHARMVAR_CACHE` | `pharmvar` |
| `pubmind` | `pubmind build` | yes | **no** | — | — | — | `JUST_DNA_PUBMIND_CACHE` | `pubmind` |
| `civic` | `civic build` | yes | yes | `just-dna-seq/civic` | — | — | `JUST_DNA_CIVIC_CACHE` | `civic` |
| `strchive` | `strchive build` | yes | yes | `just-dna-seq/strchive` | — | — | `JUST_DNA_STRCHIVE_CACHE` | `strchive` |
| `mitomap` | `mitomap build` | yes | yes | `just-dna-seq/mitomap` | — | — | `JUST_DNA_MITOMAP_CACHE` | `mitomap` |
| `mitomap_miss` | `mitomap miss` | yes | **no** | — | — | **`mitomap`, `clinvar`** | `JUST_DNA_MITOMAP_MISS_CACHE` | `mitomap_miss` |
| `mane` | `mane build` | yes | **no** | — | — | — | `JUST_DNA_MANE_CACHE` | `mane` |
| `acmg` | `acmg build` | yes | **no** | — | — | — | `JUST_DNA_ACMG_CACHE` | `acmg_sf` |
| `alphagenome_avi` | `alphagenome build` | **none** (`unbuilt`) — it still has a `build_command`; what it lacks is the unattended adapter | yes | `just-dna-seq/alphagenome_avi` | `ALPHAGENOME_AVI_TERMS` | — | `JUST_DNA_ALPHAGENOME_AVI_CACHE` | `alphagenome_avi` |

`mitomap_miss` is the only derived lane. `ensembl` and `alphagenome_avi` are the only two with no
`rebuild` adapter, for two stated and different reasons (`caches.py:841-844` / `caches.py:1075-1082`):
Ensembl's snapshot is cut by `just-dna-pipelines`; the AVI artifact is 88.5 GB behind a sign-in whose
eligibility clause bars classes of holder, so `alphagenome build --input <file you already hold>` is
the whole build and nothing downloads.

### 5.2 What an absent stage reports

Every absence is a **field**, not a comment, and the guard asserts the biconditional
(`test_cache_lanes.py:129 test_an_absent_stage_states_its_reason_and_a_present_one_does_not`).
The five reasons, verbatim from `caches.py`:

- `pharmvar` (`:922-926`) — *"refused: the bulk data is pulled under a key PharmVar's terms §2 make
  personal and non-transferable, and no axis SourceTerms records covers passing that on. Build your
  own with `pharmvar build --out <dir>`"*
- `pubmind` (`:939-942`) — *"refused: the ANNOVAR-distributed table states no data terms at all, and
  an unestablished permission is not a permission. Build your own with `pubmind build`"*
- `mitomap_miss` (`:1005-1010`) — *"derived, not downloaded: this snapshot is the join of the mitomap
  and clinvar caches and pins both their digests, so a pulled copy would carry a currency check its
  holder cannot run…"*
- `mane` (`:1027-1031`) — *"unestablished: NCBI states a policy rather than a licence…"*
- `acmg` (`:1045-1048`) — *"unestablished: the SF v3.3 list is ACMG/Elsevier supplementary material
  and nothing grants redistribution of it…"*

`test_a_lane_that_cannot_run_unattended_is_not_a_failure` (`test_cache_lanes.py:283`) pins that four
lanes land in the third state for four different reasons, none an error.

### 5.3 `cache status`

`lane_status()` (`caches.py:1255-1290`) is the read-only projection; nothing is downloaded or written.
It was extracted from the CLI loop after a consumer wrote the loop a second time (S91/RM204, docstring
at `:1256`). Its state is **three-valued** — `LANE_STATES = frozenset({"present","absent","occupied"})`
(`caches.py:1219-1220`):

- `present` — `lane.resolve()` found a payload; `release` is `lane.release_label(path)`.
- `absent` — the place the lane looks holds nothing.
- `occupied` — the place exists, is non-empty, and holds **no snapshot** (a build that died after its
  downloads, a stray `.part`, a foreign parquet). Distinguished because `absent` wants `cache pull`
  and `occupied` wants the directory moved aside or `cache prune`.

`looked_in` is the lane's `env_var` if set, else `default_dir()`. `release_unreadable` is the
present-but-`release.json`-does-not-parse case, reported as a provenance failure rather than a data
failure (`caches.py:1246-1252`, `:1287`).

`release_label` defaults to `_dataset_label` (`caches.py:227-234`), which reads `release.json`'s
`dataset` and returns `None` when the snapshot does not say — never a placeholder. `clinvar` is the
one lane that overrides it, with `clinvar_dataset_label` (`caches.py:847`), and
`test_the_lane_that_reads_its_release_differently_is_exactly_the_one_named`
(`test_cache_lanes.py:175`) enumerates that exception so it cannot grow quietly.

### 5.4 `cache prepare` / `cache pull`

`prepare_lane` (`caches.py:1304-1400`), `prepare_caches` (`:1404`). The route is a property of the
lane, never a flag:

1. `lane.resolve()` non-`None` → `PrepareOutcome(ready=True, route="present")`, nothing touched.
2. `lane.ensure is not None` → **pull**. If `lane.terms`, `check_declared_use` runs *first* (the terms
   are accepted when the bytes are taken): `LicenseRefusal` → `ready=False, route="pulled"`; a
   non-`None` reason → `ready=None, route="none", "skipped: …"`. The `ensure()` call is wrapped and
   `SnapshotNotPublished` is caught **by type** → `ready=None, "nothing published yet: …"`; any other
   exception → `ready=False`.
3. no `ensure`, no `rebuild` → `ready=None, route="none"`, carrying `lane.unbuilt`.
4. otherwise **build locally**, into `<default_dir>.incoming` and `staging.replace(target)` only on
   success. A non-empty target with no payload is refused before the build is spent
   (`caches.py:1357-1367`): *"…exists and holds no {lane} snapshot; prepare never deletes, so move it
   aside (or `cache prune --only {lane}` if it is a retired file) and re-run"*. A builder reporting
   success and writing nothing is caught explicitly (`:1386-1396`).

`PrepareOutcome.ready` is tri-state and `route` is one of `present | pulled | built | none`
(`caches.py:1279-1301`); `label` maps `{True: route, False: "FAILED", None: "unavailable"}`.
`prepare_caches` wraps each lane in `try/except Exception` so one lane's crash cannot sink the report
(`caches.py:1428-1443`).

`cache pull` is the pull-only half over the same registry (`cli.py:1848-…`).

### 5.5 `cache rebuild`

`rebuild_caches` (`caches.py:1446-1480`) writes every lane into `out/<lane>/`, **never in place**, so a
deployment can adopt a fresh set deliberately. `RebuildOutcome.built` is tri-state
(`caches.py:201-219`): `True` built, `False` failed, `None` could-not-run-unattended;
`label` = `{True:"built", False:"FAILED", None:"not run"}`.

A derived lane joins the parents **this run** cut: `parents_from_rebuild_dir` (`caches.py:1154-1172`)
maps each parent to `out/<parent>/` and judges presence by the parent lane's own resolver, not
`is_dir()` — an adapter `mkdir`s before downloading, so a cut fetch leaves an empty directory that
`is_dir()` accepted and the child was then reported FAILED for the parent's absence. `rebuild_lane`
(`caches.py:1174-1216`) refuses a child whose parents are missing with `built=None`:

> `derived from {parents}; not on disk: {how}. A miss set computed without a parent would be an
> increment measured against a comparison that never ran, not an empty one`

`_gate` (`caches.py:330-346`) separates a refusal from a skip: `commercial` against a no-sale source is
`built=False` (*"refused: …"*), `unstated` is `built=None` (*"skipped: …"*).

`--pin lane=release` and `--source lane=path` both name a lane and both go through the same registry
check (`test_an_unknown_cache_name_is_refused_by_every_flag_that_takes_one`, `test_cache_lanes.py:323`);
`--pin mane=` with no value is refused rather than read as the empty string (`:337`).
`lane_name()` (`caches.py:1093-1104`) accepts a hyphen for an underscore and **returns the declared
member** (`drug_labels`, `mitomap_miss`).

`_rebuild_clinvar` (`caches.py:348-394`) builds **both halves** — VCF and citations — because the
published artifact carries both, and a failure in the second is a failed lane; the docstring records
the incident it was written for (2026-09-03: 2026-08-29 records beside 2026-06-27 citations, because a
citations-free `release.json` was published over the one describing the pair).

### 5.6 `cache prune`

`cli.py:1987-2065` + `upload.plan_prune` / `upload.prune_repo` (`upload.py:718`, `:768`). It reports
what a published repo carries that the lane is **not made of**, and deletes only with `--yes`
(without it, it prints the plan and stops). Per lane:

- `publish_repo is None` → skipped, printing `lane.unpublished or "published elsewhere"`.
- no `SNAPSHOT_FILE_GLOBS[lane]` entry → `n/a — this snapshot has no data/ to be made of anything`.
  This is exactly `strchive` (one JSON at the repo root): `SNAPSHOT_FILE_GLOBS` (`download.py:116-126`)
  has **9 entries** — `ensembl clinvar constraint clinpgx cpic drug_labels civic mitomap
  alphagenome_avi` — against 10 lanes with an `ensure`. "prune found nothing" and "prune cannot look"
  are kept as different answers.
- a candidate is a file the lane's glob excludes **or** one a `LayoutShift` declares retired
  (`upload.py:179`, `LAYOUT_SHIFTS` at `:226`, `layout_shifts_to_apply` at `:240`). `README.md`,
  `.gitattributes`, `release.json`, `LICENSE.txt` and sidecar directories are never touched.

### 5.7 Publish-repo reachability

Cross-checked by set-diff: the nine lanes with a `publish_repo` are `clinvar`, `constraint`,
`clinpgx`, `cpic`, `drug_labels`, `civic`, `strchive`, `mitomap`, `alphagenome_avi`. Every one is
reachable — eight through `cache rebuild --publish` (they have a `rebuild` adapter) and, separately,
through their own `<group> publish` command with the matching default repo confirmed from `--help`;
`alphagenome_avi` has no adapter and therefore carries `publish_command="alphagenome publish"`
(`caches.py:1066-1073`), the field RM202 added after the repo was reachable by nothing.
`test_every_publishable_lane_can_actually_be_published` (`test_cache_lanes.py:249`) asserts the
biconditional. **No unreachable publish repo found.**
## 6. Every network client

All paths below are relative to `enricher/src/just_dna_enricher/` unless a test file is named, in
which case they are relative to `enricher/tests/`. Every line number was read with `grep -n` against
the tree in this worktree; nothing here is quoted from memory.

Two transports are in play. Sixteen classes own an `httpx` transport; one (`atlas_client.AtlasClient`)
speaks gRPC; one build-time helper (`atlas_protos`) uses `urllib`; the HuggingFace surface
(`download.py` / `upload.py`) goes through `huggingface_hub` rather than either.

### 6.1 The roster

| Client class | module:line | Talks to | Base URL / endpoint constant (verbatim) | Used for |
| --- | --- | --- | --- | --- |
| `GnomadClient` | `gnomad.py:276` | gnomAD GraphQL API | `DEFAULT_GNOMAD_ENDPOINT = "https://gnomad.broadinstitute.org/api"` (`gnomad.py:51`) | rsID→locus resolution link, allele frequencies, gene constraint |
| `EutilsClient` | `eutils.py:103` | NCBI E-utilities (`esummary`) | `DEFAULT_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"` (`eutils.py:41`) | dbSNP rsID status / merge checks, PubMed record summaries |
| `OntologyClient` | `identifiers.py:541` | OLS4 **and** HGNC (one class, two bases) | `DEFAULT_OLS4_BASE = "https://www.ebi.ac.uk/ols4/api"` (`identifiers.py:85`), `DEFAULT_HGNC_BASE = "https://rest.genenames.org"` (`identifiers.py:86`) | trait CURIE currency/obsolescence, gene-symbol approval |
| `CpicClient` | `cpic.py:268` | CPIC PostgREST API | `DEFAULT_CPIC_ENDPOINT = "https://api.cpicpgx.org/v1"` (`cpic.py:62`) | allele / diplotype / recommendation tables, `row_count` short-read guard |
| `PharmVarClient` | `pharmvar.py:210` | PharmVar REST (keyed) | `DEFAULT_PHARMVAR_ENDPOINT = "https://www.pharmvar.org/api-service"` (`pharmvar.py:52`) | star-allele definitions and defining variants |
| `EuropePmcClient` | `literature.py:292` | Europe PMC REST | `DEFAULT_EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"` (`literature.py:86`) | PMID→PMCID/DOI/licence/abstract lookup, JATS fulltext |
| `CrossrefClient` | `literature.py:395` | Crossref | `DEFAULT_CROSSREF_BASE = "https://api.crossref.org"` (`literature.py:87`) | DOI existence for records PubMed does not index |
| `PmcIdConverterClient` | `literature.py:491` | NCBI PMC ID converter | `DEFAULT_PMC_IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"` (`literature.py:91`) | PMCID → PMID, advisory only |
| `LitvarClient` | `litvar.py:268` | LitVar2 | `LITVAR_API_BASE = "https://www.ncbi.nlm.nih.gov/research/litvar2-api"` (`litvar.py:94`) | literature-coverage nodes and PMIDs per variant |
| `CivicApiClient` | `civic_api.py:198` | CIViC GraphQL | `CIVIC_API_URL = "https://civicdb.org/api/graphql"` (`civic_api.py:57`) | evidence items per CIViC variant (POST-only) |
| `PgsCatalogClient` | `pgs.py:338` | PGS Catalog REST | `PGS_REST_BASE = "https://www.pgscatalog.org/rest"` (`pgs.py:51`) | one score record; `/info` release probe |
| `GwasCatalogClient` | `gwas.py:151` | GWAS Catalog REST (EBI) | `DEFAULT_GWAS_ENDPOINT = "https://www.ebi.ac.uk/gwas/rest/api"` (`gwas.py:68`) | associations per rsID, plus `follow()` on HAL links |
| `ClingenAlleleClient` | `clingen_allele.py:201` | ClinGen Allele Registry | `CLINGEN_ALLELE_ENDPOINT = "https://reg.clinicalgenome.org/allele"` (`clingen_allele.py:44`) | CAID → placeable GRCh38 identity |
| `EnsemblResolver` | `ensembl.py:64` | Ensembl beta GraphQL **then** legacy REST | `DEFAULT_GRAPHQL_ENDPOINT = "https://beta.ensembl.org/api/graphql/variation"` (`ensembl.py:31`), `DEFAULT_REST_ENDPOINT = "https://rest.ensembl.org"` (`ensembl.py:32`) | rsID → GRCh38 loci, V2 with V1 fallback |
| `Grch37Client` | `grch37.py:87` | Ensembl GRCh37 REST | `GRCH37_REST_ENDPOINT = "https://grch37.rest.ensembl.org"` (`grch37.py:52`) | old-assembly overlap + reference bases for build diagnosis |
| `ClinVarReleaseClient` | `currency.py:99` | NCBI ClinVar FTP-over-HTTPS | `DEFAULT_CLINVAR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"` (`clinvar_build.py:45`) | streams the first `HEADER_PROBE_BYTES = 262_144` (`currency.py:82`) and reads `##fileDate=` |
| `AtlasClient` | `atlas_client.py:342` | AlphaGenome Atlas, **gRPC** | `DEFAULT_ADDRESS = "dns:///gdmscience.googleapis.com:443"` (`atlas_client.py:67`) | precomputed variant/interval impact scores, scorer roster |

Two more classes carry the `*Client` suffix and open **no socket** — they answer the same questions
from a built snapshot: `CpicSnapshotClient` (`cpic.py:537`) and `PharmVarSnapshotClient`
(`pharmvar.py:329`). `LookupClients` (`lookup.py:92`) is a bundle, not a client: it holds eight of the
above and lazily builds them through `ensure` under a lock (`lookup.py:128-139`), so a pacing gate and
a connection pool survive across a session.

### Fetchers that are functions rather than classes

These are real network calls that no client class owns and no roster walks (see §6.6):

| Function | module:line | URL constant | Translates to |
| --- | --- | --- | --- |
| `fetch_acmg_page` | `acmg.py:390` | `DEFAULT_ACMG_URL = "https://www.ncbi.nlm.nih.gov/clinvar/docs/acmg/"` (`acmg.py:85`) | `AcmgListUnavailable` with `skip="unreachable"` (`acmg.py:396-399`) |
| `fetch_curation_list` | `clingen.py:153` | `DEFAULT_CLINGEN_URL = "https://ftp.clinicalgenome.org/ClinGen_gene_curation_list_GRCh38.tsv"` (`clingen.py:50`) | `ClinGenUnavailable` (`clingen.py:159-160`) |
| `fetch_validity_export` | `gene_validity.py:375` | `DEFAULT_CLINGEN_VALIDITY_URL` (`gene_validity.py:63`) / `DEFAULT_GENCC_URL` (`gene_validity.py:66`) | `GeneValidityUnavailable` (`gene_validity.py:386-387`) |
| `discover_current_release` | `mane_build.py:592` | built from `MANE_FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human"` (`mane_build.py:90`) | `ManeUnavailable` (`mane_build.py:604-605`) |

All four translate `httpx.HTTPError` correctly; none of them retries and none of them paces.

### The bulk-download body

Every builder's `download_*` goes through one function, `net.stream_to_file` (`net.py:235`), which
returns a `StreamedFile(path, sha256, etag, last_modified)` (`net.py:215-233`). The URLs it is called
with are `DEFAULT_CLINVAR_URL` (`clinvar_build.py:45`), `DEFAULT_CITATIONS_URL` (`clinvar_build.py:49`),
`DEFAULT_CLINPGX_URL` (`clinpgx_build.py:96`), `DEFAULT_DRUG_LABELS_URL = "https://api.clinpgx.org/v1/download/file/data/drugLabels.zip"`
(`drug_labels.py:88`), `DEFAULT_MITOMAP_URL = "https://mitomap.org/downloads/mitomap.dump.sql.gz"`
(`mitomap_build.py:61`), `DEFAULT_PUBMIND_URL = "https://www.openbioinformatics.org/annovar/download/hg38_pubmind_db.txt.gz"`
(`pubmind_build.py:70`), `DEFAULT_STRCHIVE_URL` (`strchive_build.py:42`), `CIVIC_DOWNLOAD_BASE = "https://civicdb.org/downloads"`
(`civic_build.py:91`), `MANE_FTP_BASE` (`mane_build.py:90`) and the gnomAD constraint bucket
(`constraint_build.py:61`, `"https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/constraint/"`).

### 6.2 Rate limits — the shared machinery, and every constant

`net.py` is the whole shared layer: `PacingGate` (`net.py:36`), `batched` (`net.py:86`), `dedupe`
(`net.py:93`), `retry_attempts` (`net.py:118`), `attempt_floor` (`net.py:162`), `StreamedFile`
(`net.py:215`), `stream_to_file` (`net.py:235`). There is no class hierarchy in it beyond
`attempt_floor(stop_base)` (`net.py:162`) — `PacingGate` and `StreamedFile` are plain dataclasses.

**`PacingGate.wait`** (`net.py:74-83`) is the enforcement point. Its shape is load-bearing and pinned:

```python
def wait(self) -> None:
    with self._lock:
        now = self.clock()
        slot = now if self.last is None else max(now, self.last + self.interval)
        self.last = slot
        self.spent += 1
    remaining = slot - self.clock()
    if remaining > 0:
        self.sleeper(remaining)
```

The lock covers the slot reservation and the `spent` bump only, never the sleep (`net.py:75-83`;
docstring `net.py:51-54`). `clock` defaults to `time.monotonic` and `sleeper` to `time.sleep`
(`net.py:65-66`), which is what lets every test inject a zero-cost gate. `spent` (`net.py:69`) is a
monotonic count of admissions — one per `wait()` that returned, i.e. one upstream attempt — and is
never reset (`net.py:56-62`).

`test_net.py` pins it:

* `test_a_single_caller_waits_exactly_the_interval` (`test_net.py:32`) — `clock.slept == []` then `[6.0]`.
* `test_time_already_elapsed_is_credited` (`test_net.py:43`) — `pytest.approx(2.0)`.
* `test_a_gate_shared_across_threads_still_honours_the_budget` (`test_net.py:52`) — four threads through
  a `threading.Barrier`, then `gaps == [interval] * (workers - 1)` (`test_net.py:83`),
  `len(set(slots)) == workers` with `"no two callers may be cleared at the same instant"`
  (`test_net.py:84`), and `sorted(clock.slept) == [interval * n for n in range(1, workers)]`
  (`test_net.py:87`) — i.e. no thread waits out another's sleep.
* `test_the_first_caller_never_waits_however_many_are_racing` (`test_net.py:90`) — `len(clock.slept) == workers - 1`.
* `test_a_zero_interval_gate_never_sleeps` (`test_net.py:110`).
* `test_spent_counts_every_admission_including_the_ones_that_never_slept` (`test_net.py:119`) — asserts
  `(gate.spent, clock.slept) == (1, [])`, then `(2, [6.0])`, then `free.spent == 5` on a zero-interval
  gate, then `shared.spent == 20 == len(clock.slept) + 1` across 20 threads.
* `test_dedupe_keeps_first_occurrence_order` (`test_net.py:152`) — `dedupe(["b","a","b","c","a"]) == ["b","a","c"]`,
  because emitted order reaches `artifact.digest` (P7).

### Every pacing constant in the package

| Client | Interval constant | Value | Where the gate is built | Where `wait()` is called |
| --- | --- | --- | --- | --- |
| `GnomadClient` | `GnomadSettings.min_request_interval` (`gnomad.py:145`) | `6.0` s — "exactly gnomAD's stated 10-per-60s budget" (`gnomad.py:144`) | `gnomad.py:285` | `gnomad.py:326`, first statement of the retried `_request` |
| `EutilsClient` | `_UNKEYED_INTERVAL = 1.0 / 3.0` (`eutils.py:45`), `_KEYED_INTERVAL = 1.0 / 10.0` (`eutils.py:46`) | 3/s unkeyed, 10/s keyed; chosen at `eutils.py:90` from whether `NCBI_API_KEY` is present | `eutils.py:113` | inside retried `_request` (`eutils.py:157`) |
| `OntologyClient` | `min_request_interval` field (`identifiers.py:551`) | `0.2` s — "a courtesy rather than a budget" (`identifiers.py:544-546`) | `identifiers.py:558` | `identifiers.py:588` inside retried `_request` |
| `CpicClient` | — | **no gate at all** | — | — |
| `PharmVarClient` | `PHARMVAR_MIN_INTERVAL = 0.5` (`pharmvar.py:57`) | `0.5` s | `pharmvar.py:233` | `pharmvar.py:252`, first statement of retried `_request` |
| `EuropePmcClient` | `min_request_interval` field (`literature.py:297`) | `0.5` s | `literature.py:304` | `literature.py:330` |
| `CrossrefClient` | `min_request_interval` field (`literature.py:413`) | `0.1` s | `literature.py:426` | `literature.py:465` |
| `PmcIdConverterClient` | `min_request_interval` field (`literature.py:514`) | `0.5` s | `literature.py:527` | `literature.py:555` |
| `LitvarClient` | `_REQUEST_INTERVAL = 0.34` (`litvar.py:112`) | `0.34` s | `litvar.py:287` | `litvar.py:393` ("The gate is the first statement, so a retried attempt spends a slot of the budget instead of bursting past it") |
| `CivicApiClient` | `_REQUEST_INTERVAL = 0.34` (`civic_api.py:87`) | `0.34` s | `civic_api.py:221` | `civic_api.py:336` |
| `PgsCatalogClient` | `_REQUEST_INTERVAL = 0.2` (`pgs.py:63`) | `0.2` s | `pgs.py:359` | `pgs.py:411` |
| `GwasCatalogClient` | `DEFAULT_REQUEST_INTERVAL = 1.0` (`gwas.py:82`) | `1.0` s — "**Not a transcribed limit**… EBI publishes no budget to respect" (`gwas.py:80-82`) | `gwas.py:161` (`field(default_factory=…)`) | `gwas.py:187` |
| `ClingenAlleleClient` | `_REQUEST_INTERVAL = 0.1` (`clingen_allele.py:52`) | `0.1` s | `clingen_allele.py:211` | `clingen_allele.py:248` |
| `Grch37Client` | `_REQUEST_INTERVAL = 0.1` (`grch37.py:61`), surfaced as `Grch37Settings.interval` (`grch37.py:83`) | `0.1` s | `grch37.py:101` | `grch37.py:121` |
| `ClinVarReleaseClient` | `CLINVAR_MIN_INTERVAL = 0.5` (`currency.py:85`) | `0.5` s | `currency.py:124` | `currency.py:140` |
| `EnsemblResolver` | — | **no gate at all** | — | — |
| `AtlasClient` | — | **no gate**, filed deliberately: "no shared pacing gate (`@shared-pacing-gate`)" (`atlas_client.py:32-33`) | — | — |

Batch sizes also bound egress: `GnomadSettings.batch_size = 20` ("25 worked; 29 was rejected with
HTTP 400", `gnomad.py:142-143`), `EutilsSettings.batch_size = 200` (`eutils.py:69`),
`EuropePmcClient.batch_size = 25` (`literature.py:296`), `PmcIdConverterClient.batch_size = 200`
(`literature.py:513`).

### 6.3 Retry policy, per client

Every policy is a tenacity `@retry` whose `stop` is `attempt_floor(n)` (`net.py:162`), never
`stop_after_attempt(n)`. `attempt_floor.__call__` (`net.py:184-185`) resolves the ceiling **per call**
through `retry_attempts(default)` (`net.py:118`), which raises the client's own default to
`$JUST_DNA_HTTP_RETRY_ATTEMPTS` (`RETRY_ATTEMPTS_ENV`, `net.py:110`) when that is larger:
`return max(default, configured)` (`net.py:159`). It is a **floor**, never a flat setting — below the
default it is a no-op (`net.py:120-125`). A non-integer value logs
`"%s=%r is not an integer; using this client's own %d attempt(s)."` (`net.py:153`) and falls back.
`load_env()` is called once per process from inside `retry_attempts` (`net.py:142-145`) — the one
guarded inline import the house rules allow.

`attempt_floor` is documented as a drop-in for a **bare** `stop_after_attempt` only; a composed policy
(`stop_after_attempt(3) | stop_after_delay(60)`) is out of scope, and no policy in this tier is
composed today (`net.py:165-168`).

| Client | Decorated function | Attempts | Wait | Retried on | Not retried |
| --- | --- | --- | --- | --- | --- |
| `GnomadClient` | `_request` (`gnomad.py:304-311`) | `attempt_floor(4)` | `wait_exponential_jitter(initial=2.0, max=30.0)` | `(RateLimitedError, httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)` | `ValueError` from `.json()` |
| `EutilsClient` | `_request` (`eutils.py:131-143`) | `attempt_floor(4)` | `initial=1.0, max=20.0` | `(EutilsRateLimitedError, httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)` | `ValueError` |
| `OntologyClient` | `_request` (`identifiers.py:580-585`) | `attempt_floor(3)` | `initial=1.0, max=10.0` | `(httpx.TransportError, httpx.TimeoutException)` | every status — `_request` never calls `raise_for_status` |
| `CpicClient` | `_request` (`cpic.py:286-291`) | `attempt_floor(3)` | `initial=1, max=10` | `(httpx.TransportError, httpx.HTTPStatusError)` | `ValueError` |
| `PharmVarClient` | `_request` (`pharmvar.py:244-249`) | `attempt_floor(3)` | `initial=1, max=10` | `(httpx.TransportError, httpx.HTTPStatusError)` | the HTTP 401 branch — it raises `PharmVarError` **before** `raise_for_status` (`pharmvar.py:257-265`), which the predicate does not match |
| `EuropePmcClient` | `_get` (`literature.py:322-327`) | `attempt_floor(3)` | `initial=1.0, max=10.0` | `(httpx.TransportError, httpx.TimeoutException)` | status, `ValueError` |
| `CrossrefClient` | `exists` (`literature.py:451-456`) | `attempt_floor(3)` nominally | `initial=1.0, max=10.0` | `(httpx.TransportError, httpx.TimeoutException)` | **nothing — see §6.6, the decorator is inert** |
| `PmcIdConverterClient` | `_get` (`literature.py:547-552`) | `attempt_floor(3)` | `initial=1.0, max=10.0` | `(httpx.TransportError, httpx.TimeoutException)` | status, `ValueError` |
| `LitvarClient` | `_fetch` (`litvar.py:384-389`) | `attempt_floor(3)` | `initial=0.5, max=8` | `httpx.TransportError` only | status, shape |
| `CivicApiClient` | `_request` (`civic_api.py:327-332`) | `attempt_floor(3)` | `initial=0.5, max=8` | `httpx.TransportError` only | status, GraphQL `errors`, non-JSON |
| `PgsCatalogClient` | `_request` (`pgs.py:402-407`) | `attempt_floor(3)` | `initial=1.0, max=10.0` | `(httpx.TransportError, httpx.TimeoutException)` | every status — `_request` never calls `raise_for_status` (`pgs.py:408-412`) |
| `GwasCatalogClient` | `_get` (`gwas.py:174-179`) | `attempt_floor(3)` | `initial=0.5, max=8.0` | `(httpx.TransportError, httpx.TimeoutException)` | status, `ValueError` |
| `ClingenAlleleClient` | `_fetch` (`clingen_allele.py:241-246`) | `attempt_floor(3)` | `initial=0.5, max=8` | `httpx.TransportError` only | status, `ValueError` |
| `Grch37Client` | `_get` (`grch37.py:113-118`) | `attempt_floor(3)` | `initial=0.5, max=8.0` | `(httpx.TransportError, httpx.TimeoutException)` | status |
| `EnsemblResolver` | `_graphql_rsid` (`ensembl.py:124-129`) and `_rest_rsid` (`ensembl.py:146-151`) — two identical policies | `attempt_floor(3)` each | `initial=0.5, max=8.0` | `(httpx.TransportError, httpx.TimeoutException)` | status, `EnsemblError` |
| `ClinVarReleaseClient` | `_header_bytes` (`currency.py:131-136`) | `attempt_floor(3)` | `initial=1.0, max=15.0` | `(httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)` | nothing else can arise — `_gunzip_prefix` never raises (`currency.py:171-186`) |
| `AtlasClient` | — | **none** | — | — | filed, not forgotten: "no `tenacity` layer over the vendored `grpc_service_config.json` (`@retry-attempt-floor`)" (`atlas_client.py:31-33`). Retry policy is delegated to gRPC's own service config, loaded at `atlas_client.py:490`. |
| `net.stream_to_file` | `_attempt` (`net.py:278-283`) | `attempt_floor(3)` | `initial=2.0, max=30.0` | `httpx.TransportError` **only** | status, deliberately: "a 404 from a mistyped release tag is the same 404 four times over" (`net.py:256-258`) |

Every one of these carries `reraise=True`, which is what makes the *outer* translation load-bearing:
when the attempts run out the original exception, not a `RetryError`, leaves the decorated function.

Measured on the installed `httpx 0.28.1`: `issubclass(httpx.TimeoutException, httpx.TransportError)`
is `True`, so the eight `(httpx.TransportError, httpx.TimeoutException)` tuples are redundant — not
wrong, just wider than they read. `issubclass(httpx.HTTPStatusError, httpx.TransportError)` is
`False`, so listing `HTTPStatusError` really does add the status leg.

### 6.4 The exception contract

### The rule

`@client-exception-contract`, stated in `test_client_exception_contract.py:3-6`:

> `@client-exception-contract`: **retry, then translate, both legs.** A caller writes
> `except GnomadError` / `except CpicError` because that is what the client documents, and a client
> that lets `httpx` types out has no contract at all — the handler was written for exactly the case it
> cannot see.

The structural reason the translation must sit in an **outer** method is stated at
`test_client_exception_contract.py:274-279`:

> A transport error is deliberately re-raised bare inside the retried half so the decorator can
> match it — which is correct, and means the translation has to happen in the *outer* method or the
> exception escapes raw the moment the attempts run out. `reraise=True` on every one of these
> clients makes that certain rather than unlikely.

### The type hierarchies

Every family roots in `RuntimeError`; `*Unavailable` is always a **subclass**, never a sibling, so an
existing `except <Base>` keeps firing (P3). That subclassing is what makes a caller's `except` order
load-bearing — the narrow arm must go first.

| Base | Subclass(es) | Lines |
| --- | --- | --- |
| `GnomadError(RuntimeError)` | `RateLimitedError` | `gnomad.py:128`, `gnomad.py:132` |
| `EutilsError(RuntimeError)` | `EutilsRateLimitedError` | `eutils.py:53`, `eutils.py:57` |
| `IdentifierCheckError(RuntimeError)` | `IdentifierUnavailable` | `identifiers.py:108`, `identifiers.py:112` |
| `CpicError(RuntimeError)` | — (flat) | `cpic.py:66` |
| `PharmVarError(RuntimeError)` | — (flat) | `pharmvar.py:90` |
| `LiteratureEnrichmentError(RuntimeError)` | `LiteratureUnavailable` | `literature.py:112`, `literature.py:116` |
| `LitvarError(RuntimeError)` | `LitvarUnavailable` | `litvar.py:166`, `litvar.py:170` |
| `CivicApiError(RuntimeError)` | `CivicApiUnavailable` | `civic_api.py:116`, `civic_api.py:120` |
| `PgsCatalogError(RuntimeError)` | `PgsCatalogUnavailable` | `pgs.py:66`, `pgs.py:70` |
| `GwasError(RuntimeError)` | `GwasNotFound` | `gwas.py:85`, `gwas.py:94` |
| `ClingenAlleleError(RuntimeError)` | — (and nothing raises it from the client) | `clingen_allele.py:63` |
| `EnsemblError(RuntimeError)` | — | `ensembl.py:59` |
| `ReleaseProbeError(RuntimeError)` | `ReleaseUnavailable` | `currency.py:63`, `currency.py:67` |
| `AtlasError(RuntimeError)` | `AtlasUnavailable`, `AtlasRefused` → `AtlasRefMismatch`, `AtlasNotScored` | `atlas_client.py:151`, `:155`, `:159`, `:163`, `:172` |

`AtlasNotScored` is deliberately **not** an `AtlasRefused` (`atlas_client.py:172-179`): the request was
legal and the answer is "unknown". `AtlasRefMismatch` **is** an `AtlasRefused`
(`atlas_client.py:163-170`), which is what makes the Atlas ladder order-sensitive.

### What the contract roster asserts

`CLIENTS` (`test_client_exception_contract.py:160-190`) is `(label, builder, the error type this
client's callers are told to catch)`:

```
("gnomad", _gnomad, GnomadError),            ("eutils", _eutils, EutilsError),
("cpic", _cpic, CpicError),                  ("cpic.row_count", _cpic_row_count, CpicError),
("pharmvar", _pharmvar, PharmVarError),      ("identifiers", _ontology, IdentifierUnavailable),
("currency", _currency, ReleaseUnavailable), ("pgs", _pgs, PgsCatalogUnavailable),
("litvar", _litvar, LitvarUnavailable),      ("civic_api", _civic_api, CivicApiUnavailable),
```

Five of those name the **subclass** rather than the parent on purpose — "it is strictly the stronger
assertion, since passing it also proves an `except IdentifierCheckError` still fires"
(`test_client_exception_contract.py:166-167`). `cpic.row_count` is listed as its own client because
"it bypassed `_get` entirely, so it was the one method with no retry and no translation — and the one
the snapshot builder uses to refuse a short read" (`test_client_exception_contract.py:96-98`).

Four legs are driven, each parametrized over all ten rows:

1. **`test_a_server_error_surfaces_as_the_tiers_own_error`** (`:262`) — a persistent 503, asserting
   `not isinstance(caught.value, httpx.HTTPError)` with the message
   `f"{label} leaked an httpx exception through its own error type"` (`:267-269`).
2. **`test_an_exhausted_transport_failure_surfaces_as_the_tiers_own_error`** (`:273`) — `_refuse`
   raises `httpx.ConnectError("connection refused", request=request)` (`:66`).
3. **`test_a_client_error_is_not_swallowed_into_a_wrong_answer`** (`:298`) — a 404 must raise, except
   for `FOUR_OH_FOUR_IS_AN_ANSWER = {"identifiers"}` (`:294`), where it must return non-`None`.
4. **`test_a_200_that_is_not_json_surfaces_as_the_tiers_own_error`** (`:315`) — `_serve_html` returns
   `httpx.Response(200, text="<html><body>Scheduled maintenance</body></html>", headers={"content-type": "text/html"})`
   (`:71-75`). It asserts `raised.__module__.startswith("just_dna_enricher") and not isinstance(caught.value, (ValueError, httpx.HTTPError))`
   with `f"{label} leaked {raised.__name__} past its own error type"` (`:332-334`), then
   `issubclass(error, raised)` with `f"{label} raised {raised.__name__}, outside {error.__name__}'s family"`
   (`:338`). `READS_NO_JSON = {"cpic.row_count", "currency"}` (`:344`) instead asserts
   `builder(_serve_html)() is None` with `f"{label} must withhold on a body it cannot read"` (`:326`).

`WITHHOLDING_CLIENTS` (`:364-367`) is the counterpart table — the clients whose contract is a value,
not a type:

```
("grch37", _grch37, None),
("ensembl", _ensembl, (None, None)),
```

`test_a_withholding_client_withholds_on_every_failed_leg` (`:374`) crosses those two rows with all
three handlers (`ids=["5xx", "transport", "html"]`, `:373`) and asserts `builder(handler)() == withheld`.

### Where each client's translation actually happens

| Client | Retried inner | Translating outer | Legs covered |
| --- | --- | --- | --- |
| `GnomadClient` | `_request` (`gnomad.py:312`) | `_post` (`gnomad.py:333`) — `except (httpx.TransportError, httpx.HTTPStatusError, ValueError)` → `GnomadError` (`gnomad.py:350-351`) | transport, status, non-JSON |
| `EutilsClient` | `_request` (`eutils.py:144`) | `_get` (`eutils.py:165`) — two arms: `(httpx.TransportError, httpx.HTTPStatusError)` then `ValueError` (`eutils.py:181-184`) | all three |
| `OntologyClient` | `_request` (`identifiers.py:586`) | `_get` (`identifiers.py:591`) + `_json` (`identifiers.py:680`) | transport (`:607-608`), status via an explicit `raise_for_status` inside a `try` (`:611-614`), non-JSON (`:692-693`), non-dict shape (`:695`). **404 is returned, not raised** (`:609-610`) |
| `CpicClient` | `_request` (`cpic.py:292`) | `_get` (`cpic.py:308`) — `except (httpx.TransportError, httpx.HTTPStatusError, ValueError)` (`cpic.py:326-327`); plus a shape check raising `CpicError` when the payload is not a list (`cpic.py:328-329`). `row_count` has its own translation at `cpic.py:354-355` | all three + shape |
| `PharmVarClient` | `_request` (`pharmvar.py:250`) | `_get` (`pharmvar.py:270`) — `except (httpx.TransportError, httpx.HTTPStatusError, ValueError)` (`pharmvar.py:284-285`) | all three; 401 is diagnosed inside `_request` and never retried |
| `LitvarClient` | `_fetch` (`litvar.py:390`) | `_request` (`litvar.py:363`) — `except httpx.HTTPStatusError` first (`:373`), then `except httpx.HTTPError` (`:380-381`); decode through `_read_json` (`litvar.py:440`) | all three; a 400 whose body starts `_NOT_FOUND_DETAIL = "Variant not found"` (`litvar.py:117`) returns `(None, "")` (`litvar.py:375-376`) — the index answering |
| `CivicApiClient` | `_request` (`civic_api.py:333`) | `_post` (`civic_api.py:290`) — `except httpx.HTTPStatusError` (`:304-306`) then `except httpx.HTTPError` (`:308-309`), then `except ValueError` → `CivicApiError` (`:312-316`) | all three; a GraphQL `errors` block is `CivicApiError` (`civic_api.py:320-321`) |
| `PgsCatalogClient` | `_request` (`pgs.py:408`) | `_get` (`pgs.py:414`) — transport (`:424-425`), then `if response.status_code >= 400` (`:426-429`), then `ValueError` (`:432-433`), then a non-dict shape check (`:434-435`) | all three; **404 is an error here**, because this service says "no such score" with an empty body on a 200 |
| `ClinVarReleaseClient` | `_header_bytes` (`currency.py:137`) | `current_release` (`currency.py:152`) — `except (httpx.TransportError, httpx.HTTPStatusError)` → `ReleaseUnavailable` (`currency.py:160-161`) | transport, status; a non-gzip body is the documented `None` withhold via `_gunzip_prefix` (`currency.py:171-186`) |
| `Grch37Client` | `_get` (`grch37.py:119`) | callers `variants_at` (`:128`) / `reference_bases` (`:172`) — `except httpx.HTTPStatusError` first (`:145`, `:191`), then the tuple `(httpx.TransportError, httpx.TimeoutException, httpx.HTTPError)` (`:151`, `:197`), then `except ValueError` on `.json()` (`:156`) | all three, and every one returns a **value** |
| `EnsemblResolver` | `_graphql_rsid` / `_rest_rsid` | `resolve_rsid` (`ensembl.py:80`) — first `try`: `except httpx.HTTPStatusError` (`:105`) then `except (EnsemblError, httpx.TransportError, httpx.TimeoutException)` (`:108`); second `try`: `except httpx.HTTPStatusError` (`:113`) then `except (httpx.HTTPError, EnsemblError)` (`:119`). Non-JSON is typed in `_json` (`ensembl.py:162`, raising at `:173-174`) | all three, returning `(None, None)` |
| `ClingenAlleleClient` | `_fetch` (`clingen_allele.py:247`) | `resolve` (`clingen_allele.py:214`) — `except httpx.HTTPStatusError` first (`:225`), then `except (httpx.HTTPError, ValueError)` (`:233`) | all three, returning an `AlleleIdentity` whose `outcome` is `no_identity` (404) or `unchecked` |
| `GwasCatalogClient` | `_get` (`gwas.py:180`) — **retry and translation are the same function** | `except (httpx.TransportError, httpx.TimeoutException): raise` (`:192-193`), then `httpx.HTTPStatusError` → `GwasNotFound`/`GwasError` (`:194-197`), then `httpx.HTTPError` (`:198-199`), then `ValueError` (`:200-201`) | status and shape only — **see §6.6** |
| `EuropePmcClient` | `_get` (`literature.py:328`) | `fulltext` only (`literature.py:377`) — `except httpx.HTTPStatusError` (`:385-387`) then `except httpx.HTTPError` (`:388-390`), both returning `None`. `lookup` (`:335`) has **no handler** | — **see §6.6** |
| `CrossrefClient` | `exists` (`literature.py:457`) | itself — `except httpx.HTTPError` → `None` (`:468-470`), a 404 → `False` (`:471-472`), any other non-200 → `None` (`:473-475`), else `True` (`:476`) | — **see §6.6** |
| `PmcIdConverterClient` | `_get` (`literature.py:553`) | `resolve` (`literature.py:560`) — `except httpx.HTTPError: continue` (`:577-579`) | transport and status only — **see §6.6** |
| `AtlasClient` | — | `_translate` (`atlas_client.py:318`), called from all three RPCs (`:371`, `:436`, `:481`) and from `connect` for `grpc.FutureTimeoutError` (`:493-495`) | every `grpc.StatusCode` arm |

`_translate`'s arms (`atlas_client.py:325-339`): `UNIMPLEMENTED` → `AtlasNotScored`;
`INVALID_ARGUMENT` with `"reference base"` in the details → `AtlasRefMismatch`, otherwise
`AtlasRefused`; `UNAVAILABLE` / `DEADLINE_EXCEEDED` / `RESOURCE_EXHAUSTED` / `INTERNAL` →
`AtlasUnavailable`; everything else → `AtlasRefused`.

### The ordering guard

`test_shadowed_handlers.py` proves no `except` arm in the workspace is unreachable because an earlier
arm already catches it. Its premise (`test_shadowed_handlers.py:4-7`):

> once `FrequencyUnavailable` is a `FrequencyEnrichmentError`, a handler that lists the parent
> first swallows the child, and the narrower arm below it is dead code. Python takes the first matching
> clause, so the ordering that used to be arbitrary is now load-bearing.

Mechanics: it walks `_PACKAGES = [… / pkg for pkg in ("schema", "compiler", "enricher")]`
(`:32`) — **the package roots, not their `src/` subtrees**, so test files are walked too. `_class_bases`
(`:46`) collects `ast.ClassDef` → directly named `ast.Name` bases; `_ancestors` (`:56`) closes that
transitively over `_BUILTIN_BASES` (`:36-43`, which knows only `Exception`, `RuntimeError`,
`ValueError`, `TypeError`, `KeyError`, `OSError`); `_handler_names` (`:68`) returns `["<bare>"]` for a
bare `except:`, the `id` for an `ast.Name`, the `ast.Name` members of a tuple, and `[]` for anything
else; `_shadowed` (`:79`) reports
`f"{path.name}:{handler.lineno} except {name} is unreachable — {previous} at line {line} already catches it"`
(`:97-99`).

What it asserts:

* `test_no_handler_in_the_workspace_is_shadowed_by_an_earlier_arm` (`:108`) — `assert trees, "walked no sources at all — the package layout moved"`,
  then `assert not findings, "shadowed except arms:\n  " + …`. **It passes today: zero findings.**
* `test_the_walk_detects_the_shape_it_is_written_for` (`:115`) — the anti-`@tautology-zero` case.
  On S38's reported snippet it asserts `len(findings) == 1` and
  `"except FrequencyUnavailable is unreachable" in findings[0]` (`:134-135`); with the arms swapped,
  `not _shadowed(...)`.
* `test_a_parent_and_child_in_one_tuple_is_not_a_finding` (`:152`) — `except (FrequencyEnrichmentError, FrequencyUnavailable)`
  is redundant, not dead, "and a guard that reports it is one somebody deletes" (`:156-157`).
* `test_a_bare_except_shadows_what_follows_it` (`:171`) — `len(findings) == 1 and "<bare>" in findings[0]`.

**Its one documented limit** (`test_shadowed_handlers.py:19-22`): only `ast.Name` clause types are
resolved, so `except httpx.HTTPError` is compared against nothing. Every dotted ladder in this tier
therefore has to be checked by hand; I did, and all of them put the subclass first:

* `literature.EuropePmcClient.fulltext` — `HTTPStatusError` (`literature.py:385`) before `HTTPError` (`:388`). Correct.
* `litvar.LitvarClient._request` — `HTTPStatusError` (`litvar.py:373`) before `HTTPError` (`:380`). Correct.
* `civic_api.CivicApiClient._post` — `HTTPStatusError` (`civic_api.py:304`) before `HTTPError` (`:308`) before `ValueError` (`:312`). Correct.
* `clingen_allele.ClingenAlleleClient.resolve` — `HTTPStatusError` (`clingen_allele.py:225`) before `(HTTPError, ValueError)` (`:233`). Correct.
* `grch37.Grch37Client.variants_at` / `.reference_bases` — `HTTPStatusError` (`grch37.py:145`, `:191`) before
  `(TransportError, TimeoutException, HTTPError)` (`:151`, `:197`). Correct; the tuple is redundant
  (all three are `HTTPError`) but not shadowing.
* `ensembl.EnsemblResolver.resolve_rsid` — `HTTPStatusError` (`ensembl.py:105`, `:113`) before `(EnsemblError, TransportError, TimeoutException)` (`:108`) / `(HTTPError, EnsemblError)` (`:119`). Correct.
* `gwas.GwasCatalogClient._get` — `(TransportError, TimeoutException)` (`gwas.py:192`) before `HTTPStatusError`
  (`:194`) before `HTTPError` (`:198`) before `ValueError` (`:200`). Correct ordering, but see §6.6 for what the first arm does.
* `net.stream_to_file` — `httpx.HTTPError` (`net.py:299`) before `BaseException` (`net.py:303`). Correct.

`cli.py` has one ordering the tier documents as deliberate: `except ValueError` (`cli.py:1144`) sits
**before** `except IdentifierUnavailable` (`cli.py:1149`), which sits before `except IdentifierCheckError`
(`cli.py:1167`). The last pair is order-sensitive and commented as such:
"**After the `IdentifierUnavailable` arm, and the order is load-bearing**" (`cli.py:1168`). The
`ValueError`-first arm is not shadowing (the types are unrelated) but it is why
`identifiers._json` must translate a decode error rather than let it out: the comment at
`identifiers.py:685-688` records that a raw `json.JSONDecodeError` was filed as "a module whose rows
will not load" and skipped the `unreachable` attestation.

### The bulk-download contract

`test_bulk_download_contract.py` covers `net.stream_to_file`. Three AST walks and eight behavioural
tests, all offline (`httpx.stream` is monkeypatched with `_fake_stream`, `:136`).

The walks:

* `test_the_walk_finds_the_downloads_it_is_supposed_to_guard` (`:58`) — asserts these ten labels are
  reachable, named rather than counted: `"clinvar_build.py::download_clinvar_vcf"`,
  `"clinvar_build.py::download_var_citations"`, `"constraint_build.py::download_constraint_tsv"`,
  `"clinpgx_build.py::download_clinpgx_zip"`, `"drug_labels_build.py::download_drug_labels_zip"`,
  `"mane_build.py::download_mane_file"`, `"civic_build.py::download_civic_file"`,
  `"pubmind_build.py::download_pubmind_table"`, `"mitomap_build.py::download_mitomap_dump"`,
  `"strchive_build.py::download_catalogue"` (`:67-77`), each with
  `f"the walk no longer reaches {expected}"`.
* `test_no_download_opens_its_own_stream` (`:81`) — `assert offenders == []` with
  `f"these downloads open a raw httpx stream instead of calling net.stream_to_file: {offenders}"` (`:102`).
* `test_the_only_raw_stream_in_the_package_is_the_shared_one` (`:106`) — over the **whole package**,
  not only `download_*`-named functions: `assert streaming == {"net.py"}` with
  `f"httpx.stream is called outside net.py: {sorted(streaming)}"` (`:124`).

The behaviour:

* `test_a_truncated_body_is_retried_and_the_second_attempt_wins` (`:170`) — script
  `[httpx.RemoteProtocolError("peer closed"), b"payload"]`; asserts `stream.attempts["n"] == 2`,
  `result.path.read_bytes() == b"payload"`, `result.sha256 == hashlib.sha256(b"payload").hexdigest()`,
  and `not list(tmp_path.glob("*.part"))`. The digest match is what proves the retry restarts from zero.
* `test_the_failure_that_motivated_this_is_the_one_the_predicate_retries` (`:195`) —
  `assert issubclass(httpx.RemoteProtocolError, httpx.TransportError)` and
  `assert issubclass(httpx.TransportError, httpx.HTTPError)`.
* `test_a_status_error_is_not_retried` (`:205`) — `assert stream.attempts["n"] == 1, "a status error was retried"`.
* `test_a_persistent_transport_failure_is_translated_not_leaked` (`:227`) — raises `_Boom`, and
  `assert isinstance(caught.value.__cause__, httpx.HTTPError), "the cause is kept for a debugger"`,
  plus `"a thing" in str(caught.value)` and `"Pass a local copy instead." in str(caught.value)`.
* `test_a_failed_fetch_leaves_the_directory_as_it_found_it` (`:254`) — `dest.read_bytes() == b"the good copy"`
  and no `*.part`.
* `test_the_digest_is_returned_rather_than_only_logged` (`:274`) — `result.etag == '"abc"'`,
  `result.last_modified == "Wed, 03 Sep 2026 00:00:00 GMT"`, and
  `result.path == tmp_path / "f.bin", "the path is the destination, not the staging file"`.
* `test_the_retry_floor_is_the_tiers_own_knob` (`:297`) — `monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "5")`,
  then `assert stream.attempts["n"] == 5`.
* `test_a_flaky_download_is_a_failed_lane_rather_than_a_traceback` (`:319`) — runs through
  `rebuild_lane(LANES_BY_NAME["clinvar"], …)` and asserts
  `outcome.built is False, "a flaky download must be a failed lane, not an exception"` and
  `"ClinVar VCF" in outcome.detail`.
* `test_without_the_translation_it_really_did_escape_the_lane` (`:342`) — the anti-`@tautology-zero`
  half: `download_clinvar_vcf` is monkeypatched back to raising `httpx.RemoteProtocolError` and the
  test asserts `pytest.raises(httpx.RemoteProtocolError)` straight out of `rebuild_lane`.
* `test_a_write_failure_leaves_no_partial_behind_either` (`:364`) — `hashlib.sha256` replaced with a
  `_Full` stub raising `OSError(28, "No space left on device")`; asserts `pytest.raises(OSError)`
  (the caller's type, deliberately **not** translated) and that neither `dest` nor a `.part` survives.

The incident these pin, recorded at `net.py:196-199` and `test_bulk_download_contract.py:9-13`: on
2026-09-03 NCBI closed the connection **180,927,542 bytes into a 193,427,450-byte** ClinVar VCF.

I ran all four files offline: **71 passed in 3.96s**, no network.

### 6.5 Credential handling

Only three clients read a secret, and two more read a courtesy contact address. The mechanism is
always the same: `locations.load_env()` (`locations.py:281`), which walks up from CWD with
`find_dotenv(usecwd=True)` and calls `load_dotenv(env_path, override=override)` with
`override=False` by default (`locations.py:284-286`) — so a real exported variable always beats the
file.

| Variable | Read at | Which client / surface | Effect when absent |
| --- | --- | --- | --- |
| `NCBI_API_KEY` | `eutils.py:86` | `EutilsClient` (via `EutilsSettings.__post_init__`) | interval stays `_UNKEYED_INTERVAL` (1/3 s) instead of `_KEYED_INTERVAL` (1/10 s) — `eutils.py:90`; the key also rides in `identity_params()` (`eutils.py:97-98`) |
| `PHARMVAR_API_KEY` (`API_KEY_ENV`, `pharmvar.py:55`) | `pharmvar.py:230` | `PharmVarClient`, sent as the `Api-Key` header (`API_KEY_HEADER`, `pharmvar.py:54`; used `pharmvar.py:256`) | `configured` is `False` (`pharmvar.py:235-238`) and the pass **skips** rather than failing |
| `ALPHAGENOME_API_KEY` | `expression.py:297` | `atlas_client.connect(key)` → `AtlasClient._metadata = (("x-goog-api-key", api_key),)` (`atlas_client.py:347`) | `ExpressionError` naming the variable and `--offline` (`expression.py:299-302`) |
| `HF_TOKEN` | `upload.py:157` (after `load_env()` at `:156`) and `download.py:241-242` | the HuggingFace publisher / snapshot puller | `PermissionError` on publish (`upload.py:159-163`); on the read side a token is optional and "doubles the per-IP rate allowance" (`download.py:238-240`) |
| `JUST_DNA_CONTACT_EMAIL` | `eutils.py:88`, `literature.py:428`, `literature.py:529` | eutils `identity_params`, `CrossrefClient`'s `mailto:` User-Agent (`literature.py:433-434`), `PmcIdConverterClient`'s `email` param (`literature.py:573-574`) | omitted rather than invented |
| `JUST_DNA_HTTP_RETRY_ATTEMPTS` (`RETRY_ATTEMPTS_ENV`, `net.py:110`) | `net.py:146`, after a one-shot `load_env()` at `net.py:142-145` | every `attempt_floor` | each client keeps its own default |

### The `load_env` call-site rule

`@credential-where-read`: the `.env` load must happen **in the function that reads the variable**,
never as a side effect of some unrelated call. `test_cli_surface.py:176`,
`test_the_ncbi_credential_is_loaded_where_it_is_read`, is the guard. Its docstring states the incident
(`test_cli_surface.py:177-182`):

> `@credential-where-read`: a `.env`-only key must not depend on call order.
>
> `EutilsSettings` read `os.environ` directly, so the key reached it only as a side effect of some
> *unrelated* call resolving a cache path. The live effect was silent and threefold: the rate gate
> stayed at 1 request / 3 s instead of 10 / s. `PharmVarClient` carried the same `load_env()` call
> with a comment describing this exact failure.

It monkeypatches `eutils.load_env` and `literature.load_env` to append to a list
(`test_cli_surface.py:187-188`), then asserts:

* `eutils.EutilsSettings()` → `assert calls, "EutilsSettings did not load `.env` where it reads NCBI_API_KEY"` (`:190-191`);
* `literature.CrossrefClient()` then `literature.PmcIdConverterClient()` →
  `assert len(calls) == 2, "the two polite-identification clients must each load `.env`"` (`:194-196`).

Its companion `test_an_empty_key_still_means_no_key` (`test_cli_surface.py:199`) pins the other half
of `@test-no-credential`: with `monkeypatch.setenv("NCBI_API_KEY", "")`, both
`EutilsSettings().api_key is None` and `EutilsSettings().min_request_interval == pytest.approx(1 / 3)`
(`:207-209`). The reason is in the docstring (`:202-204`): "`load_dotenv` skips a variable that is
merely *present*, so `setenv(VAR, "")` is what a test means by 'no credential'".

`missing_credential_reason` (`locations.py:291`) is the surface that keeps absent and
exported-empty apart, and the message for the empty case says so verbatim: "`$…` is set but EMPTY, and
an empty exported variable outranks a `.env`… Run `unset …`" (`locations.py:312-317`).

The guard-must-load corollary: `caches._rebuild_pharmvar` calls `load_env()` **before** checking
`os.environ.get(pharmvar.API_KEY_ENV)` (`caches.py:480-481`), with the comment "A pre-check that
answers differently from the code it is guarding is worse than no pre-check" (`caches.py:478-479`).

---

### 6.6 Defect candidates (client surface)

Everything in this subsection was **measured**, offline, against the real code paths through
`httpx.MockTransport`. The probe scripts are throwaway; the shapes they drive are the three legs the
contract roster itself drives (`_serve(503)`, `_refuse`, `_serve_html`) plus an attempt counter.

### C1 — `GwasCatalogClient` leaks `httpx.ConnectError` on the exhausted transport leg

`gwas.py:174-179` puts the `@retry` **on `_get` itself**, and `_get`'s first handler is
(`gwas.py:192-193`):

```python
except (httpx.TransportError, httpx.TimeoutException):
    raise
```

That bare re-raise is the shape `test_client_exception_contract.py:274-279` says is only correct when
an *outer* method translates. There is no outer method here, and `reraise=True` (`gwas.py:178`) hands
the original exception back to the caller once the three attempts are spent.

Measured: `GwasCatalogClient.associations_for("rs1800562")` over a transport that raises
`httpx.ConnectError` makes **3 attempts** and then raises `httpx.ConnectError` — not `GwasError`. The
same failure reaches the pass: `enrich_gwas(spec, client=…, write=False)` over the same transport
raises `httpx.ConnectError`.

This directly contradicts `_get`'s own docstring (`gwas.py:181-185`):

> Both legs are translated (`@client-exception-contract`): a transport error that survives the
> retries and an HTTP status error are equally the caller's problem and equally not `httpx`'s
> vocabulary to express.

and `GwasError`'s (`gwas.py:87-90`): "Every transport and parse failure is translated into this before
it leaves the module."

Why nothing catches it:

* `gwas.GwasCatalogClient` is **exempt** from the client roster (`test_client_exception_contract.py:242`),
  on the grounds that "`GwasError` is both the client's and the pass's type, so there is no
  cross-module mismatch here for a caller to fall through" — which is a statement about the *named*
  type, not about the leaked one.
* `gwas.enrich_gwas` is **exempt** from the pass roster too (`test_pass_exception_contract.py:279`),
  with the same reasoning: "`GwasError` is both the client's type and the pass's, declared in one
  module — so there is no foreign type for a caller to fall through, and nothing to translate."
* The test that looks like it covers this, `test_gwas.py:333`
  `test_a_transport_failure_surfaces_as_this_passs_own_error`, drives a `_FakeClient(fail_on="associations")`
  whose `associations_for` **raises `GwasError("simulated outage")` directly** (`test_gwas.py:108-110`).
  It never reaches `GwasCatalogClient._get`, so it asserts the thing it assumes.
* `test_cli_surface.py:212` does drive a real `httpx.ConnectError` through the pass, but with
  `pytest.raises(Exception)` (`test_cli_surface.py:232`) — which an httpx leak satisfies.

Status leg and non-JSON leg are fine (`GwasError` on both, measured).

### C2 — `CrossrefClient.exists`'s `@retry` decorator is inert

`literature.py:451-456` decorates `exists`, and `exists`'s own body (`literature.py:468-470`) catches
`httpx.HTTPError` and returns `None`. `httpx.TransportError` is an `httpx.HTTPError`, so the exception
never propagates to tenacity: the decorator sees a clean return on the first attempt.

Measured: over a transport that always raises `httpx.ConnectError`, `exists("10.1/x")` returns `None`
after **1 request**. The declared floor is `attempt_floor(3)`.

This is not a contract leak — `None` is the documented withhold (`literature.py:459-462`) — but the
retry is dead code, and the one client in the tier whose `@retry` and whose `try` sit on the *same*
function is the one where they cancel out. `attempt_floor` is also the tier's knob: raising
`$JUST_DNA_HTTP_RETRY_ATTEMPTS` has no effect on this client
(`@off-switch-needs-a-probe`, read in the other direction).

### C3 — `EuropePmcClient.lookup` leaks all three legs

`lookup` (`literature.py:335`) calls `self._get(...)` (`literature.py:355`) with no handler at all and
then `.json()` on the result. Measured over the roster's own three handlers:

| Leg | What escapes |
| --- | --- |
| persistent 503 | `httpx.HTTPStatusError` |
| transport refused | `httpx.ConnectError` |
| 200 `text/html` | `json.decoder.JSONDecodeError` |

The third is the exact leak `test_client_exception_contract.py:315-324` was written for, and the one
`identifiers._json` (`identifiers.py:680-693`), `litvar._read_json` (`litvar.py:440`),
`civic_api._post` (`civic_api.py:312-316`), `ensembl._json` (`ensembl.py:162`) and `pgs._get`
(`pgs.py:432-433`) each close in their own module.

**Where it lands.** `enrich_literature` calls `epmc.lookup(wanted)` at `literature.py:845` inside a
`try:` (`literature.py:844`) whose only companion is `finally:` at `literature.py:944` — **no
`except`**. That is verbatim the shape `test_pass_exception_contract.py:5-7` was written for ("Five
call sites let the client's type straight through a `try/finally` with no `except`"), and the
`literature.enrich_literature` case in that file's `PASSES` (`test_pass_exception_contract.py:165-170`)
injects only `eutils=_StubEutils()`, which raises at `literature.py:833` before control ever reaches
line 845 — so the Europe PMC leg is never driven there. The hint path is luckier: `lookup.py:971`
catches a bare `Exception` around the same call and records `f"Europe PMC could not be asked: {exc}"`.
`literature.py:763`'s `except ValueError` is **not** a catcher for this — it wraps
`load_citing_rows(spec_dir)` (`literature.py:762`), eighty lines earlier.

`EuropePmcClient.fulltext` (`literature.py:377`) is genuinely fine — it withholds `None` on both httpx
legs, exactly as the exemption comment claims (`test_client_exception_contract.py:235-236`). The
exemption comment is true of `fulltext` and silent about `lookup`, which is the wider method.

Measured aside, not a leak but a wrong answer: `fulltext` on a 200 `text/html` maintenance page returns
the string `'maintenance'` — `extract_text` (`literature.py:594`) happily walks the HTML. Whether that
should be a withhold is a design question, not a defect I can settle from the code.

### C4 — `PmcIdConverterClient.resolve` leaks `JSONDecodeError` on a 200 that is not JSON

`resolve` (`literature.py:560`) wraps `self._get(params).json()` in `except httpx.HTTPError: continue`
(`literature.py:577-579`). Measured: 503 → `{}` (fine), transport refused → `{}` (fine), 200
`text/html` → `json.decoder.JSONDecodeError` escapes. Same shape as D3's third row; `ValueError` is
simply not in the handler.

### C5 — The status-retry predicate does not discriminate 4xx from 5xx, and the tier states both rules

This one is rule-against-rule, not code-against-rule, and the framing matters. `net.stream_to_file`
states one side (`net.py:256-258`):

> A **status** error is not retried: a 404 from a mistyped release tag is the same 404 four times
> over, and the caller wants it now rather than after three backoffs.

and `test_bulk_download_contract.py:205` pins it (`assert stream.attempts["n"] == 1, "a status error
was retried"`).

The **other** side is stated just as plainly, and an un-retried status error is filed there as the
RM97 *defect*. `test_client_exception_contract.py:10-12`:

> `gnomad._post` and `eutils._get` kept the unrepaired shape:
> `raise_for_status()` outside the `try`, `httpx.HTTPStatusError` in neither retry list, so a 5xx
> escaped raw **and unretried**.

`gnomad.py:337-339` and `eutils.py:170-172` say the same about their own repairs. So a retried 5xx is
deliberate. What neither rule addresses is a **4xx**, and five clients retry those too because the
predicate is the whole `httpx.HTTPStatusError` class rather than a status-code test. Measured request
counts against a transport that always answers the given status:

| Client | 404 attempts | 503 attempts | Predicate |
| --- | --- | --- | --- |
| `CpicClient._get` | **3** | 3 | `(httpx.TransportError, httpx.HTTPStatusError)` (`cpic.py:287`) |
| `PharmVarClient._get` | **3** | 3 | `(httpx.TransportError, httpx.HTTPStatusError)` (`pharmvar.py:245`) |
| `ClinVarReleaseClient.current_release` | **3** | 3 | `(httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)` (`currency.py:134`) |
| `GnomadClient._post` | **4** | 4 | `(RateLimitedError, httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)` (`gnomad.py:307-309`) |
| `EutilsClient._get` | **4** | 4 | `(EutilsRateLimitedError, httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)` (`eutils.py:134-141`) |

For comparison, the clients that get it right: `PgsCatalogClient` 1 attempt on both,
`OntologyClient` 1, `LitvarClient` 1, `CivicApiClient` 1.

gnomAD and eutils have the strongest case — a
429 is a status, and both name their **translated** rate-limit type in the predicate
(`RateLimitedError`, `gnomad.py:132`; `EutilsRateLimitedError`, `eutils.py:57`) and raise it *before*
`raise_for_status` (`gnomad.py:328-329`, `eutils.py:160-161`), so `httpx.HTTPStatusError` in the list
is redundant for the 429 case and covers 5xx as well as 4xx. cpic, pharmvar and currency have no such
story: they retry every 4xx three times. **undetermined from code: whether the blanket
`HTTPStatusError` in these five is a deliberate "retry 5xx" that over-reaches, or a copy that was
never narrowed.** Nothing in the tier says a status retry should be status-code-conditional, no
client anywhere tests `response.status_code` inside a retry predicate, and no test drives a 404
attempt count on any of them. The cost is bounded and real: a mistyped CPIC table name or a wrong
PharmVar gene costs three round trips and up to two backoffs to learn what the first response said.

### C6 — Clients present in the source but not covered by the roster walk

`test_client_exception_contract.py:193` discovers classes by walking `pkgutil.iter_modules` and keeping
any class in its own module whose source mentions `httpx` and whose name ends in `Client` **or** whose
source contains `"httpx.Client("` (`:214-228`). I re-ran that walk verbatim. It discovers **16**
classes:

```
civic_api.CivicApiClient          clingen_allele.ClingenAlleleClient   cpic.CpicClient
currency.ClinVarReleaseClient     ensembl.EnsemblResolver              eutils.EutilsClient
gnomad.GnomadClient               grch37.Grch37Client                  gwas.GwasCatalogClient
identifiers.OntologyClient        literature.CrossrefClient            literature.EuropePmcClient
literature.PmcIdConverterClient   litvar.LitvarClient                  pgs.PgsCatalogClient
pharmvar.PharmVarClient
```

`covered` is the nine module names in `CLIENTS` (gnomad, eutils, cpic, pharmvar, identifiers,
currency, pgs, litvar, civic_api). The set difference is exactly the seven-member `exempt` set
(`:232-256`), so `uncovered == exempt` and the guard passes — **no drift within the walk's own
criterion**:

```
clingen_allele.ClingenAlleleClient   ensembl.EnsemblResolver   grch37.Grch37Client
gwas.GwasCatalogClient               literature.CrossrefClient literature.EuropePmcClient
literature.PmcIdConverterClient
```

Of those seven, three are exempt for a reason the file then *also* pins elsewhere
(`grch37` and `ensembl` in `WITHHOLDING_CLIENTS`, `:364-367`), and four are exempt with no
equivalent pin: `literature`'s three and `gwas`. Those four are exactly where C1–C4 live. The
exemption text for the literature trio (`:233-236`) says they are "exercised by their own suite
against real recorded payloads. Extending the contract to them is worth doing and is wider than this
item" — an acknowledged gap, and the measurements above say what is behind it.

`clingen_allele.ClingenAlleleClient` is exempt on the grounds that "the three outcomes ARE the
contract" (`:250-255`) and is **not** in `WITHHOLDING_CLIENTS`, so its three-leg withhold is unpinned
in this file. It is pinned in its own suite, partially:
`test_clingen_allele.py:221` `test_a_transport_failure_is_unchecked_rather_than_an_absence`
(`httpx.ConnectError` → `outcome == "unchecked"`, `:229-231`) and `test_clingen_allele.py:234`
`test_a_404_is_the_registry_answering` (404 → `"no_identity"`, 503 → `"unchecked"`, `:236-237`).
There is no 200-that-is-not-JSON case for it; reading `resolve` (`clingen_allele.py:233`) the
`ValueError` arm is present, so the leg is closed in code, just not asserted.

Classes the walk cannot see by construction, each for a stated reason:

* `cpic.CpicSnapshotClient` (`cpic.py:537`) and `pharmvar.PharmVarSnapshotClient` (`pharmvar.py:329`) —
  no `httpx` in their source; they read a built snapshot. Named in the guard's docstring
  (`test_client_exception_contract.py:203-205`) as "absent by construction rather than by exemption".
* `atlas_client.AtlasClient` (`atlas_client.py:342`) — gRPC, so the httpx criterion misses it.
  **It is covered, elsewhere**: `test_atlas_client.py:317`
  `test_every_transport_error_becomes_this_modules_contract` parametrizes seven `grpc.StatusCode`
  arms (`:304-315`) and asserts `not isinstance(caught.value, grpc.RpcError)` (`:327`);
  `test_atlas_client.py:332` `test_not_scored_is_not_a_refusal` asserts
  `not issubclass(ac.AtlasNotScored, ac.AtlasRefused)`, `issubclass(ac.AtlasRefMismatch, ac.AtlasRefused)`
  and `issubclass(ac.AtlasNotScored, ac.AtlasError)` (`:338-340`); and `test_atlas_client.py:343`
  `test_handler_order_is_not_load_bearing_by_accident` walks the ladder
  `(ac.AtlasRefMismatch, ac.AtlasRefused, ac.AtlasNotScored, ac.AtlasUnavailable)` (`:350`).
  `test_pass_exception_contract.py:315-326` records that this file "has never held an Atlas case".
* `lookup.LookupClients` (`lookup.py:92`) — a bundle, no transport of its own.

**A second-order set difference the code has no guard for at all.** Four module-level fetchers make
real requests and belong to neither walk — the class roster needs a class, and the bulk-download walk
keys on a `download_*` name plus `httpx.stream`:

* `acmg.fetch_acmg_page` (`acmg.py:390`)
* `clingen.fetch_curation_list` (`clingen.py:153`)
* `gene_validity.fetch_validity_export` (`gene_validity.py:375`)
* `mane_build.discover_current_release` (`mane_build.py:592`)

All four translate `httpx.HTTPError` correctly, so there is no leak today — but nothing walks them, so
a fifth one added tomorrow is unguarded. `test_bulk_download_contract.py:106`
(`test_the_only_raw_stream_in_the_package_is_the_shared_one`) closes the equivalent hole for
`httpx.stream`, and there is no analogue for `httpx.get`.

### C7 — No wrong `except` ordering found

`test_shadowed_handlers.py` passes with zero findings over `schema/`, `compiler/` and `enricher/`
(package roots, tests included — `:32`). Its blind spot is dotted clause types (`:19-22`), so I
checked every dotted ladder in this tier by hand; the list and the verdicts are in §6.4, and all of
them put the subclass first. `cli.py:1144`'s `except ValueError` before `except IdentifierUnavailable`
(`cli.py:1149`) is not shadowing — the types are unrelated — but it is *consequence-bearing*, and is
the reason `identifiers._json` must translate a decode error rather than let it out
(`identifiers.py:685-688`).

### C8 — Three clients have no pacing gate, and only one says why

`CpicClient` (`cpic.py:268`), `EnsemblResolver` (`ensembl.py:64`) and `AtlasClient`
(`atlas_client.py:342`) are the three clients in the tier with no `PacingGate`. The Atlas one is
**filed, not forgotten** (`atlas_client.py:31-33`: "no shared pacing gate (`@shared-pacing-gate`)").
**undetermined from code: whether `CpicClient` and `EnsemblResolver` lack a gate deliberately.**
Neither module says. `EnsemblResolver` is on the resolver chain and is called once per unresolved
rsID, which is exactly the loop `Grch37Client` (same service family, `grch37.py:61`) paces at 0.1 s.

### C9 — The HuggingFace surface catches `Exception`, not a typed family

`download.py` and `upload.py` translate `huggingface_hub` failures through blanket handlers:
`download.py:245` (→ `SnapshotNotPublished`), `download.py:294`, `download.py:340`, `download.py:573`, `download.py:586`, `upload.py:494`,
`upload.py:676`, `upload.py:812`. Nothing of the library's type escapes — so there is no leak in the
D1 sense — but a blanket `except Exception` also swallows a `TypeError` or an `AttributeError` from
our own code into "nothing is published at …". `huggingface_hub` does publish a typed tree
(`HfHubHTTPError`, `RepositoryNotFoundError`, `EntryNotFoundError`) and none of it is named anywhere
in the package. **undetermined from code: whether the blanket is deliberate width (the lazy import
means the types are not available at module scope) or a gap.** `download.py:159` records the incident
in the other direction — `cache pull`'s own "blanket `except Exception`" once reported a
never-published snapshot as a failure, which is what produced `SnapshotNotPublished`
(`download.py:153`).

### C10 — `ALPHAGENOME_API_KEY` is read without `load_env()`, in the one function whose docstring cites the rule

`expression._connect` (`expression.py:291`) reads the credential at `expression.py:297`:

```python
key = os.environ.get("ALPHAGENOME_API_KEY") or ""
```

Its docstring (`expression.py:293-295`) claims the rule it does not follow:

> The credential is read **here, where it is used** rather than as a side effect of some earlier
> call (`@credential-where-read`), and an empty string and an unset variable are one absence —
> `export ALPHAGENOME_API_KEY=` must mean the same thing as never setting it.

The second half is honoured — `or ""` collapses unset and exported-empty. The first half is not:
`grep -n 'load_env' expression.py` returns **nothing**. The variable reaches `os.environ` only if some
earlier call in the process already loaded the `.env` — a `resolve_*_reference` or
`_resolve_parquet_cache` (`locations.py:335`, `locations.py:389`), or another client's constructor.
That is exactly the `EutilsSettings` incident `test_cli_surface.py:179-182` describes:

> `EutilsSettings` read `os.environ` directly, so the key reached it only as a side effect of some
> *unrelated* call resolving a cache path.

`_connect` is reached from `enrich_expression` at `expression.py:411` (`(client or _connect())`) — a
caller that injects no client. Every sibling reader in the tier calls `load_env()` immediately before
reading: `eutils.py:84`, `pharmvar.py:229`, `literature.py:424`, `literature.py:525`, `upload.py:156`,
`download.py:241`, `caches.py:480`, `net.py:142-144`. This is the one that does not.

The guard cannot see it: `test_the_ncbi_credential_is_loaded_where_it_is_read`
(`test_cli_surface.py:176`) monkeypatches `eutils.load_env` and `literature.load_env` only
(`test_cli_surface.py:187-188`) — the roster is two hand-named modules, which is
`@registry-completeness` in its usual shape. The symptom would be the same as the eutils one was:
silent, and dependent on what else the process happened to do first — here a hard
`ExpressionError("ALPHAGENOME_API_KEY is not set…")` (`expression.py:299-302`) on a machine whose
`.env` holds a working key.

**undetermined from code: whether some path into `enrich_expression` always loads `.env` first.** The
licence gate and the MANE cache resolution both run before line 411, and `mane_cache` resolution goes
through `locations`; whether that is guaranteed on every branch is not something the module states,
and relying on it would be the defect rather than the mitigation.

### Not defects, recorded so a reader does not re-flag them

* `(httpx.TransportError, httpx.TimeoutException)` appears in eight predicates and is redundant on
  `httpx 0.28.1` (`issubclass(httpx.TimeoutException, httpx.TransportError)` is `True`, measured).
  Harmless; it reads as two legs and is one.
* `grch37`'s `except (httpx.TransportError, httpx.TimeoutException, httpx.HTTPError)` (`grch37.py:151`,
  `:197`) names a superclass beside two subclasses **inside one tuple**, which
  `test_shadowed_handlers.py:152` explicitly rules a non-finding: "redundant, not dead — both names
  route to the same block".
* `PgsCatalogClient` raising on a 404 is deliberate and inverted from `OntologyClient`'s: the Catalog
  says "no such score" with an empty body on a 200, so a 404 means the request went somewhere
  unexpected (`pgs.py:426-428`, and `test_client_exception_contract.py:120-131`).
* `ClingenAlleleClient._fetch` uses `client = self._client or httpx` (`clingen_allele.py:249`) —
  module-level `httpx.get` when nothing is injected, so it owns no connection pool. `LitvarClient`
  (`litvar.py:394`) and `CivicApiClient` (`civic_api.py:337`) do the same. It is why the coverage walk
  still finds them (`"httpx" in source`) even though `"httpx.Client("` never appears in their bodies.
## 7. Every source adopted

The authority for this section is `enricher/src/just_dna_enricher/licensing.py` (1236 lines), which
holds every `SourceTerms` record, the acquisition gate, and the `sources.csv` read/merge/write
surface. The model those records are poured into lives one tier down, in
`schema/src/just_dna_format/sources.py`.

The module's own framing of the split (`licensing.py:1-24`): the enricher "is the only tier that
fetches, so it is the only tier that knows where a fact came from and on what terms", and the refusal
lives at acquisition because "under a data-usage policy, the terms are accepted when the data is
*taken*. Refusing here means nothing is fetched; refusing at compile would only mean nothing is
written, after the copy already exists on disk."

### 7.1 The complete source table

### How this was counted

Not by eye. The rows below come from walking the module's own namespace with `isinstance`:

```python
import just_dna_enricher.licensing as L
from just_dna_enricher.licensing import SourceTerms
found = {n: v for n, v in vars(L).items() if isinstance(v, SourceTerms)}
```

**Result: 18 module-level `SourceTerms` constants.** `TERMS_BY_SOURCE`
(`licensing.py:878-900`) has **18 keys**. The two sets match exactly in both directions — no constant
is missing from the registry, and no registry key lacks a constant (checked by set difference on
`t.source` vs `TERMS_BY_SOURCE.keys()`). A nineteenth `SourceTerms` is *constructed* at runtime but
never bound at module level: `pgs_score_terms()` (`licensing.py:645-677`) mints one per PGS Catalog
score, namespaced `pgs_catalog:PGS000013`.

No test asserts that parity as a set. `test_alphagenome_atlas_terms.py:35-37` pins one identity
(`TERMS_BY_SOURCE["alphagenome_atlas"] is ALPHAGENOME_ATLAS_TERMS`) and calls it "the identity assert
every source in this module carries", but that is per-source, not an equality over the walked set.

The cache-lane column is a **two-way join** against `caches.CACHE_LANES` (15 lanes,
`caches.py:827-1088`), because lane name and lane `terms` do not always agree: `drug_labels` carries
`terms=CLINPGX_TERMS` under a different lane name, and `clinvar`/`civic`/`strchive`/`mitomap`/
`pubmind`/`mane` are lanes whose `terms` field is `None` even though a terms constant exists.

### Can `check_declared_use` refuse it?

A three-state column, read straight off `check_declared_use` (`licensing.py:942-977`):

* **`commercial_use is False` → CAN RAISE.** `LicenseRefusal` on `declared_use == "commercial"`
  (`licensing.py:966-971`).
* **`commercial_use is True` → NEVER GATES.** Returns `None` immediately (`licensing.py:964-965`) for
  every declaration.
* **`commercial_use is None` → ALWAYS SKIPS.** Returns the unknown-terms reason string
  (`licensing.py:959-963`) for every declaration, including `commercial`. It can never raise and can
  never proceed.

### The table

| Source key | Constant | Licence | `commercial_use` | `redistribution` | `share_alike` | Gate outcome | Cache lane | Gated? | Pass / command that consults it |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `clinpgx` | `CLINPGX_TERMS` `:126-135` | `CC-BY-SA-4.0` | `False` | `True` | `True` | **can raise** | `clinpgx` **and** `drug_labels` (`caches.py:883`, `:909`) | yes — 2 lane gates + 3 pass gates + 2 command gates | `clinpgx check` (`clinpgx.py:201` gate, `:342` row at `annotation`); `draft-clinpgx` (`clinpgx_draft.py:377` gate, `:420` row); `clinpgx check-labels` (`drug_labels.py:680` gate, no row — see § 7.6 (j)); `clinpgx build` (`cli.py:928`), `clinpgx build-labels` (`cli.py:4605`) |
| `cpic` | `CPIC_TERMS` `:139-148` | `CC-BY-SA-4.0` | `False` | `True` | `True` | **can raise** | `cpic` (`caches.py:896`) | yes — 1 lane gate + 2 pass gates + 1 command gate | `pgx` (`pgx.py:463` via `consult`, `:319` gate); `draft` (`pgx_draft.py:282` gate, `:523` row); `cpic build` (`cli.py:2247`) |
| `pharmvar` | `PHARMVAR_TERMS` `:154-166` | `CC-BY-SA-4.0` | `False` | `True` | `True` | **can raise** | `pharmvar` (`caches.py:922`) — `publish_repo=None` | yes — 1 lane gate + 1 pass gate (`pgx.py:319`, reached via `consult`) + 1 command gate | `pgx` (`pgx.py:462`, gate at `:319`); `pharmvar build` (`cli.py:2360`) |
| `clingen` | `CLINGEN_TERMS` `:176-185` | `CC0-1.0` | `True` | `True` | `False` | never gates | none | no | `dosage` (`clingen.py:287` row at `annotation`, written only when `covered`, `:295`); `gene-validity` (`gene_validity.py:562` via `record_source_terms`, layer `gene_validity`) |
| `gencc` | `GENCC_TERMS` `:198-210` | `CC0-1.0` | `True` | `True` | `False` | never gates | none | no | `gene-validity` (`gene_validity.py:69`, `:562`) |
| `clinvar` | `CLINVAR_TERMS` `:217-229` | `public-domain` | `True` | `True` | `False` | never gates | `clinvar` (`caches.py`, `terms=None`) | no | `assertions` (`assertions.py:389`, layer `clinical_assertion`); `draft-panel` (`clinvar_draft.py:650` gate, `:839` row at `annotation`); `enrich` via `RESOLUTION_AUTHORITY_BY_LINK["clinvar"]` (`licensing.py:287`; the link is really stamped — `enrich.py:1064`, `:1068`, `:2263`) |
| `ensembl` | `ENSEMBL_TERMS` `:233-241` | `Apache-2.0` | `True` | `True` | `False` | never gates | `ensembl` (`terms=None`, `publish_repo=None`) | no | `enrich` only, via `RESOLUTION_AUTHORITY_BY_LINK` (`licensing.py:283-286`: `cache`, `ensembl`, `ensembl-rest`, `ensembl-graphql` all map to it) → `enrich.py:2029` `record_source_terms(..., "resolution", ...)` |
| `gnomad` | `GNOMAD_TERMS` `:256-269` | `CC0-1.0` | `True` | `True` | `False` | never gates | none (the `constraint` lane carries `terms=None`) | no | `frequencies` (`frequencies.py:376`, layer `frequency`); `gene-metrics` (`gene_metrics.py:431`, layer `gene_metrics`); `enrich` authority (`licensing.py:288`; link stamped at `enrich.py:1149-1150`) |
| `gwas_catalog` | `GWAS_CATALOG_TERMS` `:366-378` | `None` (no named licence) | `None` | `True` | `None` | **always skips** | none | no | `gwas` (`gwas.py:597`, `:710` — layer `gwas_effect`) |
| `pubmind` | `PUBMIND_TERMS` `:402-420` | `None` | `None` | `None` | `None` | **always skips** | `pubmind` (`terms=None`, `publish_repo=None`) | no | `draft-panel --source pubmind` (`pubmind_draft.py:649` row at `annotation`). `pubmind build` consults no terms constant — the lane carries `terms=None` |
| `civic` | `CIVIC_TERMS` `:463-478` | `CC0-1.0` | `True` | `True` | `False` | never gates | `civic` (`terms=None`) | no | `draft-panel --source civic` (`civic_draft.py:613`, layer `annotation`); `civic citations` (`civic_citations.py:547`, layer `literature` per `civic_citations.py:96`) |
| `clingen_allele_registry` | `CLINGEN_ALLELE_REGISTRY_TERMS` `:447-460` | `None` | `None` | `None` | `None` | **always skips** | none | no | `draft-panel --source civic`, **only when the registry was actually asked** (`civic_draft.py:612-613`) |
| `mane` | `MANE_TERMS` `:498-516` | `None` | `None` | `None` | `None` | **always skips** | `mane` (`terms=None`, `publish_repo=None`) | no | **none** — see § 7.6 (e) |
| `pgs_catalog` | `PGS_TERMS` `:538-554` | `None` | `None` | `None` | `None` | **always skips** | none | no | `check-identifiers --pgs` (`identifiers.py:1010` floor row, `:1015` per-score rows, `:1126` merge) |
| `strchive` | `STRCHIVE_TERMS` `:687-700` | `MIT` | `True` | `True` | `False` | never gates | `strchive` (`terms=None`) | no | `draft-repeats` (`strchive_draft.py:238` gate, `:299` row at `annotation`). `check-repeat-bands` and `strchive build` touch the lane, not the terms constant — no gate call and no `SourceRow` |
| `mitomap` | `MITOMAP_TERMS` `:720-738` | `CC-BY-3.0` | `True` | `True` | `False` | never gates | `mitomap` (`terms=None`, with an explicit comment at `caches.py:983-987`) | no | `draft-panel --source mitomap-miss` (`mitomap_draft.py:241` gate, `:323` row at `annotation`) |
| `alphagenome_avi` | `ALPHAGENOME_AVI_TERMS` `:778-821` | `AlphaGenome Services Additional Terms of Service (2026-09-08)` | `True` | `True` | `False` | never gates | `alphagenome_avi` (`caches.py:1064`, `terms=ALPHAGENOME_AVI_TERMS`) | lane gate present but **cannot refuse** | lane gate only, plus a `VerificationRecord.source` label (`alphagenome_check.py:87`). **No `SourceRow` is ever written for this key** |
| `alphagenome_atlas` | `ALPHAGENOME_ATLAS_TERMS` `:847-876` | `AlphaGenome Output Terms of Use (2026-09-08), under the AlphaGenome Services Additional Terms` | `False` | `True` | `False` | **can raise** | none | yes — pass gate | `alphagenome expression` (`expression.py:375` gate, `:495` row at layer `expression_effect` per `expression.py:90`) |

Line numbers in the Constant column are `licensing.py`.

**Axis tallies over the 18 (computed, not read):** `commercial_use` — 9 `True`, 4 `False`, 5 `None`.
`redistribution` — 14 `True`, 0 `False`, 4 `None` (`pubmind`, `clingen_allele_registry`, `mane`,
`pgs_catalog`). `share_alike` — 10 `False`, 3 `True`, 5 `None`. **No `SourceTerms` constant has
`redistribution=False`**; the only `False` on that axis in the whole module is the
`academic_research_only` PGS score class (`licensing.py:609`).

### Which lanes carry a terms object

From `CACHE_LANES` (15 lanes):

* **5 lanes with `terms`:** `clinpgx`→`clinpgx`, `cpic`→`cpic`, `drug_labels`→`clinpgx`,
  `pharmvar`→`pharmvar`, `alphagenome_avi`→`alphagenome_avi`.
* **10 lanes with `terms=None`:** `ensembl`, `clinvar`, `constraint`, `pubmind`, `civic`, `strchive`,
  `mitomap`, `mitomap_miss`, `mane`, `acmg`.
* **7 terms records with no lane under either join:** `alphagenome_atlas`, `clingen`,
  `clingen_allele_registry`, `gencc`, `gnomad`, `gwas_catalog`, `pgs_catalog`.

The lane field's stated purpose is the *gate*, not the licence — `caches.py:983-987`, on the
`mitomap` lane:

> `terms=None` even though `MITOMAP_TERMS` exists, and the field is what decides it: this column is
> the declared-use **gate**, not the licence. CC BY 3.0 states commercial and clinical use free, so
> `check_declared_use` would answer `None` on every declaration and a gate that cannot refuse is a
> gate nobody should have to read. ClinVar and STRchive have terms constants and a `None` here for
> the same reason.

### Sources reached by the tier that have no `SourceTerms` at all

* **`litvar`** — deliberate, with the membership rule stated in full at `litvar.py:97-102`: an entry
  earns its place "either through a pass that records it into `sources.csv` (`clingen_allele_registry`
  through `civic_draft`, `pubmind` through its drafting provider) or through a snapshot that keeps the
  source's bytes on disk … (`MANE_TERMS` is that case). This lane has neither … so an entry would be
  documentation wearing a registry row."
* **`acmg`** — a cache lane (`caches.py`, `terms=None`, `publish_repo=None`) with no terms constant.
  `acmg.py:26-28` states the exception explicitly: "**This pass records no `SourceRow`** … Nothing
  here lands in the module".
* **PubMed / Europe PMC literature** — deliberately absent from `TERMS_BY_SOURCE`
  (`licensing.py:296-303`): "There is deliberately **no `pubmed` entry in `TERMS_BY_SOURCE`** and
  there will not be one: a literature source's terms are per article, not per source". Article rights
  are a separate shape, `ArticleTerms` (`licensing.py:292-308`) with a 7-entry
  `ARTICLE_TERMS_BY_LICENSE` map (`licensing.py:320-328`) and the resolver `article_terms()`
  (`licensing.py:331-344`).

### 7.2 The `SourceTerms` model, and where each half lives

The tier split is clean and worth stating first: **`SourceTerms` is enricher-only, `SourceRow` is
schema-tier.** `SourceTerms` is what this tier can *state* about a service before any bytes arrive;
`SourceRow` is what gets written into the module and hashed by the compiler. `SourceTerms.row()` is
the one constructor that turns the first into the second.

### `SourceTerms` — `enricher/src/just_dna_enricher/licensing.py:58-110`

A frozen dataclass (`@dataclass(frozen=True)`, `:58`), docstring: *"The terms a service publishes, as
far as they can be established without the payload."*

| Field | Type | Default | Line | Meaning |
| --- | --- | --- | --- | --- |
| `source` | `str` | required | `:62` | The identifier that joins `sources.csv.source`. The only non-defaulted field. |
| `license` | `str \| None` | `None` | `:63` | Licence identifier or name. `None` is this file's spelling for "the terms could not be established" (`licensing.py:390-392`). |
| `license_url` | `str \| None` | `None` | `:64` | Where the terms were read from. |
| `attribution` | `str \| None` | `None` | `:65` | The credit line. |
| `notice` | `str \| None` | `None` | `:66` | Restrictions no flag expresses. |
| `share_alike` | `bool \| None` | `None` | `:67` | Copyleft obligation, tri-state. |
| `commercial_use` | `bool \| None` | `None` | `:68` | Sale permitted, tri-state. **The only axis `check_declared_use` reads.** |
| `redistribution` | `bool \| None` | `None` | `:69` | Passing the data on at all, tri-state. |

`SourceTerms` has no `layer`, no `declared_use`, no `dataset`, no `fetched_at`, no `license_sha256`
and no `draft_digest` — those are supplied by the caller or computed at `row()` time.

### `SourceTerms.row()` — `licensing.py:71-110`

```python
def row(self, layer: str, *, declared_use: str,
        dataset: str | None = None, license_text: str | None = None) -> SourceRow
```

Three things happen here that nowhere else does:

1. **`license_sha256` is computed** (`:99-101`): `"sha256:" + hashlib.sha256(pinned.encode("utf-8")).hexdigest()`.
2. **Blank-is-absent normalization** (`:93`): `pinned = license_text if (license_text or "").strip() else None`.
   The docstring (`:84-91`) gives the reason: a licence file that exists and says nothing hashes to
   `sha256:e3b0c442…b855`, "a definite answer to a question nobody answered, indistinguishable from a
   real pin once it is in `sources.csv`". One normalizer "because there are four sinks (two archive
   readers, the ClinPGx drafter, and a registry's status field)". Pinned by
   `test_a_blank_licence_is_not_terms.py:170` (`test_a_blank_licence_text_pins_nothing`) and `:178`
   (`test_a_stated_licence_still_pins`).
3. **`fetched_at=now_utc_iso()`** (`:109`) — stamped at row construction, never passed in.

### `SourceRow` — `schema/src/just_dna_format/sources.py:85-255`

A plain `BaseModel` with `model_config = ConfigDict(extra="forbid")` (`:112`), **not** an
`AuthoredModel` (`:88-90`). Thirteen fields:

| Field | Line | Notes |
| --- | --- | --- |
| `source` | `:120-127` | Open string, deliberately not a closed vocabulary. |
| `layer` | `:128-135` | Closed vocabulary `VALID_SOURCE_LAYERS`, validated at `:238-244`; **required** (the validator raises `"layer is required"` on `None`). |
| `license` | `:138-146` | Open string, "rather than a closed SPDX vocabulary". |
| `license_url` | `:147-149` | |
| `license_sha256` | `:150-158` | |
| `attribution` | `:159-163` | |
| `notice` | `:164-172` | |
| `share_alike` | `:175-182` | Tri-state; "None means UNKNOWN, never false". |
| `commercial_use` | `:183-192` | Tri-state. |
| `redistribution` | `:194-204` | Tri-state, "A THIRD axis, not a shade of `commercial_use`". |
| `declared_use` | `:207-214` | Closed vocabulary `VALID_DECLARED_USE`, validated at `:246-249`. |
| `dataset` | `:217-221` | |
| `fetched_at` | `:222-226` | Canonicalized on load, `:251-255`. |
| `draft_digest` | `:227-236` | Since `0.6.0`; the only field `SourceTerms.row()` never sets. |

Two schema-tier pieces beyond the model:

* **`SOURCE_FACT_FIELDS`** (`sources.py:69-82`) — the 12 columns feeding `integrity.source_signature`.
  `source` is **in** the fact set here, which inverts the other fact tables (`sources.py:52-57`:
  "Here the source **is the subject** of the row"). `fetched_at` and `draft_digest` are out (`:60-68`).
* **`taints_commercial_use(row)`** (`sources.py:258-269`) and **`taints_redistribution(row)`**
  (`:272-291`). Both require *two* conditions: the axis is explicitly `False` (an unknown never
  taints) **and** `row.layer == "annotation"`.

The enricher side also derives the CSV column order from the model rather than restating it:
`SOURCES_FIELDNAMES = list(SourceRow.model_fields)` (`licensing.py:989`). The comment at `:980-988`
records why: the list used to be a literal and "silently omitted `redistribution` — so every
`sources.csv` this workspace has ever written recorded that axis as *unknown* while the terms
constants right above state it as `True`". Pinned by
`test_literature_terms.py:207` (`test_the_written_columns_are_derived_from_the_model`) and
`test_pgx_licensing.py:210` (`test_every_declared_column_survives_a_write_read_cycle`).

### 7.3 `check_declared_use` in full

`licensing.py:942-977`. Signature:

```python
def check_declared_use(terms: SourceTerms, declared_use: str) -> str | None
```

Docstring (`:943-954`): *"Decide whether a fetch may proceed. Returns a skip reason, or raises, or
returns None to go. Three outcomes rather than two, and the middle one is the point."*

### The three `declared_use` values

`VALID_DECLARED_USE: frozenset[str] = frozenset({"unstated", "non_commercial", "commercial"})` —
`schema/src/just_dna_format/vocab.py:606`. `SourceRow.declared_use` describes it (`sources.py:207-214`)
as *"The use declared when the data was fetched … A claim about the user, not about the licence —
which is why it is a separate axis from the three flags."*

* **`unstated`** — nobody has said. It is the default in `record_source_terms`
  (`licensing.py:914`) and the value hardcoded by the PGS leg (`identifiers.py:1010`, `:1016`) and by
  `civic citations` (`civic_citations.py:549`). Against a no-sale source it produces a **skip**, and
  the compile gate treats it as no declaration at all (`compiler.py:5931-5933`: *"`unstated` is not a
  loophole: it is the absence of a declaration, which is precisely what this gate wants."*).
* **`non_commercial`** — the declaration that unblocks a no-sale source, both at fetch
  (`licensing.py:972-973`) and at compile (`compiler.py:5933`).
* **`commercial`** — the declaration that collides with a no-sale source and raises.

### Normalization, first

```python
declared_use = check_vocab(declared_use, VALID_DECLARED_USE, "declared_use") or declared_use
```

`licensing.py:958`, with the comment at `:955-957`: *"Through the shared checker, so a `-`/`_` slip is
canonicalized here exactly as it is in the cell this gate later reads: a caller passing
`non-commercial` must not get a different verdict from the same string written into the file."*

`check_vocab` (`schema/src/just_dna_format/vocab.py:1203-1214`) passes `None` through, canonicalizes a
`-`/`_` separator slip, and **raises `ValueError`** on a non-member:
`f"{field_name} must be one of {sorted(vocab)}, got: {value!r}"`. Verified by running it:

* `check_declared_use(PHARMVAR_TERMS, "non-commercial")` → `None` (proceeds; the hyphen is
  canonicalized).
* `check_declared_use(PHARMVAR_TERMS, "comercial")` → `ValueError: declared_use must be one of
  ['commercial', 'non_commercial', 'unstated'], got: 'comercial'`.

So a typo is a hard `ValueError`, **not** a `LicenseRefusal` and not a skip. The `or declared_use`
tail only ever fires when `check_vocab` returned `None`, i.e. when the caller passed `None` — in which
case the string comparisons at `:966` and `:972` both fail and the call lands in the final
`unstated`-shaped skip. Verified: `check_declared_use(PHARMVAR_TERMS, None)` returns the
`"forbids sale and no use was declared"` message.

### Outcome 1 — unknown terms → **skip** (`licensing.py:959-963`)

Fires first, before any declaration is looked at, so it is reached for `commercial` too.

```
f"{terms.source}: terms could not be established, so the data is not used. Unknown is "
f"not a finding that it is forbidden — it is the absence of a finding either way."
```

Applies to `gwas_catalog`, `pubmind`, `clingen_allele_registry`, `mane`, `pgs_catalog` — the five
constants with `commercial_use is None`. Pinned by
`test_pubmind_licensing.py:76` (`test_the_acquisition_gate_skips_rather_than_refusing_or_permitting`)
and `test_pgx_licensing.py:197` (`test_unknown_terms_are_skipped_not_refused_and_not_used`).

### Outcome 2 — permissive → **proceed** (`licensing.py:964-965`)

```python
if terms.commercial_use is True:
    return None
```

No declaration is consulted at all. Pinned by `test_pgx_licensing.py:205`
(`test_permissive_source_proceeds_under_any_declaration`). `licensing.py:686` says the same thing
about STRchive: *"a module drafted from this stays sellable, and `check_declared_use` answers `None`
on every declaration."*

### Outcome 3 — no-sale source + `commercial` → **raise `LicenseRefusal`** (`licensing.py:966-971`)

```
f"{terms.source} is {terms.license} and its terms forbid offering the data for sale "
f"({terms.license_url}). A commercial declaration cannot be reconciled with that, so "
f"nothing was fetched. Use --use non-commercial if that describes your use."
```

`LicenseRefusal(RuntimeError)` — `licensing.py:49-55`. Its docstring: *"Fatal in **both** modes,
unlike most enricher findings. The mode ladder grades how confident we are in a *finding*; this is not
a finding about the data, it is a statement that the fetch is not permitted. `best_effort` means
'resolve what you can', never 'take what you may not'."*

### Outcome 4 — no-sale source + `non_commercial` → **proceed** (`licensing.py:972-973`)

### Outcome 5 — no-sale source + anything else → **skip** (`licensing.py:974-977`)

```
f"{terms.source} forbids sale and no use was declared, so it was skipped. Re-run with "
f"--use non-commercial to record a declaration ({terms.license_url})."
```

### Where the three outcomes are consumed

* **Lane-level** — `caches._gate` (`caches.py:330-345`) wraps it and converts:
  `LicenseRefusal` → `RebuildOutcome(lane, False, f"refused: {exc}")`; a reason string →
  `RebuildOutcome(lane, None, f"skipped: {reason}")`. The docstring (`:332-335`) states the
  tri-state: *"`commercial` against a no-sale source is a `False` … while `unstated` is a `None`"*.
  Called from the four PGx rebuild adapters (`caches.py:419`, `:448`, `:464`, `:650`) and generically
  from `prepare_lane` at `caches.py:1327-1328` using `lane.terms`.
* **`cache pull`** — `cli.py:1885-1886`, also on `lane.terms`.
* **Pass-level** — nine direct call sites: `clinpgx.py:201`, `clinpgx_draft.py:377`,
  `clinvar_draft.py:650`, `drug_labels.py:680`, `expression.py:375`, `mitomap_draft.py:241`,
  `pgx.py:319` (inside `consult`, reached twice — `pgx.py:462` PharmVar, `:463` CPIC),
  `pgx_draft.py:282`, `strchive_draft.py:238`.
* **Command-level** — `cli.py:928` (`clinpgx build`), `:2247` (`cpic build`), `:2360`
  (`pharmvar build`), `:4605` (`clinpgx build-labels`).

A pass that receives a skip records it as a `not_permitted` verification outcome rather than as a
connectivity failure — `pgx.py:321-323`, `drug_labels.py:684`, pinned by `test_pgx_licensing.py:645`
(`test_a_licence_refusal_is_not_a_connectivity_problem`).

### 7.4 The compile gate

### The path from `SourceTerms` to the file

1. A pass builds a `SourceRow` — either directly, `X_TERMS.row(layer, declared_use=…, dataset=…)`
   (`licensing.py:71`), or through `record_source_terms(source_names, layer, spec_dir, …)`
   (`licensing.py:908-939`), which looks each name up in `TERMS_BY_SOURCE` and **silently skips a name
   with no constant** (`:936`: `if name in TERMS_BY_SOURCE`). The docstring's reason (`:931-934`):
   *"A name with no terms constant is skipped rather than guessed at … inventing a row for the rest
   would be worse than the compiler's honest warning that the terms are unrecorded."*
2. `merge_sources_file(rows, spec_dir, error=…)` (`licensing.py:1056-1075`) resolves the path,
   loads the existing table strictly (raising the *caller's* error type on an unparseable one,
   `:1073`), and merges.
3. `merge_sources_csv` (`licensing.py:1017-1027`) is **never-clobber**: `merged.setdefault((row.source,
   row.layer), row)` (`:1024`), output sorted by `(source, layer)` for determinism (`:1025`).
   `SourceRow._KEY_FIELDS = ("source", "layer")` (`sources.py:110`) is the same key.
4. `write_sources_csv` (`licensing.py:1007-1014`) writes through `atomic_writer` with
   `SOURCES_FIELDNAMES`, rendering cells via `_cell` (`:992-1004`), which keeps the tri-state intact:
   `None → ""`, `True → "true"`, `False → "false"`.

The one thing that overwrites a cell never-clobber would have kept is `withdraw_stale_dataset`
(`licensing.py:1078-1111`), and it only ever **blanks** `dataset`, never re-labels (`:1090-1093`).

### The filename the gate keys on

Two spellings are accepted, and **`sources.csv` is the deprecated one**:

* `SOURCES_CSV: str = "sources.csv"` — `schema/src/just_dna_format/layout.py:45`
* `LICENSING_CSV: str = "licensing.csv"` — `layout.py:46`
* `SIDECAR_SPELLINGS = {SOURCES_CSV: (SOURCES_CSV, LICENSING_CSV)}` — `layout.py:58-61`, documented
  *"deprecated first and preferred last"*.
* `DEPRECATED_SPELLINGS = frozenset({SOURCES_CSV})` — `layout.py:67`, warn-only in both modes:
  *"a deprecation that refused anything would be a breaking change wearing a notice"* (`:64-66`).

So the current spelling an author should write is **`licensing.csv`**, and the enricher writes
whichever the module already has — `sources_path()` (`licensing.py:1048-1053`) → `sidecar_path()`
(`:1030-1045`) → `layout.sidecar_write_path`, which also accepts the `derived/` subdirectory and
raises `SidecarCollision` when both spellings are present. That collision is re-raised as the calling
pass's own error type (`:1044-1045`). Pinned by `test_sources_spelling.py:36`, `:49`, `:93`, `:113`,
`:132`.

`layout.py:35-44` records why the rename was minor-legal: `sources.csv` "is deliberately outside the
compiler's `_INPUT_FILES` … so the filename enters no identity at all", while `sources.parquet` and
`manifest.sources` could *not* come along and wait for the major. *"For the whole 0.x tail a module
therefore reads `licensing.csv` → `sources.parquet` → `manifest.sources`."*

### The gate itself

`compiler/src/just_dna_compiler/compiler.py:5154-5163`, placed deliberately before
`output_dir.mkdir()` (`:5165`) — the comment at `:5149-5153`: *"Loaded here rather than with the other
fact tables because those are read *after* `output_dir.mkdir()`, and a refusal must leave nothing
written — this is the last point at which that is still true. Purely computation over injected data:
the compiler holds no source→licence map (Principle 2 …)."*

`_check_license_gate(rows)` — `compiler.py:5909-5941`:

```python
tainted = [r for r in rows if taints_commercial_use(r)]
if not tainted: return []
undeclared = sorted({r.source for r in tainted if r.declared_use != "non_commercial"})
if not undeclared: return []
```

Refusal message (`compiler.py:5936-5941`):

```
f"licensing: {undeclared} contribute annotation-layer content under terms that forbid sale, "
f"and this module records no non-commercial declaration for them. Re-run the enricher with "
f"a declared use (`--use non-commercial`) to record one, or remove the affected content. "
f"Declaring it is an assertion about how the module will be used — the compiler records that "
f"assertion, it does not verify it."
```

Properties the docstring states (`compiler.py:5910-5925`): it fires in **both** modes; it is keyed on
data carried by the module and never on a CLI flag, so `compile → reverse → compile` stays a fixed
point; and it is **most-restrictive-wins, module-wide** — one tainting row refuses the whole compile.

`taints_commercial_use` (`sources.py:258-269`) is the shared predicate, so "the compiler's gate and
the manifest summary cannot drift apart". It requires `commercial_use is False` **and**
`layer == "annotation"`.

### What reaches the manifest

`_sources_block(rows)` — `compiler.py:6072-6110`. The ladder (`:6083-6089`) is
most-restrictive-first: a tainting row makes the verdict `False`; failing that, any unknown makes it
`None`; only an all-known, none-forbidding set makes it `True`. Both `commercial_use` and
`redistribution` go through the same `_verdict` helper (`:6092-6093`), and
`unknown_terms_sources` (`:6091`, `:6104`) names every source whose `commercial_use is None`.
`taints_redistribution` is computed and published but **not gated anywhere in these packages** —
`sources.py:279-285` calls that settled rather than open, on the grounds that "a distribution right
is not a *use*" and the act to gate on is a publish, which happens in a registry.

`_source_checks` (`compiler.py:5947+`) adds two warning-only coherence findings (a declared source no
fact table used; a used source with no row) and "never escalates under `strict`". The `annotation`
and `literature` layers are exempt from the orphan half — `_UNCORROBORABLE_LAYERS`
(`compiler.py:5944-5945`).

### 7.5 Which sources can draft which authored tables

Named only; drafting mechanics are another section's subject. Every drafting provider writes at the
`annotation` layer, and every one of them calls `merge_sources_file` after a successful run.

| Source | Provider module | Command | Authored tables written |
| --- | --- | --- | --- |
| `cpic` | `pgx_draft.py` | `draft` | `haplotypes.csv`, `allele_function.csv`, `diplotypes.csv` (`pgx_draft.py:500-506`) |
| `clinpgx` | `clinpgx_draft.py` | `draft-clinpgx` | `pharm_variants.csv` (`clinpgx_draft.py:389`) |
| `clinvar` | `clinvar_draft.py` | `draft-panel` | `variants.csv` (partial rows, `clinvar_draft.py:726`) + `studies.csv` (`:743`) |
| `pubmind` | `pubmind_draft.py` | `draft-panel --source pubmind` | `variants.csv` only (`pubmind_draft.py:587`); it explicitly drafts **no** `studies.csv` and warns (`:591-594`) |
| `civic` | `civic_draft.py` | `draft-panel --source civic` | `variants.csv` (`civic_draft.py:597`) + `studies.csv` (`:600`) |
| `mitomap` (via the `mitomap_miss` increment) | `mitomap_draft.py` | `draft-panel --source mitomap-miss` | `variants.csv` (`mitomap_draft.py:302`) + `studies.csv` (`:305`) |
| `strchive` | `strchive_draft.py` | `draft-repeats` | `repeat_alleles.csv` (`strchive_draft.py:282`) |

`clingen_allele_registry` is consulted *by* `civic_draft` for identity resolution and records a row,
but drafts no table of its own (`civic_draft.py:612`).

### 7.6 Defect candidates (sources and licensing)

Each is a discrepancy visible in the code; none is a verified bug, and several have a stated
rationale that may make them intentional. Where the rationale exists it is quoted.

### (a) The PGS lane can write a row the compile gate refuses, and the remedy it names is unreachable

`identifiers.py:1010` and `:1016` construct **every** PGS row with `declared_use="unstated"`,
hardcoded:

```python
rows = [PGS_TERMS.row("annotation", declared_use="unstated", dataset=release)]
...
pgs_score_terms(status.pgs_id, status.license).row(
    "annotation", declared_use="unstated", license_text=status.license
)
```

The `academic_research_only` PGS class is `ScoreRights(share_alike=None, commercial_use=False,
redistribution=False)` (`licensing.py:606-610`). A score in that class therefore produces a row with
`commercial_use is False` at layer `annotation`, which is exactly `taints_commercial_use`
(`sources.py:269`). `_check_license_gate` then refuses the compile and its message says
*"Re-run the enricher with a declared use (`--use non-commercial`) to record one"*
(`compiler.py:5938-5939`).

`check-identifiers` has **no `--use` option**: its full signature is
`spec_dir / --strict / --traits / --genes / --pgs` (`cli.py:1114-1125`), and `declared_use` appears
nowhere else in `identifiers.py` (grep returns only `:1010` and `:1016`). `merge_sources_csv` is
never-clobber (`licensing.py:1024`), so a re-run cannot correct the cell either — only a hand edit of
the file can. The command's own docstring anticipates the taint (`cli.py:1136-1138`: *"a module
carrying an academic-research-use-only score must not compile claiming the generic terms"*) but not
the unreachable remedy.

*Undetermined from code:* whether any score in the Catalog currently classifies as
`academic_research_only` — that requires reading the live records, which this reference does not do.

### (b) The CIViC licence paragraph sits above the ClinGen Allele Registry constant

`licensing.py:422-430` is a comment paragraph that opens:

> `# CIViC is CC0 1.0 for the content — a public-domain dedication, so all three axes are permissive and`
> `# none of them is inferred.`

It runs without a blank separator straight into `licensing.py:431-446`, the ClinGen Allele Registry
paragraph, and the whole contiguous block sits immediately above
`CLINGEN_ALLELE_REGISTRY_TERMS` at `licensing.py:447` — whose three axes are `share_alike=None`,
`commercial_use=None`, `redistribution=None` (`:457-459`). So the comment block adjacent to the
constant opens with a sentence about a different source. The paragraph names CIViC in its first
word, so a reader is not actively misled — this is a misplaced comment above the wrong constant
rather than a false claim *about* that constant.

`CIVIC_TERMS`, the constant the paragraph is about, is at `licensing.py:463` with **no comment above
it at all** (`:461-462` are blank). The fix is a move rather than a rewrite.

### (c) A counted claim in prose that the file outgrew

`licensing.py:120-125`, the header of the original terms block:

> `# **All five permit redistribution**, so `redistribution=True` throughout`

There are now 18 `SourceTerms` constants, of which **14** are `redistribution=True` and **4** are
`None` (`pubmind`, `clingen_allele_registry`, `mane`, `pgs_catalog`). The sentence was true of the
five constants it was written above and is now read as a claim about the file. The next sentence in
the same comment is still accurate and is the one that matters: *"It is recorded rather than left null
because null means 'the terms could not be established', which is a different and weaker statement
than 'they allow it'."*

### (d) `PHARMVAR_TERMS.redistribution=True` beside a lane that refuses to publish

`PHARMVAR_TERMS` records `redistribution=True` (`licensing.py:165`). Its cache lane has
`publish_repo=None` and `ensure=None`, with this `unpublished` reason (`caches.py:923-927`):

> `"refused: the bulk data is pulled under a key PharmVar's terms §2 make personal and`
> `non-transferable, and no axis SourceTerms records covers passing that on. Build your own with`
> `pharmvar build --out <dir>"`

The lane itself says the axis cannot express the reason, so this is a documented mismatch rather than
a silent one — but `manifest.sources.redistribution` will read `True` for a module carrying a PharmVar
row, and nothing downstream sees the lane's sentence. It is the only `redistribution=True` source in
the table whose own snapshot route refuses on redistribution grounds.

**No terms record has `redistribution=False`**, so the converse case ("False but which does publish")
does not exist in `SourceTerms`. The only `False` on that axis anywhere is the PGS
`academic_research_only` class (`licensing.py:609`), which has no lane and no publish route.

### (e) `MANE_TERMS` is a registry member no executing code path reaches

`MANE_TERMS` (`licensing.py:498-516`) is in `TERMS_BY_SOURCE` (`:893`). It is never `.row()`'d: a
grep for `source="mane"` / `MANE_SOURCE` / `'mane'` across `enricher/src` returns exactly one hit,
`licensing.py:499` (the constant's own field). The `mane` cache lane carries `terms=None`, so it is
not the lane gate either. The only other mentions are docstrings — `mane_build.py:57` and
`litvar.py:101`.

The rationale is stated, at `litvar.py:97-102`:

> `#: Deliberately **not** a licensing.TERMS_BY_SOURCE member: every entry there earns its place`
> `#: either through a pass that records it into sources.csv … or through a snapshot that keeps the`
> `#: source's bytes on disk, where the unknown redistribution axis becomes load-bearing the moment`
> `#: somebody proposes publishing them (MANE_TERMS is that case).`

So the entry is earned by the snapshot rather than by a pass. Listed here because it is nonetheless a
constant with no executing consumer, and because `record_source_terms` would silently do nothing for
it (`licensing.py:936` skips names not in `TERMS_BY_SOURCE` — `mane` *is* in it, but no pass ever
hands the name over).

### (f) `ALPHAGENOME_AVI_TERMS` gates a lane it cannot refuse, and writes no row

`commercial_use=True` (`licensing.py:809`), so `check_declared_use` returns `None` for every
declaration. The lane nonetheless carries `terms=ALPHAGENOME_AVI_TERMS` (`caches.py:1064`), which
means `_gate` (`caches.py:330-345`) and `prepare_lane` (`caches.py:1327`) run a check that can only
proceed. `lane.terms` has exactly two consumers in the whole tier — `caches.py:1324-1327` and
`cli.py:1882-1885`, both of them `check_declared_use` (grep for `\.terms\b` over
`enricher/src/just_dna_enricher/*.py` returns those four lines and nothing else), so the field is the
gate and only the gate: nothing carries it into `release.json` or a published `LICENSE.txt`. That is
precisely what the `mitomap` lane's comment gives as the reason **not** to set the field
(`caches.py:983-987`): *"a gate that cannot refuse is a gate nobody should have to read. ClinVar
and STRchive have terms constants and a `None` here for the same reason."* Two lanes, one rule,
opposite settings.

Separately, no `SourceRow` is ever written for `alphagenome_avi`: the only use of
`ALPHAGENOME_AVI_TERMS.source` outside `licensing.py` and `caches.py` is
`alphagenome_check.py:87`'s `SOURCE_NAME`, which feeds `VerificationRecord.source`
(`alphagenome_check.py:444`, `:468`, `:484`, `:515`, `:533`, `:551`) — not `sources.csv`. Under
`@write-the-sourcerow` as `licensing.py:918-920` states it (*"A pass that consults a source must write
its `SourceRow`"*), a check reading AVI scores and recording nothing in the licence table is the shape
that rule names. Whether the RM193 checks *contribute* to a module table (which is the rule's real
trigger) is **undetermined from code** at the depth read here.

### (g) Three drafting gates over permissive constants

`clinvar_draft.py:650`, `strchive_draft.py:238` and `mitomap_draft.py:241` all call
`check_declared_use` on constants whose `commercial_use is True`, so the call can only return `None`.
They are not *entirely* inert — `check_vocab` inside the gate (`licensing.py:958`) raises `ValueError`
on a malformed `declared_use`, so the call doubles as vocabulary validation — but as a *licence* gate
they cannot refuse, which is the condition `caches.py:983-987` uses to justify `terms=None` on the
matching lanes. Same rule, applied at the lane and not at the pass.

`licensing.py:686` says the STRchive case out loud and treats it as expected: *"`check_declared_use`
answers `None` on every declaration."*

### (h) `record_source_terms`' docstring is contradicted by one of its six callers

`licensing.py:924-929`:

> `None of these layers can taint a module: taints_commercial_use requires the annotation layer,`
> `because a coordinate or an AC/AN is a fact the source *reports* rather than expression it *owns*.`
> `… declared_use defaults to unstated because no fact-layer source here forbids sale, so these`
> `passes never have to ask the author for a declaration.`

Five of the six callers match that description — `enrich.py:2029` (`resolution`),
`frequencies.py:376` (`frequency`), `gene_metrics.py:431` (`gene_metrics`), `gene_validity.py:562`
(`gene_validity`), `assertions.py:389` (`clinical_assertion`). The sixth does not:
`civic_draft.py:613` calls it with `"annotation"` **and** an explicit `declared_use=declared_use`
(`:617`). The function grew a caller the docstring's "none of these layers" sentence no longer
covers. Harmless today because CIViC is CC0, but the sentence is now a claim about callers rather
than about the function.

### (i) The lane comment's enumeration of `terms=None` lanes is partial and conflates two reasons

`caches.py:983-987` names "ClinVar and STRchive" as the lanes with a terms constant and `terms=None`
"for the same reason". The actual set is larger and splits in two:

* **`terms=None` because the gate could never refuse** (`commercial_use=True`): `clinvar`, `civic`,
  `strchive`, `mitomap`. `civic` is not named in the comment.
* **`terms=None` although the gate *would* act** (`commercial_use=None`, i.e. always-skip):
  `pubmind` and `mane`. Setting `terms` on these would make the lane skip every build. For `pubmind`
  the reason is stated in a test rather than in the code —
  `test_pubmind_licensing.py:76-80`: *"That is why `pubmind build` carries no `--use` flag: a gate
  that answers the same way for every declaration would refuse every build, and a flag feeding it
  would be a flag that does nothing."* For **`mane` there is no stated reason anywhere in
  `enricher/src`** — undetermined from code.
* `ensembl` and `constraint` have `terms=None` and no matching constant on the lane name
  (`ENSEMBL_TERMS`/`GNOMAD_TERMS` exist but the lanes do not reference them); `mitomap_miss` and
  `acmg` have no constant at all.

### (j) `drug_labels` consults ClinPGx and writes no `SourceRow`

`drug_labels.py:680` gates on `CLINPGX_TERMS`, and `drug_labels.py:79` binds
`SOURCE_NAME = CLINPGX_TERMS.source`, but neither `merge_sources_file` nor `record_source_terms`
appears anywhere in the module (grep over `enricher/src` returns no hit for either in
`drug_labels.py`). By contrast the sibling `clinpgx.py` check does write one (`clinpgx.py:342`,
`:349`).

The counter-argument is the narrowing rule the same codebase states — `licensing.py`'s
`@write-the-sourcerow` framing keys the duty on what the run *covered*, and `acmg.py:26-28` is an
explicit precedent for a pass that consults a source and records nothing because "Nothing here lands
in the module". `check-labels` is a cross-check that writes no authored cell, so it may be the same
case. **Undetermined from code:** whether the drug-label check contributes anything to a module
table. Listed because the analogous ClinPGx check next door does write a row, and because ClinPGx is
one of the four no-sale sources — the class where a missing row means the compile gate has nothing to
refuse on (`pgx_draft.py:509-513` records exactly that failure mode for CPIC).

### 7.7 Undetermined from code (sources and licensing)

Six of these are the code's own recorded undeterminates — it names them as open questions, and this
reference repeats them rather than resolving them. The rest are limits of what could be read here.

**The code's own:**

1. **`alphagenome_avi.redistribution=True` is a maintainer's reading, not a document.**
   `licensing.py:810-820` says so in the field comment: *"**`True` on the maintainer's reading,
   recorded as a reading rather than as a fact a document states** (2026-09-10) … Nothing in
   `docs/vendor/` says so in as many words — the download page settles *use*, not *sharing* — so this
   is the one value on this row that rests on judgement."* The same reading is *applied rather than
   re-taken* for `alphagenome_atlas` (`licensing.py:837-845`).
2. **MANE's EMBL-EBI half was never read.** `licensing.py:495-497`: *"MANE is a joint NCBI/EMBL-EBI
   product and only NCBI's side was read. EMBL-EBI's terms for the same tables were not opened, so
   nothing here asserts anything about them."*
3. **PubMind's data terms are unestablished and the unblock is an email.** `licensing.py:399-401`:
   *"The unblock action is to ask WGLab and CHOP's Office of Technology Transfer, in writing, whether
   the ANNOVAR-shipped subset may be redistributed and on what terms. Nobody else can answer it."*
4. **GWAS Catalog `commercial_use` is deliberately `None`.** `licensing.py:357-362`: the EBI sentence
   permits use generally *"but it is conditioned on terms the original data owners may impose, and
   for an aggregator of thousands of published studies those are not established here … Do not 'tidy'
   it to `True`."*
5. **PGS Catalog terms are a floor, not the terms.** `licensing.py:519-527`: *"`license` is a field on
   each score record, and the three values measured over the first 250 of 6,982 scores are not
   variations on one licence."* What the other 6,732 carry is unmeasured.
6. **ClinGen Allele Registry terms could not be established.** `licensing.py:435-440`:
   `reg.clinicalgenome.org/site/terms` *"answers **HTTP 200** with a generic Genboree 'broken link'
   page rather than a licence — a soft-404"*.

**Limits of this reading:**

7. Whether any live PGS Catalog score currently classifies as `academic_research_only` — the trigger
   for defect (a) — needs the live records and was not established.
8. Whether the RM193 AlphaGenome checks contribute anything to a module's authored tables, which is
   what decides whether defect (f)'s missing `SourceRow` is a defect or the `acmg.py:26-28` exemption.
9. Whether `clinpgx check-labels` contributes to a module table (defect (j)), same question.
10. Why the `mane` lane carries `terms=None` — no comment, test or docstring in `enricher/src` states
    a reason (defect (i)).
11. `test_alphagenome_atlas_terms.py` asserts against pinned vendor files under `docs/vendor/`
    (`test_alphagenome_atlas_terms.py:32`), which is not present in the tree this section was derived
    from, so those assertions were read but not executed.
## 8. The drafting surfaces

Seven providers in `enricher/src/just_dna_enricher/`, four CLI commands, and one shared append
mechanism that lives in the **compiler**, not here.

| command | provider module | entry point | tables written |
| --- | --- | --- | --- |
| `draft` | `pgx_draft.py` | `draft_gene` (`pgx_draft.py:253`) | `haplotypes.csv`, `allele_function.csv`, `diplotypes.csv` |
| `draft-clinpgx` | `clinpgx_draft.py` | `draft_pharm_variants` (`clinpgx_draft.py:361`) | `pharm_variants.csv` |
| `draft-panel --source clinvar` (default) | `clinvar_draft.py` | `draft_gene_panel` (`clinvar_draft.py:619`) | `variants.csv`, `studies.csv` |
| `draft-panel --source pubmind` | `pubmind_draft.py` | `draft_gene_panel_from_pubmind` (`pubmind_draft.py:435`) | `variants.csv` |
| `draft-panel --source civic` | `civic_draft.py` | `draft_panel_from_civic` (`civic_draft.py:443`) | `variants.csv`, `studies.csv` |
| `draft-panel --source mitomap-miss` | `mitomap_draft.py` | `draft_panel_from_mitomap_miss` (`mitomap_draft.py:216`) | `variants.csv`, `studies.csv` |
| `draft-repeats` | `strchive_draft.py` | `draft_repeat_loci` (`strchive_draft.py:205`) | `repeat_alleles.csv` |

`PANEL_SOURCES` is the closed `--source` vocabulary (`cli.py:3479`), folded through `_panel_source`
(`cli.py:3488-3497`) so `mitomap_miss` reaches `mitomap-miss`. Every source but `mitomap-miss` is in
`_GENE_SCOPED_PANEL_SOURCES` (`cli.py:3485`) and is refused with exit code 2 when no `--gene` is given
(`cli.py:3626-3634`).

### 8.1 What the enricher reuses, and what it reimplements

**Reused verbatim, from `compiler/src/just_dna_compiler/draft.py`.** Every provider imports the append
mechanism; none reimplements it.

- `DRAFTABLE` (`draft.py:92-99`) — the filename → model map. Not hand-kept: it is `variants.csv` and
  `studies.csv` explicitly, then `**{csv_name: model for csv_name, _, model in _TABLE_KINDS}`
  (`draft.py:95`), both spellings of the licence sidecar via `sidecar_spellings(SOURCES_CSV)`
  (`draft.py:96`), and `OVERRIDES_CSV` (`draft.py:97`). `model_for` raises `DraftError` naming
  `sorted(DRAFTABLE)` for anything else (`draft.py:172-174`).
- `natural_key` (`draft.py:213-223`) — reuses the compiler's own `_TABLE_DUPE_KEYS` plus
  `_CORE_DUPE_KEYS` (`draft.py:108-110`, itself `dict.fromkeys((VariantRow, StudyRow), _key_of)`), so a
  drafted row can never be one the compiler then rejects as a duplicate. Binning kinds return `None`
  deliberately — their duplicate rule is *overlap*, not equality (`draft.py:217-222`).
- `append_rows` (`draft.py:369-481`) — key-present ⇒ `already_present`/`differs`, key-absent ⇒
  appended. Never rewrites a cell: the whole-file rewrite path re-reads existing rows **as text**
  through `_render_existing` (`draft.py:702-709`) so a widening cannot reformat `1.0` into `1`.
- `append_partial_rows` (`draft.py:550-646`) + `PartialRow` (`draft.py:502-545`) — for a source that
  publishes most of a row. `PartialRow.rendered` writes `TEMPLATE_PLACEHOLDER` into every `stubbed`
  column (`draft.py:519-521`); `PartialRow.validation_errors` validates **by omission**, building the
  model without the stubbed columns and discarding any error located on one (`draft.py:527-545`).
- `place_rows` / `group_of` (`draft.py:666-699`) — delegated insertion. With no `group_by` it is
  `existing + incoming` and nothing shifts (`draft.py:681-682`); with one, a row lands after the last
  existing member of its group. There is deliberately no `at=N` (`draft.py:30-36`,
  `draft.py:656-658`). `DraftReport.shifted` names every existing row whose line moved.
- `authoring_requirements` (`draft.py:258-282`) — the three-shape requiredness answer (`always` /
  `any_of` / `defaulted`), used by `strchive_draft` as its skip guard.

**Reimplemented in the enricher, per provider:** which cells a source can state, which columns are
stubbed, the `match_on` tuple, the withholding vocabulary and its accounting equality, and the
`SourceRow` write. There is no shared enricher-side drafting base class — the only cross-provider code
reuse is `pubmind_draft` importing seven private helpers from `clinvar_draft`
(`pubmind_draft.py:76-88`: `_MATCH_ON`, `_genotype_worklist`, `_open_stubs`, `_refusal_summary`,
`_resolve_snapshot`, `_signature`, `_state_stub_warnings`, plus `sole_expressible_genotype`), which
the module docstring argues for explicitly (`pubmind_draft.py:3-9`).

### 8.2 `pgx_draft.py` — CPIC → the three star-allele tables

**What it drafts.** `HaplotypeRow` (`pgx_draft.py:111-123`: `haplotype_name`, `rsid`, `chrom`, `start`,
`allele`, `gene`), `AlleleFunctionRow` (`pgx_draft.py:385-390`: `gene`, `allele`, `activity_value`,
`function_status`), and `DiplotypeRow` twice — a phenotype row (`pgx_draft.py:418-423`: `gene`,
`haplotype_a`, `haplotype_b`, `phenotype`, `conclusion`) and, per `--drug`, a recommendation row
(`pgx_draft.py:230-241`) adding `drug`, `recommendation_strength`, `clinical_context`. All three go
through plain `append_rows` (`pgx_draft.py:499-507`) — nothing is stubbed. CPIC positions are stored
1-based without conversion (`pgx_draft.py:26-27`, `CPIC_GENOME_BUILD = "GRCh38"` at `pgx_draft.py:51`).

**Skip guard — RESTATED.** `pgx_draft.py:107`:

```python
if variant.rsid is None and (variant.chrom is None or variant.start is None):
```

which is a character-for-character copy of `HaplotypeRow._validate_identification`
(`schema/src/just_dna_format/pgx.py:202-205`). The comment above it says so
(`pgx_draft.py:95-96`: *"Mirror `HaplotypeRow._validate_identification` exactly"*) and records the
incident: the guard once accepted a bare `start`, so `draft --gene CYP2C9` died on an unhandled
pydantic error (`pgx_draft.py:96-99`). It is restated rather than derived, but it is **pinned
differentially**: `test_pgx_draft.py:339 test_the_guard_matches_the_models_own_rule` runs five
identity shapes through both the guard and `HaplotypeRow` and asserts
`kept == model_accepts, f"guard and model disagree for {case}"` (`test_pgx_draft.py:365`).

Two further grammar skips, both restated but against a shared constant rather than a model rule:
`STAR_ALLELE_PATTERN.match` at `pgx_draft.py:92` (haplotypes) and `pgx_draft.py:381` (allele
function), and `_split_diplotype` (`pgx_draft.py:132-136`) requiring both halves to match it.

**`SourceRow`.** Yes — `CPIC_TERMS.row("annotation", declared_use=..., dataset=cpic_dataset)` through
`merge_sources_file` (`pgx_draft.py:521-531`), then `stamp_draft_digest(spec_dir, CPIC_TERMS.source,
"annotation", ...)` (`pgx_draft.py:534`). Key `("cpic", "annotation")`. Gated `if not dry_run and
reports:` (`pgx_draft.py:508`) — i.e. on at least one table having had rows offered to it, so an
all-`already_present` re-run still writes. `dataset` is `getattr(cpic, "dataset", None)`
(`pgx_draft.py:316`), `None` on the live client. The comment block at `pgx_draft.py:509-520` records
that this provider shipped two releases *without* the row. **No test in `enricher/tests/` asserts this
write**: a grep for `sources.csv|licensing.csv|SOURCES_CSV` over `test_pgx_draft.py` returns nothing,
and `test_draft_declared_build.py:135-157` only checks `allele_function.csv`.

**Placeholders.** None. This provider stubs nothing; every row it writes is a complete model.

**Append-not-mutate.** `append_rows` keyed on `natural_key`; `test_pgx_draft.py:191
test_drafting_twice_is_idempotent` asserts `again.added == 0` and byte equality of every `*.csv`.
`--dry-run` → `test_pgx_draft.py:201 test_dry_run_writes_nothing`: `assert result.added > 0` then
`assert not list(spec.glob("*.csv"))`. No `group_by` is passed, so rows land at the end of the file.

### 8.3 `clinvar_draft.py` — the ClinVar snapshot → a gene panel

**What it drafts.** `VariantRow` as a `PartialRow` (`clinvar_draft.py:707-716`) and `StudyRow` through
`append_rows` (`clinvar_draft.py:743`). `_row_cells` (`clinvar_draft.py:432-465`) states identity,
`gene`, `clin_sig`, `clinvar=True`, `phenotype`, a transcribed `conclusion`, and folds `state` /
`pathogenic` / `benign` from `STATE_BY_CLIN_SIG` — never independently
(`clinvar_draft.py:458-465`). Five columns are refused as rules, not omissions
(`clinvar_draft.py:29-35`): `weight`/`direction`/`effect_*`, `trait_efo_id`, `acmg_sf`,
`curator`/`method`.

**Skip guard — RESTATED, and stricter than the model.** `_identity_cells` (`clinvar_draft.py:150-165`)
returns `None` unless there is an rsID, or `chrom and start is not None and ref and alt`
(`clinvar_draft.py:163`). `VariantRow._validate_identification`
(`schema/src/just_dna_format/spec.py:1044-1062`) needs only `chrom` + `start`; `ref`/`alts` are
optional and merely *require* a position. So the provider refuses records the model would accept, and
counts them as `unkeyable` (`clinvar_draft.py:688-690`, reported at `:718-722`). The rule it enforces
is stated as a design rule — identity whole or not at all (`clinvar_draft.py:25-28`) — not as the
model's rule. The residual safety net is `PartialRow.validation_errors`, whose refusals are grouped by
`_refusal_summary` (`clinvar_draft.py:304-328`).

**`SourceRow`.** Yes — `CLINVAR_TERMS.row("annotation", declared_use=..., dataset=dataset)`
(`clinvar_draft.py:838-842`), key `("clinvar", "annotation")`, then unconditional
`stamp_draft_digest` (`clinvar_draft.py:852`) and, **gated on `report.added`**,
`withdraw_stale_dataset` (`clinvar_draft.py:853-855`). `dataset` is `clinvar_dataset_label(reference)`
(`clinvar_draft.py:826`) and a snapshot that cannot state its release leaves the cell empty *and warns*
(`clinvar_draft.py:822-831`). Whole block is under `if not dry_run:` (`clinvar_draft.py:835`); a run
with no partials returns before it (`clinvar_draft.py:723-724`). Pinned by
`test_clinvar_draft.py:115` (*"a source rows were copied out of must be accounted for"* →
`assert (tmp_path / _LICENCE_CSV).is_file()`) and negatively by `test_clinvar_draft.py:172
test_dry_run_writes_nothing`, which asserts `not (tmp_path / _LICENCE_CSV).exists()`.

**Placeholders.** `genotype` and `state`, derived from the cells rather than listed:
`stubbed = tuple(column for column in ("genotype", "state") if column not in cells)`
(`clinvar_draft.py:702`). `genotype` is stubbed because ClinVar publishes alleles, not genotypes
(`clinvar_draft.py:10-16`); `state` because `VALID_STATES` has no "uncertain" member
(`clinvar_draft.py:696-700`). The one exception is `sole_expressible_genotype`
(`clinvar_draft.py:174-207`): on chrMT, and on chrY where `in_pseudoautosomal_region("Y", start)` is
`False`, exactly one genotype is expressible, so the ALT is written and nothing is stubbed — `True`
(diploid) and `None` (no PAR table) both keep the placeholder (`clinvar_draft.py:204-206`).
`test_clinvar_draft.py:442 test_an_undecidable_ploidy_keeps_the_placeholder` pins that arm.

What stops the stub compiling: `TEMPLATE_PLACEHOLDER = "<<REPLACE>>"`
(`schema/src/just_dna_format/vocab.py:980`) is refused by `reject_template_placeholders`
(`vocab.py:983-999`), a `mode="before"` validator wired onto every authored row through
`AuthoredModel._guard_raw_input` (`schema/src/just_dna_format/base.py:722-728`). Before-mode is
load-bearing: it runs *before* field coercion so a stub in `start: int` is diagnosed as an unfilled
template rather than as "Input should be a valid integer" (`vocab.py:986-989`).
`test_clinvar_draft.py:110` pins the write: `assert {r["genotype"] for r in rows} ==
{TEMPLATE_PLACEHOLDER}`.

**Append-not-mutate.** `append_partial_rows(spec_dir, "variants.csv", partials,
group_by=("gene",), dry_run=dry_run)` (`clinvar_draft.py:726`) and
`append_rows(..., "studies.csv", ..., group_by=("rsid",), ...)` (`clinvar_draft.py:743`), so rows land
in their gene's (resp. rsID's) block rather than at the end (`clinvar_draft.py:19-22`).
`test_clinvar_draft.py:119` asserts each gene occupies one contiguous block, then
`again.added == 0 and again.already_present > 0` with byte-identical file contents.

The open-work reports are scoped to the **file**, not the run: `_placeholder_rows`
(`clinvar_draft.py:233-263`) reads back every row whose column is still the placeholder, and
`_open_stubs` (`clinvar_draft.py:266-300`) unions that with `report.added` so a dry run on a fresh
directory still answers (`clinvar_draft.py:273-277`). Pinned by `test_clinvar_draft.py:935` (a second
run reprints the worklist) and `:1036` (a dry run writes nothing and still yields it).

### 8.4 `clinpgx_draft.py` — the ClinPGx snapshot → `pharm_variants.csv`

**What it drafts.** `PharmVariantRow` only (`clinpgx_draft.py:223-254`): `rsid`, `gene`, `genotype`,
`drug`, `phenotype_category`, `annotation_id`, `evidence_level`, and a `conclusion` taken **verbatim**
from the snapshot's `annotation_text` with a synthesized fallback (`clinpgx_draft.py:249-253`).
`chrom`/`start`/`ref` are deliberately not filled — the snapshot carries no coordinate, and a
coordinate authored here would be compared by `resolution._verify` against the table that supplied it
(`clinpgx_draft.py:8-14`). One annotation naming several drugs becomes one row per drug
(`clinpgx_draft.py:219`); several genes in one cell cannot, because `gene` is outside the dedup key
(`clinpgx_draft.py:25-32`).

**Skip guard — RESTATED and narrower than the model.** `clinpgx_draft.py:199-202`:

```python
rsid = (record.get("rsid") or "").strip()
if not rsid:
    skipped_unidentified += 1
    continue
```

`PharmVariantRow.REQUIRED_ANY_OF` is `(frozenset({"rsid"}), frozenset({"chrom", "start"}))`
(`schema/src/just_dna_format/pgx.py:540-543`), so the model would accept a coordinate-only row. The
narrowing is argued in the docstring (`clinpgx_draft.py:8-14`) as a consequence of what the source
publishes, not as the model's rule. Three further restated guards, each against the format's grammar
rather than a model: `_authored_genotype` (`clinpgx_draft.py:107`), `_symbolic_types`
(`clinpgx_draft.py:148`) and the `_TWO_BASE` regex (`clinpgx_draft.py:58`). Note the `--gene` filter
runs **first** (`clinpgx_draft.py:194-197`) so every skip counter is scoped to the requested genes.

**`SourceRow`.** Yes — `CLINPGX_TERMS.row("annotation", declared_use=..., dataset=release.get("dataset"),
license_text=license_text)` (`clinpgx_draft.py:418-429`), key `("clinpgx", "annotation")`, then
`stamp_draft_digest` (`clinpgx_draft.py:434`). It is the only provider that pins `license_sha256` to
the terms text it read out of the snapshot (`clinpgx_draft.py:410-417`), warning when
`SNAPSHOT_LICENSE_FILENAME` is absent or blank. Gated `if not dry_run:` (`clinpgx_draft.py:390`) after
an early return when no rows matched (`clinpgx_draft.py:386-387`). Pinned by
`test_clinpgx_draft.py:347` (`assert (tmp_path / _LICENCE_CSV).is_file()`) and
`test_clinpgx_draft.py:408 test_the_licence_terms_are_pinned_to_the_text_that_governed_them`.
**No `withdraw_stale_dataset` call.**

**Placeholders.** None — *"Nothing is stubbed and nothing is invented"* (`clinpgx_draft.py:4-5`).

**Append-not-mutate.** `append_rows(spec_dir, "pharm_variants.csv", rows, dry_run=dry_run)`
(`clinpgx_draft.py:389`), no `group_by`, so rows land at the end. The key is all five parts —
`(variant_key, drug, genotype, phenotype_category, annotation_id)` — which is `natural_key`'s own answer
for this model (`clinpgx_draft.py:16-19`). `test_clinpgx_draft.py:333
test_drafting_the_real_snapshot_is_re_runnable_and_reloads` covers the re-run.

### 8.5 `civic_draft.py` — the CIViC snapshot → the `direction` axis

**What it drafts.** `VariantRow` as a `PartialRow` (`civic_draft.py:286-291`) and `StudyRow` as a
`PartialRow` with `stubbed=()` (`civic_draft.py:313-318`). `_variant_row`
(`civic_draft.py:267-285`) states `rsid`/`chrom`/`start`/`ref`/`alts`, `gene`, `direction`,
`state` ("risk" or "protective"), `phenotype`, `trait_efo_id` (a `DOID:` CURIE minted by `trait_curie`,
`civic_draft.py:237-254`) and a transcribed `conclusion`. The axis is `direction`, not `clin_sig`, and
the measurement behind that choice is in the docstring (`civic_draft.py:3-11`).

**Skip guard — DERIVED.** `identity_refused_by_model` (`civic_draft.py:204-224`) builds a probe
`VariantRow(**{"genotype": "A/A", "state": "risk", "conclusion": "identity probe", **cells})`
(`civic_draft.py:215-217`) and returns the model's own complaint. The docstring states the derivation
rule and names the live counterexample — CIViC variant 1770 carries a build, a `start` and a
`referenceBases` with no chromosome (`civic_draft.py:19-26`). Pinned by
`test_civic_draft.py:55 test_the_identity_guard_asks_the_model_rather_than_paraphrasing_its_rule`,
which asserts `identity_refused_by_model({"start": 10188305, "ref": "A"})` is not `None` and contains
`"chrom"`.

The derivation is **partly** restated all the same: `civic_draft.py:220` decides whether the exception
is an identity refusal by string-matching pydantic's rendered message —
`if "identifier" in message or "positional" in message or "chrom" in message:` — and re-raises
otherwise (see 8.10, defect candidate 5).

**`SourceRow`.** Yes, via `record_source_terms(consulted, "annotation", spec_dir, error=CivicDraftError,
declared_use=declared_use)` (`civic_draft.py:613-619`), where `consulted = [CIVIC_SOURCE] +
([CLINGEN_ALLELE_REGISTRY_TERMS.source] if consulted_registry else [])` (`civic_draft.py:612`). So the
keys are `("civic", "annotation")` and, only where a CAID lookup actually ran,
`("clingen_allele_registry", "annotation")`. Pinned by `test_civic_draft.py:183
test_the_pass_writes_its_source_row` and `test_civic_draft.py:343
test_the_registry_gets_its_own_source_row_only_where_it_was_consulted` (which asserts that `offline=True`
still records the registry, because `"offline still ASKS the client, which answers skipped_offline —
the source was consulted"`). It is the **only** provider that neither records `dataset` nor stamps a
draft digest nor withdraws a stale label — see 8.10, candidates 1 and 2.

**Placeholders.** `genotype`, always, on the variant row (`civic_draft.py:289`), because CIViC states
which way a variant runs and never which genotype a module annotates (`civic_draft.py:260-263`). Study
rows carry no stub.

**Append-not-mutate.** `append_partial_rows(spec_dir, "variants.csv", variant_partials,
dry_run=dry_run)` (`civic_draft.py:597`) and the same for `studies.csv` (`civic_draft.py:600`) — with
**no `group_by`**, unlike `clinvar_draft` and `pubmind_draft`, so rows land at the end of the file.
`_MATCH_ON = ("rsid", "chrom", "start", "ref", "alts")` (`civic_draft.py:234`), a constant restatement
of `clinvar_draft._MATCH_ON` rather than an import (`pubmind_draft` imports it).

Contestation is decided over the whole admitted group before any per-row filter
(`civic_draft.py:487-496`), and a refutation is explicitly **not** a camp (`civic_draft.py:498-508`).

### 8.6 `mitomap_draft.py` — the MITOMAP-miss increment

**What it drafts.** `VariantRow` as a `PartialRow` (`mitomap_draft.py:291`) and `StudyRow` through
`append_rows` (`mitomap_draft.py:305`). `_cells` (`mitomap_draft.py:143-169`) states `chrom=CONTIG`,
`start`, `ref`, `alts`, `gene`, `phenotype`, `clin_sig`, and folds `state`/`pathogenic`/`benign` from
the shared `STATE_BY_CLIN_SIG`. Only the `rated_miss` bucket is written
(`mitomap_draft.py:274-281`); photocopies, unrated misses and unmintable rows are each refused for a
stated reason (`mitomap_draft.py:3-13`). `_study_rows` (`mitomap_draft.py:172-202`) keys studies on
the **position** (`chrom`, `start`, `ref`), not the allele.

**Skip guard — RESTATED, and not a requiredness rule at all.** `mitomap_draft.py:282`:

```python
missing = [name for name in ("chrom", "start", "ref", "alts", "clin_sig") if name not in cells]
```

`clin_sig` is not required by `VariantRow`, and the list is not derived from `REQUIRED_ANY_OF` or
`authoring_requirements`. The comment concedes it is unreachable from a well-formed snapshot and
guarded anyway, to avoid a raw `ValidationError` naming a column the author never wrote
(`mitomap_draft.py:283-286`).

**`SourceRow`.** Yes — `MITOMAP_TERMS.row("annotation", declared_use=..., dataset=result.dataset)`
(`mitomap_draft.py:322-326`), key `("mitomap", "annotation")`, deliberately naming the licensed source
rather than the derived `mitomap_miss` lane (`mitomap_draft.py:318-321`), with the ClinVar half of the
pin riding in `dataset`. Gated on `not dry_run and covered`, where `covered` is any outcome with
status `added` or `already_present` (`mitomap_draft.py:314-317`). `withdraw_stale_dataset` is called
when `result.added` (`mitomap_draft.py:328-334`). **No `stamp_draft_digest`.** Pinned by
`test_mitomap_draft.py:186 test_the_source_row_names_mitomap_and_the_dataset_names_both_parents` and
`test_mitomap_draft.py:200 test_a_run_that_drafted_nothing_writes_no_source_row`
(`assert not (spec_dir / "licensing.csv").exists()`).

**Placeholders.** `_STUBBED = ("genotype", "conclusion")` (`mitomap_draft.py:84`), plus `state` per row
where the fold has no answer: `stubbed = tuple(name for name in (*_STUBBED, "state") if name not in
cells)` (`mitomap_draft.py:290`). `genotype` is stubbed on a *haploid* contig here — the opposite of
`clinvar_draft` — and the reason is stated: MITOMAP's row is a claim about a literature corpus, whose
`homo`/`hetero` columns say a large share of these variants are reported only heteroplasmically, so
writing `genotype=<ALT>` would assert the homoplasmic reading (`mitomap_draft.py:15-24`). Pinned by
`test_mitomap_draft.py:100 test_the_genotype_and_conclusion_cells_are_stubbed_and_the_worklist_says_why`
and `:123 test_state_is_folded_where_the_shared_map_has_an_answer_and_stubbed_where_it_does_not`.

**Append-not-mutate.** `append_partial_rows(spec_dir, VARIANTS_CSV, partials, dry_run=dry_run)`
(`mitomap_draft.py:302`), no `group_by`. `_MATCH_ON = ("chrom", "start", "ref", "alts")`
(`mitomap_draft.py:79`) — no `rsid`, because MITOMAP publishes no rsID column, and an identity slot the
source never fills is not part of the key (`mitomap_draft.py:77-78`).
`test_mitomap_draft.py:159 test_a_second_run_adds_nothing`.

### 8.7 `pubmind_draft.py` — PubMind verdicts, attributed through ClinVar

**What it drafts.** `VariantRow` as a `PartialRow` only (`pubmind_draft.py:545-552`); no `studies.csv`,
and the run says so rather than leaving the module uncompilable in silence
(`pubmind_draft.py:592-597`). `_row_cells` (`pubmind_draft.py:343-382`) states the whole coordinate,
`gene` (only where ClinVar's attribution names exactly one requested gene), `clin_sig`, a transcribed
`conclusion`, plus the `sole_expressible_genotype` and `STATE_BY_CLIN_SIG` folds imported from
`clinvar_draft`. Five columns are refused as rules (`pubmind_draft.py:53-64`), including
`clinvar`/`pathogenic`/`benign`, because those are ClinVar flags by their own field descriptions.

The provider takes **two** snapshots: the PubMind one for the verdicts, and a ClinVar one read solely
for its per-record gene attribution (`pubmind_draft.py:450-453`, `gene_positions` at
`pubmind_draft.py:244`). A ClinVar ladder failure is translated into `PubMindDraftError` rather than
allowed to leak (`pubmind_draft.py:479-486`).

**Skip guard — none for identity; delegated to the model.** `_withhold_reason`
(`pubmind_draft.py:320-341`) is a content policy over five ordered reasons (`contested_key`,
`indel_derivation`, `clin_sig_not_selected`, `confidence_not_stated`, `below_min_confidence`), with the
contested test running first and over every record so a filter cannot pick the winner
(`pubmind_draft.py:323-326`). Identity is never checked here: the key is `(chrom, start, ref, alt)` by
construction, and anything the model refuses arrives as `report.invalid` through
`_refusal_summary` (`pubmind_draft.py:589`). That makes it the only provider with no restatement to
drift.

**`SourceRow`.** Yes — `PUBMIND_TERMS.row("annotation", declared_use=..., dataset=dataset)`
(`pubmind_draft.py:648-652`), key `("pubmind", "annotation")`, then unconditional `stamp_draft_digest`
(`pubmind_draft.py:656`) and `withdraw_stale_dataset` gated on `report.added`
(`pubmind_draft.py:657-659`). Whole block under `if not dry_run:` (`pubmind_draft.py:647`), after an
early return when `not partials` (`pubmind_draft.py:583-585`). Pinned by
`test_pubmind_draft.py:544 test_the_licence_row_records_null_on_every_term_and_the_draft_is_not_skipped`
and `test_pubmind_draft.py:523`, which asserts `{"variants.csv", _LICENCE_CSV} <= set(before)`
(`test_pubmind_draft.py:531`) before the dry run.

**Placeholders.** `genotype` and `state`, derived from the cells exactly as on the ClinVar path:
`stubbed = tuple(column for column in ("genotype", "state") if column not in cells)`
(`pubmind_draft.py:534`).

**Append-not-mutate.** `append_partial_rows(spec_dir, "variants.csv", partials, group_by=("gene",),
dry_run=dry_run)` (`pubmind_draft.py:587`), matching on the imported `clinvar_draft._MATCH_ON`
(`pubmind_draft.py:551`) so a coordinate PubMind and ClinVar both speak about is one row rather than
two. The open-stub worklist is `_open_stubs`, imported rather than reimplemented
(`pubmind_draft.py:602-604`). `test_pubmind_draft.py:483` (second run reprints the worklist) and
`:523 test_a_dry_run_appends_nothing_at_all_and_still_answers_the_worklist`.

### 8.8 `strchive_draft.py` — the STRchive catalogue → `repeat_alleles.csv`

**What it drafts.** `RepeatAlleleRow` as a `PartialRow` (`strchive_draft.py:202`), and only the
identity half. `DRAFTED_COLUMNS = ("gene", "repeat_unit", "measure_kind", "trait_efo_id",
"unresolved")` (`strchive_draft.py:83`) and `WITHHELD_COLUMNS` is **derived** from it —
`frozenset(authored_field_names(RepeatAlleleRow)) - set(DRAFTED_COLUMNS) - set(_STUBBED)`
(`strchive_draft.py:88-90`) — so a column added to the model later is withheld by default
(`strchive_draft.py:85-87`). `measure_kind="repeat_count"` and `unresolved=False` are written out
rather than left to the field default, because `load_csv_rows` turns an empty cell into `None` while
keeping the key (`strchive_draft.py:194-197`). Bands are never drafted, with the measurement behind
that in the docstring (`strchive_draft.py:22-27`).

**Skip guard — DERIVED.** `_missing_required` (`strchive_draft.py:163-180`) reads
`authoring_requirements(REPEAT_ALLELES_CSV)` and subtracts `_STUBBED`, handling both `always` and the
`any_of` groups (`strchive_draft.py:176-179`). The docstring names the `pgx_draft` incident as the
reason (`strchive_draft.py:166-169`). Pinned by `test_strchive_draft.py:293
test_the_skip_guard_is_the_models_own_requiredness_rather_than_a_copy` as an **equality**:
`assert _missing_required({}) == expected`, `assert "conclusion" in requirements["always"], "the
stubbed column really is required"`, `assert _missing_required(dict.fromkeys(expected, "x")) == []`.

**`SourceRow`.** Yes — `STRCHIVE_TERMS.row("annotation", declared_use=..., dataset=result.dataset)`
(`strchive_draft.py:298-302`), key `("strchive", "annotation")`, gated on `not dry_run and covered`
where `covered` is any `added`/`already_present` outcome (`strchive_draft.py:294-297`), plus
`withdraw_stale_dataset` when `result.drafted` (`strchive_draft.py:309-316`). **No
`stamp_draft_digest`.** Pinned by `test_strchive_draft.py:327
test_the_provider_writes_its_source_row_with_the_release_it_read` and negatively by
`test_strchive_draft.py:366 test_a_run_that_covered_nothing_writes_no_licence_row`:
`assert resolve_sidecar(spec, SOURCES_CSV) is None` and `assert sorted(p.name for p in spec.iterdir())
== []`.

**Placeholders.** `_STUBBED = ("conclusion",)` (`strchive_draft.py:78`) — the catalogue has a disease
description for the locus, which is a different claim at a different grain (`strchive_draft.py:74-77`).
Pinned by `test_strchive_draft.py:278 test_the_drafted_table_cannot_compile_until_a_human_has_finished_it`,
which asserts `REPEAT_ALLELES_CSV in DRAFTABLE` and then
`assert errors and any("conclusion" in message for message in errors), errors` (`test_strchive_draft.py:290`).

**Append-not-mutate.** `append_partial_rows(spec_dir, REPEAT_ALLELES_CSV, partials, dry_run=dry_run)`
(`strchive_draft.py:282`), no `group_by`. `_MATCH_ON = ("gene", "repeat_unit")`
(`strchive_draft.py:72`), with `trait_efo_id` deliberately **out** of it even though the bin-group key
includes it — an author may legitimately clear the trait, and a re-draft would then append the locus
twice (`strchive_draft.py:69-71`). `test_strchive_draft.py:205` (a second run appends nothing and
rewrites no cell), `:219` (a re-draft after the human filled the bands still matches),
`:349 test_a_dry_run_writes_no_file_at_all` — *"A caller asking for a dry run is asking for no files —
the licence row included"* — asserting `sorted(p.name for p in spec.iterdir()) == []`.

### 8.9 Shared behaviour

**The `DRAFTABLE` registry is walked, not hand-kept.** `draft.py:92-99` builds it from `_TABLE_KINDS`
and `sidecar_spellings`; the only literal members are `variants.csv`, `studies.csv` and
`OVERRIDES_CSV`, each with a recorded reason (`draft.py:80-91`). The enricher reads it in two places
outside drafting — `identifiers.py:748` and `litvar.py:482` — both explicitly *"derived from
`DRAFTABLE` rather than restated"* (`identifiers.py:731-739`, `litvar.py:476`). Within `enricher/tests/`
the pin is `test_strchive_draft.py:286` (`assert REPEAT_ALLELES_CSV in DRAFTABLE`); whether the map
itself carries an equality-over-a-walk test was not examined here — it would live in the compiler's
own suite, outside this section's read set.

**`match_on` semantics.** A `PartialRow`'s natural key runs through a placeholder column, so sameness is
decided on the columns that *are* filled (`draft.py:505-508`). The covered set is built from
`partials[0].match_on` and compared against every signature (`draft.py:604-607`), which is why a batch
must share one tuple — `append_partial_rows` raises outright otherwise
(`draft.py:594-600`): *"every PartialRow in one batch must share a match_on, because sameness is decided
against a single covered-set"*. Both signature sides `.strip()` and treat an absent cell as the empty
string (`draft.py:605`, `:612`). The five shipped tuples:

| provider | `match_on` | where |
| --- | --- | --- |
| `clinvar_draft` | `("rsid", "chrom", "start", "ref", "alts")` | `clinvar_draft.py:171` |
| `pubmind_draft` | the same tuple, **imported** | `pubmind_draft.py:77`, used at `:551` |
| `civic_draft` (variants) | `("rsid", "chrom", "start", "ref", "alts")`, restated | `civic_draft.py:234` |
| `civic_draft` (studies) | `("rsid", "pmid")` | `civic_draft.py:317` |
| `mitomap_draft` | `("chrom", "start", "ref", "alts")` | `mitomap_draft.py:79` |
| `strchive_draft` | `("gene", "repeat_unit")` | `strchive_draft.py:72` |

`pgx_draft` and `clinpgx_draft` use `append_rows` and therefore `natural_key`, not `match_on`.

**Placement.** Only `clinvar_draft` (`group_by=("gene",)` at `:726`, `("rsid",)` at `:743`) and
`pubmind_draft` (`("gene",)` at `:587`) delegate placement. The other five append at the end. Row
position is always the tool's choice — `place_rows` (`draft.py:672-699`) — never the caller's.

**`--dry-run`.** `append_rows` (`draft.py:448-449`) and `append_partial_rows`
(`draft.py:633-634`) return `written=False` before any write, and every provider gates its
`merge_sources_file` / `record_source_terms` / `stamp_draft_digest` / `withdraw_stale_dataset` block on
`not dry_run`. Verified empirically for `civic_draft` in this worktree: a dry run reported 16 rows
added and left the spec directory holding only `module_spec.yaml`. One thing still runs under
`--dry-run` on the CIViC path: `ClingenAlleleClient.resolve` and `SequenceProxy.subsequence`
(`civic_draft.py:522-532`, `:554`), so a dry run may still perform network lookups. Nothing asserts
otherwise and nothing is written to the module, so this is a property, not a violation.

**`--use` and the declared-use gate.** `cli.py:216-231` normalizes the flag through
`match_vocab(value, VALID_DECLARED_USE)`, so the CLI cannot teach a spelling the authored cell would
reject. `check_declared_use` (`licensing.py:942-976`) is three-outcome: **raise** `LicenseRefusal` for
`commercial` against a no-sale source, **skip** (a reason string) for `unstated` against one *or* for
any source whose `commercial_use` is `None`, **`None`** to proceed. Which providers call it, and what
each source's terms make it answer:

| provider | calls `check_declared_use`? | source terms | behaviour at `--use unstated` |
| --- | --- | --- | --- |
| `pgx_draft` | yes, `:282` | `CPIC_TERMS`, `commercial_use=False` (`licensing.py:139,146`) | **SKIPS**, `result.skipped=True`, nothing fetched |
| `clinpgx_draft` | yes, `:377` | `CLINPGX_TERMS`, `commercial_use=False` (`licensing.py:126,133`) | **SKIPS**, snapshot not read |
| `clinvar_draft` | yes, `:650` | `CLINVAR_TERMS`, `commercial_use=True` (`licensing.py:217,227`) | proceeds |
| `mitomap_draft` | yes, `:241`, and **raises** on a non-`None` answer | `MITOMAP_TERMS`, `commercial_use=True` (`licensing.py:720,736`) | proceeds; the refusal arm is `# pragma: no cover - unreachable while the terms stay permissive` |
| `strchive_draft` | yes, `:238`, same raise-on-refusal shape | `STRCHIVE_TERMS`, `commercial_use=True` (`licensing.py:687,698`) | proceeds |
| `pubmind_draft` | **no** | `PUBMIND_TERMS`, `commercial_use=None` (`licensing.py:402,418`) | proceeds, with a warning |
| `civic_draft` | **no** | `CIVIC_TERMS`, `commercial_use=True` (`licensing.py:463,476`) | proceeds |

`pubmind_draft` skipping the gate is deliberate and argued (`pubmind_draft.py:44-51`): the gate is on
*fetching*, nothing here fetches (there is no `ensure_pubmind_snapshot`), and refusing to read a
snapshot the operator built would make `pubmind build`'s own output unconsumable. The unknown terms are
instead reported in the source's own words (`pubmind_draft.py:490-496`) and the licence row records
null on every axis — pinned by `test_pubmind_licensing.py:51
test_every_licence_axis_is_null_because_none_of_them_could_be_established` and
`test_pubmind_licensing.py:76 test_the_acquisition_gate_skips_rather_than_refusing_or_permitting`.
`pgx_draft`'s two arms are pinned by `test_pgx_draft.py:208` (commercial ⇒ `LicenseRefusal`, `assert
fetched == []`) and `:229` (unstated ⇒ `skipped.skipped and skipped.added == 0`);
`clinpgx_draft`'s by `test_clinpgx_draft.py:320` and `:326`.

**The `SourceRow` write.** `merge_sources_file` (`licensing.py:1056-1075`) is read-merge-write and
**never-clobber**, so a curator's hand-written terms survive a re-run. Two escapes exist from that, and
both only ever remove: `withdraw_stale_dataset` (`licensing.py:1078-1114`) blanks a `dataset` this
run's rows did not come from (never re-labels — one column cannot name two releases), and
`stamp_draft_digest` (`provenance.py:158-188`) re-labels `draft_digest`, which has no such problem
because it describes the table as it now stands.

**`provenance.py` — the draft digest.** `DRAFT_PROJECTIONS` (`provenance.py:88-127`) maps a source to
`(table, identity, checked)` for the four sources that both draft a column and later cross-check it:
`clinvar` → `variants.csv` / `clin_sig`, `cpic` → `allele_function.csv` / `function_status`, `clinpgx`
→ `pharm_variants.csv` / `evidence_level`, `pubmind` → `variants.csv` / `clin_sig`. `draft_digest`
(`provenance.py:130-155`) hashes the sorted `(identity ‖ checked)` projection of the **raw CSV cells**,
never loaded models, because the same function must run at draft time when the table is full of
`<<REPLACE>>` that `reject_template_placeholders` refuses to load (`provenance.py:24-31`). `pubmind`'s
identity is the one that is *not* the drafter's `match_on` — it drops `rsid`, because the provider never
writes one (`provenance.py:115-121`). `drafted_unchanged` (`provenance.py:191-216`) is tri-state:
`None` nothing established, `False` a checked value moved *or the table is now gone*, `True` unchanged.
Pinned by `test_draft_provenance.py:75` (raw cells survive an unfilled stub), `:87` (filling the stub
leaves the digest alone, editing the call moves it) and `:108` (order-independent but identity-bound).

**Placeholder guard placement.** `AuthoredModel._guard_raw_input` (`base.py:722-728`) runs
`reject_template_placeholders` first, before `reject_misplaced`/`reject_compiler_filled`/
`reject_reserved`, so a stub row is diagnosed as a half-written template rather than as a reserved-name
error. `SourceRow` is **not** an `AuthoredModel` and carries its own copy
(`schema/src/just_dna_format/sources.py:114-117`), added because a module with `source=<<REPLACE>>`
compiled green under `--strict` and published `"sources": ["<<REPLACE>>"]` inside the block its own
signature is computed over (`sources.py:96-105`). `_placeholder_paths` (`vocab.py:1002-1017`) recurses
into nested blocks and lists so a scaffolded `module:` block cannot slip through.

### 8.10 Defect candidates

1. **Three providers define "this run covered something" differently, and CIViC's definition lets a
   zero-row draft write a `SourceRow`.** `strchive_draft.py:288-296` spells it as *"at least one locus
   is in the module's table because of this provider — added now, or added by an earlier run and
   recognised as `already_present`"*, and gates on that (`strchive_draft.py:297`); `mitomap_draft.py`
   computes the same predicate (`:314-317`). `civic_draft.py:608` gates on `if not dry_run:` alone —
   its own comment defines the threshold as *"never reached the snapshot"* (`civic_draft.py:604-607`),
   so the code matches that reading, but the line inside the block still says *"one that contributed
   nothing writes none"* (`civic_draft.py:609-610`) beside logic that only applies it to the registry.
   **Reproduced in this worktree**: `draft_panel_from_civic(spec, ["NOTAGENE"], snapshot=...)` returned
   `candidates=0, added=0` and still wrote `licensing.csv` carrying a `civic` row — the exact case
   `test_strchive_draft.py:366 test_a_run_that_covered_nothing_writes_no_licence_row` refuses on the
   STRchive path. `test_civic_draft.py:191` only covers the *no snapshot at all* case.
2. **`civic_draft` computes `dataset` and discards it.** `civic_dataset_label` is called at
   `civic_draft.py:475`, carried on `result.dataset`, and embedded in every drafted row's `conclusion`
   prose (`civic_draft.py:283`) — but `record_source_terms` (`licensing.py:908-939`) builds its rows as
   `t.row(layer, declared_use=declared_use)` (`licensing.py:939`) and passes no `dataset`.
   **Reproduced**: label `civic_01-Aug-2026`, `result.dataset == "civic_01-Aug-2026"`, licence row
   `dataset=''`. Consequences: no `withdraw_stale_dataset` is possible (there is nothing to withdraw),
   and `manifest.sources` cannot say which CIViC release these rows came from. Every other provider
   that drafts from a dated snapshot records it.
3. **A restated skip guard that is not merely a copy but a different rule.** `mitomap_draft.py:282`
   hand-lists `("chrom", "start", "ref", "alts", "clin_sig")` where the model's rule is
   `VariantRow.REQUIRED_ANY_OF` + `_validate_identification` (`spec.py:556-559`, `:1044-1062`) and
   `clin_sig` is not a requirement at all. `clinvar_draft._identity_cells` (`:150-165`) is *stricter*
   than the model (demands `ref` and `alt` for the coordinate branch). `clinpgx_draft.py:199` is
   *narrower* (rsID only, where the model accepts a coordinate). `pgx_draft.py:107` is an exact copy —
   pinned differentially by `test_pgx_draft.py:339`, which is the mitigation the other three lack.
   Only `civic_draft` (`:204-224`) and `strchive_draft` (`:163-180`) ask the model.
4. **`civic_draft`'s derived guard consumes pydantic's rendered message as an API.**
   `civic_draft.py:218-222` catches a bare `Exception`, then `if "identifier" in message or
   "positional" in message or "chrom" in message:` returns the refusal — **and re-raises otherwise**
   (`civic_draft.py:222`). The three substrings come from `_validate_identification`'s error strings
   (`spec.py:1052`, `:1057`, `:1061`). A reworded model error turns a `withheld` count into an
   unhandled traceback mid-draft, which is the exact failure the function exists to prevent.
5. **No `withdraw_stale_dataset` in `pgx_draft` or `clinpgx_draft`.** Both call the never-clobber
   `merge_sources_file` with a `dataset=` (`pgx_draft.py:521-531`, `clinpgx_draft.py:418-429`), so a
   module widened from a newer snapshot keeps the older label — the false claim `clinvar_draft.py:844-849`
   describes and repairs on its own path. `civic_draft` has the same gap for the different reason in
   candidate 2.
6. **`DRAFT_PROJECTIONS`' guard is a literal-against-literal, not an equality over a walked set.**
   `test_draft_provenance.py:66`: `assert set(DRAFT_PROJECTIONS) == {"clinvar", "cpic", "clinpgx",
   "pubmind"}`. The docstring calls it *"The one hand-kept thing here, so it is guarded rather than
   trusted"* (`test_draft_provenance.py:60`) and claims it *"asserts the set matches the providers that
   actually exist"* (`provenance.py:81-82`) — but the right-hand side is a second hand-kept copy, not a
   walk over the drafting modules. Two lists agreeing is not the registry idiom
   `strchive_draft.py:88-90`, `civic_draft.py:71`, `pubmind_draft.py:125` and `identifiers.py:748` all use.
7. **`mitomap_draft`'s withheld vocabulary is an inline literal and folds an unknown member into a
   definite one.** `mitomap_draft.py:234-236` builds the dict from a bare tuple where `civic_draft.py:71`,
   `pubmind_draft.py:125` and `strchive_draft.py:132` each name a `*_WITHHELD_REASONS` constant. Worse,
   `mitomap_draft.py:275` is `result.withheld[bucket if bucket in result.withheld else "unmintable"] += 1`
   — a new snapshot bucket is silently counted as `unmintable` rather than surfacing, and
   `accounts_for_every_candidate` still balances.
8. **The CPIC drafter's `SourceRow` write is unpinned.** No test under `enricher/tests/` references
   `sources.csv`/`licensing.csv` in connection with `draft_gene` (grep over `test_pgx_draft.py` and
   `test_draft_declared_build.py` returns nothing). The code does write the row
   (`pgx_draft.py:521-531`); nothing would fail if it stopped. Contrast the negative pins that exist
   for strchive (`test_strchive_draft.py:366`), mitomap (`test_mitomap_draft.py:200`) and clinvar
   (`test_clinvar_draft.py:172`).
9. **Minor — `civic_draft` restates `_MATCH_ON` where `pubmind_draft` imports it.**
    `civic_draft.py:234` duplicates `clinvar_draft.py:171` character for character, while
    `pubmind_draft.py:77` imports the same private name. Two copies of an identity tuple that must stay
    equal for the two providers to dedupe against one another.
10. **Minor — a strchive-drafted `repeat_alleles.csv` carries no `unresolved` sentinel row.**
    `_partial` writes `unresolved=False` per locus (`strchive_draft.py:196`) and nothing emits the
    sentinel, which `stub_template` emits for a binning kind precisely so the author does not *"meet
    that rule as a compile error about a row they never wrote"* (`draft.py:293-297`). It is not a
    compile error — `compiler.py:3557-3568` only refuses *two* sentinels per key group — but
    `hints.py:826-835` reports the absence as a warning: *"no unresolved sentinel row: a consumer with
    no measurement would match nothing."*

**Not defects, checked:** no `--dry-run` path writes (verified empirically for civic; asserted by
`test_pgx_draft.py:201`, `test_clinvar_draft.py:172`, `test_strchive_draft.py:349`,
`test_pubmind_draft.py:523`). `pgx_draft` writing its row on an all-`already_present` re-run is
intended: the gate is `if not dry_run and reports:` (`pgx_draft.py:508`), and a re-run's rows are still
in the module because of CPIC.

### 8.11 Undetermined from code

- **Why `civic`, `mitomap` and `strchive` are outside `DRAFT_PROJECTIONS`.** Each drafts a judgement
  column (`direction`/`state` for CIViC, `clin_sig` for MITOMAP, the trait for STRchive) that some
  check elsewhere may later compare. Nothing in `provenance.py` or the providers states whether no
  such check exists, or whether the entry is simply owed. Note that adding a `stamp_draft_digest`
  call without a projection entry would be inert: `draft_digest` returns `None` for a source
  `DRAFT_PROJECTIONS` does not carry (`provenance.py:137-139`), and `stamp_draft_digest` then returns
  early on `recorded.draft_digest == digest` (`provenance.py:184-185`). The projection is the thing
  that is undetermined, not the call site.
- **Whether `civic_draft` and `pubmind_draft` skipping `check_declared_use` are the same decision.**
  PubMind's is argued in full (`pubmind_draft.py:44-51`). CIViC's is not argued anywhere in
  `civic_draft.py`; the nearest statement is in the *publish* command's docstring
  (`cli.py:2676-2679`), which explains why CC0 needs no permission established and why the ClinGen
  registry's answers stay out of a published snapshot — but says nothing about the draft-time gate.
  Undetermined from code whether the omission is reasoned or an oversight; note that the registry is
  the one source `check_declared_use` would *skip* on (`commercial_use=None`,
  `licensing.py:447-459`), and `civic_draft` consults it at draft time
  (`civic_draft.py:554`) while recording its row (`civic_draft.py:612`).
- **Whether `mitomap_draft`'s and `strchive_draft`'s raise-on-refusal shape
  (`mitomap_draft.py:241-242`, `strchive_draft.py:238-239`) is intended to stay a raise** if either
  source's terms ever change, rather than the skip every other caller returns. Both are marked
  `# pragma: no cover - unreachable while the terms stay permissive`; neither says what should happen
  if they stop being.
- **Whether `clinvar_draft` and `pubmind_draft` writing a licence row when every partial was
  `invalid`** is intended. Both early-return on `if not partials:` (`clinvar_draft.py:723`,
  `pubmind_draft.py:583`), which is *before* `PartialRow.validation_errors` runs inside
  `append_partial_rows` — so a batch whose every row the model rejects still reaches
  `merge_sources_file` (`clinvar_draft.py:838`, `pubmind_draft.py:648`). Not reproduced; no test
  covers the shape.
## 9. The publisher / upload surface, and the snapshot layout

Five modules own this chapter. `upload.py` (878 lines) is the write half — module publish, snapshot
publish, the retirement/prune machinery — and it is the only module in the tier that deletes anything
remote. `download.py` (605) is the read half. `locations.py` (775) owns the layout both agree on.
`transaction.py` (368) is unrelated to HuggingFace: it is the durability contract for a long
`enrich()` run. `provenance.py` (216) is unrelated to both, and the brief's framing of it is wrong —
see § 9.6.

Two publish shapes share one create-or-update pathway, `ensure_repo` (`upload.py:166-175`), which is
`create_repo(..., exist_ok=True)` over an authenticated `HfApi` — so create and update are one code
path and only one `HfApi` is constructed per publish (`upload.py:169-171`).

`_hf_api` (`upload.py:135-163`) calls `load_env()` *before* `get_token()` (`upload.py:156-157`),
because `get_token()` reads the real environment and `~/.cache/huggingface/token` and neither is a
`.env` (`upload.py:138-144`). `huggingface_hub` is a guarded lazy import throughout
(`upload.py:149-155`, `download.py:229-235`, `download.py:556-562`) — the one sanctioned exception to
the no-inline-imports rule.

### 9.1 `upload` — module publishing

`just-dna-enricher upload <module_dir>` (CLI at `cli.py:1512-1574`) → `upload_module`
(`upload.py:509-579`) → `plan_upload` (`upload.py:383-451`).

#### Two destinations, two commits

`plan_upload` resolves `data/<name>` as `flat` (`upload.py:442`) and, when the manifest states a
readable SemVer version, `data/<name>/v<version>` **nested inside it** (`upload.py:448`) — not a
sibling, because the flat path is the one deployed readers are pointed at (`upload.py:390-394`).

`upload_module` writes both with two `upload_folder` calls (`upload.py:561-568`, `upload.py:571-578`),
flat first. The docstring is explicit that this is two commits and not one: *"`upload_folder` commits
per call, so a reader can briefly see the flat path refreshed while the versioned copy is not there
yet"* (`upload.py:522-528`). `test_upload_module_calls_hf_api` pins the order —

```python
assert [c.kwargs["path_in_repo"] for c in mock_api.upload_folder.call_args_list] == [
    "data/lipidmetabolism",
    "data/lipidmetabolism/v0.4.0",
]
```
(`test_upload.py:381-384`)

— and the default commit messages that distinguish them: `["Add coronary module", "Add coronary
module v1.0.0"]` (`test_upload.py:425-428`). A module with no readable version gets the flat path
alone, never a `vNone` directory (`upload.py:448`, `test_upload.py:401-412`).

`_module_version` (`upload.py:303-336`) returns `(version, reason_it_is_unknown)` with exactly one
member set, for four distinguishable reasons: no manifest (`:325`), unparseable JSON (`:329`), no
`identity.version` (`:333`), a value that is not MAJOR.MINOR.PATCH (`:335`). It reads the one field
out of the JSON rather than through `read_manifest`, so an unrelated model defect cannot withhold a
legible version (`upload.py:310-316`, pinned by `test_an_unrelated_manifest_defect_does_not_withhold_a_legible_version`,
`test_upload.py:344`).

#### What `--force` guards

`--force` guards **only the versioned path**. `upload_module` computes `_versioned_digest_conflict`
unless `force` (`upload.py:550`) and raises `PublishCollisionError` when the remote
`data/<name>/v<version>/manifest.json` states a *different* `artifact.digest` (`upload.py:551-560`).
The flat path is deliberately ungated: *"it means latest, so overwriting it is what it is for"*
(`upload.py:533-534`; `test_the_flat_path_is_deliberately_not_guarded`, `test_upload.py:669`).

The comparator has four outcomes (`upload.py:458-473`): no versioned path → `None`; the path is
absent → `None` (`:485-486`); present and digests agree → `None`, which must proceed because a re-run
is the documented recovery when the second commit fails (`:461-465`); present and different → the
collision. An **unreadable** remote manifest proceeds with a warning (`:494-501`), stated as a
decision rather than an oversight: *"Nothing established a collision, so nothing may assert one; the
house algebra withholds"* (`upload.py:468-473`). Pinned by
`test_an_unreadable_published_manifest_proceeds_with_a_warning` (`test_upload.py:681`) and
`test_the_same_artifact_republished_is_not_a_collision` (`test_upload.py:614`).

It reads the remote `manifest.json` rather than comparing per-file hashes, because `artifact.digest`
is a Merkle root over exactly the attested files (`upload.py:475-477`).

#### What `--dry-run` reads

For `upload`, nothing remote. The CLI's dry-run branch calls `plan_upload` only and returns
(`cli.py:1527-1540`); `--dry-run`'s own help text says *"Show what would be uploaded without
contacting HuggingFace"* (`cli.py:1502`). It prints both destinations, or the reason there is no
versioned one (`cli.py:1529-1539`), pinned by `test_the_dry_run_names_both_destinations`
(`test_upload.py:431`) and `test_the_dry_run_says_why_there_is_no_versioned_copy`
(`test_upload.py:442`, asserting `"states no identity.version" in printed` and `"/vNone" not in
printed`).

The *snapshot* `--dry-run` is the opposite and says so: *"Show what would be uploaded. Reads the
repo's file list; uploads nothing"* (`cli.py:1706`), and it runs
`check_publish_orphans_no_sidecar(plan)` so a rehearsal refuses where the publish would
(`cli.py:1717-1726`, and again in `_publish_rebuilt` at `cli.py:2197-2204`). The asymmetry is a
defect candidate — § 9.7(e).

#### The allowlist — derived, and from where

**Derived, not hand-kept**, at `upload.py:66-71`:

```python
_ALLOW_PATTERNS = [
    *ARTIFACT_PARQUETS,
    _MANIFEST_FILENAME,
    *(f"logo.{ext}" for ext in sorted(LOGO_EXTENSIONS)),
    *README_CANDIDATES,
]
```

All four sources are registries owned elsewhere: `ARTIFACT_PARQUETS` and `LEAD_PARQUETS` from
`just_dna_compiler.compiler`, `LOGO_EXTENSIONS` and `README_CANDIDATES` from
`just_dna_format.manifest` (`upload.py:30-32`). Measured in the installed environment:
`len(ARTIFACT_PARQUETS) == 23`, `len(LEAD_PARQUETS) == 10`, `LOGO_EXTENSIONS == {jpeg, jpg, png}`,
`len(README_CANDIDATES) == 6`, so `len(_ALLOW_PATTERNS) == 33`.

It was hand-kept twice and both are recorded in the comment above it. The parquet third was the
triple `weights`/`annotations`/`studies`, written when a module *meant* a SNP core, and measured on
2026-08-17 against the sixteen reference examples: *"seven could not be published at all and eight
published an artifact whose `manifest.artifact.files` attests, by name and sha256, six kinds of
parquet this allowlist dropped"* (`upload.py:58-65`). The logo third was the hand-spelled pair
`logo.png`/`logo.jpg` while `LOGO_EXTENSIONS` is `{png, jpg, jpeg}` and `_collect_logo` picks the
first in `sorted()` order — so `jpeg` wins and was the one spelling dropped (`upload.py:52-56`).
`test_every_logo_the_compiler_can_ship_is_a_logo_the_publisher_uploads` asserts set equality, not a
floor:

```python
assert {p for p in _ALLOW_PATTERNS if p.startswith("logo.")} == {f"logo.{ext}" for ext in LOGO_EXTENSIONS}
```
(`test_upload.py:152`; the docstring records *"a floor passes on the pre-fix tree, since two of the
three were already listed"*, `test_upload.py:149-150`.)

#### The three refusals

`plan_upload` raises three positive rules, most specific first (`upload.py:400-414`):

1. **Everything the artifact attests must be carried.** `_attested_parquets` (`upload.py:359-380`)
   reads `manifest.artifact.files`; anything attested and not in `present` raises `FileNotFoundError`
   (`upload.py:419-426`). Self-check as much as module check: *"it fires if this publisher's allowlist
   ever falls behind the compiler's output list again"* (`upload.py:408-409`).
   `test_the_plan_carries_every_file_the_artifact_attests` proves the consequence end to end by
   copying only `plan.files` into a fresh directory and recomputing:
   `assert build_artifact(received, list(ARTIFACT_PARQUETS)).digest == manifest.artifact.digest`
   (`test_upload.py:244`).
2. **`weights.parquet` never travels alone** — `_EXPECTED_WITH_WEIGHTS = ("annotations.parquet",
   "studies.parquet")` (`upload.py:76`), checked only in the weights-led case (`upload.py:427-435`),
   deliberately scoped so a `pharm_variants`-led module is not refused (`upload.py:72-75`).
3. **At least one lead table** — `if not any(f in LEAD_PARQUETS for f in present)` (`upload.py:436-441`).

An absent or unparseable manifest makes `_attested_parquets` return `None` and rule 1 withhold
(`upload.py:419`), which is what keeps a manifest-less directory publishable
(`test_an_unreadable_manifest_withholds_rather_than_refusing`, `test_upload.py:260`).

### 9.2 Snapshot publishing — the shared path

Every `<group> publish` command funnels into `plan_reference_snapshot` (`upload.py:589-642`) and
`publish_reference_snapshot` (`upload.py:788-878`). Call sites for the pair, all lazy imports:
`cli.py:1713-1714` (clinvar), `:2180-2181` (`_publish_rebuilt`, the `cache rebuild --publish` path),
`:2287`, `:2321`, `:2684-2685`, `:3096-3097`, `:4187`, `:4428`, `:4745`, `:5213`.

#### The plan

Two branches. A **payload** snapshot (`payload=` names one root file — STRchive's
`STRchive-loci.json`, ACMG's `acmg_sf.csv`) is `[payload] + the present members of
SNAPSHOT_ROOT_FILENAMES` (`upload.py:608-619`). A **parquet** snapshot is
`data/*.parquet` sorted by name (`upload.py:620-627`), then each sidecar directory's parquets
(`upload.py:630-633`), then the present members of `SNAPSHOT_ROOT_FILENAMES` (`upload.py:639-641`).
Both branches walk the same registry rather than restating a pair (`upload.py:614-616`,
`upload.py:634-638`). Empty `data/` and a missing payload are refused with the same claim
(`upload.py:610-613`, `upload.py:622-626`; `test_a_payload_snapshot_with_nothing_built_is_refused_like_an_empty_parquet_one`,
`test_upload.py:759`).

#### The publish

`publish_reference_snapshot` plans, ensures the repo, runs the orphan guard (`upload.py:803-805`),
lists the remote once more for declared retirements (`upload.py:810-817`), then sends **two
`upload_folder` calls**: payload first, description (`release.json`) second
(`upload.py:846-877`). One uploader at every size since RM199 — `upload_large_folder` emits a
`FutureWarning` in `huggingface_hub` 1.x and the size branch is gone (`upload.py:826-839`). The
allowlist is `plan.files` minus `release.json` (`upload.py:846`, `:861`), *derived from the plan it
just computed* so a dry run is a promise (`upload.py:858-860`, `@publisher-allowlist-derived`).

```python
assert RELEASE_FILENAME not in payload["allow_patterns"], "the description went out too early"
assert description["allow_patterns"] == [RELEASE_FILENAME]
...
assert payload["allow_patterns"] + description["allow_patterns"] == plan.files
```
(`test_upload.py:523-531`)

and, over a snapshot carrying a sidecar *and* a licence:

```python
sent = [f for c in mock_api.upload_folder.call_args_list for f in c.kwargs["allow_patterns"]]
assert sent == promised
assert set(promised) >= {"citations/citations.parquet", "LICENSE.txt"}
assert sent[-1] == RELEASE_FILENAME, "the description must be the last thing sent"
```
(`test_the_dry_run_promises_exactly_what_the_upload_sends`, `test_upload.py:739-742`)

`test_a_publish_never_reaches_for_the_deprecated_large_uploader` runs both 1 KiB and 6 GiB payloads
and asserts `api.upload_large_folder.assert_not_called()` plus `len(api.upload_folder.call_args_list)
== 2, "payload then description"` (`test_upload.py:794-805`).

#### `release.json`

**There is no shared writer.** All **14** `*_build.py` modules write one, in two shapes. Ten define
their own `_write_release_json` — `clinvar_build:578`, `constraint_build:322`, `civic_build:1083`,
`mitomap_build:401`, `mitomap_miss_build:409`, `strchive_build:165`, `mane_build` (called at `:691`),
`drug_labels_build:264`, `pubmind_build`, `alphagenome_avi_build:664`. Four write it inline through
`atomic_write_text`: `clinpgx_build.py:316`, `cpic_build.py:307`, `acmg_build.py:292`,
`pharmvar_build.py:181`. Two fields are common to every one read: `built_at` (`now_utc_iso()`) and
`builder_version` — e.g. `clinvar_build.py:593-594`, `mitomap_miss_build.py:429-430`. `built_at` is
deliberately outside the parquet so the parquet stays byte-reproducible
(`clinvar_build.py:586-587`). Thirteen of the fourteen take the filename from
`locations.RELEASE_FILENAME`; `constraint_build` spells the literal `"release.json"` at
`constraint_build.py:343` instead — a name the layout registry owns, restated in one builder.

ClinVar's full set (`clinvar_build.py:588-595`): `clinvar_file_date`, `source_url`, `source_sha256`,
`record_count`, `built_at`, `builder_version`. All are written through `atomic_write_text` with
`sort_keys=True` (`clinvar_build.py:597`).

The file describes **every** part of a snapshot, which is why the citations builder merges a block
rather than rewriting: `_merge_release_block` (`clinvar_build.py:432-458`) is read-modify-write, and
an unparseable existing file is left alone and reported rather than overwritten
(`clinvar_build.py:444-452`).

**A derived lane's `release.json` pins its parents.** `mitomap_miss` writes
`"parents": result.parents` (`mitomap_miss_build.py:418`), built as

```python
result.parents = {
    "mitomap": {**parent_pin(mitomap_dir), "path": str(mitomap_dir.resolve())},
    "clinvar": {**parent_pin(clinvar_dir), "path": str(clinvar_dir.resolve())},
}
```
(`mitomap_miss_build.py:335-338`)

`parent_pin` (`mitomap_miss_build.py:139-157`) copies the parent's `release.json` keys named by
`PIN_KEYS = ("dataset", "clinvar_file_date", "source_sha256", "record_count", "rows")`
(`mitomap_miss_build.py:89-95`) — read generically so a parent that starts publishing a new
identifying key is pinned on it without this module learning the parent's schema
(`mitomap_miss_build.py:86-88`). `{}` is stored as a real answer: *"recording an empty pin says so,
where omitting the parent entirely would read as 'this child has one parent'"*
(`mitomap_miss_build.py:142-144`). `stale_parents` (`:160-188`) reports `parent -> (pinned, current)`
for parents that **moved** and deliberately says nothing about a parent that is **gone**
(`:164-167`). `miss_dataset_label` (`:203-217`) is both parents or `None` — half an identity is an
unknown, not a shorter identity (`:206-211`). Beyond the parents the same file carries every count
the join made (`mitomap_miss_build.py:417-431`), on the stated ground that a number computed and
dropped is one every reader recomputes differently (`:412-415`).

#### The `DEFAULT_*_REPO_ID` constants

Enumerated programmatically (`[n for n in dir(upload) if n.startswith('DEFAULT_') and
n.endswith('_REPO_ID')]`): **10**, defined at `upload.py:97-132`.

| constant | value | line |
| --- | --- | --- |
| `DEFAULT_REPO_ID` | `just-dna-seq/annotators` | `upload.py:97` |
| `DEFAULT_CLINVAR_REPO_ID` | `just-dna-seq/clinvar` | `upload.py:98` |
| `DEFAULT_CONSTRAINT_REPO_ID` | `just-dna-seq/gnomad_constraint` | `upload.py:99` |
| `DEFAULT_CLINPGX_REPO_ID` | `just-dna-seq/clinpgx` | `upload.py:104` |
| `DEFAULT_CPIC_REPO_ID` | `just-dna-seq/cpic` | `upload.py:105` |
| `DEFAULT_CIVIC_REPO_ID` | `just-dna-seq/civic` | `upload.py:109` |
| `DEFAULT_STRCHIVE_REPO_ID` | `just-dna-seq/strchive` | `upload.py:114` |
| `DEFAULT_DRUG_LABELS_REPO_ID` | `just-dna-seq/clinpgx_drug_labels` | `upload.py:119` |
| `DEFAULT_MITOMAP_REPO_ID` | `just-dna-seq/mitomap` | `upload.py:125` |
| `DEFAULT_ALPHAGENOME_AVI_REPO_ID` | `just-dna-seq/alphagenome_avi` | `upload.py:132` |

One is the module collection; nine are snapshot lanes. **PharmVar has no entry on purpose** — *"its
bulk data is pulled under a personal, non-transferable key and no recorded axis covers passing that
on, so an unestablished permission stays a refusal"* (`upload.py:100-103`). PubMind and the derived
`mitomap_miss` have none either (`upload.py:120-124` for the latter: it pins two parents a puller
would not hold). Ensembl is pullable but is cut by `just-dna-pipelines`, so it has a download prefix
(`download.py:43`) and no publish constant.

### 9.3 The snapshot layout — what `locations.py` owns

The layout section opens with the reason it is centralized: *"Four parties have to agree on those
names — the builder writes them, the publisher uploads them, the provisioner fetches them, the reader
queries them — and every disagreement so far has been silent"* (`locations.py:31-39`).
`read_release` (`locations.py:261-278`) is named the sixth party (`:264`).

A snapshot's payload lives in a `data/` subdirectory — `SNAPSHOT_DATA_DIRNAME = "data"`
(`locations.py:42`) — except for the two payload-shaped lanes that hold no parquet at all
(`ACMG_SNAPSHOT_FILENAME = "acmg_sf.csv"`, `STRCHIVE_CATALOGUE_FILENAME = "STRchive-loci.json"`,
`locations.py:128-129`).

**Sidecars are siblings of `data/`, never inside it.** `CITATIONS_DIRNAME = "citations"`
(`locations.py:73`) with the reason attached: the readers build their view from `data/*.parquet`, so
a two-column citations file dropped in there unions with the 17-column variant parquet and every
query breaks (`locations.py:69-72`). `SNAPSHOT_SIDECAR_DIRNAMES: tuple[str, ...] =
(CITATIONS_DIRNAME,)` — **1 member** (`locations.py:78`).

**Root files** are the third category: `RELEASE_FILENAME = "release.json"` (`locations.py:84`),
`SNAPSHOT_LICENSE_FILENAME = "LICENSE.txt"` (`locations.py:92`), `ALPHAGENOME_KNOTS_FILENAME =
"avi_knots.parquet"` (`locations.py:106`), collected into `SNAPSHOT_ROOT_FILENAMES` — **3 members**,
in publish order with `RELEASE_FILENAME` last on purpose (`locations.py:122-126`, reason at
`:117-121`). The tuple exists because the hardcoded pair failed twice
(`locations.py:111-116`).

`REPRO_DIRNAME = "data/repro"` (`locations.py:51`) and `CACHES_DIRNAME = "data/caches"`
(`locations.py:55`). `repro_out(name)` returns `Path(REPRO_DIRNAME) / name`
(`locations.py:58-66`) — measured: `repro_out("demo") == data/repro/demo`. It exists because nine
`--out` defaults were bare relative names that dropped a snapshot directory beside `pyproject.toml`
(`locations.py:44-50`). An AST walk over the CLI enforces it:
`test_every_out_default_is_derived_rather_than_written_as_a_literal` (`test_build_out_defaults.py:52`)
accepts only `repro_out(...)` or `Path(<NAME>)` (`:65-75`), and the exemption list is asserted as an
equality, `assert required == INPUT_SHAPED_OUT` (`test_build_out_defaults.py:96`).
`test_repro_out_lands_under_the_ignored_data_tree` reads the real `.gitignore`
(`test_build_out_defaults.py:99-106`).

#### Cache variables and subdirs

Enumerated programmatically: **15** `*_CACHE_VAR` constants (`locations.py:244-258`) plus
`CACHE_BASE_VAR = "JUST_DNA_PIPELINES_CACHE_DIR"` (`locations.py:243`), the one variable no lane
owns; and **15** `*_SUBDIR` constants.

| lane | `*_CACHE_VAR` | `*_SUBDIR` |
| --- | --- | --- |
| ensembl | `JUST_DNA_ENSEMBL_CACHE` (`:244`) | `ensembl_variations` (`:131`) |
| clinvar | `JUST_DNA_CLINVAR_CACHE` (`:245`) | `clinvar` (`:136`) |
| constraint | `JUST_DNA_GNOMAD_CONSTRAINT_CACHE` (`:246`) | `gnomad_constraint` (`:140`) |
| clinpgx | `JUST_DNA_CLINPGX_CACHE` (`:247`) | `clinpgx` (`:155`) |
| cpic | `JUST_DNA_CPIC_CACHE` (`:248`) | `cpic` (`:156`) |
| pharmvar | `JUST_DNA_PHARMVAR_CACHE` (`:249`) | `pharmvar` (`:162`) |
| pubmind | `JUST_DNA_PUBMIND_CACHE` (`:250`) | `pubmind` (`:170`) |
| civic | `JUST_DNA_CIVIC_CACHE` (`:251`) | `civic` (`:176`) |
| acmg | `JUST_DNA_ACMG_CACHE` (`:252`) | `acmg_sf` (`:189`) |
| strchive | `JUST_DNA_STRCHIVE_CACHE` (`:253`) | `strchive` (`:194`) |
| drug_labels | `JUST_DNA_DRUG_LABELS_CACHE` (`:254`) | `drug_labels` (`:201`) |
| mane | `JUST_DNA_MANE_CACHE` (`:255`) | `mane` (`:209`) |
| mitomap | `JUST_DNA_MITOMAP_CACHE` (`:256`) | `mitomap` (`:216`) |
| mitomap_miss | `JUST_DNA_MITOMAP_MISS_CACHE` (`:257`) | `mitomap_miss` (`:224`) |
| alphagenome_avi | `JUST_DNA_ALPHAGENOME_AVI_CACHE` (`:258`) | `alphagenome_avi` (`:232`) |

`DUCKDB_NAME = "ensembl_variations.duckdb"` (`locations.py:132`) is the one non-`_SUBDIR` name in the
block. The set is asserted as an equality over a walked module, not a list:

```python
declared = {value for value in vars(locations).values()
            if isinstance(value, str) and value.startswith("JUST_DNA_")}
claimed = {lane.env_var for lane in CACHE_LANES}
assert declared == claimed | {locations.CACHE_BASE_VAR}
assert len(claimed) == len(CACHE_LANES), "two lanes share a variable"
```
(`test_the_variables_the_module_reads_are_exactly_the_ones_the_lanes_claim`,
`test_cache_lanes.py:861-870`, which also asserts `lane.env_var is getattr(locations,
f"{lane.name.upper()}_CACHE_VAR")`.)

`missing_credential_reason` (`locations.py:291-316`) distinguishes **absent** from **exported empty**
because `load_env` uses `override=False`, making `export FOO=` strictly stronger than `unset FOO`
(`locations.py:292-304`).

#### The provisioning side of the layout

`_provision_snapshot` (`download.py:184-346`) mirrors it: `data/` (`:204`), each sidecar directory
(`:289-312`), then root files (`:334-344`). A non-empty cache with no truncated parquet is trusted
without touching the network (`:220-222`). `_parquet_footer_ok` (`:171-181`) reads 4 bytes from each
end. Files outside the lane's glob are **reported, never removed** — *"this is someone's cache
directory, and a file we did not put there is not ours to delete"* (`download.py:209-219`).
`SNAPSHOT_FILE_GLOBS` (`download.py:116-126`) is the shared registry of what each lane's `data/`
consists of: **9 entries**, read by both the provisioner and `cache prune` (`download.py:105-115`).

### 9.4 The orphan / retirement guard

#### `LayoutShift` and `LAYOUT_SHIFTS`

`LayoutShift` (`upload.py:178-212`) is a frozen dataclass of `repo_id`, `retires` (one repo-relative
name, *"never a glob: a migration that deletes a pattern is a prune wearing a declaration"*,
`upload.py:205-207`), `introduces` (a repo-relative glob), and `reason`. The stated rule: *"if the new
file is absent from the repo and the old one is present, upload the new and delete the old. The
condition is a predicate over the remote, so it fires exactly once per repo and is a no-op forever
after"* (`upload.py:183-187`). *"This is the only deletion a publish performs"* (`upload.py:188-189`).

`LAYOUT_SHIFTS` holds **1** entry (`upload.py:226-237`): `just-dna-seq/clinvar`, retiring
`data/clinvar.parquet` in favour of `data/clinvar-chr*.parquet`. It is already past its own condition
and stays literal rather than widened — *"the 159 MB remnant is `cache prune`'s to remove. Loosening
the predicate to 'retire the old whenever the new is present' would sweep it"* (`upload.py:219-225`).

`layout_shifts_to_apply(repo_files, repo_id)` (`upload.py:240-257`) skips a shift whose repo differs
(`:250-251`), whose `retires` is absent from the remote (`:252-253`), or where any remote name matches
`introduces` (`:254-255`). `test_a_declared_shift_fires_only_on_a_repo_that_has_not_moved` walks all
four states (`test_declared_retirement_and_prune.py:46-56`);
`test_applying_a_shift_makes_its_own_predicate_false` asserts the fires-once property as a property
rather than a call count (`:64-73`); `test_every_declared_shift_names_a_repo_this_tier_publishes_to`
asserts `{shift.repo_id for shift in LAYOUT_SHIFTS} <= published` over `CACHE_LANES` (`:76-79`).

At publish time the retirement rides the payload commit as `delete_patterns`, not a second write:
`delete_patterns=[shift.retires for shift in due] or None` (`upload.py:856`), with
`api.delete_files.assert_not_called()  # the deletion rides the upload; it is not a second write`
(`test_declared_retirement_and_prune.py:126`) and `assert "delete_patterns" not in description, "the
description commit deletes nothing"` (`test_upload.py:829`).

#### `plan_prune` / `prune_repo`

A file is a prune candidate on exactly two grounds (`upload.py:718-765`):

1. it is under `data/`, ends `.parquet`, and the lane's own glob excludes it (`upload.py:744-754`);
2. a `LayoutShift` declares it retired, which is the only way a retired file is nameable for the four
   lanes whose glob is `*.parquet` (`upload.py:755-764`, reason at `:722-726`). A declaration wins the
   reason slot because it says *when* and *why* (`upload.py:758-759`).

**Never touched:** *"`README.md`, `.gitattributes`, `release.json`, `LICENSE.txt`, and any sidecar
directory"* (`upload.py:728-730`, repeated in the CLI help at `cli.py:2009-2012`).
`test_prune_names_the_glob_excluded_and_the_declared_and_leaves_the_rest` feeds a tree containing all
of those and asserts `[c.path for c in plan.candidates] == [_OLD, "data/stray-export.parquet"]`
(`test_declared_retirement_and_prune.py:213`). `plan_prune` reads only — `prune_repo`
(`upload.py:768-785`) takes a `PrunePlan`, *"rather than a repo id"* (`:773`), and the CLI does
nothing without `--yes` (`cli.py:2059-2064`).

#### The guard that stops a publish orphaning bytes

`check_publish_orphans_no_sidecar` (`upload.py:645-696`) **asks the remote tree, not the remote
description.** The code is `remote = list(api.list_repo_files(...))` (`upload.py:675`) and then, per
sidecar directory this publish does not carry, `orphaned = sorted(f for f in remote if
f.startswith(f"{sidecar}/") and f.endswith(".parquet"))` (`upload.py:687`) → `OrphanedSidecarError`
(`upload.py:690-696`).

The docstring states why: *"The block is a **description** of the bytes and the bytes are what a
puller gets, so the description is the half that can already be missing — which is exactly the state
`just-dna-seq/clinvar` was found in on 2026-09-03: the citations parquet present, the block gone. A
guard reading the block would have passed the second bad publish as happily as the first"*
(`upload.py:648-652`). Pinned directly:

```python
def test_the_guard_reads_the_tree_and_not_the_release_block() -> None:
    """…"""  # docstring at :184-188, elided
    api = MagicMock()
    api.list_repo_files.return_value = ["citations/citations.parquet"]  # no block anywhere
    plan = SnapshotPlan(repo_id=DEFAULT_CLINVAR_REPO_ID, files=["release.json"])
    with pytest.raises(OrphanedSidecarError):
        check_publish_orphans_no_sidecar(plan, api)
```
(`test_declared_retirement_and_prune.py:183-193`)

Two scope rules: the guard returns immediately when the plan carries no `release.json`, because such
a publish overwrites no provenance (`upload.py:663-664`;
`test_a_publish_carrying_no_release_json_overwrites_no_provenance`, `:168-173`), and a failed listing
is logged and passed, because a repo that does not exist is a first publish rather than an orphan
(`upload.py:676-682`; `test_a_repo_nobody_has_published_to_is_a_first_publish_not_an_orphan`,
`:176-180`). A dry run passes no `api` and gets an anonymous reader, since listing a public repo needs
no token (`upload.py:658-661`, `:665-673`).

The other direction of the same rule is the two-commit order: `release.json` goes last so *"a publish
that lands the description and then fails leaves a snapshot that reads as provisioned and is not"*
(`upload.py:841-845`).

### 9.5 `transaction.py` — "enrich is a transaction"

The module docstring states the trade it refuses: checkpointing the table as it goes *"trades away a
property somebody relies on, that a refused `strict` run leaves the module exactly as it was"*
(`transaction.py:4-6`). Instead: *"What goes to disk as the run proceeds is a **journal of what the
network answered**, staged beside the target and never read by anything but the next run; the table
itself is still written once, at the gate, by a writer that renames into place"*
(`transaction.py:6-9`).

#### Staging

`staging_dir_for(target)` returns `target.parent / f".{target.name}{STAGING_SUFFIX}"` with
`STAGING_SUFFIX = ".staging"` (`transaction.py:47`, `:94-103`). The sibling relationship is the
**correctness condition**, not a convenience: `os.replace` is atomic only within one filesystem and
`shutil.move` across a partition degrades to copy-then-delete (`transaction.py:14-17`, `:45-46`).

```python
for target in (Path("/a/b/resolution.csv"), Path("derived/resolution.csv"), tmp_path / "r.csv"):
    assert staging_dir_for(target).parent == target.parent
...
assert staged.parent == _table(spec).parent
```
(`test_the_staging_directory_is_a_sibling_of_the_table_it_stages`, `test_enrich_transaction.py:248-255`)

`ResolutionJournal` (`transaction.py:106-263`) stages `JOURNAL_NAME = "answers.csv"`
(`transaction.py:50`) with columns `("rsid", "source", "genome_build", "rederive", "chrom", "start",
"ref", "alts")` (`transaction.py:143`). It records **raw link answers**, not assembled
`ResolutionRow`s, so everything downstream is recomputed and a resumed run reproduces the table an
uninterrupted run produces even when flags changed (`transaction.py:110-115`). Only *positive*
answers are journaled — *"a failed request is unchecked rather than absent, and freezing that into the
journal would turn a transient outage into a permanent negative"* (`transaction.py:117-119`). Every
`record` rewrites the whole file through `layout.atomic_writer` (`transaction.py:235-253`), because
appending needs a reader that tolerates a torn tail (`transaction.py:121-123`).

`resume()` (`transaction.py:153-219`) skips two kinds of staged row loudly: rows under a **different
genome build** (`:170-172`, warning at `:200-208`) and, when this run is a `--rederive`, rows a
gap-filling run wrote (`:176-179`, info at `:191-199`) — *"a re-derivation resumes only another
re-derivation"* (`transaction.py:129-134`).

#### The commit gate, and what a refused strict run leaves

```python
def test_a_strict_refusal_commits_nothing_and_leaves_the_staged_work_behind(tmp_path: Path) -> None:
    ...
    before = _table(spec).read_bytes()

    with pytest.raises(EnrichmentError, match="strict enrichment"):
        _run(spec, tmp_path, mode="strict", resolver=_StubResolver())

    assert _table(spec).read_bytes() == before
    assert not (spec / "verification.json").exists()
    assert not (spec / _LICENCE_CSV).exists()
    # Staged, though — a refusal is not a reason to throw the answers away, and the next run resumes.
    assert staging_dir_for(_table(spec)).exists()
```
(`test_enrich_transaction.py:176-197`. The docstring notes the pre-existing table is what makes it
discriminate: *"'the file is absent' would pass for a run that wrote nothing **and** for one that
wrote and then failed to clean up"*, `:179-181`.)

The kill case asserts the same three things plus the recovery
(`test_a_kill_over_an_existing_table_leaves_that_table_byte_identical`,
`test_enrich_transaction.py:200-237`): `assert _table(spec).read_bytes() == before`, `assert not (spec
/ "verification.json").exists()`, `assert staging_dir_for(_table(spec)).exists()` (`:226-228`), and
then `assert _table(spec).read_bytes() == _table(whole).read_bytes()` (`:237`) — bytes rather than a
row count, because *"a rewritten table with the same number of rows is still a table this run had no
right to commit"* (`:213-214`).

`test_keep_staging_removes_the_staged_answers_when_it_is_off_and_keeps_them_when_it_is_on`
(`:258-278`) runs **both** values of the knob and asserts the committed run writes all three artifacts
— *"which is what makes the refusal test's assertions about their absence discriminate rather than
pass on a file nothing ever creates"* (`:270-271`).

#### The lock

`spec_lock` (`transaction.py:266-313`) takes a non-blocking `flock` on the **directory's own
descriptor** — no lockfile, because *"a lockfile left behind by exactly the kill this transaction
exists for would block every subsequent run"* (`transaction.py:275-278`). `LockStatus.held` is
`True` or `None`, never `False`: *"a run that finds the lock taken does not proceed unlocked, it
refuses"* (`transaction.py:82-87`). Three refusal/warning texts are module constants
(`LOCK_HELD_MESSAGE` `:54-59`, `LOCK_TARGET_MESSAGE` `:64-67`, `LOCK_UNAVAILABLE_MESSAGE` `:72-77`);
two are pinned verbatim — `assert LOCK_HELD_MESSAGE.format(spec_dir=spec) == str(caught.value)`
(`test_enrich_transaction.py:384`) and the same shape for `LOCK_TARGET_MESSAGE`
(`test_enrich_transaction.py:706`). `LOCK_UNAVAILABLE_MESSAGE` is a log warning and no test asserts
its text. `_acquire` (`:316-326`) turns `BlockingIOError` into the caller's error type and any other
`OSError` into a documented degradation. Tests: `:368`, `:392`, `:406`, `:428`.

#### `SubjectProgress`

`(done, total)` over **subjects** (`transaction.py:329-368`), because the incident was an idle timeout
at 1800 s and the subject count is the only unit known before the first call (`:331-337`).
Monotonicity is structural — `done` is the size of a set that only grows (`:339-340`) — and the set is
updated *before* the callback is consulted so `settled` means the same thing with or without a
listener (`:360-363`; `test_the_settled_count_grows_whether_or_not_a_callback_is_listening`, `:709`).

#### The atomic-sidecar machinery

`atomic_write_text` / `atomic_writer` live in the **schema** tier
(`schema/src/just_dna_format/layout.py:196-212`, `:215-249`): a `NamedTemporaryFile(delete=False)` in
the target's own parent, `flush` + `os.fsync` + `os.replace`, and a `finally` that unlinks the temp on
every path that does not reach the replace (`layout.py:230-249`). The reason is in the docstring:
*"The naive `write_text` truncates in place, so a process killed between the truncate and the last
byte leaves a file that is **syntactically valid and simply short**"* (`layout.py:199-201`).

`test_atomic_sidecar_writes.py` pins it three ways.

An AST walk over nine named writers (`SIDECAR_WRITERS`, `test_atomic_sidecar_writes.py:32-42`),
asserted per writer rather than as a floor — *"a floor ('at least three are atomic') is satisfied by
exactly the state the report found"* (`:78-79`):

```python
assert not truncating, (
    f"{module_name}.{func_name} truncates its target in place: {truncating}. "
    "Route it through just_dna_format.layout.atomic_writer / atomic_write_text — a killed run "
    "must leave the previous table, never a short one (S66)."
)
```
(`:83-87`, followed by `assert "atomic_write" in source` at `:90` so a third shape cannot slip past.)

A demonstration of the failure on both paths against one file
(`test_naive_write_truncates_and_atomic_write_does_not`, `:96-130`):

```python
assert list(csv.DictReader(damaged.splitlines())) == [{"variant_key": "1:100:A:G", "rsid": "rs1"}]
...
assert target.read_text(encoding="utf-8") == complete, (
    "an interrupted atomic write must leave the previous table byte-for-byte"
)
assert list(tmp_path.glob(".*tmp*")) == [], "the partial temp file must not survive the failure"
```
(`:119`, `:127-130`)

And a walk over every `*_build.py` in the package
(`test_no_builder_writes_a_text_file_in_place`, `:178-201`), whose docstring records the measurement:
*"The nine spec-dir writers above were guarded; the fourteen builders were not, and ten of them wrote
`release.json` (and `acmg_build` its whole snapshot CSV) with `write_text` / `open("w")`"*
(`:180-182`). The byte-equality guard `test_atomic_writer_emits_the_same_bytes_as_open` (`:133-155`)
asserts `atomic.read_bytes() == naive.read_bytes()` and `b"\r\n" in atomic.read_bytes()`, because the
sidecars are hashed inputs and `csv.writer`'s CRLF is what the attestation's newline normalization was
built around (`:136-138`).

### 9.6 `provenance.py`

**It is not snapshot provenance.** `provenance.py` is *draft* provenance (RM73): telling a value still
copied from a source from one a human has edited (`provenance.py:1`). Snapshot provenance is
`release.json`, written per builder (§ 9.2). Nothing in `provenance.py` imports `locations`, `upload`
or `download`.

What it records: one sha256 per drafting source over `(identity cells, checked cell)` for every row of
the drafted table, sorted and hashed (`provenance.py:12-16`, computed at `:144-155` with `_UNIT =
"\x1f"` / `_RECORD = "\x1e"` as separators, `:58-59`). The projection is a **column, not a row**,
because a `clinvar_draft` module always has edited rows by construction — `genotype` is a placeholder
the human must fill — so a whole-row hash would never match (`provenance.py:18-22`). It reads raw CSV
cells via `csv.DictReader`, never loaded models, because the same function runs at draft time when
`variants.csv` is full of `<<REPLACE>>` and would not load at all (`provenance.py:24-31`).
Order-independent, missing columns rendered as `""` (`:33-36`, `:150`).

`DRAFT_PROJECTIONS` (`provenance.py:88-127`) has **4** entries — `clinvar`, `cpic`, `clinpgx`,
`pubmind` — each a `DraftProjection(table, identity, checked)` (`:62-74`). The header comment says
"Three entries" (`:79`) while the dict holds four; `pubmind` was added below with its own note
(`:115-126`). `clinpgx`'s identity is eight columns wide because the bare triple is a bug this package
has already made once (`:84-87`). `pubmind`'s identity omits `rsid` deliberately: it is never a cell
that provider writes (`:115-121`).

Where it is called from:

- **Stamped** by four drafting providers, unconditionally after a run that wrote anything
  (`provenance.py:172-174`): `clinvar_draft.py:852`, `pgx_draft.py:534` (CPIC),
  `clinpgx_draft.py:434`, `pubmind_draft.py:656` — each passing `(spec_dir, source, "annotation",
  error=<its own type>)`. `stamp_draft_digest` (`provenance.py:158-188`) exists because
  `merge_sources_file` is never-clobber, which is wrong for a machine-stamped cell that must track the
  table (`:161-166`); unlike `dataset` it **re-labels rather than withdraws** (`:168-171`).
- **Read** by two checks: `clinical.py:195` (`return drafted_unchanged(spec_dir, authority,
  list(sources)) is True`) and `pgx.py:106` / `clinpgx.py:248`.

`drafted_unchanged` (`provenance.py:191-216`) is tri-state — `None` nothing established, `False` a
checked value moved, `True` still the drafter's — and `True` alone is **not** grounds to skip: *"The
digest describes this module's table, not the source's release, so it is silent about currency"*
(`:200-203`). A recorded digest against a now-unreadable table returns `False`, not `None`, because
something was established and no longer holds (`:211-215`).

### 9.7 Defect candidates

**(a) A hand-kept file list beside the derivable one — the provisioner never fetches
`avi_knots.parquet`.** `SNAPSHOT_ROOT_FILENAMES` is the registry the publisher walks
(`upload.py:618`, `upload.py:639-641`) and has 3 members including `ALPHAGENOME_KNOTS_FILENAME`
(`locations.py:122-126`). `_provision_snapshot` iterates a **hardcoded pair** instead:

```python
for optional in (RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME):
```
(`download.py:334`)

`download.py` never imports `SNAPSHOT_ROOT_FILENAMES` or `ALPHAGENOME_KNOTS_FILENAME` (import block,
`download.py:21-37`), and `grep -rn 'avi_knots\|ALPHAGENOME_KNOTS_FILENAME\|SNAPSHOT_ROOT_FILENAMES'
enricher/src enricher/tests` returns no fetch site anywhere. Two docstrings assert the opposite:
*"`_provision_snapshot` fetches the root files from `SNAPSHOT_ROOT_FILENAMES` for every lane, so this
needs no special case"* (`download.py:94-96`) and *"That file travels because `SNAPSHOT_ROOT_FILENAMES`
names it, not because this function does"* (`download.py:497-498`). The chain is `cache pull` →
`ensure_alphagenome_avi_snapshot` (`download.py:486-511`) → `_provision_snapshot` → no knot table; and
`locations.py:100-102` says the file *"is not optional: the artifact deliberately does not store
`PHRED`, so without this file a puller holds scores they cannot rank and `alphagenome check` refuses
outright"*. The publish half **is** tested — `test_a_publish_carries_the_knot_table_and_not_only_the_scores`
(`test_alphagenome_avi_build.py:493-522`), whose own docstring names *"a publisher iterating a hardcoded
`(release.json, LICENSE.txt)` pair"* as the defect it prevents (`:498`). No test walks the registry on
the provisioner's side, which is the missing half. Not verified end to end here (no network, and the
test needs `tabix`).

**(b) A failed fetch that is not a no-op — `release.json` in the payload-snapshot path.** Every other
download in `download.py` stages through `.part`: parquet (`:274-280`), sidecars (`:304-312`), root
files (`:336-341`), the STRchive catalogue itself (`:570-582`). One does not:

```python
fs.get(f"{hf_repo}/{RELEASE_FILENAME}", str(cache_dir / RELEASE_FILENAME))
```
(`download.py:585`, in `_provision_root_file_snapshot`)

The hazard is recorded by the module itself at `download.py:326-333`: *"`HfFileSystem.get` creates the
local file before it discovers the remote path is missing, so fetching straight to the real name left
a 0-byte `LICENSE.txt` in the cache of every snapshot whose repo publishes none… The same staging also
stops a re-pull whose repo has since dropped the file from truncating a good local copy."* Measured
against the installed client (`huggingface_hub` 1.31.0,
`.venv/.../huggingface_hub/hf_file_system.py`): `outfile = open(lpath, "wb")` at **:1121** precedes
`expected_size = self.info(rpath, revision=revision)["size"]` at **:1126**, and the guard above it is
`elif self.isdir(rpath)` (**:1111**) whose `fsspec` implementation swallows `OSError` and returns
`False`. So a missing remote path truncates/creates the local file and then raises, leaving a 0-byte
`release.json` in a STRchive cache whose repo publishes none — where `read_release` degrades it to
`None` with a warning (`locations.py:273-277`) and `cache status` renders it as the
present-and-unreadable state rather than absent (`caches.py:1271`). Not reproduced against a live
repo; the mechanism is read off the client source, not observed. The reason nothing pins it is
visible in the test seam: `_FakeFS.get` raises `FileNotFoundError` **before** touching `local_path`
(`test_download.py:56-58`), so the fake cannot model create-then-fail, and
`test_a_repo_without_release_json_still_provisions` (`test_download.py:225`) passes on the staged path
for a reason the unstaged one does not share. A sibling test against
`_provision_root_file_snapshot` with a fake that creates before raising would demonstrate (b) offline;
not written here.

**(c) The orphan guard's roster is narrower than the layout it defends.**
`check_publish_orphans_no_sidecar` iterates only `SNAPSHOT_SIDECAR_DIRNAMES` — 1 member
(`upload.py:684`) — and keys on directory prefixes (`carried = {path.split("/", 1)[0] for path in
plan.files if "/" in path}`, `upload.py:683`). A **root** file in `SNAPSHOT_ROOT_FILENAMES` can be
orphaned by the identical mechanism: the remote holds `LICENSE.txt` or `avi_knots.parquet`, the local
snapshot does not, `plan_reference_snapshot` skips it (`upload.py:639-641`, present-only), and the
publish replaces `release.json` regardless. `test_declared_retirement_and_prune.py:145-193` covers
only the sidecar case; there is no root-file case. Whether this is in scope for RM185 is a design
question the code does not answer.

**(d) The module publish's allowlist is the constant, not the plan.** The snapshot path was repaired
to pass the plan it just computed (`upload.py:861`, `@publisher-allowlist-derived`, `upload.py:89-93`).
`upload_module` still passes `allow_patterns=_ALLOW_PATTERNS` on both calls (`upload.py:566`,
`upload.py:576`) while `plan.files` is `present` (`upload.py:417`). They agree today because `present`
is filtered from the same constant, so this is structural rather than an observed break — but it is the
unrepaired sibling of a repair the code has already made once, and the property is untested on this
path: `test_the_dry_run_promises_exactly_what_the_upload_sends` (`test_upload.py:717-742`) exercises
`publish_reference_snapshot` only. What `test_upload_module_calls_hf_api` asserts instead is that the
two module commits share one allowlist (`patterns = {tuple(c.kwargs["allow_patterns"]) …}; assert
len(patterns) == 1`, `test_upload.py:394-396`).

**(e) `upload --dry-run` rehearses a different operation from the publish.** The snapshot dry runs run
the remote check deliberately — *"A rehearsal that skips the check the real thing refuses on is a
different operation"* (`cli.py:1719-1721`, and `cli.py:2199-2201`). The module dry run does not: it
calls `plan_upload` and returns (`cli.py:1527-1540`), so it cannot see the RM88 collision
(`upload.py:550-560`) and will happily promise an upload the real command exits 1 on
(`cli.py:1550-1555`). It is stated as a design choice in the help text — *"without contacting
HuggingFace"* (`cli.py:1502`) — so the two dry-run semantics are deliberately different; whether that
is the right call is a design question, not a bug on its face.

**(f) No `--dry-run` in this surface writes.** Checked at every publish/upload dry-run branch:
`cli.py:1527-1540` (module, plans and prints), `:1717-1730`, `:2197-2204`, `:2289-2292`, `:2323-2326`,
`:2689-2694`, `:3101-3106`, `:4197-4200`, `:4438-4441`, `:4748-4751`, `:5230-5240` — all return before
`publish_reference_snapshot`. `cache prune` without `--yes` calls `plan_prune` only and prints
*"Nothing was deleted"* (`cli.py:2059-2064`) — **asserted nowhere**: there is no CLI-level prune test
(`grep -n 'prune' enricher/tests/test_cli_surface.py` is empty), and the adjacent
`test_an_empty_plan_touches_nothing` (`test_declared_retirement_and_prune.py:245-252`, the file's last
test) pins a different property, that an empty plan opens no write. The `--dry-run` flags at `cli.py:1035`, `:2569`,
`:3443`, `:3605`, `:4475`, `:5104` belong to *drafting* commands and thread the flag down into the
provider (`cli.py:1065`, `:5141`'s `write=not dry_run`), where it gates the append and the digest
restamp (`clinvar_draft.py:630`, `:726`, `:743`, `:835`); they are outside this section, and none was
examined further. No writing dry run was found in the publish/upload surface.

**(g) `.part` naming is inconsistent inside one function.** `download.py:274` uses
`local_path.with_suffix(".part")`, which **replaces** the extension — `clinvar-chr1.parquet` stages as
`clinvar-chr1.part` — while `download.py:336` and `:570` use `target.with_suffix(target.suffix +
".part")`, which appends: `release.json.part`. Both are correct as staging; the consequence is that a
stray parquet `.part` does not end in `.parquet` and so is invisible to the `data/*.parquet` globs
that judge a cache populated (`download.py:206`) — cosmetic, but the two spellings in one file are the
kind of skew this codebase names elsewhere.

### 9.8 Undetermined from code

- **Undetermined from code: whether the missing knot-table fetch in (a) has ever bitten.** No lane
  publish of `alphagenome_avi` is recorded in the tree I can read, and `ensure_alphagenome_avi_snapshot`
  cannot be exercised without the network.
- **Undetermined from code: whether the root-file orphan case (c) was considered and excluded.**
  `OrphanedSidecarError`'s docstring names the general shape — *"RM179 fixed the lane; this is the
  general shape, refused at the boundary where any lane could repeat it"* (`upload.py:272-273`) — but
  the implementation's roster is sidecar directories only, and nothing says whether root files were
  ruled in or out.
- **Undetermined from code: `plan_reference_snapshot`'s `payload` parameter has no registry.** The
  caller supplies it (`cli.py:4198` for STRchive, `cli.py:2195` keyed on `lane.name == "strchive"`),
  stated as deliberate — *"a lane knows the name of the file it builds"* (`upload.py:598-601`) — but
  ACMG is named in the same docstring as *"the shape's second member"* (`:599`) and has no publish
  command, so whether a second payload lane would be reached by `_publish_rebuilt`'s single-name test
  is not answerable from the code.
- **Undetermined from code: whether `_provision_root_file_snapshot`'s early return
  (`download.py:552-553`) can leave a permanently unlabelled cache.** The docstring says a snapshot
  that arrived without a `release.json` *"stays without one until it is re-provisioned from scratch"*
  (`:546-549`) — but with (b) in play a 0-byte `release.json` **is** present, so `_json_parses` on the
  payload short-circuits every later attempt to correct it. Whether that composition was intended is
  not stated.
- **Undetermined from code: the `DRAFT_PROJECTIONS` header count.** The comment says *"Three
  entries"* (`provenance.py:79`) and the dict has four (`:88-127`). It reads as documentation drift
  from the `pubmind` addition rather than a claim about behaviour, but nothing in the file says so.
- **Undetermined from code: the `_ALLOW_PATTERNS` / `plan.files` relationship in (d) under a future
  compiler.** Nothing asserts `set(plan.files) == set(f for f in _ALLOW_PATTERNS if present)` at the
  call site, so the agreement is a property of today's `plan_upload` body rather than a pinned
  invariant.
## 10. Everything else the package owns

### 10.1 `hint` — the read-only authoring surface

`lookup.py` (1028 lines). The network half of the authoring surface: `just_dna_compiler.hints`
inspects rows using nothing but the module's own bytes, and this module adds the facts that need a
reference, **in the same report shape** (`lookup.py:1-6`).

*"It writes nothing — not a file, not a cell."* Answers come back as `hints.Alteration`s with
`applied=False` and a `refusal` naming why the value is the author's to type (`:6-9`). The refusal has
a stated reason, not fastidiousness (`:11-19`): almost every fact here is later cross-examined by a
check that only works because the author wrote the value **independently** —
`resolution._verify` compares an authored coordinate, `sequences.verify_reference_alleles` an authored
`ref`, `literature._doi_conflicts` an authored DOI. *"Supplying the cell from the same oracle the
checker consults turns each into a tautology — and for an rsid-only row `_verify` does not run at
all, so the row would go from honestly unverified to apparently verified."*

Clients are injected and reused via a `LookupClients` holder, because each carries its own
`PacingGate` and a per-question client throws away both the pacing state and the connection pool
(`:21-24`). Five subcommands: `hint variant`, `hint citation`, `hint gene`, `hint trait`,
`hint recover` (the GRCh37→GRCh38 recovery, `grch37.py`). `--json` on three of them.

### 10.2 `litvar` — coverage reported at three tiers

`litvar.py` (982). The finding the pass exists to make: *"The tier a locus is answerable at is a
property of the locus, not of the source"* (`litvar.py:17-19`). An rsID has a **position** node
(`litvar@rs1800562##`) and **allele** nodes beside it named by ClinGen CAIDs
(`litvar@CA113795#rs1800562##`); a gene has a gene-level node and a tail of unnormalized text
mentions, and *"nothing here treats a mention as a variant"* (`:5-7`).

Nothing parses a LitVar id — the field count and meaning vary by tier, so the tier is read off the
source's own `flag_rsid_variant` / `flag_clingen_variant` / `flag_gene_variant` booleans and every id
is echoed back verbatim (`:9-15`).

Measured numbers the module records (2026-09-01, `:19-25`): BRAF rs113488022 — 32,095 papers on the
position node against three allele nodes of 31,276 / 99 / 41, leaving 801 (2.5 %) position-only;
APOE rs429358 — 3,945 on the position node and **328** on its single allele node, so 92 % of that
locus's literature is not allele-resolved.

**The stated negative result** (`:27-37`): on a source that *names* a variant without *identifying*
it, LitVar is the wrong instrument — CIViC 1955/2131 resolved by hand to four CAID-bearing candidate
alleles return **no node for any of the four**, and `VHL P71fs` returns exactly one node with 1 PMID
(19996202) which is an unrelated paper that happens to write "P71fs".

**It writes no `SourceRow`, and that is the rule rather than an omission** (`:52-56`): the pass
contributes no cell to any table, so `sources.csv` — which travels to the registry meaning *this
module uses this source* — gets nothing. `identifiers.py` is named as the precedent. NCBI's terms are
recorded as a **policy, not a licence** (`:42-50`): LitVar has no `maintenance_use` page of its own, so
its gating axes are unknown rather than permissive, and *"recording it as public domain by analogy
with ClinVar is exactly the move that rule forbids."*

### 10.3 The scope/roster machinery

Four separate "what is this pass about" rosters, each with its own guard test, and each derived
rather than restated:

| roster | for | guard |
| --- | --- | --- |
| gene roster | `gene-metrics`, `dosage`, `gene-validity` | `test_gene_roster_scope.py` — incl. `test_the_scope_is_the_roster_and_not_a_second_answer` (`:62`), and a table present in two places **refuses** rather than narrowing the scope (`:102`) |
| identifier roster | `check-identifiers` | `test_identifier_roster_scope.py:113 test_the_roster_is_derived_from_the_registry_and_not_a_literal`; `:144 test_derived_tables_are_outside_the_roster`; `:166 test_the_roster_type_separates_absent_from_unreadable` |
| GWAS subject set | `gwas` | `test_gwas_subject_scope.py:42 test_the_subject_set_is_the_collectors_and_not_a_second_loop` |
| PGx record scope | `pgx` | `test_pgx_record_scope.py` — a tautological leg beside an answering one still reaches the record (`:40`), and the sentence is byte-stable across leg order (`:73`) |

A common rule across all four: *a table that will not parse refuses rather than narrowing the scope*
(`test_gene_roster_scope.py:81`, `test_identifier_roster_scope.py:66`).

### 10.4 Sidecar path resolution is uniform

`test_sidecar_resolution_is_uniform.py:71 test_no_pass_joins_a_sidecar_filename_onto_spec_dir_by_hand`
is an AST guard: every pass must go through `licensing.sidecar_path(...)`, so a module that keeps its
derived tables in `derived/` is written back to the file that was read.
`:106 test_the_roster_covers_every_writable_sidecar` asserts the roster is complete.

### 10.5 Merge keys

`test_merge_keys.py` pins the published key of every derived table:
`:39` every published key column is a real column of the table it keys; `:58` a fallback is declared
only where the primary key can be absent; `:144 test_resolution_publishes_a_subject_rule_because_several_rows_share_its_key`
— `ResolutionRow._KEY_FIELDS` is a **subject** rule, not an equality rule, because one rsID
legitimately resolves to several loci and `enrich` replaces the group whole (S51); `:175` the key is
exercised against a real written sidecar.

### 10.6 Builder `--out` defaults

`test_build_out_defaults.py:52 test_every_out_default_is_derived_rather_than_written_as_a_literal`
walks the CLI's AST and refuses a literal path as a builder's `--out` default — every one must be
`locations.repro_out("<lane>")`. `:83` enumerates the input-shaped exemptions;
`:99 test_repro_out_lands_under_the_ignored_data_tree` pins where it writes.
`repro_out` is declared immutable for bugbear's B008 in the root `pyproject.toml`
(`extend-immutable-calls`), which is what lets the AST walk prove the property.

### 10.7 Credentials and `.env`

`locations.load_env()` is called **where a credential is read**, never as a side effect of an
unrelated call. Pinned by `test_cli_surface.py:176 test_the_ncbi_credential_is_loaded_where_it_is_read`,
whose docstring records the live effect: *"`EutilsSettings` read `os.environ` directly, so the key
reached it only as a side effect of some unrelated call resolving a cache path. The live effect was
silent and threefold: the rate gate stayed at 1 request / 3 s instead of 10 / s."* The test asserts
`eutils.EutilsSettings()`, `literature.CrossrefClient()` and `literature.PmcIdConverterClient()` each
call `load_env` — `assert len(calls) == 2, "the two polite-identification clients must each load `.env`"`.

`test_cli_surface.py:199 test_an_empty_key_still_means_no_key` and `test_dotenv_credentials.py` pin
the rest: an **exported empty** variable outranks a `.env` entry, and the diagnostic says so
(`locations.py:313`): *"${var} is set but EMPTY, and an empty exported variable outranks a `.env`: the
loader uses …"*. `test_locations.py:87 test_a_real_environment_variable_still_outranks_the_dotenv`.

Known credentials: `NCBI_API_KEY` (E-utilities rate gate), `PHARMVAR_API_KEY` (personal,
non-transferable), HuggingFace token for upload.

### 10.8 The Atlas proto pin (`atlas generate`)

`atlas_protos.py` (233) carries the pin rather than the files: `UPSTREAM_REPO =
"google-deepmind/alphagenome"` (`:43`), `UPSTREAM_COMMIT = "aa6fc8f6faadcb8c910fa2b85b57386fbd5c7b5d"`
(`:44`), `PROTOS = ("atlas_service.proto", "dna_model.proto", "tensor.proto")` (`:48`), plus
`grpc_service_config.json` and the Apache-2.0 licence text, each with a sha256 in `UPSTREAM_SHA256`
(`:74-87`). `fetch_protos` (`:133-163`) downloads from
`https://raw.githubusercontent.com/{repo}/{commit}/{path}` (`:122`), verifies the digest, and
**refuses rather than writes** on a mismatch: *"A commit id says what git had and a digest says what
arrived; they disagree, so nothing is written."* A file already on disk and matching its pin is left
alone, so a build is offline after the first run.

`generate` (`:170-…`) rewrites upstream's `import "alphagenome/protos/…"` lines onto a private
`_alphagenome_atlas_protos` package prefix (`STAGE_PREFIX`, `:108`), because otherwise the generated
package would literally be named `alphagenome` and shadow the real wheel for anyone who installs
both. `hatch_build.py` (`enricher/hatch_build.py:31-45`) runs `fetch_protos()` then `generate()` as a
hatchling build hook, and adds both trees as `artifacts` rather than `force_include` (they sit inside
the declared package, so force-including adds every file twice).

**This means `uv sync` from a checkout makes network requests.** See §12.

### 10.9 Other commands not covered elsewhere

- **`template <kind>`** — prints a header-only CSV for one authored table kind, generated from the
  live models (so it cannot drift from the schema).
- **`enrich-and-compile`** — `enrich`, then compile from the produced `resolution.csv` (offline,
  deterministic). Its flag set is a strict subset of `enrich`'s plus `--frequencies` and
  `--gene-metrics`; it does **not** expose `--vrs`, `--verify-*`, `--keep-par-twin`, `--rederive`,
  `--keep-staging` or `--pubmind-cache`.
- **`civic reproduce`** — downloads a dated CIViC release and builds it **twice**, then diffs, as a
  determinism probe; `--offline` skips the reference cross-check but the build and determinism checks
  still run.
- **`mitomap miss`** — the derived lane: MITOMAP minus ClinVar, pinning both parent digests.
- **`alphagenome expression`** — fills `expression_effects.csv` from the Atlas API (RM194/RM200).
  `--gene` is **required even with an explicit interval**, because the server-side gene filter is not
  optional; `--max-rows` (`DEFAULT_MAX_ROWS = 50_000`, `expression.py:120`) refuses rather than writing more (`expression.py:482-489`).
- **`clinvar citations`** — a separate command from `clinvar build` because ClinVar publishes
  citations separately from the VCF, and *"a drafted gene panel could not compile without this:
  `studies.csv` is mandatory and the VCF carries no PMIDs"*.
## 11. Undetermined from code

Places where reading the source and the tests did not settle the question. Each is a question, not a
claim.

**This list is not the whole of it.** §6.6, §7.7, §8 and §9 each end with their own undetermined
items, written by whoever read that surface: the client surface leaves five (the 4xx/5xx retry
predicate's intent, two missing pacing gates, the HuggingFace blanket `except`, and whether any path
into `enrich_expression` loads `.env` first), licensing leaves eleven (six of which are the *code's*
own stated open questions — AVI's redistribution reading, MANE's EMBL-EBI half, PubMind's data terms,
GWAS's deliberate `None`, the PGS floor measured over 250 of 6,982 scores, and the ClinGen Allele
Registry's soft-404 terms page), drafting leaves four and the publisher surface six. Counting them
together: **32 open questions**, of which six are questions the code itself records as open.

### U1 — "Enricher checks report and never repair" has no package-wide guard

Every check module asserts it in its own docstring (`sequences.py:13`, `clinical.py:14`, `acmg.py:404`,
`strchive.py:581`, `drug_labels.py:659`, `alphagenome_check.py:5`, `clingen.py:26`,
`identifiers.py:335`, `civic_refutation.py:14`), and individual tests pin individual instances. This
tier has AST-walked structural guards for four *other* invariants (the `__main__` guard, duplicate
function definitions, `try/finally` around an owned client, `--out` defaults, sidecar path joining),
so the absence of one here is conspicuous. **I could not find a test that walks the check modules and
asserts none of them writes an authored CSV.** Either it exists under a name I did not search for, or
the property is convention-plus-review. I searched `enricher/tests/` for `never repair`,
`unchanged`, `not rewritten`, `left exactly as`, and read `test_verification_record.py`'s full test
list.

### U2 — RESOLVED into §12 D5

Filed here first as "why is `--offline` absolute in `pgx`/`enrich` and conditional in
`gwas`/`expression`", then settled far enough to be a finding rather than a question: see §12 D5. What
remains genuinely open is narrow — whether the `gwas`/`expression` shape is a considered exception or
an unswept one. There is no comment at `gwas.py:485` or `expression.py:363` addressing the
injected-client case, where `test_pgx_licensing.py:393` addresses it head-on.

### U3 — RESOLVED while writing: `alphagenome check --strict` refuses nothing extra

Recorded as resolved rather than deleted. `alphagenome_check.py:417-420`: *"`mode` is carried for the
report and is **not** a severity ladder here. A model's score disagreeing with an author's expectation
is not a `strict` matter; what `strict` still refuses is structural, and that refuses in `best_effort`
too."* The `VariantImpactError` raises (`:187`, `:230`, `:267`, `:270`, `:493`) are all unconditional
on mode. `mode` is stored on `VariantImpactResult` (`:422`) and read nowhere as a gate. So `--strict`
on this command changes the recorded mode and nothing else.

### U4 — Whether the `enrich` chain's five links are exhaustively covered by one test

The chain has five gates whose interaction matrix is large (`offline` × `use_clinvar` × `use_gnomad` ×
cache presence × staged answers × build). `test_enrich.py` (809 lines) and
`test_enrich_transaction.py` (771) exercise many of them, but I did not enumerate the covered
combinations against the reachable ones, so I cannot say whether e.g. *"staged gnomAD answer, resumed
with `--no-gnomad`, on a machine that has since gained an Ensembl cache"* is pinned anywhere. The
code path is at `enrich.py:1294-1304` and is the one whose comment argues hardest for its own
correctness.

### U5 — Where `EnrichmentResult.clin_sig_record` is consumed downstream

`enrich` writes `write_concordance_tables(spec_dir, record.parents, record.calls)` (`enrich.py:1986`)
into sidecar tables. What reads those tables afterwards — compiler, marketplace, or only the next
`enrich` run's `answered_call_shift` — is not determinable from this package alone. The comment at
`enrich.py:1985-1990` says a subject the authorities stopped contesting must *leave* the record,
which implies a reader that treats presence as meaning.

### U6 — RESOLVED into §12 D5

`frequencies.py:233` is a bare `if offline:` with no `client is None` clause. By D5's own argument
that is the *correct* shape, not an anomaly, so it belongs inside D5 rather than here.

### U7 — Two checks in the vocabulary are RESERVED; the reservation is checked, the plan is not

`gene_disease_validity` and `dosage_sensitivity` have no emitter and say RESERVED with a reason
(`vocab.py:853-863`), and `test_verification_record.py:851` enumerates exactly those two. The reason
given is that no model carries an authored dosage or gene–disease claim to compare against. Whether a
schema change adding such a field is planned, and what the pass would look like, is not in this
package.

### U8 — Whether `hatch_build.py`'s fetch is expected to run in CI

The pin is digest-verified and idempotent, and the docstring says a build "needs network once, and
then never again". I could not determine whether CI pre-populates `_atlas_protos/` (a cache), or takes
the fetch on every cold build, or whether the build is expected to fail closed on a GitHub outage —
`.github/` was present in the worktree but I did not read it, being outside my read scope.
## 12. Defect candidates

Each is something I measured, not inferred. Severity is my own reading.

### D1 — Rich markup eats `[atlas]` and `[dev]` out of three rendered help texts

**Measured.** Typer renders help through Rich, which reads `[word]` as a style tag. Three help strings
carry a bracketed extra name and it vanishes at the terminal:

| source | source text | what `--help` prints |
| --- | --- | --- |
| `cli.py:4774` | `"…Needs the [atlas] extra (grpcio + protobuf, 22 MB)…"` | `…Needs the  extra (grpcio + protobuf, 22 MB)…` |
| `cli.py:4795` | `"…which is in `[dev]` and deliberately not in `[atlas]` — the runtime imports…"` | ``…which is in `` and deliberately not in `` — the runtime imports…`` |
| `cli.py:3753` | ``"Add ClinVar's literature links to a snapshot: `data/citations.parquet` ([dev], needs polars)."`` | ``…`data/citations.parquet` (, needs polars).`` |

Verified by reading `scratchpad/help/atlas.txt`, `atlas_generate.txt`, `clinvar_citations.txt` from
the `--help` walk. The `atlas generate` line is the worst: it reads *"which is in `` and deliberately
not in ``"*, telling the reader nothing at all about which install to do. Fix is one escape
(`\[atlas]`) or backticked-outside-brackets spelling. Low severity, high visibility — this is the
first thing a new user of the Atlas surface reads.

### D2 — Two declarations of the Atlas extra's size disagree

`cli.py:4774` says the `[atlas]` extra is **22 MB**. `enricher/pyproject.toml` (the `atlas` extra
comment) says *"Measured on 2026-09-10 in a clean venv: `uv pip install grpcio protobuf` is **19 MB of
site-packages and +2 packages**"*, and adds that the 22 MB figure was measured *"at the grpcio release
current then"*. So the help text carries the superseded number while the file that records the
measurement carries the current one. The pyproject comment is explicit that stale figures have already
been a problem here ("the figures this file carried before, 255 MB and 81, were quoted from the design
round and neither was ever measured").

### D3 — The `atlas` group help says "vendored"; `atlas generate` says "not vendored"

Same command tree, two adjacent help texts, opposite claims:

- `cli.py:4776` (`atlas --help`): *"the bindings are generated from the **vendored** Apache-2.0 .proto
  sources rather than committed"*
- `cli.py` (`atlas generate --help`, rendered in `scratchpad/help/atlas_generate.txt`): *"The sources
  are **not vendored**: the repository carries a commit id and a sha256 per file, and a file that does
  not match its pin is refused rather than used (RM196)."*

The second is the one the code implements (`atlas_protos.fetch_protos`, `atlas_protos.py:133-163`,
downloads from `raw.githubusercontent.com` and verifies a sha256). The group help is pre-RM196 text
that the RM196 change did not sweep.

### D4 — A count in prose beside the registry it describes, already stale

`schema/src/just_dna_format/vocab.py:775` heads the first block of `VALID_VERIFICATION_CHECKS`:

> `# ── wired: `enrich` writes these six at the end of its run ──`

Six members sit under that heading, plus `variant_impact_agreement` which belongs to
`alphagenome check`. The header is arithmetically true of its own block and **false about `enrich`**:
`enrich` writes **eight**. Measured by extracting the check-name literals from
`enrich._verification_records` (`enrich.py:2106-2466`): `reference_allele`, `genome_build_agreement`,
`clinical_significance`, `rsid_currency`, `rsid_coordinate_agreement`, `dataset_currency`,
`published_refutation`, `evidence_status_currency`. The last two are filed further down the same set
under the *"one command each"* heading, each with `— \`enrich\`` beside it, so the membership is
right and what drifted is that two of `enrich`'s checks were never moved up into its block.

This is precisely the failure `verification.py`'s own module docstring (`verification.py:23-46`)
documents having corrected **three times** in its own prose, and which
`test_verification_record.py:851` was written to end — but that guard asserts the *membership*
equality, not any block's arithmetic, so the sentence went stale again one file away from where the
lesson is written down. Cosmetic in effect; notable because the mechanism is the one this codebase
says it has closed.

### D5 — `--offline` does not outrank an injected client in `gwas` and `alphagenome expression`

Two spellings of `--offline` coexist in this tier.

- **`pgx` makes it absolute.** `test_pgx_licensing.py:393
  test_offline_with_no_snapshot_makes_zero_requests_and_says_why` injects a live `pharmvar_client` and
  a live `cpic_client` **together with** `offline=True` and asserts `recorder == []`. Its docstring:
  *"An **injected live client is not a loophole**: `offline` outranks the injection, because a live
  client under a flag documented as making no egress is exactly the failure RM38 closes."*
- **`enrich` makes it absolute** too: the link gates are `live_ensembl_runs = not offline and …`
  (`enrich.py:1085`) and `gnomad_runs = use_gnomad and not offline and …` (`:1086`), independent of the
  injected `resolver` / `gnomad_client`.
- **`gwas` and `expression` do not.** `gwas.py:485` is `if offline and client is None:` and there is no
  later `offline` reference anywhere in the module (verified: `grep -n offline gwas.py` after line 490
  returns nothing). `expression.py:363` is the same, and `grep -n offline expression.py` returns only
  lines 65, 302, 350, 363, 365, 366 — none of them a gate on the fetch path. So
  `enrich_gwas(spec, offline=True, client=LiveClient())` fetches.

`frequencies.py:233` is a bare `if offline:` with no injection clause at all — the strict reading,
consistent with `pgx` and `enrich`, and the module offers no reason for differing from `gwas`.

`clingen.py:208`, `gene_validity.py:430` and `acmg.py:611` use the same shape but inject **text**, not
a client, so nothing there can egress — those are the documented "inject the export you already hold"
escape and are not part of this finding.

Not reachable from the CLI (neither command exposes client injection), so the blast radius is a Python
API caller and the test suite. The concern is that `--offline` means two different things in two
functions that both take one, and the tier already has a test asserting the stricter meaning elsewhere.

### D6 — `uv sync` from a checkout performs an unannounced network fetch

`enricher/pyproject.toml` declares `[tool.hatch.build.hooks.custom] path = "hatch_build.py"`.
`hatch_build.py:31-40` runs `atlas_protos.fetch_protos()` at build time, which is
`urllib.request.urlopen` against `raw.githubusercontent.com` for five files
(`atlas_protos.py:141-163`). Measured in this session: the worktree was cut at 05:49 with
`enricher/src/just_dna_enricher/_atlas_protos/` absent (it is `.gitignore`d,
`.gitignore:238`); after `uv sync --all-extras` the directory exists with mtimes of 05:51:26.

This is deliberate, pinned and digest-verified, and the docstring says a build "needs network once,
and then never again" — so it is not a bug. It is listed here because **the tier's own headline
property is that only explicit commands fetch**, and `uv sync` is not one. A developer who believes
`--offline` covers them is wrong about their first `uv sync`. An sdist install is unaffected (the
files ride along).

### D7 — WITHDRAWN after checking: `SNAPSHOT_FILE_GLOBS` **is** guarded

I flagged `download.SNAPSHOT_FILE_GLOBS` (`download.py:116-126`, nine entries) as a hand-kept dict
beside a registry that has a field for every other per-lane fact, with `strchive` missing and nothing
asserting the correspondence. That last part is wrong.
`test_declared_retirement_and_prune.py:82 test_every_published_lane_with_a_data_directory_has_a_glob`
walks the registry and asserts

```python
publishable = {lane.name for lane in CACHE_LANES if lane.publish_repo is not None}
assert publishable - set(SNAPSHOT_FILE_GLOBS) == {"strchive"}
```

— an equality over a walked set with the one exception enumerated, and the docstring says why the
exception is a shape rather than an omission. `:76 test_every_declared_shift_names_a_repo_this_tier_publishes_to`
is the matching guard in the other direction for `LAYOUT_SHIFTS`. **Not a defect.** Recorded here
because a withdrawn candidate is part of the output.

### D8 — `cache pull` never fetches `avi_knots.parquet`, and two docstrings say it does

**Verified independently of the agent that first found it.** `locations.SNAPSHOT_ROOT_FILENAMES`
(`locations.py:122-126`) is a three-member registry — `LICENSE.txt`, `avi_knots.parquet`,
`release.json` — with a comment (`:110-116`) stating *"This is a registry because the alternative
already failed twice. `plan_reference_snapshot` iterated a hardcoded pair, `release.json` and
`LICENSE.txt` … The AVI knot table is the third such file and would have been the third such
incident: a published snapshot missing it looks complete — every parquet present, `release.json`
valid — and cannot answer the question the lane exists for."*

The **publish** half walks the registry (`upload.py:618`, `:639`). The **pull** half does not:
`_provision_snapshot` (`download.py:334`) is

```python
for optional in (RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME):
```

— the same hardcoded pair the registry exists to replace. `grep -rn 'ALPHAGENOME_KNOTS_FILENAME\|avi_knots' enricher/src/`
returns no hit anywhere in `download.py` except a docstring. So `cache pull --only alphagenome_avi`
brings `data/alphagenome_avi-*.parquet` and `release.json` and **not** the knot table, which
`locations.py:99-105` calls *"not optional: the artifact deliberately does not store `PHRED`, so
without this file a puller holds scores they cannot rank and `alphagenome check` refuses outright."*

Two docstrings assert the opposite of the code:
- `download.py:95-96` — *"`_provision_snapshot` fetches the root files from `SNAPSHOT_ROOT_FILENAMES`
  for every lane, so this needs no special case"*
- `download.py:497-498` — *"That file travels because `SNAPSHOT_ROOT_FILENAMES` names it, not because
  this function does."*

The fix is one line. This is the highest-severity finding in this document: a lane that publishes
correctly and pulls into an unusable state, with the incident it reproduces written down in the
constant it ignores.

### D9 — one unstaged fetch inside a module whose rule is that fetches stage

`download.py:326-333` states the rule at length: *"Staged through `.part` like every other download
here, because a failed one is not a no-op. `HfFileSystem.get` creates the local file before it
discovers the remote path is missing, so fetching straight to the real name left a 0-byte
`LICENSE.txt` in the cache of every snapshot whose repo publishes none."* The parquet fetch, the
sidecar fetch and the root-file loop all stage.

`_provision_root_file_snapshot` (`download.py:585`) does not:

```python
fs.get(f"{hf_repo}/{RELEASE_FILENAME}", str(cache_dir / RELEASE_FILENAME))
```

By the mechanism the module itself documents, a repo with no `release.json` leaves a 0-byte
`release.json` in the cache. `caches.LaneStatus.release_unreadable` (`caches.py:1252`) is exactly the
state that produces. See §9 (b) for the agent's measurement of the `HfFileSystem` call order in the
installed client.

### D10 — `GwasCatalogClient` leaks `httpx.ConnectError` past its own translation contract

**Reproduced by me, offline, independently of §6 C1.** Run in the worktree's venv:

```python
c = GwasCatalogClient(_client=httpx.Client(transport=httpx.MockTransport(raise_connect_error)))
c.associations_for("rs1800562")
```

→ `LEAKED httpx: ConnectError | attempts: 3`. It should be `GwasError`. `_get`'s own docstring
(`gwas.py:181-185`) says *"Both legs are translated (`@client-exception-contract`): a transport error
that survives the retries and an HTTP status error are equally the caller's problem and equally not
`httpx`'s vocabulary to express"*, and `GwasError`'s (`gwas.py:87-90`) says *"Every transport and
parse failure is translated into this before it leaves the module."* Neither is true on the exhausted
transport leg: `gwas.py:192-193` is a bare `except (httpx.TransportError, httpx.TimeoutException):
raise` with `reraise=True` on the decorator above it and no outer translating method.
`test_client_exception_contract.py:242` exempts this client from the roster walk, on reasoning about
the *named* type rather than the leaked one. See §6 C1 for the full argument.

### D11 — `CrossrefClient.exists`'s `@retry` never fires

**Reproduced by me, offline, independently of §6 C2.** The decorator declares
`stop=attempt_floor(3), retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException))`,
and the body catches `httpx.HTTPError` — the **superclass of both** — logs, and returns `None`. The
exception therefore never reaches tenacity. Measured over a transport that always raises
`httpx.ConnectError`:

```
Crossref lookup failed for 10.1000/x (boom); not checked
result: None | attempts: 1
```

One attempt, not three. The tri-state answer (`None` = "could not be asked") is correct and the
withholding is correct; what is wrong is that a single transient failure produces it where the
declared policy says three would be tried first. See §6 C2.

### D12 — `alphagenome expression` cannot see an `ALPHAGENOME_API_KEY` that lives in `.env`

**Reproduced and measured by me, independently of §6 C10.** `expression._connect`
(`expression.py:291-303`) reads

```python
key = os.environ.get("ALPHAGENOME_API_KEY") or ""
```

under a docstring that says *"The credential is read **here, where it is used** rather than as a side
effect of some earlier call (`@credential-where-read`)"*. But `grep -n 'load_env' expression.py`
returns **nothing** — the module never loads `.env` at all, so the "where it is used" half is honoured
and the "loaded there too" half is not. Eight sibling modules call `load_env()`
(`locations.py`, `download.py`, `pharmvar.py`, `upload.py`, `eutils.py`, `caches.py`,
`literature.py`, `net.py`).

Measured, with the key in a `.env` in the working directory and **not** exported:

```
before load_env, key visible: False
ExpressionError: ALPHAGENOME_API_KEY is not set, and this pass has no snapsho…
after an explicit load_env, key visible: True
```

So the pass refuses on a credential the operator has configured the way every other credential in
this tier is configured. This is the same shape as the defect
`test_cli_surface.py:176 test_the_ncbi_credential_is_loaded_where_it_is_read` was written for — and
that guard monkeypatches `eutils` and `literature` by name, so it cannot see this one.

### D13 — `record_source_terms`' docstring says its layers cannot taint; one caller passes `annotation`

**Verified by reading both sides.** `licensing.py:924-929` (the docstring of `record_source_terms`):

> None of these layers can taint a module: `taints_commercial_use` requires the `annotation` layer,
> because a coordinate or an AC/AN is a fact the source *reports* rather than expression it *owns*.
> … `declared_use` defaults to `unstated` because no fact-layer source here forbids sale, so these
> passes never have to ask the author for a declaration.

`civic_draft.py:613-619` calls it with `"annotation"` **and** an explicit `declared_use`:

```python
record_source_terms(consulted, "annotation", spec_dir, error=CivicDraftError, declared_use=declared_use)
```

So the function's own account of what it is for ("these layers", "these passes") no longer covers all
its callers. Documentation defect rather than a behaviour one — the taint machinery works — but it is
the kind that sends the next reader to the wrong conclusion about whether a drafting pass can taint.
Found by the §7 agent; confirmed here at both sites.

### D14 — `civic_draft` writes a `SourceRow` on a run that drafted nothing, and its own comment says it should not

**Verified by reading the gate.** `civic_draft.py:604-619`:

```python
# … Not written on a run that never reached the snapshot: a pass that
# contributed nothing writes none.
if not dry_run:
```

The condition is `not dry_run` and nothing else — no `result.added`, no candidate count. The
`consulted_registry` flag only decides whether the **second** (ClinGen) row joins the list. The two
sibling drafters do implement the rule: `strchive_draft.py:288-297` and `mitomap_draft.py:314-317`
both gate on an `added`/`already_present` outcome, and `test_strchive_draft.py:366` refuses exactly
this shape on the STRchive path. The §8 agent reproduced the behaviour: a draft for a gene the
snapshot does not carry yields `candidates=0, added=0` and still writes a `civic` row into
`licensing.csv`.

### D15 — `civic_draft` computes a dataset label and cannot pass it on

**Verified structurally.** `civic_draft.py:475` computes `civic_dataset_label(...)` and uses it in
every row's `conclusion` (`:283`), but `record_source_terms` (`licensing.py:908-914`) **has no
`dataset` parameter** — its body is `t.row(layer, declared_use=declared_use)` (`licensing.py:938`).
So the licence row this drafter writes carries `dataset=''`. The knock-on the §8 agent names is the
real cost: with no recorded `dataset`, `enrich --verify-datasets` has nothing to compare and
`withdraw_stale_dataset` has nothing to withdraw, so a CIViC-drafted module is outside the currency
check that every other drafted module is inside.

### D16 — the remaining candidates live in their own sections

§6.6 (ten client-surface candidates C1–C10; C3–C9 are not repeated here), §7.6 (ten licensing candidates),
§8's defect subsection (ten drafting candidates), §9's (seven publisher candidates). Each was written
independently and each carries its own evidence. The ones I re-verified myself are D8–D15 above.

The client, licensing, drafting and publisher sections carry their own defect subsections, written
independently.
