# Constitution — amendment history

Why each amendment to [CONSTITUTION.md](CONSTITUTION.md) was made: what the old wording said, what
broke under it, and what was rejected. **The rules themselves are not here** — every one of them lives
in the charter, and this file records only the reasoning behind them.

The split exists because the charter is read in full before any decision and its *Rules only* header
item bans reasoning, evidence, superseded states and outward references from it. That ban is what
keeps the charter short; this file is where the material it excludes goes, so nothing is lost. Unlike
the charter, this file may cite roadmap items, consumer reports and other documents freely.

**An entry here is history, not authority.** If it disagrees with the charter, the charter wins — and
the disagreement is a defect in this file.

Newest first.

## 0.8 — the format package also defines the reference-snapshot layout (2026-11-04)

Recorded in Goals as the second bullet, *Be the contract for the reference-snapshot layout as well*.

Goal 1 scoped `just-dna-format` to "annotation modules", and a reference snapshot is not a module. No
principle forbade moving the snapshot layout down into this package: it brings no network and no new
dependency (pydantic and the standard library, plus the package's own atomic writer). But it widens
what the package is for, so it is recorded as a deliberate amendment rather than as a side effect of
[RM303](ROADMAP_HISTORY.md).

**What broke.** A snapshot is `data/*.parquet`, optional sidecars, `LICENSE.txt` and `release.json`, and
six parties have to agree on those names: the builder, the publisher, the provisioner, the resolver, the
reporter (`cache status`) and every pass that reads a release. The names were constants in the
enricher's `locations.py`, so another repository wanting the layout had to import the network tier,
and `release.json` had no model at all: fourteen builders wrote it by hand at fifteen sites. The keys
drifted (`rows` beside `row_count`, `licence` beside `license`, `builder` beside `builder_version`), and
one drift reached a user. ClinVar's builder wrote its release as `clinvar_file_date` and no `dataset`,
so `cache status` printed a blank label for the one snapshot that refreshes weekly (RM180/RM182). The
repair then was a per-lane reader in the enricher, which fixed the reader and left the contract as it
was. With the model in this package, the builder writes `dataset` through the same formula the model
uses to read an older ClinVar snapshot, and the per-lane reader is gone.

**Why here and not elsewhere.** `release.json` is the snapshot's twin of `manifest.json`, the module's
provenance record this package already owns, and pydantic is already its one dependency.

**Refused on the same day.**

- **Renaming `just-dna-format`** (to `just-dna-schema`, the workspace directory's name). With the
  snapshot contract added, "format" is *more* accurate: the package now defines two on-disk formats. A
  rename would touch about 130 importing files across five repositories and keep two distribution
  names alive for a major. Refused by the maintainer.
- **A `just-dna-datasets` / `just-dna-builders` package.** First offered in the RM261 round on
  2026-09-25 and declined then without being recorded. It forms a cycle (builders need the layout from
  the enricher, and `cache rebuild` needs the builders), and breaking the cycle means moving the layout
  below both, which is this amendment; after that a separate package buys nothing. Its dependencies
  would be the enricher's own, every snapshot change would become a release of two packages, and since
  builders fetch it would also need a Goal 2 / Principle 2 amendment naming a second tier that may.
- **A nano-library holding only the convention.** Too small to be a package of its own, when this one
  already depends on pydantic and already owns the module's provenance record.

## 0.6 — release class and artifact staleness are different axes

Recorded in Principle 3 as *Release class and artifact staleness are different axes* and *Authored
identity is not the sizing test*.

Principle 3's additive sentence used to offer *the authored identity is unchanged, and only a
recompile's `artifact.digest` moves* as its reason for sizing a new optional column as a minor. Read
as an explanation that is correct; read as a **criterion** it sizes every change to a derived facet as
free — and it cannot object, because `content_signature` excludes derived values by construction, so
the test is incapable of failing there.

[RM121](history/ROADMAP_HISTORY_0_6.md#rm121--manifeststats-described-one-table-and-was-published-as-if-it-described-the-module)
was sized exactly that way: `manifest.stats.genes` had its derivation corrected in a patch, on the
recorded ground that *"`manifest.json` is outside `artifact.digest` and `stats` outside
`content_signature`, measured."* True, and incapable of being false.

**Measured while answering [S62](CONSUMER_SUGGESTIONS_HISTORY.md)** from just-dna-registry: all sixteen
`reference_examples/` compiled under `v0.6.1` and again under `0.6.6` from byte-identical spec inputs,
across an interval that is entirely patch releases — **six of sixteen changed a published, indexed
manifest field with *both* hashes byte-identical**, which no consumer can detect by any means the
format offers. The registry that hit it had to rebuild and republish a catalog on a patch, a cost its
policy reserves for minors.

**Three moves, and the middle one is the load-bearing permission.** The amendment names the change
class the three sizing rules had no row for — a corrected derivation, which adds, removes and retypes
nothing. It permits such a correction in **any** release, on the ground that it is a bug fix and
deferring it to a minor means knowingly serving a wrong value meanwhile. And it requires the
declaration in exchange, which is the same *permitted but not unmitigated* bargain the retirement
amendment struck for a major.

**What was rejected.** Sizing the change class as a minor: rejected because a bug fix cannot wait for
one. Reconciling the two tests into a single rule: rejected because they answer different questions,
so the axes separate rather than reconcile. An earlier draft of this amendment also indicted
`StudyRow.curator` shipping in 0.6.5 — **withdrawn**, since `curator` is additive, no already-published
module can carry it, and no stored value became wrong.

Unusually, it **adds a permission and an obligation together**. The permission was already being
exercised before anyone wrote it down; only the obligation is new. The declaration mechanism itself is
[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output);
when this amendment was written it did not exist, so the charter briefly required a channel that was
still to be built. It shipped in 0.7 (2026-08-28) as the `ReleaseRecord` a release declares and the
`sweep` gate that measures a movement against it.

**0.5 amendment — the network tier.** Goal 2, the two Non-goals on dependencies and network, and
Principle 2 were amended to introduce `just-dna-enricher`: a third, network-capable tier that
*produces* the injected `resolution.csv` the compiler consumes. The change is additive and scoped, not
a reversal — `just-dna-format` and `just-dna-compiler` become *more* strictly inject-only (they own no
source convention and never fetch), and HuggingFace/httpx/tenacity are confined to the enricher, never
reaching the dependency-light tiers a verify-only or compile-only client installs. This completes the
`just-dna-datasets`/"cache authority leaves the compiler" decoupling recorded in the 0.4.1 plan.

**0.6 amendment — the retirement cadence, and mitigation at a major.** Principle 3's two-step
retirement read *deprecate at the major, remove at the next*, which put every superseded name through
two full major lines and made the cheap half of the process wait on the expensive one. Deprecation
removes nothing and breaks no reader — it is warn-only — so it needs no major to authorize it. The
cadence is now **deprecate in a minor, remove at the next major** (0.6 → 1.0, 1.2 → 2.0), scoped by the
requirement that the warning be **actionable**: a deprecation an author cannot comply with is a finding
no edit can clear, which this project treats as a defect wherever else it appears. This ratifies
existing practice rather than inventing one — `just-dna-compiler`'s `ensembl_cache` parameter has
emitted a `DeprecationWarning` since 0.5 while continuing to work, with removal queued for 1.0, which
is precisely the shape the old wording forbade. The same amendment adds the obligation that a major
carry its **upgrade procedure**: the charter has always permitted breakage at a major, and now requires
it to arrive mitigated.

**0.6 amendment — what a schema change costs, by layer.** Principles 3, 4 and 8 rule on whether a change
is *legal*: additive is minor, removal and promotion-to-required and retyping are major. They say nothing
about what a legal change *costs*, and the absence has been showing up as a recurring instinct that there
are "too many tables" — an instinct that is correct about some additions and wrong about others, with no
stated way to tell which. The cost of an addition depends on the layer it lands in:

- **Parquet columns — approximately free.** Materialized and derived; no human ever types one, and an
  author cannot see one. A stamped, compiler-managed column is the cheapest thing this format can add.
- **Derived CSVs — half.** Machine-written, so no author has to learn the shape; but a human *can* still
  open and edit one, and that should be discouraged rather than merely unmentioned.
- **Authored schemas — full.** A human writes them. Every column is a burden on the rare author, and it
  is that author the DSL exists for.

Two consequences make the rule operative rather than decorative. First, the *one concern per table, do
not burden the rare author* gate is a rule about the **authored** layer: it does not price a parquet
column at all, and it prices a machine-written sidecar at half. A new derived fact table is not the same
kind of object as a new authored table, and treating the two alike is what made obviously-worthwhile
additions look like sprawl. Second, discouraging hand-editing of a derived file is a live design concern
and not a style note — a derived table that is both machine-written and human-overridable can be edited
into a state that is not merely stale but is a false claim, and that wants a mechanism rather than a
convention.

This amendment adds no permission and removes none: what is legal is unchanged, and every addition still
answers to Principles 3 and 8 first. It states the price so that a design review can weigh a legal change
instead of reaching for an unexamined instinct about file count.

The same 0.5 amendment **removed `duckdb` from the compiler tier**, which is why Goal 2 now names
polars/pyyaml/typer alone. Resolution moved from an in-compiler DuckDB query over an injected reference
to the injected `resolution.csv` table, so the whole SQL/cache-location half went to the enricher and
the compiler became pure-Python. This is a *tightening* of Goal 2's dependency-light commitment, not a
new allowance, and it is recorded here because Goal 2 read as though duckdb were still sanctioned there
for a full release after it had gone.
