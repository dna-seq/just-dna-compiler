# Roadmap history — the items that shipped

Split out of [ROADMAP.md](ROADMAP.md), which is **forward-only**: it now carries active work and
nothing else. This file keeps the *rationale* of every `RMn` that shipped from the 0.6 line onward —
and, since 2026-08-21, of the ones **closed by a decision not to do them**, which leave the active
file for the same reason and are just as worth not re-deriving —
the earlier ones are in the archive named below — because a lot of it is reasoning worth not
re-deriving, including one entry that corrects an argument it originally made.

- **[CHANGELOG.md](CHANGELOG.md)** is the release record: what changed, newest first, shared across
  the ecosystem repos. This file is the roadmap-item view of the same events.
- **[RM_TOC.md](RM_TOC.md)** is the complete index of every `RMn`, active and shipped.
- **[COMPILER.md](COMPILER.md)** carries the per-feature coverage table.

`RM1`, `RM2`, `RM3`, `RM8`, `RM9`, `RM18` and `RM19` also shipped, but their entries live in
[USE_CASES.md § Roadmap items surfaced](USE_CASES.md#roadmap-items-surfaced) — where they were
derived — and were never duplicated here.

**The 0.5 line and everything before it moved to
[ROADMAP_HISTORY_PRE_0_6.md](history/ROADMAP_HISTORY_PRE_0_6.md)** on 2026-08-17 — the release narratives
through 0.5.0, and every `RMn` that shipped before 0.6. This file starts at the 0.6 design round.
[RM_TOC.md](RM_TOC.md) indexes both halves plus the open roadmap, so it is where to look an item up.



# The 0.7 build round

The items [PROPOSAL_0_7.md](proposals/PROPOSAL_0_7.md) decided on 2026-08-27/28 and the 0.7 batch then
built. Every one is additive under Principles 3 and 8; what is kept here is each entry's reasoning,
including the repairs it refused, which is the half that would otherwise be re-derived.

**The round's twelve are all here as of 2026-08-31**, which is when the last four entries left the
forward-only files they had been sitting in with a `SHIPPED` banner on them: RM126 and RM71 from
`ROADMAP_0_7.md`, RM133 and RM134 from [ROADMAP.md](ROADMAP.md). An entry marked shipped in a file that
describes what is *not* built reads as late rather than done, which is the state this move ends. The
deferral round those two came from closed at the same time —
[history/ROADMAP_0_7.md](history/ROADMAP_0_7.md) keeps it, and everything still waiting moved to
[ROADMAP_0_8.md](ROADMAP_0_8.md). RM83 is in this file as **closed, not shipped**, and RM139 was filed
by the cut itself rather than by the proposal.

**RM140 joined them on 2026-08-31 from a consumer report, after the round had closed.** It is not one
of the twelve and does not reopen the thread; it lands inside the same uncut `0.7.0`, because a new
optional column is what sizes a release and the number was already decided.
[PROPOSAL_0_7.md](proposals/PROPOSAL_0_7.md) carries its decision as a dated addendum, in the file's own
idiom, so the reasoning sits beside the twelve rather than in a thread of its own.

**And a second round joined the same uncut release on 2026-09-01: the source-adoption batch,
RM163–RM168.** Six items filed out of one sweep, every one gated on a probe that had not been run;
[PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) is its record. It is a *round* rather than an
addendum — six items decided together against a shared sort rule — which is why it has its own file
rather than joining RM140 and RM152 as a third dated note on the first thread. Five of the six build
here and RM164 parks on a measured negative, having spun off RM171. What the round is worth remembering
for is not any one adoption: **five of the six entries said something their own probe contradicted**,
and then four of the six verdicts the proposal drafted were overturned again in the maintainer pass —
so an unprobed entry is a question, and a probed one is still only a proposal.

**The round closed the same day it was decided**, which is the third drift and the one worth counting:
of the five items built, **four contradicted their own entry again during the build**. RM165's entry
proposed drafting four columns `RepeatAlleleRow` does not have. RM167's three headline measurements did
not reproduce — a gene-node count that conflated two id shapes, a locus count off by 34, and an id
grammar contradicted by the example printed beside it. RM163 offered `overrides.csv` as the author's
remedy for a finding the overlay cannot reach. RM166's licence motivation was already gone before the
build began. **RM168 is the only one of the six that held**, and it is the one whose questions were
cheapest to ask — a directory listing and a 1.1 MB download.

So the three-stage pattern is: an entry states what it believes, a probe contradicts it, a decision
overturns the probe's verdict, and a build contradicts the entry again. Each stage was cheaper than the
one before, and each caught something the previous one asserted. That is an argument for probing early
and for writing entries that can be contradicted, not for trusting any of the four stages on its own.

## RM176 — eleven builders, three stages each, and the roster that was supposed to name them was a list

**Severity** high · **Status** ✅ **SHIPPED 2026-09-02 in the uncut 0.7.0** — the cache registry, three
missing resolvers, three new publish/provision pairs, and `cache rebuild` (`just-dna-enricher`; no
schema, no vocabulary, no parquet column) · **Owner** enricher · **Motivating case** the maintainer's
2026-09-02 question — *do all the caches we build have a common rebuild endpoint, and does each have
download, build and upload?* — asked of every lane except Ensembl

**The answer was no, and the three gaps were one defect wearing three faces.** Every one was a fact
about a lane that no code anywhere asserted, because the roster was a four-tuple list inside `cli.py`.

- **Three lanes were not in it at all.** `acmg_build`, `strchive_build` and `drug_labels_build`
  existed and had no roster entry, so `cache status` reported nine caches on a machine that has
  twelve and `cache pull` refused the other three as unknown names.
- **Those same three had no resolver.** Each check took an explicit path and looked nowhere else, so
  the only way to run one against a built snapshot was to name it on every invocation. The path a
  deployment actually takes is the flagless one, and for all three it did something worse than fail:
  ACMG's fell through to scraping NCBI's page, which serves **v3.2** while the snapshot holds v3.3, so
  a correctly authored row came back reported as wrong; the other two skipped themselves with
  `no_reference` about a catalogue sitting in the cache directory.
- **Three lanes had the licence to publish and no way to.** The roster's own comment called CIViC's
  absent `ensure_*` a *gap* rather than a refusal — CC0 grants redistribution outright — and STRchive's
  MIT and the drug labels' CC BY-SA say the same on their own terms. What was missing was plumbing.

**What shipped.** `caches.CACHE_LANES` is a registry: one entry per lane, carrying its three stages
(acquire, build, publish) and, for each stage it lacks, **the reason as a field rather than a
comment**. `test_cache_lanes.py` walks it against the `*_build` modules on disk in both directions,
which is the check a list could never have (`@registry-completeness`). Resolvers and cache
subdirectories for acmg, strchive and drug_labels, each wired into the *flagless* branch of its own
check, and the tests assert the **call** rather than the resolver — a resolver nothing calls passes
its own unit test while leaving the defect exactly where it was (`@ensure-must-be-called`). Publish
and provision for CIViC, STRchive and the drug labels, with `strchive publish` and
`clinpgx publish-labels` as new commands. And `cache rebuild`, the endpoint the question asked for:
one command over eleven builders, calling the same `download_*`/`build_*` the per-lane commands call,
so there is one conversion algorithm with two callers rather than two that have to agree.

**Two shapes had to be generalized to get there, and both were premises rather than bugs.** The
publisher assumed every snapshot is `data/*.parquet`; ACMG's is `acmg_sf.csv` and STRchive's is
`STRchive-loci.json`, each at the snapshot root. `plan_reference_snapshot` now takes the payload
filename **from its caller** — a lane knows what it builds, and a roster of lane filenames inside the
publisher would make it the fourth place a new snapshot kind has to be taught about. The provisioner
could *not* be generalized the same way and is not: `_provision_snapshot` is parquet all the way down
and a JSON file has no footer to check, so `_provision_root_file_snapshot` gives the same guarantee by
parsing before the rename.

**`publish_reference_snapshot` now derives its allowlist from the plan** instead of restating it as
patterns. The two were separate statements of one thing that had to agree and twice did not — that is
how `citations/` and `LICENSE.txt` each went a release printed-in-the-dry-run and dropped-on-upload
(`@publisher-allowlist-derived`). One list, so a dry run is a promise.

**The rebuild outcome is three-valued, and the third state is the item's most load-bearing decision.**
ACMG needs a workbook that is Elsevier supplementary material, PharmVar a personal key, CIViC a release
date to pin, Ensembl is built by just-dna-pipelines. Folding those into *failed* would have a nightly
rebuild alarm on four lanes behaving exactly as their licences intend; folding them into *built* would
be a lie. They print as **not run** with the registry's own reason, and the exit code counts only real
failures. Each lane builds into `<base>/<lane>/`, **never in place** — a rebuild takes minutes and a
short parquet still has a `PAR1` footer, so an `enrich` reading a half-written snapshot sees a real but
incomplete table and no resolver can catch it.

**Two defects the suite caught rather than review**, and both are the repository's own recorded
shapes. `clinpgx publish-labels` had landed *after* the `__main__` guard, where nothing registers it.
And `cache status` composed its instruction as `f"{name} build"`, which is right for ten lanes and
names two commands that do not exist — there is no `drug_labels build` and no `constraint build` — so
`build_command` is a field the guard invokes against the real Typer tree (`@warning-text-is-api`).

**The dependency question the item also asked was already answered**: every builder-only dependency
(`polars`, `openpyxl`) is in the `[dev]` extra behind a guarded import, and no runtime check reads
either. Nothing moved.

**Four defects its own probe found, after the round looked finished**, and three of them are the
item's own shapes turned back on it. *One:* the default `cache pull` exited 1 on a fresh machine,
because three lanes gained an `ensure_*` before anyone created their repos and the transport's error
reached the blanket handler as a failure — nobody-published is the same third state as nobody-asked,
so `SnapshotNotPublished` is its own type and is printed rather than counted. *Two:*
`Path("./x.xlsx").as_uri()` raises, so `--source acmg=./workbook.xlsx` — the *documented*
invocation — produced a traceback instead of an outcome. *Three:* the PharmVar adapter reported every
exception as *not run*, folding a lane that broke into a lane that opted out; the split is decided
before the request now, from whether a key is configured at all, because the service's 401 is
identical for an absent, a malformed and an unrecognised key and a flat `PharmVarError` cannot carry
the difference (`@answered-is-not-absent`). *Four:* the CIViC adapter fetched the release VCF
unconditionally, which RM169 made opt-in because it *widens the status basis* — so one release would
have built two different snapshots depending on which caller asked, the exact fork this endpoint
exists to prevent.

**And two more the maintainer's question found, both `@credential-where-read`.** Asked whether the
endpoint handles credentials kept in a `.env`, it did not — for `$PHARMVAR_API_KEY` and `$HF_TOKEN`,
the two the operator actually holds. The PharmVar one is the worse of the pair and is this round's own
tri-state repair turned against it: the guard deciding *no key configured* versus *a key that failed*
read `os.environ` directly, while `PharmVarClient.__init__` calls `load_env()` before reading the same
variable — so the key was visible to the builder and invisible to the check standing in front of it,
and the lane claimed the designed third state on exactly the machine most likely to have a key. **A
pre-check that answers differently from the code it guards is worse than no pre-check.** `$HF_TOKEN`
failed honestly by comparison: `_hf_api` called `get_token()`, which reads the real environment and
`~/.cache/huggingface/token`, so a publish refused. Both load where the credential is read now, and
the probes run in subprocesses with the real variables stripped and `HF_HOME` redirected — otherwise
they pass on any laptop that has ever run `hf auth login`.

**Left undone on purpose.** The three new repos — `just-dna-seq/civic`, `just-dna-seq/strchive`,
`just-dna-seq/clinpgx_drug_labels` — do not exist on HuggingFace; the first publish creates each, and
until then both `ensure_*` and `cache pull` say so rather than failing obscurely. No lane's snapshot
was rebuilt or uploaded as part of this. And the PGS/PRS parquets under `just-dna-seq` are **out of
scope by decision**, not by oversight: `pgs-catalog`, `prs-percentiles`, `prs-sample-scores` and
`polygenic_risk_scores` are built by `just-prs`'s Dagster pipeline, and pulling them into this tier
would cross the dependency-tier rule the charter's Goal 2 states.

## RM175 — the PGx lane's default archive was a retired filename, and every row it had ever built came out of a frozen 2025 object

**Severity** high · **Status** ✅ **SHIPPED 2026-09-02 in the uncut 0.7.0** — the rebuild onto
`summaryAnnotations.zip` plus the guard that refuses the retired one (`just-dna-enricher`; no schema,
no vocabulary, no parquet column) · **Owner** enricher · **Motivating case** the maintainer's
2026-09-02 investigation ([CLINPGX_ARCHIVES](probes/CLINPGX_ARCHIVES.md)), which started from RM173's
canary and found what it was a canary of · **Supersedes** RM173

**PharmGKB renamed the table on 2025-07-29** ([the ClinPGx launch
post](https://blog.clinpgx.org/pharmgkb-is-now-clinpgx/)): *"Clinical annotations … are now called
**summary annotations**."* The archive followed. `clinicalAnnotations.zip` was last written to S3 on
**2025-07-05, twenty-four days before that post**, and has not been rebuilt since; it is on no
downloads page; and the API still answers it **200** through a 303 to the frozen object.
`clinpgx_build.DEFAULT_CLINPGX_URL` named it.

**So this was not a stale cache and not a slow source.** Every `annotations.parquet` this lane had
built, every PGx row drafted from it and every check that read one rested on a snapshot of the database
as it stood **fourteen months ago**, and nothing in the response said so — a retired filename that
still 200s is indistinguishable from a live one at the HTTP layer. RM173 measured the 13-month gap
correctly and diagnosed it as two live surfaces refreshing out of lockstep. It was one live surface and
one leftover.

### What shipped

`summaryAnnotations.zip`, `CREATED_2026-08-05`, is the same 15-column table under new names:

| 2025 archive | 2026 archive |
|---|---|
| `clinical_annotations.tsv` | `summary_annotations.tsv` |
| `clinical_ann_alleles.tsv` | `summary_ann_alleles.tsv` |
| `clinical_ann_evidence.tsv` | `summary_ann_evidence.tsv` |
| `clinical_ann_history.tsv` | `summary_ann_history.tsv` |
| `Clinical Annotation ID` | `Summary Annotation ID` |

The other fourteen column names are identical and in the same order, and `Phenotype Category` has the
same values with the same `;` separator, so **no vocabulary moved and no model changed**. The builder
reads two of the four members; the evidence and history siblings are renamed upstream and named
nowhere in this tier, so they cost nothing. What changed is the URL, two member names, the id column,
the numbers derived from the old file — and the guard.

**The guard is the item.** An archive carrying the old member names parses perfectly and yields a
plausible parquet, so `require_current_archive` reads the member names *before* anything else and
answers in three arms (`@answered-is-not-absent`): the current spelling builds; the retired one is
refused with the rename, its date, the retired filename and the URL to build from instead
(`@specific-rejection` — a generic "member missing" is a dead end where naming the rename is a fix);
an archive that is neither says so separately, listing what it holds. `clinpgx build` prints
`CLINPGX BUILD FAILED: …` and exits 1, matching `build-labels`.

Both spellings live in **one table** the reader takes its member names and its id column from, so the
guard cannot drift from what the builder reads (`@suppression-from-merge-key` has the same shape).
`RETIRED_ARCHIVE` is returned by nothing: no path through the module can read a 2025 archive, which is
stronger than refusing to. No compatibility layer was built, deliberately — a reader that parses both
vintages is a reader that can still publish 2025 data.

**It was not a rename-only patch, because the data moved.** Re-derived against both archives on
2026-09-02: over the 5,179 ids in both, 7 annotations gone, 11 new, **8 rows change `Level of
Evidence`**, 2 `Variant/Haplotypes`, 40 `Drug(s)`, 14 `Score`, 68 `Level Modifiers`, and every `URL`
rehosts `pharmgkb.org` → `clinpgx.org` on a path that still reads `/clinicalAnnotation/`. At the
snapshot's own grain the rebuild is 16,087 → **16,117 rows** across 5,186 → **5,190 annotations**,
1,086 → 1,087 genes: 22 (annotation, genotype) keys gone, 52 new, and among the 16,065 shared keys
30 rows change `evidence_level`, 120 `drugs`, 47 `annotation_text`, 38 `phenotypes` and 4 `subject`.
The parquet digest moves, and a module drafted from this lane can see an evidence level change under
it — which is correct, and is the first thing this lane has ever had to say about currency.

**And one recorded number was wrong twice.** `clinpgx_build`'s docstring said *"4,618 of 5,113 carry
exactly three"* genotype rows. 4,618 is the 2025 file's three-genotype count and 5,113 is neither
file's annotation count (5,186 then, 5,190 now) — it is the *distinct-key* count of the
`clinicalVariants` rollup. The pair appeared in five live files. It is gone from all of them, replaced
by the relationship ("the large majority carry exactly three") rather than by a fresh count: a number
measured off one download is exactly what this item is about. The fixture-bearing measurements that
are *dated but true* — 396 of 16,087 rows with a multi-gene cell (RM74), 15,331 of 16,087 with a gene,
1,199 of 17,380 colliding triples (RM29b) — were left as the release-time evidence they are.

**The fixture is real bytes now.** `assets/clinpgx_annotations_slice/` is cut verbatim from the
2026-08-05 archive: the real `LICENSE.txt` and `CREATED_*.txt`, the three rs4149056/simvastatin
annotations that disagree with each other, and a real CYP2C19 haplotype annotation replacing an
invented id the old in-memory fixture carried. Every expected value is computed from it at runtime, and
the retired-vintage archive the guard is tested against is **the same rows under the old member names
and the old header** — one copy of the data, two spellings, so the refusal is proved against an archive
that would otherwise have built.

### The general half, which is why this was severity high and RM173 was not

A filename can retire while its bytes keep serving, and **nothing in this lane could have noticed**:
the download succeeded, the members parsed, the licence read, the row count was plausible, and
`release.json` recorded a `CREATED_*.txt` nobody compared against anything. Three candidate guards were
listed when the item was sized, and **none was built** — the item is a rebuild, and each of the three
is a design in its own right:

- **Audit every default URL in the lane against what the source lists.** ClinPGx serves 19 zips;
  `drugLabels.zip`, `relationships.zip` and `clinicalVariants.zip` are all on the page and
  `clinicalAnnotations.zip` is not. A one-off read, not machinery — and one that needs a browser, per
  the trap below.
- **Record the S3 `Last-Modified` beside the `CREATED_*.txt`** in `release.json`, so an archive that
  stops being rebuilt is visible in the artifact rather than only in the source.
- **Fire when one archive of a multi-archive source is much older than its siblings** — the shape
  RM173 stumbled into, generalised. `@two-surfaces-two-denominators` is the neighbour, and
  `@currency-asks-the-source-not-the-cache` says the question goes to the source.

The name check that shipped is narrower than any of them on purpose: it catches *this* failure — a
retired name still serving — at the only moment the lane can see it, without claiming to detect
staleness in general. Nothing built here would notice `summaryAnnotations.zip` itself going quiet, and
that gap is the honest remainder.

**A trap that cost the investigation real time, and belongs in the record.** Every ClinPGx HTML route
— `/downloads`, every help page — serves the same JS shell whose no-JS body is *"Javascript Is
Disabled!"*. `curl` and `WebFetch` therefore **cannot** answer "is this file listed?", and both return
200 while telling you nothing. The downloads listing in the probe is a rendered-DOM capture from a
browser. Treat a no-JS fetch of this host as no evidence at all (`@probe-the-real-file`, one host
further on).

**Related** RM173 (closed into this), RM166 and RM29b (both built on the lane this rebuilds), RM164,
`@two-surfaces-two-denominators`, `@currency-asks-the-source-not-the-cache`, `@probe-the-real-file`,
`@pgx-research-only`.

## RM166 — the whole PGx lane is one licence class, and a second authority exists that is not in it

**Severity** low-medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** — the cross-check
built, **the licence half closed measured** (`just-dna-enricher`, plus one
`VALID_VERIFICATION_CHECKS` member; `compiler/` untouched) · **Owner** enricher ·
**Motivating case** the 2026-09-01 source-adoption round

**The item split, and only one half is code.** What builds is a `drugLabels.zip` builder beside
`clinpgx_build` — the same cache, the same payload-read `LICENSE.txt` handling, its own
`CREATED_*.txt` and therefore its own `release.json` — and a regulator-label cross-check joining at
**two tiers**, the star-allele tier where `Variants/Haplotypes` supplies one and the gene tier
otherwise, with the tier **distinguishable in the finding** because a gene-level agreement and an
allele-level agreement are not the same claim.

**The half that closes is the one the item was filed for, and it closes on measurement rather than on
deferral.** The entry wanted a PGx lane member whose terms may not gate. Both routes refute it: the
ClinPGx route is CC BY-SA + no-sale, **the same gate**, so it diversifies nothing; and the FDA's own
Table of Pharmacogenetic Associations is **126 associations in an HTML page** with no bulk download and
**no copyright or public-domain statement on the page at all**. *"US government work is public domain"*
is a rule with exceptions, the entry said so, and the page does not settle it. So the direct route
supplies a quarter of the FDA content ClinPGx already carries, in a shape that must be scraped, on
terms that are unestablished. Leaving that half open would have left an item riding on a source shown
not to serve it. **If licence diversification for the PGx lane still matters — and it plausibly does,
being a single point of failure on the axis the format gates on — it wants its own entry, with
candidates chosen for their terms first**, which is the opposite of how this one chose.

**It is five regulators, not one, and the surface is named for the labels.** `Source` counts: FDA,
Health Canada, EMA, Swissmedic, PMDA. The entry asked for the FDA and the file supplies four more at
no extra cost, which turns the concordance shape from *module ↔ authority ↔ authority* into a lane
where **the number of authorities is a parameter** — exactly what RM134's vocabulary split was built to
survive. Naming any one agency in the surface would bake an authority into a published key, the
mistake RM134 caught in `ClinSigConflict` before it shipped.

**The join key exists, contra the entry's own closing worry.** `Genes` is populated on ~87 % of rows
and `Variants/Haplotypes` on ~15 %, and the star-allele tokens in the latter are `haplotypes.csv`'s key
verbatim. So *"a check with no key to join on is not a check"* is answered: a gene-level key for most
rows, an allele-level key for a sixth, **and the sixth is where this lane's rows actually live**.

**A blank `Testing Level` is `unknown` and withholds.** Roughly a third of the file states none, which
is an absence and not a *no*: reading it as `No Clinical PGx` would manufacture a negative regulatory
claim on 472 rows. Kleene, not a default — and the levels the snapshot states that the vocabulary does
not know are **collected and reported** rather than folded into an "other" bucket
(`@lookup-with-a-default-hides-a-new-member`).

**It warns in both modes**, like every other cross-check in this round: five expert regulators
genuinely disagree with each other and with a curator, and failing would make the format arbitrate
between its own authorities (`@clinsig-never-escalates`).

**The finding that outgrew the item, noticed and not built.** ClinPGx publishes **at least twelve**
archives and `clinpgx_build` reads one. `clinicalVariants.zip` is the one bearing on a shipped table
kind — ~5,190 rows of `pharm_variants.csv` territory, whose `type` is a six-member base vocabulary that
**comma-combines**, so any adoption normalizes the *combination* rather than the token. The honest
restatement is that the PGx lane reads one of twelve files from a source it has already adopted and
gated, and the FDA question was a narrow way into a broad finding. It wants its own number.

**What the code review found after the item was written, and it is a shape rather than a slip.** The
lane shipped a `VALID_AUTHORED_POSITION` holding five members while `just_dna_format.vocab` already had
that **exact name** holding five different ones — the clinical-significance concordance axis. Nothing
broke, because one test file imported one and another the other, which is precisely what made it
dangerous: the collision is invisible until a third caller imports both and the later `from … import`
wins silently, and two members are shared so even a spot-check passes. A lane-local vocabulary carries
the lane's prefix, and the rule is now `@a-lane-local-vocabulary-may-not-shadow-a-schema-one`. Its
related half: **a reason map only a test reads is a map nothing speaks** — the equality guard over the
sentence maps passed while every actual reader still met a bare token with no statement of what it
claims.

The same pass corrected two measurements this entry would otherwise have preserved. An allele claim
whose gene-tier sibling was never answered had been counted as *no label names this allele*, when the
truth is that nothing was asked about its gene either; it is withheld, and the three buckets are now
asserted as a partition rather than checked one at a time. And the gene-qualified join composes a token
**two ways**, because the file spells it two ways — the star alleles run together (`TPMT*3A`) and the
DPYD haplotypes are spaced (`DPYD c.2846A>T`) — so trying only the concatenation told a DPYD module its
allele was named by no label while two regulators named it exactly. A false coverage claim, which is
worse than a miss.

**`@two-surfaces-two-denominators` is the live rule**: ClinPGx's bulk file and the FDA's web table are
different sources with different denominators, and any count either produces must say which. And
`clinpgx_build`'s own docstring records that `relationships.zip` was a year newer than
`clinicalAnnotations.zip`, so this archive carries its own `CREATED_*.txt` rather than inheriting the
lane's release.

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm166--the-whole-pgx-lane-is-one-licence-class-and-a-second-authority-exists-that-is-not-in-it)**,
which proposed 0.8 and was overturned: *largest in the batch* and *least urgent* is an argument about
**order**, not about the release. It was sequenced last so that an early cut would leave one item in
flight rather than four.

**Related** RM134 § B, RM29b, `@pgx-research-only`, `@two-surfaces-two-denominators`,
`@clinsig-never-escalates`, `@acquisition-gate-is-not-a-read-gate`.

## RM167 — LitVar2/PubTator3 answers "which papers name this allele", which is the half PubMind structurally cannot

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** (`just-dna-enricher`,
plus one `VALID_VERIFICATION_CHECKS` member; `compiler/` untouched) · **Owner** enricher ·
**Motivating case** the measured limits of the PubMind adoption (RM134)

**The entry set its own test and the test passes.** [PUBMIND_ASSESSMENT](PUBMIND_ASSESSMENT.md)
measured that PubMind has *record* identity, not variant identity — 68,744 coordinate keys carry more
than one PVID, HFE C282Y alone holds eight with four different verdicts — and the entry proposed
LitVar2 as an independent second vote on exactly that fan-out, *"complements if LitVar's identity is
genuinely allele-level"*. It is. BRAF rs113488022's three CAIDs resolve to three distinct ALTs at one
position and carry 31,276 / 99 / 41 papers: allele resolution doing real work, three orders of
magnitude apart.

**The finding is that the tier a locus is answerable at is a property of the LOCUS, not of the
source.** APOE rs429358's position node carries 3,945 papers and its single allele node carries 328,
so **92 % of the literature at that locus is not allele-resolved**. A pass reporting the allele node's
count as *the* answer would understate it twelvefold. So the shipped pass names which tier answered:
allele-resolved, position-only, absent — plus `unchecked` as the fourth state the house algebra needs
— each arm with its own reason sentence, the fall-back to the position node **never silent**
(`@refutation-withholds`: a position-level answer to an allele-level question withholds rather than
answering approximately), and the position-only residue counted over the union of every allele node
rather than folded into the matched one (`@dont-discard-computed`).

**It writes no row, which was pre-authorised and is a complete outcome rather than a half-done one.**
A PMID list per variant is not a table kind, `literature.csv` is keyed by article, and `sources.csv`
means *this module uses this source*, which would be false here. What lands is one
`literature_coverage` attestation.

**The corpus measurement, which the entry made the build's first task.** Over the 11 reference modules
carrying a `resolution.csv` — **389 loci, of which 180 (46.3 %) have at least one CAID node**: 165
answered at allele tier, 92 at position tier only, 122 absent, 10 could not be asked. **14,168 papers
sit on a position node no allele node claims**, 6,700 of them APOE's.

**Three of the proposal's own numbers did not reproduce, and that is the round's shape again.** Its
*"of 588 HFE nodes … 299 are gene-level"* conflates two id shapes: measured off the recorded payload
there is **exactly one** gene node (3,285 papers) and **298 text mentions**, which is a fifth shape
(`litvar@#<gene_id>#<protein_name>`, all three `flag_*` false) and not a variant at all. The
**423-locus join does not reproduce** — a roster derived from `DRAFTABLE` finds 389 loci and 388
distinct rsIDs. And the stated id grammar `litvar@<clingen_id>#<rsid>#<gene_id>` is contradicted by the
proposal's own example: `litvar@rs1800562##` puts the rsID in the ClinGen slot, so the field count
varies by tier rather than the slots being fixed.

**The bound ships with the pass, in its own documentation.** Measured against the two records this
workspace could not resolve — CIViC 1955 and 2131, worked down in
[CIVIC_LEGACY_INSERTIONS](probes/CIVIC_LEGACY_INSERTIONS.md) to four candidate alleles with registered
CAIDs — LitVar returns **no node for any of the four**, and the one nominal hit for `VHL P71fs` is an
unrelated paper that happens to write the string. The reason is structural: PubTator3's export for all
four source papers is title and abstract only, with **zero variant annotations**, and the alleles live
in a table inside a paywalled paper. So **on precisely the class this workspace built a protocol for,
LitVar is the wrong instrument** — it answers *which papers discuss an already-identified allele* and
never *which allele this name meant*. Those read as the same question and are not.

**`data_clinical_significance` is not adopted in any form.** It is populated on position nodes and
`None` on every allele node measured, so it is position-level, unattributed, undated, and cannot even
be attributed to the allele it would be voting on.

**Two API facts pinned before anyone writes a second client.** `variant/search/gene/GENE` returns
**line-delimited Python `repr()`, not JSON** — `.json()` raises on it, so the shipped client parses
rather than deserializes (`@probe-the-real-file`). And NCBI publishes a **policy, not a licence**: it
places no restrictions and in the same passage declines to grant permission, so under
`@no-named-licence` every gating axis is `None`. Recording it as public domain by analogy with ClinVar
is exactly the move that rule forbids — ClinVar has a page saying so and this surface does not. NCBI's
side only; nothing is asserted about EMBL-EBI's terms for surfaces EBI co-hosts.

**It also repaired a defect one file over.** `clingen_allele._parse` computed a one-sided allele and
then discarded it whenever an rs-number arrived, because the rsID alone makes the outcome `resolved` —
so every PALB2 indel read as incomparable. `unanchored` now travels on a `resolved` result too.

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm167--litvar2pubtator3-answers-which-papers-name-this-allele-which-is-the-half-pubmind-structurally-cannot)**,
which reversed twice: an earlier draft proposed CLOSES on a misread id, the file then proposed BUILDS
in 0.8, and the maintainer pass took it now — the three stated blockers were a small client, a tiering
rule that is the item's own result, and an artifact question the entry had already pre-authorised.

**Related** RM134, RM153, `@existence-not-identity`, `@probe-the-real-file`, `@no-named-licence`,
`@refutation-withholds`, `@dont-discard-computed`.

## RM165 — `repeat_alleles.csv` has no source, and RM65/RM66 have been waiting on exactly the corpus one would bring

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** (`just-dna-enricher`,
plus one `VALID_VERIFICATION_CHECKS` member; `compiler/` untouched) · **Owner** enricher ·
**Motivating case** RM65's own stated prerequisite

**What shipped, and the split is the finding rather than a caution.** STRchive — `dashnowlab/STRchive`,
**MIT**, 82 loci across 79 genes — is adopted **by column**: a `check-repeat-bands` cross-check over
`benign_*`/`intermediate_*`/`pathogenic_*`, and a `draft-repeats` provider over the identity half. Two
commits, so the check is revertible without the provider.

**The reason the bands are checked and never drafted was measured on both corpus modules, and it is
one agreement and one disagreement.** STRchive reproduces `htt_repeat_expansion`'s first two bands
exactly — `benign 6–26`, `intermediate 27–35`, independently authored, about as strong a validation as
a drafting provider can get before it is written. And it gives FMR1 a single `intermediate 45–200`
where the module has `45–54` and `55–200`: **the boundary it does not have is 55, the premutation
threshold**, and the module's own conclusions name what would be lost — the 45–54 grey zone where *"the
carrier is not at risk, but the allele may be unstable in transmission"*, and the 55–200 FXTAS/POF
range. Drafting the three bands straight would have erased a clinically load-bearing line in one of the
corpus's two modules. The finding names the missing boundary rather than reporting that the tables
differ.

**`pathogenic_max` is emitted nowhere, and this is the second refusal worth keeping.** STRchive gives
HTT 250 where the module leaves `measure_max` empty. A catalogue's `pathogenic_max` is the largest
allele the literature reports — an **observation**, not a clinical bound — and written as `measure_max`
a 300-repeat allele would match **no bin at all**, silently, `--strict` included, which is the exact
silence RM55 shipped a loud warning about (`@bin-grounding`). It is reported as its own finding kind
instead. `@verbatim-except-order` is about not re-encoding a source's values; it is not a licence to
import a bound the source did not intend as one, and **the band's meaning is the schema's, not the
catalogue's**.

**It warns in both modes.** Two curators disagreeing about a threshold is not a `strict` matter
(`@clinsig-never-escalates`), and a `strict` run reports exactly what a best-effort run reports.

**Four things the build contradicted, and the first is the most useful.** *The identity half is mostly
uncarryable*: `RepeatAlleleRow` has no column for coordinates, `locus_structure`, `ref_copies` or the
OMIM/MONDO disease ids, so a drafted row is gene, motif, trait and a stubbed conclusion. That gap **is**
RM65/RM87 rather than a shortfall in this provider — the entry proposed drafting columns the schema
does not have. *No `DRAFT_PROJECTIONS` entry is owed*, because the split means the checked columns were
never copies, and a test asserts the absence with the reason. *HTT is finer than the catalogue too*,
dividing the pathogenic band at 40, which the entry named only for FMR1. And drafting into a real
shipped module exposed a **pre-existing crash** in `just_dna_compiler.draft.append_partial_rows` on any
table whose header is narrower than its model; it reaches all four existing partial-row providers, was
reproduced independently of this work, and is left for its own item because `compiler/` was barred this
round.

**Two things named and deliberately not built.** RM66's evidence is real and partial — `locus_structure`
is present on **23 of 82** loci, HTT's being the `(CAG)n(CAA)(CAG)` structure RM66 asks about, published
as typed data with its own three-member vocabulary, while FMR1's is `[]`. That is enough to *decide*
RM66 and not enough to make the answer universal; naming the evidence and stopping was the whole of
this round's obligation to it. And STRchive's `evidence` is a ClinGen-style validity classification on
all 82 loci **including Disputed 3 and Refuted 1** — a second instance of **RM170**'s problem in a
different domain, worth knowing before RM170 is designed against CIViC alone.

**gnomAD's tandem-repeat release is out on category, not on terms.**
`gnomAD_STR_genotypes__2022_01_20.tsv.gz` is `Genotype`/`Allele1`/`Allele2`/`Sex`/`Age` — **one row per
sample per locus**, per-sample genotype data, the one category this format does not carry — so the
question of inheriting `GNOMAD_TERMS` never arises. A category exclusion is cheaper and more durable
than a licence answer, because it cannot be renegotiated.

**RM65's attached obligation carries forward**: `_write_resolution_csv`'s positional pass hard-codes
`locus_index = 0`, honest only while these tables never expand, and repeat coordinates are exactly what
could expand one (RM87).

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm165--repeat_allelescsv-has-no-source-and-rm65rm66-have-been-waiting-on-exactly-the-corpus-one-would-bring)**
— which drafted the provider as held to 0.8 and was overturned: the deferral assumed a cut about to
close, and the argument that the split made deferring the larger half cheap reads equally well as an
argument that the half is cheap.

**Related** RM65, RM66, RM87, RM164, RM170, `@bin-grounding`, `@enrichment-is-validation`,
`@verbatim-except-order`.

## RM163 — `pgs.csv` is keyed on a Catalog accession and nothing ever asks the Catalog about it

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** (`just-dna-enricher`,
plus two `VALID_VERIFICATION_CHECKS` members in `just-dna-format`; `compiler/` untouched) ·
**Owner** enricher · **Motivating case** the 2026-09-01 source-adoption round

**What shipped.** A fourth registry in `identifiers.py` and a `pgs.py` client asking the PGS Catalog
about every authored `pgs_id`, `PGS_TERMS` as a per-score licence **floor**, and `pgs_catalog` as the
second member of `currency.default_probes`. It attests under **two** names — `pgs_accession_currency`
and `pgs_metadata_agreement` — because currency asks whether the id still names a score and drift asks
whether two cells beside it still match: different questions, different subjects, different
denominators, and one record over two populations publishes a findings count that means nothing.

**The verdict is read off the body, never the status.** `GET /rest/score/PGS999999` — a never-assigned
id — returns **HTTP 200 and `{}`**, and so does `GET /rest/score/PGSXXXX`, which is not a well-formed
accession at all. So the status code carries no existence information and a withdrawn score, a typo and
a malformed id are indistinguishable *by construction*. `@existence-not-identity`, and RM153's warning
about a 200 that is not an answer arriving in a second source.

**And the absence message is weighted by a measured base rate, which is `@rsid-absent-two-readings`
run backwards.** About 35 % of the accession range is assigned, so an unrecognised `pgs_id` is
overwhelmingly a *never-assigned* one. dbSNP earns its equal-weight treatment because its id space is
densely assigned and merges are a frequent, real event; here the base rate runs the other way, and
naming withdrawal as a co-equal reading would send an author looking for a retirement notice that
almost certainly does not exist. The message states the absence, states the sparsity, and names
withdrawal as the rarer reading — and where the Catalog offers no supersession field at all, that is
stated as a limit of the source rather than resolved by guessing.

**Drift is over two fields, not the four the entry named.** Reading the model rather than recalling
it: `match_rate_floor` is described in its own `Field` as *"Author-set variant-match floor"* and
`research_tier` is a two-member curator judgement. **The Catalog publishes neither**, so there is
nothing to drift them against, and a check with no source-side value is a check that cannot fail
(`@tautology-zero`). The reason is written down where somebody would otherwise add them later. What
is checked is `training_ancestry` against `ancestry_distribution` and `training_cohort` against
`samples_training`, reporting and never repairing.

**The licence half is the one that had to be right, and it is a correctness requirement rather than an
optimisation.** `license` is a field on each **score record**, not a property of the Catalog: over the
first 250 of ~6,982 scores, most carry the generic *"used in accordance with any licensing restrictions
set by the authors"* string, a handful are academic-research-use-only — the class `licensing.py`'s own
comments name as barring redistribution outright — and a couple are CC0. So `PGS_TERMS` is written as
the **floor**, with EBI's terms-of-use URL and every gating axis `None`, and each score's own `license`
string overrides it in that score's `SourceRow`. `@licensing-as-data`, the shape ClinPGx's bundled
`LICENSE.txt` already uses, and `@per-article-terms` one source over: the Catalog is a **host** for
scores licensed by their authors. **The consequence is visible rather than theoretical** — a module
naming a single academic-use-only score is now refused by the compile gate *by name*, where one flat
constant would only have warned, and would have been a false claim in the permissive direction.

**Currency is read, not built.** `/rest/info` publishes the release date, the score count and the
trait and publication totals, so the infrastructure this item wanted did not have to be written — the
same finding as MANE's `README_versions.txt` in RM168, and the second time in one round that a source
turned out to publish its own release record.

**Four things the build contradicted, all of them recorded.** The section's e2e recipe wanted one spec
directory carrying a malformed accession beside a live one; `PgsRow` refuses `PGSXXXX` at load, so it
never reaches the Catalog and the malformed case has to be probed at the client. *"A drifted cell is
the author's to fix or to answer in `overrides.csv`"* is **impossible** for these cells — the overlay
is derived-tables-only and `pgs.csv` is authored, so the sentence names a remedy that does not exist
and the finding has no silencing route. `PgsRow` disagrees with itself about which ancestry
`training_ancestry` means: the name says training, the description says *"validated in"*. And
`/rest/release/current` bought nothing over `/rest/info`, so it is not read.

**Severity is deliberately split.** An unrecognised accession escalates under `--strict`; a metadata
disagreement never does, because the Catalog and a curator are two authorities and the format does not
arbitrate between them (`@clinsig-never-escalates`).

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm163--pgscsv-is-keyed-on-a-catalog-accession-and-nothing-ever-asks-the-catalog-about-it).**
**RM16 is not re-opened** — that is authored per-variant weights and stays deferred on a missing
consumer; `PgsRow` is a manifest of Catalog ids and this item touched only the manifest.

**Related** RM16, S86, RM153, `@existence-not-identity`, `@licensing-as-data`, `@tautology-zero`,
`@rsid-absent-two-readings`.

## RM168 — the identity procedure downloads MANE by hand, and nothing in the code knows the file exists

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** (`just-dna-enricher` only;
no schema change, no authored column, `compiler/` untouched) · **Owner** enricher ·
**Motivating case** [CIVIC_IDENTITY_PROTOCOL](probes/CIVIC_IDENTITY_PROTOCOL.md) § 3b

**What shipped.** `MANE_TERMS` in `licensing.py`, a `mane/` cache with `$JUST_DNA_MANE_CACHE` and the
`default_mane_cache_dir` / `resolve_mane_reference` pair, `mane_build.py`, a `mane build` sub-app, a
`_CACHES` row, and an `ENRICHER.md` lane section. **Three files in one pass**, together under 1.2 MB:
the summary, `changed_select_accessions` and `protein_coding_genes_not_in_mane`. Splitting them was
refused for a reason worth keeping — the second file *is* the currency check, so shipping the cache
without it would ship the thing this item complains about (a version pinned in prose that nothing will
notice going stale) with a cache wrapped round it.

**The source publishes its own staleness list, and its own provenance.** `README_versions.txt` is 96
bytes and states the MANE version, the NCBI RefSeq annotation release and the Ensembl release; the
builder **copies** it rather than parsing a filename, because two of those three are in no filename and
reconstructing less information than the source hands over is `@probe-the-real-file` backwards.
`changed_select_accessions` carries `Update_Affects_CDS` — **the numbering-frame axis, stated by the
source**: a MANE Select change that moves the CDS moves every `c.` and `p.` derived in that frame, and
one that does not, does not. So the currency check for a numbering frame turns out to be *read one
small file*, not *diff two releases*.

**`MANE_status` is a column and is never collapsed**, which is the decision the item exists for. 74 of
19,437 rows are MANE Plus Clinical (0.38 %), and CDKN2A is the case: two rows for GeneID 1029 with
different CDS numbering, `NM_000077.5` MANE Select beside `NM_058195.4` MANE Plus Clinical. A builder
keeping one row per gene would drop them and reintroduce the exact blind spot the table can see and a
remembered accession cannot.

**And the negative roster is a third state served by the source.**
`protein_coding_genes_not_in_mane` lists 222 genes **with a reason** over a seven-member vocabulary —
`gene not on assembled chromosomes`, `gene located on mitochondrial genome`, `pending MANE review` and
four others — so *"MANE has no answer for this gene"* is distinguishable from *"nobody asked"*
(`@unreachable-not-absent`), and `pending MANE review` is neither absent nor decided. The vocabulary is
**derived from the file and asserted as an equality against it**, so a reason MANE adds is counted
rather than joining an "other" bucket (`@registry-completeness`).

**The bound ships with it: MANE is the default, not the answer.** RUNX1 is a single row, and the
27-residue RUNX1c/RUNX1b offset § 3b derived by translating each isoform's CDS is **not in MANE and
cannot be**. The table makes the CDKN2A class of problem visible and is *silent* on the RUNX1 class, so
a pass treating it as an oracle would be wrong in a way the file itself cannot warn about. Said in the
lane's documentation rather than left for a reader to rediscover.

**Terms: NCBI publishes a policy, not a licence.** `license=None`, `license_url` at the policy, the two
operative sentences in `notice`, every gating axis `None` (`@no-named-licence`). *No restriction
imposed* is not *permission granted*. MANE is a joint NCBI/EMBL-EBI product and **only NCBI's side was
read** — the terms constant says so, and asserts nothing about EMBL-EBI's. Consequently there is no
`--use` flag on the build and no `ensure_mane_snapshot`: a declared-use gate whose every answer is a
skip is a flag that does nothing (`@acquisition-gate-is-not-a-read-gate`), and nothing publishes a MANE
snapshot to ensure.

**Pinned by the versioned directory, never `current/`.** One 96-byte request reads `current/` to
*discover* the newest version, and the answer is resolved to a `release_<v>/` URL before anything is
downloaded — so a build is pinnable after the fact. That distinction became its own gotcha,
`@current-discovers-a-version-a-directory-pins`.

**Why it went first.** Nothing else in the round depends on it and the identity protocol does: it is
the only item that makes an already-shipped result re-derivable — RM159's 33 curated name→identity
answers were derived in this frame, and the frame was recorded nowhere a re-derivation could read.

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm168--the-identity-procedure-downloads-mane-by-hand-and-nothing-in-the-code-knows-the-file-exists).**
Worth recording: of the round's six items this is **the only one whose probe the build did not move**.
Every fact was re-measured live against NCBI while building — 19,437 rows, 74 MANE Plus Clinical, 120
changed accessions with `Update_Affects_CDS` Yes on 74, 222 excluded genes over exactly 7 reasons,
CDKN2A two rows, RUNX1 one, VHL `NM_000551.4` — and none of them contradicted the entry. In a round
whose keeper is that five of six entries said something their own probe contradicted, the one that held
is the one whose questions were cheapest to ask.

**Related** RM159, RM153, RM152, `@snapshot-layout-locations`, `@release-json-provenance`,
`@current-discovers-a-version-a-directory-pins`, `@accession-version-names-no-build`.

## RM169 — the wider basis was published as a dated file all along, and nobody had looked

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`;
**no schema change**) · **Owner** enricher · **Motivating case** RM160, whose central premise this
item falsified

RM160 was filed on the finding that `civic build` reads the `accepted`-only bulk TSV while the API
serves 2.35× as much, and it stated the tension as a reproducibility bargain: *the API has no dated
release to pin*, so any wider read costs the snapshot its byte-reproducibility. All three shapes it
proposed were ways of paying that price.

**The premise was false, and the check was one HTTP request.** CIViC publishes
`<date>-civic_accepted_and_submitted.vcf` **inside the same dated release directory** the builder
already reads. It is pinnable, hashable and immutable exactly like the three TSVs. Nobody had probed
the download surface past the files already in use — the survey named three TSVs and stopped.

### What the file is, and why it is not the input

The whole release surface, enumerated: seven TSVs and two VCFs. (`GeneSummaries.tsv` is
**byte-identical** to `FeatureSummaries.tsv` — one file under two names.) The VCF carries one `CSQ`
entry per evidence item, with `CIViC Entity Status` on each.

**But it is a strict subset of the TSV, and the subset is not arbitrary.** A VCF record needs a POS,
so a variant with no GRCh37 coordinate cannot appear at all. Over `01-Aug-2026` the accepted VCF holds
473 direction rows on 236 variants against the TSV's 533 on 290 — and **52 of the 54 it drops are
exactly the `unresolvable_identity` class**, the records whose identity RM159 had to read out of their
names. Reading the VCF as the row source would silently discard the hardest-won half of the snapshot.

So the TSV pair stays primary and the VCF is joined onto it, behind `--submitted`.

### What it added, measured

| | accepted | accepted+submitted |
|---|---:|---:|
| Rows | 507 | **1,149** |
| …of which `submitted` | 0 | 642 |
| Variants | 270 | **397** — 127 of them new |
| refget coordinates cross-checked | 57 | **129**, 0 mismatches |
| `input_rows` the drop registry closes over | 4,878 | 8,328 |

`release.json` gains `status_basis`, `status_counts`, `vcf_evidence` and `unjoinable_submitted`, and
every row gains `evidence_status` carrying CIViC's own word. **A rebuild on the wider basis is
byte-identical**, so Principle 7 survives the join.

### The second accepted-only file, which is why `vcf_csq` exists

`VariantSummaries.tsv` is `accepted`-only **too** — a fact nothing had stated. So **112 of the 127**
variants the submitted evidence introduces have no row there at all: no gene, no aliases, no HGVS, no
registry id. A first cut kept identity strictly TSV-sourced and recovered only 15 of them.

The same `CSQ` entry carries all four identity cells, so for a variant the TSV cannot describe they
are read from there instead — through **the same parsers**, on **the same published identifiers**:

| route | variants |
|---|---:|
| ClinGen CAID only | 57 |
| rs-number only | 40 |
| GRCh38 accession only | 14 |
| both an rs-number and a coordinate | 1 |
| **total** | **112** |

Those rows are stamped `identity_derivation="vcf_csq"`, a member of its own: the routes inside are the
ordinary ones, and what the member names is the **file**, which is the part a consumer cannot
otherwise recover. Measured over the emitted parquet, not over the input — 172 rows on those 112
variants, and the other 15 new variants join the TSV normally and take an ordinary derivation.

**Nothing is placed from the VCF's own position.** It is GRCh37 throughout
(`##reference=…GRCh37-lite.fa.gz`) and lifting it stays refused (RM48); a CSQ-sourced row leaves the
`civic_grch37_*` provenance columns empty rather than recording a coordinate whose build this file
never states, and a test pins it.

### Two guards the round earned

- **The drop registry caught a real accounting error.** A first cut counted submitted items that
  could not join under a new drop reason — but those rows never entered the evidence list the
  registry's equality is over, so the input total disagreed with the list the loop walks. The guard
  raised (`@registry-completeness` working exactly as designed), and the count moved to its own field,
  `unjoinable_submitted`, outside the registry.
- **The vocabulary is enumerated, not computed.** The VCF spells members `SCREAMING_CASE` where the
  TSV uses title case, and a `.title()`-shaped rule gets `RARE_GERMLINE` right and
  `SENSITIVITYRESPONSE` wrong — the TSV writes it `Sensitivity/Response`, with a separator the VCF
  drops. Three exceptions in twenty members is a map, and it raises on an unmapped member rather than
  emitting a mis-spelled token (`@lookup-with-a-default-hides-a-new-member`).

### What this leaves for RM160

Its **coverage** half is answered and closed here. Its **provenance** half is not: the sweep behind it
found that 10 of the 20 records nothing can place gain citations only a wider basis carries, and the
VCF reaches **none of them** — it holds 0 of those 10 and 1 of the 53 unresolvable variants, for the
structural reason above. That half still needs the API or nothing, and RM160 stays open carrying it.

## RM159 — the identity a source states in a variant's name, adopted rather than left in a probe

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`;
**no schema change**) · **Owner** enricher · **Motivating case** the 2026-09-01 residue round
([CIVIC_UNRESOLVED](probes/CIVIC_UNRESOLVED.md))

`civic build` placed a row from what CIViC puts in its *identifier columns* — an rs-number, or a
GRCh38 RefSeq accession it can parse — and dropped 53 variants as `unresolvable_identity`. For most
of them the identity was published the whole time, one column over: in the variant's own `name`.
`N150fs (c.448delA)`, `IVS2+1G>A`, `D1709N`. A `c.` or protein fragment plus the gene's numbering
frame is an allele, and an allele registry holds it.

**Adopted: 33 of the 34 that resolved.** Coverage over the dated `01-Aug-2026` release goes from
**237/290 variants (81.7%) to 270/290 (93.1%)**, and from 474/533 evidence rows (88.9%) to
**507/533 (95.1%)**. `unresolvable_identity` falls from 59 rows to 26.

**The one excluded, and why it is not an oversight.** CIViC 4968 `TP53 R72P` resolves — rs1042522,
CA178298 — and its identity is the **reference** allele: codon 72 is `CCC` = Pro on GRCh38, so the
name has reference and alternate inverted, and the registry answers `NC_000017.11:g.7676154G=`.
A snapshot row is `chrom/start/ref/alt` and `ref == alt` is not a variant row. The identity exists and
this representation cannot carry it, which is a fact about the representation.

### Why the answers ship as data and the procedure does not run

Resolving a name needs the network, and `civic build` must stay byte-reproducible from a pinned dated
release — which is why the CAID pass (RM153) runs at *draft* time and never in a build. The obvious
repair is therefore "do this at draft time too", and it was refused: **four of the 33 required a
judgement no lookup makes.** A legacy `IVS2` name that converts structurally to the wrong exon
(788 — the structural answer `c.319+1` and the true one `c.444+1` are both real registered alleles
9 kb apart, so nothing in a lookup flags the error); a name pairing a missense protein label with a
*synonymous* cDNA change (2459); a protein consequence standing over an intronic allele (804); an
rs-number that is position-level where two alleles spell the same substitution (2196). A draft-time
resolver would either fail on those or silently pick a side.

So the **answer** is a shipped constant — `civic_identities.CIVIC_NAME_IDENTITIES`, 33 rows carrying
coordinates, rsID, the CAID as provenance and a note where one was needed — the **procedure** is
written down as [CIVIC_IDENTITY_PROTOCOL](probes/CIVIC_IDENTITY_PROTOCOL.md), and the build stays
offline. `P9` — zero authored-layer cost, no CSV, no column.

### The name is the key, and that is the safety property

Every identity was derived from the `name` string quoted beside it, so a build applies a row only on
an **exact** name match. Each curated row lands in exactly one of four counted states, published in
`release.json` and asserted as an equality over the walked table (`@registry-completeness`):

- `applied` — the name still matches, CIViC still publishes no identifier, the row was placed.
- `superseded` — CIViC now publishes an identity of its own. **The source always wins**, and a
  supersession is the cheapest currency signal available: it means the upstream has curated.
- `renamed` — the variant is there and its name changed. The answer was an answer to a name.
- `absent` — the variant is not in the file. Kept apart from `renamed` on `@unreachable-not-absent`:
  over a full release it means withdrawn, over a slice it means nothing at all.

A curated answer therefore cannot outlive the record it answered, which is what makes a hand-built
table safe against the next release rather than merely correct for this one.

### What the external check says

`civic reproduce` cross-examines every placed coordinate against the GRCh38 reference through
refget/seqrepo — an unrelated service asked whether the reference base at each position is what the
snapshot wrote. It read 24 coordinates before this item and reads **57 of 57 with 0 mismatches**
after. Every one of the 33 hand-read alleles is confirmed at its stated position by something that
has never heard of CIViC.

### Two smaller things the adoption fixed on the way

- **`allele_registry_id` is untouched.** It is CIViC's verbatim cell and is empty for all 33 by
  definition; the CAIDs the probe recovered live on the curated table as provenance. Writing them into
  the source's column would publish a finding as if the source had made it, and a test pins it.
- **`curated_name` is its own `identity_derivation` member**, not folded into `rsid`/`grch38_hgvs`.
  Those mean "the source stated this in the column for it", and a consumer must be able to exclude the
  difference without re-deriving it. The drafter needed no change — it special-cases `caid` and lets
  every other member through the placed path — but that is now an equality over the vocabulary rather
  than a property nobody checked (`@lookup-with-a-default-hides-a-new-member`).

## RM162 — `RM_TOC.md` is an index, and an index is not an allocator

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (tooling only — no package,
no schema change) · **Owner** the triage loop · **Motivating case** the 2026-09-01 collision, git
`741ec59`

The consumer-suggestion loop has had an allocator for `Sn` since it was built (`triage-state.py
--next`), because the id is written into a document and a stale one collides. `RMn` never got one.
`docs/RM_TOC.md` is the complete index of every item — that is what it was written for — but reading a
number out of it *claims* nothing, so the procedure was grep the highest, add one, and write the entry.
The window between the read and the write is exactly where a second session reads.

**Reproduced rather than hypothesised, and by this loop on itself.** On 2026-09-01 two sessions sharing
this working tree filed different work as **RM159** a minute apart, and the tree carried two RM159
entries pointing at different items. `741ec59` renumbered one to RM161, picking the cheaper move: the
other pair was contiguous and already referenced from three probe documents and the enricher reference.

**Grepping cannot fix this.** Any read-then-write with a gap has the same race, so the claim has to be
a single atomic write: `.claude/rm-next.py` scans every `docs/**/*.md` and appends the reservation
inside one critical section. Scanning outside the lock and appending inside it would be the same defect
with a smaller window, so the scan is in there too.

**The lock is on `docs/`, the directory, and the second reason was measured.** A lockfile left behind by
exactly the kill this guards against would block every later run, and the staleness rule that repairs
that is a clock — `@flock-not-a-lockfile`, the idiom `transaction.spec_lock` already uses for `enrich`.
The sharper reason is that `flock` binds an **inode**: an editor or an atomic writer that renames a new
file over `RM_TOC.md` leaves the holder locking an unlinked inode while a second process opens the new
file and acquires immediately. Verified in a sandbox before the tool was written — locking the file
would have looked correct and excluded nothing.

**A reservation is a visible index row, not a side-car.** `🔷 reserved`, under the open-items heading,
replaced by the item's real row when the entry is written. A number claimed and abandoned is then
*visible* rather than silently burned, and a state file the index cannot see is precisely how a number
goes missing — the failure `RM_TOC.md` exists to prevent. Placement is checked: the file ends in a prose
section, and a row appended at EOF would read as part of it, which is the furniture hazard the triage
loop's own §6 records one document over.

**`--release` leaves a tombstone, and the first cut of this shipped the bug it fixes.** Deleting the
reservation row made the number invisible to the scan, so a released RM10 was immediately re-reserved as
RM10 — contradicting the rule the tool's own docstring states. Ids are never reused: whatever argued the
withdrawal refers to the number, and reusing it makes two items answer to one name in the record. The
tombstone has to contain the number literally, since a scan is all that reads it. Found by running the
release path rather than by reading it.

**Pinned by a guard watched failing.** `test_rm_allocator.py` runs eight allocators at once and asserts
eight distinct contiguous numbers — and runs *the same eight with `flock` neutered*, asserting they
collide. Without that second test the first passes for reasons that have nothing to do with the lock.
The unlocked run produced 5 distinct of 8, with one number taken three times.

Also corrected: the loop's own Step 5 hygiene bullet said to read the number off `RM_TOC.md`, which is
the instruction the incident came from, and named `RM47` as the highest — a counter in prose, stale for
114 items (`@counted-prose-needs-a-fixed-field`).

## RM161 — a release record's two halves are written at different times, and the second left the first behind

**Severity** high (a red release gate) · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0
(`just-dna-format`) · **Owner** format · **Motivating case** the pre-build gate run for the 0.7.0 cut

`sweep --release 0.7.0` exited **1** with two findings: `gene_validity.superseded_count` and
`identity.version_coerced_from` *"moved and the release record does not list it"*. Both are real
manifest additions from the 2026-08-31 batch, both carry a `DeclaredChange` written the day they
landed, and neither was in the record's `manifest_fields`. The readiness table had recorded the gate
green on 2026-08-31; the two declarations were added at 06:52 and 07:04 that morning, after the
measurement the list came from.

**The shape is the record's own construction.** `SweepMeasurement.as_record` produces the *measured*
half — `axes` and `manifest_fields` — with `declared` deliberately empty, so the gate keeps refusing
until a person classifies each movement. That split is what makes the gate work, and it is also what
lets an item landing after the measurement add its declaration and leave the measured list behind.
Nothing in a checkout could see it: the gate needs the previous release installed and is a
release-sequence command by design, so between two cuts the record can be wrong for a fortnight and
every test stays green.

**The guard is an asymmetry, not a symmetry.** A declared **addition** must appear in
`manifest_fields`: a field that did not exist before moves wherever its block appears, so a release
claiming to add one while measuring no movement is claiming something its own corpus contradicts. A
declared **correction** may legitimately be unmeasurable — 0.7.0 declares `gene_validity.classifications`
and `gene_metrics.signature`, and no reference module carries a re-curated gene-validity claim or a row
from the snapshot the second is about. Those stay declared and unlisted, and the gate already has a
*note* for the reverse case. Asserting the full set equal would have forced two false claims into the
record to silence a true one.

The test walks `RELEASE_RECORDS`, so a future release joins by existing. It fails on the pre-fix tree
naming exactly the two fields, which is the whole point: this was findable offline and was not being
looked for.

**Evidence unchanged.** The record's `evidence` sentence already carried today's numbers
(`content_signature 0/15, manifest_fields 15/15, parquet_bytes 14/15, parquet_schema 14/15, warnings
3/15`) — only the field list was stale, which is why nothing else in the record needed touching. After
the fix: *"release record for 0.7.0 covers the measurement"*, exit 0.

## RM158 — the GWAS pass asked about one table's rsIDs, and the answer already existed in this package

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`) ·
**Owner** enricher · **Motivating case** the RM155 sweep, third instance

`gwas._module_subjects` built its `(rsid, variant_key)` list from `variants.csv` while five authored
models carry `rsid`, so a module whose rsIDs live in `haplotypes.csv` or `pharm_variants.csv` got no
associations and no line saying none had been asked for. Reproduced against the pre-fix code: a spec
carrying one `haplotypes.csv` row for `rs4244285` — CYP2C19\*2, which the Catalog has associations for
— returned `[]`.

**What makes this the useful one of the three: the fix was already written.** `enrich.Subject` and its
collector exist for precisely this question, and the docstring says so — resolution read `variants.csv`
alone until RM43, so a PGx module *"which by design carries **no** `variants.csv`"* enriched to an
empty `resolution.csv` and shipped with no coordinates at all. That repair normalized the question to
a subject and let three tables through the unchanged resolver. The GWAS pass, written afterwards,
restated the narrow loop instead of calling it. So the shape recurs even where the package has already
paid to end it, and a sweep is worth more than a fix: **grep for the question, not for the bug.**

`_collect_subjects` and `_Subject` are now `collect_subjects` and `Subject` — a private name is what
kept the second caller from finding the first. `studies.csv` carries `rsid` and is deliberately not a
subject: a study row *references* the variant it grounds, which the module already carries as a row of
its own, so admitting it would add no rsID and only change which table an identity came from.

**Nothing moves for a module that already had subjects.** Measured across the corpus before and after:
`pathogenic_clinvar` (301), `hboc_palb2` (16), `mt_heteroplasmy` (2) and `grch37_build` (0) return
identical lists, because `variants.csv` goes first in the collector and first occurrence wins — the
precedence that exists so a PGx row cannot take an identity a SNP row minted. This pass inherits it
rather than re-implementing it.

**No schema change**: no column, no vocabulary member, no signature moves.

## RM157 — the gene set three passes take their scope from read one table while nine carry the column

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`) ·
**Owner** enricher · **Motivating case** the RM155 sweep, run against this repo's own corpus

`gene_metrics.module_genes` built its list from `variants.csv` alone while nine authored models declare
`gene`. It is not a report: it is the **scope** of the constraint-metrics pass, the gene-validity pass
and the ClinGen dosage pass — all three call it, the second through a wrapper that exists only to
re-raise its error as its own type — so a module whose genes live in its PGx tables had all three
quietly do nothing. No rows, no findings, and no line saying a question had not been put.

**Measured on the corpus, not on a fixture.** `cyp2c19_star_alleles`, `apoe_epsilon`,
`cyp2c9_warfarin_grch37` and `hfe_compound_het` returned `[]` here while naming CYP2C19, APOE, CYP2C9,
VKORC1, CYP4F2 and HFE on rows an enrichment could have asked gnomAD and ClinGen about. A fixture
written to the widened roster cannot produce that evidence, which is the general rule this pair of
items leaves behind.

**The workspace was already carrying two answers to one question.** `pgx._module_genes` reads two PGx
tables, and this one read a table those modules do not have; nobody had put them side by side. And the
pass had already been patched for the *symptom* without anyone asking why the list was empty — RM104
bound `reference` before the branch because "any module with no `variants.csv`" raised
`UnboundLocalError` out of a run where `wanted` came back empty. That sentence was in the code, in a
comment, describing the defect as a shape rather than a question.

**Derived, and refusing rather than narrowing.** The set now comes from the same registry walk the
identifier roster uses (`@registry-completeness`), so a table kind that gains the column joins by
existing and a second implementation cannot drift from the first. A table that exists and will not
parse **raises** here, in this pass's own phrasing — a reporting surface may route an unreadable table
to `not_read`, but a scope may not: half a gene set is a silently narrowed one, which is the same
defect one table wider. `IdentifierRoster` gained `read_errors` so the loader's own message survives
into that refusal instead of being reconstructed by string surgery, which is what keeps
`gene_validity`'s `variants.csv is invalid` diagnosis exactly as it was.

**`pgx._GENE_TABLES` stays two tables** and is not this roster: it decides whether the star-allele
cross-check *applies*, which is a fact about that check's inputs rather than about what the module is
about. Widening it would run the cross-check over modules carrying no star alleles at all.

**No schema change**, and no ordering change: `gene_metrics` sorts its rows by `(gene, dataset)` before
writing, so the roster's order reaches no artifact. What moves is that three passes now have a scope on
modules where they had none.

## RM156 — the widened roster was gated behind the one table it had stopped depending on

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`) ·
**Owner** enricher · **Motivating case** the RM155 sweep, run against this repo's own corpus

RM155 widened `check_identifiers`' rosters from `variants.csv` to the nine authored tables that carry
each column. Two gates in front of it were still keyed on `variants.csv` alone, so on the module shape
the widening was most for, the wide roster was never reached: `check_identifiers(spec_dir=)` loaded
that table unconditionally and raised `variants.csv is invalid: ... not found`, and the command
returned *"no variants.csv — nothing to check"* one call earlier and hid it.

**The table has never been mandatory (RM2), and four of the nine carrying `gene` are the PGx kinds a
module is built entirely out of.** Reproduced on this repo's own reference examples rather than a
fixture: `cyp2c19_star_alleles`, `apoe_epsilon`, `cyp2c9_warfarin_grch37` and `hfe_compound_het` carry
no `variants.csv` at all, and between them name CYP2C19, APOE, CYP2C9, VKORC1, CYP4F2 and HFE on rows
the roster now reads. `check-identifiers` printed *"no variants.csv — nothing to check"* and exited 0
on every one. That is S86's unreadable `0` surviving one level above the function that repaired it,
which is the more useful half of the lesson: a widening is not done while a caller still gates on the
narrow thing.

**The old guard's comment is what dated.** It justified writing no attestation on the grounds that such
a module "has no `gene`, `trait_efo_id` or row for these checks to have an opinion about, so the check
does not APPLY". The first clause became false the moment the roster walked `DRAFTABLE`; the second —
no attestation without a question — was right and is kept, now derived: nothing to check means **no
id-bearing table was read**, which is a fact about the roster rather than about a filename. Both checks
switched off is a different state and keeps its own path, recorded as `not_requested`.

**A third site, found by following the rows.** With `variants` empty and symbols in hand,
`_gene_locus_conflicts` returned `compared=0` with `None` beside it — the `ran(0, 0)` its own
attestation docstring forbids, and the same vacuous pass a third time. It now returns the reason: no
`variants.csv` rows, so no symbol could be placed against a variant's chromosome. The guard sits
*before* the "no row names a gene" arm because it is the more specific fact — since the widening, a
module can reach that code with genes and no rows.

Present-and-unparseable still raises, deliberately: that is a module whose rows exist and cannot be
read, which is the author's to fix rather than a shape the check should tolerate.

**No schema change**: no column, no vocabulary member, no signature moves. What moves is which modules
the check runs on at all.

## RM153 — the identity CIViC does not publish, recovered through the registry rather than by lifting a coordinate

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-enricher`; additive — one new client, one
snapshot derivation, two withhold reasons, one licence row. **No schema change.**)
**Severity** low-medium · **Owner** enricher · **Motivating case** measured while building RM152

The residue RM152 left: CIViC publishes GRCh37 coordinates or none, and after every published
identifier is read, some variants still have no route to a GRCh38 identity. The item carried two
questions — should a ClinGen CAID be resolved, and should the remainder be lifted over. **Both are now
answered, and they answer in opposite directions.**

### What was measured

Over the dated `01-Aug-2026` release, 533 germline direction rows on 290 variants:

| | Variants | |
|---|---:|---|
| Recovered by the builder before this item | 138 | 48% |
| Recoverable through a ClinGen CAID | **+64** | 52 via an rs-number, 12 via a GRCh38 coordinate |
| …plus one-sided indels the registry states, once anchored | **+35** | 22 deletions, 13 insertions — **all 35**, no exceptions |
| **After RM153** | **237** | **82%** |
| No identifier of any kind | 53 | of which **9** carry a GRCh37 coordinate |

The registry answered all 102 probe requests with **zero failures**, serves both an rs-number and a
GRCh38 coordinate, and needs no key.

**A correction to this item's own figures, and then a correction to the correction.** It said 131
unreachable where the dated release gives 157. That gap was first written up as nightly-versus-dated —
reach numbers from one file, row counts from the other. Re-measured on **2026-09-01** it is not two
files at all: the nightly and `01-Aug-2026` are identical on this slice, and 131 versus 157 is one
file read two ways, counting variants that *carry* a GRCh38 accession (40) against variants carrying
one `parse_grch38_substitution` can *read* (12). 157 is the number the builder acts on.
[CIVIC_SURVEY](probes/CIVIC_SURVEY.md) carries the measurement and now labels the *definition* behind
every identity figure, not just the file.

### What shipped

- **`clingen_allele.ClingenAlleleClient`** — CAID → rs-number and/or GRCh38 coordinate, paced, cached
  per run, with **three outcomes and never two**: `resolved`, `no_identity` (the registry answered and
  holds none — a 404 is an answer), `unchecked` (a 5xx or a transport failure), plus
  `skipped_offline`. It raises nothing; the outcome *is* the contract, which is why it joins
  `Grch37Client` in the exception-contract suite's named exemptions rather than being given an error
  type to leak.
- **`identity_derivation="caid"`** — the snapshot now **keeps** a CAID-only row with null coordinate
  and null rsID, instead of dropping it. It has a *route* to an identity rather than an identity, and
  dropping it made the recovery invisible to every later pass. `unresolvable_identity` now means no
  identifier of any kind, and falls from 204 rows to 59.
- **The pass runs at draft time, not build time.** A build that fetched would forfeit the offline
  byte-reproducibility that is the whole reason `civic build` reads a dated file. `--offline` is the
  switch, as it is everywhere in this tier, and a run without the registry withholds those rows as
  **`caid_unresolved`** — unplaced, never unplaceable.
- **The rs-number is preferred over the coordinate**, and the reason is the item's central argument:
  ClinGen supplies it and the ordinary resolution chain verifies it against **Ensembl**. Two
  authorities, so the check is real — which is precisely the property a lifted coordinate lacks.

- **One-sided indels are anchored VCF/Picard-style, and that closed the last recoverable class.** The
  registry states an insertion as `referenceAllele=""` and a deletion as `allele=""`, in interbase
  terms — neither is a row a `ref`/`alts` pair can hold. Prefixing both sides with the single
  reference base before the event is the left-aligned representation VCF requires, and the registry's
  interbase `start` *is* that anchor position for both shapes, so one rule covers them with no
  per-shape arithmetic. `anchor_indel` is a pure function with the base reader injected; the reader is
  `SequenceProxy`, already in this tier for the reference-allele check. **All 35 rows that previously
  read `no_identity` are one-sided indels, and every one anchors.**

  Verified two ways rather than asserted: the reference base at `chr3:10142013` is `G`, and ClinGen's
  own HGVS for that allele is `NC_000003.12:g.10142013dup` — a duplication of `G`, which is exactly
  the `G>GG` row produced. An anchor that cannot be read is withheld under its own reason
  (`anchor_base_unreadable`), never guessed: a guessed anchor is a wrong `ref` on a right position,
  which is the mismatch class `sequences.RefMismatch` exists to report.

Measured end to end, the drafter goes from **115 variant rows offline to 201 online**, withholding
nothing.

### Repairs rejected

- **Liftover.** Reopened at the maintainer's instruction with new balance weights and refused on the
  measurement — the full probe is [CIVIC_UNRESOLVED](probes/CIVIC_UNRESOLVED.md). Its ceiling is
  **13 evidence rows on 9 variants**, 2.4% of the corpus, and after analysing what those events *are*
  the honest recovery is **at most one variant**. Three are gene-level assertions (`Loss`, `Mutation`)
  that no genotype satisfies on any build. Five are imprecise by the source's own HGVS
  (`c.1-?_340+?del`) — the ClinGen registry **refuses those expressions outright**, which is a
  stronger statement than a count: they have no allele identity on either build. And variant 2099 is
  the worked instance of RM48's hazard: its own coordinate pair says 15 bp while its name and alias
  say 24, and lifting CIViC's coordinate exactly yields **a different allele** from the one the source
  is describing. The format cannot defend itself either — a fabricated `<DEL:340>` and a bare
  gene-span locus both compile clean in both modes.
- **`pyliftover` as a dev dependency.** Tried. It agrees with Ensembl on all 18 endpoints, so it buys
  no accuracy; it downloads an unpinned chain file from UCSC at construction; and the assembly-map
  endpoint already returns interval *segment structure*, which two point-lifts cannot.
- **Picard `LiftoverVcf` as the tool of record.** Not run, and the reason is worth keeping. Two
  independent implementations already agree to the base on all 18 endpoints, so a third would confirm
  arithmetic nobody disputes — while eight of the nine carry no `REF`/`ALT` at all, so feeding
  `LiftoverVcf` would mean **fabricating** symbolic records with invented spans, which is
  manufacturing the input whose correctness is the question. The blocker was never the mapping.
- **Resolving CAIDs inside `civic build`.** It would make the snapshot depend on a live service and
  cost the reproducibility the dated input exists to provide.
- **Inheriting ClinGen's CC0 for the registry.** The gene-curation surface is CC0; this is a different
  surface, and `reg.clinicalgenome.org/site/terms` answers **HTTP 200 with a generic Genboree
  "broken link" page** — a soft-404, the same shape as HPO's licence URL. Every axis is recorded
  `None`: unknown is not permissive. Nothing is redistributed, and reading a public endpoint to place
  a row is a read rather than an acquisition anyone has gated.

### Charter check

P2 — the fetch is in the enricher, the only tier permitted one. P3/P8 — no column, no table, no
vocabulary member; a new `identity_derivation` value on a **derived snapshot**, which is not the
authored surface. P5 — `caid_unresolved` and `caid_no_identity` are two withhold reasons because they
are two facts, and collapsing them is the S20 defect. P7 — the snapshot stays byte-reproducible
precisely because this pass is not in it. P9 — zero authored-layer cost.

### What it left open

**53 variants carry no identifier at all**, and five of the nine coordinate-bearing ones can never be
reached by any identity pass, because an unambiguous identity does not exist for them. That is a
permanent floor on CIViC's germline reach rather than a gap to close.

Two smaller residues are sized in the probes and not taken: 26 unresolved variants publish a GRCh38
**deletion** accession the substitution-only parser cannot read *directly* — most are reached through
the registry instead, which is why this was not worth a second parser — and 31 carry a `c.` HGVS
inside their *name* rather than in `hgvs_descriptions`. Whether a name plus a transcript resolves
through the registry was not measured and is the obvious next question.

**Measured on 2026-09-01, and the answer moves this item's residue a long way.** It does resolve: all
53 were put through a four-tier identity procedure and **34 of them have an identity**, from the
fragments CIViC publishes in the variant's own name. The paragraph above understated it by testing a
per-**gene** fact (which transcript a `c.` fragment is numbered against) as a per-**record** one, so
29 variants were written off for lacking a `representative_transcript` cell. Thirty-three of the 34 were adopted the
same day as **RM159**, taking coverage from 237/290 to **270/290 variants** and 474/533 to **507/533
rows**; the one held back is `TP53 R72P`, whose identity is the reference allele and so is not a
`ref`/`alt` row. The "53 carry no identifier" sentence
above therefore stands only as the state at this item's cut. What survives unchanged is the five that
can never be reached, plus six more that name a class of event rather than an allele. Class by class,
with the four wrong CIViC names and three self-duplicates the round also turned up, in
[CIVIC_UNRESOLVED](probes/CIVIC_UNRESOLVED.md).

## RM152 — CIViC's germline quarter says almost nothing on the axis we asked it, and a great deal on the one next to it

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-enricher`; additive — a new snapshot
builder, a new drafting source, one licence row, and no schema change of any kind).
**Severity** low-medium · **Owner** enricher · **Motivating case**
[S84](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator), 2026-08-31

**The item was filed carrying no release class**, because both adoptions S84 proposed had been refuted
by measurement and an item with no repair has none to state. It acquired one when the probe it named
was finally run: the refutations stood, and a third route nobody had proposed turned out to be
buildable. The full measurement record is [CIVIC_SURVEY.md](probes/CIVIC_SURVEY.md), which is evidence
and not contract.

### What was measured, and by whom

S84 reported the germline split and declined to claim the follow-up probe. The reply named it —
`SUPPORTS`/`DOES_NOT_SUPPORT` × `PREDISPOSITION`/`PROTECTIVENESS` against `VALID_DIRECTIONS`, over a
corpus that can say how much it reaches — and it was run on 2026-08-31. Every figure in the item
reproduced, including the 412 obtained by subtraction. Four things it did not know:

1. **The contested count was wrong in both directions.** The item read `PREDISPOSITION` ×
   `DOES_NOT_SUPPORT` as "4 items, precisely the reading `contested` was added for". Grouped by
   molecular profile it is 1; grouped by **variant**, which is the granularity identity uses, it is
   **3**, because a two-variant profile's refuting row propagates to both members while each carries
   supporting evidence on its own profile. Two of the original four are lone refutations, which
   `contested` does not describe. **Genuine opposition — a risk call against a protective one — is 0**,
   at every scope probed and under every status basis.
2. **Widening the scope changes nothing.** All 620 variants re-swept with no origin, significance or
   status filter: 2,811 items, 11 newly camp-bearing, every one `SUPPORTS` on a variant already
   carrying risk, **0 new contested variants**.
3. **The assertions table cannot carry the axis at all.** Not thinly — *structurally*.
   `AssertionSignificance` is a different 16-member enum that does not contain `PREDISPOSITION` or
   `PROTECTIVENESS`, so filtering by them is a GraphQL type error rather than an empty result. No
   CIViC assertion can ever hold a direction call, however the database grows.
4. **The number everything quotes has an undeclared denominator.** Both connections default to
   `status: NON_REJECTED`, so the 11,518 in the item and the report is that basis; `ACCEPTED` is 4,904.
   The bulk TSV release is `accepted`-only at 4,903 rows. Two published surfaces of one source, 2.35×
   apart, neither declaring it.

### What shipped

- **`civic build`** — a dated release reduced to one parquet plus `release.json`, byte-reproducible.
  It reads the **bulk TSVs**, not the API, because only the download side has dated releases and a
  snapshot that cannot name its input cannot be reproduced; `release.json` records the `accepted`
  basis so a count from it is never compared with one from the API. Three input files, because
  `MolecularProfileSummaries.tsv` is what tells a combination genotype from a dangling reference.
- **`draft-panel --source civic`** — writes `direction`, never `clin_sig`, reading the snapshot.
- **`CIVIC_TERMS`** — CC0 1.0, permissive on all three axes.
- **A defect in shared drafting code**, found by dogfooding rather than by review: `append_partial_rows`
  built its covered-set from `partials[0].match_on` while comparing each row against its own, so a
  batch of mixed arity re-added rows on every lap. Fixed at the provider and guarded at the helper.

### Repairs rejected

- **CIViC as a concordance authority.** S84's preferred candidate, refuted before this round and
  confirmed by it: five germline ACMG-tier calls, **zero** benign-class, so `discordant` is unsayable.
- **A `direction`-axis concordance apparatus.** The open question the item carried, and the answer is
  no. Genuine opposition is 0; the 3 contested variants are claim-against-refutation, all three
  dissolve under `ACCEPTED`, and nothing else in the enricher fills `direction` — `clinvar_draft`'s
  fold targets `state`, the legacy axis, and `@axes-passthrough` bars crossing them. A concordance
  record needs two authorities and this axis has one.
- **`draft_from_civic` on the `clin_sig` axis.** Still refused, and the surviving half of the item's
  own objection is the silent somatic drop — now a counted drop rather than a filter. The half that
  did **not** survive is "it would write rows with an empty significance column": true of `clin_sig`
  at 812 `NA`, and false of `direction`, where `NA` is 0 of 1,458. The rejection had been measured on
  the axis the report aimed at rather than the one the item itself identified as surviving.
- **Liftover, to reach the GRCh37 coordinates.** Reopened on the maintainer's instruction and closed
  again on the number — see [RM153](ROADMAP_HISTORY.md#rm153--the-identity-civic-does-not-publish-recovered-through-the-registry-rather-than-by-lifting-a-coordinate).
- **Reading "does not support predisposition" as `protective`.** A refutation removes a claim without
  establishing its opposite. The row is kept, the axis value withheld, and the count reported.

### Charter check

P1 — a snapshot is data and a drafted row is an ordinary authored row; no predicate language. P2 — all
of it in the enricher, the only tier permitted to fetch; the compile path imports none of it. P3/P8 —
**no schema change at all**: no new column, no new table, no vocabulary member, nothing demoted or
retyped, no published module invalidated. The whole adoption rides on `direction` and `state`, which
have existed since 0.3. P5 — `direction` and `clin_sig` stay separate axes, which is the entire finding.
P7 — a rebuild is byte-identical and a re-draft is a no-op, both pinned. P9 — the snapshot is the free
layer and the drafter writes only authored columns that already exist, so the authored surface is
priced at zero.

### What it measured

Over the `01-Aug-2026` release: 4,878 evidence rows in, 329 kept on 133 variants; dropped
`non_germline_origin` 4,067, `not_direction_axis` 278, `unresolvable_identity` 204, and the two
structural reasons 0 each. Identity: `rsid` 305, `both` 17, `grch38_hgvs` 7. Drafted into an empty
spec: 110 variant rows and 311 study rows, every study row carrying a real PMID.

## RM146 — every authored column now says which release it appeared in

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`; **additive** — a marker on each
field declaration, no column, no parquet, no signature). **Severity** medium · **Owner** format
(schema) · **Motivating case** [S81](CONSUMER_SUGGESTIONS_HISTORY.md) (just-dna-registry, relaying
just-module-creator)

### The finding

A module authored on 0.6.6 was sent to a registry deployment running format 0.6.1, which runs our
`validate_spec` server-side and reports its findings verbatim:

```
studies.csv line 2 [curator]: Extra inputs are not permitted
```

`StudyRow.curator` is ours, added in 0.6.5. A genuine typo produces the byte-identical shape
(`[curatr]`), and the two want **opposite actions** from an author — upgrade the reader, or fix the
cell. The finding is pydantic's under `extra="forbid"`, so it could not be reworded into carrying the
distinction: the information was not in the model at all.

### What shipped

`base.since("0.6.5")` on every authored field, read back by `base.field_first_seen(model)`. It
composes with `vocabulary()` rather than replacing it — both are entries in one `json_schema_extra`
dict — and `stamped_identity_field` takes `first_seen` as a **required** argument, because a
compiler-stamped column is still one an older reader refuses and defaulting it would let the next such
column inherit a version nobody measured.

**On the field, not in a roster.** A list keyed like `release_records` was the alternative and loses on
the rule this repo keeps relearning: a hand-kept list beside a model is a second statement of one fact,
and it is the copy that goes stale. Declared on the field, it travels through every rename and move.

### The backfill was measured, and the numbers are worth recording

Parsed out of each release tag's own sources — `git ls-tree` per tag, the model classes read from the
**AST** rather than imported, since old code need not import under a current Python. **414 fields
across 31 models**, and the distribution is a fair summary of this format's history: 115 fields date to
0.2.0, 81 to 0.4.0, 150 to 0.5.0, 160 to 0.6.0, 3 to 0.6.5, and 78 land in the uncut 0.7.0.

**`curator` is the worked example and it is the reason the answer is per `(model, field)`**: it is on
`VariantRow` from 0.2.0 and gains its `StudyRow` twin only in 0.6.5. A roster keyed by column name
would have given one answer for two facts — and the wrong one for the module in the report.

### The guard, and why it is an equality

`test_first_seen.py` asserts **set equality over the walked registry**: every field of every model in
`_ALL_MODELS` declares one. A floor (`>= 400`) or a truthiness check is satisfied by exactly the state
that produced this report (`@registry-completeness`). Two guards ride with it — the registry itself is
checked for completeness, since a guard over an incomplete registry reports a clean bill about the
models it happens to know (RM96's shape), and every declared version is checked against the set of
releases that actually exist, because a typo'd number is the one error the model cannot catch itself.

### Two things the build turned up

**A mechanical edit needs an AST, and the AST needs to know what a field is.** The first pass wrapped
nine `ClassVar` declarations — `ALLELE_COLUMNS`, `REQUIRED_ANY_OF` — in `Field(...)`, which is not a
field at all; the suite caught it as `TypeError: 'FieldInfo' object is not iterable` from the tests
that iterate those constants. Unwrapped by AST rather than by regex, because the multi-line forms are
invisible to a line-oriented pattern.

**The entry said 402 fields and the tree holds 414.** It was written before 0.7's own additions
landed, which is the ordinary fate of a counted number in prose (`@counted-prose-needs-a-fixed-field`)
— and the reason the test asserts a floor on the *total* while asserting equality on the *coverage*.

### Repairs rejected, kept from the entry

Reading `release_records`' `parquet_schema` axis names **4 of 402** authored columns, because it records
what a release changed about compiled output; `curator` happens to be there, which is what makes it
dangerous — right for the case in hand, silently wrong for 398 others. Rewording the pydantic message
has nothing to word. Loosening `extra="forbid"` removes the guard that catches the typo half. And a
compatibility handshake was explicitly *not* asked for; the reporter corrected their own side.

### What it does not settle

A reader still cannot be told *which* release it is missing without also knowing its own — that pairing
is the consumer's, already shipped in their 0.22.0, and stays theirs. This supplies the half nobody
outside this repo can compute.

## RM117 — the vindication signal shipped, and it replaced a message that read as an accusation

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`).
**Severity** medium · **Owner** enricher when filed, compiler as built · **Motivating case**
[S52](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### What the item was by the time it was built

Two halves settled before this one. `ProvenanceItem.outranks` — `{column: why}`, per column, additive
— landed 2026-08-20 so an author overriding a checked value has somewhere to record why. The
**severity** half was closed on 2026-08-21, not deferred: putting a checked verdict under authored
control is something nothing else in this format does. What remained was the observability half: two
signals a check can compute because it runs on every compile and needs nobody's permission.

**Recast onto the overlay rather than `outranks`.** The entry proposed both signals over
`provenance.json`, and by 2026-08-28 that was the wrong file: RM135 settled the overlap as a dated
succession, `outranks` is filed for removal at the major, and `concordance.py` already names the
overlay as where an answer goes. Growing observability on a field queued for deletion is what RM135
warns against, so the signals compute from `overrides.csv`, where the surviving mechanism is.

### The signal was already firing, with the wrong words on it

This is the part worth keeping. `clin_sig_concordance.csv` holds **contested subjects only** and is
**rewritten whole**, and `concordance.py` states outright that a subject leaving the record is how an
author learns the archive caught up with them. So the state RM117 wanted to observe — *the archive
resolved a conflict the author had answered* — already produced an observable: the overlay row reaches
nothing.

What it produced was the generic finding, offering *the subject may be mistyped, or the correction may
be aimed at a row the compiler drops* — put to an author in the one case where their judgement had just
been confirmed. **So the work was not adding a signal; it was stopping a wrong one**, which is why this
earns a code (`overlay_answer_vindicated`) rather than a rewording, and why the test asserts the
misleading line is **gone** as well as that the good one appears.

### It is an observation, not a verdict, and the wording is pinned

The authorities agreed and the overlay row is now unnecessary. Whether the author was right about the
biology is not something a compiler can say. The test greps the message for adjudicating words on a
**word boundary**, and it caught a real one: the first wording said *the conflict ended rather than
that the correction is wrong*, which grades the author's row while claiming not to. The published
sentence says the disagreement ended and the row can be retired.

### The second signal was filed rather than built, and shipped the same day

*A record whose row's value has changed again* needs the archive's value **now** against its value at
record time, so it needs a fetch — enricher work, with the offline/no-snapshot/nobody-asked ladder
every network check here carries. It is **RM151**, and it turned out more tractable than this entry
assumed: `clin_sig_authority_calls.csv` records each authority's call, its verbatim wording and its
release, so the baseline exists — for the concordance pair alone, which is the scope RM151 states. It
is below, shipped inside the same uncut 0.7.0.

### Scope

One table, because one table's absence has a single reading. Every other overridable table's unmatched
update is ambiguous and takes RM137's split; `VINDICATING_OVERLAY_TABLE` names the exception, and the
routing is a `continue` rather than a reachability predicate, since the generic classifier's two
readings are exactly what must not be printed here.

## RM151 — the second vindication signal, and the baseline is the file the same run overwrites

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-enricher`). **Severity** low-medium ·
**Owner** enricher · **Motivating case** [S52](CONSUMER_SUGGESTIONS_HISTORY.md)
(just-module-creator), RM117's second signal

RM117 shipped the signal that a subject has **left** the concordance record. This is the other one: an
`overrides.csv` row answering a contested subject is a judgement written *about a particular
disagreement* — the archive said X, the author says Y, and `reason` explains why — and if the archive
later says Z, that reason was written about a value that is no longer there. Nothing distinguished a
justification that still describes the disagreement on file from one that describes a disagreement
since replaced by a different one.

### The baseline exists, and it is exactly one file

RM117 said a record "is not bound to the value it justifies", and for the concordance pair that is no
longer quite true. `clin_sig_authority_calls.csv` records what each authority actually said —
`clin_sig`, the verbatim `clin_sig_raw`, and the `dataset` release it came from, keyed
`(variant_key, genotype, authority)` — so recorded-call against fresh-call is available here and
nowhere else in this format.

**Scoped to that table, and the finding says so in its own text** (`@probe-names-the-table`). An
overlay row against `frequencies.csv` or `resolution.csv` has no recorded prior value at all, so a
general *the value moved* check would be answerable for one table and silently absent for every other
— an unscoped negative becoming a permanent false constraint.

### The ordering is the feature, and it is guarded where a refactor would break it

`write_concordance_tables` replaces the record whole, so the previous run's rows exist only until this
run commits. The comparison is therefore computed in the staging phase, above the commit — which
`enrich()` already does for every product of a run, for the unrelated reason that a refused `strict`
run must change nothing. No assertion over a return value can see statement order, so the test walks
the AST and asserts the read's line precedes the write's, in the same enclosing function. The guard
was demonstrated to fail on a source copy with the two swapped before it was kept.

### A move is observable exactly once, and that is the honest shape

The run that notices also rewrites the baseline; the next run compares against the new one and is
silent. Persisting it needs the overlay row **bound** to the value it justifies — a column on
`overrides.csv` recording what the answer was written against — and that is a schema change to the
authored surface, a minor rather than a patch, and precisely the binding RM117's three objections all
turned on missing. **None of those objections is an objection to noticing that the value moved**, which
is why this ships as an observation and the binding stays unbuilt. Decided per item with the maintainer.

### Three states, and the third is the whole point

Unchanged is `recorded` on both sides with the same classification, `dataset` moved or not: a
re-released archive saying the same thing has not moved the disagreement. A **shift** is a changed
classification, or `recorded → no_record` and back — asked both times, and the answer differs.
Everything else is **withheld**, `no_prior_record` or `unchecked_now`, and reported as an info note.
Neither withheld state ever reads as *nothing moved*: telling an author their reasoning still stands on
evidence nobody looked at is the one way this check does real harm, and it is what the tests spend
their weight on.

**A move this tier's own normalizer made is reported apart from the archive's.** Same verbatim
`clin_sig_raw`, different normalized member, means `clin_sig.py` changed rather than ClinVar — a fact
about our code with nothing for an author to do. Folding it in would accuse a source of a change we
made.

### What counts as an answer, and why it is the opposite rule from RM136's

**Any overlay row naming the subject** — every operation, every field. What goes stale is the `reason`,
which the model makes mandatory on every row whatever the row does, so a per-field rule would have to
name a column the reason does not live in. RM136's `overlay_answers` is per field for the opposite
direction: it decides whether a finding may be **silenced**, and anything looser silences findings the
author never looked at. A finding raised too widely costs a reader one line; one silenced too widely
costs them the finding. `licensing.overlay_answered_subjects` is the second reader, beside rather than
inside the first.

### The boundary with RM117, and the wording

A subject that has left the record entirely never enters this comparison: that is
`overlay_answer_vindicated`, reported by the compiler as good news, and hanging a second and gloomier
finding on the same overlay row is exactly the *already firing with the wrong words* failure RM117 was.
The messages are pinned by a word-boundary grep refusing `correct`, `wrong`, `mistaken`, `vindicated`,
`confirmed` and their siblings — *the disagreement you answered is not the one on record now* is a
statement about the record, and *your answer may be wrong* is a verdict this check cannot see the
reasoning for.

**Warning-tier in both modes, escalating in neither** (`@clinsig-never-escalates`), with more force
than the record itself: gating on it would make an artifact refuse over an archive's release schedule.

## RM138 — closed: the duplication costs 1.84× raw and 1.06× compressed, and the encoding stands

**Closed on 2026-08-31 with no code change**, inside the uncut 0.7.0. **Severity** low · **Owner**
format (schema) + compiler · **Found by** reviewing RM131 against its own motivation

**Not a defect, and the entry said so first.** The shape was decided per item with the maintainer — a
`carried` list beside `warnings`, holding the subset the author cannot clear — over a field on each
finding, because it invents no permanent names and a consumer subtracts to get the actionable set.
Both properties hold. What the decision did not have in front of it was the size, and the size is the
thing RM131 exists about.

### The number that was missing, measured rather than argued

The entry measured the raw cost at **1.84×** across the corpus. The question it left open was whether a
published manifest should pay that. Re-measured on 2026-08-31 with the compression a real transport
uses, over every reference example that emits a warning:

| module | warnings | carried | raw | gzip |
|---|---|---|---|---|
| `pathogenic_clinvar` | 113 | 109 | 1.96× | **1.13×** |
| `hboc_palb2` | 12 | 12 | 2.00× | **1.07×** |
| `shox_par1` / `apoe_epsilon` | 2 | 2 | 2.00× | 1.05× / 1.07× |
| `htt_repeat_expansion` | 3 | 1 | 1.33× | 1.02× |
| **corpus** | | | **1.84×** | **1.06×** |

The raw column reproduces the entry's figure exactly, which is what makes the second column
trustworthy. **`carried` is a verbatim subset of `warnings`, which is precisely the input DEFLATE's
back-references are for**, so the duplication that doubles the bytes on the wire uncompressed adds
**6%** compressed — and the whole with-`carried` payload gzips to **0.21×** the *uncompressed*
warnings-only one. The worst case in the corpus, the 113-warning module the item was filed about, pays
13%.

### The decision

**Keep the encoding, and recommend compression where the size matters** — a catalog serving many
manifests, an API response, anything shipping `manifest.json` over a wire. That is a deployment
concern rather than a schema one, and it is where the cost actually lands.

The three cheaper encodings the entry weighed stay rejected, unchanged, and their reasons are now
cheaper to accept because the thing they were buying is worth ~6%:

* **`carried: list[int]`, indices into `warnings`.** Breaks the one property the field was chosen for
   — the subtraction becomes a zip, and an index means nothing to a consumer that filtered or
   re-ordered the channel. It also positionally couples two published fields, which
   `manifest.compilation.warnings` has always avoided.
* **`carried: list[str]` of codes.** Answers a different question, and one already answered:
   carried-ness is a property of the code alone, so `warnings_summary` plus `CARRIED_WARNING_CODES`
   gives the count without this field at all.
* **Drop `carried`, publish a per-message `codes: list[str]`.** The genuinely minimal encoding, and
   still a **third** shape rather than the decided one — it re-introduces the positional coupling and
   hands every consumer a derivation where they currently read an answer.

**Closing it now rather than leaving it open is the point.** A fourth encoding after 1.0 is a removal,
and removals are major-only under Principle 3, so this had to be settled inside 0.7 either way. It is
settled with a number rather than by drift.

## RM136 — the enricher reads the author's overlay, so a correction stops coming back forever

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-compiler` — one loader made public —
plus `just-dna-enricher`). **Severity** medium · **Owner** enricher · **Found by** the wave-1 audit of
RM124, 2026-08-28

### The asymmetry

The compiler applies `overrides.csv` before any check reads a row, which is the whole point: a check
must report on what the module asserts. The enricher did not — its passes re-read the raw derived file
— so an author who corrected a `resolution.csv` cell through the overlay went on being told the same
finding on every subsequent run, forever, with no way to clear it and no indication that the
correction had been recorded and honoured one tier over. `INTEGRATION_0_6` states the asymmetry for
*consumers*; it was never stated for the **author**, who meets it first and has no parquet to read at
the point they are curating.

### The decision, and the line it draws

**Read-only, at INPUT reads, per field.** Three separable choices, and each has a refused alternative:

* **Read-only.** The enricher never *writes* through the overlay: an overlay row is the author's
  answer to a difference, never the tier's (RM83's standing refusal).
* **Input reads only, never merge baselines.** A pass that reads its own output file to merge against
  it writes that file back, so feeding it post-overlay rows would bake the correction into the derived
  table. The three input sites — `frequencies`, `assertions`, and `identifiers`' gene-locus check —
  read `resolution.csv` as an input to something else and take the overlay; every merge baseline stays
  raw. Same rule the sidecar gotchas already state from the other side: read the file you write.
* **Per field, not per row.** A finding is answered when the overlay `update`s the very cell the
  finding is about, so correcting a coordinate silences the coordinate check and leaves an unrelated
  `clin_sig` finding standing. Per row was cheaper and was refused: an author correcting one cell would
  silence findings they never looked at, which is the silent-suppress hole the overlay's design calls
  its worst case.

**No second implementation of `apply_overrides`** — the entry's central refusal, on the grounds that
two copies would drift on exactly the normalization seam that produced a silent P7 break in this
feature's first week. `compiler.load_overlay` became public (the S74 shape: a private symbol the
enricher would otherwise reach into) and `licensing.overlaid_input_rows` calls *the* `apply_overrides`.
A test compares the helper's output against `apply_overrides` directly, so a future copy would be seen.

### Answered is not agreed, and that is what keeps it honest

An answered pair **leaves `disagreements` and stays in `subjects`**, with `PairCheck.answered`
counting it and one INFO line saying so. The comparison ran and found a difference; dropping it from
the denominator would report a cleaner module than there is, which is the silent-success shape this
codebase keeps closing. What changes is only that the difference reads as *settled by the author*
rather than as work owed — and the author finally gets the acknowledgement that was missing.

### What it does not reach, stated rather than left to be discovered

One check consults the answered set today: the rsid↔coordinate comparison, which is the finding an
`overrides.csv` row on `resolution.csv` can actually answer. The mechanism is general — `overlay_answers`
takes a table name — but a check is wired to it deliberately rather than in bulk, because "which cells
does this comparison read" is a per-check fact and guessing it wrong silences a finding nobody
answered. `_COORDINATE_FIELDS` is that fact written down for the first one.

## RM137 — the unmatched-overlay warning is now a property of the module, not of the lap

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`).
**Severity** low-medium · **Owner** compiler · **Found by** the wave-1 audit of RM124, 2026-08-28,
reproduced end to end

### The defect

`reverse_module` rebuilds a derived table from the artifact, and two of the eight overridable tables
are rebuilt from something narrower than the file the compiler read: `literature.csv` loses its uncited
rows before the parquet and is rebuilt *from* that parquet, and `resolution.csv` has no parquet at all
and is rebuilt from the SNP core, which re-emits only positioned rows. An `update` naming such a row
matched on lap 1 and warned on lap 2, so a module and its own `compile → reverse → compile` disagreed
on `manifest.compilation.warnings` — a published field, and one RM126 had made load-bearing.

### What "count it over the overlay's own rows" means in code

The decision was to report the finding the way `suppress` reports its own — over the overlay rather
than over what it reached. Turning that into code needed one step the entry did not have:

* counting the overlay's `update` rows outright is a **tautology** that fires on every healthy module
  (`@tautology-zero`);
* counting the ones that reached nothing is the **lap-dependent original**.

The stable quantity is neither. It is a property of the **target**: *could an artifact of this module
carry that row at all?* For `literature.csv` that is "is the PMID cited", and for `resolution.csv` it
is "can the module place that `variant_key`" — both computable from data that survives the round trip,
so both answer the same on lap 1 and lap 2 whether or not the row is there to be matched.

**The unreachable finding therefore fires matched-or-not, and that asymmetry is the whole fix.** An
earlier cut of this classified only the *unmatched* set and was silently lap-dependent all over again:
on lap 1 the uncited row is present and the update matches, so nothing was reported. Caught by
asserting **equality between the two laps** rather than "lap 2 warns", which would have passed on the
broken code.

### Two readings, and neither of them is "a typo"

That framing was the original entry's and it is wrong. A mistyped PMID is also an uncited one and a
mistyped `variant_key` is also an unpositioned one, so a mistake lands in the *unreachable* bucket.
What the reachable bucket really means is narrower and more useful:

* **`overlay_update_unmatched`** (reworded) — the subject *is* cited or positioned, so the artifact
  could carry the row and the sidecar simply does not have it. Re-run the enrichment pass.
* **`overlay_update_target_unreachable`** (new, actionable) — no artifact of this module can carry the
  row. Two readings, named rather than collapsed: the subject may be mistyped, or the correction may
  be aimed at a row the compiler drops and be perfectly fine.

### Scope, and why it is not a dodge

Only `literature.csv` and `resolution.csv` — `LOSSY_OVERLAY_TABLES`, asserted as an equality over the
walked registry. The other six rebuild whole on a reverse, so an `update` reaching nothing there is
unmatched on **both** laps already and needs none of this. The predicate is defined only where the
loss is, and a table added to `OVERRIDABLE_TABLES` has to face the question deliberately.

### Two traps the build hit

**The predicate must share the drop's own function, not restate it.** `cited_pmids` was extracted out
of `split_cited_literature` so both ask one question; two statements would drift, and in the worst
direction — the predicate would call a row unreachable that the drop had kept, and a healthy overlay
would report a finding forever.

**And it must mirror the drop's empty-cited guard.** `split_cited_literature` discards *nothing* when
the module cites nothing at all, on the stated grounds that such a module cannot distinguish a stale
sidecar from citations not yet authored. Without the mirror, every literature `update` on such a module
reads as unreachable — a **stable false positive**, which is worse than the unstable true one.

### Where the classification happens, and why it moved

Not at apply time. `apply_overrides` runs before any check reads a row, and the question needs
`studies.csv` and the citing tables, which `validate_spec` and `compile_module` both load later. So
`apply_overrides` gained `defer_unmatched=True` (additive, default off), the unmatched set is stashed
from the **pre-overlay** rows — apply rebinds its input, and an `insert` earlier in the same overlay
would otherwise make a later update look matched — and one shared helper splits it late in both
functions, so the two cannot classify differently (`@parity-by-check`). Hoisting the `studies.csv`
load instead was refused: pre-flight warnings seed the compile's list, so reordering the load reorders
a published field for no gain.

## RM150 — `unknown` was carrying an absence and a finding, and `contested` takes the second

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`). **Severity** low-medium ·
**Owner** format (schema) · **Motivating case** [S83](CONSUMER_SUGGESTIONS_HISTORY.md)
(just-module-creator), the residue RM148 did not take · **Taken into 0.7 by the maintainer** on the
grounds that there was no sense postponing it — it was filed to `ROADMAP_0_8.md` earlier the same day
and moved here without its shape changing.

### The shade RM148 left

The reporter said `direction`'s `unknown` covers three things: *no evidence*, *conflicting evidence*,
and *evidence that does not exclude either direction*. RM148 removed the third by **reassignment** —
an unestablished sign is still a sign, so that state is the pair `direction=<sign>` +
`stat_significance=not_significant`, and a member for it would have been a second spelling. That
reasoning holds and is not reopened.

It does not reach the first two, and RM148's own field description said so out loud — *"not assessed,
or the sources conflict"* — while adding nothing that told a consumer which. **They are not one thing:
one is an absence and the other is a finding.** The reply to S83 asserted the two were "one thing
(nothing to record)", and that was our assertion rather than the reporter's concession.

### The decision, and why the member is earned here where it was refused there

`contested` is added and **`unknown` keeps its original meaning**. Both halves are load-bearing.
Re-pointing a shipped member at the narrower sense would silently change what every published module
already says by it — a retype in everything but name, and Principle 3 territory; adding beside it is
minor-legal. The name is the workspace's own word for the same idea one table over
(`clin_sig_concordance.csv` is one row per *contested* subject, and `clin_sig_concordance_contested`
is an existing warning code), so coining a synonym would be the drift
`@one-normalizer-two-spellings` records.

The cost that made RM148 refuse a member — a wire vocabulary gains one — is paid here because this
shade is genuinely **not expressible as a pair**: no combination of `direction` and
`stat_significance` says *two sources disagree about the sign*.

### The trap, and it is why the map was the first edit rather than a follow-up

`trimmed_state()` projects a `direction` back into the legacy `state` set through
`_DIRECTION_TO_STATE.get(direction, "neutral")` — **a `.get` with a default, not a lookup that
raises**. Measured before anything was changed: `trimmed_state("contested")` already returned
`"neutral"`, and so does `trimmed_state("a string that is not a direction")`. So adding `contested` to
`VALID_DIRECTIONS` and stopping there ships a module whose `upgraded()` silently emits the wrong
legacy `state`, with nothing failing anywhere.

The map entry therefore went in first, and the guard is a **registry-iterating equality** —
`set(_DIRECTION_TO_STATE) == VALID_DIRECTIONS`, walked. A test asserting
`trimmed_state("contested") == "neutral"` would have passed against the unfixed code and measured
nothing; the assertion has to be about the map's *coverage*, not its output, and the test says so with
the demonstration beside it. `contested → neutral` is the right projection once it is **explicit**:
the legacy set has no member for it, and `neutral` is where `unknown` already lands.

### What it deliberately did not touch

* **`_STATE_TO_DIRECTION` gains nothing.** The two maps look like they should mirror and do not: no
  legacy `state` value means *the sources disagree about the sign*, so there is nothing to map from. A
  module upgraded off the legacy column can never produce `contested`; only an author writing
  `direction` directly can. Commented at the site, because it invites a "fix".
* **`stat_significance` gains nothing.** Two sources disagreeing about the *sign* is not two sources
  disagreeing about the *strength*, so the two vocabularies' intersection is still exactly `unknown` —
  asserted, so a later member has to face the question deliberately.
* **Nothing re-points, so nothing drifts.** `upgraded()` stays idempotent and `needs_upgrade` does not
  start reporting existing `unknown` rows, which is the half that makes this an addition rather than a
  retype.

## RM155 — the identifier roster read one table while eleven carry the column

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`) ·
**Owner** enricher · **Motivating case** S86 (just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md)

`check_identifiers` built its trait and gene rosters from `variants.csv` alone. Walking `_ALL_MODELS`,
**eleven** authored models declare `trait_efo_id` or `gene` — `StudyRow` has carried the trait column
since 0.3 — so a 67-variant module carrying the id on all 68 `studies.csv` rows reported nothing
checked and nothing flagged, and could ship a retired or simply wrong CURIE with every gate green.
Reproduced offline in both directions before anything moved.

**The unreadable `0` is the item; the missing table is only how it got there.** `traits checked: 0`
asserted *this module declares no trait* and *its traits are in a table nobody read* in one breath —
`@unreachable-not-absent` at a finer grain, a question never put rendered as an answer. Widening the
roster alone would have left that hole, because a wide roster still returns `[]` for a module that
genuinely declares none. So the fix is both halves, which is what the reporter proposed as an
either/or and is really an and: `IdentifierReport` gained `trait_tables_read` /
`trait_tables_not_read` and the gene pair beside them, and the CLI count names its own denominator.

**The roster is derived from `DRAFTABLE`, never listed.** A hand-kept set would be the same defect with
a longer literal in it, so the test asserts an **equality over the walked `_ALL_MODELS`**
(`@registry-completeness`) and a table kind added later joins by existing. Nine tables carry
`trait_efo_id`, nine carry `gene`. Two edges the walk settled: `MeasureBinRow` is correctly absent as
the abstract base whose four concrete subclasses are each their own entry — pinned rather than assumed
— and the three **derived** models carrying these columns (`GeneMetricsRow`, `GeneValidityRow`,
`GwasEffectRow`) are outside the roster on purpose, since a stale id in a machine-written row is the
*source's* currency and no author can act on it. Widening to them would report findings against rows
nobody wrote, and `dataset_currency` is the surface that asks that question.

**A third instance, one level up, found by the same framing.** `report.clean` is `all()` over a set
that can be empty, so `check-identifiers` printed a green *"all identifiers current"* having asked
nothing at all. It now says what it read. Worth the general form: a predicate that is `all()` over a
possibly-empty set reports a pass it did not earn.

An absent optional table and one that exists and will not parse are kept apart — the first is every
module's normal shape, the second means ids the module carries went unchecked, and only the second
warns. The narrow roster survives for a caller passing `variants=`, which is all rows-in-hand can
serve, and that caller is told so in `*_tables_not_read` rather than left indistinguishable from the
wide case.

**No schema change**: no column, no vocabulary member, no signature moves. `IdentifierReport` is a
report object rather than a published row, and the added fields default to empty, so an existing
caller reads unchanged.

## RM154 — an answered lookup whose alleles were rejected was published as an absence

**Severity** medium · **Status** ✅ shipped 2026-08-31 in the uncut 0.7.0 (`just-dna-format` +
`just-dna-compiler` + `just-dna-enricher`) · **Owner** enricher · **Motivating case** S85
(just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md)

A 64-variant longevity module authored from a paper whose supplementary is GRCh37/hg19 left five
subjects unresolved, each written into `resolution.csv` as `status: not_found`, `source: ensembl`.
Ensembl has all five and returns them immediately. What failed was allele matching: the paper spells
the submitted strand, so its `G/A` meets GRCh38's `C/T` and the allele-aware filter rejects every
locus, emptying `loci` and dropping the row through to the `not_found` arm.

**Two states of the world, byte-identical rows.** Reproduced offline against the real `enrich` path: a
snapshot that *has* the rsID with complemented alleles and one that genuinely lacks it produce the same
`(rsid, status, chrom, start)`. That is the collapse RM98 repaired one branch over — the reporter cited
its comments back at us — arriving from a third direction: `unreachable_rsids` means the request failed,
`unconsulted_rsids` that nobody looked, and this one that the asking **succeeded** and the answer did
not match. The consumer's own framing is the item: `not_found` sends an author to *does this rsID exist*,
a question with an obvious answer that is not the problem.

**Both obvious repairs are worse, and the second is worse in a way that had to be measured.** A new
`VALID_RESOLUTION_STATUS` member changes a wire vocabulary every reader of a published `resolution.csv`
shares — the reporter argued this themselves. *Deleting* the row looks more honest and is not:
`variant_key` and `rsid` are `RESOLUTION_FACT_FIELDS` while `status` is provenance and is not, so
removing the row **moves `resolution_signature`** and changing its status is free. Checked with the real
function rather than reasoned from the field list. The row was never the untruth — it is honestly
unresolved either way — so what moved is the reason, not the row.

**Shipped:** `EnrichmentResult.allele_mismatches`, carrying
`AlleleMismatch(rsid, genotype, loci, offered, strand_flip)` — the shape `ref_mismatches` and
`stale_rsids` already have, which is the option the reporter proposed. One aggregated run warning in both
modes, naming the rsIDs and saying the source *has* them, because an author who greps the artifact for
`not_found` is exactly who this exists to contradict.

**A second defect the report did not file, found in the sentence it quoted.** `hosting_verdict` returns
a confident `False` from two arms — a substitution/MNV locus (no flank, so no spelling freedom) and an
event length the locus does not offer — and the warning gave the second arm's reason for both. So a
strand-flipped SNV was reported as *"The event sizes differ, which re-anchoring cannot change"* about two
1 bp substitutions: a false claim, and the one that cost the run its largest diagnosis detour.
`contradiction_reason` is now `undecided_reason`'s twin on the `False` side (five causes there, two
here), walked by a test asserting the arms' reasons are pairwise distinct — the failure mode is a third
arm silently inheriting a second's sentence, which raises nothing and reads as a diagnosis.

`strand_flip_explains` and `reverse_complement` landed in **format**, not the enricher: they are pure
string work over the four bases with no reference access, the compiler's twin reporting site needs them,
and digest parity between the two resolution paths is a documented guarantee. `reverse_complement`
withholds on anything that is not four bases — a degenerate code states an uncertainty, and complementing
it would assert a base the source declined to name. `strand_flip_explains` tests `called <= locus` first,
because a palindromic SNV (`A/T` at `T>A`) satisfies both readings and would otherwise be reported as a
flip when it needed no explaining at all.

**No artifact changes**: no column, no vocabulary member, no signature moves, and every existing module
recompiles byte-identically. The `not_found` rows stay exactly where they were, which is what the
reporter concluded too — nothing in their data needed editing beyond the five genotypes' strand.

## RM108 — a re-curation is recognised, and currency is DERIVED rather than marked

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler` +
`just-dna-enricher`). **Severity** medium · **Owner** enricher, and the derivation landed in format ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `gene_validity.md`)

### The finding

`_merge_key` returns `("id", row.assertion_id)` when the source published one — the right rule in
general, and wrong here, because ClinGen's assertion id **embeds the curation timestamp**
(`CGGV:assertion_…-2019-08-18T160312.829Z`). A re-curated assertion arrives under a different id,
misses the merge key, and is appended beside the old one. `manifest.gene_validity.classifications`
then published a pair as far apart as `["definitive", "refuted"]`, with `classification_date` and
`dataset` the only discriminators and no consumer reading either.

### The decision that survived contact with the code, and the one that did not

**Survived:** the newest `classification_date` is current, and nothing is deleted. That is S45's
answer carried over to a weaker signal, and taking it means accepting one thing this format had not
accepted before — that a date is authoritative for currency. The concession is narrower than it looks.
The date decides *ordering* and nothing else: it never says a classification is right, both rows stay
in the file so the drift stays visible, and a consumer wanting the answer no longer has to reconstruct
one.

**Did not survive: the marker column.** The entry said the superseded marking "needs a column, which
is additive and minor-legal". Legal it is; workable it is not, and the reason only shows up when you
try to write it. **The row that must be marked is the one already in the file**, and merge-not-clobber
forbids this pass editing it (`@sidecar-authoritative`). So the marker would be correct on every run
*except the one that created the ambiguity* — the run that appends the new curation is exactly the run
that cannot go back and mark the old one. A boolean fails that way and a `superseded_by` pointer fails
that way too, plus three of its own: GenCC rows may carry no `assertion_id` to point at, a row
superseded twice needs a rule about immediate-versus-current successor, and a pointer *locates* rather
than asserts, which is the line `GENE_VALIDITY_FACT_FIELDS` already draws to keep `report_url` outside.

**So nothing is stored.** Currency is a total function of the rows present, so it is derived at every
read (`@derived-not-stored`): `classify_currency` in the format tier, called by the enricher to report
and by the compiler to warn and to build the manifest block. One consequence worth stating plainly —
**no column changed, so `gene_validity.signature` does not move and no existing module recompiles to
different bytes.** The reported harm was in the manifest, and the manifest is where it is fixed.

### The grouping, and its one difference from the merge key

`(gene, disease_id, moi, submitter)` — the source's grain **without `dataset`**. A re-curation is by
definition a later *release* of the same claim, so including `dataset` would put the two rows in
different groups and answer "nothing was superseded" every time. Computed **beside** `_merge_key` and
never inside it: the merge must keep both rows, because the drift staying visible is the property the
item exists to preserve.

### Two edges, and both withhold

Neither was in the original entry, and both are decisions rather than defaults:

* a **tie** on `classification_date` — two curations stamped the same instant, and nothing says which
  came second;
* **any row in the group carrying no date** — including the dated siblings, because being the newest
  of the rows that *stated* a date is not the same as being the newest.

In both cases no row is current and none superseded, and the manifest publishes every classification
in the group. Breaking a tie on `assertion_id` was rejected: an identifier carries no chronology, and
sorting on one manufactures a winner out of a spelling. A group of **one** is current, dated or not —
there is nothing to order it against, and that is what keeps the finding quiet on an ordinary module.

### Severity: a warning in both modes, in both tiers

The enricher **never raises**, in `best_effort` or `strict` — a curating body re-curating is the source
working, not the module being wrong. That is the pass's own argument for `missing` (*"`strict` is a
report, not a refusal to have looked"*) and the stronger form of it: the only edit available to an
author is deleting a row, which falsifies the record rather than repairing it. It is a deliberate
departure from `@enrichment-is-validation`'s mode ladder, and the second such check.

The compiler warns in both modes and never escalates, on the rule `_vrs_coverage_warnings` and
`frequencies`' `not_covered` already follow — **a finding no authored edit could clear is not a
`strict` matter** — and both codes are in `CARRIED_WARNING_CODES` for the same reason.
`validate_spec` reports the same two findings, since this is pure computation over injected bytes
(`@parity-by-check`).

### What the build turned up on the way

**The first fact-table check to run on both sides, so it was the first to double.** `compile_module`
runs `validate_spec` as its pre-flight, both reached the identical sentence, and
`manifest.compilation.warnings` carried it twice — which doubled `warnings_summary`'s count with it,
the case `@no-rerun-with-counts` is about. The fact-handler loop now dedupes on the message like every
other both-sides check (RM94's idiom); both passes read the same *post-overlay* rows, so the counts
agree and the rule is satisfied rather than dodged.

**`manifest.gene_validity.superseded_count` is new, and it is gated on the round trip.**
`gene_validity.csv` is rebuilt whole from its parquet — no row drops, unlike `literature.csv` — so the
row set is identical on lap 2 and the derivation over it is too. Asserted rather than assumed, because
a published field that differs between a module and its own round trip is precisely RM137.

**The merge test could not see this defect and is part of the fix, not the thing that confirms it.**
`test_a_rerun_merges_rather_than_duplicating` feeds the same bytes twice, and the same bytes carry the
same ids, so the key matches and nothing is appended however wrong the key is. The new fixture is two
*different* exports of one claim, which is what the real source produces.

## RM103 — the manifest now records the version that was READ, not only the one that was invented

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`; the
manifest half of the split item — the refusal half stays on the 1.0 tracker). **Severity** low-medium
· **Owner** format · **Motivating case** S42 (just-dna-lite, in CONSUMER_SUGGESTIONS_HISTORY.md)

### What shipped, and what deliberately did not

`Identity.version_coerced_from` — the authored `module.version` when the model rewrote it, `None`
when it was already canonical SemVer. `'v2'` beside `'2.0.0'`, `'abc'` beside `'0.0.0'`. Additive,
out of `artifact.digest`, declared in `RELEASE_RECORDS` on the `manifest_fields` axis.

**The coercion is untouched and must stay untouched.** RM17 decided coerce-rather-than-reject because
the pre-0.4 corpus is full of `v2` and `3`, and 0.6 widened it at `mode="before"` after **26 of 61**
foreign modules refused on an unquoted integer. Every digit-bearing case still behaves exactly as it
did, and the test parametrizes all of them precisely so a later change cannot quietly undo RM17 while
appearing to be about this item.

**A sentinel stays rejected.** Coercing to something unmistakable has no target: every three-number
string is a legal SemVer and therefore somebody's real release. Publishing what was *read* is the only
repair available, which is exactly why the additive half was worth separating from the refusal.

### The second-order effect that was nearly shipped, in the release that files RM137 about it

`reverse_module` takes `version` from its caller, and the caller has `manifest.identity.version` — the
**coerced** string. Re-emitting that leaves lap 2 with nothing to coerce, so `version_coerced_from`
comes back absent and a module disagrees with its own round trip on a published field. That is RM137's
exact shape, and it would have arrived in the same release.

So reverse re-emits the **pre-coercion** string: `_authored_version_from_artifact` reads the
artifact's own manifest, prefers `version_coerced_from`, falls back to `version`. Both cells then hold
across two laps, which the test asserts rather than assumes — and the failure was demonstrated on the
naive implementation before the test was called a regression net (`abc` → lap 1 `abc`, lap 2 `None`).

**It also repairs a quieter loss nobody had filed.** Reverse emitted no `version:` at all unless a
caller supplied one, so even an ordinary canonical version did not survive a round trip. Nothing
hashed on it — `module.version` is advisory and out of `artifact.digest` — which is why it went
unnoticed. An explicit argument still wins, and a bare parquet directory with no manifest still leaves
the key out: recover it or say nothing, never invent one, the same rule `genome_build` follows.

### What the reporter should do meanwhile, restated because it was already true

Both `compile` and `validate` have always warned, naming the authored string and the coerced result,
so a build that greps its warnings caught this before 0.7. The gap was between the *model* (silent)
and the *pipeline* (loud), and the reporter was testing the model directly. The manifest closes it for
a consumer holding only the artifact, which is the population that could not act at all.

**One correction to their report, in their favour**, kept from the original entry: they noted their own
CLAUDE.md claimed *"an unquoted `1` in YAML loads as an int and is rejected"* and is wrong on 0.6.1 —
`1` coerces to `1.0.0`. Confirmed, and our documents do not carry that claim. The hazard is the
unquoted *decimal*, still refused and deliberately so.

## RM110 — `constraint_flags` had two producers, two encodings, and one of them inside the fact set

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-enricher`).
**Severity** medium · **Owner** enricher, and it moved to format — see below · **Motivating case**
the 2026-08-19 doc audit (just-module-creator's `gene_metrics.md`)

### What was wrong, measured on the published snapshot rather than estimated

The live GraphQL route wrote `"|".join(sorted(flags)) if flags else None`. The snapshot route copied
gnomAD's bulk-TSV cell verbatim, and gnomAD writes a **JSON array literal** there. Re-probed against
`/data/.../gnomad_constraint/data/*.parquet` before any code was touched:

| cell | rows | what a consumer got |
|---|---|---|
| `[]` | 17,403 | `if row.constraint_flags:` → **true**, for an unflagged gene |
| a real array literal (`["outlier_mis","outlier_syn"]`, 14 distinct shapes) | 708 | splitting on `\|` → **one bogus token**, never two flags |
| null or empty | **0** | — |

So `if row.constraint_flags:` was true for **18,111 of 18,111 rows — 100%**, where the true flagged
fraction is **3.9%**. The field description (*"kept verbatim and pipe-joined"*) was false on the
snapshot leg in both directions, and `constraint_flags` is inside `GENE_METRICS_FACT_FIELDS`, so the
same gene fetched two ways minted two `gene_metrics.signature` values.

### The decision, and the one thing it changed on contact with the code

Pipe-joined when non-empty, `None` when empty, on both legs — never in doubt:
`enricher/tests/test_gnomad.py` had pinned `constraint_flags is None` on the live producer since 0.5,
so the contract existed, was tested, and the snapshot producer had simply never implemented it. **The
item was filed as needing a decision when what it needed was a release.**

What the entry did not anticipate is *where* the normalizer belongs. It said the normalization "goes
in the cell" rather than in a public accessor, and that argument, followed properly, puts it on the
**model** — `just_dna_format.gene_metrics.normalize_constraint_flags`, bound as a `mode="before"`
validator on the field. `mode="before"` because neither producer hands over the `str | None` the field
declares (a Python `list` from the API, an array literal from the TSV), and a `mode="after"` validator
cannot rescue a value the field's type rejects first (`@yaml-version-int`).

**Putting it in the fetching tier would have fixed the wrong half.** The published v4.1 snapshot is
immutable, and every `gene_metrics.csv` already written from it — including this repo's own
`reference_examples/hboc_palb2/` — carries `[]` on disk. A producer-side fix makes new tables agree
with each other and leaves those still contradicting the column's description and still hashing apart
from a live fetch. On the model, one function reaches every producer there will ever be, a
hand-written table, and a re-read of a file some earlier release wrote.

Three call sites nonetheless, and each earns its place: the live route (so the payload is normal
before it becomes a row), `gene_metrics.lookup_snapshot` (so the **published** snapshot reads
correctly — the leg that matters most), and `constraint_build._gene_record` (so a snapshot built from
here on is clean at source). All three are the same function, so they cannot drift; it is idempotent,
so a rebuilt snapshot passes through unchanged.

### What "empty → null" would have missed

Half the finding. It clears the 17,403 `[]` rows and leaves the 708 flagged ones still unparsed, so a
consumer splitting on `|` still gets one token. The non-empty cells needed **parsing**, which is why
the normalizer takes the cell apart instead of testing it against a null set. A bracketed string that
does not parse is kept verbatim — this normalizes an encoding it recognises and invents no reading for
one it does not, and a cell surviving unchanged stays visible to whoever reads the table.

### Cost, measured

Exactly one row in the corpus: `reference_examples/hboc_palb2/gene_metrics.csv` carried
`constraint_flags=[]`, so its `gene_metrics.signature` and `artifact.digest` move and nothing else in
the sixteen examples does. The checked-in file was corrected in the same commit, so it now holds what
the model stores. Beyond that it is whatever consumers have compiled from the snapshot, which nobody
has counted — which is the entire reason this is a minor with a CHANGELOG line rather than a patch.

### The test that would have caught it

`enricher/tests/test_constraint_flags_normalization.py`, and its shape is the durable part
(`@one-normalizer-two-spellings`): it runs **both producers' raw tokens** through the one function and
names the answer both must reach. A suite over the live leg alone was green throughout — that is
exactly what let this survive a release. The pre-fix behaviour was demonstrated before the tests were
called a regression net: an unflagged gene read as flagged, and a two-flag cell split to one token.

## RM147 — a source read by hand that yields no row had nowhere to go, and the home already existed

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`, documentation only — no
behaviour changed). **Severity** low-medium · **Owner** format · **Motivating case**
[S82](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The question

An agent read five literature services by hand — Crossref, Europe PMC, OpenAlex, PubMed, Unpaywall —
to find and confirm the papers behind two rows, and recorded that as five `licensing.csv` rows at
`layer=literature`. The reporter removed them, correctly, on our own two rules: a literature source's
terms are per **article** and live on `LiteratureRow` (RM46), and a pass that put no row in a table
records no source (S77/RM142). They measured that the rows bought no enforcement — identical verdicts
and warnings with and without them, since literature-layer rows are exempt from the orphan check.

Then they asked the real question: **after removal there is no trace anywhere** that a human went and
looked, and found the second paper the module's whole claim rests on. They offered three readings and
were attached to none.

### The answer: reading (2), and the home is already built

Their reading (2) was *"it belongs in `logs/`, and nothing writes it"*. Close, and the file is
`literature.csv` rather than a log. A row no study, bin or pharm row cites is **kept in the CSV and
dropped from the artifact** with `literature_row_uncited` — shipped since RM79 for the case of a
citation the author deleted, and the same shape answers the opposite case exactly: a paper that was
read and did not become a row.

That gives the consultation the three properties the report wanted and a log would not have. It is
**structured** — a `pmid`, a `doi`, an `exists` verdict, checked by the same pass that checks a cited
one. It **cannot make a licence claim**, which is what made the original rows wrong. And it is
**about the paper**, which is the thing that was actually consulted; a service is only how the author
reached it, and it is the paper that carries terms.

The compiler dropping the row from the artifact is right rather than a loss: nothing in the module
joins to it, and the CSV is where the author's own record lives.

### Documented rather than built, and that is the whole change

Nothing in the code moved. `LiteratureRow`'s docstring now says the uncited row is this case's home
and why the licensing table is not, and a test authors the reported shape end to end: two articles,
one cited and one not, a green `--strict` compile, `literature_row_uncited` naming the unused one, and
**no `licensing.csv` at all** — because nothing is owed for reading an abstract.

### The readings not taken

- **(1), "it should not be recorded."** Their straight application of S77, and the near miss. S77 is
  about *obligations*: a source that contributed nothing creates none. It is not a rule that the
  looking is uninteresting — and the looking is a fact about a paper, which this format already has a
  table for. Answering (1) would have made human search effort invisible by a rule that was never
  about visibility.
- **(3), a new `layer` member or a boolean meaning "consulted, contributed nothing".** The reporter
  was least confident in this and named the reason themselves: a row meaning *no obligation*, sitting
  in the obligations table, re-opens the check-that-cannot-fail shape S77 had just closed. Agreed, and
  it is worse than they said — `VALID_SOURCE_LAYERS` is a wire vocabulary, so the member would be
  permanent under P3 for a fact that has a home already.
- **Keeping the rows as they were.** Their own rejected candidate, and their argument is the one to
  keep: a `pubmed,literature` row with blank permission booleans sits one column from a false
  all-clear for text quoted out of a `cc by-nc-nd` paper.
- **A `logs/` writer.** Their (2) read literally. The transport exists, but a log line is unstructured,
  unchecked and unqueryable, and would have made us specify a line format that publishes. The typed
  row is strictly better and needed no new surface.

### Charter check

P3/P8/P9 — a docstring and a test; no field, no vocabulary member, no behaviour, and zero cost on the
authored layer. Measured: nothing in the corpus changes, so the 0.7.0 release record is unaffected.

## RM148 — `direction` and `stat_significance` are one pair, and the description did not say so

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`). **Severity** low-medium ·
**Owner** format · **Motivating case** [S83](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The measurement

Two runs of a byte-identical prompt, same model, same paper, authoring `rs117385980` for a longevity
module. Both green through every gate, and they wrote **different values in `direction`** for the same
variant on the same evidence: `risk`/`suggestive` against `unknown`/`not_significant`.

The evidence: two cohorts trending the same way, p ≈ 0.074 and 0.073, combined OR 3.58 with a 95% CI
of 0.96–13.4 — the interval contains 1 — at 28.4% power. Filed in the same spirit as S80, an hour
after that one was accepted.

### The answer: not a vocabulary gap, and the reason is the orthogonality itself

The reporter's reading (1), which they identified as the cheap one and which is also the correct one.
`direction` records the **sign of the reported estimate**; `stat_significance` records **how far to
lean on it**. They are orthogonal by design — the split RM145 just finished unwinding out of `state` —
and orthogonality is precisely the answer to *is a sign you cannot lean on still a sign*: yes, because
the other column is what says you cannot lean on it.

**The state they wanted a member for already exists as the pair.** `direction=risk` +
`stat_significance=not_significant` is exactly *a real trend the evidence does not establish*, and it
authors and validates today — asserted by a test that constructs their row rather than arguing about
it.

**Writing `unknown` there is the lossy choice**, which is the half the old description left an author
to work out. It discards the sign the paper reports and leaves `stat_significance` making a statement
about nothing. So the description now bounds `unknown`: *no sign to record* — not assessed, or the
sources conflict — **never a sign you may not act on**.

### Why no new member

Their reading (2) — a member meaning *looked, and the evidence does not establish a sign* — is the one
they could most easily imagine and did not push for. It would be a **second spelling of the pair**,
which is Principle 5's overloading arriving as a synonym rather than as a conflation: two ways to say
one thing, with consumers splitting on which they read. It is also a wire vocabulary change touching
every consumer, permanent under P3, for a state that is already expressible.

A test asserts the two vocabularies stay disjoint but for `unknown`, over the walked sets rather than
by naming members, so a future addition to either has to face this deliberately.

### What the fix is

One description string, the RM145 mechanism the reporter explicitly cites — it reaches `describe`,
`requirements`, `reference` and any consumer rendering `model_fields`, and it would have settled their
two runs. Their own interim repair (say which value you chose and why in `conclusion`) stays good
practice for a genuinely contested row; it is no longer the only thing standing between two agents and
a coin flip.

### Charter check

P3/P8 — a description string; no member added or removed, nothing invalidated. P5 — the fix *is* that
principle, stated where an author reads it. Measured: no reference example moves anything.

## RM144 — the licence-disagreement warning printed the remainder as though it were the whole set

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-compiler`). **Severity** medium ·
**Owner** compiler · **Motivating case** [S79](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The defect

`_check_declared_license_agrees` filtered the annotation-layer rows to those whose licence *differs*
from the module's declaration, then rendered that remainder as if it were the whole set. So a
two-source module declaring `CC-BY-NC-ND-4.0` — an exact match for one row, and the binding constraint
on the artifact — printed *declares 'CC-BY-NC-ND-4.0' but annotation-layer sources report
['CC-BY-4.0']*. The row that agrees is invisible in the sentence complaining about agreement.

Reproduced at the function, both ways: the matching-one case and the matching-none case produced
messages of the same shape, differing only in the length of a list. Nothing in the output told the two
apart.

**Two problems with different repairs read identically.** *Your declaration is unsupported* means the
author picked a licence no source grants. *Your declaration is not universal* is the ordinary shape of
a mixed-licence module, where the most restrictive term binds and the declaration is already right. An
author reading the first when the second was true re-adjudicated a module's whole licence position and
found nothing wrong — measured twice, in two separate reported rounds, and it survived RM142's fix
because removing the phantom `CC0-1.0` row leaves a real disagreement still rendered as total.

### What shipped

The reporter's option (1): the count leads and the agreeing rows are named beside the disagreeing ones.
*declares 'CC-BY-NC-ND-4.0' and 1 of 2 annotation-layer source(s) report a different licence:
['CC-BY-4.0']*, with a distinct sentence — *no annotation-layer source reports it* — for the case the
old message was actually written for. The tail names the mixed-licence reading explicitly, so an author
who sees a partial match knows it is a recognised shape rather than an unexplained complaint.

**The denominator counts rows, not distinct licences.** Two sources sharing a licence are two
obligations, and the number the author is checking against is how many sources they have; counting
distinct licences would report "1 of 2" for a three-row file, a number matching nothing in it. Rows with
no licence stay outside the denominator — unknown terms are neither agreement nor disagreement — and so
do non-`annotation` layers, or the count would disagree with the set the warning is about.

`declares license` still leads the sentence: it is the fragment an existing test keys on, and the
non-escalation is unchanged and re-pinned — two claims about a legal position disagreeing is not the
compiler's to arbitrate.

### Repairs rejected

- **Suppressing the warning when any row matches.** The reporter argued this against their own case and
  is right: a module declaring the *least* restrictive of several licences is exactly the one worth
  warning about.
- **Their (2), a bare count, and (3), changing only the verb.** Both remove the false reading and
  neither separates unsupported from not-universal, which is the distinction that cost the work. They
  offered these as cheaper floors; the full form is three lines of code, so the cheaper ones buy
  nothing.
- **An SPDX compatibility matrix.** Unchanged and not reopened: world-knowledge that goes stale, in the
  wrong tier.

### Charter check

P2/P3/P8 — pure text over already-loaded rows; no schema change, no field, no vocabulary member, and no
severity change. `@warning-text-is-api` is the live constraint and the grepped fragment is preserved.
Measured: no reference example moves a digest, signature or warning, so the 0.7.0 release record is
unaffected — the corpus has no mixed-licence module, which is why this survived it.

## RM145 — `state`'s six members were printed as peers, and two of them are retired in our own code

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`). **Severity** low-medium ·
**Owner** format · **Motivating case** [S80](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The defect, and how it was found

`VariantRow.state` was described as `One of: risk, protective, neutral, significant, alt, ref`. Six
values, no ordering, no standing. `derive.py` calls `alt`/`ref` **the retired descriptors** and maps
both to `direction=unknown`; nothing in the printed string carried that.

A consumer's authoring surface passes our descriptions through verbatim — deliberately, so a vocabulary
change reaches an author without them restating it and drifting — so an agent was offered six equal
choices and picked `alt` for a heterozygote, honestly. **The reporter had to read `derive.py` inside
their own `.venv` to author one cell**, which is the part they said they would fix first, and they are
right: that contract works only while the description carries what an author needs in order to choose.

Their usage measurement recomputed here: across the sixteen reference examples `state` is **377 `risk`
and 4 `neutral`**, with `significant`, `alt` and `ref` used **zero** times.

### What shipped, and why it is three groups rather than the two asked for

The description now reads: *Direction of effect for this genotype. Current: risk, protective, neutral.
Superseded, still valid and still read: `significant` — a significance claim rather than a direction,
write `stat_significance` instead; `alt`/`ref` — genotype descriptors carrying no direction, which
derive to `direction=unknown`.*

The report proposed *current | retired*, with `significant` among the retired. **That would tell an
author `significant` means nothing, when it means something this column is the wrong place for.**
`state` is the Principle 5 anti-pattern the charter names by hand — one field conflating statistical
significance, effect direction and a genotype descriptor — so the split has to be by *which axis a
value was really on*, and `derive.py` is the evidence: `alt`/`ref` map to `unknown` on both axes, while
`significant` maps to `significant` on the significance one and is refined from the weight sign before
falling back.

**Each group names its successor**, because a standing with no destination is a warning nobody can
clear — P3's own test for whether a deprecation belongs in a minor — and all three successors ship.

### Repairs rejected

- **Removing the three.** The reporter did not ask for it and it is major-only regardless: published
  modules carry these values and the read-time `effective_*` aliases derive from them. They cited S69's
  lesson about a deprecation claiming *nothing else is lost*, from the other side.
- **A `RECOMMENDED_STATES` frozenset beside the closed one.** Two lists to keep in step for a fact that
  fits in the string every surface already prints.
- **A compile warning on a superseded value.** Every such module would warn on every build for a value
  that still works and still derives correctly, and the author of a *published* module cannot clear it.
- **Fixing it in the consumer's `describe_table`.** Their own rulebook forbids it and they are right to
  — a restated vocabulary is one that drifts.

### Charter check

P3/P8 — a description string; no schema change, no vocabulary member added or removed, nothing
invalidated. P5 — the fix is that principle applied to the field the charter cites as its own example.
P9 — zero cost on the authored layer; the burden it removes is on the author. Measured: no reference
example moves anything, and none uses a superseded member — pinned by a test that recomputes it.

## RM143 — the enricher diagnosed a wrong-assembly coordinate and `compile --strict` built over it anyway

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-compiler`). **Severity** medium ·
**Owner** compiler · **Motivating case** [S78](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The measurement

A one-variant spec with a GRCh37 coordinate pasted into a GRCh38 module — the ordinary shape of a paper
stating its assembly once in the methods and nowhere near the table an author reads. `rs61849494` is
`10:51613269 G/A` on GRCh37 and `10:45982565 C/T` on GRCh38: 5.6 Mb apart and strand-flipped.

The reporter walked all four gates. `validate` passes, correctly — it is offline and cannot know.
`enrich(strict)` refuses, with a diagnosis they call better than anything they could have asked for.
`enrich(best_effort)` reports all three readings and writes the table, which is what best-effort means.
And `compile_module(strict=True)` **succeeds**, silently, over a module that is internally consistent
and about the wrong locus.

### Two of the three asks were already shipped, and saying so is half the answer

They offered three repairs in order of preference and asked for our view rather than guessing.

**Their (2) — have the compiler re-run the rsid↔coordinate agreement — is refutable on the data.**
`resolution.csv` does not hold both coordinates. For a coordinate-authored row the enricher records
what the author wrote, so there is one coordinate in the table and nothing to compare it against. The
change is not small, it is impossible without a fetch, and P2 forbids the fetch.

**Their (3) — make the compile warn — shipped in this same release and they could not have seen it.**
`verification_findings_recorded` (S70/RM130) reports every recorded finding at the author. It is absent
from 0.6.6, the version they measured. Reproduced: with the diagnosis in `verification.json`, a 0.7
compile prints *records 2 finding(s) across 2 check(s): genome_build_agreement (1 of 1),
reference_allele (1 of 1)*.

**Their (1) — record the diagnosis where the compiler can see it — is also mostly shipped**, and the
`verification.json` record is that place. What was missing is the last step: no severity attached to
it, so the fact was carried and never acted on.

### What shipped

`build_disagreement_error` refuses a `strict` compile when `verification.json` records a finding on
`genome_build_agreement`, in both `validate_spec` and `compile_module`, with the error equal on both
sides and placed ahead of `output_dir.mkdir()` so a refusal writes nothing.

**This does not move the strict line, and that distinction is the item.** `strict` means *reproducible*,
never *right* — the FAQ says so and it stands. `genome_build_agreement` is the exception on
**internal-consistency** grounds: a finding there says the module's rows are on a different assembly
than the `genome_build` it declares, which is one authored file contradicting another, not the module
disagreeing with an outside archive. Every other recorded finding keeps warning, pinned by a
parametrized test over four checks — including `reference_allele`, which *produces* this diagnosis's
input and still does not refuse on its own, because a ref mismatch has three causes and only one is an
assembly.

**The compiler adds no judgement.** It acts on a record the enricher wrote against a GRCh37 service the
compiler may never call. What changed is that the answer stops being discarded at the tier boundary.

Three things it must not do, each with its own test: **no attestation is silent** (an unverified module
is the ordinary case, and refusing on absent evidence reads unknown as wrong); **`findings=0` is a
clean bill**, so the gate keys on findings and not on the record's presence; and a **`skipped` record
is unknown**, which is what an `--offline` run writes — refusing there would make offline enrichment
poison a module.

### Repairs rejected

- **A column on `resolution.csv` marking the row as diagnosed** — their (1) read literally. It is a
  fact about a *check* in a table of facts about *variants*, the same axis that keeps `fetched_at` out
  of every fact set, and `verification.json` is the file that already exists for it. Also full cost
  under P9 for a fact with one reader.
- **Re-running the check in the compiler** — their (2), refuted above on the data.
- **Escalating every recorded finding under `strict`.** The obvious generalisation and the wrong one:
  it would fail a build over a ClinVar disagreement, which the cross-check deliberately refuses to do
  because the archive is the stale side often enough that the format would be arbitrating someone
  else's dispute.
- **Telling authors to always run strict enrichment.** Their own rejected candidate and correct:
  `best_effort` exists for good reasons, and a module authored under it stays wrong forever with every
  later gate green. The defect was the discarded diagnosis, not the chosen mode.

### Charter check

P2 — no fetch; the gate reads an injected sidecar. P3/P8 — no schema change, no field, no vocabulary
member; `BUILD_AGREEMENT_CHECK` names an existing one. P5 — severity and reporting stay separate axes:
the warning still fires in both modes and the refusal is the ladder's upper rung. Measured: no
reference example carries a `genome_build_agreement` finding, so nothing in the corpus changes and the
0.7.0 release record is unaffected.

## RM142 — the dosage pass declared a ClinGen obligation for a module ClinGen curates nothing of

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-enricher`). **Severity** medium ·
**Owner** enricher · **Motivating case** [S77](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### What was measured

A single-variant `SIRT6` module. The dosage pass reported, correctly, that it covered nothing —
`dosage: missing: [SIRT6]` — wrote no `gene_metrics.csv` row, and wrote a ClinGen licence row into
`licensing.csv` anyway. Reproduced exactly: `covered=[]`, `missing=['SIRT6']`, zero data rows,
`licensing.csv` present with one `clingen` row.

Two costs, and the reporter is right that the second is the expensive one:

- **A false statement in a published artifact.** `licensing.csv` travels to the registry and is read as
  *this module uses this source*. It is not true of a module ClinGen curates no gene of.
- **It fires `declared_license_disagrees` for nothing.** Reproduced: a module declaring `license: MIT`
  and using ClinGen for nothing warns *declares MIT but annotation-layer sources report CC0-1.0*, and
  an author then adjudicates a conflict that does not exist. Two agents were measured spending real
  effort on exactly that in an earlier round.

**The compiler cannot catch it**, which is what makes this the pass's job rather than a check. The
orphan warning `_source_checks` emits exempts the `annotation` layer deliberately (RM46), because
`sources.csv` is where an author is told to record a hand-read source and warning about that would make
compliance noisy while omission stayed silent. So an annotation-layer row nothing uses is silent by
design, and only the pass knows whether it contributed.

### The fix, which is what the siblings already do

`merge_sources_file` is now behind `if covered:`. That is not a new rule — it is the rule the rest of
the family already follows and this one member missed. `gene_metrics`, `frequencies`, `assertions` and
`gene_validity` all pass `{row.source for row in out}` to `record_source_terms`, so a pass that wrote
no row records no source. `clingen.py` alone built a fixed row and wrote it unconditionally.

**Checked rather than assumed, because the reporter asked us to check the others**: `enrich_gene_metrics`
and `enrich_frequencies` were run offline over a module they cover nothing of, and neither writes a
`licensing.csv` at all. The defect is `clingen.py`'s alone.

**`covered`, not `out`, and not `not missing`.** `out` carries rows a *previous* run merged in, whose
terms are already recorded, so keying on it would be keying on history. `not missing` is the dangerous
inversion — it would drop the declaration from every module carrying one uncurated gene beside a
curated one, which is a real obligation going unrecorded. Both directions have a test, and so does the
second lap, where `covered` is empty because the work is done and the row must stand.

`ClinGenResult.source_row` is still populated whatever happened: the terms of what was *consulted* are
a fact a caller may want to render, and they are a different fact from what the module uses.

### Repairs rejected

- **Having the author delete the row.** The reporter's own rejected candidate and correct: it is
  machine-written and returns on the next pass, and authors deleting licence rows by hand is a worse
  habit than the defect.
- **A `covered: false` marker on the row.** Their alternative suggestion. It makes `sources.csv` carry
  rows that are not declarations, so every consumer reading the table — the compile gate included —
  gains a case to handle for a fact that has no reader. Absence already says it.
- **Removing the `annotation` exemption from the compiler's orphan check.** It would catch this and
  reintroduce what RM46 removed: a warning at the author who followed the documented advice to declare
  a hand-read source. Compliance warning while omission stays quiet is the wrong direction, and the
  exemption's reasoning is unchanged.
- **Recording "we queried this source" somewhere.** The reporter floated a `logs/` entry. Nothing reads
  it, and a run's history is not what `licensing.csv` is for — the same axis that keeps `fetched_at` out
  of every fact set.

### Charter check

P2 — no new fetching; the pass consults exactly what it consulted. P3/P8 — no schema change, no field,
no vocabulary member; a `licensing.csv` that was being written is not written, which cannot invalidate
a module that never depended on it. Measured: no reference example changes — none carries a ClinGen
dosage row from an empty pass — so the published 0.7.0 release record is unaffected.

The direction is worth naming: this **removes** a declaration, and a licence table losing a row is the
dangerous direction in general. It is safe here only because the row's own predicate is now the thing
that decides — a module ClinGen fed keeps its row, checked by test in three arrangements.

## RM141 — `validate --strict` blessed a module `compile --strict` refused, whenever the resolution table was partial

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-compiler`). **Severity** medium ·
**Owner** compiler · **Motivating case** [S76](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### What was reported, and what reproduced

A consumer's `enrich` was killed by an external quota limit partway through a 263-subject module,
leaving a well-formed `resolution.csv` covering 201 of them. They reported two things: that nothing on
disk marks such a file partial, and — the part that made it urgent — that **merge-not-clobber turns it
into a silent wrong answer**, because the natural recovery of re-running merges onto the stale rows and
never retries the missing 62.

**The second half does not reproduce, and it does not reproduce on the version they ran either.**
Probed directly: a run over a table covering one of three subjects asks the source about exactly the
other two and commits all three. Measured on this tree and again on `v0.6.6` built from its own tag, so
this is not something 0.7 fixed underneath them. `enrich` gap-fills; the merge is over subjects the
table records, and a subject it does not record has nothing to merge onto. Their proposed repair (1),
writing the sidecar atomically, is also already shipped — `layout.atomic_writer`, from RM128 in this
same release, which is why the interrupted run left the *previous* table rather than a truncated one.

**And the reporter corrected their own account the same day, which sharpens what this closes.** From
the preserved artifact: the 203 rows are sorted throughout, the last line ends cleanly, and the 62
absent rsIDs scatter across the whole alphabetical range rather than forming a tail. So it is a
**complete write of an incomplete resolution set**, not a half-written file — which matches the code
rather than contradicting it, because a subject whose live request could not be made joins
`unreachable_rsids` and is written as **no row at all**, deliberately, so the table never states a
negative nobody established (`@unreachable-not-absent`). Nothing was interrupted mid-write, so RM128's
transaction and atomic writer would not have prevented it, and the same file comes out of a
`best_effort` run that completes normally over an unreachable source.

That re-attributes the closure to this item rather than to RM128, and by the right route: a check
reading the table against the spec beside it is the only thing that can see a set complete as a file and
incomplete as an answer, and it is indifferent to *why* a row is absent — which matters, because the
cause was misdescribed and the check does not depend on the cause.

**What is real is that nothing said so until the compile**, and that is a defect of ours.

### The defect

`compile --strict` refuses a module whose variants have no position after resolution — the check that
keeps a partial artifact from being published as a reproducible one. `validate --strict` did not
report it at all. So a spec whose table covers some of its variants passed the pre-flight clean and was
refused by the compile immediately after: the green-pre-flight-then-refusal shape the parity rule exists
to prevent, and the third time that rule has been broken in the same way.

It hid behind the rule's own exemption. What stays compile-only is *a check reading resolved rows*, and
coverage looks like one — but whether the injected table **can** place an authored row is arithmetic
over bytes the pre-flight has already loaded, and needs no resolution to have run. The exemption is
about resolved rows, not about the word "resolution".

### What shipped

`resolution.unresolved_subjects` is the predicate `resolve_from_table` applies, factored out and called
from both sides, so the two cannot drift into disagreeing about which rows are unplaceable — the
alternative was a second implementation of `_usable_loci`'s three exclusions (a `not_found` sentinel, a
row under another build, a row with no `chrom`). The pre-flight emits `rsid_unresolved` with the
sentence resolution already emits, and under `strict` appends the compile's error **verbatim**, which
the test asserts by equality rather than by both being non-empty: a pre-flight refusing in its own words
still sends the author hunting.

Two distinctions the fix had to keep, both the compile's own rather than new:

- **Nobody-asked is not asked-and-absent.** With a table present, an uncovered row is absent from
  something that was consulted and is named. With no table, nothing was consulted, and the pre-flight
  says so once instead of blaming a missing file once per variant. Both still refuse under `strict`.
- **`--no-resolve` means the same thing on both sides.** The master switch turns resolution off by
  request, and `resolution_disabled` already says that once with its row count; the coverage check
  stays silent there rather than restating it per row.

**A double-report was found and fixed while doing it.** `compile_module` runs the pre-flight in
best_effort whatever its own mode, so both passes reach this finding for the same subject; appending
blind published every one twice, measured at **24 warnings for 12 subjects** on a real example, with
`warnings_summary` counting 24. De-duplicated on the message, the `_check_contig_ploidy` idiom — safe
here because no message resolution re-derives embeds a count, which is the condition
`@no-rerun-with-counts` sets.

### Repairs rejected

- **A partial-file marker, sentinel, or row-count header on `resolution.csv`** — the reporter's
  framing. The file is a pure build product since RM124, and a marker in it would be a fact about a
  *run* living in a table of facts about *variants*, on the same axis `fetched_at` is kept off the fact
  set. It would also be unwritable by the case that needs it: a killed process writes no marker.
- **A `--rederive`-style completeness command** (their option 3). They offered to build it themselves
  and asked whether it is theirs; it is neither theirs nor a new surface — `compile` already answers it,
  and now so does `validate`, which is the command their authoring loop runs first.
- **Having `enrich` refuse to start on a short-looking sidecar.** Argued against by the reporter
  themselves and correct: a deliberately-resolved subset and an injected curated table are both
  supported practice, and nothing distinguishes either from a crash.
- **Recording the intended subject count in the run's output** (their option 2). `SubjectProgress`
  already carries `(done, total)` live, and a durable count of what a *killed* run meant to do is the
  marker above wearing a different hat.

### Charter check

P2 — pure computation over already-loaded bytes; nothing fetches, and the pre-flight gains no new input.
P3/P8 — no schema change, no new field, no vocabulary member: `rsid_unresolved` and
`resolution_not_injected` are existing codes and the strict error is the existing sentence. Measured:
no reference example moves its `artifact.digest`, `content_signature` or warnings, so the published
0.7.0 release record is unaffected — none of the sixteen has a partial table, which is why the defect
survived a corpus this size.

**One test was asserting the defect and was corrected**, not deleted:
`test_quoting_a_noncommercial_article_warns_and_never_gates` built a fixture with no `resolution.csv`
and asserted `validate --strict` reported valid. Its subject is that a licence finding never gates, and
the module was independently strict-refusable for an unrelated missing coordinate — so the fixture now
injects the table, and the assertion means what it says.

## RM140 — a study row's p-value and effect size are asserted to belong together, and nothing recorded what either came from

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`).
**Severity** medium · **Owner** format + compiler · **Motivating case**
[S75](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### What was measured, and by whom

A reproducibility benchmark the reporter ran: two agents, byte-identical prompts, the same three DOIs,
one module each. They overlapped on exactly one row — `rs117385980` from PMID 41249831 — and disagreed
on its `p_value`, 0.36 against 0.75, with an identical `effect_size` of 1.42.

Neither was a misreading. The paper reports **two analyses of the same association**: an allelic
Fisher's exact test giving `OR 1.4, p 0.36` on the 2×2 allele table, and a univariate logistic
regression giving `OR 1.42, 95% CI 0.18–11.67, p 0.75`, with five adjusted models after it. One run's
row was internally consistent. The other carried the logistic regression's `effect_size` beside the
Fisher test's `p_value` — one analysis's estimate and another's p-value on one row.

**Everything was green**, and this is the part that made it an item rather than an authoring mistake:
`validate_module(strict)`, `compile_module(strict)` and `audit_module` all passed, and `quotes_found`
was satisfied — the provenance quote is verbatim and correct, because it grounds the *significance
verdict* and contains no statistic at all. A quote cannot witness a number it does not contain, so
quote verification is structurally blind to this class of error.

`StudyRow` had `study_design` — *"e.g. meta-analysis, GWAS"* — which describes the **study**. Nothing
described the **analysis**. So a correct row and a mispaired one were byte-indistinguishable to every
consumer and every check, and no check could be written, because the facts it would compare were not
recorded anywhere.

### What shipped

**One optional free-form column, `StudyRow.statistical_test`**, shaped like `study_design` beside it:
which test or model produced this row's `p_value`/`effect_size`, and what it was adjusted for. Plain
`str | None`, no vocabulary marker, no `RECOMMENDED_*` set — the space is open and a recommended set is
additive later if a corpus ever shows a shape. Wired through all four touch points, with the round trip
watched failing on each of the last two in turn before the test was called done.

**And one behaviour change, which is what makes the column do something.**
`duplicate_study_citation` fires on a repeated `(variant_key, pmid)` because the check's own docstring
reads that pair as *the same claim written twice* — which two rows naming two analyses are not. Since
this item, **both stated and different** suppresses it. Nothing else does: an absent `statistical_test`
is *unknown*, and unknown against a stated value cannot establish that two rows describe separate work.
Kleene, not `a != b` — the naive form would suppress on every absent cell and silently retire the check
for every module written before the column existed.

**`StudyRow._KEY_FIELDS` is not widened**, which the reporter explicitly scoped out and which is also
the legal answer: that tuple drives `hints.key_fields` and the `key.columns` an authoring surface
publishes, and re-keying a shipped authored table changes what an identity key means — major-only under
P3. The check restates `(variant_key, pmid)` rather than reading `_KEY_FIELDS`, so the split is
contained in the one place that needed it.

### Repairs rejected

- **A validator requiring the pair to come from one analysis.** The reporter argued this against their
  own ask and is right: it cannot be written, because nothing on either side of the boundary knows what
  test a number came from until the column exists, and adding column and gate together would make every
  published row retroactively incomplete. **Column first, and possibly never a gate** — what a gate
  would need is a second recorded fact per number, not a stricter reading of one.
- **Widening `(variant_key, pmid)` to carry an analysis.** Above. Also unnecessary: both rows already
  reach `studies.parquet` today — the duplicate is a warning, never a drop — so the capability was
  present and only the *legibility* was missing.
- **A `RECOMMENDED_STATISTICAL_TESTS` vocabulary.** A recommended set is a claim about what the corpus
  contains, and one module is not a corpus. Open now, additive later.
- **A second warning code for the half-stated pair** — one row naming an analysis, the other blank.
  Considered and not taken: it is one more permanent key for a case that is a transient state of an
  author mid-adoption, and the existing message plus the rule stated in
  [COMPILER § the analysis grain](COMPILER.md#one-paper-several-analyses-and-the-dedup-key-rm140)
  covers it. File it if anyone actually reports being stuck there.
- **Editing a reference example to exercise the column.** It moves digests for no gain and manufactures
  the RM139 *one side only* case at the next cut. Test fixtures only.

### Charter check

P3 — a new optional column on an authored model: additive, minor-legal, and it lands inside the already
decided `0.7.0`. P8 — optional with respect to every published module, so nothing previously valid
becomes invalid; pinned by a test asserting two specs differing only in the *presence* of the column
hash to the same `content_signature`. P5 — `study_design` and `statistical_test` are separate axes, and
a future `analysis_covariates` sits beside this one rather than inside it. P7 — the round trip carries
the value and the digest is a fixed point. P9 — full cost, an authored column, and the answer is that
the rare author here is the one asking: an unset cell burdens nobody and the alternative is prose in a
README that no consumer can read.

### What it measured

`artifact.digest` moved on **10 of the 16** reference examples — exactly the ten carrying a
`studies.parquet` — and `content_signature` on **none** of the sixteen. The same shape RM91 measured
when it added `effect_allele`, for the same reason: a new column in a materialized table moves bytes
and no authored identity.

**The published `0.7.0` release record was re-measured rather than left standing.** RM126's record
carries measured counts, and this item landed after they were taken: the 0.6.6 → 0.7.0 sweep was re-run
end to end with 0.6.6 built from its own tag, and the two parquet axes went from `4/15` to `14/15`
while `content_signature` stayed `0/15`. `studies.parquet:statistical_test` is declared on both axes,
and the concordance-parquet declaration calling itself *the release's most visible consequence* was
corrected in place — it was a measured claim, and ten digests to four is no longer that. The gate
exits 0 against the amended record. A stale measured number reads as an all-clear, which is the failure
this repo keeps meeting from the other direction.

The suppression is a **loosening of a warning**, not of validity: no module that compiled stops
compiling, and no module that was silent starts warning. The message and code are byte-identical for
every case that still reports (`@warning-text-is-api`), pinned by its own test.

## RM139 — the release gate could not tell a broken compile from a spec that outgrew the old compiler

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`). Filed by
running RM126's gate for real at that cut, decided and built the day after.

**Severity** medium · **Status** ✅ shipped · **Owner** compiler · **Found by** the 0.7.0 cut

`gate_findings` failed a release when a module compiled on **one side only**, and its reasoning was
sound as far as it went: the likeliest operator error is running the sweep before `uv sync` propagated
the bump, and a module vanishing into an all-`False` result over its surviving neighbours is a false
green in the one mechanism the item rests on. But *one side only* was read as *a compile failed*, and
the very first real use of the gate hit the other cause. RM70 added the optional `requires_callable`
column to `pharm_variants.csv`, `reference_examples/cyp2c9_warfarin_grch37/` uses it, and 0.6.6
refuses that spec under `extra="forbid"`. Nothing failed: the previous release cannot produce a before
state for that module at all, so no like-for-like comparison exists and the sweep is right to say
nothing about it. The 0.7.0 record stated the exclusion in `evidence` prose the gate cannot read, and
the tag was waved through by a human — which is the state this entry ends.

**The decision, in two halves.**

*Which side, not whether.* The two directions are facts about **different releases**, and collapsing
them lost that. A module in the BEFORE tree and not the AFTER one is a regression **in the release
being gated** — it fails unconditionally, and now carries the compiler's own errors, which
`build_outputs` had been logging and discarding. A module in the AFTER tree and not the BEFORE one is
a fact about the *previous* release: whatever the cause, nothing in this release failed, and there is
no measurement to declare. A stale reused BEFORE directory holding a module the spec root no longer
has reads as the first, which is the fail-safe direction; the runbook already says fresh trees every
time.

*The exclusion moves into a field the gate reads.* `ReleaseRecord.unmeasured` names the modules the
previous release produced no output for, and the second direction fails until the published record
lists them. Old records read `[]`, which is the correct claim for them.

**Why that is not the per-module escape hatch this entry originally refused.** The refusal was right
about the shape it named — a field an operator can use to silence the gate is weaker exactly where the
docstring warns — and `unmeasured` is not that field, because the check is an **equality** over the
measured set rather than a membership test (`@registry-completeness`). It cannot cover a module the
sweep measured on both sides: listing one is reported as a note. It cannot cover a module this release
broke: that direction is fatal however it is listed, and `as_record` refuses to mint a record over
one. And a movement on a measured module still gates however the list reads. What is lost, precisely
and only, is that *the previous release could not compile module X* no longer blocks a tag — which is
right, because it is not a fact about the release being cut. What is gained is the forcing function:
`as_record` fills the field from the measurement, so the exclusion is committed to the published record
rather than remembered in a sentence nothing checks. That is the same mechanism `declared` already
uses, extended to the unmeasured set, not a second kind of gate input beside it.

The other three refusals in the original entry stand and were not revisited: the sweep still cannot
see the authored spec at the previous version, compiling the old spec from git would vary input *and*
compiler, and demoting the check to a note would re-open the false green RM126 exists to close.

**Measured, not asserted.** The 0.6.6 → 0.7.0 sweep was re-run end to end over all sixteen reference
examples with 0.6.6 installed in an isolated environment: fifteen measured, `cyp2c9_warfarin_grch37`
refused by 0.6.6 on `requires_callable]: Extra inputs are not permitted`, and the gate now exits 0
against the shipped record instead of needing a human to read past it. Removing a module from the spec
root exits 1 on the other direction, naming it.

**The prose-versus-field shape is the recurring one.** A count or an exclusion stated only in a
sentence goes blind — the triage threshold counter did it twice — so the field is pinned to the
sentence by a test rather than maintained beside it.

## RM126 — nothing tells a consumer what a release changed about compiled *output*

**SHIPPED in 0.7 on 2026-08-28 — `just_dna_format.release_records` (record, `needs_recompile`, roster), `just_dna_compiler.sweep` + `just-dna-compiler sweep` (instrument and gate), and `0.6.1`/`0.6.6` backfilled by measurement. See [SCHEMAS § The release record](SCHEMAS.md#the-release-record-07-rm126--what-a-release-changed-about-compiled-output) and [COMPILER § The release-record sweep](COMPILER.md#the-release-record-sweep-rm126).**

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output) on 2026-08-28 — BUILDS in 0.7, in full plus the S65 roster.** Record + `needs_recompile` in format, the sweep in the compiler, the gate in the bump→tag sequence; intervals compose as a union over `(a, b]`, which is what gives S65's convergence requirement for free.

**Severity** medium-high · **Status** ✅ **SHIPPED in 0.7** (2026-08-28) — the record, `needs_recompile`,
the roster, the sweep and the release gate. The charter *required* this channel: Principle 3 says a corrected derivation may ship in
any release but never silently, and this is the declaration it mandates. Until it exists the charter
describes a surface that is not there · **Owner** format (record + `needs_recompile`) + compiler
(the sweep) · **Motivating case** [S62](CONSUMER_SUGGESTIONS_HISTORY.md) (just-dna-registry)

A registry sweeping its catalog for artifacts that should be recompiled has two questions it can
answer and one it cannot. *Is the stored input still legal?* — re-run `validate_spec`, which answers
`ok`. *Was this compiled under a contract-incompatible compiler?* — compare versions, and a patch is
compatible. Neither is the question a changed derivation raises: **would recompiling this artifact
produce different output than the stored one?** Today the only way to answer it is to enrich into a
scratch directory, recompile and diff — which is the operation, not a triage for it.

**Reproduced here, and it is wider than the report.** All sixteen `reference_examples/` compiled under
`v0.6.1` (detached worktree) and under `0.6.6`, spec inputs byte-identical across the interval — the
whole of which is patch releases:

| | measured |
|---|---|
| changed at least one published manifest field | **16 / 16** |
| moved `artifact.digest` (and `artifact.files` with it) | **10 / 16** |
| moved `content_signature` | **0 / 16** |

`compilation.compiled_at` is a timestamp and is excluded as noise. The digest movement is not noise:
`studies.parquet` grew by exactly 257 bytes on each of the ten because **RM120 added the authored
column `curator`**, first present in `v0.6.5`. So the *parquet schema* moved across a patch interval,
which is the sharpest form of the finding and the one the reporter had not seen — they reported
changed manifest fields. `stats.genes`/`stats.gene_count` moved on **seven** (RM121) and
`literature.quotes_unchecked` appeared on three (RM119). **Six of the sixteen changed a published,
indexed manifest field with *both* hashes byte-identical** — `apoe_epsilon` went `genes: []` →
`["APOE"]` at the same `artifact.digest` and the same `content_signature`. That is the sharpest number
here and the one the surface has to answer to.

**Authored identity held throughout**, which is the charter working as designed: an unset optional
column is omitted from `content_signature`, so nothing a consumer keys on moved. That is exactly why
no existing surface can see this — a digest comparison, a signature comparison and a `revalidate` all
correctly report no change while an indexed field goes stale.

**The shape asked for** is a declaration keyed on the **interval** rather than on a version, because
the question is always *compiled under X, installed Y*, with the axes separated — parquet schema,
parquet bytes, `content_signature`, and the set of manifest fields. Deliberately **not** a
`should_rebuild` verdict: the same fact carries different costs per consumer (a stale cache is a free
rebuild for `just-dna-lite`; for a registry it mints an immutable PATCH and moves what a client
tracking `latest` receives), so the decision is the consumer's and only the fact is ours.

**Three things the design has to get right, and the third is why this is filed rather than shipped.**

- **Unknown must be a state, not an empty result.** Asked about an interval the installed package has
  no record of — an artifact compiled under something newer, or older than the table reaches — the
  answer is *cannot say*, never *nothing changed*. That is the house tri-state (`None` is never
  `False`), and without it the surface is worse than nothing, because a consumer would stop
  recompiling on the strength of a silence.
- **`content_signature` needs its own axis, separate from bytes.** For a registry a signature is a
  permanent global duplicate-content claim that only a purge frees, so *the identity moved in a patch*
  is an answer to fail loudly on rather than merely to act on. Our sweep says it has never happened;
  the axis exists so that stays checkable rather than remembered.
- **A hand-kept per-release map is the defect wearing a public name.** The reporter said so themselves,
  and it is `@registry-completeness` — five of the six RM104–RM111 fixes were a derived value restated
  by hand. So the map has to be a **measurement**: the sweep above is the guard's prototype, and it is
  cheap — check out the previous tag into a detached worktree, compile `reference_examples/`, diff the
  manifests, and fail when the declared hints disagree with what actually moved.

**The shape, decided 2026-08-21 in the S62 thread — two axes, and only one of them is measurable.**

- **`output_differs` — measured.** One record per release, produced by the sweep: parquet schema,
  parquet bytes, `content_signature`, and the set of changed manifest fields. Intervals compose as a
  **union over the releases in `(a, b]`**, so storage is linear rather than O(releases²) and
  *moved-and-moved-back still counts as moved*, which is the right reading for staleness. Backfillable
  for 0.6.1→0.6.6 by measurement with the harness that produced the numbers above; older intervals stay
  honestly `unknown`.
- **Correction versus addition — declared.** Only the person fixing the bug knows whether the stored
  value was **wrong** (`stats.genes`) or merely **absent** (`curator`), and no diff can tell them
  apart: both look like "a field changed". This is the canary — *not a minor, but rebuild time* — and
  it is the half the consumer cannot compute for themselves at any price.
- **The gate is what keeps the declaration honest.** A release whose sweep shows a changed field with
  no declaration covering it **fails**. That is what stops this becoming the hand-kept map everyone
  agrees it must not be: the measurement forces the declaration rather than the author remembering to
  write one. A release where nothing moved records a measured zero **with its evidence**, never
  silence (`@tautology-zero`).

**This does not contradict the reporter's "no `should_rebuild` verdict", and the item must say so.**
Their objection is to a *cost* verdict, because the cost differs per consumer. The correction flag is
not a cost judgement — it is a fact about whether a value we published was wrong, which is upstream
knowledge only this repo holds. The per-axis breakdown stays exposed underneath it, so a consumer who
wants the facts rather than the flag still has them. A bare boolean with nothing under it would deserve
their objection exactly.

**Tiers.** The record, its model and a pure `needs_recompile(compiled_under, current)` belong in
`just-dna-format` — a static table plus a function, which pydantic-only holds comfortably, and format
is the tier every consumer has. The **sweep instrument** belongs in the compiler, since producing a
record means compiling. The **gate** runs in the bump → `uv sync` → tag sequence rather than as an
ordinary test, because it needs the previous release actually installed. Keyed on `compiler_version`,
which is what `manifest.compilation` already stamps and what a consumer holds. **Scope v1 to
compiler-derived outputs and say so** — enricher-side outputs stay unmeasured rather than unchanged.

**Open, because the representation is not obvious.** An interval table is O(releases²) unless it is
composed from per-release records, and composing them means deciding whether the axes are unions
(a field that moved and moved back still moved) — probably yes, but that is a decision. The tier is
open too: the natural caller is a consumer of `just-dna-compiler`, and the hints describe compiler
behaviour, but a verify-only consumer holding `just-dna-format` alone has the same question about a
manifest it can read. **[RM127](ROADMAP_HISTORY.md#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one)
is why this is needed rather than a nicety**, and it is now **closed**: a corrected derivation is a bug
fix, deferring it to a minor means serving a wrong value meanwhile, so the release number cannot carry
staleness and a second channel is the only resolution left. The charter amendment of 2026-08-21 made
that a rule, which is what turns this item from a nicety into a debt.

### Four constraints handed back by the consumer who built the other half (S65, 2026-08-21)

just-dna-registry shipped the recomputation side as `services/rebuild.py` in their 0.21.0 and reported
what building it taught them. Each of these narrows the design and none was visible from here.

- **Convergence is a hard requirement, and the obvious shape fails it.** If a hint fires for a version
  compiled by the *exact* compiler now installed, recompiling derives the same value again — so an
  automated sweep mints a fresh PATCH every run, forever. That is the *a patch is not a gap* rule
  re-entering by a different door. **The interval-keyed shape gets this for free, because the interval
  from a version to itself is empty** — so state that as load-bearing rather than incidental, since a
  field-keyed or "latest known defect" shape would not have the property. It is also what bounds a
  false positive to one wasted version number per module ever, which is what made them willing to act
  unattended at all.
- **Recomputability splits the problem in half, and the better half already shipped.** For a manifest
  field that is a pure function of the authored rows, a consumer can recompute the *current* answer
  from stored inputs — no enrichment, no parquet, no network — using `spec_tables` (RM116) for the
  defaults-folded rows and `module_stats` (RM121) for the derivation. Neither landed for this reason.
  **So what would help most is not a bigger table but a small published roster: which manifest fields
  are pure functions of the authored rows.** That is a fact we hold and they guess at, and it *shrinks*
  this item rather than growing it. The interval-keyed table then only has to cover what a consumer
  cannot recompute — `literature.quotes_unchecked` (RM119) is their worked example, since it derives
  from a sidecar rather than from authored rows.
- **The roster's boundary is conditional, and the condition is invisible from outside.** `validate_spec`
  computes `stats` over the full row set; `compile_module` re-derives over the survivors **only when
  the symbolic-allele drop removed something**. So a recomputation from authored rows is the *pre-drop*
  side, and `manifest.stats` legitimately disagrees with it — permanently, under any compiler — for a
  module that lost the sole row naming a gene. A roster stating "pure function of the authored rows"
  without that condition would send consumers to spend version numbers on modules that are current.
- **`compilation.dropped_rows` closes the residue, and shipped 2026-08-24.** Their guard discriminates
  on `variant_count`, which catches a drop from `variants.csv`; a drop inside a *kind* table moved no
  published counter at all. With the counter, the `stats` half of the roster is unconditionally
  checkable. They rejected reading the warning text for the reason our own catalogue rule gives.

**Scope it for coexistence rather than replacement, at the reporter's request.** Their probes sit
behind one named seam so a probe this covers retires by deletion, and they may keep one or two anyway
— a recomputation checks the artifact actually in front of them, a hint states what a release did in
general, and the two fail differently. **The useful division: we state what a release did, they check
what a specific stored artifact says.** And they are not re-asking for `should_rebuild`; building the
decision themselves is what surfaced all four constraints above.

---

## RM134 — PubMind as a literature-derived annotation authority, and a ClinVar concordance check

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm134--pubmind-as-a-literature-derived-annotation-authority-and-a-clinvar-concordance-check) on 2026-08-28 — BUILDS in 0.7, pulled in after the other eleven were decided and reviewed against them.** Eight corrections, two of which were defects that would have shipped: **the concordance record is shared with RM130 and RM130's shape changes because of it** (`ClinSigConflict` names its authority in a *field*, so a second authority would have cost a key change or a retype — major-only); and **one normalizer, not two, after two fixes** — `_normalize_clin_sig`'s map keys are underscored while PubMind's tokens are spaced, so `Uncertain significance` and `Conflicting` both fall to `other` today and the check would manufacture a disagreement on PubMind's largest disagreeing class. **A maintainer stress test at five authorities failed the drafted vocabulary**: `pubmind_only`/`clinvar_only` name the authority inside the member, because one field carried two axes. Split into `authority_concordance` and `authored_position`, five members each at any N. **Nothing resolves a split** — E+A agreeing against B/C/D needs a weighting model this repo has refused to invent three times — so the precedence list is recorded as methodology and computed with by nothing. Licensing governs what a module may *do* with the values, not whether the machinery exists: unknown terms warn and never gate, and publishing such a module is RM27's axis.

**Severity** low-medium · **Status** ✅ **SHIPPED in 0.7** — all four sections (§ A the snapshot and
the shared normalizer, § B the N-authority check, § C `draft-panel --source pubmind`, § D the hint)
· **Owner** enricher · **Motivating case** the PubMind paper
(doi:10.1038/s41467-026-76834-4, 20 August 2026), and a user direction on 2026-08-28 to design both a
ClinVar-shaped derived table and a ClinVar concordance check · **Full design**
[PUBMIND_ASSESSMENT.md](PUBMIND_ASSESSMENT.md)

PubMind extracts variant–disease–pathogenicity associations from 41.7 M PubMed abstracts and 5.4 M PMC
full texts with LLaMA-3.3-70B behind a fine-tuned BERT triage stage. It is **a source, not a
competitor**: its own discussion calls it *"a literature-grounded complement to human curated
databases"*, and the description holds one layer further down — it produces assertions and stops
exactly where we start, at identity, integrity, licensing and the round trip. The only contested
surface is its pitch to institutions wanting their own interpretation database, which is our module
author's use case; what it hands them is a SQLite file behind a Flask app.

**What is reachable, measured against the bytes rather than the paper.** The web API takes `gene`,
MONDO and PMID/PMCID only — an rsID query is refused — and returns aggregate counts, never a record,
which the response says outright. So the single per-variant channel is the coordinate table ANNOVAR
redistributes as `hg38_pubmind_db` (2026-08-24, 6.5 MB gzipped, 909,224 rows: `PVID`,
`pathogenicity_sum`, `paper_level_pathogenicity_score`, `confidence` 0–3). Its coordinates are
**VCF-style despite the ANNOVAR packaging** — no `-` alleles anywhere, deletions carry the anchor base
— so it joins our `chrom`/`start`/`ref`/`alts` with no translation. Whether the indels are
left-normalized is not established.

**It is much smaller than 909,224.** 439,388 rows (48 %) are **enumerated codon alternatives, not
observed variants**: where only a protein change was recovered from text, every codon encoding that
amino acid is written out, and 439,383 of those triplets need two or three simultaneous base changes
to reach the reported protein — which is a statement about the protein, not a position anyone can
genotype.
Decomposing the single-base codons leaves **342,209 distinct `chrom:start:ref:alt` keys over 305,935
loci** as the honest joinable layer. 523 rows have `Ref == Alt`.

**Consolidation is on extracted text, never on a coordinate**, so PubMind has record identity where we
have variant identity: 68,744 coordinate keys (8.4 %) carry more than one PVID, worst case 35. At
chr6:26092913 G>A (HFE C282Y) eight PVIDs disagree four ways, and one of them — `PVID926871`, verdict
**Benign** — pairs `rs1800562` with gene *TMPRSS6*, a chromosome 22 gene on a chromosome 6 variant.
`_gene_locus_conflicts` catches that shape today (`@gene-locus-relationship`).

**Worth on our own corpus**: 173 of 423 GRCh38 `reference_examples` loci matched (40.9 %), 190 of 589
authored ALTs exactly (32.3 %), and where both sides state a verdict they agree on 83 of 134 (62 %),
every disagreement running our-pathogenic vs their-uncertain-or-benign. That profile — real breadth,
low confidence — is a **cross-check source, not a fact source**.

**The design, directed 2026-08-28, is four sections.** An earlier draft of this entry stopped at a
report-only check and recorded the rest as blocked; that framing is overtaken, and the licence
constraint moves from *reason not to design* to *precondition on shipping*.

**A. `pubmind build` / `pubmind publish`**, a sub-app beside `clinvar`, mirroring `clinvar_build.py`:
polars builder, fixed column order for a byte-identical rebuild (P7), one parquet plus `release.json`
through `locations`. Schema follows `_empty_schema()`'s split, except **no column is a resolver link** —
"authority" here means an authoritative *annotation* source the way ClinVar is one, never
`resolution.csv`'s `authority` (`@source-vs-authority`), because PubMind's coordinates are PyEnsembl
back-mappings of extracted text. `pathogenicity_sum` maps into `VALID_CLIN_SIG` with the composite kept
verbatim in `pubmind_sig_raw`, the `clin_sig_raw` precedent. Every normalization drop is **counted into
`release.json`** rather than silently applied (`@dont-discard-computed`): 160,090 codon rows decomposed,
439,388 enumerations and 523 `Ref == Alt` rows dropped, 20,131 indels kept but stamped, and PVID
fan-out kept as separate rows because collapsing it would pick a winner by an ordering nobody defined.
**`publish` refuses**, on the PharmVar precedent (`@gated-source-caches`) — a bulk file under terms we
cannot establish is not one we may pass on, and the command exists and refuses rather than being
absent, which would read as an oversight somebody helpfully fixes.

**B. A three-way check, module ↔ ClinVar ↔ PubMind**, beside the existing ClinVar `clin_sig` check
rather than replacing it. Seven outcomes — `concordant`, `authored_dissents`, **`authorities_differ`**
(the case nothing today can report), `pubmind_only`, `clinvar_only`, `neither`, `unchecked` — combined
under Kleene, with unknown withheld and never negated. `ClinSigConflict.opposed` already draws the
severity line (opposed vs merely different) and is reused rather than re-invented. Warning-tier in both
modes, never escalating (`@clinsig-never-escalates`), and `authorities_differ` is not a module defect at
all. Corpus-wide concordance is stamped into `release.json` **at build time only** — our own
reproduction of their 10.6 % / >80 % claims against our denominator — because a message embedding a
count that runs twice publishes two numbers (`@no-rerun-with-counts`).

**C. Drafting**, through `--source pubmind` on the existing `draft-panel` rather than a new command,
since it writes the same tables from the same gene argument and a twin would duplicate the genotype
worklist, placeholder guard and dedup pass. `--min-confidence` is the `min_review_stars` analogue;
identity is coordinate-whole or nothing (`@identity-whole-or-none`), most PubMind rows carrying no
rsID. **The self-agreement trap has an existing answer**: a module drafted from PubMind and then checked
against PubMind agrees with itself, so `pubmind` joins `DRAFT_PROJECTIONS` projected onto `clin_sig`
(`@draft-digest`) — raw CSV cells at draft time, and the skip a conjunction of release **and** digest.
The ClinVar half of B is unaffected, which is why the three-way shape earns its keep.

**D. The hint surface**, unchanged and cheapest: surface verdict, confidence, paper count and PMIDs
beside the cell, and never pre-fill `clin_sig` (`@hint-redundancy-bearing`) — the same defect
`@draft-digest` solves one layer down, without a digest to rescue it.

**The gate is one unanswered question, and asking is the unblock action.** A and D are buildable now;
B and C acquire and carry values. The ANNOVAR-distributed table publishes **no data terms** —
`LICENSE.md` covers the software (academic, non-commercial), the paper is CC BY-NC-ND, the table itself
says nothing, and unknown is not permissive (`@no-named-licence`). Ask WGLab and CHOP's Office of
Technology Transfer in writing; it will not resolve itself by the file continuing to download without
a key. Separately, RM27 still owes the redistribution axis (`@redistribution-ungated`) — a gate on
*publishing a module that carries such bytes*, not on building the snapshot or running the check
locally, and conflating the two is what stalled this area in the first draft.

## RM133 — a card subtitle has no amendable home, and the binding is not where that gets fixed

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm133--a-card-subtitle-has-no-amendable-home) on 2026-08-28 — BUILDS in 0.7, on the authored layer at zero cost.** `short_description` joins the registry-owned family as a **separate** frozenset beside `IDENTITY_AUTHORITY_KEYS`, stripped by the same function, so the stored bytes are untouched and the closure stands; the ~120-character calibration ships as a constant rather than being guessed at downstream.

**Severity** low-medium · **Status** ✅ **SHIPPED in 0.7** (2026-08-28) — the binding question it
arrived with is **answered and closed** · **Owner** format (+ registry, for the half that is theirs) ·
**Motivating case** S64 (just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md

Measured by the reporter: editing `module.description` from 44 words to 11 moves **no**
`content_signature`, **no** `artifact.digest`, **no** fact signature — and drops the closure, because
`manifest.inputs` covers the raw bytes of `module_spec.yaml`. `README.md`, by a wide margin the longer
prose, is outside `inputs` and freely amendable. The shortest fixable prose in the system was the one
that could not be fixed.

**The binding stays as it is, and the reason is the partition, not the cost.** The ask was to split it
along the line `content_signature` already draws. That line is stated in `integrity.py` and excludes
**name, version and namespace** alongside title and colour — so a binding drawn there makes a closure
**transferable across a rename**: a module closed and signed by a named reviewer keeps its attestation
after its identity is changed. `content_signature` excludes those *so a registry strip does not move
content identity*, which is right for a content-dedup key and exactly wrong for an attestation. The two
hashes cannot share a partition because they answer opposite questions about the same fields. **Do not
re-propose this.**

The reporter's narrower six-field version (`title`/`description`/`report_title`/`icon`/`icon_set`/
`color`) does **not** carry that attack and is recorded as the better form of the idea. It inherits the
cost they named themselves — hashing a *parse* of the yaml, and so every canonicalization question
`content_signature` answers, with two hashes able to disagree about what counts as display. RM82 is the
precedent that prices it: the last change to the binding turned on being *a byte transform needing no
loader, no parse and no schema knowledge*, and refused BOM/whitespace/final-newline because each
*"makes the binding more content-ish without making it content"*. A field-aware split crosses that line
on purpose.

**What the binding buys, since the reporter asked and could not construct it:** it is the *reviewer's*
claim rather than the artifact's. The other two hashes answer *is this the same data* and *are these
the same bytes*; this one answers *is this the same document a named person signed off*. A card
subtitle is a claim about what the rows mean, so excluding it would make the attestation cover less
than the reviewer actually read.

**The route that actually unblocks it, and it is the item.** The framing *"the binding overrides the
registry's rule from a layer below"* assumes an amend must **rewrite the stored `module_spec.yaml`**.
It need not: `normalize.IDENTITY_AUTHORITY_KEYS` (`namespace`, `owner`, `canonical_id`) is the standing
precedent for **registry-owned** metadata that sits beside the module rather than inside it, with
`strip_authority_keys` handing the spec to our validator without them. A registry-owned display
override leaves the stored bytes untouched, so `manifest.inputs` still matches, `verify_manifest` still
passes and the closure stands. **So the registry's `amend_display` is not gated on this item** — it is
gated on whether the amended value is registry-owned or a spec rewrite.

**What is left to design: where a bounded `short_description` lives so that it lands amendable.** Not
on `ModuleInfo` — under the answer above every field in `module_spec.yaml` is on the un-amendable side,
so putting it there reproduces the defect in a new place, which is the reporter's own objection and it
is correct. Their argument for why a `max_length` is legitimate on a **new** field where it is not on
`description` holds and is why this is a real item: a field that exists to fit a fixed layout is
*specified* by that layout, it refuses nothing anyone has written, and absent it everything behaves as
today. Calibration from the live catalog: ~**120 characters**, against a measured 71 (comfortable) and
467 (the case that prompted it).

**Not in scope**: render-time truncation or folding, which hides prose an author chose to write and
leaves the spec as wrong; and anything retroactive to the seven published modules, which met every
requirement that existed.

## RM71 — the alleles a drafted `genotype` stub must be written from are in no file

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm71--the-alleles-a-drafted-genotype-stub-must-be-written-from-are-in-no-file) on 2026-08-28 — BUILDS in 0.7, and no schema moves.** The answer to *where does an author do this work* is **in the command they already ran**: the worklist covers every stubbed row in the file rather than only this run's additions, and `draft-panel` gains the `--dry-run` that `draft` has. The bulk advisory command is rejected for putting the worklist in a third place.

**Severity** medium · **Status** ✅ **SHIPPED in 0.7** (2026-08-28) — the worklist now covers every
stubbed row in the file, and the `--dry-run` the decision asked for turned out to have shipped in
0.5.1 already, so what landed is the test that pins it · **Owner** enricher (`clinvar_draft`) ·
**Found by** dogfooding on 2026-08-13, `reference_examples/hboc_palb2/`

### What was observed

`draft-panel` drafts `variants.csv` rows from ClinVar and leaves `genotype` as
`vocab.TEMPLATE_PLACEHOLDER`, correctly: ClinVar publishes **alleles, not genotypes**, and whether
carrying a pathogenic allele once is informative is inheritance-mode interpretation the source does not
state. The mechanism under it is `draft.PartialRow` — the row is validated by **omission** and matched
on `match_on` (the identity columns) rather than the natural key, because the natural key runs *through*
the stub, which is what makes a re-draft after the human fills the genotype report `already_present`
instead of appending a second stub. None of that is in question.

What is missing is that the alleles the author must write the genotype *from* are in no file. A drafted
row is rsID-only — identity whole or not at all — so `rs118203998` arrives with empty `ref`/`alts`, and
the pair is stated once, in the warning stream:

```
warning:   genotype for rs118203998: ClinVar publishes G>T — an allele pair from {G, T}
```

The author's next action is an edit to a file that does not contain the information. At the 16 rows
PALB2 yields at ClinVar's 3-star floor this is a transcription exercise; at the **761** the same command
drafts for PALB2 at the 2-star floor it is not one.

**And it is emitted exactly once.** The worklist is built inside `if report.added:` and scoped to
`added_records`, which is itself a correct earlier repair — it used to name rows the model had refused
and rows already in the file, so a "3 row(s) carry a placeholder" header was followed by twenty-seven
lines. The consequence is that re-running `draft-panel` after the first draft adds nothing and therefore
prints **no worklist at all**, and `draft-panel` has no `--dry-run` (`draft` does). The information
cannot be re-requested from the command that produced it.

### Candidate repairs, and why each is wrong

- **Write `ref`/`alts` into the drafted row.** The one the ledger already names. A drafting provider
  fills identity whole or not at all, and the model forbids `ref`/`alts` without a coordinate — so this
  means writing the full coordinate, which discards the rsID identity the provider deliberately chose as
  the stabler and more legible one. `alts` is also `REDUNDANCY_BEARING`: the compiler's allele-membership
  check compares the author's genotype against it, and that check keeps its force *because* the two were
  authored independently. Filling it makes the compiler compare ClinVar with ClinVar.
- **A comment column on `VariantRow`.** `extra="forbid"` rejects any column the model does not declare,
  so a "comment" is a real optional field — full cost on the most expensive table, carrying text that is
  dead the moment the stub is replaced. It
  is also a provenance claim with no machine reader: "ClinVar publishes G>T" is a statement about a
  snapshot release, and a re-draft from a newer one leaves it naming the old alleles. That is exactly
  the staleness `licensing.withdraw_stale_dataset` had to be built for on `dataset`, on a column where
  nothing could notice.
- **A sidecar the author reads beside the CSV.** Half cost, so the cheapest legal candidate, and still
  wrong three ways. Its only reader is a human, which is the one thing the charter amendment says to
  discourage rather than leave unmentioned. Its join key is the key the stub runs through, so it either
  keys on the rsID — saying nothing a `hint variant` call does not — or on the natural key, which
  contains the placeholder. And an unknown file in a spec directory is tolerated but not read, hashed or
  listed in `artifact.files` (S16), so a worklist file the author must remember to delete becomes a
  permanent resident of every drafted module, with one more name for `_check_misspelled_tables` to
  learn.
- **Have the enricher fill it after resolution.** `enrich` resolves the alleles, so it *could*. It must
  not, twice: `ref` and `alts` are both in `hints.REDUNDANCY_BEARING` (`ref` against
  `verify_reference_alleles`, `alts` against the allele-membership check), and filling a cell a Class-2
  check cross-examines makes the comparison vacuous. And the dependency runs the other way — `enrich`
  refuses to load a file containing a placeholder, correctly, because forward resolution is allele-aware
  (`hosting_verdict`) and a placeholder genotype would silently skip that filter on exactly the
  one-to-many rsIDs that need it. Rewriting the authored cell at all is the parked enricher-co-authoring
  item, which nothing here should ship by accident.
- **Make `genotype` optional so the stub is unnecessary.** Barred by Principle 8 — it is a required
  field, and demoting one within a major is the forbidden move. It would be wrong at 1.0 too: the
  zygosity decision is what the stub protects, and an optional genotype lets a module ship without it
  silently, which is the reassurance-manufacturing failure this format guards hardest against.

### What is actually undecided

`just-dna-enricher hint variant rs118203998` already returns the alleles and already refuses to apply
them (`refusal="redundancy_bearing"`), so the information is reachable at one command per row. The
candidate that survives every objection above is therefore a **bulk read-only advisory** over a module's
stubbed rows: it changes no schema, fills no cell, and re-answers a question the drafting run answered
once. That is a build rather than a decision — but it is not obviously the answer either, because it
puts the worklist in a *third* place while the author's complaint is that it is not in the one place
they are editing.

So the open question is not "which column" but **where an author does this work**, and this repo has no
model of that. Filed here rather than built for exactly that reason.

## RM85 — a recorded release, compared against the one its source publishes now

**Shipped in `just-dna-enricher` (plus a `just-dna-format` vocabulary member) on 2026-08-29.** The
enricher check `PROPOSAL_0_7` decided: `currency.check_dataset_currency`, run at the end of `enrich()`
and attested as `dataset_currency`, with `--verify-datasets/--no-verify-datasets` as its switch.

**Severity** low-medium · **Status** ✅ shipped in 0.7 · **Owner** enricher ·
**Motivating case** a source-drafted panel two ClinVar releases later

### What it does

`SourceRow.dataset` had recorded which release a module's rows came from since RM4, and two things read
it — the tautology skip, and `withdraw_stale_dataset` when a module ends up mixing two. Neither answered
*"ClinVar has published since you drafted this"*. The check reads `sources.csv`, asks each source which
release it publishes now, and reports the gap. It writes nothing: repairing a stale label is a re-draft,
which is an author's decision and a different command.

It is `--rederive`'s cheap neighbour, and ENRICHER § `rederive` now says so where an author reads it.
Both ask *has the world moved* — one about the rows, one about the release **label** — and the label
question costs one request per source, so it is what tells an author whether the expensive one is worth
running.

### The three things the entry did not settle, decided in the build

- **Which source can actually be asked.** The entry said "the source's current release" as though every
  source publishes one in a form we record. They do not: `dataset` labels are minted by whichever pass
  wrote the row, and only ClinVar's has a live counterpart this tier can read in the same namespace
  (`clinvar_<##fileDate>`, through the reader `clinvar_build` already uses). So **one probe ships**, in
  a registry (`PROBE_SOURCES`, derived from `default_probes` rather than restated beside it), and every
  other source reports `unsupported` — an honest *this tier cannot ask*, never a clean bill. Widening it
  is adding a member.
- **Comparability is a third state, beside the tri-state the entry did name.** `clinvar_dataset_label`
  has a digest form for a snapshot built from a VCF whose header stated no date. A digest against a
  stated date names one release space in two spellings and equality across them means nothing, so it is
  *uncomparable* (`no_reference`), not *behind*. Reporting it as behind would send an author to
  re-draft a module that may already be current.
- **`strict` refuses over `behind` alone.** Severity follows the mode, as the decision says — but an
  unreachable source and an `--offline` run both leave every leg unchecked, and escalating those would
  make `--offline --strict` impossible forever over something no author can edit. That is the
  `unreachable_rsids` rule (warned in both modes, escalated in neither), and the gate is written over
  the superseded set so the two cannot be confused.

### What the shape had to avoid

**A check must not be able to agree with itself.** Wave 2 had just found a `--rederive` path seeded from
its own staged answers, reporting a clean bill for exactly the subjects it was re-checking. The same
shape was available here — comparing `dataset` against the *provisioned snapshot's* `release.json`,
which is very often the snapshot the module was drafted from. So the current release is read from the
source over the wire, and the rows compared are the ones on disk before this run's commit; the licence
rows `enrich()` itself writes are at the `resolution` layer and carry no `dataset` at all.

**And the denominator has to be honest.** `subjects` counts the legs asked *and* answered comparably;
an unreachable or unaskable source is named in the record's `detail` rather than counted, and with no
leg settled the pass records a **skip** instead of `ran(0, 0)`.

### Repairs refused, and still refused

- **A column stating what this module was made from and what would age it** — RM71's argument one table
  over: it restates `dataset` and rots where `dataset` is maintained.
- **A publish-time or catalog-side signal** — puts the notice where a reader is rather than where an
  author is, and is out of these packages' scope. Still recorded as an ask rather than built.
- **Nothing, deliberately** — defensible only while a module has one author who remembers.

### Also worth knowing

The probe **streams and abandons** rather than sending a `Range` header: a server that ignores one
answers `200` with the whole 200 MB body, and the probe silently becomes a download. Reading the first
256 kB off a normal stream and closing it needs no promise from the server.

## RM130 — a check's findings were counted and not kept, so a conflict had no name to act on

**Shipped in `just-dna-format` + `just-dna-compiler` + `just-dna-enricher` on 2026-08-28.** Two new
optional derived tables, three new closed vocabularies and one new warning code — additive throughout,
and no published module's identity moves, because a module that carries neither file contributes
neither entry.

**Severity** medium · **Status** ✅ shipped in 0.7 (the observability half shipped 2026-08-24) ·
**Owner** enricher · **Motivating case** S70 (just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md ·
**Decided in** [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm130--a-checks-findings-are-counted-and-not-kept-so-a-conflict-has-no-name-to-act-on),
amended the same day by RM134

### What shipped

`clin_sig_concordance.csv`, keyed `(variant_key, genotype)`, and its paired
`clin_sig_authority_calls.csv`, keyed `(variant_key, genotype, authority)`. The first carries the
agreement state — `authority_concordance`, `authored_position`, `opposed`, and the module's own call —
and the second carries what each authority actually said, with its raw token and its confidence in its
own units. Both are compiled to parquets, fact-hashed, summarized in `manifest.clin_sig_concordance`,
and reported at `validate` and `compile` by `clin_sig_concordance_contested`.

The enricher half is `concordance.py` (the classifier, the row builder and the writer) plus
`clinical.clin_sig_concordance`, which returns the two tables or `None`. `ClinSigConflict.clinvar`
became `authority_clin_sig` beside a new `authority`, with the old name kept as a read-only alias.

### Why the shape changed before it was built, and the reason is the durable part

The entry asked for a table carrying *the authored value, the source's value, and whether the two are
opposed or merely different*. That shape names its authority in a **field** — `ClinSigConflict` really
did carry `clinvar: str` — and RM134 arrived in the same release with a second authority. Shipping the
first shape would have cost a key change or a retype one item later, and Principle 3 reserves both for
a major. Two items landing in one release is what caught it; either alone would not have.

So the parent row carries an agreement *state* instead of a pair of values, and *which* authority spoke
became data in the detail table. That is what makes the key stable at any N.

### The stress test, and why one field could not have held it

A single vocabulary was drafted with seven outcomes and failed at five authorities: its members named
the authority inside themselves (`clinvar_only`, `pubmind_only`), so a third source needed a third
member and five needed every subset. The root cause was one field carrying two axes — *do the
authorities agree with each other* and *where does the module's own call sit* — with `concordant`
defined as "both agree **and** the authored row agrees with them" and `authored_dissents` as a sibling
member. That is the Principle 5 anti-pattern and the combinatorial growth was its symptom. Split, both
vocabularies are five members at two authorities and five at five.

### Nothing resolves a split, and that is a decision rather than an omission

At five authorities with a declared order E>B>D>C>A, suppose E and A agree and B, C and D agree against
them. Lexicographic resolution says E; majority says B/C/D; choosing between those rules is a judgement
about how authority rank trades against agreement count, and it needs a weighting model. This
workspace has refused to invent one three times — RM126's `should_rebuild` (*the same fact costs
consumers differently, so the decision is theirs and only the fact is ours*), `@clinsig-never-escalates`,
and RM16's PRS weights. So `authored_position` is a relation to the **set**: computable with no weights,
true at any topology, and the E+A case reads `discordant` + `matches_some` under either rule.

The same refusal one level down keeps confidence unnormalized. A gold-star count and a literature
miner's evidence-depth count are different instruments, and folding them into one number is three axes
in one field — so the detail row carries the published value with `confidence_unit` beside it, and the
model refuses a magnitude with no instrument named (`@weight-has-no-unit`, enforced rather than
documented).

### The lifetime, and the succession it promotes

**A conflict is a question and an `overrides.csv` row is the answer.** The record joined the overlay's
covered set, taking it from seven to eight, and it is in for a *different* reason from the other seven:
not because it carries hand-curation a re-derivation would destroy — it carries none and is rewritten
whole on every run — but because answering a contested subject is what an overlay row is. RM124's
vindication signal then works for free: when the archive catches up, the author's `suppress` stops
changing anything.

The paired detail table is **out**, by name, in the same equality test. The author answers the question;
they do not get to rewrite what an archive published, and an overlay over the detail table would let a
module ship ClinVar's name above a classification ClinVar never made.

The table's documentation and the warning both name `overrides.csv` and **never**
`provenance.json`'s `outranks`. The two are the same idea one table apart, 0.7 settled the overlap as a
dated succession in the overlay's favour, and steering a new author onto the side that survives 1.0
cost a sentence.

### Severity, and the one thing it must never become

Warning-tier in both modes, never escalating under `strict` (`@clinsig-never-escalates`). A
disagreement with an archive is a fact about the field, not a defect in the module: half the time the
archive is the stale side, and failing a build on one would have this format arbitrate a clinical
dispute.

The finding is **actionable rather than carried**, which inverts its neighbour
`verification_findings_recorded` and does so deliberately. Nothing an author writes moves a number
sitting in `verification.json`; a contested row is answered by writing an overlay row, and the count is
taken over the **post-overlay** table, so writing one clears the finding. `overlay_rows_suppressed`
reports the removal, so an answered conflict is visible rather than silent.

### Two things found while building it

**`opposed` is a tautology at one authority, and the record is what makes it stop being one.** The
two-way check only reports where both sides are opinionated and their camps differ, and
`pathogenic`/`benign` are the only two opinionated camps — so every conflict it reports is opposed by
construction, and `_clin_sig_detail`'s differing-but-not-opposed group has no producer today. Filed
rather than mended: the formatter lives in `enrich.py`, the group becomes reachable as soon as two
authorities can disagree while neither contradicts the module, and that is exactly what the record is
shaped for.

**Several vocabulary members are reachable by the classifier and not by today's producer** — `absent`
needs a subject the module makes no clinical claim about, and `none` needs every archive asked and
empty; neither is a contested subject, so neither is written. They are kept on the
`VALID_RSID_STATUS.withdrawn` precedent: a member is permanent within a major, so reserving one now is
free and adding one later is not. The classifier tests walk every topology at three and five
authorities and assert an equality against both vocabularies, which is where the members are exercised.

### Repairs rejected

- **Folding the conflict into the overlay as an evidence column.** A conflict nobody has answered has
  no overlay row to live on, so unanswered conflicts — the entire point — would have nowhere to be.
- **Escalation under `strict`, or auto-correction.** Out of scope on the reporter's own scoping and
  ours: a conflict is a question, and half the time the archive is the stale side.
- **A `majority` or consensus field.** The E+A case is the argument; precomputing it is
  `should_rebuild` wearing a different name, and it would publish a judgement as a fact.
- **A second significance map.** The check's whole output is a comparison of two normalizations, so a
  drift between two maps would report a disagreement with ourselves as a disagreement between two
  archives. `CLIN_SIG_CAMP` moved out of `clinical.py` rather than being copied, for the same reason
  one level up.
- **Writing a row for every compared subject.** A record of every agreement is a copy of the module's
  own `clin_sig` column with a second opinion attached, and the number of subjects compared is already
  published as the check's denominator.

## RM131 — the warnings channel says what each finding is, and whether an author can clear it

**Shipped in `just-dna-format` + `just-dna-compiler` on 2026-08-28**, with the deprecated DuckDB
resolver in `just-dna-enricher` brought along because its warnings land in the same published channel.
Both halves the proposal sequenced, in one release, because the audit is the cost and doing it twice is
what the sequencing existed to avoid.

**Severity** medium · **Status** ✅ shipped in 0.7 · **Owner** compiler ·
**Motivating case** S68 (just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md

### What shipped

`compilation.carried` and `compilation.warnings_summary` beside `compilation.warnings`, which is
unchanged down to the byte — the same sentences in the same order, so nothing that greps a phrase
broke. `carried` is the subset **no edit to the spec directory can clear**; a consumer subtracts it to
get the actionable set. `warnings_summary` is `{code: count}` over `vocab.VALID_WARNING_CODES`, with the
values summing to `len(warnings)` so a reader can tell the digest is complete. The same three fields
are on `ValidationResult`, `CompilationResult` and `ClosureResult`, on every path including a failed
compile.

Sixty-eight codes, nine of them carried. `findings.CodedWarning` is a `str` subclass, so the transport
stayed `list[str]` and every de-duplication, extend and phrase-grep went untouched.
`sweep.compare_module` reports `carried_added` beside `actionable_added`, which is the discriminator
RM126's own comment said would land here.

### The three things worth not re-deriving

**The container was free and the vocabulary was the release**, which was the whole of the original
deferral and is answered rather than dismissed: the set was derived across every emission site in three
tiers, and the derivation rule is *one code, one remediation* — two sentences cleared by the same edit
share a member and the sentence says which cell, two cleared differently do not. So the weight-sign
pair is one code across `state` and `direction` (two axes under P5, one edit) and the five orphan fact
tables are one code, while a VCF pointer collision and an unselected element are two.

**The emission surface was larger than the entry's "~29 append sites and 16 returning helpers"**, and
the parts it missed are the parts that would have shipped unclassified: the `findings`/`messages`
collectors a survey of `.append` cannot see, two `.extend` sites reaching into the schema tier's
`measurement_shape_warnings`/`deprecation_warnings`, `validate_bins`, `overrides.apply_overrides`, and
the deprecated resolver in the *enricher*, whose warnings reach `manifest.compilation.warnings` like
everything else. Re-derive such a count; never trust the one in an entry.

**A `carried` list beside `warnings` was the right shape and a field on each finding was not**, but the
`str`-subclass transport that makes it cheap leaks the code at exactly two places, and both are
load-bearing: a pydantic field flattens the subclass (so `compile_module`/`close_module` seed from an
internal `_validate_spec` that returns the classified list beside the result), and any reformat returns
plain prose (so three prefixing sites go through `findings.restate`, which refuses an uncoded input
rather than inventing a code). Both are pinned by tests, and the second half of the guard is a run over
the whole reference corpus — a static walk proves every *site* names a code, and only a run proves every
*message that arrives* still carries one.

### What it did not do

**No cap, no truncation, no verbosity flag**, per the reporter and us: all three hide findings rather
than organising them, and the author with the most warnings is the one who most needs the hidden ones.
**No metainfo artifact** — the channel already ships and `artifact_digest` is a Merkle root over the
parquet `FileEntry` list, so `manifest.json` sits outside it and neither new field moved a hash on any
published module. **Codes were not derived from the pinned phrase catalogue** (partial by construction,
and a digest that silently omits findings is worse than none because the reader believes it) **nor from
the emission site** (a refactor then renames a published key — P3's rename arriving by the back door).

**`axes["warnings"]` still fires on any movement of the set**, deliberately: narrowing it would make a
published axis mean something other than what every record already written claims about it, and the axis
drives no rebuild. A pre-0.7 manifest reports every addition as actionable, which is the safe direction —
calling an unrecorded finding carried would tell a reader that something fixable is not.

### The suppression record it carried in (RM124 × RM131)

A row removed by a `suppress` was invisible in the build product: absent, with no trace of why, and a
consumer holding the compiled bytes has no `overrides.csv` to read. It now reports one line per
**reason** with a count — which is what `reason` being a required column buys — and the count is over
the *overlay's* rows, never over the rows removed. That is not tidiness: after `reverse_module` the
derived table is already post-overlay, so an effect-based count would say a number on lap 1 and vanish
on lap 2, making a module disagree with its own round trip on a published field. Proved against the real
compile → reverse → compile path. Classified **actionable** rather than carried, because the author owns
the overlay and deleting the row clears it.

The three candidate derivations are argued at length in
[PROPOSAL_0_7 § RM131](proposals/PROPOSAL_0_7.md#rm131--warnings-is-a-flat-liststr-and-the-discriminator-that-would-make-it-readable-is-discarded),
which is where the decision was taken; the entry this replaces lived in ROADMAP.md and not in
ROADMAP_0_7, so there is no second copy to keep in step.

## RM124 — an author's correction to a derived table now has somewhere to live

**Shipped in `just-dna-format` + `just-dna-compiler` + `just-dna-enricher` on 2026-08-28**, as
`overrides.csv` — a new optional authored table, additive under Principles 3 and 8, so no published
module's `content_signature` or `artifact.digest` moves. It is the keystone of the 0.7 round: RM83
closes into it, RM130 was blocked on one of its questions, and RM128's central ask thins because of it.

**What it discharges.** The 2026-08-12 cost amendment names the class in its own words — *a derived
table that is both machine-written and human-overridable can be edited into a state that is not merely
stale but a false claim, which wants a mechanism rather than a convention.* RM45 discharged that for
exactly one table by making `verification.json` unwritable by hand. Nothing discharged it for the seven
where overriding **is** the intended feature, and their merge-not-clobber rule meant that re-deriving
one required deleting it, which discarded every hand-curated row in it.

**The covered set is seven, and the number is a correction.** The proposal says "the six covered
derived tables" and never enumerates them; the roadmap entry it inherits the number from does not
either. The maintainer settled it on 2026-08-28 as every merge-not-clobber derived sidecar —
`resolution.csv`, `frequencies.csv`, `gene_metrics.csv`, `gene_validity.csv`,
`clinical_assertions.csv`, `literature.csv`, `gwas_effects.csv` — with `sources.csv` / `licensing.csv`
outside it, because it has its own merge path and is the one derived table the schema tells a human to
write. `overrides.OVERRIDABLE_TABLES` is the registry and a test asserts the equality against the
compiler's own table tuples rather than a floor.

**Three decisions worth not re-deriving**, all of them recorded in
[SCHEMAS § the authored overlay](SCHEMAS.md#the-authored-overlay-07-rm124--overridescsv):

- **One `member` column, whose meaning the named table fixes**, rather than a per-table key grammar —
  which is a rule every consumer would re-derive, differently. An empty `member` on a grouped table is
  group-scoped for `update` and refused for `suppress` (not recoverable by reading the result) and for
  `insert` (the row it would create carries no member value, so nothing could match it again).
- **No `previous_value` column.** `reverse_module` emits the post-overlay derived table plus the
  overlay, so the overlay applies twice; all three operations are idempotent set operations, so the
  second lap is a fixed point, checked by test rather than assumed. The alternative would put a derived
  cell inside an authored table, which rots the moment the source moves.
- **No operation reports its own no-op**, and that is forced rather than tidy: after a reverse, all
  three no-ops are true of a healthy module, so reporting any of them would make a module and its own
  round trip disagree on `manifest.compilation.warnings`. The price is stated rather than hidden — a
  `suppress` with a typo'd subject does nothing, forever, and cannot warn.

**Merge-not-clobber's behaviour is unchanged and its cost is gone.** A re-run still gap-fills rather
than re-asking every subject — re-asking was explicitly rejected, since it would put the full
resolution time on every pass. What changed is that a recorded row now carries no authored content, so
leaving it alone risks nothing and a full re-derivation (`rm` plus a re-run) is free. The seven writers'
docstrings say so where a reader outside this repo actually meets them, in the same commit as the
behaviour.

**The `outranks` overlap is a dated succession rather than a merge.** Both mechanisms stand in 0.7, the
duplication is stated in SCHEMAS, and the unification is [RM135](ROADMAP.md#rm135--provenanceitemoutranks-is-superseded-by-the-overlay-and-one-of-them-has-to-go)
on the 1.0 tracker. 0.7 emits no deprecation warning, which is P3 rather than caution: an author warned
off `outranks` has nowhere to go until the overlay reaches authored tables.

**Coordination.** `just-dna-registry` rebuilds a spec directory from `RECOGNIZED_SPEC_FILES`, a
hand-kept mirror of our table constants, and a name missing there is a file dropped on re-publish —
which is how `licensing.csv` was lost before their 0.16.2. `overrides.csv` needs one entry added there;
it is recorded in [INTEGRATION_0_6.md](INTEGRATION_0_6.md) rather than left to be discovered.

## RM128 — `enrich()` persisted nothing until its tail, so a run killed at minute 29 had written nothing

**Shipped in `just-dna-enricher` on 2026-08-28**, as `just_dna_enricher.transaction` plus three
keyword arguments on `enrich()` and two flags on the command. Additive: no schema, no manifest field,
no vocabulary. **Motivating case** S66 (just-module-creator).

**The truncation half was already closed** on 2026-08-24 — nine sidecar writers go through
`layout.atomic_writer`, so a killed process leaves the previous table rather than a short one. What
this entry records is the three asks beside it, each of which was a decision rather than a missing
line.

**The central ask dissolved rather than being argued down.** It was filed as incremental or
checkpointed persistence, and it turned on a question nobody had written down: *is a `strict` refusal
allowed to leave rows behind?* The choice looked like **keep the promise or recover the thirty
minutes**. It is not a choice. The run becomes a **transaction**, which keeps the promise absolutely
and recovers the work as well.

- **Durable staging beside the target, plus an atomic commit at the gate.** Each live link's answer is
  staged to `.<name>.staging/answers.csv` beside `resolution.csv` as it arrives; the table is still
  written once, at the bottom, by a writer that renames into place. `layout.atomic_writer` already
  staged exactly there, so this extends a shipped primitive from one file to a whole run rather than
  inventing one.
- **Same-directory staging is the correctness condition, not a convenience.** A rename within one
  filesystem is atomic; `shutil.move` across a partition degrades to copy-then-delete and is not.
  Staging beside the target makes a cross-device move structurally impossible rather than merely
  avoided, which is why the test asserts the sibling relationship structurally.
- **What is staged is the answer, never the row.** Everything downstream of an answer recomputes —
  the hosting filter, the pseudoautosomal selection, `locus_index`, the minted ids — so a flag that
  changed between the kill and the resume changes the table exactly as it would have, and the journal
  cannot carry a stale derivation. It is seeded **between the caches and the live links**, so a
  snapshot provisioned in between still wins the variant it would have won on a first run.
- **Only positive answers are staged.** A failed request is unchecked rather than absent
  (`@unreachable-not-absent`), and freezing one into the journal would make a transient outage
  permanent on every future run. And a staged answer is honoured **only if the link that produced it
  would run this time**: the seeding reads the same two booleans that gate the live blocks, so a
  `--no-gnomad` or `--offline` resume drops that link's answers rather than stamping a row a first run
  with those flags could never have written — `alts` is a fact column, so the alternative would move
  the compiled digest.
- **The gate commits**, so *a refused `strict` run changes nothing* became a written promise instead
  of an accident of statement order — the item's actual question, answered in the direction that
  breaks nothing. The test asserts it on the bytes of a pre-existing table, not on a return value.
- **`--keep-staging` keeps the staged answers after a successful commit**, for debugging; the default
  removes them, and both values are exercised.
- **Not mode-conditional**, as the entry refused in advance: `write=True` meaning "at the end" under
  `strict` and "as we go" under `best_effort` is a flag that does not mean the same thing in every
  function that takes one. Under a transaction it does, because committing is the only write, and
  `write=False` stages nothing and takes no lock — with nothing written there is no window to exclude.

**RM124 thins what the promise has to protect**, and the two were reached independently. What a
staged, uncommitted table can contain is now provably machine-derived and never an authored value,
because the author's corrections live in the overlay.

### The lock, and why it is `flock`

The transaction does not close the concurrency window: two runs can each stage and each commit, last
writer winning over a merge with neither knowing. The reported incident is the sharp form — a
client-side kill did not stop the worker, a zombie run reached the write and overwrote a restored
330-row table with 162 rows, and the module then validated, closed and compiled green. Nothing
downstream could see it, because the three branches that deliberately write **no row** for an
unanswerable subject make a shorter table indistinguishable from a module whose author resolved less.
Those branches are correct and were not in scope.

`flock` on the spec directory's own descriptor, non-blocking, **no lockfile**. A lockfile left by
exactly the kill this item is about would block every subsequent run — a worse unattended failure than
the one it prevents — and the staleness rule that would fix it is a clock, which this repo has refused
before (*guard the plan, not the clock*). `flock` dies with the process, so there is nothing to expire.
Non-blocking because a run silently waiting half an hour behind a zombie is its own unattended failure,
and the refusal is accurate by construction: the lock is only ever held by a live process.

**The degradation is documented rather than silent, which the design explicitly owed.** No `fcntl` on
a non-POSIX platform, or a filesystem answering `ENOLCK`/`EOPNOTSUPP`, logs that the run is **not**
excluded from a concurrent one and carries on. Both branches are reached by tests — an unreached
refusal branch is not an API, which the wave-1 audit had just demonstrated. **`flock` is untested here
on the network filesystems a consumer may use**, and ENRICHER says so where a consumer meets it.

### The progress unit, argued rather than guessed

`progress: Callable[[int, int], None] | None = None`, reporting `(done, total)` over **subjects**. The
entry filed this rather than shipping it because the resolver chain is batched inside `resolver.py`
rather than being a per-subject loop, so the unit reported is a design choice — and a leaf shipped
against a guess is one Principle 3 keeps working forever.

- **The incident is an idle timeout.** Both reported runs died at 1800 s with essentially every
  variant resolved, so what the caller needs first is a keepalive with monotonic progress — which
  rules out **phases**, since a 29-minute phase emits nothing and the timeout fires anyway.
- **`total` must be known up front** for the number to mean anything to a caller rendering it. The
  subject count is; the link count is not, since it depends on what resolution finds.
- **Subjects are the only unit the author's mental model already has.** Links are an implementation
  detail of the batched resolver, and publishing one would make a refactor of `resolver.py` a contract
  change — the rename P3 forbids arriving through the back door.

No protocol was added, because none was asked for: two integers, no object, no event vocabulary to
keep working forever. Monotonicity is structural — `done` is the size of a set that only grows — and
the assembly loop touches every subject, so the last report is always `(total, total)`.

### `enrich --rederive` — RM83's residue, and it composes rather than adds

A full re-derivation that keeps a baseline reports what moved, which is MODULE_LIFECYCLE § 5.1's
canary performed. It composes with the transaction: the recorded table is still in memory and the
fresh one has not been committed, so both sides exist at the commit boundary and the comparison is
free. The comparison is over `RESOLUTION_FACT_FIELDS`, read off the registry rather than restated,
because the provenance columns move on every run by design.

- **`None` is not `[]`.** `None` says nobody re-derived; `[]` says every recorded subject was re-asked
  and every one still answers the same. Only a real difference prints — a comparison whose empty
  result is the normal case must not announce a zero as though it were evidence.
- **A recorded subject the run could not ask about keeps its recorded rows**, and the carry-forward
  warns naming them. Without it, an offline `--rederive` would replace a full table with an empty one:
  the reported incident wearing a new flag, and the sharpest test in the unit. Answered-and-absent is
  an answer and does replace (it writes a `not_found` row); could-not-ask is not.
- **A re-derivation resumes only another re-derivation.** After a gap-filling run commits, its staged
  answers are exactly what produced the recorded table, so seeding them would compare that table
  against its own provenance and report a clean bill for precisely the subjects being re-checked —
  the canary silenced by a file left behind for debugging. The journal records which run wrote each
  row; the reverse direction is allowed, because an answer a re-derivation obtained is still an answer.
- **The honest limit is stated rather than hidden.** `rm resolution.csv` plus a re-run re-derives just
  as correctly and reports **nothing**, because it destroys the old values before the fresh ones
  arrive and nothing holds both sides.

**Repairs rejected**, kept because each looks obvious from the headline: a `--refresh` command (RM83's
three open questions were all answered elsewhere, leaving a mode on the command that already does the
derivation); a diffs file or table, or a proposed table beside the current one (version control with no
consumer, beside the version control the author already has); a pass that *applies* the newer value
(rewriting an authored or curator-set cell destroys the evidence of the upstream change — still the
rule, and the overlay does not soften it); and re-asking every subject on **every** run (dropping
merge-not-clobber did not mean that, and reading it that way would put the full resolution time on
every pass to buy drift detection nobody asked to run continuously).

### Charter check

P2 — enricher-only; the compile path imports none of it. P3 — three keyword arguments with defaults, a
staging directory and a new module are additive; no schema, no manifest field, no vocabulary. P7 — a
committed run produces the table an uninterrupted run produces, which the resume path proves by test.

## RM83 — a derived sidecar can only be refreshed by deleting it, which discards the overrides it exists to hold

**Closed, not shipped, on 2026-08-28**, in the commit that landed RM124 and not before — a closure
recorded against an unlanded dependency is the kind of bookkeeping that makes a ledger untrustworthy.
**Dissolved rather than argued down**: the premise stopped holding.

The entry named a missing operation, a `--refresh` that re-asks the source about recorded rows and
reports the difference, and it had two halves. **The refresh half stops existing** — its problem was
that re-deriving a sidecar means deleting it and losing the curator's rows, and once the derived files
are pure build products with the corrections in the overlay there is nothing inside a sidecar to
preserve, so `rm` costs nothing and needs no command wrapped around it to be safe. **The drift half
stops being unperformable** — merge-not-clobber meant a re-run never re-asked about a recorded row, so
a source that silently *revised* an answer moved no `fetched_at`, no fact signature and no digest,
making MODULE_LIFECYCLE § 5.1's canary an instrument that could not fire, because detecting drift *was*
the delete-and-re-derive that discarded the overrides. With the discard harmless, a full re-derivation
is an ordinary operation and the canary fires from it.

**The blocking question is answered rather than deferred.** The entry named it: on most sidecars
nothing records that a row was overridden, so "re-derive the machine rows and keep the overrides" was
not implementable, because the tier could not tell a curator's edit from what the source said last
time. Under the overlay the tier never has to — the edit is recorded by construction and the derived
row carries no authored content at all.

**Nothing named in the entry is built.** No `--refresh` command, no proposed table beside the current
one, no diffs file. What remains is a residue and it is a flag rather than a command: `enrich
--rederive`, which stages a fresh table beside the current one and commits by rename (composing with
RM128's transaction), so both files exist at the commit boundary and the report of what moved is free.
The honest limit is stated with it — `rm` followed by a re-run destroys the old values before the fresh
ones arrive, so that path re-derives silently and correctly and no report is possible.

**Repairs rejected**, kept because each looks obvious from the headline: a diffs file or table tracking
what moved between passes (version control with no consumer, beside the version control the author
already has, over a file now regenerable from source plus overlay); a pass that *applies* the newer
value (rewriting a curator-set cell destroys the evidence of the upstream change — still the rule, and
the overlay does not soften it: an overlay row is the author's answer to a difference, never the
tier's); and re-asking every subject on every run (dropping merge-not-clobber does not mean this, and
reading it that way would put the full resolution time on every pass to buy drift detection nobody
asked to run continuously).
## RM132 — `pharm_variants.csv` made a clinical claim per row and could only cite per variant

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm132--pharm_variantscsv-makes-a-clinical-claim-per-row-and-cites-per-variant) on 2026-08-28 — SHIPPED in 0.7.** `PharmVariantRow.pmid` plus both literature cross-check sites in the same release; `provenance_quote` did **not** follow, stated rather than implied.

**Severity** medium · **Status** ✅ shipped in 0.7 · **Owner** format (schema) + compiler + enricher ·
**Motivating case** S73 (just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md

### What was observed

A ClinPGx-drafted module carried **1,482** drug-response rows and had nowhere to ground any of them:
sixteen model fields, thirteen authored, none a PMID or DOI. The reporter asked which of three
provenance models was intended, worked out that none of them held, and declined to build on any.

**The tree had already answered it one release earlier.** RM47 decided this shape for a structurally
identical table, and the rule underneath generalizes: **a row cites when its claim is finer-grained
than `studies.csv`'s key.** `studies.csv` keys on `(variant_key, pmid)`, so a study row attaches to a
*variant*; `pharm_variants.csv` keys on `(variant_key, drug, genotype, phenotype_category,
annotation_id)`, so one study row would attach the paper to every drug, genotype and phenotype
category recorded for that variant at once. `evidence_level` is not the provenance handle — it points
at somebody else's *grading of* the evidence rather than at the evidence — and the licence row's
`source`/`dataset` state redistribution terms rather than grounding a claim.

### Why a full-cost authored column was taken rather than deferred

This is the item the round's sort rule turns on, so the argument is kept rather than assumed.

**What P9 prices is not the byte.** An authored column is full cost because a human must learn it and
P3 keeps it working forever, so the risk being priced is *getting the shape wrong* — and that risk was
spent a release ago. The column is a copy of two shipped fields under one grammar, so an author who
has met either learns nothing new. Demand fixes an *unfixed* shape; there was none left here for
demand to fix.

**It is closer to a half-defect than to a new capability.** The table already made a clinical claim
per genotype and structurally could not ground one. That is a hole in an existing concern rather than
a new concern added to a table, which is the distinction the *one concern per table* gate turns on.

### What was built

`PharmVariantRow.pmid`, optional and free-form, validated by `spec.validate_pmid_cell` — the one
grammar every citation pointer in the schema routes through, so the PMCID diagnosis and the
`[PMID: N]` spelling come with it and cannot drift. No compiler change was needed for the column
itself: the parquet materializer and the reverse writer both derive their column lists from the model.

**Both cross-check sites learned the site in the same release**, which is the half that made this a
piece of work rather than a column, and is RM47's recorded lesson in its own words — *shipping the
column without both would be evidence the format never checks, which is worse than the gap.*
`_cross_check_literature` (with `split_cited_literature` and `_check_quote_counter_is_current`
beneath it) and the enricher's `enrich_literature` both read it. Since RM79 the orphan finding has
teeth: blind to the new site, the compiler would not merely report a pharm-grounded citation as stale,
it would **discard** the literature row the claim's evidence lives in.

**The roster is derived, which is the part that generalizes.** Rather than a third hand-kept list,
`_CITING_TABLE_KINDS` is every `_TABLE_KINDS` model declaring a `pmid`, and the new public
`load_citing_rows` / `table_citations` walk it. The enricher reads through that pair — the RM40/RM41
requirement, met structurally: a test walks the enricher's own source with `ast` and asserts no citing
CSV name appears in a string constant there, so the next kind to declare the column is read by both
tiers with no edit to either. `load_binning_rows` / `binning_citations` stay and stay narrow; a caller
asking for the binning kinds is asking about thresholds, not about the citations a module makes.

One warning text moved with it — `literature_row_uncited` now reads *"no study, bin or pharm row in
this module cites"*. The code is the stable handle and did not change; the phrase is pinned by four
tests, which is what makes each rewording a deliberate act.

### The open question, answered

**`provenance_quote` does not follow, and the release says so rather than leaving it implied.** The
binning side drew the same line deliberately: the row cites, and `studies.csv`/`literature.csv`
describe. That is what stops `StudyRow`'s whole provenance column set — population, `p_value_num`,
`effect_size`, `provenance_quote`, `curator` — migrating onto a citing row one column at a time. A
1,482-row body of clinical claims is exactly where somebody asks next, which is the reason to state
the line rather than the reason to cross it. The consequence is carried in the code too: a pharm row
cites and cannot quote, so it contributes a denominator of **zero** to the quote-counter check rather
than being skipped, or a literature row reachable only from a pharm row would read as cited by
nothing.

### Repairs refused

- **Widening `studies.csv`'s key.** The repair that looks obvious and the one RM47 already refused: it
  would make a study row's subject depend on which table read it.
- **Treating `evidence_level` as the provenance handle.** It grades evidence rather than pointing at
  it, and the two now sit side by side in the model so the distinction stays visible (P5).
- **A second table roster in the enricher.** The RM40/RM41 shape, and a list that goes stale the next
  time a model declares the column.
- **A grounding warning for an uncited pharm row.** `_check_binning_grounding` exists for the
  interpretive-threshold case — where a boundary is a clinical judgement with nothing behind it — and
  a drug-response table is not that case. Adding one would have fired on every ClinPGx draft.

### Charter check

P3 — a new optional column, additive; no published module is invalidated. P5 — citation and grading
are separate axes on separate columns. P7 — the round trip is asserted on the `pharm_variants.parquet`
bytes as well as on `content_signature` and `artifact.digest`. P8 — optional with respect to every
published module, proved by running it: a spec with no `pmid` header hashes equal to the same spec
carrying the header with every cell empty. P9 — full cost, taken with the argument above rather than
by weighing file count.

## RM70 — `requires_callable` is `VariantRow`-only, so no PGx table can state CPIC's core assumption

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm70--requires_callable-is-variantrow-only-so-no-pgx-table-can-state-cpics-core-assumption) on 2026-08-28 — BUILDS in 0.7.** `requires_callable` on `HaplotypeRow` and `PharmVariantRow`, not on `DiplotypeRow`; `callable_from` does not travel with them.

**Severity** medium · **Status** SHIPPED in 0.7 — optional `requires_callable` on `HaplotypeRow` and
`PharmVariantRow`, not on `DiplotypeRow`, and `callable_from` did not travel · **Owner** format (schema)
· **Found by** dogfooding on 2026-08-13, `reference_examples/cyp2c9_warfarin_grch37/`

### What was observed

CPIC's star-allele system assumes that a position not called is reference — that is literally
`requires_callable=false` — and `haplotypes.csv`, `pharm_variants.csv` and `diplotypes.csv` carry no such
column. `requires_callable` and its companion `callable_from` are on `VariantRow` alone. So a
star-allele module cannot record whether its call needed the defining positions to be callable, which is
the single assumption a consumer most needs to know before trusting a `*1/*1` result.

The corpus shows both sides of it. D6 confirmed RM57's inversion warning fires correctly on the row type
it exists for: a `requires_callable=true` row with `quality_from=QUAL, min_quality=30` warns, cites VCF
§1.6.1.6, and names GQ and MIN_DP as the fix. D2 could not exercise it at all, because a PGx module has
no `variants.csv` — the check and the column are unreachable from the module kind whose upstream states
the assumption in prose.

### What was built

The two columns as decided, and nothing else. The parquet schema and the reverse writer both derive
their column lists from the model, so no compiler change was needed — `_polars_type` maps `bool | None`
to a nullable `pl.Boolean` and `_scalar_cell` already rendered `None` and `False` as `""` and `"false"`.
That was proven rather than assumed: a temporary mutation collapsing an authored `False` into a blank
cell was run against the round-trip test first, and it failed on both tables.

`reference_examples/cyp2c9_warfarin_grch37`, the module the gap was found against, now populates the
column and exercises all three states. `haplotypes.csv` records CPIC's assumption verbatim (`false` on
both defining SNPs). `pharm_variants.csv` is keyed on genotype and so splits: the reference-homozygote
rows carry `true`, because a variant-only callset emits no record for them and absence is not the call;
the rows naming an alternate allele carry `false`; and the twelve rows whose reference allele the
module's own `resolution.csv` never named are left **blank** rather than guessed. That answers the PGx
half of the consumer ask for `requires_callable` *"populated somewhere real, to try the round trip
against"*. The module was re-closed, so its attestation binds the edited bytes.

**No cross-table equality check, and the reason is not cost.** `haplotypes.csv` and
`pharm_variants.csv` can name one locus and legitimately disagree: a haplotype row's claim is about
assigning the *reference haplotype* there, and a pharm row's is about matching *that row's genotype*.
The fixture holds exactly this shape — a haplotype default-to-reference (`false`) beside a
reference-homozygote genotype needing a proof (`true`) — so a checker asserting the two agree would
refuse a correct module. Both field descriptions say what each claim is about, and a test compiles the
disagreeing pair clean so the check is not added later.

### Cost, priced honestly

`requires_callable` is an **authored** column, which is full cost under the 0.6 charter amendment — the
most expensive kind of addition this format makes, on the layer the rare human writes. That is the
reason the item is filed rather than done, and it is also why the scoping question below is not a
detail: covering three tables and covering the two that name a position are different prices for the
same capability, and the difference is a column on the table a human writes.

### Candidate repairs, and why each is wrong

- **Copy the column onto all three PGx tables.** Full cost, three times, and wrong on the third.
  `haplotypes.csv` and `pharm_variants.csv` name loci — they are two of RM43's three positional tables —
  so a callability claim on either is about a position the row states, which is exactly what the column
  means on `VariantRow`. `diplotypes.csv` names a star-allele *pair*, not a locus, so the same column
  there could only mean "the variants defining these two haplotypes were callable" — a fact about
  `haplotypes.csv`'s rows, restated one table over where it drifts the moment a definition is edited.
  One concept, one home (P5).
- **Declare it once in `module_spec.yaml`.** The verdict is per locus, and this repo has twice paid for
  assuming otherwise: RM36 rejected per-CSV build declaration because two files could disagree about one
  fact, and RM32 rejected a gene-scoped PAR verdict because XG and SPRY3 straddle a boundary. CPIC's own
  assumption is not uniform either — a gene whose common alleles are single SNPs and one defined partly
  by a structural event do not have the same callability requirement, and CYP2D6 has both inside one
  gene.
- **Derive it from `callable_from`.** There is no `callable_from` on the PGx tables either, so this
  starts by adding the more expensive of the two columns. It is also an axis overload: `callable_from`
  says *where the proof lives*, `requires_callable` says *a proof is required*, and a row may
  legitimately require one and not know where the evidence is. Deriving requiredness from the presence
  of a pointer collapses two questions into one column.
- **A stamped, compiler-managed parquet column.** Nearly free under the amendment, and it cannot work:
  this is a curator's claim about what the annotation assumes, so there is nothing for the compiler to
  compute. A stamped column carries only what the compiler derives.
- **Author the defining positions a second time in `variants.csv`.** Two tables then name one locus, and
  `variants.csv` alone carries `alts` as a resolution fact, so the shadow rows move `artifact.digest`
  while asserting nothing new — and it re-opens *a star allele can be used without being defined* from
  the other end, with two definitions instead of none.

### Is it gated on the same thing as RM65/RM66?

**No, and the difference is the useful part of this entry.** RM65 and RM66 wait on a real repeat-caller
or CNV VCF because the open question there is what a *caller emits* — the shape of the data decides the
schema. This question is about what a *curator asserts*, and the assertion already exists in prose: CPIC
states it. A PGx caller VCF would say nothing about which of three tables should carry a curator's
claim. The adjacency the ledger records is that both ask whether a non-`variants.csv` table should carry
something `variants.csv` has, not that they share a blocker.

**What unblocked it:** the entry's own closing reading, put to the maintainer and taken as written —
*two* optional columns, on `HaplotypeRow` and `PharmVariantRow`, the PGx tables that name a position,
and **not** on `DiplotypeRow`. The second question the entry left open, whether `callable_from` travels
with them, was answered the cheap way: it does not, and it is added when a module needs to say where the
proof lives. What the entry got wrong is the other half of its unblocker — it also asked for *a real
module whose author wants to state it*, and the module was already in the corpus. The one this was found
against is the one that now states it.

# The 2026-08-24 consumer round (S63–S74)

Twelve items from two reporters, triaged in one pass. The per-item record is in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md); what is here is the reasoning
behind each `RMn` the round produced.

## RM129 — `producer` described the document and was read as describing the checks

**Shipped in `just-dna-format` + `just-dna-enricher` on 2026-08-24**, a minor. `verification.json`
carried `producer` at the document level only, and `record_verification` refills it from
`producer_label()` on every write — so a merge that correctly **kept** an older run's record
restamped that record's attribution to the writing release. Reported against a module carrying a
0.6.4 `clinical_significance` record that came back attributed to 0.6.6.

**The reporter's argument is the item and it is an argument from the other fields.** Every field
describing *one piece of work* was already on the record — `source` (which authority answered),
`release` (which snapshot), `checked_at` (when) — and `producer`, naming *who ran it*, was the only
one on the document. Once the list is written out that way the asymmetry reads as an oversight rather
than a design, and the fix is where the field goes rather than what it says.

**`produced_at` stays on the document and is correct there**, which is the discriminator worth
keeping: it genuinely describes the file's last write, and so does `producer` **under its new
reading**. The two are now a pair meaning *what last wrote this file*, and the per-record field means
*who put this check*. `Verification.producer`'s own description had said *"Tool and version that put
the checks"* — the false claim, sitting in the printed contract where `describe`/`reference` render it
verbatim — and correcting it was part of the fix, not a follow-up (`@field-description-is-a-claim`).

**Three obligations a new field on a fact-hashed record owes, discharged rather than assumed.**
`producer` is outside `VERIFICATION_FACT_FIELDS` on exactly the reasoning that excluded `checked_at`
(*who* ran a check is a fact about the run, not about the module), so no published
`verification.signature` moved — asserted by a test rather than reasoned about. It is `str | None`
defaulting to `None`, so a record written before the field existed reads as *not recorded*; defaulting it to the
reading version would manufacture the false attribution the item is about, which is the tri-state rule
applied to a provenance field. And `merge_records` carries whole records, so the value travels with
no change to the merge — pinned by a test that hand-builds a 0.6.4 record, merges over it, and asserts
the old attribution survives.

**What was not changed: the merge.** The reporter went out of their way to record that
`merge_records` did the right thing — RM72's rule that a fresh *skip* does not displace an earlier
*answer* held, and nothing was lost. That mattered to the triage: a report framed as "the merge is
broken" would have aimed the repair at the one part that was correct.


# The 2026-08-21 output-contract round — what a patch may change about a compiled artifact

One report from a new consumer, just-dna-registry ([S62](CONSUMER_SUGGESTIONS_HISTORY.md)), and the
two items it produced are open in [ROADMAP.md](ROADMAP.md). What belongs here is **a framing that was
filed and then withdrawn the same day**, kept because the withdrawn version is the more tempting one
and will be re-proposed by anyone who reads only the measurement.

**RM127 was first filed as *the release-class table and the release practice disagree*.** The argument
ran: our table sizes a new optional column as a **minor**; `StudyRow.curator` shipped in **0.6.5**, a
patch, and the cut's own entry names it (*"Additive only: one new authored column"*); so the rule we
state and the rule we practise disagree and one of them must give. Three candidates were recorded —
the table is right and 0.6.5 was mis-sized; the practice is right and both documents should say *a
change that moves no authored identity may take a patch*; or split the axis so authored surface sizes
the release and derived surface does not.

**It was withdrawn because it indicts the wrong release.** `curator` is additive, no already-published
module can carry it, and **no stored value became wrong** — the only consequence is that a recompile
writes different bytes, which P4 already declines to guarantee across compiler versions. Sizing it as
a patch is defensible; the table calling it a minor is the table being strict, not the cut being
wrong. Chasing that disagreement would have produced a rule change that fixed nothing the consumer
reported.

**The defect is RM121, and it is a change class the taxonomy does not have** — an existing published
field whose *derivation was corrected*, so the same spec yields a different value. Neither additive nor
a removal/retype. And because a corrected derivation is a **bug fix**, deferring it to a minor means
knowingly serving a wrong value meanwhile, so no release-class scheme can carry it: the version number
answers *is the code contract compatible*, never *are your stored outputs stale*. The two axes have to
be separated rather than reconciled, which dissolves all three original candidates instead of choosing
among them. The rewritten entry is
[RM127](#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one).

**The lesson worth keeping is the tautology.** The safety argument for RM121 was *`content_signature`
is unchanged, measured* — true, and incapable of being false, because `stats` sits outside
`content_signature` by design. A check that cannot fail was read as a pass (`@tautology-zero`), one
level up from where that rule is usually applied. The same property has a second edge: a field outside
identity is a field no digest, no signature and no `revalidate` can see move, so **the cheapest changes
to make are exactly the ones with no detection channel.** Measured across 0.6.1→0.6.6: six of sixteen
reference examples changed a published, indexed manifest field with *both* hashes byte-identical.


## RM127 — a corrected derivation has no release class, and the version number is the wrong place to carry one

✅ **Severity** medium · **Status** **CLOSED 2026-08-21 — the charter was amended the same day it was
filed**, which is the whole item; filed, rewritten and answered within one pass · **Owner** maintainer
· **Motivating case** [S62](CONSUMER_SUGGESTIONS_HISTORY.md) (just-dna-registry)

**What shipped.** Principle 3 gained two rules — *Release class and artifact staleness are different
axes* and *Authored identity is not the sizing test* — and the charter gained a **Rules only** header
item plus Principle 9, the cost-by-layer pricing promoted out of an amendment entry where it had been
the only rule stated nowhere else. The reasoning moved to `CONSTITUTION_AMENDMENTS_HISTORY.md`, a new
file, and the charter came out **11.5% smaller while gaining three rules**. The obligation the
amendment creates — a release declares its corrections — is owed by
[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output),
queued for 0.7, and until it is built the charter names a channel that does not exist.

**This entry was first filed as *the release table and the practice disagree*, and that was aimed at
the wrong target.** The original framing indicted `StudyRow.curator` shipping in 0.6.5. It should not
have: `curator` is additive, no already-published module can carry it, no stored value became wrong,
and the only consequence is that a recompile writes different bytes — which P4 already declines to
guarantee across compiler versions. Sizing it as a patch is defensible, and the table calling it a
minor is the table being strict rather than the cut being wrong. The original text is preserved in
[the 2026-08-21 output-contract round](#the-2026-08-21-output-contract-round--what-a-patch-may-change-about-a-compiled-artifact).

**The real item is RM121, and it is a change class the taxonomy does not have.** `stats.genes` is an
*existing published field whose derivation was corrected* — the same spec now yields a different
value. Nothing was added, removed, promoted or retyped. The three rows we have are *additive → minor*,
*legibility → patch*, *removal/promotion/retype → major*, and a corrected derivation is in none of
them. It did not fall between two rules; it fell outside the list.

**Why it read as safe, and this is the mechanism.** The only test applied was *does authored identity
move?* But `stats` sits outside `content_signature` **by design** — it is a derived facet, not
content. So that test returns "safe" for *any* change to `stats` whatsoever, including replacing it
with nonsense. It cannot fail there. It was not evidence; it was a tautology, and `@tautology-zero` is
our own name for the shape — *a check that cannot fail must not report a zero*. RM123 shipped that
same week about compile checks; the identical error was made one level up, in the release-sizing
argument, where nothing was watching for it.

**And the structural half.** The property that makes a derived field cheap to change is the same
property that makes the change undetectable downstream. `stats` is outside identity, so changing it
costs nothing by the identity test *and* no digest, no signature and no `revalidate` can see it move.
**Measured: six of sixteen reference examples changed a published, indexed manifest field while both
hashes stayed byte-identical.** The cheapest changes to make are exactly the ones with no detection
channel, and the identity test rewards them.

**The version number cannot carry this, and the reason closes the original question rather than
answering it.** A corrected derivation is a **bug fix**. Deferring it to the next minor means
knowingly serving a wrong value for an undefined period, which is not a trade anybody should take —
so "make it a minor" is not available, and neither is any other scheme that encodes staleness in the
release class. SemVer answers *is the code contract compatible*; it was never designed to answer *are
your stored outputs stale*, and those are orthogonal. **They must be separated rather than reconciled**
— which dissolves this entry's original three candidates instead of picking one.

**What is left here is one charter question**, and it is the maintainer's: does P3's sentence — *"a new
optional column… lands in a minor: the authored identity is unchanged, and only a recompile's
`artifact.digest` moves"* — get amended to say that release class and artifact staleness are different
axes, with the second carried by the mechanism in
[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)? The sentence
currently states a ruling and, in the same breath, offers the identity test as its rationale — which
is exactly the reading that sized RM121, so leaving it unamended leaves the trap armed. Everything
else RM127 used to ask now belongs to RM126.


# The 2026-08-21 decision round — six undecided minors answered in one pass

[ROADMAP.md § Active items](ROADMAP.md#active-items) held six items whose common property was that
every one of them was a *decision* rather than a missing line of code, and none had been made. All six
were answered in a single pass on 2026-08-21. Four stayed open with their shape settled or narrowed and
are still in the active file (RM103's manifest half, RM108, RM110, RM117); **RM122** parked on demand
and moved to the minor-deferral file ([ROADMAP_0_8.md](ROADMAP_0_8.md) since the 0.7 cut); **RM103's refusal half** moved to
[ROADMAP § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker); and **RM102** closed
outright, which is why it is here.

**The finding worth keeping is about the queue rather than any item in it.** Two of the six were not
design-blocked at all. RM110's encoding was already pinned by a test on one of its two producers, so
nothing was undecided — it was parked because normalizing the other producer moves a fact signature
and the round that found it was a *patch* round, which is a release-class objection that reads, in a
status line, exactly like an open design question. RM102's was the mirror image: the entry argued two
candidate repairs at length and the thing nobody had written down was that **no incident had ever
followed from the behaviour**, which made "close it" a live option that had never been on the list.
Both cost more attention than they were worth, and the same question would have found both: *what
would a decision here actually change?*

## RM102 — the enricher loads a `.env` into `os.environ` from library paths

✖ **Closed 2026-08-21 as a decision not to act**, after the half of it that was a real defect had
already shipped. Motivating case [S39](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.
**Owner** enricher.

**What shipped, and it was the actual bug.** `load_dotenv_file=False` reached none of the six cache
resolvers: each passes its `default_*_cache_dir()` as an *argument*, and that helper went through a
`_cache_dir` whose `load_env()` was unconditional, so the file was loaded before the resolver looked at
its own flag. The knob did nothing at all. Threaded through `_cache_dir` and the six
`default_*_cache_dir` helpers in **0.6.3**, with `test_locations.py` running each resolver in a
subprocess and pinning both directions plus the pre-fix arrangement, and a twelfth test walking both
families so a seventh resolver cannot quietly reopen it. That is `@off-switch-needs-a-probe` and
`@registry-completeness` in one repair.

**What was filed and is now closed.** Everything the repair does not reach: `load_dotenv` writes the
*whole* file into `os.environ`, not the cache variables alone, and four credential paths — `net`,
`eutils`, `literature`, `pharmvar` — call `load_env()` with **no flag at all**, deliberately, because
a credential is loaded where it is read (`@credential-where-read`). So a caller passing `False`
everywhere still has the process environment mutated by the first network client they construct.

**Why it closed rather than shipping a fix.** The record holds exactly one incident, and it is not one:
S39's reporter lost about an hour to a test named `test_a_token_does_not_leak_between_sessions` failing
with *"The server is configured offline"* instead of its assertion, because their fixture had cleared
a variable with `monkeypatch.delenv` and `override=False` — which skips a variable that is
**present** — let the file refill it. The credential involved was their own, in their own process,
from their own `.env`; nothing crossed a boundary, no build shipped wrong data. Weighed against that:
both candidate repairs cost a full minor, and the better-looking one is **silent for every caller who
never passed the parameter**, so a deployment pointing its cache through `.env` alone simply stops
finding it — the exact "the cache is right there" report the unconditional load was added to end
(S14's shape: the addition being legal does not make the change legal).

**The two repairs, recorded so they are not re-proposed as if new.**

- *Flip the default and leave loading to the entry point.* Right shape — a CLI loading `.env` is
  ordinary, a library function doing it while answering "where is the cache" is not — but a bare flip
  is silent, so the honest route is warn-in-one-minor-then-flip, and it has to cover the four flagless
  credential paths too or it is an assurance that is not one.
- *Narrow it to the cache variables.* Rejected on its own terms: it makes the enricher a filter over
  somebody else's file, and the allowlist becomes a hand-kept list of every variable any tier might
  read — `@registry-completeness`, arriving as a design rather than as a bug. It also does not answer
  the reporter's actual complaint, which is about mutating the process environment at all.

**What stands as the answer for 0.x.** [ENRICHER.md](ENRICHER.md) § cache locations states that the
load writes into `os.environ`, that it is a library path rather than a CLI one, that `override=False`
skips a variable that is present so *deleting* one is what lets the file win, and names both the switch
and the flagless credential paths. That was the reporter's own fallback ask. Their defence — walking
`sys.modules` and replacing every bound `load_dotenv`, rather than patching `dotenv.load_dotenv`, since
every `from dotenv import load_dotenv` holds its own binding — is correct and stays correct.

**Reopen it if the record changes**, and the trigger is specific: something worse than a lost hour —
a credential reaching a subprocess, a crash report, or any boundary at all. The failure mode argues for
watching rather than for building, because it is **green in CI and different on every developer's
machine**, which is the shape that stays undiagnosed longest.


# The 2026-08-21 lookup round — a finding that contradicted the payload carrying it

## RM125 — a cache link answered a question only the caller could answer, and said the opposite

✅ **Shipped in `just-dna-enricher` on 2026-08-21**, motivating case
[S61](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

`lookup_variant(rsid="rs4988235")` returned the correct live coordinate `2:135851076` and, in the same
payload, a finding reading *"rs4988235: not in the injected Ensembl snapshot, position remains unset"*.
Both halves of one response, disagreeing about whether the lookup had succeeded.

**The reporter's framing is the item, and it is sharper than the row it is about.** Their consumer of
this surface is an agent, and the instruction it carries everywhere is to read findings rather than
trust a bare value — so a finding that contradicts the data does not merely mislead once, it teaches
the reader to discount findings, on a surface whose entire discipline is that `null` means unchecked
and a warning on a green run is the interesting output. They were explicit that the snapshot miss
itself should stay recorded, since knowing a local cache is incomplete is what tells an author whether
to warm it; the ask was only that the record stop asserting the position is unset.

**This is the ordinary three-valued failure wearing an unusual costume.** At the moment the cache link
speaks, whether the position remains unset is not false and not true — it is *unknown*, because a live
leg that has not run yet may still answer. The house rule is to withhold, and the link asserted
instead. The wording had already been half-corrected once, when it stopped saying "not in Ensembl" and
started naming the snapshot it had actually searched; that fix addressed the link speaking for its
**source** and left it speaking for the **rest of the run**.

**Three shapes were offered and the architecture picks one.** Dropping the warning on a live hit loses
the cache-warming signal the reporter wanted kept. Re-wording it at the emission site to *"resolved
live"* is not implementable there at all — the emitter runs before the live leg. What is left is their
third: the caller reconciles, *"since it is the function that knows both halves ran"*. Established
while probing, and it makes the choice cheaper than it looks: `enrich()` discards both links' warning
lists into `_`, so `lookup_variant` is the **only** reader either sentence has ever had. Each link now
reports what it searched and stops; `lookup_variant` states `"{rsid}: position remains unset"` once at
the end, guarded on there being an rsID, because a position-only lookup fills `rsid_candidates` and
never `loci` and would otherwise be told its own supplied position was unset.

**Widened past the report: the ClinVar twin had neither correction.** `clinvar.lookup_loci` is
documented as signature-identical to `resolver.lookup_loci` — *"one implementation, no drift"* — and
still emitted *"not found in ClinVar, position remains unset"*, speaking for the source exactly as the
Ensembl half had before it was fixed. Reachable in the same call, since the cache loop breaks only on a
hit, so a real run produced **two** false claims where the report scoped one. A pair described as one
implementation is still two strings, and only one of them was ever reviewed — the `@registry-completeness`
shape, arriving as a matched pair rather than a registry.

**Why a green suite held it.** Neither phrase was pinned by any test, and every existing `lookup_variant`
test passes an **empty** cache directory, so `resolve_*_reference` finds no snapshot and the per-rsID
miss line is never emitted at all. The defect lived on a line the fixtures could not reach. The new
tests build a populated snapshot that simply lacks the rsID under test — the reporter's own method,
running the tool against real rsIDs instead of reading it.

Severity was **already** `info` on this finding, which is worth recording because the reporter offered
"downgrade to `info`" as half of one candidate fix: the level was right and the sentence was wrong. A
**patch** — advisory findings are written nowhere, so no digest and no signature moves.


# The 2026-08-19 doc-audit patch round — six of the eight, fixed

The 2026-08-19 audit validated `just-module-creator`'s 24 per-table dossiers against this repo's code
and turned up eight code findings, filed as RM104–RM111 and none of them fixed at the time. Six were
sized as patches and are below. **The two that are not here are not oversights**: RM108 (a ClinGen
re-curation appends beside its predecessor) needs a currency notion decided before anything can be
written, and RM110 (`constraint_flags` has two producers with two encodings) moves
`gene_metrics.signature` for every module already carrying snapshot rows — legal, but a recompile the
ecosystem should be told about. Both stay open as minors in [ROADMAP.md](ROADMAP.md).

**What the six have in common is worth naming, because it is not "eight unrelated bugs".** Five of the
six are a *derived* value that had been restated by hand somewhere else — a suppression set restated
beside its merge key, an allowlist restated beside the extension set, a dupe key registered in the map
one loop reads and not the one that would have found it, a check re-run without the filter its
neighbour eleven lines away carries, a `Field` description restating an analogy that is true of a
different field. The sixth is the empty-work path nobody runs. None of them was visible to the suite,
which was green at 2859 tests throughout.

## RM104 — `enrich_gene_metrics` raised `UnboundLocalError` on the ordinary re-run

✅ **Shipped in `just-dna-enricher` on 2026-08-20**, from the 2026-08-19 doc audit
(just-module-creator's `gene_metrics.md`).

`reference` was bound only inside `if wanted:` and read unconditionally forty lines below as
`constraint_routes_consulted = reference is not None or not offline`. So both runs where `wanted` comes
back empty raised out of the pass: the **idempotent re-run**, where every gene already has a row, and
any module with **no `variants.csv`**. Reproduced on a scratch `hboc_palb2` at enricher 0.6.4, offline
and online, through the library and through the CLI.

**Worse than a crash, which is why it was the only `high` in the batch.** The pass is documented as
merge-not-clobber, so the re-run is the *supported* path, and RM101 built `GeneMetricsEnrichmentError`
precisely so a caller could wrap this pass in one `except`. An `UnboundLocalError` is outside that
contract, so every caller who followed RM101's advice was unprotected in exactly the case they were
told to expect.

One line — `reference: Path | None = None` before the branch, which is also the honest value, since
with nothing wanted no snapshot was resolved. **The test is the part that mattered.** Every existing
merge test re-runs with `wanted` non-empty, which is how a green suite never saw either path; the new
one runs the pass twice over a table it has already filled and once on a module that names no gene, and
fails with the original `UnboundLocalError` on the pre-fix tree. `@empty-work-is-a-path`.

## RM107 — a duplicate `(source, layer)` row compiled green under `--strict`

✅ **Shipped in `just-dna-compiler` on 2026-08-20**, from the 2026-08-19 doc audit
(just-module-creator's `licensing.md`).

`SourceRow` is keyed `(source, layer)` — `draft._CORE_DUPE_KEYS` refuses to append over it and
`licensing.merge_sources_csv` merges on it, so every other writer in the ecosystem already treated it as
the key. The compiler was the outlier. Measured on `hboc_palb2`: appending an exact copy of a row gave
`strict compile ok: True`, no warning of any kind, `row_count` 7, and a **moved** `source_signature`. A
duplicate carrying the *opposite* `commercial_use` also compiled green — and `licensing.csv` is the one
file the compile gate keys on, so which of the two rows the gate reads decides whether the module
compiles at all.

**The fix as filed would have done nothing, and that is the durable half.** `_TABLE_DUPE_KEYS[SourceRow]`
is only consulted by `_validate_table_kind`, which `validate_spec` called from its `_TABLE_KINDS` loop —
and `sources.csv` is a `_FACT_TABLES` member, so no loop would have reached the new entry. Writing the
red test first is what surfaced that: it failed on `valid=True` with the map entry already in place.
What shipped is the call site widened — the fact-table loop runs `_validate_table_kind` too, named by
the file actually read so either sidecar spelling reports itself — plus the map entry, plus `SourceRow`
moved *out* of `draft._CORE_DUPE_KEYS`, which had been carrying it only because the compiler had no key
for it. Parity comes free: `compile_module` runs `validate_spec` and returns its errors, so both
commands refuse with one sentence.

"Keyed kind ⇒ dupe-checked" was never the dividing line — which loop calls the checker was.
`@which-loop-calls-the-checker`.

**Checked while in there, since the item asked**: the map covers five of the nine authored kinds and the
other four are the binning kinds, whose duplicate rule is *overlap* rather than equality and which
`validate_bins` owns — so the authored side is complete. The remaining gap is the other fact tables,
which have no duplicate rule at all; RM109's own defect produced exactly such a pair and nothing
reported it. Not widened here: that is a tightening across every module carrying a fact sidecar, and it
wants its own item.

## RM109 — the gene-metrics fetch-suppression key was not derived from the merge key

✅ **Shipped in `just-dna-enricher` on 2026-08-20**, from the 2026-08-19 doc audit
(just-module-creator's `gene_metrics.md`).

The merge key is `(gene, dataset)`; the suppression set was
`{row.gene for row in existing.values() if (row.source or "").startswith("gnomad")}` — a proxy for the
key, and the two disagree exactly where it matters. A hand-written correction that honestly records
`source="manual"` did not mark its gene done, the fetch ran anyway, and the file came back with two rows
sharing `(gene, dataset)` and contradicting each other. `compile_module` emits zero warnings on that
(see RM107's closing note), so the manifest reports it as ordinary.

`done` now asks whether a row already sits under a key **this pass would write** — the gene plus one of
the two dataset labels it writes, one per route. Scoping to those two is the half worth keeping rather
than collapsing to the gene: a second authority's ClinGen dosage row carries a different `dataset`, is a
different key, and must not suppress this pass's fetch. That is the older bug in the other direction,
and it is why the key is a pair. `clingen.py`, the sibling pass in the same package, has always tested
`(gene, dataset) in existing`; the shape was understood and simply not applied here.

The general rule is the durable half and is now written down: **a suppression set must be derived from
the merge key, never restated beside it** — the same derive-don't-restate rule `@draft-appends` and
`@fieldnames-from-model` carry. `@suppression-from-merge-key`.

## RM106 — the `faf95` arithmetic warning was published twice

✅ **Shipped in `just-dna-compiler` on 2026-08-20**, from the 2026-08-19 doc audit
(just-module-creator's `frequencies.md`).

`_check_frequency_arithmetic` runs in `validate_spec` (added by RM93 for parity) and again in the
compile-side `_frequency_checks`, with no dedup — while `_literature_checks`, eleven lines below it,
*does* filter and says why in a comment. Measured on a doctored `hboc_palb2`: **15 warnings, 14
distinct**, the `faf95 … exceeds the group's own allele frequency` line appearing twice.
`manifest.compilation.warnings` is a published field (RM44), so the duplicate is published, and any
consumer counting warnings overstates what is wrong with the module.

Filtered on the message, the idiom the neighbour already uses. Only the warnings need it: validate's
errors abort the compile before that closure runs. Second instance of the shape after RM94, so the test
asserts the general property beside the specific one — `len(warnings) == len(set(warnings))` over the
whole published list — and fails `2 == 1` on the pre-fix tree. `@no-rerun-with-counts` grew the half it
was missing: the rule already said never re-run a check whose message embeds a count, and the countless
case still owes the filter.

## RM105 — `logo.jpeg` compiled, was attested, and was never uploaded

✅ **Shipped in `just-dna-enricher` on 2026-08-20**, from the 2026-08-19 doc audit
(just-module-creator's `logo.md`).

`manifest.LOGO_EXTENSIONS` is `{png, jpg, jpeg}` and `_collect_logo` iterates `sorted(...)`, so **`jpeg`
wins over `jpg` over `png`** — while `upload._ALLOW_PATTERNS` hand-spelled `logo.png` and `logo.jpg` and
not `logo.jpeg`. The result is a manifest attesting, by name and sha256, bytes the published repo does
not carry: the exact failure `@publisher-allowlist-derived` exists to prevent, in the one place the
allowlist was still hand-spelled. `verify_manifest(check_logo=True)` does not catch it either — an
absent file is not a failure there, so an attestation check that tolerates absence cannot stand in for
the publisher carrying the file.

The logo half now derives from `LOGO_EXTENSIONS`, the way the readme half already derives from
`README_CANDIDATES`. `_collect_logo`'s pick order is deliberately untouched: jpeg-winning is the fact
that made this visible, not the defect, and changing it would move published artifacts. The test asserts
**set equality** — a floor passes on the pre-fix tree, two of the three already being listed — and then
compiles a real example carrying a `logo.jpeg` to check that what the manifest attests is what the plan
sends.

**The process lesson is the one to keep.** This skew was named twice and owned by nobody: once in the
CHANGELOG entry that introduced the derived allowlist, and once in a code comment that deferred it
(*"a pre-existing instance of that same skew, left alone here because widening it is not this item's
decision"*). Deferring a neighbouring gap is fine; not filing it as an `RMn` in the same commit is how a
known defect survives two releases.

## RM111 — three shipped strings asserted a registry override of `license` that nothing performs

✅ **Shipped in `just-dna-format` + `just-dna-compiler` on 2026-08-20**, from the 2026-08-19 doc audit
(just-module-creator's `module_spec.md`).

`ModuleSpecConfig.license`'s description (*"Advisory and registry-overridable, exactly like
`module.version`: the marketplace stamps the canonical value on publish"*), the matching comment in the
compiler's manifest builder, and `manifest.py`'s own module docstring all stated that a publishing
registry overrides the authored `license`. Verified in the registry checkout: its publish path never
writes that field. `module.version` really is stamped, so the analogy the strings lean on is sound for
*version* and false for *license* — which is exactly how the claim survived review.

**Intent decided the way the item predicted, and the code already agreed with it**: a licence
declaration is the author's claim, and `_check_declared_license_agrees` compares it against the
annotation-layer sources and *warns in both modes* rather than replacing either — the opposite of
overriding it. So the strings were corrected, not the behaviour, and each now says what actually happens
and names `module.version` as the field that is genuinely stamped.

**Four sites, not three.** The item cited `normalize.py:40`; that line is the `IDENTITY_AUTHORITY_KEYS`
note, which is correct about the identity keys and says nothing about `license`. The real third and
fourth were `manifest.py`'s module docstring and `ModuleManifest.license`'s own description — so **two**
shipped `Field(description=…)` were involved, as the item said, and they reach authors through
`describe_table` / `authoring_reference`. `@field-description-is-a-claim`: an analogy inside a field
description is a claim a reader will act on, and it does not travel with the field.


# The RM10/RM11 session — a downstream MCP surface restated three schema facts it could not generate

Four items from `just-module-creator` on 2026-08-20, filed together because they came out of one work
item: their MCP tools had three answers that **restated** a schema fact instead of generating it, and
they went looking for the public symbol to generate each from. Two of the three had none — which is the
report, and it is the useful shape of it: a consumer who wants to generate rather than restate, blocked
by a private name, will hand-keep the same lines every other consumer hand-keeps and will be the one who
misses the next table. All four are additive or documentation; nothing removed, nothing retyped.

## RM123 — two attestations recorded a check whose scope they could not state

✅ **Shipped in `just-dna-compiler` + `just-dna-enricher` on 2026-08-20**, motivating case
[S59](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**The reporter's generalisation is the item, and it is a good one:** *a check that could not have
failed should record why rather than record a zero.* They filed three instances. Two reproduced, in
different tiers and with the same shape underneath; the third had shipped four releases earlier and is
answered as a non-issue in the reply, with what was probed.

### Half one — the PGx record lost a tautological leg whenever another leg answered

RM73 already built the skip they asked for: `pgx._tautology_note` is the ClinVar `tautology_reason`
conjunction one source over — the licence row must name **this** release *and* the drafter's digest
must still match — applied **per leg**, because PharmVar is an independent authority and a whole-record
skip would throw away a real comparison to suppress a hollow one. That has been in the tree since
0.6.0, and the reporter is running 0.6.4.

What it did not do is reach the file. `_function_check_record`'s **skip** branch joins every
non-answered leg's note into `detail`, so a tautology-only record already says so. The **answered**
branch built `detail` from `answered` alone, so the one case the per-leg design exists for — CPIC
tautological, PharmVar answering — published *"compared N authored allele function(s) against pharmvar
(…)"* and no trace at all that half the check was a copy against itself. `result.warnings` carried it,
which is the run's stderr; `verification.json` is what a later reader trusts, and the run is not part
of the module. Demonstrated by calling `_function_check_record` directly with a mixed `legs` dict —
its signature takes every number as a parameter, which is what made the demonstration a unit test
rather than a network pass.

Fixed by appending the withheld legs' notes to the answered branch, **sorted by source in both
branches**. That sort is not tidiness: `verification.json` is a hashed input, `legs` is filled in
whichever order the pass reached the authorities, and an iteration-order sentence is a file whose bytes
depend on which authority answered first.

### Half two — a redundancy-bearing advisory named a checker that cannot see the table

`hints.REDUNDANCY_BEARING` is keyed on a bare column name with no model attached, and
`_flag_advisory_columns` gated only on whether the *model* carries the column. `clin_sig` is authored
on `variants.csv`, on all four binning kinds and on `diplotypes.csv`, while `verify_clin_sig` takes
`list[VariantRow]`; `evidence_level` is on `diplotypes.csv` and `pharm_variants.csv`, and the ClinPGx
check loads `pharm_variants.csv` alone. So six (column, table) pairs printed *"filling it from that
same source would make the check vacuous"* about a check that never sees the table. **The advice stays
right and the reason was false**, which is the worse half of being wrong: it implies a green run is
evidence of agreement.

`REDUNDANCY_BEARING_TABLES` narrows the explanation, and the map's **absences are checked claims**.
`rsid`/`chrom`/`start`/`ref`/`alts` stay unscoped because resolution reaches the positional table kinds
and the PGx tables (RM43), so a coordinate on `heteroplasmy.csv` really is cross-examined; `pmid` stays
unscoped because RM47 made a bin a second citation site and `enricher.literature` reads both through
`binning_citations`. Both were nearly scoped from the checker-name strings alone, which would have
suppressed a **true** advisory — the same defect facing the other way, and the reason every entry and
every absence has a test.

**It scopes the explanation and not the refusal.** `REDUNDANCY_BEARING` is also the map a drafting
provider refuses on; whether a provider should start filling `clin_sig` on a binning row is a decision
nobody has taken, and taking it as a side effect of fixing a message is what this repo refuses. The
model→CSV direction is derived from `draft.DRAFTABLE` rather than listed, so a kind added later is
scoped by construction — and two names for one model is real (`SourceRow` answers to both spellings
since RM51), not a quirk to normalize away.

**A patch on both halves**: prose in a record that is outside the verification signature (`detail` is
excluded on purpose, so rewording never moves it), and an `info` finding's text. No schema moved, no
authored surface moved, nothing was retyped. Suite 2843 → 2859.

## RM121 — `manifest.stats` described one table and was published as if it described the module

✅ **Shipped in `just-dna-compiler` + `just-dna-format` on 2026-08-20**, motivating case
[S57](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**The reporter asked which of two things `stats` is, and said they had no preference between the two
answers — only a preference for knowing.** Either `stats.genes` describes the module, in which case
`variant_stats` was wrong to read one table, or it describes `variants.csv`, in which case the field is
honest and the registry's gene index is reading a variants-shaped number as a module-shaped one. **The
model had already answered**: `Stats`'s own docstring says *"card/detail stats derived from the spec"*,
and a spec is not a table of itself. So this is an unimplemented sentence rather than a design choice —
the same shape as RM113, where `describe_table` had promised a key since 0.5 and never carried one.

**Reproduced on the module they named.** `reference_examples/cyp2c19_star_alleles/` has no
`variants.csv` at all and publishes `gene_count: 0, genes: []` against **1,332 rows naming CYP2C19** —
106 in `haplotypes.csv` (the number they measured), 1,190 in `diplotypes.csv`, 36 in
`allele_function.csv`. Seven of the eight non-variant gene-bearing models make `gene` **required**, so
these are modules that know their genes exactly and published none of them. Seven of our own sixteen
reference examples carry no `variants.csv`.

**What made it ours rather than a documentation note is the workaround it forces.** They had already
written a guard into their skills against the obvious repair — adding an empty or invented
`variants.csv` to become discoverable — because `studies.csv` becomes required the moment `variants.csv`
exists, so the honest module is the undiscoverable one and the discoverable one is a fiction. A gap an
author can only close by writing something untrue is not a gap the author owns.

**Shipped as `module_stats` beside `variant_stats`, not as a rename.** `variant_stats` names which
table it reads, and renaming it would be a major on S14's rule — a rename is a removal plus an
addition, and the addition being legal does not make the rename legal. The two differ in exactly two
keys. `_GENE_BEARING_TABLE_KINDS` derives from `_TABLE_KINDS` by `"gene" in model.model_fields`, the
same one-liner `_POSITIONAL_TABLE_KINDS` uses, so a kind added later enters the union by construction:
the defect being fixed *is* a hand-scoped notion of which tables count, and closing it with a second
hand-kept list would have been the same defect wearing a fix's name.

**Derived sidecars are deliberately outside the union.** A gene reaches `gene_metrics.csv` because a
pass looked it up, not because the author said the module is about it, and `gene_metrics.genes` already
publishes that set one block down. The exclusion is structural rather than a filter — `_TABLE_KINDS`
holds authored kinds only, which is the line the 0.5 fact-table rework drew.

**One thing the fix moved that the report could not have seen.** The post-symbolic-drop re-derive lived
*inside* the loop's `variants.csv` branch, which was right while the stats read one table and became
wrong the moment they read nine: `pharm_variants.csv` is the other droppable kind and it carries a
`gene`, so a drop that removed the last row naming a gene would have left it in a published manifest —
the RM44 class of defect that branch was itself written against, recreated by the fix for it. Moved
after the loop and pinned with a two-row fixture where one row drops and one survives.

**A patch, and the check that says so.** `manifest.json` is not one of the hashed artifact files and
`content_signature` is over authored rows, so no `stats` value can move either identity; measured
byte-for-byte on the example above, both unchanged. Nothing was added to an authored schema and nothing
was retyped. `compiler/tests/test_module_stats.py` runs the real compile over the whole reference
corpus with the expected gene set computed from the CSVs at run time; six of its eight tests were
watched failing against the old behaviour before the fix was kept. Suite 2835 → 2843.

**What is not ours, and the reply says so.** The registry's gene index consuming this field is theirs;
what we owed was a field that means what it says. Documented in
[SCHEMAS.md § The output half](SCHEMAS.md#the-output-half--manifest-models) and on `Stats` itself.

## RM116 — `content_signature` returned only its hash, so anything finer restated the fold

✅ **Shipped in `just-dna-compiler` on 2026-08-20**, motivating case
[S53](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**The reporter is specifying the tool MODULE_LIFECYCLE §7 says nothing owns** — *what moved between two
versions of this module* — as a three-level ladder: one signature for whether the content moved,
per-table for where, per-row for what. Levels two and three need the rows `content_signature` hashes,
and it returned the digest alone, so the mapping had to be rebuilt outside against two private things.

**Both halves reproduced before the fix, on `reference_examples/hfe_hemochromatosis`.** Renaming
`sources.csv` to `licensing.csv` and then editing a `notice` cell in it both left `content_signature`
at `sha256:44ad4449…` — the reporter's own measured digest, to the character. And the fold: writing one
`curator` value on every variant row in one copy and the identical value under `defaults:` in another,
`compiler.content_signature` agreed across the pair (correct — RM37) while `integrity.content_signature`
over raw `load_csv_rows` output disagreed, reproducing their `sha256:0b8dd27c…` for the yaml copy.

**The roster half was a documentation defect and the fold half a correctness trap**, which is why the
two land differently. A caller *can* derive the roster publicly — `draft.DRAFTABLE` minus
`layout.SIDECAR_SPELLINGS` — but as the reporter says, that equality is a coincidence two files
maintain rather than a contract, and it breaks in the direction that hashes an extra table. The fold has
no public route at all, and its third line (`None if effective == model_default else effective`) is the
one whose omission produces a signature that *looks* fine.

**Shipped their candidate fix, `compiler.spec_tables(spec_dir) -> (tables, declared_build)`**, with
`content_signature` becoming `_content_signature(*spec_tables(spec_dir))` and no logic moving. Their
rejected alternative is rejected here for their reason: exporting `_TABLE_KINDS` and
`_resolve_spec_defaults` separately hands out three pieces that must be assembled in one order — load
with the declared build injected, fold, then hash — and one function returning the finished mapping
cannot be assembled wrongly. The `ValueError`-on-invalid-CSV contract carries over because one function
is now the other plus a hash, and a test pins that rather than trusting it.

**The documentation half shipped too, since they asked for it either way.** COMPILER.md's public-surface
entry now names which CSVs feed the hash, says the licensing table is outside it and why, and states the
fold with the measured consequence of omitting it.

**Guards.** Four in `compiler/tests/test_content_signature.py`, using the RM37 fixtures that already
model the measured pair: the digest rebuilt from `spec_tables` output over three specs, the fold
**demonstrated** rather than asserted (the raw build is shown to disagree in the same test that shows the
folded one does not), the licence table shown outside the roster in both directions including the
notice-cell edit, and the `ValueError` contract over both functions. 2813 → 2817.

## RM119 — a citation sidecar could contradict its own studies.csv, and the manifest turned it into a confident zero

✅ **Shipped in `just-dna-compiler` + `just-dna-format` on 2026-08-20**, motivating case
[S56](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**Two separable halves, both reproduced against our own tree.**

**The staleness half.** `aggression_anger/literature.csv` records `quotes_authored=0` on all three
rows while its `studies.csv` carries 69 quotes — 65 of them citing pmid 29500382, which is the row
reading zero. All four published modules are in that state, 3,668 quotes and not one counted. The
mechanism is ordinary and is nobody's bug: the literature pass ran while `provenance_quote` was still
empty, wrote what was true then, and the sidecar is merge-not-clobber so every later run keeps the old
row. The module compiles green with a sidecar contradicting the table beside it in the same directory.

**Why the compiler owes this.** Both files are loaded at the same moment and joined on `pmid`, and the
count is arithmetic over rows already in memory. `LITERATURE_FACT_FIELDS`' own comment gives, as the
reason `quotes_authored` is outside the fact hash, that it *"is derivable from `studies.csv`"* — which
is precisely the argument for recomputing it at compile rather than trusting the stored copy. Shipped
as `_check_quote_counter_is_current`, a warning naming both numbers per citation, aggregated to one
line. It reads both citation sites through `binning_citations` — walking `bin_rows` directly reaches
`DiplotypeRow`, which has no `pmid` column, and a suite failure caught that before it shipped.

**The manifest half, and it is the more interesting one.** `_literature_block`'s docstring is right and
its per-row guard works: `quotes_found` sums only non-null rows, because folding a null into zero would
report an unchecked quote as a missing one — *"the single most misleading thing this block could say"*.
What it cannot express is the total over rows that are **all** null: `sum(...)` over an empty selection
is `0`, `Literature.quotes_found` is `int` with `default=0`, and the exact sentence the docstring warns
against is what the block ends up saying one aggregation later. A published manifest read
`quotes_authored: 0, quotes_found: 0` for a module with 69 authored quotes and no fulltext ever
retrieved — indistinguishable from one where every quote was checked and missed.

**Shipped `Literature.quotes_unchecked`** rather than making the pair nullable, which was the
reporter's own preferred option and the right one: a reader needs three states — found, missed, never
asked — and `int | None` collapses the last two back into "no number". Additive, out of
`artifact.digest` like the rest of the block. The reporter's rejected candidate (treat `0` as `null`
when no `quote_source` is set) is rejected for their reason: it silences the report without making the
distinction visible, and guesses the author's intent from the absence of a second field.

Pinned by a pair that is identical on `(quotes_authored, quotes_found)` and separated only by the new
counter, which is the confusion the field exists to end.

## RM120 — the table where the attestation lives could not name its attributor

✅ **Shipped in `just-dna-format` + `just-dna-compiler` on 2026-08-20**, motivating case
[S55](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator — **a retraction of their own S11**.

**The reporter withdrew the argument they gave us for `ATTESTATION_BEARING`, and the withdrawal is
right.** S11 said a passage extracted from a fulltext a tool just fetched *"asserts a curator reading
that never occurred"*, and our own answer turned on the same hinge: *"nothing establishes a human ever
looked."* That sentence names the defect and it is not the one the refusal fixes. It is a **missing
attributor**, not an illegitimate reader — the machine does read the article, so the reading is real
and what the rule protected was a fiction about *who* did it. The column then stayed empty for the only
reader actually present.

**The evidence that this is not academic is RM118.** The refusal did not produce human-located
passages; it produced 3,668 rows of title-as-quote in four published modules with the check green.

**Our own model already disagreed with the argument, in two places the reporter found.**
`Defaults.curator` defaults to the literal `ai-module-creator` — an AI curator is the documented
default for every row rather than an edge case — and `Contribution` carries the whole vocabulary for
saying who did what, with `who` reading *"a name, handle, or model id"* and `kind` laddering
`{human, human_expert, human_certified}` against `{ai}`. `attestation_bearing` was the one place that
then refused the AI contributor a cell.

**Shipped `StudyRow.curator`**, the same field `VariantRow` has had all along, on the table where the
attestation lives. The asymmetry it closes is the reporter's: a variant row could name who decided it
while a quote could not name who located it, though the quote is the attestation of the two. Free text
resolvable against `authorship`, never a `machine_located: bool` — two-valued collapses *an agent found
it and a human confirmed it* into one of two lies and cannot name which agent or which human. It
records the distribution of labour so a reviewer can route scrutiny; it does not move responsibility,
which the human author holds regardless.

**`ATTESTATION_BEARING` is unchanged and stays right for our layer**, which is the reporter's own
reading. A provider still must not fill the quote; what changed is that an author who *does* locate a
passage now has somewhere to say so.

**The interesting half is what wiring it found: `@three-touch-points` undercounts for this writer.**
`_write_studies_csv` names its columns in a `fieldnames` list **and** fills a row dict, and naming a
column in the first but not the second writes the *header* with an empty cell on every row —
`DictWriter` fills a missing key silently. The reversed spec looked right and re-validated, and the
value was gone; only the digest fixed-point assertion caught it. The comment on that list now says so,
and a behavioural guard fills every authored `StudyRow` column and asserts each survives the reverse,
derived from the model so a column added later cannot quietly fall outside it. Both guards were shown
to fail on the buggy code before being kept. 2830 → 2833.

## RM118 — `quotes_found` could not fail on a title, and four published modules are titles

✅ **Shipped in `just-dna-enricher` on 2026-08-20**, motivating case
[S54](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**Measured against our own tree and reproduced here in full.** Four published `antonkulaga/*` modules
carry a `provenance_quote` on every studies row — 3,668 of them — and **exactly one distinct quote per
PMID**: `cognitive_intelligence` 2045 rows / 33 PMIDs / 33 quotes, `risk_impulsivity` 695/19/19,
`big_five_personality` 859/26/26, `aggression_anger` 69/3/3. A passage located for a claim varies row
to row, because different rows cite the same paper for different findings; one string per paper is
structurally a property of the *article*. It is the title, verbatim including the trailing period.

**Why this is a check defect and not only an authoring one.** A title appears in its own fulltext, so
`_study_quote_found` matches, `quotes_found` equals `quotes_authored`, and the module publishes full
quote coverage while establishing nothing about whether any claim is in any paper. The check is
satisfiable from `esummary` metadata without retrieving a word of the article — which is the one thing
the column exists to witness. The reporter's sharpest line is that this is *worse* than the failure S11
was written to prevent: their own ask refused a machine-located passage, and what the refusal produced
instead was a machine-copied title with the check agreeing.

**The discriminator has to be the metadata**, which is the reporter's argument and it is right. A
minimum length does not separate a title from a passage (seventeen words is an ordinary title and an
ordinary sentence), and requiring a `provenance_regex` is no help because a regex is as copyable as a
quote. `CitationHint.title` shipped for S12 and arrives in the same `esummary` response that answers
existence, so the comparison costs no request — and it therefore answers for a **paywalled** article
too, which is exactly where `quotes_found` stays null and a reader has nothing else.

**Shipped** `LiteratureResult.titles_as_quotes` plus a yellow CLI line, warning-only and never an exit
code: whether a title is an acceptable locator is the author's call, and what the tool can honestly say
is that `quotes_found` is not evidence here. Two deliberate narrownesses — normalisation is case,
whitespace and a trailing period and **nothing more**, since a quote *containing* the title is a real
quote of a paper that names itself; and the report fires only when **every** quote for a citation is
the title, since a mixed citation has an author doing the work.

**The reporter corrected their own report mid-triage, and the correction was load-bearing.** They
measured the four modules' actual `literature.csv` and found `quotes_authored=0` with `quotes_found`
empty on every row: the quote check had **never run** on any of the 3,668, because the sidecar was
written before the quotes existed and is merge-not-clobber. So `quotes_found` never equalled
`quotes_authored`, and — the part that matters here — a pinned row is not in `wanted`, so a check
living in the fetch loop would have fired on none of them. Confirmed against the code and then against
a test that fails on the first version. The summary is now fetched for **any cited PMID carrying a
quote**, pinned or not, and the comparison runs over the merged ones too; `esummary` batches, so it
costs no extra round trip in the common case. Their other two consequences are RM119.

**One correction to the report, and it came from a failing test rather than from reading.** The claim
that a title always appears in its own fulltext is *nearly* true: esummary gives the title with a
trailing period, PMC5753237's JATS body carries it without, and `quote_matches` does not strip one, so
that exact pair misses. The substance is unaffected — the miss is punctuation, not evidence — and both
states are pinned: the finding fires either way, and a module whose two spellings agree gets the green
check the report describes.

## RM115 — a derived sidecar's merge key lived inside the pass that writes it

✅ **Shipped in `just-dna-format` + `just-dna-compiler` + `just-dna-enricher` on 2026-08-20**,
motivating case [S51](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**RM113's question, asked of the machine-produced tables, where the answer was one step further away.**
For an authored kind the key at least existed as a lambda in `_TABLE_DUPE_KEYS`; for a fact sidecar it
existed only as a dict-key expression in the body of the pass that writes it — `existing[(row.gene,
row.dataset)] = row` and seven more like it. `key_fields` already routed derived names through
`derived_model_for` after RM113, so it *would* have answered; the seven models simply declared no key
and it correctly withheld. What shipped is the declarations, plus the half that keeps them honest.

**The reporter's approximation, and why "safe" was not "right".** They derived the subject as the
required members of the fact-field tuple — public pydantic over a public tuple, so it could not silently
drift — and it agreed on five of eight tables. It was coarse on two, and those two are exactly the
tables where one subject legitimately carries several rows: `gene_validity.csv` came out `(gene,
dataset)`, dropping `disease_id`, and `clinical_assertions.csv` came out `(variant_key, dataset)`,
dropping `variation_id`. Coarse is the safe direction for their tool — it reports more rows as ambiguous
and auto-repairs fewer — but it demotes a gene's second real disease assertion into an ambiguity a human
has to adjudicate, on the one table where a gene legitimately carries several. Both reproduced here
before the fix, against the published `*_FACT_FIELDS` tuples.

**Two shapes the obvious design could not express, and both would have been wrong answers rather than
coarse ones.** `resolution.csv`'s key is not a uniqueness constraint at all: one rsID resolves to several
loci, `locus_index` orders them, and the pass replaces the group whole — so `KEY_RULES` gains a third
member, `subject`, and reporting `equality` there would tell a consumer a legal one-to-many file is a
duplicate. And `gene_validity.csv`'s key has **two levels** — the source's own `assertion_id` where it
published one, the gene's grain where it did not — so `TableKey` gains `fallback`, tagged `"id"`/`"grain"`
so a grain tuple can never collide with an id that happens to equal it.

**Shipped.** Seven models declare `_KEY_FIELDS` (`ResolutionRow` also `_KEY_RULE`, `GeneValidityRow`
also `_KEY_FALLBACK_FIELDS`); `base.merge_key(row)` is the row-level answer; `TableKey` carries
`fallback` and `KEY_RULES` carries `subject`; `describe_table`'s `key` block carries `fallback` too.
**Every pass now keys its `existing` map through `merge_key`** — `enrich`, `enrich_frequencies`,
`enrich_gene_metrics`, the ClinGen dosage pass, `enrich_literature`, `enrich_gwas`,
`enrich_gene_validity`, `enrich_clinical_assertions` — which is the half that makes the pass and the
surface unable to disagree, rather than merely agreeing today.

**The rewire found three live restatements of the same fact, and one was a latent break.** Keying the
map off a declared tuple immediately mismatched three *lookup* sites that rebuilt the key positionally:
`covered_keys = {key for key, _population in existing}`, `if (gene, dataset) in existing`, and
`pmid not in existing` — the last of which would have refetched every cited article on every run once
the dict held tuples. All three now read the attribute off the row instead of unpacking a key, which is
the shape that cannot break again when a member is added. That is `@dont-discard-computed`'s neighbour:
a key derived in one place and re-derived positionally in another is the same defect as a hand-kept list.

**Guards.** `enricher/tests/test_merge_keys.py` — the two-level key run rather than read, the `not_found`
row keying apart from every record for its allele, the `subject` rule shown over several loci sharing a
key, every published column asserted to be a real field of the model it keys (both levels), a fallback
declared under a required primary rejected as unreachable, and every published key deduplicating the
real sidecars the reference examples carry. Two existing tests changed meaning rather than being
deleted: the withhold is now shown against a model with no `_KEY_FIELDS` instead of against tables that
have since grown one, and the rule-membership equality walks the derived registry too. 2799 → 2813.

## RM113 — a table kind's natural-key *columns* were not obtainable, only its key *values*

✅ **Shipped in `just-dna-compiler` + `just-dna-format` on 2026-08-20**, motivating case
[S48](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**What was wrong, and it had already cost a consumer.** `draft.natural_key` answers per **row**,
returning a tuple of *values*, so a tool holding only a table name could not ask which columns those
values came from; `_TABLE_DUPE_KEYS` was private *and* held lambdas, so even reaching in yielded no
column names out of `lambda r: (r.gene, r.allele)`. Every consumer wanting the columns therefore
hand-kept a string — and the reporter's went stale the day 0.6 landed: their surface was telling authors
to key `copynumbers.csv` on `modifier_cn`, whose own description reads *DEPRECATED since 0.6, removed at
1.0*. Reproduced here: the description does say exactly that.

**A promise was already outstanding.** `hints.describe_table`'s docstring has advertised *"the natural
key two rows are the same row by"* since 0.5, and the returned dict never carried it. So this was not a
feature request but an unimplemented sentence, which is why the dict is where it landed.

**The fix that would have been wrong.** Filtering `_KEY_FIELDS` through `model_fields` — which is what
the compiler's own grounding-remedy sentence does, correctly, for a remedy. `CopyNumberRow` keys on
`effective_modifier_copy_number`, a *property* over two columns, so the filter **silently drops the
modifier axis** and the answer becomes "two rows differing only in modifier dosage are the same row."
A wrong answer whose drop is invisible is worse than a refusal, so a derived member is mapped back to
the authored column it coalesces instead — and to the **preferred** spelling, so this surface can never
hand an author the deprecated half of a pair.

**Shipped.** `hints.key_fields(csv_name) -> TableKey | None`, plus the `key` block in
`describe_table`. `TableKey` carries `columns` (author's spelling), `rule`
(`equality`/`overlap`, a `frozenset` vocabulary per Principle 6) and `stamped` (members the compiler
fills, so `variant_key` is named as part of the key but never presented as a fillable cell). `None` for
a kind with no declared key — withheld, not invented.

**The structural half, and the reason this touched the schema tier.** The columns and the key were two
statements of one fact, so eight models now **declare** `_KEY_FIELDS` and both `_TABLE_DUPE_KEYS` and
`_CORE_DUPE_KEYS` are **derived from it** through one `_key_of`. One source of truth: `key_fields` and
`natural_key` cannot disagree, and a test pins them against each other over real authored rows from
`reference_examples/cyp2c19_star_alleles`. The whole suite passing unchanged (2784) is the evidence that
the derivation reproduces every lambda it replaced, including the PGx dedup keys each earned by real
ClinPGx data.

**What the tests found that the design had not.** `variant_key` is a stamped **field** on `VariantRow`,
`HaplotypeRow` and `PharmVariantRow` but a **property** on `StudyRow`. The first guard written asserted
every key column is a `model_fields` member and failed on `studies.csv` — correctly. The invariant worth
pinning is the weaker, truer one: a key member is either an authored column or flagged in `stamped`,
never a bare name resolving to nothing. Two further guards keep the class closed rather than the
instance: no key column on any kind carries a `DEPRECATED` description, and every rule is a declared
vocabulary member.

## RM114 — the scaffold pulled `variants.csv` in behind `studies.csv`, which RM47 made wrong

✅ **Shipped in `just-dna-compiler` on 2026-08-20**, motivating case
[S49](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**What was wrong.** `COMPANION_KINDS["studies.csv"] == ("variants.csv",)` was applied
unconditionally, so `scaffold_module(kinds=["copynumbers.csv", "studies.csv"])` warned that
`variants.csv` was owed and wrote a stub for it — inviting an empty table into a module whose author was
doing the right thing. **RM47 is what made this wrong**: a study row is legal with no variant identity
precisely so a binning module can ground its thresholds through `pmid`, and that is the *intended*
shape. Reproduced both halves — the scaffold really does create the stub, and the resulting
`copynumbers.csv` + `studies.csv` module really does compile **strict-green**, three warnings, none of
them about `variants.csv`.

**The comment was already right.** Its own justification said `studies.csv` *alone* fails with "module
has no recognized table" — true when literally alone, false beside a binning table. So the defect was
that the condition the comment described was never applied, which is why the repair is the comment's own
wording rather than a new rule.

**Shipped.** `scaffold.companions_for(kinds)`, public, applying the condition and used by
`scaffold_module` itself. `studies.csv` pulls `variants.csv` only when no other recognised table was
requested; `variants.csv` still pulls `studies.csv` **unconditionally**, because that direction has no
condition — the compiler wants grounding evidence for a variant claim however the module is composed.
The recognised set is derived from the compiler's own `_TABLE_KIND_CSVS` plus `variants.csv`, mirroring
`if not has_variants and not kind_row_counts` exactly, so a table kind added later counts without an
edit. `sources.csv` is deliberately outside it: a licence ledger is not a table a module can consist of.

**`COMPANION_KINDS` itself is unchanged**, and that is deliberate rather than incidental — the mapping
states a real pair, and a consumer reading it is not wrong about the pair, only about its
unconditionality. The reporter passes the constant through rather than restating it, which was the right
instinct and is why the accessor is public: an internal-only fix would have left their surface giving the
old answer while ours gave the new one.

**Rejected candidate**, the reporter's own blunter option: drop that direction of the pair and let the
"no recognized table" error speak for itself. It loses the help in the one case the pair was added for —
`studies.csv` truly alone — which a test now pins.

## RM112 — the machine-produced tables have no public `csv -> row model` resolver

✅ **Shipped in `just-dna-compiler` on 2026-08-20**, motivating case
[S47](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**What was missing.** `draft.model_for` answers for authored kinds and refuses everything else by
design, so a tool asked *"what is in `frequencies.csv`"* — or `resolution.csv`, files an author must
read and must never hand-finish — got `'resolution.csv' is not an authored table of this format`. True,
and useless. The only complete map was `compiler._FACT_TABLES`, private and free to move in a patch.

**Why the four obvious substitutes do not work**, each checked rather than assumed: `hints.model_for`
and `draft.DRAFTABLE` are authored-only; `just_dna_registry.specfiles.FACT_CSVS` is public but is
**names only**, and lives in another package, so a registry release lagging a compiler release makes the
answer lag too; `ARTIFACT_PARQUETS - LEAD_PARQUETS` does not isolate them — measured at **nine** names
against seven fact tables, because `annotations.parquet` and `studies.parquet` are in neither set; and
`authoring_reference()["models"]` is keyed by **model name**, so it answers "what columns does
`GeneValidityRow` have" and cannot answer "which model is `gene_validity.csv`" — which is the direction a
tool caller holding a filename actually needs.

**Shipped.** `hints.DERIVED_TABLE_MODELS` plus `hints.derived_model_for(csv_name)`, the read-only
counterpart to `draft.model_for`. **Derived from `_FACT_TABLES`, never restated** — re-introducing a
hand-kept map in order to publish one would be the defect wearing a public name — with a test asserting
set equality over the walked set, so an eighth fact table fails CI instead of becoming undescribable.
Both spellings of the licence table are keys, exactly as `DRAFTABLE` does it and for the same reason
(`@sidecar-name-and-place`); `sources.csv` is deliberately in both maps, being the one fact table a human
legitimately writes. `verification.json` is excluded: it is the attestation document, not a fact table.
Asking it for an authored name raises with the route that *does* answer — `@specific-rejection`, since
"not machine-produced" is a dead end where "use `model_for`" is a fix.

**What was not done.** `describe_table` still refuses non-authored names. Widening it was tempting and
rejected: a caller today can rely on that refusal, and the reporter had already built the second
read-only route themselves — the missing piece was the map, not the presentation.

# 0.6.2 — the enricher's exception contract, one layer up from RM97

One item, and the first in a while to arrive from the consumer inbox rather than from a doc pass.
**A partial cut**: only `just-dna-enricher` moved, so `just-dna-format` and `just-dna-compiler` stay
at `0.6.1`. The additions are minor-legal — new public names beside the old, nothing removed or
retyped — so the patch number carries them without straining P3.

## RM101 — a pass raises its client's exception type, which its own documented type does not cover

✅ **Shipped in `just-dna-enricher` 0.6.2 on 2026-08-18**, motivating case
[S37](CONSUMER_SUGGESTIONS_HISTORY.md) from just-dna-registry. `@client-exception-contract`, one layer
up from where RM97 left it.

**What was wrong.** RM97 made each *client* raise its own type instead of `httpx`'s. A consumer does
not call a client — they call a **pass**, and the pass's docstring and the CLI handler beside it both
name the pass's type. Five call sites held a client in `try: … finally: close()` with **no `except`**,
so `GnomadError` walked out of `enrich_frequencies` and `enrich_gene_metrics`, and `EutilsError` out
of `enrich_literature` and `check_rsids`. A handler written as
`except FrequencyEnrichmentError` was silent for exactly the failure it was written for.

**It was not only a consumer's problem, and that is what sized the item.** `just-dna-enricher`'s own
`frequencies` command promises `FREQUENCIES FAILED: <reason>` and exit 1; measured on a gnomAD 503 it
printed **nothing at all** and let the exception out. The printed contract was false on the path it
existed for.

**Three of the six sites were reported; three were found by walking.** The report named
`frequencies`, `literature` and the `clingen` conflation. Walking every pass that takes an injected
client added `gene_metrics` and both `identifiers` sites, and walking the *clients* found
`OntologyClient` still leaking a raw `httpx.HTTPStatusError` from both of its methods — a full release
after RM97 declared that class of defect closed. **RM97's own coverage guard is why it survived**: it
walked a hand-written tuple of eight module names and `identifiers` was not one of them.
`@registry-completeness`, in the guard whose job was to prevent exactly this. Both guards now discover
by `pkgutil` walk — one by "owns an `httpx` transport", the other by signature — so a new client or
pass fails the suite by name until it is covered or explicitly exempted.

**The leak was load-bearing in two places, which is the trap worth carrying.** Repairing a client
without grepping for handlers that catch the *leaked* type turns working behaviour off silently. Two
handlers here did exactly that: `cli.py`'s `check-identifiers` caught `httpx.HTTPError` to attest
`unreachable` — on the run its own test calls *"the run where the record matters most is the one with
no report to print"* — and `enrich()` caught `EutilsError` under *"a dbSNP outage does not sink a
finished enrichment"*. Both only ever fired because of the defect. The second was caught by its test;
the first would have been a silent loss of an attestation.

**Why a subclass and not the obvious translation.** `FrequencyUnavailable(FrequencyEnrichmentError)`
and five siblings, after `AcmgListUnavailable`. The reporter proposed flat translation
(`raise FrequencyEnrichmentError(...) from exc`) **and then argued against it themselves**, correctly:
it flattens "your input is wrong" and "the source is down" when every pass here used one type for
both. There is a second reason they did not give, and it is the stronger one — *they had already
compensated* by catching the client's type, so a flat repair would have broken the consumer who filed
the item. A subclass keeps every `except <Pass>Error` working (P3) and makes the narrow catch new
capability rather than a migration. The client's error stays on `__cause__`.

**The conflation half, and its unreported twin.** `ClinGenError` covered "could not fetch the curation
list" *and* "your local `gene_metrics.csv` will not parse" — opposite histories, separable only by
reading `exc.__cause__`. `gene_validity.py` had the identical pair at lines 369 and 437 and nobody had
reported it. Both now raise the `*Unavailable` subclass on the fetch path only. Matching the message
was the alternative and is worse: neither string is in the pinned warning-text catalogue, so a reword
would silently flip a consumer's verdict from "unchecked" to "your table is broken".

**Deliberately untouched.** `enrich_gwas` (client and pass share `GwasError`, so nothing is foreign),
`enrich()` and `enrich_pgx` (both **degrade** rather than raise — the tri-state withhold, which is the
right shape where work worth keeping has already been produced), `Grch37Client` (returns `None`/`[]`
on every transport path and raises nothing), and the two snapshot builders plus `pgx_draft.draft_gene`,
whose callers correctly enumerate the several types they can see. That last group is the *list* shape
the report objected to and RM96 is the lesson for — a real question, wider than this item, and named
in the guard's exemption block rather than left to be rediscovered.

Tests: `enricher/tests/test_pass_exception_contract.py` (new — walks the passes, drives both histories
for the two conflated modules) and the rewritten guard in `test_client_exception_contract.py`. Each
repair was demonstrated failing on the unrepaired code before being asserted.

# 0.6.1 — the eight the documents caught, the two the fixes found, and RM88

**A documentation pass regenerated SCHEMAS/COMPILER/ENRICHER from the source alone on 2026-08-18, read
the result against the shipped documents, and asked which of the two was wrong.** Eight times it was
the code. **RM88 rode along**, closed the same day and for a related reason — detailing it showed the
technical blocker it had been carrying was mispriced, leaving a policy question that took one decision
— and its own entry below carries the half that shipped as an ask rather than a fix. Everything else: no schema surface moves, `schema_version` stays `"1.0"`,
and all sixteen reference examples recompile byte-identical — verified against a worktree at `5c1ea87`,
the state before the first fix, rather than assumed from the absence of a model change.

**Every one of the eight broke a rule this repo had already written down**, and in four of them the
file carrying the violation also carried the rule, sometimes in an adjacent comment: `@validate-refuses-all`,
`@vocab-separator-slip`, `@registry-completeness`, `@client-exception-contract`, `@unreachable-not-absent`,
`@sidecar-name-and-place`, `@credential-where-read`. **That is the finding underneath the eight, and it
is the one worth keeping: the gotcha book is not the thing that catches a regression.** So the durable
half of every item below is a *test*, and in six of the nine that test walks a registry rather than a
list — the `@registry-completeness` shape turned on the guards themselves.

**Five of them were found by the same failure mode, at five different scales**, which is the second
thing worth recording. A hand-kept list stands in for a registry, and then the list is only as complete
as whoever last remembered it: `_ALL_MODELS` missing five row models (RM96), `test_validate_agrees_with_compile`
missing four of the seven fact tables (RM93), `net.py`'s "nine policies" against a tree of twelve
(RM100), the sidecar resolver three passes did not call (RM99), and the client contract two of four
clients honoured (RM97). None of these is a hard bug in a clever place. All five are a number or a list
somebody had to remember.

**What the items said and what was actually there differed five times**, and the differences are folded
into the entries below rather than left as a filing to reconcile. Four made the item bigger — RM93's
guard was missing four fact tables and not one, RM96's registry was missing five models and not three,
RM99 had five more sites in the CLI's own reporting, RM100 stranded a fourth command — and one made a
claim right for a different reason than stated (RM98's `SourceRow`, which follows from `authority`
rather than from `source`). RM100 also grew a fifth defect on 2026-08-18, after four of them had
shipped.

**One consumer-visible surface grows, deliberately and with the trade stated** (RM96): `authoring_reference()`,
`describe`, `requirements` and `json_schemas()` now render 28 models where they rendered 23. That is
additive under Principle 3 and buys guards that cannot miss a model again, which is the trade — a wider
printed reference in exchange for a registry that iterates itself.

The suite went **2568 → 2722**. Every new regression test was demonstrated failing on the pre-fix tree
before being claimed as a guard.

## RM88 — republishing without bumping `version:` overwrites a versioned path with different bytes

✅ **Shipped in `just-dna-enricher` 0.6.1.** [RM84](ROADMAP_0_8.md#rm84--a-module-has-no-version-identity-on-the-discovery-path-and-the-publisher-is-the-half-we-own)
built the versioned path `data/<name>/v<version>/` and it did exactly what it said. What it could not
do was notice that the version had *not* moved: an author who recompiled a changed module and
republished without editing `version:` overwrote the versioned copy with different bytes, and the path
then named a version whose contents were not the ones that version had. The same lie the flat path
already tells, arriving at the address built to stop telling it — which is why it was worth an entry
rather than a shrug, and also why it was never a defect in RM84.

**The delay was the policy, and the entry's own accounting of the other half was wrong.** It named a
remote read as the first of two blockers, pricing it against "a path whose current cost is one
`upload_folder`". The real cost is `create_repo` plus **two** `upload_folder` calls, in the one tier
permitted to fetch, so one more read was always marginal — the entry's closing line had already
conceded as much ("the check is cheap once the policy is chosen"). Corrected while detailing it on
2026-08-18, which is what left the product question alone as the blocker.

**Refuse unless `--force`**, decided 2026-08-18, over warn-and-proceed and refuse-outright. The flag's
existence is itself the claim that overwriting is sometimes right, and that is the honest position: a
curator re-cutting a draft release is a real workflow, and a gate with no override becomes a gate
people route around.

**Four outcomes, and the third is the one that decided the shape.** No versioned path (the module
states no version) — nothing addressable to collide with. The path is absent — the first publish of
this version, one `file_exists` and no download. **Present with the same digest — proceed**, because
`upload_module` writes two commits and documents a re-run as the recovery when the second fails, so a
gate keying on *presence* would refuse exactly the retry the design depends on. Present with a
different digest — refuse. `artifact.digest` is the comparator because it is a Merkle root over
exactly the attested files, so one small manifest read answers the question a tree listing could only
answer for whatever happens to be LFS-backed.

**It fails open, deliberately.** If the published manifest cannot be read, nothing established a
collision, so nothing asserts one — the house algebra withholds, and the publish proceeds with a
warning. Failing closed would make every network flake demand `--force`, training an author to pass it
by default and turning the gate into one people route around, which is the exact failure the policy
was chosen to avoid. It must not come back through the error path.

**A recompile under a newer compiler trips it, and that is correct rather than a false positive.** P4
scopes byte-reproducibility to a fixed `compiler_version`, so the versioned path really would come to
hold different bytes than the ones it was published with. The refusal says so in its own text, because
*"but I changed nothing"* is the first thing its first user will think.

**Not a repair, and still refused:** making the compiler bump `version:` automatically. A version is an
authored claim about compatibility, and a tool that increments it asserts something only the author
knows — the same move the repo already refused for `SourceRow.dataset` in RM85.

### The half that shipped as an ask instead of a fix

**`upload_folder` adds and replaces; it never removes.** Found while detailing this entry, wider than
the filed defect, and verified off the API contract rather than a live publish. A recompile that stops
emitting a table leaves the previous release's parquet at the path beside a manifest that does not
attest it — so a republish leaves a **union of two releases**, on the **flat path, every time**,
version bumped or not.

**The format's answer is that this does not matter**, and it is the right reading:
`manifest.artifact.files` states which parquets *are* the module, `artifact.digest` is a Merkle root
over exactly those, and an unattested leftover is outside both. A manifest-first reader never sees one
and verification passes, because nothing was corrupted. On that reading the leftover is an inert fossil.

**What stops it being true is the reader**, which
[MODULE_LIFECYCLE § 6.8](MODULE_LIFECYCLE.md#68-what-a-consumer-sees-when-v2-lands) already records,
verified in the consumer's tree rather than inferred: the discovery path adds *"no manifest fetch and
no digest check"*, `verify_manifest` *"has no call sites there"*, and the scan is `fs.ls` at one level
plus `fs.exists` on **named files**. Registry path: inert. Discovery path: a leftover parquet is
indistinguishable from a live one. The concrete failure is a **shape misreport, not corruption**, and
it needs two things at once — a module whose table set *shrank*, read over discovery. A SNP-core module
re-authored as table-only keeps a fossil `weights.parquet` and still probes as a SNP core.

**`delete_patterns` was considered and declined**, which is the part worth recording because it is the
obvious repair:

- **It leaves the nested `v<version>/` archive alone today, and by accident.** HuggingFace filters
  delete patterns with `fnmatch`, whose `*` **crosses path separators** — their own docs warn about it
  — and every member of `_ALLOW_PATTERNS` is a literal basename, so `manifest.json` does not match
  `v1.0.0/manifest.json`. Add one `*.parquet`, a completely reasonable tidy-up of a 28-entry list, and
  a single publish deletes every archived version's parquets. `_SNAPSHOT_ALLOW_PATTERNS` already
  carries two globs, on a path with no nesting, so the habit exists.
- **It would not close the case anyway.** Only a republish cleans a fossil, so every module nobody
  republishes keeps its own; and it does nothing at all for a consumer that probes filenames rather
  than reading the manifest.

A fix whose safety rests on an accident, and which does not close the case, is the wrong half of the
answer. **The right half is the reader**, so it shipped as an explicit ask in
[INTEGRATION_0_6 § 2.8](INTEGRATION_0_6.md#28-the-publisher-path-marketplace--registry) with the
mechanism, the failure and the reasoning — the RM27 shape: a finding about a downstream reader is an
explicit ask, never an implication. One read of `manifest.artifact.files` closes it for good, on every
module including the ones already published, which no publisher-side change can reach.

## RM93 — two checks refuse in `compile` and report nothing in `validate`

✅ **Shipped in 0.6.1.** `@validate-refuses-all`, broken twice, and reproduced against real specs before
being fixed rather than argued from the source.

`_check_study_effect_alleles` sat inside `validate_spec`'s `if variants:` block and ran unconditionally
on the compile side, so it never ran for the one composition it was written for: a module with a table
kind, `studies.csv` and `resolution.csv` and **no** `variants.csv`. The comment three lines above the
call claimed it was "audited by check, not by table (`@parity-by-check`)" while the gate did the
opposite. Measured on `cyp2c19_star_alleles` plus one study row naming `C` at an `A/G` locus:
`validate(strict).valid=True` beside `compile(strict).success=False`. The repair is a move and nothing
more — `membership_table` is filled from `resolution.csv` in the sidecar loop far above and is in scope
whether or not a variant was authored, which is the thing worth checking before assuming the hoist needs
an input rebuilt.

`_check_frequency_arithmetic` was never called from `validate_spec` at all. It lives in a per-model
closure on the compile side, so a pass auditing table by table saw `frequencies.csv` loaded and stopped.
Its integer half returns **errors**, so this was the plain-mode variety of the gap — measured on
`hboc_palb2` with `allele_count=500` against `allele_number=100`.

**The durable half is that the guard now enumerates**, and this is where the item was bigger than filed.
`test_validate_agrees_with_compile.py` walked a literal list of four filenames — **four of the seven
fact tables were missing**, not one — and every case in it was a *row-level pydantic* failure, the kind
both sides already catch, so no table-level check had a path through it at all. Separately, every study
fixture wrote `variants.csv` beside `studies.csv`, so `if variants:` was always true and the shape the
gate excluded was never constructed: the suite only ever asked well-composed questions. The list is now
a module constant checked against `_FACT_TABLES`, and the four missing tables have cases.

## RM94 — the p-value re-run publishes its warning twice into the manifest

✅ **Shipped in 0.6.1.** The compile-side `_check_p_value_num` re-run extended `all_warnings` with no
`if w not in all_warnings` filter, which every neighbouring re-run has, including the study-allele block
four lines above it. Reproduced: one authored disagreement, two byte-identical sentences in
`manifest.compilation.warnings`.

**Why it survived is the part worth keeping.** `@no-rerun-with-counts` guards against a re-run whose
message embeds a count, because the two copies then *disagree* and the manifest publishes two numbers —
a self-contradiction somebody notices. This message carries no count, so the copies agreed and the field
was merely redundant. The wider rule the neighbours already followed is now written beside the fix: **a
check that runs on both sides dedupes on the message, and re-running it is the normal case rather than
the exception.**

**The re-run itself was examined and kept**, against the entry's own suggestion that it might not earn
its place. It does: `compile_module` runs `validate_spec` in best_effort *regardless of this compile's
mode*, so the second pass in the caller's mode is the only thing that lets `--strict` escalate the
warning into a refusal. Dropping it would have disarmed the strict gate silently — which is the answer
to "does this pass need to run twice" that the standing test (does resolution change its input?) does
not reach on its own.

## RM95 — a canonicalized vocabulary value is discarded, so the slip is stored and then rejected

✅ **Shipped in 0.6.1.** `@vocab-separator-slip` says a closed vocabulary accepts `-` for `_` **and
stores the declared member**. `MeasureBinRow._validate_measure_kind` called `check_vocab` for its raising
side effect and returned the uncanonicalized value, so the rule held for every other field and failed
for this one. Both halves of the consequence needed fixing: `measure_kind="copy-number"` validated and
stored `'copy-number'` — a value not in the vocabulary, inside `content_signature` — and `_EXPECTED_KIND`
was compared against that same raw string, so every subclass rejected exactly what the base class had
just accepted, with an error naming the canonical form the input already denoted.
`_validate_measure_tiling`, one line above, always returned the result, which is what makes this a slip
rather than a decision.

`Contribution._check_role` and `PgsRow._validate_ancestry` discarded the same return and are fixed with
it. They were latent only because no member of either vocabulary contains a separator *today* — a
property of the current members, not of the code. The list case in `PgsRow` was the sharpest: it
canonicalized per element and returned the original list, so a slip in a multi-valued cell survived whole.

**The durable half reads storage rather than acceptance.** `test_vocab_separator.py` proved `check_vocab`
canonicalizes and could not see a validator that ignored the answer. It now walks every closed-vocabulary
field in the schema — discovered through `field_vocabularies` and pydantic's own decorator registry, so a
new one is covered without editing the file — and drives each validator with both spellings. Five of its
cases fail on the pre-fix tree: `MeasureBinRow` and all four subclasses.

**No signature moved**: every `measure_kind` across the sixteen reference examples was already canonical,
checked rather than assumed.

## RM96 — the registry an audit iterates was missing five of the models

✅ **Shipped in 0.6.1, wider than filed.** `GeneMetricsRow.status` named the `ResolutionRow` vocabulary
in its own description and enforced nothing, so `status="totally-made-up"` validated while every sibling
fact table refused it. `@registry-completeness` from the other side: the model sat outside
`reference._ALL_MODELS`, so the guard that discovers an unenforced vocabulary *by iterating the registry*
could not see it, and `reference.py` recorded the exclusion in a comment while the enforcement stayed
missing.

**The entry named three models outside the registry. There were five.** `ResolutionRow` was outside too
— the canonical holder of `VALID_RESOLUTION_STATUS`, the vocabulary three of the others point at by name
— and `GwasEffectRow` (RM90) landed outside it a day before the audit that found this. So the registry
was falling behind faster than it was being caught up, which is the argument for the fix being the
registry rather than the validator.

Admitting them turned the existing guards on, which is the point, and they immediately found **seven
fields enforcing a vocabulary without declaring it**: `ResolutionRow.status`/`.rsid_status`,
`FrequencyRow.status`, `GeneMetricsRow.haploinsufficiency`/`.triplosensitivity`,
`LiteratureRow.quote_source`/`.status`. Each now carries its marker, so `authoring_reference()` prints
what each cell may contain instead of leaving a consumer to read `model_fields` — the S21 hole, seven
more times.

**The price was accepted knowingly and is the one consumer-visible change in this release**:
`authoring_reference()`, `describe`, `requirements` and `json_schemas()` render 28 models where they
rendered 23. Additive under Principle 3, no schema surface moves, and `INTEGRATION_0_6 § 7` says so.

Two smaller ones alongside. `GwasEffectRow._check_finite` is registered for `effect_size` *and*
`standard_error` and reported `"effect_size"` for both, sending an author to the column that was fine;
`gene_metrics.py` passes `info.field_name` for the identical validator across nine fields, so the idiom
was one file over. And `start` carried `ge=0` on five of the eight models with a position —
`HaplotypeRow`, `PharmVariantRow` and `HeteroplasmyRow` accepted `start=-5`.

**The bound stays `ge=0` and deliberately does not tighten to `ge=1`.** The entry asked the question, and
the answer was already recorded: VCF 4.4 §1.6.1.2/§5.4.5 permit POS 0 for a **telomeric breakend**, and
[VCF_4_4_AUDIT § 9](probes/VCF_4_4_AUDIT.md) filed it under *checked, and not a finding* — `VariantRow.start`'s
`ge=0` is what lets such a record load, while `derive_vrs_allele_id` returns `None` below 1 rather than
minting an id for a position that does not exist. Tightening would have re-broken something a probe round
deliberately left alone, so the reasoning now sits in a test rather than in a probe document.

## RM97 — two clients leak the transport exception the other two document repairing

✅ **Shipped in 0.6.1.** `@client-exception-contract`: retry, then translate, **both legs**. `cpic.py`
and `pharmvar.py` carried the repair *and* the narrative of why it was needed (R2-13) for a whole release
while `gnomad._post` and `eutils._get` kept the unrepaired shape. Both leaked twice over, not once:
`raise_for_status()` sat outside the `try` **and** `httpx.HTTPStatusError` was in neither retry list, so a
5xx escaped raw and unretried; and the transport leg was re-raised bare on purpose, for the decorator to
match, then escaped just as raw once `reraise=True` exhausted the attempts. gnomAD leaked `ValueError`
from `response.json()` past both, while eutils already translated that one leg — the asymmetry that made
it easy to read as fixed.

Both now use cpic's split. **The one deliberate deviation from copying that idiom verbatim** is that each
client's `429 → RateLimitedError` branch stays inside the retried half and before `raise_for_status()`:
those types are what the retry predicate matches and what drives the pacing, and cpic has no such branch
to copy.

`CpicClient.row_count` bypassed its own `_get` entirely, so the one method with no retry and no
translation was the one the snapshot builder uses to refuse a short read: a transport failure raised raw
httpx past `cli.cpic_build_`'s handler, and a 5xx returned `None`, which the builder reads as *"CPIC gave
no count"* — a wrong answer rather than an error.

**Both call sites the entry names are repaired, not just the clients.** `enrich()`'s `check_rsids` had no
handler at all and runs after every other pass has finished and *before* `resolution.csv` is written, so
an NCBI outage threw away work that had already succeeded. It now warns and continues with no verdicts,
matching the gnomAD block above it — and withholding is the outcome rather than a fallback: `rsid_status`
stays unset, which says nobody asked, where stamping `absent` would assert a negative the run never
established.

**The durable half tests the contract, not the method** — that is the finding underneath the item. One
file parametrized over gnomad / eutils / cpic / `cpic.row_count` / pharmvar, both legs plus the
swallow-into-a-wrong-answer case, with a guard that walks the tier for `*Client` classes so a sixth
cannot ship without joining it (the four left out are *named in the assertion*, not skipped). Nine of its
sixteen cases fail on the pre-fix tree — and the seven that pass are cpic and pharmvar, which is the
finding restated.

## RM98 — two passes record an absence nobody established under `--offline`

✅ **Shipped in 0.6.1.** `@unreachable-not-absent`: unreachable is not absent — write no row, name it
separately, warn in both modes.

`enrich.py` holds that rule twice, in the branches on either side of the one that broke it, each with a
comment spelling out that writing `not_found` would state *"the source was asked and does not have this
rsID"*, a negative nobody established. The branch **between** them did exactly that: with `--offline` and
no Ensembl and no ClinVar cache, it wrote `status="not_found", source="cache"`, naming a cache that was
never opened. `gene_metrics` had the same shape: having logged *"gene metrics will be empty"* it wrote a
`not_found` row per module gene labelled `gnomad_v4.1_constraint`, asserting a release was consulted when
nothing was, three lines below its own comment drawing exactly that distinction.

**The filing's `SourceRow` claim was right for a different reason than stated, and the correction is
worth having**: the fabricated row carries `authority='ensembl'`, and `record_source_terms` keys on
`authority` rather than `source` — so a `SourceRow` for a source never read really did follow, by a route
the entry did not name.

Both passes now compute a *was any route consulted at all* predicate from the gates that already exist —
a resolved cache reference, or `not offline` — and withhold when every gate is shut. The result is named
**separately** rather than folded into a neighbour: `EnrichResult.unconsulted_rsids` and
`GeneMetricsResult.unconsulted` are a third state beside `unreachable_rsids` ("the request was made and
failed") and `missing` ("asked, and the source has none"). Collapsing them would have replaced one small
untruth with another. Both warn in both modes and both stay inside the strict refusal, since a run that
established nothing must still refuse.

**`test_fact_passes.py` pinned the wrong behaviour in two places** — it asserted `[r.status for r in
result.rows] == ["not_found"]`, so it was falsifying the log line rather than the behaviour and the suite
was green either way. Those moved with the fix, and each gained a negative control: offline **with** a
cache that genuinely lacks the rsID still writes `not_found`, because that is a real fact and the repair
must not throw it away. Without those, *"stop writing not_found offline"* would have passed.

The `--offline` case is where this matters most, because it is the mode a consumer runs when they
*cannot* reach the source: the fabricated negative is guaranteed there rather than incidental.

## RM99 — three passes bypass the sidecar resolver, so one family writes to two places

✅ **Shipped in 0.6.1, with five more sites than filed.** `@sidecar-name-and-place`: resolve a sidecar's
name and place through the resolver, and **write to the file you read**. RM49 shipped
`licensing.sidecar_path` for exactly this, and nine `sources.csv` writers were converted to it in one go.
`gene_metrics`, `clingen` and `literature` kept their own `spec_dir / "<name>.csv"` literal.

The sharp part is that it was inconsistent **inside one family**: `gene_validity` — `gene_metrics`'
sibling, sharing `module_genes` — did use the resolver. And `gene_metrics` and `clingen` write the *same
file*, both read-merge-write, so one `enrich` run on one module produced two copies of `gene_metrics.csv`
that each dropped the other authority's rows. That is the both-copies-present collision RM49 made an
error rather than a preference, arrived at by following the documented workflow.

**Five more sites turned up in the reporting layer.** `cli.py` printed `spec_dir / 'resolution.csv'` and
four more like it in its success lines, so even where the pass wrote to the right place the CLI sent the
author to a file that had not changed. Two commands already carried the fix with a comment saying why;
the other five did not — which is the same "the rule is written down beside the violation" shape as the
rest of this release.

`literature.py`'s hand-joined `studies.csv` **read** is deliberately left alone and now says so: that is
an *authored* table living in the spec root, and `sidecar_path` is for the machine-written files RM49
allowed under `derived/`.

**The durable half does not test three passes.** Per-pass repair leaves the next pass free to make the
same choice, and these three were written *after* the rule was.
`test_sidecar_resolution_is_uniform.py` walks the enricher's AST for `spec_dir / "<a sidecar name>"` — an
AST rather than lines, so a filename inside a docstring is not a false positive — with `identifiers.py`'s
documented read-only fallback **named** as the one exemption rather than pattern-matched away. Beside it
the behavioural half: the resolver really does follow `derived/` for every sidecar the schema knows
about, and a flat module still gets the flat path, since `derived/` is tolerated and not canonical. The
roster is checked against `layout.SIDECAR_SPELLINGS`, so a ninth sidecar fails there.

## RM100 — five enricher surface defects with no common cause

✅ **Shipped in 0.6.1.** Filed together because each is a few lines, not because they share a root. What
they do share is that every one is invisible from the happy path — which is why the fifth was still
arriving while the first four were being fixed.

**`python -m just_dna_enricher.cli` was missing commands.** `if __name__ == "__main__": app()` sat
two-thirds down the file, above the `hint` sub-app, `draft-clinpgx`, `draft-panel` and — not in the
filing — `clinvar citations`, so the module form called `app()` before those registrations ran. Measured
before and after: 23 vs 26 top-level commands, now 26 vs 26. The guard is structural as well as
behavioural, since the AST test fails the moment a registration is appended below the block, which is
exactly how this arose.

**`clinvar_build._sha256_file` was defined twice.** The second shadowed the first at module load, so the
one that always ran returned `str | None` while the **dead** one returned `str` — and the annotations
downstream had been written against the dead one. `BuildResult.source_sha256` and
`_write_release_json(source_sha256=)` both said `str` while a `None` really could reach them; both now
say `str | None`, which is the house algebra rather than a typing nicety: an unhashable source file is an
unknown digest, not a missing one.

**`enrich_gwas` leaked its client and ignored `mode`.** The close was a bare `if client is None:
catalog.close()` after ~80 lines of fetching and writing, so any exception in between leaked the httpx
client while every sibling pass already used `try/finally`.

`mode` was accepted and never read while the CLI advertised `--strict` as a severity ladder, so the flag
was inert. **What it escalates is deliberately not `missing`**, and the reasoning sits where the raise is:
the Catalog holding nothing for a variant is a fact *about the variant* — recorded as a `not_found` row,
true of most variants, and the pass's own docstring says so — so escalating it would refuse nearly every
module and mean nothing. `strict` reads the two counts that say the artifact does not hold what the
Catalog **did** publish: associations served without an id to key on, and p-values below float64 whose
queryable number is withheld.

**`NCBI_API_KEY` and `JUST_DNA_CONTACT_EMAIL` were read without `load_env()`** (`@credential-where-read`).
`PharmVarClient` calls it with a comment describing this exact failure; `eutils` and both literature
clients read `os.environ` directly, so a `.env`-only key was honoured or ignored by call order and the
NCBI rate gate silently stayed at 1/3 s instead of 10/s.

That fix immediately broke `test_eutils.py`, and **that is the interesting part rather than collateral**:
it used `monkeypatch.delenv("NCBI_API_KEY")` and passed only because nothing had loaded `.env` yet.
`@test-no-credential` says `setenv(VAR, "")`, never `delenv` — `load_dotenv` skips a variable that is
merely present — and `test_literature_terms.py` states the same rule beside its own fixture. So the rule
was already written, already explained, and already violated one file over; the fix made it fire. Both
call sites move to the documented idiom.

**The fifth, filed after the first four had shipped: `net.py` documented "the nine policies" in two
places while the tree carries twelve**, across nine modules. The guard meant to hold that claim was blind
on both axes at once — `assert len(found) >= 9` is a floor, so three new policies pass it, and it walked
a hand-kept list of seven module names.

The measurement is sharper than the filing. The old walk reported 12, the right number, **by accident**:
it counted a client once per module that *imports* it, so the inflation from double-counting happened to
cancel the two modules it never opened. Filtering by defining module, it saw ten distinct policies and
was blind to `grch37.Grch37Client._get` and `gwas.GwasCatalogClient._get` entirely. **A guard whose number
is right for the wrong reason is worse than one that is merely wrong, because the number reads as
confirmation.**

The fix is an equality over a walked set, not a corrected count: the test discovers modules through
`pkgutil`, filters owners by `__module__` so an import cannot double-count, and asserts set equality
against the twelve by name. The prose loses its number rather than gaining a corrected one, and says why
— a count in a docstring is a registry nothing iterates, which is RM96's finding arriving in a docstring
instead of a `dict`.

# 0.6.0 — the design round, built

**The whole of [PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md)'s decision list, implemented.** Sixteen items were
argued to a decision on 2026-08-13 — each with the facts probed, the repairs rejected and why, and the
consequences that follow without being chosen — and the eleven that build are below with their original
entries intact. The proposal stays the reasoning document; these are the outcomes, and where the two
disagree the note at the top of each section wins, because several of these entries were written before
the decision and describe a shape that was rejected.

**Landing them cost one charter amendment, which went first and alone.** The Constitution ruled on
whether a change was *legal* and said nothing about what a legal change *cost*, and the absence kept
surfacing as an instinct that there were "too many tables" — right about some additions, wrong about
others, with no stated way to tell which. A schema addition now costs what its layer costs: a parquet
column is approximately free, a derived CSV is half, an authored schema is full. Four of the decisions
below turn on it, and two obviously-worth-building items (RM24, RM25) had looked like creep only because
a machine-written sidecar was being priced as though a human had to learn it.

**The VCF 4.4 cluster shipped with them.** RM53–RM65 came from [VCF_4_4_AUDIT.md](probes/VCF_4_4_AUDIT.md), a
full read of the specification against the schema, and they are not repeated here as sections because
the audit remains their evidence document. Their through-line is worth stating once: *the schema named
a VCF field by a bare token, and a VCF field is not identified by its name* — it is identified by
namespace (INFO and FORMAT collide on `DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and, new in 4.4, `CN`) and
described by cardinality. Both readings of a colliding key are usually type-compatible, so nothing
detects the confusion: a consumer reads a well-formed number of the wrong kind. Two shipped reference
examples were wrong on exactly this and were re-authored, which is why `mt_heteroplasmy` and
`htt_repeat_expansion` are the only two modules in the corpus whose `content_signature` moved across
the whole batch.

**What the batch cost the corpus, measured rather than assumed.** Across all eleven reference examples:
`content_signature` moved on **two** (the two re-authored above), `artifact.digest` moved on **seven**
(new optional and stamped columns — Principle 4 scopes byte-reproducibility to a fixed
`compiler_version`), `resolution_signature` **gained** a value on the four table-only modules that
carry a `resolution.csv` and no `variants.csv`, which is precisely the hole RM45 closed, and the source
signature moved nowhere. The suite went from 1535 to 2046 tests.

**One pattern showed up three times independently and is now a rule in CLAUDE.md.** Three separate
lanes shipped the same defect and each was caught by its own code review: a check re-run after
resolution counts the *expanded* rows, so an rsID that resolves to several loci produces the same
finding twice with different numbers, message-dedup keys on the sentence and cannot collapse them, and
both reach `manifest.compilation.warnings` — a published field contradicting itself. Measured at
"1 row(s)" beside "2 row(s)", and at 328 beside 337 on `pathogenic_clinvar`. The rule covering it and
its opposite: **re-run a check after resolution exactly when resolution changes its input, and never
when the message embeds a count.**

## RM4 — Native ClinVar gene-panel materialization

✅ **Shipped in 0.6.** Compile-time materialization was dropped rather than built: the mechanism is enricher draft-scaffolding, which already shipped, and the author's no-op over the drafted subset is still an authorial act. `panel:` lost its last consumer and is deprecated (removal at 1.0, tracker line filed); `clinvar_draft` now stamps the ClinVar release into the licence row's `dataset`, and `clinical.tautology_reason` keys on that instead of the authored block — both sides calling one shared label function, because a writer and a reader disagreeing about it would not fail, they would silently never match. The hand-edit hole closed on a mode ladder (`strict` audits every row into copied / authored / conflicting / no_record; `best_effort` keeps the cheap skip plus a notice naming the hole). Two findings the round produced: `merge_sources_csv`'s never-clobber rule is right for terms and wrong for a machine-stamped release label, so the label is now *withdrawn* rather than re-labelled when a module spans two releases; and "copied" had to become allele-exact, since a locus-wide match can be a sibling allele's call (`rs334` carries pathogenic `T>A` beside likely-benign `T>G`). The unrelated surface bug shipped with it: `draft-panel` exposes `--download/--no-download`.

**Severity** medium · **Status** deferred to 0.6+ — the injectable-reference half is unblocked ·
**Owner** format (compiler) + consumer-provided reference · **Motivating case** gene-panel modules
(cardio / cancer / pathogenic)

Compile a `GenePanelSpec` (gene set + significance predicate) into `weights.parquet` at compile
time, gated on a **content-pinned ClinVar reference mixin**. The 0.2 `GenePanelSpec` *interface*
ships and is recorded verbatim; the app-level `gene_panel` adapter in just-dna-lite is the interim
reference implementation. Blocked only by Constitution P2 (no network) — the reference must be
*injected*, not fetched. **0.5 update:** the content-pinned reference now exists as an injectable
artifact — `just-dna-enricher`'s ClinVar snapshot (`clinvar build` → `data/*.parquet` +
`release.json` carrying `source_sha256`/`clinvar_file_date`, feeding
`GenePanelSpec.reference`/`reference_sha256`). What stays parked is the *compile-time
materialization* of a `GenePanelSpec` into `weights.parquet`; the injectable reference half is
unblocked.

## RM5 — Symbolic / structural alleles

✅ **Shipped in 0.6.** The five closed VCF first-level types (`DEL`, `INS`, `DUP`, `INV`, `CNV`) with open subtypes, and nothing above them — the `##ALT` declaration mechanism stayed rejected as unasked extendability. **The one question the decision left open, where the length lives, resolved to *inside the token* (`<DEL:1500>`, `<CNV:TR:30>`) on evidence rather than taste**: VCF carries it as `SVLEN`, which is `Number=A`, so a scalar column cannot describe `alts=<DEL:5>,<DUP:9>` and a parallel array is the desync shape `vrs_id` needed two guards for; and three of the columns holding an allele have no row to hang a length on. A length-less symbolic allele is dropped with a warning saying **dropped** under `best_effort` and refused under `strict` — fatal in both modes on the composite tables, where dropping a row makes a quietly *different* module rather than a smaller one. 5-HTTLPR stays a plain indel and CPIC's IUPAC codes stay unexpressible, both deliberately. Carried the docstring fix: `validate_allele` has two users, not one.

**Severity** medium · **Status** deferred to 0.6+ · **Owner** format (schema) · **Motivating
case** 5-HTTLPR, SNP+SV modules, symbolic-VCF consume

A representation beyond `^[ACGT]+$`: `<S>`/`<L>`, `<DEL>`/`<INS>`/`<DUP>`, `<STR n>`, and large
indels. **Motivating cases: 5-HTTLPR** (a biallelic ~43 bp structural indel → Short/Long, *not* a
repeat count; rejected by today's nucleotide grammar and a category error in `repeat_alleles.csv`)
**and ClinPGx's `del`/`ins` genotypes** (177 rows in the release, e.g. `C/del`, `del/del`), which
the PGx passes skip rather than coerce. Also unblocks SV-scale variation and consuming symbolic
VCF alleles (round-2 §1b/3c).

## RM24 — Gene–disease validity as a table

✅ **Shipped in 0.6** as `gene_validity.csv`, a derived fact sidecar with its own signature, manifest block and non-tainting `gene_validity` source layer. **Probing corrected the stated grain twice**: mode of inheritance had to join the key (59 ClinGen gene/disease pairs carry two rows differing only there) and so did `submitter`, because GenCC is a nineteen-submitter aggregate whose *disagreement* is the data and collapsing it would publish one arbitrary verdict as consensus. **HPO ships no route**, a deviation argued in the PR: its licence URL 404s and OBO Foundry records no SPDX id, so its terms cannot be established, and an inject-only tier does not get to assume them.

**Severity** medium · **Status** deferred on the design, not the code · **Owner** format (schema +
compiler) + enricher · **Motivating case** gene-panel triage; lay-language disease naming

(`gene_validity.csv`) — one row per `(gene, disease term, classification, source, dataset)`,
serving **ClinGen** gene-disease validity, **GenCC** aggregate validity and **HPO** gene→phenotype
from one shape. This is a *different grain* from `gene_metrics.csv` (gene × term, not gene), which
is why it is a table rather than more columns; dosage sensitivity went the other way for the same
reason. The cost is the design (getting one shape to fit three submitters' vocabularies), not the
code. All three sources are free, so unlike RM23 this one leaves a module sellable — worth
remembering if the marketplace ever sells modules, since every PGx upstream forbids it.

## RM25 — ClinVar assertion tier as artifact data

✅ **Shipped in 0.6** as `clinical_assertions.csv` — the clinical call, the review wording, the star rating and ClinVar's own VariationID, one row per allele × record. The deciding argument was the house one applied a fourth time: `draft_gene_panel` was already using the star rating as a filter and throwing it away, so every consumer would have recomputed it. A one-star single submission and a practice guideline are no longer flattened to the same `clin_sig`. The cross-check's severity stays parked, deliberately.

**Severity** medium · **Status** deferred as a new table · **Owner** format (schema + compiler) +
enricher · **Motivating case** authorship/assertion-aware scrutiny

A facts sidecar carrying `clin_sig` + `review_status` + `review_stars` + `variation_id` per
variant, so a consumer can route scrutiny by assertion tier at query time (a 1-star submitter and
a practice guideline are not the same claim). Nothing is lost today: `clinical.ClinSigFinding`
**already** reports both fields via its `confidence` property, so this is about persisting the
tier, not discovering it. Deferred as a new table. **Do not confuse this with escalating the
check's severity** — see *Parked in 0.5*.

## RM27 — A redistribution compile gate

✅ **Shipped in 0.6 as record-only, with a named enforcer.** The most-restrictive redistribution verdict is stamped into the manifest and **no gate exists in these four packages** — gating belongs at *publish*, which lives downstream, so the item ships with an explicit ask addressed to the registry in SCHEMAS.md rather than an implication. That is the whole difference from the status quo the item was filed about: a recorded right nobody is told to enforce, versus a recorded right with a named enforcer. `taints_redistribution` no longer describes the design as open.

**Severity** low (after the design) · **Status** deferred — needs the third axis designed first ·
**Owner** format (compiler) + enricher · **Motivating case** OMIM-/dbNSFP-class sources

RM21's gate keys on `commercial_use` + `declared_use`; the 0.5 `redistribution` column is recorded
but **not** gated. Deferred because it is a genuine design question rather than a missing branch:
a redistribution bar is not a *use*, so `declared_use` (`unstated`/`non-commercial`/`commercial`)
is the wrong axis to resolve it against — a module may be built legitimately and still not be
shippable, which is a different verdict from the ones the gate currently issues. Needs the third
axis thought through before code.
## RM43 — Resolution reaches the SNP core only, so a 0.4-led module is rsid-joinable and nothing more

✅ **Shipped in 0.6.** The injected `resolution.csv` is joined onto the three positional kinds before `_build_table` materializes them, in `validate_spec` as well as `compile_module`. Each model gained stamped, parquet-only `variant_key` and `authored_ident`, plus `alts` on `PharmVariantRow`/`HaplotypeRow` filled as **data, not identity** — the key is still derived without it, so the existing "matches at `chrom:start:ref` regardless of allele" contract is unchanged. The reported case closed: `pgx_slco1b1_simvastatin`'s nine rows went from every coordinate null to `12 / 21178615 / T / A,C`. `reverse` rebuilds the lookup table from the positional parquets as a second source, which P7 forces. No `resolution.parquet`. **One deviation worth keeping**: the stamped fields are `Field(exclude=True)`, because declaring them plainly moves `content_signature` on all five positional-table modules — `model_dump(exclude_none=True)` never omits a stamped field, since it is never `None`. That leaves `VariantRow`'s own two inconsistent with the three new ones, grandfathered and filed as a 1.0-cleanup candidate.

**Severity** high (the prerequisites, not the join) · **Status** open — **0.6**, gated on a design
round rather than on a version · **Owner** format (schema) + compiler · **Motivating case** an rsid-authored ClinPGx
module: 1,482 rows, 147 variants, every coordinate null (S9 in
[CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md))

`compile_module` resolves `variants.csv`; every other table goes through `_build_table`, which is
`model_dump()` → parquet. So a module led by `pharm_variants.csv` or `haplotypes.csv` keeps exactly the
coordinates its author typed, which for an rsid-authored one is none — and a VCF is joined by position,
so the table annotates nothing, silently, as an empty result rather than an error. Reproduced on this
tree's own `reference_examples/pgx_slco1b1_simvastatin/`: 9 rows, all null, while the `resolution.csv`
beside the spec resolves the rsID perfectly well. **0.5.3 made it legible** — the compiler now reports,
per positional table, how many rows cannot be joined and how many of those the injected table could
place — but the fix itself is here.

**The obvious repair is illegal as stated, and that is the part worth recording.** "Join `resolution.csv`
on `variant_key` and fill the empty cells" moves more than the digest the reporter expected: materializing
the coordinate and running `compile → reverse → compile` moves **`content_signature`**
(`sha256:8173dab7…` → `sha256:fb91ffa2…`), because `reverse_module` rebuilds the CSV from the parquet and
a filled coordinate returns as an *authored* one. That is exactly what `VariantRow.authored_ident` exists
to prevent, and no 0.4-family model has an equivalent. So the prerequisite is a stamped
"which identity columns did the author supply" column per positional table — a **new column on an
existing parquet** — which is **0.6 work** since the 2026-08-11 charter amendment, so the prerequisite
is a design round rather than a major bump. What stays major-only is nothing here: the item is gated on
doing the stamped-identity design first, not on a version.

Three more constraints found with it, each of which shapes the design rather than merely costing:

- **`PharmVariantRow` has no `alts` column at all.** A filled row can carry `chrom`/`start`/`ref` and no
  allele, so a positional join lands on the locus and allele matching still goes through `genotype`.
  Adding `alts` is a second new column, and it would make the key allele-specific — which
  `_collect_subjects` deliberately avoids ("a pharm annotation matches a variant at `chrom:start:ref`
  regardless of allele").
- **`variant_key` is a *property* on these models**, so it is materialized in no PGx parquet. A consumer
  cannot join a PGx row to `weights.parquet` on it either — which is a second, smaller instance of the
  same complaint and probably wants solving in the same round.
- **The manifest cannot say any of this.** `fully_resolved` is `all(...)` over `VariantRow`, so it is
  vacuously `true` for a table-only module — against the trust rule its own field comment states — and
  `resolution_signature`/`resolution_sources` stay unset, so the injected table leaves no trace.
  Stamping the signature is itself blocked: `reverse_module` rebuilds `resolution.csv` from
  `weights.parquet` alone, so a table-only module reverses to a spec without one and the round-trip
  fixed point breaks. This half is the same shape as the registry's S8 (a manifest that cannot say a
  check ran) and should be decided with it.

## RM45 — the manifest is rich about resolution and silent about verification, so `unchecked` and `clean` are one state to a downloader

✅ **Shipped in 0.6** as `verification.json` — a derived attestation the enricher writes and the compiler reads, stamping `manifest.verification` or dropping it with a warning when stale. Counts rather than booleans and **two fields rather than one union-typed slot**, so "ran against 0 rows" and "did not run" can never share a value; two closed vocabularies rather than free strings, which would have recreated RM44 one level down; bound to the authored bytes with a **~0.4 s median** proof-of-work, one per sidecar per run, found deterministically so the bytes reproduce. Every field is marked untrusted, in the descriptions *and* in SCHEMAS.md, because a forged pass is worse than silence. **A JSON document rather than a fifth fact CSV**: one attestation over many records is a service row in CSV, and it is the one derived artifact whose human-overridability must not be a feature — which is the mechanism the 0.6 charter amendment asks for. The vocabulary audit moved the set twice: `pgx_evidence_level` and `rsid_coordinate_agreement` were genuinely missing, while lane E's two new passes correctly get no member because they adjudicate nothing, and a test pins that exclusion by name. Wiring it up surfaced two pre-existing holes — the reference-allele and clinical checks each had an internal skip returning an empty list indistinguishable from a clean pass, which is S4's defect surviving inside S4's own machinery. `resolution_signature`/`resolution_sources` are now stamped for table-only modules too, unblocked by RM43.

**Severity** medium (a per-version trust signal nobody can build, and no way to triage what was
published unchecked) · **Status** open — **0.6** · **Owner** format (the manifest shape + vocabulary) +
enricher (the only tier that holds the facts) + compiler (the stamp) · **Motivating case** a catalog
that verifies a module's `clin_sig` on its own deployment has nowhere to record that it did (S8 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Confirmed structurally, which is the strongest form this claim can take.** `Compilation`'s twelve
fields carry nothing about verification. `ResolutionRow`'s eighteen columns are all per-*row*
(`status`, `rsid_status`, `rsid_current`). `EnrichmentResult` holds `clin_sig_not_checked`,
`ref_mismatches`, `stale_rsids` and `vrs`, and dies when the run ends. So a module whose authored
`clin_sig` was cross-checked against ClinVar and one where the check never ran ship **identical**
manifests — not by oversight in some path, but because no field exists that could differ.

**This is S4's own argument one level down.** 0.5.2 accepted that an empty `clin_sig_conflicts` meant
both "compared everything, nothing disagreed" and "never compared", and fixed it — on
`EnrichmentResult`. The layer that outlives the run inherited none of it, so the rule holds in process
memory and nowhere else. The same applies to the reference-allele and rsID-currency passes.

**Legality is not the obstacle, and it is cheaper than the usual case.** The manifest was never inside
`artifact.digest`, and a new optional field is additive and minor-legal (P3, amended 2026-08-11) — so
**0.6, not 1.0**. A manifest field that a *publishing authority* stamps rather than the compiler
deriving is also already this schema's shape: `compiled_by`, `namespace`, `owner`, `published_at` and
`canonical_id` are all that. And the reporter's field shape is right for our own stated reasons —
counts rather than bools, and **two** fields rather than one map with a union-typed value, so "ran
against 0 rows" and "did not run" can never occupy one slot. `vrs_alleles`/`vrs_alleles_identified` is
the precedent; the ACMG pass's `checked: 0` is the other.

**Four things the proposal leaves open, which is what makes this a design round and not a patch:**

1. **The check name is a vocabulary, or this is RM44 again one level down.** A `dict[str, int]` keyed on
   free strings lets the enricher write `clin_sig`, a registry write `clinsig`, and a consumer
   substring-match the difference — an unversioned interface, the exact defect RM44 exists to remove.
   The keys want `frozenset[str]` + a validator (P6), and because vocabulary members are permanent
   within a major (P5) the set has to be audited once against the passes that would plausibly join it:
   reference allele, rsID currency, ACMG SF, identifier/trait currency, quote-checking, dosage
   sensitivity.
2. **The skip *reason* must not be free prose either, for the same reason.** Backfill triage — the
   reporter's own second use case — branches on *why* a pass did not run, so `dict[str, str]` of prose
   relocates the substring matching rather than ending it. The reason wants a small closed vocabulary
   (`tautological`, `no_reference`, `offline`, `not_applicable`) with the sentence *beside* it, not
   instead of it: `clinical.tautology_reason` already writes a good sentence and it is worth keeping as
   human detail rather than promoting to a machine key.
3. **The seam has no channel, and that is the actual work.** `resolution.csv` is the enricher→compiler
   contract and carries per-row facts only; "this pass did not run" is per-pass by nature and has no row
   to attach to — the reporter identifies this precisely. Two routes, and choosing is the design. A new
   sidecar the enricher writes and the compiler reads is consistent with every other injected table
   (and would want its own fact-signature), and it gives the workspace a path it can test end to end.
   An argument on `compile_module` is cheaper and is what the reporter proposes, but then the only
   producer is the caller: the format would declare a field its own reference implementation never
   fills, which is how `VALID_SOURCE_LAYERS` ended up with members no file carried.
4. **The trust rule belongs in the schema's own docs, not in the reporter's caveat.** Their point that a
   forged pass is *worse than silence* is right, and it already has a spelling here — `compiled_by`'s
   description says "foreign values are untrusted". Whatever lands must say the same on each field and
   in SCHEMAS.md, or the first consumer to read `checks_run` off an untrusted manifest believes it.

**Recommended shape: option 2, a `Verification` block.** The reporter's own argument for it is the
stronger one and it is the house pattern — `Frequency` earned a separate block because it has its own
producer, its own release and its own fact-hash, and verification has all three. A `clin_sig` check is
only as good as the snapshot it read, so the block wants that release id, and no existing block has a
home for it; `locations.read_release` (0.5.2) is what makes "verified against ClinVar release X" a
sentence this tier can complete at all. Absent on a module nothing verified, which reads correctly as
*says nothing* rather than as a pass.

**It does not subsume RM44.** S13 offered S8 as the superset and it is not one: `resolution_subjects` is
the denominator of an existing flag about *resolution*, which is not a verification pass. Adopting that
framing would park a one-line additive integer behind this whole round.

## RM46 — a literature source's terms are per-article, so the enricher names a source it cannot record

✅ **Shipped in 0.6** as per-article licence columns on the derived literature row, filled from the Europe PMC response the pass already makes and mapped at read time. No `PUBMED_TERMS` constant: a literature source's terms are per-article, and one `pubmed` row would be right for a module citing only ids and **wrong** for one carrying a quote lifted from a CC-BY-NC article — wrong in the dangerous direction, because that quote is publisher text in the module's own annotation layer. Quoting a restrictive article **warns and gates nothing**, on the clinical-cross-check precedent: arbitrating copyright is the same class of overreach as arbitrating a clinical dispute.

**Severity** low as a symptom (a warning on every literature-enriched module), medium as a hole (a
module quoting a CC-BY-NC article has no way to say so) · **Status** open — **0.6** · **Owner**
enricher (`licensing` + `literature`) · **Motivating case** every literature-enriched module warns
about a source the enricher itself introduced (S10 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Reproduced by reading the three pieces.** `enrich_literature` writes `source="pubmed"` into every
`literature.csv` row. `TERMS_BY_SOURCE` has seven members and no `pubmed`, and `record_source_terms`
deliberately *skips* a name it has no terms for ("inventing a row for the rest would be worse than the
compiler's honest warning"). `_source_checks`'s under-declaration branch then names `pubmed` on every
such module. So the tier introduces a source and declines to record it, and the finding lands on the
author. Worth stating precisely, because it bounds the severity: `SourceRow.source` is free text, so an
author *can* hand-write the row and clear the warning. This is not an unclearable finding — it is the
enricher asking the author to write down something only the enricher knows.

**The reporter is right that a `PUBMED_TERMS` constant would be the wrong fix, and this is the part
worth keeping.** A literature source's terms are **per-article, not per-source**: PubMed's *metadata* is
one thing, the *article* belongs to its publisher, and Europe PMC's OA subset spans CC-BY, CC-BY-NC and
bronze. One `pubmed` row would be right for a module that cites only PMIDs and **wrong** for one
carrying a `provenance_quote` lifted from a CC-BY-NC article — and wrong in the dangerous direction,
because that quote is publisher text sitting in the module's own **annotation** layer, which is exactly
where `taints_commercial_use` bites. A row that reads "pubmed, fine" would make such a module look
cleared when it is not, which is worse than today's warning.

**Two other obvious repairs, both wrong.** *Stop writing `source="pubmed"`* — no: `source` is how a
consumer knows which upstream answered, and the existing reasoning for preferring PubMed over Europe PMC
(which "cannot originate a row", since it silently omits ids it does not know) is sound. *Have the
compiler exempt enricher-introduced sources* — no: the compiler would need to hold a list of which
sources a pass introduces, which is a **source convention**, forbidden it since 0.5 (P2) and the exact
mistake RM33 removed. The fix belongs to the tier that both names the source and owns the terms table.

**The shape that matches the facts is the reporter's option 2, and it is the bigger one.** Per-article
terms, either as an additive licence column on `LiteratureRow` (minor-legal) or as `sources.csv` rows
keyed by DOI, plus one decision that is not the enricher's to make alone: whether quoting a CC-BY-NC
article taints the module for sale. That is the *use*-versus-*distribution* axis **RM27** already parks,
so the two want settling together. The tier is closer than it looks: `is_open_access` is already
tri-state on the row, and the pass holds the licence at the moment it would need to record it (Europe
PMC returns `isOpenAccess`; Unpaywall returns a licence id per DOI).

**Interim step, if 0.6 slips:** the reporter's option 1 (a `literature`-layer `pubmed` row for the
*metadata*, plus a documented rule that quoting requires a second `annotation`-layer row for the
article) is defensible — but only if the row's terms are stated as the metadata's and the quoting
obligation is written where an author reads it. Shipped as a bare terms constant it silences the warning
and buys the false clearance above, so it is not a one-liner.

## RM47 — a bin boundary is the most interpretive claim in the format and the only one with nowhere to cite

✅ **Shipped in 0.6.** `MeasureBinRow.pmid` grounds the *boundary* — one optional column on the binning base reaching all four kinds — and `StudyRow`'s subject requirement relaxed so a citation row may name no variant, which only makes previously-*invalid* rows valid. The documented line is **the bin row cites, the citation table describes**, which is what stops `StudyRow`'s provenance column set migrating onto binning rows one column at a time. The same-release obligation was met rather than deferred: `_cross_check_literature` and the enricher's literature pass both read the new site, reached across the tier boundary through new **public** compiler symbols (`load_binning_rows`/`binning_citations`) rather than a private import or a second hand-kept kind list. `htt_repeat_expansion` stays deliberately uncited — the example exists to show the gap.

**Severity** medium (no module is unauthorable, but the claim a reader would most want to check is the
one the schema asks nothing about) · **Status** open — **0.6**, gated on a design round rather than on a
version · **Owner** format (schema) + compiler + enricher (the literature pass) · **Motivating case** an
HTT CAG module whose thresholds had nowhere to record their source (S19 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Reproduced on this tree's own reference example.** `reference_examples/htt_repeat_expansion` compiles
green under `--strict` stating four Huntington thresholds — 26/27, 35/36, 39/40 — with no citation
anywhere in the module, and until 0.5.4 nothing said a word. Its README even says *"a module making a
novel claim should carry its evidence"*, which is advice the schema gave the author no way to take.
`StudyRow` identifies its subject by `rsid` **or** `chrom`(+`start`), and a `repeat_alleles.csv` row is
keyed `(gene, repeat_unit)`, so no study row can name one; `MeasureBinRow` has no `pmid`, `doi` or
`evidence_level`. The requirement is enforced exactly where citations usually arrive for free — a
ClinVar-drafted `variants.csv` — and absent where a human made the judgement.

**One correction to the report, and it narrows the item.** The same does *not* hold for
`heteroplasmy.csv`: it has carried optional `rsid`/`chrom`/`start`/`ref`/`alts` since 0.5.1, so a study
row on the same variant identity points at it exactly, and `reference_examples/mt_heteroplasmy` already
does this. What is genuinely unpointable is the three gene-keyed kinds — `repeat_alleles.csv`,
`copynumbers.csv`, `activity_phenotype.csv` — plus a heteroplasmy row that names only a gene. A second
correction in the other direction: `studies.csv` is *not rejected* in a variants-free module. It loads,
validates and materializes `studies.parquet` today, so an author can ground the module as a whole right
now — the row simply has to claim a variant identity the bin does not have (a bare `chrom=4` for HTT),
and nothing ties it to a bound.

**Shipped in 0.5.4 (the reporter's option 2), and it is the interim, not the answer.**
`compiler._check_binning_grounding` warns in both modes when a binning table states thresholds and the
module records no study rows at all, with the message split on whether the rows *could* be pointed at:
the heteroplasmy shape gets a remedy ("fill the identity columns"), the gene-keyed shape gets the honest
statement that no study row can name one of these bins. That turns silence into a visible decision and
changes no schema.

**Four candidate repairs, and none is a one-liner — which is why this is filed rather than fixed.**

- **`pmid`/`doi` on `MeasureBinRow`.** The smallest schema move (a new optional column on the base
  reaches all four kinds, minor-legal under P3) and the only one that grounds a *boundary*, which is what
  was actually asked for. It is also the largest **wiring** move: `literature.csv`, `_cross_check_literature`
  and the enricher's literature pass all read `StudyRow.pmid` and nothing else, so a bin-row PMID would
  be a citation no existence check, no bibliographic check (S12) and no quote check ever reaches —
  grounding that *looks* verified and is not, which is worse than the honest gap. And it starts the
  drift: `studies.csv` carries population, `p_value_num`, `effect_size` and `provenance_quote`, so the
  first author wanting a quote begins growing `StudyRow`'s column set onto a binning table.
- **A generic `subject_key` on `StudyRow`.** Rejected on the binning tables' own stated rule —
  *multicolumn keying, never a packed tuple*. `HTT|CAG` is a second spelling of an identity the columns
  already spell, it can drift from them with nothing to catch it, and P5 gets a field carrying two axes.
- **Key columns on `StudyRow` plus a new `REQUIRED_ANY_OF` alternative.** Legal — the columns are
  optional, and widening an any-of only makes previously-*invalid* rows valid, so no published module
  breaks. But it grounds at table granularity, not at the boundary: a `(gene, repeat_unit)` study row
  still does not say why 36. Making it say so means putting `measure_min`/`measure_max` on the study row,
  i.e. restating the bin inside its own evidence. It also quietly changes a contract consumers read —
  every `studies.parquet` row today carries an rsid or a chrom.
- **A `bin_evidence.csv` join table.** Keeps one-CSV-one-concern and grounds per bound, but the join key
  *is* the bounds, and they are floats: re-authoring `40` as `40.0`, or moving a threshold, silently
  orphans its evidence with no rule able to notice. A join key that is also the data is the shape to
  avoid.

**So the decision to make is which granularity the format promises** — module, table, or boundary — and
every honest repair costs either a duplicated column set or a duplicated key. Settle that first; the
column follows in an afternoon. Whichever wins, the literature pass and `_cross_check_literature` have to
learn about the new PMID site in the same release, or the format ships evidence it does not check.

## RM48 — an hg19 coordinate has no supported path into a GRCh38 module, and liftover is the wrong primitive

✅ **Shipped in 0.6, and the roadmap's stated blocker was false.** Ensembl runs a permanent GRCh37 REST service serving both dbSNP variants and reference bases, and per-contig lengths for both builds are 25 numbers each — no chain file, no provisioned asset, no new licence, so the scope-back condition never triggered. rs-number recovery only, live-only, reporting and never filling. The offline half (a position past its contig's end, a contig only one build names) went into the **compiler**, in `validate_spec` and `compile_module`, as an **error in both modes** — it is provably wrong, the inconsistent-reference-allele class. The online build-guessing half stayed in the enricher. **The round's sharpest finding was about already-shipped code**: run on a real wrong-build scenario, the existing ±1 neighbour check reported "shifted 1 base to the right" for two rows whose true variants are 228 and 411 bases away — a neighbouring base equalling the authored `ref` is a one-in-four coincidence. The new diagnosis supersedes it, but only from its two strong evidence tiers, since a single-base GRCh37 match rests on the same coincidence.

**Severity** low-medium (an authoring gap with a manual workaround, filed as a longshot by the
reporter) · **Status** open — **0.6**, gated on choosing the primitive · **Owner** enricher (the
recovery link + any provisioned asset) + format (`resolution.csv` provenance) · **Motivating case** an
author curating from older literature with hg19 supplementary tables (S22 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Not RM15, and the distinction is the useful part.** RM15 is about supporting another build *as the
module's build* — it changes `variant_key` semantics and every coordinate, which is why it is 1.0. What
is missing here is one-way and authoring-time: the module stays GRCh38, only the author's input is
hg19. It re-keys nothing, needs no GRCh37 refget table, and changes no published identity, so filing it
under RM15 would park an additive tool behind a major-version blocker for no structural reason.

**The reporter argues against their own request, and the argument holds.** Trace when liftover is
actually reachable. If the paper gives an rsID, liftover is unnecessary and worse: authoring the rsID
*produces* the independent second value `resolution._verify` cross-examines. So liftover is only
reachable when there is no rsID and only an hg19 coordinate — and in exactly that case the lifted
coordinate becomes the row's sole identity, with nothing independent to check it against. A liftover
tool is therefore a generator of unverifiable-by-construction identities, which is the hazard class
behind the 3,038-variant off-by-one this tree already paid for. What the author wants is **rsID
recovery**: given an hg19 `chrom:start:ref:alt`, return the rsID or say there is none, so they author
an identity normal resolution can verify. Same input; it converts an unverifiable coordinate into a
verifiable one using machinery the enricher already has.

**Why it is not simply "do rsID recovery, then".** The recovery lookup is against a *build the enricher
does not otherwise touch* — every link is gated on GRCh38 — so it needs either an hg19-keyed dbSNP
surface or a chain file, and a chain file is a provisioned, pinned asset with its own licence and
release, i.e. the whole snapshot apparatus for one authoring convenience. That is the design round, and
it is what the version gate is on. Liftover survives only as the fallback for a locus with no rsID at
all, where it must announce itself rather than emit a coordinate that looks authored.

**One requirement whichever primitive wins, and it is already a shipped lesson.** The outcomes are
**mapped**, **unmapped** and **ambiguous** (a coordinate lifting to several targets), and they must not
collapse — `pyliftover` returns an empty list both for unmapped and for a missing chain file, which is
byte-for-byte the fusing S20 fixed in this same resolution path on the same day. Whatever lands here
returns three states, and the provenance goes in `resolution.csv`'s `source` column rather than being
lost into an ordinary authored coordinate.

## RM50 — PMID and PMCID are one id apart, and only one direction of the conversion exists

✅ **Shipped in 0.6.** `extract_pmids` now declines a digit run whose context spells `PMC` in any spacing, and the refusal **names the id it saw** rather than the one it wanted. This closed a live hazard rather than a cosmetic one: `PMC3110566` never parsed, but **`PMC 3110566` did** — and those digits are a real PMID for an unrelated article, so the outcome turned on a space and the accepted spelling silently cited the wrong paper. A cell that compiled before may refuse now; that is the fix. The PMC id lives on the derived row only, and `hint citation --pmcid` is a **reporting** lookup that never fills `pmid`, because filling it would make the existence check compare a value against the registry that produced it. The authoring half stays 1.0 with the requiredness demotion, since a citation with no PubMed id cannot become legal while P8 holds.

**Severity** medium (the accepted-but-wrong case is a silently misattributed citation — the S12 class)
· **Status** open — the **diagnosis half is an enricher patch and does not wait**; the schema half is
**0.6**, gated on a design round and on the requiredness demotion already queued for 1.0 · **Owner**
enricher (the guard, the reverse lookup) + format (`extract_pmids`' grammar and its message) ·
**Motivating case** raised while reading SCHEMAS.md's own account of the three reference tables
(2026-08-12)

**Three distinct confusions live under one heading, and only the middle one is already tracked.**

**1. A PMCID written where a PMID goes is sometimes accepted, as a different paper.** `StudyRow.pmid`
is free-form and validated through `spec.extract_pmids`, which is `\b(\d{1,8})\b`. Probed:
`PMC3110566` → `[]` and `pmcid: PMC3110566` → `[]` (no word boundary between `C` and a digit), but
`PMC 3110566` → `['3110566']`. The outcome turns on a space. When it is accepted the extracted number
is a **real PMID for an unrelated article** — PMIDs are densely allocated, which is precisely the S12
finding that made `pmid_exists` useless as a fabrication guard and put `title`/`journal`/`year`/
`first_author` on `CitationHint`. The rejected half is barely better: the message says "must contain at
least one PubMed ID" and never says the word PMCID, so it is a generic refusal where a specific one is
a fix — the same shape as `MISPLACED_COLUMN_REASONS` and `reject_reserved` one level down.

**2. A citation with no PMID at all** is *already tracked* and is not re-filed here: [§ 1.0 cleanup —
`StudyRow.pmid` required + PMID-shaped](ROADMAP.md#studyrowpmid-required--pmid-shaped) queues the requiredness
demotion to "≥1 of `{doi, pmid}`", and a PMC-only record (books, NIH reports, some datasets) is largely
covered by it, since such a record normally carries a DOI. What that entry does not say is what
`LiteratureRow` — keyed on `pmid`, digits-only, **required** — is supposed to do with such a row. That
is the piece which has to be decided in the same release, and it is the reason this item exists beside
the tracker entry rather than inside it.

**3. Only one direction of PMID↔PMCID is resolved, and the recorded reason only covers that
direction.** `literature._identifiers` reads `doi` and `pmc` out of the esummary `articleids` block, so
PMID → PMCID arrives free, and `literature.py`'s own docstring records that the **PMC ID converter is
deliberately unused** because of it (and separately that the converter is no existence oracle — its
"invalid article id" is about PMC *membership*). Both statements are true, and neither is about
**PMCID → PMID**, which is the direction the converter actually exists for. So a curator holding a PMC
id has no route through any of the three packages to the `pmid` every table keys on. Do not close this
by quoting the docstring back at it; it answers the other question.

**What can ship without the design round** — enricher plus `extract_pmids`, no schema change, no
verdict changed for anything else: refuse a digit run whose immediate context spells `PMC` in any
spacing, and **name the id that was seen** rather than the one that was missing. And where the record
does resolve, the pass already holds the PMCID from the same esummary response, so comparing it against
the authored digits catches the accepted-with-a-space case for free. Both are diagnosis, never repair —
nothing rewrites an authored cell.

**What needs the design round:** whether a PMCID is an *identity a citation may be authored under*, or
only a cross-reference the enricher fills. Three candidates, with their costs:

- **An optional `StudyRow.pmcid`.** Additive and minor-legal, and it closes the authoring half — but it
  leaves `LiteratureRow`'s key unanswered for a row carrying no PMID, and it puts a second id column on
  a table whose `pmid` is already free-form and may hold several.
- **Resolve every PMCID to a PMID at enrich time and store only PMIDs.** Smallest surface, and it
  silently drops the records that have none: two ways of returning nothing rendered as one sentence,
  which is S20 exactly.
- **Re-key `LiteratureRow` on a general citation id.** The honest shape, and it changes what an existing
  key *means*, so it is 1.0 and not this.

Whichever wins lands **with** the requiredness demotion, not before it — deciding the sidecar's key
while `StudyRow.pmid` is still mandatory answers a question no module can currently ask. Related:
RM47 makes the same observation from the other side, that a new PMID site obliges the literature pass
to learn it in the same release.


# 0.6 dogfooding — the fix round's own findings, repaired

Round 2 of [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md) came from *reading the code around each
repair* rather than from building a module, and the thirteen findings that needed action were numbered
RM74–RM79 on 2026-08-14. What follows is what shipped, in the order it was worked.

## RM74 — the drafting providers read their sources wrong, and the test that would have caught one does not run

**Severity** high (one member) · **Status** ✅ shipped · **Owner** enricher · **Found by** code review
during the 0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-1, R2-11, R2-3

Three defects, one read each and one loop, all in `clinpgx_draft._rows_from_snapshot` and the test file
beside it.

**ClinPGx's `gene` is `;`-multi-valued** (R2-1). Re-probed against the provisioned snapshot before
touching anything: **396 of 16,087 rows** carry a `;` (`IFNL3;IFNL4` ×51, `ANKK1;DRD2` ×24,
`CYP2A7P1;CYP2B6` ×18), and `--gene VKORC1` dropped the **3** rows of `rs17886199`, published as
`PRSS53;VKORC1`. The filter now matches per member. The `;` separator was already a named constant —
for `drugs` — which is the part worth keeping: one dialect, two columns, and only one of them read it.

**What is *written* for a plural cell was the one real choice here, and the three candidates are not
equally wrong.** Writing the cell verbatim is what shipped until now, and it is a non-symbol in a
column described as *"Gene symbol, e.g. VKORC1"* — every consumer's gene filter misses it for exactly
the reason ours did. **One row per gene is illegal, not merely undesirable**: `gene` is *outside*
`PharmVariantRow`'s dedup key, so the copies collide on
`(variant_key, drug, genotype, phenotype_category, annotation_id)` and the compiler refuses the module
— which is the structural difference from `drugs`, which *is* in the key and therefore legitimately
becomes one row each. And **picking from the cell alone has no rule to pick by**: the pharmacogene is
first in `CYP3A5;ZSCAN25` and second in `ANKK1;DRD2`, `CYP2A7P1;CYP2B6` and `PRSS53;VKORC1`, so
position orders nothing and "the one that matters" is a pharmacological judgement this tier does not
make.

What shipped is the CPIC `gene.chr` move — a **lookup in what the caller already stated**. Under
`--gene VKORC1` the request selects exactly one member and writing it asserts only what the source
asserts. With no request, or with a request selecting two members of one cell, nothing selects, and
the answer is the house one: **withhold, and say which genes the cell named**, aggregated by cell so a
panel-scale draft does not print one line per row. An empty cell reads as *not stated*, which is
weaker than the truth; the joined cell is false about its own column.

**`skipped_unidentified` counted the wrong denominator** (R2-11). The rsID check ran before the
`--gene` filter, so a record with no rsID from an unrequested gene incremented it, and on any
`--gene` draft the "records the source could not identify" number was inflated by the rest of the
database — destroying the one thing it is for, judging whether coverage of *your* gene is poor. The
filter moved above it; every skip counter is now scoped to the requested set.

**A test's stated coverage was not exercised** (R2-3). `test_draft_declared_build.py` built its
fixture with a nested `"location"` key while `cpic.defining_variants` reads `"sequence_location"`, so
the dict was always `{}` and the file's claim to cover "one defining variant carrying a coordinate"
was hollow — the drafted `haplotypes.csv` did not exist and the file passed either way. Third
instance of the class after S21's registry and D6-2's `_MOVABLE`. Fixed with the key **and** an
assertion that the coordinate reaches the file, which is what makes the key load-bearing; demonstrated
by restoring the old key and watching the new assertion fail on a missing `haplotypes.csv`.

## RM75 — a complete result is destroyed by an incidental failure, and one handler cannot see its own case

**Severity** medium · **Status** ✅ shipped · **Owner** enricher · **Found by** code review during the
0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-13, R2-4, R2-2

**A client that leaks its transport library's exception type has no contract** (R2-13). `CpicClient._get`
called `raise_for_status()` and wrapped only *shape* failures into `CpicError`, so once retries were
exhausted a raw `httpx.HTTPStatusError` walked through both of `enrich_pgx`'s per-leg handlers — the
handlers written under the comment *"One source failing must not sink the pass — the other may still
answer"* — and took PharmVar's answer with it. The retrying request is now `_request` and the
translating wrapper is `_get`, in that order, because wrapping *inside* the retry would defeat it:
`retry_if_exception_type` tests `httpx.HTTPStatusError`, and a `CpicError` raised there is a
first-and-final attempt. A test asserts the ladder survived the split, since a decorator on the wrong
half turns three attempts into one and nothing fails.

**The same hole was on the PharmVar leg and the ledger named only CPIC.** Repairing one and not the
other would make that comment true in one direction, so the guarantee would hold or not depending on
which source went down — worse than either state. `PharmVarClient` got the identical split; its 401
branch stays inside `_request`, because that is a *diagnosis* raised before the status check rather
than a translation of one, and it must not be retried.

**An optional message-enrichment call could discard a finished draft** (R2-4). `pgx_draft` asks
`cpic.knows_drug` inside the `try` whose `finally` closes the client — deliberately — but by then the
alleles, diplotypes, defining variants and every recommendation have already returned. `knows_drug`
exists only to tell a typo apart from a real drug CPIC scores in a shape this table cannot hold (F5),
so a transport failure there threw away complete work to improve a sentence about it: the gnomAD rule
(a per-item error must never sink a batch) in a different tier. It is caught now, and the `bool | None`
tri-state that was *designed and never delivered from the live client* is finally reachable from it.

**A third reading of "could not establish" earned its own sentence rather than reusing the second.**
`known is None` already meant "the snapshot's recommendation table cannot answer this", whose remedy is
to go live; a failed request is re-runnable. Folding them would put the snapshot's wording in front of
an author who has no snapshot.

**An ordinary mid-authoring state tracebacked** (R2-2). F1's repair routed `draft` and `draft-panel`
through `source_build_mismatch` → `spec_genome_build`, which deliberately raises `EnrichmentError` on a
present-but-unreadable `module_spec.yaml`. Neither CLI named that exception, so a spec carrying only
`name:` turned `draft-panel --gene PALB2 --offline` into a rich traceback where every other enricher
command exits with a message. The presentation regressed *because* the build defect was fixed, which is
the shape worth naming: a shared precondition added to three providers owes the same addition to each
of their handlers. `_DRAFT_PRECONDITION_ERRORS` is what makes the fourth provider inherit it instead of
rediscovering it.

**And the raise moved to the top of both providers.** It landed *after* `_resolve_snapshot` had
provisioned a published ClinVar snapshot and after every CPIC query, for a check that reads one file
beside the spec. The warning is still appended where it was, so no reported order moved.

## RM76 — an unfinished authoring state passes every gate, including `--strict`

**Severity** high · **Status** ✅ the narrow repair shipped; **the general question is
[RM73](ROADMAP_HISTORY.md#rm73-phase-boundary--authoring-is-a-process-and-it-now-has-an-end)**
· **Owner** format + compiler · **Found by** the 0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-8

`SourceRow` is a plain `BaseModel`, not an `AuthoredModel`, deliberately and for a stated reason: it is
a machine-produced reference fact, grouped with `ResolutionRow`/`FrequencyRow`/`GeneMetricsRow`/
`LiteratureRow`. S21 then made it **draftable**, also deliberately, because it is *"the only fact
sidecar a human writes"* and the only table the compile licence gate reads. Nobody reconciled the two,
and the gap is exactly the shape of both decisions being right.

Re-probed on `reference_examples/hfe_hemochromatosis` with `source=<<REPLACE>>`: the module **compiles
green under `--strict`** and `manifest.sources` publishes `"sources": ["<<REPLACE>>"]` inside the block
its own `signature` covers. The compiler's only remark on that file was that `sources.csv` is the
deprecated spelling.

**What shipped: the guard, on the model rather than through the base.** `ModuleSpecConfig` is the
precedent — standalone for its own reasons, carrying its own `reject_template_placeholders` all the
same — so the classification stays true and the other four sidecars stay out, since no template is ever
generated for them. It refuses in **both** modes, which is not a choice: a load error is fatal in both,
and it is what every other authored table already does with the same token.

**Why a vocabulary column was hiding it, and why that matters twice.** `layer` refuses `<<REPLACE>>` as
a non-member, so a stub in *that* cell was caught by accident; `source` is free text by design, and
free text is most of this table. The accident is also what made the **first draft of this item's own
test green on the unfixed code** — asserting "some error mentions `<<REPLACE>>`" is satisfied by the
vocabulary message quoting the token back. The test now asserts the guard's own wording, and a second
one isolates the real hole: a valid `layer` with only `source` stubbed. A guard green because a
different mechanism happens to fire is the S21 / D6-2 / R2-3 shape arriving inside the repair for one.

**And the guarantee is now asserted, which it never was.** `draft.stub_template`'s docstring prints
*"an unreplaced stub **cannot compile** — `vocab.reject_template_placeholders` refuses it by name and
row, in both modes"*, and nothing checked it; it held only where a model happened to inherit the right
base. The new test is parametrized over `DRAFTABLE` rather than naming kinds, because the defect was a
model quietly outside a set and a hand-written list would have to be extended by whoever forgot the
base class. One `test_hints` docstring stated the old behaviour as a reason and is corrected in place
rather than deleted — the correction is the useful part.

Nothing in the corpus moved: a `mode="before"` validator that only raises changes no accepted value,
verified against the `artifact.digest` / `content_signature` values recorded independently in
ROADMAP_0_7 and CLAUDE.md.

**What is not closed.** *"A generated stub must be unable to compile"* is now true and now tested, but
it is still a property that holds because each model was individually given the right guard. What marks
authoring as **unfinished** — as opposed to marking one token as unreplaced — reaches this from
underneath, and that is RM73's phase boundary — a sprout repaired a day before its root, which closed on
2026-08-16 with `just-dna-compiler close`. Note what the two do and do not cover between them: a closure
says the author declared *these bytes* final, and the guard here says one particular token cannot survive
into a compile. Neither says a cell is right, and neither is the other's substitute.

## RM77 — the genotype diagnosis tells the author about the wrong thing

**Severity** medium · **Status** ✅ shipped · **Owner** format · **Found by** the 0.6 dogfooding fix
round, 2026-08-14 · **Ledger** R2-9, R2-14

**A genotype pasted out of a VCF was refused without anyone naming allele indices** (R2-9). `GT` is
`0/1`; `genotype` wants the bases. Re-probed on all the spellings: `0/1` and `0|1` fell through to the
nucleotide-grammar wall — a sentence reciting what an allele may be (nucleotides, `*`, a symbolic
token whose first-level type is one of five) that never says the one thing that resolves the cell.
This is the single most likely mistake an author makes here, because pasting the `GT` field is the
obvious first guess.

`0/1/1` was **worse, and 0.6 made it worse**: the ploidy-message fix gave it a confident, correct
explanation of the two-allele ceiling, which is about the wrong thing — that cell's defect is the
notation, not how many alleles it names. A correct sentence aimed at the wrong defect is worse than a
generic one, because it sends the author to change the wrong cell. So the diagnosis runs **ahead of
the arity branch**, and a test pins that a genuinely polyploid call spelled in bases still gets the
ceiling explanation and this one does not.

The repair is CLAUDE.md's standing shape — a generic rejection is a dead end where a specific one is a
fix — and it **changes no verdict**: every cell it matches was already refused. `_GT_INDEX_CELL`
matches a cell whose every member is a digit run or VCF's no-call `.`, which nothing legal can look
like: `ALLELE_PATTERN` is `^[ACGT]+$`, a symbolic allele is bracketed, and `*` is one character. The
message names what to translate *against* (the record's own REF and ALT) and says those cannot be
resolved here, since a genotype cell carries neither. It reaches `PharmVariantRow` for free, because
the grammar has lived on `AuthoredModel` since 0.5 — pinned, since a diagnosis added to one arm of a
shared validator is the drift that move exists to prevent.

**RM63's correction was itself an overclaim, and it is the third turn of one screw** (R2-14). The
comment read *"Read a pipe here as **heterozygous**, phase recorded but unaddressable"*. Probed:
`VariantRow(genotype="C|C")` loads, and `1|1` is an ordinary phased homozygous call, so the sentence
was false of a genotype the model accepts. The history is the finding — the original comment claimed a
pipe encodes which homolog an allele sits on; RM63 refuted that correctly and replaced it with an
unchecked claim about *zygosity*; the 0.6 unit carrying the wording onto the printed `describe` output
dropped the zygosity word and kept the true half, so the **printed contract has been right since then
and only its source was wrong.** A correction is exactly where this happens: the reviewer checks the
claim being removed, not the one going in. The comment now says only what RM63 established, keeps the
history of both wrong versions, and a test pins that `C|C` loads so there is no fourth turn.

## RM78, the two fixes — the unobservable marker, and a guard that answered its own question wrong

**Severity** medium · **Status** ✅ both fixes shipped; **the R2-5 decision stays open in
[ROADMAP.md](ROADMAP.md)** · **Owner** format + compiler · **Found by** the 0.6 dogfooding fix round,
2026-08-14 · **Ledger** R2-6, R2-10

**`*` landed in the compiler's indel bucket** (R2-6). 0.6 gave the symbolic class its own permanent
reason in `_vrs_gap_reason` and `_recompute_vrs_id` and guarded `*` and `.` on the *enricher* side, and
neither compiler function was told — so an unobservable allele in `resolution.csv`'s `alts` was
reported as *"an indel or MNV … re-run it online"*: the same false class D1-2 had just fixed for
symbolic alleles, one axis over, offering a remedy that can never apply.

**Filed as having no instantiation and upgraded when it turned out to have one.** The reasoning was
that nothing writes a `*` there today; the unit fixing D1-1 then probed `LiteralSequenceExpression`'s
pattern — `^[A-Z*\-]*$` — and found `*` **passes**, so before the enricher guard an unobservable allele
reaching the minter would have been normalized and handed a content-addressed id for a state that is
not a sequence. *"Nothing produces it today"* is a fact about the wiring, never about the function:
RM38 and `VALID_RSID_STATUS.withdrawn` already carry the same lesson.

Three classes now, not two, and the split is P5's rather than a convenience: `parse_symbolic_allele`
asks *which variant is this, unspelled*, and `is_unobservable_allele` asks *whether the call could see
an allele at all* — the callability axis. **Severity could not have caught this**, which is why the
test asserts the reason: the indel branch it fell into is also tier-blame, so the verify matrix read
`warn` before the fix and after it.

**`refget_supports_build` answered `True` for the two inputs `refget_accession` raises on** (R2-10).
Its docstring says it is *"the question `refget_accession` raises on"*; for `GRCh37` the two agreed and
for `None` and `""` they did not. Latent, because the one caller filters `if row.genome_build` first —
but it is public in the schema tier and it is the guard a caller reaches for *precisely* to avoid that
exception, so the first caller handing over an unset build got what the guard exists to prevent. Same
class as the `start` docstring: a printed claim the code does not honour, in the tier the other two
build on.

**Which side moved, and why that was the real question.** The old reasoning was *"an unset build is the
format's default, not an unbuilt assembly"* — which imports a fact about the **spec** layer into the
**identity** layer. `ModuleSpecConfig.genome_build` does default to GRCh38, and so does each of these
functions' own *signature*; but an explicitly passed `None` is not an omitted argument, it is a caller
who has not threaded the row's build through — the bug class `test_build_call_sites.py` walks the AST
to prevent. Every other build gate in `vrs` (`in_pseudoautosomal_region`, `par_partner`,
`contig_length`, both minting functions) already withholds on anything that is not literally `GRCh38`,
so answering `True` made this one function the outlier rather than the rule. Both now read one
predicate, so RM15's second table cannot re-open the gap.

## RM78, the decision — a stored VRS id against a symbolic allele is the row's contradiction

**Severity** medium · **Status** ✅ decided and shipped 2026-08-15 · **Owner** format + compiler ·
**Ledger** R2-5

`_recompute_vrs_id` returned **tier-blame** — a warning in both modes — for a symbolic allele carrying
a `ga4gh:VA.…`. Tier-blame exists for a finding **no authored edit could clear** (P5, the rule that
also keeps `not_covered` and the coverage warnings out of the `strict` gate), and deleting the cell
clears this one. So the finding was filed in the class whose own test it fails.

**Decided: escalate to row-blame — an error in both modes — but settle the grammar first.** That order
was the point. The escalation only follows if a present id can *only* be a VA minted for a different
allele, and nothing had established that: `vrs_id` was validated for well-formedness alone
(`ga4gh:<TYPE>.<digest>`, five types), while its description says *"GA4GH VRS allele id
(`ga4gh:VA.…`)"*. Changing severity before answering that would have been a verdict resting on a
premise the schema did not state.

**The grammar step.** `validate_vrs_allele_id` makes `ResolutionRow.vrs_id` and `FrequencyRow.vrs_id`
`ga4gh:VA.`-only, and names the type it got when refusing. Three things about it:

- **It makes no passing module fail.** A `ga4gh:SL.…` already reached `_verify_vrs_ids`, which
  recomputes with `derive_vrs_allele_id` (always a VA), and was reported as a **mismatch** —
  *"recomputed and different, so corruption"* — an error in both modes with the wrong explanation. The
  tightening moves a confident wrong diagnosis to load time.
- **No instantiation**, which is the test this repo applies to a tightening (the IUPAC probe is the
  precedent): nothing mints a non-VA into either column, and a probe across all sixteen reference
  examples found **844 ids, every one `ga4gh:VA.`, zero of the other four types**.
- **`validate_vrs_id` keeps its lenience and its documented reason.** What was wrong was using a
  *format* check where a *column* rule was meant — "is this a well-formed VRS id" and "may this column
  hold one" are different questions, and only the first should be generous.

**The escalation.** With the column VA-only, a recorded id on a symbolic row can only be a VA for some
other allele: a false content-addressed claim, catchable offline, the same class as *inconsistent
reference allele* and *an id recorded against no ALT*. The message says which cell to delete and that
the allele keeps its identity through `variant_key`, so the remedy is one edit and loses nothing.

**The asymmetry that must not be flattened, and it is now pinned by a test.** The *coverage* side
(`_vrs_gap_reason`, `_vrs_coverage_warnings`) still reports a symbolic allele as a permanent gap and
**warns in both modes**. An absent id there is the ordinary, correct state — no tier can mint one — so
refusing would make every structural module uncompilable for a reason no edit could fix, which is the
P5 class this whole item is about. *Absence is a limit; a claim is a claim.* `mt_common_deletion`,
`cyp2d6_structural` and `pathogenic_clinvar` still compile under `--strict`.

## RM79 — two honest counters disagreed, so the compiler stopped carrying the dead weight

**Severity** low · **Status** ✅ shipped 2026-08-15 · **Owner** compiler · **Found by** the 0.6
dogfooding fix round, 2026-08-14 · **Ledger** R2-16

`manifest.literature.missing_count` counted `exists is False` over **every row in `literature.csv`**;
the `citation_existence` verification record counted over the citations the module makes **now**.
`literature.csv` is merge-not-clobber, so it keeps a row for a citation since deleted from
`studies.csv`, and the two numbers then disagreed in a published manifest with nothing wrong in the
module. Each was right about its own subject, which is what made it a decision rather than a repair.

**What the item asked was the wrong question, and probing showed why.** It framed the choice as
*should `manifest.literature` describe the table it is named after, or the module's current
citations?* — and both blocks already publish their own denominator (`row_count`, `subjects`), so a
reader could in principle reconcile them. The thing nobody had decided was upstream of the counting:
**why is a row nothing joins to in the artifact at all?**

**Decided: the compiler discards it, and `literature.csv` keeps it.** A literature row for a citation
no study and no bin names is dead weight — nothing in the module references it, and it is present only
as a side effect of merge-not-clobber. That rule is right and stays: the CSV is the pin that makes a
re-run cheap. Carrying the row onward into `literature.parquet` and `manifest.literature` was a
separate thing nobody had chosen. `split_cited_literature` is the one rule both the check and the
materializer read.

The counters then agree **by construction** rather than by documentation, which is the part worth
having: no reader has to reconcile two numbers, because there is only one subject.

Four things to keep straight:

- **The check sees every row; everything after it sees the kept ones.** Reporting what was dropped
  needs the full list, so the split happens after the cross-check rather than at load — and the
  warning now reports an *action taken* ("left out of the artifact, and left in the CSV") instead of
  nagging about a file the author is not expected to tidy.
- **An empty citation set discards nothing**, and that guard is not the degenerate case it looks like:
  a module citing nothing at all cannot tell "the sidecar is stale" from "the citations are not
  authored yet", and emptying the table on the first reading would delete a whole enrichment pass's
  output. The orphan check already had the guard; the filter inherits it rather than re-deriving it.
- **Both citation sites count** (RM47), and the stakes went up. Blind to bin `pmid`s the compiler used
  to *warn* about a threshold-grounding citation; it would now **discard** the row that evidence lives
  in. `test_citation_sites` pins the split against both sites for that reason.
- **The round trip narrows once and converges.** `reverse_module` rebuilds `literature.csv` from the
  parquet, so a reversed copy carries the kept rows only — a deterministic narrowing of a
  machine-written derived sidecar rather than a P7 breach (the RM69 reading of the principle's letter),
  and lap two discards nothing, so the signature is a fixed point. Pinned by a test, because a
  narrowing that kept narrowing would be a defect whatever the sidecar's status.

Nothing in the corpus moved: no reference example carries an uncited literature row, verified by
recompiling all sixteen. Which also means the corpus cannot exercise this — the standing
corpus-uniformity trap — so the behaviour is pinned by fixtures rather than by an example.

## RM73 (phase boundary) — authoring is a process, and it now has an end

✅ **Shipped in 0.6.0** (2026-08-16), completing the item; the provenance half below shipped the same
day. What remains of RM73 is not a half but a **promotion**: making a closure a *precondition* of
compiling is major-only under P8, it is filed in
[ROADMAP_1_0 § RM73 (gate half)](ROADMAP_1_0.md#rm73-gate-half--the-closure-gate-refuses-on-step-3-of-the-round-trip),
and it is **blocked** there for a reason found while building this — see the last section.

**What was missing was one sentence's worth of state.** RM45 had already built almost all of it for a
different purpose: `verification.json` binds `module_hash` over the authored files, the compiler
recomputes that binding on every compile, and a mismatch drops the whole block with a warning. So
change-evidence over the authored set had been shipping since 0.6 — what nobody had is a record saying
*a human declared this finished*, because the document was written as a **side effect of a pass
running** and therefore only ever said "the enricher ran".

**What shipped: `Closure`, `just-dna-compiler close`, and a warning.** `VerificationDoc.closure` is an
optional block (`closed_at`, `closed_by?`, `signature?`), `close_module` writes it, and both
`validate_spec` and `compile_module` report a module that carries none. Five decisions worth keeping:

- **No new file, no new binding, no new proof-of-work.** The closure rides the attestation, so an edit
  after closing un-closes the module for free; a free-standing `closure.json` would need its own
  staleness rule and would be dropped silently by `reverse` (the RM51 class). It sits **outside**
  `pow_digest`'s payload, so closing re-mines nothing and every attestation written before 0.6 still
  verifies. Measured: all sixteen reference examples compile to a byte-identical `artifact.digest` and
  `content_signature` before and after being closed.
- **Deliberate, never a side effect.** `validate` stays read-only however cleanly it passes, because a
  mark left by whatever happened to run reproduces the exact defect this item levels at
  `verification.json`. `--private-key` signs the closure over `module_hash` with the same
  `signing.sign_digest` the artifact signature uses, which turns *someone closed this* into *this
  party closed this*. Unsigned stays legal and still change-evident — tamper-*evidence* was always the
  guarantee on offer.
- **Refuses an invalid spec; does not refuse on a warning.** Declaring finished a set the compiler will
  not accept is a contradiction. Declaring finished one that carries an unresolvable rsID or an
  ungrounded threshold is ordinary, and refusing there would make closure unreachable for exactly the
  modules whose findings no authored edit can clear (P5, the `not_covered` class).
- **The enricher's merge had to learn it, and this is the never-clobber trap a third time.**
  `record_verification` rebuilds the document rather than editing it, so it dropped the new field by
  default — silently, and in the wrong direction, since enrichment writes only derived sidecars and the
  ordinary case is a closed module staying closed. It now carries the closure across **only while the
  binding holds**, and drops rather than re-binds it otherwise: re-stamping would have the machine
  assert on the author's behalf. Same shape as `SourceRow.dataset` and `draft_digest`, one column over.
- **Absence warns; a false claim drops the block.** No closure is the state every module was in before
  0.6, so it is a warning in both modes, never `strict`-gated (an unclosed module is perfectly
  reproducible). A closure that is *signed* and whose signature does not verify drops the whole
  document — absence is a limit, a claim is a claim.
- **Closing adds a block to the document; it does not rebuild one.** The first version re-attested,
  which rewrote `producer` from `just-dna-enricher 0.6.0` to `just-dna-compiler 0.6.0` on the three
  reference examples that carry real check records — a field naming who put the *checks*, so the
  compiler was claiming an enricher's cross-checks as a side effect of an unrelated act. Found by
  reading the corpus diff rather than by a test, and now pinned by one. Keeping the document verbatim
  is also what makes *closing re-mines nothing* literally true rather than nearly so.

**Whether compile should warn on absence was decided twice, and the second answer was right.** The
first analysis argued for silence, on the grounds that `reverse` cannot re-emit the document, so a
closed module's `compile → reverse → compile` warns on step 3 where step 1 was silent — and RM44 made
`manifest.compilation.warnings` a surface consumers parse. That was overturned by two facts. The
divergence **costs nothing enforceable**: `artifact_digest` is a Merkle root over `_OUTPUT_FILES`,
which is parquet only, `manifest.json` is not in it, warnings feed no signature, and no round-trip test
compares them. And with no warning, the closure has **no consumer in 0.x at all** — the manifest field
would be read by a catalog that does not exist yet and by nothing else until 1.0, which is the
designed-and-never-delivered shape that let the `knows_drug` raise escape. So the corpus was closed
instead: all sixteen reference examples ship a closure, with a test asserting each one is still current
so an authored edit fails loudly rather than degrading into a *stale* warning nobody reads.

**And that probe is what blocks 1.0.** Warnings being free is a fact about warnings; a **refusal** is
not free. Under the planned gate, a reversed spec is unclosed by construction — reverse rebuilds from
parquet and the document is not there — so `compile → reverse → compile` would refuse on step 3 for
every module, and P7's round trip is enforced by tests. The obvious repair is closed too:
`manifest.verification` carries the records but not `difficulty`/`nonce`, so reverse cannot rebuild a
valid document from the artifact it holds. Three candidate answers are recorded, undecided, in
ROADMAP_1_0 — and the reason this was worth writing down rather than discovering later is that
`verification.json` has carried the identical asymmetry since RM45 without consequence, so the
precedent is silent about the danger.

---

## RM73 (provenance half) — a drafted value that has not moved is a copy that can be *established*

✅ **Shipped in 0.6.0** (2026-08-16), alongside the phase boundary above; this is the half the sprouts
were actually asking for, and it landed first because it needed no phase boundary to answer.

**The problem, restated at the size that shipped.** RM4's tautology skip exists because a panel
drafted from ClinVar carries ClinVar's own `clin_sig`, so the cross-check compares a value against
itself and reports a zero that *looks like evidence*. The skip was keyed on a module-level marker (the
release stamped into the licence row) because that was the finest grain available, and RM4 named the
hole in its own warning text: a cell edited after the draft is no longer a copy, and no module-level
fact can see it. The expensive repair — `strict` looking every row up — is the validation-by-
duplication route this item had already argued against.

**What shipped: one digest per drafting source, over the projection the check actually reads.**
`enricher/provenance.py` holds three entries — `clinvar`/`variants.csv`/`clin_sig`,
`cpic`/`allele_function.csv`/`function_status`, `clinpgx`/`pharm_variants.csv`/`evidence_level` —
each naming the table, the identity cells and the checked cell together. The provider hashes it and
stamps `SourceRow.draft_digest`; the check recomputes it and compares. Six things worth keeping:

- **The projection is a COLUMN, not a row, and that is what makes it work at all.** A
  `clinvar_draft` module always has edited rows by construction — `genotype` is a placeholder the
  human is *required* to fill — so a whole-row hash is invalidated on every drafted module and the
  skip would never fire once. Scoping to the checked column makes the digest exactly as sensitive as
  the question: filling a stub does not disturb it, editing a `clin_sig` does. Pinned by a test.
- **Raw CSV cells, never loaded models — forced, not stylistic.** One function serves both sides,
  because a writer and a reader that computed this differently would not fail, they would silently
  never match (`clinvar_dataset_label`'s lesson). That function must therefore run at *draft* time,
  when the table is full of `<<REPLACE>>` and `reject_template_placeholders` refuses to load it by
  design. So `variant_key` and `effective_clin_sig` are unavailable and the identity is spelled as
  the raw cells the provider already matches on.
- **The skip is a CONJUNCTION, and shipping only the digest half would have been wrong.** The digest
  hashes the module's table, not the snapshot, so it is silent about currency: a matching digest
  against a *newer* release is a real comparison. Skip requires the recorded release to match **and**
  the digest to match. A consequence worth stating: a check run against a **live** source never
  skips, because there is no release to name.
- **`merge_sources_file` would have eaten it.** Never-clobber is right for terms a curator may have
  hand-written and wrong for a machine-stamped cell that must track the table — the same rule that
  bit `dataset` and produced `withdraw_stale_dataset`, arriving on the neighbouring column one
  release later. `stamp_draft_digest` restamps explicitly. Unlike `dataset` it **re-labels rather
  than withdraws**: a release label cannot name two releases, so a mixed module has no honest value,
  while a digest describes the table as it now stands whatever produced it.
- **Two unmarked tautologies closed, neither previously filed.** `pgx_draft` writes `function_status`
  out of CPIC and `pgx._function_conflicts` compares that column against CPIC; `clinpgx_draft` writes
  `evidence_level` out of ClinPGx and `clinpgx` compares that column against ClinPGx. Both were
  publishing a structurally guaranteed `findings=0` into `verification.json` — RM4's misinformation,
  now inside RM45's proof-of-worked attestation, which is a stronger claim than a warning line. CPIC
  was additionally the one provider recording **no `dataset` at all**, so it now stamps one.
- **In `enrich_pgx` the tautology is a PER-LEG outcome.** That check has two authorities: on a
  CPIC-drafted module the CPIC leg cannot fail while PharmVar's is genuinely independent. The
  existing `legs` dict already carried one outcome per authority, so the CPIC leg records `tautology`
  and PharmVar still runs. A whole-record skip would have discarded a real comparison to suppress a
  hollow one — precisely the expressiveness the module-level marker shape lacked. `tautology` sits
  **last** in `_SKIP_PRECEDENCE`: the other members say the source could not be consulted, and an
  absence a reader can act on outranks a comparison that could not have failed.

**The removal, which is the point as much as the addition.** `ClinSigAudit` and the
copied/authored/no_record bucketing are gone, with `EnrichmentResult.clin_sig_audit`, its CLI line
and the `mode != "strict"` branch in `enrich()`. The bucketing existed for exactly one reason — the
module-level marker could not see a per-row edit, so `strict` paid for a lookup to recover the split
— and the digest answers that offline. **The mode ladder collapsed with it**: this check now behaves
identically in both modes, which is what RM4 wanted and could not have, and `strict` stops meaning
"pay for a per-row lookup", which was never a reproducibility axis (P5). Removing it changed no
verdict: the `copied` bucket was an early exit taken *before* the camp logic, and an exact match
agrees with itself, so every row it caught already reached "no conflict" by the path below it.

**The honest limit, stated rather than discovered.** The digest covers the whole table, so it means
*no checked value has changed since the drafter last wrote*. A row hand-authored **before** a
subsequent re-draft is covered by the new stamp and escapes the check. Strictly narrower than what it
replaces — today's module-level marker lets *every* hand-edit escape — and unlike today any later
edit re-enables the check in full.

**Behaviour change worth reading twice.** A licence row naming the right release but carrying no
digest **no longer skips**. Nothing that was being checked stopped being checked; a module that was
being waved through on a claim is now examined. Its test says so by name.

**Identity effect, measured.** `draft_digest` is deliberately **outside** `SOURCE_FACT_FIELDS` —
`dataset` is inside it because which release these annotations came from is part of the claim the row
makes about the source, while this is a fact about how the module was *built* and moves on every
re-draft. So `sources.signature` moves nowhere, and `content_signature` is untouched
(`pgx_slco1b1_simvastatin` still `sha256:8173dab7…`). A recompile's `artifact.digest` moves for any
module carrying a licence table, since `sources.parquet` gains a column — the additive case P4 scopes
to a fixed `compiler_version`.

## RM80 — `annotations.parquet` had no column for the thing that distinguishes its rows

✅ **Shipped in 0.6.0** (2026-08-16), retro-filed. **Reported by a downstream consumer**, whose note
is the cleanest statement of it: `variant_key` is not unique in that table, so every consumer must
dedup before joining — *either the table should be unique per `variant_key`, or it should carry the
genotype that distinguishes its rows.*

The first option is impossible and the reason is already recorded here: a genuine poly-effect variant
is one locus carrying two annotations, which is why the table was re-keyed on the variant-effect pair
`(variant_key, conclusion, negatives)` in the first place. So the answer is the second — except that
the authored column which decides *which call an annotation applies to* was in no column at all. A
het "carrier" row and a hom "affected" row at one locus could be told apart only by reading the prose
in `conclusion`.

**Carrying it without keying on it would have been worse than the gap**, which is why this is one
change and not two. Two genotypes sharing a conclusion (`C/T` and `T/T` both "carrier") collapse under
the old key, so the surviving row would name one genotype while silently standing for both, and a
consumer filtering on it gets a *wrong* answer instead of a missing one. With `genotype` in the key
the dedup is provably a no-op — `(variant_key, genotype)` is `VariantRow`'s own natural key and
`_cross_validate_variants` rejects duplicates on it — so the table is now exactly one row per authored
variant row. The dedup is kept anyway rather than deleted, because the function must not silently
depend on a guarantee another function enforces.

Two mechanics. Reverse now reads **which** generation of the table an artifact carries
(`ann_key_columns`, derived from the columns present) instead of one bool — three keyings are in the
wild and the old two-branch detection could not express a third; both legacy branches are preserved
exactly. And the genotype reconstruction had to move **above** the annotation probe, because
`weights.parquet` stores the allele list plus a `phased` bit rather than the authored cell, so the
string has to be rebuilt before it can be joined on.

A parquet column is ~free under the 2026-08-13 charter amendment (materialized, derived, no human
types one), which is what makes this a minor rather than a deferral. `content_signature` does not
move; a recompile's `artifact.digest` does, for any module carrying `variants.csv`.

# 0.6 — what answering S35 closed

One item, and it is the shape the triage loop exists to produce: an entry filed with a genuinely open
question, the consumer answering it the next day, and building the answer finding a defect underneath
that neither side had stated. Filed 2026-08-17, closed 2026-08-17.

## RM89 — the publisher cannot upload a table-only module at all

✅ **Shipped in `just-dna-compiler` + `just-dna-enricher` 0.6.0** (2026-08-17), the day after it was
filed, unblocked by [S35](CONSUMER_SUGGESTIONS_HISTORY.md) from just-dna-lite. **Owner** enricher
(`upload._REQUIRED` / `_ALLOW_PATTERNS`) + compiler (a public name) · **Motivating case** seven of the
sixteen reference examples

`upload._REQUIRED` was `("weights.parquet", "annotations.parquet", "studies.parquet")` and `plan_upload`
raised `FileNotFoundError` when any was absent. The comment above it said *"weights/annotations/studies
are what discovery needs"*, and that premise expired when RM2 made the SNP core optional in 0.4: a
module carries only the table kinds it uses, so a module with no `variants.csv` produces none of the
three and could not be published by this tier at all. `fmr1_cgg_repeat` was the instructive one — it has
`studies.parquet` and lacks the other two, so the rule was *"not all three"*, not *"no SNP core"*, and
the obvious repair (**exempt a module with no `variants.csv`**) would still have refused it. Same class
as RM55's `_INTEGER_KINDS`: a rule whose premise the format withdrew, left standing.

**The open question was genuinely open, and it was not ours to answer.** Whether the required set should
become *"`manifest.json` plus at least one parquet"* or drop the parquet requirement entirely depends on
what the consuming discovery path actually opens. It was asked of just-dna-lite alongside RM84's two
questions rather than guessed. Their answer: `_find_lead_table` probes `{base}/{family}.parquet` across
ten lead families and returns the first hit — that single existence probe **is** their "is this a
module" test — and `manifest.json` is not opened by discovery at any point. So of the two candidates,
manifest-plus-at-least-one-parquet is the one a consumer can use.

### What answering it found, and it is larger than the item

**`_REQUIRED` was not the only gate.** The allowlist handed to `upload_folder` was `*_REQUIRED` plus
`manifest.json`, the two logo spellings and `README_CANDIDATES` — so **not one 0.4 family and not one
derived-fact table was in it**. Relaxing `_REQUIRED` alone would have converted *"a table-only module
cannot be published"* into *"a table-only module publishes as `manifest.json` + README with no data"*,
which is a worse failure because it is silent and leaves a directory behind. just-dna-lite found this
half from the other end: `sources.parquet` is not in the allowlist and they read it, so a module
published through this tier arrived with its licence terms missing and their report footer rendered
*"Not stated"* — correct for what they received, and the derivative-work obligation gone with the bytes.

**The consequence neither side had stated, found by probing rather than by reading.**
`manifest.artifact.files` lists a name, a sha256 and a size per parquet, and `artifact.digest` is a
Merkle root over exactly those — so a file attested and not uploaded makes the published manifest a
false claim about bytes that are not there, and the digest cannot be reproduced from what arrives.
Measured over the sixteen reference examples, compiled and run through `plan_upload`: **seven refused
outright, and eight of the remaining nine published an artifact whose own digest did not verify**
(`hboc_palb2` dropped six parquets). Only `grch37_build` — a bare SNP core with no sidecar and no
0.4-family table — was correct. Fifteen of sixteen, on a surface where the failure is silent. Stated
honestly: nothing is known to have been published through it, so this is *would publish*, never *has
published*.

### What was built

**The allowlist is derived, never hand-kept.** `_OUTPUT_FILES` became public as
`compiler.ARTIFACT_PARQUETS` and the publisher imports it, so a new table family reaches the publisher
in the commit that adds it. This is `@fieldnames-from-model` one tier further out, and it is the
property the consumer explicitly asked to have preserved from their own shipped version of this fix.
`LEAD_PARQUETS` is the companion — `weights` plus the nine 0.4 families, matching what their
`_find_lead_table` probes.

**Three positive rules replace the required triple**, ordered most specific first so a refusal names the
actual fault (`@specific-rejection`): the plan must carry every file `manifest.artifact.files` attests;
`weights.parquet` never travels alone (the consumer's `_EXPECTED_WITH_WEIGHTS`, kept and scoped exactly
as they scoped it, since a `pharm_variants`-led module legitimately has neither companion); and at least
one **lead** parquet must be present. A positive rule rather than a deleted constant was the shape both
sides wanted independently — the risk here runs toward letting a half-compiled directory upload, not
toward refusing too much.

**The first rule is a self-check as much as a module check**, which is why it earns its place on top of
a derived allowlist: it compares what would be sent against what the artifact says it contains, so the
two cannot drift apart silently a second time. And an absent or unreadable `manifest.json` **withholds**
rather than refusing — the same tri-state as RM84's `version_unknown_reason`, and what keeps that item's
four reasons four reasons rather than one refusal.

Re-measured after: **16 of 16 publish, and all 16 digests verify** against exactly what would be sent.
Nothing that published before stops publishing; the only new refusals are the two shapes that were never
a publishable module.

# 0.6 — what S36 closed: weights declare a scale, and a study names its allele

Three items from one consumer report about authored `weight` values. Anton Kulaga's note is field
feedback rather than a bug: the column declares no scale, every module means something different by
it, and published GWAS effects often beat hand-set curator weights. Triaging it found a fourth thing
nobody had measured — `weight` is authored **zero times** in this repo — and one thing the report
asked for that is barred outright. Filed and closed 2026-08-17.

## RM91 — a study states an effect magnitude relative to no allele

✅ **Shipped in `just-dna-format` + `just-dna-compiler` 0.6.0** (2026-08-17). **Owner** format (schema +
compiler) · **Motivating case** [S36](CONSUMER_SUGGESTIONS_HISTORY.md), found while checking whether a
GWAS effect could be carried on `studies.csv` at all.

`VariantRow` has carried `effect_allele` since 0.3 for a stated reason — `ref`/`alts` plus the sign of
the magnitude cannot recover which allele the claim is about — and `_check_allele_membership`'s own
message says naming the wrong one *inverts* the conclusion rather than breaking it. `StudyRow` has
carried `effect_size` + `effect_measure` since the same release and had **no such column**, so every
study row in the format stated a magnitude relative to nothing. The existing check iterates `variants`
only, and there was no field on a study row for it to examine even if it had.

**What landed.** One optional column, plus the check that makes it load-bearing:

- `StudyRow.effect_allele`, worded from `VariantRow`'s, and `StudyRow.ALLELE_COLUMNS =
  ("effect_allele",)`. **The omission of `ref` from that tuple is the design, not an oversight**:
  `AuthoredModel.ALLELE_COLUMNS` says *sequence columns that are the claim, never a column that merely
  points at a variant*, and names `StudyRow.ref` as its own example of the second kind.
- `_check_study_effect_alleles`, on the same mode ladder as the variant-side check — warning in
  `best_effort`, error in `strict` — and registered in **both** `validate_spec` and `compile_module`,
  since a mode ladder left compile-only is exactly the defect the 2026-08-07 audit fixed for
  `_verify_vrs_ids` and `_check_p_value_num` (`@parity-by-check`).
- **It reads resolved evidence only and withholds on everything else.** A `StudyRow` has `ref` without
  `alts` — `ref` is there so a position-only row keeps an identifier — so the authored branch has
  nothing to compare, and `{ref}` alone would flag every study of a non-reference allele, which is most
  of them. A row whose key reaches no `resolution.csv` entry is skipped rather than reported:
  unresolvable is unknown, and the house algebra withholds on unknown instead of negating it. A row
  naming no variant at all (legal since RM47) derives no key and is skipped by the same path.
- `_allele_verdict`'s resolved half was **factored out** as `_resolved_allele_verdict(call,
  variant_key, table)` rather than copied. A `StudyRow` has no `alts` and no `variant_key` column, so
  it cannot be passed to the row-shaped predicate; two implementations of "can this locus host that
  call" is precisely the drift `_allele_verdict`'s docstring already records, where membership and
  resolution disagreed the moment one indel was spelled two ways.

**Measured, and the prediction held exactly.** `artifact.digest` moved on **10 of 16** reference
examples — precisely the ten carrying a `studies.parquet`, since the column changes that schema — and
`content_signature` moved on **none of the sixteen**, because `exclude_none=True` omits an unset
optional column. That is what makes it minor-legal under P3 rather than merely additive-looking.

The reverse writer's hand-kept `fieldnames` list is the third of `@three-touch-points` and the one that
gets missed; the round-trip test was **watched failing** with only that entry removed, which raises
`dict contains fields not in fieldnames` at the reverse step rather than at the recompile.

## RM92 — the one magnitude in the format with no unit beside it

✅ **Shipped in `just-dna-format` + `just-dna-compiler` 0.6.0** (2026-08-17). **Owner** format (schema +
compiler) · **Motivating case** [S36](CONSUMER_SUGGESTIONS_HISTORY.md), which is a report about exactly
this and nothing else.

`effect_size` has `effect_measure` beside it. `VariantRow.weight` is a bare `float | None` described
only as "Score (positive=protective)", with no unit column anywhere, no statement of range, and nothing
saying whether two modules' weights are on one scale. The reporter's summary of living with that across
a corpus: the weights "construct nonsense", and *de facto* every module has a different methodology.
The 1.0 tracker had already called `weight` "module-local" — but nothing in the **artifact** said so,
so consumers combined across modules anyway.

**Measured while triaging, and it reframed the item.** `weight` is authored **zero times** in this
repo. Nine of the sixteen reference examples carry a `variants.csv`; four carry a `weight` column
(`hboc_palb2` 16 rows, `hfe_hemochromatosis` 13, `par_boundary` 3, `shox_par1` 10) and **every cell is
blank**; the other five have no such column. The column has never been dogfooded here, which is worth
recording beside the 1.0 review of whether `weight` survives at all.

**What landed.** `Weighting` on `ModuleSpecConfig` and copied to `ModuleManifest` — `scale`, `method`,
`note`, three optional strings, `extra="forbid"`. Advisory exactly like `license`: out of
`artifact.digest`, out of `content_signature`, dropped by `reverse_module`.

**All three fields are free text, and the field the block does *not* have is the design.** A closed
vocabulary would enumerate scales nobody has surveyed, against P5's one-way-door rule. More to the
point, the block deliberately carries **no precedence rule** — nothing saying "use the GWAS effect
where `weight` is null". That was the reporter's own first suggestion and it is refused: a per-row
precedence rule puts two methodologies in one summable column, which is the defect being reported, and
it leaves the module with no single scale left to declare. The module states what its weights *are*;
a consumer picks a table wholesale rather than blending row by row.

**`measure_tiling` is the nearest precedent and it is a column, not a yaml key** — worth stating,
because "flag it like the binning kinds do" is the obvious move and it is the wrong one here.
`measure_tiling` is per-row on `MeasureBinRow` and constant within a bin group; a weighting
methodology is module-wide, and repeating it on every row is exactly the authoring burden the
human-authorable gate exists to price. What *did* transfer is the shape of its resolution: declared →
inferred → default, with the evidence returned beside the value.

**Corpus movement: none.** No digest and no signature moved anywhere, because no example adopted the
block in this commit. The cost lands on the module that *does* adopt it: `module_spec.yaml` is
byte-hashed into `manifest.inputs[0]` and the RM45 attestation binds the same set, so adopting the
block stales an existing `verification.json` and the module must be re-closed. Pinned by a test.

One gap closed in passing: `license`, `panel` and `authorship` are all documented as dropped by
`reverse_module` and **none of them was asserted anywhere**, so the round trip could have started
re-emitting one with no test noticing. `weighting`'s reverse-drop is pinned.

## RM90 — GWAS effect sizes as a derived fact table, because they may not go in `weight`

✅ **Shipped in all three packages, 0.6.0** (2026-08-17). **Owner** format (schema) + compiler (the
seventh fact table) + enricher (the Catalog pass) · **Motivating case**
[S36](CONSUMER_SUGGESTIONS_HISTORY.md), whose reporter asked for the one thing this does not do.

The ask was: have the enricher procure GWAS effects and fill `weight` where the authored cell is null.
Barred, twice over — `MODULE_LIFECYCLE` § Stage 3 names `weight`/`direction`/`effect_size` in the cells
no tool fills, and Stage 5 says every check reports rather than repairs. A null `weight` means *the
author has not modelled this*, which is the house algebra rather than a hole to backfill. There is
also a sign trap in the middle of it: `weight` is documented positive=protective while a GWAS beta is
positive on the effect allele, so a silent fill inverts the claim on exactly the rows nobody re-reads.

So the effect goes in its own table — the third category the compiler already names, *"machine-produced
reference-fact table … injected, fact-hashed, human-overridable"* — and `weights.parquet.weight` stays
100% authored. A module carrying both holds an authored opinion **and** a machine-transcribed reference
fact, which is exactly what it already does with `frequencies` and `gene_metrics`.

### The model was shaped by the real payload, and the download TSV would have got it wrong

Probed on 2026-08-17 against `rest/api/singleNucleotidePolymorphisms/{rsid}/associations`:

- **`orPerCopyNum` and `betaNum` are separate, mutually exclusive keys** — not the download file's
  single ambiguous "OR or BETA" column — so `effect_size` + `effect_measure` maps exactly.
- **`betaUnit` is free text and frequently uninterpretable.** This is the column the table exists for:
  a magnitude without its unit reproduces S36's defect one layer down. It is inside the fact hash.
- **`betaDirection` is increase/decrease, about the measured trait**, and is deliberately not folded
  into `direction` (protective|risk|neutral|unknown). Increasing HDL and increasing LDL are both
  `increase`; one field carrying both axes is the P5 overloading `state` is being unwound for.
- **`riskAlleleName` is `rs4149056-?` when the study never established the allele.** Parsed to `None`,
  never a guess, and the row is **kept and counted** rather than dropped — it is real evidence that
  cannot be used as a weight, and a consumer that silently dropped such rows and one that silently
  kept them would both be wrong invisibly.
- The row carries **no coordinates**: the association payload has none, and one copied from the
  module's own `resolution.csv` would be the module's fact rather than the source's.

`rsid` is **inside** `GWAS_FACT_FIELDS`, which inverts `CLINICAL_ASSERTION_FACT_FIELDS` on purpose:
there the rsID is filled from the module's resolution because the archive returns none, here the
Catalog is queried by it and echoes it back. Copying the newer precedent because it is newer would
have been the wrong reading of it.

### Running it against a real module broke it twice, and both would have shipped green

Neither failure was reachable from a recorded fixture, which is the argument for the probe:

1. **A 404 is the empty answer, not an outage.** The Catalog holds only variants with a published
   association, so it 404s on a rare clinical one. The pass read that as a transport failure and died
   on `rs111033563` — the **first** variant in `hfe_hemochromatosis` — so it could never have completed
   on any clinically-authored module. `GwasNotFound` is a subclass rather than a flag, keeping the
   distinction typed: `associations_for` reports the empty answer, `follow` withholds one association's
   study facts and keeps the effect. The reverse must never happen.
2. **A p-value below float64's range dropped the whole association.** The Catalog publishes
   `pvalue: 0.0` past the subnormal boundary and `p_value_num` is `gt=0` for the reason SCHEMAS gives —
   that is an underflow, not a probability. The model was right and the pass was wrong: it let the
   `ValidationError` discard a real published effect over one derived column. The number is now
   withheld, the verbatim string keeps what the source said, and the row survives. **Six on rs1800562;
   189 rows became 195.** This is the catalogue-scale case the 0.5 mantissa/exponent rejection
   anticipated, met without reopening it.

**And a prediction the measurement refuted.** `_LinkCache` exists because `pmid`, `study_accession`,
`ancestry`, `trait` and `trait_efo_id` all sit behind `_links`, making the pass `1 + 2N` requests per
variant; the expectation was that associations share studies heavily and caching would collapse most of
it. It saved **nothing** — rs1800562's 189 associations each name their own study, so the real figure
was **382 requests and zero cache hits**. The cache stays (it costs a dict and pays on a module whose
variants share literature), the docstring now states the measured budget instead of the guess, and
`--no-study-facts` exists because of the measurement rather than in anticipation of it.

### Licensing: the first source here with no named licence

`GWAS_CATALOG_TERMS` records EBI's prose terms, read 2026-08-17. `license` is null, which is the honest
answer. **`commercial_use` stays `None` deliberately**: the page permits "use" generally but conditions
it on the original data owners' terms, and for an aggregator of thousands of published studies those
are not established here. Unknown is neither permission nor refusal — `taints_commercial_use` requires
an explicit `False`, so a null warns rather than gating, which is the right outcome for terms stated in
prose. Pinned by a test so it is not "tidied" to `True`. Rate limits are **not established** for EBI,
unlike gnomAD's real and load-bearing 10/60s, and the interval says so.

### Measured

Adding the table moved **nothing**: no digest and no signature on any of the sixteen examples, since a
module without the table has no such file. `hfe_hemochromatosis` then adopted it — 195 real rows, 186
associations for rs1800562 across **62 EFO traits in 12 distinct effect units**, three of which are
spellings of one unit (`SD units`, `SD`, `s.d.`) and two more of which differ only in case (`g/dL`,
`g/dl`); 138 rows carry the uninformative `unit` and **42 of 195 name no effect allele at all**. Its
`artifact.digest` moved, correctly, and its **`content_signature` did not** — which corrects the
prediction written into the plan: neither a derived sidecar nor a manifest-only block is authored row
content.

## RM173 — closed 2026-09-02, superseded by RM175: the year-old archive was a retired filename, not a stale sibling

**Severity** low-medium · **Status** ✖ **CLOSED 2026-09-02, not shipped** — its premise was replaced
twice in one day, and the second replacement is a different and much larger item. Closed into
[RM175](ROADMAP_HISTORY.md#rm175--the-pgx-lanes-default-archive-was-a-retired-filename-and-every-row-it-had-ever-built-came-out-of-a-frozen-2025-object)
· **Owner** enricher · **Motivating case** RM166's probe, which found it while answering a narrower
question

> **Read this first: closed because it was right about the number and wrong about what the number
> meant.** This entry measured a 13-month gap between `clinicalAnnotations.zip` and
> `clinicalVariants.zip` and read it as two live surfaces of one source refreshing out of lockstep.
> [CLINPGX_ARCHIVES](probes/CLINPGX_ARCHIVES.md) established that the 15-column table was **renamed**
> to `summaryAnnotations.zip` when PharmGKB became ClinPGx on 2025-07-29; the old filename is a frozen
> S3 object the API still answers 200, it is on no downloads page, and **this repo's builder still
> defaults to it**. So the currency question this entry ended on is not a signal to publish — it is a
> lane reading a dead file, which is RM175. Everything below is kept as written; §7 of the probe lists
> the five corrections point by point.

**Filed 2026-09-01, out of RM166's build.** RM166 asked whether the FDA's drug-label content was
already inside a source this repo has adopted; it is, and enumerating the download endpoint properly
answered a second question nobody had asked. **ClinPGx publishes at least twelve archives** —
`clinicalAnnotations`, `variantAnnotations`, `clinicalVariants`, `drugLabels`, `relationships`,
`variants`, `genes`, `drugs`, `chemicals`, `phenotypes`, `occurrences`, `pathways-tsv` — and after
RM166 the lane reads **two**. That framing stands. What does not is the sentence that followed it.

### Probed 2026-09-02, and `clinicalVariants` is not a third source

The entry said `clinicalVariants.zip` is "the one that bears on a shipped table kind", and posed the
`type` column's comma-combining as the design question. Both were wrong, and one join says why.

**96.3% of its rows are already in the archive the lane reads.** Joining all 5,190 rows against
`clinical_annotations.tsv` on `(variant, gene, drugs, phenotype category, level of evidence)` recovers
**5,000**; 190 remain, of which only 91 are a `(variant, gene)` pair the adopted archive does not
carry at all. Its six columns are a strict subset of the other's fifteen — no `Clinical Annotation
ID`, no `URL`, no `Score`, no PMID or evidence counts, no specialty population. It is a rollup of
`clinicalAnnotations` published as its own download, and everything it could contribute to
`pharm_variants.csv` the lane already has a richer version of.

**The `type` question is already answered by the column the lane stores.** `type`'s thirteen observed
values are `Phenotype Category`'s thirteen observed values, member for member, differing only in the
separator: `Efficacy;Toxicity` in `clinical_annotations.tsv`, `Efficacy,Toxicity` in
`clinicalVariants.tsv`. The lane stores that cell verbatim as `phenotype_category` and it is already
in the ClinPGx dedup key (`@clinpgx-full-key`), so "one cell or several rows" was settled before this
item existed. The combination is 106 rows, 2.0%, seven combinations over a six-member base
(`Efficacy`, `Toxicity`, `Metabolism/PK`, `Other`, `Dosage`, `PD`), and the member order is canonical
— no combination appears in two orders. The separator difference is `@one-normalizer-two-spellings`
with the *separator* as the spelling, and it is a reason to be careful reading this file, not a reason
to read it.

### What the probe found instead, and it is worth more than the item it replaces

**The archive the lane reads is 13 months older than the one beside it.** `clinicalAnnotations.zip`
as served by `api.clinpgx.org` today carries `CREATED_2025-07-05.txt`; `clinicalVariants.zip` carries
`CREATED_2026-08-05.txt`. Same source, same licence (CC BY-SA 4.0 + no-sale, read out of each
payload's own `LICENSE.txt`), two archives of substantially the same content a year apart. That is
`@two-surfaces-two-denominators` with teeth: **99 of the 190 residue rows are subjects the lane
already holds whose level, category or drug set has moved** — curation drift the lane cannot see,
because the file it reads has not been rebuilt upstream since 2025-07-05.

**So the open question is a currency one.** Does the lane report that its own ClinPGx archive is
stale relative to a sibling archive from the same source — and if so is that a check, a `release.json`
field, or a line in the snapshot's notice? `@currency-asks-the-source-not-the-cache` says the question
is asked of the source, and here the source answers it in a second file's `CREATED_*.txt`, which is
about as cheap as the ask gets. Reading `clinicalVariants` **as a dated probe of the lane's own
staleness** is a different and much smaller thing than adopting it as a table source, and it is the
only use the measurement supports.

**Not a widening of RM166.** That item is drug labels and it shipped; this is a different file
answering a different question, and keeping an item open by changing what it is about is how an item
stops meaning anything. This entry has now changed what it is about *once*, on a measurement that
refuted its premise — which is the one licit reason, and it is recorded here rather than smoothed.

**Related** RM166 (where it was found), RM29b, `@clinpgx-full-key`, `@one-normalizer-two-spellings`,
`@two-surfaces-two-denominators`, `@currency-asks-the-source-not-the-cache`, `@pgx-research-only`.

## RM170 — a source that both asserts and refutes a claim is muddy water, and nothing tells an author

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-02 in the uncut 0.7.0** (`just-dna-enricher`
plus one `VALID_VERIFICATION_CHECKS` member; **no model, no parquet column, no authored surface, and
no new `VALID_WARNING_CODES`** — that vocabulary is the compiler's and its guard asserts every member
is built by a compiler check, so the two finding codes stay this pass's own and a compile restates
them as `verification_findings_recorded`) · **Owner** enricher · **Motivating case** the RM169 widening, which
made the first such variants visible in a built snapshot

> **What shipped.** Two surfaces, one shape. `draft-panel --source civic` names the variants it *wrote*
> a direction for that the same snapshot also rebuts — the variant, both evidence ids, their statuses
> and the `status_basis` — where before it only counted the refuting rows it had withheld, which is a
> different fact and never mentioned the rows it went on to write. `enrich` folds in
> `published_refutation` whenever a CIViC snapshot resolves, so a hand-authored module that never ran
> the drafter meets the same sign; the record states its basis on every run **including the empty
> one**, because on the `accepted` basis this class is empty by construction. Two warning codes:
> `refutation_beside_claim` and `refutation_without_claim`, both keys of this pass rather than of the
> compiler's vocabulary. Warns in both modes, escalates in neither, repairs nothing.
>
> **The finding keys on the refuting evidence item and fans out to the rows it touches**, so EID
> 8721 — one statement about the combination genotype `VHL S183L AND VHL D126N`, which the snapshot
> writes as two single-variant rows — is reported as one refutation over two subjects. That stays true
> whichever way RM174 is repaired.
>
> **`comparison_plan` gained an `authored` selector rather than a second copy**: both authorities are
> asked about the same alleles, and a private copy is how the second caller stops finding the first.
>
> **The design record is [rm170_kleene.md](probes/rm170_kleene.md)** — the case-by-case advocacy (A–J)
> the build follows, and the two refusals it turns on: no new `VALID_DIRECTIONS` member, and no sum of
> camps into a point. The measurements are [CONTRADICTION_CORPORA](probes/CONTRADICTION_CORPORA.md).
>
> **Two holes the design record did not cover, closed in the build rather than left to be discovered.**
> The *join* is the `clin_sig` route — resolved `(chrom, start, ref, alt)`, never rsID — so the two
> authorities are asked about the same alleles. And an authored row **disagreeing** with the supported
> sign is still a subject: the finding is that the variant is muddy, not that the author picked the
> wrong side, so it fires on any authored `direction`. Source-versus-author on a *settled* variant
> stays out of it, which is case B and still nobody's item.

**A second corpus exists, found while probing RM165 (2026-09-01) — design against both, not against CIViC alone.** STRchive's `evidence` field is a ClinGen-style validity call on **all 82** of its repeat loci, and its members include **`Disputed` (3) and `Refuted` (1)** beside Definitive 46 / Limited 14 / Moderate 8 / Provisional 6 / Strong 4. That is this entry's shape in a different domain and on a *published, closed vocabulary* rather than CIViC's per-record assertion/refutation pair — so the two corpora disagree about where the contradiction lives (a field vs. two rows), which is exactly the sort of thing that decides a record shape. Probe both before fixing one.

**The correction this item starts from.** It was reported during the RM169 round that reading
submitted evidence would make three VHL variants `contested` and so stop them being drafted. That was
wrong, and the way it was wrong is the item. `contested_variants` counts a variant whose camps include
**both** `risk` and `protective` — genuine opposition — and a `Does Not Support` row does not enter a
camp at all: `CIVIC_DIRECTION_MAP` maps it to `None`, because a refutation removes a claim without
establishing the opposite one. So `contested_variants` is **0 on both bases**, correctly, and the
drafter withholds nothing new.

But the three variants are real, and an author has no way to learn about them:

| variant | claim | refutation |
|---|---|---|
| 2161 `VHL S183L (c.548C>T)` | 2 supporting items | ev 8721 `DOES_NOT_SUPPORT` |
| 2428 `VHL G104V (c.311G>T)` | 1 supporting item | ev 10949 `DOES_NOT_SUPPORT` |
| 2533 `VHL D126N (c.376G>A)` | 1 supporting item | ev 8721 `DOES_NOT_SUPPORT` |

Each carries a claim **and** a published rebuttal of that claim. The snapshot keeps both rows — the
refutation with its raw words and a null `direction`, which is the three-valued rule working — and
then nothing downstream ever mentions it. A module can author a `risk` row over one of these and every
gate stays green.

### Why a check rather than a filter

`enrich`-tier checks report and never repair (`@enrichment-is-validation`), and this is squarely that
shape: a fact about the world an author should weigh, not a defect to fix. The natural home is a new
`VALID_VERIFICATION_CHECKS` member — the vocabulary already holds sixteen of exactly this kind, each
comparing something authored against something external.

The subject is **an authored row whose variant a source both asserts and refutes**, so it fires
regardless of how the row got there: a hand-authored module gets the same warning as a drafted one,
which is the point. Muddy water is a property of the variant, not of the provenance.

### Probed 2026-09-02 — [CONTRADICTION_CORPORA](probes/CONTRADICTION_CORPORA.md)

Both corpora measured before designing against either, as this entry asked. It answered both open
questions and corrected the entry on the one that mattered.

**The weight question is answered, and this entry had it backwards.** It said only 2428 has a
refutation an editor signed off. 2428's *claim* is accepted; its refutation (EID 10949) is
`SUBMITTED`. **No refutation anywhere in CIViC that stands against a claim is accepted** — both
accepted refutations in the whole database (CHEK2 788 / EID 1854, TP53 4968 / EID 1302) are
refutation-**only**, with no claim beside them. So the subject count is not merely basis-dependent, it
is **0 on `accepted` and 3 on `accepted+submitted`**: the class does not exist on the basis the
builder read before RM169, and exists entirely on the strength of unreviewed content. A hint that
states the basis alongside the disagreement is now the *only* shape that can be honest, rather than
the preferred one. (TP53 4968 never enters the snapshot at all — dropped `unresolvable_identity`, and
absent from the VCF for want of a GRCh37 position. One of the two accepted refutations in the database
is invisible to every consumer of this artifact.)

**The three instances are one pair plus one combination-profile item counted twice.** EID 8721 belongs
to molecular profile 5278, which CIViC publishes as `VHL S183L (c.548C>T) AND VHL D126N (c.376G>A)` —
one statement about a two-variant genotype. `_submitted_evidence_row` stamps `molecular_profile_id`
from the *variant's* single-variant profile, so the parquet writes it as two rows claiming MP 2037 and
2406 and the column that would say "combination" is overwritten. Bounded and measured: 5 evidence ids
on 2 parquet rows each, 108 fanning out across the whole VCF. Note the path asymmetry — a combination
profile arriving via the TSV is dropped `combination_profile`, via the VCF it is fanned out and kept.

**The scope question is answered from the adopted set rather than guessed, and STRchive is not a new
axis.** A walk of all 26 `VALID_*` frozensets finds refuting members in exactly two source-facing
vocabularies: `VALID_GENE_VALIDITY` (`disputed`/`refuted`/`no_known_disease_relationship`, for
ClinGen+GenCC) and `VALID_CLIN_SIG` (`conflicting`, for ClinVar). Four adopted sources carry this
shape and three already land it somewhere — `gene_validity` even publishes an unorderable
`["definitive","refuted"]` group as a **set, not a verdict**, which is this item's machinery already
built one grain up. **STRchive's is the one that lands nowhere**: `StrchiveLocus` drops `evidence` at
parse, and a real `draft-repeats --gene DMD` run (DMD is the single `Refuted` locus) writes a row
indistinguishable from HD_HTT's and says nothing — the field is not even in the read-and-not-written
accounting.

**But the two corpora do not share a subject, so one check cannot be both.** CIViC's contradiction is
*inter-row, post-join, per variant*: neither row is contradictory alone, and the subject exists only
after an authored row is matched to a snapshot variant. STRchive's is *intra-record, pre-join, per
locus*, and is not a contradiction in CIViC's sense at all — nothing asserts the locus is pathogenic
and then denies it; one field grades the association `Refuted` while the same record still publishes a
pathogenic band the drafter writes. That is a self-inconsistent record, closer to a grade the drafter
drops than to a disagreement. Its vocabulary is also **open**, not closed: the published schema uses
`examples` + `combobox: true`, and carries `Provisional` (6 loci), which the schema's own text defines
as *not yet curated* — a nobody-asked, not a grade, and it has no house member. The two corpora
overlap on **one gene (`CBL`) and zero loci**, and no reference example authors any of the six genes,
so zero corpus modules would fire either finding today.

### What has to be decided, and what is already settled

- **The subject set is per authored row, not per snapshot row.** A check that counted snapshot rows
  would publish a number about CIViC; this one is about the module.
- **Severity: warn in both modes, never gate.** Its two nearest neighbours both say so
  (`@clinsig-never-escalates`, and `@a-source-recuring-is-not-a-strict-matter`), and for the same
  reason: a source disagreeing with itself is not an authoring error.
- **Settled by the probe — the hint must state the status basis**, because every pair rests on
  submitted content and a check that did not say so would publish a finding whose subject count
  silently depends on a build flag.
- **Open, and reshaped — one check or two?** The measured answer to "CIViC-scoped or general" is that
  the *shape* is general (four adopted sources) but the *subject* is not shared: a per-variant
  post-join contradiction and a per-locus published grade are two different findings that would only
  look like one in a vocabulary. Deciding this is deciding whether STRchive's `evidence` is adopted at
  all — today it is dropped at parse, so the STRchive half is a **source-adoption** question wearing a
  check's clothes.
- **Open — the combination-profile stamp is a defect, not a design question.** `molecular_profile_id`
  overwritten with the variant's own profile is wrong regardless of what this item decides; it belongs
  to whoever fixes it first, and it makes 8721 look like two independent refutations.

**Related** RM169 (which made these visible), RM152, RM160.
