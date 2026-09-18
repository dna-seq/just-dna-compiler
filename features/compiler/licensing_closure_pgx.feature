# Licensing as data, authoring's end, and the PGx tables' cross-checks.
#
# Source of truth: compiler/src/just_dna_compiler/compiler.py, docs/COMPILER.md,
# docs/SCHEMAS.md's licence table, docs/MODULE_LIFECYCLE.md.
#
# Licensing lives as DATA in the licence table, never as a table in the compiler (`@licensing-as-data`),
# and the compile gate is data-driven for a Principle 7 reason rather than a stylistic one: a
# `--non-commercial` flag could never be re-emitted by `reverse_module`, so a flag-gated compile would
# refuse on the third step of a round trip (`@gate-is-data-driven`).

Feature: The licence gate, the closure, and the PGx cross-checks
  One tainting row refuses the whole compile, in both modes. Everything else about licensing warns,
  because the alternative is the format arbitrating a legal question.

  # source: compiler/src/just_dna_compiler/compiler.py:6073
  @refusal @both_modes
  Scenario: a no-sale source with no matching declaration refuses
    Given a sources.csv row whose terms forbid sale and whose declared_use is "unstated"
    When the module is compiled in either mode
    Then the compile refuses saying those sources "contribute annotation-layer content under terms that forbid sale"
    And the remedy is to re-run the enricher with `--use non-commercial` or remove the content
    And it says declaring it "is an assertion about how the module will be used"
    And it says the compiler "records that assertion, it does not verify it"
    # `unstated` is not a loophole: it is the absence of a declaration, which is precisely what the gate
    # wants. `declared_use` is a third axis with three states, not a mode (`@declared-use-third-axis`).

  # source: compiler/src/just_dna_compiler/compiler.py:6047
  Scenario: most restrictive wins, module-wide
    Given one no-sale source and five permissive ones, none declaring a use
    When the module is compiled
    Then the whole compile refuses
    # Mixing a permissive source into a restricted one cannot launder it, which is why the verdict is not
    # computed per row or per layer.

  # source: compiler/src/just_dna_compiler/compiler.py:6047
  @parity
  Scenario: the gate survives a round trip because the declaration is data
    Given a module whose sources.csv declares non_commercial use
    When the module is compiled, reversed, and compiled again
    Then all three compiles reach the same verdict
    # `sources.csv` round-trips, so the declaration travels with the module. `reverse_module` rebuilds
    # `module_spec.yaml` from parquet alone and could never re-emit a flag.

  # source: compiler/src/just_dna_compiler/compiler.py:6158
  @code:source_row_unused @actionable @both_modes
  Scenario: a declared source no fact table uses
    Given a sources.csv row at the frequency layer and a module with no frequencies.csv
    When the module is compiled
    Then a warning fires whose text contains "no table in this module uses"
    # Over-declaration: harmless but probably stale. `frequencies.csv` IS machine-written with a `source`
    # column naming a licensed source, so a frequency declaration in a module with no frequencies really
    # is stale.

  # source: compiler/src/just_dna_compiler/compiler.py:6089
  Scenario: an annotation-layer row is structurally exempt, and so is literature
    Given a sources.csv row at the annotation layer, which is the row that makes the licence gate work
    When the module is compiled
    Then it is not reported as unused
    # Structural rather than a softening: "no table used it" is decided by reading the fact tables'
    # `source` columns, and the annotation layer IS `variants.csv`/`diplotypes.csv`, which carry no such
    # column by design (`@orphan-check-exempt`). It was reported as stale on every drafted module.
    # Note which way the old behaviour pushed an author: declaring a hand-read source earned a warning
    # that the row is unused, while deleting it and shipping with the provenance unrecorded was silent.
    # Compliance warned, omission quiet.

  # source: compiler/src/just_dna_compiler/compiler.py:6089
  Scenario: literature's exemption is unconditional since 0.6, and the reason is the point
    Given a module citing a PMID through studies.csv and carrying a literature.csv
    When the module is compiled
    Then the literature-layer declaration is not reported as unused
    # `literature.csv`'s `source` names the bibliographic registry that ANSWERED (`pubmed`), not a
    # licensed source, and the tier has no terms constant for it because a literature source's terms are
    # per ARTICLE (`@per-article-terms`). A single `pubmed` row in `sources.csv` would be wrong in the
    # dangerous direction: right for a module citing only ids, and a false all-clear for one carrying a
    # `provenance_quote` lifted from a CC-BY-NC article.

  # source: compiler/src/just_dna_compiler/compiler.py:6166
  @code:source_terms_unrecorded @actionable @both_modes
  Scenario: a source a fact table cites with no row recording its terms
    Given a frequencies.csv citing a source sources.csv has no row for
    When the module is compiled
    Then a warning fires saying "their terms are unrecorded"
    And it is a warning rather than an error
    # The compiler cannot know whether the omission is an oversight or a source with no terms worth
    # recording. Emitted only when `sources.csv` exists at all, so a module without one warns exactly as
    # it did before (Principle 3).

  # source: compiler/src/just_dna_compiler/compiler.py:6216
  @code:declared_license_disagrees @actionable @both_modes
  Scenario: a module licence that contradicts an annotation-layer source's
    Given a module_spec.yaml declaring one licence and two annotation-layer rows declaring another
    When the module is compiled
    Then a warning fires whose text contains "declares license"
    And it says the disagreement is "Not adjudicated here"
    And it names its denominator — the agreeing rows beside the disagreeing ones
    And it says the mixed-licence case is where "the most restrictive term binds the whole artifact"
    # S79: the message used to render the REMAINDER as though it were the whole set, so a declaration
    # matching one of two rows printed identically to one matching none. Those are different problems —
    # *your declaration is unsupported* versus *your declaration is not universal* — and an author
    # reading the first when the second was true re-adjudicated the module's whole licence position and
    # found nothing wrong, twice, in two reported rounds. String equality only: an SPDX compatibility
    # matrix is world-knowledge that would go stale.

  # source: compiler/src/just_dna_compiler/compiler.py:6160
  Scenario: suppressing the warning when any row matches was refused
    Given a module declaring the least restrictive of several source licences
    When the module is compiled
    Then the warning still fires
    # The reporter argued it against their own case and is right: that module is exactly the one worth
    # warning about.

  # source: compiler/src/just_dna_compiler/compiler.py:7188
  @code:quoted_article_license_restrictive @actionable @both_modes
  Scenario: a quote lifted from an article whose licence forbids commercial reuse
    Given a studies.csv row carrying a provenance_quote from an article recorded commercial_use=False
    When the module is compiled
    Then a warning fires saying the licence "forbids commercial reuse"
    And it says this is "Not adjudicated here"
    And it says the passage "is publisher text in this module's annotation layer"
    And the finding is aggregated by licence string, one line per licence

  # source: compiler/src/just_dna_compiler/compiler.py:7149
  @tri_state
  Scenario Outline: the quote licence check is keyed on the quote and withholds on unknown
    Given a literature row whose commercial_use is <recorded> and a study row that <quotes>
    When the module is compiled
    Then the finding is <outcome>
    # Keyed on the QUOTE, not on the citation: naming a PMID costs nothing under any licence, while a
    # `provenance_quote` copies the publisher's own words into `studies.csv`, which is authored content
    # the module ships.
    Examples:
      | recorded | quotes                  | outcome                 |
      | False    | carries a quote         | reported                |
      | False    | cites the id only       | not reported            |
      | None     | carries a quote         | withheld — unknown      |
      | True     | carries a quote         | not reported            |

  # source: compiler/src/just_dna_compiler/compiler.py:7265
  @code:clin_sig_contradicts_frequency @actionable @both_modes
  Scenario: a variant the module calls pathogenic that is common in a general population
    Given a variants.csv row whose clin_sig is pathogenic
    And a frequencies.csv row putting its ALT above 5% in a general population
    When the module is compiled
    Then a warning names ACMG's BA1 threshold and says BA1 "treats that as stand-alone evidence of benign impact"
    And it says the threshold "is disease-specific" and calls itself "a prompt to check, not a verdict"
    # The 5% default is ACMG's, not a constant of nature, and it is overridable: sickle-cell's rs334 sits
    # around 4-5% in African-ancestry groups and legitimately lives near it. Failing a compile over that
    # would be the format arbitrating a clinical judgement, which the data-agnostic charter forbids.
    # `faf95` is preferred over a raw AF when the sidecar carries one, because that is the statistic an
    # ACMG filter actually uses.

  # source: compiler/src/just_dna_compiler/compiler.py:6051
  @code:clin_sig_concordance_contested @actionable @both_modes
  Scenario: the module carries subjects two authorities disagree about
    Given a clin_sig_concordance.csv recording 3 contested subjects
    When the module is compiled
    Then a warning says "A contested subject is a question, not a defect"
    And it says "half the time the archive is the stale side, which is why this never fails a build in either mode"
    And it names overrides.csv as where the answer goes
    # It names `overrides.csv` and never `provenance.json`'s `outranks`: both record an authored value
    # beating a source with prose, and 0.7 settled the overlap as a dated succession — the overlay wins
    # and the knob is filed for removal at the major. Counted over the POST-overlay rows, which is what
    # makes the finding clearable.

  # source: compiler/src/just_dna_compiler/compiler.py:6003
  @parity
  Scenario: the count is safe to embed although both passes emit it
    Given a module with contested subjects
    When it is validated and then compiled
    Then both passes reach a byte-identical sentence and the duplicate collapses
    # Normally the trap where a message carrying a number is built twice from inputs resolution changed
    # in between (`@no-rerun-with-counts`). This one reads `clin_sig_concordance.csv` after the overlay,
    # and no compile step between the two passes touches either the file or the overlay. Pinned by a test
    # rather than left to the argument.

  # source: compiler/src/just_dna_compiler/compiler.py:3324
  @code:star_allele_undefined @actionable @both_modes
  Scenario: a star allele used but never defined
    Given a diplotypes.csv naming *36, *37 and *42
    And a haplotypes.csv defining none of them
    When the module is compiled
    Then a warning says "A consumer's caller cannot emit an allele nothing defines"
    And it says rows about it "can never match"
    # Found by drafting CYP2C19 from CPIC: three alleles used across 666 diplotype rows, two of them
    # declared `no_function`, and nothing defined any of them.

  # source: compiler/src/just_dna_compiler/compiler.py:3287
  Scenario: the check only runs when haplotypes.csv is present
    Given a module carrying diplotypes.csv and no haplotypes.csv
    When the module is compiled
    Then no undefined-allele warning fires
    # A module may legitimately carry a diplotype table alone and lean on the caller's own definitions,
    # and punishing that would be the orphan-sidecar mistake: don't fault an author for a file they
    # deliberately did not write. `*1` is exempt in any case.

  # source: compiler/src/just_dna_compiler/compiler.py:3476
  @code:diplotype_phase_ambiguous @actionable @both_modes
  Scenario: two diplotype rows unphased data cannot tell apart, disagreeing
    Given HFE rows for C282Y/H63D in trans and C282Y-H63D/wt in cis
    When the module is compiled
    Then a warning says they are "indistinguishable without phase — same unphased genotype, different conclusions"
    And it says an unphased consumer "must withhold rather than pick one"
    # RM28's cis/trans motivation, closed by computation rather than by a grammar: a diplotype is already
    # a statement about two homologs, so cis and trans are two rows. What no table can say is that the
    # two cannot be told apart, and nearly all consumer data is unphased. A `requires_phase` column would
    # restate what the data determines and go stale the moment a haplotype is edited.

  # source: compiler/src/just_dna_compiler/compiler.py:3353
  Scenario: it compares haplotype PAIRS, never rows, and it is closed-world
    Given a CYP2C19 module with one row per drug and per clinical_context for each pair
    When the module is compiled
    Then the ambiguity count is over distinct pairs
    Given an APOE module carrying no ε1
    When the module is compiled
    Then nothing fires about the textbook ε2/ε4 versus ε1/ε3 collision
    # Grouping on rows reported 595 ambiguities in a module that has none. And it compares the rows a
    # module STATES, never the ones it omits — the module makes no claim about ε1, and the neighbouring
    # used-but-not-defined check covers that side.

  # source: compiler/src/just_dna_compiler/compiler.py:3465
  @code:diplotype_definitions_identical @actionable @both_modes
  Scenario: two diplotype rows whose haplotypes this module defines identically
    Given two diplotypes.csv rows naming haplotypes with identical defining variants
    And different conclusions
    When the module is compiled
    Then a warning says "nothing in it can tell them apart — phase does not help"
    And it says "at most one can be right"
    And it names both readings: incomplete defining variants, or one allele under several names

  # source: compiler/src/just_dna_compiler/compiler.py:6470
  @code:module_not_closed @actionable @both_modes
  Scenario: a module that never declared authoring finished
    Given a spec directory with no closure
    When the module is compiled
    Then a warning says "nothing in it states that authoring is finished"
    And it names `just-dna-compiler close <spec-dir>` as the act
    And it says closing "is never stamped by a passing check"
    And it says editing any authored file afterwards "drops the closure again"
    And it carries no count
    # One sentence covers all three ways a compile publishes no closure, because what an author needs to
    # know is the same in each: this artifact does not say the module is done. The other warnings carry
    # the reasons. Carrying no count is what keeps it collapsible under the de-duplication that runs it
    # in both `validate_spec` and `compile_module` (`@closure-phase-boundary`).

  # source: compiler/src/just_dna_compiler/compiler.py:6385
  @code:verification_stale @actionable @both_modes
  Scenario: an attestation that no longer describes these bytes
    Given a verification.json bound to an earlier state of the authored files
    When the module is compiled
    Then a warning says the file "is stale" and names the failure
    And it says the manifest "records no verification for this compile, which says nothing rather than claiming a pass"
    And the remedy names re-closing only if the dropped document actually carried a closure
    # The remedies differ — re-running the checks is the enricher's job, re-closing is the author's — and
    # a compile that recommended both to everyone would send half its readers after a file they never
    # had. The attestation binds newline-normalized bytes and their normalized size, while
    # `manifest.inputs[]` stays raw (`@binding-normalizes-newlines`).

  # source: compiler/src/just_dna_compiler/compiler.py:6367
  @code:verification_unreadable @actionable @both_modes
  Scenario: an attestation that cannot be parsed
    Given a corrupt verification.json
    When the module is compiled
    Then a warning says it "could not be read as a verification attestation"
    And it says "this compile records no verification"
    And the remedy is to re-run the checks

  # source: compiler/src/just_dna_compiler/compiler.py:5783
  @code:closure_discarded_unreadable_record @actionable @both_modes
  Scenario: closing over an unreadable existing record discards what it recorded
    Given a spec directory whose verification.json cannot be read
    When `close` runs
    Then a warning says "this closure replaces it, so any checks it recorded are gone"
    And it says to re-run the checks

  # source: compiler/src/just_dna_compiler/compiler.py:6311
  @code:verification_findings_recorded @carried @both_modes
  Scenario: a check found something, said where the author is standing
    Given a verification.json recording 20 findings across 3 checks
    When the module is compiled
    Then a warning names both counts and the checks
    And it says "A finding is a disagreement between this module and a source, not a defect"
    And it says the archive "is the stale side often enough that this never fails a build"
    And it points at the record's `detail` and at provenance.json's `outranks`
    # S70: nothing read `VerificationRecord.findings` at all. The counts reached
    # `manifest.verification.checks[]`, so a consumer that went looking found them, while the author
    # running `validate` saw a green result with warnings about closure and nothing about the rows a
    # source disagrees with. Reported as 20 of 141,616 and 32 of 618,629 on two real modules.

  # source: compiler/src/just_dna_compiler/compiler.py:6263
  @parity
  Scenario: this one carries counts and runs on both sides, and that is not the rerun trap
    Given a module whose verification.json records findings
    When it is validated and then compiled
    Then both passes reach a byte-identical sentence and the duplicate collapses
    # `@no-rerun-with-counts` fires where RESOLUTION changes a check's input between the two passes, so
    # the same finding is reported with two different numbers and message-dedup cannot collapse them.
    # This check's input is `verification.json`, which no compile step touches.
