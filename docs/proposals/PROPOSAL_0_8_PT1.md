# PROPOSAL 0.8 PT1: the bugfix round, where every decision is already made

**Status: concluded 2026-09-30.** Every item below landed on the `0.8` branch in the build order, one
commit each (RM241, RM275, RM308, RM313, RM300, RM278, RM272, RM258, RM263, RM283, RM288), and RM270's
addendum was already in place; each record is in [ROADMAP_HISTORY](../ROADMAP_HISTORY.md) with its
**Residuals**. It no longer overrides the roadmap files. Departures taken during the build are recorded
as dated addenda here (RM241) and in the items' history entries (RM241, RM258).

Drafted and decided with the maintainer on 2026-09-29, in one interview over the open items on `main`
and in [ROADMAP_0_8.md](../ROADMAP_0_8.md).

**What PT1 is.** The first build round on the `0.8` branch, limited to defects and gaps whose repair
the entries had already mostly worked out. Each item below states its decision, the build, the test
that pins it, and its legality and price. Nothing here needs a design round, so the build can run
unattended. An item that turns out to need one during the build stops there and becomes a new `RMn`,
never an improvised design (RELEASE_CYCLE § Minors, step 4).

**Why these are on `0.8` and not `main`.** Every item adds public surface: a warning code, a result
field, a manifest field, a CLI option, a public constant, or a changed default on a public function.
`main` is patch scope only. Three of the items add a member to `VALID_WARNING_CODES`, which a reader
pinned to an older `just-dna-format` refuses (`ModuleManifest.warnings_summary` validates its keys
against the closed set). **So 0.8 has an old-reader break of the INTEGRATION_0_7 kind.** The first item
that adds a code also opens `docs/INTEGRATION_0_8.md` and records it there, and each later code adds
its line.

**Precondition, done first.** `main` was merged into `0.8` on 2026-09-29 as `0b4f8f0`, before this
file was written. The branch had forked at `067b520` and was 109 commits behind, so it knew none of
RM265–RM309. RM310 was filed on `main` afterwards and reaches `0.8` at the next sync.

---

## What the branch already carries

These shipped on `0.8` before this round, uncut. The branch keeps them, and no PT1 item touches them:
RM256 (an abstract-only miss published as a checked quote), RM257 (PMC's BioC service as the fulltext
rung), RM259 (a GRCh38 position mapped to the genes worth asking the Atlas about), RM260 (the
`compiler`, enricher `cli` and `enrich` modules split into packages behind re-export shells), RM262 (a
DOI lookup names the paper it found), and RM264's docs half.

## Out of scope, and where each item went

- **Patch-class items stay on `main`** and go into the next patch, by *version by omission*: RM285,
  RM290, RM307 and RM309, each still owing its own small decision. RM310, found while vetting RM288
  for this round, was handed to the patch seat on 2026-09-29.
- **The indel-placement cluster is PT2.** RM304 (record the VRS version), then RM267 (a second witness
  for every placement), RM270 (`vrs_id` onto the parquets), RM292 (a check states its witness) and
  RM305 (ClinVar-GKM as that witness). These are the high-severity items of the release. They are held
  back because they are one design and need an interview of their own, not because they matter less.
  Leaving them out of PT1 does not mean they were overlooked.
- **Schema design goes to PT2 or later:** RM265 (`panel:` provenance), RM266 (the phase-confusable
  set), RM284, RM286, RM287, RM294, RM296, RM298, RM302, RM306, RM281, RM282, and everything already
  in ROADMAP_0_8.md apart from RM241.

## Build order

1. **RM241**, first, because it widens the round-trip test that every later item's compile changes
   run through.
2. **RM275, RM308, RM313**: the three compiler warnings. The first of them to land opens
   `INTEGRATION_0_8.md`.
3. **RM300, RM278**: manifest counts and the CLI flags that stamp the manifest.
4. **RM272, RM258, RM263, RM283, RM288**: enricher-only, independent of each other. Any order works.
5. **RM270's addendum**: a docs line, which can land with anything.

Each item is one commit carrying its code, its test, the docs it changes and its CHANGELOG line
(`@a-closure-states-its-residuals`: each closure states its **Residuals**).

---

## RM241, widened: `reverse` rebuilds every authored field the artifact carries

**Decided:** widen it, in PT1. The entry's option (c) would have kept the gap and only warned about it.

**What the investigation found (2026-09-29).** P7 says `compile → reverse → compile` preserves *every
authored value*. The round-trip test enforces this by comparing `content_signature` and
`artifact.digest` (`test_reference_examples_roundtrip.py`), and both of those exclude `manifest.json`
by design. So no authored value that reaches only the manifest can fail the gate. Run on
`hfe_hemochromatosis`, both digests held equal while the recompiled manifest had:

- lost `weighting`;
- replaced all five `display` fields (`title`, `description`, `report_title`, `icon`, `color`) with
  name-derived defaults, although the manifest holds the real ones;
- lost the README, although the artifact directory ships `README.md`.

`reverse` already reads two fields from the manifest, `identity.version` (RM103) and `genome_build`
(the 2026-08-06 audit). Each was added separately, after an incident, and nothing links the
`ModuleConfig` fields to what `reverse` rebuilds. That is the list shape
(`@registry-completeness`). COMPILER.md § Reverse also contradicts itself: it says reverse reads "the
parquet artifact only (never `manifest.json`)" and then lists two fields it reads from there.
**The charter needs no amendment.** P7 already says the right thing, and the enforcement fell short of
it.

**The build.**

- `reverse_module` rebuilds every `ModuleConfig` and `ModuleInfo` field the artifact carries:
  `module.title`, `description`, `report_title`, `icon`, `icon_set`, `color` (from `manifest.display`),
  `license`, `weighting`, `authorship`, `authority_precedence` and `panel`. `version` and
  `genome_build` already work this way and are folded into the same reader. The manifest carries no
  `defaults`, so `defaults.curator`/`method` stay recovered by `_most_common` over the rows, and they go
  in `EXCLUDED` with that reason.
  `README.md` is copied byte for byte from the artifact directory when present, and checked against
  `manifest.readme.sha256`.
- Precedence is the same for every field: explicit argument, then manifest, then today's fallback for
  a bare parquet directory. `icon` and `color` change their defaults from `"database"` and `"#6435c9"`
  to `None`, so "not passed" can be told apart from "passed the old default". The fallback values
  themselves do not change. The CLI `reverse` flags follow suit.
- `panel:` is safe to re-emit. RM4 dropped compile-time materialization in 0.6, so the block is
  record-only. Probed on 2026-09-29 with `test_v02.py`'s spec: with and without the block, the same
  `artifact.digest` and `content_signature`, and the same rows. On recompile it fires
  `panel_block_deprecated` again, which is correct because the module did carry it. RM265 owns that
  warning.
- `verification.json` stays excluded, with its existing warning. It is not a `ModuleConfig` field.

**Tests.**

- **The registry walk.** A test walks `ModuleConfig.model_fields` and `ModuleInfo.model_fields` and
  asserts equality between the walked set and `RECONSTRUCTED ∪ EXCLUDED`. `EXCLUDED` maps each name to
  its reason. A new spec field then fails the suite until someone decides it.
- **The round-trip gate compares the manifest's authored projection**, not only the two digests. The
  projection is `display`, `license`, `weighting`, `authorship`, `authority_precedence`, `panel`,
  `genome_build`, `identity.version` and `readme`, compared across laps in
  `test_reference_examples_roundtrip.py`. Show it failing on the current `reverse` before the fix
  (the AI-test rule: prove a test would have caught the bug).
- The corpus sets `weighting`, `license` and `authorship` once each, and `panel` and
  `authority_precedence` nowhere. So one test copies an example into `tmp_path`, sets **every** field,
  and asserts the projection survives two laps. The README test asserts the copied bytes hash to
  `manifest.readme.sha256`.

**Docs.** COMPILER.md § Reverse loses "never `manifest.json`" and its *Normalized* bullet shrinks to
what is still normalized (the bare-directory fallbacks). The "NOT reconstructed by the lossy
`reverse_module`" sentence goes, both from the `authority_precedence` field descriptions (spec and
manifest) and from SCHEMAS.md. FAQ gets an entry: *"my reversed module lost its display metadata"*.
AGENT_NOTES gets the lesson, and CLAUDE.md one line: **a round-trip gate made of digests cannot see an
authored value that lives only in the manifest; compare the authored projection.**

**Legality and price.** No field is added, removed or retyped. `reverse` writes more of a spec it
already wrote. The changed defaults loosen a parameter's type (`str` to `str | None`), which is minor
surface. Price: nothing authored, nothing derived.

**Addendum 2026-09-30, from the build.** The manifest *does* carry the defaults, as
`manifest.curator`/`method`, so the premise above was wrong. The row-mode guess also produced
`unknown` on every table-only module, which has no `weights.parquet` to take a mode over. Both are
now read from the manifest, with the mode as the bare-directory fallback, and only
`defaults.priority` is in `EXCLUDED`. The logo is copied back beside the README, since it is shipped
and hashed the same way.

**Residuals.** The `vrs_id` loss found in the same probe is RM270's (below). `defaults.curator/method`
stays a normalization, stated in the *Normalized* bullet, because the manifest does not carry it.

## RM270, addendum only: a round trip drops every `vrs_id`

**Decided:** evidence for RM270, not a new item. RM270 stays in PT2.

In the same `hfe_hemochromatosis` probe, `compilation.vrs_alleles_identified` fell from 10 to 0 of 12
after one round trip. `reverse` rebuilds `resolution.csv` from the parquets, and no variant parquet
carries `vrs_id`, so the recompile records the alleles as unidentified. P7's own remedy ("the artifact
is missing a field, not the spec") is RM270's candidate 4. PT1 adds this paragraph to RM270's entry
and adds nothing else.

## RM275: a warning for two contradicting rows under one merge key, in the seven unkeyed fact tables

**Decided in the entry (2026-09-27); nothing left open.**

**The build.** This is **a separate check beside `_TABLE_DUPE_KEYS`, never an entry in it.** The
entries there refuse, and their predicate is "the key repeats". This one warns, and its predicate is
"same merge key, different values". Registering these tables in the refusing registry would tighten
every module published on `main`, which is exactly the P3 break the entry warns against. It covers
`frequencies`, `gene_metrics`, `literature`, `gene_validity`,
`clinical_assertions`, `gwas_effects` and `expression_effects`. Each key is
**derived from `base.merge_key`** (`@suppression-from-merge-key`), never a second tuple. "Duplicate"
means **both stated and different** under that key (`@absent-is-not-different`). A repeated identical
row is not a finding, and neither is `gene_validity`'s deliberate second row when the source's
classification drifts (the comment at `gene_validity.py`'s merge). Measure that last case before
settling on the rule: if the drift rows differ only in a column outside the merge key, they never
collide; if they differ inside it, the rule must name the column that tells them apart.

- New code **`fact_rows_contradict`**, a **warning in both modes**. It is aggregated per table by
  reason, with a count and examples. It fires from both `validate` and `compile`, deduplicated at
  the extend site (`@first-fact-check-on-both-sides`).
- Add a line to the 1.0 cleanup tracker: *refuse at 1.0*, because refusal is a tightening (P3).
- Open `INTEGRATION_0_8.md` with the old-reader line for this code.

**Tests.** The entry's reproduction, run live: `hboc_palb2` with its first `gene_validity.csv` row
duplicated and `classification` changed from `definitive` to `refuted` must warn. An identical
duplicate must not. A registry equality `_FACT_TABLES == keyed ∪ exempt-with-reason`. A
`features/` scenario, and the phrase pinned in COMPILER.md's warning catalogue.

**Legality and price.** One vocabulary member, additive (P3); a derived check, no column.

## RM308: the conclusion-genotype check at `validate` and `compile`

**Decided in the entry; nothing left open.**

**The build.** Code **`conclusion_names_other_genotype`**, emitted by `validate_spec` and
`compile_module` (`@parity-by-check`) from the existing
`just_dna_compiler.conclusion.conclusion_genotype_mismatches`. It is a warning in both modes: 10 of 10
measured over one corpus does not justify a refusal. Aggregate it by reason. The hint and `lint_rows`
keep their own emission.

**Tests.** The RM279 fixtures: a swapped pair warns under a `--strict` compile that stays green.
Parity is asserted by check. A `features/` scenario, the catalogue phrase, and the INTEGRATION_0_8
line.

**Legality and price.** One vocabulary member; nothing authored.

## RM313: retire RM57's QUAL warning, which states the spec backwards, and say what is true instead

**Added 2026-09-30 by the maintainer**, after the round was written: *"to 0.8, retrofit it into
bugfixes"*. Found by the just-vcf session and confirmed against the code the same day. The VCF 4.5
audit (`docs/probes/VCF_4_5_AUDIT.md`, its finding 2) re-read the spec
independently and agrees.

**What is wrong.** VCF §1.6.1 item 6, identical in 4.4 and 4.5: QUAL is the Phred confidence in
whatever ALT asserts. Where ALT is `.`, it is −10log10 P(variant), so a high QUAL is a **confident
reference call**. The 4.4 audit read it as *"almost certainly variant"*, and RM57 shipped that
reading. `quality_floor_inverted` fires on every `requires_callable` row whose `quality_from` names
QUAL and tells the author the opposite of the spec. Its remedy recommends GQ, which Table 2 conditions
on the site being variant, so that advice is ungrounded too.

**What is true, and is what the replacement says.** A `requires_callable` row's evidence is a
reference record, usually a `<*>` block, and such a block conventionally carries QUAL `.`. A QUAL floor
there is a check that **cannot run** (`@unreachable-not-absent`): the row either always withholds or,
if the consumer skips a missing value, is never gated. On a joint-called site record QUAL is also a
site-level number, not this sample's. Neither is an inversion.

**Decided (assumption stated, per the maintainer's "retrofit it"):** both halves ship together on `0.8`.

**The build.**

- **Retire `quality_floor_inverted`.** Nothing emits it any more. It **stays** in
  `VALID_WARNING_CODES`, because removing a member is major and published manifests carry it. The
  registries that walk the codes (the emission-site walk in `test_warning_codes.py` and
  `test_feature_corpus.py`'s equality) gain a declared `RETIRED_WARNING_CODES` set in `vocab`, each
  member with its reason, so that "in the vocabulary but emitted nowhere" is a stated state rather than
  an exemption. `QUAL_INVERSION_PHRASE` goes, and COMPILER.md's catalogue keeps the phrase under a
  *retired* heading, because a consumer may still grep old manifests for it (`@warning-text-is-api`).
- **The replacement code, `qual_floor_on_reference_evidence`**, is a warning in both modes on the same
  trigger: `requires_callable=true` with `quality_from` naming QUAL, matched as `_quality_fields`
  already matches it. The message says the floor states a site-level confidence that a reference block
  usually leaves missing, so on the record this row is decided from it either cannot be read or is not
  about this sample. It recommends **no** field. What a caller writes on its reference blocks varies,
  and the spec reserves no per-sample reference-confidence key, so naming one would be the same
  mistake again. Aggregated, with a count and examples, as the old one was. It fires from both
  `validate` and `compile` (`@parity-by-check`).
- **Correct every place that states the claim:** the `VariantRow.quality_from` description in
  `spec.py`, the docstring of the check, SCHEMAS.md, COMPILER.md's catalogue, the `features/` scenario,
  and `test_vcf_conformance_warnings.py`. The 4.4 audit already carries a dated correction note, and
  its body stays as evidence.
- **INTEGRATION_0_8.md:** one line for the new code, and one saying the old code is retired, with
  the reason that it misstated the spec, so a consumer who keyed on it knows why it stopped.

**Tests.** Show the current test asserting the false claim before changing it. Then:
- the old code is never emitted over the reference corpus and a synthetic `requires_callable` + QUAL row;
- the new code fires on exactly that row, and not on the same row without `requires_callable` or
  with `quality_from=FORMAT/GQ`;
- `validate` and `compile` parity;
- the retired set is disjoint from every emission site the walk finds, and a subset of
  `VALID_WARNING_CODES`.

**Legality and price.** The retirement adds and removes nothing from the contract (P3); a code that is
no longer emitted still validates in every reader. The replacement is one new vocabulary member,
minor-legal, and it is what puts this item on `0.8` rather than `main`. Nothing authored.

**Residuals.** The 4.5 audit's finding 1 touches the neighbouring `callable_from` text. It says a
reference block's end is read from each sample's FORMAT `LEN` in 4.5, with INFO `END` now the maximum
across samples. That is a separate correction and is not folded in here; it is left for the decision
on the 4.5 audit's candidates.

## RM300: per-tier ClinVar counts in the manifest

**Decided:** a mapping, at both grains.

**The build.** Add two optional `manifest.Stats` fields, each `dict[str, int]` keyed on
`VALID_CLIN_SIG` members:

- `clin_sig_counts`: genotype rows per tier, the grain `pathogenic_count` already uses;
- `clin_sig_variant_counts`: distinct `variant_key` per tier.

Count from the **effective** `clin_sig` (`clin_sig_from_booleans` fills a boolean-only row where it
can). **Emit every `VALID_CLIN_SIG` member, zeros included**, in the vocabulary's sorted order. The
vocabulary is closed and fixed per `compiler_version`, so an absent key would be ambiguous between zero
and not counted. A row with no derivable tier is counted nowhere in the mapping, and its count stays
readable without a field (`@vrs-coverage`, `@derived-not-stored`): `Stats` already holds both totals,
`weights_rows` and `variant_count`, so the unstated count is the total minus the mapping's sum. The
field descriptions say so. `pathogenic_count` and `benign_count` keep their meaning.

**Tests.** Over the reference examples, the per-tier sums reconcile with the folded counts
(`pathogenic` + `likely_pathogenic` equals `pathogenic_count` where every row carries `clin_sig`).
Expected values are computed at runtime from the parquet, never copied. Ordering is pinned.

**Legality and price.** New optional manifest fields, outside `artifact.digest`. Near zero (P9).

## RM278: `compile --ensembl-reference` and `--ba1-threshold`

**Decided:** add both.

**The build.** Two options on the `compile` command, passed straight through to `compile_module`.
`--ba1-threshold` is a float and inherits the API's default. `--ensembl-reference` takes whatever type
`compile_module` does for the value it stamps into `manifest.compilation.ensembl_reference`. Extend
`test_cli_parity.py` to assert that the `compile` options equal `compile_module`'s parameters minus a
declared, reasoned exclusion set, so the next parameter cannot drift unweighed. COMPILER.md's sentence
about the gap goes.

**Legality and price.** Two options on an existing command. Free.

## RM272: `EnrichmentResult` fields for rsIDs answered but withheld

**Decided:** two lists, one per state.

**The build.**

- **`unanchored_rsids`**: live Ensembl answered with a one-sided indel whose anchor base could not be
  read (RM268). This is transient, and a re-run can fix it. The set already exists in the enrichment
  pass; only the result field is missing.
- **`non_nucleotide_rsids`**: every allele Ensembl gave is a non-base (`dbSNP_novariation`, an `N`
  run; RM271). This is permanent. RM271 filters it inside `ensembl.py` and only logs it, so the rsIDs
  have to be passed up to the result.
- Each is documented with its remedy, beside `unreachable_rsids`, `unconsulted_rsids` and
  `allele_mismatches`. The log lines stay as they are.

**Stated assumption, for the builder.** RM274's `reference_rejected` (a locus dropped because the
reference shows a different event of the same size) is a third state, permanent, and per **locus**
rather than per rsID. It gets its own field, `reference_rejected_loci`, and is not folded into the
second list. Two causes with different evidence behind them go side by side and are never merged. If
building this shows the field has no reader, drop it and record why.

**Tests.** Each state is driven through its real path with a stubbed client. Each rsID is asserted to
appear in exactly one of the result lists (the lists must be disjoint), and still in `unresolved`.

**Legality and price.** New fields on a result dataclass. Free.

## RM258: record how the fulltext question ended, and ask again only what went unanswered

**Decided:** the entry's candidate 3. A null on a row written before the column existed means **ask
once**.

**The build.**

- `EuropePmcClient.fulltext` and `PmcBiocClient.fulltext` stop returning one `None` for two answers. A
  404 or an explicit "no copy" is **absent**. A 5xx, a transport failure or a non-JSON 200 raises the
  lane's `*Unavailable` type, retried then translated (`@client-exception-contract`). Before retyping,
  grep for handlers that depend on the `None` (the rule's fourth line).
- `literature.csv` gains an optional derived column, **`fulltext_status`**, with a closed vocabulary
  `retrieved | absent | unreachable`. Audit the name against the reserved namespace (P5).
- In the pass's `wanted` rule, a row whose status is `unreachable` or null is asked for its fulltext
  again. The other fields keep merge-not-clobber (answered is per field, `@answered-is-not-absent`).
  A re-ask that answers overwrites `quote_source`, the quote counts and the status on that row. A
  re-ask that fails again leaves the row as it was, with `unreachable`. `--rederive` keeps its own
  rule (`@rederive-never-shortens`).
- The fix flips `test_every_way_bioc_has_no_text_reads_as_not_retrieved`, which pins today's defect:
  its 500 arm must now write `unreachable`, and the next run must ask again.

**Tests.** 404 → `absent`, never re-asked. 500 → `unreachable`, re-asked, and healed when the second
run answers. Null → asked exactly once. A lap-2 equality on a run with nothing left to ask
(`@empty-work-is-a-path`). The pacing count: one request per re-asked row per run, never more.

**Legality and price.** An optional column on a derived CSV: minor-legal, half cost (P9). If the column
reaches `literature.parquet`, it is a new optional parquet column and near free.

## RM263: a DOI's PMID, through Europe PMC

**Decided:** an advisory in RM50's shape. A title disagreement is two `info` findings side by side;
more than one PMID withholds the advisory.

**Why a title disagreement is not a warning.** Probed on 2026-09-29: a DOI names one paper, but its two
title records can differ while naming the same paper. `10.1055/s-0041-111184` is *Agitation und
Aggression in der Psychiatrie* at Crossref and *[Agitation and Agression in Psychiatric Patients].* at
PubMed, which is PubMed's bracketed translation. `10.1055/s-0041-111136` is *[Not Available].* at
PubMed. A warning would fire on every non-English paper.

**The build.**

- `EuropePmcClient` gains a DOI search (`DOI:"<doi>"`, `SRC:MED`), under the same client contract.
- `lookup_citation` on a DOI with no PMID returns the PMID as an advisory (`applied=False`,
  `refusal="redundancy_bearing"`), then asks PubMed which paper that PMID is, as `_check_pmcid` does.
- The Crossref title and the PubMed title are reported as two `info` findings, unconditionally, so the
  curator sees both. No string comparison decides anything.
- **Two or more PMIDs** for one DOI: no advisory, and a finding naming every PMID
  (`@multiplicity-is-a-finding`). **Zero**: the lookup says Europe PMC holds no record for the DOI,
  which is not the same as saying PubMed has none (`@absence-is-weighted-by-the-base-rate`).

**Tests.** Network tests behind `JUST_DNA_NETWORK_TESTS=1`: `10.1038/ng826` → `11788828` (Enattah 2002,
not in PMC; this is the case the NCBI converter misses) and one of the Thieme DOIs above for the
two-title shape. Offline stubs cover the zero and multiple arms.

**Legality and price.** A new client method and new lookup output. Nothing authored.

## RM283: when a ClinPGx archive has gone quiet

**Decided:** record `Last-Modified` for every archive. A finding fires at **180 days or more behind
the newest sibling**. It reports and never refuses.

**The build.** `clinpgx_build` sends `HEAD` to the lane's archive and to a fixed, named list of sibling
archives on the same host. Each response's `Last-Modified` goes into `release.json`, beside the
`CREATED_*.txt` date. The sibling list is a module constant with a comment saying where it came from
(RM166's inventory). When the lane's own archive is at least 180 days older than the newest sibling,
the build result carries a finding and logs it once. A sibling that does not answer is
could-not-ask: it is counted and named, never treated as old
(`@one-registrys-outage-may-not-speak-for-another`). Staleness is not a `strict` matter
(`@a-source-recuring-is-not-a-strict-matter`). The URL audit stays a manual step in the lane's
rebuild runbook, because ClinPGx's HTML routes are JavaScript shells (RM175).

**Tests.** Stubbed `HEAD` responses: fresh, stale by 181 days, a sibling missing its header, a sibling
that fails. RM175's real incident (fourteen months) as the named fixture.

**Legality and price.** New fields in a published snapshot's `release.json`: minor, near free.

## RM288: each builder exports its own error family

**Decided:** a callee-owned tuple. No base class, and no hand-written list at the call site.

**Why, and what changed the answer.** A base class makes a caller's `except` order load-bearing
(`@client-exception-contract`). A list at every call site drifts, and on 2026-09-29 it had:
`caches._rebuild_cpic` named `CpicBuildError` and forgot `CpicError`, so a CPIC outage escapes
`cache rebuild` and every lane after it goes unbuilt (**RM310**, filed on `main` as a patch and handed
to the patch seat). A
tuple exported by the callee keeps both properties: the callee owns the list, and `except` order does
not matter.

**The build.** `cpic_build.ERRORS`, `pharmvar_build.ERRORS` and `pgx_draft.ERRORS`, each a
`tuple[type[Exception], ...]` naming every type the surface can raise. Every caller (the CLI handlers,
`caches._rebuild_*`, `pgx.py`) writes `except <module>.ERRORS`. `_DRAFT_PRECONDITION_ERRORS` becomes
the draft surface's exported tuple, or is built from them.

**Tests.** An AST walk refuses any handler that names a member of a family without using the family's
tuple. The three surfaces **stay** in `test_pass_exception_contract.py`'s exempt set: that test asserts
each pass raises *one* documented type, and a declared family is a different contract. The exemption
comment is rewritten to state RM288's decision rather than defer it. A new test drives each surface
with stubs and asserts that everything it raises is a member of its `ERRORS`. RM310's `CACHE_LANES`
walk already covers the rebuild side.

**Legality and price.** Three new public constants. Free.

---

## What "done" looks like for PT1

- Every item above is built, with its test shown failing on the code before it (for a defect item) or
  shown asserting the decided set (for a surface item).
- `INTEGRATION_0_8.md` names all three new warning codes as the old-reader break, and says that
  `quality_floor_inverted` is retired and why.
- The full suite, `ruff format --check`, and `properdocs build --strict` pass at the last commit.
- Each item's record has moved to ROADMAP_HISTORY with its **Residuals**, and its RM_TOC row is updated.
- What the build found is filed, not folded in, unless it is the same item (RELEASE_CYCLE § Minors,
  step 4).
