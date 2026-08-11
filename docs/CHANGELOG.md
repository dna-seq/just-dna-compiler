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
content is [RM38](ROADMAP.md#rm38--a-cache-for-every-gated-source-the-hosted-enricher) — a cache for the
licence-gated sources, so a hosted enricher stops fetching them live per request. This does **not**
reopen the paragraph above: that one is about labelling a batch inside an *unpublished* release, which
0.5.1 is not — 0.5.0 shipped, so 0.5.1 is a real next number rather than a name for work in progress.
**0.5.2 follows the same rule** and stretches it by one package: its ClinVar-drafting, query-shape and
cache-location work is enricher-only, and the one compiler change (a warning when
`resolve_with_ensembl=False` discards an injected `resolution.csv`) writes no parquet and moves no
signature, so `just-dna-compiler` took the patch alongside while `just-dna-format` stayed at 0.5.0.

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

**The second half is filed, not built — [RM49](ROADMAP.md#rm49--a-spec-directory-is-flat-so-a-legible-derived-layout-is-one-the-compiler-refuses).**
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

## 2026-08-11 (later still) — S24: the gene a row names, against the chromosome its variant sits on

`just-dna-enricher`. `variants.csv` carries a `gene` column and nothing compared it to anything.
`identifiers.py` asked HGNC whether a symbol was *approved*, which is a different question — `FTO` is
approved whatever variant sits beside it — so a row pairing a real gene with a variant on another
chromosome passed every check, because both halves were individually true and only the relationship was
false. Four of a reporter's seven rows were exactly that: real symbols beside invented rs numbers,
which resolve anyway because dbSNP is dense enough that almost any seven-digit number hits something.
Machine-written sources are now a real authoring input, and this is the shape they fail in.

`check_identifiers` reports `GeneLocusConflict` per row and repairs nothing. **Chromosome granularity
only, and the stronger version is refused in the code with the reporter's own argument**: `rs1421085`
sits in an FTO intron and acts on *IRX3*/*IRX5* megabases away, so a row may legitimately name any of
the three, and an interval check would fire on correct rows until someone switched it off. A test pins
that the FTO row stays silent with the variant nowhere near the gene body.

Three details. The join is against HGNC's **cytoband** (`16q12.2` → `16`, `mitochondria` → `MT`), and
anything unparsed yields `None` rather than a guess, since a guess becomes a false accusation about a
row. For an rsID-only row the chromosome comes from an injected `resolution.csv` beside the spec — the
table the compiler already consumes — and nothing is fetched, because a currency check should not
depend on a resolver. A **pseudoautosomal** gene is exempt: `XG` straddles the PAR1 boundary, so X/Y
there is a spelling, not a contradiction (RM32). `gene_loci_not_checked` carries the reason when the
comparison could not run, for the reason `clin_sig_not_checked` exists, and the CLI prints it.

## 2026-08-11 (later still) — S21/S23: the authoring surface could not describe the one table it tells you to write

Two fixes and one roadmap item, all from a consumer's test run over the authoring surface, all folded
into 0.5.4. Both fixes are about `sources.csv`, which is the only fact sidecar a **human** writes — the
other three are produced by an enricher pass — and the only table the compile licence gate reads.

**`authoring_reference()` did not describe it at all (S21, format + compiler).** The root was one level
below the report: `SourceRow.layer` and `.declared_use` run closed-vocabulary validators while carrying
no `vocabulary=` marker, and the guard that exists for exactly that
(`test_every_enforced_vocabulary_field_declares_its_options`, which discovers enforcement by behaviour
rather than from a list) never saw them, because it iterates `_ALL_MODELS` and `SourceRow` was not in
it. One omission hid the other. Both markers now sit on the fields, the model is in the registry, and
the guard covers it — demonstrated by stripping the markers and watching it name both fields, not
asserted. An author left to reconstruct this table from a filename has to guess that
`share_alike`/`commercial_use`/`redistribution` are three orthogonal axes where `None` means unknown
rather than false, which is not a guessable shape; the reporter got it right only by reading
`SourceRow.model_fields`, i.e. reading our source to learn our schema.

The same probe found the compiler half, which nobody had filed: `draft.blank_template("sources.csv")`
answered *"is not an authored table of this format"*. False, and said by the surface an author reaches
for instead of the source. It is now in `DRAFTABLE`, with `(source, layer)` — the key
`licensing.merge_sources_csv` already merges on — as its natural key, so a draft and the enricher
cannot disagree about whether a row is already recorded.

**And the compiler warned about the row the schema instructs you to write (S23, compiler).**
`_source_checks` decides "no table used it" by reading the `source` **columns** of the generated
tables. `studies.csv` has none, by the same design that already exempts the annotation layer, so a
hand-declared `pubmed`/`europepmc` row could never be corroborated and was reported as unused —
while deleting it, and shipping with the literature provenance unrecorded, was silent. Compliance
warned, omission quiet, and an author following the warning ends up deleting the exact row the licence
gate exists to read. A `literature`-layer row is now uncorroborable rather than orphaned whenever the
module carries `studies.csv` rows. Narrow by construction: `frequency` still warns, because
`frequencies.csv` is machine-written *with* a `source` column, so a frequency declaration in a module
with no frequencies really is stale. Both directions pinned.

**Filed, not built: [RM48](ROADMAP.md#rm48--an-hg19-coordinate-has-no-supported-path-into-a-grch38-module-and-liftover-is-the-wrong-primitive) (S22, 0.6).**
An author curating from older literature has hg19 coordinates and the module must be GRCh38, and
nothing here converts. Filed as **rsID recovery** rather than liftover, on the reporter's own argument
against their request: with an rsID liftover is unnecessary and strictly worse (the rsID *produces* the
independent second value `resolution._verify` cross-examines), so liftover is only reachable where the
lifted coordinate becomes the row's sole identity with nothing to check it against — the hazard class
behind the 3,038-variant off-by-one. Not RM15, which changes the module's own build and every identity;
this is one-way and authoring-time, hence additive and 0.6 rather than 1.0.

## 2026-08-11 (later) — S20: an unreachable Ensembl is unchecked, never absent

`just-dna-enricher` only, folded into the same 0.5.4 cut. `EnsemblResolver.resolve_rsid` returned
`([], None)` both when Ensembl answered with no GRCh38 locus and when the request never completed, so a
failed lookup was reported as a **definite negative**: `loci: []` plus "live Ensembl has no GRCh38 locus
for it either", at `info`. A consumer checking which rsIDs in a machine-written document were real —
where that pair is exactly the fingerprint of a fabricated identifier — put two published variants
(`rs6567160`, a long-standing MC4R BMI locus, and `rs13010010`) in the fabricated pile, and caught it
only because five-of-seven succeeding looked more like flaky egress than a 30%-honest document.

Three outcomes now: loci, `[]` for an answered absence, `None` for could-not-ask. The unreachable case
is a **warning** — the caller has to decide whether to re-run — and a **4xx stays an answer**, since
Ensembl 400s on rsIDs it cannot resolve (`rs3216883`, merged per dbSNP); only a 5xx, a transport error
or a timeout is unchecked. An answered-empty carries its source, so `hint.checked` records
`ensembl-rest` when Ensembl was reached and said nothing — the report's own evidence was a *missing*
element in that set, which is unreadable in practice.

The artifact half was the worse one and no consumer could see it from `lookup_variant`: `enrich()`
wrote `ResolutionRow(status="not_found", source="ensembl")` for a request that failed, stating in the
injected table that Ensembl was asked and does not have the rsID. That row is no longer written — the
key stays `unresolved`, so `strict` still refuses and `best_effort` still warns, but nothing claims a
source said no, and `EnrichmentResult.unreachable_rsids` names them. The argument was already four
lines below in the same function, where the non-GRCh38 branch declines to write `not_found` for
precisely this reason; it was one branch away from the case that mattered. Generalize it: when a
function has two ways of returning nothing, check whether any caller renders them as one sentence.

Also here, found by the fix rather than reported:
`test_without_the_load_the_first_resolve_really_did_miss` asserted a resolve returns `None`, which is
only true on a machine with no ClinVar snapshot in the platform default — so it passed on a clean
checkout and failed for anyone who had run `cache pull`, the documented workflow. The probe now
redirects `XDG_CACHE_HOME` at an empty directory, making the miss a property of the arrangement rather
than of the developer's laptop. Same trap as the `.env` credentials already documented in CLAUDE.md.

## 2026-08-11 — 0.5.4: the consumer-suggestion backlog, answered — seven fixes, three roadmap items, and a diagnosis where there was a dead end

The first full run of the triage loop ([CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md)) over the
eleven unanswered entries in `CONSUMER_SUGGESTIONS.md`, plus `S18`, which a consumer filed while the pass
was running. All eighteen now carry a reply and have moved to
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), which indexes every one and where it
landed. Touches `just-dna-format` (two guards), `just-dna-compiler` (two checks plus a coordinate on a
report) and `just-dna-enricher` (a lock, and bibliography on a hint). No schema field, no parquet column,
no manifest field, and no signature moves. **Verified rather than assumed**, since two of the fixes are
in the format tier: all eleven reference examples were compiled under `HEAD` in a detached worktree and
under this tree, and all three identities — `artifact.digest`, `content_signature`,
`resolution_signature` — are identical for every one of them.

**Two of the eleven were already fixed and had simply never been answered** (S1, S2), and a third's
preferred fix had shipped in 0.5.2 from a different report (S14). That is the first lesson of running the
loop: `new` in the ledger means *no reply in the document*, never *no work done* — so establish what
shipped before designing anything. For S1 that turned an apparent feature request into one missing error
message.

**A misplaced or registry-owned column now says which it is, instead of "extra inputs are not
permitted".** Two guards, both layered on `extra="forbid"` exactly as `vocab.reject_reserved` already
was, and both keyed on the model's own fields so the tables they describe cannot be broken by the
description:

- **`normalize.reject_authority_keys`** on `ModuleInfo` (S1) — `namespace`/`owner`/`canonical_id` name
  themselves, say they are registry-stamped, and point at `strip_authority_keys` / `--strip-identity`.
  The per-key reasons had existed since 0.4.1 with `authoring_reference()` as their only reader, so an
  author who never injected the set still hit the generic message. It diagnoses and strips nothing: the
  inject-only rule is about *applying* one consumer's convention, and a message is not an application.
- **`vocab.reject_misplaced` / `MISPLACED_COLUMN_REASONS`** (S17) — a `source` column on a hand-authored
  fact table now explains that `source` is recorded on generated tables only and that a hand-read source
  is declared as a **row in `sources.csv`**. `FrequencyRow` and the other three keep their column.
  Deliberately not the reserved namespace: that set is for names no model has, and `source` is a real
  column in the wrong place — a different failure deserving a different sentence.

**`hints.inspect_rows` no longer mis-parses a ragged row in silence, and a finding names the line an
editor shows** (S18, reported with an HTT CAG fixture that reproduced verbatim). An unquoted comma in
`conclusion` shifted every later column, dropped the overflow, and produced `Input should be a valid
boolean` against `unresolved` — a cell whose authored value was `false`. The field-count mismatch is now
reported **before** the type error it explains (error for a surplus, which discards data; warning for a
shortfall, which only pads), and `Finding` carries **`line`** — 1-based, header-inclusive, the coordinate
`validate`/`compile` already print — beside `row`, which keeps its meaning and is now documented as a
0-based data-row index. A rename rather than a redefinition, because a consumer already adding 1 would
otherwise have started reporting line 4 for line 3 with no signal.

**One `PacingGate` is safe to share across threads** (S15). `wait()` read `last`, slept, then wrote it
with no lock, so two workers could both find the interval elapsed, both skip the sleep, and turn a
published 3/s budget into 6/s. The reporter's argument is what decides it: `LookupClients`' own docstring
tells callers to hold and reuse a client, so a server threading its blocking work arrives at a shared gate
by following our documentation, and an unstated single-threaded-only contract is not one worth keeping.
The lock covers the **bookkeeping, not the sleep** — each caller reserves the next slot and waits for it
alone, so N callers get N slots one interval apart without blocking each other. Demonstrated rather than
asserted: four threads at a barrier with a frozen clock must come out spaced by the interval, and the old
implementation yields gaps of `[6.0, 0.0, 0.0]`.

**Existence is not identity, so `lookup_citation` now says which paper it found** (S12). PMIDs are
densely allocated, so a recalled 8-digit number is usually a real record for a different article, and
`pmid_exists=True` could never catch a fabrication. `CitationHint` gains `title`/`journal`/`year`/
`first_author` from the same `esummary` response that answers existence — `literature.bibliographic()`,
public because two tiers read it — plus an `info` finding naming the paper, and **`hint citation --json`,
which did not exist** (`hint variant` had it). No title column on `LiteratureRow`: that table records what
was *checked*, not bibliography.

**A quote is an attestation, and that is a sharper refusal than a spent comparison** (S11).
`provenance_quote`/`provenance_regex` were missing from `hints.REDUNDANCY_BEARING` although
`_study_quote_found` compares both against the Europe PMC fulltext — the drift that map's docstring
predicts. Both registered, plus a fifth refusal reason, `attestation_bearing` (`hints.ATTESTATION_BEARING`):
filling `doi` from the registry that checks it makes a comparison *vacuous*, while extracting a passage
from a just-fetched fulltext states something **false**. ENRICHER.md now says the consequence nothing
stated — once a machine has retrieved the text, `quotes_found` demonstrates that the quote pairs with the
PMID, not that a human read the paper.

**Two checks that close silent-success paths.** `--no-resolve` names the size of what it discarded (S14:
`N row(s), covering K variant key(s)`) and says there is no flag for "do not reach the network" because
the compiler never does — verified branch by branch, including the deprecated `ensembl_cache` path, which
reads an injected local cache. And an unknown `.csv` within one small edit of a table name warns
(`_check_misspelled_tables`): S16 asked whether unknown files are tolerated — they are, now stated in
COMPILER.md and pinned by a digest comparison — and probing that found the one case where "ignored" is the
wrong answer, since `varaints.csv` drops every row in it from a green compile. Keyed on **near miss**, not
"any unknown csv", or it would undo the tolerance it sits beside.

**Documentation, where the docs were the defect.** SCHEMAS.md's hash table called `artifact_digest` *"the
version's immutable **content** identity"* — against Principle 4, which names it the *byte* identity — and
that conflation is the likely proximate cause of S7, where a registry spent an afternoon hunting a content
change that had not happened. Fixed, with the reading spelled out: a moved digest beside an unmoved
`content_signature` is a provenance-only change, `find-by-hash` should key on the signature, and
`just-dna-compiler signature` computes it without compiling. Also: the three-way field-ownership boundary
(S2), which `authoring_reference()` has generated since 0.4.1 with no prose anywhere.

**Filed rather than fixed, both 0.6.** [RM45](ROADMAP.md#rm45--the-manifest-is-rich-about-resolution-and-silent-about-verification-so-unchecked-and-clean-are-one-state-to-a-downloader)
(S8) — the manifest records what resolution *achieved* and nothing about which verification passes *ran*,
so a verified module and an unchecked one ship identical manifests. Additive and cheap, but a design round:
free-string check names and free-prose skip reasons are both unversioned interfaces, the enricher→compiler
seam has no per-*pass* channel, and the trust rule belongs on the fields. It does **not** subsume RM44,
and saying so unblocks that one-line integer.
[RM46](ROADMAP.md#rm46--a-literature-sources-terms-are-per-article-so-the-enricher-names-a-source-it-cannot-record)
(S10) — `enrich_literature` writes `source="pubmed"` and no terms constant exists, so every
literature-enriched module warns about a source the enricher introduced. A `PUBMED_TERMS` entry is the
wrong fix for the reporter's own reason: a literature licence is **per-article**, so one row would clear a
module carrying a CC-BY-NC quote, which is publisher text in the module's annotation layer.

**Three non-issues, each of which cost real probing** — S7 (three compiles plus a merge probe to show a
rebuild *cannot* move `fetched_at` unless the sidecar is deleted, since `merge_sources_csv` is
`setdefault`), S1 and S2. A bare "works as intended" would have been worthless and, for S7, wrong about
which fact mattered.

**The loop's own machinery got two fixes from being run.** `triage-state.sh` scoped a reply to its first
*paragraph*, so writing a multi-paragraph answer immediately reported the section `revised` — the same
self-firing failure the marker exclusion exists to prevent, by another route; a reply now ends at its
marker. And archiving is a tool (`.claude/triage-archive.sh`) rather than a careful copy-paste, because
the property that matters — the prose moves byte-for-byte — is verifiable: every section's fingerprint is
compared before and after and the write is refused if one changed.

### S19, filed after the batch above was written — a binning table had nowhere to record its evidence

The watcher picked it up the same day, and it lands in the same unpublished 0.5.4 cut rather than
inventing a number for a batch. **Reproduced on this tree's own reference example**, which is what makes
it worth the entry: `reference_examples/htt_repeat_expansion` compiles green under `--strict` asserting
where Huntington disease becomes fully penetrant — 26/27, 35/36, 39/40 — with no citation anywhere, and
its README even said *"a module making a novel claim should carry its evidence"*, which is advice the
schema gave the author no way to take. Grounding is mandatory exactly where citations usually arrive
already attached (a ClinVar-drafted `variants.csv` requires `studies.csv`) and absent where a human made
the judgement, because `StudyRow` names a variant and a bin is keyed `(gene, repeat_unit)`.

**Probing narrowed it in both directions, and both corrections matter.** `heteroplasmy.csv` is *not*
affected as reported — it has carried optional `rsid`/`chrom`/`start`/`ref`/`alts` since 0.5.1, so a
study row on the same identity points at it exactly, which `reference_examples/mt_heteroplasmy` already
does. And `studies.csv` is **not rejected** in a variants-free module: it loads, validates and
materializes `studies.parquet`, so an author can cite the literature today — the row simply has to claim
a variant identity the bin does not have, which grounds the module and not the bound.

**Shipped: the reporter's option 2, a warning, plus the documentation their option 1 asked for.**
`compiler._check_binning_grounding` fires when a binning table states thresholds and the module records
no study rows at all, in **both** modes (an uncited module still reproduces exactly, so `strict` is the
wrong axis — P5), de-duplicated across `validate_spec` and `compile_module` the way the ploidy and
joinability checks are. The message splits on whether the rows *could* be pointed at, and the split is
derived from the model — `variant_key` is `None` only when a row names no variant — never from the table
name: the heteroplasmy shape gets a remedy ("fill those columns"), the gene-keyed shape gets the honest
statement that no study row can name one of these bins. The binning kind set is derived from
`MeasureBinRow` for the same reason `_POSITIONAL_TABLE_KINDS` is derived from `chrom`/`start`.

**One comment was load-bearing and false.** The exemption in `validate_spec` was justified as "the 0.4
tables carry their own evidence (e.g. `evidence_level`)" — true of two of the nine kinds. `DiplotypeRow`
and `PharmVariantRow` have it; `PgsRow` carries a catalog accession, which is a provenance and not a
citation; the four binning kinds and `HaplotypeRow`/`AlleleFunctionRow` carry nothing of the sort. The
real reason is that for a gene-keyed table the requirement would be *unsatisfiable* rather than merely
unmet, which is a different thing and is now what the comment says.

**Filed as [RM47](ROADMAP.md#rm47--a-bin-boundary-is-the-most-interpretive-claim-in-the-format-and-the-only-one-with-nowhere-to-cite) for 0.6**, with the four candidate repairs and why none is a one-liner — the
short version is that each costs either a duplicated column set (`pmid` on `MeasureBinRow` drags
`studies.csv`'s provenance columns along, and lands a PMID the literature pass does not read) or a
duplicated key (`subject_key` is the packed tuple the binning tables explicitly reject; a
`bin_evidence.csv` joins on floats that silently orphan when a bound is re-authored). Docs updated in
`SCHEMAS.md` (where grounding goes and where it cannot), `COMPILER.md` (listed apart from the inescapable
blind spots, because this one is a schema limit rather than a limit of the tier) and the HTT README,
whose thresholds stay uncited on purpose so the example keeps showing the gap. Eight new tests; the suite
is 1410 → 1418 and every reference example still compiles to the same three identities.

## 2026-08-11 — `just-dna-compiler` + `just-dna-enricher` 0.5.3: say what is positionally joinable

S9 from `just-dna-lite`: the 0.4 table families are materialized verbatim, so an rsid-authored PGx
module compiles clean, validates, publishes — and every row has a null `chrom`/`start`, which joins to
no VCF. Reproduced on this tree's own `reference_examples/pgx_slco1b1_simvastatin/` (9 rows, all three
identity columns null, **zero warnings**) while the `resolution.csv` beside the spec resolves
`rs4149056` to `12:21178615 T>A,C`. Digest-neutral, verified: all eleven reference examples recompile
byte-identical against `HEAD`.

**The reporter's preferred fix is not merely digest-moving — it breaks Principle 7**, which is the
finding worth keeping. Materializing the coordinate into the parquet and running compile → reverse →
compile moves `content_signature` (`sha256:8173dab7…` → `sha256:fb91ffa2…`), because `reverse_module`
rebuilds the CSV from the parquet and a filled coordinate comes back as an *authored* one. That is
exactly what `VariantRow.authored_ident` exists to prevent, and no 0.4-family model has an equivalent;
adding one is a new column on an existing parquet — 0.6 work under the amended Principle 3, so the
prerequisite is a design round rather than a major bump. Filed as **RM43** with the two
smaller constraints found alongside — `PharmVariantRow` has no `alts` column at all, and `variant_key`
is a *property* on these models, so it is materialized in no PGx parquet and a consumer cannot join
them to `weights.parquet` on it either.

**What ships is legibility.** `_check_positional_joinability` reports, per positional table, how many
rows have no `chrom`+`start` and **how many of those the injected `resolution.csv` could place**. The
second count is the actionable half: it separates "this module was never enriched" from "the
coordinates exist and this tier does not apply them here", which is a distinction the author cannot
otherwise make. A **half** coordinate is counted apart — `haplotypes.csv` drafted from CPIC carries a
`start` with no `chrom` (CPIC publishes the position on `sequence_location` and the chromosome on
`gene`), and 106 of the 106 rows in `reference_examples/cyp2c19_star_alleles/` are that shape. The
table set is derived from the models (`chrom` and `start` both declared), never hand-kept. One
aggregated line per table, in `validate` as well as `compile`, de-duplicated between them.

**A warning in both modes, deliberately never a `strict` error.** Rsid-only identity is legal by these
models' own rule, so escalating would have the format tighten a field it left open; and the remedy is a
compiler change, not an authored edit — the `not_covered` / VRS-coverage class, where refusing makes a
correct module uncompilable for something its author cannot clear.

**`heteroplasmy.csv` joins the enricher's subject list**, which is the other half of the same gap:
`_collect_subjects` covered `variants.csv`, `pharm_variants.csv` and `haplotypes.csv`, so an
rsid-authored heteroplasmy module resolved to nothing at all and the new warning would have named a gap
no tool could close. It is the one subject here that is **build-dependent** — `HeteroplasmyRow.variant_key`
mints *with* `alts`, exactly as `VariantRow` does (verified equal for both the rsid and the coordinate
shape), so that load passes the module's `genome_build` where the two PGx loads rightly do not. Its
allele constraint is `None`: a measurement band over a locus is not a claim about a genotype.

**Also recorded, not fixed:** `manifest.compilation.fully_resolved` is `all(...)` over `VariantRow`, so
it is **vacuously `true`** for a table-only module — against the trust rule its own field comment states
(*"a consumer trusts a module when `resolution_mode == "strict" or fully_resolved`"*). And
`resolution_signature`/`resolution_sources` stay unset for such a module, so its injected table leaves
no trace in the manifest. Stamping the signature is blocked on reverse, which rebuilds `resolution.csv`
from `weights.parquet` alone; both halves are in RM43, beside the registry's S8.

## 2026-08-10 — `just-dna-enricher` + `just-dna-compiler` 0.5.2: the quirks a panel-scale consumer hit

Everything in this cut came from `just-dna-lite` rebuilding all ten `just-dna-seq` modules on the 0.5
route (S3–S6 in [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md), plus five freeform items). None of
it touches a model, a parquet column or a manifest field, which is what makes it patch-legal inside the
closed digest window — **verified rather than assumed**: all eleven `reference_examples/` modules
recompile to byte-identical `artifact.digest`, `content_signature` and `resolution_signature`, compared
against `HEAD` in a detached worktree. `just-dna-format` stays at 0.5.0.

**A batch lookup has to hash its probe, and that is why a gene panel never finished (S3).** DuckDB
cannot fold a disjunction of equality *conjunctions* into a hash probe, so
`WHERE (chrom=? AND start=? AND ref=? AND alt=?) OR …` was evaluated against every row of the
reference and the cost grew with `alleles × rows`. The consumer's 297-gene panel ran two hours at 12%
CPU with no disk I/O — which reads like a deadlock and was one large expression tree — and only became
buildable by slicing `variants.csv` into 10,000-row batches to cap the quadratic term. Measured here on
the 4,431,781-record snapshot, 5,000 alleles, same connection, identical output: **88 s → 0.21 s**.
`clinvar.lookup_clin_sig` and `resolver._lookup_rsid_candidates` now join a temp probe table
(`resolver.probe_table`); `clinvar.select_by_gene` is single-column and became `gene IN (…)` — 20.9 s →
6.6 s, because `IN` is pushed into the parquet reader and an OR-chain is not. `_lookup_positions_by_rsid`
and `citations_for` already used `IN` and were left alone.

Two findings inside that one worth keeping. **The join was never the cost — parameter binding was.**
Same query, same data: literal `VALUES` 0.21 s, a composite-key `IN (?, …)` 1.04 s, a parameterized
`UNNEST(?::VARCHAR[])` 3.51 s, `executemany` 8.6 s. So the probe rows are rendered as escaped SQL
literals (the way `_connect` already renders the parquet path) and parameterizing it back would give up
most of the win. And the **first** benchmark was misleading: a sample taken with `LIMIT 5000` is
clustered on one contig, where row-group statistics prune the OR-chain and the speed-up reads as ~1×.
The realistic shape is alleles spread across the genome. `test_query_shapes.py` pins both halves — the
query *plan* must contain a hash join (no clock involved), and both shapes are timed in one process so
a slow runner moves both numbers together.

**A check that cannot fail is not run, and the run says so (S4).** Where a module declares it was
drafted from the very ClinVar snapshot the `clin_sig` cross-check reads, every authored value is a copy
of what it would be compared against: 27.1 s against 2.6 s on a 7,818-row panel, byte-identical output,
and 0 conflicts either way — *necessarily* 0. The zero was the defect rather than the cost, because it
looks like evidence. `clinical.tautology_reason` compares the module's `panel:` pin
(`GenePanelSpec.reference`/`reference_sha256`) against the snapshot's `release.json`
(`clinvar_file_date`/`source_sha256`) and skips only on an **established match**; no `panel:` block, a
panel over another source, an unstated pin, a different release or an unreadable `release.json` all
leave the check running, because an unknown is never a permission to skip. The reason travels on
`EnrichmentResult.clin_sig_not_checked` (`not_requested` / `no_snapshot` / the tautology sentence /
`None`), since an empty conflict list otherwise says two opposite things. `locations.read_release` is the
first reader of `release.json` outside `cache status` — it was written by every builder and consulted by
nothing.

**A placeholder that protects a decision nobody has to make (S6).** `draft_gene_panel` left `genotype`
as `<<REPLACE>>` on every row, including the mitochondrial genome (haploid) and chrY outside PAR1/PAR2
(hemizygous), where exactly one genotype is expressible — so every consumer independently rediscovered
that the natural "write both zygosities" fill is wrong there, and one wrote `A/G` and `A/A` across 264
mitochondrial loci in a genome-wide panel and 260 in a cardiac one, each asserting a second copy that is
not there. `sole_expressible_genotype` now writes the ALT where the contig leaves nothing open, keeping
the stub everywhere else; Y is decided **per locus** through the three-valued
`vrs.in_pseudoautosomal_region` (`XG` and `SPRY3` straddle a boundary), and both `True` and `None` keep
the placeholder. The run reports what it committed to in one aggregated line — those rows read as
homoplasmic/hemizygous, and a heteroplasmic *level* belongs in `heteroplasmy.csv`. Row counts do not
change: the doubling the consumer saw is their own `fill_genotypes` step, which now has no placeholder
to expand.

**The chrY half of that report was checked and does not reproduce**, which is why nothing in the
compiler moved: a real `SRY` row (`rs104894976`, Y:2787207, genotype `A/G`) enriched from the snapshot
and compiled produces the ploidy warning exactly as MT does. The consumer's own note has since been
corrected the same way; what they were seeing was their output truncating the tail.

**One bad citation used to kill a 297-gene draft.** ClinVar files 218 of 3,952,341 `PubMed` rows under
an id that is not a PMID (Variation 12606 cites `168335863`, nine digits; PubMed is at eight), so
`StudyRow` refused it — correctly — as an unhandled `ValidationError` in the middle of drafting.
`clinvar_build.build_citations` now drops them at the snapshot boundary using the format's own
`extract_pmids` grammar rather than a restated regex, and `_study_rows` skips-and-counts anyway, because
every snapshot already published carries them. The two shortfalls are reported apart: `--max-citations`
is a choice this run made, an unusable id is a defect in the source.

**One ordering bug, three bug reports.** `_resolve_parquet_cache` calls `load_env()` inside itself, but
every `resolve_*_reference` passed `default_*_cache_dir()` as an *argument* — evaluated first. With the
cache base set only in `.env`, the **first** resolve in a process therefore computed its default from
platformdirs and returned `None`, while every later one was correct. That produced `cache pull` writing
into `~/.cache` while `cache status` looked in the configured directory and reported *absent* moments
after a successful pull, `draft-panel --offline` refusing with "no ClinVar snapshot found" for a
snapshot `cache status` called present, and a test module whose first skip-guard silently skipped.
`_cache_dir` now loads the environment itself: one load, six resolvers, both CLI paths.
`test_locations.py` runs in a subprocess and demonstrates the old asymmetry rather than asserting about
it — in-process it would neither reproduce nor stay isolated, since `load_env` mutates `os.environ` for
the whole session.

**`compile_module(resolve_with_ensembl=False)` now says what it just did.** The flag names Ensembl and
is the master switch for resolution of every kind, so turning it off with a complete `resolution.csv`
beside the spec compiled **successfully** with `chrom=None` on every weight row — rows that can never
match a VCF. The silent success is the defect; the combination now warns. The rename the report also
suggested is a published-signature change and stays a 1.0 item.

**Documentation, from the same batch (S5).** COMPILER.md's coverage table split the `direction` row so
each tick names its tier, and § Upgrade derivation now states outright that `weights.parquet` carries
the **authored** value only, that an empty column on a legacy module is correct, and that a
parquet-side consumer applies `derive.direction_from_state(state, weight)` itself. The compiler does not
and should not fill it: `state='significant'` carries no direction, so the derivation refines one from
the weight sign — sound as a reader's fallback, a fabricated fact in a published table. Whether an
artifact should ever carry the derived axes is a 1.0 question and is parked as such.

**Consciously not done:** one DuckDB connection per `enrich()` run. At 0.07 s a connect it is not where
the time goes, and threading one connection through three call sites is a refactor with its own risk.

## 2026-08-09 (later) — consumer note: `just-dna-lite` rebuilt all ten modules on the 0.5 route

Recorded from the consumer side, per the working agreement. **Nothing is being requested here**; five
findings that belong to this tree are filed as freeform items at the end of
[ROADMAP.md](ROADMAP.md#freeform-suggestions--the-06-idea-book) (the `clinvar_draft` citation crash,
`cache pull` writing where `resolve_*` does not look, the first-resolve-in-a-process ordering,
`draft-panel --offline`, and the `resolve_with_ensembl=False` naming trap).

**What the consumer built.** The six curated Generation-I ports moved off
`compile_module(ensembl_cache=…)` onto `just-dna-enricher enrich` → `resolution.csv` → inject-only
compile, and gained `literature.csv`. The three ClinVar modules (`cardio`, `cancer`, `pathogenic`) were
**rebuilt rather than re-ported** — the old route scanned the raw ClinVar VCF and baked coordinates;
the new one drives `clinvar_draft.draft_gene_panel` over the published snapshot, so variants are
authored by identity, carry a typed `clin_sig`, sit above a stated review-status floor, and are grounded
on ClinVar's own per-variant literature links instead of one blanket citation of the resource paper.
`module_spec.yaml` carries a `panel:` block pinning `clinvar_file_date` + `source_sha256`. A tenth
module, `pharmgkb`, is new: the ClinPGx clinical annotations at evidence 1A/1B/2A/2B, which is the first
`pharm_variants.csv` module outside this tree's reference examples.

**Two things the reference examples do not show, which a second implementor will hit.**

1. **A drafted panel needs a zygosity decision per row, and at panel scale it cannot be per row.**
   `draft_gene_panel` leaves `genotype` as `<<REPLACE>>` for good reasons, and `_genotype_worklist`
   reports the alleles rather than writing them — right for a curated module, but `cardio` is 57,696
   records. The consumer expands each stub into **both zygosities a diploid caller can emit** (`ref/alt`
   and `alt/alt`) and says so in the conclusion, which is a transcription of zygosity rather than a claim
   about its consequence, and matches what the Generation-I modules did. Worth a sentence in the panel
   docs either way, since "what do I do with 57k placeholders" is the first question the command raises.
2. **The licence cross-check compares spellings, not grants.** A ClinVar panel that declares
   `license: CC0-1.0` warns, because the `SourceRow` says `public-domain`; they are the same grant. Not
   asking for an equivalence table — the warning is explicitly "not adjudicated here" — just noting that
   the obvious SPDX id for a US-government work is the one that trips it.

**The registry's `/check` endpoint earned its keep.** `POST /api/v1/modules/{ns}/{name}/check` graded
`longevitymap` **invalid** where the local best-effort compile passed: four rows whose genotype is not
among the locus's resolved alleles (`rs699 A/T` and `T/T` against `A/G`; `rs1207362 C/C` against `G/T`;
`rs2107538 A/A` against `C/T`). That is Generation-I curation following a paper's strand rather than the
reference's, and it is *not* a reverse-complement away — `rs699`'s authored pair mixes one forward-strand
allele with one reverse-strand one, so no transformation recovers it. The consumer drops such rows
(named in its log) because a genotype whose alleles are not at the locus can never match a VCF; the
repair is curation against the original papers. Four rows in one module, found by a check that costs
nothing — the strict/best-effort split is doing exactly what it was designed to do.

## 2026-08-09 — consumer note: `just-dna-lite` is on the 0.5 line

Recorded from the consumer side, per the working agreement — no change is being requested here.
`just-dna-lite` now pins `just-dna-format>=0.5.0`, `just-dna-compiler>=0.5.1`,
`just-dna-enricher>=0.5.1`. Two import sites had to move, and neither is greppable from its old name:

- `RSID_PATTERN` from `just_dna_format.spec` to `.vocab`. `ALLELE_PATTERN` is still re-exported from
  `spec`, which makes the pair look inconsistent from outside — worth a line in the 0.5 notes if
  other consumers hit it.
- `just_dna_compiler.resolver` to `just_dna_enricher.resolver`. Same `resolve_variants` signature and
  `EnsemblReferenceError`, so it was a one-line change once located.

**Round-trip audit of all five published modules** (`just-dna-seq/annotators`: longevitymap,
lipidmetabolism, vo2max, superhuman, coronary), download -> `reverse_module` -> `validate_spec` ->
`compile_module` -> diff. All five reverse, validate and recompile **cleanly**, and no column is ever
dropped. The deltas, for anyone sizing the same migration:

- `weights` 19-20 -> 37 columns; `annotations` 5 -> 8; `studies` 7 -> 19.
- `weights` and `studies` row counts unchanged for every module. `annotations` grows only where a
  variant carries multiple genotypes, now keyed by `variant_key` instead of collapsed per rsID:
  lipidmetabolism 15 -> 41, vo2max 13 -> 28, coronary 27 -> 77; superhuman and longevitymap unchanged.

So republishing under 0.5 is a rebuild, not a data repair — worth knowing before someone budgets it
as the latter. Full write-up in `just-dna-lite/docs/MODULE_FORMAT_0_5_MIGRATION.md`.

**One thing that cost time and might be worth a docs line upstream:** `compile_module` called without
`ensembl_cache=` returns `success=True` with `chrom=None` rather than warning that resolution was
skipped. Combined with an Ensembl cache that is merely *incomplete*, the failure is silent in the same
way — variants on missing chromosomes come back unresolved and the module still compiles. We hit both
at once and it read as a resolver bug for a while. The deprecation notice pointing at
`just-dna-enricher enrich` -> `resolution.csv` is clear, and we will migrate off `ensembl_cache=`
before 1.0.

## 2026-08-07 — `just-dna-enricher` / `just-dna-compiler` 0.5.1: the hosted tier

**A network-tier patch, and `just-dna-format` does not move.** Nothing here touches a parquet, a model
or a manifest field, which is exactly what makes it legal inside the closed 0.5 digest window (P3/P8).
Format stays at **0.5.0**; compiler and enricher cut **0.5.1**, and the enricher's floor rises with it
(one item, RM41, adds a compiler symbol the enricher now uses).

### RM38 — a cache for every licence-gated source

The three PGx sources (ClinPGx, CPIC, PharmVar) were the only `licensing.TERMS` entries with
`commercial_use=False` **and** the only ones with no cache — the same set, and not a coincidence worth
leaving. Ensembl, ClinVar and gnomAD constraint were already snapshot-first, so a hosted `enrich()` was
cache-served; a hosted PGx check had two options, fetch a gated source live per request on the
operator's own credentials or skip. Two independent reasons make the first wrong for a service, and
either alone is enough: the operator's acceptance and *personal, non-transferable* PharmVar key stand in
for every caller's, and every published rate figure is **per IP**, so a server multiplies its callers
onto one allowance rather than getting one each.

- **Builders** (`[dev]`, polars): `cpic_build` pulls the whole CPIC PostgREST database into five
  parquets — 132 genes, 120,778 rows, **256 KB** — with no gene filter, because a snapshot covering only
  the genes the operator thought of answers "CPIC has nothing" for the next one. `pharmvar_build` takes
  the single `/genes` call (15 genes, 1,173 core alleles, **36 KB**). Both store the source's values
  **verbatim** and map to this workspace's vocabularies at read time, so a mapping fix reaches a
  snapshot built last month and a live answer and a snapshot answer are the same object by construction.
- **Plumbing**: `locations` gains `CPIC_SUBDIR` / `PHARMVAR_SUBDIR` / `CLINPGX_SUBDIR`, their
  `default_*_cache_dir` / `resolve_*_reference`, and `$JUST_DNA_{CPIC,PHARMVAR,CLINPGX}_CACHE`. Six
  resolvers now share one body; they had been copied per snapshot and had already drifted.
  `download.ensure_cpic_snapshot` / `ensure_clinpgx_snapshot` provision from HuggingFace.
- **Readers**: duckdb snapshot clients duck-typed against the live ones, so `enrich_pgx` and
  `draft_gene` needed no branch. Builder in polars, runtime pass in duckdb — the house convention.
- **`--offline` is real**: it was a no-op that warned and returned for `pgx`, and absent entirely from
  `draft`. Each leg is now snapshot → live → **skipped with a reason** (`PgxResult.skipped_offline`),
  and `offline` outranks an injected *live* client, decided on the type — a snapshot client is exempt
  because reading a local parquet is not egress. `clinpgx check` provisions automatically instead of
  skipping silently, because unlike the other two it has no live route to fall back to.
- **The route is recorded, not implied**: `PgxResult.routes` says `snapshot` or `live` per source, and a
  snapshot stamps its own release into `SourceRow.dataset`, as the two gnomAD constraint routes already
  do. A consumer must be able to tell a pinned file from a live API.
- **`cache status` / `cache pull`** are the operator's entry point; `pull` gates ClinPGx and CPIC on
  `--use`, because under a data-usage policy the terms are accepted when the data is **taken**.
- **PharmVar is build-only, and that is the design.** Its bulk data is pulled under a key its terms §2
  make personal and non-transferable, and no axis `SourceTerms` records covers passing that on —
  `redistribution=True` describes the CC BY-SA grant over the *content*, not a clause about the
  *account*. An unestablished permission is never a permission, so: a resolver and a builder, and
  deliberately no `ensure_pharmvar_snapshot` and no `pharmvar publish`.

**Two prerequisite defects, fixed on the way.** Publishing a snapshot silently dropped its
`LICENSE.txt` — the allow-patterns were `data/*.parquet`, `citations/*.parquet` and `release.json` — so
the pinned-licence design pinned nothing for anyone who *downloaded* rather than built. Both ends fixed.
And `clinpgx.py` imported its layout constants from the `[dev]` builder; they live in `locations` with
the rest, where the builder/publisher/provisioner/reader rule already puts them.

**Two integration defects, found by probing the real sources rather than their docs.**

- **PharmVar publishes every defining variant against *both* assemblies and lists GRCh37 first**, and
  `_merge_variants` was first-wins over any `NC_` row, so **451 of 739** rsID-keyed defining variants
  would have carried a GRCh37 position (DPYD rs868235016 at chr1:97547910 rather than its GRCh38 place).
  The accession *version* cannot separate them — chr10 is `.10`/`.11` and so is chr22 — but
  `referenceCollections` can, exactly. Latent until now because nothing consumed
  `PharmVarAllele.variants`; a snapshot stores them, which is what turns a latent wrong number into a
  written one. Fourth build confusion here, hence `pharmvar.PHARMVAR_GENOME_BUILD` as a named constant.
  The test fixture carried only a GRCh38 row — corpus uniformity again — and now carries both, in the
  real payload's order.
- **CPIC does publish a chromosome, on `gene.chr`.** A 2026-08-03 probe read `sequence_location` alone,
  which genuinely has none, and concluded CPIC has none at all — so the drafting provider skipped every
  defining variant CPIC gives no rsID for: 18 in CYP2C9, 14 in TPMT, 4 in NUDT15. Joining `gene.chr` onto
  the symbol the location row already names is a lookup in CPIC's own tables, not the inference that
  probe rightly refused. `draft --gene CYP2C9` now writes 17 coordinate-only haplotype rows it dropped,
  and the module validates.

### RM39–RM42 — four seams a consumer could not cross

From a `just-dna-registry` field report, and one argument each time: **a number this workspace computed
and then discarded gets recomputed by every consumer, and a recomputation is a place to drift.**

- **RM39** — `enrich_dosage_sensitivity` was the only pass with no `offline`, so a caller running the
  family under one flag had to know out of band that one member ignored it; forgetting meant silent
  egress from a path documented as making none. Now a no-op with a warning, reported as
  `ClinGenResult.skipped_offline`, with `--offline` on `dosage`. An injected `curation_text` still wins.
- **RM40** — `EnrichmentResult.vrs` carries the `MintResult` `enrich()` already computed: the two
  counters the compiler later stamps into the manifest, plus `unmintable_reasons`. `None` when the pass
  did not run, never a coverage of zero.
- **RM41** — `compiler.load_csv_rows` is public (`_load_csv_rows` kept as an alias), and
  `compiler.load_spec_variants` does the yaml read + build injection + re-stamp in one call.
  `verify_acmg_sf` and `check_identifiers` accept `spec_dir=` beside `variants=` — exactly one, never
  both. This is the item that makes 0.5.1 a two-package cut.
- **RM42** — the nine `stop_after_attempt(3..4)` decorator arguments are now `net.attempt_floor(n)`,
  reading `$JUST_DNA_HTTP_RETRY_ATTEMPTS` per call. A **floor**, so gnomAD and eutils keep their higher
  default; below a client's own number it is a no-op. Safe to raise because every gated client paces
  *before* it retries. Only bare `stop_after_attempt`s were replaced — a composed policy means the
  conjunction its author wrote.

Also: `PharmVarClient` loads `.env` where it reads the key, rather than relying on some *other* call
having resolved a cache path first — which worked for `enrich_pgx` by accident and not at all for the
new builder. And ENRICHER.md gains a **cache chapter**: all six snapshots, their env vars, the layout,
how to pre-cache from HuggingFace, and what to do when one is broken.

## 2026-08-07 — 0.5.0 published, and the CI that was meant to gate it never ran

**0.5.0 is released** — tagged `v0.5.0`, built into `dist/`, and on PyPI for all three packages, with
`just-dna-enricher` 0.5.0 the first release of that package. The docs are brought into line with that in
one pass: every place that told a reader "0.4.0 is the published line" or that the digest window is open
now says the opposite, and the historical rationales that were true when written are tense-corrected
rather than deleted (the argument is the part worth keeping).

**The digest window closing is the substantive change, not the version number.** `integrity.file_entries`
skips missing files, so a **new optional table** is still additive at any time — a module that does not
carry the new parquet keeps its digest byte for byte — while a **new column on an existing parquet** now
moves the digest of every module compiled against 0.5.0, which is no longer a hypothetical set. Sorting
the active roadmap by that rule turned out to be a vindication of how 0.5 was cut rather than a new
constraint: the pre-cut batch was columns *precisely because* columns needed the window, and everything
deferred past it was deferred on design or corpus questions. So 0.6 is unblocked by construction — RM23,
RM24, RM25, RM16 and RM28 are all new tables, RM5 widens a grammar, RM27 is a gate over a column that
already ships, and RM4 is compiler behaviour. Only two items move: **RM15** (multi-build identity) is now
a 1.0 item rather than a minor, and **RM10** acquires a gate it never had — as a column on an existing
table it is a major, as its own table or manifest metadata it stays a minor, and that placement is now
the expensive half of the decision. The new table is in [ROADMAP § 0.6](ROADMAP.md#06--what-a-minor-permits).

**CI was red from the commit that added it, and not for any reason in the code.** All three jobs — ruff
and both pytest legs — failed inside *Set up job*, before a single test ran: `astral-sh/setup-uv@v9`
resolves against nothing, because astral-sh **stopped publishing floating major-version tags after
`v7`**. Only exact `vX.Y.Z` tags exist from `v8.0.0` on, so `@v8` and `@v9` are equally unresolvable
while `@v7` and `@v6` still work — which is the trap: the pin looks like every other action pin in the
file and the failure mode is not "wrong version" but "no such ref". Pinned to `v9.0.0`. `actions/checkout@v5`
and `actions/upload-artifact@v7` were checked against the same list and do resolve; they are left alone.

The suite itself was never the problem — **1314 passed, 6 skipped** on both Python 3.13 and 3.14 locally,
with `uv sync --locked` clean and `ruff check` clean. Worth recording as the lesson rather than the fix:
a green local suite says nothing about a workflow that dies before it starts one, and the badge now in
the README is there so the next such break is visible from the front page instead of from a failure
notification nobody reads.

## 2026-08-07 — the enricher minted identities its own compiler refused

**`compile --strict` rejected two of the eleven reference examples, one of which documents that exact
command as its point.** Found by the pre-release audit, running the *shipped wheels* against the corpus
rather than the test suite: `pathogenic_clinvar` failed on 185 alleles and `shox_par1` on 2. Bisected to
the per-ALT `vrs_id` change earlier the same day — regenerating that example's `resolution.csv` online
took it from 52 identities (all offline-mintable substitutions) to 289 substitutions **plus 185 indels**,
and `_verify_vrs_ids` escalated every unverifiable allele under `--strict`.

**The severity was the defect, not the data.** Minting indel ids over the seqrepo proxy is exactly what
`just-dna-enricher` exists to do, so the two tiers had been shipped disagreeing: the network tier
produced identities the compile tier refused to carry, and the error's own two remedies were *recompile
without strict* and *drop the vrs_id* — lower the guarantee, or delete a correct identity, the latter
being the same abstention the per-ALT fix had just finished removing one file away. The blast radius was
never only the examples: every ClinVar-derived module contains indels, and the authoring skill's step 6
tells every author to run `validate --strict` then `compile --strict`.

**`strict` means *reproducible artifact*, and an injected indel VA reproduces perfectly** — the bytes
come from the table, the compile is deterministic, recompiling gives the same digest. What is out of
reach here is the *verification*, not the reproduction, and escalating on that conflates "I could not
check this" with "this cannot be rebuilt". Two sibling checks had already reasoned it out correctly and
the pass beside them had not: `_vrs_coverage_warnings` warns in both modes because "an indel with no
sequence proxy, a build with no refget table" is fixable by no authored edit, and `frequencies`'
`not_covered` sits outside the strict gate for the same reason.

So the outcome now splits on **whose limit the finding is**, which is the distinction that was missing:

* **the tier's limit — warning in both modes.** Indel/MNV, off-assembly contig, non-GRCh38 build.
  Nothing an author could write would let this compiler recompute them.
* **the row contradicting itself — error in both modes** (it was strict-only). A `vrs_id` recorded
  against no coordinate, or against no ALT: the row asserts an identity while withholding what that
  identity is a digest of, so nothing anywhere could check it. Same class as *inconsistent reference
  allele*.
* **mismatch — error in both modes**, unchanged.

`_verify_vrs_ids` now takes **no mode argument at all**, which is the honest signature: there is nothing
left for it to switch on. Nothing moved — `artifact.digest`, `content_signature` and
`resolution_signature` are byte-identical on all eleven examples, in both modes, since only severity and
reporting changed.

**Two things came out with it.** The warnings were **duplicated**, because the pass runs in
`validate_spec` and again in `compile_module` and `all_warnings` is seeded from the first — harmless
while these were strict-mode errors (which return early), and 370 lines for 185 alleles once they became
warnings. De-duplicated on the message, the way `_check_contig_ploidy` and allele membership already
were. And the corpus sweep gained a **strict pass** (`test_reference_example_compiles_under_strict`):
every other check over `reference_examples/` ran in `best_effort`, which is the default an inline fixture
reaches for, so a release's worth of examples could fail the command their own READMEs print with the
suite green. 1303 tests → 1314.

The general lesson, and it is the audit method rather than the bug: **a mode that no test exercises over
the real corpus is a mode nobody is checking.** The suite had 1303 passing tests and a dedicated
`validate`-agrees-with-`compile` file, and neither could see this, because both asked whether the two
commands agreed — and they agreed perfectly, on refusing.

## 2026-08-07 — a locus spelled `T>Y`: the right verdict with the wrong explanation, and a third compile-only check

**A non-nucleotide allele made the compiler blame the genotype.** `hosting_verdict("C/T", "T", "Y")`
returns `False`, and correctly — a substitution locus has no shared flank, so no spelling freedom, which
is exactly what keeps the strand-flip check sharp. But the message built on that verdict said the
genotype's alleles "are not among the alleles at this locus", and then explained it either as *the row
contradicts itself* or as *the resolving source's allele list is incomplete*. Both are false when the
locus itself is spelled with an IUPAC code or a symbolic allele: the author is sent to re-examine a
genotype that was right, three steps from the cell that is wrong. `alleles.non_nucleotide_reason` /
`non_nucleotide_alleles` (format tier, stdlib) classify the offender and both call sites — the
expansion's dropped-locus warning and `_check_allele_membership` — now name which of the two it is.
The verdict is untouched; only the explanation changed.

**Two reasons, each carrying its own consequence.** An ambiguity code is a permanent uncertainty, never
expanded into the alleles it could stand for; a symbolic/structural allele is a grammar gap (RM5) a
release may close. The first cut of this message appended the ambiguity sentence to *both* branches, so
a `<DEL>` locus was lectured about IUPAC — the identical conflation `cpic.unusable_allele_reason` was
repaired to stop making, reintroduced inside the message that repair paid for. That provider now
**delegates** to the format-tier classifier: one definition, two callers, each with its own wording.

**Why the grammar was not tightened instead**, since that is the obvious move and it is wrong three
ways: **no** `ref`/`alt`/`alts` column in the schema has a nucleotide grammar (eleven columns across six
models; `vocab.validate_allele` has exactly one user, `HaplotypeRow.allele`), so adding one rejects
`<DEL>` and `N` alongside a typo — tightening the field **RM5** exists to widen; a module with
`alts="Y"` *compiles today* under `best_effort`, so refusing it stops an existing module validating
(**Principle 3**); and the only non-ACGT allele that occurs in real variant records is `N`, which
`clinvar_build` already filters at the snapshot boundary. Full probe in ROADMAP's 0.6 idea-book, kept
because the reasons are reusable.

**`_check_allele_membership` was compile-only, and it is a mode ladder — so `validate --strict` reported
`valid` for a module `compile --strict` refused.** The third instance of the defect the 2026-08-07
readiness audit fixed for `_verify_vrs_ids` and `_check_p_value_num`, and it survived that pass because
the pass went **table by table**: this check reads *authored* rows rather than a sidecar, so "which
tables does `validate` read" could not surface it. Its own docstring already said it runs on the
authored rows *before* resolution expands them, which is precisely what makes it computable at
pre-flight. Now in `validate_spec`, with the resolution table (empty when the module carries none — a
row authoring its own `ref`/`alts` is judged from authored bytes alone). The compile-side call stays,
because `compile_module` runs `validate_spec` in **best_effort** regardless of its own mode, so
re-running is how a mode ladder reaches its real severity; its warnings are de-duplicated on the
message, the same way `_check_contig_ploidy`'s already are. The lesson for the next audit of this kind:
**enumerate checks, not tables.**

## 2026-08-07 — a VA per ALT: the identity a multi-allelic row was refused, and the coverage nobody counted

**`ResolutionRow.vrs_id` is one id per ALT, comma-joined and positionally aligned with `alts`.** It was
a scalar, and the mint pass abstained on any comma-joined cell — `_single_alt`, whose docstring gave the
reason as "a VA names exactly one allele, so a comma-joined cell has no single id; picking one would be
a data error wearing an identifier". That argument belongs to `derive_variant_key`, where it is right:
`variant_key` is one column naming one thing, so a plural cell must fall through to the coordinate key.
It was wrong for `vrs_id`, a cross-reference the schema deliberately keeps **outside**
`RESOLUTION_FACT_FIELDS`, on which no identity rests, and where nothing is picked because every ALT gets
its own id. The tier was already giving the opposite answer one file away:
`frequencies._alleles_from_resolution` expands a multi-allelic cell into one entry per ALT and always
had. Cost, measured on a real externally-authored module: **909 of 1,613 rows carried no id at all**
while every input needed to mint all 2,110 of their alleles sat in the same row, and all 2,110 were
single-base substitutions — stdlib, offline, no seqrepo. Across the five modules in that corpus, 4,022
allele identities that were computable and absent.

Shape notes, all load-bearing:

* **A parallel array, not one row per allele.** `resolve_from_table` groups resolution rows by
  `variant_key` and reads `len(loci)` as a *locus* count, so three alt-rows at one position would enter
  the one-to-many expansion path and be reported as three loci — and `locus_index` would then carry two
  different kinds of "many" (P5). A single-alt row still spells a bare id, byte-identical to every file
  already written.
* **A hole is a value.** An empty member means "this allele's id could not be minted here" — a
  substitution and an indel share plenty of sites, and losing the substitution's id to the indel beside
  it would be the same abstention one level down.
* **Desync is caught twice.** `ResolutionRow` refuses a pair of the wrong length at load; the compiler's
  `_verify_vrs_ids` recomputes member by member, so a pair of the right length in the wrong *order* is a
  mismatch — an error in both modes, like any other corrupt id.
* **Nothing moved.** `vrs_id` is outside every signature and `reverse_module` does not re-emit it:
  `artifact.digest`, `content_signature` and `resolution_signature` are byte-identical before and after
  on all five modules, and `compile → reverse → compile` is still a fixed point.

**Absence is now counted, because a VA is becoming a key.** `_verify_vrs_ids` only ever looks at ids
that are *there* — "a row with no `vrs_id` is skipped entirely" — so a table where nothing was minted
verified flawlessly. That was the right severity for a decorative cross-reference and the wrong one for
an identity anything may join on: an identity scheme covering an unstated fraction of the table is not
one a consumer can key on, and *unstated* is the defect. Both tiers now report coverage, and the counts
reach `manifest.compilation.vrs_alleles` / `vrs_alleles_identified` so a shortfall outlives the terminal
it scrolled past. Two counts rather than a ratio or a bool, for the same reason `fully_resolved` sits
beside `resolution_mode`: the shortfall's *size* is the reliability figure, and "complete" is derived.
The denominator is alleles, not rows. Gaps group by **reason class** — the first cut grouped on
`_recompute_vrs_id`'s per-row prose and produced forty lines each naming a different indel, which is the
per-row wall this codebase has now had to collapse five times. A shortfall **warns in both modes**: an
indel offline or a build with no refget table is fixable by no authored edit, and `strict` means
"reproducible artifact", which an incompletely-named table still is.

**The check's first act was to indict this repo's own corpus.** Four reference examples had never been
fully minted — `pathogenic_clinvar` at **52/474 (11%)**, `cyp2c19_star_alleles` 18/57,
`shox_par1` 6/14, `pgx_slco1b1_simvastatin` 0/2 — and nothing had ever said so, because verification of
present ids cannot see absent ones. All four are re-minted **online**, so the 187 indels went through
seqrepo normalization too: every one is now 100%, and `artifact.digest`, `content_signature` and
`resolution_signature` are identical to HEAD on all four. `grch37_build` carries no `resolution.csv`, so
it reports nothing new — its existing RM15 warning (VA minting is GRCh38-only) already says what it has.

## 2026-08-07 — pre-merge readiness audit: a green pre-flight that wasn't, and one timestamp in two spellings

**Blocker — `validate` reported `valid` for modules `compile` refused, and the authoring skill promised
it could not.** The 0.5 fix for this covered which *tables* `validate` reads; the exemption was then
applied per table rather than per **check**, so two checks stayed compile-only that read nothing but
injected or authored bytes. `_verify_vrs_ids` compares a `resolution.csv` row against its own
content-addressed id and consults nothing else — a **mismatch is an error in both modes**, so a plain
`compile` (no `--strict`) refused a module `validate` had just blessed as corrupt-free.
`_check_p_value_num` compares two encodings of one p-value in `studies.csv`. Both now run in
`validate_spec`, whose inputs already included them. The reason it hid: "it compares a sidecar" reads
like "it is a cross-check", and the cross-checks genuinely do need resolved rows — but a *self*-check on
one row does not. The line is **needs resolution**, not **touches a sidecar**.

**`validate` gained `--strict/--best-effort`.** Several checks are a mode ladder, so a modeless
pre-flight answered for the wrong compile: green under the default, refused under `compile --strict`.
The flag changes severity only, never which findings exist, which is what keeps the two commands one
contract. `test_validate_agrees_with_compile.py` pins both halves, including that an indel's
*unverifiable* id appears in `warnings` at `best_effort` and in `errors` at `strict` with the same
sentence.

**One instant, two spellings, and it moved a digest.** `sources.csv` wrote
`2026-08-03T02:03:23Z` (`strftime`) while `literature.csv` wrote `2026-08-01T20:55:37.406184+00:00`
(`.isoformat()`) — twelve producers reaching for whichever was nearer. Both columns land in a parquet
inside the Merkle root, so the same moment recorded two ways was two artifact identities for one set of
facts. There is now a single producer (`normalize.now_utc_iso`, second resolution, `Z`) and
`normalize_utc_timestamp` canonicalizes **on load** on all five models carrying `fetched_at`, so the
column is canonical by construction rather than by convention at the point of writing. An offset is
converted rather than truncated; an unreadable value raises instead of passing through, because this
column is machine-written.

*Digest move, one module:* `pathogenic_clinvar` (the only committed sidecar carrying the microsecond
spelling). `content_signature` and every fact signature are unchanged — the spelling was never inside a
fact set. Spent inside the unpublished window on purpose.

**What was deliberately *not* changed: `fetched_at` stays inside `artifact.digest`.** Removing it was
proposed and rejected. Two independent enrichments of one module legitimately happen at two moments, and
making their digests equal would need each *source* to publish its own last-modified time so the stamp
described the data rather than the fetch — unenforceable against upstreams that mostly do not offer one,
and bound to break wherever it was assumed. The digest correctly says "two artifacts, built at two
moments"; `content_signature` and the four fact signatures are the producer-independent identities, and
they already exclude it. `test_ensembl_cache_wins_when_both_present` was asserting digest equality across
two separately-enriched specs — a stronger claim than it meant, intermittently red on whether the two
`enrich()` calls landed in the same second. It now compares `resolution_signature`, which is the
instrument for "are these the same resolved facts".

**Lint is a gate rather than noise.** `ruff` was a declared dev tool with no configuration, so
`ruff check .` reported over a thousand findings — 808 of them one modernization nobody had decided on.
`[tool.ruff]` now pins `target-version = "py313"` (every member requires ≥3.13), an explicit rule set,
and the reasons `BLE001`/`ISC004`/`E501` are deliberately unselected. `Optional[X]` → `X | None`
throughout, PEP 695 type parameters in `net.py`, and `ruff check .` is clean. The printed authoring
reference is **byte-identical** across all of it — pydantic already normalized `Optional[str]` to
`str | None`, so `describe`/`requirements`/`reference` never showed the old spelling. Two changes in
that sweep were not cosmetic: `zip(..., strict=True)` on the PAR interval pairing in `vrs.par_partner`,
where truncation would have kept PAR1 answering and silently dropped PAR2, and `raise ... from exc` in
`integrity`'s signature-verify path, which had been dropping the cause chain.

**Docs.** `REFERENCE_EXAMPLES.md` §4 claimed `HeteroplasmyRow` keys on `(gene, reference_sequence)`;
the real key is `(gene, reference_sequence, tissue, variant_key)` plus `trait_efo_id`, and the section
that stated it wrongly is the one whose one-variant-per-gene shape had already made a module
uncompilable. It now names `_KEY_FIELDS` as the live list and points at `reference_examples/mt_heteroplasmy/`,
which was the only built example named nowhere in that document. Three pointers to a deleted
`docs/AUTHORING.md` now name where the material actually lives in the skill.

## 2026-08-06 — externally authored modules: the authoring contract said 0-based

Five modules produced elsewhere (two Claude4Science bundles: a GWAS intelligence/personality catalogue
and a bodybuilding/lean-mass panel) were run through the shipped surface end to end. Four of the five
compiled clean under `--strict` on the first try, which is the good news and also how the finding
stayed hidden. The dogfooding value was in what the tools *said* about modules nobody here wrote.

**Blocker — the authored `start` columns described themselves as "0-based" while every tier reads them
as 1-based VCF POS.** `VariantRow.start`, `StudyRow.start`, `HaplotypeRow.start` and
`PharmVariantRow.start` all carried it, and those strings are not commentary: `describe`,
`requirements` and `reference` print them, so they *are* the authoring contract. An independent author
followed them and shifted **3,038 variants across four modules** by one base. The inconsistency was a
known one — recorded in CLAUDE.md as a CPIC/PharmVar gotcha and named in the ROADMAP as a blocker for
the `end` column — but it was rated low severity as an internal tidiness issue, because nobody had
watched it produce a wrong module. Fixed: the four descriptions now state the VCF convention and say
not to subtract one. `schema/tests/test_coordinate_convention.py` pins the prose against what
`derive_vrs_allele_id` actually does with the number, so the two cannot drift apart again.

**Nothing offline could catch it, and that part is by charter.** A uniformly shifted module passes
`validate`, passes `compile --strict`, reports `fully_resolved: true`, and mints `ga4gh:VA.…` ids the
compiler's VRS pass then reports **verified** — a content-addressed id is a correct digest of whatever
it is handed, so it certifies the wrong locus perfectly happily (24 of 69 ids in the smallest module).
The Class-2 coordinate cross-check (`resolution._verify`) was defeated for a second reason worth
recording: the modules shipped their own hand-built `resolution.csv`, so **both sides of the redundancy
check came from one author with one convention** and agreed exactly. Validate-by-redundancy assumes
independence; authoring both sides removes it. The `create-module` skill says so under its own heading
(*Never author both sides of a redundancy check*, in step 3 and again in *The checks, and the two ways to
defeat them by accident*).

**Fixed — the reference-allele check misdiagnosed the cause and reassured the author falsely.** It
reported "authored ref 'T' disagrees with GRCh38 11:61790330, which is 'C'", pointing at a `ref` column
that was correct, and then added "the minted allele id is still the true allele at this position" —
true of the position recorded, worthless when the position is the defect. `verify_reference_alleles`
now reads one base either side (one window read, so the diagnosis costs no extra round trip) and names
a coordinate shift when it can establish one, withholding when both neighbours match and the direction
is undetermined. `RefMismatch.distorts_the_allele_id` is true for a shifted row whatever the claimed
length. On the real module: 56 single-line findings became two grouped ones, 41 of them named as
"coordinate shifted 1 base to the right". Sensitivity is inherently partial — only rows whose
neighbouring base differs from the authored `ref` are visible, ~3 in 4 — and the docs say so rather
than implying a clean bill.

**Fixed — one variant gnomAD has never heard of aborted the whole `frequencies` pass.** gnomAD answers
an unknown `variantId` with `{"message": "Variant not found"}` carrying **no `path`**, while still
returning `data` with a `null` at that alias. `_errors_by_alias` classed every pathless error as a
broken query and raised, so `frequencies` died with a traceback on the bodybuilding module (6 of 13
alleles absent) — even though the null node already *is* the per-row answer and `fetch_frequencies`
handled it. The reasoning behind the old rule is right and stays: a genuinely broken query must never
read as "nothing found". The premise was wrong for this API, so absence is now recognised by message
and logged, and the batch keeps its good rows. `not_found` is what such a row was always meant to get.

**Fixed — RM37: `content_signature` counted *where* a value was written.** `compile → reverse →
compile` held `artifact.digest` and `resolution_signature` exactly but moved `content_signature` for
any module filling `curator`/`method` on the row instead of in `defaults:`, because `reverse_module`
re-emits the value in the other place and the hash read the CSVs before spec defaults applied. No
reference example could show it — all eleven use `defaults:`, the canonical form reverse emits — so it
took a module authored elsewhere, which is RM36's lesson again about an axis the corpus holds uniform.
Fixed by `_resolve_spec_defaults`: `defaults:` is folded into each variant row immediately before
hashing, making the signature a function of what the module means rather than where it was typed.

Filed as *surfaced, not fixed* on compatibility grounds, then shipped once that objection was checked
rather than assumed. **0.5 was unpublished**, which is where an identity change is cheap; and the change
is narrower than it looked because it reuses RM36's `genome_build` normalization — an effective value
equal to the `Defaults` model's own default is omitted from the hash, exactly as an unset optional
column always was. Measured: **one of eleven reference examples moved** (`grch37_build`, which sets
`curator: audit` with blank cells), itself a 0.5-era addition. It also closed an unfiled defect in the
same stroke: `defaults:` reached the hash by no path at all, so two modules differing *only* in
`defaults.curator` hashed **equal** — different content under one identity, which is what a dedup key
must never do. `priority` is deliberately untouched and stays correct by the same rule (its model
default is `None`, so an unset one is still omitted, and `reverse` still refuses to infer one).

**Re-scoped.** The `weights.parquet` `end` item said it was blocked on "settling the coordinate
convention". Half of that is now closed — the authored `start` is 1-based VCF POS and says so — and
what remains is genuinely open: whether a second coordinate is interbase-half-open or inclusive, the
same choice RM15 must make. The two stay paired for that reason and not the old one.

## 2026-08-06 — 0.5 readiness audit: the round trip moved a module to another assembly

A pre-publication audit of 0.5. The suite was green (1178 passed) and all ten reference examples were
Principle 7 fixed points, so the findings came from probing the one place the corpus was uniform: **every
reference example is GRCh38**, which makes "reads the module's build" and "writes GRCh38" indistinguishable.
Seven code paths were doing the second. New reference example
[`reference_examples/grch37_build/`](../reference_examples/grch37_build) is the probe, and its README is the
evidence.

**Blocker — `reverse_module` hardcoded `genome_build: "GRCh38"`, so `compile → reverse → compile` relocated
a GRCh37 module's identity.** `genome_build` reaches the artifact through `manifest.json` and **no parquet
column**, so reverse had nothing to read and simply wrote the constant — into the rebuilt
`module_spec.yaml` *and* into `resolution.csv`'s own `genome_build` column. On a GRCh37 module the recompile
then minted `ga4gh:VA.…` ids for GRCh37 coordinates: `artifact.digest` moved (P7 failed outright), and the
new key was a **false content-addressed claim** — a VA asserts this allele at this base of this sequence,
and 6:26,093,141 on GRCh38 is a base the module never named. 0.5 had already fixed this on the forward path
(`_restamp_for_build`, "a GRCh37 module minted GRCh38 identities, silently"); reverse reintroduced it one
step later. Fixed by `_genome_build_from_artifact`, reading the artifact's own manifest, with an explicit
`genome_build=` override for a bare parquet directory (also `--genome-build` on `reverse`). The mislabelled
`resolution.csv` was the sharper half of that bug: `resolve_from_table` **filters** rows on that column, so a
reversed table was not only wrong but unjoinable.

**Blocker — the enricher ignored the module's declared build entirely.** `enrich()` took
`genome_build: str = "GRCh38"` and **nothing ever passed it** — no CLI flag, no caller. Every resolver link
inside is gated on `genome_build == "GRCh38"`, and so is the warning saying a non-GRCh38 module resolves
nothing, so all of that was unreachable: enriching a `genome_build: GRCh37` module resolved it against
GRCh38 Ensembl, wrote the **GRCh38** coordinate into its `resolution.csv` labelled `GRCh38`, minted a
GRCh38 VA for it, and said nothing. The compiler then correctly refused the lot, so the visible symptom was
an unresolved module while the file on disk claimed another assembly's coordinate. Exactly the
`_restamp_for_build` shape: the guard and its fall-through both existed and the value never arrived. Fixed
by `enrich.spec_genome_build`, which reads the declaration; the parameter stays an inject-only override. A
spec with no `module_spec.yaml` gets the format's own default (a derivation, not a guess); one whose yaml is
present but unreadable now **refuses**, because choosing an assembly for a module whose declaration cannot
be read is the invention being removed.

It also wrote `status="not_found"` for those rsIDs — "the source was asked and does not have this" — when no
link had run. That is the `None` ≠ `False` rule, and the fix is to write **no row**: the position is still
unset, which the unresolved list already reports. `VALID_RESOLUTION_STATUS` has no `unchecked` member, and
adding one to describe a row carrying no fact would be worse than writing no row.

**Blocker — one GRCh37 row aborted the whole enrich run.** `refget_accession` **raises**
`UnsupportedBuildError` for a build with no table, deliberately, so every call site must catch it.
`VrsMinter.mint`'s substitution branch did not — while `_mint_normalized` beside it always had — so a single
hand-authored `genome_build: GRCh37` row in an otherwise fine `resolution.csv` killed the run with an
unhandled exception. Now it is an unmintable row like any other. `derive_vrs_allele_id`'s docstring had
meanwhile promised it "never raises"; it now documents the one input that does, and why softening it to
`None` would be wrong (`None` is a per-row fact; an unknown build is the caller's whole frame of reference
missing).

**Blocker — the frequency pass queried gnomAD with coordinates from another assembly.**
`_alleles_from_resolution` took every resolved row regardless of `genome_build` and re-keyed it with
`derive_variant_key` **without** passing one. gnomAD's variant id is `chrom-pos-ref-alt` and carries no
assembly, so a GRCh37 coordinate is a *well-formed request for a different variant*: the pass would have
written another variant's `allele_count`/`allele_number` under this module's key, with no error anywhere —
and minted a GRCh38 `ga4gh:VA.…` for the GRCh37 coordinate on the way, the identical false identity from a
third place. Now gated on `gnomad.FREQUENCY_GENOME_BUILD`, a named constant beside `covers_locus` because
one round produced three build confusions, with the skipped rows reported in one counted line naming the
build. Third rule earned: **anything calling `derive_variant_key`/`derive_vrs_allele_id` on a row must pass
that row's `build`** — the default is GRCh38 and it does not complain.

**The sweep: three more instances, and a check so there is no fourth round.** Having found the same
mistake four times, the remaining question was whether the list was complete. It was not.
`derive_variant_key` mints a VRS id **only** when handed a single `alts` — an rsID short-circuits first,
and no-`alts`/multi-allelic cells fall through to a coordinate key that never touches the build — so the
whole exposure is enumerable: *calls that pass one allele and omit `build=`*. Auditing that set found:

- **The reverse-emitted `resolution.csv` keys**, i.e. an incomplete first fix. Threading the build into
  the `genome_build` *column* was not enough: the same function derives `variant_key` from
  `(chrom, start, ref, alts)`, so a GRCh37 module got rows reading
  `ga4gh:VA.TWxWV6Sk…,…,GRCh37` — a GRCh38 allele identity beside a cell saying GRCh37, in one row. And
  since `resolve_from_table` joins on `variant_key`, the table silently matched nothing on recompile.
  `_write_variants_csv`'s dedupe key had the same gap (it mis-groups rather than mislabels).
- **`enrich()` never re-stamped `variants.csv`.** `_restamp_for_build` was wired into the compiler's two
  load sites and there is a **third**: the enricher loads the same file. So `enrich` wrote a
  `resolution.csv` keyed by GRCh38 VAs for a module the compiler keys by coordinate — a resolution table
  that could not join to the module it was produced for.
- **`_subject_of_variant`'s fallback**, threaded rather than left on the default.

Two call sites are exempt and say why: `VariantRow._freeze_identity` (a model validator with no module
in scope — it writes a *stored field*, which is precisely what `_restamp_for_build` corrects afterwards)
and `HeteroplasmyRow.variant_key`, which has no stored field to correct and is now **RM36**. Also
removed: `VariantRow.authored_key`, a dead, undocumented, build-blind third copy of the identity rule
that no caller in the workspace used.

`compiler/tests/test_build_call_sites.py` walks the AST of all three packages and fails on a call that
supplies an allele without supplying a build, with the exemptions listed in the test and each one checked
to still exist. It is a static check on purpose: the behavioural tests cover the paths we know about, and
what this catches is the *next* one somebody adds. It found the last two of the three above on its first
run.

**RM36, filed and then closed: the build is injected at load, not authored.** The sweep's one
leftover was `HeteroplasmyRow.variant_key`, a *property* that mints a VA and has no module in scope —
so unlike `VariantRow.variant_key` there is no stored field for `_restamp_for_build` to correct
afterwards. One locus on a GRCh37 module therefore carried two identities, a coordinate key from
`variants.csv` and a GRCh38 VA from `heteroplasmy.csv`.

Three repairs were considered and all three answer the wrong question — they ask *where should the build
be stated*, when it is already stated correctly, once, in `module_spec.yaml`. Per-row is overkill for a
module-wide property; **per-CSV (a "service row") is worse**, because two files could then disagree about
one fact, a data table would carry a non-data row (P5), an author copying rows between files would drop
it silently, and it would *still* not reach the model — a loader parsing such a row already knows the
build from the yaml it just read. So the row is **told**, not asked to **hold**:
`AuthoredModel._genome_build` is a `PrivateAttr` that `_load_csv_rows` sets on every row it builds.
Private, so it is absent from `model_fields` and `model_dump()` — not a column, no CSV, no parquet, no
digest move — and `extra="forbid"` still rejects an author who tries to write one. `PrivateAttr` behind
a read-only property was already the house idiom (`ModuleInfo._version_coerced_from`), so this adds no
new mechanism.

**`content_signature` was not "build-independent", and now says so.** The docstring's claim was true of
the *reference used to resolve* and false of the **declared assembly**, and conflating them meant the
content-dedup key hashed two modules describing loci 228 bp apart as identical content — reachable by
"lifting over" a GRCh37 panel through the yaml without touching the coordinates, at which point a
registry calls the result the same module. `genome_build` now feeds the hash **only when it is not the
default**, which is the same omit-the-default normalization already applied to an unset optional column
rather than an exception to it. That keeps it targeted: every GRCh38 module — every module published to
date — keeps its signature byte for byte, so `find_versions_by_content` still links a 0.4 module to its
own 0.5 recompile, and only the modules that were being misidentified move. Verified across all eleven
reference examples: ten unchanged on all three signatures, `grch37_build`'s `content_signature` changed
and its `artifact.digest` did not.

**`validate` reported `valid` for modules `compile` then refused.** Both loops in `validate_spec` iterate
`_TABLE_KINDS`, and `resolution.csv` plus the four fact sidecars are `_FACT_TABLES` — a tuple it never
touched, though `compile_module` refuses on a bad row in any of them. The `create-module` skill's step 6
puts `validate`
immediately before `compile`, so it is the author's pre-flight, and a green pre-flight followed by a refusal
sends them hunting a change they did not make. Worst case, and the one that shipped: the **licence gate**
reads `sources.csv` and nothing else, so a module drafted entirely from a no-sale source with no
`declared_use` validated clean and refused to compile. `validate` now runs the row-level checks on all five
injected tables plus the gate — all of them pure computation over injected bytes, needing no output
directory. The cross-checks that compare a sidecar against resolved rows stay in `compile`, where the rows
exist; this is about the error channel agreeing.

**A YAML syntax error came out as a traceback.** `_load_yaml` parsed outside its own `try`, so an unclosed
bracket — the likeliest mistake in a hand-written file — killed `validate` with
`yaml.parser.ParserError` instead of locating it, for the one command whose job is to report problems
legibly. pyyaml's message already names line and column, so it is kept and merely labelled. A YAML scalar or
list now reports "must be a mapping of top-level keys" rather than a pydantic message about input types.

**A warning wall, and a false label inside it.** `resolve_from_table` emitted
`Position {variant_key}: no rsid found in resolution table` once per row — 26 of `pathogenic_clinvar`'s 37
warnings, burying nine expansion findings and a duplicate-citation error. And `variant_key` is a
`ga4gh:VA.…` digest for a resolved substitution, so a third of those lines announced a content-addressed
identity as a position, giving the author nothing to look up. Now one counted line naming real coordinates
(`11:5226931 TGCCCAGG>T`), with the tail counted rather than listed: 37 warnings → 11. The deprecated DuckDB
resolver's similar message was checked and is **correct** — its key is built without `alts`, so it really is
a position.

**Tests.** `compiler/tests/test_reference_examples_roundtrip.py` sweeps **every** reference example for the
fixed point on all three signatures, by discovery rather than a list, plus compile-idempotency and
build-survival — the sweep that did not exist, which is why the reverse bug survived. It includes a guard
that the corpus spans more than one build, since a uniform corpus cannot catch a hardcoded one. Also
`test_build_roundtrip.py` (which keeps the old behaviour as a demonstration, passing
`genome_build="GRCh38"` explicitly), `test_validate_agrees_with_compile.py`, and
`enricher/tests/test_build_awareness.py`. Every one was run against a detached worktree at the prior commit
first: 7 of 10, 3 of 6, and 2 of 2 respectively fail there.

**Docs.** The root `README` still described a **two**-package workspace and listed the compiler's 0.4
dependency set (`duckdb`, `platformdirs`, `python-dotenv`) — `just-dna-enricher` was absent from the table
that is a reader's first contact with the repo. `compiler/README` headlined the deprecated
`resolve_with_ensembl=` DuckDB path and never mentioned `resolution.csv`. **CONSTITUTION Goal 2 said the
compiler adds duckdb**, which has been false since the 0.5 amendment removed it; the amendment section now
records that removal explicitly, as the tightening it is. `REFERENCE_EXAMPLES.md` claimed "three examples
are real, compiled modules" when there are eleven — replaced with a pointer to the directory rather than a
count to keep in sync.

**Checked and found sound**, so nobody re-audits them: tier import purity (no `duckdb`/`httpx`/`ga4gh` leaks
into format or compiler); a clean-venv `pip install just-dna-compiler` compiling five real examples; every
enricher module importing on a core (non-`[dev]`) install; all three wheels+sdists building; every CLI
subcommand on both CLIs registering and `--help`-ing; the reverse-side `fieldnames` lists matching
`authored_field_names` for `VariantRow`/`StudyRow` exactly (`ResolutionRow`'s omissions are the documented
provenance columns); `RM_TOC` covering all 35 items; and a module carrying **all twelve** table kinds at
once — 14 parquets, a shape no example or test had built — round-tripping to a fixed point.

## 2026-08-06 — `draft-panel`: an undecided clinical call is a second stub, not a dropped row

Both defects that building `par_boundary` surfaced, and the first turned out to be losing data rather than
just reporting badly.

**`--clin-sig uncertain_significance` drafted nothing.** Every row was refused with a raw
`state: Field required` — one identical line per row, 26 of them for a two-gene panel, naming no rsID and
giving no reason an author could act on. Three things were wrong and only one was the message:

- **The row was thrown away.** `_STATE_BY_CLIN_SIG` folds only the four decided calls, and that decision is
  right: `VALID_STATES` has no member meaning "undecided", so `neutral` would assert the variant is benign
  and `risk` a direction the submitters declined. But `state` is *required*, so a correct refusal to guess
  became a silent drop of the conclusion, phenotype, `clin_sig` and citations already assembled for the row.
  It is now **stubbed like `genotype`** — the machinery `PartialRow` exists for, since this is the same
  shape: the source did not say, and only a human can. XG at 1★ now drafts 26 rows where it drafted 0, and
  the placeholder guard names both columns (`unreplaced template placeholder … genotype, state`).
- **The explanation is one line per clinical *call*,** not per row, since the answer is identical for every
  row carrying it, and it says why no `VALID_STATES` member fits rather than quoting pydantic.
- **`_refusal_summary` is the generic net**, grouping whatever still fails by reason with a count and a
  capped list of affected rows. A cause the provider can *diagnose* should be caught before validation and
  explained in its own words; a raw validation message reaching the author as the whole diagnosis is a
  misdiagnosis, not a report. This is the fifth time this provider family has needed warning aggregation.

**A third defect fell out while fixing it:** `_genotype_worklist` was handed every candidate record rather
than the rows that landed, so a "3 row(s) carry a placeholder" header was followed by a 27-line worklist
naming rows that had been refused or were already present. A worklist naming work that does not exist is
worse than no worklist; it now covers exactly `report.added`, and a re-run that adds nothing emits none.

**And the run summary no longer adds rows across tables.** It printed `added 7 row(s)` where the per-file
lines correctly said `variants.csv: 3 added` and `studies.csv: 4 added` — a number matching neither file.
The CLI reports per table; `ClinVarDraftResult.added` already warned against the bare total in its own
docstring, and `added_for` was already there.

## 2026-08-04 — RM32: a pseudoautosomal locus is one place, and the sources already picked which contig

The last open dogfooding item from 2026-08-03, held back because it was a *question* rather than a defect:
a PAR variant maps to both X and Y, so the one-to-many expansion emitted two rows per finding — 20 rows for
10 findings in `reference_examples/shox_par1/`, all inside `artifact.digest`, while standard GRCh38 analysis
sets hard-mask the Y PAR so the Y rows could match nothing. The entry named its opening probe. **The probe
came back negative and that is what settled it:** the ClinGen Allele Registry mints **two** CA ids for one
PAR base (`CA254919`/`CA254920` for `rs137852556`; `CA10330023`/`CA2467802563` for `rs746801054`), so
`ResolutionRow.caid` cannot carry a place identity and no upstream mints one.

What the probing found instead is that **every annotation source has already chosen a spelling, and it is
X**: ClinVar holds no variant in either PAR on Y (0 of 677 Y records; all 1,675 records across
SHOX/CSF2RA/ASMT/CD99/XG/SPRY3/IL9R/VAMP7 are on X), gnomAD v4 excludes the Y PAR from its callset
(`region(chrom:"X", 640000-641500)` → 880 variants; the same interval on Y → 0), and the Registry's Y record
is a bare dbSNP cross-reference. Only Ensembl/dbSNP reports both, and it is the link that manufactures the
Y row. So the objection that had parked an enricher PAR policy — that it "encodes the consumer's analysis
set into the module" — does not hold: selecting X records the **sources' own convention**, which is what P2
makes the enricher the only tier allowed to hold.

- **`vrs.par_partner(chrom, start, *, build)`** — format tier, stdlib, three-valued, beside
  `in_pseudoautosomal_region`. Maps a PAR locus to its spelling on the other contig by index-matched offset:
  PAR1 at offset 0, PAR2 at 98,813,480. **PAR2 is why this is arithmetic and not an equality** — a shortcut
  comparing "the same base on X and Y" would have passed SHOX and silently failed SPRY3. A test pins the
  equal-length property over `PAR_GRCh38` itself, so a future build whose intervals do not pair cannot
  corrupt a selection quietly. Public and dependency-free, like `alleles.parsimony_reduce`.
- **`enrich` keeps the X spelling and reports the twin** (`select_par_representative`); `--keep-par-twin`
  records both for an unmasked reference. It **selects, it does not repair** — same contract as the
  allele-aware `hosting_verdict` filter beside it — and it will not fuse on geometry alone: a Y locus is
  dropped only when its partner position carries the same `ref`/`alts`, because partner coordinates say
  "same place", not "same variant". Reported once with a count, and surfaced on `EnrichmentResult` and in
  the CLI, since a selection nobody can see is indistinguishable from a silent repair.
- **The verdict is per locus, and a real gene forces that.** **XG** runs out of PAR1 (ends 2,781,479) and
  **SPRY3** runs into PAR2 (starts 155,701,383), so any gene- or module-scoped policy is wrong for half of
  either. New `reference_examples/par_boundary/` is that case end to end: one run, one PAR2 locus selected,
  two XG loci past the boundary untouched, and a `compile → reverse → compile` fixed point on all three
  signatures — which is *why* the flag is legal here and would be charter-illegal on the compiler (P7).
- **The compiler now says which kind of "many" an expansion is** (`resolution._expansion_warning`). A
  paralog and a PAR pair produced the same count for opposite reasons, and the generic "a consumer can
  count them" told a SHOX author to count ten findings as twenty. It describes only; the row-set decision
  stays in injected data.
- **A false absence in `frequencies.csv`, found on the way.** The pass recorded `status="not_found"` for any
  locus gnomAD returned nothing for, commenting that the row was a **fact** — "gnomAD was asked and does not
  have this allele". False for a Y-PAR locus, so a SHOX frequency run would have written ten absences nobody
  established. Fixed with a third vocabulary member `not_covered` (`VALID_FREQUENCY_STATUS`; and
  `FrequencyRow.status` gained the validator it never had — it was free text on a fact table), the coverage
  rule in `gnomad.covers_locus` where a source convention belongs, and such a locus is no longer queried at
  all. `not_covered` rather than `unchecked`, which is this codebase's word for a question never put. It is
  deliberately outside the `strict` gate: a locus gnomAD cannot cover is perfectly reproducible, and
  refusing would make a PAR module uncompilable for a reason no authored edit could fix.

**Digest impact, spent inside the unpublished window on purpose:** `shox_par1` goes from 20 rows to 10 with
every other cell byte-identical, and its compile is now silent for the first time. `content_signature` did
not move, which is a clean demonstration of its documented pre-resolution independence. The **multi-build**
half remains RM15's — `par_partner` withholds on any build but GRCh38.

Two things checked and found harmless, recorded so they are not re-flagged: `studies.csv` is rsID-keyed, so
both expanded rows always inherited the citation; and `_check_contig_ploidy` branches only on
`chrom in {MT, Y}`, so selecting X makes it quiet rather than wrong — it stays for hand-authored and
`--keep-par-twin` modules.

Building `par_boundary` also surfaced two **diagnosis** defects unrelated to PAR, fixed in the entry above
this one.

## 2026-08-04 — `draft-panel` finds its own snapshot, so the published citations reach an author

`draft_gene_panel(spec_dir, genes, *, snapshot: Path, …)` **required** the snapshot, with no resolution
and no provisioning — the third instance of the same gap as `ensure_constraint_snapshot` having no caller.
So the published snapshot could not reach an author at all: they had to build 4.4M records from a 200 MB
VCF, or already know the cache path. That mattered most for the **citations**, which are what make a
drafted panel compilable (`studies.csv` is mandatory, the VCF carries no PMIDs) and which had just started
travelling with the published snapshot.

`snapshot` is now optional and `_resolve_snapshot` runs the ladder `enrich()` uses: an explicit path is
taken as given (the inject-only escape hatch, and what an air-gapped run passes), else the cache
locations, else the published snapshot is downloaded unless `--offline`. No snapshot with `--offline`
**raises** rather than drafting nothing, because an empty draft would read as "ClinVar has nothing for
this gene". A provisioning failure raises with the reason attached, not a bare "not found".

Verified from a genuinely empty cache: `draft-panel --gene HFE` provisioned `data/` + `citations/` +
`release.json` and drafted 12 variant rows with **33 grounded study rows carrying real PMIDs**, then
refused to compile on the genotype placeholders — the designed state, not a failure. The module docstring
claimed "Inject-only — `snapshot` is a path this function reads, never downloads", which is exactly the
kind of claim this repo fixes rather than leaves: the *compiler* is inject-only, this is the network tier.

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
with no authored edit. *(**20** was the count while both PAR contigs were recorded. RM32 later reduced the
module to 10 rows by keeping only the X spelling; the resolution of the indel is unaffected.)*

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

## 2026-08-03 — 0.5.0: a GRCh37 module minted GRCh38 identities, silently

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

## 2026-08-03 — 0.5.0: dogfooding mitochondrial heteroplasmy — one blocker fixed, one proved unfixable

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

## 2026-08-03 — 0.5.0: dogfooding CYP2D6, the hard PGx case — and a defect in a check shipped hours earlier

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

## 2026-08-03 — 0.5.0: dogfooding a pseudoautosomal module — two fixes, three questions

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
look undecidable turned out to be wrong. RM32 was deferred to its own run and **shipped on 2026-08-04** —
see the entry at the top — where the same thing happened a third time: the probe this entry was waiting on
refuted the direction it called most promising.)*

- **RM31** — indel spellings. A reference-free parsimony trim fixes this pair but cannot left-align
  inside a repeat; a reference-backed one can only run in the enricher, and `genotype_fits` is shared
  with the compiler, which by charter holds no reference.
- **RM32** — nine of ten SHOX variants map to both contigs, so 10 findings became 19 rows, all inside
  `artifact.digest`, and standard GRCh38 analysis sets hard-mask the Y PAR so those rows can never
  match. Collapsing them would contradict VRS identity (X and Y are different refget sequences), and
  the expansion is correct for the paralog case it was built for. *(**19** is right for this moment and
  should not be "corrected" to the 20 the later entries state: the tenth variant was still resolving to
  `not_found` until RM31 landed hours later. Closed on 2026-08-04 — not by collapsing, which stayed
  rejected for exactly the reason given here, but by recording the X spelling every annotation source
  already uses.)*
- **RM33** — `resolution.csv`'s `source` names *which link answered*; `sources.csv`'s names *a
  licensed source*. Two vocabularies under one name, compared by string equality, which is why every
  enriched module warns that `ensembl-rest` has no terms. Writing a row per link would make
  `ensembl-rest` and `ensembl-graphql` two sources with identical terms; teaching the compiler a
  link→source map would give it a source convention, which P2's 0.5 tightening removed on purpose.

## 2026-08-03 — 0.5.0: CLI/API parity — signing was never CLI-complete

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

## 2026-08-03 — 0.5.0: RM28's cis/trans case, closed by a check rather than a grammar

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

## 2026-08-03 — 0.5.0: RM29 cofactors, and a refusal dissolved rather than resolved

Three optional columns carrying single-subject cofactors with **no predicate language at all** —
because a row's columns already conjoin, which is the whole reason RM29 was ever separable from RM28.
Taken then because the digest window was still open: new columns on an existing parquet move every
module's digest, and 0.5 was unpublished. Nothing in the repo pins a digest, so there was nothing to
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

## 2026-08-03 — 0.5.0: the ACMG SF cross-check, and what a "simple scrape" actually cost

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

## 2026-08-03 — 0.5.0: delegated insertion, partial rows, and RM26's last provider

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
later cross-table check turned the workaround into a dead end: `*4` in one table and `e4` in another
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
and ClinGen's FTP publishes no secondary-findings file. A guarded scrape is possible and is recorded as follow-up work
rather than rushed — a hand-transcribed gene list in the enricher is the un-injected-reference
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

## 2026-07-23 — 0.5.0 — source-independent resolution table

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
