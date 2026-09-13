# Identity: `variant_key`, VRS allele ids, and the build they are relative to.
#
# Source of truth: compiler/src/just_dna_compiler/compiler.py, schema/src/just_dna_format/identity.py,
# schema/src/just_dna_format/vrs.py, docs/SCHEMAS.md's hash family, docs/COMPILER.md § the VRS verify
# pass.
#
# `derive_variant_key` order is rsid → VA (coordinate substitution only) → `chrom:start:ref[:alts]`
# (`@vkey-precedence`). `genome_build` lives in the manifest and in no parquet column, so every mint
# call is passed the row's build (`@build-in-manifest-only`).

Feature: Identity and the VRS verify pass
  A `ga4gh:VA.…` is content-addressed, which makes it the one column in the artifact checkable against
  itself with no reference, no network and no dependency. Every row lands in exactly one of three
  outcomes, and the difference between the last two is the one that matters.

  # source: compiler/src/just_dna_compiler/compiler.py:1141
  @code:non_grch38_variant_keys @carried @both_modes
  Scenario: a non-GRCh38 module is keyed by coordinate instead
    Given a module declaring genome_build "GRCh37"
    When the module is compiled
    Then the rows are re-keyed by coordinate and a warning names how many
    And it says a coordinate key is "**build-relative**"
    And it warns that "the same key means a different locus on another build"
    And the author can do nothing about it short of republishing on GRCh38
    # RM15. Carried because the remedy is not an edit to this module but a change to what identity is.

  # source: compiler/src/just_dna_compiler/compiler.py:1113
  Scenario: the re-stamp is a no-op on GRCh38, which is every module today
    Given a module declaring genome_build "GRCh38"
    When the module is compiled
    Then nothing is re-keyed and no warning fires
    # A row is stamped before the module is known, so the build-dependent stamp is re-derived at both
    # load sites (`@restamp-for-build`). The build is INJECTED at load and never authored on a row.

  # source: compiler/src/just_dna_compiler/compiler.py:2885
  @tri_state
  Scenario Outline: the VRS verify pass has three outcomes and one of them is not a mismatch
    Given a resolution.csv row carrying a stored vrs_id
    When the id is recomputed and the result is <result>
    Then the outcome is <outcome> with severity <severity>
    # The third case is emphatically NOT "an indel mismatch". This tier cannot recompute an indel's id,
    # so it can never detect that one disagrees — it can only report that it did not check. Calling that
    # a mismatch would claim a verdict that was never reached (`@vrs-three-outcomes`).
    Examples:
      | result                          | outcome       | severity                    |
      | equal to the stored id          | verified      | silent                      |
      | different from the stored id    | mismatch      | error in both modes         |
      | not computable at all           | unverifiable  | depends on whose limit it is |

  # source: compiler/src/just_dna_compiler/compiler.py:2970
  @refusal @both_modes
  Scenario: a recomputed id that differs is corrupt, in both modes
    Given a stored vrs_id that does not match the id recomputed from the row's own coordinate
    When the module is compiled in either mode
    Then the compile refuses, naming both ids and the coordinate they were computed from
    # The computation is fully deterministic here, so a disagreement can only mean the stored id is
    # corrupt — the row was tampered with, or the producer and this implementation disagree. Either way
    # the id is not usable as an identity.

  # source: compiler/src/just_dna_compiler/compiler.py:3003
  @code:vrs_id_unverifiable @carried @both_modes
  Scenario: an id this tier cannot recompute, where the limit is the tier's
    Given a resolution.csv row whose stored vrs_id is for an indel
    When the module is compiled in either mode
    Then a warning fires saying the id is "carried unverified"
    And one line is emitted per REASON with a count and named examples, never one per allele
    And the same finding does not escalate under strict
    # `strict` means *reproducible artifact*, and an enricher-minted indel VA is perfectly reproducible.
    # An indel or MNV must be justified against the reference sequence, which this tier has no access to
    # and will never fetch (Principle 2).

  # source: compiler/src/just_dna_compiler/compiler.py:2961
  @refusal @both_modes
  Scenario: an id recorded against nothing to check it with is a contradiction, not a tier limit
    Given a resolution.csv row carrying a vrs_id and no coordinate
    When the module is compiled in either mode
    Then the compile refuses saying it is "a contradiction in the table, not a limit of this tier"
    And the remedy offered is to resolve the row or drop the vrs_id
    # `_BLAME_ROW` is an error in both modes and `_BLAME_TIER` a warning in both: severity follows whose
    # limit it is, not the mode. The row asserts an identity while withholding the coordinate that
    # identity is a digest of, so nothing can ever check it.

  # source: compiler/src/just_dna_compiler/compiler.py:3174
  Scenario Outline: the five reasons an allele is unverifiable, and who each one belongs to
    Given a resolution.csv row whose allele is <shape>
    When the id is recomputed
    Then the reason is <reason> and the blame is <blame>
    Examples:
      | shape                                     | reason                                  | blame |
      | a row with no coordinate                  | nothing to recompute from               | row   |
      | a position-only row with no ALT           | a VA names exactly one allele           | row   |
      | a symbolic allele like <DEL:4977>         | it names an event and no sequence       | tier  |
      | an indel or MNV                           | it needs the reference sequence         | tier  |
      | a build with no refget table              | no accession to address the sequence by | tier  |

  # source: compiler/src/just_dna_compiler/compiler.py:3188
  Scenario: a symbolic allele is checked before the indel reason it would otherwise fall into
    Given a resolution.csv row whose allele is "<DEL:4977>"
    When the id is recomputed
    Then the reason names the structural event, not the missing reference sequence
    # Both statements are true of the row, and the one to print is the one NO release can answer: the
    # enricher cannot mint a VA for a symbolic allele either. Whether a *stored* id on such a row should
    # be blamed on the row is a real open question, deliberately left open rather than half-mended —
    # acting on it would refuse, in both modes, a module that compiles today.

  # source: compiler/src/just_dna_compiler/compiler.py:3208
  Scenario: a multi-allelic site of substitutions verifies as completely as a bi-allelic one
    Given a resolution.csv row with three comma-joined alts and three vrs_ids
    When the ids are recomputed
    Then each is checked against its own ALT
    # `vrs_id` is positionally aligned with `alts`, one id per ALT, empty members kept, never one row
    # per allele (`@vrsid-per-alt`). Nothing is picked, so the old multi-allelic exemption is gone.

  # source: compiler/src/just_dna_compiler/compiler.py:3212
  Scenario: an unsupported build is caught and turned into a reason, not allowed to abort the compile
    Given a resolution.csv row on a build with no refget table
    When the id is recomputed
    Then the raised error becomes an unverifiable reason
    # `refget_accession` RAISES off GRCh38 rather than returning, deliberately: a caller asking for
    # GRCh37 should hear "not built" rather than get a GRCh38-flavoured answer (`@refget-raises`).
    # Letting it propagate would abort the whole compile over one unverifiable row.

  # source: compiler/src/just_dna_compiler/compiler.py:3146
  @code:vrs_coverage_incomplete @carried @both_modes
  Scenario: the shortfall, and what a consumer keying on the VA actually sees
    Given a resolution.csv where 40 of 100 alleles carry no ga4gh:VA. id
    When the module is compiled
    Then a warning reports the covered fraction as a percentage and the shortfall as a count
    And it says "Anything keying on the VA sees only the covered fraction."
    And a second line per reason continues the SAME code
    # One code for the headline and its breakdown, because a summary counting itself and its own detail
    # under two keys would double-count one coverage gap. A check over recorded values must also count
    # the records carrying none (`@vrs-coverage`).

  # source: compiler/src/just_dna_compiler/compiler.py:3130
  Scenario: full coverage reports nothing at all
    Given a resolution.csv where every allele carries a ga4gh:VA. id
    When the module is compiled
    Then no coverage warning fires
    # A check that cannot fail must not report a zero (`@tautology-zero`).

  # source: compiler/src/just_dna_compiler/compiler.py:3130
  Scenario: the two halves of the VRS story are ordered the same way round
    Given a module with both unverifiable ids and a coverage shortfall
    When the module is compiled
    Then both sets of per-reason lines are sorted by descending count then by reason
    # Deterministic because warning text is an API and a set-ordered one would differ between runs
    # (`@warning-text-is-api`).

  # source: compiler/src/just_dna_compiler/compiler.py:4705
  Scenario: content_signature hashes the effective default, not the cell
    Given two modules stating one curator, one in `defaults:` and one on every row
    When both are compiled
    Then they reach the same content_signature
    # `compile → reverse → compile` moved the signature for any module writing the value per row,
    # because reverse re-emits it in the other place. The data was never lost — `artifact.digest` was
    # byte-identical — only the pre-resolution identity disagreed with itself
    # (`@effective-defaults-hash`).

  # source: compiler/src/just_dna_compiler/compiler.py:4737
  Scenario: a value equal to the model's own default is written back as None
    Given a module stating the built-in curator value explicitly on every row
    When it is compiled
    Then its content_signature is unchanged byte for byte
    # The same normalization `integrity.content_signature` already applies to `genome_build` and to
    # every unset optional column. What moves is a module stating something else — which is exactly the
    # module whose two spellings were being hashed apart.
