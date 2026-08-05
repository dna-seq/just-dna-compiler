# just-dna-format — Roadmap

**Forward-only, and now active-only.** Every item here is open work. What shipped moved to
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) with its rationale intact, so this file answers one question:
*what is left to do, and how bad is it?*

- **[RM_TOC.md](RM_TOC.md)** — the complete index of every `RMn`, active and shipped, with the document
  that defines each and every document that mentions it. **Start there if you are looking for an item.**
- **[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md)** — the shipped items, plus the 0.4.1 / 0.5.0 / 0.5.1
  release narratives.
- **[CHANGELOG.md](CHANGELOG.md)** — what shipped in each release, newest first.
- **[USE_CASES.md](USE_CASES.md)** — where most `RMn` were derived (the *what-blocks?* lens);
  **[PROPOSAL_0_5.md](PROPOSAL_0_5.md)** — where their shape was argued.

Code comments citing "ROADMAP item N" / "ROADMAP 0.3 item 5b" are historical breadcrumbs — follow them
to [CHANGELOG.md](CHANGELOG.md) / [COMPILER.md](COMPILER.md).

**Status:** **0.4.0 is the published line** (tags stop at `v0.4.0`; `dist/` holds only 0.4.0 wheels).
All three packages are at **`0.5.0`, unpublished**, on `enricher-0.5`; `schema_version` stays `"1.0"`.

**The unpublished window is load-bearing while it lasts.** `integrity.file_entries` skips missing
files, so a **new optional table** never moves the digest of a module that does not carry it (additive
any time), while a **new column on an existing parquet** moves every module's digest — major-only once
0.5 ships. Anything digest-moving is therefore cheap now and expensive after the cut. Spent in this
window so far: `ResolutionRow.authority` (provenance, so no signature moved), the continuous-bin
semantics (`mt_heteroplasmy` re-authored), indel reconciliation (`shox_par1` gained a resolved
coordinate), and pseudoautosomal locus selection (`shox_par1` halved, 20 rows to 10) — RM33, RM35, RM31
and RM32 respectively. Only the last two moved an `artifact.digest`; neither moved a
`content_signature`, which is pre-resolution by definition.

Each entry below is `## RMn — name`, a metadata line (**severity**, **status**, **owner**, **motivating
case**), then the detail. Severity is *how much it costs to do*, not how urgent.

# Active items

## RM4 — Native ClinVar gene-panel materialization

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

**Severity** medium · **Status** deferred to 0.6+ · **Owner** format (schema) · **Motivating
case** 5-HTTLPR, SNP+SV modules, symbolic-VCF consume

A representation beyond `^[ACGT]+$`: `<S>`/`<L>`, `<DEL>`/`<INS>`/`<DUP>`, `<STR n>`, and large
indels. **Motivating cases: 5-HTTLPR** (a biallelic ~43 bp structural indel → Short/Long, *not* a
repeat count; rejected by today's nucleotide grammar and a category error in `repeat_alleles.csv`)
**and ClinPGx's `del`/`ins` genotypes** (177 rows in the release, e.g. `C/del`, `del/del`), which
the PGx passes skip rather than coerce. Also unblocks SV-scale variation and consuming symbolic
VCF alleles (round-2 §1b/3c).

## RM10 — Declarative inheritance-expectation field

**Severity** low (on demand) · **Status** deferred, on demand only · **Owner** format (schema) ·
**Motivating case** trio / multi-sample panels

An optional trio / de-novo / Mendelian-consistency assertion carried *as data* (the panel says
what it expects; a consumer checks it). Only if a real module needs it.

## RM15 — Build-agnostic identity & multi-build support (other-builds-support)

**Severity** large · **Status** deferred to 0.6+ — the build-naming half shipped as RM19 ·
**Owner** format (schema + compiler) · **Motivating case** GRCh37 / T2T modules; cross-build
annotatability

Today a coordinate is *implicitly GRCh38* (legacy-from-implementation): `genome_build` is
authored/manifest metadata, but every `chrom/start/ref`, the Ensembl resolver, and all coord-based
reasoning silently assume GRCh38. Coordinates are **not absolute** — GRCh37 / GRCh38 / T2T-CHM13
disagree, and the rsid↔coordinate mapping is **build-specific**: an rsid may resolve in one build
and be un-annotatable (unplaced/absent) in another, and presence/absence combinations vary per
build. This item makes the build a first-class axis — coordinates tagged by (or resolved per)
build, a **build-aware resolver** (the injected reference declares its build; a module/reference
build mismatch degrades to *unverified* rather than a false consistency error), and cross-build
rsid annotatability recorded *as data*. **The "coordinate-first identity" parking is now RESOLVED,
on its own stated condition.** This item parked option C because a bare coordinate "would bake
GRCh38 into `variant_key`", and said it "becomes reconsiderable only once identity can name its
build". A **GA4GH VRS allele id names its build**: the sequence is addressed by its refget
accession — the digest of the reference sequence itself — so GRCh38 and GRCh37 mint distinct,
correctly non-colliding ids. 0.5 therefore ships coordinate-first identity as the VA for a
resolved substitution (see [SCHEMAS.md](SCHEMAS.md) § the identity switch). What remains of RM15
here is the **multi-build** half: a second refget table beside `REFGET_GRCh38`, per-build
coordinates, and cross-build annotatability. The GRCh38-only minting ships now — the same
"GRCh38-now, multi-build-later" split this item already applies to one-to-many expansion.
**Generalizes one-to-many rsid expansion to multi-build:** a no-coord rsid that maps to several
loci is expanded to one row per locus (a paralog/SV signal a client can count — data-agnostic),
and that ships **GRCh38-only now as compiler behavior** (pinned by `compiler_version`, not a
schema break). What is build-specific is *which* loci and *how many*, so RM15 tags expanded
coordinates by build and records cross-build annotatability; the GRCh38 expansion itself is not
deferred. Blocked by nothing external (schema-shape + resolver decision) but large — touches
identity, positions, the resolver, and `artifact.digest`. Interacts with RM5 (symbolic/structural
alleles differ across assemblies) and the reserved `reference_db` axis.

## RM16 — Authored PRS weights (a scoring file, not a manifest)

**Severity** medium-large (on demand) · **Status** deferred — build against a real consumer ·
**Owner** format (schema + compiler) · **Motivating case** authored-weight PRS modules

0.4 shipped `pgs.csv` as a *manifest of PGS Catalog IDs* with the ancestry-validity fields — not
authored per-variant weights (just-prs resolves a `PGSxxxxxx` id to a harmonized scoring file and
scores each id itself, so inlined weights would be dead data; a PRS is a
Z/percentile-in-reference, a shape the format does not bin). Deferred: a distinct, digest-bearing
`effect_allele`+`effect_weight` scoring table for the case a module must ship weights the PGS
Catalog does not host. Build only against a real consumer that combines authored weights into a
score. See [PROPOSAL_0_5.md](PROPOSAL_0_5.md) D1.

## RM23 — Computational predictor scores as a table

**Severity** medium · **Status** deferred on grain + acquisition, not on code · **Owner** format
(schema + compiler) + enricher · **Motivating case** pathogenicity triage; splice-impact panels

(`predictions.csv`) — the groundwork every predictor source needs, built **once**: one row per
`(variant, predictor, score_kind)` with `score`, `dataset`, `source`, and an optional
`transcript`. Long-form, not wide, is the load-bearing choice — SpliceAI is four deltas plus
positions, CADD is one number, AlphaMissense is one plus a class, so wide columns would make every
new predictor a schema bump while long form makes it *data*. A predictor score is the same class
of object as an allele frequency or a LOEUF (a per-variant number from a named dataset, no
measurement), so the 0.5 sidecar precedent covers it. Deferred on two unsettled questions, neither
of which is code: the **grain** (per-transcript scores; how to name the four splice deltas without
inventing a predictor-specific column set) and the **acquisition** — precomputed splice scores
need the *masked vs raw* file sizes measured and the Broad lookup API's terms read, which is the
same measure-first question that correctly parked the frequency snapshot. Licensing is already
solved rather than blocking: SpliceAI/Pangolin, dbNSFP, AlphaMissense, REVEL, CADD and PrimateAI
are all non-commercial or academic-only, and `sources.csv` + the compile gate already confine that
to the modules that use them, while phyloP/phastCons/GERP (UCSC, free — and queryable per-range
rather than a bulk download) keep a module sellable.

## RM24 — Gene–disease validity as a table

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

**Severity** medium · **Status** deferred as a new table · **Owner** format (schema + compiler) +
enricher · **Motivating case** authorship/assertion-aware scrutiny

A facts sidecar carrying `clin_sig` + `review_status` + `review_stars` + `variation_id` per
variant, so a consumer can route scrutiny by assertion tier at query time (a 1-star submitter and
a practice guideline are not the same claim). Nothing is lost today: `clinical.ClinSigFinding`
**already** reports both fields via its `confidence` property, so this is about persisting the
tier, not discovering it. Deferred as a new table. **Do not confuse this with escalating the
check's severity** — see *Parked in 0.5*.

## RM27 — A redistribution compile gate

**Severity** low (after the design) · **Status** deferred — needs the third axis designed first ·
**Owner** format (compiler) + enricher · **Motivating case** OMIM-/dbNSFP-class sources

RM21's gate keys on `commercial_use` + `declared_use`; the 0.5 `redistribution` column is recorded
but **not** gated. Deferred because it is a genuine design question rather than a missing branch:
a redistribution bar is not a *use*, so `declared_use` (`unstated`/`non-commercial`/`commercial`)
is the wrong axis to resolve it against — a module may be built legitimately and still not be
shippable, which is a different verdict from the ones the gate currently issues. Needs the third
axis thought through before code.
## RM28 — Meta-conclusions and injected cofactors

**Severity** medium (after the corpus) · **Status** parked — and smaller than it was · **Owner**
format (schema + compiler) · **Motivating case** combination annotations; disclosure policy

**meta-conclusions and injected cofactors (starter shape recorded, deliberately unbuilt):**
A module is rarely one axis, and what a curator wants is to pair them — a CVD module that also says
something about aspirin or warfarin *given* what the rest of the module found. The format cannot
state that today: every table keys on one subject and `conclusion` is prose about it alone.
CONSTITUTION P1 already sanctions the mechanism (a non-Turing-complete boolean predicate, drafted
since 0.1 and never wired because nothing demanded it). **The algebra is three-valued, not boolean** — true/false/**unknown**, Kleene operators, with
`unknown` a first-class value. That is not new here, it is the rule this codebase already follows
everywhere (`None` ≠ `False` in `SourceTerms`, `CrossrefClient.exists`, `quotes_found`, `--offline`
reporting `unchecked`, `unresolved` for a missing measurement, `requires_callable` for an uncalled
absence) finally stated as an algebra rather than as separate cases. It matters concretely: with
Kleene `AND`, a conclusion gated on "ε4 present AND QUAL ≥ 60" is decidably **false** at ref/ref
whatever the quality was, so a blanket withhold-on-any-unknown would be strictly worse than the
tables it replaces. A predicate evaluating to `unknown` is withheld — never reported, never negated.
The full design thread, the starter shape and what is deliberately left open are in
[PROPOSAL_0_5.md § G3](PROPOSAL_0_5.md). In brief: a new
**optional** table, a predicate that **never blocks** (an unresolvable reference warns), a grammar
kept to the smallest thing that covers the motivating case — conjunction **plus one relational
notion, in-cis/in-trans**, because the case that most justifies the table is compound
heterozygosity, where the same two alleles mean *affected* in trans and *carrier* in cis and a
pure conjunction cannot tell them apart (*the table is the safe commitment; the grammar is where
drift happens*) — and **injected cofactors** — values the consumer supplies at query time that a module must
never hold. Three classes so far, each with the same withhold-on-missing rule: **ancestry**
(a panel-scale inference, not derivable from a curated module's own gnomAD frequencies —
real models do not rely on single SNPs), **clinical context** (CPIC's populations), and
**call quality** (a `QUAL`/`GQ` floor, the `source_field`/`callable_from` declarative-pointer
idiom pointed at confidence — and distinct from the dropped `caller` names, which recorded
measurement provenance rather than an annotation's own applicability). The first real evidence arrived with
CPIC's clopidogrel populations, where `draft --population` makes an author bake in a choice that is
only knowable at query time. **Feasibility probed 2026-08-03 and the result argues for keeping it parked:**
`reference_examples/apoe_epsilon/` builds the highest-profile meta case — APOE, whose ε
haplotypes are defined by two SNPs together and whose ε4 condition is P1's own example
(`rs429358==C AND rs7412==C`) — with **bricks that shipped in 0.4 and no predicate at all**.
`HaplotypeRow` is a junction table, so same-strand co-location is what it already expresses;
`diplotypes.csv` carries the conclusion. What stays out of reach is narrower than it looked. **Rows are a disjunction and columns are a
conjunction**, so the existing tables already span any finite boolean function over an enumerable
set of genotypes — `OR` is two rows, `XOR` and bounded `NOT` are enumeration, and `haplotypes.csv`
is same-strand `AND`. No operator is missing. What is missing is (a) **economy and intent** — "any
two pathogenic variants in trans" over 300 of them is ~45,000 pairs, expressible but unwritable
and unreadable — and (b) **open-world negation**, which no operator fixes: "no pathogenic variant
in this gene" quantifies over a set the module does not close, and absence is only assertable where
the region was callable (`requires_callable`). A negation feature ignoring that would manufacture
reassurance, the worst failure mode this format has.

**Probed again 2026-08-03, and the cis/trans motivation is now closed — as a check, not a table.**
`reference_examples/hfe_compound_het/` builds the case that most justified the predicate grammar:
HFE C282Y and H63D, where the same two heterozygous calls mean *compound heterozygote, at-risk* in
trans and *carrier* in cis. It needs no new machinery either. A **diplotype is already a statement
about two homologs** — `haplotypes.csv` says which alleles ride together on one chromosome and
`diplotypes.csv` pairs two of them, which is what "in trans" means — so cis and trans are two rows,
and the relational notion the proposal was going to add to the grammar is what a diplotype pair *is*.
Between this and APOE, **both** halves of the phase argument are now answered by the existing tables.

What building it *did* surface is narrower and real: nothing said the two rows are
**indistinguishable without phase**. They present the identical unphased genotype with opposite
conclusions, and nearly all consumer data is unphased. That is derivable from the two tables the
compiler already holds, so it shipped as `_cross_validate_phase_ambiguity` — a warning, never a block.
A `requires_phase` column was rejected: it would make an author restate what the data determines and
would go stale the moment a haplotype is edited. It is closed-world by design (it compares stated rows,
never omitted ones), which is why APOE — whose ε2/ε4 vs ε1/ε3 is the textbook collision — stays quiet:
the module carries no ε1.

**So what remains of RM28 is smaller again**, and is the same two items APOE named: pairing across
*subjects* (no table keys on more than one), and **economy** — "any two pathogenic variants in trans"
over 300 of them is ~45,000 pairs, expressible and unwritable — plus open-world negation, which is not
an operator problem. RM29 removed two of the three cofactor classes into columns in the same round, so
only ancestry stays genuinely injected. Still parked. It waits on a corpus to generalize from — roughly 70% built; nutrigenomics
and supplements do not exist yet — because fixing a shape against four table kinds and then meeting
the fifth is how a one-way door gets spent badly (P3/P5). It also blocks the "shy module" signal.


The five items found by **dogfooding** on 2026-08-03 have **all shipped** — RM31, RM33, RM34 and RM35 in
that window, and RM32 in its own run — so none of them lives here any more; their rationale, including
the probe each rested on, is in [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md). The pattern worth carrying
forward is that in three of the five, part of what made the item look hard turned out to be **wrong on
probing** rather than merely cautious, so an entry's own reasoning is a starting point and not a finding.

**Round-3 / on-demand (widen additively only if a real module hits it):**
- **STR microvariant notation** — forensic loci use `full.partial` allele names (TH01 `"9.3"` = 9 full
  `TCAT` repeats + 3 extra bases), which is *not* the decimal 9.3. A binning bound stays a plain
  magnitude for ordering; the `full.partial` allele *name* is a distinct string (a candidate for the
  reserved repeat motif-path / allele-string escape hatch), never smuggled into the float bound
  (CONSUMER_ROUND2 C2). Pathogenic-threshold loci (HTT CAG) are unaffected.


# Not format scope

Listed so they are not mistaken for format scope, and so nobody re-proposes them.

## RM7 — Evaluation-output / report-card schema

**Severity** — · **Status** **not format scope** — a consumer contract · **Owner** consumer
(`just-dna-lite`) · **Motivating case** verification harness (§1a)

For the verification harness — **NOT a format task.** Per-sample results are a *measurement*, so
by the data-agnostic north star this is a **consumer** contract (`just-dna-lite`), listed here
only so it is not mistaken for format scope.

## Annotating core, not format scope (the 0.5 source assessment)

RM7 and RM13 are listed above so they are not mistaken for format scope. The same needs saying about
roughly half of every annotation source assessed in 0.5 — the half that **calls or interprets**. A
module supplies annotation tables; the measurement arrives from the consumer at query time, so none of
the following can land in these libs no matter how useful it is:

- **Star-allele callers** — PharmCAT, and Cyrius / PyPGx for the CYP2D6 case PharmCAT punts on. These
  turn a VCF or a BAM into a diplotype call: measurement. What *does* belong here is their **data** —
  the CPIC allele definitions PharmCAT ships — which is why the drafting helper reads them. Note that
  routing through PharmCAT does not launder the terms: its definitions are CPIC's, so the ClinPGx
  no-sale clause still applies.
- **Running splice or missense predictors**, and choosing their thresholds. A SpliceAI delta of 0.2 vs
  0.5 is an interpretation policy, not an annotation; RM23 carries the score and the dataset, never a
  verdict.
- **ACMG rule application and incidental-findings reporting policy.** The format carries `acmg_sf` as a
  flag and (with the pre-cut check) validates it against the published list; deciding what to report to
  whom is the consumer's.
- **Lay-language rendering.** A module already carries the ontology CURIE and a human `conclusion`;
  turning a MONDO term into patient-facing prose is a presentation concern.

**Cross-repo (tracked elsewhere):** **just-dna-marketplace** — take `just-dna-compiler` as the M4
publish dependency; serve `logs` via the files endpoint; render the cross-version provenance union
(`aggregate.aggregate_provenance`) on the module-detail view.


# Trackers

## The 1.0 cleanup (candidate tracker)

The **compatibility policy** — additive within a major, breaking cleanup only at a major bump, the
two-step deprecate→remove default — is a durable rule in [CONSTITUTION.md](CONSTITUTION.md)
(Principle 3). This is the **living tracker** of concrete items queued for the `→ 1.0` break; add
candidates as they surface.

**Additivity has two axes.** A new version may expand the **column-set** (new optional columns —
routine, digest-only-move while unpublished) *and* the **row-set** (one authored row compiling to
several — e.g. a one-to-many rsid → one row per locus). Row-set expansion changes identity
*cardinality* but is **not** a schema break: it is resolver behavior pinned on the `compiler_version`
axis (P4 already pins the digest to the resolved reference), so the GRCh38 expansion ships now. Only
the *build-aware* generalization (which/how-many loci per build, cross-build annotatability) is RM15.
The idea is to pile genuinely rule-tripping edge-cases (requiredness demotions, retypes, identity-key
*semantics* changes) on the 1.0/RM15 piles instead of forcing them into a minor.

Version-axis note: `schema_version` is `"1.0"` while the packages are `0.x` (now `0.4.0`). At `1.0`,
either align them or document explicitly that they track different things (wire format vs. package
release).

### `VariantRow.state`

**Severity** medium · **Status** queued for 1.0 — deprecate; remove at 2.0

Overloaded legacy field; a derived alias of `direction` since 0.3. **Disposition:** Deprecate at
1.0 (still read) → remove at 2.0, once consumers read `direction`/`stat_significance`.

### `state` values `alt` / `ref`

**Severity** low · **Status** queued for 1.0 — drop from the read-vocabulary

Genotype-relative descriptors that never belonged; recoverable from `ref`/`alts`/`genotype`; not
emitted since 0.3. **Disposition:** Drop from the accepted read-vocabulary at 1.0.

### `VariantRow.pathogenic` / `benign` booleans

**Severity** medium · **Status** queued for 1.0 — deprecate; remove at 2.0

Lossy (can't express `likely_*`/`uncertain`); derived aliases of `clin_sig` since 0.3 (now
materialized tri-state). **Disposition:** Deprecate at 1.0 → remove at 2.0. (`clinvar` provenance
boolean stays.)

### `StudyRow.p_value: str`

**Severity** low · **Status** queued for 1.0 — retype (`p_value_num` shipped in 0.5)

Untyped string holding a number; can't be compared/sorted numerically. **Disposition:** Add a
numeric companion in 0.x if needed; retype/remove the string at 1.0 (breaking).

### `weights.parquet` `end` column

**Severity** low · **Status** queued for 1.0 — blocked on the coordinate convention

Always set equal to `start` — no source column feeds it. **Disposition:** Remove outright at 1.0
(artifact-digest change, major-only) or wire it to a real end coordinate. **Re-examined in 0.5 and
deliberately left here** rather than wired inside the window: an end coordinate needs the
0-based/1-based convention settled first, and the repo currently has that inconsistency in the
open (`start`'s docstring says 0-based while the pipeline stores Ensembl's 1-based position, per
the CPIC/PharmVar gotcha). Wiring a second coordinate onto an unsettled first one buys an
off-by-one, not a feature.

### `weights.parquet` `likely_pathogenic` / `likely_benign`

**Severity** low · **Status** queued for 1.0 — remove; wiring rejected in 0.5

Always `False`; no CSV column feeds them — dead output. **Disposition:** Remove at 1.0, or wire to
the `clin_sig` tier. **Re-examined in 0.5: removal is the answer, and wiring was rejected.**
`clin_sig` is itself materialized into `weights.parquet` and `derive.pathogenic_from_clin_sig`
already maps `likely_pathogenic → True`, so a wired column would tell a consumer nothing it cannot
already read — it would spend the window's one free digest move on redundancy.

### `VariantRow.weight` vs `effect_size`

**Severity** low · **Status** queued for 1.0 — review only

Potential confusion — module-local score vs published magnitude (both kept, documented).
**Disposition:** Review at 1.0 whether `weight` stays or is subsumed by `effect_size`.

### Deprecated flag/vocab aliases

**Severity** low · **Status** queued for 1.0 — collapse to the canonical vocab

Any transitional vocab kept for 0.x compat (e.g. the trimmed-vs-full `state` set).
**Disposition:** Collapse to the canonical vocab at 1.0.

### `ModuleManifest.authors: list[str]` + free-form `curator`

**Severity** medium · **Status** queued for 1.0 — fold into RM14's record

Flat and overloaded — no role (created/edited/audited), no kind (AI/human); `Defaults.curator`
smuggles kind via its `"ai-module-creator"` default. Superseded by the structured authorship
record (RM14) once it ships. **Disposition:** Keep both as derived projections through 0.x (P8);
at 1.0 fold `authors` into the structured record and drop the kind-smuggling `curator` default.

### `StudyRow.pmid` required + PMID-shaped

**Severity** medium · **Status** queued for 1.0 — a requiredness demotion

Mandatory `pmid` (must parse to a real PubMed id) rejects DOI-only provenance — preprints
(bioRxiv/medRxiv), books, theses, datasets. Demoting a required field is P8-forbidden in-major, so
adding optional `doi` (RM11) alone can't unblock it. **Disposition:** **doi-first at 1.0**: make
`pmid` optional/legacy and require **≥1 of `{doi, pmid}`** (every citation has a stable id, not
necessarily a PMID; the reverse holds). Requiredness change → major-only.

### Compiler `ensembl_cache` deprecated shim

**Severity** low · **Status** queued for 1.0 — remove the parameter

0.5 already moved the whole DuckDB resolver + cache-location into `just-dna-enricher` and dropped
`duckdb`/`platformdirs`/`python-dotenv` from the compiler (it is now pure-Python; resolution is
the `resolution.csv` table). What remains is the `compile_module(ensembl_cache=…)` **surface**,
kept as a deprecated shim that emits `DeprecationWarning` and routes to the enricher via a guarded
import. **Disposition:** Remove the `ensembl_cache`/`resolve_with_ensembl` params outright at 1.0
(internal call, not the wire/artifact contract, so additive-within-major does not protect it).

### Coordinate-first identity (option C)

**Severity** — · **Status** ✅ resolved in 0.5 by VRS — kept for traceability

The objection was that a coordinate key is *build-baked*. A **VRS allele id is not**: it names its
reference sequence by refget accession, so it satisfies RM15's own reconsideration condition.
`variant_key` now derives from the VA for a resolved substitution; rsid-keyed, position-only,
indel and multi-allelic rows keep their previous keys. **Disposition:** **Done, in 0.5.0's
pre-publication window** — an identity-semantics change is major-only because `variant_key` sits
in `artifact.digest`, and that gate is *publication*, not the version number: 0.4 is the published
line and 0.5.0 never shipped, so it rode the same one-time re-baseline as the alt-carrying key. No
published artifact moved.


## Reserved namespace

Because backward-compat makes column names and vocabularies **permanent within a major** (CONSTITUTION
Principle 5), a name expected to become a real **module column** later is reserved against the one-way
door and **must not** be claimed early or smuggled in as `flags`. This list is *only* for genuine
anticipated module-side axes — it is **not** a catalogue of names that "may not appear" (that space is
unbounded and pointless to enumerate; barring `caller` would be as arbitrary as barring `pasta_recipe`).
Audit every new name against this list before adding it.

**Enforced now** (the live set is `just_dna_format.vocab.RESERVED_NAMES_0_4`). Every authored model
inherits `AuthoredModel`, which sets `extra="forbid"` (rejects *any* unknown column) **and** runs the
`reject_reserved` before-validator, so a reserved name fails with a *specific* diagnosis — what it is
reserved for + that a release may claim it (`vocab.RESERVED_NAME_REASONS`) — while a random/misspelled
column gets the generic "extra inputs not permitted":
- **`reference_db`** — a module-side hint naming *which* reference database the app should join this
  annotation against when several exist (implicit Ensembl for variants / ClinVar for `clin_sig` today;
  a module may pin it, e.g. a specific PharmVar release). Annotation-side addressing, a real future axis.

*(**`callable_from` was reserved here through 0.4 and is now BUILT** as a `VariantRow` column in 0.5
(RM6). A built name must leave this list: `reject_reserved` refuses a reserved column at author time,
so leaving it would make the very column the release added unwritable.)*

*(`caller` / `caller_version` were reserved through the 0.4 draft as a "provenance triple" (round-2 Q2)
but are **dropped**: they name which tool produced a *call* — a consumer-side measurement, never module
annotation — so there is no future module axis to hold, and barring the bare name is arbitrary. A
consumer records them on its own call data; a module never carries them, and `extra="forbid"` rejects
them like any stray column. `reference_db` stayed because it has a real annotation-side meaning above,
not the caller-provenance one it was first reserved under.)*

**Planned future annotation axes** (documented intentions, **not yet in the enforced set** above — they
are rejected generically by `extra="forbid"` today, and get a slot + a specific diagnosis only when a
release actually commits to building them):
- **`consequence`** — VEP molecular consequence (Sequence-Ontology term, e.g. `missense_variant`).
  Distinct from `direction` (phenotypic) and `clin_sig` (clinical). **Never repurpose the bare word
  `effect`** for it.
- **`impact`** — VEP impact `{HIGH, MODERATE, LOW, MODIFIER}`, derived from `consequence`.
*(**`allele_frequency`** + **`af_population`** were listed here and are now **built in 0.5 as a
table, not a column** — `frequencies.csv` → `FrequencyRow`, one row per (allele, ancestry group).
A column pair could carry one number for one population; frequency is inherently per-group, and
flattening it onto the variant row would smear two axes together. So the planned axes are retired
rather than shipped. Gene-level constraint arrived beside it as `gene_metrics.csv`. See
[SCHEMAS.md](SCHEMAS.md) and [USE_CASES.md §6](USE_CASES.md).)*

*(`doi`, `provenance_quote`, and `provenance_regex` were reserved here for RM11/RM12 and are now **built**
as optional `StudyRow` columns in 0.4 — so they are absent from this list. The **doi-first** flip that
relaxes the mandatory `pmid` remains a 1.0 item; see the 1.0-cleanup tracker.)*

*(The ploidy / non-SNV quantities that were reserved through 0.3 — `allele_fraction` / heteroplasmy,
`repeat_count` + `repeat_unit`, copy-number dosage — are **built** as the 0.4 binning primitive; the
`hemizygous` genotype case ships via the widened single-allele genotype. Symbolic/structural alleles
remain open as RM5.)*


# The idea-book

## Freeform suggestions — the 0.5 idea-book

The consumer's grounded 0.5 ideas (kept inside the one constraint: **VCF-based, possibly augmented on
top**) live in full in [CONSUMER_ROUND2_AND_0_5.md](CONSUMER_ROUND2_AND_0_5.md) §3, each run through
the what-blocks lens in [USE_CASES.md](USE_CASES.md) §1. Standing dispositions:

- **3a — module declares where its measurement lives in a VCF.** ✅ Taken early: `source_field` shipped
  in 0.4 (an optional, `|`-alternatable **bare field-name token** on every binning table — a
  *declarative pointer, not an expression*, inside Principle 1). An ExpansionHunter VCF (`INFO/RU` →
  `repeat_unit`, `FORMAT/REPCN` → the measure) is consumable with zero glue.
- **3b — modules as a deterministic verification harness** (run a panel against N VCFs, emit a
  byte-diffable report-card). **The strongest idea, and it needs *nothing* from the format:** a panel
  is already a module, `source_field` names the field to read, `artifact.digest` makes the before/after
  diff trustworthy, and the mandatory `unresolved`/callability contract stops a no-call masquerading as
  a mismatch. It is a **consumer** feature (`just-dna-lite`); the format only supplies properties it
  already froze. Recorded as an *enabled* use case, not a gap.
- **3c — augmented-VCF as the landing pad** for cracked short-read loci (a synthetic `<STR>` record with
  `INFO/RU` + `FORMAT/REPCN` + custom evidence fields, consumed through the same `source_field=REPCN`
  path). Endorsed as the interface — the format binds to the VCF, it does not reinvent it. Consuming the
  *symbolic* alleles themselves is RM5.
- **3d — smaller VCF-native ideas:** callability three-state → RM6; phasing-aware panels → already
  expressible (the `phased` flag + VCF `PS`/`HP`); trio/de-novo assertion → RM10.

### Parked in 0.5 (recorded so they are not re-proposed as if new)

- **Enricher co-authoring** (permission-gated writes to *authored* files, not just sidecars). Attractive
  — it would let a stale rsID or a missing DOI be fixed where it actually lives instead of only being
  reported — and deliberately **not** taken, for a reason stronger than tidiness: `content_signature`
  is *defined* as pre-resolution and reference-independent ("computed from the rows before resolution,
  so recompiling against a different/complete reference does not change it"). If a network fetch could
  edit `variants.csv`, the content-dedup identity would become network-dependent and that documented
  property would simply be false. A secondary problem: `authorship` records who wrote the module, and
  an enricher that edits rows either falsifies that record or must add itself as an `ai`/`agent`
  contribution — coherent, but a much larger design than it first looks. Revisit only with both
  answered.

  **The drafting helper is not this item, and the line between them is one word: *mutate*.** The 0.5
  helper appends rows a source publishes into an authored CSV; it never rewrites a cell that is already
  there. Appending happens at authoring time and leaves `content_signature` a function of the authored
  bytes exactly as before — the property that would break is the one where a *fetch* changes the meaning
  of rows the author already wrote. So a row whose natural key is already present is **reported, never
  overwritten** (drift on existing rows is the cross-check pass's job, `pgx.enrich_pgx`), and the helper
  stamps no `authorship`: it transcribes a published table, and the human owns the module. Dedup keys on
  the compiler's own `_TABLE_DUPE_KEYS`, so an append can never produce a row the compiler would then
  reject as a duplicate, and rows are appended **at the end** — authored row order is preserved through
  compile → reverse → recompile, so re-sorting an existing file would move a compiled module's digest.

- **Escalating the ClinVar `clin_sig` cross-check when the disagreement is with an expert panel.**
  Tempting, because a VCEP or practice-guideline assertion genuinely is a different kind of claim from a
  one-star submitter's, and the snapshot already carries `review_status`/`review_stars` to tell them
  apart. Not taken: this is the one check that warns in **both** modes on purpose, because failing a
  compile over a clinical disagreement makes the format arbitrate a clinical dispute, which the
  data-agnostic charter forbids — and a curator who has read the primary literature and disagrees with a
  submission is doing their job. The tier is already *surfaced* (`clinical.ClinSigFinding.confidence`
  puts it in the message), and persisting it as queryable data is RM25. Surface it, let the consumer
  route on it, do not decide for them.

- **An offline allele-frequency snapshot.** The obvious symmetry with the ClinVar and gene-constraint
  snapshots, and it does not work: gnomAD v4.1's sites VCFs are **58 GB** (exomes) and **742 GB**
  (genomes), so there is no slice to ship at any useful coverage. Frequency is therefore the first and
  only **online-only** link in the chain. This is not a reproducibility hole — once `frequencies.csv` is
  written it *is* the pin, and every later compile reads it offline and deterministically. Revisit only
  if gnomAD publishes a small pre-aggregated frequency release.
- **HGVS string generation** (`c.`/`p.` notation). `ga4gh.vrs`'s extras pull `hgvs` transitively, so it
  would be *available* — but HGVS generation is its own feature with its own argument (which transcript,
  which reference, how to present ambiguity), and taking a dependency for indel normalization does not
  commit to shipping it. Deferred as a feature, not blocked by tooling.
- **Multi-build VRS minting.** A second refget table beside `REFGET_GRCh38`; the remaining half of RM15.
- ~~**dbSNP obsolescence / merge checking**~~ — **built in 0.5** as `identifiers.check_rsids`, wired
  into `enrich()` behind `--verify-rsids`. Two corrections to what this entry used to claim, both found
  by probing: it is **not** "detectable two ways" — Ensembl REST resolves *some* merges (`rs77121243` →
  `rs334`) and returns **HTTP 400** on others (`rs3216883`, which dbSNP correctly reports as merged into
  `rs3051860`), so Ensembl alone would misclassify a merged rsID as unresolvable. **NCBI `esummary
  db=snp` is the oracle**, batched and authoritative. See *the stale-identifier collision* below for
  what is done with the answer.
- **Sex-stratified frequency counts.** gnomAD serves `nfe_XX`/`XY`; sex is a second axis, and folding it
  into `population` would be the `state`-overloading mistake again. A future `sex` column on
  `FrequencyRow` is the additive shape if it is ever wanted.
- **`google-re2` for `provenance_regex` matching** (candidate, only if the current bound proves
  insufficient). The enricher matches `provenance_regex` against fulltext with stdlib `re` inside a
  killable child process (`literature.regex_matches`). That is a *bound*, not a linear-time guarantee,
  and the honest reason it is enough today is that the threat model here is a curator writing a slow
  pattern by accident — the pattern comes from the module being enriched and the document from a public
  archive, on the author's own machine, not an attacker meeting an arbitrary document.

  **The reason not to switch pre-emptively is capability, not cost.** Real fulltext has periodic
  structure — repeated section headers, boilerplate, tabular runs — and pinning a quote inside it often
  needs a **lookahead or lookbehind**. RE2 does not support either, so adopting it would narrow the
  pattern language the format offers authors, in exchange for a guarantee the subprocess already
  approximates. Revisit if `re` exhibits problems the process bound does not contain (a pattern that
  wedges a worker often enough to matter, or memory blow-up rather than time). If it happens, the shape
  is: keep `re` as the default, add `google-re2` as an optional accelerator, and record which engine
  ran — never silently change which patterns match.
- **Fulltext beyond the open-access subset** (candidate, cost-driven). OpenAlex and Unpaywall can point
  at a green-OA repository copy for some closed articles. Probed and *not* taken: the closed paper
  tested (`10.1038/s41580-019-0134-2`) has `is_oa: false` with no location at all, and the copies that
  do exist are PDFs — which would mean a PDF-parsing dependency in the network tier for a partial
  improvement on a check that is already labelled partial. The **abstract fallback shipped instead**,
  which costs nothing (the abstract is already in the Europe PMC response the pass makes) and covers
  four of five non-OA papers. Revisit only if authors report quotes that live in the body of closed
  papers often enough to matter.
- ~~**Google Scholar for citation existence**~~ — **rejected, not deferred.** It publishes no API, and
  automated querying violates its terms of service and is IP-blocked in practice. Crossref (DOIs,
  including preprints/books/datasets) and PubMed (indexed literature) cover the same ground through
  supported interfaces.



### The stale-identifier collision (design note, 0.5)

An obsolete authored rsID forces a choice that Principle 7 and "keep the module current" pull opposite
ways on, and it is worth writing down before anyone implements the lookup.

`weights.parquet` carries **both** `variant_key` and `rsid`, and for an rsid-authored row both are the
authored label. Writing the *updated* label into the artifact is not a one-time digest move — it is an
**identity migration performed by a network lookup**: reverse would then emit the new rsID into
`variants.csv`, the next compile would key on it, and `variant_key` itself would change. The module's
identity would drift without any authored edit, and the round-trip would stop being a fixed point.

So the rule is the one every other check here follows: **report, never repair.** Severity follows the
mode, matching the VRS-unverifiable decision exactly — `best_effort` warns and compiles with the
authored label (digest stable, round-trip intact), `strict` **refuses**, on the grounds that an
all-or-nothing artifact should not be built on an identifier its own source has retired. Failing is the
honest move because it pushes the fix to where it belongs: an authored edit.

Two refinements, both now settled by the 0.5 implementation:

- **Merged ≠ withdrawn — and withdrawn is not observable.** This entry used to say "probe the withdrawn
  shape before deciding", on the assumption that a withdrawn rsID deserved failing in both modes. The
  probe was done, and it dissolved the question rather than answering it: `rs11273140`, a genuinely
  *withdrawn* id, returns a response **byte-identical** to `rs2000000000`, which was never assigned —
  the same `error` string from `esummary`, the same `count=0` from `esearch`, the same Ensembl 400.
  Routes checked and rejected for separating them: `esearch` has no withdrawn filter (the phrase is not
  indexed), and `latest_release/misc/rs_unsupported_b157.txt` looks like a withdrawn registry but is a
  one-off build-157 ClinVar-parsing incident list that does not contain `rs11273140`. Separating them
  would need a historical dbSNP dump, not the live API. So the vocabulary is **`live|merged|absent`**,
  not `live|merged|withdrawn`, and `absent`'s *message* names both readings and asserts neither —
  because guessing "typo" sends an author to fix the wrong thing when the truth is that the variant
  itself was retracted. Severity is the same ladder for both (warn / fail in `strict`), not escalated
  beyond it, since `absent` has benign causes too (a very new rsID, or API lag).
- **The new columns are provenance, not facts.** `rsid_current` + `rsid_status` sit **outside**
  `RESOLUTION_FACT_FIELDS`, beside `rsid_alternates`. They describe time-varying *external* state;
  inside the fact set they would make `resolution_signature` change when dbSNP merges something, with
  no change to the module — the signature would stop being reproducible from the module's own content.
  (Shipped as specified, with a test that pins it.)

One consequence worth recording, since it was previously filed as a loose end: **`reverse_module` does
not carry these columns, and that is correct rather than a gap.** Reverse rebuilds `resolution.csv` from
`weights.parquet`, which by design holds no provenance — it already resets `source` to `reversed`,
`status` to `resolved` and blanks `fetched_at`. `rsid_alternates`/`rsid_current`/`rsid_status` are out
of the fact set *precisely* so they never reach the artifact, so the information does not exist for
reverse to emit; adding the column names would produce a permanently empty header. Recovering them
after a round-trip means re-running the enricher, which is where a statement about a reference at a
moment belongs. What reverse *does* now carry back correctly is the resolved **facts** and the authored
**shape** — see [COMPILER.md § Resolution](COMPILER.md) for the enumerated round-trip contract that
replaced the old "reverse emits position-only" rule.

**The strategic reading:** this whole class of problem is *label drift*, and it exists only for
rsid-keyed rows. A coordinate-authored row keys on a VRS allele id, which is content-addressed and
cannot drift. The obsolescence check is therefore the standing cost of the rsID key, and the format
already offers the escape — author coordinates and carry the rsID as data (reverse already emits
coord-keyed rows as position-only). A strict failure is the nudge toward the drift-proof key.

New ideas enter here as freeform suggestions, then graduate through the design cycle
(feedback → USE_CASES lens → PROPOSAL → shipped or parked as an `RMn` above).

