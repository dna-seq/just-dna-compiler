# The meta-table (meta.csv, 0.8): members expanded into the rows they match, and the two findings the
# expansion can raise.
#
# Source of truth: compiler/src/just_dna_compiler/compiler/meta.py, schema/src/just_dna_format/meta.py,
# docs/COMPILER.md § "The meta-table", docs/SCHEMAS.md § "The meta-table".
#
# Standing contract: expansion reads the authored rows after the symbolic-allele drop and before
# resolution, on both sides, so `validate` and `compile` reach the same sentence and the compile
# de-duplicates it (`@parity-by-check`). Neither finding is a mode ladder.

Feature: The meta-table's members and what they match
  A member is `table[column=value, …]` over variants, diplotypes, pharm_variants or allele_function. The
  compiler expands it so a consumer evaluates no rule, and says so when a member matches nothing.

  # source: compiler/src/just_dna_compiler/compiler/meta.py
  # anchor: build_meta
  @code:meta_selector_matches_nothing @actionable @both_modes @parity
  Scenario: a member that matches no row of its table
    Given a meta.csv row whose member is "variants[variant_key=rs99999999]"
    And a variants.csv carrying no row with that variant_key
    When the module is compiled
    Then a warning fires whose text contains "matches no row of"
    And it states that "A selector that matches nothing is almost always a typo"
    And the manifest's meta_selectors records that member with a match count of zero
    # Never a refusal: the module still compiles, and the meta row's match list is empty.

  # source: compiler/src/just_dna_compiler/compiler/meta.py
  # anchor: build_meta
  @code:meta_member_allele_ambiguous @actionable @both_modes @tri_state
  Scenario: a bare-locus member on a direction row whose locus disagrees on its effect allele
    Given a meta.csv row stating a direction for the member "variants[variant_key=rs3184504]"
    And variants.csv rows of that locus stating two different effect_allele values
    When the module is compiled
    Then a warning fires whose text contains "do not share one effect_allele"
    And it states that "The direction is withheld from the"
    And meta.parquet keeps the authored direction and lists "direction" in that row's withheld
    # Three-valued: a locus whose rows share one effect_allele bears that allele (no finding); one
    # whose rows disagree or state none is unknown, so the direction is withheld, never guessed; a
    # tag or gene selector fixes no allele at all and is refused by the model.
