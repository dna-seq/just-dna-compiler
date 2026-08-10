# Consumer suggestions

Field notes from consumers adopting the libraries. Two sources so far, each in its own section:

- **[just-dna-registry](#s1--module-extraforbid-rejects-registry-owned-identity-keys-the-whole-pre-04-corpus-carries)** (S1–S2) — the catalog server, on 0.4.
- **[just-dna-lite](#field-notes-from-just-dna-lite--the-05-enricher-at-panel-scale)** (S3–S6) — the app, on the 0.5 enricher at panel scale.

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
