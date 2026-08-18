# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S41

**Claim ids from here, never from what this file shows.** S1–S44 are all answered and live in the
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

---

## S45 — a re-draft repairs S41's missing records and leaves the wrong-labelled ones, undetectably

**Status — accepted and fixed in the tree; it ships as enricher 0.6.4. Your candidate is built, at the
layer that can actually see the condition, and report-and-never-remove is the right call for exactly
the reason you gave.** Reproduced independently before touching anything, and every number matches:
996 → 1,061 against a fresh 1,030, `added=65, already_present=965`, **0 identities missing, 31
extra**, all rsid-only, and **0 of 31** findable by the rsid-also-on-a-coordinate-row predicate.

**You measured the half we said we had not, and the answer was worse than we assumed.** The 0.6.3
entry said published modules "need a re-draft" and left it there. That reads as a complete instruction
and is not one: drafting appends and never mutates, so the re-draft adds the coordinate rows *beside*
the collapsed one. Thank you for taking the sentence literally and checking what it produces — that is
the thing that turns a plausible remediation into a measured one.

**One correction to where the fix goes.** You proposed `append_partial_rows`, on the grounds that it
has both halves at merge time. It has the file, but not the predicate: it is the compiler's generic
drafting helper, shared by every provider, and it knows nothing about rsIDs or ClinVar — teaching it
would put a source's identity rule into the tier that must not hold one. `clinvar_draft` already
computes `ambiguous` and now reads the written file back through `DraftReport.path`, which needs no
new surface and keeps the rule where the source convention lives. The output is what you asked for: a
counted, named, aggregated line beside the rest of the run's warnings.

```
31 row(s) already in variants.csv identify by rsID alone (rs1060500703, rs1553653237, … and 26 more)
— but this run writes those rsIDs with their full coordinate, because each names more than one allele
here. They were most likely drafted before that check was widened (0.6.3), when two ClinVar records
collapsed onto one such row. This run has ADDED the coordinate-keyed rows beside them and has removed
nothing: drafting never deletes an authored row, and yours may have been curated since. Review each
and delete it once its records are covered by the coordinate rows — until then the module carries both
the row and its replacements.
```

**Your doubt about removal is the correct one and we are not overriding it.** A drafted row is
authored material by the time a re-draft runs; a human may have decided its `genotype`, `state` and
`conclusion`, and deleting curated work to repair *our* defect is a trade only the author can make.
Drafting-appends-never-mutates is the rule one file over, and a provider that started deleting rows
would be the exception to it. So: named, counted, never touched.

**Your narrower fallback is also done**, because it stays true whether or not anyone reads a warning:
the 0.6.3 CHANGELOG entry now points forward to this one for what a re-draft does *not* do, and
ENRICHER.md carries the whole finding — the 996/1,030/1,061 measurement, the 0-of-31 detection result,
and the reason `_superseded_rsid_rows` can see what a file-level predicate cannot.

**And your advice to authors is better than ours, so it is now in the reference too.** A fresh
directory reconciled against the old module is the clean remediation; the notice exists for the author
who followed the shorter instruction, which is the one we wrote. Three tests: the mirror pair through
a real stale-then-re-draft cycle, silence on a correctly drafted module (a false positive here would
tell an author to delete correct rows), and your `MLH1` measurement asserted as a relationship — every
fresh identity present after the re-draft, every extra one an rsid-only row the notice counts.

**Nothing filed, and one thing still open on your side.** We have not re-measured the downstream label
errors either — like you, we established only that the rows carrying them survive the remediation.
If a module re-drafted *after* 0.6.4, with its superseded rows deleted, still shows mislabelled
expansions, that is a separate defect and we want it as its own item.
<!-- triaged: 0.6.4 · sha 39bdee3ea387 -->

Reported by **just-module-creator** on 2026-08-19, adopting enricher 0.6.3 (format 0.6.1 / compiler
0.6.1 / registry 0.18.1). This is a corroboration of **S41** aimed at its one open half — you wrote
that already-published artifacts "were drafted under the old predicate and need a re-draft", and
explicitly did not claim to have measured that end to end. We measured it, because our tool surface
wraps `draft_gene_panel` and we had to decide what to tell an author holding a pre-0.6.3 module.

**A re-draft into the existing spec directory recovers every dropped record and leaves the collapsed
rows in place. Nothing in the resulting file distinguishes them.**

**What we ran.** One gene, `MLH1`, `min_review_stars=2`, `max_citations=0`, against the local
`clinvar` snapshot, on installed enricher 0.6.3. Three drafts:

- **A** — drafted with `multi_allelic_rsids` monkeypatched back to the 0.6.2 predicate (grouping on
  `(rsid, chrom, start, ref)`), standing in for a module drafted before the fix.
- **B** — drafted fresh into an empty directory with the 0.6.3 predicate. The ground truth.
- **A again** — re-drafted with the fixed predicate into the same directory, which is the remediation
  an author would actually perform.

**What happened.**

| | rows | distinct identities | rsid-only | coordinate |
|---|---:|---:|---:|---:|
| A, first draft (0.6.2 predicate) | 996 | — | — | — |
| B, fresh draft (0.6.3) | 1,030 | 882 | 703 | 327 |
| A, after re-draft (0.6.3) | 1,061 | 913 | 734 | 327 |

The re-draft reported `added=65, already_present=965`. Against B: **0 identities missing** — every
record S41 was dropping came back — and **31 identities present in A that B does not contain**. Those
31 are the collapsed rsid-only rows: identities the fixed drafter no longer writes, because those
rsIDs now take coordinate identity. 1,061 − 1,030 = 31 exactly, and 913 − 882 = 31 exactly.

**The part that makes it more than an untidy file.** Those 31 rows are the ones carrying S41's
consequence (2) — the surviving rsID whose resolution pairs its authored genotype with both loci and
renders the dropped record's coordinate under the survivor's `clin_sig`, gene and condition. The
re-draft adds the correct coordinate-keyed rows *beside* them rather than replacing them, so after
remediation the module states both the right answer and the wrong one for the same locus.

**And they cannot be found from inside the module.** We checked the obvious predicate — an rsid-only
row whose rsID also appears on a coordinate row — and it finds **0 of 31**: `draft_gene_panel` writes
no `rsid` on a coordinate-identity row (327 coordinate rows in both A and B, none carrying an rsid).
So the stale rows are not distinguishable from legitimate rsid-only rows by any column, and an author
who follows "re-draft" literally ends up with a module that is worse-formed than either the old one or
a fresh one, with nothing to indicate it.

**What we did meanwhile.** Our `draft_from_clinvar` docstring now tells an author holding a pre-0.6.3
module to draft into a **fresh directory** and reconcile against it, rather than re-running the drafter
over the file they have, and says why the second option looks like it works. That is advice, not a
repair; we cannot detect the condition either, for the same reason they cannot.

**A candidate fix, and our doubt about it.** `append_partial_rows` has both halves in hand at merge
time: it knows the rsIDs the current predicate flags, and it can see rsid-only rows already in the file
carrying one of them. Reporting those — a counted, named list on the draft report, alongside
`already_present` — would turn this from undetectable into a line an author can act on, and it needs no
schema change. What we are less sure about is whether it should *remove* them: a drafted row is
authored material by the time a re-draft runs, a human may have curated its `genotype`, `state` and
`conclusion`, and deleting curated work to fix a drafting defect is a trade only the author can make.
So our preference is report-and-name, never touch. The narrower version, if even that is too much, is a
sentence in the S41 CHANGELOG entry saying that a re-draft is additive and does not retract the
collapsed rows — because "needs a re-draft" reads as a complete instruction and it is not one.

**Not asserted.** We measured one gene, and we did not re-measure the downstream label errors
themselves — only that the rows carrying them survive the remediation. The 31/0 split is a count of
identities, not of the 8,231 matchable rows just-dna-lite reported.

**A contrast that sharpens the ask, measured the same afternoon.** We ran the equivalent probe on
`clinpgx_draft` for S44's genotype-gate widening, with a stand-in for the old gate that was
deliberately *broader* than 0.6.2's (12,410 rows drafted where the fix produces 18,895 — so it
declined considerably more than the real one did, which makes it the harder case rather than an
easier one). Re-drafting into the same directory landed on **18,895 rows, 0 stale keys, 0 missing** —
exactly the fresh draft. So "re-draft to pick up a drafter fix" is sound advice in general, and S44
needs no caveat at all.

The difference is that S44 **skipped** rows while S41 **wrote them under an identity that has since
moved**. Only the second leaves anything behind, and it is the case where the file cannot be
inspected to tell. If the report we suggest above is too much machinery for one defect, the cheap
version is to say in the S41 entry which of the two shapes it is — a reader who has just seen S44 in
the same release notes will reasonably assume both remediate the same way, and they do not.
