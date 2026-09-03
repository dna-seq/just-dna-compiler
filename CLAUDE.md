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

**`docs/` root holds only what is still live.** Five subfolders hold the rest, and nothing in them is
edited as routine work: `docs/history/` (the closed record — the pre-0.6 halves of the three history
files, the round-2 consumer thread, and `ROADMAP_0_7.md`, the 0.7 deferral round closed at that cut),
`docs/proposals/` (the `PROPOSAL_*` design threads, **eight concluded, none live** — **`PROPOSAL_0_7_PT3` became a record on 2026-09-03**, when its third and last item landed: the build plan for RM174, RM160 and RM171, all three decided with the maintainer and none of them designed there. It carries **two** dated addenda — RM160's authored column pair, which its release-class line had priced at none, and RM171's five departures from the build order — a live one wins over the
roadmap files until its items land, and `PROPOSAL_0_7` stopped being live when the twelfth landed;
**`PROPOSAL_0_7_PT2` stopped being live on 2026-09-01**, when it was decided with the maintainer and five of its six
items shipped the same day. It is a record now, and RM166 is the one item still open — tracked in ROADMAP like any
other open item, not by the proposal.
`PROPOSAL_0_7` gained **two** dated addenda on 2026-08-31, RM140 and RM152, and is still a record, because both landed inside the same uncut 0.7.0 — the second one also states the rule that a closed proposal is closed against reopening its own decisions, never against recording a new one taken inside the same release), `docs/probes/` (the dogfood, VCF audit and CIViC rounds — the last of these carries CIVIC_IDENTITY_PROTOCOL, the re-runnable procedure for resolving a variant a source names but does not identify, its source-agnostic handout IDENTITY_FROM_A_NAME, and CIVIC_LEGACY_INSERTIONS, where the two records it cannot resolve are worked by hand at sequence level; rm170_kleene is RM170's design record — the case-by-case advocacy the shipped check follows, and the two repairs it refuses; CONTRADICTION_CORPORA measures the two corpora RM170 is about, CIViC's assert-and-refute pair and STRchive's `evidence` grade, and is where you look before designing anything that reads a source disagreeing with itself; MITOMAP_STATUS reads that source's `status` column as the two-token grammar it is, and measures how much of it ClinVar already carries; rm171_diff_strategy is RM171's adoption shape, **written by the maintainer and built as its specification** — the increment against ClinVar, not the photocopies, and the reason `VUS*` is withheld; read it before touching the MITOMAP lanes, and note that the build's own rejoin moved its motivating number from sixteen to six; CLINPGX_ARCHIVES is the ClinPGx download surface read from a browser, and the reason RM173 closed — a **retired filename still answers 200**, so the lane's default archive was a frozen 2025 object until RM175 rebuilt it onto `summaryAnnotations.zip` and made the builder refuse the old member names), `docs/audit/` (the tier
references re-derived from the code on 2026-08-18 — **evidence, never contract**; the maintained
reference is the one in `docs/` root), `docs/vendor/` (two upstream files kept for reference,
PharmVar's OpenAPI document and its licence text).

| Doc | Answers | Grep for |
| --- | --- | --- |
| [CONSTITUTION.md](docs/CONSTITUTION.md) | the 9 principles + goals/non-goals. Wins over any plan. **Rules only** — no reasoning lives there | `grep -n '^[0-9]\+\. \*\*' docs/CONSTITUTION.md` |
| [CONSTITUTION_AMENDMENTS_HISTORY.md](docs/CONSTITUTION_AMENDMENTS_HISTORY.md) | *why* each amendment was made — the reasoning the charter bans from itself | `grep -n '^## ' docs/CONSTITUTION_AMENDMENTS_HISTORY.md` |
| [AGENT_NOTES.md](docs/AGENT_NOTES.md) | the long-form gotcha book behind this file | `grep -n '^## ' docs/AGENT_NOTES.md`, then the symbol name |
| [RM_TOC.md](docs/RM_TOC.md) | where any `RMn` lives, status included — the complete list. **Claim a new number with `.claude/rm-next.py`** (scan + locked reservation), never by reading the highest off the file — an index is not an allocator, and two sessions once filed the same RM159 | `grep -n 'RM47' docs/RM_TOC.md` |
| [ROADMAP.md](docs/ROADMAP.md) | open items, the idea-book, the reserved-namespace and 1.0-cleanup trackers | `grep -n '^## RM' docs/ROADMAP.md` |
| [ROADMAP_HISTORY.md](docs/ROADMAP_HISTORY.md) | shipped items with their rationale, 0.6 onward. Pre-0.6 is in [history/](docs/history/ROADMAP_HISTORY_PRE_0_6.md) — **use RM_TOC rather than guessing the half** | `grep -rn '^## RM' docs/ROADMAP_HISTORY.md docs/history/` |
| [ROADMAP_0_8.md](docs/ROADMAP_0_8.md) / [ROADMAP_1_0.md](docs/ROADMAP_1_0.md) | deferred items, with the reason for the deferral. **The minor file is named for the release that will decide its contents**, so a cut closes one and opens the next — 0_7 closed on 2026-08-31 into [history/](docs/history/ROADMAP_0_7.md) | `grep -n '^## RM' docs/ROADMAP_1_0.md` |
| [CHANGELOG.md](docs/CHANGELOG.md) | what shipped, newest first (shared across the ecosystem repos); 2026-08-12 onward, earlier entries in [history/](docs/history/CHANGELOG_PRE_0_6.md) | `grep -rn '^## 2026-' docs/CHANGELOG.md docs/history/` |
| [INTEGRATION_0_6.md](docs/INTEGRATION_0_6.md) | the 0.5.4→0.6 surface delta and the per-consumer check/change lists | `grep -n '^## \|^### ' docs/INTEGRATION_0_6.md` |
| [INTEGRATION_0_7.md](docs/INTEGRATION_0_7.md) | the 0.6.6→0.7 surface delta, the same shape one release on — and the one **old-reader break** (`VerificationRecord.producer` vs `extra="forbid"`) | `grep -n '^## \|^### ' docs/INTEGRATION_0_7.md` |
| [SCHEMAS.md](docs/SCHEMAS.md) | models, CSV families, conventions, the hash family (one signature per derived sidecar, plus the two identity halves and the three verification ones — the roster states the rule, never a total), the tri-state inventory, the allele grammar | `grep -n '^## ' docs/SCHEMAS.md` |
| [COMPILER.md](docs/COMPILER.md) | validation ceiling, compile pipeline, **§ Resolution** + round-trip matrix, reverse, coverage, **deterministic ordering**, the **warning-text catalogue** a consumer greps | `grep -n '^## ' docs/COMPILER.md` |
| [ENRICHER.md](docs/ENRICHER.md) | resolver chain, the check table, rate limits, caches, publish/upload, and the open questions the code does not answer | `grep -n '^## ' docs/ENRICHER.md` |
| [MODULE_LIFECYCLE.md](docs/MODULE_LIFECYCLE.md) | origin → publish → a consumer's join; **what pass 2+ moves** | `grep -n '^## ' docs/MODULE_LIFECYCLE.md` |
| [FAQ.md](docs/FAQ.md) | settled questions keyed by *question* ("why did my digest move?") | `grep -n '^\*\*' docs/FAQ.md` |
| [CONSUMER_SUGGESTIONS.md](docs/CONSUMER_SUGGESTIONS.md) | the **open** consumer inbox (`Sn`) — empty means nothing owed | `grep -n '^## S' docs/CONSUMER_SUGGESTIONS.md` |
| [CONSUMER_SUGGESTIONS_HISTORY.md](docs/CONSUMER_SUGGESTIONS_HISTORY.md) | answered `Sn`, verbatim, with the reply; it keeps the **whole** contents list, and the items 0.5 answered (S1–S24, S27, S28) sit in [history/](docs/history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md) | `grep -rn '^## S[0-9]' docs/CONSUMER_SUGGESTIONS_HISTORY.md docs/history/` |
| [CONSUMER_TRIAGE_LOOP.md](docs/CONSUMER_TRIAGE_LOOP.md) | the runbook for answering an `Sn`, and the ledger | `grep -n '^## ' docs/CONSUMER_TRIAGE_LOOP.md` |
| [USE_CASES.md](docs/USE_CASES.md) | a use case → enabled / consumer-side / gap. **Start a design task here** | `grep -n '^## ' docs/USE_CASES.md` |
| [REFERENCE_EXAMPLES.md](docs/REFERENCE_EXAMPLES.md) | how to author each case with today's bricks; indexes `reference_examples/` | `grep -n '^## ' docs/REFERENCE_EXAMPLES.md` |
| [PUBMIND_ASSESSMENT.md](docs/PUBMIND_ASSESSMENT.md) | the 2026-08-28 assessment of PubMind — what it competes with (little), what it complements (a lot, upstream), what its open channel actually contains, and the four-section adoption design behind RM134: a ClinVar-shaped derived snapshot, a three-way ClinVar concordance check, drafting, and the hint | `grep -n '^## ' docs/PUBMIND_ASSESSMENT.md` |
| PROPOSAL_[0_4_1\|0_5\|0_5_1\|0_6\|0_6_PT2\|0_7\|0_7_PT2\|0_7_PT3].md | design threads with their charter checks and open questions. **0.6 has two and so does 0.7** — a PT2 sorts the items that landed behind the first round. **0_7 is a record, not a plan**: twelve items decided per-item with the maintainer, every one shipped, entries in ROADMAP_HISTORY. Its **two dated addenda** (RM140 and RM152, both 2026-08-31) are decisions taken after the round closed, kept there because they have the round's shape and shipped inside the same uncut 0.7.0 — they are addenda rather than a thirteenth and a fourteenth item, and every bare "twelve" in that file means the 2026-08-27/28 round. **0_7_PT2 is a record too** (drafted and decided 2026-09-01): RM163–RM168, the six source-adoption items, each gated on a probe the entry had not run. Read it for the two-stage drift — **five of six entries say something their own probe contradicted, and then four of six drafted verdicts were overturned in the maintainer pass**, so an unprobed entry is a question and a probed one is still only a proposal. RM163/165/167/168 shipped the same day, RM164 parked (spinning off RM171), RM166 is sequenced last. **0_7_PT3 is a record too** (2026-09-03): RM174, RM160 and RM171, all three shipped, and its two dated addenda are where a departure from a build order is recorded rather than contradicted silently | `grep -n '^## ' docs/proposals/PROPOSAL_0_7_PT2.md` |
| [DOGFOOD_0_6.md](docs/probes/DOGFOOD_0_6.md), [DOGFOOD_0_6_FINDINGS.md](docs/probes/DOGFOOD_0_6_FINDINGS.md), [VCF_4_4_AUDIT.md](docs/probes/VCF_4_4_AUDIT.md) | probe rounds and what they broke | `grep -n '^## ' docs/probes/DOGFOOD_0_6_FINDINGS.md` |
| [audit/](docs/audit/README.md) | the 2026-08-18 code-first re-derivation of all three tier references, and the instrument that found RM93–RM100. Its durable material is **merged**; what stays there is dated detail (per-parquet columns, per-command flags) that would rot in a maintained doc. Never edit one to record a fact | `grep -rn '<symbol>' docs/audit/` |

Cross-cutting greps worth knowing: an `RMn` or `Sn` anywhere → `grep -rn 'RM47' docs/`; a symbol's
rule → `grep -rn 'hosting_verdict' docs/ schema/ compiler/ enricher/`; a warning a consumer quoted →
`grep -rn 'have no chrom+start' compiler/ docs/`.

## Read these first, in this order

1. **[docs/CONSTITUTION.md](docs/CONSTITUTION.md) — the durable charter. READ IT BEFORE JUDGING OR
   CHANGING ANYTHING.** Declarative-not-code, no network, backward-compat within a major,
   integrity-as-identity, orthogonal axes, the vocabulary idiom, round-trip/idempotency, requiredness
   compatibility, release-class-is-not-staleness, and what a change costs by layer. When a plan
   conflicts with it, it wins; **an audit that has not read it is incomplete**, since P3/P7/P8 decide
   whether a change is even legal. It is **self-contained** — it names no other document, and the
   navigation into the living material is here. Never add an outward pointer to it.

   **It is rules only, by its own header item**: no reasoning, evidence, open questions, superseded
   states or rhetoric, and no outward reference beyond a published version a rule turns on. When you
   amend it, the *rule* goes there and the *why* goes in
   [CONSTITUTION_AMENDMENTS_HISTORY.md](docs/CONSTITUTION_AMENDMENTS_HISTORY.md) — which may cite `RMn`
   and consumer reports freely. That split is what keeps a file read in full from growing.

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

## Gotchas — one line each, keyed for grep

Every line is a rule. The reasoning behind it — what broke, what was measured, which repair was
refused — sits in [docs/AGENT_NOTES.md](docs/AGENT_NOTES.md) under the tag the line ends with:

```bash
grep -A25 '^- .@start-1based' docs/AGENT_NOTES.md   # the entry; 4–60 lines, -A60 for big ones
grep -n  '^- .@' docs/AGENT_NOTES.md                # every tag in order, with its headline
```

**Read the entry before acting against one of these lines** — most of them have a rejected repair
attached, and the rejected repair is usually the one that looks obvious from the headline.

### Identity: `variant_key`, VRS, digests

- `derive_variant_key` order is rsid → VA (coordinate substitution only) → `chrom:start:ref[:alts]`. `@vkey-precedence`
- Pass `alts` only when *minting* an identity; position-level matching calls it without. `@vkey-precedence`
- `vrs_id` is one id per ALT, parallel to `alts`; keep empty members; never one row per allele. `@vrsid-per-alt`
- A check over recorded values must also count the records carrying none. `@vrs-coverage`
- A VA does not encode `ref` — only the enricher can catch a single-base wrong one. `@va-omits-ref`
- VRS verdicts are verified / mismatch / unverifiable, and severity is whose limit it is, not the mode. `@vrs-three-outcomes`
- `ga4gh.vrs` is a core enricher dep; never in format or compiler. `@ga4gh-vrs-core-dep`
- `refget_accession` raises off GRCh38 and `refget_supports_build` answers the same predicate. `@refget-raises`

### Coordinates and the genome build

- `start` is the 1-based VCF position — never `-1` it. Bounded `ge=0`, not `ge=1`: VCF permits POS 0. `@start-1based`
- A row is stamped before the module is known; re-derive build-dependent stamps at both load sites. `@restamp-for-build`
- `genome_build` is in the manifest and no parquet column — pass the row's build to every mint call. `@build-in-manifest-only`
- The build is injected at load, never authored on a row. `@build-injected`
- `content_signature` is reference-independent, **not** build-independent. `@sig-not-build-independent`
- A "ref mismatch" has three causes; one window read, withhold when ambiguous, group by reason. `@ref-mismatch-causes`
- The ±1 shift reading is wrong on an old-assembly coordinate; only two evidence tiers supersede it. `@old-assembly-vs-shift`

### Alleles: grammar, spelling, hosting

- A non-nucleotide allele is a *spelling* defect — diagnose it, never grammar-check `alts`, never expand `Y`. `@non-nucleotide-spelling`
- Symbolic alleles: VCF's five types, length inside the token; schema accepts lengthless, compiler drops it. `@symbolic-alleles`
- Hosting is three-valued; raw comparison first, and the confident negative is about event size. `@hosting-tri-state`
- An rsID is position-level — identity is `variant_key` + genotype, and back-fill is allele-aware. `@rsid-not-per-allele`
- `absent` means typo *or* withdrawn: name both readings. `VALID_RSID_STATUS` has four members. `@rsid-absent-two-readings`
- NCBI, not Ensembl, is the oracle for rsID merge status. `@ncbi-merge-oracle`

### Resolution and the round trip → also [COMPILER § Resolution](docs/COMPILER.md)

- `compile → reverse → compile` reproduces the module or `strict` refuses; `authored_ident` is why. `@resolution-reversible`
- Allele membership compares the union of every locus a key resolves to, before expansion. `@membership-union`
- The Ensembl snapshot pipe-joins `alt`; every other link uses commas. `@snapshot-pipe-alt`
- Resolution reads the PGx tables too; subjects dedupe with `variants.csv` first. `@resolution-reads-pgx-tables`
- Reverse dropping `rsid_alternates` is closed, not a bug — don't re-flag it. `@rsid-alternates-closed`
- A sidecar is merged, never clobbered — delete it to regenerate after a machinery change; since 0.7 that delete is free. `@sidecar-authoritative`
- A correction to a derived table goes in `overrides.csv`, applied and never merged in; it is a third category in neither table registry. `@overlay-not-inside`
- The enricher reads the overlay at input reads only, never at a merge baseline; answered is per field. `@overlay-read-at-inputs-never-at-baselines`
- An answered set that **silences** a finding is per field; one that **raises** a finding is per subject. `@a-set-that-silences-is-narrower-than-one-that-raises`
- The overlay applies twice (reverse emits the post-overlay table plus the overlay), so no operation may report its own no-op. `@overlay-not-inside`
- Match an overlay key as the model **stores** it, never as the author spelled it — a raw compare grew the table one row per lap. `@overlay-not-inside`
- Resolution reaches the positional tables too since 0.6; `authored_ident` is what keeps the fill out of `content_signature`. `@rm43-positional-fill`
- Unreachable is not absent: write no row, name it separately, warn in both modes. `@unreachable-not-absent`
- **Nobody-asked is a third state** beside asked-and-failed and asked-and-absent; `--offline` is where it bites. `@unreachable-not-absent`
- Answered-and-rejected is a fourth: the row stays and the *reason* moves, never the status. `@answered-is-not-absent`
- A verdict function with several arms owes a reason function with the same arms, pairwise distinct. `@answered-is-not-absent`

### Checks: placement and severity

- Audit `validate`/`compile` parity by **check**, not by table. `@parity-by-check`
- `validate_spec` must refuse everything `compile` refuses. `@validate-refuses-all`
- The compile-only exemption is *resolved rows*, not the word resolution; share the predicate, copy the error. `@validate-refuses-all`
- Know the validation ceiling first; a check needing a reference belongs in the enricher. `@validation-ceiling`
- Enricher checks report, never repair; severity follows the mode. `@enrichment-is-validation`
- A judgement another tier **recorded** is a fact `strict` may gate on — one check only, the one where two authored files contradict. `@a-recorded-judgement-is-a-fact`
- Move a check behind resolution when resolution fills its input (`chrom` for ploidy). `@ploidy-behind-resolution`
- Never re-run a check whose message embeds a count — the manifest then publishes two numbers. `@no-rerun-with-counts`
- A fact-table check the pre-flight also runs arrives twice; dedupe at the extend site. `@first-fact-check-on-both-sides`
- A check is only as wide as the tables it reads; derive the roster, and publish what was read. `@roster-is-as-wide-as-the-tables-it-reads`
- A widening is not done while a caller still gates on the narrow thing; reproduce it from the corpus. `@roster-is-as-wide-as-the-tables-it-reads`
- A *scope* refuses where a *report* withholds; and two answers to one question go side by side. `@roster-is-as-wide-as-the-tables-it-reads`
- Grep for the question, not the bug; a private name keeps the second caller from finding the first. `@roster-is-as-wide-as-the-tables-it-reads`
- Lap-stable means a property of the MODULE, fired matched-or-not; assert equality between laps. `@lap-stable-means-a-property-of-the-module`
- Ask whether the signal already fires with the wrong words; pin adjudicating words on a boundary. `@the-signal-may-already-be-firing-with-the-wrong-words`
- A source re-curating is not a `strict` matter; the two currency findings stay apart, and both edges withhold. `@a-source-recuring-is-not-a-strict-matter`
- A check running on both sides dedupes on the message; re-running is the normal case. `@no-rerun-with-counts`
- The ClinVar `clin_sig` cross-check never escalates under `strict`, deliberately. `@clinsig-never-escalates`
- Splitting a dedup key on a new optional column: **both stated and different**, and narrow the check rather than the key. `@absent-is-not-different`
- A check that cannot fail must not report a zero. `@tautology-zero`
- Two vocabularies that do not fully meet: compute the unmappable half too, and withhold. `@two-vocabularies-that-do-not-meet-withhold`
- A cell key carries the VALUE when the row key is wider — or a second, differing claim vanishes. `@a-cell-key-carries-the-value-when-two-rows-may-state-two-claims`
- One registry's outage may not write a skip against another's check. `@one-registrys-outage-may-not-speak-for-another`
- Ask whether a table-level check's rules are jointly satisfiable. `@jointly-satisfiable`
- An all-digit genotype is a pasted `GT`; diagnose it before the arity check. `@gt-indices`
- Check the relationship, not the members — chromosome granularity, repairing nothing. `@gene-locus-relationship`
- Unknown files in a spec dir are tolerated; a near-miss table name is not. `@misspelled-tables`
- "Keyed kind ⇒ dupe-checked" is not the line — which loop calls the checker is. `@which-loop-calls-the-checker`
- An analogy in a `Field(description=…)` is a claim, and it does not travel with the field. `@field-description-is-a-claim`
- A vocabulary's members have standing; a flat list publishes them as peers. Group by axis, name each successor. `@field-description-is-a-claim`
- A warning's text is an API: pin the phrase, and publish the denominator behind any flag. `@warning-text-is-api`
- A release sweep's *one side only* has two causes: missing from AFTER is this release's regression, missing from BEFORE is the previous one's. `@one-side-only-has-two-causes`
- An exclusion the gate must act on is a field checked for equality, never a sentence in `evidence`. `@one-side-only-has-two-causes`
- A warning code is a permanent key: name the **finding**, one code per remediation, never the emission site. `@warning-code-names-the-finding`
- A `Finding` loses its code at a pydantic field and at any reformat — seed from the classified list, reformat through `restate`. `@finding-loses-its-code-at-a-boundary`
- Count a correction's record over the **overlay**, never over what it removed, or lap 2 disagrees with lap 1. `@suppression-counts-the-overlay-not-the-effect`
- The compiler discards an uncited literature row; `literature.csv` keeps it. `@uncited-literature-dropped`
- One normalizer for a vocabulary two sources spell differently; test **both** sides' raw tokens. `@one-normalizer-two-spellings`
- A join with two granularities needs two kinds of **subject**, or the coarse answer repeats per fine claim. `@the-tier-is-a-property-of-the-subject`
- `MULTI_SEP` splits on `,;|`; a source using one writes the other two as data — measure its separator. `@a-shared-separator-constant-is-not-a-sources-separator`
- A lane-local vocabulary carries the lane's prefix; a reason map only a test reads speaks to nobody. `@a-lane-local-vocabulary-may-not-shadow-a-schema-one`
- `fetch origin <branch>` leaves the tracking ref; an empty `A..B` may mean B does not exist. `@a-ref-that-reads-as-landed-may-not-be`

- A release record's measured half and declared half drift; re-measure when a declaration lands. `@a-record-written-in-two-passes-drifts-between-them`
- Assert the asymmetric invariant when only one direction is entailed; equality forces false claims. `@a-record-written-in-two-passes-drifts-between-them`

### PAR loci and contig ploidy

- `chrom=Y` is not "never diploid" — PAR1 and PAR2 are diploid in everyone. `@y-not-haploid`
- A PAR locus is one place on two contigs: offset-matched partner, keep X, decide **per locus**. `@par-one-place`
- gnomAD does not cover the Y PAR — `not_covered`, outside the strict gate. `@gnomad-no-y-par`

### Binning, citations, literature

- A binning table stating thresholds with no study rows warns in both modes. `@bin-grounding`
- A row cites when its claim is finer-grained than `studies.csv`'s key; the citation table describes. `@rm47-bin-cites`
- A shared endpoint belongs to the higher bin under continuous tiling; `measure_max` is always inclusive. `@dense-bin-boundary`
- Tiling is its own axis: the bin rules read effective `measure_tiling`, and absent means the kind's default. `@measure-tiling`
- The fractional inference fires only against a `quantised` default — only a stated grid can be contradicted. `@measure-tiling`
- It reads bounds only: a key column is not a point on the axis, and letting one vote flips legality. `@measure-tiling`
- A paywall hides the fulltext, not the record; Crossref covers what PubMed does not index. `@citation-existence`
- Existence is not identity — a lookup must say *what* it found. `@existence-not-identity`
- Two readings of one absence are not automatically equal — measure which is likely, and lead with it. `@absence-is-weighted-by-the-base-rate`
- A quote is an attestation: a sharper refusal than redundancy-bearing. `@quote-attestation`
- PMID and PMCID are one letter apart — `PMC 3110566` once parsed as a real unrelated PMID. `@pmid-vs-pmcid`
- A regex timeout needs a killable process; a thread hangs the interpreter at exit. `@regex-timeout-process`
- Derive the `literature.csv` writer from the model; merge-not-clobber never back-fills. `@literature-writer-derived`
- A coverage answer names the tier it was measured at; allele-resolved, position-only and absent are three. `@the-tier-that-answered-is-part-of-the-answer`
- An empty id slot is not a suffix, and a prefix search's first hit is a different variant. `@the-tier-that-answered-is-part-of-the-answer`

### Licensing, sources, the compile gate

- Resolve a sidecar's name and place through `layout`; write to the file you read; both present is an error. `@sidecar-name-and-place`
- Licensing lives as data in the licence table, never as a table in the compiler. `@licensing-as-data`
- Every pass that consults a source **writes** its `SourceRow`. `@write-the-sourcerow`
- And one that **contributes nothing writes none** — key on what this run covered, never on the table or on `not missing`. `@write-the-sourcerow`
- A second surface of an already-declared source may not claim the lane's `(source, layer)` row. `@write-the-sourcerow`
- Derive a column list from the model; a hand-kept one loses a column. `@fieldnames-from-model`
- `source` names the licensed source; only `resolution.csv` also records the link, via `authority`. `@source-vs-authority`
- A layer with no `source` column to join is structurally exempt from the orphan check. `@orphan-check-exempt`
- The compile gate is data-driven; a `--non-commercial` flag would break the round trip. `@gate-is-data-driven`
- `declared_use` is a third axis with three states, not a mode. `@declared-use-third-axis`
- `redistribution` is recorded but not gated — RM27 must design the axis first. `@redistribution-ungated`
- Literature terms are per **article**; there is deliberately no `pubmed` terms constant. `@per-article-terms`
- A host's terms are not its contents' terms: write the floor, let each record override it. `@a-hosts-terms-are-not-its-contents-terms`
- ClinPGx/CPIC/PharmVar are CC BY-SA + no-sale, never a resolution link, and the PharmVar key is personal. `@pgx-research-only`
- Every gated source has a cache; PharmVar's is unpublishable; `offline` outranks an injected client. `@gated-source-caches`
- A source may publish no licence at all; unknown commercial terms warn, they never gate. `@no-named-licence`
- `check_declared_use` gates a fetch; reading a snapshot the operator built is not one. `@acquisition-gate-is-not-a-read-gate`

### PGx sources

- ClinPGx clinical annotations are per genotype. `@clinpgx-per-genotype`
- The key is `(variant_key, drug, genotype, phenotype_category, annotation_id)` — the bare triple is a bug. `@clinpgx-full-key`
- A negative finding about a source is only as wide as the table you probed — say which. `@probe-names-the-table`
- A source publishing both assemblies lists the wrong one first; filter on the assembly field. `@assembly-first-wins`
- An interbase coordinate is `start + 1`; a single-base allele cannot reveal the off-by-one. `@a-one-base-allele-hides-an-off-by-one`
- Load a credential where it is read, not as a side effect of some other call. `@credential-where-read`
- A guard in front of a loader must load too, or it answers differently from what it guards. `@credential-where-read`
- `export FOO=` outranks a `.env` where `unset FOO` does not; diagnose the two absences apart. `@credential-where-read`
- A reproduced mechanism is not a diagnosis: check the run's `built_at` against the fix first. `@credential-where-read`
- The dedup key decides which columns may become several rows, not the source's dialect. `@dedup-key-decides-rows`
- `draft --allele` filters all three tables; `*1` is always kept. `@draft-allele-filter`
- An incidental call must not be able to discard finished work. `@incidental-call-isolated`
- A client leaking its transport library's exception has no contract; retry, then translate, both legs. `@client-exception-contract`
- Test the contract over every client, not the method on one. `@client-exception-contract`
- A **pass** owes its own type too; translate to an `*Unavailable` subclass, never a flat one. `@client-exception-contract`
- Before retyping a leak, grep for handlers catching the leaked type — some are load-bearing. `@client-exception-contract`
- A subclass makes a caller's `except` **order** load-bearing; enumerate handler shapes, and guard with an AST walk. `@client-exception-contract`

### Drafting and the authoring surfaces

- Drafting appends, never mutates; rows go at the end. `@draft-appends`
- A partial row validates by omission and matches on `match_on`, not the natural key. `@partial-row-omission`
- A placeholder protects a decision — fill it where the contig leaves none. `@placeholder-protects-decision`
- A provider fills identity whole or not at all. `@identity-whole-or-none`
- A source with no gene column is drafted by gene through another source's per-record attribution, never a span. `@gene-map-is-another-sources-attribution`
- Decide contestation over the whole group before any dial runs, or the dial picked the winner. `@filter-before-the-group-picks-a-winner`
- `SourceRow` carries the placeholder guard, tested over every `DRAFTABLE` kind. `@sourcerow-placeholder-guard`
- A generated stub must be unable to compile — `mode="before"`, and never reuse `unresolved`. `@stub-cannot-compile`
- Scaffolding refuses per file; drafting refuses per row. `@file-vs-row-refusal`
- Requiredness has three shapes; use `field_category` / `authoring_requirements`. `@requiredness-three-shapes`
- `sources.csv` is draftable, keyed `(source, layer)`. `@sources-csv-draftable`
- A registry-iterating guard is only as complete as its registry — add new models to `_ALL_MODELS`. `@registry-completeness`
- Assert an **equality over a walked set**, never a floor or a count in prose. `@registry-completeness`
- A vocabulary binding lives on the field and carries its members *and* its closedness. `@vocabulary-on-field`
- A closed vocabulary accepts `-` for `_` and stores the declared member — **return `check_vocab`, never just call it**. `@vocab-separator-slip`
- `model_fields` is not the authored surface; skip by `COMPILER_MANAGED`, never by name. `@authored-field-names`
- A generic rejection is a dead end where a specific one is a fix — diagnose, don't apply. `@specific-rejection`
- A hint may not fill a cell a Class-2 check cross-examines. `@hint-redundancy-bearing`
- "It moves the digest" does not forbid a row move; the tool picks where, the caller never indexes. `@row-move-allowed`
- Report a ragged row's field-count mismatch before the type error it explains. `@ragged-csv-row`
- A drafted value that has not moved is an establishable copy — digest the *checked column*. `@draft-digest`
- One `match_on` per batch: sameness is decided against a single covered-set, and a mixed one re-adds every lap. `@match-on-is-per-batch`
- Refute is not reverse: evidence against a claim withholds the axis, it never writes the opposite value. `@refutation-withholds`
- Authoring has an end: `close` + `VerificationDoc.closure`; `validate` stays read-only. `@closure-phase-boundary`
- The attestation binds newline-normalized bytes and their normalized `size`; `manifest.inputs[]` stays raw. `@binding-normalizes-newlines`
- The draft marker is machine-written into `dataset`; a stale one is withdrawn, never re-labelled. `@rm4-dataset-marker`

### Schema evolution

- A new optional column or table is minor-legal; removal, promotion to required and retyping are major. `@optional-column-legal`
- Every authored field declares its first release; per (model, field), measured from the tags. `@a-generic-refusal-cannot-name-its-own-cause`
- An authored column is three touch points; the reverse half is really two, and the row dict fails silently. `@three-touch-points`
- Derived-not-stored is the pattern for a convenience number. `@derived-not-stored`
- Before adding a column to a merge-not-clobber sidecar, ask which run writes it. `@currency-cannot-be-a-column`
- A vocabulary read through `.get(x, default)` makes the map the first edit, and the guard an equality. `@lookup-with-a-default-hides-a-new-member`
- A total function cannot decide a three-valued answer: withhold BEFORE a normalizer whose default is a member. `@a-withhold-cannot-be-delegated-to-a-default-that-is-a-definite-answer`
- Split a judgement column where the source's own legend splits it; map only the half it calls a classification. `@a-withhold-cannot-be-delegated-to-a-default-that-is-a-definite-answer`
- Store a source's value verbatim except when the encoding lies about its own order. `@verbatim-except-order`
- The 0.3 axes are a passthrough — never fill `direction` from `state` at compile. `@axes-passthrough`
- `annotations.parquet` carries **and keys on** `genotype`. `@annotations-keys-genotype`
- A `mode="after"` validator cannot rescue a value the field's type rejects first. `@yaml-version-int`
- `content_signature` hashes the effective `curator`/`method`/`priority`, not the cell. `@effective-defaults-hash`
- A magnitude needs its unit beside it; `weight` has none, and no tool may fill one. `@weight-has-no-unit`
- An effect relative to an unknown allele is evidence that cannot be weighted — count it, never drop it. `@unknown-effect-allele`

### Snapshots, caches, network clients

- gnomAD's rate limits are load-bearing; a pathless error raises **except** the absence messages. `@gnomad-rate-limits`
- The two gene-constraint routes are different releases and must stay distinguishable. `@constraint-two-releases`
- Builder in polars, runtime pass in duckdb. `@duckdb-vs-polars`
- A batch lookup must hash its probe; guard the plan, not the clock. `@hash-the-probe`
- A default computed as an argument runs before the callee's setup. `@default-arg-before-setup`
- Dogfood data is git-ignored, and 0.5.0's published digests are frozen. `@dogfood-data-ignored`
- A published snapshot accumulates — provision only your own files. `@snapshot-accumulates`
- The publisher's allowlist is derived from the artifact's file list; what it drops, the manifest still attests. `@publisher-allowlist-derived`
- The snapshot layout lives in `locations`; a sidecar is a sibling of `data/`. `@snapshot-layout-locations`
- A second published artifact makes provenance a question — answer it in `release.json`. `@release-json-provenance`
- A `latest` pointer discovers a version; a versioned directory pins it, and a local file names neither URL. `@current-discovers-a-version-a-directory-pins`
- Run a knob's **disabling** value; a flag the callee never sees is a flag that does nothing. `@off-switch-needs-a-probe`
- An `ensure_*` must actually be called; `--offline` is the only switch. `@ensure-must-be-called`
- A cache lane has three stages; a hand-kept roster names none of them as missing. `@a-cache-lane-has-three-stages-and-a-list-cannot-say-which-are-missing`
- A derived lane's parents are a **field**; an absent parent is could-not-run, never an empty result. `@a-derived-lane-has-parents-and-an-absent-parent-is-not-an-empty-result`
- A derived artifact's identity is the pair it came from, and half a label is withheld. `@a-derived-lane-has-parents-and-an-absent-parent-is-not-an-empty-result`
- A parent that MOVED and a parent that is GONE are different instructions; report the first, never the second as it. `@a-derived-lane-has-parents-and-an-absent-parent-is-not-an-empty-result`
- Take a snapshot's release label from the bytes, not from the transfer — or the off-switch build is incomparable. `@a-label-read-in-band-beats-one-read-off-the-transfer`
- Every stage a lane lacks carries its reason as a **field**, and a rebuild's outcome is tri-state. `@a-cache-lane-has-three-stages-and-a-list-cannot-say-which-are-missing`
- A rebuild writes to `<base>/<lane>/`, never in place: a short parquet still has a footer. `@a-cache-lane-has-three-stages-and-a-list-cannot-say-which-are-missing`
- Network tests are opt-in: `JUST_DNA_NETWORK_TESTS=1`. `@network-tests-optin`
- A flag must mean the same thing in every function that takes one. `@flag-means-same`
- Don't compute a number and discard it — every consumer then recomputes it. `@dont-discard-computed`
- A constant two deployments want different values of is a knob: a floor, not a flat set. `@retry-attempt-floor`
- A shared rate limiter locks the bookkeeping, not the sleep. `@shared-pacing-gate`
- A fetch-suppression set is derived from the merge key, never restated beside it. `@suppression-from-merge-key`
- The run with nothing to do is a path: re-run a merge pass over a table it already filled. `@empty-work-is-a-path`
- Probe a source's real file before modelling it; the docs lie by omission. `@probe-the-real-file`
- A sidecar writer is atomic or it leaves a valid short file a merge believes. `@atomic-sidecar-write`
- An `enrich` run is a transaction: stage the *answer* beside the target, commit the table at the gate. `@enrich-is-a-transaction`
- A refused `strict` run commits nothing — a written promise now, asserted on the bytes. `@enrich-is-a-transaction`
- `flock` the directory, never a lockfile: the kill it guards against is what leaves one behind. `@flock-not-a-lockfile`
- And never lock a path something rewrites atomically — `flock` binds an inode, so a rename-over defeats it. `@an-index-is-not-an-allocator`
- An index is not an allocator: a number is claimed by a locked write, never by reading the highest. `@an-index-is-not-an-allocator`
- A progress callback's unit is a contract — subjects, because `total` must be known up front. `@progress-unit-is-subjects`
- `--rederive` never shortens a table: answered replaces, could-not-ask keeps its rows. `@rederive-never-shortens`
- A currency check asks the source, never the cache it was drafted from; and a digest label does not compare against a dated one. `@currency-asks-the-source-not-the-cache`
- A baseline the same run overwrites is read before the commit, walked by an AST guard, and the finding fires once. `@baseline-is-the-file-the-commit-overwrites`
- A source's record-id fan-out is a finding: keep every row, count the contested keys, never `mode()` a winner. `@multiplicity-is-a-finding`
- A source's bulk download and its API are different sources; state the status basis or the counts mean nothing. `@two-surfaces-two-denominators`
- Score a RefSeq accession for build with the per-chromosome map — the version alone names no build. `@accession-version-names-no-build`
- A source on an old assembly is placed by the identity it publishes beside the coordinate, never by lifting it. `@published-identity-not-liftover`

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
   **Do not start a second feedback file** — both pre-`Sn` threads were retired for the same reason,
   that an inbox the ledger cannot see is a backlog nobody sees: round 1 on 2026-08-12 (git `53f9260`,
   two undelivered asks refiled as S27/S28) and round 2 on 2026-08-18 (git `635da8c`, nothing
   undelivered). Their per-item dispositions are recorded in the pre-0.6 consumer archive.
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
  disagree** — `clinical_context` is in the dedup key since RM29b, so `draft --drug` writes **every**
  context as its own row and `--population` only filters. Drug rows sit *beside* phenotype rows.
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

### Dogfooding and the adversarial role — one line each, same tags

- A capability the tool **lacks** is the result, not an obstacle to route around with a script. `@dogfood-lacks-are-results`
- Dogfooding is not validation — don't verify the tool's answers with a second implementation. `@dogfood-not-validation`
- The adversarial role pays: attack **claims**, not gaps, and use real data. `@adversarial-role`
- Pick the probe where the schema generalized from one case — take a real case with two. `@probe-uniform-corpus`
- Turn the tool on the work you just did. `@probe-your-own-work`
- Finish each probe as a reference example whose README names what it broke. `@probe-becomes-example`
- Separate "fix it" from "surface it", and say why each candidate repair is wrong. `@fix-vs-surface`
- Prove a P7/dedup finding with a real example against the real code paths, or it is not a finding. `@dedup-finding-needs-example`

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
- A test meaning "no credential" must say so: `api_key=None` is indistinguishable from "not passed",
  `.env` leaks into `os.environ` from any unrelated test, so neutralize with `setenv(VAR, "")`, never
  `delenv`. Suspect ordering whenever a test passes alone and fails in the suite. `@test-no-credential`

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
  `data/interim/` (code-generated intermediates), `data/output/`, `data/repro/<name>/` (a
  reproduction run's working directory — `civic reproduce` defaults to `data/repro/civic/`).
- **Nothing a command generates goes in the repository root.** `civic reproduce` wrote
  `civic-reproduce/` there and needed its own `.gitignore` line to say so; a default under `data/`
  needs none. Check where a new `--out` default lands before shipping it.
- **`scripts/` is the operator-facing drivers, `.claude/` is agent tooling** — the split is by
  audience, not by file type. A deployment runs `scripts/rebuild-caches.sh`; nothing but a Claude
  session runs `.claude/rm-next.py`. [scripts/README.md](scripts/README.md) states the rule.
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
