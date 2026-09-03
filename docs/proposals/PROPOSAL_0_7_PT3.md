# PROPOSAL 0.7 PT3 — the three items left open after the 2026-09-02 round, planned for build

**Status: LIVE.** Drafted 2026-09-03, decided with the maintainer the same day. It wins over the
roadmap files until its items land, at which point it becomes a record like its six predecessors.

**Scope: three items, all decided, none designed from scratch here.** Each already has its shape
settled — RM160 by a maintainer choice between three written options, RM171 by a strategy document
the maintainer wrote, RM174 by a phase measurement that replaced its own premise. What this file adds
is the *build*: the order, the surfaces each one touches, what a first cut owes, and what it must not
do. Nothing below reopens a decision.

**Release class: all three are additive and fit the uncut 0.7.0.** A new parquet column, a new
verification-check member, a new cache lane and a new draft source are every one of them minor-legal
under P3/P8. No model field is removed, promoted to required or retyped. The 0.6 charter amendment
prices the authored layer: RM174 adds parquet columns only (approximately free), RM160 adds no
authored column at all, and RM171 adds no schema — it writes rows into tables that already exist.
(**RM160's half of that sentence is wrong and is corrected in the addendum at the foot of this file**:
it shipped with one optional authored column pair. Still minor-legal, still additive; the price was
misquoted, not the legality.)

**Not in scope, and named so nobody widens into them.** RM164 stays parked to 0.8 — the MITOMAP probe
confirmed its measured negative rather than moving it, and no source publishes a heteroplasmy level
per tissue. RM28 stays parked on its corpus, which RM174 just gave its first real entry. The
representation of a two-variant claim is RM28's and is not attempted here.

---

## Build order, and why

**RM174 → RM160 → RM171**, smallest first, and the order is not only size.

RM174 touches `civic_build` and nothing else; it is a day's work and it makes the CIViC parquet stop
stating something false, which every later CIViC-reading pass inherits. RM160 also reads CIViC and
adds the first live API read to the enricher's CIViC surface, so it wants RM174's columns already in
place — a citation recovered for a combination profile should be able to name the profile it belongs
to. RM171 is the largest by a wide margin (a new lane, a derived child lane, a registry field, a
draft source, a `SourceTerms` row) and depends on neither, so it goes last where a long build cannot
block two short ones.

---

## RM174 — publish the evidence item's own molecular profile

**Decided:** repair 2 of the two written — keep the fan-out, publish the real profile beside it.
**Not decided here and not attempted:** representing a two-variant claim, which is RM28's.

### What it is

`_submitted_evidence_row` stamps `molecular_profile_id` from **the variant's**
`single_variant_molecular_profile_id`, because that column is the join key into the profile map and
the evidence item's own profile would not join. The result is that CIViC evidence item 8721 — one
statement about `VHL S183L (c.548C>T) AND VHL D126N (c.376G>A)`, in trans — is written as two rows
each claiming to be a single-variant refutation, and the column that would have said otherwise has
been overwritten.

### The build

1. **Two new parquet columns** on `civic.parquet`, filled from the CSQ block
   `CivicVcfEntry.molecular_profile_id` already parses:
   - `evidence_molecular_profile_id` — the profile the evidence item actually belongs to.
   - `evidence_molecular_profile_name` — CIViC's own rendering of it, so a reader sees
     `VHL S183L (c.548C>T) AND VHL D126N (c.376G>A)` without a second lookup.

   On a single-variant row the **id** equals the existing `molecular_profile_id` — deliberately, since
   a column that is null on the common case invites a reader to treat null as "not a composite", and
   the honest statement is that every row knows its own profile. The **name** is null on a TSV-sourced
   row, because `MolecularProfileSummaries.tsv` publishes none; filling it from the variant's name
   would state a profile name the source never wrote.

2. **`molecular_profile_id` keeps its meaning** — the single-variant profile the row was joined
   through. Renaming it would be a wire break for a consumer that already reads it, and the field is
   doing a real job.

3. **A derived count, not a stored boolean.** Whether a row is a composite is
   `evidence_molecular_profile_id != molecular_profile_id` — derived-not-stored is the pattern for a
   convenience number (`@derived-not-stored`), and a stored flag would be a second thing that can
   disagree with the two ids.

4. **`release.json` gains `composite_profile_rows`**, the count of rows where those two differ, so
   the class is a published number rather than something each consumer re-derives
   (`@dont-discard-computed`).

5. **The TSV path is left alone**, and the asymmetry is documented rather than repaired. A
   multi-variant profile arriving through the TSV is dropped `combination_profile`, counted; through
   the VCF it is fanned out and now labelled. Making both paths keep it is a wider change that would
   move an accepted-basis build's numbers, and `@parity-by-check` says to audit an asymmetry
   deliberately rather than inherit it — this entry audits it and leaves it, with the reason in
   ENRICHER.md.

### Tests

- Over the real slice: every row's `evidence_molecular_profile_id` is non-null, and a row whose
  evidence item belongs to a multi-variant profile carries a different value from
  `molecular_profile_id` while a single-variant row carries the same.
- `release.json`'s `composite_profile_rows` equals the count derived from the frame — a relationship,
  not a copied number.
- A rebuild stays byte-identical (P7).
- RM170's check still reports one finding over two subjects, which it must, because it keys on the
  evidence id and never on the profile column.

### What moves

`artifact.digest` for any module compiled against a rebuilt CIViC snapshot, and the snapshot's own
digest. That is expected and is not a reason to defer.

---

## RM160 — the provenance half, at enrich time

**Decided:** shape 3 (read `SUBMITTED` at `enrich` time), the recovered citations **are drafted**,
and each drafted row carries a retrieval pin that a later run re-asks. Shape 1 (hash a capture) and
shape 2 (a second parquet) were both available and not taken.

### What it is

`civic build` reads dated files. The wider basis RM169 adopted comes from a VCF, and a VCF record
needs a POS — so submitted evidence attached to a variant with **no GRCh37 coordinate** is published
on one surface only, the API. That is the class RM160 opened on: ten records whose hidden citations
nothing local can reach, including variant 1955, whose only reachable evidence for a numbering
convention (EID 9969, Dollfus 2002, PMID 12202531, free full text) exists in the API and in no file
the builder reads.

### The build

1. **A per-variant API read in the enricher**, `evidenceItems(variantId:, status: ALL)`, behind the
   same offline discipline as every other fetch. CIViC is CC0, so `check_declared_use` does not gate
   it; `--offline` does, and the skip is `offline` rather than an empty answer
   (`@unreachable-not-absent`).

2. **It drafts `literature.csv` and `studies.csv` rows** for the citations the snapshot's basis does
   not carry. Appending, never rewriting (`@draft-appends`), matched on the identity key so a second
   run adds nothing.

3. **The canary, which is what makes drafting from a live read honest.** Every drafted row records
   *when the API was asked* and *on which basis*, pinned on the row's `SourceRow` rather than restated
   beside it. A later run re-asks CIViC for the same variant and reports when the answer has moved —
   an item accepted since, rejected since, or newly added. Without that pin an API-drafted row is a
   claim about a moment nobody wrote down, and the objection to drafting from a live read is exactly
   that. With it, the row is auditable.

   The re-ask is a `VALID_VERIFICATION_CHECKS` member, warning in both modes, never gating: CIViC
   re-curating is not an authoring error (`@a-source-recuring-is-not-a-strict-matter`), and the two
   currency findings stay apart.

4. **`status` rides as `confidence`/`confidence_unit`, unconverted** — CIViC's own instrument named
   rather than translated into a house grade, which the entry settled before this round. An
   `accepted` row and a `submitted` row must not be indistinguishable once both are in a file.

5. **`civic build` and `civic reproduce` are untouched.** That is the whole point of shape 3: the
   published snapshot keeps its byte-reproducibility contract and does not grow.

**Landed 2026-09-03**, as written apart from the one correction in the addendum below. See
ROADMAP_HISTORY for what shipped.

### What a first cut owes

- The skip must distinguish *the API said this variant has nothing more* from *nobody asked*. Three
  outcomes, not two.
- The read is per variant by construction, which is why it fits `enrich` and would not fit a build —
  say so in the docstring, because the first repair anyone proposes is to batch it into the builder.
- A pacing gate shared with the other network clients, and a probe that the disabling switch actually
  disables (`@off-switch-needs-a-probe`).

### Tests

- A drafted citation carries a retrieval pin, and a second run with an unchanged API adds no row.
- A moved answer fires the currency check and names which variant moved.
- `--offline` records `skipped`/`offline`, never `ran, findings=0`.
- The tautology guard: a module whose CIViC rows were drafted from the same basis is not re-reported
  against itself.

---

## RM171 — adopt the increment, never the photocopies

**Decided:** build it; **both** `mmutation` and `rtmutation` in the first increment; a **published
`mitomap-miss` child lane**; terms authored from the live read of 2026-09-03.
**The design is [rm171_diff_strategy](../probes/rm171_diff_strategy.md)** and is not restated here —
this section is the build order against it.

### Why both tables, settled

`reference_examples/mt_heteroplasmy` carries two variants and **both live in `rtmutation`; neither is
in `mmutation`**. An `mmutation`-only lane would draft nothing the one existing mtDNA module needs,
and the strategy's own warning is that shipping one table and finding the sibling later is how RM164
happened. It is the same join with a second input table, not a second shape.

### The build, in order

1. **`MITOMAP_TERMS`** in `licensing.py`, from the live r5 (2026-06-30) read: `CC-BY-3.0`,
   commercial and clinical use **stated** free, attribution `MITOMAP (mitomap.org)` or Lott et al.
   2013 (PMID 25489354), `share_alike=False`, `redistribution=True`. Written as a **floor** — the
   page says *unless otherwise noted*, so a per-record note outranks it
   (`@a-hosts-terms-are-not-its-contents-terms`). The compile gate does not fire.

2. **A `mitomap` cache lane.** Acquire is the dump (byte-identical to what RM164 held, no
   interstitial on the *data* surface). Build extracts `mmutation`, `rtmutation`,
   `mmutation_reference`/`rtmutation_reference` and `reference`. `SourceRow.dataset` pins the dump's
   `Last-Modified` and sha256.

3. **A `parents` field on `CacheLane`** — a tuple of lane names, empty for the twelve that shipped
   with RM176 — plus a guard that a child cannot rebuild before its parents, and a rebuild outcome of
   `built=None` when either parent is absent. Additive to a registry that shipped yesterday.

4. **The `mitomap-miss` child lane.** Not a download: its acquire stage is *both parents on disk*.
   Its build is the join on exact `(chrom="MT", start=position, ref=refna, alt=regna)` against the
   ClinVar chrMT parquet, upper-cased both sides, **no position-only matching**. Its `release.json`
   pins **both** parent digests, so a ClinVar rebuild without a child rebuild is detectably stale.

5. **Three buckets, and only one of them drafts**: photocopy (in ClinVar — nothing, the VCEP call is
   already adopted with ClinVar's provenance); rated miss (absent, bracket in the five documented
   classes — a `variants.csv` row with `clin_sig` from the existing normalizer); unrated miss
   (absent, no mappable bracket — counted, no `clin_sig` invented).

6. **`draft --source mitomap-miss`**, appending `variants.csv` + `studies.csv` + the `SourceRow`.
   `genotype` is stubbed with a before-validator the author must replace (`@stub-cannot-compile`) —
   MITOMAP publishes no called genotype and never will, so a MITOMAP-drafted module cannot compile
   until a human writes those cells. That is honest, and it is the cost of this adoption.

### What this must not do

Straight from the strategy, and each is a test:

- Never map `Reported` / `Cfrm` / `Conflicting reports` onto `clin_sig`. MITOMAP states in as many
  words that its confirmation token is **not** an assignment of pathogenicity.
- Never map `VUS*`. It is undocumented, it is not one of the five VCEP classes, it is not the
  legend's diamond, and it is not APOGEE's `VUS+`/`VUS-`. Withhold, count, and revisit if a legend
  turns up.
- Never draft a photocopy so a concordance check has something to disagree with — that is a tautology
  against a source this repo already adopts (`@tautology-zero`).
- Never left-anchor the `:` deletions in format or compiler. That needs an rCRS base at `position-1`
  and Principle 2 forbids those tiers from fetching. They stay in the unmintable count.
- Never put a count in a constant. **"16" is a fact about one ClinVar vintage, not about MITOMAP.**
  The first build owes a rejoin against the ClinVar cache of that day, and every test asserts a
  relationship rather than a number.

### What a first cut still owes, carried from the strategy's §7

`nlmid` was verified as a PMID on 4 of 4 sampled values and is empty on 397 of 6,770 reference rows —
the column has to be walked before the lane claims "every citation". The 250 unbracketed rows absent
from ClinVar are an identity increment with no mappable class, counted as unrated miss, and whether
their identity earns a row at all is a second, smaller call that can wait.

---

## What "done" looks like for this round

Each item lands as its own commit block — behaviour with its test, doc and changelog line — and moves
from ROADMAP to ROADMAP_HISTORY with its RM_TOC row restated. When all three have landed this file
becomes a record, and the next open item is tracked in ROADMAP like any other, not by this proposal.

**One thing that is not code and is owed to whoever publishes:** the ClinPGx HuggingFace snapshot is
still the 2025 parquet until `clinpgx build` + `clinpgx publish` run. RM175 rebuilt the builder, not
the published artifact. Publishing is outbound and stays the maintainer's.

---

## Addendum, 2026-09-03 — RM160 shipped with an authored column pair, which this file priced at none

The release-class paragraph at the top says RM160 "adds no authored column at all". It shipped with
two: `StudyRow.confidence` and `StudyRow.confidence_unit`, optional, 0.7.0.

**Why the estimate was wrong.** The item's own point 4 requires `status` to ride as
`confidence`/`confidence_unit` — a requirement settled before this round, in RM160's entry, and
restated here as non-negotiable. What nobody checked while writing the release-class line is that **no
authored model carried that pair**. `ClinSigAuthorityCallRow` has it, and that is a machine-written
concordance row about clinical significance, not a citation. So the requirement and the price were
written a paragraph apart and could not both be true, and the one that had a test attached won.

**The legality does not move.** A new optional column is minor-legal under P3/P8; nothing was removed,
promoted to required or retyped. `content_signature` does not move for a module that fills neither
cell — asserted by hashing a module that declares the columns empty against one written before they
existed — and the parquet the pair lands in is `studies.parquet`, which RM140 had already moved on the
ten reference examples carrying one, inside this same uncut 0.7.0. The 0.6 amendment's price is real
and was paid: the authored layer is full cost, and the gate it asks — *will this burden the author?* —
is answered by both cells being optional and by the model refusing only the incoherent combination.

**The rule this records, since a closed proposal is closed against reopening its decisions and not
against recording one taken inside the same release.** A release-class line that prices an item at
"no authored column" is a claim about the *schema surface as it stands*, and it has to be checked
against the models rather than inferred from the item's shape. This one could have been settled by a
single grep for the field name.
