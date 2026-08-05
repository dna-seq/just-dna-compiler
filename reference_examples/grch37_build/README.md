# `grch37_build` — a module on the build the compiler does not resolve

**What this probes:** *the identity key names its build.* Every other reference example is GRCh38, so
every code path that hardcoded `"GRCh38"` looked exactly like a path that read the real value. This
module declares `genome_build: GRCh37` and authors real GRCh37 coordinates, which is the smallest
change that tells those two apart.

`docs/SCHEMAS.md` states the property this rests on: a GA4GH VRS allele id addresses its sequence by
**refget accession**, so GRCh38 and GRCh37 mint distinct, correctly non-colliding ids — and minting is
GRCh38-only today (RM15), so a GRCh37 row must fall through to a coordinate key rather than get a
GRCh38-flavoured one.

## The data

HFE, the two common variants, from the report that described both (PMID 8696333):

| variant | GRCh37 | GRCh38 |
|---|---|---|
| C282Y (`rs1800562`) | 6:26,093,141 | 6:26,092,913 |
| H63D (`rs1799945`) | 6:26,091,179 | 6:26,090,951 |

The 228 bp offset is the whole point: either coordinate is a valid *place*, and neither is a place at
the other's number. Coordinates are authored rather than rsIDs so the module states the build-relative
facts directly — an rsID would only be resolvable against GRCh38, which is the case the enricher now
refuses rather than answers.

## What it broke

Seven defects, all in the direction of *silently relabelling the assembly*. The first four
were found by building this module; the last three by then asking whether the list was
complete — see *The sweep* below.

**1 — `reverse_module` hardcoded the build, so the round trip relocated the identity.**
`genome_build` reaches the artifact through `manifest.json` and **no parquet column**, and reverse wrote
`genome_build: GRCh38` into every spec it rebuilt. So for this module:

```
compile  → variant_key = 6:26093141:G:A        (correct: no refget table for GRCh37)
reverse  → module_spec.yaml says GRCh38        (false)
compile  → variant_key = ga4gh:VA.TWxWV6Sk…    (a GRCh38 allele identity for a GRCh37 position)
```

`artifact.digest` moved, so Principle 7 failed outright — but the worse half is the new key. A VA is
content-addressed: it asserts *this allele at this base of this sequence*, and 6:26,093,141 on GRCh38 is
a base this module never named. The forward path had been fixed in 0.5 (`_restamp_for_build`, after "a
GRCh37 module minted GRCh38 identities, silently"); reverse put the same bug back one step later.
`resolution.csv`'s own `genome_build` column was hardcoded the same way, and `resolve_from_table`
filters on that column, so a reversed table was mislabelled *and* unjoinable.

**2 — the enricher ignored the declaration entirely.** `enrich()` took `genome_build: str = "GRCh38"`
and nothing ever passed it — no CLI flag, no caller. Every resolver link inside is gated on
`genome_build == "GRCh38"`, and so is the warning that says a non-GRCh38 module resolves nothing, so all
of it was unreachable. Enriching the rsID form of this module wrote the **GRCh38** coordinate into its
`resolution.csv` labelled `GRCh38`, with a GRCh38 VA minted for it, and said nothing. Same shape as the
`_restamp_for_build` bug: the guard and its fall-through both existed and the value never arrived.

It also wrote `status="not_found"` for the rsID, which claims Ensembl was asked and does not have
`rs1800562`. No link had run. `VALID_RESOLUTION_STATUS` has no `unchecked` member, so the fix is to
write no row — the position is simply still unset, which the unresolved list already reports.

**3 — one GRCh37 row aborted the whole enrich run.** `refget_accession` **raises**
`UnsupportedBuildError` for a build with no table, deliberately, so every call site has to catch it.
`VrsMinter.mint`'s substitution branch did not — while the indel branch beside it always had — so a
single hand-authored `genome_build: GRCh37` row in an otherwise fine `resolution.csv` killed the run
with an unhandled exception. `derive_vrs_allele_id`'s docstring meanwhile promised it "never raises".

**4 — the frequency pass would have fetched a different variant.** `_alleles_from_resolution` took every
resolved row regardless of `genome_build`, and gnomAD's variant id is `chrom-pos-ref-alt` — no assembly in
it. So a GRCh37 coordinate is not a rejected request, it is a *valid request for whatever GRCh38 variant
sits at that number*, and its counts would have been written into `frequencies.csv` under this module's
key. The same row also reached `derive_variant_key` without a `build`, minting a GRCh38 VA for a GRCh37
coordinate — the third place producing that exact false identity, which is why the build gnomAD serves is
now a named constant (`gnomad.FREQUENCY_GENOME_BUILD`) rather than an assumption at each call site.

## The sweep — defects 5 to 7, and why they were only found by asking

Four instances of one mistake is a pattern, not a coincidence, so the next question was whether the list
was complete. It was not, and the method that answered it is worth keeping: **`derive_variant_key` mints
a VRS id only when handed a single `alts`** — an rsID short-circuits first, and no-`alts` or
multi-allelic cells fall through to a coordinate key that never touches the build. The exposure is
therefore small and enumerable: *calls passing one allele and omitting `build=`*.

**5 — the fix to defect 1 was itself incomplete.** Threading the build into `resolution.csv`'s
`genome_build` *column* left the same function deriving `variant_key` from `(chrom, start, ref, alts)`
on the default, so this module reversed to rows reading
`ga4gh:VA.TWxWV6Sk…,6,26093141,G,A,GRCh37` — a GRCh38 allele identity and a `GRCh37` cell in one row,
contradicting each other. `resolve_from_table` joins on `variant_key`, so the table also matched nothing
on recompile. The round trip still looked like a fixed point because this module's coordinates are
authored and nothing needed filling: it held by luck, not by correctness.

**6 — `enrich()` never re-stamped `variants.csv`.** `_restamp_for_build` was wired into the compiler's
two load sites, and there is a **third** — the enricher loads the same file. So `enrich` produced a
`resolution.csv` keyed by GRCh38 VAs while the compiler keyed the same rows `6:26093141:G:A`: a
resolution table that could not join to the module it was made for.

**7 — `_subject_of_variant`'s fallback**, threaded rather than left on the default.

`compiler/tests/test_build_call_sites.py` now walks the AST of all three packages and fails on any call
that supplies an allele without supplying a build. Two exemptions, each stating its reason and each
checked to still exist: `VariantRow._freeze_identity` (a validator with no module in scope — but it
writes a *stored field*, which is exactly what `_restamp_for_build` corrects afterwards) and
`HeteroplasmyRow.variant_key`, which has no stored field to correct and is **RM36**. The check found
defects 6 and 7 on its first run.

## Reproducing

```bash
just-dna-compiler validate reference_examples/grch37_build
just-dna-compiler compile  reference_examples/grch37_build out/grch37
just-dna-compiler reverse  out/grch37 out/grch37_rev
just-dna-compiler signature reference_examples/grch37_build
just-dna-compiler signature out/grch37_rev      # the same content_signature
just-dna-compiler compile  out/grch37_rev out/grch37_again   # the same artifact.digest
```

Two warnings are expected and correct, and neither is a defect in the module:

- `genome_build is 'GRCh37': GA4GH VRS allele identity is GRCh38-only (RM15), so 3 variant(s) are keyed
  by coordinate instead` — the honest statement of what the key is.
- `Resolution-table fill skipped: compiler is GRCh38-bound` — nothing needs filling here (the
  coordinates are authored), and the compiler says so rather than resolving cross-build.

`artifact.digest` is `sha256:020304fa…`; `compile → reverse → compile` is a fixed point on
`artifact.digest`, `content_signature` **and** `resolution_signature`.

## What this example is *not*

It is not multi-build support. RM15 remains open: there is still one refget table, coordinates are not
tagged per build, and cross-build annotatability is not recorded. What ships here is the narrower
guarantee that the tools **say which build they are working in and never quietly change it** — a
GRCh37 module compiles, round-trips and keeps a build-relative coordinate key, and every place that
could have answered a GRCh38 question in its name now declines instead.
