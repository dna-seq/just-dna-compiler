# 0.8 part 2: the build plan for the agreed scope

**Status.** Written by the lead on 2026-11-04 from the pm's handout ("0.8 scope agreed: yours to plan and
build") and its two addenda (the tag selector, then `column=value` selectors). This is RELEASE_CYCLE § Minors
step 2: the plan the build runs from without asking. PT1 (the bugfix round) is concluded on the `0.8` branch.
A fresh critic read it the same day against the decision lines and the code; its findings that held are
applied, and the ones that need the maintainer are §4 questions 5 to 7. The pm's third addendum (the
shape agreed after the second measuring run) is folded in.

**How to read it.** The decisions are the maintainer's and live as dated lines under each item in
[ROADMAP_0_8.md](../ROADMAP_0_8.md); where an item has several, the latest wins. This file does not restate
them. It fixes what the decisions left open (§3), names what goes back to the pm (§4), and gives each item the
contract a builder works from (§5). A builder that finds a decided column with no case, or a needed one
missing, stops and sends it to the pm; it never builds around it.

## 1. Branching

1. **Push `0.8`.** The local branch is 150 commits ahead of `origin/0.8` (last pushed 2026-09-25) and 0
   behind; PT1's build (2026-09-30) is among the unpushed commits. The lead's grant covers a fast-forward
   push.
2. **Merge `main` into `0.8`** (`main` is 80 commits ahead of the fork point, `0.8` is 43). A trial merge on
   2026-11-04 conflicted in 13 files. Resolution rules:
   - `compiler/src/just_dna_compiler/compiler.py` and `enricher/src/just_dna_enricher/cli.py` were split into
     packages on `0.8` (RM260) and edited on `main` since (93 lines added, 22 removed). Port `main`'s hunks
     into the package modules that now hold those functions, then take `0.8`'s deletion.
   - `docs/ROADMAP_0_8.md`: `main`'s text wins wholesale (the scope table and every 2026-11-04 decision line).
     `0.8`'s "built" markers for PT1's items are re-applied on top.
   - `docs/ROADMAP.md`, `docs/RM_TOC_*.md`, `docs/CHANGELOG.md`: the union. An item `0.8` closed (PT1) stays
     closed; an item `main` filed or decided keeps its newest line.
   - `.claude/hooks/*`: `main`'s versions (the charter gate is newer there).
   - Code conflicts (`orchestration.py`, `test_declared_use_recorded.py`) are resolved by reading both
     sides, and the full suite runs before the merge commit.
   - **The polars 2 lock lands in wave 0, right after the merge** (A1's second half, moved forward), so no
     lane builds on one polars and merges onto another. Its RELEASE_RECORDS line goes with it.
3. **Every item is built in its own worktree** under the scratchpad, on a `build/RMnnn` branch cut from
   `0.8`, and merged into `0.8` by the lead once its tests pass. `main` is merged into `0.8` again at each
   wave boundary (§2), so a patch triage lands on `main` reaches the builders within a wave.
4. **Nothing in this scope lands on `main`.** RM338 is the exception that proves it: its patch half is
   `main`'s (a patch, built by the lead there), and RM337's warning builds on `0.8` after the sync that
   carries RM338 across.

## 2. Order, and what runs in parallel

Four lanes, one builder each, serial inside a lane. A builder is a subagent (Opus) with this file and its
lane's §5 block as its brief. The lead reviews and merges.

| Wave | Lane A: small schema adds | Lane B: the meta-table | Lane C: indel placement | Lane D: derived inputs |
|---|---|---|---|---|
| 0 | the push, the sync and the polars 2 lock (§1), the lead alone; RM338's patch on `main`, the lead | | | |
| 1 | RM342 (with P4's amendment), RM336, RM322, RM334 | waits on §4 question 1 (built under its default if no answer) | RM304 | RM303 (with the Goals amendment) |
| 2 | the `StudyRow` batch: RM325, RM326, RM328, RM329, RM330's stratum, RM331's author half, RM332, and the locus-level derived columns (§3 item 10) | RM28 / RM323 / RM324 / RM327 / RM330's `sex`, one item, without the study-orphan widening | RM292 | RM333's Open Targets lane, carrying RM239, RM236 and RM238's coloc (§4 question 2) |
| 3 | RM335, RM337 (after the sync that carries RM338), RM253 | the derived columns (`tradeoff`, the resolved facts), then the study-orphan widening once the `StudyRow` batch has merged (both edit `_cross_validate_studies`) | RM305, after RM303 | RM331's computed LD pair |
| 4 | | | RM267, then RM270 | |
| 5 | reference examples (§6), INTEGRATION_0_8, the review wave and the dogfooding wave | | | |

**Why this order and not the scope table's listing.**

- **RM303 first in lane D**: RM305's and RM333's lanes write `release.json`, and RM305's own text asks for
  RM303's model if it has landed. Building a lane before the model means writing a hand-built dict the
  model's guard then refuses.
- **Lane C runs RM304 → RM292 → RM305 → RM267 → RM270**, not the scope table's order. RM292 makes every
  check name its witness, RM305 is the witness those checks name, RM267's comparison needs both, and RM270
  carries the `vrs_id` RM304 versions.
- **The `StudyRow` batch is one builder**, because seven items edit one model, one parquet and one duplicate
  check. In parallel they would conflict on every file.
- **The outcome strip and `eur_only_evidence` are lane A's**, built with the `StudyRow` batch, because
  they derive from `phenotype_class` and `ancestry` and nothing in the meta-table.
- **The study-orphan widening waits for the `StudyRow` batch**: both edit `_cross_validate_studies`.

**Rough sizes**, for the person's planning, not as a promise: wave 0 about 2 hours; lane A about a day; lane
B one to two days; lane C two days; lane D two days, most of it the Open Targets lane. With four builders in
parallel, waves 1–4 take about three working days, then the review and dogfooding waves.

## 3. Decided here (reversible until the cut, listed for review)

Each is the lead's call under LEAD.md step 3: a reversible choice with a recommendation. The rejected
alternative is beside it. Names still get the P5 audit in §5, and the audit can overturn any of them.

**The meta-table.**

1. **File name `meta.csv`, parquet `meta.parquet`.** The maintainer's and every document's working name.
   Rejected: `statements.csv` (accurate but nobody's word for it), `combinations.csv` (wrong for a
   one-member facts row), `meta_conclusions.csv` (a facts-only row concludes nothing).
2. **One grammar for every member: `table[column=value, column=value]`.** A concrete row is the selector over
   its table's full key (`variants[variant_key=rs429358, genotype=C/C]`), a locus is
   `variants[variant_key=rs10455872]`, a named allele is `allele_function[gene=APOE, allele=ε4]`, a tag set
   is `variants[flags=legacy_longevitymap]`. The precedence the maintainer decided then falls out of the
   conditions: the full key is a concrete row, `variant_key` alone is a locus, otherwise more conditions
   outrank fewer. Rejected: a bare `rs10455872` shorthand beside it (a second grammar; additive later if
   authors ask), and the typed prefixes of the audit's appendix (`allele:APOE=ε4`, `dip:…`), which were one
   grammar per member kind.
   **A named allele is an `allele_function.csv` item** (the pm's setting in the third addendum, which
   overrode this plan's first choice of `haplotypes.csv`). The cost accepted with it: a named allele the
   module uses as a member needs an `allele_function.csv` row, every column but the key empty, which is
   also where RM334's HLA alleles live.
3. **Members are joined by `&` at bracket depth 0, in one `members` cell.** The parser is bracket-aware, so
   an `&` inside a value (RM253's DPYD names, `c.1129-5923C>G&c.1236G>A(HapB3)`) is data, and so is `|` in a
   phased genotype. The shared `MULTI_SEP` splitter is never used on this cell. A value may not contain `[`,
   `]`, `,` or `=`; such a selector is refused with a message naming the character. Rejected: `member_a` /
   `member_b` columns (no separator at all, but every corpus case is arity 2 only until it is not, and a
   third member would be a third column).
4. **The table key is the normalized member set plus `trait_efo_id` plus `sex`.** Members are sorted for
   the key, so `A & B` and `B & A` are one key, refused as a duplicate. Within a member, conditions are
   sorted too. `sex` is in the key because it scopes the whole row, facts included: a `male` row and a
   `female` row for one member set are two statements, not a duplicate. A row with `sex` outranks the same
   key without it, for that sex.
5. **Columns**, all optional except `members`: `trait_efo_id`, `trait_role` (closed: `mediator`; empty means
   the trait is an effect, the maintainer's third addendum),
   `direction` (the existing vocabulary), `conclusion`, `negatives`, `tier`, `age_of_action`,
   `age_of_action_confidence`, `flags`, `pmid`, `doi`, `sex` (closed: `male`, `female`). A row stating none
   of the finding or fact columns is refused as empty. `trait_role` without `trait_efo_id` is refused.
   `pmid` and `doi` follow `StudyRow`'s rules, the `NONE` sentinel included (decided in the third
   addendum for every citing table, A2).
6. **A per-trait row needs an allele-bearing member** (the audit's gap 2): every member of a row with
   `direction` must fix an allele, meaning a `variants` member with a `genotype` condition, a `diplotypes`
   or `pharm_variants` member that names its alleles, or an `allele_function` member. **A bare `variant_key`
   member also fixes an allele when every `variants.csv` row of that locus states the same
   `effect_allele`**, and `direction` is then about that allele. This is the audit's second run (§6): v2
   is uniform on 228 of 228 loci, and the rule halves the per-trait rows (about 134 against 268 with
   genotype keys), the reduction rule's direction. A locus whose rows disagree on `effect_allele` or state
   none draws the warning `meta_member_allele_ambiguous` and its `direction` is withheld (the maintainer:
   a warning, not a refusal). A tag selector on such a row is refused, naming it. The four loci v2 marks
   "allele not determined" honestly get no per-trait row. The member tables are `variants`, `diplotypes`,
   `pharm_variants` and `allele_function` (the pm's setting); `studies` is excluded by the maintainer's
   bound.
7. **`tier` is open text, and `module_spec.yaml` gains `tier_scale`** (one free-text name, the `weighting:`
   pattern), copied into the manifest and listed in `REVERSE_RECONSTRUCTED` so `reverse` writes it back
   (else the recompile refuses every `tier` cell, a P7 break). A `tier` cell in a module with no
   `tier_scale` is refused (`@weight-has-no-unit`). Values are not checked against the scale: the scale is
   the module's, and v2's `X`, `A-`, `B-` are legal.
8. **The compile writes two parquets.** `meta.parquet`: one row per authored row, the selector text kept
   verbatim for `reverse`, the match count, and the expanded matches as a list column of (table, row key).
   A matched combination replaces the findings of exactly the rows in that list, which is how a consumer
   knows what it replaces without evaluating anything (P1). `meta_resolved.parquet`: one row per
   single-statement row that any meta row reaches, carrying each fact column after precedence, `tradeoff`
   (item 9), and a `withheld` list naming the columns two incomparable, disagreeing matches withheld.
   Combination matching against a genome stays the consumer's join, as every table's is. Rejected: a third
   parquet for the expanded members (it folds into `meta.parquet`'s list column), and resolved facts on
   `weights.parquet` and `diplotypes.parquet` (two published parquets widened for one concern).
   **Specificity across member kinds** (the audit's gap 1, decided in the third addendum: "the narrower
   condition wins across tables"): a `diplotypes` member is more specific than an `allele_function` member
   naming either of its two haplotypes in the same gene. This is an ordering of members, not a selector
   condition, so the maintainer's bar on cross-table selectors is not crossed. With it the ε2/ε4 diplotype
   row settles the ε2 and ε4 rows' disagreement, and without it that column is withheld.
9. **`tradeoff` is a column of `meta_resolved.parquet`**, Kleene as RM327 says: true when an allele-bearing
   member has both a `protective` and a `risk` per-trait row, false only when every trait's judgement is
   stated and none opposes another, otherwise null. The name moves from `RESERVED_NAMES_0_4` to
   `MISPLACED_COLUMN_REASONS` in the same commit.
10. **The two locus-level derived outputs** (the audit kept both): `eur_only_evidence` (RM328) and the
    outcome strip (RM326) become columns on `weights.parquet`, repeated per genotype row, since a parquet
    column is approximately free and adds no file. Both Kleene: `eur_only_evidence` is true when every
    supporting study row states only `EUR`, false when one states another code, null when any states none;
    a strip cell (`healthspan`, `lifespan`, `exceptional`) is true when a study row of a mapped class
    exists and null (untested) otherwise, never false. The class-to-cell map is a format constant over the
    recommended classes, taken from v2's requirements §5.1 as written there and listed in the builder's
    report for the pm; MULTIVARIATE_AGEING and any class outside the twelve map to no cell, which v2's
    README states (the audit's gap 8).

**The `StudyRow` batch.**

11. **`sample_size` is the total analysed, cases included; `n_cases` is the case count.** A row with
    `n_cases` greater than `sample_size` is refused (the two cannot both be true, and both columns are new,
    so no published row can hold the pair). `sample_unit` is closed: `individuals`, `lives`. A
    `sample_size` without `sample_unit` is refused (`@weight-has-no-unit`).
12. **`ancestry` is multi-valued over the 1000G superpopulations** (`AFR`, `AMR`, `EAS`, `EUR`, `SAS`),
    closed. `VALID_TRAINING_ANCESTRY` (pgs.py) holds the same five plus `multi`, so the five become one
    constant and the PGS set is derived from it with `multi` added: one vocabulary, not two. A
    multi-ancestry study lists its codes rather than writing `multi`. `population` stays free text.
13. **`phenotype_class` is open, with v2's twelve as recommended members**, spelled as RM326's list spells
    them (`FAMILIAL`, `MR`, `BIOMARKER`, not the long forms). A token outside them draws the new warning
    `phenotype_class_unrecognized`.
14. **`age_min` / `age_max` are numbers in years, either may be empty** (an open band), and `age_of` is
    closed: `participant`, `parent`. No refusal ties them together.
15. **`stratum` / `stratum_level` are free text**, both or neither. Rejected: a recommended vocabulary for
    `stratum` (a warning nobody asked for).
16. **The duplicate-citation narrowing** (RM140) treats two rows for one `(variant_key, pmid)` as distinct
    when any of these is both stated and different: `phenotype_class`, the band (`age_min`, `age_max`,
    `age_of`), the stratum pair. Unstated is not different (`@absent-is-not-different`). Gap 12 decided
    these three and no more.
17. **`effect_unit` reaches `weights.parquet` from "the matching study row"**, and `VariantRow` has no
    field naming a study, so "matching" is undefined: sent to the pm (§4 question 5). Default meanwhile:
    the unit joins only when every study row of the variant that states a unit states the same one;
    otherwise the column is null, never a guess.

**Elsewhere.**

18. **`pmid`'s sentinel is `NONE`, exactly.** Other spellings an author might reach for (`NA`, `n/a`, `-`,
    `none`) are already refused today; the message gains a pointer to `NONE`. With `NONE`, `doi` is
    required and checked against `spec.DOI_PATTERN`, which exists; `validate_pmid_cell` has no DOI arm
    yet, and A2 adds it.
19. **RM342's toolchain block** is `manifest.compilation.toolchain: dict[str, str] | None`, with the keys
    `python` and `polars`. A future library is a new key. Where its reason fires is §4 question 7.
20. **RM304's names**: `manifest.resolution.vrs_version` (the pin) and a `vrs_version` column beside
    `vrs_id` in `resolution.csv` and in every parquet carrying an id **we minted**; `frequencies.parquet`'s
    `vrs_id` is gnomAD's and gets none. The new reason `vrs_version_differs` belongs to the enricher's VRS
    verify pass (RM304's question 2), not to `verify_manifest`.
21. **RM303**: the builder first lists what each reader of `release.json` reads (the item's own method),
    then types every key a reader reads, plus `parents`; the rest ride in `extra="allow"`. The drifted
    pairs settle on `row_count` and `license` (the spelling `module_spec.yaml` already uses), and the old
    spellings are read on input, never written. `builder` against `builder_version`: read what acmg's
    builder means by `builder` first; default, `builder_version` is the field and `builder` is read as an
    alias if it holds a version.
22. **RM334's grammar applies where `gene` starts with `HLA-`**: `*`, then colon-separated numeric fields,
    then an optional expression suffix (`N`, `L`, `S`, `C`, `A`, `Q`), IPD-IMGT/HLA's published grammar.
    "At a stated resolution" is read as: the name states its own resolution by its field count, and the
    check refuses a name with fewer than two fields; no column states it. A malformed name is a refusal,
    gated on the same published-module scan RM336's refusal owes (§5, A2).
23. **RM335's `pmid` and `doi` are optional and draw no warning**, because 17 of v2's 77 rows have no PMID
    and the table is annotation only (R-ANIMAL-1); when a row cites, the pmid/doi pair's rules apply (A2). Rejected: a fourth warning code for an uncited row. Its
    `concordance` is closed (`concordant`, `discordant`, `nonmonotone`); an empty cell is unstated, which
    is what v2's 55 "unclear" rows are.

## 4. Sent to the pm, each with the default the build takes meanwhile

**Answered by the pm, 2026-11-04:** questions 2, 3, 4, 5 and 7 accepted as their defaults (RM238 moved to
0.9 in 3c18ea3); 6 answered in the third addendum. Question 1 is with the person; the build takes its
default meanwhile.

1. **The meta-table's member grammar and name (§3 items 1–4).** A one-way door at the cut. Default: as
   written. This is the block to read closely.
2. **One Open Targets lane for four inputs.** The 26.09 release on EBI's FTP lists `l2g_prediction`,
   `credible_set`, `colocalisation`, `variant` and `study` side by side (listing read 2026-11-04), under the
   one CC0 marking RM333's probe checked. So RM333's lane can feed RM239's posterior (from `credible_set`,
   onto `gwas_effects.csv`), RM236's per-transcript consequence (from `variant`, as RM236's recommended
   derived sidecar), and the coloc behind effector confidence (from `colocalisation`) in place of RM238's
   per-tissue GTEx table, which its own entry parks on a consumer. One lane and one licence instead of
   three sources: the reduction rule's direction. Default: build it that way; RM238's GTEx table stays
   parked and moves to 0.9. Field-level contents (that `variant` carries transcript consequences) are
   unprobed and are the lane's first hand-run step.
3. **RM267's open half: may the enricher write the corrected spelling?** Default: no. A disagreement between
   two authorities withholds the row and reports both placements; nothing is rewritten in 0.8
   (`@enrichment-is-validation`).
4. **RM331's LD reference.** Default: Ensembl REST's pairwise LD endpoint over the 1000 Genomes phase 3
   superpopulations, which matches decision 12's codes and adds no new licence. Unprobed; its first step
   is a hand-run call.
5. **RM332's "matching study row" is undefined**, since `VariantRow` names no study. Default: §3 item 17's
   unanimity rule (a unit joins only when every stating study row agrees).
6. **`doi` on the meta-table.** Answered in the third addendum: yes, on every citing table (A2).
7. **Where RM342's toolchain reason fires.** The decision says `verify`, but `verify_manifest` never
   recompiles: it re-hashes the files on disk against the manifest, so the running polars cannot change
   its answer (checked in `integrity.py`). The places that compare a fresh compile against a recorded
   digest are the publish collision check (`upload.py`, a re-publish whose digest differs) and the release
   sweeps (`release_records.py`). Default: the reason `toolchain_differs` fires there, when the digests
   differ and the two manifests' recorded toolchains differ; `verify_manifest` is unchanged.

## 5. Per-item contracts

Every block follows the shared rules in §7. "Touch" lists the places a builder must reach; it is a floor,
not a ceiling, and the registry guards (`_ALL_MODELS`, the warning-code and feature-corpus equalities) will
name any it misses.

### Lane A: small schema adds

**A1. RM342, the toolchain in the manifest.** Add `Compilation.toolchain` (§3 item 19), filled at compile
from `sys.version_info` and `polars.__version__`. The reason `toolchain_differs` fires where §4 question 7
puts it: where two manifests' digests differ and their recorded toolchains differ, it replaces the plain
collision or mismatch; when either toolchain is unrecorded (an older manifest), the existing behaviour
stands. Amend Principle 4's reproducibility sentence to "pinned via `compiler_version`, the recorded
toolchain and the resolved reference", with the why in CONSTITUTION_AMENDMENTS_HISTORY.md, in the same
commit. The polars 2 lock already landed in wave 0. Test first: two manifests for one module whose
digests and recorded polars versions differ are reported as `toolchain_differs`, never as a collision.

**A2. RM336, a DOI in `pmid`, and the `NONE` sentinel.** Before building, scan the published modules (the
registry catalogue through `registry_search` and `reference_examples/`) for a DOI in `pmid`; any hit goes to
the pm, not into the build. Then: `validate_pmid_cell` refuses a cell whose only token is a DOI and names
it (RM50's arm is the template); accepts `NONE` (§3 item 18), which makes `doi` required and validated;
`extract_pmids` returns nothing for `NONE` and for a DOI, so the literature pass never looks up `10`,
`1101`, and so on. **The pair applies to every citing table** (the third addendum): `doi` is added to
`pharm_variants.csv`, the binning kinds, `gwas_effects.csv` (derived), `meta.csv` and
`model_organisms.csv`, and the roster is read from `_CITING_TABLE_KINDS`, asserted by an equality over it,
never listed by hand. Tests: the RM336 reproduction (`10.1101/2025.03.01.640000` → refused), `NONE` with
and without `doi` on every citing kind, and the literature pass's lookup list for a DOI cell. Lane A runs
A2 before A5 and A6, which lean on it.

**A3. RM322, `DiplotypeRow` gains `negatives` and `category`.** The three touch points (model, compile,
`reverse`) and the diplotype parquet. Both are free text, as on `VariantRow` (which binds no vocabulary to
`category`). Round-trip test over a diplotype module carrying both.

**A4. RM334, the HLA nomenclature grammar on `allele_function.csv`** (§3 item 22). Gated on A2's
published-module scan, extended to HLA rows. Tests: `*15:01`, `*57:01:01`, `*02:01:01:02N` pass;
`15:01`, `*1501`, `*15:01X` refuse with a message naming the expected shape.

**A5. The `StudyRow` batch** (wave 2, one builder, one commit per item): RM325 (`sample_size`,
`sample_unit`, `n_cases`), RM326 (`phenotype_class` and its warning code), RM328 (`ancestry`), RM329
(`age_min`, `age_max`, `age_of`), RM330's study half (`stratum`, `stratum_level`), RM331's author half
(`proxy_rsid`; `_check_study_effect_alleles` checks `effect_allele` against the proxy's alleles when it is
stated, and the enricher resolves proxy rsIDs as resolution subjects so those alleles exist), RM332
(`effect_unit`, and its join onto `weights.parquet`, §3 item 17), and the locus-level derived columns
(`eur_only_evidence` and the outcome strip, §3 item 10). Then the duplicate-citation narrowing
(§3 item 16), with one test per narrowing column showing a pair that warned before and does not now, and
one showing an unstated column still warns. Each column: the P5 audit line in the commit message, the
three touch points, `studies.parquet`, and `reverse`.

**A6. RM335, the model-organism table** (`model_organisms.csv`, parquet `model_organisms.parquet`). Columns:
`gene` (required, the human symbol), `orthologue`, `species`, `model_type`, `sex`, `diet`,
`lifespan_effect`, `concordance` (§3 item 23), `pmid`, `doi`. Key: every column except `lifespan_effect`
and `concordance`. A `_TABLE_KINDS` entry, a `_TABLE_DUPE_KEYS` entry, `reference.py`'s model map, the
authoring reference, TABLES.md's hand-written section. It never reaches an effect column or a tier.

**A7. RM337, the warning for a file under `logs/` that does not ship.** After the sync that carries RM338's
patch from `main`. New code `log_file_not_shipped`, one finding per file, naming it and the reason: not a
recognized extension, or failed its content check (RM338's reasons). Both modes, never a refusal.

**A8. RM253, the CPIC drafter's notation.** Repeat alleles spelled as callers spell them (the RM253
decision line: `*28` = `C>CAT` at GRCh38 `2:233760233`), `DEL<bases>` / `INS<bases>` spelled VCF-anchored
with the anchor read from the reference the enricher already reads, the bare `DEL` still skipped, and DPYD
names as CPIC writes them with spaces dropped and `&` for the comma. No row keyed on `rs3064744` alone.
Test against the provisioned CPIC snapshot: `draft_gene("UGT1A1")` defines `*28`, `*36`, `*37`, and the
"used but not defined" warning no longer fires for them.

### Lane B: the meta-table

**B1. RM28 / RM323 / RM324 / RM327 / RM330's `sex`, one item.** The table as §3 items 1–9 fix it, plus
`module_spec.tier_scale`. The work, in order:

1. The model (`MetaRow`, on `AuthoredModel`) with the selector parser, its refusals (an unknown table, an
   unknown column, a forbidden character, an empty row, `trait_role` without a trait, `tier` without a
   scale), and the bounds the maintainer set (no negation, OR, ranges, cross-table joins, or selectors over
   `studies.csv`; each refused with its own message, not the generic one).
2. Expansion at compile: each member against its table's rows, list columns meaning "contains". A member
   matching nothing is the warning `meta_selector_matches_nothing`; the manifest records every selector's
   match count. Precedence and withholding (§3 item 8).
3. The two parquets, `tier_scale` in the manifest and `REVERSE_RECONSTRUCTED`, `reverse` (selectors
   verbatim), and the round trip.
4. The study-orphan widening (`_cross_validate_studies`), **in wave 3, after the `StudyRow` batch has
   merged**: a study variant is not an orphan when it is a `variants.csv` row, a defining variant in
   `haplotypes.csv`, or the `variant_key` of a meta member. APOE's 14 links are the test.
5. The rsID-merge check (NCBI, enrichment) runs over meta members' variant keys too, so IL6R's rs8192284
   under two keys is caught.

Tests first: the duplicate set (`A & B` against `B & A`); the ε2/ε4 nesting case (two incomparable allele
rows disagree → withheld, and a diplotype row settles it); a combination replacing what it names;
`variants[flags=legacy_longevitymap]` against a more specific locus row; CPIC's TPMT × NUDT15 written as one
phenotype-pair row; a selector matching nothing. Each against the real compile path.

**B2. The derived columns**: `tradeoff` (§3 item 9) and the resolved facts' `withheld` list, with the
Kleene truth table as a parametrized test.

### Lane C: indel placement

**C1. RM304, the VRS version.** The pin and the per-row column (§3 item 20), the minting call recording its
version, the enricher's VRS verify pass reporting `vrs_version_differs`. The pinned insertion test (`rs72613567` →
`ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7`) behind `JUST_DNA_NETWORK_TESTS=1`. The `ga4gh.vrs<2.4` cap
stays until vrs-python releases the `rle_subunit_mode` keyword; lifting it is the liaison's call, and when
it is lifted our call passes the mode explicitly.

**C2. RM292, every check names its witness.** `VerificationRecord` gains the source a check reads and the
source it checks against, and a verdict member `self_consistent` used when they are the same. The check
registry carries both as fields, and an equality test over the roster refuses a check that states neither.
A tolerance that makes a class undecided publishes the count of that class.

**C3. RM305, the ClinVar-GKM lane.** Through CACHE_SURFACE.md's checklist, every line with its test. Indels
only (the ~270k `ReferenceLengthExpression` alleles and other indels). A pinned release recorded through
RM303's model; the Google Cloud Storage download owes the client exception contract; a currency finding
when the latest weekly delta is old. It is a witness RM292's records name, with no check of its own.

**C4. RM267, two authorities compared.** For each rsID two loaded authorities place, compare by minted
`vrs_id` (no tolerance), else by `parsimony_reduce` over a reference window. A disagreement is a finding
naming both placements, and the row is withheld (§4 question 3). The count of rsIDs with one witness is
published beside it. A new optional `resolution.csv` column records the witness asked and its answer,
tri-state. Tests: `rs8176719` (two ids, withheld), `rs72613567` (one id, written).

**C5. RM270, the spelling-independent key reaches the artifact.** The enricher left-normalizes the
coordinates it fills; for an authored coordinate it reports the normalized spelling as a finding and never
rewrites the cell. The per-ALT `vrs_id` (with C1's version) goes onto the variant parquets. The stamped
verdict (left-aligned / not / unknown) is a `resolution.csv` column. Remove the SHOX pin from
`compiler/tests/test_consumer_join.py`; the test then passes with an empty miss set, which is the proof.

### Lane D: derived inputs

**D1. RM303, the snapshot layout in `just_dna_format.snapshot`.** As the item's split says, with §3 item
21's choices, the Goals amendment (rule in CONSTITUTION, why in CONSTITUTION_AMENDMENTS_HISTORY) in the same
commit, and an AST walk over `*_build.py` refusing a hand-built `release.json`. ClinVar's per-lane label
exception (`clinvar_dataset_label`) is removed once its builder writes `dataset` through the model.

**D2. RM333's Open Targets lane, and what it carries** (under §4 question 2's default). First, by hand: read
one row of each of `l2g_prediction`, `credible_set`, `colocalisation` and `variant` from release 26.09,
record their sizes and fields in `docs/probes/`, and only then build. The lane writes:
- an effector-gene derived table at Open Targets' own grain, one row per (study locus, gene) with the
  study locus's lead `variant_key`, the L2G score and the release, and a sibling grain for coloc
  evidence as the probe finds it published. No row is collapsed to one per variant: several study loci
  per variant are kept and counted, never resolved to a winner (`@multiplicity-is-a-finding`). The
  probe's field list decides the exact columns, which go back to the pm before the build fixes them;
- RM239's two columns on `gwas_effects.csv`, the posterior and the credible-set level, with the item's
  withhold for a study with no credible set (a nobody-asked third state, not a zero);
- RM236's per-transcript consequence sidecar keyed `(variant_key, transcript)`, so RM23 inherits the grain
  when it is built (it stays in 0.9).
The `SourceRow` states Open Targets' terms with `notice` carrying its disclaimer verbatim (RM333's decision).
The eight hand-curated causal/effector inputs go in `overrides.csv` as corrections; nothing authored names a
C or E label.

**D3. RM331's computed LD pair.** After A5. For each study row with `proxy_rsid`, the enricher asks the LD
reference (§4 question 4) for r² between proxy and lead in the study's one `ancestry` code (a
mixed-ancestry study gets its row with r² withheld, the pm's setting; the audit's second run counts 3 such
links), and writes a
machine-written `ld_pairs.csv` keyed `(proxy_rsid, variant_key, ancestry)` with r², the reference and its
release. A study with no ancestry gets no row and is counted (unknown is not zero). First step: one hand-run
call, recorded.

## 6. Reference examples

The audit's thirteen candidates fold into six examples, each with a README naming what it exercises and
what it broke while being built (`@probe-becomes-example`). Each is the real check for its lane: it compiles
under `--strict`, reverses, and recompiles to the same digest.

| Example | Audit candidates | Lane |
|---|---|---|
| `apoe_klvs_meta` | 1 (facts-only row), 2 (allele facts, the ε2/ε4 nesting), 3 (KL-VS × ε4), and the legacy tag selector | B |
| `pleiotropy_tradeoff` | 4 (per-trait rows, `tradeoff`, the no-allele loci) | B |
| `cpic_gene_pairs` | none (the second addendum's case): TPMT × NUDT15 as phenotype-pair rows | B |
| `longevity_studies` | 5, 6, 7, 8, 9, 11, 13 (the `StudyRow` columns, the narrowing, the sentinel) | A |
| `hla_alleles` | 10 (HLA members, `sex`) | A + B |
| `model_organisms` | 12 | A |

## 7. The shared rules every builder follows

- **The contract before the code, a failing test first.** Each test is shown failing on the branch before
  the fix, and the commit message says so.
- **Each new column**: the P5 audit (collisions, the reserved namespace, likely future names) in the commit
  message; the three touch points plus the parquet; `reverse`; a round-trip test (P7).
- **Each new warning code**: a `features/` scenario (the corpus gate stays on although RM149 is frozen) and
  a line in `docs/INTEGRATION_0_8.md`, since an older reader refuses an unknown code. The codes this plan
  names: `phenotype_class_unrecognized`, `meta_selector_matches_nothing`, `meta_member_allele_ambiguous`,
  `log_file_not_shipped`. Any other
  a builder adds is listed in its report.
- **Each new check is broken on purpose** (mutate the condition, watch the test go red) before it lands.
- **Real paths, real data**: the compile and reverse paths, the provisioned snapshots, expected values
  computed at run time. No mocking of a transformation.
- **An item that calls an outside service** (D2, D3, C3) is marked building only once its first hand-run
  call and what it returned are recorded.
- **Commit as one block**: the behaviour, its test, its doc line, its CHANGELOG line. `uv run ruff format`
  on the changed Python files first.
- **Forbidden**: building around a decided column that turns out to have no case (send it to the pm);
  network in the format or compiler tiers; a refusal on data a published module already holds without the
  scan A2 describes; a count stated in prose that a test cannot re-derive.

## 8. Release gates

The cut waits for all of these, checked at the cut commit, never read off this list:

- both charter amendments landed (P4 with A1, Goals with D1), each with its history entry;
- the polars 2 lock and its RELEASE_RECORDS line;
- `docs/INTEGRATION_0_8.md` covering every new warning code, manifest field (`toolchain`, `vrs_version`,
  `tier_scale`, the selector match counts), parquet and reason;
- RM270's `test_consumer_join` pin removed and green;
- the six reference examples compiling, reversing and recompiling to the same digest;
- the review wave and the dogfooding wave come back clean (RELEASE_CYCLE § Minors steps 5–6), with
  longevitymap v2 itself as the dogfood.
