# `cyp2d6_structural` — the two binning kinds no module had ever carried

**What this probes:** *`copynumbers.csv` and `activity_phenotype.csv`, which the corpus had zero
instances of.* Both shipped before 0.6, both are load-bearing for RM55 and RM56, and both were
exercised only by inline fixtures. CYP2D6 is the gene that motivates them: it is deleted (`*5`),
duplicated (`*1x2`), and multiplied, and CPIC's phenotype call is a function of a score summed over
the two haplotypes rather than of any single variant.

Every bin here is CPIC's own — `diplotypes.parquet` from the published snapshot, probed rather than
recalled: Poor Metabolizer at 0, Intermediate 0.25–1.0, Normal 1.25–2.25, Ultrarapid from 2.5.

## What it broke

### 1 — the lengthless-symbolic-allele message names `<DEL>` whatever was authored

```
$ # variants.csv carrying alts=<DUP:TANDEM>
warning: variants.csv: 1 row(s) carry a symbolic allele with no usable length. A <DEL> that does not
say how long it is cannot be sized … e.g. 22:42126499:N:<DUP:TANDEM> alts='<DUP:TANDEM>'
```

The verdict is right — `<DUP:TANDEM>` carries a subtype and no length, and RM5 put the length in the
token — but the sentence explaining it quotes an allele type the author did not write. The example
clause names the real cell, so the two halves of one message disagree about what is being discussed.
Small, and squarely in the class this workspace treats as a defect elsewhere: a diagnosis that names
the wrong thing sends the reader looking for a `<DEL>` they do not have.

### 2 — RM67's refusal does not make the documented divergence findable

CYP2D6 with a duplication carrying SNVs is the *spec's own* polyploid example, and it is the module
where an author meets it:

```
error: variants.csv line 5 [genotype]: Value error, genotype must be a single allele (hemizygous,
e.g. A), two sorted slash-separated alleles (A/G), or two pipe-separated phased alleles (A|G),
got: 'A/A/G'
```

The rule is stated and the *divergence* is not. VCF permits higher ploidy; this format deliberately
does not, and RM67 records that as a decision with reasons. Nothing in the message says so, so an
author holding a real triploid call reads it as "I typed it wrong" and has no route to the reasoning.
Every other deliberate refusal in this codebase names its own limit in-line — RM5's lengthless
message says the grammar could widen and a release away, the ploidy check says which contigs, the VRS
coverage warnings name RM15. This one reads like a syntax error.

## What was probed and held

- **RM55 fires on `copy_number`, loudly and once.** It names the field it read (`CN`), cites VCF 4.4
  §7.2 and §5.6, gives the concrete failure (`[0,0] [1,1] [2,2] [3,∞)` answers nothing for a 2.4),
  says the coverage-gap check *cannot* see the hole because on an integer kind it only flags one
  wider than a whole number, and states that no authored edit fixes it — the fix is a parallel float
  column at 0.7 and the retype at 1.0. It does not imply the author did anything wrong. This is the
  stated behaviour, and it is what the plan asked to be checked rather than "finished".
- **RM56 fires once for the whole table**, not per row, says a conforming consumer **withholds**, and
  says explicitly that withholding is *not* falling back to the `unresolved` row — which is a
  different claim (no measurement was available).
- **`activity_phenotype` is in neither `_INTEGER_KINDS` nor `_CONTINUOUS_GAP_KINDS`, and CPIC's real
  table authors cleanly because of it.** The holes at 1.0→1.25 and 2.25→2.5 draw no gap warning,
  which is correct: activity scores are summed on a 0.25 grid, so 1.1 is not a measurement this gene
  produces. And two bins meeting at 2.25 *is* an overlap error — the asymmetry RM35 designed. So the
  third kind escapes RM35's unsatisfiable triangle, and it does so for a reason rather than by luck.
- **RM53's newest collision.** A bare `CN` in `source_field` warns with the specific consequence —
  *"INFO/CN is the allele-specific copy number and FORMAT/CN is the sample's total copy number …
  the two answers differ by a factor of the ploidy"* — and `FORMAT/CN` is silent.
- **RM54's pairs.** `largest` and `largest_alt` are both accepted on the same field, which is the
  point: on a `Number=R` field they are different numbers and the vocabulary exists to say which one
  a bin means.
- **RM5's open subtypes.** `<CNV:TR:30>` and `<DUP:16000>` are accepted; the length is read out of
  the token in both spellings, and a subtype below the closed five is not a special case.
- **RM59's natural `*`.** `*/T` on an autosome — the second haplotype taken by the `*5` whole-gene
  deletion — is accepted in silence, which is the control for `mt_common_deletion`'s hostile `*` on a
  haploid contig.
- **The gap check still works where it should.** A deliberate hole between copy-number bins 10 and 21
  is reported (`no bin covers (10.0, 21.0)`), so RM55's "the coverage-gap check cannot report the
  hole" is a statement about *sub-integer* holes and not a check that has been turned off.

## RM65 / RM66 — the gating evidence, not a finding

0.6 corrected the claim that these tables are "not joinable by position, which is a property of what
they describe" to say the non-joinability is a **schema gap**, gated on a real caller VCF. This
module is that case made concrete: `copynumbers.csv` is keyed `(gene, …)` and carries `FORMAT/CN`,
and a consumer holding a `<CNV>` record at `22:42126400` has no column to join on. Filed as the
evidence RM65 waits for, not as a defect — the plan's rule is to attack claims, not gaps.

## The round trip

```bash
just-dna-compiler compile reference_examples/cyp2d6_structural out/d3 --strict
just-dna-compiler reverse out/d3 out/d3_rev
just-dna-compiler compile out/d3_rev out/d3_again --strict
```

A fixed point on `artifact.digest` (`2dbdeee7…`) and `content_signature` (`d8f59952…`), with both
symbolic alleles and the `*/T` genotype surviving verbatim, and the two RM55/RM56 warnings emitted
identically on both sides — which is the count-rule check for this module, since both messages embed
a bin count.
