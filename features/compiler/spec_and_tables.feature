# The spec directory: which files the compiler reads, which it tolerates, and what a cell may spell.
#
# Source of truth: compiler/src/just_dna_compiler/compiler/, schema/src/just_dna_format/layout.py,
# docs/COMPILER.md § "The compile pipeline", docs/SCHEMAS.md's CSV families.
#
# Standing contract (S16): unknown files in a spec directory are IGNORED on purpose. A module may carry
# curation notes or a publisher's receipt, neither of which reaches `artifact.files` and so neither of
# which moves the digest. Every finding below is a narrow exception to that tolerance, not a retreat
# from it (`@misspelled-tables`).

Feature: The spec directory and the cells inside it
  A near-miss table name is the one case where "ignored" is the wrong answer, because the author's rows
  are silently dropped and the compile is green.

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _check_misspelled_tables
  @code:table_file_near_miss @actionable @both_modes
  Scenario: a mistyped table name, one small edit from a real one
    Given a spec directory containing "varaints.csv"
    When the module is compiled
    Then a warning fires saying it is "not a table this compiler reads"
    And it says "if that is a typo, every row in it is being silently ignored"
    And it restates that "Unknown files are otherwise tolerated"

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _check_misspelled_tables
  Scenario: an unrelated filename stays quiet
    Given a spec directory containing "curation-notes.csv"
    When the module is compiled
    Then no near-miss warning fires
    # Keyed on near miss rather than on "unknown csv": warning about every unrecognised file would fire
    # on the legitimate sidecars the contract exists to permit, so the check has to be high-precision or
    # it undoes the tolerance. `difflib` at a 0.8 cutoff catches a transposition, a doubled or dropped
    # letter, and a singular/plural slip.

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _check_misspelled_tables
  Scenario: the derived/ tree is scanned too
    Given a spec directory containing "derived/varaints.csv"
    When the module is compiled
    Then the near-miss warning fires there as well
    # RM49: tolerating a second input location without teaching this check about it would put a typo'd
    # table exactly where the guard cannot see it, re-opening the hole S16 closed as the price of a
    # convenience.

  # source: compiler/src/just_dna_compiler/compiler/table_checks.py
  # anchor: _check_misspelled_tables
  @code:table_file_misplaced @actionable @both_modes
  Scenario: an authored table sitting where only sidecars live
    Given a spec directory containing "derived/variants.csv"
    When the module is compiled
    Then a warning fires saying it holds "only the machine-written sidecars"
    And it says "every row in it is being silently ignored" and to move it to the spec root
    And it states that only resolution.csv and the fact tables have a second legal home

  # source: compiler/src/just_dna_compiler/compiler/tables.py
  # anchor: _locate_sidecar
  # text: schema/src/just_dna_format/layout.py
  @code:sidecar_spelling_deprecated @actionable @both_modes
  Scenario: reading a sidecar under its deprecated spelling
    Given a spec directory carrying "sources.csv" rather than "licensing.csv"
    When the module is compiled
    Then a warning fires saying it is "the deprecated spelling of this table and will be removed at 1.0"
    And it names the preferred spelling and says the file "is read exactly as before until then"
    And it says the compiled parquet and manifest key keep their current names
    # Actionable by construction, which is what the 0.6 cadence amendment requires of a deprecation in a
    # minor: the replacement exists, the old name is not mandatory, and the migration is `git mv`.
    # On a split tree the notice names WHICH copy rather than a bare filename that could be either.

  # source: compiler/src/just_dna_compiler/compiler/tables.py
  # anchor: _locate_sidecar
  # text: schema/src/just_dna_format/layout.py
  @refusal @both_modes
  Scenario: both spellings present is an error, not a precedence rule
    Given a spec directory carrying both "sources.csv" and "licensing.csv"
    When the module is compiled
    Then it refuses saying they "are the same table in two places, and both are present"
    And it says neither "can be preferred without discarding the other"
    # Not a merge and not newest-wins. These tables are fact-hashed and human-overridable — a curator
    # edits a row the enricher wrote and that edit is the point — so two copies are two legitimate
    # claims and picking one discards somebody's work without saying so (`@sidecar-name-and-place`).

  # source: compiler/src/just_dna_compiler/compiler/manifest.py
  # anchor: _read_verification_block
  # text: schema/src/just_dna_format/layout.py
  @code:verification_two_copies @actionable @both_modes
  Scenario: the same collision on the attestation is a warning, because the outcome is already weaker
    Given a spec directory carrying verification.json in both the root and derived/
    When the module is compiled
    Then a warning fires rather than a refusal
    And no verification is published
    # Two attestations are two claims, neither may be preferred, so nothing is published — the outcome is
    # already the weak one, and refusing would add nothing. The message is built by `layout` as a refusal
    # and coded at the point where it becomes a warning, which is the only place that knows it is one.

  # source: compiler/src/just_dna_compiler/compiler/validate.py
  # anchor: _validate_spec
  @code:module_version_coerced @actionable @both_modes
  Scenario: a module version that is not SemVer
    Given a module_spec.yaml whose version reads "1.2"
    When the module is compiled
    Then a warning names the coerced SemVer value
    And it says the version "is advisory either way"
    And the module compiles under the coerced value
    # A `mode="after"` validator cannot rescue a value the field's type rejects first
    # (`@yaml-version-int`), which is why the coercion is where it is.

  # source: compiler/src/just_dna_compiler/compiler/validate.py
  # anchor: _check_composite_gene_cells
  @code:composite_gene_cell @actionable @both_modes
  Scenario: a gene cell that looks like a list
    Given 33 variants.csv rows sharing the gene cell "IFNL3;IFNL4"
    When the module is compiled
    Then one warning fires, not 33
    And it says the composite value "becomes a gene nobody will search for, beside its parts"
    And it says "Nothing is split here"
    # It reports and never repairs: splitting would guess at a vocabulary, and `IFNL3;IFNL4` may
    # legitimately name THE LOCUS, which is a real thing in that dataset. The value also came straight
    # out of an upstream export, so refusing it would refuse a faithful transcription. `stats.genes` is
    # what a registry's gene index reads, which is what makes a composite cell a third gene.

  # source: compiler/src/just_dna_compiler/compiler/vcf_checks.py
  # anchor: _check_vcf_pointers
  @code:vcf_pointer_key_collision @actionable @both_modes
  Scenario: a pointer naming a key INFO and FORMAT both define
    Given a variants.csv row whose source_field is "AF"
    When the module is compiled
    Then a warning fires saying "the pointer does not say which field it means"
    And the remedy is to qualify it as INFO/AF or FORMAT/AF
    And a bare key "stays legal and keeps meaning unqualified, which is why this is a warning"
    # A VCF field is not identified by its name: INFO and FORMAT are two reserved-key tables colliding on
    # DP, AD, ADF, ADR, MQ, AF and — since 4.4 — CN. Both readings are usually type-compatible, so
    # nothing detects the confusion. `reference_examples/mt_heteroplasmy` shipped `source_field=AF`
    # meaning this person's heteroplasmy fraction, where the spec's AF is the cohort frequency of the
    # same ALT — one of those tells a carrier they are asymptomatic on the strength of how rare the
    # variant is in a reference panel.

  # source: compiler/src/just_dna_compiler/compiler/vcf_checks.py
  # anchor: _check_vcf_pointers
  @code:vcf_pointer_unselected_element @actionable @both_modes
  Scenario: a pointer at a multi-valued field with no element rule
    Given a variants.csv row pointing at a field the spec defines as multi-valued
    And no companion element rule
    When the module is compiled
    Then a warning fires saying "the pointer names a list rather than a number"
    And it says that on a Number=R field "the reference is element zero"
    # Which is why each ranging rule comes in a pair: `largest` counts the reference and `largest_alt`
    # does not.

  # source: compiler/src/just_dna_compiler/compiler/vcf_checks.py
  # anchor: _check_vcf_pointers
  @tri_state
  Scenario: a key the spec does not define has no cardinality this tier may assert
    Given a variants.csv row pointing at "REPCN", which is ExpansionHunter's key and not the spec's
    When the module is compiled
    Then no element-rule warning fires
    # `vocab.VCF_FIELD_NUMBER` is a transcription of the spec's own reserved-key tables and answers
    # `None` for anything outside them. Asserting a cardinality would be a source convention wearing a
    # fact (P2). Unknown withholds.

  # source: compiler/src/just_dna_compiler/compiler/vcf_checks.py
  # anchor: _check_quality_inversion
  @code:quality_floor_inverted @actionable @both_modes
  Scenario: a quality floor stated against QUAL on a row where absence is the informative call
    Given variants.csv rows with requires_callable true, quality_from "QUAL" and min_quality 30
    When the module is compiled
    Then a warning fires quoting VCF §1.6.1.6's two definitions of QUAL
    And it says "the higher the floor, the more confidently wrong"
    And it is aggregated to one line with examples
    # The sign of the assertion FLIPS with the record: QUAL 60 on a variant record means the variant is
    # almost certainly real, and the same 60 on a monomorphic reference record means the position is
    # almost certainly variant. Refusing was considered and rejected — it would encode one reading of a
    # field whose meaning depends on a record this tier will never see, and would refuse the legitimate
    # case of the same row read against a variant record elsewhere in the same file.

  # source: compiler/src/just_dna_compiler/compiler/validate.py
  # anchor: _validate_spec
  @code:panel_block_deprecated @actionable @both_modes
  Scenario: a deprecated panel block whose one reader has been replaced
    Given a module_spec.yaml declaring a `panel:` block
    And a clinvar licence row carrying a `dataset`
    When the module is compiled
    Then a warning says the block "is deprecated in 0.6 and removed at 1.0"
    And it names the licence row's `dataset` column as what replaced its one reader

  # source: compiler/src/just_dna_compiler/compiler/validate.py
  # anchor: _validate_spec
  Scenario: the same block where nothing has replaced it yet says the opposite
    Given a module_spec.yaml declaring a `panel:` block
    And no clinvar or annotation licence row carrying a `dataset`
    When the module is compiled
    Then the warning says "Do NOT delete the block yet"
    And it says the block "is currently the only record of which snapshot this module was drafted from"
    And it warns that re-drafting will not backfill the licence row
    # One code, two sentences that give opposite instructions, because the state of the module decides
    # which advice is safe. A deprecation belongs in a minor only where its audience can ACT on it, and
    # here whether they can is a property of their own module.

  # source: compiler/src/just_dna_compiler/compiler/binning_checks.py
  # anchor: _check_binning_grounding
  @code:bins_ungrounded @actionable @both_modes
  Scenario: a binning table stating thresholds with no evidence anywhere in the module
    Given a repeat_alleles.csv stating four thresholds
    And no studies.csv rows and no bin pmid
    When the module is compiled
    Then a warning names how many of how many bins state a threshold with no grounding
    And it fires in both modes
    # Grounding is enforced where it is most often automatic and silent where it is most interpretive: a
    # `variants.csv` row is frequently drafted from ClinVar with citations attached, while where 36 rather
    # than 35 CAG becomes "reduced penetrance" is a clinical judgement drawn from specific literature and
    # is exactly the number a reader would want to check. `reference_examples/htt_repeat_expansion`
    # compiled green under `--strict` stating four thresholds with no citation anywhere.

  # source: compiler/src/just_dna_compiler/compiler/binning_checks.py
  # anchor: _check_binning_grounding
  Scenario: a bin carrying its own pmid is grounded and is not counted
    Given a repeat_alleles.csv whose threshold rows each carry a pmid
    When the module is compiled
    Then no grounding warning fires
    # RM47 made the remedy sayable: `MeasureBinRow.pmid` is a pointer on the row that states the
    # threshold, and `StudyRow`'s subject requirement was relaxed in the same release so the citation row
    # describing that paper need not invent a variant to hang off (`@rm47-bin-cites`).
