# Derived sidecars: the facts the compiler consumes on trust, and the parts it can cross-examine.
#
# Source of truth: compiler/src/just_dna_compiler/compiler/, docs/COMPILER.md § the trust boundary
# and § "Validate-by-redundancy", docs/SCHEMAS.md's CSV families.
#
# `resolution.csv`, `frequencies.csv`, `gene_metrics.csv`, `literature.csv`, `gene_validity.csv` and
# `clinical_assertions.csv` are consumed as FACT. The compiler can re-derive what is self-verifying and
# cross-examine what is redundant; everything sourced is taken on trust from whoever produced it. That
# trust is the price of Principle 2 — a tier that never fetches cannot confirm a fetched fact.
#
# An over-broad sidecar is the ordinary result of enriching a module and then narrowing its variant
# list, so every orphan finding here is a warning in both modes and must not fail a compile.

Feature: Derived sidecars, their arithmetic, and their orphans
  Two independently-authored numbers that must agree are checkable with no reference at all. The
  compiler cannot know whether an allele count is right; it can know when a set of counts is impossible.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_frequencies
  @code:derived_row_orphan @actionable @both_modes
  Scenario Outline: a sidecar describing something the module does not carry
    Given a <table> row about a subject no variant in this module carries
    When the module is compiled
    Then a warning fires naming the count and examples
    And it is matched at <granularity>
    # One code across six tables, because the remediation is identical: the sidecar is stale or
    # over-broad, and an extra row is harmless. What differs is the join, and it differs by a property
    # of the SOURCE rather than by preference.
    Examples:
      | table                     | granularity                                       |
      | frequencies.csv           | position level — chrom:start:ref, no alt          |
      | gene_metrics.csv          | gene symbol                                       |
      | gene_validity.csv         | gene symbol                                       |
      | clinical_assertions.csv   | position level — chrom:start:ref, no alt          |
      | clin_sig_concordance.csv  | variant_key, against the AUTHORED keys            |
      | gwas_effects.csv          | variant_key, against the AUTHORED keys            |

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_frequencies
  Scenario: the position-level join is not a preference
    Given a frequencies.csv row about the same locus as a module row under a different key
    When the module is compiled
    Then no orphan is reported
    # The sidecar is keyed per-allele while a module row may be position-only or multi-allelic, so
    # `variant_key` equality would false-alarm on rows that are in fact about the same locus.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_gwas_effects
  Scenario: the variant_key join is a property of the source, and it uses the authored keys
    Given a gwas_effects.csv row and a one-to-many rsID in variants.csv
    When the module is compiled
    Then the comparison is against the authored keys, before expansion
    And no sibling of the expansion is reported as an orphan
    # A `GwasEffectRow` carries no coordinates at all, because the Catalog's association payload has
    # none — they sit on the SNP object behind a link. So the key the enricher wrote is the only thing
    # to compare, and comparing it to the expanded keys would let a one-to-many rsID report its own
    # siblings.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_clin_sig_concordance
  Scenario: an orphan in the concordance record means something narrower than elsewhere
    Given a clin_sig_concordance.csv row about a variant the module no longer carries
    When the module is compiled
    Then the warning says "The record is rebuilt whole on every run"
    And the remedy is to re-run rather than to edit the table
    # This record is rewritten whole rather than merged, so a row cannot survive a re-run of the check
    # that produced it — an orphan can only mean `variants.csv` was narrowed since.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_clin_sig_concordance
  Scenario: one function serves both halves of the concordance pair
    Given a concordance detail row and a concordance subject row that have both gone stale
    When the module is compiled
    Then both are reported in the same sentence shape
    # A detail row and a subject row go stale together and for the same reason, and two functions saying
    # so differently is how the two spellings of one finding get reported as two findings.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _check_frequency_arithmetic
  @code:faf95_exceeds_frequency @actionable @both_modes
  Scenario: a confidence bound above the point estimate it bounds
    Given a frequencies.csv row whose faf95 exceeds its own allele_frequency
    When the module is compiled
    Then a warning says a 95% CI "*lower bound* should sit at or below the point estimate"
    And it concludes the two numbers "may not describe the same denominator"
    # Float relations are warnings while integer impossibilities are errors: exact arithmetic has no
    # tolerance argument to have, but these compare numbers a source computed on possibly-different
    # denominators, and failing a good module over a rounding difference would be worse than the miss.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _check_frequency_arithmetic
  @refusal @both_modes
  Scenario: an impossible set of integer counts refuses
    Given a frequencies.csv row whose allele_count exceeds its allele_number
    When the module is compiled in either mode
    Then the compile refuses
    # A count cannot exceed its denominator, and each homozygote contributes two alleles. These columns
    # are not independent — they constrain each other — so a violation is detectable with no reference,
    # which is exactly the class of check a no-network tier can own.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _check_gene_metrics_arithmetic
  @code:oe_lof_outside_interval @actionable @both_modes
  Scenario: a point estimate outside its own confidence interval
    Given a gene_metrics.csv row whose oe_lof lies outside [oe_lof_lower, loeuf]
    When the module is compiled
    Then a warning says the point estimate and the bounds "may have come from different releases or columns"

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _check_gene_metrics_arithmetic
  @code:oe_lof_disagrees_with_counts @actionable @both_modes
  Scenario: the same quantity stored three ways, disagreeing
    Given a gene_metrics.csv row where obs_lof/exp_lof does not equal oe_lof
    When the module is compiled
    Then a warning says "these are the same quantity, so a disagreement means one of the three columns is mismapped"
    # On the recorded gnomAD payload the two agree to six decimal places for both BRCA1 and MYH7, which
    # is what makes the relation safe to check. Warnings rather than errors throughout: every value here
    # is a float that has been through a CSV, and a constraint score is advisory to begin with.

  # source: compiler/src/just_dna_compiler/compiler/allele_checks.py
  # anchor: _check_p_value_num
  @code:p_value_encodings_disagree @actionable @ladder
  Scenario: two encodings of one p-value disagreeing
    Given a studies.csv row whose p_value string reads 5e-9 and whose p_value_num is 5e-8
    When the module is compiled in best_effort mode
    Then a warning says "the string is the record; the number is what a consumer filters on"
    When the same module is compiled in strict mode
    Then the compile refuses

  # source: compiler/src/just_dna_compiler/compiler/allele_checks.py
  # anchor: _check_p_value_num
  @tri_state
  Scenario Outline: a free-form cell that denotes no definite value is skipped in silence
    Given a studies.csv row whose p_value string is <cell>
    When the module is compiled
    Then the finding is <outcome>
    # `normalize.parse_p_value` is anchored on the WHOLE cell rather than reading a leading number out of
    # commentary, so none of these disagrees with anything. The comparison is relative at 1%: the string
    # is the record and the number a transcription of it, so 5.23e-8 beside 5.2e-8 is a rounding rather
    # than a contradiction, while a wrong digit or a wrong power of ten is neither.
    Examples:
      | cell               | outcome                         |
      | "5.23e-8"          | compared, at 1% relative        |
      | "<0.001"           | skipped in silence              |
      | "NS"               | skipped in silence              |
      | "5e-8 (adjusted)"  | skipped in silence              |

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _cross_validate_studies
  @code:study_variant_orphan @actionable @both_modes
  Scenario: a study citing a variant the module does not carry
    Given a studies.csv row naming a variant absent from variants.csv
    When the module is compiled
    Then a warning fires whose text contains "Studies reference variants not in variants.csv"

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _cross_validate_studies
  Scenario: a study matches on any shared identifier, not on frozen-key equality
    Given a coordinate-keyed variant and a study referencing it by rsID
    When the module is compiled
    Then no orphan is reported
    # Keying strictly on `variant_key` would false-orphan a study that references a variant by a
    # different but co-identifying handle than the one the variant froze its key to.

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _cross_validate_studies
  Scenario: a study row that names no variant at all is not an orphan
    Given a studies.csv row grounding a binning bound and naming no variant
    When the module is compiled
    Then no orphan is reported
    # RM47: since 0.6 a citation row may ground the module or a bound rather than a locus, and a row
    # referencing nothing cannot reference something missing.

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _cross_validate_studies
  @code:duplicate_study_citation @actionable @both_modes
  Scenario: one paper cited twice for one variant
    Given two studies.csv rows sharing a variant and a pmid with no statistical_test stated
    When the module is compiled
    Then a warning fires whose text contains "Duplicate (variant, pmid)"
    # Two subject-less rows citing one paper are still a duplicate, deliberately: they are the same claim
    # written twice, and the whole point of the 0.6 relaxation is that one such row is enough.

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _cross_validate_studies
  @tri_state
  Scenario Outline: a stated statistical_test splits the dedup key, and only when both are stated
    Given two studies.csv rows sharing a variant and a pmid
    And statistical_test <first> on one and <second> on the other
    When the module is compiled
    Then the duplicate finding is <outcome>
    # RM140/S75: one paper often reports several analyses of one association with different statistics,
    # and those rows are not one claim written twice. Only BOTH stated and different suppresses — an
    # absent analysis is unknown, and unknown cannot establish distinctness (`@absent-is-not-different`).
    Examples:
      | first            | second           | outcome    |
      | "logistic"       | "Cox"            | suppressed |
      | "logistic"       | "logistic"       | reported   |
      | "logistic"       | absent           | reported   |
      | absent           | absent           | reported   |

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_literature
  @code:citation_not_in_pubmed @actionable @both_modes
  Scenario: a citation PubMed has no record of
    Given a literature.csv row whose `exists` is recorded as False
    When the module is compiled
    Then a warning names both readings — "the id is a typo or the article was retracted from the index"
    And it says the annotation resting on it should be re-examined either way
    # Not an orphan but a defect in the module, and the compiler can surface it offline because the
    # enricher already recorded the verdict as a fact. `None` is unknown and withholds.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_literature
  @code:literature_row_uncited @actionable @both_modes
  Scenario: a literature row nothing in the module cites
    Given a literature.csv row for a PMID no study, bin or pharm row cites
    When the module is compiled
    Then a warning says the row is "left out of the artifact, and left in the CSV"
    And it calls that "the pin that keeps a re-run cheap"
    # The compiler discards an uncited literature row and `literature.csv` keeps it
    # (`@uncited-literature-dropped`).

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_literature
  Scenario: every citation site counts, and the set of them is derived
    Given a module whose only citation is a `pmid` on a binning row
    When the module is compiled
    Then its literature row is not reported as uncited
    # RM47/RM132: `studies.csv` was the only citing site until binning rows gained a `pmid`, and
    # `pharm_variants.csv` is the third. Reading fewer than all of them makes every citation from the
    # site left out look like an orphan — shipping evidence the compiler then reports as stale, which is
    # worse than the honest gap the column replaced. `table_citations` walks `_CITING_TABLE_KINDS`
    # (`@roster-is-as-wide-as-the-tables-it-reads`).

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _cross_check_literature
  Scenario: PMIDs are matched through one normalizer both tiers share
    Given a literature.csv pmid cell written with a bracketed PMID wrapper
    When the module is compiled
    Then it matches a studies.csv row citing the bare digits
    # `extract_pmids` is the same normalizer the enricher pass uses, so the two sides cannot drift apart
    # (`@one-normalizer-two-spellings`). PMID and PMCID are one letter apart, and `PMC 3110566` once
    # parsed as a real unrelated PMID (`@pmid-vs-pmcid`).

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _check_quote_counter_is_current
  @code:quote_counter_stale @actionable @both_modes
  Scenario: a merge-not-clobber sidecar whose counter predates the quotes
    Given a literature.csv row reading quotes_authored=0
    And studies.csv rows carrying provenance quotes for that citation
    When the module is compiled
    Then a warning names both numbers
    And the remedy is to re-run the literature pass
    # The sidecar can be stale in exactly the way that matters and nothing said so: it is
    # merge-not-clobber, so a pass that ran while `provenance_quote` was empty wrote zero and every
    # later run treated that row as authoritative. Four published modules are in that state — 3,668
    # authored quotes, every counter reading zero — and they compile green.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _check_gene_validity_currency
  @code:gene_validity_superseded @carried @both_modes
  Scenario: a curating body re-curating is not an error in your module
    Given a gene_validity.csv carrying two curations of one gene-disease claim with different dates
    When the module is compiled
    Then a warning says an earlier row "is superseded and kept"
    And it says "Nothing is deleted and nothing is wrong"
    And the newest classification_date is published as current
    And the author can do nothing about it, which is why the code is carried
    # ClinGen's `assertion_id` embeds the curation timestamp, so a re-curated assertion arrives under a
    # different id, misses the merge key and is appended beside the row it replaces. The manifest then
    # published ["definitive", "refuted"] as a pair with nothing saying which was current. Both rows are
    # true records of what a curating body published, and deleting one would falsify the file.

  # source: compiler/src/just_dna_compiler/compiler/fact_checks.py
  # anchor: _check_gene_validity_currency
  @code:gene_validity_currency_undecidable @carried @both_modes
  Scenario: two curations and nothing to order them by
    Given a gene_validity.csv where two curations of one claim share a classification_date
    When the module is compiled
    Then a warning says "nothing orders them" and that none is called current
    And it says every classification in those groups is published
    And it says the answer is "Withheld deliberately, not skipped"
    # Two findings, never one number, because they ask a reader for different things: a superseded row is
    # the archive having moved on, and an unorderable group is the archive not having said enough to
    # tell. Picking a winner from an identifier is the repair that was refused
    # (`@a-source-recuring-is-not-a-strict-matter`).
