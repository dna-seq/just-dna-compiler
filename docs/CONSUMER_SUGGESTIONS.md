# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S31

**Claim ids from here, never from what this file shows.** S1–S29 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
.claude/triage-state.sh --next        # scans this file AND the history file
```

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## S30 — the 0.4 families store a genotype string, `weights` stores a list

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
