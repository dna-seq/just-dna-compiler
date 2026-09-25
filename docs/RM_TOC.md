# `RM` table of contents — every roadmap item and where it actually lives

**The single complete list.** Nothing else was: [ROADMAP.md](ROADMAP.md)'s detail table covered
RM4–RM7 / RM10–RM17 / RM20–RM27, [USE_CASES.md](USE_CASES.md)'s covered RM1–RM14 / RM18–RM22, neither
was sorted, RM28–RM35 lived only as prose paragraphs, and the major-version items are not numbered at
all. So `RM33` was genuinely unfindable. This file exists to make that impossible. ROADMAP.md's active
list ran empty after the 0.6 batch, filled again with RM74–RM79, and emptied again when those shipped —
which does not retire the argument in either direction. An item that moves leaves a pointer at where it
used to live, and that is the same defect one document over.

**Paged by number since 2026-09-25**, because one file had grown past 600 lines. Each page holds every
item in its hundred, under the status or round heading it had in the single file:

- [items 1–99](RM_TOC_000_099.md)
- [items 100–199](RM_TOC_100_199.md)
- [items 200–299](RM_TOC_200_299.md)

**Add an entry whenever you add an item, on the page for its hundred.** A new item goes under that
page's *⏳ Open, no release decided* heading until its release is decided. Item 300 opens
`RM_TOC_300_399.md`, which also goes into `mkdocs.yml`'s nav beside the others. Search all pages at
once with `grep -n 'RM47' docs/RM_TOC*.md`. **Page labels never spell an unfiled number with the
`RM` prefix**: the allocator counts every `RMn` string under `docs/` as used, and a label reading
"up to 299" that way once made it skip to 301. If you find yourself wanting a second index somewhere
else, don't: two partial lists of the same 35 items is what caused this one.

**Claim the number with `.claude/rm-next.py`, never by reading the highest one off this file.** An
index is not an allocator: reading a number claims nothing, so two sessions a minute apart read the
same answer and both write it — which happened on 2026-09-01, when two sessions sharing one working
tree filed different work as RM159 (git `741ec59` renumbered one to RM161). The allocator scans every
document under `docs/` and *reserves* the next number in the same locked write, appending a
`🔷 reserved` row under *Reservations* below. When you write the item, put its real row on the page for
its hundred and delete the reservation, or `--release` it, which leaves a `✖` tombstone here, because
ids are never reused.

**Shipped items now live in two files, which is exactly why this one is worth keeping.**
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) starts at the 0.6 design round;
[ROADMAP_HISTORY_PRE_0_6.md](history/ROADMAP_HISTORY_PRE_0_6.md) holds the 0.5 line and everything before it.
A reader should never have to guess which half an item is in — follow the link from here.

Format of an entry: the **number** links to the authoritative entry, the one to edit. *also in* lists
every other document that mentions it, so a rename or a status change can be propagated without
grepping.

---

## 🔷 Reservations — numbers claimed, entries not yet written

The allocator writes here. A row below is a number some session has claimed; it moves to its page when
the entry is written.

## 🔒 The major bucket — unnumbered on purpose, and that is why it hides

Everything needing a **major** lives in one table in
[ROADMAP § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker). These have **no `RMn`
number**, which is why they are easy to lose. They are not deferred features — each breaks a rule
Principle 3/8 protects, so a minor cannot carry it.

**Read this list under the amended cadence** (CONSTITUTION § 0.6 amendment, 2026-08-12): *deprecate in a
minor, remove at the next major*. An item whose replacement already exists takes its warn-only
deprecation in a 0.x release and is **gone at 1.0**, not deprecated at 1.0 and lingering to 2.0 — the
entries below still phrased the old way are stale, not decided. What genuinely keeps the old shape is
whatever Principle 8 makes mandatory (`state`, the `pathogenic`/`benign` booleans), because an author
cannot comply with a warning about a field they must still set. Every item here also owes an upgrade
line under **RM52**, which is release-blocking for 1.0.

- `VariantRow.state` — deprecate at 1.0, remove at 2.0; a derived alias of `direction` since 0.3
- `state` values `alt` / `ref` — drop from the read-vocabulary; genotype-relative descriptors
- `VariantRow.pathogenic` / `benign` — deprecate → remove; lossy aliases of `clin_sig`
- `StudyRow.p_value: str` — retype (the numeric companion `p_value_num` shipped in 0.5)
- `weights.parquet` `end` — **split by the charter amendment: wiring it is 0.6 work, only the removal is major.** Either way it needs an *end*-coordinate convention (interbase-half-open vs inclusive), the same choice RM15 must make. The authored `start` is settled: 1-based VCF POS, pinned by a test
- `weights.parquet` `likely_pathogenic` / `likely_benign` — remove; dead output, wiring rejected in 0.5
- `VariantRow.weight` vs `effect_size` — review whether `weight` is subsumed
- Deprecated flag / vocab aliases — collapse to the canonical vocab
- `ModuleManifest.authors` + free-form `curator` — fold into RM14's structured record
- `StudyRow.pmid` required — **doi-first**: require ≥1 of `{doi, pmid}`; a requiredness demotion. Pairs with RM50, which carries the PMCID axis and the `LiteratureRow` key
- `sources.csv` — **rename** (recommendation: `licensing.csv`). The *input* half is RM51 and shipped in 0.6.0; what waits for the major is `sources.parquet` (inside `artifact.digest`) and the `manifest.sources` key — both removals. The old CSV spelling is deprecated in 0.6 beside the alias and **removed at 1.0**, on the amended cadence this item prompted. It is a licensing/attribution ledger whose name collides with the `source` *column* meaning "which link answered" (the overload RM33 had to split) and with the ordinary sense in which `studies.csv`/`literature.csv` are sources too
- `fetched_at` — **rename** on all seven sidecar models (`updated_at` or `recorded_at`; the choice encodes a semantic decision about whether a provenance-column rewrite restamps). The name says *fetch*; measured, a re-run never restamps, so the value dates when the row's **facts** were set. Outside every fact set, so no signature moves and only `artifact.digest` does — which is why the disposition is to **bundle it with the `sources.parquet` rename above**, not to schedule it alone
- Compiler `ensembl_cache` shim — remove the deprecated parameter outright
- ~~Coordinate-first identity~~ — **resolved in 0.5** by VRS; kept struck through for traceability

## The other trackers

| Tracker | Where | What it holds |
|--------------|----------------------|----------------------------------------------------------------|
| Reserved namespace | [ROADMAP § Reserved namespace](ROADMAP.md#reserved-namespace) | Names withheld because a release will plausibly claim them (Principle 5). Three: `reference_db`, plus `callable_element` / `quality_element`, the two element-rule columns RM54 decided against building. |
| Freeform idea-book | [ROADMAP § Freeform suggestions](ROADMAP.md#freeform-suggestions--the-05-idea-book) | Unshaped ideas — the 0.5 book, plus **Parked in 0.5** (recorded so they are not re-proposed as new) and a [0.6 book](ROADMAP.md#freeform-suggestions--the-06-idea-book) below it. |
| Not format scope | [ROADMAP § Annotating core](ROADMAP.md#annotating-core-not-format-scope-the-05-source-assessment) | Half of every source assessed: anything that *calls or interprets* is a consumer's job. |
| Design threads | [PROPOSAL_0_6_PT2](proposals/PROPOSAL_0_6_PT2.md), [PROPOSAL_0_6](proposals/PROPOSAL_0_6.md), [PROPOSAL_0_5_1](proposals/PROPOSAL_0_5_1.md), [PROPOSAL_0_5](proposals/PROPOSAL_0_5.md), [PROPOSAL_0_4_1](proposals/PROPOSAL_0_4_1.md) | Where an item's shape was argued before it became an `RMn`, one file per release line — **two for 0.6**, because a second round of items landed behind the first and PT2 re-asked which release they belonged to. |
| Dogfooding ledgers | [DOGFOOD_0_6.md](probes/DOGFOOD_0_6.md) (the plan) + [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md) (what it found) | Findings from using the shipped CLIs on real modules. Only the `surface` half becomes an `RMn` — RM68–RM72 — so the `fix` half is findable **here and nowhere in this index**, by design. |
| What shipped | [CHANGELOG.md](CHANGELOG.md) | Newest first. The statuses above summarize it. |

## Where an item comes from

An `RMn` is stage 5 of the design cycle, not its start: a field report
([CONSUMER_SUGGESTIONS](CONSUMER_SUGGESTIONS.md)) → run it against the bricks
([USE_CASES](USE_CASES.md)) → shape it (the release's proposal file) → then either **shipped**
(recorded in [COMPILER.md](COMPILER.md)'s coverage table) or **parked as an `RMn`**. An item with no
trail through those was found by dogfooding or by an audit: RM31–RM35 came from the 2026-08-03 round,
RM53–RM67 from the VCF 4.4 audit, and RM68–RM72 from dogfooding the 0.6 batch on 2026-08-13.
