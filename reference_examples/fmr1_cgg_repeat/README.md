# `fmr1_cgg_repeat` — the first module in the corpus where a threshold cites its paper

**What this probes:** *RM47's fix, which had no worked instance anywhere.* S19 found that a bin
boundary is the most interpretive claim the format carries and had nowhere to cite; 0.6 gave
`MeasureBinRow` a `pmid` and relaxed `StudyRow`'s subject requirement to nothing. Then the corpus
kept exactly one binning module — `htt_repeat_expansion` — which stays **deliberately uncited** as
the example of the gap. So the column shipped and no module used it.

FMR1's CGG tract is the natural case: four published boundaries (≤44 normal, 45–54 intermediate,
55–200 premutation, >200 full mutation), all from one ACMG technical standard, and a gene on **chrX**,
where a male sample is hemizygous and the repeat field carries one value rather than two.

## What it broke

### 1 — `largest`'s meaning sentence assumes a ploidy this contig does not have

> **Fixed** (D5-1). The illustration is gone; the rule keeps the reference-inclusion clause two tests pin. The sentence quoted below is the pre-fix text, kept as the evidence of what was found.

`vocab.ELEMENT_RULE_MEANINGS`, printed by `just-dna-compiler reference` under `vocabulary_notes`:

> **largest** — the greatest of the values the field carries for this record, the reference element
> included where the field has one (Number=R). This is the rule a dominant repeat expansion wants:
> **the longer of the sample's two alleles**, whichever of them happens to be reference-length

The *rule* is fine: "the greatest of the values the field carries" is well-defined for one value, and
`largest` is exactly right for a hemizygous FMR1 call. The *explanation* is a claim about a diploid
record, and this module is the one where it is false — a male sample's `REPCN` carries one number,
and fragile X in males is the presentation the whole gene is known for.

These descriptions are the authoring contract rather than internal commentary — that is the lesson
the 0-vs-1-based `start` docstring cost 3,038 rows to learn — so an author on a hemizygous locus
reads this and reasonably concludes the rule is not for them. Every other member's sentence is
written in terms of *elements the field carries*; only `largest` reaches for an illustration, and the
illustration is where the ploidy assumption entered.

### 2 — RM63's correction is a code comment, and the pipe form is not in the printed contract at all

> **Fixed** (D5-2), with one correction to the finding itself. Both `genotype` descriptions now name all three shapes the validator accepts and carry RM63's reading of the pipe — except the zygosity word, which turned out to be false: `C|C` loads, and `1|1` is an ordinary phased homozygous call. RM63's own comment in `base.py` still carries that overclaim and is filed as R2-14.

`just-dna-compiler describe variants.csv` gives `genotype` as:

> Slash-separated sorted alleles, e.g. A/G. An allele is bases, or a symbolic/structural allele
> carrying its length — a heterozygous deletion sorts as `<DEL:1500>/A`

No mention of `A|G`. The validator accepts it — its own *error* message says so, listing "two
pipe-separated phased alleles (A|G)" — and `phased` is materialized into `weights.parquet` and
re-emitted by reverse. So the pipe form is a supported, round-tripped part of the authored grammar
that the generated authoring reference does not describe.

RM63's correction lands one layer further in. It reads, in `base.py`:

> Read a pipe here as **heterozygous, phase recorded but unaddressable** … an authored `A|G` and an
> authored `G|A` are distinguishable to us and indistinguishable to any consumer, and two rows both
> written `A|G` assert nothing about being in cis.

That is the sentence an author needs before writing a pipe, and it is a comment above the validator.
Nothing prints it. The finding RM63 filed was that the *old* comment overclaimed; the corrected
version is now accurate and unreachable, which is the same defect one step along — an author cannot
overclaim from a document they cannot read, but they can overclaim from the silence.

## What was probed and held

- **RM47's fix works end to end, and its same-release obligation holds in both directions.** Every
  boundary here carries `pmid: 23099194`, so `_check_binning_grounding` is silent — the module
  grounds what it states. Stripped to a bin-only citation (no `studies.csv` at all),
  `just-dna-enricher literature` still fetched the PMID and wrote a `literature.csv` row for it, and
  the compiler did **not** report that row as a stale orphan. Both call sites see the bin pointers,
  which is the thing the item was filed to guarantee. A genuinely uncited row *is* reported
  (`literature.csv describes 1 citation(s) no study in this module cites: ['99999999']`), so the
  check was not simply widened into silence.
- **RM47's subject relaxation.** `studies.csv` here names no variant at all — legal only since 0.6 —
  because the ACMG standard is about the thresholds rather than about a locus a study row could point
  at. It loads, validates and materializes, and the orphan half of `_cross_validate_studies` skips a
  subject-less row rather than reporting it as referencing something missing.
- **RM55 on the repeat half, with the right field.** The warning names **`RUC`** and cites VCF 4.4 §3
  typing it as a Float — not the `CN` reasoning `copynumbers.csv` gets. The FMR1 bins tile the
  integers cleanly and nothing looks wrong, which is precisely why 0.6 made this loud.
- **RM56 on a 10-wide window.** The intermediate zone is 45–54, and a call with a ±5 confidence
  interval spans two thresholds. The warning fires once for the table, names `CIRUC`, and says a
  conforming consumer withholds rather than picking — identical geometry and identical behaviour to
  HTT's, on a different gene.
- **The round trip** is a fixed point on `artifact.digest` (`a5258209…`) and `content_signature`
  (`3969ba06…`), with the bin `pmid`s and the subject-less study row surviving.

## RM66 — the gating evidence, not a finding

`repeat_alleles.csv` is keyed `(gene, repeat_unit)`, which binds one count to one motif. FMR1's
expansion risk depends on the **AGG interruption pattern** inside the CGG tract: a premutation of the
same length is far more stable with two AGGs than with none, and a caller reporting `RUS=CGG,AGG,CGG`
is describing exactly that structure. The module cannot say it — the pure-CGG tract and the total are
different numbers and there is one key for them. `studies.csv` carries the citation for the effect
(Nolin 2015) so the module records what it cannot express, and the gap is filed as RM66's evidence
rather than as a defect.
