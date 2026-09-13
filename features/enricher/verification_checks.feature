# The verification vocabulary: every check a module can attest to having been put.
#
# Source of truth: schema/src/just_dna_format/vocab.py's VALID_VERIFICATION_CHECKS (each member carries
# its own line saying which command emits it, or that it is RESERVED),
# enricher/src/just_dna_enricher/verification.py, and docs/ENRICHER.md § the check table.
#
# The line that decides whether a pass belongs in this vocabulary at all is whether it compares
# something the module ASSERTS. A pass that records what a source says and adjudicates nothing has no
# check name and must not gain one — a member for it would let a manifest report a check where no
# question was put. That is why `gene_validity.csv`, `clinical_assertions.csv`, `frequencies.csv` and
# `gene_metrics.csv` have none.
#
# Every record is one of three things and the model enforces the split with two constructors, because
# the `ran` and `skipped` shapes cannot both be filled: `ran(subjects, findings)` where findings is 0,
# `ran` where it is not, and `skipped(reason)`. A zero out of zero on a check that could not run is the
# clean-looking pass the whole skip vocabulary exists to prevent.

Feature: The verification checks and their three outcomes
  A check compares an authored value against a reference. It reports and never repairs, and the record
  is written unconditionally — there is no `--attest` flag, because an optional record is ambiguous
  between *the check was not run* and *it ran without the flag*.

  # source: enricher/src/just_dna_enricher/verification.py:201
  @tri_state
  Scenario Outline: a record is one of three things, and the split is two constructors
    Given a check that <situation>
    When the pass attests
    Then the record is <shape>
    # Two constructors rather than one with an optional `skipped`, because the two shapes cannot both be
    # filled and the model refuses a record that tries — making the split visible at every call site is
    # cheaper than discovering it as a validation error.
    Examples:
      | situation                             | shape                                  |
      | ran and agreed with the source        | ran, subjects=N, findings=0            |
      | ran and disagreed                     | ran, subjects=N, findings>0            |
      | could not be put at all               | skipped, with a vocabulary reason      |

  # source: enricher/src/just_dna_enricher/enrich.py:2186
  @check:reference_allele
  Scenario: an authored ref against the actual reference sequence
    Given a variants.csv row stating ref "A" at a locus whose reference base is "G"
    When `enrich` runs with a sequence reference
    Then the record names the subjects compared and the disagreements found
    And nothing in variants.csv is repaired
    # The clean example of the tier division: the compiler can catch two rows contradicting EACH OTHER
    # about a reference base, and only the enricher can catch a row contradicting THE GENOME. A "ref
    # mismatch" has three causes and one window read cannot separate them, so an ambiguous case is
    # withheld and the findings group by reason (`@ref-mismatch-causes`).

  # source: enricher/src/just_dna_enricher/enrich.py:2253
  @check:genome_build_agreement
  Scenario: authored coordinates against the declared assembly
    Given a module declaring GRCh38 whose coordinates match GRCh37
    When `enrich` runs
    Then the record carries the disagreeing rows
    # This is the one recorded finding `strict` acts on at compile time: two authored files contradict
    # each other about the build, which is a fact rather than an opinion
    # (`@a-recorded-judgement-is-a-fact`). The ±1 shift reading is wrong on an old-assembly coordinate,
    # and only two evidence tiers supersede it (`@old-assembly-vs-shift`).

  # source: enricher/src/just_dna_enricher/enrich.py:2286
  @check:clinical_significance
  Scenario: an authored clin_sig against ClinVar's own, allele-exactly
    Given a variants.csv row calling a variant pathogenic
    And a ClinVar snapshot calling the same allele benign
    When `enrich` runs
    Then the record carries the finding and ClinVar's review-star count
    And the finding never escalates under strict
    # Every other check compares an authored value against a FACT — the genome's bases, a deterministic
    # digest, a registry's own id — where the source is simply right. A `clin_sig` disagreement is two
    # opinions differing, and ClinVar is not truth: a curator who has read the primary literature and
    # disagrees with a one-star submission is doing their job. Failing the compile would make the format
    # arbitrate a clinical dispute (`@clinsig-never-escalates`).

  # source: enricher/src/just_dna_enricher/enrich.py:2432
  @check:rsid_coordinate_agreement
  Scenario: an authored rsID and coordinate PAIR against the reference
    Given a variants.csv row carrying both an rsID and a coordinate
    When `enrich` runs
    Then the record says how many pairs were checked and how many disagree
    # The pair co-identifies one variant, so the redundancy is checkable. NCBI rather than Ensembl is the
    # oracle for merge status (`@ncbi-merge-oracle`).

  # source: enricher/src/just_dna_enricher/enrich.py:2369
  @check:rsid_currency
  Scenario: an authored rsID against dbSNP's own status
    Given a variants.csv row whose rsID dbSNP reports as merged
    When `enrich` runs
    Then the record carries it
    And `VALID_RSID_STATUS` has four members, not three
    # `absent` means a typo OR a withdrawal, and the message names both readings — two readings of one
    # absence are not automatically equal (`@rsid-absent-two-readings`,
    # `@absence-is-weighted-by-the-base-rate`).

  # source: enricher/src/just_dna_enricher/enrich.py:2470
  @check:dataset_currency
  Scenario: a recorded dataset against the release that source publishes now
    Given a sources.csv row whose `dataset` names an earlier release
    When `enrich` runs with currency checking
    Then the record says the module's own claim about where its rows came from is behind
    # The subject is the module's own ASSERTION, which is why this is a check and not a recording pass. A
    # currency check asks the SOURCE, never the cache the rows were drafted from, and a digest label does
    # not compare against a dated one (`@currency-asks-the-source-not-the-cache`).

  # source: enricher/src/just_dna_enricher/enrich.py:2345
  @check:evidence_status_currency
  Scenario: a recorded curation status against what the source says about that item now
    Given a studies.csv row whose confidence records a CIViC status from when it was drafted
    And a CIViC snapshot where that item has since been accepted
    When `enrich` runs
    Then the record names it
    And the finding never escalates under strict
    # A sibling of `dataset_currency` and deliberately not the same member: that one asks which RELEASE a
    # table came from, this one whether a per-ITEM judgement has moved, and the two currency findings stay
    # apart (`@a-source-recuring-is-not-a-strict-matter`). A source re-curating is not an authoring error.

  # source: enricher/src/just_dna_enricher/enrich.py:2319
  @check:published_refutation
  Scenario: an authored direction against the refutations a source publishes
    Given a variants.csv row asserting direction "risk"
    And a CIViC snapshot that refutes that assertion
    When `enrich` runs with a CIViC snapshot available
    Then the record carries two findings under one record
    And it names its `status_basis`
    And the axis is withheld rather than reversed
    # Two findings under one record because they share a subject SET: the source asserts and refutes, or
    # the source has only ever refuted and the module asserts anyway. Refute is not reverse — evidence
    # against a claim withholds the axis, it never writes the opposite value (`@refutation-withholds`).
    # Never escalates under strict: a source disagreeing with itself is not an authoring error. On the
    # `accepted` basis the class is empty by construction, which is why the basis is named.

  # source: enricher/src/just_dna_enricher/literature.py:1337
  @check:citation_existence
  Scenario: an authored pmid or doi against PubMed and Crossref
    Given a studies.csv row citing a PMID
    When `enrich-literature` runs
    Then every citation gets an existence verdict
    # A paywall hides the FULLTEXT, not the record, and Crossref covers what PubMed does not index
    # (`@citation-existence`). Existence is not identity — a lookup must say WHAT it found
    # (`@existence-not-identity`).

  # source: enricher/src/just_dna_enricher/literature.py:1413
  @check:citation_identifier
  Scenario: an authored doi against the registry's own for that PMID
    Given a studies.csv row carrying both a PMID and a DOI
    When `enrich-literature` runs
    Then only the citations carrying an authored identifier are compared
    And a citation PubMed named no identifier for rides in `detail` rather than shrinking the denominator
    # Two readings of one drop-out must not be one sentence: a citation leaves the comparison because
    # PubMed named no identifier OR because a curator wrote that row, and reporting the second as the
    # first is a claim about PubMed nobody established. A DOI has THREE states rather than two —
    # resolved, a pinned verdict about a DOI the module no longer cites, and one no run ever put the
    # question for, which is what a `--no-doi` run followed by a plain one leaves behind.

  # source: enricher/src/just_dna_enricher/literature.py:1484
  @check:provenance_quote
  Scenario: an authored quote against the article's own text
    Given a studies.csv row carrying a provenance_quote
    And a retrieved fulltext for that article
    When `enrich-literature` runs
    Then `subjects` counts the quotes a retrieved text SETTLED, never the quotes authored
    And the remainder rides in `detail`, split into its two kinds
    # Three questions with three different denominators, and one record cannot carry them. The remainder
    # splits in two and the two must not be one sentence: an article whose text could not be read, and a
    # quote NOBODY WENT LOOKING FOR because the sidecar's pinned counts do not describe the quotes the
    # module carries now. Only the second is cleared by deleting the sidecar, and calling it a retrieval
    # failure is flatly false for an open-access article read on the previous run. A quote is an
    # attestation — a sharper refusal than redundancy-bearing (`@quote-attestation`).

  # source: enricher/src/just_dna_enricher/literature.py:1472
  Scenario: a pinned count has to match, not merely be non-zero
    Given a literature.csv row pinned at two quotes and a studies.csv now carrying one
    When `enrich-literature` runs
    Then the whole row goes unexamined
    # A row pinned at two quotes says nothing attributable about the one that is left, so it goes
    # unexamined rather than carrying a finding about a quote the module no longer makes.

  # source: enricher/src/just_dna_enricher/pgx.py:576
  @check:allele_function
  Scenario: an authored function_status against PharmVar and CPIC
    Given an allele_function.csv row stating a function
    And PharmVar and CPIC snapshots that disagree with it
    When `pgx` runs
    Then the record carries the finding
    And it warns under strict too
    # PharmVar and CPIC are different expert panels — one assigns a molecular function, the other a
    # clinical one — and they genuinely disagree about some alleles, so failing a compile would make the
    # format arbitrate between the two authorities it depends on. One of the two deliberate breaks in the
    # severity rule; the other, the declared-use gate, goes the opposite way.

  # source: enricher/src/just_dna_enricher/clinpgx.py:372
  @check:pgx_evidence_level
  Scenario: an authored evidence_level against ClinPGx's own
    Given a pharm_variants.csv row stating an evidence level
    When `clinpgx check` runs
    Then the record carries any disagreement
    # `recommendation_strength` is CPIC's and `evidence_level` is PharmGKB's — different axes. ClinPGx's
    # clinical annotations are per GENOTYPE, keyed
    # `(variant_key, drug, genotype, phenotype_category, annotation_id)`; the bare triple is a bug
    # (`@clinpgx-per-genotype`, `@clinpgx-full-key`).

  # source: enricher/src/just_dna_enricher/drug_labels.py:850
  @check:regulator_label_agreement
  Scenario: authored gene, allele and drug claims against five regulators' label annotations
    Given a pharm_variants.csv row naming a gene, an allele and a drug
    When `clinpgx check-labels` runs
    Then the record reports at two join tiers, allele and gene
    And it never escalates under strict
    # Named for the LABELS rather than for any one agency, because the file carries five and baking an
    # authority into a published key is the mistake RM134 caught in `ClinSigConflict` before it shipped.
    # A join with two granularities needs two kinds of subject, or the coarse answer repeats per fine
    # claim (`@the-tier-is-a-property-of-the-subject`).

  # source: enricher/src/just_dna_enricher/strchive.py:720
  @check:repeat_band_agreement
  Scenario: an authored repeat band table against a published repeat-locus catalogue
    Given a repeat_alleles.csv stating bands for a locus
    And a STRchive snapshot whose bands are coarser
    When `check-repeat-bands` runs
    Then the record reports the difference and repairs nothing
    # The corpus has one module the catalogue agrees with and one it is a band coarser than, and the
    # format does not arbitrate between its own authorities.

  # source: enricher/src/just_dna_enricher/acmg.py:769
  @check:acmg_secondary_findings
  Scenario: an authored acmg_sf flag against the published SF gene list
    Given a variants.csv row flagged acmg_sf on a gene the published list does not carry
    When `check-acmg` runs
    Then the record carries the finding
    And nothing fills `acmg_sf` from the list being asked about it
    # Filling the cell from the registry under examination stays refused whatever the attestation does:
    # that is `hints.REDUNDANCY_BEARING`, and it is why these are open-ended checks rather than an apply
    # route (`@hint-redundancy-bearing`).

  # source: enricher/src/just_dna_enricher/identifiers.py:1573
  @check:gene_symbol_currency
  Scenario: an authored gene symbol against HGNC's approved and previous names
    Given a variants.csv row naming a retired gene symbol
    When `check-identifiers` runs
    Then the record names it as previous rather than as unknown

  # source: enricher/src/just_dna_enricher/identifiers.py:1547
  @check:trait_currency
  Scenario: an authored trait CURIE against OLS4
    Given a variants.csv row whose trait_efo_id OLS4 reports obsolete
    When `check-identifiers` runs
    Then the record names the obsolescence and its replacement

  # source: enricher/src/just_dna_enricher/identifiers.py:1631
  @check:gene_locus_agreement
  Scenario: a row's gene against the chromosome its variant sits on
    Given a variants.csv row naming a gene on chr17 and a coordinate on chr13
    When `check-identifiers` runs
    Then the record carries the disagreement
    And nothing is repaired
    # Check the RELATIONSHIP, not the members — at chromosome granularity, repairing nothing
    # (`@gene-locus-relationship`). Two true halves can make one false row (S24): a live gene symbol and
    # a live coordinate that do not belong together.

  # source: enricher/src/just_dna_enricher/identifiers.py:1682
  @check:pgs_accession_currency
  Scenario: an authored pgs_id against the PGS Catalog's record for it
    Given a row citing a PGS accession the Catalog has no record of
    When `check-identifiers` runs
    Then the check reads the response BODY rather than the status
    And the verdict is about the accession, never about the status
    # The Catalog answers 200 with `{}` for a never-assigned id AND for a malformed one, so a status-only
    # reading would call both of them fine. A retired filename still answering 200 is the same shape one
    # source over (`@probe-the-real-file`).

  # source: enricher/src/just_dna_enricher/identifiers.py:1758
  @check:pgs_metadata_agreement
  Scenario: authored training ancestry and cohort against the score record's own
    Given a row stating training_ancestry and training_cohort
    When `check-identifiers` runs
    Then a separate record is written from the accession-currency one
    # Its own member rather than a second finding under the line above: currency asks whether the id
    # still names a score, and this asks whether two cells beside it still match. Two questions, two
    # subjects, so two records.

  # source: enricher/src/just_dna_enricher/litvar.py:975
  @check:literature_coverage
  Scenario: which papers an index holds for a module's alleles, and at which tier
    Given a variants.csv row with an allele-resolved identity
    When `litvar coverage` runs
    Then the record says at which TIER the answer was found
    And a position-level answer to an allele-level question is recorded as such
    # Allele-resolved, position-only and absent are three outcomes, and a coverage answer names the tier
    # it was measured at (`@the-tier-that-answered-is-part-of-the-answer`). An empty id slot is not a
    # suffix, and a prefix search's first hit is a different variant.

  # source: enricher/src/just_dna_enricher/alphagenome_check.py:560
  @check:variant_impact_agreement
  Scenario: a module's variants against AlphaGenome's AVI scores
    Given a variants.csv row inside a knot spanning the PHRED threshold
    And an Atlas client
    When `alphagenome check` runs
    Then the record carries the refinement's verdict
    # Its own member rather than a second writer of `reference_allele`, although the Atlas answers the REF
    # question too: letting one registry's outage write a skip against another's check is exactly what
    # `@one-registrys-outage-may-not-speak-for-another` forbids.

  # source: enricher/src/just_dna_enricher/cli.py:3196
  @check:vrs_allele_id
  Scenario: the check whose every record is a skip, deliberately
    Given a resolution.csv with no source-reported allele ids
    When `vrs mint` runs
    Then the record is a skip with reason "nothing_to_check"
    And the coverage counts travel in `detail` rather than as this record's numbers
    # The member names the CROSS-CHECK — a source's own `ga4gh:VA.…` against the one minted here — and its
    # input is a map this command has nothing to fill from: `resolution.csv` records the ids the tier
    # minted and never where an id came from, so the question was not put. Recording `subjects` as the
    # alleles the run NAMED would say the opposite of what happened, and it is the reading a coverage
    # figure invites, since this pass does end with a number out of a number. The compiler publishes
    # those counts as `manifest.compilation.vrs_alleles` and `vrs_alleles_identified`.

  # source: schema/src/just_dna_format/vocab.py:861
  @check:gene_disease_validity @reserved
  Scenario: a member with no emitter, reserved on the withdrawn precedent
    Given a module carrying gene_validity.csv
    When `gene-validity` runs
    Then it records ClinGen and GenCC verdicts into a derived table
    And it emits no verification record, because it compares nothing authored
    # Wiring it would report a check where no question was put. The name exists now rather than later on
    # the `withdrawn` precedent: adding an emitter is legal in a minor, while adding the NAME late would
    # leave the release that needs it with nothing to write. The member is for a future pass that checks
    # an authored gene/phenotype pair.

  # source: schema/src/just_dna_format/vocab.py:865
  @check:dosage_sensitivity @reserved
  Scenario: the same shape, for a dosage claim no model carries yet
    Given a module carrying gene_metrics.csv
    When `dosage` runs
    Then it records ClinGen's haplo and triplo curation into gene_metrics.csv
    And it emits no verification record
    # No model carries an authored dosage claim to compare it against. The member is for the pass that
    # gains one.

  # source: schema/src/just_dna_format/verification.py:315
  Scenario: a skipped record does not replace a ran one
    Given a verification.json recording subjects=13 findings=0 for a check
    When the same check is re-run offline and records a skip
    Then the existing record stands
    # RM72: `merge_records` is newest-wins per check, and an offline re-run after a full one rewrote a
    # true verdict to `subjects=0 findings=0 skipped=offline`. Newest-wins still holds between two
    # records of the same disposition.

  # source: schema/src/just_dna_format/verification.py:315
  Scenario: unless the authored bytes have moved since
    Given a verification.json recording a verdict over authored bytes
    And those authored files edited since
    When a fresh skip is merged
    Then the existing record no longer binds and the skip wins
    # `existing_still_binds`: an answer over authored bytes the author has since edited is not an answer
    # the document may keep asserting. Without it, `literature`'s deliberate skip-on-changed-citations
    # became a stale finding again, undoing an earlier round.

  # source: enricher/src/just_dna_enricher/verification.py:182
  Scenario: the attestation is bound to the module's authored bytes
    Given an attested verification.json
    When variants.csv is edited afterwards and the module is compiled
    Then the compiler drops the block with a warning
    # Correctly, because the checks were put against rows that no longer exist. Re-running the pass
    # re-attests. Currency of the SOURCE is a different question, read off each record's own `release`.
