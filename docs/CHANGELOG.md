# Changelog

Shared change log for the just-dna module format/compiler ecosystem. Because
`just-dna-format` + `just-dna-compiler` are consumed by **just-dna-pipelines**,
**just-dna-marketplace**, and **just-dna-agents**, cross-repo integration changes are recorded
here so parallel work in the other repos isn't surprised. Newest first.

## 2026-08-04 — the citations table travels with the snapshot

**A downloaded ClinVar snapshot was second-class.** `citations/` was built and published nowhere, so a
consumer who *provisioned* the snapshot had no PMIDs while one who *built* it did — and `draft-panel`
cannot produce a compilable module without them, because `studies.csv` is mandatory ("grounding evidence
is mandatory"). `publish_reference_snapshot` now uploads the parquet sidecars beside `data/`, and
`ensure_*_snapshot` fetches them.

The layout moved into `locations` — `SNAPSHOT_DATA_DIRNAME`, `SNAPSHOT_SIDECAR_DIRNAMES`,
`CITATIONS_DIRNAME`, `RELEASE_FILENAME` — because **four** parties have to agree on those names (builder,
publisher, provisioner, reader) and every disagreement so far has been silent: `release.json` uploaded and
never fetched, `citations/` built and never published, and `CITATIONS_DIRNAME` declared twice. A sidecar
stays a **sibling** of `data/`: the readers glob `data/*.parquet`, so a two-column citations table inside
it is the same poisoning a stale single-file `clinvar.parquet` causes. Absence stays normal at both ends —
only ClinVar has a sidecar, and only after `clinvar citations`.

**And publishing it made the snapshot's provenance a real question.** ClinVar publishes
`var_citations.txt` on its own cadence, so an artifact can carry records from one release and citations
from another; shipping both while `release.json` documented only the VCF would be mixed-vintage and silent
about it — the same confusion `dataset` is inside the fact set to prevent for the two gene-constraint
routes. `build_citations` now merges a `citations` block (source URL, sha256, row count, built_at) into
`release.json`, read-modify-write so the records' provenance survives; it hashes the input itself when the
caller has no digest, because recording "unknown" with the bytes on disk is an unknown we chose not to
establish; and an unreadable `release.json` is reported and left alone rather than overwritten — the
citations table is still written, since a provenance failure is not a data failure.

## 2026-08-04 — the published snapshots are wired in, and a published dataset accumulates

The ClinVar and gnomAD-constraint snapshots are published as HF datasets, so the enricher now *uses*
them. Three things were in the way, and the middle one is the interesting one.

**`ensure_constraint_snapshot` had no caller.** It was written when the download body was generalized for
ClinVar, and nothing ever invoked it — so a plain install running `gene-metrics` fell straight through to
the live gnomAD API, recorded its **v2.1.1** constraint numbers, and then warned about the
v2.1.1-vs-v4.1 difference for a snapshot it had never tried to fetch. `enrich_gene_metrics` now provisions
first, in the shape `enrich()` already used for the other two snapshots: `--offline` is the only switch,
a failure degrades to the API rather than sinking the pass, and the warning names the consequence (older
numbers, not no numbers). Verified against the live upload: the pass fetched
`gnomad_constraint.parquet` into the default cache and wrote a `gnomad_v4.1_constraint` row.

**A published dataset accumulates, and `just-dna-seq/clinvar/data` proves it.** It carries a 159 MB
`clinvar.parquet` from the single-file era beside today's 25 `clinvar-chr*.parquet` — the publisher adds
and never deletes. Its columns are the raw VCF INFO fields (`clnsig`, `clnrevstat`, …), the reader globs
`data/*.parquet`, and provisioning everything would therefore put two schemas under one DuckDB relation
and fail every query on `Referenced column "clin_sig" not found`. That is not a hypothesis: it is exactly
how a locally-built old snapshot broke the `clin_sig` cross-check the day before. So each `ensure_*` now
fetches only the files its snapshot is *made of* (`clinvar-*.parquet`, `homo_sapiens-*.parquet`,
`gnomad_constraint.parquet`); a repo with none of them is a clear error naming what it did have; and a
foreign file *already* in a local cache is reported, never deleted, with the fix in the message.
Confirmed end to end — provisioning ClinVar from the live repo pulled 25 files, skipped the 26th, and the
HFE example then enriched fully offline.

**`release.json` was uploaded and never fetched**, so a *built* snapshot could say which release it was
and a *provisioned* one could not. It comes down with the data now. That is the difference between a cache
and a pinnable reference: `source_sha256` is what `GenePanelSpec.reference_sha256` pins against (RM4), and
it cannot pin a file that was never fetched. The filename moved to `locations.RELEASE_FILENAME` so the
publisher and the provisioner cannot disagree about it again; a repo without one still provisions.

## 2026-08-03 — RM31: one indel spelled two ways, reconciled without a reference

**ClinVar publishes a SHOX deletion as `X:634689 CAG>C` and Ensembl publishes the same 2 bp AG deletion as
`X:634690 AGAG>AG`**, and `genotype_fits` compared allele *strings*, so `rs1569493663` resolved to
`not_found` in `reference_examples/shox_par1/`. It now resolves — 20 rows, 10 findings, both PAR contigs —
with no authored edit.

`alleles.parsimony_reduce` (new, format tier, stdlib) strips the flank a *collection* of alleles shares,
which leaves the event: `{C, CAG}` and `{AGAG, AG}` both reduce to `{'', 'AG'}`. **No position is passed
in and none could be** — the row records no coordinate at all, because `clinvar_draft` prefers the rsID and
the model forbids `ref`/`alts` without one, so the authored genotype is spelled in a frame the row never
stated. A genotype naming two alleles carries its own frame regardless, since both strings share whatever
flank their record used.

`hosting_verdict` replaces the boolean with **three** answers, so nothing is missed silently:

- **reconciled** → the locus hosts the genotype;
- **different event size** → a confident negative, because re-anchoring moves an indel but never changes
  how many bases it adds or removes (`rs281864532` really does file a 1 bp insertion and a 2 bp deletion
  under one rsID);
- **same size, different content** → **undecided**, the repeat-region residual, and the locus is *kept*
  with a message saying what was not decided. The previous message asserted "a different variant sharing
  the rsID", which was flatly wrong for the case that found the item.

`genotype_fits` remains as the boolean face (`is not False`), so all three call sites and the documented
digest parity with the DuckDB resolver are unchanged. **The raw string comparison runs first**, so
normalization can only ever *add* acceptances — pinned by a property test over every real
(genotype, ref, alts) triple in the reference examples, and the reason this was safe to ship in the window.

**Adding the case to the resolution matrix found a second defect in the other half of the compiler.**
`_check_allele_membership` did its own exact set difference, so once resolution reconciled the spellings
and expanded onto the locus, membership refused the same module under `strict` — the compiler contradicting
itself. It now asks the shared predicate, Kleene-OR'd over the loci.

**One residual, stated rather than hidden:** the compiled row carries the authored genotype in ClinVar's
frame beside the resolved alleles in Ensembl's, so a consumer joining them by string equality still misses.
`just_dna_format.alleles` is public and dependency-free so a consumer can apply the same reduction; having
the enricher rewrite the authored cell is the parked co-authoring item, because it would make
`content_signature` depend on a network fetch.

## 2026-08-03 — RM34: `draft --allele`, and three defects the filter's own dogfood found

**`draft --gene CYP2D6` produced 16,290 diplotype rows, 73% `Indeterminate`** — every row a faithful
transcription, and a module no human can read, with no way to take a subset (`--drug` *adds* rows).

`--allele` is the filter because the author already knows the answer: a caller emits a bounded allele set,
and *n* alleles is *n(n+1)/2* pairs. Six alleles turn CYP2D6 into **21 diplotypes**, verified against live
CPIC, and the result compiles. It applies to **all three** tables — filtering one and not the others
leaves a module naming alleles it never defines. `*1` is always kept (defined by carrying no variants, and
without it `*1/*2` would be undraftable for an author who asked for `*2`), an unknown allele refuses with
the list CPIC publishes, and `--allele` needs a single `--gene` because a star name is gene-scoped.

**Then the filter was turned on real CYP2D6, and found three more:**

- **its own count was misleading** — "567 of 16836 drafted" for six alleles, because the 546 copy-number
  rows (`*4x≥3/*95`) the filter deliberately leaves alone were counted as kept and then skipped by the
  notation rule. Two findings, neither visible. Now counted over parsable pairs: "21 of 16290".
- **`DELTCT` and `AAAGGGGCG(2)` are not IUPAC ambiguity codes**, and the message said they were — a false
  claim that sends an author after the wrong thing. `cpic.unusable_allele_reason` separates an *ambiguity*
  (an uncertainty CPIC recorded, never expressible) from a *notation* (a grammar gap, RM5, a release could
  widen), and reports them as two findings.
- **two more walls of un-aggregated warnings** — 67 unusable-allele lines and 10 "no rsID and no
  chromosome" lines in one run — collapsed to one line per reason with the count and examples.

## 2026-08-03 — RM35: a shared bin endpoint is a boundary, and the higher bin owns it

**A continuous binning table could not be tiled without a finding**, and that was a check nobody could
satisfy rather than one that was failing: bounds inclusive at both ends, overlap an error, any positive
hole a warning — so two adjacent `allele_fraction` bins either shared an endpoint (error) or left a hole
(warning), at any epsilon. `reference_examples/mt_heteroplasmy/` was authored `0.0–0.099` / `0.1–0.299`
to dodge the error and warned anyway, four times.

`validate_bins` now treats a shared endpoint on a **dense** kind (`allele_fraction`, `prs_percentile`) as
a boundary rather than an overlap, with the lookup rule stated where a consumer will read it: *select the
row with the greatest `measure_min ≤ x`*. The example migrated to touching bounds — `0.0–0.1`,
`0.1–0.3`, `0.3–1.0` — and compiles clean.

**Why not half-open `[min, max)` for continuous kinds**, which is the formally cleaner option: it makes
`measure_max` mean two different things depending on `measure_kind` (P5), the number written in the cell
is then not in the bin while the same column stays inclusive on integer tables, and a bounded domain's
top value — AF `1.0` is homoplasmy, a real measurement — becomes unreachable unless the last bin is
authored open, which is a new convention plus a new finding class. Both options produce identical
authored bytes in the interior and need the same check predicate; they differ in one cell and in what an
author must remember, and the charter's gate is the author.

Discrete kinds are untouched: `repeat_count`/`copy_number` tile cleanly under inclusive bounds — which is
where the convention came from and why this was missed — so a shared endpoint there is still a real
overlap and still an error. Two bins sharing a **lower** bound now refuse on any kind, since the
tie-break selects the greatest `measure_min` and equals do not sort. The original bind stays demonstrable
in the suite by running the same bounds through `copy_number`.

## 2026-08-03 — RM33: a resolution link is not a licensed source

**Every enriched module warned that `ensembl-rest` has no terms recorded**, because `resolution.csv`'s
`source` names *which link answered* while `sources.csv`'s names *a licensed source*, and
`_source_checks` compared the two by string equality. Fixed with the third thing the roadmap entry said
was missing rather than either repair it rejected: **`ResolutionRow.authority`**, naming the licensed
source a link speaks for, with the link→authority map in the **enricher**
(`licensing.RESOLUTION_AUTHORITY_BY_LINK`) — the only tier permitted a source convention (P2). It is
provenance, outside `RESOLUTION_FACT_FIELDS`, so no `resolution_signature` moved; reverse does not
re-emit it, because a reversed table's facts came from parquet and no source answered for them.

Implementing it turned up four more, all in the same family:

- **`sources.csv` had been dropping `redistribution` on every write.** `SOURCES_FIELDNAMES` was a
  hand-kept literal that omitted it, so all four reference examples recorded *unknown* for an axis the
  terms constants state as `True` — and RM27 is a gate designed to read a column that had never reached
  a single file. The list is now derived from `SourceRow.model_fields`, and the test asserts field-by-field
  equality across a write→read cycle so the next column cannot be lost either.
- **Three passes consulted sources and recorded none.** `enrich`, `frequencies` and `gene_metrics` now
  write their `SourceRow`s through one shared `licensing.record_source_terms`, filling the
  `resolution`/`frequency`/`gene_metrics` layers that `VALID_SOURCE_LAYERS` had reserved and nothing had
  ever written. None can taint a module (only `annotation` does), so what they carry is the
  **attribution** those sources request — as much the table's job as the prohibitions are.
- **`GNOMAD_TERMS`, read from gnomAD's own policy page**: CC0 for the primary exome/genome data,
  attribution requested but not required, the no-reidentification undertaking, and a notice that layered
  annotations keep their own terms (SpliceAI is CC BY-NC) — which is why "gnomAD is CC0" must not be read
  as covering everything gnomAD serves.
- **`gene_metrics.csv` had the same overloading**, and was fixed the other way: `source` recorded
  `gnomad-constraint`/`gnomad-api`, two *routes* for one source, and now records `gnomad` with the route
  left in `dataset` — where the v2.1.1-vs-v4.1 distinction already lived, and which is inside the fact
  set where `source` is not.
- **An `annotation`-layer row could never be corroborated**, so the orphan check called it stale on
  every drafted module: "no table used it" is decided from fact tables' `source` columns, and the
  annotation layer *is* `variants.csv`/`diplotypes.csv`, which carry none by design. Those rows are now
  exempt — and they are the rows the licence gate keys on, so calling them unused was backwards.

## 2026-08-03 — the ACMG SF check was answering against a list a year out of date

**`check-acmg` called correctly authored rows wrong, and passed every guard doing it.** ACMG published
**SF v3.3** in June 2025 (`10.1016/j.gim.2025.101454`) — 84 genes over 100 gene-condition rows, adding
`ABCD1`, `CYP27A1` and `PLN`. NCBI still serves its adaptation of **v3.2** (81/94), which is the only
form `acmg.py` could read. So a module flagging `acmg_sf=true` on ABCD1 got
`acmg_sf=true but ABCD1 is not on ACMG SF v3.2`.

That is the exact *short list* failure `parse_acmg_page`'s five guards were built to prevent, and none
of them could see it: the page is well-formed, complete, and simply a release behind. The guards defend
against a list that is **broken**; nothing defended against a list that is **old**. Demonstrated rather
than asserted — `test_a_v33_gene_is_reported_as_wrong_against_the_v32_page` runs the pre-fix path on the
real v3.2 fixture and shows the three mismatches.

Two halves, and the first is the real fix:

- **The list is injectable now, and the check works offline.** ACMG publishes v3.3 as a supplementary
  **workbook**, which beats the page on every axis: version-pinned behind a DOI instead of
  hand-maintained, content-hashable, and carrying four columns the page lacks (`Inheritance`,
  `Phenotype Category`, the release that first listed each gene, and ACMG's scope-of-reporting text —
  recorded, never applied, since reporting policy is out of format scope). `acmg build` writes
  `acmg_sf.csv` + `release.json` (`sf_version`, `source_sha256`, DOI, counts); `check-acmg --sf-list`
  reads it. Same split as ClinVar: **builder in `openpyxl` (`[dev]`), pass in the standard library**, so
  a plain `pip install just-dna-enricher` can still run the check — the rule `clinpgx.py` learned by
  reading its snapshot with polars. Only MedGen ids go the other way (NCBI has them, ACMG's sheet does
  not); no verdict reads them.
- **The scrape path admits when it is stale.** `KNOWN_LATEST_SF_VERSION` is **one version string**, and
  when the list actually read is older every disagreement is demoted to a new `unverifiable` verdict:
  warned in both modes, never a `strict` refusal. Both directions are demoted, not just the observed one
  — ACMG can remove entries as well as add them, so a `denied` against a stale list is equally
  unsettled. This is the house tri-state doing its job: a mismatch against a superseded list is a
  question, and answering it is worse than withholding. The hand-kept constant is acceptable where a
  hand-kept gene list would not be, and the asymmetry is the reason: when v3.4 ships the constant
  under-warns (degrading to the previous release's behaviour), whereas a transcribed list would make
  confident wrong claims about named genes.

Three existing tests asserted `not_listed` against the v3.2 fixture and had to move to a `current_list`
fixture built from the workbook — the demotion working as intended, and the reason both fixtures are
kept side by side in `assets/`: the page tests the *parser*, the workbook tests the *check*.

The workbook parse earned one guard of its own shape. ACMG's trailing **disclaimer sits in the Gene
column** — ~1,200 characters of prose that a naive read counts as an 85th gene, with a symbol no
authored row will ever match. It is skipped only when every other cell in its row is empty; an
unreadable symbol on a *populated* row refuses, because that is the `<tr>` failure again. Headers are
matched by prefix and resolved **by name to a column index** (ACMG misspells one — `Disease/Phentyope` —
and pads another), so a reordered column moves the reader instead of shifting every value left.

## 2026-08-03 — 0.5.1: a GRCh37 module minted GRCh38 identities, silently

The sharpest finding of the dogfooding round, and the shortest to state. **A module declaring
`genome_build: GRCh37` compiled with no warning and stamped GA4GH VRS allele ids that name the GRCh38
sequence.**

The guard already existed and was already correct. `derive_variant_key` takes a `build` and its
docstring says any build without a refget table "falls through to case 3 rather than minting an id
that would claim the wrong sequence"; `vrs.py` opens by promising that "GRCh38 and GRCh37 mint
distinct, correctly non-colliding ids instead of silently baking one build into the key". **Nobody
ever passed the argument.** `VariantRow._freeze_identity` runs at row construction, where there is no
module and therefore no declared build, so every row took the GRCh38 default.

Probed on a real pair rather than argued: HFE C282Y is 6:26092913 on GRCh38 and 6:26093141 on GRCh37.
A GRCh37 module at 26093141 minted `ga4gh:VA.TWxWV6SkC5-…` — **byte-identical** to what a GRCh38
module claiming that coordinate gets, which is a different place in the genome 228 bp away. Two
modules about different loci shared one content-addressed identity, and a registry deduplicating on
`variant_key` would have merged them.

Fixed in the compiler, which is the only tier holding both the row and the spec: `_restamp_for_build`
re-derives the key against the declared build after load. Re-stamping is not a new concept — the
resolver already re-keys on one-to-many expansion — and it is a strict no-op on GRCh38, which is every
module that exists. Both load sites are covered, because `compile_module` re-loads its own rows and
fixing only `validate_spec` would have left the artifact carrying the bad keys.

The fallback is now **stated**, which is the other half of the bug: silence is what let this go
unnoticed. The warning says the consequence rather than the fact — a coordinate key is build-relative,
will not join against GRCh38-keyed data, and means a different locus on another build.

## 2026-08-03 — 0.5.1: dogfooding mitochondrial heteroplasmy — one blocker fixed, one proved unfixable

`reference_examples/mt_heteroplasmy/` — two MELAS-causing MT-TL1 variants (m.3243A>G, m.3271T>C)
binned in blood and in muscle. Heteroplasmy is the case the binning primitive was built for, so it is
the right place to ask whether the primitive holds a real module.

**A mitochondrial gene could carry only one variant, and that was a hard block.** `HeteroplasmyRow`
keyed on `(gene, reference_sequence, tissue)` and carried **no variant identity at all**, so both
variants' bins landed in one group, `validate_bins` saw `[0, 0.099]` overlapping `[0, 0.149]`, and
refused — as an **error**, not a warning, so the module could not compile. There was no honest
workaround: `trait_efo_id` is in the group key and would have separated them, but both variants cause
MELAS, so using two ontology ids means falsifying the data to satisfy the tool. The alternatives were
one module per variant or dropping a real annotation.

The row now carries optional `rsid`/`chrom`/`start`/`ref`/`alts`, mirroring `PharmVariantRow` exactly,
entering the key through a derived `variant_key` property. Optional is load-bearing: a single-variant
table groups precisely as before (P3/P8). `alts` is in the derivation because MT-ATP6 m.8993T>G and
m.8993T>C are the same base with different alleles and different phenotypes. `REFERENCE_EXAMPLES.md`
§4 only ever showed one variant per gene, which is why this was invisible rather than decided — the
schema had generalized from a one-variant case.

**And a check that cannot be satisfied — RM35, recorded not patched.** Three rules, each right alone,
jointly unsatisfiable on a continuous measure: bounds are inclusive at both ends, an overlap is an
**error**, and any positive hole is a **warning**. Two adjacent `allele_fraction` bins therefore either
share an endpoint (a measurement of exactly `0.1` selects two phenotypes) or leave a hole — and no
epsilon escapes it, `[0, 0.0999999]` and `[0.1, 1.0]` still warn. Every `allele_fraction` and
`prs_percentile` table must carry a finding forever. Integer kinds are fine and that is why it was
missed: HTT `[6,35]`, `[36,39]`, `[40,∞)` is genuinely gapless because the domain is discrete, and the
inclusive convention was generalized from those. Proved by construction in the tests. Every candidate
resolution is a semantic decision — half-open intervals for continuous kinds, dropping the continuous
gap check, or treating a shared endpoint as a boundary — so it is recorded. *(Resolved later the same
day as the third of those; see the RM35 entry above.)*

**What the module gets right, and is worth copying.** Each variant/tissue group carries its own
`unresolved` sentinel, and the conclusions state the consequence: an absent heteroplasmy read is not a
low one, and the low-blood row tells a reader to measure urine or muscle before reassuring anyone,
because blood is the tissue most likely to look innocent.

## 2026-08-03 — 0.5.1: dogfooding CYP2D6, the hard PGx case — and a defect in a check shipped hours earlier

`REFERENCE_EXAMPLES.md` has listed CYP2D6 as "the hard PGx case" since 0.4 and nobody had built it.
Drafting it from CPIC produces **16,290 diplotype rows over 644 defining variants and 206 alleles**,
and compiles in 1.9 seconds. Three findings, two fixed.

**The phase-ambiguity check shipped this morning was overclaiming, and CYP2D6 proved it.** It flagged
`*10/*8`, `*100/*8`, `*101/*8` and `*147/*8` as "indistinguishable without phase — a phased consumer
resolves it". They are not phase-ambiguous: `*10`, `*100`, `*101` and `*147` carry **identical
defining-variant sets** in CPIC's core definitions (rs1058164 G, rs1065852 A, rs1135840 G), so those
pairs present the same genotype phased or not. The advice would have sent an author to buy phasing
that cannot help.

The two cases separate exactly, by grouping on the *phase-preserving* signature: the same multiset of
haplotype definitions means nothing distinguishes them, a different one means phase does. They now
get different messages, and the first is arguably the more valuable finding — "this module names
alleles it defines identically, so at most one of these disagreeing rows can be right" is a real
data-quality signal. CYP2D6 has **378** such groups and 20 genuinely phase-resolvable ones; HFE still
reports the phase case correctly. This is the dogfooding rule applied to my own new code: the check
was built, run against real data, and found wrong within the day.

**398 warning lines became 2.** Both classes now aggregate per gene with examples and a count — the
rule CPIC taught with ~600 lines for CYP2C19, which this check had to relearn.

**And the same wall in the CPIC provider.** 546 CYP2D6 diplotypes are skipped because CPIC writes
copy number as `x≥3` and `≥` is not a star-string character, and they were emitted one line each —
inside a function that aggregates the activity-score skips four lines below. 644 output lines became
99, which is what finally made the three *allele* skips and the licence row visible at all.

**Recorded, not patched — RM34.** The module is 73% `Indeterminate` (11,825 rows of CPIC saying it
cannot call that pair) and there is no way to draft a subset: `--drug` adds rows rather than filtering
them. The gap shows as a parity difference — `draft-panel` takes `--clin-sig` and
`--min-review-stars`, `draft` takes nothing — but *which* filter is the decision, and each spends a
CLI name on a different view of what a PGx module is for.

## 2026-08-03 — 0.5.1: dogfooding a pseudoautosomal module — two fixes, three questions

`reference_examples/shox_par1/` was built adversarially: pick a real gene where the libraries are
likely to claim more than they know, and use only the shipped surface. SHOX sits in **PAR1**, the
stretch X and Y share and recombine, so it is present in two copies in every karyotype. Ten
pathogenic ClinVar alleles, drafted, curated, enriched, compiled. Four findings; two are fixed and
three are recorded because patching them would mean inventing a design.

**The non-diploid guardrail was wrong in both directions.** Its comment claimed Y was *"the safe,
false-positive-free half of non-PAR X/Y"*. PAR1 (Y:10,001–2,781,479) and PAR2
(Y:56,887,903–57,217,415) are diploid in everyone, so a two-allele genotype there is correct and the
advice to use a single allele would have made the annotation wrong — and the author need not even
choose the Y coordinate, because the one-to-many expansion produces the Y row on its own
(`rs6603251` maps to X:359845 *and* Y:359845).

The same probe found the **opposite** error, which is the bigger one. The check lived inside
`_cross_validate_variants`, which compile calls twice and the second time takes *errors only* — so a
warning whose entire input is `chrom` was computed before resolution filled it and discarded after.
`rs199474657` with genotype `A/G` — the MELAS m.3243A>G fake-diploid error, and **the shape every
drafting provider emits** — was silently unchecked, while `MT,3243,A/G` warned. Coverage depended on
authoring style rather than on data. Now: `vrs.in_pseudoautosomal_region` answers three-valued (the
`None` being a build with no PAR table, where the message names both readings and asserts neither),
the guardrail runs where `chrom` is final, and it keeps a pass inside `validate_spec` too, since the
standalone `validate` command has no resolution step and would otherwise have been silently emptied.
PAR intervals are assembly constants of the same class as `vrs.REFGET_GRCh38`, so holding them is not
the un-injected-reference mistake.

**`draft-panel` asked for a decision and withheld its inputs.** It leaves `genotype` stubbed —
correctly, since ClinVar publishes alleles and zygosity follows from inheritance mode. But a genotype
is nucleotides from `{ref} ∪ alts`, and an rsID-identified row carries neither, so the author faced
`rs201157428` and `<<REPLACE>>` with nothing to write from. `enrich` would resolve the alleles and
refuses to load a file containing a placeholder — which is *right*, because forward resolution is
allele-aware and a placeholder genotype would skip that filter on exactly the one-to-many rsIDs that
need it. The alleles are now reported, one line per stubbed row, and still never written: writing them
would need the whole coordinate, and `alts` is redundancy-bearing.

**And a message that asserted the wrong reason.** `rs1569493663` does not resolve — ClinVar publishes
`X:634689 CAG>C`, Ensembl publishes the same 2 bp AG deletion as `X:634690 AGAG>AG`. The warning said
"that record is a different variant sharing the rsID", sending an author to hunt a dbSNP merge that
does not exist. It now names both readings. The underlying normalization is **RM31**.

**Three recorded rather than patched**, each because the obvious repair is wrong. *(Two of the three were
fixed later the same day — see the RM31 and RM33 entries above — and in both cases part of what made them
look undecidable turned out to be wrong. RM32 stands, and is deferred to its own run.)*

- **RM31** — indel spellings. A reference-free parsimony trim fixes this pair but cannot left-align
  inside a repeat; a reference-backed one can only run in the enricher, and `genotype_fits` is shared
  with the compiler, which by charter holds no reference.
- **RM32** — nine of ten SHOX variants map to both contigs, so 10 findings became 19 rows, all inside
  `artifact.digest`, and standard GRCh38 analysis sets hard-mask the Y PAR so those rows can never
  match. Collapsing them would contradict VRS identity (X and Y are different refget sequences), and
  the expansion is correct for the paralog case it was built for.
- **RM33** — `resolution.csv`'s `source` names *which link answered*; `sources.csv`'s names *a
  licensed source*. Two vocabularies under one name, compared by string equality, which is why every
  enriched module warns that `ensembl-rest` has no terms. Writing a row per link would make
  `ensembl-rest` and `ensembl-graphql` two sources with identical terms; teaching the compiler a
  link→source map would give it a source convention, which P2's 0.5 tightening removed on purpose.

## 2026-08-03 — 0.5.1: CLI/API parity — signing was never CLI-complete

An audit of every command against every public function across the three packages. Most of it was
already level; three gaps were not, and they clustered in one place, for one reason.

**`just-dna-format` ships no CLI** — Typer would breach its pydantic-plus-cryptography dependency
floor (Goal 2) — so anything the schema tier owns that a *user* needs has to surface through
`just-dna-compiler`. `verify` was added on exactly that argument. Three siblings were still
Python-only:

- **`keygen`** (new). `sign --private-key` demanded a key file the toolchain had no way to produce,
  and `verify --public-key` demanded a string only `public_key_b64_from_pem` could derive. So signing
  was CLI-complete only for someone willing to write Python — the same gap `verify` closed, left open
  one step upstream. A test now runs the whole keygen → sign → verify loop through the CLI, with a
  wrong-key case so it cannot pass for the wrong reason. The key is unencrypted PKCS#8 (what
  `sign_digest` reads): a deliberate limit, since this bootstraps a key rather than managing one, and
  a passphrase prompt would imply custody guarantees nothing here provides. It **refuses to
  overwrite** — every signature made with the old key would stop verifying, and published bytes are
  never mutated.
- **`reference`** (new). `authoring_reference()`/`json_schemas()` had no route at all, which hurt most
  for the consumer that most needs them: an MCP surface offering an author the valid values had to
  import `just_dna_format.reference`. `describe` answers that for one table; this answers it for all
  of them plus the vocabularies, the closedness flag, `REQUIRED_ANY_OF` and the palette.

**And the audit found a drift in the anti-drift module itself.** `authoring_reference()` reported
requiredness with pydantic's two-way `is_required()` while `just_dna_compiler.draft` had already been
fixed to the three-way `required` / `defaulted` / `optional` split. The middle category is the
documented trap — `MeasureBinRow.measure_kind` and `unresolved` are *not* required and *not* safely
left blank either, because `_load_csv_rows` turns an empty cell into `None` and keeps the key. Two
surfaces answering one question, and the one whose entire job is not to drift was the stale one. The
split moved to **`base.field_category`**, the only tier both can import from; `draft.field_category`
re-binds it and the reference emits it as `category`. `required` is kept beside it — insufficient
rather than wrong, and removing a published key breaks consumers.

**Left unlevelled on purpose:** the enricher mirrors `template` but not `stub`/`requirements`/
`describe`/`hint`/`scaffold`. The offline authoring surface has an owner; the one mirror exists so a
PGx author does not switch binaries for a CSV header. And `clinical.verify_clin_sig` /
`sequences.verify_reference_alleles` stay command-less because their verdicts land on `resolution.csv`
and the enrichment report — run standalone they would compute a finding with nowhere to put it. Both
packages' command → API tables are now in [COMPILER.md](COMPILER.md) and [ENRICHER.md](ENRICHER.md).

## 2026-08-03 — 0.5.1: RM28's cis/trans case, closed by a check rather than a grammar

RM28's proposal says the demand for a predicate language "has to come from a module somebody actually
failed to write". So one was written. `reference_examples/hfe_compound_het/` builds the case that most
justified the grammar — HFE C282Y and H63D, where the same two heterozygous calls mean *compound
heterozygote, at-risk* in trans and *carrier* in cis — and it needs no new machinery.

**A diplotype is already a statement about two homologs.** `haplotypes.csv` says which alleles ride
together on one chromosome (which is what `apoe_epsilon` established) and `diplotypes.csv` pairs two of
them, which is what "in trans" means. `C282Y`/`H63D` and `C282Y-H63D`/`wt` are two rows with bricks
that shipped in 0.4. The single relational notion the proposal was going to add to the grammar — in-cis
/ in-trans — is what a diplotype pair *is*. Between this and APOE, both halves of the phase argument
are now answered by the existing tables.

**What building it surfaced is the real finding.** Nothing said those two rows are indistinguishable
without phase. They present the identical unphased genotype (rs1800562 G/A, rs1799945 C/G) and carry
opposite conclusions, and nearly all consumer genotype data is unphased: reporting the first
manufactures an at-risk finding, reporting the second suppresses one. Derivable from tables the
compiler already holds, so it shipped as `_cross_validate_phase_ambiguity` — a warning, never a block.

A `requires_phase` column was rejected. It would make an author restate what the data already
determines and go stale the moment a haplotype is edited; this is the validate-by-redundancy class,
not a schema gap. The signature is, per variant, the **sorted pair** of alleles the two haplotypes
contribute — sorted because that is precisely what losing phase does. An unmentioned variant reads as
the implied reference and an allele equal to the row's own `ref` normalizes to the same sentinel, so
no reference *sequence* is needed anywhere (P2): it runs unchanged on a CPIC-drafted table where
haplotypes are sparse and `ref` is absent, and correctly finds nothing there.

**Dogfooding the check immediately killed the first version of it.** Grouping on rows rather than on
distinct haplotype *pairs* reported **595 phase ambiguities in the CYP2C19 example, which has none** —
one pair legitimately carries a row per drug and per `clinical_context`, so those share a signature by
construction and differ in conclusion by design. The messages named the same pair twice, which is what
gave it away. Kept as a regression test. Zero findings now across APOE, CYP2C19, SLCO1B1 and a
2,664-row CPIC clopidogrel draft; one on the module built to have one.

**Two side-defects, found by dogfooding and fixed.** `just-dna-enricher hint variant --rsid rs1799945`
answered *"not found in Ensembl, position remains unset"* for a variant live Ensembl serves at
6:26090951 — the surface had **no live coordinate route at all**, only the local snapshot, so an
advisory tool answered "no" where the pass it advises on answers a coordinate. Live Ensembl (V2→V1) now
runs on a cache miss, in `enrich()`'s own order, so a provisioned snapshot still costs no egress. And
the snapshot's own message stopped speaking for Ensembl: it says *"not in the injected Ensembl
snapshot"*, which is what it actually searched. Adding the live route then exposed a third: the
advisory rows were hard-coded to `source="snapshot"`, so a network answer claimed to come from a pinned
file, in the one field an author reads to judge reproducibility.

**What is left of RM28 shrank twice this round.** RM29 moved two of the three cofactor classes into
columns, leaving only ancestry genuinely injected; this closes the cis/trans motivation. The residue is
what APOE already named — pairing across *subjects*, and economy ("any two pathogenic variants in
trans" over 300 of them is ~45,000 pairs, expressible and unwritable) — plus open-world negation, which
is not an operator problem. Still parked, on a smaller case than before.

## 2026-08-03 — 0.5.1: RM29 cofactors, and a refusal dissolved rather than resolved

Three optional columns carrying single-subject cofactors with **no predicate language at all** —
because a row's columns already conjoin, which is the whole reason RM29 was ever separable from RM28.
Taken now because the digest window is still open: new columns on an existing parquet move every
module's digest, and 0.5 is unpublished. Nothing in the repo pins a digest, so there was nothing to
re-baseline.

**(a) `VariantRow.quality_from` + `min_quality`** — "assert this only where the call is at least this
good". `requires_callable`/`callable_from` ask whether the position was *seen*; this asks whether what
was seen is good enough to act on. Two columns rather than one expression: a pointer at the VCF
confidence field plus an inclusive numeric floor, so there is no grammar to specify, no evaluator to
write and nothing to sandbox (P1). `quality_from` joined the *existing* shared pointer validator on
`AuthoredModel` beside `source_field` and `callable_from` — three columns, one grammar, not a third
private rule.

**Both-or-neither**, enforced by a model validator. Half a floor is worse than no floor: a bound with
no field does not say what must clear it, a field with no bound is no threshold at all, and either
alone reads as a configured gate. A consumer would have to guess the missing half, and every guess is
a clinical policy the module did not write. An absent floor materializes as **null, never `0.0`** — a
zero floor is a gate everything clears, which is a different statement from "no gate". This is still
not the dropped `caller`/`caller_version` names: those recorded which tool made a call (consumer-side
measurement provenance); this is an applicability bound the annotation itself carries, the same kind of
thing a `MeasureBinRow` bound states, and inclusive for the same reason.

**(b) `DiplotypeRow.clinical_context`**, in `_TABLE_DUPE_KEYS` — which **dissolves** the
`draft --population` refusal built two entries below rather than resolving it. That refusal was
correct given the schema at the time: CPIC scopes a gene/drug recommendation to a setting, the
settings disagree, and with nowhere to record which was which, drafting all of them collided on the
duplicate-row key while drafting one asserted a clinical setting nobody chose. The column removes the
dilemma. Every setting is a distinct row and the **consumer** selects — which indication a patient is
being treated for is knowable at query time, not at authoring time, so the consumer is the right owner.

Dogfooded live rather than argued: `draft --gene CYP2C19 --drug clopidogrel` now writes 1,998 rows
across `CVI ACS PCI`, `CVI non-ACS non-PCI` and `NVI`, compiles clean, and the disagreement the
refusal was protecting is visible in the data — `*2/*2` Poor Metabolizer is `strong` in the first and
`moderate` in the other two, with different prescribing text for `NVI`. `--population` survives as a
filter; an unknown value is still an error, because drafting nothing on a typo would look like "CPIC
has no recommendations here". A test demonstrates the collision on the buggy shape (strip the column,
the same three CPIC rows are rejected as duplicates) rather than asserting it.

**Not named `population`, and that was a probe rather than a preference.** `FrequencyRow.population`
is an ancestry group with its own validated vocabulary. CPIC's live `recommendation` table (2,115
rows, 2026-08-03) turns out to carry indication (`CVI ACS PCI`, `NVI`), age band (`pediatrics`,
`adults`, `child >40kg_adult`), prior-treatment status (`PHT naive`, `CBZ use >3mos`, `OXC naive`) and
dose band (`<= 1g per day`), with `general` on 1,912 of them — no sense of ancestry anywhere. One name
for two axes across two tables is the P5 mistake, and it would have spent the name ancestry will want
on `DiplotypeRow` later. Open rather than a closed vocabulary, since CPIC's own set is open-ended and
DPWG/CPNDS scope differently; whitespace-stripped on load, because three of CPIC's sixteen values ship
a trailing space and the column is part of the key.

## 2026-08-03 — 0.5.1: the ACMG SF cross-check, and what a "simple scrape" actually cost

`VariantRow.acmg_sf` has been materialized into `weights.parquet` since 0.4 and checked against
nothing — assertable and unfalsifiable. It now has a checker: `enricher/acmg.py` and
`just-dna-enricher check-acmg`.

**Re-probed first, because the deferral was conditional on a data file appearing.** It has not.
ClinGen's FTP publishes gene-curation, region-curation, dosage and recurrent-CNV lists and **no
secondary-findings list**; ClinVar's own FTP tree carries no ACMG flag at all
(`gene_condition_source_id`, 13,478 rows, zero mentions). NCBI's adaptation of ACMG Table 1 at
`/clinvar/docs/acmg/` remains the only machine-reachable form of SF v3.2, as HTML. So the roadmap's
second branch — accept the guarded scrape — was taken.

**The deferral's own worry was right, and understated.** It described a "91-row HTML table". It is 94
gene-condition rows over **81 genes**, and the obvious `<tr>` split returns **78 genes, silently**: two
rows open with a bare `<td>` after the previous `</tr>` and have no `<tr>` of their own, four leave a
`<td>` unclosed with a stray trailing `</td>`, and the gene cell links through three different URL
shapes (`/gtr/genes/324`, `/gtr/genes/4089/`, `/gene/3949`). The three genes the naive split drops are
`TP53`, `COL3A1` and `TPM1` — so the predicted failure mode, a short list making correctly authored
`acmg_sf=true` rows look wrong, would have opened with the most recognizable secondary-findings gene
there is. A test reproduces the naive parse on the real page and asserts exactly which three it loses,
so the guard is not cargo-culted.

The parse therefore counts **cells**, not rows, behind five guards: the page must declare its version,
one table must carry all four expected headers, the `<td>` count must divide exactly by four, every
four-cell group must yield **exactly one** gene link, and a floor of distinct genes must survive. None
hard-codes 81 — that would be the hand-transcribed list this avoids, stale the day v3.3 lands.

**Two things the page holds that a first pass would have flattened.** A row is a gene–*condition* pair
(`TRDN` appears twice), and a single cell can carry several MIMs and several MedGen concepts —
`SDHB` names MIM 115310 *and* 171300 against `C1861848, C0031511`, linking to a MedGen **search**
rather than a concept, so the href has no id in it at all. Both are tuples now.

**Verdicts are the house tri-state.** `agree`/`blank` silent, `not_listed`/`denied` findings (warn in
`best_effort`, refuse in `strict` — list membership is a published fact, not a clinical judgement, so
unlike the `clin_sig` check there is no reason to hold it at a warning), `unstated` a **note** because
a blank cell means "not stated", and `unchecked` for a row naming no gene and for all of `--offline`.

**Dogfooding the CLI changed the output shape.** Run against `reference_examples/hfe_hemochromatosis`
— 13 variants in one gene — the per-row report printed the same 220-character sentence 13 times. Every
verdict here is about a *gene*, so `AcmgReport.by_gene` groups them; the per-row verdicts stay on the
report. Same rule CPIC taught with ~600 identical lines for CYP2C19.

**ACMG's list is not purely gene-level, and the column is.** The `HFE` entry reads *"Hereditary
hemochromatosis (c.845G>A; p.C282Y homozygotes only)"*. `acmg_sf` is documented as a gene-level fact,
so that is what is compared, and the `denied` message quotes the entry and tells an author to leave the
cell **blank** rather than `false` for a variant in a listed gene that is not itself reportable.
Reading the column as per-variant reportability would make the format decide disclosure policy.

**No `SourceRow`, deliberately** — the exception to "a pass consulting a source writes one". Nothing
lands in the module: this asks a registry about a cell a human already authored, which is
`check-identifiers`' shape, not `dosage`'s. The corollary runs the other way: `acmg_sf` joins
`hints.REDUNDANCY_BEARING`, so no lookup may fill it.

## 2026-08-03 — 0.5.1: delegated insertion, partial rows, and RM26's last provider

Two mechanisms and the provider they unblock. The short version: **the tool decides where a row goes
and what it can honestly state; it never decides what a human must.**

**Delegated insertion.** Drafting appended at the end, and the reason recorded for that led with
`artifact.digest`. Probing killed the argument: a pure row reorder does move the digest, but
`content_signature` is unchanged (it is order-independent by construction), the compile → reverse →
compile fixed point still holds, duplicate keys are rejected outright so order can disambiguate
nothing, and **nothing in the codebase reads the append-only prefix property** — one test asserts it.
The decisive point is that an author reordering rows in their editor is already legal and already
moves the digest, so "it moves the digest" cannot be grounds for refusing a tool the same move. Nor
is mid-flight digest stability worth much: the digest is consumed at exactly one moment, publish, and
during authoring every edit changes it anyway.

What stays refused is *arbitrary* insertion — an `at=N` index buys nothing a text editor does not.
What shipped is `append_rows(..., group_by=…)`: a new row joins the block sharing its group columns,
or goes to the end. One writer, no index arithmetic, and the never-rewrite-a-cell rule intact — a
test asserts every shifted row is byte-identical afterwards, and `DraftReport.shifted` names each.
A `sort`/`canonicalize` command remains a hard no: it moves every row for no authoring gain.

**Partial rows.** `draft.PartialRow` + `append_partial_rows`, for a source that publishes most of a
row. The cells it has are written; the rest carry `TEMPLATE_PLACEHOLDER`, which no mode compiles.
Two details carry the design. The stubbed columns are validated **by omission** — the row is built
without them and errors located on them are discarded — which avoids a per-column table of dummy
values, i.e. the hand-kept list this module keeps abolishing. And sameness is decided by `match_on`
rather than the natural key, because for the case that forced this the key runs *through* the stub:
once a human fills the genotype, a re-draft must recognise the row and report `already_present`
instead of appending the stub again.

**RM26's last provider — ClinVar → `variants.csv`** (`clinvar_draft.draft_gene_panel`,
`just-dna-enricher draft-panel`). This partially dissolves RM4: a gene panel becomes authorable with
no compile-time reference materialization and no reference in the compile path. It was blocked on a
real problem, not effort: `VariantRow.genotype` is required and ClinVar publishes **alleles, not
genotypes**. Whether carrying a pathogenic allele once is informative — carrier, affected, neither —
follows from the condition's inheritance mode, which ClinVar does not state; writing `A/G` because
the alt is `G` would be a clinical claim the source never made.
`reference_examples/pathogenic_clinvar/` is a human having made that call by hand, per row. So the
provider states what is published and stubs the rest, and the panel cannot compile until someone has
decided. Rows land in their gene's block, which is what makes this usable on a 2,500-row BRCA1 draft
rather than merely possible.

Identity is filled **whole or not at all** — the rsID, else the complete coordinate. A lone `alts` on
a position-only row makes `derive_variant_key` mint a VRS `ga4gh:VA.…` id instead of
`chrom:start:ref`, so a partial coordinate silently changes which variant the row *is*. It fills
`gene`, `clin_sig`, `clinvar`, the folded `pathogenic`/`benign` booleans, `state` (a fold of
ClinVar's own call, absent when the call does not map), `phenotype` from `condition` verbatim, and a
transcribed `conclusion`. It fills no `weight`, `direction` or effect statistic (ClinVar publishes
none), no `trait_efo_id` (its `condition` is free text and MedGen, not EFO), no `acmg_sf`, and no
`curator`/`method` (the `defaults:` block owns those). `min_review_stars` defaults to 2, because a
panel that silently mixes a 0-star submission with a 3-star expert-panel review is worse than one
that says which floor it drew from. `licensing.CLINVAR_TERMS` is new — public domain, and recorded
anyway, because attribution is asked for even where permission is not required.

**Then the provider was dogfooded against a real panel, and it did not survive contact.** Authoring
`reference_examples/hfe_hemochromatosis/` — scaffold → draft-panel → curate → enrich → compile —
produced four findings, each fixed in the product rather than worked around in the example:

* **An rsID can name two alleles.** ClinVar lists `rs773443949` at 6:26091590 as both `G>A` and
  `G>T`. Both drafted to the same rsid-only row, the second was reported `already_present`, and a
  real allele vanished. Such rsIDs now take the **coordinate** identity, and `alts` joined `match_on`
  — without it the two coordinate rows collapsed in exactly the same way.
* **A drafted panel could not compile at all.** `studies.csv` is mandatory and the ClinVar VCF
  carries no PMIDs, so the provider produced a module needing evidence nothing could supply. ClinVar
  publishes its literature links separately, so `clinvar_build` gained `download_var_citations` /
  `build_citations` and the CLI gained `clinvar citations` (3.9M PubMed links); `clinvar.citations_for`
  reads them and `draft-panel` now drafts `studies.csv` alongside. Capped at three per variant —
  `rs1800562` alone carries 84 — with the dropped count always reported.
* **The citations table broke the snapshot view**, because it landed in `data/` and
  `clinvar._connect` globs `data/*.parquet`: a two-column file unioned with the 17-column variant
  parquet and every query failed. It lives in a `citations/` sibling now, with the reason recorded
  where the path is defined.
* **A study must carry the identity its variant row got.** The study rows for the multi-allelic
  variant were still keyed by rsID while the variant had moved to a coordinate, so they referenced
  nothing — caught by the compiler's own orphan warning.

Two smaller gaps the same run exposed: `hint variant` had no way to point at a specific snapshot
(the shipped Ensembl cache is a popular-rsID slice and has none of these rare variants), so it gained
`--ensembl-cache`/`--clinvar-cache`; and `ClinVarDraftResult.added` became ambiguous once two tables
were written, so `added_for(csv_name)` answers the question callers actually have.

The example itself is the argument for the design: `rs1800562` appears as `A/A` (risk) and `A/G`
(carrier) — same variant, same ClinVar call, opposite clinical meaning, because `clin_sig` describes
the allele and `state`/`direction` describe the finding for a genotype. A provider deriving a
genotype from an alt would have been wrong half the time.

**The PGx side, dogfooded the same way — and it failed differently, which is the interesting part.**
Authoring `reference_examples/cyp2c19_star_alleles/` from CPIC produced a module that was *complete*:
811 rows, no stubs, valid immediately. Where ClinVar left a hole for a human, CPIC left none — so the
curator's job became deciding what to **remove**, and the findings were about what nobody checked.

* **`draft --gene CYP2C9` crashed** with a raw pydantic traceback while `--gene CYP2C19` worked. The
  skip guard checked "no rsID *and* no position", but `HaplotypeRow` needs an rsID **or** chrom AND
  start — and CPIC publishes no chromosome at all (`sequence_location` has genesymbol/dbsnpid/
  position and no chromosome column, probed 2026-08-03). 18 CYP2C9 defining variants have a position
  and no rsID, plus 14 in TPMT and 4 in NUDT15; CYP2C19 has none, which is why it looked fine. The
  guard is now derived from the model's own rule, and a test asserts the two agree case by case —
  which promptly found a **second** bug: `_haplotype_rows` never passed `chrom` through at all.
* **Nothing recorded CPIC as a source.** The provider checked the licence before fetching and then
  wrote no `SourceRow`, so a module built entirely from CC BY-SA **no-sale** data carried no
  `sources.csv` and the compile gate had nothing to key on. That is the `clingen.py` bug living in
  the newest provider, and it is the one place it matters most. Fixed via `merge_sources_file`;
  a test strips the declaration and asserts the compile then refuses.
* **`n/a` was diagnosed as "an inequality rather than a number"**, which is the wrong reading — CPIC
  means *it did not score this pair*, an absence, not a bound. And it was emitted once per row: ~600
  identical lines for CYP2C19, 2,184 for CYP2C9, burying every other finding in the run. Now
  classified into unscored-vs-bounded and aggregated, with the total and a few examples.
* **A new compiler check, from a real coherence gap.** CPIC pairs alleles whose defining variants it
  does not publish in a holdable form, so `*36`, `*37` and `*42` arrived used across 71 diplotype
  rows — two declared `no_function` — and defined by nothing. A caller can never emit an allele
  nothing defines, so those rows are dead, and the compiler said `valid`.
  `_cross_validate_haplotype_definitions` now warns (Class 2: two independently-authored tables that
  must agree), and only when `haplotypes.csv` is present — a module leaning on an external caller's
  definitions is legitimate, and faulting it would be the orphan-sidecar mistake.

The example carries the curation that warning prompted (666 → 595 diplotypes) and validates clean.
Its drug columns are deliberately empty: CPIC's prescribing recommendations live in a resource the
provider does not read, so filling them would mean inventing them, and the module is named for star
alleles rather than for clopidogrel for the same reason.

**CPIC prescribing recommendations — the increment that stops the module being an infodump.**
`draft --gene CYP2C19 --drug clopidogrel --population "CVI ACS PCI"` now adds drug-carrying
`DiplotypeRow`s beside the phenotype rows. They coexist rather than replace: `_TABLE_DUPE_KEYS` keys
on `drug`, and the two answer different questions — what phenotype a pair is, and what CPIC advises
about it for a drug. The `conclusion` is CPIC's own two halves transcribed, implication then
recommendation, and `classification` maps onto `VALID_RECOMMENDATION_STRENGTH` (`n/a` maps to nothing:
CPIC did not classify, which is an empty cell, not a member).

`evidence_level` stays empty and that is deliberate — PharmGKB grades how well established an
association is, CPIC grades how firmly a guideline says to act, and one column for both would repeat
the `state`-overloading mistake.

**`--population` is required rather than convenient**, and it is the round's sharpest finding. CPIC
scopes clopidogrel to three clinical contexts and **they disagree**: the same Poor Metabolizer
diplotype is `strong` in `CVI ACS PCI` and `moderate` in `NVI`. `DiplotypeRow` has no population
column, so drafting all three collides on the dedup key and picking one silently would assert a
clinical context nobody chose. With several available and none named, the provider drafts nothing and
lists them.

**Design thread recorded, deliberately unbuilt — meta-conclusions (RM28,
[PROPOSAL_0_5 § G3](PROPOSAL_0_5.md)).** A module is rarely one axis, and what a curator wants is to
pair them: a CVD module that also says something about warfarin *given* what the rest of it found.
The format cannot state that — every table keys on one subject. Principle 1 has sanctioned the
mechanism since 0.1 (a non-Turing-complete predicate) and nothing had demanded it. The starter shape
commits to the **carrier** — an optional table that **never blocks**, since an unresolvable reference
warns — and keeps the **grammar** minimal, because the table is the safe commitment and the grammar
is where drift happens.

Three things sharpened it, and one of them corrected it:

* **Phase corrects the grammar.** The case that most justifies the table is compound heterozygosity:
  two pathogenic alleles **in trans** leave no functional copy (affected), **in cis** leave one
  (carrier) — same rows, same genotypes, opposite conclusion. `rs1 AND rs2` is true of both, so a
  pure-conjunction starter grammar could not express the very example that motivates it. The minimum
  is conjunction **plus one relational notion**, in-cis/in-trans.
* **Cofactors the module must never hold.** Detected ancestry, clinical context and call quality are
  all supplied by the consumer at query time, like the measurement already is. The tempting shortcut
  — derive ancestry from the gnomAD frequencies a module already carries — does not work, because
  real population models are panel-scale and a module curated for disease association is precisely
  the wrong panel.
* **Call quality is the third class**, and reuses the `source_field`/`callable_from` declarative-
  pointer idiom. It is *not* the dropped `caller`/`caller_version` mistake: those recorded which tool
  made a call (consumer-side provenance), while a `QUAL` floor is the module stating where its own
  conclusion stops being reliable.

**And the scoping cut that shrank it: columns are already a conjunction.** A row carrying
`genotype` + `requires_callable` + a quality floor already means "all of these", with no grammar —
and `HeteroplasmyRow.tissue` has been a cofactor-as-column since 0.4, with bins explicitly
tissue-conditional and the consumer selecting the row matching what it measured. So the line is not
cofactor-vs-not, it is **arity**: a condition about *one* subject is a column, and only a relation
*between* subjects needs the table. That reclassifies two of the three — a SNP quality floor and
CPIC's clinical population are columns (recorded as **RM29**, digest-moving so major-only once 0.5
ships; the population column would dissolve the `--population` refusal built above) — and leaves the
predicate with relations and essentially nothing else. The most useful thing said about this design
was that the table already had a conjunction and nobody had called it one.

The safety rule is the same in all three and is the reason the table can never block: a **missing**
cofactor withholds the conclusion rather than resolving it either way — the discipline `unresolved`
already applies to a missing measurement and `requires_callable` to an uncalled absence. It waits on
a corpus to generalize from (~70% built; nutrigenomics and supplements do not exist yet), and it
blocks the "shy module" signal, which cannot mean anything until a module can carry something a
source could not have produced.

**And then the design was probed instead of argued — `reference_examples/apoe_epsilon/`.** APOE is
the sharpest possible test of the meta-conclusion case: its ε haplotypes are defined by *two* SNPs
together, and Principle 1's escape-hatch example is literally the ε4 condition
(`rs429358==C AND rs7412==C`). The probe **weakened the case for the table**, which is the more
useful outcome. APOE builds with bricks that shipped in 0.4 and no predicate at all: `HaplotypeRow`
is a junction table, so a two-SNP haplotype is two rows, and `diplotypes.csv` carries the conclusion.
Same-strand co-location is what a haplotype table already *is* — the predicate would have restated it
less legibly, and the cis/trans motivation evaporates for the same-gene case that was its strongest
example.

What survives is narrower and now labelled honestly: pairing across **subjects** (an APOE diplotype
with a cardiovascular variant and a drug row — no table keys on more than one subject), and compound
heterozygosity without enumerating every pair, which is an argument from *economy* rather than from
expressiveness. RM28 stays parked, with better reasons than it had.

The probe found a real defect on the way (**RM30**): `AlleleFunctionRow.allele` enforces a leading
`*` while `HaplotypeRow.haplotype_name` and `DiplotypeRow.haplotype_a`/`_b` accept any string, so
`e4` is legal in two of the three PGx tables and illegal in the third — and the new cross-table check
would report `*4` against `e4` as used-but-undefined, a mismatch the author has no legal way to fix.
APOE carries no allele-function table (an ε allele has no CPIC activity value), which is honest for
APOE and not a fix.

**RM30 fixed in the same round: one rule for a haplotype name.** The asymmetry was real and
narrow — `STAR_ALLELE_PATTERN` had exactly one schema-side use, on `AlleleFunctionRow.allele`, while
`HaplotypeRow.haplotype_name` and `DiplotypeRow.haplotype_a`/`_b` had no validator at all. So one of
three tables imposed a star-allele convention on what the other two treated as a plain name, and the
0.5.1 cross-table check turned the workaround into a dead end: `*4` in one table and `e4` in another
reports "used but not defined", and no spelling satisfies both. All three now share
`validate_haplotype_name` — non-empty, no whitespace, nothing else, because **a name is an identity,
not a grammar**. `STAR_ALLELE_PATTERN` stays exported and `pgx_draft` still checks it at four sites,
so the CPIC provider is exactly as strict as before; only the schema stopped enforcing one gene
family's convention on all of them. Two tests that pinned the old behaviour were updated — they were
pinning the defect.

916 passed, 6 skipped. Reference examples still compile to byte-identical digests.

## 2026-08-03 — 0.5.0: the authoring surface — options as data, stubs that cannot compile, hints that never write

The 0.5 drafting helper shipped a mechanism with one provider and one accessory (`blank_template`, a
bare header). This round builds the surface around it, along one line: **templating and lookup are
built; filling a cell for the author is not.** The second half is a mechanical rule rather than a
preference, and it is worth stating once because it decides the shape of everything below.

COMPILER.md's Class 2 — validate-by-redundancy — is "where most real authoring bugs are caught", and
every check in it compares two **independently-authored** things. Fill `chrom`/`start` from Ensembl
and the compiler's rsid↔coordinate check compares Ensembl with Ensembl; fill `doi` from PubMed and
`literature._doi_conflicts` compares PubMed with PubMed. It is worse than tautological: for an
rsid-only row `resolution._verify` never runs at all, so the row would move from *honestly
unverified* to *apparently verified* and the compile would report success. `literature` already
reasoned this way about one field — it asks Crossref about the **authored** DOI because the derived
one "exists by construction" — and `hints.REDUNDANCY_BEARING` now generalizes it to every cell.

**Two shipped bugs surfaced on the way**, both reproduced before being fixed:

* **`blank_template` emitted a header the compiler then refused.** `MeasureBinRow.measure_kind` and
  `unresolved` have defaults but are not `Optional`, and `_load_csv_rows` turns an empty cell into
  `None` *and keeps the key* — so the model received `None`, never its default. `required_fields`
  never named them (they are not required), so an author who filled exactly what they were told to
  fill got `Input should be a valid string` about a column nobody had mentioned. Requiredness has
  **three** shapes here, not two: `field_category` splits `required` / `defaulted` / `optional`, and
  `authoring_requirements` reports all three plus the identity groups.
* **`actionability` was advertised open while being enforced closed.** `_validate_actionability`
  calls `check_vocab`, but the authoring reference filed it under `open_recommended`, so a tool
  offering a novel value got a rejection it had been told to expect to work. A drift in *closedness*
  rather than in membership — which is why the new marker carries that flag and not just the members.
  An existing test was pinning the wrong side.

**Schema — the vocabulary binding.** `base.vocabulary(name, options, closed=)` plus
`field_vocabularies()`, mirroring `COMPILER_MANAGED`. The marker carries the **members**, not a name
to look up: a registry in `vocab` cannot import `pgx` (the cycle `base`'s dependency note exists to
avoid), and a registry anywhere else is a second hand-kept list, which is the failure being fixed.
`SHARED_VOCABULARIES` holds the four the base class validates, so the set a tool offers an author is
the same object the validator rejects against. `authoring_reference()["vocabularies"]` is now
generated from the markers — **13 entries to 22**, picking up `recommendation_strength` and
`phenotype_category`, which 0.5 added and the hand-kept dict never learned about — and each field
carries its options inline. The guard tests discover the binding by **behaviour** (feed a non-member,
see whether it rejects), in both directions, so neither an unlisted vocabulary nor a marker for a
vocabulary nothing enforces can recur. Consumer note: `open_recommended.actionability_seed` is gone;
the same members are at `vocabularies.actionability`, where enforcement actually puts them.

**Schema — requiredness that is not field-local.** `AuthoredModel.REQUIRED_ANY_OF` declares "rsid, or
chrom+start" as data on the four models whose validators enforce it. `is_required()` cannot express
it, so every tool listing required columns had been telling authors a `variants.csv` row needs no
identifier. A `ClassVar` because the rule is a property of the model (`{chrom, start}` is one group
meaning "both together"), the same shape as `MeasureBinRow._KEY_FIELDS`; a test derives its cases
from the declaration and checks them against the real validator, so the two cannot diverge.

**Schema — a stub that cannot compile.** `vocab.TEMPLATE_PLACEHOLDER` (`<<REPLACE>>`) with a
recursive `mode="before"` guard on every authored row and on `module_spec.yaml`. Running before
coercion is the whole trick: an unreplaced stub in `start: int` is diagnosed as an unfilled template
naming the column and row, not as "Input should be a valid integer". Deliberately **not**
`MeasureBinRow.unresolved` — that sentinel means "no measurement at read time" and is designed to
*compile*, and two opposite lifecycles on one field is the overloaded-axis anti-pattern (P5). This
tightens validation: a module carrying the literal `<<REPLACE>>` in free text becomes invalid.
Recorded here rather than slipped in.

**Compiler — templating.** `stub_template` writes the placeholder where a human must decide, the
**default** where a column has one (the bug above), and blank elsewhere; a binning kind also gets its
mandatory `unresolved` companion row, so that contract is met as a template rather than as a compile
error about a row the author never wrote. It offers **one** identity group, not the union — the
groups are alternatives, and stubbing both would ask for two identities.

**Compiler — scaffolding.** `scaffold.py` creates `module_spec.yaml` plus stub tables. Refusal is
**file**-level here and **row**-level in `draft`, and the difference is derivable rather than
stipulated: you scaffold once (so nothing self-defuses) and a stub row has no natural key to merge on
— its key columns *are* the placeholder. Refusal is per file, not per run, or a module could never
gain a second table kind. `COMPANION_KINDS` is symmetric, and **both halves were found by the test
that pins it to the compiler's real rules**: `variants.csv` needs `studies.csv` ("grounding evidence
is mandatory") and `studies.csv` alone is "no recognized table".

**Compiler — hints.** `hints.py` takes CSV text and returns a report; it **writes nothing**, asserted
by hashing the directory rather than by review. Only `normalized` alterations are applied, and those
are changes the model already makes silently on load — `DiplotypeRow` swaps its haplotype pair, and
surfacing that before the author is surprised by it adds no external information. Redundancy-bearing
columns are explained once per report and never filled. Bin overlap and coverage gaps come from the
schema's own `validate_bins`; duplicate keys from the compiler's own `_TABLE_DUPE_KEYS`.

**Enricher — lookups.** `lookup.py` answers the questions an author actually has: an rsID's validity
(dbSNP is the oracle — Ensembl 400s on some merged ids), its coordinate list with ambiguity reported
**on demand** and never resolved for you, ref/alts, gnomAD populations with the frequency computed as
`ac/an` (the API exposes no `af`), ClinVar's own call, and citation existence with the DOI and PMC id
that arrive free in the same response. Every answer comes back as an `Alteration` with
`applied=False` and a `refusal`. Clients are injected and reused, because each owns a `PacingGate`
and a fresh one per question throws away the rate-limit state. Offline is a first-class answer:
`unchecked`, never `absent` — `None` is not `False` anywhere in the file.

**Enricher — RM26's second provider.** `clinpgx_draft.draft_pharm_variants` appends ClinPGx
annotations into `pharm_variants.csv`. The clean contrast to `pgx_draft`: every column the model
requires is published, so nothing is stubbed. One annotation naming several drugs (`drugs` is
`;`-joined) becomes one row per drug — they share an `annotation_id` and key distinctly, which is
what PharmGKB is actually saying. `CC` becomes `C/C`, and only for an unambiguous two-base call; a
star allele is routed to `diplotypes.csv` and a `del/del` is RM5, both skipped with a reason rather
than coerced. It writes its `SourceRow` through `licensing.merge_sources_file`, because a source that
is consulted and not recorded is one the module cannot account for.

**CLI.** `just-dna-compiler` gains `template`, `stub`, `requirements`, `scaffold`, `describe` and
`hint` — all offline, so they belong on the tier that owns the CSV shape; `template` had shipped only
on the enricher, which meant an author who installed just the compiler had the API and no command.
`just-dna-enricher` gains `hint variant|citation|trait|gene` and `draft-clinpgx`, and its `template`
now reports the never-leave-empty defaults too.

Also: `_write_table_csv` reads `authored_field_names` rather than `model_fields` — identical output
today, but it was the third place the authored surface is derived and the two before it both drifted.

870 passed, 6 skipped (from 792). All three reference examples compile to byte-identical
`artifact.digest` and `content_signature` against a clean HEAD worktree, so the whole batch is
digest-neutral; the compile → reverse → recompile fixed point is proven for a module built entirely
by `scaffold` plus fill.

## 2026-08-02 — 0.5.0: the pre-cut batch — columns that need the window, tooling that doesn't

A survey of five candidate annotation-source groups (splice predictors, ClinGen/GenCC/ACMG SF,
PharmCAT+CPIC, HPO/MONDO/Orphanet, missense predictors) split cleanly along one line, and that line
set this batch's scope. The groundwork each group needs is either a **new table** or a **new column**,
and `integrity.file_entries` skips missing files — so a new optional table never moves the digest of a
module that does not carry it (additive any time), while a new column moves every module's digest
(major-only once 0.5 ships). The columns therefore landed now; the tables are roadmapped (RM23–RM27).

**`StudyRow` gets a queryable p-value.** `p_value` is a free-form string, so nothing could sort or
threshold it; `p_value_num` is the same number typed, constrained to (0, 1]. `neg_log10_p` is
**derived** into `studies.parquet` — the `allele_frequency` = AC/AN split, applied again — because it
is the scale a consumer filters and plots on, while authoring it would make the human compute a
logarithm to write a row down.

*Considered and rejected: a mantissa/exponent pair* (the GWAS Catalog's own representation). It
survives p-values past what float64 holds — subnormal below ~1e-308, flatly `0.0` below ~5e-324 — but
that range is a problem for a catalogue of millions of associations, not for a curated module citing
tens of studies. Two columns and a both-or-neither rule is a real cost paid by every author to insure
against a case none of them will meet. A p-value that small reads as *indefinite* rather than as zero:
`parse_p_value` returns `None` for it, since the column could not hold it either and reporting a
mismatch would be a finding about float64 rather than about the module.

A compiler check compares the number against the verbatim string (relative, at 1%, so a rounding is
not a contradiction) and reports a disagreement — warning, error in `strict` — skipping in silence any
cell that does not denote one definite value (`"<0.001"`, `"NS"`, `"5e-8 (adjusted)"`).

**`VariantRow.callable_from`** (RM6's second half) — `requires_callable` says a negative must be
proven, this says where the proof lives. It reuses `source_field`'s pointer grammar, which moved to
`vocab.validate_field_token` and onto `AuthoredModel` now that two models share it. `callable_from`
leaves the reserved namespace: a built column must not also be reserved, or the author cannot write it.

**`DiplotypeRow.recommendation_strength`** — CPIC grades how firmly to act; PharmGKB's `evidence_level`
grades how well established the association is. Different bodies, different questions, and a
well-evidenced association routinely carries an optional action, so folding them into one column would
be the `state`-overloading mistake again. Members are CPIC's own five, lowercased; its `n/a` is
deliberately not a member (that is CPIC declining to classify, which is an empty cell).

**ClinGen dosage sensitivity** — `haploinsufficiency` / `triplosensitivity` on `GeneMetricsRow` (gene-
keyed, so columns on the existing sidecar rather than a new table), plus `clingen.py` and
`just-dna-enricher dosage` to fill them. **Ratings are stored as terms, not ClinGen's numeric codes**,
which is a deliberate departure from the usual keep-it-verbatim rule: probing the live file showed the
codes are an ordinal-looking scale that is not ordinal — `30` means "autosomal recessive" and `40`
means "dosage sensitivity unlikely", so sorting raw codes ranks `40` above `3` (sufficient evidence),
the exact inversion of the meaning. Two more shapes found by reading the file rather than its docs: a
literal `"Not yet evaluated"` in 210 of 1,520 rows (an absence, and what makes `int(cell)` crash), and
a six-line comment block whose last line is the header. ClinGen is CC0 — the one annotation-layer
source here a module can be **sold** on, which `sources.csv` now records rather than leaving implied.
The gnomAD pass's `existing` map was re-keyed on `(gene, dataset)`: keyed on the gene alone, a ClinGen
row looked like that pass's own work and suppressed the constraint fetch.

**`SourceRow.redistribution`** — a third tri-state axis, recorded and summarized, not gated. An
academic-use-only source (OMIM, dbNSFP) permits neither sale nor redistribution, while CC BY-NC forbids
sale and expressly allows sharing; recording the first as merely non-commercial understates it. All five
current sources permit redistribution, so this is the window's cheap insurance. The **gate** is
deliberately deferred (RM27): a distribution right is not a *use*, so `declared_use` is the wrong axis
to resolve it against, and that needs design rather than a branch.

**RM17: `module.version` is enforced, coercing.** `v2` → `2.0.0`, reported once. Coerce rather than
reject because the pre-0.4 corpus is full of `v2`, and rejecting would break those modules to gain a
stricter spelling of an advisory field. One behaviour change worth noting for consumers: a non-SemVer
version used to be dropped from `Identity.version` entirely, so such a module published with no version
at all; it now reaches the manifest coerced.

**A generic drafting helper — `just_dna_compiler.draft` + `just-dna-enricher draft`.** Started as a
PGx scaffold and generalized, because the mechanism (append rows into an authored CSV without
clobbering) is table-kind-agnostic and useful to a human on its own. The compiler owns the pure half
(it already writes authored CSVs in `reverse_module`, and already defines what makes two rows the same
row); the enricher owns the network providers, of which CPIC is the first.

*Append-only at **row** granularity, never file granularity* — a file-level "refuse if it exists" rule
self-defuses after the first gene and makes a multi-gene module unbuildable. A row whose natural key is
new is appended; a row whose key exists is reported (`already_present`, or `differs` with the cells
named) and **never rewritten**. Dedup keys on the compiler's own `_TABLE_DUPE_KEYS`, so an append
cannot produce a row the compiler would then reject as a duplicate; rows go at the end, because
authored row order is preserved through compile → reverse and parquet bytes depend on it. That word —
*mutate* — is the line between this and the parked enricher-co-authoring item: appending leaves
`content_signature` a function of the authored bytes, editing a cell a human wrote would not.
`just-dna-enricher template <kind>` emits a header from the live models for starting a table by hand.

**`just-dna-compiler verify` and `sign`.** `verify_manifest` and `sign_digest` were fully built and
reachable from no command line — `just-dna-format` ships no CLI (Typer would breach its
pydantic-plus-cryptography floor), so the README's "verify-only client" path meant writing Python, and
nothing in the workspace could sign a module.

**Orphanet joins the trait-currency check**, and exposed a latent trap while doing it: the IRI was
composed as `stem + PREFIX + "_" + local`, but `ORPHA:558` is a term at `…/ORDO/Orphanet_558`. The
composed `ORPHA_558` returns HTTP 200 with zero terms — indistinguishable from "this id does not
exist" — so the bug would have surfaced as a false finding about the module. `_ONTOLOGY_IRI` now stores
the full IRI prefix instead of assembling it.

**`reference_examples/htt_repeat_expansion/`** — the binning family's first real compiled module
(§4–§8 of REFERENCE_EXAMPLES.md were sketches). No variants, no studies, no coordinates: the locus is
named by `(gene, repeat_unit)`, `source_field=REPCN` binds it to an ExpansionHunter VCF, and the
mandatory `unresolved` sentinel is the row that stops an unspanned expansion reading as "normal".

**The ACMG SF check was probed and deferred, not skipped.** `acmg_sf` is validated against nothing and
deserves a check, but the probe found no machine-readable list: NCBI carries SF v3.2 as an HTML table
and ClinGen's FTP publishes no secondary-findings file. A guarded scrape is possible and is recorded in
0.5.1 rather than rushed — a hand-transcribed gene list in the enricher is the un-injected-reference
mistake RM21 already taught.

## 2026-08-02 — 0.5.0: the ClinPGx snapshot, and a PGx reference example

**`clinpgx_build` + pass 6.** `clinicalAnnotations.zip` → a parquet snapshot the cross-check reads
offline, following the ClinVar builder. The snapshot's grain is (annotation, genotype), joining the
summary table to its per-genotype child. `CREATED_<date>.txt` is the release id — ClinPGx publishes
no version and does not refresh its archives in lockstep.

The builder extracts the `LICENSE.txt` ClinPGx ships **inside the archive** and records its sha256 in
`release.json`; the pass stamps that hash onto the emitted `SourceRow`. That is the licensing design's
payoff: the recorded terms are provably the ones shipped with the recorded data, not a lookup that was
true once. Pass 6 is offline-capable but still honours the declared-use gate — the terms were accepted
when the snapshot was built, and using it is the same act. Severity follows the mode ladder, unlike
the allele-function check: an evidence level is ClinPGx's own metadata, so a difference means the
module is stale rather than that two panels disagree.

**Two collision bugs, both found by dogfooding real data.**

*Schema.* `(variant_key, drug, genotype)` is still not a key. One variant and one drug carry several
*distinct* annotations — rs4149056 + simvastatin is Metabolism/PK at 1A, Efficacy at 3 **and**
Toxicity at 1A, each with its own three genotypes. 1,199 of 17,380 triples in the release map to more
than one annotation: 839 separated by phenotype category, and 283 by neither category nor level.
`PharmVariantRow` therefore gains `phenotype_category` (closed vocabulary `VALID_PHENOTYPE_CATEGORIES`,
multi-valued, accepting ClinPGx's own `Metabolism/PK` spelling) and `annotation_id` (a source
accession as identity, the same shape as `PgsRow.pgs_id`). The key is now
`(variant_key, drug, genotype, phenotype_category, annotation_id)`.

*The checker had the same bug.* Its first implementation indexed the snapshot on `(rsid, drug,
genotype)` and compared each authored row against whichever annotation was indexed first — which
reported all three of the new reference example's correctly-authored levels as stale. The lookup is
now `annotation_id` → `(rsid, drug, genotype, category)` → the bare triple, and an ambiguous bare
triple is reported as **unchecked** rather than compared against an arbitrary candidate.

**`reference_examples/pgx_slco1b1_simvastatin/`.** The PGx reference example: nine rows transcribed
from the three real ClinPGx annotations, no `variants.csv`, resolution driven by
`pharm_variants.csv`, and a `sources.csv` recording that the module is not sellable. Its README walks
the four commands that rebuild it.

## 2026-08-02 — 0.5.0: data-source licensing as data, and the PGx cross-check

**`sources.csv` — the fifth fact table.** One row per (data source, layer), recording what a module
was built from and on what terms: `license`, `license_url`, `license_sha256`, `attribution`, `notice`,
tri-state `share_alike`/`commercial_use`, and the acquirer's `declared_use`. Compiled to
`sources.parquet`, fact-hashed by `integrity.source_signature`, summarized into `manifest.sources`.
`module_spec.yaml` also gains an optional `license:` (advisory, registry-overridable, like `version`).

The motivation is that every pharmacogenomics upstream is copyleft **and none is sellable**: ClinPGx,
CPIC and PharmVar are each CC BY-SA 4.0 *plus* a separate contractual bar on sale. A bare "CC BY-SA"
line is not permission to sell. `api.pharmgkb.org` was retired 2026-07-20 (successor
`api.clinpgx.org`), and CPIC is inside the ClinPGx merger — `cpicpgx.org/license/` 302-redirects to the
ClinPGx policy — so switching sources does not escape the terms.

**The compile gate is data-driven, not flag-driven.** The compiler refuses when an annotation-layer
source forbids sale and the module records no matching declaration. Keying it on a `--non-commercial`
CLI flag would have broken Principle 7: `reverse_module` rebuilds `module_spec.yaml` from parquet alone
and could never re-emit a flag, so `compile → reverse → compile` would refuse on the third step.
`sources.csv` round-trips, so the declaration travels with the module and the cycle reproduces. The
refusal fires in **both** modes — `strict` means "reproducible artifact", which is a different axis.

Three deliberate non-obvious behaviours, all pinned by tests: **only the `annotation` layer taints** (a
source used purely to look up a coordinate contributed a fact Ensembl reports identically, so marking
it viral would be a false positive); **most-restrictive-wins module-wide** (a permissive source cannot
launder a restricted one); and **`None` is not `False`** — a source whose terms could not be
established has not been shown to permit anything, so the verdict is *undetermined*, never *permitted*.

The compiler holds **no** source→licence map: that would give it a source convention (Principle 2) and
an un-injected reference, and it would go stale — both halves of one did inside this release. The
licence travels as data, read by the enricher from the bytes it downloaded and pinned by
`license_sha256`.

**Enricher pass 5 (`pgx.py`, `licensing.py`, `pharmvar.py`, `cpic.py`).** Cross-checks authored
`allele_function.csv` against PharmVar and CPIC and writes `sources.csv`. `--use` (`unstated` |
`non-commercial` | `commercial`) is a third orthogonal axis, never folded into `mode`: a source that
forbids sale is *skipped* when nothing is declared and *refuses* when `commercial` is. The refusal
lives at acquisition, because that is when terms are accepted and because refusing there means nothing
is fetched. The allele-function check **warns in both modes**, joining the ClinVar `clin_sig`
exception — PharmVar and CPIC are different expert panels that genuinely disagree, and failing would
make the format arbitrate between its own authorities.

Generation stays manual: the PGx tables are *authored* `_TABLE_KINDS`, not fact sidecars, so a network
pass writing them would blur the authored/derived line 0.5 drew. The automatic pass only reads.

Gotchas recorded: PharmVar needs an **`Api-Key`** header (not `X-API-KEY`; every wrong spelling returns
the same 401) at **2 rps**, and its key is personal so it never enters a module or fixture. CPIC's
`variantallele` uses IUPAC ambiguity codes (`R` at CYP2C19 `*2`) which are reported, not coerced, and
its activity scores are inequality strings (`"≥3.0"`). Coordinates from both are 1-based — PharmVar,
CPIC and our own resolution independently agree on rs4244285 → chr10:94781859.

## 2026-08-02 — 0.5.0: PGx tables join resolution, and a multi-allelic cache bug

**Resolution now reads every table that can ask for a coordinate**, not just `variants.csv`. A PGx
module carries none by design (one CSV = one concern), so it enriched to an *empty* `resolution.csv`
and shipped with no coordinates — the chain was never variant-specific, only its input was.
`enrich._collect_subjects` normalizes `variants.csv`, `pharm_variants.csv` and `haplotypes.csv` to a
common subject and feeds them through the unchanged chain, caches, ordering and back-fill.

A `HaplotypeRow`'s defining `allele` reuses the shared `genotype_fits` predicate — the one-allele form
of the question a genotype asks of two — so a one-to-many rsID still drops loci that cannot carry it.
Subjects dedupe by `variant_key` with `variants.csv` first: it is the only table carrying `alts`, a
resolution fact, so letting a PGx row win would move an already-compiled module's `artifact.digest`.
The PGx tables key **without** `alts`, matching at `chrom:start:ref` per the standing rule.

**Bug fix (pre-existing, affected plain SNP modules too).** The Ensembl snapshot stores a
multi-allelic site as one row whose `alt` is **pipe-joined** (`A|C|T`), while every other link emits
commas. `genotype_fits` splits on commas, so the cell became a single opaque "allele", no genotype was
ever a subset of `{ref} ∪ alts`, and the 0.5 allele-aware filter discarded **every** cache-resolved
locus: `rs4244285` with the ordinary genotype `A/G` — where both alleles genuinely exist — resolved to
`not_found`. The reverse back-fill had the mirror bug, `!=` against the whole joined cell.
`resolver._snapshot_alleles` now normalizes at the single boundary where the snapshot is read. The
unit suite missed it because its fixtures were comma-separated, so the shape only ever appeared with a
real cache; the new tests use the real pipe-joined shape and fail on the pre-fix code.

## 2026-08-02 — 0.5.0: PharmGKB annotations are per-genotype

`PharmVariantRow` gains an optional `genotype`, and the duplicate-row key becomes
`(variant_key, drug, genotype)`.

The old key rejected real data. A PharmGKB clinical annotation is published *per genotype* — the
summary row names the variant and the drug, a child table gives one annotation per call, and **4,618
of the 5,113** annotations in the ClinPGx release carry exactly three. Authoring the real
SLCO1B1/simvastatin annotation (CAID 1451356520) produced `duplicate row for key ('rs4149056',
'simvastatin')` twice, so roughly 97% of the corpus was unauthorable.

The axis is not derivable: the three calls are distinct findings and sometimes opposed ones (CC and
CT "decreased response", TT "increased"), and nothing else on the row separates them but free text.
The original model was drawn from PharmGKB's *summary* table and never met the per-genotype child
table — the tell is that `VariantRow` has `genotype` and `DiplotypeRow`'s haplotype pair *is* one,
leaving `PharmVariantRow` the only sibling without it.

`genotype`'s grammar moved from `VariantRow` onto `AuthoredModel` (`check_fields=False`) now that two
models share it, so the rule cannot drift between them. It is deliberately **not** widened for the
symbolic alleles PharmGKB also carries (`C/del`, `del/del`, 177 rows) — those stay RM5. Haplotype-keyed
annotations (`*1`, `*1xN`) route to `DiplotypeRow`. PharmGKB writes a diploid call concatenated
(`CC`); the canonical form is sorted and slash-separated (`C/C`), because `CC` would otherwise read as
a single two-base allele.

Additive and optional, so existing modules validate and compile unchanged.

## 2026-08-01 — 0.5.0: validation tightening, and resolution made reversible

Where the previous round *added* facts, this one *checks* them. The organising idea is the one written
down in [COMPILER.md § what the compiler can and cannot validate](COMPILER.md): the compiler proves an
artifact well-formed and self-consistent, never true, and several of its blind spots are closable by the
enricher — the only tier that can compare authored data against reality.

**New offline compiler checks (validate-by-redundancy).** Every genotype allele and every
`effect_allele` must be one of the alleles its locus actually has (`{ref} ∪ alts`). A genotype `A/G` at
a `C>T` locus — a strand flip, the classic transcription slip — compiled clean before this. A wrong
`effect_allele` is the more dangerous of the two, because `direction`/`weight`/`effect_size` are all
stated *relative to* it, so naming the wrong allele silently inverts the module's conclusion rather than
corrupting it visibly. Also new: an **ACMG BA1 lint** (a `pathogenic` variant whose filtering allele
frequency exceeds a threshold), newly possible only because `frequencies.csv` exists.

**⚠️ Two things about that check's severity, both decided by dogfooding rather than by argument.** The
plan specified an unconditional error when the row's *own* `ref`+`alts` contradict its genotype — author
versus author, apparently decidable. It is not, and building it that way broke the suite in a way worth
recording: **`ref`/`alts` in `variants.csv` are not necessarily human-authored, because `reverse_module`
writes them too.** A one-to-many rsid reverses into N rows that each carry their own locus's alleles
beside the *one* genotype the author wrote, so exactly one of them can match. An unconditional error
would mean any module with a one-to-many rsid compiles once and never again — Principle 7's fixed point,
broken by a lint. Severity is therefore the mode ladder in both provenance cases (warn / error in
`strict`), with provenance shaping only the *message*. Relatedly, the check compares against the
**union** of every locus a key resolves to, never per-expanded-row: run per-row it produced three
findings on this repo's own `reference_examples/pathogenic_clinvar/`, and unioned it produces none.
Both properties now have regression tests built from the real `rs281864532` shape.

**New: the ClinVar clinical cross-check** (`clinical.verify_clin_sig`, offline). Compares each authored
`clin_sig` against the ClinVar snapshot's own and reports opposed calls with ClinVar's review-star
count. Matching is **allele-exact, never rsID-level**, and the committed slice shows why: `rs334` at
11:5227002 carries `T>A` as pathogenic (2 stars) *and* `T>G` as likely_benign (1 star). One rsID, one
locus, two opposite calls — an rsID-level comparison would report a module that is simply right. It is
also **the one check whose severity does not escalate in `strict`**: failing there would make the format
arbitrate a clinical dispute, which the data-agnostic charter forbids. A curator who disagrees with a
one-star submission is doing their job.

**New: the literature pack and a third derived-fact sidecar.** `literature.csv` → `LiteratureRow`, one
row per **citation** — the first sidecar not keyed on a variant, because a DOI and a PMCID are
properties of the paper, not of the variant citing it. Fact-hashed by `literature_signature`, compiled
to `literature.parquet`, summarized in a new `manifest.literature` block. The enricher pass confirms
each `pmid` resolves in PubMed, cross-fills DOI/PMCID, and matches `provenance_quote`/`provenance_regex`
against Europe PMC fulltext for the open-access subset. **Coverage is partial by nature and is reported
as a fraction**: `quotes_found` is *null* when no fulltext could be read and *0* when one was read and
the quote was absent. Collapsing those would report an unread paper as a wrong citation.

**New: identifier currency** (`identifiers.py`) — the generalization of the *"is the source stale?"*
blind spot from datasets to identifiers. rsIDs against dbSNP (live / merged / absent), trait CURIEs
against OLS4 (obsolete + replacement term), gene symbols against HGNC (approved / previous). The rsID
verdict lands on two new **provenance** columns, `ResolutionRow.rsid_current` / `rsid_status`, kept
outside `RESOLUTION_FACT_FIELDS` so a dbSNP merge cannot move a module's `resolution_signature` with no
change to the module. Report, never repair — `weights.parquet` carries `rsid` as identity, so writing a
merged-into label back would migrate `variant_key` by network lookup.

**Corrections to the plan, made under probing rather than assumed.**
(i) **The PMC ID converter is not used at all**, though the plan budgeted for it as a separate step:
`esummary` already returns both `doi` and `pmc` in `articleids`, and the converter answers a *different*
question — for PMID 12345678, a real indexed record, it replies `"Identifier not found in PMC"`, so
wiring it in as an existence check would flag every paywalled article as a broken citation.
(ii) **Europe PMC is not an existence oracle**: asked about three ids where one does not exist, it
returns two results and silently omits the third, with no error marker.
(iii) **`literature.csv` carries no `dataset` column.** Every other fact table has one because gnomAD
ships numbered releases; PubMed and Europe PMC publish no release identifier, so the column could only
be null or a fabricated label.
(iv) **`quote_found` became two integer counts**, because a quote is authored per study row while the
table's grain is the citation — one boolean would have to lie about one of them.
(v) **The automated rsID check can never emit `withdrawn`.** ROADMAP asked for the withdrawn shape to
be probed before deciding; probing dissolved the question instead of answering it. `rs11273140`
(genuinely withdrawn) returns a response **byte-identical** to `rs2000000000` (never assigned) across
`esummary`, `esearch` and Ensembl alike. So the check reports `absent` and its *message* names both
readings without choosing — guessing "typo" sends an author to fix the wrong thing when the truth is
that the variant itself was retracted. The vocabulary member is kept regardless; see the `withdrawn`
paragraph below for why, and for why its severity is not `absent`'s.
(vi) **A thread-based regex timeout does not work**, and looks like it does. `re` cannot be interrupted,
threads cannot be killed, and the interpreter joins pool threads at exit — so a runaway pattern returns
`None` on schedule and then hangs the process on the way out (observed: the test suite stopped). The
bound is a killable child process instead. No `google-re2` dependency was added; the charter's
linear-time requirement was written when the match was specified as consumer-side, and here the pattern
comes from the module being enriched, on the author's own machine.
(vii) **Dogfooding the reference example found a reporting bug in the coverage sentence.** Its single
citation (PMID 29165669, the ClinVar paper) is open access *and* carries no provenance quote, and the
first implementation reported "1 have no retrievable fulltext" — the opposite of true. The denominator
now counts only citations that actually carry a quote: one that asks no question was not skipped for
lack of an answer.
(viii) **A previously-filed loose end was not a bug.** `reverse_module` omitting `rsid_alternates` was
recorded as an open defect; it is neither open nor fixable there. Reverse rebuilds `resolution.csv` from
`weights.parquet`, which by design holds no provenance at all — it already resets `source`, `status` and
`fetched_at` — and the provenance columns are kept out of the artifact on purpose, so the information
does not exist for reverse to emit. Documented as intended behaviour instead.

**Fixtures are recorded, not fabricated.** New committed assets: `pubmed_esummary_payload.json`,
`europepmc_search_payload.json`, `europepmc_fulltext_PMC5753237.xml` (real JATS, matched with a phrase
read out of that same document), `dbsnp_esummary_payload.json`, `ols4_terms_payload.json`,
`hgnc_fetch_payload.json`, `crossref_works_payload.json` (a journal article, a bioRxiv preprint with no
PMID, and a fabricated DOI that 404s). Each captures a quirk a hand-written fixture would have smoothed away, and
the withdrawn-vs-never-assigned equality is asserted **on the recordings themselves**, so a future dbSNP
release that *does* separate them fails the test rather than silently invalidating the design. Each new
test file also carries an opt-in live probe (`JUST_DNA_NETWORK_TESTS=1`) that re-asks the real services
the same questions; all pass.

**⚠️ Resolution became reversible, and `weights.parquet` gains `authored_ident`.** The allele-membership
check above turned up rows in this repo's own reference example asserting alleles their locus does not
have — not authoring errors, but *fabrications produced by the compiler*: a one-to-many rsid copies one
authored genotype onto N loci, and reverse then wrote each locus out as an authored row. Three of the
23 expanded rows in `reference_examples/pathogenic_clinvar/` were of that kind. Two changes fix it at
the source:

* **A locus whose `{ref} ∪ alts` cannot host the authored genotype is no longer expanded onto**
  (`resolution.genotype_fits`, shared with the deprecated DuckDB path so digest parity holds).
* **`VariantRow.authored_ident`** records which identity columns the author actually supplied, stamped
  at load beside `variant_key` and materialized to the artifact. Reverse re-emits exactly that shape:
  an rsid-only row comes back rsid-only instead of carrying resolved coordinates, and an expansion
  collapses back to the single row it was written as. This is only possible now that the key is
  canonical — a VRS allele id identifies the row without the coordinate having to live in
  `variants.csv`, which under coordinate-first keying it did.

Consequence: **`content_signature` is now a round-trip fixed point for rsid-authored modules**, where
before it moved on *every* one of them. Not a regression being fixed — the behaviour dates from 0.4's
frozen-identity work and was tested under the name `test_expanded_rsid_roundtrips_as_position_only`;
what changed is that canonical keys made the better answer available.

**Forward resolution is now allele-aware too.** The reverse (position→rsid) back-fill has matched on
the exact allele since 0.5; the forward (rsid→loci) direction did not, and that asymmetry is what put
unusable loci into the table in the first place. A candidate whose alleles cannot host the authored
genotype is now reported and left out. The compiler keeps the same check as a safety net for
hand-authored tables (the predicate is shared, so they cannot drift), but a table the enricher produced
no longer needs it — which is what lets the reference example compile under `--strict`.

**The resolution round-trip contract, enumerated.** Five identity columns the author may or may not
supply, crossed with what the table says about them, is a finite set — so it is enumerated in
`compiler/tests/test_resolution_matrix.py` under one rule: **every combination is either a round-trip
fixed point on all three signatures, or it fails in `strict`.** Making that true required tightening two
cases that used to pass quietly: an authored coordinate or `ref` contradicting the table (the artifact
keeps the authored value, so the table's is lost on reverse) now refuses in `strict`, and so does an
`ambiguous` rsid — not because anything is lost, but because a deterministic pick among equals is a pick,
not a finding. `artifact.digest` remains a fixed point in *every* case, including the unstable ones.
Also fixed while enumerating: a coordinate-only row never adopted the table's `alts`, so the resolved
allele never reached the artifact.

**Citation coverage beyond PubMed, and beyond the open-access subset.** Two additions, both probed
before being built. **Crossref** confirms the *authored* DOI resolves — the registry's own exists by
construction — which covers what PubMed structurally cannot index (a probed bioRxiv preprint returns
`type: posted-content`; a fabricated DOI 404s) and de-risks the 1.0 doi-first flip, since existence
checking then works without a PMID. And the quote check now **falls back to the abstract**, which
Europe PMC serves for non-open-access records in the response the pass already makes: four of five
probed non-OA papers carried one. A new `quote_source` column records how far the search reached,
because a hit and a miss are not symmetric — a phrase found in an abstract is in the paper, while a
phrase absent from a 200-word abstract says nothing about the body, so an abstract miss still counts
as unchecked. Worth stating plainly since it was easy to misread: **a paywall never hid *existence*** —
PubMed indexes paywalled work, and `exists` was always answered for it. Rejected explicitly rather than
deferred: **Google Scholar** (no API, and automated querying violates its terms); OA-repository PDF
retrieval via OpenAlex/Unpaywall is on the roadmap, since the closed paper probed had no OA copy at all
and the ones that exist are PDFs.

**`withdrawn` is back in `VALID_RSID_STATUS`, with its own severity.** Nothing automated emits it — a
retraction is byte-identical to a never-assigned id through every live endpoint, so the check still
reports `absent` and names both readings — but the member is kept so a curator who has established a
retraction can record it, and so a future source can start producing it without a vocabulary change
(Principle 3 makes that a one-way door). It is **not** interchangeable with `absent`: absent has benign
causes and refuses only under `strict`, while a retracted variant may leave the annotation describing
nothing, so `withdrawn` refuses in `best_effort` too — the only resolution finding that does.

**A correction to the analysis, caught by the repo's own fixture rule.** The first pass concluded that
an ambiguous resolution could not be round-trip stable and therefore had to be an error in both modes.
That came from a hand-written two-row fixture; the enricher actually writes **one** row carrying the
deterministic pick, with the candidate list in `rsid_alternates` (provenance, outside the fact set). The
real shape is stable, so ambiguity stays a best-effort warning as intended.

**Also:** `PacingGate`/`batched`/`dedupe` moved out of `gnomad.py` into a shared `net.py` (three clients
now need them), a new `eutils.py` NCBI client shared by the literature and rsID checks, and the
compiler's two-way fact-table branch became a per-model dispatch that scales past three sidecars.
`compile_module` gains an optional `ba1_threshold`; `enrich()` gains `verify_clinsig` / `verify_rsids`;
new CLI commands `literature` and `check-identifiers`.

## 2026-07-31 — 0.5.0: gnomAD v4.1 (frequency + gene constraint) and GA4GH VRS identity

Three roles for one source, plus the identity change the VRS work unlocked. Design thread and the
reasoning in [PROPOSAL_0_5.md § G1](PROPOSAL_0_5.md); use cases in [USE_CASES.md §6](USE_CASES.md).

**New derived-fact sidecars** (schema + compiler + enricher). `frequencies.csv` → `FrequencyRow`, one
row per **(allele, ancestry group)** carrying AC/AN, `homozygote_count`, `faf95` and `dataset`;
`gene_metrics.csv` → `GeneMetricsRow`, one row per gene carrying pLI/LOEUF/Z scores. Both are injected,
machine-produced, human-overridable, hashed by **facts** (`frequency_signature` /
`gene_metrics_signature`, sharing one `fact_signature` body with `resolution_signature`), and compiled
into their own optional parquets with new `manifest.frequency` / `manifest.gene_metrics` blocks. They
are deliberately **not** `_TABLE_KINDS` — a machine-produced reference-fact table is a third category
beside authored DSL tables and the compiled artifact. `allele_frequency` is a **derived** property
materialized only in the parquet: integers round-trip exactly through CSV, a stored float does not.
Ancestry groups are an **open, seeded** vocabulary (the table must outlive gnomAD as its only source).

**gnomAD in the enricher.** A new `gnomad.py` client — batches of 20 aliased GraphQL lookups on a 6s
pacing gate (the stated limit is 10 requests/IP/60s), tenacity on transport/timeout/429, and per-alias
error handling so a partial failure keeps the rest of the batch. A **last-resort resolver link**
(`source="gnomad"`, after live Ensembl so no compiled module's `alts` or digest can move), the
frequency pass (online only — the v4.1 sites VCFs are 58 GB / 742 GB, so no snapshot is possible), and
the gene-constraint pass (snapshot first, live API second — the one gnomAD role that completes offline),
with a `[dev]` builder for the 95.5 MB constraint TSV and a third HF snapshot on the existing ladder.

**GA4GH VRS allele identity — minted, not merely recorded.** New stdlib `just_dna_format.vrs`:
`derive_vrs_allele_id` computes a `ga4gh:VA.…` for a substitution with `hashlib`/`base64`/`json` and
**no new dependency in the format tier**, against a committed GRCh38 refget table. `ResolutionRow` and
`FrequencyRow` gain `vrs_id`/`vrs_spec`/`caid` cross-reference columns (outside the fact sets, so no
existing `resolution_signature` moves). The enricher mints indels too, normalized against the reference.

**⚠️ `variant_key` now derives from the VA for a resolved substitution — `artifact.digest` moves.**
An rsid row keeps its rsid; an indel, MNV, multi-allelic or position-only row keeps its coordinate key.
This is legal now, not at 1.0, because `variant_key` is *derived and frozen, never authored* — no
authored schema, no DSL, and no human author is touched. It is major-only for one reason (the column is
in `weights.parquet`, hence in the digest), and that gate is **publication**, not the version number:
0.4 is the published line and 0.5.0 never shipped, so this rides the same one-time pre-publication
re-baseline as the alt-carrying key. **No published artifact moves.** A VRS id also *names its build*
(the refget accession is the digest of the reference sequence), which is exactly the condition RM15 set
for reconsidering coordinate-first identity — so that parking is resolved, with multi-build minting the
remaining RM15 half. Modules compiled on an earlier 0.5.0 dev commit must be recompiled.

**Two compiler checks come with it.** A stored `vrs_id` is recomputed and verified before anything is
written, with **three** outcomes rather than two: *verified* (silent), *mismatch* (recomputed and
different — an error in both modes, since a substitution's id is deterministic here and a disagreement
can only be corruption), and *unverifiable* (could not be recomputed at all — a warning in
`best_effort`, an error in `strict`, because "unchecked" and "correct" are different things). An indel
is never reported as a mismatch: this tier cannot recompute one, so it can only say it did not check.
Unverifiable also covers multi-allelic, position-only, no-coordinate, off-assembly and non-GRCh38 rows;
the last used to let `UnsupportedBuildError` escape and abort the whole compile, and the off-assembly
case used to pass `strict` silently — both fixed, with a full matrix test. And because a VA addresses
the *place and the alt* but not `ref`, two positioned rows sharing a key while disagreeing on `ref` are
now an explicit error — preserving a diagnosis the old key gave for free.

**New: the reference-allele check, and enrichment-as-validation stated as a goal.** `sequences.py`
compares every authored `ref` against the actual reference bases and reports disagreements on
`EnrichmentResult.ref_mismatches` (`--verify-ref/--no-verify-ref`; `best_effort` warns, `strict`
refuses). This closes a gap the VRS work opened: a VA is built from *which sequence*, *which interval*
and *what replaces it*, so the reference allele is not a component — which means minting never checks
it, and VCF's free `REF` consistency check (liftover slips, off-by-ones, wrong assembly) had no
equivalent. Two failure modes, separated by the claimed length: a **single-base** wrong ref is absorbed
(the same id is minted, so nothing downstream could notice), while a **multi-base** wrong ref sets the
wrong interval and mints a well-formed id for a *different allele*. Findings are **reported, never
repaired** — rewriting an authored value would destroy the evidence that something upstream is broken.
[ENRICHER.md](ENRICHER.md) now states the general principle: the enricher is the only tier that *can*
compare authored data against reality (format and compiler are inject-only by charter), so surfacing
discrepancies is part of its job, and every such check reports rather than repairs with severity
following the mode.

**New: the validation model is written down, limits included.** [COMPILER.md](COMPILER.md) now opens
with *What the compiler can and cannot validate* — the trust boundary with the enricher, the three
strengthening classes of check it performs (formal conformance → validate-by-redundancy →
content-addressed self-verification), and an explicit table of **inescapable blind spots**. The
compiler is an assembler/linker, not a truth oracle: it proves an artifact well-formed and
self-consistent, never true, and several things it cannot check are permanent consequences of being a
no-network tier or of the data-agnostic charter. What it cannot validate, the format makes *legible*
instead (`source`, `dataset`, `status`, `authorship.kind`, the signatures). Framing the VRS work in
those terms: it moved `vrs_id` out of "opaque cross-reference you must believe" into the
self-verifying class, which is the strongest static guarantee available here.

**New: validate-by-redundancy on the sidecars.** The new tables' numbers constrain each other, so
violations are detectable with no reference at all: `allele_count ≤ allele_number` and
`2 × homozygote_count ≤ allele_count` are exact integer impossibilities (**errors**), while
`faf95 ≤` the group's own AF, `oe_lof_lower ≤ oe_lof ≤ loeuf`, and `obs_lof / exp_lof == oe_lof` are
float relations that hold on real gnomAD output and **warn** when they break (the last catches a
column-mapping slip in a builder). A test asserts the recorded payload trips none of them — a
redundancy check that fires on genuine data is worse than no check.

**Fixed: the canonical trait example was an obsolete ontology term.** `EFO_0001645` (used in
`spec.py`'s `trait_efo_id` description, `vocab.py`'s CURIE comment and its author-facing error message,
`REFERENCE_EXAMPLES.md`, and a compiler fixture) has been retired in favour of `MONDO_0005010`. The
grammar examples now use `EFO_0004340`; the two coronary-artery-disease examples use `MONDO_0005010`.
Found while probing the ontology-currency check that later shipped as T4.1 — and worth
recording that `EFO_0001360` is obsolete too, so replacing these by memory rather than by lookup would
have substituted one retired term for another.

**Fixed: a located-but-unusable ClinVar cache no longer crashes `enrich()`.** A cache directory holding
parquet from another tool (or an older builder) made the DuckDB query raise and killed the whole
enrichment, even when the Ensembl cache had the answer. It now degrades to a miss with a warning, like
every other link. This also made a pre-existing test only pass depending on cross-file ordering.

**Corrections to the plan, made under probing rather than assumed.** (i) The live `gnomad_constraint`
API field serves **v2.1.1** constraint, not v4.1 — same gene, same MANE transcript, different numbers —
so the two routes are labelled as the different datasets they are, and the planned "the routes agree"
test asserts the difference instead. (ii) Indel normalization needs no local `seqrepo`/`pysam`: core
`ga4gh.vrs` over the seqrepo REST proxy does it in 14 pure-Python packages, so complete allele identity
is a **core** enricher capability rather than a `[dev]` extra, and `--offline` is the only thing that
degrades it. (iii) The VRS allele serialization embeds the location's *digest*, not its content — the
plan's stated mechanism was wrong even though its conclusion held; the shape was settled against
recorded gnomAD ids. (iv) Indels keep the coordinate key rather than an enricher-minted VA, because
re-keying from an optional network call would make `artifact.digest` depend on whether that call
succeeded.

**Fixtures are recorded, not fabricated** — `assets/gnomad_v4.1_variant_payload.json`,
`gnomad_gene_constraint_payload.json`, `gnomad_v4.1_constraint_slice.tsv`. The quirks under test (a
`"Multiple variants found"` error beside valid data, `XX`/`XY` listed twice, two `mane_select=true` rows
per gene) are ones a hand-written fixture would have omitted, letting the naive implementations pass.

## 2026-07-30 — `variant_key` carries the alt (distinct alleles at one locus no longer collide)

Second finding from the ClinVar dogfood (`reference_examples/pathogenic_clinvar/`): with the
allele-aware back-fill in place, the compiler's reverse round-trip *still* wasn't a fixpoint for
`resolution_signature`, because `variant_key = chrom:start:ref` **excluded `alt`** — two distinct
alleles at one locus (the coordinate-only insertion `11:5226762 C>CAAAG` and the expanded `rs33979901`
locus `11:5226762 C>CA`) collapsed onto one key, and the decompiler couldn't tell them apart.

- **`base.derive_variant_key` gains an optional `alts`.** The coordinate identity is now
  `chrom:start:ref:alts` (alts normalized/sorted) **when an alt is present**; rsid keys, position-only
  keys (no alt), and the position-level *matching* helpers (studies, verify, reverse-lookup,
  haplotypes) are unchanged — a study still matches a variant at `chrom:start:ref` regardless of allele.
- Passed at the identity-mint sites only: `VariantRow._freeze_variant_key` and the three one-to-many
  expansion re-key points (compiler `resolution.py`, enricher `resolver.py`, reverse writer).
- Result: `compile → reverse → compile` is now a **full fixpoint** (`artifact.digest`,
  `content_signature`, **and** `resolution_signature`). This changes `artifact.digest` for any module
  carrying alt-bearing *coordinate* variants (rsid-based modules are unaffected) — acceptable while 0.5
  is unpublished and `resolution.csv`/the digest are not yet frozen. `StudyRow`/`PharmVariantRow` keep
  their position/rsid-level keys by design.

## 2026-07-30 — enricher: allele-aware reverse back-fill + ambiguity marking

Surfaced by dogfooding the ClinVar module (see `reference_examples/pathogenic_clinvar/`): the reverse
(position→rsid) back-fill for coordinate-only variants was **allele-blind** — it matched
`(chrom,start,ref)` and could attach a co-located *different-allele* rsID (an un-rs'd insertion
inheriting the SNV's rsid), which also made the compiler's reverse round-trip drift on
`resolution_signature`.

- **Allele-aware reverse lookup.** `resolver.lookup_loci` / `clinvar.lookup_loci` now match the exact
  allele `(chrom,start,ref,alt)` and return *all* candidate rsIDs (shared `_lookup_rsid_candidates`,
  one implementation for both tables). `enrich()` passes the authored `alt` through.
- **Don't-guess + mark ambiguity.** A coordinate-only variant with no allele-exact rsid stays
  `rsid=null`/`source=authored` (coordinate is the identity); with exactly one → resolved; with several
  for the *same allele* (a dbSNP merge) → `status="ambiguous"`, a deterministic `rsid` pick, and the
  full candidate list in the new provisional **`ResolutionRow.rsid_alternates`** column (provenance,
  excluded from `resolution_signature`).
- This removes the mis-attribution and makes `resolution_signature` a reverse fixpoint whenever
  `variant_key`s are distinct. A deeper residual remains and is parked: `variant_key = chrom:start:ref`
  excludes `alt`, so two alleles at one locus still share a key — carrying `alt` in the resolution key
  is the follow-up. `resolution.csv` is provisional in 0.5, so no released contract is affected.

## 2026-07-30 — enricher: ClinVar reference snapshot (builder + resolver link + publisher)

ClinVar becomes a second, complementary reference beside the Ensembl snapshot in `just-dna-enricher`.
**No schema change, no compiler change** — `ResolutionRow.source` is an open field, so `"clinvar"`
needs nothing new, and the compiler's consumption contract is untouched.

- **`clinvar_build`** (`[dev]`, guarded `polars`) — `build_snapshot(vcf, out_dir)` converts the NCBI
  ClinVar GRCh38 VCF into a per-chromosome parquet snapshot (`data/clinvar-chr{N}.parquet`, one row per
  ACGT ALT allele) + `release.json` provenance; `download_clinvar_vcf` streams the VCF with the core
  `httpx`. `clin_sig` is folded into `vocab.VALID_CLIN_SIG` by an explicit severity order, `clin_sig_raw`
  kept verbatim. The parquet is byte-reproducible across rebuilds.
- **`clinvar`** (core, `duckdb`) — `lookup_loci` mirroring `resolver.lookup_loci` exactly, so the
  enrich chain treats the two references identically. Reads only `chrom/start/ref/alt` (annotation
  columns stay out of `resolution.csv` — orthogonal axes, P5).
- **Chain wiring** — a ClinVar link between the Ensembl cache and live Ensembl, stamping
  `source="clinvar"`, filling only what the Ensembl cache missed. It sits **after** the Ensembl cache
  on purpose: `alts` is a resolution fact flowing into `artifact.digest`, so a both-caches variant keeps
  the Ensembl `alts`/`source="cache"` and **no already-compiled module's digest moves** (tested).
  `--offline` clamps to both local caches (zero egress); `--no-clinvar` disables the link.
- **Publisher** — `upload.py` gains `ensure_repo` (`create_repo(exist_ok=True)`, absent from the
  extracted `v1_port.publish`) and `publish_reference_snapshot`; module upload now routes through
  `ensure_repo` too, so create-or-update-then-upload is one pathway.
- **CLI** — `clinvar build`/`clinvar publish` sub-app; `enrich`/`enrich-and-compile` gain
  `--clinvar-cache` and `--clinvar/--no-clinvar`.
- **Doc fix:** `ResolutionRow.start` is documented as **1-based** (VCF POS convention; it always was —
  the coordinates are unchanged, only the docstring was wrong).

## 2026-07-28 — enricher `[dev]`: HF module upload extracted from just-dna-lite

- **`just_dna_enricher.upload`** — publisher surface for pushing a compiled module
  (`weights`/`annotations`/`studies.parquet` + `manifest.json` + optional logo) to a HuggingFace
  dataset collection (`data/<name>/`). Plan + upload APIs, with a lazy `huggingface_hub` import.
  Extracted from `just_dna_pipelines.v1_port.publish` (just-dna-lite Gen-I recreation/publish path).
- **CLI:** `just-dna-enricher upload <module_dir> [--repo] [--name] [--message] [--dry-run]`.
- **`just-dna-enricher[dev]`** optional extra (+ matching `dependency-groups.dev`) marks the
  publisher/test install path; snapshot *download* stays a core enrich dep, upload is the
  author/publisher half of the same HF surface.
- **Consumer note (just-dna-lite):** `v1_port.publish` still carries a local copy (pipelines is
  pinned to format/compiler `<0.4` and cannot import enricher 0.5 yet). Docstring points here as
  the canonical home; switch to a thin modules.yaml-aware re-export of
  `just_dna_enricher.upload` when pipelines adopts the enricher tier (`just-dna-enricher[dev]`).

## 2026-07-23 — 0.5.0 (in progress, `enricher-0.5`) — source-independent resolution table

The 0.5 rework begins: resolution moves from a *live-ish opaque reference the compiler queries* to a
*persisted, source-independent table the compiler is handed*, so the compiler owns no source
convention and becomes strictly inject-only. All fetching (cache download + live Ensembl) will live
in a new `just-dna-enricher` network tier that *produces* the table; this increment lands the
consumption side entirely inside the two existing packages — additive, digest-neutral, and green
(the compiler still never fetches; it is *more* inject-only, not less). See
`docs/PROPOSAL_0_5.md` and the approved plan. **Per-package references (added this pass):**
[SCHEMAS.md](SCHEMAS.md), [COMPILER.md](COMPILER.md), [ENRICHER.md](ENRICHER.md).

> **`resolution.csv` is provisional.** It is **new in unreleased 0.5** — no 0.4 module carries it — so
> the additive-within-a-major / digest-freeze obligations (Principles 3/8) have **not** engaged for it.
> Its shape (`ResolutionRow` columns, keying, the `status` vocabulary, how one-to-many expansion is
> encoded) may be **refactored wholesale** during 0.5 dev and is expected to take a few passes before
> it settles. The stable contract (`variant_key` identity, `artifact.digest`, `content_signature`) is
> unaffected by resolution's internal shape.

Shipped in this increment (schema + compiler; **no network added yet**):

- **`resolution.csv` — the injected fact table.** New `just_dna_format.resolution.ResolutionRow`
  (schema tier, shared by the three parties: compiler consumes, enricher will produce, a verify-only
  client can re-check). Keyed by the frozen `variant_key`; carries the resolved facts
  (`rsid/chrom/start/ref/alts/genome_build/locus_index`) and a segregated provenance triple
  (`source`/`status`/`fetched_at`). A one-to-many rsid is N rows sharing `variant_key` with distinct
  `locus_index`. `genome_build` is the RM15 forward hook (no more silent GRCh38). `status` is a closed
  vocabulary `{resolved, not_found, ambiguous}` (Principle 6); `not_found` is the resolution analogue
  of the binning `unresolved` sentinel.
- **Pure `resolve_from_table`** (`just_dna_compiler.resolution`, **no `duckdb` import**) reproduces the
  DuckDB resolver's fill / expand / verify semantics from the injected table. `compile_module`
  precedence (additive, P3): `resolution.csv` present → this pure path; else an injected
  `ensembl_cache` → the superseded DuckDB path; else skip-with-warning. **Digest parity is proven** —
  given the same facts, both paths emit byte-identical `weights.parquet` (the expansion order is
  pinned on `(locus_index, chrom, start, ref)`).
- **Two-layer hashing kept intact; the table hashed separately.** `content_signature` (authored-only)
  is untouched — verified it builds from its own explicit table list, never `_INPUT_FILES`. The table
  is **not** added to `_INPUT_FILES` (a raw-bytes hash would be unstable across the enricher/human/
  reverse producers); instead a new **`integrity.resolution_signature`** hashes only the fact columns
  (provenance excluded), so a human-filled and an Ensembl-filled table with identical facts hash
  equal. Reproducibility identity is the triple `(content_signature, resolution_signature,
  compiler_version) ⟹ artifact.digest` — offline from two small CSVs.
- **Manifest (`Compilation`, all optional, out of `artifact.digest`):** `resolution_mode`
  (policy: strict|best_effort), `fully_resolved` (outcome — orthogonal axis, P5), `resolution_signature`,
  `resolution_sources`. Together they tell a catalog a strict, fully-resolved module from a
  best-effort half-baked one.
- **Reverse emits `resolution.csv`.** `reverse_module(..., write_resolution=True)` reconstructs the
  resolved facts from the artifact, so `reverse → compile` reproduces the identical `artifact.digest`
  with **no network and no reference** — hardening Principle 7's round-trip from reference-dependent to
  self-contained (a coord-keyed row's resolved rsid, dropped from `variants.csv`, is restored here).
- **CLI:** `reverse --resolution/--no-resolution`; `compile` prints `resolution_mode`/`fully_resolved`/
  `resolution_signature`. **Tests +8** (schema `resolution_signature` stability; compiler digest-parity
  / offline round-trip; provenance/order-independence; `resolution.csv` absent from `manifest.inputs`
  with `content_signature` unchanged; strict-vs-best-effort via the table).

**`just-dna-enricher` — the new network tier (shipped this increment).** The only package allowed to
fetch; it *produces* `resolution.csv`, and the arrow points inward (`enricher → compiler → format`) so
`httpx`/`huggingface-hub` never enter the compile path. `enrich(spec_dir, mode, offline, ...)` runs a
first-hit-wins chain — existing/human row (authoritative) → local cache (offline; reuses the
compiler's new public `resolver.lookup_loci`) → HF snapshot download (footer-checked, atomic, inherited
from lite byte-for-byte) → live Ensembl **V2 GraphQL → V1 REST fallback on 500/503**, `tenacity`
retrying transient errors — then writes `resolution.csv`. Modes: `best_effort` records misses as
`not_found`; `strict` fails unless every variant resolves; `--offline` clamps to the cache (zero
egress). Ensembl query shapes/endpoints are leeched from ensembl-mcp with `fastmcp`/`eliot` dropped
(stdlib logging), Python floor held at the compiler's `>=3.13`. CLI: `enrich`, `enrich-and-compile`.
Downstream (ensembl-mcp, lite/pipelines) adopt this as the single source of truth for resolution.
**Tests +6** (offline enrich→compile matches the DuckDB digest; `--offline` makes zero network calls;
V2 503 → V1 REST; tenacity retry; strict failure; one-to-many expansion). The two libs bumped
`0.4.0 → 0.5.0` so the workspace resolves the new member.

**Constitution amended (deliberately).** Goal 2, both dependency/network Non-goals, and Principle 2
now name the network tier: format + compiler become *more* strictly inject-only (own no source
convention, never fetch), and HuggingFace/httpx/tenacity are scoped to the enricher, never reaching
the dependency-light tiers a verify-only/compile-only client installs. Additive and scoped, not a
reversal — it completes the 0.4.1 *"cache authority leaves the compiler"* decoupling.

**The compiler is now duckdb-free (final decoupling, done).** `cache.py` and `resolver.py` (the cache
location + the whole DuckDB rsid↔coord resolver) **moved into `just-dna-enricher`** — `enricher/locations.py`
and `enricher/resolver.py`. The compiler dropped `duckdb`, `platformdirs`, and `python-dotenv`; its only
resolution is now the pure `resolve_from_table` (a `resolution.csv`). The `compile_module(ensembl_cache=…)`
**surface is kept** but deprecated: when used it emits a `DeprecationWarning` and routes to the enricher
via a guarded optional import (the compiler declares no dependency on the enricher and never fetches);
`None` now means *skip* (no env/platformdirs auto-discovery — the P2 tightening). The legacy path is
removed at **1.0**. This is legal because additive-within-a-major binds the wire/artifact *contract*, not
an internal compiler call. The resolver's own tests (`test_resolver_unit`/`test_resolver_integration`)
moved to `enricher/tests`; a `test_deprecated_ensembl_cache_path_warns` asserts the deprecation fires.

## 2026-07-15 — 0.4.0 (released) — audit pass: input-hardening tidy-ups

A fourth audit pass over the 0.4 branch. A full read confirmed the invariants hold (round-trip/
idempotency proven empirically across the frozen-key, expansion, and 0.4 generic-table paths); two
input-validation gaps remained, both fixed with regression tests. (The previously-suspected residual
poly-effect annotation loss was re-examined and found **non-real** — same `variant_key` implies one
locus implies one gene, and identical `conclusion`+`negatives` implies the same effect, so no
sensible case can differ in `gene`/`phenotype`/`category`; the genuine loss was already closed by the
variant-effect-pair keying below.)

- **Ragged CSV rows no longer slip past `extra="forbid"`.** A data row with more cells than the header
  had its surplus bucketed under `csv.DictReader`'s `None` key and silently dropped, so a shifted or
  extra column read as valid instead of being rejected like a typo'd header. `_load_csv_rows` now
  fails such a row with a line-located diagnosis (a typo'd *header* was already caught).
- **Namespace slug rule tightened.** `NAMESPACE_PATTERN` rejected a leading hyphen but accepted a
  trailing (`just-dna-`) or doubled (`a--b`) one; it now requires hyphens to *separate* alphanumeric
  segments (`^[a-z0-9]+(-[a-z0-9]+)*$`). No real namespace used those forms, so nothing valid is
  invalidated. **Tests +3.**

## 2026-07-15 — 0.4.0 (released) — frozen variant identity + one-to-many rsid expansion

A follow-up correctness pass on the 0.4 branch, resolving an identity-model flaw the branch review
surfaced (unpublished at the time, so the `artifact.digest` move was free). Root cause: `variant_key =
rsid-else-coord` treated an rsid and a coordinate as interchangeable identities, so the Ensembl
resolver — an enrichment — *mutated identity* (filling a coord→rsid flipped the derived key; a
one-to-many rsid had no faithful representation), silently breaking round-trip/idempotency
(Principle 7) and collapsing `annotations.parquet` dedup.

- **Frozen `variant_key` (minimal B+).** `VariantRow.variant_key` is now a stored column (via
  `base.derive_variant_key`), stamped once at load — rsid when it uniquely identifies the row, else
  the coordinate — and never re-derived; a `model_copy` does not re-run the validator, so resolution
  can fill a coord/rsid or expand a row without ever re-keying it. Materialized into
  `weights.parquet`; **compiler-managed** — excluded from `authoring_reference()` and never written
  back by `reverse_module`. `StudyRow`/`PharmVariantRow` keep the derived property (never resolved).
- **One-to-many rsid → row expansion.** A no-coord rsid that resolves to N>1 loci now expands into N
  coord-keyed rows (a paralog/SV signal a consumer can count — data-agnostic), instead of a
  non-deterministic "first-met" pick. `_lookup_positions_by_rsid` gained `ORDER BY id, chrom, start,
  ref` and returns all loci. Compiler behavior pinned by `compiler_version` (P4), GRCh38-only.
- **`reverse_module` restores authored shape** by reading the frozen key: an rsid-keyed row emits its
  rsid; a coord-keyed row (rsid was *resolved*, or position-only/expanded) emits **position-only**,
  dropping the resolved rsid — so field-only recompute + re-resolution reproduce the same key. No new
  CSV column; reverse→recompile is a digest fixed point (proven for the position-only→rsid and
  expansion shapes).
- **Bidirectional rsid↔coord consistency check** against the **injected** reference (inject-only, no
  network — Principle 2, same pattern as the resolver): a disagreement is a **warning** (may be a
  dbSNP merge/build difference), never fatal.
- **GRCh38-bound reality made explicit.** Resolution is skipped with a warning for a non-GRCh38
  `genome_build` (positions are not re-resolved cross-build — RM15) rather than corrupting
  coordinates against the wrong assembly; documented on `genome_build`, in COMPILER.md, and as
  ROADMAP RM15 + the "additivity has two axes" note.
- **Audit fixes.** Studies orphan check matches on a shared identifier (rsid *or* coord), not
  frozen-key equality; the position-consistency check compares only positioned rows (no
  mixed-authoring false positive); a malformed `provenance.json` / unsupported logo returns
  `CompilationResult(success=False)` instead of raising mid-compile; stale docs corrected
  (`COMPILER.md` reserved-namespace row, compiler `__init__` "three-parquet"); dead `or v` tails
  dropped. **Tests +20** (frozen-key freeze/backfill/reference-exclusion, resolver expansion +
  determinism + consistency + build-skip, compile→reverse→recompile flip-prevention + expansion
  idempotency, old-artifact fallback, orphan-on-coord, malformed-provenance).

## 2026-07-15 — 0.4.0 (released) — audit pass: poly-effect round-trip + reverse-writer dedup

A third correctness/tidiness pass over the 0.4 branch (unpublished at the time, so the `annotations.parquet`
schema move is free). Each fix ships with a regression test.

- **Poly-effect annotation no longer lost on round-trip (Principle 7).** `annotations.parquet` was
  deduplicated by `variant_key` alone, so a genuine poly-effect variant — one locus, two genotype rows
  with distinct `conclusion` **and** distinct `gene`/`phenotype`/`category` (as embryo-level / neural
  findings routinely are when `category` does not subsume the effect) — collapsed onto its first row,
  silently overwriting the second row's annotation on `reverse_module`. This was introduced with the
  `variant_key` column. The genuine identity is the **variant-effect pair**, so annotations now dedups
  on `(variant_key, conclusion, negatives)` and carries `conclusion`/`negatives` so the table is
  self-joinable back to `weights.parquet`; reverse probes the same key. `artifact.digest` moves once
  (annotations gained two columns) — expected while it was still pre-release; determinism + round-trip are held.
- **Coord-key format de-inlined to one source.** `chrom:start:ref` was hand-built in ~8 spots across
  the compiler and resolver despite `base.derive_variant_key` being the documented single source of
  truth; all now call the helper (the literal format lives only in `base.py`).
- **Reverse writers share one cell formatter.** The None→""/tri-state-bool/integer-float/list-join
  cell logic was implemented four ways (`_write_table_csv`, `_bool_cell`, and per-field ternaries in
  the variants/studies writers); consolidated into `_scalar_cell`/`_list_cell` used by all three.
- **Doc:** `reverse_module`'s manifest-only-metadata boundary (it reconstructs the compilable core
  from parquets; `genome_build`/`authorship`/`panel`/`provenance`/`logo` are not restored) is now
  stated explicitly as known/expected in COMPILER.md.

## 2026-07-15 — 0.4.0 (released) — branch-review fixes

A second correctness/consistency pass over the 0.4 branch before publish (unpublished at the time, so all
of the below is free to absorb). Each fix ships with a regression test.

- **PGx diplotypes with multiple drug annotations now compile.** The per-table duplicate-row key for
  `DiplotypeRow` omitted `drug`, so two legitimate rows for one haplotype pair differing only by drug
  (e.g. CYP2D6 `*1/*1` → codeine and → tramadol) were wrongly rejected as duplicates and the whole
  module failed to compile. The key now includes `drug` (matching its own comment and the intended
  authoring pattern). `HaplotypeRow`'s key likewise gained `ref`, so two position-only defining
  variants at the same locus differing only by reference allele no longer false-collide.
- **Reserved-namespace enforcement extended to the SNP core.** `VariantRow`/`StudyRow` now enforce
  `extra="forbid"` (via the shared `AuthoredModel` base below), matching the 0.4 composed tables — the
  ROADMAP tracker previously scoped rejection to "the 0.4 tables" only, so the core defaulted to
  `extra="ignore"` and a genuinely-reserved name (or a misspelled column like `directon`) was silently
  dropped rather than rejected. Now caught at validate time. A **hardening** in the spirit of
  CONSTITUTION P5 (reserve names so they survive the one-way door) + P3 (names permanent within a
  major) — the charter mandates reserve+audit, not runtime rejection, so this is a strengthening, not a
  charter-forced fix.
- **The reserved list now has build-time teeth, not just a published dictionary.** A `reject_reserved`
  before-validator (`vocab.py`), layered on `extra="forbid"` on every authored model, makes a reserved
  name fail with a *specific* diagnosis — what the name is reserved for (`vocab.RESERVED_NAME_REASONS`)
  and that a future release may claim it — while a random or misspelled column still gets the generic
  "extra inputs not permitted". So `reference_db` ≠ `xyzzy` at the point of failure, at author time and
  in the compile errors, for both a human and an authoring agent. Previously the frozenset drove no
  validation behavior at all (consulted only by `authoring_reference()`); now reserved vs. arbitrary is
  a real distinction the maintainer's list produces.
- **Reserved set corrected: `caller`/`caller_version` dropped, `reference_db` re-scoped.** The
  "provenance triple" (round-2 Q2) was a category error: `caller`/`caller_version`
  name which tool produced a *call* — a consumer-side measurement the module never holds — so there is
  no anticipated module axis to reserve, and barring the bare name is arbitrary (one non-feature among
  unbounded non-features; `extra="forbid"` already rejects them generically). They are removed from
  `RESERVED_NAMES_0_4`, which is now *only* genuine anticipated module axes: **`reference_db`** —
  re-scoped to its real module-side meaning, a hint naming which reference DB the app should join an
  annotation against (implicit Ensembl/ClinVar today; pinnable per module) — and **`callable_from`**
  (RM6). (The provenance-triple framing was dropped when the 0.4 proposal doc was retired.)
- **DRY: single `AuthoredModel` base** (`base.py`). The reserved-namespace guard (`extra="forbid"` +
  `reject_reserved`) and the field validators for the shared authored vocabulary (`rsid`,
  `trait_efo_id`, `direction`, `clin_sig`, `stat_significance`, `evidence_level`, finite-`effect_size`)
  were copy-pasted across `spec`/`binning`/`pgx`/`pgs` (~22 duplicated validators + 8 `model_config` +
  8 guards). They now live once on `AuthoredModel`; each row model inherits it and keeps only its
  field-specific rules (genotype/phase, star-allele strings, measure bounds, PGS ancestry, the mtDNA
  legacy-reference guard, identifier completeness). `check_fields=False` means a validator runs only
  for the fields a subclass actually declares, so per-field rules can no longer drift model-to-model.
- **Deterministic ref-less rsid resolution.** In the inject-a-reference path, a ref-less position over
  a multi-allelic dbSNP site was resolved to whichever row the DB returned first (no `ORDER BY`) — a
  latent idempotency risk, silent. It now resolves deterministically and emits an ambiguity warning
  telling the author to specify `ref` to disambiguate.
- **Doc/comment consistency:** the compiler module docstring now describes the composed multi-parquet
  artifact (not a fixed three-parquet one); the COMPILER.md coverage header reads "0.3 / 0.4 feature"
  and its dangling "Upgrade derivation" ROADMAP pointer is removed; the ROADMAP 0.5-scope table no
  longer describes its shipped ✅ rows as "still open"; `just-dna-agents` is listed among related repos
  in CLAUDE.md; and the RM11/RM12 provenance-column comments read "0.4 (from the 0.5 scope)".

## 2026-07-11 — 0.4.0 (released) — round-trip hardening + audit fixes

A correctness/robustness pass over the 0.4 work, before publish. Packages bumped **0.3.0 → 0.4.0**
(the `just-dna-format` / `just-dna-compiler` versions now match the milestone the code already
implements). **`schema_version` stays `"1.0"`.** Unpublished at the time, so the `artifact.digest` changes
below are free to absorb.

- **Structured per-version authorship (RM14; docs/USE_CASES.md §5a).** A new optional
  `authorship: list[Contribution]` on `module_spec.yaml` (and `ModuleManifest`), unbundling the flat
  `authors: list[str]` + free-form `curator` (which smuggled author-kind via the `"ai-module-creator"`
  default) into three orthogonal axes (P5): `who` (identity), `role` (closed vocab
  `created`/`edited`/`audited`/`reviewed`), and `kind` — an **open, multi-valued** tag set with a
  recommended seed: a human ladder of assurance `human` → `human_expert` → `human_certified`
  (medically/board-certified), or `ai` plus a scale tag `agent`/`team`/`swarm`. There is no `hybrid`
  tag — a joint contribution is two entries (a human and an ai), so the mix is always explicit. The
  motivating case: **AI and human error-spectra overlap but differ**, so a consumer (the network
  validator, a marketplace review queue, a human auditor) routes scrutiny by author-kind — the format
  carries the kind, the consumer picks the profile (north star). It is **manifest metadata, out of
  `artifact.digest`** (like `provenance`/`logs`/`panel`), so it is additive/digest-neutral even
  post-freeze and two versions with identical annotation content but different authorship keep one
  content identity. `authoring_reference()` surfaces the `Contribution` model + `author_role`
  vocabulary + `author_kind` seed automatically. Folding the flat `authors`/`curator` in is a
  1.0-cleanup item.
- **Provenance columns on `StudyRow` (RM11/RM12; docs/USE_CASES.md §4a).** Three optional columns that
  let a *network-first* validator (RM13, a consumer — Principle 2 keeps fetching out of these libs)
  scrutinise a module without the format ever downloading:
  - **`doi`** — Digital Object Identifier, wider than `pmid` (covers preprints/books/datasets with no
    PubMed id); validated against the DOI grammar and kept verbatim.
  - **`provenance_quote`** / **`provenance_regex`** — a keyword phrase and/or regex locating a study's
    claim in the cited article's fulltext, so a validator can confirm fulltext-contains yes/no. The
    regex is a Principle-1 *declarative pattern grammar* (data, not code): compiled at author time for
    a sanity check, matched consumer-side by a linear-time/ReDoS-safe engine. The provenance analogue
    of `source_field`.
  All optional → additive/monotonic (P3/P8); materialized into `studies.parquet` with lossless
  round-trip (P7). The mandatory-`pmid` → doi-first relaxation remains a 1.0-cleanup item (a required
  field can't be demoted in-major). `authoring_reference()` picks the columns up automatically.

- **Round-trip fidelity fixes (CONSTITUTION Principle 7).** Four shapes silently round-tripped wrong
  — the happy path (rsid-keyed, uniform priority, no explicit-`False` booleans) stayed green, so the
  invariant was only nominally tested:
  - **Position-only study rows** (`rsid` null, `chrom`/`start`/`ref` set) were dropped on compile and
    made *recompile fail*; `studies.parquet` now carries the position columns.
  - **Position-only variant annotations** (gene/phenotype/category) were lost because the reverse
    lookup keyed on the null `rsid`; `annotations.parquet` now carries an explicit `variant_key`.
  - **`priority`** was fabricated on reverse (an unset row inherited the mode as an inferred default,
    turning `['high', null]` into `['high', 'high']`); it is now written verbatim.
  - **ClinVar booleans** (`clinvar`/`pathogenic`/`benign`) collapsed an authored `False` to `None`;
    they are now materialized tri-state (nullable), matching the 0.4 axes.
- **Resolver fix.** A position-only-without-`ref` variant never resolved its rsid even on an Ensembl
  hit (the result was keyed by the DB ref, the lookup by `chrom:start:None`) — keys now reconcile.
- **Input hardening.** `start` positions are `ge=0` (a negative position is a clean validation error,
  not a polars `UInt32` overflow); `weight`/`effect_size`/measure bounds/`activity_value`/
  `match_rate_floor` reject non-finite floats (`NaN`/`inf`) that broke round-trip equality.
- **Tests (+20).** New round-trip regressions for every shape above; resolver unit tests over a
  **synthetic** parquet cache (the resolver + cache were previously covered only by
  integration-gated tests that skip in CI); `aggregate_provenance`, continuous-fraction coverage-gap,
  and several untriggered validator/error branches.
- **Docs reconciled with shipped code.** ROADMAP no longer frames 0.4 as unbuilt / PGS as note-only /
  a `VariantRow.copy_number` field that was rejected; READMEs describe composed modules (not a fixed
  three-parquet artifact) and the full dependency lists; the CONSTITUTION dependency-tier goal and
  `CLAUDE.md` acknowledge `cryptography` alongside `pydantic`.

## 2026-07-10 — 0.4 quantitative tables + composed modules

Additive 0.4 schema shapes (design frozen through the 0.4 proposal + consumer round-2) with full
compiler materialization.
**`schema_version` stays `"1.0"`** — every 0.1–0.3 module keeps validating; all new tables/columns
are optional.

- **The measure→phenotype binning primitive** (`just_dna_format.binning`): one shared column
  vocabulary (`measure_kind`, inclusive `[measure_min, measure_max]`, `direction`/`clin_sig`/
  `trait_efo_id`, `conclusion`, mandatory `unresolved` sentinel, declarative `source_field` pointer)
  across per-quantity tables — `activity_phenotype.csv`, `copynumbers.csv` (+ optional
  `modifier_gene`/`modifier_cn`), `repeat_alleles.csv`, `heteroplasmy.csv` (tissue + legacy-`NC_001807`
  reference guard). There is **no `copy_number` column** — a sharp value is `measure_min == measure_max`.
- **PGx star-alleles** (`just_dna_format.pgx`): `haplotypes.csv` (variant↔allele junction),
  `allele_function.csv` (star-string verbatim identity + optional `suballele`/CN/SV conveniences),
  `diplotypes.csv` (canonicalized pair fallback, + optional `drug`/`response`/`evidence_level`), and
  **PharmGKB** `pharm_variants.csv` (single-variant drug response, `evidence_level` 1A…4).
- **PGS** (`just_dna_format.pgs`): `pgs.csv` — a PGS-Catalog-ID manifest with the ancestry-validity
  one-way-door fields (`training_ancestry`, `training_cohort`, `match_rate_floor`, `research_tier`).
- **`VariantRow` general axes** (optional): `requires_callable`, `acmg_sf`, `actionability`
  (validated against `ACTIONABILITY_SEED`) — retired from the reserved namespace.
- **Compiler materialization (RM1 + RM2).** A generic model-driven materializer compiles all nine
  table kinds to parquet with lossless, idempotent round-trip. A module **composes from optional
  table kinds**: `variants.csv` is no longer mandatory — a PGx/PharmGKB/PRS-only module compiles and
  reverses without an empty `variants.csv`; `studies.csv` is required iff `variants.csv` is present.
- **Table-level coherence is enforced at compile time.** `validate_bins` now runs inside
  `validate_spec`: **overlapping resolved bins are a compile error** (a measurement would select two
  phenotypes), interior coverage gaps a warning, and more than one `unresolved` sentinel per key
  group an error. Duplicate rows (diplotype pair, `pgs_id`, `(pharm variant, drug)`, allele-function
  allele, haplotype-defining variant) are errors — the 0.4 analog of the SNP core's duplicate check.
- **Drift-proof authoring reference** (`just_dna_format.reference.authoring_reference()` /
  `json_schemas()`, RM8) generated from the live models, plus a recommended `RECOMMENDED_COLORS`/
  `RECOMMENDED_ICONS` palette (RM9) — so MCP servers / agents render the current field set instead of
  a hand-maintained summary that drifts.
- **Shared vocabulary leaf** (`just_dna_format.vocab`): the orthogonal-axis vocabularies and
  identifier grammars moved out of `spec` into one dependency-light source of truth, re-exported from
  `spec` for backward compatibility.

## 2026-07-08 — just-dna-format 0.3.0 + just-dna-compiler 0.3.0

Additive schema + partial compiler coverage for the 0.3 columns. **`schema_version` stays `"1.0"`** —
every 0.1/0.2 module keeps validating; all new columns are optional. Design captured in
`docs/ROADMAP.md` (Planned for 0.3 / 0.4), invariants in `docs/CONSTITUTION.md`, worked drafts in
`docs/REFERENCE_EXAMPLES.md`, and the compiler coverage split in `docs/COMPILER.md`.

- **New optional columns.** `VariantRow`: `direction` (protective|risk|neutral|unknown),
  `stat_significance` (significant|suggestive|not_significant|unknown), `effect_size` +
  `effect_measure` (open vocab), `effect_allele`, `flags` (open list; reserved:
  conditional|phased|pleiotropic), `trait_efo_id` (EFO/MONDO CURIEs, matches just-prs), `clin_sig`
  (ClinVar/ACMG vocab). `StudyRow`: `stat_significance`, `effect_size`, `effect_measure`,
  `trait_efo_id`.
- **Genotype widened** to accept a single allele (hemizygous X/Y, homoplasmic MT) and a phased `A|G`
  (order-preserved), alongside the existing sorted unphased `A/G`.
- **Compiler — validator complete; derivations, boolean sync, and phase round-trip now ship** (see
  `docs/COMPILER.md`). New columns materialize into `weights.parquet`/`studies.parquet`; non-reserved
  `flags` surface as INFO via the new `ValidationResult.info`; warnings for a two-allele `MT` **or
  `Y`** genotype (X excluded — it is diploid in XX) and a `direction`/`weight` sign mismatch.
- **Upgrade derivation shipped** (`just_dna_format.derive`, `pydantic`-only leaf module). `state`(+
  `weight`) → `direction`/`stat_significance` and the ClinVar booleans ↔ `clin_sig`, exposed as
  non-mutating `VariantRow.effective_*` accessors plus a materializing `VariantRow.upgraded()` and a
  `needs_upgrade` flag — the derivation the marketplace `revalidate`/`needs_upgrade` drift flow
  consumes. `state` and the booleans **stay required/authoritative** (CONSTITUTION Principle 8 — a
  required field is never demoted inside a major); the new axes are optional with these fallbacks.
- **Lossless, idempotent round-trip** (CONSTITUTION Principle 7, now a durable invariant): a `phased`
  bit in `weights.parquet` preserves `A|G` vs sorted `A/G` through `reverse_module` → recompile, and
  compiling the same spec twice yields the same digest. Only *new computed stats* and all of 0.4
  (diplotype/copy-number/PGx star-alleles) remain out of scope.
- **Digest note:** the parquet schema now carries the 0.3 columns + the `phased` bit, so a re-compile
  changes `artifact.digest` for every module (expected on a compiler-version bump; reproducibility
  pinned by `compiler_version`; 0.3 was unpublished at the time, so the change was still free to absorb).
- **Docs:** new root `CLAUDE.md` makes `docs/CONSTITUTION.md` the mandatory first read (discoverability
  gap — the charter was only linked from README/ROADMAP, with no agent entry-point). CONSTITUTION gains
  Principle 7 (round-trip/idempotency) and Principle 8 (requiredness compatibility).
- Tests: `compiler/tests/test_v03.py` (30) + `test_v03_roundtrip.py` (6) + `schema/tests/test_derive.py`
  (13); suite 153 passed / 5 skipped.

## 2026-07-07 — just-dna-format 0.2.0 + just-dna-compiler 0.2.0

First contract release since 0.1.0. **Every change is additive and backwards-compatible**: the
`manifest_version`/`schema_version` stay `"1.0"`, and every 0.1.0 module keeps compiling and
verifying byte-for-byte unchanged (optional fields are absent, optional files never invalidate).
Consumed by just-dna-marketplace 0.5.0.

- **Structured provenance (ROADMAP #1).** New `Provenance` summary on the manifest + `ProvenanceItem`
  / `ProvenanceDoc` models. The compiler auto-discovers `spec_dir/provenance.json` (per-variant
  rationale/verdict/confidence/human-review items), ships + hashes it like a log (kept **out of
  `artifact.digest`**), and records the lean summary (`generator`, `model`, `agent_version`,
  `item_count`, `sha256`) so a catalog can flag "AI-authored · rationale available" without inlining
  text. `verify_manifest(check_provenance=True)` re-hashes it when present.
- **Ed25519 signing (ROADMAP #2 / SPEC §5).** New optional `Signature` block on the manifest, a
  `signing` module (`sign_digest`, `generate_private_key_pem`, `public_key_b64_from_pem`), and
  `integrity.verify_signature`. `verify_manifest(public_key=...)` enforces a pinned key. Signs the
  `artifact.digest` string. Adds a `cryptography` dependency to `just-dna-format`.
- **Cross-version log aggregation (ROADMAP #3).** New `aggregate` module: `aggregate_logs` /
  `aggregate_provenance` return the deduplicated union across a set of version manifests
  ("v3 provenance = v1+v2+v3").
- **ClinVar/quality stats (ROADMAP #5).** `Stats` gains `clinvar_count` / `pathogenic_count` /
  `benign_count`; `validate_spec` and the manifest now summarize the per-row ClinVar flags.
- **PMID validation (ROADMAP #6).** `StudyRow.pmid` now requires at least one extractable PubMed ID
  (bare digits or the legacy `[PMID: N]` / `PMID N; ...` forms) via a re-introduced `PMID_PATTERN` +
  `extract_pmids` helper. The string is kept **verbatim**; a dbSNP URL (no PMID token) is rejected.
  Audited against the Gen-I corpus (all digit-only) so nothing published is invalidated.
- **Gene-panel interface (ROADMAP #7) — interface only, no machinery.** New `GenePanelSpec`
  (`source`, `reference`, `reference_sha256`, `genes`, `significance`), optional on `ModuleSpecConfig`
  and mirrored on the manifest. The compiler records it **verbatim** and does not materialize
  variants from it; the app-level `gene_panel` adapter (just-dna-lite) can now declare its panel
  provenance structurally. Native compile-time materialization is a follow-up gated on a working
  ClinVar reference mixin.
- **Module logo + icon set.** `Display.icon_set` (`fomantic` | `awesome`) selects the no-logo
  fallback glyph's family. New optional `manifest.logo` (`FileEntry`): the compiler discovers
  `spec_dir/logo.{png,jpg,jpeg}`, ships + hashes it, **out of `artifact.digest`** (so a logo swap is
  a PATCH, not a new content identity). `verify_manifest(check_logo=True)` re-hashes when present.
- **`negatives` field (ROADMAP Obs #5).** Optional free-text `VariantRow.negatives` (adverse /
  antagonistic-pleiotropy counterpart to `conclusion`), carried into `weights.parquet` and the
  reverse round-trip.
- **Docs.** `ValidationResult.stats` now documents its de-facto key contract (ROADMAP Obs #1). Item 4
  (resolver provisioning) is unchanged: strictly inject-only, no network.

## 2026-07-07 — just-dna-lite: longevitymap full parity + gene-panel reference implementation

Consumer-side only; no changes to the published packages. Two Gen-I parity advances in just-dna-lite,
flagged here so `-marketplace`/`-agents` see them:

- **longevitymap reached 528/528 rsid parity** (was 518/528). The gap was not Ensembl coverage but a
  genotype-reconstruction bug: heterozygous genotypes were built by concatenating the Ensembl `ref` +
  `alt` columns, and `alt` is a `|`-joined multiallelic list. The fix pairs the module's curated
  effect allele with its single complement and parses two-base `spec` alleles directly. No format API
  change; still compiles under the 0.1.0 contract.
- **Gene-panel reference implementation** for `cardio`/`cancer` (`just_dna_pipelines.v1_port.clinvar`
  + a `gene_panel` adapter): enumerates ClinVar pathogenic/likely-pathogenic variants in the panel's
  gene list into risk-state VariantRows (het + hom-alt), `weight=None`, grounded to the ClinVar
  resource paper (PMID 29165669). Kept within the 0.1.0 contract (multi-base ACGT alleles are legal;
  structural >50 bp and symbolic alleles are dropped). This is the intended upstream reference for a
  native `GenePanelSpec` — see **ROADMAP item 7** (added the same day, with items 8/9 for the APOE
  diplotype and PharmGKB shapes). `pathogenic`/`lnewco`/`drugs` remain deferred.

## 2026-07-06 — just-dna-lite ported the Generation-I OakVar modules onto the DSL

Consumer-side only; no changes to the published packages. just-dna-lite added
`just_dna_pipelines.v1_port` (CLI `pipelines v1-port`), which downloads the Generation-I `just_*`
OakVar postaggregator modules from the `dna-seq` GitHub org, converts their curated SQLite into the
authored DSL (`module_spec.yaml` + `variants.csv` + `studies.csv`), validates and compiles them via
`validate_spec`/`compile_module`, and writes standalone modules to `data/interim/v1_port/`.

- **Curated weights are carried verbatim**; `state` is taken from the source where present and
  otherwise from the weight's sign (reproducing the v1 reporter's `get_color(weight)` behavior).
- **All emitted `pmid` values are digit-only** — see ROADMAP.md → Observations #4 for the PMID audit
  this produced (input to planned item 6; the Gen-I corpus would not be rejected by a bare-digit
  `PMID_PATTERN`).
- Five modules (coronary, thrombophilia, lipidmetabolism, vo2max, longevitymap) compile; the
  reproduced coronary/vo2max/lipidmetabolism rsid sets match the published HF artifacts exactly and
  longevitymap matches 518/528. `superhuman` (URL-only references → no PMIDs) and the non-variant
  modules (cardio/cancer/pathogenic gene panels, drugs/PharmGKB, lnewco APOE diplotype) are
  documented as gaps, not ported. No `just-dna-format` API was exercised beyond the 0.1.0 contract.

## 2026-07-06 — just-dna-pipelines repointed at the published libs

Consumer-side integration in `just-dna-lite/just-dna-pipelines`. No changes to the published
`just-dna-format` / `just-dna-compiler` packages themselves; this entry documents how a consumer
adopted them and the contract facts that surfaced.

### Added
- `just-dna-pipelines` now depends on `just-dna-format>=0.1.0` and `just-dna-compiler>=0.1.0`
  (`uv add`).
- `.json` added to `module_registry._SPEC_SUFFIXES`, so a compiled `manifest.json` is copied
  alongside the parquets on register/install (was previously dropped).

### Changed
- `just_dna_pipelines.module_compiler` is now a **compatibility shim layer** over the libs; the
  duplicated in-repo schema + transform were deleted:
  - `module_compiler/models.py` → re-exports `just_dna_format.spec` (DSL models + constants) and
    `just_dna_compiler.models` (`ValidationResult`, `CompilationResult`).
  - `module_compiler/compiler.py` → re-exports `validate_spec` / `compile_module` /
    `reverse_module` from `just_dna_compiler.compiler`.
  - `module_compiler/resolver.py` → keeps the pipelines-only `ensure_resolver_db` provisioning and
    a `resolve_variants` wrapper that provisions then delegates to `just_dna_compiler.resolver`.
  - `module_compiler/__init__.py`, `cli.py` unchanged in surface (names still resolve via shims).
- Kept pipelines tests were adapted to the libs' current `validate_spec` stats keys — see
  Contract notes below. Test **coverage** is unchanged; only expected key names changed.
- CLI `pipelines module compile` help text updated: it no longer claims to auto-download the
  Ensembl cache from HuggingFace (the lib is inject-only).

### Behavior change (downstream)
- Ensembl resolution is now **inject-only at the library boundary**: `just_dna_compiler` never
  downloads a reference. Provisioning stays in just-dna-pipelines:
  - `register_custom_module` **auto-provisions** — when `resolve_with_ensembl` is on and no cache
    is passed, it calls `ensure_resolver_db()` (idempotent: cheap when the cache exists, builds/
    downloads from HuggingFace only when absent) and injects the result. Failure degrades to
    inject-only (resolution skipped with a warning). This preserves the pre-extraction convenience.
  - Direct callers of `just_dna_pipelines.module_compiler.resolver.resolve_variants` also
    auto-provision via `ensure_resolver_db`.
  - `compile_module` itself (the library re-export) remains inject-only: called directly with no
    cache and none present, it skips resolution with a warning rather than downloading. The
    `pipelines module compile` CLI relies on an already-provisioned cache (help text updated).
  - Integration tests pass because their `ensembl_db_path` fixture provisions the default cache
    the lib then reads.

### Contract notes for other consumers (-marketplace, -agents)
- **`ValidationResult.stats` keys renamed** vs. the pre-extraction schema:
  `unique_genes → gene_count`, `study_rows → study_count`, `unique_variants → variant_count`;
  `genes` / `categories` are sorted lists with `None` filtered out. `unique_rsids` and
  `module_name` are unchanged.
- **`VALID_PRIORITIES` and `PMID_PATTERN` are not in `just_dna_format.spec`** — they were dead code
  in the original schema (no validator referenced them / the PMID validator was commented out). The
  live study rule remains "pmid must be non-empty".

## 2026-07-06 — just-dna-format 0.1.0 + just-dna-compiler 0.1.0 (initial workspace release)

Restructured the format into a uv workspace publishing the two packages, and extracted the schema +
transform out of just-dna-pipelines so they are shared, not duplicated. `manifest_version` /
`schema_version` established at `"1.0"`.

- **`just-dna-format`** (schema; `pydantic` + stdlib at this point): `spec` (the authored DSL —
  `ModuleSpecConfig`, `VariantRow`, `StudyRow`, `ModuleInfo` extending `Display`); `manifest`
  (`ModuleManifest` + `Identity` / `Display` / `Stats` / `Compilation` / `FileEntry` / `Artifact`);
  `integrity` (`sha256_file`, the `artifact_digest` Merkle root, `build_artifact`, `verify_manifest`);
  `identity` (name/namespace rules, SemVer `Version` / `parse_version`, `canonical_id`, legacy
  `vN → N.0.0`).
- **`just-dna-compiler`** (transform; + polars / duckdb / pyyaml / platformdirs / python-dotenv):
  `validate_spec`, `compile_module` (emits `manifest.json` with input + artifact hashes and the
  digest, plus `genes` / `categories` stats), `reverse_module`, and a pipelines-free, **inject-only**
  Ensembl `resolver` (never downloads).
- **Provenance logs.** Optional per-version hashed log files (`ModuleManifest.logs`) — a top-level
  `*.log` plus a `logs/` per-role subtree — copied into the module dir, hashed like `inputs`, kept
  **out of `artifact.digest`**. Absent logs never invalidate; `verify_manifest(check_logs=True)`.
- **Ensembl cache reuse.** `just_dna_compiler.cache` mirrors just-dna-lite's on-disk layout
  (`$JUST_DNA_PIPELINES_CACHE_DIR/ensembl_variations/…`, `.env`-driven); it locates a reference but
  never downloads one.
- Tests: 82 passing (schema + compiler), incl. regression tests ported from just-dna-lite; the
  Ensembl resolver tests are `@integration` (skip without a cache).
