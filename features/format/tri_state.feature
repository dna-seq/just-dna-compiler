# The house algebra: true / false / unknown, and `None` is never `False`.
#
# Source of truth: schema/src/just_dna_format/release_records.py's `_kleene_or`, and the dozen places
# that follow it — `CrossrefClient.exists`, `quotes_found`, `hosting_verdict`, `unchecked` under
# `--offline`, `unresolved`, `requires_callable`, `commercial_use`, `measure_tiling`'s third state.
#
# One rule behind all of them: give anything that answers a question three outcomes, and when the answer
# is unknown WITHHOLD — never report, never negate. Combine with Kleene semantics rather than
# withhold-on-any-unknown, because `unknown AND false` really is `false`.
#
# This feature states the algebra once. Every tier feature in this corpus carries its own `@tri_state`
# scenarios showing the rule applied to a particular question; the point of writing it here is that a
# reader meeting the fourth of those should be able to find the one statement they are all instances of.

Feature: The three-valued house algebra
  A check with two outcomes is a check that will one day report a negative it never measured. The
  vocabulary for that is not a flag but a third value, and the combinator is Kleene.

  # source: schema/src/just_dna_format/release_records.py:402
  Scenario Outline: Kleene OR — True dominates, then None, then False
    Given two tri-state answers <left> and <right>
    When they are combined
    Then the result is <result>
    # "The house algebra, not withhold-on-any-unknown." A single measured `True` beats any number of
    # unknowns, because something that definitely moved definitely moved; an unknown beside a `False`
    # cannot be reported as `False`, because nothing measured it.
    Examples:
      | left  | right | result |
      | True  | True  | True   |
      | True  | None  | True   |
      | True  | False | True   |
      | None  | None  | None   |
      | None  | False | None   |
      | False | False | False  |

  # source: enricher/src/just_dna_enricher/concordance.py:31
  Scenario: an authority that could not be consulted never contests anything on its own
    Given two authorities, one of which disagrees with the module
    And a third authority that could not be reached
    When the concordance record is built
    Then the disagreement already witnessed still stands
    And the unreachable authority produces no row of its own
    # `unknown AND false` is `false` under Kleene, so an unreachable archive does not un-see a
    # disagreement already witnessed. But on its own it produces nothing, because a question nobody
    # could put is not a finding.

  # source: compiler/src/just_dna_compiler/compiler.py:2171
  Scenario: the union reading over loci is the same combinator
    Given a one-to-many rsID where one locus can host the genotype and another cannot
    When the hosting question is asked of the row
    Then the answer is that it can
    # Allele membership compares the union of every locus a key resolves to, before expansion
    # (`@membership-union`). One locus that CAN host is enough, which is Kleene-OR over the loci.

  # source: schema/src/just_dna_format/release_records.py:412
  Scenario: a narrowing keeps False and drops True, and the asymmetry is sound rather than cautious
    Given an answer measured over a wider span than the question asked about
    When the answer is narrowed to the interval actually asked about
    Then a `False` survives and a `True` becomes unknown
    # If nothing moved across the wider span then nothing moved inside it either. Something moving across
    # the wider span says nothing about WHERE — it may have moved entirely outside the interval the
    # caller asked about.

  # source: schema/src/just_dna_format/normalize.py:97
  Scenario: a total function cannot decide a three-valued answer
    Given a source value a normalizer would map to a definite member by default
    When the value is one the source did not state
    Then the withhold happens BEFORE the normalizer runs
    # A vocabulary read through `.get(x, default)` makes the map the first edit and the guard an equality
    # (`@lookup-with-a-default-hides-a-new-member`). Delegating a withhold to a default that is itself a
    # definite answer turns "we do not know" into a claim
    # (`@a-withhold-cannot-be-delegated-to-a-default-that-is-a-definite-answer`).

  # source: schema/src/just_dna_format/overrides.py:845
  Scenario: a verdict function with several arms owes a reason function with the same arms
    Given a predicate that withholds for four distinct reasons
    When a finding is written
    Then the reason names which of the four applies
    And the four reasons are pairwise distinct
    # Naming one of them for all four is the shape that told a reader the locus was a different variant
    # when the truth was that the comparison did not reach a verdict (`@answered-is-not-absent`).

  # source: schema/src/just_dna_format/vocab.py:678
  Scenario: an absent input is the unknown arm and a malformed one is the refusal
    Given a check whose input is absent
    When the question is put
    Then the answer is unknown and it is withheld
    Given the same check whose input is present and unreadable
    When the question is put
    Then it refuses, quoting all of what it could not read
    # Two different absences, and the guard belongs at the answerer rather than in the shared parser
    # (`@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal`).

  # source: schema/src/just_dna_format/findings.py:97
  @tri_state
  Scenario Outline: `classify` over a warning channel — three cases, no flag
    Given a warning channel whose members are <coded>
    When it is classified
    Then the answer is <answer>
    # No catch-all key, in any of the three: a `warnings_summary` with a bucket for the unclassified is
    # the rejected repair wearing a different hat — it silently omits findings nobody classified while
    # looking complete, and the reader believes the digest. Withholding says less; it does not lie.
    Examples:
      | coded              | answer                                                   |
      | every one          | the full summary, whose total equals the channel's length |
      | none of them       | withheld — `([], {})`, because nothing here can tell     |
      | some of them       | raises, loudly, at the first compile that reaches it     |

  # source: schema/src/just_dna_format/findings.py:111
  Scenario: the mixed case raises because no legitimate caller can produce it
    Given a warning channel where some members carry a code and some do not
    When it is classified
    Then it raises rather than reporting
    # Every emission site in this repository names a code, so a part-classified channel is not a caller's
    # data — it is a bug. The public result models have accepted plain prose since 0.6 and Principle 3
    # keeps them accepting it, which is why the ALL-uncoded case withholds instead.

  # source: schema/src/just_dna_format/findings.py:56
  Scenario: a code survives copy and pickle, and is lost at a pydantic boundary
    Given a classified warning list
    When it is deep-copied
    Then each member keeps its code
    When the same list is assigned to a model field
    Then the subclass is stripped and the codes are gone
    # `str.__getnewargs__` hands back just the text, so the two-argument `__new__` was called with one and
    # raised `TypeError` on any `copy.deepcopy` — not hypothetical, since `_validate_spec` hands its list
    # to a caller and tells it to keep building. The pydantic stripping is a feature for serialization and
    # a trap for anything reading warnings back off a result model, so the rule is: classify BEFORE
    # constructing the model (`@finding-loses-its-code-at-a-boundary`).

  # source: schema/src/just_dna_format/findings.py:80
  Scenario: reformatting a warning goes through `restate`, which refuses an uncoded one
    Given a caller that prefixes a table name onto a finding
    When it reformats through `restate`
    Then the code travels with the new text
    Given a plain string with no code
    When it is passed to `restate`
    Then it refuses rather than inventing a code
    # A reformatting site is exactly where a code goes missing, because every other string operation on a
    # `CodedWarning` returns a plain `str` by construction. Bucketing it here would reproduce the
    # silently-partial summary the whole item exists to avoid.
