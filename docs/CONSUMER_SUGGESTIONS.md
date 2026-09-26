# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S120

**Claim ids from here, never from what this file shows.** S1–S119 are all answered and live in the
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

## S120 — the format declares no coordinate-normalization convention, so a legal respelling of an indel is a silent position-join miss ("no one is wrong" is the footgun)

**Status — accepted; filed as
[RM270](ROADMAP.md#rm270--an-indels-artifact-key-is-its-sources-spelling-a-left-aligned-vcf-misses-a-respelled-row-and-the-spelling-independent-id-the-enricher-mints-never-reaches-the-artifact)
(a minor, release undecided). The documentation half shipped: [CONSUMING.md § Identity](CONSUMING.md#identity)
now says indel coordinates are not normalized and tells a consumer to normalize both sides.** No
package change.

Reproduced. All three of your rows sit in our Ensembl snapshot one base right of ClinVar's spelling,
which matches your callers. Against GRCh38 (UCSC `hg38`; Ensembl REST was down during this pass) each
pair gives the same sequence, so these are RM267's harmless +1 class, not its wrong-event −1 class.

**Your option 2 is refused where you placed it, for two reasons.** The compiler has no reference
sequence and is kept that way deliberately (P2). Left-alignment needs flanking sequence, and
COMPILER.md § the VRS verify pass names giving the compiler sequence access as the line not to cross.
And on an *authored* coordinate, rewriting it at compile would move `content_signature` on the first
round trip (P7). The same normalization is legal one tier up. The enricher holds sequence and may
left-normalize the coordinates *it fills* (a fill is outside `content_signature`). For an authored
coordinate like `superhuman`'s, it can report the normalized spelling as a finding but not rewrite it.

**Your option 1 is part of the answer only as a checked verdict.** An authored
`coordinate_normalization` key would be believed without anyone having checked it. A tri-state
verdict the enricher stamps after checking is honest, and RM270 carries it.

**What the probe added.** A key that ignores spelling already exists and is thrown away. The
enricher mints `vrs_id` over the fully justified allele. Both spellings of `rs72613567` mint
`ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7`, and both of `rs77944059` mint one id too. S117's
`rs8176719` pair mints two different ids, so this key also keeps a wrong event apart instead of
hiding it. It lives in `resolution.csv` and never reaches `weights`/`annotations.parquet`, where an
indel is keyed by its source spelling (`16:23635706:G:GT` in `hboc_palb2`). RM270's build is to
left-normalize enricher fills, carry `vrs_id` onto the variant parquets, and stamp the verdict. You did
not ask about `DiplotypeRow`/`RepeatAlleleRow` coordinates, and they were not checked here either.

**What to do now:** keep re-anchoring `superhuman` to left-aligned + parsimony against the FASTA before
compile. That is exactly right, and after RM270 it becomes something the enricher reports instead of
something you have to know about.
<!-- triaged: RM270 filed · sha 6649f7b00bb9 -->

**This sits one level above S117/RM267/RM268.** Those arbitrate a specific defect — the Ensembl snapshot
anchors a class of insertions one base early, and the fix is re-anchoring at build plus an enricher
finding that withholds against a ClinVar/REST second witness. This item is the contract gap they rest
on: **nothing in the schema or manifest states which normalization a module's coordinates are in**, so
even a perfectly-sourced module and a perfectly-sourced VCF can hold two VCF-legal spellings of the same
indel, and the position join misses them with no error, no warning, and every offline gate green. S117
made that concrete for one data source; the point of this item is that the *class* is unbounded as long
as the convention is unstated, and the maintainer's own arbitration of S117 ("ClinVar and REST agree,
Ensembl's dump is one base left") is exactly the kind of judgement that should be a declared convention
rather than settled case by case.

**What I ran (consumer: just-dna-lite, 2026-09-27).** Rebuilt `superhuman` on 0.7; its indel rows are
placed from the Ensembl-cache resolution. Measured against four real GRCh38 genomes: the module places
`rs72613567` at `4:87310241 A>AA`, `rs77944059` at `2:166204471 AAACA>A`, `rs333` (CCR5-Δ32) at
`3:46373453 ACAGT…CCAGA>A`; the callers (GATK/DeepVariant, left-aligned) carry them at `…240 T>TA`,
`…470 GAAAC>G`, `…452 TACAGT…CCAG>T` — one base left. `hf_logic._lead_join_strategy` routes the module
to a position join (it has coordinates), the join requires POS+REF agreement (correctly — that REF check
is what stops indel false-matches), and the rows carry no rsID, so there is no fallback. Real carriers,
silently dropped.

**Why nothing catches it, and why that is the footgun.** Both spellings are legal VCF §1.6.1.4 — VCF
permits multiple representations of one indel and names no canonical position without a normalization
convention. The de-facto standard (`bcftools norm` / `vt`, and what every caller emits) is
left-alignment + parsimony. But the format tier does **parsimony only**: `alleles.parsimony_reduce`
trims shared bases both ends (VCF_4_4_AUDIT.md §9, "Position-1 padding", records this as clean) and there
is no left-aligner and no declared assumption that coordinates arrive left-aligned. So "no one is wrong"
is true and is precisely the problem: it is VCF_4_4_AUDIT.md's own thesis — a legal-on-both-sides
mismatch that is a silent wrong answer at query time — arriving through coordinate spelling rather than
through a field namespace.

**What I did meanwhile.** Held `superhuman` out of our publish set and am re-anchoring its indel
coordinates (and the genotype allele strings) to left-aligned + parsimony against the GRCh38 FASTA in
`v1_port/runner.py` before compile — the build-side re-anchoring S117/RM267 says is the pipeline's job.
That fixes our artifact; it does nothing for the next consumer who resolves the same rsIDs.

**Ask / candidate fixes (either the flag or the compiler-side; the reporter's own preference is the
second).**
1. **A declared convention field** — a manifest (and/or `module_spec.yaml`) key such as
   `coordinate_normalization: left_aligned` (closed vocab: `left_aligned` | `unnormalized` | `unknown`),
   additive and minor. It makes the convention explicit so a consumer/engine can assert its VCF is on the
   same one and **warn on mismatch instead of silently missing**. This is the "left-aligned flag" a
   consumer asked for by name.
2. **Better: the compiler left-normalizes coordinates to that convention and stamps the field**, so the
   burden is not re-derived by every consumer and every rsID-resolving build. This is where a normalizer
   belongs — it needs the reference, which the compiler tier can reach and a bare consumer cannot.
   `parsimony_reduce` already exists; left-alignment is the missing half.
3. **At minimum**, name a single canonical convention in the contract (left-aligned + parsimony) so
   "no one is wrong" becomes "here is the convention; conform, or be flagged." The `−1` class S117 found
   (`G>GC` with no room to shift) shows a naming-only rule is not sufficient alone — it still needs the
   second-witness withhold — but an undeclared convention guarantees the silence continues.

Legality: (1) is an additive optional field, minor. (2) is compiler behaviour over injected coordinates,
no schema change to the authored side. Not checked: whether `DiplotypeRow`/`RepeatAlleleRow` coordinates
(where they exist per VCF_4_4_AUDIT.md §10) would want the same declaration.

---
