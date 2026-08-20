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
- **S39** `.env` loaded into `os.environ` by a library path — fixed; RM102
- **S40** upgrade note silent on RM47's relaxation — docs fixed; 1 test
- **S41** ClinVar dup/del pairs collapsed onto one row — fixed; 725 recovered
- **S42** a digitless `module.version` becomes `0.0.0` — filed as RM103
- **S43** `likely_pathogenic` is unwritable, not just unwritten — documented
- **S44** ClinPGx dropped MT-RNR1 and F508del — fixed; 158 rows, licence pinned
- **S45** a re-draft cannot retract S41's collapse — fixed; 0.6.4, 3 tests
- **S46** §6.6 said the closure reached nothing downstream — RM86 closed
- **S47** no public csv → model map for the fact tables — RM112
- **S48** a kind's key columns were unobtainable — RM113
- **S49** scaffold pulled variants.csv behind studies.csv — RM114
- **S50** `--no-study-facts` loses linked columns for good — docs fixed
- **S51** a sidecar's merge key lived inside its pass — RM115
- **S52** nothing reads the outrank record — `outranks` shipped, check is RM117
- **S53** no public route to the rows behind the digest — RM116
- **S54** a provenance_quote that is the article's title — RM118
- **S55** the quote's table could not name its locator — RM120
- **S56** a stale quote counter, and a confident zero — RM119

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

# just-module-creator, adopting format 0.6.1 / enricher 0.6.2 (2026-08-18)

## S39 — a library call loads the caller's `.env` into `os.environ`, and it silently un-did a consumer's test isolation

**Status — accepted, and it split in two: a bug we had not seen, fixed in the tree; the default you
asked about, filed as [RM102](ROADMAP.md#rm102--the-enricher-loads-a-env-into-osenviron-from-library-paths-and-only-half-of-that-has-an-off-switch).**

**The bug is the one you did not report.** Probing your report found that `load_dotenv_file=False` —
the parameter you correctly identified as the machinery already being there — **did nothing at all**,
in all six resolvers. Each passes its `default_*_cache_dir()` as an *argument*, and that helper went
through a `_cache_dir` whose `load_env()` was unconditional, so the file was loaded before the resolver
had looked at its own flag. Reproduced with a marker variable in a `.env` and a controlled cwd:
`resolve_cpic_reference(load_dotenv_file=False)` left `PROBE_SECRET_TOKEN=leaked_from_dotenv` in
`os.environ`, and so did the ensembl and clinvar resolvers. The flag is now threaded through
`_cache_dir` and the six `default_*_cache_dir` helpers rather than the load being removed — the
unconditional load is itself a repair (three "the cache is right there" reports in 0.5.2), and the
`True` path is unchanged. `test_locations.py` runs each resolver in a subprocess and pins both
directions plus the pre-fix arrangement, and a twelfth test walks both families asserting each takes
the parameter, so a seventh snapshot cannot quietly reopen it. **In the tree, not cut** — the version
carrying it will be `0.6.3`; check CHANGELOG.md before pinning.

**It does not fix what you actually hit, and that is worth being plain about.** Your reproduction ran
the *default* path — `build_server` → a resolver with `load_dotenv_file` untouched — so nothing above
changes your result. Your `sys.modules` sweep remains the right defence, and your reasoning for walking
the modules rather than patching `dotenv.load_dotenv` is correct: every `from dotenv import load_dotenv`
holds its own binding. Note also that four credential paths — `net`, `eutils`, `literature`, `pharmvar`
— call `load_env()` with **no flag at all**, deliberately, because a credential is loaded where it is
read; so even a caller passing `False` everywhere still has `os.environ` mutated by the first network
client they build.

**Your candidate, and your reason for doubting it, are both in RM102 rather than being answered here.**
You were right to doubt it. A default flip is silent for every caller who never passed the parameter:
nothing warns, and a deployment pointing its cache through `.env` alone simply stops finding it — which
is the exact report the unconditional load was added to end. Under our charter that is S14's shape (the
addition being legal does not make the change legal) and the retirement cadence requires a deprecation
an author can *act* on, so the honest route is warn-then-flip across a minor, not a patch. The
allowlist variant — load the file, set only `JUST_DNA_*` — is rejected in the item for a separate
reason: it makes us a filter over somebody else's file and the allowlist becomes a hand-kept list of
every variable any tier reads.

**Your narrower ask is done.** [ENRICHER.md](ENRICHER.md) § cache locations now states that the load
writes into `os.environ`, that it is a library path rather than a CLI one, that `override=False` skips
a variable that is **present** so *deleting* one is what lets the file win — your finding, and the part
that is genuinely counter-intuitive — and names both the switch and the flagless credential paths. The
cache-internals bullet carries the S39 defect beside the 0.5.2 one it grew out of.
<!-- triaged: 0.6.3 · sha f5fff5532a4e -->

Reported by **just-module-creator** on 2026-08-18, adopting format 0.6.1 / enricher 0.6.2.

**What we ran.** Our suite has an autouse fixture whose job is to make a forgotten `_env_file=None`
harmless: it points `Settings.model_config["env_file"]` at a path that cannot exist, and clears the
ecosystem's variables out of `os.environ` with `monkeypatch.delenv`. It has a test of its own asserting
the clear-list is derived from the model rather than hand-written. On this tree it had stopped working,
and nothing said so.

**What happened.** Measured inside one test, on a machine with a real `.env`:

```
1 after fixture:      None
2 after Settings():   None
3 after build_server: 'mk_live_…'      # a live polygon credential
4 after connect:      'mk_live_…'
```

`build_server` reaches `just_dna_enricher.locations` through our network module, and `locations`
calls `load_dotenv(env_path, override=override)` while resolving a cache path. `override=False` skips
a key that is **present** — so deleting the variable is precisely what lets the file win. The fixture
had made the leak possible rather than prevented it, and the failure shape is the bad one: it passes in
CI where no `.env` exists, and means something different on every developer's machine.

The concrete symptom was a test named `test_a_token_does_not_leak_between_sessions` failing with *"The
server is configured offline"* instead of its assertion — because a session that had authenticated
nothing resolved a real token, got past the auth check, and hit the offline ceiling behind it. It took
a while to believe that the token was arriving from the environment rather than from our own session
store, because the store was empty and the session id was fresh.

**What we did meanwhile.** Neutralized the loader rather than the file: the fixture now walks
`sys.modules` and replaces every `load_dotenv` binding it finds with a no-op returning `False`. Walking
rather than patching `dotenv.load_dotenv` is deliberate — every module that did `from dotenv import
load_dotenv` holds its own binding, so patching the source module reaches none of them. Two tests pin
it, one asserting no ecosystem variable changes across `build_server` and one asserting the sweep
actually reached `just_dna_enricher.locations`; both were run against the unfixed fixture and watched
to fail.

**Why we think it is yours and not just ours.** `load_dotenv` mutates the whole process environment,
and `locations` calls it from a *library* path rather than from a CLI entry point. Any consumer that
imports the enricher and resolves a cache path inherits the contents of whatever `.env` happens to sit
above their working directory — including credentials for services they never asked about. A CLI
loading `.env` is normal and ours does it too; a library function doing it as a side effect of
answering "where is the cache" is the part that surprises.

**A candidate fix, and the reason we are not confident in it.** The obvious move is to have
`locations` read `os.environ` and leave the loading to the entry point — `load_dotenv_file: bool = True`
already exists as a parameter, so the machinery is there and only the default is the question. What we
cannot judge from here is who relies on the current default: if a documented workflow is "call the
enricher's Python API directly and let it find your `.env`", then flipping it breaks that, and a
deprecation cycle is the honest path rather than a patch. The narrower version, if the default has to
stay, is to say so in the ENRICHER docs beside the cache-path helpers — the behaviour is currently
discoverable only by reading `locations.py`, which is how we found it after an hour of assuming the bug
was in our own fixture.

---

# just-dna-lite, adopting 0.6 from a working 0.5.4 integration (2026-08-18)

## S40 — two 0.6 changes a consumer meets that INTEGRATION_0_6.md does not name, one of them a check that *stopped* refusing

**Status — accepted, all three; [INTEGRATION_0_6.md](INTEGRATION_0_6.md) fixed in this pass, and item
2 also gained the fixture it was missing.** All three reproduced exactly as written, on this tree:
`StudyRow.REQUIRED_ANY_OF` is `()` and `StudyRow(pmid="12345", conclusion="Test")` is accepted with
`variant_key is None`; `reference_examples/shox_par1/resolution.csv` is 10 rows, 10 distinct rsIDs,
every one on chrX, so nothing in it expands; `_OUTPUT_FILES` is gone from
`just_dna_compiler.compiler` and `ARTIFACT_PARQUETS` is there in its place.

**1 — the relaxation now has its own subsection, and your framing is the one that went in.** § 1 gains
a *"one check **stopped** refusing"* heading beside the two tightenings, and the § 1 table gains the
symmetric row (*Requiredness relaxed — one*), because you are right that the old row was literally
true and still left a reader with no way to anticipate the failure. The subsection leads with the
consequence rather than the validator — `StudyRow.variant_key` can be `None`, a null join key in
polars is a silently smaller result rather than an error — and carries your two-line advice verbatim
in spirit: pin the consequence, not the acceptance, and do not repair a null key into a string. Your
argument for *more* emphasis rather than less is quoted in the heading itself: a relaxation is
invisible to a corpus run and visible to every consumer holding a negative test.

We looked for our own half underneath it, as an item like this usually has one, and there is none:
`_cross_validate_studies` handles the subject-less row deliberately (its docstring names RM47 and
explains why the dedup key is `(None, pmid)`), and the compiler's own study paths match on any shared
identifier rather than on `variant_key` equality. So this is documentation-only on our side, which is
worth saying rather than leaving you to infer.

**2 — the sentence was wrong to point at a shipped artifact, and it now says how to build one *and*
where the fixture lives.** Your reading afterwards was generous; ours is that "one is instantiated in
`reference_examples/shox_par1/`" is not defensible when the committed example instantiates nothing,
and it is worse than a plain gap because it was offered as the evidence that your mitigation is
insufficient. § 3 now states outright that the committed example contains no expansion, gives the
regeneration route (`enrich --keep-par-twin`, whose default keeps only the X spelling), and describes
the hand edit — including that the VRS check will refuse the copied `vrs_id` and print the recomputed
ones, which is the ten-minutes-not-an-afternoon detail you found.

**Building it here found the gap under your report.** The claim had no instance anywhere in this
repository, tests included: the corpus's only other expansion is `pathogenic_clinvar`'s
`rs1554917888`, `T>TA` beside `TA>T`, which differs in `ref` — so every existing assertion about
`locus_count` would have survived an expansion that deduped on `(chrom, start, ref)`, and the
same-`ref` case a `ref`-spelling guard cannot see was pinned by nothing.
`test_two_loci_sharing_a_ref_still_count_as_two` now builds the twin from the example's own row
through `par_partner`, and asserts both halves against each other — exactly one distinct `ref` across
the expanded rows, *and* `locus_count == 2` on each. It is the ground-truth artifact you wanted, in a
form that also fails if we ever break it.

**3 — added, as the half-sentence you wrote.** § 1's headline now carries the exception directly:
`_OUTPUT_FILES` was made public as `ARTIFACT_PARQUETS` (§ 2.4), so a consumer who imported the private
name gets an `ImportError` at module scope. We also recorded that you had the better of the two
arguments — re-listing that set by hand is the defect § 2.8 and S35 trace the broken publisher to, so
importing the underscore was the lesser evil and the headline should have said so.

**Nothing is filed.** Three documentation fixes and one test, all in the tree; the fixes are in a
document that describes an already-shipped release, so there is no version to wait for. Thank you for
the last section — the `layout` and § 8 notes are the only evidence we get that a document did its
job, and § 8's *four shapes with the silent one spelled out* is the shape we will keep writing.
<!-- triaged: 0.6.2 · sha 09e9c111af7c -->

Reported by **just-dna-lite** on 2026-08-18, adopting format 0.6.1 / compiler 0.6.1 / enricher 0.6.2
(and registry 0.17.0) from a working 0.5.4 integration. `INTEGRATION_0_6.md` was the whole plan for the
migration and it was accurate about everything it covered — the delta in § 2 held, § 3's per-consumer
list was the real work list, and the two tightenings in § 1 were correctly the only *new* refusals.
Three things still cost time, and all three are documentation rather than code.

### 1. `StudyRow`'s identifier requirement was relaxed (RM47), and nothing in the integration note says so

**What we ran.** `uv run pytest` immediately after the version bump, before touching any of our own
code, exactly as § 1 invites ("nothing you have breaks"). Seven failures, and the first was ours
asserting a *refusal*:

```python
with pytest.raises(Exception, match="At least one identifier"):
    StudyRow(pmid="12345", conclusion="Test")     # 0.5.4: raised.  0.6.1: accepted.
```

**What we expected.** § 1 lists what can newly refuse (RM50, RM48) and states "Fields removed,
retyped, or promoted to required | **none**". We read the whole document looking for the converse and
it is not there. `REQUIRED_ANY_OF` going from `({rsid}, {chrom})` to `()` is not a removed, retyped or
newly-required field, so the table is literally true — and a consumer holding a test suite still gets
a failure the document gave them no way to anticipate. RM47 is in the changelog and the schema
docstring is excellent; it is the *integration* note that is silent.

**Why it is worth a line rather than being obvious.** The load-bearing half is not the validator, it
is the consequence one layer out: **`StudyRow.variant_key` can now be `None`**. Anything joining
`studies.parquet` to a lead table on `variant_key` now meets a null key, and a null join key in polars
is a silently smaller result, not an error. We were lucky — `load_studies_for_variants` filters
`pl.col("rsid").is_in(rsids)`, and a null rsid matches nothing, which is the correct outcome for a
citation that grounds a bin boundary rather than a variant. A consumer who keyed on `variant_key`
instead would have lost rows with no signal at all.

**What we did meanwhile.** Rewrote the test to assert the new contract, and pinned the *consequence*
rather than the acceptance — `row.variant_key is None` and `REQUIRED_ANY_OF == ()` — with a comment
saying not to repair a null key into a string.

**Suggested for 0.6.3, and it is one table.** § 1 has "Two checks can newly refuse an author's spec".
The symmetric entry is missing: *one check stopped refusing, and here is what it does to `variant_key`*.
A relaxation is invisible to a corpus run (it can only turn red green) and visible to every consumer
with a negative test, which is the reverse of the tightenings — so it needs saying more, not less.

### 2. § 3 points us at `reference_examples/shox_par1/` for a same-`ref` expansion, and the shipped example has none

**What we ran.** § 3's first change item for us is to adopt `locus_count > 1`, on the argument that our
own mitigation "**misses same-`ref` expansions**, and one is instantiated in
`reference_examples/shox_par1/` via `enrich --keep-par-twin`". That is exactly the fixture we wanted —
our mitigation is real code with a real measured harm behind it (S33's 3,762 findings) and we wanted a
ground-truth artifact to test the replacement against rather than a frame we invented.

**What happened.** The shipped example has no expansion in it:

```
resolution.csv                     10 rows, 10 distinct rsIDs, no id on >1 locus
compile_module(shox_par1, ...)     success, expanded_keys=0, expanded_rows=0
weights.parquet                    11 rows, locus_count == 1 on every one
```

Read again afterwards, the sentence is defensible — `via enrich --keep-par-twin` can be read as *"this
is the example you would regenerate with that flag"* rather than *"this is what is committed"*. But it
is the only pointer in the document to a concrete instance of the shape, it is offered as evidence
that our mitigation is insufficient, and a consumer follows it expecting to find the thing.

**What we did meanwhile.** Synthesized the twin ourselves: copied the example, duplicated one
`resolution.csv` row onto chrY, and compiled. Two notes from doing it, both in the compiler's favour:

- The VRS check caught it and **refused**, correctly and with the recomputed ids in the message
  (`stored vrs_id … does not match the id recomputed from Y:641036 C>A (ga4gh:VA.0qI84…)` — "this is
  corruption, not a difference of opinion"). Pasting the two reported ids back in was the whole fix.
  That error message is the reason this took ten minutes rather than an afternoon.
- With that done: `expanded_keys=1`, `expanded_rows=2`, and two rows with `ref="C"` on both,
  `start` equal, `locus_count=2`, `locus_index` 0 and 1 — the shape § 3 describes, and one our
  `ref`-spelling guard demonstrably passes through (we ran it both ways: the grouped test finds one
  `ref` spelling per position and withholds nothing).

**Suggested for 0.6.3.** Either commit the twinned `resolution.csv` as its own tiny example, or make
the sentence say the example must be regenerated and name the two-line edit. We would take the
regeneration note happily; what we could not do is tell from the document which of the two it was.

### 3. A smaller one: the only hard break we hit was a *private* name, and § 1's headline reads past it

`from just_dna_compiler.compiler import _OUTPUT_FILES` is an `ImportError` on 0.6.1. This is **fairly
documented** — § 2.4 says `ARTIFACT_PARQUETS` "Was private `_OUTPUT_FILES`" — and it is our own fault
for importing an underscore, which we did knowingly and with a comment saying why (a hand-copied copy
of that list had already gone stale once here, and re-listing it is what INTEGRATION_0_6 § 2.8 and S35
both identify as the defect that broke the publisher; importing the private name was the lesser evil).

Recording it only because "**§ 1. The headline: nothing you have breaks**" is the sentence a reader
carries into the upgrade, and for us the very first thing that happened was an import failing at
module scope. A half-sentence under that headline — *"one private name a consumer may have imported
was made public under a new name; see § 2.4"* — would have set expectations right. No action needed on
the code: making it public is the correct fix and we have adopted it.

### What went right, since a report that only lists friction is a misleading record

`§ 3`'s list for us was accurate and complete. The seven test failures we saw sorted into exactly
three groups, all three anticipated by the document (RM80's annotations key, the `licensing.csv`
rename, and RM47 above). `content_signature` not moving meant there was nothing to re-derive.
`layout` is the module we did not know we needed and it removed a whole class of guesswork — our
drafters' stale-file sweep named `sources.csv` literally, and on a `derived/` tree that leaves the
**deprecated** spelling as the copy the next `sidecar_write_path` merges into, so the module keeps the
old name permanently; `sidecar_candidates` made the fix three lines and correct by construction rather
than by coincidence. And § 8's exception table cost us nothing to check precisely because it was
written as four shapes with the silent one spelled out — we have no handler around an enricher pass at
all, so the answer was "nothing to do", reached in one grep instead of by reasoning about MRO.

# just-dna-lite, a 0.6 audit of the ten v1_port modules (2026-08-19)

## S41 — `multi_allelic_rsids` keys `ref` into the site, so a dup/del pair collapses and one ClinVar record is lost

**Status — accepted and fixed in the tree (enricher, uncut; it ships in 0.6.3). Your candidate was
right, and the predicate is now the whole allele event rather than the alt alone.** Reproduced three
ways before touching anything: your `rs80359609` pair through the real `_row_cells` →
`append_partial_rows` path (2 records in, **1 row out**, and the survivor is the 1★ record while the
3★ BRCA2 `ATT>A` is dropped — consequence (1) exactly as you describe it); the predicate in isolation;
and the whole thing against our own `2026-06-27` snapshot over your five named genes.

**Our measurement agrees with yours and adds the number that convinced us.** 17,004 records for
BRCA1/BRCA2/ATM/MLH1/MSH2: 942 rsIDs flagged under the old rule, 1,589 under the new one, and the 647
newly flagged are **exactly** the 647 identities that were collapsing — 725 records dropped, of which
**187 dropped a better-reviewed record than the one kept**. After the fix: 0 collapsed identities, 0
records dropped, and 0 records made unkeyable, which was the one risk in the candidate (a record with
no complete coordinate would become `unkeyable` rather than collapsing; there are none in that
selection, but the test asserts it rather than assuming it).

**One deliberate difference from your wording.** You proposed grouping on `rsid` alone — any rsID
naming more than one record takes coordinate identity. We group on the distinct `(chrom, start, ref,
alt)` events instead, which coincides with yours on real data (every multi-record rsID in that
selection is also multi-allele) but differs on a re-submission: the same allele under a second
`variation_id` is one claim written twice, and moving it to coordinate identity would not separate the
two rows anyway. Flagging only when coordinate identity actually *resolves* the collapse keeps the
predicate true by construction rather than by measurement. Both readings fix your case.

**Your reading of the docstring is the one that settled it.** "More than one alt at one position" was
the correct rule and the code was narrower than its own claim — a differing `ref` breaks an rsid-only
identity exactly as thoroughly as a differing `alt`. Widening also catches a third shape neither of us
listed: **one rsID at two distinct positions**, which the old site key also swallowed, and which is
the direct producer of your consequence (2).

**Six tests, including the one that runs on the real snapshot.** The mirror pair does not collapse;
the pair demonstrably *did* collapse under the old grouping (restated in the test, so the claim is
shown rather than trusted); a re-submitted identical allele still does not flag; one rsID at two
positions flags; the HFE case the predicate was originally written for still fires; and no identity
collapses across your five genes — asserted as a relationship (unique identities == keyable records)
so it holds whatever the snapshot's vintage. All six were run against the unfixed predicate and
watched to fail, the real-data one at exactly 725 dropped records.

**The warning now aggregates.** It listed every flagged rsID, which was right at the one that motivated
it and unreadable at 1,589; it uses the house `examples` helper, so at one rsID the text is
byte-identical to what `reference_examples/hfe_hemochromatosis/README.md` quotes.

**On consequence (2), and this is the part we are not claiming to have fixed.** The 8,231 matchable
rows with wrong labels are a *downstream* effect of the collapse: with each record keeping its own
identity there is no surviving rsID for resolution to pair against two loci, so newly drafted panels
should not produce them. We have not re-measured that end to end on your modules, and we are not going
to assert it from the drafting fix alone — your `_identity_collapse_note` is still the right thing to
run, and if it reports collapses on a panel drafted after this ships, that is a second defect and we
want it as its own item. **Already-published artifacts are not reached by any of this**, which is the
bit worth planning around: they were drafted under the old predicate and need a re-draft.

**Nothing filed.** The repair is legal and additive-in-effect — it writes more rows, moves no schema,
and the drafted output is authored material a human owns rather than a compiled identity — so it is a
fix rather than a roadmap item. `manifest` fields, `content_signature` and every reference example are
untouched; suite 2762 → 2768.
<!-- triaged: 0.6.3 · sha 0b16582fa93d -->

Reported from just-dna-lite, 2026-08-19, during a 0.6 audit of the ten `v1_port` modules. Measured on
enricher 0.6.2 / compiler 0.6.1 / format 0.6.1 against the ClinVar `2026-06-27` parquet snapshot.

**What we ran.** Rebuilt the identity assignment `draft_gene_panel` performs, over the exact record set
`select_by_gene` returns for our three ClinVar panels, and compared drafted identities to input records.

**What we expected.** An rsID naming more than one distinct ClinVar allele takes the coordinate identity,
so no two records share an authored row.

**What happened.** `multi_allelic_rsids` groups on `(rsid, chrom, start, ref)` and fires only on >1 alt
*within* that group. The ordinary ClinVar dup/del mirror pair — `A>AT` and `ATT>A` at one position — is
two groups of one alt each, so the rsID is never flagged, both records reduce to the same rsid signature,
and `append_partial_rows` keeps whichever the selection ordered first.

| module | records dropped | collapsed identities | notes |
|---|---:|---:|---|
| `cancer` | 1,619 | 1,481 | 483 allele events exist nowhere in the artifact — 454 pathogenic, 29 likely-pathogenic, **108 at 3★** — across 63 genes incl. BRCA1, BRCA2, ATM, MLH1, MSH2 |
| `pathogenic` | 3,140 | 2,953 | 100% differ in `ref`; 435 differ in `clin_sig`; 2,378 differ in `condition`; 69 sit at different positions |

Two consequences worse than the dropped row itself:

1. **The survivor is not the better-evidenced record.** `ref` sorts before `review_stars DESC` in
   `select_by_gene`'s ORDER BY, so which record wins is an artifact of allele spelling. On `cancer` the
   kept row is the *lower*-starred one in 400 of 1,481 collapses. `rs80359609` keeps a 1★ `A>AT` and drops
   the 3★ BRCA2 `ATT>A` (Variation 52138).
2. **The dropped record's coordinate comes back wearing the survivor's labels.** Resolution finds both
   loci for the surviving rsID and the compiler pairs every authored genotype with every resolved locus.
   On `pathogenic` that is 10,558 rows, of which **8,231 are matchable** (het or hom-alt, so restoration
   never sees them): **301 state the wrong `clin_sig` for the locus they sit at and 1,453 the wrong
   condition**. `rs761621516` is the sharpest — a GBA1 record at 1:155239968 rendered with GAMT's gene and
   "Parkinson disease, late-onset", and a genotype `C/CGCT` not expressible from its own `ref=GGTA`. The
   compiler flagged that one ("could not be decided here") and kept the locus.

**Candidate fix.** Group on `rsid` alone: any rsID naming more than one record in the selection takes
coordinate identity. The docstring already says the predicate is "more than one alt at one position" —
a differing `ref` at the same position breaks the identity just as thoroughly, and the mirror pair is
common rather than exotic.

**Why we did not work around it locally.** `draft_gene_panel` re-queries the snapshot itself, so the
records are gone before anything on our side sees the drafted rows, and our own `_allele_index` /
`_row_key` key on the same collapsed identity. Meanwhile we detect the condition and report it
(`_identity_collapse_note` in `clinvar_panel.py`) so a build states what it lost instead of shipping the
loss silently. That is a report, not a repair, and it is all a consumer can do from outside.

**Not urgent for restoration.** We checked: the hom-ref half is fully withheld on both modules — the
pre-0.6 `ref`-spelling guard catches 1,296/1,296 on `cancer` and 2,728/2,728 on `pathogenic`, and there
are **zero same-`ref` expansions** in either. The 8,231 matchable rows are the live half, and neither
`locus_count` nor the `ref` guard addresses them, because those rows do match a real call.

## S42 — `ModuleInfo.version` coerces `'abc'` to `'0.0.0'` rather than refusing it

**Status — accepted as a real defect, filed as [RM103](ROADMAP.md#rm103--a-version-with-no-digits-coerces-to-000-which-is-a-real-version-nobody-wrote)
rather than fixed in this pass, and documented in [SCHEMAS.md](SCHEMAS.md) meanwhile. Your correction
about the unquoted integer is confirmed, and our own docs did not carry the claim.** Reproduced:
`ModuleInfo(version="abc").version` is `"0.0.0"`, as are `draft`, `TBD`, `unreleased` and `-`. We then
took it one step further than the model, and it is worse than your report says — the value **reaches
the published artifact**: a real compile of a reference example with `version: "abc"` writes
`identity.version: "0.0.0"` into `manifest.json`.

**Why it is filed rather than repaired today, and the reason is release sizing rather than doubt.**
Refusing `"abc"` makes a spec that compiles today fail tomorrow, which is the same class as RM50 (a
PMC id refused by name) and RM48 (a wrong-build coordinate) — both shipped in **0.6.0** as minor work,
and both are listed in INTEGRATION_0_6 § 1 under *"two checks can newly refuse an author's spec"*
precisely because a consumer who compiles other people's specs sees CI go red. Legality sizes the
release here; severity would only order it. Given RM17's history — the coercion exists because the
pre-0.4 corpus is full of `v2` and `3`, and 0.6 widened it after **26 of 61** foreign modules refused
on an unquoted integer — we are not going to spring a new refusal on that corpus inside a patch. The
item carries three candidates, including why *coerce to an unmistakable sentinel* is a dead end: every
three-number string is somebody's real version, which is your complaint restated.

**One thing your report will want, because it changes what you can do today.** You tested the model
directly, where the coercion is indeed silent — but the **pipeline is not**. Both `compile_module` and
`validate_spec` already emit a warning naming both values: *"module.version 'abc' was read as SemVer
'0.0.0'. It is advisory either way … but the module now compiles under the coerced value."* We checked
the two for parity and they report it identically, so a build that greps its warnings catches this
now. `ModuleInfo.version_coerced_from` holds the authored string for the same purpose. That is a
mitigation rather than a fix — it does not stop the bad value being published — but it is the
difference between invisible and merely quiet, and it is available before RM103 lands.

**Your correction, checked and standing.** `ModuleInfo(version="1").version` is `"1.0.0"` on 0.6.1, so
"an unquoted `1` loads as an int and is rejected" is indeed false — that was the **pre-0.6** state, and
RM17's widening at `mode="before"` is exactly what fixed it (26 of 61 foreign modules, every one an
integer). We grepped our own documents for the stale claim and none carries it: AGENT_NOTES
`@yaml-version-int`, the CHANGELOG entry and DOGFOOD_0_6_FINDINGS D7-3 all describe the int refusal as
history. You have the hazard right — it is the unquoted **decimal**, which stays refused because YAML
reads `1.10` as `1.1` and the author's text is gone before any validator runs.

**Documented now**: SCHEMAS.md's identity-keys section states the digitless behaviour, that it reaches
`manifest.identity.version`, that both entry points warn, and that RM103 is the open question — so the
next person meets it in the reference rather than in a manifest.
<!-- triaged: uncut · sha bf9b69206ba1 -->

Same audit. `ModuleInfo(version='abc').version` returns `'0.0.0'`. A version is an identity key, and
`0.0.0` is indistinguishable from a deliberate pre-release, so an unparseable string becomes a
plausible-looking claim rather than an error. `1.5` (a float) is refused with an excellent message about
YAML reading `1.10` as `1.1`; `'abc'` is not.

Noting also that CLAUDE.md in our repo carried "an unquoted `1` in YAML loads as an int and is rejected",
which is **not** true on 0.6.1 — `1` coerces to `'1.0.0'`. We have corrected our own doc. The hazard is
the unquoted *decimal*, not the unquoted integer.

## S43 — `clinvar_draft` folds `likely_pathogenic` into `pathogenic=True` and never sets the `likely_pathogenic` column

**Status — the fold is deliberate and stays; the column is worse than you found and is now documented
as permanently unwritten, which is your second option. [SCHEMAS.md](SCHEMAS.md) carries it and three
tests pin it.** Reproduced on our own shipped `hfe_hemochromatosis`, which the drafter produced: its
one `clin_sig=likely_pathogenic` row carries `pathogenic=true`, and `likely_pathogenic` is `False` on
every row of the artifact.

**The fold is 0.3 compatibility, and you were right to suspect it had a history.** `pathogenic` and
`benign` are the legacy booleans P8 pins — required-ish authoritative since 0.3, never demotable
inside a major — and the four-tier distinction lives on `clin_sig`, the orthogonal axis added beside
them. `derive.pathogenic_from_clin_sig` folds both pathogenic tiers to `True` and
`clin_sig_from_booleans` states the loss in its own docstring: *"legacy cannot recover
`likely_pathogenic`/`likely_benign`"*. `clinvar_draft` is doing what the schema says. Your read path
already prefers `clin_sig`, which is the correct one.

**What you found is sharper than "never set by the drafter", and this is the part worth your
attention: `likely_pathogenic` and `likely_benign` cannot be written by anything.** They are parquet
columns with **no authored field behind them** — `VariantRow` declares `pathogenic` and `benign` and
nothing else, so `extra="forbid"` refuses `likely_pathogenic` in a CSV — and the compiler writes the
literal `False` into the parquet at a fixed line. They have been that way since the initial 0.1.0
commit, `reverse` does not read them, and no derivation consults them. So it is not 0 of 214,827 on
your module; it is 0 of every row of every module ever compiled by this project.

**We are not filling them, and the reason is the charter rather than reluctance.** They are published
columns that have always read `False`. Writing `True` — or `None` — into them changes what an existing
reader is told with no way for that reader to notice it changed, which is the silent break P3 exists to
prevent; removing them is major-only for the same reason. So the honest statement for the 0.x line is
the one you offered as your alternative, and it is now in the reference: **permanently unwritten, read
`clin_sig`**. They also went into SCHEMAS.md's tri-state table as its one acknowledged exception —
that table exists to say `None` is never `False`, and these two are a hardcoded `False` sitting in the
middle of it.

**On `pathogenic_count`: your reading is right, and probing it corrected something we would have told
you wrongly.** It counts the folded boolean, so it does include the likely tier — consistent with what
the boolean means, but not with what the name reads as. It also counts **authored `variants.csv` rows,
not parquet rows**, which we only established by writing the test: our first version asserted against
unique rsIDs in the parquet and failed, 13 vs 11, because resolution expands one authored row onto
several loci. Both facts are now in SCHEMAS.md, because the second is the kind of thing a consumer
reconciling a count against an artifact would otherwise chase for an afternoon.

**Three tests**, so the documentation cannot quietly stop being true: the two columns are unauthorable
and always `False` (walking both rather than naming one), a `likely_pathogenic` row reaches the parquet
as `pathogenic=true` on a shipped example, and `pathogenic_count` equals the authored rows carrying the
folded boolean and strictly exceeds the strictly-pathogenic ones. If either column ever becomes
writable, the first test fails and the doc gets rewritten deliberately rather than drifting.

**Nothing filed.** Filling the columns is major-only and there is no 1.0 design question here worth an
`RMn` of its own — the tier axis already exists and already works. If you would rather see the pair
*removed* at 1.0 than left reading `False` forever, say so and we will add it to the 1.0 cleanup
tracker; that is a real choice and it is yours to push on, since you are the consumer who would have
to stop reading them.
<!-- triaged: uncut · sha 27c16dbb010d -->

Same audit, measured on all three of our ClinVar panels.
`clinvar_draft.py` sets `cells["pathogenic"] = True` for both tiers, commented "the 0.3 booleans stay
authoritative and are folded from the same call, never independently". The result is not merely lossy —
it is a wrong assertion on the rows it touches, and the column that exists to carry the distinction is
never written:

| module | `clin_sig=pathogenic` | `clin_sig=likely_pathogenic` | stored `pathogenic` | stored `likely_pathogenic` |
|---|---:|---:|---|---|
| cardio | 75,909 | 39,151 | `true` on both | `false` everywhere |
| cancer | 110,476 | 28,778 | `true` on both | `false` everywhere |
| pathogenic | 402,174 | 214,827 | `true` on both | `false` everywhere |

`manifest.stats.pathogenic_count` reads the boolean and inherits the inflation (cancer 136,662;
pathogenic 611,542). We are not asking for a behaviour change we cannot see the history of — the fold may
well be deliberate 0.3 compatibility. What we would ask is that `likely_pathogenic` either be populated
or be documented as permanently unwritten, because a consumer keying on the column gets 0 of 214,827 and
nothing says so. Our own read path prefers the `clin_sig` column (`_effective_clin_sig`) and is unaffected.

## S44 — `clinpgx_draft` drops MT-RNR1 and every `del`-spelled annotation, including CFTR F508del

**Status — accepted; both genotype families and the licence pin are fixed in the tree (enricher,
shipping in 0.6.3). The `del`-spelled rows themselves stay skipped, and that half is unchanged and
deliberate.** All four claims reproduced against the provisioned snapshot before anything was
touched.

**The diagnosis you did not quite make, and it is the one that matters: our gate was narrower than
our own schema.** `_authored_genotype` accepted only `CC` — two unseparated bases — reasoning that
the general case needs the resolved ref/alt to disambiguate. That is true of an *unseparated* cell
and false of both shapes you found, because `validate_allele` accepts any `^[ACGT]+$` allele:

- **`CTT/CTT` is already separated by the source.** ClinPGx writes `/` wherever an allele runs past
  one base, so there is no splitting decision to get wrong. You are right that these are discarded
  *with* their `del` siblings — same `annotation_id`, so skipping the annotation took the writable row
  too. That is the F508del loss, and it was pure loss.
- **`A` / `CCCCCCC` is a single haploid allele**, which the grammar already holds and which is how
  ClinPGx spells mtDNA. Your instinct was right and so was your evidence — `split_genotype` handles a
  one-element list. The reasoning is the one `clinvar_draft.sole_expressible_genotype` already
  applies on the ClinVar side: the placeholder protects a zygosity decision, and on a haploid contig
  there is none to protect. Inventing a second allele would have been the error, not writing one.

**Measured after the fix: 158 rows recovered**, 36 at evidence level 1A — MT-RNR1 48 (all 24
annotations, the 1A aminoglycoside set intact), plus HTR2C, ACE, TYMS, IFNL4, GSTM3 and CFTR's
`CTT/CTT`. The unseparated multi-base cell the old rule was guarding against does not occur in the
snapshot at all; every multi-base call arrives slashed. It is still declined.

**What stays skipped, and why we are not moving it.** The `del`-spelled genotypes themselves —
`CTT/del`, `del/del` — still do not get written. Since RM5 the grammar *can* spell `<DEL:1500>`, so
the block is no longer "the format cannot express it"; it is that **ClinPGx publishes no length**, and
a lengthless symbolic allele is a rule the compiler drops. Writing those rows would hand you work the
next command in the workflow undoes. So DPYD\*7, RYR1 and ACE keep their `del` rows skipped — but any
pure-nucleotide sibling under the same annotation now survives, which is the part that was costing you
real findings.

**The general rule is now a test rather than a comment**, because this defect is the kind that
recurs: *every genotype spelling this pass declines must be one `PharmVariantRow` would also refuse*,
walked over the accepted set. The converse stays allowed — that is what keeps `del/del` skipped
deliberately rather than by accident.

**Your one-liner was exactly a one-liner, and it was worse than cosmetic.** `license_sha256` was null
on a **share-alike** source whose `LICENSE.txt` we ship in the snapshot ourselves — so the module
named ClinPGx's terms without pinning them to the text that governed the bytes, which is the entire
purpose of that field. Fixed by passing `license_text=`, read from the snapshot. One deliberate
difference from your framing: we hash **the file**, not `release.json`'s stated hash. The file is what
the module is actually claiming, and hashing it independently means a truncated or tampered copy
cannot pin to a value it does not have. They agree on your snapshot — we checked, byte for byte. An
absent `LICENSE.txt` (an older snapshot, built before the extractor) stays `None` and warns, rather
than inventing a hash.

**You are right that `merge_sources_file` is never-clobber and you cannot patch it afterwards** — so
a module drafted before this fix keeps its null. Delete the sidecar and re-draft to pick it up; that
is the documented way to regenerate after a machinery change.

**Nothing filed.** Four tests: the already-separated form, the haploid form, the never-narrower-than-
the-schema rule, and two against the real snapshot (MT-RNR1 and CFTR present, `del` spellings still
absent; the licence hash computed independently from the file). One existing assertion changed
deliberately — `_authored_genotype("CAT") is None` was the old rule stated as a test, and it is now
the new rule with the reason written next to it.
<!-- triaged: 0.6.3 · sha aae77d27f69b -->

Same audit, on our `pharmgkb` module (ClinPGx snapshot, evidence ≥2B).

- **MT-RNR1: 16 annotations / 32 rows, all level 1A**, dropped because the genotype is a single haploid
  allele the drafter cannot pair into a diploid genotype. This is aminoglycoside-induced hearing loss, a
  CPIC guideline. It does not look like a format limit: `split_genotype` handles a one-element list, and
  the format carries a whole `heteroplasmy` family for mtDNA.
- **6 annotations / 19 rows dropped whole for a `del` spelling**, including **CFTR F508del (1A)**,
  DPYD*7 (1A), RYR1 (1A) and ACE (2A). The sharp part is that these annotations also carry
  **pure-nucleotide** genotypes (`CTT/CTT`) which the schema accepts, and those are discarded with them.
  Our module therefore ships 176 CFTR rows and the drug "elexacaftor / tezacaftor / ivacaftor" while
  omitting the most common CF variant.

Also minor, and a one-liner: `sources.parquet.license_sha256` is null on both our rows although the
snapshot ships `LICENSE.txt` and `release.json` states its hash (they match exactly). `SourceTerms.row`
already accepts `license_text=`; the `clinpgx_draft` call passes only `declared_use` and `dataset`. So we
record ClinPGx's terms without pinning them, which is the field's purpose, and `merge_sources_file` is
never-clobber so we cannot patch it afterwards.

# just-module-creator, measuring what a re-draft actually remediates (2026-08-19)

## S45 — a re-draft repairs S41's missing records and leaves the wrong-labelled ones, undetectably

**Status — accepted and fixed in the tree; it ships as enricher 0.6.4. Your candidate is built, at the
layer that can actually see the condition, and report-and-never-remove is the right call for exactly
the reason you gave.** Reproduced independently before touching anything, and every number matches:
996 → 1,061 against a fresh 1,030, `added=65, already_present=965`, **0 identities missing, 31
extra**, all rsid-only, and **0 of 31** findable by the rsid-also-on-a-coordinate-row predicate.

**You measured the half we said we had not, and the answer was worse than we assumed.** The 0.6.3
entry said published modules "need a re-draft" and left it there. That reads as a complete instruction
and is not one: drafting appends and never mutates, so the re-draft adds the coordinate rows *beside*
the collapsed one. Thank you for taking the sentence literally and checking what it produces — that is
the thing that turns a plausible remediation into a measured one.

**One correction to where the fix goes.** You proposed `append_partial_rows`, on the grounds that it
has both halves at merge time. It has the file, but not the predicate: it is the compiler's generic
drafting helper, shared by every provider, and it knows nothing about rsIDs or ClinVar — teaching it
would put a source's identity rule into the tier that must not hold one. `clinvar_draft` already
computes `ambiguous` and now reads the written file back through `DraftReport.path`, which needs no
new surface and keeps the rule where the source convention lives. The output is what you asked for: a
counted, named, aggregated line beside the rest of the run's warnings.

```
31 row(s) already in variants.csv identify by rsID alone (rs1060500703, rs1553653237, … and 26 more)
— but this run writes those rsIDs with their full coordinate, because each names more than one allele
here. They were most likely drafted before that check was widened (0.6.3), when two ClinVar records
collapsed onto one such row. This run has ADDED the coordinate-keyed rows beside them and has removed
nothing: drafting never deletes an authored row, and yours may have been curated since. Review each
and delete it once its records are covered by the coordinate rows — until then the module carries both
the row and its replacements.
```

**Your doubt about removal is the correct one and we are not overriding it.** A drafted row is
authored material by the time a re-draft runs; a human may have decided its `genotype`, `state` and
`conclusion`, and deleting curated work to repair *our* defect is a trade only the author can make.
Drafting-appends-never-mutates is the rule one file over, and a provider that started deleting rows
would be the exception to it. So: named, counted, never touched.

**Your narrower fallback is also done**, because it stays true whether or not anyone reads a warning:
the 0.6.3 CHANGELOG entry now points forward to this one for what a re-draft does *not* do, and
ENRICHER.md carries the whole finding — the 996/1,030/1,061 measurement, the 0-of-31 detection result,
and the reason `_superseded_rsid_rows` can see what a file-level predicate cannot.

**And your advice to authors is better than ours, so it is now in the reference too.** A fresh
directory reconciled against the old module is the clean remediation; the notice exists for the author
who followed the shorter instruction, which is the one we wrote. Three tests: the mirror pair through
a real stale-then-re-draft cycle, silence on a correctly drafted module (a false positive here would
tell an author to delete correct rows), and your `MLH1` measurement asserted as a relationship — every
fresh identity present after the re-draft, every extra one an rsid-only row the notice counts.

**Your contrast arrived while this was being built, and it is the most useful part of the report.**
We re-ran it: `clinpgx_draft` under a stand-in for the old gate drafts 18,691 rows, a fresh 0.6.3
draft gives 18,895, and re-drafting the stale directory lands on **18,895 with 0 missing and 0
stale** — byte-for-byte the fresh draft, exactly as you found. So the two defects genuinely do
remediate differently, and the reason is the one you name: **S44 skipped rows, S41 wrote them under an
identity that has since moved.** Only the second leaves anything behind. That sentence is now the
frame for the whole finding in ENRICHER.md and the CHANGELOG, because it is what stops the next reader
generalising one remediation to both — and you are right that seeing S41 and S44 in the same release
notes invites exactly that. Your cheap version got done as well as, not instead of, the machinery.

**Nothing filed, and one thing still open on your side.** We have not re-measured the downstream label
errors either — like you, we established only that the rows carrying them survive the remediation.
If a module re-drafted *after* 0.6.4, with its superseded rows deleted, still shows mislabelled
expansions, that is a separate defect and we want it as its own item.
<!-- triaged: 0.6.4 · sha 06325e5d4ca3 -->

Reported by **just-module-creator** on 2026-08-19, adopting enricher 0.6.3 (format 0.6.1 / compiler
0.6.1 / registry 0.18.1). This is a corroboration of **S41** aimed at its one open half — you wrote
that already-published artifacts "were drafted under the old predicate and need a re-draft", and
explicitly did not claim to have measured that end to end. We measured it, because our tool surface
wraps `draft_gene_panel` and we had to decide what to tell an author holding a pre-0.6.3 module.

**A re-draft into the existing spec directory recovers every dropped record and leaves the collapsed
rows in place. Nothing in the resulting file distinguishes them.**

**What we ran.** One gene, `MLH1`, `min_review_stars=2`, `max_citations=0`, against the local
`clinvar` snapshot, on installed enricher 0.6.3. Three drafts:

- **A** — drafted with `multi_allelic_rsids` monkeypatched back to the 0.6.2 predicate (grouping on
  `(rsid, chrom, start, ref)`), standing in for a module drafted before the fix.
- **B** — drafted fresh into an empty directory with the 0.6.3 predicate. The ground truth.
- **A again** — re-drafted with the fixed predicate into the same directory, which is the remediation
  an author would actually perform.

**What happened.**

| | rows | distinct identities | rsid-only | coordinate |
|---|---:|---:|---:|---:|
| A, first draft (0.6.2 predicate) | 996 | — | — | — |
| B, fresh draft (0.6.3) | 1,030 | 882 | 703 | 327 |
| A, after re-draft (0.6.3) | 1,061 | 913 | 734 | 327 |

The re-draft reported `added=65, already_present=965`. Against B: **0 identities missing** — every
record S41 was dropping came back — and **31 identities present in A that B does not contain**. Those
31 are the collapsed rsid-only rows: identities the fixed drafter no longer writes, because those
rsIDs now take coordinate identity. 1,061 − 1,030 = 31 exactly, and 913 − 882 = 31 exactly.

**The part that makes it more than an untidy file.** Those 31 rows are the ones carrying S41's
consequence (2) — the surviving rsID whose resolution pairs its authored genotype with both loci and
renders the dropped record's coordinate under the survivor's `clin_sig`, gene and condition. The
re-draft adds the correct coordinate-keyed rows *beside* them rather than replacing them, so after
remediation the module states both the right answer and the wrong one for the same locus.

**And they cannot be found from inside the module.** We checked the obvious predicate — an rsid-only
row whose rsID also appears on a coordinate row — and it finds **0 of 31**: `draft_gene_panel` writes
no `rsid` on a coordinate-identity row (327 coordinate rows in both A and B, none carrying an rsid).
So the stale rows are not distinguishable from legitimate rsid-only rows by any column, and an author
who follows "re-draft" literally ends up with a module that is worse-formed than either the old one or
a fresh one, with nothing to indicate it.

**What we did meanwhile.** Our `draft_from_clinvar` docstring now tells an author holding a pre-0.6.3
module to draft into a **fresh directory** and reconcile against it, rather than re-running the drafter
over the file they have, and says why the second option looks like it works. That is advice, not a
repair; we cannot detect the condition either, for the same reason they cannot.

**A candidate fix, and our doubt about it.** `append_partial_rows` has both halves in hand at merge
time: it knows the rsIDs the current predicate flags, and it can see rsid-only rows already in the file
carrying one of them. Reporting those — a counted, named list on the draft report, alongside
`already_present` — would turn this from undetectable into a line an author can act on, and it needs no
schema change. What we are less sure about is whether it should *remove* them: a drafted row is
authored material by the time a re-draft runs, a human may have curated its `genotype`, `state` and
`conclusion`, and deleting curated work to fix a drafting defect is a trade only the author can make.
So our preference is report-and-name, never touch. The narrower version, if even that is too much, is a
sentence in the S41 CHANGELOG entry saying that a re-draft is additive and does not retract the
collapsed rows — because "needs a re-draft" reads as a complete instruction and it is not one.

**Not asserted.** We measured one gene, and we did not re-measure the downstream label errors
themselves — only that the rows carrying them survive the remediation. The 31/0 split is a count of
identities, not of the 8,231 matchable rows just-dna-lite reported.

**A contrast that sharpens the ask, measured the same afternoon.** We ran the equivalent probe on
`clinpgx_draft` for S44's genotype-gate widening, with a stand-in for the old gate that was
deliberately *broader* than 0.6.2's (12,410 rows drafted where the fix produces 18,895 — so it
declined considerably more than the real one did, which makes it the harder case rather than an
easier one). Re-drafting into the same directory landed on **18,895 rows, 0 stale keys, 0 missing** —
exactly the fresh draft. So "re-draft to pick up a drafter fix" is sound advice in general, and S44
needs no caveat at all.

The difference is that S44 **skipped** rows while S41 **wrote them under an identity that has since
moved**. Only the second leaves anything behind, and it is the case where the file cannot be
inspected to tell. If the report we suggest above is too much machinery for one defect, the cheap
version is to say in the S41 entry which of the two shapes it is — a reader who has just seen S44 in
the same release notes will reasonably assume both remediate the same way, and they do not.

# just-module-creator, writing a `module-revise` skill out of MODULE_LIFECYCLE §6 (2026-08-20)

*Filed 2026-08-20, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as installed, and
`just-dna-registry` 0.18.2. **Priority: we are writing an author-facing skill straight out of
`MODULE_LIFECYCLE.md` §6 this session, so the answer changes text we ship.***

## S46 — `MODULE_LIFECYCLE.md` §6.6 and RM86 say the closure reaches nothing downstream; the registry has recognized and attested it since 0.16

**Status — accepted as a documentation defect, fixed in the tree today; §6.6 and RM86 are rewritten and
RM86 is closed. Your measurements reproduce, and one thing you did not ask about has also moved — see
the pre-flight paragraph below, because it changes your skill too.**

**The narrow question you actually needed answered: no, "served by no endpoint" is not true any more,
and it is false by two independent routes.** Verified first-hand in the registry tree at **0.18.3**
(commit `28f3cea`) on 2026-08-20, not taken from their replies:

- **A read endpoint projects the attestation.** `manifest.verification` is projected onto the
  module-detail response as a `VerificationInfo` block — `closed`, `closed_at`, `closed_by`, `producer`,
  `produced_at` and a per-check list of `check`/`subjects`/`findings`/`skipped`. It is built by
  `services/catalog.py::_verification`, from the **latest** version's manifest; per-version access is the
  `…/manifest` route. Deliberately **not** a card facet, not a filter and not sortable, and `None` is not
  collapsed with an empty block — absent means no attestation survived, which is a different statement
  from an attestation that recorded no checks.
- **The bytes come back too**, but name the flag when you teach it: `download(include_inputs=True,
  layout="split")` lands `derived/verification.json`, because the file is in their `DERIVED_FILES` and
  attested in `manifest.derived` since 0.17. A plain download does not carry it.

**The distinction you drew is the right one and it survives — with a sharper edge than you gave it.**
The projection reads `manifest.verification`, never the file, and that server compiles the spec itself,
so the closure in that block was **re-bound by their compiler against the authored bytes** and dropped if
it did not match. So `closed: true` on that endpoint is hash-checked rather than asserted: it is the
strongest form of "visible" available, and it is still not a registry verdict about your checks. Their
refusal to read the file as a verdict is intact and, as you say, correct. `SIGNATURE_INPUTS` is unchanged
— shipping an attestation still moves no identity and no `409` claim, and their tests assert it.

**The thing you did not ask about, and the reason we would rather you read this before you ship: the
pre-flight is fixed too.** Your report says *"the pre-flight disagreement and the `publish succeeds`
carve-out are both still live as far as we can see."* The carve-out is live — that is the good half. The
disagreement is **not**: it was repaired in registry **0.16.0**. `would_publish_module_level` now
quantifies over a new `published_elsewhere` — the subset of content hits under a *different*
`(namespace, name)`, which is what the gate actually refuses — while `published_as` still lists the
same-module hit, since *"this data is already published as 1.0.0"* is exactly what a review pass wants
to confirm. The namespace is threaded through both pre-flight routes, so `validate` and `check` agree.
Verified at `services/enrich.py`, where the comment names this precise defect. **If your skill warns an
author that the pre-flight will refuse a review publish, drop that warning** — against a current
registry it will not. The honest caveat is a version floor: a deployment older than 0.16.0 still refuses.

**And the question that RM86 said was ours is answered, which changes the advice rather than just the
facts.** We had it filed as waiting on their S12; they answered it in 0.16.0 and we had not read the
reply. The sentence, now §6.6's advice: **a `reviews` row by default; an `authorship` entry when the
record has to travel inside the module or be signed; both when both matter.** Not substitutes — a
`reviews` row cannot carry the reviewer's key, so provenance-of-review is `authorship` or nothing, while
everything else favours the row (no version number, projected onto cards, moderatable, drives
`?group=curated`, and postable by someone who is not the author). So the re-close is no longer a version
spent on an invisible record — but the default instrument for a plain review is still theirs, not a
version bump. Please do not let the inversion carry you past that: *visible* is not *the recommended
path*, and a skill that now tells authors to bump a version for every review would be the opposite
error to the one you caught.

**Third finding, for completeness:** `authorship` still reaches no projected field, and that is now
stated **policy** rather than the omission RM86 called it — payload, so their card never renders an
author's claim about their own reviewer beside the server's own claims. Read it from the manifest.

**What we changed.** [MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md) §6.6's composite sentence is replaced by
the four findings stated separately, each with the release that moved it — your suggested shape, adopted
for your reason: the conclusion outlived the clause it rested on, and a reader could not tell which third
was stale. §6.6 now ends on the `reviews`-versus-`authorship` advice instead of on the version-cost
argument. The stages 7–8 passage is marked fixed with the version floor. Your second candidate — delete
the paragraph and defer to the registry's docs — is rejected for exactly your reason: §6.6 is where a
module author meets this question and their reference docs are not on that reader's path.
[RM86](ROADMAP_0_7.md#rm86--a-review-pass-is-legal-at-the-gate-refused-by-the-pre-flight-and-invisible-once-published)
is **closed**, in place, with the per-finding dispositions and the note that its "waits on their answer to
S12" status was itself stale; [RM_TOC.md](RM_TOC.md)'s row carries the same. Its pointer said
`../just-dna-marketplace`, which is a symlink to `just-dna-registry` — the real name is now given.

**You were right that this is not a trivia correction, and right about the cause.** It is a missed
propagation, three releases deep: their 0.16.0 answered our own S11, and nothing on our side re-read the
reply. Every clause of that sentence was checked against their tree when it was written and none of it
was re-checked afterwards — which is the failure mode of citing another repo's code from prose, and the
reason §6.6 now dates each finding to a release. **Cite us rather than correcting us**: §6.6 as it now
reads is the text to quote, and drop your pre-flight warning at the same time.
<!-- triaged: 0.6.4 · sha a078a50e2186 -->

We are writing a `module-revise` skill — pass two and beyond — with §6 as its primary source, because
§3 says pass two normally re-enters at 3 and §6.1's six kinds are the only enumeration of them
anywhere. §6 held up under checking except on the one claim the skill's central advice turns on.

**What §6.6 says.** In the RM86 paragraph:

> the closure reaches **nothing** — `verification.json` is uploaded, stored, and then read by no code
> path, absent from `RECOGNIZED_SPEC_FILES`, so it is dropped by every server-side rebuild and served
> by no endpoint. The re-close is right and currently costs a version number for a record nothing
> downstream can see.

**What we measured**, against `just-dna-registry` 0.18.2:

```
>>> from just_dna_registry import specfiles as S
>>> S.VERIFICATION_FILE in S.RECOGNIZED_SPEC_FILES
True
>>> S.VERIFICATION_FILE in S.DERIVED_FILES
True
>>> S.VERIFICATION_FILE in S.SIGNATURE_INPUTS
False
```

So all three halves of the sentence have moved. It is recognized, which is precisely what makes
`revalidate` materialize it back out of storage and `upgrade` carry it forward instead of rebuilding a
spec directory without it. It is in `DERIVED_FILES`, so `download(layout="split")` places it in
`derived/` and a downloader receives it. And their `specfiles.py` attributes both changes explicitly —
the `VERIFICATION_FILE` docstring reads *"0.16 recognized this file so a rebuild would carry it
forward; 0.6 lets the manifest attest it (`manifest.verification`), and 0.17 surfaces it — as the
**publisher's** claim, never as a registry verdict"*, and *"**In** `DERIVED_FILES` since 0.17"*.

The `SIGNATURE_INPUTS: False` half is the part that did **not** move, and it is load-bearing in your
favour: shipping an attestation still moves no identity and no `409` claim, which is the property that
makes recognizing an unread file safe. Their own tests assert it.

**Why this is not a trivia correction.** §6.6's conclusion is that a re-close *"costs a version number
for a record nothing downstream can see"*, and that conclusion is the argument for treating "should a
review be a version" as open. If the record *is* carried forward, served in a split download, and
attested in `manifest.verification`, the cost/benefit inverts and the advice we write inverts with it.
We were one paragraph away from telling authors that re-closing after a review buys them nothing.

**One thing we could not settle and are not asserting.** Recognized-and-carried is not the same as
*read*. The registry is explicit that it will not read the file as a verdict — this server compiles
what it publishes, so `compile_success` and the digest are theirs while the attestation is the
publisher's word about what an enricher saw against live sources at authoring time, which they cannot
reproduce offline. That refusal looks correct to us and we are not asking for it to change. What we
cannot tell from outside is whether "served by no endpoint" is still true in the narrow sense — whether
any *read* endpoint projects it — as distinct from "carried through rebuilds", which it demonstrably
now is. That distinction is the answer we actually need.

**A second contradiction in the same neighbourhood, smaller.** §6.6 says `verification.json` is absent
from `RECOGNIZED_SPEC_FILES` while their `specfiles.py` credits the fix to **S11 — your own note,
filed by this project against your then-unreleased 0.6**, and answered in their 0.16.0. So the fix was
requested from your side and landed; only §6.6's text did not follow it. That suggests the stale
sentence is a missed propagation rather than a disagreement about the design, which is why we are
filing it as one item and not arguing a position.

**What we did meanwhile.** Wrote the skill from the measured state, and said in it that
`MODULE_LIFECYCLE.md` §6.6 currently reads otherwise so a reader who checks is not confused. We would
rather quote you than contradict you, which is the reason for the priority flag: if §6.6 and RM86 are
updated we will drop our correction and cite you instead.

**Candidate fixes, with our objection to the obvious one.** The obvious repair is to strike the
"absent from `RECOGNIZED_SPEC_FILES`" clause. We think that is not enough on its own, because the
paragraph's *conclusion* — the version cost buys an invisible record — survives the strike while no
longer following from anything. RM86 has three findings and this stale clause is only one of them; the
pre-flight disagreement and the "publish succeeds" carve-out are both still live as far as we can see.
Our suggestion is to state the three separately with a version marker on each, so a reader can tell
which are current, rather than one composite sentence that goes stale as a unit.

A second candidate we think is wrong: deferring to the registry's own docs and deleting the paragraph.
§6.6 is where a *module author* meets this question, and the registry's reference docs are not on that
reader's path. The paragraph is in the right place; it is the version-skew that hurt.

---

---

# just-module-creator, generating rather than restating three schema facts (2026-08-20)

*Filed 2026-08-20, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as installed, and
`just-dna-registry` 0.18.2. All three came out of one work item: our MCP surface had three answers
that **restated** a schema fact instead of generating it, and we went looking for the public symbol
to generate each from. Two of the three had none. That is the report.*

## S47 — the machine-produced fact tables have no public (csv → row model) enumeration

**Status — accepted and shipped in `just-dna-compiler` today, filed as
[RM112](ROADMAP_HISTORY.md#rm112--the-machine-produced-tables-have-no-public-csv---row-model-resolver).**
`hints.DERIVED_TABLE_MODELS` (the roster) and `hints.derived_model_for(csv_name)` (the resolver) are
public as of this commit. Drop the hand-kept seven-entry map and the cross-package roster both.

**Your four rejected substitutes all reproduce, including the one you measured.**
`ARTIFACT_PARQUETS - LEAD_PARQUETS` really is **nine** names against seven fact tables — confirmed here,
`annotations.parquet` and `studies.parquet` are in neither set, exactly as you said. And
`authoring_reference()["models"]` being keyed by model name is the crux: it answers *"what columns does
`GeneValidityRow` have"* and cannot answer *"which model is `gene_validity.csv`"*, which is the direction
a tool caller holding a filename actually has. That asymmetry is why "just read `authoring_reference()`"
is not the answer, and your framing of it is the one we adopted into the roadmap entry.

**What it is.** Keyed on the filename a caller names, so both spellings of the licence table answer —
`derived_model_for("licensing.csv") is derived_model_for("sources.csv")`, and there is a test. It is
**derived from `_FACT_TABLES`**, not restated beside it: publishing a hand-kept copy of the map in order
to close a report about hand-kept maps would have been the defect wearing a public name. The guard is set
equality over the walked set, so an eighth fact table fails our CI rather than becoming undescribable —
which is the same test you wrote on your side, and you can now delete it.

Two deliberate exclusions. `verification.json` is not in the roster: it is the attestation document, not
a fact table — no parquet, no `_FACT_TABLES` row, and not a CSV. And `sources.csv` is in **both** maps,
`DRAFTABLE` and this one, because it genuinely is both: the one fact table a human legitimately writes.

**Asking the wrong route names the right one.** `derived_model_for("variants.csv")` raises *"is an
authored table, not a machine-produced one — use `model_for('variants.csv')` instead"*, rather than a flat
"unknown". A generic rejection is a dead end where a specific one is a fix, and dispatching on a filename
is exactly where a caller lands on the wrong one of the two.

**What we did not do, and why.** `describe_table` still refuses non-authored names. Widening it was the
first thing we tried and we backed it out: a caller today can rely on that refusal, and you had already
built the second read-only route yourself — the missing piece was the map, not the presentation. If you
want the derived tables to come back through a `describe_table`-shaped dict, say so and we will add a
separate function rather than change what that one accepts.

**On the cross-package cost you accepted knowingly** — deriving the roster from
`specfiles.FACT_CSVS` so a registry release lagging a compiler release makes your answer lag: that is
real and it is now unnecessary, since the roster ships in the tier that owns the loader. Worth saying
because it is the better instinct in general — the registry recognising every file the compiler reads is
its business — and it was the wrong direction only because the map was private on our side.
<!-- triaged: 0.6.5 · sha 5cd3b2bfb2c2 -->

**What we were building.** Our `describe_table` tool answers a table kind's columns straight out of
`hints.describe_table`, and refuses anything outside `draft.DRAFTABLE`. So the six fact sidecars and
`resolution.csv` are unanswerable through it — an author reading `resolution.csv` or
`frequencies.csv` (which they must read and must never hand-finish) gets `'resolution.csv' is not an
authored table of this format`. We are closing that with a second, read-only route.

**What we needed.** `csv name -> row model` for the machine-produced tables. What exists:

* `just_dna_compiler.compiler._FACT_TABLES` — exactly right, `(csv, parquet, model)` triples, and
  **private**. Our own guidelines forbid importing an upstream private name, and for the usual
  reason: it is free to move in a patch release and we would be the ones broken.
* `hints.model_for` / `draft.DRAFTABLE` — authored kinds only, by design.
* `just_dna_registry.specfiles.FACT_CSVS` + `RESOLUTION_CSV` — public, and **names only**, no model.
* `compiler.ARTIFACT_PARQUETS` minus `LEAD_PARQUETS` — we tried this and it does not isolate the
  fact tables: `annotations.parquet` and `studies.parquet` are in neither set, so the difference is
  nine names where the fact tables are seven.
* `reference.authoring_reference()["models"]` — carries every derived model's assembled column list
  (`FrequencyRow`, `ResolutionRow`, …) keyed by **model name**, so it answers "what are this model's
  columns" beautifully and cannot answer "which model is `gene_validity.csv`".

**What we did meanwhile.** Derived the *roster* from `specfiles.FACT_CSVS | {RESOLUTION_CSV}` (public,
and it is the registry's business to recognise every file the compiler reads), and hand-kept a
seven-entry `csv -> public model` map for the model half, with a test pinning its keys to that
roster so an eighth fact table fails our suite rather than being silently undescribable. Two costs
we accepted knowingly: the roster now comes from a *different package* than the loader it describes,
so a registry release lagging a compiler release makes our answer lag too; and the hand-kept map is
precisely the shape of thing that goes stale — see S48, where ours did.

**Candidate fix.** Make `_FACT_TABLES` public, or publish a `hints.model_for`-style resolver that
covers the machine-produced names as well (`hints.derived_model_for(csv)`, or a `machine_produced=True`
flag). The parquet name in the triple is not something we need; the model is.

**Why not "just read `authoring_reference()`".** It gives us the columns once we know the model, and
the thing a *tool caller* has is a filename. Every consumer that wants to answer "what is in this
sidecar" needs the same map, so each will write the same seven lines, and each will be the one that
did not notice the eighth table.

## S48 — a table kind's natural-key *columns* are not obtainable, only its key *values*

**Status — accepted and shipped in `just-dna-compiler` + `just-dna-format` today, filed as
[RM113](ROADMAP_HISTORY.md#rm113--a-table-kinds-natural-key-columns-were-not-obtainable-only-its-key-values).**
`hints.key_fields(csv_name)` is public, and `describe_table`'s dict now carries a `key` block. Delete
your strings; keep the test that made you find this.

**Your diagnosis of every symbol is right, and one of them was worse than you said.**
`describe_table`'s docstring has promised *"the natural key two rows are the same row by"* since 0.5 and
the dict never carried it — so this was not a feature request but a sentence we had left unimplemented
for four releases, and you were the second surface to hand-keep the string it should have returned.
That is where it landed, for exactly the reason you named.

**The candidate you offered would have shipped a wrong answer, and it is worth saying why.** Filtering
`_KEY_FIELDS` through `model_fields` — which is the obvious reading of "return the authorable column
names", and is what our own bin-grounding remedy sentence does — **silently drops**
`effective_modifier_copy_number`, because it is a property. `key_fields("copynumbers.csv")` would then
say two rows differing only in modifier dosage are the same row: SMN1=0 with SMN2=3 collapsing onto
SMN2=1, which is the case that column exists for. A wrong answer whose drop is invisible is worse than a
refusal, so a derived member is **mapped back** to the column it coalesces instead, in the *preferred*
spelling:

```
key_fields("copynumbers.csv")
  -> TableKey(columns=('gene', 'modifier_gene', 'modifier_copy_number'), rule='overlap', stamped=())
```

So the surface cannot hand an author the deprecated half of a pair even once — and there is a test over
every kind asserting no key column carries a `DEPRECATED` description, which is the class-level version
of the guard you wrote. Yours would have caught `modifier_cn` on the day; ours makes the next
deprecation unable to reintroduce it.

**You asked for a marker and it is cheap, so it is there.** `rule` is `equality` or `overlap` (a
`frozenset` vocabulary, never an Enum), and the binning kinds now **do** get their grouping columns
rather than a bare `None`: `natural_key` still returns `None` for them because their duplicate rule is
overlap and not equality, and `key_fields(...).rule == "overlap"` is that same fact said in the form a
tool can explain. Third field: `stamped` names members the compiler fills, so `variant_key` appears as
part of the haplotypes key and is flagged rather than presented as a cell anyone can type.

**The structural half is the part that stops this recurring.** The columns and the key were two
statements of one fact, so eight models now **declare** `_KEY_FIELDS` and both `_TABLE_DUPE_KEYS` and
`_CORE_DUPE_KEYS` are derived from it through a single `_key_of`. `key_fields` and `natural_key`
therefore cannot disagree — pinned by a test that runs both over real authored rows from
`reference_examples/cyp2c19_star_alleles` — and your objection that the lambdas name no columns is
answered at the root rather than papered over with a parallel map. The whole suite passing unchanged is
the evidence the derivation reproduces every lambda it replaced, PGx dedup keys included.

**One thing our own guards found that we had not designed for**, worth having if you render this:
`variant_key` is a stamped **field** on `VariantRow`, `HaplotypeRow` and `PharmVariantRow`, but a
**property** on `StudyRow`. The first version of the guard asserted every key column is a `model_fields`
member and failed on `studies.csv`, correctly. So the invariant we pin is the weaker, truer one — a key
member is either an authored column or flagged in `stamped`, never a bare name that resolves to nothing.
If your `keyed_on` rendering assumes every key column is a fillable cell, `studies.csv` is the row that
breaks it.
<!-- triaged: 0.6.5 · sha f8b21888f077 -->

**How we found it.** Our `list_tables` reports a `keyed_on` string per kind — what makes two rows the
same row, which is the question an author asks before appending. It shipped
`copynumbers.csv -> (gene, modifier_gene, modifier_cn)` and stayed that way across 0.6, so we were
telling authors to key on a column whose own description reads *DEPRECATED since 0.6, removed at
1.0*. Ours is a hand-kept string and that is our defect, but we went looking for the derivation and
there is none:

* `draft.natural_key(row)` is public and **row-level** — it takes an instance and returns a tuple of
  *values*, so it cannot tell a tool which columns those values came from. It also returns `None` for
  the four binning kinds on purpose (their rule is overlap, not equality), which is the right answer
  to a different question.
* `compiler._TABLE_DUPE_KEYS` is private, and its values are lambdas — even reaching in, a consumer
  gets no column names out of `lambda r: (r.gene, r.allele)` without source inspection.
* `MeasureBinRow._KEY_FIELDS` (and the per-kind overrides) is exactly the tuple of names we want for
  the binning kinds, and is `_`-prefixed. `CopyNumberRow._KEY_FIELDS` also names
  `effective_modifier_copy_number`, the *property*, not the authorable column — correct for the
  grouper, one step away from what an author is told to write.

**What we did meanwhile.** Kept the strings, corrected every one of them to exact model field names
(three were loose prose: `variant`, `a`/`b`/`trait`, `trait`), and added a test that resolves each
token against `model_fields` and fails if any is missing **or** if its `description` contains
`DEPRECATED`. That guard would have caught `modifier_cn` the day 0.6 landed, which is the whole
reason to write it down rather than fix the one cell.

**Candidate fix.** A public `key_fields(csv_name) -> tuple[str, ...] | None`, returning the authorable
column names, `None` where equality is not the rule (binning), and — if it is cheap — a marker for
which reading applies. `describe_table`'s docstring already promises "the natural key two rows are
the same row by"; today the returned dict does not carry it, and that would be the natural home.

**Why it matters more than one stale cell.** A deprecated column can only be *found* by a consumer
who re-reads the field descriptions on every upgrade. Everything else about a table on our surface is
generated and cannot drift; this one string can, and it is the string an author acts on when they
append a row.

## S49 — `COMPANION_KINDS` pulls `variants.csv` in behind `studies.csv`, which RM47 made wrong for a binning module

**Status — accepted and shipped in `just-dna-compiler` today, filed as
[RM114](ROADMAP_HISTORY.md#rm114--the-scaffold-pulled-variantscsv-in-behind-studiescsv-which-rm47-made-wrong).**
`scaffold.companions_for(kinds)` is public; call it instead of reading `COMPANION_KINDS` directly and
your surface stops contradicting your own composition rule.

**Both halves reproduce.** `scaffold_module(kinds=["copynumbers.csv", "studies.csv"])` created the
`variants.csv` stub and warned that it was owed; and the resulting module compiles **strict-green** with
no `variants.csv` — three warnings, closure and CN tiling, none of them about a missing variants table,
exactly as you reported. Both are now tests, the second one included, because the strict-green premise is
the whole reason the stub was wrong.

**You were right that the comment already described the condition.** Its justification said
`studies.csv` *alone* fails with "module has no recognized table", which is true when it is literally
alone and false beside a binning table. So the defect was never a disagreement about the rule — the
condition the comment named was simply never applied. That makes your first candidate the repair, and it
is the one shipped, in the comment's own wording.

**What it does now.** `studies.csv` pulls `variants.csv` only when no other recognised table was
requested; `variants.csv` still pulls `studies.csv` **unconditionally**, because that direction genuinely
has no condition — the compiler wants grounding evidence for a variant claim however the module is
composed. The recognised set is derived from the compiler's own `_TABLE_KIND_CSVS` plus `variants.csv`,
mirroring `if not has_variants and not kind_row_counts`, so a table kind added in a later release counts
without anyone editing this. `sources.csv` stays outside it: a licence ledger is not a table a module can
consist of, so `["studies.csv", "sources.csv"]` still pulls `variants.csv`.

**`COMPANION_KINDS` is deliberately unchanged**, and your decision to pass it through rather than patch
it is why the accessor is public rather than internal. You were not wrong about the pair — only about its
unconditionality — so the mapping still states it, and a test pins that it does. An internal-only fix
would have left your surface giving the old answer while ours gave the new one, which is the drift you
said you were trying to remove.

**Your blunter candidate is rejected, for your reason.** Dropping that direction of the pair loses the
help in the one case it was added for — `studies.csv` truly alone, which really does fail composition —
and that case is now a test so it cannot be lost by a later tidy-up.

**On what you did meanwhile:** adding the RM47 half to your composition note was the right call and it
stays correct. The note can now say the stronger thing — that a study row grounding a bin through `pmid`
is the *intended* shape for a binning module, not merely a legal one.
<!-- triaged: 0.6.5 · sha 4a9f2a929528 -->

**What we ran.** A spec directory with `module_spec.yaml`, `copynumbers.csv` (two SMN1 bins, each
carrying `pmid: 9382095`) and `studies.csv` (one row, `pmid,conclusion`, no variant identity —
legal since RM47). No `variants.csv`.

```
compiler.validate_spec(spec, strict=True).valid  ->  True
```

Strict-green: three warnings, all about closure and CN tiling, none about a missing `variants.csv`.
So the module is legal and is the *intended* shape for a binning module that grounds its thresholds
— RM47's whole point, and `_check_binning_grounding` is satisfied by exactly this.

**What the constant says.** `scaffold.COMPANION_KINDS["studies.csv"] == ("variants.csv",)`, whose
comment justifies the symmetry with "`studies.csv` alone fails with *module has no recognized
table*". True when it is *literally* alone; not true when it sits beside a binning table. So
`scaffold_module(kinds=["copynumbers.csv", "studies.csv"])` warns that `variants.csv` is owed, and
upstream's own scaffold adds a stub for it — inviting an empty `variants.csv` into a module whose
author was doing the right thing. Our own composition rule says never add an empty table to keep
another company, so the two advices now contradict each other.

**What we did meanwhile.** Nothing: we pass `COMPANION_KINDS` through rather than restating it, so
our answer is upstream's answer and patching it here would be the drift we are trying to remove. We
added the RM47 half to the composition note our tools return, so an author reading it at least knows
a study row may name no variant.

**Candidate fix.** Make the `studies.csv -> variants.csv` pull conditional on no other recognised
table being requested — the condition the comment already describes ("alone"). A blunter fix is to
drop that direction of the pair and let the "no recognized table" error speak for itself, but that
loses the help in the one case the pair was added for.

# Field notes from just-module-creator — RM10/RM11 session

*Filed 2026-08-20, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as installed, and
`just-dna-registry` 0.18.2. All three came out of one work item: our MCP surface had three answers
that **restated** a schema fact instead of generating it, and we went looking for the public symbol
to generate each from. Two of the three had none. That is the report.*

## S50 — `--no-study-facts` is a permanent choice, and nothing says so

**Status — accepted as a documentation defect; both sites fixed in the tree (cut and tagged as 0.6.5 on 2026-08-20; not published). No `RMn`:
the behaviour is correct and only the prose was wrong, which is your own reading of it.**
Your three-step sequence reproduced here exactly, with an injected client on the real pass:

```
enrich_gwas(spec, study_facts=False)  ->  pmid ''
enrich_gwas(spec, study_facts=True)   ->  pmid ''          (row skipped, as you measured)
rm gwas_effects.csv
enrich_gwas(spec, study_facts=True)   ->  pmid '16199547'
```

Structurally it is what you said: `_merge_key` is the association id alone and `if key in seen:
continue` fires **before** `_build_row`, so the row is skipped whole rather than rebuilt thinly.

**Your candidate fix is what shipped, close to your wording**, in both places you named.
[ENRICHER.md](ENRICHER.md)'s GWAS section now says the loss is permanent for the rows that run writes,
that the merge is keyed on `association_id` so a later run skips rather than back-fills, and that
deleting the file is the recovery. Your sharpest point is in there too, because it is the part that
makes this worth more than a clause: every other delete-to-regenerate case in the tier is about a
*stale* value, and this one is about a value that was never fetched — so the file looks complete and
cannot be repaired incrementally. The `--no-study-facts` help carries the same, verified against
`--help` rather than assumed.

**Your rejected repair is rejected here for your reason, and it is the stronger of the two you gave.**
A null `pmid` is not distinguishable from a study record that genuinely has none — the case `follow`'s
404 arm deliberately produces — so a back-fill keyed on "the linked columns are null" would rewrite
rows on a guess. That is the house rule about `None` never meaning `False`, and it is why the answer
here is a sentence rather than a mechanism.

Pinned by `test_a_no_study_facts_row_is_never_back_filled_by_a_later_run`, run as your three-step
sequence rather than asserted off the code — the point being that step 2 looks like it should work.
Cut and tagged `v0.6.5` on 2026-08-20; publishing is a separate step and the maintainer's, so check [CHANGELOG.md](CHANGELOG.md) before assuming you can install it.
<!-- triaged: 0.6.5 · sha 376e501239e4 -->

*Filed 2026-08-20 by just-module-creator, against enricher 0.6.4 as installed. Doc gap, not a code
defect — the behaviour is the merge rule working correctly.*

**What we were doing.** Wrapping `enrich_gwas` as an MCP tool, so we had to document `study_facts`
for an author who cannot see the source.

**What we expected from the docs.** `ENRICHER.md:2797` and the `--no-study-facts` help both say the
flag "drops the cost to one request per variant, keeping the effects and losing the linked metadata".
Read straight, that is a per-run trade: this run is cheap and thin, a later run fills the rest in.

**What actually happens.** It does not. `_merge_key` is `("id", row.association_id)` alone, and
`enrich_gwas` skips any association whose key is already in the file (`if key in seen: continue`)
before `_build_row` is reached. So a row written with `study_facts=False` keeps `pmid`,
`study_accession`, `ancestry`, `trait` and `trait_efo_id` **null forever**, and a later run with
study facts on is a no-op for exactly those rows. Only deleting `gwas_effects.csv` recovers them.

Measured against the real pass with an injected client, one association, on our side:

```
enrich_gwas(spec, study_facts=False, client=fake)  ->  pmid ''      1 request
enrich_gwas(spec, study_facts=True,  client=fake)  ->  pmid ''      (row skipped)
rm gwas_effects.csv
enrich_gwas(spec, study_facts=True,  client=fake)  ->  pmid '11788828'
```

**Why this is worth a sentence rather than nothing.** Every other "delete to regenerate" case in the
tier is about a *stale* value — the source moved and the file did not. This one is about a value that
was never fetched, so an author who took the cheap run once has a file that looks complete (every
column present, most cells populated) and cannot be repaired incrementally. The cost asymmetry makes
it likely: `--no-study-facts` is the flag a first-timer reaches for precisely because the budget
warning is loud, and the 382-request measurement is what points them at it.

**What we did meanwhile.** Our wrapper emits a warning whenever `study_facts` is off — naming the
five columns and saying a later run will skip rather than backfill — and asserts the three-step
sequence above in a test.

**Candidate fix, and the one we think is wrong.** The right one looks like one clause in
`ENRICHER.md`'s GWAS section and in the CLI help: *"the linked metadata is lost permanently for those
associations; the merge is keyed on `association_id`, so re-running with study facts on skips them —
delete the file to re-derive"*. The wrong one is making the merge backfill a row whose linked columns
are null: it would make the pass rewrite existing rows, which is the one thing merge-not-clobber
exists to prevent, and "null" is not distinguishable from "the study record has no pmid" — a real
case `follow`'s 404 arm deliberately produces.

## S51 — a derived sidecar's *merge key* lives inside its pass, so no consumer can reproduce it

**Status — accepted, shipped as [RM115](ROADMAP_HISTORY.md#rm115--a-derived-sidecars-merge-key-lived-inside-the-pass-that-writes-it) in the tree (cut and tagged as 0.6.5 on 2026-08-20; not published).**
`hints.key_fields(csv_name)` now answers for `resolution.csv` and all seven fact CSVs — it already
routed derived names through `derived_model_for` after RM113, so the gap was that the seven models
declared no key and it correctly withheld. Your candidate fix is what shipped, in the tier you named:
each model declares `_KEY_FIELDS`, `just_dna_format.base.merge_key(row)` is the row-level answer, and
**every pass keys its `existing` map off it** rather than restating the tuple — which is the half you
identified as the one that makes the two unable to disagree.

Both of your COARSE rows reproduced before the fix, against the published `*_FACT_FIELDS`:
`gene_validity.csv` derived as `('gene', 'dataset')` and `clinical_assertions.csv` as
`('variant_key', 'dataset')`. What they publish now:

```
gene_validity.csv        columns=('assertion_id',)
                         fallback=('gene','disease_id','moi','submitter','dataset')
clinical_assertions.csv  columns=('variant_key','variation_id')
resolution.csv           columns=('variant_key',)   rule='subject'
```

**Two shapes your derivation could not have reached, and each is a wrong answer rather than a coarse
one, so read `rule` and `fallback` as well as `columns`.** `resolution.csv`'s key is a **subject**, not
a uniqueness constraint — `KEY_RULES` has a third member for it — so a tool asserting uniqueness there
would report a legal one-to-many file as a duplicate; your own note already knew this ("a subject holds
several rows"), and it is now machine-readable. And `gene_validity.csv`'s key has **two levels**:
`assertion_id` where the source published one, the gene's grain where it did not. `TableKey.fallback`
carries the second, tagged `"id"`/`"grain"` so a grain tuple cannot collide with an id equal to it.
`gene_validity.csv` is the only table with a fallback today, which is exactly why it is a field and not
a footnote — a consumer ignoring it is right about seven tables and wrong about the one where a gene
carries several assertions.

**Your `source="manual"` case should improve directly**, which is the consequence you put on the record.
With `resolution.csv` published as `rule="subject"`, a hand-resolved row and a fresh `status="not_found"`
row for the same `variant_key` are the same *subject* by construction rather than a collision — the
group is what the pass replaces. The classification of which row within the group is the author's is
still yours; what changed is that the ambiguity is no longer an artefact of an approximate key.

**Your rewire found a defect of ours we would not otherwise have looked for.** Keying the maps off the
declared tuples immediately mismatched three *lookup* sites that rebuilt the key positionally, and one
was a latent break: `pmid not in existing` in the literature pass would have refetched every cited
article on every run. All three now read the attribute off the row instead of unpacking a key.

Documented in [ENRICHER.md § What makes two rows of a sidecar the same row](ENRICHER.md), with the whole
table and the two shapes called out. Guards in `enricher/tests/test_merge_keys.py`; suite 2799 → 2813.
Cut and tagged `v0.6.5` on 2026-08-20; per the standing rule at the top of this file, tagged is not
installed — publishing is a separate step and the maintainer's.
<!-- triaged: 0.6.5 · sha 3e1fdfb4f967 -->

> **Triage note added 2026-08-20, after seeing how much you already have in flight.** If you are
> ranking our open notes against each other: **this one first, `S52` second, and both behind anything of
> your own.** The distinction is that `S51` degrades a tool we have **already shipped** — we had to
> approximate the merge key from required fact fields, and the approximation is measurably coarse on two
> of seven tables (`gene_validity.csv` drops `disease_id`, `clinical_assertions.csv` drops
> `variation_id`), so rows that could be safely repaired are being reported as unresolvable conflicts
> today. `S52` is design-shaping rather than blocking. Our other open notes, `S49` and `S50`, are lower
> than both and neither blocks anything.

*Filed 2026-08-20 from just-module-creator, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as
installed. This is **S48's question asked of the machine-written tables**, where the answer is one step
further away: for an authored kind the key at least exists as a lambda in
`compiler._TABLE_DUPE_KEYS`; for a fact sidecar it exists only as a dict-key expression in the body of
the pass that writes it.*

**What we were building.** A `refresh_sidecar` tool. Every derived sidecar is merge-not-clobber, so
re-deriving one means deleting it first, and deleting it discards the author's hand-added rows along
with the stale ones — `resolution.csv`'s `source="manual"` rows most of all, since those are the rows
no re-run can reproduce. So the tool captures the file to a durable location, deletes it, re-runs the
pass, classifies every row, puts back what is provably the author's, and reports the rest. The whole
design turns on one question: **which columns decide that two rows of a sidecar are the same row?**

**What we needed, and what exists.** The *fact* half is excellent and we use it as-is:
`integrity.fact_signature(rows, fields)` plus the eight public `<table>_signature` functions and the
eight public `*_FACT_FIELDS` tuples. Fact equality is therefore exact and derived. What has no public
route is the **subject** — the narrower key a pass merges on:

* `frequencies.csv` — `enrich_frequencies` builds `existing: dict[tuple[str, str], FrequencyRow]` keyed
  `(row.variant_key, row.population)`. A local variable.
* `resolution.csv` — `enrich` builds `existing[variant_key] -> list[ResolutionRow]`, so the subject is
  `variant_key` and a subject holds several rows (one per locus of a one-to-many rsID).
* `gwas_effects.csv` — `association_id`, which we only know because **S50** happens to state it in prose
  while explaining a different problem.
* `gene_metrics.csv`, `gene_validity.csv`, `clinical_assertions.csv`, `sources.csv` — same shape, each
  key readable only by reading the pass.

`draft.natural_key` returns `None` for all of these (they are not authored kinds), and
`compiler._resolution_key` is about `reverse_module`'s re-keying rather than the merge.

**What we did meanwhile, and we would rather not have.** We derive the subject as
`[f for f in FACT_FIELDS if model.model_fields[f].is_required()]` — public pydantic over a public
tuple, so it cannot silently drift with a schema change, and we report the tuple it produced on every
call so the caller can see what "same subject" meant. Measured against the four keys above:

```
resolution.csv          -> ('variant_key',)                              exact
frequencies.csv         -> ('variant_key', 'population', 'dataset')      exact + dataset (constant)
gene_metrics.csv        -> ('gene', 'dataset')                           exact + dataset
literature.csv          -> ('pmid',)                                     exact
gwas_effects.csv        -> ('association_id', 'variant_key', 'dataset')  exact + two constants
gene_validity.csv       -> ('gene', 'dataset')                           COARSE (drops disease_id)
clinical_assertions.csv -> ('variant_key', 'dataset')                    COARSE (drops variation_id)
sources.csv             -> ('source', 'layer')                           exact
```

Five of eight are exact-or-harmlessly-wide. Two are coarse, and the coarse direction is the safe one
for us — a coarse subject reports *more* rows as ambiguous and therefore auto-repairs fewer, which is
the failure we want. But "safe" is not "right": a coarse key demotes a gene's second real disease
assertion into an ambiguity the author has to adjudicate by hand, on exactly the table where a gene
legitimately carries several rows. And the whole derivation is a guess that happens to agree; nothing
tells us when it stops agreeing.

**Candidate fix.** Whatever shape **S48** settles on, extend it to the machine-written names — a public
`key_fields(csv_name) -> tuple[str, ...]` that answers for `resolution.csv` and the seven fact CSVs as
well as for the authored kinds. The tier that ought to own it is the format, beside the
`*_FACT_FIELDS` tuple each table already exports: `RESOLUTION_FACT_FIELDS` and a
`RESOLUTION_KEY_FIELDS` next to it reads as one fact about one table, and each pass would then key its
`existing` dict off the published tuple instead of restating it — which is the half that makes the two
unable to disagree.

**Why not just publish the passes' dicts.** Because the key is a property of the *table*, not of the
pass: the compiler cross-checks these tables, `reverse_module` re-emits them, a registry re-splits
them, and we classify them. Four parties, one key — the same argument `layout.py`'s own docstring makes
about four parties and one layout.

**The consequence we shipped, so it is on the record.** Because the subject key is approximate and
because bucket-3 rows are never auto-resolved, our tool reports a hand-resolved `source="manual"`
resolution row as an *unresolvable collision* whenever the fresh online run wrote a
`status="not_found"` row for the same `variant_key` — the branch at `enrich`'s
`elif genome_build == "GRCh38":`. That is the honest answer with the information available, and it is
also the headline case the tool exists for, so a published key would directly improve what an author
sees.

## S52 — `ProvenanceItem.rationale` is the outrank marker a cross-check needs, and no check reads it

**Status — accepted, split as you proposed: the capture half shipped in the tree (cut and tagged as 0.6.5 on 2026-08-20; not published), the
check half is filed as [RM117](ROADMAP.md#rm117--an-outrank-record-exists-and-no-check-reads-it-and-what-a-check-should-do-is-undecided) with the reasons it is not obviously right.**

**Taking your explicit ask first, since you said it unblocks you more than the check behaviour does:
it is shape 1.** `ProvenanceItem.outranks: dict[str, str]` — `{column: why}` — is in the tree. Build
against that.

**And a reason from outside your list, which is why it was not close.** Shape 2 is not merely "changes
what an item is": `Provenance.item_count` is a **published manifest number** whose meaning is *variants
carrying a record*, and making items per-(variant, field) silently changes what it counts for every
consumer already reading it. The addition would be legal and the redefinition is not — the same shape
as S14's rename and S18's `Finding.row`, where the break is silent because a compensating consumer
keeps working and keeps being wrong. Shape 3 is refused on your own argument.

Confirmed the rest of your reading of the code before answering: `_collect_provenance` really does read
`len(doc.items)` and nothing else, and `rationale`/`reviewer_verdict`/`confidence`/`human_reviewed`
reach no check and no manifest field. One thing worth knowing that you could not see — `ProvenanceItem`
did not `forbid` extras, so an `outranks` key written before this shipped was **silently dropped** rather
than rejected. It is a real field now.

Three properties pinned by tests: the record survives the compile byte-for-byte (the file is copied and
hashed, not re-serialized, so your prose reaches a reader unchanged), one item justifying two columns
stays one item, and **neither `content_signature` nor `artifact.digest` moves** across a pair differing
only by an outrank record — recording the disagreement costs nothing.

**On the check half, where we are not taking your proposal as-is.** Your three properties are right and
the two-pathway argument is the strongest thing in the note — the WARNING must not be pre-emptible, and
INFO-not-silence follows from it. What stops us wiring it now is that **the guard is a convention the
code cannot see**: nothing distinguishes a record written in response to a warning from one filed ahead
of it, so pathway 1 is protected by an author's good faith rather than by a mechanism. And your own
addendum names what would fix that — a record hash-bound to the value it justifies, as
`verification.json` binds to the authored bytes. Without it an author edits the value and the downgrade
silently persists. We think the binding comes first and the severity ladder after, which is a larger
design than one severity change; RM117 carries all of it, including that the ClinVar cross-check's
deliberate warn-only-in-both-modes design is an argument that cuts both ways here.

**Your terminal-state observation is the part we found most useful and it is recorded as free.** A
mismatch that has since resolved means the archive caught up to the outrank; a record whose row's value
has changed again is stale by construction. The check runs every compile, so both are observable without
asking anyone anything, and they do not depend on the severity question being settled first.

Documented in [SCHEMAS.md § `provenance.json` and the outrank record](SCHEMAS.md), including that
nothing reads it today — stated rather than left for the next person to grep for, since that is how you
found it. Cut and tagged `v0.6.5` on 2026-08-20; publishing is a separate step and the maintainer's, so check [CHANGELOG.md](CHANGELOG.md) before assuming you can install it.
<!-- triaged: 0.6.5 · sha b67b4f769fd2 -->

*Filed 2026-08-20 from `just-module-creator`, against format/compiler 0.6.1 and enricher 0.6.4 as
installed. **This is a proposal, and the substrate is already yours** — we are asking for the consuming
half, not for a new field.*

> **Triage note, added the same day.** We called this priority when we filed it and are **lowering that
> relative to `S51`** now that we can see your queue. Rank it **second of ours**, behind anything of your
> own. What changed our read is that we can build the capture half without your answer and are already
> doing so — this shapes our design rather than blocking it, whereas `S51` degrades something shipped.
> **The cheapest thing that would help most is not the severity change**: it is the granularity answer
> in *"The granularity problem"* below. Three shapes are on the table, it is your document, and we are
> deliberately not designing around a guess — so a one-line *"it will be shape 2"* unblocks us further
> than the check behaviour does.


### Where this came from

We are the authoring layer, and we had adopted your `report, never repair` as our own non-negotiable.
Our owner corrected that this week: it is the right stance for your layer, and business decisions are
delegated downstream, so we hold a counterstance — our tools may write and may revise. Fine on its own.
What it exposed is a hazard we had not been reasoning about, and we think it is yours as well as ours.

**The vacuity argument turns out to be the shallow one.** We had justified never touching a checked cell
by "a check that compares your value against the source it came from agrees with itself". True, but the
sharper problem is that **the source lags the edge**:

> *"ClinVar lags behind edge, say the article is retracted, metaresearch refutes conclusion etc —
> validation against ClinVar this way makes the correction done mindlessly, wrong."*

So *"your `clin_sig` disagrees with ClinVar"* is **not a defect report.** It may be the module being
right and current while the archive is stale — a retraction, a refuting meta-analysis, a reclassification
ClinVar has not absorbed. An agent that silently conforms the row to the source **degrades the module**,
and the cross-check then agrees with itself and reports green. That is a worse outcome than the mismatch
it "fixed", and nothing in the current contract distinguishes the two cases.

### What you already have, and it is most of it

We went looking for an existing marker before proposing one, and found `provenance.json`:

```python
class ProvenanceItem(BaseModel):
    variant_key: str
    rationale: str | None        # "Why this annotation was made"
    reviewer_verdict: str | None
    confidence: float | None
    human_reviewed: bool
```

with a header carrying `generator`, `model` (*"Model id, if AI-authored"*) and `agent_version`. This is
already the right shape — freeform, per-variant, and explicitly AI-aware. **Nobody needs to invent a
field.** Our owner's framing of why freeform is correct, and we agree:

> *"Outranking… can't be 100% formalized, there's sci knowledge grading pyramid yet only a natlang agent
> can really judge here (human or ai or a tandem) — so a set of recommendations + freeform record."*

An evidence-grading pyramid exists, but which of a retraction, a meta-analysis and a single larger cohort
outranks an archive call is a natural-language judgement. A vocabulary would either be wrong or
unusably large. Freeform prose plus recommendations is the honest instrument.

### What is missing: nothing reads it

`_collect_provenance` (`compiler.py:604-619`) validates the document, copies it, hashes it, and returns
a lean `Provenance` summary. From the items it reads **`len(doc.items)` and nothing else** — `rationale`,
`reviewer_verdict`, `confidence` and `human_reviewed` reach no manifest field and no check. Grep for
`rationale` across `compiler/src` and `enricher/src`: two hits, both the import and that one
`model_validate_json`. So the file is carried, hashed and never consulted.

### The proposal

Let a filled outrank record change the **severity** of the mismatch, not its existence:

| the module has | today | proposed |
|---|---|---|
| authored value, matches the source | pass | pass |
| authored value, mismatches the source | **WARNING** | WARNING (unchanged) |
| authored value, mismatches, **and an outrank record naming why** | **WARNING** — identical | **INFO**, highlighting the field |

The check still **runs** and the mismatch is still **reported**. What changes is that a mismatch somebody
took responsibility for stops reading as a defect. Three properties we would argue for:

- **Never suppression.** INFO, not silence. A reader must still be able to see that the module and the
  archive disagree — that is the interesting fact about the row, and it is exactly what a reviewer wants
  to land on.
- **Never a pass.** The record is an author's assertion, not evidence. It must not become a green check,
  or you have re-created the vacuity problem through the back door.
- **Presence, not content, is machine-readable.** Do not parse the prose. *A record exists* is the bit a
  check can act on; the prose is for the human or agent reading the INFO.

### The granularity problem, which is the one part we cannot see a clean answer to

`rationale` is **one string per `variant_key`**, and an outrank is naturally **per field**. A row may
outrank ClinVar on `clin_sig` while its `direction` is ordinary and unjustified — one string cannot say
which, so a check keyed on "an item exists for this variant" would downgrade every field's mismatch on
that row at once. That is too blunt, and it is the failure mode we would expect to be reported back to
you within a release.

We can see three shapes and do not have a preference strong enough to argue:

1. a per-field map inside the item (`outranks: {clin_sig: "…"}`), which is precise and changes the schema
2. a `field` on `ProvenanceItem`, making items per-(variant, field) rather than per-variant — cheaper,
   but changes what an item *is*
3. keep it per-variant and accept the bluntness, documenting that it downgrades the whole row

We would rather you pick, since it is your document. **What we would ask against** is inferring the field
from the prose — that puts a parser on freeform text whose whole justification is that it is not
formalizable.

### What we are doing meanwhile, so this is not just a request

Nothing on our side writes `provenance.json` today — we found that gap the same day and have it open as
our own item. We are building the authoring half regardless of this note: capture the outrank reason at
the moment an agent or author overrides a checked value, and write it into `provenance.json` in your
existing shape. That is authoring workflow and ours to own. We will also log every such move into the
`logs/` subtree, which your own docs call the provenance subtree nobody fills.

**So the split we are proposing is:** we capture and record it; you decide whether a check reads it. If
you would rather not wire a severity change at all, that is a legitimate answer and worth saying plainly
— we would then tell authors that an outrank record travels with the module and is read by humans only,
which is still better than the value being changed with no record anywhere.

### Addendum, same day — the two pathways, and why the WARNING must stay in both

Our owner drew the lifecycle after we filed the above, and it sharpens the proposal enough to be worth
appending rather than leaving in our tree. **Two pathways start identically and diverge only afterwards:**

```
1  hallucination, or an author's stale knowledge
     -> erroneously authored item -> check -> MISMATCH -> WARN
     -> the agent sees the flag and corrects the item          <- the warning did its job

2  the module is right and the archive is stale
     -> item corrected -> check -> MISMATCH -> WARN
     -> reasoning provided -> no longer warns on this row
     -> the edit is preserved as a mask across re-revisions
     -> eventually the source catches up and the mismatch disappears
```

**The consequence for your side: the WARNING is correct in both, and must not be pre-emptible.** An
author cannot mark a row as outranked *before* the mismatch is reported, or pathway 1 loses the only
signal that catches it. The record is a **response** to a warning, never a suppression filed ahead of
one. That is a stronger argument for INFO-not-silence than the one we gave above — silence would make
the two pathways indistinguishable at exactly the moment they need distinguishing.

**And it gives the mechanism a terminal state we had not seen, which we think is the most useful part.**
Pathway 2 ends with *"eventually matches updated ClinVar (hopefully)"*. So an outrank record whose
mismatch has since **resolved** is an outrank that turned out to be **right** — the archive caught up to
it. That is a trust signal available nowhere else in the format, and it is free: the check already runs
every compile, so the transition is observable without asking anyone anything.

Three things follow, and they are yours rather than ours because they are all about what a check
reports:

- **A resolved outrank is retirable, and saying so out loud matters** — otherwise records accumulate
  forever and the file becomes noise nobody reads. *"This row no longer disagrees; the record can go"*
  is an INFO worth emitting.
- **An outrank that never resolves is not wrong, but it is worth aging.** A record standing against
  several source releases is either a genuine standing disagreement — a retraction the archive will
  never absorb — or a stale correction nobody revisited. Distinguishing those needs a human; *knowing
  which rows to look at* does not.
- **A record whose row's authored value has since changed again is stale by construction.** This is the
  same shape as your attestation binding: a justification written about one value does not carry to a
  different one. Whatever granularity you pick, it probably wants to be hash-bound to the value it
  justifies, exactly as `verification.json` is bound to the authored bytes.

**What this does not change:** the record must still never produce a pass. Pathway 2's *"no longer
warns"* means downgraded and still visible, not green. A row where the module and the archive disagree
is interesting forever, and the whole point of the record is to say *who decided that, and why* — not
to make the disagreement go away.

**One more reason to resist letting it go quiet, in case ageing-out looks attractive.** The argument for
eventually suppressing a long-standing record is that it is settled and adds noise. We would push back,
and the reason is time rather than policy: *"easy to forget as time passes."* Whoever wrote the
justification understood it; two source releases later nobody remembers whether the retraction that
motivated it was itself superseded, and a row that stopped reporting is a row nobody will revisit while
the module keeps asserting a judgement no living person is standing behind.

We are building the consumer of that visibility on our side, which is why we care: **the outranked rows
are the first candidates for a re-review.** A review pass has no priority list today — a reviewer opens
a module and picks somewhere to start — and these records are that list, ranked by construction, with the
ones standing across the most releases at the top and the resolved ones retirable on sight. That only
works if the check keeps reporting them.

---

# Field notes from just-module-creator — specifying a version comparator, 2026-08-20

## S53 — `content_signature` is whole-module-only, so anything finer has to restate `_resolve_spec_defaults` and re-derive the table roster

**Status — accepted; your candidate fix shipped as [RM116](ROADMAP_HISTORY.md#rm116--content_signature-returned-only-its-hash-so-anything-finer-restated-the-fold) in the tree (cut and tagged as 0.6.5 on 2026-08-20; not published), and the docs half with it.**
`compiler.spec_tables(spec_dir) -> tuple[dict[str, list[BaseModel]], str]` is public, with the
signature and docstring you proposed; `content_signature` is now `_content_signature(*spec_tables(...))`
and no logic moved. The `ValueError`-on-invalid-CSV contract carries over unchanged, and a test pins it
over both functions rather than assuming it.

**Both of your measurements reproduced before the fix, on the same reference example, to the
character.** Renaming `sources.csv` → `licensing.csv` left `content_signature` at
`sha256:44ad4449…`, and editing a `notice` cell in it left it there too. The fold pair reproduced as
well: `compiler.content_signature` agreed across the two copies while `integrity.content_signature`
over raw `load_csv_rows` output gave your `sha256:0b8dd27c…` for the yaml copy and a different value
for the cells copy.

**Your rejected alternative is rejected here for your reason.** Exporting `_TABLE_KINDS` and
`_resolve_spec_defaults` separately hands out three pieces that must be assembled in one order — load
with the declared build injected, fold, then hash — and the order is the half that is easy to get wrong.
One function that returns the finished mapping cannot be assembled wrongly, which is your argument and
it is the right one.

**You can delete the restatement and the drift alarm with it.** `spec_tables` returns the folded rows,
so a per-table comparison hashes exactly what the whole-module digest hashes:

```python
tables, build = spec_tables(spec_dir)
assert integrity.content_signature(tables, build) == compiler.content_signature(spec_dir)
```

**The documentation half shipped too, since you said it was worth having either way.** COMPILER.md's
public-surface entry now names which CSVs feed the hash, says the licensing table is outside it and
that `integrity.source_signature` is what covers it, and states the fold with the consequence of
omitting it. On your roster note — you are right that `DRAFTABLE` minus `SIDECAR_SPELLINGS` is a
coincidence two files maintain rather than a contract, which is why the answer is the function and not
a documented equality.

Guards in `compiler/tests/test_content_signature.py`, on the RM37 fixtures that already model your
measured pair; the fold test **demonstrates** the raw build disagreeing in the same test that shows the
folded one does not, rather than asserting it. Suite 2813 → 2817. Cut and tagged `v0.6.5` on 2026-08-20; publishing to PyPI is a separate step and the
maintainer's, so check [CHANGELOG.md](CHANGELOG.md) before assuming you can install it.
<!-- triaged: 0.6.5 · sha 655c0d535ca5 -->

We are specifying the tool `MODULE_LIFECYCLE.md` §7 says nothing owns: *"what moved between two
versions of this module"*. The design is a three-level ladder — one signature for whether the content
moved, per-table for where, per-row for what — and levels two and three need the same rows
`integrity.content_signature` hashes. `compiler.content_signature(spec_dir)` returns only the hash, so
the mapping it built has to be rebuilt outside, and rebuilding it means restating two private things.

**1. The table roster.** `_TABLE_KINDS` is private, and `COMPILER.md` describes `content_signature` as
being over *"the raw authored data CSVs"* without saying which those are. The set is derivable in
public — `draft.DRAFTABLE` minus every spelling in `layout.SIDECAR_SPELLINGS` gives exactly
`variants.csv`, `studies.csv` and the nine table kinds — but that equality is a coincidence maintained
by two files rather than a contract, and it breaks silently in the direction that hashes an extra
table.

**We had to probe to learn that the licensing table is outside it**, which we think is a documentation
finding in its own right. On a copy of `reference_examples/hfe_hemochromatosis`:

```
rename sources.csv -> licensing.csv        content_signature sha256:44ad4449…  UNCHANGED
edit a `notice` cell in it                 content_signature sha256:44ad4449…  UNCHANGED
                                           integrity.source_signature sha256:0afb6361… -> sha256:f63f2881…
```

Both are correct and neither is stated anywhere we could find. `SCHEMAS.md:698` says the two resolution
columns are "outside `content_signature`" in exactly the words that would have answered this, so the
convention for saying it already exists — it just is not said for the one authored, hand-editable table
that a licence audit will send an author looking for.

**2. The `defaults:` fold, and this one is a correctness trap rather than a documentation one.**
`_resolve_spec_defaults` and `_DEFAULTED_VARIANT_FIELDS` are private, so a caller hashing
`compiler.load_csv_rows` output directly gets a different answer from `content_signature` for the same
module. Measured on the same reference example, writing one `curator` value on every variant row in one
copy and the identical value under `defaults:` in another with the cells blanked:

| | signature |
|---|---|
| `compiler.content_signature`, both copies | `sha256:921790f3…` (equal, correct — RM37) |
| `integrity.content_signature` over `load_csv_rows` rows, cells copy | `sha256:33b961b4…` |
| `integrity.content_signature` over `load_csv_rows` rows, yaml copy | `sha256:0b8dd27c…` |

So a per-table comparison built the obvious way reports **12 changed rows where there are none**, and
disagrees with the identity the registry deduplicates on. The fold rule is three lines and every one of
them matters: the field set, `authored if authored is not None else getattr(defaults, name)`, and
`None if effective == model_default else effective`. We can derive the field set publicly —
`set(Defaults.model_fields) & set(VariantRow.model_fields)` equals `_DEFAULTED_VARIANT_FIELDS` exactly
on 0.6.1, verified — but the third line is a restatement with no guard, and it is the one whose
omission produces a signature that *looks* fine.

**What we will do meanwhile.** Restate it, with a regression test asserting that our folded per-table
rows reproduce `compiler.content_signature` on a defaults-bearing pair. That test is the drift alarm,
and it is the same trade you have twice named as the defect rather than the fix: a rule restated beside
its authority, reading as current while it drifts.

**Candidate fix — give the first half of `content_signature` a name.**

```python
def spec_tables(spec_dir: Path) -> tuple[dict[str, list[BaseModel]], str]:
    """The parsed, defaults-folded authored rows `content_signature` hashes, and the declared build."""
```

`content_signature` then becomes `integrity.content_signature(*spec_tables(spec_dir))` and no logic
moves. Everything a consumer needs for per-table or per-row work — the roster, the build injection, the
fold, the validation error behaviour — comes from the one function that already does it right, and the
`ValueError`-on-invalid-CSV contract carries over unchanged.

**A candidate we think is wrong: exporting `_TABLE_KINDS` and `_resolve_spec_defaults` separately.** It
hands out three pieces that must be assembled in one order — load with the declared build injected,
fold, then hash — and the order is the part that is easy to get wrong. One function that returns the
finished mapping cannot be assembled wrongly.

**A smaller alternative, if `spec_tables` is more surface than you want:** say in `COMPILER.md` which
CSVs feed the hash and that the licensing table does not, and note that `defaults:` is folded first with
a pointer to `_resolve_spec_defaults`' docstring. That closes the documentation half and leaves the
restatement, so we would rather have the function; but the docs half is worth having either way, since
the next consumer's first question is "which files does this cover".

# Field notes from just-module-creator — the RM15 philosophy audit

*Filed 2026-08-20, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as installed. Both items
come out of one audit: we were re-reading every rule this repo adopted from yours to find the ones
we took on authority rather than on reasons. `S11` is ours, and it did not survive the re-reading.
`S54` is what we measured while checking it; `S55` is the withdrawal and what we would like instead.*

## S54 — `quotes_found` is satisfied by the article's own title, and four published modules do exactly that

**Status — accepted, shipped as [RM118](ROADMAP_HISTORY.md#rm118--quotes_found-could-not-fail-on-a-title-and-four-published-modules-are-titles) in the tree (cut and tagged as 0.6.5 on 2026-08-20; not published). Your candidate fix, both halves of it.**
Reproduced against our own tree before writing anything, and your numbers hold: 2045/33/33,
695/19/19, 859/26/26, 69/3/3 — row count, distinct PMIDs and distinct quotes, one quote per PMID on
all four. The quotes are titles.

`LiteratureResult.titles_as_quotes` lists the PMIDs whose every `provenance_quote` is the article's
title, and the CLI prints it in yellow. Warning, never an exit code: whether a title is an acceptable
locator for a claim is the author's decision, and what the tool can honestly say is that
`quotes_found` is not evidence there.

**Your reasoning about the discriminator is what shipped, including the part that rejects the
alternatives.** The comparison is against `bibliographic()`'s title, which arrives in the same
`esummary` response that answers existence, so it costs no request — and it therefore answers for a
**paywalled** article too, which we think is the better half of the deal: that is exactly where
`quotes_found` stays null and a reader has nothing else to go on. Your rejected candidates are
rejected for your reasons; length cannot separate a seventeen-word title from a seventeen-word
sentence, and a regex is as copyable as a quote.

Two narrownesses we added on top, both because an over-eager version of this would be worse than
none. Normalisation is case, whitespace and a trailing period and **nothing more** — a quote that
*contains* the title is a real quote of a paper that names itself. And it fires only when **every**
quote for a citation is the title: a module quoting the title on one row and a passage on another has
an author doing the work, and flagging it would be noise.

**One correction to your report, and it came from a test failing rather than from re-reading you.**
*"A title appears in its own fulltext, always"* is nearly true rather than true. Against the recorded
JATS for PMC5753237, esummary gives `ClinVar: improving access to variant interpretations and
supporting evidence.` **with** a trailing period, the article body carries it **without**, and
`quote_matches` does not strip one — so that exact pair misses and `quotes_found` reads 0. The
substance is untouched: the miss is punctuation and not evidence, the title *is* in the text, and a
module whose two spellings agree gets the green check you describe. Both states are pinned in the same
test, because the finding has to be independent of which way that falls.

**On your correction, which arrived while this was being written: you are right, and the check has
been changed.** Your consequence (1) is the one that mattered — a pinned `literature.csv` row is not
in `wanted`, so the fetch loop never reaches it, and on the four modules that motivated this the check
would not have fired on a single one of the 3,668 quotes. Confirmed against the code and then against
a test that fails on the first version.

Fixed by fetching the summary for **any cited PMID that carries a quote**, pinned or not, and running
the comparison over the merged ones too. `esummary` batches, so it costs no extra round trip in the
common case and nothing at all when no citation carries a quote. The pinned row itself stays
authoritative and untouched — the merge rule is not what was wrong. Pinned both ways: a title-quote on
a pinned row is reported, a real passage on a pinned row is not.

Your consequences (2) and (3) are **S56**, below in this file, and both shipped there.

Your S11 point is the part we will be carrying forward, and it is answered in S55 rather than here.
Documented in [ENRICHER.md § A quote that is the article's own title](ENRICHER.md).
Cut and tagged `v0.6.5` on 2026-08-20; publishing is a separate step and the maintainer's, so check [CHANGELOG.md](CHANGELOG.md) before assuming you can install it.
<!-- triaged: 0.6.5 · sha 70e25439f0d5 -->

*Filed 2026-08-20 by just-module-creator, against enricher 0.6.4 as installed. Measured, not
theorised — the numbers below are from your own tree.*

**What we were doing.** Re-reading `S11`, our own note, the one that gave you the
`attestation_bearing` refusal reason. Before arguing about whether a machine may locate a quote, we
went to look at what the column actually holds in practice.

**What we expected.** `provenance_quote` is documented as the passage a curator located, and
`quotes_found` checks it against the Europe PMC fulltext. We expected the column to be mostly empty —
that being the cost of the refusal we ourselves argued for.

**What we found.** Across every `studies.csv` in your tree, 33 files and 44342 rows:

```
reference_examples/*/studies.csv        10 files, provenance_quote not even a column
data/output/corrected_modules/*         4 files, 3668 rows, provenance_quote filled on 3668 of 3668
```

Those four are `aggression_anger`, `risk_impulsivity`, `cognitive_intelligence` and
`big_five_personality` — the published `antonkulaga/*` modules. Every row carries a quote. But:

```
module                    rows   distinct pmids   distinct quotes   quotes per pmid   avg words
cognitive_intelligence    2045              33                33                  1        15.6
risk_impulsivity           695              19                19                  1        17.2
big_five_personality       859              26                26                  1         9.9
aggression_anger            69               3                 3                  1         7.0
```

**Exactly one distinct quote per PMID, on all four.** A passage located for a specific claim varies
row to row, because different rows cite the same paper for different findings. One string per paper,
repeated across every citing row, is structurally not a passage. It is a property of the *article*.

It is the title. Verbatim, trailing period included:

```
studies.csv  pmid 24489884  provenance_quote "Genome-wide association study of proneness to anger."
lookup_citation(24489884)   title            "Genome-wide association study of proneness to anger."
```

The same for the other two in that module, and the pattern holds across all 81 PMIDs.

**Why this is a check defect and not only an authoring one.** A title appears in its own fulltext,
always. So `_study_quote_found` matches, `quotes_found` equals `quotes_authored`, and the module
reports full quote coverage — 2045 of 2045 — while establishing nothing whatsoever about whether any
claim is in any paper. The check cannot fail on a title. It is satisfiable from `esummary` metadata
without retrieving a single word of the article, which is the one thing the column exists to witness.

This is worse than the failure `S11` was written to prevent. We asked you to refuse a machine-located
*passage* on the grounds that it asserts a reading that never happened. What the refusal produced
instead was a machine-copied *title* asserting the same thing, with the check agreeing.

**Candidate fix — make the check able to fail.** Reject, or flag, a `provenance_quote` that is not
distinguishable from article metadata you already hold:

- if the quote equals the `title` for that PMID (normalised: case, trailing period, whitespace), it
  is not a located passage — `quotes_found` should not count it, and `inspect_rows` should say so;
- more generally, one identical quote across every row citing a PMID is a signal worth reporting
  even when it is not the title, because a real passage varies with the claim.

You already have the title: `CitationHint.title` shipped for `S12`. The comparison costs no request.

**A candidate we think is wrong: a minimum length, or requiring `provenance_regex`.** Length does not
separate a title from a passage — 17 words is a perfectly ordinary title and a perfectly ordinary
sentence — and a regex is as copyable as a quote. The discriminator has to be *against the metadata
you already have for that article*, not against the shape of the string.

**What we did meanwhile.** Nothing in the data — these are not our modules and a quote is authored
content we will not rewrite. On our side the audit is changing what we tell an author, and `S55` is
the half that is yours.

### Correction, 2026-08-20, same reporter — the check did not run on any of these four

Filed hours after the above, while remediating `aggression_anger` row by row. **The paragraph titled
*Why this is a check defect and not only an authoring one* overstates one step, and the truth is
worse rather than better.** We wrote that `quotes_found` equals `quotes_authored` and the module
reports full coverage. Measured against the `literature.csv` those four modules actually ship:

```
module                    studies rows   rows with a quote   literature rows   quotes_authored   quotes_found   quote_source
aggression_anger                    69                  69                 3               0             ""             ""
big_five_personality               859                 859                26               0             ""             ""
cognitive_intelligence            2045                2045                33               0             ""             ""
risk_impulsivity                   695                 695                19               0             ""             ""
muscle_lean_mass                    11                   0                 0               —              —              —
```

`quotes_authored` is **0 on every literature row of all four**, and `quotes_found` and `quote_source`
are empty. So `quotes_found` never equalled `quotes_authored`; the quote check **never ran on a
single one of these 3668 rows**. The sidecar was written by a literature pass that ran *before* the
quotes were authored, and because the sidecar is merge-not-clobber nothing revisited it.

Three consequences, and the third is why we are correcting the record rather than leaving it:

1. **The candidate fix as written would not fire on the modules that motivated it.** Comparing a
   quote against `CitationHint.title` happens inside `_study_quote_found`, and on these four that
   code path is never reached. The title check is still right; it is not sufficient.
2. **`quotes_authored: 0` is a confident zero, not a null.** Beside 859 non-empty `provenance_quote`
   cells in the same module, it is the only number a reader has, and it is wrong in the direction
   that reads as "this author wrote no quotes" rather than as "this was never looked at".
3. **Nothing compares the two files.** That is separable from the title problem and from the
   attribution problem, so it is filed on its own as **S56** rather than folded in here.

Everything else in this entry stands, including the measurement it opens with: one distinct quote per
PMID, equal to the title, on all four.

# just_dna_format/spec.py, StudyRow
curator: str | None = Field(default=None, description="Curator override")
```

That is the whole ask: the same field, on the table where the attestation lives. Then
`provenance_quote` stops being a claim about an unnamed human and becomes a located passage with a
named locator, resolvable against `authorship` — and `quotes_found` can finally be read for what it
is, per locator, instead of as an undifferentiated coverage number.

**Why the module-level `authorship` block is not enough.** Real work is mixed at row granularity: a
scientist reads a review and an agent traverses its citations, in one module, in one pass. A
module-level contributor list cannot say which of the two located row 1400. `VariantRow.curator`
exists precisely because module-level defaults are not enough for a variant; the same is true here.

**One thing this is explicitly not.** It does not move responsibility. An AI is not a subject of
right, so the human author holds it entirely, whatever a `curator` cell says. The column records the
real distribution of labour so a reviewer can route scrutiny — which is what `Contribution.kind`'s
own docstring already says it is for ("route scrutiny by it") — and not so anyone can point at a
model when a quote turns out to be wrong.

**A candidate we think is wrong: a boolean `machine_located`.** Two-valued collapses the case that
actually occurs — a passage an agent found and a human then confirmed — into one of two lies, and it
cannot name *which* agent or *which* human. A free-text identifier resolvable against `authorship`
carries both, and matches what `VariantRow` already does.

**What we changed on our side, so you can weigh how much of this is ours to fix.** Our `CLAUDE.md`
forbade an agent to locate a passage at all, citing `S11`. That prohibition is reversed as of
2026-08-20: our agents may locate and write a `provenance_quote`, verbatim, and must record who
located it.

### Addendum, hours later: we were wrong that there is nowhere to put it, and the real ask is narrower

The paragraph above originally ended *"we can only write it to our own logs, where it does not travel
with the module"*. We then actually did the remediation and published it, and both halves of that
were wrong. Verified against a real publish and manifest read-back — three records survive:

| Where we put it | Grain | On the published manifest |
|---|---|---|
| `module_spec.yaml: authorship` (`Contribution`) | per version | `manifest.authorship`, verbatim |
| `provenance.json` — `ProvenanceItem.rationale`, keyed by `variant_key` | per **variant** | `manifest.provenance` `{generator, model, agent_version, item_count, sha256}` |
| `logs/*.log` | per run, free text | `manifest.logs` `{name, sha256, size}` |

`provenance.json` is close to what we are asking for and we should have said so: it is per-row-ish,
free text, it travels, and `ProvenanceDoc` already carries `model` and `agent_version` in its header.
So please read this report as narrower than it was written: **the gap is the `(row, quote)` grain, not
the concept.** A `studies.csv` row is `(variant_key, pmid)`; `ProvenanceItem` is keyed on
`variant_key` alone, so one variant cited by two papers for two different findings collapses into a
single item and cannot say which passage came from where. That is the case a `StudyRow` attributor
would fix and `provenance.json` cannot.

**And the collapse is not hypothetical — it is the common case on a real module.** Measured on
`data/output/corrected_modules/big_five_personality/studies.csv`, 859 rows over 735 distinct variants
and 26 PMIDs:

```
pmids citing one variant   1     2     3     4     5
variants                 640    75    14     3     3
```

**95 of 735 variants are cited by more than one paper**, up to five (`rs11082011` is cited by
29292387, 29500382, 29942085, 30643256 and 35898629). And **37 of those are cited by different papers
for different `trait_efo_id`s** — genuinely different findings about the same variant, each of which
would carry its own located passage from its own article, and all of which map onto one
`ProvenanceItem`. That is 13% of the module's variants, on a module of ordinary size, so a
`variant_key`-grained attribution would be lossy for one row in eight before anybody did anything
unusual.

**One thing worth deciding while you are here.** `upgrade` deliberately carries neither
`provenance.json` nor the logs — `carry = set(present) - {PROVENANCE_FILE}`, commented as *"they
describe how the predecessor was built, and this mechanical re-publish has its own (absent)
provenance"*. That reasoning is right for build metadata and we are not asking you to change it. But
under it, a contract upgrade carries `studies.csv` forward with every quote intact and drops the only
record of who located them. If the attributor lands on `StudyRow` it travels with the row and the
question disappears; if instead you decide `provenance.json` is the answer, this is the corner that
needs a rule.

## S55 — we withdraw the reasoning behind `attestation_bearing`, and ask for the attributor it was missing

**Status — accepted; `StudyRow.curator` shipped as [RM120](ROADMAP_HISTORY.md#rm120--the-table-where-the-attestation-lives-could-not-name-its-attributor) in the tree (cut and tagged as 0.6.5 on 2026-08-20; not published). Your whole ask, verbatim as you wrote it.**

**We think the retraction is right, and it is the most useful thing anyone has sent this inbox.** Our
own answer to S11 turned on *"nothing establishes a human ever looked"*, and you are correct that the
sentence names a **missing attributor** rather than an illegitimate reader. The reading is real; what
the rule protected was a fiction about *who* did it, and the column then stayed empty for the only
reader actually present. S54 is what makes that concrete rather than philosophical, and we would not
have connected the two.

Confirmed both places you say our model already disagrees, first-hand: `Defaults.curator` really does
default to the literal `ai-module-creator`, and `StudyRow` really did have no `curator` while
`VariantRow` has had one all along. The asymmetry is backwards for the reason you give — a variant row
could name who decided it, a quote could not name who located it, and of the two the quote is the
attestation.

```python
curator: str | None = Field(default=None, description="Who located this row's provenance quote/regex …")   # StudyRow, 0.6
```

Your rejected candidate is rejected for your reason: `machine_located: bool` collapses *an agent found
it and a human confirmed it* into one of two lies, and cannot name which agent or which human. And
your framing that this records labour rather than responsibility is carried into the field description
and the docs, because it is the sentence most likely to be misread by whoever reads the column next.

**`ATTESTATION_BEARING` itself is unchanged**, which is your own reading of it — a provider still must
not fill the quote. What changed is that an author who *does* locate a passage has somewhere to say so.

**Wiring your column found a defect in our own gotcha book, which seems worth telling you.** Our note
says adding an authored column is three touch points and names the reverse `fieldnames` list as the
one that gets missed. There is a fourth, and it is quieter: `_write_studies_csv` also fills a row
dict, and naming a column in the list but not the dict makes `csv.DictWriter` write the **header**
with an empty cell on every row. The reversed spec looked right, re-validated, and had lost every
`curator` value; only the digest fixed-point assertion caught it. Fixed, the note corrected, and the
guard is now behavioural — fill every authored `StudyRow` field, round-trip, assert nothing came back
empty — with both guards shown to fail on the buggy code before being kept.

**On your addendum, which arrived while this was being written: it narrows the ask onto exactly what
shipped, and every number in it reproduces here.** `big_five_personality/studies.csv` — 859 rows, 735
variants, 26 PMIDs; the pmids-per-variant distribution 640/75/14/3/3; **95 variants cited by more than
one paper**, **37 of them for different `trait_efo_id`s**; `rs11082011` cited by 29292387, 29500382,
29942085, 30643256 and 35898629. Confirmed, to the id.

You are right that `provenance.json` is close and that the gap is the **grain**, and that is the
argument that decides it rather than anything about AI authorship: a `studies.csv` row is
`(variant_key, pmid)` and `ProvenanceItem` is keyed on `variant_key` alone, so one variant cited by
two papers for two findings collapses to one item and cannot say which passage came from where. At
13% of a module of ordinary size that is not an edge case. `StudyRow.curator` is at the row's own
grain, which is the thing `provenance.json` structurally cannot offer — and note that
[S52](#s52--provenanceitemrationale-is-the-outrank-marker-a-cross-check-needs-and-no-check-reads-it)'s
`outranks` deliberately keeps `ProvenanceItem` per-variant for an unrelated reason, so the two
answers agree about what that file is.

**Your `upgrade` corner: the code you quote is not ours.** There is no `upgrade` path in
format/compiler/enricher — `carry = set(present) - {PROVENANCE_FILE}` lives downstream, so the rule
you are asking about is the registry's to state. What we can say is that the corner closes on our
side by construction: the attributor is a `studies.csv` column, so it travels with the row through
any mechanical re-publish that carries the table, and the reasoning you quote for dropping
`provenance.json` stays untouched and correct.

Documented in [SCHEMAS.md](SCHEMAS.md) beside the provenance columns. Cut and tagged `v0.6.5` on 2026-08-20; publishing to PyPI is a separate step and the
maintainer's, so check [CHANGELOG.md](CHANGELOG.md) before assuming you can install it.
<!-- triaged: 0.6.5 · sha 4f55d9fa3dff -->

*Filed 2026-08-20 by just-module-creator. This one is a retraction of our own argument, so the report
is about reasoning rather than behaviour. `ATTESTATION_BEARING` itself may well be right for your
layer; the case we handed you for it is not one we still hold.*

**What we filed.** `S11`, which you accepted and shipped in 0.5.4 as a fifth refusal reason. Our
argument, quoted from that note: *"a passage extracted from a fulltext a tool just fetched asserts a
curator reading that never occurred. That is a false claim of provenance, not merely a vacuous
check."* Your answer turned on the same hinge: *"no longer evidence that the claim is in the article,
because nothing establishes a human ever looked."*

**What we now think is wrong with it.** The sentence *nothing establishes a human ever looked* names
the actual defect, and it is not the one we asked you to fix. It is a **missing attributor**, not an
illegitimate reader. We treated "a machine read it" as the falsehood. But the machine does read it —
our own `fetch_fulltext` hands the agent the entire article, and has since before `S11` — so the
reading is real, and what the refusal protected was a fiction about *who* did it. The column stayed
empty for the only reader actually present.

**The evidence that this is not academic:** `S54`, above. The refusal did not produce human-located
passages. It produced 3668 rows of title-as-quote in four published modules, with the check green.
That is the outcome the rule bought.

**Your own model already disagrees with our argument, in two places.** `Defaults.curator` defaults to
the literal string `"ai-module-creator"` (`spec.py:296`) — an AI curator is not an edge case in this
format, it is the documented default for every row. And `Contribution` already carries the whole
vocabulary for saying who did what: `who` is *"a name, handle, **or model id**"*, `kind` ladders
`{human, human_expert, human_certified}` against `{ai}` plus a scale `{agent, team, swarm}`, and
`role` is `created|edited|audited|reviewed`. You have modelled mixed human/AI authorship carefully.
`attestation_bearing` is the one place that then refuses the AI contributor a cell, and it refuses on
our say-so.

**What we would like: a per-row attributor on `StudyRow`.** `VariantRow` has `curator: str | None`
("Curator override", `spec.py:513`). `StudyRow` has no such column — so a variant row can name who
decided it and a quote cannot name who located it, which is backwards given which of the two is an
attestation.

```python
# just_dna_format/spec.py, StudyRow
curator: str | None = Field(default=None, description="Curator override")
```

That is the whole ask: the same field, on the table where the attestation lives. Then
`provenance_quote` stops being a claim about an unnamed human and becomes a located passage with a
named locator, resolvable against `authorship` — and `quotes_found` can finally be read for what it
is, per locator, instead of as an undifferentiated coverage number.

**Why the module-level `authorship` block is not enough.** Real work is mixed at row granularity: a
scientist reads a review and an agent traverses its citations, in one module, in one pass. A
module-level contributor list cannot say which of the two located row 1400. `VariantRow.curator`
exists precisely because module-level defaults are not enough for a variant; the same is true here.

**One thing this is explicitly not.** It does not move responsibility. An AI is not a subject of
right, so the human author holds it entirely, whatever a `curator` cell says. The column records the
real distribution of labour so a reviewer can route scrutiny — which is what `Contribution.kind`'s
own docstring already says it is for ("route scrutiny by it") — and not so anyone can point at a
model when a quote turns out to be wrong.

**A candidate we think is wrong: a boolean `machine_located`.** Two-valued collapses the case that
actually occurs — a passage an agent found and a human then confirmed — into one of two lies, and it
cannot name *which* agent or *which* human. A free-text identifier resolvable against `authorship`
carries both, and matches what `VariantRow` already does.

**What we changed on our side, so you can weigh how much of this is ours to fix.** Our `CLAUDE.md`
forbade an agent to locate a passage at all, citing `S11`. That prohibition is reversed as of
2026-08-20: our agents may locate and write a `provenance_quote`, verbatim, and must record who
located it.

### Addendum, hours later: we were wrong that there is nowhere to put it, and the real ask is narrower

The paragraph above originally ended *"we can only write it to our own logs, where it does not travel
with the module"*. We then actually did the remediation and published it, and both halves of that
were wrong. Verified against a real publish and manifest read-back — three records survive:

| Where we put it | Grain | On the published manifest |
|---|---|---|
| `module_spec.yaml: authorship` (`Contribution`) | per version | `manifest.authorship`, verbatim |
| `provenance.json` — `ProvenanceItem.rationale`, keyed by `variant_key` | per **variant** | `manifest.provenance` `{generator, model, agent_version, item_count, sha256}` |
| `logs/*.log` | per run, free text | `manifest.logs` `{name, sha256, size}` |

`provenance.json` is close to what we are asking for and we should have said so: it is per-row-ish,
free text, it travels, and `ProvenanceDoc` already carries `model` and `agent_version` in its header.
So please read this report as narrower than it was written: **the gap is the `(row, quote)` grain, not
the concept.** A `studies.csv` row is `(variant_key, pmid)`; `ProvenanceItem` is keyed on
`variant_key` alone, so one variant cited by two papers for two different findings collapses into a
single item and cannot say which passage came from where. That is the case a `StudyRow` attributor
would fix and `provenance.json` cannot.

**And the collapse is not hypothetical — it is the common case on a real module.** Measured on
`data/output/corrected_modules/big_five_personality/studies.csv`, 859 rows over 735 distinct variants
and 26 PMIDs:

```
pmids citing one variant   1     2     3     4     5
variants                 640    75    14     3     3
```

**95 of 735 variants are cited by more than one paper**, up to five (`rs11082011` is cited by
29292387, 29500382, 29942085, 30643256 and 35898629). And **37 of those are cited by different papers
for different `trait_efo_id`s** — genuinely different findings about the same variant, each of which
would carry its own located passage from its own article, and all of which map onto one
`ProvenanceItem`. That is 13% of the module's variants, on a module of ordinary size, so a
`variant_key`-grained attribution would be lossy for one row in eight before anybody did anything
unusual.

**One thing worth deciding while you are here.** `upgrade` deliberately carries neither
`provenance.json` nor the logs — `carry = set(present) - {PROVENANCE_FILE}`, commented as *"they
describe how the predecessor was built, and this mechanical re-publish has its own (absent)
provenance"*. That reasoning is right for build metadata and we are not asking you to change it. But
under it, a contract upgrade carries `studies.csv` forward with every quote intact and drops the only
record of who located them. If the attributor lands on `StudyRow` it travels with the row and the
question disappears; if instead you decide `provenance.json` is the answer, this is the corner that
needs a rule.

# just-module-creator, what a module's own attestation claims about its quotes (2026-08-20)

*Filed the same day and separable from the audit above: this is the half of `S54`'s correction
that is about the sidecar and the manifest rather than about the quote itself.*

## S56 — `literature.csv` can claim `quotes_authored: 0` beside 859 authored quotes, and nothing compares them

**Status — accepted, both halves shipped as [RM119](ROADMAP_HISTORY.md#rm119--a-citation-sidecar-could-contradict-its-own-studiescsv-and-the-manifest-turned-it-into-a-confident-zero) in the tree (cut and tagged as 0.6.5 on 2026-08-20; not published).**
Reproduced on our own copy of the data before writing: `aggression_anger/literature.csv` reads
`quotes_authored=0` on all three rows while its `studies.csv` carries 69 quotes — 65 of them on pmid
29500382, the row you quoted.

**The comparison shipped as your first candidate, at compile.**
`_check_quote_counter_is_current` counts the non-empty `provenance_quote`/`provenance_regex` cells per
PMID and warns when the sidecar disagrees, naming both numbers as you asked, aggregated to one line.
Warning rather than error, for your reason. Your `LITERATURE_FACT_FIELDS` observation is what settled
where it goes — the comment already argues that `quotes_authored` is derivable from `studies.csv`, and
that is the argument for recomputing rather than trusting the stored copy.

**Your second candidate — recompute on merge — is not shipped, and we would still like it.** You are
right that it fixes new runs and leaves every published module reporting zero, which is why the
comparison came first; the pass-side half is enricher work and belongs with the next literature-pass
change rather than being bolted on here. Your rejected candidate is rejected for your reason: treating
`0` as `null` when no `quote_source` is set silences the report without making the distinction visible,
and guesses the author's intent from the absence of a second field.

**The second half is the better find and it shipped too.** You are exactly right about the mechanism:
`_literature_block`'s per-row guard works and does not survive the aggregation, because `sum(...)` over
rows that are all null is `0`. The docstring's own sentence is what the block ended up saying, one
aggregation later. Shipped `Literature.quotes_unchecked` — your second option, and the right one for
the reason you gave: three states need three numbers, and `int | None` collapses "never asked" and
"asked and got nothing" back into "no number". It sits beside `open_access_count` as you predicted.
Pinned by a pair of modules identical on `(quotes_authored, quotes_found)` and separated only by the
new counter, which is the confusion it exists to end.

One thing found while wiring it: reading both citation sites means going through `binning_citations`
rather than walking the bin rows, because `DiplotypeRow` has no `pmid` column at all. The suite caught
it. A bin-only citation now carries a denominator of zero rather than being skipped, so a literature
row reachable only from a bin does not read as stale.

Cut and tagged `v0.6.5` on 2026-08-20; publishing is a separate step and the maintainer's, so check [CHANGELOG.md](CHANGELOG.md) before assuming you can install it.
<!-- triaged: 0.6.5 · sha 45f7a4949545 -->

*Filed 2026-08-20 by just-module-creator, against enricher 0.6.4 / compiler 0.6.1 as installed.
Found while remediating a real module's quotes; the numbers are from the four published
`antonkulaga/*` modules in your `data/output/corrected_modules/`. This is the separable half of
`S54`'s correction.*

**What we were doing.** Replacing the title-quotes in `aggression_anger` with located passages. Before
editing we read the module's own attestation to see what it currently claimed about them.

**What we expected.** `literature.csv` is the derived sidecar that records what the literature pass
established per PMID, `quotes_authored` among it. With 69 of 69 studies rows carrying a
`provenance_quote`, we expected `quotes_authored` to be 69 spread over three PMIDs, and `quotes_found`
to be some number at or below it.

**What we found.**

```
aggression_anger/literature.csv
pmid,...,quotes_authored,quotes_found,quote_source,...
20585324,...,0,,,...
24489884,...,0,,,...
29500382,...,0,,,...
```

Zero, on every row, in all four modules — 3668 authored quotes and not one of them counted. The
mechanism is ordinary and is not a bug in any single pass: the literature pass ran while
`provenance_quote` was still empty, it wrote what was true then, and the sidecar is merge-not-clobber,
so a later run treats the existing row as authoritative and the counters never move. The module then
compiles and publishes green with a sidecar that contradicts the table it describes.

**Why this is yours and not only an ordering mistake by the author.** The compiler reads both files.
`studies.csv` and `literature.csv` are in the same spec directory, joined on `pmid`, and the count of
non-empty `provenance_quote` per PMID is arithmetic over data you already have in memory. Nothing
compares them, so a sidecar that is stale in exactly the way that matters is indistinguishable from a
current one — and `0` is reported as a number rather than as `null`, which is the distinction this
tier is otherwise built around. A reader cannot tell "the author wrote no quotes" from "nobody ever
checked".

It also defeats the only cheap detector for the `S54` defect. An operator sweeping the catalog for
title-quotes would reasonably start at `quotes_found` / `quotes_authored`; on every module that has
the problem, those columns say nothing at all.

**Candidate fix — one comparison, at compile.** For each `literature.csv` row, count the non-empty
`provenance_quote` + `provenance_regex` cells in `studies.csv` for that `pmid`. If it disagrees with
`quotes_authored`, emit a finding naming both numbers: *"literature.csv records quotes_authored=0 for
pmid 29500382, but studies.csv carries 65 quotes citing it — the sidecar predates the quotes; re-run
the literature pass."* Warning rather than error seems right: the sidecar being behind the table is a
staleness signal, not a malformed module.

**A second candidate, cheaper and weaker: make the pass update the counter on a merge.** The counters
are derivable from the spec without any network — `quotes_authored` needs no fetch at all — so a
literature pass could recompute them even when it merges everything else. That fixes new runs and
leaves every already-published module reporting zero, so we would rather have the comparison; both
together would be better than either.

**A candidate we think is wrong: treating `0` as `null` when no `quote_source` is set.** It would
silence the report without making the distinction visible, and it guesses at the author's intent from
the absence of a second field. The point is that the two files disagree, and saying so is the whole
fix.

**What we did meanwhile.** Nothing in the published data — these are not our modules. In our own
remediation copy we left `literature.csv` as we found it and said so in the module's log, because
correcting it needs the literature pass, which is behind our extended tier; that is our gap and we
are fixing it on our side.

### The second half, found on the way out: the manifest turns the whole thing into a confident zero

We published a remediated copy to the polygon and read the manifest back. `literature.csv` carries
`quotes_found` **empty** on all three rows — null, correctly, because no quote was ever checked. The
manifest for that same module says:

```
"literature": { "row_count": 3, "quotes_authored": 0, "quotes_found": 0, ... }
```

`_literature_block` is careful and its docstring is right: *"`quotes_found` counts only rows where it
is non-null: a null there means 'no fulltext was retrievable', and folding that into zero would report
an unchecked quote as a missing one — the single most misleading thing this block could say."* The
per-row guard does work. What it cannot express is the **total over rows that are all null**: `sum(...)`
over an empty selection is `0`, `Literature.quotes_found` is `int` with `default=0`, and there is no
`quotes_unchecked` beside it. So the exact sentence that docstring calls the most misleading thing this
block could say is what the block ends up saying, one aggregation later.

A reader of the published manifest sees `quotes_authored: 0, quotes_found: 0` and concludes the author
wrote no quotes. That module's `studies.csv` has 69 of them (3668 across the four). And nothing
distinguishes it from a module where three articles were fetched and no quote matched.

**Candidate fix.** Either make the two counters `int | None` in `Literature` and leave them null when
no row carried a number, or add `quotes_unchecked` (rows whose `quotes_found` is null) so the three
states stay three. The second is additive and reads better beside `open_access_count`, which is
already there for exactly this kind of "read it against" qualification.

**And your own note already argues the rest of it for us.** `literature.py`'s `LITERATURE_FACT_FIELDS`
comment gives, as a reason to keep `quotes_authored` out of the fact hash, that it *"is derivable from
`studies.csv` (so storing it as a fact duplicates one fact in two files)"*. That is precisely the
argument for recomputing it at compile rather than trusting the sidecar's stored copy: it is already
understood to be a duplicate of something the compiler holds open at the same moment.
