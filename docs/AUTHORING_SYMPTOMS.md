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
pattern the CPIC provider checks, so those rows are skipped and counted (RM5's notation gap).

**`draft --gene CYP2D6` produced thousands of diplotype rows**
Expected without a filter, and the fix is `--allele`: name the star alleles your consumer's caller can
emit and every table is drafted to that set (`*1` is kept automatically). Six alleles turn CYP2D6's 16,290
diplotypes into 21. One `--gene` at a time, because `*2` means a different allele in each gene.

## Resolution and enrichment

**`not in the injected Ensembl snapshot, position remains unset`**
The local snapshot does not contain it — **not** a claim that Ensembl does not. Online, the live link
runs next. Offline, that is the end of the road and the row stays unresolved.

**`cannot host the authored genotype … The event sizes differ`**
A real contradiction, and a decidable one: re-anchoring an indel never changes how many bases it adds or
removes, so this is a different variant sharing the rsID rather than another spelling of yours. One rsID
legitimately covers several records at a locus (`rs281864532` is `G>GT`, `GT>G` *and* `GTT>G`), so check
which record your genotype was written from. Two spellings of *one* indel now reconcile automatically —
ClinVar's `X:634689 CAG>C` and Ensembl's `X:634690 AGAG>AG` are the same 2 bp deletion and both resolve
(**RM31**, shipped).

**`could not be decided here … the same size but different content`**
Not a contradiction and not your mistake: the two spellings describe an event of the same size in different
bases, which is either one indel re-anchored inside a repeat or two different variants, and telling those
apart needs the reference sequence. **The locus is kept** — nothing is dropped and `strict` still compiles.
Run the enricher (it has sequence access) if you want the ambiguity resolved; do not edit an allele to
silence it.

**`maps to N loci in the resolution table; expanded to N rows`**
Normal for a **paralogous** rsID — one id, several genuinely distinct places. Expected, not an error; do
not delete rows to suppress it. To count *findings* rather than rows, count distinct `rsid` in
`weights.parquet` — the expanded rows keep it.

**`rsN is pseudoautosomal: it maps to 2 loci (X:… and Y:…) that are 1 place(s)`**
A different message for a different situation, and the wording is the point: PAR1/PAR2 are shared between
X and Y, so this is **one place spelled twice**, not two places. You only see it if the table carries both
contigs — `enrich` records the X spelling alone by default, since ClinVar holds no PAR variant on Y and
gnomAD excludes the Y PAR from its callset, so the Y row could match nothing in a standard
(analysis-set-masked) GRCh38 pipeline. Re-run `enrich` without `--keep-par-twin` to record X only; keep
both deliberately if your reference is unmasked. Not an error either way.

**`pseudoautosomal: kept the X spelling of N locus/loci; left out …`** (from `enrich`)
Informational, and printed rather than silent precisely so a table half the size you expected is never a
surprise. The named Y loci are the same places as the X ones kept. `--keep-par-twin` records both.

**A sidecar did not change after you edited the spec**
An existing `resolution.csv` / `frequencies.csv` / `gene_metrics.csv` is authoritative and merged.
**Delete the file** and re-run, or stale rows persist silently.

**`sources.csv has no row for … ['gnomad']`**
A real finding now, not noise: a source contributed facts and the module records no terms for it. Fixed
by **re-running the pass that consulted it** — `enrich`, `frequencies` and `gene-metrics` each write
their own `sources.csv` row, and merging never clobbers a row you wrote by hand.
It used to fire for link names (`ensembl-rest`), which are not sources at all; `resolution.csv` now
records an `authority` beside the link and the check reads that (**RM33**, shipped). An older
`resolution.csv` written before the column existed simply says nothing here — re-enrich to fill it.

## Validation and compile

**`overlapping bins for key (…)`** — an **error**, so the module cannot compile
Two resolved bins in one group select two phenotypes for one measurement. Check the group key first
([AUTHORING_TABLES.md](AUTHORING_TABLES.md)): bins are grouped by the kind's key columns **plus** `trait_efo_id`. If
two different variants are colliding in a heteroplasmy table, give each its variant identity
(`chrom`/`start`/`ref`/`alts`) — that is what the key is for.

**`coverage gap … no bin covers (0.099, 0.1)`** on a fraction or percentile
Now fixable, and the fix is to **make the bounds touch**: write `0.0–0.1` and `0.1–0.3` rather than
`0.0–0.099`. On a continuous measure two bins may share an endpoint and the higher bin owns it, so a
measurement of exactly `0.1` selects the second row. Author the top bin **closed** (`0.3–1.0`) — the
top of the domain is a real measurement. This used to be unfixable (**RM35**, shipped in 0.5); on
`repeat_count`/`copy_number` a shared endpoint is still an overlap and still an error, because there the
bins genuinely both claim that integer.

**`bins with the same lower bound for key (…)`** — an **error**
Two bins in one group start at the same number, so the shared-endpoint rule has nothing to order and a
measurement at that number has two answers. Usually a sharp bin (`0.1–0.1`) written beside the range
that begins there; drop the sharp row or move the range's start.

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

**`acmg_sf=false but <GENE> is on ACMG SF v3.3`**
The column is gene-level list membership. If the row is about a variant in a listed gene that is not
itself a reportable finding, leave the cell **blank** — blank means "not stated". ACMG scopes some
entries more narrowly than the gene (HFE is *"c.845G>A; p.C282Y homozygotes only"*).

**`unverifiable: …` and `the list read is ACMG SF v3.2 but v3.3 is published`**
**Not a finding about your module.** You ran `check-acmg` without `--sf-list`, so it fell back to NCBI's
page, which is a release behind — it does not carry `ABCD1`, `CYP27A1` or `PLN`, all of which v3.3 lists.
Every disagreement is withheld rather than reported, and `--strict` will not fail on one. To get an
answer: `just-dna-enricher acmg build assets/acmg_sf_v3.3.xlsx --out acmg/`, then re-run with
`--sf-list acmg/` (which also works `--offline`).

**A note saying a gene is listed and `acmg_sf` is blank**
Informational, never a defect, and `--strict` does not escalate it. Blank is a legitimate answer.

**`clin_sig` differs from ClinVar's** and `--strict` did not fail
Deliberate. Two opinions differing is not a factual error, and ClinVar is not truth — a curator who has
read the primary literature may correctly disagree with a one-star submission. The finding carries
ClinVar's review-star count so you can weigh it. The allele-function check behaves the same way.

**A wall of near-identical warnings**
Should not happen; findings aggregate per gene with a count and examples. If you see one, that is a bug
worth fixing at the source rather than filtering — three of them were found and fixed this way.
