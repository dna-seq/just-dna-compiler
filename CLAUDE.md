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

## Authoring a module? It is the `/create-module` skill, and that is the only copy

`.claude/skills/create-module/SKILL.md` plus `references/TABLES.md` (which table kind a finding belongs
in) and `references/SYMPTOMS.md` (message → cause → action, keyed on the actual text). It is the
workflow for *using* this format rather than changing it — the command order and the one place
deviating from it deadlocks, what only a human may decide, the three questions that close off wrong
turns, the command surface of both CLIs, and the gotcha list. Every command in it was run end to end.

**It is written for an author with no checkout** — someone who ran `pip install just-dna-enricher` and
can see the skill and the CLI and nothing else — so it is **fully dereferenced and must stay that way:
it names no path outside its own directory.** No `docs/`, no `reference_examples/`, no Constitution, no
bare `RMn` without saying in-line what an RM is. Adding a pointer its reader cannot follow breaks the
only property it has. Note the direction of that constraint: it bans *outward references*, not the
material behind them — where a repo doc would link, the skill states the rule and moves on.

This replaced two earlier attempts, and both failure modes are worth not repeating. `/write-module` was
a dispatcher into `docs/`, useless to the reader above. `docs/AUTHORING.md` + `AUTHORING_TABLES.md` +
`AUTHORING_SYMPTOMS.md` were the repo-side twin, kept "for a reader who has the checkout" — 578 lines
that the skill turned out to contain in full (identical symptom-entry set, identical table claims), so
the split bought a second thing to update and nothing else. They were removed; recover them from git
history if you ever want the wording.

Four rules that follow:

- **There is one copy. A new authoring gotcha goes in the skill**, and reaches this file only if a
  **contributor** also needs it. Do not start a second authoring doc under `docs/` — that is the thing
  that just got deleted.
- **Why a bug existed, or what a repair rejected, never goes in the skill.** That belongs here or in
  ROADMAP_HISTORY. The skill is operative rules only, which is what keeps it short enough to read.
- **Repo-side context is reached through this file, not from the skill**: worked modules in
  `reference_examples/` (indexed by [REFERENCE_EXAMPLES.md](docs/REFERENCE_EXAMPLES.md)), the
  validation-ceiling table in [COMPILER.md](docs/COMPILER.md), the tracked limitations in
  [RM_TOC.md](docs/RM_TOC.md).
- **The skill's command-surface tables are the part that rots silently**, since no test reads them. When
  a published surface changes — a flag, a command, a vocabulary member — re-run `--help` against them.
  Everything it says about *schemas* it delegates to `describe`/`requirements`/`reference` rather than
  restating, which is what keeps that half drift-proof; keep it that way.

**Looking for a roadmap item?** [docs/RM_TOC.md](docs/RM_TOC.md) is the single complete list of every
`RMn` — status, the doc that defines it, and every doc that mentions it — plus the unnumbered
1.0/major bucket. Neither ROADMAP's nor USE_CASES' table was complete, which is how `RM33` became
unfindable.

## Read these first, in this order

1. **[docs/CONSTITUTION.md](docs/CONSTITUTION.md) — the durable charter. READ IT BEFORE JUDGING OR
   CHANGING ANYTHING.** It is the source of truth for what these packages are, what they will never
   do, and the invariants every release upholds (declarative-not-code, no network, backward-compat
   within a major, integrity-as-identity, orthogonal axes, the vocabulary idiom, round-trip/
   idempotency, and requiredness compatibility). When a plan conflicts with it, it wins. **An audit
   or design review that has not read the Constitution is incomplete** — its compatibility rules
   (Principles 3, 7, 8) decide whether a proposed change is even legal. **The charter is
   self-contained — it names no other document.** The navigation *into* the living material it
   alludes to is here in this guide (below); keep it that way — never add an outward pointer to the
   Constitution.

   **Never delegate a Constitution question to a spawned agent — read it yourself, in full.** It is
   150 lines and it is the document that decides whether a change is legal at all. A subagent returns
   a *summary*, and a summary of a charter is exactly the lossy relay that loses the clause the
   decision turned on: a principle's force is in its wording (the difference between "additive" and
   "non-breaking", between `None` and `False`, between "tightened" and "loosened"), and a paraphrase
   silently drops the qualifier. The same applies to any other durable rule you are about to *judge*
   a design against, as opposed to merely locate — delegation is for finding things, never for
   deciding them. Exploring wide (which files touch X, where does Y live) is what agents are for;
   reading the charter, the principle you are invoking, or the exact test that pins a behaviour is
   first-hand work.
2. **[docs/ROADMAP.md](docs/ROADMAP.md)** — forward-only and **active-only**: one `## RMn — name`
   section per open item, each with a severity/status/owner line. Also holds the freeform idea-book,
   **the reserved-namespace tracker** (Constitution Principle 5), and **the 1.0-cleanup candidate
   tracker** (Principles 3 and 8) — the two concrete lists the Constitution keeps out of itself.
   Shipped items moved to **[docs/ROADMAP_HISTORY.md](docs/ROADMAP_HISTORY.md)** with their rationale;
   [docs/RM_TOC.md](docs/RM_TOC.md) indexes both.
3. **[docs/CHANGELOG.md](docs/CHANGELOG.md)** — what actually shipped, newest first (shared across the
   ecosystem repos that consume these libs).
4. **Per-package references** — [docs/SCHEMAS.md](docs/SCHEMAS.md) (the schema tier: models, the CSV
   families, conventions, the seven hashes), [docs/COMPILER.md](docs/COMPILER.md) (the transform:
   compile pipeline, the Resolution section + its round-trip matrix, reverse, the coverage table), and
   [docs/ENRICHER.md](docs/ENRICHER.md) (the network tier: the resolver chain, Ensembl V2→V1, snapshot
   download + module upload). Read the tier your task touches.

## 0.5 enricher — current state & gotchas (read before touching resolution)

Both the **ClinVar snapshot** and the **gnomAD v4.1** work are shipped (see
[ENRICHER.md](docs/ENRICHER.md); reference example at `reference_examples/pathogenic_clinvar/`; the
design thread and the decisions in [PROPOSAL_0_5.md § G1](docs/PROPOSAL_0_5.md)). gnomAD landed as a
last-resort resolver link, a `frequencies.csv` pass, an offline-capable `gene_metrics.csv` pass, and
**GA4GH VRS allele identity**. The plan file `gnomad_4.1_enricher_a2c1ccca.plan.md` was **deleted in
0b82494** — **read the docs, not the plan**, since probing overturned several of its assumptions
(listed in the CHANGELOG entry). Recover it from git history if you ever need the original.

- **`variant_key` is the rsid FIRST, and the VRS allele id only for a coordinate-authored substitution
  (0.5) — read the precedence, not this headline.** An earlier wording led with the VRS half and a
  consumer read it as the rule, then filed "`variant_key` = rsid" as 0.4-era drift on four modules where
  it is exactly right.
  `derive_variant_key(rsid, chrom, start, ref, alts=None)` returns, in order: the **rsid**; else the
  **`ga4gh:VA.…`** id when the row is a single-base substitution with a coordinate; else
  `chrom:start:ref:alts` (alts sorted/normalized) or bare `chrom:start:ref`. Indels, MNVs,
  multi-allelic cells and off-assembly contigs deliberately fall through to the coordinate key — a VRS
  id is defined over the *justified* allele, and justifying an indel needs the reference sequence.
  Pass `alts` **only when minting a variant identity** (`VariantRow._freeze`, the one-to-many expansion
  re-key sites). Position-level **matching** — studies, `_verify`, the reverse pos→rsid lookup,
  haplotype dedup — deliberately calls it **without** `alts`, so it never mints a VA (a study matches a
  variant at `chrom:start:ref` regardless of allele). Mixing these up would orphan every study *and*
  reintroduce the same-locus allele collision.
- **`ResolutionRow.vrs_id` is ONE ID PER ALT, positionally aligned with `alts` — and the rule it used to
  follow was borrowed from the wrong function.** The mint pass abstained on any comma-joined cell,
  quoting `derive_variant_key`'s reason ("a VA names exactly one allele; picking one would be a data
  error wearing an identifier"). True *there* — `variant_key` is one column naming one thing, so a plural
  cell falls through to the coordinate key — and false for `vrs_id`, which the schema keeps **outside**
  `RESOLUTION_FACT_FIELDS`, which no identity rests on, and where nothing is picked because every ALT is
  named. `frequencies._alleles_from_resolution` had reasoned it out correctly all along, so the tier was
  answering the same question two opposite ways. It cost 909 of 1,613 rows their id on a real module
  whose 2,110 alleles were all offline-mintable substitutions. Four things not to redo:
  - **A parallel array, never one row per allele.** `resolve_from_table` groups by `variant_key` and
    reads `len(loci)` as a *locus* count, so per-allele rows would enter the one-to-many expansion path,
    and `locus_index` would carry two kinds of "many" (P5). A single-alt row still spells a bare id.
  - **An empty member is a hole, and holes are kept.** A site can carry a substitution and an indel;
    dropping the whole row's ids over the one that will not mint offline is the same abstention again.
  - **Desync is guarded twice, because a parallel array has a failure mode a scalar does not.** The model
    refuses a wrong-*length* pair at load; `_verify_vrs_ids` recomputes member by member, so a
    right-length pair in the wrong *order* is a mismatch (error in both modes).
  - **It moves nothing.** `vrs_id` is outside every signature and `reverse_module` never re-emits it —
    verified byte-identical `artifact.digest`/`content_signature`/`resolution_signature` on five modules.
- **A pass that only checks what is PRESENT must also count what is ABSENT — `_vrs_coverage`,
  `MintResult.coverage_warnings`.** `_verify_vrs_ids` verifies stored ids, so "a row with no `vrs_id` is
  skipped entirely" and a table where nothing was minted verified flawlessly. Fine for a decorative
  cross-reference, wrong for an identity a consumer may key on: coverage of an unstated fraction is not
  something anything can key on, and *unstated* is the defect. Both tiers report it, the counts land in
  `manifest.compilation.vrs_alleles`/`vrs_alleles_identified` (two counts, not a ratio or a bool — same
  reason `fully_resolved` sits beside `resolution_mode`; "complete" is derived), the denominator is
  **alleles not rows**, and gaps group by **reason class** — grouping on `_recompute_vrs_id`'s per-row
  prose produced forty lines each naming a different indel. It **warns in both modes**: an indel offline
  or a build with no refget table is fixable by no authored edit, and `strict` means "reproducible
  artifact", an unrelated axis. Generalize it: when you add a check that inspects recorded values, ask
  what it says about the records that carry none.
- **A non-nucleotide allele in `ref`/`alts` is a SPELLING defect, and the tempting repair is illegal
  three ways.** `hosting_verdict("C/T", "T", "Y")` is `False` and rightly so — a substitution locus has
  no shared flank, which is what keeps the strand-flip check sharp — but the message then blamed the
  *genotype* ("the row contradicts itself" / "the source's allele list is incomplete"), both false when
  the locus is the thing misspelled. Fixed as a **diagnosis**: `alleles.non_nucleotide_reason` /
  `non_nucleotide_alleles` classify it, both "cannot host" sites name which, and
  `cpic.unusable_allele_reason` delegates to the same function rather than keeping its copy. Do **not**
  "fix" it by adding a nucleotide grammar to `alts`: **no `ref`/`alt`/`alts` column has one** (eleven
  columns, six models; `validate_allele`'s only user is `HaplotypeRow.allele`), so a grammar rejects
  `<DEL>` and `N` too — tightening the field **RM5** exists to widen; a module with `alts="Y"` compiles
  today under `best_effort`, so refusing it breaks **P3**; and the only non-ACGT allele in real variant
  records is `N`, already filtered by `clinvar_build` at the snapshot boundary. And do not "expand"
  `Y`→`C,T`: probed across **4,439,382** ClinVar rows and all sixteen modules, `R/Y/S/W/K/M/B/D/H/V`
  appear in REF or ALT **zero** times — the compressed-ALT-set reading that argument rests on has no
  instantiation. Full probe in ROADMAP's 0.6 idea-book. Keep the two reasons' **consequences** separate
  (an uncertainty is permanent, a grammar gap is a release away); appending one to both branches is the
  CPIC conflation, and it was reintroduced once already inside its own fix.
- **Audit `validate`/`compile` parity by CHECK, not by TABLE — that is how the third instance hid.**
  `_check_allele_membership` stayed compile-only through the pass that fixed `_verify_vrs_ids` and
  `_check_p_value_num`, because that pass asked *which tables does validate read* and this check reads
  **authored** rows. It is a mode ladder, so `validate --strict` blessed modules `compile --strict`
  refused. The rule is unchanged and now applies to three checks: pure computation over injected or
  authored bytes with no `output_dir` belongs in `validate_spec` too. Two mechanics to copy when moving
  one: `compile_module` runs `validate_spec` in **best_effort** whatever its own mode, so the compile
  side must still re-run the check to reach the real severity, and its warnings need de-duplicating on
  the message (`_check_contig_ploidy` is the existing model).
- **A VA does not encode `ref`.** VRS names the place and the alt; the reference base is determined by
  the accession + interval, so it is not a digest component. Two consequences, both guarded, both of
  which must stay: the compiler has an **"inconsistent reference allele"** error (two rows sharing a key
  while disagreeing on `ref` — internal contradiction, catchable offline), and the enricher has
  `sequences.verify_reference_alleles` (authored `ref` vs the real bases — needs the sequence, so
  online only). A *single-base* wrong ref still mints the correct id, so **only** the enricher check can
  find it; a *multi-base* wrong ref mints a different allele entirely.
- **Know the validation ceiling before adding a check.** [COMPILER.md](docs/COMPILER.md) opens with
  *What the compiler can and cannot validate*: three strengthening classes it **can** do (formal
  conformance → validate-by-redundancy → content-addressed self-verification, which is the class VRS
  moved `vrs_id` into) and a table of **inescapable blind spots** that follow from what the tier is.
  The compiler is an assembler/linker, not a truth oracle: it proves well-formed and self-consistent,
  never *true*. When you find something it "should" catch, check that table first — several entries are
  permanent by charter, and what cannot be validated is instead made **legible** (`source`, `dataset`,
  `status`, `authorship.kind`, the signatures). Adding a check that needs a reference means adding it
  to the **enricher**, not the compiler.
- **Enrichment is partly validation, by design.** The enricher is the only tier that can compare
  authored data against reality (format/compiler are inject-only). Every such check **reports, never
  repairs** — rewriting an authored value destroys the evidence of an upstream bug — and severity
  follows the mode (`best_effort` warns, `strict` refuses). Add new checks in that shape; see the table
  at the top of [ENRICHER.md](docs/ENRICHER.md).
- **The compiler's VRS check has THREE outcomes, and NONE of them is a mode ladder.** *verified*
  (silent), *mismatch* (recomputed and different — **error in both modes**, since a substitution's id
  is deterministic here so a difference can only be corruption), and *unverifiable* (**could not be
  recomputed at all**), whose severity comes from **whose limit it is** rather than from the mode:
  - **the tier's limit → warning in both modes.** Indel/MNV, off-assembly contig, non-GRCh38 build.
    This escalated under `strict` for one cycle and the consequence was that the enricher's own online
    indel minting produced modules its own compiler refused — `pathogenic_clinvar` (185 alleles) and
    `shox_par1` (2) stopped compiling in the mode their READMEs print, and the skill's step 6 tells
    every author to run it. `strict` means *reproducible artifact*, and an injected indel VA
    reproduces perfectly; only the **verification** is out of reach, which is a different claim.
    Same rule as `_vrs_coverage_warnings` and `not_covered`: **a finding no authored edit could clear
    is not a `strict` matter** (P5 — orthogonal axes stay orthogonal). The old error's own remedies
    gave it away: *lower your guarantee*, or *delete a correct identity*.
  - **the row's contradiction → error in both modes.** An id recorded against no coordinate or no ALT:
    the row asserts an identity while withholding what that identity is a digest of, so nothing
    anywhere could check it. Same class as *inconsistent reference allele*, catchable offline.

  An indel is **never** a "mismatch": this tier cannot recompute one, so it can only report that it did
  not check, and saying otherwise would claim a verdict never reached. Multi-allelic is not
  unverifiable either — `vrs_id` is one id per ALT and each is checked alone. Full matrix in
  [COMPILER.md](docs/COMPILER.md). Two mechanics that came with it: `_verify_vrs_ids` takes **no mode
  argument** (there is nothing left for it to switch on), and because it runs in both `validate_spec`
  and `compile_module`, its warnings are **de-duplicated on the message** the way ploidy's already
  were — otherwise 185 alleles print 370 lines.
- **`refget_accession` RAISES for a non-GRCh38 build** (it must — a caller asking for GRCh37 should
  hear "not built", not get a GRCh38 answer). Every call site therefore has to catch
  `UnsupportedBuildError`; one that didn't used to abort a whole compile over a single row.
- **`ga4gh.vrs` is a CORE enricher dependency, not `[dev]`.** Substitution minting is stdlib in the
  format tier; indel normalization goes over the **seqrepo REST** proxy (14 pure-Python packages — the
  plan's `[extras]`/`pysam`/multi-GB-seqrepo assumption was wrong). `--offline` is the only thing that
  degrades minting to substitutions-only. Never add `ga4gh.vrs` to format or compiler: the compiler's
  verify pass is stdlib on purpose.
- **The two gene-constraint routes are different releases.** The live `gnomad_constraint` API field
  serves **v2.1.1**; v4.1 ships only in the bulk TSV. They carry different `dataset` labels, and
  `dataset` is inside the fact set. Don't "fix" a test that asserts they differ.
- **An rsID is position/multi-allelic-level, not per-allele.** One rsID (`rs33922842`) legitimately spans
  pathogenic + benign + uncertain alleles at one locus, so clinical identity keys on `variant_key`+
  genotype, never rsID. The reverse pos→rsID back-fill is therefore **allele-aware**
  (`resolver._lookup_rsid_candidates`, shared by `clinvar`): 0 allele-exact candidates → leave `rsid`
  null (don't guess); 1 → attach; ≥2 (a dbSNP merge) → deterministic pick + `status="ambiguous"` +
  `ResolutionRow.rsid_alternates`.
- **`enrich()` treats an existing `resolution.csv` beside the spec as authoritative** (merged, never
  clobbered) — and so do the two new passes for `frequencies.csv` / `gene_metrics.csv`, and VRS minting
  for an existing `vrs_id`. To regenerate after a machinery change you MUST **delete the sidecar first**,
  or stale rows silently persist (this bit me while regenerating the reference example).
- **Rate limits are load-bearing in `gnomad.py`.** 10 requests/IP/60s, so everything is batched (20
  aliases; 29 returns HTTP 400) behind a 6s pacing gate on an **injectable clock** — tests prove the
  interval without really sleeping. Per-alias GraphQL errors must never sink a batch; a *pathless* error
  must raise (it's our broken query, and swallowing it looks like "nothing found") — **except a pathless
  error that says a record is simply absent.** gnomAD answers an unknown `variantId` with
  `{"message": "Variant not found"}` and **no `path` key**, while still returning `data` with a `null` at
  that alias, so the absence is already fully expressed by the node and the error is commentary. Treating
  it as fatal made `frequencies` die with a traceback on any module carrying a variant gnomAD lacks —
  which is ordinary, and is what `VALID_FREQUENCY_STATUS.not_found` exists for. `_ABSENCE_MESSAGES` is the
  narrow exemption, matched on the message because with no path there is nothing else to match on. The
  general lesson: "pathless ⇒ our bug" was a premise about the API, not a law — check what the API
  actually does before deriving severity from a field's absence.
- **Reverse dropping `rsid_alternates` is NOT a bug — closed, don't re-flag it.** This was filed as an
  open loose end and is neither open nor fixable in the writer. `_write_resolution_csv` rebuilds the
  table from `weights.parquet`, which by design carries **no provenance at all** (it already resets
  `source="reversed"`, `status="resolved"`, blank `fetched_at`). `rsid_alternates`/`rsid_current`/
  `rsid_status` are outside the fact set *precisely* so they never reach the artifact, so the data does
  not exist for reverse to emit; adding the column names would produce a permanently empty header.
  Recovering them after a round-trip means re-running the enricher.
- **Resolution must be REVERSIBLE — read [COMPILER.md § Resolution](docs/COMPILER.md) before touching
  it.** One rule: `compile → reverse → compile` reproduces the module, or `strict` refuses. The finite
  matrix of authored-shape × mishap is enumerated and enforced in
  `compiler/tests/test_resolution_matrix.py`; a new resolution behaviour adds a row there.
  - **`authored_ident` is what makes it work.** It records which of `{rsid, chrom, start, ref, alts}`
    the author supplied, stamped at load beside `variant_key` and materialized to `weights.parquet`.
    Reverse re-emits exactly that shape. `variant_key` **cannot** substitute for it: it answers "which
    variant is this", not "what did the author write" — identical for an rsid-only row and an
    rsid+coordinate pair, and after expansion it is the per-locus allele id with no trace of the rsid.
  - **An expansion collapses back to ONE authored row on reverse.** Until 0.5 it emitted N position-only
    rows, which moved `content_signature` on every rsid-authored module *and* wrote each locus out
    carrying the single authored genotype — fabricating annotations for loci that genotype cannot
    describe (three such rows in `reference_examples/pathogenic_clinvar/`).
  - **A locus that cannot host the authored genotype is dropped from the expansion**
    (`resolution.hosting_verdict`). The predicate is **shared three ways** — the compiler, the enricher's
    deprecated DuckDB path (digest parity is a documented guarantee) and `enrich()`'s forward
    rsid→loci resolution, which since this round leaves such a record out of `resolution.csv`
    entirely. Resolution is allele-aware in BOTH directions now; the reverse back-fill always was.
  - **`withdrawn` refuses in BOTH modes**, unlike `merged`/`absent` (strict-only). Nothing automated
    emits it — the API cannot tell a retraction from a never-assigned id — but it is a real vocabulary
    member for curator-recorded retractions and for a future source. Don't drop it as dead code.
  - **`ambiguous` is stable and still refuses in strict.** The enricher writes ONE row (deterministic
    pick + `rsid_alternates`); a two-row fixture is fabricated and will invent an instability that does
    not exist. Strict refuses because a pick among equals is not a finding, not because anything is lost.
- **The allele-membership check compares against the UNION of every locus a key resolves to**, on the
  authored rows before `resolve_from_table` — a per-expanded-row comparison flags the siblings the
  genotype was never about. Severity is the mode ladder, never an unconditional error. Pinned by tests.
- **The ClinVar `clin_sig` cross-check is the one check where `strict` does NOT escalate** — it warns in
  both modes, deliberately, because failing would make the format arbitrate a clinical dispute. The
  reason is documented at the call site; don't "fix" the inconsistency.
- **`absent` for an rsID means typo *or* withdrawn, and the API cannot separate them.** `rs11273140`
  (withdrawn) and `rs2000000000` (never assigned) return byte-identical responses, so
  `identifiers.classify_rsid` answers `absent` and the message names **both** readings rather than
  guessing — a typo is fixed, a retraction may leave the annotation describing nothing. A test asserts
  the equality on the *recordings* so a future dbSNP release that separates them fails loudly.
  **`VALID_RSID_STATUS` is `{live, merged, absent, withdrawn}`** — four members. This bullet used to say
  three, on the reasoning that nothing could ever produce the fourth, and that is the confusion to avoid:
  "nothing emits it today" is a fact about the live API, while the member exists for the two cases the
  API is not the authority on — a curator who has *established* a retraction records it by hand, and a
  future source that can tell the two apart starts emitting it without a vocabulary change P3 would
  otherwise make a one-way door. Its severity is not `absent`'s either: see the `withdrawn` bullet under
  Resolution, which is fatal in **both** modes.
- **Existence vs retrievability for citations.** A paywall hides the *fulltext*, never the PubMed
  record — `exists` is answered for paywalled work. The real gaps, both now covered: citations PubMed
  does not index at all (preprints/books/datasets → **Crossref**, checking the *authored* DOI, since
  the derived one exists by construction) and quote-checking for paywalled papers (→ the **abstract**,
  which Europe PMC serves for non-OA records in the same response). `quote_source` records how far the
  search reached because a hit and a miss are not symmetric — an abstract miss is not a verdict.
  Google Scholar is rejected, not deferred: no API, and automated querying violates its terms.
- **A thread-based regex timeout is a trap.** `re` cannot be interrupted, threads cannot be killed, and
  the interpreter joins `ThreadPoolExecutor` threads at exit — so the obvious implementation returns
  `None` on schedule and then hangs the process on the way out. `literature.regex_matches` uses a
  killable child process. Don't "simplify" it back to a thread.
- **For rsID merge status, NCBI is the oracle — not Ensembl.** Ensembl resolves *some* merged rsIDs
  (`rs77121243` → `rs334`) and returns **HTTP 400 on others** (`rs3216883`, which dbSNP correctly
  reports as merged into `rs3051860`), so Ensembl alone would misclassify a merged rsID as
  unresolvable. `esummary db=snp` is batched and authoritative: `snp_id` != requested + `merged_sort=1`
  means merged, an `error: "cannot get document summary"` record means absent. **No live endpoint
  reports a distinct "withdrawn" state** (the *vocabulary* has one — see the `absent` bullet above): an
  rsID retracted for mapping/clustering errors (`rs11273140`) is byte-identical
  to one never assigned (`rs2000000000`) across esummary, esearch and Ensembl, so a message about an
  absent rsID must name *both* readings — typo vs withdrawn-and-the-annotation-may-be-worthless — and
  assert neither. (`misc/rs_unsupported_b157.txt` looks like a withdrawn registry and is not; it is a
  one-off build-157 ClinVar-parsing incident list.) And when picking a negative-test rsID, check it:
  `rs999999999` looks synthetic but is a real variant at chr6:58247859.
- **An UNREACHABLE source is unchecked, never absent — and the artifact must not say otherwise (S20,
  0.5.4).** `EnsemblResolver.resolve_rsid` returned `([], None)` both when Ensembl answered with no
  GRCh38 locus and when the request never completed, so a failed lookup rendered as a definite negative:
  `loci: []` plus "live Ensembl has no GRCh38 locus for it either". That pair is exactly the fingerprint
  of a **fabricated** rsID, and a consumer auditing a machine-written document put two published
  variants (`rs6567160`, a long-standing MC4R BMI locus, and `rs13010010`) in the fabricated pile on a
  flaky run. Three outcomes now: loci, `[]` for an answered absence (carrying its source, so
  `hint.checked` records *which* link said nothing), `None` for could-not-ask. Three things to keep
  straight. **A 4xx is an answer** — Ensembl 400s on rsIDs it cannot resolve — so only a 5xx, a
  transport error or a timeout is unchecked. The **artifact half was worse and invisible from
  `lookup_variant`**: `enrich()` wrote `ResolutionRow(status="not_found", source="ensembl")` for a
  request that *failed*, stating in the injected table that Ensembl was asked and said no. No row is
  written now — the key stays `unresolved`, so `strict` still refuses and `best_effort` still warns, but
  nothing claims a source answered — and `EnrichmentResult.unreachable_rsids` names them, distinct from
  `unresolved`, which is silent about why and so cannot tell a re-runnable failure from a real absence.
  It **warns in both modes**: no authored edit clears a failed request (P5, the `not_covered` class).
  And the argument was already four lines below in the same function, where the non-GRCh38 branch
  declines to write `not_found` for precisely this reason. Generalize it: **when a function has two ways
  of returning nothing, check whether any caller renders them as one sentence.**
- **Two true halves can make a false row — check the RELATIONSHIP, not the members (S24, 0.5.4).**
  `variants.csv` carries a `gene` column and nothing compared it to anything: `identifiers` asked HGNC
  whether a symbol was *approved*, which is a different question (`FTO` is approved whatever variant
  sits beside it), so a row pairing a real gene with a variant on another chromosome passed every check.
  Four of a reporter's seven rows were exactly that — real symbols beside invented rs numbers, which
  resolve anyway because dbSNP is dense enough that almost any seven-digit number hits something.
  **Machine-written sources are a real authoring input now, and this is the shape they fail in.**
  `check_identifiers` reports `GeneLocusConflict` per row and repairs nothing (which of the two halves
  is wrong is not knowable here). Four design points, none of which should be "improved":
  **chromosome granularity only** — the stronger interval version is refused in the code using the
  reporter's own argument, since `rs1421085` sits in an FTO intron and acts on *IRX3*/*IRX5* megabases
  away, so a row may legitimately name any of the three and an interval check would fire on correct rows
  until someone switched it off (a test pins that the FTO row stays silent). The join is against HGNC's
  **cytoband** (`16q12.2` → `16`, `mitochondria` → `MT`) and anything unparsed yields `None` rather than
  a guess, because a guess here becomes a false accusation about a row. For an rsID-only row the
  chromosome comes from an **injected `resolution.csv`** beside the spec and nothing is fetched — a
  currency check must not depend on a resolver. And a **pseudoautosomal** gene is exempt: `XG` straddles
  the PAR1 boundary, so X/Y there is a spelling, not a contradiction (RM32).
  `gene_loci_not_checked` carries the reason when the comparison could not run — same rule as
  `clin_sig_not_checked`, because an empty conflict list otherwise says both "compared everything" and
  "never compared".
- **Network tests are opt-in:** `JUST_DNA_NETWORK_TESTS=1` runs the live gnomAD query, the seqrepo
  refget re-derivation, and indel-normalization round-trips. They pass; they just aren't run by default.
- **PharmGKB is now ClinPGx, and every PGx upstream is research-only.** `api.pharmgkb.org` was
  **retired 2026-07-20** and no longer resolves; the successor is `api.clinpgx.org` with paths and
  formats unchanged. ClinPGx is the umbrella that merged PharmGKB + CPIC + PharmCAT, so **CPIC is not
  an unrestricted alternative** — `cpicpgx.org/license/` 302-redirects to the ClinPGx data usage
  policy. All three sources (ClinPGx, CPIC, PharmVar) are **CC BY-SA 4.0 plus a contractual no-sale
  clause**, so none is sellable: don't read a bare "CC BY-SA" line as permission to sell, read the
  surrounding terms (`docs/pharmvar_lic.txt` §3 is the PharmVar one). Ensembl/dbSNP already cover
  rsID→coordinate, so never wire ClinPGx/CPIC as a resolution link — that keeps the coordinate layer
  unrestricted. PharmVar needs an **`Api-Key:` header** (not `X-API-KEY`) at **2 rps**, and its ToS §2
  makes the key personal — never bake one into a module, fixture, or snapshot. API schema:
  `docs/pharmvar_api_docs.json`.
- **PharmGKB clinical annotations are per-genotype — `(variant_key, drug)` is not a key.** 4,618 of
  5,113 carry exactly three genotype rows, sometimes opposed (rs4149056/simvastatin: CC/CT
  "decreased", TT "increased"), so `PharmVariantRow.genotype` is in the dedup key. Its grammar lives
  on `AuthoredModel` — shared with `VariantRow`, so don't re-declare it. Route haplotype-keyed
  annotations (`*1`) to `DiplotypeRow`; skip symbolic alleles (`del/del`, 177 rows) as **RM5** rather
  than widening the nucleotide grammar. PharmGKB writes `CC`; canonical form is `C/C`, since `CC`
  would otherwise parse as a single two-base allele — disambiguate using the *resolved* ref/alt.
- **`(variant_key, drug, genotype)` is STILL not a PharmGKB key** — one variant+drug carries several
  distinct annotations (rs4149056+simvastatin is Metabolism/PK 1A, Efficacy 3 AND Toxicity 1A). 1,199
  of 17,380 triples collide; 839 separate by `phenotype_category`, 283 only by `annotation_id`. The key
  is `(variant_key, drug, genotype, phenotype_category, annotation_id)`. **Any code that indexes
  ClinPGx by the bare triple has this bug** — the first cross-check did, and reported correctly-authored
  levels as stale. Look it up by `annotation_id`, then category, and report ambiguity rather than
  comparing against an arbitrary candidate.
- **Read snapshots with duckdb, not polars — but NOT for the reason this bullet used to give.**
  `polars` is `[dev]` in the enricher (builders only) and `duckdb` is core, so the convention is: builder
  in polars, runtime pass in duckdb. `clinvar.py` had it right; `clinpgx.py` first read its snapshot with
  polars. **The stated justification was checked in the 0.5 audit and is false**: `just-dna-compiler`
  requires `polars` *unconditionally* and the enricher requires the compiler, so polars is present on
  every enricher install and no runtime pass was ever unusable on a plain
  `pip install just-dna-enricher`. Keep the convention anyway — it is what keeps the enricher's declared
  dependency set honest about what its runtime actually needs, so the tier could stop pulling polars
  transitively without every pass breaking — but do not repeat the broken-install claim, and do not
  reason from it when judging a new pass.
- **Every gated source now has a cache, and PharmVar's is deliberately unpublishable (RM38, shipped in
  enricher 0.5.1).** The three PGx sources were the only `commercial_use=False` entries *and* the only
  ones with no cache — the same set, because every ungated link was already snapshot-first. A hosted
  surface therefore had two options, fetch live per request on the operator's own credentials or skip
  the check. Six things to keep straight now that it is built:
  - **The route is snapshot → live → skip-with-a-reason, and `--offline` means the first only.**
    `PgxResult.routes` records which answered and a snapshot stamps its release into `SourceRow.dataset`
    (the gnomAD-constraint precedent: a consumer must be able to tell a pinned file from a live API).
    `skipped_offline` is a third state, never a silent pass.
  - **`clinpgx` provisions automatically; `pgx`/`draft` fall back to live.** Not an inconsistency —
    ClinPGx has no live route at all (the API was retired), so there is nothing to degrade to, while
    downloading a whole database to answer one gene is the wrong default for an author on a laptop.
  - **`offline` outranks an injected client, decided on the TYPE not on `configured`.** A live client
    under `--offline` would egress from a run documented as making none; a snapshot client is exempt
    because reading a local parquet is not egress. A live client with a perfectly good key is exactly
    the one that must not be used there.
  - **No `ensure_pharmvar_snapshot`, no `pharmvar publish`, ever.** Its bulk data comes under a key its
    terms §2 make personal and non-transferable, and `redistribution=True` describes the CC BY-SA grant
    over the *content*, not a clause about the *account* — an unestablished permission is not a
    permission. Also still don't add a `SourceRow` column for research-use-only — not because of the
    version (an optional column is minor-legal since the 2026-08-11 amendment) but because it belongs to
    RM27's design round: a *distribution* right is not a *use*, and the axis has to be designed once.
  - **The builders store values verbatim and map at READ time.** `cpic_build` writes CPIC's own prose
    (`"No function"`, `"Strong"`) and the snapshot client calls the same `map_function_status` /
    `map_classification` the live client does — so a mapping fix reaches an already-built snapshot, and
    the two routes return the same object by construction rather than by inspection. Same rule for
    `unusable_allele_reason`: it is a *judgement this workspace makes* about CPIC's value, so freezing
    it into the parquet would pin one release's opinion into every snapshot built under it.
  - **A flattened JSON map must carry what the flattening lost.** `recommendation.phenotypes` is a
    `{gene: phenotype}` dict and the live client keeps only single-gene rows; the snapshot is one row
    per gene named, so `gene_count` travels with it and the reader applies the identical rule. Without
    it, flattening silently promotes multi-gene recommendations.
- **A negative finding about a source is only as wide as the table you looked at — say which.** The
  comment "CPIC publishes no chromosome" was true of `sequence_location` and false of CPIC: `gene.chr`
  has it, and the drafting provider had been skipping 36 real defining variants (18 CYP2C9, 14 TPMT, 4
  NUDT15) for a year on the strength of a probe that named no table. Joining `gene.chr` on the symbol the
  location row already carries is a **lookup in the source's own tables**, not the inference the original
  comment rightly refused — that distinction is the whole difference between the two.
- **A source that publishes both assemblies will list the wrong one first.** PharmVar emits each defining
  variant once per reference sequence — transcript, GRCh37, GRCh38 — with **GRCh37 first**, and
  `_merge_variants` was first-wins, so 451 of 739 rsID-keyed variants carried a GRCh37 coordinate. The
  accession *version* cannot separate them (chr10 is `.10`/`.11`, and so is chr22); `referenceCollections`
  can. Two durable points. **Filter on the field that names the assembly, never on the accession.** And
  it was latent for a release because nothing consumed `PharmVarAllele.variants` — **a snapshot is what
  turns a latent wrong number into a written one**, so re-check every parsed-but-unused field the first
  time something persists it. `pharmvar.PHARMVAR_GENOME_BUILD` is the named constant (fourth build
  confusion here; `gnomad.FREQUENCY_GENOME_BUILD` is the precedent).
- **A credential must be loaded where it is read.** `PharmVarClient` read `os.environ` and `.env` only
  ever reached it as a side effect of some *other* call resolving a cache path — which worked for
  `enrich_pgx` by accident and not at all for `pharmvar build`, which resolves nothing and reported "no
  PharmVar API key" on a machine that had one. `load_env()` now runs in `__init__`, `override=False`, so
  a real environment variable and a test's neutralizing `""` both still win.
- **A flag must mean the same thing in every function that takes one (RM39).** `enrich_dosage_sensitivity`
  was the only pass without `offline`, so a caller running the family under one switch had to know, out
  of band, that one member ignored it — and the cost of forgetting was silent egress from a path the
  docs call zero-egress. The shape to copy is `enrich_frequencies`: a **no-op with a warning**, reported
  as `skipped_offline`, which is a first-class answer distinct from "ran and found nothing" and from a
  failure. An *injected* payload (`curation_text=`) still wins — handing over bytes you already hold is
  not egress, and refusing it would break the inject-only escape hatch. Corollary from the same round:
  **"a flag with one legal value" is a claim about the current wiring, not about the function.** That
  was the standing reason `enrich_clinpgx` had no `offline`, and RM38 gave it a second value the same
  week — re-ask the question whenever the wiring changes.
- **A number this workspace computes and discards gets recomputed by every consumer (RM40/RM41).** Two
  instances, one argument. `enrich()` computed the `MintResult` the compiler later stamps into the
  manifest and dropped it, so a pre-compile consumer re-implemented per-ALT-slot counting and could
  disagree with the manifest a publish would produce; it is now `EnrichmentResult.vrs` (`None` when the
  pass did not run — never a coverage of zero). And `_load_csv_rows` was the only correct authored-CSV
  loader *and* private, so a consumer chose between a private symbol and a re-implementation with two
  known traps; it is now `compiler.load_csv_rows`, with `compiler.load_spec_variants` for the
  build-injection-and-restamp, and `verify_acmg_sf`/`check_identifiers` take `spec_dir=` beside
  `variants=` (**exactly one, never both** — a caller passing both has two answers in mind). Before
  logging a computed value and returning, ask whether a caller would have to recompute it.
- **A constant two deployment shapes want different values of is a knob (RM42).** Nine
  `stop_after_attempt(3..4)` were decorator arguments evaluated at import, so a *server* inside an
  unattended publish could not ask for more persistence than an author at a terminal wants — and a
  consumer was walking the package reassigning `policy.stop`. `net.attempt_floor` reads
  `$JUST_DNA_HTTP_RETRY_ATTEMPTS` per call. Two shape rules worth reusing: **a floor, not a flat set**
  (the per-client differences are deliberate — gnomAD and eutils are at 4 because their budgets are
  tightest — and below a client's own default it is a no-op, since nothing wants *less* persistence),
  and **leave a composed policy alone** (`stop_after_attempt(3) | stop_after_delay(60)` means both, and
  raising one term changes something whose author meant the conjunction).
- **A machine-written sidecar has two legal names and two legal places — never join one onto a spec
  directory by hand (RM51 + RM49, 0.6).** `just_dna_format.layout` is the single resolver, in the schema
  tier because *four* parties must agree: compiler reads, enricher writes, publisher uploads, registry
  re-splits. The licence table is `licensing.csv` (the old `sources.csv` is deprecated, warn-only,
  removed at 1.0), and any of the five sidecars may sit under `derived/`. Four things to keep straight:
  - **Write to the file you read** (`layout.sidecar_write_path`, `licensing.sidecar_path`). Writing the
    current spelling onto a module carrying the old one — or the root onto a split module — leaves two
    copies, which is the refusal below, arrived at by following the documented workflow rather than by
    misuse. This is the load-bearing half; tolerating a location on *input* alone breaks on first use.
  - **Both present is an ERROR naming both paths.** No merge, no newest-wins: these tables are
    fact-hashed *and* human-overridable, so two copies are two legitimate claims and preferring one
    discards a curator's override.
  - **Only the machine-written tables move.** `variants.csv` and the table kinds have one name in one
    place; two legal homes for an authored table means a module can carry two with the ignored copy
    invisible. And **`_check_misspelled_tables` had to learn `derived/`** — tolerating a location
    without extending the guard puts a typo'd `derived/varaints.csv` exactly where the check written to
    catch it cannot see. That is also why "search any subdirectory" was refused.
  - **The outputs did not move**: still `sources.parquet`, still `manifest.sources`, both major-only
    renames. The 0.x tail reads `licensing.csv` → `sources.parquet` → `manifest.sources`, knowingly.
    Neither the name nor the location enters any identity — measured on all eleven reference examples.
  RM51 estimated five enricher write sites; there were **nine**, which is why `record_source_terms` and
  `merge_sources_file` take the **spec directory** now. A count of call sites is exactly the thing that
  goes stale; routing them through one function is the durable form.
- **Licensing lives as DATA in the licence table, never as a table in the compiler.** A source→licence map
  in `just_dna_compiler` would give it a source convention (Principle 2, tightened in 0.5) and an
  un-injected reference — and it goes stale (both halves of one did inside 0.5). The enricher reads the
  terms from the bytes it downloaded and pins them with `license_sha256`. Three rules the tests pin,
  don't "simplify" any of them: **only the `annotation` layer taints** (a coordinate is a fact Ensembl
  reports identically, so marking it viral is a false positive); **most-restrictive-wins module-wide**
  (a permissive source can't launder a restricted one); and **`None` ≠ `False`** on
  `share_alike`/`commercial_use` (unknown terms are undetermined, never permitted).
- **A pass that consults a source must WRITE its `SourceRow` — use `licensing.record_source_terms`.**
  Building the row is half the job; the compile gate and `manifest.sources` read `sources.csv` and
  nothing else, so a row that is only returned is a source the module cannot account for. `clingen.py`
  returned one and never wrote it — permissive terms (CC0) made it look harmless, but CC0 still asks
  for attribution and the table exists to carry it — and then `enrich`/`frequencies`/`gene_metrics`
  turned out to write nothing at all, which is why `VALID_SOURCE_LAYERS` had reserved members no file
  ever carried. `record_source_terms(names, layer, path, error=…)` maps source names → terms → rows and
  does the load-merge-write (over `merge_sources_file`) in one place; don't grow a private copy.
  Corollary: **a fact-layer row cannot taint a module**, so what it carries is *attribution*, which is
  as much the table's purpose as the prohibitions are.
- **A column list written by hand will lose a column — derive it from the model.** `SOURCES_FIELDNAMES`
  was a literal and omitted `redistribution`, so every `sources.csv` ever written recorded *unknown* for
  an axis the terms constants state as `True`, and `merge_sources_file` dropped it again on each merge —
  RM27 is a gate designed to read a column that had reached no file. `SourceRow` has no
  compiler-stamped fields, so `list(SourceRow.model_fields)` is exactly right there. Where a model
  *does* have stamped fields, that is what `base.authored_field_names` and the `COMPILER_MANAGED` marker
  are for — the rule is the same one, never hand-keep a list of a model's columns.
- **`source` names the licensed source in every fact table; only `resolution.csv` also records the
  link.** `resolution.csv`'s `source` is *which link answered* (`ensembl-rest`, `cache`, `clinvar`) and
  `authority` is what `sources.csv` joins on (`ensembl`, `clinvar`, `gnomad`), empty for
  `authored`/`reversed`/`manual` because the module's own bytes are not a licensed source. The
  link→authority map (`licensing.RESOLUTION_AUTHORITY_BY_LINK`) lives in the **enricher**; the same map
  in the compiler is the un-injected-reference mistake one bullet up. `gene_metrics.csv` had the same
  overloading (`gnomad-constraint`/`gnomad-api` are routes, not sources) and was fixed the other way —
  it records `gnomad`, and the route stays in `dataset`, which is inside the fact set where `source` is
  not. This was RM33.
- **A layer with no `source` column to join is exempt from the orphan check, structurally — and that is
  now TWO layers, not one (S23, 0.5.4).** "No table used it" is decided by reading fact tables' `source`
  columns, and `annotation` *is* `variants.csv`/`diplotypes.csv`, which carry none — so the check
  reported the one row the licence gate keys on as probably stale, on every drafted module. `literature`
  joins the exemption by the identical argument whenever the module carries `studies.csv` rows
  (`_source_checks(..., literature_evidenced=…)`, `uncorroborable = {"annotation", "literature"}`):
  `studies.csv` is the hand-curated literature table and has no `source` column *by the same design*, so
  a `pubmed`/`europepmc` row can only be corroborated by the enricher-written `literature.csv`, and a
  module with none has nothing to join. Note which way the old behaviour pushed an author:
  `MISPLACED_COLUMN_REASONS['source']` tells them to declare a hand-read source as a `sources.csv` row,
  and doing so earned a warning that the row was unused, while **deleting** it — shipping with the
  provenance unrecorded — was silent. Compliance warned, omission quiet. Narrow by construction:
  `frequency` still warns, because `frequencies.csv` *is* machine-written with a `source` column, so a
  frequency declaration in a module with no frequencies really is stale. Don't "restore" either half.
- **The compile gate is data-driven; a `--non-commercial` CLI flag would be charter-illegal.** It
  refuses when an annotation-layer source forbids sale and the module records no declaration, reading
  only injected `sources.csv`. A *flag* cannot be recorded in the artifact — `reverse_module` rebuilds
  `module_spec.yaml` from parquet alone — so `compile → reverse → compile` would refuse on the third
  step (P7). The gate sits immediately before `output_dir.mkdir()`, which is why `sources.csv` is
  parsed there rather than with the other fact tables (they load after mkdir). It refuses in **both**
  modes; `strict` means "reproducible artifact", an unrelated axis (P5).
- **`declared_use` (`--use`) is a THIRD axis, not a mode.** `mode` says how hard to fail on a finding;
  `declared_use` says who is using the data. Three states, so not a bool pair — defaulting either way
  would make the tool assert a purpose for the user. A forbidding source is *skipped* on `unstated`
  and *refused* on `commercial`, at acquisition (nothing is fetched), in both modes.
- **The Ensembl snapshot's `alt` is PIPE-joined; every other link uses commas.** A multi-allelic site
  is one snapshot row (`A|C|T`), not one row per alt. `resolver._snapshot_alleles` normalizes at that
  boundary — don't remove it, and don't "fix" it by widening the hosting predicate instead (the locus-dict
  contract is comma-separated, and the snapshot is the deviation). This silently broke *all*
  cache-resolved genotyped variants until 0.5: the comma-only split made `A|C|T` one opaque allele, so
  the allele-aware filter dropped every locus and `rs4244285` with genotype `A/G` came back
  `not_found`. Unit fixtures were comma-separated, so only a real cache showed it — when adding a
  resolver fixture, use the pipe shape for multi-allelic sites.
- **Resolution reads `pharm_variants.csv` and `haplotypes.csv` too, not just `variants.csv`** (0.5,
  `enrich._collect_subjects`). PGx modules carry no `variants.csv`, so they used to enrich to an empty
  `resolution.csv`. Subjects dedupe by `variant_key` with **`variants.csv` first** — it alone carries
  `alts`, a fact column, so a PGx row winning would move `artifact.digest`. PGx tables key **without**
  `alts`; a `HaplotypeRow` passes its defining `allele` to the shared `hosting_verdict`.
- **Every `start` in this codebase is the 1-based VCF position — do NOT convert.** The pipeline stores
  Ensembl's position (`rs1135071` → 5226799 everywhere), CPIC `sequence_location.position` and PharmVar
  `NC_……:g.` use the same convention, and `derive_vrs_allele_id` does the interbase conversion itself,
  once. The instinctive `-1` introduces an off-by-one. **This bullet used to open "Despite the `start`
  docstring saying 0-based" — that docstring was the bug, and it was fixed on 2026-08-06 only after it
  had cost someone 3,038 rows.** `describe`/`requirements`/`reference` print those descriptions, so they
  are the authoring contract, not internal commentary; an external author followed them, shifted four
  whole modules by one base, and every offline gate passed (`--strict` included, VRS ids minted *and*
  reported verified — a content-addressed id is a correct digest of the wrong input). Two durable
  lessons. **A known-but-unrated inconsistency in a printed contract is a live defect, not tidiness** —
  it sat in the ROADMAP as a low-severity blocker for the `end` column precisely because nobody had
  watched it produce a wrong module. And **Class-2 validate-by-redundancy assumes independence**: those
  modules shipped their own hand-built `resolution.csv`, so `resolution._verify` compared the author's
  convention against itself and agreed. `schema/tests/test_coordinate_convention.py` now pins the prose
  to what the minting code does with the number. Two more CPIC traps: `variantallele` carries values `HaplotypeRow.allele`
  rejects, in **two different kinds** that must not be conflated — **IUPAC ambiguity codes** (`R`), an
  uncertainty CPIC recorded and never expressible, and **deletion/repeat notations** (`DELTCT`,
  `AAAGGGGCG(2)`, 23 in CYP2D6), a grammar gap (RM5) a release could widen; `cpic.unusable_allele_reason`
  names which, and calling the second an ambiguity code was a false claim that survived until a real
  CYP2D6 draft. And activity scores are **inequality strings** (`"≥3.0"`), not numbers, so they don't drop
  into `MeasureBinRow`'s numeric bounds.
- **A "ref mismatch" has three causes, and the coordinate one is the common one.** `verify_reference_alleles`
  reads **one window** spanning a base either side of the claimed span (not three reads — the rows needing
  the diagnosis arrive in thousands) and reports a shifted `start` when exactly one neighbour carries the
  authored `ref`. Both neighbours matching is ambiguous, so it withholds — tri-state, as everywhere else.
  Don't "improve" it by inferring the direction from the module's dominant shift: that is a per-row claim
  built from an aggregate. A shifted row sets `distorts_the_allele_id` **whatever the claimed length**,
  because the id is minted at the authored position; the old length-only test plus its reassurance ("the
  minted allele id is still the true allele at this position") was true of the recorded position and
  worthless when the position is the defect. Sensitivity is structurally partial (~3 rows in 4 — a
  neighbour that happens to equal `ref` hides it), and both docs say so rather than implying a clean bill.
  Findings are grouped by **reason** via `summarize_ref_mismatches`; 56 lines became 2 on a 69-variant
  module.
- **`content_signature` hashes a variant row's EFFECTIVE `curator`/`method`/`priority`, not its cell
  (RM37, shipped).** `defaults:` in `module_spec.yaml` and a per-row cell are two spellings of one value,
  and `reverse_module` re-emits it in the other place (it infers the module default via `_most_common`
  and blanks the matching cells), so hashing the cell made `compile → reverse → compile` move the
  signature. `compiler._resolve_spec_defaults` folds the defaults in first. **The normalization is the
  load-bearing part and must not be "simplified": a value equal to the `Defaults` model's own field
  default is written back as `None`, so `exclude_none=True` omits it** — the same trick RM36 used for
  `genome_build`, and what keeps existing signatures byte-identical (one of eleven reference examples
  moved). It also fixed an unfiled defect: `defaults:` previously reached the hash by no path at all, so
  two modules differing only in `defaults.curator` hashed **equal**. `priority` needs no special case —
  its model default is `None`, so an unset one stays omitted, and `reverse` still rightly refuses to
  infer a `priority` default (that would fabricate a value for rows that never set one). No reference
  example could catch any of this: all eleven use `defaults:`, so an externally authored module found it
  — the same corpus-uniformity lesson as RM36, on the axis "where the author chose to write it".
- **A large star-allele gene is drafted with `draft --allele`, and the filter covers all three tables.**
  Unfiltered CYP2D6 is 16,290 diplotype rows (73% `Indeterminate`); the author's real bound is the allele
  set their caller emits, and *n* alleles is *n(n+1)/2* pairs. Filtering `diplotypes.csv` alone would
  leave a module naming alleles `haplotypes.csv` never defines — the thing
  `_cross_validate_haplotype_definitions` warns about — so `_selected_alleles` gates the defining
  variants and the function rows too. `*1` is always kept (defined by carrying no variants; without it
  `*1/*2` is undraftable), an unknown name refuses with CPIC's list, and the flag takes a single `--gene`
  because a star name is gene-scoped. This was RM34. When counting what a filter dropped, count over the
  rows the filter actually judged: tallying the copy-number rows it deliberately passes through read
  "567 of 16836" for a six-allele set.
- **A new OPTIONAL column is minor-legal, and the "digest window" that said otherwise rested on a
  premise that expired in 0.4.1.** The charter now states the rule (P3/P4): a new optional column or
  table is additive; **removal, promotion to required, and retyping** are the major-only moves,
  because those are what break a reader or invalidate published data. Two mechanics behind it, both
  measured rather than argued:
  - **An unset optional column is omitted from `content_signature`** (`model_dump(exclude_none=True)`)
    and the per-input hashes cover authored bytes nothing rewrote — so adding one leaves the **authored**
    identity byte-identical. Only a *recompile's* `artifact.digest` moves, and P4 already scoped that to
    a fixed `compiler_version`. Verified on `pgx_slco1b1_simvastatin`: `content_signature`
    `8173dab7…` unchanged, inputs unchanged, `artifact.digest` `3375adef…` → `cd687baf…`, and
    `compile → reverse → compile` still a fixed point.
  - **`integrity.file_entries` skips missing files**, so a new optional *table* does not even move the
    digest of a module that does not carry it. Still true, and now the weaker of the two facts rather
    than the whole argument.

  **The history, since the charter no longer carries it.** `artifact.digest` (2026-07-06) was the only
  identity when the Constitution was written (2026-07-08), so it carried both jobs — *which bytes are
  these* and *which content is this* — and "a column change is major-only" followed honestly. 0.4.1
  (2026-07-23) split the second job into `content_signature`; the clause was never revisited, and every
  "that column is a 1.0 item" deferral in the living docs descended from it. Amended 2026-08-11. What
  this does **not** license: a required column, a retype, a removal, or filling values into an existing
  column (that one is `reverse`'s problem — see RM43).
- **Adding an authored column is exactly three touch points, and the third is the one that gets
  missed.** The pydantic model; the compile-side row dict + polars schema in `compiler.py`; and the
  **reverse-side `fieldnames` list + `_scalar_cell` mapping**. A column missing from the reverse list
  round-trips as silent data loss, which is why every new column gets a round-trip test. Table kinds
  under `_TABLE_KINDS` are exempt — `_build_table`/`_write_table_csv` are generic over `model_fields`,
  so `DiplotypeRow.recommendation_strength` needed no compiler change at all.
- **`model_fields` is NOT the authored surface — generators must use `base.authored_field_names`.**
  `VariantRow.variant_key` and `authored_ident` are declared fields (carried in memory, materialized
  to `weights.parquet`) that the compiler *stamps* and `reverse_module` deliberately never writes
  back. Anything that turns a model into CSV columns for a human — `draft.blank_template`,
  `draft.append_rows`, `reference.authoring_reference` — has to skip them, and it must skip them by
  the field's own `COMPILER_MANAGED` marker, **never by name**: `FrequencyRow.variant_key` is the same
  name and is genuinely authored and required, so a name set hides a column an author must fill. Both
  hand-kept exclusion lists that preceded the marker were wrong — `reference.py`'s named only
  `variant_key` and never learned about `authored_ident`; `draft.py` had none, so it wrote a
  `variants.csv` the compiler then refused to load (`authored_ident` renders as `rsid` and does not
  reload as a `list[str]`). The bug survived a green suite because every drafting test used a PGx or
  binning table, and no model but `VariantRow` has a stamped field. **When adding a drafting provider
  or any new model-driven generator, test it against `variants.csv` specifically.**
- **A closed vocabulary accepts `-` where `_` goes, and canonicalizes — `vocab.match_vocab` (0.6).**
  The enricher CLI normalized `--use non-commercial` on its way in while `SourceRow` refused the
  identical string in a cell, so the surface an author learns the vocabulary from taught a spelling the
  file rejected. A separator slip is *the* slip a hand-written CSV makes, and the human-authorable gate
  says the schema absorbs that cost rather than charging it. `check_vocab` runs the matcher, so every
  vocabulary gets it and nothing keeps a private copy — the CLI's `_use` delegates now. Three
  properties to preserve: the value **as written is tried first** and both swap directions after (a
  future hyphenated member cannot be broken by this); the match **returns the declared member**, so
  what is stored, fact-hashed and compared is never two spellings; and it **widens only** (P3), so a
  value that names nothing still fails with the full list. How sure we are it was worth doing:
  `test_validate_agrees_with_compile` had been using `non-commercial` as its example of an *invalid*
  value.
- **A vocabulary binding lives on the FIELD, and it carries the members — `base.vocabulary`.** The
  authoring reference's vocabulary block used to be a hand-kept dict and drifted twice: it never
  learned about `recommendation_strength`/`phenotype_category` (0.5), and it filed `actionability`
  under `open_recommended` while `VariantRow` *rejects* a non-member — a drift in **closedness**, not
  membership, which is why the marker carries a `closed` flag and not just a list. The marker holds
  the frozenset's members rather than a name to look up, because a registry in `vocab` cannot import
  `pgx` (the cycle `base`'s dependency note exists to avoid) and a registry elsewhere is a second
  hand-kept list. Rule for where a binding goes: **wherever its validator is** — shared validator →
  `base.SHARED_VOCABULARIES`; model-specific validator → that model's `Field(...)`. Never mark a
  field nothing enforces: `StudyRow.chrom` and the PGx `chrom`s run no chrom validator, so they carry
  no marker, and the guard test catches it in both directions.
- **A guard that iterates a model registry is only as complete as the registry — and one omission hid
  another (S21, 0.5.4).** `SourceRow.layer` and `.declared_use` ran closed-vocabulary validators while
  carrying no `vocabulary=` marker, so `authoring_reference()` did not describe `sources.csv` at all —
  and the guard that exists for exactly that
  (`test_every_enforced_vocabulary_field_declares_its_options`, which discovers enforcement by
  *behaviour* rather than from a list) never saw it, because it iterates `reference._ALL_MODELS` and
  `SourceRow` was not in it. The behaviour-discovering half was the good design and it was defeated by
  the one hand-kept thing left beside it. **When adding a model, add it to `_ALL_MODELS`**, and when
  reviewing a guard, ask what it enumerates before trusting what it proves. The cost was concrete:
  `sources.csv` is the **only fact sidecar a human writes** and the only table the compile licence gate
  reads, and an author reconstructing it from a filename has to guess that
  `share_alike`/`commercial_use`/`redistribution` are three orthogonal axes where `None` means unknown
  rather than false — not a guessable shape. The reporter got it right only by reading
  `SourceRow.model_fields`, i.e. reading our source to learn our schema.
- **`sources.csv` is draftable, and the exception is the rule's own point (S21, 0.5.4).**
  `draft.blank_template("sources.csv")` used to answer *"is not an authored table of this format"* — a
  false claim, made by the surface an author reaches for *instead of* reading the models. It is in
  `DRAFTABLE` now with `(source, layer)` as its natural key, borrowed from
  `licensing.merge_sources_csv` for the same reason `_CORE_DUPE_KEYS`' other entries are borrowed: a
  draft must not append a row the other writer would treat as already present, and one source
  legitimately appears at two layers. The other three fact sidecars stay out — they are produced by an
  enricher pass, so an author never starts one by hand.
- **Requiredness has THREE shapes, and the middle one is invisible to pydantic.** `is_required()` is
  false for `MeasureBinRow.measure_kind` and `unresolved` — they have defaults — but they are not
  `Optional`, and `load_csv_rows` turns an empty cell into `None` **and keeps the key**, so the model
  gets `None` instead of its default and fails on type. `blank_template` + `required_fields` therefore
  told an author to fill three columns and produced a file the compiler refused, naming a fourth.
  Use `draft.field_category` (`required` / `defaulted` / `optional`) and `draft.authoring_requirements`
  — which also reports `REQUIRED_ANY_OF`, the "rsid **or** chrom+start" rule that is a model validator
  and which no per-field flag can express.
- **A generated stub must be unable to compile — `vocab.TEMPLATE_PLACEHOLDER`, guarded before
  coercion.** The guard is `mode="before"` on purpose: an unreplaced stub in `start: int` then reads
  as "unreplaced template placeholder in column start", not "Input should be a valid integer". Do
  **not** reuse `MeasureBinRow.unresolved` for this — that sentinel means "no measurement at read
  time" and is designed to *compile*; two opposite lifecycles on one field is the overloaded-axis
  anti-pattern (P5).
- **Scaffolding refuses per FILE; drafting refuses per ROW — and the difference is derivable.** A
  file-level rule self-defuses for `draft` (you re-run it per gene), but you scaffold a module once,
  and a stub row has no natural key to merge on because its key columns *are* the placeholder.
  Refusal is per file, not per run, or a module could never gain a second table kind. Both use the
  same definition of absent — a zero-byte file counts as missing.
- **A hint may not fill a cell a Class-2 check cross-examines — `hints.REDUNDANCY_BEARING`.** Class 2
  works because two *independently-authored* things must agree. Fill `chrom`/`start` from Ensembl and
  `resolution._verify` compares Ensembl with Ensembl; worse, for an rsid-only row that check never
  runs at all, so the row moves from honestly unverified to apparently verified and the compile
  reports success. Same for `doi` vs `literature._doi_conflicts` and `ref` vs
  `verify_reference_alleles`. `literature` already argued this for one field (Crossref is asked about
  the **authored** DOI, since a derived one "exists by construction"). So a looked-up value comes back
  `applied=False` with a refusal; the only thing `hints` applies is a `normalized` rewrite the model
  already performs silently on load (`DiplotypeRow` swaps its haplotype pair). A `--apply` flag on a
  lookup would ship the parked enricher-co-authoring item without deciding to.
- **"It moves the digest" is NOT a reason to refuse a row move — that argument was checked and it
  failed.** Probed: a pure reorder moves `artifact.digest` but leaves `content_signature` untouched
  (order-independent by construction), the compile → reverse → compile fixed point still holds,
  duplicate keys are rejected so order can disambiguate nothing, and **nothing reads the append-only
  prefix property** (one test asserts it; no other code). The decisive point: an author reordering
  rows in their editor is already legal and already moves the digest, so forbidding the tool the same
  move proves too much. Mid-flight digest stability is worth ~nothing — the digest is consumed at
  exactly one moment, *publish*, and every authoring edit changes it anyway. What stays refused is an
  `at=N` index (it buys nothing an editor does not) and a `sort`/`canonicalize` command (every row
  moves, no local reason for any of them). What shipped is `append_rows(..., group_by=…)` /
  `place_rows`: **the tool picks where, the caller never supplies an index.** Shifted rows keep their
  cells byte-for-byte — `_render_existing` re-reads them as text — and `DraftReport.shifted` names them.
- **A partial row is validated by OMISSION, and matches on `match_on`, not the natural key.**
  `draft.PartialRow` exists because ClinVar publishes **alleles, not genotypes**, and
  `VariantRow.genotype` is required: zygosity is inheritance-mode interpretation the source does not
  state, so `clinvar_draft` writes what is published and leaves `genotype` as `TEMPLATE_PLACEHOLDER`.
  Two traps. (1) Validating the non-stubbed cells by substituting dummy values needs a per-column
  value oracle — a hand-kept list again; instead the row is built **without** the stubbed columns and
  errors located on them are discarded. (2) The natural key runs *through* the stub, so it cannot
  decide sameness; `match_on` (the identity columns) does, which is what makes a re-draft after the
  human fills the genotype report `already_present` instead of appending the stub a second time.
- **A placeholder protects a DECISION; where the contig leaves none, filling it is not pre-empting
  anything (S6, 0.5.2).** `draft_gene_panel` stubs `genotype` because zygosity follows from the
  inheritance mode and the source does not state it — true on a diploid contig, vacuous on MT (haploid)
  and chrY outside PAR1/PAR2 (hemizygous), where exactly one genotype is expressible.
  `sole_expressible_genotype` writes the ALT there and keeps the stub everywhere else; Y is decided
  **per locus** through three-valued `vrs.in_pseudoautosomal_region`, with `True` *and* `None` keeping
  the placeholder. Three points. **Row counts do not change** — the provider always wrote one row per
  record; the doubling a consumer saw was their own placeholder-expansion step, which now has nothing to
  expand. **The notice is aggregated and names the reading** (homoplasmic/hemizygous; a heteroplasmic
  level is `heteroplasmy.csv`), because at panel scale it is hundreds of loci and the *reading* is what
  the author must know. And **the chrY half of the report did not reproduce** — a real SRY row warns
  through the compiler exactly as MT does — so nothing in the ploidy check moved; check a claim about a
  guard before adjusting the guard.
- **A drafting provider fills identity WHOLE or not at all.** rsID, else the complete
  `chrom`/`start`/`ref`/`alts` — never a subset. A lone `alts` on a position-only row makes
  `derive_variant_key` mint a VRS `ga4gh:VA.…` id instead of `chrom:start:ref`, so a partial
  coordinate silently changes *which variant the row is*.
- **A generic rejection is a dead end where a specific one is a fix, and the reason lives beside the
  constant (0.5.4).** `extra="forbid"` refuses every unknown column identically, so three different
  mistakes read the same. There are now three guards layered on it, all the same shape — a
  `mode="before"` validator that raises a *diagnosis* and changes no verdict: `vocab.reject_reserved` (a
  name held against a future release), `normalize.reject_authority_keys` (`namespace`/`owner`/
  `canonical_id`, registry-stamped — the reasons had existed since 0.4.1 with `authoring_reference()` as
  their only reader), and `vocab.reject_misplaced` / `MISPLACED_COLUMN_REASONS` (`source`, which is real
  on the four **generated** tables and on `sources.csv`, and nowhere else). Four rules. **Diagnosing is
  not applying** — the inject-only rule bars the validator from *stripping* one consumer's convention, and
  a message strips nothing, so `strip_authority_keys` stays opt-in. **Key on the model's own fields**, so
  `FrequencyRow.source` cannot be broken by the message describing it. **A misplaced column is not a
  reserved one**: reserved is for names no model has, and conflating them would bar a real column.
  And **prose, not a cross-model registry** — `base` cannot import `spec`/`pgx` (the cycle the vocabulary
  markers avoid) and a hand-kept model list is the drift being unwound; a sentence about a stable table
  role does not rot the way a column list does.
- **A ragged CSV row misdiagnoses the column *after* the mistake, and both coordinates were wrong
  (S18, 0.5.4).** `hints.inspect_rows` padded a short row with `""` (indistinguishable from cells left
  empty) and, for a long one, shifted every column from the offender onward and dropped the overflow — so
  an unquoted comma in `conclusion` produced `Input should be a valid boolean` against `unresolved`, whose
  authored value was `false`. The field-count mismatch is reported **before** the type error it explains,
  error for a surplus (data is discarded, and `csv_out` carries the damage forward) and warning for a
  shortfall (padding is recoverable). Padding and truncating stay: a hint describes a broken file rather
  than refusing it. Separately, `Finding` now carries **`line`** — 1-based, header-inclusive, the
  coordinate `validate`/`compile` print — beside `row`, a 0-based data-row index; **added, never
  redefined**, because a consumer already compensating for the old meaning would then break silently. The
  compiler's own loader had the ragged case right all along (`more values than header columns`, with a
  line number), which is what made the hints surface the odd one out.
- **A rate limiter the injection API tells callers to share must be safe to share (S15, 0.5.4).**
  `PacingGate.wait()` read `last`, slept, then wrote it with no lock, so two threads could both find the
  interval elapsed, both skip the sleep, and turn a published 3/s budget into 6/s — a budget someone else
  enforces by blocking the operator's IP. What decides it is not thread-safety in the abstract but that
  `LookupClients`' own docstring tells callers to hold and reuse a client, so a server threading its
  blocking work arrives at a shared gate *by following our documentation*. The lock covers the
  **bookkeeping, not the sleep**: each caller reserves the next slot and waits for it alone, so N callers
  get N slots one interval apart and none blocks another. Holding a lock across the sleep would instead
  give "one in-flight request per service", which is a **concurrency limit, not a pace** — a different
  axis, and a semaphore's job (P5). Proven on a frozen clock: four threads at a barrier must come out
  spaced by the interval, and the old code yields gaps of `[6.0, 0.0, 0.0]`.
- **Existence is not identity — a lookup that answers "does this exist" must say *what* it found (S12,
  0.5.4).** PMIDs are densely allocated, so a recalled or invented 8-digit number is usually a real record
  for a different paper, and `pmid_exists=True` could never catch a fabricated citation; the surrounding
  docs treated existence as the guard, and a consumer's skill had to retract a rule its surface could not
  enforce. `CitationHint` carries `title`/`journal`/`year`/`first_author` from the same `esummary`
  response, via public `literature.bibliographic()` (two tiers read it — the RM41 lesson), with `None` for
  a field the record lacks and a `year` taken only from a leading four digits. No title column on
  `LiteratureRow`: that table records what was *checked*, not bibliography. Generalize it: when a check
  answers a yes/no about an identifier, ask whether "yes" could be true of the wrong thing.
- **A quote is an ATTESTATION, which is a sharper refusal than a spent comparison (S11, 0.5.4).**
  `provenance_quote`/`provenance_regex` were missing from `hints.REDUNDANCY_BEARING` although
  `literature._study_quote_found` compares both against the fulltext — exactly the drift that map's
  docstring predicts. Both are registered now, **plus** a fifth `REFUSAL_REASONS` member,
  `attestation_bearing` (`hints.ATTESTATION_BEARING`): filling `doi` from the registry that checks it makes
  a Class-2 comparison *vacuous*, while extracting a passage from a fulltext a tool just fetched states
  something **false**. The registration is additive, not instead — a provider consulting either map must
  reach a refusal. And the consequence, now in ENRICHER.md: once a machine has retrieved the text,
  `quotes_found` shows the quote **pairs with the PMID**, not that a human read the paper.
- **Unknown files in a spec directory are tolerated — and probing that contract found the case where
  tolerance is wrong (S16, 0.5.4).** A module may carry a README (every reference example does), curation
  notes, or a registry's `published.json` receipt, whose keys cannot go in `module_spec.yaml` because
  `extra="forbid"` rightly rejects them; none is read, hashed, or in `artifact.files`, so none can move
  `artifact.digest` (pinned by a digest comparison, not asserted). The exception is a **mistyped table
  name**: `varaints.csv` silently is not a table, so every row in it is dropped from a green compile.
  `_check_misspelled_tables` warns on an unknown `.csv` within one small edit of a known name, deriving
  the name set from the table registries. Keyed on **near miss** rather than "any unknown csv" on purpose
  — warning about every unrecognised file would undo the tolerance it sits beside.
- **A warning's TEXT became an API, because the manifest carries prose and no field (RM44).**
  `compile_module` copies its warnings into `manifest.compilation.warnings` → `manifest.json`, and a
  catalog reindexing from a published manifest has nothing else: `fully_resolved` is `all()` over
  `variants.csv`, so it is **vacuously `true`** for a table-only module and the documented trust rule
  (`resolution_mode == "strict" or fully_resolved`) grants a badge to a module that annotates nothing.
  A consumer shipped that, then repaired it by substring-matching `"have no chrom+start"`.
  `compiler.UNJOINABLE_PHRASE` names the fragment and a test pins it in **both** places it must hold —
  emitted verbatim, and present in `manifest.compilation.warnings` — so a reword breaks our build
  instead of their catalog. Two durable points: **anything a consumer can only learn from a warning
  string is an unversioned interface**, so give it a structured field rather than asking everyone
  downstream to parse; and when a flag quantifies over a subset, **publish the denominator** —
  `vrs_alleles`/`vrs_alleles_identified` already argue exactly this one line above it in the same
  model, and nobody applied it to the flag.
  **`resolution_subjects` shipped in 0.6.0** — one additive integer, counted *after* the rsID expansion
  because that is the list the flag iterates, so the safe trust rule is
  `resolution_subjects > 0 and (resolution_mode == "strict" or fully_resolved)`. Three things it did
  **not** do, all deliberate: `fully_resolved` stays `bool` (consumers branch on it, so a `None` is a
  breaking read for all of them), `UNJOINABLE_PHRASE` and its test **stay** (the *unjoinable-row* count
  is a different question, still prose-only until RM43), and there is no second counter (RM45 settled
  three things into three homes). And one thing the item missed, worth generalizing: **the number was
  already available as `Stats.weights_rows`** — equal on every reference example, because the
  materializer emits one weights row per in-scope variant row. Publishing it beside the flag is still
  right (that equality is a property of the transform, not a contract, and `Stats` is documented as
  *display* facets), but **before adding a computed field, check whether another block already carries
  the number, and if it does, say in the code why the new home is the right one.**
- **Resolution reaches the SNP core ONLY, and the naive repair breaks P7 (RM43, surfaced in 0.5.3).**
  `_build_table` is `model_dump()` → parquet, so a `pharm_variants.csv`/`haplotypes.csv`/
  `heteroplasmy.csv` row keeps the coordinates its author typed — none, for an rsid-authored module —
  and the table joins to no VCF. Before proposing "just join `resolution.csv` on `variant_key`":
  **materializing the coordinate moves `content_signature`, not only `artifact.digest`**, because
  `reverse_module` rebuilds the CSV from the parquet and a filled cell returns as *authored*. That is
  what `VariantRow.authored_ident` exists to prevent and no 0.4-family model has one, so the
  prerequisite is a new stamped column per positional table — **0.6 work since the 2026-08-11 charter
  amendment, not 1.0**; what is major-only is the *filling*, if it ever re-emits as authored. Three
  related traps:
  `PharmVariantRow` has **no `alts`**; `variant_key` is a **property** on these models so it is in no
  parquet (a consumer cannot even join them to `weights.parquet` on it); and `fully_resolved` is
  `all(...)` over `VariantRow`, hence **vacuously `True`** for a table-only module — the manifest's own
  trust rule (`resolution_mode == "strict" or fully_resolved`) is unsafe there. What 0.5.3 shipped is
  legibility: `_check_positional_joinability` reports, per table, how many rows cannot be joined and
  how many of those `resolution.csv` **could** place — the second count is what separates "never
  enriched" from "the answer exists and this tier does not apply it". Warning in both modes, because
  rsid-only identity is legal by the models' own rule and the remedy is a compiler change.
- **A batch lookup must HASH its probe, and the cost is in the BINDING, not the join (0.5.2).** DuckDB
  cannot fold a disjunction of equality *conjunctions* into a hash probe, so
  `WHERE (chrom=? AND start=? AND ref=? AND alt=?) OR …` is evaluated against every row: cost grows
  with `alleles × rows` and a 297-gene panel ran two hours at 12% CPU looking like a deadlock. Fixed by
  `resolver.probe_table` (temp table + join) — 88 s → 0.21 s on 5,000 alleles against the real 4.4M-row
  snapshot. Four things not to redo. **A single-column list is already fine as `IN (…)`** (it is pushed
  into the parquet reader; `x = ? OR x = ? OR …` is not, so `select_by_gene` was 20.9 s → 6.6 s) —
  `_lookup_positions_by_rsid` and `citations_for` were always correct and must be left alone. **The
  probe rows are rendered as escaped SQL literals on purpose**: measured, same query and data, literals
  0.21 s / composite-key `IN (?, …)` 1.04 s / parameterized `UNNEST(?::VARCHAR[])` 3.51 s /
  `executemany` 8.6 s, so parameterizing it back gives up most of the win. **Benchmark on a spread
  sample** — a `LIMIT 5000` sample is clustered on one contig where row-group statistics prune the
  OR-chain, and the first measurement therefore read ~1×. **Guard the plan, not the clock**:
  `test_query_shapes.py` asserts `EXPLAIN` contains a hash join, and separately times both shapes in
  one process so a slow runner moves both numbers together.
- **A check that cannot fail must not report a zero — `clinical.tautology_reason` (0.5.2).** A panel
  drafted by `draft_gene_panel` copied its `clin_sig` out of the snapshot the cross-check reads, so the
  comparison is a value against itself: 0 conflicts, necessarily, at 90% of the resolve time. The zero
  is the defect, not the cost — it looks like evidence. The skip keys on an **established** match
  between the module's `panel:` pin and the snapshot's `release.json`, and every unknown (no `panel:`,
  another source, an unstated pin, an unreadable release) leaves the check running. The reason lands on
  `EnrichmentResult.clin_sig_not_checked` because an empty conflict list otherwise means both "compared
  everything" and "never compared". Generalize it: **when a check's inputs can share a source, ask
  whether a pass is structurally guaranteed before reporting one.**
- **`_cache_dir` loads the `.env` itself, and that one ordering fixed three reports (0.5.2).**
  `_resolve_parquet_cache` calls `load_env()` inside itself, but each `resolve_*_reference` passed
  `default_*_cache_dir()` as an *argument* — evaluated first — so with the base set only in `.env` the
  **first** resolve in a process returned `None` and every later one was correct. That asymmetry is the
  whole explanation for `cache pull` writing where `cache status` does not look, `draft-panel --offline`
  refusing a present snapshot, and a test module whose first skip-guard silently skipped. The durable
  rule: **a default computed as an argument is computed before the callee's setup runs** — if the callee
  loads configuration, the default belongs inside it.
- **The 0.3 axes are a materialized PASSTHROUGH; the derivation is read-time and Python-only.** The
  compiler copies `direction`/`stat_significance`/`clin_sig` into `weights.parquet` verbatim and never
  fills a blank from `state` — `derive.direction_from_state` invents a direction from the weight sign
  for `state='significant'`, which is sound as a consumer's fallback and a fabricated fact in a
  published table. So every `state`-only module (all four curated Generation-I ports) ships an empty
  `direction`, correctly. **Do not "finish" it at compile**: it asserts what no curator wrote — that is
  the whole objection, and it does not depend on the digest (filling *values* into an existing column is
  not the additive case the charter permits). The live gap is that a
  parquet-side consumer cannot reach `effective_direction`/`upgraded()` at all, and COMPILER.md's
  coverage row ticks both tiers and reads *complete*; filed for 0.5.2 as docs (ROADMAP 0.6 idea-book,
  CONSUMER_SUGGESTIONS S5).
- **Derived-not-stored is the house pattern for a convenience number**: store the exact parts in the
  CSV, materialize the derived value into parquet as a `@property`, and let it fall away on reverse
  because it is not a model field. `FrequencyRow.allele_frequency` (AC/AN) and
  `StudyRow.neg_log10_p` (mantissa/exponent) both do this. For p-values it is load-bearing rather than
  cosmetic: float64 goes subnormal below ~1e-308 and is flatly `0.0` below ~5e-324, so a single float
  column would render a panel's strongest association as its weakest.
- **Store a source's value verbatim — EXCEPT when the encoding lies about its own order.** ClinGen's
  dosage codes are `{0,1,2,3,30,40}` where `30` = "autosomal recessive" and `40` = "dosage sensitivity
  unlikely", so sorting the raw numbers ranks `40` above `3` (sufficient evidence). They are decoded to
  `VALID_DOSAGE_SENSITIVITY` terms at the enricher boundary (`vocab.DOSAGE_SENSITIVITY_BY_CODE` holds
  the total mapping). Verbatim is right for an *identity* (a star allele, an accession); it is wrong
  for a code a consumer will sort. Also: that file writes `"Not yet evaluated"` in the
  triplosensitivity column for 210 of 1,520 genes — an absence, and what makes `int(cell)` crash.
- **`redistribution` is a third licensing axis, recorded but NOT gated.** CC BY-NC forbids sale and
  allows sharing; academic-use-only (OMIM, dbNSFP) forbids both. The compile gate deliberately keys
  only on `commercial_use` — a distribution right is not a *use*, so `declared_use` is the wrong axis
  to resolve it against (RM27). Don't "finish" the gate without doing that design.
- **Drafting appends, it never mutates — that word is the whole line.** `just_dna_compiler.draft`
  appends rows into an authored CSV at **row** granularity (a file-level "refuse if it exists" rule
  self-defuses after the first gene and makes a multi-gene module unbuildable). A row whose key exists
  is reported (`already_present` / `differs`), never rewritten; drift on existing rows is
  `pgx.enrich_pgx`'s job. Dedup keys on the compiler's own `_TABLE_DUPE_KEYS` so an append cannot
  create a row the compiler then rejects, and rows go **at the end** because authored row order is
  load-bearing for the digest. This is *not* the parked enricher-co-authoring item: appending leaves
  `content_signature` a function of the authored bytes; editing a cell a human wrote would not.
- **Probe a source's real file before modelling it; the docs lie by omission.** Every non-obvious
  decision in this round came from a probe, not from a spec: CPIC's recommendation classifications
  (five values, `n/a` among them), ClinGen's non-ordinal codes, the ACMG SF list existing only as an
  HTML table (so the check was deferred rather than built on a scrape), and Orphanet's IRI — `ORPHA:558`
  is a term at `…/ORDO/Orphanet_558`, so composing `stem + PREFIX + "_" + local` queries `ORPHA_558`
  and gets **HTTP 200 with zero terms**, which is indistinguishable from "this id does not exist". That
  last one is the shape to watch for: a lookup bug that surfaces as a false finding about the module.
- **Dogfood data is git-ignored** (`/data/` now in `.gitignore`): local ClinVar VCF at
  `/data/just-dna-cache/clinvar/clinvar_GRCh38.vcf.gz` (2026-06-27); the built snapshot the example used
  is `data/interim/clinvar`. (`resolution.csv` was provisional while 0.5 was unpublished, which is what
  made `artifact.digest` changes for alt-bearing coordinate modules acceptable. **0.5.0 shipped on
  2026-08-07 and it is frozen now** — see the digest-asymmetry bullet above.)
- **A PUBLISHED snapshot accumulates — provisioning must fetch only its own files.** The publisher adds
  and never deletes, so `just-dna-seq/clinvar/data` still carries a 159 MB `clinvar.parquet` from the
  single-file era beside the 25 `clinvar-chr*.parquet`; its columns are the raw VCF INFO fields
  (`clnsig`, `clnrevstat`), the readers glob `data/*.parquet`, and one foreign file therefore puts two
  schemas under one DuckDB relation and kills every query with `Referenced column "clin_sig" not found`.
  `download._{ENSEMBL,CLINVAR,CONSTRAINT}_FILES` is the glob each `ensure_*` filters on; don't widen one
  to `*.parquet`. The same failure arrives locally from an **old builder** — if a cache errors with
  "present but not queryable", check `data/` for a file the current builder would not write, and rebuild.
- **The snapshot layout lives in `locations`, because FOUR parties must agree on it.** Builder writes,
  publisher uploads, provisioner fetches, reader queries — `SNAPSHOT_DATA_DIRNAME`,
  `SNAPSHOT_SIDECAR_DIRNAMES`, `CITATIONS_DIRNAME`, `RELEASE_FILENAME`. Every disagreement so far was
  silent: `release.json` was uploaded and never fetched, `citations/` was built and never published (so a
  *downloaded* snapshot had no PMIDs and `draft-panel` could not produce a compilable module for its
  users), and `CITATIONS_DIRNAME` was declared twice. A sidecar is a **sibling** of `data/`, never inside
  it — the readers glob `data/*.parquet`. Absence is normal at both ends: only ClinVar has a sidecar, and
  only after `clinvar citations`.
- **Publishing a second artifact makes provenance a question — answer it in `release.json`.** ClinVar
  publishes `var_citations.txt` on its own cadence, so a snapshot can carry records and citations from
  different releases; `build_citations` merges its own block (read-modify-write, so the VCF's keys
  survive) and hashes the input when no caller supplied a digest. Recording `null` with the bytes on disk
  is an unknown you chose not to establish, and `source_sha256` is what RM4's `reference_sha256` pins
  against. An unreadable `release.json` is reported and left alone — a provenance failure is not a data
  failure, so the table is still written.
- **A snapshot's `ensure_*` must actually be CALLED — check the pass, not just the function.** Three
  instances so far, all the same shape. `ensure_constraint_snapshot` shipped with the ClinVar
  generalization and had no caller for a whole release, so `gene-metrics` on a plain install skipped the
  v4.1 snapshot entirely and recorded the live API's **v2.1.1** numbers while warning about the
  difference. `draft_gene_panel` *required* `snapshot=`, so the published ClinVar snapshot could not reach
  an author at all — they had to build 4.4M records from a 200 MB VCF first, which is why the published
  citations were useless to anyone who had not. And `citations/` itself was built, never published. When
  a resource becomes fetchable, grep for who asks. The shape to copy is `enrich()`'s: provision when the
  local resolve returns `None` and the run is not `offline`, degrade to the next link on failure (or raise
  where there is no next link — an empty draft reads as "the source has nothing for this gene"), and add
  no second CLI flag — `--offline` is the switch. An explicit path stays the inject-only escape hatch and
  is never second-guessed. And `release.json` travels with the parquet
  (`locations.RELEASE_FILENAME`, shared by `upload` and `download`) because `source_sha256` is what RM4's
  `reference_sha256` pins against; a cache that cannot state its release is not a pinnable reference.
- **A row is stamped before the module is known — so anything build-dependent must be re-derived by
  the compiler.** `VariantRow._freeze_identity` runs at construction, where `module_spec.yaml` is not
  in scope, so it always took `derive_variant_key`'s GRCh38 default. A `genome_build: GRCh37` module
  therefore minted GRCh38 VRS ids, silently, for years of the design — the `build` parameter and its
  fall-through-rather-than-lie guard both existed and were simply never reached.
  `compiler._restamp_for_build` fixes it after load, at **both** load sites (`validate_spec` and
  `compile_module` each read their own copy; fixing one leaves the artifact wrong). When adding
  anything else that depends on the spec, check whether the model can possibly know it.
- **`genome_build` is in `manifest.json` and NO parquet column — so anything rebuilding a spec must
  read it, and three things didn't.** The bug above was fixed on the forward path and then re-entered
  twice more, because a corpus where **every** reference example is GRCh38 cannot tell "reads the
  module's build" from "writes `GRCh38`". `reverse_module` hardcoded the constant into both the rebuilt
  `module_spec.yaml` and `resolution.csv`'s own column, so `compile → reverse → compile` on a GRCh37
  module minted `ga4gh:VA.…` ids for GRCh37 coordinates — P7 broken *and* a false content-addressed
  claim, since a VA names a base on a sequence the module never referenced. (`resolve_from_table`
  **filters** on that column too, so the mislabelled table was also unjoinable.) And `enrich()` took
  `genome_build="GRCh38"` that **no caller ever passed**, making every `== "GRCh38"` gate inside it
  dead code: a GRCh37 module was resolved against GRCh38 and the answer written under its own build.
  The **frequency pass** was the fourth site: it fed every resolved row to gnomAD regardless of build and
  re-keyed it with `derive_variant_key` *without* passing one. gnomAD's id is `chrom-pos-ref-alt` and
  carries no assembly, so a GRCh37 coordinate is a well-formed request returning **a different variant's**
  counts, written under this module's key — with a GRCh38 VA minted on the way. Fixes:
  `compiler._genome_build_from_artifact` (manifest → explicit arg → default), `enrich.spec_genome_build`,
  and `gnomad.FREQUENCY_GENOME_BUILD` (a named constant precisely because it was the third
  build-confusion in one round). Three rules from it: **a parameter nothing passes is not a guard, so
  grep for the caller**; **any code calling `derive_variant_key`/`derive_vrs_allele_id` on a row must
  pass that row's `build`**, since the default silently mints GRCh38; and **`reference_examples/grch37_build/`
  must stay** or the corpus goes uniform again — `test_reference_examples_roundtrip.py` asserts more than
  one build is represented for exactly that reason. `test_build_call_sites.py` walks the AST and fails on
  a call that hands over an allele without a build, so a *sixth* site cannot arrive silently.
- **The build is INJECTED into a row, never authored on one — `AuthoredModel._genome_build` (RM36).** A
  model built from a CSV dict has no `module_spec.yaml` in scope, and a *property* (unlike
  `VariantRow.variant_key`) has no stored field for `_restamp_for_build` to correct afterwards — which is
  why `HeteroplasmyRow.variant_key` minted a GRCh38 VA on a GRCh37 module. `load_csv_rows` tells every
  row it builds; the attribute is **private**, so it is not a column, reaches no CSV or parquet, moves no
  digest, and `extra="forbid"` still rejects an author who writes one. Two shapes that were **rejected**,
  so don't re-propose them: per-row declaration (overkill — the build is module-wide) and **per-CSV, as a
  "service row"** — two files could disagree about one fact, a data table would carry a non-data row (P5),
  a copied row would drop it, and it would still not reach the model, since a loader parsing it already
  knows the build from the yaml. The rule generalizes: **anything module-wide that a row needs is told to
  the row at load, not stated on the row.**
- **`content_signature` is reference-independent, NOT build-independent — the docstring said the wrong
  one.** True of the reference used to *resolve*; false of the *declared assembly*, which for a
  coordinate-authored module is the frame the numbers are in. Two modules with byte-identical CSVs and
  different builds describe loci 228 bp apart, and the content-dedup key hashed them equal — reachable by
  "lifting over" a panel through the yaml alone. `genome_build` now feeds the hash **only when
  non-default**, which is the existing omit-the-default normalization, not an exception: every GRCh38
  module keeps its signature byte for byte, so a 0.4 module still links to its own 0.5 recompile.
- **`validate` must refuse everything `compile` refuses — it exempted four of the twelve tables.** Both
  loops in `validate_spec` iterate `_TABLE_KINDS`; `resolution.csv` and the four fact sidecars are
  `_FACT_TABLES`, which it never read, though `compile_module` refuses on a bad row in any of them.
  The authoring skill's step 6 puts `validate` immediately before `compile`, making it the author's
  pre-flight, so a green pre-flight then a refusal sends an author hunting a change they did not make — and the worst case shipped: the **licence gate** reads
  `sources.csv` alone, so a module drafted entirely from a no-sale source with no `declared_use`
  validated clean and refused to compile. Rule for a new compile-side check: if it is pure computation
  over injected bytes and needs no `output_dir`, it belongs in `validate_spec` too. What stays
  compile-only is anything reading *resolved* rows.
- **A warning computed post-resolution is discarded — the second `_cross_validate_variants` call takes
  errors only.** That is right for a warning about authored cells and wrong for any whose input
  resolution fills. It made the non-diploid guardrail invisible to every rsID-authored row, i.e. to
  everything a drafting provider emits. `_check_contig_ploidy` now runs where `chrom` is final and
  keeps a pass inside `validate_spec` (which has no resolution step), de-duplicated on the message.
- **`chrom=Y` is NOT "never diploid" — PAR1 and PAR2 are diploid in every karyotype.**
  `vrs.in_pseudoautosomal_region` is three-valued and `vrs.PAR_GRCh38` holds the intervals; they are
  assembly constants of the same class as `REFGET_GRCh38`, not an un-injected reference.
- **A PAR locus is ONE place on two contigs, and the enricher records the X spelling (RM32, shipped).**
  `vrs.par_partner` maps a PAR locus to its twin by **index-matched offset** — PAR1 at 0, PAR2 at
  98,813,480 — so never compare "the same base on X and Y": that passes PAR1 and silently fails PAR2,
  where `rs184115031` is X:155773979 **and** Y:56960499. `enrich.select_par_representative` keeps X and
  reports the twin; `--keep-par-twin` keeps both. Five things not to redo:
  - **The place-identity direction is closed by probe, not by opinion.** ClinGen's Allele Registry mints
    **two** CA ids per PAR base (`CA254919`/`CA254920` for `rs137852556`), so `ResolutionRow.caid`
    cannot carry a place and no upstream mints one. A `place_key` column was rejected too — the relation
    is derivable, so a column would restate what the data determines (the `requires_phase` argument).
  - **Selecting X follows the SOURCES, which is why it is legal** (P2). ClinVar has 0 PAR records on Y
    (of 677 Y records), gnomAD v4 excludes the Y PAR (X PAR1 640000-641500 → 880 variants, Y → 0), and
    the Registry's Y record is a bare dbSNP xref. Only Ensembl/dbSNP reports both. The old objection
    ("it encodes the consumer's analysis set") was checked against data and failed.
  - **The verdict is PER LOCUS — `XG` and `SPRY3` straddle a boundary** (XG out of PAR1 at 2,781,479,
    SPRY3 into PAR2 at 155,701,383), so anything gene- or module-scoped is wrong for half of either.
    `reference_examples/par_boundary/` is that case, and its round trip is a fixed point on all three
    signatures — which is why an enricher flag is legal where a `--par` compiler flag is P7-illegal.
  - **Position agreement is necessary, never sufficient.** A twin is dropped only when the partner
    position carries the same `ref`/`alts`; partner coordinates say "same place", not "same variant".
  - **Two non-problems, checked:** `studies.csv` is rsID-keyed so both rows always inherited the
    citation, and `_check_contig_ploidy` only branches on `{MT, Y}` so selecting X makes it quiet rather
    than wrong. It stays, for hand-authored and `--keep-par-twin` modules.
- **gnomAD does not cover the Y PAR, and an absence there is not a fact.** `frequencies.csv` wrote
  `status="not_found"` for it — an absence nobody established. `gnomad.covers_locus` (the source
  convention, so enricher-only; the PAR *geometry* stays in `vrs`) gates it, such a locus is not queried
  at all, and the outcome is **`not_covered`** — a third `VALID_FREQUENCY_STATUS` member, distinct from
  `unchecked` (this codebase's word for a question never *put*). It is deliberately outside the `strict`
  gate: a locus the source cannot cover is perfectly reproducible, and refusing would make a PAR module
  uncompilable for a reason no authored edit could fix.
- **Hosting is a THREE-valued question — `hosting_verdict`, not `genotype_fits` (RM31, shipped).** One
  indel has several valid spellings: ClinVar's `X:634689 CAG>C` and Ensembl's `X:634690 AGAG>AG` are the
  same 2 bp deletion, and comparing allele *strings* resolved it to `not_found` while asserting a dbSNP
  merge that does not exist. `alleles.parsimony_reduce` (format tier, stdlib) strips the flank a
  *collection* shares, so both reduce to `{'', 'AG'}`. Four things about it that must not be "simplified":
  - **No position is passed in, and none can be.** The row records *no coordinate* — `clinvar_draft`
    prefers the rsID and the model forbids `ref`/`alts` without a coordinate — so the authored genotype is
    spelled in a frame the row never states. A genotype naming *two* alleles carries the frame instead.
  - **The raw comparison runs FIRST.** Normalization may only ever *add* acceptances, which is what keeps
    every compiled digest and expansion stable; a property test over the reference examples pins it.
  - **The confident negative is about event SIZE.** Re-anchoring moves an indel, it never changes how many
    bases it adds or removes, so differing sizes prove different variants (`rs281864532`: 1 bp insertion
    *and* 2 bp deletion under one rsID). Same size, different content → `None`, and the locus is **kept**
    with a message saying nothing was decided. A substitution/MNV locus has no flank, so a mismatch there
    is `False`, not `None` — that is what keeps the strand-flip check sharp.
  - **`_check_allele_membership` must ask the same predicate.** It did its own exact set difference, so
    once resolution reconciled a spelling and expanded onto the locus, membership refused the same module
    under `strict` — the compiler contradicting itself. Kleene-OR over the loci, matching the union reading.
  Residual: the authored `genotype` keeps its source's frame, so a row can carry `genotype=C/CAG` beside
  `ref=AGAG`. A consumer applies the same reduction (`just_dna_format.alleles` is public for that);
  rewriting the authored cell is the parked co-authoring item.
- **Before adding a table-level check, ask whether its rules are jointly satisfiable.** Inclusive
  bounds + overlap-is-an-error + any-hole-is-a-warning cannot all hold on a continuous measure, so
  every `allele_fraction` table warned forever (RM35, now fixed). Integer kinds tile cleanly, which is
  why nobody noticed.
- **A bin boundary is the most interpretive claim the format carries and it has nowhere to cite —
  a SCHEMA limit, not a tier limit (S19/RM47, 0.5.4).** `studies.csv` names a variant (`rsid`, or
  `chrom`+`start`) and a `repeat_alleles.csv` row is keyed `(gene, repeat_unit)`, so nothing can point at
  it: `reference_examples/htt_repeat_expansion` compiles green under `--strict` asserting where
  Huntington disease becomes fully penetrant — 26/27, 35/36, 39/40 — with no citation anywhere, and its
  README said *"a module making a novel claim should carry its evidence"*, advice the schema gave the
  author no way to take. Probing narrowed it in **both** directions and both corrections matter:
  `heteroplasmy.csv` is *not* affected (its optional `rsid`/`chrom`/`start` columns, 0.5.1, give a row
  an identity a study row names exactly — `reference_examples/mt_heteroplasmy` does it), and
  `studies.csv` is **not rejected** in a variants-free module (it loads, validates and materializes
  `studies.parquet`), so a binning or PGx module can cite its literature today; the row simply grounds
  the *module* rather than the bound. What ships is `_check_binning_grounding`: warns in **both** modes
  when a binning table states thresholds and the module records no study rows, message split on whether
  the rows *could* be pointed at — derived from the model (`variant_key is None`), never from the table
  name. One comment was load-bearing and false — `validate_spec`'s exemption was justified as "the 0.4
  tables carry their own evidence (e.g. `evidence_level`)", true of two of the nine kinds; the real
  reason is that for a gene-keyed table the requirement would be **unsatisfiable** rather than merely
  unmet. Closing it is **RM47** (0.6), a design round: every candidate repair costs either a duplicated
  column set (`pmid` on `MeasureBinRow` drags `studies.csv`'s provenance columns along) or a duplicated
  key (`bin_evidence.csv` joins on floats that orphan silently when a bound is re-authored). Don't
  file it again, and keep the HTT thresholds uncited — the example exists to show the gap.
- **A shared bin endpoint is a BOUNDARY on a dense measure, and the higher bin owns it** — the lookup
  rule is *the row with the greatest `measure_min ≤ x`* (`binning._DENSE_KINDS`: `allele_fraction`,
  `prs_percentile`). So the overlap test is `lo < prev_hi` there and stays `lo <= prev_hi` on
  `repeat_count`/`copy_number`, where two integer bins sharing an endpoint really do both claim it.
  `measure_max` is inclusive on **every** kind: half-open for continuous kinds only was the other
  candidate and lost on authorship, which is the charter's gate — it makes one column's meaning depend
  on `measure_kind` (P5), the number in the cell is then not in the bin, and a closed top bin can no
  longer reach a bounded domain's top value (AF `1.0` is homoplasmy, and real). Both spellings produce
  identical authored bytes in the interior and need the same predicate. Also: two bins sharing a
  **lower** bound refuse on any kind — the tie-break has nothing to order — which is reachable only as
  a sharp `[0.1, 0.1]` beside a range starting there.

## The design cycle (the order of things)

Feature ideas move through **one loop**; the docs are its stages, and a design task should walk them
in order rather than jumping to code:

1. **Feedback** — a consumer's field report → [docs/CONSUMER_SUGGESTIONS.md](docs/CONSUMER_SUGGESTIONS.md)
   (the live one, `S1`…`Sn`), [docs/CONSUMER_ROUND2_AND_0_5.md](docs/CONSUMER_ROUND2_AND_0_5.md).
   **The round-1 thread `docs/CONSUMER_FIELD_NOTES.md` was removed on 2026-08-12** — a second inbox with
   its own reply idiom that the ledger could not read, which is how two accepted doc deliverables (now
   S27/S28) sat undelivered across three releases while the live file said nothing was owed. Its two live
   asks were refiled with their prose verbatim; recover the thread from git history (`53f9260`) for the
   wording. Do not start a third feedback file: an inbox the ledger cannot see is a backlog nobody sees.
   **Every `Sn` gets a `**Status —**` reply written back into the document, and the runbook for that is
   [docs/CONSUMER_TRIAGE_LOOP.md](docs/CONSUMER_TRIAGE_LOOP.md)** — read it before answering one. It
   holds the four routes (fix / non-issue / doc fix / surface-only), the rule that **legality sizes the
   release while severity only orders the queue**, and the ledger (`.claude/triage-state.sh`) that says
   which items are unanswered. `.claude/watch-suggestions.sh` under `Monitor` is what notices a consumer
   has written; if a notification says a section settled, that doc is the brief.
   **CONSUMER_SUGGESTIONS.md is the OPEN inbox only** — an answered item moves to
   [docs/CONSUMER_SUGGESTIONS_HISTORY.md](docs/CONSUMER_SUGGESTIONS_HISTORY.md) (byte-for-byte, plus a row
   in that file's index), the same split as ROADMAP/ROADMAP_HISTORY. So an empty live file means nothing
   is owed, and **"no reply in the live file" never means "no work was done"**: S1 and S2 had both
   shipped — one of them with a code comment naming the item — and were still sitting there unanswered.
   Establish what shipped before designing anything.
2. **Usage → blockers → solvability** — run each use case against the current bricks: *enabled*,
   *consumer-side* (the format owns nothing), or a *gap* closable additively? →
   [docs/USE_CASES.md](docs/USE_CASES.md)  ← **start a design task here**
3. **Means → draft schema → decision** — the proposed shape + charter check + open questions →
   [docs/PROPOSAL_0_5.md](docs/PROPOSAL_0_5.md) (0.5 design threads),
   [docs/PROPOSAL_0_4_1.md](docs/PROPOSAL_0_4_1.md) (the 0.4.1 patch). *(0.4's proposal shipped and
   was retired — its decisions live in [docs/CHANGELOG.md](docs/CHANGELOG.md).)*
4. **Conclusion — how to author it now, with these bricks** → [docs/REFERENCE_EXAMPLES.md](docs/REFERENCE_EXAMPLES.md)
5. **Terminal** — either **shipped** (schema + compiler; recorded in COMPILER.md coverage) **or**
   **deferred** (a recognised gap parked as an `RMn` roadmap item in ROADMAP.md).

`USE_CASES.md` and `REFERENCE_EXAMPLES.md` are the **same use cases at two points in the loop** —
questions (what blocks?) vs answers (author it like this). A blocker is never a dead end: it is
dissolved (was consumer-side), closed additively, or explicitly parked. See *The feedback → schema
cycle* in `USE_CASES.md`.

## Coding standards

- **Dependency tiers are sacred** (CONSTITUTION Goal 2 + the 0.5 amendment): never add a heavy dep to
  `just-dna-format` (pydantic + cryptography only); `just-dna-compiler` is pure-Python since 0.5
  (polars/pyyaml/typer — **duckdb-free**). Network **and HuggingFace** live **only** in
  `just-dna-enricher`. Never pull Dagster / LLM SDKs into any tier.
- **No network in format/compiler; inject-only** (Principle 2): they never download — the compiler
  consumes an injected `resolution.csv` (or, deprecated until 1.0, an injected reference) and skips
  with a warning when nothing is injected. Fetching is `just-dna-enricher`'s job.
- **Data-agnostic — a north star, not a totality claim.** A module and its compiled artifact are
  pure *annotation*: lookup tables and bounded rules mapping a quantity/genotype to a phenotype. They
  carry **no sample data, no genotype under test, no measured value** — the measurement is supplied by
  the consumer at query time (the format supplies the table; the consumer supplies the call). *But*
  the pydantic schemas are a **generalization over a practical subset** of real data items — concrete
  loci, callers, and realistic value ranges — i.e. an implicit data model with an untracked empirical
  footprint, not an all-encompassing universal one. Be explicit that a shape generalizes known cases
  rather than pretending it covers everything: when a real data item doesn't fit, that is a schema gap
  to widen *additively*, not a consumer error. (This is why `copy_number`-as-a-measured-value was
  wrong — the module never holds the measurement — yet the *range* shapes are still only as general as
  the cases they were generalized from.)
- **Human-authorable ⇔ machine-precise — a gate on every schema change.** The authored DSL
  (`module_spec.yaml` + CSVs) is a *duality*: it must be **both** a legible, human-authorable artifact
  **and** a formally algorithmizable, machine-precise one. The compiled parquet is already the
  pure-machine form — **if we only wanted machine precision we would ship parquet-only.** The DSL
  exists for the human. So gate any schema change on: **"will this burden the rare human author?"**
  Modules must never read like enterprise-DB internals — alien, sprawling, machine-code-like. Corollary
  — **one CSV = one concern; compose from optional table kinds**: the SNP core (`variants.csv` +
  `studies.csv`) stays minimal; a module includes only the table kinds it uses; a PGx / PharmGKB / PRS
  module adds its own focused table (`diplotypes.csv`, `pharm_variants.csv`, `pgs.csv`) rather than an
  empty `variants.csv` or a foreign domain's columns on every row. When human-legibility and
  machine-precision tension, the parquet absorbs the precision; the DSL keeps the human shape.
- Type hints mandatory; **pathlib** for paths; **absolute imports only**; **no inline imports** (a
  guarded module-level `try/except ImportError` for optional deps is the only exception).
- **Avoid nested try/except** — it is a nightmare to read and debug, and usually just swallows the
  real error. Use it only where an error is an unavoidable, handled part of the use case (that guarded
  optional-dep import is that case).
- **Polars in the compiler**: prefer lazyframes (`scan_parquet`) and streaming (`sink_parquet`), and
  pre-filter before joining so you never materialize more than needed. (The format tier stays
  polars-free — Goal 2.)
- **Typer for every CLI**; the root package's `[project.scripts]` owns the user-facing command. If a
  `uv run <cmd>` wrapper goes stale after a dependency upgrade, bump this package's version and
  re-run `uv sync` — never rename the command to dodge a stale wrapper.
- **Standard-library `logging`** for diagnostics — never `print`.
- **Heed terminal warnings, deprecations especially** — they are the signal that an API moved since
  training. Read and fix them; don't paper over them.
- **No placeholder paths or fabricated example values** in code (`/my/custom/path/`, dummy digests, …).
- **Refactor internals aggressively** — don't keep dead code or an old API around for nostalgia. The
  one exception is the wire/artifact **contract**: it obeys additive-within-a-major (Principles 3/8),
  never "no legacy support." Internals are free; the schema and `manifest.json` shape are not.
- **Versions read from `pyproject.toml`** (via `module.version`); never hardcode a version string in
  `__init__.py`.
- **Avoid `__all__` / pure re-export `__init__.py`s** — they obscure where a symbol actually lives.
- Pydantic 2 for all data models. Constrained vocabularies are `frozenset[str]` + a validator, never
  `Enum`/`Literal` (Principle 6).
- **Authored row models inherit `AuthoredModel`** (`just_dna_format.base`), never `BaseModel` directly.
  It carries the reserved-namespace guard (`extra="forbid"` + the `reject_reserved` before-validator)
  and the shared field validators (`rsid`/`trait_efo_id`/`direction`/`clin_sig`/`stat_significance`/
  `evidence_level`/finite-`effect_size`). Don't re-declare `model_config` or re-copy those validators
  per model (that per-model duplication is the anti-pattern being unwound); when a validator is
  identical across ≥2 models, move it onto the base with `check_fields=False`. Keep only field-specific
  rules on each model.
- **The reserved namespace (`vocab.RESERVED_NAMES_0_4`) is only for names expected to become real
  module columns later** (Principle 5) — *not* a catalogue of barred names. `extra="forbid"` already
  rejects any unknown/misspelled column generically, so barring a specific non-feature is arbitrary
  (barring `caller` is as pointless as barring `pasta_recipe`). Before reserving a name, ask: *will a
  release plausibly build this as a module column?* A reserved name earns a specific author-time
  diagnosis (`vocab.RESERVED_NAME_REASONS` via `reject_reserved`); everything else gets the generic
  message. (This is why `caller`/`caller_version` were dropped — consumer-side measurement provenance
  with no module-side meaning — while `reference_db`, a join-target-DB hint, was kept.)
- **Additive within a major** (Principles 3/8): a new column is **optional and minor-legal**, and a
  required field is never demoted. What waits for the major bump is **removing** a column, **promoting**
  one to required, or **retyping** one. A recompile's `artifact.digest` moving is not by itself a
  reason to defer — the authored identity (`content_signature`, per-input hashes) does not move, and
  P4 scopes byte-reproducibility to a fixed `compiler_version`.
- **Round-trip must stay lossless and idempotent** (Principle 7) — prove it with tests, don't assume.
- **CPIC recommendations are keyed by (gene phenotype, drug, POPULATION) — and the populations
  disagree.** Clopidogrel has three (`CVI ACS PCI`, `CVI non-ACS non-PCI`, `NVI`); the same Poor
  Metabolizer diplotype is `strong` in one and `moderate` in another. `DiplotypeRow` has no
  population column, so drafting them all collides on `_TABLE_DUPE_KEYS` and defaulting to one would
  assert a clinical context the author never chose — `draft --drug` therefore *refuses* and lists the
  choices when several exist. Drug rows sit **beside** the phenotype rows (the key includes `drug`),
  they do not replace them. And `recommendation_strength` is CPIC's; `evidence_level` is PharmGKB's;
  they are different axes and a provider must fill only its own.
- **The house algebra is THREE-valued: true / false / unknown — and `None` is never `False`.** This
  is the single rule behind a dozen separate-looking ones: `SourceTerms.share_alike`/`commercial_use`
  (unknown terms are undetermined, never permitted), `CrossrefClient.exists` (`Optional[bool]`, so
  "could not ask" ≠ "no such work"), `LiteratureRow.quotes_found` (null, not zero, when no text could
  be read), `--offline` reporting `unchecked` rather than `absent`, `unresolved` for a missing
  measurement (never the lowest bin), `requires_callable` for an absence nobody called, and
  `hints`/`lookup` returning findings rather than verdicts. When adding anything that answers a
  question, give it three outcomes, not two — and when the answer is unknown, **withhold**: never
  report, never negate. The one place this gets subtle is combining them: use **Kleene** semantics,
  not withhold-on-any-unknown, because `unknown AND false` really is `false` (an ε4-gated conclusion
  is decidably false at ref/ref whatever the call quality was) and collapsing that loses real answers.
- **A drafting provider's skip guard must be DERIVED from the model's rule, not restated beside it.**
  `pgx_draft` skipped a CPIC variant when "no rsID *and* no position", while `HaplotypeRow` requires
  an rsID **or** chrom AND start — and CPIC publishes no chromosome (`sequence_location` carries
  genesymbol/dbsnpid/position and nothing else, probed 2026-08-03). So `draft --gene CYP2C9` died on
  an unhandled pydantic error while `--gene CYP2C19` was fine: 18 CYP2C9 defining variants have a
  position and no rsID, 14 in TPMT, 4 in NUDT15, and none in CYP2C19. Test the guard against the
  model case-by-case rather than asserting a message — doing that immediately found a second bug,
  `chrom` never being passed to the constructor at all.
- **Every provider must write its `SourceRow` — check the newest one, not just the old one.** The
  rule was recorded for `clingen.py` and then `pgx_draft` shipped without it, which is the worst
  instance: CPIC is CC BY-SA **with a no-sale clause**, so a module drafted entirely from it carried
  no `sources.csv`, and the compile gate keys on that file and nothing else — the restriction simply
  vanished. A test that strips `declared_use` and asserts the compile refuses is what keeps the row
  load-bearing rather than decorative.
- **Distinguish "the source did not say" from "the source said something we cannot hold", and
  aggregate repeated warnings.** CPIC's `n/a` means *not scored* (an absence → an empty cell);
  `≥3.0` is a real bound the numeric columns cannot express. Both were reported as "an inequality
  rather than a number", one line per row — ~600 lines for CYP2C19 and 2,184 for CYP2C9, which
  buries every other finding a run produces. Say which case it is, once, with the count. **This has
  now been needed four times in the same provider** (activity scores, copy-number diplotypes, unusable
  defining alleles, and variants with no locus): when a warning is emitted inside a per-row loop over a
  source table, assume it needs collapsing before you ship it, and group by *reason* rather than by row —
  two reasons under one message is the other half of the same mistake.
- **A star allele can be *used* without being *defined*.** `allele_function.csv`/`diplotypes.csv`
  name alleles that `haplotypes.csv` may never define, and a consumer's caller can then never emit
  one — every row about it is dead. `_cross_validate_haplotype_definitions` warns (Class 2), only
  when `haplotypes.csv` is present, since a module leaning on an external caller's definitions is
  legitimate. `*1` is exempt: the reference allele is defined by carrying no variants.
- **Dogfooding means using the shipped surface to do real work — and a capability the tool LACKS is
  the result, not an obstacle to route around.** The moment you reach for an ad-hoc script, a raw
  `httpx` call, or a hand-written query to get past something the product cannot do, the exercise has
  stopped producing its signal: you have proven the task is possible with *general* tooling, which was
  never in question, and learned nothing about the product. When the tool cannot do the step, that is
  the finding — record it (roadmap / field notes) and, if it blocks the work, **build it into the
  product and carry on with the product**. This happened for real: drafting an HFE panel needed
  citations, the enricher turned out to *check* an authored PMID but have no way to *find* one, and
  the reflex was to script PubMed esearch directly. That script would have produced a
  reference example while hiding the actual result — grounding evidence is mandatory for a module, the
  ClinVar snapshot carries no PMIDs, so `draft-panel` cannot produce a compilable panel on its own.
  (The same round's *good* dogfooding went the other way: drafting a real panel exposed that one rsID
  naming two alts collapsed to a single row and silently lost an allele, and that got fixed in
  `clinvar_draft`.)
- **Dogfooding is not validation.** Validation is what tests do — real fixtures, computed
  expectations, adversarial cases. Dogfooding asks a different question: *is this usable, and what is
  missing?* So do not "verify the tool's answers" with a second, independent implementation while
  dogfooding; that is a test, and it belongs in the suite. Use the tool, notice the friction, and
  write down what was not there.
- **The adversarial role, and why it pays.** Dogfooding finds friction; the sharper yield comes from
  switching roles deliberately — *be a beta-tester trying to show the libraries fail at something they
  advertise*, then switch back and fix. Two rules keep it honest, and both matter. **Attack claims,
  not gaps**: a documented deferral (RM5's symbolic alleles, VRS-for-indels) is a decision, and
  "finding" it proves nothing; what counts is where a docstring, a comment or a doc *promises*
  something the code does not do. **Use real data**: no `rs999999999`, no `e-328`. Every finding of
  the 2026-08-03 round came from a real gene, and each is a sentence that quotes the code's own claim
  back at it — `vrs.py` promised "GRCh38 and GRCh37 mint distinct, correctly non-colliding ids" while
  a GRCh37 module minted GRCh38 ids; a comment called `chrom=Y` "the false-positive-free half" while
  PAR1 is diploid in everyone; `draft-panel` asked for a `genotype` and supplied neither `ref` nor
  `alts`.
- **Pick the probe by where the schema generalized from one case.** The two blocking defects that
  round were both "the documented example only ever showed one": `REFERENCE_EXAMPLES.md` §4 shows one
  MT variant per gene, so `HeteroplasmyRow` keyed on the gene and a second real MELAS variant made the
  module uncompilable; the binning bounds were generalized from integer kinds, so a continuous measure
  turned out to be untileable (RM35). Choose a real case with **two** of whatever the example has one
  of, and a case at the edge of a stated convention (a PAR locus for "Y is not diploid", a non-GRCh38
  build for "the key names its build").
- **Turn the tool on the work you just did.** A check written in the morning is the best candidate for
  the afternoon's probe, and it will be wrong in a way its tests were not. The phase-ambiguity check
  shipped, then reported 595 ambiguities in a CYP2C19 module that has none (grouped by row instead of
  by haplotype pair), then — once fixed — told CYP2D6 authors that phase would resolve alleles the
  module defines *identically*, which phase cannot. Both were found by running it on a real 16k-row
  module, neither by re-reading it.
- **Finish each probe as a reference example with a README that names what it broke.** The module is
  the regression test and the README is the evidence; a finding recorded only in a commit message is
  not reproducible. Keep the failing observation in the test suite by demonstrating it on the *old*
  behaviour (strip the column, watch the compiler reject the real rows) rather than asserting that it
  used to fail.
- **Separate "fix it" from "surface it" before writing any code, and be strict about the line.** Fix a
  false claim, a misdiagnosis, a wall of un-aggregated warnings, a guard that is never reached. Surface
  anything where the obvious repair is itself a design decision — and say *why each candidate repair is
  wrong*, because that is the part that makes the item actionable later. RM31/32/33/35 each carry that
  paragraph; RM33's is the cleanest, since one of its two obvious fixes is charter-illegal.
- **Dogfood a P7/dedup finding before you report it — construct a *real, sensible* example against
  the actual code paths, or it is not a finding.** A round-trip/dedup "loss" that is mechanically
  possible but has no real instantiation is noise; walk the data model with a biologist's eye before
  flagging it. The standing example: `annotations.parquet` dedups on the **variant-effect pair**
  `(variant_key, conclusion, negatives)`. An audit flagged "two rows sharing that key + identical
  `conclusion`/`negatives` but differing `gene`/`phenotype`/`category` collapse to the first — a P7
  loss." It read airtight mechanically, yet it is **non-real**, and trying to build one example proves
  why: sharing a `variant_key` forces a *single locus* (a one-to-many rsid is **expanded to distinct
  coord-keys** by the resolver, so paralogs never share a key) ⟹ one `gene`; and identical
  `conclusion`+`negatives` means the *same effect* ⟹ the same `phenotype`/`category`. `gene` isn't
  even carried in `weights.parquet`, so two such rows are physically indistinguishable regardless of
  keying. The constraint set is empty — no real, sensible module hits it. The **genuine** poly-effect
  loss (one locus, two genotypes, *distinct* conclusions — het "carrier" vs hom "affected") is what
  the variant-effect-pair keying already fixed. Lesson: empirical probing + a real-example test beat a
  plausible-looking mechanistic claim; the mechanistic claim, unfalsified, was a mechanical re-flag of
  an already-closed item.
- **Deterministic ordering is load-bearing** (an implicit consequence of Principle 7, not its own
  charter rule). Parquet bytes depend on **row order**, so `artifact.digest` is order-sensitive:
  **authored row order is preserved** through compile → reverse → recompile and must stay that way.
  Never derive emitted rows, CSV/parquet contents, or manifest fields from `set`/`dict` iteration or
  from polars `mode()`/`unique()` without an explicit stable sort or tie-break (both give *no* order
  guarantee — `mode()` is unstable even call-to-call). Prefer explicit `ORDER BY` in SQL, `sorted(...)`
  /`min(...)` for picks, and first-occurrence (insertion) order for dedup. **Column order and cell
  formatting, by contrast, are normalized, not preserved** (reverse emits a fixed `fieldnames` order;
  values are stripped/canonicalized) — that asymmetry is intended. New orderings get a test.
- Use `uv sync` / `uv add`; **never** `uv pip install`. `uv run pytest` runs the suite (see *Testing*).
- New markdown (except this file / `README`) goes in `docs/`.

## Testing

- `uv run pytest` runs the suite; run it **`-vvv`** when diagnosing.
- **Real data + ground truth**: exercise the actual compile / reverse paths against real fixtures and
  **compute expected values at runtime** rather than hardcoding them.
- **Deterministic coverage**: fixed seeds or explicit filters; cover representative *and* edge cases.
- **Meaningful assertions**: prefer relationships and aggregates over existence-only checks; prefer
  set equality (`assert a == b`) over count checks.
- Hardcoding **domain constants** (vocabulary members from the spec) is fine; hardcoding **row/unique
  counts** read off a data dump is not.
- **Avoid the AI test anti-patterns**: happy-path-only tests, hardcoded counts derived from inspecting
  data, mocking a data transformation instead of running the real path, and claiming a test "would
  have caught" a bug without first demonstrating the failure on the buggy code.
- Round-trip / idempotency (Principle 7) and every new ordering get a real test — see the dogfood rule
  above; a mechanically-possible loss with no real instantiation is not a finding.
- **Async tests use `pytest-asyncio`** (kept in the dev deps for when async paths land; today there
  are none).
- **A test that means "no credential" must SAY so — `api_key=None` does not, and `.env` leaks across
  the whole session.** Two mechanisms compound here, and neither is visible on CI:
  - **`api_key=None` is indistinguishable from "not passed."** `PharmVarClient.__init__` does
    `api_key or os.environ.get(API_KEY_ENV)` (`EutilsSettings` the same for `NCBI_API_KEY`), so an
    explicit `None` still picks up a real key. `test_one_source_failing_does_not_sink_the_pass` built
    a "keyless" client that was configured, PharmVar answered its `MockTransport` happily, and the
    assertions about degrading-without-a-key failed — **only for a developer who had legitimately
    configured a key**. Green on CI, broken on the machine that owns the credential, which is exactly
    the wrong way round.
  - **`.env` reaches `os.environ` from an unrelated test and stays there.** `locations.load_env()`
    runs inside each `resolve_*_reference`, so *any* test that resolves a cache path loads the repo's
    `.env` into the process environment and every later test inherits it. Run that file alone and it
    passes; run the suite and it fails. **Suspect ordering whenever a test passes in isolation and
    fails in the suite** — the pollution is a global `os.environ` mutation, not a fixture.

  So neutralize the variable in an autouse fixture, and **`setenv(VAR, "")`, not `delenv`**:
  `load_dotenv(override=False)` skips a key that is merely *present*, so an empty value survives a
  later reload where a deleted one is silently restored. Every reader treats empty as absent
  (`x or environ.get(...)`). `test_eutils.py` had the idiom right for `NCBI_API_KEY` all along;
  `test_pgx_licensing.py` now carries it for `PHARMVAR_API_KEY`. Three real credentials sit in `.env`
  (`HF_TOKEN`, `PHARMVAR_API_KEY`, `NCBI_API_KEY`), so this applies to any new test that asserts
  unkeyed behaviour — a pacing interval, a skip, a degradation warning.

## Documentation & prose style

- Write in natural, human prose. Avoid AI-typical tells (em-dash pile-ups, filler transitions,
  marketing voice). Never hallucinate documentation or overpromise an unimplemented feature.
- Keep the `README` concise; deep detail belongs in `docs/`.
- Describe the format honestly: it supplies **annotation tables**, never sample data and never a
  gene–disease inference. Don't let docs imply a module measures or calls anything — the consumer
  supplies the measurement at query time (mirrors the data-agnostic rule above).
- **Self-correction**: when outdated API knowledge causes a real crash or logic failure, fix the code
  *and* update this `CLAUDE.md` / the affected `docs/` with the correct pattern so the next agent
  doesn't repeat it. Update the guides immediately whenever code is refactored.

## Data & assets conventions

- Generated and sample data lives under `data/`, **git-ignored and build-ignored** — nothing here
  travels with the repo or the package:
  - `data/input/` — input samples, where applicable
  - `data/interim/` — code-generated intermediates
  - `data/output/` — results
- Data that must **travel with the project** (a fixture a test or example genuinely needs) lives in
  `assets/`, committed.
- Any asset that exceeds **~5 MB** and must travel goes through **Git LFS**: `git lfs install` once,
  `git lfs track "<path>"`, then commit the **LFS pointer** — never the raw blob.

**Gotcha — check tree history whenever LFS is introduced; no large blob may remain in history.** A
blob committed *before* `git lfs track` stays in every past commit even after the pointer replaces it
at HEAD, so the pack still ships it. Detect it:

```bash
git lfs ls-files                       # what LFS tracks at HEAD
git rev-list --objects --all \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '/^blob/ && $3 > 5000000 {print $3, $4}' | sort -rn   # large blobs anywhere in history
```

I don't run history-rewriting operations. **If a large blob is found in history, here is the
remediation sequence for you to run:**

1. `git lfs migrate import --include="<path-or-glob>" --everything` — rewrites history, moving matching
   blobs into LFS.
2. Verify: re-run the large-blob scan above (should be empty) and `git lfs ls-files --all` (should list
   the migrated paths).
3. `git push --force-with-lease` the rewritten history; collaborators must re-clone or hard-reset, since
   history has diverged.
4. Optionally reclaim local space: `git reflog expire --expire=now --all && git gc --prune=now`.

## Related repos (read-only unless the task targets them)

`just-dna-pipelines` (compiler/discovery, depends on these libs), `just-dna-lite` (app + webui, the
reference consumer), `just-dna-marketplace` (catalog/storage/serving; consumes the `revalidate`/
`needs_upgrade` derivation these libs supply), `just-dna-agents` (MCP surface — its `get_spec_format`/
`list_colors`/`list_icons` are the drift `authoring_reference()`/`RECOMMENDED_*` replace), `just-prs`.
