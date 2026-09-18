# The nine warning codes the enricher's own resolver emits, which are the same nine the compiler emits
# from its injected-table twin — and seven of the nine are a DIFFERENT SENTENCE under the same code.
#
# The first drafting pass closed `VALID_WARNING_CODES` as an equality per code, and a code is not a
# text: every one of these nine was accounted for by a scenario in `features/compiler/resolution.feature`
# that quotes the compiler's words. A consumer greps the sentence (`@warning-text-is-api`), and the
# sentence `enrich` prints for `rsid_unresolved` shares no phrase with the one `compile` prints for it.
#
# `test_a_code_emitted_by_two_tiers_has_a_scenario_in_each` is what found the nine and what keeps a
# tenth from arriving unnoticed. Where the two tiers agree verbatim the scenario says so, because
# "identical" is a fact about the pair rather than a reason to write nothing.

Feature: What the enricher's resolver says, in its own words
  `enrich` resolves against an injected Ensembl reference; `compile` resolves against an injected
  `resolution.csv`. The findings are the same findings — the compiler's own comment at the second site
  says the members are shared deliberately, because the remedy is the same and `compile_module` puts
  both paths' warnings in one channel. What is not shared is the wording, and the wording is the part a
  consumer matches on.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: resolve_variants
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:resolution_skipped_cross_build @carried @tri_state
  Scenario: a module on an assembly the resolver is not bound to
    Given a module whose genome_build is "GRCh37"
    When enrich resolves it against an injected Ensembl reference
    Then a warning fires saying "compiler is GRCh38-bound, module genome_build is"
    And it says "positions are not re-resolved cross-build (RM15)."
    And no position is re-resolved, so nothing is filled and nothing is contradicted
    # Carried: no edit to the spec directory clears it, because the build is the module's and the
    # reference is GRCh38's. The compiler's twin says the same thing about the positional fill instead
    # — one code, two sentences, two scopes.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: resolve_variants
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:resolution_not_injected @actionable
  Scenario: nothing was injected to resolve against
    Given no Ensembl reference cache on any of the searched paths
    When enrich resolves a module that has rows needing a position
    Then a warning fires saying "no reference cache found"
    And it names the two environment variables and the argument that would provide one
    And every row is returned unpatched rather than marked not_found
    # Nobody-asked is a third state beside asked-and-failed and asked-and-absent
    # (`@unreachable-not-absent`). The compiler's sentence for this code names `resolution.csv` and
    # points at the enricher; this one names the cache and points at the operator.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: resolve_variants
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:resolution_not_injected @actionable
  Scenario: a reference that is present and cannot be opened
    Given an Ensembl reference path that raises when it is connected to
    When enrich resolves a module that has rows needing a position
    Then a warning fires saying "Ensembl resolution skipped:" and carrying the reason verbatim
    And it is the same code as the absent-cache case, because the remedy is the same
    # A present-and-unreadable input is the refusal arm and an absent one is the unknown arm
    # (`@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal`); here both are
    # reported, and the sentence is what separates them.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: resolve_variants
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:locus_cannot_host_genotype @actionable
  Scenario: one locus of an rsID that cannot carry the authored call
    Given an rsID mapping to three loci, one of which cannot host genotype "A/G"
    When enrich expands it
    Then a warning fires saying that locus is "which cannot host the authored genotype"
    And it says "that locus is dropped from the expansion"
    And the other two loci are still expanded
    # The compiler's sentence continues past that phrase to say the row is not emitted as an assertion;
    # this one stops. Same code, same remedy, one clause of difference.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: resolve_variants
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_no_hosting_locus @actionable
  Scenario: no locus of an rsID can carry the authored call
    Given an rsID whose every locus is refused by the hosting check for genotype "A/G"
    When enrich expands it
    Then a warning fires saying none of its "loci can host the authored genotype"
    And it says "position remains unset"
    And the row is kept unpatched rather than dropped
    # Byte-identical to the compiler's, which is worth stating rather than assuming: the two sentences
    # were written separately and agree, and nothing today would notice if one of them drifted.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: resolve_variants
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_expanded_to_multiple_loci @carried
  Scenario: an rsID that names more than one place
    Given an rsID mapping to two loci that can both host the authored genotype
    When enrich expands it
    Then a warning fires saying it "maps to" two loci and was "expanded to" two rows
    And it says the rows are "one per locus, each keyed by its coordinate"
    And each emitted row is keyed by its own coordinate rather than by the rsID
    # Deliberately per authored row and deliberately NOT converged with the compiler's twin, which S33
    # moved to one accumulated sentence per rsID with the real row total: this is the deprecated
    # `ensembl_cache` route, removed at 1.0, and the modules reaching it report `expanded_keys` and
    # `expanded_rows` as `None` rather than as a count.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: resolve_variants
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_without_resolution_label @actionable
  Scenario: a coordinate-authored row the reference has no rsID for
    Given a variants.csv row authored as a coordinate with no rsid
    When enrich looks the position up and the reference names no id there
    Then a warning fires saying "no rsid found in" the reference it consulted
    And the row stays coordinate-keyed, which is a complete identity on its own
    # The compiler's sentence for this code is an aggregate over rows with the reassurance that it is
    # not an error; this one is per position and says neither. The finding is the same and a consumer
    # matching either string finds only one of the two tiers.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: _lookup_positions_by_rsid
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_unresolved @actionable
  Scenario: an rsID the injected snapshot does not carry
    Given a partial Ensembl snapshot that has no record of the queried rsID
    When enrich looks it up
    Then a warning fires saying it is "not in" "the injected Ensembl snapshot"
    And it does not say the rsID is absent from Ensembl, because a partial snapshot cannot know that
    And it does not say whether the position stays unset, because a live leg may still answer
    # Three sentences the corpus's compiler-side scenario holds none of: that one says "not found in
    # resolution table, position remains unset". The withheld consequence is S61 — the one caller that
    # reads these states it once, after both legs, and this site genuinely does not know it yet.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: _check_rsid_coord_consistency
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_coordinate_disagrees @actionable
  Scenario: an authored rsID whose coordinate the reference contradicts
    Given a row authoring both an rsID and a coordinate the reference does not pair
    When enrich checks the pair bidirectionally
    Then a warning fires carrying `coordinate_disagreement`'s sentence
    And the second arm reports the other direction, saying "Ensembl reports"
    And it offers "may be a dbSNP merge/build difference" rather than calling either side wrong
    # Never fatal here, which is the whole difference from the compiler's twin: the same code is a
    # `strict` refusal under `compile` because the authored value wins and the table's position is then
    # lost to the round trip. In the enricher there is no artifact to be unreproducible.

  # source: enricher/src/just_dna_enricher/resolver.py
  # anchor: _lookup_rsids_by_position
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_ambiguous @actionable
  Scenario: one position, ref unspecified, matching several dbSNP ids
    Given a lookup by chrom and start with no ref at a multi-allelic site
    When the reverse map is built
    Then a warning fires at that position saying the "rsid resolved as AMBIGUOUS"
    And it says the pick "is a pick, not a finding." and offers "Specify ref to disambiguate."
    And it fires once per position rather than once per colliding id
    # The `ORDER BY` fixes which id wins, so the answer is stable; stable is not the same as right, and
    # the warning is what keeps a deterministic pick from reading as a fact
    # (`@a-withhold-cannot-be-delegated-to-a-default-that-is-a-definite-answer`).
