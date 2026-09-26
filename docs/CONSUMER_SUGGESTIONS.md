# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S114

**Claim ids from here, never from what this file shows.** S1–S113 are all answered and live in the
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

## S114 — the `panel_block_deprecated` replaced-branch warns whether or not you need the three fields it says to keep the block for, so there is no way to signal "accepted"

**Status — accepted, filed as [RM265](ROADMAP.md#rm265--the-panel-deprecation-has-no-accepted-signal-on-the-replaced-branch-the-warning-fires-whether-or-not-you-need-the-three-fields-it-tells-you-to-keep-the-block-for) (open, a minor), plus a doc fix shipped this pass.** Reproduced against the code: on the `replaced=True` branch (`compiler.py:4231`) `panel_block_deprecated` fires for a fully-migrated module, and its `unreplaced` clause tells the author to keep the block for `genes`/`significance`/`reference_sha256` — so keeping it *is* the permanent warning, with no key to say "accepted". Your reading is exactly right, and it is the state P3 forbids: a deprecation is legal in a minor only where the audience can act, and for these three fields on the replaced branch no replacement exists.

The design question RM265 records is whether `panel:` is deprecated *as a whole* or only its reader. Your candidate (1) — a home for the three fields, a `panel_provenance:` sub-block or keys beside `dataset` — is the P3-clean answer and is minor (additive); it is a schema-shape decision for the version interview (where the gene *denominator* lives, and that it is your one lossy field). Your candidate (2) — fire only on `replaced=False` — we are **not** taking on its own: it silences a *true* statement on the modules that keep the block, so they would compile clean until 1.0 removes the block under `extra="forbid"` and the data with it, and P3 makes a major ship its upgrade procedure rather than a silent loss. So (2) is a noise stopgap, not the fix.

Doc fix landed now (patch): the RM4 row in [ROADMAP_1_0.md](ROADMAP_1_0.md)'s upgrade tracker still carried the pre-S69 line "delete it, nothing replaces it, consumer no action needed" — that is the migration procedure P3 turns on, and it is corrected to name the three-field loss, the empty-`dataset` trap, and RM265. Your workaround (record the three in a `manifest.logs`-hashed provenance log) is exactly the right shape meanwhile, and RM265 exists so it does not stay per-consumer.
<!-- triaged: 0.7.x · sha 436f69c4b141 -->

**What we ran.** just-dna-lite rebuilt its three ClinVar gene-panel modules (`cardio`, `cancer`,
`pathogenic`) under 0.7 (compiler 0.7.1). Each authored a `panel:` block and each compiled with
`panel_block_deprecated`. All three are in the **`replaced=True`** branch: their licence row carries a
`clinvar,annotation` entry with a non-empty `dataset` (`clinvar_2026-06-27`), which `draft_gene_panel`
writes, so the block's one machine reader — the clin_sig cross-check — is already migrated.

**The contradiction we hit.** The replaced-branch message ends "`genes`, `significance` and
`reference_sha256` have no replacement anywhere — keep the block until 1.0 if you need them recorded."
But the block emits `panel_block_deprecated` *whether or not* you need those fields, and there is no key
to say "I read this, I need the three, stop telling me." A consumer who follows the advice keeps a
permanent deprecation warning on every compile of a module that is otherwise fully on the upgrade path;
a consumer who wants it clean has to drop provenance the format itself says has no home. The two
outcomes the message offers are "warn forever" and "lose data", with nothing in between.

**What we did meanwhile.** We moved the three fields into our own provenance record (`clinvar_panel.log`,
already hashed into `manifest.logs`, which survives the 1.0 removal) and dropped the block, so the
warning clears with no loss. Two of the three were **already** in that log before we touched it —
`reference_sha256` as the `clinvar_source_sha256` line and `significance` as the `clin_sig` line — so
only the requested **gene list** actually needed adding. Worth noting for the 1.0 upgrade-path doc:
of the three, only the gene list is not trivially reconstructable — `significance` is a build constant
and `reference_sha256` was already duplicated; the gene list is recoverable from `variants.csv`'s
`gene` column but **lossily** (cardio requested 327 genes and 297 matched a pathogenic variant; the 30
that matched none are absent from `variants.csv` entirely).

**What 1.0 needs (candidate fixes, either suffices).** Give the three fields a home that is not the
deprecated block — a small `panel_provenance:` sub-block under `module_spec.yaml`, or three keys beside
`dataset` on the licence row — so a derived-panel module can record what it was built from without a
deprecated surface. Or, if they are genuinely meant to have no home, **split the warning so
`panel_block_deprecated` fires only on the `replaced=False` branch** (where the block is still the sole
record of the snapshot and the warning is actionable): on the `replaced=True` branch it currently tells
a consumer who has done everything right that they are still wrong. Our workaround (record them in a
consumer-side log) works but is per-consumer; every consumer of the panel route will re-derive it.

---

## S115 — RM7: a consumer's diplotype-call output schema, and the one thing the artifact could not tell it

**Status — recorded; output schema is RM7 corpus (a consumer contract, no format RM), the defining-site gap is (b): the artifact already carries it, derivably.** Two halves.

The output shape — the four-state `status`, the phenotype-only-on-agreement rule, the consistent candidates, the tri-state per-site evidence, `phase_would_decide` — is exactly the kind of ground-truth [RM7](ROADMAP.md#rm7--evaluation-output--report-card-schema) is parked on. RM7 is **not format scope**: per-sample results are a *measurement*, so the caller's output is `just-dna-lite`'s contract to settle, and this shape is now noted on RM7 as the first corpus entry a shipped caller produced. Nothing to file here — that would put a measurement in the format.

The defining-site gap is `@derived-not-stored`, and the reconstruction you already do is provably the whole answer. A gene's defining-site set is the union of the sites named across that gene's `haplotypes.parquet` rows, and that union is complete: a site is *defining* only if some haplotype is non-reference there, and every such site appears in that haplotype's row — even under the sparse convention where a row lists only its non-reference variants. So "this site was a `no_call`" versus "this gene defines no site there" is decidable by any artifact reader, not just your caller: (defining set = the union) minus (the sites your sample called) is the withheld-because-uncalled set, and it needs nothing the artifact does not already ship. A per-gene completeness column would be a convenience over a derivable fact, which P9 keeps out of the authored layer — so we do not materialize it, on the same reasoning `effective_*` reads a derivation rather than storing it. If it ever turns out the union is *not* complete for some real module — a defining site no haplotype row can name — that is a genuine gap and worth a fresh report with the case; we probed `hfe_compound_het` and `apoe_epsilon` and did not find one.
<!-- triaged: 0.7.x · sha 865633adb667 -->

**What we ran.** just-dna-lite built the phenotype caller RM7 assigns to the consumer — the thing that
turns a VCF into a diplotype. It reads a `haplotypes` + `diplotypes` module and emits one call per
(module, gene). Compiled the `apoe_epsilon` and `hfe_compound_het` reference examples with the installed
compiler 0.7.1 (both clean, `haplotypes.parquet` + `diplotypes.parquet` + `manifest.json`, coordinates
fully populated) and ran the caller against real WGS samples.

**The output shape that survived contact with two real modules**, as corpus evidence for whatever RM7
settles on: a **status** of `called` | `ambiguous` | `not_assessable` | `no_match` (never silence, never
a reference default); a `phenotype` set only when every consistent diplotype agrees; the **consistent
candidates** themselves; a **per-site evidence** list, tri-state `called` | `restored_hom_ref` |
`no_call`; and a `phase_would_decide` predicate (see S116).

**The one place the artifact could not answer a question the caller needed.** There is no stated *defining
site set* for a gene. The caller reconstructs it from the union of the gene's `haplotypes` rows — which
works — but it makes two different situations indistinguishable to anything reading the *artifact* rather
than our derived call: "this site was a `no_call`, we could not observe it" versus "this gene does not
define a site there at all". A `called` status that had to withhold because a defining site was uncalled
is a different statement from one that had nothing to withhold, and only the consumer's reconstruction
currently tells them apart. A per-gene defining-site set (or a completeness flag derived from one) would
put that distinction in the artifact. Filed as an observation, not a blocker — we derive it and move on.

## S116 — RM28: the HFE compound-het-vs-cis case is a meta-conclusion a consumer can name but not resolve

**What we ran.** The caller from S115 against the compiled `hfe_compound_het` example, with a sample
heterozygous at both rs1800562 (C282Y) and rs1799945 (H63D), unphased.

**What happened.** The genotype is consistent with **two** diplotypes the module maps to **different**
phenotypes: `C282Y / H63D` (compound heterozygous, in *trans*) and `C282Y-H63D / wt` (both variants in
*cis*). Nothing in an unphased VCF distinguishes them, so the honest call is `ambiguous`, and the caller
marks `phase_would_decide` because the two candidates share the observed allele multiset at every site and
differ only in homolog assignment. This is RM28's "predicate keyed on more than one subject" as it reaches
a consumer: the readings are enumerable, the resolution is not. Two notes from having built it:

1. What made the ambiguity **expressible** is that the module defines the cis allele (`C282Y-H63D`) as an
   explicit haplotype with its own diplotype row. Without that row the caller would have reported
   `no_match` or a single wrong phenotype. The enumerative `diplotypes` table already carries what a
   consumer needs to *name* the ambiguity — keep that property.
2. What the artifact cannot carry is **which diplotype pairs are the phase-confusable set.** The caller
   derives `phase_would_decide` by comparing the consistent candidates' per-site multisets — a
   reconstruction. If an RM28 axis let an author state "this pair is distinguishable from that one only by
   phase", a downstream reader of the artifact could see the confusable set without running our engine.

Both S115 and S116 are usage observations from a consumer that shipped the feature; neither blocks
anything, and both are left as the record of what building the diplotype caller against 0.7 actually
needed.

---
