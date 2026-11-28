# Roadmap — 0.11 and later minors

**What this file is.** The open minors' scope: what 0.11 builds, and the methylation minor, undated. Each item states
why it is here. The file is named for the release that will decide its contents, as
[ROADMAP_0_10.md](history/ROADMAP_0_10.md) was; the 0.11 cut moves it to `docs/history/` and opens the next one with
what is left. Opened at the 0.10.0 cut (2026-11-28) from ROADMAP_0_10.md's open items and everything after them, plus
the known issues 0.10's two review rounds placed in 0.11.

| Minor | Theme | Items |
|---|---|---|
| **0.11** | an **odd** minor (fixes and decided work, RELEASE_CYCLE.md § Tic/tac), started at 10–20 decided items | RM469; RM459 once the registry reads `KEY_COMPARES`; 0.10's known issues RM472–RM482 |
| **methylation** | after 0.10, undated until the PacBio samples are in hand | RM317–RM319, RM433, RM56, RM65, RM66 |

Everything here is **additive under Principles 3/4/8**; an item waiting on a version belongs in
[ROADMAP_1_0.md](ROADMAP_1_0.md). The 0.10 minor's own record (its scope, the preview and both review rounds'
placements) is the closed [history/ROADMAP_0_10.md](history/ROADMAP_0_10.md).

**Three of these are not work at all.** RM84's own half shipped in the 0.6 PT2 batch, and only the consumer's
discovery half is open. RM67 is a documented divergence, numbered so it stays findable and does not get re-probed. The
Gherkin corpus (RM149) is **frozen**; its entry says why. All three stay here, so that a reader meets the reasoning
instead of re-deriving it.

Indexed in [RM_TOC.md](RM_TOC.md), which is the complete list and the place to look an item up.

---

# 0.11's scope — fixes and decided work

RM469 (decided fix work, built and held on `build/011-rm469`), RM459 (waits on the registry's S36), and the known
issues 0.10 ships with, each placed in 0.11 by the pm on 2026-11-28 and filed at the cut: RM472 to RM477 and RM479 to
RM481 from the two review rounds' known-issue lists, RM478 (R4's second half) and RM482 (single 4's wider walk). The
table above is the list to count from; the pm sizes the minor and says when it starts.

## RM469 — the pinned-text walk sees only the texts 0.9 added, so a new text in a module older than 0.9 is held by nothing

**Severity** low · **Status** open — **a minor, 0.11** (the pm, 2026-11-27: decided fix work, so the next odd minor under the tic/tac rule; it may be built early on a branch held for 0.11; from RM461's build) · **Owner** enricher
(`test_every_new_text_is_pinned.py`, the emitted texts) · **Motivating case** RM461's fourth point, which its build in
0.9 did not reach · *related* RM461, RM430

**What was seen.** RM461 carried the proxy's `release_unreadable`, split a request on its longest column and made
`lane_status` refuse a URL, but its fourth point was not built: the walk over every module needs a registry of the
texts already emitted, and the build counted 387 such texts in 64 modules that no list names. Without one, the walk
holds only the fragments 0.9's diff added, so a warning text added later to an older module is pinned by nothing.

**What it would be.** A registry of every emitted warning and refusal text, each with the fragment a consumer may
grep (`@warning-text-is-api`), and the walk over every module held to it by set equality, so a new text with no
entry fails the suite. Filling it is the bulk of the work; the walk is small once the registry exists.

**Residuals** none yet.

## RM459 — with the registry's proxy set and Hugging Face off, a gene lookup on clinpgx, cpic, drug_labels or civic answers could-not-ask

**Severity** low · **Status** open — **a minor, 0.11; waits on the registry** (its S36; moved from 0.10 by the pm, 2026-11-27, under the tic/tac rule) · **Owner** enricher
(`remote.RemoteLane.proxy_compares`, `key_compare.KEY_COMPARES`) · **Motivating case** the RM430 follow-up's readings,
placed by the pm on 2026-11-18 as a 0.9 known issue, filed at the 0.9.0 cut · *related* RM430, RM454

**What 0.9 ships.** The registry's proxy compares a parquet cell exactly. The local readers of four lanes fold a gene
to its `gene_key` and, on clinpgx and drug_labels, split a `;`-joined cell into members, so the proxy would answer a
gene lookup short (399 of 16,117 ClinPGx rows and 361 of 1,433 drug labels sit in joined cells). The holder therefore
passes the proxy over for a key column whose compare folds or splits (`RemoteLane.proxy_compares`) and asks Hugging
Face (`route` says `hf`). With `RemoteSnapshots(huggingface=False)` and a proxy set, those four lanes answer a gene
lookup as could-not-ask (`SnapshotRouteUnavailable`, the reason naming the compare), pinned by a test. Lookups by
rsID or position are not affected: their keys are normalized before the query and stored in that form.

**The fix is the registry's first.** The registry decided (its S36, 2026-11-18) to read
`just_dna_enricher.key_compare.KEY_COMPARES` from its release that floors 0.9 and to fold and split as the local
readers do. Once it does, the holder may send those keys to the proxy again. That needs a way to tell a folding proxy
from an exact one (a field in the lane reply, or a registry version), which is this item's design question, and
`KEY_COMPARES` stays stable meanwhile: it is now read outside this repository.

**Residuals** none yet.

## RM472 — the answer store keeps an anchored indel's raw REST record, so a replay with no sequence service withholds what the live run anchored

**Severity** low · **Status** open — **a minor, 0.11** (a known issue of 0.10, review round 1's single 1, placed by the pm
2026-11-28; filed at the 0.10.0 cut) · **Owner** enricher (`ensembl`, `answer_store`) · **Motivating case** 0.10
review round 1 (Argon; read at `ensembl.py:302-320`) · *related* RM468, RM385

**What was seen.** RM468's store keeps the Ensembl REST record as the source answered it. For an indel the live run
then anchors that record against the reference (the padding base REST leaves out). A replay from the store with no
sequence service configured has the raw record and no base to anchor it with, so the subject answers could-not-ask
where the live run answered. It is a withhold, never a wrong answer, and the host that asked for the store reads a
local FASTA (RM385), so the case needs a store shared with a host that has none.

**What it would be.** Store the anchored answer beside the raw one, or record that the replay needs a sequence read and
say so in the could-not-ask reason. Either keeps the store's promise that a replay answers what the live run answered.

**Residuals** none yet.

## RM473 — a corrupt IPD-IMGT/HLA snapshot reads as present, so status, pull and prepare report a lane enrich then cannot read

**Severity** low · **Status** open — **a minor, 0.11** (a known issue of 0.10, review round 1's single 5, placed by the
pm 2026-11-28; filed at the 0.10.0 cut) · **Owner** enricher (`locations.resolve_ipd_imgt_hla_reference`,
`ipd_imgt_hla_build.load_lists`) · **Motivating case** 0.10 review round 1 (Sol; read at `locations.py:1240-1255`) ·
*related* RM350

**What was seen.** RM350's resolver answers present when the snapshot's files exist. A truncated `Allelelist.txt`, or
a `release.json` describing other bytes, still reads present in `cache status`, `pull` and `prepare`; `enrich` then
withholds the HLA check with a reason about the module rather than the snapshot.

**What it would be.** Judge the lane by its payload, as `@a-derived-lane-has-parents-and-an-absent-parent-is-not-an-empty-result`
asks of every lane: the files' digests against `release.json`'s `source_sha256`, and a reason that names the snapshot.

**Residuals** none yet.

## RM474 — the genotype-mismatch check reads `conclusion` only, so a register that names the wrong genotype goes unchecked

**Severity** low · **Status** open — **a minor, 0.11** (a known issue of 0.10, review round 1's single 8, placed by the
pm 2026-11-28; filed at the 0.10.0 cut) · **Owner** compiler (`conclusion.py`, the genotype-mismatch check) ·
**Motivating case** 0.10 review round 1 (Argon; read at `conclusion.py:77`) · *related* RM302

**What was seen.** RM302 added `conclusion_lay` and `conclusion_concise` beside `conclusion`. The check that warns when
a conclusion names a genotype other than its row's reads `conclusion` alone, so the same slip in either register
passes. A register is the author's own wording of the same claim, so the check owes it the same reading.

**What it would be.** Run the check over every stated register, and name the register in the warning. Pin the
phrase (`@warning-text-is-api`).

**Residuals** none yet.

## RM475 — the HLA name check reads `allele_function.csv` only, while diplotype and haplotype names carry HLA names too

**Severity** low · **Status** open — **a minor, 0.11** (decided by the pm 2026-11-28: review round 1's C4, split; 0.10's
record names the tables it read, the widening is 0.11's; filed at the 0.10.0 cut) · **Owner** enricher
(`ipd_imgt_hla.authored_names`) · **Motivating case** 0.10 review round 1, C4 (Opus, Sol; read) · *related* RM350,
RM351

**What was seen.** RM350 checks HLA allele names against IPD-IMGT/HLA's lists where RM334's grammar applies, which is
`allele_function.csv`. `diplotypes.csv` and `haplotypes.csv` carry HLA names too (RM351 exempts them from the
definition check), and the assignment check never reads them. Since round 1's fix the record says which tables were
read, so the narrower answer is stated, not hidden.

**What it would be.** Derive the roster from every column an HLA gene or the HLA grammar can reach
(`@roster-is-as-wide-as-the-tables-it-reads`), and publish the wider list of tables read.

**Residuals** none yet.

## RM476 — three locks new in 0.10 are held across I/O, and one busy SQLite answer turns the answer store off for the run

**Severity** low · **Status** open — **a minor, 0.11** (a known issue of 0.10, review round 2's R1, placed by the pm
2026-11-28; filed at the 0.10.0 cut) · **Owner** enricher (`answer_store`, `fasta`, `sequences`) · **Motivating case**
0.10 review round 2, R1 (three of three runs; read) · *related* RM468, RM385

**What was seen.** `AnswerStore._access` holds its lock over the SQLite connect, a 15 s busy timeout and the
operation, and one `SQLITE_BUSY` sets `_failed` for the store's life; `AnswerRun.release` runs the HTTP release probe
under the run lock (RM468). `FastaReference._identity` hashes a whole contig and writes its cache under a shared lock,
and `SequenceProxy.proxy()` builds the reference and calls `current()` under the proxy lock on every read, where its
docstring says threads wait only for a dict (RM385). The repository's own rule is `@shared-pacing-gate`: lock the
bookkeeping, not the work. The cost is latency and a store disabled by one busy answer, never a wrong answer.

**What it would be.** Per-key once-cells for the identity and the release probe, a retry before `_failed`, and an AST
walk refusing I/O inside a `with lock:` block.

**Residuals** none yet.

## RM477 — `layout.atomic_writer` writes every sidecar 0600, so a second account cannot read what the first wrote

**Severity** low · **Status** open — **a minor, 0.11** (a known issue of 0.10, review round 2's R2, placed by the pm
2026-11-28: fixed at the writer, the class; filed at the 0.10.0 cut) · **Owner** format (`layout.atomic_writer`) ·
**Motivating case** 0.10 review round 2, R2 (two of three runs; ran) · *related* RM385

**What was seen.** Round 1's C7 made `fasta index` write the `.fai` with the mode of the file it replaces. The
`.refget.json` identity cache beside a FASTA goes through `layout.atomic_writer`, which stages in a 0600 temporary
file and renames it into place, so a second account on the host cannot read the cache, re-hashes the whole reference
(about 155 s on GRCh38) and replaces it with a 0600 copy of its own. The writer is older than 0.10 and every sidecar
it writes is 0600.

**What it would be.** The writer takes the mode of the file it replaces, or the process umask for a new one, for every
caller at once. A test reads the mode back for each writer.

**Residuals** none yet.

## RM478 — the tag tests skip when the clone has no tags, and nothing turns that skip into a failure in CI

**Severity** low · **Status** open — **a minor, 0.11** (review round 2's R4, second half, placed by the pm 2026-11-28;
filed at the 0.10.0 cut) · **Owner** the suite (`conftest.release_tags`) and `.github/workflows/ci.yml` ·
**Motivating case** 0.10 review round 2, R4 (two of three runs; read) · *related* RM441, RM399, RM435

**What was seen.** `release_tags` answers `[]` on a shallow clone, and the tests built on it skip: the old-reader
breaks test, the public-name walk, the tag half of `test_derivation_records` (RM399, RM441), the v0.9.0 half of
`test_study_effect_direction` (RM435) and `test_first_seen`. 0.10 made CI check out with `fetch-depth: 0` and tags, so
they run there now, but a checkout that loses the tags again would turn them back into skips with a green run.

**What it would be.** An environment flag CI sets, under which an empty tag list fails instead of skipping.

**Residuals** none yet.

## RM479 — a FASTA removed in the middle of a run raises `FileNotFoundError` where the read should withhold

**Severity** low · **Status** open — **a minor, 0.11** (a known issue of 0.10, review round 2's R5, placed by the pm
2026-11-28; filed at the 0.10.0 cut) · **Owner** enricher (`sequences.SequenceProxy`, `fasta`) · **Motivating case**
0.10 review round 2, R5 (two of three runs; ran) · *related* RM385

**What was seen.** Once the local FASTA is unlinked mid-run, `subsequence` raises from `proxy()` → `current()` →
`stat`, outside the try that turns a failed read into could-not-ask (`sequences.py:172`). The entry points are enrich,
CIViC and CPIC drafting and Ensembl anchoring. Round 1's single 9 (a bad URI's documented `ValueError`) is a
different trigger.

**What it would be.** An `OSError` from the reference's `stat` or read is a could-not-ask for that read, with a reason
naming the file, as an outage of a remote sequence service already is.

**Residuals** none yet.

## RM480 — the FASTA identity cache is keyed on size and mtime only, so an edited base under a restored mtime reads as bound

**Severity** low · **Status** open — **a minor, 0.11** (a known issue of 0.10, review round 2's R6, placed by the pm
2026-11-28; filed at the 0.10.0 cut) · **Owner** enricher (`fasta.FastaReference._identity`) · **Motivating case**
0.10 review round 2, R6 (two of three runs; ran) · *related* RM385

**What was seen.** RM385 caches each contig's refget digest in `.refget.json`, keyed on the file's `(size,
mtime_ns)`. A base overwritten in place with the mtime restored leaves the key unchanged, and a fresh reader still says
`bound` and serves the edited base. RM385's entry and ENRICHER.md state the key, not this consequence. Design-level:
it needs a deliberate edit to reach.

**What it would be.** Add `st_ctime_ns` and `st_ino` to the key, which an in-place edit moves, and say in ENRICHER.md
what the cache does and does not notice.

**Residuals** none yet.

## RM481 — one mirrored site gets two contradictory sentences, "is not filled" and "so both are filled as before"

**Severity** low · **Status** open — **a minor, 0.11** (a known issue of 0.10, review round 2's single 2, placed by the
pm 2026-11-28; older than 0.10; filed at the 0.10.0 cut) · **Owner** compiler (`resolution`, the mirrored-site
settlement) · **Motivating case** 0.10 review round 2 (Grok; ran on `11:108256251:CT:C`) · *related* RM460, RM449

**What was seen.** The mirrored-site settlement is recorded before the claimed-row filter (`resolution.py:206-213`
against `:221-243`), so a module can get both "is not filled on 11:108256251:CT:C" and "so both are filled as
before" for one site, counted twice. RM460 moved both sentences onto `rsid_genotype_reads_as_two_events`, so the
contradiction now sits under one code; it is older than 0.10.

**What it would be.** Settle after the filter, one sentence per site, and a test asserting that no site is named by
two sentences of that code.

**Residuals** none yet.

## RM482 — the public-name walk sees classes and functions, so a new constant or type alias ships undocumented

**Severity** low · **Status** open — **a minor, 0.11** (review round 2's single 4, placed by the pm 2026-11-28; filed at
the 0.10.0 cut) · **Owner** the suite (round 1's C6 walk over new public names since the tag) · **Motivating case**
0.10 review round 2 (Sol; read) · *related* RM385, RM468, RM294, RM460

**What was seen.** Round 1's C6 added a walk refusing a new public class or function with no docstring or reference
line. It does not see module-level constants or type aliases, and five shipped in 0.10 that way: `FASTA_SCHEME` and
`VALID_FASTA_CONTIG_STATUS` (RM385), `StoreSetting` (RM468), `REPEAT_GRADE_FACT_FIELDS` (RM294) and
`ALL_SPELLINGS_CLAIMED_CODE` (RM460). The 0.10.0 cut documents those five by hand.

**What it would be.** Widen the walk to every new public module-level name, so the next one fails the suite.

**Residuals** none yet.

# After 0.10: the methylation minor, undated

Its own minor, after 0.10, undated until the PacBio samples are reported in hand ([desk #329](https://github.com/winternewt/desk/issues/329), its default). RM317–RM319, RM433, and the PacBio zone's RM56, RM65 and RM66. The sections below also keep the three items that are not work (RM67, RM84's consumer half, RM149).

## RM317 — FMR1 repeat methylation is in every PacBio TRGT VCF as `FORMAT/AM`, and no module can bin it on a two-allele record

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (a `measure_kind` member, the element-rule vocabulary, the host table) + compiler · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO §§ 1.1, 3, 4.1](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM433, RM66, RM65, RM164

**What is real.** TRGT, PacBio's tandem-repeat genotyper and part of the HiFi WGS pipeline since at
least v2.1.0, writes `##FORMAT=<ID=AM,Number=.,Type=Float,Description="Mean methylation level per
allele">`: the mean 5mC level over the CpGs **inside the repeat tract**, one value per called allele.
Open samples exist: NA09237 (male full mutation) is `GT=1`, `MC=898`, `AM=0.85`, reproduced with TRGT
5.1.0, and HG002 (normal male) is `AM=0.1`. `source_field: FORMAT/AM` already passes the pointer
grammar. `fmr1_cgg_repeat` asserts in prose that a full mutation "is methylated and silenced", and this
is the field that can check it.

**What a module cannot do today.**

- **Select the right allele.** HM06968 (female) is `MC=33,112`, `AM=0.90,0.07`: the expanded allele
  is the *unmethylated* one. NA06905 goes the other way. The band means "the methylation of the
  expanded allele", i.e. the `AM` at the index where `MC` is largest. Every element rule picks by the
  field's own values, so none can say it.
- **Name the quantity.** No `measure_kind` is a methylation fraction. `allele_fraction` would put two
  quantities under one name (P5). `repeat_alleles.csv` pins `measure_kind=repeat_count`.
- **Name the absence.** `AM=.` means either no CpG in the span or no MM/ML tags in the BAM, and the
  file cannot tell them apart.

**Scale trap.** TRGT 0.5.0 wrote `AM` as an Integer (values up to 185; probably the 0–255 byte,
unverified). From 0.7.0 it is a Float on `[0, 1]`, and the changelog is silent about the change.

**To design (the 0.8 interview).** The kind's name, audited under P5, and whether the modification
(5mC) is its own axis. Whether `repeat_alleles.csv` hosts a second kind or a sibling table does. How a
cross-field selection is stated without hard-coding TRGT's `MC` into a vocabulary: the probe prices an
optional pointer column naming the selecting field at full cost. And **the band values**: none is
cited yet. The probe quotes sample observations, not boundaries, and a row needs a paper behind it
(`@rm47-bin-cites`).

**Legality and price.** Everything is additive, so it is minor-legal (P3, P6, P8). A kind member is
cheap but a one-way door (P5). The selector column is full cost.

## RM318 — imprinting-region methylation is real in PacBio outputs, but lives in BED and TSV files that no pointer can name

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (a new optional region table kind, a non-VCF pointer) + compiler · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO §§ 1.2–1.4, 3, 4.2](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM433, RM66, RM65, RM164

**What is real.** HG002 shows allele-specific methylation at two imprinted regions in public PacBio
pipeline outputs, and MethBat 1.1.0 run on them reports `PASS`:
SNURF:TSS-DMR (15q11–13) hap1 80.1 / hap2 14.6, and KCNQ1OT1:TSS-DMR (11p15 IC2) hap1 15.3 / hap2 86.4,
with pooled values near 49. The consumer holds per-CpG `5mC.bed.gz` (MethBat 1.x) or
`cpg_pileup.*.bed.gz` (pb-CpG-tools 3.x), plus a `profile.tsv`. None of it is in a VCF, and no PacBio
tool writes VCF 4.5 `M5mC`.

**What a row would need.** Every item comes from the probe's measurements:

- a region (chrom, start, end, build), with no `variant_key`;
- a pointer to a BED or TSV column, which `source_field` (a VCF pointer) cannot be widened to without
  overloading it (P5);
- the aggregation from sites to region;
- a row selector (`Total`, or a statement about both haplotypes);
- the unit and the modification;
- a coverage floor, because a missing row is never "unmethylated";
- bands: pooled around 20% and 80%, plus a haplotype-delta band.

**Traps the data showed.**

- **Haplotype labels are not parental.** The same sample has hap1 methylated at SNURF and hap2 at
  KCNQ1OT1, so no band can say "the maternal allele".
- **The scale moved at MethBat 1.0.0** (fractions to percent) under unchanged column names.
- **pb-CpG-tools `model` and `count` modes disagree** (hap2 4.1% vs 16.1% at one CpG). The mode is a
  header line, not a column.
- **The pipeline runs `methbat profile` over CpG islands, never `methbat report`**, so a user holds
  island numbers, not the imprinted regions.
- **H19 had no haplotype rows at all.**

**Not decided, and not to be built on thin air.** The 20%/80% cut-offs are MethBat's defaults, not a
guideline. No clinical source was read. MethBat ships 15 imprinted regions from Mackay et al. 2022
(Table 2), which is the corpus a design would start from.

**Legality and price.** A new optional table kind is minor-legal (P3). Its price is full, and it is the
largest addition in the methylation work. The probe prices a separate pointer column over widening
`source_field`.

## RM319 — PacBio's TRGT carries the repeat count as `FORMAT/MC`, a per-motif String, so `repeat_alleles.csv`'s count half does not reach a PacBio user

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (the consumer contract, possibly the element-rule vocabulary) + the corpus · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO § 4.1, last paragraph](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM433, RM66, RM65, RM164

**What was found.** No PacBio file opened in the probe carries `REPCN`, the ExpansionHunter key that
`fmr1_cgg_repeat` (and the corpus's other repeat examples) point at. TRGT writes the count as `MC`,
`Type=String`, per allele, with `_`-joined per-motif counts inside each allele (`18_8,25_8` at HTT
under TRGT 5.x). A PacBio consumer therefore cannot follow the module's `source_field` at all. An
author who writes `FORMAT/REPCN|FORMAT/MC` hands the consumer a motif-segmented string that no element
rule defines a reading of.

**Why it matters now.** A beneficiary of this work is about to hold PacBio samples, and TRGT is the
repeat caller in PacBio's pipeline. Every `repeat_alleles.csv` module is invisible to them today.

**To decide.**

- Whether this is a consumer-contract rule ("sum the motifs", or "the motif the row's `repeat_unit`
  names") or a vocabulary addition. The second is a minor.
- How it meets RM66, one repeat locus with several motifs: TRGT's per-motif segments are exactly RM66's
  shape.
- Whether the reference examples gain the TRGT alternation.

Measure against the PureTarget VCFs first. The probe lists them, with FMR1, HTT and more.

**Legality.** A contract sentence alone is a patch. A new element rule or pointer shape is a minor. It
is filed against 0.8 because the RM66 overlap wants one decision.

---

# The VCF 4.4 items deferred out of 0.6

Numbered and triaged on 2026-08-13 from [VCF_4_4_AUDIT.md](probes/VCF_4_4_AUDIT.md); the rest of that cluster
(RM53, RM54, RM56–RM64, and RM65's comment fix) went into 0.6 — see
[PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md). The audit remains the evidence document: spec quotations,
`file:line` references and probe transcripts live there and are not duplicated.

## RM433 — AlphaGenome 2's live model service is unused: the only surface that scores an indel

**Severity** low · **Status** open — **a minor, 0.9** (with the methylation zone, RM317 to RM319) · **Owner** enricher (a new client beside
`alphagenome_check`) · **Motivating case** the maintainer's ask through the lead, 2026-11-12 ("yes (to pm)"), after
upstream's v2.0.0 · *related* RM317, RM318, RM319, RM191, RM192, RM193, RM345

**What changed upstream.** AlphaGenome v2.0.0 (2026-11-11) adds `DnaModelServiceV2` (package `v2main`), a
live-prediction service: `PredictVariant`, `ScoreVariant`, `ScoreInterval`, `ScoreIsmVariant`, expression
conditioned on a reference or a single-cell profile, `EncodeCells` embeddings and input gradients. Nothing of ours
uses it. Our Atlas client reads the precomputed `v1main` scores, its three proto files are byte-identical at v2.0.0 to
our pin, and a live `GetDenseVariantScores` on rs4149056 answered on 2026-11-12 (the lead). So nothing breaks and no
patch is owed. The pin-bump trap (at v2.0.0 `protos/dna_model.proto` is a shim importing `protos/v1/dna_model.proto`)
is the liaison's.

**What adopting it would buy.** The Atlas probe's surface table (`docs/probes/ALPHAGENOME_ATLAS.md` § 6.4) has the
model API as the only one of three surfaces that scores an **indel**: the bulk files carry none and the Atlas API
answers `UNIMPLEMENTED`. That was already true of the v1 model service, which we never adopted either, so v2 is not
what opens it. What v2 adds over v1 (read from its protos at the `v2.0.0` tag, 2026-11-12): a **methylation** output
(per-CpG probabilities) with a variant scorer over a window around the variant, the one addition that meets a named
0.9 zone (methylation, RM317 to RM319); single-cell expression and ATAC outputs; conditioning on a single-cell
profile; cell embeddings; and input gradients. PRO-cap is gone. Single-cell outputs, embeddings and gradients have no
table a module could put them in. The terms are the v1 model service's: non-commercial, no training of other models,
not for clinical decisions; commercial use only through Google Cloud. Live predictions get a lower query rate than
Atlas lookups and are meant for small analyses.

**What it costs.** A new client on a different gRPC service with new message types; a decision on what is stored (a
column on an existing derived table, or a lane of its own); and the service's terms, quota and licence. The Atlas
probe's § 2 is the precedent: the artifacts there turned out not to be one licence, and § 7 left the daily quota
unmeasured. A computed prediction is per request, never offline and never reproducible (§ 6.4), so it sits beside
the house rule that a check over a source records what it read.

**Sizing (pm, 2026-11-12, then the maintainer the same day): 0.9, tied to the methylation zone.** First parked,
since no named zone held it. The maintainer then tied it to RM317 to RM319 ("tie the v2 to them"), so it joins the
methylation zone. The tie is complementary, not overlapping. RM317 to RM319 are the **measured** half: a consumer's
PacBio files hold the sample's own methylation, and the module points at it and bins it. v2's methylation scorer is a
**predicted** half: per variant, how the alternate allele shifts methylation at the CpGs near it. That is an annotation
in this format's sense (no sample data), so a module could carry it and a consumer could read it beside their measured
values.

Built in this order, each step allowed to stop the next:

1. **A terms probe** of the model service, in the shape of the Atlas probe's § 2: what the output may be used for,
   stored as and published as. If its output may not be stored in a module, the item shrinks to a live check and the
   methylation half ends there.
2. **A trial** on a handful of variants with a published methylation effect (an mQTL, an imprinting-region variant),
   measured against what is known, plus the live query rate. About two hours with the maintainer's API key.
3. **Only then a design**: where a predicted methylation shift is stored (a derived table or columns, at RM317's
   design interview, so the measured and the predicted halves share their vocabulary).

Indel scoring rides along only if step 2 shows the model service is usable at our scale; it was never v2's to
unlock.

**The trial, run 2026-11-12** ([ALPHAGENOME2_METHYLATION_TRIAL.md](probes/ALPHAGENOME2_METHYLATION_TRIAL.md)):
inconclusive, not negative. Cheap (about 1 s and 1 KB a call, deterministic, no throttling, indels accepted), and
strong only within about 15 bp of the variant. At nine published blood mQTLs its shifts stayed inside its own window
sensitivity (at most 0.046 logit against up to 0.1 of noise); 7 of the 8 readable signs agreed, but 6 of those came
from one locus. The vendored terms allow publishing the scores non-commercially only, with notice and the Use
Restrictions carried as a term, never under CC0 or CC BY. **So step 3 waits** on a second trial with enough loci,
spread across the genome, to tell signal from that noise, run at night; and on the live terms page re-read.

**The second trial, run 2026-11-14** ([§ 7](probes/ALPHAGENOME2_METHYLATION_TRIAL.md#7-trial-2-2026-11-14-a-signal-at-strong-mqtls)):
**a signal at strong mQTLs**, by a rule fixed before scoring. At 42 strong blood mQTLs on 18 chromosomes (ARIES,
middle age), the predicted shift at the published CpG was 27 times the shift at 84 matched non-mQTL variants
(median 0.49 against 0.018 logit, p = 3e-12), and 28 of the 31 readable signs agreed (p = 2e-6). It holds within
about 100 bp of the CpG, likely to 300 bp, and not beyond; trial 1's moderate mQTLs read at the null level, so
moderate effects are untested. Sizes move with the input window (−44% to +103% at 16 kb), signs do not. So what a
module could carry is a **predicted direction** for a variant already known as a strong mQTL, at a named CpG within
300 bp, stamped with model, condition, track and window, never a size and never a score for an arbitrary variant.
The live terms are newer than the vendored copies (Output Terms 2026-10-09, Additional ToS 2026-11-06): still
non-commercial with notice and the Use Restrictions as a term, and training any model on the output is now barred
except AlphaGenome-like ones. **So step 3, the design, is open** and goes to RM317's design interview; a third
trial on moderate mQTLs is the natural next measurement, wanted only if the design needs more than strong leads.

**Residuals** none yet.

## RM56 (policy half) — the rule for a measurement that spans bins

**Stays in 0.9, the pm (2026-11-05)**: it is in the PacBio zone: the real repeat-caller output it waits on is TRGT's, the same evidence as RM319. The status line below predates this.

**Severity** high on the flagship example · **Status** 0.6 ships withhold plus an explicitly
not-implemented warning; **the policy lands here, gated on real caller output** · **Owner** format
(schema) + compiler

A real repeat call is `RUC=38, CIRUC=-5,5` — `[33,43]`, crossing all three Huntington thresholds, so
`htt_repeat_expansion` says *benign*, *uncertain* and *fully penetrant* at once. 0.6 makes withholding
the stated behaviour and says loudly that no policy exists yet.

**The policy is a closed vocabulary** — withhold / take the worst bin / take the point estimate — stated
by the curator and applied by the consumer. That is annotation rather than measurement, so it stays
legal. **Its grain is deliberately undefined**: per table matches how the decision is actually made (a
stance on a whole disorder), per row is more expressive and nobody has demonstrated the need.

**The prerequisite is a real caller VCF**, so the vocabulary is fixed against what callers emit rather
than against a guess. Same gate as RM65; RM66's evidence arrived separately (see its entry).

**Never** widen the measurement into an interval on the row (`measure_min_observed` and friends): that
puts a *measurement* in the module, which the data-agnostic north star forbids outright.

## RM65 (implementation half) — repeat and copy-number tables are positional

**Stays in 0.9, the pm (2026-11-05)**: it is in the PacBio zone: its coordinates wait on a real repeat-caller VCF, which TRGT's output (RM319) is. The status line below predates this.

**Severity** medium · **Status** 0.6 corrects the false claim in the code; **the coordinates wait here**
· **Owner** format (schema) + compiler

§5.6 says POS and SVLEN specify the interval a copy number is defined over; §5.7 says a `<CNV:TR>`
record's POS and END *"should match the STR/VNTR reference catalog sizes for catalog-based callers"*. So
a tandem repeat and a copy-number segment are **loci with coordinates**, emitted at fixed published
positions, and the compiler's claim that these tables are unjoinable *"which is a property of what they
describe rather than a gap"* is false for both. 0.6 fixes the comment.

**Adding the coordinates waits on a real repeat-caller or CNV VCF sample, or a consumer field report.**
Without one it is scaffolding in thin air — and it is not free: it would put two more tables into RM43's
coordinate-filling path, taking that lane from three tables to five.

**And it carries an RM87 obligation, noticed while that lane was being built.** The reverse writer's
positional-table pass hard-codes `locus_index = 0` (`_write_resolution_csv`, the second loop), which is
honest only while those tables never expand — true today, since RM43's fill is one locus per row.
Putting coordinates on the repeat and copy-number tables is exactly what could make one of them expand,
and the `0` would then be a wrong number rather than a trivially correct one. Not a blocker for RM65;
a line whoever implements it must clear.

## RM66 — one repeat locus, several motifs

**Stays in 0.9, the pm (2026-11-05)**: it is in the PacBio zone: TRGT writes several motifs per locus (RM319's `FORMAT/MC`), and STRchive's `locus_structure` already decides it. The status line below predates this.

**Severity** medium · **Status** deferred here; filed beside RM65, but **its evidence has since arrived on its own** (below) · **Owner** format (schema)

§5.7: a `<CNV:TR>` allele *"can encode multiple different repeat motifs in a single allele"* (`RN=3`,
`RUS=CAG,TG,CAGG`). `RepeatAlleleRow` is keyed `(gene, repeat_unit)` and binds one count to one motif.
For HTT the interruption structure `(CAG)n(CAA)(CAG)` is exactly what a modern caller reports as several
`RUS` entries, and the pure-CAG tract length differs from the total — a difference with published effect
on age of onset. The key cannot say which count the thresholds are about, and two motifs for one gene
read as two unrelated groups rather than components of one allele.

A keying change on a shipped table, which is the expensive kind. Filed beside RM65 so both would
arrive with the same evidence — **and they no longer will (2026-09-01,
[RM165](ROADMAP_HISTORY.md#rm165--repeat_allelescsv-has-no-source-and-rm65rm66-have-been-waiting-on-exactly-the-corpus-one-would-bring)).**
STRchive publishes `locus_structure` on 23 of 82 loci as typed data with its own three-member
vocabulary, HTT's being exactly the `(CAG)n(CAA)(CAG)` structure above; that is enough to *decide* this
item and not enough to make the answer universal. RM65's prerequisite — a real repeat-caller or CNV
VCF — is still missing, so the two items now wait on different evidence and this one is decidable
first.

## RM67 — polyploid and partially-phased genotypes

**Stays in 0.9, the pm (2026-11-05)**: it is not work, so it is a note here, not a parked item. The status line below predates this.

**Status** **not work** — a documented divergence, numbered so it is findable and not re-probed

VCF 4.4 §7.2 added polyploid partial phasing (`GT |0|0/1/2`), first phasing indicator optional. Our
grammar caps at two alleles and refuses a leading separator (probed: `A/A/G` and `A|G/T` both rejected).

This is a **defensible generalization** — the format annotates human diploid loci, and
`_check_contig_ploidy` already handles the hemizygous and haploid directions. **No change proposed.** The
spec's own polyploid example is a tandem duplication with SNVs on it, which a CNV-aware consumer will
meet, so revisit if one actually does.

**The message changed on 2026-08-14; the decision did not.** Dogfooding a duplicated CYP2D6 — the
spec's own polyploid example — refused the call with a bare restatement of the grammar, so a deliberate
limit read as a syntax error, while every other deliberate refusal in this schema names its own limit
in-line. The arity refusals now carry that sentence: two alleles is a decision, VCF 4.4 §7.2 permits
more, and nothing is queued against it. Recorded as D3-2 in
[DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md).

---

# Vocabulary residue from the 0.7 consumer round

## RM149 — expected behaviour lives in prose, and the prose is where two readers split

**Frozen, decided 2026-11-03.** The maintainer froze the Gherkin work. The verification bench beside the seats kit (`harness/bestiary`) marks all eight of its Gherkin entries retired by their origin, after the acceptance pipeline's originator reversed on it in September 2026, and the same day the maintainer chose TLC model checking over Gherkin for the kit's own acceptance work. Nothing here is built until that is reopened; the status line below predates it.

**What the freeze leaves running, decided 2026-11-03.** The maintainer kept the corpus gate:
`schema/tests/test_feature_corpus.py` still fails a new warning code that has no scenario, so `features/`
keeps growing as text with each new code, and with no runner. The freeze stops the review and the runner work
this entry asked for, not the corpus.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-21; asked by the maintainer
2026-08-31** · **Owner** format + compiler (the test corpus) · **Found by** running the consumer loop

**The ask, verbatim in intent:** express our described scenarios as Gherkin, because the freeform prose
in expected-behaviour descriptions is producing ambiguities faster than it resolves them.

**The evidence for it is this repo's own recent record**, which is what makes this an item rather than a
preference. Three consumer reports in one week were **two readers splitting on one sentence**, none of
them a code defect:

- **S80** — `state`'s six members printed as peers; an agent chose a retired one honestly.
- **S83** — two runs of a byte-identical prompt wrote `risk` and `unknown` for one variant on one body
  of evidence, both green, both defensible against the field description.
- **S79** — a warning's text read as *your declaration is unsupported* when it meant *not universal*.

Each was answered by writing a better sentence. That is three fixes to prose in a week, and the pattern
says the next one is already in flight somewhere.

### What is actually being asked

Not a testing framework — the suite is not the problem, and a `pytest`-to-`behave` migration would be
motion rather than progress. The gap is that a **scenario** — *given a module with a partial
`resolution.csv`, when `validate --strict` runs, then it refuses with the compile's own error* — exists
today as a docstring, a test name, and a paragraph in `COMPILER.md`, and those three can drift from
each other and from the code. A structured form is one statement, and the natural home is a
`.feature`-shaped corpus each side is derived from or checked against.

### Open questions this needs decided before it can be built

- **What is the source of truth.** Gherkin generated *from* the tests is documentation that cannot
  drift; tests generated *from* Gherkin makes the feature files the contract and every existing test a
  migration. These are opposite projects with the same output, and the ask does not say which.
- **What is in scope.** Every check the compiler runs is ~140 warning codes plus a mode ladder. The
  release-gate scenarios, the tri-state outcomes and the parity rules are the parts where ambiguity has
  actually cost something; the round-trip fixed points are already pinned by assertion and would gain
  nothing from prose.
- **Where it lives.** A `features/` tree at the root, per-package, or inside `docs/`. That decides
  whether it ships to consumers — and if it does, it becomes a published surface under P3, which is a
  much larger commitment than an internal one.
- **What it costs the next contributor.** A second dialect to learn beside the docstring convention
  this repo already leans on heavily, and every new check owing a `.feature` clause. That is the P9
  question one layer up: this is a *maintenance* surface, not an authored one, and it is not free.

### Why it is filed rather than started

The three reports above were each fixed by naming what the rule is, and the fix was one string. A
scenario corpus is worth building when the *cost of ambiguity* exceeds the cost of the corpus, and the
measurement that would show that has not been taken — this entry is where it goes when it is. What is
not in doubt is the direction: the recurring failure is real and repeatedly measured, and it is filed
here so the next instance lands against a number rather than as a fourth anecdote.

### Addendum, 2026-09-13 — a first corpus is drafted, and this is the measurement

**Status is still open.** What exists is a draft, unreviewed, at `features/` in the repository root:
12 `.feature` files, 213 scenarios, guarded by `schema/tests/test_feature_corpus.py`. Nothing
about it is a contract yet, and the entry stays here rather than moving to ROADMAP_HISTORY until it has
been read.

**Two of the four blocking questions are answered by the ask itself**, and are recorded in
`features/README.md` as assumptions rather than decisions:

- **Source of truth: code → Gherkin.** The scenarios describe what the code does. No step definitions,
  no `behave`, no `pytest-bdd`, no new dependency in any tier; the `pytest` suite stays the executable
  statement of behaviour and this is the readable one.
- **Where it lives: the repository root, not `docs/`.** That keeps the P3 publishing question *open*
  rather than answering it by side effect, which a drafting round has no standing to do.

**Scope is decided by registry rather than by taste**, which is the third question. Three walked sets
are covered in full: `VALID_WARNING_CODES`, `VALID_VERIFICATION_CHECKS`, `VALID_VERIFICATION_SKIPS`.
Round-trip fixed points are out, on this entry's own argument. **And the scope estimate in the body
above is wrong by a factor of two**: it says *~140 warning codes*, and `VALID_WARNING_CODES` has **73**.
A number in prose beside a registry, in the entry that exists because prose drifts — left in place
above rather than silently corrected, because it is the fourth instance of the shape this round
measured and the most on-the-nose.

**The fourth question — what it costs the next contributor — has a partial answer and it is the
cheaper half of the estimate.** A new warning code without a scenario fails the guard, so the cost is
one scenario per code, not a second dialect to learn: there are no step definitions to write and no
runner to learn. What is *not* yet measured is whether a reviewer finds the scenarios easier to check
than the docstrings they stand beside, and that needs a reader rather than a round.

#### The measurement this entry was waiting for

The case for the corpus was to be made on *the cost of ambiguity exceeding the cost of the corpus*.
Drafting it produced **four findings in the first pass**, two of them code-or-doc defects that were
filed and fixed rather than noted:

| # | finding | disposition |
| --- | --- | --- |
| 1 | **Two of our own documents disagree about whether `strict` builds.** COMPILER.md's validate-by-redundancy table gives the rsid↔coordinate check the severity *warning* with no qualifier; its own mishap matrix gives the same check *⚠️ warning / ❌ refuses*. The matrix is the half the code agrees with. | marked `# DRIFT:` in `features/compiler/mode_ladder.feature`, unrepaired — the round's findings are its output |
| 2 | **The mode ladder is two mechanisms and reads as one.** Four codes flip channel on one sentence; three resolution codes pair a warning with a *different, longer* refusal through `ResolutionOutcome.strict_errors`. Calling those ladder members quotes a text that does not exist; calling them warn-only describes a compile that succeeds. | written down in the same feature; no defect, a distinction nothing stated |
| 3 | **`alphagenome check` with no API key raised instead of recording a skip** — `skipped(CHECK, "unchecked")`, and `"unchecked"` is not a vocabulary member. | **[RM242](ROADMAP_HISTORY.md#rm242--alphagenome-check-without-an-api-key-raised-where-it-was-supposed-to-attest-nobody-asked)**, fixed |
| 4 | **Four per-command attestation counts summing to 17 of 24**, in ENRICHER.md's paragraph that refuses to state a total. | **[RM243](ROADMAP_HISTORY.md#rm243--the-paragraph-that-refuses-to-state-a-total-stated-four-of-them-summing-to-17-of-24)**, fixed |

**What produced each of them is worth separating from the fact that they were produced.** None came
from reading prose more carefully. Finding 1 came from writing the severity down as a table and
noticing two tables; finding 2 from having to name a mechanism in order to tag a scenario; findings 3
and 4 from AST walks the corpus needed anyway — the emission-site check and the skip-reason enumeration.
So the argument this addendum supports is narrower and stronger than *Gherkin is good*: **the act of
deriving a scenario from an emission site is what found things, and the guard is what will keep
finding them.** A corpus of prose scenarios with no grounding check would have found none of the four.

#### The three assertions that make it worth more than the prose — and what each really covers

Each was proven by reintroducing the defect and watching it go red, which is this workspace's standing
requirement. Two of the three were **narrower than they read on the first pass**, and both narrowings
were found by measuring rather than by re-reading, which is worth recording because a guard that
half-covers its subject while the reference claims it covers all of it is worse than no guard:

- **a `@code:X` scenario's `# source:` sits within three lines of X's own `CodedWarning` call.** Held
  from the start.
- **the same alignment for `@check:` and `@skip:`.** *Missing at first*, and it cost precisely what it
  exists to prevent: RM242 and RM243 — the two fixes this round produced — inserted six and eight
  comment lines above referenced sites, eleven `# source:` lines silently began pointing six to eight
  lines early, and the suite stayed green, because those two tags had only *the line is inside the
  file*. The guard now catches all fourteen when the insert is reproduced. Two of the eight skip reasons
  (`tautology`, `not_permitted`) are never passed to `skipped()` as a literal at all — they travel as a
  variable — so the alignment is against any literal naming the reason, which is the better pointer
  anyway: where a reason is *decided* is what a reader wants.
- **every phrase a step quotes as a warning's text is a real substring of a real string literal in the
  module named.** *Keyed on a verb before the quote at first* (`contains`/`says`/`states`), which
  extracted **46 of the 162** quoted phrases — a `Then` also says `saying the flag "…"`, `ends at "…"`,
  `continues "…"`, `offers "…"`. Keyed on the step keyword instead, it now checks **160 of 160** on
  outcome steps, and the widening found three real defects in the corpus. `Given`/`When` stay excluded:
  those name an input value, which has no reason to appear in the module's own strings.

**The residue, measured rather than estimated.** Of 213 scenarios, **108 carry a registry tag and are
aligned; 105 are structural** — pointing at a docstring, a branch or a constant, with no call site to
align against — so they carry only the *line is inside the file* check and will rot on an edit above
them. Measured 2026-09-13 by walking the corpus, because the first draft of this paragraph said
"roughly 130" on an estimate, in the document whose whole subject is unmeasured counts beside
registries. That is a real contributor cost and it belongs in the fourth question's answer above rather
than in a footnote.

One mechanism had to be added rather than worked around: a message built by one module and coded by
another (`layout.deprecation_notice` writes the sentence, `_locate_sidecar` names the code) needs a
`# text:` line, so the code is checked against the emission site and the phrase against the module that
holds the words. That is the boundary where a code goes missing
(`@finding-loses-its-code-at-a-boundary`), and it is better as a checked fact than a convention.

#### What a review should push on

- **Is the root the right home, or should this publish?** Publishing makes every clause a P3
  commitment. The draft assumes not, and the assumption is the thing to overturn first if at all.
- **Are the scenarios readable by someone who did not write them?** That is the whole premise and it
  cannot be self-assessed. If the answer is no, the corpus is a second dialect with none of the benefit
  and this entry should close rather than grow.
- **Should the DRIFT finding be repaired here or filed?** Finding 1 is one sentence in COMPILER.md.
  Leaving it marked was deliberate — a round that silently fixes what it finds cannot be audited — but
  it should not stay marked for long.
- **The corpus has no scenarios for the compiler's `errors` that carry no warning code**, beyond the
  handful written as `@refusal`. Whether a refusal without a code deserves the same coverage as a coded
  warning is an open scoping question the registry cannot answer, because refusals have no registry.

### Second addendum, 2026-09-13 — the second pass, and where coverage was not what the equalities said

**Still open, still a draft.** The corpus is now 13 files and **228 scenarios** — 118 registry-tagged
and aligned, 110 structural — with **182 quoted phrases** on outcome steps. The question this pass put
was the one the first pass could not put to itself: *are all the features covered?* The three registry
equalities said yes and they were answering a narrower question than they read.

**Four findings, and what produced each.** None came from reading the scenarios again; three came from
walking a set the first pass did not walk, and the fourth from reading the residue the first pass
measured and left.

| # | finding | disposition |
| --- | --- | --- |
| 5 | **A code is not a text.** Nine resolution codes are emitted by the compiler's `resolution.py` *and* by the enricher's `resolver.py`, and **seven of the nine pairs are a different sentence**. `rsid_unresolved` is *"not found in resolution table, position remains unset"* in one tier and *"not in the injected Ensembl snapshot"* in the other. The per-code equality accounted for all nine while the corpus held none of the enricher's words for any of them, and a warning's text is an API. | fixed — the equality now keys on `(code, tier)`, and `features/enricher/resolution_warnings.feature` is the nine in the enricher's own words |
| 6 | **The house algebra was covered as a mechanism and not as a value.** `tri_state.feature` had Kleene, the withhold, `classify` and `restate`, and not one of the columns that carries a three-valued answer into an artifact: **five of the nine members** of `VALID_FREQUENCY_STATUS`, `VALID_RESOLUTION_STATUS` and `VALID_AUTHORITY_CALL_STATUS` appeared nowhere in the corpus, `not_covered` among them — the member the gnomAD Y-PAR probe was run to justify. | fixed — six scenarios; the walk that found them (three-member `VALID_*` sets) is recorded as the heuristic it is |
| 7 | **`@ladder` was a judgement written four times over a walkable set.** The mode ladder's first mechanism is `(errors if strict else warnings_out)`, and the codes reachable from a function carrying that shape are exactly the four tagged. | fixed — a fourth registry equality, proven red by untagging `p_value_encodings_disagree` |
| 8 | **Ten `# source:` lines pointed at a blank line, a bare `"""`, a bare `return [` or the middle of a comment — and two pointed at the wrong subject.** *a total function cannot decide a three-valued answer* named a comment about a length constant in `normalize.py` when the rule is `mitomap.vcep_clin_sig`; *an absent input is the unknown arm* named the concordance block in `vocab.py` when the rule is `needs_recompile`. Both scenarios stated their rule correctly and cited the right tag; only the pointer was wrong. | fixed — all ten re-anchored; **not rot**, since no source file here has changed since the corpus was written, so they were authored that way and nothing could say so |

#### Two questions the first addendum left open, now answered with a measurement

- **Refusals without a code have no registry, and the reason is that they have no shape.**
  `compiler.py` alone reaches the error channel from **four** distinct mechanisms — an inline
  `errors.append` of a literal, an `extend` of a helper's returned list, the
  `(errors if strict else …)` selector, and `ResolutionOutcome.strict_errors` — across roughly forty
  sites, against 22 scenarios tagged `@refusal`/`@strict_only`. So the answer to *should a refusal
  without a code get the same coverage as a coded warning* is not *no*; it is that **there is nothing to
  walk**, and inventing a registry so an equality can be written would be the `@registry-completeness`
  defect committed on purpose. It stays a scoping question for a reviewer, now with a number beside it.
- **The phrase check's file scope is correct, and that was measured rather than assumed.** Eight of the
  182 quoted phrases match no message at the site their scenario names but do match another literal in
  the same module. All eight were read: every one is a message built into a variable a few lines away
  (`ambiguous_warnings`, `_verify`, `coordinate_disagreement`, `layout.deprecation_notice`). Tightening
  the check from the module to the call site would need dataflow and would report eight correct
  scenarios as defects. Recorded so the next pass does not re-derive it.

#### What this pass did not touch

The `# DRIFT:` in `mode_ladder.feature` still stands — finding 1 of the first pass, one sentence in
COMPILER.md, and a repair decision rather than a drafting one. And `# anchor: <token>`, a symbol the
guard could grep for instead of a line number, is the obvious repair for the 110 structural scenarios
and is deliberately unbuilt: it is a convention change across the whole corpus and belongs to whoever
reviews it.

**Not to be confused with** `just-module-creator`'s authoring guidance, which is a different
document for a different reader and stays prose. This is about *our* stated behaviour, not an author's.

# The lifecycle items — what writing down the second pass surfaced

Filed on **2026-08-16** out of [MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md), which mapped a module from
origin to publish to a consumer's join and found that **the second pass had never been written down at
all**. Four items, none of them a defect in a rule: each is a place where two individually-correct rules
compose into something nobody chose, or where an absence only bites the second time somebody opens a
module. The document keeps the measurements (§5.1 the canary, §6.2 the six-edit consequence matrix, §6.3
what deleting a sidecar costs); these entries keep the decisions and the refused repairs, and do not
restate the numbers.

They were the closing section of that document — an "open questions" list — which is exactly the shape
this repo has twice found to be a backlog nobody reads. A question filed against a release is findable;
a question at the bottom of a prose document is not.

Everything here is legal in a minor.

## RM84 — a module has no version identity on the discovery path, and the publisher is the half we own

**Stays in 0.9, the pm (2026-11-05)**: the open half is the consumer's, so it is a note here, not a parked item. The status line below predates this.

**Severity** medium-high · **Status** **our half SHIPPED in the 0.6 PT2 batch (lane D, 2026-08-17)** —
`upload_module` writes `data/<name>/` and `data/<name>/v<version>/`. **The segment spelling is settled
and both asks are answered** ([S35](CONSUMER_SUGGESTIONS_HISTORY.md), 2026-08-17): `v<version>` verbatim
stays. Only the consumer's discovery half is open, and it is theirs, which is why this entry stays here.
*Previously:* our half taken into 0.6 PT2 on
2026-08-16 ([PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM84); before that, open — **joint with the
reference consumer, and their half is already agreed in writing** · **Owner** enricher
(`upload.upload_module`) + `just-dna-lite` discovery ·
**Motivating case** a republished module on the HuggingFace path

**Why a partial mitigation does not close it** (S34 §3): the fields a consumer can read today record
*where* a module came from, never *which build* of it. Two uploads under one path are then
indistinguishable on the discovery side, which is the half this item exists for.

### What was observed

[MODULE_LIFECYCLE § 6.8](MODULE_LIFECYCLE.md#68-what-a-consumer-sees-when-v2-lands) traces two
acquisition paths with two entirely different notions of "updated", and neither delivers a notification.
The registry path at least has a per-version audit. The **discovery path has no version identity at
all**: no version in the path, no manifest fetch, no digest check. A republished module keeps the same
URL, so a cached copy shadows it, and the only invalidation is a purge keyed on the *consumer
application's own package version*. Stated plainly: on that path the identity used to detect "the module
changed" is a property of the reader, not of the module. A module republished with new science while the
app stays pinned is invisible; an app patch release with no module change purges everything.

**Half of that is ours.** `just_dna_enricher.upload.upload_module` writes the flat `data/<name>/` layout
— so this tier publishes the shape that cannot express a version, and no amount of consumer-side work
invents one.

### Why it is joint rather than ours alone

A pinning surface is a change to our publisher **and** to their discovery in the same breath: a version
segment nobody reads is dead bytes, and a reader looking for a segment nobody writes finds nothing.
[S34 § 4](CONSUMER_SUGGESTIONS.md) is the consumer's half, already stated: *"If the publisher grows a
version segment we will follow it in discovery; the `vN` fallback in our generic fsspec scan is already
the shape."* That is as close to a pre-agreement as a cross-repo item gets, and it makes this cheaper
than "wants agreeing" implied when it was first written down.

### What is undecided

*Was:* the layout itself — a `vN` segment, a digest segment, or a pointer file — and what happens to
every module already published flat, which is all of them. Whatever is chosen has to leave an
unversioned path working, because that is what is deployed.

**Settled on our side.** The layout is the dual write, decided in PROPOSAL_0_6_PT2 § RM84 and built in
lane D. Nothing already published moves, because the flat path keeps being written and keeps meaning
*latest*. The full behaviour, including the null-version fallback and the two-commit caveat, is
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84).

### The ask was put, and answered the next day — both questions closed

**Asked** in ENRICHER.md (RM27's shape: a finding about a downstream reader is an explicit ask, never an
implication), delivered there rather than into their tree because `just-dna-lite` carries no consumer
inbox. **Answered as [S35](CONSUMER_SUGGESTIONS_HISTORY.md) on 2026-08-17**, read off their code file
and line rather than recalled.

*(1)* **Their scan matches only `v`-plus-integer** — `^v(\d+)$`, compared with `int()`, so `v1.0.0` does
not match and `v10` would sort under `v9`. **The half that actually decides it is their correction, not
the regex:** that fallback lives only in `_discover_fsspec_source`, the generic github/http/s3 branch.
HuggingFace has its own branch with **no version fallback at all** — so on the path this item is *about*,
no spelling is read today and the segment cannot be chosen to suit one. Their words: S34 § 4's *"the `vN`
fallback in our generic fsspec scan is already the shape"* was accurate about the shape and quoted about
a branch that does not serve HF, and they call that their error rather than a misreading here.
**So `v<version>` verbatim stays** — a bare major segment would still collide two patch releases at one
path, and would buy nothing since the code that would read it is not on this path.

*(2)* **No, and by construction rather than by luck.** Both discovery branches call `fs.ls` at exactly
one level and never `fs.find`, a `**` glob or a recursive listing, and their probe asks `fs.exists` on
named files rather than listing the directory it is probing — so a nested `data/<name>/v<version>/` is
never enumerated and never probed. Verified in their tree by search: no `fs.find`, `recursive=True`,
`maxdepth` or `snapshot_download` against a module path anywhere. The one part of this change that could
have regressed a consumer who never adopts it, and it does not.

**One consequence recorded rather than fixed**, raised by them as a consequence and not an objection:
the dual write doubles the collection's bytes and nothing prunes `data/<name>/v<version>/`, so the repo
grows one full artifact set per release forever. It does not affect discovery. Retention is the
collection owner's decision, not the publisher's; noted in
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84).

**What is left here is theirs and unscheduled:** teach `_discover_hf_source` a versioned fallback, and
replace the regex and `int()` with `just_dna_format.identity.Version`, which already gives them parsing
and ordering. Nothing is broken meanwhile — the flat path resolves and keeps meaning *latest* — so their
`read_module_provenance` states `version: None` for every HF-discovered module, which their report
renders as *Not stated*.

**Confirmed by exhaustive search to have had no `Sn` and no `RMn`** before this entry, which is why it
is filed rather than cross-referenced.

### Two items building this surfaced, filed 2026-08-17 rather than folded in

Both were found by writing the code, not by planning it, and neither is a defect in what shipped —
recorded here because this entry is where a reader meets the publisher.

- **[RM88](history/ROADMAP_HISTORY_0_6.md#rm88--republishing-without-bumping-version-overwrites-a-versioned-path-with-different-bytes)** — the versioned path cannot notice that the version has *not* moved, so a republish
  without a `version:` bump overwrites it with different bytes. Refusing needs a remote read *and* an
  undecided policy (warn / refuse / `--force`), which is why it is an item and not a fix.
- **[RM89](history/ROADMAP_HISTORY_0_6.md#rm89--the-publisher-cannot-upload-a-table-only-module-at-all)** —
  `_REQUIRED` still demanded all three SNP-core parquets, so a table-only module could not be published
  at all: seven of the sixteen reference examples, measured. Its open question — what the discovery path
  actually needs open — went to the same team as the two asks above rather than as a third message, and
  **came back with them in S35, so it shipped on 2026-08-17**. Answering it found the larger half:
  `_ALLOW_PATTERNS` carried no 0.4 family and no derived-fact table either, so eight *more* examples
  published a manifest attesting parquets that were never uploaded.
