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

**A reply's release status is as-of the day it was written, and some are now out of date by design.**
Replies below describe work as *"inside `0.7.0`, bumped and **not tagged**"* or *"in the uncut 0.7.0"*;
0.7.0 was cut, tagged `v0.7.0` and published to PyPI on 2026-09-12, so a reader meeting one of those
sentences today is reading a true statement about a past moment. They are **not corrected**, for the same
reason the consumer's prose is not: a reply is the record of what we told somebody on a date, and a
consumer returning to their own item should find the answer they were given. Correcting them would also
be the treadmill [ROADMAP.md](ROADMAP.md) names in its own status paragraph — *a status line nobody
re-reads is a status line that lies* — and it would add one more set of sentences to re-read at every
cut. No count is given here on purpose, for that reason; grep `not tagged` and `uncut` if you want
today's.

**So there is exactly one place to ask what is released: [ROADMAP.md](ROADMAP.md)'s `**Status:**`
paragraph**, with [CHANGELOG.md](CHANGELOG.md) for what each number contained. Nothing in this file
answers that question, and an `RMn` cited below may have shipped in a later release than its reply names.

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
- **S57** `stats.genes` read variants.csv alone — RM121
- **S58** the binning family has no consumer, and no spec — RM122
- **S59** three attestations that could not have failed — RM123
- **S60** an authored overlay over a derived table — RM124 (0.7)
- **S61** a snapshot-miss finding denied the position beside it — RM125
- **S62** nothing says what a release changed about output — RM126, RM127
- **S63** the three required `ModuleInfo` fields had no description — shipped
- **S64** the attestation binds display metadata — justified; RM133
- **S65** what building RM126's consumer half taught — RM126 narrowed
- **S66** a killed enrich leaves a valid short sidecar — shipped; RM128
- **S67** the better-resolved module got the warning flood — shipped
- **S68** `warnings` is a flat list with no code — RM131
- **S69** the `panel:` deprecation named no replacement — shipped
- **S70** a check counted findings and kept none — shipped; RM130
- **S71** a merge restamped `producer` on records it did not put — RM129
- **S72** `unique_rsids: 0` beside 1,482 rsIDs — shipped; retype → 1.0
- **S73** `pharm_variants.csv` had nowhere to cite — answered; RM132
- **S74** nothing public produced a `ModuleSpecConfig` — shipped `load_spec`
- **S75** p-value and effect size named no analysis — shipped; RM140
- **S76** partial resolution.csv nothing marks — withdrawn; RM141
- **S77** a licence row for a source that fed nothing — shipped; RM142
- **S78** strict compiled over a diagnosed wrong build — shipped; RM143
- **S79** a licence warning printed only the mismatches — shipped; RM144
- **S80** `state`'s six members printed as peers — shipped; RM145
- **S81** unknown column vs newer column, one finding — filed; RM146
- **S82** a hand-read source that yielded no row — shipped; RM147
- **S83** `direction` for a trend whose sign is unestablished — RM148
- **S84** CIViC scored as a source; germline quarter too thin — RM152
- **S85** `not_found` for an rsID the source has — accepted, RM154
- **S86** identifier roster read only variants.csv — accepted, RM155
- **S87** overlay `reason` inside `content_signature` — accepted, RM180
- **S88** `needs_recompile` crashed on an unstamped version — accepted, RM183
- **S89** `CacheLane` lacked its override variable — accepted, RM184
- **S90** a declared correction could not say which modules it reaches — accepted, RM201
- **S91** `cache status` was CLI-only; `lane_status()` + `occupied` — accepted, RM204
- **S92** `LookupClients` had three lazy-build semantics — accepted, RM206
- **S93** lookup payload carried absolute snapshot paths — accepted, RM205
- **S94** a resolver rung that consults a peer — idea-book, licence question first
- **S95** `PacingGate` could not report what it spent — accepted, RM203
- **S96** `sidecar_spellings` keyed on the table key only — accepted, RM224
- **S97** `CacheLane` declared no size — accepted, RM229
- **S98** data written before its licence row, in eight passes — accepted, RM231
- **S99** PubMind drafter thought unreachable under null terms — does not reproduce; FAQ
- **S100** `AcmgReport.clean` was `True` on a run that consulted no list — accepted, RM234; spun off RM235
- **S101** `pgs.csv`'s paragraph claimed a compile gate — doc fixed; `research_tier` is calibration

**Keep this list one line per item.** It is a contents list, not a second copy of the replies: the
detail belongs in each section's `**Status —**` paragraph, where it cannot drift out of step with the
answer it describes. Append a line when an item is archived; ids are never reused.

---

**This file is split three ways, and the contents list above is not.** S1–S24, S27 and S28 —
everything answered in the 0.5 line — moved to
[CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md](history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md) on
2026-08-17, when this file passed 3,300 lines; **S25–S61, everything the 0.6 line answered, moved to
[CONSUMER_SUGGESTIONS_HISTORY_0_6.md](history/CONSUMER_SUGGESTIONS_HISTORY_0_6.md)** on 2026-09-12,
when 0.7.0 was cut and published. What is left here is S62 onward. Both boundaries are a **tag** read
off `git show`, never a date, and both fall on a group heading so no report is separated from the
group that introduces it. The contents list above stays whole and covers all three halves, because
splitting an index is how an item stops being findable — and `triage-state.py --next` globs every
half, so the next id cannot drift from them.

---

# just-dna-registry — what a patch may change about a compiled artifact (2026-08-21)

The first report from this consumer, filed while adopting `0.6.1 / 0.6.1 / 0.6.4` → `0.6.6` across all
three tiers. Not a defect report: every layer of their catalog sweep behaved as documented and still
found nothing to do while an indexed manifest field went stale underneath it.

## S62 — a patch changed a published field, and nothing a consumer can read said so

**Status — accepted, and filed as two items: [RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)
for the surface you asked for, [RM127](ROADMAP_HISTORY.md#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one)
for the thing underneath it that you found without naming.** Nothing ships yet — the second one sizes
the first, and it is the maintainer's decision rather than ours. Your analysis stands in full, and
probing it widened the case twice.

**You understated it, and here is the measurement.** All sixteen `reference_examples/` compiled under
`v0.6.1` in a detached worktree and again under `0.6.6`, spec inputs verified byte-identical across the
interval (only a README moved), and that whole interval is patch releases:

| | measured |
|---|---|
| changed at least one published manifest field | **16 / 16** |
| moved `artifact.digest`, and `artifact.files` with it | **10 / 16** |
| moved `content_signature` | **0 / 16** |

`compilation.compiled_at` is a timestamp and is excluded as noise. The digest movement is not:
`studies.parquet` grew by exactly **257 bytes** on each of the ten, because RM120 added the authored
column `curator`, first present in **`v0.6.5`**. So it is not only manifest fields — **the parquet
schema moved across a patch interval**, which is your `parquet_schema` axis, the one you ranked just
below signature. On your catalog that is a changed column set on every module carrying `studies.parquet`.

**Your third layer is the reason none of this is visible, and it is us working as designed.**
`content_signature` held on all sixteen, because an unset optional column is omitted from it. So the
authored identity really did not move, a digest comparison really is correct to say nothing happened,
and `revalidate` really is right to answer `ok`. Every rule you have is sound and the composition is
still blind. That is the defect, and it is ours.

**One correction to the report, and it narrows the indictment rather than the finding.** RM106 is not
an instance. Our own release table sizes *a warning, a count, an error message* as patch-level
legibility work, so `manifest.compilation.warnings` was never promised stability across a patch and a
consumer pinning warning counts was relying on something we do not offer. Keeping it separate matters
because it is the case *for* your axis decomposition rather than against it: warning text is
patch-legal and a column is not, so a single "did the output change" bit would have been useless to you
even if it existed. The real instances in this interval are RM120 (the column), RM121
(`stats.genes`/`gene_count`, eight modules) and RM119 (`literature.quotes_unchecked`, three).

**And the second finding, which is yours by implication.** Our release table says a new optional
column, table or manifest field is a **minor**; `curator` shipped in a patch, and 0.6.5's own changelog
entry names it — *"Additive only: one new authored column"* — so it was sized deliberately, by a
different test: *"an existing module's `content_signature` is unchanged, verified."* Both tests are
defensible and they are not the same test, and they diverge exactly where you landed. Your premise
*"a compiler patch changes nothing about compiled output"* was never our stated rule; but the rule we
state and the rule we practise disagree, that gap is written down nowhere, and you read the published
half. RM127 records the three candidates and does not pick one. Whatever RM126 publishes has to be true
of what we actually do, which is why it is filed second and blocks the first.

**On your three properties: all three are accepted as constraints, not as nice-to-haves.**

1. **`unknown_interval` as a state rather than an empty result** is the house rule verbatim — three
   values, and `None` is never `False`. You are right that without it the surface is worse than
   nothing, and the reason is the one we apply everywhere: withhold when the answer is unknown, never
   negate. It is in RM126 as a constraint on the type, not a field to add later.
2. **`content_signature` on its own axis** is accepted for your reason. Our sweep says it has never
   moved in a patch; the axis exists so that stays *checkable* rather than remembered, which is the
   distinction that decides most things here.
3. **The guard.** You called the hand-kept map correctly — it is the registry-not-a-list defect with a
   public name, and it is the shape of five of the six RM104–RM111 fixes. Your proposed enforcement is
   right and cheaper than you may think: the sweep in this reply **is** the prototype, and it took one
   worktree and one loop. A map derived that way is a measurement rather than an author's recollection,
   which as you say is the half worth trusting.

**We are not building `should_rebuild`, and your argument for that is the one we would have made.** The
same fact costs you an immutable PATCH and a moved `latest`, and costs `just-dna-lite` a free cache
rebuild. Ours is the fact; the decision stays yours.

**Your `--apply --force` re-baseline is the right thing to run meanwhile**, and your reason for
rejecting a hardcoded "0.6.6 is interesting" check is the same reason we would have rejected it — a
landmark test is a boolean frozen at one era boundary, and it answers wrong for every version after.

**What we did not measure, so you should not read this as covering it.** The sweep is an offline
compile over sixteen specs: it says nothing about enricher-side outputs, so `verification.json` and the
documents RM123 touched were not compared across the interval. If your catalog stores those, treat them
as unmeasured rather than unchanged.

**Your RM107 aside is correctly scoped and needs nothing from us.** It is the *will my next publish
still work* axis, `validate_spec` answers it, and you are right that it does not make a stored artifact
stale. If a hints surface grows a `newly_refused` field it will be because that axis earned one, not
because this item asked.

**One small thing:** `version.contract_compatible` is not ours — there is no `version.py` in any of the
three packages, and no compatibility helper under another name either. We assume the symbol is yours;
we mention it because the absence is part of what you are reporting, and because a reply that let the
attribution stand would put a function in our record that nobody can grep for.
**Correction, 2026-08-21, same day.** Two things in the reply above are wrong and are corrected
here rather than edited out. **`stats.genes` moved on seven modules, not eight** — recounted off the
same compiled corpus. And the reply's framing of the fault was too broad: `StudyRow.curator` shipping
in a patch is *defensible* — it is additive, no already-published module can have it, and no stored
value became wrong — so the release table calling it a minor is the table being strict, not the cut
being wrong. **The defect is RM121 alone, and it is a different change class**: `stats.genes` is an
existing published field whose derivation was *corrected*, so the same spec yields a different value.
That is neither additive nor a removal/retype, and the release taxonomy has no row for it. The sharper
measurement, which the reply should have led with: **six of sixteen modules changed a published,
indexed manifest field while both hashes stayed byte-identical.** [RM127](ROADMAP_HISTORY.md#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one)
is rewritten around that.

<!-- triaged: 0.6.6 · sha b41bdd76f12b -->

**Reported by** just-dna-registry, 2026-08-21, adopting `0.6.1 / 0.6.1 / 0.6.4` → `0.6.6` across all
three tiers. Not a defect report: everything below behaved as documented. The finding is that two
correct rules compose into a silently wrong outcome, and the missing piece is a fact only this repo
holds.

**What we ran.** After `uv sync` onto 0.6.6, `registry upgrade --dry-run` over the catalog — the sweep
whose whole job is to find published versions that should be recompiled under the current contract.

**What we expected.** RM121 changes `manifest.stats.genes` from a `variants.csv`-only derivation to a
union over every authored gene-bearing table. We index that field: a registry's gene facet is fed from
it, which is the consequence RM121's own docstring names. So every already-published star-allele,
diplotype and copy-number module in our catalog is carrying `genes: []` and is unreachable by `?gene=`,
and the recompile that fixes it is exactly what the sweep exists to schedule.

**What happened.** The sweep reported nothing to do, correctly, at every layer:

* Our gap detector compares `manifest.compilation.compiler_version` against the installed compiler under
  your own `version.contract_compatible`. `0.6.1` vs `0.6.6` is a **patch** — same contract — and we
  deliberately do not act on a patch, because acting would mint a fresh immutable PATCH per module every
  time a dependency moved and the sweep would never be finished.
* Our `revalidate` audit re-runs the current `validate_spec` over each version's stored spec inputs.
  It answers **`ok`**, also correctly: nothing is wrong with those specs. The stale value is not in the
  input, it is in an output field that the compiler used to compute differently.

So we have a rule for *"is the stored input still legal?"* and a rule for *"was this compiled under a
contract-incompatible compiler?"*, and both answer no-action. Neither is the question RM121 raises,
which is a third axis: **would recompiling this artifact produce different output than the stored one?**

**We can answer that axis today, but only by doing the expensive thing we are trying to decide whether
to do** — enrich into a scratch dir, recompile, diff. That is minutes per module, catalog-wide, and it
*is* the operation, not a triage for it.

**What we did meanwhile.** Documented an explicit `registry upgrade --apply --force` as the operator's
re-baseline for this release, scoped per module, with a note that it costs a version number each. We
also considered and rejected teaching our detector that `0.6.6` specifically is worth acting on: this
codebase removed exactly that pattern in its 0.18.0 (a boolean frozen at one era boundary, which
answered "no gap" for every version of the following era), under the rule *never date a stored artifact
by testing for a landmark; compare versions*. A hardcoded list of interesting versions is that defect
with more entries.

**RM121 is not the only instance in this release, which is what makes it a contract question rather
than a one-off.** RM106 de-duplicates the `faf95` warning, so `manifest.compilation.warnings` — a
published list — shipped 15 entries where 14 were distinct, and a consumer pinning warning counts sees
one fewer after a **patch**. Two output-visible changes in one patch pair is enough to say the premise
"a compiler patch changes nothing about compiled output" no longer holds, and the premise is what every
consumer's rebuild rule currently rests on.

**What we think is missing.** A machine-readable, offline-queryable declaration of what a release
changes about the *output* of a compile, keyed on the **interval** rather than on a single version —
because the question is always "compiled under X, installed Y". Sketch, and the field names matter less
than the axes:

```python
from just_dna_compiler import rebuild_hints
rebuild_hints(compiled_under="0.6.1", current="0.6.6")
# RebuildHints(
#     parquet_schema=False,          # columns added/removed/retyped
#     parquet_bytes=False,           # a recompile writes different bytes
#     content_signature=False,       # the identity moved  ← the one that must never surprise us
#     manifest_fields={"stats.genes", "stats.gene_count", "compilation.warnings"},
#     unknown_interval=False,
# )
```

Three properties we would need, in descending order of how much they matter to us:

1. **`unknown_interval` must exist and must not be spelled as an empty result.** Asked about an interval
   the installed package has no record of — an artifact compiled under something newer than what is
   installed, or older than the table reaches — the answer has to be *I cannot say*, never *nothing
   changed*. This is your own rule about a value two opposite histories can produce, applied to a version
   table, and without it the hint is strictly worse than no hint: a consumer would stop recompiling on the
   strength of a silence.
2. **`content_signature` needs its own axis, separate from bytes.** For this service a signature is a
   permanent global `409 duplicate_content` claim that only a purge frees, so "the identity moved in a
   patch" is the one answer we would want to fail loudly on rather than merely act on.
3. **The declaration needs a guard, or it becomes the thing it is fixing.** A hand-kept per-release map
   is precisely the shape of five of the six RM104–RM111 fixes, and closing this with one would be the
   defect wearing a public name. We think you already have the enforcement: compile the reference
   examples under the previous release and diff, and fail when the declared hints disagree with what
   actually moved. That also makes the map a *measurement* rather than an author's recollection of what
   they touched, which is the half we would trust.

**What we are deliberately not asking for: a `should_rebuild` verdict.** The same fact carries different
costs per consumer — for `just-dna-lite` a stale cache is a free rebuild, while for us a rebuild mints an
immutable PATCH, spends a version number, and moves what a client tracking `latest` receives. So the
decision is ours and should stay ours; what we cannot get anywhere is the fact.

**One thing that is a different question, filed here only so it is not conflated.** RM107 (a duplicate
`(source, layer)` row is now an error) does not make a stored artifact stale — it makes some *specs*
newly invalid, which is "will my next publish still work?" rather than "is what I stored out of date".
Our `revalidate` already answers that axis by re-running `validate_spec`, and it answers it correctly,
so we are not asking for anything there. If a hints surface ever grows a `newly_refused` field we would
read it, but the existing route works and this item does not depend on it.

**Reproduced against** `just-dna-compiler` 0.6.6 installed, on a catalog of versions stamped
`compiler_version` 0.6.1. Our side of it is in `services/upgrade.py::ContractGap.acts_by_default`, which
now carries this analysis as a comment, and in the 0.20.0 release notes.

# just-module-creator, 2026-08-21 — what the authoring surface does not say, and what saying it costs

Two items filed the same day and deliberately as a pair: S63 asks for a field description on the
three `ModuleInfo` fields that had none, and S64 measures what editing one of those fields costs.
The second is why the first is not the whole answer — the norm belongs where the prose is authored,
and the repair for prose already published cannot live there.

## S63 — the three required `ModuleInfo` fields are the only ones with no `Field(description=…)`, and the catalog shows what that costs

**Status — accepted; shipped 2026-08-24 in `just-dna-format`, as a patch.** Reproduced exactly, in
the tree rather than only in your installed copy: those three are the only fields in the block
carrying no description, and they are the three an author must replace before a spec validates.

**We took your three sentences nearly as written, and the one we widened is `description`.** Your
proposed text is the field's text: what it is for, the 5–15-word band, and — the part that matters —
*say what this module distinguishes, not how it was made*, naming `weighting:`, `authorship:` and
`README.md` as the homes that are meant for methodology. That last clause is why the fix reaches your
sharper half. Four specs sharing a byte-identical fifteen-word methodology sentence is not a length
problem, and a description that said only "keep it short" would not have stopped it: the field whose
job is telling a module apart from its neighbours was doing the exact opposite on four cards at once,
and an author needs to be told where the sentence *should* go, not just that it is too long here.

**We did not add a `max_length`, for your reasons, and a test now pins that it stays absent** — with
the argument in its docstring, so the next person to propose one meets it rather than re-deriving it.
Your framing is right on all three counts: a ceiling refuses a merely verbose spec, refuses it after
the prose was written, and makes finished work retroactively invalid for failing a requirement that
did not exist when it was published.

**What we did beyond the ask, because three named fields is a symptom and the class is the item.**
There is now a guard that walks `_ALL_MODELS` — 28 models — and asserts that **every authored field
carries a description**, as an equality rather than a count. `describe`, `requirements` and
`reference` render these verbatim, so a blank one is the authoring surface going silent at the moment
an author is filling that cell; the three you found were simply the ones where that silence was most
expensive. It was watched failing on the pre-fix state (exactly your three) before being kept. The
corpus is now at zero, and the next field added blank cannot ship.

**On the length norm being an inherited assumption — that is worth more than the fix.** You went and
measured seven published modules rather than asserting the band, found six of seven outside it, and
established that nothing upstream or downstream had ever said so. We had not said it either, which is
why your two documents could assert it in good faith and be unfalsifiable. The field now says it in
the one place an author is looking when they type the line, which is the half neither of us had.

**We agree the registry clamping is not ours and should not be filed there either**, and for your
reason: clamping hides prose an author chose to write while leaving the spec exactly as wrong. Note
that `S64` then argues the repair belongs somewhere the author can still reach *after* publishing,
which is a real tension with "the repair belongs where the prose is authored" — the answer to that
one is where it gets resolved.

<!-- triaged: next-minor · sha be123afbaead -->


`module.title`, `module.description` and `module.report_title` are the three fields an author *must*
replace before a spec validates. They are also the only fields in `ModuleInfo` that carry no field
description at all:

```
$ uv run --project /data/sources/just-module-creator python -c "
from just_dna_format.spec import ModuleInfo
for n, f in ModuleInfo.model_fields.items():
    print(n, '|', f.metadata, '|', repr(f.description))"
title       | [] | None
description | [] | None
report_title| [] | None
icon        | [] | 'Icon name within `icon_set` — the no-logo fallback glyph'
icon_set    | [] | "Icon family for `icon`: 'fomantic' or 'awesome' (FontAwesome)"
color       | [] | 'Hex color for UI theming'
name        | [] | 'Machine name: lowercase, underscores, no spaces'
version     | [] | 'Authored **advisory** version — a human marker …'
```

`just_dna_format.__file__` under `.venv/lib/python3.14/site-packages/`, format 0.6.6.

So an author gets told what `icon_set` accepts and nothing whatsoever about the field that becomes the
subtitle of their module's catalog card. That asymmetry is the whole report — this is a documentation
gap rather than a behavioural one, and we are filing it because we had to measure the published corpus
to find out what the field is supposed to look like.

**What the corpus says.** `registry_search()` against production, 2026-08-21, all seven published
modules, `description` word counts:

```
 79 words  antonkulaga/aggression_anger_snps@2.0.0
 60 words  antonkulaga/cognitive_intelligence@2.0.0
 45 words  antonkulaga/bodybuilding@1.0.0
 38 words  antonkulaga/big_five_personality_snps@2.1.0
 36 words  ksuha-dna/placebo_response_claude@1.0.0
 25 words  antonkulaga/risk_impulsivity_snps@2.0.0
  8 words  eric-mods/lactose_tolerance@1.0.1
```

Six of seven are two to five sentences. The registry renders the field whole, so the 60-word one
occupies **fourteen lines** of its catalog card, which is what prompted this — our owner's read was
that five to fifteen words is the readable band and anything past it looks bloated.

**The sharper half is not the length, it is the repetition.** Four of the five specs in
`data/output/corrected_modules/` end with the byte-identical sentence *"Curated from the GWAS Catalog
(GRCh38), allele/strand-validated against dbSNP with a gnomAD r4 second witness."* — fifteen words of
methodology, the same on four cards. On a search-results page the description's only job is to tell
this module apart from the ones beside it, and a sentence four modules share does the opposite while
costing each of them the majority of their card. Methodology has homes that persist and are meant for
it — `weighting:`, `authorship:`, `README.md` — and none of them is the card subtitle.

**Our side of it, so this does not read as an empty request.** Two of our own documents already assert
*"`description` is one sentence"* (a tool docstring and a table dossier) and we can find nothing
upstream or downstream that ever said so — it was an inherited assumption, not a norm an author could
have read, and the corpus above is what it was worth. We are fixing that on our side now: the norm gets
one home in our `module_spec` dossier, the scaffold's own `next_step` string says it at the moment the
`<<REPLACE>>` is being filled, and the other restatements link rather than repeat.

**Proposed fix — a `Field(description=…)` on the three, and nothing else.** Something like:

- `title` — *"Human-readable module name, shown as the catalog card's heading."*
- `description` — *"One short sentence, roughly 5–15 words: the catalog card's subtitle and the line a
  browsing consumer reads first. Say what this module distinguishes, not how it was made — methodology
  belongs in `weighting:`, `authorship:` and `README.md`."*
- `report_title` — *"Heading for the rendered per-consumer report, which may differ from `title`."*

**What we are deliberately NOT asking for: a `max_length` or a validator.** A length ceiling would
refuse a spec that is merely verbose, and it would refuse it at validate time — after the prose was
written, and for a property that is a matter of taste rather than of correctness. It would also make
the six published modules above retroactively invalid, which is a claim about somebody's finished work
that we do not think is true: they met every requirement that existed. A field description reaches the
author while they are writing the line, costs nothing, and cannot fail a build.

**One thing that is a different question.** Whether the registry should clamp or fold a long
description on the card is a rendering decision and not yours; we are not filing it there either,
because clamping hides content that an author chose to write. The repair belongs where the prose is
authored.

---

## S64 — display metadata is inside the attestation binding, so shortening a card subtitle wipes the closure and produces a byte-identical artifact

**Status — answered (a): the binding is justified, and here is the attack you could not construct.
`short_description` is filed as
[RM133](ROADMAP_HISTORY.md#rm133--a-card-subtitle-has-no-amendable-home-and-the-binding-is-not-where-that-gets-fixed),
open — but not on `ModuleInfo`, because there it would reproduce the defect. And the answer to your
ordering question is better than you expected: registry S16 is *not* gated on us.**

Your measurement is right in every cell, and the `README.md` control is what makes it an argument
rather than a complaint. We are not disputing any of it.

**The attack, and it is in the partition you cited rather than the six fields you listed.** You asked
us to *"split the binding along the line you already drew"* — the `content_signature` partition. That
line is stated in `integrity.py` and it excludes **name, version and namespace** alongside title and
colour. A binding drawn there makes a closure **transferable across a rename**: take a module closed
and signed by a named reviewer, change `module.name` and `namespace`, and the attestation still holds
— the closer's claim travels to a module with a different identity. `content_signature` excludes those
deliberately, *so that a registry strip does not change content identity*, and that is exactly right
for a content-dedup key. It is exactly wrong for an attestation, which is the one artifact that must
not survive an identity change. So the two hashes cannot share a partition, and the reason is not
cost — it is that they answer opposite questions about the same fields.

**Your narrower six-field list does not have that attack**, and we want to be honest about that rather
than let the sharper version stand for both. `title`/`description`/`report_title`/`icon`/`icon_set`/
`color` really are display-only. What that version inherits is the cost **you** named: it has to hash a
*parse* of the yaml, so it acquires every canonicalization question `content_signature` answers, and
when the two disagree about what counts as display an author gets two different answers to "did my
edit count". You asked whether that is the blocker. It is a blocker, and RM82 is the precedent that
settles how much weight it carries: when the binding was last changed, the deciding property was that
newline normalization is *a byte transform needing no loader, no parse and no schema knowledge* — and
the item explicitly refused the obvious next steps (BOM, trailing whitespace, final newline) on the
grounds that each *"makes the binding more content-ish without making it content"*. A field-aware
split is that line crossed deliberately.

**What the binding buys, stated plainly, since that was the ask.** It is the **reviewer's** claim, not
the artifact's. `content_signature` and `artifact.digest` already answer *is this the same data* and
*are these the same bytes*; the binding answers *is this the same document a named person read and
signed off*. A closer reads `module_spec.yaml` — including what the module says it is — and a card
subtitle is a claim about what the rows mean. A module whose rows are honest and whose card
mis-describes them is a real failure mode, and it is the one you said you could not construct: it is
not a substitution attack, it is that the attestation would then cover less than the reviewer actually
reviewed. We would rather it stayed coarse and honest than became precise and partial.

**Now the part that unblocks you, and we think it is the actual answer to the item.** You framed this
as *the binding overriding the registry's rule from a layer below*, and that framing assumes an amend
must **rewrite the stored `module_spec.yaml`**. It does not have to, and there is already a precedent
for exactly this in the format: `normalize.IDENTITY_AUTHORITY_KEYS` — `namespace`, `owner`,
`canonical_id` — are **registry-owned**, stamped beside the module rather than authored into it, and
`strip_authority_keys` exists so a consumer can hand the spec to our validator with them removed. A
registry-amendable display value is the same shape. If `amend_display` stores an override the registry
owns, the stored `module_spec.yaml` is untouched, `manifest.inputs` still matches, `verify_manifest`
still passes, and the closure stands. **So registry S16 is not gated on this item** — it is gated on
whether the amended value is registry-owned or a spec rewrite, which is their call and ours to
support. Please pass that on; we think it is a cheaper route than either of your (a)/(b).

**Which is why `short_description` is filed but explicitly not as a `ModuleInfo` field.** You are right
that a bounded field which still costs a version to fix reproduces the problem in a new place — and
under (a), *every* field in `module_spec.yaml` is on the un-amendable side, so putting it there is that
exact reproduction. Your argument for why a `max_length` on a **new** field is legitimate where one on
`description` is not, is correct and we have recorded it: a field that exists to fit a fixed layout is
specified by that layout, and it invalidates nothing anyone has written. What RM133 has to settle is
where such a field lives so it lands amendable. Your 120-character calibration and the 71-vs-467
measurement are in the item.

**Nothing retroactive to the seven published modules**, agreed, and for your reason.

**And S63's "the repair belongs where the prose is authored" is in genuine tension with this item**,
which we noted there. The resolution is that both are true of different repairs: the *norm* belongs
where the prose is authored, which is why the field description shipped; the *fix for a subtitle
already published* cannot live there, because the module is closed and its bytes are attested. Those
are different problems and it took your two items side by side to see that.

<!-- triaged: next-minor · sha b3e1234da021 -->


Companion to `S63`, which asked for field descriptions on `ModuleInfo.title/description/report_title`.
This one is about what those fields *cost*, and it is worse than we told our own users yesterday. The
registry half is filed as `just-dna-registry` `S16`; **this one is the prerequisite** and the ordering
matters — see the last section.

### The measurement

`assets/fto_bmi`, copied twice. In one copy we edited **one thing**: `module.description`, from 44
words to 11. Nothing else — `diff` over the rest of the file is empty. Compiled both, strict, with
compiler 0.6.6.

| | copy A (44 words) | copy B (11 words) |
|---|---|---|
| `content_signature` | `sha256:d519efda…fbfe` | **identical** |
| `artifact.digest` | `sha256:c3d633f0…aa09` | **identical** |
| `resolution_signature` | `sha256:63ab1af5…fd59` | **identical** |
| `inputs["module_spec.yaml"].sha256` | `sha256:4a010e53…aba0` | `sha256:8ee80caf…7799` |
| `verification` | full closure block: `closed_at`, `closed_by`, `module_hash`, `signature` | **`null`** |
| `compilation.warnings` | `[]` | *"verification.json is stale…"* + *"This module records no closure…"* |

So the edit moved **no content identity, no artifact digest and no fact signature**. Every compiled
byte a consumer receives is the same. What it did move is `manifest.inputs`, and through it the
attestation — a module that was closed on 2026-08-18 by a named closer became a module that *"records
no closure"*, and the record is gone rather than marked stale in the manifest: `verification: null`.

**Our user's framing was "does this really need to cost a version?" The answer we found is that it
costs a version *and* the closure record, in exchange for changing nothing measurable.** That is the
fact we think neither repo has in front of it.

**And `README.md` is the control, measured in the same run.** `manifest.inputs` is exactly
`["module_spec.yaml", "variants.csv", "studies.csv"]`. The readme is not in it — it has its own
`manifest.readme` entry with its own hash, outside the binding — which is why it is freely amendable.
It is also, by a wide margin, the longer piece of prose. The shortest fixable prose in the system is
the one that cannot be fixed.

### Why we think this is a defect and not a design decision we simply dislike

**You have already ruled on this twice in your own tree, and the binding is the only place that did
not get the ruling.**

- `integrity.py:215-218` excludes exactly these fields from `content_signature`, and names them:
  *"**Name/metadata-independent** — the *identity and display* half of `module_spec.yaml` (name,
  version, namespace, title, colour) is excluded, so a metadata edit or a registry strip does not
  change it."* That reasoning is ours verbatim; we are only asking for it to reach one more hash.
- The manifest block holding these six fields is literally called **`Display`**.

So the format already calls them display everywhere except the one place where calling them provenance
costs an author a version number and an attestation.

**And the registry's amend family is already defined in a way that admits `description`.** Their
`amend_readme` docstring: *"Out-of-digest metadata, like the logo and the changelog: the artifact, its
digest and any signature over it stay immutable, so no version bump is needed."* Our table above shows
`description` satisfies that definition byte-for-byte. It is not the registry's rule that refuses it —
it is this binding overriding the registry's rule from a layer below.

Their stated reason for making the readme amendable applies harder here: *"a readme is where a module
says what it is not, and a badly phrased caveat must be fixable without burning a version number and a
`content_hash` that `yank` would not release."* A badly-shaped **card subtitle** is more visible than a
caveat inside a readme — it is the first line of the search grid, and on our production catalog six of
seven modules render it as a paragraph.

### What we are asking for — either answer closes this

**(a) Justify it, and we will teach it.** Name what the binding buys by covering `title`,
`description`, `report_title`, `icon`, `icon_set`, `color`. If attesting display metadata prevents a
real substitution or a real confusion — a module whose rows are honest but whose card lies about what
they are, say — that is a coherent position and we would rather write it into our skills as a cost
worth paying than keep asking. We could not construct the attack ourselves, which is why we are asking
rather than asserting. **A justification is a complete answer and we are not pushing for (b).**

**(b) Or split the binding along the line you already drew.** Hash the content-bearing half of
`module_spec.yaml` into `_INPUT_FILES` — `genome_build`, `defaults:`, `weighting:`, `license`,
`authorship:` — and leave the `Display` half out, the same partition `content_signature` uses today.
An author editing `weighting:` or `genome_build` still drops the attestation, which is right; an author
fixing a subtitle does not.

We can see one real cost in (b) and would rather name it than have it found for us: today the binding
is *"any byte of an authored file"*, which is simple and needs no schema knowledge to verify. A split
binding has to hash a **parse** of the yaml, so it inherits every question about canonicalization that
`content_signature` already answers — and if the two ever disagree about what counts as display, an
author gets two different answers to "did my edit count". If that is the blocker, say so; it is a real
one and it may be what decides for (a).

### A second field, and the length bound we asked you NOT to add yesterday

`description` has two jobs that pull opposite ways: the card's one-line subtitle, and the author's own
summary of their module in their own file. We do not think one field can serve both, and the corpus
says it currently serves neither well.

So: a **`short_description`** on `ModuleInfo` with a real `max_length` — a **character** bound, because
that is the unit a card layout is measured in and the unit a validator can hold. Around **120
characters** matches the readable band our owner named (5–15 words). Calibration from the live catalog:
`eric-mods/lactose_tolerance`'s description is 71 characters and sits comfortably inside it; the
60-word one that prompted all of this is 467.

**We argued against a `max_length` in `S63` and this is not us changing our minds — the distinction is
load-bearing and we would rather state it than have you spot it.** A bound on `description` would
refuse a merely verbose spec, refuse it after the prose was written, and retroactively invalidate six
published modules that met every requirement that existed. A bound on a **new, optional** field
invalidates nothing, refuses nothing anyone has written, and is the field's *definition* rather than a
taste judgement applied afterwards: a field that exists to fit a fixed layout is specified by the
layout. If `short_description` is absent, everything behaves as it does today.

**Whichever way (a)/(b) goes, `short_description` should land on the amendable side of it.** A bounded
field that still costs a version to fix reproduces the problem in a new place.

### Ordering, and why the registry cannot go first

`just-dna-registry` `S16` asks for an `amend_description` (or, and we think this is cleaner, an
`amend_display` covering the whole six-field block, since `title`, `report_title`, `icon` and `color`
have the identical status — their call, not ours). **That endpoint cannot ship before this item is
settled.** Rewriting the stored `module_spec.yaml` would put it out of agreement with
`manifest.inputs`, so a downloaded spec would fail `verify_manifest`; and an amend that *also* rewrites
the inputs entry produces a manifest that is no longer what the compiler wrote, which is worse. The
binding decision is yours and it gates theirs.

### What we are deliberately not asking for

- **Render-time truncation or folding on the card.** It hides prose the author chose to write and
  leaves the spec exactly as wrong. Not filed with the registry either, for the same reason.
- **Any retroactive fix to the seven published modules.** They met the requirements that existed. What
  we want is for the eighth author to have somewhere short to put a subtitle, and a way to fix it if
  they get it wrong.

### Our side, so this is not an empty-handed request

We cannot do any of the above from here — the field, the binding and the card all belong to you and to
the registry. What we could do we have done, in commit `8fb2825`: the 5–15-word norm now has one home
in our `module_spec` table dossier and is repeated in `scaffold_module`'s `next_step`, the string an
authoring agent reads immediately before it replaces the `<<REPLACE>>`. Two older assertions of ours
that said *"description is one sentence"* without saying it anywhere an author looks now agree with it
and name what overrunning costs.

**Reproduced against** format / compiler / enricher **0.6.6** installed (`just_dna_format.__file__`
under `.venv/lib/python3.14/site-packages/`), spec `assets/fto_bmi` in `just-module-creator`, both
compiles strict and green apart from the two warnings in the table.

---

# just-dna-registry, 2026-08-21 — what building the consumer half of RM126 taught them

A follow-up to S62, filed as its own item because S62 was answered and archived the same day. It
carries three corrections to their own report and four constraints on RM126 that were not visible
from this side.

## S65 — we built the consumer half of RM126, and it narrows what RM126 has to publish

**Status — accepted with thanks; your four constraints are written into
[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)
as a section of their own, and the fifth ask — `compilation.dropped_rows` — shipped 2026-08-24 in
`just-dna-compiler`.** S62 stays archived and untouched; your three corrections are recorded here,
which is where a correction to a report belongs.

**On the corrections: all three accepted, and the middle one we would have let stand.** RM106 not
being an instance is yours to take back and you have. `version.contract_compatible` being yours is the
one that matters — a symbol nobody can grep for outliving the report that named it is exactly the rot
we refuse elsewhere, and we only caught it because it was attributed to us. And the flush-left `#`
cost us an archive repair, yes, but the fix landed in the tools rather than as a rule for writers: both
triage scripts are fence-aware now and the archiver refuses outright on a structural finding, because
a writing-side rule had no owner for the case that matters — a `#` in **your** prose is one we may not
touch.

**The roster is the ask we would not have arrived at, and it is the one that shrinks this item.** You
are right that `spec_tables` and `module_stats` together answer the whole authored-row-derived class
without a hints table existing at all, and right that neither landed for this reason. So RM126's job
narrows to *what a consumer cannot recompute*, and the cheapest thing we can publish is **which
manifest fields are pure functions of the authored rows** — a fact we hold and you were guessing at.
That is now the first thing RM126 owes.

**The pre-drop/post-drop boundary is the sharpest thing in the report and we had not seen it.**
`validate_spec` computes `stats` over the full row set and `compile_module` re-derives over the
survivors *only when the drop removed something* — so a recomputation from authored rows is
permanently the pre-drop side for a module that lost the sole row naming a gene, under any compiler.
A roster stating "pure function of the authored rows" without that condition would send you to spend
version numbers on modules that are perfectly current. It is written into RM126 as the roster's
boundary rather than as a footnote.

**`compilation.dropped_rows` shipped, and it is per table rather than a scalar** — `{"pharm_variants.csv": 1}`
— because your guard already catches a `variants.csv` drop via `variant_count`, and what you could not
see is *which* table shrank. An empty dict means nothing was dropped, which is a real answer and not
an absence: the check runs on every compile. The test pins exactly your case, a kind-table drop with
`variant_count` unmoved. **You were also right to reject reading the warning text** — that is our own
catalogue rule and we would have said the same.

**Convergence is now stated in RM126 as load-bearing rather than incidental, in your words.** That the
interval from a version to itself is empty is the property that makes the interval shape correct, and
you are right that a field-keyed or latest-known-defect shape would not have it. That your first design
had the loop in it, and that you found it by building rather than by consuming a verdict, is the best
argument available for the thing you say next.

**Coexistence rather than replacement, agreed and recorded.** We will not scope RM126 around covering
what you currently probe. Your division is the right one and is now RM126's: *we state what a release
did, you check what a specific stored artifact says* — a recomputation checks the artifact in front of
you, a hint states a general fact, and the two fail differently. Keeping a probe whose field a hint
covers is not a vote of no confidence and we will not read it as one.

**And we are not building `should_rebuild`.** You building the decision yourself is what produced the
convergence requirement, the pre-drop boundary and the `variant_count` guard — none of which a verdict
would have surfaced. That is the argument for the split, made by evidence rather than by preference.

<!-- triaged: next-minor · sha 69a2bf56b7ea -->


**Reported by** just-dna-registry, 2026-08-21. A follow-up to **S62**, filed as a new item because that
one was answered and archived the same day — this is what building the consumer side taught us, and it
arrived after your reply rather than before it. Shipped as `services/rebuild.py` in our **0.21.0**.

**First, three corrections to our own S62, since a report we filed is a claim we made.**

* **RM106 is not an instance, and we accept the correction.** We had it in a shipped changelog entry and
  in a test docstring; both now carry the correction rather than a silent edit, because the reason is
  the case *for* your axis decomposition — warning text is patch-legal and a corrected derivation is
  not, so a single "did the output change" bit would have been useless to us either way.
* **`version.contract_compatible` is ours, not yours.** It lives in `just_dna_registry/version.py`, and
  our sentence *"under your own `version.contract_compatible`"* was simply wrong. Thank you for refusing
  to let the attribution stand — a symbol nobody can grep for is exactly the kind of thing that survives
  in a record for years.
* **The flush-left `#` in our fenced block is what truncated S62's span**, and it cost you an archive
  repair. We have written the hazard into our own agent guidelines, and this item is authored without
  one.

**What we built.** For a manifest field that is a pure function of the authored rows, the current answer
can be recomputed from stored inputs — no enrichment, no parquet, no network, just a temp dir and a CSV
parse — using `spec_tables` for the defaults-folded rows and `module_stats` for the derivation itself. A
difference against the published manifest is then *evidence* rather than a version comparison, so our
sweep acts on it under a plain apply instead of asking an operator for an override.

**The hint that matters most: recomputability splits RM126 in half, and you already shipped the better
half.** `spec_tables` (RM116) is what makes the recomputation correct rather than approximate — the
`defaults:` fold is precisely the part a caller reimplements wrongly — and `module_stats` being public
(RM121) is what makes it *your* derivation rather than our imitation of it. Neither landed for this
reason. Together they answer the entire authored-row-derived class without a hints table existing at
all.

So the interval-keyed table only has to cover what a consumer **cannot** recompute. What would help most
is therefore not a bigger table but a small published **roster**: which manifest fields are pure
functions of the authored rows. That is a fact you hold and we currently guess at, and it shrinks RM126
rather than growing it.

**Second: your measurement changed our operator advice, and part of it is invisible from here.** Ten of
sixteen moving `artifact.digest` on a 257-byte `studies.parquet` growth is not something we could have
found from outside, and it is now written into our code as the reason a digest comparison cannot stand
in for this axis. We also took the note about your sweep's own limit literally:
`literature.quotes_unchecked` (RM119) is a published manifest field we cannot recompute, because it
derives from a sidecar rather than from authored rows — so the enricher-written blocks are now named in
our unmeasurable list rather than quietly assumed unchanged.

**Third: convergence is a hard requirement on anything a consumer acts on unattended, and it is easy to
miss.** Our first design had a loop in it. If a hint fires for a version compiled by the *exact*
compiler now installed, recompiling derives the same value again — so an automated sweep mints a fresh
PATCH every run, forever, which is the failure the "a patch is not a gap" rule exists to prevent,
re-entering through a different door. We close it by refusing to act when the compiler is identical, and
reporting an anomaly instead. **Your interval-keyed shape gets this for free**, because the interval
from a version to itself is empty — worth stating in RM126 as load-bearing rather than incidental, since
a field-keyed or "latest known defect" shape would not have the property. It is also what bounds a false
positive to one wasted version number per module ever, which is what made us willing to act
automatically at all.

**Fourth: the pre-drop/post-drop asymmetry is the exact boundary that roster has to draw, and it cannot
be seen from outside.** `validate_spec` computes `stats` over the full row set; `compile_module`
re-derives them over the survivors **only when the symbolic-allele drop removed something**. A
recomputation from authored rows is therefore the pre-drop side, so `manifest.stats` and the
recomputation legitimately disagree — permanently, under any compiler — for a module that lost the sole
row naming a gene. "Pure function of the authored rows" is thus **conditionally** true for `stats`, and a
roster that stated it without the condition would send consumers to spend version numbers on modules
that are perfectly current.

We discriminate on `variant_count`: when the recomputed count disagrees with the published one, a drop
happened and we downgrade the whole comparison to *not measurable* rather than reporting drift. Reading
the warning text was the other option and we rejected it for the reason your own catalogue rule gives —
a warning's wording is yours to change, and only the pinned catalogue is an API.

**Fifth, small and additive: a `compilation.dropped_rows` counter would close the residue.** The guard
above catches a drop from `variants.csv`, because `variant_count` moves. A symbolic-allele drop inside a
*kind* table moves no counter a published manifest carries, so from outside it is indistinguishable from
real drift. With such a counter the `stats` half of the roster becomes unconditionally checkable.

**On scoping RM126: please design for coexistence, not replacement.** Our probes sit behind one named
seam so that a probe whose field your hint covers retires by deletion. We may keep one or two anyway,
and that is not a vote of no confidence — a recomputation checks the artifact actually in front of us, a
hint states what a release did in general, and the two fail differently. So RM126 does not need to be
scoped around covering everything we currently probe. The useful division is that you state what a
release did, and we check what a specific stored artifact says.

**One thing we are deliberately not asking again.** You said you are not building `should_rebuild`, and
we agree — building the decision ourselves is what surfaced the convergence requirement, the pre-drop
boundary and the `variant_count` guard, none of which we would have found by consuming a verdict.

---

# just-module-creator, 2026-08-22 to 2026-08-24 — an unattended authoring run, and what a green run does not say

Nine items from one round of unattended module authoring against 0.6.6. S66 is first because it is
the one that cost real work rather than clarity; the rest are about what a compile reports, what it
reports too much of, and what it does not report at all.

## S66 — `enrich()` writes `resolution.csv` once, at the very end, in place, with no lock — so a run killed at minute 29 has written nothing, and one killed mid-write leaves a valid-looking short file

**Status — accepted, and all four asks have now shipped. Ask 1 landed 2026-08-24; asks 2, 3 and 4
shipped in 0.7 as [RM128](ROADMAP_HISTORY.md#rm128--enrich-persisted-nothing-until-its-tail-so-a-run-killed-at-minute-29-had-written-nothing) — the run became a transaction, so a kill leaves the staged
answers for the next run to resume from and a refused `strict` run commits nothing; the lock is
`flock` on the spec directory; and `progress` reports `(done, total)` over subjects.** Every line of your reading holds against the tree and not only
against the installed package — one write at `enrich.py:1248`, a truncating writer, no `flock`,
`fcntl`, `os.replace`, `NamedTemporary` or `fsync` anywhere in any of the three packages, and the
read-modify-write window really is the whole run.

**We fixed nine writers where you reported three.** `layout.atomic_writer` / `atomic_write_text` in
the format tier — temp file in the same directory, `fsync`, `os.replace` — and every sidecar writer
in the workspace now goes through it: `resolution.csv`, `verification.json` and `sources.csv` as you
asked, plus `clinical_assertions.csv`, `gene_metrics.csv`, `gene_validity.csv`, `frequencies.csv`,
`gwas_effects.csv` and `literature.csv`. The six you did not name had the identical shape, reached by
each being copied from its neighbour, so a fix scoped to the report would have left the next writer
inheriting whichever neighbour it came from. The guard is an AST walk over the set with an equality
assertion rather than a floor, and it was watched failing on the pre-fix source of all four spot-checked
writers before being kept.

**The half of your report we would not have got to on our own is why the short file is the dangerous
residue rather than the annoying one.** You joined it to merge-not-clobber and to the three no-row
branches yourself, and that join is the item: a truncated `resolution.csv` is read back, keyed on
`subject`, and *believed*, because `enrich.py:873`/`:881`/`:903` make "fewer rows" a state the table
reaches honestly. We have written that pairing into ENRICHER.md under the merge-key table rather than
beside the writers, since the merge is what gives truncation its teeth, and into the gotcha book as
`@atomic-sidecar-write`. Your three branches are correct and are explicitly out of scope in RM128 — a
`not_found` row for a subject nothing could answer is the fabricated negative each comment refuses.

**Two things the fix had to get right that are worth naming, because both are ways it could have been
a no-op that looked like a fix.** The temp file goes in the *same directory*, since `os.replace` is
atomic only within a filesystem and a `/tmp` default would have silently degraded to a copy on any
split mount. And `newline=""` is passed through rather than defaulted: `csv.writer` terminates with
`\r\n`, the sidecars are hashed inputs on one path, and RM82's newline normalization was built around
exactly that byte — a helper that quietly normalized it would have moved bindings on the
machine-written half of the corpus, which is precisely the half that carries CRLF. A test asserts the
emitted bytes are identical to what `open` produced.

**Why 2, 3 and 4 are filed rather than shipped — each is a decision, and we would rather have your
view than guess.**

- **Ask 2 (checkpointing), the one you care about most.** Your argument that merge semantics make a
  partial file *correct input* is right, and we verified it: `existing` is read at `enrich.py:584-593`
  and keyed by `merge_key`, so checkpointed rows are picked up and completed, and a re-run over them
  hits cache and is instant. What stops us doing it unattended is a second atomicity nobody wrote
  down: today `strict` raises at `:1228`/`:1240` *before* the `if write:` block, so a refused run
  leaves the module exactly as it was. Checkpointing means a refusal leaves rows behind. We think that
  is probably fine and possibly better, but "a refused strict run changes nothing" is the kind of
  property that gets broken by accident precisely because it was never a promise — so it gets decided
  first. One shape is refused in advance so you know it is not the answer: a checkpoint that fires
  under `best_effort` and not under `strict` makes `write=True` mean two things, which is a defect we
  have a rule against.
- **Ask 3 (the lock).** It buys the most — it is the only one of the four that would have stopped the
  zombie overwrite outright, and your account of that is the sharpest thing in the report: the module
  validated, closed and compiled green over a table that had halved. What blocks it is that a lockfile
  left by exactly the kill this item is about then blocks every subsequent run, which is a worse
  unattended failure than the one it prevents; a staleness rule for a lock is a clock, and we have
  refused clocks before. `flock` on the file has neither problem and is probably the answer — we have
  not tested it on the network filesystems a consumer might use, which is the remaining work.
- **Ask 4 (the progress callback).** Additive, minor-legal, and it is the incident's actual root
  cause — both runs died to a client-side 1800 s idle timeout with essentially everything resolved.
  It is not shipped only because the resolver chain is not a per-subject loop in `enrich()`; it is
  batched inside `resolver.py`, so *what unit* the callback counts (subjects, links, phases) is a
  signature decision, and a leaf shipped against a guess is one P3 keeps working forever. If you have
  a preference from the transport side, that is the input that settles it — you are the caller.

**What you can do now:** upgrade when the next minor is cut and the truncated-file class is gone. The lost-work
class is not, so a long unattended run still wants the timeout raised on your side until RM128's
second half lands.

<!-- triaged: next-minor · sha 1b43eba05679 -->


**Reported by** just-module-creator (the authoring plugin), 2026-08-22. Found by two independent
unattended runs on 2026-08-21, both against enricher 0.6.6; the second hit it without knowing the first
had. It is the one item in this batch that cost real work rather than clarity, so it is first.

### The shape, in the installed package

`just_dna_enricher/enrich.py` — every path we opened is under
`.venv/lib/python3.14/site-packages/`, printed beside the answer:

```
$ uv run --project /data/sources/just-module-creator python -c "
import just_dna_enricher; print(just_dna_enricher.__file__)"
/data/sources/just-module-creator/.venv/lib/python3.14/site-packages/just_dna_enricher/__init__.py
```

* **One write, at the end.** The only call to `_write_resolution_csv` is `enrich.py:1248`, inside the
  `if write:` at `1247` — after the resolver chain, after `verify_reference_alleles`, after
  `diagnose_wrong_build`, after `compare_clin_sig`, after `check_rsids`, and after both `strict`
  raises at `1228` and `1240`. Nothing is persisted before it.
* **The writer truncates in place.** `_write_resolution_csv` at `enrich.py:1565` is
  `open(output_path, "w", …)` plus a `csv.DictWriter` loop. No temp file, no `os.replace`, no `fsync`.
  A process killed between the truncate and the last row leaves a syntactically valid CSV that is
  simply short — and short is the one failure mode this table cannot report about itself.
* **Two more files ride in the same tail, and both writers have the same shape.**
  `record_verification` at `enrich.py:1253` and `record_source_terms` at `enrich.py:1277`. The first
  lands in the format tier's `verification.py:357`, which is `path.write_text(...)`; the second in
  `licensing.py:489`, which is `Path(path).open("w", …)`. Neither is atomic either, so one kill can
  leave the module carrying a truncated `resolution.csv`, a truncated `verification.json` and a
  truncated `sources.csv` at once.
* **No lock anywhere.** `grep -n "flock\|fcntl\|os.replace\|NamedTemporary\|fsync"` over the whole
  installed `just_dna_enricher/*.py` returns nothing. The existing table is read at `enrich.py:584-593`
  and rewritten at `1248`, so the read-modify-write window is **the entire run** — thirty minutes on
  the modules below. Two concurrent enrichments of one spec directory are last-writer-wins over a
  merge, and neither knows.

### What it cost, and why the merge design makes this worse rather than better

Two runs, 330 and 474 variants, were killed by a **client-side idle timeout at 1800 s**. Both had
resolved essentially every variant by then. Both wrote **nothing** — half an hour of successful
per-variant network work discarded because one late call in the tail had not returned.

That is the part we want to put in front of you rather than the crash: the sidecar's documented
character is **merge-not-clobber** — `enrich.py:579` says so in those words, and `ResolutionRow`'s key
rule is `subject`, which S51 established. A merge-shaped table is exactly the table for which a
partial write is *safe*: an interrupted run that had flushed 300 of 330 rows would leave a file the
next run reads, keys on, and completes. The design that would make incremental persistence correct is
already in place; only the persistence is missing.

**And a kill is not the end of the run.** The worker thread cannot be interrupted from the client side,
so the aborted run kept going. The author, seeing nothing written, restored the module's published
330-row `resolution.csv` and re-enriched — which returned `resolved: 330, sources: ["cache"]`
instantly and correctly. The zombie then reached `enrich.py:1248` and overwrote that file with **162
distinct rsIDs**, plus a rewritten `verification.json`. The module then validated, closed and compiled
green: nothing downstream can see that a table halved.

**The mechanism for the shrink is in your own code and is not a bug** — it is what makes the
last-writer-wins window dangerous rather than merely untidy. Three branches contribute **no row at all**
for a subject that got no answer: `enrich.py:873` (the live link was asked and never answered),
`enrich.py:881` (no link ran, RM98), and `enrich.py:903` (nothing is GRCh38-gated). Each has a good
comment explaining why writing `not_found` there would be a fabricated negative, and we agree with all
three. The consequence is that an interrupted-then-completed run does not write *worse* rows; it writes
**fewer**, and a shorter `resolution.csv` is indistinguishable from a module whose author resolved less.

### What we did about it meanwhile

Nothing that helps anyone else: we restored the file from the published module and re-ran. There is no
guard we can build on our side, because the write we would have to make atomic is inside `enrich()`.

### Asks, in the order we would take them

1. **`tmp` + `os.replace` on all three writers.** Smallest, purely local, and it removes the
   truncated-file class outright. `os.replace` is atomic on the same filesystem on every platform you
   support, and `verification.json`'s writer is already a single `write_text` so it is a two-line
   change there.
2. **Incremental or checkpointed persistence of `resolution.csv`.** Flush the resolved rows before the
   verification passes run, or every N subjects. The merge semantics already make a partial file the
   correct input to the next run — this is the ask that turns thirty lost minutes into thirty
   recovered ones, and it is the one we care about most.
3. **An advisory lock over the read-modify-write window.** A lockfile beside the sidecar, or `flock` on
   the file itself. Even a refusal — *"another enrichment is in progress"* — would have prevented the
   zombie overwrite entirely.
4. **A progress callback on `enrich()`.** There is none in the signature (`enrich.py:499` onward), and
   the pass reports through `logger` to stderr, so a caller driving it over a transport has no
   in-band signal at all and cannot keep a connection alive through a thirty-minute call. A
   `progress: Callable[[int, int], None] | None = None` would be enough; we are not asking for a
   protocol.

We would take (1) alone as a real improvement, and (1)+(2) as a complete answer.

**Reproduced against** format / compiler / enricher **0.6.6** installed, line numbers read from
`.venv/lib/python3.14/site-packages/just_dna_enricher/enrich.py` (1591 lines).

---

## S67 — `_verify_vrs_ids` emits one warning per allele where `_vrs_coverage` aggregates the same class, so the better-resolved module gets the flood

**Status — accepted; shipped 2026-08-24 in `just-dna-compiler`, as a patch.** Grouped by `reason`,
exactly as asked and in exactly the `summarize_ref_mismatches` shape: descending count then reason,
three `variant_key`s named, `and N more` for the rest. `_BLAME_ROW` stays per-row for the three
reasons you gave.

**Your framing is the argument and we are not improving on it.** *Which path a row lands in is
decided by whether the enricher minted an id for it, and nothing else* — that sentence is the item.
Both passes walk the same rows, both report the same underlying fact (an indel identity needs the
reference sequence), and the shapes differed because the two functions were written at different
times rather than because the findings differ. **Noise inversely proportional to how well-resolved
the module is** is the consequence worth writing down, and we have put it in COMPILER.md beside the
warning catalogue so the next person to add a VRS finding meets it.

**You were also right about which argument settles it.** `compiler.py:2633-2634` says *a finding no
authored edit could clear is not a `strict` matter*, and it applies one step out unchanged: a finding
no authored edit could clear is not worth one line per row either. That is the whole justification, it
was already in the file, and it had been spent on severity only — which is the same shape as the
`blame` discriminator you flag in **S68**, computed and then dropped on the way out.

**A patch, not a minor.** Warning wording is patch-legal, no verdict moves, and the pinned substrings
survive — `"could not be verified"` is in the grouped line and the suite's contract assertions pass
untouched.

**Three things the tests pin, and the third is the one we would have got wrong.** That the count
survives the grouping, since this is not a cap and the coverage number matters. That two distinct
reasons never collapse into one line — the tempting cheap version is "collapse the VRS warnings",
which would hide that a module has two different problems with two different remedies, and that is
`_vrs_coverage_warnings`' own stated reason for grouping by *why*. And that `_BLAME_ROW` still emits
one line per row: a per-reason line for an error the author must fix individually removes the only
thing they need, which is *which row*.

**On your module A, the effect is 80 lines to a small number of reason lines**, so the three
genotype-coverage findings you could act on are no longer items 83–85 of 85. **S68** is where the
general question goes — this fix makes one wall shorter and does nothing about the channel's
structure, which is your point there and it stands on its own.

<!-- triaged: next-minor · sha 9886db1793f6 -->


**Reported by** just-module-creator, 2026-08-22. Companion to **S68**, which asks for the structure
that would make a wall of warnings survivable in general; this one is the single local fix that does
not need any of it. Both were found in the same unattended run.

### The two paths, side by side

Both live in `just_dna_compiler/compiler.py` and both walk the same `resolution.csv` rows:

* `_verify_vrs_ids` at **2597** — for each allele whose `vrs_id` is *present* but not recomputable
  offline, appends its own line: `f"{message}; carried unverified."` at **2671**.
* `_vrs_coverage` at **2682** — for each allele whose `vrs_id` is *absent*, increments
  `gaps[reason]`, and `_vrs_coverage_warnings` at **2797** turns the whole dict into a handful of
  lines grouped by cause.

**Which path a row lands in is decided by whether the enricher minted an id for it**, and nothing
else. `_verify_vrs_ids` skips `row.vrs_id is None` outright (`2651`), because "nothing to check" is
correctly not a finding. So an indel with no id is one line in an aggregate; the *same* indel with an
enricher-minted id is a line of its own, on the reason at **2928**: *"is not a single-base
substitution, so justifying it needs the reference sequence — minted upstream by the enricher, not
recomputable here"*.

### Measured, 2026-08-21, on two modules from the run that found this

| module | resolution rows | rows with a `vrs_id` | indels | compile warnings | of which per-allele VRS |
|---|---|---|---|---|---|
| A | 101 | 101 | 47 | **85** | **80** |
| B | 57,595 | 0 | 26,810 | **7** | 1, aggregated |

The 57,595-row module is quiet because nothing minted ids for it. The 101-row module is loud because
something did. **Noise is inversely proportional to how well-resolved the module is**, which inverts
the incentive the whole minting story exists to create.

The consequence is not aesthetic. The three warnings an author of module A could actually act on —
heterozygous, homozygous and reference-homozygote genotypes with no matching row — were items **83,
84 and 85** of 85.

### Why we think the fix is uncontroversial

Your own docstring at `compiler.py:2633-2634` already states the governing rule: *"a finding no
authored edit could clear is not a `strict` matter"* — which is why `_BLAME_TIER` is a warning rather
than an error in both modes. The same argument applies one step further out: a finding no authored edit
could clear is not a finding worth **one line per row** either. `_vrs_coverage`'s own docstring makes
the aggregation case in the same file: *"Gaps are grouped by why, because the reasons have completely
different remedies and a bare 'N missing' hides which one you have."*

**Ask:** group `_verify_vrs_ids`'s `_BLAME_TIER` warnings by `reason` the way `_vrs_coverage` already
groups gaps — one line per reason with a count and a few named `variant_key`s, exactly the shape
`sequences.summarize_ref_mismatches` uses (three examples plus *"and N more"*). `_BLAME_ROW` stays
per-row: it is an error, it is rare, and it names a row that contradicts itself.

**What we are not asking for.** Not suppression, and not a cap that silently drops lines — the
coverage number matters and an author who wants the list should get it. Aggregation keeps the count
truthful while making the other 5 warnings visible.

**Reproduced against** compiler **0.6.6** installed
(`.venv/lib/python3.14/site-packages/just_dna_compiler/compiler.py`, 6911 lines).

---

## S68 — `warnings` is a flat `list[str]` with no code, no count and no way to tell a finding an author can clear from one they cannot

**Status — accepted as real, filed as
[RM131](ROADMAP_HISTORY.md#rm131--the-warnings-channel-says-what-each-finding-is-and-whether-an-author-can-clear-it),
and ✅ SHIPPED in 0.7 on 2026-08-28 — both halves, not just the actionability one. We did not take the
minimal version, and you are owed the reason because you explicitly offered to stop asking for it; the
answer turned out to be that the reason was worth spending a release on rather than a deferral.**

**What you get:** `compilation.carried` beside an unchanged `compilation.warnings` — the subset no edit
to your spec directory can clear, so subtracting it gives you the actionable set — and
`compilation.warnings_summary` as `{code: count}` over `vocab.VALID_WARNING_CODES`, whose values sum to
`len(warnings)` so you can tell the digest is complete rather than hoping. All three on
`ValidationResult`/`CompilationResult`/`ClosureResult` too, filled on every path including a failed
compile. `warnings` itself is byte-identical, so anything you grep today keeps working.
[COMPILER.md § Warning texts a consumer keys on](COMPILER.md) lists all 69 codes and marks the 9
carried ones.

**The diagnosis is right and the best line in it is yours:** *you already compute the discriminator
and spend it on severity only.* `_BLAME_TIER`/`_BLAME_ROW`'s own comment says *"blame decides severity
and nothing else"*, `_closure_warning` reaches the same distinction from the other end, and both throw
it away on the way out. **S67 is that shape one level down** and we fixed it there, which is the part
of your report that shipped this pass — the 190-row module's VRS flood is now a few grouped lines, so
the three findings its author could act on are no longer items 83–85 of 85.

**Why `warnings_summary: dict[str, int]` is not the free win it looks like.** The field is additive
and harmless. **The `code` is not.** A published vocabulary is permanent within a major under P3 and
P6, so the first set we ship is the one you and every other consumer key on forever — and it has to be
derived across roughly 29 append sites and 16 returning helpers that were never written to be
classified. Shipping a plausible set in a triage pass is precisely the *leaf shipped against a
hypothesis* the charter then keeps working indefinitely. The container is free; the vocabulary is the
release. You half-anticipated this — *"if the model change is too big for a minor"* — but the
expensive half is not the model, it is the naming.

**Three candidate derivations are in RM131, and the reason none is obviously right is worth having
now**, because your view would move it. From the **pinned catalogue** in COMPILER.md: honest, and
exactly the findings consumers already match on — but partial by construction, and a digest that
silently omits unpinned findings is worse than no digest, since a consumer reading a summary believes
it complete. From the **emission site**: mechanical and total, but it keys on where the code lives, so
a refactor renames a published key, which is the rename P3 forbids arriving through the back door.
From the **check itself**, named where the finding is built, the way `VALID_VERIFICATION_CHECKS`
already works: most work, most stable, and it has a precedent here that is already a closed vocabulary
a consumer keys on. We lean at the third and have not committed.

**Your fallback shape is probably the thing that lands first, and it is the better half of the ask
anyway.** A `carried`/`notes` list beside `warnings` needs **no vocabulary at all**, is additive,
breaks no consumer, and answers the question an author actually has — *can I do anything about this?*
— which the count never does. `blame` and the closure branch already classify two families; what it
needs is every emission site saying which side it is on, which is the same audit the codes need, done
once.

**What we are not doing, and it is your own list**: no cap, no truncation, no verbosity flag. All
three hide findings rather than organising them, and the author with the most warnings is the one who
most needs the hidden ones. That sentence is in RM131 in your words because it forecloses the cheap
repair somebody will propose.

**Concretely for you meanwhile:** `warnings` is unchanged, so nothing on your side breaks, and S67
alone should take a large bite out of the 14 kB on any module whose ids were minted. If you have a
preference between the three derivations, that is the input that moves this — you are the consumer
who would key on it.

<!-- triaged: next-minor · sha ed6cb3422c35 -->


**Reported by** just-module-creator, 2026-08-22. The general half of **S67**: that one asks for a
single aggregation, this one asks whether the channel it lands in has enough structure to be read at
all. Two asks, one restructure, so one item.

### What the type is

```
$ grep -n '^class \|    warnings:' .venv/lib/python3.14/site-packages/just_dna_compiler/models.py
11:class ValidationResult(BaseModel):
16:    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings")
36:class ClosureResult(BaseModel):
64:    warnings: list[str] = Field(default_factory=list)
67:class CompilationResult(BaseModel):
73:    warnings: list[str] = Field(default_factory=list)
```

All three results, and through them everything a consumer surfaces — our `validate_module`,
`compile_module` and `registry_check` all pass the list through field-for-field, because collapsing it
ourselves would be us inventing a vocabulary you own.

### Why a flat list stops working

**It is not readable at the sizes it reaches.** A compile of a **190-row** module in the 2026-08-21 run
returned roughly **14 kB** of warnings. `strict=false` does not help — it changes what counts as an
*error*, not how much prose the warning channel carries. Every consumer-facing document on both sides
of this seam, ours included, tells an author that warnings on a green run are the real output; that
instruction is only followable if the output can be read.

**And nothing in the string says whether the author can do anything about it.** The VRS lines say so in
their own prose — *"minted upstream by the enricher, not recomputable here"* (`compiler.py:2928`) — so
no edit to the spec clears them, ever. They sit in the same list, at the same level, as a
genotype-coverage gap that only the author can close. An author reading top-to-bottom cannot sort the
one from the other without knowing the codebase.

**You already compute the discriminator and spend it on severity only.** `_BLAME_TIER` / `_BLAME_ROW`
at `compiler.py:2831-2832` is exactly *whose limit this is*, and its comment says *"blame decides
severity and nothing else"*. The closure warning at `compiler.py:5205` is the same distinction reached
from the other end — *"a finding the author can clear, but whose severity is not the mode's
business"*. So the fact exists at the point each warning is built and is discarded on the way out.

### Two asks, and they are the same change

1. **Warnings as objects with a stable `code` and a `count`**, repeats collapsed. The `code` is the
   part that ends substring-matching on prose, which RM44 already made a rule for the manifest and
   which applies verbatim here — we match on warning text today because there is nothing else to match
   on, and your changelog is right that wording is patch-legal.
2. **Carry the actionability out with it** — `actionable: true | false`, or a split between `warnings`
   and a `carried` / `notes` list. Deriving it from `blame` and from the closure branch covers the two
   cases we can see; you will know whether the others classify as cleanly.

**A minimal answer that breaks nothing, if the model change is too big for a minor.** Add
`warnings_summary: dict[str, int]` beside the existing list — code to count — and leave `warnings`
exactly as it is. Every existing consumer keeps working, and one that wants a readable digest has one.
We would take that and stop asking.

**What we are deliberately not asking for.** Not a cap, not truncation, and not a verbosity flag. All
three hide findings rather than organise them, and the author who most needs the hidden ones is the
author with the most warnings.

**Reproduced against** compiler **0.6.6** installed. The 14 kB figure is from the 2026-08-21 run and is
reported rather than re-measured here; the type, the three result models and the blame constants are
read from the installed package at the lines above.

---

## S69 — the `panel:` deprecation warning says *"nothing else is lost"*, and three fields it is the only home of have no replacement

**Status — accepted; shipped 2026-08-24 in `just-dna-compiler`, as a patch. We took both of your
asks, because they fix different halves and neither alone is enough.** You offered them as
alternatives — *either one closes this* — and the probing said otherwise: gating the warning leaves
the false clause standing in the branch that still fires, and narrowing the sentence leaves an author
told to delete a block whose replacement their module does not have.

**Ask 2, the sentence.** The closing clause is now *"the rows it describes are the authored
variants.csv rows. `genes`, `significance` and `reference_sha256` have no replacement anywhere — keep
the block until 1.0 if you need them recorded."* Your three arguments are each the reason one field is
named, and the `genes` one is the sharpest thing in the report: with the block deleted, *this gene is
not in the panel* and *this gene is in the panel and had nothing to report* become the same absence,
and they are opposite statements about the module's coverage. Your 425-against-`gene_count: 298`
measurement is what makes that concrete, and it is in COMPILER.md now.

**Ask 1, the gate, and it turned out to be a charter point rather than a nicety.** P3 permits a
deprecation in a minor **only where its audience can act on it** — the replacement exists and the
deprecated thing is not still mandatory — and whether that holds depends on a value the check had not
read: it fired beside `_load_yaml`, before the licence rows were loaded. So the check moved behind
them (`source_rows` is stashed the way `literature_rows` already was), and with no filled
`clinvar`/`annotation` `dataset` it now says **do not delete the block yet**, names filling the licence
row as the thing to do first, and says that re-drafting will not do it because the merge is
never-clobber. Your point that there is *no path from that module to the state the warning assumes*
is exactly the condition P3 names, and we had not noticed the deprecation was resting on it.

**An empty cell is an absence, not a value**, so your `cardio` shape takes the same branch as a module
with no licence row at all. Tested both ways.

**On the fixture gap you flagged — you were right and it was the reason the defect survived.** None of
the sixteen `reference_examples/` carries a `panel:` block, so the deprecation had no worked example
on either side. The existing test used a hand-written spec and asserted only that the message
contained `"dataset"`, which both of our new branches satisfy — so it would have passed over either
defect. The licence row is now hand-built in the test, and the three assertions are: the unreplaced
branch refuses deletion and says why, the replaced branch gives the old advice, and **neither branch
claims "nothing else is lost"**, checked against `GenePanelSpec.model_fields` rather than against a
copy of the field list.

**What we did not do, per your own scoping.** `panel:` is not un-deprecated — the compiler was right
that it materializes nothing and RM4 was right about where the tautology marker belongs. We also did
not carry the block into `manifest.json` the way `weighting` is: that is your option 2's second half,
it is a real candidate for the same reasons you give, and it is a minor rather than a patch, so it
waits for someone to want the fields *after* 1.0 rather than being decided by this item. The warning
now says to keep the block, which is the honest interim.

<!-- triaged: next-minor · sha ae749c00ff13 -->


**Reported by** just-module-creator, 2026-08-22.

### The warning

`compiler.py:3423-3431`:

> `module_spec.yaml` declares a `panel:` block. It is deprecated in 0.6 and removed at 1.0: the
> compiler never materialized rows from it, and the one thing that did read it — the enricher's
> ClinVar clin_sig cross-check, deciding whether a drafted module is being compared against its own
> source — now reads the `dataset` column of the module's licence row, which
> `just-dna-enricher draft-panel` writes itself. **Delete the block; the rows it describes are the
> authored `variants.csv` rows, and nothing else is lost.**

The first two sentences are exactly right and we have verified the replacement: `clinical.py:165-173`
recomputes `clinvar_dataset_label(reference)` and compares it against the `dataset` of the
`source="clinvar", layer="annotation"` licence row, and `clinvar_draft.py:704` is what writes it. The
tautology marker really did move.

**It is the last clause that does not hold.** `GenePanelSpec` carries five fields, not one:

```
$ uv run --project /data/sources/just-module-creator python -c "
from just_dna_format.manifest import GenePanelSpec
for n, f in GenePanelSpec.model_fields.items(): print(n, '|', f.annotation)"
source            | str
reference         | str | None
reference_sha256  | str | None
genes             | list[str]
significance      | list[str]
```

`SourceRow.dataset` is documented as *"Which release the data came from, e.g. `clinpgx_2026-07-05`"* —
a release label, one string. It cannot carry `genes`, it cannot carry `significance`, and it is not a
digest, so it cannot carry `reference_sha256`. An author who follows the warning deletes the only
place any of those three is written, and `manifest.panel` (`compiler.py:5377`, `manifest.py:1473`)
goes to `null` with them.

### Why each of the three is load-bearing rather than decorative

* **`genes` states the denominator.** In the run that found this, one drafted module declared 425
  panel genes and `validate_module` reported `gene_count: 298`. The difference — 127 genes that were
  searched and yielded no qualifying variant — is derivable **only** from the block. With it deleted,
  *"this gene is not in the panel"* and *"this gene is in the panel and had nothing to report"* become
  the same absence, and they are opposite statements about the module's coverage.
* **`significance` states the predicate.** It is what makes a panel module's row set reproducible:
  the same genes against the same release with a different significance filter is a different module.
* **`reference_sha256` is a digest and `dataset` is a name.** ClinVar reissues; a release label does
  not pin bytes. This is the same distinction your own `clinvar_dataset_label` draws internally when
  it falls back to `source_sha256` — the label is a name *or* a digest, and only one of those two
  spellings pins anything.

### The sharper half: the replacement field is legitimately empty, and your own drafter says so

`clinvar_draft.py:691-699` — when the snapshot has no readable `release.json`,
`clinvar_dataset_label` returns `None` (`clinvar.py:58-67`) and the drafter warns that *"the licence
row records no dataset"*. That is the right behaviour and we are not filing it. But it means a module
can carry a populated `panel:` block **and** an empty `dataset`, and today the compiler tells that
author to delete the block on the strength of a replacement their module does not have. In the run
that found this, a module drafted 2026-08-10 had an empty `dataset` while one drafted 2026-08-19 had a
filled one — and because `merge_sources_file` is never-clobber, re-running the pass does not backfill
it. There is no path from that module to the state the warning assumes.

### Asks — either one closes this

1. **Make the warning conditional on the replacement actually being present.** If the `clinvar` /
   `annotation` licence row has a non-empty `dataset`, warn as today. If it does not, either stay
   silent or say what is missing. This is the smaller change and it is honest under both states.
2. **Or narrow the sentence and keep the block's data.** *"…the rows it describes are the authored
   `variants.csv` rows. `genes`, `significance` and `reference_sha256` have no replacement; keep the
   block until 1.0 if you need them recorded."* If they should have a home past 1.0, the shape that
   already exists is `manifest.weighting` — a descriptive authored block the compiler records and does
   not act on, which is what `panel:` has been since 0.6 anyway.

**What we are not asking for.** Not un-deprecating `panel:`. The compiler was right that it
materializes nothing, and RM4 was right that the tautology marker belonged on the licence row. The
defect is one clause of one sentence, and a backfill path for the modules that followed it.

**Reproduced against** format / compiler / enricher **0.6.6** installed. The 425/298 and empty-`dataset`
measurements are from the 2026-08-21 run and are reported rather than re-measured — we have no
panel-bearing spec in a tree either of us can inspect, which is itself worth noting: none of the
sixteen `reference_examples/` carries a `panel:` block, so the deprecation has no worked example on
either side.

---

## S70 — `verification.json` counts a check's findings and keeps none of them, and `clinical_significance` is the only check where that leaves nothing at all

**Status — accepted. Ask 2 and the cheap half of ask 1 shipped 2026-08-24; the sidecar is filed as
[RM130](ROADMAP_HISTORY.md#rm130--a-checks-findings-were-counted-and-not-kept-so-a-conflict-had-no-name-to-act-on),
open, a minor.** Your table of where each check's findings survive is correct check by check, and your
claim that **nothing in `compiler.py` reads `VerificationRecord.findings`** is confirmed against the
tree — one grep, no hits.

**Ask 2 first, because it was the cheapest and the most obviously missing.** `validate` and `compile`
now say that a record reports findings, naming each check and its denominator: *"verification.json
records 20 finding(s) across 1 check(s): clinical_significance (20 of 141616)…"*. The sentence says a
finding is a disagreement rather than a defect, that this never fails a build, and where to record a
justified one. A record reporting **zero** says nothing at all — a check that could not fail must not
report a zero, which is the rule your S59 established and which applies to the reporting side too.

**The cheap half of ask 1: `clinical_significance` now writes a `detail`**, grouped on `opposed` with
the `verification.examples` aggregation so a 618,629-subject module cannot put a list in the message.
It names the rows and **both values** — `1:100:A:G (pathogenic vs benign)` — because your point is
that an author must be able to check both sides, and a bare key sends them back to the comparison.
Grouping on `opposed` rather than by count is your own distinction: `ClinSigConflict.opposed` already
draws it and it is the one that decides what to do.

**The sidecar is filed rather than shipped, and the reason is a decision a neighbouring item says to
make first.** You are right that this is the input side of S52/RM117 — `outranks` can only be written
for a row an author can name, so the record and the trigger are one piece of work seen from two ends,
and a `detail` string makes the rows nameable to a *human* without making them joinable. What stops us
building it this pass is **RM124's open question 2**, from S60: it asks whether one record serves both
an authored overlay and `outranks`, on the grounds that both are *an authored value beating a source
with prose*, and it says to settle that **before either grows a second field**. A conflict sidecar is a
third table in that family, so shipping it now would answer RM124 by accident — which is the failure
mode your S60 was filed to prevent.

**One thing settled in advance so it does not have to be re-derived: the key cannot be a bare
`variant_key`.** `compare_clin_sig` compares an authored call for a **genotype**, and
`annotations.parquet` keys on genotype for the same reason, so a conflict is per
`(variant_key, genotype)` — a variant-keyed table would collapse two authored calls that disagree with
the archive differently. That is in RM130.

**Nothing about severity moved, per your last paragraph and our own rule.** No error, no `strict`
matter, no auto-correction; the ClinVar cross-check still never escalates, and the new warning says in
its own text that the archive is the stale side often enough that this cannot fail a build.

<!-- triaged: next-minor · sha 7eca8f9cafc6 -->


**Reported by** just-module-creator, 2026-08-22. Companion to **S71**, which is about the same file at
the document level.

### The measurement

Two modules from the 2026-08-21 run, read out of their `verification.json`:

```
check: clinical_significance   subjects: 141616   findings: 20   detail: null
check: clinical_significance   subjects: 618629   findings: 32   detail: null
```

Fifty-two rows across two modules assert a clinical significance that ClinVar's own records do not
support, and **nothing anywhere says which rows**.

### Why this check specifically, and not the other four

We went looking for the rows before filing, and the reason they are not findable is precise. Of the
five checks `enrich()` records (`enrich.py:1318-1530`):

| check | where its findings survive |
|---|---|
| `reference_allele` | `detail=` at `enrich.py:1345`, via `summarize_ref_mismatches` — grouped by diagnosis, three `variant_key`s named per group plus *"and N more"* |
| `rsid_coordinate_agreement` | `detail=` at `enrich.py:1524` — up to `DETAIL_LIMIT` disagreements, plus what was not compared and why |
| `rsid_currency` | **per row, in `resolution.csv`** — `row.rsid_status` and `row.rsid_current` are stamped at `enrich.py:1092-1093` and are columns of the written file (`_FIELDNAMES`, `enrich.py:80`) |
| `genome_build_agreement` | count only — but its subjects *are* `reference_allele`'s mismatches, so the candidate rows are reachable from the row above |
| `clinical_significance` | **nowhere.** `ran(...)` at `enrich.py:1432-1438` passes `subjects`, `findings`, `source` and `release`, and no `detail` |

The conflicts do exist at runtime: `compare_clin_sig` returns them, they reach
`EnrichmentResult.clin_sig_conflicts` (`enrich.py:1158`), and every one is written to the logger at
`enrich.py:1055-1057`. That is stderr — it survives the process and nothing else. No sidecar carries
them, and `verification.json` records the count.

### Why an author cannot work around it

The instruction every consumer document on this seam gives — ours in the strongest terms — is that a
mismatch against an archive means **checking both sides**: the row may be wrong, and the archive may be
stale, retracted or superseded. That instruction is exactly right and it is why we do not want the
enricher conforming the row silently. But it is unexecutable against a finding that has no name. An
author holding *"20 of 141,616"* can neither defend the twenty nor correct them, and re-running the
pass to see the log again costs the full ClinVar comparison.

### Asks

1. **Write the findings.** A derived sidecar keyed by `variant_key` carrying the authored value, the
   source's value, and whether the two are *opposed* or merely *different* — the distinction
   `ClinSigConflict.opposed` already draws at `enrich.py:1055-1056`. **This is the input side of
   S52/RM117 and we think the two are the same work seen from opposite ends**: `ProvenanceItem.
   outranks` is where an author records *why* their row outranks the archive, and it shipped in 0.6.5
   — but an author can only write one for a row they can name, and this check is the thing that knows
   which rows those are. We are not re-asking S52; we are saying its answer has no reachable trigger
   until a conflict has a name. That is the shape S60 argued for
   from the other direction, and the merge-key machinery `hints.key_fields` publishes already covers a
   new sidecar. If a sidecar is too much, `detail=` with the `summarize_ref_mismatches` treatment —
   grouped, N named, *"and M more"* — would already make the check actionable.
2. **Surface a one-line summary where an author is standing.** `validate_spec` and `compile_module`
   both read the file — `_verification_block` at `compiler.py:5115` is deliberately shared between them
   — and both warn when it is *stale* or carries no *closure*. Neither says anything about a record
   reporting a **non-zero `findings`**. We checked: nothing in `compiler.py` reads
   `VerificationRecord.findings`. The counts do reach `manifest.verification.checks[]`
   (`verification.py:289-296`), so a consumer that goes looking will find them — but the author running
   `validate` sees a green result with warnings about closure and nothing about fifty-two contested
   rows.

**What we are not asking for.** Not an error, not a `strict` matter, and emphatically not an
auto-correction. A conflict is a question, not a defect, and half the time the archive is the stale
side. We want the question askable.

**Reproduced against** enricher **0.6.6** installed
(`.venv/lib/python3.14/site-packages/just_dna_enricher/enrich.py`). The two `subjects`/`findings` pairs
are from the 2026-08-21 run and are reported rather than re-measured; every line reference above was
read in the installed package.

---

## S71 — `verification.json`'s `producer` is a single document-level field, so a merge restamps records it did not produce

**Status — accepted; shipped 2026-08-24 in `just-dna-format` + `just-dna-enricher` as
[RM129](ROADMAP_HISTORY.md#rm129--producer-described-the-document-and-was-read-as-describing-the-checks),
a minor.** Your ask as written: `producer: str | None` on `VerificationRecord`, beside
`source`/`release`/`checked_at`, and the document-level one kept for what it actually means.

**Your argument from the other fields is the whole case and we are recording it as such.** Every
field describing *an individual piece of work* was already on the record — which authority answered,
which snapshot, when — and `producer`, naming who ran it, was the one sitting on the document. That
asymmetry is what made the restamp possible rather than merely unfortunate, and it reads as an
oversight once the list is written out the way you wrote it.

**We also fixed the sentence, not just the field.** `Verification.producer`'s description read *"Tool
and version that put the checks"* — which is exactly the false claim, sitting in the printed contract
where `describe`/`reference` render it. It now says it names what last **wrote the file**, pairs with
`produced_at`, and is not a claim about the checks, and it points at the per-record field for the
question it cannot answer. A description that survives its own field becoming wrong is a repeat of a
defect we have a rule about, so it gets corrected in the same commit rather than softened.

**Three things established before shipping, because a new field on a record with a published fact-hash
owes them.** `producer` is **outside** `VERIFICATION_FACT_FIELDS`, on precisely the reasoning that put
`checked_at` outside it — who ran a check is a fact about the run, not about the module — so no
published `verification.signature` moved, and a test asserts that rather than assuming it. It is
`str | None` defaulting to `None`, exactly the shape you proposed; `None` on an older record reads as
*not recorded* and specifically not as any release, since defaulting it to the reading version would
manufacture the very attribution the item is about. And `merge_records` does carry it across for free,
as you predicted — the test writes a hand-built 0.6.4 record, merges a new one over it, and asserts
the old attribution survives.

**Thank you for putting the merge on the record as correct.** That half took more care than the
defect: RM72's rule that a fresh *skip* does not displace an earlier *answer* is doing real work
there, and a report that had described the whole thing as "the merge is broken" would have pointed the
fix at the one part that was right. Your triage case — *was this check put before or after that
release* — is now answerable without hand-mapping a timestamp, and it is written into SCHEMAS beside
the attestation as the reason the two fields both exist.

<!-- triaged: next-minor · sha 0becb402ecc1 -->


**Reported by** just-module-creator, 2026-08-22. Companion to **S70**; small, and the merge it is about
is otherwise correct.

### What we saw

A module already carried a `clinical_significance` record produced by enricher **0.6.4**. We ran
`check_identifiers`, which merged new records in. The resulting file reports
`producer: just-dna-enricher 0.6.6` for the whole document — including the 0.6.4 record, which that
release did not produce.

**The merge itself did the right thing and we want that on the record**, because it is the part that
took thought: `merge_records` (`verification.py:299`) kept the older `ran` record rather than letting
this run's silence delete it, and RM72's rule that a fresh *skip* does not displace an earlier *answer*
held. Nothing was lost. What moved was only the attribution.

### The shape

```
$ uv run --project /data/sources/just-module-creator python -c "
from just_dna_format.manifest import VerificationRecord, Verification
print('record:', list(VerificationRecord.model_fields))
print('block :', list(Verification.model_fields))"
record: ['check', 'subjects', 'findings', 'skipped', 'detail', 'source', 'release', 'checked_at']
block : ['signature', 'module_hash', 'producer', 'produced_at', 'closure', 'checks']
```

Every other field that describes *an individual piece of work* is on the record: `source` names the
authority, `release` names the snapshot, `checked_at` names when. `producer` — which names **who ran
it** — is the one that sits on the document, and `record_verification` fills it from
`producer_label()` at `enrich.py`'s call site (`verification.py:168`, `producer=producer_label()`)
every time the file is rewritten, whatever the records came from.

`produced_at` has the same scope and is fine there: it genuinely describes the document's last write.
`producer` reads as a claim about the checks.

### Why it is worth a field rather than a note

It is the field that tells a reader whether a record predates a fix. Your own S45 is the worked case:
a drafter defect fixed in enricher 0.6.4 left records that a later release names differently. A reader
triaging *"was this check put before or after that release"* has `checked_at` — a timestamp they must
map to a release by hand — and a `producer` that is guaranteed to say the newest thing that touched
the file.

**Ask:** move `producer` onto `VerificationRecord`, beside `source` / `release` / `checked_at`, and
keep the document-level one as *"what last wrote this file"* if it is useful (it pairs naturally with
`produced_at`). `merge_records` already carries a whole record across, so the per-record value travels
for free; only the constructors need it.

**What we are not asking for.** Not a schema break. If a required field on `VerificationRecord` is too
much for a minor, `producer: str | None` defaulting to `None` reads correctly as *"written before this
was recorded"*, which is honest and is the same three-valued shape the rest of this file uses.

**Reproduced against** format / enricher **0.6.6** installed.

---

## S72 — `stats`' scalar counters still describe `variants.csv` alone, so a `pharm_variants` module publishes `unique_rsids: 0` beside 1,482 rsIDs

**Status — accepted, and split. Ask 2 and the gene-delimiter warning shipped 2026-08-24 in
`just-dna-compiler`; ask 1 is queued for 1.0 in
[ROADMAP § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker), because it is a retype and
nothing smaller reaches it.** Reproduced on `reference_examples/cyp2c19_star_alleles`:
`variant_count: 0, unique_rsids: 0` with `table_rows` carrying 1,332.

**You are right that `unique_rsids: 0` is a different kind of wrong from the others, and it is the
sentence that carried the item.** `variant_count: 0` for a module with no `variants.csv` is *true* and
unhelpful; `unique_rsids: 0` beside 1,482 rows whose first authored column is `rsid` is untrue. And
your framing — our own three-valued rule inverted in the producer's own output, quoting
`VerificationRecord`'s docstring back at us — is exactly it. That is in the tracker entry in your
terms.

**Why ask 1 is not a minor.** `Stats.variant_count` and its siblings are `int` in a **published**
`manifest.json`, so widening to `int | None` breaks any reader that compares or sums them, and P3
names retyping as major-only for precisely that reason. `ValidationResult.stats` is `dict[str, Any]`
so nothing retypes formally — but its keys are a documented contract and `0` → `None` breaks the same
arithmetic one layer down. Sizing it as a minor on the grounds that the field is "only advisory" is
the move RM127 recorded as the tempting one, and we are not making it. **We think it is the right end
state**, which is why it is filed rather than refused, and it is queued beside the `module.version`
refusal because both turn on how far P3/P8's field-shaped clauses reach.

**Ask 2 shipped, and we took both halves of your "or".** `table_rows` is promoted from a de-facto key
to a documented one, and `row_count` is beside it: the family-independent number, the sum across every
authored table. The `stats` description now says in terms that `0` in the scalar counters means *no
`variants.csv` rows* and never *no data*, and points a caller asking *how big is this module* at
`row_count`. That makes the counters readable without pretending it makes them correct.

**One thing worth telling you because you would have hit it.** The first draft of `row_count` summed
the kind-table counts alone and reported **0 for a twelve-variant module** — `variants.csv` and
`studies.csv` are the SNP core and sit outside `_TABLE_KINDS`. That is this very item's defect, one
family over, reproduced inside its own fix. It is pinned by a test that asserts both directions.

**The delimiter warning shipped as you scoped it: it reports and splits nothing.** Your two reasons
are the reasons — splitting guesses at a vocabulary, and `IFNL3;IFNL4` may legitimately name the
locus. We would add a third: the value came out of an upstream export rather than from the author, so
refusing it would refuse a faithful transcription. It aggregates by **cell**, not by row, since your
case was 33 rows sharing one value. The message says what it costs — `stats.genes` is what a gene
index reads, so a composite is published beside its parts as a term nobody will search for — and
leaves the call to a human.

**And thank you for filing this against your own accepted item.** S57's reply settled that `stats`
describes the module, we shipped the gene half, and the comment beside that change says *"the keys
this adds for such a module are all zero"* — which reads as a note about harmlessness and was in fact
the residue. A reporter who reads our own change comment back to us is the most useful kind.

<!-- triaged: next-minor · sha 69b0980f68de -->


**Reported by** just-module-creator, 2026-08-22. **A follow-up to S57**, which you accepted and fixed in
RM121 — this is the residue that fix deliberately did not cover, and we are filing it because your own
reply settled the principle that decides it.

### The residue

S57 asked whether `stats` describes **the module** or **`variants.csv`**, and your answer was
unambiguous: *"`stats` describes **the module**. `Stats`'s own docstring has always read 'card/detail
stats derived from the spec' — from the spec, not from a table of it."* `module_stats`
(`compiler.py:3856`) now unions `genes` and `gene_count` across every gene-bearing kind, and that
half is fixed.

The scalar counters were not, and the code says so in the comment beside the change
(`compiler.py:3818-3820`):

> Unconditional where it used to be `if variants:` — a table-only module has no variant rows and is
> exactly the module whose genes were being dropped (S57). **The keys this adds for such a module are
> all zero**, which is what `Stats` already defaults them to, so no manifest number moves by it.

So `module_stats` calls `variant_stats` (`compiler.py:3833`) unchanged, and for a module with no
`variants.csv`:

```
variant_count   = len({v.variant_key for v in []})            -> 0
unique_rsids    = len({v.rsid for v in [] if ...})            -> 0
study_count     = len(studies)                                -> 0
clinvar_count / pathogenic_count / benign_count               -> 0
```

Measured in the 2026-08-21 run on a **1,482-row `pharm_variants.csv`** module: `variant_count: 0`,
`unique_rsids: 0`, `study_count: 0`, with the real number present only in `stats["table_rows"]`
(`compiler.py:3814`).

**`unique_rsids: 0` is the one that is simply false rather than merely narrow.** `rsid` is the first
authored column of `pharm_variants.csv` (`scaffold.authored_field_names(model_for('pharm_variants.csv'))`)
and 1,482 rows carry one. The counter reports none. It is not part of the table's key — that is
`key_fields('pharm_variants.csv')` → `columns=('variant_key', 'drug', 'genotype',
'phenotype_category', 'annotation_id')`, `stamped=('variant_key',)` — but the key is not what
`unique_rsids` claims to count.

### Why zero is the wrong value even under the old reading

This is the three-valued rule broken in the producer's own output, and it is the rule your
`VerificationRecord` docstring states better than we can: *"`subjects=0` with no `skipped` means the
check ran and had nothing in scope, which is not the same as not running."* A `variant_count` of `0`
says *this module has no variants*. For a PGx module that is true and harmless. `unique_rsids: 0` says
*this module names no rsIDs*, and that is false. A consumer cannot tell "counted, and the answer is
none" from "this counter does not apply here", and a registry keying a facet off either one inherits
the collapse — which is the S57 failure exactly, one field over.

### Asks

1. **`None` for a counter whose table is absent**, where the field type allows it. `variant_count: 0`
   for a module with a present-but-empty `variants.csv` stays `0`; a module with no such table gets
   `null`. This is the RM44/S31 counter rule applied to `stats`.
2. **A family-independent `row_count`**, or promote `table_rows` from a de-facto key to a documented
   one. `table_rows` already carries the honest number and nothing in `Stats`' documented contract
   mentions it.

### Related, and in this item because it is the same field: a delimiter inside a single-valued cell

The same module carries 33 rows whose `gene` cell reads `IFNL3;IFNL4` — that spelling comes straight
out of the upstream ClinPGx export, so it is not the author's invention. `module_stats`
(`compiler.py:3887`) does `genes.add(gene)` on the raw cell, so `"IFNL3;IFNL4"` becomes a **third
gene** in `stats.genes` beside `IFNL3` and `IFNL4`, and `gene_count` counts it.

`VariantRow.gene` is `str | None` with no validator and no metadata, and neither is any other kind's:

```
$ uv run --project /data/sources/just-module-creator python -c "
from just_dna_format.spec import VariantRow
f = VariantRow.model_fields['gene']; print(f.annotation, f.metadata, repr(f.description))"
str | None [] 'Gene symbol, e.g. MTHFR'
```

Nothing splits it and nothing flags it. Since S57 made `genes` the field a registry gene index is fed
from, a composite value is now a search term nobody will ever type. **We are not asking you to split
on a delimiter** — that would guess at a vocabulary, and `IFNL3;IFNL4` may legitimately mean *the
locus*, which is a real thing in that dataset. A warning naming the rows would be enough, and it
belongs beside the other authored-value hints rather than in a validator that refuses.

**Reproduced against** compiler **0.6.6** installed. The 1,482-row and 33-row figures are from the
2026-08-21 run; the code paths, the zero-derivation and the absent `gene` validator were read in the
installed package at the lines given.

---

## S73 — an open question, not a defect: `pharm_variants.csv` has no citation column, so a ClinPGx-drafted module makes 1,482 clinical claims with nowhere to cite them

**Status — answered: your third reading is the intended one, and the column is missing rather than
deliberately absent. Stated in [SCHEMAS.md](SCHEMAS.md) as you asked, filed as
[RM132](ROADMAP_HISTORY.md#rm132--pharm_variantscsv-made-a-clinical-claim-per-row-and-could-only-cite-per-variant)
— and ✅ shipped in 0.7 (2026-08-28) as `PharmVariantRow.pmid`, with both literature cross-check sites
reading it in the same release. The question this reply left open is answered the way the binning side
answered it: `provenance_quote` does not follow.**

**The one-sentence answer: a row cites when its claim is finer-grained than `studies.csv`' key.** That
is the rule, and it decides every table without anyone having to ask again. `studies.csv` keys on
`(variant_key, pmid)`, so a study row attaches to a **variant** — which is exactly right for
`variants.csv`, whose rows are per `(variant_key, genotype)`. It is wrong wherever one variant carries
several distinct claims.

**We had already decided this, one release ago, for a different table — and you reconstructed the
argument without knowing that.** RM47 put `pmid` on the **bin row** rather than widening `studies.csv`,
for your reason exactly: *the bin row cites; the citation table describes*. Your reading 2 fails on the
keys precisely as you suspected, and your instinct not to build on it is the same call we made. The
gap is that nobody carried the rule across to `pharm_variants.csv`, whose key is the longest in the
schema.

**On reading 1, since it was the plausible one and we want it closed rather than merely unchosen.**
`evidence_level` is not the provenance handle: it points at somebody else's *grading of* evidence
rather than at the evidence, which is your own phrasing and it is right. And the licence row's
`source`/`dataset` state redistribution terms and which snapshot the rows came from — they say nothing
about which study grounds a given drug–genotype claim. So the module is not "citing ClinPGx as a
whole" in any sense that discharges a per-row claim. Both are written into SCHEMAS beside the new
citation-site table so the next person meets the refutation rather than re-deriving it.

**Why the column is filed rather than shipped in this pass, and it is not hesitation about the
answer.** RM47's recorded lesson is that the column is the smaller half: **both** literature
cross-check sites have to learn the new citation site in the same release — `_cross_check_literature`
and `enrich_literature` — or every citation from it reads as a stale orphan in one direction and is
invisible in the other, which its own note calls *evidence that the format never checks, worse than
the gap*. That is a piece of work across three tiers, not a field.

**One thing genuinely open, and your skills are the reason it matters.** Whether `provenance_quote`
follows `pmid` here. The binning side deliberately said no — the row cites, the table describes, which
is what stops `StudyRow`'s whole provenance column set migrating across one column at a time. We think
the same holds, and we are flagging it rather than assuming it because you teach `provenance_quote`
and per-row citation hard, on S54/S55, and a 1,482-row body of clinical claims is exactly where that
question gets asked next. Your view would settle it.

**For the dossier meanwhile:** a `pharm_variants` module **is** supposed to carry citations; today it
can carry `literature.csv` article records, which is the *describing* half, and it has no way to say
which row any of them grounds. Teaching "cite everything" is right and currently unexecutable for this
table — which is a fact about our schema, not about the author.

<!-- triaged: next-minor · sha d5038107cbd4 -->


**Reported by** just-module-creator, 2026-08-22. **We are asking what the intended model is, not
asserting that something is broken** — we could not find the answer in either tree and we would rather
ask than write a guess into our skills.

### What we found

```
$ uv run --project /data/sources/just-module-creator python -c "
from just_dna_compiler.scaffold import model_for, authored_field_names
m = model_for('pharm_variants.csv')
print(len(m.model_fields), list(m.model_fields))
print(len(authored_field_names(m)), authored_field_names(m))"
16 ['rsid', 'chrom', 'start', 'ref', 'alts', 'gene', 'genotype', 'variant_key', 'authored_ident',
    'drug', 'phenotype_category', 'annotation_id', 'response', 'evidence_level', 'trait_efo_id',
    'conclusion']
13 ['rsid', 'chrom', 'start', 'ref', 'gene', 'genotype', 'drug', 'phenotype_category',
    'annotation_id', 'response', 'evidence_level', 'trait_efo_id', 'conclusion']
```

Sixteen model fields, thirteen of them authored (the `stub_template` header). None of them is a PMID,
a DOI or any other citation. `evidence_level: 1A` is the closest thing, and it is a pointer at
*somebody else's grading of evidence they hold* rather than at the evidence.

Beside it, `variants.csv` + `studies.csv` is a two-table design where the second table exists to carry
exactly this: `pmid`, `provenance_quote`, and since 0.6.5 `curator`. `COMPANION_KINDS` pulls
`studies.csv` in behind `variants.csv` and — per S49 — deliberately does not pull it behind everything.

### The question

**Is a `pharm_variants` module supposed to carry citations at all?**

Three readings we can construct, and we have no basis for choosing:

1. **No, by design.** The module cites ClinPGx as a whole, through the licence row's `source` and
   `dataset`, and per-row citation is ClinPGx's job rather than the module's. Under this reading
   `evidence_level` is the intended provenance handle and the design is complete.
2. **Yes, through `studies.csv`.** An author who wants to cite adds one and keys it — but the two
   keys do not line up. `key_fields('studies.csv')` keys a study on `variant_key`, while
   `key_fields('pharm_variants.csv')` returns
   `columns=('variant_key', 'drug', 'genotype', 'phenotype_category', 'annotation_id')`,
   `rule='equality'`, `stamped=('variant_key',)`. So one study row attaches to every drug, genotype
   and phenotype category recorded for that variant, and the claims a PGx module makes are per-row
   rather than per-variant. We do not think this works as-is, which is why we are not just doing it.
3. **Yes, and the column is missing.** In which case this stops being a question.

We are asking for the **intended provenance model to be stated**, wherever such a statement belongs —
the model's docstring, `SCHEMAS.md`, or a line in the table's own documentation. Whichever of the three
is right, an author should not have to derive it, and today they cannot: nothing on either side of
this seam says.

### Why we are asking rather than deciding

Our skills teach `provenance_quote` and per-row citation hard, on the strength of S54 and S55 — a
module whose claims cannot be traced to a paper is the failure mode we spend the most words on. A
1,482-row drug-response module is a large body of clinical claims to leave outside that rule, and we
do not want to tell an author either *"cite everything"* or *"this table does not need citations"*
without knowing which one you meant. A one-sentence answer closes this and we will write it into the
dossier.

**Checked against** format / compiler **0.6.6** installed. The 1,482-row figure is from the 2026-08-21
run; the field lists above were produced against the installed package just now.

---

## S74 — `ModuleSpecConfig` is public and the only thing that produces one is private, so every consumer re-parses `module_spec.yaml` by hand

**Status — accepted; shipped 2026-08-24 as `just_dna_compiler.compiler.load_spec`, a minor.** Your
second shape, verbatim: `load_spec(path, *, authority_keys=None) -> ModuleSpecConfig`, raising
`SpecError` rather than returning a tuple, beside `read_manifest` and `read_verification` because that
is the sibling you named and it is the right one.

**Your guess about why it was private is correct, and it is the whole design.** The tuple exists
because `validate_spec` accumulates errors from a dozen sources and reports them together, which is
right for a validator and wrong for a loader — a caller who wants the object should not have to check
a tuple's second element to find out it got `None`. So both exist now: `_load_yaml` keeps the
accumulating shape for the validator, and `load_spec` raises. `SpecError` is a `ValueError` subclass,
so a caller already bracketing loads the way `read_verification`'s callers do keeps working without
knowing the type exists.

**It is in the compiler, not the format tier, and that is not an oversight.** Loading it needs
`pyyaml`, and `just-dna-format` is `pydantic` + `cryptography` by charter — a verify-only consumer
must not pull a YAML parser. You already depend on the compiler (every caller of `validate_module`
does), so **you can drop your PyYAML declaration**, which was the concrete cost you named.

**One correction, because you would otherwise expect something the function does not do.**
`_load_yaml` does *not* fold `defaults:` — it validates the YAML into `ModuleSpecConfig`, and the
block stays a block. The fold happens per row, and the public route to folded rows is
**`spec_tables`** (RM116), which exists for exactly the reason you give here: it was added because a
caller re-deriving it got it wrong, and it is the piece your own S65 calls *"precisely the part a
caller reimplements wrongly"*. So the pairing is `load_spec` for the yaml's own blocks —
`weighting`, `authorship`, `license`, `module` — and `spec_tables` for the rows. Authority-key
dropping and the diagnoses you do get.

**Which keys were dropped is deliberately not returned.** That is `validate_spec`'s `.info`, and a
caller who needs it wants the validator rather than the loader; putting it on `load_spec` would
reintroduce the tuple in a new shape.

**On your fallback — "consumers should go through `validate_spec`'s result instead" — that is not the
answer, and you were right not to take it.** `ValidationResult.stats` does not carry these blocks,
as you say, and running a full validation to read `authorship:` is the wrong cost. Reading the file is
legitimate; what was missing was a supported way to do it.

**The evidence that this was ours rather than a preference: `enrich.py` imports `_load_yaml`
directly.** The workspace's own network tier reaches into the private symbol, which is the clearest
statement available that no public route existed. That is now the one caller left to migrate on our
side.

<!-- triaged: next-minor · sha b9d0445a5feb -->


**Reported by** just-module-creator · **Filed** 2026-08-24 · **Severity** low, and it is an API-surface
gap rather than a defect

`ModuleSpecConfig` is exported from `just_dna_format.spec` and is the model of the one file every
module has. The function that turns a `module_spec.yaml` on disk into one is
`just_dna_compiler.compiler._load_yaml(path, authority_keys=None)` — underscored, and there is no
public route beside it. Checked against the installed 0.6.6 rather than the tree:

```python
# nothing public in format or compiler returns a ModuleSpecConfig
public functions returning ModuleSpecConfig: NONE
# and the registry's specfiles module has no loader either
just_dna_registry.specfiles: ['RENAMED_ON_UPLOAD', '__loader__']
```

**What that costs a consumer.** We do not reach into private APIs, so we `yaml.safe_load` the file
ourselves in two places and read the keys we need out of a raw dict. That is fine until it is not:
the defaults-folding, the authority-key dropping and the error list your loader produces are all
things we now silently do not get, and a consumer reading `weighting:` or `authorship:` out of a bare
dict is reading a shape your model owns without your model's validation. It also puts **PyYAML** in
our dependency list for no reason other than that yours is not reachable — we have just declared it
rather than leaning on it transitively, and it is the only dependency we carry that exists purely to
work around a private symbol.

**The ask is one line of surface, not new behaviour.** Either export the existing function under a
public name, or add a thin `load_spec(path) -> ModuleSpecConfig` beside `read_verification` and
`read_manifest`, which is exactly the shape those two already have and which is what made us look for
it in the first place. If the errors-and-dropped-keys tuple is the reason it is private, a
`strict=True` variant that raises would suit a consumer better than the tuple does.

**What we are doing meanwhile:** parsing it ourselves and reading only `weighting`, `authorship`,
`license` and `module` — no defaults folding, no authority keys. If the answer is that consumers
should not read `module_spec.yaml` at all and should go through `validate_spec`'s result instead, that
is a complete answer and we will take it; `ValidationResult.stats` does not carry these blocks today,
which is why we did not.

**Found while** building an offline audit surface that reports "this module fills `weight` on 190 rows
and declares no `weighting:`" — the case where an author who deliberately authors no weights and an
author who forgot are the same bytes.

# just-module-creator, 2026-08-31 — a benchmark that disagreed for a real reason

## S75 — `StudyRow` records a p-value and an effect size with no field naming the analysis that produced them, so a mispaired row is indistinguishable from a correct one

**Status — accepted and shipped in the tree as [RM140](ROADMAP_HISTORY.md#rm140--a-study-rows-p-value-and-effect-size-are-asserted-to-belong-together-and-nothing-recorded-what-either-came-from); the minimal ask, exactly as scoped.**
`StudyRow.statistical_test` is one optional free-form column shaped like `study_design` — the test or
model that produced this row's `p_value`/`effect_size`, and what it was adjusted for. Open, no
vocabulary, and **no gate**: your argument against your own candidate is the one we took, and it is
recorded in the roadmap entry rather than paraphrased. Column first, and possibly never a gate.

**Answered is not installable.** This is inside `0.7.0`, whose three `pyproject.toml` files are bumped
and whose tag is **not cut** — so it is committed, not published. [CHANGELOG.md](CHANGELOG.md)'s 0.7.0
heading is the record, and it will say so when that changes.

**One premise of the report does not reproduce, and it changes what you can do today.** Point (2) reads
`key.columns = (variant_key, pmid)` as meaning one paper's several analyses can be represented by
exactly one, the rest dropped by silent choice. Probed on a real spec: two rows sharing a variant and a
PMID **both reach `studies.parquet`**, and the duplicate is a *warning* — `duplicate_study_citation`,
which does not escalate under `strict`. Nothing was ever dropped. What was missing was the legibility,
not the capacity.

**So the one behaviour change is that warning, and it is what makes the column do something.** The
check reads a repeated key as *the same claim written twice*, which your two rows are not. Since RM140,
**both rows stating an analysis, with the two names different**, suppresses it. Nothing else does: an
absent `statistical_test` is *unknown*, and unknown against a stated value cannot establish that two
rows describe separate work — `a != b` would have suppressed on every blank cell and quietly retired
the check for every module written before the column existed. Neither stated, both the same, or one
stated and one blank in either order: warns as before, with the byte-identical message and code.

**What that buys you concretely.** Your SIRT6 row can now be two rows —
`0.36 / Fisher's exact (allelic)` and `0.75 / univariate logistic regression`, same variant, same PMID
— compiling with no duplicate warning, each self-describing. The discrepancy your README and
`logs/authoring.log` were holding has a place in the module itself. Your decision to withhold
`effect_size`/`effect_measure`/`effect_allele` where the reported OR is not reconstructible from the
paper's own counts is the right one and stays right; the column does not ask you to fill anything.

**`(variant_key, pmid)` is unwidened**, as you asked, and independently that is the legal answer:
`_KEY_FIELDS` drives `hints.key_fields` and the published `key.columns`, and re-keying a shipped
authored table is major-only under Principle 3. The check restates the pair rather than reading the
tuple, so the split is contained in one function and reaches no drafting provider.

**On quote verification being blind to this** — you are right, and the roadmap entry says so in those
terms rather than treating it as a limitation to be worked around. A quote cannot witness a number it
does not contain, and yours grounds the significance verdict correctly. That is a fact about what an
attestation is, not a gap in the pass.

Reproduced end to end before deciding: the duplicate-warning behaviour on a real spec, the round trip
carrying the column through `compile → reverse → compile` byte-identically (watched failing on each of
the two reverse touch points in turn), and two specs differing only in the *presence* of the column
hashing to the same `content_signature`, which is what makes it minor-legal. Written up in
[COMPILER § the analysis grain](COMPILER.md#one-paper-several-analyses-and-the-dedup-key-rm140),
[SCHEMAS](SCHEMAS.md), and the authoring skill's table reference.
<!-- triaged: 0.7.0 · sha 745de3190cb9 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A reproducibility benchmark: two agents, byte-identical prompts, same three DOIs, building one module
each. They overlapped on exactly one row — `rs117385980` from PMID 41249831
(`10.1038/s41598-025-24018-3`, SIRT6 and frailty) — and disagreed on it:

| run | `effect_size` | `effect_measure` | `p_value` | `stat_significance` |
|---|---|---|---|---|
| A | 1.42 | OR | **0.36** | not_significant |
| B | 1.42 | OR | **0.75** | not_significant |

### What we expected, and what is actually there

We expected one of them to be a misreading. Neither is. The paper reports **two different tests of the
same association**, and each run took a different one:

- **Table 3**, with Table 5 naming the test: allelic **Fisher's exact**, `OR 1.4`, `p 0.36`, on the 2×2
  allele table (non-frail T 8/376, frail T **0**/78). The paper states this one in its own prose.
- **Table 6**, `Univariate(Allele)`: **univariate logistic regression**, `OR 1.42`, `95% CI 0.18–11.67`,
  `p 0.75`. Five further adjusted models follow in the same table, down to `OR 0.96, p 0.98`.

So run B's row is internally consistent — OR, CI and p all from Table 6's single row. **Run A's is not:
it carries Table 6's `effect_size 1.42` beside Table 3's `p_value 0.36`**, and its own `conclusion`
cites Table 6's confidence interval, so the row names one analysis's estimate and another's p-value.

**Everything was green.** `validate_module(strict)` passed, `compile_module(strict)` passed,
`audit_module` raised nothing relevant, and `quotes_found` was satisfied — the provenance quote is
verbatim and correct, because it grounds the *significance verdict* ("not statistically significant")
and contains no statistic at all. A quote cannot witness a number it does not contain, so quote
verification is structurally blind to this class of error.

### The gap

`StudyRow` has `study_design` — *"e.g. meta-analysis, GWAS"* — which describes **the study**. There is
no field describing **the analysis**: which test, which model, adjusted for what. So:

1. A `p_value` and an `effect_size` on one row are asserted to belong together, and **nothing records
   or checks that they came from the same analysis.** `redundancy_bearing` lists neither, and there is
   no plausible place for such a check to live today because the facts it would compare are not
   recorded.
2. `key.columns` is `["variant_key", "pmid"]` with `rule: equality`, so a paper reporting several
   analyses of one variant can be represented by **exactly one** of them. The others are dropped by
   silent choice — and, as above, which one was chosen is not recorded either.

The consequence is not that a module is wrong. It is that a *correct* row and a *mispaired* row are
byte-indistinguishable to every consumer and every check.

### What we did meanwhile

Built a reference module carrying `p_value 0.36` (allelic Fisher's exact — the appropriate test given
a zero cell; the logistic MLE under near-separation is what the 65-fold CI is reporting) and
**withheld `effect_size`, `effect_measure` and `effect_allele` entirely**, because the reported ORs are
not reconstructible from the paper's own counts: with frail T = 0/78 and non-frail T = 8/368 the
T→frail odds ratio is 0 raw, ≈0.28 Haldane-corrected and ≈3.6 reverse-coded, none of which is 1.4. The
authors' own prose says the T allele "increased with robustness", i.e. the opposite direction to an
OR > 1. The second test and the discrepancy are recorded in the module's README and its
`logs/authoring.log`, which is the only place they can go.

### The ask, minimal

**One optional free-form column on `StudyRow` naming the analysis** — `statistical_test`,
`analysis_model` or similar, shaped like `study_design`: open vocabulary, no validation, no new check.
That alone makes `0.36 / Fisher's exact` and `0.75 / univariate logistic` two self-describing rows
instead of two indistinguishable ones, and it gives a future check somewhere to compare against.

**The key constraint is context, not a second ask.** We are *not* asking you to widen
`(variant_key, pmid)`; carrying one analysis per variant-paper is a defensible design and prose can
hold the rest. We mention it only because it is why the choice is silent: with one row available and
no field naming what was chosen, the discarded analyses leave no trace.

**A candidate we think is wrong**, argued against ourselves: a validator requiring the pair to come
from one test. It cannot be written — nothing on either side of the boundary knows what test a number
came from until the column above exists, and adding the column plus a gate in one step would make
every existing published row retroactively incomplete. Column first, and possibly never a gate.

## S76 — WITHDRAWN as a duplicate of S66; kept for its one new measurement

**Status — the withdrawal is accepted and your closing question is answered YES; a real defect underneath the report is fixed and shipped in the tree as [RM141](ROADMAP_HISTORY.md#rm141--validate---strict-blessed-a-module-compile---strict-refused-whenever-the-resolution-table-was-partial).**
No apology needed — an item withdrawn within hours with a measurement attached costs less than one
nobody files. Three things, and the middle one is the reason this is not simply closed.

**Your closing question first, because you said no reply is needed if the answer is yes, and it is
yes.** `verification.json` is written inside the same commit block as `resolution.csv`, below the line
every refusal raises above. A killed run writes neither; a resumed run writes both. So the two
artifacts cannot disagree the way you describe, and the loud half you observed was 0.6.6's behaviour,
where the transaction did not exist. Closed.

**Your correction of 2026-08-31 is accepted, and it improves the item — this reply is amended for it
rather than left standing.** You are right that a complete write of an incomplete resolution set is not
S66's family, and right about the mechanism: a subject whose live request could not be made joins
`unreachable_rsids` and is written as **no row at all**, deliberately, so the artifact never states a
negative nobody established. Nobody-asked is a third state beside asked-and-failed and
asked-and-absent, and it is the one that leaves no trace in the table. So your 62 are unanswered, not
lost, and the same file comes out of a `best_effort` run that completes normally over a source it could
not reach.

That makes RM141 the closure by the right route rather than by luck. `validate --strict` reads the
table against the spec beside it, which is the only thing that can see a set complete as a file and
incomplete as an answer — and it is indifferent to *why* the rows are absent, which is what you want
given the cause turned out to be misdescribed. Two paragraphs below reasoned from the truncation
premise and are corrected in place.

**Your central mechanism does not reproduce, on either version — and this is worth more than the
withdrawal.** You describe merge-not-clobber as making the re-run trust the partial file and never
retry the missing 62. Probed directly: a module with three authored subjects and a table recording one
is re-run against a resolver that records every question asked. It asks about **exactly the other two**
and commits all three. The merge is over subjects the table records; a subject it does not record has
nothing to merge onto and goes to the source like any other. Measured on this tree **and on `v0.6.6`
built from its own tag**, so it is not something 0.7 fixed underneath you. Re-running would have filled
your 62. The recovery you avoided as dangerous was the correct one.

That also re-reads your arithmetic, and your correction re-reads it further: 203 rows covering 201 of
263 is a table **short of an answer** — not a wrong one, and, as you established from the sorted rsids
and the clean final newline, not a half-written one either. S66's incident replaced a restored 330-row
table with 162, a run that *overwrote* good rows. Yours recorded every answer it got. Either way the
next run continues from it, which is the property that mattered.

**And RM128's atomic write is therefore the answer to the failure you first described rather than the
one you had** — worth keeping in this reply, because the 0.6.6 writer you were running *did* truncate
in place, so it is what you would have met on the next kill. `layout.atomic_writer` stages a temp file
beside the target and `os.replace`s it: an interrupted run leaves either the previous file or none.

**What is real, and is ours.** `compile --strict` refuses a module whose variants still have no
position after resolution. `validate --strict` said nothing about it — so your partial table passed the
pre-flight clean and was refused by the compile immediately after, which is the
green-pre-flight-then-refusal shape our own parity rule exists to prevent, and the third time we have
broken it. It hid behind that rule's exemption: what stays compile-only is a check reading *resolved*
rows, and whether the table **can place** a row is arithmetic over bytes the pre-flight has already
loaded.

So the detector you asked for exists now, in the command your loop already runs first: `validate
--strict` refuses a partial table with the compile's verbatim error naming every unplaced subject,
`validate` warns per uncovered row, a module with no table at all says so once rather than per variant,
and `--no-resolve` silences it. A double-report was found while fixing it and is fixed too — both
passes reached the finding for one subject, measured at 24 warnings for 12.

**One thing we are refusing, and the reason generalises past this item.** A durable marker recording
that a run was partial is a fact about a **run** living in a table of facts about **variants**, on the
same axis that keeps `fetched_at` out of every fact set — and `resolution.csv` has been a pure build
product since RM124. It is also unwritable by the case that needs it: a killed process writes no
marker. The answer to "is this table complete" is a *reading*, computed from the spec beside it, which
is what `validate` now gives you.

**Answered is not installable.** All of it is inside `0.7.0`, bumped and **not tagged**.
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record.
<!-- triaged: 0.7.0 · sha 82cd8b8dde15 -->

**Withdrawn by the reporter, 2026-08-31, within hours of filing.** We filed this before finding
`S66` in the history file, which reports the same defect from the same consumer and is already
answered: the transaction, the `flock` and the atomic writers all shipped as `RM128` in 0.7. Our
apologies — the duplicate check we ran keyed on "partial" and "sidecar" and missed it.

**What is new and worth keeping is the arithmetic**, because `S66`'s worked example is a run that
wrote *nothing*, and ours wrote something that looked complete: a run killed mid-`enrich` left
`resolution.csv` with **203 rows covering 201 of 263 authored rsIDs**, every row correct, every
`status=resolved`, and nothing in the file recording that it is short. Merge-not-clobber then means
the natural recovery — re-run it — trusts the partial file and never retries the missing 62. That is
`S66`'s "valid-looking short file" with a number against it, and it is `RM128`'s case for the
transaction rather than a separate ask.

**One thing that is genuinely not covered by `RM128`, stated as an observation rather than a new
item:** the same interruption left `verification.json` attesting bytes a completed enrich would
change. That half is loud — the stale-verification warning fires — so an interrupted run leaves two
artifacts disagreeing, one that announces itself and one that does not. If the transaction already
stages `verification.json` alongside `resolution.csv`, this is closed too and no reply is needed.

The original report follows, unedited, because the prose is the record of what was observed.

## S76 (original text) — an interrupted `enrich` leaves a partial `resolution.csv` that nothing on disk marks as partial, and merge-not-clobber makes the next run trust it

**Status — answered in the withdrawal section above, which this is the evidence for.** Kept verbatim
and marked only so the ledger can see it: the reporter wrote it as one item under two headings, and a
top-level heading is the unit the ledger counts. No separate reply — the three findings (the gap-fill
does reproduce as *working*, `verification.json` is inside the commit, and the `validate`/`compile`
parity gap that is ours) are all above. **The reporter appended a correction here on 2026-08-31** —
the file was never truncated, which re-attributes the closure from RM128 to RM141 — and it is answered
in the withdrawal section, which this reply's fingerprint now covers.
<!-- triaged: 0.7.0 · sha f1c8681f3f6e -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A reproducibility benchmark: six agents building modules in parallel, sharing one process. One was
authoring a GWAS module from a paper's supplementary workbook — 789 variant rows over **263 distinct
rsIDs** — and was killed by an external quota limit partway through `enrich`.

### What we found on disk

```
variants.csv      789 rows, 263 distinct rsIDs
resolution.csv    203 rows, 201 distinct rsIDs   <- written by the killed run
```

`resolution.csv` is a well-formed, complete-looking CSV. Every row in it is correct: real coordinates,
real VRS ids, `status=resolved`, `source=cache`. **Nothing in the file, its header, or any sibling file
records that it covers 201 of 263 subjects.** There is no marker, no row count, no "in progress"
sentinel, no partial flag. A reader — human or agent — opening this directory tomorrow sees a resolution
sidecar and has no way to tell it from a finished one without independently counting distinct rsIDs in
`variants.csv` and diffing the two sets.

### Why this is worse than an ordinary crash artifact

**Merge-not-clobber turns it into a silent wrong answer.** The documented behaviour is that an existing
sidecar is authoritative and merged rather than regenerated. So the natural recovery — "it died, run it
again" — merges onto the stale 201 and reports success. The 62 unresolved rsIDs are not retried, because
from the merge's point of view there is nothing to do for the rows already present and no record that
the others were ever attempted.

The correct recovery is to delete or capture-and-replace the sidecar first, which the enricher's own
docs do say. Our objection is not that the recovery is undocumented — it is that **the failure is
undetectable**. A consumer who does not already suspect a partial write has no signal to prompt them
into that recovery, and the one they will naturally reach for is the one that entrenches it.

There is a second-order effect we hit in the same directory: the run had written `verification.json`
before the interruption, so the module now carries an attestation over spec bytes that a completed
enrich will change. That part is at least loudly reported — the stale-verification warning fires — but
it means an interrupted run leaves two artifacts disagreeing about the module's state, one loud and one
silent.

### What we did meanwhile

Nothing automatic, deliberately: we surfaced it to the operator rather than repairing it, because
deleting a sidecar is destructive and `resolution.csv` can carry hand-curated `source="manual"` rows
that a blind delete would discard. Our own `refresh_sidecar` (capture, verify the capture, re-derive)
is the safe path and it exists precisely because this class of delete is dangerous. But it is a repair,
not a detector: it does not tell you the sidecar needs refreshing.

### The ask

**A completeness signal a reader can check without reconstructing the subject set.** The cheapest form
we can see is the one that costs no schema change at all: since `fetched_at` is already a column, an
interrupted write is in principle distinguishable from a complete one *if* something records what the
run set out to do. Concretely, one of:

1. **Write the sidecar atomically** — temp file, then rename — so an interrupted run leaves either the
   previous file or none, and never a half one. This is the smallest fix and needs no new field.
2. **Record the intended subject count** in the run's own output (a `logs/` entry, or a manifest-side
   counter), so `resolved 201 of 263` is recoverable after the fact.
3. **A cheap completeness check** callable against a spec directory: distinct authored rsIDs versus
   distinct resolved subjects, three-valued, with `unknown` where the authored set cannot be determined.

We think (1) alone would close the reported failure, and it is the one we would pick. (3) is more
useful but is arguably ours to build rather than yours — say so and we will, since it is a reading
rather than a schema fact.

**A candidate we argued ourselves out of:** having `enrich` refuse to start when a sidecar looks
short. It cannot distinguish a partial write from a legitimately smaller sidecar — an author who
resolved a subset deliberately, or injected a curated `resolution.csv` for exactly the rows they care
about, both of which are supported today. Refusing there would break a working practice to catch a
crash.

### Reporter's correction, 2026-08-31 — the file was never truncated, and that re-attributes the fix

Appended by the reporter after re-reading the preserved artifact, because we handed you arithmetic
that misdescribes it and part of your reply reasons from it. No new ask; no reply needed.

**Proven, from the file itself.** The 203 rows are sorted by rsid throughout and the last line ends
with a clean `\r\n`. The 62 absent rsIDs scatter across the whole alphabetical range of the authored
set (indices 0 and 262 among them), not as a tail. So it is a **complete write of an incomplete
resolution set**, not a half-written file — which we should have checked before calling it partial.

**That matches your code rather than contradicting it.** `_write_resolution_csv` runs once at the end,
and a subject whose live request could not be made joins `unreachable_rsids` and is written as **no row
at all** — deliberately, so the artifact never states a negative nobody established. The 62 are
missing because they were never answered, not because the write stopped.

**What it re-attributes.** This is not `S66`'s family after all: `RM128`'s transaction and atomic
write would not have prevented it, because nothing was interrupted mid-write. The same file is
produced by a `best_effort` enrich that completes normally over an unreachable source. So the thing
that closes it is `RM141` — `validate --strict` reading the table against the spec beside it — which
you landed anyway, and which is the right shape for a cause we described wrongly.

**Your two corrections stand, and one is now explained.** The gap-fill does work: we read
`need_pos`/`need_rsid` in the installed 0.6.6 and they skip only subjects `existing` covers, so the
62 go to the resolver like any other. Re-running was the correct recovery and we advised against it;
that advice is being retracted in our own docs.

**Inference, stated as such.** The likely cause of the 62 unanswered requests is our own benchmark
running six agents through one shared pacing gate. The enrich thread also outlives a dead client in
our wrapper, so the write plausibly completed after the agent that started it was gone. Neither is
measured.

## S77 — `enrich_dosage_sensitivity` writes a ClinGen licence row for a gene it did not cover, so a module carries an obligation for a source that contributed nothing

**Status — accepted in full and shipped in the tree as [RM142](ROADMAP_HISTORY.md#rm142--the-dosage-pass-declared-a-clingen-obligation-for-a-module-clingen-curates-nothing-of); your ask, verbatim, and it was a one-line guard.**
`merge_sources_file` is now behind `if covered:`. A pass that put no row in a table records no source.

Both halves reproduced. A single-variant `SIRT6` module: `covered=[]`, `missing=['SIRT6']`, zero
`gene_metrics.csv` data rows, and a `licensing.csv` with one `clingen` row in it. And the second cost,
which is the one worth the item — a module declaring `license: MIT` and using ClinGen for nothing warns
*declares MIT but annotation-layer sources report CC0-1.0*. Your two agents were adjudicating a
conflict that could not exist.

**Your framing (3) is the right one and is why this could not be fixed on our side of the compile.**
It is the shape of a check that cannot fail — and the compiler genuinely cannot catch it:
`_source_checks`'s orphan warning **exempts the `annotation` layer deliberately** (RM46), because
`sources.csv` is where an author is told to record a hand-read source, and warning about that would
mean compliance is noisy while omission stays silent. So an annotation-layer row nothing uses is quiet
by design, and the only party that knows whether it contributed is the pass.

**We checked the other passes, as you asked, and the answer is that this was `clingen.py` alone.**
`gene_metrics`, `frequencies`, `assertions` and `gene_validity` all pass `{row.source for row in out}`
to `record_source_terms`, so an empty pass records nothing by construction. Run offline over a module
they cover nothing of, `enrich_gene_metrics` and `enrich_frequencies` write no `licensing.csv` at all —
measured, not read off the code. `clingen.py` was the one member building a fixed row and writing it
unconditionally, which is the family's rule missed rather than a rule that needed inventing.

**One choice inside the fix is worth your knowing, because the obvious spelling is the dangerous one.**
The guard keys on `covered` — what *this run* contributed — not on `missing` being empty. `not missing`
would drop the declaration from every module carrying one uncurated gene beside a curated one, which is
a real obligation going unrecorded, and that is the direction that actually harms someone. It also does
not key on the table's contents, which include rows an earlier run merged in and already recorded.
Three tests: covers nothing, covers some, and a second lap where `covered` is empty because the work is
done and the row must stand.

**On your `covered: false` marker alternative** — we went the other way. It makes `sources.csv` carry
rows that are not declarations, so every reader of the table gains a case to handle, the compile gate
included, for a fact with no reader. Absence already says it. Your rejected candidate — the author
deleting the row — we agree is worse than the defect, for exactly the reason you give.

**And on the question you raised as possibly format's**: what `licensing.csv` means when a source was
consulted-and-empty. It means nothing should be there. The table answers *what does this module use*,
and "we queried this" is a fact about a **run**, on the same axis that keeps `fetched_at` out of every
fact set. `ClinGenResult.source_row` is still returned whatever happened, so a caller wanting the terms
of what was consulted has them — a different fact with a different home, which is your own distinction.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. Written up in
[ENRICHER § a pass that contributes nothing records no terms](ENRICHER.md).
<!-- triaged: 0.7.0 · sha be41eff2ba06 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A single-variant module on `SIRT6` (rs117385980), authored by an agent from one paper. It ran the
fact passes, then compiled.

### What happened

The dosage pass reported, correctly, that it covered nothing:

```
dosage: missing: [SIRT6]
```

and nonetheless wrote a licence row into `licensing.csv`:

```
clingen,annotation,CC0-1.0,https://clinicalgenome.org/docs/terms-of-use/,,
"ClinGen (https://clinicalgenome.org), accessed via the gene-curation list",
CC0 public-domain dedication; attribution requested but not required.,
false,true,true,non_commercial,"clingen_dosage_30 Aug,2026",2026-08-30T23:57:03Z,
```

So the compiled module declares an obligation to a source that supplied **no data to any table**.
`SIRT6` is not on ClinGen's dosage curation list; the pass looked, found nothing, and still recorded
having consumed the source.

### Why it is worth fixing rather than shrugging at

1. **It is a false statement in a published artifact.** `licensing.csv` travels to the registry and
   is what a downstream consumer reads to decide whether a module is redistributable. A row saying
   *this module uses ClinGen* is not true of this module.
2. **It fires the licence-disagreement warning for no reason.** The compile emits *"module declares
   license X but annotation-layer sources report [...]"*, and an author then adjudicates a conflict
   that does not exist. We saw two independent agents spend real effort on exactly that in an earlier
   round, before we traced it here — and the honest adjudication in both cases was "compatible",
   reached by reasoning about a source that was never read.
3. **It is the same shape as a check that cannot fail.** A licence row that appears whether or not the
   source contributed says nothing about what the module contains.

We are not certain whether the same holds for the other fact passes when they cover nothing — we saw
it on dosage because that is the pass this module happened to run. Worth checking `gene_validity`,
`frequencies` and `literature` in the same breath.

### The ask

**Write the licence row when the pass actually contributes a row, not when it runs.** If the intent is
to record "we queried this source", then that is a different fact from "this module uses this source"
and wants a different home — the `logs/` entry, or a `covered: false` marker on the row — because
`licensing.csv` is read as the second thing.

**A candidate we think is wrong:** having the author delete the spurious row. It is machine-written
and would come back on the next pass, and an author deleting licence rows by hand is a worse habit
than the defect.

**Filed as an enricher item rather than a format one**, since the row is written by the pass, but the
question of what `licensing.csv` means when a source was consulted-and-empty may be format's to
settle.

## S78 — `compile --strict` builds a green artifact over a coordinate the enricher has already diagnosed as another assembly's

**Status — accepted; your option (1) completed and shipped in the tree as [RM143](ROADMAP_HISTORY.md#rm143--the-enricher-diagnosed-a-wrong-assembly-coordinate-and-compile---strict-built-over-it-anyway). Two of your three asks were already shipped, and one of those you could not have seen.**
You asked for our view rather than guessing the shape, so here is the view, ask by ask.

**(2) — have the compiler re-run the rsid↔coordinate agreement — does not work, on the data rather
than on the principle.** `resolution.csv` does not hold both coordinates. For a coordinate-authored row
the enricher records **what the author wrote**, so the table has one coordinate and there is nothing to
compare it against. Your reading that "resolution.csv holds both the authored coordinate and the
resolved one" is the premise this turns on, and it does not hold; getting the other one would be a
fetch, which P2 forbids. So this is not the smallest change — it is the impossible one.

**(3) — make the compile warn — shipped in this release, and 0.6.6 is why you did not see it.**
`verification_findings_recorded` (S70, another of yours) reports every recorded finding where the
author is standing. Reproduced on your exact spec with the diagnosis in `verification.json`: the
compile prints *records 2 finding(s) across 2 check(s): genome_build_agreement (1 of 1),
reference_allele (1 of 1)*. Absent from 0.6.6 entirely, which is the version you measured. Your own
objection to (3) stands and is why it is not the whole answer — an author who did not read the enrich
report is not obviously going to read a compile warning.

**(1) — record the diagnosis where the compiler can see it — was already three-quarters done, and the
missing quarter is what shipped.** The place is `verification.json`: `enrich` writes a
`genome_build_agreement` record carrying the finding count, the subjects, and a `detail` naming the
rows. It reached the compiler and **no severity attached to it**. `build_disagreement_error` now
refuses a `strict` compile on it, in `validate --strict` and `compile --strict` alike, with the error
equal on both sides and placed ahead of `output_dir.mkdir()` so a refusal writes nothing.

**You said you did not want the strict line moved generally, and it is not moved.** `strict` still
means reproducible, never right — the compiler has no reference and a whole file shifted by one base
still passes. This one check is the exception on **internal-consistency** grounds, which is your own
argument stated in our terms: its findings say the rows are on a different assembly than the
`genome_build` the module itself declares, so it is one authored file contradicting another, not the
compiler adjudicating an outside claim. The judgement stays the enricher's; what changed is that it
stops being discarded at the tier boundary.

**Every other recorded finding still only warns**, pinned by a parametrized test over four checks. The
one worth naming is `reference_allele` — it produces this diagnosis's own *input* and still does not
refuse on its own, because a ref mismatch has three causes and only one of them is an assembly. And
escalating all recorded findings was the tempting generalisation we did not take: it would fail a build
over a ClinVar disagreement, which the cross-check deliberately refuses to do.

**Three things it does not do, each with a test, because each would be worse than the defect:** no
`verification.json` at all is **silent** (an unverified module is the ordinary case, and refusing on
absent evidence reads unknown as wrong); `findings=0` is a **clean bill**, so the gate keys on findings
rather than the record's presence; and a `skipped` record — exactly what an `--offline` enrich writes —
is **unknown**, so offline enrichment cannot poison a module. `best_effort` builds and warns as before.

**Your rejected candidate is the one we agree with hardest.** "Always run strict enrichment" is not
sufficient, for your reason: `best_effort` exists because an unreachable Ensembl must not be a failure,
and a module authored under it stayed wrong forever with every later gate green. The defect was the
discarded diagnosis, not the chosen mode — which is why the fix is on the reading side.

**What still does not reach an already-authored module**, as you noted: nothing here re-examines a
module whose `verification.json` predates the diagnosis. Re-running `enrich` writes the record, and
from then on the gate applies.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. Written up in
[COMPILER § the one recorded finding `strict` acts on](COMPILER.md#the-one-recorded-finding-strict-acts-on-rm143-07)
and in [FAQ](FAQ.md), beside the entry that says `--strict` is not a correctness gate — which is still
true and now carries its one exception.
<!-- triaged: 0.7.0 · sha 9babec06ad13 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A minimal spec, one variant, deliberately pasting a **GRCh37** coordinate onto a module declaring
`genome_build: GRCh38` — the ordinary shape of a paper that states its assembly once in the methods
and nowhere near the table an author is reading. `rs61849494` is `10:51613269 G/A` on GRCh37 and
`10:45982565 C/T` on GRCh38: **5.6 Mb apart and strand-flipped**.

```
rsid,chrom,start,ref,alts,genotype,state,conclusion
rs61849494,10,51613269,G,A,A/G,alt,Pasted verbatim from a GRCh37 paper.
```

### What each gate did, measured

**`validate_spec` — passes.** `valid: True`, zero errors, and the only warning is the unrelated
missing-closure one. Correct: it is offline and cannot know.

**`enrich(mode="strict")` — refuses, and this is exactly right.** `EnrichmentError`, no
`resolution.csv` written, module unchanged. Your diagnosis is better than anything we could have
asked for; all three lines fire and the second names the repair:

> Old-assembly coordinate — 1 row(s) — the authored ref is the GRCh37 base AND GRCh37 dbSNP records a
> variant starting there — the strongest of the three, and the one that names the rs-number to author
> instead (10:51613269 → rs61849494).

**`enrich(mode="best_effort")` — reports all three, then writes `resolution.csv` with the GRCh37
coordinate in it.** Also defensible: best-effort means proceed.

**`compile_module(strict=True)` — succeeds. This is the ask.** Handed that `resolution.csv`, a strict
compile builds the artifact, reports no error and no warning about the coordinate at all, and emits
only the missing-closure warning. The module is internally consistent, reproducible, and about the
wrong locus.

### The gap, stated precisely

Not "strict should catch reference mismatches" — the enricher's strict already does, and does it
well. The gap is that **`resolution.csv` carries no record that its rows were produced over a
diagnosed mismatch**, so the compiler cannot know, and a `--strict` compile therefore cannot refuse
what a `--strict` enrich already refused. The two strict flags mean different things about the same
defect, and the weaker one is the one that produces the published artifact.

We know your position that `--strict` is a determinism gate and not a correctness gate, and we are
not asking you to move that line generally. This is narrower: the correctness judgement **has already
been made** by another pass in the same toolchain, and is then discarded.

### The ask, and we would rather have your view than guess the shape

Any of these closes it; they are in our order of preference:

1. **Have the enricher record the diagnosis where the compiler can see it** — a column on
   `resolution.csv`, or a marker beside it, saying this row was written despite a reported
   ref/assembly disagreement. Then `compile --strict` can refuse on a fact rather than on a re-run of
   the check, and `--no-strict` still builds.
2. **Have `compile --strict` re-run the rsid↔coordinate agreement it already has the data for** —
   `resolution.csv` holds both the authored coordinate and the resolved one, so the disagreement is
   visible without any network. This is the smallest change but it does put a correctness judgement
   inside the determinism gate.
3. **Refuse nothing, but make the compile *warn*** — strictly better than silence, and it costs the
   line nothing. This is the floor, not our preference: an author who did not read the enrich report
   is not obviously going to read a compile warning either.

**A candidate we argue against, having tried it:** telling authors to always run strict enrichment.
That is what we will do in our own skills, and it is not sufficient — `best_effort` exists for good
reasons (an unreachable Ensembl must not be a failure), and a module authored under it stays wrong
forever with every subsequent gate green. The defect is that the diagnosis is thrown away, not that
somebody chose the wrong mode.

### The general form of the ask, which is bigger than one coordinate

Sharpened by our owner after reading the measurement above, and it subsumes options 1–3:

> **A `compile --strict` over a `resolution.csv` produced by a `best_effort` enrichment should be
> blocked.**

The reasoning is about what the two strict flags jointly promise, not about assemblies. `strict` on
the enricher means *every row was checked against the reference and none disagreed*. `strict` on the
compile means *this artifact is reproducible*. A module that ran `best_effort` and then compiled
`--strict` gets the second stamp without the first ever having been earned — and nothing in the
artifact records which of the two happened. The published module is indistinguishable either way.

That makes the mode a **property of the derived sidecar**, not of the run that happened to produce
it: `resolution.csv` should say which mode wrote it, and `compile --strict` should refuse a sidecar
that does not carry the strict stamp. Refusal, not a warning, is what our owner asked for, and the
argument for it is that the alternative has already failed once — the enricher's diagnosis is
excellent and it still reached a green artifact, because a report nobody is required to read is not a
gate.

This also fixes a case our probe did not cover: **any** ref-mismatch class, not just an old assembly.
`best_effort` is the mode that proceeds past all of them.

**We are aware this is a behaviour change with a migration cost**, and we are not pretending
otherwise: every existing `resolution.csv` has no mode stamp, so the rule needs an
absent-means-unknown reading rather than absent-means-best_effort, or it retroactively blocks
recompiles of published modules. `None` is not `False`, and this is that rule at the artifact level.
Whether that is worth it is yours to weigh — we are stating the ask plainly because the weaker
options above all leave the same artifact publishable.

### Our side

We default to `best_effort` and expose `strict` as a flag, so our own callers meet this. We are
adding the assembly-triage prose to two skills and pointing them at rsID-only authoring, which
prevents the paste rather than catching it. Neither fix reaches a module already authored, and
neither is a substitute for the sidecar knowing how it was made.

# just-module-creator and just-dna-registry, 2026-08-31 — a second round the same day

## S79 — the licence-disagreement warning prints only the sources that mismatch, so a declaration matching one of two annotation-layer rows reads as matching none

**Status — accepted; your option (1) shipped in the tree as [RM144](ROADMAP_HISTORY.md#rm144--the-licence-disagreement-warning-printed-the-remainder-as-though-it-were-the-whole-set).**
Reproduced at the function: with your two rows and `CC-BY-NC-ND-4.0` declared, the matching-one case and
the matching-none case produced messages of the same shape, differing only in the length of a list.
Nothing in the output told them apart — which is the whole finding, and it is a real defect rather than
a phrasing nit for exactly the reason you give.

The message now reads *declares 'CC-BY-NC-ND-4.0' and 1 of 2 annotation-layer source(s) report a
different licence: ['CC-BY-4.0']*, with a distinct sentence — *no annotation-layer source reports it* —
for the case the old wording was actually written for. The tail names the mixed-licence reading
outright, so an author seeing a partial match knows it is a recognised shape rather than an unexplained
complaint about a declaration that is already correct.

**We took (1) rather than (2) or (3), and your ordering was right.** Both of the cheaper forms remove
the false reading; neither separates *unsupported* from *not universal*, which is the distinction that
cost your agents the work. The full form is three lines, so the floors bought nothing.

**One choice inside it worth your knowing: the denominator counts rows, not distinct licences.** Two
sources sharing a licence are two obligations, and the number you are checking against is how many
sources you have — counting distinct licences would report *1 of 2* for a three-row file, a number
matching nothing in it. A row with no licence stays outside the denominator, because unknown terms are
neither agreement nor disagreement, and so does a non-`annotation` layer, or the count would disagree
with the set the warning is about. All four have tests.

**Your rejected candidate is rejected here too, on your argument.** Suppressing the warning when any
row matches would silence exactly the module worth warning about — one declaring the least restrictive
of several. We did not consider overriding that.

**And you are right that this survived S77's fix.** With RM142 landing, the phantom `CC0-1.0` row goes
away and you are left with `['CC-BY-4.0']` — a real disagreement, still rendered as total until now.
Two of your reports, one underneath the other.

`declares license` still leads the sentence, so anything grepping that fragment is unaffected, and the
non-escalation is unchanged and re-pinned: two claims about a legal position disagreeing is not ours to
arbitrate.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. No reference example moves a digest,
signature or warning — the corpus has no mixed-licence module, which is why this survived it.
<!-- triaged: 0.7.0 · sha f4e68b26c202 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A two-source `SIRT6` module. `licensing.csv` carries two `annotation`-layer rows: `pmid:41249831` at
`CC-BY-NC-ND-4.0` and `pmid:28399814` at `CC-BY-4.0`. `module_spec.yaml` declares
`license: CC-BY-NC-ND-4.0` — an exact match for the first, and the binding constraint on the module.

### What it printed

```
module declares license 'CC-BY-NC-ND-4.0' but annotation-layer sources report ['CC-BY-4.0', 'CC0-1.0']
```

The declaration matches an annotation-layer row exactly, and the sentence says it matches nothing. The
filter selects the rows whose licence differs from the declared one, and the message then renders that
remainder as though it were the whole set — so the one row that agrees is invisible in the output
complaining about agreement.

### Why it costs more than a phrasing nit

**An author reads it as "your declaration is unsupported" and goes looking for the wrong defect.** In
the run that produced this, an agent re-adjudicated the module's whole licence position from scratch —
including the phantom `CC0-1.0` row from `S77` — before working out that the declaration was already
correct for the source it was chosen for. Two agents in an earlier round spent the same effort.

It is also the second-order cost `S77` names, surviving `S77`'s fix. With `RM142` landing the `CC0-1.0`
element goes away and the message becomes `['CC-BY-4.0']` — still a real disagreement worth reporting,
and still rendered as if the declared licence appeared nowhere.

### The ask

**Name the denominator.** Any of these closes it; in our order of preference:

1. **Report matched and unmatched together** — *"declares X; annotation-layer sources report X (1 row)
   and CC-BY-4.0 (1 row)"*. The author then sees whether the declaration is unsupported or merely not
   universal, which are different problems with different repairs.
2. **Say the count**: *"1 of 2 annotation-layer sources reports a different licence: CC-BY-4.0"*.
   Cheaper, and it removes the false reading without restructuring the message.
3. **Leave the list and change the verb** — *"…but 1 annotation-layer source reports…"*. The floor.

**A candidate we argue against:** suppressing the warning when any row matches. A module whose declared
licence is the *least* restrictive of several is exactly the case worth warning about, and this is a
mixed-licence module where the NC term binds the whole artifact.

## S80 — `state`'s vocabulary is published flat, and two of its six values are called retired in your own code

**Status — accepted; the standing is in the field description and shipped in the tree as [RM145](ROADMAP_HISTORY.md#rm145--states-six-members-were-printed-as-peers-and-two-of-them-are-retired-in-our-own-code).**
Your ask was one string reaching every consumer that renders `model_fields`, and that is what shipped.
Your measurement is exact, recomputed here: 377 `risk`, 4 `neutral`, and zero uses of `significant`,
`alt` or `ref` across the sixteen examples.

**"We had to read `derive.py` in our `.venv` to author one cell" is the part of the report that decided
it.** Passing our descriptions through unmodified is the right contract and we want you to keep it —
a restated vocabulary is one that drifts, which is the failure your own rulebook is guarding against.
That contract puts the obligation on us: it works only while the description carries what an author
needs in order to choose, and ours did not.

**We did not take your proposed split, and the difference matters.** You asked for
*current | retired* with `significant` among the retired. That would tell an author `significant` means
nothing, when it means something this column is the wrong place for. `state` is the Principle 5
anti-pattern our charter names by hand — one field conflating statistical significance, effect
direction and a genotype descriptor — so the grouping has to be by **which axis a value was really
on**, and `derive.py` is the evidence: `alt`/`ref` map to `unknown` on both axes, while `significant`
maps to `significant` on the significance axis and is refined from the weight sign before falling
back. Three groups:

> Direction of effect for this genotype. Current: risk, protective, neutral. Superseded, still valid
> and still read: `significant` — a significance claim rather than a direction, write
> `stat_significance` instead; `alt`/`ref` — genotype descriptors carrying no direction, which derive
> to `direction=unknown`. Prefer the orthogonal `direction`/`stat_significance` columns, which this one
> predates.

**Each group names its successor**, which is the half that makes it actionable rather than merely
honest — a standing with no destination is a warning nobody can clear, and that is our own test for
whether a deprecation belongs in a minor. All three successors ship today.

**On "the cheapest deprecation notice available" — agreed, and that is the whole mechanism here.** No
compile warning: every module carrying a superseded value would warn on every build for a value that
still works and still derives correctly, and the author of a *published* module cannot clear it.

**Removal is refused and you did not ask for it.** Major-only under P3 regardless, and the read-time
`effective_*` aliases derive from these values. Your citation of S69's lesson from the other side is
the right instinct.

Verified where you need it: the new description reaches `describe_table` verbatim, which is the surface
you build on. Three tests pin it — that every member appears with the current three named as such, that
the grouping matches what `derive.py` actually derives, and that no shipped example uses a superseded
member, recomputed at runtime rather than copied from your report.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. Also written up in
[SCHEMAS § `VariantRow`](SCHEMAS.md).
<!-- triaged: 0.7.0 · sha 94b00f4e2af2 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

An agent authoring a `VariantRow` asked the schema what `state` accepts, through our `describe_table`,
which passes your field description through verbatim and adds nothing to it:

```
state | One of: risk, protective, neutral, significant, alt, ref
```

Six values, no ordering, no note. It chose `alt` for a heterozygote and moved on.

### What the description does not say

`derive.py` calls `alt` and `ref` **the retired descriptors**. Nothing in the field description, and so
nothing in `describe_table` or `table_requirements`, carries that. The flat list reads as six peers, and
an author choosing from it has no way to know which are live.

The usage evidence agrees with `derive.py` rather than with the description. Across the 16 modules in
your `reference_examples/`, `state` is **377 `risk`** and **4 `neutral`**; `alt`, `ref` and
`significant` are used **zero times**. A vocabulary whose published form gives equal standing to values
no shipped example uses is one an agent picks from at random — and this one did.

### How we found it, which is the part we would fix first

**We had to read `.venv/…/just_dna_format/derive.py` to author one cell honestly** — that is, do exactly
what our own rulebook forbids. Our authoring surface is built on passing your descriptions through
unmodified, precisely so a vocabulary change reaches an author without us restating it and drifting.
That contract works only while the description carries what an author needs in order to choose.

### The ask

**Put the standing in the field description**, so it travels through every consumer that renders it:

> `One of: risk, protective, neutral (current) | alt, ref, significant (retired; alt/ref carry no direction)`

That is the whole fix as far as we are concerned — one string, reaching us, your CLI and anything else
reading `model_fields`. If the three are retired rather than deprecated-with-a-date, saying so in the
description is also the cheapest deprecation notice available.

**A candidate we are not asking for:** removing them. Published modules may carry them, and `S69`'s
lesson about a deprecation that said *"nothing else is lost"* is one we would rather not repeat from the
other side.

## S81 — an unknown column and a column newer than the reader are the same finding, and only this repo holds what separates them

**Status — accepted, shape decided, and filed as [RM146](ROADMAP_HISTORY.md#rm146--every-authored-column-now-says-which-release-it-appeared-in) rather than built in this pass.**
The design is settled and written down; what is left is 402 field declarations plus the guard that
keeps them honest, which is a change to every authored model in the tier. It is minor-legal and
additive, so it waits on scheduling rather than on a question. You are not waiting on a decision from
us — you are waiting on the typing, and the entry says so.

**Your finding reproduces and your framing is right.** The finding is pydantic's under
`extra="forbid"`, so it cannot be reworded into carrying the distinction — the information is not in
the model at all. That is why this is ours: no amount of care on your side can recover it.

**Decided: a `first_seen` version on the field**, in `json_schema_extra` beside the `vocabulary()`
marker, which is the existing idiom for a per-field fact an authoring surface reads. You offered "a
`first_seen` on the field, or a roster keyed the way `release_records` is keyed" and we took the first
for your own stated reason: a hand-kept list beside a model is a second statement of one fact, and it
is the copy that goes stale. You have the scar; so do we, twice, and both are in our gotcha book. On
the field, it travels through every rename and move.

Three things the implementation owes, recorded so the shape does not drift while it waits: a
registry-iterating guard asserting an **equality** over every authored field of every model (a floor or
a count is satisfied by the state that produced your report); a **public reader**, so you are not
parsing `model_fields` yourselves; and a backfill that is **measured per (model, field), not per
name** — `curator` is on `VariantRow` at v0.6.1 and gains its `StudyRow` twin at v0.6.5, checked
against the tags, so the answer is not a property of the column name.

**Your argument against `release_records` is correct, and measurement makes it stronger than you knew.**
That axis names **4 of 402** authored columns. It records what a release changed about *compiled
output*, so an optional column unset across the interval's corpus — or one no parquet carries — never
appears, and it starts at 0.6.1 so it cannot answer the question for anything older. `curator` happens
to be on it, which is exactly the danger you name: the right answer for the case in hand, and silent
wrong answers for 398 others, where absence reads as *this column has always been legal*. We would have
reached for it too. Filing your reasoning verbatim in the entry is the point of the entry.

**On the handshake half — nothing is owed and we are not treating it as a report against us.** Your
`contract_compatible` certifies the parquet contract and `artifact.digest` at `0.x` MINOR; it held here
and was right to. The authored row schema tightens at PATCH under `extra="forbid"`, that distinction
was unwritten, and your correction is yours and is made. We will say the same thing on our side when
RM146 lands, since a reader who learns *when* a column appeared will want to know why a patch could
introduce it.

**What this will not settle**, so you can plan around it: a reader still cannot be told *which* release
it is missing without also knowing its own, and that pairing is yours and already shipped. RM146
supplies only the half nobody outside this repo can compute.

**Answered is not installable, and this one is not even built** — RM146 is open, with the release
undecided. [RM_TOC.md](RM_TOC.md) carries its status; watch that rather than this reply.
<!-- triaged: 0.7.0 · sha 8d68ccd6bc2e -->

**Reported by** just-dna-registry, 2026-08-31, relaying a case from `just-module-creator`. Installed
here: format/compiler/enricher 0.6.6. The instances in the report validate at 0.6.1.

### What we ran

An author brought a single-variant module through `validate_module(strict)`, `enrich_module(strict)`
and `compile_module(strict)` locally on 0.6.6, all green, then sent the spec to a registry deployment
running format **0.6.1** for a pre-publish check. We run your `validate_spec` server-side and report
its findings verbatim.

### What happened

```
valid: false — studies.csv line 2 [curator]: Extra inputs are not permitted
```

`StudyRow.curator` is yours, added in 0.6.5 (RM120). The instance predates it, `StudyRow` is
`extra="forbid"`, and the finding is pydantic's. We reproduced both sides against the real validator
at 0.6.6: `curator` passes, and a genuine typo — `curatr` — returns

```
studies.csv line 2 [curatr]: Extra inputs are not permitted
```

The two lines differ only in the column name. **A reader of `validate_spec`'s output cannot tell a
column that postdates it from a column that was misspelled**, and the two want opposite actions from
an author: upgrade the reader, or fix the cell.

### What we shipped meanwhile, and exactly where it stops

Our 0.22.0 attaches the pair of versions to the report — *this instance validates against 0.6.1, your
client reports 0.6.6* — derived from the two version strings and never from the findings, since as
above the findings cannot carry it. That converts a dead end into a decision, and it is as far as we
can get without modelling your schema history, which we will not do: we hand-kept a map of your
sidecar spellings once and it ended up pointing the wrong way for a release.

What we cannot say is the sentence the author actually needed: **`curator` is a 0.6.5 column.**

### The ask

**A machine-readable map from a spec column to the release that introduced it**, covering the
authored row models. Anything a reader can query offline works — a `first_seen` on the field, or a
roster keyed the way `release_records` is keyed. The consumer of it is any tool that renders your
validation findings to a human, which is most of them.

### The candidate we argue against, and it is your own newest surface

**`release_records`' `parquet_schema` axis is not this**, and we say so because it is the first thing
a reader of RM126 will reach for — including us. Its targets are spelled `file:column`, and for
`curator` it would give the right answer, which is what makes it dangerous. It is a record of what a
release changed about **compiled output**: an authored column that is optional and unset across the
interval's module set, or one the compiler does not emit into a parquet at all, never appears on that
axis, and its absence there would read as *this column has always been legal*. Answering an
input-schema question from an output channel is the same category error as asking `artifact.digest`
whether two modules are the same module — which your own docs say plainly, and which we got wrong in
the other direction for five releases.

So we would rather have a small input-side roster than a clever read of the output-side one, even
though the output-side one exists today and the input-side one does not.

### One thing that is not an ask

The handshake half of this is **ours**, and we are not asking you to change anything about
compatibility. `version.contract_compatible` lives in `just_dna_registry/version.py`; it certifies at
`0.x` MINOR and passed this pair, and it was *right* to — within a minor your parquet contract and
`artifact.digest` hold, which is precisely what it exists to certify. What it never certified is the
authored row schema, which tightens at PATCH under `extra="forbid"`. We had not written that
distinction down, the consumer read the handshake as covering the whole exchange, and their workspace
notes now say *every 0.6.x interoperates*. That correction is ours and is made. We mention it only so
the report is not read as a claim that your patch policy is wrong: adding an optional column in a
patch moves no `content_signature`, and your own measurement across 0.6.1→0.6.6 shows it moved none.

# just-module-creator, 2026-08-31 — two questions rather than two defects

## S82 — a source read by hand that yields no row leaves no trace anywhere, and that is real authoring work with nowhere to go

**Status — your reading (2), and the home is already built: an uncited `literature.csv` row. Shipped as [RM147](ROADMAP_HISTORY.md#rm147--a-source-read-by-hand-that-yields-no-row-had-nowhere-to-go-and-the-home-already-existed) — documentation and a test, no behaviour changed.**
You asked for a view rather than a shape, and the view is that the record belongs in the module, on the
**paper** rather than on the service.

**A `literature.csv` row that nothing cites is kept and reported.** It stays in the CSV; the compiler
drops it from the artifact with `literature_row_uncited`, which reads *describes N citation(s) no
study, bin or pharm row in this module cites — left out of the artifact, and left in the CSV*. That
shipped in RM79 for a citation an author had deleted, and it is the same shape for your case arriving
from the other side: a paper that was read and did not become a row.

You were close on (2) — the transport exists and nothing writes it — and the file is `literature.csv`
rather than `logs/`. That matters for three reasons a log line would not give you. The row is
**structured** (`pmid`, `doi`, `exists`) and checked by the same pass that checks a cited one. It
**cannot make a licence claim**, which is exactly what made your original five rows wrong. And it is
about the **paper**, which is the thing that was consulted — the service is how you reached it, and it
is the paper that carries terms.

So we did not take (2) literally and build a `logs/` writer, and you should not either: we would have
had to specify a line format that publishes, for something unstructured and unqueryable, when a typed
row already exists.

**(1) is the near miss, and worth saying why.** S77 is about **obligations** — a source that
contributed nothing creates none, which is why your removal was right and why we agreed the general
principle two days ago. It is not a rule that the *looking* is uninteresting. Answering (1) would have
made human search effort invisible by a rule that was never about visibility, and the looking is a fact
about a paper, which this format already has a table for.

**(3) we refuse, on your own argument and one more.** You said a row meaning *no obligation* sitting in
the obligations table is the wrong place for a true statement, and that it re-opens the
check-that-cannot-fail shape S77 closed. Both correct. The extra reason: `VALID_SOURCE_LAYERS` is a
wire vocabulary, so the member would be permanent under P3 — a one-way door for a fact with a home
already.

**Your rejected candidate is rejected here too, and your reasoning is the one we kept**: a
`pubmed,literature` row with blank permission booleans sits one column away from a false all-clear for
text quoted out of a `cc by-nc-nd` paper. Losing the record was the right call over putting it there.

**And your gaps-list line is half wrong in the direction you suspected.** For a hand-read *data*
source, writing the row yourself is still right — it has a layer that fits. For a literature service it
collides with RM46, and the resolution is that there is no row to write: the consultation is recorded
on the article, not on the service.

Verified end to end: two articles, one cited and one not, a green `compile --strict`,
`literature_row_uncited` naming the unused one, and **no `licensing.csv` at all** — because nothing is
owed for reading an abstract. Written up in [SCHEMAS](SCHEMAS.md) and in `LiteratureRow`'s own
docstring, which is where the next author to ask this will be standing.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record.
<!-- triaged: 0.7.0 · sha 5be7bed5c007 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.
**We are asking for your view rather than proposing a shape** — this is the one where we think our
instinct is likely to be wrong, and where a guideline from you would be worth more than a column.

### What we ran

An agent authoring a single-variant module read five literature services by hand while working —
Crossref, Europe PMC, OpenAlex, PubMed, Unpaywall — to find and confirm the papers behind two rows. It
recorded that work the only way it could see: five `licensing.csv` rows at `layer=literature`, each
with a `notice` reading *"Bibliographic metadata read by hand through this service while authoring; no
article text was taken from it."*

### Why we removed them, and what removing them cost

They are the wrong home, and your rules say so from two directions. `TERMS_BY_SOURCE` has no `pubmed`
entry and will not (`RM46`); a literature source's terms are per **article** and live on
`LiteratureRow`. And `S77`/`RM142` settled the general principle two days ago in exactly these words —
**a pass that put no row in a table records no source**. Consultation is not consumption. We measured
it too, before deciding: with and without those five rows, `validate --strict` and `compile --strict`
return identical verdicts and identical warnings, because literature-layer rows are exempt from the
orphan check outright. The rows bought no enforcement.

So we removed them and corrected our own skills, which had been contradicting each other about it.

**And that is where the item is.** What was removed was not a licence claim. It was a record that a
human went and looked — at five services, deliberately, and found the second paper that this module's
whole longevity claim rests on. **After removal there is no trace of it anywhere**: not in
`licensing.csv`, not in the manifest, not in `literature.csv` (which has rows only for articles that
became rows), not in `logs/`. The module now says less about how it was made than it did.

### The specific shape of the gap

Our own gaps list has carried this line for a while, and we now think it is half wrong:

> *No column recording why a source was consulted, and none recording that a source was read by a
> human rather than fetched. `source` is free text, so the honest way to record a hand-read source is
> to write the row yourself.*

For a hand-read **data** source that is fine — it has a layer that fits. For a literature service it
collides with `RM46`: write the row yourself, at the one layer that is forbidden. We have scoped our
own text to say so. What we cannot resolve is the underlying question.

### What we are asking

**How do you see a consultation being recorded, if at all?** Genuinely open, and "it should not be" is
a complete answer we will write down. Three readings we can see, none of which we are attached to:

1. **It should not be recorded, and the module is right to be silent.** `S77`'s principle applied
   straight through: a source that contributed nothing creates no obligation and no fact. The
   consequence is that human search effort is invisible by design, which may be correct — provenance
   is about what is *in* the module, not about how long somebody looked.
2. **It belongs in `logs/`, and nothing writes it.** The compile already sweeps `logs/**.log` into the
   published artifact with no opt-out, so the transport exists and costs nothing. What is missing is
   any writer for "consulted X, took nothing" — ours only logs cell-level authoring moves. If this is
   your reading, we would build the writer on our side and would want to know the line format you
   would accept, since it publishes.
3. **The vocabulary is what is short.** You asked us once whether an extension would help elsewhere,
   so we will say where we think one might here: a `layer` member, or a boolean, that means *consulted
   and contributed nothing* would let the row exist without asserting a licence obligation — which is
   the thing that made these rows wrong. We are **least** confident in this one: it re-opens the
   check-that-cannot-fail shape `S77` just closed, and a row that means "no obligation" sitting in the
   obligations table seems like the wrong place to put a true statement.

**A candidate we argue against outright:** keeping the rows as they were. A `pubmed,literature` row
with blank permission booleans is a true statement in a file that a downstream consumer reads to
decide redistributability, sitting one column away from source-level booleans that would be a false
all-clear for the article text quoted from a `cc by-nc-nd` paper. We would rather lose the record than
put it there.

## S83 — `direction` has no member for a concordant trend whose sign is not established, and two runs of one prompt split on it

**Status — your reading (1): not a vocabulary gap, and the description now says so. Shipped as [RM148](ROADMAP_HISTORY.md#rm148--direction-and-stat_significance-are-one-pair-and-the-description-did-not-say-so).**
You named the cheap answer and it is also the right one, for a reason worth stating rather than
asserting: **the orthogonality is itself the answer to your question.** `direction` records the sign of
the reported estimate; `stat_significance` records how far to lean on it. So *is a sign you cannot lean
on still a sign* resolves to yes — because the other column is the one that says you cannot lean on it.

**The state you wanted a member for already exists, as the pair.** `direction=risk` +
`stat_significance=not_significant` is exactly *a real trend the evidence does not establish*, and it
authors and validates today. There is a test that constructs your row — `rs117385980`, `risk`,
`not_significant`, OR 3.58 — rather than arguing about it.

**Run A was right and run B lost information.** Writing `unknown` for a concordant non-significant
trend discards the sign the paper actually reports, and leaves `stat_significance` making a statement
about nothing. That is the half your old description left an author to work out, and both your runs
were defensible against it, which is the definition of a description that does not settle the question
being asked. It now reads:

> Effect direction: one of protective|risk|neutral|unknown. The sign of the reported estimate, whether
> or not it is established — a non-significant or borderline trend still has a direction, and
> `stat_significance` is what says how far to lean on it. `unknown` means no sign to record (not
> assessed, or the sources conflict), never a sign you may not act on. Orthogonal to `state`, which
> predates both.

**Bounding `unknown` is the load-bearing clause.** You identified the overload precisely — it was
covering *no evidence*, *conflicting evidence* and *evidence that does not exclude either direction*.
The first two are one thing (nothing to record); the third is the pair's job. Saying so is what stops
the two readings being equally available.

**(2), a new member, we refuse — and you were right not to push it.** *Looked, and no sign
established* would be a **second spelling of the pair**: two ways to write one state, with consumers
splitting on which they read. That is Principle 5's overloading arriving as a synonym rather than as a
conflation, and it is a wire vocabulary change, permanent under P3, for something already expressible.
A test now asserts the two vocabularies stay disjoint but for `unknown`, over the walked sets rather
than by naming members, so a future addition has to face this deliberately.

**(3) partly stands and is not a substitute.** Your rule — where the interval contains the null or the
row carries a counter-direction, say which value you chose and why in `conclusion` — is good practice
for a genuinely contested row, and your instinct that "prose covering a gap is usually the sign the gap
is real" is a good one. It was right here: the gap was in *our* prose, not in the vocabulary.

**Your module is not self-contradictory**, for what it is worth: `direction: risk` recording the point
estimate, `negatives` carrying the counter-direction, and `flags: pleiotropic` beside it is three cells
each doing its own job, which is what the orthogonal axes are for.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. Also in [SCHEMAS](SCHEMAS.md), beside the
`state` note S80 prompted an hour earlier.
<!-- triaged: 0.7.0 · sha ef8be021b4dd -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.
Filed in the same spirit as `S80`, which you accepted an hour ago as `RM145`: the question is whether
the published vocabulary carries what an author needs to choose.

### What we ran

Two runs of a byte-identical prompt over the same paper, by the same model, authoring `rs117385980`
(SIRT6) for a longevity module. Both green through every gate. They wrote **different values in
`direction`** for the same variant on the same evidence:

| | run A | run B (rerun) |
|---|---|---|
| `direction` | `risk` | `unknown` |
| `stat_significance` | `suggestive` | `not_significant` |

### The evidence both were reading

- Two cohorts, Finnish and Iranian, and **both trends run the same way**: the T allele is depleted
  among the longest-lived.
- Neither is significant: **p ≈ 0.074 and 0.073**.
- Combined **OR 3.58, 95% CI 0.96–13.4** — the interval contains 1 — at **28.4% power** by the
  authors' own analysis.
- And the row that says `direction: risk` carries, in its own `negatives`, that the same allele is
  *more* frequent among robust participants than frail ones — the opposite direction — with
  `flags: pleiotropic` set beside it because the source paper raises antagonistic pleiotropy.

So one module simultaneously asserts a direction, records the counter-direction, and flags itself
pleiotropic. Every one of those cells is individually correct.

### What the vocabulary offers, and what it does not

`direction` is `protective | risk | neutral | unknown`, documented as orthogonal to `state`. That
orthogonality is right and is the reason `risk` is defensible here: `stat_significance: suggestive`
already carries "not established", so `direction` is free to record the sign of the point estimate.

But `unknown` is equally defensible, and for a reason the vocabulary cannot express: **an interval
containing the null is a sign that has not been established**, which is a different claim from "nobody
looked" — and `unknown` is the only member available for it. So the same word covers *no evidence*,
*conflicting evidence* and *evidence that does not exclude either direction*, and a consumer cannot
tell them apart. Meanwhile `risk` covers both *established* and *point estimate only*.

### What we are asking, and we are not asking for four new members

**Your view on whether this is a vocabulary gap at all.** We can see three answers and would take any:

1. **It is not.** `direction` records the sign of the estimate, `stat_significance` records whether
   you may lean on it, and reading them together is the consumer's job. If so, **say it in the field
   description** — that is exactly what `RM145` just did for `state`, it costs one string, and it
   would have settled our two runs. Our current text is *"Effect direction: one of
   protective|risk|neutral|unknown. Orthogonal to `state`."*, which does not say whether a
   non-significant trend has a direction.
2. **`unknown` is overloaded and one member would fix it** — something meaning *looked at, and the
   evidence does not establish a sign*, distinct from *not assessed*. This is the extension we can
   most easily imagine, and we note it costs a wire vocabulary change and touches every consumer, so
   we would not push for it on one variant.
3. **It is a `weighting:`-shaped question rather than a column one** and belongs in prose, in which
   case we will keep it in our skills and stop looking for a cell.

**What we did meanwhile.** Kept `risk` in the reference module and added the disagreement to its
decision list, so a reviewer sees the judgement rather than a value. And added a rule to our own
authoring skill: where the interval contains the null or the row carries a counter-direction, say
which value you chose and why in the row's `conclusion`. That is prose covering a gap, which is
usually the sign the gap is real.

# just-module-creator, 2026-08-31 — a source scored for a paper, and the number that scored it

Filed from writing a comparison table rather than from a broken run, and the report's own framing
is that the measurement in it decides whether the adoption is worth anything. It was right about
that, and the follow-up probe moved the number.

## S84 — CIViC is a source of the same kind as PubMind, and its germline quarter is the only part that reaches a VCF

**Status — accepted as a measurement, filed as [RM152](ROADMAP_HISTORY.md#rm152--civics-germline-quarter-says-almost-nothing-on-the-axis-we-asked-it-and-a-great-deal-on-the-one-next-to-it); neither candidate adoption survived, and the one you preferred is the one that dies.**
Every number reproduced against `civicdb.org/api/graphql` on 2026-08-31, including the 412 you got by
subtraction — queried individually it is `UNKNOWN` 374, `COMBINED` 20, `MIXED` 18, and the seven
buckets sum to 11,518 exactly, so the enum partitions cleanly and germline is 3,103, 26.9 %. You are
also right that nothing here needs a schema change: `concordance.py` already keys `authority: str`,
and RM134's two five-member vocabularies were stress-tested to hold at any number of authorities.
Legality was never the obstacle, and CC0 makes the licence row trivial.

**What the follow-up probe found is that 3,103 is not the operative denominator.** Of the germline
subset, the ACMG five-tier — the only members `VALID_CLIN_SIG` can receive — covers 599, and **594 of
those are `UNCERTAIN_SIGNIFICANCE`**. That leaves 4 `PATHOGENIC`, 1 `LIKELY_PATHOGENIC`, and **zero
benign-class calls of any kind**; the largest single germline significance is `NA` at 812. Scoped over
both tables rather than one: `assertions` takes no `variantOrigin` filter, so all 296 were paged and
split per record — 275 `SOMATIC`, 6 germline, 5 pathogenic-class, 1 uncertain, none benign-class, none
`COMMON_GERMLINE`. So the finding is as wide as `evidenceItems` **and** `assertions`, and no wider.

**That kills the concordance candidate, which was your preferred one.** The check's entire product is
opposition — a pathogenic-class call set against a benign-class one — and `concordance.py` states in
terms that an uncertain call opposes nothing. An authority carrying 5 calls in one camp and 0 in the
other cannot make `discordant` sayable about anything; it would join and read `single` or `concordant`
by construction. Your sentence *"3,103 items is too few to draft from and plenty to disagree with"* is
exactly half right, and the wrong half is the one the preference rests on: the disagreeing quantity is
5. Your argument against the drafter stands and measures worse than you knew — the germline remainder
that survives the origin filter is a further quarter unclassified.

**What survives is real, and it is one axis over from where you aimed.** By evidence type the germline
subset is 2,867 of 3,103 `PREDISPOSING`; by significance, `PREDISPOSITION` 1,456 + `PROTECTIVENESS` 2.
That is our `direction` axis, not `clin_sig`. Your instinct to connect this to S83 was sound and lands
there: `PREDISPOSITION` × `DOES_NOT_SUPPORT` is **4 items**, precisely the reading `contested` was
added for when RM150 shipped on 2026-08-31, hours before your report arrived. But there is no
`direction`-axis concordance check to add an authority to — the RM130/RM134 machinery is clin_sig-only
end to end — so the open question RM152 carries is *does `direction` warrant the apparatus `clin_sig`
has*, not *adopt CIViC*. It is filed with **no release class on purpose**, because an item with no
repair has none to state.

One correction worth making since it will be quoted: you reason from *"this ecosystem annotates
germline genotypes from a VCF"* as though it were a charter rule. It is not — the Constitution says
nothing about germline. It is a fitness argument about what a consumer's genotype can satisfy, which is
the right argument and does not need charter standing. What the charter does settle is the half you
raised by analogy: recording what an authority *said* catalogs a curated annotation rather than
inferring a gene–disease relation, so CIViC is legal to consume for the same reason ClinVar and PubMind
are. It fails on quantity, not on principle.

**What to do now:** nothing on your side, and keep the paper's table as you have it — *a source to
consume rather than an alternative* is the conclusion the measurement supports. If you want to move
RM152, the probe that would do it is the one you declined to claim: `SUPPORTS`/`DOES_NOT_SUPPORT` ×
`PREDISPOSITION`/`PROTECTIVENESS` mapped against `VALID_DIRECTIONS`, over a corpus where you can say
how many of the 1,458 rows your modules actually reach.
<!-- triaged: 0.7.0 · sha af8bd379c019 -->


Filed from `just-module-creator` on 2026-08-31. This one did not come from a broken workflow: it came
from writing the comparison table in our paper, where CIViC had to be scored against the same criteria
the PubMind assessment used. It scored the same way, so the conclusion in
[PUBMIND_ASSESSMENT.md](PUBMIND_ASSESSMENT.md) — *"PubMind is a **source**, of the same kind as ClinVar,
gnomAD or the GWAS Catalog"* — appears to apply to CIViC unchanged, and the enricher already consumes
four such sources. We are reporting the measurement rather than asking for the adoption, because the
one number below is what decides whether the adoption is worth anything.

**What we probed.** The public GraphQL API at `https://civicdb.org/api/graphql`, 2026-08-31, no key
required:

| | |
|---|---|
| Evidence items | 11,518 |
| Variants | 5,065 |
| Genes | 734 |
| Molecular profiles | 5,661 |
| Assertions | 296 |

`EvidenceLevel` is the closed enum `{A, B, C, D, E}`. Every evidence item carries its own source:
querying `source { citationId sourceType title }` on evidence item 116 returns
`citationId 19357394`, `sourceType PUBMED`, and the paper's title. That is per-record provenance to a
PMID, already in the shape `studies.csv` wants, which is why the comparison table gives CIViC a tick on
provenance where it gives VEP a dash. Content is **CC0 1.0 Universal** (their FAQ: *"The content of
CIViC, hosted by Washington University School of Medicine is released under the Creative Commons Public
Domain Dedication (CC0 1.0 Universal) and the source code for the CIViC application is licensed under
the MIT License"*), so `licensing.csv` has an easy row and redistribution is not the obstacle.

**The number that matters, and it is the reason to read this before building anything.** `VariantOrigin`
is the enum `{SOMATIC, RARE_GERMLINE, COMMON_GERMLINE, UNKNOWN, COMBINED, MIXED, NA}`, and the evidence
items split:

| Origin | Evidence items |
|---|---|
| `SOMATIC` | 7,376 |
| `RARE_GERMLINE` | 3,018 |
| `COMMON_GERMLINE` | 85 |
| `NA` | 627 |
| the remaining three values | 412 (by subtraction from 11,518; not queried individually) |

**CIViC is a somatic cancer-interpretation resource, and this ecosystem annotates germline genotypes
from a VCF.** The applicable subset is `RARE_GERMLINE` + `COMMON_GERMLINE` = **3,103 evidence items,
27% of the database** — and `COMMON_GERMLINE`, the 85, is the part a population-frequency module would
actually meet. A drafter that pulled CIViC wholesale would fill a module with assertions about tumour
tissue that no consumer's genotype can satisfy, and every one of them would pass schema validation.

**What we did meanwhile.** Nothing in the tool. We added CIViC to the paper's comparison table as a
curated knowledgebase — ticks on schema validation, provenance and shared catalog, dashes on versioned
modules and AI-assisted authoring — and said in prose that it is a source to consume rather than an
alternative. No `draft_from_civic` exists and we have not started one.

**A candidate, and the argument against our own first version of it.** The obvious move is
`draft_from_civic` beside `draft_from_clinvar`. We think that is wrong as stated, for a reason the
somatic split makes concrete: the natural filter is `variantOrigin` in `{RARE_GERMLINE,
COMMON_GERMLINE}`, and applying it silently would hide from the author that 73% of the source was
dropped — the same defect as a check whose scope is narrower than its name. If a drafter is built, the
count it excluded belongs in its result, not in its docstring.

The second candidate is the one we would rather have: CIViC as a **second authority for a concordance
check**, the shape RM134 gave PubMind. It is a better fit here than a drafter, because 3,103 items is
too few to draft from and plenty to disagree with, and because CIViC's `evidenceDirection`
(`SUPPORTS` / `DOES_NOT_SUPPORT`) is an independently curated opinion about a direction — which is
live for you right now, since **S83** is about `direction` having no member for a concordant trend
whose sign is not established. We have not checked whether the two vocabularies map cleanly, and that
is the next probe rather than a claim.

**What we are not asking for.** Not a schema change. Nothing above needs a new column; the question is
whether a somatic-majority source earns a place beside the four the enricher already reads, and that
is your call about the enricher's scope, not ours.

# just-module-creator, 2026-08-31 — an absence the source did not report

## S85 — `status: not_found` for an rsID the source has, when what failed was allele matching

**Status — accepted, both halves; shipped in the tree as RM154, uncut at 0.7.0.** Your reading of
`enrich.py`'s neighbouring arms is exactly right, and it found a second defect you did not file.

Reproduced end to end, offline, against the real `enrich` path: a snapshot carrying `rs61849494` at
`1:11856378 C>T` with the genotype authored as its complement writes `status="not_found"`,
`chrom=None` — and a snapshot that genuinely lacks the rsID writes a **byte-identical row**. Two
different states of the world, indistinguishable in the artifact. That is the collapse RM98 repaired
one branch over arriving from a third direction: there nobody asked, here the asking *succeeded* and
the answer did not match.

**We took your second option, and your argument against the cheap one holds — with a sharper reason
than redundancy.** `EnrichmentResult.allele_mismatches` now carries
`AlleleMismatch(rsid, genotype, loci, offered, strand_flip)`, the shape `ref_mismatches` and
`stale_rsids` already have. A new `VALID_RESOLUTION_STATUS` member is a wire change every reader of a
published `resolution.csv` shares; but *deleting* the row — the other obvious repair, and the one that
looks most honest — is worse still, and measurably: `variant_key` and `rsid` are
`RESOLUTION_FACT_FIELDS` while `status` is provenance and is not, so removing the row moves
`resolution_signature` and changing its status is free. Checked rather than reasoned. The row was never
the untruth; it is honestly unresolved either way. Only the reason it gave was wrong, so only the reason
moved.

**The second defect is in the sentence you quoted.** `hosting_verdict` returns a confident `False` from
two arms — a substitution/MNV locus (no flank, so no spelling freedom) and an event length the locus
does not offer — and the warning asserted the second arm's reason for both. So your five rows were told
*"The event sizes differ, which re-anchoring cannot change"* about two 1 bp substitutions, which is a
false claim and is precisely what sent you to dbSNP. That is `undecided_reason`'s repair arriving on the
`False` side, so `compiler.resolution.contradiction_reason` is now its twin, walked by a test asserting
the arms' reasons are pairwise distinct.

Your case is now named where it is established: *"the authored alleles are the reverse complement of
this locus's — reading A/G on the other strand fits it exactly. The source HAS this variant"*, plus one
aggregated run line saying the source has them, so an author grepping for `not_found` is contradicted
rather than confirmed. `strand_flip` is `False` for *not established*, never *established otherwise* —
an allele that cannot be complemented withholds it — and `strand_flip_explains` tests `called <= locus`
first, because a palindromic SNV satisfies both readings and would otherwise report a flip for a
genotype that needed no explaining.

Not changed, deliberately: the rows stay `not_found` in `resolution.csv`, and `unresolved` stays right,
as you said. Nothing in your data needs editing beyond the five genotypes' strand. The new symptom
entries are in the authoring skill's guide, so the next author is sent to the strand rather than to
dbSNP — which is what you did for your own team meanwhile.
<!-- triaged: 0.7.0 · sha 8d0159ae0d36 -->

Reported by `just-module-creator`, 2026-08-31. Enricher 0.6.6.

**What ran.** A 64-variant longevity module, every subject an rsID authored from a paper whose
supplementary is GRCh37/hg19. `enrich(mode="best_effort")` on GRCh38 left five unresolved and wrote
each of them into `resolution.csv` as `status: not_found`, `source: ensembl` — `rs2762745`,
`rs575564328`, `rs61849494`, `rs61849498`, `rs796389673`.

**Why that reading is wrong.** Ensembl has all five. `lookup_variant` returns each of them
immediately, and the module now resolves all 64 — same rsIDs, same request path. What actually failed
is allele-aware matching: the paper's hg19 alleles are the exact reverse complement of GRCh38's at
those five positions (`rs61849494` is `G/A` in the paper and `C/T` on GRCh38), so the authored
genotypes are not drawn from the allele set the resolver found.

Those are different facts and the author acts on them differently. `not_found` sends you to *does this
rsID exist* — a question with an obvious answer that is not the problem. The real answer is *the source
has this variant and your alleles are on the other strand*, which is one of the highest-value catches
in the pass: nothing downstream would have found it, and the module would have compiled green and
matched no VCF. The run spent its single largest diagnosis detour on that misdirection before working
out what had happened.

**This is your own rule, applied one branch over.** `enrich.py`'s neighbouring arms are explicit about
it. The unconsulted branch refuses to write `not_found` because that would be *"a negative nobody
established, about a question never put"*, and names `unconsulted_rsids` separately from
`unreachable_rsids` because *"'nothing was asked' and 'the asking failed' are two different states of
the world, and collapsing them would replace one small untruth with another."* The GRCh38 arm at
`out.append(ResolutionRow(..., status="not_found"))` collapses a third state into the same word: the
asking succeeded and the answer did not match. `not_found` there asserts the source does not have the
rsID, which is false and is checkable against the very response that produced the row.

**What we did meanwhile.** Nothing in the data — the rows are legitimately unresolved and the
`unresolved` list is right. We record the reading in our own symptom guide so the next author is sent
to the strand rather than to dbSNP.

**A candidate fix, and the argument against the cheap one.** The cheap fix is a distinct status, but
`VALID_RESOLUTION_STATUS` is a wire vocabulary and `ambiguous` already exists next door, so adding a
member is a format change with consumers to carry. The alternative that costs no vocabulary is a
structured diagnosis beside the row — the shape `ref_mismatches` and `stale_rsids` already have — say
`allele_mismatches: list[AlleleMismatch]` carrying the rsID, the authored alleles and the resolved
allele set. That keeps the artifact's vocabulary fixed, makes the state legible in the result object
where a caller can surface it, and leaves the row itself honestly unresolved. If you prefer the status
member, the one we would want is not `not_found`.

# just-module-creator, 2026-09-01 — a check as wide as one table

## S86 — `check_identifiers` reads `variants.csv` only, so a trait id that lives in `studies.csv` is never checked and the tally says `0`

**Status — accepted, both halves, and wider than filed; shipped in the tree as RM155, uncut at
0.7.0.** Reproduced offline in both directions: a spec whose only `trait_efo_id` sits in
`studies.csv` returns `module_trait_ids(variants) == []`, and a spec whose only `gene` sits in
`haplotypes.csv` returns an empty gene roster. Thank you for the correction about the check not being
dead — it saved the reproduction, and you were right that the scope and the `0` are the defect.

**The scope is wider than "studies.csv and the binning kinds".** Walking `_ALL_MODELS`: **eleven**
authored models declare one of these columns, so the roster now covers **nine tables per column**,
derived from `DRAFTABLE` rather than listed. A hand-kept set here would be the same bug with a longer
literal in it, so the test asserts an equality over the walked registry — a table kind added later
joins by existing. Two edges fell out of that walk. `MeasureBinRow` is correctly absent, being the
abstract base whose four concrete subclasses are each their own entry (pinned, not assumed). And the
three **derived** models carrying these columns — `GeneMetricsRow`, `GeneValidityRow`, `GwasEffectRow`
— are deliberately outside it: they are machine-written, so a stale id there is the *source's*
currency and no author can act on it. `dataset_currency` is the surface that asks that question.

**We took your `not_read` suggestion as well, because widening alone would have left the hole.** You
put it as the fallback if the roster stayed narrow; it is load-bearing either way, since a widened
roster still returns `[]` for a module that genuinely declares no trait. `IdentifierReport` now carries
`trait_tables_read` / `trait_tables_not_read` and the gene pair beside them, and the CLI count names
its own denominator — `traits checked: 0 (from 2 table(s): studies.csv, variants.csv)`. An absent
optional table and one that exists and will not parse are kept apart: the first is every module's
normal shape and says nothing, the second warns, because it means ids you really do carry went
unchecked.

**Your framing found one more, one level up.** `report.clean` is vacuously true over an empty roster,
so `check-identifiers` printed a green *"all identifiers current"* having asked nothing at all — the
same unreadable zero wearing a pass. It now says what it read.

Nothing about your data needs changing, as you concluded. Your wrapper's warning is welcome but should
become unnecessary: `spec_dir=` reads all nine tables now, and the narrow roster survives only for a
caller passing `variants=`, which is told so in `*_tables_not_read` rather than left equal to the wide
case.
<!-- triaged: 0.7.0 · sha bc7dcb9fcc92 -->

Reported by `just-module-creator`, 2026-09-01. Enricher 0.6.6.

**What ran.** A 67-variant module whose `studies.csv` carries `trait_efo_id` on all 68 rows.
`check_identifiers` returned `trait_tally: {checked: 0, clean: 0, flagged: 0}` beside
`gene_tally: {checked: 55}`. `module_trait_ids(variants)` is the whole roster — the trait ids in
`studies.csv` are not in it, and `StudyRow` has carried `trait_efo_id` since 0.3.

**Why `0` is the problem rather than the omission.** A reader cannot tell *this module declares no
trait* from *this module's trait ids are in a table the check does not read*. Both print `checked: 0`,
and `0 clean, 0 flagged` beside it reads as a clean run — which is the three-valued rule at a finer
grain, and the one your own `unconsulted_rsids` split (RM98) exists to protect one layer down. A
module can therefore ship a retired or simply wrong CURIE with every gate green, provided the id sits
only in `studies.csv`.

**The gene half is the same defect and is worth fixing in the same change.** The roster is built from
`variants.csv`, so a `gene` on a binning row is never checked either. We have had that one in our own
notes since 2026-08-20 as an instance of *a check is only as wide as the table it reads*, and never
filed it, which was our mistake — filing it now with the trait half, since one fix covers both.

**What we did meanwhile.** Nothing to the data: the module's ids are correct, verified by putting each
through `lookup_identifier` by hand. Our own wrapper can see both tables, so we will likely warn when
`studies.csv` carries trait ids the check did not read — but that is a plaster over a scope question
that is yours, and it cannot make the underlying check any wider.

**Candidate fix.** Widen the roster to every authored table that carries the column — trait ids from
`variants.csv` and `studies.csv`, gene symbols from `variants.csv` and the binning kinds — and keep
the tally counting the union. If the roster stays narrow deliberately, then the honest report is a
`not_read` count beside `checked`, naming the tables skipped, so `0` never has to mean two things.

**One correction to the report that produced this, offered because it may save you a reproduction.**
The run that found it concluded the trait check *never runs*. It does: once the same module's
`variants.csv` carried `trait_efo_id`, the next call returned `checked: 1, clean: 1`. The first call's
`0` was honest for the table it read. The defect is the scope and the unreadable `0`, not a dead check.

# just-module-creator, 2026-09-03 — a before-the-cut report against the 0.7 branch

## S87 — an overlay row's `reason` prose is inside `content_signature`, and fixing a typo in it mints a new content identity

**Status — accepted, decided with the maintainer on 2026-09-03 and shipped the same day in the uncut
0.7.0 as [RM180](ROADMAP_HISTORY.md#rm180--an-overlay-rows-provenance-was-inside-content_signature-and-rewording-a-reason-minted-a-new-content-identity).** Reproduced exactly as
reported, on `reference_examples/hboc_palb2`: `sha256:43ad8ac1…` with no overlay, then a distinct
signature for the same correction under a reworded `reason` and again under a changed
`decided_by`/`decided_at`. The line is drawn where you argued it should be — `reason`, `decided_by`
and `decided_at` are outside `content_signature`; the six cells that say *what* the correction is stay
inside — and on the precedents you cited: S25 keeps a README caveat out of both identity halves, and
the fact-signature family keeps `fetched_at`/`status` out of every derived table's hash. **Your
candidate mechanism was not taken, and the suite is what refused it.** `exclude=True` is the
stamped-column idiom, and it empties the three cells in every writer that serializes a row through
`model_dump()` — `draft._authored_dump` in production, and the enricher's own overlay writers in its
tests — so a drafted overlay row would have failed its own compile on the blank the tool wrote. The
three carry a field marker instead (`base.OUTSIDE_CONTENT_IDENTITY`, walked by
`content_identity_exclusions`) that `integrity.content_signature` alone reads; `model_dump()` stays
complete, and a test pins the marked set over every model to exactly those three. Everything else
still sees the prose, as you expected: `overrides.parquet`, the raw-bytes hash of `overrides.csv` in
`manifest.inputs`, the verification binding (a reworded reason still un-closes a module) and
`artifact.digest`, which moves. The asymmetry you argued against your own fix stands and is stated in
SCHEMAS rather than repaired, beside a second one you did not raise: `curator`/`method` on
`variants.csv` are inside the signature and stay there, because moving them re-keys every published
module. The maintainer's note on your closing paragraph became
[RM181](ROADMAP_0_8.md#rm181--a-byte-digest-that-moves-beside-intact-signatures-says-something-changed-and-not-what-and-provenance-has-no-shift-tracker) — a byte digest moving beside intact signatures says *something*
changed and not *what*, and provenance has no shift tracker of its own. **What to do now:** nothing.
No published module carries an overlay, so no signature moved; once 0.7 is cut, an overlay whose
reason you improve is a patch. If you compute the signature yourself rather than calling
`integrity.content_signature`, drop the three columns via `content_identity_exclusions(OverrideRow)`. <!-- triaged: 0.7.0 · sha 720cc1c7a5c3 -->


Reported from `just-module-creator`, 2026-09-03, against the 0.7 branch at `f4a9b14`
(`schema`/`compiler`/`enricher` installed editable from `/data/sources/just-dna-format`, so
`just_dna_format.__file__` is your tree, not a wheel). We are building a preview branch against the
uncut 0.7 to find things while they are still cheap to move, which is why this is a "before the cut"
report rather than a bug.

**What we ran.** Copied `reference_examples/hboc_palb2` twice, added an `overrides.csv` to one, and
asked for `content_signature` on each — no compile, no network:

```python
from just_dna_compiler import compiler
compiler.content_signature(a)   # no overlay
compiler.content_signature(b)   # + overrides.csv
```

| spec | `content_signature` |
| --- | --- |
| no overlay | `sha256:43ad8ac1…` |
| `frequencies.csv / 16:23603657:AC:A / global / faf95 → 0.0001`, reason `"probe"` | `sha256:aed031fd…` |
| same row, value `0.0002` | `sha256:b9399ab8…` |
| same row, same value, **reason text changed only** | `sha256:950a4edc…` |

The first three movements are correct and we are not reporting them: an overlay is authored input,
the value it writes changes what the module asserts, and `spec_tables`' comment says so outright.
**The fourth is the report.** `reason`, `decided_by` and `decided_at` carry no `exclude=True`, so they
reach `model_dump()` and therefore the hash. Rewording a sentence, correcting an initial in
`decided_by`, or two curators recording the identical correction on different days each produce a
different *content* identity for byte-identical data.

**Why we think that is the wrong side of the line, using your own argument.** `stamped_identity_field`
in `base.py` states the rule we are appealing to — a value that adds nothing to a content identity is
excluded, because moving the signature of an already-published module "is the one thing a
content-dedup key may not do" — and `compile_module`'s docstring keeps `README.md` out of both
identity halves for the same reason, citing S25: *prose about the module is not part of its identity,
so fixing a caveat is a patch.* An overlay `reason` is prose about a correction. It is required, it is
load-bearing for a human reader, and it is exactly the cell an author will improve on a second pass —
and improving it is the case S25 decided should be a patch.

**Why now rather than later.** No published module carries an `overrides.csv`, so excluding the three
fields today moves nothing. After 0.7 is cut, excluding them moves the signature of every module
published with an overlay, which is the movement the `base.py` comment says is unavailable. The
window is the release, not the design.

**Candidate fix, and the part we are least sure of.** Exclude `reason` / `decided_by` / `decided_at`
from `model_dump()` the way `stamped_identity_field` does, keeping them in the parquet (`_build_table`
already reads fields off the model directly) and in `manifest.inputs`, whose raw-bytes hash still
covers the file and is the right place for "this exact overlay file, prose and all". `artifact.digest`
would then still move on a reason edit via `overrides.parquet`, which we think is correct — the
artifact carries the prose — while `content_signature` would not.

**The argument against our own fix, which you may find decisive.** Unlike a README, the overlay's
prose sits *in a data table* that compiles to a parquet, and a reader who dedups on
`content_signature` and then reads `overrides.parquet` would find two modules with one signature whose
overlay prose differs. If that asymmetry is worse than the typo-mints-an-identity one, the other
consistent answer is to say so in `spec_tables`' comment — it currently justifies including the
overlay without distinguishing the value cells from the provenance cells, and we read it as not having
considered them separately.

**What we did meanwhile.** Nothing — we have no module carrying an overlay yet, and our adoption of
`overrides.csv` is the work this probe was opening.

# just-module-creator, 2026-09-03 — a recompile question with no lower bound

## S88 — `needs_recompile` raises `AttributeError` on the one input it is most likely to be handed: a manifest that stamped no compiler version

**Status — accepted and shipped 2026-09-03 in the uncut 0.7.0 as
[RM183](ROADMAP_HISTORY.md#rm183--needs_recompile-crashed-on-the-one-input-a-registry-is-most-likely-to-hand-it-an-unstamped-compiler-version).** Your table reproduced row for row. `None`, `""` and whitespace now
answer alike and answer the way you argued: every axis `None`, `complete=False`, `compiled_under=None`,
`span=(None, current)` — the unknown arm, the same answer the table gives for a release it has no
record of, and a stronger case for it. Your doubt was weighed and the line is drawn one row down: a
stamp that is **present and unreadable** (`"0.7"`, `"v0.7.0"`, `"0.6.6+local"`, a trailing note) is a
different state — asked and cannot be read, a caller's bug to fix — and still raises `ValueError`, now
quoting the **whole** stamp rather than its last token, so `(marketplace-server)` is named beside the
version it followed. Absent, malformed, uncovered: three states, two answers, one refusal. The prefix
is deliberately unchecked — one version across the workspace is the rule, so `just-dna-format 0.6.6`
names the same release. Two type widenings a reader of `RecompileAnswer` should know:
`compiled_under` and `span[0]` are `str | None` now, `None` only where the call used to crash. **What
to do now:** adopt it — loop over stored manifests and group the `complete=False` answers by whether
`compiled_under` is `None` (nobody stamped) or a version (no record covers it); nothing else about the
call changed. <!-- triaged: 0.7.0 · sha 24a374c07f0f -->


Reported from `just-module-creator`, 2026-09-03, 0.7 branch at `f4a9b14`, installed editable.

**What we ran.** The call your own § 2.8 recommends, on a manifest read back through `read_manifest`:

```python
mf = read_manifest(out / "manifest.json")     # parses fine
mf.compilation.compiler_version               # None
needs_recompile(mf.compilation.compiler_version, "0.7.0")
# AttributeError: 'NoneType' object has no attribute 'strip'
```

`Compilation.compiler_version` is `str | None` with a `None` default, so a manifest carrying nothing
there is well-formed and round-trips through your own reader. We produced one by editing a real
compiled manifest and re-reading it — no private API, no constructed model.

**Why this is the input that matters rather than a fuzzing result.** The consumer you named for this
API is a registry's `revalidate` / `needs_upgrade`, which walks manifests it did not produce.
`INTEGRATION_0_7 § 3` tells `just-dna-marketplace` to "adopt `needs_recompile` for the
`revalidate` / `needs_upgrade` derivation", and the obvious implementation is a loop over stored
manifests. One manifest with an unstamped `compiler_version` takes that loop down with a
`NoneType.strip`, which is not an error a caller can catch by type or act on by reading.

**And the answer it should give already exists in the design.** The three-valued axis is the whole
point of this API — `None` is *unknown*, `complete` is False over a span you have no record for. An
unstamped version is the purest possible "unknown provenance", and it is the one case that raises
instead of blunting. `needs_recompile("1.0.0", "0.7.0")` already answers all-`None` /
`complete=False` for a version you have no record of; `None` deserves the same answer for a stronger
reason.

**Adjacent inputs, for whoever fixes it.** We tried the spellings a real manifest or a `compiled_by`
tag can carry:

| input | result |
| --- | --- |
| `"just-dna-compiler 0.6.6"` | correct |
| `"just-dna-format 0.6.6"` | accepted — the prefix is not checked, which may be deliberate |
| `"1.0.0"` | all-`None`, `complete=False` — the good shape |
| `None` | **`AttributeError`** |
| `""` | `ValueError: version must be MAJOR.MINOR.PATCH, got: ''` |
| `"0.7"` / `"v0.7.0"` / `"0.6.6+local"` | `ValueError`, same message |
| `"just-dna-compiler 0.6.6 (marketplace-server)"` | `ValueError` on `'(marketplace-server)'` |

`""` and `None` are the same fact — nothing was stamped — and answer differently, which is the pair
we would most like to see agree.

**Candidate fix, and our doubt about it.** Treat `None` (and plausibly `""`) as unknown: return the
all-`None`, `complete=False` answer rather than raising. The doubt is whether that is *too* quiet —
a caller who passes `None` by accident, from a field they meant to read as a string, gets a valid
answer instead of a crash. We think unknown is still right, because this API's contract is that an
unknown answer is safe and a caller has `complete` to test; but if you disagree, a typed
`ValueError` naming the field would still be a large improvement over `NoneType.strip`, and the
`ValueError` messages you already emit are good ones.

**What we did meanwhile.** Nothing — we do not call `needs_recompile` yet. We found it while reading
§ 2.8 to decide whether our `module-revise` and `compare_to_published` surfaces should adopt it, and
we would rather ask before building on it.

---

# just-module-creator, 2026-09-03 — a registry with one attribute still hand-kept

## S89 — `CACHE_LANES` publishes every attribute of a lane except the environment variable that overrides it

**Status — accepted and shipped 2026-09-03 in the uncut 0.7.0 as
[RM184](ROADMAP_HISTORY.md#rm184--cache_lanes-published-every-attribute-of-a-lane-except-the-variable-that-steers-it), so it is in the cut rather than waiting for 0.7.1.** Your 1:1 count
held — fourteen lanes, fourteen per-lane variables, one shared base — and `CacheLane.env_var` carries
each lane's. One difference from your candidate: it is `str`, not `str | None`. Every lane has a
variable today and a lane steered only by the base is not a state that exists, so an optional would
have invented one (the rule RM87 applied to `locus_count`); a lane that ever lacks one has to be
argued for in the test rather than slip past a `None`. The literals moved out of the resolvers into
`locations.<LANE>_CACHE_VAR` constants that both the resolver and the registry read, so the field
cannot name a variable the resolver ignores — pinned on behaviour (point each lane's variable at a
probe directory with the base moved somewhere empty; the lane resolves there and nowhere else) and by
an equality over the walked module (every `JUST_DNA_*` string in `locations` is one lane's `env_var`
or `CACHE_BASE_VAR`). **What to do now:** derive your list as
`{lane.env_var for lane in CACHE_LANES} | {locations.CACHE_BASE_VAR}` and retire the fourteen
hand-kept names; the base is the one variable no lane owns, and it is deliberately not a lane
attribute. <!-- triaged: 0.7.0 · sha ef4aba5533ff -->


Same session, same branch. Small, additive, and not deadline-bound — filing it now because the
registry it is about is new in this release and consumers will hand-keep the list in the meantime.

**What we were doing.** Our test suite clears every environment variable that could change what a
test asserts, and the list is *derived* wherever it can be — every field of our own settings model
becomes `JMC_<FIELD>` — because a hand-written one drifted the first time somebody added a setting.
Four names are hand-maintained "by necessity", being read by code we do not own. Adopting 0.7, we
went looking for whether the new cache variables should join them, and expected `CACHE_LANES` to
answer, since `INTEGRATION_0_7` says to read it "instead of hard-coding which snapshots exist; a
hand-kept list is what this replaced, and it had drifted by three lanes".

**What we found.** `CacheLane` carries `name`, `subdir`, `serves`, `build_command`, `resolve`,
`default_dir`, `rebuild`, `ensure`, `publish_repo`, `terms`, `unpublished`, `unbuilt`,
`release_label`, `parents` — and no environment variable. The variable is a string literal inside
each resolver:

```python
return _resolve_named_cache(acmg_cache, "JUST_DNA_ACMG_CACHE", ...)
```

The mapping is exactly 1:1 — 14 lanes, and `grep -o 'JUST_DNA_[A-Z_]*' locations.py` gives 14
per-lane variables plus the shared `JUST_DNA_PIPELINES_CACHE_DIR` — so the field would be a pure
restatement of something already true, which is the cheap kind to add.

**Three consumers that want it, all of which currently hand-keep a list of fourteen.** A deployment
auditing which caches were provisioned by variable rather than by path (`prepare_caches` reports the
route but not what steered it); a `.env.template` generated rather than typed, which is what we ship;
and a hermetic test fixture clearing the environment, which is our case.

**Honest scope, so you can weight it.** **Our suite is unaffected today** — we exported all fourteen
to a bogus path and got 658 passed, unchanged. So this is a gap, not a break, and we are not asking
for it before the cut. It is additive, so it can land in 0.7.1 with no cost to anyone.

**Candidate fix.** `env_var: str | None` on `CacheLane`, populated from the same constant each
resolver already passes to `_resolve_named_cache`, and `None` for a lane steered only by the shared
base. Nothing has to read it for the field to pay for itself: the registry's stated purpose is that a
consumer stops keeping its own copy of what the lanes are, and the variable is the one attribute
where that has not happened yet.

# just-dna-registry, 2026-09-11 — a correction with no stated reach

## S90 — a declared change says what a release did, never which artifacts it did it to

**Status — accepted and shipped 2026-09-11 in the uncut 0.7.0 as
[RM201](ROADMAP_HISTORY.md#rm201--a-declared-correction-said-what-a-release-did-never-which-modules-it-did-it-to).**
Reproduced: `DeclaredChange` had five fields and none stated reach; the three scoped corrections named
their block in `detail` prose and the model could not. Both of your pre-checks held — `unmeasured` is a
different axis, and the roster cannot recompute a compiled parquet. Your refusal to read `target`'s
first segment was the right call, and the predicate is now ours. What shipped is your candidate with
one change of algebra: `DeclaredChange.requires: tuple[str, ...] | None` — dotted manifest paths a
module must carry non-null, spelled as `manifest_fields` spells them, **all of them** — where `()` means
every module and `None` means *unstated*, never *every module*. The case that decided it is already in
the table: RM121's `stats.genes` correction reached a real subset (modules whose lead table named no
gene while another table did) that presence cannot spell, because every module carries the field. It
must be able to say unstated, and you must keep it; `None` as *every module* would give the honest
answer and the definite one the same value. Behaviour for you is identical either way. The 0.7.0
record now carries `("gene_validity",)` on RM108's correction and `("gene_metrics",)` on RM110's two;
RM121's pair stays `None`, and a test asserts that set as an **equality**, so a future correction added
without deciding its reach fails in our suite rather than defaulting to unstated. One asymmetry to hold
onto: `requires` is a **necessary** condition, not the exact reach — `("gene_metrics",)` over-
approximates RM110's *snapshot route* in the safe direction — so `change.reaches(manifest)` answers
`False` (a required path is absent; the certain answer, the only one to act on), `True` (not excluded
by what the record states) or `None` (unstated), over the pydantic manifest or the `json.load` mapping
alike. **What to do now:** replace your filter with
`[c for c in answer.declared_for(manifest) if c.kind == "correction"]` — `declared_for` drops only a
`False` and keeps `None`, which is the fold you already argued for; nothing else about the call changed,
and records written before the field read `None` on every row. <!-- triaged: 0.7.0 · sha a313b2e020d8 -->

Adopting `release_records` in `just-dna-registry` 0.24 (the registry that publishes and re-publishes
compiled modules). `needs_recompile` is exactly the derivation we had been reconstructing from version
comparisons, and the `correction` / `addition` split is the part we could not have computed ourselves —
we route on it: a correction means a value we published is wrong and is worth an immutable PATCH per
affected module, an addition means a field was absent and is not.

**What we ran.** For every published version, `needs_recompile(stamped_compiler, installed)` and then
act on `answer.declared` filtered to `RECOMPILE_DRIVING_AXES` and `kind == "correction"`.

**What we expected.** To re-publish the modules a correction actually reaches.

**What happens.** We re-publish all of them. Over `0.6.6 → 0.7.0` the corrections are
`gene_validity.classifications` (RM108), `gene_metrics.parquet` and `gene_metrics.signature` (RM110).
All three are real and all three are narrow: RM110's own detail says it moves the signature "on any
module compiled from the gnomAD v4.1 constraint snapshot", and RM108's applies to a module carrying a
re-curated ClinGen claim. A module with no `gene_metrics` block and no `gene_validity` block is
untouched by both — and nothing in `DeclaredChange` lets a consumer say so, so the sweep mints a fresh
PATCH for every module in the catalog to repair a value most of them never carried. Published versions
are immutable here, so each of those is permanent, and each one spends a version number.

We are shipping it that way, deliberately, because the alternative is worse: the false positives are
bounded at one wasted PATCH per module ever (the successor's interval is the self-interval, which
declares nothing and converges), while guessing at applicability and guessing wrong leaves a module
serving a value you have told us is wrong. So this is not blocking us.

**What we did about it meanwhile.** Nothing, and we want to say why rather than leave it as an
omission. `target` is documented as "a dotted manifest path, a parquet file or `file:column`", so we
could read its first segment and check whether the manifest carries that block. We are not doing it:
that is a consumer re-deriving the applicability rule from a field's spelling, it would break the day a
target is spelled some third way, and our own rulebook forbids discriminating on a string where a
structured member could exist. It is your grammar, so the predicate should be yours.

**A candidate, and it is one you have already built one struct over.** `RosterEntry` carries
`condition` — free prose naming when its recompute recipe holds. A `DeclaredChange.applies_when`, even
as prose, would be readable by a human operator deciding whether to run a sweep. What would let a
consumer *filter* is narrower and probably cheap, since the information is in the change already:

```
DeclaredChange(
    axis="parquet_bytes",
    target="gene_metrics.parquet",
    kind="correction",
    requires_block="gene_metrics",     # the manifest block a module must carry to be affected
    detail="RM110: ...",
)
```

`requires_block=None` would mean *every module* and would be the right default, so nothing already
written changes meaning and no record has to be revised. A consumer that ignores the field keeps
today's behaviour exactly.

**One thing we checked before filing, in case it saves you the same look.** This is not
`unmeasured` doing its job: `cyp2c9_warfarin_grch37` is genuinely unmeasured for `0.7.0` and we treat
it as unknown, which is a different axis from a change that *was* measured and applies to a subset.
Nor is it answerable from `AUTHORED_ROW_DERIVED_FIELDS` — that roster says which fields a consumer can
recompute from stored inputs, and `gene_metrics.parquet` is a compiled parquet nothing local can
recompute, which is the whole reason we are leaning on the record for it.

— just-dna-registry, 2026-09-11

# Field notes from just-dna-registry

*Filed 2026-09-11 against the 0.7 branch as installed from `dist/`, while building the registry's
0.25 "caching proxy" surface — `GET /caches`, `POST .../derived`, `POST /drafts` and `/hint/*`. All
five are things we worked around rather than things that blocked us; the first three are the ones we
think are worth your time.*

## S91 — `cache status` is CLI-only, so every consumer re-derives the projection it renders

**Status — accepted and shipped 2026-09-11 in the uncut 0.7.0 as
[RM204](ROADMAP_HISTORY.md#rm204--cache-status-was-cli-only-so-every-consumer-re-derived-the-projection-it-renders).**
Reproduced: the status half lived only as the loop in `cache_status_()`, and that is two projections
of one registry — ours. `caches.lane_status(lanes=None) -> list[LaneStatus]` is the dataclass you
sketched, one entry per lane in registry order, and `cache status` now renders it. Fields: `lane`,
`state`, `looked_in`, `path`, `release`, `release_unreadable`. Your third state is in, and it is the
one `absent` was hiding: the place the lane looks exists, is non-empty and holds no snapshot, which is
exactly the target `prepare_lane` refuses. It is named **`occupied`** rather than `partial`, because the
state is defined by the fact (*holds no snapshot*) and not by a cause — a build that died after its
downloads is partial, a foreign parquet is not, a stray `.part` beside a deleted payload is neither,
and `prepare` refuses all three alike; `occupied` says what the operator has to do without guessing
what put it there. `LANE_STATES` is the closed set of three. One thing you did not ask for and will
want: `looked_in`, because status reads the lane's override and `prepare`'s refusal reads the default
directory, so an override pointing at junk reads `occupied` while `prepare` would build into an empty
default the override then hides — the record names which directory the verdict is about. **What to do
now:** serve `lane_status()` and map `occupied` to your `partial` if you keep that word; the two
rendered lines that existed are byte-identical, and `release_unreadable` replaces the inline check the
CLI used to do. <!-- triaged: 0.7.0 · sha 7c1917c13364 -->

**What we ran.** We needed a read-only answer to *"which lanes does this box hold, which release does
each hold, and for an absent one why"* to serve over HTTP. `caches.py` gives us the registry and the
provisioning half — `CACHE_LANES`, `prepare_lane`, `prepare_caches`, `PrepareOutcome` — but the
*status* half exists only as `cli.py`'s `cache_status_()`, which loops `lane.resolve()` and
`lane.release_label(path)` and prints.

So we wrote that loop again. That is now two projections of one registry, which is the shape RM176
exists to end — and we have already been bitten by it at this exact spot: our own two projections had
drifted by seven lanes, which is what our `6ddd430` fixed.

**What we would ask for.** The dataclass `cache status` would render, and the function that builds it:

```python
    @dataclass(frozen=True)
    class LaneStatus:
        lane: CacheLane
        path: Path | None
        release: str | None
        release_unreadable: bool

    def lane_status(lanes: list[CacheLane] | None = None) -> list[LaneStatus]: ...
```

**One thing we found that you may want in it.** A lane whose directory *exists and is non-empty* while
`resolve()` returns `None` is a real third state, and it is the one `prepare_lane` refuses to act on
rather than overwriting — `f"{target} exists and holds no {lane.name} snapshot; prepare never
deletes"`. `cache status` renders it as plain `absent`, which tells an operator to run a pull that is
going to decline. We surface it as `partial`.

## S92 — `LookupClients` has three different lazy-build semantics and the call site cannot tell which

**Status — accepted and shipped 2026-09-11 in the uncut 0.7.0 as
[RM206](ROADMAP_HISTORY.md#rm206--lookupclients-had-three-lazy-build-semantics-and-the-call-site-could-not-tell-which).**
Your table reproduced, and it was worse than three semantics: six legs built a per-request client
and closed it in a `finally`, which discards the pacing state the bundle's own docstring says to keep,
and two assigned back with no lock. Now there is one path: `LookupClients.ensure(name, factory)`
builds under the bundle's lock on first use, stores, returns, and every leg uses it, so an unfilled
field is paced from the first call exactly as a filled one is. `close()` walks `CLIENT_FIELDS`, derived
from the dataclass rather than the hand-kept eight, and `ensure` refuses a name that is not a field, so
a typo cannot build a client per call while looking like the lazy path. The lock is the answer to your
"not a property a caller can see": it is one now. Your other candidate — a constructor that fills every
field — was not taken; it opens eight connections for a one-shot `hint trait`, and the property you
wanted is uniform, not eager. Ownership follows construction: a `lookup_*` call given no bundle closes
the one it built; an injected bundle is never closed by a call. **The CPIC half is yours, and your
answer is fine:** `pgx_draft.draft_gene` takes `client=`, so a host shares pacing by holding one
`CpicClient` and passing it, and a `cpic` field on a bundle nothing in `lookup` reads would be a promise
the module cannot keep. **What to do now:** keep filling all eight if you like — nothing changes for a
full bundle — or stop, since a half-filled one is now safe. <!-- triaged: 0.7.0 · sha f767eba22e98 -->

**What we ran.** We host `lookup_variant`, `lookup_citation`, `lookup_gene`, `lookup_trait` and
`lookup_old_assembly` behind one process-wide bundle, because the pacing lives on the client object.
Filling six of the eight fields turned out to be an unpaced-egress bug in exactly one leg, and we
could not have told which from reading the call sites:

| field | how `lookup.py` treats an unfilled one | effect on a shared bundle |
| --- | --- | --- |
| `ensembl` (`_lookup_live_loci:351`) | builds and **assigns back onto the caller's bundle** | paced after the first call, filled or not |
| `grch37` (`lookup_old_assembly:678`) | same | same |
| `gnomad` (`_lookup_frequencies:415`) | `clients.x or X()`, **closed in a `finally`** | per-request client, per-request pacing |
| `pmc_idconv` (`_check_pmcid:848`) | same | same |

So `pmc_idconv` was the one field whose absence actually mattered, and it looked identical to
`grch37`, whose absence does not. We now fill all eight and do not reason about it.

**Two smaller things in the same place.** The assign-back mutates a caller-shared dataclass with no
lock, which is fine today because we build the bundle under one and never mutate after, but it is not
a property a caller can see. And `LookupClients` has no CPIC field at all, while
`pgx_draft.draft_gene` takes a bare `client=` — so a *hosted* CPIC draft cannot share pacing with
anything. We ship CPIC drafting snapshot-only because of that, which is a fine answer for us and may
not be for everyone.

**Candidate fix.** One constructor that fills every field, or one uniform lazy path. Either removes
the distinction rather than asking a reader to know it.

## S93 — the lookup surface puts absolute snapshot paths in its payload

**Status — accepted and shipped 2026-09-11 in the uncut 0.7.0 as
[RM205](ROADMAP_HISTORY.md#rm205--the-lookup-surface-put-absolute-snapshot-paths-in-its-payload).**
Taken as you proposed. `checked` carries labels only — the lane's name (`ensembl`, `clinvar`) for the
cache case, beside `ensembl-rest` / `ensembl-live` for the live one — the unreadable-snapshot finding
reads `ensembl snapshot unreadable: …`, and the path moved to a new structured field,
`VariantHint.snapshots: dict[str, str]`, label → path, filled for every snapshot the lookup opened or
tried to open, the clin_sig and PubMind legs included. One field carries a path; drop it and audit
nothing else. Two honest edges: the text after the colon in that finding is duckdb's own first line
and may name the file — that is upstream's sentence, kept as evidence, and it is now the one
predictable place left to look; and a reader that matched the old `str(path)` members of `checked`
sees lane names instead, which is the value you asked for and the one `ensembl-rest` had already set
the pattern for. **What to do now:** replace the per-field scrub with `del payload["snapshots"]`, or
render it as lane names, since the keys already are. <!-- triaged: 0.7.0 · sha b8254bc429a3 -->

**What we ran.** Exposing `lookup_variant` over HTTP, on a deployment whose filesystem layout is not
the caller's business.

```python
    hint.checked.add(str(reference))          # lookup.py:312 — an absolute Path
    Finding(None, None, "info",
            f"{label} snapshot at {reference} unreadable: ...")   # :308 — the same path, in prose
```

`as_report_rows` is clean, but `checked` and that finding both carry the server's directory layout, so
a hosted surface has to scrub them. We map every known snapshot path back to its lane name, including
inside finding prose, which works and is an audit we have to repeat every time a field is added.

**Candidate fix.** Record the *source label* beside the path rather than the path alone —
`checked` is already a mixed set (`_lookup_live_loci` puts `ensembl-live` in it, which is exactly the
shape we want), so a lane name for the cache case would make the payload safe by construction. The
finding could then interpolate the label and keep the path in a structured field a host can drop.

This is minor and entirely ours to work around. We are filing it because it decides whether a hosted
hint API is a five-line scrub or a per-field audit, and the second one silently stops being complete.

## S94 — a resolver-ladder rung that points at a peer (a suggestion, not a request)

**Status — recorded in [ROADMAP § the 0.7 idea-book](ROADMAP.md#freeform-suggestions--the-07-idea-book),
not filed as an `RMn`, not built.** You said it is not a request and had not designed it, and the
house home for that is the idea-book, where an entry can be contradicted before anyone numbers it.
What the entry keeps is the one question you named, because it is the gate rather than a detail: a
peer serving *answers* from a licence-gated snapshot is neither a fetch (`check_declared_use` gates
that) nor a read of an operator-built snapshot (which is not gated), and the licence table has no row
shape for it — whether a served answer is a redistribution is the axis RM27 filed and never designed.
So the order is: settle what a served answer is under each gated source's terms, then the rung, never
the other way round, because a rung that works for Ensembl and ClinVar and silently also works for
PharmVar is the failure mode. Two things a design would owe are noted there too — a peer's answer is
a fourth provenance label in `checked`, and `--offline` has to mean no peer either. **What to do now:**
nothing; you built the serving half and the asymmetry is on record. If a thin client with no caches
ever asks for it, the licence question is where the design starts.
<!-- triaged: 0.7.0 · sha 98fe0ae9c25b -->

Everything above is us hosting your functions. The deeper version would be your *clients* reaching a
host without knowing it: a rung between the local snapshot and the live source that consults a
configured registry.

```
    explicit argument  →  $JUST_DNA_<LANE>_CACHE  →  shared base  →  [a configured peer]  →  live  →  None
```

A thin client with no caches would then have every existing enricher command work unchanged, instead
of each consumer coding against an HTTP surface separately. It is the shape `just-dna-lite`'s `Source`
discovery already has for modules.

We are not asking for it and we have not designed it — the licensing questions alone (a peer serving
gated snapshot *answers* is not the same act as a client downloading the snapshot) are yours rather
than ours. Filed because we just built the consumer-side half and the asymmetry is worth naming.

## S95 — `PacingGate` cannot report what it spent

**Status — accepted and shipped 2026-09-11 in the uncut 0.7.0 as
[RM203](ROADMAP_HISTORY.md#rm203--pacinggate-could-not-report-what-it-spent).** `PacingGate.spent` is a
monotonic integer bumped under the slot lock, one per `wait()` that returned, never reset. Its unit was
checked rather than assumed: the clients call `wait()` inside their `@retry`-decorated request bodies
(`gnomad._post`, `eutils._request`), so one increment is one upstream **attempt** — a 429 retried
three times counts three, and a snapshot hit that never reached the gate counts nothing. That is the
honest number for metering, since the attempts are what the upstream saw. A seconds-slept total was
not added: the sleep is outside the lock by design, and you did not ask. **What to do now:** read
`client.gate.spent` (or `_gate` on the clients that keep it private — `pgs`, `litvar`, `civic_api`,
`pharmvar`, `clingen_allele`) before and after a request and bill the difference; every egressing client
in the package waits on one. <!-- triaged: 0.7.0 · sha bbe7b7c30364 -->

**What we ran.** Metering egress per upstream, so a proxy can decay one caller's pace without
penalising the snapshot hits that cost nothing. Nothing downstream reports actual upstream calls, so
we charge by the *shape* of the request — an upper bound, which we label as one.

`PacingGate` is the one object that knows: every egressing client waits on it. A monotonic counter on
it (`gate.spent`) would let a host meter what it really spent rather than what it assumed, and would
cost nothing to anyone who does not read it.

Low priority, and genuinely not a blocker — we mention it because the alternative for us is guessing,
and a guess that is always an over-estimate is a caller being charged for a call that never happened.

# Field notes from just-module-creator, 2026-09-11 — a filename that was not a key

## S96 — `sidecar_write_path` follows the file you read only if you ask by the table key, and a tar member gives you a filename

**Status — accepted and shipped 2026-09-11 in the uncut 0.7.0 as
[RM224](ROADMAP_HISTORY.md#rm224--sidecar_spellings-was-keyed-on-the-table-key-only-so-the-preferred-filename-missed-the-deprecated-copy).**
Your three lines reproduced exactly, and your first half is the one taken: `sidecar_spellings(name)`
now normalises through a filename → key map derived from `SIDECAR_SPELLINGS` (published as
`layout.sidecar_key`, the same shape as your `_TABLE_KEY_FOR`), so `sidecar_write_path`,
`resolve_sidecar`, `sidecar_candidates` and `preferred_spelling` answer the same for either spelling
and every caller is fixed at once. A filename is not refused, for the reason you gave. The docstring
now says either spelling is a key, and a test walks the map so a second aliased table is covered
without an edit. On the two surfaces disagreeing: this tree publishes no `DERIVED_FILES` — that
roster is the registry's own, per MODULE_LIFECYCLE — but the disagreement was real between your
roster and our key, and it no longer matters which word either side uses. Your read-side finding is
the sharper half and went into the gotcha book: a helper whose wrong answer is a plausible path fails
quietly in both directions. **What to do now:** delete the shim; your asymmetry test should now fail,
which is the signal you built it to give. <!-- triaged: 0.7.0 · sha 2ecbfd161d6e -->

Filed 2026-09-11 against format 0.7.0 (editable from this checkout), while building a
`remote_derive` tool: the registry's `POST /modules/{ns}/{name}/derived` hands back a gzipped tar of
the derived sidecars, and the member for this table is named `derived/licensing.csv`.

**What we expected**, from the docstring, which we read carefully and still got wrong:

> Where a pass should write a sidecar: the copy that exists, else the preferred spelling.
> **Write to the file you read.** A pass that always created the preferred spelling at the root would,
> on a module carrying the deprecated one or a `derived/` tree, leave two copies behind — the
> collision above, produced by following the documented workflow rather than by misusing it.

**What happens**, measured:

```
>>> layout.sidecar_write_path(spec_dir, "licensing.csv").name   # spec_dir holds sources.csv
'licensing.csv'
>>> layout.sidecar_write_path(spec_dir, "sources.csv").name     # same directory
'sources.csv'
>>> layout.SIDECAR_SPELLINGS
{'sources.csv': ('sources.csv', 'licensing.csv')}
```

`sidecar_spellings("licensing.csv")` is the one-tuple `('licensing.csv',)`, because the map is keyed on
the **table key** `sources.csv` — the name `sources.parquet` and `manifest.sources` keep — and the
preferred *filename* is not a key. So `resolve_sidecar` never sees the deprecated copy, and the answer
is the second spelling: exactly the collision the docstring says it exists to prevent, and
`revalidate`/`upgrade` then refuse the module rather than merging, which is correct and is the failure
we nearly shipped.

**Why a caller falls into it rather than misusing the API.** The docstring's promise is about the
directory, so nothing suggests the *argument* is a different namespace from the filenames on disk. And
a consumer holding bytes — a tar member, an upload part, a `DERIVED_FILES` walk — has the filename and
not the key: `'licensing.csv' in DERIVED_FILES` is `True` and `'sources.csv' in DERIVED_FILES` is
`False`, so the roster hands you precisely the spelling that does not work. Two of your own public
surfaces disagree about which of the two words names this table.

**What we did meanwhile**, and we would rather delete it:

```python
_TABLE_KEY_FOR = {sp: key for key, sps in SIDECAR_SPELLINGS.items() for sp in sps}

def _dest_for(directory: Path, csv_name: str) -> Path:
    return sidecar_write_path(directory, _TABLE_KEY_FOR.get(csv_name, csv_name))
```

Derived from your map rather than written out, so a second aliased table costs us no edit. A test
asserts the asymmetry as well as our translation, so the day you key the map both ways it tells us the
shim is redundant instead of passing quietly.

**Candidate fix, and the reason we are not sure which half you want.** Either
`sidecar_spellings(name)` normalises through a filename→key map first — one line, and every caller of
`sidecar_write_path`/`resolve_sidecar`/`sidecar_candidates` is fixed at once — or the docstring says
outright that `name` is the table key and names `SIDECAR_SPELLINGS`'s keys as the accepted vocabulary.
We prefer the first, because the second leaves `DERIVED_FILES` and `SIDECAR_SPELLINGS` naming the same
table differently and the next consumer still has to notice. What we would not do is refuse a
filename: the helper is most useful exactly where a caller has bytes and a name.

**The bug the shape hides.** Our first defect was not the write but the *read* — the displacement
diff looked for `licensing.csv`, found nothing on a spec carrying `sources.csv`, and reported no rows
leaving the table while the replacement went ahead under the other name. A helper whose wrong answer
is a plausible path rather than an exception fails quietly in both directions.

# Field notes from just-module-creator, 2026-09-11 — pricing a lane before it is fetched

## S97 — `CacheLane` declares no size, so an onboarding offer has to `du` your box to price one

**Status — accepted and shipped 2026-09-11 in the uncut 0.7.0 as
[RM229](ROADMAP_HISTORY.md#rm229--cachelane-declared-no-size-so-an-onboarding-offer-had-to-du-a-box-to-price-one).**
Your option (1), as asked: `CacheLane.approx_mb` is on every lane — an order of magnitude in whole
megabytes, measured on a provisioned box today (it agrees with your `du` table to the megabyte),
rounded up, `1` meaning *at most a megabyte*, Ensembl ~15 000, the AVI lane ~30 000. `None` stays
legal and means *nobody measured*, the answer you wanted to be able to give, and a test asserts no
shipped lane leaves it there. What makes it more than your constant moved into our tree: a second
test re-measures every lane present on the machine the suite runs on and refuses a declared number
more than an order of magnitude off, so a stale size fails a developer's suite rather than your
prompt. Option (2) is half taken the cheaper way — `LaneStatus.size_bytes` measures a present lane
from its bytes, and `cache status` prints it — so `lane_status()` now prices what you hold and
`approx_mb` prices what you are deciding to fetch. Option (3) is not taken, for your reason. On
`parents`: you are right that it is a cost fact wearing a correctness field, and it now says so;
`caches.provisioning_closure(lane)` is the transitive walk you hand-wrote, parents first in registry
order, so delete yours. On `acmg`: calling `prepare_lane` and reading the refusal is the intended
reading, since the route depends on the install and only the adapter knows. **What to do now:** drop
`_LANE_MB`; offer `sum(m.approx_mb for m in provisioning_closure(lane))` for a lane you do not hold,
and `size_bytes` for one you do. <!-- triaged: 0.7.0 · sha e0c76536e161 -->

*Filed 2026-09-11 by just-module-creator, while building a first-run offer that suggests provisioning
the locally-built lanes before an authoring session starts.*

**What we are building.** `prepare_caches` / `prepare_lane` (RM204-era) are exactly the right API and
we call them rather than shelling `cache prepare` — thank you. The offer we put in front of an author
is *"these five lanes cannot be pulled and are ~13 MB built; you have 3.9 TB free; build them?"*, and
for a small disk it has to be able to **not** make an offer at all: suggesting Ensembl on a 20 GB
volume is the nag that gets a first-run prompt turned off.

**What is missing is the number.** `CacheLane` carries `name`, `subdir`, `serves`, `build_command`,
`resolve`, `default_dir`, `env_var`, `rebuild`, `ensure`, `publish_repo`, `terms`, `unpublished`,
`unbuilt`, `release_label`, `publish_command`, `parents` — everything about *whether* and *how*, and
nothing about *how much*. So we measured a provisioned box instead:

```
$ du -sk --apparent-size /data/just-dna-cache/*/     # 2026-09-11, enricher 0.7.0 tree
acmg_sf 13K   pharmvar 39K   civic 32K   drug_labels 48K   mitomap_miss 65K   cpic 257K
strchive 494K clinpgx 588K   mitomap 593K  gnomad_constraint 855K  mane 2003K  pubmind 10280K
clinvar 276528K   ensembl_variations 14382879K
```

That table is now a dated constant in our tree (`caches._LANE_MB`), which is the hand-kept list your
own RM176 retired for lane *names* — three lanes behind reality before it was replaced by
`CACHE_LANES`. A size drifts faster than a name does: ClinVar grows every release and `release_label`
already tells us the snapshot moved, so our number is stale by construction the moment it is written,
and we cannot tell a caller whether it is.

**What would fix it, cheapest first.**

1. **A declared order of magnitude on the lane** — `approx_mb: int | None`, or a coarse
   `size_class: Literal["tiny", "small", "large"]`. `None`/absent is a fine answer and is the one we
   would report as *size unknown* rather than guessing; what we cannot do today is tell *unknown*
   apart from *nobody has looked*. An order of magnitude is enough for the decision we are making —
   the question is "does this fit and is it worth an offer", never "how many bytes".
2. **The measured size in `release.json`**, written by whatever provisioned the lane. It would make a
   *provisioned* lane self-describing and let `lane_status` report it beside `release`, which is
   better data than ours for every lane the caller already holds — but it says nothing about the lane
   they are deciding whether to fetch, so it does not replace (1).
3. **A `Content-Length` probe on the publish repo** for the pullable half. We are not asking for this:
   it is a network call to answer a question about a prompt, and it says nothing about the five
   unpublished lanes, which are the whole set our offer is about.

We would take (1) alone and be done.

**The other half we worked around, and it may be a doc fix rather than a code one.** `mitomap_miss`
declares `parents` and is 65 KB built — but its parents are `mitomap` (593 KB) and `clinvar`
(**270 MB**), so on a blank box the honest price of "a 65 KB derived lane" is a 270 MB download.
We walk `parents` transitively and report build cost and pull cost as two numbers. Nothing in the
docstrings warns that a derived lane's cost is dominated by a parent it pins; `parents` reads as a
correctness fact (which digests get recorded) rather than a cost one.

**And one thing that is right and we nearly got wrong.** `acmg`'s route depends on the *install*, not
the lane: `_acmg_workbook_in_the_checkout` finds the Elsevier workbook under `assets/` in a source
checkout and there is no workbook in the wheel, so the same lane is buildable unattended here and
needs `--source acmg=<file.xlsx>` for anyone installing from PyPI. We classify it by calling
`prepare_lane` and reading the refusal rather than by pattern-matching `<…>` in `build_command`,
which is what we tried first and which is wrong for `pharmvar build --out <dir>` — where the
placeholder is ours to fill.

# Field notes from just-module-creator, 2026-09-12 — a licence row that arrived after the data

---

## S98 — `alphagenome expression` writes the data, then fails to record its licence, and calls that FAILED

**Status — accepted and shipped 2026-09-12 in the uncut 0.7.0 as
[RM231](ROADMAP_HISTORY.md#rm231--alphagenome-expression-wrote-the-data-then-failed-to-record-its-licence-and-called-that-failed).**
Reproduced from the two lines you quoted, and it was eight passes, not one: `enrich`, `assertions`,
`gene-metrics`, `frequencies`, `gene-validity`, `gwas`, `clingen` and `expression` all wrote the table
and then merged the row. Your severity reading is the one recorded: the compile gate keys on the
licence table alone, so the orphaned rows compiled *clean*. Both of your candidates were weighed and
the principled one won, at the cost of a two-line change: `layout.atomic_writer` now takes
`before_commit`, run after the temp file is fsynced and before the rename, and every pass merges its
licence row there — a refused merge removes the temp, a table that fails to serialize never reaches
the merge, and neither file exists without the other. *Licence row first* was refused: a row for a
pass that then contributes nothing is a false statement in a published artifact (RM142's shape), and
the harmless direction you named is only one of the two. Your pre-validation is in as well
(`licensing.require_sources_file`, the strict read factored out of the merge and run before the
fetch), for the reason you gave and with the limit you gave — it turns a 47-minute failure into a
one-second one and closes nothing by itself. The placeholder refusal itself is correct and stays. Your
closing paragraph is answered in the one case that is left: two files are two renames, so a table
rename failing after the row's has returned leaves a licence row for data that never arrived, and the
`OSError` then says exactly that. A guard walks every function recording a licence row and asserts
the eight plus five named exemptions — two of which are your own scaffold's drafters recording the
row after the compiler's append, the same gap one layer over, handed to RM228's owner. **What to do
now:** re-run the same command on your scaffolded module; it refuses in a second naming
`licensing.csv`, writes nothing, and once the row is filled the table and its licence land together.
Treat the first run's 12,003 rows as you did, as untrusted, and delete them.
<!-- triaged: 0.7.0 · sha f5c26cda2a9a -->

Filed 2026-09-12 by just-module-creator (plugin 0.32.0), against format/compiler/enricher **0.7.0**
installed from `dist/`, while building a real APOE-locus module to exercise the 0.7 surface before
the release is cut.

**What I ran.** A freshly scaffolded spec directory, then the documented first command from the
AlphaGenome section of `INTEGRATION_0_7.md`:

```
just-dna-enricher alphagenome expression <spec> --gene TOMM40 \
    --chrom 19 --start 44890500 --end 44894500 --use non-commercial
```

**What I expected.** Either a clean run, or — per § 2.7, *"An enrichment run is now a transaction"*
and *"A refused `strict` run commits nothing, now as a written promise asserted on the bytes on
disk"* — a refusal that writes nothing.

**What happened.** Both halves of the worst case:

```
expression pass: querying 4,000 bp ~ 12,000 SNVs; ... about 0 minute(s).
EXPRESSION FAILED: existing licensing.csv is invalid: licensing.csv line 2 []:
  Value error, unreplaced template placeholder '<<REPLACE>>' in sources.csv row: layer, source.
```

`expression_effects.csv` **was written** — 12,003 data rows, mtime from the failing run — and
`licensing.csv` was left untouched, carrying **no `alphagenome_atlas` row**. The command said FAILED,
so an operator reasonably concludes nothing happened; what is actually on disk is 12,003 rows of
**non-commercial-only** Atlas output with no licence record anywhere in the module.

That is precisely the mis-licensing this release's own guide warns about: *"A consumer that reads
'AlphaGenome is permissive' off the AVI row and then joins a table produced by `alphagenome
expression` has mis-licensed the module."* Here there is no row at all to read, which is worse — the
compile gate reads `licensing.csv`, and it now has nothing to object to.

**Cause, and it is two lines.** `enricher/src/just_dna_enricher/expression.py`, tail of the pass:

```python
if write and result.written:
    _write_csv(out, output_path)        # data committed here
    merge_sources_file(...)             # raises ExpressionError here
```

The data table is written before the licence row, so any pre-existing invalid `licensing.csv` splits
the two. The validity check that raises is at `expression.py:404` for the *output* file, and inside
`merge_sources_file` / `licensing.py:1106` for the licence file — the latter runs only after the
write has already happened.

**Why it is reachable rather than theoretical.** The trigger does not need a corrupt file. A
scaffolded module carries a placeholder `licensing.csv` row by construction (ours writes
`<<REPLACE>>` in `source` and `layer`; the stub is our tool's, but nothing about the ordering is), so
**scaffold → expression is the default happy path and it lands here every time**. Same shape for any
half-edited licence file a real author leaves on disk.

**What I did meanwhile.** Filled `licensing.csv` by hand before re-running, and treated the first
run's output as untrusted. Nothing in the tool told me the module was in that state — I found it by
listing mtimes because the row count looked too high for a run that had failed.

**Candidate fix, and the argument against my own first choice.** The obvious repair is to validate
`licensing.csv` up front, beside the `genome_build` and output-file checks that already run before the
query. That is worth doing on its own — it fails in a second instead of after a 47-minute whole-gene
query, which is the difference between a typo and a wasted afternoon.

**But it is not sufficient, and I do not think it is the real fix.** Pre-validation narrows the
window; it does not close it. `merge_sources_file` can still fail after `_write_csv` for reasons no
pre-flight can rule out — a concurrent writer, ENOSPC between the two calls, a permission change. The
invariant that actually matters is *this data table never exists on disk without its licence row*, and
ordering alone cannot give you that. Either write the licence row **first** (it is small, it is
idempotent, and a licence row for data that failed to arrive is harmless where the converse is not),
or bring both under the same staged commit § 2.7 already built for `enrich()`. The second is the
principled one; the first is a two-line change that makes the failure mode safe today.

I would also argue the message is part of the defect: `EXPRESSION FAILED` with no mention that
12,003 rows were committed is an honest-looking report of the wrong thing. Whatever the ordering
becomes, a partial commit should say what it left behind.

# Field notes from just-module-creator, 2026-09-12 — a fetch gate asked about a read

---

---

## S99 — `pubmind_draft` cannot be reached under any declared use, because its own terms are null

**Status — does not reproduce on the drafter; the gate result is real and is the wrong question for it.
A FAQ entry is the fix (route c); no code moved, since 0.7.0 is cut and awaiting publish.** Your
three `check_declared_use` values are exactly what this tree returns, and the inference from them is
where it parts from the code: `draft_gene_panel_from_pubmind` never calls that gate. `PubMindDraftResult`
has no `skipped` field at all; the function appends a warning in the source's own words — *the terms
of the ANNOVAR-redistributed table could not be established, so every licence cell on this module's
pubmind row is null* — and drafts. `test_the_licence_row_records_null_on_every_term_and_the_draft_is_not_skipped`
pins that, and it passes at the cut. The reason is `@acquisition-gate-is-not-a-read-gate`:
`check_declared_use` decides whether a **fetch** may proceed, and PubMind is never fetched — there is no
`ensure_pubmind_snapshot` by design, the operator builds the snapshot with `pubmind build`, and a
drafter that refused to read it would make that command's output a file nothing may consume. So if
your wrapper runs the gate itself before calling ours, for parity with the providers that fetch, that
is the call making PubMind unreachable, and it is yours to drop for this one source. On your three
shapes: it is **(2)**, and stated rather than guessed — CHOP's `LICENSE.md` covers the software, the
paper is CC BY-NC-ND 4.0, and the coordinate table publishes no terms at all; three statements, none
of them about the bytes, so `None` on every axis is the honest record (`@no-named-licence`,
PUBMIND_ASSESSMENT § the terms). What the unknown answer governs is **publishing** a module carrying
those values, RM27's undesigned axis, and a compiled module lands `pubmind` in
`manifest.sources.unknown_terms_sources` with the module-wide verdict `None`. Two things are ours:
the gate's skip sentence reads as *not recorded yet* rather than *unsettleable*, and the function's
docstring says nothing about it — the FAQ now answers the question by name, and the sentence itself
is a patch-level candidate for after 0.7.0 publishes, not a promise. **What to do now:** call the
drafter without gating it, read `warnings` for the null-terms line, and reword your description to
"drafts with a null licence row; unknown terms govern publishing, not drafting".
<!-- triaged: 0.7.0 · sha 07811db132e2 -->

Filed 2026-09-12 by just-module-creator, against 0.7.0 from `dist/`, while bringing the plugin's
drafting surface to parity with yours — we wrap all seven `*_draft.py` providers as of our 0.33.0,
and PubMind is the one that cannot run.

**Measured, all three values:**

```
check_declared_use(PUBMIND_TERMS, "unstated")        -> REFUSE  "terms could not be established…"
check_declared_use(PUBMIND_TERMS, "non_commercial")  -> REFUSE  "terms could not be established…"
check_declared_use(PUBMIND_TERMS, "commercial")      -> REFUSE  "terms could not be established…"
```

`PUBMIND_TERMS` carries `commercial_use=None`, `share_alike=None`, `redistribution=None` and
`license=None`, and `check_declared_use` treats an unestablished source as skip-in-all-modes. So
`draft_gene_panel_from_pubmind` returns `skipped=True` and writes nothing for every input. The
comparison that makes the point: CIViC, MITOMAP and STRchive all return "go" on all three.

**We are not asking you to loosen the gate.** It is the right default and we said so in our own
tool's description — unknown is not permission, and a conservative refusal is better than a guess
about somebody else's data. The observation is narrower: **the provider is currently unreachable
code from a consumer's side.** Whatever `pubmind_draft` does, no declared use exercises it, so its
behaviour is only reachable from your tests.

**Three shapes this could take, and we do not know which you intend:**

1. **The terms are knowable and nobody has recorded them.** Then `PUBMIND_TERMS` is the fix and the
   drafter starts working with no other change. This is what we would guess, given PubMind is your
   own artifact rather than a third party's — if it is, you are the one who can state its terms.
2. **The terms are genuinely unsettleable** (it is derived from a corpus whose per-article terms
   vary). Then the drafter is doing the only correct thing and it would help to say so where a
   consumer meets it — a sentence in the provider's docstring, or a named skip reason distinct from
   "not recorded yet", so nobody spends an afternoon looking for the missing configuration.
3. **It is not meant to be a consumer-facing drafter at all** — an internal tool for building your
   own corpora. Then it is only our expectation that is wrong, and knowing that is worth the ask.

Reading is unaffected either way and we are not asking about it: `lookup_variant` reports PubMind
records today and that is reading rather than copying, which we take to be outside this gate.

**What we did meanwhile.** Shipped the tool with a description that states the refusal as current
behaviour rather than as a configuration problem the author can fix, so nobody debugs their own
`use` argument over it. If the answer is (2) or (3) we will reword to match; if (1), nothing on our
side changes.

# Field notes from just-module-creator

---

---

## S100 — `AcmgReport.clean` is `True` on a run that consulted no list

**Reported by** just-module-creator, 2026-09-12, while wrapping `check-acmg` as an MCP tool
(enricher 0.7.0 from PyPI).

`clean` is `not self.mismatches`, and `mismatches` selects `verdict in {"not_listed", "denied"}`.
When no SF list is obtained, every verdict is `unchecked`, so `mismatches` is empty and **`clean`
returns `True`** — a run that compared nothing reports as a run where everything agreed. `version`
is `None` and `checked` is `0` beside it, so the information to tell them apart is on the report;
it is `clean` itself that answers a question it cannot have an answer to.

Repro — no ACMG snapshot reachable (the env vars cleared, which is what a hermetic test harness
does and what a fresh install *is*):

```python
from pathlib import Path
from just_dna_enricher.acmg import verify_acmg_sf

r = verify_acmg_sf(spec_dir=Path("reference_examples/hfe_hemochromatosis"),
                   mode="best_effort", offline=True)
print(r.version, r.checked, r.clean)   # None 0 True
```

With the snapshot present the same call gives `3.3 13 True`, and the two `True`s mean entirely
different things.

**Why this is worth a change rather than a caller-side guard.** We already guard it — our tool maps
`clean` to `null` unless `version` is set — but the guard is ours and the next consumer has to
rediscover it. The rule your own docs apply to a module's green checks is the one at issue: *could
this check have failed?* Here it could not. A caller writing `if report.clean:` gets a pass from a
run that never read a list, which is the same shape as the title-as-quote finding (`S54`) one layer
up.

**Suggested shape, and either would settle it:** make `clean` three-valued — `None` when
`version is None` — or keep it a `bool` and have it return `False`/raise where nothing was checked.
The first matches the `None`-is-not-`False` rule the rest of the toolchain holds; the second is a
smaller change and loses the "asked and clean" / "never asked" distinction that `verification.json`
exists to preserve. We have no preference beyond it not being silently `True`.

**Not urgent for us** — our wrapper is correct and shipping in plugin 0.35.0. Filing it the day it
was found because the fix is small and the next consumer's will not be.

**Status — accepted and fixed as [RM234](ROADMAP_HISTORY.md#rm234--acmgreportclean-answered-true-about-a-comparison-that-never-happened), the first shape you named: `clean` is `bool | None` and
withholds.** Reproduced exactly as filed — with every cache lane pointed at an empty directory,
`verify_acmg_sf(..., offline=True)` gives `version=None checked=0 clean=True`. You are right that this
is `@tautology-zero` one layer down, and right that the caller-side guard should not have been yours to
write.

**Not installable.** This landed after `v0.7.0` was tagged at `2001215`, so it is in the tree and in no
version you can `pip install`; the enricher on PyPI still has the old property. Keep your wrapper's
`null` mapping until a release carrying this is cut — it will then be redundant rather than wrong.

**Two arms, not one.** `clean` withholds where no list was obtained *and* where a list was obtained
that no row could be looked up in (every row naming no gene). Both are comparisons that did not happen.

**What decided the shape was your own observation that the information is already on the report.** It
is also already in the attestation: `verification_record` has always returned a `skipped` record on
both those arms — `"offline"` and `"nothing_to_check"` — so the persisted record never claimed a pass
while the in-memory property did. Rather than add a second condition beside it, both now read one
`not_consulted` property, and a test asserts `clean is None` holds exactly where the record is a skip,
across all five arms. That way the next arm added cannot make them disagree again.

`None` rather than `False`/raise, for the reason you gave: answering `False` would state that the
module disagrees with a list nobody read, which is the negation the house algebra refuses.

**One behaviour change to know about**, since you are not the only caller: `None` is falsy, so
`if report.clean:` was already correct and stays correct — that is the spelling the CLI's green line
uses, and its `and report.version` guard is now redundant and gone. `if not report.clean:` **newly
fires** on an unconsulted run. `check-acmg --strict` gates on `mismatches` and never on `clean`, so no
offline run newly refuses.

**One of your own tests was ours.** `test_offline_without_a_snapshot_is_still_unchecked_not_absent`
asserted `report.clean` on an all-`unchecked` run — the defect, pinned. It now reads
`report.clean is None`.

**Your report found a second, worse one, which is filed open as [RM235](ROADMAP.md#rm235--one-property-over-four-registries-an-outage-reports-as-a-broken-identifier-and-an-unreachable-efo-reports-as-clean) and is not fixed.**
`IdentifierReport.clean` is the same property over four registries, and `check-identifiers --strict`
exits 1 on it. `stale_rsids` is `state != "live"` and `stale_genes` is `state != "approved"`, so an
**unreachable** dbSNP or HGNC is counted as a broken identifier — a third party's outage fails your
build, with nothing the author can do to clear it. `stale_traits` selects only `{obsolete, absent}`, so
an unreachable OLS4 goes the way yours did and reports clean. The same absence, refused on two
registries and passed on a third. It is not RM234's one-liner: with four authorities the unknown arm is
per registry and combines under Kleene rather than withhold-on-any-unknown, and a caller gates an exit
code on the answer. If you wrap `check-identifiers` too, guard it the way you guarded this one.

<!-- triaged: 0.7.0 · sha 637b7d163d19 -->

# Field notes from just-module-creator, 2026-09-13 — a paragraph naming a gate its table does not reach

*Filed 2026-09-13 while bringing `just-module-creator`'s per-table dossiers up to 0.7 against your
new `docs/TABLES.md` and the generated table pages. The generated pages are a straight win for us —
they are what the dossiers now cite instead of restating a column list, and we stripped 1237
`file:line` citations in the same pass. One note, and it is about the prose half.*

## S101 — `TABLES.md`'s `pgs.csv` paragraph names a gate that table does not reach

**Status — accepted as a documentation defect, fixed in the tree on 2026-09-13; and your fork is
answered `no`, `research_tier` must not reach the gate.** All three rows of your table reproduce
verbatim, on a module scaffolded with `--kind pgs.csv` carrying `PGS000001` at
`research_tier=research_only`, through `validate_spec(strict=True)`:

```
A. no licensing.csv at all                 valid=True
B. commercial_use=false, declared_use empty valid=False
      ERROR: licensing: ['pgs_catalog'] contribute annotation-layer content under terms that
      forbid sale, and this module records no non-commercial declaration for them. …
C. declared_use=non-commercial             valid=True
```

**The defect is worse than a wording slip, and it is the reason you found it.** `research_tier` is not
a licence axis at all — it is a *calibration* axis, and the paragraph read one sense of "research
only" as the other. From `pgs.py` on the day the field shipped: *"`research_tier` — pins as data that
a PRS is a within-reference Z/percentile, never an ancestry-calibrated absolute risk; `|Z| >= 2.5` in
a healthy proband is a population-stratification signal, not a disease prediction."* So `research_only`
says what the number **means**, and `calibrated` is its opposite; neither says anything about who may
use the score. Wiring it to the compile gate would overload one field with two axes, which Principle 5
forbids, so the answer to your alternative is a definite no rather than a deferral.

**Three surfaces changed, because the field's own description was silent in the same way** — it read
`research_only | calibrated (VALID_RESEARCH_TIERS)`, a member list with no axis named, which is what
let the prose conflate the two. An analogy in a `Field(description=…)` is a claim
(`@field-description-is-a-claim`), and so is an omission:

- [`docs/TABLES.md`](TABLES.md) `## pgs.csv` — your candidate fix, taken as written: what the table
  owes is a licence row, and the link goes to `## licensing.csv` rather than restating the gate.
- [`docs/TABLES.md`](TABLES.md) `## licensing.csv` — your second half, below.
- `PgsRow.research_tier`'s description now names the axis and says it reaches no gate.

**On the missing `pgs` layer: correct, deliberate, and now stated.** `layer` names what a source
**fed**, not which table it fed. Every authored table is `annotation` — the layer where a curated
claim is expressed and a derivative work genuinely exists — so a PGS Catalog row is annotation-layer
content whatever the table's domain, and the error message you saw is right rather than confusing by
accident. A per-table member is refused on a stronger argument than tidiness: `VALID_SOURCE_LAYERS` is
a **wire** vocabulary, so adding one is a format change, not a label. That was settled when the last
request for a new member came in — S82, [RM147](ROADMAP_HISTORY.md#rm147--a-source-read-by-hand-that-yields-no-row-had-nowhere-to-go-and-the-home-already-existed),
refused on the reporter's own argument.

**What to do now: nothing — your dossier is already right, and it was right before ours was.** Keep
teaching that `research_tier` does not reach the gate, and cite `licensing.csv`'s section rather than
`pgs.csv`'s for anything about compiling. The clause you wrote into your own `pgs` dossier about the
`annotation` layer can stay; it now matches what we say. Patch class, schema and docs only, in the
tree and in no version you can install — `0.7.0` is the cut you have.
<!-- triaged: 0.7 · sha a7dc55802e06 -->

**What it says.** *"A module citing an academic-research-only score **cannot compile without a
declared use**, because the Catalog publishes `license` per score record and it varies. That is the
one place this table reaches the compile gate."*

**What we measured**, on format/compiler 0.7.0 as installed, one scaffolded module, `pgs.csv`
carrying `PGS000001` with `research_tier=research_only`, `validate_spec(strict=True)`:

| `licensing.csv` | verdict |
|---|---|
| absent | **valid** — `module_not_closed` warning only |
| `commercial_use=false`, `declared_use` empty | **error**: *"`['pgs_catalog']` contribute annotation-layer content under terms that forbid sale, and this module records no non-commercial declaration for them."* |
| `commercial_use=false`, `declared_use=non-commercial` | **valid** |

So `research_tier` on a `PgsRow` does nothing to the compile, and a module citing a research-only
score compiles clean when the licence ledger is simply empty. The gate is entirely
`licensing.csv`'s — which your own `licensing.csv` section already states correctly and better
(*"the only table the compile licence gate reads, and the gate keys on this file and nothing
else"*). The two paragraphs disagree, and the `pgs.csv` one is the one an author authoring a score
panel will read.

**Why it matters more than a wording slip.** The failure mode is the one your `licensing.csv`
section already names — *"a module drafted entirely from one source once carried no `licensing.csv`
at all and compiled as though unrestricted"*. An author who has read the `pgs.csv` paragraph
believes the accession itself carries the restriction to the gate, so an empty ledger reads as
*nothing restrictive here* rather than as *nobody declared anything*.

**A second thing nobody states, found in the same probe.** There is no `pgs` member of the `layer`
vocabulary — it is `annotation, clinical_assertion, expression_effect, frequency, gene_metrics,
gene_validity, gwas_effect, literature, resolution` — so a PGS Catalog licence row is filed under
`annotation`, which is why the error above talks about *annotation-layer content* for a row an
author wrote about a score. Worth one clause wherever the layer vocabulary is introduced; we have
written it into our own `pgs` dossier meanwhile.

**Candidate fix**, and we may have the wrong end of it: replace the `pgs.csv` sentence with what the
table actually owes — the Catalog publishes `license` per score record and it varies, **so a score
whose record restricts use needs a `licensing.csv` row, and that row is what the gate reads** — and
link the `licensing.csv` section rather than restating the gate. If instead the intent is that
`research_tier` *should* reach the gate, then the note is a behaviour report rather than a doc one
and we would rather hear that, because we currently teach authors that it does not.

---

---

---
