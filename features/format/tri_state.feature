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

  # source: schema/src/just_dna_format/release_records.py
  # anchor: _kleene_or
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

  # source: compiler/src/just_dna_compiler/compiler/allele_checks.py
  # anchor: _allele_verdict
  Scenario: the union reading over loci is the same combinator
    Given a one-to-many rsID where one locus can host the genotype and another cannot
    When the hosting question is asked of the row
    Then the answer is that it can
    # Allele membership compares the union of every locus a key resolves to, before expansion
    # (`@membership-union`). One locus that CAN host is enough, which is Kleene-OR over the loci.

  # source: schema/src/just_dna_format/release_records.py
  # anchor: _blunt_to_unknown
  Scenario: a narrowing keeps False and drops True, and the asymmetry is sound rather than cautious
    Given an answer measured over a wider span than the question asked about
    When the answer is narrowed to the interval actually asked about
    Then a `False` survives and a `True` becomes unknown
    # If nothing moved across the wider span then nothing moved inside it either. Something moving across
    # the wider span says nothing about WHERE — it may have moved entirely outside the interval the
    # caller asked about.

  # source: enricher/src/just_dna_enricher/mitomap.py
  # anchor: vcep_clin_sig
  Scenario: a total function cannot decide a three-valued answer
    Given a source value a normalizer would map to a definite member by default
    When the value is one the source did not state
    Then the withhold happens BEFORE the normalizer runs
    # `mitomap.vcep_clin_sig`: only a bracket in `MITOMAP_VCEP_CLASSES` ever reaches
    # `normalize_clin_sig`, whose fall-through is `other` — a MEMBER of the vocabulary, so an
    # undocumented `[VUS*]` passed to it would have been recorded as a confident classification rather
    # than as an unknown. A vocabulary read through `.get(x, default)` makes the map the first edit and
    # the guard an equality (`@lookup-with-a-default-hides-a-new-member`); this is that one step further
    # (`@a-withhold-cannot-be-delegated-to-a-default-that-is-a-definite-answer`).
    # Re-anchored in the second pass: this pointed at a comment about a length constant in
    # `normalize.py`, which the line-is-inside-the-file check cannot see is the wrong place.

  # source: schema/src/just_dna_format/overrides.py
  # anchor: classify_update_targets
  Scenario: a verdict function with several arms owes a reason function with the same arms
    Given a predicate that withholds for four distinct reasons
    When a finding is written
    Then the reason names which of the four applies
    And the four reasons are pairwise distinct
    # Naming one of them for all four is the shape that told a reader the locus was a different variant
    # when the truth was that the comparison did not reach a verdict (`@answered-is-not-absent`).

  # source: schema/src/just_dna_format/release_records.py
  # anchor: needs_recompile
  Scenario: an absent input is the unknown arm and a malformed one is the refusal
    Given a check whose input is absent
    When the question is put
    Then the answer is unknown and it is withheld
    Given the same check whose input is present and unreadable
    When the question is put
    Then it refuses, quoting all of what it could not read
    # `needs_recompile` answers unknown for a `None` or blank `compiled_under` before the stamp ever
    # reaches `release_version`, which refuses a malformed one quoting the whole stamp rather than its
    # last token. Two different absences, and the guard belongs at the answerer rather than in the
    # parser `sweep.py` and `cli.py` share and want strict
    # (`@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal`).
    # Re-anchored in the second pass: this pointed at the concordance comment block in `vocab.py`.

  # source: schema/src/just_dna_format/findings.py
  # anchor: classify
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

  # source: schema/src/just_dna_format/findings.py
  # anchor: classify
  Scenario: the mixed case raises because no legitimate caller can produce it
    Given a warning channel where some members carry a code and some do not
    When it is classified
    Then it raises rather than reporting
    # Every emission site in this repository names a code, so a part-classified channel is not a caller's
    # data — it is a bug. The public result models have accepted plain prose since 0.6 and Principle 3
    # keeps them accepting it, which is why the ALL-uncoded case withholds instead.

  # source: schema/src/just_dna_format/findings.py
  # anchor: __getnewargs__
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

  # source: schema/src/just_dna_format/findings.py
  # anchor: restate
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

  # The three DATA tri-states. Everything above is the house algebra as a mechanism — Kleene, the
  # withhold, `classify`, `restate`. These three are the algebra as a recorded VALUE, and the corpus had
  # none of them: five of their nine members appeared nowhere in it, including `not_covered`, which is
  # the member the gnomAD Y-PAR probe exists to justify. Found by walking `vocab` for three-member
  # `VALID_*` sets, which is a heuristic and not a rule — `VALID_RSID_STATUS` has four members and is
  # just as much a house-algebra axis.

  # source: enricher/src/just_dna_enricher/frequencies.py
  # anchor: enrich_frequencies
  @tri_state
  Scenario Outline: a frequency source has one more way to answer than a lookup does
    Given an allele at <locus> queried against gnomAD
    When the frequency table is built
    Then the row's status is <status>
    And the row is written either way, because an absent row says nothing at all
    # `not_found` is a FACT about a locus gnomAD covers: absent from the callset means absent from
    # those samples. `not_covered` is the absence of an answer — gnomAD hard-masks the Y PAR, so the
    # Y spelling of a place has no frequency to give while the X spelling of the same place does.
    # Writing the second as the first asserts a negative nobody established, which is `None` is never
    # `False` in one column.
    Examples:
      | locus                                    | status        |
      | one gnomAD covers, with counts           | "resolved"    |
      | one gnomAD covers, with no counts        | "not_found"   |
      | the Y PAR, which gnomAD masks outright   | "not_covered" |

  # source: enricher/src/just_dna_enricher/frequencies.py
  # anchor: enrich_frequencies
  @tri_state
  Scenario: the uncovered rows are aggregated into one sentence that refuses to call them absent
    Given four alleles in the Y pseudoautosomal region
    When the frequency table is built
    Then one warning fires saying they were "recorded as not_covered"
    And it says they were "not asked about and not counted as absent"
    And it ends "This is an unknown, not a zero."
    And it fires once for the run rather than once per allele

  # source: enricher/src/just_dna_enricher/enrich.py
  # anchor: _run_enrichment
  @tri_state
  Scenario Outline: the resolution table's third member is a query that cannot be narrowed
    Given a coordinate-authored row with <candidates> candidate rsID(s) at its exact allele
    When enrich back-fills the rsid
    Then the row's status is <status>
    And <label>
    # `ambiguous` is rare by construction: a one-to-many rsID is EXPANDED into distinct rows rather
    # than recorded as ambiguous, so this member is reached only by the reverse direction — several
    # dbSNP ids clustered at one allele. The pick is deterministic and the candidate list travels
    # beside it, which is what keeps a deterministic pick from reading as a fact.
    Examples:
      | candidates | status        | label                                                     |
      | 0          | "resolved"    | the rsid stays null and the coordinate is the identity    |
      | 1          | "resolved"    | the rsid is attached and no alternates are recorded       |
      | 2 or more  | "ambiguous"   | the first is picked and rsid_alternates carries them all  |

  # source: enricher/src/just_dna_enricher/clinical.py
  # anchor: _concordance_subjects
  @tri_state
  Scenario Outline: what ONE authority did when it was consulted about one subject
    Given an authority <situation> for a subject
    When the concordance rows are built
    Then that authority's call status is <status>
    And clin_sig is empty unless the status is "recorded"
    # The per-row half of the concordance record, and the half that makes the aggregate honest:
    # `no_record` is an established absence and can make the concordance `none`, while `unchecked`
    # is nobody-asked and must never be read as agreement. Folding the two would let an unprovisioned
    # snapshot look like unanimity.
    Examples:
      | situation                                        | status        |
      | that has a classification here                   | "recorded"    |
      | consulted, with nothing at this subject          | "no_record"   |
      | whose snapshot was never provisioned             | "unchecked"   |

  # source: enricher/src/just_dna_enricher/clinical.py
  # anchor: concordance_notes
  @tri_state
  Scenario: an authority nobody could ask says so in its own sentence
    Given a concordance run where one authority's snapshot is absent
    When the findings are written
    Then a finding names that authority and says it "was not consulted"
    And it carries the reason it could not be, rather than a bare absence
    And the concordance reads "unchecked" rather than reporting what the others agreed
