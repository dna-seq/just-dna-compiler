# SHOX — an annotation in the pseudoautosomal region

Built adversarially: the goal was to find where the libraries claim more than they know, using a real
gene and a real source rather than contrived inputs. SHOX is the right probe because it sits in
**PAR1**, the stretch X and Y share and recombine at meiosis — so it is present in two copies in
*every* karyotype, escapes X-inactivation, and its haploinsufficiency causes Léri-Weill
dyschondrosteosis and a share of idiopathic short stature in both sexes.

Ten pathogenic / likely-pathogenic alleles, 2★ and above, drafted from ClinVar with
`draft-panel`, zygosity decided by hand, enriched and compiled. It found four things.

## 1. The non-diploid guardrail was wrong in both directions (fixed)

The compiler warns when a `chrom=MT` or `chrom=Y` row carries a two-allele genotype — a "fake
diploid" call. Its comment claimed Y was *"the safe, false-positive-free half of non-PAR X/Y"*.

It is not. PAR1 spans Y:10,001–2,781,479 and PAR2 spans Y:56,887,903–57,217,415; a locus inside
either is diploid in everyone, so a two-allele genotype there is **correct** and the advice to use a
single allele would have made the annotation wrong. And the author need not even choose the Y
coordinate — the resolver's one-to-many expansion produces the Y row on its own.

The same probe found the opposite error. The check ran inside `_cross_validate_variants`, which the
compile calls twice and the second time takes **errors only** — so a warning whose entire input is
`chrom` was computed on rows where resolution had not yet filled it, and then discarded on the rows
where it had. An rsID-authored MT variant — `rs199474657` with genotype `A/G`, the exact MELAS
fake-diploid error, and *the shape every drafting provider emits* — was silently unchecked, while the
same variant written as `MT,3243,A/G` warned. Coverage depended on authoring style, not on data.

Both are fixed: `vrs.in_pseudoautosomal_region` answers three-valued (`True`/`False`/`None`, the last
for a build with no PAR table), and the guardrail runs where `chrom` is final.

## 2. `draft-panel` asked for a decision and withheld its inputs (fixed)

The provider leaves `genotype` as a placeholder, correctly: ClinVar publishes **alleles, not
genotypes**, and zygosity follows from inheritance mode. But a genotype is nucleotides drawn from
`{ref} ∪ alts`, and a row identified by its rsID carries neither — so the author faced
`rs201157428` and `<<REPLACE>>` with nothing to write from. The obvious next move fails too: `enrich`
would resolve the alleles and *refuses* to load a file containing a placeholder, which is right,
because forward resolution is allele-aware and a placeholder genotype would silently skip that filter
on exactly the one-to-many rsIDs that need it.

The alleles are now **reported** — one line per stubbed row — never written. Writing them would need
the whole coordinate (identity is filled whole or not at all), discarding the rsID identity the
provider deliberately chose, and `alts` is redundancy-bearing: the compiler's allele-membership check
keeps its force only because the human's genotype and the source's alleles were authored
independently.

## 3. One indel, two spellings, no match (fixed — [RM31](../../docs/ROADMAP_HISTORY.md))

`rs1569493663` used not to resolve. ClinVar publishes it as `X:634689 CAG>C`; Ensembl publishes the same
2 bp AG deletion as `X:634690 AGAG>AG`, anchored one base earlier with a padding base.
`genotype_fits` compared allele strings, so the two spellings did not match and the locus was dropped —
and the message *asserted* the wrong reason ("a different variant sharing the rsID"), sending an author to
hunt a dbSNP merge that does not exist.

It resolves now, on both contigs, with no authored edit. `alleles.parsimony_reduce` strips the flank a
collection of alleles shares, so `{C, CAG}` and `{AGAG, AG}` both reduce to `{'', 'AG'}` — the event, which
is what the two spellings have in common. **The reduction needs no position, and that turned out to be
forced rather than clever:** this row records no coordinate at all (the provider chose the rsID identity),
so there was never an authored anchor to normalize against. What carries the frame is the genotype naming
*two* alleles.

`hosting_verdict` has three answers, so the residual is named rather than swallowed: differing event
**sizes** are a confident negative (re-anchoring never changes how many bases an event adds or removes),
while same-size different-content spellings — one indel rotated inside the repeat, or two variants — are
**undecided**, and the locus is kept with a message that says so.

**What is still true of this module, and worth knowing before copying it.** The compiled row carries the
authored genotype `C/CAG` (ClinVar's frame) beside the resolved `ref=AGAG, alts=AG,AGAGAG` (Ensembl's). The
variant is located and the module is coherent, but a consumer matching that genotype against a VCF call by
string equality will still miss, because the VCF is in the reference's frame. `just_dna_format.alleles` is
public and dependency-free so the consumer can apply the same reduction; having the enricher rewrite the
authored cell is the parked co-authoring item, since it would make `content_signature` depend on a fetch.

## 4. Ten findings, twenty rows (fixed — [RM32](../../docs/ROADMAP_HISTORY.md))

Every one of the ten variants maps to **both** X and Y at the same base (PAR1 has identical coordinates on
the two contigs in GRCh38), so the expansion emitted two rows each: **20 rows for 10 findings**, all inside
`artifact.digest`. Standard GRCh38 analysis sets hard-mask the Y PAR, so in a normal pipeline the ten Y rows
could never match anything.

It is **10 rows now**, and the module lost nothing:

```python
w = pl.read_parquet("out/shox_par1/weights.parquet")
w.height, w["rsid"].n_unique()      # (10, 10) — was (20, 10)
```

The question the entry parked on was whether a **place identity** exists — a name for the locus that is not
a contig coordinate — and the probe it named answered no. The **ClinGen Allele Registry mints two CA ids**
for one PAR base (`CA254919` for X:640851 and `CA254920` for Y:640851 of `rs137852556`; `CA10330023` /
`CA2467802563` for `rs746801054`), so `ResolutionRow.caid` cannot carry a place and no upstream mints one.

What the probe found instead is that **every annotation source already picked a spelling, and it is X**:
ClinVar holds no variant in either PAR on Y at all (0 of 677 Y records), gnomAD v4 excludes the Y PAR from
its callset (X PAR1 640000–641500 serves 880 variants, the same interval on Y serves none), and the
Registry's Y record is a bare dbSNP cross-reference with no ClinVar and no gnomAD. Only the coordinate
resolver reports both contigs. So recording the X locus alone is not encoding the *consumer's* analysis set
— the objection that had parked the idea — it is recording the **sources' own convention**, which is what
the enricher is for. `enrich` keeps the X spelling and says so; `--keep-par-twin` keeps both for an unmasked
reference.

Two things this did **not** become, and why. Collapsing the pair into one row would contradict the identity
model 0.5 adopted — a VRS allele id keys on the refget accession, and X and Y are different sequences — and
the expansion is exactly right for the paralog case it was built for; selecting between two spellings is not
collapsing two alleles. And a `place_key` column was rejected: the X↔Y correspondence is *derivable* from
constants already in the tier (`vrs.par_partner`, which is public and dependency-free precisely so a
consumer can apply it), so a column would make an author restate what the data determines — the same
argument that rejected `requires_phase`.

The boundary case that decided the *shape* of the fix is a separate module,
[`par_boundary/`](../par_boundary/README.md): XG and SPRY3 straddle a PAR boundary, so the verdict has to be
per locus and could never be per gene or per module.

## Also visible in the compile output

**Nothing.** The compile is silent now, which it has never been before. Licensing went quiet in the round
that landed [RM33](../../docs/ROADMAP_HISTORY.md) — `resolution.csv` records an `authority` beside the link,
so the `sources.csv has no row for ['ensembl-rest']` warning is gone and `sources.csv` carries Ensembl's
terms at the `resolution` layer, written by the pass that consulted it. The ten PAR-expansion warnings that
remained after that were the last thing this module emitted, and RM32 removed the expansion that caused
them.

## Reproduce

```bash
just-dna-enricher draft-panel reference_examples/shox_par1 --gene SHOX --snapshot <clinvar-snapshot>
# then decide each genotype, from the allele pairs the draft reports
just-dna-enricher enrich reference_examples/shox_par1 --no-clinvar
just-dna-compiler compile reference_examples/shox_par1 out/shox_par1
```

`--no-clinvar` pins the resolver to the Ensembl link, which is what produced the coordinates and `alts` this
module's digest was computed from. It matters here beyond reproducibility: the chain is first-hit-wins, and
the ClinVar link resolves several of these rsIDs to a *narrower* `alts` (`rs137852552` as `C>T` rather than
Ensembl's `C>A,T`) and spells the `rs1569493663` deletion in ClinVar's own frame instead of the
`X:634690 AGAG>AG` one section 3 is about. Both tables are correct; they are not the same bytes, and `alts`
is a fact column.
