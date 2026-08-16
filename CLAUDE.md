# Agent Guidelines — just-dna-format

This repo is a **uv workspace** publishing three libraries in dependency tiers
(`enricher → compiler → format`):

- **`just-dna-format`** — the schema contract: pydantic models for the authored spec DSL and the
  compiled `manifest.json`, plus integrity/identity helpers. `pydantic` + `cryptography` only (the
  latter solely for Ed25519 signing), so any verify-only consumer stays light. → [docs/SCHEMAS.md](docs/SCHEMAS.md)
- **`just-dna-compiler`** — the reference compiler: a validated spec → a multi-parquet artifact +
  manifest (the three-parquet SNP core plus one parquet per optional table kind). `polars`/`pyyaml`/
  `typer` — **pure-Python and duckdb-free since 0.5**. → [docs/COMPILER.md](docs/COMPILER.md)
- **`just-dna-enricher`** — the network tier, the **only** package that fetches: it *produces* the
  injected `resolution.csv` the compiler consumes (cache → HF snapshot → live Ensembl V2/V1) and
  carries the module-upload publisher surface. `httpx`/`tenacity`/`huggingface-hub`. → [docs/ENRICHER.md](docs/ENRICHER.md)

Any consumer picks the tier it needs. **`just-dna-format` and `just-dna-compiler` never fetch**
(Principle 2 — inject-only); all network + HuggingFace live in `just-dna-enricher`. There is still
**no app and no orchestration here** — those live in `just-dna-pipelines` / `just-dna-lite` /
`just-dna-marketplace`.

**This file is headlines only.** Every rule below is one or two lines; the reasoning behind it — what
broke, what was measured, which repair was refused — lives in
**[docs/AGENT_NOTES.md](docs/AGENT_NOTES.md)**, section by section, and in the per-tier docs. When you
add a hard-won lesson, put the narrative there and one line here. Do not grow this file back into the
gotcha book: it is loaded into every session and has a size ceiling.

## The doc map — what each answers, and what to grep

| Doc | Answers | Grep for |
| --- | --- | --- |
| [CONSTITUTION.md](docs/CONSTITUTION.md) | the 8 principles + goals/non-goals. Wins over any plan. | `grep -n '^[0-9]\+\. \*\*' docs/CONSTITUTION.md` |
| [AGENT_NOTES.md](docs/AGENT_NOTES.md) | the long-form gotcha book behind this file | `grep -n '^## ' docs/AGENT_NOTES.md`, then the symbol name |
| [RM_TOC.md](docs/RM_TOC.md) | where any `RMn` lives, status included — the complete list | `grep -n 'RM47' docs/RM_TOC.md` |
| [ROADMAP.md](docs/ROADMAP.md) | open items, the idea-book, the reserved-namespace and 1.0-cleanup trackers | `grep -n '^## RM' docs/ROADMAP.md` |
| [ROADMAP_HISTORY.md](docs/ROADMAP_HISTORY.md) | shipped items with their rationale | `grep -n '^## RM' docs/ROADMAP_HISTORY.md` |
| [ROADMAP_0_7.md](docs/ROADMAP_0_7.md) / [ROADMAP_1_0.md](docs/ROADMAP_1_0.md) | deferred items, with the reason for the deferral | `grep -n '^## RM' docs/ROADMAP_1_0.md` |
| [CHANGELOG.md](docs/CHANGELOG.md) | what shipped, newest first (shared across the ecosystem repos) | `grep -n '^## 2026-' docs/CHANGELOG.md` |
| [SCHEMAS.md](docs/SCHEMAS.md) | models, CSV families, conventions, the nine hashes, the allele grammar | `grep -n '^## ' docs/SCHEMAS.md` |
| [COMPILER.md](docs/COMPILER.md) | validation ceiling, compile pipeline, **§ Resolution** + round-trip matrix, reverse, coverage | `grep -n '^## ' docs/COMPILER.md` |
| [ENRICHER.md](docs/ENRICHER.md) | resolver chain, the check table, rate limits, caches, publish/upload | `grep -n '^## ' docs/ENRICHER.md` |
| [MODULE_LIFECYCLE.md](docs/MODULE_LIFECYCLE.md) | origin → publish → a consumer's join; **what pass 2+ moves** | `grep -n '^## ' docs/MODULE_LIFECYCLE.md` |
| [FAQ.md](docs/FAQ.md) | settled questions keyed by *question* ("why did my digest move?") | `grep -n '^\*\*' docs/FAQ.md` |
| [CONSUMER_SUGGESTIONS.md](docs/CONSUMER_SUGGESTIONS.md) | the **open** consumer inbox (`Sn`) — empty means nothing owed | `grep -n '^## S' docs/CONSUMER_SUGGESTIONS.md` |
| [CONSUMER_SUGGESTIONS_HISTORY.md](docs/CONSUMER_SUGGESTIONS_HISTORY.md) | answered `Sn`, verbatim, with the reply | `grep -n '^## S[0-9]' docs/CONSUMER_SUGGESTIONS_HISTORY.md` |
| [CONSUMER_TRIAGE_LOOP.md](docs/CONSUMER_TRIAGE_LOOP.md) | the runbook for answering an `Sn`, and the ledger | `grep -n '^## ' docs/CONSUMER_TRIAGE_LOOP.md` |
| [USE_CASES.md](docs/USE_CASES.md) | a use case → enabled / consumer-side / gap. **Start a design task here** | `grep -n '^## ' docs/USE_CASES.md` |
| [REFERENCE_EXAMPLES.md](docs/REFERENCE_EXAMPLES.md) | how to author each case with today's bricks; indexes `reference_examples/` | `grep -n '^## ' docs/REFERENCE_EXAMPLES.md` |
| PROPOSAL_[0_4_1\|0_5\|0_5_1\|0_6].md | design threads with their charter checks and open questions | `grep -n '^## ' docs/PROPOSAL_0_6.md` |
| [DOGFOOD_0_6.md](docs/DOGFOOD_0_6.md), [DOGFOOD_0_6_FINDINGS.md](docs/DOGFOOD_0_6_FINDINGS.md), [VCF_4_4_AUDIT.md](docs/VCF_4_4_AUDIT.md) | probe rounds and what they broke | `grep -n '^## ' docs/DOGFOOD_0_6_FINDINGS.md` |

Cross-cutting greps worth knowing: an `RMn` or `Sn` anywhere → `grep -rn 'RM47' docs/`; a symbol's
rule → `grep -rn 'hosting_verdict' docs/ schema/ compiler/ enricher/`; a warning a consumer quoted →
`grep -rn 'have no chrom+start' compiler/ docs/`.

## Read these first, in this order

1. **[docs/CONSTITUTION.md](docs/CONSTITUTION.md) — the durable charter. READ IT BEFORE JUDGING OR
   CHANGING ANYTHING.** Declarative-not-code, no network, backward-compat within a major,
   integrity-as-identity, orthogonal axes, the vocabulary idiom, round-trip/idempotency, requiredness
   compatibility. When a plan conflicts with it, it wins; **an audit that has not read it is
   incomplete**, since P3/P7/P8 decide whether a change is even legal. It is **self-contained** — it
   names no other document, and the navigation into the living material is here. Never add an outward
   pointer to it.

   **Never delegate a Constitution question to a spawned agent — read it yourself, in full.** A
   summary of a charter drops the qualifier the decision turned on ("additive" vs "non-breaking",
   `None` vs `False`, "tightened" vs "loosened"). Same for any durable rule you are about to *judge* a
   design against, and for the exact test that pins a behaviour. Delegation is for **finding**, never
   for **deciding**.
2. **[docs/ROADMAP.md](docs/ROADMAP.md)** — open items only, one `## RMn` each with severity/status/
   owner, plus the idea-book and the two trackers the Constitution keeps out of itself. Shipped work
   is in ROADMAP_HISTORY; [RM_TOC.md](docs/RM_TOC.md) indexes both (it exists because `RM33` became
   unfindable when neither table was complete).
3. **[docs/CHANGELOG.md](docs/CHANGELOG.md)** — what actually shipped.
4. **Per-tier reference** — SCHEMAS / COMPILER / ENRICHER. Read the tier your task touches.
5. **[docs/FAQ.md](docs/FAQ.md)** — **check it before designing anything.** Most entries are a repair
   somebody proposed that was checked and refused.
6. **[docs/MODULE_LIFECYCLE.md](docs/MODULE_LIFECYCLE.md)** — the cross-tier view: which surface owns
   which stage, and what a second/third/twenty-fifth pass moves. Read before reasoning about updates,
   versioning, or anything downstream of publish. It carries the honest note that no module here has
   ever had a second version.

## Authoring a module? It is the `/create-module` skill, and that is the only copy

`.claude/skills/create-module/SKILL.md` + `references/TABLES.md` (which table kind a finding belongs
in) + `references/SYMPTOMS.md` (message → cause → action). It is the workflow for *using* the format,
and every command in it was run end to end.

- **It is written for an author with no checkout**, so it is **fully dereferenced and must stay that
  way: it names no path outside its own directory** — no `docs/`, no `reference_examples/`, no
  Constitution, no bare `RMn`. That bans *outward references*, not the material: where a repo doc
  would link, the skill states the rule and moves on.
- **One copy.** A new authoring gotcha goes in the skill, and reaches this file only if a
  *contributor* also needs it. Do not start a second authoring doc under `docs/` — the repo-side twin
  (`AUTHORING*.md`, 578 lines the skill already contained in full) was deleted for being a second
  thing to update. `/write-module`, a dispatcher into `docs/`, was deleted for being unusable by the
  reader above. Recover either from git history for the wording.
- **Why a bug existed, or what a repair rejected, never goes in the skill** — that is
  [AGENT_NOTES.md](docs/AGENT_NOTES.md) or ROADMAP_HISTORY. The skill is operative rules only.
- **Its command-surface tables rot silently** (no test reads them): re-run `--help` against them
  whenever a flag, command or vocabulary member changes. Everything about *schemas* it delegates to
  `describe`/`requirements`/`reference` — keep that half delegated.

## Gotchas — headlines. The reasoning is in [docs/AGENT_NOTES.md](docs/AGENT_NOTES.md)

### Identity: `variant_key`, VRS, digests → [notes](docs/AGENT_NOTES.md#identity-variant_key-vrs-ids-and-what-a-digest-is-a-function-of)

- **`derive_variant_key` precedence: the rsid FIRST**, then the `ga4gh:VA.…` id for a
  coordinate-authored single-base substitution, else `chrom:start:ref[:alts]`. Indels, MNVs and
  multi-allelic cells deliberately fall through. Pass `alts` **only when minting an identity**;
  position-level matching (studies, `_verify`, reverse pos→rsid, haplotype dedup) calls it *without*.
- **`ResolutionRow.vrs_id` is one id per ALT**, positionally aligned with `alts`, outside
  `RESOLUTION_FACT_FIELDS` — a parallel array, never one row per allele; an empty member is a hole and
  holes are kept; desync is guarded twice (length at load, member-wise on recompute).
- **A pass that checks what is present must also count what is absent.** `_vrs_coverage` →
  `manifest.compilation.vrs_alleles` / `vrs_alleles_identified` (two counts, never a ratio or a bool),
  denominator in **alleles**, gaps grouped by reason class, warns in both modes.
- **A VA does not encode `ref`** — hence two guards: the compiler's *inconsistent reference allele*
  error (offline) and the enricher's `verify_reference_alleles` (online, the only one that can catch a
  single-base wrong ref).
- **The compiler's VRS check has three outcomes and none is a mode ladder** — verified / mismatch
  (error both modes) / unverifiable, whose severity follows **whose limit it is**: tier limit warns in
  both modes, a row contradiction errors in both, `*` (RM59) is its own gap class. An **absent** id on
  a symbolic row is a coverage warning; a **stored** one is an error. An indel is never a "mismatch".
  Full matrix in COMPILER.md.
- **`ga4gh.vrs` is a CORE enricher dependency, never `[dev]`, never in format/compiler** — the
  compiler's verify pass is stdlib on purpose; `--offline` degrades minting to substitutions only.
- **`refget_accession` raises on a non-GRCh38 build**, and `refget_supports_build` answers the same
  predicate including `None`/`""` — catch `UnsupportedBuildError` at every call site.

### Coordinates and the genome build → [notes](docs/AGENT_NOTES.md#coordinates-and-the-genome-build)

- **Every `start` is the 1-based VCF position — do NOT convert.** `derive_vrs_allele_id` does the
  interbase conversion once, itself. The docstring that said "0-based" was the bug: it shifted four
  external modules by one base past every offline gate, `--strict` included.
- **A row is stamped before the module is known**, so anything build-dependent is re-derived by the
  compiler (`_restamp_for_build`, at **both** load sites).
- **`genome_build` is in `manifest.json` and no parquet column.** Anything rebuilding a spec must read
  it; reverse, `enrich()` and the frequency pass each got this wrong. Any call to
  `derive_variant_key`/`derive_vrs_allele_id` must pass the row's build — `test_build_call_sites.py`
  walks the AST — and `reference_examples/grch37_build/` must stay or the corpus goes uniform again.
- **The build is INJECTED into a row at load** (`AuthoredModel._genome_build`), never authored on one.
  Per-row and per-CSV "service row" shapes were rejected; don't re-propose them.
- **`content_signature` is reference-independent, NOT build-independent** — `genome_build` feeds the
  hash only when non-default, so every GRCh38 signature is byte-identical.
- **A "ref mismatch" has three causes and the coordinate one is common.** One window read, withhold
  when both neighbours match, group by reason (`summarize_ref_mismatches`), never infer direction from
  the module's dominant shift.
- **The ±1 shift reading is confident and wrong on an old-assembly coordinate — RM48 orders the two.**
  Only `dbsnp_corroborated` / `multi_base_match` supersede; a single-base GRCh37 match rests on the
  same one-in-four coincidence. Recovery **reports, never fills**.

### Alleles: grammar, spelling, hosting → [notes](docs/AGENT_NOTES.md#alleles-grammar-spelling-hosting)

- **A non-nucleotide allele in `ref`/`alts` is a SPELLING defect** — diagnose it
  (`alleles.non_nucleotide_reason`); adding a nucleotide grammar to `alts` is illegal three ways, and
  "expanding" `Y`→`C,T` has zero instantiation across 4.4M ClinVar rows. `validate_allele` has **two**
  users (`HaplotypeRow.allele`, `VariantRow.effect_allele`) plus the shared diploid grammar.
- **Symbolic/structural alleles are held since 0.6 (RM5)** — VCF 4.4's closed five, length in the
  token. The schema accepts a lengthless `<DEL>`; the **compiler** refuses it (warn-and-drop under
  `best_effort`, fatal on `haplotypes.csv`/`heteroplasmy.csv`). `hosting_verdict` returns `None` for
  one, never `False`. `##ALT=<ID=…>` and readable aliases stay rejected.
- **Hosting is a THREE-valued question (`hosting_verdict`, RM31).** `parsimony_reduce` first tries the
  raw comparison, normalization may only *add* acceptances, the confident negative is about event
  **size**, and `_check_allele_membership` must ask the same predicate.
- **An rsID is position/multi-allelic-level, not per-allele** — clinical identity keys `variant_key` +
  genotype, and the reverse pos→rsID back-fill is allele-aware (0 → leave null, 1 → attach, ≥2 →
  deterministic pick + `ambiguous` + `rsid_alternates`).
- **`absent` for an rsID means typo *or* withdrawn** and no live endpoint separates them; the message
  must name both readings. `VALID_RSID_STATUS` has **four** members.
- **For merge status NCBI is the oracle, not Ensembl** (`esummary db=snp`, batched).

### Resolution and the round trip → [notes](docs/AGENT_NOTES.md#resolution-and-the-round-trip) · [COMPILER § Resolution](docs/COMPILER.md)

- **Resolution must be REVERSIBLE**: `compile → reverse → compile` reproduces the module or `strict`
  refuses. `authored_ident` is what makes it work (`variant_key` cannot substitute); an expansion
  collapses back to **one** authored row; a locus that cannot host the genotype is dropped;
  `withdrawn` refuses in both modes, `ambiguous` in strict only. A new behaviour adds a row to
  `compiler/tests/test_resolution_matrix.py`.
- **Allele membership compares against the UNION of loci a key resolves to**, on authored rows before
  expansion; mode ladder, never an unconditional error.
- **The Ensembl snapshot's `alt` is PIPE-joined**; every other link uses commas. Use the pipe shape in
  resolver fixtures for multi-allelic sites.
- **Resolution reads `pharm_variants.csv` and `haplotypes.csv` too**; subjects dedupe by `variant_key`
  with `variants.csv` **first** (it alone carries `alts`, a fact column).
- **Reverse dropping `rsid_alternates` is not a bug — closed, don't re-flag it.**
- **An existing `resolution.csv` is authoritative and merged, never clobbered** — same for
  `frequencies.csv`, `gene_metrics.csv` and an existing `vrs_id`. **Delete the sidecar** to regenerate
  after a machinery change.
- **Resolution reaches the SNP core ONLY (RM43)** — "just join `resolution.csv` on `variant_key`"
  moves `content_signature`, not only the digest. 0.5.3 shipped legibility
  (`_check_positional_joinability`), not the fill.
- **An UNREACHABLE source is unchecked, never absent (S20)** — no `not_found` row is written,
  `EnrichmentResult.unreachable_rsids` names them, warns in both modes. A 4xx **is** an answer.

### Checks: where they run, what severity means → [notes](docs/AGENT_NOTES.md#checks-where-they-run-and-what-severity-means)

- **Audit `validate`/`compile` parity by CHECK, not by TABLE.** Pure computation over injected or
  authored bytes with no `output_dir` belongs in `validate_spec` too — it once exempted the fact
  sidecars, so a module the licence gate would refuse validated clean. `compile_module` runs
  `validate_spec` in `best_effort` whatever its own mode, so the compile side re-runs to reach real
  severity, de-duplicated on the message.
- **Know the validation ceiling before adding a check** → COMPILER.md § *What the compiler can and
  cannot validate*. It is an assembler, not a truth oracle; a check needing a reference belongs in the
  **enricher**.
- **Enricher checks report, never repair**, and severity follows the mode (see ENRICHER.md's table).
- **Re-run a check after resolution exactly when resolution changes its input — and never when the
  message embeds a count.** `_check_contig_ploidy` had to move behind resolution (it fills `chrom`); a
  count-bearing warning must stay in front, or `manifest.compilation.warnings` publishes two
  contradicting sentences (measured at 328 beside 337).
- **The ClinVar `clin_sig` cross-check never escalates under `strict`** — failing would make the
  format arbitrate a clinical dispute. Don't "fix" the inconsistency.
- **A check that cannot fail must not report a zero** (`clinical.tautology_reason`) — a structurally
  guaranteed pass looks like evidence.
- **Before adding a table-level check, ask whether its rules are jointly satisfiable** (RM35).
- **An all-digit genotype is a pasted VCF `GT`** and is diagnosed before the arity check (RM77): a
  correct sentence aimed at the wrong defect sends the author to the wrong cell.
- **Check the RELATIONSHIP, not the members (S24)** — `GeneLocusConflict` compares `gene` against the
  variant's chromosome, at **chromosome granularity only**, exempting PAR genes, repairing nothing.
- **Unknown files in a spec directory are tolerated (S16); a near-miss table name is not** —
  `_check_misspelled_tables`, derived from the table registries, and it must know `derived/`.
- **A warning's TEXT is an API (RM44)** — `compiler.UNJOINABLE_PHRASE` is pinned by a test in both
  places. Give consumers a structured field, and when a flag quantifies over a subset **publish the
  denominator** (`resolution_subjects` shipped in 0.6; `fully_resolved` stays `bool`).
- **The compiler discards a literature row no study and no bin cites; `literature.csv` keeps it
  (RM79)** — `split_cited_literature` is the one shared rule; an empty citation set discards nothing.

### PAR loci and contig ploidy → [notes](docs/AGENT_NOTES.md#par-loci-and-contig-ploidy)

- **`chrom=Y` is NOT "never diploid"** — PAR1/PAR2 are diploid in every karyotype;
  `vrs.in_pseudoautosomal_region` is three-valued and `PAR_GRCh38` is an assembly constant.
- **A PAR locus is one place on two contigs (RM32)** — `par_partner` by index-matched offset (never
  "the same base on X and Y"), the enricher keeps the **X** spelling, the verdict is **per locus**, and
  position agreement is necessary but not sufficient.
- **gnomAD does not cover the Y PAR** — `not_covered`, a distinct status, deliberately outside the
  `strict` gate.

### Binning, citations, literature → [notes](docs/AGENT_NOTES.md#binning-bounds-citations-and-literature)

- **A bin boundary is the most interpretive claim the format carries** — `_check_binning_grounding`
  warns in both modes when a binning table states thresholds and the module records no study rows
  (S19).
- **RM47 shipped: the bin row cites (`MeasureBinRow.pmid`), the citation table describes.** That
  sentence is what stops `StudyRow`'s columns migrating onto bins. `StudyRow.REQUIRED_ANY_OF = ()`;
  the enricher reaches bins through **public** compiler symbols (`load_binning_rows`,
  `binning_citations`); grounding is counted per row off the `pmid` alone.
- **A shared bin endpoint belongs to the higher bin on a dense measure** (`lo < prev_hi` there,
  `lo <= prev_hi` on integer kinds); `measure_max` is inclusive on **every** kind.
- **Existence vs retrievability for citations** — a paywall hides the fulltext, not the record;
  Crossref covers what PubMed does not index (checking the *authored* DOI); `quote_source` records how
  far the search reached. Google Scholar is rejected, not deferred.
- **Existence is not identity (S12)** — a lookup answering "does this exist" must say **what** it
  found (`CitationHint` carries title/journal/year/first author).
- **A quote is an ATTESTATION (S11)** — `hints.ATTESTATION_BEARING`, a sharper refusal than
  redundancy-bearing: a machine-extracted passage states something false, not merely vacuous.
- **PMID and PMCID are one letter apart and a space decided the outcome (RM50)** — `PMC 3110566` once
  parsed as a real unrelated PMID. Four diagnoses; the converter is a **reporting** lookup; no
  authored `pmcid` column before 1.0 (P8).
- **A thread-based regex timeout is a trap** — `literature.regex_matches` uses a killable child
  process; don't "simplify" it back.
- **The `literature.csv` writer is derived from the model**; merge-not-clobber means a re-run does not
  back-fill new columns — delete the sidecar.

### Licensing, sources, the compile gate → [notes](docs/AGENT_NOTES.md#licensing-sources-and-the-compile-gate)

- **A machine-written sidecar has two legal names and two legal places — never join one onto a spec
  directory by hand (RM51 + RM49).** `just_dna_format.layout` is the single resolver (four parties
  must agree). **Write to the file you read**; both present is an **error** naming both paths; only
  machine-written tables move; `_check_misspelled_tables` had to learn `derived/`, and it takes two
  tests there. Reverse is the fresh-directory case of the rule, not an exception.
- **Licensing lives as DATA in the licence table, never as a table in the compiler** (that would be a
  source convention, P2, and it goes stale). Only the `annotation` layer taints; most-restrictive-wins
  module-wide; `None` ≠ `False`.
- **A pass that consults a source must WRITE its `SourceRow`** — `licensing.record_source_terms`; a
  row that is only returned is a source the module cannot account for. A fact-layer row carries
  *attribution*, which is as much the point as the prohibitions.
- **Derive a column list from the model, never by hand** — `SOURCES_FIELDNAMES` omitted
  `redistribution`, so RM27's gate read a column no file had. Use `list(Model.model_fields)`, or
  `base.authored_field_names` where the model has stamped fields.
- **`source` names the licensed source in every fact table; only `resolution.csv` also records the
  link** (`authority` is what `sources.csv` joins on). The link→authority map is **enricher-side**.
  `gene_metrics.csv` was fixed the other way — route stays in `dataset`. This was RM33.
- **A layer with no `source` column is structurally exempt from the orphan check** — `annotation`, and
  since RM46 `literature` unconditionally. `frequency` still warns. Don't restore either half.
- **The compile gate is data-driven; a `--non-commercial` CLI flag would be charter-illegal** (a flag
  cannot be recorded in the artifact, so step 3 of the round trip would refuse). It refuses in **both**
  modes and sits immediately before `output_dir.mkdir()`.
- **`declared_use` (`--use`) is a THIRD axis, not a mode** — three states; defaulting either way would
  make the tool assert a purpose for the user.
- **`redistribution` is recorded but NOT gated** — a distribution right is not a *use*; finishing the
  gate needs RM27's design round first.
- **A literature source's terms are PER ARTICLE, which is why there is no `pubmed` row (RM46)** — four
  columns on the derived row, `license` stored verbatim and mapped at read time, independent of
  `is_open_access`, outside `LITERATURE_FACT_FIELDS`. Quoting a non-commercial article warns in both
  modes and gates nothing.
- **PharmGKB is now ClinPGx (`api.clinpgx.org`), and every PGx upstream is research-only** — ClinPGx,
  CPIC and PharmVar are CC BY-SA **plus a contractual no-sale clause**, so none is sellable, and none
  may ever be wired as a resolution link (that keeps the coordinate layer unrestricted). PharmVar needs
  an `Api-Key:` header at 2 rps and its key is personal — never bake one into a module, fixture or
  snapshot.
- **Every gated source has a cache, and PharmVar's is deliberately unpublishable (RM38)** — the route
  is snapshot → live → skip-with-a-reason, `--offline` means the first only, `offline` outranks an
  injected client **on the type**, and builders store values verbatim and map at **read** time.

### PGx sources → [notes](docs/AGENT_NOTES.md#pgx-sources-clinpgx-cpic-pharmvar)

- **ClinPGx clinical annotations are per genotype, and the key is
  `(variant_key, drug, genotype, phenotype_category, annotation_id)`** — anything indexing by the bare
  triple has the bug (the first cross-check did). `PharmVariantRow.genotype`'s grammar lives on
  `AuthoredModel`; canonical form is `C/C`, disambiguated from the resolved ref/alt.
- **A negative finding about a source is only as wide as the table you looked at** — "CPIC publishes
  no chromosome" was true of `sequence_location` and false of CPIC (`gene.chr`), and cost 36 defining
  variants for a year.
- **A source that publishes both assemblies lists the wrong one first** — filter on the field that
  *names* the assembly (`referenceCollections`), never the accession version. A snapshot is what turns
  a latent wrong number into a written one.
- **A credential must be loaded where it is read** — `load_env()` in `__init__`, `override=False`.
- **Which columns may become several rows is decided by the DEDUP KEY, not the source's dialect
  (R2-1)** — write the member the *request* selects, otherwise withhold and name what the cell held.
  Check filter ordering while you are there.
- **A large star-allele gene is drafted with `draft --allele`, and the filter covers all three
  tables** (RM34); `*1` is always kept; count over the rows the filter actually judged.
- **An incidental call must not discard finished work (R2-4)** — `knows_drug`'s failure renders as the
  tri-state's *could not ask*, with its own wording.
- **A client that leaks its transport library's exception type has no contract (R2-13)** — retry in
  `_request`, translate in `_get`, in that order, and **fix both legs**.

### Drafting and the authoring surfaces → [notes](docs/AGENT_NOTES.md#drafting-and-the-authoring-surfaces)

- **Drafting APPENDS, it never mutates** — row granularity, keyed on the compiler's own
  `_TABLE_DUPE_KEYS`, rows at the end (authored order is load-bearing for the digest). Drift on
  existing rows is `enrich_pgx`'s job.
- **A partial row is validated by OMISSION and matches on `match_on`**, not the natural key (which
  runs through the stub). `PartialRow` exists because ClinVar publishes alleles, not genotypes.
- **A placeholder protects a DECISION; where the contig leaves none, filling it pre-empts nothing**
  (`sole_expressible_genotype` on MT and non-PAR chrY, S6) — decided **per locus**, `True` *and* `None`
  keep the stub.
- **A drafting provider fills identity WHOLE or not at all** — rsID, else complete
  `chrom`/`start`/`ref`/`alts`; a lone `alts` changes which variant the row *is*.
- **`SourceRow` carries the placeholder guard**, and "a generated stub cannot compile" is tested over
  every `DRAFTABLE` kind (RM76).
- **A generated stub must be unable to compile** — `vocab.TEMPLATE_PLACEHOLDER`, `mode="before"` so
  the message names the placeholder rather than the type. Never reuse `MeasureBinRow.unresolved` (P5).
- **Scaffolding refuses per FILE; drafting refuses per ROW.** Both treat a zero-byte file as missing.
- **Requiredness has THREE shapes and the middle one is invisible to pydantic** — use
  `draft.field_category` and `draft.authoring_requirements` (which also reports `REQUIRED_ANY_OF`).
- **`sources.csv` is draftable**, keyed `(source, layer)`; the other three fact sidecars are not.
- **A guard that iterates a model registry is only as complete as the registry (S21)** — add new
  models to `reference._ALL_MODELS`, and ask what a guard *enumerates* before trusting what it proves.
- **A vocabulary binding lives on the FIELD and carries its members** (`base.vocabulary`, with a
  `closed` flag — the drift was in closedness, not membership). Shared validator →
  `base.SHARED_VOCABULARIES`; never mark a field nothing enforces.
- **A closed vocabulary accepts `-` where `_` goes and canonicalizes** (`vocab.match_vocab`) — as
  written is tried first, the declared member is what gets stored, and it widens only.
- **`model_fields` is NOT the authored surface** — generators use `base.authored_field_names` and skip
  by the `COMPILER_MANAGED` marker, **never by name** (`FrequencyRow.variant_key` is genuinely
  authored). Test any new generator against `variants.csv` specifically.
- **A generic rejection is a dead end where a specific one is a fix** — three `mode="before"`
  diagnoses over `extra="forbid"`: reserved names, authority keys, misplaced columns. Diagnosing is
  not applying; key on the model's own fields; prose, not a cross-model registry.
- **A hint may not fill a cell a Class-2 check cross-examines** (`hints.REDUNDANCY_BEARING`) — the row
  would move from honestly unverified to apparently verified. A `--apply` flag on a lookup would ship
  the parked co-authoring item without deciding to.
- **"It moves the digest" is NOT a reason to refuse a row move** — probed and failed. `append_rows(…,
  group_by=…)` / `place_rows`: the tool picks where, the caller never supplies an index. `at=N` and a
  `sort`/`canonicalize` command stay refused.
- **A ragged CSV row misdiagnoses the column *after* the mistake (S18)** — report the field-count
  mismatch **before** the type error, error on surplus, warning on shortfall. `Finding.line` was
  **added** beside `row`, never redefined.
- **A drafted value that has not moved is a copy that can be ESTABLISHED, scoped to the CHECKED
  COLUMN (RM73)** — `SourceRow.draft_digest` over raw CSV cells, one function for writer and reader,
  the skip is release **and** digest, outside `SOURCE_FACT_FIELDS`. It closed two unfiled tautologies;
  audit by *check*, not by provider.
- **Authoring has an END (RM73)** — `VerificationDoc.closure` + `just-dna-compiler close`. No new file
  and no new proof-of-work (it rides the attestation); `validate` stays read-only; refuses an invalid
  spec but never a warning; absence warns while a false claim drops the block; closing **keeps** the
  document verbatim. The 1.0 gate is undecided — see ROADMAP_1_0 § RM73 before building it.
- **The draft marker is MACHINE-written, and `panel:` is deprecated with it (RM4)** — the release goes
  in `dataset` on the `clinvar`/**`annotation`** row, one function computes the label for both sides,
  compile-time panel materialization is **dead not deferred**, and a stale `dataset` is **withdrawn**,
  never re-labelled.

### Schema evolution: columns, signatures, materialization → [notes](docs/AGENT_NOTES.md#schema-evolution-columns-signatures-materialization)

- **A new OPTIONAL column or table is minor-legal** (P3/P4, charter amended 2026-08-11); major-only is
  **removal, promotion to required, retyping** — and *filling values* into an existing column, which is
  reverse's problem (RM43). An unset optional column is omitted from `content_signature`; only a
  recompile's `artifact.digest` moves. Measured, not argued.
- **Adding an authored column is exactly three touch points** — the model; the compile-side row dict +
  polars schema; and **the reverse `fieldnames` list + `_scalar_cell`**, the one that gets missed.
  Every new column gets a round-trip test. Table kinds under `_TABLE_KINDS` are generic and exempt.
- **Derived-not-stored is the house pattern for a convenience number** — exact parts in the CSV, a
  `@property` materialized to parquet, gone on reverse (`allele_frequency`, `neg_log10_p` — the latter
  load-bearing, since float64 flattens sub-1e-308 p-values).
- **Store a source's value verbatim EXCEPT when the encoding lies about its own order** (ClinGen
  dosage codes decode at the enricher boundary).
- **The 0.3 axes are a materialized PASSTHROUGH** — never fill `direction` from `state` at compile;
  that asserts what no curator wrote, independent of the digest.
- **`annotations.parquet` carries `genotype` AND keys on it (RM80)** — carrying without keying would
  turn a missing answer into a wrong one; reverse reads *which* of three keyings the artifact has.
- **`version: 3` in YAML is an INT** — a `mode="after"` validator cannot rescue a value the field type
  rejects first (RM17). A float stays refused *with the reason*. Run the corpus you did not write.
- **`content_signature` hashes a variant row's EFFECTIVE `curator`/`method`/`priority`** (RM37) — the
  defaults are folded in first, and the write-back-as-`None` normalization is what keeps existing
  signatures byte-identical.

### Snapshots, caches, network clients → [notes](docs/AGENT_NOTES.md#snapshots-caches-and-network-clients)

- **Rate limits are load-bearing in `gnomad.py`** — batches of 20 behind a 6 s pacing gate on an
  injectable clock. A pathless GraphQL error must raise, **except** the absence messages
  (`_ABSENCE_MESSAGES`); "pathless ⇒ our bug" was a premise about the API, not a law.
- **The two gene-constraint routes are different releases** (live v2.1.1 vs bulk v4.1), carry different
  `dataset` labels, and a test asserts they differ.
- **Builder in polars, runtime pass in duckdb** — keep the convention, but the "unusable on a plain
  install" justification for it was checked and is false.
- **A batch lookup must HASH its probe** — `resolver.probe_table` (88 s → 0.21 s on 5,000 alleles).
  SQL literals on purpose; a single-column `IN (…)` was always fine; benchmark on a spread sample;
  guard the plan (`EXPLAIN`), not the clock.
- **A default computed as an argument is computed before the callee's setup runs** — if the callee
  loads configuration, the default belongs inside it (`_cache_dir` / `load_env()`).
- **Dogfood data is git-ignored** (`data/interim/clinvar`, `/data/just-dna-cache/…`). 0.5.0 shipped
  2026-08-07, so published digests are frozen.
- **A PUBLISHED snapshot accumulates — provisioning must fetch only its own files**; a foreign parquet
  puts two schemas under one DuckDB relation. Same failure arrives locally from an old builder.
- **The snapshot layout lives in `locations` because FOUR parties must agree**; a sidecar is a
  **sibling** of `data/`, never inside it, and absence is normal at both ends.
- **Publishing a second artifact makes provenance a question — answer it in `release.json`**
  (read-modify-write, hash the input, and an unreadable release file is reported, not fatal).
- **A snapshot's `ensure_*` must actually be CALLED** — three instances so far. Provision when the
  local resolve returns `None` and the run is not `offline`; add no second CLI flag; an explicit path
  is the inject-only escape hatch and is never second-guessed.
- **Network tests are opt-in**: `JUST_DNA_NETWORK_TESTS=1`.
- **A flag must mean the same thing in every function that takes one (RM39)** — the shape is a no-op
  plus a warning reported as `skipped_offline`. "A flag with one legal value" is a claim about the
  wiring, so re-ask when the wiring changes.
- **A number this workspace computes and discards gets recomputed by every consumer (RM40/RM41)** —
  `EnrichmentResult.vrs`, `compiler.load_csv_rows` / `load_spec_variants`.
- **A constant two deployment shapes want different values of is a knob (RM42)** —
  `net.attempt_floor` (`$JUST_DNA_HTTP_RETRY_ATTEMPTS`), a **floor** not a flat set; leave a composed
  retry policy alone.
- **A rate limiter callers are told to share must be safe to share (S15)** — the lock covers the
  bookkeeping, **not** the sleep (that would be a concurrency limit, a different axis).
- **Probe a source's real file before modelling it; the docs lie by omission.** Watch especially for a
  lookup bug that surfaces as a false finding about the module (Orphanet's IRI: HTTP 200, zero terms).

## The design cycle (the order of things)

Feature ideas move through **one loop**; the docs are its stages, and a design task walks them in
order rather than jumping to code.

1. **Feedback** — [CONSUMER_SUGGESTIONS.md](docs/CONSUMER_SUGGESTIONS.md) is the **open inbox only**
   (`S1…Sn`); an answered item moves verbatim to
   [CONSUMER_SUGGESTIONS_HISTORY.md](docs/CONSUMER_SUGGESTIONS_HISTORY.md) with a row in its index, the
   same split as ROADMAP/ROADMAP_HISTORY. So an empty live file means nothing is owed — and **"no
   reply in the live file" never means "no work was done"**: establish what shipped before designing.
   Every `Sn` gets a `**Status —**` reply written back into the document; the runbook is
   [CONSUMER_TRIAGE_LOOP.md](docs/CONSUMER_TRIAGE_LOOP.md) (four routes; **legality sizes the release,
   severity only orders the queue**; the ledger `.claude/triage-state.py` says which items are
   unanswered). `.claude/watch-suggestions.sh` notices that a consumer has written.
   **The two `.py` tools run under `python3`, never `bash`** — bash reads `import x` as ImageMagick's
   screen-capture tool and litters the repo root (runbook §6).
   **Do not start a third feedback file** — the round-1 thread was removed on 2026-08-12 (git
   `53f9260`) precisely because an inbox the ledger cannot see is a backlog nobody sees.
2. **Usage → blockers → solvability** — enabled / consumer-side / a gap closable additively? →
   [USE_CASES.md](docs/USE_CASES.md)  ← **start a design task here**
3. **Means → draft schema → decision** — shape + charter check + open questions → the `PROPOSAL_*`
   thread for the release.
4. **Conclusion — how to author it now** → [REFERENCE_EXAMPLES.md](docs/REFERENCE_EXAMPLES.md)
5. **Terminal** — **shipped** (recorded in COMPILER.md's coverage table) or **deferred** (an `RMn`).

`USE_CASES.md` and `REFERENCE_EXAMPLES.md` are the same use cases at two points in the loop —
questions vs answers. A blocker is never a dead end: dissolved, closed additively, or parked.

## Coding standards

- **Dependency tiers are sacred** (CONSTITUTION Goal 2 + the 0.5 amendment): nothing heavy in
  `just-dna-format` (pydantic + cryptography only); `just-dna-compiler` is pure-Python and duckdb-free
  (polars/pyyaml/typer); network **and HuggingFace** live only in `just-dna-enricher`. Never pull
  Dagster / LLM SDKs into any tier.
- **No network in format/compiler; inject-only** (Principle 2) — the compiler consumes an injected
  `resolution.csv` and skips with a warning when nothing is injected.
- **Data-agnostic — a north star, not a totality claim.** A module is pure *annotation*: lookup tables
  and bounded rules, **no sample data, no genotype under test, no measured value** — the consumer
  supplies the measurement at query time. *But* the schemas generalize a **practical subset** of real
  data items, so when a real item does not fit, that is a schema gap to widen *additively*, not a
  consumer error.
- **Human-authorable ⇔ machine-precise — the gate on every schema change.** The authored DSL must be
  both legible to a rare human author and formally precise; the parquet is already the pure-machine
  form. Gate on *"will this burden the author?"*, and keep **one CSV = one concern** — a module
  includes only the table kinds it uses, never a foreign domain's columns on every row.
- **That gate prices the AUTHORED layer only (the 0.6 charter amendment).** A parquet column is
  approximately free, a derived CSV is half cost, an authored schema is full cost. It adds no
  permission — legality is still P3/P8, decided first — it only says what a *legal* change costs, so a
  review weighs it instead of reaching for file count. First consequence: `resolution.csv` gets **no
  parquet**, deliberately (SCHEMAS.md says so, because "publish it as a parquet" is the first repair
  anyone proposes).
- **Additive within a major** (P3/P8): a new column is optional and minor-legal; a required field is
  never demoted. Major-only: removing, promoting to required, retyping. A recompile's `artifact.digest`
  moving is not by itself a reason to defer.
- **Round-trip must stay lossless and idempotent** (P7) — prove it with tests.
- **Deterministic ordering is load-bearing.** Parquet bytes depend on row order, so **authored row
  order is preserved** through compile → reverse → recompile. Never derive emitted rows or manifest
  fields from `set`/`dict` iteration or polars `mode()`/`unique()` without an explicit stable sort or
  tie-break. Column order and cell formatting, by contrast, are **normalized, not preserved** — that
  asymmetry is intended. New orderings get a test.
- **The house algebra is THREE-valued: true / false / unknown — and `None` is never `False`.** One rule
  behind a dozen: unknown licence terms, `CrossrefClient.exists`, `quotes_found`, `unchecked` under
  `--offline`, `unresolved`, `requires_callable`, hints returning findings rather than verdicts. Give
  anything that answers a question three outcomes, and when the answer is unknown **withhold** — never
  report, never negate. Combine with **Kleene** semantics, not withhold-on-any-unknown, because
  `unknown AND false` really is `false`.
- **Authored row models inherit `AuthoredModel`** (`just_dna_format.base`), never `BaseModel` — it
  carries the reserved-namespace guard and the shared field validators. Don't re-declare `model_config`
  or re-copy a validator per model; when one is identical across ≥2 models, move it onto the base with
  `check_fields=False`.
- **The reserved namespace is only for names expected to become real columns** (P5) — `extra="forbid"`
  already rejects unknown columns generically, so barring a non-feature is arbitrary. A reserved name
  earns a specific diagnosis (`vocab.RESERVED_NAME_REASONS`).
- Pydantic 2 everywhere. Constrained vocabularies are `frozenset[str]` + a validator, never
  `Enum`/`Literal` (P6).
- **A drafting provider's skip guard must be DERIVED from the model's rule, not restated beside it** —
  `pgx_draft` skipped on "no rsID *and* no position" while `HaplotypeRow` wants rsID **or**
  chrom+start, and `draft --gene CYP2C9` died on an unhandled pydantic error. Test the guard against
  the model case by case rather than asserting a message.
- **Every provider must write its `SourceRow` — check the newest one, not just the old one.** A module
  drafted entirely from CPIC once carried no `sources.csv` at all, and the compile gate keys on that
  file and nothing else. A test that strips `declared_use` and asserts the compile refuses is what
  keeps the row load-bearing.
- **Distinguish "the source did not say" from "the source said something we cannot hold", and
  aggregate repeated warnings** — CPIC's `n/a` is an absence, `≥3.0` is a bound the numeric columns
  cannot express. Needed four times in one provider: assume a per-row warning needs collapsing before
  you ship it, grouped by **reason** rather than by row.
- **CPIC recommendations are keyed by (gene phenotype, drug, POPULATION), and the populations
  disagree** — `DiplotypeRow` has no population column, so `draft --drug` **refuses** and lists the
  choices rather than asserting a clinical context. Drug rows sit *beside* phenotype rows.
  `recommendation_strength` is CPIC's, `evidence_level` is PharmGKB's — different axes.
- **A star allele can be *used* without being *defined*** — `_cross_validate_haplotype_definitions`
  warns when `haplotypes.csv` is present; `*1` is exempt.
- Type hints mandatory; **pathlib** for paths; **absolute imports only**; **no inline imports** (a
  guarded module-level `try/except ImportError` for an optional dep is the only exception).
- **Avoid nested try/except** — it hides the real error. Use it only where an error is an unavoidable,
  handled part of the use case.
- **Polars in the compiler**: prefer `scan_parquet`/`sink_parquet`, and pre-filter before joining.
- **Typer for every CLI**; the root package's `[project.scripts]` owns the command. If a `uv run`
  wrapper goes stale, bump the version and re-run `uv sync` — never rename the command to dodge it.
- **Standard-library `logging`**, never `print`. **Heed terminal warnings, deprecations especially.**
- **No placeholder paths or fabricated example values** in code.
- **Refactor internals aggressively** — no dead code kept for nostalgia. The one exception is the
  wire/artifact **contract**, which obeys additive-within-a-major.
- **Versions read from `pyproject.toml`** (via `module.version`); never hardcode one in `__init__.py`.
- **Avoid `__all__` / pure re-export `__init__.py`s** — they obscure where a symbol lives.
- Use `uv sync` / `uv add`; **never** `uv pip install`. `uv run pytest` runs the suite.
- New markdown (except this file / `README`) goes in `docs/`.

### Dogfooding and the adversarial role → [notes](docs/AGENT_NOTES.md#dogfooding-adversarial-probing-and-how-a-finding-gets-filed)

- **Dogfooding means using the shipped surface to do real work — a capability the tool LACKS is the
  result, not an obstacle to route around.** The moment you reach for an ad-hoc script or a raw `httpx`
  call to get past something the product cannot do, the exercise stops producing its signal. Record it,
  and if it blocks the work, **build it into the product and carry on with the product**.
- **Dogfooding is not validation.** Validation is what tests do. Do not verify the tool's answers with
  a second implementation while dogfooding — that is a test, and it belongs in the suite.
- **The adversarial role pays**: try to show the libraries fail at something they *advertise*, then
  switch back and fix. **Attack claims, not gaps** (a documented deferral is a decision), and **use
  real data** — no `rs999999999`, no `e-328`.
- **Pick the probe where the schema generalized from one case** — take a real case with **two** of
  whatever the documented example has one of, and one at the edge of a stated convention.
- **Turn the tool on the work you just did.** A check written in the morning is the best candidate for
  the afternoon's probe.
- **Finish each probe as a reference example with a README naming what it broke** — the module is the
  regression test, the README is the evidence. Demonstrate the failure on the *old* behaviour.
- **Separate "fix it" from "surface it" before writing code**, and say *why each candidate repair is
  wrong* — that paragraph is what makes an item actionable later.
- **Dogfood a P7/dedup finding before reporting it** — construct a real, sensible example against the
  actual code paths, or it is not a finding. A mechanically-possible loss with no instantiation is
  noise (the standing example is the `annotations.parquet` variant-effect-pair claim).

## Testing

- `uv run pytest` runs the suite; **`-vvv`** when diagnosing.
- **Real data + ground truth**: exercise the actual compile/reverse paths against real fixtures and
  **compute expected values at runtime**. Hardcoding **domain constants** is fine; hardcoding
  **row/unique counts** read off a data dump is not.
- **Deterministic coverage** (fixed seeds or explicit filters), representative *and* edge cases.
- **Meaningful assertions**: relationships and aggregates over existence checks; set equality over
  counts.
- **Avoid the AI test anti-patterns**: happy-path-only, counts copied from a data dump, mocking a
  transformation instead of running the real path, and claiming a test "would have caught" a bug
  without first demonstrating the failure on the buggy code.
- Round-trip/idempotency (P7) and every new ordering get a real test.
- **Async tests use `pytest-asyncio`** (dev dep; no async paths today).
- **A test that means "no credential" must SAY so** — `api_key=None` is indistinguishable from "not
  passed", and `.env` leaks into `os.environ` from any unrelated test that resolves a cache path. So
  neutralize in an autouse fixture with **`setenv(VAR, "")`, not `delenv`**. Suspect ordering whenever
  a test passes alone and fails in the suite. Three real credentials sit in `.env`.
  → [notes](docs/AGENT_NOTES.md#testing-traps)

## Documentation & prose style

- Write in natural, human prose. Avoid AI-typical tells (em-dash pile-ups, filler transitions,
  marketing voice). Never hallucinate documentation or overpromise an unimplemented feature.
- Keep the `README` concise; deep detail belongs in `docs/`.
- Describe the format honestly: it supplies **annotation tables**, never sample data and never a
  gene–disease inference.
- **Self-correction**: when outdated API knowledge causes a real crash or logic failure, fix the code
  *and* update the affected doc so the next agent doesn't repeat it. One line here (or in the
  `/create-module` skill if an author needs it), the narrative in
  [AGENT_NOTES.md](docs/AGENT_NOTES.md). Update the guides immediately whenever code is refactored.

## Data & assets conventions

- Generated and sample data lives under `data/`, **git-ignored and build-ignored**: `data/input/`,
  `data/interim/` (code-generated intermediates), `data/output/`.
- Data that must **travel with the project** (a fixture a test or example needs) lives in `assets/`.
- Any asset over **~5 MB** that must travel goes through **Git LFS**: `git lfs install`,
  `git lfs track "<path>"`, commit the **pointer** — never the raw blob.

**Gotcha — check tree history whenever LFS is introduced.** A blob committed *before* `git lfs track`
stays in every past commit, so the pack still ships it:

```bash
git lfs ls-files                       # what LFS tracks at HEAD
git rev-list --objects --all \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '/^blob/ && $3 > 5000000 {print $3, $4}' | sort -rn   # large blobs anywhere in history
```

I don't run history-rewriting operations. **If a large blob is found, here is the sequence for you to
run:** `git lfs migrate import --include="<path-or-glob>" --everything`; verify with the scan above
plus `git lfs ls-files --all`; `git push --force-with-lease` (collaborators must re-clone or
hard-reset); optionally `git reflog expire --expire=now --all && git gc --prune=now`.

## Related repos (read-only unless the task targets them)

`just-dna-pipelines` (compiler/discovery), `just-dna-lite` (app + webui, the reference consumer),
`just-dna-marketplace` (catalog/storage/serving; consumes the `revalidate`/`needs_upgrade`
derivation), `just-dna-agents` (MCP surface — its `get_spec_format`/`list_colors`/`list_icons` are the
drift `authoring_reference()`/`RECOMMENDED_*` replace), `just-prs`.
