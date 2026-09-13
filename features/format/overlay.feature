# The author's overlay — `overrides.csv`, a correction applied on top of a derived table.
#
# Source of truth: schema/src/just_dna_format/overrides.py, docs/SCHEMAS.md's overrides section, and
# docs/ENRICHER.md § "The author's overlay, read but never written".
#
# Two rules shape every finding below. The overlay is APPLIED and never merged into the table it
# corrects (`@overlay-not-inside`), so reverse emits the post-overlay table *and* the overlay, and the
# overlay applies twice. That is why no finding here may be computed from its own effect: a count over
# what a suppression removed reads 12 on lap 1 and 0 on lap 2.

Feature: The author's overlay and what a correction reaching nothing means
  An `update` names a row in a derived table and changes a cell. Whether it reached one has several
  readings, and the tier separates only the readings it can answer.

  # source: schema/src/just_dna_format/overrides.py:962
  @code:overlay_rows_suppressed @actionable @both_modes
  Scenario: a suppression leaves no trace in the artifact, so it leaves one in the warnings
    Given an overrides.csv with 40 suppress rows against "frequencies.csv" sharing one reason
    When the module is compiled
    Then one warning fires whose text contains "suppress override(s) remove"
    And its count is 40 — one line per reason, naming every row it stands for
    And the count is taken over the overlay's own rows, never over the rows removed
    # Aggregated by reason, which is why `reason` is a required column. An `update` leaves the changed
    # cell and an `insert` leaves the new row; only a suppression is invisible from the artifact alone.

  # source: schema/src/just_dna_format/overrides.py:962
  @parity
  Scenario: the suppression count is the same on both laps of a round trip
    Given a module whose overrides.csv suppresses 12 rows of a derived table
    When the module is compiled, reversed, and compiled again
    Then both compiles report the same count of 12
    # The reversed module's derived table is already post-overlay, so on lap 2 the suppress matches
    # nothing. A count over the effect would move `manifest.compilation.warnings`; a count over the
    # overlay file, which round-trips unchanged, does not.

  # source: schema/src/just_dna_format/overrides.py:914
  @code:overlay_update_unmatched @actionable @both_modes
  Scenario: an update reaching no row, where the caller cannot ask whether the subject is reachable
    Given an update override naming a row a derived table does not carry
    And no reachability predicate for that table
    When the overlay targets are classified
    Then one aggregated warning fires whose text contains "update override(s) name a row"
    And it names all three readings and separates none of them
    And neither an insert nor a suppress reports this
    # Withholding is the house algebra: an unknown answer is neither reported as a fault nor negated.
    # The three readings are a mistyped subject, a source that stopped publishing the row, and a row
    # the compiler dropped before the parquet so reverse could not rebuild it.

  # source: schema/src/just_dna_format/overrides.py:866
  @code:overlay_update_unmatched @actionable
  Scenario: the same finding, narrowed, where the subject IS reachable
    Given an update override naming a row a derived table does not carry
    And a reachability predicate saying the subject is cited or positioned
    When the overlay targets are classified
    Then the warning says the table "does not carry, though this module could carry it"
    And it tells the author to re-run the enrichment pass that writes the table
    # The reachable bucket is the narrow, useful one: the artifact *could* hold the row, so the sidecar
    # is short rather than the correction wrong. A mistyped subject lands in the unreachable bucket,
    # because a mistyped pmid is also an uncited one.

  # source: schema/src/just_dna_format/overrides.py:877
  @code:overlay_update_target_unreachable @actionable @both_modes
  Scenario: an update naming a row no artifact of this module can carry
    Given an update override whose subject is neither cited nor positioned
    When the overlay targets are classified
    Then a warning fires whose text contains "no artifact of this module can carry"
    And it names two readings and separates neither
    And it fires whether or not the row is present today
    # Reachability is a property of the MODULE, so it answers the same on both laps
    # (`@lap-stable-means-a-property-of-the-module`). "Did it match" is exactly the quantity a reverse
    # moves, which is why only the short-table finding is conditioned on it.

  # source: schema/src/just_dna_format/overrides.py:813
  @code:overlay_answer_vindicated @actionable @both_modes
  Scenario: an answered subject the authorities have since stopped contesting
    Given an overrides.csv answering a contested subject in "clin_sig_concordance.csv"
    And the concordance record no longer holds that subject
    When the overlay targets are classified
    Then a warning fires whose text contains "are no longer contested"
    And it says the overlay row "can be retired" and that nothing forces it
    And no generic unmatched warning fires for that subject
    # The one table where an unreached update has a single reading: the record holds contested subjects
    # only and is rewritten whole, so leaving it means the contest ended. It says nothing about who was
    # right about the biology — the authorities agreed, which is an observation about the record.

  # source: schema/src/just_dna_format/overrides.py:824
  @tri_state
  Scenario Outline: the reachability predicate is three-valued by absence
    Given an update override that reached no row in <table>
    And a reachability predicate that answers <reachable>
    When the overlay targets are classified
    Then the finding is <finding>
    Examples:
      | table                      | reachable      | finding                                   |
      | literature.csv             | yes            | overlay_update_unmatched, narrowed        |
      | literature.csv             | no             | overlay_update_target_unreachable         |
      | literature.csv             | cannot ask     | overlay_update_unmatched, all three readings |
      | clin_sig_concordance.csv   | no             | overlay_answer_vindicated                 |

  # source: compiler/src/just_dna_compiler/compiler.py:3802
  @code:overlay_targets_missing_table @actionable @both_modes
  Scenario: an overlay against a table the module does not carry
    Given an overrides.csv correcting "frequencies.csv"
    And a module carrying no frequencies.csv
    When the module is compiled
    Then a warning fires whose text contains "which this module does not carry"
    And it states that "An overlay lies on top of a derived table and never creates one"
    # An `insert` creates a ROW, never a TABLE. The remedy named is to run the pass that writes the
    # table, or to drop the override rows.

  # source: schema/src/just_dna_format/overrides.py:560
  @refusal
  Scenario: one key group written under two spellings, carrying two operations, refuses
    Given two overrides.csv rows whose member differs only by a trailing space
    And the two rows carry different operations
    When the overlay's coherence is checked over the groups the MODEL sees
    Then it refuses with a message naming both the spellings and the stored key
    And the message states that "a key group carries exactly one operation"
    # Matched as the model STORES the key, never as the author spelled it: `apply_overrides` groups on
    # the stripped value while the duplicate check keyed on the raw one, so two rows were distinct to
    # the check and one group to the apply, where the second silently won (`@overlay-not-inside`).

  # source: schema/src/just_dna_format/overrides.py:588
  @refusal
  Scenario: one cell stated twice under two spellings of its key refuses rather than letting one win
    Given two update rows naming one field under two spellings of one stored key
    When the overlay's coherence is checked over the groups the model sees
    Then it refuses with a message saying "the later row would silently win; state each cell once"
