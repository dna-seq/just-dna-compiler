# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S65

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
