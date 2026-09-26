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

## S117 — the Ensembl variation cache spells indel rsIDs at a different anchor from ClinVar for every insertion, and for some it names a different event

**Status — accepted; filed as [RM267](ROADMAP.md#rm267--the-ensembl-snapshot-anchors-a-class-of-insertions-one-base-early-and-resolutioncsv-serves-them-as-a-different-event)
(a minor, release undecided), with a second defect found while reproducing it filed as
[RM268](ROADMAP.md#rm268--the-live-ensembl-rest-rung-writes-an-unanchored-insertion-into-resolutioncsv-ref--at-the-interbase-start)
(a patch).** Nothing has shipped.

Reproduced: `lookup_loci` on our snapshot returns `rs8176719` as `9:133257520 G>GC`, and applied to the
GRCh38 window that is `GGGGCTACC` against ClinVar/dbSNP's `GGGGTCACC`. Your other two −1 examples
reproduce the same way. The snapshot is faithful to its source. Ensembl's own current VCF dump carries
`133257520 G GC`, while Ensembl's **REST** mapping for the same rsID says `start 133257522, end
133257521, -/C`, an insertion between 521 and 522, which anchors at your `521 T>TC`. On the two cited
cases plus five sampled from your −1 class, the dump's POS is REST `end` − 1 every time, and REST `end`
equals ClinVar's POS every time. So this is arbitrated: Ensembl's VCF export anchors a class of
insertions one base left of Ensembl's own interbase point, and ClinVar, REST, gnomAD and your callers
agree with each other.

Nothing here catches it today. The early anchor base is a real genome base, so the reference-allele
check passes it by construction. The rsID↔coordinate check deliberately treats indel position
differences as undecided (RM31). And an rsID-only row gets no coordinate cross-check at all. RM267
sets out why each candidate repair is wrong alone. Your left-normalization fixes only the +1 class,
because `G>GC` after `GGGG` has no room to shift. Re-anchoring at build is `just-dna-pipelines`' job.
The part that fits the enricher is a finding that withholds, using the ClinVar or REST placement as the
second witness and applying both spellings to the window the way you did.

RM268 is the live fallback for rsIDs the snapshot misses. It writes REST's spelling straight into
`resolution.csv`, so `rs8176719` through that rung becomes `9:133257522 ref='-' alts='C'`, and the
table accepts it.

**What to do now:** keep what you have. Author ABO's indels at the left-normalized position with the
`record_override` naming the cache value, and keep the ±10 bp respelling tolerance labelled as a
tolerance. For any rsID-authored insertion, do not trust a snapshot-resolved coordinate until RM267
lands.
<!-- triaged: RM267 RM268 filed · sha bc9d8aadc361 -->

*From just-dna-lite, 2026-09-27, while authoring an ABO blood-group phenotype module.*

**What we ran.** `lookup_variant(rsid="rs8176719")` (ABO c.261delG, the O1 marker) returned
`9:133257520 G>GC`. dbSNP, gnomAD and both of our callsets that carry it (one DRAGEN, one DeepVariant) place it at
`9:133257521 T>TC`. GRCh38 reads `…GGGG T ACC…` at 517–524, so the two are **not** one event
respelled: inserting C after the G gives `GGGGCTACC`, after the T gives `GGGGTCACC`. gnomAD records
`520 G>GC` separately at AF ~6e-7, while the cache row carries MAF 0.34 — the common variant, placed
one base early. A module that resolves rs8176719 through `resolution.csv` matches no real sample.

**Measured corpus-wide**, joining the Ensembl cache (`ensembl_variations/data/*.parquet`) to the
ClinVar snapshot (`clinvar/data/*.parquet`) on rsID, over ClinVar's length-changing alleles:

| | ClinVar alleles | same `(start, ref, alt)` | same event by `parsimony_reduce`, other anchor | no matching event |
|---|---|---|---|---|
| insertions | 57,742 | **0** | 56,696 | 1,046 |
| deletions | 108,685 | 25,745 | 82,317 | 623 |

The respelled ones split by offset (Ensembl start − ClinVar start): insertions +1: 50,882, −1: 5,788;
deletions +1: 80,157, −1: 2,111. We applied both spellings to the reference (Ensembl REST sequence)
for samples of each:

- **+1 is harmless respelling**: 7/7 sampled produce the identical haplotype. The cache spells an
  indel one base right of VCF left-normalization (`C>CT` at 38343142 becomes `T>TT` at 38343143 in a
  T run).
- **−1 is mostly a different event**: 23 of 30 sampled insertions (chr1, 2, 7, 11, 17, 19) produce a
  different haplotype, e.g. rs546596010 ClinVar `2:26455249 T>TA` vs cache `26455248 C>CA`,
  rs1553364018 `1:224434032 C>CT` vs `224434031 G>GT`. Extrapolated, a few thousand insertion rsIDs.
  We did not arbitrate which side is right beyond rs8176719, where reads-based callers and gnomAD agree
  with ClinVar.

**Why it matters to a consumer.** `parsimony_reduce` alone cannot tell the two classes apart (it drops
position), so a consumer tolerant of respelling cannot also refuse a real misplacement without sequence
access, which is enricher-side. And even the harmless +1 class means an rsID-authored indel resolved
through the cache never meets a left-normalized VCF record in a position join.

**What we did meanwhile.** The pilot authors both ABO indels at the left-normalized position, checked
against the reference sequence, with `record_override` naming the cache value. Our phenotype caller
matches an indel respelled within ±10 bp when exactly one record in the window reduces to the same
event, and refuses (and never restores to hom-ref) when two do. That is a tolerance, not a check, and
it is labelled as such in the report.

**Candidate fix, and an argument against it.** Left-normalize at cache build (or in `resolve_variants`)
against the reference the enricher already holds, so `resolution.csv` carries VCF spellings. That fixes
the +1 class outright. It does not fix the −1 class, which is a placement disagreement, not a spelling
one — there the enricher could flag rather than choose, since it can apply both spellings to the
sequence the way we did.

## S118 — a haplotype carries `ref` at any defining site it does not list, and nothing in the format says so

**Status — documentation defect, fixed in [TABLES.md § haplotypes.csv](TABLES.md#haplotypescsv); the
validate warning is declined.** Nothing to install: it is a doc and a code comment.

Confirmed in the code, not just in your reading of it. `_cross_validate_phase_ambiguity` already says
*"a haplotype that does not mention a variant is treated as carrying the reference there"* and
normalizes a row whose `allele` equals its `ref` to the same sentinel. So your caller and the compiler
agree, and the gap was only that TABLES.md never said it. It now does, closed-world per module: the
sites are the ones some haplotype of the gene in this module lists, and "unknown at a site" has no
spelling.

**On `*1`, the answer is that it is a CYP convention, and the format only exempts the name.** The
used-but-not-defined warning skips the literal `*1` for every gene, and that is all. Nothing infers a
definition. A diplotype naming an undefined `*1` is skipped by the phase check, not read as
all-reference. Probed: renaming `hfe_compound_het`'s `wt` to `*1` validates, and the phase warning
then names `*1/C282Y-H63D`, so a *defined* `*1` is an ordinary haplotype. The comment on
`_REFERENCE_HAPLOTYPE` claimed `*1` "can never appear in `haplotypes.csv`", which is false, and it is
corrected. TABLES.md now says a gene whose reference has another name (NAT2's `*4`, your blood-group
`wt`) defines it with reference-matching rows, as your pilots already do.

**Why no warning on differing site sets.** Sparse is the norm this rule exists for. Two of the four
reference examples with `haplotypes.csv` (the CPIC-drafted `cyp2c19_star_alleles` and
`cyp2c9_warfarin_grch37`) list different site sets per haplotype, as every CPIC draft does. The
warning would fire on each of them while catching an author who means "unknown", and that author has no
row to write either way.

**What to do now:** nothing changes on your side. Keep listing every allele at every site if you like.
It is redundant under the rule but not wrong.
<!-- triaged: doc fix · sha 52d96d1ab43f -->

*From just-dna-lite, 2026-09-27.*

Our diplotype caller (and, as far as we can tell, the compiler's own phase-ambiguity check) assumes the
PharmVar/CPIC reading: a haplotype that lists no row at a site the gene's other haplotypes define
carries the reference allele there. TABLES.md never states it. It decides results: remove the
reference-matching rows from `hfe_compound_het`'s `H63D` haplotype and the caller's answer is unchanged
only because of this assumption; a consumer reading "unlisted" as "unknown" would turn every such site
into a wildcard and call far more `ambiguous`.

The corpus avoids the question by listing every allele at every site (`apoe_epsilon`, `hfe_compound_het`
and our ABO/FUT2 pilots all do), so it has never been tested. Two ways out, either fine by us: state the
convention in TABLES.md under `haplotypes.csv` (one sentence), or have `validate` warn when haplotypes
of one gene list different site sets, so an author who means "unknown" finds out. The same sentence
would settle the related `*1` question: `*1` is the one implicit allele the format allows, and a
consumer cannot tell whether "`*1` = reference at every site" is the rule or a CYP convention.

## S119 — `DiplotypeRow.haplotype_b` is required, so a hemizygous call has no spelling; plus one more cross-gene case for RM28

**Status — note 1 accepted and filed for 1.0 as
[RM269](ROADMAP_1_0.md#rm269--diplotyperowhaplotype_b-is-required-so-a-hemizygous-star-allele-call-has-no-row);
note 2 recorded in [RM28's corpus](ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half).** Nothing
shipped.

**Note 1.** Confirmed: `haplotype_b` has been required since 0.4.0. Making it nullable is the right
shape, but it demotes a required field, which the charter (P8) allows only at a major. So RM269 is
filed against 1.0, with the empty value meaning "no second copy", distinct from unknown. Your source
already writes this case. CPIC's own diplotype table spells 187 G6PD rows as a single haplotype with
no `/`. RM269 records why the in-line alternatives are worse. One of them is legal today and is a trap:
a sentinel in `haplotype_b` is accepted (`-` is even sorted into `haplotype_a` by canonicalization,
and `none` is accepted as an allele name), and no reader can tell it from a real allele. **Please do
not ship one.** Reading a haploid contig as `no_match`, as your caller does, is the honest answer
until 1.0.

**Note 2.** Lewis is in the RM28 corpus beside S102's six CPIC gene pairs. It is the same
subject-pairing shape outside pharmacogenomics, keyed on two genes' *phenotypes*, and it enumerates.
So it argues for a two-subject key, not a predicate, and it is recorded as unbuilt.

**What to do now:** nothing new. Keep FUT2 as its own module and Lewis out, as you have.
<!-- triaged: RM269 filed · sha 829617f9c975 -->

*From just-dna-lite, 2026-09-27.*

1. **Hemizygous diplotypes.** The 0.4 widening gave `variants.csv` a single-allele genotype for
   hemizygous calls, but `DiplotypeRow.haplotype_b` is still `required=True`. An X-linked star-allele
   phenotype (G6PD in males is the common one) therefore cannot be enumerated: a male `B`/— has no row.
   Our caller is diploid today and says so, reading a haploid contig as `no_match`, so nothing is being
   silently miscalled — but the module could not state the answer even if we read it. A nullable
   `haplotype_b` meaning "no second copy" (distinct from "unknown") would be enough on our side.
2. **Lewis (FUT3 × FUT2)** for the RM28 corpus. S102 already counted the CPIC pair-keyed drugs; Lewis
   is the blood-group instance: Le(a−b+) / Le(a+b−) / Le(a−b−) is a function of the FUT3 phenotype and
   the FUT2 secretor phenotype, not of either gene's diplotype. We shipped FUT2 secretor status as its
   own module and left Lewis out for exactly this reason. The enumerative answer we would reach for is a
   table keyed on the two per-gene *phenotypes*; we have not built it.
