# Measurement bins: how an axis is divided, and what the division cannot say.
#
# Source of truth: schema/src/just_dna_format/binning.py, and docs/SCHEMAS.md's binning section.
# Every finding here is a warning in BOTH modes and never a `strict` error — `strict` means
# *reproducible artifact*, and a table whose axis is divided awkwardly reproduces exactly.

Feature: Measurement bins and the tiling axis
  A binning table maps a measured number onto a phenotype. `measure_tiling` is its own axis, separate
  from the bounds: `quantised` reads the axis as a grid of whole steps, `continuous` reads it as dense.
  Absent means the kind's default, which is not a third answer.

  # source: schema/src/just_dna_format/binning.py:1137
  @code:bin_coverage_gap @actionable @both_modes
  Scenario: a positive hole between two bins on a continuous axis
    Given a bin group read as continuous whose bins are [0.0, 0.3] and [0.5, 1.0]
    When the bins are validated
    Then a warning fires whose text contains "coverage gap for key"
    And the text names the uncovered interval as "(0.3, 0.5)"
    And nothing is repaired — the gap is reported and the rows stand

  # source: schema/src/just_dna_format/binning.py:1137
  @tri_state
  Scenario Outline: whether a hole is a gap is a three-valued question, not a comparison
    Given a bin group whose effective tiling is <tiling>
    And a hole of <hole> between two adjacent bins
    When the bins are validated
    Then the coverage-gap finding is <outcome>
    # A one-step hole is not a hole on a grid: `[0,0] [2,2]` states copy numbers 0 and 2 and the
    # missing 1 is a step, not a gap. On a dense axis any positive hole is one. And the third arm
    # withholds: a kind whose step the schema does not know (activity_score is summed onto a coarse
    # grid) is not a claim this tier can make, so `is_gap` is False by abstention rather than by
    # measurement — a different thing from "no gap found", and the reason it reads as silence.
    Examples:
      | tiling     | hole | outcome                                  |
      | continuous | 0.2  | reported                                 |
      | continuous | 0.0  | not reported — the bins meet             |
      | quantised  | 1.0  | not reported — one step is not a hole    |
      | quantised  | 3.0  | reported                                 |
      | neither    | 3.0  | withheld — the step is unknown           |

  # source: schema/src/just_dna_format/binning.py:1075
  @code:bin_tiling_inferred @actionable @both_modes
  Scenario: a fractional bound no quantised reading can hold
    Given a bin group that declares no measure_tiling
    And a bound of 0.5 on one of its rows
    When the bins are validated
    Then the group is read as continuous
    And a warning fires whose text contains "tiling inferred for key"
    And the text asks the author to "Declare `measure_tiling` on these rows"

  # source: schema/src/just_dna_format/binning.py:1086
  @code:bin_tiling_contradicted @actionable @both_modes
  Scenario: a declared grid with a value that is not on it
    Given a bin group that declares measure_tiling "quantised"
    And a bound of 0.5 on one of its rows
    When the bins are validated
    Then a warning fires whose text contains "is not a grid point"
    And the text states that "The declaration stands"
    And the bins are still read under the quantised rules
    # The declaration wins over the data, deliberately. Reading the fraction as permission to switch
    # tiling would let one cell silently re-read a published table's whole axis.

  # source: schema/src/just_dna_format/binning.py:1066
  @refusal
  Scenario: two rows of one group declaring two tilings is a refusal, not a warning
    Given a bin group where one row declares "quantised" and another declares "continuous"
    When the bins are validated
    Then a ValueError is raised whose text contains "conflicting measure_tiling for key"
    And the message tells the author to leave the column empty on rows that do not state it
    # Empty means the kind's default. A second spelling is not a third answer.

  # source: schema/src/just_dna_format/binning.py:1099
  @refusal
  Scenario: overlapping bins refuse in both modes
    Given a bin group whose bins are [0, 5] and [3, 9]
    When the bins are validated
    Then a ValueError is raised whose text contains "overlapping bins for key"
    And the message says both bins "select a phenotype for a measurement in the overlap"

  # source: schema/src/just_dna_format/binning.py:1110
  @refusal
  Scenario: two bins sharing a lower bound refuse, because the endpoint rule cannot separate them
    Given a continuous bin group whose bins are [0.1, 0.1] and [0.1, 0.3]
    When the bins are validated
    Then a ValueError is raised whose text contains "bins with the same lower bound for key"
    And the message explains that "the shared-endpoint rule (the higher bin owns it) cannot separate them"
    # The shared-endpoint rule answers an equal *upper* bound against a lower one. Two equal lower
    # bounds are an ambiguous selection, so this refuses rather than warns.

  # source: schema/src/just_dna_format/binning.py:945
  @code:measure_field_fractional @actionable @both_modes
  Scenario: a VCF field the spec types as fractional, tiled as whole numbers
    Given a bin table of kind "copy_number" with at least one group read as quantised
    When the measurement shape is checked
    Then a warning fires once per kind whose text contains "bins here are tiled as whole numbers"
    And the text offers the authored answer "`measure_tiling: continuous` on these rows"
    And the finding is stated against the kind, never per row and never per group

  # source: schema/src/just_dna_format/binning.py:945
  Scenario: the same table read as continuous answers its own boundaries and is silent
    Given a bin table of kind "copy_number" where every group declares measure_tiling "continuous"
    When the measurement shape is checked
    Then no measure_field_fractional warning fires
    # Fires only where it is still true. A group that carries a fractional bound and is therefore read
    # as continuous is silent for the same reason, without being asked.

  # source: schema/src/just_dna_format/binning.py:964
  @code:measurement_spans_bins @carried @both_modes
  Scenario: a measurement that travels with a confidence interval can cross a threshold
    Given a bin table of kind "copy_number" whose widest group states 4 resolved bins
    When the measurement shape is checked
    Then a warning fires whose text contains "bins for it to cross"
    And the text states the consumer contract's three states and that none of them is this one
    And the author can do nothing about it — the policy vocabulary RM56 needs does not exist
    # This is why the code is carried rather than actionable. The count is of bins, not of *adjacent*
    # bins: an interval crosses two bins whether or not there is a hole between them.

  # source: schema/src/just_dna_format/binning.py:964
  Scenario: a single-bin group has no threshold to cross
    Given a bin table of kind "copy_number" whose every group states one resolved bin
    When the measurement shape is checked
    Then no measurement_spans_bins warning fires

  # source: schema/src/just_dna_format/binning.py:1000
  @code:deprecated_bin_modifier @actionable @both_modes
  Scenario: the deprecated integer dosage column
    Given a copy-number bin table where a row sets modifier_cn
    When the deprecations are checked
    Then a warning fires whose text contains "`modifier_cn` is deprecated"
    And the text names "`modifier_copy_number`" as the replacement
    And it fires at most once for the rows handed over, carrying no count
    And the column still reads and behaves exactly as it did before
    # Principle 3's two-step retirement, and the 0.6 cadence amendment's condition is met: the
    # replacement exists in this same release, so the author can act on the warning today.

  # source: schema/src/just_dna_format/binning.py:560
  @refusal
  Scenario: setting both dosage columns is an error, not a precedence rule
    Given a copy-number row that sets both modifier_cn and modifier_copy_number
    When the row is validated
    Then it is rejected
    # A deprecated column that still reads needs no tie-break, because a row may not state two.
