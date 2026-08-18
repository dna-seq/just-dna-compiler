# Changelog

Shared change log for the just-dna module format/compiler ecosystem. Because
`just-dna-format` + `just-dna-compiler` are consumed by **just-dna-pipelines**,
**just-dna-marketplace**, and **just-dna-agents**, cross-repo integration changes are recorded
here so parallel work in the other repos isn't surprised. Newest first.

**A version heading names the release a change will ship in, not a development batch.** Entries dated
2026-08-03 carried a `0.5.1:` label for a while; at the time nothing 0.5.x had been published, all three
packages sat at `0.5.0`, and that work therefore shipped **as 0.5.0** — the label was relabelled to
match. Keep it that way: a number here should answer "which published version introduced this", and a
batch inside an unpublished release is not a version.

**0.5.0 is published** — tagged `v0.5.0` and released to PyPI on 2026-08-07 (`just-dna-format`,
`just-dna-compiler`, and `just-dna-enricher`, the last being that package's first release). Everything
below dated 2026-08-07 or earlier is in it. The next heading is therefore a real new number: additive
work — including a **new optional column or table** — is **0.6.0**, while **removing** a column,
**promoting** one to required, **retyping** one, or changing what an identity key *means* is **1.0**.
That is Principle 3 as amended on 2026-08-11; the earlier "anything that moves `artifact.digest` is
1.0" rested on a premise that expired when `content_signature` took over content identity in 0.4.1.
See [ROADMAP § 0.6](ROADMAP.md#06--what-a-minor-permits).

**That rule is about the schema surface, and the three packages version independently — so
`just-dna-enricher` can take a patch.** "Additive work is 0.6.0" sorts changes by what they do to a
compiled module's identity, which is a *format/compiler* question. Work confined to the network tier
touches no parquet, no model and no manifest field, so it can ship as an enricher patch release while
format and compiler stay where they are. The first of those is **`just-dna-enricher` 0.5.1**, whose
content is [RM38](history/ROADMAP_HISTORY_PRE_0_6.md#rm38--a-cache-for-every-gated-source-the-hosted-enricher) — a cache for the
licence-gated sources, so a hosted enricher stops fetching them live per request. This does **not**
reopen the paragraph above: that one is about labelling a batch inside an *unpublished* release, which
0.5.1 is not — 0.5.0 shipped, so 0.5.1 is a real next number rather than a name for work in progress.
**0.5.2 follows the same rule** and stretches it by one package: its ClinVar-drafting, query-shape and
cache-location work is enricher-only, and the one compiler change (a warning when
`resolve_with_ensembl=False` discards an injected `resolution.csv`) writes no parquet and moves no
signature, so `just-dna-compiler` took the patch alongside while `just-dna-format` stayed at 0.5.0.

## 2026-08-18 (latest) — the outward half of the gist sync, and the off-switch that was not one

**No package is cut for this.** Loop maintenance again: the only executable change is to
`.claude/watch-suggestions.sh`, which ships in nothing, and the rest is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md) plus the published copy of the loop. The live
consumer inbox is empty and stayed empty, and the ledger read all-`current` over both history files
before and after.

**The sync is cheaper to start: check a digest, fetch only when it moves.** Pulling both scripts from
the gist and diffing them at the head of every pass is work for nothing in the normal case — the
upstream changes rarely, and the diff is deliberately noisy because the published copy is
parameterized. The gist's own revision id is a public digest of the whole thing, so one unauthenticated
API request answers the only question the sync-in asks first. The baseline lives in the runbook rather
than a side-car file, on the same reasoning as the in-document ledger, and it is pinned to a revision
established rather than assumed: the gist had not moved since 2026-08-16, and both local adoptions are
later, so the revision `e9a538e` read is the one it still served.

**The standing outward debt is discharged.** The 2026-08-17 entry above closed naming it — the
watcher's branch-pause had not reached the gist — and the digest check joined it, since a change to the
*pattern* belongs in the published copy by that document's own rule. Both are in gist revision
`bd793a8c`, genericized: the branch-pause derives its work tree from the watched file rather than from
the script's own layout, and never fires outside a git work tree at all, because a generic adopter may
be running with no repo.

**Porting it forced a correction the pattern had been carrying.** The gist's "why not git" gave two
fatal reasons, one being *the loop must not commit* — which stopped being a property of the design here
when the unattended permit was granted, and a watcher that pauses precisely **because** the loop commits
cannot sit in a document denying that it does. The surviving reason is fatal alone (a reporter may
commit their own addition, and a diff-based ledger then sees nothing), so the design holds; the expired
reason is recorded rather than deleted, because a design defended by two reasons is worth re-checking
when one of them goes.

**And the port found a real defect in our own watcher.** `BRANCH=${BRANCH:-main}` treats an explicitly
empty value as unset, so `BRANCH=` — the one thing anybody would type to switch the pause off — restored
`main` and switched it on. Fixed in both copies to `${BRANCH-main}`. It surfaced only because the
off-switch was *run* in a sandbox rather than read: the two spellings behave identically for every value
except the empty one, which is the value no test reaches by accident. The same rehearsal covered
`main → branch → main`, an edit written while paused arriving in the resume event, and a non-git
directory never pausing.

## 2026-08-18 — 0.6.2: a pass owes its own exception type, not its client's (S37 / RM101)

**`just-dna-enricher` 0.6.2 — cut and tagged `v0.6.2`. A partial cut**: `just-dna-format` and
`just-dna-compiler` have no diff since `v0.6.1` and stay there, which is the normal shape here (schema
sat at 0.5.0 across two compiler releases). The additions are minor-legal — six new public exception
classes beside the existing ones, nothing removed, promoted or retyped — so a patch number carries
them without straining P3.

**What a caller gets.** A pass now raises **its own** type, and where the reason is "the source could
not be reached" it raises an `*Unavailable` subclass of that type — `FrequencyUnavailable`,
`LiteratureUnavailable`, `GeneMetricsUnavailable`, `IdentifierUnavailable`, `ClinGenUnavailable`,
`GeneValidityUnavailable`, after the `AcmgListUnavailable` that already had this shape. Every one is a
subclass, so an existing `except <Pass>Error` catches everything it did before (P3) and the narrower
catch is new capability rather than a migration. The client's exception is chained onto `__cause__`.
The table is in [ENRICHER § Exception contract](ENRICHER.md).

**What was broken.** Five call sites held a client in `try: … finally: close()` with no `except`, so
`GnomadError` left `enrich_frequencies`/`enrich_gene_metrics` and `EutilsError` left
`enrich_literature`/`check_rsids`. The handler a consumer was told to write did not fire. **Our own
CLI had it too**: `just-dna-enricher frequencies` promises `FREQUENCIES FAILED: <reason>` and exit 1,
and on a gnomAD 503 it printed nothing and let the exception out.

**And a third client was still leaking `httpx` after RM97 said that was over.**
`OntologyClient.trait`/`.gene` kept the exact unrepaired shape — `raise_for_status()` in the callers,
`HTTPStatusError` in neither retry list. RM97's coverage guard walked a hand-written tuple of eight
module names and `identifiers` was not one of them; both guards now walk the package, so a new client
or pass fails the suite by name.

**Two conflations split.** `ClinGenError` and `GeneValidityError` each covered "the source could not
be fetched" *and* "the local CSV will not parse" — opposite histories, previously separable only by
reading `exc.__cause__`. Only the fetch path is now `*Unavailable`.

**If you catch the client's type today, you can stop** — but check first whether you catch it
*instead of* the pass's type, because that is the form that stops firing. Catching both, which is what
just-dna-registry did as a workaround, keeps working unchanged.

Suite: 2738 tests. Every repair was demonstrated failing on the unrepaired code before being asserted.

## 2026-08-18 — 0.6.1: nine defects a code-first reading of the documents found, and RM88 closed

**`just-dna-format` + `just-dna-compiler` + `just-dna-enricher` 0.6.1 — cut and tagged `v0.6.1`.** A
documentation pass regenerated SCHEMAS/COMPILER/ENRICHER from the source alone, read the result against
the shipped documents, and asked which of the two was wrong. Eight times it was the code (RM93–RM100,
filed as eight items; RM100 grew a fifth defect while the first four were being fixed, so nine
defects in eight entries). **No schema surface moves, `schema_version` stays `"1.0"`, and all sixteen
reference examples recompile byte-identical** — verified against a worktree at `5c1ea87`, the state
before the first fix, rather than inferred from the absence of a model change. The suite went
**2568 → 2722**, and every new regression test was demonstrated failing on the pre-fix tree before
being claimed as a guard. The seven doc commits that landed after `v0.6.0` ride along, as the entry
below said they would.

**Every one of the eight broke a rule this repo had already written down, and in four of them the file
carrying the violation also carried the rule — sometimes in an adjacent comment.** That is the finding
underneath the release rather than a remark about it: `@validate-refuses-all`, `@vocab-separator-slip`,
`@registry-completeness`, `@client-exception-contract`, `@unreachable-not-absent`,
`@sidecar-name-and-place`, `@credential-where-read`. **The gotcha book is not the thing that catches a
regression.** So the durable half of every item is a test, and in six of the nine that test walks a
registry rather than a list.

**Five of the nine are the same failure at five scales: a hand-kept list standing in for a registry.**
`_ALL_MODELS` missing five row models; `test_validate_agrees_with_compile` missing four of the seven
fact tables; `net.py`'s "nine policies" against a tree of twelve; a sidecar resolver three passes did
not call; a client contract two of four clients honoured. None is a hard bug in a clever place — all
five are a number or a list somebody had to remember.

**The two parity gaps (RM93/RM94, compiler).** `_check_study_effect_alleles` sat inside `validate_spec`'s
`if variants:` block and ran unconditionally on the compile side, so it never ran for the composition it
was written for — a table-only module with `studies.csv` and `resolution.csv`. `_check_frequency_arithmetic`
was never called from `validate_spec` at all, and its integer half returns errors, so a plain `validate`
blessed a module a plain `compile` refused. Both reproduced on real specs first. The compile-side
`_check_p_value_num` re-run also published its warning twice into `manifest.compilation.warnings`;
the re-run was examined and **kept**, because the inner `validate_spec` always runs in best_effort and
the second pass is the only thing that lets `--strict` escalate.

**The vocabulary and registry items (RM95/RM96, format).** A closed vocabulary is supposed to accept
`-` for `_` **and store the declared member**; three validators called `check_vocab` for its raising
side effect and returned the raw input, so `measure_kind="copy-number"` was stored inside
`content_signature` and then rejected by every subclass. And `_ALL_MODELS` was missing `ResolutionRow`,
`FrequencyRow`, `GeneMetricsRow`, `LiteratureRow` and `GwasEffectRow` — five, where the filing named
three. Admitting them turned the existing guards on and found **seven** more fields enforcing a
vocabulary without declaring it.

**One consumer-visible surface grows, deliberately:** `authoring_reference()`, `describe`,
`requirements` and `json_schemas()` render **28 models where they rendered 23**. Additive under
Principle 3, and the trade is stated where the registry is — a wider printed reference in exchange for
guards that cannot miss a model again. `INTEGRATION_0_6 § 7` tells a consumer so.

**The four network-tier items (RM97–RM100, enricher).** `gnomad` and `eutils` leaked raw `httpx`
exceptions past handlers written to catch this tier's own error types, while `cpic` and `pharmvar` had
carried the repair *and* its narrative for a release. Two `--offline` paths wrote `not_found` naming a
cache and a release nobody opened — a fabricated negative, guaranteed rather than incidental in the one
mode a consumer runs when they cannot reach the source. Three passes joined a sidecar filename onto
`spec_dir` by hand, and five more sites did the same in the CLI's success lines. And five small surface
defects, of which the sharpest is that `python -m just_dna_enricher.cli` exposed 23 of 26 commands
because `if __name__ == "__main__"` sat two-thirds down the file.

**Five filings understated what was there, and the entries in ROADMAP_HISTORY say so** — the user's
call was to correct them as they moved rather than preserve the filing verbatim. RM93's guard was
missing four fact tables, not one; RM96's registry five models, not three; RM99 had five more sites in
the reporting layer; RM100 stranded a fourth command. The fifth is a correction in the other direction:
RM98's `SourceRow` claim was right, but by way of `authority` rather than `source`.

**RM88 rode along, and closing it needed one decision rather than any new capability.** The entry had
carried a technical blocker beside its policy question — a remote read, priced against "a path whose
current cost is one `upload_folder`". Detailing it showed the real cost is `create_repo` plus **two**
`upload_folder` calls, in the one tier permitted to fetch, so the read was always marginal and the
policy was the only thing holding the item. Decided **refuse unless `--force`**: `upload` reads the
published `manifest.json` at `data/<name>/v<version>/` and compares `artifact.digest`, refusing a
*different* artifact. Identical bytes are **not** a collision, which is load-bearing rather than tidy —
`upload_module` writes two commits and documents a re-run as the recovery when the second fails, so a
presence check would have refused exactly that retry. It fails **open** on an unreadable remote
(nothing established a collision, so nothing asserts one), and the flat path stays unguarded because it
means *latest*. New `PublishCollisionError`, reported as `ALREADY PUBLISHED` rather than
`UPLOAD FAILED` — the module is fine; the remote is what disagrees.

**The wider half of RM88 shipped as an ask, not a fix, and consumers should read it.**
`upload_folder` adds and replaces and **never removes**, so a recompile that stops emitting a table
leaves the previous release's parquet beside a manifest that does not attest it — a union of two
releases, on the **flat path, every republish**. The format's answer is that an unattested file is not
part of the module, and it is the right answer; what stops it being true is that the discovery path
fetches no manifest and probes named files, so a fossil parquet makes a module read as the wrong
*kind*. `delete_patterns` was **declined**: it cleans nothing on a module nobody republishes, does
nothing for a consumer that probes, and is one wildcard from dangerous (HF filters with `fnmatch`,
whose `*` crosses path separators, so a single `*.parquet` would delete every archived version's
parquets). The fix that closes it is the reader's, asked in **INTEGRATION_0_6 § 2.8** with the
mechanism and the failure — the RM27 shape: a finding about a downstream reader is an explicit ask,
never an implication.

**One fix broke a test, and that is the release in miniature.** Making `EutilsSettings` call `load_env()`
where it reads `NCBI_API_KEY` turned `test_eutils.py` red on a machine with a key in `.env`: it used
`monkeypatch.delenv`, and `@test-no-credential` says `setenv(VAR, "")` — a rule written down, explained,
and violated one file away from where `test_literature_terms.py` states it beside its own fixture.

## 2026-08-17 — the triage loop's own lint found two bad markers, and a link guard that was editing consumer prose

**Shipped in 0.6.1**, which is the "next patch whenever one is cut" this paragraph promised. Loop
maintenance rather than format work: nothing here touches a model, a parquet, a manifest field or any
published signature. The live consumer inbox is empty and stayed empty;
all of this came from running the ledger against the **history** file, which is the check that an empty
inbox is not an all-clear.

**A link guard was quietly rewriting what a consumer said, and the ledger caught it.**
`schema/tests/test_doc_links.py` requires every relative markdown link to resolve, and it exists because
an item moving live→history breaks every pointer at it. Consumers have started citing `RMn` items by
link inside their reports, so when RM89 shipped, S35's quoted prose held a link the guard called dead —
and the pass that archived the next item retargeted it to keep the suite green. That is the one edit the
triage loop forbids: a report is evidence and moves byte-for-byte. It also moved S35's fingerprint, so
the section read `revised`, our own edit impersonating a consumer revision. The prose is restored to what
was written, and the guard now exempts everything below a section's `<!-- triaged: -->` marker in both
consumer documents — replies stay checked, since they sit above it. A new test asserts a genuinely dead
anchor still survives inside quoted prose, so the exemption cannot rot into a no-op.

**A marker held a git commit sha instead of a fingerprint, and it failed twice.** S36's read
`sha cbeeb8f` — a real commit here, seven characters where `MARKER_RE` wants twelve, which made the
marker invisible and the section indistinguishable from one answered before the ledger existed. The
compounding half is the one to remember: with no marker visible, `reply_end()` falls back to the
single-paragraph rule, so paragraphs two onward of the reply leaked into the fingerprint and the value
the ledger *reported* was wrong too. Restamped, then re-run until it read `current`.

**Fixes adopted inward from the published gist.** The generalized copy of this loop is where other
repositories' fixes arrive, and two had been sitting there: `RULE_RE`, so a trailing horizontal rule is
no longer hashed as if a consumer had written it, and the archiver's closing line, which still told you
to add a row to an index table that became a contents list. Adopting `RULE_RE` re-scored four markers
(S2, S6, S7, S12 — the reports ending in a `---`); they were restamped on the proof that the ledger read
all-`current` immediately before, which shows the delta is the function and not the prose.
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md) gains the sync-in procedure, including the one gate
on auto-adopting — does it move a fingerprint — and the standing outward debt (the watcher's
branch-pause has not reached the gist).

**Three stale "0.6.0 is not cut" claims corrected**, in both S35's and S36's replies and in the live
inbox's preamble, which told consumers the newest tag was `v0.5.4`. `v0.6.0` is tagged at the commit
this batch sits on. Tagged is still not published, so the rule those paragraphs exist to teach —
answered is not installable — is unchanged, and only its example moved.

## 2026-08-17 — weights declare a scale, and GWAS effects get their own table (S36 / RM90–RM92)

**`just-dna-format` + `just-dna-compiler` + `just-dna-enricher` 0.6.0 — cut and tagged `v0.6.0` later
the same day; this entry read "uncut" until then.** Three items from one
consumer note about authored `weight` values: the column declares no scale, every module means
something different by it, and published GWAS effects are often better grounded than a hand-set
curator score. The note asked for one specific repair, which is barred; what shipped is the machinery
that makes the underlying want satisfiable instead.

**Measured while triaging, and it reframed the whole batch: `weight` is authored zero times in this
repo.** Nine of the sixteen reference examples carry a `variants.csv`; four carry a `weight` column —
`hboc_palb2` 16 rows, `hfe_hemochromatosis` 13, `par_boundary` 3, `shox_par1` 10 — and **every cell is
blank**. The column has never been dogfooded here, which the 1.0 review of whether it survives now has
as a data point.

- **The enricher will not fill `weight`, and `gwas_effects.csv` is where the effect goes instead
  (RM90).** MODULE_LIFECYCLE § Stage 3 names `weight`/`direction`/`effect_size` among the cells no tool
  fills; a null one means *the author has not modelled this*. There is a sign trap under the request
  too — `weight` is positive=protective while a GWAS beta is positive on the effect allele. So the
  seventh derived-fact table carries the Catalog's published effects beside the authored column, and
  `weights.parquet.weight` stays 100% authored. **A per-row precedence rule was refused** as putting
  two methodologies in one summable column, and so was splitting such a module in two: the split
  criterion would be source coverage rather than methodology, and membership would churn on every new
  paper.
- **`effect_unit` is the load-bearing column, and the corpus proves it.** rs1800562 carries 186
  published associations across **62 EFO traits in 12 distinct effect units** — `SD units`, `SD` and
  `s.d.` are three spellings of one; `g/dL` and `g/dl` differ only in case; 138 rows carry the
  Catalog's uninformative `unit`. `manifest.gwas_effects.units` publishes the set, so a consumer sees
  that those betas are not poolable without reading the parquet. **42 of 195 rows name no effect
  allele at all** (the Catalog writes `rs4149056-?`) and are counted rather than dropped — real
  evidence that cannot be weighted in any direction.
- **A study can finally say what its magnitude is relative to (RM91).** `StudyRow` has carried
  `effect_size` + `effect_measure` since 0.3 with no `effect_allele`, while `VariantRow` has had one
  since the same release precisely because `ref`/`alts` plus a sign cannot recover it. One optional
  column plus a check on the same mode ladder, in **both** `validate_spec` and `compile_module`; it
  reads resolved evidence only and **withholds** on an unresolvable row rather than reporting.
  `artifact.digest` moved on exactly the ten examples carrying a `studies.parquet`, and
  `content_signature` on none.
- **A module can declare what its weights mean (RM92).** `weighting:` — `scale`, `method`, `note`, all
  free text — in `module_spec.yaml`, copied to the manifest, out of both identity halves and dropped by
  `reverse_module`. Deliberately no closed vocabulary and deliberately no precedence field.
- **Running the new pass against a real module broke it twice**, and neither failure was reachable from
  a recorded fixture. A 404 is the Catalog's *empty answer* — it holds only variants with a published
  association — and the pass read it as an outage and died on the first variant of
  `hfe_hemochromatosis`. And `pvalue: 0.0`, which the Catalog really publishes past float64's subnormal
  boundary, was discarding whole associations through a `ValidationError` on one derived column; the
  number is withheld, the verbatim string kept, the row survives (189 rows became 195).
- **A prediction the measurement refuted, recorded rather than quietly dropped.** The link cache exists
  because `pmid`/`trait`/`ancestry` sit behind `_links`, making the pass `1 + 2N` requests per variant;
  it was expected to collapse most of that because associations share studies. It saved **nothing** —
  382 requests, zero hits, since each of rs1800562's associations names its own study. Hence
  `--no-study-facts`, added because of the number rather than in anticipation of it.
- **The first source here with no named licence.** EBI states the Catalog's terms in prose, so
  `license` is null. `commercial_use` stays `None` — the page permits "use" but conditions it on the
  original data owners' terms, which for an aggregator of thousands of publications are not
  established. Unknown neither permits nor refuses: `taints_commercial_use` requires an explicit
  `False`, so it warns rather than gating.

## 2026-08-17 — the publisher stopped dropping most of the artifact (S35 / RM89)

**`just-dna-compiler` + `just-dna-enricher` 0.6.0, uncut.** One item, answered and built the day after
it was filed. `just-dna-lite` replied to the three questions RM84 and RM89 had put to them
([S35](CONSUMER_SUGGESTIONS_HISTORY.md)), and the answer that unblocked RM89 also carried a finding of
their own: the publisher's `_ALLOW_PATTERNS` was not just refusing table-only modules, it was **dropping
the data of the ones it accepted**.

**Measured before, over the sixteen reference examples compiled and run through `plan_upload`:** seven
refused outright, and eight of the remaining nine published an artifact whose `manifest.artifact.files`
attests parquets — by name, sha256 and size — that were never uploaded, so the `artifact.digest` in the
published manifest cannot be reproduced from what arrives. **Fifteen of sixteen wrong**; only
`grch37_build`, a bare SNP core with no sidecar and no 0.4-family table, was correct. `sources.parquet`
was in the dropped set every time it existed, which is the half the consumer found from their end — a
module published this way arrives with no licence terms and their report footer renders *"Not stated"*.
Nothing is known to have been published through this surface, so this is *would publish*.

- **The allowlist is derived, never hand-kept.** The compiler's `_OUTPUT_FILES` is now public as
  `ARTIFACT_PARQUETS` and `just_dna_enricher.upload` imports it, so a new table family reaches the
  publisher in the commit that adds it. `LEAD_PARQUETS` joins it — `weights` plus the nine 0.4 families —
  which is what the consumer's discovery actually probes.
- **`_REQUIRED` is replaced by three positive rules**, most specific first: the plan must carry every
  file the manifest attests; `weights.parquet` never travels alone; at least one lead parquet must be
  present. The first is a self-check as much as a module check, so publisher and compiler cannot drift
  apart silently again. An absent or unreadable `manifest.json` **withholds** rather than refusing,
  which is what keeps RM84's four version reasons intact.
- **Re-measured after: 16 of 16 publish and all 16 digests verify.** Nothing that published before stops
  publishing; the only new refusals are `weights.parquet` alone and a directory with no annotation table.
- **RM84's two asks are answered and the segment spelling is settled** — `v<version>` verbatim stays,
  and a nested versioned subdirectory does not disturb their scan, by construction. Both remaining fixes
  are theirs. Recorded in [ENRICHER.md](ENRICHER.md), along with the one consequence they raised and we
  are not fixing: nothing prunes the versioned copies, so the collection grows one artifact set per
  release.

## 2026-08-17 — the 0.6 PT2 batch: five items built, and three of the proposal's own numbers corrected

The second 0.6 design round ([PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md), decided 2026-08-16) sorted
twenty-one open items into five to build and sixteen to defer. All five are here, built as five
independent lanes and merged in the order the proposal fixed. **Everything is additive under P3/P8 and
all three packages stay at 0.6.0**, which is uncut — no version moves.

**What shipped.**

- **RM55** — a fractional copy number matched no bin, silently, `--strict` included. The defect was
  never a type (the bin bounds have been `float | None` since 0.4) but three semantic rules keyed on
  the measure kind. `MeasureBinRow` gains an optional `measure_tiling` (`{quantised, continuous}`) and
  `CopyNumberRow` gains `modifier_copy_number` beside `modifier_cn`, read through
  `effective_modifier_copy_number`. The shared-endpoint and gap rules now read an **effective tiling**
  resolved per bin group — declared, else inferred from a fractional bound on a `quantised`-defaulting
  kind, else the kind's default — and the inference announces itself. `modifier_cn` is deprecated
  warn-only and goes at 1.0. The unconditional 0.6 warning is now conditional;
  `FRACTIONAL_MEASURE_PHRASE` is byte-identical, because a warning's text is an API.
- **RM87** — an expanded row was indistinguishable from an authored one, and a consumer produced 3,762
  false findings from it. `VariantRow` gains stamped, compiler-managed `locus_index` and `locus_count`
  (defaulting to `0` and **`1`**, so `locus_count > 1` is a predicate a reader can apply holding one
  row). Both are `exclude=True`, so no `content_signature` moves. Reverse prefers the stored column and
  keeps the encounter-order recompute for a pre-0.6 artifact.
- **RM72** — four `VALID_VERIFICATION_CHECKS` members were emitted by nothing. `check-identifiers` now
  records `gene_symbol_currency`, `trait_currency` and `gene_locus_agreement`; `check-acmg` records
  `acmg_secondary_findings`. Unconditional, no flag: an optional record is ambiguous between "not run"
  and "ran without the flag". **Both commands' "Writes nothing" promise is reworded** — they write no
  authored cell and record that the question was put. `merge_records` no longer lets a `skipped` record
  displace a `ran` one.
- **RM84** — the publisher now writes `data/<name>/v<version>/` alongside the flat `data/<name>/`,
  which keeps meaning *latest*. Enricher-only; no schema, no digest, no signature.
- **RM82** — an editor's line endings un-closed a module. The attestation binding now normalizes
  `\r\n` → `\n` before hashing, through a **separate** entry builder: `manifest.inputs[]` and
  `artifact.digest` deliberately keep following raw bytes, because they answer a different question.
  The trap was that `size` is inside the hashed listing, so normalizing only the digest input would
  have been a no-op that looked like a fix.

**Three of the proposal's own claims were measured and found wrong.** They are corrected in place, and
they are the reason the batch's standing rule is that every claimed movement is measured rather than
predicted:

- RM82's *"a one-time invalidation of every `module_hash` in existence"* is **7 of 16**. A binding
  moves only where an authored file really carries `\r\n`, and the half of the corpus that does is the
  **machine-written** half — `csv.writer`'s default terminator is `\r\n`, so the rewrite an author
  actually performs is normalization *toward* LF.
- RM87's *"twelve of sixteen"* is **nine**. Exactly nine reference examples carry a `variants.csv`, and
  those nine are exactly the nine whose digest moved; seven are table-only.
- RM55's evidence rule contradicted itself on `activity_score`: read broadly, a fractional value
  switches the rules "whatever its kind's default says", which produced **three false coverage gaps on
  a shipped module** (`cyp2d6_structural` bins activity scores at 0.25/0.5/1.25/2.25). The inference
  fires only against a `quantised` default — only `quantised` states a grid to contradict.

**Measured signature movement for the whole batch**, taken per lane against a baseline so each move is
attributable: `artifact.digest` moves on **eleven** modules (RM55's five ∪ RM87's nine, three
overlapping) and `manifest.verification.signature` on two, where re-closing dropped records attested
over the old bytes. **No `content_signature`, no `sources.signature` and no `resolution_signature`
moved anywhere.** P4 scopes the digest movement to a fixed `compiler_version`.

Two smaller repairs rode along because they are the drift their own neighbours warn about: the
enricher's verification-recorder docstring named three call sites where there are now seven, and
`authored_input_entries` claimed a coupling to `manifest.inputs` that the code has never had.

## 2026-08-16 — the triage loop's two Python tools are `.py`, and why that mattered

No library change; repo tooling only. `.claude/triage-state.sh` and `.claude/triage-archive.sh` are
**`.claude/triage-state.py` and `.claude/triage-archive.py`** — they were always Python with a
`#!/usr/bin/env python3` shebang, and the extension was a standing invitation to run them the one way
that breaks: `bash` ignores a shebang, reads the module docstring as commands, and reaches
`import hashlib`, where `/usr/bin/import` is **ImageMagick's screen-capture tool** and treats its
argument as an output filename. One such run left four empty files named `hashlib`, `pathlib`, `re` and
`sys` in the repository root — the script's own imports, in order — and left them *silently*, because
`import` writes the file before failing on its security policy. Entries below this one name the old
`.sh` paths; they record what the files were called then and are left alone.

The rename is the fix — nobody types `bash foo.py` — but the same class of failure had two other
doors, now shut: `triage-archive.py` invokes the ledger through `sys.executable` and
`watch-suggestions.sh` through `$PYTHON`, so neither the exec bit nor the shebang is load-bearing at
any call site. `watch-suggestions.sh` stays bash, because it really is bash.

Three fixes came back the other way, from the generalized copy of this loop published as a
[gist](https://gist.github.com/winternewt/54b94bda01812be937b892146d1bb254): the archiver now refuses
when the history file is missing rather than dying in `read_text`, the watcher's event-line cap is
`CAP` rather than a hardcoded 8, and `stat -f %m` is tried where `stat -c %Y` fails. Two gotchas came
with them, both found while adopting the loop into a second repository and neither reachable here —
**the archiver verifies the move, not the verdict** (it will archive a section the ledger calls `new`;
the lint is running the ledger against the *history* file afterwards), and **a preamble line beginning
`**Status` is read as a block reply**, which marks every id it names answered and which `--backfill`
then stamps. Runbook §6 has both, and the gist has the correction that went the other way: its
`group_span` docstring claimed archiving shifts the *preceding* section's fingerprint, which this repo
had already checked and refuted — `fingerprint()` ends in `.strip()`, so an injected heading below a
section's prose leaves its hash alone.

## 2026-08-16 (later) — 0.6.0: S33 and S34, and a premise of ours that a consumer had believed

Two more field notes from **just-dna-lite**, from the same twelve-module annotation as S30–S32. One is
a real defect with 3,762 false findings behind it; the other is a five-section reply in which four
sections needed nothing built and the fifth was a doc of ours being wrong. Both are archived to
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md).

**S33 — a one-to-many expansion's other rows are well-formed, and nothing said they were there.**
An rsID resolving onto N loci is paired with each, so K authored genotypes become K×N rows and only the
member whose alleles can carry a genotype can match it. COMPILER.md has said so for a release, in the
authoring frame where an unmatchable row is inert. It is not inert to a *reader*: `TA/TA` beside
`ref=TA` at a ClinVar duplication/deletion pair is a well-formed reference homozygote carrying the
module's conclusion, and the reporting consumer queued 2,579 of them into one genome's `pathogenic`
section and 1,183 into `cancer` before catching it. Reproduced from our own corpus — nine multi-locus
keys in `pathogenic_clinvar`, two in `hboc_palb2`, every one same-position/different-`ref` — and the
fixture is now `compiler/tests/test_expansion_counts.py`.

The expansion stays; filtering it is refused for the two reasons already on record, and the reporter
argued that case themselves. What ships is `manifest.compilation.expanded_keys` / `expanded_rows`
(RM44's two-counts shape, `None` where resolution did not run so a catalog can tell "no expansion" from
"no measurement", out of `artifact.digest` and pinned by a recompile test) and the **read-side
contract** in SCHEMAS § *the consumer join contract*, where a consumer meets it rather than in the
validation discussion. Note that `expanded_rows - expanded_keys` is **not** the unmatchable-row count —
that needs a per-key authored-genotype number the manifest does not carry.

**Probing the report found two defects in our own reporting.** The expansion warning was emitted inside
the per-authored-row loop, so a site with two authored genotypes published the identical sentence twice
and each copy said *"expanded to 2 rows"* of an artifact that had gained four — `compilation.warnings`
is a published surface (RM44), so that is a wrong answer, not a repeated one. And
`_check_genotype_coverage`, the check S32 produced three days earlier, fired on that exact site with the
reason *"no ref is authored or resolved here"* of a site the table resolves onto two disagreeing refs.
Turning a new check on the new report is what found the second; it is the standing advice and it paid
again.

**RM87 is filed to correct a premise, not to defer one.** S33 declined to ask for `locus_index` in
`weights.parquet` on the grounds that a new column moves every module's digest and is therefore a 1.0
conversation. Under P3 it is a **minor** — the authored identity does not move — P4 scopes
byte-reproducibility to a fixed `compiler_version` anyway, and the 0.6 cost amendment prices a stamped
compiler-managed parquet column as *"approximately free… the cheapest thing this format can add"*. A
consumer talked themselves out of the right fix using a rule we retired on 2026-08-11, which is a
communication failure on our side. What is genuinely open is *which* column: `locus_index` alone is `0`
on a non-expanded row and on an expansion's first member both, so it needs `locus_count` beside it, and
a bare boolean forecloses the ordinal permanently under P5. The reporter is asked to state a preference.

Also corrected for them: their mitigation (withhold any locus spelled with more than one `ref`) misses
same-`ref` expansions, and one is instantiated here — `enrich --keep-par-twin` records a pseudoautosomal
locus on X and Y with identical alleles, which is what `reference_examples/shox_par1/` was built from.

**S34 — the brief promised fields nobody could install.** The consumer's own opening complaint, upheld:
a table of 0.6 fields was presented as *"also shipped since you last synced"*, and 0.6 is uncut (every
`pyproject.toml` reads `0.6.0`; `git tag` stops at `v0.5.4`). The standing rule, now written into the
reply: *"in the tree" means committed and nothing more* — check this file for whether the version was
cut. Of the five sections, §3 and §5 were closed consumer-side and needed nothing, §4 was already filed
as RM84 with their agreement recorded in it, and §2 was a documentation defect the previous session had
already fixed (SCHEMAS.md and `manifest.py` both said *a consumer* should apply the `fully_resolved`
trust rule; the reader is a **catalog**, and saying "a consumer" sent one hunting for a read path they
had deliberately not built).

**§1 is the one with work in it.** `verify_manifest` has no call site anywhere, and its
`require_marketplace` **defaults to the marketplace policy** — so one naive call site rejects every
locally-compiled module, ours included, since our compiler leaves `compiled_by` null by design. The
contract is right; the docstring listed the flag among the optional steps rather than as the fork it is,
and `schema/README.md`'s example used the default silently. Both now state the two policies, one per
install route, and both point at the pinned `public_key` as the guarantee that is actually load-bearing.
Beside it, `schema/README.md` still called `artifact.digest` *"the version's immutable content
identity"* — the exact wording S7 was filed against; SCHEMAS.md was corrected then and this copy was
missed. Last one in the tree.

## 2026-08-16 — 0.6.0: a consumer round, S30–S32

Three field notes from **just-dna-lite**, all out of one annotation of one WGS genome against twelve
modules. Two shipped whole, one shipped its authored half and routed the rest; the routing is the part
worth reading, because in each case the reported symptom and the fixable defect were not the same size.

**S30 — the genotype split had three copies, and the consumer's was the only one with no code to read.**
`_split_genotype` was private to the compiler, so a consumer joining `weights.parquet` re-derived the
rule from prose, got it wrong twice in opposite directions, and had no failing run either time to say
which was right — sorting the alleles raises nothing, it just matches a quietly larger set on phased
data. `just_dna_format.alleles.split_genotype` is the leaf now (format tier, stdlib, the
`parsimony_reduce` precedent), and probing turned up a **third** copy in `resolution.py`; both of ours
call it and a test asserts they are the same object. Contract: *a validated cell in, alleles in authored
order out*, never sorted. Dropping empty fragments makes the split total over any string and is **not** a
widening — `|A|G` splits here and is still refused by `_validate_genotype` (RM67), pinned by a test so
nobody reaches for this as a validator. The artifact half — `weights.parquet` splits, the 0.4 families
keep the string — is [RM81](ROADMAP_1_0.md#rm81--one-artifact-spells-a-genotype-two-ways), 1.0: it is a
retype of a published column, and the minor-legal parallel-column workaround is refused there as two
spellings of one value in one table.

**S31 — the unjoinable count RM44 filed against RM43, published as a number.**
`manifest.compilation.positional_rows` / `positional_rows_placed`, the same parts-not-a-ratio shape as
`vrs_alleles`: complete is `placed == rows`. Until now the only published record of whether a PGx table
joins to a VCF was the warning sentence a downstream registry substring-matches, which RM44 established
is an unversioned interface. `pgx_slco1b1_simvastatin` reports 9 of 9 beside a `fully_resolved: true`
that quantifies over zero variant rows. **Both fields are `int | None`**, and that is the second half of
the item: `0` is a real answer (no positional table), so defaulting to it would have a pre-0.6 manifest
report "no positional rows" for a 1,482-row artifact with every coordinate null — the vacuous-
`fully_resolved` failure re-made inside the field written to close it. `None` is *this compiler did not
count*, which is what every pre-0.6 manifest honestly is, and it is how a consumer tells the eras apart
without probing parquet. `UNJOINABLE_PHRASE` and its test **stay**: already-published artifacts carry
neither field.

**S32 — a site annotated for some of its genotypes and not the rest.** A consumer matches on
`(variant, genotype)`, so a genotype with no row is a subject with no answer; the reporter's curated
520-site module authors no homozygous-alternate genotype at 208 of them, with their subject homozygous
at 74. `_check_genotype_coverage` reports the missing members by reason, with both counts (genotypes and
sites, since one two-alternate locus can be missing two). It fires **only where the module already
annotates a site for two or more genotypes** — one genotype at a site is a rule that fires on the call
the author cares about, and `pathogenic_clinvar` is in that shape at 326 of its 327 sites, so the wider
version is a line on nearly every module ever drafted. Dogfooded on our own corpus first and it found
three true instances there, including `pathogenic_clinvar` stating both HBB heterozygotes at 11:5225715
and neither homozygote. Never demands an alt/alt pair (RM35), never guesses the reference, and skips
sites whose genotypes are not diploid nucleotide pairs — which keeps MT and non-PAR Y out with no contig
list. Warning in both modes, `validate_spec` only (its message carries a count, and a post-resolution
re-run would publish a second differently-numbered copy of the same finding).

**What S32 did *not* get, and why it is a routing decision rather than a deferral.** Whether a hom-ref
row can ever match is a property of the file a consumer brings — a variant-only VCF emits no record where
the sample matches the reference, a gVCF and an array do — so **which annotation path works against a
chosen data input is the annotator's call, not this format's**. No module-level "evaluate me against a
callset that can express the reference genotype" claim was built, the *presence* of hom-ref rows is never
reported (they are correct, and are what make a module work on array data), and restoration and
imputation stay on the consumer side. The item's second ask turned out to be already satisfied:
`mt_common_deletion`, `mt_heteroplasmy` and `shox_par1` populate `requires_callable` — the PGx half is
RM70.

Also corrected: the authoring skill's joinability symptom still described the pre-RM43 world and told
authors there was nothing they could do about it.

## 2026-08-16 — 0.6.0: RM73 closed, both halves, and RM80

**RM73 (phase boundary) — authoring is a process, and it now has an end.** A module could not say it
was finished, so every check that needed to know where a value came from was guessing. The mechanism
turned out to be one block: RM45 had already built the binding for another purpose — `verification.json`
hashes the authored files and the compiler drops the whole block when that hash no longer matches — so
what was missing was a record saying *a human declared this final* rather than *a pass ran*.

`VerificationDoc.closure` (`closed_at`, `closed_by?`, `signature?`) is written by the new
`just-dna-compiler close`, and by nothing else. **No new file, no new binding, no new proof-of-work**:
the closure rides the attestation, so an edit after closing un-closes the module for free, and it sits
outside `pow_digest`'s payload, so closing re-mines nothing and every attestation written before it
still verifies. `validate` stays read-only however cleanly it passes — a mark left by whatever happened
to run says only that something ran, which is the defect the item levels at a by-product attestation.
`--private-key` signs the closure over the authored bytes with the same key `sign` uses, turning
*someone closed this* into *this party closed this*; unsigned stays legal and still change-evident.
Closing refuses a spec that does not validate and **does not** refuse on a warning, or a module carrying
a finding no authored edit can clear could never be closed at all.

A compile (and the pre-flight) now warns when it publishes no closure — both modes, never `strict`, no
count in the sentence so the two runs de-duplicate. A closure that is *signed* and does not verify drops
the whole document: absence is a limit, a claim is a claim. `record_verification` had to learn to carry
a closure across, and only while the binding holds — the never-clobber trap a third time after
`SourceRow.dataset` and `draft_digest`, and it drops rather than re-binds one whose bytes have moved,
because only the author may make that claim again.

**No identity moved and the corpus is closed.** All sixteen reference examples compile to a
byte-identical `artifact.digest` and `content_signature` before and after being closed, measured rather
than argued; all sixteen now ship a closure, with a test asserting each is still current so an authored
edit fails loudly instead of decaying into a *stale* warning nobody reads.

**Whether to warn on absence was decided twice, and the probe behind the reversal is what blocks 1.0.**
The first analysis argued for silence, since `reverse` cannot re-emit the document, so a closed module's
`compile → reverse → compile` would warn on step 3 where step 1 was silent — and RM44 made
`manifest.compilation.warnings` a parsed surface. Two facts overturned it: the divergence costs nothing
enforceable (`artifact_digest` covers the parquet only, `manifest.json` is not in it, warnings feed no
signature, no round-trip test compares them), and without the warning the closure has **no consumer in
0.x at all** — a manifest field read by a catalog that does not exist yet is the designed-and-never-
delivered shape. But a *refusal* is not free the way a warning is: under the 1.0 gate a reversed spec is
unclosed by construction, so step 3 would refuse for every module. That is filed with three undecided
candidate answers in [ROADMAP_1_0 § RM73 (gate half)](ROADMAP_1_0.md).

**Dogfooding the closure against 61 foreign modules turned up three fixes, one of them unrelated and
bigger than the two that were.** `just-dna-compiler close` was run over every module spec directory in
`just-dna-registry`, `just-dna-lite`, `just-module-creator`, `clawbio` and `dna-agents` — copies, never
their trees. 30 closed and 29 refused, and **26 of the 29 refused because `module.version: 3` is an
`int` by the time YAML hands it over**, while RM17's SemVer coercion — written expressly to accept the
pre-0.4 corpus's `v2` and `3` — is a `mode="after"` validator the field's `str` check never lets it
reach. Quoted `'3'` coerced; unquoted `3` refused with *Input should be a valid string*, and unquoted
is the only way YAML spells a number. Widened at `mode="before"` (P3-legal — previously-refused values
become legal and nothing accepted changes); a **float** stays refused with the reason, since YAML reads
`1.10` as `1.1` and the authored text is gone before any validator runs. Every one of this repo's
sixteen reference examples quotes its version, so no corpus here could have found it.

The two closure bugs: `close` printed *Run `just-dna-compiler close`* as the first line of every
refusal, having faithfully echoed the pre-flight's warning to the one caller for whom it is already
answered (the RM77 class); and a module closed straight from its authored state published
`produced_at` beside `producer: null` and no checks — a timestamp for a run that never happened. After
the three, the same sweep closes 54 of 59 and the five refusals are real: two modules with no
`studies.csv`, two published registry modules carrying *inconsistent reference allele* contradictions
that `validate` and `compile` refuse identically, and one `<<REPLACE>>` template. Findings in
[DOGFOOD_0_6_FINDINGS § Round 3](probes/DOGFOOD_0_6_FINDINGS.md).

**RM73 (provenance half) — a drafted value that has not moved is a copy that can be *established*.**
Shipped the same day, and the half four separate items were actually asking for; it needed no phase
boundary to answer.

A drafting provider now hashes the table it wrote, projected onto the column its own cross-check later
reads, and stamps it onto the licence row it was already writing (`SourceRow.draft_digest`, new
optional column; `just_dna_enricher.provenance`). The check recomputes and compares. RM4's tautology
skip stops being a hopeful module-level guess and becomes a **conjunction**: this release *and* no
checked value moved since.

- **Scoped to the checked column, not the row.** A ClinVar-drafted module always has edited rows —
  `genotype` is a placeholder the human must fill — so a whole-row hash would never match once.
- **Raw CSV cells, not models**, because the same function must run at draft time, when the table is
  full of `<<REPLACE>>` that the models refuse to load by design.
- **Uniform across all three providers**, which closed two tautologies nobody had filed:
  `pgx_draft` writes `function_status` out of CPIC and the PGx check compares that column against
  CPIC; `clinpgx_draft` writes `evidence_level` out of ClinPGx and the ClinPGx check compares that.
  Both were publishing a structurally guaranteed `findings=0` into `verification.json`. CPIC was also
  the one provider recording **no `dataset`**, and now stamps one.
- **Per-leg in `enrich_pgx`**, so the CPIC leg skips while PharmVar — an independent authority —
  still runs.
- **Removed:** `ClinSigAudit`, the copied/authored/no_record bucketing, `EnrichmentResult.clin_sig_audit`
  and its CLI line. They existed only because the module-level marker could not see a per-row edit, so
  `strict` paid for a lookup to recover the split. **The mode ladder went with them** — the check now
  behaves identically in both modes.
- **Behaviour change:** a licence row naming the right release but carrying **no digest no longer
  skips**. Nothing that was checked stopped being checked; a module waved through on a claim is now
  examined.
- **Identity:** `draft_digest` is outside `SOURCE_FACT_FIELDS`, so `sources.signature` moves nowhere
  and `content_signature` is untouched (`pgx_slco1b1_simvastatin` still `sha256:8173dab7…`). A
  recompile's `artifact.digest` moves for any module with a licence table.

**RM80 — `annotations.parquet` carries the `genotype` that distinguishes its rows.** Retro-filed from
a downstream consumer report: `variant_key` is not unique there and never could be (poly-effect is
real), so consumers had to dedup before joining, and the authored column deciding *which call* an
annotation applies to was in no column. It is now carried **and in the dedup key** — carrying without
keying would let two genotypes sharing a conclusion collapse onto a row naming one of them, turning a
missing answer into a wrong one. Reverse reads which of three keyings an artifact carries; both legacy
branches preserved. `content_signature` unmoved.

## 2026-08-16 — consumer note: `just-dna-lite`'s annotating engine moves onto 0.5

No change here; recorded so the other consumers are not surprised. `just-dna-lite` migrated its
*producing* side to 0.5 last August and left the *consuming* side on the 0.2 shape. The annotating
engine has now been moved; the report follows in a second pass. Three things worth knowing:

- **A `pharm_variants`-led module could not be annotated at all.** `weights.parquet` splits the
  genotype into `List(Utf8)` and the 0.4 families keep the authored `"C/C"` string, so joining either
  to a VCF's `List(Utf8)` genotype raised `SchemaError`. Filed as **S30**; the engine now coerces the
  lead table's genotype to `List(Utf8)` before joining, mirroring `_split_genotype` exactly — **not
  sorted**, so one artifact does not end up with two spellings of a genotype — after which `pharmgkb`
  annotates rather than aborting the run.
- **A lead table is now classified by its schema, not its family name.** `diplotypes`, `pgs`,
  `allele_function` and the binning families carry no per-variant key, and the engine used to die on
  `ColumnNotFoundError` — taking every other selected module's annotation with it. They are skipped
  with the reason recorded, so adding a family to the format no longer breaks a consumer that has not
  learned it yet.
- **A shared ALT is not a shared variant.** Joining on `(chrom, start, genotype)` and dropping the
  module's `ref` let `G>A` match a module's `GTGTCT>A` at the same locus. On one real sample that was
  **6 of 9** reported `pathogenic` findings. The engine now requires `ref` agreement where the module
  states one — and we checked that cheap string equality does not disagree with
  `just_dna_format.alleles` on the set it can reach: once the genotype has matched, a differing `ref`
  means the two records delete different numbers of bases, so `event_profile` calls all six a
  **positive contradiction** and both survivors a match, with no "unknown" residual. Pinned by a
  test, because it holds only of that reachable set — comparing allele strings is the wrong test for
  indels in general.

Two more came out of reading **PROPOSAL_0_6** against our own code, and both were live here:

- **RM60 was biting us in production.** We strip a leading `chr`, so an hs38DH-aligned sample's
  `chrM` became `M` — a contig no module writes — and **every mitochondrial annotation was dropped
  without a word**. One of our three real samples is exactly that (35 rows), and `heteroplasmy` is an
  entire table family about mtDNA. Fixed by routing our contig column through `vrs.normalize_chrom`
  instead of maintaining a second, weaker folding.
- **RM64 was a latent gap.** Our rsid join keyed on the raw ID cell, so a spec-legal `rs123;rs456`
  record would have matched nothing. Zero occurrences in our two samples, so this is a fix ahead of
  the failure rather than after it.

**S29 was answered in the same round as [RM80](ROADMAP_HISTORY.md#rm80--annotationsparquet-had-no-column-for-the-thing-that-distinguishes-its-rows)** — `annotations.parquet` gains `genotype`,
keyed `(variant_key, genotype, conclusion, negatives)`. Our report pass will join on
`(variant_key, genotype)` as instructed rather than shipping the local dedup we had planned, which
the reply rightly notes is lossless only for as long as it happens to be. **S30 is open.**

## 2026-08-15 — 0.6.0: RM74–RM79, the fix round's own findings

Round 2 of [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md) — the findings the fix round produced by
reading the code around each repair — was grouped into RM74–RM79 on 2026-08-14. The first two are
worked here. Both are **enricher-only**: no parquet, no model, no manifest field, so the corpus is
untouched and nothing versions but the network tier's own next patch.

**RM74 — the drafting providers read their sources wrong.** ClinPGx joins the genes one annotation
names with `;`, the same separator its drug list already had a named constant for, and both readers in
`clinpgx_draft` treated the whole cell as one symbol. Re-probed against the provisioned snapshot:
**396 of 16,087 rows** carry a `;`, and `--gene VKORC1` silently dropped the three rows of `rs17886199`
(published as `PRSS53;VKORC1`). The filter matches per member now.

*What a plural cell writes* was the one real choice, and two of the three candidates are refuted by
facts rather than by taste. **One row per gene is illegal**: `gene` is *outside* `PharmVariantRow`'s
dedup key, so the copies collide on `(variant_key, drug, genotype, phenotype_category, annotation_id)`
and the compiler refuses the module — the structural difference from `drugs`, which *is* in the key.
**Picking from the cell alone has no rule to pick by**: the pharmacogene is first in `CYP3A5;ZSCAN25`
and second in `ANKK1;DRD2`, `CYP2A7P1;CYP2B6` and `PRSS53;VKORC1`. So the answer is the CPIC `gene.chr`
move — write the member the *request* selects, which is a lookup in what the caller already stated, and
otherwise **withhold and name the genes the cell held**, aggregated by cell. An empty cell reads as
*not stated*; the joined cell is false about its own column and matches no consumer's gene filter.

Two more in the same loop: `skipped_unidentified` was counted **before** the `--gene` filter, so on any
narrowed draft the "records the source could not identify" number was inflated by the rest of the
database — which destroys the one thing it is for. And `test_draft_declared_build.py`'s location
fixture was keyed `"location"` where `cpic.defining_variants` reads `"sequence_location"`, so the
nested dict was always `{}` and the file's claim to cover a coordinate-carrying defining variant was
hollow — third instance of that class after S21's registry and D6-2's `_MOVABLE`. Repaired with the key
*and* an assertion that the coordinate reaches `haplotypes.csv`, which is what makes the key
load-bearing.

**RM75 — a complete result destroyed by an incidental failure.** `CpicClient._get` called
`raise_for_status()` and wrapped only *shape* failures into `CpicError`, so an exhausted retry ladder
left a raw `httpx.HTTPStatusError` that walked through both of `enrich_pgx`'s per-leg handlers — the
handlers written under *"One source failing must not sink the pass"* — and took PharmVar's answer with
it. The retrying half is `_request` now and the translation sits **outside** it: wrapping inside would
make `retry_if_exception_type` a no-op, so a test pins that the ladder survived the split. **The
finding named only CPIC and PharmVar had the identical hole**, which is worth stating because repairing
one leg makes that comment true in one direction only — the guarantee would hold or not depending on
which source went down.

`cpic.knows_drug` is caught now (it exists only to sharpen a sentence, and every substantive query has
already returned by the time it is asked), so an optional message-enrichment call can no longer discard
a finished draft. Its `bool | None` tri-state had been designed and never delivered *from the live
client*, which is why the raise escaped: the handling existed and nothing could reach it. The failure
gets a **third** wording rather than reusing the snapshot one — "the snapshot cannot answer" is fixed by
going live, "the request failed" by re-running.

And `spec_genome_build`'s deliberate raise no longer tracebacks out of `draft`/`draft-panel`. That
regressed *because* the declared-build defect was fixed: routing three providers through a shared
precondition owes the same addition to each of their handlers, which `_DRAFT_PRECONDITION_ERRORS` now
carries. The check also moved to the top of both providers — it reads one file beside the spec and was
landing after a published ClinVar snapshot had been provisioned.

**RM76 — an unfinished authoring state passed every gate, including `--strict`.** `SourceRow` is a
plain `BaseModel`, not an `AuthoredModel`, deliberately: it is a machine-produced reference fact,
grouped with the other four sidecars. S21 then made it **draftable**, also deliberately, because it is
the only fact sidecar a human writes and the only table the compile licence gate reads. Both decisions
were right and nobody reconciled them. Re-probed on `hfe_hemochromatosis` with `source=<<REPLACE>>`: the
module compiles green under `--strict` and `manifest.sources` publishes `"sources": ["<<REPLACE>>"]`
inside the block its own `signature` covers — a signed module's attribution ledger naming a template
placeholder as the source it accounts for.

The guard lands on the model rather than through the base, with `ModuleSpecConfig` as the precedent —
standalone for its own reasons and guarded all the same — so the classification stays true and the
other four sidecars stay out, since no template is ever generated for them. It refuses in both modes,
which is not a choice: a load error is fatal in both.

Two things the repair turned up. A **vocabulary** column was catching the stub by accident (`layer`
refuses the token as a non-member), which is why the free-text half stayed open — and why the first
draft of this item's own test came out **green on the unfixed code**, since "some error mentions
`<<REPLACE>>`" is satisfied by the vocabulary message quoting it back. And `draft.stub_template`'s
docstring has printed the guarantee *"an unreplaced stub cannot compile … in both modes"* all along
with nothing checking it; it is now asserted over every `DRAFTABLE` kind, parametrized rather than
listed, because the defect was a model quietly outside a set.

No corpus movement: a `mode="before"` validator that only raises changes no accepted value, verified
against `artifact.digest` / `content_signature` values recorded independently in ROADMAP_0_7 and
CLAUDE.md. The general question underneath — what marks *authoring* as unfinished, rather than one
token as unreplaced — stays [RM73](ROADMAP_HISTORY.md#rm73-phase-boundary--authoring-is-a-process-and-it-now-has-an-end).

**RM77 — the genotype diagnosis told the author about the wrong thing.** `GT` is `0/1`; `genotype`
wants the bases. Pasting the `GT` field is the obvious first guess and therefore the single most likely
mistake in this column, and `0/1` fell through to the nucleotide-grammar wall — a sentence reciting
what an allele may be that never says those digits are **indices** into the record's own REF/ALT list.
`0/1/1` was worse *because of* 0.6: the ploidy-message fix gave it a confident, correct explanation of
the two-allele ceiling, which is about the wrong thing, and a correct sentence aimed at the wrong
defect sends the author to change the wrong cell. So the diagnosis runs ahead of the arity branch, with
a test pinning that a base-spelled triploid still gets the ceiling message and this one does not.

It changes no verdict — every cell it matches was already refused — and it is the `mode="before"`
diagnosis shape `reject_reserved` / `reject_authority_keys` / `reject_misplaced` already share,
reaching a *value* rather than a column name. Nothing legal can look like a GT cell: `ALLELE_PATTERN`
is `^[ACGT]+$`, a symbolic allele is bracketed, `*` is one character. It reaches `PharmVariantRow` for
free, since the grammar has lived on `AuthoredModel` since 0.5, and that is pinned rather than assumed.

**And RM63's correction was itself an overclaim — the third turn of one screw.** The comment read
*"Read a pipe here as **heterozygous**, phase recorded but unaddressable"*. `VariantRow(genotype="C|C")`
loads, and `1|1` is an ordinary phased homozygous call. The original comment claimed a pipe encodes
which homolog an allele sits on; RM63 refuted that correctly and replaced it with an unchecked claim
about zygosity; the 0.6 unit that carried the wording onto the printed `describe` output dropped the
zygosity word on the way, so **the contract an author reads has been right since then and only its
source was wrong.** A correction is exactly where this happens: the reviewer checks the claim being
removed, not the one going in. The comment now keeps the history of both wrong versions, and a test
pins that `C|C` loads.

**RM78's two fixes — the VRS reason surface's remaining blind spots.** `*` still landed in the
compiler's indel bucket: 0.6 gave the symbolic class its own permanent reason in `_vrs_gap_reason` and
`_recompute_vrs_id` and guarded `*` and `.` on the *enricher* side, and neither compiler function was
told — so an unobservable allele in `resolution.csv`'s `alts` was reported as *"an indel or MNV … re-run
it online"*, the same false class D1-2 had just fixed for symbolic alleles, offering a remedy that can
never apply. Filed as having no instantiation and upgraded when it turned out to have one: `*` **passes**
`LiteralSequenceExpression`'s `^[A-Z*\-]*$`, so before the enricher guard it would have been normalized
and handed a content-addressed id for a state that is not a sequence. Three reason classes now, split by
the P5 line the predicates already draw — *which variant is this, unspelled* versus *could the call see
an allele at all*. **Severity could not have caught this**, and the test says so: the indel branch it
fell into is also tier-blame, so the verify matrix read `warn` before and after.

`refget_supports_build` answered `True` for the two inputs `refget_accession` raises on. Its docstring
says it is *"the question `refget_accession` raises on"*, and for `None` and `""` it was answering the
opposite — a printed claim the code does not honour, in the tier the other two build on, on the guard a
caller reaches for *precisely* to avoid the exception. The old reasoning (*"an unset build is the
format's default"*) imports a spec-layer fact into the identity layer: the GRCh38 default lives in each
signature, and an explicitly passed `None` is a caller who has not threaded the row's build through —
the class `test_build_call_sites.py` walks the AST to prevent. Every other build gate in `vrs` already
read it that way. Both sides now read one predicate, so RM15's second table cannot re-open the gap.

The third part of RM78 is a decision and stays open: whether a stored VA against a symbolic allele is
the row's contradiction rather than the tier's limit.

**RM78's decision — a stored VRS id against a symbolic allele is the row's contradiction, and the
grammar was settled first.** `_recompute_vrs_id` returned tier-blame (a warning in both modes) for a
symbolic allele carrying a `ga4gh:VA.…`. Tier-blame is for a finding **no authored edit could clear**
(P5), and deleting the cell clears this one — so the finding sat in the class whose own test it fails.

The escalation only follows if a present id can *only* be a VA minted for a different allele, and
nothing had established that: `vrs_id` was checked for well-formedness alone (`ga4gh:<TYPE>.<digest>`,
five types) while its description says *"GA4GH VRS allele id (`ga4gh:VA.…`)"*. So the grammar went
first. `validate_vrs_allele_id` makes `ResolutionRow.vrs_id` and `FrequencyRow.vrs_id` `ga4gh:VA.`-only
and names the type it refuses. It makes no passing module fail — a `ga4gh:SL.…` already reached
`_verify_vrs_ids` and came out as a **mismatch** ("recomputed and different, so corruption"), an error
in both modes with the wrong explanation — and it has no instantiation, the test this repo applies to a
tightening: 844 ids across all sixteen reference examples, every one a VA. `validate_vrs_id` keeps its
lenience and its documented reason, because "is this a well-formed VRS id" and "may this column hold
one" are different questions and only the first should be generous.

With that settled the escalation is mechanical: a recorded id on a symbolic row can only name some
*other* allele, which is the *inconsistent reference allele* class — catchable offline, an error in both
modes. The message says which cell to delete and that the allele keeps its identity through
`variant_key`.

**The asymmetry is pinned rather than assumed.** The coverage side still reports a symbolic allele as a
permanent gap and warns in both modes: an **absent** id there is the ordinary correct state, and
refusing would make every structural module uncompilable for a reason no edit could fix. Absence is a
limit; a claim is a claim. `mt_common_deletion`, `cyp2d6_structural` and `pathogenic_clinvar` still
compile under `--strict`.

**RM79 — two honest counters disagreed, so the compiler stopped carrying the dead weight.**
`manifest.literature.missing_count` counted `exists is False` over every row in `literature.csv`; the
`citation_existence` verification record counted the module's *current* citations. `literature.csv` is
merge-not-clobber, so it keeps a row for a citation since deleted from `studies.csv`, and the two
numbers disagreed in a published manifest with nothing wrong in the module.

**The item's own framing turned out to be the wrong question.** It asked whether `manifest.literature`
should describe the table it is named after or the module's current citations — and probing found both
blocks already publish their denominator (`row_count`, `subjects`), so a reader could reconcile them.
What nobody had decided sat upstream of the counting: why is a row nothing joins to in the artifact at
all? A literature row for a citation no study and no bin names is dead weight, present only as a side
effect of merge-not-clobber. So the compiler discards it and the CSV keeps it — that file is the pin
that makes a re-run cheap, and carrying the row onward was a separate thing nobody had chosen. The two
counters now share a subject **by construction** rather than by documentation.

Four things pinned rather than left to be re-derived. The check sees every row and everything after it
sees the kept ones, since reporting what was dropped needs the full list — and the warning now reports
an action taken rather than nagging about a file the author is not expected to tidy. An empty citation
set discards nothing, because a module citing nothing cannot tell a stale sidecar from citations not
yet authored, and emptying the table on the first reading would delete a whole enrichment pass's
output. **Both** citation sites count (RM47) and the stakes rose with them: blind to bin `pmid`s the
compiler used to warn about a threshold-grounding citation and would now *discard* the row that
evidence lives in. And the round trip narrows once and **converges** — `reverse_module` rebuilds the
CSV from the parquet, so a reversed copy carries the kept rows only, which is a deterministic narrowing
of a machine-written derived sidecar rather than a P7 breach (RM69's reading), and lap two discards
nothing.

No corpus movement — no reference example carries an uncited row, verified by recompiling all sixteen —
and therefore no corpus coverage either, so the behaviour is pinned by fixtures.

Suite 2262 → 2264.

## 2026-08-14 — 0.6.0: the dogfooding fix round — sixteen findings worked, nine more found

[DOGFOOD_0_6.md](probes/DOGFOOD_0_6.md) built six probe modules against the shipped CLIs and produced a
ledger, [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md), whose own header said fixing was a separate
round. This is that round: twelve parallel units in isolated worktrees, one finding or group each, every
one exercised against a real module rather than only the suite. Ten `fix` findings landed, five
`surface` ones became **RM68–RM72** in [ROADMAP_0_7.md](ROADMAP_0_7.md), and the work turned up **nine
new findings** which are filed in the same ledger as Round 2 rather than in a new file.

**Nothing in the corpus moved except where a new column made it legal.** All sixteen reference examples
were compiled before and after: `content_signature`, `resolution_signature` and `sources.signature` are
identical on every module, and `artifact.digest` moved on exactly the three carrying `literature.csv`,
because `LiteratureRow` gained an optional `doi_checked`. That is the additive case Principle 3 permits
as amended — the column is outside `LITERATURE_FACT_FIELDS`, so no authored identity moved.

The findings worth knowing outside this repo:

- **`enrich` crashed on any module carrying a symbolic allele** (D1-1). RM5 shipped the grammar in 0.6
  and the VRS tier was never told, so `<DEL:4977>` reached `ga4gh.vrs` and raised an unhandled
  `ValidationError`. Probing the fix showed the crash is the *character class*, not the spelling:
  RM58's `.` raises identically, and RM59's `*` **passes** the sequence pattern, so it would have been
  handed a content-addressed id for a state that is not a sequence. All three are guarded, in both
  tiers, each with its own permanent reason class rather than being called an indel.
- **The rsid↔coordinate check was documented, named in the check vocabulary, and unreachable**
  (R2-15). It lives on `resolve_variants`, whose only non-test caller is the compiler's deprecated
  `_legacy_resolve`; `enrich()` never called it, and a row authoring both halves was never compared.
  Found only because wiring its attestation required counts that did not exist. Generalize it: asking a
  pass to publish a number is how you discover it never computed one.
- **Six of the twelve unemitted `VALID_VERIFICATION_CHECKS` members are now emitted** (D4-1) —
  `literature` writes three, `pgx` and `vrs mint` one each, and `enrich` gained rsid↔coordinate.
  `merge_records` had been built and tested for a multi-command document no two commands produced; two
  real commands now exercise it. The remaining six are RM72, four of them blocked on
  `check-identifiers`/`check-acmg` advertising "Writes nothing".
- **`vrs mint` records a skip, not a pass.** Its member names the cross-check against a *source-reported*
  id, and nothing in the workspace fills that input — so recording the alleles it minted as `subjects`
  would assert a comparison never made. Coverage rides in `detail` instead.
- **A `<<REPLACE>>` template stub in `licensing.csv` compiles green under `--strict`** and reaches
  `manifest.sources` inside the block its own signature covers (R2-8, unfixed). `SourceRow` is not an
  `AuthoredModel`, so the "a generated stub must be unable to compile" guarantee never reached the one
  fact sidecar a human writes.
- **RM62's rule was one-sided as shipped.** "Narrow the authored bound to float32" rests on
  `float32(0.3)` being above `0.3`; `float32(0.9)` is **below** `0.9`, so narrowing an authored `0.9`
  drops a row whose measurement never went through float32. The rule that survives is the one
  SCHEMAS.md's heading always gave: compare *in* float32. Now on the `measure_max` description, where an
  author reads it.
- **RM63's own correction overclaimed** (R2-14, unfixed). It replaced a false statement about homologs
  with *"read a pipe as heterozygous"*, and `C|C` loads — `1|1` is an ordinary phased homozygous call.
  The printed descriptions carry the true half; the comment still does not. A correction is where this
  happens: the reviewer checks the claim being removed, not the one going in.

Two process notes. **Eleven units were green alone and one pair was not green together** — a test
pinned `"indel/MNV"` for an allele another unit was concurrently reclassifying as symbolic, which only
merging could catch. And **three of the nine new findings came from re-verifying a report rather than
relaying it**: one claim was refuted outright (R2-7, raised twice and now closed against every path),
one brief was wrong about where its own subject ran (R2-15), and one instruction had to be disobeyed to
avoid printing a false claim (D5-2).

## 2026-08-13 — 0.6.0: the design round, built — eleven items, the VCF 4.4 cluster, and a charter amendment

**The whole of [PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md)'s build list shipped**, in eleven parallel lanes
over one day. The reasoning stays in the proposal; the outcomes and what probing changed are in
[ROADMAP_HISTORY § 0.6.0](ROADMAP_HISTORY.md#060--the-design-round-built). This entry is the release
view: what a consumer will notice.

**A charter amendment landed first and alone, because four decisions turn on it.** The Constitution
ruled on whether a change is *legal* and said nothing about what a legal change *costs*. It now does:
a **parquet column is approximately free** (materialized, derived, no human types one), a **derived CSV
is half** (machine-written, but a human can still edit it, and that should be discouraged), an
**authored schema is full cost** (the rare author writes it). This grants nothing new — legality is
still Principles 3 and 8, decided first — but it retires the instinct that there were "too many tables",
which was right about some additions and wrong about others with no stated way to tell which. Its first
consequence is written into SCHEMAS.md: `resolution.csv` is a build-time artifact with exactly two
consumers and **gets no parquet, deliberately**.

### What a module author will notice

- **Coordinates now reach the pharmacogenomics tables** (RM43). A PGx module authored with rs-numbers
  used to compile to parquets with every coordinate null, so a consumer matching a patient VCF by
  position matched nothing — silently, as an empty result rather than an error.
  `reference_examples/pgx_slco1b1_simvastatin` went from nine null rows to `12 / 21178615 / T / A,C`.
- **Symbolic and structural alleles are authorable** (RM5): the five closed VCF types with the length
  inside the token (`<DEL:1500>`, `<CNV:TR:30>`). A length-less one is dropped with a warning that says
  *dropped*, and refused under `--strict`.
- **`*` is writable** (RM59) — the allele that could not be observed, which any joint-called VCF emits
  and which no row could previously carry.
- **`chrM` validates** (RM60), folding to `MT`. The gate was stricter than the normalizer beside it.
- **A bin can cite its own threshold** (RM47): `MeasureBinRow.pmid`. The bin row cites, the citation
  table describes — and a `studies.csv` row may now name no variant at all.
- **A VCF pointer can name its namespace** (RM53) — `INFO/DP` versus `FORMAT/DP` — and say which element
  it means on a multi-valued field (RM54). Both are widenings; a bare key stays legal.
- **Two new derived tables**: `gene_validity.csv` (RM24) and `clinical_assertions.csv` (RM25).
- **A PMC id is refused by name** (RM50). `PMC 3110566` used to be *accepted* as PMID 3110566 — a real
  id for an unrelated article — so a cell that compiled before may refuse now. That is the fix.
- **The manifest can say what was checked** (RM45): a `verification` block, or nothing at all, which
  reads correctly as *says nothing* rather than as a pass. Every field is marked untrusted.

### Two behaviour changes worth reading before upgrading

- **Two reference examples were re-authored because they were wrong**, and their `content_signature`
  moved: `mt_heteroplasmy` wrote `source_field=AF` meaning this person's heteroplasmy fraction, while
  the spec's `AF` is the *cohort* frequency of that ALT — both floats in `[0,1]`, both binning cleanly,
  and one of them tells a carrier they are asymptomatic on the strength of how rare the variant is in a
  reference panel. `htt_repeat_expansion` gained an element rule for the same class of reason.
- **A wrong-build coordinate is now an error in both modes** (RM48): a position past its contig's end,
  or a contig only the other assembly names. It is arithmetic rather than judgement, so it does not
  follow the mode ladder. rs-number recovery against Ensembl's permanent GRCh37 service reports and
  never fills.

### Corpus effect, measured rather than assumed

Across all eleven reference examples: `content_signature` moved on **two** (the two re-authored above),
`artifact.digest` on **seven** (new optional and stamped columns — Principle 4 scopes byte
reproducibility to a fixed `compiler_version`), `resolution_signature` was **gained** by the four
table-only modules carrying a `resolution.csv` and no `variants.csv` — precisely the hole RM45 closed —
and the source signature moved nowhere. Test suite **1535 → 2046**.

### One pattern, found three times independently

Three lanes shipped the same defect and each was caught by its own code review: a check re-run after
resolution counts the **expanded** rows, so an rsID resolving to several loci reports one finding twice
with different numbers; message-dedup keys on the sentence and cannot collapse them, and both reach
`manifest.compilation.warnings`, which RM44 established is a surface consumers parse. Measured at
"1 row(s)" beside "2 row(s)", and at 328 beside 337 on `pathogenic_clinvar`. The rule now in CLAUDE.md
covers this and its opposite: **re-run a check after resolution exactly when resolution changes its
input, and never when the message embeds a count.** `_check_contig_ploidy` is not a counterexample — it
had to *move* behind resolution because resolution fills `chrom`.

Also fixed, both pre-existing and both found by a lane reviewing someone else's shipped work:
`reverse_module` re-emitted the deprecated `sources.csv` spelling, so a module and its own round-trip
disagreed on a published manifest field; and the `derived/` near-miss guard caught nothing it claimed
to, so authored tables placed under `derived/` compiled **green and empty, silently**.

## 2026-08-12 — 0.6.0: the version bump, and the first three items of the line

**All three packages move to 0.6.0 together** (`schema`/`compiler`/`enricher`), and the
inter-package floors move with them. The two entries below dated 2026-08-12 — `manifest.readme` and
`manifest.derived` — were already labelled 0.6.0 while every `pyproject.toml` still read 0.5.4; the
bump makes the number real, and everything from here lands under it. Cutting a release from the
branch is still the user's call.

### RM44 — publish the denominator, so a vacuous `fully_resolved` reads as one

`manifest.compilation.fully_resolved` is `all(...)` over the module's variant rows, so on a module
carrying no `variants.csv` it is `all()` over an empty list — **vacuously true**. The field is not
wrong; it cannot say *which* question it answered, and the trust rule its own comment documents
(`resolution_mode == "strict" or fully_resolved`) reads it as a module-level verdict. A consumer
followed that comment and badged two modules that join to no VCF, then repaired it by
substring-matching the 0.5.3 warning's prose — a bad place for a sentence to be.

`Compilation.resolution_subjects` is the count the flag quantifies over, taken **after** the
one-to-many rsID expansion because that is the list `fully_resolved` iterates (`pathogenic_clinvar`:
328 authored rows, 337 subjects). `fully_resolved=true` beside `resolution_subjects=0` is then
self-evidently vacuous, with no new vocabulary and nothing to parse out of a warning. Five of the
eleven reference examples are in that state today.

**It restates a number `Stats.weights_rows` also carries, and the code says so.** Measured, the two
are equal on every example, because the materializer emits one weights row per in-scope variant row.
That is a property of the current transform rather than a contract, and `Stats` is documented as
card/detail *display* facets — a consumer keying trust on it would be keying on a coincidence in a
block that promises none. A denominator belongs beside the flag it qualifies; a test pins the two
together so a divergence becomes a decision instead of a drift.

Not done, deliberately: `fully_resolved` stays `bool` (consumers branch on it directly, so a `None`
is a breaking read for all of them — the reporter asked for this explicitly), `UNJOINABLE_PHRASE`
and its pinning test stay (this makes the vacuity visible, it does not make the tables joinable —
that is RM43), and there is no second counter, per RM45's settlement of three things into three homes.

### RM51 — `licensing.csv`, so the major only has to remove a spelling

`sources.csv` records licence *terms*, and its name collides with the `source` **column** that means
"which link answered" in four other tables — which is why SCHEMAS.md needed a three-row table to
explain which of `studies`/`literature`/`sources` is which. A rename landing only at 1.0 would have
to **add** a spelling at the major and remove one at the next. Landing the alias in a minor inverts
that: every module drafted from here carries the new name, so 1.0 removes rather than adds. The old
spelling is **deprecated here** — warn-only, read exactly as before — and goes at 1.0, which is the
cadence the 0.6 charter amendment settled, and this is the case that prompted it.

Minor-legal for a checked reason: the fact sidecars are deliberately outside `_INPUT_FILES` (their
identity is the fact hash, not the raw bytes), so the filename enters no identity at all. Proven by
compiling one module under both names and comparing — same `artifact.digest`, `content_signature`,
`manifest.sources` and `resolution_signature`.

**What does not come along, taken knowingly**: `sources.parquet` is inside `artifact.digest` and read
by name, and `manifest.sources` is a published key. Both renames break a reader, so the whole 0.x
tail reads `licensing.csv` → `sources.parquet` → `manifest.sources`. That is a real legibility
regression against today's single consistent (bad) name, and it is the price of not paying for the
rename twice. A test pins it, so a well-meaning follow-up cannot "finish" the rename into a
published key.

The item estimated **five** enricher write sites; there are **nine**. `record_source_terms` and
`merge_sources_file` now take the spec directory rather than a path, so none of them can name a
spelling by hand. The ninth was `pgx.py` — the one pass whose *primary* output is this table and the
only one calling `write_sources_csv` directly, so its literal would have re-created the retired name
behind the alias's back.

### RM49 — `derived/` tolerated on input, so a legible spec tree recompiles where it sits

Nothing in a flat spec listing says which files a human wrote and which the enricher produced. A
registry gave its publishers a `derived/` tree and found a downloaded module does not recompile where
it lands, so their layout stayed transport-only (flatten on upload, re-split on download). This makes
the layout a *tolerated* input location — never required, never canonical: `reverse_module` still
emits a flat tree, and making `derived/` canonical would buy two supported layouts and have `reverse`
emit a tree older compilers in the same major cannot read.

**The write side had to be decided in the same change**, which is what kept this a design round.
Tolerating the location on input alone breaks on first use: `enrich` on a downloaded split module
writes to the root, leaving both copies — the collision, reached by following the documented workflow.
So the rule is RM51's, shared: **write to the file you read**, and **both present is an error naming
both paths**. Never a merge, never newest-wins — these tables are fact-hashed *and* hand-editable, so
two copies are two claims and preferring one discards a curator's override.

Scope is the machine-written sidecars only. An authored table does **not** get a second home, and the
asymmetry is the point: two legal places for `variants.csv` means a module can carry two with the
ignored copy invisible. `_check_misspelled_tables` follows into the subdirectory against the derived
names alone — without that, tolerating a location would put a typo'd `derived/varaints.csv` exactly
where the guard cannot see it, buying a convenience by re-opening the hole S16 closed. That is also
the argument against "search any subdirectory": one fixed name is the only version the guard can
follow. `manifest.derived` records the relative path, so `FileEntry.name` carries `derived/…` for a
split tree — legal there because that block is documented transport-only.

**The shared piece is `just_dna_format.layout`** — the names, the subdirectory constant, and one
resolver, in the schema tier because four parties must agree on this layout (compiler reads, enricher
writes, publisher uploads, registry re-splits) and every disagreement in `locations` so far has been
silent. Pure `pathlib`, so the dependency-light tier is untouched.

### A `-` where a `_` goes is now accepted in every closed vocabulary

Not an `RMn` — a usability defect found while writing the above. The enricher CLI already normalized
`--use non-commercial` on its way in, while `SourceRow` refused the identical string in a cell: the
surface an author learns the vocabulary from taught a spelling the file rejected. This DSL exists for
the human — if the project only wanted machine precision it would ship parquet and no CSVs — so a
separator slip in a categorical is an authoring cost the schema should absorb.

`vocab.match_vocab` is the one definition and `check_vocab` runs it, so every closed vocabulary gets
it and the CLI's private copy is gone. The value as written is tried first and both swap directions
after, so a future hyphenated member cannot be broken by this; the match **canonicalizes**, so what
is stored, fact-hashed and compared is always the declared spelling. Widening, never narrowing (P3):
everything that validated before still validates, and a value that names nothing still fails with the
full list. The evidence it was worth doing is in the diff —
`test_validate_agrees_with_compile` had used `non-commercial` as its example of an *invalid* value.

### Corpus and verification

Four reference examples move to `licensing.csv`; `hfe_hemochromatosis` deliberately keeps the old
spelling so the deprecation path stays exercised on a real module, with its README saying why.

All eleven reference examples keep their exact `artifact.digest`, `content_signature`,
`resolution_signature` and `source_signature` across the whole batch — compared through the CLI
against a pre-branch baseline, including under the split layout and the renamed file. The manifest
was never inside the digest; the filename and the location are not either.

## 2026-08-12 — docs: the round-1 field notes are retired, and two accepted asks finally land

**S27 + S28, refiled from `docs/CONSUMER_FIELD_NOTES.md`, which is removed in this pass.** That file was
the pre-0.4 round-1 thread: a consumer's report with the maintainer's answers written inline as
`↳ maintainer reply` blockquotes. It was a **second inbox**, with its own reply idiom, that
`.claude/triage-state.sh` cannot read — so while the live inbox correctly said nothing was owed, ten
accepted asks sat in a file no ledger covered. Establishing what shipped found eight delivered (several
over-delivered: `reference_sequence`, `requires_callable`, `acmg_sf` and `actionability` were promised as
*reserved names* and were **built as columns**; `repeat_alleles`/`heteroplasmy`/`pgs` froze in 0.4) and
**two never written at all**, both accepted at the time as "trivial, docs only":

- **S27** — the `effect_allele` liftover ref-flip caveat. What shipped instead is stronger than the
  requested caveat: 0.5 checks `effect_allele ∈ {ref} ∪ alts`, non-reconciliation is a named permanent
  blind spot in COMPILER.md, and a flipped reference base is caught by `verify_reference_alleles`. What
  was owed was the pointer from the **schema tier**, since a verify-only consumer never opens the
  compiler's docs. Now a paragraph beside `VariantRow`'s field list in SCHEMAS.md, naming RM48 for the
  hg19 authoring path.
- **S28** — the normative **consumer join contract**. The rule "absent from a variant-only callset ≠
  hom-reference" existed only inside `requires_callable`'s field *description*, which
  `describe`/`requirements`/`reference` print to an **author** — while the obligation binds the
  **consumer**. Documented in the wrong place for the party it binds, for three releases. SCHEMAS.md
  gains *The consumer join contract — three states, and the one that gets collapsed*: the MUST/MUST NOT
  as the reporter wrote them, the four columns that express it (`requires_callable`, `callable_from`,
  `quality_from`+`min_quality`, `MeasureBinRow.unresolved`), the "present but matching no bin" third
  state kept distinct from `unresolved`, and Kleene combination. No schema change — the reporter's own
  framing (a consumer concern, not a module field) still decides it.

**Also fixed, found while probing S28: a docstring claiming a diagnosis the code no longer produces.**
`vocab.reject_reserved`'s docstring illustrated itself with "`caller` fails differently from `xyzzy`",
but `caller`/`caller_version` were *dropped* from `RESERVED_NAMES_0_4` rather than built, so `caller`
takes the generic `extra="forbid"` message like any other stray column. The example now uses
`reference_db`, the set's only member, and records what it used to say. Same class as round 1's own
single code finding (A2, a stale comment contradicting shipped behaviour), which is a fair note on which
to close the thread.

**The durable lesson, and the reason the file is gone rather than annotated.** A feedback document with
its own reply convention is invisible to the loop that exists to notice unanswered work, and "nothing in
the live inbox" then means nothing at all. Do not start a third one. The two live asks were refiled with
the reporter's prose extracted byte-for-byte and verified with `diff` before the file was deleted; the
whole thread is recoverable from git history at `53f9260`. One archived section's consumer preamble links
to the removed file and that link is deliberately left dangling — editing evidence to tidy a reference is
the one thing the history file does not do.

## 2026-08-12 (later) — 0.6.0: `manifest.derived`, so the enricher's own tables can be served

**S26, reported by `just-dna-registry`.** A publisher asked which files in a spec directory are theirs.
The derived-fact CSVs — `resolution.csv` plus `frequencies`/`gene_metrics`/`literature`/`sources` — were
attested by no byte hash anywhere: `_INPUT_FILES` excludes them on purpose (they are **fact**-hashed,
because the enricher, a human override and `reverse_module` all legitimately emit different bytes for
the same content) and only their *parquets* are in `_OUTPUT_FILES`. Every route a registry serves files
through is defined over what the manifest attests, so a consumer could not fetch the table that produced
a parquet, or diff the two to see what the enricher actually decided.

`derived: list[FileEntry]` mirrors `logs` semantically — optional, absent-is-not-a-failure, out of
`artifact.digest` and `content_signature` — and `inputs` in locality: hashed **where the files live,
beside the spec**, not copied into the module dir, because each is its own parquet's content in another
encoding and a panel's frequency table should not ship twice. `_DERIVED_FILES` is derived from
`_FACT_TABLES` rather than hand-listed, for the reason `SOURCES_FIELDNAMES` once lost a column.
`verify_manifest(check_derived=True)` and `verify --check-derived` re-hash what is present.

**The trap this field creates is pinned by a test.** There are now two hashes over one file answering
different questions, and reading the byte hash as identity would call a legitimate re-emission
tampering — the exact failure the fact signatures exist to prevent. A test rewrites a sidecar so the
facts are unchanged and the bytes are not, and asserts the byte hash moves while the fact signature and
`content_signature` do not. Verified against the previous commit on four reference examples: all three
signatures byte-identical, with `grch37_build` correctly getting an empty list rather than a fabricated
one.

**The second half is filed, not built — [RM49](history/ROADMAP_HISTORY_PRE_0_6.md#rm49--a-spec-directory-is-flat-so-a-legible-derived-layout-is-one-the-compiler-refuses).**
The reporter also asked that a `derived/` subdirectory be *tolerated* on input, so a downloaded module
recompiles where it sits. It is not the one-line fallback it looks like: `spec_dir / "resolution.csv"` is
resolved in eight places across two packages, and tolerating the layout on input without deciding the
*write* side breaks on first use — running `enrich` on a split module writes to the root, so the module
carries both copies, reached by following the documented workflow rather than by misuse. Two copies of a
fact-hashed, human-overridable table are two legitimate claims, so the collision cannot be resolved by
newest-wins or by merging without discarding a curator's override. Three candidate repairs are refused
in the item with reasons, one of which would re-open the hole S16 closed.

## 2026-08-12 — 0.6.0: `manifest.readme`, so a module's prose can travel with it

**The first change in this line whose legal release is a *minor*, and the version is therefore not
bumped here** — all three packages still read 0.5.4 and cutting a release is the user's call. A new
optional manifest field is additive under Principle 3 (the 2026-08-11 amendment): existing modules keep
validating, `schema_version` is unchanged, and the field is out of `artifact.digest` entirely, so it is
cheaper than a column. That makes it minor, not patch, purely because it is a new field rather than a
better diagnosis on an existing path.

**S25, reported by `just-dna-registry` relaying `just-module-creator`.** A publisher shipped a
`README.md` beside `module_spec.yaml`; the registry stored the bytes and then could neither serve them
nor tarball them, because both paths are defined over *what the manifest attests* and `ModuleManifest`
had no field for a readme. `logo` was the precedent and the asymmetry was pure accident of history: a
logo can be listed, hashed, fetched, verified and swapped; prose with all the same properties had none
of the machinery. The motivating module is an 11-row set of explicitly *candidate* findings — most from
a preprint, one association not significant — where the README saying so is the single most important
artefact for anyone deciding whether to install it, and it was the one thing that could not travel.

`readme: FileEntry | None` mirrors `logo` exactly: discovered from `manifest.README_CANDIDATES`
(`README.md` first, then the other stem and `md`/`rst`/`txt` in a fixed order, so two readmes on disk
cannot resolve by luck), copied into the module dir, hashed, and **outside both identity halves** —
`artifact.files`, hence `artifact.digest`, and `content_signature`. `verify_manifest(check_readme=True)`
and `just-dna-compiler verify --check-readme` re-hash it.

**Both identities, not just the digest, because the reporter's own argument needs both.** They rejected
putting `README.md` in `artifact.files` themselves: on an immutable registry a corrected typo in a
caveat would then cost a version number, and the corrected module would collide with its own predecessor
under a name-independent content-dedup check. That only holds if prose stays out of `content_signature`
too, so the tests compute both and a dedicated case rewrites a readme and asserts only its own hash
moves. Measured on six real reference examples against a baseline worktree: `artifact.digest`,
`content_signature` and `resolution_signature` byte-identical, each now attesting its `README.md`.
Inlining the text into `display` was rejected for the reporter's reason — a readme is unbounded (this
one outweighs its module's data) while `display` is inlined into every card a catalog serves.

**The publisher was the gap that would have made the field decorative.** `upload._ALLOW_PATTERNS` had
`logo.png`/`logo.jpg` and no readme, so a manifest would have attested a file the HuggingFace repo did
not carry — the same silent shape as ClinVar's unpublished `citations/` and ClinPGx's dropped
`LICENSE.txt`. It now imports `README_CANDIDATES` rather than copying it, so a spelling the compiler can
discover cannot fall out of what the publisher sends. (`logo.jpeg` is a pre-existing instance of that
skew, left alone: widening it is not this item's decision.)

Two adjacent corrections, both found by reading rather than reported:

- **`integrity.artifact_digest`'s docstring still called the digest "the version's immutable *content*
  identity"** — the exact wording S7 got corrected in SCHEMAS.md, against Principle 4, which makes the
  digest the **byte** identity and `content_signature` the content one. The docs were fixed when a
  consumer made that misreading; the code copy outlived the fix, next to the field whose whole design
  turns on the distinction.
- **`_check_misspelled_tables` advertised a README as the headline *tolerated* file** ("nothing outside
  the known table set is read, hashed, or in artifact.digest"). A readme is now read and hashed and
  still moves no digest, so the message names curation notes and a publisher's receipt instead, and the
  claim narrows to the one that is still true. S16's test asserts both halves together now.

Suite 1442 → 1448 (six new tests); every reference example still recompiles byte-identically.

---

**Entries dated 2026-08-11 and earlier — the whole 0.5 line and everything before it — are in
[CHANGELOG_PRE_0_6.md](history/CHANGELOG_PRE_0_6.md).** The split is the 0.6.0 version bump, not a change of
format: the archive is this same document continued downward.
