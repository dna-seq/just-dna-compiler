# Table prose — the half a model cannot state

**This file is a build input, not a page.** Each `## <name>.csv` section below is spliced above the
generated identity card and column table on that table's reference page, so nothing here is published
twice. `mkdocs.yml`'s `exclude_docs` keeps it off the site and
`schema/tests/test_docs_site_nav.py` asserts that `nav`, `not_in_nav` and `exclude_docs` partition
`docs/`.

**What belongs here, and what does not.** A section says what a *model cannot*: the grain of one row,
which cells a person decides versus a machine fills, why the artifact has the shape it has, and the
symptom when the table is wrong. Columns, types, requiredness and vocabularies are **generated** from
the row model on every build — never restate one here, because a restated column is a column that
drifts, which is why `just-module-creator`'s hand-written dossiers were a release behind by the time
anyone noticed.

**No procedure.** Not "run this, then that" — the authoring workflow is `just-module-creator`'s, and
this repository deliberately carries no authoring document. If a sentence here starts telling somebody
what command to run, it is in the wrong repository.

Sections are required for every **lead** table (the ones whose parquet is in `LEAD_PARQUETS`) and
allowed for any other; `compiler/tests/test_table_prose.py` asserts that asymmetry rather than an
equality, so a section for a derived table is legal and a missing lead section is not.

## variants.csv

**One row is one (locus, genotype) pair** plus the prose conclusion for somebody carrying that call.
It is the only table a consumer joins directly against a VCF genotype, and the only lead table
carrying the general annotation axes — clinical significance, direction, effect size, callability.
Its audience is two-sided, which is why it has more columns than anything else here: an author
decides zygosity and prose, and a consumer's engine matches sample calls row by row.

**The artifact splits it in two, and that asymmetry trips every consumer once.** `weights.parquet`
gets the authored surface *except* `gene`, `phenotype` and `category`; `annotations.parquet` gets nine
columns *including* those three. So a gene symbol exists in the artifact **only** in
`annotations.parquet`, and a consumer reading `weights.parquet` alone cannot see one. The two also
disagree on how they store the call: `annotations` keeps the authored `genotype` string while
`weights` keeps a sorted allele list plus a `phased` bool.

**`start` is the 1-based VCF position.** Never subtract one from it. The bound is `ge=0` rather than
`ge=1` because VCF permits POS 0, not because the column is ever interbase — every check and every
minted identity reads it as VCF POS.

**The symptom of getting the identity wrong is a silent miss, not an error.** A row identified only by
`rsid` matches at position level, so it answers for every allele at that locus; a row identified by
`chrom`+`start` without `ref` cannot be checked for a wrong reference base by the compiler at all —
only the enricher, holding a reference, can catch that.

## haplotypes.csv

**One row is one defining variant of one named haplotype** — a junction table, not a description of
the haplotype. Many rows per haplotype, and a variant recurs across many: CYP2D6's rs1065852 is
core-defining in 22 alleles. Nobody should expect one row to describe `*4`.

**A star allele can be used without being defined**, and that is legal. `diplotypes.csv` and
`allele_function.csv` may name an allele this table never defines; the compiler warns only when
`haplotypes.csv` is present at all, and `*1` is exempt by construction — it is the reference allele
and has no defining variants to list.

**`requires_callable` lives here** rather than on `diplotypes.csv`, because a row here names a locus,
so a callability claim is about a position the row actually states.

## allele_function.csv

**One row is one allele-unit** — the canonical star-string is the identity and the required key.
Everything beside it is a parsed convenience of the *cis* unit: `copy_number`, `sv_type`,
`hybrid_orientation`. When a convenience column and the star-string disagree, **the star-string is
truth**; the others exist so a consumer need not re-parse it.

`suballele` is optional extra precision (Aldy's `Minor`, e.g. `1.001`) and never replaces the core
star. A consumer keyed on the suballele silently misses every row that carries only the core.

## diplotypes.csv

**One row is one haplotype pair → one phenotype**, and the pair is canonicalised (`haplotype_a <=
haplotype_b`) so a lookup is order-independent. Several rows per pair are legal — a pleiotropic
diplotype affecting several traits is several rows, not one row with a list.

**There is deliberately no `requires_callable` column, and the absence is the decision.** A diplotype
names a *pair*, not a locus, so the column could only mean "the variants defining these two
haplotypes were callable" — a fact about `haplotypes.csv` rows, restated one table over, free to drift
the moment a definition is edited. One concept, one home. `extra="forbid"` is what enforces it, so
adding the column by hand is a compile error rather than a silent second source of truth.

## pharm_variants.csv

**One row is (variant, drug, genotype) → response**, at a PharmGKB evidence level. It is a distinct
table rather than columns on `variants.csv` so that a module carrying no drug annotations carries no
drug columns — one CSV, one concern.

**`genotype` is part of the identity, not decoration.** PharmGKB publishes a clinical annotation *per
genotype*: a summary names variant and drug, and the child rows give one annotation per call, usually
three. They are not variations on one finding — they are distinct and sometimes opposed ones, so
collapsing them to the variant loses the direction of the effect.

**`evidence_level` is PharmGKB's axis and `recommendation_strength` is CPIC's.** They are not two
spellings of confidence and must not be filled from one another.

## pgs.csv

**One row is one curated PGS Catalog entry** — the accession and the trait, not the weights. The
scoring file itself is deliberately not authored here: a polygenic score's variant weights are a
data file, and carrying them as an authored table is tracked separately rather than assumed.

A module citing an academic-research-only score **cannot compile without a declared use**, because the
Catalog publishes `license` per score record and it varies. That is the one place this table reaches
the compile gate.

## activity_phenotype.csv

**One row is one activity-score band → one metabolizer phenotype, per gene** (CYP2D6 PM/IM/NM/UM).
The score itself is the *consumer's* call — Σ activity × copies across the diplotype — and this table
only bins it. Nothing here computes a score, and a module that looks like it does is misread.

Bounds are inclusive and a shared endpoint belongs to the **higher** bin under continuous tiling, so
two adjacent bands may legitimately name the same number.

## copynumbers.csv

**One row is one whole-gene dosage band → one phenotype** (SMN1 in SMA). A sharp dosage is
`measure_min == measure_max` — zero copies is `[0, 0]`, not a null — and an open top end is
`measure_min=3, measure_max=None` for "3 or more".

**The modifier locus is named columns, never a tuple.** An SMN1 phenotype depends on SMN2's copy
number, so `modifier_gene` plus a modifier dosage express a second locus read in context; the gene and
its dosage are set together or both left null.

**The modifier dosage has two spellings and one meaning.** `modifier_copy_number` is the float column;
`modifier_cn` is the original `int`, deprecated and removed at 1.0. VCF 4.4 §7.2 redefined `CN` to
admit non-integer copy numbers, so an `int` cannot hold a real modifier dosage — and retyping a column
is major-only, which is exactly what the companion column exists to avoid. Everything reads the
coalesced value, `_KEY_FIELDS` included, so filling both with different numbers is the one way to make
this table lie.

## repeat_alleles.csv

**One row is one repeat-count band for one (gene, motif)** — and the motif is part of the identity. A
count is only comparable within the motif definition that produced it, so a row that omits the unit is
not a looser row, it is an unusable one.

The count is the consumer's call (ExpansionHunter, adVNTR, a span genotyper) and the caller **must**
state the motif it counted. The symptom of a mismatch is a plausible wrong answer rather than a miss:
a count against a different unit length bins cleanly into the wrong band.

## heteroplasmy.csv

**One row is one mtDNA allele-fraction band, keyed on gene, reference sequence, tissue — and the
variant.** Every part of that key earned its place by breaking something without it.

The **reference sequence** is in the key because rCRS/`NC_012920` and the legacy `NC_001807` disagree
on position, and `genome_build` does not disambiguate them. The **variant identity** is in the key
because one mitochondrial gene carries several pathogenic variants with genuinely different
thresholds — MT-TL1 has m.3243A>G and others, and binning them together is not conservative, it is
wrong in both directions.

**Tissue is optional and load-bearing, which is the uncomfortable combination.** Heteroplasmy bins are
tissue-conditional: a blood-derived fraction systematically under-represents the burden in affected
tissue, and the penetrance threshold itself shifts, so the *same* fraction bins to different
phenotypes across tissues. A heteroplasmy table with no tissue context is quietly unsafe — it will
compile, and a consumer cannot tell which tissue its bins assume. State it.
