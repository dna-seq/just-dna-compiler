# Consumer suggestions — history

Answered items from [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md). An item moves here once it
carries a `**Status —**` reply, so the live document holds only what is still unanswered — the same
split as [ROADMAP.md](ROADMAP.md) / [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md), for the same reason. The
inbox only grows, and eleven unanswered entries were invisible inside 6,000 words of answered ones,
which is the problem [CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md) exists to solve.

**The consumer's prose is moved byte-for-byte, never rewritten** — it is the report, not the
resolution. A reply travels with the item it answers, and a group whose items split across the two
files keeps its dateline in both.

**"Answered" is not "finished".** Several of these spawned an `RMn` that is still open;
[RM_TOC.md](RM_TOC.md) is the complete index for that half. Read this file for what a consumer
reported and what we told them, and the roadmap for what is still owed.

## Contents

One line each; the verdict in full is the `**Status —**` paragraph inside the section.

- **S1** `module:` rejects registry identity keys — shipped 0.4.1+0.5.4 (RM17)
- **S2** the other pre-0.4 forbid edges — shipped 0.4.1, docs 0.5.4
- **S3** ClinVar reader OR-chains a hash probe — shipped 0.5.2
- **S4** `clin_sig` check tautological on drafted panels — shipped 0.5.2
- **S5** 0.3 axes derived in Python, app reads parquet — docs 0.5.2
- **S6** panel genotype placeholder is contig-blind — shipped 0.5.2
- **S7** `fetched_at` in the digest breaks find-by-hash — non-issue, docs 0.5.4
- **S8** manifest cannot say which checks ran — filed RM45 (0.6)
- **S9** resolution never reaches the 0.4 tables — filed RM43, docs 0.5.3
- **S10** `pubmed` terms unrecordable, and per-article — filed RM46 (0.6)
- **S11** provenance quote/regex absent from the map — shipped 0.5.4
- **S12** `lookup_citation` misses a fabricated PMID — shipped 0.5.4
- **S13** `fully_resolved` reads as a module verdict — filed RM44 (0.6)
- **S14** `--no-resolve` is the master switch — shipped 0.5.2+0.5.4
- **S15** `PacingGate` is not safe to share — shipped 0.5.4
- **S16** unknown files in a spec dir unspecified — docs 0.5.4 + a guard
- **S17** `source` exists only on generated rows — docs 0.5.4 + a diagnosis
- **S18** `inspect_rows` mis-parses a ragged row — shipped 0.5.4
- **S19** binning thresholds have nowhere to cite — warning 0.5.4, filed RM47
- **S20** a failed Ensembl request reads as a definite absence — shipped 0.5.4
- **S21** the reference omits `SourceRow`, the hand-written table — shipped 0.5.4
- **S22** hg19 literature has no path into a GRCh38 module — filed RM48 (0.6)
- **S23** a hand-declared literature source warns as an orphan — shipped 0.5.4

**Keep this list one line per item.** It is a contents list, not a second copy of the replies: the
detail belongs in each section's `**Status —**` paragraph, where it cannot drift out of step with the
answer it describes. Append a line when an item is archived; ids are never reused.

---

## Field notes from the registry (just-dna-registry)

*Written after the 0.4 pin bump landed and the whole test corpus was run through the server-side
compile path.*

**Status: consumer feedback / design input — not a shipped contract.** Same spirit as
[`CONSUMER_FIELD_NOTES.md`](CONSUMER_FIELD_NOTES.md): illustrative asks framed to stay inside the
[`CONSTITUTION.md`](CONSTITUTION.md) invariants (additive-within-a-major, orthogonal axes,
declarative-not-code). Everything below is **out-of-digest** (identity/metadata), so none of it
touches `artifact.digest` bytes — it is 4.1-shippable, not major-gated.

---

## S1 — `module:` `extra="forbid"` rejects registry-owned identity keys the whole pre-0.4 corpus carries

**Status — answered by work that shipped in 0.4.1 (folded into the 0.5.0 cut); the one piece that was
genuinely missing is fixed in this pass.** No reply was ever written back here, which is the only reason
this read as open. Reproduced on a spec carrying all four keys: `version: v2` does **not** error — it is
coerced to `2.0.0` with the pre-coercion string kept on `version_coerced_from`
([RM17](ROADMAP_HISTORY.md#rm17--semver-on-moduleversion-coercing)), so the corpus-wide blocker is gone;
`namespace`/`owner`/`canonical_id` still refuse on a bare `validate_spec` and disappear cleanly under
`validate_spec(spec_dir, IDENTITY_AUTHORITY_KEYS)`, leaving only that module's own missing fields.

Neither option as written. **`version` went further than (1):** accept-and-drop would have preserved the
0.3 behaviour where a non-SemVer module published with *no version at all*, so it is a genuine advisory
field now rather than a documented no-op. The other three went to `normalize.strip_authority_keys` +
`IDENTITY_AUTHORITY_KEYS`, threaded through `validate_spec`/`compile_module` and the CLI
(`--strip-identity`, `--authority-key`) — your `strip_registry_owned_keys()` upstreamed, byte-preserving
when nothing matches. Not (2)'s reserved set, deliberately: `vocab.RESERVED_NAMES_0_4` is for names a
release may claim **as module columns**, which is the opposite of a key that will never be authored. And
not accept-and-drop inside the validator, for two reasons that still hold — a validator validates, it
does not fix, and baking one consumer's identity convention into the format is the un-injected reference
0.5 spent a release removing.

**What (2) was really asking for was the *specific* failure, and that part was missing.** The per-key
reasons existed (`IDENTITY_AUTHORITY_REASONS`) with `authoring_reference()` as their only reader, so an
author who never injects the set still got the bare `Extra inputs are not permitted` you describe as a
dead end. `normalize.reject_authority_keys` is now a `mode="before"` guard on `ModuleInfo` — the same
shape `vocab.reject_reserved` already had on the row models — naming the key, why it is not authored, and
both ways out. It diagnoses and strips nothing, so validity is unchanged; `nmespace:` still falls through
to the generic message; and the test is parametrized over `IDENTITY_AUTHORITY_KEYS` itself, so a key
added without a reason fails rather than silently reverting to generic.

Nothing to do on your side — keep the strip (it is the same function) or pass `authority_keys=`.
<!-- triaged: 0.5.4 · sha 84bfc5662bdd -->

**The friction.** 0.4 made the `module:` block `extra="forbid"` (good — it catches `colour:`/`nam:`
typos and the `genome_bild:` safety trap). But it also now *rejects* keys that are **filled by the
registry on publish**, not authored: essentially every pre-0.4 `module_spec.yaml` in the wild carries
`module.version` (an author's informal `v2`/`3`), and some carry `namespace`/`owner`. Under 0.3 these
were silently dropped; under 0.4 they are a hard `Extra inputs are not permitted`. That breaks three
registry paths at once for the entire existing corpus:

- **import** of a legacy spec archive → `422 invalid_spec`
- **upgrade** (re-publishes the carried-forward `module_spec.yaml`) → `422` mid-upgrade
- **revalidate** (contract-drift audit) → flags every pre-0.4 module `needs_upgrade` on a key the
  0.3-column back-population can't fix, so the flag never clears

The registry is the authority on `identity.{version,namespace,canonical_id}` and `owner` (SPEC §4):
it stamps them from the request and *overrides* any authored value. So the authored copies are
vestigial by construction — the `forbid` is firing on fields the format itself says the marketplace
fills.

**What the registry did (and keeps, regardless of 4.1).** We added a small, universal normalization
step — `strip_registry_owned_keys()` — that drops the registry-owned set
(`version`, `namespace`, `owner`, `canonical_id`) from the authored `module:` block *before*
`validate_spec`/`compile_module`, on every server compile path (publish, import, upgrade) and before
the revalidate drift check. It is byte-preserving when nothing is stripped, so a clean 0.4 spec is
untouched. This is robust and version-independent, so **we keep it after 4.1** — it is the right
place for *registry*-owned identity to be normalized. This note is a heads-up, not a "we're blocked"
ask.

**Suggestion for 4.1 (pick whichever fits the charter).** The friction is that the format's own
"the marketplace fills these" fields collide with author-time `forbid`. Options, all additive and
digest-neutral:

1. **Ignore-but-don't-reject the registry-filled set.** Keep `extra="forbid"` for genuinely unknown
   keys, but let `ModuleInfo` accept-and-drop the known registry-owned identity keys
   (`version`/`namespace`/`owner`/`canonical_id`) — they are already documented as marketplace-filled
   on `Identity`. A typo like `versoin:` still fails; `version:` becomes a documented no-op.
2. **Reserve them by name** (the vocabulary idiom already used elsewhere): put the registry-owned
   identity keys in the reserved set with a `RESERVED_NAME_REASONS` entry ("filled by the registry;
   omit from authored specs"), so the failure is *specific* ("reserved, registry-filled") rather than
   the generic extra-inputs message — pointing an author (or authoring agent) straight at the fix.
3. **Document only.** If neither is wanted, a one-line note in `COMPILER.md` / the authoring reference
   that authored specs must omit `module.version`/`namespace`/`owner` (registry-filled) would at
   least make the 0.4 tightening a known migration step rather than a surprise.

Our lean is (1) or (2): a large corpus of authored specs carries `module.version` today, and an
author reading "extra inputs not permitted" for a field the docs elsewhere describe as
marketplace-filled is a confusing dead-end.

## S2 — this is probably not the only pre-0.4 → 0.4 migration edge

**Status — the ownership table shipped in 0.4.1 and its code comment names this item; the migration
enumeration is refused with a reason rather than deferred; the documentation half is fixed in this pass.**

The table exists and is **generated**, not written: `authoring_reference()` gives you all three
categories in one payload — `models` lists *only* authored fields, a compiler-stamped column is excluded
from `models` and present in `json_schemas()`, and **`registry_stamped_keys`** maps each registry-filled
`module:` key to why it is not authored. Reachable as `just-dna-compiler reference --summary`. It was
undocumented in prose, which is presumably why you did not find it; [SCHEMAS.md](SCHEMAS.md) §
*Generated authoring reference* now states the boundary and where each category lands.

**The enumeration of "which columns/keys moved from warn to reject in 0.4" cannot be written, and that is
the answer rather than a deferral.** Pre-0.4 dropped every unknown key silently, so the newly-rejected
set is the *complement* of a finite set — every name the models do not declare — and no list can hold it.
The finite side is the surfaces that close their namespace and the legal keys of each, which is what the
generated payload already gives you: the yaml blocks (`ModuleSpecConfig`, `ModuleInfo`, `Defaults`,
`GenePanelSpec` for `panel:`, `Contribution` for an `authorship:` entry) and every row model, whether it
inherits `extra="forbid"` from `AuthoredModel` or sets it directly as the generated sidecars do. A prose
migration table would be one more hand-kept list of a model's columns, which is the failure this repo
keeps repeating — the `SOURCES_FIELDNAMES` literal that silently lost `redistribution` is the freshest
instance, and it made RM27 a gate reading a column that had reached no file.

So `registry upgrade --trim --force` stays the right home for the lossy half, and an operator planning a
`--trim` pass reads the legal key set from `reference --summary` rather than reconstructing it from a
changelog diff. Nothing filed.
<!-- triaged: 0.5.4 · sha a19316700932 -->

The `module.version` case surfaced only because the registry runs the *whole* corpus through
`validate_spec` on every publish/import/upgrade — it's a good fuzzer for "authored shapes that were
tolerated pre-0.4 and are now `forbid`-rejected." Given `extra="forbid"` now covers the SNP core
(`VariantRow`/`StudyRow` via `AuthoredModel`), `Defaults`, and `ModuleInfo`, other silently-dropped-
then-newly-rejected keys are likely lurking in real specs (stray `defaults:` keys, legacy column
aliases). A short **"authored vs. registry-filled field ownership"** table in the authoring reference
— which keys an author sets, which the compiler derives, which the registry stamps — would make the
`forbid` boundary legible and pre-empt the next round of this. The registry's strip handles the
identity keys durably; the rest are author-facing and best addressed in the format's docs/vocab.

For the newly-`forbid` surfaces generally — an unknown CSV column *or* a `module_spec.yaml` key
(`module:`/`defaults:`/`panel:`/`authorship:` + top level) that a pre-0.4 lax schema only warned
about — the registry added a **lossy, opt-in `registry upgrade --trim --force`** that drops the
offenders so a legacy spec recompiles, and reports a version *blocked* (rather than crashing) when
such offenders are present without `--trim`. Registry-owned `module:` keys are excluded (the always-on
strip handles them). That's the right home for a *lossy* fix (explicit human ops), so no format change
is requested for it. But it reinforces S2's ask: the more
of the pre-0.4 authored surface that silently-dropped-then-now-rejects, the more of this a catalog
operator has to triage by hand. A migration note enumerating the newly-`forbid` surfaces (which
columns/keys moved from warn to reject in 0.4) would let operators plan the `--trim` pass instead of
discovering each blocker one compile at a time.

---

# Field notes from just-dna-lite — the 0.5 enricher at panel scale

*Written 2026-08-10 while rebuilding all ten `just-dna-seq` modules on the 0.5 route, including three
ClinVar gene panels: `cardio` (115,060 weight rows), `cancer` (139,254) and `pathogenic` (617,001,
genome-wide, 4,793 genes).*

**None of it is digest-moving.** S3 and S4 are **performance** findings in the enricher's network
tier; S5 is about where a derived axis is computed; S6 is about what a drafting provider writes into
a cell a human is then asked to fill. No schema, model, manifest field or emitted row changes in any
of them, so all four are patch material inside the closed 0.5 digest window rather than 0.6/1.0 work.*

**Status — S3, S4 and S6 shipped in `just-dna-enricher` + `just-dna-compiler` 0.5.2 (2026-08-10)**,
with the five freeform items filed alongside them and the documentation half of S5. S5's open
question — whether an artifact should carry the derived 0.3 axes at all — is parked in
[ROADMAP.md](ROADMAP.md) as a design question: what bars it is that filling a blank asserts what no
curator wrote, not the bytes. Digest
neutrality was **verified, not assumed**: all eleven reference examples recompile byte-identical
against `HEAD`. [CHANGELOG.md](CHANGELOG.md) records what each became, including the chrY half of S6,
which was checked against a real `SRY` row and did not reproduce. The notes below are left as
written — they are the report, not the resolution.

## S3 — the ClinVar reader OR-chains its predicates where DuckDB wants a hash, and it is up to 1000×

**The friction.** A gene panel of any real size does not finish. `enrich()` on `cardio` (57,696
ClinVar records) ran **two hours without completing**, at 12% CPU and with no disk I/O — which reads
like a deadlock and is not one. It is a single DuckDB query evaluating a very large expression tree.

**It is not the cache, and that is worth stating because it is the natural first suspect.** The
snapshot is local parquet, the run is `--offline`, and on this machine
(`clinvar_2026-06-27`, 4,431,781 records, 306 MB, 25 files):

| | |
|---|---|
| `duckdb.connect` + `CREATE VIEW … read_parquet('data/*.parquet')` | 0.07 s |
| `SELECT count(*)` — a full scan of all 4.4M records | 0.03 s |

So scanning the whole reference is free. The cost is entirely in **how the predicate is written**.
Measured against that view, same connection, same 5,000 alleles sampled from the snapshot itself:

| query shape | time | result |
|---|---|---|
| `WHERE (chrom=? AND start=? AND ref=? AND alt=?) OR …` × 5,000 | **127.13 s** | 5,000 hits |
| insert the 5,000 into a temp table, `JOIN` on the four columns | **0.13 s** | 5,000 hits |

**~1000×, identical output.** DuckDB cannot turn a disjunction of equality *conjunctions* into a hash
probe, so it evaluates every predicate against every row: cost scales with `alleles × rows`, i.e.
quadratically in the module. That is the whole explanation for the two-hour non-finish.

**The same shape appears on a single column, and still costs 15×** — which is the surprising half,
since a reader might reasonably expect the planner to fold `a=? OR a=? OR …` into an `IN` set. On the
`pathogenic` gene list:

| query shape | time |
|---|---|
| `WHERE (gene = ? OR gene = ? OR …)` × 4,793 | **15.22 s** |
| `WHERE gene IN (?, …)` — same 4,793 | **1.02 s** |

**Which call sites are affected, and which are already right.** Worth spelling out so nobody
"optimizes" the two that are fine:

| function | predicate shape | verdict |
|---|---|---|
| `clinvar.lookup_clin_sig` | 4-column conjunctions, OR'd | **slow** — the 127 s case, and the hot path |
| `resolver._lookup_rsid_candidates` | `(chrom = ? AND start = ?)`, OR'd | **slow** — same shape; used by the Ensembl *and* ClinVar links |
| `clinvar.select_by_gene` | single-column equalities, OR'd | **slow** — the 15 s case |
| `clinvar._lookup_positions_by_rsid` | `rsid IN (…)` | fast, leave alone |
| `clinvar.citations_for` | `variation_id IN (…)` | fast, leave alone |

**Suggested fixes, in the order we would take them.** All are query-shape only: same rows, same
`ORDER BY`, same output, so `resolution.csv` is byte-identical and no digest moves.

1. **Multi-column predicates → temp table + `JOIN`.** For `lookup_clin_sig` and
   `_lookup_rsid_candidates`: `CREATE TEMP TABLE wanted(...)`, `executemany` the tuples in, join on
   the key columns. Nothing beyond stdlib and the duckdb dependency already present — no Arrow or
   polars, which matters since polars is `[dev]`-only in the runtime tier. This is the whole fix for
   the 1000× case, and it makes the batching workaround below unnecessary.
2. **Single-column OR-chains → `IN`.** For `select_by_gene`, a one-line change for 15×.
3. **One connection per enrich run.** `lookup_loci`, `lookup_clin_sig` and `citations_for` each call
   `_connect` and close it. At 0.07 s a rebuild this is *not* where the time goes and we would not
   suggest it on its own — but once (1) lands it becomes a visible share, and threading one
   connection through is tidier than three.
4. **A regression guard.** The failure mode is invisible in a unit test (small inputs are fast) and
   catastrophic at panel scale, which is exactly the shape that regresses silently. A benchmark that
   resolves a few thousand fixed alleles and fails above a generous ceiling would pin it.

**What we did meanwhile, and would happily delete.** `just-dna-lite`'s `clinvar_runner` slices
`variants.csv` into 10,000-row spec directories, enriches each, and concatenates the
`resolution.csv` files — safe only because every resolver decision is per locus (allele-aware
genotype fit, one-to-many rsID expansion, PAR representative), so a row-boundary split can separate
loci from each other but never a locus from its own alleles. It caps the allele count per call and
therefore the quadratic term, turning "never finishes" into 62 batches for `pathogenic`. It is a
workaround for (1) living in the wrong repo; fix (1) and the batching goes away.

<!-- triaged: backfilled · sha a02c30a6ac7c -->

## S4 — the `clin_sig` cross-check is tautological for a provider-drafted panel

**The friction.** `verify_clinsig` re-reads each resolved allele's clinical significance and compares
it to the authored one. On a 7,818-row panel: **27.1 s with it on, 2.6 s with it off**, byte-identical
`resolution.csv`, and **0 conflicts either way** — necessarily 0, because `draft_gene_panel` copied
that `clin_sig` out of the very snapshot the check reads. Ninety percent of the resolve time to be
told that a value equals itself. (Live confirmation mid-build on `pathogenic`: 83 s/batch → 10 s/batch
when we turned it off.)

**The default is right and we are not asking to change it.** Where a human typed the `clin_sig`, this
check is one of the best things in the enricher — it is how a module stays honest about the source it
claims. The gap is only that a *provider-drafted* module has no way to say "this came from you".

**Suggestion.** `draft_gene_panel` already pins what is needed: it writes
`GenePanelSpec.reference` + `reference_sha256` (the ClinVar `clinvar_file_date` and `source_sha256`).
If `enrich()` compared that declaration against the snapshot it is about to check and found them
equal, it could skip the pass and *say so* — "not run: drafted from this release" — which is both
faster and more honest than reporting a check that could not have failed. Reporting "0 conflicts" for
a structurally guaranteed result is mild misinformation: it looks like evidence and is not.

Second-best, and much cheaper to ship: a line in the panel docs saying the check is redundant for a
drafted panel and that `verify_clinsig=False` is the intended setting there. After S3 fix (1) the
*speed* argument mostly evaporates — 0.13 s is not worth optimizing — but the honesty argument does
not, so this is worth a decision either way rather than closing as "fixed by performance".

<!-- triaged: backfilled · sha c54983dc586f -->

## S5 — the 0.3 axes are derived in Python, and the app reads parquet

*Written 2026-08-10, reading the rebuilt curated modules back through the app's `report_logic`.*

**Two things that look like breaks and are not.** Both are consistent across all four curated
Generation-I ports (`coronary`, `longevitymap`, `vo2max`, `superhuman` — identical shape), which is
what says "corpus property" rather than "regression in this build":

- **`variant_key` is the rsid, not a `ga4gh:VA.…` id.** That is case 1 of `derive_variant_key`,
  ahead of the VRS case: an rsid-authored row keeps the identity its author wrote. The per-ALT VRS
  ids are in `resolution.csv`'s `vrs_id`, which is where the consumer found them. Nothing to change —
  worth stating only because the format tree's own agent notes lead with "`variant_key` is the VRS
  allele id for a resolved substitution", a headline whose body then gives the precedence correctly.
- **`direction` is empty.** It is an authored optional column and these modules were authored against
  0.2, when `state` was the only axis. `weights.parquet` carries it as a passthrough; the compiler
  does not compute it, and should not — that would be filling in a claim the curator never made. The
  app still renders correctly because `report_logic` reads `state`.

**The forward-looking half, which is the actual ask.** A consumer that moves from `state` to
`direction` — the migration the 0.3 orthogonality split invites — reads every legacy module as
directionless. The format has the answer already: `derive.direction_from_state` /
`VariantRow.effective_direction` / `upgraded()`. The gap is that they are **Python accessors and the
app reads parquet**, so from a SQL or polars query the derivation does not exist and the empty column
is all there is. `COMPILER.md`'s coverage table did not resolve this for us: the `direction` row ticks
both "`weights.parquet`" and "derived from `state`" and reads *complete*, and it took reading
`derive.py` to see that the two ticks are in different tiers.

**Suggestion, and we are not asking for a schema change.** A paragraph in COMPILER.md § Upgrade
derivation saying the parquet column is the authored value only, that empty is correct for a legacy
module, and that a parquet-side consumer should apply `direction_from_state(state, weight)` itself,
would close it — the function is already public and leaf-importable, which is what makes this a
documentation fix rather than a feature. Splitting that coverage row so each tick names its tier would
have saved the trip through the source. Whether an artifact should ever carry the derived axes is a
larger question and we have no stake in it; today's answer (authored-only, derive at read time) works
for us as long as it is written down where a consumer looks.

<!-- triaged: backfilled · sha 9b5c0fe1b3a3 -->

## S6 — `draft_gene_panel`'s genotype placeholder is contig-blind, and the mistake is quiet

*Written 2026-08-10, from the same panel rebuild.*

**The friction.** The `<<REPLACE>>` genotype exists because zygosity is a judgement the source does
not make — carrying a pathogenic allele is a carrier state or an affected one depending on the
condition's inheritance mode. That reasoning is right, and it is why `_genotype_worklist` reports the
alleles rather than writing them.

**But on a non-diploid contig there is no judgement to make.** The mitochondrial genome is haploid,
chrY is hemizygous: exactly one genotype is expressible per allele, so the human decision the
placeholder is protecting does not exist there. Every consumer of `draft_gene_panel` therefore has to
independently rediscover that its natural "write both zygosities" fill is wrong for those rows. We
did: `A/G` and `A/A` on 264 mitochondrial loci in `pathogenic` and 260 in `cardio`, both of which
assert a second copy that is not there.

**The compiler catches it, but quietly.** It says the right thing — *"chrom=MT is not diploid here —
use a single-allele genotype (e.g. 'G') for a homoplasmic/hemizygous call"* — and it covers chrY as
well as MT (checked directly: a `Y` row with `A/G` warns identically). The problem is volume. On a
617,000-row panel the output is aggregated to **8 visible lines for 264 affected rows**, so the
finding reads as a footnote rather than a defect, and the chrY warnings were truncated out of the
visible tail entirely — which is how we first, wrongly, concluded Y was not covered at all.

**Suggestion.** In order of how much they remove:

1. **Have the provider fill the genotype where only one is possible.** For a record on MT or chrY,
   `_row_cells` can write the single-allele genotype outright instead of `<<REPLACE>>` — no judgement
   is being pre-empted, and it deletes the whole failure mode rather than describing it. The rows
   that genuinely need a human keep their placeholder, which makes the remaining worklist *more*
   meaningful, not less.
2. **Failing that, say it in the worklist.** `_genotype_worklist` already prints one line per stubbed
   row with the alleles to choose from; for a non-diploid contig it could print
   "MT — homoplasmic, write a single allele" instead of "an allele pair from {A, G}", which currently
   instructs the author to do the wrong thing.
3. **Consider raising the aggregation cap for this particular finding**, or summarising it as a
   count ("264 rows carry a diploid genotype on a non-diploid contig") rather than a truncated
   sample. A defect that scales with the module should not get quieter as the module grows.

We fixed it consumer-side (`NON_DIPLOID_CONTIGS = {"MT", "Y"}`, one row instead of two, pinned by a
test on an all-mitochondrial panel), so this is not a block — but it is a rake that every panel
author steps on once, and (1) removes it for all of them.

---

<!-- triaged: backfilled · sha 3f48bba94f04 -->

# Field notes from the registry — adopting 0.5.2

*Written 2026-08-11: S7 while re-deriving why three panel digests moved, S8 while wiring
`clin_sig_not_checked` through the publish and dry-run paths.*

## S7 — `sources.csv` stamps `fetched_at` into the digest, so a rebuild is never reproducible

**Status — non-issue: the identity you need already exists, is invariant under this, and is the one the
charter defines for the question. One real documentation defect found behind it and fixed in this pass;
nothing filed.** Reproduced on `reference_examples/hfe_hemochromatosis`, three compiles: untouched
recompile → digest `36f184f7…` **identical**; change *only* `fetched_at` → digest `ccc1aec4…`,
`content_signature` **unchanged at `44ad4449…`**, and `sources.parquet`'s own sha moved
`e127c3ce…` → `d50ff8fb…`. So the digest is not stamping a timestamp into an identity that should have
ignored it: the bytes it names really did change, and it is doing its documented job.

**The premise does not hold for a rebuild, and it is stronger than that — a rebuild cannot move
`fetched_at` unless you make it.** `licensing.merge_sources_csv` merges with `setdefault` on
`(source, layer)`, so an already-recorded row **wins**. Probed directly: `record_source_terms` run twice
across a real second boundary leaves `fetched_at` byte-identical; delete the file and only then does it
re-stamp. Your workaround is therefore not a workaround but the tier's enforced behaviour — `enrich()`
treats an existing sidecar as authoritative and never clobbers it — and the thing you expect someone to
forget is the thing they would have to do *deliberately*: delete `sources.csv` first, which is documented
as the step required to regenerate after a machinery change. "Byte-identical inputs" was never the case
being measured; a fresh `sources.csv` is a different input.

**Which identity answers "same content, rebuilt" is settled by Principle 4, not by taste.** Identity has
two halves: `artifact.digest` is the **byte** identity (*these bytes, from this compiler*) and
`content_signature` is the **content** identity (*this data, however and wherever it was compiled*).
`find-by-hash` for dedup and provenance wants the second — `fetched_at` is outside `SOURCE_FACT_FIELDS`
by design, so it is invariant exactly as you want — and `just-dna-compiler signature <spec>` computes it
**without compiling**, which also answers the CI change-signal you say you lost.

**Where we were genuinely at fault**, and the likely proximate cause of the afternoon: SCHEMAS.md's hash
table called `artifact_digest` *"the version's immutable **content** identity"* — the exact conflation
that makes a moved digest read as a content change. Both fixed there: the row now says **byte** identity
and names the trap, and § *Identity & integrity* states the reading (moved digest + unmoved signature =
provenance-only change) with the keying rule spelled out.

**Each of the three options is worse than the status quo, and (1) is unsound rather than unwanted.**
Computing the digest over a table with `fetched_at` blanked breaks verify-then-install: `verify_manifest`
re-hashes every `artifact.files[]` entry from disk and compares it to the declared sha *before*
recomputing the root, so a digest over anything but the shipped bytes is one no consumer can check. The
mtime analogy is what misleads here — a build system's excluded mtime is not *inside* the artifact, and
this timestamp is a column in the parquet. (2) removes a column from the artifact, which is major-only
under P3, and is lossy in a way the manifest cannot absorb: `fetched_at` is **per source row** — five
sources, five fetch times — while `built_at` is one instant per run. (3) as worded would be actively
misleading, since a rebuild does *not* necessarily mint a new digest; what was missing was where to look,
which is now written down.
<!-- triaged: 0.5.4 · sha 25cfaae82d29 -->

*Written 2026-08-11, adopting 0.5.2 and re-deriving why three panel digests moved.*

**The friction.** Rebuilding a module with **byte-identical inputs** produces a **different**
`artifact.digest`. `SourceRow.fetched_at` is stamped when the row is written, `sources.csv` compiles
to `sources.parquet`, and that parquet is one of the four `artifact.files` the digest is a Merkle root
over. So the timestamp is inside the identity of the artifact.

Isolated rather than inferred. On one spec, same machine, same snapshot:

| action | digest |
|---|---|
| `compile` twice, spec untouched | **identical** |
| change **only** `fetched_at` in `sources.csv`, recompile | **different** |

That second row is the whole finding: no data changed, and the artifact is a different artifact.

**How it surfaced, which is the part worth reading.** Three ClinVar panels came out with new digests
after a rebuild. We assumed content had changed and went looking: ruled out resolution row *order*
(proved digest-invariant — same row set, same digest), duplicate rows, authored row order
(`select_by_gene`'s `ORDER BY` is unchanged), and finally the library itself — the same spec resolved
under 0.5.1 and 0.5.2 gives **byte-identical** `resolution.csv`, so 0.5.2's rewritten lookups are
faithful, exactly as the changelog claims. The one thing left was a timestamp. Cheap to find once
suspected; expensive to suspect, because a digest change reads as a content change.

**Why it matters beyond tidiness.** The registry ships `find-by-hash` for dedup and provenance, and
this defeats it for any module rebuilt rather than recompiled: the same content, rebuilt, will never
match. It also means "the digest moved" cannot be used as a change signal in CI.

**Suggestion.** The tension is real — `fetched_at` is genuine provenance and worth recording. Options,
cheapest first:

1. **Keep it, exclude it from the hash.** `sources.parquet` stays in `artifact.files`; the digest is
   computed over the table with `fetched_at` blanked, the way a build system excludes mtimes. The
   value still ships and is still readable.
2. **Move it out of the artifact** into the manifest's provenance block, beside `built_at` — where a
   timestamp already lives without being load-bearing for identity.
3. **Document it**, if neither is wanted: one line saying a rebuild necessarily mints a new digest,
   so nobody else spends an afternoon looking for the content change that did not happen.

Our workaround is to keep the previous `sources.csv` across a rebuild, which is exactly the kind of
thing that stops being done the moment someone forgets.

---

## S9 — the 0.4 table families are materialized verbatim, so `resolution.csv` never reaches them

**Status — option 2 shipped in 0.5.3 (2026-08-11); option 1 is filed as
[RM43](ROADMAP.md#rm43--resolution-reaches-the-snp-core-only-so-a-04-led-module-is-rsid-joinable-and-nothing-more),
and it is not 1.0 for the reason given below — nor 1.0 at all any more.** Its prerequisite is a stamped
identity column, which the 2026-08-11 charter amendment makes **0.6** work: a new optional column is
additive and minor-legal, and only removal, promotion to required or retyping waits for a major. Reproduced on this tree's own
`reference_examples/pgx_slco1b1_simvastatin/`, so the note needed no extra evidence. Three things the
investigation added: option 1 does not merely move `artifact.digest`, it **breaks Principle 7** —
materializing the coordinate and running compile → reverse → compile moves `content_signature`, because
reverse re-emits a filled coordinate as an authored one, which is what `VariantRow.authored_ident`
exists to prevent and no 0.4-family model has; `manifest.fully_resolved` is vacuously `true` for a
table-only module, against the trust rule its own field comment states; and `heteroplasmy.csv` was
missing from the enricher's subject list entirely, so that family could not have been resolved even in
principle (fixed in the same cut). What ships now is the warning, with the second count — how many of
the unjoinable rows `resolution.csv` *could* place — because that is what separates "never enriched"
from "the coordinates exist and this tier does not apply them here". <!-- triaged: backfilled · sha 6ad21f1db1a7 -->

Filed from just-dna-lite, 2026-08-11. Not a bug report — the behaviour is consistent and arguably
correct — but a gap we had to work around in the consumer, and one every 0.4-led module will hit.

`compile_module` applies resolution to the SNP core (`weights.parquet`). The `_TABLE_KINDS` loop
takes a different path: `_load_csv_rows` → `_build_table` → `write_parquet`, with no resolution
step. So a module led by one of those families keeps exactly the coordinates its author typed.

For an rsid-authored module that means **none**. Our `pharmgkb` module compiles cleanly, validates,
and publishes; `resolution.csv` resolves all 147 of its variants; and every one of the 1,482 rows in
`pharm_variants.parquet` has `chrom`, `start` and `ref` null. Nothing warns, because nothing is
wrong by the compiler's lights — the author did not supply coordinates and the compiler does not
invent them.

The consequence lands one layer out. A VCF is joined by position, and a table with no positions
joins to nothing at all — silently, as an empty annotation rather than an error. We now detect the
null-coordinate case at annotation time and fall back to an rsid + genotype join, which works but
narrows the module to VCFs that carry rsIDs in `ID`. Many callers (DeepVariant among them) do not.

Three ways this could close, in our order of preference:

1. **Resolve the 0.4 families too**, the same way the SNP core is resolved: join `resolution.csv` on
   `variant_key` and fill `chrom`/`start`/`ref`/`alts` where the author left them empty. This makes
   a pharmacogenomics module positionally joinable and costs the author nothing. It moves
   `artifact.digest` for every existing 0.4-led module, so it is a 1.0 item, not a 0.5.x one.
2. **Warn at compile time** — "N rows in pharm_variants.parquet have no coordinate and
   resolution.csv resolves them; they will not match a VCF by position". Cheap, non-breaking,
   digest-neutral, and it would have saved us the investigation.
3. **Say so in the docs**, if neither is wanted: one line stating that resolution applies to the SNP
   core only, so a 0.4-led module is rsid-joinable and nothing more.

Worth noting the asymmetry that made this surprising: the same authored spec produces resolved
coordinates in `weights.parquet` and null ones in `pharm_variants.parquet`. Whichever way this goes,
the two paths reading the same `resolution.csv` and disagreeing about it is the part that reads as
accidental.

### S9 corroboration — independently reproduced from just-module-creator, 2026-08-11

Second consumer, different code path, same result. Recording it because the reproduction isolates
the mechanism more sharply than the original report could, and because two unrelated consumers
hitting this in one day is the argument for option 1 or 2 rather than option 3.

Minimal case — one authored row, no SNP core at all:

```
spec/module_spec.yaml          # name: statin_demo, genome_build: GRCh38
spec/pharm_variants.csv        # rsid,drug,conclusion,gene,genotype,phenotype_category
                               # rs4149056,simvastatin,…,SLCO1B1,C/C,toxicity
```

`compile_module(..., resolve_with_ensembl=True, ensembl_cache=None, strict=False)` succeeds, writes
`pharm_variants.parquet`, and the single row has `chrom` and `start` null. Expected so far — nothing
was resolved.

The isolating half is the second run. Adding a `resolution.csv` that covers the variant:

```csv
variant_key,rsid,chrom,start,ref,alts,genome_build,source,status
rs4149056,rs4149056,12,21178615,T,C,GRCh38,authored,resolved
```

changes nothing in the parquet — `chrom` and `start` are still null — which rules out "no resolution
table was available" and leaves only "this family does not consult it".

**The detail we think is worth having.** That second compile *did* read the file, and said so: it
emitted `VRS allele identity covers 0/1 allele(s) in resolution.csv (0%)` and recommended
`just-dna-enricher vrs mint`. So a single run demonstrably loads `resolution.csv`, reports on its
contents, and still does not apply it to the only table the module has — while emitting no warning
about the coordinates it left empty. That is the asymmetry S9 calls "accidental", visible inside one
invocation rather than across two modules.

It also sharpens why option 2 (warn at compile time) is worth doing even if option 1 waits for 1.0:
the run already holds both facts it would need to emit the warning — the resolved rows, and the
null-coordinate rows — at the same moment.

No preference beyond S9's. Filed from the authoring surface rather than the annotation surface, so
we have no VCF-join stake in the outcome; our interest is only that a module author gets told, since
today the spec that produces this looks entirely healthy: `validate --strict` passes, the compile is
green, and the artifact verifies.

## S8 — the manifest records what resolution *achieved* but not which checks *ran*, so `unchecked` and `clean` are indistinguishable to a downloader

**Status — accepted and filed as [RM45](ROADMAP.md#rm45--the-manifest-is-rich-about-resolution-and-silent-about-verification-so-unchecked-and-clean-are-one-state-to-a-downloader), targeted at 0.6; your two-field shape and your trust caveat are both adopted.**
Confirmed structurally rather than by example, which is the strongest form the claim can take:
`Compilation` has twelve fields and none is about verification; `ResolutionRow`'s eighteen columns are
all per-*row*; `EnrichmentResult` holds `clin_sig_not_checked`, `ref_mismatches`, `stale_rsids` and
`vrs` and dies with the run. Two such modules ship identical manifests not because some path drops the
information but because **no field exists that could differ** — and your framing of it as S4's own
argument one layer down is exactly right, which is why the item is written that way.

**Legality is not the obstacle and it is cheaper than you assumed**: the manifest was never inside
`artifact.digest` at all, and a new optional field is minor-legal since the 2026-08-11 charter
amendment, so this is 0.6 rather than anything major. A manifest field stamped by a publishing
authority is also already this schema's shape — `compiled_by`, `namespace`, `owner`, `published_at`,
`canonical_id` — so "let the party that ran the checks fill it" needs no new precedent.

**Where we are not simply taking the patch, and it is not the part you'd expect.** Not the fields — two
maps rather than one union-valued map is right for our own stated reasons, and counts-not-bools is the
`vrs_alleles` pattern. It is that **both halves of `dict[str, X]` are unversioned interfaces as
proposed.** Free-string check names let this tier write `clin_sig` and yours write `clinsig`, and free
prose in `checks_skipped` puts your backfill triage back to matching substrings — which is S13's defect
one level down, arriving inside its own fix. So the keys and the skip reasons both need closed
vocabularies (P6), and vocabulary members are permanent within a major (P5), so that set gets audited
once against the passes that would plausibly join it rather than grown per release. `clin_sig_not_checked`'s
sentence survives *beside* the token, not as it.

The other open half is the one you named: `resolution.csv` carries per-row facts and "a pass did not
run" has no row to attach to, so the seam genuinely has no channel and choosing one (a signed sidecar
the compiler reads, versus an argument on `compile_module`) is the design. We lean to your option **2**,
a `Verification` block, for your own reason — it wants the verified-against release id, which no
existing block has a home for, and `Frequency` is the precedent for a block with its own producer and
release. And your caveat is adopted as a requirement, not a footnote: it lands under `compiled_by`'s
existing rule, whose description already says foreign values are untrusted.

**One correction, and it is why the item is separate from S13's.** RM44 is *not* subsumed by this.
`resolution_subjects` is the denominator of a flag about **resolution**, and resolution is not a
verification pass; folding a row count into a map of which checks ran would overload that map (P5).
Treating S8 as the superset would have parked a one-line additive integer behind this whole design
round — so RM44 ships on its own, and RM45 records the three-way split (RM44's denominator, RM43's
unjoinable-row count, and this record) so neither of us designs one shape for three questions.
<!-- triaged: 0.5.4 · sha 52dd2f4f3b63 -->

**The friction.** 0.5.2's S4 fix is the right one and we adopted it: `EnrichmentResult` now carries
`clin_sig_not_checked`, so an empty `clin_sig_conflicts` no longer means both "compared everything,
nothing disagreed" and "never compared". But the distinction **stops at the enricher's return value.**
It reaches the publisher and then evaporates:

| who | can tell verified from unchecked? |
|---|---|
| the enricher's caller, in-process | **yes** — `clin_sig_not_checked` |
| the publisher, at publish time | yes, if the server says so (we now do) |
| the compiler | **partly** — see below |
| **the manifest** | **no — nothing is recorded** |
| **anyone downloading the module, ever** | **no** |

So the rule 0.5.2 established one layer up is unenforceable at the layer that outlives the run. A
module whose authored `clin_sig` was cross-checked against ClinVar and a module where the check never
ran ship **identical** manifests. Same for the reference-allele check and the rsID currency check.

**The seam carries row facts but has no channel for pass status**, which is the precise shape of the
gap. `resolution.csv` is the enricher→compiler contract, and it does carry per-row findings — a stale
rsID lands on `rsid_status` / `rsid_current`, so that one *is* visible downstream. What it has no place
for is a statement about a **pass**: whether the `clin_sig` check ran at all, whether the ref-allele
check ran, or why one didn't. `clin_sig` conflicts are not in the table on any row (there is nowhere to
put a comparison against an authored value), and "did not run" is per-pass by nature — it is exactly
the thing that has no row to attach to. That asymmetry is why `rsid_status` exists and
`clin_sig_not_checked` cannot follow the same route.

**Why this is S4's own argument, one level down.** `Compilation` already draws exactly this
distinction for resolution, and says so in a comment: `resolution_mode` is what was *requested*,
`fully_resolved` is what was *achieved* ("policy vs outcome are orthogonal axes"), and both VRS counts
at `0` means "nothing was attempted, which is not the same as nothing achieved". That is the same
sentence as S4's. The verification passes are the one part of the network tier that inherited none of
it — the manifest is rich about resolution and silent about verification.

**Why it matters to us specifically.** The registry's whole value proposition is that a *trusted party*
ran the gate: `compile_success` is meaningful only because `compiled_by == "marketplace-server"`. We
can say "this server verified this module's `clin_sig` against ClinVar release X" at publish time, and
then we have nowhere to put it. Concretely, three things we cannot build:

- A **catalog badge** — "clin_sig verified" vs "not verified on this deployment" is exactly the kind of
  quality signal the store surface exists for, and it is per-version and immutable, so the manifest is
  where it belongs.
- **Backfill triage.** Once an operator provisions a ClinVar snapshot, which already-published
  versions were published *without* the check and are worth re-checking? Today: unknowable, so the
  answer is all of them or none.
- **Honest degradation.** A deployment with no snapshot publishes for months, and nothing in the
  corpus records that a check was skipped rather than passed.

Note we can already say it *ephemerally* and have just fixed our half of that (the reason now rides on
the dry run as a token and on the publish path as prose; we also had a gap where a **successful**
publish dropped the findings entirely, which was ours and is on our roadmap). Neither reaches a
downloader, because both are response bodies.

**Suggestion.** Additive, out-of-digest, and — the reason this is cheap — **it needs no compiler work
at all.** The registry already post-stamps registry-owned manifest fields on publish (`namespace`,
`owner`, `published_at`, `canonical_id`), and it is the party that holds both the `EnrichmentResult`
and the manifest. So the ask is to *declare the shape* and let the caller that ran the checks fill it.
Cheapest first:

1. **Fields on `Compilation`, beside the resolution ones.** The pattern is already there in
   `resolution_sources: list[str]`:

   ```
   checks_run:     dict[str, int]   # check name → rows it actually put the question to
   checks_skipped: dict[str, str]   # check name → why it did not run, verbatim from that tier
   ```

   Absent on every existing manifest, which reads correctly as "this module says nothing", not as a
   pass. Counts rather than a bool or a bare name list, on the ACMG pass's own precedent (`checked: 0`,
   never zero mismatches): a check that ran against an empty list is neither a pass nor a skip, and a
   bool — or membership in a `list[str]` — cannot say so. Two fields rather than one map with a union
   value type, so "ran, 0 rows" and "did not run" can never collide in the same slot.

2. **A `Verification` block**, if `Compilation` should not keep growing — `Frequency` got its own block
   on the same reasoning (its own producer, its own release, its own fact-hash), and verification has
   its own release too: a `clin_sig` check is only as good as the ClinVar snapshot it read, so the
   block would want that release id, which is a fact none of the current blocks has a home for. 0.5.2
   is what makes this newly answerable, incidentally — `locations.read_release` is the first reader of
   the `release.json` every builder was already writing, so "verified against ClinVar release X" is a
   sentence the tier can now actually complete.

3. **Document the silence**, if neither is wanted: one line saying the manifest records no verification
   state, so nobody builds a trust signal on the absence of a finding.

**One caveat we would rather raise than have designed around us.** These fields are only worth
anything when the party that stamped them is trusted — a foreign `checks_run: ["clin_sig"]` is *worse
than silence*, because silence is honest and a forged pass is not. Whatever the shape, it should live
under the same `compiled_by` trust rule as `compile_success`, and the docs should say plainly that an
untrusted stamp is to be ignored rather than believed. We are content to be the only party that fills
it in.


# Field notes from the registry — adopting 0.5.3

*Written 2026-08-11, wiring the positional-joinability warning into the catalog's trust facet.*

## S13 — `fully_resolved` is scoped to `variants.csv` but reads as a verdict about the module, and the only durable record of the difference is a warning string

**Status — confirmed from this side and filed as
[RM44](ROADMAP.md#rm44--fully_resolved-answers-a-question-nobody-asked-it-and-prose-is-the-only-record-of-the-real-one),
targeted at 0.6; suggestion (1) is the accepted shape.** Reproduced end to end: the phrase
`have no chrom+start` reaches `manifest.compilation.warnings` in `manifest.json` verbatim for both
modules named below and is absent for a module whose core resolves, so the marker match is sound and
`trusted: true` really was being granted on an empty quantifier. Two things done immediately, without
waiting for the field: the fragment is now `compiler.UNJOINABLE_PHRASE` rather than an inline literal,
and a test pins it in both places it must hold — emitted verbatim, and present in
`manifest.compilation.warnings` — so a reword breaks this build rather than your catalog. **The rest of
that sentence is still free to improve**; that fragment is not, until RM44 gives you a field to read
instead. And the ask not to make `fully_resolved` tri-state is accepted and recorded in the item. <!-- triaged: backfilled · sha 49b41e5bcf94 -->

**Not a new fact — a new consequence.** S9 already records that `manifest.fully_resolved` is vacuously
`true` for a table-only module, "against the trust rule its own field comment states", and RM43 tracks
it. This is the report from the far end of that: it reached production, and the workaround we had to
ship is worse than the bug.

**What happened.** The registry projects a `trusted` facet per version, on the rule the field comments
document: `resolution_mode == "strict" or fully_resolved`. `fully_resolved` is `all()` over
`variants.csv`, so for a module without one it is `all()` over an empty list. The disjunction was
therefore granting trust on an empty quantifier, and the catalog served — under a badge that means
"fully baked" — modules that join to no VCF and annotate nothing. On your own reference examples:

| module | shape | what the catalog said |
|---|---|---|
| `pgx_slco1b1_simvastatin` | 9 of 9 `pharm_variants.csv` rows, no `chrom`/`start` | `trusted: true` |
| `cyp2c19_star_alleles` | 106 of 106 `haplotypes.csv` rows, a `start` and **no `chrom` column at all** | `trusted: true` |

Fixed in registry 0.11.3, including a migration — the manifests were always correct and immutable, so
only our *reading* of them was wrong, but the stored projection had to be repaired in place.

**The part worth your attention is the fix, not the bug.** There is no structured field that says a
table joins to nothing, so the only record that survives into the catalog is the 0.5.3 warning's
*prose*. Our trust facet now contains, in shipped code:

```python
UNJOINABLE_MARKER = "have no chrom+start"   # db/facets.py
```

matched as a substring against `manifest.compilation.warnings`, because at reindex time the manifest
is all we have — the spec directory is long gone. **A reword of that sentence silently re-grants trust
to modules that join to nothing.** We have pinned it with a test that compiles a real spec through the
real compiler, so it breaks our build rather than our catalog, and the miss direction is "cannot say"
rather than "trusted". It is still a string match deciding a trust badge, and we would rather not be
the reason that sentence can never be improved.

**Suggestion.** Cheaper than S8's `checks_run`/`checks_skipped` (which subsumes it), and cheapest
first:

1. **One additive integer on `Compilation`: how many rows resolution was actually applied to.**
   Something like `resolution_subjects: int = 0`. Then `fully_resolved=True` alongside
   `resolution_subjects=0` is *self-evidently* vacuous to any consumer, with no prose anywhere and no
   new vocabulary — it is the same "keep the parts, compute the convenience" pattern as
   `vrs_alleles`/`vrs_alleles_identified`, whose comment already makes exactly this argument ("Both `0`
   means no resolution table was present, i.e. nothing was attempted, which is not the same as nothing
   achieved"). That reasoning was applied to VRS coverage and not to the flag beside it.
2. **S8's structured check record**, which answers this and the `clin_sig` case together.
3. **Document the scope**, if neither is wanted: one line on `fully_resolved` saying it quantifies over
   `variants.csv` only and is not a module-level verdict. That at least means the next consumer reads
   it correctly the first time instead of after a migration.

**What we are explicitly *not* asking for.** Do not make `fully_resolved` tri-state or `None`-able. It
is typed `bool` and consumers branch on it directly; changing that is a breaking read for everyone to
fix a case an additive sibling field describes better. The flag is not wrong — it answers its question
correctly. It just cannot say which question it answered.

Worth noting this got cheaper while we were writing it: the 2026-08-11 charter amendment makes a new
optional column minor-legal, and a manifest field was never in `artifact.digest` to begin with, so (1)
is additive, digest-neutral and needs no major.

### S9 — answered in 0.5.3 (legibility shipped; the fix is RM43)

Adopted in just-dna-lite on 2026-08-11 along with registry 0.11.3. Recording the consumer-side
outcome so this entry does not read as still open.

`_check_positional_joinability` says exactly the right thing on our module, and the second count is
the half that makes it actionable:

> pharm_variants.csv: 1482 of 1482 row(s) have no chrom+start, so this table joins by rsID only — a
> VCF whose ID column is empty matches none of them. resolution.csv can place 1482 of them, and the
> compiler applies that table to variants.csv only.

Digest-neutrality holds on our modules too, not only on `reference_examples/`: recompiling
`pharmgkb`, `coronary` and `vo2max` against 0.5.3 reproduces `artifact.digest` byte-identically, so
nothing republishes on account of the bump.

Two notes on where the finding leaves us, neither a request:

**The warning does not remove the consumer-side workaround, and we did not expect it to.** We detect
the null-coordinate case at annotation time and downgrade the join to rsid + genotype, because the
alternative is annotating nothing at all. That stays until RM43 materializes the coordinate. We
mention it only so the constraint is visible from your side: for us the practical limit is not the
missing warning but that a VCF without rsIDs in `ID` — DeepVariant output among them — matches such a
module on nothing.

**The registry's three-valued `trusted` is the right call and lands where it should.** Our `pharmgkb`
will publish as `trusted: false`, which is accurate: the module is real and the rows are correct, and
a consumer joining by position gets nothing from it. We would rather ship it labelled honestly than
have the facet round up. Worth flagging only that the verdict keys off warning prose, which 0.11.3's
own commit message already calls out — a reword upstream silently re-grants trust, and their test
compiling a real spec is the thing standing between that and a quiet regression.

## S14 — `resolve_with_ensembl=False` reads as "skip Ensembl" and is the master switch for all resolution, including an injected `resolution.csv`

**Status — suggestion (1) had already shipped in 0.5.2, from a different report, before this one was
filed; the row count you specified is added in this pass. (2) is refused with a reason and (3) stands
as major-only. Nothing filed.** Your lateness cost nothing — someone else hit the same flag a day
earlier, so the warning was already there; what was missing was the *N* your wording included, which is
the part that makes it actionable. It now reads `… ({N} row(s), covering {K} variant key(s)), which was
not read …` — rows rather than keys, because a one-to-many rsid makes those different numbers and the
reader wants the first. Pinned by a test that counts its own fixture and asserts the two numbers differ,
so the distinction cannot quietly collapse.

**(2) is not merely unnecessary for the compiler, it would assert something false about it.** Read the
branches: with a `resolution.csv` the compiler reads the table; with the deprecated `ensembl_cache` it
routes an **injected local cache** to the enricher's resolver; with neither it warns and leaves rows
unresolved. There is **no branch that reaches the network** — that is Principle 2, and since 0.5 it is
tighter than it was, not looser. So "do not reach the network, use the injected table" is not a mode of
this tool, it is the only thing this tool does, and a `--no-ensembl` flag would be a permanent no-op
whose existence implies the compiler might otherwise fetch. The request is spelled by passing no flag at
all, and the warning now says exactly that in its last sentence. Your guess about `--offline` is the
right instinct pointed at the wrong tier: it is an **enricher** flag, because the enricher is the only
tier with egress to switch off.

**(3) is still major-only, and the charter amendment does not reach it.** The 2026-08-11 amendment made
a new *optional column or table* minor-legal; renaming a parameter in a published signature removes a
name, and removal is major-only under P3 whatever the thing is. Worth noting what *would* be legal, in
case you want it: **adding** a differently-named alias while keeping `resolve_with_ensembl` is additive
and needs no major (P3 keeps a superseded name as a working alias). We are not doing it, because the
only honest alias is `--no-resolution`, which buys a better name at the cost of two flags meaning one
thing — and (1) removes the failure mode that made the name expensive.

Your consumer-side pin (`resolve_with_ensembl=True`, `ensembl_cache=None`) is now belt-and-braces rather
than load-bearing; keeping it costs nothing, but an agent that reaches the flag through the CLI is told
what it just did.
<!-- triaged: 0.5.4 · sha 43031f8f63b3 -->

*Filed 2026-08-11. Late: we found this while building the wrapper, guarded against it on our side, and
described the guard in our own README instead of telling you. That was the wrong order — the guard
only protects our callers, and the flag is still there for everyone else.*

**The friction is the name.** `compile_module(resolve_with_ensembl=False)` / `--no-resolve` reads as
"do not go out to Ensembl" — which is a reasonable thing for an author to want, and the obvious thing
to reach for when working offline or from a committed `resolution.csv`. What it actually does is
switch off resolution **entirely**, including the injected table sitting beside the spec. Every row
compiles with `chrom`/`start` null, and the compile **succeeds**.

So the failure has all three properties that make one expensive:

- **The flag's name describes a narrower action than it performs.** Nothing in
  `resolve_with_ensembl` suggests "and also ignore the resolution table you committed".
- **The wrong thing looks like the careful thing.** An author who has read that the compiler is
  inject-only, and who wants a hermetic build, will reach for exactly this flag.
- **It exits zero.** No error, no warning, and a module that annotates nothing.

**Why we think it is worth a change rather than a doc line.** The 0.5.3 positional-joinability warning
(S9) covers the adjacent case, and its reasoning applies here more strongly: an author who ends up
with a coordinate-less module cannot otherwise tell *why*. With `--no-resolve` the diagnosis is
available for free at the same moment — the run knows the flag was passed and knows a
`resolution.csv` was present and unread.

Options, cheapest first, none digest-moving:

1. **Warn when the flag is passed and a `resolution.csv` exists.** "resolution disabled by
   `--no-resolve`; the `resolution.csv` beside this spec (N rows) was not read." One line, and it
   converts a silent wrong answer into an obvious one. This is the same shape as the joinability
   warning and would slot beside it.
2. **Split the flag.** `--no-ensembl` for "do not reach the network, use the injected table" — which
   is what the current name promises and, we suspect, what most callers who pass it actually want —
   and leave `--no-resolve` meaning what it means today. `--offline` may already cover the first
   intent, in which case the ask reduces to (1) plus a note that `--offline` is the flag an author
   reaching for `--no-resolve` probably wanted.
3. **Rename it** to something that says what it does (`--no-resolution`, `--skip-resolution`). Not our
   preference: it is a breaking CLI change for the benefit of a name, and (1) delivers most of the
   value.

**What we did, and why it does not close this.** `compile_module` in our MCP surface pins
`resolve_with_ensembl=True` with `ensembl_cache=None`, so an agent driving our tool cannot reach the
branch at all, and our authoring docs say plainly never to pass it. That protects our callers and
nobody else's — the CLI still offers it, and the next consumer to reach for the obvious-looking flag
gets a green build and an empty module. Filing it so the fix can live where the flag does.


# Field notes from just-module-creator — the literature tier, 2026-08-11

Found while building literature *discovery* on the app surface (search is ours, not yours — these
three are defects in the verification tier you own, not requests for features we should be writing
ourselves).

## S10 — `enrich_literature` introduces a source whose terms nothing can record, and the terms are per-article anyway

**Status — accepted and filed as [RM46](ROADMAP.md#rm46--a-literature-sources-terms-are-per-article-so-the-enricher-names-a-source-it-cannot-record), 0.6; your per-article analysis is the reason it is not a one-line constant.**
Reproduced by reading the three pieces together: `enrich_literature` writes `source="pubmed"` on every
row, `TERMS_BY_SOURCE` has seven members and no `pubmed`, and `record_source_terms` deliberately skips a
name it has no terms for — so the tier introduces a source and declines to record it, and the finding
lands on the author. One bound worth knowing while it is open: `SourceRow.source` is **free text**, so
you or an author *can* hand-write the `pubmed` row and the warning clears. It is not unclearable — it is
the enricher asking someone else to write down what only the enricher knows.

**Your reason for not wanting `PUBMED_TERMS` is the finding, and it is recorded as such.** A single row
would be right for a citations-only module and wrong for one carrying a `provenance_quote` from a
CC-BY-NC article — wrong in the dangerous direction, since that quote is publisher text in the module's
own **annotation** layer, which is precisely where `taints_commercial_use` bites. A row reading "pubmed,
fine" would make such a module look *cleared*, which is worse than the warning you are getting now. That
is why the interim half-step is written into the item with a condition attached rather than shipped.

**Two repairs the item rules out, one of them yours by implication.** Dropping `source="pubmed"` is no
good: it is how a consumer knows which upstream answered, and the existing reason to prefer PubMed over
Europe PMC (which cannot originate a row, since it silently omits ids it does not know) still holds. And
the compiler cannot exempt enricher-introduced sources, because it would need a list of which sources a
pass introduces — a **source convention**, forbidden it since 0.5 and the exact thing RM33 removed. You
reached the same conclusion from the other side, and you were right to leave `sources.csv` alone: a terms
table in a consumer is the un-injected reference, and we are not asking you to carry one.

**Where it goes.** Per-article terms need one decision that is not the literature pass's to make alone —
whether quoting a CC-BY-NC article taints the module for sale — and that is the *use*-versus-*distribution*
axis **RM27** already parks, so the two are marked for settling together. The tier is closer than it
looks: `is_open_access` is already tri-state on the row, and the pass holds the licence at the moment it
would record it.
<!-- triaged: 0.5.4 · sha f1c69a10c377 -->

**What happens.** `enrich_literature` writes `source="pubmed"` into every `literature.csv` row.
`_source_checks` builds `used_sources` from the `source` column of every fact table. `TERMS_BY_SOURCE`
has no `pubmed`. So every literature-enriched module warns:

> `sources.csv has no row for 1 source(s) the module's fact tables cite: ['pubmed'] — their terms are unrecorded.`

It is a warning, never an error, so it ships unnoticed — and the source it names was introduced by the
enricher itself, not by anything the author did. `VALID_SOURCE_LAYERS` already reserves `literature`,
so the row has somewhere to go.

**Why we are not just asking for a `PUBMED_TERMS` constant.** That would be wrong, and this is the
part we think is worth your time: **a literature source's terms are per-article, not per-source.**
PubMed's *metadata* is a US-government work; the *article* belongs to its publisher, and Europe PMC's
OA subset spans CC-BY, CC-BY-NC and bronze. A single `pubmed` row in `TERMS_BY_SOURCE` would be
right for a module that only cites PMIDs and **wrong** for any module carrying a `provenance_quote`
lifted from a CC-BY-NC article — because that quote is publisher text sitting in the module's own
annotation layer, where `taints_commercial_use` actually bites.

So the question is about `SourceRow` granularity, not a missing entry. Two shapes we can see, no
preference between them:

1. A `pubmed` row at `layer="literature"` covering the *metadata* only, plus a documented rule that
   quoting an article requires a second row at `layer="annotation"` carrying that article's licence.
   Cheap; puts the burden on the author but at least makes the obligation nameable.
2. Per-article terms keyed off `literature.csv` — the OA licence is already retrievable (Europe PMC
   returns `isOpenAccess`, and Unpaywall returns the licence id per DOI), so the pass that writes
   `literature.csv` is holding the fact at the moment it would need it.

We are not writing a terms table on our side. `licensing.py` says the enricher is the only tier
permitted to hold a source convention, and we agree — a terms table in a consumer is exactly the
un-injected reference 0.5 removed. We report the gap to the author and leave `sources.csv` alone.

## S11 — `provenance_quote` and `provenance_regex` are redundancy-bearing and the map does not say so

**Status — accepted and fixed in this pass, including the sharper refusal you argued for and the
consequence you said nothing states.** Confirmed: the map had eleven columns and
`_study_quote_found` compares both provenance cells against the Europe PMC fulltext to produce
`quotes_found`, so they qualify under the map's own definition — the drift its docstring predicts
("a new check that forgets to register lands here rather than silently becoming fillable"), arriving
exactly as predicted.

Both are now registered in `REDUNDANCY_BEARING`, and you were right that this is not a one-line
addition: the failures differ in kind, so there is a **fifth** refusal reason,
`attestation_bearing`, with `hints.ATTESTATION_BEARING` naming the cells. Filling `doi` from the
registry that checks it makes a comparison **vacuous**, which is what every other entry on that map is;
filling `provenance_quote` from a fulltext a tool just fetched is a **false claim of provenance**, and no
lookup can make it true. The registration is *additional*, not instead — a provider consulting either map
reaches a refusal, which is what you asked for when you said you would rather the refusal be ours.

**Your docs consequence is now written down**, in ENRICHER.md § the literature pack, in your terms:
`quotes_found` is independent evidence only while the author and the pass read the article separately;
once a machine has retrieved the text, a hit shows the quote **pairs with the PMID** — still worth having,
since it catches a passage filed against the wrong paper — but no longer that the claim is in the article,
because nothing establishes a human ever looked.

Pinned by two tests, one of which is a guard rather than an example: every column the map names must exist
on an authored model, `ATTESTATION_BEARING` must be a subset of `REDUNDANCY_BEARING`, and an authored quote
must survive `inspect_rows` unaltered. So a future provider that tries to fill one has to decide the
refusal instead of inheriting silence.
<!-- triaged: 0.5.4 · sha d9347bd3c827 -->

`hints.REDUNDANCY_BEARING` lists eleven columns with the check each one feeds. It omits
`provenance_quote` and `provenance_regex`, yet `enrich_literature._study_quote_found` compares both
against the Europe PMC fulltext to produce `quotes_found`. By the map's own definition — "a check
compares the authored value against a source" — they qualify.

**They also want a different refusal token from the rest, which is why this is not a one-line
addition.** For `doi` or `clin_sig` the rule is "do not fill this from the source that checks it".
For a provenance quote the author is *supposed* to have read the source — that is the entire point of
the column. What must not happen is a **machine** reading it: a passage extracted from a fulltext a
tool just fetched asserts a curator reading that never occurred. That is a false claim of provenance,
not merely a vacuous check, and it is a sharper failure than any other entry on the list.

Consequence worth stating in the docs either way, because it is true today and nothing says it: once
a fulltext has been retrieved programmatically, `quotes_found` on that row is no longer independent
evidence. It degrades to a citation-pairing check — still useful, since it catches a quote written
against the wrong PMID, but no longer evidence that the claim is in the paper.

Our tools refuse to extract passages at all and say why. We would rather that refusal be yours, since
`REDUNDANCY_BEARING` is what every consumer reads to find out which cells are theirs to author.

## S12 — `lookup_citation` cannot detect a fabricated PMID, because `CitationHint` carries no title

**Status — accepted and shipped in this pass; you were right that it was surfacing fields we already
had.** Confirmed: `_identifiers` reads `doi` and `pmcid` out of the `articleids` block and drops the
rest of the record. `CitationHint` now carries **`title`, `journal`, `year` and `first_author`**, filled
from the same `esummary` response that answers existence, so it costs no extra request and works for
paywalled work exactly as `exists` does.

Three details beyond the ask. `literature.bibliographic()` is **public**, unlike `_identifiers` beside it,
because two tiers read it and the alternative is a consumer re-parsing a payload we hold — the RM41
lesson. Every value is `None` when the record does not carry it, never an empty string, and `year` is the
leading four digits of the free-form `pubdate` (`2017 Nov 20` → `2017`), so nothing is invented when it
does not start with one. And the answer says the thing your skill had to retract, as an `info` finding
next to the fields: *"PMID … names: '…' (author, journal, year) — existence is not identity, so confirm
this is the paper you meant."* A caller who recalled a number from memory is more likely to be reading
prose than JSON.

**`hint citation --json` did not exist**, which your note assumed — `hint variant` has the flag and this
command never got it. It does now, carrying all four fields, and the bibliographic lines print in the
plain output too. The command's docstring leads with the distinction rather than with existence.

The test earns its keep by demonstrating the failure rather than describing it: two real-shaped esummary
records, the paper meant and a PMID one digit away, both `pmid_exists=True` — so existence provably cannot
separate them and the title provably can. It uses the actual field names (`fulljournalname`, `pubdate`,
`sortfirstauthor`), since a parse against invented keys would pass a test and fail against PubMed.

**One thing deliberately not done:** no title column on `LiteratureRow`. It would be additive and legal,
but a stored title is a fact that can drift from its source, and `literature.csv` exists to record what
was *checked*, not to cache bibliography. If you want titles in the artifact, that is a separate ask and
worth filing as one.
<!-- triaged: 0.5.4 · sha 3cc1b2e4a6e7 -->

`CitationHint` carries `pmid_exists`, `doi`, `registry_doi`, `pmcid`, `open_access`,
`abstract_available`. It carries no **title**, journal or year.

PMIDs are densely allocated across roughly 1–40,000,000, so a recalled or hallucinated 8-digit number
is almost always a real record — for a different paper. `lookup_citation` answers `pmid_exists=true`
and the caller has learned nothing about whether the citation is the right one. Fabrication is a
failure of *identity*, and the only field that could catch it is absent.

This matters because the surrounding docs treat existence as the guard. Our own skill said "never
invent a PMID — verify each one with `lookup_citation` before writing it", which we have now had to
correct: it is a rule our surface could not enforce.

`esummary` already returns `title`, `fulljournalname`, `pubdate` and `sortfirstauthor` in the payload
`_check_pmid` parses — `literature._identifiers(record)` reads that same record for the DOI and PMCID
and drops the rest. So this looks like surfacing fields you already have, not a new request.

Suggestion: add `title` (and ideally journal + year) to `CitationHint` and to `hint citation --json`,
so "does this PMID exist" can become "does this PMID name the paper you meant". If there is a reason
to keep the hint minimal, a `--verbose` flag would do — the important part is that the answer be
reachable at all, since today no upstream surface returns it.

We are solving our own half by searching (a search result carries a title, so the PMID never has to
be recalled). That does not help anyone using `hint citation` or the enricher directly.

---

# Documentation gaps — facts we had to establish by experiment, 2026-08-11

*A different category from the entries above: nothing here is misbehaving. These are
things a consumer has to **probe** because the docs do not say, and each one we
guessed wrong about at least once. Filed together because the fix is the same shape
— a sentence in the right place — and because a fact discovered by experiment is a
fact the next consumer will also discover by experiment.*

## S15 — `PacingGate`'s concurrency contract is unstated, and it is not safe to share

**Status — accepted; option (1) shipped in this pass, so you can delete `ServiceGate`.** Confirmed by
reading `wait()`: it read `last`, slept, then wrote it, with no lock. The decisive argument is the one you
make — the injection API *asks* for sharing. `LookupClients`' own docstring tells callers to hold a client
and reuse it, because a fresh one per question would discard exactly this state, so a server running
blocking work through a thread pool arrives at a shared gate by following our documentation. A budget
someone else enforces by blocking the operator's IP is not a good place for an unstated
single-threaded-only contract, and "document it" would have left every threaded consumer to rediscover
the wrapper you had to write.

**One difference from your `ServiceGate`, and it is deliberate: the lock covers the bookkeeping, not the
sleep.** Each caller reserves the next free slot (`now`, or one interval after the last claim) and then
waits for that slot alone. N callers therefore get N slots spaced one interval apart — the same budget
guarantee as a lock held across the sleep — without any worker blocking on another's wait. If the
property you actually wanted is *one in-flight request per service*, that is a different requirement (a
concurrency limit, not a pace) and a semaphore around the call site is the honest way to say it; the gate
should not conflate the two axes.

Single-threaded behaviour is unchanged, and the test earns its keep by demonstrating the failure rather
than asserting the fix: four threads meet at a barrier inside `wait()` with the clock frozen, and the
slots they are cleared for must be spaced by the interval. Run against the old implementation the gaps
come out `[6.0, 0.0, 0.0]` — three of four callers cleared at the same instant, which is precisely your
3/s becoming 12/s. `ENRICHER.md`'s rate-limit section now states the sharing contract instead of leaving
it to be inferred from nine mentions.
<!-- triaged: 0.5.4 · sha 8d339211894b -->

`ENRICHER.md` documents `PacingGate` as the pacing mechanism in nine places and
never says whether one instance may be shared across threads. It may not:
`wait()` reads `self.last`, sleeps, then writes it, with no lock. Two threads can
both observe the interval as elapsed, both skip the sleep, and a published 3/s
budget becomes 6/s.

**This is correct for the CLI and a trap for anything else.** Upstream's own callers
are single-threaded, so it has never bitten there. Every tool in our MCP server runs
its blocking work through `anyio.to_thread.run_sync`, which is the ordinary way to
keep a server responsive — so several workers sharing the injected `LookupClients`
(which `LookupClients`' own docstring *tells* callers to hold and reuse) is not an
exotic arrangement, it is the arrangement the injection API invites.

Demonstrated rather than argued: with a clock frozen so the interval provably has
not elapsed, four threads entering `wait()` on one `PacingGate` overlap inside the
sleep; on a lock-wrapped subclass, never more than one is inside at a time.

The ask is a decision plus a sentence, in either direction:

1. **Lock it**, and document that a gate is shareable. Three lines, and it makes the
   injection API safe by default for the server shape 0.5 created.
2. **Document that it is not**, and say a gate belongs to one thread — at which
   point a threaded consumer knows to wrap it and, more importantly, knows that
   sharing one `LookupClients` across workers needs care.

We shipped (1) as a local `ServiceGate` subclass that adds a lock and nothing else,
which also gives us the property we actually wanted from a courtesy budget: one
in-flight request per service at a time. We would rather not be carrying it.

## S16 — whether a spec directory may contain files the compiler does not know is unspecified

**Status — accepted: the behaviour you observed is now a stated contract, and probing it turned up one
case where "ignored" is the wrong answer.** Reproduced on a real spec (`hfe_hemochromatosis` plus a
`published.json`, a `README.md` and one more file): `validate_spec` and `compile_module` say nothing,
`artifact.files` is unchanged, and the digest is byte-identical. [COMPILER.md](COMPILER.md) now states it
where the pipeline is described — unknown files are not read, not hashed, and not in `artifact.files`, so
they cannot move `artifact.digest` — and a test compiles the same spec with and without two unknown files
and compares digests, so the guarantee you are relying on breaks our build if it ever stops holding. Your
`published.json` receipt is safe, and the reasoning is sound: those keys cannot go in `module_spec.yaml`
precisely because the registry owns them (S1), so a sibling file is the right place.

**The third file in that probe was `varaints.csv`, and it is why this is not purely a doc fix.** A
mistyped table name is silently not a table: every row in it is dropped and the compile is green, which is
the silent-success shape this codebase treats as the worst kind of mistake. `validate_spec` now warns when
an unknown `.csv` is within one small edit of a known table name, naming the likely intended file and
saying the rows are being ignored. It is keyed on **near miss** rather than on "any unknown csv" on
purpose — warning about every unrecognised file would undo the tolerance you are relying on — and a test
pins both directions, so `curation_notes.csv` stays silent while `varaints.csv` does not.

**On the reserved prefix:** not taken, and worth saying why rather than leaving it open. It would buy the
option of rejecting unknown names later, but the tolerance is now a *documented* contract with a test
behind it, so that option is one we have deliberately given up — and a prefix convention only helps files
written after it exists, which is not the corpus that would break.
<!-- triaged: 0.5.4 · sha 665524d2394b -->

`COMPILER.md` enumerates what a spec directory contains and never says what happens
to anything else in it. Both answers are defensible — strict rejection would catch a
typo'd filename, tolerance lets a module carry its own README — so a consumer cannot
infer it and has to test.

We tested: `validate_spec` and `compile_module` ignore an unknown file completely —
no error, no warning, and the digest is unaffected because it is a Merkle root over
`artifact.files` and an unknown file is not one of them.

We are relying on that. `registry_publish` now writes a `published.json` receipt
beside the spec, recording the identity the registry stamps (`namespace`, `owner`,
`version`, `canonical_id`) so it survives the session — those keys cannot go into
`module_spec.yaml`, where `extra="forbid"` rejects them precisely because the
registry owns them (`S1`). A sibling file was the only place left.

So the ask is just to make it a stated contract rather than an observed behaviour:
one line in `COMPILER.md` saying unknown files are ignored — or saying they are not,
in which case we need to know before more consumers put things there. A reserved
prefix would be an even better answer if you would rather keep the option of
rejecting unknown names later.

## S17 — `source` exists only on enricher-produced rows, so an authored table has nowhere to declare provenance

**Status — accepted; suggestions (1) and (2) both shipped in this pass. Your table is right, with one
addition worth knowing.** Verified by enumerating the models through the compiler's own table registries
rather than by hand: your "has it" column is exactly right, and there is a **fifth** — `SourceRow` itself.
That one is not an exception to your rule, it is the answer to your last paragraph: on `sources.csv` the
column is the *subject* of the row rather than provenance (which is also why it is inside that table's
fact set while being excluded everywhere else). So the sharper statement is that no **fact** table has a
`source` column, and the place to declare a hand-read source is a row in `sources.csv` — there is
something to fill, just not where you looked.

(1) is in [SCHEMAS.md](SCHEMAS.md) under `SourceRow`, naming all five, saying the four are exactly the
generated ones, and stating the consequence in your terms: because `used_sources` is built from those
columns, a source an author read by hand is invisible to the coverage check **structurally** rather than
through carelessness, so no amount of care in the fact table helps.

(2) is done and it is the part that would have saved you the trip through the models.
`vocab.MISPLACED_COLUMN_REASONS` + `reject_misplaced` give a `source` column on a model that does not
declare one its own diagnosis — where provenance is recorded, why an authored table has none, and to add
the `sources.csv` row instead — layered on `extra="forbid"` exactly as the reserved-name guard is. It keys
on **the model's own fields**, so `FrequencyRow` and the other three keep their column and cannot be
broken by the message that describes them; a test asserts both halves across every authored model. It is
deliberately *not* the reserved namespace: that set is for names no model has, held against a future
release, and `source` is a real column in the wrong place — a different failure that deserves a different
sentence.

**(3) is not taken, and it is not deferred either.** Per-row authored provenance is a design question, and
the honest answer is that the axis already has an owner: what a hand-read source needs recorded is its
*terms*, which is what `sources.csv` is, and the open work there is per-article granularity —
[RM46](ROADMAP.md#rm46--a-literature-sources-terms-are-per-article-so-the-enricher-names-a-source-it-cannot-record),
from your own S10. If a use case survives that, file it then; you were right not to ask for it now.
<!-- triaged: 0.5.4 · sha a58134120148 -->

The `sources.csv` gate reads `used_sources`, built from the `source` column of the
fact tables. Which tables actually have that column is not documented anywhere we
could find, and the answer is narrower than it reads:

| Has a `source` column | Does not |
|---|---|
| `ResolutionRow`, `FrequencyRow`, `GeneMetricsRow`, `LiteratureRow` | `VariantRow`, `StudyRow`, `PharmVariantRow`, `DiplotypeRow`, `HaplotypeRow`, `AlleleFunctionRow`, `ActivityPhenotypeRow`, `CopyNumberRow`, `RepeatAlleleRow`, `HeteroplasmyRow`, `MeasureBinRow`, `PgsRow` |

**All four that have it are enricher-produced sidecars. No hand-authored table has
one.** So the coverage check can only ever see sources a *pass* introduced, and a
source the author read by hand is structurally invisible to it — not merely
easy to forget.

This is the mechanism behind the advice everyone repeats ("a source you copied from
by hand is invisible to the gate, so add the `sources.csv` row yourself"), and
knowing it is structural rather than incidental changes what an author does: there
is no column to fill and no amount of care in the fact table will help.

How we found it, which is the part that argues for documenting it: we put a
`source` column on a one-row `pharm_variants.csv` — reasonably, we thought, since
the value joins to `sources.csv` — and got `line 2 [source]: Extra inputs are not
permitted`. A plausible column name, rejected, with the reason discoverable only by
reading the models.

Suggestions, cheapest first:

1. **State it in `SCHEMAS.md`**: which rows carry `source`, that they are exactly the
   generated ones, and the consequence for `used_sources`.
2. **Say it in the error.** `Extra inputs are not permitted` on a column named
   `source` is worth a specific message — "`source` is recorded on generated tables
   only; declare a hand-read source as a row in `sources.csv`" — since it is a name
   an author will reach for.
3. If authored provenance is meant to be expressible per row at some point, that is
   a design question and this note is the use case for it. We are not asking for it.


# Field notes from just-module-creator — `hints.inspect_rows`, 2026-08-11

*Filed during the same authoring-surface work as S10–S12, after this document's first triage pass had begun.*

## S18 — `inspect_rows` silently mis-parses a ragged row, then reports the resulting error against the wrong column and the wrong line

**Status — both accepted and fixed in this pass, your HTT fixture reproduced verbatim.** Defect 1: your
three-line table now reports `error: 8 field(s) where the header declares 7 — every column from the extra
one onward is shifted and the overflow is dropped … the usual cause is an unquoted comma in a free-text
column (conclusion, phenotype); quote the value ("a, b") or remove the comma.` It is emitted **before**
the per-row validation, deliberately: the misleading `unresolved` error is still there — nothing about the
parse changed — and an author who reads the type error first goes and edits a cell they wrote correctly.
Padding and truncating are kept, because a hint must describe a broken file rather than refuse it.

**The asymmetry you proposed is the one implemented**, and it has a reason worth stating: a surplus field
is an **error** because it shifts later columns *and discards the overflow*, so the row now asserts things
the author never wrote and `csv_out` carries the damage forward; a shortfall is a **warning**, because
padding is recoverable and usually a trailing comma. Both name both counts.

Defect 2 took your option **2** and your caution about it. `Finding` gains **`line`** — 1-based, header
included, the same coordinate `validate`/`compile` already print — and `row` keeps its meaning, now
documented as a 0-based index into the data rows. Not a quiet redefinition, exactly for the reason you
gave: a consumer already adding 1 would have started reporting line 4 for line 3 with no signal. Both are
useful and they answer different questions — `row` indexes `csv_out`, `line` is what the editor shows —
so both are stated on the dataclass rather than one being inferred. The compiler CLI now prints
`line N`, so the two error surfaces over one file finally agree.

Four tests, including one that caught a bug in **our** fix: a "the guard must be silent on every shipped
template" test fired on `variants.csv`, which turned out to be the test misusing `stub_template` (it
returns a string, so joining it split the header into characters) rather than the guard being noisy — but
that is the test we wanted, and it stays. The line-number tests assert `line == row + 2` with a header and
`line == 1` without one, so the header offset cannot silently drift.
<!-- triaged: 0.5.4 · sha bf05c1f7bf7f -->

Two defects in `hints.inspect_rows`. They are filed together because they land in the
same few lines and because an author hits them at the same moment: the one time you
most need to be told *where* the problem is, both coordinates are wrong.

### 1. A row with more fields than the header is accepted and silently shifted

`hints.py:268`:

```python
rows = [
    {name: (values[i] if i < len(values) else "") for i, name in enumerate(header)}
    for values in (next(csv.reader([line])) for line in body)
]
```

`len(values)` is never compared to `len(header)`. A row with an extra field has every
column from the offending one onward shifted left by one, and the surplus past
`len(header)` is dropped. A row with too *few* fields is padded with `""`, which is
indistinguishable from cells the author deliberately left empty.

The overwhelmingly common cause is an unquoted comma in prose — and `conclusion`,
`phenotype` and every free-text column invite exactly that. Real example, a
`repeat_alleles.csv` for HTT CAG bins:

```
gene,repeat_unit,measure_kind,measure_min,measure_max,conclusion,unresolved
HTT,CAG,repeat_count,,26,Normal range with no expanded allele.,false
HTT,CAG,repeat_count,27,35,Intermediate allele, may expand on paternal transmission.,false
```

Reported:

```
row 1, unresolved, error: Input should be a valid boolean, unable to interpret input
```

`unresolved` on that row reads `false`. It is a valid boolean, in the right column,
and the author is told it is not — because `conclusion` split in two, `unresolved`
received `" may expand on paternal transmission."`, and the real `false` was
discarded off the end. Nothing anywhere says the row had 8 fields where 7 were
declared. The diagnosis names a column the author got right and stays silent about
the one they got wrong.

It also corrupts quietly when the shifted value happens to be type-valid. In the
five-bin version of the same table the surplus landed such that `source_field` was
simply lost — `REPCN` on four rows and empty on the fifth, no error, no warning. The
returned `csv_out` carries the damage forward, so a caller writing it back to disk
persists it.

**Ask:** compare `len(values)` against `len(header)` in `_parse` and emit a finding —
`error` for too many, at least a `warning` for too few, naming both counts. It is a
two-line guard that turns an actively misleading message into a correct one. Worth
saying explicitly in the message that an unquoted comma in a free-text column is the
usual cause.

### 2. `Finding.row` is 0-based, and offset from the line the author is looking at

`inspect_rows` builds findings with `enumerate(rows)`, so the first data row is
`row 0`. Confirmed both ways on the table above: the error moves to `row 0` when the
malformed row is first, and `row 1` when it is second.

Every tool an author has open counts from 1, and their file has a header line, so the
row reported as `1` is line 3 of the CSV. There is nothing on `HintReport` saying which
convention `row` uses, and the mismatch is silent — on a two-row table an off-by-one
still lands on a real row, so it misdirects rather than obviously breaking.

This is also inconsistent within the ecosystem: `compile`/`validate` errors are
reported as `line 2 [source]: ...` — 1-based and line-numbered, counting the header
(that is the wording quoted in `S17`). Two error surfaces over the same file, two
conventions, neither stated.

**Ask, cheapest first:**

1. **Document it** — one line on `Finding.row` saying it is a 0-based index into the
   data rows, header excluded.
2. **Better: match the compiler.** Report the CSV line number, 1-based and
   header-inclusive, so `inspect_rows` and `validate_spec` name the same location the
   same way. This is a breaking change to the field's meaning, so it wants a rename
   (`line`) rather than a quiet redefinition — a consumer that already adds 1 would
   otherwise start reporting line 4 for line 3 with no signal.

Either is fine. Silence is the thing that costs, because the only way to learn the
convention is to author a broken row deliberately and count.

# Field notes from a module author — authoring a binning module, 2026-08-11

The first item filed after the inbox was emptied, and the first to arrive with no group heading of its
own: it was written directly under the live file's preamble, which the archiver then carried across.
Given a heading here rather than left under the inbox's own description, which introduces nothing.

## S19 — a binning table has nowhere to record its evidence, so the most interpretive claims in the format are the only ungrounded ones

**Status — accepted; suggestions (1) and (2) shipped in compiler 0.5.4, suggestion (3) filed as
[RM47](ROADMAP.md#rm47--a-bin-boundary-is-the-most-interpretive-claim-in-the-format-and-the-only-one-with-nowhere-to-cite) for 0.6.** Reproduced on our own reference example, which is the part that
settled it: `reference_examples/htt_repeat_expansion` compiles green under `--strict` asserting where
Huntington disease becomes fully penetrant, with no citation anywhere — and its README already said "a
module making a novel claim should carry its evidence", advice the schema gave no way to take. The
comment in `validate_spec` that justified the exemption was also wrong: it claimed "the 0.4 tables carry
their own evidence (e.g. `evidence_level`)", which is true of two of the nine kinds.

**Two corrections, and both narrow what you should do next.** `heteroplasmy.csv` is *not* in the same
position — it has carried optional `rsid`/`chrom`/`start`/`ref`/`alts` since 0.5.1, so a study row on
the same variant identity points at such a row exactly, and `reference_examples/mt_heteroplasmy` does
this today. And `studies.csv` is **not rejected** in a module with no `variants.csv`: it loads,
validates and compiles to `studies.parquet`. So you can ground the HTT module right now — the study row
just has to claim a variant identity the bin does not have (a bare `chrom=4`), which grounds the module
rather than the 36. That is worth doing and it is not what you asked for.

**What ships now (2).** `_check_binning_grounding` warns, in both modes, when a binning table states
thresholds and the module records no study rows at all — silence became a visible decision, with no
schema change. The message splits on whether the rows *could* be pointed at, derived from the model
rather than the table name: your `repeat_alleles.csv` is told that no study row can name one of these
bins, a gene-only heteroplasmy table is told to fill its identity columns instead. **And (1):**
`SCHEMAS.md` now states where grounding goes and where it cannot, `COMPILER.md` lists this apart from
the inescapable blind spots because it is a schema limit rather than a limit of the tier, and the HTT
README says so at the point an author reads it. You were right that `sources.csv` does not answer it —
it records a dataset's terms, not why a boundary is where it is.

**Why (3) is filed rather than built.** Your third option is the real fix and there are four versions of
it, none a one-liner: `pmid` on `MeasureBinRow` is the only one that grounds a *boundary*, but
`literature.csv`, `_cross_check_literature` and the enricher's literature pass all read `StudyRow.pmid`
and nothing else, so it would ship a citation nothing verifies — grounding that looks checked and is
not. A generic `subject_key` is the packed tuple the binning tables explicitly reject. Key columns plus a
new `REQUIRED_ANY_OF` alternative are legal but ground the table, not the bound, unless the study row
restates the bin's bounds. A `bin_evidence.csv` join table keys on the bounds themselves, which are
floats, so re-authoring `40` as `40.0` silently orphans its evidence. The decision is which granularity
the format promises — module, table, or boundary — and RM47 carries all four with their costs.

Your note about what you did meanwhile is the right call and we have copied it: the HTT thresholds in
our own example stay uncited deliberately, so the example keeps demonstrating the gap.
<!-- triaged: 0.5.4 · sha 0b5e9db9ecd9 -->

Authoring a `repeat_alleles.csv` for HTT CAG bins, we went looking for where to cite
the source of the thresholds and found there is no such place.

`studies.csv` is the grounding mechanism, and it is variant-shaped in both directions:

- its identity rule is `any_of: [[rsid], [chrom]]`, and a `repeat_alleles.csv` row is
  keyed `(gene, repeat_unit)` — it has no `rsid` and no `chrom`, so no study row can
  point at it;
- it is required **iff** `variants.csv` is present, and a binning module correctly
  carries no `variants.csv`.

Nor does the bin row itself have anywhere to put one: `RepeatAlleleRow` has no `pmid`,
no `doi`, no `evidence_level`. The same holds for `heteroplasmy.csv`, `copynumbers.csv`
and `activity_phenotype.csv`.

The net effect is that this compiles green under `--strict`, asserting a clinical
threshold with no evidence attached and nothing anywhere reporting its absence:

```csv
gene,repeat_unit,measure_kind,measure_min,measure_max,direction,conclusion,unresolved
HTT,CAG,repeat_count,40,,risk,"Full-penetrance allele. Associated with Huntington disease.",false
```

**Why this is the wrong way round.** A `variants.csv` row is frequently drafted from
ClinVar, arrives with citations attached, and is *required* to carry `studies.csv`. A
bin boundary is the opposite: where 36 rather than 35 becomes "reduced penetrance" is a
clinical judgement drawn from a specific literature, it is exactly the number a reader
would want to check, and the format asks for nothing. Grounding is enforced where it is
most often automatic and absent where it is most interpretive.

We are not asking for a schema we can fill from memory — the opposite. Right now the
honest options are to leave the claim ungrounded or to write the citation into
`conclusion` as prose, and prose is not checkable.

Suggestions, cheapest first:

1. **Say what is intended.** If bins are meant to be grounded through `sources.csv`
   alone, one line in `SCHEMAS.md` saying so would settle it — though `sources.csv`
   records a *dataset's* terms, not a per-bin citation, so it answers "where did this
   table come from" and not "why is the boundary here".
2. **Warn on an ungrounded binning table**, the way an uncovered measure range warns
   today. Cheap, needs no schema change, and turns silence into a visible decision.
3. **Let `studies.csv` key on a binning row** — a `gene` + `repeat_unit` identity
   alternative in its `any_of`, or a generic `subject_key`. This is the real fix and the
   largest, so it is last.

A note on what we did meanwhile: we left the thresholds ungrounded rather than citing a
paper we had not confirmed states them. `literature_search` for the HTT thresholds
returns cohort papers that *use* the categories and no standard that *defines* them, so
citing any of them would have been a provenance claim we could not support.

# Field notes from just-module-creator — the resolver's two empties, 2026-08-11

Found while checking which of seven rsIDs in an LLM-written summary were real — a task where "Ensembl
has no locus for it" is the fingerprint of a fabricated identifier, which is what made a fused failure
mode expensive rather than merely untidy.

## S20 — a failed Ensembl request and a genuine absence produce the identical finding, and it reads as a definite "no"

**Status — accepted in full; shipped in enricher 0.5.4, in the shape you proposed.** Reproduced from
the code rather than the symptom: `ensembl.py` returned `([], None)` on line 98 for "asked, nothing
there" and the identical `[], None` on line 101 for "the request failed", so by the time
`_lookup_live_loci` tested `if not loci:` the distinction was gone, exactly as you traced it.
`resolve_rsid` now has three outcomes — loci, `[]` for an answered absence, `None` for could-not-ask —
and `_lookup_live_loci` reports the last as a **warning** saying the answer is unchecked rather than
empty. Your candidate is what shipped, including `warning` over `info`.

Two things the probe added. **A 4xx is an answer, not a failure**: Ensembl 400s on rsIDs it cannot
resolve (`rs3216883`, which dbSNP reports as merged), so only a 5xx, a transport error or a timeout
return `None` — lumping every exception into "could not ask" would have turned a real negative into a
permanent maybe. And **an empty answer now carries its source**, so `hint.checked` gains
`ensembl-rest` when Ensembl was reached and said nothing: the signal you had to read as a *missing*
element is now a present one stating the opposite, which is the half of your report we could fix
without asking you to diff sets.

**The artifact half was worse than the finding half, and you did not see it because `lookup_variant`
does not write one.** `enrich()` recorded a failed request as `ResolutionRow(status="not_found",
source="ensembl")` — a claim, in the injected table a module compiles from, that Ensembl was asked and
does not have this rsID. That row is no longer written: the key stays `unresolved`, so `strict` still
refuses and `best_effort` still warns, but nothing claims a source said no. The argument was already in
the tree, four lines below, where the non-GRCh38 branch declines to write `not_found` for exactly this
reason — *"a negative nobody established, about a question never put."* It was one branch away from
the case that mattered. `EnrichmentResult.unreachable_rsids` names them, beside `unresolved`, for the
same reason `clin_sig_not_checked` sits beside an empty conflict list.

**Your rejected candidate was rejected here too, for your reason.** Retrying inside `resolve_rsid`
narrows the window without closing it, and the caller still cannot tell the two empties apart when the
retries run out — which is when it matters. Retry persistence is already the deployment's to set
through `$JUST_DNA_HTTP_RETRY_ATTEMPTS` (RM42), and that is the right axis for it.

Tests: the two states asserted as distinct values in one test, the 4xx/5xx split, and the `enrich()`
row that is no longer written. `F17`'s advice can be retired — a bare `loci: []` now means what it
says, and the unreachable case announces itself.
<!-- triaged: 0.5.4 · sha 7c9537a53cee -->

**Reported by:** just-module-creator (`lookup_variant` wraps `enricher.lookup`) · **Found:** 2026-08-11,
checking seven rsIDs a user brought in from an LLM-written summary of a YouTube lecture.

**What I ran.** Seven `lookup_variant` calls in one batch, each `VariantHint` via
`enricher.lookup`, cache cold for all seven. Five resolved. Two came back with `loci == []` and this
finding:

```
rs6567160: live Ensembl has no GRCh38 locus for it either
rs13010010: live Ensembl has no GRCh38 locus for it either
```

**What I expected.** That message to mean what it says: Ensembl was asked and has no GRCh38 locus.

**What happened.** Both are ordinary, well-attested SNPs. Re-running the *same call* minutes later,
unchanged:

| rsid | run 1 | run 2 |
|---|---|---|
| rs6567160 | `loci: []`, "live Ensembl has no GRCh38 locus for it either" | `chr18:60161902 T>C` |
| rs13010010 | `loci: []`, "live Ensembl has no GRCh38 locus for it either" | `chr2:100236272 C>T` |

So the transport failed and the failure was reported as a **negative answer**. `_lookup_live_loci` is
explicit that this is by design:

> A failure is a finding, never an exception … `EnsemblResolver.resolve_rsid` already swallows its own
> transport errors into an empty result.

Swallowing into an empty result is what fuses the two states. By the time `_lookup_live_loci` tests
`if not loci:` there is nothing left to distinguish "Ensembl answered, no such locus" from "the request
never completed", and the one finding it writes asserts the first.

**The only trace is an absence.** `hint.checked.add(source)` runs on the success path only, so a failed
run omits `ensembl-rest` from `checked` — the payloads differ:

```
run 1  checked: ["…/ensembl_variations"]                    # no ensembl-rest
run 2  checked: ["…/ensembl_variations", "ensembl-rest"]     # present
```

That is the correct signal and it is unreadable in practice: it is a *missing* element in a set, while
the finding beside it states a conclusion in prose. No caller diffs `checked` against the set of sources
that were supposed to be consulted, and the finding is `info`, so nothing draws the eye.

**Why this one is worth a fix rather than a note.** It inverts the judgment the surrounding workflow
exists to support. My actual task was deciding which rsIDs in a machine-written document were real —
four of the seven turned out to be fabricated, pairing a real dbSNP id with a gene on another
chromosome. `loci: []` plus "Ensembl has no locus" is exactly the fingerprint of a fabricated id, so
run 1 put two real, published variants (`rs6567160`, a long-standing MC4R BMI locus; `rs13010010`) in
the fabricated pile. I only caught it because five-of-seven succeeding on one batch looked more like
flaky egress than like a document that was 30% honest. An author with less reason to be suspicious
drops two true rows and reports the source as more fabricated than it is — and the same shape silently
weakens `enrich()`, where a cache-cold row that failed to resolve is indistinguishable from one with
no locus to find.

It also contradicts the tri-state rule the rest of this tree is careful about: an unreachable source
reports `results=null`, never `0`, and the reason it must is exactly this. `_lookup_live_loci` is the
one place where an unreachable source reports the negative instead.

**Candidate fix.** Have `EnsemblResolver.resolve_rsid` distinguish its two empties — a third return
value, or `None` for "could not ask" against `[]` for "asked, nothing there" — and branch:

```python
loci, source = clients.ensembl.resolve_rsid(rsid)          # loci: list | None
if loci is None:
    hint.findings.append(Finding(None, None, "warning",
        f"{rsid}: live Ensembl could not be reached — its answer is UNCHECKED, not empty"))
    return
if not loci:
    hint.findings.append(Finding(None, None, "info",
        f"{rsid}: live Ensembl has no GRCh38 locus for it"))
    return
```

`warning` rather than `info` because the caller has to decide whether to retry, and `info` is where
this currently hides.

**A candidate I think is wrong:** retrying inside `resolve_rsid` until it succeeds. It narrows the
window without closing it, and it converts a fast wrong answer into a slow one — the caller still
cannot tell the two empties apart when the retries are exhausted, which is precisely when the
distinction matters most. Retry policy is also the consumer's to set; the fusing of the two states is
not.

**What I did meanwhile.** Nothing, deliberately. `lookup_variant` is a pass-through and mitigating this
on our side would mean either re-implementing the resolver or retrying blind, and neither belongs in a
wrapper. Tracked as `F17` in `just-module-creator`, where the advice for now is to distrust a bare
`loci: []` whenever `checked` lacks `ensembl-rest` — which is only actionable because I now know to look.

# Field notes from just-module-creator — a test run over the authoring surface, 2026-08-11

Three filed in one sitting while writing a two-table, literature-grounded module: the generated
reference could not describe the one table a human hand-writes, the compiler warned about the row that
schema text instructs them to write, and an hg19 supplementary table had nowhere to go. The first and
third are both about a surface an author reaches for *instead of* reading our source, which is the
point of having one.

## S21 — `authoring_reference()` omits `SourceRow`, the one table an author is told to write by hand

**Status — accepted; shipped in format + compiler 0.5.4.** Reproduced exactly, and the root turned out
to be one level below the report. `SourceRow.layer` and `.declared_use` run closed-vocabulary
validators while carrying **no `vocabulary=` marker**, so no generated surface could see them — and the
guard that exists for precisely this (`test_every_enforced_vocabulary_field_declares_its_options`,
which discovers enforcement by *behaviour*, not by a list) never covered them, because it iterates
`_ALL_MODELS` and the model was not in it. One omission hid the other. Both markers are now on the
fields, `SourceRow` is in the registry, and the guard covers it automatically: with the markers
stripped it reports `SourceRow.layer` and `SourceRow.declared_use`, which is checked rather than
asserted.

Your first option is what shipped, not the `hand_authored_sidecars` alternative. A separate key would
only be seen by consumers who learn to look for it, whereas `models` is what every existing reader
already iterates — so the drift-proof property you were relying on does the delivery. The three
permissions are asserted as `bool | None` in the test, because tri-state-where-`None`-means-unknown is
exactly the part nobody reconstructs from a filename.

**The probe found the other half of your F20, and it was ours.** `draft.blank_template("sources.csv")`
answered *"'sources.csv' is not an authored table of this format"* — a false claim from the surface an
author reaches for instead of reading our source, which is what you ended up doing. `sources.csv` is now
in `DRAFTABLE`, so `blank_template`, `required_fields` and `authoring_requirements` all serve it; its
natural key is `(source, layer)`, borrowed from `licensing.merge_sources_csv` so a draft and the
enricher cannot disagree about whether a row is already recorded. The other three sidecars stay out on
purpose — a pass writes them, so there is nothing for an author to start.

Two consequences worth knowing. A module consisting *only* of `sources.csv` still refuses with "no
recognized table", which is right — it is a licence sidecar, not a table a module can be made of. And
your `list_tables`/`describe_table` inconsistency should resolve on its own once you are on 0.5.4, since
both now resolve through the same registry.
<!-- triaged: 0.5.4 · sha 53623ac0e6d3 -->

**Reported by:** just-module-creator (`authoring_reference` / `describe_table` wrap this) ·
**Found:** 2026-08-11, writing a `sources.csv` for a two-row literature-grounded module.

**What I ran.** I needed `sources.csv`'s columns. The generated reference is documented as "every model,
column, vocabulary and one-of rule at once", so I asked it:

```python
>>> from just_dna_format import reference
>>> blob = json.dumps(reference.authoring_reference())
>>> [p in blob for p in ('SourceRow', 'declared_use', 'share_alike', 'layer')]
[False, False, False, False]
```

**What I expected.** `SourceRow` among the models, since `sources.py:74` defines it and it is a table a
human writes.

**What happened.** It is absent, along with every column and both of its vocabularies
(`VALID_SOURCE_LAYERS`, `VALID_DECLARED_USE`). Only the bare string `"sources"` appears, from an
unrelated field description.

**Why this one stings.** `sources.csv` is the *only* fact sidecar a human is expected to author, and
this tree says so itself. `MISPLACED_COLUMN_REASONS['source']` in `vocab.py:411` ends:

> To declare a source you read by hand, add a ROW to sources.csv (whose own `source` column is the
> subject of the row, and is what the licence gate and manifest.sources join on)

So the schema instructs the author to hand-write a row in a table the generated reference does not
describe. Every other sidecar is produced by a pass, where omission costs nothing; this one is not.

It also compounds: `sources.csv` is the only thing the compile licence gate reads, and the house rule
is that unknown terms are undetermined rather than permitted. An author guessing at the columns is
guessing at the shape of the licence declaration — and `share_alike` / `commercial_use` /
`redistribution` being a **three-axis** design with `None`-means-unknown is exactly the sort of thing
nobody reconstructs correctly from a filename. I only got it right by importing `SourceRow` and
reading `model_fields`, which is reading your source to learn your schema — the thing the generated
reference exists to make unnecessary.

**Candidate fix.** Include `SourceRow` in `authoring_reference()`'s `models`, and its two vocabularies
in `vocabularies`. If the concern is that the generated reference means *authorable annotation tables*
specifically, then a separate `hand_authored_sidecars` key carrying just this one would say the true
thing more clearly than silence does.

**A candidate I think is wrong:** documenting the columns in prose in `sources.py`'s module docstring
and leaving the reference alone. The docstring is already good and it did not help — a consumer reaches
for the generated reference precisely because prose drifts, and a column list maintained in two places
is the drift this module's own comment (`vocab.py:409`, "a hand-kept list of models would be the drift
this module keeps removing") says it exists to remove.

**What I did meanwhile.** Read `SourceRow.model_fields` directly and wrote the two rows by hand,
leaving all three licence flags empty so they stay UNKNOWN rather than asserting permission. Tracked as
`F20` in just-module-creator, where the surface has a related and separate defect of its own:
`list_tables` advertises `sources.csv` as a sidecar while `describe_table` and `get_template` both
reject the name outright.

## S22 — literature reports hg19 and a module must be GRCh38; there is no supported path between them (longshot)

**Status — accepted as a real gap and filed as [RM48](ROADMAP.md#rm48--an-hg19-coordinate-has-no-supported-path-into-a-grch38-module-and-liftover-is-the-wrong-primitive) (0.6). No code in 0.5.4.**
Your framing is adopted whole, including the part that argues against your own request — the item is
filed as *rsID recovery*, with liftover as the announced fallback, for the reason you give: with an
rsID liftover is unnecessary and strictly worse, so it is only reachable in the case where the lifted
coordinate becomes the row's sole identity with nothing independent to check it against. That is the
hazard class behind the 3,038-variant off-by-one, and a tool that manufactures it would look official
while being less checkable than your manual conversion.

**The RM15 distinction is right and is why this could be filed at all.** RM15 changes the module's own
build and therefore every identity, which is what makes it 1.0; a one-way authoring-time conversion
re-keys nothing and is additive, so it sizes as 0.6. Filing it under RM15 would have parked it behind a
major-version blocker for no structural reason — that observation is the most useful thing in the
report.

**What the item is gated on**, so the wait is legible rather than silent: the recovery lookup is against
a build no link here touches (every one is gated on GRCh38), so it needs either an hg19-keyed dbSNP
surface or a chain file — and a chain file is a provisioned, pinned asset with its own licence and
release, i.e. the entire snapshot apparatus for one authoring convenience. Choosing that surface is the
design round.

And yes: three outcomes, mapped/unmapped/ambiguous. You filed S20 the same day about `([], None)`
fusing two of them in this very code path, so the requirement is written into the roadmap item rather
than left to be rediscovered.
<!-- triaged: 0.5.4 · sha 71f8c7faea86 -->

**Reported by:** just-module-creator · **Found:** 2026-08-11 · **Priority: low — filed as a longshot,
not a request.** Nothing is broken; this is a use case with no answer yet, and we would rather it sat in
your backlog than in ours.

**The situation.** An author curating from older literature has hg19/GRCh37 coordinates in front of
them, often from a supplementary table, and the module has to be GRCh38. Nothing in the four packages
converts between them — no liftover, no chain file, no `pyliftover`; `sequences.py:14` mentions
liftover only as a *cause* of a bad authored `ref`. So the author converts by hand, off-tool, and the
result lands in `variants.csv` as an ordinary authored coordinate with nothing recording where it came
from.

**This is not RM15, and we think that distinction is the useful part of this note.** RM15 is
`❌ — 1.0` and is about *supporting another build as the module's build* — it changes `variant_key`
semantics and every coordinate, the identity-change class. What is wanted here is a **one-way,
authoring-time** conversion: the module stays GRCh38, only the author's input is hg19. It re-keys
nothing, needs no GRCh37 refget table, and changes no published identity. Filing it under RM15 would
park a small additive tool behind a 1.0 blocker for no structural reason.

**We think liftover is the wrong primitive, and would rather argue that than ask for it.** Trace when
it is actually needed:

- If the paper gives an rsID, liftover is unnecessary — author the rsID and let resolution find
  GRCh38. Strictly better, because it *produces* the independent second value
  `compiler.resolution._verify` needs.
- So liftover is only reachable when there is **no rsID and only an hg19 coordinate**. And in exactly
  that case the lifted coordinate becomes the row's sole identity, with nothing independent to check it
  against. The only remaining check is `sequences.verify_reference_alleles`, online, which sees roughly
  three rows in four.

That makes a liftover tool a generator of unverifiable-by-construction identities — the hazard class
behind the 3,038-variant off-by-one. **What the author actually wants is rsID recovery**: given hg19
`chrom:start:ref:alt`, return the rsID (or that there is none), so they author an rsID and normal
resolution does the rest. Same input, and it converts an unverifiable coordinate into a verifiable
identity using machinery the enricher already has. Liftover then survives only as the fallback for a
locus with no rsID at all, where it should say so loudly rather than quietly.

**One hard requirement whichever primitive wins.** The outcomes are **mapped**, **unmapped**, and
**ambiguous** (a coordinate that lifts to several targets), and they must not collapse — `pyliftover`
returns an empty list for unmapped *and* for a missing chain, which is the same fusing we filed as
`S20` today, in this same resolution path. If this ever gets built, `S20`'s shape is the thing to not
repeat.

**Chain files are the other reason we think this is yours rather than ours.** A chain file is a
provisioned, pinned data asset, and the enricher already owns snapshot provisioning from HuggingFace;
we own none. And `resolution.csv`'s `source` column is where a recovered-or-lifted coordinate's
provenance has to land, which is your schema.

**What we do meanwhile.** Nothing, and we are not planning a tool of our own — an authoring-side
liftover that no reference check can see would be worse than the manual conversion it replaces, because
it would look official. Our skill tells authors to prefer the rsID, which sidesteps the whole problem
for the majority of rows.

## S23 — a `sources.csv` row for a literature source is structurally an orphan, and the schema tells you to write it

**Status — accepted; shipped in compiler 0.5.4, your narrower candidate.** Reproduced, and your reading
of the mechanism is exactly right: `used_sources` is gathered from the `source` **columns** of the
generated tables, `studies.csv` has none by the design `MISPLACED_COLUMN_REASONS['source']` states, so
`pubmed` could never enter that set and the branch followed mechanically. A `literature`-layer row is
now uncorroborable — and therefore not an orphan — whenever the module carries `studies.csv` rows.

**The reason this was worth fixing at once rather than filing is the incentive, which you identified
and which the table in your report measures.** Declaring the service warned; deleting it was silent. So
the author who *reads* the warning ends up shipping with their literature provenance unrecorded, and
nothing anywhere says so — the compiler talking an author out of the exact row the licence gate exists
to read. An over-declaration is the cheap error here; that is not.

This is the same exemption the annotation layer already had, reached by the same argument, which is
what makes it narrow rather than a softening: `frequency` stays corroborable, because `frequencies.csv`
is machine-written *with* a `source` column, so a frequency declaration in a module with no frequencies
really is stale and still warns. Both directions are pinned by tests.

Your rejected candidate is rejected here too, for your reason — a `source` column on `studies.csv`
would contradict the design note directly, and a curated annotation's provenance is the module's rather
than a per-row link. Nothing to do on your side beyond retiring `F21`'s note; your two rows were true
and the warning was the thing that was wrong.
<!-- triaged: 0.5.4 · sha 4630136804e6 -->

**Reported by:** just-module-creator · **Found:** 2026-08-11, compiling a two-table module that cites
one PMID. **Priority: low-to-medium** — no wrong data, but the warning steers an author toward deleting
provenance.

**What I ran.** A module with `variants.csv` (3 rows, one rsID), `studies.csv` (1 row, PMID 26287746),
`resolution.csv`, and a `sources.csv` I hand-wrote covering the two literature services I read the
record through. Compile, strict:

```
warnings: ["sources.csv declares 2 source(s) no table in this module uses: ['europepmc', 'pubmed']"]
```

**What I expected.** No warning. `MISPLACED_COLUMN_REASONS['source']` in `vocab.py:411` says, of a
hand-authored fact table:

> A hand-authored fact table has no such column by design … **To declare a source you read by hand, add
> a ROW to sources.csv**

I added exactly that row, and got told it is unused.

**What happens, and why both directions are wrong.** `_orphan_sources` (`compiler.py:2671`) and the
undeclared check (`compiler.py:2673`) both compare `declared` against `used_sources`, and
`used_sources` is gathered from the `source` **columns** of the generated tables. `studies.csv` has no
`source` column — by the design the quote above states — so `pubmed` can never enter `used_sources`.
Both branches then follow mechanically:

| `sources.csv` | compile says |
|---|---|
| carries a `pubmed` row (what `vocab.py` instructs) | **warning:** declares a source no table uses |
| carries no `pubmed` row | **silence** — verified by deleting the file and recompiling: `warnings: []` |

So compliance is warned and omission is silent. The direction of the incentive is the problem: an
author who reads the warning deletes the row, and the module then ships with its literature provenance
unrecorded and *nothing* to say so. That is the opposite of what the licence gate exists for, and it is
reached by following the warning rather than by ignoring it.

**Candidate fix.** Treat a `layer='literature'` row as used when `studies.csv` is non-empty — the
module demonstrably consulted *some* literature service, and which one is not joinable precisely
because a curated annotation's provenance is the module's rather than per-row. More generally: exempt
layers whose tables carry no `source` column from the orphan check, since for those the join can only
ever return nothing.

**A candidate I think is wrong:** adding a `source` column to `studies.csv` so the join works. That
contradicts `MISPLACED_COLUMN_REASONS['source']` directly, and its reasoning is right — a per-row link
on a curated table is not what the provenance means.

**What I did meanwhile.** Kept the two rows and left the warning standing, because the rows are true and
the warning is not. Tracked as `F21` in just-module-creator, whose skill additionally asserts the
*opposite* of the observed behaviour and is our own bug to fix.
