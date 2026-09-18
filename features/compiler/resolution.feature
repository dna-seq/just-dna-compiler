# Resolution — the injected table, and what the compiler will and will not do with it.
#
# Source of truth: compiler/src/just_dna_compiler/resolution.py,
# compiler/src/just_dna_compiler/compiler.py, and docs/COMPILER.md § Resolution + the mishap matrix.
#
# Principle 2: the compiler NEVER fetches. `resolution.csv` is injected, and with nothing injected the
# compiler skips with a warning rather than downloading. Every finding here is about a table that was
# handed over, not about a lookup.

Feature: Resolution from the injected table
  Three operations: fill a 1:1 key, expand a one-to-many key, and verify a pair the author wrote both
  halves of. A locus that cannot host the authored genotype is never expanded onto.

  # source: compiler/src/just_dna_compiler/compiler.py:4453
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:resolution_not_injected @actionable @both_modes
  Scenario: nothing injected, so nothing is fetched
    Given a spec directory with no resolution.csv and no injected ensembl_cache
    When the module is compiled
    Then a warning fires whose text contains "variants lacking a genomic position are left unresolved"
    And it names `just-dna-enricher` as where the table comes from
    And no network call is made
    # This is Principle 2 as a behaviour rather than a promise. The enricher emits the same code from
    # its own resolver when it has no cache, so one code covers both tiers' version of "nobody asked".

  # source: compiler/src/just_dna_compiler/compiler.py:5133
  @code:resolution_disabled @actionable @both_modes
  Scenario: the flag named after Ensembl is the master switch
    Given a complete resolution.csv beside the spec
    When the module is compiled with resolve_with_ensembl=False
    Then a warning fires saying the flag "switches off resolution entirely"
    And it publishes the row count and key count of the table it did not read
    And it says "every variant will compile with no chrom/start and match no VCF"
    And it states that there is no flag for "do not reach the network"
    # A silent success is the worst shape a mistake can take: without this the combination compiles
    # green with `chrom=None` on every weight row. The warning publishes the denominator behind the
    # flag, which is the rule a warning quantifying over a table follows (`@warning-text-is-api`).
    # Renaming the parameter is a 1.0 conversation, because it is part of a published signature.

  # source: compiler/src/just_dna_compiler/compiler.py:1419
  @code:resolution_skipped_cross_build @carried @both_modes
  Scenario: a non-GRCh38 module is not joined against a GRCh38-bound table
    Given a module declaring genome_build "GRCh37" and a positional table
    When the module is compiled
    Then a warning fires saying the fill was skipped and names the tables it did not join
    And it says those rows "keep the coordinates their author typed"
    And the author can do nothing about it until identity is build-agnostic
    # RM15: the identity minting behind these keys is GRCh38-only, so joining a table the compiler
    # cannot re-derive a key for would place rows against loci it has no way to check. Carried because
    # no authored edit reaches it — the fix is RM15, not the module.

  # source: compiler/src/just_dna_compiler/resolution.py:161
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_unresolved @actionable @both_modes
  Scenario: an rsID the table does not name
    Given a variants.csv row keyed by an rsID absent from resolution.csv
    When the module is compiled
    Then a warning fires whose text contains "not found in resolution table, position remains unset"
    And the row compiles with no coordinate

  # source: compiler/src/just_dna_compiler/resolution.py:302
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_without_resolution_label @actionable @both_modes
  Scenario: a coordinate-authored row with no rsID to label it
    Given a coordinate-authored variants.csv row the table has no rsID for
    When the module is compiled
    Then a warning fires saying the rows "stay coordinate-keyed"
    And it says explicitly "Not an error — a coordinate is a complete identity"
    # An rsID is a label on top of a coordinate, not a component of it (`@rsid-not-per-allele`). The
    # message names the place rather than the key, because `variant_key` for a resolved substitution is
    # a `ga4gh:VA.…` id and the old sentence read "Position ga4gh:VA.…" — calling a content-addressed
    # identity a position, and giving the author nothing to look up.

  # source: compiler/src/just_dna_compiler/resolution.py:319
  @code:rsid_expanded_to_multiple_loci @carried @both_modes
  Scenario: one rsID, several loci, one sentence
    Given an rsID the table maps to 3 loci, all of which can host the authored genotype
    When the module is compiled
    Then one warning fires for that rsID, not one per row
    And it distinguishes the union of loci from the number of rows emitted
    And it says what the extra rows ARE, not only that they exist

  # source: compiler/src/just_dna_compiler/resolution.py:894
  Scenario: a paralogous rsID and a pseudoautosomal one are different kinds of many
    Given an rsID mapping to X:359845 and Y:359845
    When the module is compiled
    Then the warning says this is one place spelled on two contigs
    Given an rsID mapping to two genuinely distinct loci
    When the module is compiled
    Then the warning says those are several places
    # Both produce the same row count for opposite reasons, and reporting both with "a consumer can
    # count them" told a SHOX author to count ten findings as twenty. The compiler can tell them apart
    # offline — `chrom`, `start` and the PAR intervals are all it needs (`@par-one-place`).

  # source: compiler/src/just_dna_compiler/resolution.py:894
  Scenario: the union of loci and the sum of rows come apart when the author wrote two genotypes
    Given an rsID at which the author wrote two different genotypes
    And two loci, each hostable by one of them
    When the module is compiled
    Then "maps to N loci" reports the union and "expanded to M rows" reports the sum
    # `_hostable_loci` asks the question per genotype, so two rows at one key can legitimately reach
    # different loci. The old per-row copy said "2 rows" of an artifact that gained four (S33).

  # source: compiler/src/just_dna_compiler/resolution.py:894
  Scenario: the compiler describes an expansion and never prunes it
    Given an rsID whose pseudoautosomal pair both reach the table
    When the module is compiled
    Then both loci are emitted and the finding describes them
    # Which loci reach the table is the ENRICHER's decision
    # (`enrich.select_par_representative`, which keeps the X spelling by default), because that choice
    # has to be recorded in injected data to survive `compile → reverse → compile`. A compiler-side
    # prune would fail Principle 7.

  # source: compiler/src/just_dna_compiler/resolution.py:202
  @code:locus_cannot_host_genotype @actionable @ladder
  Scenario: a locus whose alleles contradict the authored genotype is dropped from the expansion
    Given a one-to-many rsID with genotype "A/G" and a locus spelled C>T
    When the module is compiled in best_effort mode
    Then a warning fires saying the locus is "dropped from the expansion"
    And it says why: rather than "emitted as a row asserting an allele it does not have"
    # The enricher's resolver emits the same code with a shorter sentence, because only the compiler's
    # copy has a round-trip consequence to explain.

  # source: compiler/src/just_dna_compiler/resolution.py:183
  @code:locus_hosting_undecidable @carried @both_modes
  Scenario: whether a locus can host the genotype could not be decided
    Given a one-to-many rsID and a locus whose hosting verdict is unknown
    When the module is compiled
    Then a warning fires saying it "could not be decided here"
    And it names WHICH of the four ways it withheld
    And it ends "The locus is kept."
    # Hosting is three-valued (`@hosting-tri-state`): the row is carried and the reader is told the
    # comparison did not reach a verdict — never that the locus is a different variant, which is what
    # the old message asserted. Carried, because deciding it needs a reference sequence P2 keeps out of
    # the compiler.

  # source: compiler/src/just_dna_compiler/resolution.py:224
  @code:rsid_no_hosting_locus @actionable @both_modes
  Scenario: every candidate locus contradicts the genotype
    Given an rsID all of whose loci reject the authored genotype
    When the module is compiled
    Then a warning fires saying "position remains unset"
    And the row is left unresolved rather than resolved to a guess
    # The rsID and the genotype cannot both be right, so the row is left for the unresolved gate to
    # treat as the unresolved variant it is.

  # source: compiler/src/just_dna_compiler/resolution.py:333
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_ambiguous @actionable @ladder
  Scenario: the table marks an rsID ambiguous and the pick is carried as a pick
    Given a resolution row whose status is ambiguous with candidates listed in rsid_alternates
    When the module is compiled in best_effort mode
    Then a warning says the rsID "resolved as AMBIGUOUS" and names the candidates
    And it says the pick "is a pick, not a finding."

  # source: compiler/src/just_dna_compiler/resolution.py:1134
  # text: compiler/src/just_dna_compiler/resolution_findings.py
  @code:rsid_coordinate_disagrees @actionable @ladder
  Scenario: an authored pair the table contradicts
    Given a variants.csv row carrying both an rsID and a coordinate
    And a resolution table that maps that rsID elsewhere
    When the module is compiled in best_effort mode
    Then a warning fires containing "(reference disagreement"
    And the authored coordinate is kept
    # Three causes, and one window read cannot separate them (`@ref-mismatch-causes`). The enricher's
    # twin of this code adds the dbSNP merge reading, which is the one the compiler cannot check.

  # source: compiler/src/just_dna_compiler/compiler.py:1436
  @code:positional_identity_contradicted @actionable @both_modes
  Scenario: a positional row whose own coordinate contradicts the table is left alone
    Given a haplotypes.csv row with a start the resolution table disagrees with
    When the module is compiled
    Then a warning fires saying the rows "are left exactly as authored"
    And nothing is filled or overwritten
    # `haplotypes.csv` drafted from CPIC carries a `start` with no `chrom`, so the fill has to complete
    # a half-coordinate — and completing it from a locus whose `start` disagrees would build a
    # coordinate neither side stated. Fill only what the author left empty; a cell the author wrote is
    # never overwritten, which is `enrich`'s inject-only doctrine and what makes the fill idempotent.

  # source: compiler/src/just_dna_compiler/compiler.py:1582
  @code:positional_rows_unjoinable @actionable @both_modes
  Scenario: the residue the positional fill could not place
    Given a pharm_variants.csv where 4 of 12 rows are still unplaced after the fill
    When the module is compiled
    Then a warning fires containing "have no chrom+start"
    And it reports counts per table, never a line per row
    And it says which of the three reasons applies
    # `have no chrom+start` is substring-matched by a downstream trust badge (S13), so it is a contract
    # rather than prose. The counts are also published structurally in `manifest.compilation`, because
    # anything a consumer can only learn from a warning string is an unversioned interface (RM44).

  # source: compiler/src/just_dna_compiler/compiler.py:1482
  @tri_state
  Scenario Outline: why a positional row is still unplaced is a three-way answer
    Given a positional table after the fill where a row is unplaced because <cause>
    When the module is compiled
    Then the reason sentence says <sentence>
    # The third branch is why `fill_applied` is a parameter rather than inferred from placeability:
    # asserting "the compiler looked and would not pick" about a lookup that never happened is a
    # fabricated diagnosis in a document a catalog reads.
    Examples:
      | cause                                     | sentence                                      |
      | nothing in the table names the key        | run enrich first — an enrich run fixes it     |
      | the table names it at several loci        | the compiler leaves them rather than picking  |
      | the fill never ran at all                | the coordinates may be right there, untried   |

  # source: compiler/src/just_dna_compiler/compiler.py:1482
  Scenario: a half coordinate is counted apart, because it is the more deceptive shape
    Given a haplotypes.csv row carrying a start with no chrom
    When the module is compiled
    Then the warning notes it "reads as a position and is not one"

  # source: compiler/src/just_dna_compiler/resolution.py:311
  Scenario: there is deliberately no expansion in a positional table
    Given a one-to-many rsID on a pharm_variants.csv row
    When the positional fill runs
    Then the row stays unplaced and is counted
    And it is not multiplied across loci
    # Expanding here would multiply a pharm annotation's `(variant_key, drug, genotype, …)` key across
    # loci the author never named. One usable locus fills; several filter by hosting verdict, and if
    # that leaves one it fills, otherwise nothing does.

  # source: compiler/src/just_dna_compiler/compiler.py:1482
  @parity
  Scenario: the fill runs on both sides, and before the report
    Given any module with a positional table
    When `validate` runs
    Then the fill runs there too and the report describes the residue rather than the whole table
    # Running the fill on one side only would have the pre-flight name a gap the compile has already
    # closed, and the pre-flight would then be the more OPTIMISTIC of the two commands — the
    # disagreement direction the parity rule exists to prevent.
