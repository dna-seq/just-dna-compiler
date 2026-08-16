# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S33

**Claim ids from here, never from what this file shows.** S1–S29 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
.claude/triage-state.sh --next        # scans this file AND the history file
```

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## S30 — the 0.4 families store a genotype string, `weights` stores a list

**Status — accepted, split in two: the shared leaf shipped in 0.6.0, the artifact half is
[RM81](ROADMAP_1_0.md#rm81--one-artifact-spells-a-genotype-two-ways) and needs the major.** You asked
for the public leaf as a fallback and it is the better half of the request, so it is what shipped:
`just_dna_format.alleles.split_genotype` — format tier, stdlib, the `parsimony_reduce` precedent for
"the pure rule lives in the format and every reader calls it". Its contract is *a validated genotype
cell in, alleles in authored order out*, and the docstring says **never sorted** with your reason, not
a semantic one.

Reproduced, and it was worse than reported: there were **three** copies of that regex, not two.
`compiler._split_genotype` was one, `resolution.py` had its own for the hosting predicate, and yours
was the third. Both of ours now call the leaf, and a test asserts they are the same object — two
implementations that agree today do not fail when they drift, they stop matching, which is exactly the
failure you describe. Your deciding argument is pinned as
`split_genotype("G|A") == ["G","A"] != split_genotype("A|G")`, so a future edit that sorts breaks our
build rather than your match set. You were right to land on not sorting, and right about why: whatever
RM63 settles about what a pipe *means*, the compiler does not sort, so a reader that does is the one
introducing the second spelling.

**The narrower half is real and does not fit in a minor.** Splitting `pharm_variants.parquet.genotype`
is a **retype of a published column** — P3/P8 make that major-only precisely because it breaks a reader,
and you are that reader. RM43 is not a precedent for it: those were stamped columns that did not exist
before, which is the additive case. The tempting minor-legal repair — a parallel `genotype_alleles`
list column beside the string — is refused in the item, because it puts two spellings of one value in
one table (the desync shape `ResolutionRow.vrs_id` needed two guards for) and leaves the original
defect in place with a third spelling on top. So RM81 records the two candidate unifications (split
everywhere, or verbatim everywhere and every reader calls the leaf) and the argument each way; the
`reverse_module` cost you did not have to consider is written down there.

Nothing to do on your side: your normalization stays correct, and `split_genotype` is available to
replace it whenever you take a 0.6 dependency.
<!-- triaged: 0.6.0 -->

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, same round as S29.

**What we ran.** Annotating a real WGS VCF with our `pharm_variants`-led `pharmgkb` module, joining on
`(rsid, genotype)`.

**What happened.**

```
SchemaError: datatypes of join keys don't match - `genotype`: list[str] on left
does not match `genotype`: str on right (and no other type was available to cast to)
```

`weights.parquet` splits `VariantRow.genotype` into `List(Utf8)`; `pharm_variants.parquet` is
materialized verbatim from its authored CSV and keeps the string (`"C/C"`). Both are documented and
neither is wrong, but a consumer joining either family to the same VCF meets two representations of one
concept, and the split is invisible until the join raises.

**What we did meanwhile.** Normalize the lead table's genotype to `List(Utf8)` before any join, mirroring
`just_dna_compiler.compiler._split_genotype`: split on `/` or `|`, drop empty fragments, **do not sort**.
After that `pharmgkb` annotates 63 and 45 rows on our two rsID-bearing samples rather than aborting the
run. Cheap, and we are not asking for it to be undone.

**Why we are reporting it anyway — we got it wrong twice, in opposite directions, from the prose.** Our
first version sorted the alleles, reasoning that with no phase-set column the order names no homolog. We
then reverted that after reading `AuthoredModel._validate_genotype`, which says phase encodes which
allele sits on which homolog. Re-reading PROPOSAL_0_6, **RM63 says that docstring claims more than the
format supports** and is being corrected to "phase recorded but unaddressable" — so our first reasoning
was closer to the truth than the docstring we abandoned it for. Neither round involved a failing run: no
module in our corpus carries a phased genotype, so nothing we could execute would have told us either
way.

We landed on **not sorting**, and the point of this report is that the deciding argument turned out not
to be the semantic one at all. Whichever way RM63 settles what a pipe *means*, the compiler's
`_split_genotype` does not sort, so `weights.parquet` holds authored order; a consumer that sorts the
0.4 families gives one artifact two spellings of a genotype and matches a phased row that a weights-led
module would not. Self-consistency decides it, and that is stable under RM63. The semantics we spent two
rounds on decide nothing here.

So the rule lives in three places that must agree — the validator's grammar, `_split_genotype`, and
every consumer that touches a 0.4 table — and the third is a re-derivation from prose that is currently
mid-correction. `_split_genotype` is private, so reimplementing it was the only route; a consumer that
reimplements it slightly wrong gets no error, just a quietly larger match set on phased data. A shared
public leaf — the genotype counterpart to `derive.direction_from_state`, the precedent for "the pure
rule lives in the format and every reader calls it" — would remove the class. Failing that, exporting
`_split_genotype` under a public name would do.

The narrower half is still worth fixing on its own: `weights.parquet` gets the split and the 0.4
families do not, so two tables in one artifact disagree about how a genotype is spelled. RM43 already
stamps `variant_key`/`authored_ident` onto `pharm_variants`, `haplotypes` and `heteroplasmy` in 0.6 —
splitting `genotype` on the same pass would make the whole artifact self-consistent.

## S31 — RM43 is built and unreleased, so a `pharm_variants` module still ships zero coordinates, and on an rsID-less genome that is zero annotations

**Status — the field you guessed at did not exist and now does: `manifest.compilation.positional_rows`
/ `positional_rows_placed`, shipped in 0.6.0.** You were right that `resolution_subjects` looks
adjacent and right that it is not the answer — it counts `variants.csv`, which your module has none
of. RM44's own entry recorded that the *positional* count "belongs with RM43", and RM43 then shipped
the fill without it, so until this the only published record of whether a PGx table joins to a VCF was
the warning sentence your registry substring-matches. Two counts, parts not a ratio, the
`vrs_alleles`/`vrs_alleles_identified` shape: complete is `positional_rows_placed == positional_rows`.
`pgx_slco1b1_simvastatin` now reports 9 of 9 while its `fully_resolved: true` still quantifies over
zero variant rows, which is the pair of readings a catalog needs side by side.

**The era question has a definite answer, and it is the reason both fields are nullable rather than
`0`.** `None` means *this compiler did not count*, which is exactly what every pre-0.6 manifest
honestly is; `0` means the module carries no positional table. Defaulting to `0` would have your 0.5
artifact report "no positional rows" while its parquet holds 1,482 — the vacuous-`fully_resolved`
failure re-made inside the field written to close it, so a test pins the distinction. Alongside that,
`compiler_version` is the discriminator that exists in manifests already published. COMPILER.md's
resolution section now carries the read-side rule, including the part that outlasts the release: a
published artifact does not move when a consumer installs 0.6, only when its maintainer recompiles
**and** republishes.

`UNJOINABLE_PHRASE` and its test **stay**, and the comment claiming RM44 would retire them is
corrected rather than deleted: manifests already on `just-dna-seq/annotators` carry neither new field,
so for those the sentence is still the whole record. Retiring it is a decision for after the corpus is
recompiled, not a consequence of the field existing.

The rest is outside the format and stays there. Republishing the corpus is a maintainer action we do
not control from here, and `trusted: false` is your registry's rendering of a true fact — the
counts give it something better to render than a warning's prose, but what a badge *says* is a
consumer contract (RM7). Your own bug — distinguishing "we could not test you" from "you carry none of
these" — reads right to us, and it is the same tri-state discipline this repo applies everywhere: an
unasked question is never a negative answer.
<!-- triaged: 0.6.0 -->

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, same round as S30 — the same module and
the same run, one layer down. **We know RM43 shipped this in the 0.6 tree**; this is the field cost of
it not being installable yet, plus one consequence we do not think RM43 alone closes.

**What we ran.** `annotate_and_report_job` over Anton Kulaga's public genome (Zenodo 18370498, CC-Zero,
DeepVariant 1.1.0, GRCh38, variant-only), 4,257,537 records after quality filtering, against all twelve
modules we discover — `pharmgkb` among them.

**What happened.** `pharmgkb` annotated **0 rows**, and the report told the reader "No annotated
variants found for this module."

The artifact we published under 0.5:

```
pharm_variants.parquet   1,482 rows, 147 distinct rsids
  chrom  null on 1,482 / 1,482
  start  null on 1,482 / 1,482
  ref    null on 1,482 / 1,482

resolution.csv           147 rows, status=resolved on 147 / 147
  rs1042713 → 5 / 148826877 / G / A,C  (+ two VRS ids)
```

So the compiler held a complete, resolved coordinate for **1,482 of 1,482 rows** and emitted an artifact
with none of them. That is RM43 exactly, and we are not re-reporting it as a defect — we are reporting
what it costs downstream, because the number is larger than "joins on rsid instead of position"
suggests.

**The part that is not just slower.** Our engine detects the null coordinates and downgrades the join
to `(rsid, genotype)`, which is the right fallback and works on our two rsID-bearing samples (63 and 45
rows, per S30). But this genome carries **0 rsIDs across all 4,257,537 records** — DeepVariant writes
`.` in `ID`, and so do most callers we see. So the fallback has nothing to key on, and a module whose
every row the compiler could place annotates nothing at all on a fully sequenced genome. Position was
not a faster route to the same answer here; it was the only route.

**What we did meanwhile.** Detect the all-null-coordinate case, downgrade to rsid, and — separately —
detect that the VCF carries no rsIDs at all and record *that* as the reason, so "we could not test you"
is distinguishable from "you carry none of these". The second half is ours to render and we had not
been rendering it; that part is our bug, now filed on our side.

**Why we are writing it up rather than just waiting for 0.6.** Two things outlast the release:

1. **The published corpus does not move when the compiler does.** Every module on
   `just-dna-seq/annotators` was compiled under 0.5, so a consumer installing 0.6 still meets
   coordinate-less `pharm_variants` artifacts until each one is recompiled *and* republished — two
   maintainer actions, in our case gated on a namespace token. A consumer cannot tell from the artifact
   which era it is holding except by looking for the nulls. If `manifest` already distinguishes this
   (we may simply be missing the field — RM44's `resolution_subjects` looks adjacent), a pointer in
   COMPILER.md's read-side section would save the next consumer the probe.

2. **`trusted: false` is the right verdict and an unhelpful one.** Registry 0.11.3 reads the 0.5.3
   unjoinability warning and publishes `pharmgkb` as `trusted: false`, which is correct. But the flag
   reads as a quality judgement on the curation, when the curation is fine and the artifact is merely
   missing a mechanical fill the compiler had in hand. Post-RM43 that resolves itself; pre-RM43 it means
   our best-curated PGx module is the one flagged least trustworthy.

**One argument against our own framing.** "Weld the coordinate in at compile time" is what P7 forbids
in general — `reverse_module` would read a materialized coordinate back as authored. RM43's answer
(stamped, `Field(exclude=True)`, rebuild the lookup from the positional parquets on reverse) is a
better shape than the one we would have proposed, and the `content_signature` consequence it documents
is a cost we had not considered. We raise the corpus half only because it survives the fix.

## S32 — hom-ref rows are correct data that our callset cannot supply, and we nearly filed them as dead weight

Reported from **just-dna-lite** (consuming 0.5.4), 2026-08-16, same run as S31.

**What we ran.** The same twelve-module annotation of the same variant-only WGS genome.

**What happened.** `lactose_tolerance` — a small module of ours, 6 rows over 2 sites — matched **0
rows**, and the report said "No annotated variants found for this module."

It authors, for rs4988235 (2:135851076, `ref=G`, `alt=A`):

| genotype | weight | state | conclusion |
|---|---|---|---|
| `A/A` | 1.2 | protective | lactase persistence |
| `A/G` | 1.0 | protective | lactase persistence, dominant |
| **`G/G`** | **0.0** | **neutral** | **adult-type hypolactasia — possible lactose intolerance** |

There is **no record at 2:135851076 in the VCF at all**. Nearest calls are 180 bp before (135850896,
DP 22) and 1,576 bp after. A variant-only callset emits nothing where the sample matches the reference,
so the subject is almost certainly `G/G` — the module's own third row, the most common result worldwide
and the one a reader asking about lactose came for — and the pipeline is structurally unable to say so.

**It is not one small module.** Counting rows whose `genotype` equals `[ref, ref]`, straight out of
`weights.parquet`:

| module | hom-ref rows | of total |
|---|---:|---:|
| `pathogenic` | 2,727 | 617,001 |
| `cancer` | 1,296 | 139,254 |
| `cardio` | 539 | 115,060 |
| `longevitymap` | **193** | **1,039 (19%)** |
| `coronary` / `lipidmetabolism` / `vo2max` / `thrombophilia` | 27 / 15 / 13 / 8 | **one row in three** |

The four hand-curated modules author all three genotypes at every site.

**But "unreachable" is the wrong word, and getting it wrong is the point of this report.** Whether a
hom-ref row can match is a property of the *callset*, not of the module and not of the format:

| callset | hom-ref row |
|---|---|
| variant-only VCF (this run) | no record at the site — needs restoration |
| gVCF with reference blocks | **record exists, matches today** |
| microarray / direct-to-consumer | every probed site is genotyped, hom-ref included — **matches today** |
| joint-called cohort VCF | site present iff *someone* varied — partially reachable, and which part is not a fact about this sample |

The gVCF row is not a hypothetical. Thirteen `GT=0/0` records survive our own quality filter on this
genome, and `_compute_genotype_expr` turns every one of them into exactly `[ref, ref]`:

```
1  106517189  CATAT  C  0/0  ["CATAT","CATAT"]  PASS
2  36033272   A      G  0/0  ["A","A"]          PASS
```

13 of 13. So the join mechanism already works end to end; what hid it on this genome is one line of our
own config (`pass_filters: ["PASS","."]`, which drops `FILTER=RefCall`), plus the fact that this
particular file is variant-only. We had written those rows off as dead weight in the artifact. They are
not — they are the rows that make a module work on array data, which is the input we have not shipped
support for yet and which every Gen-I consumer had.

**What we did meanwhile.** Nothing, deliberately. We can classify these rows today — `ref` is in
`weights.parquet`, so `genotype == [ref, ref]` is a one-line predicate, and that is exactly how the
table above was computed. What we cannot do is act on it, for a reason we think is the real content of
this report: **absence is not hom-ref.** It is hom-ref *or* uncovered, and a variant-only VCF cannot
tell them apart. Restoring blindly would report "you are lactase non-persistent" to someone whose MCM6
enhancer was never sequenced, which is the manufactured-reassurance failure ROADMAP_0_7 names as the
worst this format has.

`requires_callable` / `callable_from` (RM6) are precisely the missing half, and they are **unpopulated
on every module in our corpus** — so nothing is lost by our engine not honouring them yet, and nothing
is gained either.

**A worked precedent, because we already solved the adjacent problem next door.** `just-prs` (0.7.7,
same authors, shared workspace) hit this as *"a scoring variant absent from the callset is hom-ref
there"* and shipped `just_prs.reference_allele`. Four properties look transferable:

1. **Two tiers, ranked by authority.** The reference panel's `.pvar` first (a real `REF`, indels
   included), then a single-base faidx lookup against the Ensembl primary assembly for the tail.
2. **A tri-state provenance column, not a boolean.** `ref_source ∈ {panel, fasta, unresolved}`. An
   unresolved position stays unresolved and is never guessed.
3. **A refusal that is the interesting part.** The FASTA tier is gated to SNVs: *"an absent variant
   gives no REF length, so multi-base / indel positions are left `unresolved` rather than
   mis-represented by one base."* Exactly the discipline the ref-agreement rule already needs.
4. **Resolve once, offline; the runtime reads a table.** The output is a precomputed
   `reference_allele_universe_{build}.parquet` of `(genome_build, chrom, pos, ref, ref_source)`, pushed
   to HuggingFace. `compute_prs` then imputes hom-ref for an absent variant **only when the scoring file
   carries a `reference_allele`** — the fact travels with the data, the policy stays with the engine.

**Where the analogy holds and where it does not.** PRS needs a *universe* because genome-wide scoring
files routinely omit `reference_allele` — the fact is missing and must be fetched. A module is the
easier case: `resolution.csv` resolves the reference allele at enrich time and the compiler already
writes it into `weights.parquet`, so **for a weights-led module the fact is in the artifact today**. A
module's site set is also tiny — 520 sites for `longevitymap`, 2 for `lactose_tolerance` — so if
anything were needed it would be kilobytes welded in, never a download.

So we are **not** asking for a per-module reference universe, and we are **not** asking the format to
say which rows are reachable — that is ours, and it is a different answer for every file a user
uploads. A module cannot know it and should not carry it. Two narrower things, ranked:

1. **A compiler warning when a site authors hom-ref, or omits hom-alt.** Independent of everything
   above and cheap. The same probe found `longevitymap` authors **no hom-alt genotype at 208 of its 520
   sites (40%)** — this subject is homozygous at 74 of them and every one is silently unreported. That
   is our curation defect, and no tool told us; a warning at the same tier as the 0.5.3 unjoinability
   one would have. Note this warning needs no notion of reachability: it fires on what the author
   wrote, which is the only thing the compiler can see.
2. **`requires_callable` populated somewhere real, to try the round trip against.** We would rather
   implement restoration against one module that states its callability requirement than infer a policy
   from an empty column. `pgx_slco1b1_simvastatin` or a reference example would do.

**And one thing that *is* a module property, which we had been reaching for from the wrong end.** A
module authoring hom-ref rows is making a static claim — *"evaluate me against a callset that can
express the reference genotype"* — and today that claim exists only as an inference a consumer may or
may not draw from the row shape. `lactose_tolerance` is unusable on a variant-only VCF and correct on an
array; nothing in the artifact says so, and the difference is not visible until a user gets an empty
report. That is close to what `requires_callable` encodes per row, one level up and about the callset
rather than the region. We are not proposing a column for it — we have one module's evidence and P3 says
that is not enough to fix a shape against — but it is the question we think sits under this report, and
we would rather name it than have it arrive later as a second suggestion.

**The longer shot, filed as clearly separate.** Beyond restoration there is *imputation* — reporting a
genotype from population frequency where callability is genuinely unknown — and `just-prs` has an
`ancestry` package that would make it population-specific. We think this is a different kind of claim
and should not ride along: restoration is deterministic given callability evidence, imputation is not,
and mixing them into one column would put a probabilistic call behind the same rendering as a
sequenced one. Recording it here only so the ordering is on the record.

**For the 0.4 families this is blocked behind S31.** `pharm_variants` carries no `ref` at all pre-RM43,
so a consumer cannot even classify the rows. RM43's fill unblocks the classification; the callability
half is unchanged by it.

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
