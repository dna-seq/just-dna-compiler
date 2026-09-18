# Alleles, genotypes and the contig they sit on.
#
# Source of truth: compiler/src/just_dna_compiler/compiler.py, docs/COMPILER.md
# § "Validate-by-redundancy", and docs/SCHEMAS.md's allele grammar.
#
# The recurring rule: a non-nucleotide allele is a SPELLING defect, diagnosed by name, never
# grammar-checked and never expanded (`@non-nucleotide-spelling`). None of these checks repairs a cell.

Feature: Alleles, genotypes and contig ploidy
  A genotype names alleles the locus has, an effect allele is one of them, and the number of alleles a
  genotype may carry is a property of the contig and the locus — not of the chromosome name alone.

  # source: compiler/src/just_dna_compiler/compiler.py:2384
  @code:genotype_allele_not_at_locus @actionable @ladder
  Scenario: a genotype naming an allele the locus does not have
    Given a variants.csv row whose locus is C>T and whose genotype is "A/G"
    When the module is compiled in best_effort mode
    Then a warning fires whose text contains "are not among the"
    And the text names only the alleles the verdict was actually taken over
    And an unobservable "*" allele is never listed among the missing ones
    # The predicate abstains on `*` (RM59): it records what the call could not observe, so it is never
    # one of the alleles "missing" from a locus. Listing it pointed the author at a correct
    # transcription — a false accusation in the one sentence that says which cell is wrong.

  # source: compiler/src/just_dna_compiler/compiler.py:2396
  @code:effect_allele_not_at_locus @actionable @ladder
  Scenario: an effect allele the locus does not have inverts the conclusion rather than breaking it
    Given a variants.csv row whose effect_allele is not among its locus's alleles
    When the module is compiled in best_effort mode
    Then a warning fires saying "a wrong effect allele inverts the conclusion rather than breaking it"
    And direction, weight and effect_size are all understood as relative to that allele
    # The more dangerous of the pair, and the reason both are checked: a wrong genotype corrupts the row
    # visibly, while a wrong effect allele silently reverses what the module claims.

  # source: compiler/src/just_dna_compiler/compiler.py:2451
  @code:study_effect_allele_not_at_locus @actionable @ladder
  Scenario: the same question asked of a study row
    Given a studies.csv row whose effect_allele is not among its locus's resolved alleles
    When the module is compiled in best_effort mode
    Then a warning fires naming the PMID and saying "effect_size is stated relative to it"
    And it advises checking which side is wrong before editing

  # source: compiler/src/just_dna_compiler/compiler.py:2403
  @tri_state
  Scenario: a study row with no resolved locus is skipped, not reported
    Given a studies.csv row whose key reaches no resolution.csv entry
    When the module is compiled
    Then no study_effect_allele_not_at_locus finding is produced for it
    # Unresolvable is unknown, and the house algebra withholds on unknown rather than negating it. A
    # `StudyRow` has `ref` but no `alts`, so `{ref}` alone would flag every study of a non-reference
    # allele, which is most of them. Silent under `--no-resolve` for the same reason, which is correct.

  # source: compiler/src/just_dna_compiler/compiler.py:2606
  @code:genotype_coverage_gap @actionable @both_modes
  Scenario: a site annotated for some of its genotypes and not the rest
    Given a variants.csv authoring two or more genotypes at a site
    And one genotype of that site's space carrying no row
    When the module is compiled
    Then a warning fires whose text contains "have no row"
    And it says the module "states two or more genotypes at each of those sites"

  # source: compiler/src/just_dna_compiler/compiler.py:2475
  Scenario: a site authoring exactly one genotype is not a gap
    Given a variants.csv authoring one genotype at each of 326 sites
    When the module is compiled
    Then no genotype_coverage_gap warning fires
    # Scoped to sites authoring two or more genotypes, and that is the whole of the design. One genotype
    # is the ordinary shape of a drafted-then-curated module (`pathogenic_clinvar` is 326 of 327), and a
    # rule that fires on the risk genotype and says nothing otherwise is a rule, not a gap. Reporting
    # those would warn on almost every module in existence, which is where warnings stop being read.

  # source: compiler/src/just_dna_compiler/compiler.py:2475
  Scenario: it says nothing about any callset
    Given a module with a missing homozygous-alternate genotype
    When the module is compiled
    Then the finding names the genotype the module has no row for and nothing about matchability
    And the presence of a hom-ref row is not reported at all
    # Whether a hom-ref row can ever match is a property of the DATA a consumer brings — a variant-only
    # VCF emits no such record, a gVCF and an array both do — and that call belongs to the annotator.
    # On array data those rows are the ones carrying the answer.

  # source: compiler/src/just_dna_compiler/compiler.py:2780
  @code:symbolic_allele_unusable @actionable
  Scenario: a symbolic allele with no length is a rule nothing can evaluate
    Given a variants.csv row whose alts is "<DEL>" with no length inside the token
    When the module is compiled in best_effort mode
    Then a warning fires and the row is dropped from the artifact
    # The schema ACCEPTS what this refuses, and the split is forced rather than chosen: a model-level
    # rejection surfaces as a load error, which is fatal in both modes, and the decided behaviour is
    # warn-and-drop. So the grammar says what the DSL can spell and this says what makes a usable
    # rulebook. Do not tighten it back into the models.

  # source: compiler/src/just_dna_compiler/compiler.py:2781
  Scenario: the same defect arrives by two routes and is diagnosed identically
    Given a lengthless "<FOO>" in a genotype column, which has a grammar
    Then it fails at load, in both modes
    Given the same token in an alts column, which deliberately has none
    When the module is compiled
    Then it reaches this check and gets the same diagnosis
    # `ref`/`alts` have no nucleotide grammar on purpose: adding one would reject `N` and stop existing
    # modules validating (P3).

  # source: compiler/src/just_dna_compiler/compiler.py:1921
  @code:missing_allele_marker_in_alts @actionable @both_modes
  Scenario: VCF's missing marker in alts splits one site into two identities
    Given one variants.csv row writing alts "." and another leaving the cell empty at the same site
    When the module is compiled
    Then a warning fires saying "." "states that the record has no alternate allele (VCF §1.6.1.5)"
    And it distinguishes the marker from a symbolic allele like "<DEL>"
    And the remedy offered is "Leave the cell empty instead."
    And the two keys are shown side by side where the identity split is real
    # The only VCF-conformance finding in this batch that reaches identity: `1:1:A:.` and `1:1:A` are one
    # site under two keys with different `content_signature`s and no dedup between them.

  # source: compiler/src/just_dna_compiler/compiler.py:1839
  Scenario: on an rsid-authored row the cell is wrong without the identity consequence
    Given an rsid-authored variants.csv row writing alts "."
    When the module is compiled
    Then the finding reports the cell
    And it does not claim an identity split, because both keys are the rsid
    # Claiming otherwise would be a false statement about that row.

  # source: compiler/src/just_dna_compiler/compiler.py:1213
  @code:contig_ploidy_mismatch @actionable @both_modes
  Scenario: a two-allele genotype on a contig that is not diploid there
    Given a variants.csv row with chrom "MT" and genotype "A/G"
    When the module is compiled
    Then a warning fires whose text contains "is not diploid here"
    And it suggests a single-allele genotype "for a homoplasmic/hemizygous call"

  # source: compiler/src/just_dna_compiler/compiler.py:1152
  Scenario: the check runs after resolution, because chrom is what resolution fills
    Given an rsid-authored row for the MELAS variant with genotype "A/G" and no authored chrom
    When the module is compiled
    Then the ploidy finding still fires
    # It used to live in `_cross_validate_variants`, whose second call takes errors only, so coverage
    # depended on authoring style: `MT,3243,A/G` warned and `rs199474657` — the same variant, the same
    # fake-diploid error, and the shape every drafting provider emits — was silently unchecked
    # (`@ploidy-behind-resolution`).

  # source: compiler/src/just_dna_compiler/compiler.py:1152
  Scenario: chrom X is excluded outright
    Given a variants.csv row with chrom "X" and a two-allele genotype
    When the module is compiled
    Then no ploidy finding fires
    # X is diploid in XX samples, so warning on it would be pure noise.

  # source: compiler/src/just_dna_compiler/compiler.py:1203
  @code:contig_ploidy_undecidable @carried @both_modes
  Scenario: chrom Y on a build with no pseudoautosomal table
    Given a variants.csv row with chrom "Y", a two-allele genotype, and a build with no PAR table here
    When the module is compiled
    Then a warning fires saying whether the locus is diploid "could not be decided"
    And it names both readings — hemizygous outside PAR1/PAR2, and correct inside them
    And the author can do nothing about it, which is why the code is carried
    # `chrom=Y` is not "never diploid": PAR1 and PAR2 recombine with X and are diploid in every
    # karyotype, so a two-allele genotype at Y:359845 is CORRECT and the old advice would have made the
    # annotation wrong (`@y-not-haploid`). Real instance: rs6603251 maps to X:359845 and Y:359845, and a
    # one-to-many expansion produces the Y row on its own — the author never chose it.

  # source: compiler/src/just_dna_compiler/compiler.py:1198
  @tri_state
  Scenario Outline: Y ploidy is a three-valued question answered per locus
    Given a two-allele genotype at chrom Y position <position> on a build with a PAR table
    When the module is compiled
    Then the finding is <outcome>
    Examples:
      | position  | outcome                                       |
      | inside PAR1  | none — the genotype is right                |
      | outside PAR  | contig_ploidy_mismatch                      |
      | unknown, no PAR table for the build | contig_ploidy_undecidable |

  # source: compiler/src/just_dna_compiler/compiler.py:1084
  @code:weight_sign_disagrees_with_effect @actionable @both_modes
  Scenario Outline: two encodings of one claim disagreeing about its sign
    Given a variants.csv row where <axis> is <value> and weight is <weight>
    When the module is compiled
    Then a warning fires naming both the axis value and the weight
    # Four emission sites, one finding: the legacy `state` column and the 0.3 `direction` axis are
    # checked separately because a row may carry either, and the 0.3 axes are a passthrough — nothing
    # fills `direction` from `state` at compile (`@axes-passthrough`).
    Examples:
      | axis      | value      | weight |
      | state     | risk       | 0.4    |
      | state     | protective | -0.4   |
      | direction | risk       | 0.4    |
      | direction | protective | -0.4   |
