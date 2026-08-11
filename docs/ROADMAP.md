# just-dna-format — Roadmap

**Forward-only, and now active-only.** Every item here is open work. What shipped moved to
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) with its rationale intact, so this file answers one question:
*what is left to do, and how bad is it?*

- **[RM_TOC.md](RM_TOC.md)** — the complete index of every `RMn`, active and shipped, with the document
  that defines each and every document that mentions it. **Start there if you are looking for an item.**
- **[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md)** — the shipped items, plus the 0.4.1 and 0.5.0
  release narratives.
- **[CHANGELOG.md](CHANGELOG.md)** — what shipped in each release, newest first.
- **[USE_CASES.md](USE_CASES.md)** — where most `RMn` were derived (the *what-blocks?* lens);
  **[PROPOSAL_0_5.md](PROPOSAL_0_5.md)** — where their shape was argued.

Code comments citing "ROADMAP item N" / "ROADMAP 0.3 item 5b" are historical breadcrumbs — follow them
to [CHANGELOG.md](CHANGELOG.md) / [COMPILER.md](COMPILER.md).

**Status:** **0.5.0 is the published line** — tagged `v0.5.0`, built into `dist/`, and released to PyPI
on 2026-08-07, with `just-dna-enricher` 0.5.0 the first release of that package. `schema_version` stays
`"1.0"`.

**Shipped since: `just-dna-enricher` + `just-dna-compiler` 0.5.1 and 0.5.2** — 0.5.1 was
[RM38](ROADMAP_HISTORY.md#rm38--a-cache-for-every-gated-source-the-hosted-enricher)
(a cache for every licence-gated source, so a hosted enricher never reaches one live per request) plus
[RM39–RM42](PROPOSAL_0_5_1.md) from a consumer field report; **0.5.2** is the panel-scale batch behind
S3–S6 in [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md) — the quadratic DuckDB probe that stopped a
gene panel finishing, a `clin_sig` cross-check that no longer reports a structurally guaranteed zero, a
drafted genotype on the contigs where only one is expressible, and the `.env`-ordering bug behind three
separate "the cache is right there" reports (see [CHANGELOG.md](CHANGELOG.md)). **0.5.3** answers S9 the
same way: it does not widen resolution to the 0.4 families (that is RM43, whose prerequisite column
is 0.6 work since the charter amendment) but makes the scope legible — per positional table, how many rows a VCF cannot join and
how many of those `resolution.csv` could place — and adds `heteroplasmy.csv` to the enricher's subject
list so that family can be resolved at all. The three packages version independently, so
the network tier took a patch while `just-dna-format` stayed at 0.5.0; RM41 is the one item that also
touches the compiler, which is why that package moved too. None of it touches a parquet, a model or a
manifest field, which is why none of it is in the 0.6 table below. **That table is *format/compiler
schema* work**, and enricher-only work sits outside it entirely; do not read "additive work is 0.6" as
covering the network tier.

**The "digest window" is retired — the charter was amended on 2026-08-11 and the sort below follows the
amended rule.** What gates a change is what it does to a *reader*, not to a recompile's bytes:

- **A new optional column is additive and lands in a minor.** An unset optional column is omitted from
  `content_signature` and the per-input hashes cover authored bytes nothing rewrote, so the **authored**
  identity does not move; only a recompile's `artifact.digest` does, and Principle 4 already scopes that
  to a fixed `compiler_version`. Measured, not assumed — see CLAUDE.md for the numbers.
- **A new optional *table* is additive too, and more cheaply**: `file_entries` skips missing files, so a
  module that does not carry the new parquet keeps even its `artifact.digest` byte for byte.
- **Major-only is removal, promotion to required, and retyping** — the moves that break an existing
  reader or invalidate published data.

The practical effect is that several items below were deferred on a rule that no longer holds, and have
been re-sorted on their *own* merits instead; where an item stays deferred, the reason is now stated and
is never "it moves the digest".

Spent while the pre-publication window was open, recorded so it is not re-litigated: the VRS identity switch
(RM19) and the cofactor columns (RM29) — the two that actually needed it — plus
`ResolutionRow.authority` (provenance, so no signature moved), the continuous-bin semantics
(`mt_heteroplasmy` re-authored), indel reconciliation (`shox_par1` gained a resolved coordinate), and
pseudoautosomal locus selection (`shox_par1` halved, 20 rows to 10) — RM33, RM35, RM31 and RM32
respectively. Of the last four only RM31 and RM32 moved an `artifact.digest`; none moved a
`content_signature`, which is pre-resolution by definition.

**The 2026-08-06 readiness audit spent none of it**, which is worth recording because the findings were
severe: it fixed a Principle 7 break where `compile → reverse → compile` relabelled a non-GRCh38 module's
assembly and re-minted its identity key, three further build-confusions in the enricher (including a
frequency pass that would have fetched a *different variant's* counts), and a `validate` that passed
modules `compile` refused (see [CHANGELOG.md](CHANGELOG.md)). Every fix is confined to behaviour
that was only reachable **off** GRCh38 or through the error channel, so all ten pre-existing reference
examples keep their exact `artifact.digest`, `content_signature` and `resolution_signature` — verified by
comparing before and after, not assumed. The one addition is a new example
(`reference_examples/grch37_build/`), and a new module cannot move an existing digest.

Each entry below is `## RMn — name`, a metadata line (**severity**, **status**, **owner**, **motivating
case**), then the detail. Severity is *how much it costs to do*, not how urgent.

# 0.6 — what a minor permits

Sorted by the amended rule: what a change does to a **reader**, not to a recompile's bytes. Nothing
here is gated on the digest any more, so every ❌ or ⚠ below carries a reason of its own — a design
question, a corpus question, or a genuine break:

| Item | Shape | Minor-legal now? |
|---|---|---|
| **RM23** `predictions.csv` | new optional table | ✅ |
| **RM24** `gene_validity.csv` | new optional table | ✅ |
| **RM25** ClinVar assertion tier | new optional table | ✅ |
| **RM16** authored PRS weights | new optional table | ✅ |
| **RM28** meta-conclusions | new optional table + injected cofactors | ✅ — parked on the corpus, not on the window |
| **RM5** symbolic / structural alleles | *widens* a grammar | ✅ — P3 bars tightening, not widening |
| **RM27** redistribution gate | a gate over a column that already ships | ✅ — reads `sources.csv`, writes no parquet |
| **RM4** gene-panel materialization | compiler behaviour, opt-in per spec | ✅ — row-set expansion pinned on `compiler_version`; only a module that *declares* a panel gains rows |
| **RM10** inheritance expectation | a column, its own table, or yaml metadata | ✅ — all three placements are minor-legal now; pick on orthogonality (P5), not on cost |
| **RM43** resolve the 0.4 families | a stamped-identity column per positional table, then the join | ✅ — the column is additive; what is left is the design round, not a version gate |
| **RM44** `resolution_subjects` count | one additive integer on `Compilation` | ✅ — a manifest field, never in `artifact.digest`; retires a prose-matching workaround |
| **RM15** multi-build identity | changes the *semantics* of `variant_key` and of every coordinate | ❌ — 1.0, and not for digest reasons: re-keying published identity is the identity-change class |
| ~~**RM38** gated-source cache~~ | enricher-only: new builders + cache resolvers, no parquet touched | ✅ **shipped in `just-dna-enricher` 0.5.1** — never a 0.6 item; kept here so the *reason* an enricher change bypasses this table stays visible |

Two consequences worth stating outright:

- **RM10's gate dissolved.** It was parked partly because "where it lands" decided whether it was a
  minor or a major. Every placement — a column on an existing table, its own optional table, or
  `module_spec.yaml` metadata reaching only the manifest — is minor-legal under the amended rule, so the
  placement is now a pure design question: which one keeps the axes orthogonal (P5). Decide it on merit.
- **The 1.0 pile split when the rule changed**, and the two items that used to sit together show why.
  `weights.parquet`'s `end` is an *additive optional column*, so it is 0.6 work now, gated on the one
  thing that was always its real blocker: the coordinate convention a second coordinate needs
  (interbase-half-open vs inclusive), which RM15 must settle. **Removing** the dead
  `likely_pathogenic`/`likely_benign` pair stays major, because removal is exactly what the amended
  rule reserves for a major. Same tracker, opposite answers, and the reason is now legible.

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

**Severity** low (on demand) · **Status** deferred, on demand only — **and the placement now decides the
release** · **Owner** format (schema) · **Motivating case** trio / multi-sample panels

An optional trio / de-novo / Mendelian-consistency assertion carried *as data* (the panel says
what it expects; a consumer checks it). Only if a real module needs it.

**Where it lands is a design question, not a version gate.** A column on an existing table, its own
optional table, and `module_spec.yaml` metadata reaching only `manifest.json` are all minor-legal, so
choose on orthogonality (P5) and on what a consumer would have to join, never on cost. Settle it before
writing any of it — the item was parked while shapeless, and it is still shapeless.

## RM15 — Build-agnostic identity & multi-build support (other-builds-support)

**Severity** large · **Status** deferred to **1.0** — the build-naming half shipped as RM19, and the
remaining half changes the *semantics* of `variant_key` and of every coordinate, which is the
identity-change class a major exists for (not a digest question) · **Owner** format (schema + compiler) · **Motivating case** GRCh37 / T2T modules;
cross-build annotatability

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

**What a non-GRCh38 module gets *today* is now pinned, and it was not before.** The 2026-08-06 audit
found four separate paths quietly answering a GRCh38 question in a GRCh37 module's name — reverse
relabelling the build, `enrich()` resolving against the wrong assembly, `VrsMinter` aborting on one,
and the frequency pass querying gnomAD with an off-build coordinate. All four survived because **every
reference example was GRCh38**, so "reads the build" and "writes `GRCh38`" were indistinguishable.
`reference_examples/grch37_build/` closes that, and `test_reference_examples_roundtrip.py` asserts the
corpus spans more than one build so it cannot reopen. This does not shrink RM15 — the remaining work is
unchanged — but it does separate the two halves cleanly: **RM15 is about *supporting* another build;
what shipped is only that the tools *decline* to answer for one rather than answering wrongly.**
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

## RM43 — Resolution reaches the SNP core only, so a 0.4-led module is rsid-joinable and nothing more

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

## RM44 — `fully_resolved` answers a question nobody asked it, and prose is the only record of the real one

**Severity** low (one additive field) · **Status** open — **0.6** · **Owner** format (manifest) +
compiler · **Motivating case** a catalog served `trusted: true` for modules that annotate nothing
(S13 in [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md))

`manifest.compilation.fully_resolved` is `all(...)` over `variants.csv`, so on a module without one it
is `all()` over an empty list — **vacuously `true`**. The field is not wrong; it answers its question
correctly. It simply cannot say *which* question it answered, and the trust rule its own field comment
documents (`resolution_mode == "strict" or fully_resolved`) reads it as a module-level verdict. A
consumer followed that comment and shipped it: `just-dna-registry` granted its `trusted` badge to
`pgx_slco1b1_simvastatin` and `cyp2c19_star_alleles`, both of which join to no VCF, and needed a
migration to repair the stored projection.

**The workaround is the finding.** There is no structured field saying a table joins to nothing, so the
only record surviving into a catalog is the 0.5.3 warning's *prose* — `compile_module` copies its
warnings into `manifest.compilation.warnings`, and a reindex has no spec directory left to re-derive
from. The registry pins `UNJOINABLE_MARKER = "have no chrom+start"` and substring-matches it to decide a
badge. Confirmed from this side: the phrase reaches `manifest.json` verbatim for both modules and is
absent for a module whose core resolves. That sentence is now load-bearing, which is a bad place for a
sentence to be; `compiler.UNJOINABLE_PHRASE` names it and a test pins it, so a reword breaks this build
rather than their catalog, but that is a splint, not a fix.

**The fix is one additive integer on `Compilation`** — `resolution_subjects`, the count of rows
resolution was actually applied to, i.e. the denominator `fully_resolved` quantifies over. Then
`fully_resolved=true` beside `resolution_subjects=0` is self-evidently vacuous with no prose anywhere
and no new vocabulary. This is the same "keep the parts, compute the convenience" pattern as
`vrs_alleles`/`vrs_alleles_identified`, whose comment already argues it in as many words — *"Both `0`
means no resolution table was present, i.e. nothing was attempted, which is not the same as nothing
achieved"* — and the argument was simply never applied to the flag sitting beside it. Additive, and a
manifest field was never inside `artifact.digest`.

**Two things not to do.** Do not make `fully_resolved` tri-state or `None`-able: it is typed `bool`,
consumers branch on it directly, and that is a breaking read for everyone to fix a case an additive
sibling describes better — the reporter asked explicitly for this not to happen. And do not treat the
counter as a substitute for **RM43**: it makes the vacuity visible, it does not make the tables
joinable.

**Open design question, worth settling with S8 rather than alone:** one counter or two. The denominator
of `fully_resolved` (variants in scope) is the cheap, self-evident half. A second count — table rows
that cannot be joined — is what the prose actually carries today, and it overlaps the structured
`checks_run`/`checks_skipped` record S8 asks for. Deciding them together avoids shipping two shapes for
one question (P5). **Settled in [RM45](#rm45--the-manifest-is-rich-about-resolution-and-silent-about-verification-so-unchecked-and-clean-are-one-state-to-a-downloader): three separate things, three homes.**
The denominator is this item's, and it is not blocked by RM45; the unjoinable-row count belongs with
RM43's warning; neither is a member of a verification-checks map, because resolution is not a
verification pass and folding a row count into "which checks ran" overloads that map's axis (P5).

## RM45 — the manifest is rich about resolution and silent about verification, so `unchecked` and `clean` are one state to a downloader

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

## RM49 — a spec directory is flat, so a legible `derived/` layout is one the compiler refuses

**Severity** low-medium (a presentation gap with a working workaround; the reporter's own layout is
transport-only because of it) · **Status** open — **0.6**, gated on deciding the *write* side · **Owner**
compiler (path resolution) + enricher (where it writes) + format (any shared constant) ·
**Motivating case** a registry giving publishers a readable spec tree, then finding a downloaded module
does not recompile where it sits (S26 in [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**The ask is narrow and reasonable.** Nothing in a spec listing says which files a human wrote and which
`just-dna-enricher` produced — `module_spec.yaml`/`variants.csv`/`studies.csv` against `resolution.csv`
and the four fact tables, with `sources.csv` genuinely both. A `derived/` subdirectory says it at a
glance. The compiler resolves authored and derived tables at the spec root **and only there**, so that
tree is one `compile` refuses; the reporter flattens on upload and re-splits on download, which works and
means the layout can never be more than presentation. They ask for a *tolerated* input location, not a
required one. The byte-attestation half of S26 shipped in 0.6.0 (`manifest.derived`); this is the half
that did not.

**Why it is not the one-line change it looks like.** `spec_dir / "resolution.csv"` is resolved in **eight
places across two packages** — `validate_spec`, `compile_module`'s resolution and fact-table loops, and
four enricher passes (`enrich`, `frequencies`, `identifiers`, the CLI's inspect path) — so a fallback
added in the compiler alone gives a module that compiles from `derived/` and silently re-enriches to the
root. That is the `locations` failure mode exactly: four parties must agree on a layout, and every
disagreement there so far has been silent.

**The decisive argument, and the reason this is a design round rather than a fix.** Tolerating the layout
on *input* without deciding the *write* side is incoherent, and it breaks on first use: run `enrich` on a
downloaded split module and the enricher writes `resolution.csv` to the root, so the module now carries
both `derived/resolution.csv` and `resolution.csv` — the collision case, reached by following the
documented workflow rather than by misuse. Any acceptable design answers where the enricher writes when
a `derived/` already exists, and what happens when both copies are present and disagree. Note that a
collision cannot be resolved by "newest wins" or by merging: these tables are fact-hashed and
human-overridable, so two copies are two legitimate claims and picking one silently discards a curator's
override.

**Three candidate repairs, and why each is wrong:**

- **Search any subdirectory** (what the registry does on upload). Wrong here: it makes the compiler walk
  the tree, and both S16's unknown-file tolerance and `_check_misspelled_tables`' near-miss guard assume
  one level — a typo'd `derived/varaints.csv` would be invisible to the check written precisely to catch
  that, so the feature would re-open the hole a previous item closed. A single fixed directory name is
  the only version that keeps the guard meaningful.
- **Make `derived/` canonical** — `reverse_module` emits it, the enricher writes it. Wrong: P3 keeps the
  flat spelling working as an alias regardless, so this buys two supported layouts instead of one and
  makes `reverse` emit a tree older compilers in the same major cannot read. A layout migration is a
  major-version move dressed as a convenience.
- **Extend it to the authored tables too**, for symmetry. Wrong, and it is the tempting one: the authored
  CSVs are what `content_signature` reads and what the human-authorable gate is about. Two legal
  locations for `variants.csv` means a module can carry two, and the one the compiler ignores is invisible
  — the silent-success shape this codebase treats as the worst kind of mistake. The asymmetry is the
  point: only machine-written tables move, because only they have a machine that knows where to put them.

**What a shipped version probably looks like**, recorded so the next pass does not re-derive it: one
constant naming the directory, in the **format** tier so both consumers import rather than copy it (the
`locations`/`README_CANDIDATES` precedent); a shared resolver that prefers the root and falls back to the
subdirectory; an **error, not a warning**, when both exist, naming both paths; and the enricher writing
beside whichever copy it read. No new CLI flag — the layout is discovered, not declared.

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
  flag and (since 0.5) validates it against the published list; deciding what to report to
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

**Additivity has two axes.** A new version may expand the **column-set** (new optional columns) *and*
the **row-set** (one authored row compiling to several — e.g. a one-to-many rsid → one row per locus).
Both are minor-legal: a new **optional** column leaves the authored identity untouched (it is omitted
from `content_signature`) and moves only a recompile's `artifact.digest`, which P4 already scopes to a
fixed `compiler_version`. Row-set expansion changes identity
*cardinality* but is **not** a schema break: it is resolver behavior pinned on the `compiler_version`
axis (P4 already pins the digest to the resolved reference), so the GRCh38 expansion ships now. Only
the *build-aware* generalization (which/how-many loci per build, cross-build annotatability) is RM15.
The idea is to pile genuinely rule-tripping edge-cases (requiredness demotions, retypes, identity-key
*semantics* changes) on the 1.0/RM15 piles instead of forcing them into a minor.

Version-axis note: `schema_version` is `"1.0"` while the packages are `0.x` (now `0.5.0`). At `1.0`,
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

**Severity** low · **Status** split by the charter amendment — **wiring it is 0.6; removing it is 1.0**

Always set equal to `start` — no source column feeds it. **Disposition:** wire it to a real end
coordinate (an additive change to an existing optional column, so a minor) or remove it outright at 1.0
(removal is what the amended rule reserves for a major). **Re-examined in 0.5 and
deliberately left here** rather than wired inside the window: wiring a second coordinate buys an
off-by-one unless the first one's convention is unambiguous, and half of that was still open — every
tier *stored* Ensembl's 1-based position while `VariantRow.start`'s own description said "0-based",
which is the text `describe`/`requirements`/`reference` print at an author.

That half is now closed: the authored `start` descriptions say 1-based VCF POS, and
`schema/tests/test_coordinate_convention.py` pins the prose to what the minting code actually does.
What remains is the genuine design question — whether an `end` is interbase-half-open (VRS) or
inclusive (VCF-ish), which is the same choice RM15 has to make for a build-agnostic identity, so the
two stay paired.

### `weights.parquet` `likely_pathogenic` / `likely_benign`

**Severity** low · **Status** queued for 1.0 — remove; wiring rejected in 0.5

Always `False`; no CSV column feeds them — dead output. **Disposition:** Remove at 1.0, or wire to
the `clin_sig` tier. **Re-examined in 0.5: removal is the answer, and wiring was rejected.**
`clin_sig` is itself materialized into `weights.parquet` and `derive.pathogenic_from_clin_sig`
already maps `likely_pathogenic → True`, so a wired column would tell a consumer nothing it cannot
already read. That argument is unchanged by the charter amendment — wiring is cheap now and still
pointless — while the **removal** stays major, which is the half the amendment does speak to.

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
mode — `best_effort` warns and compiles with the authored label (digest stable, round-trip intact),
`strict` **refuses**, on the grounds that an all-or-nothing artifact should not be built on an
identifier its own source has retired. Failing is the honest move because it pushes the fix to where it
belongs: an authored edit.

That last clause is now load-bearing rather than rhetorical, and it is what qualifies this check for a
mode ladder at all. This entry used to cite "the VRS-unverifiable decision" as its precedent; that
decision was reversed in 0.5 for the half of it where **no authored edit could clear the finding** (an
indel the compiler cannot recompute stays a warning in both modes), which is precisely the test this
item passes and that one did not. An obsolete rsID is a cell a human can rewrite.

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

## Freeform suggestions — the 0.6 idea-book

- ~~**IUPAC ambiguity codes in `ref`/`alts` — expand `Y` to `C,T`**~~ — **probed and rejected as
  specified; one small real defect survives it.**
  ([the code table](https://www.bioinformatics.org/sms/iupac.html): `R`=A/G, `Y`=C/T, `S`=G/C, `W`=A/T,
  `K`=G/T, `M`=A/C, `B`/`D`/`H`/`V` for the three-base sets, `N`=any, `.`/`-` a gap.) Recorded in full
  because the *reasons* it fails are reusable, and because the first draft of this entry asserted a
  premise nobody had checked.

  **The load-bearing premise has no instantiation.** The proposal rested on a code in an ALT column
  being a *compressed ALT set* — `Y` written once instead of `C,T`. Probed: **zero** occurrences of
  `R`/`Y`/`S`/`W`/`K`/`M`/`B`/`D`/`H`/`V` in REF or ALT across all **4,439,382** ClinVar GRCh38 records,
  and zero across all sixteen modules in this tree. Genuine ambiguity codes live in *sequence* contexts
  (consensus FASTA, array-manifest probes) and in *genotype* contexts (a Sanger heterozygote written
  `Y`) — the second of which is a **measurement**, so it is the consumer's by charter, and
  `AuthoredModel`'s genotype validator already refuses it with a clear message. Not one of them is a
  variant record's ALT. This is the "mechanically possible, never instantiated" anti-finding the
  dogfooding rule exists to catch, and the first draft of this entry walked straight into it.

  **The non-ACGT alleles that *are* real are `N`, and they are two different things, neither
  expandable.** 35 ClinVar records carry a single-base `A>N` — *the substituted base is unknown*, so
  expanding to `A,C,G,T` would assert four alleles ClinVar never stated. 633 more carry `N` **inside** a
  longer allele (`TAAAAAT…TTTGG` + `NNNNNNNNNN` + `AAAA…`) — unknown *interior* of a known-length
  insertion, not an ambiguity code at all, and 4¹⁰ expansions of nonsense. A rule keyed on "every
  character is a nucleotide or an IUPAC code" files the second as an ambiguity code, which is precisely
  the false claim `cpic.unusable_allele_reason` was already repaired to stop making about `DELTCT`.

  **And it is already solved, in the right place.** `clinvar_build` filters `^[ACGT]+$` on both alleles
  at the **snapshot builder** and counts what it skipped, so none of those 668 records ever reaches a
  drafted module. Skip-at-the-source-boundary is the pattern; it is implemented; for the only non-ACGT
  ALT that exists in real data it is the correct answer.

  **Both halves of the proposed repair were also wrong on their own terms**, and these are the parts to
  remember:

  * *"Normalize at the enricher boundary, like ClinGen's dosage codes."* The analogy does not hold.
    Those are decoded while **reading a source into rows the enricher authors**. An ambiguity code in
    `variants.csv` is **authored data**, where the enricher's standing rule is *report, never repair* —
    rewriting an authored value destroys the evidence of the upstream bug. The only legitimate site is a
    drafting provider at the moment of transcription, and every provider that meets one already refuses
    correctly.
  * *"Have the compiler reject the code by name."* Far larger than it sounds, and pointed the wrong way.
    **No nucleotide grammar exists on any of the eleven `ref`/`alt`/`alts` columns across six models** —
    `vocab.validate_allele` has exactly one user, `HaplotypeRow.allele`. Introducing one would reject
    `<DEL>` and `N` alongside `Y`, i.e. tighten the very field **RM5** exists to widen. It is also
    **Principle 3-illegal on the published line**: a module with `alts="Y"` *compiles today* under
    `best_effort` (the locus is dropped with a warning), so a grammar would stop an existing module
    validating. The first draft claimed such a module "is already broken by it" — checked, and false.

  **What survived was small, and it shipped.** `hosting_verdict("C/T", "T", "Y")` returns a confident
  **`False`**: a substitution locus has no spelling freedom, so a non-nucleotide alt reads as a positive
  contradiction. The author was told *their genotype does not fit their own locus* — true of the cell,
  false of the variant, and three steps from the actual mistake. A **diagnosis** defect rather than a
  grammar one, so fixing it needed no decision about what `Y` means:
  `alleles.non_nucleotide_reason`/`non_nucleotide_alleles` (format tier, the single definition
  `cpic.unusable_allele_reason` now delegates to) classify the offending allele, and both "cannot host"
  call sites say which of the two it is. Additive, digest-neutral, tightens nothing, orthogonal to RM5.
  The verdict itself is untouched — `False` was never the wrong answer, only the wrong explanation.


- **What an artifact should carry of the 0.3 axes — the residue of the `direction` report, and a 1.0
  question.** The documentation half shipped in 0.5.2: COMPILER.md's coverage row now names the tier
  each tick belongs to, and § Upgrade derivation says outright that `weights.parquet` carries the
  **authored** `direction` only, that an empty one on a legacy module is correct, and that a
  parquet-side consumer applies `derive.direction_from_state(state, weight)` itself. What is not
  settled is whether the artifact should ever carry the derived axes at all — a design question, not a
  version one: what bars it is that filling a blank asserts what no curator wrote. The candidate repairs
  and why each is wrong today —
  *populate at compile* asserts an axis no curator wrote (`state='significant'` has no direction, so
  one gets invented from the weight sign), *trim `state` to a derived mirror on load* is `upgraded()`,
  which belongs to the publisher's `needs_upgrade` flow rather than to the compiler, and `state` stays
  required under P8 regardless. Note for whoever picks it up: there is no numbered `RMn` for the 0.3
  orthogonal-axes work — it shipped in 0.3 and is tracked only in COMPILER.md, which is part of why
  this gap sat unattended. Reported as S5 in [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md).

- **Rename the compiler's resolution master switch.** `compile_module(resolve_with_ensembl=False)`
  now *warns* when an injected `resolution.csv` is present and being ignored (0.5.2), which closes the
  silent-success half. The name is still wrong — it says Ensembl and means resolution of every kind —
  and a rename is a published-signature change, so `resolve` / `resolution=off|table|cache` is a 1.0
  item rather than a patch.

New ideas enter here as freeform suggestions, then graduate through the design cycle
(feedback → USE_CASES lens → PROPOSAL → shipped or parked as an `RMn` above).

