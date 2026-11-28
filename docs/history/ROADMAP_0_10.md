# Roadmap — 0.10 (closed)

**Closed on 2026-11-28, when 0.10.0 was cut.** This was `docs/ROADMAP_0_10.md`: 0.10's scope from the 0.9.0 cut, the
desk epic's answers that set its second batch, the consumers' preview and both review rounds' placements. It is kept
here for the record of what 0.10 took in and why. Every item 0.10 scoped shipped, and each record is in
[ROADMAP_HISTORY.md § The 0.10 minor](../ROADMAP_HISTORY.md#the-010-minor) with its `**Residuals**`; RM471, a patch
from `main`, shipped inside the same cut. The known issues 0.10 ships with are in
[INTEGRATION_0_10.md § 4](../INTEGRATION_0_10.md#4-known-issues).

**Where its contents went.** RM469 and RM459 (0.11's from the start), the methylation minor and everything after it
(the VCF 4.4 items, the vocabulary residue, RM149, RM84 and RM67) moved to [ROADMAP_0_11.md](../ROADMAP_0_11.md)
unchanged but for the file they sit in. The known issues both review rounds placed in 0.11 were filed there as
RM472 to RM482. [RM_TOC.md](../RM_TOC.md) indexes every item and is where to look one up. Nothing here is edited as
routine work, the same rule as the rest of this folder.

| Minor | Theme | Items |
|---|---|---|
| **0.10** | an **even** minor (features and the maintainer's decisions, RELEASE_CYCLE.md § Tic/tac): the re-derive signals, four optional additions, the live-answer store; desk epic [#466](https://github.com/winternewt/desk/issues/466) decides the rest | RM399 + RM441 (with S156), RM435, RM385, RM460, RM468 (built); RM265 (desk #468), RM302, RM350, RM294 (desk #467), built on the questions' defaults since 2026-11-28 (S166's two fixes ride on RM385) |
| **0.11** | the next **odd** minor (fixes and decided work), started at 10–20 decided items | RM469; RM459 once the registry reads `KEY_COMPARES` |
| **methylation** | after 0.10, undated until the PacBio samples are in hand | RM317–RM319, RM433, RM56, RM65, RM66 |

Everything here is **additive under Principles 3/4/8**; an item waiting on a version belongs in
[ROADMAP_1_0.md](../ROADMAP_1_0.md). 0.9's two trial rules ended with 0.9: at most two review rounds is now the rule for
every minor ([RELEASE_CYCLE.md](../RELEASE_CYCLE.md) step 5), and an item that emerges during the build joins the same
release again (step 4). The pm's report on both is in [history/ROADMAP_0_9.md](ROADMAP_0_9.md).

**Three of these are not work at all.** RM84's own half shipped in the 0.6 PT2 batch, and only the consumer's
discovery half is open. RM67 is a documented divergence, numbered so it stays findable and does not get re-probed. The
Gherkin corpus (RM149) is **frozen**; its entry says why. All three stay here, so that a reader meets the reasoning
instead of re-deriving it.

Indexed in [RM_TOC.md](../RM_TOC.md), which is the complete list and the place to look an item up.

**Built and in review (the pm, 2026-11-28).** Every item of 0.10 is on the `0.10` branch (5e20ce89). Review round 1 of
at most two runs on it now. The consumers' preview ran on the first batch (992e85b1); the second batch (RM265, RM302,
RM294, RM350, S167) goes to just-module-creator **in parallel with round 1**, not before it as RELEASE_CYCLE step 6
encourages for an even minor, because the registry holds its ClinVar-scale re-derive for 0.10's release. Its findings
are placed with the round's classes.

**Review round 1, placed (the pm, 2026-11-28; classes on 5e20ce89, no blocker found).** By RELEASE_CYCLE step 5:
a class this release introduced on a new surface is fixed in the release, before round 2, each fixed as a class with
its catch; what 0.10 did not introduce, or what only withholds, is a known issue in 0.11.

- **In 0.10, before round 2:** C1 (`repeat_grade`'s old-reader break: a test listing new closed-vocabulary members
  against v0.9.0, the upgrade note fed from it; a 0.9 compiler's `table_file_near_miss` on `repeat_grades.csv` joins
  the note); C2 (the merged block merges every field over both blocks and keeps an authored value the source does not
  contradict); C3 (an answered `(gene, repeat_unit, locus_id)` replaces its rows, `--rederive` reaches the pass, the
  licence row from what the run covered, the grade stripped on write, contested keys counted); C5 (as one class:
  the one-normalizer test's exemptions re-derived, the pre-0.10 sites riding along); C6; C7. From the single-model
  list: 2 (`effect_direction` dropped when no row states it, as RM302 drops an unstated register, so a studies
  module's digest does not move for nothing); 3 (a stub in `allele_function.csv` or `repeat_alleles.csv` withholds
  that pass, never refuses the run 0.9 ran); 4; 6 only if RM265's specified cross-check is missing, else nothing;
  7 (fixed here).
- **C4, split:** in 0.10 the HLA record names the tables it read; widening to diplotype and haplotype names is
  0.11's, decided (`@roster-is-as-wide-as-the-tables-it-reads`), a known issue of 0.10.
- **Known issues, 0.11:** 1 (the answer store replays an anchored indel as could-not-ask without a sequence service:
  a withhold, and the host that asked for the store reads a local FASTA); 5 (a corrupt IPD snapshot reads present:
  judge by payload); 8 (the genotype-mismatch check reads `conclusion` only).
- **No change:** 9 (a Python caller passing a bad URI gets the `ValueError` the reference documents); 10's contested
  count rides on C3.
- **Round 2** reads RM399, RM441, RM460 and RM385's left-alignment core, which round 1 read lightly, with a fourth
  model in Grok's place, and gets this list so nothing here is reported again.
- **Done (the lead, 2026-11-28):** every fix placed in 0.10 above is on 0.10 at `12975c1d` (merged suite green bar
  the floor guard, which the cut moves); round 2 runs on that commit with Opus, Sol, Argon and Grok 4.6 high-fast.

**Review round 2, placed (the pm, 2026-11-28; the last round, on 12975c1d).** Three runs answered (Opus, Sol, Grok
4.6 high-fast); Argon timed out. The review found no blocker; the placement is the pm's, by round 1's rule: a wrong
answer (not a withhold, a raise or latency) that 0.10 introduced, on a surface a consumer gates on, is fixed in 0.10
with its catch and no third round. Everything else is a known issue for 0.11.

- **Fixed in 0.10, no third round:**
  - **Single 3, the re-derive records (RM399, RM441).** 0.10's headline surface, and the registry's sweep waits on it.
    A record that answers "no re-derive" where the truth is "yes" or "unknown" is a silent stale module: `sources.csv`
    is missing from 0.8.0's record (RM383 retires a licence row on re-derive), and an unlisted intermediate patch is
    skipped where it should count as unknown. The fix: walk consecutive versions, an unlisted one withholds, and each
    table gets the first release that produced it (so `repeat_grades.csv` no longer answers 0.8.8). The catch is a
    test over every table in every pair of consecutive tags.
  - **Single 1, RM460's code in the carried set.** `rsid_genotype_reads_as_two_events` leaves `CARRIED_WARNING_CODES`:
    its sentences tell the author the edit that clears it (author the event's coordinate row). The rule is that a
    code's classification follows its remediation. A sentence under the code that no authored edit clears gets a
    carried code of its own, a split rather than a move. This costs nothing until `manifest.compilation.carried` is
    first published, and is permanent after. The catch is the classification test flipped, plus a check that no
    sentence emitted under a carried code proposes an authored edit. Single 6, the unpinned clauses telling the
    unasked and undecided sentences apart, rides along because it is the same lines and a test only.
  - **R3, a short FASTA read used as a full window (RM385).** A read past a contig's end comes back clipped, and
    `_left_align` reads it as whole, so `MT:16599 A>AA` becomes `MT:16598 G>GA`, a variant at a position that does not
    exist. CIViC drafting writes it into an authored row. A real input reaches it: an hg19 `chrM` coordinate (the Yoruba sequence, 16571
    bases) read against GRCh38's MT (16569). The fix: a short window withholds, and the memo never stores a clipped
    read under the interval asked. The catch is that test at the contig end, over every reader of the window.
  - **R4's first half:** CI checks out with `fetch-depth: 0` and tags, so the tag tests (round 1's C1 and C6, and
    single 3's catch above) run there. The setting that turns their skip into a failure is 0.11's.
- **Known issues, 0.11:** R1 (a lock held across I/O: latency, and one `SQLITE_BUSY` disables the store for the
  run); R2 (`layout.atomic_writer` writes every sidecar 0600, so a second account re-hashes a shared FASTA: fixed at
  the writer, the class); R4's skip-to-failure flag; R5 (a FASTA removed mid-run raises `OSError` where it should
  withhold); R6 (the FASTA identity cache is keyed on size and mtime only); single 2 (two contradictory sentences for
  one mirrored site, older than 0.10); C6's walk widened to constants and aliases.
- **For the cut's documents:** single 4's five names (`FASTA_SCHEME`, `VALID_FASTA_CONTIG_STATUS`,
  `ALL_SPELLINGS_CLAIMED_CODE`, `REPEAT_GRADE_FACT_FIELDS`, `StoreSetting`) are documented in the docs pass. On single 5,
  INTEGRATION_0_10 lists as old-reader breaks the fields new in 0.10 on `extra="forbid"` authored models (a 0.9
  compiler refuses a reversed 0.10 module that uses one), as INTEGRATION_0_7 counted `VerificationRecord.producer`.
  The manifest's new keys are not breaks.
- **Round 1, corrected:** C7 holds for the `.fai` only (`.refget.json` is R2); C1 and C6 hold on a full clone only
  (R4), and C6 misses constants (single 4).
- **Not placed:** what the review itself marked wrong or known (`civic reproduce` offline, S163's per-call
  `AnswerRun`, CIViC's `read_window` withholding).
- **Blind spots, stated:** Argon's share is missing, and RM435, RM302, RM265's cross-check and seqrepo REST's
  out-of-range reads were read lightly. They do not block, and there is no third round.
- **Filing:** the lead files an `RMn` in 0.11's roadmap for each known issue, round 1's included (1, 5, 8, C4's
  widening). The cut's INTEGRATION_0_10 and CHANGELOG entry cite each.
- **Done (the lead, 2026-11-28):** every fix placed above is on 0.10 at `0ded96cd` (merged suite green bar the floor
  guard, which the cut moves). The review is closed and **the cut is called** (the pm, 2026-11-28).

---

# 0.10's scope — a small schema release right after 0.9

The items, each optional for an author: RM399 with RM441 (one design, which also carries S156's per-table "newest enricher release that could change it"), RM435, RM265, RM385, RM460, RM468, and from desk #467 RM302, RM350 and RM294. The table above is the list to count from.

**Filed at the 0.9.0 cut (2026-11-19), from 0.9's known issues and residuals:** RM459 (the second known issue, waiting on the registry's S36) and RM460 (the warning code RM449 named for 0.9, placed in 0.10 by the pm); their entries follow RM385. RM458, RM461, RM465 and RM466 were filed here too and went back into 0.9 at the rescope (2026-11-26). **Placed at the redone cut (2026-11-26):** RM468 (S162, a persistent store of live answers, the pm's placement beside RM399 and RM441) moved in from ROADMAP.md, and RM469 (RM461's residual) was filed; both follow RM460.

The ten entries moved to [ROADMAP_HISTORY.md § The 0.10 minor](../ROADMAP_HISTORY.md#the-010-minor) at the cut, each with its `**Residuals**` line, and RM471 from `main` after them.

## RM459 — how it left 0.10: moved to 0.11 to wait on the registry

Kept here as RM412's split was kept in [ROADMAP_0_9.md](ROADMAP_0_9.md): the record of a decision that moved an item
out of this minor. RM459 was filed at the 0.9.0 cut into 0.10's scope (0.9's second known issue). **The pm,
2026-11-27:** moved to 0.11 under the tic/tac rule, since its fix is the registry's first (its S36, reading
`KEY_COMPARES`) and what is left here is decided fix work, an odd minor's. The item is open in
[ROADMAP_0_11.md](../ROADMAP_0_11.md#rm459--with-the-registrys-proxy-set-and-hugging-face-off-a-gene-lookup-on-clinpgx-cpic-drug_labels-or-civic-answers-could-not-ask).
