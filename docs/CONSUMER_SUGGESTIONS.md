# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S35

**Claim ids from here, never from what this file shows.** S1–S29 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
.claude/triage-state.py --next        # scans this file AND the history file
```

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## S34 — reply to CONSUMER_BRIEF_LITE: two gaps (both now closed), two deliberate, one joint

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16. This is the line-per-section answer
`CONSUMER_BRIEF_LITE.md` asked for, plus what we changed on our side. Every grep in the brief
reproduced exactly as written. *(The brief itself was removed in `6c9db05`, the commit that filed this
answer — recover it from git history if you need the questions it put.)*

**A version fact that gates half of it, and that we could not tell from outside.** We are on
**0.5.4** of all three packages. The installed `Compilation` model carries `compile_success`,
`compiled_at`, `compiled_by`, `compiler_version`, `ensembl_reference`, `fully_resolved`,
`resolution_mode`, `resolution_signature`, `resolution_sources`, `vrs_alleles`,
`vrs_alleles_identified`, `warnings` — and nothing else. So `resolution_subjects`,
`positional_rows`/`positional_rows_placed`, `gene_validity`, `clinical_assertions`, `derived`,
`readme`, `verification` and `just_dna_format.layout` do not exist in any version a consumer can
install. The brief presents that table as *"also shipped since you last synced"*, which reads as
"pip and you have it"; this file's own S25/S26 note says the opposite and is right. Worth one
sentence in the brief saying the table is 0.6 and 0.6 is uncut, because we spent a while looking for
fields that were never going to be there.

**§1 `verify_manifest` — gap, and the spec is the first half of it.** Confirmed: no call site,
and `compiled_by` appears only as a value we write. One thing to know that the brief does not
mention: the 0.5.4 signature is `verify_manifest(module_dir, manifest, *, require_marketplace=True,
…)`, so the *default* is the marketplace policy. A naive single call site would reject every
locally-compiled module, since our own compiler leaves `compiled_by` null by design. Wiring it means
two policies — `True` for a registry install, `False` for a local compile — which is a fine contract,
just not the one the parameter name advertises at a glance. Meanwhile we have marked the
verify-then-install flow in our `docs/MODULE_MARKETPLACE_SPEC.md` as unimplemented rather than let it
keep describing behaviour we do not have.

**§2 `resolution_mode` / `fully_resolved` — deliberate, and your guess is right: the docs are what
needs fixing.** Registry-projected `resolution.trusted` is the only path we intend to support. The
stronger reason than "the registry already evaluated it": for the question the annotating engine
actually asks — *can this table join to a VCF by position* — we read the artifact's own null
coordinates (`_lead_join_strategy` in `hf_logic.py`) rather than any manifest field. That is
authoritative for the bytes in hand, needs no trust rule, and works on a module whose manifest we
never fetched, which on the HuggingFace path is all of them. By the same argument we do not expect to
need `positional_rows_placed == positional_rows`: it is the manifest-side twin of a test we already
run against the data.

**§3 no module version on an annotation run — gap, and the only one of the five that touched the
report. Closed.** `ModuleOutputMapping` gained `version`, `digest` and `source_url`, filled by a new
`read_module_provenance()`, and the report renders a "Modules in this report" table from them. Three
choices worth stating because they are the honest half:

- All three are **tri-state**. `None` means *not established*, never "unversioned" and never
  "unverified". A module discovered on HuggingFace has no manifest fetched at all, so only
  `source_url` is knowable there, and the template renders the other two as *Not stated*.
- The digest recorded is the one the module **claims** — read from `manifest.json`, not recomputed —
  precisely because §1 is still open. It ties a report to a stated identity, not a checked one, and
  the docstring and the template both say so.
- Version falls back from `identity.version` to the authored spec, as the brief suggests. Doing it
  surfaced something on our side rather than yours: six of our own Gen-I ports author
  `module.version: null` (longevitymap among them), so *Not stated* is the common case across our
  corpus today. That is ours to fix in the porting pipeline, not a format issue — recording it here
  only so a reader of the next brief does not read those blanks as a contract failure.

**§4 flat HF layout — joint, and we agree it wants agreeing.** Confirmed on our side exactly as
described: no version segment, no digest check, and the only invalidation keyed on our own package
version. The §3 fields are a partial mitigation and we want to be clear about how partial: on the
HuggingFace path they record *where* a module came from and nothing about *which build*, so a
silent republish is still invisible to a saved report. If the publisher grows a version segment we
will follow it in discovery; the `vN` fallback in our generic fsspec scan is already the shape.

**§5 two predicates for "is this a module" — gap. Closed.** Your reading is right: `weights.parquet`
was standing in for "has a lead table" in all three places, not meaning "SNP-core module". Traced
consequence, which is worse than the brief guessed: a `pharm_variants`-led install was discovered
and annotated fine, but invisible to `module list-custom`, unbadged in the module list, and — the
real one — **absent from the publish/edit pane, so an installed PGx module could not be published or
edited from the UI at all**. Same failure mode as the discovery bug that made such a module
unpublishable in the first place. Fixed with one shared `find_lead_table()`/`has_lead_table()` over
`LEAD_TABLES` in `module_config`, so the local-filesystem predicate and the fsspec one now answer the
same question, and a new family is one edit for both.

## S33 — "exactly one of those rows can match" is true, and the other rows are not inert to a reader

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, from the same run as S31 and S32 and
found while building the restoration feature S32's reply discusses.

**We know this one is documented, and we are not asking for the expansion to change.**
[COMPILER.md](COMPILER.md) says it plainly: *"one-to-many rsid reverses into N rows that each carry
their own locus's alleles beside the **one** genotype the author wrote; exactly one of those rows can
match"* — with an unconditional error rejected because it would break P7's fixed point, and the
`{ref} ∪ alts` membership check deliberately unioned across loci because a short alt list is a gap in
the source at least as often as a defect in the module. We think all of that is right. This report is
about the scope of the word **match**.

**What we ran.** The same twelve-module annotation of Anton Kulaga's variant-only WGS genome, with the
first cut of reference-genotype restoration: reporting a module's authored *reference* genotype at
sites the callset emitted no record for.

**What happened.** It would have emitted **2,579** rows into that genome's `pathogenic` section and
**1,183** into `cancer`, each telling the reader they carry a pathogenic variant they do not have.
Caught before rendering. Every one came from a one-to-many expansion.

**The trace**, given in full because we first blamed our own panel builder and were wrong:

1. **ClinVar holds two real records** at 5:112767222 under one rsID — Variation 428095, the
   duplication `T → TA`, and Variation 2583495, the deletion `TA → T`, both pathogenic. Correct data.
2. **Our panel authors it faithfully, rsid-only.** `variants.csv` has exactly two rows, no
   coordinates: `T/TA` and `TA/TA`, both meaning the duplication ("genotype: homozygous (two
   copies)").
3. **`resolution.csv` records both loci** under one `variant_key`, `locus_index` 0 and 1,
   `status=resolved` on both.
4. **The compiler pairs each authored genotype with each resolved locus.** 2 × 2 = four rows in
   `weights.parquet`, so `TA/TA` also lands beside `ref=TA`.

**Where the scope assumption breaks.** Against a position join, row 4 is exactly as harmless as the
prose says — nothing matches it. But it is not silent. `TA/TA` beside `ref=TA` is a **well-formed
reference genotype**, and a consumer doing anything other than a position join — classifying a row,
counting rows, or asking "what does this module say about someone who is reference here" — reads it
as a statement the module never made. Ours read it as *"the reference genotype at this locus is
pathogenic"*: syntactically valid, and false.

Nothing on the row marks it as the non-matching member, though the compiler knew which it was at emit
time. We checked: `locus_index` is **not carried into `weights.parquet`** (the artifact has
`variant_key` and `authored_ident`), and SCHEMAS.md is explicit that `resolution.csv` is a lookup
rather than a consumer contract — so from the artifact alone a reader cannot tell an expanded row from
an authored one.

**Scale in our corpus**, `variant_key`s resolving to more than one locus:

| module | variant_keys | multi-locus | same position | same `ref` |
|---|---:|---:|---:|---:|
| `cancer` | 68,331 | **1,296 (1.9%)** | 1,296 | **0** |
| `pathogenic` | 305,850 | **2,730 (0.9%)** | 2,728 | **0** |
| `cardio` | 57,055 | **540 (0.9%)** | 540 | **0** |
| `longevitymap` / `coronary` and the other curated modules | 528 / 27 | **0** | — | — |

Those match the false reference-genotype rows we measured (1,296 / 2,727 / 539) one for one, which is
what identified the mechanism rather than merely correlating with it. Only the ClinVar-derived panels
are affected, and the corresponding shape is in your corpus too —
`reference_examples/pathogenic_clinvar/` is named in COMPILER.md as having three variants of it.

**What we did meanwhile, and why it is not a fix.** Withhold any locus the artifact spells with more
than one `ref`. That took the three panels to 0 and left every curated module untouched. It works
**because of the last column above** — every expansion we hold is same-position/different-`ref`, which
is a property of ClinVar's duplication/deletion pairs and not a guarantee the format makes. A
same-`ref` expansion (two loci differing only in `alts`, or at two positions) is invisible to our check
and to any consumer's, and we would have no way to know it had happened.

**An argument against the repair we would have proposed first.** "Emit the genotype only at the locus
where it fits `{ref} ∪ alts`" is wrong for the reason COMPILER.md already gives — `alts` came from a
source, ClinVar carries only submitted alleles, so a genotype not fitting a locus is a gap in the
source at least as often as a fact about the module, which is why the check unions across loci in the
first place. Dropping rows would also change what `reverse_module` reads back, which P7 forbids. We do
not think the expansion should be filtered.

**The ask, both halves small.**

1. **A read-side sentence.** The statement quoted above lives in the authoring/validation discussion,
   where "can match" is the natural frame. A consumer reading SCHEMAS.md § weights gets no signal that
   a row may be a non-matching member of an expansion, and the natural reading of a parquet row is
   that it is a standalone assertion. One sentence on the read side — *a row asserts something about a
   (locus, genotype) pair, and only the matching member of a one-to-many expansion asserts anything* —
   would have saved us the incident.
2. **A count on the manifest, the RM44 / `positional_rows` shape.** A count of expanded keys (or rows)
   would let a consumer know an artifact contains expansion rows at all, and act on it, without
   touching `artifact.digest`. Carrying `locus_index` into the parquet is what we actually want and we
   are explicitly **not** asking for it in a minor — the 0.5 digest window is closed and a new column
   moves every module's digest, so that is a 1.0 conversation if it is one at all.

**One adjacent question we cannot answer from 0.5.4.** S32's reply says `_check_genotype_coverage`
"takes the reference allele from the row or from `resolution.csv`" and fires at a site annotated for
two or more genotypes. At an expanded locus there are two reference alleles at one position and four
rows. If that check runs post-expansion, does it see one site with two genotypes under each `ref`, and
does the reference-homozygote reason fire on the row that *is* the other locus's hom-alt? We may be
wrong about the ordering — we cannot run 0.6 — but the two features touch the same rows and it seemed
better to ask than to find out after recompiling the corpus.

## Everything before S30

S1–S29 are all answered, as of 2026-08-16 — see
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), whose contents list is the one-line
summary of every one. Seven spawned roadmap items — **RM43**, **RM44**, **RM45**, **RM46**, **RM47**,
**RM48**, **RM49** — and all seven shipped in 0.6.0, RM44 and RM49 on 2026-08-12 and the rest with the
design round on 2026-08-13; **S29** spawned **RM80**, shipped 2026-08-16. [RM_TOC.md](RM_TOC.md) is the index for that half and carries their status. The distinction the sentence was written for still holds:
*answered* means a consumer has a reply, never that the work is finished.

**S25 and S26 are answered but not yet installable**, which is a state this file had not carried
before: each fix is a new optional manifest field, so it is legal only in a **minor**, and the tree
still reads 0.5.4 because cutting a release is the maintainer's call. A reply that says "shipped in the
tree" means the code and tests are in `main`, never that a consumer can `pip install` it — check
[CHANGELOG.md](CHANGELOG.md) for whether the version it names has actually been cut.

## Adding one

Append a `## Sn — <what happened>` section with the id above. Write the report, not a request: what you
ran, what you expected, what happened, and what you did about it meanwhile. A candidate fix is welcome
and so is a reason a candidate is wrong — several of the answers in the history file are shaped entirely
by a reporter's argument against their own first option.

Prose is left byte-for-byte when it is answered and when it is moved, so it stays the record of what was
observed rather than of what was decided.

---
