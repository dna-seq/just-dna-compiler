# The module lifecycle

How a module comes into existence, how it reaches a consumer, and — the half nothing else here
describes — **what happens the second, third and twenty-fifth time somebody opens it again.**

## 1. What this document is, and what it is not

This repository documents its tiers by *surface*: [SCHEMAS.md](SCHEMAS.md) is the schema contract,
[COMPILER.md](COMPILER.md) the transform, [ENRICHER.md](ENRICHER.md) the network tier. Each answers
"what does this package do". None answers **"what happens to a module over time, and who touches it
at each point"**, and the gap is not cosmetic: the whole of our dogfooding has been *ground zero → a
compiled module*, once, and the second pass has therefore never been written down at all. Everything
about a v2 — which files may be re-run, which must be deleted first, which identities move, what the
registry will and will not let you do, what a consumer sees — exists today only as an implication of
rules stated for other reasons, scattered across five documents and three repositories.

So this document does two things:

1. **States pass one explicitly** as a sequence of stages, naming the surface each stage touches.
   The *procedure* is not here — that is `just-module-creator`, whose `/create-module` skill is the
   door into its stage skills. What is here is the **map**: actor, tier, inputs, outputs, and the identity
   consequences, for a reader who needs to reason about the pipeline rather than walk it.
2. **Describes pass two onward**, which no document currently covers.

It is explorative. Where the lifecycle is designed but has never been run end to end, §8 says so
rather than letting the prose imply otherwise.

**Not an authoring guide.** It teaches no column, no vocabulary and no table choice. If a sentence
here starts explaining what to put in a cell, it has drifted into the skill's job and should be cut.

## 2. The cast — six surfaces, and which one owns which stage

The dependency arrow points inward and only one tier fetches.

| Surface | Repo / package | Owns | Never |
|---|---|---|---|
| **schema** | `just-dna-format` | the models, vocabularies, the hash family, `layout`, signing/verification helpers, the generated authoring reference | fetches; ships a CLI |
| **transform** | `just-dna-compiler` | spec → parquet + `manifest.json`; `validate`, `reverse`, `close`, `signature`, scaffolding/templates, `hint`, the authoring-reference CLI | fetches; creates a row no curator wrote |
| **network** | `just-dna-enricher` | resolution, VRS minting, the derived sidecars, the drafting providers, every cross-check, snapshot build/publish | decides what a variant *means*; repairs an authored cell |
| **catalog** | `just-dna-registry` (checkout: `../just-dna-marketplace`) | accounts, namespaces, publish, search, download, the module card, recompilation server-side | authors anything |
| **agent surface** | `just-module-creator` | the MCP tool set and its stage skills, entered through `/create-module` — the procedure, and the refusals that keep an agent from filling a checked cell | own a schema fact |
| **consumer** | `just-dna-lite` and any other reader | joining the module's annotation against a sample's measurement | supply the annotation |

Two of those are outside this repository's control and are described here as consumers of what we
publish, not as things we specify.

## 3. The chart

```
 0 origin
 (idea, gap, paper, a handed source)
    │
    ▼
 1 scaffold ─▶ 2 draft ──▶ 3 curate ──▶ 4 enrich ─▶ 5 cross-check ─▶ 6 compile ─▶ 7 rehearse ─▶ 8 publish
 (spec dir)    (source      (authored:   (network:   (report-only,     verify      (polygon)    (immutable)
                rows,        an agent,    sidecars)   never repair)     sign                         │
                stubs)       a human,                                   close                        │
                             or both)                                                                ▼
                                                                                             9 install & join
                                                                                                 (consumer)
                                                                                                      │
  ┌────────────────────────── 10 feedback ◀────────────────────────────────────────────────────────────┘
  │   a finding · a new paper · a review · a source release · a tightened contract
  │
  └─▶ pass 2+ re-enters at ─┬─ 3 curate    ← the usual case: rows, conclusions, evidence, a review
                            ├─ 2 draft     ← a source refresh
                            ├─ 1 scaffold  ← adding a table kind the module did not carry
                            └─ 6 compile   ← a rebuild under a newer toolchain, nothing authored changed
```

Steps 4 and 5 are the only ones that use the network on the authoring side; step 8 is the only one
that leaves the machine. Once `resolution.csv` and `literature.csv` exist, every later compile is
offline and reproducible — that is what makes 6 replayable without 4.

**Pass two normally re-enters at 3, not at 1**, and that is the difference between the loop and the
line. Stages 1 and 2 create files; stage 3 is where a module is *worked on*, and most second passes
are exactly that — a conclusion reworded, a row added, evidence relocated, a reviewer recorded. The
other three entry points are the special cases the arrows name. What no pass re-enters at is 0: **a
second pass never starts from nothing.** It starts from a spec directory already carrying authored
rows, machine-written sidecars that will merge rather than refresh, an attestation bound to specific
bytes, and — if it was published — an immutable predecessor with a permanent claim on its content.
Which of those a given edit invalidates is §6.

## 4. Pass one, stage by stage

| # | Stage | Actor | Surface touched | Reads | Writes | Can refuse |
|---|---|---|---|---|---|---|
| 0 | origin | human + agent | registry search; literature search | the catalog, the sources | nothing | — |
| 1 | scaffold | agent | compiler `scaffold`/`template`/`stub`/`requirements`/`describe`; format `reference` | the models | `module_spec.yaml`, empty/stubbed CSVs | never overwrites |
| 2 | draft | agent | enricher drafting providers (over compiler `draft.append_rows`) | a source or its snapshot | authored CSV rows + a licence-table row | licence gate at acquisition |
| 3 | curate | the author — an agent, a human, or both | compiler `hint`, enricher `hint`/`literature` — all report-only | the drafted rows, papers | the cells nothing else may fill | — |
| 4 | enrich | agent | enricher passes | authored tables + caches/snapshots/live | the derived sidecars | `strict` refuses unresolved |
| 5 | cross-check | agent | enricher checks | authored cells vs sources | findings, `verification.json` | `strict` escalates most findings |
| 6 | compile | anyone | compiler `validate`/`compile`/`verify`/`sign`/`close` | the whole spec dir | the artifact + `manifest.json` | the licence gate, the mode ladder |
| 7 | rehearse | agent | registry, polygon instance | the spec dir | a deletable published version | the server's own gates |
| 8 | publish | human decision | registry, production | the spec dir | an immutable version | duplicate-content claim |
| 9 | install & join | consumer | format (verify) + the artifact | the artifact | a report | signature/digest mismatch |
| 10 | feedback | anyone | — | the world | a reason to re-open | — |

### Stage 0 — origin

Four honest starting points, and they differ in what pass two will look like. A module drafted from
a source (ClinVar, CPIC, ClinPGx, CIViC, PubMind, STRchive, MITOMAP — `draft`, `draft-clinpgx`,
`draft-panel --source …`, `draft-repeats`) inherits that source's release cadence and will need a
**source-refresh pass**; a module built from one paper the author read inherits the *literature's*
cadence and will need an **evidence pass** when the preprint is published or a replication lands.
That is the first thing this document can say that nothing else does: **the origin picks the shape
of the second pass**, and it is worth recording in the module's own README at the time.

### Stage 1 — scaffold

Only `module_spec.yaml` is always present. Everything else is a table kind the module opted into,
and scaffolding is re-runnable: adding a table kind later is the same call again, which is already a
pass-two mechanism sitting inside a pass-one stage.

### Stage 2 — draft

Drafting **appends and never rewrites**. A row whose key already exists comes back reported
(`already_present` / `differs`), never overwritten. That rule is what makes the drafting stage safe
to re-enter on pass two — it is the one stage designed for repetition from the start — and it is
also why drift on an existing row is a *cross-check's* finding rather than a draft's edit.

### Stage 3 — curate

**The line here is tool-filled versus authored, not machine versus human.** A module written entirely
by an agent is a normal artifact, not a compromise: an AI co-author does the triage, the rows, the
conclusions and the located passages, and `authorship` records that it did (`kind: [ai, agent]`). What
the rules below forbid is a *tool* writing a cell that a *check* will later compare — a provider or a
lookup silently applying a value — which is a different thing from an author, of whatever kind,
deciding it.

The cells no tool fills: `genotype` (sources publish alleles, not genotypes), `state` where the
record is uncertain, `weight`/`direction`/`effect_size`, `trait_efo_id`, `conclusion`, and the two
provenance locators.

**Where a machine-held effect size goes instead (0.6, RM90).** This rule is the one a consumer asked to
have relaxed — fill `weight` from a GWAS effect where the authored cell is null — and the answer is a
table rather than an exception. `gwas_effects.csv` records the Catalog's published effects beside the
authored column, with their units, their effect alleles and their traits; `weights.parquet.weight`
stays 100% authored, and a consumer chooses one source or the other wholesale rather than blending row
by row. A per-row precedence rule was refused for the same reason the fill was: it puts two
methodologies in one summable column, and leaves the module with no single scale left to declare
(`module_spec.yaml`'s `weighting:` block, RM92, is where it declares one). Two of the toolchain's standing rules live here and both bear on later passes:

- **Never fill a cell from the source that checks it.** The redundancy-bearing set exists so that a
  Class-2 check compares two independently produced values. Filling one from the other does not fail
  — it *agrees*, permanently.
- **A blank cell is "unknown", never "no".** Tri-state is the house algebra, and a later pass that
  "tidies" a blank into `false` has changed a claim, not a formatting choice.

### Stage 4 — enrich

The only tier that fetches. Every pass here writes a **derived sidecar** beside the spec, and every
one of them is **merge-not-clobber**: an existing row wins, because a human may legitimately have
overridden it. The consequence for pass two is large enough to have its own section (§6.3).

### Stage 5 — cross-check

Every check **reports and never repairs** — rewriting an authored value destroys the evidence of the
upstream mistake. Severity follows the mode, with named exceptions that never escalate because
escalating would make the format arbitrate a dispute it has no standing in (the ClinVar `clin_sig`
comparison, the allele-function comparison, the article-licence warning, and since 0.7 the repeat-band
comparison against STRchive, the regulator-label comparison, the published-refutation finding and the
evidence-status currency finding — a source disagreeing with itself or re-curating is not an authoring
error). The roster of checks is the table at the top of ENRICHER.md and the
`VALID_VERIFICATION_CHECKS` vocabulary behind it; it grew by seven members in the 2026-09 adoption
round (PGS accession and metadata, repeat bands, literature coverage, regulator labels, published
refutation, evidence-status currency), and this document does not restate it.

Since 0.6 the outcome of this stage can outlive the run: `verification.json` records, per check, what
was checked, how many subjects, how many findings, and — when a check did **not** run — the reason.
Two counts, never a boolean, because "ran and found nothing" and "never ran" are different
statements.

### Stage 6 — compile, verify, sign, close

`validate` refuses everything `compile` refuses that does not need resolved rows, so a green
pre-flight in the *same mode* should mean a green compile. `compile` writes the parquet set and
`manifest.json`. `verify` re-hashes the files and recomputes the digest. `sign` is a detached Ed25519
signature over `artifact.digest`. `close` — new in 0.6 — writes the closure into `verification.json`,
which is the only record anywhere that says *a human declared these bytes final* rather than *a tool
ran*.

`close` is deliberately its own command: `validate` stays read-only however cleanly it passes,
because a record stamped by whatever happened to execute attests nothing.

### Stages 7–8 — rehearse, then publish

Two instances, `REGISTRY_MODE` `prod` or `test`, separate databases, separate accounts and tokens.
Exactly three behaviours differ and nothing else does: the polygon accepts `test-`/`test_` names
without a flag, it scopes the duplicate-content check to the publishing account, and it serves the
two `DELETE` routes production does not mount.

The publisher uploads **the spec, never the parquets** — `module_spec.yaml`, the authored CSVs, the
derived sidecars, `README.md`, a logo, logs. The server then **enriches, strict-compiles and stores**
it itself (`compiled_by="marketplace-server"`), which is why a published digest is trusted rather
than claimed. It fills the identity fields the module must not author — `namespace`, `owner`,
`version`, `canonical_id`, `published_at`, `license` — and strips those keys out of an uploaded
`module_spec.yaml` on every path, so a downloaded module is republishable as itself.

Three pre-flight calls exist and cost nothing: a local `content_signature` lookup (is this data
already published, under any name), `validate` (server gates, no network), and `check` (adds the
network tier). `would_publish_module_level` composes three gates only and means *nothing
module-level blocks this*, never *this will publish*.

**And on one scenario it is not merely weaker than the gate, it disagrees with it** — found by reading
the registry on 2026-08-16, in the course of settling §6.6, and **fixed there in 0.16.0** — so what
follows is the shape of a defect that is closed, kept because the reasoning is what a publisher should
still hold. Publishing a later version whose data is unchanged (a review pass, the commonest case there
is) is **allowed** by the gate, which carves out *"a collision under the same module"* by comparing
`(namespace, name)`. The pre-flight computed the same lookup with **no carve-out at all**, and the
namespace was never threaded into it, so it reported `published_as: [the predecessor]` and
`would_publish: false` for a publish that then succeeded. A publisher branching on that field — the
field the API docs say to branch on — refused its own legal publish. Recorded as an ask to the registry
in [RM86](history/ROADMAP_0_7.md#rm86--a-review-pass-is-legal-at-the-gate-refused-by-the-pre-flight-and-invisible-once-published);
their own test file stated the standard it violated, and the repair added `published_elsewhere` so the
verdict quantifies over what the gate actually refuses. **Branch on `would_publish` against a current
registry; a deployment older than 0.16.0 will still refuse a legal review publish.**

The irreversibility is the point of the rehearsal. On production a version is immutable, and the
authored data is claimed by a name-independent content hash that **`yank` does not release** — so a
botched publish spends the version number *and* the right to publish that data under any other name.

### Stage 9 — install and join

The consumer's obligation is normative and stated in [SCHEMAS.md § the consumer join contract](SCHEMAS.md#the-consumer-join-contract--three-states-and-the-one-that-gets-collapsed):
a conforming consumer distinguishes a covered reference call from a no-call, and never reads absence
from a variant-only callset as hom-reference. The module supplies the table; the consumer supplies
the measurement and the callability.

## 5. What moves what — the identity ledger

Everything in §6 depends on this table, so it comes first. Nine hashes, two of them structural.

| Identity | Covers | Moved by | **Not** moved by |
|---|---|---|---|
| `artifact.digest` | Merkle root over the compiled parquet set | any parquet byte: a row edit, a row reorder, a new sidecar parquet, a re-stamped `draft_digest`, a different compiler/polars version | `manifest.json` itself, `authorship`, README, logo, `verification.json` |
| `content_signature` | the authored rows, order-independent, `exclude_none`, plus a non-default `genome_build` | an authored cell, a new row, a changed build declaration | row order, module name/display, the resolving reference, a recompile, `fetched_at`, a new *unset* optional column |
| `resolution_signature` | the resolution **facts** only | a changed coordinate/allele/build/locus_index | who resolved it, when, or through which link |
| `frequency` / `gene_metrics` / `literature` / `gene_validity` / `clinical_assertions` / `source` signatures | each sidecar's own fact set | a changed fact | provenance columns, `fetched_at`, `is_open_access`, `rsid_current` |

Three readings that this document exists to make explicit, because each has cost somebody a day:

- **A moved `artifact.digest` beside an unmoved `content_signature` says the change was below the
  authored layer — it does not say the change was cosmetic.** Key a dedup surface on
  `content_signature` and a "these exact bytes" claim on `artifact.digest`, then localize with the
  fact signatures (§5.1). This pairing is the canary, not the noise.
- **`fetched_at` is written once per row and no merge restamps it** — so it already behaves the way
  an `updated_at` would, and the name is the only thing that still says otherwise. Its own field
  description is accurate: *"when this row was last written by a pass, not when the source published
  anything"*. The merge is `setdefault`, measured — `record_source_terms` twice against one spec
  leaves the file byte-identical; **only deleting it re-stamps.** This is
  [S7](history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md#s7--sourcescsv-stamps-fetched_at-into-the-digest-so-a-rebuild-is-never-reproducible),
  answered as a non-issue in 0.5.4 with the same probe — which settled the *behaviour* question and
  left the naming one unasked. It is asked now: the rename is planned in
  [ROADMAP § the 1.0 cleanup](ROADMAP.md#fetched_at--the-column-says-fetch-the-value-means-write),
  major-only (a column rename is a removal plus an addition under P3) and dispositioned to **ride
  along with the `sources.parquet` rename** rather than to spend a digest move of its own.
- **Reproducibility identity is a triple**: `(content_signature, resolution_signature,
  compiler_version) ⟹ artifact.digest`. A holder of the two small CSVs reproduces the artifact
  byte-for-byte, offline. That is what makes stage 6 replayable on pass two without re-running
  stage 4.

One more thing an edit can move, and it is not an identity at all: `verification.json`'s
`module_hash`, which binds the **bytes** of the authored files (`authored_input_entries` —
`module_spec.yaml`, `variants.csv`, `studies.csv`, the nine table kinds), read with `\r\n` as `\n`
since 0.6 (RM82) and otherwise byte for byte. Because it hashes bytes rather than content, it does not
move with either identity, in either direction. §6.2 measures both ways round.

### 5.1 Reading a digest move — the canary

The pairing above is a **diagnostic instrument**, and it is the only one this format has for detecting
that the world moved under a module. Read it as a decision tree, not as a single bit:

| `content_signature` | a fact signature | `artifact.digest` | what happened |
|---|---|---|---|
| same | same | same | nothing; a recompile |
| same | same | **moved** | you deleted a sidecar and re-derived it against an unchanged source (fresh `fetched_at`, same facts), or the toolchain moved under you. Both are things *you* did |
| same | **moved** | moved | **the canary. Nobody authored anything and a derived fact changed — the upstream source said something different this time** |
| **moved** | any | moved | somebody edited the module |

The fact signatures are one per derived table and each is published in its own manifest block:
`compilation.resolution_signature`, and `signature` inside `frequency` / `gene_metrics` /
`literature` / `gene_validity` / `clinical_assertions` / `sources`. Absent blocks mean the module
carries no such table. A worked read, from `reference_examples/hfe_hemochromatosis`:
`content_signature sha256:44ad4449…`, `resolution_signature sha256:9717cdda…`,
`sources.signature sha256:b79154f1…`, everything else absent — three numbers to watch, not nine.

`dataset` is deliberately **inside** `SOURCE_FACT_FIELDS`, so a module that gets widened from a newer
snapshot has its blanked release label show up as a moved `source_signature` rather than as a silent
byte. `draft_digest` is deliberately **outside** it, so a re-stamp lands in row 2 of the table above.
Both placements are what make the rows distinguishable.

**Row 2 is narrower than it looks, and the elimination is the useful part.** "Content unchanged,
timestamp moved" has no instantiation on an ordinary run, because the two conditions cannot both
hold: a merge that finds the row already recorded rewrites nothing (so the stamp does not move), and
a merge that records something new adds a fact (so a signature *does* move). `draft_digest` is the
same — it is re-stamped only by a provider that appended rows, which moves `content_signature`
anyway. Measured across the three states:

| | `fetched_at` | `source_signature` |
|---|---|---|
| initial write | `2026-08-16T02:02:24Z` | `sha256:b79154f1…` |
| plain re-run | **unchanged** | unchanged |
| delete, then re-derive against an unchanged source | `…02:02:27Z` — **moved** | unchanged |

So row 2 is reachable by exactly two routes — **a delete-and-re-derive, and a toolchain change** —
and both are deliberate acts by the holder of the module. Nothing upstream can produce it. That makes
row 3 the only row that means *the world moved*, which is what the canary is for.

**And the canary is an operation, not a passive signal.** Merge-not-clobber means a re-run never
re-asks about a row already recorded, so a source that quietly revised an existing answer moves
nothing at all — no stamp, no signature, no digest. Detecting upstream drift is therefore an act, and
since 0.7 there is a command that performs it: **`just-dna-enricher enrich spec/ --rederive`** re-asks
every recorded subject and names the ones that came back different. It costs the full resolution time,
which is why it is a flag rather than the default.

Two things made this unperformable before, and both are gone. The overrides a re-derivation used to
discard now live in `overrides.csv` and are never inside the derived file (§6.3), so re-deriving costs
nothing. And the comparison is free because the run is a transaction: the fresh table is staged beside
the current one and commits by rename, so both sides exist at the commit boundary.

**The honest limit, because it is the obvious alternative.** `rm resolution.csv` plus a re-run
re-derives just as correctly and reports **nothing** — it destroys the old values before the fresh ones
arrive, so nothing holds both sides and there is no comparison left to make. Use `--rederive` when you
want to be told; use `rm` when you only want the file rebuilt. A subject the sources could not be asked
about keeps the rows it had either way: re-deriving is never a way to shorten the table.

## 6. Pass two and beyond

### 6.0 There is no versioning contract, and that is a decision

A version number is a **signal a reader weighs, not a schedule**. `2.0.0` does not mean reviewed,
`1.0.0` does not mean unreviewed, a human may curate from the very first version or never, and a
module may sit at `1.0.0` forever and be fine. What accumulates trust is what the module *records* —
`authorship` entries, their `kind`, the checks in `verification.json`, the closure — and a reader
weighs those directly. Any rule of the form "version N means stage X" is invented, and inventing one
makes a tool withhold a publish waiting for a milestone that does not exist.

The registry states SemVer *conventions* (major = the annotation results change, minor = rows added
without changing existing answers, patch = metadata only) and **enforces none of them**. It enforces
exactly two things about a version: that it parses as SemVer, and that this exact
`(namespace, name, version)` does not already exist. Ordering is checked client-side or not at all.

So the pass-two question is never "what version does this deserve". It is the four questions below:
what moved, what has to be regenerated, what claims were invalidated, and what a consumer will see.

### 6.1 Six kinds of second pass

| Kind | What the author did | Typical trigger |
|---|---|---|
| **Prose** | README, changelog, logo | a caveat was unclear |
| **Review** | appended an `authorship` entry; changed no data | somebody — a specialist, a second agent — read the module |
| **Evidence** | added/replaced citations, quotes, `studies.csv` rows | the preprint was published; a replication landed |
| **Data** | edited or added annotation rows | a call was wrong, a genotype was missing, scope grew |
| **Source refresh** | re-drafted from a newer snapshot | the drafting source (ClinVar, CPIC, ClinPGx, CIViC, STRchive, MITOMAP, …) published a release |
| **Rebuild** | changed nothing; recompiled under a newer toolchain | a contract tightened, or the catalog asked |

They are not stages and they compose. What separates them is which of the four consequences each
one triggers — and the answers are not what intuition suggests, which is why they were measured
rather than derived.

### 6.2 The consequence matrix — measured, not derived

Run against `reference_examples/hfe_hemochromatosis` with `just-dna-compiler compile --strict`,
comparing `artifact.digest`, top-level `content_signature`, and whether the manifest carried a
`verification` block and a `closure` after each edit.

| Edit | `artifact.digest` | `content_signature` | attestation | closure |
|---|---|---|---|---|
| recompile, nothing touched | same | same | kept | kept |
| `README.md` edited | same | same | kept | kept |
| **an `authorship:` entry appended** | **same** | **same** | **dropped** | **dropped** |
| line endings normalized in `variants.csv` | same | same | kept (RM82) | kept (RM82) |
| **`fetched_at` hand-edited in the licence table** | **moved** | same | kept | kept |
| a `conclusion` reworded | moved | moved | dropped | dropped |

Four readings. The last two are already documented elsewhere and are repeated here because the
matrix is unreadable without them; the first two are not stated anywhere:

- **A review pass moves no identity and destroys both claims — and that is correct.** Appending a
  reviewer to `authorship` leaves the compiled bytes byte-identical — `authorship` is manifest-only, in
  neither identity — and yet the compile warns *"verification.json is stale: the attestation was
  computed over different module bytes"* and drops the whole block, plus the closure. It follows from
  each rule in isolation (`module_spec.yaml` is an authored input; the binding is over authored bytes;
  an authored edit un-closes the module), and the composite reads at first as a defect: the one pass
  the trust model is built on appears to discard the module's record of having been checked. **Decided
  on 2026-08-16 that it is not a defect, and the reason is worth stating rather than merely living in
  the rules.** A review that changes nothing is not a no-op — it is an attestation *of* zero changes,
  a reviewer saying *I submit this exactly as received*. That is a new claim about the bytes, made by
  someone who had not made it before, so the old closure is genuinely spent and the reviewer is exactly
  the person who should re-close. The remedy — re-run the checks, close again — is not a workaround; it
  is the review being recorded. §6.6 states the resulting four-step pass. What is **not** settled is what
  a catalog does with two versions whose data is byte-identical and which differ only in who signed off.
- **Line endings used to cost the same as an edit, and since 0.6 they cost nothing (RM82).** Rewriting
  `variants.csv` with a different line ending changes no value, no digest and no signature, and it used
  to drop the attestation and the closure anyway. Unlike the row above, no human made a claim there: an
  editor did, or Git did through `core.autocrlf`. The binding now reads `\r\n` as `\n` — a byte
  transform needing no loader and no parse, which is what separates it from the content-aware binding
  that was rightly refused. **It stops at newlines**: a BOM, trailing whitespace and a missing final
  newline are still edits, because those are things a human typed. And it is the *binding* only —
  `manifest.inputs[]` still lists the file's raw hash and raw size, so that entry does move on a
  rewrite. The two answer different questions (*is this the same module* versus *are these the exact
  bytes*), and the asymmetry is the decision rather than an inconsistency to tidy. The wider trade for
  everything the binding still covers stands: a stale claim is worse than a re-run.

  So what un-closes a module is exactly what it should: any changed *value* in `module_spec.yaml` or an
  authored CSV, a row added or removed, a column reordered, a cell requoted — and an `authorship:`
  entry, per the row above. What no longer does: the line endings, and (since the binding was drawn) a
  re-enrichment that rewrites a derived sidecar.
- **A provenance column moves the digest and no signature.** `fetched_at` is outside every fact set,
  so nothing hashes it — and `sources.parquet` is inside the Merkle root, so the bytes count. Note
  the row says *hand-edited*: this is the mechanism, demonstrated deliberately, **not** what a re-run
  does. No merge restamps `fetched_at` (§5). The column that really moves this way on a second pass
  is `draft_digest`, which is re-stamped on purpose and sits outside `SOURCE_FACT_FIELDS`.
- **Prose is genuinely free.** README and logo are outside both identities *and* outside the binding,
  which is what makes "fix a typo without spending a version" true end to end: the registry has three
  amend endpoints (changelog, logo, readme) that move no digest and no content claim.

### 6.3 What must be deleted, and what deleting costs — **nothing, since 0.7**

Every derived sidecar is **merge-not-clobber**: an existing row is authoritative and a re-run adds to
it rather than replacing it. The rule exists because these tables were human-overridable by design,
and until 0.7 its consequence was the single most important operational fact about a second pass:

> **A re-run does not refresh anything already recorded. To re-derive a sidecar you delete it first,
> and deleting it discards every hand-curated row in it along with the stale ones.**

**The second sentence stopped being true in 0.7 (RM124).** A correction now lives in `overrides.csv`
beside the spec, the compiler applies it on every build, and the derived files became pure build
products — `derived = f(source, overlay)`. So there is nothing inside a sidecar to preserve, `rm` plus
a re-run costs nothing, and the last column of the table below is a record of what the arrangement
used to cost rather than a warning about what it still does.

**What the change is not.** Merge-not-clobber's *behaviour* is unchanged: a re-run still gap-fills —
it fills subjects with no row and leaves recorded rows alone — because re-asking every subject on
every pass would put the full resolution time on every run to buy drift detection nobody asked to run
continuously. What changed is what leaving a recorded row alone *risks*, which is now nothing, because
the row carries no authored content. The first sentence of the quote therefore still holds and the
deletion it recommends is now free.

| Sidecar | A re-run… | Delete to re-derive when | Deleting cost, before 0.7 |
|---|---|---|---|
| `resolution.csv` | skips every `variant_key` already covered | an identity column changed, or a locus was resolved wrongly | hand-authored `source=manual` rows — real, and not reproducible by re-running (`reference_examples/cyp2c9_warfarin_grch37` carries three). Now an `insert` in the overlay |
| `frequencies.csv` | merges; existing rows win | the variant set changed, or you want a newer gnomAD | nothing hand-written normally |
| `gene_metrics.csv` | merges | the gene set changed | curator overrides, if any |
| `literature.csv` | refetches nothing; **will not back-fill** the 0.6 licence columns onto older rows | you need the licence columns, or a `doi_checked` verdict re-put | a curator's deliberate blank, which merge cannot distinguish from an absent value. Now an `update` with an empty `value` |
| `gene_validity.csv`, `clinical_assertions.csv` | merge, per the governing sidecar rule — ENRICHER.md does not restate it for these two 0.6 passes | the source published a newer release | curator overrides |
| `gwas_effects.csv` | merges on `association_id` | the catalog published new associations | curator overrides |
| `licensing.csv` (`sources.csv`) | never clobbers a row — **except** that `withdraw_stale_dataset` blanks `dataset` when rows were actually added, and `draft_digest` is re-stamped explicitly | rarely; the two machine-owned columns maintain themselves | the curator's hand-written terms, which is exactly what never-clobber protects. **Outside the overlay's covered set**, deliberately — it is the one derived table a human is told to write |
| `verification.json` | replaces **per check**, and never erases a check this run did not put | never by hand | the record of every other check |

Two more rules that only bite on a second pass:

- **Write to the file you read.** A module carrying the old `sources.csv` spelling, or carrying its
  sidecars under `derived/`, must be written back the same way. Both copies present is an **error
  naming both paths** (`layout.SidecarCollision`) — never a merge and never newest-wins, because two
  fact-hashed, human-overridable copies are two legitimate claims.
- **A no-op run writes nothing rather than a zero.** `literature --offline` on a module that already
  has a `literature.csv` writes no records at all, because the verification merge replaces per check
  and a true `subjects=5, findings=1` must not become "never asked" on a run that changed nothing.

### 6.4 The two things a re-draft does that a recompile does not

**A re-draft that appends nothing changes nothing** — and that corrects a claim in circulation.
the retired authoring skill's gotcha list said *"a re-draft always changes `artifact.digest`, even when the data
is identical"*, on the reasoning that the licence row's `fetched_at` is re-stamped each run. It is
not: `merge_sources_csv` is `setdefault`, `stamp_draft_digest` is a no-op when no row was appended,
and `withdraw_stale_dataset` only fires when rows were actually added. Verified by running
`record_source_terms` twice against one spec directory — byte-identical file. **A re-draft that finds
nothing new is inert.**

What a re-draft that *does* append moves, in order of how much it means:

| moved | by |
|---|---|
| `content_signature` + digest | the appended authored rows — a real content change |
| `source_signature` + digest | `dataset` blanked, because the module now spans two releases (`dataset` is a fact); or a source recorded for the first time |
| digest only | `draft_digest` re-stamped over the newly grown table |
| nothing | a re-draft that appended no row |

**A recompile is reproducible** — the same spec twice under a fixed compiler gives the same digest,
measured above. What breaks digest-based dedup is therefore not a rebuild but a **toolchain change**:
parquet is not byte-deterministic across polars/arrow versions, so P4 scopes the guarantee to a fixed
`compiler_version`. Key `find-by-hash` and any dedup surface on `content_signature` for that reason,
not because re-drafting churns the digest.

**A re-draft appends and reports; it never rewrites.** A row whose key already exists comes back
`already_present` or `differs`. `differs` is the interesting one on a second pass: it is the source
disagreeing with something you already authored, left unchanged deliberately, because only you know
which side is right. A partial row matches on its **identity columns** rather than its natural key,
so a re-draft after a human filled a stubbed `genotype` adds nothing rather than duplicating.

And the provenance columns maintain themselves in a specific, non-obvious way. `SourceRow.dataset`
names the release the annotations were copied from, and `draft_digest` is a hash of the drafted
column. Together they let the ClinVar cross-check skip a comparison that could not fail:

| what the module records | what the `clin_sig` check does |
|---|---|
| no licence row, no `dataset`, a different release, an unreadable `release.json` | runs |
| this release, **no digest** | runs |
| this release **and** a digest that still matches | skipped as a tautology, in both modes |
| this release, digest **moved** — someone edited a `clin_sig` | runs, over the whole table |

Widening a panel from a newer snapshot puts the module in the first row of that table on purpose:
`withdraw_stale_dataset` **blanks** `dataset` rather than re-labelling it, because a module carrying
two releases has no single release to name.

### 6.5 The attestation and the closure across passes

- The attestation binds authored bytes, so **enrichment never invalidates it** (the sidecars are
  outside the binding) and **any authored edit does** (§6.2) — *edit* meaning a changed value, since
  0.6 reads `\r\n` as `\n` (RM82) and a line-ending rewrite is therefore not one. Currency of the
  *source* is a different question entirely and is read off each record's own `release`, never off the
  binding.
- `record_verification` carries the author's **closure** across a re-run only while the binding
  holds, and **drops rather than re-binds** it otherwise: re-binding would have a machine assert
  *a human declared these bytes final* about bytes that human never saw.
- `close_module` drops — and names, in `ClosureResult.dropped_checks` — any record attested over
  different bytes, rather than re-binding it.
- A **present** closure signature that fails to verify drops the whole document. Absence merely
  warns. Absence is a limit; a claim is a claim.
- So the re-open mechanism is implicit and is arguably the neatest thing in the design: **editing an
  authored file is what re-opens a module.** There is no `reopen` command and none is needed.

### 6.6 `authorship` across passes

A later pass **appends an entry; it never edits an earlier one**, because who wrote what is exactly
what a reviewer routes on. A joint contribution is two entries, each with its own `kind` — the format
refuses a lossy `hybrid` tag. Nothing constrains the order: the human entry may be first, or may
never come. And since `authorship` sits outside both identities, a pure review is a real version bump
without pretending the data changed — two versions with identical rows and different authorship share
a `content_signature`, which the registry's duplicate-content gate explicitly permits **within the
same module**. What it does cost is the attestation and the closure, measured in §6.2 — so a review
pass is: **append the entry, re-run the checks, close again, publish.**

That cost is the design working, not a wrinkle in it. A review that changes nothing still asserts
something nothing had asserted before — *I read these exact bytes and they needed no change* — and the
closure is a record of a human declaring bytes final, so the person making the new claim is the person
who must make it. There is no version of this where the old closure survives and still means what it
says.

**What happens to that pass downstream was the sharper half of the question, and it is now answered.**
Four findings, first read out of `just-dna-registry`'s tree on 2026-08-16 and re-verified against that
tree on **2026-08-20 at registry 0.18.3**. Three of them were filed there as asks — their S10–S12; the
first is a confirmation and was never one. They are stated separately, each
with the release that moved it, because the composite sentence this paragraph used to carry went stale
as a unit — three of the four have moved since it was written, and a reader could not tell which:

- **The publish succeeds, and the same-module carve-out is real code rather than prose** — unchanged,
  and it is what makes the rest legal. The duplicate-content gate compares `(namespace, name)` and is
  pinned by a test, so two versions sharing a `content_signature` inside one module are permitted by
  design.
- **The pre-flight now agrees with the gate** — fixed in registry **0.16.0**, and this is the finding
  most worth knowing, because it had a blast radius: an automated publisher branching on
  `would_publish` refused its own legal review publish. The verdict now quantifies over a new
  `published_elsewhere` — the subset of hits under a *different* `(namespace, name)`, which is what the
  gate actually refuses — while `published_as` still lists the same-module hit, since *“this data is
  already published as 1.0.0”* is exactly what a review pass wants to confirm. The namespace is
  threaded through both pre-flight routes, `validate` and `check`.
- **The closure now reaches downstream, by two routes, neither of which is the registry reading the
  file as a verdict.** `verification.json` entered `RECOGNIZED_SPEC_FILES` in **0.16.0**, so a
  server-side rebuild (`revalidate`, `upgrade`) carries it forward instead of dropping it; and in
  **0.17** it entered that registry's `DERIVED_FILES` and `manifest.derived`, so
  `download(include_inputs=True, layout="split")` lands it at `derived/verification.json`. Separately,
  `manifest.verification` is **projected onto a read endpoint** — the module detail response, from the
  latest version's manifest, with per-version access through the `…/manifest` route. Deliberately not a
  card facet, not a filter and not sortable: it is presented as the publisher's claim, never as a
  registry verdict, on the reasoning that a server which compiles what it publishes must not lend its
  credibility to an attestation it cannot reproduce offline. `closed` is the sturdiest field in it,
  because the closure is hash-bound and that server's own compile re-binds it against the authored bytes
  and drops it when it does not match. It stays out of `SIGNATURE_INPUTS`, which is the property that
  made recognising an unread file safe in the first place and has not moved.
- **`authorship` still reaches no projected field, and that is now policy rather than an omission** —
  stated by that registry in answer to our ask. Seeing who reviewed a module means reading the manifest,
  which is where it is plainly the manifest's word; a card presenting it beside the server's own claims
  would present two different kinds of fact as one.

**So the re-close is no longer a version number spent on an invisible record** — which is what this
paragraph used to conclude, and the conclusion inverted when the three releases above landed. What that
does *not* mean is that a review should default to a version bump. That registry has a **`reviews` table**
of its own — projected onto module cards, moderatable, driving `?group=curated`, costing no version at
all, and postable by a reviewer who is not the author, which the manifest cannot express. Asked which
instrument an author should reach for, it answered: **a `reviews` row by default; an `authorship` entry
when the record has to travel inside the module or be signed; both when both matter.** They are not
substitutes, and the deciding asymmetry is that a `reviews` row cannot carry the reviewer's key — so
provenance-of-review is `authorship` or nothing. The version-bump path is legal and now costs a version
number and nothing else; it is the right instrument when the record must survive a download, a hand-off
on disk or a re-publish, and reach a consumer who never talks to that API at all.

### 6.7 What the registry does with v2

Structurally, v2 is the same call as v1: the same multipart publish, the same required files, the
same gates. What differs is what is already claimed.

- **Enforced:** SemVer well-formedness, and that this exact `(namespace, name, version)` is free.
  Ordering against `latest` is a **client-side** check (`update-module-version`); the API does not
  compare.
- **No content relationship between versions is enforced or recorded.** No diff requirement, no
  parent digest, no monotonic stats. The only cross-version content rule is the duplicate-content
  gate, which is keyed on `content_signature` and **exempts a later version of the same module**.
- **v1's data is claimed forever.** Publishing v1's authored rows under a *different* `(namespace,
  name)` is refused, and yanking v1 does not release the claim. Yank delists; it never edits.
- **v2 compiles under today's contract; v1 did not.** This is the real asymmetry of a rebuild pass. A
  spec that passed two releases ago can now hit a tightened validator or strict resolution on the way
  back in. The registry's own audit (`revalidate`) classifies every published version as
  `ok` / `upgradable` / `needs_upgrade` / `blocked` / `strict_blocked` / `skipped` / `superseded`,
  and `upgrade` remediates by **re-publishing the latest non-yanked version as the next patch,
  never mutating old bytes**.
- **v2 replaces the card.** README, title and display are carried forward from the newest spec;
  `updated_at` advances, `created_at` does not; a spec with no README leaves the existing prose alone
  rather than blanking it.
- **Do not spend a version on prose.** Changelog, logo and readme each have an amend endpoint that
  moves no digest and no content claim.
- **Rehearse v2 too.** The polygon exists because on production a botched publish is permanent in two
  ways at once. It differs from production in exactly three behaviours: `test-`/`test_` names, the
  scope of the duplicate-content check, and the `DELETE` routes.

### 6.8 What a consumer sees when v2 lands

This is where the lifecycle is thinnest, and the honest summary is that **there are two acquisition
paths with two entirely different notions of "updated", and neither delivers a notification.**

**Registry-installed modules** get a real per-version audit. The reference consumer reads four
per-version fields and branches on all of them: `needs_upgrade` (a hard filter — a stale-schema
version is not offered at all), `artifact_digest`, `resolution.trusted` (three-valued, and
deliberately kept as a string so `None` cannot collapse to `False`), and `yanked`. But **there is no
upgrade action**: no "update available" badge, no SemVer comparison anywhere in the install path.
Installed-vs-current is decided by exact version-string equality, a new version replaces the old one
in place (`rmtree` then extract — two versions of one module cannot coexist locally), and the user has
to notice and choose.

**Modules discovered by path** (the HuggingFace layout the reference consumer defaults to) had **no
version identity at all**. There was no version in the path, no manifest fetch, no digest check. A
republished module kept the same URL, so the cached copy shadowed it; the only invalidation is a purge
keyed on the *consumer application's own package version*. Stated plainly: on that path, the identity
used to detect "the module changed" was a property of the reader, not of the module. A module
republished with new science while the app stays pinned is invisible, and an app patch release with no
module change purges everything.

**The publisher half of that is closed in 0.6 (RM84); the reader half is theirs.** `upload_module` now
writes the same files twice — the flat `data/<name>/`, unchanged in meaning and still *latest*, and
`data/<name>/v<version>/` (a subdirectory of it) whenever the manifest states a version, so the path
can finally name a release. That is deliberately the cheaper half: a version segment nobody reads is dead bytes and a
reader looking for a segment nobody writes finds nothing, so writing both is what lets the two sides
land independently and leaves everything already published exactly where it is. Three things it does
**not** do, and none of them is an oversight: it adds no manifest fetch and no digest check to the
discovery path (both are the consumer's step), it is two HuggingFace commits rather than one, and it
falls back to the flat path alone for a module whose `identity.version` is null — which, until the
registry stamps one on publish, is most of them. Two questions stay open, both asked of the consumer in
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84):
whether their `vN` fsspec fallback matches `v1.0.0`, and whether a subdirectory inside `data/<name>/`
disturbs a scan of a directory that until now held files only. Both are facts about their code rather
than things this repository can assert, and either answer is one line here.

Three further facts about the seam, all verified in the consumer's tree rather than inferred:

- **`verify_manifest` has no call sites there.** The install path extracts and registers without
  re-hashing `artifact.files[]` or recomputing the digest — even though the consumer's own spec
  document specifies a six-step verify-then-install flow. The format supplies the verification; the
  consumer does not run it.
- **`resolution_mode` and `fully_resolved` are never read — deliberately, and the docs were the thing
  at fault.** The reference consumer reads the registry's projected `resolution.trusted` where it wants
  a verdict at all, and for the question its engine actually puts — *can this table join to a VCF by
  position* — it reads the artifact's own null coordinates, which is authoritative for the bytes in hand
  and works on a module whose manifest was never fetched. Answered as [S34](CONSUMER_SUGGESTIONS.md);
  the fields address *"a consumer"* in SCHEMAS.md and in `manifest.py`'s own comment while their reader
  is a **catalog**, and both now say so. No item: it dissolved into a documentation fix.
- **An annotation run records no module version.** The output manifest names each module by *name*
  and carries no version, no digest and no source URL, so a rendered report cannot be tied to the
  module bytes that produced it, and nothing can answer "which of my saved results are stale".
  **Closed on the consumer's side** in the same round (S34 §3): `ModuleOutputMapping` gained
  tri-state `version`/`digest`/`source_url`. Partial by construction on the discovery path, where only
  `source_url` was knowable — which is RM84 again, and the publisher half now makes a *versioned*
  `source_url` available to a consumer that follows the new segment: the URL then carries the version
  it used to be silent about.

Meaning-drift between versions is absorbed **at read time, by shape**: the consumer detects which
generation of artifact it is holding from the columns present (three are in circulation at once) and
falls back through `direction ← state` and `clin_sig ← booleans` accordingly. That works, and it is
the right design for a format that is additive within a major — but note what it implies: **the
consumer never learns that a module's meaning changed, it only copes with whichever shape arrives.**

### 6.9 `reverse` is not the recovery path

A round trip is a **fixed point, not a backup**. `compile → reverse → compile` preserves every
authored value and reproduces the digest offline, which is Principle 7 and is tested. What it does
not do is restore a module:

- **Lost, because they are manifest-only:** `authorship`, `provenance`, `logo`, `readme`, `panel`.
- **Lost, because it is not in the artifact:** `verification.json` — every check record *and* the
  closure. A reversed spec is open and warns until a human closes it again, which is deliberate:
  reverse holds no key and no standing to declare someone else's authoring finished.
- **Lost, because they were deliberately never materialized:** `resolution.csv`'s provenance —
  `authority`, `rsid_alternates`, `rsid_current`, `rsid_status`; `source` resets to `reversed` and
  `status` to `resolved`. Recovering them means re-running the enricher.
- **Lost on a non-GRCh38 module:** hand-authored resolution rows for the positional tables, because
  the positional fill is gated on GRCh38 (RM15) and there is nothing in the parquet to rebuild them
  from. This is [RM69](ROADMAP_1_0.md#rm69--resolution_signature-is-not-a-round-trip-invariant-when-the-positional-fill-is-skipped),
  and it is a documented limit of P7, not a breach: `resolution.csv` is not an authored value.

The module in your repository is the source of truth. Reverse is for reading back somebody else's
artifact and for proving the fixed point — not for getting your spec back.

## 7. What no stage owns

Stated plainly, because each of these is currently an absence a reader has to infer:

- **Nothing compares two versions of a module.** There is no `diff` in any tier. An author asking
  "what changed between v1 and v2" has CSV diffing and a set of signatures that say *whether*
  something moved, and nothing that says *what*.
- **Nothing generates a changelog.** It is prose typed at publish time, and it lives only in the
  registry — outside every hash, every signature and the artifact.
- **Nothing told an author their source had moved on — closed in 0.7 for one source, and honestly
  unanswered for the rest.** The tautology skip reads the release the module was drafted from, and
  `withdraw_stale_dataset` handles a module that ends up mixing two; neither answers *"ClinVar has
  published since you drafted this"*, which is the actual trigger for a source-refresh pass.
  [RM85](ROADMAP_HISTORY.md#rm85--a-recorded-release-compared-against-the-one-its-source-publishes-now) closed that as an
  enricher check rather than the tempting column (refused on RM71's argument — it restates `dataset`
  and rots where `dataset` is maintained): `enrich --verify-datasets` compares each recorded
  `SourceRow.dataset` against the release its source publishes now, and it is the cheap question to put
  before `--rederive`. **What remains is the reach.** Only ClinVar and, since RM163, the PGS Catalog
  have a live release label this tier can read in the namespace it records, so every other source
  reports `unchecked` with `unsupported` beside it — which is the honest state, not a clean bill, but
  it does mean a CPIC- or ClinPGx-drafted module still relies on its author knowing. Adding a probe is
  adding a member to `currency.default_probes`, which is how the second one arrived.
- **Nothing re-asked a question already answered — closed in 0.7.** Merge-not-clobber still means an
  ordinary re-run re-asks nothing, so a source that revised a row it already gave us moves no signature
  at all; what changed is that `enrich --rederive` now re-asks every recorded subject and reports what
  moved, and `rm` no longer costs anything because the curator's corrections are in the overlay rather
  than inside the derived file. §5.1's canary is performable. What remains is that it costs a full
  resolution and nobody schedules it for you.
- **The artifact records no predecessor.** `manifest.json` carries `identity.version` and nothing
  linking it to the version before it — no parent digest, no previous `content_signature`. The
  registry knows the history; a module handed to you on a disk does not.
- **Nothing notifies a consumer.** Both acquisition paths are pull. One of them had no version to pull
  against at all (§6.8) — [RM84](ROADMAP_0_8.md#rm84--a-module-has-no-version-identity-on-the-discovery-path-and-the-publisher-is-the-half-we-own),
  whose publisher half shipped in 0.6: the path can now express a version. It is still pull, and the
  reader half is the consumer's.
- **No results are traceable to the module version that produced them** (§6.8), which is the missing
  prerequisite under both [RM7](ROADMAP.md#rm7--evaluation-output--report-card-schema) and the
  verification-harness idea — both of which are consumer scope by charter, and are named here only so
  the dependency is visible from this side.

## 8. Evidence status — what has actually been run

This document's two halves are not equally tested, and it should be read that way.

| Stage | Status |
|---|---|
| 0–6 (origin → compile) | **exercised repeatedly.** Sixteen reference examples, all compiled and all sixteen closed; the corpus is round-tripped and swept for signature movement on every release batch |
| 6 identity behaviour under a second edit | **measured for this document** (§6.2), six edits against one real module |
| 7–8 (rehearse, publish) | **exercised by the agent surface**, not from this repository. Nothing here publishes |
| 9 (install, join) | exercised by the reference consumer; the format's own guarantee (`verify_manifest`) is **not** exercised by it |
| **Every pass-2 kind, end to end** | **never run.** No module in this repository has ever had a second version |

The last row is measurable rather than rhetorical: of the sixteen reference examples, **two declare a
`version:` at all and neither is above `1.0.0`**, and **one** carries an `authorship:` block. The
corpus contains no re-drafted module, no reviewed module, no module that was published and then
edited. Everything in §6 above therefore rests on the rules plus the six measurements in §6.2, and the
first real second pass should be expected to find something none of it predicted.

The obvious way to close that gap is the way the first pass was closed: take one existing reference
example through a real v2 — a review pass on one, a source refresh on another — and keep the result
as a reference example whose README names what it broke.

**Where the questions this document raised went.** It closed with an open-questions section until
**2026-08-16**, on the reasoning that each needed a decision before it needed an item. That reasoning
is the one this repo has twice found to be wrong — a question filed against a release is findable, and
a question at the bottom of a prose document is a backlog nobody reads. Five became
[RM82–RM86](history/ROADMAP_0_7.md#the-lifecycle-items--what-writing-down-the-second-pass-surfaced), two of them
carrying a decision rather than a fork — and RM82's shipped in 0.6, which is why §6.2's line-ending row
now reads *kept*. Two did not become items and are recorded where they belong
instead: the published trust rule addresses *"a consumer"* while its reader is a catalog, which
dissolved into a documentation fix (§6.8, and SCHEMAS.md); and the review pass costing the attestation,
**decided** — a review that changes nothing is an attestation of zero changes, so un-closing is correct
(§6.2, §6.6). That second decision spawned RM86 rather than closing flat, which is the one thing this
exercise did not predict: settling the format side is what sent someone to read what the catalog does
with the result, and the catalog turned out to refuse the publish in its pre-flight and drop the
closure on the floor. **RM86 closed on 2026-08-20**, all three findings answered — the pre-flight and
the closure both repaired upstream, the third declared policy — so §6.6 now records what a review pass
actually reaches rather than what it did not. Nothing was dropped from the section itself.
