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

## 2026-09-13 — Genomi survey: what a genomics *runtime* annotates, and the seven gaps it exposes

**Documentation only** — a probe round, no code, no `RMn`. New:
[probes/GENOMI_SURVEY.md](probes/GENOMI_SURVEY.md), a competitor survey of
[`exon-research/genomi`](https://github.com/exon-research/genomi) at commit `1df4f5b` (version 0.1.0,
Apache-2.0), read from its source rather than its README.

The short finding is that genomi is a *runtime* — an agent's local index of one person's genome, plus
live fetchers — and not a competing artifact format, so its ~100 operations partition into reference
annotation (comparable), sample compute (consumer-side here, by the data-agnostic goal) and agent
runtime (out of scope). Only the first bucket is compared. Its declared source roster is 29 entries,
but `adapter_status` splits it **15 wired against 14 `record_via_research`** — an agent reading a
page by hand — and its whole *authored* annotation corpus is thirteen records: ten hardcoded Python
dictionaries in `capabilities/nutrigenomics/catalog.py`, which is a `variants.csv` written in the
wrong language, plus three CYP2C19 star-allele markers in a JSON file. §7 was **run, not sketched**:
their MTHFR record is authored as a spec and `validate` refuses it — `studies.csv line 2 [pmid]:
Field required`, and `studies.csv is missing. Grounding evidence is mandatory` when the file is
dropped instead — then passes once a real PMID (7647779) is supplied. **That refusal is the gate
working, not a gap**: the folate claim has primary literature behind it and genomi cites the CDC's
summary of it, which is a curation shortcut rather than something we owe a slot for.

**The findings route to [RM188](ROADMAP_0_8.md), and all of them are 0.8.** A derived sidecar is a row
model plus a `VALID_SOURCE_LAYERS` member plus a parquet plus an enricher pass, so it touches format
and compiler and is minor-legal-and-minor-required under P3/P8; the same holds for
`out_of_scope_claims` as a new optional authored column. The one item that could still be a
`just-dna-enricher` patch on 0.7.x is Tier 3's PGxDB, and only if its probe finds something the
CPIC/PharmGKB/FDA lanes miss *and* that reduces to a check over existing tables, RM166's
`check-labels` being the shape. Their record also carries one
`effect_allele` where we carry a row per genotype, and encodes the APOE ε2/ε3/ε4 haplotype as an
English sentence in a string field, against `reference_examples/apoe_epsilon`, which already ships
the same two variants as six `haplotypes.csv` rows and six diplotypes.

**Nine gap rows, seven real, five of the seven gene-keyed** (the other two are locus-keyed and join
on `variant_key`): Open Targets target–disease and L2G,
drug target/mechanism (ChEMBL), pathway membership (Reactome/MSigDB), baseline tissue and cell-type
expression (HPA), regulatory-feature overlap (ENCODE cCRE), and perturbation screens (DepMap/ORCS);
PGxDB is the small ninth and the 1000 Genomes ancestry panel is charter-blocked. Every candidate
prices as a **derived sidecar via an enricher pass** on the `gene_validity.csv` template — half cost
under the 0.6 amendment — never as an authored table kind, because no author decides those cells.
The one authored-layer candidate is genomi's `out_of_scope_claims`, which is a third thing beside
`conclusion` and `negatives`: the popular claim a row exists to contradict.

HPO stays refused for the reasons already on record in [ENRICHER.md](ENRICHER.md) (its licence cannot
be established, and `genes_to_phenotype.txt` is a different grain), and the survey records what has
no analogue on their side either — heteroplasmy, repeat alleles, copy number, ACMG SF, MANE,
constraint, CIViC, AlphaGenome, the literature pack, licence-as-data, signing, the overlay and the
round trip.

## 2026-09-13 — S101: `pgs.csv`'s page claimed a compile gate, and read a calibration term as a licence one

**`just-dna-format` and the docs — a `Field(description=…)` and two `TABLES.md` sections; no behaviour
changed, and nothing in the gate moved.** In the tree and in no version anyone can install.

`TABLES.md`'s `## pgs.csv` said *"a module citing an academic-research-only score cannot compile
without a declared use … that is the one place this table reaches the compile gate"*. It reaches no
gate at all. Measured on a scaffolded module carrying `PGS000001` at `research_tier=research_only`,
through `validate_spec(strict=True)`:

```
A. no licensing.csv at all                  valid=True
B. commercial_use=false, declared_use empty valid=False   # the gate, and it is licensing.csv's
C. declared_use=non-commercial              valid=True
```

**The conflation under it is the part worth recording.** `research_tier` is a *calibration* axis, not a
licence one — `research_only` pins as data that a score is a within-reference Z/percentile rather than
an ancestry-calibrated absolute risk, which is what `pgs.py` has said since the field shipped in 0.4.
Two unrelated senses of "research only" met in one paragraph. Wiring it to the gate is refused rather
than deferred: one field carrying a statistical frame *and* a licence term is the overloading Principle
5 forbids.

**The field's own description was silent in the same way** and is the third surface fixed. It read
`research_only | calibrated (VALID_RESEARCH_TIERS)` — a member list naming no axis, which is what let
the prose read it as terms (`@field-description-is-a-claim`). It now names the axis and says it reaches
no gate.

**Also stated, and settled rather than new:** `layer` names what a source *fed*, not which table it
fed, so every authored table is `annotation` and a PGS Catalog row reads as annotation-layer content in
the gate's error. There is deliberately no per-table member — `VALID_SOURCE_LAYERS` is a wire
vocabulary, and the last request for one was refused on the reporter's own argument (S82, RM147).

Reported by just-module-creator, who had the diagnosis right and asked for the behaviour reading if we
disagreed; their own dossier was teaching the correct thing before ours was.

## 2026-09-12 — RM234: `AcmgReport.clean` is three-valued, because it was `True` on a run that compared nothing

**`just-dna-enricher` only — no parquet, model or manifest field changes, and the release class is the
maintainer's call.** Landed after the 0.7.0 cut, so it is **in the tree and in no version anyone can
install**.

`AcmgReport.clean` was `not self.mismatches`, and `mismatches` selects the verdicts `not_listed` and
`denied`. A run that obtained no ACMG SF list gives every row the verdict `unchecked`, so `mismatches`
was empty and `clean` answered `True` — a comparison that never happened reporting as one in which
everything agreed. `version=None checked=0 clean=True` and `version=3.3 checked=13 clean=True` are the
two readings a caller could not tell apart, and `if report.clean:` took the first for a pass.

`clean` is now `bool | None` and withholds on both arms of a non-comparison: no list obtained, and a
list obtained that no row could be looked up in. It is `None` rather than `False`, because answering
`False` would say the module disagrees with a list nobody read.

**The attestation was already correct and that shaped the fix.** `verification_record` has always
returned a `skipped` record on both arms, so the persisted record never claimed a pass while the
in-memory property did. Rather than testing the same two conditions in two places, a single
`not_consulted` property names the arm and both read it; a test asserts `clean is None` holds exactly
where the record is a skip, across all five arms.

**For callers.** `None` is falsy, so `if report.clean:` was correct before and stays correct — the
CLI's green line uses that spelling and its now-redundant `and report.version` guard is gone. `if not
report.clean:` **newly fires** on an unconsulted run, which is the intended change. `check-acmg
--strict` gates on `mismatches` and never on `clean`, so no offline run newly refuses.

Reported as S100 by just-module-creator, who had already written the caller-side guard and filed it so
the next consumer would not have to. One existing test was asserting the defect.

**Filed alongside: [RM235](ROADMAP.md#rm235--one-property-over-four-registries-an-outage-reports-as-a-broken-identifier-and-an-unreachable-efo-reports-as-clean), open and more serious.** The same shape in
`IdentifierReport.clean`, which combines four registries and gates `check-identifiers --strict`'s exit
code: an **unreachable** dbSNP or HGNC is counted as a broken identifier (so a third party's outage
fails your build), while an unreachable OLS4 is dropped and reports clean. Not fixed here — its unknown
arm is per registry and combines under Kleene, which is a design rather than a one-line change.

## 2026-09-12 — the docs site gets a user-facing front (no version bump: nothing shipped in a package changed)

**Documentation only — no package version moves and nothing a consumer holds changes.** The site went
up carrying the material that already existed, which is almost entirely development record and tier
reference written for whoever maintains that tier; its home page was the README, whose first three
sections are *Develop*, *The docs site* and *Design docs*. A reader who has a compiled module and wants
to report on a genotype had nowhere to land.

**Four new pages, written for a reader rather than an author**, sitting in front of SCHEMAS / COMPILER /
ENRICHER and citing them: `index.md` (what this is, and which tier answers your question),
`GETTING_STARTED.md` (install, compile a reference example, verify it), `CONSUMING.md` (what is in an
artifact, the two digests, the join contract's two obligations, the licence axes) and `COMPILING.md` +
`ENRICHING.md` (the operator paths). They **restate no rule** — where a guide and a tier reference
disagree, the guide is the one that is wrong. Every command in them was run before it was written and
the output is quoted as it came back.

**The CLI reference is generated** (`scripts/gen_cli_pages.py`, a second `gen-files` script), walked off
the live Typer command trees at build time: of the order of a hundred commands and several hundred
flags across the two tools, which is exactly the shape `CLAUDE.md` already refuses to keep by hand. It
reads parameters through `param_type_name` rather than `isinstance`, and that is load-bearing — Typer
vendors its own copy of click, so `TyperOption` is **not** a `click.Option` and the first version wrote
every page with its argument and option tables silently empty.

**Two nav changes.** `navigation.sections` opens the top level, because Material folds every group until
the reader is inside it and the sidebar therefore read as a site documenting one tier — *Reference* with
nothing under it. And the roadmap ledgers (`ROADMAP`, `ROADMAP_HISTORY`, the two deferred files,
`RM_TOC`) leave `not_in_nav` for a *Releases* group: they were excluded so a reader was not wading
through shipped-roadmap rationale to reach the schema reference, which is true of a sidebar where they
sit beside it and false of a group somebody opens deliberately — and every reference page cites `RMn` by
number with nowhere to resolve one.

`schema/tests/test_docs_site_nav.py` now derives the generated-page prefixes from the `gen-files`
`scripts:` list rather than one hardcoded path, so a second generator is visible to the partition guard
instead of unknown to it.

## 2026-09-12 — [RM233](ROADMAP_HISTORY.md#rm233--main-was-red-on-two-jobs-and-green-on-every-local-run-and-the-difference-was-a-colour-code): a red `main` that was a colour code

**Test infrastructure only — no package version moves and nothing a consumer holds changes.** `main`
was red at `2001215` on both Python jobs while every local run was green. Two tests match a string
inside Typer's rich-rendered output; rich decides colour from the environment, so on a runner `--use`
arrives as three ANSI spans and the assertion reports a command missing a flag it declares. The second
failure, a diagnostic wrapped across the error box, was never environment-dependent — `CliRunner` pins
its own width, so no environment variable can widen it. Fixed in the two places the two causes live:
`TERM=dumb` in a root `conftest.py`, and the box-collapsing helper promoted out of one test module into
a shared `cli_text` fixture. The transferable half is that the helper already existed under a private
name, so the second caller that needed it wrote the raw match instead.

## 2026-09-12 — `docs/` renders as a site (no version bump: nothing shipped in a package changed)

**`docs/` is now a documentation site, built in place.** `mkdocs.yml` at the repository root, a `docs`
dependency group (`uv run --group docs properdocs build --strict -f mkdocs.yml`), and a CI job that
fails on a build warning and uploads the rendered site as a PR artifact. **Nothing moved**: every path
`CLAUDE.md`, `schema/tests/test_doc_links.py` and the `.claude/` tools cite is unchanged, and no file
was added to `docs/` — the home page (this repository's README, its links repointed) and the 119 API
pages come from the packages' own docstrings and are written into the build by `mkdocs-gen-files`.

**Nothing about a compiled module, a model, a manifest field or a CLI changed**, so no package version
moves and there is nothing for a consumer to do. Two things are worth knowing anyway:

- **The site's navigation is curated, not filtered.** The charter, the three tier references, the
  cross-tier and using-it documents, the two integration guides and this changelog are in the sidebar;
  the development records (the roadmap ledgers, the consumer inbox and its archive, the agent notes,
  the probe rounds, the design threads, the code-first audit) are built, linkable and searchable but
  absent from it.
- **It is published to <https://just-dna.life/just-dna-compiler/>** by `.github/workflows/pages.yml`
  on every push to `main`, through the *GitHub Actions* Pages source — no `gh-pages` branch, so the
  repository never carries a copy of its own output. That job holds `pages: write` and an OIDC token,
  which is why it is separate from `ci.yml`'s `docs` job: the PR-side build uploads a plain artifact for
  a reviewer and must stay runnable on a fork. The URL is a path beneath the organisation's custom apex
  domain, which a project site inherits rather than serving from `github.io`, and the path segment is the
  repository's canonical name — `just-dna-compiler`, this repository having been renamed, with
  `just-dna-format` redirecting. A `docs.`/`format.` subdomain was weighed and declined: a path costs no
  DNS and leaves one for every sibling repo. `schema/tests/test_docs_site_nav.py` asserts the two halves
  partition `docs/` exactly, so a page added to `docs/` without a place in one of them fails the suite
  rather than quietly rendering without a sidebar entry.
- **The builder is [ProperDocs](https://properdocs.org/) rather than `mkdocs`.** MkDocs 1.x upstream is
  unmaintained and the announced 2.0 removes the plugin system with no migration path; ProperDocs is a
  1.x continuation over the same `mkdocs.yml`, and `mkdocs-gen-files` and `mkdocs-literate-nav` already
  depend on it. The config keeps the `mkdocs.yml` name so that Zensical — the Material team's successor,
  Material itself having entered maintenance mode — stays a change of build command away. **Zensical was
  tried, not assumed:** it renders all 60 real `docs/` pages and `mkdocstrings` works under it, but it
  accepts `mkdocs-gen-files` and then ignores it, so the home page and every API page vanish with no
  warning. That one plugin is the whole distance to the switch, and `docs/AGENT_NOTES.md` carries the
  ten-minute probe and its pass criterion rather than an opinion to re-argue.

Heading anchors are slugified GitHub's way (`pymdownx.slugs.slugify`), which is what
`test_doc_links.py` has always verified them against; the first build without it reported 540 broken
anchors that were not broken.

## 2026-09-12 (latest) — RM232: a drafted row commits with its licence row too

**Cut as 0.7.0 across all three packages, with `v0.7.0` now at `2001215` on 2026-09-12** — the
maintainer settled the line and retagged at `65b9913`, so this entry is **inside** the cut rather
than the first of the next number, and the patch-versus-minor question its first draft left open does
not arise. The tag's history, kept because the hashes in INTEGRATION_0_7 § 5 only mean something
against it: first at `8b981f6` (2026-09-11), re-cut at `83b1674` when RM231 and a release-record
declaration landed after it, re-cut at `65b9913` when RM232 did, and moved once more to `2001215`
after S99 was answered, which is where it stands here and on `origin`. `dist/` is built from
`65b9913` and stays there: the delta to the tag is five documents and no code, no sdist carries
`docs/`, and a rebuild at `2001215` reproduces all six artifacts byte-identically. **So the readiness
commit no longer sits past the tag** — that sentence held for the first three positions and this entry
asserted it for a fourth it could not see, which is why INTEGRATION_0_7 § 5 now carries the position
as a measurement rather than a plan.

**Published to PyPI on 2026-09-12, 15:49–15:50 UTC, all three packages.** The six uploaded sha256
equal the six in INTEGRATION_0_7 § 5, so what is out is what that table describes.


RM231 closed the two-step tail in the eight enrichment passes and had to name **five exemptions** to
close its guard's roster. Two of them were one defect rather than two local ones, and this closes it:
a drafter's rows do not go through a writer of its own, they go through the compiler's
`draft.append_rows` / `append_partial_rows`, which had no `before_commit` to hand a callback to. So
`civic_citations.draft_civic_citations` and the drafting scaffold's `record_draft_provenance` recorded
the licence row only once the drafted rows were already renamed into place — and a refused merge (a
scaffolded module's unreplaced `<<REPLACE>>` row is enough, which is S98's own trigger) left drafted
rows in the author's tables with nothing recording what licensed them. `sources.csv` is the only file
the compile gate reads.

- **Both draft writers take `before_commit`** and thread it to all three of their `atomic_writer`
  sites. Optional, defaulted to `None`, so a caller that passes nothing gets exactly what it got
  before — see the release-class note above for why that is not by itself the number.
- **`drafting.licence_commit`** is the merge half of `record_draft_provenance` as a closure factory —
  one body, handed to every append a drafter makes. It fires **per table that actually writes**, which
  is the grain the row needs: hoisting the merge ahead of the appends cannot work, because `covered`
  is not knowable until the append is attempted (a run whose rows all `differ` covers nothing and must
  write no row), and binding it to only the first or only the last append leaves a table committed
  unlicensed whichever one turns out to be the no-op. The merge is never-clobber, so N firings record
  one row.
- **`record_draft_provenance` keeps its tail call** for the run that covered something and wrote
  nothing — every row already present, so no append reached a writer — along with the stale-label
  withdrawal and the projection restamp, both of which are answers about the run and not about one
  table.
- **The pre-flight is inherited, not remembered**: building the closure reads the licence table, so a
  placeholder refuses before the first append rather than after it.
- **The guard is an equality from both ends.** Nine committing passes now (`civic_citations` stops
  being an exemption), the two closures named as *being* the callback, and a new walk over every
  `append_*` call under `just_dna_enricher` — 11 of them, all 11 unbound before this change and all 11
  bound after.
- **The residual is unchanged and still stated**: two files are two renames, so a table rename failing
  after its callback has returned leaves a licence row for data that never arrived. Conservative, and
  the `OSError` names what landed.
- **One behaviour change beyond the fix, and it is intended**: the pre-flight runs when the closure is
  built, and a drafter builds it unconditionally, so `draft --dry-run` against a module whose
  `licensing.csv` does not load now **refuses** where it used to report. A dry run that hides the
  refusal the real run will make is the worse of the two, and RM231 made the same trade for the same
  reason. Pinned by a test.

Suite 4,639 passed, 29 skipped.

**Filed before it was fixed, and that is the point.** The gap was confirmed and then recorded only as
two exemption reasons in a passing test — honest, and invisible to a release check that reads *no open
RMs, all green*. It went into ROADMAP as an open item in its own commit before any code moved.

## 2026-09-12 — RM231: a licence row is part of its table's commit, in every pass

`just-dna-format` and `just-dna-enricher`, inside the uncut 0.7.0. `alphagenome expression` wrote
12,003 non-commercial rows, then refused to record its licence row on a scaffold's `<<REPLACE>>`
placeholder, and printed `FAILED` (S98) — and the compile gate, keyed on the licence table alone,
then passed the module as unrestricted. Eight passes had the same two-step tail.

- **`layout.atomic_writer(before_commit=…)`** runs a callback after the temp file is fsynced and
  before the rename. Every fact pass now merges its `SourceRow` there, so a refused merge removes the
  temp and a table that fails to serialize never reaches the merge: neither file exists without the
  other. A rename failing after the callback — two files are two renames — raises an `OSError`
  naming what landed.
- **`licensing.require_sources_file`**, the strict read factored out of `merge_sources_file`, runs
  before each pass's fetch, so a placeholder row fails in a second rather than after a whole-gene
  query. The gentle `read_sources_file` for readers is unchanged.
- **A guard** walks every function that records a licence row: eight commit through the seam and
  pre-read the table; five are named exempt with reasons, two of which are the same gap in the
  drafting scaffold, RM228's to close.

Refused: writing the licence row first, because a row for a pass that then contributed nothing is a
false statement in a published artifact. The `if write and result.written` gate is unchanged.

**The release gate, re-run at the cut, found one undeclared manifest field.** `expression_effects` —
the top-level block RM200 added for the tenth derived sidecar — appears (as `null`) on every module
compiled under 0.7.0 and on none under 0.6.6, and the 0.7.0 record did not list it: the block landed
after the round's last sweep. Declared as an addition, and the gate reads `covers the measurement`
again: content_signature 0/15, manifest_fields 15/15, parquet_bytes 14/15, parquet_schema 14/15,
warnings 3/15, `cyp2c9_warfarin_grch37` unmeasured.

## 2026-09-11 — RM230: a leak an exemption hid, a remedy no flag could reach, and a debt that was not owed

**`EuropePmcClient.lookup` leaked all three failure legs** — `httpx.HTTPStatusError`,
`httpx.ConnectError` and `json.JSONDecodeError` — into `enrich_literature`, whose `try:` has only a
`finally:` and no `except`. It was hidden because the contract suite exempted the **class** behind a
note about what one **method** promises: `fulltext` really does withhold correctly, and that sentence
silently covered a sibling nobody had read. Third form of one shape this round — RM208 was a guard
inheriting a roster's exemptions, RM225 a comment outliving the code it described. Removing it also
showed `covered` was keyed on the module and could not express "one class here is covered, two are
not".

**`check-identifiers` gains `--use`.** PGS rows were built with `declared_use="unstated"`, hardcoded,
and the `academic_research_only` class is `commercial_use=False` at the `annotation` layer — exactly
where the compile gate reads. So the compile refused and told the operator to *"re-run the enricher
with a declared use (`--use non-commercial`)"*, a flag that did not exist, on a file
`merge_sources_csv` will never clobber. The audit left "is any live score in that class" undetermined,
so it was measured: **6 of the first 250 Catalog scores**, PGS000013–PGS000017 among them. Reachable,
not latent.

**And a debt disproved by writing its test first.** RM228 recorded that `clinvar_draft` and
`pubmind_draft` write their licence row unconditionally. They do not — both return early at "nothing
matched" *before* the write. The test that would have proved the bug passes unchanged, so it is kept
as a pin on the early return, which is the thing actually holding the rule and which nothing else
asserted.

**[DRAFTING_MATURITY.md](DRAFTING_MATURITY.md)** is new: the post-RM228 read on what drafting still
needs to be a mechanism rather than seven grassroots implementations, written after the migration
because four of its findings were invisible until the copies sat side by side.

## 2026-09-11 — RM228: drafting stops being seven grassroots implementations of one mechanism

Seven `*_draft.py` providers turn a snapshot into authored rows, and they grew one at a time. By 0.7
each carried its own copy of the same four decisions and the copies had drifted: `clinpgx_draft` and
`pgx_draft` recorded a release label and **never withdrew a stale one**, so a module widened from a
newer snapshot kept a licence row naming the older release; `pubmind_draft` imported
`clinvar_draft._MATCH_ON` across modules; `civic_draft` branched on pydantic's rendered error text;
and `DRAFT_PROJECTIONS` was a hand-kept copy of the drafters' own `match_on`, its comment pointing at
`clinvar_draft._MATCH_ON` by name.

**The obvious repair was refuted by measuring it.** Four providers restated the model's skip rule and
two derived it, so migrating everyone onto the derived one is the instinct — and it is wrong.
`authoring_requirements("variants.csv")` answers `any_of: [['rsid'], ['chrom','start']]`, which cannot
express `VariantRow`'s third clause, *`ref`/`alts` require `chrom` and `start`*. The derived
implementation therefore accepts `{"rsid": "rs1", "alts": "G"}` — a partial coordinate the model and a
compile both refuse. Constructing the model is the only complete oracle, and it deletes the message
parsing for free.

A new `drafting.py` splits the **derived** model requirement from a **declared** source precondition
that carries its reason as a field. That distinction is what makes `mitomap_draft`'s `clin_sig` clause
legible: it gates identity on a column the model does not require, and it is *correct* — a
`rated_miss` carries one by construction — but the reason lived three lines away in a comment, so a
real constraint and a misread read identically. This item predicted mitomap would be its one
behaviour change; it was not.

The import cycle the refactor hit was the diagnosis rather than an obstacle: `draft_digest`,
`stamp_draft_digest` and `drafted_unchanged` had been drafting code sitting in `provenance.py`, a
boundary only holdable while the registry was a copy. Two guards — registry equality and an AST walk —
fail on all seven providers pre-migration. Enricher suite: 2108 passed, 25 skipped.

## 2026-09-11 — RM229: a cache lane declares its size, and a derived lane prices its parents

`just-dna-enricher` only, inside the uncut 0.7.0. A first-run offer had to `du` a provisioned box to
price a lane (S97), because `CacheLane` said everything about whether and how and nothing about how
much. `approx_mb` is now on every lane — an order of magnitude in whole megabytes, measured
2026-09-11 and rounded up, `None` legal and meaning unmeasured — with a test that re-measures it
against every snapshot the running machine holds, so a stale number fails a suite instead of a
consumer. `LaneStatus.size_bytes` measures a present lane and `cache status` prints it.
`provisioning_closure(lane)` walks `parents` transitively in registry order: `mitomap_miss` is under
a megabyte and its closure is a ClinVar download, which is what a blank box actually pays.

## 2026-09-11 — RM224: either spelling of a sidecar is a key

`just-dna-format` only, inside the uncut 0.7.0. `layout.SIDECAR_SPELLINGS` is keyed on the table
key — `sources.csv`, the spelling the parquet and the manifest keep — and the preferred filename was
not a key, so `sidecar_spellings("licensing.csv")` answered a one-tuple and `sidecar_write_path`
created the preferred copy beside a deprecated one: the collision it documents itself as preventing,
reached by a consumer holding a tar member named `derived/licensing.csv` (S96). `sidecar_key(name)`
reads the map backwards, derived from it, and `sidecar_spellings` normalises through it, so every
helper answers the same for either spelling. Nothing is refused, nothing added or removed; a test
walks the map. AGENT_NOTES `@sidecar-name-and-place` carries the read-side lesson: a helper whose
wrong answer is a plausible path fails quietly in both directions.

## 2026-09-11 — RM207–RM227, a second and blind derivation of the docs found in the code

**The docs were re-derived from the code by three agents that had never read them**, one per tier, in
worktrees with `docs/` and `CLAUDE.md` deleted — the method is now written down as
[BLIND_REDERIVATION.md](BLIND_REDERIVATION.md) rather than living as its first output's preamble. The
maintained references gained what they were missing (twenty-six modules, a check row, an AlphaGenome
section, the eighteen-source licence roster, all with walking tests). What follows is the other half:
**RM207–RM227**, eighteen shipped and two filed for 1.0 — places where the code was wrong, or
where a registry had a hand-kept copy of itself, each reproduced or measured before it was repaired.

**RM225 — four stale claims a reader acts on, and one had drifted three times.** The schema tier's
long-tail candidates, walked item by item instead of batch-closed. `actionability` is a **closed**
vocabulary and three separate places said otherwise: `vocab.py`'s comment ("the field is not built
yet"), `base.vocabulary`'s own docstring listing it among the open sets — inside the helper that
defines what `closed` means — and an earlier `reference.py` incident. The constant's name carried it
too, so `ACTIONABILITY_SEED` is now `VALID_ACTIONABILITY` with the old name a working alias.
`CANONICAL_MT_REFERENCE_SEQUENCES` looked like dead code and is not: it is correctly unenforced (an
allow-list would refuse future refs), but the refusal beside it spelled `NC_012920.1` as a literal,
so the set had one job and was not doing it. A `pgx.py` comment named `StudyRow.chrom` as validated
at two sites, and it has no validator. And `is_multi_valued_number`'s docstring promised a tri-state
its signature cannot express — checked every caller first: there is one, it gates whether to *raise*
a warning, so `False` on unknown **is** the withhold. The deliverable is the guard, which measures
each vocabulary's closedness against its validator and walks the constant names out of
`base.vocabulary`'s docstring; run against the pre-fix text it reports the third instance, the one no
tool could catch because only the prose was wrong.

**RM226 and RM227 filed for 1.0.** RM226 collects three warts the code declares in its own comments
and no tracker held — the grandfathered `content_signature` asymmetry, the hardcoded
`likely_pathogenic`/`likely_benign`, and `_freeze_identity`'s build-blind key — so the 1.0 cleanup has
a list rather than a grep. RM227 is RM215's other half: `derive_variant_key`'s coordinate fallback
still does not fold allele case, which splits joins rather than dedup and moves a stored cell.

**RM215 — one heterozygote had four content identities.** `ALLELE_PATTERN` carries `re.IGNORECASE`, so
a lowercase allele is legal, and the cell is stored verbatim — so `A/G`, `a/G`, `A/g` and `a/g` are one
genotype that hashed four different ways, which for a content-dedup key is the wrong answer.
`content_signature` now upper-cases a cell whose grammar is case-insensitive, and the four collapse to
the value every existing module already had. **This was filed for 1.0 and the filing was wrong**: it
sized the change by citing RM81, a parquet *retype*, where folding at hash time retypes nothing, leaves
the authored cell untouched and leaves the round trip alone. That is P3's *corrected derivation*, which
may ship in any release but never silently — and RM36 is the precedent in this very function, having
made `genome_build` feed the hash back in 0.5. The fold is driven by a marker over the four columns
whose validator is that grammar, found by probing all 57 models rather than grepping for "allele";
`ref`/`alts` are excluded because they are not grammar-checked at all. Measured across the corpus: 536
such cells, none lowercase, so no published signature moves. The `variant_key` coordinate fallback
still splits on case (`1:100:a:g,t`) and is surfaced rather than fixed, since that one moves a stored
cell.

**RM223 — the upgrade guide was the one maintained doc nothing walked.** A consumer measured four of
`INTEGRATION_0_7.md`'s numbers against the installed packages and found all four wrong: 22 parquets
where `ARTIFACT_PARQUETS` holds 23, 72 and then 71 warning codes where the vocabulary holds 73, and 31
models where the authoring reference renders 32. Three had moved when the AlphaGenome round landed
`expression_effects` after the numbers were taken. The document's own § 8 forbids exactly this and §§
2.2 and 2.3 already said to derive from the constants, so the repair is the guard rather than the four
words — the counted-prose test walked `SCHEMAS.md` and `COMPILER.md` and stopped. The document now
states no registry size at all, and a new guard refuses the shape.

**RM207 — the refusal that is fatal in both modes was asked of the wrong key, on the wrong side.**
`resolve_from_table` walked the *post-expansion* rows and looked each one's `variant_key` up in a table
keyed by the key the author wrote. Those strings are equal for a row the fill merely completes and
different for a row the table expands — the expansion mints the locus's `ga4gh:VA.…` id — so a module
carrying a **withdrawn** rsID on an expanded variant compiled clean, `success=True`. And the check
existed only inside `resolve_from_table`, which only `compile_module` calls, so where it did fire
`validate` was green in both modes and a plain `compile` refused: the `@validate-refuses-all` sequence.
Both reproduced on `reference_examples/hfe_hemochromatosis` with one column changed. The predicates are
shared now; the published `resolution: ` / `strict resolution: ` prefixes are unchanged, because that
text is API.

**RM208 — two clients put the translation inside the retry, so one never retried and one never
translated.** `CrossrefClient.exists` caught `httpx.HTTPError`, the **superclass** of both types its own
`@retry` matched, and turned a `ConnectError` into a withhold before tenacity could see it: **one**
upstream request measured where `attempt_floor(3)` asked for three, and the knob a deployment is meant
to raise moved nothing. `GwasCatalogClient` had the mirror image — the transport leg re-raised bare for
the decorator and nothing translated it once the attempts ran out, so `associations_for` raised a raw
`httpx.ConnectError` while its own docstring said "Both legs are translated". Both got the
`_request`/`_get` split every other client in the tier already had.

The guard walks the **package**, not the roster: both clients sat in the contract suite's `exempt` set,
and a guard that iterates a roster inherits its exemptions — the RM101 blind spot one file over. GWAS's
exemption is removed rather than re-argued.

**RM209 — the publish half walked the root-file registry and the pull half did not.** `upload.py` walks
`locations.SNAPSHOT_ROOT_FILENAMES`; `download._provision_snapshot` iterated a hand-kept
`(release.json, LICENSE.txt)` pair. So RM198's `avi_knots.parquet` was published and never pulled — and
since the AVI lane stores no `PHRED`, a pulled lane held scores nobody can rank and `alphagenome check`
refuses it. Two docstrings over that code said the registry was walked; they described the design, and
the copy beside it was what ran.

**RM210 — one finding, two counts.** `_cross_check_literature` runs on both sides and every message
it builds embeds a count; the pre-flight was handed the tables as loaded and the compile the tables
after the symbolic drop. `pharm_variants.csv` is both droppable and a citation site, so a row that is
both made the two sentences differ by a number — and a dedup that compares strings kept both. One
manifest carried "1 citation(s) … ['99999999']" beside "2 citation(s) … ['29165669', '99999999']" with
`warnings_summary: {literature_row_uncited: 2}` for one finding. The repair is to make the inputs
agree rather than to stop re-running: the post-drop view was already computed three lines earlier.

**RM211 — `@parity-by-check`, on the sibling RM93 left behind.** `_check_gene_metrics_arithmetic` is
the exact structural analogue of the check RM93 moved into the pre-flight, and stayed compile-only for
two releases, so a module whose `oe_lof` disagreed with `obs_lof / exp_lof` passed a green `validate`
and warned at compile. Four checks moved — the arithmetic one, the two **gene**-keyed orphan checks
(`gene` is authored and nothing fills it), and the declared-licence check. **Five deliberately did
not**, and that is recorded rather than left implicit: four are keyed on position or `variant_key`, so
asking them before resolution would report every rsID-only row as an orphan, and `_source_checks`
needs a set that is complete only after the last sidecar is read.

**RM212 — the AlphaGenome key in a `.env` was invisible to the two paths that read it.**
`@credential-where-read` has two clauses and only the first was kept: `expression._connect` — the one
function whose docstring cites the rule — read `os.environ` without `load_env()`, and nothing else on
`alphagenome expression`'s path loads a `.env`. So the pass refused with *is not set* while the key sat
in the working directory. `cli._atlas_client_or_none` had the same gap, failing quietly into the knot
interval. Both refusals now carry `missing_credential_reason`, because `export VAR=` is strictly
stronger than never setting it and "not set" sent an operator to the wrong fix. Same incident as the
PharmVar lane's, whose comment already says a pre-check answering differently from the code it guards
is worse than no pre-check.

**RM213 — `merge_key` collapsed silently on an empty key.** Its docstring says a silent `()` would
merge every row into one; it raised for a model declaring **no** key and returned `()` for one
declaring an **empty** key, which is `MeasureBinRow`'s base-class default. Latent — the table is
authored and every subclass overrides — and fixed because the next kind to inherit the default would
find the collapse in a merge pass instead.

**RM214 — the allele grammar is case-insensitive and the sort beside it was ASCII**, which orders every
uppercase letter before every lowercase one. So `A/g` validated and `a/G` did not: one unordered pair,
two answers. Sorted on `str.casefold`, stably, so every previously-valid value still validates —
a loosening, minor-legal. **RM215 is the half it leaves open** and is filed for 1.0: the cell is stored
verbatim, so those two spellings still hash to two `content_signature`s, and normalizing allele case
moves an identity key.

**RM216 + RM217 — the superset sweep the round owed.** Take each `*_FROM_CODE.md`, pull every
backticked identifier, keep the ones the package defines at top level, grep them against the
maintained doc: **341 real surfaces absent** across the three tiers. Most are legitimately delegated —
per-field and per-column names belong in the dated snapshot, not in a hand-kept table that loses one
(`@fieldnames-from-model`). Two classes are not.

`ENRICHER.md`'s exception-contract § carried a ten-row table against a tier defining **83 error
classes**, 51 of them named nowhere — in a section titled *what a caller catches*. The complete roster
is now grouped by what raises them, because the groups are the contract, with the narrowing column
asserted to be a real subclass ladder (`except` order is load-bearing). And eight of `vocab`'s 29
vocabularies were missing from `SCHEMAS.md`, two of them from every maintained file; the roster there
carries count, openness and purpose but deliberately not members.

**RM218–RM221 — the long tail, and what it says about where drift lives.** The round's second pass
worked through the candidates the snapshots recorded but nobody had verified. Four more items came
out of it, and three of the four are the *same defect class one layer out from where the rule is
written down*:

- **RM218** — `test_counted_prose.py` enforces "no number beside a registry" for `docs/` and stops
  there; `compiler.py`'s own module docstring said "twelve" against 23 parquets and `_vrs_gap_reason`
  said "six reasons" against 8 arms. Neither number was re-counted: both sentences state the rule, and
  the guard asserts what each stood in for — for the reasons, that the arms are **pairwise distinct**,
  which a count never checked. A 15-name `issubset` **floor** over a 39-column schema became an
  equality, and `validate_spec`'s docstring stopped claiming `strict` "changes severity only".
- **RM219** — `download.py` documents that every fetch stages through `.part`, and one of its own
  fetches did not, so a repo publishing no `release.json` got a **0-byte** one. That converts *nobody
  said* into *the description is corrupt*.
- **RM220** — `--offline` had two readings and `expression` had the wrong one for a **licence-gated**
  source, so an injected client fetched under a flag documented as making no egress. The axis the two
  readings differ on is now written down; `gwas` keeps its behaviour, deliberately, because the GWAS
  Catalog is ungated.
- **RM221** — Rich ate `[atlas]` and `[dev]` out of three help texts, the extra's size disagreed
  across five places, "vendored" survived RM196 in two, and `VALID_VERIFICATION_CHECKS` said `enrich`
  writes "six" against eight.
- **RM222** — the CIViC drafter wrote a licence row on a run that drafted **nothing** (the rule was a
  comment above a gate that only checked `dry_run`), and the row carried no `dataset` because
  `record_source_terms` had no parameter for one — so a CIViC-drafted module sat **outside** the
  currency check `--verify-datasets` runs.

**What the round says about itself.** All three are shapes this repository had already written a rule
against — a hand-kept list beside a derivable one, a check on one side of the validate/compile pair, a
translation on the wrong side of a retry. That is the same finding the 2026-08-18 round produced with
RM93–RM100, and it is the argument for the method rather than for any of the fixes: reading a reference
against its code confirms sentences, deriving it again asks which of two documents is wrong.

## 2026-09-11 — the axis the AVI artifact threw away, as the tenth derived-fact sidecar

**RM194 + RM200 shipped together, because they were always one build.** `expression_effects.csv` →
`expression_effects.parquet`: one row per `(variant, gene)` saying which way a variant moves that
gene's predicted expression, how many of AlphaGenome's 371 tissue tracks agree, and how far the
variant sits from the gene. Filled by a new `just-dna-enricher alphagenome expression`.

**The design question RM200 could not settle dissolved rather than being decided.** It asked whether
non-commercial Atlas Output may become a *stored* value at all, given RM193's position that it enters
as a finding and never as one. The answer is a third route: a **derived sidecar**, which honours that
rule literally — nothing here is authored, nothing enters `content_signature`, and the compile gate
still reads `sources.csv` and nothing else — while carrying the per-gene direction a finding would
have had to flatten into prose. Half cost under Principle 9 rather than full.

**One scorer of twenty-two, and the other twenty-one are a measured refusal.** `RNA_SEQ` is the only
one with a gene axis, the only one whose disagreement across tracks is meaningful rather than flat,
and the only one that attributes its own claim to a gene. `CAGE`'s top-5 of 546 tracks carry 2–7% of
the effect and the concentration runs *backwards* to effect size; `CHIP_TF`'s leading factor is
whichever TF happens to be measured once.

**`distance_to_gene` is the column that makes the table usable, and null is one of its values.**
Distal scores run ~10× lower than scores at the gene, so a flat `--min-score` keeps only the proximal
rows while looking like it filtered on effect — the failure RM194 exists to prevent. The distance
comes from the MANE lane, and a deployment without it records the absence rather than an interval
edge; the manifest publishes `without_distance` so a whole table of them is visible before a join.

**What the schema gained:** `ExpressionEffectRow`, `expression_effect_signature`, a
`manifest.expression_effects` block, an `overrides.csv` target keyed `(variant_key, gene)`, and the
`expression_effect` source layer. `alphagenome_atlas` is a second source name because one
`(source, layer)` key cannot carry two licence classes — the AVI artifact is Permissive Use while
this scorer's output is non-commercial, and that one is **documented** rather than read off a page.

**Three bugs only real execution could find**, each one a case where every offline fixture agreed with
the code that built it: the Atlas wants `chr22` on the wire where a module stores `22`; a snapshot's
`summary.parquet` lives under `data/` rather than at its root; and a lane *directory* existing is not
the same as a lane being built. The first is now fixed by the client owning the spelling, as it
already owns the 0-based/1-based conversion.

Verified end to end against the live service and a real MANE lane: 303 rows compiled into a module,
`compile → reverse → compile` byte-identical with `artifact.digest`, `content_signature` and
`expression_effect_signature` all stable.

## 2026-09-11 — the registry's field notes: five things a caching proxy had to work around

`just-dna-enricher` only, inside the uncut 0.7.0. just-dna-registry filed S91–S95 while building its
0.25 caching-proxy surface over this package — `GET /caches`, a hosted `lookup_*`, egress metering —
and none of the five blocked them. Four shipped the same day; the fifth is an idea, filed as one.

- **RM204 — the status half of the cache registry is a function** (S91). `caches.lane_status()`
  returns one `LaneStatus` per lane and `cache status` renders it, so a consumer serving the same
  answer stops re-deriving the loop. A third state, **`occupied`** — the place the lane looks is
  non-empty and holds no snapshot, the target `prepare` refuses — used to print as `absent`, which
  sends an operator to run a pull that will decline. `looked_in` names which directory the verdict is
  about, because status reads the override and `prepare`'s refusal reads the default.
- **RM206 — `LookupClients` has one lazy path** (S92). `ensure(name, factory)` builds a client under
  the bundle's lock on first use and keeps it; six legs had been building a per-request client and
  closing it, discarding exactly the pacing state the bundle exists to keep, and two assigned back
  without a lock. `close()` walks the derived `CLIENT_FIELDS`; a `lookup_*` call given no bundle closes
  the one it built. The CPIC half stays consumer-side: `draft_gene(client=)` already shares pacing.
- **RM205 — the hint payload names lanes, not paths** (S93). `VariantHint.checked` holds labels only,
  the unreadable-snapshot finding interpolates the label, and the new `VariantHint.snapshots` (label →
  path, every snapshot opened or tried) is the one field carrying a filesystem path — drop it and
  audit nothing else.
- **RM203 — `PacingGate.spent`** (S95). Admissions so far, one per `wait()` that returned, which is
  one upstream *attempt* because the clients wait inside their retry loop. A host meters egress from it
  instead of charging by request shape.
- **S94, a resolver rung that consults a configured peer**, is in ROADMAP's 0.7 idea-book, not an
  `RMn`: the consumer called it a suggestion and had not designed it, and the one thing the entry keeps
  is the gate — a peer serving answers from a licence-gated snapshot is neither a fetch nor a read of
  an operator-built snapshot, and the licence table has no row shape for it (RM27's undesigned axis).

All four shipped items are additive on the enricher: new fields, a new function, a derived tuple,
one new rendered line beside two byte-identical ones. One value changed on a read field — `checked`
members that were paths are lane names now — which is what the reporter asked for and what the live
leg's `ensembl-rest` had already set the pattern for.

## 2026-09-11 — RM201: a declared correction now says which modules it can reach

`just-dna-format` only, inside the uncut 0.7.0. A registry adopting `needs_recompile` for its
re-publish sweep reported (S90) that a correction declared for `gene_metrics.parquet` re-published every
module in its catalogue, because nothing in `DeclaredChange` could say the change reaches only modules
carrying that block — and it refused, correctly, to read the rule out of `target`'s first segment,
since that is a consumer re-deriving our grammar from a field's spelling.

- **`DeclaredChange.requires`** — an optional tuple of dotted manifest paths a module must carry
  non-null for the change to apply, a *necessary* condition rather than the exact reach. `()` means
  every module and `None` means unstated; the three scoped corrections in the 0.7.0 record now carry
  `("gene_validity",)` (RM108) and `("gene_metrics",)` (RM110), and RM121's `stats.genes` pair stays
  `None` on purpose, because every module carries the field and presence cannot spell "the modules whose
  lead table named no gene".
- **The predicate is ours.** `DeclaredChange.reaches(manifest)` is three-valued — `False` is the only
  answer a consumer acts on — over the pydantic manifest or the mapping `json.load` returns alike
  (`manifest_carries` is the walk); `RecompileAnswer.declared_for(manifest)` keeps everything but a
  certain miss, so an unstated reach costs a version number rather than a wrong value left standing.
- **Forced, not defaulted.** A test asserts as an equality which shipped corrections leave `requires`
  unstated, so a future correction added without deciding its reach fails in the suite. Every required
  path is walked against the manifest models, the same way `manifest_fields` already is.

Additive: a new optional field on a package-level record, minor-legal, and a consumer that ignores it
keeps the behaviour it has. Docs: SCHEMAS § The release record, INTEGRATION_0_7 § 2.8.

## 2026-09-11 — RM200: the API has expression direction, and the scorer that looked most useful does not survive being measured

The shipped AVI artifact is one number per variant with the sign discarded. The Atlas serves
twenty-two scorers, and nobody had asked which of the other twenty-one a module could take. Measured
against the live service.

**A correction to our own probe first.** ALPHAGENOME_ATLAS.md § 4.7 concludes *"there is no
expression direction anywhere in the model"*. That is true of the **AVI aggregate**, whose eighteen
features are all `MAX_ABS_*`, and **false of the API**: eight scorers report `is_signed=True`,
`RNA_SEQ` among them. AVI throws the sign away; the others never had it thrown away.

**`RNA_SEQ` is the one to adopt, and the reason is structural.** It is the **only scorer with a gene
axis** — its shape is `(genes, tracks)` and the gene count varies with the window, 61 at one variant
and 48 at another, against `(1, N)` for all twenty others. So AlphaGenome makes the gene attribution
itself, which is exactly what `@gene-map-is-another-sources-attribution` demands: a gene claim comes
from a source's own per-record attribution, never from a span the caller drew. Signed, 371 tissue
tracks, 22,631 values at one variant — expression, per gene, per tissue, with direction.

**`CHIP_TF` was the most promising candidate and it is refused.** All 1,617 tracks carry a real
transcription factor code, so "this variant disrupts CTCF binding" looks sayable. Aggregated by TF
over 751 factors, the top three carry **1–3% of the mass**, the concentration **does not track effect
size** — the `PHRED` 84 variant is no more concentrated than the `PHRED` 1 one — and every leading
factor is a **singleton track**, so the "top TF" is whichever one happens to be measured once.
Naming a TF from that would publish a sampling artefact as a mechanism.

**And `*_ACTIVE` is not what its name suggests**, which is the finding worth keeping. It is an
activity **level**, not a variant effect: raw assay units, barely moved by swapping the ALT. So it
does not describe the variant, it describes **the locus** — "this position sits in open chromatin in
these cell types", which is a claim the format holds nothing like today. Every track carries a
`nonzero_mean`, so a level normalises to fold-over-typical; without that a raw 31 and a raw 0.7 are
incomparable, which is why a first pass found all 167 tracks "above threshold" everywhere.

Filed with what still has to be decided: what one authored cell would record, whether this is a check
or a column, and that `CAGE` — 546/546 tracks negative at the extreme variant, the only signal so far
that looked like a claim — has **not** been put to the same test and should be before anyone believes
it. All of it is non-commercial Output and needs the second source name `alphagenome_atlas`.

## 2026-09-10 — RM197 and RM199: the ALT column a proof removed, and the description a publish sends last

**RM197 — wide by position.** The AVI lane stores one row per locus with three ALT-score columns and
**no `alt` column at all**: `chrom, pos, ref, alt0, alt1, alt2`. **3.371 B/row against 3.882**, so
29.7 GB rather than 34.2 — taken now because RM198 publishes the lane, and transfer size binds where
local disk never did.

The column disappears because of a **proof**, not an assumption. Which base each column means is
`{A,C,G,T} − ref` ascending, a function of `ref` alone, so nothing travels beside the data — and that
is only well-defined if every locus really carries all three. Measured over the whole corpus first:
across 24 contigs and 8,812,917,339 rows, `rows == 3 × 2,937,639,113 positions` exactly, `pos`
sorted, `alt` strictly ascending within a position, no `alt` equal to `ref`. Three *distinct
non-ref* bases must be all three. Zero violations.

Two earlier attempts at that check were **OOM-killed** — `group_by(pos)` and `n_unique` both hold
billions of keys. Counting boundaries in a sorted column holds nothing and did the genome in 178
seconds; the technique is the transferable part.

**It is not a schema break.** `to_long()` recovers `(chrom, pos, ref, alt, score)` rows from the
stored ones with no lookup table, so RM193's join is unchanged — it converts the handful of rows it
already filtered to. The round trip is tested against the **published source text**, not against
another derivation of the same parquet.

**And the builder re-proves the property on every build**, refusing a locus that breaks it. Padding
a missing ALT with a null would silently redefine what `alt1` means at that locus. That refusal
immediately caught a defect of ours: `_stream_lines` yields whole *lines*, and a locus is three
lines, so a chunk boundary split one — the genome-wide build stopped at `chr1:1196920`, a locus the
file carries in full. Every test passed while that was true, because the 4 MB fixture fits in one
64 MB chunk. The regression test builds the same slice at 64 KB and demands an identical table.

**RM199 — `release.json` goes last.** It is what a puller reads to learn which release it holds, so a
publish that lands the description and then fails leaves a snapshot that *reads as* provisioned and
is not. Payload first, description second, on every path — and the ordering lives in
`SNAPSHOT_ROOT_FILENAMES` rather than in the publisher, so a `--dry-run` prints the plan in the order
the upload sends it.

Above **5 GB** the payload goes through `upload_large_folder`. That is an atomicity choice rather
than a speed one: `upload_folder` is a single commit with no resumption, right at megabytes and
wrong at 32 GB where a failure at 30 GB starts over. The large uploader chunks, retries and resumes,
at the cost of not being atomic — which is why there is a threshold instead of always using it.

A declared retirement on that path is **refused**, naming both rules: RM186 promises the arrival and
the departure are one commit, and the large uploader cannot give one. Doing the deletion quietly in
a separate commit would leave exactly the window RM186 exists to close.

## 2026-09-10 — RM198: the AVI lane joins the cache surfaces, and the publisher nearly dropped the file that makes it usable

With RM195 settled, the AVI lane is publishable, and wiring it into `cache status` / `pull` /
`prepare` / `upload` took three fields — the lane registry means no per-lane branch anywhere. It is
the first lane that is **pullable without being buildable**: this tier may not fetch the gated
88.5 GB source, but the 32 GB re-encoding is Permissive-Use output, so an operator who cannot
download the artifact can still provision the lane. That is the whole reason to publish it.

**The defect wiring it found is the third of its exact shape.** `plan_reference_snapshot` collected
`data/*.parquet`, the sidecar *directories*, and then a **hardcoded pair**: `release.json` and
`LICENSE.txt`. `avi_knots.parquet` is a root-level sibling of `data/` — one small parquet rather than
a directory of them — so it would have been dropped silently. The published snapshot would have
looked complete, every score present and `release.json` valid, and **nothing on the other side could
reconstruct a `PHRED`**, because the artifact deliberately does not store one.

That pair was itself a repair: `LICENSE.txt` is only in it because a share-alike snapshot had already
gone out without the terms it exists to carry. So the names moved to
`locations.SNAPSHOT_ROOT_FILENAMES` and the publisher walks them — the same move `CACHE_LANES` is,
one layer down — and a fourth such file added to a lane and not to the registry now fails a test
rather than a publish.

**Filed rather than improvised: RM199.** `publish_reference_snapshot` uses `upload_folder`, which is
one atomic commit with no resumption, and every lane published so far is at most ~200 MB. The AVI
snapshot is 32 GB over 26 files with a 2.7 GB largest member. `upload_large_folder` is what the Hub
documents for that shape, but it is **not atomic** — and a publish that lands the parquets then fails
before `release.json` leaves a snapshot that looks provisioned and cannot name its release. Commit
ordering is a design decision, not a parameter, so it is written down rather than guessed at.

The dataset repo exists at
[`just-dna-seq/alphagenome_avi`](https://huggingface.co/datasets/just-dna-seq/alphagenome_avi) with a
card and no data. Nothing publishes without an explicit `--publish`.

## 2026-09-10 — RM195 and RM196: a pinned page settles the licence, and the repository stops vendoring somebody else's source

Two of the AlphaGenome round's open items closed the same evening, and both are about what a
repository should carry as evidence.

**RM195 — AVI may be used commercially, and now the repository can show why.** The Additional Terms
define a "Permissive Use Downloadable Artifact" class and grant it commercial use, then delegate
**membership** to a section of the Atlas website. None of the four pinned terms documents named a
single artifact, and that page is a sign-in-gated single-page app. So the most consequential claim
about this source shipped as `commercial_use=None` — unknown is a value, `None` is never `False`, and
unknown commercial terms warn rather than gate.

The maintainer saved the page. It carries its content as **embedded JSON rather than markup**, which
is why every attempt to fetch it had returned navigation chrome, and it says: *"Permissive Use
Downloadable artifacts for commercial and non-commercial use"* → **AVI SNV scores**; *"Downloadable
artifacts for non-commercial use only"* → merged splicing scores and feature importance scores. So
`commercial_use=True`, and it independently confirms why the builder refuses the other two artifacts
by name. The whole page is pinned (7.1 MB → 1.1 MB gzipped) with a greppable extraction; the test
asserts against those bytes rather than a constant.

**`redistribution=True` is a reading, not a clause**, and the entry says whose. Prohibition 1 permits
sharing "indirectly via … open source release", and an openly published snapshot — carrying the Use
restrictions inside it as `LICENSE.txt`, which restriction 3b requires — was read as one. The three
permission axes now rest on three different kinds of ground and `sources.csv` shows only booleans, so
a test records which is documented and which is decided.

**RM196 — `pip install just-dna-enricher[atlas]` used to install two packages and then fail to
import.** The protos lived in `docs/`, the bindings were git-ignored, and neither reaches a wheel.

What shipped is not "commit the generated code" or "vendor harder": **the repository now carries a
pin rather than a copy.** A commit id and a sha256 per file; `atlas_protos.fetch_protos()` downloads
from `google-deepmind/alphagenome` and refuses anything that does not match; `enricher/hatch_build.py`
runs that and `protoc` at build time. Both trees are git-ignored and deliberately **not**
build-ignored, so the sdist and wheel carry the files while the history does not. A commit id proves
what git had; a digest proves what arrived.

Only the enricher moved to hatchling — **build backends are declared per package**, so
`just-dna-format` and `just-dna-compiler` are untouched. `hatch-protobuf` was measured and cannot do
the job: it has no import rewriting, and that rewrite is what stops the generated package being
named `alphagenome` and shadowing the real wheel.

Three things only the real build found: upstream's Apache-2.0 `LICENSE` is at the **repository
root**, not beside the protos; hatchling globs `LICEN[CS]E*` for the *package's own* licence
metadata, so a fetched `LICENSE` was added twice and mis-advertised as ours; and `force_include`
duplicates files that live inside the declared package, where `artifacts` is the right mechanism.
Verified from a clean venv: installs with `grpcio` and `protobuf` alone, imports, and
`find_spec("alphagenome")` is `None`.

`docs/vendor/` keeps the terms documents and the download page, and its README now says why — those
are **evidence about licensing**, which should be frozen in the repository. Upstream's source code is
the opposite kind of file.

## 2026-09-10 — the AVI lane built genome-wide: 8.8 billion rows, 34.3 GB, and two defects only the real thing found

`just-dna-enricher alphagenome build` has now been run over the whole artifact. 88.5 GB of tabix TSV
becomes **34,291,319,173 bytes over 24 parquets — 3.891 B/row — in 85 minutes** on twelve streams.

**Every published number cross-checks against a measurement taken independently:** 8,812,917,339
rows and 672,931 genuine zeros against the probe's own counts, 49.30% negative against its §1.4, and
**41,474 knots against a table a different session built from a different pass over the same bytes**
— compared knot by knot, not by count, with zero raw values in one and not the other, zero `n`
disagreements and zero `phred_lo` disagreements. Exactly one knot straddles any integer `PHRED`
threshold from 1 to 50: `0.00076`, 676,356 rows, spanning 2.99961 to 3.00027.

**Two defects the real artifact found that no fixture could**, and both are the same shape — a thing
that is correct at every size a test can reach and wrong at the size that matters.

`pl.len()` is `UInt32`. Every contig fits it — chr2, the largest, is 721 M rows — and the corpus
does not, so summing the per-contig knot tables wrapped 8,812,917,339 to **222,982,747**, which is
`− 2·2³²` exactly. Nothing else in the pass would have noticed: the parquets were right, the
per-contig counts were right, and the curve would have looked plausible while describing a fortieth
of the data. The reconciliation check that requires `sum(n)` to equal the rows written is what
caught it, 65 minutes in.

And `alphagenome check` joined the module's variants against the snapshot *before* filtering it.
On a fixture that is merely inelegant; on 34 GB it was fatal — the first smoke test was killed by
the OOM killer on a module with twelve variants. It now picks parquets by contig from the filename
and filters `pos` inside the scan, where parquet's row-group statistics skip almost everything
before a row is decoded. The same query takes **4 seconds**.

A third, smaller and caught in the same run: the check's `subjects` was `decided + unanswered`, and
a variant whose knot straddles the threshold is legitimately in both — so a three-variant module
published a denominator of four.

Per-contig knot aggregates are now parked until the merge succeeds. They are built from `PHRED`,
which the artifact deliberately does not store, so they cannot be recovered from the finished
snapshot — which is why the overflow cost a full re-read rather than a retry.

## 2026-09-10 — the artifact is 34.2 GB, and the 43 GB was the tape measure

A correction to the RM191 entries below, and the reason it gets its own heading is that the mistake
generalises further than the number does.

The first genome-wide build measured **4.878 B/row → 43.0 GB**, against the 34.4 GB the design had
projected. That went into RM191's history entry, into a new RM197, and into a sentence saying the
design's figure "reproduces in neither layout". **All of it was wrong, and the defect was in the
thing doing the measuring.**

The builder assembled each contig with `scan_parquet(...).sink_parquet(...)` — the memory-cheap way
to concatenate — which fragments the result into one arrow chunk per morsel: **1,432 of them for
chr22**. Parquet writes at least one row group per chunk, and a sorted `pos` column only
delta-encodes *within* a row group. Varying nothing else on the same frame:

| arrow chunks | B/row | genome-wide | `pos` alone |
| ---: | ---: | ---: | ---: |
| 1–64 | 3.871 | 34.1 GB | 1.249 |
| 128 | 3.904 | 34.4 GB | — |
| **1,432** | **4.892** | **43.1 GB** | **2.067** |

Assembly now reads the chunk files in bounded groups, rechunks each group — one small copy at a
time, rather than a 14 GB rechunk of chr1 for no gain — and the same contig writes at **3.882 B/row,
34.2 GB**.

**Two things worth carrying out of it.** Setting `row_group_size` explicitly is *worse at every
value tried* (4.7–5.1 B/row against 3.88): the default adaptive sizing is what responds to the data,
so the obvious knob moves it the wrong way. And what actually governs is **rows per chunk, not chunk
count** — measured on two different slices, the cliff sits near twenty-odd thousand rows per chunk
either way, so a cap expressed in chunks is data-dependent. The builder carries both.

The lesson is the one this round keeps finding, pointed the other way: a measurement disagreed with
a document, the document was assumed wrong, and **the disagreement was in the instrument**.

## 2026-09-10 — the Atlas interval RPC works hand-built, and the reason it looked broken was one enum

`AtlasClient.score_interval` lands, which is the half of the client RM192 deferred and the thing
RM194 was waiting on. It is worth its own entry because what it cost was not what anyone expected.

The blueprint recorded the interval RPC as unreachable from a hand-built client, needing "an
`x-goog-fieldmask` header and 32 bp chunking". Measured against the live service:

- **The field mask is optional.** The same interval answers identically without it — asserted as
  equality of the two answers, not as "both calls succeeded".
- **32 bp chunking is not a requirement.** A 128 bp interval answers in one call; the SDK's 32 bp
  sub-intervals are how it parallelises, not what the protocol demands.
- **`Interval.strand` was the whole thing.** The `Strand` enum has **no zero member** —
  `STRAND_UNSPECIFIED = 0` is the proto3 default — so an `Interval` that omits `strand` goes on the
  wire carrying a value the server rejects, and it rejects it as a bare `INVALID_ARGUMENT: Request
  contains an invalid argument.` naming no field at all.
- **A filter is effectively required**, which is a size limit rather than a rule: unfiltered, 32 bp
  comes back as a **43 MB** message against a 4 MB receive default.

**And an upstream bug, in the pagination.** The server returns a `next_page_token` on an
*exactly-full final page*, and following it fails. A 1,000 bp interval — 3,000 variants, a short last
page — correctly omits the token; 1,024 bp is 3,072, exactly six pages of 512, and page six carries
one whose seventh request 400s. AIP-158 says an omitted token means there are no further pages, so a
client that believes the token crashes on precisely the interval widths that divide evenly. The SDK's
loop has the same shape and never trips it, because 32 bp cannot fill a page. `score_interval`
follows the token *and* stops once the interval it asked for is covered, with an offline test that
reproduces the lying token so this cannot come back as a live-only surprise.

`Interval.start` is **0-based** while `Variant.position` next door is the 1-based VCF one, so the
conversion happens at that boundary and callers of this module pass VCF positions throughout.

## 2026-09-10 — RM193: the Atlas as a resolver, and a check that refuses to run unbounded

`just-dna-enricher alphagenome check <spec>` cross-checks a module's variants against AlphaGenome's
AVI scores. It reports and never repairs, and it exists for the three questions the nine-billion-row
snapshot on your own disk provably **cannot** answer.

**Most of it is offline, by design rather than as a fallback.** Without `--threshold` there is no
question the local artifact cannot settle, so nothing is asked. With one, the knot table names the
candidate set — the variants whose printed score spans a `PHRED` interval containing the cut — from
**466 KB, before a single request is spent**. `threshold_is_safe()` answers the prior question for
the same 466 KB, and genome-wide it is yes at every integer threshold from 1 to 50 except 3.

**The check refuses to run unbounded.** Rebuilding the `PHRED` column by RPC is 272 days and ~92
million requests at the measured rate, so a caller whose candidate set exceeds `--refinement-cap`
gets a refusal that costs zero calls and names the cheaper answer they already hold.

**Three states, kept apart, and none of them a zero.** A `REF` that disagrees with GRCh38 becomes a
finding **carrying the base the server named** — the one thing a local lookup cannot produce, since
a file simply misses and a miss looks like an uncovered position. An indel, or a quantile that
saturated off the top of the `float32` scale, is recorded as *no answer exists*. A transport failure
is recorded as *could not ask* and deliberately produces **no finding at all**: a bad minute at
Google is not a claim about the caller's data. `--offline` gives the same third state rather than a
silent skip.

It emits its own `variant_impact_agreement` check rather than a second `reference_allele`. The Atlas
answers the `REF` question too, but that check belongs to `enrich` and compares against the reference
*sequence* — letting an Atlas outage write a skip against it would make one registry's availability
speak for another's question.

**A bug worth naming, because it was silent.** `VariantRow` normalizes `chrom` and stores `22`;
AlphaGenome ships `chr22`. Joining one onto the other matched nothing and raised nothing — every
variant came back as "absent from the snapshot", which reads exactly like an artifact that does not
cover them. Caught only because the test asserted a positive count rather than the absence of a
crash. The conversion now happens at the boundary, and a test asserts both spellings give the *same*
answer rather than that neither is empty.

**The `[atlas]` extra stays optional**, and a subprocess test with `grpc` blocked proves it: the
offline half of this check, and the whole CLI, must not acquire a 19 MB dependency by the back door.

## 2026-09-10 — RM191: AlphaGenome's AVI scores as a cache lane, and a 466 KB curve instead of a 24.7 GB column

`just-dna-enricher alphagenome build --input <the file you downloaded>` re-encodes AlphaGenome's
Variant Impact scores — 8,812,917,339 SNVs — into a fifteenth cache lane.

**It never downloads, and that is not the usual inject-only rule.** This is the network tier, so it
is allowed to fetch; the reason it does not is that the artifact sits behind a sign-in whose
eligibility clause bars *classes of holder* rather than classes of use. So `--input` is required and
there is no default URL: acquisition is the operator's act under their own acceptance.

**`PHRED` is not stored.** Measured over every row, `PHRED ≥ p` keeps `10^(-p/10)` of the corpus to
four significant figures across four decades — it is an exact within-corpus rank and therefore a
function of `raw_score`. Storing it costs 24.7 GB. A **466 KB knot table** beside the data carries
the reconstruction curve instead, and carries an **interval** per printed score rather than a point,
because the artifact prints `raw_score` to four significant digits and `PHRED` to six. That interval
is the useful part: **a threshold is unsafe iff it lands inside a knot's span**, which is checkable
in advance from 466 KB without reading a data row. Genome-wide, exactly **one** knot straddles any
integer threshold between 1 and 50 — `0.00076`, 676,356 rows, spanning 2.99961 to 3.00027. Every
other threshold is decided.

**`raw_score` is `Int32` at a scale of 10⁵, and the losslessness is checked rather than asserted.**
Both published columns print at most five decimals, so an integer scale is exact where `Float32` is
both larger *and* lossy. The builder refuses a value that does not land on the grid instead of
rounding it, so if upstream ever widens the column the build stops rather than silently disagreeing
with its own source.

**One consumer-facing caveat, measured:** the exactness is about the **decimal**. Recovering a float
with `raw_score_e5 / 1e5` disagrees with `float(printed)` on **53% of rows** — the division rounds a
second time and lands one ulp away. Compare in the integer domain (`score >= 0.1` is
`raw_score_e5 >= 10_000`) and it never arises.

**The artifact is 34.2 GB**, which is the figure the design quoted — see the entry above for why
this said 43.0 GB for several hours and what the difference was.

**Absence stays row-absence.** AVI covers about 95% of the assembly and writes 672,931 genuine
zeros, so an unscored position has no row while a scored-zero position has a row holding zero.

The snapshot carries the Output Terms' **"Use restrictions" section as a `LICENSE.txt` beside the
data**, because restriction 3b requires it to travel *inside* a derivative rather than as a link
when the distributor attaches terms of their own — which a module's `sources.csv` is. `release.json`
records the artifact's own timestamp, which is legally load-bearing rather than provenance hygiene:
the Output Terms pin the applicable version to the date the Output was generated.

**`commercial_use` is recorded as unknown, not permitted** — RM195. The Additional Terms define a
Permissive Use class and grant it commercial use, then delegate *membership* to a sign-in-gated page
that nothing in `docs/vendor/` pins. `None` is never `False`, and unknown commercial terms warn
rather than gate.

## 2026-09-10 — RM192: the AlphaGenome Atlas client, on two packages

`just-dna-enricher` gains a working client for the AlphaGenome Atlas — Google DeepMind's
precomputed variant scores, served over gRPC — and it costs **two packages**, not the SDK's
forty-seven.

**The measurement that decided it.** `uv add alphagenome` resolves to **550 MB and 47 packages**
(re-measured into a clean venv on 2026-09-11; this entry first said 255 MB and 81 — the count was
never run at all, and the size does not reproduce)
(anndata, pandas, scipy, zarr, h5py, numcodecs, pyarrow, matplotlib, seaborn, pyfaidx, absl-py,
fsspec) against a tier whose entire runtime list is httpx/tenacity/huggingface-hub/typer/ga4gh.vrs.
Six of the twenty dependencies that wheel declares are never imported on any scoring path, and
`atlas.py` imports `anndata` at module level so even the SDK's own import path costs 242 MB. The
Atlas score fields are plain `bytes` and the request filter is an AIP-160 string, so `grpcio` +
`protobuf` reach every RPC and `struct.unpack` from the standard library decodes the scores —
**19 MB and +2 packages**, measured in a clean venv on 2026-09-10 at grpcio 1.83.1 / protobuf
7.36.1.

**What a consumer does.** `pip install just-dna-enricher[atlas]`, from a checkout, then
`just-dna-enricher atlas generate` once. The bindings are generated from the three Apache-2.0
`.proto` sources vendored in `docs/vendor/alphagenome_protos/` rather than committed, so what the
repository carries is reproducible input rather than machine-written output. **The extra is
checkout-only for now** — an installed wheel has neither the sources nor the bindings, which is
filed as **RM196** rather than papered over: the client's import is guarded and names the command
to run.

**The error contract is the part worth reading.** The service says no in three ways with three
different remedies, and the types keep them apart: `AtlasUnavailable` (retry), `AtlasRefMismatch`
(your `REF` disagrees with GRCh38 — and the server names the real base, which
`@va-omits-ref` says only this tier can discover), and `AtlasNotScored` (an indel, or a quantile
that saturated off the top of the `float32` scale). `AtlasNotScored` deliberately does **not**
derive from `AtlasRefused`, so an `except AtlasRefused` cannot swallow it and record a zero for a
variant the service never claimed to have scored.

**What is deliberately absent**, filed rather than improvised: no `tenacity` layer over upstream's
vendored retry policy, no shared pacing gate, and no interval RPC — that one is RM194's.

The `alphagenome` extra is **deleted**, and the comment block in `enricher/pyproject.toml` that
argued the light client "is not declarable here" went with it: commit `1f9a84a` had already refuted
it by vendoring the sources, and an argument against what the file now declares is worse than no
comment at all. Twenty-five tests moved into `testpaths` with the code and all twenty-five are
green, including the four live ones against the real service.

## 2026-09-10 — PROPOSAL 0.7 PT4: adopting AlphaGenome as RM191–RM195

**The first live proposal since PT3 closed on 2026-09-03**, and the point at which eleven rounds of
measurement in [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md) become a build.
[PROPOSAL_0_7_PT4](proposals/PROPOSAL_0_7_PT4.md) wins over the roadmap files until its items land.
**Additive throughout — a cache lane, an optional extra, enricher checks and a drafting provider add
no authored column at all**, so the round fits the uncut 0.7.0.

- **RM191 — the AVI artifact as a derived cache lane.** 88.5 GB of tabix TSV to **34.4 GB** of parquet,
  `raw_score` as `Int32`×10⁵ (exactly lossless; `Float32` is larger *and* lossy), and **`PHRED` not
  stored at all** — the 466 KB knot table reconstructs it with zero threshold misclassifications.
  Operator-built, never fetched: the source is 88.5 GB behind a sign-in.
- **RM192 — the Atlas client on two packages, and the `alphagenome` extra deleted.** 22 MB in a new
  `[atlas]` extra against 550 MB and 47 packages for the wheel, six of whose declared dependencies are
  never imported on any scoring path. Already built and tested as `probes/alphagenome_poc/`.
- **RM193 — the Atlas as a resolver, not a source.** Knot-straddle refinement (the API's `raw_score`
  carries ~7 significant digits against the file's 4), `REF` validation that **names the real base**,
  and `UNIMPLEMENTED` recorded as the third state. Reports, never repairs, and refuses an unbounded
  refinement.
- **RM194 — gene-scoped subslices, and the ±512 kb horizon.** Measured: gene-filtered scores reach
  +500 kb and vanish at +700 kb. The filter is required rather than optional — unfiltered fails
  `RESOURCE_EXHAUSTED` — and at ~50 minutes per gene this is a panel tool, never genome-wide.
- **RM195 — `commercial_use=None`, not `True`.** The Terms define the Permissive class but delegate
  membership to a page nothing in `docs/vendor/` pins, so the claim that AVI is commercially usable
  rests on a reading the repository cannot verify. Unknown is a value; it resolves by saving one page.

**The round's standing rule is measured-not-inferred**, and it is not rhetoric: four of the probe
document's own claims were refuted by later measurement, every one a plausible reading of upstream
prose that the bytes then contradicted.

## 2026-09-10 — a 502 KB knot table replaces both the `PHRED` column and the API refinement

Eleventh round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md) § 4.7.2. No `RMn`, no adoption.

- **Rebuilding `PHRED` through the API is 272 days.** 8.81 billion variants at the measured **375
  variants/s** (the interval RPC, 10 workers) is 23.5 M seconds in ~**92 million RPCs**; single-variant
  calls would be 45 years, and even the 14.2% of rows on an ambiguous knot is 39 days. It is also the
  wrong shape of request: prohibition 3 bars republishing the Services, the licence is revocable, and
  credentials are personal — 92 M calls on a personal key to reconstruct a file that is a download.
- **The `raw_score` value set saturates, so the ambiguity is enumerable.** Four-significant-digit
  printing makes it a fixed grid: chr22 alone shows 40,204 distinct values, and adding ~400 M more rows
  across five other regions grows it to **40,888 — 1.7%** — while the **2,001 ambiguous knots and the
  0.000700 widest span do not move at all**.
- **So ship the knots, not the column.** `(raw_score, phred_lo, phred_hi, n)` over ~41,000 rows is
  **501,592 bytes** as parquet (381,432 without counts), and it carries three things at once: the exact
  reconstruction curve, the per-knot ambiguity **interval** — so an ambiguous row reports
  `[lo, hi]` rather than a point, which is `@tri-state-is-the-house-algebra` rather than a workaround —
  and threshold safety decidable by scanning 41,000 rows instead of 8.8 billion.
- API refinement then shrinks to a last resort: only rows on a knot straddling the threshold actually
  in use — ~633,000 genome-wide at threshold 3, **zero at every other integer threshold from 1 to 50**
  — and only if a caller insists on a point estimate where the data supports an interval.

## 2026-09-10 — the precision the file lost is on the API, and neither surface is a superset

Tenth round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md) § 4.7.1. No `RMn`, no adoption.

- **The 3.56e-4 residual is a publishing artefact of the TSV, not a model limit.** The Atlas returns
  `raw_score` as a `float32` — about **seven significant digits against the file's four**. Tested at
  the exact atom that causes every threshold-3 flip: six rows the file prints identically as `0.00076`
  come back as `0.000758832 … 0.000764675`, in an order that makes the file's own `PHRED` **perfectly
  monotone**, and the `PHRED` derived from them reproduces the published column **exactly at all five
  decimals**. The tie was never a tie in the model.
- **Neither surface is a superset of the other**, which is `@two-surfaces-two-denominators` as sharp as
  it gets. The API wins on `raw_score` everywhere; the **file** wins on `PHRED` above 72.247, where the
  API's `float32` quantile saturates at exactly 1.0 and the file still carries values to 89.451. There
  is no single surface carrying the artifact at full fidelity.
- **No other download helps.** The splicing artifact publishes at the same four significant digits, and
  the SHAP artifact carries the eighteen model *features* — also four — and **no AVI score column at
  all**. `AVI_SCORE_FEATURE_IMPORTANCE`, which does sum to the score, exists only as an Atlas scorer.
- So the shape this suggests is not a choice between surfaces but **a bulk build plus targeted API
  refinement**, with §4.8.1's knot rule saying exactly which rows need it — a threshold inside a knot's
  span — and 161 ms per variant making a few thousand of them a matter of minutes.

## 2026-09-10 — sixteen bits for `PHRED` is dominated by not storing it at all

Ninth round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md) § 4.9.1, one question:
`PHRED` rescaled into `UInt16` rather than `Int32`×10⁵. No `RMn`, no adoption.

- **It loses to the free option on both axes.** A rescaled `UInt16` costs **16.3 GB** genome-wide to
  deliver `max |err| 7.63e-4` and 6,615 threshold flips, while **dropping the column entirely** and
  rebuilding it from `raw_score` costs **nothing** and delivers `3.56e-4` and 1,218 flips. Twice as
  inaccurate and five times as flip-prone, for 16 GB. There is no operating point where it wins.
- **And it is not a tuning problem.** Beating the reconstruction's 3.56e-4 needs a uniform scale of at
  least **1,404**, putting the top of the 89.45 range at **125,632** — nearly twice what `UInt16`
  holds. 65,536 codes over that range is a mean spacing of 1.37e-3 however they are assigned, so **no
  uniform 16-bit encoding can match a column that is free.** A density-weighted non-uniform code could
  in principle do better in the dense low-`PHRED` region; it was not measured, and it would still have
  to beat free.
- So the roster is two entries, not three: **`Int32`×10⁵ when the rank must be exact, nothing when it
  need not be.** `Float32` remains worse than both — larger than `UInt16` and lossy where `Int32` is
  not.

## 2026-09-10 — the reconstruction residual reranks, but only inside ties the rounding made

Eighth round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md), following the previous
round's `3.56e-4` residual to its consequences. No `RMn`, no adoption.

- **Threshold flips are lumpy, not smooth, and the lumps are diagnosable** (§4.8.1). Across a 36 M-row
  slice, every integer threshold from 1 to 50 flips **zero rows** except **3**, which flips **1,218 at
  once** — and all of them come from a single printed `raw_score`. `0.00076` occurs 8,443 times on
  `chr22` and spans `PHRED` 2.99961–3.00027, straddling 3.0, so the curve's mean lands a hair below
  and the whole atom moves together. That turns an error bar into a **decidable rule**: a threshold is
  unsafe iff it falls inside a knot's span, 2,001 of 40,204 knots span more than one `PHRED`, the
  widest span is 0.000700, and exactly one integer threshold in 1–50 is unsafe. A "sharp 50" is safe.
- **Rounding does not mend it and makes the worst case worse** (§4.8.2). Rounding to 10⁻³ makes 97.4%
  of rows compare equal, but the **maximum residual rises from 3.6e-4 to 1.0e-3**, because two values
  3.6e-4 apart can land on opposite sides of a grid line. It hides the common case and worsens the
  rare one, and it cannot recover what the fourth significant digit already lost.
- **Reranking is pervasive but microscopic** (§4.8.3): **15.74%** of rows change rank, mean shift 143
  places, but the **largest move anywhere is 3,168 of 36 M — 0.0088 of a percentile**. So "the
  ordering is preserved" is false and "the ordering is usable" is true; the churn is entirely inside
  ties that `raw_score`'s rounding created.
- **Integer packing is strictly better than `Float32`** (§4.9). Both columns print **at most 5
  decimals** (measured over all 117 M `chr22` rows), so `Int32`×10⁵ is **exactly lossless** while
  `Float32` is larger *and* lossy. Whole rows: **59.2 GB against 67.9 GB**, and 34.4 GB keeping
  `raw_score` alone. `Float64` beats `Float32` on `raw_score` for the same reason — a 5-decimal value
  has long runs of zero mantissa bits in `f64` that `f32` rounding scatters into noise. The lesson
  generalises past this source: **where a source publishes fixed decimals, a float is the wrong
  container.**

## 2026-09-10 — where AVI's bytes go, whether `PHRED` is droppable, and what a negative means

Seventh round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md), three measurements
answering three questions the size table raised. No `RMn`, no adoption.

- **The 88.5 GB → 69 GB gap is not container overhead** (§4.5). bgzip's block headers are 0.03% and
  the `.tbi` is 3.2 MB. Uncompressed the TSV is **310 GB**, so DEFLATE already gets 3.5× on it. What
  parquet cannot beat is the payload: written in isolation the two float columns are **54.7 of 67.9
  GB — 80%** — while `pos` is 11.0 GB and `ref`/`alt`/`chrom` together 2.1 GB. Text holds up because
  the values only ever had 4–6 significant digits and DEFLATE squeezes the rest, where an IEEE float
  stores a full mantissa of noise the source never had. Quantising `raw_score` to `Int32`×10⁵ — its
  real precision — costs **2.41 B/row against `Float32`'s 3.15**, and `Float64` beat `Float32` for the
  same reason. An earlier draft of §4.4.3 labelled its float column `f32` when it was `f64`; corrected.
- **`PHRED` is monotone in `raw_score` but not recomputable from it exactly** (§4.6). Zero negative
  steps across `chr22`'s 40,204 distinct values, so there is one 1-D empirical curve. Applied to three
  disjoint regions totalling 59.9 M rows, reconstruction gives mean `|Δ| 2.2e-5`, **max 3.56e-4**, and
  `Σ|Δ|` of 322–765 against an `ε·N` budget of ~3e-9 — the machine-epsilon test fails by eleven orders
  of magnitude. The cause is not float error: the file prints `raw_score` to **four** significant
  digits and `PHRED` to **six**, so 2,001 raw values carry up to **68** distinct `PHRED`s each. It
  reclassifies **zero rows** at `≥10` or `≥20`, so it is exact for triage and lossy for reporting a
  rank — and the framing inverts: `raw_score` is published too coarsely to regenerate `PHRED`.
- **A negative `AVI` is low conservation, not down-regulation** (§4.7). `AVI_SCORE_MODEL_FEATURES` and
  `AVI_SCORE_FEATURE_IMPORTANCE` are Atlas scorers returning 18 values each, and they are the SHAP
  file's columns in order — verified by matching feature 0 against the splicing artifact at two loci
  (4.0252 vs 4.025, 0.0345 vs 0.03451) and against its absence at a third. At both negative variants
  probed the whole score is one feature, the signed `CACTUS_241_WAY` at −20.0 and −11.5, with
  attributions of −1.23 and −0.70 and everything else near zero. The nine regulatory features are all
  `MAX_ABS_*` — sign discarded before the model sees them — so **no expression direction exists
  anywhere in the feature set**. The axis is benign ↔ damaging. The positive extreme decomposes as a
  stop-gain (attribution 1.63), a splicing effect (1.29) and AlphaMissense 0.92 (0.83). Also worth
  noting: `ALPHAMISSENSE` comes back `nan` on non-coding variants, so one input distinguishes
  unmeasured from zero where `MERGED_SPLICING` does not.

## 2026-09-10 — AVI measured whole, and its `PHRED` turns out to be a size dial

Sixth round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md): the 88.5 GB AVI
artifact extracted and passed over in 46 minutes, 24 contigs, 12-way. No `RMn`, no adoption.

- **AVI is genome-wide where splicing was not**: **8,812,917,339 rows** over 2,937,639,113 positions,
  ~95% of the primary assembly against splicing's 42%, and 2.25× the rows. `raw_score` is **signed and
  49.30% negative**, so an ingest calling `abs()` discards what half the corpus says, and it writes
  **672,931 exact zeros** where the splicing artifact had none — so `0.0` cannot be an absent sentinel
  here either.
- **`PHRED ≥ p` keeps exactly `10^(-p/10)` of the corpus** — 79.4321% at ≥1, 10.0002% at ≥10, 0.9999%
  at ≥20, 0.0100% at ≥40, matching the transform to four significant figures across four orders of
  magnitude. The column is the variant's exact percentile rank among all possible SNVs, so **its
  histogram is a straight line by construction**: no shoulder, no natural cut, nothing to discover.
  What it *is* is an unusually honest dial — state the budget, read off the threshold.
- **That refutes an inference this document had already drawn.** From the upstream FAQ alone it looked
  as though the rarity axis was already inside the calibrated score, the background being ~300 K common
  variants at MAF > 0.01. An all-possible-SNV corpus scored against a common-variant background would
  be visibly shifted; it is not shifted at all. The FAQ describes the API's `quantile_score` for the
  recommended scorers, and AVI's published column behaves differently. **`PHRED` is not a rarity
  comparison and cannot stand in for §5's missing allele-frequency axis.**
- **Thresholding on `PHRED` drops every negative-scored variant.** Every row above `PHRED` 5 is
  positive; at ≥1, 36.17% are still negative. A rank discards sign, and nothing in the column names
  warns of it — a design decision disguised as a filter. *Negative-scored*, not *down-regulating*:
  `AVI_SCORE` is not among the seven scorers the Atlas marks `is_signed` and its quantile is [0, 1),
  so the source states no direction and reading one in would be `@field-description-is-a-claim`.
- **Sizes at each cut**, measured on `chr22` and scaled: 69.0 GB for everything with both columns as
  `f32`, **34.4 GB keeping `raw_score` alone**, 6.7 GB at ≥10, 662 MB at ≥20, 70 MB at ≥30. **AVI
  still fits whole, but only one way**: a both-column build needs a cut between ≥1 and ≥5 to reach
  40 GB, while `raw_score` alone holds every row inside the budget with the sign intact — and drops
  nothing unrecoverable, since `PHRED` is the rank and recomputes from a complete `raw_score` column.
  The information lives in `raw_score`, whose magnitude histogram is a genuine lognormal-ish hump
  peaking at 0.032–0.056 with 20.5% of rows.
- **The API saturates where the download does not.** `calibrated_scores` is a `float32`, so the
  largest quantile it can carry caps a derived Phred at **72.247** — and the artifact reaches
  **89.451**. At `chr22:30339156 C>A` (file: `PHRED 84.10132`) the API returns `calibrated = 1.0`
  exactly and the rank is gone, while `raw_score` still agrees to five decimals. About **1,300 rows
  genome-wide**, and they are the highest-impact ones, so `@two-surfaces-two-denominators` applies to
  AVI after all — narrowly, on the rank and not the magnitude. The PoC client had clamped at the FAQ's
  Phred 50 and would have rewritten those as fifty; the clamp is gone and saturation now raises.

## 2026-09-10 — the light Atlas client is declarable after all, and now it is built

Fifth round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md), after reading the upstream
repository rather than the rendered docs. Still no `RMn`, still nothing imported by a shipped package.

- **§6.2 said the 22 MB client was "not declarable". That was wrong.**
  `github.com/google-deepmind/alphagenome` is Apache-2.0 and ships the four `.proto` sources its own
  wheel generates bindings from (`hatch_build.py` calling `grpc_tools.protoc`). The Atlas surface needs
  three of them — **28 KB** — so vendoring those and declaring `grpcio` + `protobuf` is a real
  dependency set. Corrected in place, and the option list went from three shapes to four.
- **[`docs/probes/alphagenome_poc/`](probes/alphagenome_poc/README.md) is the blueprint, test-proven.**
  A working client with **23 passing tests**, 20 needing no network. An AST walk asserts its
  third-party imports are exactly `{grpc, docs}`, which makes the 22 MB figure a property of the code
  rather than a claim in prose; the bindings regenerate from the committed sources; and a live test
  asserts the RPC returns what the 88.5 GB AVI artifact contains. Scores decode with `struct.unpack` —
  numpy is not needed either. It is **outside `testpaths`** on purpose, so the 4,332-test suite is
  unchanged.
- **One real mistake, caught by writing it.** protoc bakes the staged path into every cross-import, so
  staging at upstream's own `alphagenome/protos/` produces a package literally named `alphagenome`
  that shadows the real wheel for anyone with both installed. Staging under the full package path
  fixes it and removes the `sys.path` insertion at the same time;
  `test_the_generated_bindings_do_not_shadow_the_upstream_package` pins it.
- **The error contract is where the house rules land.** Three refusals with three different remedies —
  `AtlasUnavailable` (retry), `AtlasRefMismatch` (the caller's `REF` disagrees with GRCh38, and the
  server names the real base), `AtlasNotScored` (an indel: the answer does not exist). The third
  deliberately does **not** derive from the second, so `except AtlasRefused` cannot swallow it and
  record a zero for a variant nobody scored.
- **The upstream FAQ defines `calibrated_scores`**: the quantile score, an empirical rank against a
  background of **common variants, MAF > 0.01 in any gnomAD v3 population**, ~300 K of them, capped at
  ±0.999990 — so `PHRED` cannot exceed **50**. That matters for §5: **the rarity axis is already inside
  the calibrated score**, and pairing `PHRED` with gnomAD MAF double-counts the same reference set.
- **The merged-splicing discrepancy is not an abs-versus-signed slip.** Upstream's own
  `compute_merged_splicing_score` takes a signed `max`; re-running with it changed nothing, so §6.3's
  finding stands with one candidate cause ruled out rather than assumed away. And the only mention of
  "motif" in the whole repository is the quick-start's note that contribution scores are what discover
  them, naming **tfmodisco-lite**, **tangermeme** and **tomtom** — outside tools. §6.5 confirmed.

## 2026-09-10 — what the API adds over the files is resolution, and motifs are not a dataset

Fourth round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md), measuring the network
surface against the offline copies now that all three artifacts are on disk. No `RMn`, no adoption.

- **Three surfaces, not two** (§6.4). The bulk files, the **Atlas** service (precomputed) and the
  **model** service (computed on demand) differ in a way that matters: indels work on the model API
  and are `UNIMPLEMENTED` on Atlas, exactly as they are absent from the files. Atlas also **validates
  `REF` against the assembly** and names the real base in the error, where a file lookup just misses —
  `@va-omits-ref` answered by the source rather than by us.
- **The API's addition is resolution, not more scores.** One variant unfiltered returns **36,152
  values across 22 scorer blocks** against the files' 20 columns. The breakdown is the finding:
  `CHIP_TF` comes back as **1,617 named tracks** where the SHAP file carries one `MAX_ABS_CHIP_TF`,
  `CHIP_HISTONE` 1,116 against one, `RNA_SEQ` 37 genes × 371 tracks against one. `MAX_ABS_` is a lossy
  aggregate and the **name** is what the file throws away. Median single-variant latency 161 ms, so it
  is not a bulk surface and does not pretend to be.
- **Motifs are not a dataset at either surface, and the announced "Motif datasets" block nothing**
  (§6.5). The string "motif" appears nowhere in the SDK and none of the 22 scorers is one. What reads
  a motif is in-silico mutagenesis, and `query_interval` over a 200 bp window returns a
  **600 × 1,617** ISM matrix in **1.6 s** with a `transcription_factor` column naming every track. The
  files hold a genome-wide ISM matrix already — that is what a score for every SNV *is* — but with the
  TF identity and cell type aggregated away. So the motif conclusion holds and its reason does not:
  the API is the only route because a motif needs per-track resolution, not because a motif dataset
  sits behind it. Motif work is per-locus and network-bound, which puts it on the enricher side as a
  check about a variant, never as something a compiled module carries.

## 2026-09-10 — the Output Terms want the licence inside the artifact, and the dep moved to an extra

Third round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md). Still no `RMn` and still no
adoption; what changed is that the terms are now readable from the repo and the dependency question has
a landed answer.

- **`alphagenome` is an optional extra, not a core dependency of the enricher.** A default install is
  back to its 45-package closure; `just-dna-enricher[alphagenome]` adds 36 more (anndata, pandas,
  scipy, zarr, h5py, matplotlib, seaborn, pyarrow, …). The 22 MB protos-only client measured in §6.2 is
  **not declarable** — the generated stubs ship only inside the wheel, so the light path is
  `pip install --no-deps alphagenome grpcio protobuf`, a deployment recipe rather than a dependency
  specifier, and declaring it would mean vendoring the protos. Nothing imports either yet.
- **Four terms documents are now pinned in `docs/vendor/`** with `pdftotext` extractions and recorded
  hashes: the Additional Terms (2026-09-08), the **Output Terms of Use** (Effective 2025-06-25), the
  Google Terms of Service (2026-07-30) and the Google APIs Terms of Service (2021-11-09). Two binding
  documents are still missing, and §2.8 names them — the Generative AI Prohibited Use Policy, and the
  website section that says **which artifacts are Permissive**, which is the only statement of the
  single most consequential claim in the whole probe.
- **The Output Terms add three things the Additional Terms did not say** (§2.7). The licence text must
  travel **inside** a derivative rather than as a link — restriction 3b makes the "Use restrictions"
  section an enforceable provision anyone attaching their own terms must carry, which is the shape
  `SNAPSHOT_LICENSE_FILENAME` already has for ClinPGx. Google may demand deletion **on breach**, not
  only on termination. And the applicable version is pinned to **the date the Output was generated**,
  which turns an artifact's timestamp into a legally load-bearing field and is the argument for
  recording `license_sha256` and a dated `dataset` rather than linking a live page. The document also
  predates the Atlas by fifteen months and carries no AVI carve-out at all.
- **The SHAP artifact is a 20-column feature table, not an opacity** (§1.5): `MERGED_SPLICING`, nine
  `MAX_ABS_*` modality scores, and three third-party features — `ALPHAMISSENSE`, `CACTUS_241_WAY`,
  `PHASTCONS_470_WAY` — so a module carrying those columns stacks terms rather than inheriting one
  set. Its `MERGED_SPLICING` is the splicing artifact **rescaled by 3.345 ± 0.043**, not copied, so
  neither file recovers the other exactly and a module must say which it read. And it writes `0.0`
  where the splicing pipeline never scored a position — 2.42 M of 2.95 M rows in the window measured —
  so the source itself collapses unmeasured into no-effect, `@unreachable-not-absent` occurring
  upstream of us. Its `IS_INSERTION`/`IS_DELETION` columns are constant `0` across 8 M sampled rows
  despite the filename, so the SNV-only finding survives being checked.

## 2026-09-10 — the AVI artifact is a different corpus, and a 22 MB client reaches all of it

Second round on [probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md). Still no `RMn`, still no
adoption, and **`alphagenome>=0.9.0` is deliberately left uncommitted** in `enricher/pyproject.toml` —
adding it is the decision §6.2 exists to inform.

- **The sizing in §4 was the splicing artifact and nothing else**, which §4.3 now says in its first
  line rather than its last paragraph. AVI is not a bigger version of it: `raw_score` is **signed**,
  its rows start at `chr1:10001` rather than 65,409 (so plausibly genome-wide, ~2.4× the rows), and
  its `PHRED` is not a second score — `PHRED = −10·log₁₀(1 − calibrated)` reproduces the file exactly
  from the API's calibrated percentile, so a parquet needs two columns and not three.
- **A complete Atlas client costs two packages.** The Atlas service (`gdmscience.googleapis.com`,
  `x-goog-api-key`) serves the precomputed scores — **22 scorers**, the 283.9 GB SHAP breakdown among
  them — and the generated protos with `grpcio`/`protobuf` reach all of it: the score fields are plain
  `bytes` that `frombuffer('<f4')` decodes and the request filter is an AIP-160 string. Measured as
  real venvs: **22 MB** protos-only, 85 MB with numpy, **242 MB** for the SDK's own import path
  (`atlas.py` imports `anndata` at module level, which drags scipy/zarr/h5py), 255 MB for
  `uv add alphagenome` — that last figure does not reproduce, and re-measuring it on 2026-09-11 gave
  **550 MB across 47 packages** (probe § 6.5.1). Six declared dependencies — matplotlib, seaborn, pyfaidx, absl-py, fsspec,
  pyarrow — are never imported on any scoring path. Against a tier whose whole list is
  httpx/tenacity/huggingface-hub this is the "dependency tiers are sacred" question, not a size one;
  §6.2 states three shapes (core deps, optional extra, or no client at all) and picks none.
- **The two surfaces agree for AVI and not for splicing** — `@two-surfaces-two-denominators`, measured
  rather than assumed. The AVI file is the API's float32 printed to five decimals. The splicing file is
  not reachable from its own documented merge formula (2.81 against a stated 2.735, 1.83 against
  2.112), and at `chr1:65409` — 10 bp upstream of *OR4F5* — all three splice scorers return zero rows
  at both 128 KB and 1 MB windows while the file scores it 0.003052.
- **The source names its own threshold**, which replaces the invented ones: the splicing docs call
  >1.0 a substantial effect, and that is 9,761,281 rows, 0.249% of the corpus, ~62 MB as parquet.

## 2026-09-09 — AlphaGenome Atlas read as an exploration: three artifacts, three licence answers

**No code, no `RMn`, no adoption.** Google DeepMind published the AlphaGenome Atlas on 2026-09-08 —
precomputed molecular predictions over every possible human SNV — and this is the exploratory read of
what it would take to carry any of it. The record is
[probes/ALPHAGENOME_ATLAS.md](probes/ALPHAGENOME_ATLAS.md); the terms it quotes are pinned in
`docs/vendor/` as the maintainer's saved PDF plus a `pdftotext` extraction, so §2's clauses are
greppable and hashed rather than re-fetched from a sign-in-gated single-page app.

- **The three bulk artifacts are not one licence, and the one already downloaded is the restricted
  one.** Only *AVI SNV scores* (88.5 GB) is a "Permissive Use Downloadable Artifact", usable
  commercially and by commercial organizations; the merged splicing scores (20.6 GB) and the AVI
  feature-importance/SHAP scores (283.9 GB) are non-commercial-only. The Terms make the split a
  definition: the AVI Score is carved out of nearly every prohibition and the *AVI Score Feature
  Breakdown* is expressly not part of it.
- **Four things the Terms need that `SourceRow` cannot say** (§2.6), the first of which is not a use
  restriction at all: eligibility is a bar on **who may hold the data** — "aren't available for any
  commercial entity, even if conducting non-commercial work" — where every gated source the repo
  already carries restricts only what may be *done*. The other three are the no-training-a-similar-model
  clause, a **revocable** licence with a delete-and-tell-third-parties termination obligation against
  P4's frozen digests, and a notice requirement that must travel with a derivative *and* state the
  modifications made to it. Two further shapes are existing gotchas rather than gaps:
  `@acquisition-gate-is-not-a-read-gate` (eligibility gates the download; commercial use of the
  downloaded AVI artifact is expressly permitted) and `@write-the-sourcerow`'s `(source, layer)` key,
  which one source with two licence classes would collide on.
- **The corpus was measured, not sampled** — 3,924,674,451 rows over 1,308,224,817 positions, exactly
  three ALTs each, `chr1`–`chr22`/`X`/`Y` and no `chrM`, covering ~42% of the assembly rather than all
  of it. The score has **no tail toward zero**: 86.7% of rows sit between 0.032 and 0.100 and 0.32%
  fall below 0.01, so discarding "the negligible 90%" is a threshold against a background lump, not a
  filter of zeros. A first pass over the leading 20 M rows of `chr1` would have sized a slice ~55% too
  large; the whole-file numbers are in §3.
- **Size turned out not to be the constraint.** Measured on `chr22` and scaled: the entire corpus as
  parquet (`UInt32` at 10⁻⁶, one row per position, three ALT columns — **verbatim**, since the source
  states six decimals) is **~11.4 GB with nothing discarded and no digit lost**, and a ≥0.1 slice is
  ~1.1 GB. So the design question is not
  which slice fits a budget but whether the artifact is a *lookup table* (absent means unscored) or a
  *finding list* (absent means unscored **or** below threshold, a fresh instance of
  `@unreachable-not-absent`). §4.2 states both and picks neither.
- **The rarity axis exists offline and is 6% populated**, which is worse than absent. The Ensembl
  snapshot the enricher already provisions carries `MAF`/`MAC`, so no new download is needed — but on
  `chr22` only 6.1% of its SNVs have a value, and after the join only **0.61% of AlphaGenome's ≥0.1
  slice has a frequency at all**. "Score ≥0.1 and rare" is ~1.6 M rows genome-wide, small because the
  column is 94% null rather than because the biology says so: `MAF` absent means unmeasured, never
  rare, and a build that filters on it answers a different question than the one asked. §5 states the
  four honest options. Separately, only 9.95% of AlphaGenome's SNVs are observed variants at all, so
  intersecting changes the corpus kind. And **the bulk artifacts are SNV-only**, so rare indels are
  not a slice of them — they exist only through the API, which is per-request, returns 367-track
  matrices rather than scalars, and carries no AVI carve-out.
- `ALPHAGENOME_API_KEY` joins `.env.template` with the PharmVar-shaped warning: personal under
  prohibition 7a, never in a module, fixture or snapshot.

## 2026-09-09 — the pre-cut audit: what a green suite and a passing sweep did not see

**Found by a code audit against the house rules rather than by a failure**, run after the 2026-09-01
readiness measurement had gone 138 commits stale. Every gate was re-measured first and held (the
table in INTEGRATION_0_7 § 5 carries the commit); the items below are what reading the code found
behind the green. Each landed as its own commit with the test that pins it.

- **`resolution.csv`'s writer kept its column list by hand, twice** (`just-dna-enricher`, no output
  change today). `enrich._FIELDNAMES` was a literal in sync with `ResolutionRow` by coincidence,
  paired with a per-column dict literal in `_write_resolution_csv` — the shape `SOURCES_FIELDNAMES`
  had when it lost `redistribution`, and quieter here because `DictWriter` raises nothing for a model
  field the dict simply omits. The next optional column on `ResolutionRow` would have been dropped by
  every enrich run, and a fact column among them would have made `resolution_signature` disagree
  between a hand-filled and an enricher-filled table. Now `list(ResolutionRow.model_fields)` and a
  generic renderer, the idiom every sibling writer already uses; reproduced on the old writer by
  subclassing the model with one extra field, and pinned by the equality plus a full-row read-back.

- **An overlay spelling one key two ways defeated its own coherence rule** (`just-dna-format`; a
  check gains reach, no schema change — INTEGRATION_0_7 § 1 lists it as the fourth check that can
  newly refuse). `_canonical_key_cell` had repaired the *match* — `member=AFR` reaches the `afr` row —
  but `apply_overrides` and `update_targets` still *grouped* by the raw spelling, so two spellings
  were two key groups with one operation each and "one operation per key group" had nothing to
  refuse. Reproduced: an `update` under `AFR` beside a `suppress` under `afr` corrected the row and
  then deleted it with no error, and two `update`s of `faf95` under the two spellings kept the later
  value with the author's first correction silently absent. Grouping now runs through the model
  (`_key_groups`), and a merged group with more than one spelling is refused on a mixed operation or
  a twice-stated field, naming both spellings and the stored key. Two spellings carrying one
  operation on different fields stay one coherent group. The pre-flight `overlay_coherence_errors`
  is unchanged (it has no table to canonicalize against), which is why the refusal lives in the
  function both `validate` and `compile` call.

- **Three clients leaked on a 200 that is not JSON** (`just-dna-enricher`; no schema change). The
  contract test drove a 5xx, a transport failure and a 404, and a maintenance page served with a 200
  is none of those: `raise_for_status()` passes it and `.json()` raises a bare `JSONDecodeError`.
  `identifiers` (OLS4/HGNC) let it reach `cli.py`'s `except ValueError` arm, which sits before
  `except IdentifierUnavailable`, so the run was filed as "rows will not load" and skipped the
  `unreachable` attestation; `ensembl`'s GraphQL leg answering HTML never fell through to REST and
  aborted `enrich` mid-loop; `grch37.variants_at` raised out of a three-valued method. All three now
  translate (`IdentifierUnavailable`, `EnsemblError` → the `(None, None)` withhold, `None`). The
  contract test gains the leg over every client, a `WITHHOLDING_CLIENTS` table pins the withheld
  value across all three legs for the two clients whose contract is a value rather than an
  exception, and the discovery guard now keys on owning an `httpx.Client` rather than on a `Client`
  suffix — `EnsemblResolver` had been invisible to it since RM101. Fourth appearance of
  `@client-exception-contract` in AGENT_NOTES.

- **A directory is not a snapshot — three cache-side repairs** (`just-dna-enricher`; no schema
  change). *(1)* The derived-lane parent guard judged a parent by `is_dir()`, and every adapter
  `mkdir`s before it downloads, so a ClinVar fetch cut mid-body left an empty `out/clinvar/` that the
  guard accepted; `mitomap_miss` then ran, its join found no parquet, and the **child** was the lane
  reported FAILED — the arm the guard's own docstring forbids. Parents are judged by their lane's
  resolver now (`_snapshot_at`), and a supplied path with no payload is reported missing by name
  rather than silently swapped for the machine's older cache. *(2)* `prepare_lane` read `resolve()
  is None` as "absent" and renamed its staging directory onto a target that could exist with no
  payload, so `Directory not empty` escaped the whole `cache prepare` with every later lane
  unattempted; it refuses before the build now, naming `cache prune`, since provisioning never
  deletes, and `prepare_caches` isolates each lane the way `cache pull` always has. *(3)*
  `net.stream_to_file` removed its `.part` only on `httpx.HTTPError`, so a disk that filled mid-body
  left the partial its docstring promised was gone; removed on every failure now, translated only
  for the transport.

- **A rejected partial row widened the author's header, and both drafting writers truncated the
  author's file in place** (`just-dna-compiler`, drafting surface only; no artifact change).
  `append_partial_rows` computed what the batch fills over every partial *before* the loop rejected
  any, so a column only an invalid row filled — or only an already-present row, or a raw `""` —
  was added to a hand-authored CSV, empty in every row; `append_rows` had always decided it over the
  rows it writes. Now decided over the accepted rows, with a blank counting as unfilled, and a dry
  run reports the extension it would have made rather than the one it was asked for. Separately,
  both writers opened the author's CSV with `open(path, "w")` after reading it, so a kill mid-rewrite
  left a valid short file; both go through `atomic_writer` now, the append path copying the author's
  bytes through verbatim, and an AST walk pins it the way the enricher's sidecar guard does.

- **Ten builders wrote `release.json` in place, and `acmg build` its whole snapshot CSV**
  (`just-dna-enricher`; no schema change). The nine spec-dir sidecar writers have been guarded since
  S66; the builders were not, and the three newest (`mane`, `drug_labels`, `strchive`) had adopted
  `atomic_write_text` while the ten older ones kept `write_text` — the next builder would inherit
  whichever neighbour it copied. A truncated `release.json` is at least invalid JSON that
  `read_release` degrades to `None`; a truncated ACMG CSV parses cleanly and is simply short, so
  `verify_acmg_sf` would have reported a gene as "not on the list" with nothing failing. Every
  builder text write goes through `atomic_write_text` / `atomic_writer` now, and the guard walks
  every `*_build.py` by AST rather than a hand-kept function list.

- **The lookup's refusal map was read with a default that is itself a member** (`just-dna-enricher`,
  latent; no output change). `_advisory` read `_REFUSAL_BY_COLUMN.get(column, "redundancy_bearing")`,
  so the next advisory column would have been handed the mildest refusal silently, where
  `identity_bearing` may be the right one, and every output assertion would have passed against it
  (`@lookup-with-a-default-hides-a-new-member`). Indexed strictly now — an unknown column is a
  `KeyError` at the call — and a test walks every `_advisory` call site by AST to assert the
  advised columns are a subset of the map's keys and the map's values are members of
  `REFUSAL_REASONS`. The two entries nothing advises on yet (`gene`, `trait_efo_id`, since 0.5.0)
  are decisions recorded ahead of the lookup that would need them, and stay.

- **The readiness table was re-measured at `a6f31f8`** (INTEGRATION_0_7 § 5): suite 4311/0, lint
  clean, corpus 16/16 with every digest identical to the pre-audit compile, sweep gate exit 0, the
  0.6.6 client at 15/16 on the same one field — its previous row had rested on "nothing touched the
  manifest surface", which RM160 had already falsified. **`dist/` was rebuilt** from a detached
  worktree at that commit: the six artifacts it held were `741ec59` bytes under the 0.7.0 name and
  lacked twenty enricher modules added since. The tag is still the maintainer's.

## 2026-09-04 — the allocator reserved a number when you asked it for help

**Agent tooling only (`.claude/rm-next.py`), no package, no schema, no CLI surface.** Found while
clearing a stale `🔷 reserved` row that RM187 had left in `RM_TOC.md` after the item shipped.

- **Reserving was the default path, so an unknown flag reached it.** `main()` handled `--dry-run`,
  `--note`, `--release` and `--list` and let everything else fall through to `allocate()` — so
  `.claude/rm-next.py --help`, a flag the tool never had, claimed **RM189**, and one more typo while
  repairing it claimed **RM190**. Both numbers are spent (ids are never reused) and share one
  tombstone row in `RM_TOC.md` that names the cause rather than reading as two withdrawn items.
- **The repair**: a `KNOWN_FLAGS` set, a real `--help` printing the usage, and exit 2 on anything
  else. `--note`'s value is excluded from the flag scan, so a note may open with a dash.
- **Pinned by running the version without the guard**, the idiom the lock probe in the same file
  already uses: the unguarded copy reserves on `--nonsense`, the guarded one refuses and leaves the
  index byte-identical. Three tests on the argument surface, which had none — the tool had eleven on
  the lock, the tombstone and the anchor, and nothing on how it reads `sys.argv`.
- Recorded in AGENT_NOTES under `@an-index-is-not-an-allocator`, with the sentinel slip the repair
  passed through on the way (`else -1` made index 0 the exempt slot, so the first argument went
  unchecked — `None` is the sentinel that cannot collide with a real index).

## 2026-09-03 — a download that could not fail politely, and one body for eleven of them

**`just-dna-enricher` only, no schema change.** [RM187](ROADMAP_HISTORY.md#rm187--eleven-bulk-downloads-carried-one-body-in-eleven-copies-four-of-them-leaking-the-transport),
found by a real failure rather than an audit: NCBI closed the connection 180,927,542 bytes into a
193,427,450-byte ClinVar VCF during RM179's republish.

- **A flaky download was a traceback, not an outcome.** `download_clinvar_vcf` raised `httpx`'s own
  exception and `_rebuild_clinvar` catches `ClinVarBuildError`, so the lane could not report
  `built=False` — and it escaped `rebuild_lane` too, which in a full `cache rebuild` aborts every lane
  after the flaky one. Four of eleven builder downloads leaked; the other seven translated.
- **None of the eleven retried**, on the largest requests this tier makes, while every live client has
  had `attempt_floor` since RM42. They now share `net.stream_to_file`: atomic through `.part`,
  translated at the boundary, retried on `TransportError` (a status error is not retried — a 404 from
  a mistyped tag is the same 404 four times over), and restarted from byte zero per attempt.
- **Eleven public signatures are unchanged.** Each downloader builds its own return type from the
  `StreamedFile` it gets back, so the five existing return shapes all stay.
- **`constraint_build` gains the error type it never had** — the reason its download had nothing to
  translate into. `ClinVarUnavailable`, `ClinPgxUnavailable` and `ConstraintUnavailable` subclass
  their lane's error, so an existing `except` still catches them.
- **Two defects the sweep found:** `pubmind_build` was the one handler of eleven that left its `.part`
  behind on failure, and four of them computed a sha256 while streaming and only logged it.
- **Consumer-visible:** a failed bulk download now raises the lane's own type rather than an `httpx`
  one. If you catch `httpx.HTTPError` around these builders, catch the lane's error instead — the
  `httpx` exception is kept as `__cause__`.

## 2026-09-03 — what a publish may delete, and what it may stop describing

**`just-dna-enricher` only, no schema change.** Two policy decisions taken with the maintainer after
the published-artifact audit, and the code that enforces them. The premise being corrected is this
repository's own: `@snapshot-accumulates` had been read as *never delete*, and a HuggingFace dataset
repo is git-backed — a delete is a commit and a superseded revision still resolves. The risk was never
lost bytes; it is that a retired file goes on answering 200 to whoever still asks for it, and that a
sweep removes what nobody looked at.

- **A publish refuses to leave a sidecar undescribed**
  ([RM185](ROADMAP_HISTORY.md#rm185--a-publish-could-replace-a-releasejson-describing-bytes-it-was-not-carrying)).
  The general form of RM179: a snapshot's `release.json` describes every half the artifact carries, so
  a publish carrying one half replaces the whole description while add-never-delete leaves the other
  half as bytes nothing describes. `OrphanedSidecarError` now refuses that publish and names the file
  and the command that builds the missing half. **The guard reads the remote tree, not the remote
  `release.json`** — by the second bad publish the block was already gone while the sidecar was still
  there, so a guard interrogating the description would have passed it. `--dry-run` runs the same
  check and exits non-zero, because a rehearsal that skips what the publish refuses on is a different
  operation.
- **`cache prune` is new, and it is the only unnamed deletion route**
  ([RM186](ROADMAP_HISTORY.md#rm186--deletion-on-a-published-repo-by-declaration-or-by-asking-never-as-a-side-effect)).
  It names two kinds of remote file — one under `data/` that the lane's own glob excludes, and one a
  `LayoutShift` declares retired — and nothing else: `README.md`, `.gitattributes`, `release.json`,
  `LICENSE.txt` and sidecar directories are never candidates. Without `--yes` it reads, prints each
  file with its size and why it is nameable, and stops. Against the live repos it finds one candidate
  (`just-dna-seq/clinvar`'s 159 MB single-file `clinvar.parquet`, from before the per-chromosome
  split), six lanes clean, STRchive *n/a* — its snapshot is one JSON at the repo root, so there is no
  `data/` to be outside of, and "cannot look" is not "found nothing".
- **A layout change now carries its own migration** (same item). A change that retires a published
  file and introduces another declares a `LayoutShift`: *if the new spelling is absent from the repo
  and the old one is present, upload the new and delete the old.* The predicate is over the remote, so
  it fires once per repo and is a no-op afterwards, and it rides the upload's own commit as
  `delete_patterns` — the arrival and the removal are one commit, with the retired name in the commit
  message. This is the only deletion a publish performs.
- **The per-lane file globs became a registry** (same item). `cache prune` asks what a repo carries
  that its lane is not made of, which can only be asked by lane, so `SNAPSHOT_FILE_GLOBS` is now the
  one place each pattern is spelled and the `ensure_*` closures read it — the provisioner and the
  pruner cannot come to disagree about what a snapshot is. Walked by test against the publishable
  lanes.
- **Operator-visible:** one new command (`cache prune`), and a publish can now refuse where it used to
  proceed. No parquet column, model field or vocabulary member changed. Nothing was deleted from any
  published repo by this work.

## 2026-09-03 — a recompile question with no lower bound, and a registry missing one attribute

Two consumer reports from the same preview build against the uncut 0.7, both answered the day they
arrived; no schema, parquet or manifest change in either.

**`just-dna-enricher`.** [RM184](ROADMAP_HISTORY.md#rm184--cache_lanes-published-every-attribute-of-a-lane-except-the-variable-that-steers-it), from
[S89](CONSUMER_SUGGESTIONS_HISTORY.md#s89--cache_lanes-publishes-every-attribute-of-a-lane-except-the-environment-variable-that-overrides-it): **`CacheLane.env_var`** names the variable that
overrides a lane's location — the one attribute of a lane that was still a string literal inside its
resolver, so three consumers were hand-keeping fourteen names. The literals are now
`locations.<LANE>_CACHE_VAR` constants read by both the resolver and the registry, beside
`CACHE_BASE_VAR`, the shared base no lane owns; pinned on behaviour per lane and by an equality over
every `JUST_DNA_*` string the module declares. `str`, not optional — every lane has one.

**`just-dna-format`.** [RM183](ROADMAP_HISTORY.md#rm183--needs_recompile-crashed-on-the-one-input-a-registry-is-most-likely-to-hand-it-an-unstamped-compiler-version),
from [S88](CONSUMER_SUGGESTIONS_HISTORY.md#s88--needs_recompile-raises-attributeerror-on-the-one-input-it-is-most-likely-to-be-handed-a-manifest-that-stamped-no-compiler-version) — a consumer reading § 2.8 before adopting it.

- **`needs_recompile(None, current)` answers unknown instead of raising `AttributeError`.**
  `Compilation.compiler_version` is `str | None`, so a manifest stamping nothing is well-formed and a
  registry walking manifests it did not produce will meet one. `None`, `""` and whitespace now answer
  alike: every axis `None`, `complete=False`, `compiled_under=None`, `span=(None, current)`.
- **A present but unreadable stamp still raises, and the refusal quotes the whole stamp.**
  `just-dna-compiler 0.6.6 (marketplace-server)` was refused as `'(marketplace-server)'`; it is refused
  as itself now. Absent is unknown, malformed is a caller's bug — two states, not one.
- **Two fields widened**: `RecompileAnswer.compiled_under` and `span[0]` are `str | None`, `None`
  only where the call used to crash.

## 2026-09-03 — the published artifacts, audited: two lanes that could not describe themselves

**`just-dna-enricher` only, no schema change.** An audit of every artifact this project publishes to
HuggingFace — nine snapshot repos and the module repo — pulled each publishable lane into a scratch
cache and read what actually arrived. Every lane is current against its source and every published
module verifies byte-for-byte against its own manifest; what the audit found was two lanes that could
not state what they held, and one of them had been publishing a false description.

- **A ClinVar rebuild builds the citations half too, or reports failed**
  ([RM179](ROADMAP_HISTORY.md#rm179--the-clinvar-rebuild-built-one-half-of-a-two-half-artifact-and-published-its-provenance-over-the-other)).
  A ClinVar snapshot is two halves on two cadences — the VCF and `var_citations.txt` — which is why
  `build_citations` merges a `citations` block into `release.json` rather than writing its own file.
  `_rebuild_clinvar` built the VCF half only, and `release.json` is written by that half, so
  `cache rebuild clinvar --publish` uploaded a citations-free provenance over a repo whose sidecar it
  had not replaced. The publisher adds and never deletes, so the sidecar outlived its own description:
  the published snapshot carried **records from 2026-08-29 beside citations from 2026-06-27** and said
  nothing about it. Both halves now, or `built=False` with no `out_dir` — and `--publish` uploads only
  on `built is True`. **Operator-visible:** a fully offline `cache rebuild --only clinvar --source
  clinvar=<vcf>` now reports failed instead of producing that snapshot, because the citations file is a
  separate ClinVar download. The published repo still needs a citations rebuild off 2026-08-29; this
  stops the next bad publish, it does not repair the last one.
- **`cache status` names ClinVar's release instead of printing a blank**
  ([RM182](ROADMAP_HISTORY.md#rm182--cache-status-named-the-release-of-every-snapshot-except-the-one-that-moves-weekly)).
  The reporter labelled a lane with `release.json`'s `dataset`; eleven builders write it and
  `clinvar_build` writes `clinvar_file_date`, so the one lane that refreshes weekly was the only one an
  operator could not read a release off. `CacheLane` gains `release_label`, defaulting to the `dataset`
  reader, with ClinVar's set to `clinvar_dataset_label` — the function `clinvar_draft` and
  `clinical.tautology_reason` already share, so there is one spelling of the label rather than two. The
  override set is asserted as an equality over the registry. **Consumer-visible:** one more populated
  column in `cache status` output; no parquet column, model field or vocabulary member changed.

## 2026-09-03 — an overlay's reason was part of its content identity

**`just-dna-format` + `just-dna-compiler`, no parquet column, no vocabulary member, and no published
signature moves.** [RM180](ROADMAP_HISTORY.md#rm180--an-overlay-rows-provenance-was-inside-content_signature-and-rewording-a-reason-minted-a-new-content-identity), from
[S87](CONSUMER_SUGGESTIONS_HISTORY.md#s87--an-overlay-rows-reason-prose-is-inside-content_signature-and-fixing-a-typo-in-it-mints-a-new-content-identity) — a consumer building a preview against the uncut 0.7,
decided with the maintainer before the cut because the window in which it moves nothing is the release.

- **`overrides.csv`'s `reason`, `decided_by` and `decided_at` are outside `content_signature`.**
  Rewording a reason is a patch, as a README caveat is (S25); changing the value an override writes is
  still a new identity. They stay in `overrides.parquet`, `manifest.inputs`, the verification binding
  and `artifact.digest`, which all still move.
- **The mechanism is a field marker, not `exclude=True`.** `base.OUTSIDE_CONTENT_IDENTITY`, walked by
  `content_identity_exclusions`, read only by `integrity.content_signature`, so `model_dump()` stays
  complete for every writer. The stamped-column idiom was probed first and emptied `reason` in
  `draft._authored_dump` and the enricher's overlay writers — a drafted row the model then refuses.
- **Filed, not built**: [RM181](ROADMAP_0_8.md#rm181--a-byte-digest-that-moves-beside-intact-signatures-says-something-changed-and-not-what-and-provenance-has-no-shift-tracker) — a byte digest moving beside intact
  signatures says *something* changed and not what, and provenance has no shift tracker of its own.
  The maintainer's note for the 0.8 digest-coverage review.

## 2026-09-02 — a cache roster that could not be walked, and the three lanes it lost

**`just-dna-enricher` only, no schema change.** [RM176](ROADMAP_HISTORY.md#rm176--eleven-builders-three-stages-each-and-the-roster-that-was-supposed-to-name-them-was-a-list),
from the maintainer's question: do all the caches we build have a common rebuild endpoint, and does
each have download, build and upload? No — and the three gaps were one defect, a roster that was a
four-tuple list inside `cli.py` rather than something a test could walk.

- **`cache status` reported nine caches on a machine that has twelve.** `acmg_build`,
  `strchive_build` and `drug_labels_build` existed with no roster entry, and `cache pull` refused all
  three as unknown names. The roster is `caches.CACHE_LANES` now, walked against the `*_build`
  modules on disk in both directions.
- **The same three had no resolver, so the flagless path never found them.** ACMG's fell through to
  scraping NCBI's page, which serves **v3.2** while the built snapshot holds v3.3 — a correctly
  authored row reported as wrong. The other two skipped themselves with `no_reference` about a
  snapshot sitting in the cache directory. Each now resolves through
  `$JUST_DNA_ACMG_CACHE` / `$JUST_DNA_STRCHIVE_CACHE` / `$JUST_DNA_DRUG_LABELS_CACHE` or the shared
  base, and the tests assert the **call** rather than the resolver.
- **Three lanes had the licence to publish and no way to.** New: `strchive publish` (MIT),
  `clinpgx publish-labels` (CC BY-SA, its own repo because the two ClinPGx archives do not refresh in
  lockstep), and `ensure_civic_snapshot` / `ensure_strchive_snapshot` /
  `ensure_drug_labels_snapshot`. **The three repos do not exist on HuggingFace yet** — the first
  publish creates each, and until then `cache pull` says so.
- **`cache rebuild` is the one endpoint over eleven builders**, with a driver at
  `scripts/rebuild-caches.sh`. It calls the same `download_*`/`build_*` the per-lane commands call, so
  those stay and nothing forks. Its outcome is **three-valued**: ACMG needs an Elsevier workbook,
  PharmVar a personal key, CIViC a pinned release, Ensembl is built by just-dna-pipelines — all print
  as *not run* with a reason, and the exit code counts only real failures. Every lane builds into
  `<base>/<lane>/`, never in place over a live cache.
- **`publish_reference_snapshot` derives its allowlist from the plan.** The pattern list and the file
  list were two statements of one thing, which is how `citations/` and `LICENSE.txt` each went a
  release printed-in-the-dry-run and dropped-on-upload. `plan_reference_snapshot` also takes a
  `payload` filename now, because two snapshots hold no parquet at all.
- **A repo nobody has created yet is absent, not failed.** Five of the snapshot repos have never
  been published, and both provisioners were letting the transport's own error reach `cache pull`'s
  blanket handler — so the command that provisions a deployment exited 1 on a fresh machine because
  a snapshot had never been uploaded. `SnapshotNotPublished` is its own type now, printed in yellow
  and not counted; a download that *breaks* still fails and still exits 1.
- **Two credentials were not being read from the `.env`,** found by an operator asking whether the
  new endpoint handles one. `$PHARMVAR_API_KEY`: the rebuild guard read `os.environ` directly to
  decide *no key configured* versus *a key that failed*, while `PharmVarClient` loads the file before
  reading the same variable — so a key living only in a `.env` was visible to the builder and
  invisible to the guard, and the lane reported "no key" and never built. `$HF_TOKEN`:
  `upload._hf_api` called `get_token()`, which reads the real environment and the hub's own token
  file and neither is a `.env`, so a publish refused outright. Both load at the point the credential
  is read now; an exported variable still wins.
- **Absent and exported-empty are two states.** `load_env` uses `override=False`, so `export FOO=`
  is strictly stronger than `unset FOO` — an empty variable is *present* and the `.env` cannot
  replace it. Both credential refusals name which state they are in and give the matching remedy;
  the empty one says `unset`.
- **`cache prepare` is the command a deployment wants,** and the complement of `cache pull`. It
  leaves the machine with every cache it can have: pulls what is published, **builds the four that
  are not** — PharmVar, PubMind, MANE and ACMG, each unpublished for a recorded reason — so a machine
  that only pulled is no longer four caches short with the checks reading them silently skipping. The
  route is a property of the lane, never a flag. A present cache is left alone, so it is idempotent
  and cheap to re-run; a built lane is staged beside its target and moved across, never written into
  a live cache directory.
- **A Python counterpart for both loops:** `caches.prepare_caches()` and `caches.rebuild_caches()`,
  returning one outcome per lane in registry order. `PrepareOutcome.route` says **which route
  answered** — `present` / `pulled` / `built` — because a deployment auditing its caches has to tell
  a snapshot it fetched from one it made, and `release.json` names the release but not the route.
  `caches.CACHE_LANES` is the registry itself: read it instead of hard-coding which snapshots exist.
- **`cache rebuild --only acmg` needs no `--source` from a checkout.** `assets/acmg_sf_v*.xlsx`
  travels with the repository and is found by walking up from the working directory; a glob rather
  than a pinned filename, because the list is versioned and a constant would stop finding it the day
  v3.4 lands. `assets/` stays out of the wheel, so a `pip install` is unaffected and still supplies
  its own copy — the workbook is Elsevier supplementary material.
- **`cache rebuild --source lane=path` is validated up front** and expands `~`. A mistyped path used
  to reach the lane's builder as a bare `[Errno 2]`, and `acmg` is the last lane in the registry, so
  that arrived after every other lane had already downloaded.
- **Consumer-visible:** `cache status` output gains three rows and names each lane's real build
  command (it composed `f"{name} build"`, which named two commands that do not exist), and
  `cache pull`'s exit code no longer reflects an unpublished repo. No parquet column, model field or
  vocabulary member changed, and builder-only dependencies were already `[dev]`-only.
- **Every builder now writes under `data/repro/<lane>/` when the operator names nowhere, and the
  rule is derived rather than restated**
  ([RM177](ROADMAP_HISTORY.md#rm177--nine-builders-wrote-their-snapshot-beside-pyprojecttoml-because-the-rule-that-forbade-it-was-prose),
  `just-dna-enricher` only, no schema change). *"Nothing a command generates goes in the repository
  root"* has been the rule since `civic reproduce` needed its own `.gitignore` line — and it was
  prose, so **nine `--out` defaults drifted past it**: `civic`, `clinvar`, `pubmind`,
  `gnomad_constraint`, `mane`, `strchive`, `acmg_sf`, `mitomap`, `mitomap_miss`, each a bare relative
  name that dropped a snapshot directory beside `pyproject.toml`. Four more builders (`clinpgx build`,
  `clinpgx build-labels`, `cpic build`, `pharmvar build`) required `--out` with no default at all,
  which is how the docs came to tell an operator to write `--out ./clinpgx` into the root. One
  `locations.repro_out` now spells it, and an **AST walk over the CLI** asserts no `--out` default is
  written inline — so the next builder inherits the rule instead of repeating it. `cache rebuild`
  keeps `data/caches/`, named the same way. **`civic reproduce` moved** from `data/repro/civic` to
  `data/repro/civic_reproduce`, since `civic build` now takes the plain name. Callers passing `--out`
  are unaffected.
- **The `.claude/skills/create-module/` authoring skill is deleted.** It was the dogfooding
  predecessor of `just-module-creator`'s `/create-module` and stage skills, was never invoked, and
  had become a third command-surface table to keep in step with `--help`. Authoring guidance is that
  plugin's; this repository documents the format. Recover the wording from git history
  (`git show dffa03f:.claude/skills/create-module/SKILL.md`) if a rule in it turns out to have lived
  nowhere else.
- **A failed optional fetch no longer leaves a 0-byte `LICENSE.txt` in the cache, and a blank licence
  pins nothing**
  ([RM178](ROADMAP_HISTORY.md#rm178--a-failed-optional-fetch-left-a-0-byte-licence-in-every-pulled-cache-and-an-empty-licence-pins-the-empty-string),
  `just-dna-enricher` only, no schema change). `HfFileSystem.get` opens the destination for writing
  before it resolves the remote path, so `cache pull` created a phantom licence file for every snapshot
  whose repo publishes none — **four of the nine published ones** (clinvar, gnomad_constraint, cpic,
  mitomap) — and a re-pull of a repo that had dropped the file **truncated a good local copy**. Both
  verified against the live hub. The fetch now stages through `.part` like every other download in that
  function. **An empty licence file is not a smaller absence**: absence leaves `license_sha256` null and
  warns, while an empty file used to pin `sha256:e3b0c442…b855`, the hash of the empty string — so blank
  now normalizes to `None` at the sink (`SourceTerms.row`), with `read_license` answering `None` for a
  present-but-blank archive member and `clinpgx_draft` keeping its own check for the warning it owes.
  **Consumer-visible:** none — no parquet column, model field or vocabulary member changed. An existing
  cache's 0-byte `LICENSE.txt` is inert and is not deleted for you.
- **MITOMAP is two more lanes, and one of them is derived from the other two**
  ([RM171](ROADMAP_HISTORY.md#rm171--mitomaps-curated-mtdna-tables-adopted-as-the-increment-they-carry-over-clinvar),
  `just-dna-enricher` only, no schema change). `mitomap build` cuts the source's published `pg_dump`
  into a parquet snapshot — both curated mtDNA variant tables, because the repository's one mtDNA
  module draws from `rtmutation` and neither of its variants is in `mmutation` — and `mitomap miss`
  joins it against the ClinVar chrMT parquet to publish **the increment MITOMAP carries over the
  cache**, never the rows both already have. `draft-panel --source mitomap-miss` appends the rated
  half of that increment to `variants.csv` and `studies.csv`. `CacheLane` gains `parents`, empty for
  the twelve lanes that shipped yesterday, and a child whose parents are not on disk is `built=None`
  naming which — never `False`, and never an empty increment, which would be the strongest possible
  claim about a source derived from a comparison that never ran. The child pins both parents in its
  `release.json`, so a ClinVar rebuild without a child rebuild is detectable, and the drafter says so
  rather than refusing. **Nothing hardcodes a diff**: the number the item was filed about ("sixteen
  new expert-panel calls") is derived on every rebuild, and against the ClinVar of the build's own day
  it is six rather than sixteen — thirteen of the sixteen are deletions MITOMAP writes right-anchored,
  which need an rCRS base at `position-1` that Principle 2 forbids these tiers from fetching, so they
  are counted as unmintable instead. MITOMAP's confirmation token is never mapped onto `clin_sig`
  (the source states it is not an assignment of pathogenicity) and neither is its undocumented
  `[VUS*]`; the five documented ClinGen mtDNA VCEP abbreviations became keys in the one shared
  normalizer, so `normalize_clin_sig("LP")` and `normalize_clin_sig("Likely_pathogenic")` are the same
  answer. `MITOMAP_TERMS` is CC BY 3.0 written as a **floor**, with commercial and clinical use stated
  rather than inferred, so the compile gate does not fire. **A drafted row's `genotype` is a
  placeholder** — MITOMAP's `homo`/`hetero` are literature-presence flags rather than a called
  genotype — so a module drafted from this source does not compile until a human writes those cells,
  and the draft prints one worklist line per row with the flags the source did publish.
- **Consumer-visible, second half:** `draft-panel --gene` is optional under `--source mitomap-miss`
  (the increment is asked for as a whole) and still required for the other three sources; a lane name
  may be written with a hyphen anywhere one is taken (`--only mitomap-miss`, `--source mitomap-miss`)
  and the declared underscore member is what is stored. `cache status` gains two rows.

### The citations ten CIViC records carry and no dated file can reach ([RM160](ROADMAP_HISTORY.md#rm160--the-citations-ten-civic-records-carry-are-published-on-one-surface-and-it-is-the-one-nothing-read))

**All three packages.** `just-dna-format` gains two optional `studies.csv` columns; the compiler
carries them through; the enricher gains a client, a command and a check. Additive throughout — a new
optional column and a new verification-check member are both minor-legal, so this fits the uncut 0.7.0.

- **`civic citations <spec>` recovers what the builder cannot see.** RM169 widened the CIViC snapshot
  as far as a dated file goes, and the wider basis is a VCF — which needs a POS. CIViC publishes no
  GRCh37 coordinate for a variant it names as a class of event or a legacy notation, so the submitted
  evidence on those records is on the GraphQL API and nowhere else. Ten records' citations were
  unreachable; one of them is variant 1955, whose only reachable evidence for the numbering convention
  its identity turns on is EID 9969 (PMID 12202531, free full text).
- **`civic build` and `civic reproduce` are untouched.** That is the decision, not a side effect: the
  published snapshot keeps its byte-reproducibility contract and does not grow. Hashing an API capture
  as a build input was available and not taken — it keeps the *word* reproducible while changing what
  it is reproducible against. The read is **one request per variant by construction**, which is why it
  fits a command an author runs and would not fit a builder.
- **`StudyRow.confidence` / `confidence_unit`** (optional, 0.7.0): how far the citing source stands
  behind an evidence link, in **its own units, unconverted**. CIViC's `accepted` and `submitted` are
  the case — a module holding both must not render them as the same row — and there is no house grade
  for "an editor signed this off". A `confidence` with no `confidence_unit` is refused at the model,
  the way `ClinSigAuthorityCallRow` already refuses it. `studies.parquet` gains both columns; a module
  that fills neither hashes exactly as before.
- **`evidence_status_currency` joins `VALID_VERIFICATION_CHECKS`**, emitted by `enrich`. It re-asks
  CIViC about every citation the module recorded from the API and reports what has moved — a status
  accepted or rejected since the draft, or a citation added since. **Warns in both modes and escalates
  in neither**, because a source re-curating its own evidence is not an authoring error, and it is
  deliberately not `dataset_currency`: that one asks which release a table came from, this one asks
  whether a per-item judgement has moved.
- **The pin is on the `SourceRow`, at the `literature` layer.** Every drafted row records when the API
  was asked and on what basis (`dataset = civic_api:status=ALL`), rather than a timestamp in each
  `conclusion` — a moment is not a claim about a variant. `(civic, annotation)` stays the snapshot
  drafter's row: a second surface of one source may not claim the lane's slot.
- **Withholding, three ways.** Rejected evidence is not drafted (counted, never silently dropped); a
  paper whose live items disagree about their status gets its confidence withheld rather than picked;
  a non-PubMed `citationId` withholds rather than becoming a `pmid`. `--offline` records every subject
  as not-asked and writes nothing — never `ran, findings=0`.
- **Consumer-visible:** two new `studies.parquet` columns, one new `verification.checks` member, one
  new command. Nothing was removed, promoted to required, or retyped.

## 2026-09-02 — two records that contradicted themselves, and a header a draft could not write into

**`just-dna-enricher` + `just-dna-compiler`, no schema change.** Three defects, each found by a probe
that was measuring something else, plus the probe round behind RM170.

- **`release.json` declared the accepted basis while recording the wider one.** RM169 added
  `--submitted` and every derived field moved with it — `status_basis`, `status_counts`,
  `vcf_evidence`, the per-row `evidence_status` — but `notice` stayed a literal, so a snapshot built
  on the wider basis published *"every row of which is status 'accepted'"* beside
  `status_basis: accepted+submitted` and 642 submitted rows. **A consumer quoting the notice was
  quoting a false sentence.** Derived from the basis now, with the counts it read.
- **A partial draft into a header that predates a column crashed.** `append_partial_rows` re-rendered
  the existing rows against the model's **full** field list and then wrote them under the file's
  narrower header, so `csv.DictWriter` raised a bare `ValueError: dict contains fields not in
  fieldnames`. `draft-repeats` into the shipped `htt_repeat_expansion` example hit it on `pmid` and
  `measure_tiling`. The header now grows by exactly the columns the batch fills, settled before
  anything is rendered — the rule `append_rows` already had.
- **[CONTRADICTION_CORPORA](probes/CONTRADICTION_CORPORA.md)**, the RM170 probe: both corpora measured
  before either is designed against. **No refutation in CIViC that stands against a claim is
  accepted** — so that finding's subject count is 0 on the accepted basis and 3 on the wider one, and
  a hint that does not state the basis cannot be honest. Four adopted sources publish this shape,
  three already land it, and **STRchive's is dropped at parse**. Filed **RM174** out of it: a
  combination-genotype refutation reaches the parquet as two single-variant rows because the row
  builder stamps the variant's profile over the evidence item's.
- **Two probes landed, and each replaced the entry that asked for it.**
  [MITOMAP_STATUS](probes/MITOMAP_STATUS.md) (RM171): `status` is a **two-token grammar**, not 29 free
  strings — base × optional bracket covers 568 of 602 — and **both positions are documented**, the
  bracket explicitly as a **ClinGen mtDNA VCEP rating**. So mapping the bracket is a normalization, not
  a curation decision; but **120 of the 136 bracketed rows are already in the ClinVar chrMT snapshot,
  all as `reviewed_by_expert_panel`, 119 agreeing**, leaving 16 new calls. The base half must *not* be
  mapped: MITOMAP states it is not an assignment of pathogenicity. Also: the sibling `rtmutation` holds
  both variants of the repo's only mtDNA module, and `mmutation` holds neither.
  [rm170_kleene](probes/rm170_kleene.md) is RM170's design record.
- **RM174 rewritten on a phase measurement, and RM28 gains its first corpus entry.** EID 8721's own
  description reads *"heterozygous compound mutation"* — the two variants are **in trans**, and a
  haplotype is *cis*, so `HaplotypeRow` would assert the opposite of what the source observed. CIViC's
  profile grammar is boolean and counted: **209 multi-variant of 1,964 — `AND` 141, `OR` 72, `NOT` 1**,
  nested. Both of RM28's surviving arguments (economy in trans, open-world negation) appear there with
  instances. The stamp defect stays RM174's; the representation is RM28's and stays parked.
- **RM160's shape decided (unbuilt): read `SUBMITTED` at `enrich` time.** `civic build` /
  `civic reproduce` keep byte-reproducibility and the snapshot does not grow.
- **RM174's stamp half shipped: a row names the profile its evidence item actually belongs to.** A
  combination-genotype claim reaching the builder through the VCF was fanned out into one row per
  variant, each stamped with *that variant's* profile — so the parquet stated, once per variant, that
  a two-variant claim was a single-variant one. `evidence_molecular_profile_id` and
  `evidence_molecular_profile_name` now ride beside the join key on every row (the key has to stay the
  variant's own profile or the row does not join), a composite is the inequality of the two ids, and
  `release.json` carries `composite_profile_rows`. The name is null on a TSV-sourced row because that
  file publishes none. **The representation question is not touched** — 8721 is a claim about two
  variants *in trans*, `HaplotypeRow` is *cis*, and no brick holds it; that is RM28's and stays parked.
- **RM170 shipped: an authored direction beside a refutation the source published.** `Does Not
  Support` was already withheld rather than negated — but a variant CIViC *supports* and *also* rebuts
  still got a `risk` row drafted, and nothing then said the rebuttal existed. `contested_variants`
  cannot see it (a refutation enters no camp, so that counter is correctly 0 on every basis). Now
  `draft-panel --source civic` names the variants it wrote such a row for, and `enrich` folds in the
  new **`published_refutation`** check whenever a CIViC snapshot resolves, so a hand-authored module
  meets the same sign. Two finding codes — `refutation_beside_claim`, `refutation_without_claim` —
  because they are two sentences; they key the record's `detail` rather than joining the compiler's
  `VALID_WARNING_CODES`, which a compile restates as `verification_findings_recorded`. **Warns in both modes, escalates in neither, repairs nothing.**
  Consumers pinning `VerificationRecord.check` should add the member. The record names its
  `status_basis` on every run including the empty one: every such pair in CIViC rests on submitted
  content, so on the `accepted` basis the class is empty by construction.
- **RM173 closed, and RM175 opened: the PGx lane reads a retired filename.** The entry's premise was
  replaced twice in one day. First: `clinicalVariants.zip` is not a third source — **96.3% of its
  5,190 rows are already in the archive the lane reads**, and its `type` column is
  `Phenotype Category` with a different separator. Then the maintainer's investigation
  ([CLINPGX_ARCHIVES](probes/CLINPGX_ARCHIVES.md)) replaced the 13-month gap that finding ended on:
  the 15-column table was **renamed** to `summaryAnnotations.zip` when PharmGKB became ClinPGx on
  **2025-07-29**, and `clinicalAnnotations.zip` is a frozen S3 object last written 24 days before that
  post, on no downloads page, still answering 200 — **and, until the rebuild two bullets down, this
  lane's default**. So every
  `annotations.parquet` ever built here came out of the database as it stood 14 months ago.
  **RM175** is the rebuild: four member renames, one id column, no vocabulary or model change, but
  8 rows change `Level of Evidence` and every URL rehosts, so the digest moves. **A retired filename
  that still 200s is indistinguishable from a live one at the HTTP layer**, which is the durable
  lesson; and a no-JS fetch of any clinpgx.org page is the *Javascript Is Disabled!* shell, so it is
  no evidence about what the source lists.
- **RM175 shipped the same day: the PGx lane builds from `summaryAnnotations.zip` now, and refuses
  the retired archive by name.** The default URL, two member names and the id column moved
  (`summary_annotations.tsv`, `summary_ann_alleles.tsv`, `Summary Annotation ID`) with **no
  vocabulary member, no model field and no parquet column changed** — the other fourteen columns and
  `Phenotype Category`'s values are identical. **The guard is the item**: an archive carrying the old
  member names parses perfectly and yields a plausible fourteen-month-old parquet, so the builder
  reads the member names first and refuses the retired spelling with the rename, its date and the URL
  to use instead; a third arm answers for an archive that is neither. Both spellings live in one table
  the reader takes its names from, and the retired one is returned by nothing, so no path through the
  module can read a 2025 archive. **The data moved and the digest with it**: 16,087 → 16,117 snapshot
  rows over 5,190 annotations, 22 (annotation, genotype) keys gone and 52 new, 30 rows changing
  `evidence_level`, 120 `drugs`, and every shared row rehosting its `URL` — so a module drafted from
  this lane can see an evidence level move under it, which is the check working. The builder
  docstring's *"4,618 of 5,113"* is gone from all five live files, restated as a relationship rather
  than swapped for a fresh count. **Left unbuilt on purpose**: the three currency canaries the entry
  listed, each of which is its own design — nothing here would notice `summaryAnnotations.zip` itself
  going quiet.
- **MITOMAP's terms are read (RM171): CC BY 3.0**, commercial use and redistribution permitted,
  attribution required. Read from a Wayback capture because the live page is behind a Cloudflare
  interstitial; the CC BY-NC a search surfaces is the *article's* licence, not the database's.

## 2026-09-01 — the source-adoption round closes: regulator drug labels (RM166)

**`just-dna-enricher`, plus one `VALID_VERIFICATION_CHECKS` member.** Last of the five items
[PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided, and with it **the whole 2026-09-01
source-adoption round has landed inside the uncut 0.7.0**: RM163, RM165, RM166, RM167 and RM168 built;
RM164 parked on a measured negative, spinning off RM171.

- **A `drugLabels.zip` builder beside `clinpgx_build`** — same cache, same payload-read `LICENSE.txt`,
  and **its own `release.json`** from its own `CREATED_*.txt`. ClinPGx's archives do not refresh in
  lockstep; `relationships.zip` was once a year newer than `clinicalAnnotations.zip`.
- **A regulator-label cross-check joining at two tiers.** Star-allele where the file supplies one,
  gene otherwise, and **the tier is part of the finding** — a gene-level agreement and an allele-level
  agreement are different claims and a consumer must be able to tell them apart.
- **It is five regulators**: FDA, Health Canada, EMA, Swissmedic, PMDA. The surface is named for the
  labels rather than for any agency, so adding a sixth is data rather than a rename.
- **A blank `Testing Level` is `unknown` and withholds** — about a third of the file states none, and
  reading that as `No Clinical PGx` would manufacture a negative regulatory claim.
- **New verification check `regulator_label_agreement`.** Consumers pinning `VerificationRecord.check`
  should add it; it warns in both modes and never escalates under `--strict`.
- **What did not ship, and closed instead:** the PGx lane gains no member outside its licence class by
  this route. ClinPGx is the same CC BY-SA + no-sale gate, and the FDA's own association table is 126
  rows of HTML with no stated terms. Diversifying that lane needs its own item, choosing candidates
  for their terms first.
- Noticed and filed rather than built: ClinPGx publishes at least twelve archives and this tier reads
  two of them.

## 2026-09-01 — the source-adoption round: literature coverage, and the tier that answered (RM167)

**`just-dna-enricher`, plus one `VALID_VERIFICATION_CHECKS` member. Writes no authored row at all.**
Fourth of the five items [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided.

- **`just-dna-enricher litvar coverage` asks LitVar2 which papers name a module's alleles**, and
  records **which tier could answer**: allele-resolved, position-only, absent, or `unchecked`. The
  distinction is the point — APOE rs429358's position node carries 3,945 papers and its allele node
  328, so an answer that did not name its tier would understate that locus twelvefold.
- **It writes no row.** A PMID list per variant is not a table kind, so the pass reports and attests
  and changes nothing in the spec directory. That was the entry's pre-authorised outcome.
- **New verification check `literature_coverage`.** Consumers pinning `VerificationRecord.check`
  should add it.
- **The bound ships with it, in the lane's own documentation**: LitVar answers *which papers discuss
  an already-identified allele*, and does not answer *which allele a name meant*. Measured against the
  two CIViC legacy insertions, it returns no node for any of their four candidate alleles.
- **`clingen_allele.AlleleIdentity.unanchored` is now populated on a `resolved` result too.** It was
  computed and then discarded whenever the registry also served an rs-number, so a caller wanting the
  allele rather than an identity got nothing — every PALB2 indel read as incomparable. A consumer
  reading `unanchored` only under `outcome == "needs_anchor"` is unaffected.
- Terms: NCBI publishes a policy rather than a licence, so every gating axis is `None`. A module
  carrying LitVar-derived findings records unknown terms rather than permissive ones.

## 2026-09-01 — the source-adoption round: STRchive, checked and drafted by column (RM165)

**`just-dna-enricher`, plus one `VALID_VERIFICATION_CHECKS` member. No authored column, no parquet
change, `just-dna-compiler` untouched.** Third of the five items
[PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided.

- **`repeat_alleles.csv` gains a source, split by column.** `just-dna-enricher check-repeat-bands`
  compares an authored band table against STRchive's and reports; `just-dna-enricher draft-repeats`
  drafts the identity half. New `STRCHIVE_TERMS` (MIT — the first candidate in this round with terms
  that are both established and permissive) and a `strchive` snapshot builder.
- **The bands are checked and never drafted, for a measured reason.** STRchive reproduces
  `htt_repeat_expansion`'s first two bands exactly, and gives FMR1 one `45–200` band where the module
  has `45–54` and `55–200` — losing 55, the premutation threshold. The finding names the missing
  boundary rather than reporting that two tables differ.
- **`pathogenic_max` is never written as `measure_max`.** A catalogue maximum is an observation, not a
  clinical bound; imported as one, an allele above it would match no bin at all and nothing would say
  so. It is reported as its own finding kind.
- **New verification check `repeat_band_agreement`.** Consumers pinning `VerificationRecord.check`
  should add it. It warns in both modes and never escalates under `--strict`.
- **The drafting provider writes no band column at any severity**, and a drafted row is gene, motif,
  trait and a placeholder conclusion — `RepeatAlleleRow` has no column for the coordinates,
  `locus_structure` or `ref_copies` the catalogue also publishes. That gap is RM65/RM87.
- Known and not fixed here: `just_dna_compiler.draft.append_partial_rows` crashes on any table whose
  header is narrower than its model, which reaches all four existing partial-row providers. Found
  while drafting into a real module, reproduced independently, filed rather than patched — this round
  changes nothing in `just-dna-compiler`.

## 2026-09-01 — the source-adoption round: the PGS Catalog becomes a registry (RM163)

**`just-dna-enricher`, plus two `VALID_VERIFICATION_CHECKS` members in `just-dna-format`. No authored
column, no parquet change, `just-dna-compiler` untouched.** Second of the five items
[PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided.

- **`check-identifiers` asks a fourth registry.** `pgs_id` was the one authored identifier in the
  format nothing checked, on the column `PgsRow` is keyed by. New `pgs.py` client; the roster derives
  from `DRAFTABLE` the same way the other three do.
- **The verdict is read off the response body, never the HTTP status.** The Catalog answers `200` with
  `{}` for a never-assigned accession *and* for a malformed one, so the status carries no existence
  information. A consumer relying on `raise_for_status` to mean "this id is real" would be wrong.
- **The absence message names the typo reading first.** Only about a third of the accession range is
  assigned, so an unrecognised id is overwhelmingly never-assigned rather than withdrawn — the
  opposite weighting to the dbSNP message, and stated for the measured reason.
- **Two new verification checks**, `pgs_accession_currency` and `pgs_metadata_agreement`. Consumers
  validating `VerificationRecord.check` against a pinned vocabulary should add both.
- **`PGS_TERMS` is a floor, not the terms.** Each score record carries its own `license`, and the
  values are not variations on one licence: most generic, some academic-research-use-only, some CC0.
  The per-score string overrides the constant in that score's `SourceRow`. **A module naming an
  academic-use-only score is now refused by the compile gate by name** — if you have such a module, it
  will stop compiling under a commercial `declared_use`, and that refusal is correct.
- **Drift is checked over `training_ancestry` and `training_cohort` only.** `match_rate_floor` and
  `research_tier` are author judgements the Catalog does not publish, so there is nothing to compare
  them against.
- **Currency comes from `/rest/info`**, added as `currency.default_probes`' second member, so
  `--verify-datasets` now covers this source.
- Known gap, recorded rather than fixed: a `pgs.csv` drift finding **cannot** be answered in
  `overrides.csv` — the overlay applies to derived tables and `pgs.csv` is authored.

## 2026-09-01 — the source-adoption round: MANE becomes a cache (RM168)

**`just-dna-enricher` only; no schema change, no new authored column, nothing in `just-dna-compiler`.**
First of the five items [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided, all landing inside
the uncut 0.7.0.

- **`just-dna-enricher mane build` — MANE is a source now, not a sentence in a probe document.**
  `CIVIC_IDENTITY_PROTOCOL` § 3b pinned a numbering frame with a file "downloaded once and cited";
  it is now a cache with a location, a recorded release and a currency check, like every other
  reference table here. New: `MANE_TERMS`, `$JUST_DNA_MANE_CACHE` / `default_mane_cache_dir` /
  `resolve_mane_reference`, `mane_build.py`, a `mane` sub-app, a `cache status` row.
- **Three files, under 1.2 MB together.** The summary (19,437 rows), `changed_select_accessions` (120
  rows) and `protein_coding_genes_not_in_mane` (222 genes). The second is the currency check and ships
  in the same pass deliberately — a cache without the thing that notices it going stale is the defect
  the item was about.
- **`release.json` is copied from the source's own `README_versions.txt`**, so it carries the MANE
  version, the NCBI RefSeq annotation release *and* the Ensembl release — two of which appear in no
  filename.
- **`MANE_status` is a column and is never collapsed.** 74 of 19,437 rows are MANE Plus Clinical, and
  CDKN2A carries two rows with different CDS numbering. A consumer reading one row per gene would not
  see it.
- **`Update_Affects_CDS` is carried as a tri-state.** Yes on 74 of the 120 changed accessions: a MANE
  Select change that moves the CDS moves every `c.` and `p.` derived in that frame.
- **The negative roster keeps its reasons.** 222 genes over a seven-member vocabulary derived from the
  file, so "MANE has no answer for this gene" is distinguishable from "nobody asked" — and
  `pending MANE review` is neither.
- **Terms are `None`, not permissive.** NCBI publishes a policy rather than a licence, so every gating
  axis is unknown; there is no `--use` flag, because a gate whose every answer is a skip is a flag that
  does nothing. Only NCBI's side was read — nothing is asserted about EMBL-EBI's terms for the same
  tables.
- **Scope is a transcript-identity aid, not HGVS generation**, and the lane documents its own bound:
  MANE is the default, not the answer. It makes CDKN2A's problem visible and is silent on RUNX1's.
- Two `--help`-parsing tests that had been failing every PR run since 2026-08-30 are fixed: Typer
  renders through Rich, CI sets `FORCE_COLOR`, and a coloured flag is not one token.

## 2026-09-01 — CIViC: the identity in a variant's name, and the basis in its own VCF (RM159, RM169)

**`just-dna-enricher` only; no schema change, no new column, nothing in `just-dna-format` or
`just-dna-compiler`.**

- **`civic build` places 33 variants it used to drop.** CIViC states an identity in a variant's `name`
  for records whose identifier columns are empty — `N150fs (c.448delA)`, `IVS2+1G>A`, `D1709N` — and
  those identities now ship as `civic_identities.CIVIC_NAME_IDENTITIES` and are emitted with
  `identity_derivation="curated_name"`. Coverage over the dated `01-Aug-2026` release goes from
  **237/290 variants (81.7%) to 270/290 (93.1%)** and from 474/533 rows to **507/533**;
  `unresolvable_identity` falls from 59 rows to 26.
- **`identity_derivation` gains the member `curated_name`.** Additive, and deliberately not folded
  into `rsid`/`grch38_hgvs`: those mean "the source stated this in the column for it". A consumer
  filtering on the vocabulary should add the member; one that ignores it sees the rows as ordinary
  placed rows, which they are.
- **`release.json` gains `curated_identities`** — `applied` / `superseded` / `renamed` / `absent`,
  every member present, summing to the table. `superseded` means CIViC has since published an identity
  of its own and the curated row stood down; it is also a free currency signal.
- **`civic reproduce` now reads 57 coordinates against the GRCh38 reference instead of 24**, still
  0 mismatches. Every hand-read allele is confirmed at its stated position by an unrelated service.
- Unchanged: the build is still offline and byte-reproducible from the dated TSV pair, and
  `allele_registry_id` is still CIViC's verbatim cell — the CAIDs the resolutions went through are
  provenance on the shipped table, not the source's statement.
- The procedure behind the identities is `docs/probes/CIVIC_IDENTITY_PROTOCOL.md`; the per-variant
  evidence and the classes that did **not** resolve are `docs/probes/CIVIC_UNRESOLVED.md`.

**RM169 — `civic build --submitted` and `civic reproduce --submitted`.**

- **The unreviewed majority is now readable from the dated release.** CIViC publishes
  `<date>-civic_accepted_and_submitted.vcf` beside the three TSVs, so no API read and no
  reproducibility bargain are needed — RM160 was filed believing otherwise. Opt-in:
  **507 rows on 270 variants → 1,149 on 397**, rebuild still byte-identical, refget cross-check
  **57 → 129 coordinates with 0 mismatches**.
- **New parquet column `evidence_status`** — `accepted` / `submitted`, CIViC's own word, unconverted.
  Present on every row; on the accepted basis it is uniformly `accepted`.
- **`identity_derivation` gains `vcf_csq`.** `VariantSummaries.tsv` is accepted-only as well, so 112
  of the 127 new variants have no row in it; their identity comes from the VCF's `CSQ` block through
  the same parsers and the same published identifiers. The member names the *file*, not the route.
  A consumer filtering on the vocabulary should add it.
- **`release.json` gains `status_basis`, `status_counts`, `vcf_evidence` and `unjoinable_submitted`.**
  `status_basis` is the field to read before comparing any count here with a count from anywhere else.
- Unchanged: the TSV pair is still primary (the VCF cannot carry a variant with no GRCh37 position,
  which is exactly the class RM159 resolved by name), and nothing is placed from the VCF's own GRCh37
  coordinate.

## 2026-08-28 — 0.7.0: the items PROPOSAL_0_7 decided

**A MINOR, being built; the number is decided and not yet cut.** Every item in this batch is additive
under Principles 3 and 8, and a new optional column is what sizes a release. The heading names `0.7.0`
because the proposal decided it per item, so unlike the 2026-08-24 batch below — which is also an
uncut minor and deliberately names no number — there is a version to write down here. The three
`pyproject.toml` files were bumped to `0.7.0` on 2026-08-31 and **the tag is not cut**, so work still
lands inside this number; the 2026-08-24 batch ships inside it too. Each entry below names the
packages it actually touched.

**The twelve entries dated 2026-08-31 are a batch of their own and are worth reading as one.** They are
the roadmap items that stood open against this release — RM103, RM108, RM110, RM117, RM136, RM137 and
RM138 — plus RM146 and RM150 from the same day's consumer reports, and RM151, which was filed and
built the same day as RM117's other half, and RM152, a consumer measurement that arrived carrying
no release class and acquired one when its probe was finally run, and RM154, which arrived from a
consumer report after the rest were built; all taken in one pass so 0.7 cuts with its own backlog
cleared rather than carrying it. Eleven are built; **RM138 is closed with its numbers measured and no
code changed**. **The items dated 2026-09-01 are deliberately outside that count** — RM155 arrived
from a consumer the next morning, RM156, RM157 and RM158 from sweeping its shape across the
tier, and RM161 from the pre-build gate run those four preceded; all five ship inside the same uncut
0.7.0. The batch stays the thing it describes rather than growing a member
whenever another item lands before the tag: the count is of the 2026-08-31 round, and the rule for a
later item is to date it and leave the number alone. Two things a reader should take from them together: `carried` costs
1.06× gzipped rather than the 1.84× raw the item was filed about, so **serve manifests compressed**;
and two derived values change — `gene_metrics.constraint_flags` and
`gene_validity.classifications` — which are **corrections**, so a moved signature there is the fix
arriving rather than drift.

- **RM161 — a release record's two halves are written at different times, and the second left the
  first behind.** *(`just-dna-format`; **additive** — two names into an existing list and one new test.
  No column, no vocabulary member, no signature moves.)* The pre-build gate run for this cut exited
  **1**: `gene_validity.superseded_count` and `identity.version_coerced_from` *"moved and the release
  record does not list it"*. Both are real manifest additions from the 2026-08-31 batch, both carry a
  `DeclaredChange` written the day they landed, and neither had reached `manifest_fields` — the two
  declarations went in at 06:52 and 07:04, after the measurement the list came from, and the readiness
  table recorded the gate green earlier that day. **The shape is the record's own construction**:
  `SweepMeasurement.as_record` produces the measured half with `declared` deliberately empty, which is
  exactly what makes the gate useful and also what lets a later item add its declaration and leave the
  measured list behind. Nothing in a checkout could notice — the gate needs the previous release
  installed and is a release-sequence command by design. The guard is an **asymmetry**: a declared
  *addition* must be listed, because a field that did not exist before moves wherever its block
  appears; a declared *correction* may be unmeasurable on the corpus, so `gene_validity.classifications`
  and `gene_metrics.signature` stay declared and unlisted and the gate keeps its existing *note* for
  the reverse. The record's `evidence` sentence already carried the current numbers, so only the field
  list was stale. After the fix: *"release record for 0.7.0 covers the measurement"*, exit 0. *(from
  the 0.7.0 pre-build gates)*

- **RM158 — the GWAS pass asked about one table's rsIDs, and the answer already existed in this
  package.** *(`just-dna-enricher`; **additive**, and **no schema change** — no column, no vocabulary
  member, no signature moves.)* `gwas._module_subjects` built its `(rsid, variant_key)` list from
  `variants.csv` while five authored models carry `rsid`, so a module whose rsIDs live in
  `haplotypes.csv` or `pharm_variants.csv` got no associations and no line saying none had been asked
  for — a spec carrying one `haplotypes.csv` row for CYP2C19\*2, which the Catalog has associations
  for, returned `[]` against the pre-fix code. **The third instance in one sweep, and the one worth
  reading**: the fix was already written. `enrich.Subject` and its collector exist for exactly this
  question — resolution read `variants.csv` alone until RM43, when a PGx module *"which by design
  carries no `variants.csv`"* enriched to an empty `resolution.csv` — and this pass, written
  afterwards, restated the narrow loop instead of calling it. So grep for the **question**, not for
  the bug. `_collect_subjects`/`_Subject` are now public (`collect_subjects`/`Subject`), since a
  private name is what kept the second caller from finding the first. `studies.csv` carries `rsid` and
  is deliberately not a subject: a study row references the variant it grounds, which the module
  already carries. Measured across the corpus before and after — `pathogenic_clinvar` 301,
  `hboc_palb2` 16, `mt_heteroplasmy` 2, `grch37_build` 0, identical lists — because `variants.csv`
  goes first in the collector and first occurrence wins, the precedence that stops a PGx row taking an
  identity a SNP row minted. *(from the RM155 sweep)*

- **RM157 — the gene set three passes take their scope from read one table while nine carry the
  column.** *(`just-dna-enricher`; **additive**, and **no schema change** — no column, no vocabulary
  member, no signature moves, and no ordering change, since `gene_metrics` sorts its rows by
  `(gene, dataset)` before writing.)* `gene_metrics.module_genes` built its list from `variants.csv`
  alone. It is not a report but the **scope** of the constraint-metrics pass, the gene-validity pass
  and the ClinGen dosage pass — all three call it — so a module whose genes live in its PGx tables had
  all three quietly do nothing: no rows, no findings, and no line saying a question had not been put.
  **Measured on this repo's own corpus**, where `cyp2c19_star_alleles`, `apoe_epsilon`,
  `cyp2c9_warfarin_grch37` and `hfe_compound_het` returned `[]` while naming CYP2C19, APOE, CYP2C9,
  VKORC1, CYP4F2 and HFE. Two things worth reading together: the workspace already held **two answers
  to one question**, since `pgx._module_genes` reads two PGx tables and nobody had put them side by
  side; and RM104 had patched the *symptom* — an `UnboundLocalError` on "any module with no
  `variants.csv`" — with that sentence sitting in a comment, describing the defect as a shape rather
  than asking why the list was empty. The set is now derived from the same registry walk the
  identifier roster uses, and a table that will not parse **refuses** here rather than being routed to
  `not_read`: a reporting surface may narrow, a scope may not. `IdentifierRoster` gained `read_errors`
  so the loader's own message survives into that refusal and `gene_validity`'s `variants.csv is
  invalid` diagnosis is unchanged. `pgx._GENE_TABLES` stays two tables — it decides whether the
  star-allele cross-check *applies*, which is a fact about that check's inputs. *(from the RM155
  sweep)*

- **RM156 — the roster RM155 widened was gated behind the one table it had stopped depending on.**
  *(`just-dna-enricher`; **additive**, and **no schema change** — no column, no vocabulary member, no
  signature moves. What moves is which modules the check runs on at all.)* Two gates in front of the
  widened roster were still keyed on `variants.csv`: `check_identifiers(spec_dir=)` loaded that table
  unconditionally and raised `variants.csv is invalid: ... not found`, and `check-identifiers`
  returned *"no variants.csv — nothing to check"* one call earlier and hid it. The table has never
  been mandatory, and **four of the nine tables carrying `gene` are the PGx kinds a module is built
  entirely out of** — reproduced on this repo's own corpus, where `cyp2c19_star_alleles`,
  `apoe_epsilon`, `cyp2c9_warfarin_grch37` and `hfe_compound_het` carry no `variants.csv`, name
  CYP2C19/APOE/CYP2C9/VKORC1/CYP4F2/HFE between them, and all four exited 0 having asked nothing.
  **S86's unreadable `0`, one level above the function that repaired it.** The command's guard is now
  the **roster** — nothing to check means no id-bearing table was read, and only then is no
  attestation written, which is the half of the old guard that was right; an absent `variants.csv` is
  no rows, a present-and-unparseable one still raises. **A third vacuous pass beneath them**: with
  symbols in hand and no rows, `_gene_locus_conflicts` returned `compared=0` with `None` beside it,
  the `ran(0, 0)` its own attestation docstring forbids. *(from the RM155 sweep)*

- **RM162 — `RM_TOC.md` is an index, and an index is not an allocator.** *(tooling only —
  `.claude/rm-next.py` plus its test; **no package, no schema change**, nothing a consumer installs.)*
  The `Sn` loop has allocated ids since it was built, because an id written into a document collides
  when it is stale. `RMn` had no allocator: the number was read by grepping *"the highest in use"*, and
  the window between that read and writing the entry is where a second session reads. **Reproduced by
  this repo on itself** — on 2026-09-01 two sessions sharing one working tree filed different work as
  **RM159** a minute apart, and `741ec59` renumbered one to RM161. The new tool scans every
  `docs/**/*.md` and **reserves** the next number in the same locked write; a tool that only *printed*
  the number would be the same defect with a nicer interface. **The lock is on `docs/`, never on
  `RM_TOC.md`**: a leftover lockfile would block every later run (`@flock-not-a-lockfile`), and — the
  half that was measured rather than assumed — `flock` binds an **inode**, so an atomic rename-over
  leaves the holder locking an unlinked file while a second process acquires immediately. A reservation
  is a visible `🔷` row in the index rather than a side-car it cannot see, and `--release` leaves a `✖`
  tombstone because **ids are never reused** — the first cut deleted the row, the number went invisible
  to the scan, and a released RM10 was handed straight back out. Pinned by a test that runs eight
  allocators at once **and runs the same eight with `flock` neutered to watch them collide** (5 distinct
  of 8, one number taken three times). The loop's Step 5 bullet, which told an agent to read the number
  off the index and named a highest that had been stale for 114 items, is corrected. *(the 2026-09-01
  collision)*

- **RM155 — the identifier roster read one table while eleven carry the column, and reported its
  blindness as a clean zero.** *(`just-dna-enricher`; **additive**, and **no schema change** — no
  column, no vocabulary member, no signature moves; the new report fields default to empty, so an
  existing caller reads unchanged.)* `check_identifiers` built its trait and gene rosters from
  `variants.csv` alone while **eleven** authored models declare `trait_efo_id` or `gene` — `StudyRow`
  has carried the trait column since 0.3 — so a 67-variant module carrying its trait id on all 68
  `studies.csv` rows reported nothing checked and nothing flagged, and could ship a retired CURIE with
  every gate green. **The unreadable `0` was the defect rather than the omission**: it asserted *this
  module declares no trait* and *its traits are in a table nobody read* in one breath, which is
  `@unreachable-not-absent` at a finer grain, so widening the roster alone would have left the hole —
  a wide roster still returns `[]` for a module that genuinely declares none. Both halves shipped: the
  roster is **derived from `DRAFTABLE`** (nine tables per column, asserted as an equality over the
  walked `_ALL_MODELS` rather than listed, so a kind added later joins by existing), and
  `IdentifierReport` gained `trait_tables_read`/`trait_tables_not_read` plus the gene pair, with the
  CLI count naming its own denominator. `MeasureBinRow` is correctly absent — the abstract base whose
  four concrete subclasses are each their own entry — and the three **derived** models carrying these
  columns are excluded on purpose, since a stale id in a machine-written row is the *source's*
  currency and no author can act on it. **A third instance one level up**, found by the same framing:
  `report.clean` is `all()` over a possibly-empty set, so `check-identifiers` printed a green *"all
  identifiers current"* having asked nothing at all. An absent optional table and one that exists and
  will not parse are kept apart; only the second warns. *(S86)*

- **RM154 — an rsID the source HAS was published as an absence, and the warning explaining it was
  false.** *(all three packages; **additive**, and **no schema change of any kind** — no column, no
  vocabulary member, no signature moves, and every existing module recompiles byte-identically.)*
  `enrich` writes `status: not_found` — *this source has no record of your rsID* — when the source
  answered and the **allele-aware filter rejected every locus**. Reported over five subjects of a
  64-variant longevity module authored from a GRCh37/hg19 supplementary: the paper spells the submitted
  strand, so its `G/A` meets GRCh38's `C/T`, and Ensembl returns all five immediately. Reproduced
  offline against the real path — a snapshot that has the rsID with complemented alleles and one that
  genuinely lacks it write **byte-identical rows**. This is the fourth state in the family RM98 built
  (`unreachable_rsids` = the request failed, `unconsulted_rsids` = nobody looked, `unresolved` = no
  position and silent about why): here the asking **succeeded** and the answer did not match. New
  `EnrichmentResult.allele_mismatches`, carrying `AlleleMismatch(rsid, genotype, loci, offered,
  strand_flip)`, plus one aggregated warning in both modes saying the source *has* them. **The row is
  deliberately unchanged**: a new `VALID_RESOLUTION_STATUS` member is a wire change, and *deleting* the
  row moves `resolution_signature` (`variant_key`/`rsid` are fact fields, `status` is not — measured,
  not reasoned), so what moved is the reason rather than the row. **Second defect, in the sentence the
  reporter quoted**: `hosting_verdict`'s two `False` arms shared one explanation, so a strand-flipped
  SNV was diagnosed as *"The event sizes differ, which re-anchoring cannot change"* about two 1 bp
  substitutions — `compiler.resolution.contradiction_reason` is now `undecided_reason`'s twin on the
  `False` side, with a test asserting the arms' reasons stay pairwise distinct. `strand_flip_explains`
  and `reverse_complement` land in **format** (pure string work, and the compiler's twin site needs
  them); both withhold rather than guess — a degenerate code cannot be complemented, and a palindromic
  SNV that already fits is never reported as a flip. *(S85)*

- **RM153 — the identity CIViC does not publish, recovered through a registry rather than by lifting a coordinate.**
  *(`just-dna-enricher`; **additive**, **no schema change** — one client, one snapshot derivation, three
  withhold reasons, one licence row.)* RM152's residue. CIViC publishes GRCh37 coordinates or none, and
  after every published identifier is read some variants still have no route to a GRCh38 identity. Two
  questions, answered in opposite directions.
  **Taken: the ClinGen Allele Registry.** A CAID is build-independent; the registry serves an
  rs-number *and* a GRCh38 coordinate, needs no key, and answered 102 probe requests with zero
  failures. Recovery over the direction set goes from **138/290 (48%) to 237/290 (82%)** — 52 via an
  rs-number, 12 via a coordinate, and **35 one-sided indels anchored**. The rs-number is preferred
  because ClinGen supplies it and *Ensembl* verifies it: two authorities, so the check is real, which
  is precisely what a lifted coordinate lacks. New `identity_derivation="caid"` keeps a route-bearing
  row in the snapshot instead of dropping it; `unresolvable_identity` now means no identifier at all
  and falls from 204 rows to 59. The pass runs at **draft** time — a build that fetched would forfeit
  the offline reproducibility the dated input exists to give — and `--offline` withholds those rows as
  `caid_unresolved`: **unplaced, never unplaceable**.
  **One-sided indels are anchored VCF/Picard-style.** The registry states an insertion with an empty
  `referenceAllele` and a deletion with an empty `allele`, in interbase terms; neither is a row a
  `ref`/`alts` pair can hold. Prefixing both sides with the reference base before the event is the
  left-aligned form VCF requires, and the interbase `start` *is* that anchor for both shapes, so one
  rule covers them. All 35 rows that previously read `no_identity` are one-sided indels and every one
  anchors. Verified twice: the base at `chr3:10142013` is `G`, and ClinGen's own HGVS is
  `g.10142013dup`, which is exactly the `G>GG` produced. An unreadable anchor is withheld under its
  own reason, never guessed.
  **Refused: liftover.** Reopened on request and closed on the number — ceiling 13 evidence rows on 9
  variants, honest recovery **at most one**. Three are gene-level assertions no genotype satisfies on
  any build; five are imprecise by the source's own HGVS and the registry refuses to parse them at
  all; and variant 2099 lifts *exactly* to **a different allele** than its own name and alias
  describe, which is RM48's hazard demonstrated rather than argued. `pyliftover` agrees with Ensembl
  on all 18 endpoints so buys no accuracy and downloads an unpinned chain; Picard `LiftoverVcf` was
  not run because 8 of the 9 carry no REF/ALT to feed it.
  **The registry's terms are unestablished** and recorded as such: `reg.clinicalgenome.org/site/terms`
  answers 200 with a generic broken-link page, so every axis is `None`. ClinGen's CC0 grant covers the
  gene-curation surface, not this one. Nothing is redistributed.
  Measurements in [CIVIC_SURVEY.md](probes/CIVIC_SURVEY.md) and
  [CIVIC_UNRESOLVED.md](probes/CIVIC_UNRESOLVED.md).

- **RM152 — CIViC adopted on the axis it can answer, and refused on the one it was proposed for.**
  *(`just-dna-enricher`; **additive**, and there is **no schema change of any kind** — no column, no
  table, no vocabulary member. The adoption rides on `direction` and `state`, which have existed since
  0.3, which is why it lands inside an uncut release without sizing it.)* S84 proposed CIViC as a
  second `clin_sig` concordance authority; measured, its germline subset carries five ACMG-tier calls
  and **zero benign-class**, so `discordant` is unsayable and the check would read `single` or
  `concordant` by construction. The same measurement found 1,458 germline rows on
  `Predisposition`/`Protectiveness` — the **`direction`** axis — where the `NA` count is 0. So the
  drafter that was rejected for "rows with an empty significance column" is right on `direction` and
  wrong only on `clin_sig` (812 `NA`), and that is what shipped.
  **New `civic build`**: a dated release (`--release 01-Aug-2026`) reduced to one parquet plus
  `release.json`, byte-reproducible. It reads the **bulk TSVs, not the GraphQL API**, because only the
  download side is dated — and that surfaces a fact neither surface declares: the TSV is
  `accepted`-only at 4,903 rows while the API defaults to `NON_REJECTED` at 11,518, so **a count from
  one is not comparable with a count from the other**. Three inputs are required, because
  `MolecularProfileSummaries.tsv` is what tells a combination genotype from a dangling reference.
  **New `draft-panel --source civic`**, writing `direction` and never `clin_sig`; `--clin-sig` is
  reported inert rather than silently ignored. **New `CIVIC_TERMS`** (CC0 1.0), distinctive not for
  permitting redistribution — five sources here do — but for asking nothing back.
  **A `direction`-axis concordance record was refused**, which was RM152's open question: genuine
  risk-versus-protective opposition is **0** at every scope and status basis, the three contested
  variants are claim-against-refutation and dissolve under `ACCEPTED`, and **nothing else in the
  enricher fills `direction`**, so there is no second authority to be concordant with.
  **Coordinates are GRCh37 or absent, never GRCh38**, and the snapshot survives that by reading the
  rsID and GRCh38 accession CIViC publishes beside them rather than lifting anything — RM48's rule
  applied, and better than it hoped, since a published rs-number is an independent value resolution
  can cross-examine. The residue is RM153. **A refutation is kept with its direction withheld**:
  "does not support predisposition" removes a claim without establishing its opposite.
  **One fix in shared code, found by dogfooding rather than review** — `append_partial_rows` built its
  covered-set from `partials[0].match_on` while comparing each row against its own, so a mixed-arity
  batch re-added rows on **every lap**: invisible on a first run, a file that grows thereafter.
  Providers now pass one constant tuple and a mixed batch is refused.
  Measurements in [CIVIC_SURVEY.md](probes/CIVIC_SURVEY.md); the decision is the RM152 addendum in
  [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md).

- **RM146 — every authored column now says which release it appeared in.**
  *(`just-dna-format`; **additive** — a marker on each field declaration. No column, no parquet, no
  signature, no manifest field.)* A module authored on 0.6.6 met a registry running 0.6.1 and got
  `studies.csv line 2 [curator]: Extra inputs are not permitted` — byte-identical to what a typo
  (`[curatr]`) produces, and the two want opposite actions from an author: upgrade the reader, or fix
  the cell. pydantic's message under `extra="forbid"` could not carry the distinction, because the
  information was not in the model.

  **New: `just_dna_format.base.since("0.6.5")` on every authored field, read with
  `base.field_first_seen(model)`** — a plain `{field: release}` map, so any tool rendering our findings
  can answer *when did this column appear* offline. It composes with `vocabulary()` in one
  `json_schema_extra` dict rather than replacing it. `stamped_identity_field` now takes `first_seen`
  as a **required** argument: a compiler-stamped column is still one an older reader refuses.

  **The backfill was measured, not recalled** — parsed per release tag from the AST rather than
  imported, since old code need not import under a current Python. 414 fields across 31 models: 115
  date to 0.2.0, 81 to 0.4.0, 150 to 0.5.0, 160 to 0.6.0, 3 to 0.6.5, and 78 land in 0.7.0. The answer
  is per **(model, field)**, never per name: `curator` is on `VariantRow` from 0.2.0 and gains its
  `StudyRow` twin only in 0.6.5.

- **RM117 — an answered conflict the archive has since resolved says so, instead of reading as a typo.**
  *(`just-dna-format` + `just-dna-compiler`; **one new warning code**, no field and no signature moves.)*
  `clin_sig_concordance.csv` holds contested subjects only and is rewritten whole, so a subject leaving
  the record means the authorities stopped disagreeing — which is how an author learns the archive
  caught up with them. An `overrides.csv` row answering that conflict then reaches nothing, and until
  now it drew the generic *the subject may be mistyped, or the correction may be aimed at a row the
  compiler drops*, put to an author whose judgement had just been confirmed.

  **New: `overlay_answer_vindicated`** (actionable — the author can retire the overlay row, and nobody
  else can). It is an observation about the record and not a verdict: the authorities now agree and the
  row is unnecessary; who was right about the biology is not something a compiler can say. Scoped to
  that one table, because every other unmatched update is ambiguous and takes RM137's split.

  This is RM117's observability half. The **severity** half stays closed, and the second signal — a
  justification written about a value the source has since changed — is **RM151**, below: it needs the
  archive's value now against its value at record time, so it needed a fetch and an enricher home.

- **RM151 — an answer written about a disagreement the archive has since changed says so.**
  *(`just-dna-enricher`; **two new warning stems**, no field, no schema and no signature moves.)*
  An `overrides.csv` row against `clin_sig_concordance.csv` is a judgement about a *particular*
  disagreement, and its `reason` explains why. When the archive later says something else, that reason
  describes a disagreement that is no longer the one on record — and nothing said so.

  `enrich()` now compares each authority's fresh call against **the previous run's
  `clin_sig_authority_calls.csv`**, per `(variant_key, genotype, authority)`, for every subject the
  module's overlay answers. That table is the only place this format keeps what a source said at the
  time, so the finding **names it**: an overlay row against `frequencies.csv` or `resolution.csv` has
  no recorded baseline and nothing here promises one. Warns in both modes, escalates in neither.

  Three states, and withheld is never *unchanged*: `no_prior_record` (first run, unreadable previous
  record, or the authority was unchecked when the answer was written) and `unchecked_now` are info
  notes, not agreement. A difference that is only our own normalizer moving — same verbatim
  `clin_sig_raw`, different normalized member — is reported as a separate sentence, because folding it
  in would accuse a source of a change we made.

  **A move is observable exactly once**, by the run that notices, because the commit rewrites the
  baseline it read. That is the honest shape for an observation; persisting it needs the overlay row
  bound to the value it justifies, which is an authored-surface change and the binding RM117's
  objections all turned on missing. Silent on a module with no overlay answers, which is every module
  today. New surfaces: `clinical.answered_call_shift`, `concordance.shifted_authority_calls` /
  `read_recorded_calls` / `answered_call_sentences` / `answered_call_notes`,
  `licensing.overlay_answered_subjects`, and `EnrichmentResult.answered_calls`.

- **RM138 — closed with its numbers measured; no code changed.** *(documentation only.)* `carried`
  duplicates the text of the warnings it names, growing `compilation` **1.84×** across the reference
  corpus. Re-measured with the compression a real transport uses: **1.06× gzipped** over the corpus and
  **1.13×** on `pathogenic_clinvar`, the 113-warning module the item was filed about — because
  `carried` is a verbatim subset of `warnings`, which is precisely what DEFLATE's back-references
  eliminate. The whole with-`carried` payload gzips to 0.21× the *uncompressed* warnings-only one.

  **The encoding stands, and the recommendation is to serve manifests compressed** where the size lands
  — a catalog, an API response, anything shipping `manifest.json` over a wire. The three cheaper
  encodings stay rejected for the reasons the item already recorded. Closed inside 0.7 deliberately: a
  fourth encoding after 1.0 would be a removal, and removals are major-only.

- **RM136 — the enricher reads the author's overlay, so a correction stops coming back forever.**
  *(`just-dna-compiler` + `just-dna-enricher`; **additive** — one loader made public, one new counter
  on an internal result, no manifest field and no signature moves.)* The compiler applies
  `overrides.csv` before any check reads a row; the enricher re-read the raw derived file, so an
  author who corrected a `resolution.csv` cell through the overlay kept being told the same finding on
  every run, with nothing saying the correction had been recorded and honoured one tier over.

  **Read-only, at input reads, per field.** The enricher never writes through the overlay. Passes that
  read `resolution.csv` as an *input* (`frequencies`, `assertions`, `identifiers`' gene-locus check)
  now see the post-overlay rows; every **merge baseline stays raw**, because a pass that reads its own
  output file writes it back and post-overlay rows would bake the correction into the derived table. A
  finding is answered only when the overlay updates the very cell it is about.

  **Answered is not agreed**: the pair stays in the denominator and `PairCheck.answered` counts it,
  with one INFO line saying the correction is recorded. Dropping it would report a cleaner module than
  there is. New public API: `just_dna_compiler.compiler.load_overlay`, plus
  `licensing.overlaid_input_rows` / `licensing.overlay_answers` in the enricher — there is deliberately
  no second implementation of `apply_overrides`.

- **RM137 — the unmatched-overlay warning is now a property of the module, not of the lap.**
  *(`just-dna-format` + `just-dna-compiler`; **one warning code added, one reworded** — no field, no
  parquet, no signature moves.)* An overlay `update` naming a row the compiler drops matched on lap 1
  and warned on lap 2, so a module and its own `compile → reverse → compile` disagreed on
  `manifest.compilation.warnings`. The stable quantity turned out to be a property of the **target** —
  *could an artifact of this module carry that row at all* — which is computable from data that
  survives the round trip, so it answers the same on both laps whether or not the row is there to
  match. The unreachable finding therefore fires **matched or not**; that asymmetry is the fix.

  **Two codes where there was one**, and neither reading is "a typo" — a mistyped PMID is also an
  uncited one, so a mistake lands in the unreachable bucket:
  - `overlay_update_target_unreachable` (**new**, actionable) — no artifact of this module can carry
    the row: mistyped subject, or a correction aimed at a row the compiler drops, which is fine.
  - `overlay_update_unmatched` (**reworded**, so grep it afresh) — the subject *is* cited or
    positioned, so the table is short rather than the correction wrong. Re-run the enricher.

  **Scoped to `literature.csv` and `resolution.csv`** (`LOSSY_OVERLAY_TABLES`), the only two a reverse
  rebuilds from something narrower. The other six rebuild whole, so their warning was lap-stable
  already and its text is unchanged. `apply_overrides` gains an additive `defer_unmatched` keyword;
  `update_targets` / `classify_update_targets` are the split, and `cited_pmids` /
  `literature_target_survives` / `resolution_target_survives` are the predicates.

- **RM150 — `direction` gains `contested`; `unknown` stops meaning two things.**
  *(`just-dna-format`; **additive** — a new member on an existing vocabulary. Nothing re-points, so no
  published module changes meaning and nothing drifts.)* `unknown` had been carrying both *nobody
  assessed the sign* and *the sources disagree about it* — an absence and a finding — and RM148's own
  field description said so without giving a consumer any way to tell them apart. **`unknown` keeps
  its original meaning**, because re-pointing a shipped member would silently change what every
  published module already says by it; `contested` is added beside it, using the word this workspace
  already uses one table over (`clin_sig_concordance.csv`).

  This is the shade RM148 could not fold into a pair. An unestablished sign is still a sign, so
  *evidence that does not exclude either direction* is `direction=<sign>` +
  `stat_significance=not_significant` and needs no member — but no pairing of the two axes says *two
  sources disagree about the sign*.

  **Upgrading a legacy module is unchanged.** `_STATE_TO_DIRECTION` deliberately gains nothing: no
  legacy `state` value means *contested*, so only an author writing `direction` directly can produce
  it. `stat_significance` gains nothing either — a disputed sign is not a disputed strength.
  `contested` projects to `state=neutral` through `trimmed_state()`, like `unknown`, and that entry is
  **explicit**: the map is read with a default, so a member missing from it projects silently rather
  than failing, and the guard is now an equality over the walked vocabulary.

- **RM108 — a re-curation is recognised, and currency is derived rather than marked.**
  *(all three packages; **additive** — one new manifest field and two new warning codes. No column
  changed, so `gene_validity.signature` does not move and no module recompiles to new bytes.)*
  ClinGen's `assertion_id` embeds the curation timestamp, so a re-curated assertion arrives under a
  different id, misses the merge key, and is appended beside the row it replaces —
  `manifest.gene_validity.classifications` then published `["definitive", "refuted"]` with nothing
  saying which stood. **The newest `classification_date` is now read as current and nothing is
  deleted**; both rows stay in the file so the drift is visible.

  **The marker column the item was filed for does not exist, deliberately.** The row that must be
  marked is the one *already in the file*, and merge-not-clobber forbids the pass editing it — so a
  stored marker would be correct on every run except the one that created the ambiguity. Currency is
  derived at every read (`just_dna_format.gene_validity.classify_currency`, public), grouped on
  `(gene, disease_id, moi, submitter)` — the source's grain minus `dataset`.

  **Two edges withhold rather than guess:** a tie on `classification_date`, or any member of the group
  stating none, leaves no row current and none superseded; those groups publish all of their
  classifications. New: **`manifest.gene_validity.superseded_count`**, and the warning codes
  `gene_validity_superseded` / `gene_validity_currency_undecidable`, both **carried** — an author's
  only available edit is deleting a row, which falsifies the record. They warn in both modes in both
  tiers and escalate in neither; `validate` reports what `compile` reports.

  **One behaviour change beyond gene-validity:** the compiler's fact-table loop now de-duplicates
  check warnings on the message, as every both-sides check already did. This is the first fact check
  the pre-flight also runs, and without it the line — and its `warnings_summary` count — arrived twice.

- **RM103 — the manifest now records the version that was read, not only the one that was invented.**
  *(`just-dna-format` + `just-dna-compiler`; **additive** — a new optional manifest field, no digest
  moves.)* `normalize_version` strips every non-digit and pads to three zeros, so `version: abc`
  becomes `"0.0.0"` — deliberate since RM17, and unchanged here. What changes is that the artifact
  recorded only the *result*: `manifest.identity.version` read `0.0.0` with nothing beside it saying
  the author wrote `abc`. **New: `manifest.identity.version_coerced_from`**, the authored string when
  the model rewrote it and `None` when it was already canonical SemVer. The compiler's warning naming
  both values is unchanged and still fires in `compile` and `validate` alike; a build log is just not
  what a consumer holds.

  **`reverse_module` now re-emits the pre-coercion string**, recovered from the artifact's own
  `manifest.json` (`version_coerced_from` first, `version` second). Re-emitting the coerced one would
  leave the next compile nothing to coerce, so the new field would go absent on lap 2 and a module
  would disagree with its own round trip on a published field. An explicit `--version` still wins, and
  a bare parquet directory with no manifest still leaves the key out. **Side effect worth knowing:**
  reverse previously dropped `module.version` entirely unless a caller supplied one, so a reversed
  spec now carries the authored version where it used to carry none. Nothing hashes on it.

  The **refusal** half of RM103 — should a digitless version be rejected outright — is unchanged and
  stays on the 1.0 cleanup tracker; it is a tightening, and no sentinel SemVer exists to coerce to.

- **RM110 — `constraint_flags` had two producers, two encodings, and one of them inside the fact set.**
  *(`just-dna-format` + `just-dna-enricher`; **one existing artifact's digest moves** — see the cost
  line.)* The live gnomAD route pipe-joined its flag list; the bulk-TSV snapshot route copied gnomAD's
  **JSON array literal** into the cell. Re-probed against the published v4.1 parquet before any code
  moved: of 18,111 rows **none** is null or empty — 17,403 carry `[]` and 708 carry a real literal in
  14 distinct shapes — so `if row.constraint_flags:` was true for **100%** of snapshot rows where the
  flagged fraction is 3.9%, and splitting a two-flag cell on `|` returned one bogus token. The column
  is inside `GENE_METRICS_FACT_FIELDS`, so the same gene fetched two ways minted two
  `gene_metrics.signature` values.

  **Fixed on the model, not in the fetching tier**: `just_dna_format.gene_metrics.normalize_constraint_flags`,
  bound as a `mode="before"` field validator (neither producer hands over the declared `str | None`,
  and a `mode="after"` validator cannot rescue a value the type rejects first). The published snapshot
  is immutable and every `gene_metrics.csv` already written from it carries `[]` on disk, so a
  producer-side fix would have left those tables contradicting the column's own description. Three
  call sites share the one function — the live route, `lookup_snapshot` (the published snapshot) and
  `constraint_build` (future ones) — and it is idempotent, so a rebuilt snapshot passes unchanged.
  "Empty → null" was only half the fix: the non-empty cells needed parsing, or the 708 flagged rows
  stayed unreadable. A bracketed string that does not parse is kept verbatim rather than guessed at.

  **Cost, measured:** exactly one row in the reference corpus — `reference_examples/hboc_palb2/`
  carried `constraint_flags=[]`, so its `gene_metrics.signature` and `artifact.digest` move; the
  checked-in CSV was corrected in the same commit. Nothing else in the sixteen examples changes.
  **If you have compiled modules from the v4.1 constraint snapshot, their `gene_metrics.signature`
  will move on the next recompile, and that is the fix arriving rather than a regression.** The field
  description, false on the snapshot leg in both directions, was rewritten.

- **RM147 — a source read by hand that yields no row had nowhere to go, and the home already existed.**
  *(`just-dna-format`; documentation and a test — no behaviour changed.)* Filed and answered on
  2026-08-31 from a consumer report (S82), which asked for a view rather than proposing a shape.

  An agent read five literature services by hand to confirm the papers behind two rows and recorded it
  as five `licensing.csv` rows at `layer=literature`. The reporter removed them on our own two rules —
  a literature source's terms are per **article** (RM46), and a pass that put no row in a table records
  no source (RM142) — and measured that they bought no enforcement. Then asked the real question: after
  removal, nothing anywhere records that a human went and looked.

  **The home already exists.** A `literature.csv` row no study, bin or pharm row cites is kept in the
  CSV and dropped from the artifact with `literature_row_uncited`, shipped in RM79 for a citation the
  author deleted — and it is the same shape for the opposite case, a paper read that did not become a
  row. It is structured and checked, it **cannot make a licence claim**, and it is about the *paper*,
  which is the thing consulted; a service is only how the author reached it.

  **Consumers:** nothing changed. `LiteratureRow`'s docstring now says this is that case's home and why
  the licensing table is not, and a test authors the reported shape — two articles, one cited and one
  not, green `--strict`, the uncited one named, and no `licensing.csv` at all, because nothing is owed
  for reading an abstract.

- **RM148 — `direction` and `stat_significance` are one pair, and the description did not say so.**
  *(`just-dna-format`.)* Filed and built on 2026-08-31 from a consumer report (S83), an hour after S80
  was accepted and in the same spirit.

  Two runs of a byte-identical prompt, same model and paper, wrote different values for one variant on
  one body of evidence: `risk`/`suggestive` against `unknown`/`not_significant`, both green. The
  evidence was two cohorts trending the same way at p ≈ 0.073, combined OR 3.58 with a CI of 0.96–13.4
  at 28.4% power — and both readings were defensible against a description that named the four members
  and said only *orthogonal to `state`*.

  **Not a vocabulary gap.** `direction` records the sign of the reported estimate; `stat_significance`
  records how far to lean on it; and the orthogonality is itself the answer to *is a sign you cannot
  lean on still a sign* — yes, because the other column says you cannot lean on it. The state the
  report wanted a member for is already the **pair**, `direction=risk` + `stat_significance=
  not_significant`, which authors and validates today.

  The description now carries that reading and bounds `unknown`: *no sign to record* — not assessed, or
  the sources conflict — **never a sign you may not act on**. Writing `unknown` for a weak trend
  discards the sign the paper reports and leaves `stat_significance` speaking about nothing.

  **Consumers:** one description string, so anything rendering `model_fields` picks it up. No member
  added — a *looked, no sign established* member would be a second spelling of the pair, which is
  Principle 5's overloading arriving as a synonym, and permanent under P3. A test asserts the two
  vocabularies stay disjoint but for `unknown`.

- **RM144 — the licence-disagreement warning printed the remainder as though it were the whole set.**
  *(`just-dna-compiler`.)* Filed and built on 2026-08-31 from a consumer report (S79).

  The check filtered the annotation-layer rows to those whose licence *differs* from the declaration,
  then rendered that remainder as the whole set. A two-source module declaring `CC-BY-NC-ND-4.0` — an
  exact match for one row, and the binding constraint on the artifact — printed *sources report
  ['CC-BY-4.0']*, with the agreeing row invisible in the sentence complaining about agreement.

  **Two problems with different repairs read identically:** *your declaration is unsupported* versus
  *your declaration is not universal*, the second being the ordinary mixed-licence shape where the most
  restrictive term binds and the declaration is already correct. It cost two agents a full
  re-adjudication that found nothing wrong, and it survived RM142's fix — removing the phantom row
  leaves a real disagreement still rendered as total.

  The count now leads and the agreeing rows are named beside the disagreeing ones, with a distinct
  sentence for the genuinely-unsupported case. **The denominator counts rows, not distinct licences** —
  two sources sharing a licence are two obligations — and a licence-less row or a non-`annotation` layer
  stays outside it. Suppressing the warning when any row matches was refused, on the reporter's own
  argument: a module declaring the least restrictive of several is exactly the one worth warning about.

  **Consumers:** the message text changes; `declares license` still leads it, which is the fragment the
  existing test keys on, and the non-escalation is unchanged and re-pinned. No reference example moves a
  digest, signature or warning — the corpus has no mixed-licence module, which is why this survived it.

- **RM145 — `state`'s six members were printed as peers, and two of them are retired in our own code.**
  *(`just-dna-format`.)* Filed and built on 2026-08-31 from a consumer report (S80).

  `VariantRow.state` was described as `One of: risk, protective, neutral, significant, alt, ref` — six
  values, no standing — while `derive.py` calls `alt`/`ref` **the retired descriptors** and maps both to
  `direction=unknown`. A consumer whose authoring surface passes our descriptions through verbatim
  (deliberately, so a vocabulary change reaches an author without being restated) therefore offered an
  agent six equal choices, and it picked `alt` for a heterozygote. **The reporter had to read
  `derive.py` inside their own `.venv` to author one cell honestly.** Measured across the sixteen
  reference examples: 377 `risk`, 4 `neutral`, and zero uses of `significant`, `alt` or `ref`.

  The description now separates current members from superseded ones and names each group's successor.
  **Three groups rather than the two the report asked for:** `state` is the Principle 5 anti-pattern the
  charter names by hand, so the split is by which axis a value was really on — `significant` is a
  significance claim that `stat_significance` owns, not a dead value, and grouping it with `alt`/`ref`
  would tell an author it means nothing when it means something this column is the wrong place for.

  **Consumers:** one description string, so anything rendering `model_fields` — `describe`,
  `requirements`, `reference` and the reporter's own surface — picks it up with no change of their own.
  No vocabulary member added or removed and nothing invalidated; removal stays major-only and was not
  requested.

- **RM143 — the enricher diagnosed a wrong-assembly coordinate and `compile --strict` built over it
  anyway.** *(`just-dna-compiler`.)* Filed and built on 2026-08-31 from a consumer report (S78).

  A GRCh37 coordinate pasted into a GRCh38 module — `rs61849494`, 5.6 Mb and a strand flip away from
  where the module says it is. `enrich --strict` refuses with a diagnosis naming the rs-number to author
  instead; `enrich` best-effort reports it and writes the table; and `compile --strict` then succeeded
  **silently**, over a module internally consistent and about the wrong locus.

  **Two of the reporter's three asks were already shipped**, which is half the answer. Their option (2),
  re-running the rsid↔coordinate check in the compiler, is refutable on the data: `resolution.csv` holds
  one coordinate, not both — for a coordinate-authored row the enricher records what the author wrote —
  so there is nothing to compare without a fetch, and P2 forbids the fetch. Their option (3), a compile
  warning, is `verification_findings_recorded`, which shipped in this same release and is absent from
  the 0.6.6 they measured.

  What was missing was the last step of their option (1): the diagnosis reached `verification.json` and
  **no severity attached to it**. `build_disagreement_error` now refuses a `strict` compile on a recorded
  `genome_build_agreement` finding, in both `validate_spec` and `compile_module`, with the error equal on
  both sides and placed ahead of `output_dir.mkdir()` so a refusal writes nothing.

  **The strict line does not move.** `strict` still means reproducible, never right — the compiler has no
  reference and a file shifted by one base still passes. This one check is the exception on
  *internal-consistency* grounds: its findings say the rows are on a different assembly than the
  `genome_build` the module declares, which is one authored file contradicting another rather than the
  module disagreeing with an outside archive. Every other recorded finding still only warns, pinned over
  four checks including `reference_allele`, which produces this diagnosis's own input.

  **Consumers:** a `strict` compile refuses a spec whose `verification.json` records a wrong-build
  finding — new behaviour for anyone compiling one, and the point. Everything else is unchanged: no
  attestation is silent (an unverified module is the ordinary case), `findings=0` is a clean bill, and a
  `skipped` record is unknown, which is what `--offline` writes. `best_effort` builds and warns as
  before. No reference example carries such a finding, so the 0.7.0 release record is unaffected.

- **RM142 — the dosage pass declared a ClinGen obligation for a module ClinGen curates nothing of.**
  *(`just-dna-enricher`.)* Filed and built on 2026-08-31 from a consumer report (S77).

  A single-variant `SIRT6` module. The pass reported `dosage: missing: [SIRT6]`, wrote no
  `gene_metrics.csv` row, and wrote a ClinGen row into `licensing.csv` anyway. That table travels to
  the registry and is read as *this module uses this source*, so the module carried a false statement —
  and it fired `declared_license_disagrees` against a declared licence that never met ClinGen's, sending
  an author to adjudicate a conflict that does not exist. Both reproduced.

  **The compiler cannot catch it.** `_source_checks` exempts the `annotation` layer from its orphan
  warning by design (RM46), because that is where an author is told to record a hand-read source and
  warning about it would make compliance noisy while omission stayed silent. Only the pass knows whether
  it contributed.

  The fix is the rule the rest of the family already follows: `gene_metrics`, `frequencies`,
  `assertions` and `gene_validity` all derive the source set from the rows they wrote, so a pass that
  wrote nothing records nothing. `clingen.py` alone built a fixed row and wrote it unconditionally.
  **The siblings were checked rather than assumed** — run offline over a module they cover nothing of,
  neither writes a licensing file at all.

  **Consumers:** a module whose dosage pass covered no gene no longer carries a `clingen` row, and no
  longer warns about a licence disagreement it had no part in. A module ClinGen actually fed is
  unchanged — keyed on what this run covered, not on what the table holds and not on the absence of
  missing genes, with tests for all three. No reference example changes, so the 0.7.0 release record is
  unaffected.

- **RM141 — `validate --strict` blessed a module `compile --strict` refused, whenever the resolution
  table was partial.** *(`just-dna-compiler`.)* Filed and built on 2026-08-31 from a consumer report
  (S76) whose headline mechanism did not reproduce, and whose second finding was ours.

  The report: an `enrich` killed by a quota limit left a `resolution.csv` covering 201 of 263 subjects,
  and — the urgent half — merge-not-clobber was said to turn that into a silent wrong answer, since
  re-running would merge onto the stale rows and never retry the missing 62. **That does not
  reproduce, on this tree or on the `v0.6.6` they ran.** `enrich` gap-fills: a run over a table
  covering one of three subjects asks the source about exactly the other two. The atomic write they
  asked for is also already shipped, as RM128 in this same release, which is why the interrupted run
  left the previous table rather than a truncated one.

  **The reporter then corrected their own account**, which sharpens what this closes: the file was
  never truncated — 203 sorted rows, a clean final newline, and the 62 absent rsIDs scattered across the
  whole range rather than forming a tail. A complete write of an incomplete resolution *set*, which
  matches the code: a subject whose live request could not be made is written as no row at all, so the
  table never states a negative nobody established. Nothing was interrupted, so the atomic writer would
  not have prevented it — and the same file comes out of a `best_effort` run that completes normally
  over an unreachable source. The closure is this item, by the right route: reading the table against
  the spec beside it is indifferent to *why* a row is absent.

  **What is real is that nothing said so until the compile.** `compile --strict` refuses a module whose
  variants have no position after resolution; `validate --strict` did not report it at all. So the
  pre-flight passed clean and the compile immediately after refused — the third break of the parity
  rule, hiding behind that rule's own exemption. What stays compile-only is a check reading *resolved*
  rows, and whether the injected table **can** place a row is arithmetic over bytes the pre-flight has
  already loaded.

  `resolution.unresolved_subjects` is the predicate resolution applies, now called from both sides
  rather than restated, and under `strict` the pre-flight appends the compile's error verbatim. Two of
  the compile's own distinctions are kept: nobody-asked is not asked-and-absent, and `--no-resolve`
  silences the check the way it silences the fill. A **double-report** was found doing it — both passes
  reach the finding for one subject, measured at 24 warnings for 12 subjects with `warnings_summary`
  counting 24 — and is de-duplicated on the message.

  **Consumers:** no schema change, no new field, no new warning code. A spec that was going to be
  refused by `compile --strict` is now refused by `validate --strict` too, with the identical message —
  which is a behaviour change for anyone treating a green `validate` as a compile guarantee, and is the
  point. Measured: no reference example moves its `artifact.digest`, `content_signature` or warnings,
  so the 0.7.0 release record is unaffected; none of the sixteen has a partial table, which is why this
  survived a corpus that size.

- **RM140 — a study row's p-value and effect size were asserted to belong together, and nothing
  recorded what either came from.** *(`just-dna-format` + `just-dna-compiler`.)* Filed and built on
  2026-08-31 from a consumer's reproducibility benchmark (S75), after the proposal round had closed —
  it is not one of the twelve and lands inside this same uncut number, because a new optional column is
  what sizes a release.

  Two agents, byte-identical prompts, the same three DOIs, overlapping on exactly one row: `p_value`
  0.36 against 0.75, `effect_size` 1.42 on both. Neither was a misreading. The paper reports two
  analyses of the same association — an allelic Fisher's exact test (`OR 1.4, p 0.36`) and a univariate
  logistic regression (`OR 1.42, p 0.75`) — and one run's row carried the second's magnitude beside the
  first's p-value. **Everything was green**, `strict` on both `validate` and `compile`, `audit_module`
  and `quotes_found` included: the provenance quote is verbatim and correct because it grounds the
  significance *verdict* and contains no statistic at all, so quote verification is structurally blind
  to this. `study_design` describes the **study**; nothing described the **analysis**, so a correct row
  and a mispaired one were byte-indistinguishable to every consumer and every check — and no check could
  be written, because the facts it would compare were recorded nowhere.

  **`StudyRow.statistical_test`** is one optional free-form column shaped like `study_design`: which
  test or model produced this row's numbers, and what it was adjusted for. No vocabulary, and
  **deliberately no gate** — the reporter argued that against their own ask and is right, since the
  gate is unwritable before the column exists and shipping both would make every published row
  retroactively incomplete.

  **The one behaviour change is the duplicate-citation warning.** `duplicate_study_citation` reads a
  repeated `(variant_key, pmid)` as *the same claim written twice*, which two rows naming two analyses
  are not; **both stated and different** now suppresses it, and nothing else does. An absent
  `statistical_test` is *unknown*, and unknown against a stated value cannot establish that two rows
  describe separate work — Kleene rather than `a != b`, which would suppress on every absent cell and
  silently retire the check for every module written before the column existed.

  **Measured, not asserted.** `artifact.digest` moved on **10 of the 16** reference examples — exactly
  the ten carrying a `studies.parquet` — and `content_signature` on **none** of the sixteen. The
  published `0.7.0` release record was re-measured with it rather than left standing: its two parquet
  axes read `4/15` before this item and read `14/15` after, the `studies.parquet` column is declared,
  and the concordance-parquet declaration that called itself *the release's most visible consequence*
  was corrected, because it was a measured claim and stopped being true. The gate exits 0 against the
  amended record.

  **Consumers:** one optional column on `studies.csv` and `studies.parquet`, read by nothing that does
  not want it; unset, it is omitted from `content_signature`, so no published module's identity moves.
  The warning's code and message are byte-identical for every case that still reports. `_KEY_FIELDS` is
  **not** widened — the published `key.columns` for `studies.csv` is still `(variant_key, pmid)`, and
  re-keying a shipped authored table is major-only. Note the premise this corrects: two rows sharing a
  variant and a PMID have always both reached `studies.parquet` — the duplicate is a warning, never a
  drop — so the capability was there and only the legibility was missing.

- **The 0.7 round's files were closed out.** *(Documentation only — no package changed.)* Four entries
  sat in forward-only files with a `SHIPPED` banner on them, which reads as late rather than done:
  RM126 and RM71 in `ROADMAP_0_7.md`, RM133 and RM134 in ROADMAP.md. All four moved to
  [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md), so the round's twelve are now in one place.

  **`ROADMAP_0_7.md` closed with them, and the succession is the point rather than the tidying.** The
  minor-deferral file is named for the release that will decide its contents, so a cut closes one and
  opens the next: the round is in [history/ROADMAP_0_7.md](history/ROADMAP_0_7.md) with the seven
  entries that shipped or closed, and the ten still waiting — RM122, RM23, RM16, RM28, RM56, RM65,
  RM66, RM67, RM68, RM84 — became [ROADMAP_0_8.md](ROADMAP_0_8.md), unchanged but for the file they sit
  in. `PROPOSAL_0_7.md` stays beside the other five concluded threads in `docs/proposals/` and is
  marked a record rather than a plan; it no longer wins over anything, because everything it decided
  has landed.

  Every inbound link was retargeted **by item rather than by path** — a link to a deferral that moved
  now resolves in `ROADMAP_0_8.md`, one to an entry that shipped resolves in `ROADMAP_HISTORY.md`, and
  one to the round itself resolves in `history/`. Verified by `test_doc_links.py`, which is the
  authority here rather than a fresh sweep: it exempts a consumer's byte-frozen prose, and **three
  links in an archived report were reverted after being retargeted** — including the `ROADMAP.md#rm89`
  in S35 that the exemption test asserts on, which records where RM89 lived on the day it was written
  and whose current pointer is in the reply above it. Our own replies in that file *are* ours to
  correct and were. Three stale counters in ROADMAP.md were fixed in passing, including the *Active
  items* enumeration, blind for the third time — it read *not one of them is a decision* through the
  three decisions filed beneath it.

- **RM139 — the release gate could not tell a broken compile from a spec that outgrew the old
  compiler.** *(`just-dna-format` + `just-dna-compiler`.)* Filed by running RM126's own gate for real
  at this cut, where it refused the release over `reference_examples/cyp2c9_warfarin_grch37/`: RM70
  put the optional `requires_callable` column on `pharm_variants.csv`, that example uses it, and 0.6.6
  refuses the spec under `extra="forbid"`. Nothing had failed — the previous release cannot produce a
  before state for it, so no like-for-like comparison exists — and this recurs in **every minor that
  adds an authored column and exercises it in the corpus**, as it does for any example newer than the
  last release. The gate read *one side only* as *a compile failed* and the tag had to be waved
  through by hand.

  **The two directions are facts about different releases, and the gate now says which.** A module in
  the BEFORE tree and not the AFTER one is a regression **in the release being cut**: still fatal,
  unconditionally, and now carrying the compiler's own errors, which `build_outputs` had been logging
  and throwing away. A module in the AFTER tree and not the BEFORE one fails until the published
  record's new `ReleaseRecord.unmeasured` list names it. `SweepMeasurement` splits `unmeasured` into
  `only_before`/`only_after` and keeps the union as a derived property; the sweep's JSON keeps its
  original `unmeasured` key and adds the two halves beside it, so a release script piping to `jq` is
  unaffected. `UNMEASURED_MODULE_PHRASE` still appears in both messages for the same reason.

  **`unmeasured` is a denominator, not the per-module escape hatch the roadmap entry refused**, and
  the difference is that the gate checks an **equality** against what it could not measure rather than
  a membership test: a module measured on both sides cannot be excused by listing it (that is reported
  as a note), a regression cannot be excused by listing it, `as_record` refuses to mint a record over
  one, and a movement on a measured module gates however the list reads. `as_record` fills the field
  from the measurement, so the exclusion is forced into the record the same way `declared` is —
  extending the existing mechanism, not adding a second kind of gate input. Records written before the
  field read `[]`, which is their correct claim; the 0.7.0 record is backfilled with the module its own
  `evidence` sentence already named.

  **Consumers:** `ReleaseRecord` gains one optional list field, minor-legal under Principle 3 and read
  by nothing that does not want it. `build_outputs` now returns `(outputs, failures)` — a compiler
  internal, but a release script calling it directly must unpack.

  Re-measured end to end rather than asserted: the 0.6.6 → 0.7.0 sweep was re-run over all sixteen
  reference examples with 0.6.6 installed in an isolated environment — fifteen measured, one refused on
  `requires_callable]: Extra inputs are not permitted`, gate exit 0 against the shipped record where
  the cut had needed a human to read past it, and exit 1 naming the module when one is removed from the
  spec root instead.

- **RM134 § B — the concordance check takes a second authority, and the record has a producer.**
  *(`just-dna-enricher`, plus one optional `module_spec.yaml` field in `just-dna-format` and its
  one-line passthrough in `just-dna-compiler`.)* PubMind (RM134 § A shipped its snapshot) joins ClinVar
  as an annotation authority, and `clinical.clin_sig_concordance` becomes an N-authority check whose
  seam is RM130's `classify_concordance` — a pure function that already knew nothing about ClinVar.
  `pubmind.py` is the runtime reader over the snapshot, duckdb beside the polars builder; there is
  deliberately no `lookup_loci` on it, because PubMind's coordinates are back-mappings of extracted
  text and nothing it produces may enter `resolution.csv`.

  **The three-way check subsumes the two-way rather than running beside it.** With no PubMind snapshot
  that authority's call reads `unchecked` on every subject, and the degenerate case is exactly the
  ClinVar-only finding: the same subjects are contested, the same conflicts are logged in the same
  pinned words, and no author meets one disagreement twice. What changes is what the record withholds
  — `authority_concordance` reads `unchecked` rather than `single`, because one authority speaking
  while another was never asked is not corroboration and must not be recorded as any.

  **The record now has a caller.** RM130 shipped the models, the classifier and the writer with
  nothing producing them; `enrich()` builds the record from the comparison it already ran — never a
  second pass over the snapshot — and commits both tables at the gate, after every strict refusal, so
  a refused run leaves none behind. A module holding a ClinVar snapshot therefore carries the record
  even when nothing is contested: the empty pair is the claim *we asked, and nothing here is
  contested*, which is a different claim from the absent pair a run with no authority to ask leaves.

  **The tautology is decided per leg.** Where a module's `clin_sig` was drafted out of a snapshot it
  would be compared against and has not moved since, that authority is not consulted at all and states
  nothing — a call recorded there would agree with the module by construction. But the *check* is
  skipped only when every leg is hollow or unasked: a module drafted from ClinVar still gets a real
  comparison out of PubMind, and throwing that away to suppress the hollow half is the error
  `enrich_pgx` already made once. `is_tautological_leg` states the conjunction once and reads the
  checked column out of `DRAFT_PROJECTIONS`, so § C's drafter needs no edit here.

  **Several PVIDs over one allele fold to one call, camp guard first.** PubMind consolidates on
  extracted text, so one allele carries several records whose verdicts disagree — 35,742 disagreeing
  keys in the measured file. Where they straddle the pathogenic/benign line the answer is
  `conflicting`, the vocabulary's own word for it, in the camp that opposes nothing; folding by
  severity there would silently answer `pathogenic`, a winner picked by an ordering nobody defined.
  Within one camp the fold is the shared normalizer's own severity rule, the same one that resolves a
  composite token. Confidence is withheld unless exactly one record stands behind the call, and the
  multiplicity is counted on the record rather than discarded.

  **`authority_precedence:` is recorded and computed with by nothing.** One optional ordered list in
  `module_spec.yaml`, beside `weighting:`/`authorship:`, saying whose call the curator weighted while
  deciding — machine-readable so a consumer can see the stance, and read by no tier. Two modules
  differing only in it compile to byte-identical parquets with the same `content_signature` and the
  same `artifact.digest`, which is the property the tests assert rather than a round trip of the
  value. **Nothing resolves a split**: no `majority`, no consensus call, no resolved winner, because
  choosing between a declared order and a majority needs a weighting model this workspace has
  declined to invent three times.

  **Warning-tier in both modes, escalating in neither** (`@clinsig-never-escalates`), with more force
  at two authorities than at one: a disagreement with a literature miner's aggregate is a statement
  about that extraction's limits at least as often as about the module, the measured corpus join
  agreed 62 % of the time, and `discordant` is a fact about the field rather than a defect in the
  module. A run that found nothing contested reports no zero, and a run that could not put the
  question writes nothing at all.

- **RM85 — a recorded release, compared against the one its source publishes now.**
  *(`just-dna-enricher`, plus one `VALID_VERIFICATION_CHECKS` member in `just-dna-format`.)*
  `SourceRow.dataset` has recorded which release a module's rows came from since RM4, and two things
  read it — the tautology skip, and `withdraw_stale_dataset` when a module ends up mixing two. Neither
  answered *"ClinVar has published since you drafted this"*, which is the actual trigger for a
  source-refresh pass, so an author who had forgotten and a curator who inherited the module were both
  on their own. `currency.check_dataset_currency` is that comparison, run at the end of `enrich()`,
  attested as `dataset_currency`, switched by `--verify-datasets/--no-verify-datasets`.

  **A comparison, not a column.** The column-shaped repair — a field saying what this module was made
  from and what would age it — was refused one table over in RM71 for restating `dataset` and then
  rotting where `dataset` is maintained. This reads `sources.csv` and writes nothing at all; repairing
  a stale label is a re-draft, which is an author's decision and a different command.

  **Three states, and the third is the item.** `behind` is `True` (the source has published since, with
  both labels named), `False` (still current) or `None` — nobody could ask. `--offline` is where that
  bites: an offline run makes no request, so every recorded release is `unchecked`, never *up to date*.
  `subjects` counts the legs asked **and** answered comparably, an unaskable source is named in the
  record's `detail` rather than counted, and with no leg settled the pass records a skip rather than
  `ran(0, 0)`. Comparability is a withhold of its own: `clinvar_dataset_label`'s digest form and its
  stated-date form name one release space in two spellings, so a digest against a date is
  *uncomparable*, not behind.

  **Severity follows the mode, over the superseded set alone.** `strict` refuses on a release the
  source has moved past and never on an unchecked one — escalating an unreachable source would make
  `--offline --strict` impossible forever over something no author can edit, which is the
  `unreachable_rsids` rule.

  **One probe ships: ClinVar.** It is the only source this tier can ask for a release label in the
  namespace it already records — the live VCF's `##fileDate=`, read through the same function
  `clinvar_build` uses on a downloaded file, because two spellings of one label would not fail, they
  would simply never match. The stream is abandoned after 256 kB rather than sending a `Range` header a
  server may ignore. Every other source reports `unsupported`, and `PROBE_SOURCES` is derived from the
  registry rather than restated beside it.

  It is **`--rederive`'s cheap neighbour** — the same *has the world moved* question asked about the
  release label instead of the rows, at one request per source — so ENRICHER § `rederive` now says to
  put it first. And it cannot agree with itself: the rows compared are the ones on disk before this
  run's commit, and the licence rows `enrich()` writes are at the `resolution` layer with no `dataset`
  at all.

- **RM130 — a contested clinical call now has a name to act on, and a key that survives five
  authorities.** *(`just-dna-format` + `just-dna-compiler` + `just-dna-enricher`; two new optional
  derived tables, three new closed vocabularies, one new warning code.)* The ClinVar cross-check
  reported *twenty findings of 141,616 subjects* and kept none of the twenty: they reached a logger
  and nothing else, so an author could read the number and not act on it. `clin_sig_concordance.csv`
  is those subjects, named and joinable, keyed `(variant_key, genotype)` — genotype because the
  comparison is of an authored call for a genotype, and a table keyed on the variant alone collapses
  two authored calls that disagree with the archive differently. Beside it
  `clin_sig_authority_calls.csv` carries what each authority actually said, keyed
  `(variant_key, genotype, authority)`.

  **The shape is RM134's, not the one RM130 first decided, and the swap is the interesting part.** The
  original record carried "the authored value, the source's value" and named its authority in a
  *field* — `ClinSigConflict.clinvar` — which would have cost a key change or a retype the moment a
  second archive arrived, one item later in this same release. P3 reserves both for a major. So the
  parent row carries an agreement *state* instead: `authority_concordance`
  (`concordant`/`discordant`/`single`/`none`/`unchecked`) and `authored_position`
  (`matches_all`/`matches_some`/`matches_none`/`absent`/`unchecked`), two orthogonal closed
  vocabularies that are five members at two authorities and five at five. A single vocabulary was
  drafted and failed a stress test at five sources because its members named the authority inside
  themselves; the root cause was one field carrying two axes, which is the Principle 5 anti-pattern
  and the combinatorial growth was its symptom.

  **Nothing resolves a split.** With five authorities in a two-against-three disagreement, precedence
  names one winner and majority names another, and choosing needs a weighting model this workspace has
  declined to invent three times. There is no `majority` column, no consensus call and no resolved
  winner anywhere in the tables or the manifest block. Confidence is likewise not normalized across
  authorities — a gold-star count and a literature miner's evidence-depth count are different
  instruments — so the detail row carries the published value with `confidence_unit` beside it, and the
  model refuses a magnitude with no instrument named.

  **A conflict is a question and an `overrides.csv` row is the answer.** The record joins the overlay's
  covered set, taking it from seven to eight, and it is in for a different reason from the other seven:
  not because it carries curation to lose — it carries none and is rewritten whole on every run — but
  because answering a contested subject is what an overlay row *is*. The paired detail table stays out
  by name: the author answers the question and does not get to rewrite what an archive published. The
  table's documentation and the new `clin_sig_concordance_contested` warning both name `overrides.csv`
  and never `provenance.json`'s `outranks`, steering new authors onto the side of the succession that
  survives 1.0. The warning is **actionable rather than carried**, unlike its neighbour
  `verification_findings_recorded`, because it counts the post-overlay rows — so writing the answer
  clears the finding, and `overlay_rows_suppressed` reports the removal so nothing goes quiet. It never
  escalates under `--strict`, for the reason the check beneath it does not: half the time the archive
  is the stale side, and escalating would have this format arbitrate a clinical dispute.

  Two smaller things travelled with it. `_CLIN_SIG_CAMP` moved out of `clinical.py` into the new
  `concordance.py`, because the record and the two-way check must draw the opposed-versus-differing
  line in one place — two maps for one distinction is how a drift in our own code comes to read as a
  disagreement between two archives. And an honest note that came out of building it: at a single
  authority every reported conflict is `opposed` by construction, since the check only fires where both
  sides are opinionated and `pathogenic`/`benign` are the only opinionated camps, so
  `_clin_sig_detail`'s differing-but-not-opposed group has no producer today. It gets one as soon as two
  authorities can disagree with each other while neither contradicts the module, which is what the
  record is shaped for.

- **RM131 — the warnings channel says what each finding is, and whether an author can clear it.**
  *(`just-dna-format` + `just-dna-compiler`, plus the deprecated resolver in `just-dna-enricher`; a
  structure change to a surface that already ships.)* `ValidationResult`, `ClosureResult` and
  `CompilationResult` all carried `warnings: list[str]` with no code, no count and no way to tell a
  finding an author *can* clear from one they cannot. A compile of a 190-row module returned roughly
  **14 kB** of prose, and `strict=false` does not help — it changes what counts as an *error*, not how
  much the channel carries — while every document on both sides of this seam tells an author that
  warnings on a green run are the real output.

  **The answer was already being computed and spent on severity alone.** `_BLAME_TIER`/`_BLAME_ROW` is
  literally *whose limit this is*, and its own comment says "blame decides severity and nothing else";
  `_closure_warning` reaches the same distinction from the other end and says so in prose.

  **Two derived fields beside `warnings`, which is unchanged down to the byte.**
  `compilation.carried` is the subset **no edit to the spec directory can clear** — a limit of this
  tier or a fact of a source — so a consumer subtracts it to get the actionable set;
  `compilation.warnings_summary` is `{code: count}` over `vocab.VALID_WARNING_CODES`, with the values
  summing to `len(warnings)` so the digest accounts for the whole channel rather than the part somebody
  remembered to key. Both ship on all three result types too, on every path including a failed compile.
  `manifest.json` sits outside `artifact.digest` (a Merkle root over the parquet `FileEntry` list, and
  that is the mechanism — not a slot in `ARTIFACT_PARQUETS`, which name-sorts), so neither moved a hash
  on any published module.

  **A code names the finding, never the emission site**, because a code derived from where the function
  lives is renamed by a refactor and a published key is permanent within a major (P3/P6). One code
  carries one remediation: two sentences cleared by the same edit share a code and the sentence says
  which cell (the weight-sign pair, the five orphan fact tables), two cleared differently do not.
  Sixty-eight members, nine of them carried.

  **The audit was the real cost and was done once.** Every emission site across three tiers now names
  a code — the ~29 named-list appends in `compiler.py`, the `findings`/`messages` collectors a survey
  of `.append` cannot see, the two `.extend` sites that reach into `binning.measurement_shape_warnings`
  and `deprecation_warnings`, `validate_bins`, `overrides.apply_overrides`, `compiler/resolution.py`,
  and the deprecated DuckDB resolver in `enricher/resolver.py`, whose warnings land in the same
  `manifest.compilation.warnings` as everything else. The three sites that *reformat* a message from
  another tier go through `findings.restate`, which is the one operation that carries a code across a
  rewrite; every other string operation on a finding returns plain prose by construction.

  **`classify` has three answers and no flag: derive, withhold, refuse.** A `warnings_summary` with a
  catch-all key is the rejected repair wearing a different hat — it silently omits what nobody
  classified, and the reader takes the digest as complete. But refusing outright was wrong in the other
  direction: `CompilationResult(warnings=["prose"])` has been legal since 0.6, so an unclassified
  channel now **withholds** (an empty pair, which reads as *not classified* rather than as
  *complete and short*), and only a *part*-classified channel — which no legitimate caller can produce
  — raises. That also keeps a raise out of `_build_manifest`, which runs after every parquet is on
  disk, where it would have left an output directory with no `manifest.json` beside them. The published
  contract is therefore *either empty or accounting for the whole channel*, stated in both field
  descriptions; a supplied pair is checked against the channel, since a wrong claim is worse than a
  withheld one.

  **The guards are equalities over walked sets, and one of them was a hole until a mutation found it.**
  `test_warning_codes.py` asserts the emission sites against the vocabulary in both directions (a code
  with no emitter and an emitter with no code both fail), and the corpus half runs every reference
  example through both entry points, which is what catches a message that lost its code on the way
  rather than at its site. The receiver names are themselves a registry now: a hand-typed list omitted
  `lines`, which `_carried_vrs_warnings` collects into, and stripping that site's wrapper passed the
  guard — so the declared set is checked for equality against the receivers actually derived from the
  source, with the channel/refusal split declared beside it because one builder feeds both.

  **The transport stays `list[str]`.** `findings.CodedWarning` is a `str` subclass, so every `.extend`,
  every `if w not in all_warnings` de-duplication and every consumer already grepping a phrase keeps
  working untouched — including the de-dup-by-message that lets a check run in both `validate_spec` and
  `compile_module` and publish one line. Pydantic flattens the subclass at a model boundary, which is
  right for the published surface and fatal for a caller that keeps building on it, so `compile_module`
  and `close_module` seed from an internal `_validate_spec` that hands the classified list back beside
  the result. That trap is pinned by a test rather than left in a comment.

  **The suppression record rides the same channel (RM124 × RM131).** A row removed by a `suppress` was
  invisible in the build product — absent, with no trace of why — so the overlay now says so, one line
  per **reason** with a count, which is what `reason` being a required column buys. Counted over the
  *overlay's* rows and never over the rows removed: after `reverse_module` the derived table is already
  post-overlay, so an effect-based count would say a number on lap 1 and vanish on lap 2, moving a
  published field between a module and its own round trip. Proved against the real
  compile → reverse → compile path, not argued.

  **RM126's sweep gets the discriminator its own comment promised.** `sweep.compare_module` reports
  `carried_added` beside `actionable_added`, read off the after-manifest's `carried` rather than
  re-derived from prose. `axes["warnings"]` deliberately still fires on any movement — narrowing it
  would make a published axis mean something other than what every record already written claims — and
  a pre-0.7 manifest reports every addition as actionable, the safe direction, since calling an
  unrecorded finding carried would tell a reader that something fixable is not. Both new fields join
  `compilation.warnings` in `EXCLUDED_MANIFEST_FIELDS`, because they are derived from it and move
  exactly when it does.

  **Repairs rejected, recorded so they are not re-proposed:** a plausible code set shipped unattended
  (the container is free, the vocabulary is a one-way door); codes derived from the pinned phrase
  catalogue (partial by construction); codes derived from the emission site (a refactor renames a
  published key); a cap, a truncation or a verbosity flag (all three hide findings, and the author with
  the most warnings most needs the hidden ones); a new metainfo artifact (the channel already ships and
  is outside the digest).

  **Two consequences recorded rather than left to be discovered**, both in COMPILER.md beside the
  catalogue: the code vocabulary is closed, so a consumer pinned to an older `just-dna-format` refuses
  a manifest carrying a code added later — the standing cost of every closed vocabulary on a published
  field here, and "additive" describes the writer; and `carried` holds full message text, which grows
  the channel **1.84× across the reference corpus** (1.96× on `pathogenic_clinvar`). The second is the
  shape the item decided rather than an oversight, and the three cheaper encodings are weighed as
  **RM138** instead of being taken unilaterally. → [COMPILER.md § Warning texts a consumer keys on](COMPILER.md)

- **RM124 — `overrides.csv`, an authored overlay over the derived tables.** A correction to a
  derived row now lives beside the spec rather than inside the file, so `resolution.csv`,
  `frequencies.csv`, `gene_metrics.csv`, `gene_validity.csv`, `clinical_assertions.csv`,
  `literature.csv` and `gwas_effects.csv` become pure build products — `derived = f(source, overlay)`.
  Columns are `table`, `subject`, `member`, `field`, `operation`, `value`, `reason`, `decided_by`,
  `decided_at`, with **`reason` required**: that is what makes the table a record rather than a knob.
  Operations are `update` / `insert` / `suppress`, keyed `(table, subject, member, field)` with **one
  `member` column whose meaning the named table fixes** rather than a per-table key grammar. An empty
  `member` on a grouped table is group-scoped for `update` and refused for the other two. An `insert`
  is written as several rows sharing `(table, subject, member)`, one per field, and lands at the end
  of its subject's group in overlay order, because parquet bytes depend on row order.

  **What it costs an existing module: nothing.** The table is optional, an absent optional table
  contributes nothing to `content_signature`, and a module that carries no overlay carries no
  `overrides.parquet` either, so no published module's identity moves on either axis. (Its slot in
  `ARTIFACT_PARQUETS` is not what protects them: `artifact_digest` name-sorts the listing before
  hashing, so tuple position is invisible to the digest.) The overlay is authored
  input, so when a module carries one it is inside `content_signature` and byte-hashed into
  `manifest.inputs` — editing a correction un-closes a module, which is correct.

  **What it costs a second pass: also nothing, and that is the point.** Merge-not-clobber's *behaviour*
  is unchanged — a re-run still gap-fills rather than re-asking every subject — but a recorded row now
  carries no authored content, so a full re-derivation (`rm` plus a re-run) is free. Every writer of a
  covered table says so in its docstring. `licensing.csv` / `sources.csv` is deliberately outside the
  covered set: it has its own merge path and is the one derived table a human is told to write.

  `reverse_module` emits the post-overlay derived tables **plus** the overlay, so the overlay applies
  twice and the fixed point is checked by test rather than assumed — it holds because all three
  operations are idempotent set operations, which is why there is no `previous_value` column. One
  consequence stated rather than hidden: **no operation reports its own no-op**, because after a
  reverse all three no-ops are true of a healthy module, so a `suppress` with a typo'd subject does
  nothing and cannot warn. Two warnings do exist and are pinned in
  [COMPILER § warning texts](COMPILER.md#warning-texts-a-consumer-keys-on) — an `update` reaching no
  row, and an overlay naming a table the module does not carry.

  `ProvenanceItem.outranks` still stands and the duplication is stated in
  [SCHEMAS](SCHEMAS.md#the-authored-overlay-07-rm124--overridescsv) rather than hidden; the unification
  is **RM135** on the 1.0 tracker, and 0.7 emits no deprecation warning because an author warned off
  `outranks` today has nowhere to go.

  **Cross-repo:** `just-dna-registry` needs `overrides.csv` added to `SPEC_DATA_FILES` /
  `RECOGNIZED_SPEC_FILES`, or the file is dropped on the next re-publish — the way `licensing.csv` was
  lost before their 0.16.2. Recorded in [INTEGRATION_0_6.md](history/INTEGRATION_0_6.md).

- **RM83 — closed, not shipped.** Dissolved by RM124 rather than argued down: with the corrections in
  the overlay there is nothing inside a sidecar to preserve, so the `--refresh` command it asked for
  has no problem left to solve and the drift detection it wanted falls out of an ordinary
  re-derivation. Its residue shipped as `enrich --rederive`, in RM128's entry below. See
  [ROADMAP_HISTORY](ROADMAP_HISTORY.md#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it-which-discards-the-overrides-it-exists-to-hold).


- **RM128 — an enrichment run is a transaction, and it holds a lock, reports progress, and can
  re-derive.** *(`just-dna-enricher`; no schema, no manifest field, no vocabulary — a new module, three
  keyword arguments and two flags.)* `enrich()` persisted nothing until its tail, so a run killed at
  minute 29 had written **zero bytes**. The obvious repair, checkpointing the table as it goes, trades
  away a property somebody may be relying on — that a refused `strict` run leaves the module exactly as
  it was — and the trade turned out to be unnecessary.

  **Durable staging beside the target, plus an atomic commit at the gate.** Each live link's answer is
  written to `.<name>.staging/answers.csv` beside `resolution.csv` as it arrives; the table itself is
  still written once, at the bottom, by a writer that renames into place. Same-directory staging is the
  correctness condition rather than a convenience: `os.replace` is atomic only within one filesystem,
  so staging beside the target makes a cross-device move structurally impossible instead of merely
  avoided. What is staged is the **raw answer**, never the assembled row — the hosting filter, the
  pseudoautosomal selection, `locus_index` and the minted ids all recompute — so a resumed run
  reproduces the table an uninterrupted one produces, which is the item's P7 obligation and has a test.

  **A refused `strict` run commits nothing**, now as a written promise rather than an accident of
  statement order, asserted on the bytes on disk of a pre-existing table. `--keep-staging` leaves the
  staged answers after a successful commit, for debugging; the default removes them. Not
  mode-conditional: `write` gates the persistence machinery whole, so it means one thing everywhere.

  **`flock` on the spec directory, non-blocking, no lockfile.** Two concurrent runs were
  last-writer-wins over a merge with neither knowing, and a zombie run once overwrote a restored 330-row
  table with 162 rows that then validated, closed and compiled green. A lockfile left by exactly the
  kill this item is about would block every subsequent run, and the staleness rule that would fix it is
  a clock; `flock` dies with the process. A second run refuses with a pinned message. **The degradation
  is documented, not silent** — no `fcntl`, or a filesystem answering `ENOLCK`/`EOPNOTSUPP`, logs that
  the run is not excluded from a concurrent one. `flock` is untested here on the network filesystems a
  consumer may use.

  **`progress: Callable[[int, int], None] | None`, reporting `(done, total)` over SUBJECTS.** The
  incident is an idle timeout — both reported runs died at 1800 s with essentially every variant
  resolved — so the caller needs a keepalive with monotonic progress. That rules out phases (a
  29-minute phase emits nothing) and links (whose total is unknown until resolution finds them). No
  protocol: two integers, no object, no event vocabulary to keep working forever.

  A staged answer is honoured **only if the link that produced it would run this time** — the seeding
  reads the same two booleans that gate the live blocks — so a `--no-gnomad` or `--offline` resume does
  not stamp a row a first run with those flags could never have written.

  **`--rederive` is RM83's residue, and it composes rather than adding machinery.** It re-asks every
  recorded subject and names the ones that came back different — MODULE_LIFECYCLE § 5.1's canary,
  finally performable. `None` means nobody re-derived and `[]` means nothing moved; only a real
  difference prints. **A recorded subject the sources could not be asked about keeps its rows**, or
  re-deriving would be a way to shorten the table — the reported incident wearing a new flag. The
  **A re-derivation resumes only another re-derivation**, because a gap-filling run's staged answers
  are, after its commit, exactly what produced the recorded table — seeding them would compare the
  table against its own provenance and report a clean bill for the subjects being re-checked. The
  honest limit is stated with it: `rm` plus a re-run re-derives just as correctly and reports nothing,
  because it destroys the old values before the fresh ones arrive.


- **RM126 — a release now declares what it changed about compiled output.** Principle 3, as amended
  on 2026-08-21, lets a corrected derivation ship in any release but never *silently*: each release
  declares its corrections, readable offline and without recompiling. No such channel existed, so the
  charter named a surface that was not there. This is the one item of the 0.7 round that was owed
  rather than offered.

  **`just_dna_format.release_records`** carries a static table of per-release records and a pure
  `needs_recompile(compiled_under, current)` over it — pydantic-only work in the tier every consumer
  already has. Five axes per record (`parquet_schema`, `parquet_bytes`, `content_signature`,
  `manifest_fields`, `warnings`), each tri-state, **plus the declared correction-versus-addition
  split** — the half no diff can compute, since only the person who fixed the bug knows whether the
  stored value was *wrong* (`stats.genes`) or merely *absent* (`curator`).

  **Deliberately not a `should_rebuild` verdict.** The same fact costs a registry an immutable PATCH
  and a local cache a free rebuild, so the decision is the consumer's and only the fact is ours. The
  per-axis breakdown stays exposed underneath the declared flag.

  **Intervals compose as a union over `(a, b]`**, walked down each record's `previous` link — linear
  storage rather than O(releases²), *moved-and-moved-back still reads as moved*, and, load-bearing
  rather than incidental, **the interval from a version to itself is empty**. That last property is
  what stops an unattended sweep minting a fresh PATCH every run forever, and a field-keyed or
  latest-known-defect shape would not have it.

  **Unknown is a state, never an empty result.** An interval the installed table does not cover
  answers `None` per axis under Kleene semantics, and so does a downgrade. Without it the surface
  would be worse than nothing, because a consumer would stop recompiling on the strength of a silence.

  **`compilation.warnings` gets its own axis, outside the set that drives a recompile.** It is a
  published manifest field and RM131/RM134 both move that channel in 0.7, so folding it into
  `manifest_fields` would report *a manifest field changed* on essentially every module in a catalogue
  for a reworded message. It cannot join `compiled_at` in the excluded set either, because a **new**
  warning can be a real signal. RM131's `carried` split is the discriminator that will make the two
  decidable; the seam is `sweep.compare_module`, which keeps added and removed warnings apart for it.
  `SpecRow.needs_upgrade` is computed over authored row content and a warning never touches one, so no
  warning change can flip it — verified, not assumed.

  **The roster ships beside the table** (`AUTHORED_ROW_DERIVED_FIELDS`): which manifest fields are pure
  functions of the authored rows, so a consumer can recompute the current answer from stored inputs
  with `spec_tables` and `module_stats` instead of consulting the table at all. **Its boundary is
  conditional and the condition rides on the entry**: `compile_module` re-derives `stats` over the
  survivors only when the symbolic-allele drop removed something, so a module that lost the sole row
  naming a gene legitimately disagrees with a recomputation, permanently. `compilation.dropped_rows`
  (2026-08-24) is what makes that checkable rather than merely stated.

  **`just-dna-compiler sweep`** is the instrument, and it exists so this never becomes the hand-kept
  per-release map everyone agrees it must not be — the defect wearing a public name. It compares two
  trees of compiled output built from **one** spec root, and with `--release` it runs the gate: a
  measured movement that no record declares **fails**, so the measurement forces the declaration. The
  gate belongs to the bump → `uv sync` → tag sequence rather than to the test suite, because it needs
  the previous release installed.

  **Backfilled by measurement, not by memory.** Both shipped records were produced on 2026-08-28 by
  compiling all sixteen `reference_examples/` from one spec root under each *published* 0.6 release.
  `0.6.0 → 0.6.1` moved nothing — recorded as a **measured zero with its denominator**, never silence.
  `0.6.1 → 0.6.6` moved the parquet schema and bytes on 10 of 16 (RM120's `curator` column growing
  `studies.parquet`), a published manifest field on 9 (`stats.genes`/`stats.gene_count` on seven,
  RM121; `literature.quotes_unchecked` on three, RM119) and `content_signature` on **none**. Six moved
  a published, indexed manifest field with *both* hashes byte-identical, which is precisely the case a
  digest comparison, a signature comparison and a `revalidate` all correctly call *no change*. Only
  `0.6.0`, `0.6.1` and `0.6.6` reached PyPI in that line, so those are the only intervals a stored
  artifact can name; everything older stays honestly `unknown`.

  **Scope v1 is compiler-derived outputs, said out loud.** Enricher-side outputs are **unmeasured**,
  which is not the same claim as unchanged. And this coexists with a consumer's own recomputation
  probes rather than replacing them: we state what a release did, they check what a specific stored
  artifact says, and the two fail differently.



- **RM70 — a star-allele module can state CPIC's core assumption.** *(`just-dna-format`; no compiler
  change — the parquet schema and the reverse writer both derive their columns from the model.)*
  `requires_callable` was a
  `VariantRow` column, so `haplotypes.csv`, `pharm_variants.csv` and `diplotypes.csv` had no way to
  record the one thing a consumer most needs before trusting a `*1/*1` result: CPIC assumes a position
  it did not call is reference — literally `requires_callable=false` — and the assumption lived only
  in the upstream's prose. The optional tri-state column now sits on **`HaplotypeRow` and
  `PharmVariantRow`**, the two PGx tables that *name a locus*, so the claim is about a position the
  row itself states.

  **Not on `DiplotypeRow`, and `callable_from` did not travel.** A diplotype names a star-allele pair,
  not a locus; the same column there could only mean "the variants defining these two haplotypes were
  callable", which is a fact about `haplotypes.csv` restated one table over, free to drift the moment
  a definition is edited. `callable_from` stays `VariantRow`-only because the two are different axes —
  one says a proof is required, the other says where the proof lives — and a curator can state the
  first from the source's prose with no basis for the second. Declaring it once in `module_spec.yaml`
  was refused for the reason RM36 and RM32 already paid for: the verdict is per locus, and CYP2D6
  holds a SNP-defined allele beside a structurally-defined one inside one gene.

  `reference_examples/cyp2c9_warfarin_grch37` — the module the gap was found against — now populates
  the column on both tables and exercises all three states. Its `haplotypes.csv` records CPIC's
  assumption verbatim (`false` on both defining SNPs); its `pharm_variants.csv` is keyed on genotype
  and so splits: the reference-homozygote rows require a callability proof, the rows naming an
  alternate allele do not, and the rows whose reference allele the module never resolved are left
  **blank** rather than guessed. That answers the consumer ask for `requires_callable` "populated
  somewhere real, to try the round trip against" on its PGx half. The module was re-closed, so its
  attestation binds the new bytes.

  Optional with respect to every module published before it: `content_signature` normalizes with
  `exclude_none`, so a spec that never writes the column hashes exactly as it did. `artifact.digest`
  does move for any module carrying either table, which P3 says is not by itself a reason to defer.

- **RM133 — the card subtitle gets a home a registry can amend.** *(`just-dna-format`; Principle 4 deliberately untouched — the closure binding is exactly what it was.)*

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

- **RM71 — the drafted-genotype worklist is re-requestable from the command that produced it.**
  `draft-panel` leaves `genotype` as the placeholder, correctly, and reports the alleles the author
  must write it from in one uncapped line per open row. That report used to be scoped to the rows a
  single run *added*, so a second run added nothing and therefore said nothing, and the alleles could
  not be asked for again. The worklist now covers **every row in `variants.csv` whose `genotype` is
  still the placeholder** — refused rows were never written and settled rows no longer carry the stub,
  so the earlier narrowing survives on a better basis — and `draft-panel --dry-run` obtains it without
  appending anything, meaning what it means on `draft`. The `state`-placeholder line moves with it,
  because it reads as "these rows *also*". An open row this run holds no record for has its alleles
  **withheld** and is named by gene in one aggregated line rather than guessed at or silently dropped
  from the count; the line says only that nothing this run selected covers them, since the usual causes
  (another gene, a tighter `--clin-sig`/`--min-review-stars`) are not ones the pass establishes. A
  scaffolded template row — the placeholder in `rsid` as well as `genotype` — is not drafting work and
  stays out of both lists. No schema, no cell filled,
  no digest moved. The 0.7 proposal recorded `draft-panel` as *lacking* `--dry-run`; it has had one
  since 0.5.1, so that half of the item was already true and is now pinned by a test over the whole
  drafting family rather than asserted.

- **RM134 § A — the PubMind snapshot, and one significance normalizer.** *(`just-dna-enricher`; nothing in the format or compiler tiers moves and the compile path imports none of it.)*

  **Package: `just-dna-enricher`.** Additive: a new module, a new snapshot kind and two new commands.
  Nothing in the format or compiler tiers moves, no schema field is added, removed, promoted or retyped,
  and the compile path imports none of it. Decided in
  [PROPOSAL_0_7 § RM134](proposals/PROPOSAL_0_7.md); the evidence is
  [PUBMIND_ASSESSMENT.md](PUBMIND_ASSESSMENT.md).

  - **`clin_sig.normalize_clin_sig` is now the one raw-significance → `VALID_CLIN_SIG` fold**, moved out
    of `clinvar_build._normalize_clin_sig`, and **two defects were fixed on the way out**. Its map keys
    are underscored because that is ClinVar's spelling; PubMind spells the same concepts with spaces, so
    `Uncertain significance` and `Conflicting` both fell through to `other` while ClinVar's
    `Uncertain_significance` and `Conflicting_classifications_of_pathogenicity` mapped correctly — two
    sources that agree, reported as disagreeing. Repaired with a whitespace→underscore step in the
    tokenizer (an identity on every existing key) and a bare `conflicting` key. **No ClinVar answer
    changes**, which is asserted as an equality over the walked map rather than spot-checked. A second
    hand-written map was the rejected repair: the concordance check RM134 § B builds compares two
    *normalized* calls, so a drift between two maps would report a disagreement between our own tables.
  - **A whitespace-only or token-less significance value is now `not_provided`, not `other`.** "The source
    states no classification" and "the source stated something we do not model" are different answers and
    only the second is a disagreement. No ClinVar `CLNSIG` takes that shape, so nothing built to date
    moves.
  - **New: `just-dna-enricher pubmind build`** (`[dev]`, `polars`) — the ANNOVAR-redistributed
    `hg38_pubmind_db.txt.gz` → `data/pubmind.parquet` + `release.json`, byte-reproducible across rebuilds.
    Columns are `chrom, start, ref, alt, pvid, clin_sig, clin_sig_raw, pathogenicity_score, confidence,
    derivation`; the significance names are **unprefixed**, matching the ClinVar snapshot, because one
    column vocabulary across every snapshot is what lets a later check read N authorities with no
    per-source mapping. `pathogenicity_score` is nullable and null means *not computed*, never 0.0;
    `confidence` is PubMind's own 0–3 and is deliberately not normalized against `review_stars`.
  - **Every dropped row is counted, as an equality over a walked registry.**
    `input_rows == record_count + sum(dropped.values())` over `PUBMIND_DROP_REASONS` — `off_target_chrom`,
    `non_acgt`, `ref_equals_alt`, `multi_substitution`, `identical_duplicate`. A codon block differing at
    exactly one base is decomposed onto it (`derivation=codon`); one needing two or three simultaneous
    changes is dropped, because it asserts a change to the protein rather than to a genotypable position.
    Length-changing rows are kept and stamped `derivation=indel`: upstream left-normalization is
    unverified, and a consumer must be able to exclude them without re-deriving why.
  - **A bad cell and a bad row are different outcomes.** A row with no PVID or an unreadable `Start` is
    dropped and counted (`no_pvid`, `unparsable_position`) — the PVID is the record id everything here is
    keyed on, and a null one would have merged distinct records under `identical_duplicate` as well as
    crashing the emit sort. A malformed `pathogenicity_score` or `confidence` withholds *that value* and
    keeps the row, counted in `unparsable_score` / `unparsable_confidence`. `NaN` and `inf` count as
    unparsable rather than being stored (`float()` accepts both), and a non-integral confidence is
    withheld rather than truncated to a count the source never stated.
  - **`download_pubmind_table` raises `PubMindUnavailable`**, a subclass of `PubMindBuildError`, so a
    moved bulk URL surfaces as this tier's type rather than `httpx`'s and one `except` arm covers both an
    outage and a malformed table. The subclass makes a caller's `except` order load-bearing.
  - **A contested coordinate keeps every PVID as its own row.** Consolidation into a PVID is keyed on the
    text the model extracted, never on a coordinate, so one variant fragments into records whose verdicts
    disagree. Collapsing them was rejected: it needs an ordering nobody defined, which is `mode()` over an
    unsorted group. `release.json` records `multi_pvid_keys`, `max_pvids_per_key` and `contested_keys`.
  - **New: `just-dna-enricher pubmind publish`, which refuses and says why.** On the PharmVar precedent,
    with a different reason: PharmVar's bytes arrive under terms that bar passing them on, PubMind's under
    **no stated data terms at all**. The command exists rather than being absent, because a missing command
    reads as an oversight somebody will helpfully add. The refusal text is pinned by a test.
  - **`PUBMIND_TERMS` records `None` on every licence axis**, and the nulls are load-bearing: null means
    *the terms could not be established*. Unknown terms **warn and never gate** — `taints_commercial_use`
    requires `commercial_use is False` — so a module carrying PubMind values compiles, lands `pubmind` in
    `manifest.sources.unknown_terms_sources`, and drives the module-wide verdict to `None`: undetermined,
    never permitted. That is also why `pubmind build` has **no `--use` flag**: `check_declared_use` returns
    a skip for every declaration, so the gate would refuse every build and the flag would do nothing.
  - **New cache: `pubmind/`, `$JUST_DNA_PUBMIND_CACHE`**, with `resolve_pubmind_reference` and
    `default_pubmind_cache_dir` and deliberately **no `ensure_pubmind_snapshot`** — a refused publish means
    no repo to provision from. `cache status` lists it as build-your-own.
  - **Fixed a counted-prose assertion that a correct addition broke.**
    `test_every_resolver_and_default_dir_takes_the_off_switch` asserted `len(named) == 12` with "expected
    six resolvers and six default dirs" in its message, so the seventh snapshot failed it on arithmetic.
    It now asserts an equality between the two walked families keyed by snapshot name, which says
    something the count never did: no resolver is missing its default directory and none is orphaned.

  **Still open, and named rather than implied.** The ANNOVAR-distributed table's data terms are
  unestablished and only CHOP can settle them; the unblock action is to ask WGLab and CHOP's Office of
  Technology Transfer in writing. Whether the indel rows are left-normalized is likewise unestablished,
  which is what `derivation=indel` exists to let a consumer act on.

- **RM134 §§ C and D — drafting from PubMind, and the hint.** *(`just-dna-enricher`; nothing in the format or compiler tiers moves and the compile path imports none of it.)*

  **Package: `just-dna-enricher`.** Additive: one flag and two options on an existing command, one
  option on `hint variant`, a new provider module and a fourth `DRAFT_PROJECTIONS` entry. No schema
  field is added, removed, promoted or retyped, and no published module is invalidated. Decided in
  [PROPOSAL_0_7 § RM134](proposals/PROPOSAL_0_7.md); the evidence is
  [PUBMIND_ASSESSMENT.md](PUBMIND_ASSESSMENT.md).

  - **New: `just-dna-enricher draft-panel --source pubmind`** — a flag on the existing command rather
    than a `draft-pubmind` beside it. The two write the same rows into the same table from the same
    gene argument, so a twin command would carry a second copy of the genotype worklist, the
    placeholder guard, the dedup pass and the refusal summary — the four parts that are hard to get
    right. `pubmind_draft` therefore **imports** the ClinVar provider's machinery, `_open_stubs`
    included: scoping the worklist to `report.added` is the once-only defect RM71 removed in this same
    release, and a second copy of that rule is the one that goes stale. `draft-clinpgx` stays separate
    because it writes *different* tables.
  - **The gene map is ClinVar's own per-record attribution, matched at the exact position.** PubMind
    names no gene, so `--gene BRCA1` needs a gene→locus map, and this repo deliberately holds none —
    the compiler's gene/locus check is chromosome-granular for that reason. Every position ClinVar
    records for the gene is the universe, with **no** clinical or review filter, because filtering the
    map would narrow what PubMind is asked about while looking like a filter on PubMind's calls. A
    min/max span was rejected: it invents a boundary nobody defined and writes a `gene` cell that is a
    false claim wherever two genes overlap. Both snapshots are required and each absence names its own
    switch. The cost is stated rather than counted — **a PubMind verdict at a position ClinVar has no
    record for cannot be reached by gene at all**, and that class is not countable, since attributing
    it to a gene is exactly what there is no map for.
  - **Five withheld classes, each named at draft time, and the accounting is an equality over the
    walked reason set.** `PUBMIND_WITHHELD_REASONS` covers a contested key, a length-changing row, a
    call outside `--clin-sig`, a confidence below `--min-confidence`, and a confidence the source never
    stated — that last one its own class, because `None` is not 0 and reading an unstated confidence as
    0 invents a reading. `candidates == drafted + Σ withheld` holds over the set, and a class that
    withheld nothing reports no zero.
  - **Contestation is decided over every PVID at the key, before either dial runs.** A `--clin-sig` or
    `--min-confidence` applied first would remove the dissenting record and pick the winner exactly as
    the `mode()` this design already refused would; a test constructs a dissenter that either dial
    alone would have hidden. Where the records agree, one row is written and the record count, the
    PVIDs and the best stated confidence stay in the transcription.
  - **Identity is the whole coordinate or nothing**, since the snapshot has no rsID column at all — and
    the row still matches on the same five columns a ClinVar-drafted row does, so a coordinate both
    sources speak about is one row rather than two. No `clinvar`, `pathogenic` or `benign` is folded:
    all three are ClinVar flags by their own field descriptions, and a position appearing in ClinVar's
    gene map says nothing about whether *this allele* is in ClinVar. No `studies.csv` row is drafted —
    the ANNOVAR channel carries no PMID — and the run says so, because that table is mandatory. A
    position two requested genes both claim leaves `gene` **empty**, counted and named: a joined
    `BRCA1, BRCA2` is not a symbol `check-identifiers` resolves, and picking one is the gene model the
    pass went to ClinVar to avoid inventing.
  - **New: `pubmind` in `DRAFT_PROJECTIONS`**, projected onto `clin_sig`, so a module drafted from
    PubMind cannot confirm itself when the concordance check reads the same column (`@draft-digest`).
    Its `identity` is the coordinate and **not** the provider's `match_on`: the source states no
    rs-number, so an rs-number an author adds later is a change to the row's spelling, not to the call.
  - **Unknown terms warn and never gate, and the drafter does not call the acquisition gate.**
    `check_declared_use` decides whether a *fetch* may proceed and skips on unknown terms, which is
    right for a pass that would go and get such data. Nothing is fetched here — there is deliberately
    no `ensure_pubmind_snapshot`, the operator built the snapshot with our own command, and refusing to
    read it would make that command's output a file nothing may consume. The reason is reported in the
    source's own words instead, and the licence row the provider writes carries `None` on every term,
    which does not taint: `taints_commercial_use` requires an explicit `False`. That is § A's finding,
    re-asserted here over the row this provider actually writes rather than trusted from a fixture.
  - **New: `just-dna-enricher hint variant --pubmind-cache`** (§ D) — PubMind's records beside the cell
    an author is about to fill, **never filling it**: `clin_sig` is what the concordance check
    cross-examines, so a hint supplying it from one of the authorities being compared would make the
    check agree with the source it is checking (`@hint-redundancy-bearing`). Three states rather than
    two: no snapshot is *nobody asked* and names `$JUST_DNA_PUBMIND_CACHE`, a snapshot holding nothing
    at the allele is an absence in their corpus, and disagreeing records are all reported with none
    picked. It answers for a coordinate the caller typed as well as one an rsID resolved to, because
    their channel is coordinate-keyed and most of its rows carry no rs-number.
  - **A dial belonging to the other authority is named rather than ignored.** `--min-review-stars` and
    `--max-citations` under `--source pubmind`, and `--min-confidence` under `--source clinvar`, warn
    when set away from their default: a run that honoured neither the flag nor the author's
    expectation is the failure worth reporting before it happens.

- **RM132 — `pharm_variants.csv` can cite the evidence for its own claim.** *(`just-dna-format` +
  `just-dna-compiler` + `just-dna-enricher`; a new optional authored column, additive under Principles
  3 and 8, and no published module is invalidated.)*

  A ClinPGx-drafted module carried **1,482** drug-response rows and had nowhere to ground any of them:
  sixteen model fields, thirteen authored, none a PMID or DOI. `studies.csv` cannot close it, and that
  is structural rather than an oversight — a study row keys on `(variant_key, pmid)` and attaches to
  the **variant**, while a `pharm_variants.csv` row keys on
  `(variant_key, drug, genotype, phenotype_category, annotation_id)`, so one study row would attach
  the paper to every drug, genotype and phenotype category recorded for that variant at once.
  Widening `studies.csv`'s key was refused for the reason RM47 already refused it: it would make a
  study row's subject depend on which table read it. `evidence_level` is not the handle either — it
  points at somebody else's *grading of* the evidence rather than at the evidence — and the licence
  row's `source`/`dataset` state redistribution terms rather than grounding a claim.

  **`PharmVariantRow.pmid`**, optional and free-form under the one grammar `spec.validate_pmid_cell`
  owns, so an author who has met `StudyRow.pmid` or `MeasureBinRow.pmid` learns nothing new. That is
  why a full-cost authored column (P9) is taken here rather than deferred for demand: demand fixes an
  *unfixed* shape, and RM47 fixed this one a release ago for a structurally identical table.

  **`provenance_quote` does not follow, and the release says so rather than leaving it implied.** The
  row cites; `studies.csv` and `literature.csv` describe. That is the line that stops `StudyRow`'s
  whole provenance column set — population, `p_value_num`, `effect_size`, `provenance_quote`,
  `curator` — migrating onto a citing row one column at a time, and a body of clinical claims this
  size is exactly where the question gets asked next.

  **Both literature cross-check sites learned the site in this release**, which is RM47's recorded
  lesson in its own words: a column shipped without them would make every citation from it read as a
  stale orphan in one direction and be invisible in the other. `_cross_check_literature` (with
  `split_cited_literature` and `_check_quote_counter_is_current` beneath it) and the enricher's
  `enrich_literature` both read it, so a pharm-grounded citation is checked for existence and
  identifiers exactly like a study-grounded one — and a module whose only citations are pharm pointers
  is now enriched rather than refused.

  **The roster is derived, so there will not be a fourth round of this.** `_CITING_TABLE_KINDS` is
  every `_TABLE_KINDS` model declaring a `pmid`, and the new public
  `load_citing_rows` / `table_citations` walk it — the pair the enricher reads through, so a second
  copy of the table roster in that tier (the RM40/RM41 shape) is not repeated, and a test walks the
  enricher's own source with `ast` to assert none is kept. `load_binning_rows` / `binning_citations`
  stay and stay narrow: a caller asking for the binning kinds is asking about thresholds, not about
  the citations a module makes. The internal third parameter of `split_cited_literature` is renamed
  `bin_rows` → `kind_rows` to match what it always held.

  **One warning text moved, deliberately**: `literature_row_uncited` now reads *"no study, bin or
  pharm row in this module cites"*. The **code** is the stable handle and is unchanged; the phrase is
  pinned by the suite, which is what makes the rewording a deliberate act rather than a drift.

  Optionality is proved by running it rather than by citing `exclude_none`: a spec carrying no `pmid`
  header hashes to the same `content_signature` as the same spec carrying the header with every cell
  empty, and a filled cell moves it. The round trip is asserted on the `pharm_variants.parquet` bytes
  as well as on both identities.

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
**[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)
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
stale. **[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)**
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

---

**Older entries are in two archives, both cut at a release boundary rather than a date.** Entries that
shipped in a 0.6 number are in [CHANGELOG_0_6.md](history/CHANGELOG_0_6.md), split out on 2026-09-12 at
the `v0.6.6` tag — four entries dated 2026-08-21 shipped in 0.7.0 and stay above, which is why the cut
was read off `git show` and not off the dates. Entries dated 2026-08-11 and earlier — the whole 0.5
line and everything before it — are in [CHANGELOG_PRE_0_6.md](history/CHANGELOG_PRE_0_6.md). Neither
split is a change of format: each archive is this same document continued downward.
