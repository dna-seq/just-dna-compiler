# Why a check did not run — the eight members of `VALID_VERIFICATION_SKIPS`.
#
# Source of truth: schema/src/just_dna_format/vocab.py's VALID_VERIFICATION_SKIPS and the comment block
# above it, docs/ENRICHER.md.
#
# The set is the union of how the passes used to spell their own skips (`skipped_offline`,
# `no_snapshot`, `unusable_snapshot`, `unchecked`, ClinPGx's licensing `skipped`), mapped onto one axis
# — which is the whole point: those spellings are what a consumer would otherwise have to learn.
# Closed, because backfill triage branches on WHY, so prose here would relocate the substring matching
# rather than end it. The human sentence travels BESIDE the key, in `VerificationRecord.detail`, never
# instead of it.
#
# A skip is not `subjects=0, findings=0`. A zero out of zero on a check that could not run is exactly
# the clean-looking pass the vocabulary exists to prevent (`@unreachable-not-absent`).

Feature: The skip vocabulary
  Nobody-asked is a third state beside asked-and-failed and asked-and-absent. Each member below names a
  different one, and two of them are different facts about the same absence.

  # source: enricher/src/just_dna_enricher/identifiers.py:1510
  @skip:not_requested
  Scenario: the caller switched this check off
    Given `check-identifiers --no-traits`
    When the pass attests
    Then the record is a skip with reason "not_requested" and detail naming the flag
    # The record is unconditional — there is no `--attest` flag — because an optional record is ambiguous
    # between *the check was not run* and *it ran without the flag*, which reintroduces the
    # two-readings-of-one-absence defect the vocabulary was built to end.

  # source: enricher/src/just_dna_enricher/enrich.py:2360
  @skip:offline
  Scenario: the check needs egress and the run had none
    Given `enrich --offline`
    When the rsID currency check is reached
    Then the record is a skip with reason "offline"
    # `not_requested` and `offline` are different facts about the same absence and must not be merged:
    # one is a caller's choice, the other a capability the run did not have, and only the second is
    # cleared by re-running with egress.

  # source: enricher/src/just_dna_enricher/identifiers.py:1608
  @skip:no_reference
  Scenario: nothing was provisioned to compare against
    Given a gene-locus check with no reference provisioned
    When the pass attests
    Then the record is a skip with reason "no_reference"
    # A comparison whose input was missing is `no_reference`, never `ran(0, 0)`. A directory is not a
    # snapshot: judge a parent by its payload, never by `is_dir()`
    # (`@a-derived-lane-has-parents-and-an-absent-parent-is-not-an-empty-result`).

  # source: enricher/src/just_dna_enricher/litvar.py:946
  @skip:unreachable
  Scenario: the source was asked and never answered
    Given a LitVar request that fails at the transport
    When the pass attests
    Then the record is a skip with reason "unreachable"
    # A failed request, not a no. One registry's outage may not write a skip against another's check
    # (`@one-registrys-outage-may-not-speak-for-another`).

  # source: enricher/src/just_dna_enricher/identifiers.py:1601
  @skip:nothing_to_check
  Scenario: the module carries no row this check applies to
    Given a module with no gene column anywhere
    When the gene-locus check is reached
    Then the record is a skip with reason "nothing_to_check"
    # A check that cannot fail must not report a zero (`@tautology-zero`). This is the shape where the
    # subject set is genuinely empty, as opposed to the tautology below where it is not.

  # source: enricher/src/just_dna_enricher/enrich.py:1540
  # text: enricher/src/just_dna_enricher/clinical.py
  @skip:tautology
  Scenario: the module was drafted from the very source the check reads
    Given a module whose clin_sig was copied out of the ClinVar snapshot this check reads
    When the clinical significance check is reached
    Then the record is a skip with reason "tautology"
    And the detail sentence says why the comparison cannot fail
    # S4, re-keyed by RM4. The comparison is a value against itself: on a 7,818-row panel a consumer
    # measured 27.1 s with the check on and 2.6 s with it off, byte-identical output, and 0 conflicts
    # either way — necessarily 0. Reporting "0 conflicts" there is mild misinformation, since it looks
    # like evidence and is not, and the cost is 90% of the resolve time on a panel.

  # source: enricher/src/just_dna_enricher/clinical.py:240
  Scenario: the provenance marker is the licence row's dataset, not an authored block
    Given a module drafted by `clinvar_draft`
    When the tautology is decided
    Then the label is read off the licence row's `dataset` column
    # RM4: the claim being established is PROVENANCE — these rows came from this snapshot — and the tool
    # that copied them is the authority on it, so the enricher records it itself rather than asking every
    # author to maintain a declaration whose only reader is this check. The draft marker is
    # machine-written into `dataset`, and a stale one is withdrawn rather than re-labelled
    # (`@rm4-dataset-marker`).

  # source: enricher/src/just_dna_enricher/identifiers.py:1526
  @skip:unsupported
  Scenario: this tier cannot put the question for these rows
    Given a trait currency check on rows the tier cannot address
    When the pass attests
    Then the record is a skip with reason "unsupported"
    # An unbuilt assembly is the standing example: `refget_supports_build` answers the same predicate
    # `refget_accession` raises on (`@refget-raises`).

  # source: enricher/src/just_dna_enricher/clinpgx.py:207
  @skip:not_permitted
  Scenario: a source's terms bar the fetch under the declared use
    Given a ClinPGx source whose terms forbid the declared use
    When `clinpgx check` runs
    Then the record is a skip with reason "not_permitted"
    And the run refuses the fetch in both modes
    # Deliberately its own member: a check skipped because a source's terms bar the fetch is cleared by a
    # DECLARATION, not by egress or by a flag, so folding it into `offline` would send a reader looking
    # for a network problem that does not exist. It is the one a reader would otherwise misdiagnose.
    # This is the second deliberate break in the severity rule, in the opposite direction from the
    # allele-function check: refusing in both modes, because it is not a finding about the data at all —
    # it is a statement that the fetch is not permitted, and `best_effort` means "resolve what you can",
    # never "take what you may not" (`@acquisition-gate-is-not-a-read-gate`).

  # source: enricher/src/just_dna_enricher/alphagenome_check.py:546
  Scenario: a skip reason outside the vocabulary raises rather than recording (RM242)
    Given `alphagenome check` against a local AVI snapshot with a straddling variant and no client
    When the pass attests
    Then the record is a skip with reason "offline" and the absence named in detail
    # This branch wrote `"unchecked"` — one of the per-pass spellings the vocabulary replaced, surviving
    # in a single call site — so the model refused the record and the branch RAISED where it was supposed
    # to attest that nobody asked. Guarded since by an AST walk over every literal `skipped()` reason in
    # the workspace, because pinning this branch would pass the day another pass writes `no_snapshot`.
