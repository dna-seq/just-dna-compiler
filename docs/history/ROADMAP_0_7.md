# Roadmap — the 0.7 deferral round (closed)

**Closed on 2026-08-31, when 0.7 was built.** This was `docs/ROADMAP_0_7.md`: items legal in a minor
and not taken into 0.6, each with the reason it waited. Split out of [ROADMAP.md](../ROADMAP.md) on
2026-08-13 so the active roadmap described the line being built and a deferral was filed against the
release that would decide it. It is kept here for the reasoning, which is the half worth not
re-deriving — several of these entries are the record of what a probe observed, and two of them say
where an entry was later overturned.

**Where its contents went.** Everything still waiting moved to
[ROADMAP_0_8.md](../ROADMAP_0_8.md) — RM122, RM23, RM16, RM28, RM56, RM65, RM66, RM67, RM68, RM84 —
unchanged but for the file they sit in. The two that **built in 0.7**, RM126 and RM71, have their
shipped entries in [ROADMAP_HISTORY.md](../ROADMAP_HISTORY.md). What stays below is the round's closed
record: RM55, RM72, RM82, RM87 and RM124, each shipped, plus RM83 (closed, not shipped) and RM86
(closed). [RM_TOC.md](../RM_TOC.md) indexes every one of them and is where to look an item up.

**Nothing here is edited as routine work**, the same rule as the rest of this folder. A fact that is
still true belongs in a maintained document; if you find yourself wanting to correct an entry below,
the entry is evidence of what was believed then, and the correction goes where the rule lives.

**What the round recorded about itself, kept verbatim.** RM69 left for
[ROADMAP_1_0.md](../ROADMAP_1_0.md) on 2026-08-27 because its only stated unblocker was RM15, a major:
an item whose deciding release is 1.0 is waiting on a version, not on a design question, and this file
said nothing in it was. Five entries — RM55's fix, RM72, RM82, RM84 and RM87 — were taken back into 0.6
on 2026-08-16 through [PROPOSAL_0_6_PT2.md](../proposals/PROPOSAL_0_6_PT2.md), **which is authoritative
for all five**; their entries below are the record of what was observed. Nothing moved on a legality
argument — everything here was already legal in a minor — so what moved them was severity: a shipped
thing that is silent, wrong or lying outranks a capability nobody has asked for.

---

# The VCF 4.4 items deferred out of 0.6

Numbered and triaged on 2026-08-13 from [VCF_4_4_AUDIT.md](../probes/VCF_4_4_AUDIT.md); the rest of that cluster
(RM53, RM54, RM56–RM64, and RM65's comment fix) went into 0.6 — see
[PROPOSAL_0_6.md](../proposals/PROPOSAL_0_6.md). The audit remains the evidence document: spec quotations,
`file:line` references and probe transcripts live there and are not duplicated.

## RM55 — copy number and repeat count are not whole numbers (the usable fix)

**Severity** high · **Status** ✅ **shipped in 0.6** — built to
[PROPOSAL_0_6_PT2.md](../proposals/PROPOSAL_0_6_PT2.md) § RM55, which is authoritative and against which this entry
is stale in its suggested fix; only the **removal** of `modifier_cn` is still 1.0
([ROADMAP_1_0.md](../ROADMAP_1_0.md)). Indexed in [RM_TOC.md](../RM_TOC.md); the built shape is described in
[SCHEMAS.md](../SCHEMAS.md) · **Owner** format (schema) + compiler

**One deviation from the proposal, taken while building and recorded here.** The proposal says a group
carrying a fractional value is read under the continuous rules *"whatever its kind's default says"*.
As built, the inference fires only where the kind would default to `quantised` — that is the only
reading a fraction contradicts. `activity_score` defaults to *neither* precisely because the score is
summed onto a grid whose step the schema does not know, and it is fractional by nature: reading it as
continuous produced three "coverage gap" warnings on `reference_examples/cyp2d6_structural`, whose real
bins sit at 0.25/0.5/1.25/2.25, for intervals no activity score can land in. The proposal's own
sentence two paragraphs earlier — that `activity_score` *"keeps its third behaviour (no gap warning, a
shared endpoint is an error)"* — is the half that was kept.

> **Stale below.** The proposal's probe found the bin bounds are *already* `float | None`
> (`binning.py:231`, `:238`), `_INTEGER_KINDS` has exactly one code reader (`binning.py:688`), and the
> unstated half of the defect is that the shared-endpoint rule **refuses the continuous tiling that
> would fix it** (`binning.py:666-677`). So "a parallel float column beside the integer one" names a
> column that mostly does not exist. What was decided instead: an optional `measure_tiling` column
> (`{quantised, continuous}`) for the tiling half, read as an **effective** tiling — declared, else
> inferred from a fractional value (one-directional and announced, since fractional-ness is
> incompatible with quantised semantics while integer-ness implies nothing), else the kind's current
> default — **plus** the
> parallel float column applied to `modifier_cn` — the one genuine `int` — as `modifier_copy_number`,
> read through an effective-value alias that falls back to `float(modifier_cn)`, with `_KEY_FIELDS`
> keying on the effective value so a key never holds two spellings. `modifier_cn` is deprecated in 0.6
> and **removed** at 1.0, so the three-release route collapses to two.

VCF 4.4 §7.2: *"Redefined INFO and FORMAT CN to support non-integer copy numbers"*, with fractional
worked examples throughout, and §3 standardises the repeat count `RUC` as a **Float**. Both kinds sit in
`_INTEGER_KINDS` here, so a copy number of 2.4 matches **no bin at all**, silently, `--strict` included —
and `CopyNumberRow.modifier_cn` is typed `int`, so even a modifier dosage cannot be written down.

**Suggested fix, and the reason it is this one.** A **parallel float column beside the integer one**,
with the integer column deprecated and removed at 1.0. It is strictly additive and therefore
charter-clean, where the direct correction is a **retype** plus a change to what published bin tilings
mean — reserved for a major. Three-release route, decided 2026-08-13: **0.6 makes the defect loud, 0.7
makes it fixable, 1.0 removes the wrong column.** An author is never more than one minor away from being
able to write a fractional dosage, and no published table is retyped under anyone.

**Still open when this is designed**, and the parallel column does not foreclose either: whether
quantised-versus-continuous is a **per-table declaration** or a **sixth measure kind**. The two kind-sets
answer *"can a hole be arbitrarily small?"* and *"can two bins touch?"* separately, and a rounded catalog
count and a continuous segment mean genuinely differ on both — so this is not a formality.

**Do not** simply move the kinds into the continuous set: `[2,2]` beside `[3,3]` is a legal integer
tiling today, and continuous semantics change both the shared-endpoint rule and the gap warning for
tables already published.

# The 0.6 dogfooding items deferred out of the fix round

The findings from [DOGFOOD_0_6_FINDINGS.md](../probes/DOGFOOD_0_6_FINDINGS.md) whose obvious repair is itself a
design decision — the round filed five, and two have since left: RM69 for
[ROADMAP_1_0.md](../ROADMAP_1_0.md) (see the header), and **RM70 shipped in 0.7**, its entry now in
[ROADMAP_HISTORY.md](../ROADMAP_HISTORY.md). The three below are what remains. No fixed count is stated
here on purpose: one goes wrong silently the next time an item leaves, and this section has already
lost two. The ledger classes each **surface** rather than **fix**, which is this repo's standing
split: a false claim, a misdiagnosis, an unaggregated wall or an unreached guard gets fixed in the round
that finds it; anything whose repair has to be *chosen* gets filed with the candidates and the reason
each one fails. The refutations are the point of these entries — an item that only names a gap is one
somebody re-derives from scratch a release later.

Everything below is legal in a minor. Where a repair would be additive it says so; where the only
candidate repairs are illegal it says which principle bars them. Legality sizes the release; severity
only orders the queue.

## RM72 — six verification members still emitted by nothing, and the "Writes nothing" contract

**Severity** medium · **Status** **SHIPPED in 0.6 PT2 (lane C), 2026-08-17.** The four members are
wired unconditionally (`check-identifiers` three, `check-acmg` one), the reword landed at the three
sites that carry *this* promise, every member of `VALID_VERIFICATION_CHECKS` now says on its own line
whether it is wired or reserved, and `merge_records` no longer lets a `skipped` record displace a
`ran` one. The merge rule gained a condition the proposal did not anticipate and the implementation
found: the protection holds **while the authored bytes stand still**, because an answer over bytes the
author has since edited is not an answer this document may keep asserting — without it the fix
re-opened a defect an earlier `literature` round had closed. The `create-module` skill needed no edit,
as predicted: its rows for both commands carry no "Writes nothing" annotation. See
[PROPOSAL_0_6_PT2.md](../proposals/PROPOSAL_0_6_PT2.md) § RM72; the two reserved members did not move. *Previously:*
deferred — four members blocked on a printed contract, two deliberately
reserved, one general question open · **Owner** enricher · **Found by** dogfooding on 2026-08-13,
`reference_examples/hboc_palb2/`

**The quoted docstrings below are the pre-RM72 text, kept because they are what the item was about.**
The citations in this entry had already drifted to lines that no longer held them once, so they now
name the command or the symbol rather than a line number.

**Scope.** This is the surfaced remainder of the D4-1 finding. That finding counted **twelve** of
seventeen `VALID_VERIFICATION_CHECKS` members as emitted by nothing; six of them were wired in the same
round that filed this (`citation_existence`, `citation_identifier`, `provenance_quote` from `literature`;
`allele_function` and `vrs_allele_id` from `pgx` and `vrs mint`; `rsid_coordinate_agreement` inside
`enrich`). The honest remainder is narrower than the headline, and the narrowing is the point.

### The four blocked on a printed contract

`gene_symbol_currency`, `trait_currency` and `gene_locus_agreement` belong to `check-identifiers`;
`acmg_secondary_findings` belongs to `check-acmg`. Both commands do put their question, report the
answer to stdout, and let the record die with the process — the sentence RM45's own docstring opens with
as the thing it exists to fix. Wiring them is not a small matter, because both commands **promise not to
write**:

> `check-identifiers`: *"Writes nothing: unlike the rsID check (whose verdict lands on resolution.csv),
> these are module-level identifiers with no sidecar column to record, so the report is the whole
> output."* (`enricher/src/just_dna_enricher/cli.py`, `check_identifiers_`)
>
> `check-acmg`: *"Writes nothing, for the same reason `check-identifiers` writes nothing: `acmg_sf` is
> an authored cell this asks a registry about, not a fact this pass contributes. Filling it here would
> break the check — see `hints.REDUNDANCY_BEARING`."* (same file, `check_acmg_`)

The same promise is made by `hint` in both CLIs (`hint_app`'s help in each `cli.py`), by `lookup`'s
module docstring, and — the part that decides how expensive a
reword is — by `docs/ENRICHER.md`, `docs/COMPILER.md`'s coverage table and the `create-module` skill's
command tables, which are printed for an author who has `pip install`ed the package and has no checkout.
It is a published contract in both CLIs, both package references and the skill, not an implementation
note.

**What "writes nothing" protects, and it is not one thing.** For `hint`/`lookup` it protects the
inject-only escape hatch and the Class-2 checks: `lookup`'s docstring says *"not a file, not a cell"*,
and the reason is `REDUNDANCY_BEARING` — a surface that can write is a surface someone asks to write,
and `--apply` on a lookup would ship the parked co-authoring item without deciding it. For
`check-identifiers`/`check-acmg` the stated reason is narrower and different: the cell in question is
*authored*, and filling it breaks the check. Both reasons are about not writing into the module's
authored data. Neither is about not writing a record of having asked.

**Is an attestation a *write* in the sense the promise means?** On the reason, no: `verification.json`
holds two counts and a closed skip key per check and no authored cell at all, so it cannot make a
Class-2 comparison vacuous, which is the harm both docstrings name. On the words, yes — and the words
are what a reader outside this repo has. The asymmetry gives the item away: `enrich` writes
`verification.json` and nobody calls that a violation, because `enrich` never promised otherwise. So the
blocker is not the design, it is that a narrowly-justified rule was written down as a blanket. Restating
one is not a docstring edit here: a printed contract is the surface this repo has measured the cost of
getting wrong, at 3,038 rows for the 0-vs-1-based `start` description.

**Would `--attest` be a second switch?** Yes, and it is the wrong shape twice over. The tier's standing
rule is that `--offline` is the switch and a pass adds no second CLI flag. Worse, a flag makes the
record *optional*, and an optional record is ambiguous between "the check was not run" and "it ran
without the flag" — which reintroduces the two-readings-of-one-absence defect the skip vocabulary
(`not_requested` versus `offline`) was built to end. A record has to be unconditional or absent by
design, never conditional on a switch.

**Candidate repairs, then:**

- **Wire them and leave the docstrings.** Ships commands whose printed contract is false. `describe` /
  `requirements` / `reference` and the skill's command tables are the authoring contract, not
  commentary, and this batch already found four other items landing just short of that surface.
- **Wire them and reword every site that carries the promise.** Legal, probably right, and a decision —
  the reword has to separate *writes no authored cell* from *writes no file* without inviting the
  `--apply` request the blanket wording deters, and one of those sites is written for a reader who
  cannot follow a pointer to the reason.
- **Fold both checks into `enrich` so the record comes from the pass that already writes.** They are
  separate commands because they are separately expensive and separately optional (OLS4, HGNC, the ACMG
  page), so this makes every enrichment pay for them. It also contradicts `merge_records`, whose whole
  purpose is that two commands write into one document.
- **Drop the unreachable members.** The one move Principle 3 bars: the vocabulary is closed and
  permanent within a major, so a removed member cannot return until 1.0 — and the vocabulary's own
  comment argues the opposite direction, that adding a name *late* means the release that needs it has
  none to write.

### The two deliberately reserved — not gaps, and not to be "wired too"

**`gene_disease_validity`.** Argued in the code beside `vocab.VALID_VERIFICATION_CHECKS`: it
*"has **no emitter yet** and is kept on the `withdrawn` precedent … 0.6's `enrich_gene_validity`
**records** ClinGen/GenCC verdicts into a derived table and compares nothing authored, so it does not
emit this. The member is for a future pass that checks an authored gene/phenotype pair against those
verdicts."* Wiring it to `gene-validity` would report a check where no question was put, which is the
confusion RM45 exists to end.

**`dosage_sensitivity`.** The same shape, with less written down. `dosage` is a `gene_metrics.csv`
writer and does not appear in `docs/ENRICHER.md`'s check table at all; the member's own comment reads
*"an authored dosage claim vs ClinGen's curation"*, and there is no authored dosage claim anywhere in
the schema — `haploinsufficiency` and `triplosensitivity` are columns on the **derived**
`GeneMetricsRow`. So it is reserved for a pass that does not exist, exactly like `gene_disease_validity`,
and unlike it nothing states so. That asymmetry is the small concrete deliverable this item carries: a
member should say on its own line whether it is *wired* or *reserved*, which is what would have made the
D4-1 headline count of twelve read correctly the first time. **Both now do**, and both stay reserved.

The exclusion half is already tested in one direction.
`schema/tests/test_verification.py`'s `test_a_pass_that_only_records_a_source_gets_no_member` pins
that `clinvar_assertion_tier`, `clinical_assertions`, `allele_frequency`, `gene_constraint` and
`article_license` are **not** members, on the rule the `assertions` command states about itself: *"It
records; it does not adjudicate."* Nothing tests the other direction, which is where the two reserved
members live.

### A finding about the merge itself, not about any one pass

Wiring the first of the six turned up something that belongs here rather than in the pass that found
it, because it is a property of the mechanism every future wiring will use: **`merge_records` replaces
per check, so a later run can downgrade a true verdict to a skip.** Measured — an offline `literature`
re-run, which is a documented no-op that keeps the existing sidecar as the pin, rewrote a real
`subjects=2 findings=1` record to `subjects=0 findings=0 skipped=offline`. The pass that found it is
repairing its own instance.

What is worth recording is that the general rule may be the one at fault. `merge_records` is *newest
wins, per check*, and its own docstring already argues the opposite case one step out:

> A check absent from `fresh` keeps its earlier record: a run that did not put a question has said
> nothing about it, and deleting the older answer would turn "not asked this time" into "never asked",
> which is the exact collapse RM45 exists to undo.

A `skipped(offline)` record **is** a run that did not put the question — the same fact, spelled as a
record instead of as an absence — so the argument that protects an absent check protects this one too,
and newest-wins does the deletion the docstring refuses. The counter-argument is real and is why this
is not decided here: a skip is a *fact about the latest run*, a reader may legitimately want to know
that today's enrichment could not reach the source, and a rule that lets an old `ran` outlive every
later skip can present a stale verdict as current. Both readings are defensible, which is what makes
the merge rule a design question rather than a bug: whether "newest wins" should hold unconditionally,
hold only between two `ran` records, or be replaced by something that keeps both facts. It reaches
every check wired from here on, so it wants deciding once.

**Decided and shipped in 0.6 PT2.** Newest-wins holds between two records of the same disposition; a
skip does not displace an answer. The counter-argument above is answered rather than dismissed — a
skip is a fact about the **run** and `verification.json` is a per-check document, so a run-level fact
needs a run-level place, which is a separate question and was not opened. The stale-verdict half of
the counter-argument turned out to be the real constraint and is handled by a condition the
implementation added: the protection applies only while the earlier record still describes the
module's authored bytes (`existing_still_binds`). Once they have moved the older record is about rows
that no longer exist, and this run's honest "could not ask" wins — which is what `literature` relies
on when a module's citations change, and without it this fix would have re-opened a defect an earlier
round had closed.

### The general question

Is a check that reports to stdout and writes no record a **defect**, or a legitimate **read-only
surface**? Both readings are live in this codebase and neither is stated. `hint` and `lookup` are
read-only on purpose and should stay that way. `enrich` and `enrich_clinpgx` attest. `check-identifiers`
and `check-acmg` sit between: they put a real authored-versus-source question, which is precisely the
membership rule `VALID_VERIFICATION_CHECKS` states — *does this compare something the module asserts
against what a source says?* — and then answer it only to a terminal.

**What would unblock it:** a decision on that line, which then settles the reword. The four members
follow mechanically once it is made; the two reserved ones do not move either way.

**Decided for these two commands, and only for them.** The line is not *does it write* but *does it
compare something the module asserts against what a source says* — a surface that puts that question
owes a record of having put it; a surface that answers a question about a value owes nothing. So
`hint` and `lookup` stay read-only on purpose, and their "writes nothing" is untouched.

---

# The lifecycle items — what writing down the second pass surfaced

Filed on **2026-08-16** out of [MODULE_LIFECYCLE.md](../MODULE_LIFECYCLE.md), which mapped a module from
origin to publish to a consumer's join and found that **the second pass had never been written down at
all**. Four items, none of them a defect in a rule: each is a place where two individually-correct rules
compose into something nobody chose, or where an absence only bites the second time somebody opens a
module. The document keeps the measurements (§5.1 the canary, §6.2 the six-edit consequence matrix, §6.3
what deleting a sidecar costs); these entries keep the decisions and the refused repairs, and do not
restate the numbers.

They were the closing section of that document — an "open questions" list — which is exactly the shape
this repo has twice found to be a backlog nobody reads. A question filed against a release is findable;
a question at the bottom of a prose document is not.

Everything here is legal in a minor.

## RM82 — the attestation binds raw bytes, so an editor's line endings un-close a module

**Severity** low-medium · **Status** **shipped in 0.6 (2026-08-17)** — `\r\n` → `\n` before hashing,
nothing else; `integrity.newline_normalized_file_entry`, used by the binding and by nothing else ·
**Owner** format (schema: `verification.module_binding`) · **Found by** the §6.2 measurement, and
sighted once before from the other side

> **One fact this entry does not carry, and it is the whole implementation.**
> `module_binding` *is* `artifact_digest` (`verification.py:79-90`), and `size=stat().st_size` is inside
> the hashed listing (`integrity.py:80-83`, `:106-112`). So normalizing the digest input while reporting
> the on-disk size **still moves the binding** on exactly the CRLF files the fix exists for — the naive
> implementation is a no-op that looks like a fix. The normalized length has to travel with the
> normalized digest, through a builder used by the binding and by nothing else. See
> [PROPOSAL_0_6_PT2.md](../proposals/PROPOSAL_0_6_PT2.md) § RM82.

### What was observed

Measured in [MODULE_LIFECYCLE § 6.2](../MODULE_LIFECYCLE.md#62-the-consequence-matrix--measured-not-derived):
rewriting `variants.csv` with a different line ending changed no value, no digest and no signature —
and still dropped the attestation **and** the closure. `verification.json`'s `module_hash` binds the raw
bytes of the authored files, so a formatting change an author never intended costs exactly what a
re-authored conclusion costs. An author whose editor normalizes newlines un-closes their module without
touching a cell.

### The decision

**Normalize `\r\n` → `\n` on the bytes before `module_binding` hashes them.** What separates this from
the content-aware binding RM45 rightly refused is that it needs **no loader, no schema knowledge and no
parse** — it is a byte transform, and the binding stays a byte binding. Precedent is on its side:
normalize-before-hashing is already the house move for `content_signature` (defaults folded in,
`exclude_none`, the default build omitted).

Three things settled with it, because each is a way the fix could go wrong:

- **The stopping point is newlines, and it is chosen rather than inherited from the first symptom
  reported.** A BOM, trailing whitespace and a missing final newline are the obvious next steps, and
  each makes the binding more content-ish without making it content. Newlines are the one difference a
  *tool* introduces on a file the author did not edit — an editor's default, or Git itself through
  `core.autocrlf`; the others are things a human typed. If a real case arrives for one of them it is
  additive (P3) and gets argued then, on its own evidence.
- **The cost is a one-time invalidation of every `module_hash` in existence**, all sixteen closed
  reference examples included. That is a **soft** break: a stale attestation warns and is dropped, it
  never fails a build. But it is every module in the wild re-attesting once, and the corpus re-closing
  in the same commit as the change.
- **`manifest.inputs[]` must not follow it.** Those raw-byte hashes answer *are these the exact bytes*,
  which is a different question — so normalizing one and not the other is coherent, not an
  inconsistency to tidy up later.

**As built, and where the prediction was wrong.** The invalidation is **not** universal: a binding moves
only for a module that actually carries `\r\n` in one of the twelve authored files, so **7 of the 16
reference examples re-bound and 9 were byte-identical** — for those nine `close_module` took its
`held` branch and kept records, producer and nonce verbatim. Which way round the corpus was CRLF is the
part worth keeping: `csv.writer`'s default line terminator **is** `\r\n`, so the machine-written half of
the corpus ships CRLF and the edit an author really makes is *normalizing to LF*. Two modules lost four
attested check records each (`cyp2c9_warfarin_grch37`, `hboc_palb2`) — dropped rather than re-bound,
which is the rule working. Nothing else moved: `artifact.digest`, `content_signature`,
`source_signature` and `resolution_signature` are byte-identical across all sixteen, measured before and
after.

### It was sighted once before, from the other side

[DOGFOOD_0_6.md](../probes/DOGFOOD_0_6.md)'s lane plan asked whether a round-tripped spec's attestation may read
as stale **to its own compiler** with nothing edited, since `reverse` normalizes cell formatting and
column order, and closed with *"Both are legitimate outcomes; neither is documented."* Same mechanism,
different trigger. The editor case is the one an author actually meets, which is what promoted the
question from an observation to a decision.

### What this is not

A change to **which files** the binding covers. That question — should the `authorship:` block be inside
it, given that appending a reviewer drops the attestation while moving no identity — was asked beside
this one and **answered the other way** on 2026-08-16: a review stamp is an attestation that zero
changes were needed, so un-closing is exactly correct and the reviewer re-closes. Recorded in
[MODULE_LIFECYCLE § 6.6](../MODULE_LIFECYCLE.md#66-authorship-across-passes). Do not re-open it as a
by-product of building this.

## RM83 — a derived sidecar can only be refreshed by deleting it, which discards the overrides it exists to hold

**Moved to [ROADMAP_HISTORY.md](../ROADMAP_HISTORY.md#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it-which-discards-the-overrides-it-exists-to-hold) on 2026-08-28.**
Closed rather than shipped, dissolved by RM124 once derived tables became pure build products, and
moved out of this file in the commit that landed the overlay — which is the condition
[PROPOSAL_0_7](../proposals/PROPOSAL_0_7.md#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it)
attached to the closure, because a closure recorded against an unlanded dependency is the kind of
bookkeeping that makes a ledger untrustworthy. **The heading is kept verbatim for its anchor** — six
documents link to it — and the entry and its reasoning now live in the history file.

## RM86 — a review pass is legal at the gate, refused by the pre-flight, and invisible once published

**Severity** medium-high · **Status** ✅ **CLOSED 2026-08-20** — all three findings answered by
`just-dna-registry`, two of them by code, and the question that was ours is decided and written into
[MODULE_LIFECYCLE § 6.6](../MODULE_LIFECYCLE.md#66-authorship-across-passes). Filed with them on 2026-08-16
as their S10, S11 and S12, one item per finding; all three are answered and archived in their history ·
**Owner** `just-dna-registry`, with a documentation half here — **that half is now done** · **Found by**
reading the registry tree on 2026-08-16, while settling whether a review pass costing the attestation is
a defect (it is not) · **Closed by** re-reading that tree at **registry 0.18.3** on 2026-08-20, prompted
by [S46](../CONSUMER_SUGGESTIONS_HISTORY.md) from `just-module-creator`, who measured the recognition half
from outside and reported §6.6 as stale

**How it closed, per finding.** The dispositions are not uniform, which is the reason this entry keeps
all three rather than collapsing to one line:

- **The pre-flight — fixed in registry 0.16.0.** `published_elsewhere` is a new field carrying the
  subset of content hits under a *different* `(namespace, name)`, and `would_publish_module_level`
  quantifies over it, so the verdict now matches the gate; `published_as` still lists the same-module
  hit, because a review pass wants to see it. The namespace is threaded through both pre-flight routes.
  Verified first-hand at `services/enrich.py` — the carve-out and the comment naming this exact defect.
- **The closure — fixed across 0.16.0 and 0.17.** `verification.json` is in `RECOGNIZED_SPEC_FILES`
  (0.16.0), so a rebuild carries it forward; it is in that registry's `DERIVED_FILES` and
  `manifest.derived` (0.17), so `download(include_inputs=True, layout="split")` returns it at
  `derived/verification.json`; and `manifest.verification` is projected onto the module-detail response,
  with `closed` re-bound by that server's own compile. Still **out of `SIGNATURE_INPUTS`**, which is the
  property that made recognising an unread file safe and is asserted by their tests. The version-lag
  clause is also dead: they now require `just-dna-format>=0.6.1` / `just-dna-compiler>=0.6.1`, not 0.5.4.
- **`authorship` unsurfaced — answered as policy, not repaired, and correctly.** It stays payload: a
  server that compiles what it publishes must not render the author's statement about their own reviewer
  beside claims of its own. Read it from the manifest, where it is plainly the manifest's word.

**The question that was ours is answered too**, by their reply to S12, and it is now §6.6's advice
verbatim: a `reviews` row by default; an `authorship` entry when the record has to travel inside the
module or be signed; both when both matter. The version-bump path is legal and costs a version number
and nothing else.

**Where the report lives:** `../just-dna-registry/docs/CONSUMER_SUGGESTIONS_HISTORY.md` (the tree is also
reachable as `just-dna-marketplace`, a symlink to it, which is the name this entry used to give), under
*Field notes from just-dna-format — the second pass*, as their S10–S12 with a reply on each. The original
filing carried the standing caveat that **0.6 was not published and not finished**, so the half of S11
needing a reader of ours was explicitly filed as *do not build against this yet*; 0.6 has since been cut
and that caveat has expired. This entry is the tracking record; their file is the authoritative report,
and the citations below were each verified in their tree first-hand rather than taken second-hand.

**Everything below this line is the 2026-08-16 finding as first written**, kept because the reasoning is
what a publisher should still hold and because two of the three sections describe behaviour that a
registry deployment older than 0.16.0 still has. Read it against the dispositions above.

### Why this was looked at

The decision that a review stamp is an attestation of zero changes settles the *format* side and
immediately raises the downstream one: a review pass publishes a version whose `content_signature`
**and** `artifact.digest` are byte-identical to its predecessor, differing only in `authorship` and
`verification.json`, neither of which is in either identity. Whether a catalog can even represent that
is not something this repository can assert from its own rules, so the registry was read. RM27's shape
applies — a finding about a downstream enforcer is filed as an **explicit ask**, not as an implication.

### What the publish actually does

**It succeeds, and the gate is right.** The duplicate-content check is keyed on `content_signature`
alone, enforced in the service layer before enrich/compile, and the same-module carve-out is real code
rather than prose — it compares `(namespace, name)` and is pinned by a test. Nothing else can bite:
there is no unique index on the digest or the content hash, and storage keys are
`namespace/name/version`, deliberately **not** content-addressed, with a comment giving this exact
reason. `latest` advances normally. `find-by-hash` returns both versions in a deterministic list, which
is the one place the shared digest is visible and is by design.

So the §6.6 sentence this document has carried — that the gate permits identical content within one
module — is now **confirmed against code** rather than believed.

### The three things that are wrong

- **The pre-flight disagrees with the gate on precisely this case.** `validation_report` computes
  `published_as` from the raw content lookup with **no same-module carve-out**, and the namespace is
  never threaded into the worker — so `validate` and `check` report the predecessor and answer
  `would_publish: false` for a publish that then succeeds. The registry's own test file states the
  standard this breaks (*"a pre-check that disagreed with the gate would be worse than none, because it
  would give a publisher confidence before taking it away"*), and its coverage tests only the
  different-name direction. **This is the one with a blast radius**: an automated publisher branching on
  the field the API documentation says to branch on refuses a legal publish, and a review pass is the
  commonest way to reach it.
- **The closure reaches nothing.** `verification.json` is uploaded by the client and copied into
  storage, and then read by no code path: it is not in `RECOGNIZED_SPEC_FILES`, so every server-side
  spec rebuild (`revalidate`, `upgrade`) drops it, and it is outside the served allow-list so no
  endpoint hands it back. `provenance.json`, one file over, *is* recognised and *is* served — so this
  is an omission rather than a policy. Compounded but not caused by a version lag: the registry pins
  **0.5.4**, where `manifest.verification` does not exist and `close_module` does not either, and the
  server regenerates `manifest.json` from its own compile — so today the closure cannot appear even in
  principle. The recognition gap outlives that upgrade; the pin does not.
- **The review is served but unsurfaced.** `authorship` does reach the published manifest and is
  readable two ways, but no projected field, column, filter or card element carries it, so seeing who
  reviewed a module means parsing the manifest — and only for the latest version without a second
  request. The registry's own schema states the policy this follows (*"a column is for something you
  filter or sort by; the rest is payload"*), naming `authorship` as payload.

### The question that is ours, not theirs

The registry already has a **`reviews` table** with a verdict tier and a `highlighted` flag, projected
onto module cards, costing no version number at all. This document has been saying that a pure review
is *"a real version bump without pretending the data changed"* — which is true of the format and may be
the wrong instrument on that catalog. The two mechanisms record different things (an `authorship` entry
travels **inside the module**, survives a download and a hand-off on disk, and is signed by the same
key; a registry review lives in the catalog and does not travel), so this is not a case of one being
redundant. What is undecided is what an author should be told to do, and whether both should be
recorded — and it is a **documentation** decision here, not a schema one: nothing in the format changes
either way.

### What this is not

A reason to re-open the binding question. Un-closing on a review is correct
([MODULE_LIFECYCLE § 6.2](../MODULE_LIFECYCLE.md#62-the-consequence-matrix--measured-not-derived)); every
finding here is about what a catalog does with the result, and none of them would be fixed by keeping a
closure the reviewer did not make.

**What would unblock it** *(as written on 2026-08-16; all three happened)*: the pre-flight carve-out and
the `verification.json` recognition are theirs and are small; the review-versus-version guidance is ours
and needs deciding once, wherever an author is told how to run a review pass.

## RM87 — an expanded row is indistinguishable from an authored one in the artifact

**Severity** medium-high (a consumer produced 3,762 false findings on it; caught before rendering) ·
**Status** **SHIPPED in 0.6 PT2 (lane B)** — `VariantRow.locus_index` **+** `locus_count`, both
`stamped_identity_field` (`exclude=True`, so no `content_signature` moved anywhere), stamped at the
expansion loop in `resolution.py` **and** at its twin in the deprecated `resolver.resolve_variants`
(digest parity between the two paths is a guarantee, and two round-trip tests caught the omission);
`locus_count` defaults to **1**; `_build_weights` materializes both as `UInt32`; reverse prefers the
stored column over its encounter-order recompute and keeps the recompute for a pre-0.6 artifact.
`_freeze_identity` overwrites an authored cell of either name, the way it already does for
`variant_key`. Measured over the sixteen reference examples: `artifact.digest` moved on the **nine**
carrying a `variants.csv` — hence a `weights.parquet` — and on nothing else; `content_signature`,
`sources.signature`, `verification.signature` and `compilation.resolution_signature` all held on all
sixteen. (The proposal predicted twelve and four; the real split is nine and seven, which is a
miscount in the prediction and not a behaviour difference.)
[PROPOSAL_0_6_PT2.md](../proposals/PROPOSAL_0_6_PT2.md) § RM87 is the design record · **Owner** format (schema) +
compiler (materializer, reverse) · **Motivating case** S33 in
[CONSUMER_SUGGESTIONS_HISTORY.md](../CONSUMER_SUGGESTIONS_HISTORY.md), from just-dna-lite

A one-to-many rsID is paired with every locus it resolves to, so K authored genotypes at that key
become K×N rows in `weights.parquet` and only the member whose alleles can carry a given genotype can
match it. The others are ordinary well-formed rows — real coordinate, real reference allele, the
module's own conclusion — and **nothing on the row says so**. `locus_index` lives in `resolution.csv`,
which SCHEMAS.md states is a lookup rather than a consumer contract and which gets no parquet by
design; the artifact carries `variant_key` and `authored_ident` and neither separates the members.

The reporting consumer that found this measured 2,579 rows into one genome's `pathogenic` section and
1,183 into `cancer`, each stating that a subject carried a pathogenic variant they do not have, all
from `TA/TA`-beside-`ref=TA` reference homozygotes at ClinVar duplication/deletion pairs. Their
mitigation — withhold any locus the artifact spells with more than one `ref` — took those to zero and
is **partial by their own account**, because same-`ref` expansions are invisible to it. They are real
here: `--keep-par-twin` records a pseudoautosomal locus on X and Y with identical alleles, which is
what `reference_examples/shox_par1/` was built from (nine of ten SHOX variants, 20 rows for 10
findings — RM32), and a paralogous rsID can name two positions carrying the same reference base.

**0.6 shipped the artifact-level half** — `manifest.compilation.expanded_keys`/`expanded_rows`, plus
the read-side contract in SCHEMAS § *the consumer join contract* and one expansion warning per rsID
carrying the true row total. Those answer *does this artifact contain expansion rows*. They do not
answer *is this row one*, which is the question a row-by-row reader actually has.

### The premise this item exists to correct

S33 declines to ask for the parquet column: *"the 0.5 digest window is closed and a new column moves
every module's digest, so that is a 1.0 conversation if it is one at all."* **That is wrong under our
own charter, and the mistake is ours for not having said so plainly enough.** Principle 3: *"A new
optional column, or a new optional table, is additive and lands in a minor: the authored identity —
`content_signature` and the per-input hashes — is unchanged, and only a recompile's `artifact.digest`
moves."* Principle 4 scopes byte-reproducibility to a fixed `compiler_version` in the first place, so a
digest that moves between compiler versions is the documented behaviour rather than a cost. And the
0.6 cost amendment prices this exact object at the bottom of its scale: *"Parquet columns —
approximately free. Materialized and derived; no human ever types one, and an author cannot see one. A
stamped, compiler-managed column is the cheapest thing this format can add."*

So the thing the reporter says they actually want is both **legal in a minor** and the cheapest class
of change the charter recognises. It is filed rather than shipped in the same pass for one reason
only, and it is not legality.

### The open design question — `locus_index` alone does not answer it

`locus_index` is what S33 names, and taken by itself it is under-determined: it is `0` on every
non-expanded row *and* on the first member of every expansion, so a reader holding one row cannot tell
the two apart. Making it answerable needs one of:

- **`locus_index` + `locus_count`** — index within the key's expansion, and how many members that key
  has. `locus_count > 1` is then the row-level predicate, self-sufficient and mirroring what
  `resolution.csv` already records. Two columns for one fact, which is the cost.
- **`locus_count` alone** — the predicate without the ordinal. Cheaper, and it loses the ability to
  line a weights row up with its `resolution.csv` row, which is the other thing an index buys.
- **A single boolean `expanded`** — cheapest to read, and it forecloses both of the above under
  Principle 5's one-way-door rule: a `bool` cannot later carry an ordinal without a retype, which is
  major-only.

None of these is obviously right, the name is permanent within the major (P5), and picking one during
a triage pass is exactly the kind of decision this repository files instead of guessing. Whichever
lands, it is compiler-managed and stamped, so it needs the three touch points — model, compile-side
row dict plus polars schema, and the reverse `fieldnames`/`_scalar_cell` pair — plus a round-trip test:
reverse currently *recomputes* `locus_index` by encounter order over the weights rows (which works only
because those rows are sorted on it), and a stored column would have to be shown either to agree with
that or to supersede it.

**What it does not change.** The expansion stays. Filtering the non-matching member is refused for the
two reasons COMPILER.md § Resolution already gives — a source's allele list is incomplete at least as
often as a module is wrong, and dropping rows changes what `reverse_module` reads back, which
Principle 7 forbids. The reporter argued the same case against their own first candidate, and they are
right.

## RM124 — an author's correction to a derived table has nowhere to live except inside it

**SHIPPED 2026-08-28 — the entry below is kept as the record of what was observed, and
[ROADMAP_HISTORY](../ROADMAP_HISTORY.md#rm124--an-authors-correction-to-a-derived-table-now-has-somewhere-to-live)
carries what it did when it landed.** Two things the entry and the proposal both got wrong or left
open, corrected there rather than here: the covered set is **seven** tables and not six (the proposal
never enumerated them and the six was a miscount — `gwas_effects.csv` is the one nobody counted), and
the wildcard `member` is refused for **`insert` as well as `suppress`**, because the row an insert
would create under an empty member carries no member value and so could never be matched again.

**Decided in [PROPOSAL_0_7](../proposals/PROPOSAL_0_7.md#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it) on 2026-08-28 — BUILDS in 0.7, and it is the round's keystone.** `overrides.csv`, keyed `(table, subject, member, field)`; operations `update`/`insert`/`suppress`, with the wildcard refused for the destructive one; applied at load and merge-not-clobber's *cost* dropped for the covered tables; P7 held by idempotency, so no `previous_value` column. Question 2 answered as a dated succession — see **RM135**.

**Severity** medium-high · **Status** ✅ **SHIPPED in 0.7** (2026-08-28) — the four questions were
settled in PROPOSAL_0_7 and the entry below is kept as the record of what was observed · **Owner**
format + compiler · **Motivating case**
S60 (just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md) · **Answers the blocking sub-question of
[RM83](#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it-which-discards-the-overrides-it-exists-to-hold)**

### What RM83 was blocked on, and what this is

RM83 named a missing operation — a `--refresh` that re-asks and reports — and named the thing that made
half of it unbuildable: *on most sidecars nothing records that a row was overridden*, so "re-derive the
machine rows and keep the overrides" cannot be implemented, because the tier cannot tell a curator's
edit from what the source said last time. It offered two exits: compare and report every difference
without classifying it, or **something has to start recording the edit**, which it called a schema
question with the usual cost.

This is that second exit, proposed by a consumer who built the first one and hit its ceiling. They wrote
a non-destructive wrapper around the delete-and-re-derive sequence — capture, verify the capture, delete,
re-derive, classify, reapply what is provably the author's — and it stops exactly where RM83 predicted:
when a subject is present in both copies with a differing fact, the fresh row is *either* a cell the
author edited *or* a revision the source published, and with two data points there is no third to
separate them. Their tool reports and refuses to resolve, which is the honest outcome and is a symptom.

### The proposed shape

A recognized **authored overlay table** that lies on top of a derived one and is never merged into it:
one row per `(table, subject, field)` carrying the authored value, the reason in prose, who decided, and
when. The derived files become pure build products — `derived = f(source, overlay)` — and four things
follow, three of which are theirs and all of which check out:

- nothing is hand-edited, so re-derivation is non-destructive **by construction** rather than by a
  wrapper being careful;
- a difference between a fresh row and a previous one means the source revised, full stop; the
  three-explanations ambiguity stops existing rather than being reported;
- the reason for a correction travels with the module instead of living in someone's memory;
- **the terminal state becomes detectable and it is free** — an overlay row that no longer changes
  anything means the source caught up, which is evidence that an authored judgement was later vindicated
  and is available nowhere else in this format. That is the observation to keep whatever else changes;
  it is the same shape as S52's, recorded there for the same reason.

### The charter, first-hand

Legal, and specifically invited. A new optional authored table is additive and minor-legal (P3), it
demotes nothing (P8), it is data and not code (P1), and it is authored input rather than a fetch (P2) —
a compiler reading it is doing what it already does with every other authored table. Under the 2026-08-12
cost amendment it is the **full-cost** layer, a human writes it; but that same amendment is what names
this class in the first place — *a derived table that is both machine-written and human-overridable can
be edited into a state that is not merely stale but is a false claim, and that wants a mechanism rather
than a convention.* RM45 discharged that for exactly one table by making `verification.json` unwritable
by hand. Nothing discharges it for the **seven** where overriding **is** the intended feature —
enumerated in [PROPOSAL_0_7 § RM124](../proposals/PROPOSAL_0_7.md#whether-merge-not-clobber-survives-it-does-not-and-what-replaces-it),
which corrected this count on 2026-08-28. It said *six* here and there, and listed them in neither.

### Four questions, and none of them is the tier

**Their tier argument is accepted and is not an open question.** An overlay is authored input, not a
repair, so report-never-repair is not at stake; and if each downstream tool applies its own overlay, two
consumers compiling one spec directory disagree about what the module says and the artifact stops being a
function of the spec. That settles *where*, and leaves:

1. **`(table, subject, field)` is not enough, and the table it fails on is their flagship case.** RM115
   shipped the merge keys they were blocked on, and it published something their derivation could not
   reach: `resolution.csv`'s key is `rule="subject"`, not a uniqueness constraint. One `variant_key`
   legitimately resolves onto several loci, `locus_index` orders them, and a pass replaces the group
   whole — so a subject names a *group of rows*, and an overlay row keyed on it cannot say which locus it
   corrects. Their `source="manual"` rows are in exactly that table. Either the subject gains a
   within-group discriminator for the one table that needs one, or overlays on `resolution.csv` are
   group-scoped and say so. `gene_validity.csv` needs the same care in a different direction — its key
   has two levels (`assertion_id` else the gene's grain), so an overlay written against one level is
   silent about rows keyed by the other.
2. **P5: this and `provenance.json` must not become two records of one concept.** S52 shipped
   `ProvenanceItem.outranks: dict[str, str]` — `{column: why}`, an authored cell outranking a source,
   with prose. The overlay is a corrected cell in a *derived* table, with prose. Their split is clean as
   stated (authored vs derived) and it is exactly the kind of line that erodes: the first author who
   wants to explain why their `clin_sig` beats ClinVar *and* why their `chrom` beats Ensembl has to learn
   which of two files each belongs in. Decide whether one record with a table column serves both, or
   whether the two are genuinely different axes, **before** either grows a second field.
3. **What P7 makes of a build product.** If the compiler applies the overlay, `reverse_module` has to
   reproduce a spec directory that recompiles byte-identically — which means deciding whether it re-emits
   the *pre-overlay* derived table plus the overlay, or the post-overlay table with the overlay beside it
   (in which case the overlay applies twice and the fixed point has to be checked, not assumed).
   `resolution_signature` and the fact signatures are over the derived tables as they stand today, so
   which of the two they cover is the same question wearing an identity.
4. **Whether merge-not-clobber survives.** The real prize is that `derived = f(source, overlay)` lets the
   rule be dropped for the tables the overlay covers, which removes the operational fact RM83 opens with.
   The real cost is that every pass writes through it, and dropping it changes what a re-run does to every
   module already published. That is the part that makes this 0.7 rather than a minor.

### The dependency that is real but routine

The registry rebuilds a spec directory from its own `RECOGNIZED_SPEC_FILES`, and a name missing there is
a file dropped on the next re-publish — which is how `licensing.csv` was lost before their 0.16.2. That
tuple is built from `SPEC_DATA_FILES`, a **hand-kept mirror** of our table constants, so an overlay needs
one entry added there. It is the same one-line change every new table kind already needs, and their own
comment records the scar; it is a coordination step, not a design blocker.
