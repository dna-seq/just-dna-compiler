# Consumer suggestions — history

Answered items from [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md). An item moves here once it
carries a `**Status —**` reply, so the live document holds only what is still unanswered — the same
split as [ROADMAP.md](ROADMAP.md) / [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md), for the same reason. The
inbox only grows, and eleven unanswered entries were invisible inside 6,000 words of answered ones,
which is the problem [CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md) exists to solve.

**The consumer's prose is moved byte-for-byte, never rewritten** — it is the report, not the
resolution. A reply travels with the item it answers, and a group whose items split across the two
files keeps its dateline in both.

One consequence is visible below: the round-1 thread `CONSUMER_FIELD_NOTES.md` was **removed on
2026-08-12** (a second inbox the ledger could not read — its two undelivered asks are S27/S28, and the
thread itself is in git history at `53f9260`), and a reporter's own preamble links to it. That link is
left dangling **on purpose**: rewriting it would edit evidence to tidy a reference, which is the one
thing this file does not do.

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
- **S24** nothing checks a variant is on its named gene's chromosome — shipped 0.5.4
- **S25** the manifest attests a logo but not a readme — in tree, lands 0.6.0
- **S26** the derived-fact CSVs are attested nowhere — in tree 0.6.0; layout RM49
- **S27** accepted `effect_allele` liftover caveat unwritten — docs 0.5.4
- **S28** accepted consumer join contract unwritten — docs 0.5.4
- **S29** `annotations.parquet` states no joinable key — RM80, 0.6.0
- **S30** one artifact spells a genotype two ways — leaf 0.6.0; artifact RM81
- **S31** no manifest field says a PGx table joins by position — 0.6.0
- **S32** nothing reports a site's missing genotypes — 0.6.0; callset half deflected
- **S33** an expansion's other rows look authored — 0.6.0; row marker RM87
- **S34** brief promised uninstallable fields — docs fixed; §4 RM84
- **S35** answers RM84+RM89; publisher dropped most of the artifact — 0.6.0
- **S36** `weight` declares no scale — 0.6.0; RM90, RM91, RM92
- **S37** passes leak the client's error type — accepted, RM101; 6 sites
- **S38** subclass made `except` order matter — docs fixed; AST guard

**Keep this list one line per item.** It is a contents list, not a second copy of the replies: the
detail belongs in each section's `**Status —**` paragraph, where it cannot drift out of step with the
answer it describes. Append a line when an item is archived; ids are never reused.

---

**S1–S24, S27 and S28 — everything answered in the 0.5 line — moved to
[CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md](history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md)** on 2026-08-17,
when this file passed 3,300 lines. This one holds what the 0.6 line answered. The contents list above
stays whole and covers both halves, because splitting an index is how an item stops being findable.

---

# Field notes from just-dna-registry — publishing a module's prose, 2026-08-12

## S25 — the manifest can carry a module's logo but not its prose, so a readme reaches no downstream reader

**Status — accepted as asked, shipped in the tree; it lands in 0.6.0.** `readme: FileEntry | None` is
on `ModuleManifest`, mirroring `logo` in every respect you named, including exclusion from
`artifact.digest` *and* `content_signature`. Reproduced first: no field existed, and `README.md` was
the headline example in the compiler's own "unknown files are tolerated" message, so the bytes really
did stop at whatever the registry chose to keep.

What ships: the compiler discovers a readme beside the spec, copies it into the module dir and hashes
it (`manifest.README_CANDIDATES` — `README.md` first, then the lowercase stem and `md`/`rst`/`txt` in a
fixed order, so a directory with two readmes cannot resolve by luck); `verify_manifest(check_readme=
True)` and `just-dna-compiler verify --check-readme` re-hash it, which is what makes your `/files/{path}`
guard satisfiable rather than something to weaken. **You were right to keep that guard** — the fix was
the missing attestation, not the refusal to serve unhashed bytes.

Your two rejections are both upheld, and one of them shaped the tests. Prose stays out of
`artifact.files` for exactly the reason you gave, and since that argument only holds if it also stays
out of `content_signature`, the tests compute **both** identities rather than the digest alone, plus a
case that rewrites a readme and asserts only its own hash moves. Measured on six real reference
examples against a baseline worktree: `artifact.digest`, `content_signature` and
`resolution_signature` byte-identical, each now attesting its `README.md`. `display` stays uninlined
for your reason too.

One thing you could not have seen from outside: the enricher's HuggingFace publisher allowlisted
`logo.png`/`logo.jpg` and no readme, so the field alone would have attested a file the repo did not
carry — the same silent shape as a snapshot sidecar we once built and never published. It now imports
the same candidate list the compiler discovers from.

**What to do now.** Nothing on your side is wrong: keep the catalog projection and the amend route,
and once 0.6.0 is cut, read `manifest.readme` as the source of truth and let the DB copy be a
projection again. The version is **not** bumped in the tree — a new optional manifest field is minor
under Principle 3, and cutting a release is the maintainer's call, so `0.6.0` names the release this
will ship in rather than a state you can install today. Your test that pins the limitation should flip
to asserting the field; it is the one that will tell you the moment it is real.
<!-- triaged: 0.6.0 · sha ece792dfe14f -->

**Filed by:** `just-dna-registry` (relaying a case from `just-module-creator`) · **Found:** 2026-08-12,
implementing module readmes · **Versions:** format 0.5.0 / compiler 0.5.3

**What we ran.** A publisher ships a `README.md` beside `module_spec.yaml`. The registry stores every
non-parquet spec file under the version key, so the bytes are there on disk. We then tried to serve
that file and to include it in the module tarball, and could do neither — both of those paths are
defined over **what the manifest attests**, and `ModuleManifest` has no field for a readme.

**Why this is a manifest question rather than a registry one.** `logo` is the exact precedent, and it
is already yours: `logo: FileEntry | None`, out of `artifact.digest`, amendable without a version
bump. Because that field exists, a logo can be listed, hashed, fetched, verified and swapped. A
readme has all the same properties — prose *about* the module, not part of its content identity — and
none of the same machinery, purely because there is no field. The asymmetry is not one any consumer
can fix on its own: a registry can keep the text in its own database (we now do), but then the
manifest has stopped being the source of truth for something a reader wants, and anyone consuming
manifests directly — an installer, a mirror, a second registry — gets nothing at all.

**What we would ask for:** `readme: FileEntry | None` on `ModuleManifest`, mirroring `logo` in every
respect, including its exclusion from `artifact.digest` and from `content_signature`.

**The arguments against our own option, since they are the useful part:**

- **Inline the text in `display` instead.** Rejected: a readme is unbounded prose — the case that
  motivated this is an 11-row module whose README is longer than its data — and `display` is inlined
  into every card and listing we serve. A `FileEntry` keeps the manifest a manifest.
- **Just put `README.md` in `artifact.files`.** Rejected, and this is the one that would actively
  hurt: it would enter `artifact.digest`, so fixing a typo in a caveat would mint a new content
  identity. On an immutable registry that means a corrected sentence costs a version number, and the
  corrected module then collides with its own predecessor under the name-independent duplicate check.
  Prose must stay out of the digest, which is exactly the property `logo` already has.
- **Leave it to each registry.** This is what we shipped, and we are not comfortable with it: it makes
  our catalog DB carry a fact no manifest records, which is the one shape our own guidelines say a
  projection must never have.

**What we did meanwhile (registry 0.14.0).** Publish reads `README.md` from the spec and projects it
onto the module card; `POST .../versions/{v}/readme` amends it without a version bump. The bytes are
stored, but our `/files/{path}` route and our tarball builder both refuse to serve what the manifest
does not list, and we deliberately did **not** weaken that guard to paper over the missing field — a
file we serve without a recorded hash is a file nobody can verify. So today the prose reaches a
catalog card and stops there. A test in our suite pins that limitation rather than asserting it as
desirable, so whoever lands this field on your side will find the test that documents it.

**Naming the case, since we are relaying:** `just-module-creator` published an 11-row module of
explicitly *candidate* findings — most from a preprint, one association not significant — and the
README saying so is the single most important artefact for a reader deciding whether to install it.
That is the thing that currently cannot travel with the module.

# Field notes from just-dna-registry — a readable spec layout, 2026-08-12

## S26 — the derived-fact CSVs are attested nowhere, so the enricher's own tables cannot travel with a module

**Status — first half accepted and shipped in the tree (lands in 0.6.0); second half filed as
[RM49](history/ROADMAP_HISTORY_PRE_0_6.md#rm49--a-spec-directory-is-flat-so-a-legible-derived-layout-is-one-the-compiler-refuses).**
Reproduced end to end: compiling `reference_examples/pathogenic_clinvar` leaves `resolution.csv` and
`literature.csv` beside the spec with `literature.parquet` in the artifact and no byte hash for either
CSV anywhere in the manifest. Your reading of why is exactly right, including that `_INPUT_FILES`
excludes them deliberately.

`derived: list[FileEntry]` is on `ModuleManifest`. It follows `logs` where you said it should —
optional, absent-is-not-a-failure, out of `artifact.digest` and `content_signature` — and departs from
it in one respect worth flagging: entries are hashed **where the files live, beside the spec**, and not
copied into the module dir. Copying would ship each table twice, since a sidecar CSV and its parquet are
the same content in two encodings, and a panel's `frequencies.csv` is not small. That makes `derived[]`
`inputs[]`' sibling in locality and `logs`' in optionality, which is why
`verify_manifest(check_derived=True)` *skips* a missing entry where `check_inputs` raises. Your
`download(layout=...)` already stores spec files, so this should need nothing new on your side.

**One thing to hold onto, because your test is the one that will catch it.** There are now two hashes
over each of these files answering different questions, and the byte hash is the *weaker* one: a
reverse→recompile cycle, or an enricher re-run against a fresher gnomAD, changes those bytes while the
facts are identical. The fact hashes (`compilation.resolution_signature`, and each sidecar block's
`signature`) remain the identity; `derived[]` is for transport and verification-in-flight only. Reading
it as identity would make a legitimate re-emission look like tampering. A test pins the pair by
rewriting a sidecar so the facts hold and the bytes move, asserting the byte hash changes and the fact
signature does not — your `SIGNATURE_INPUTS`-disjointness test is the same instinct from the other side,
and it is the right one.

**The `derived/` layout is filed rather than built, and your own report contains the reason.** Because
you flatten on upload, the two halves look equally mechanical from outside; from in here they are not.
`spec_dir / "resolution.csv"` is resolved in eight places across two packages — `validate_spec`,
`compile_module`'s resolution and fact loops, and four enricher passes — so a fallback in the compiler
alone yields a module that compiles from `derived/` and silently re-enriches to the root. That is the
decisive case: run `enrich` on a downloaded split module and it writes `resolution.csv` beside the spec,
so the module now holds both copies, reached by following the documented workflow. Two copies of a
fact-hashed, human-overridable table are two legitimate claims, so no newest-wins or merge rule can
resolve it without discarding a curator's override. RM49 records the shape a fix probably takes (one
constant in the format tier, prefer-root-then-fall-back, an error naming both paths on collision, the
enricher writing beside whichever copy it read) and refuses three tempting repairs with reasons —
notably "search any subdirectory", which would blind the mistyped-table-name guard S16 exists for.

**What to do now.** Keep the transport-only layout; it is correct until RM49 lands, and nothing about it
was wrong. Once 0.6.0 is cut, read `manifest.derived` for serving and verification and keep using the
fact signatures for identity. As with S25, the version is **not** bumped in the tree — a new optional
manifest field is minor under Principle 3 and cutting a release is the maintainer's call, so `0.6.0`
names the release both halves of this will ship in rather than something installable today.
<!-- triaged: 0.6.0 · sha cade5b4fbffa -->

**Filed by:** `just-dna-registry` · **Found:** 2026-08-12, giving a spec directory a readable layout ·
**Versions:** format 0.5.4 / compiler 0.5.4 / enricher 0.5.4

**What we ran.** A publisher asked, reasonably, which files in a spec directory are theirs. A module
compiled by our server holds `module_spec.yaml`, `variants.csv` and `studies.csv` that a human wrote,
and `resolution.csv`, `frequencies.csv`, `gene_metrics.csv`, `literature.csv` and `sources.csv` that
`just-dna-enricher` wrote — with `sources.csv` being genuinely both, the author's rows with the
enricher's merged in. Nothing in the directory listing says which is which. We added a `derived/`
subfolder convention for that (ours, transport-only: uploads are flattened before anything reads them,
downloads are split after verification) and then tried to make the download half actually contain the
derived tables. It cannot.

**What happens.** `ModuleManifest` has fields for `logs`, `logo`, `provenance` and `inputs`, and every
route we serve files through is defined over what the manifest attests, because serving a file with no
recorded hash is serving something nobody can verify. The derived CSVs are in none of those:
`_INPUT_FILES` deliberately excludes them (they are fact-hashed, not byte-hashed, which is right), and
only their *parquets* are in `_OUTPUT_FILES`. So the CSVs are stored on our side, reachable by nobody.
A consumer who wants to see **what the enricher actually decided** — which rsID resolved to which
coordinate, which frequency came from where, which source line justified a row — has to take the
parquet's word for it and cannot diff it against the table that produced it.

**What we would ask for:** `derived: list[FileEntry]` on `ModuleManifest`, mirroring `logs` in every
respect — optional, hashed, out of `artifact.digest` and out of `content_signature`. `logs` is the
precedent rather than `inputs`: like a run log, these files are *evidence about* a compile rather than
the authored data the identity is built from, and an absent one must not invalidate a module.

**Arguments against our own option, since that is the useful part:**

- **Put them in `inputs[]`.** Rejected, and it is the tempting wrong answer: `inputs[]` entries are
  raw-byte hashes, and these tables are fact-hashed precisely because they are multi-producer — the
  enricher, a human override and `reverse_module` all legitimately emit different bytes for the same
  content. A byte hash there would make a reverse→recompile cycle look like tampering.
- **Reuse `artifact.files[]`.** Rejected for the reason S25 rejected it for a readme: it enters
  `artifact.digest`, so re-running enrichment against a fresher gnomAD would mint a new content
  identity for unchanged authored data.
- **Leave it to each registry.** This is what we shipped, and it is the same shape we were
  uncomfortable with in S25: our storage holds a file the manifest does not know about, so a mirror,
  an installer or a second registry gets nothing.

**A second, smaller half, which is why our layout is transport-only.** The compiler discovers authored
tables at the spec root and only there, so the legible tree we hand a human is a tree
`just-dna-compiler compile` refuses — it has to be re-flattened first. We do that flattening on upload
and it works, but it means the folder can never be more than a presentation. If a `derived/`
subdirectory were honoured on input, a downloaded module would recompile where it sits. We are not
asking for a required layout, only a tolerated one.

**What we did meanwhile (registry 0.14.0).** `derived/` is accepted on upload from any subdirectory
and flattened; `download(layout="split")` re-splits after `verify_manifest` has passed;
`download(include_inputs=True)` was added because our own `/download` listed `artifact.files` only, so
until now a downloaded module did not even contain the authored CSVs. A test asserts that
`SIGNATURE_INPUTS` and the derived set are disjoint, so the convention cannot start moving content
identities by accident. The `derived/` folder is created only when something lands in it, which today
is nothing — that emptiness is this report.

# just-dna-lite, moving the annotating engine and report onto 0.5 (2026-08-16)

*Reported against 0.5.4. S29 arrived first and S30–S32 came out of the same migration two runs later —
one annotation of one WGS genome against twelve modules, read from three different angles — so the four
sit together here. All four are answered.*

## S29 — `annotations.parquet` is keyed by nothing a consumer can join on

**Status — fixed in 0.6.0 as [RM80](ROADMAP_HISTORY.md#rm80--annotationsparquet-had-no-column-for-the-thing-that-distinguishes-its-rows), 2026-08-16.** Your second
candidate, and your closing sentence is the one that decided it: the table could not state its own key,
so we made the key statable rather than picking a dedup rule for you.

`annotations.parquet` now carries **`genotype`**, and the dedup key is
`(variant_key, genotype, conclusion, negatives)`.

**Why not the first candidate.** Unique-per-`variant_key` is not reachable: a genuine poly-effect
variant is one locus carrying two annotations with different `conclusion`/`phenotype`/`category`, which
is why the table was re-keyed off bare `variant_key` in the first place. Your own ClinVar panels are the
same shape from the other side. So collapsing further would have to discard a real row eventually, and
the local dedup you are running is lossless only for as long as it happens to be.

**Why carrying the column was not enough on its own, and this is the part worth knowing.** Adding
`genotype` *without* putting it in the key would have been worse than the gap you reported. Two
genotypes sharing a conclusion (`C/T` and `T/T` both "carrier") collapse under the old key, so the
surviving row would name one genotype while silently standing for both — and a consumer filtering on it
would get a **wrong** answer where today it gets a missing one. Both halves shipped together.

With `genotype` in the key the dedup is provably a no-op: `(variant_key, genotype)` is `VariantRow`'s
own natural key and the compiler rejects duplicates on it. So the table is now **exactly one row per
authored variant row**, which is the property your join wants.

**On your `rs4977574` case.** Those three rows were surviving a key that already included
`conclusion` and `negatives`, so something in that pair separated them — but not anything a reader could
act on, which is the defect you are describing rather than a different one. `genotype` now makes the
distinction visible in the table instead of implied by it.

**What to change.** Drop the local dedup and join on `(variant_key, genotype)`; on the weights side the
genotype is stored as an allele list plus a `phased` bit, so rebuild the string the way `reverse` does
(phased → `|` in order, unphased → `/` alphabetically sorted). Your ×1.00 should hold without the
projection step. Older artifacts are unaffected — reverse now detects which of the three keyings an
artifact carries rather than assuming, and both legacy branches are preserved.

**Cost:** a parquet column is approximately free under the 2026-08-13 charter amendment (materialized,
derived, no human types one), which is what made this a minor rather than a deferral.
`content_signature` does not move; a recompile's `artifact.digest` does, for any module carrying
`variants.csv`.

<!-- triaged: 0.6.0 · sha b06fea9cf075 -->

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, while moving the annotating engine and
report onto the 0.5 contract.

**What we ran.** The report enriches a user's annotated variants with `gene`/`category`/`phenotype` by
joining `annotations.parquet` on `rsid` — a join written when annotations were one row per rsID. On 0.5
artifacts it fans out. Measured over our built corpus (`weights` left-joined to
`annotations.select(rsid, gene, category, phenotype)`):

| module | weights rows | annotations rows | joined | inflation |
|---|---|---|---|---|
| coronary | 81 | 77 | 231 | ×2.85 |
| lipidmetabolism | 45 | 41 | 123 | ×2.73 |
| vo2max | 39 | 28 | 84 | ×2.15 |
| longevitymap | 1039 | 528 | 1039 | ×1.00 |

**What we expected.** That `variant_key` would be the key, per the 0.5 note that annotations are keyed
by `variant_key` rather than collapsed per rsID. It is not unique either: coronary's 77 annotation rows
carry **27** distinct `variant_key`, and the three rows of `rs4977574` are byte-identical across every
column the table has — same `rsid`, same `variant_key`, same `gene`, same `conclusion`.

**What is actually happening.** The table has one row per authored *genotype* — coronary's `rs4977574`
is authored `A/A`, `A/G`, `G/G` — but carries no `genotype` column, so the distinguishing field is not
in the table. The rows are therefore not duplicates that a dedup would be discarding information to
remove; they are genuinely indistinguishable.

**What we did meanwhile.** Deduplicated the projection before joining, on `variant_key` where the
weights side has one. That restores exactly ×1.00 on all nine of our modules with zero unmatched rows —
including the three ClinVar gene panels, where an rsID maps to several genes and `variant_key` is the
only key that separates them (`rsid` dedup still inflates cardio ×1.12, cancer ×1.14, pathogenic ×1.08).

**Candidate fixes, and the argument against the first.** *Make the table unique per `variant_key`* is
what we do locally and it loses nothing today — but it is only lossless while the per-genotype rows stay
identical, and the table exists to carry per-variant facts that a curator might one day want to state
per genotype. *Add the `genotype` column* keeps that door open and makes the row count honest, at the
cost of a column on a table whose whole point is to be the variant-level one. We have no view on which
is right; what we would ask for either way is that the table state its own key, since a consumer
currently cannot derive it from the artifact.

## S30 — the 0.4 families store a genotype string, `weights` stores a list

**Status — accepted, split in two: the shared leaf shipped in 0.6.0, the artifact half is
[RM81](ROADMAP_1_0.md#rm81--one-artifact-spells-a-genotype-two-ways) and needs the major.** You asked
for the public leaf as a fallback and it is the better half of the request, so it is what shipped:
`just_dna_format.alleles.split_genotype` — format tier, stdlib, the `parsimony_reduce` precedent for
"the pure rule lives in the format and every reader calls it". Its contract is *a validated genotype
cell in, alleles in authored order out*, and the docstring says **never sorted** with your reason, not
a semantic one.

Reproduced, and it was worse than reported: there were **three** copies of that regex, not two.
`compiler._split_genotype` was one, `resolution.py` had its own for the hosting predicate, and yours
was the third. Both of ours now call the leaf, and a test asserts they are the same object — two
implementations that agree today do not fail when they drift, they stop matching, which is exactly the
failure you describe. Your deciding argument is pinned as
`split_genotype("G|A") == ["G","A"] != split_genotype("A|G")`, so a future edit that sorts breaks our
build rather than your match set. You were right to land on not sorting, and right about why: whatever
RM63 settles about what a pipe *means*, the compiler does not sort, so a reader that does is the one
introducing the second spelling.

**The narrower half is real and does not fit in a minor.** Splitting `pharm_variants.parquet.genotype`
is a **retype of a published column** — P3/P8 make that major-only precisely because it breaks a reader,
and you are that reader. RM43 is not a precedent for it: those were stamped columns that did not exist
before, which is the additive case. The tempting minor-legal repair — a parallel `genotype_alleles`
list column beside the string — is refused in the item, because it puts two spellings of one value in
one table (the desync shape `ResolutionRow.vrs_id` needed two guards for) and leaves the original
defect in place with a third spelling on top. So RM81 records the two candidate unifications (split
everywhere, or verbatim everywhere and every reader calls the leaf) and the argument each way; the
`reverse_module` cost you did not have to consider is written down there.

Nothing to do on your side: your normalization stays correct, and `split_genotype` is available to
replace it whenever you take a 0.6 dependency.
<!-- triaged: 0.6.0 · sha 0516f5706788 -->

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, same round as S29.

**What we ran.** Annotating a real WGS VCF with our `pharm_variants`-led `pharmgkb` module, joining on
`(rsid, genotype)`.

**What happened.**

```
SchemaError: datatypes of join keys don't match - `genotype`: list[str] on left
does not match `genotype`: str on right (and no other type was available to cast to)
```

`weights.parquet` splits `VariantRow.genotype` into `List(Utf8)`; `pharm_variants.parquet` is
materialized verbatim from its authored CSV and keeps the string (`"C/C"`). Both are documented and
neither is wrong, but a consumer joining either family to the same VCF meets two representations of one
concept, and the split is invisible until the join raises.

**What we did meanwhile.** Normalize the lead table's genotype to `List(Utf8)` before any join, mirroring
`just_dna_compiler.compiler._split_genotype`: split on `/` or `|`, drop empty fragments, **do not sort**.
After that `pharmgkb` annotates 63 and 45 rows on our two rsID-bearing samples rather than aborting the
run. Cheap, and we are not asking for it to be undone.

**Why we are reporting it anyway — we got it wrong twice, in opposite directions, from the prose.** Our
first version sorted the alleles, reasoning that with no phase-set column the order names no homolog. We
then reverted that after reading `AuthoredModel._validate_genotype`, which says phase encodes which
allele sits on which homolog. Re-reading PROPOSAL_0_6, **RM63 says that docstring claims more than the
format supports** and is being corrected to "phase recorded but unaddressable" — so our first reasoning
was closer to the truth than the docstring we abandoned it for. Neither round involved a failing run: no
module in our corpus carries a phased genotype, so nothing we could execute would have told us either
way.

We landed on **not sorting**, and the point of this report is that the deciding argument turned out not
to be the semantic one at all. Whichever way RM63 settles what a pipe *means*, the compiler's
`_split_genotype` does not sort, so `weights.parquet` holds authored order; a consumer that sorts the
0.4 families gives one artifact two spellings of a genotype and matches a phased row that a weights-led
module would not. Self-consistency decides it, and that is stable under RM63. The semantics we spent two
rounds on decide nothing here.

So the rule lives in three places that must agree — the validator's grammar, `_split_genotype`, and
every consumer that touches a 0.4 table — and the third is a re-derivation from prose that is currently
mid-correction. `_split_genotype` is private, so reimplementing it was the only route; a consumer that
reimplements it slightly wrong gets no error, just a quietly larger match set on phased data. A shared
public leaf — the genotype counterpart to `derive.direction_from_state`, the precedent for "the pure
rule lives in the format and every reader calls it" — would remove the class. Failing that, exporting
`_split_genotype` under a public name would do.

The narrower half is still worth fixing on its own: `weights.parquet` gets the split and the 0.4
families do not, so two tables in one artifact disagree about how a genotype is spelled. RM43 already
stamps `variant_key`/`authored_ident` onto `pharm_variants`, `haplotypes` and `heteroplasmy` in 0.6 —
splitting `genotype` on the same pass would make the whole artifact self-consistent.

## S31 — RM43 is built and unreleased, so a `pharm_variants` module still ships zero coordinates, and on an rsID-less genome that is zero annotations

**Status — the field you guessed at did not exist and now does: `manifest.compilation.positional_rows`
/ `positional_rows_placed`, shipped in 0.6.0.** You were right that `resolution_subjects` looks
adjacent and right that it is not the answer — it counts `variants.csv`, which your module has none
of. RM44's own entry recorded that the *positional* count "belongs with RM43", and RM43 then shipped
the fill without it, so until this the only published record of whether a PGx table joins to a VCF was
the warning sentence your registry substring-matches. Two counts, parts not a ratio, the
`vrs_alleles`/`vrs_alleles_identified` shape: complete is `positional_rows_placed == positional_rows`.
`pgx_slco1b1_simvastatin` now reports 9 of 9 while its `fully_resolved: true` still quantifies over
zero variant rows, which is the pair of readings a catalog needs side by side.

**The era question has a definite answer, and it is the reason both fields are nullable rather than
`0`.** `None` means *this compiler did not count*, which is exactly what every pre-0.6 manifest
honestly is; `0` means the module carries no positional table. Defaulting to `0` would have your 0.5
artifact report "no positional rows" while its parquet holds 1,482 — the vacuous-`fully_resolved`
failure re-made inside the field written to close it, so a test pins the distinction. Alongside that,
`compiler_version` is the discriminator that exists in manifests already published. COMPILER.md's
resolution section now carries the read-side rule, including the part that outlasts the release: a
published artifact does not move when a consumer installs 0.6, only when its maintainer recompiles
**and** republishes.

`UNJOINABLE_PHRASE` and its test **stay**, and the comment claiming RM44 would retire them is
corrected rather than deleted: manifests already on `just-dna-seq/annotators` carry neither new field,
so for those the sentence is still the whole record. Retiring it is a decision for after the corpus is
recompiled, not a consequence of the field existing.

The rest is outside the format and stays there. Republishing the corpus is a maintainer action we do
not control from here, and `trusted: false` is your registry's rendering of a true fact — the
counts give it something better to render than a warning's prose, but what a badge *says* is a
consumer contract (RM7). Your own bug — distinguishing "we could not test you" from "you carry none of
these" — reads right to us, and it is the same tri-state discipline this repo applies everywhere: an
unasked question is never a negative answer.
<!-- triaged: 0.6.0 · sha 84e0c4378987 -->

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, same round as S30 — the same module and
the same run, one layer down. **We know RM43 shipped this in the 0.6 tree**; this is the field cost of
it not being installable yet, plus one consequence we do not think RM43 alone closes.

**What we ran.** `annotate_and_report_job` over Anton Kulaga's public genome (Zenodo 18370498, CC-Zero,
DeepVariant 1.1.0, GRCh38, variant-only), 4,257,537 records after quality filtering, against all twelve
modules we discover — `pharmgkb` among them.

**What happened.** `pharmgkb` annotated **0 rows**, and the report told the reader "No annotated
variants found for this module."

The artifact we published under 0.5:

```
pharm_variants.parquet   1,482 rows, 147 distinct rsids
  chrom  null on 1,482 / 1,482
  start  null on 1,482 / 1,482
  ref    null on 1,482 / 1,482

resolution.csv           147 rows, status=resolved on 147 / 147
  rs1042713 → 5 / 148826877 / G / A,C  (+ two VRS ids)
```

So the compiler held a complete, resolved coordinate for **1,482 of 1,482 rows** and emitted an artifact
with none of them. That is RM43 exactly, and we are not re-reporting it as a defect — we are reporting
what it costs downstream, because the number is larger than "joins on rsid instead of position"
suggests.

**The part that is not just slower.** Our engine detects the null coordinates and downgrades the join
to `(rsid, genotype)`, which is the right fallback and works on our two rsID-bearing samples (63 and 45
rows, per S30). But this genome carries **0 rsIDs across all 4,257,537 records** — DeepVariant writes
`.` in `ID`, and so do most callers we see. So the fallback has nothing to key on, and a module whose
every row the compiler could place annotates nothing at all on a fully sequenced genome. Position was
not a faster route to the same answer here; it was the only route.

**What we did meanwhile.** Detect the all-null-coordinate case, downgrade to rsid, and — separately —
detect that the VCF carries no rsIDs at all and record *that* as the reason, so "we could not test you"
is distinguishable from "you carry none of these". The second half is ours to render and we had not
been rendering it; that part is our bug, now filed on our side.

**Why we are writing it up rather than just waiting for 0.6.** Two things outlast the release:

1. **The published corpus does not move when the compiler does.** Every module on
   `just-dna-seq/annotators` was compiled under 0.5, so a consumer installing 0.6 still meets
   coordinate-less `pharm_variants` artifacts until each one is recompiled *and* republished — two
   maintainer actions, in our case gated on a namespace token. A consumer cannot tell from the artifact
   which era it is holding except by looking for the nulls. If `manifest` already distinguishes this
   (we may simply be missing the field — RM44's `resolution_subjects` looks adjacent), a pointer in
   COMPILER.md's read-side section would save the next consumer the probe.

2. **`trusted: false` is the right verdict and an unhelpful one.** Registry 0.11.3 reads the 0.5.3
   unjoinability warning and publishes `pharmgkb` as `trusted: false`, which is correct. But the flag
   reads as a quality judgement on the curation, when the curation is fine and the artifact is merely
   missing a mechanical fill the compiler had in hand. Post-RM43 that resolves itself; pre-RM43 it means
   our best-curated PGx module is the one flagged least trustworthy.

**One argument against our own framing.** "Weld the coordinate in at compile time" is what P7 forbids
in general — `reverse_module` would read a materialized coordinate back as authored. RM43's answer
(stamped, `Field(exclude=True)`, rebuild the lookup from the positional parquets on reverse) is a
better shape than the one we would have proposed, and the `content_signature` consequence it documents
is a cost we had not considered. We raise the corpus half only because it survives the fix.

## S32 — hom-ref rows are correct data that our callset cannot supply, and we nearly filed them as dead weight

**Status — ask (1) shipped in 0.6.0; ask (2) was already true and we should have said where; the
callset question is deflected, and that is a routing decision rather than a deferral.**

**(1) The warning exists.** `_check_genotype_coverage` reports, per reason, the genotypes a site has no
row for — the reference homozygote, a heterozygote, a homozygous alternate — with a count of genotypes
*and* of sites, since one two-alternate locus can be missing two of them. It fires **only at a site the
module already annotates for two or more genotypes**, and that scope is the whole design: one genotype
at a site is a rule that fires on the call the author cares about, and `pathogenic_clinvar` is in that
shape at 326 of its 327 sites, so the wider version would put a line on nearly every module ever
drafted. Two or more is you having shown the genotype space is what you are describing. It warns in
both modes and never fails a compile — which genotypes to annotate is the curator's judgement.

Dogfooded on our own corpus before shipping, and it found three real instances there, which is the part
worth telling you: `grch37_build` and `hfe_hemochromatosis` state a carrier and a homozygote and no
reference homozygote, and `pathogenic_clinvar` states both HBB heterozygotes at 11:5225715 and neither
homozygote — so a subject homozygous for a pathogenic HBB allele matched nothing, in our flagship
example, for the same reason your 74 sites did. It never demands an alternate/alternate pair (RM35's
unsatisfiable-triangle lesson), it takes the reference allele from the row or from `resolution.csv` and
never guesses one, and sites whose genotypes are not diploid nucleotide pairs drop out on their own —
which is how MT and non-PAR Y stay out with no contig list.

**(2) `requires_callable` is populated, in three reference examples, and has been since 0.5.** Your
corpus does not carry it; ours does — `mt_common_deletion` and `mt_heteroplasmy` set
`requires_callable=true` with `callable_from=FORMAT/DP` on every row, and `shox_par1` sets the bare flag
on all ten. `pgx_slco1b1_simvastatin` cannot: the column is `VariantRow`-only, so no PGx table can state
it, which is filed as RM70 and is the gap your example choice happened to land on. So the round trip you
want to implement against has a target today, and the missing piece for the PGx half is named.

**(3) The callset question is not ours to answer, and your own framing had already reached that.**
Which annotation path works against a chosen data input — variant-only VCF, gVCF, array, joint-called
cohort — is the **annotator's** determination, not the format's, and the module cannot know it. So we
are not building the module-level "evaluate me against a callset that can express the reference
genotype" claim you named, and we are not warning on the *presence* of hom-ref rows either: your own
report is the argument, since those rows are correct and are what make a module work on array data.
Restoration and imputation both sit on your side of that line for the same reason, and your instinct to
rank them apart is the one this repo would apply too — one is deterministic given callability evidence
and the other is a probabilistic call, and a single rendering for both is what makes a manufactured
reassurance possible. What the format owes you is the row-level statement (`requires_callable` /
`callable_from`) and the honesty about what the table does *not* contain, which is ask (1).

Note the check needs no notion of reachability, exactly as you said — it fires on what the author wrote,
which is the only thing the compiler can see, and its message deliberately says "matches no row in this
module" rather than anything about a file.
<!-- triaged: 0.6.0 · sha 0e9a92d4c0f1 -->

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, same run as S31.

**What we ran.** The same twelve-module annotation of the same variant-only WGS genome.

**What happened.** `lactose_tolerance` — a small module of ours, 6 rows over 2 sites — matched **0
rows**, and the report said "No annotated variants found for this module."

It authors, for rs4988235 (2:135851076, `ref=G`, `alt=A`):

| genotype | weight | state | conclusion |
|---|---|---|---|
| `A/A` | 1.2 | protective | lactase persistence |
| `A/G` | 1.0 | protective | lactase persistence, dominant |
| **`G/G`** | **0.0** | **neutral** | **adult-type hypolactasia — possible lactose intolerance** |

There is **no record at 2:135851076 in the VCF at all**. Nearest calls are 180 bp before (135850896,
DP 22) and 1,576 bp after. A variant-only callset emits nothing where the sample matches the reference,
so the subject is almost certainly `G/G` — the module's own third row, the most common result worldwide
and the one a reader asking about lactose came for — and the pipeline is structurally unable to say so.

**It is not one small module.** Counting rows whose `genotype` equals `[ref, ref]`, straight out of
`weights.parquet`:

| module | hom-ref rows | of total |
|---|---:|---:|
| `pathogenic` | 2,727 | 617,001 |
| `cancer` | 1,296 | 139,254 |
| `cardio` | 539 | 115,060 |
| `longevitymap` | **193** | **1,039 (19%)** |
| `coronary` / `lipidmetabolism` / `vo2max` / `thrombophilia` | 27 / 15 / 13 / 8 | **one row in three** |

The four hand-curated modules author all three genotypes at every site.

**But "unreachable" is the wrong word, and getting it wrong is the point of this report.** Whether a
hom-ref row can match is a property of the *callset*, not of the module and not of the format:

| callset | hom-ref row |
|---|---|
| variant-only VCF (this run) | no record at the site — needs restoration |
| gVCF with reference blocks | **record exists, matches today** |
| microarray / direct-to-consumer | every probed site is genotyped, hom-ref included — **matches today** |
| joint-called cohort VCF | site present iff *someone* varied — partially reachable, and which part is not a fact about this sample |

The gVCF row is not a hypothetical. Thirteen `GT=0/0` records survive our own quality filter on this
genome, and `_compute_genotype_expr` turns every one of them into exactly `[ref, ref]`:

```
1  106517189  CATAT  C  0/0  ["CATAT","CATAT"]  PASS
2  36033272   A      G  0/0  ["A","A"]          PASS
```

13 of 13. So the join mechanism already works end to end; what hid it on this genome is one line of our
own config (`pass_filters: ["PASS","."]`, which drops `FILTER=RefCall`), plus the fact that this
particular file is variant-only. We had written those rows off as dead weight in the artifact. They are
not — they are the rows that make a module work on array data, which is the input we have not shipped
support for yet and which every Gen-I consumer had.

**What we did meanwhile.** Nothing, deliberately. We can classify these rows today — `ref` is in
`weights.parquet`, so `genotype == [ref, ref]` is a one-line predicate, and that is exactly how the
table above was computed. What we cannot do is act on it, for a reason we think is the real content of
this report: **absence is not hom-ref.** It is hom-ref *or* uncovered, and a variant-only VCF cannot
tell them apart. Restoring blindly would report "you are lactase non-persistent" to someone whose MCM6
enhancer was never sequenced, which is the manufactured-reassurance failure ROADMAP_0_7 names as the
worst this format has.

`requires_callable` / `callable_from` (RM6) are precisely the missing half, and they are **unpopulated
on every module in our corpus** — so nothing is lost by our engine not honouring them yet, and nothing
is gained either.

**A worked precedent, because we already solved the adjacent problem next door.** `just-prs` (0.7.7,
same authors, shared workspace) hit this as *"a scoring variant absent from the callset is hom-ref
there"* and shipped `just_prs.reference_allele`. Four properties look transferable:

1. **Two tiers, ranked by authority.** The reference panel's `.pvar` first (a real `REF`, indels
   included), then a single-base faidx lookup against the Ensembl primary assembly for the tail.
2. **A tri-state provenance column, not a boolean.** `ref_source ∈ {panel, fasta, unresolved}`. An
   unresolved position stays unresolved and is never guessed.
3. **A refusal that is the interesting part.** The FASTA tier is gated to SNVs: *"an absent variant
   gives no REF length, so multi-base / indel positions are left `unresolved` rather than
   mis-represented by one base."* Exactly the discipline the ref-agreement rule already needs.
4. **Resolve once, offline; the runtime reads a table.** The output is a precomputed
   `reference_allele_universe_{build}.parquet` of `(genome_build, chrom, pos, ref, ref_source)`, pushed
   to HuggingFace. `compute_prs` then imputes hom-ref for an absent variant **only when the scoring file
   carries a `reference_allele`** — the fact travels with the data, the policy stays with the engine.

**Where the analogy holds and where it does not.** PRS needs a *universe* because genome-wide scoring
files routinely omit `reference_allele` — the fact is missing and must be fetched. A module is the
easier case: `resolution.csv` resolves the reference allele at enrich time and the compiler already
writes it into `weights.parquet`, so **for a weights-led module the fact is in the artifact today**. A
module's site set is also tiny — 520 sites for `longevitymap`, 2 for `lactose_tolerance` — so if
anything were needed it would be kilobytes welded in, never a download.

So we are **not** asking for a per-module reference universe, and we are **not** asking the format to
say which rows are reachable — that is ours, and it is a different answer for every file a user
uploads. A module cannot know it and should not carry it. Two narrower things, ranked:

1. **A compiler warning when a site authors hom-ref, or omits hom-alt.** Independent of everything
   above and cheap. The same probe found `longevitymap` authors **no hom-alt genotype at 208 of its 520
   sites (40%)** — this subject is homozygous at 74 of them and every one is silently unreported. That
   is our curation defect, and no tool told us; a warning at the same tier as the 0.5.3 unjoinability
   one would have. Note this warning needs no notion of reachability: it fires on what the author
   wrote, which is the only thing the compiler can see.
2. **`requires_callable` populated somewhere real, to try the round trip against.** We would rather
   implement restoration against one module that states its callability requirement than infer a policy
   from an empty column. `pgx_slco1b1_simvastatin` or a reference example would do.

**And one thing that *is* a module property, which we had been reaching for from the wrong end.** A
module authoring hom-ref rows is making a static claim — *"evaluate me against a callset that can
express the reference genotype"* — and today that claim exists only as an inference a consumer may or
may not draw from the row shape. `lactose_tolerance` is unusable on a variant-only VCF and correct on an
array; nothing in the artifact says so, and the difference is not visible until a user gets an empty
report. That is close to what `requires_callable` encodes per row, one level up and about the callset
rather than the region. We are not proposing a column for it — we have one module's evidence and P3 says
that is not enough to fix a shape against — but it is the question we think sits under this report, and
we would rather name it than have it arrive later as a second suggestion.

**The longer shot, filed as clearly separate.** Beyond restoration there is *imputation* — reporting a
genotype from population frequency where callability is genuinely unknown — and `just-prs` has an
`ancestry` package that would make it population-specific. We think this is a different kind of claim
and should not ride along: restoration is deterministic given callability evidence, imputation is not,
and mixing them into one column would put a probabilistic call behind the same rendering as a
sequenced one. Recording it here only so the ordering is on the record.

**For the 0.4 families this is blocked behind S31.** `pharm_variants` carries no `ref` at all pre-RM43,
so a consumer cannot even classify the rows. RM43's fill unblocks the classification; the callability
half is unchanged by it.

# just-dna-lite, the same migration read once more — and a brief answered (2026-08-16)

*Reported against 0.5.4, later the same day as S30–S32 and out of the same twelve-module annotation.
S33 came from building the reference-genotype restoration feature S32's reply discusses, so it is that
group's fourth run rather than a new investigation; S34 is the line-per-section answer to a brief this
repository put to them, and it carries their reply about our own documentation being wrong on what a
consumer could install. Both are answered.*

## S33 — "exactly one of those rows can match" is true, and the other rows are not inert to a reader

**Status — accepted, both halves. Ask 1 and ask 2 are in the tree for 0.6; ask 2's bigger sibling is
filed as [RM87](ROADMAP_0_7.md#rm87--an-expanded-row-is-indistinguishable-from-an-authored-one-in-the-artifact),
and the reason you gave for not asking for it is wrong — it is minor-legal, not a 1.0 conversation.**
You are also owed a correction about your mitigation, which is narrower than you think for a reason
that is instantiated in our own corpus.

**Reproduced, from our corpus rather than from your report.** `pathogenic_clinvar` has **9**
`variant_key`s resolving onto more than one locus (of 328) and `hboc_palb2` has **2** (of 16); every
one is same-position, different-`ref`, matching your table's last column. Authoring both genotypes at
your `rs1554917888` — `T/TA` and `TA/TA`, rsid-only, against that module's own two resolution rows —
compiles to exactly the four rows you describe, and the fourth is `variant_key=11:5226675:TA:T`,
`ref=TA`, `alts=[T]`, `genotype=[TA,TA]`, `conclusion=pathogenic`. A well-formed reference homozygote
asserting a pathogenic finding, exactly as you said. That fixture is now
`compiler/tests/test_expansion_counts.py`, so the row is a regression test rather than a description.

**Ask 1 — the read-side sentence — shipped, and it is a section rather than a sentence.** It went into
SCHEMAS.md § *the consumer join contract*, which is the normative consumer-facing part of that
document and already carries the callable/no-call obligation; a new subsection states that a row
asserts about a **(locus, genotype) pair**, that only the matching member of an expansion asserts
anything, and — because it is the question a reader has next — that the expansion is not going to be
filtered and why. COMPILER.md's paragraph now says the same thing from the other side: the "exactly
one can match" sentence is right about *matching* and was written in a frame where an unmatchable row
is inert, which it is not to a reader.

**Ask 2 — the manifest count — shipped as two: `expanded_keys` and `expanded_rows`.** RM44's shape,
and neither derives the other (one key over three loci and three keys over two are different
situations). Both are `None` where resolution did not run — no `variants.csv`, no injected table, or a
non-GRCh38 module — deliberately not `0`, since a catalog that cannot tell "no expansion" from "no
measurement" will badge the second as the first. One caveat worth stating because it is tempting:
**`expanded_rows - expanded_keys` is not the number of unmatchable rows.** That needs the authored
genotype count per key, which is per-row information the manifest does not carry.

**Probing your report turned up two defects in our own reporting, both fixed here.** The expansion
warning was emitted inside the per-authored-row loop, so the fixture above published the identical
sentence **twice** into `manifest.compilation.warnings` and each copy said *"expanded to 2 rows"* of an
artifact that had gained four — a published surface (RM44) giving a wrong count, not merely a repeated
one. It is now one sentence per rsID with the true total, and it says what the extra rows are. And
`_check_genotype_coverage` — the check S32 produced, three days old — fired on your exact site with the
reason *"no ref is authored or resolved here"*, of a site the table resolves onto **two** refs. Right
conclusion, false stated cause, and it would have sent an author to fill a cell that is already
answered twice over.

**Your adjacent question, answered by running it.** `_check_genotype_coverage` runs in `validate_spec`
and **only** there, in front of resolution — deliberately, because its message embeds a count and a
post-resolution re-run would count the expanded rows and publish a second, differently-numbered copy
of the same finding. So it never sees the four rows; it sees your two authored ones as a single site,
because the site key is position-level. It fires once, reporting the missing `T/T`. The
reference-homozygote reason **cannot** fire there, and there are two independent guards:
`_site_reference_allele` takes the ref from the injected table only when the loci agree on one, and
withholds on a disagreement; and were the check ever moved behind resolution, the expanded rows carry
`ref` themselves and it withholds again on the same disagreement, by its other branch. You were right
that the two features touch the same rows, and right to ask.

**The correction you are owed on your mitigation.** "Withhold any locus the artifact spells with more
than one `ref`" is, as you say, not a guarantee the format makes — and the shape it misses is not
hypothetical here. `enrich --keep-par-twin` records a pseudoautosomal locus on **both X and Y with
identical alleles**: `reference_examples/shox_par1/` was built from that (nine of ten SHOX variants,
20 rows for 10 findings), and it is the same-`ref`, same-alleles expansion your check cannot see. A
paralogous rsID naming two positions that carry the same reference base is the other. Both are rarer
than the ClinVar dup/del pair and neither is excluded by anything.

**And the premise behind your own deferral is wrong, which is our fault for not saying so plainly.**
You wrote that carrying `locus_index` into the parquet is *"a 1.0 conversation"* because *"the 0.5
digest window is closed and a new column moves every module's digest"*. Under our charter it is a
**minor**: Principle 3 says a new optional column is additive and lands in one, with the authored
identity — `content_signature` and the per-input hashes — unchanged and only a recompile's
`artifact.digest` moving; Principle 4 scopes byte-reproducibility to a fixed `compiler_version`
anyway; and the 0.6 cost amendment prices a stamped compiler-managed parquet column as *"approximately
free… the cheapest thing this format can add"*. "It moves `artifact.digest`" has not been a reason to
defer since 2026-08-11. So the thing you actually want is legal and cheap.

It is filed rather than built because **`locus_index` alone does not answer your question**: it is `0`
on every non-expanded row *and* on the first member of every expansion, so a reader holding one row
cannot tell them apart. It needs a `locus_count` beside it, or to be a `locus_count` instead — and a
plain boolean forecloses the ordinal permanently under P5. That choice is one-way inside the major and
RM87 carries the three candidates with what each costs. **If you have a preference, say so there** —
you are the reader, and this is a decision that should be made by the party who has to use it.

**Nothing here changes what you should do now.** Your withholding rule is right to keep. `expanded_keys
> 0` tells you an artifact has these rows at all, which lets you scope the rule instead of running it
everywhere. All of it is 0.6, and 0.6 is still uncut.
<!-- triaged: 0.6.0 · sha 8f9daad34977 -->

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, from the same run as S31 and S32 and
found while building the restoration feature S32's reply discusses.

**We know this one is documented, and we are not asking for the expansion to change.**
[COMPILER.md](COMPILER.md) says it plainly: *"one-to-many rsid reverses into N rows that each carry
their own locus's alleles beside the **one** genotype the author wrote; exactly one of those rows can
match"* — with an unconditional error rejected because it would break P7's fixed point, and the
`{ref} ∪ alts` membership check deliberately unioned across loci because a short alt list is a gap in
the source at least as often as a defect in the module. We think all of that is right. This report is
about the scope of the word **match**.

**What we ran.** The same twelve-module annotation of Anton Kulaga's variant-only WGS genome, with the
first cut of reference-genotype restoration: reporting a module's authored *reference* genotype at
sites the callset emitted no record for.

**What happened.** It would have emitted **2,579** rows into that genome's `pathogenic` section and
**1,183** into `cancer`, each telling the reader they carry a pathogenic variant they do not have.
Caught before rendering. Every one came from a one-to-many expansion.

**The trace**, given in full because we first blamed our own panel builder and were wrong:

1. **ClinVar holds two real records** at 5:112767222 under one rsID — Variation 428095, the
   duplication `T → TA`, and Variation 2583495, the deletion `TA → T`, both pathogenic. Correct data.
2. **Our panel authors it faithfully, rsid-only.** `variants.csv` has exactly two rows, no
   coordinates: `T/TA` and `TA/TA`, both meaning the duplication ("genotype: homozygous (two
   copies)").
3. **`resolution.csv` records both loci** under one `variant_key`, `locus_index` 0 and 1,
   `status=resolved` on both.
4. **The compiler pairs each authored genotype with each resolved locus.** 2 × 2 = four rows in
   `weights.parquet`, so `TA/TA` also lands beside `ref=TA`.

**Where the scope assumption breaks.** Against a position join, row 4 is exactly as harmless as the
prose says — nothing matches it. But it is not silent. `TA/TA` beside `ref=TA` is a **well-formed
reference genotype**, and a consumer doing anything other than a position join — classifying a row,
counting rows, or asking "what does this module say about someone who is reference here" — reads it
as a statement the module never made. Ours read it as *"the reference genotype at this locus is
pathogenic"*: syntactically valid, and false.

Nothing on the row marks it as the non-matching member, though the compiler knew which it was at emit
time. We checked: `locus_index` is **not carried into `weights.parquet`** (the artifact has
`variant_key` and `authored_ident`), and SCHEMAS.md is explicit that `resolution.csv` is a lookup
rather than a consumer contract — so from the artifact alone a reader cannot tell an expanded row from
an authored one.

**Scale in our corpus**, `variant_key`s resolving to more than one locus:

| module | variant_keys | multi-locus | same position | same `ref` |
|---|---:|---:|---:|---:|
| `cancer` | 68,331 | **1,296 (1.9%)** | 1,296 | **0** |
| `pathogenic` | 305,850 | **2,730 (0.9%)** | 2,728 | **0** |
| `cardio` | 57,055 | **540 (0.9%)** | 540 | **0** |
| `longevitymap` / `coronary` and the other curated modules | 528 / 27 | **0** | — | — |

Those match the false reference-genotype rows we measured (1,296 / 2,727 / 539) one for one, which is
what identified the mechanism rather than merely correlating with it. Only the ClinVar-derived panels
are affected, and the corresponding shape is in your corpus too —
`reference_examples/pathogenic_clinvar/` is named in COMPILER.md as having three variants of it.

**What we did meanwhile, and why it is not a fix.** Withhold any locus the artifact spells with more
than one `ref`. That took the three panels to 0 and left every curated module untouched. It works
**because of the last column above** — every expansion we hold is same-position/different-`ref`, which
is a property of ClinVar's duplication/deletion pairs and not a guarantee the format makes. A
same-`ref` expansion (two loci differing only in `alts`, or at two positions) is invisible to our check
and to any consumer's, and we would have no way to know it had happened.

**An argument against the repair we would have proposed first.** "Emit the genotype only at the locus
where it fits `{ref} ∪ alts`" is wrong for the reason COMPILER.md already gives — `alts` came from a
source, ClinVar carries only submitted alleles, so a genotype not fitting a locus is a gap in the
source at least as often as a fact about the module, which is why the check unions across loci in the
first place. Dropping rows would also change what `reverse_module` reads back, which P7 forbids. We do
not think the expansion should be filtered.

**The ask, both halves small.**

1. **A read-side sentence.** The statement quoted above lives in the authoring/validation discussion,
   where "can match" is the natural frame. A consumer reading SCHEMAS.md § weights gets no signal that
   a row may be a non-matching member of an expansion, and the natural reading of a parquet row is
   that it is a standalone assertion. One sentence on the read side — *a row asserts something about a
   (locus, genotype) pair, and only the matching member of a one-to-many expansion asserts anything* —
   would have saved us the incident.
2. **A count on the manifest, the RM44 / `positional_rows` shape.** A count of expanded keys (or rows)
   would let a consumer know an artifact contains expansion rows at all, and act on it, without
   touching `artifact.digest`. Carrying `locus_index` into the parquet is what we actually want and we
   are explicitly **not** asking for it in a minor — the 0.5 digest window is closed and a new column
   moves every module's digest, so that is a 1.0 conversation if it is one at all.

**One adjacent question we cannot answer from 0.5.4.** S32's reply says `_check_genotype_coverage`
"takes the reference allele from the row or from `resolution.csv`" and fires at a site annotated for
two or more genotypes. At an expanded locus there are two reference alleles at one position and four
rows. If that check runs post-expansion, does it see one site with two genotypes under each `ref`, and
does the reference-homozygote reason fire on the row that *is* the other locus's hom-alt? We may be
wrong about the ordering — we cannot run 0.6 — but the two features touch the same rows and it seemed
better to ask than to find out after recompiling the corpus.

## S34 — reply to CONSUMER_BRIEF_LITE: two gaps (both now closed), two deliberate, one joint

**Status — every section answered; §1 fixed here as a documentation defect, §2 fixed as one already,
§4 filed as [RM84](ROADMAP_0_7.md#rm84--a-module-has-no-version-identity-on-the-discovery-path-and-the-publisher-is-the-half-we-own),
§3 and §5 need nothing from us. And your opening complaint is upheld: the brief was wrong about what
you could install.**

**The version fact — you are right, and it is worse than a wording slip.** The brief presented a table
of 0.6 fields as *"also shipped since you last synced"*, which is a claim about installability, and
this file's own S25/S26 note says the opposite. Confirmed as you describe: `resolution_subjects`,
`positional_rows`/`positional_rows_placed`, `gene_validity`, `clinical_assertions`, `derived`,
`readme`, `verification` and `just_dna_format.layout` are all 0.6, and **0.6 is still uncut today** —
every `pyproject.toml` reads `0.6.0`, and `git tag` stops at `v0.5.4`. So the sentence you asked for
is now the standing rule for anything we write to you: *"in the tree" means the code and tests are
committed and nothing more; check [CHANGELOG.md](CHANGELOG.md) for whether the version it names was
cut.* We cannot put it in the brief — that file was removed in `6c9db05`, as your own note records —
so it goes here, and into the next one. Sorry for the afternoon.

**§1 — accepted as a documentation defect, fixed in the same pass.** Confirmed: no call site anywhere
in this workspace, and `compiled_by` appears only as a value we write. Your trap reproduces exactly and
it is the better half of the report — the default *is* the marketplace policy, so one naive call site
rejects every locally-compiled module, ours included, since our compiler leaves `compiled_by` null by
design. The contract is right and the surface was not saying so: `verify_manifest`'s docstring listed
`require_marketplace` among the optional steps rather than as the fork it is, and `schema/README.md`'s
example used the default with no comment. Both now state the two policies, one per install route, and
say that neither is a strict/lax pair — the hashes and the digest are checked in full either way, and
only the provenance claim is dropped. Both also point at the guarantee that is actually load-bearing,
since `compiled_by` is an unsigned string in a file its own claimant wrote: a pinned `public_key`.
Marking the flow unimplemented in your spec rather than letting it describe behaviour you do not have
is the right call and we would make the same one.

Probing that turned up an adjacent defect and it is one you should know about: **`schema/README.md`
still called `artifact.digest` "the version's immutable content identity"** — the exact wording S7 was
filed against, and the opposite of what the charter says (the digest is the *byte* identity;
`content_signature` is the content one). SCHEMAS.md was corrected when S7 was answered and this copy
was missed. If any of your reasoning about when a module "changed" came from that README rather than
from SCHEMAS.md, it was reading a false statement.

**§2 — deliberate, and your guess was right; the docs were the defect and they are fixed.** Your
`_lead_join_strategy` argument is better than the trust rule and we have adopted it as the reason
rather than merely accepting the outcome: reading the artifact's own null coordinates is authoritative
for the bytes in hand, needs no trust rule, and works on a module whose manifest was never fetched,
which on your discovery path is all of them. Both SCHEMAS.md and `manifest.py`'s own comment said *a
consumer* should apply the trust rule, which is what sent you looking for a read path you had
deliberately not built; they now say the reader is a **catalog** — a server projecting a badge over
many modules cannot open every artifact, and that is who those fields are for. Same correction applied
to `positional_rows_placed == positional_rows`, and your reading of it as the manifest-side twin of a
test you already run is exactly right.

**§3 — nothing owed, and the three choices you flag are all the ones we would defend.** Tri-state with
`None` meaning *not established* is this project's own house algebra, so it needs no argument here.
Recording the digest the module **claims** rather than one you recomputed is the honest thing while §1
is open — and note that §1 being fixed does not by itself close it: `verify_manifest` verifies bytes
against a manifest, so a recomputed digest still tells you the artifact matches its own manifest, not
that either is the module you meant to install. That is what a pinned key is for. Your `module.version:
null` finding is yours, as you say, and we are only glad it surfaced in your pipeline rather than in a
reader's report.

**§4 — joint, agreed, and filed on our side as [RM84](ROADMAP_0_7.md#rm84--a-module-has-no-version-identity-on-the-discovery-path-and-the-publisher-is-the-half-we-own).**
Our half is `upload.upload_module`, which writes the flat `data/<name>/` layout with no version
segment; the item records your §4 statement — that you will follow a version segment in discovery if
the publisher grows one — as the consumer half already agreed in writing, so whoever picks it up does
not have to re-negotiate it. Your point that the §3 fields record *where* and not *which build* is
right and is written into the item as the reason a partial mitigation does not close it.

**§5 — nothing owed, and the traced consequence is the useful part.** An installed PGx module being
undiscoverable to the publish/edit pane is a sharper version of the bug than the brief guessed, and
one shared `find_lead_table()`/`has_lead_table()` over `LEAD_TABLES` is the same repair we would have
made — the two-predicates-for-one-question shape is a defect this repository keeps finding in itself
(S30 had three copies of one rule). Nothing to do here.
<!-- triaged: 0.6.0 · sha e1630101892d -->

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16. This is the line-per-section answer
`CONSUMER_BRIEF_LITE.md` asked for, plus what we changed on our side. Every grep in the brief
reproduced exactly as written. *(The brief itself was removed in `6c9db05`, the commit that filed this
answer — recover it from git history if you need the questions it put.)*

**A version fact that gates half of it, and that we could not tell from outside.** We are on
**0.5.4** of all three packages. The installed `Compilation` model carries `compile_success`,
`compiled_at`, `compiled_by`, `compiler_version`, `ensembl_reference`, `fully_resolved`,
`resolution_mode`, `resolution_signature`, `resolution_sources`, `vrs_alleles`,
`vrs_alleles_identified`, `warnings` — and nothing else. So `resolution_subjects`,
`positional_rows`/`positional_rows_placed`, `gene_validity`, `clinical_assertions`, `derived`,
`readme`, `verification` and `just_dna_format.layout` do not exist in any version a consumer can
install. The brief presents that table as *"also shipped since you last synced"*, which reads as
"pip and you have it"; this file's own S25/S26 note says the opposite and is right. Worth one
sentence in the brief saying the table is 0.6 and 0.6 is uncut, because we spent a while looking for
fields that were never going to be there.

**§1 `verify_manifest` — gap, and the spec is the first half of it.** Confirmed: no call site,
and `compiled_by` appears only as a value we write. One thing to know that the brief does not
mention: the 0.5.4 signature is `verify_manifest(module_dir, manifest, *, require_marketplace=True,
…)`, so the *default* is the marketplace policy. A naive single call site would reject every
locally-compiled module, since our own compiler leaves `compiled_by` null by design. Wiring it means
two policies — `True` for a registry install, `False` for a local compile — which is a fine contract,
just not the one the parameter name advertises at a glance. Meanwhile we have marked the
verify-then-install flow in our `docs/MODULE_MARKETPLACE_SPEC.md` as unimplemented rather than let it
keep describing behaviour we do not have.

**§2 `resolution_mode` / `fully_resolved` — deliberate, and your guess is right: the docs are what
needs fixing.** Registry-projected `resolution.trusted` is the only path we intend to support. The
stronger reason than "the registry already evaluated it": for the question the annotating engine
actually asks — *can this table join to a VCF by position* — we read the artifact's own null
coordinates (`_lead_join_strategy` in `hf_logic.py`) rather than any manifest field. That is
authoritative for the bytes in hand, needs no trust rule, and works on a module whose manifest we
never fetched, which on the HuggingFace path is all of them. By the same argument we do not expect to
need `positional_rows_placed == positional_rows`: it is the manifest-side twin of a test we already
run against the data.

**§3 no module version on an annotation run — gap, and the only one of the five that touched the
report. Closed.** `ModuleOutputMapping` gained `version`, `digest` and `source_url`, filled by a new
`read_module_provenance()`, and the report renders a "Modules in this report" table from them. Three
choices worth stating because they are the honest half:

- All three are **tri-state**. `None` means *not established*, never "unversioned" and never
  "unverified". A module discovered on HuggingFace has no manifest fetched at all, so only
  `source_url` is knowable there, and the template renders the other two as *Not stated*.
- The digest recorded is the one the module **claims** — read from `manifest.json`, not recomputed —
  precisely because §1 is still open. It ties a report to a stated identity, not a checked one, and
  the docstring and the template both say so.
- Version falls back from `identity.version` to the authored spec, as the brief suggests. Doing it
  surfaced something on our side rather than yours: six of our own Gen-I ports author
  `module.version: null` (longevitymap among them), so *Not stated* is the common case across our
  corpus today. That is ours to fix in the porting pipeline, not a format issue — recording it here
  only so a reader of the next brief does not read those blanks as a contract failure.

**§4 flat HF layout — joint, and we agree it wants agreeing.** Confirmed on our side exactly as
described: no version segment, no digest check, and the only invalidation keyed on our own package
version. The §3 fields are a partial mitigation and we want to be clear about how partial: on the
HuggingFace path they record *where* a module came from and nothing about *which build*, so a
silent republish is still invisible to a saved report. If the publisher grows a version segment we
will follow it in discovery; the `vN` fallback in our generic fsspec scan is already the shape.

**§5 two predicates for "is this a module" — gap. Closed.** Your reading is right: `weights.parquet`
was standing in for "has a lead table" in all three places, not meaning "SNP-core module". Traced
consequence, which is worse than the brief guessed: a `pharm_variants`-led install was discovered
and annotated fine, but invisible to `module list-custom`, unbadged in the module list, and — the
real one — **absent from the publish/edit pane, so an installed PGx module could not be published or
edited from the UI at all**. Same failure mode as the discovery bug that made such a module
unpublishable in the first place. Fixed with one shared `find_lead_table()`/`has_lead_table()` over
`LEAD_TABLES` in `module_config`, so the local-filesystem predicate and the fsspec one now answer the
same question, and a new family is one edit for both.

# just-dna-lite, answering three asks and reporting a gate under one of them (2026-08-17)

The first item in this file that is mostly *answers* rather than a report: ENRICHER.md had put two
questions to them under RM84 and one under RM89, and this is the reply — read off their code file and
line. The finding it carries is the by-product, and it is the half that mattered most.

## S35 — answering RM84's two questions and RM89's one, and a second gate under RM89 that `_REQUIRED` is hiding

**Status — accepted whole; all three answers taken, the finding confirmed and it is larger than
reported. Fixed in the tree on 2026-08-17, in `just-dna-compiler` + `just-dna-enricher` 0.6.0, which
has since been cut and tagged `v0.6.0` — this line said "NOT cut, the newest tag is `v0.5.4`" when it
was written and was corrected on 2026-08-17 once the tag landed. Tagged is not published, so check
[CHANGELOG.md](CHANGELOG.md) and the index before building against it.** [RM89](ROADMAP_HISTORY.md#rm89--the-publisher-cannot-upload-a-table-only-module-at-all) is closed
by this and moved to history; RM84 keeps only its consumer half, which is yours.

**Your finding is right, and probing it found the consequence neither of us had stated: the published
manifest becomes a false claim.** `manifest.artifact.files` lists a name, a sha256 and a size per
parquet, and `artifact.digest` is a Merkle root over exactly those — so a file attested and not
uploaded means the digest in the manifest cannot be reproduced from the bytes that arrive. Measured
over the sixteen reference examples, compiled and run through `plan_upload`: **seven refused outright**
(your `_REQUIRED` half) and **eight of the remaining nine published an artifact whose own digest did not
verify**. Only `grch37_build` — a bare SNP core with no sidecar and no 0.4-family table — was correct.
`hboc_palb2` dropped six parquets. So 15 of 16, and `sources.parquet` was in the dropped set every time
it existed, which is the half you found from the other end. Nothing is known to have been published
through this surface, so this is *would publish*, not *has published*.

**What was built, and it takes your design.** The allowlist's parquet half is now derived from
`just_dna_compiler.compiler.ARTIFACT_PARQUETS` — the compiler's own `artifact.digest` list, made public
for this — so a new table family reaches the publisher in the commit that adds it, which is the property
you asked to have preserved. `_REQUIRED` is replaced by three positive rules, most specific first: the
plan must carry every file the manifest attests; `weights.parquet` never travels alone (your
`_EXPECTED_WITH_WEIGHTS`, kept and scoped exactly as you scoped it); and at least one **lead** parquet
must be present — `LEAD_PARQUETS` is `weights` plus the nine 0.4 families, matching what
`_find_lead_table` probes. An absent or unreadable `manifest.json` still withholds rather than refusing,
so RM84's four version reasons are untouched. Re-measured after: 16 of 16 publish, and all 16 digests
verify against what would be sent.

**Your two RM84 answers are recorded in
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84), and
`v<version>` verbatim stays.** The deciding half is your correction, not the regex: with no version
fallback in `_discover_hf_source` at all, no spelling is read on this path today, so there is nothing to
suit — and a bare `vN` would still collide two patch releases at one path. Q2's "no, by construction"
is recorded as you established it. The dual write's unbounded growth is recorded there too, as a
consequence rather than an item: retention is the collection owner's call, not the publisher's.

**What to do now: nothing is blocked, and nothing changes for you until you adopt
`just-dna-enricher upload`.** When you do, the gate is "at least one lead parquet" — the same question
`_find_lead_table` asks — and every family you probe is a family that now travels.

<!-- triaged: 0.6.0 · sha ba8028800470 -->

**Reporter** `just-dna-lite` · **Date** 2026-08-17 · **Answers**
[RM84](ROADMAP_0_7.md#rm84--a-module-has-no-version-identity-on-the-discovery-path-and-the-publisher-is-the-half-we-own)
§ *The one open thing* and
[RM89](ROADMAP.md#rm89--the-publisher-cannot-upload-a-table-only-module-at-all)
§ *The open question* · **Read as** three answers and one finding, not a request

ENRICHER.md put three questions in front of us and said delivering them into our tree was the reader's
step. This is the reply, in one item because RM84 asked us to keep them together. Everything below is
read off `just-dna-lite@ui-store`, file and line, not recalled.

### RM84 Q1 — does our discovery scan match `v1.0.0`, or only a `v`-plus-integer segment?

Only `v`-plus-integer, and the ordering is worse than the matching. `annotation/hf_modules.py:251`:

```python
_VERSION_RE = re.compile(r"^v(\d+)$")
...
if m and int(m.group(1)) > best_version:
```

Anchored and integer-only, so `v1.0.0` does not match; and even if it did, `int()` is not a SemVer
comparator, so `v10` would sort under `v9`.

**The correction that matters more than the regex: that fallback is on the wrong path for this item.**
It lives only in `_discover_fsspec_source` — the generic github/http/s3 branch. HuggingFace has its own
branch, `_discover_hf_source` (`hf_modules.py:198-211`), which lists `datasets/<repo>/data` one level
and flat-probes each subfolder with `_probe_module_at_path`. There is **no version fallback there at
all**. So on the HuggingFace path, which is RM84's own motivating case, `v<version>` is invisible in
every spelling, and the segment you chose cannot be the reason.

[S34 § 4](CONSUMER_SUGGESTIONS_HISTORY.md)'s "the `vN` fallback in our generic fsspec scan is already the
shape" was accurate about the shape and was quoted about a branch that does not serve HF. That is our
error in the original suggestion, not a misreading in RM84.

**So: keep writing `v<version>` verbatim.** A bare major segment would collide two patch releases at one
path — the reason the proposal already rejected it — and would buy us nothing anyway, since the code
that would read it is not on this path. Both halves of the fix are ours: teach `_discover_hf_source` a
versioned fallback, and replace the regex and `int()` with `just_dna_format.identity.Version`, which
already gives us parsing and ordering. Not scheduled yet; the flat path resolves, so nothing is broken
today, only unimproved.

### RM84 Q2 — does a subdirectory under `data/<name>/` disturb that scan?

No, and by construction rather than by luck, which is the part worth having in writing.

Both discovery branches call `fs.ls` at exactly one level and never `fs.find`, `glob` or a recursive
listing, and `_probe_module_at_path` (`hf_modules.py:117-170`) asks `fs.exists` on named files instead of
listing the directory it is probing. A nested `data/<name>/v<version>/` is therefore never enumerated and
never probed. On the fsspec branch the flat probe runs first and `continue`s on success
(`hf_modules.py:260-263`), so under the dual write the versioned copy is not reached even there. Nothing
else in our tree recursively lists or folder-downloads a module directory — `scan_module_table` opens the
remote parquet URL directly.

**Verified by search, not assumed**: no `fs.find`, `recursive=True`, `maxdepth` or `snapshot_download`
against a module path anywhere in `annotation/` or `module_registry.py`.

One consequence rather than an objection, since Q2 asked what could regress: the dual write doubles the
collection's bytes and nothing prunes `data/<name>/v<version>/`, so the repo grows one full artifact set
per release forever. That is your call and it does not affect discovery; recorded because a consumer
mirroring the collection pays it.

### RM89 — what the consuming discovery path actually opens

**Exactly one lead-family parquet.** `_find_lead_table` (`hf_modules.py:109-114`) probes
`{base}/{family}.parquet` across the ten families in `module_config.LEAD_TABLES` and returns the first
hit; that single existence probe **is** our "is this a module" test. Everything else is `fs.exists`-gated
and optional: `annotations.parquet`, `studies.parquet`, `sources.parquet`, `metadata.json`/`.yaml`,
`logo.{png,jpg,jpeg}`. `manifest.json` is not opened by discovery at any point.

Of your two candidates, **"`manifest.json` plus at least one parquet" is the one we can consume**;
"manifest as the only required file" would let a directory publish that our scan cannot see at all. We
also share your instinct that the replacement be a positive rule — the guard against a half-compiled
directory uploading is the reason to rewrite `_REQUIRED` rather than delete it.

### The finding: `_REQUIRED` is not what blocks a table-only module — `_ALLOW_PATTERNS` is

RM89 names `upload._REQUIRED` as the widening. Reading `upload.py:49-55`, the allowlist handed to
`upload_folder` is `*_REQUIRED + manifest.json + logo.png + logo.jpg + README_CANDIDATES`. Not one 0.4
family is in it — `pharm_variants.parquet`, `diplotypes.parquet`, `haplotypes.parquet`,
`repeat_alleles.parquet`, `allele_function.parquet` and the rest appear in neither constant.

So relaxing `_REQUIRED` alone converts *"a table-only module cannot be published"* into *"a table-only
module publishes as `manifest.json` + README + logo, with no data"* — which our discovery then correctly
ignores, and which is a worse failure than the current one because it is silent and leaves a directory
behind. We checked the seven measured examples against the allowlist as well as against `_REQUIRED`:
all seven fail both gates. `fmr1_cgg_repeat` stays the instructive one for the same reason it is in
RM89 — it has `studies.parquet`, which *is* in the allowlist, so it would publish exactly one side table
and no lead table.

**We are not asking for a design, because we shipped one and it is running.**
`just_dna_pipelines.v1_port.publish` (`publish.py:22-35`) derives its allowlist from the same list
discovery probes:

```python
_LEAD_PARQUETS = tuple(f"{t}.parquet" for t in LEAD_TABLES)
_SIDE_TABLES = ("annotations.parquet", "studies.parquet",
                "sources.parquet", "literature.parquet",
                "frequencies.parquet", "gene_metrics.parquet")
_ALLOW_PATTERNS = [*_LEAD_PARQUETS, *_SIDE_TABLES, "manifest.json", "logo.png", "logo.jpg"]
_EXPECTED_WITH_WEIGHTS = ("annotations.parquet", "studies.parquet")
```

The gate is "carries a lead table", and `_EXPECTED_WITH_WEIGHTS` keeps the half-compiled-directory
refusal you want, scoped to the weights-led shape where a missing side table really does mean an
interrupted compile — a `pharm_variants`-led module legitimately has neither. This is what publishes
`pharmgkb` today, so RM89 does **not** block us; it blocks you, and it blocks us on the day we adopt
`just-dna-enricher upload` as the canonical path, which `publish.py`'s own docstring says is the plan.

Deriving both lists from one constant is the property we would most like preserved in whatever you
build: adding a family becomes one edit that discovery and the publisher learn together, which is
exactly the skew RM89 describes — a rule whose premise the format withdrew, left in place — arriving a
second time.

### A live gap in that same allowlist: `sources.parquet` does not travel

Separable from RM89 and reported here because it is the same six lines. `sources.parquet` is not in
`_ALLOW_PATTERNS`, and we read it: discovery exposes `sources_url` (`hf_modules.py:167`) and the report
renders distinct source terms in its footer, restricted to `layer == "annotation"` because
[SCHEMAS.md § SourceRow](SCHEMAS.md) makes that the layer carrying the derivative-work obligation.

A module published through the enricher therefore arrives with its source terms missing, and our footer
renders **"Not stated"** — which is our tri-state for *could not be established*, and is the correct
rendering of what we received. The bytes existed at compile time and were dropped at upload. That is the
same shape as the note already above `_ALLOW_PATTERNS` about `manifest.readme` and the ClinPGx
`LICENSE.txt`: a field whose bytes nobody uploads is a field that does not travel — here applied to a
licensing table rather than to a manifest field. `literature.parquet`, `frequencies.parquet` and
`gene_metrics.parquet` are in our list for the weaker reason that a published module should be a complete
artifact; `sources.parquet` is the one with an obligation attached.

### What we did meanwhile

Nothing was worked around, because nothing is blocked. We publish through our own
`pipelines v1-port publish`, whose allowlist already covers every family and `sources.parquet`. The
RM84 discovery work is unstarted and unscheduled: until it lands, `read_module_provenance` continues to
state `version: None` for every HF-discovered module, which our report renders as *Not stated* — correct,
and now correct for a reason that has a fix on our side rather than yours.

# Anton Kulaga on authored weights, from the app side (2026-08-17)

Field feedback rather than a bug report, arriving over chat rather than as a written item — recorded
here in the reporter's own words, Russian original and translation, because the diagnosis was right
and the specific repair proposed with it was not.

## S36 — `weight` declares no scale and no methodology, so every module means something different by it

**Status — accepted, and the diagnosis is right; the specific repair you proposed is refused, and the
three items that make the underlying want satisfiable shipped in the tree on 2026-08-17.** All three
packages read **0.6.0, which has since been cut and tagged `v0.6.0`** — this line said "NOT cut, the
newest tag is `v0.5.4`" when it was written and was corrected on 2026-08-17 once the tag landed.
Tagged is not published, so check [CHANGELOG.md](CHANGELOG.md) before building against any of this.
[RM90](ROADMAP_HISTORY.md#rm90--gwas-effect-sizes-as-a-derived-fact-table-because-they-may-not-go-in-weight),
[RM91](ROADMAP_HISTORY.md#rm91--a-study-states-an-effect-magnitude-relative-to-no-allele) and
[RM92](ROADMAP_HISTORY.md#rm92--the-one-magnitude-in-the-format-with-no-unit-beside-it).

**Reproduced, and it is worse than you said.** `weight` is authored **zero times** in this repository.
Nine of the sixteen reference examples carry a `variants.csv`; four carry a `weight` column — 42 rows
between them — and every cell is blank. So the column you are describing as inconsistent has never
been dogfooded here at all, which is a fact about us rather than about your modules, and it now sits
beside the 1.0 review of whether `weight` survives.

**What shipped.** `module_spec.yaml` gains a free-text `weighting:` block — `scale`, `method`, `note` —
so a module states what its numbers mean and whether they travel; it reaches `manifest.weighting` and
moves neither identity half. `gwas_effects.csv` → `gwas_effects.parquet` is a new derived-fact table
carrying the GWAS Catalog's published effects **with their units and their effect alleles**, filled by
`just-dna-enricher gwas`. And `StudyRow` finally has `effect_allele`, because it had been stating
magnitudes relative to nothing since 0.3.

**What is refused, and why the fallback half is not in the design.** Having the enricher fill `weight`
where the authored cell is null is barred twice over: MODULE_LIFECYCLE § Stage 3 names
`weight`/`direction`/`effect_size` among the cells no tool fills, and every check in the tier reports
rather than repairs — a null `weight` means *the author has not modelled this*, not *nobody has
computed this yet*. There is a sign trap inside the proposal as well: `weight` is documented
positive=protective while a GWAS beta is positive on the **effect allele**, so a silent fill inverts
the claim on exactly the rows nobody re-reads.

The per-row precedence rule that came up next — "use the GWAS value where `weight` is null" — is
refused for a different reason, and it is your own argument: it puts two methodologies in one summable
column, which is the defect you reported, and it leaves the module with no single scale left for
`weighting:` to declare. Splitting such a module in two was also considered and refused: the split
criterion would be *source coverage* rather than methodology (module B would be "the variants with no
published GWAS"), and membership would churn every time a paper lands, routing an upstream fact
straight into authored identity. So there is **no fallback mechanism at all** — the module declares
what its weights are, and a consumer chooses a table wholesale rather than blending row by row.

**One caution the data supplies better than any design note.** We ran the new pass against
`hfe_hemochromatosis`: rs1800562 alone carries **186 published associations across 62 EFO traits in 12
distinct effect units**. Three of those units are spellings of one thing (`SD units`, `SD`, `s.d.`),
two more differ only in case (`g/dL`, `g/dl`), 138 rows carry the Catalog's uninformative `unit`, and
**42 of 195 name no effect allele at all** and cannot be weighted in any direction. "GWAS effects beat
curator weights" is true per trait and false in aggregate — pooling that set is worse than the weights
it would replace. Read `manifest.gwas_effects.units` before combining anything.

**What to do now.** Add `weighting:` to any module that authors weights, run `just-dna-enricher gwas`
where you want published effects, and read them per trait. Note the request budget: it is `1 + 2N` per
variant and measured at 382 requests for that one module, so `--no-study-facts` exists if you only
want the effects.

<!-- triaged: 0.6.0 · sha f3ed632b2b17 -->

Reported 2026-08-17 by Anton Kulaga, over chat, in Russian, from the consumer side (the app that reads
`weights.parquet` and combines the column). Not a bug report — field feedback after living with the
column across a corpus of modules. Quoted verbatim, then translated:

> сейчас уже недома. Но основая идея, что weights какую-то фигню городят
> на по каждому модулю нужно расписыавть методологию и давать по каким шкалам
> часто есть gwas эффект по множеству снипов
> они часто идут лучше чем отфанаревые куратор бейзд весы
> у нас де факто по каждому модулю разные методология если говорить о весах

"Not at my desk right now. But the main idea is that the weights construct some nonsense. For each
module you need to spell out the methodology and say on which scales. There is often a GWAS effect
across many SNPs. Those often work better than eyeballed curator-based weights. De facto we have a
different methodology per module when it comes to weights."

Four claims, and they are not the same claim:

1. **The scale is undeclared.** `VariantRow.weight` is `float | None` described only as "Score
   (positive=protective)". Nothing anywhere — not the row, not `module_spec.yaml`, not the manifest —
   says what range it runs over, whether it is additive, or whether two modules' weights are on one
   scale. `effect_size` has `effect_measure` beside it; `weight` has no unit column at all.
2. **The methodology is undeclared.** `defaults.method` exists and defaults to `literature-review`, a
   free-text string that is about the *annotation* method rather than the *weighting* method.
3. **A different methodology per module, in practice.** So the column is module-local — which the 1.0
   tracker already says ("module-local score vs published magnitude") — but nothing in the artifact
   marks it as module-local, and the consumer combines across modules anyway.
4. **GWAS effect sizes often beat hand-set curator weights,** and are available for many SNPs.

**Candidate the maintainer raised, with the argument against it in the same breath:** have the
enricher procure GWAS effect sizes into a derived table and fill `weight` where the authored cell is
null. The argument against is already written down twice —
[MODULE_LIFECYCLE § Stage 3](MODULE_LIFECYCLE.md) names `weight`/`direction`/`effect_size` verbatim in
the cells no tool fills, and Stage 5 says every check reports and never repairs. A null `weight` is
"the author has not modelled this", which is the tri-state house algebra, and filling it from a source
destroys the redundancy a Class-2 check needs. There is also a sign trap sitting in the middle of it:
`weight` is documented positive=protective while a GWAS beta is positive on the effect allele, so a
silent fill inverts the claim on exactly the rows nobody re-reads.

Claim 4 also overlaps a settled thread: combining a GWAS effect across many SNPs is a polygenic score,
which the format delegates to `pgs.csv` + `just-prs` rather than scoring itself
([RM16](ROADMAP_0_7.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest)).

# just-dna-registry, adopting 0.6.1 — the enricher's exception contract (2026-08-18)

Reported from registry 0.17 while adapting each enricher pass for its `POST .../check` dry run.
Not a regression: it predates 0.6, and RM97 is what made it legible, because after RM97 the
escaping exception is at least the tier's own type rather than `httpx`'s.

## S37 — three passes raise their client's error type, which their own documented error type does not cover

**Status — accepted in full, built, and it was six sites rather than three.** Your preferred option is
what shipped: a per-pass unavailability subclass, `FrequencyUnavailable(FrequencyEnrichmentError)` and
five siblings, so `except FrequencyEnrichmentError` starts working and `except FrequencyUnavailable`
becomes possible. Filed and detailed as
[RM101](ROADMAP_HISTORY.md#rm101--a-pass-raises-its-clients-exception-type-which-its-own-documented-type-does-not-cover).
**Shipped in `just-dna-enricher` 0.6.2**, tagged `v0.6.2`. A partial cut: `just-dna-format` and
`just-dna-compiler` are unchanged and stay at `0.6.1`, so upgrade the enricher alone.

**Reproduced, all three, exactly as you measured them** — `GnomadError` out of `enrich_frequencies`,
`EutilsError` out of `enrich_literature`, `ClinGenError` out of `enrich_dosage_sensitivity`, each
through a `try/finally` carrying no `except`. Then the same probe against our own CLI, which is the
part that changed how the item was sized: `just-dna-enricher frequencies <dir>` promises
`FREQUENCIES FAILED: <reason>` and exit 1, and on a gnomAD 503 it printed **nothing at all** and let
the exception out. Your report was about where a contract is stated; it turned out ours was false on
the path it exists for, so this is our defect and not a convenience request.

**Walking the passes instead of the report found three more.** `enrich_gene_metrics` (gnomAD
constraint) and both `identifiers` sites — `check_rsids` against dbSNP and `check_identifiers` against
OLS4/HGNC — had the identical shape. And your "second, smaller instance" has a twin you could not have
seen: `gene_validity.py` conflates "could not fetch the export" with "the existing
`gene_validity.csv` is invalid" at lines 369 and 437, precisely as `clingen.py` did. Both now raise the
subclass on the fetch path only.

**Underneath all of it, RM97 had left a third client leaking.** `OntologyClient.trait`/`.gene` still
returned a raw `httpx.HTTPStatusError` — `raise_for_status()` in the callers, `HTTPStatusError` in
neither retry list — a full release after we told you that class of defect was closed. The reason is
worth your time because it is the failure mode your own report is about: RM97 *had* a coverage guard,
and the guard walked a hand-written tuple of eight module names with `identifiers` missing from it.
Both guards now discover by walking the package, so a new client or pass fails the suite by name.

**On your argument against your own first choice — you were right, and there is a second reason you
did not give.** Flat translation would have broken *you*. You have already compensated by catching the
client's type; `raise FrequencyEnrichmentError(...) from exc` would have stopped `GnomadError` arriving
without giving you anything that was a `FrequencyEnrichmentError` before, so a consumer who had done
exactly the sensible workaround would have been the one to break. The subclass has neither problem.
Your documentation option we agree is weaker, for your reason: RM96 was that lesson, and the two
guards above are what a type-shaped answer buys that a list does not.

**What to do now.** Nothing urgent, and nothing that breaks if you do nothing: your adapters catch the
client's type *alongside* the pass's, and that keeps working unchanged. When you drop the client half,
drop it only where you catch both — an adapter catching `GnomadError` *instead of*
`FrequencyEnrichmentError` is the form that stops firing. If you want the distinction your `unreachable`
field is recording, `except FrequencyUnavailable` is now the way to ask for it, and
`__cause__` still carries the client's error. The full table is in
[ENRICHER § Exception contract](ENRICHER.md).

**On the half you fixed yourselves** — one `try` per pass so a dead ClinGen cannot discard collected
PharmVar/CPIC findings — that matches what `enrich_pgx` does per leg, and it is the right shape. We
deliberately did *not* make `enrich()` or `enrich_pgx` raise these new types: both degrade and withhold
instead, because they have already produced work worth keeping. The subclass is for passes that have
nothing to return.
**Correction, 2026-08-18 (S38).** The sentence above — *"your adapters catch the client's type
alongside the pass's, and that keeps working unchanged"* — is true only if the two types are one
`except (PassError, ClientError)` tuple. Written as two separate arms with the parent first, the
upgrade kills the second arm, because `FrequencyUnavailable` **is a** `FrequencyEnrichmentError` and
Python takes the first matching clause. That is the shape just-dna-registry actually had, in three of
four handlers, and it fails silently: the pass reports a clean check while the source is down. The
guidance is corrected in [INTEGRATION_0_6 § 8](INTEGRATION_0_6.md#8-what-061-got-wrong-and-062-fixed),
which gains a fourth row, and in [ENRICHER § Exception contract](ENRICHER.md). Left as a correction
rather than an edit: this reply is what they were told, and rewriting it would hide that the advice was
incomplete.

<!-- triaged: 0.6.1+unreleased · sha af7eb4c93e62 -->

Reported by **just-dna-registry** while adopting 0.6.1 (registry 0.17). Not a regression: this predates
0.6 and RM97 is what made it easy to see, because after RM97 the escaping exception is at least *your*
type rather than `httpx`'s.

**What we run.** `services/enrich.py` adapts each enricher pass for the `POST .../check` dry run, and each
adapter catches the error type the pass module defines and documents:

```python
try:
    result = enrich_frequencies(spec_dir, mode="best_effort", offline=offline, write=False,
                                client=clients.gnomad)
except FrequencyEnrichmentError as exc:
    return FrequencyCheck(warnings=[str(exc)])       # a degradation to report, not a failed request
```

**What happens.** That `except` never fires for a transport failure, because the pass does not raise its
own type for one:

* `frequencies.py` contains **no `except` at all**. `gnomad.fetch_frequencies` is called at
  `frequencies.py:218` inside `try: … finally: gnomad.close()`, so a `GnomadError` — a 5xx after retries,
  or a whole-request query error from `_errors_by_alias` — travels straight out of `enrich_frequencies`.
* `literature.py:794` calls `client.esummary("pubmed", wanted)` inside a bare `try/finally`, so
  `EutilsError` leaves `enrich_literature` the same way.
* `clingen.py:203` calls `fetch_curation_list(url)` unguarded, so a `ClinGenError` naming an
  unreachable curation list leaves `enrich_dosage_sensitivity`.

Measured, on `reference_examples/hboc_palb2` with `frequencies.csv` and `literature.csv` removed so each
pass reaches its client, and a stub client raising what the real one raises:

```
frequency:  ESCAPED -> just_dna_enricher.gnomad.GnomadError: gnomAD request failed: Server error '503 …'
literature: ESCAPED -> just_dna_enricher.eutils.EutilsError: eutils request failed: Server error '502 …'
clingen:    ESCAPED -> just_dna_enricher.clingen.ClinGenError: could not fetch the ClinGen curation list …
```

**What it cost us.** A `500` from a reporting endpoint, on all three. The endpoint's contract is that a
pass which could not run reports why and never reports clean — your rule as much as ours — and an
upstream 503 was instead ending the request. The ClinGen one was the worst shape: our three PGx adapters
shared one `try`, so the unguarded fetch also discarded the PharmVar/CPIC and ClinPGx findings already
collected. That half is ours and is fixed here (one `try` per pass, which is what `enrich_pgx` already
does between PharmVar and CPIC).

**What we did meanwhile.** Each adapter now catches the client's type alongside the pass's, records the
source in a new `unreachable` field, and returns findings. So we are not blocked — this is about where
the contract is stated, and it is the same argument RM97 settled one layer down.

One thing the fix turned up that is worth passing on, because it is the shape rather than the cause: the
new field alone was not enough. Our CLI prints per-pass findings and no summary for the frequency,
literature and ACMG passes, so a gnomAD outage rendered as `✓ would publish` with nothing else on
screen — the report carried `unreachable` and the human read a clean check. Whatever the resolution
here, a consumer adopting it has a second place to change.

**The ask, and an argument against our own first choice.** The obvious fix is to translate at the pass
boundary (`raise FrequencyEnrichmentError(...) from exc`), which is what `pgx.py:327/374` already does
with `PharmVarError` / `CpicError`. But it flattens two things a caller may want apart — "your input is
wrong" and "the source is down" — and every current pass uses one error type for both, so translating
without splitting would make the distinction harder rather than easier. Documenting instead would be
cheaper and, we think, weaker: a docstring listing four types a caller must catch is a list, and lists
drift (RM96 is that lesson at a different scale). Our preference would be a per-pass *unavailability*
subclass, so `except FrequencyEnrichmentError` keeps working and `except FrequencyUnavailable` becomes
possible — the shape `AcmgListUnavailable(AcmgSfError)` already has, and whose docstring gives exactly
this reason.

**A second, smaller instance of the same thing.** `ClinGenError` covers two opposite histories: an
unfetchable curation list (`clingen.py:142`) and an invalid local `gene_metrics.csv`
(`clingen.py:199`). Only the first means ClinGen was asked. A caller can separate them today only by
inspecting `exc.__cause__` — chained from `httpx.HTTPError` for the fetch, raised bare for the table —
which is what we do, and it is a private detail to be depending on. Matching the message was the
alternative and we rejected it: your warning and error texts are pinned where they are an API, and these
two are not, so a reword would silently flip our verdict from "unchecked" to "your table is broken". A
subclass would make it a type question.

# just-dna-registry, upgrading to 0.6.2 the day it landed (2026-08-18)

## S38 — the 0.6.2 upgrade table has a fourth row: two separate `except` arms, parent first

**Status — accepted as a documentation defect, and it is ours twice over: the table and the sentence in
S37's reply. Both fixed here, plus a guard.** Nothing in the code changes — you are right that the
subclass design is correct, and it is what makes your ordering matter at all. No release is cut for
this; `just-dna-enricher` stays at 0.6.2 and the fix is in documents plus one test.

**Reproduced by construction, then measured.** `FrequencyUnavailable` is declared
`class FrequencyUnavailable(FrequencyEnrichmentError)` in `frequencies.py`, so a parent arm above it
catches every instance and the arm below is unreachable — there is no configuration in which your two
handlers both fire. Driven as an `ast` walk over your reported shape: the parent-first pair reports one
dead arm, the reversed pair reports none, and the one-tuple form reports none. That last case is the
one that makes the two shapes look identical in prose while behaving oppositely, which is the whole
item.

**What §8 now says.** A fourth row, in your words:

| both, as **two separate arms with the parent first** | **the outage arm goes dead.** Move the `*Unavailable` arm above the parent: Python takes the first matching clause, and the subclass is now the more specific one. This is the row that fails *silently* |

with a paragraph under the table saying to read rows one and four together, because *"we catch both"*
describes either and they differ only in punctuation. The row for consumers pinned to 0.6.1 now says
**in one tuple**, and the sentence you needed is the one you wrote — it is in
[ENRICHER § Exception contract](ENRICHER.md) too, since that is the maintained reference and §8 is a
migration note that stops being read.

**On the S37 reply.** *"your adapters catch the client's type alongside the pass's, and that keeps
working unchanged"* was our sentence, and it was too broad in exactly the way you describe. It carries a
dated correction now rather than an edit: the reply is what you were told, and rewriting it would hide
that the advice was wrong for a shape we had not considered.

**Your structural guard is the right instrument and we adopted it.**
`enricher/tests/test_shadowed_handlers.py` parses all three packages and fails on any `except` arm an
earlier arm in the same `try` already catches. Our tree is clean — every `.py` in all three packages,
zero shadowed arms — and
because a zero is worthless unless the walk can fail, a second test runs it against your reported
snippet and asserts it reports exactly one. It also asserts a parent and child in **one tuple** is not
a finding: that is redundant rather than dead, and a guard that cries wolf on it is one somebody
deletes. Only bare-name clauses are compared; `except httpx.HTTPError` is not resolved, which is
documented in the module rather than left to be discovered.

**On `AcmgListUnavailable.skip` — agreed, and it is now pointed at from §8.** You are reading it the way
it was designed: `skip` is decided where the failure happens and holds a `VALID_VERIFICATION_SKIPS`
member, `unreachable` when the source was asked and never answered against `no_reference` when
something was there and no list could be read out of it. Collapsing them sends an operator to check a
healthy network, which is the same answered-absence-versus-unasked-question distinction this tier draws
everywhere. Nothing else carries a `skip` today — the other six are a plain pair — so if you want that
shape on the passes you actually report per-source availability for, file it and we will size it.

**And the observation we are keeping.** That the parent arm becomes *useful* rather than redundant once
the subclass exists — "the question was put and the answer is a problem" is a distinct thing to report
— is a better statement of what the split buys than the one in our own reference, which mostly argues
that the narrow catch is new capability. §8's "what you gain" paragraph is unchanged, but that reading
is now in ENRICHER's contract section.
<!-- triaged: 0.6.2 · sha 26ca25f77e30 -->

Reported by **just-dna-registry**, upgrading to `just-dna-enricher` 0.6.2 the day it landed. **Not a
defect in 0.6.2** — the subclass design is right and we would not change it. This is about the guidance
beside it, because the shape that bit us is not in the table, and it is the one that fails *silently*.

**What INTEGRATION_0_6 § 8 says.** Three rows: catch both types (keeps working), catch the pass's type
only (starts working), catch the client's type *instead of* the pass's (stops firing — "the one that
breaks"). We read that as "we are row one, nothing to do", and S37's own reply says the same:
*"your adapters catch the client's type alongside the pass's, and that keeps working unchanged."*

**It did not.** Row one is written as though catching both means one `except (PassError, ClientError)`
tuple. Ours were two separate arms, because the two meant different things to us — a structural problem
is a plain warning, an outage additionally sets an `unreachable` field:

```python
except FrequencyEnrichmentError as exc:          # structural: no resolution.csv, or it won't parse
    return FrequencyCheck(warnings=[str(exc)])
except GnomadError as exc:                       # the outage arm, added as the S37 workaround
    return FrequencyCheck(unreachable=["gnomad"], warnings=[...])
```

On 0.6.2 `enrich_frequencies` raises `FrequencyUnavailable`, which **is a** `FrequencyEnrichmentError`,
so the first arm wins and the second is dead. Measured on the real pass with a stubbed 503: our
`unreachable` came back `[]` where it had been `["gnomad"]`. Same for literature and ClinGen dosage —
three of our four handlers.

**Why this is worth a note rather than a shrug.** Nothing raises, nothing 500s, no test that asserts a
`200` notices. The endpoint reports a clean check while the source is down, which is the exact failure
S37 was filed to end — reintroduced by the fix for it, in a consumer that had followed the advice. We
caught it only because our guards assert the *field* rather than the status code, and that was luck as
much as design.

**A fourth row would say it.** Something like:

| two separate `except` arms, parent first | **the outage arm goes dead.** Move the `*Unavailable` arm above the parent — Python takes the first match, and the subclass is now the more specific one |

And the sentence we would have needed in the S37 reply is narrower than the one that is there: *catching
both keeps working if they are one tuple; if they are separate arms, check the order.*

**What we did.** Reordered so every `*Unavailable` arm precedes its parent, dropped the client-type
catches entirely (the pass owns it now — we import `httpx` nowhere in that module any more), and added a
structural guard that walks our own AST and fails on any `except` clause shadowed by an earlier one. We
also found the parent arm is now genuinely useful rather than redundant: `FrequencyEnrichmentError`
alone means "the question was put and the answer is a problem", which is a distinct thing to report.
That is the split doing its job.

**One place the split paid off immediately, unprompted.** `AcmgListUnavailable` predates this with its
`skip` member, and we had been collapsing it: a `no_reference` (offline, no snapshot built) was being
reported as an outage, sending an operator to check a network that was fine. `exc.skip` is decided where
the failure happens and is a `VALID_VERIFICATION_SKIPS` member, so we now report only `unreachable` as
one. Worth pointing at from § 8's table — it is the same distinction one level finer, and it was already
shipped before anybody asked for it.
