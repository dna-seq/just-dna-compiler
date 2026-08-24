# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S75

**Claim ids from here, never from what this file shows.** S1–S46 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
.claude/triage-state.py --next        # scans this file AND the history file
```

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## Everything before S30

S1–S29 are all answered, as of 2026-08-16 — see
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), whose contents list is the one-line
summary of every one. Seven spawned roadmap items — **RM43**, **RM44**, **RM45**, **RM46**, **RM47**,
**RM48**, **RM49** — and all seven shipped in 0.6.0, RM44 and RM49 on 2026-08-12 and the rest with the
design round on 2026-08-13; **S29** spawned **RM80**, shipped 2026-08-16. [RM_TOC.md](RM_TOC.md) is the index for that half and carries their status. The distinction the sentence was written for still holds:
*answered* means a consumer has a reply, never that the work is finished.

**Answered is not installable, and this is the standing rule for every reply in both files (S34).**
A reply that says "shipped in the tree" means the code and tests are committed, never that a consumer
can `pip install` it — check [CHANGELOG.md](CHANGELOG.md) for whether the version it names has actually
been cut. S25 and S26 were the first replies to carry that state; everything labelled 0.6.0 sat in it
until **2026-08-17, when 0.6.0 was cut and tagged `v0.6.0`** across all three packages. Tagged is still
not installed — publishing is a separate step and the maintainer's call — so the rule is unchanged and
only the example moved. S34 is here because a document of ours presented a table of 0.6 fields as
"also shipped since you last synced", and a consumer spent an afternoon looking for fields no version
they could install has. Write the version, and write whether it was cut.

## Adding one

Append a `## Sn — <what happened>` section with the id above. Write the report, not a request: what you
ran, what you expected, what happened, and what you did about it meanwhile. A candidate fix is welcome
and so is a reason a candidate is wrong — several of the answers in the history file are shaped entirely
by a reporter's argument against their own first option.

Prose is left byte-for-byte when it is answered and when it is moved, so it stays the record of what was
observed rather than of what was decided.

---

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

<!-- triaged: 0.6.7 · sha be123afbaead -->


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

## S65 — we built the consumer half of RM126, and it narrows what RM126 has to publish

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
## S66 — `enrich()` writes `resolution.csv` once, at the very end, in place, with no lock — so a run killed at minute 29 has written nothing, and one killed mid-write leaves a valid-looking short file

**Status — accepted. Ask 1 shipped 2026-08-24; asks 2, 3 and 4 are filed as
[RM128](ROADMAP.md#rm128--enrich-persists-nothing-until-its-tail-so-a-run-killed-at-minute-29-has-written-nothing),
open, a minor, release undecided.** Every line of your reading holds against the tree and not only
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

**What you can do now:** upgrade when 0.6.7 is cut and the truncated-file class is gone. The lost-work
class is not, so a long unattended run still wants the timeout raised on your side until RM128's
second half lands.

<!-- triaged: 0.6.7 · sha 1b43eba05679 -->


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

<!-- triaged: 0.6.7 · sha 9886db1793f6 -->


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

<!-- triaged: 0.6.7 · sha ae749c00ff13 -->


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
[RM130](ROADMAP.md#rm130--a-checks-findings-are-counted-and-not-kept-so-a-conflict-has-no-name-to-act-on),
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

<!-- triaged: 0.6.7 · sha 7eca8f9cafc6 -->


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

<!-- triaged: 0.6.7 · sha 0becb402ecc1 -->


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
