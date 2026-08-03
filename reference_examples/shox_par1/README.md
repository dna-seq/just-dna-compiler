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

## 3. One indel, two spellings, no match (surfaced — [RM31](../../docs/ROADMAP.md))

`rs1569493663` does not resolve. ClinVar publishes it as `X:634689 CAG>C`; Ensembl publishes the same
2 bp AG deletion as `X:634690 AGAG>AG`, anchored one base earlier with a padding base.
`genotype_fits` compares allele strings, so the two spellings do not match and the locus is dropped.

The message used to *assert* the wrong reason — "that record is a different variant sharing the
rsID" — sending an author to hunt a dbSNP merge that does not exist. It now names both readings, which
is all this layer can honestly do. Reconciling them needs indel normalization, and that is a real
design decision rather than an oversight: a reference-free parsimony trim fixes this pair but cannot
left-align inside a repeat, while a reference-backed one can only run in the enricher — and
`genotype_fits` is shared with the compiler, which by charter holds no reference.

## 4. Nine findings became eighteen rows (surfaced — [RM32](../../docs/ROADMAP.md))

Nine of the ten variants map to **both** X and Y at the same base, so the expansion emits two rows
each: 19 resolution rows for 10 findings, all inside `artifact.digest`. A consumer counting findings
gets 19, and since standard GRCh38 analysis sets hard-mask the Y PAR, the nine Y rows can never match
anything in a normal pipeline.

Collapsing them would contradict the identity model 0.5 just adopted — VRS keys on the refget
accession, and X and Y are different sequences — and the expansion is exactly right for the paralog
case it was built for. So it is recorded as a question (is a module's subject a *place* or a *contig
coordinate*?) rather than patched.

## Also visible in the compile output

`sources.csv has no row for ['ensembl', 'ensembl-rest']` — [RM33](../../docs/ROADMAP.md). The
resolution table's `source` names *which link answered*; `sources.csv`'s names *a licensed source*.
Two vocabularies, one column name, compared by string equality.

## Reproduce

```bash
just-dna-enricher draft-panel reference_examples/shox_par1 --gene SHOX --snapshot <clinvar-snapshot>
# then decide each genotype, from the allele pairs the draft reports
just-dna-enricher enrich reference_examples/shox_par1
just-dna-compiler compile reference_examples/shox_par1 out/shox_par1
```
