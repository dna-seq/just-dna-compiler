# Symptom → cause → action

Real message text, matched on the distinctive phrase. Most of these cost someone a day.

## Authoring and loading

**`unreplaced template placeholder '<<REPLACE>>' in VariantRow row: genotype`**
A scaffolded stub or a drafted partial row still needs a human. This blocks **every** loader, including
`enrich` — deliberately, since forward resolution is allele-aware and a placeholder genotype would skip
that filter. Do not try to enrich first: the draft report already printed the allele pair for each
stubbed row (`genotype for rs…: ClinVar publishes C>T — an allele pair from {C, T}`). Curate from that.

**`Input should be a valid string [input_value=None]` on a column you were not told to fill**
A *defaulted* column left empty. An empty cell arrives as `None` and overrides the default. Run
`just-dna-compiler requirements <kind>` — its "must not be left empty (defaults)" line names them.
`required_fields` alone is not enough; requiredness has three shapes.

**`ref/alts require chrom and start to also be provided`**
Identity is filled whole or not at all. Either give the complete coordinate or use the rsID alone. A
lone `alts` on a position-only row would make the key a VRS allele id instead of `chrom:start:ref`,
silently changing which variant the row is.

**`trait_efo_id tokens must be ontology CURIEs`** on a value that is not a trait
Almost always a column-shift in a hand-edited CSV. Re-write it with a CSV writer rather than by
splitting on commas — several `conclusion` values contain commas.

**`must be a non-empty haplotype name without whitespace`**
A haplotype name is an identity, not a grammar — `*4`, `e4`, `ε4` are all fine. This fires on an empty
cell or one with a space. Note CPIC's `x≥3` copy-number notation is *not* accepted by the star-allele
pattern the CPIC provider checks, so those rows are skipped and counted (RM34).

## Resolution and enrichment

**`not in the injected Ensembl snapshot, position remains unset`**
The local snapshot does not contain it — **not** a claim that Ensembl does not. Online, the live link
runs next. Offline, that is the end of the road and the row stays unresolved.

**`cannot host the authored genotype … Either it is a different variant sharing the rsID, or the two
sources spell one indel differently`**
Two readings and the tier cannot separate them. For an indel, suspect the second: ClinVar's
`X:634689 CAG>C` and Ensembl's `X:634690 AGAG>AG` are the same 2 bp deletion, differently anchored, and
`genotype_fits` compares allele **strings**. Tracked as **RM31**; there is no data-side workaround, so
leave the row unresolved rather than editing an allele to make it match.

**`maps to N loci in the resolution table; expanded to N rows`**
Normal for a paralogous or pseudoautosomal rsID. For a PAR variant the two rows are one physical place
on two contigs, and standard GRCh38 analysis sets hard-mask the Y copy — **RM32**. Expected, not an
error; do not delete rows to suppress it.

**A sidecar did not change after you edited the spec**
An existing `resolution.csv` / `frequencies.csv` / `gene_metrics.csv` is authoritative and merged.
**Delete the file** and re-run, or stale rows persist silently.

**`sources.csv has no row for … ['ensembl', 'ensembl-rest']`**
Known and harmless: `resolution.csv`'s `source` names *which link answered* while `sources.csv`'s names
*a licensed source*. Two vocabularies, one column name — **RM33**. Do not hand-write rows for the link
names to silence it.

## Validation and compile

**`overlapping bins for key (…)`** — an **error**, so the module cannot compile
Two resolved bins in one group select two phenotypes for one measurement. Check the group key first
(`references/table-kinds.md`): bins are grouped by the kind's key columns **plus** `trait_efo_id`. If
two different variants are colliding in a heteroplasmy table, give each its variant identity
(`chrom`/`start`/`ref`/`alts`) — that is what the key is for.

**`coverage gap … no bin covers (0.099, 0.1)`** on a fraction or percentile
Unfixable by authoring, and not your mistake: inclusive bounds, overlap-is-an-error and
any-hole-is-a-warning cannot all hold on a continuous measure — touching endpoints error, any epsilon
gap warns. **RM35**. Integer kinds tile cleanly; continuous ones always warn.

**`chrom=MT is not diploid here`** / **`chrom=Y is not diploid here`**
A two-allele genotype on a non-diploid contig. Use a single allele (`G`) for a homoplasmic or
hemizygous call. If the locus is in **PAR1 or PAR2** it really is diploid and this no longer fires —
if it does, check the coordinate.

**`chrom=Y with two alleles on build 'GRCh37', which has no pseudoautosomal table`**
Ploidy could not be decided on that build. The message names both readings and asserts neither.

**`genome_build is 'GRCh37': … keyed by coordinate instead … build-relative`**
Your identities will not join against GRCh38-keyed data (gnomAD, ClinVar, ClinGen), and the same key
means a different locus on another build. VRS identity is GRCh38-only (RM15). Publish GRCh38
coordinates unless the module is deliberately build-local.

**`inconsistent reference allele`**
Two rows share a key while disagreeing about `ref`. Exactly one can be right — a VRS allele id names
the place and the alt, not the reference base, so this is the only place the contradiction surfaces.
An authored `ref` contradicting the *genome* is a different check, and needs the enricher.

**`Star allele(s) used but not defined in haplotypes.csv`**
`allele_function.csv` or `diplotypes.csv` names an allele nothing defines, so a caller can never emit
it and those rows are dead. Either define it or drop the rows. `*1` is exempt — the reference allele is
defined by carrying no variants.

**`diplotype rows … name haplotypes this module defines identically`**
Different names, identical defining-variant sets, disagreeing conclusions — so at most one can be
right, and **phase does not help**. Either the definitions are incomplete or the rows describe one
allele under several names. Distinct from the next entry.

**`diplotype rows … are indistinguishable without phase`**
Same unphased genotype, different conclusions, but the haplotype definitions *do* differ — so phase
resolves it. Correct and expected for a cis/trans pair; a consumer with unphased calls must withhold.

**`sources.csv declares N source(s) no table in this module uses`**
Over-declaration; usually a stale row after you removed a table. Harmless.

**The compile refuses over licensing**
An annotation-layer source forbids sale and the module records no declaration. Compile with
`--use non-commercial` at draft time so the terms are recorded, or drop the source. There is no
compiler flag for this by design — a flag cannot survive `reverse`, so the third compile would refuse.

## Checks

**`acmg_sf=false but <GENE> is on ACMG SF v3.2`**
The column is gene-level list membership. If the row is about a variant in a listed gene that is not
itself a reportable finding, leave the cell **blank** — blank means "not stated". ACMG scopes some
entries more narrowly than the gene (HFE is *"c.845G>A; p.C282Y homozygotes only"*).

**A note saying a gene is listed and `acmg_sf` is blank**
Informational, never a defect, and `--strict` does not escalate it. Blank is a legitimate answer.

**`clin_sig` differs from ClinVar's** and `--strict` did not fail
Deliberate. Two opinions differing is not a factual error, and ClinVar is not truth — a curator who has
read the primary literature may correctly disagree with a one-star submission. The finding carries
ClinVar's review-star count so you can weigh it. The allele-function check behaves the same way.

**A wall of near-identical warnings**
Should not happen; findings aggregate per gene with a count and examples. If you see one, that is a bug
worth fixing at the source rather than filtering — three of them were found and fixed this way.
