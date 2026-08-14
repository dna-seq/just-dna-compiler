# `mt_common_deletion` — a symbolic allele on the contig where dropping a row is fatal

**What this probes:** *RM5's symbolic-allele grammar, on a real module, through every tier.* 0.6 gave
the format VCF's five structural allele types with their length in the token (`<DEL:4977>`), and
**no reference example carried one** — so the grammar shipped, the compiler learned it, and the
enricher never met it.

The data is the mitochondrial 4,977 bp common deletion (Kearns–Sayre, Pearson) beside two point
variants, one of which — `m.8993T>G` — sits *inside* the deleted interval. The literature reports the
deletion at two start positions because 13 bp direct repeats flank it, which is the honest reason a
structural allele is spelled symbolically rather than as bases.

`chrM` is authored deliberately (RM60 widened the contig grammar to accept it); everything downstream
normalizes to `MT`, including on reverse.

## What it broke

### 1 — `enrich` crashes on any module carrying a symbolic allele

> **Fixed** (D1-1). `VrsMinter.mint` refuses a sequence-free allele before routing it to `_mint_normalized`, alongside the `UnsupportedBuildError` guard it sits beside. Probing it also showed the crash is the *character class*, not the symbolic spelling: RM58's `.` raises the identical error, and RM59's `*` passes `LiteralSequenceExpression`'s pattern, so it would have been handed a content-addressed id for a state that is not a sequence. All three are guarded.

```
$ just-dna-enricher enrich reference_examples/mt_common_deletion
ValidationError: 1 validation error for LiteralSequenceExpression
sequence
  String should match pattern '^[A-Z*\-]*$'
  [type=string_pattern_mismatch, input_value='<DEL:4977>', input_type=str]
```

An unhandled pydantic error out of `ga4gh.vrs`, three frames down from the CLI. `VrsMinter.mint`
routes on `is_substitution(ref, alt)`, a symbolic allele is not one, so it falls into
`_mint_normalized`, which builds

```python
state=models.LiteralSequenceExpression(sequence=alt.upper()),
```

**outside** the `try` that follows it — and the comment immediately below that `try` says *"A failure
here is a live-service problem … never a reason to fail the enrichment."* The guard starts one line
too late, and the thing it was written to catch is not the thing that arrives.

This is the same shape as the defect `reference_examples/grch37_build` records as its third: a
`refget_accession` raise that `VrsMinter.mint` did not catch, so one row killed a whole run. The
comment explaining that fix sits eight lines above the crash.

Grep confirms why it survived: **no reference example and no enricher test carried a symbolic
allele** before this module. `test_clinpgx_draft.py` is the only enricher test that mentions `<DEL:`
and it exercises the drafter *skipping* them.

### 2 — offline, the same allele is misdiagnosed as an indel, with a remedy that crashes

> **Fixed** (D1-2), in both tiers. `why_not` and the compiler's `_vrs_gap_reason` / `_recompute_vrs_id` each give a symbolic allele its own permanent reason class, so nothing offers a remedy that cannot work.

```
VRS coverage — VRS allele identity covers 2/3 allele(s) (67%) — 1 still carry no ga4gh:VA. id
VRS coverage —   1 allele(s): an indel/MNV, which must be justified against the reference sequence
                — re-run without --offline to mint it
```

Both halves are wrong. `<DEL:4977>` is not an indel: symbolic notation exists precisely because the
sequence is *not* known, so there is nothing to justify against the reference and no id will ever be
mintable — this is a permanent reason class, not a `--offline` limitation. And the remedy it offers
is the command in finding 1.

`_vrs_coverage`'s grouping-by-reason machinery is doing its job; it was simply never told that RM5
added a fourth reason. One root cause, two visible defects, and the offline one is the more dangerous
because it looks like ordinary output.

### 3 — a binning table that names a variant is exempt from the grounding check, in a module with no `studies.csv`

> **Fixed** (D1-3). The variant-identity term is gone from the `ungrounded` filter: inside a scope where the module has no study rows, naming a variant grounds nothing. The two-route remedy text stays, because a heteroplasmy author really does have both routes open.

`_check_binning_grounding` opens with `if studies: return []` — it only runs when the module has **no
study rows at all** — and then counts a bin as grounded when it names a variant:

```python
ungrounded = [r for r in rows if r.pmid is None and getattr(r, "variant_key", None) is None]
```

The comment above it says the second route is *"naming the variant a study row can then name back."*
There is no study row; the function has just established that. So a `heteroplasmy.csv` module stating
four thresholds and citing nothing anywhere compiles green and silent, while the identical module
built on `repeat_alleles.csv` is warned — reopening the S19 gap for the one binning kind a real
MELAS/NARP module uses.

Reproduced on a two-bin `heteroplasmy.csv` with `rsid=rs199474657`, no `pmid`, no `studies.csv`:
zero grounding warnings, in both modes. The control (`reference_examples/htt_repeat_expansion`) warns
as designed.

### 4 — `describe` omits the vocabulary notes that `reference` carries

> **Fixed** (D1-4). Per-member prose now rides on the field's `vocabulary` marker, so `describe`, `field_options` and the per-field entries of the whole-schema reference all carry it, with a cross-surface guard test that did not exist before.

`just-dna-compiler describe heteroplasmy.csv` calls itself "the **full** machine description of one
table kind" and prints `source_element`'s eight members with one general sentence about the `_alt`
pairs. The per-member meanings — `vocab.ELEMENT_RULE_MEANINGS`, pinned member-by-member by
`test_vcf_pointers.py` — reach only the whole-schema `reference` output, under `vocabulary_notes`.
An author authoring one table reaches for the per-table command and gets the names without the rules.

## What was probed and held

Every one of these is a claim 0.6 makes, checked against a real row rather than a fixture:

- **RM5's placement rule, all four cells.** `<DEL:4977>` on `variants.csv` is accepted (it has a
  length). A lengthless `<DEL>` there is warned, named in both the `alts` and `genotype` cells, and
  the message says the row is **DROPPED** and that `--strict` refuses. The same lengthless allele on
  `heteroplasmy.csv` is an **error in both modes**, with the reason stated in-line: *"a
  heteroplasmy.csv row is part of a composite (a haplotype's definition, a bin tiling), so dropping
  it would not make a smaller module but a quietly different one."*
- **RM60 did not blind RM48.** This was the seam the plan flagged as untested: `chrom: chrM`
  normalizes, and a row at `chrM:16600` is still refused — *"place a variant past the end of MT on
  GRCh38 (16,569 bp) — no build this compiler knows has a contig MT that long"*. The widening reaches
  the contig-length table through the same normalization.
- **RM58 keeps `.` apart from a symbolic allele.** `alts=.` is diagnosed as VCF's MISSING marker,
  says explicitly that it *"is not the same kind of thing as a symbolic allele like `<DEL>`"*, and
  adds the consequence the plan did not ask for: the row keys differently from the same site with an
  empty cell, so two modules authoring one site carry two identities and neither `content_signature`
  dedups against the other.
- **RM59's `*` and the ploidy check do not collide.** `*/A` on MT warns *"chrom=MT is not diploid
  here"* — correct, and not a miscount: `*/A` is two-allele notation whatever `*` denotes, and a
  haploid contig has one allele. A bare `*` is accepted in silence. (The unsorted `A/*` is refused by
  the shared diploid grammar for sort order, `*` sorting before `A`; that is the existing rule, not a
  symbolic-allele question.)
- **RM53's collision warning** fires on a bare `AF` in `source_field` with the full INFO-versus-FORMAT
  explanation and the observation that a heteroplasmy fraction is the second one; `FORMAT/AF` is
  silent. **RM61's widening** accepts a dotted vendor key (`gnomAD.AF`) and a leading-digit one
  (`INFO/1000G`) without a word.
- **RM43 reaches the third positional kind.** An rsID-only `heteroplasmy.csv` is reported as
  unjoinable; inject a `resolution.csv` naming the key and the warning goes.
- **RM47 on a bin row.** `pmid` on the `heteroplasmy.csv` boundaries is accepted, and this module
  grounds every threshold it states — which is the thing `htt_repeat_expansion` deliberately does not
  do.

## The round trip

```bash
just-dna-compiler compile reference_examples/mt_common_deletion out/mt --strict
just-dna-compiler reverse out/mt out/mt_rev
just-dna-compiler compile out/mt_rev out/mt_again --strict
```

`artifact.digest` and `content_signature` are a fixed point, with the symbolic allele surviving
verbatim in both `variants.csv` and `heteroplasmy.csv`. `chrM` comes back as `MT` — normalization,
not loss, and the same asymmetry every other example shows on column order and cell formatting.

One expected warning, and it is the right one:

> 1 coordinate-authored row(s) have no rsid in the resolution table, so they stay coordinate-keyed:
> `MT:8470 N><DEL:4977>`. Not an error — a coordinate is a complete identity and an rsID is a label
> on top of it.

The deletion has no rsID because dbSNP does not carry it, and the module says so rather than
implying the enrichment failed.
