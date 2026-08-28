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

## 0.7.0 (latest) — RM133: the card subtitle gets a home a registry can amend

**Package: `just-dna-format`.** Additive under Principle 3 — two new constants and one new number, no
authored field, no schema change, no parquet column, nothing invalidated. Principle 4 is deliberately
untouched: the closure binding is exactly what it was.

- **`normalize.PRESENTATION_AUTHORITY_KEYS = frozenset({"short_description"})`** — a second
  registry-owned key family beside `IDENTITY_AUTHORITY_KEYS`, with
  **`PRESENTATION_AUTHORITY_REASONS`** mirroring the identity map. Separate sets because ownership and
  presentation are different reasons for a key to be registry-owned and a consumer may stamp one
  without the other; **one stripper** — `strip_authority_keys` takes either family or their union, so
  there is one path and not two.
- **`normalize.SHORT_DESCRIPTION_MAX_CHARS = 120`** — the card-subtitle calibration, published here
  rather than guessed at downstream. It **refuses nothing**: no model carries it as a `max_length`,
  `Display.description` stays unbounded on purpose, and absent the key everything behaves as before.
- **Why this and not a smaller binding.** Rewriting `module.description` moves no `content_signature`,
  no `artifact.digest` and no fact signature, and still drops the closure, because `manifest.inputs`
  covers the raw bytes of `module_spec.yaml`. The binding stays as it is — an attestation answers *is
  this the same document a named person signed off*, and a partition along `content_signature`'s line
  would make a closure transferable across a rename. A `short_description` field on `ModuleInfo` is
  refused for the same reason: every key in the spec is on the un-amendable side.

**For `just-dna-marketplace` and any other publishing registry — this is the integration note.** Store
`short_description` in your own record beside the module, never in `module_spec.yaml`. Import the two
constants from `just_dna_format.normalize` and strip the union before handing a block to our
validator: `strip_authority_keys(block, IDENTITY_AUTHORITY_KEYS | PRESENTATION_AUTHORITY_KEYS)`. The
stored bytes then never move, so `manifest.inputs` still matches, `verify_manifest(check_inputs=True)`
still passes and a closure over those bytes still stands — **your `amend_display` endpoint is not gated
on us**. Read the ceiling off `SHORT_DESCRIPTION_MAX_CHARS` rather than hardcoding 120; enforcing it is
yours to do, since we bound nothing. Nothing is retroactive: the seven published modules met every
requirement that existed and are untouched. On the CLI, `--strip-identity` still means identity alone;
the second family is `--authority-key short_description`.

## 2026-08-24 — twelve consumer items in one pass (S63–S74)

**Packages: `just-dna-format`, `just-dna-compiler`, `just-dna-enricher` — a MINOR, deliberately
left uncut (2026-08-27).** The number is not decided, so nothing here names one: the replies'
markers read `next-minor` and every doc dates a change by its `Sn` rather than by a version that
does not exist yet. Answered is not installable, and here it is not even tagged.
Most of what follows is patch-class legibility, but three changes are each independently additive
and so size the release under P3: `VerificationRecord.producer`, `compilation.dropped_rows`, and
the new public `load_spec`. Legality sizes the release and severity only orders the queue inside
it, so a pass that is mostly warnings still cuts as a minor when one field is new. Two
reporters, twelve items, answered serially. Eight shipped code, four are filed; the counts below are
off the tree rather than remembered.

**Filed:** RM128 (`enrich()`'s lost work), RM130 (a conflict sidecar), RM131 (`warnings` structure),
RM132 (`pharm_variants.csv` citations), RM133 (an amendable card subtitle), plus the `stats` counter
retype queued to the 1.0 tracker.

**The two findings that cost real work:**

- **A sidecar writer that truncates in place leaves a valid short file, and a merge believes it
  (S66).** Nine writers across the enricher and format tiers used `open(path, "w")` + `csv.DictWriter`,
  so a killed process left a table that parses cleanly and is simply shorter. For `resolution.csv`
  that is the worst residue available: the next run reads it back, merges on `subject`, and believes
  it — and the three branches of `enrich()` that deliberately write **no row** for an unanswerable
  subject make "fewer rows" a state the table reaches honestly. The reported incident had a
  client-killed run keep going, reach the write, and replace a restored 330-row table with **162**
  rows, after which the module validated, closed and compiled green. Fixed with
  `layout.atomic_writer`/`atomic_write_text`. **Three writers were reported and nine were routed** —
  the guard walks the set with an AST check and asserts an equality, and was watched failing on
  pre-fix source first.
- **The better-resolved module was the loud one (S67).** `_verify_vrs_ids` emitted one warning per
  allele where `_vrs_coverage` aggregates the same fact, and which path an allele took was decided by
  whether the enricher happened to mint an id for it. Noise ran *inversely* to how well-resolved a
  module was: 80 of a 101-row module's 85 warnings, with the three findings its author could act on at
  positions 83–85, against a 57,595-row module producing one line. The governing rule was already in
  the file — *a finding no authored edit could clear is not a `strict` matter* — spent on severity
  alone.

**Also shipped:** field descriptions on the three `ModuleInfo` fields that had none, plus a guard
asserting every authored field across 28 models carries one (S63). `VerificationRecord.producer`, so
a merge stops restamping records it did not produce, with the document-level field's own description
corrected because it *was* the false claim (S71/RM129). The `panel:` deprecation gated on its
replacement existing and no longer claiming *"nothing else is lost"* — both halves, since gating alone
leaves the false clause standing (S69). A `detail` on the clin-sig record and a warning when any check
reports findings; nothing read `VerificationRecord.findings` at all (S70). `row_count`, `table_rows`
documented, and a composite-`gene` warning (S72). `compilation.dropped_rows`, closing the residue a
consumer's recomputation guard could not see (S65). Public `load_spec`, ending a private-symbol reach
the enricher itself was making (S74).

**Two answers are the deliverable and shipped no code.** S64 asked us to justify the attestation
binding or split it along `content_signature`'s line — the split is refused because that line excludes
**name, version and namespace**, so a binding drawn there makes a closure **transferable across a
rename**; and the route that actually unblocks the registry is registry-owned metadata
(`IDENTITY_AUTHORITY_KEYS`' shape), which means their endpoint was never gated on us. S73 asked which
provenance model `pharm_variants.csv` was meant to use, and the tree had answered it a release earlier
under a rule nobody had stated generally: **a row cites when its claim is finer-grained than
`studies.csv`' key.**

**A 26-finding dogfooding note had arrived in `ROADMAP.md` rather than the inbox**, where the ledger
cannot see it. Eight of its findings had `Sn` twins; the other eight are dispositioned in place — one
(D17) did not reproduce, one (D11) is our own documented policy, three went to the idea-book with the
cheap half separated from the design half, and one is cross-repo.

Suite 2881 → 2916 (+8 skipped), green throughout; `ruff check` clean.

## 2026-08-21 — the Constitution says rules only, and gained three (RM127 closed, RM126 → 0.7)

**Documentation only; no package changed.** [S62](CONSUMER_SUGGESTIONS_HISTORY.md)'s finding was that a
*corrected derivation* — an existing published field whose derivation changes, so the same spec yields
a different value — is in none of the three sizing rows, and that the safety argument used to clear it
(*`content_signature` is unchanged, measured*) is **incapable of failing**, because `stats` sits outside
the signature by design. A check that cannot fail read as a pass (`@tautology-zero`), one level up from
where RM123 caught the same shape the same week.

**Principle 3 gains two rules.** *Release class and artifact staleness are different axes* — a corrected
derivation is a bug fix, so it **may ship in any release**, since deferring it to a minor means
knowingly serving a wrong value meanwhile; what it may not do is ship **silently**. And *authored
identity is not the sizing test*, which disarms the clause that sized RM121.

**The charter is now rules only, by its own header item**, and came out **11.5% smaller (17,239 →
15,263 bytes) while gaining three rules.** Reasoning, evidence, open questions, superseded states and
rhetoric are banned from it, along with any outward reference beyond a published version a rule turns
on — the old phrasing said the file *"points to no other document"* as a description and `the 0.4.1
plan` drifted in anyway, so it is now an instruction. The four existing amendment entries moved
**verbatim** to the new [CONSTITUTION_AMENDMENTS_HISTORY.md](CONSTITUTION_AMENDMENTS_HISTORY.md), which
may cite `RMn` and consumer reports freely.

**Principle 9 exists because the audit caught a rule about to be deleted.** The cost-by-layer pricing —
parquet approximately free, derived CSV half, authored schema full — was stated *only* inside an
amendment entry, and is cited by CLAUDE.md's coding standards. Moving the amendments out wholesale
would have silently removed it, so it was promoted to a numbered principle instead.

**[RM127](ROADMAP_HISTORY.md#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one)
is closed** — filed, rewritten and answered inside one pass.
**[RM126](ROADMAP_0_7.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)
moves to 0.7 as owed rather than deferred**: the amendment obliges a release to declare its
corrections, and that channel does not exist yet, so the charter currently names a surface that is not
there. Two axes — `output_differs` measured by a previous-tag sweep, correction-versus-addition
declared — with a gate that fails a release whose measured change carries no declaration.

## 2026-08-21 — a patch changed a parquet schema, and nothing could say so (S62, RM126, RM127)

**Nothing shipped; two items filed.** A new consumer, **just-dna-registry**, adopted
`0.6.1 → 0.6.6` and ran the catalog sweep whose job is to find published artifacts that should be
recompiled. It correctly reported nothing to do, at all three layers, while `manifest.stats.genes` —
which feeds their gene facet — sat stale on every star-allele and copy-number module they publish.

**Measured, and wider than the report.** All sixteen `reference_examples/` compiled under `v0.6.1`
in a detached worktree and again under `0.6.6`, spec inputs byte-identical across the interval, which
is entirely patch releases: **16/16 changed a published manifest field, 10/16 moved `artifact.digest`,
0/16 moved `content_signature`.** The digest movement is `studies.parquet` +257 bytes on each of the
ten — **RM120's `curator` column, first present in `v0.6.5`.** So the *parquet schema* moved across a
patch interval, which the reporter had not seen; they reported changed manifest fields.

Authored identity held on all sixteen, which is the charter working: an unset optional column is
omitted from `content_signature`. **The sharpest number is the one that took a recount: six of the
sixteen changed a published, indexed manifest field with *both* hashes byte-identical** — `apoe_epsilon`
went `genes: []` → `["APOE"]` at the same `artifact.digest` and the same `content_signature`.
(`stats.genes` moved on seven modules; an earlier draft of this entry said eight.) That is precisely why nothing can see this — a digest comparison, a
signature comparison and `revalidate` are each correct to report no change while an indexed field goes
stale. **[RM126](ROADMAP_0_7.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)**
is the missing third axis, asked for as an interval-keyed declaration with the axes separated,
explicitly not a `should_rebuild` verdict, and with unknown-interval as a *state* rather than an empty
result. The guard it needs is a measurement rather than a hand-kept map, and the sweep above is its
prototype.

**[RM127](ROADMAP_HISTORY.md#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one) was filed and rewritten the same
day, and the withdrawal is the useful part.** It first read *the release table and the practice
disagree*, indicting `curator`'s patch. Withdrawn: `curator` is additive, no published module can carry
it, **no stored value became wrong**, so a patch is defensible and the table is merely strict. The
defect is RM121 alone, and its change class is not in the taxonomy — an existing published field whose
*derivation was corrected*. **Why it read as safe is the keeper:** the only test applied was *does
authored identity move*, and `stats` sits outside `content_signature` **by design**, so that test
cannot fail there. A tautology read as a pass (`@tautology-zero`), one level up from where RM123 caught
the same shape that week. The structural edge — a field outside identity is one nothing can see move,
so **the cheapest changes have no detection channel**: six of sixteen examples changed a published
indexed field with both hashes byte-identical. And since a corrected derivation is a **bug fix**,
deferring it to a minor means serving a wrong value meanwhile — so the release number cannot carry
staleness at all, and the two axes separate rather than reconcile.

**Not an instance, and separated deliberately:** RM106's warning de-duplication. The release table
already sizes a warning or a count as patch-level legibility, so `compilation.warnings` was never
promised stability across a patch. It is the argument *for* the reporter's axis decomposition — warning
text is patch-legal and a column is not, so one "did the output change" bit would have been useless.

**Scope of the negative:** the sweep is an offline compile over sixteen specs. Enricher-side outputs
were not compared across the interval, so `verification.json` and the documents RM123 touched are
unmeasured rather than unchanged.

## 2026-08-21 — the triage loop's threshold counter went blind for the second time

**Documentation only; no package changed.** The [triage loop](CONSUMER_TRIAGE_LOOP.md) § 4 counters
grep `ROADMAP.md` for open items to decide when to ask the user whether the next minor should start.
The 2026-08-21 decision round rewrote all four open items' status lines to lead with what had just
been decided, which pushed the release-class phrase out of the slot the grep reads and wrapped one of
them across a line. **The count read zero with four grounded items in the file** — the direction that
matters, because a zero reads as an all-clear.

This is the counter's **second** failure: the first counted a literal `**0.6**` and kept counting it
after 0.6 shipped, fixed by counting the idiom instead. The idiom then drifted. The durable half of
the repair is that the release-class token is now named as a **fixed field** in
[ROADMAP § Active items](ROADMAP.md#active-items) — verbatim, on one line, with everything else the
status wants to say after it — so the rule sits where a status line is *written* rather than only in
the file that reads it. The incident is in [CONSUMER_TRIAGE_LOOP § 6](CONSUMER_TRIAGE_LOOP.md#6-gotchas-found-while-building-this).
A phrase a tool greps is an API whether or not the tool belongs to a consumer (`@warning-text-is-api`).

Also: the CHANGELOG's `(latest)` marker had stayed on the second entry when the decision round
prepended a new one, against this file's own newest-first rule. Moved — **and then it went stale a
second time within the same pass**, when this entry was prepended above the one that had just been
corrected. That is twice in two prepends. The marker is a *derived* fact — "the topmost entry in a
newest-first file" — restated by hand, which is the exact pattern the RM104–RM111 batch named as the
thing worth carrying out of it, and the file's preamble already says *Newest first*. Surfaced rather
than acted on, because retiring a convention across every heading is a bigger call than this pass:
the next person to trip on it has the evidence to delete the marker outright.

## 2026-08-21 — just-dna-lite's consumer-side changes from the just-module-creator hand-off

**Consumer-side only; nothing in this repo changed.** Recorded because the working agreement asks
for cross-repo integration changes, and because the agents most affected are the hand-off's own
authors — they asked just-dna-lite for ~60 reads and this is what the first tranche did. Their
document lives at `just-dna-lite/docs/CONSUMER_HANDOFF_from_just-module-creator.md`; the reply, with
a verdict per item, is at `just-dna-lite/docs/reviews/consumer-handoff-triage.md`.

**A correction to what a consumer believed about the published corpus.** Both that repo's CLAUDE.md
and the hand-off assumed no module on HuggingFace publishes a `manifest.json` — CLAUDE.md said "every
module on HuggingFace today" and the hand-off called the logo fallback "dead code in production" on
the same premise. Measured 2026-08-21 against `just-dna-seq/annotators`: **all ten modules publish
one.** Attestation (INTEGRATION_0_6 § 2.8) is therefore the *normal* discovery path there and probing
is the exception. Checked for the failure that implies — a file present at the path but absent from
`artifact.files` is now dropped where it used to be probed and found — and the attested set matches
what is present on all ten, so no side table was lost.

**RM43's status was stale downstream by two releases.** just-dna-lite's docs still said the
`pharm_variants` coordinate fill "waits on RM43", and two comments in its annotation engine asserted
that the compiler applies `resolution.csv` to `weights.parquet` alone. Verified against installed
compiler 0.6.1 (`compiler.py:499`) and corrected. Consequence worth knowing if you maintain a similar
consumer: **classify a lead table by the values it holds, not by its family name.** Both generations
are live — that repo's shipped `pharmgkb` is a 0.5 artifact measuring 0 of 1482 rows placed, while a
0.6 recompile of the same spec qualifies for a position join — so a value probe routes both correctly
and no `positional_rows` gate is needed in the join path.

**A phase asymmetry that is a consumer bug, not a format one, and is now reported rather than
silent.** A VCF reader that sorts a genotype (as that repo's does) cannot match an authored genotype
held in homolog order, in either ordering. Sorting the *module* side is not the fix — it folds `A|G`
and `G|A` into one key and manufactures a match the module never stated — so the module side still
never sorts and the unmatchable rows are now counted and logged before normalization strips the `|`
that reveals them. Nothing here needs to change; noted so another consumer does not "fix" it by
sorting.

**Two consumer-side reads that now use this repo's own constants rather than restating them.**
`README_CANDIDATES` reached that repo's HuggingFace publisher allowlist, which had omitted it — so
`manifest.readme` attested a file the upload never sent, and `verify_manifest(check_readme=True)`
passed anyway because absent is not a failure there. And discovery now keeps `identity.version`,
`artifact.digest` and the `weighting` block from a remote manifest it was already fetching and
validating; before, every remotely discovered module reported no provenance at all. All three stay
tri-state.

**Filed separately in [ROADMAP.md](ROADMAP.md):** `manifest.stats.genes` is derived from
`variants.csv` alone, so a module whose gene is stated only in a PGx or binning table publishes
`gene_count: 0` and cannot be found by gene. Originally measured by just-module-creator; relayed
because neither consumer owns `variant_stats`.

## 2026-08-21 — a lookup finding that contradicted the payload carrying it (S61, RM125)

**Cut as 0.6.6** across all three packages and tagged `v0.6.6` on 2026-08-21; this entry read "still
uncut" until the tag landed the same day. It joins the two rounds below rather than taking a number of
its own. Tagged is not published — `uv publish` is a separate step and the maintainer's. `just-dna-enricher`
only — no authored schema, no parquet, no manifest field, and advisory findings are written nowhere, so
no digest and no signature moves. A **patch**. Publishing stays the maintainer's step.

**`lookup_variant` could return a coordinate and deny it in the same breath.** `lookup_variant(rsid=
"rs4988235")` came back with `2:135851076` in `loci` and, beside it, *"rs4988235: not in the injected
Ensembl snapshot, position remains unset"*. The cache link emits that line and the live link fills the
coordinate a few lines later; nothing revisited it. Reported by `just-module-creator`, whose reader of
this surface is an agent under a standing instruction to trust findings over bare values — so the two
halves of one response disagree about whether the lookup succeeded, and the durable cost is that a
finding contradicting the data teaches the reader to discount findings.

**The fix is the three-valued rule applied to a sentence rather than a cell.** At the moment the cache
link speaks, whether the position remains unset is neither true nor false but *unknown* — a leg that
has not run may still answer — so the link now reports only what it searched and withholds the rest.
`lookup_variant`, the one caller that sees both halves, states `"{rsid}: position remains unset"` once
at the end when nothing placed the variant. It is guarded on there being an rsID at all: a position-only
lookup fills `rsid_candidates` and never `loci`, and an unguarded closing line would tell a caller its
own supplied position was unset. The snapshot miss stays on the record, which the reporter asked for —
knowing a local cache is incomplete is what tells an author whether to warm it.

**The ClinVar twin had the same defect and an older one.** `clinvar.lookup_loci` is documented as
signature-identical to `resolver.lookup_loci` ("one implementation, no drift") and still said *"not
found in ClinVar, position remains unset"* — speaking for the source, which is exactly what the Ensembl
half was corrected out of in 0.5. It is reachable in the same call (the cache loop breaks only on a
hit), so a real run produced **two** false claims where the report scoped one. Both links now say *"not
in the injected `<source>` snapshot"*.

**Message texts changed, and they are an API.** The two snapshot-miss strings lost their trailing
clause and the ClinVar one was reworded; `"{rsid}: position remains unset"` is now its own finding. A
consumer grepping the old composite phrase should grep the two new ones. `SYMPTOMS.md` in the authoring
skill and `ENRICHER.md` are updated. `enrich()` is unaffected — it discards both links' warning lists,
so `lookup_variant` was the only reader either sentence ever had.

**Why a green suite held it:** neither phrase was pinned by a test, and every existing `lookup_variant`
test passed an **empty** cache directory, so no snapshot was located and the per-rsID miss line was
never emitted. Six tests now cover it against a populated snapshot that simply lacks the rsID — the
reporter's own method, running the tool against real rsIDs instead of reading it. Suite 2864 → 2870.

## 2026-08-20 — the 2026-08-19 doc audit's six patches (RM104–RM107, RM109, RM111)

**Cut as 0.6.6** across all three packages and tagged `v0.6.6` on 2026-08-21 — this entry read
"bumped, uncut" until then. What the tag carries is this round, the S57–S60 batch below, and S61/RM125
above: nine patch fixes in all. Every item here is a **patch**: no authored
schema changed, nothing was retyped, no published identity moved. One behaviour tightens — a duplicate
`(source, layer)` row in `licensing.csv`/`sources.csv` is now an **error** in both `validate` and
`compile`, where it used to pass silently — so a spec carrying one stops compiling. Publishing stays
the maintainer's step.

Six of the eight findings the 2026-08-19 audit turned up (it validated `just-module-creator`'s 24
per-table dossiers against this repo's code). **RM108 and RM110 are deliberately not here**: the first
needs a currency notion decided before a re-curation can be marked superseded, and the second moves
`gene_metrics.signature` for every module already carrying snapshot rows — legal, but a recompile the
ecosystem should be told about. Both stay open as minors.

**Five of the six were a derived value restated by hand somewhere else** — a suppression set beside its
merge key, an allowlist beside the extension set, a dupe key in the one map the finding loop does not
read, a check re-run without the filter its neighbour eleven lines away carries, a field description
restating an analogy true of a different field. The sixth is the empty-work path nobody runs. The suite
was green at 2859 tests throughout, and is 2864 now.

- **[RM104](ROADMAP_HISTORY.md#rm104--enrich_gene_metrics-raised-unboundlocalerror-on-the-ordinary-re-run)
  — the gene-metrics re-run raised out of the pass** (`just-dna-enricher`). `reference` was bound inside
  `if wanted:` and read unconditionally below it, so the **idempotent re-run** — the path
  merge-not-clobber documents as supported — and any module with no `variants.csv` raised
  `UnboundLocalError`. That is outside `GeneMetricsEnrichmentError`, so the single `except` RM101 built
  for exactly this caller caught nothing. The fix is one line; the test is the part that matters, since
  every existing merge test re-ran with `wanted` non-empty.
- **[RM107](ROADMAP_HISTORY.md#rm107--a-duplicate-source-layer-row-compiled-green-under---strict)
  — a duplicate `(source, layer)` row compiled green under `--strict`** (`just-dna-compiler`). No
  warning, a moved `source_signature`, and a pair free to carry opposite `commercial_use` in the one
  file the compile gate reads. **The consumer-visible change is the tightening**: both commands now
  refuse with `"<file>: duplicate row for key ('<source>', '<layer>')"`. A module whose licensing table
  carries one will need it removed. `licensing.merge_sources_csv` already merges on that pair, so
  re-running the enricher's licensing writer collapses the pair — checked — but it keeps the **last** row
  under the key, so where the two rows disagree (the case worth catching) picking the right one is a
  human's call and not the writer's. One source at two layers is unaffected, which is why the key is a
  pair.
- **[RM109](ROADMAP_HISTORY.md#rm109--the-gene-metrics-fetch-suppression-key-was-not-derived-from-the-merge-key)
  — a hand-written gene-metrics row did not suppress the fetch** (`just-dna-enricher`). The merge key is
  `(gene, dataset)` and "already done" asked `source.startswith("gnomad")`, so a correction recording
  `source="manual"` was re-fetched and the file came back with two rows under one key contradicting each
  other. Now derived from the key, scoped to the two dataset labels this pass writes so a ClinGen dosage
  row for the same gene still does not suppress it.
- **[RM106](ROADMAP_HISTORY.md#rm106--the-faf95-arithmetic-warning-was-published-twice)
  — the `faf95` warning was published twice** (`just-dna-compiler`). `_check_frequency_arithmetic` runs
  in `validate_spec` (RM93) and again on the compile side, and the compile side had no filter — so the
  line appeared twice in `manifest.compilation.warnings`, a published field, and a consumer counting
  warnings overstated what was wrong with the module. Measured at 15 warnings, 14 distinct. **A consumer
  pinning warning counts may see one fewer**; the text is unchanged.
- **[RM105](ROADMAP_HISTORY.md#rm105--logojpeg-compiled-was-attested-and-was-never-uploaded)
  — `logo.jpeg` was attested and never uploaded** (`just-dna-enricher`). `LOGO_EXTENSIONS` admits
  `jpeg` and discovery sorts, so the spelling the compiler *prefers* was the one `_ALLOW_PATTERNS`
  dropped, and the published manifest attested bytes the repo did not carry. The logo half now derives
  from `LOGO_EXTENSIONS`, as the readme half already derives from `README_CANDIDATES`. **Anyone who
  published a module with a `logo.jpeg` should re-publish**; the discovery order is deliberately
  unchanged, so nothing else moves.
- **[RM111](ROADMAP_HISTORY.md#rm111--three-shipped-strings-asserted-a-registry-override-of-license-that-nothing-performs)
  — the `license` strings claimed an override nothing performs** (`just-dna-format` +
  `just-dna-compiler`). Two shipped `Field(description=…)`, a module docstring and a code comment said a
  publishing registry stamps the authored `license`; it does not, and what the compiler actually does is
  warn when the declaration contradicts the annotation-layer sources. Documentation only — no behaviour
  changed — but it reaches authors through `describe_table`/`authoring_reference`, so a consumer
  rendering those descriptions will see new text.

## 2026-08-20 — a dossier audit's four reports (S57–S60, RM121–RM124)

**Folded into 0.6.6, cut and tagged `v0.6.6` on 2026-08-21** — this batch and the doc-audit patches above sat on the same then-uncut
number. Nothing here was added to an authored schema, nothing was retyped, and no published identity
moved. Publishing is the maintainer's step, as always.

Four reports from `just-module-creator`, filed the same day after they audited their own per-table
dossiers and their own attestations. Two are ours to fix, one is a documentation gap with a code-shaped
edge, and one is a 0.7 design that turns out to answer a question a 0.7 item has been blocked on.

**Two of the four turned out to be about a record that could not state its own scope**, which is the
reporter's sentence and is worth keeping: *a check that could not have failed should record why rather
than record a zero.*

- **[RM121](ROADMAP_HISTORY.md#rm121--manifeststats-described-one-table-and-was-published-as-if-it-described-the-module)
  — `manifest.stats` described one table and was published as if it described the module.** `stats.genes`
  came from `variants.csv` alone, so a module led by `diplotypes.csv`, `allele_function.csv` or any other
  gene-bearing kind published `gene_count: 0, genes: []` however many rows named a gene — and a registry's
  gene index is fed from that field. Measured on `reference_examples/cyp2c19_star_alleles`: **1,332 rows
  naming CYP2C19** against `genes: []`; seven of our sixteen examples carry no `variants.csv`, and seven
  of the eight non-variant gene-bearing models make `gene` **required**. `Stats`'s own docstring already
  said *"derived from the spec"*, so this was an unimplemented sentence and not a scoping choice.
  Shipped `module_stats` **beside** `variant_stats` — renaming it would be a major (S14's rule) — with
  `_GENE_BEARING_TABLE_KINDS` derived from `_TABLE_KINDS`, and derived fact sidecars structurally
  excluded. Building it recreated the RM44 defect it inherits: the post-symbolic-drop re-derive sat
  inside the `variants.csv` branch and `pharm_variants.csv` also drops and also carries a gene.
- **[RM123](ROADMAP_HISTORY.md#rm123--two-attestations-recorded-a-check-whose-scope-they-could-not-state)
  — two attestations recorded a check whose scope they could not state.** Two halves in two tiers.
  *PGx:* RM73's per-leg tautology skip has worked since 0.6.0, but `_function_check_record`'s **answered**
  branch built `detail` from the answered legs alone — so a CPIC-drafted module with PharmVar answering
  published a clean two-authority comparison with no sign that half of it was a copy against itself. The
  note lived on `result.warnings`, which is the run's stderr, and `verification.json` is what a later
  reader trusts. Both branches now sort by source: that file is a hashed input and `legs` fills in pass
  order. *Hints:* `REDUNDANCY_BEARING` is keyed on a bare column with no model attached, so the
  vacuous-check reason printed on six (column, table) pairs whose checker cannot see the table — right
  advice, false reason, and the false reason implies a green run is agreement.
  `REDUNDANCY_BEARING_TABLES` narrows the **explanation only**; the provider refusal stays column-keyed.
  The six unscoped columns are checked claims — RM43 puts resolution on the positional kinds, RM47 makes
  a bin a second citation site — and scoping either from the checker-name strings would have suppressed
  a *true* advisory.
- **[RM122](ROADMAP_0_7.md#rm122--the-measure-lookup-is-specified-and-nothing-anywhere-implements-it)
  — the binning family is now specified for consumers, and says so.** [SCHEMAS.md](SCHEMAS.md) gains the
  normative **measure lookup** beside the genotype join contract: scope to the group, select the row whose
  inclusive range contains the value, greatest `measure_min` on a shared endpoint, compare in float32
  (RM62), `unresolved` on a missing measurement and withhold on no match, and `trait_efo_id` multiplies
  the answer rather than disambiguating it. It opens with the plain sentence that the family is specified
  **ahead of its consumers** — verified: `just-dna-lite` touches all four binning tables in exactly two
  places and both count rows. The authoring skill now tells an author to write what the bins mean into
  the README. RM122 is open for the question they did not ask — whether the rule should also be a public
  function — which waits on a consumer to fix the signature against.
- **[RM124](ROADMAP_0_7.md#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it)
  — an authored overlay table, filed for 0.7.** RM83 named two exits from *nothing records that a row was
  overridden*; the reporter **built the first one** — a non-destructive capture/delete/re-derive/reapply
  wrapper — and it stops exactly where RM83 predicted. RM124 is the second exit with their shape, the tier
  settled in their favour, and four questions open. The sharpest is one only RM115 could expose:
  `(table, subject, field)` cannot key `resolution.csv`, whose published rule is `subject`.

**One report did not reproduce, and the reply says what was probed.** `enrich_facts` names no symbol in
any tier; read as the gene-constraint pass, the two states it describes have been separate since RM98 in
**0.6.1** — a looked-up gene gnomAD publishes nothing for gets a `not_found` row, a gene reachable
through neither route gets no row and lands in `unconsulted` with its own warning. The reporter is
running enricher 0.6.4.

**Triage thresholds moved to 20/30** the same day (dev-start and the stop-filing ceiling, from 10/20),
and the block that counts them was worse than stale: it grepped `Status** open — **0.6**`, an idiom
`ROADMAP.md` stopped using once 0.6 shipped, so it returned `0` however full the queue was. It now counts
the two forms the file actually carries. A stale counter reads as an all-clear.

Suite 2835 → 2859 passing (2,867 collected, 8 skipped — the opt-in network tests).

## 2026-08-20 — a triage batch of seven, and the one authored column in it (S50–S56, RM115–RM120)

**Cut as 0.6.5** across all three packages and tagged `v0.6.5` on 2026-08-20 — the aligned number, since
schema, compiler and enricher all moved in this batch. Tagged is not published: `uv publish` is a
separate step and the maintainer's. Seven items from `just-module-creator` across three reports in one day. Additive
only: **one new authored column** (`StudyRow.curator`), two new manifest/document fields, three new
public names, two new checks and one documentation fix. Nothing removed, nothing retyped, no existing
authored column moved — so an existing module's `content_signature` is unchanged, verified.

**Two of the seven came from the reporter re-reading rules they had themselves asked us for**, and one
is a retraction. That is worth recording as the useful shape of a consumer relationship rather than as
a curiosity: S55 withdraws the argument behind S11, and S54 is the measurement they took while checking
it — 3,668 quotes across four published modules that the rule had produced, all of them titles.

- **RM115 — a derived sidecar's merge key is published, and every pass reads it.** RM113's question
  asked of the machine-produced tables, where the key existed only as a dict-key expression inside each
  writing pass. `hints.key_fields` already routed derived names through `derived_model_for`; the seven
  fact models simply declared no key. The reporter's approximation was coarse on exactly the two tables
  where one subject carries several rows, both reproduced. `KEY_RULES` gains `subject` for
  `resolution.csv` (one rsID, several loci — reporting `equality` would call a legal file a duplicate)
  and `TableKey` gains `fallback` for `gene_validity.csv`'s two-level key. `base.merge_key` is the
  row-level answer and **every pass keys its `existing` map through it**, which is what stops the two
  drifting. The rewire exposed three lookup sites restating the key positionally; one would have
  refetched every cited article on every run.
- **RM116 — `compiler.spec_tables(spec_dir)`.** The rows behind `content_signature`, defaults-folded,
  plus the declared build; `content_signature` is now that plus the hash. Anything finer than a
  whole-module digest had to restate the private roster and the `defaults:` fold, and the fold silently
  produces a wrong answer — measured, the obvious build outside the function reports twelve changed rows
  where there are none. COMPILER.md now names the roster and says the licensing table is outside it.
- **RM117 — `ProvenanceItem.outranks`, and the check half filed.** `{column: why}`, so a module that
  deliberately disagrees with a source can say which column and why. Per column, because a row may
  outrank an archive on `clin_sig` while its `direction` is unjustified; per *variant*, because
  `Provenance.item_count` is a published number meaning *variants carrying a record* and redefining it
  is a silent break. Whether a check downgrades a mismatch to INFO is **open** (RM117): the
  pre-emption guard is a convention the code cannot see, and a record is not yet bound to the value it
  justifies.
- **RM118 — a `provenance_quote` that is the article's own title is reported.** A title appears in its
  own fulltext, so the quote check cannot fail on one — `quotes_found` equals `quotes_authored` while
  nothing about any claim is established. `LiteratureResult.titles_as_quotes` plus a yellow CLI line.
  The discriminator is the **metadata**, not the string's shape: length cannot separate a 17-word title
  from a 17-word sentence. Warning-only. It answers for a **pinned** sidecar row too, which the reporter
  corrected us on mid-triage: those four modules have every row pinned, so a check living in the fetch
  loop would have fired on none of the 3,668 quotes it was written for.
- **RM119 — a citation sidecar can no longer contradict its own `studies.csv`.** `literature.csv`
  recorded `quotes_authored=0` beside 69 real quotes in four published modules, because it is
  merge-not-clobber and the pass ran before the quotes existed. `_check_quote_counter_is_current` warns
  naming both numbers. And **`Literature.quotes_unchecked`**: `_literature_block`'s per-row null guard
  is right and does not survive aggregation — `sum()` over all-null rows is `0`, so the block published
  exactly the sentence its own docstring calls the most misleading thing it could say.
- **RM120 — `StudyRow.curator`.** Who located this row's quote: the field `VariantRow` has always had,
  on the table where the attestation lives. Free text resolvable against `authorship`, never a
  `machine_located` boolean. `ATTESTATION_BEARING` is unchanged. **Wiring it found that
  `@three-touch-points` undercounts for `_write_studies_csv`** — there is a fourth site, the row dict,
  where a missing key makes `DictWriter` write the header with an empty cell on every row: the reversed
  spec re-validates and the value is gone, and only the digest fixed-point catches it.
- **S50 — `--no-study-facts` is permanent for the rows it writes.** Documentation only, no `RMn`: the
  merge rule is correct and the prose read as a per-run trade. ENRICHER.md and the CLI help now say the
  linked columns are lost for those rows and that deleting `gwas_effects.csv` is the recovery.

Suite 2784 → 2833.

## 2026-08-20 — three schema facts a downstream surface could not generate (S47–S49, RM112–RM114)

**Shipped in 0.6.5**, cut and tagged on 2026-08-20 with the batch above. Three items from
`just-module-creator` in one sitting, all from the same work: their
MCP tools had answers that **restated** a schema fact instead of generating it, and two of the three had
no public symbol to generate from. Additive only — new public names beside the old, nothing removed or
retyped, no authored column moved, so `content_signature` is untouched everywhere.

- **RM112 — `hints.DERIVED_TABLE_MODELS` + `hints.derived_model_for(csv)`.** `draft.model_for` is
  authored-only by design, so a tool asked what is in `frequencies.csv` or `resolution.csv` got *"not an
  authored table of this format"* — true and useless — and the only complete map was private
  `compiler._FACT_TABLES`. All four substitutes were measured and fail; notably
  `ARTIFACT_PARQUETS - LEAD_PARQUETS` is **nine** names against seven fact tables. Derived from
  `_FACT_TABLES`, never restated.
- **RM113 — `hints.key_fields(csv)` → `TableKey(columns, rule, stamped)`, and `describe_table` now
  carries a `key` block its docstring has promised since 0.5.** The reporter's hand-kept key string had
  gone stale, naming `modifier_cn`, deprecated at 0.6. The obvious repair is a **wrong answer**:
  filtering `_KEY_FIELDS` through `model_fields` silently drops `CopyNumberRow`'s property-valued
  modifier axis. Structurally, eight models now declare `_KEY_FIELDS` and both dupe-key dicts derive
  from it, so `key_fields` and `natural_key` cannot drift.
- **RM114 — `scaffold.companions_for(kinds)`.** The `studies.csv -> variants.csv` pull was
  unconditional, so scaffolding a binning module invited an empty `variants.csv` into a spec that
  compiles strict-green without one. RM47 is what made it wrong; the constant's own comment already said
  *alone*.

**The shape worth carrying.** All three are one defect at three sites: a fact stated twice, once where it
is enforced and once where it is described, with only the enforced copy under test. The durable half of
each is therefore a **derivation** rather than a fix — the published map reads `_FACT_TABLES`, the key
reads the model, the companion set reads the compiler's composition rule — because publishing a
hand-kept copy of a map in order to close a report about hand-kept maps is the defect wearing a public
name. Two guards found things the designs had not: `variant_key` is a stamped **field** on three models
and a **property** on `StudyRow`, and the first key guard failed on `studies.csv` correctly.

Suite 2779 → 2799, green throughout; `ruff` clean. **S50–S52 arrived during the pass and are
deliberately left `new`** — S50 is a documented doc-gap in the GWAS merge, S51 and S52 untriaged. An
empty verdict is honest; a hedged one is not.

## 2026-08-20 — §6.6 said a review pass reaches nothing downstream, and it had reached it for three releases (S46)

Documentation only; no code moved and no version needs cutting. `just-module-creator`, writing a
`module-revise` skill with [MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md) §6 as its source, measured §6.6's
central claim from outside and found all three halves of it false. Re-verified here first-hand against
the `just-dna-registry` tree at **0.18.3**, not taken from their report or from that registry's replies:

- **`verification.json` is recognized** (`RECOGNIZED_SPEC_FILES`, their 0.16.0), so `revalidate` and
  `upgrade` carry it forward instead of dropping it; it is in `DERIVED_FILES`/`manifest.derived` (0.17),
  so `download(include_inputs=True, layout="split")` returns it at `derived/verification.json`; and
  `manifest.verification` is **projected onto their module-detail response**, with `closed` re-bound by
  their own compile against the authored bytes. Still out of `SIGNATURE_INPUTS` — the property that made
  recognising an unread file safe, unchanged.
- **The pre-flight agrees with the gate** as of their 0.16.0, via a new `published_elsewhere` the verdict
  quantifies over. Nobody on this side had re-read the reply, so §6.6 and § stages 7–8 both still
  described a publisher being refused its own legal review publish.
- **`authorship` reaching no projected field is policy, not an omission** — answered, not repaired.

So §6.6's conclusion — that a re-close *"costs a version number for a record nothing downstream can
see"* — had inverted, and the section is rewritten: the four findings are stated **separately with the
release that moved each**, which is the reporter's suggested shape, adopted because the composite
sentence went stale as a unit and a reader could not tell which third was still true. The new advice is
that registry's own answer to the question RM86 had left open: **a `reviews` row by default; an
`authorship` entry when the record must travel inside the module or be signed; both when both matter** —
so *visible downstream* deliberately does not become *bump a version for every review*.

**[RM86](ROADMAP_0_7.md#rm86--a-review-pass-is-legal-at-the-gate-refused-by-the-pre-flight-and-invisible-once-published)
is closed** in place, with per-finding dispositions; its own status line ("waits on their answer to S12")
was stale too, since that answer arrived in their 0.16.0. [RM_TOC.md](RM_TOC.md) carries the same, and
the entry's `../just-dna-marketplace` pointer now names `just-dna-registry` — the former is a symlink to
the latter. S46 is archived.

**The lesson, which is why this entry is long for a doc fix:** every clause of that sentence was verified
in another repository's tree the day it was written, and none of it was re-checked afterwards. Prose
citing another repo's code has no test behind it and no expiry, so it decays silently while reading as
evidence. §6.6 now dates each finding to a release, which is the cheapest thing that makes the decay
visible to the next reader.

## 2026-08-20 — a downstream reference surface, validated against the code, and eight findings filed (RM104–RM111)

**No version moves.** Format and compiler stay at **0.6.1**, enricher at **0.6.4**. This is an audit
round: nothing shipped, eight things were filed, and one downstream repository's documentation was
corrected in place.

**What was audited.** `just-module-creator`'s `skills/module-tables/references/` holds 24 files, one
per table kind, written against this repo's 0.6.1/0.6.4 by another agent. All 24 were checked three
ways — the reference, against our `docs/`, against **the code as arbiter**. The calibration result is
worth recording because it inverts the expected yield: roughly 250 `file:line` citations were
spot-checked across twelve reports and **near-zero named the wrong symbol**. Their line numbers have
drifted with the tree; their reasoning held. So most of what the audit found is wrong in **our**
documents, not in theirs.

**Two of our own findings were themselves wrong, and the reason generalises.** Two reports accused the
reference of fabricating `describe_table`'s return value and of calling a `table_requirements` symbol
that does not exist. Both accusations are false: those are the **plugin's own MCP tools**, which really
do return `redundancy_bearing`/`attestation_bearing` and really do expose `table_requirements`. The
agents checked `just_dna_compiler.hints` — a different surface with the same names. **When a claim
names a tool, establish which surface owns that name before calling it a misread**; the wrapper and the
library disagree deliberately, and only the *count* was actually wrong (thirteen authorable kinds, not
twelve).

**The downstream files now carry two markers**, and they are a convention worth knowing if you read
them: 🚧 **ROADWORKS** for a surface that is broken or unfinished, always with a **Guard** naming what
to do instead, and ⚠️ **CHECK** for a claim whose current state is not what the surrounding text
implies. 25 and 10 of them respectively, plus a per-file audit banner and about ten unmarked in-place
corrections. That repository is not ours to commit; the edits are left in its working tree.

**Eight code findings, filed as RM104–RM111 and none of them fixed.** Three are one-line patches with a
test each — `enrich_gene_metrics` raising `UnboundLocalError` on the ordinary idempotent re-run
(**RM104**, and it defeats the `GeneMetricsEnrichmentError` contract RM101 was built for), the `faf95`
arithmetic warning being **published twice** into `manifest.compilation.warnings` (**RM106**, the same
shape as the shipped RM94, three lines from a dedup filter whose comment names the hazard), and the
gene-metrics fetch-suppression key not being derived from its merge key, so an honest `source=manual`
override duplicates instead of overriding (**RM109**). Two more are patches with a wider blast radius:
`logo.jpeg` compiles and is attested but never publishes, because the publisher allowlist is the one
place still spelling logo names by hand (**RM105**), and a duplicate `(source, layer)` row compiles
green under `--strict` because `SourceRow` is in the *drafter's* dupe map and not the *compiler's*
(**RM107**) — in the one file the compile gate keys on. Two need design before code: a ClinGen
re-curation appends a second row with nothing marking the superseded one, so
`manifest.gene_validity.classifications` can publish `["definitive", "refuted"]` with no currency
notion (**RM108** — S45's shape, minus the signal S45 had), and `constraint_flags` carries two
encodings from two producers, where normalizing the snapshot leg's literal `"[]"` would move
`gene_metrics.signature` for every module already holding those rows (**RM110**). The last is
documentation shipped as code: three strings, two of them `Field(description=…)`, assert a registry
override of `license` that the registry's publish path never performs (**RM111**).

**Three recurring shapes came out of it, and they are the part worth carrying forward.** A check is
only as wide as the table it reads, and our documents name checks without naming that scope — six
agents found an instance independently, from `REDUNDANCY_BEARING` being keyed on a bare column name
(so it advertises checkers that cannot run on the model in front of you) to `manifest.stats.genes`
being `variants.csv`-only, so a gene-keyed table-only module publishes `gene_count: 0`. A counted
claim in prose rots the same way a hand-kept list does — "seven fact signatures" (eight), "six derived
sidecars" (seven), "four causes" (five) — and the repair is an **equality over a walked set**, never a
corrected integer. And an *enforcement* claim needs its surface named: the `unresolved` bin sentinel is
called mandatory in three places, and the compile path refuses a **second** one while refusing zero
nowhere at all, with the presence half living on the authoring hints and scoped to the whole table
where the compile rule is per bin group.

## 2026-08-19 — 0.6.4: "needs a re-draft" was an incomplete instruction (S45)

**`just-dna-enricher` 0.6.4**; format and compiler stay at **0.6.1**. One fix, three tests, suite
2776 → 2779. It exists because a consumer measured the half the 0.6.3 entry explicitly did not claim
to have measured, and the answer was worse than assumed.

**Two drafting fixes shipped in 0.6.3 and they remediate differently, which is the frame worth
carrying: S44 *skipped* rows, S41 *wrote them under an identity that has since moved*.** Only the
second leaves anything behind. Re-measured here: a stale ClinPGx module of 18,691 rows re-drafts to
**18,895 with 0 missing and 0 stale**, exactly a fresh draft — so S44 needs no caveat, while S41 does.
A reader meeting both in one set of release notes will reasonably assume otherwise.

**A re-draft repairs S41's omission and cannot retract S41's collapse.** Drafting appends and never
mutates, so re-running the fixed drafter over an existing spec adds the coordinate-keyed rows
**beside** the collapsed rsid-only row instead of replacing it. The module then carries both the
replacement rows and the row they replace — and the stale one is the row bearing the mislabelled
expansion, since resolution pairs its authored genotype with every locus its rsID resolves to. So the
remediation named in the 0.6.3 entry leaves a module worse-formed than either the old one or a fresh
one.

Reproduced independently on `MLH1` at `min_review_stars=2`, every number matching the report: a stale
module of 996 rows re-drafts to **1,061** against a fresh draft's **1,030** — `added=65,
already_present=965`, **0 identities missing** and **31 present that a fresh draft does not contain**.

**And they were undetectable from inside the module.** `_row_cells` writes no `rsid` on a
coordinate-identity row, so the obvious predicate — *an rsid-only row whose rsID also appears on a
coordinate row* — finds **0 of 31**. The pass itself can see it, because it holds the set of rsIDs it
is deliberately writing by coordinate this run; an rsid-only row carrying one of those is a row no
current draft would produce. `_superseded_rsid_rows` now names them after the append, aggregated
through the house `examples` helper.

**Reported, never removed**, which is the reporter's own preference and the right one: a drafted row
is authored material by the time a re-draft runs, a human may have curated its `genotype`, `state` and
`conclusion`, and deleting curated work to repair a drafting defect is a trade only the author can
make. The cleaner remediation is still a fresh directory reconciled against the old module — the
notice is for the author who followed the shorter instruction, which is the one we wrote.

## 2026-08-19 — 0.6.3: a drafter that silently dropped ClinVar records, and three more from one audit (S41–S44)

**`just-dna-enricher` 0.6.3**; `just-dna-format` and `just-dna-compiler` stay at **0.6.1** — a partial
cut, since no code outside the enricher moved. Suite 2761 → 2776, `ruff` clean. Everything here came
from one just-dna-lite audit of ten `v1_port` modules, plus S39 from just-module-creator carried over
from the previous pass.

**The serious one: `multi_allelic_rsids` keyed the site on `ref`, so an ordinary ClinVar dup/del pair
collapsed onto one row and the second record was dropped (S41).** An rsID takes coordinate identity
when it names more than one allele *here* — except the predicate grouped by
`(rsid, chrom, start, ref)` and fired on more than one alt inside that group, which is not what its own
docstring claimed. A mirror pair (`A>AT` beside `ATT>A` at one position, the same event written from
either side) is two groups of one alt each, so the rsID was never flagged, both records reduced to the
same rsid-only identity, and `append_partial_rows` dropped the second as `already_present` — silently,
because dedup is the normal case and nothing distinguishes it from a re-draft.

Re-measured here on the `2026-06-27` snapshot over BRCA1/BRCA2/ATM/MLH1/MSH2 rather than quoted from
the report: **942 rsIDs flagged before, 1,589 after**, and the 647 newly flagged are exactly the 647
identities that were collapsing. **725 records recovered, 0 made unkeyable, and 187 of those collapses
had been dropping the better-reviewed record** — `select_by_gene` orders by `ref` before
`review_stars DESC`, so which of a pair survived was decided by allele spelling rather than by
evidence. The event key is now the whole `(chrom, start, ref, alt)`, which also catches one rsID at two
distinct positions; distinctness is over the allele event and not over records, so a re-submission
under a second `variation_id` still does not flag. Six tests, all run against the unfixed predicate and
watched to fail, the real-snapshot one at exactly 725. **Modules published before this need a
re-draft** — no fix here reaches an artifact already built.

**The ClinPGx drafter's genotype gate was narrower than the schema it writes into (S44).**
`_authored_genotype` took only `CC`, on the argument that the general case needs the resolved ref/alt
to disambiguate — true of an unseparated cell, false of the two shapes ClinPGx publishes beside it,
since `validate_allele` accepts any `^[ACGT]+$` allele. `CTT/CTT` is *already* separated by the source,
and declining it cost **CFTR F508del**: those annotations carry a `del`-spelled genotype and a
pure-nucleotide one under one `annotation_id`, so skipping the annotation discarded the writable row
with it. A bare `A`/`CCCCCCC` is the haploid form the grammar already holds and how ClinPGx spells
mtDNA — declining it cost every **MT-RNR1** annotation, 32 rows at evidence level 1A, a CPIC guideline.
**158 rows recovered**, 36 at 1A. `del/del` and `C/del` stay skipped, unchanged and deliberate: ClinPGx
publishes no length and the compiler drops a lengthless symbolic allele. The general rule is a test now
rather than a comment — *every spelling this pass declines must be one `PharmVariantRow` would also
refuse* — walked over the accepted set, with the converse still allowed.

**A share-alike source was recording its licence without pinning it (S44).** `SourceTerms.row` has
taken `license_text=` all along; `clinpgx_draft` passed only `declared_use` and `dataset`, so
`license_sha256` was null while `clinpgx_build` was extracting `LICENSE.txt` into the snapshot for
exactly this purpose. Hashed from the file rather than copied from `release.json`'s stated hash — the
file is what the module claims, so a truncated copy cannot pin to a value it lacks. Absent stays `None`
and warns. `merge_sources_file` is never-clobber, so a module drafted earlier keeps its null until the
sidecar is deleted and re-drafted.

**Two documentation defects with no code half, and one filed.** `likely_pathogenic` and `likely_benign`
turned out to be **unwritable, not merely unwritten** (S43): parquet columns with no authored field
behind them, a literal `False` since the initial 0.1.0 commit, read by nothing. Not filled and not
removed — both are breaking moves on a published column — but documented as permanently unwritten, in
SCHEMAS.md's tri-state table as its one acknowledged exception. Probing that corrected a claim we were
about to make wrongly: `manifest.stats.pathogenic_count` counts **authored `variants.csv` rows**, not
parquet rows, which diverge wherever resolution expanded one row onto several loci. And a digitless
`module.version` coerces to `0.0.0` and reaches `manifest.identity.version` (S42) — filed as
**RM103** rather than fixed, because refusing it is a new refusal and that sizes as a minor, the
RM50/RM48 class. Both entry points already warn naming the authored string, so the silence is the
model's alone.

## 2026-08-18 — an off-switch that switched nothing, and an upgrade note silent on a relaxation (S39, S40)

**One enricher fix, three documentation fixes, one new test, one roadmap item.** Nothing is cut:
`just-dna-enricher` stays at **0.6.2** in `pyproject.toml`, and the fix below will carry **0.6.3**
whenever the maintainer cuts it. Suite 2761 → 2762, green throughout.

**`load_dotenv_file=False` reached none of the six cache resolvers (S39).** The parameter has existed
since the resolvers were generalized, is named in six signatures, and did nothing at all: each
`resolve_*_reference` passes `default_*_cache_dir()` as an *argument*, and that helper went through a
`_cache_dir` whose `load_env()` was unconditional — so the `.env` was loaded before the resolver had
looked at its own flag. Probed rather than read, with a marker variable in a `.env` and a controlled
cwd: `load_dotenv_file=False` left it in `os.environ` for cpic, ensembl and clinvar alike. The flag is
now threaded through `_cache_dir` and the six `default_*_cache_dir` helpers rather than the load being
removed — the unconditional load is itself the 0.5.2 repair behind three "the cache is right there"
reports, and the `True` path is unchanged. `test_locations.py` runs each resolver in a subprocess and
pins both directions plus the pre-fix arrangement; a twelfth test walks both families asserting each
member takes the parameter, so a seventh snapshot cannot quietly reopen it.

This is the **second** knob in two days whose disabling value did not disable — after the watcher's
`${BRANCH:-main}`, where `BRANCH=` restored `main` — so it is now a rule with a tag:
`@off-switch-needs-a-probe`. Run the disabling value; a test that passes the enabling value and a test
that passes nothing are the same path.

**What that fix does not reach is [RM102](ROADMAP_HISTORY.md#rm102--the-enricher-loads-a-env-into-osenviron-from-library-paths),
and S39's reporter hit the default path.** The enricher loads a whole `.env` into `os.environ` from
*library* code, so asking where the ClinVar cache is can hand a process credentials for sources it
never named — and `override=False` skips a variable that is **present**, which means *deleting* one is
exactly what lets the file supply it. Their test isolation was undone that way. Filed rather than
fixed: a default flip is silent for every caller who never passed the parameter (S14's shape, so an
actionable deprecation has to come first), the allowlist variant makes us a filter over somebody
else's file, and four credential paths carry no flag at all by `@credential-where-read`. ENRICHER.md
now documents the mutation, the sharp edge, and both halves.

**INTEGRATION_0_6.md was silent on the one check that *stopped* refusing (S40).** RM47 relaxed
`StudyRow.REQUIRED_ANY_OF` to `()`, which § 1 never mentioned while naming both tightenings — the
table row *"Fields removed, retyped, or promoted to required | none"* is literally true and still left
a consumer's negative test failing with nothing to anticipate it. § 1 gains the symmetric table row
and a subsection that leads with the consequence rather than the validator: `StudyRow.variant_key` can
now be `None`, and a null join key in polars is a **silently smaller result**, not an error. A
relaxation is invisible to a corpus run and visible to every consumer holding a negative test, which
is the argument for saying more about it rather than less. No code half underneath it —
`_cross_validate_studies` handles the subject-less row deliberately.

**And it pointed at a fixture that does not exist.** § 3 told just-dna-lite that a same-`ref`
expansion "is instantiated in `reference_examples/shox_par1/`", offered as the evidence that their
`ref`-spelling mitigation is insufficient; the committed example is 10 rows, 10 distinct rsIDs, all on
chrX, `expanded_keys=0`. The sentence now says so and names both routes to build one, including that
the VRS check refuses a copied `vrs_id` and prints the recomputed pair — the detail that makes it ten
minutes rather than an afternoon. **Building it found the gap under the report:** the claim had no
instance anywhere in this repository, tests included, because the corpus's only other expansion
(`pathogenic_clinvar`'s `rs1554917888`, `T>TA` beside `TA>T`) differs in `ref` — so every existing
`locus_count` assertion would have survived an expansion that deduped on `(chrom, start, ref)`.
`test_two_loci_sharing_a_ref_still_count_as_two` builds the twin from the example's own row through
`par_partner` and asserts both halves against each other. Third item, same document: § 1's *"nothing
you have breaks"* now carries the one exception, the private `_OUTPUT_FILES` made public as
`ARTIFACT_PARQUETS`.

**A consumer note from just-dna-lite is recorded below**, dated the same day, in the convention this
file already carries for their 0.5 adoption. It is their writing and is committed unedited.

## 2026-08-18 — the 0.6.2 upgrade note had a fourth shape, and it was the silent one (S38)

**No package is cut.** `just-dna-enricher` stays at **0.6.2** and the code is unchanged — S38 is
explicit that the RM101 subclass design is right, and it is exactly what makes the reported shape
possible. What moves is two documents, one guard test, and a dated correction on S37's reply.

**The defect: "catch both" describes two handlers that behave oppositely.** § 8's migration table said
`except (FrequencyEnrichmentError, GnomadError)` "keeps working, unchanged", written as though catching
both could only mean one tuple. just-dna-registry had them as two separate arms — the two meant
different things to them, a plain warning against an `unreachable` field — with the parent first. On
0.6.2 `enrich_frequencies` raises `FrequencyUnavailable`, which **is a** `FrequencyEnrichmentError`, so
the first arm wins and the outage arm is dead code. Three of their four handlers. **It fails silently**:
nothing raises, nothing 500s, and their endpoint reported a clean check while gnomAD was down — the
failure RM101 exists to end, reintroduced by the fix for it, in a consumer who had followed our advice.
They caught it only because their guards assert the *field* rather than the status code.

**Fixed where it was read and where it is maintained.**
[INTEGRATION_0_6 § 8](INTEGRATION_0_6.md#8-what-061-got-wrong-and-062-fixed) gains the fourth row in
the reporter's own words, plus a paragraph saying to read rows one and four together, since they differ
only in punctuation. [ENRICHER § Exception contract](ENRICHER.md) gains the same warning, because a
migration note stops being read while the reference does not. The 0.6.1 workaround row now says **in
one tuple**. § 8 also now points at `AcmgListUnavailable.skip`, which separates `unreachable` from
`no_reference` — the reporter had been collapsing the two and sending operators to check a healthy
network, and fixed it themselves once they read the field.

**The guard is structural, because the defect is invisible except in the shape of the code.**
`enricher/tests/test_shadowed_handlers.py` parses all three packages and fails on any `except` arm an
earlier arm in the same `try` already catches. Our tree is clean — and since a zero is worth nothing
unless the walk can fail, a second test runs it over the reporter's snippet and asserts exactly one
finding. A parent and child in **one tuple** is deliberately not a finding: that is redundant rather
than dead, and a guard that cries wolf on it gets deleted. Adopted from the guard the reporter built
for themselves.

**S37's reply carries a dated correction rather than an edit.** The sentence *"your adapters catch the
client's type alongside the pass's, and that keeps working unchanged"* was ours and was too broad. It
stands, with the correction beneath it: the reply is what a consumer was told, and rewriting it would
hide that the advice was incomplete. The fingerprint is unmoved — corrections sit above the marker,
which is what the reply span excludes.

## 2026-08-18 — the outward half of the gist sync, and the off-switch that was not one

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

## 2026-08-18 — consumer note: `just-dna-lite` adopts format 0.6.1 / compiler 0.6.1 / enricher 0.6.2

No change here; recorded so the other consumers are not surprised. Done on a branch, against
`INTEGRATION_0_6.md` § 3's just-dna-lite list, with registry `0.17.0` bumped in the same commit range
(its floor is `just-dna-format>=0.6.1`, and `version.contract_compatible` compares installed *format*
versions, so the two pins cannot move apart). Field notes are **S40**.

- **`locus_count > 1` replaced the `ref`-spelling guard as the expansion predicate** (RM87), which is
  the S33 follow-through. The old guard is kept beside it as the pre-0.6 fallback, because every module
  we have published predates the column. Both are needed and the gap between them was measured, not
  assumed: on a compiled same-`ref` fixture (`shox_par1` with its `resolution.csv` twinned onto chrY),
  the grouped `ref` test finds one spelling at each of the two positions and withholds nothing, while
  `locus_count=2` withholds both. Restoration is where this matters — an unobserved hom-ref row at a
  locus that is one of N is a fabricated result, not an ambiguous one.
- **The report's genotype split now calls `alleles.split_genotype`** (S30's public leaf), and ours was
  wrong in a way the corpus cannot show: it split on `/` only, so a phased `"A|G"` came back as the
  single allele `["A|G"]` and the row rendered with **no zygosity**. Nothing we ship authors a phased
  genotype, so no fixture drawn from real modules could have caught it. Both our splitters — the
  Python one and the engine's vectorized polars twin, which cannot call the leaf per row — are now
  pinned against it over a cell list that deliberately includes `A|G` and `G|A`.
- **Discovery decides a module's shape from `manifest.artifact.files`** (§ 2.8's ask), falling back to
  probing where there is no manifest, which is every module on HuggingFace today. `None` rather than an
  empty set is what makes that safe to adopt now. Demonstrated on a directory holding an unattested
  `weights.parquet` beside an attested `pharm_variants.parquet`: probing answers `weights` and the
  attested list answers `pharm_variants`, so the fossil really does decide the module's *kind*.
- **Two hand-kept lists were deleted rather than updated.** The HuggingFace publisher's allowlist named
  six side tables where 0.6 has nine, so a module carrying any of the three new fact tables would have
  published a manifest attesting parquets the upload never sent — the same defect S35 found upstream,
  one repo over. It now derives from `ARTIFACT_PARQUETS`. Separately, two copies of "which authored CSV
  leads a module" named four of the ten families, so a `heteroplasmy`- or `copynumbers`-led module
  counted **zero** authored rows and was always routed to the enrichment half of `/check`.
- **The licence sidecar is cleared through `layout`, not by name.** Our drafters' stale-file sweep
  unlinked `sources.csv` literally. That is fine at the spec root and wrong under `derived/`: the sweep
  cannot reach `derived/sources.csv`, so `sidecar_write_path` finds it as the existing copy and merges
  into the **deprecated** spelling, which the module then keeps for good. Measured both ways on the
  pre-fix tree (`['derived/sources.csv']` before, `['licensing.csv']` after). `sidecar_candidates` made
  it three lines.
- **Nothing changed for § 8.** We hold no `except` around any enricher pass, so there was no handler to
  reorder and nothing that had been silently dead. The 0.6.2 floor is taken for the registry's sake and
  for the unavailability subclasses if we ever want them.
- **Not done, deliberately:** the ten modules in `data/interim/v1_port/` are **not** rebuilt or
  republished. That is the maintainer's call (`docs/MODULE_RELEASE_0_5.md`), and leaving them as 0.5
  artifacts keeps the mixed-era read paths — `_annotations_keying`'s three generations, the pre-0.6
  `ref` guard, `UNJOINABLE_PHRASE` — under live test rather than under test only by fixture.

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
