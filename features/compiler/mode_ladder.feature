# The mode ladder, the parity rule, and what `strict` actually means.
#
# Source of truth: compiler/src/just_dna_compiler/compiler.py, and docs/COMPILER.md
# § "What the compiler can and cannot validate".
#
# `strict` means *reproducible artifact*. It does NOT mean "be harsher": a finding about a module that
# reproduces perfectly does not escalate, however much an author might want it to. That single sentence
# decides every severity in this corpus.
#
# **There are two escalation mechanisms and they are not the same thing**, which is the distinction a
# reader most often loses. A *mode ladder* puts ONE sentence in the warning channel under `best_effort`
# and in the error channel under `strict` — measured 2026-09-13, four codes. The resolution tier instead
# has a THIRD channel, `ResolutionOutcome.strict_errors`, which carries a **different, longer sentence**
# than the warning beside it: the warning says what happened, the refusal says what it costs the round
# trip and is printed under a `strict resolution:` prefix. Three codes pair that way. Counting them as
# ladder members would claim a text that does not exist; counting them as warn-only would claim a
# compile that succeeds.

Feature: The mode ladder and validate/compile parity
  `validate` is a pre-flight for a compile in the same mode. The contract is that `validate(strict=x)`
  and `compile(strict=x)` reach the same verdict — not that the two modes of `validate` differ by a
  fixed amount.

  # source: compiler/src/just_dna_compiler/compiler.py:2399
  @ladder
  Scenario Outline: the four checks whose own sentence changes channel
    Given a module whose only finding is <finding>
    When it is compiled in best_effort mode
    Then the finding is a warning and the compile succeeds
    When the same module is compiled in strict mode
    Then the same sentence is an error and the compile refuses
    Examples:
      | finding                                                     |
      | a genotype naming an allele the locus does not have         |
      | an effect_allele naming an allele the locus does not have    |
      | a study's effect_allele naming an allele its locus lacks     |
      | a p_value string disagreeing with the p_value_num beside it  |

  # source: compiler/src/just_dna_compiler/compiler.py:2322
  Scenario: provenance shapes the message and cannot shape the severity
    Given a genotype naming an allele the locus does not have
    When the allele list came from resolution.csv rather than from the row
    Then the message says the resolving source's allele list "may also be incomplete"
    And the severity is the mode ladder either way
    # A resolved mismatch may be an incomplete source rather than a bad row, so failing by default
    # would let a source's gap sink a correct module. An authored mismatch looks decidable and is not:
    # `reverse_module` writes `ref`/`alts`, and a one-to-many rsid reverses into N rows each carrying
    # its own locus's alleles beside the ONE authored genotype, so exactly one can match. Escalating
    # unconditionally would break Principle 7's fixed point with a lint.

  # source: compiler/src/just_dna_compiler/compiler.py:5260
  @strict_only @refusal
  Scenario: unresolved genomic positions refuse under strict and warn otherwise
    Given a module with 3 variants the resolution table does not place
    When it is compiled in best_effort mode
    Then the rows compile with no chrom or start and the finding is a warning
    When it is compiled in strict mode
    Then the compile refuses with a message containing "strict compile:"
    And the message names the count of variants that have unresolved genomic positions

  # source: compiler/src/just_dna_compiler/compiler.py:4439
  @parity @strict_only
  Scenario: the pre-flight predicts that refusal rather than discovering it at compile
    Given the same module with 3 unplaced variants
    When `validate --strict` runs
    Then it refuses with the same "strict compile:" message the compile would produce
    # The standing parity rule: `validate_spec` must refuse everything `compile` refuses. A green
    # `validate` followed by a failing `compile` is the sequence the rule exists to prevent, and this
    # file has closed that gap four times (`@validate-refuses-all`).

  # source: compiler/src/just_dna_compiler/compiler.py:6414
  @strict_only @refusal
  Scenario: the one recorded judgement strict acts on
    Given a verification.json recording a genome_build_agreement finding
    When the module is compiled in strict mode
    Then the compile refuses with a message containing "strict compile: verification.json records"
    And the message names how many rows, of how many subjects, disagree about coordinates
    When the same module is compiled in best_effort mode
    Then the same finding is reported as a warning
    # A judgement another tier RECORDED is a fact `strict` may gate on, and this is the only check
    # where it does: two authored files contradict each other about the build
    # (`@a-recorded-judgement-is-a-fact`). Every other verification finding is a disagreement with a
    # SOURCE, where the archive is the stale side often enough that escalating would be wrong.

  # source: compiler/src/just_dna_compiler/compiler.py:2807
  @strict_only
  Scenario: strict reports an unusable symbolic allele where best_effort drops the row
    Given a variants.csv row whose alts carries a lengthless "<DEL>"
    When the module is compiled in best_effort mode
    Then the row is dropped from the artifact and a warning says so
    When the module is compiled in strict mode
    Then the compile refuses and nothing is dropped
    # Not a severity promotion: the *behaviour* differs. `strict` cannot silently shorten a table, so
    # it refuses instead of dropping — which is also why the pre-flight asks for the drop set under
    # `strict` and gets an empty one.

  # source: compiler/src/just_dna_compiler/compiler.py:2835
  @refusal @both_modes
  Scenario: a drop that would empty a table outright refuses in both modes
    Given a variants.csv every row of which carries an unusable symbolic allele
    When the module is compiled in best_effort mode
    Then the compile refuses with a message containing "Refused in both modes"
    And the message says the compile "would quietly produce a module that annotates nothing at all"
    # The drop exists so a module can lose one unusable rule and still say the rest. A table that loses
    # every row says nothing, and says it silently. Computed in the check rather than at the point of
    # application, so the pre-flight predicts it — the first cut refused inside the drop, which only
    # `compile_module` performs, and produced exactly the green-validate-then-failing-compile sequence.

  # source: compiler/src/just_dna_compiler/compiler.py:1316
  @refusal @both_modes
  Scenario: a coordinate past the end of its contig is false, not unreproducible
    Given a variants.csv row at chr1 position 249,200,000 under genome_build GRCh38
    When the module is compiled in either mode
    Then the compile refuses with a message containing "row(s) place a variant past the end of"
    And it says the position "reads as an un-lifted" GRCh37 coordinate under a GRCh38 heading
    And it offers `hint recover` as the remedy rather than a conversion
    # Error in both modes rather than a ladder: `strict` means reproducible, and these rows are not
    # unreproducible, they are false. Nothing downstream catches them either — a VRS id minted at an
    # impossible position is a correct digest of the wrong input, exactly as the 3,038-row off-by-one
    # was. The remedy is an rs-number, which resolves into a coordinate the compiler can cross-examine,
    # where a converted position is its own only witness.

  # source: compiler/src/just_dna_compiler/compiler.py:1321
  @refusal @both_modes
  Scenario: a contig only one build names
    Given a variants.csv row on contig "GL000209.1" recorded as GRCh38
    When the module is compiled in either mode
    Then the compile refuses with a message containing "which is a top-level sequence of"
    And it says "A coordinate on it means nothing here"
    # Entirely about unplaced scaffolds: the 25 primary contigs are spelled identically in both builds.
    # A shared scaffold, a patch, an alt locus or an unversioned accession settles nothing and is left
    # alone.

  # source: compiler/src/just_dna_compiler/compiler.py:1331
  Scenario: where the build is declared is not the same file for both shapes
    Given a wrong-build coordinate on an authored table
    When the refusal is written
    Then the remedy names declaring `genome_build` for the whole module
    Given the same coordinate on a machine-written sidecar
    When the refusal is written
    Then the remedy names deleting the sidecar and re-running enrich instead
    And it says the build "is a per-row column here, not the module's declaration"

  # source: compiler/src/just_dna_compiler/compiler.py:3826
  @parity
  Scenario: validate takes a mode for exactly one reason
    Given any module
    When `validate` runs without a mode
    Then it is the pre-flight for a best_effort compile and for no other
    # Several checks are a mode ladder, so a modeless `validate` would be a pre-flight for the *other*
    # compile. Under `strict` the unresolved-position aggregate is genuinely ADDED rather than
    # promoted, because the per-row warning fires in both modes.

  # source: compiler/src/just_dna_compiler/compiler.py:5396
  @parity
  Scenario: the one check the pre-flight does not run, and why that is not a parity break
    Given a module whose frequencies.csv puts a pathogenic variant above the BA1 threshold
    When `validate --strict` runs
    Then it is silent about BA1
    When the module is compiled
    Then a clin_sig_contradicts_frequency warning fires
    # The parity rule is about REFUSALS: `validate_spec` must refuse everything `compile` refuses. This
    # check warns in both modes and refuses in neither, so no refusal is hidden from the pre-flight.
    # It is the resolved-rows exemption — the check needs the frequency rows matched against resolved
    # coordinates, which only the compile holds (`@parity-by-check`, `@validate-refuses-all`).

  # source: compiler/src/just_dna_compiler/resolution.py:45
  # text: compiler/src/just_dna_compiler/compiler.py
  Scenario: resolution has three severity channels, not two
    Given a module whose resolution table produces one finding of each severity
    When it is compiled in best_effort mode
    Then a `warnings` finding is reported and the compile succeeds
    And a `strict_errors` finding is reported as a warning and the compile succeeds
    And an `errors` finding refuses the compile
    When it is compiled in strict mode
    Then the `strict_errors` finding refuses instead, prefixed "strict resolution:"
    # Only `withdrawn` lands in `errors`: every other finding leaves the annotation intact, while a
    # retracted variant may leave it describing nothing.

  # source: compiler/src/just_dna_compiler/resolution.py:1067
  @ladder
  Scenario: the strict half of a resolution finding is a different sentence, not the same one louder
    Given an authored rsID and coordinate the resolution table contradicts
    When the module is compiled in best_effort mode
    Then the warning ends at "(reference disagreement)."
    When the module is compiled in strict mode
    Then the refusal continues "The authored value is kept, so the table's position does not survive a"
    And it offers "Fix one of the two, or compile without strict."
    # The authored value wins in BOTH modes — the row keeps what its author wrote — which is exactly why
    # the round trip cannot reproduce the injected table. A contradiction is an instability, not a
    # difference of opinion.
    #
    # DRIFT: docs/COMPILER.md:155's validate-by-redundancy table gives this check the severity
    # "warning" with no qualifier, while the mishap matrix at docs/COMPILER.md:1298 gives it
    # "⚠️ warning / ❌ refuses". Both are ours and they disagree about whether `strict` builds. The
    # matrix is the one the code agrees with.

  # source: compiler/src/just_dna_compiler/resolution.py:157
  @ladder
  Scenario: dropping a locus that cannot host the genotype refuses under strict
    Given a one-to-many rsID one of whose loci cannot host the authored genotype
    When the module is compiled in best_effort mode
    Then the locus is dropped and a warning names it
    When the module is compiled in strict mode
    Then the compile refuses saying dropping it "makes the compile non-reproducible from the injected table"
    # Dropping a locus makes the emitted table smaller than the injected one, so the round trip cannot
    # reproduce it. `strict` must refuse rather than silently prune.

  # source: compiler/src/just_dna_compiler/resolution.py:528
  @ladder
  Scenario: an ambiguous rsID label is a deterministic pick, and strict will not build on one
    Given a resolution row marking an rsID ambiguous
    When the module is compiled in best_effort mode
    Then a warning says the pick "is a pick, not a finding."
    When the module is compiled in strict mode
    Then the compile refuses saying the label is "a deterministic pick among equals, not a fact"
    # The one row of the mishap matrix that is round-trip STABLE and still refuses: the enricher writes
    # a single row carrying the pick while the candidate list rides in `rsid_alternates`, which is
    # provenance and outside the fact set. Nothing is lost; `strict` declines to rest an all-or-nothing
    # artifact on a coin toss.

  # source: compiler/src/just_dna_compiler/resolution.py:279
  @refusal @both_modes @parity
  Scenario: a withdrawn rsID refuses in both modes, and the pre-flight asks it too
    Given a resolution row recording an rsID as retracted by dbSNP
    When the module is compiled in best_effort mode
    Then the compile refuses
    When `validate` runs in either mode
    Then it refuses too
    # A merged or absent rsID leaves the annotation intact — the module is dated, or the label is
    # unserved. A withdrawn one is dbSNP repudiating the variant, so carrying it under `best_effort`
    # would publish a claim its own source has retracted. `validate` reads the injected table's own
    # column and no resolved row, so the compile-only exemption does not cover it (RM207).

  # source: compiler/src/just_dna_compiler/resolution.py:278
  Scenario: both refusals are asked over the AUTHORED keys, not the expanded ones
    Given a one-to-many rsID that is also recorded as withdrawn
    When the module is compiled
    Then the refusal still fires
    # An expansion rewrites `variant_key` to the locus's `ga4gh:VA.…` id, and a lookup of that id in a
    # table keyed by the rsID the author wrote misses every time — so the both-modes refusal was
    # silently skipped on exactly the rows that expanded (RM207).
