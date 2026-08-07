# Proposal — 0.5.1: four seams a downstream consumer cannot cross without re-implementing something

**Status: ✅ all four decided and shipped in 0.5.1** (2026-08-07), alongside
[RM38](ROADMAP_HISTORY.md#rm38--a-cache-for-every-gated-source-the-hosted-enricher). Each is
**enricher/compiler API shape**, out of `artifact.digest`, and touches no parquet — which is what made
them patch-shippable inside the closed 0.5 digest window (CONSTITUTION P3/P8) rather than 0.6 schema
work. What shipped, and the shape decisions taken while building, are recorded per item in
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md#rm39--one-pass-in-the-family-ignored-offline); this file keeps
the *filing* — the argument as the consumer made it — because that is the part worth not re-deriving.

One thing changed on contact. RM41 was filed as *"either half closes it, preferably both"*, and both
shipped — which makes 0.5.1 a **two-package cut**: `just-dna-compiler` takes the public
`load_csv_rows` / `load_spec_variants`, `just-dna-enricher` requires `>=0.5.1`, and `just-dna-format`
stays at 0.5.0 with nothing changed.

These came from a **consumer field report** rather than from design, in the same shape as
[`CONSUMER_SUGGESTIONS.md`](CONSUMER_SUGGESTIONS.md)'s S1/S2: `just-dna-registry` 0.11 wires the 0.5
pipeline server-side (`enrich()` → `compile_module(strict=…)`, plus the optional passes behind a
`/check` pre-flight endpoint), and each of the four below is a place where doing that correctly
required either special-casing one pass against its siblings, copying logic out of this workspace, or
reaching into a decorator's state to change behaviour nothing exposes.

The through-line is worth stating, because it is the same argument each time and it is one this
codebase already makes elsewhere: **a number this workspace computed and then discarded gets
recomputed by every consumer, and a recomputation is a place to drift.** That is exactly why
`base.field_category` exists (two surfaces answering one requiredness question, and the drift-proof
one was the stale one) and why `resolution.hosting_verdict` is shared with the deprecated DuckDB path
rather than duplicated. Each item below is the same shape, one tier out.

---

## RM39 — `enrich_dosage_sensitivity` is the only pass with no `offline` parameter

**The asymmetry.** Every other pass in the enricher takes `offline: bool` and degrades on it —
`enrich`, `enrich_frequencies`, `enrich_gene_metrics`, `enrich_literature`, `enrich_pgx`,
`verify_acmg_sf`. `clingen.enrich_dosage_sensitivity(spec_dir, *, mode, declared_use, write,
curation_text, url)` does not. It downloads ClinGen's gene-curation TSV unconditionally, and the only
way to stop it is to inject `curation_text=` — which requires the caller to have fetched the thing
already, i.e. to have solved the problem the parameter would solve. The `dosage` CLI command has no
`--offline` flag either, so the asymmetry is user-visible and not merely internal.

**What it costs.** [ENRICHER.md](ENRICHER.md) documents `--offline` as *"clamps to local caches /
sidecars"* and the registry advertises the same guarantee — an offline dry run is asserted to make
zero egress. A caller running the family under one flag therefore has to know, out of band, that one
member of it does not honour the flag, and hoist a `if not offline:` around that call specifically.
The registry now does; it is a guard that has to be re-derived by every consumer, and the failure
mode of forgetting it is silent egress from a path documented as having none.

**Why the shape matters more than the flag.** `enrich_frequencies` is the model to copy: online-only,
and `--offline` makes it a **no-op with a warning**, reported as `FrequencyResult.skipped_offline`.
That is a first-class answer a caller can render (*"the frequency pass did not run because this
deployment is offline"*), and it is different both from "it ran and found nothing" and from "it
failed". `ClinGenResult` has no equivalent, so even a caller that does hoist the guard has nowhere to
put the reason except its own prose.

**Ask.** `enrich_dosage_sensitivity(..., offline: bool = False)`, no-op-with-a-warning when set,
`ClinGenResult.skipped_offline` beside it, and `--offline` on the `dosage` command. Additive on every
axis; nothing that exists today changes behaviour.

**Not asked for, deliberately:** a ClinGen *snapshot*. That is RM38's family and a much bigger
question. This is only about the flag meaning the same thing in every function that takes it.

---

## RM40 — VRS coverage is computed by `enrich()` and thrown away

**The finding.** `vrs.mint_resolution_rows` returns a `MintResult` carrying exactly the two numbers
`compile_module` will later stamp into `manifest.compilation.vrs_alleles` /
`vrs_alleles_identified` — plus `unmintable_reasons`, the grouped-by-reason breakdown that is the
*actionable* half — and `enrich()` logs `coverage_warnings()` and drops the object.
`EnrichmentResult` carries `rows`, `unresolved`, `sources`, `mode`, `ref_mismatches`,
`clin_sig_conflicts`, `stale_rsids`, `par_twins_dropped` — and nothing about minting.

**Why that is a defect rather than a missing convenience.** The whole point of the coverage counters,
as [COMPILER.md](COMPILER.md) puts it, is that *"a consumer can read the reliability of the identity
scheme instead of inferring it"*. A consumer that wants to read it **before** a compile — which is
what a publish dry run is — cannot, so it re-implements the counting over `EnrichmentResult.rows`.
The registry's `services/enrich.py::vrs_coverage` is that re-implementation, and it has to get two
non-obvious rules right to agree with the manifest a publish would produce:

- count per **ALT slot**, not per row, because `vrs_id` is a parallel array of `alts`;
- treat an *absent* cell as `len(alts)` unnamed slots rather than as zero slots, or a table where
  nothing minted reports flawless coverage out of a denominator of nothing.

Both are stated in `MintResult`'s own docstring. A consumer that reads only the field list gets the
second one wrong in the direction that reports a problem as a success — the failure mode the
`identified == alleles` derivation exists to prevent.

**And the reasons are unreachable at all.** `unmintable_reasons` is where *"no refget table for build
'GRCh37'"* and *"needs the reference sequence"* live — the difference between a finding an author can
act on and one that is the tier's own limit, which is precisely the distinction the verify pass's
three-outcome table is built on. Today that survives only as a log line, so a service reporting to a
publisher over HTTP can show the shortfall and not the reason for it.

**Ask.** `EnrichmentResult.vrs: MintResult | None`, populated when `mint_vrs=True` and `None` when the
pass did not run (`None` ≠ a coverage of zero — the house rule). Purely additive: a dataclass field
with a default, no behaviour change, no signature change on `enrich()`.

---

## RM41 — `_load_csv_rows` is private, and it is the only way to load an authored CSV

**The finding.** Two checks take rows rather than a spec directory —
`acmg.verify_acmg_sf(variants: list[VariantRow], …)` and
`identifiers.check_identifiers(variants, …)` — unlike every other pass, which takes `spec_dir`. So a
caller has to turn `variants.csv` into `VariantRow`s itself, and the only thing that does that
correctly is `just_dna_compiler.compiler._load_csv_rows`, which is private. This workspace's own
`just-dna-enricher` CLI reaches across the package boundary for it in both `check-acmg` and
`check-identifiers`.

**Why re-implementing it is a trap rather than a chore.** It is not `csv.DictReader` plus
`Model(**row)`. It carries two rules a hand-rolled loader gets wrong:

- **An empty cell becomes `None`, and the key is kept.** [SCHEMAS.md](SCHEMAS.md) documents the
  consequence in the requiredness discussion: `MeasureBinRow.measure_kind` has a default, so
  `is_required()` is `False`, but the model receives `None` rather than its default and **fails on
  type**. A `""` where the loader would have put `None` is a different failure again.
- **`genome_build` is told to each row, not read from it.** A pydantic model built from a CSV dict
  has no `module_spec.yaml` in scope, so a loader that does not inject the module's declared build
  mints GRCh38 identities for a GRCh37 module — the exact bug `_restamp_for_build` exists to fix, one
  layer up.

A consumer that writes its own loader therefore has a second, drifting copy of the rule this
workspace already had to fix once.

**Ask — either half closes it.** Preferably both:

1. **Make the loader public**: `compiler.load_csv_rows(path, row_model, file_label, genome_build)`,
   same body, same three-tuple return. It is already de-facto public — this workspace consumes it
   across a package boundary, which is the definition.
2. **Give the two row-taking checks a spec-dir entry point**, so they match the shape of every other
   pass: `verify_acmg_sf(spec_dir=…)` / `check_identifiers(spec_dir=…)` alongside the existing
   `variants=` form. The row-taking form should stay — it is the right thing for an in-process caller
   that already holds the rows.

Until then a consumer picks between reaching for a private symbol and re-implementing a loader with
two known traps in it. `just-dna-registry` chose the private symbol and pinned the signature with a
test, on the reasoning that a rename failing CI is strictly better than a silent divergence in row
normalization — but that is a workaround for a boundary, not a place to leave it.

---

## RM42 — the retry policies are import-time constants, so a deployment cannot tune persistence

**The finding.** Every live client retries, and the policy is sound: `tenacity`, exponential jitter,
on transport errors, timeouts and the two clients' own rate-limit exceptions, and — the part that
makes this safe to touch at all — **paced before the retry**, so an extra attempt spends a slot of
the budget rather than bursting past it. What a caller cannot do is choose *how many*. The nine
policies are `@retry(stop=stop_after_attempt(3))` (or `(4)` for gnomAD and eutils) evaluated at
import, with no parameter, no setting and no environment variable.

**Why one number cannot serve both callers.** Three attempts is right for the audience the CLI was
written for: an author at a terminal, who would rather see a failure in ten seconds than wait out a
flapping upstream. It is wrong for the other deployment shape the 0.5 tiering created — a **server**
running `enrich()` inside a publish. That work is unattended, it has already been queued, nobody is
watching a spinner, and giving up on a transient 502 does not cost ten seconds: it costs the
publisher a whole re-upload of a module the server had already accepted, validated and dedup-checked.
The two want opposite things from the same constant, which is the definition of a knob.

**What a consumer does today.** `just-dna-registry` walks the package at boot, finds every attribute
that is an instance of `tenacity.BaseRetrying`, and assigns `policy.stop = stop_after_attempt(n)` —
raising only, so a client already more persistent keeps its own policy. It works, `BaseRetrying.stop`
is documented and stable, and it is pinned by a test that asserts the walk still finds all nine. It
is also plainly a consumer reaching into another package's decorator state to change behaviour its
author did not expose, which is the thing an RM is for.

**Ask.** A single `EnricherSettings`-style attempt count (or `JUST_DNA_HTTP_RETRY_ATTEMPTS`) read
where the clients are constructed, defaulting to today's values so nothing changes for the CLI. Two
notes on shape, from having built the workaround:

- **A floor, not a setting per client.** The per-client differences are deliberate — gnomAD and
  eutils are at 4 because their budgets are tightest — so a single number that *raises* everything
  to at least `n` preserves that tuning, where a single number that *sets* it would flatten it.
- **Leave a composed `stop` alone.** `stop_after_attempt(3) | stop_after_delay(60)` means both, and
  raising one term silently changes a policy whose author meant the conjunction. None of the nine is
  composed today; the rule matters the day one is.

---

## What is *not* here

Three things the same audit looked at and concluded were correct as they are, recorded so they are not
re-raised. **One of them has since changed for a reason the audit could not have known**, and the note
is kept rather than deleted because the *reasoning* was right at the time:

- **`enrich_clinpgx` taking no `offline` parameter.** ~~Unlike RM39 this is right: the pass is
  snapshot-only and never fetches, so a flag would be a parameter with one legal value.~~ (It did cost
  a consumer bug — the registry skipped the whole PGx family offline, ClinPGx included — but the fix
  belonged in the consumer, and the note now in ENRICHER.md pass 6 is what it needed.)
  **Overtaken by RM38, shipping in the same cut.** The premise was that the pass never fetches, and
  that was true only because its snapshot was orphaned from the plumbing — no `locations` resolver, no
  `ensure_*`, so it skipped itself unless handed `--snapshot` by hand. Now that it can *provision* one,
  it has something to decline to do, and `offline` has a second legal value. The general lesson is
  worth more than the item: **"a flag with one legal value" is a claim about the current wiring, not
  about the function** — re-ask it whenever the wiring changes.
- **`refget_accession` raising `UnsupportedBuildError` rather than returning `None`.** Documented,
  deliberate, and the caller-side catch is the point — a build with no table should be heard as "not
  built yet", not answered in GRCh38.
- **The `--use` spelling split** (`non-commercial` on the CLI, `non_commercial` in
  `VALID_DECLARED_USE`). The CLI normalizes at its own boundary, which is where a user-facing spelling
  belongs; a consumer exposing the vocabulary member directly just has to validate against the
  frozenset, which is one line and the same thing every other vocabulary asks for.
