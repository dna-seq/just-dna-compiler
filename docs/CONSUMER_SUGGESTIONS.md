# Consumer suggestions

Field notes from consumers adopting the libraries. Two sources so far, in sections by adoption:

- **[just-dna-registry](#s1--module-extraforbid-rejects-registry-owned-identity-keys-the-whole-pre-04-corpus-carries)** (S1–S2) — the catalog server, on 0.4.
- **[just-dna-lite](#field-notes-from-just-dna-lite--the-05-enricher-at-panel-scale)** (S3–S6) — the app, on the 0.5 enricher at panel scale.
- **[just-dna-registry](#field-notes-from-the-registry--adopting-052)** (S7–S8) — the catalog server again, on 0.5.2: a digest that moves without content (S7), and a manifest that cannot say a check ran (S8).

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
question — whether an artifact should carry the derived 0.3 axes at all — is parked as 1.0 work in
[ROADMAP.md](ROADMAP.md), since filling the column moves every compiled module's bytes. Digest
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

# Field notes from the registry — adopting 0.5.2

*Written 2026-08-11: S7 while re-deriving why three panel digests moved, S8 while wiring
`clin_sig_not_checked` through the publish and dry-run paths.*

---

## S7 — `sources.csv` stamps `fetched_at` into the digest, so a rebuild is never reproducible

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

## S8 — the manifest records what resolution *achieved* but not which checks *ran*, so `unchecked` and `clean` are indistinguishable to a downloader

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

## S9 — the 0.4 table families are materialized verbatim, so `resolution.csv` never reaches them

**Status — option 2 shipped in 0.5.3 (2026-08-11); option 1 is filed as
[RM43](ROADMAP.md#rm43--resolution-reaches-the-snp-core-only-so-a-04-led-module-is-rsid-joinable-and-nothing-more)
and is 1.0 with a prerequisite, not a 1.0 for the reason given below.** Reproduced on this tree's own
`reference_examples/pgx_slco1b1_simvastatin/`, so the note needed no extra evidence. Three things the
investigation added: option 1 does not merely move `artifact.digest`, it **breaks Principle 7** —
materializing the coordinate and running compile → reverse → compile moves `content_signature`, because
reverse re-emits a filled coordinate as an authored one, which is what `VariantRow.authored_ident`
exists to prevent and no 0.4-family model has; `manifest.fully_resolved` is vacuously `true` for a
table-only module, against the trust rule its own field comment states; and `heteroplasmy.csv` was
missing from the enricher's subject list entirely, so that family could not have been resolved even in
principle (fixed in the same cut). What ships now is the warning, with the second count — how many of
the unjoinable rows `resolution.csv` *could* place — because that is what separates "never enriched"
from "the coordinates exist and this tier does not apply them here".

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
