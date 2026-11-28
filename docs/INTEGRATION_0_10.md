# Integrating 0.10 — what changed against the 0.9 surfaces

For the repos that consume this one: **just-dna-registry**, **just-dna-lite**, **just-dna-pipelines** (inside
just-dna-lite) and **just-module-creator**. It answers one question: *given a working 0.9.0 integration, what do I
have to check, and what do I have to change?* § 1 is the surface delta, item by item. § 2 is the upgrade order and
the changes it implies, by surface. § 3 is the same list cut per consumer. § 4 lists the known issues 0.10 ships with.

**What 0.10 is.** An even minor (features and the maintainer's decisions, RELEASE_CYCLE.md § Tic/tac): a release can
say which derived tables an enricher upgrade asks you to re-derive (RM399, RM441); four optional authored additions (a
study's effect direction, RM435; `panel_provenance:`, RM265; lay and concise conclusion wordings, RM302; STRchive's
evidence grade beside the repeat loci, RM294); offline left-alignment against an operator's own GRCh38 FASTA (RM385);
a host-wide store of live answers keyed by the release that answered (RM468); HLA allele names checked against a
pinned IPD-IMGT/HLA release (RM350); and the warning code RM449 named for 0.9 (RM460). RM471, an enricher patch built
on `main` for a 0.9.1 that was never cut, ships inside 0.10.0. All three packages move.

**Status: cut as 0.10.0 on 2026-11-28, on the branch `cut/v0.10.0` (off `0.10`).** All three packages are `0.10.0`,
every intra-workspace floor is `>=0.10.0`, and no third-party floor moved. Publishing to PyPI is the maintainer's; the
tag `v0.10.0` follows the publish. PyPI's latest at the cut is 0.9.0 for all three.

**Pin the release:**

```toml
dependencies = [
    "just-dna-format>=0.10.0",
    "just-dna-compiler>=0.10.0",
    "just-dna-enricher>=0.10.0",
]
```

**Raise the format floor first.** 0.10 has old-reader breaks (§ 1.0): a format reader older than 0.10 refuses a
manifest that counts one of the new warning codes, a licence row on the new source layer, and a verification record
of the new check. Any service that reads modules (a catalog, a validator, a server) moves to format 0.10 before
anything it reads is compiled or enriched by 0.10.

**The consumers' preview ran (RELEASE_CYCLE § Minors step 6, encouraged for an even minor).** The registry and
just-module-creator tried the first batch on `992e85b1` before the first review round; their findings S163, S165 and
S166 were built on `0.10`, and the registry re-ran its socket-tripwire re-derive on `135eed6d` with no sequence
request leaving the host. The second batch (RM265, RM302, RM294, RM350, S167) went to just-module-creator in parallel
with round 1. Two review rounds ran, the last on `12975c1d`, and found no blocker; their known issues are § 4.

[RM_TOC.md](RM_TOC.md) is the per-item record, and the [CHANGELOG](CHANGELOG.md)'s 0.10 headings carry every change
in detail; this file says what a consumer does about them.

---

## 1. The surface delta

### 1.0 What a 0.9 reader refuses

A 0.9 format reader rejects a row or record that uses one of these 0.10 members: `warnings_summary` and the other
fields below validate against closed vocabularies. The table is checked against the vocabularies at `v0.9.0` by
`schema/tests/test_old_reader_breaks.py`, so it lists every new closed member and nothing else.

### Old-reader breaks

| Closed vocabulary and field binding | New member |
| --- | --- |
| `VALID_SOURCE_LAYERS`, `source_layer` | `repeat_grade` |
| `VALID_VERIFICATION_CHECKS`, `verification_check` | `hla_allele_assignment` |
| `VALID_WARNING_CODES`, `warning_code` | `hla_allele_deleted` |
| `VALID_WARNING_CODES`, `warning_code` | `hla_allele_not_assigned` |
| `VALID_WARNING_CODES`, `warning_code` | `panel_unmatched_has_rows` |
| `VALID_WARNING_CODES`, `warning_code` | `panel_unmatched_not_requested` |
| `VALID_WARNING_CODES`, `warning_code` | `rsid_genotype_reads_as_two_events` |
| `VALID_WARNING_CODES`, `warning_code` | `study_effect_direction_disagrees_with_size` |

### 1.0.1 The other two breaks: new authored fields, and one filename

**New fields on authored models that forbid unknown fields.** A 0.9 compiler or validator refuses a module that uses
one of them, as `extra="forbid"` refuses any column or key it does not know. That reaches a consumer when it reverses a
0.10 module and recompiles it with 0.9, or validates 0.10 specs with a 0.9 format. The fields are
`panel_provenance:` in `module_spec.yaml` (RM265), `effect_direction` on `studies.csv` (RM435), and
`conclusion_lay` and `conclusion_concise` on `variants.csv`, `diplotypes.csv`, `pharm_variants.csv` and the measure-bin
tables (RM302). INTEGRATION_0_7 counted `VerificationRecord.producer` the same way. A module that states none of them
is read by 0.9 as before.

**The manifest's new keys are not breaks.** `ModuleManifest` ignores unknown keys, so a 0.9 reader reads
`manifest.panel_provenance` and `manifest.repeat_grades` as absent.

**A 0.9 compiler warns `table_file_near_miss` on `repeat_grades.csv`.** Its similarity to `repeat_alleles.csv` is
exactly 0.8, the filename check's inclusive cutoff, so 0.9 reads the new derived table as a misspelling. The warning
is harmless (the table is not read), but a consumer that fails a build on warnings will fail there. A registry that
lists recognised tables recognises `repeat_grades.csv` at its own bump.

### 1.1 Which tables an enricher upgrade asks you to re-derive (RM399, RM441, S156, S161)

`just_dna_enricher.derivation_records` answers offline, from the enricher's own records, whether moving from one
enricher release to another changes the derivation of a derived table: `needs_rederive(from_release, to_release,
table=None)` (three-valued: `True`, `False`, or `None` when a release in the interval has no record),
`rederive_reasons(...)` (the releases, causes and items behind the answer) and `newest_rederive_release(table)` (S156:
the newest enricher release whose derivation of that table could have changed). Both queries walk every published
release in between, so an unlisted release withholds an all-clear rather than being skipped. The records cover a
reference lane moving (0.8.0's Ensembl switch, RM372) and a declared correction (0.8.5's rsID correction, RM438), and
each table answers only from the release that first produced it (`repeat_grades.csv` from 0.10.0).

The format's `release_records.needs_recompile` still answers the compiled-output question; the two are separate
questions, and a consumer asks both.

### 1.2 Offline left-alignment against a local GRCh38 FASTA (RM385, S157, S165, S166, S167)

`enrich` and `vrs mint` take `--sequence-uri fasta+file:///abs/path.fa` (and `enrich(..., sequences=proxy)` a
`SequenceProxy` built from one), so an `--offline` run can left-align an indel, mint its VRS id and check an authored
REF without the network. Each contig is checked against its GRCh38 refget digest before use; a missing or mismatched
contig stays unread and the report says why. The REF attestation names its source, `fasta` or `seqrepo`.

- **The FASTA is host-provisioned.** No lane publishes it. NCBI's `GCF_000001405.40` (GRCh38.p14) binds all 25
  primary contigs; UCSC's `hg38.fa` binds 10 of 25 (measured 2026-11-27). The first digest pass over the whole file
  took about 393 s here; digests are then cached beside the reference in `.refget.json`, keyed on the file's size and
  mtime (RM480 in § 4).
- **`just-dna-enricher fasta index PATH`** (S167) writes the five-column `.fai` beside an unpacked FASTA, byte-identical
  to `samtools faidx` on the full NCBI file; `fasta.write_fasta_index(path)` is the same writer.
- **`SequenceProxy.contig_identity()`** (S165) reports which primaries a FASTA can serve, each with its indexed name,
  expected accession, computed digest and status (`VALID_FASTA_CONTIG_STATUS`).
- **One proxy across runs** (S166): `EnsemblResolver(sequences=proxy)`, `enrich(..., sequences=proxy)` and
  `draft_panel_from_civic(..., sequences=proxy)`; the CLI takes `--sequence-uri` on `draft-panel --source civic`, CPIC
  `draft` and the `civic reproduce` cross-check.
- **A read past a contig's end withholds** (round 2's R3): the placement is withheld with the contig and its length,
  never shifted onto a position that does not exist.

### 1.3 Live answers persist between runs (RM468, S162, S163)

The live clients (Ensembl REST, NCBI E-utilities, remote seqrepo) keep each answer in a host-wide SQLite file,
keyed by the release that answered. **It is on by default**, at `live-answers.sqlite3` under the cache base;
`JUST_DNA_ANSWER_STORE` names another file or, set empty, turns it off; `--no-answer-store` bypasses it for one
command. **With the store on, a run asks each source's release before its first answer** (Ensembl's `/info/data`,
NCBI's `einfo` per database), so a moved release sends only that source's subjects back to the service. An explicit
absence survives a re-run; a failed request is asked again. The enrichment report states, per source, the release and
how many subjects came from the store and how many were asked live. A host passes its store as
`LookupClients(answer_store=...)`, or wraps a batch in `answer_run(...)` for one release probe per source.

### 1.4 HLA allele names against IPD-IMGT/HLA (RM350)

`enrich` checks authored HLA allele names in `allele_function.csv` at their stated resolution against a pinned
IPD-IMGT/HLA release: a deleted name warns `hla_allele_deleted` with the curators' reason, an unassigned one
`hla_allele_not_assigned` with the release searched, both warnings under `strict` too. The result is a
`verification.json` record of the new check `hla_allele_assignment` (an old-reader break, § 1.0), which names the
tables it read; an unavailable list records it skipped. The lists come from a new **per-host** lane, `ipd_imgt_hla`
(`cache rebuild --only ipd_imgt_hla --pin ipd_imgt_hla=3.66.0`), which keeps the curators' files verbatim and has no
publisher: the curators ask that their data not be mirrored. A run that reads it writes their citations into
`sources.csv`.

### 1.5 The four optional authored additions

- **`studies.csv` `effect_direction`** (RM435): a study can state that its effect allele increases or decreases the
  trait without a size. Stating it moves `content_signature`; a blank column keeps it, and `studies.parquet` omits the
  column when every row leaves it blank. A direction without an allele warns `paired_field_half_stated`; a direction
  that disagrees with the size's sign warns `study_effect_direction_disagrees_with_size`, under `strict` too.
- **`panel_provenance:`** (RM265): `genes`, `significance` and `reference_sha256` move from `panel:` into this block,
  with `genes_unmatched`, so a reader tells a gene that yielded no row from one never requested. Both identity hashes
  are unchanged, reverse restores the block, and the manifest carries it as `panel_provenance`. Validate and compile
  warn `panel_unmatched_not_requested` and `panel_unmatched_has_rows`; `panel_block_deprecated`'s text now says when
  the old block can go. ClinVar `draft-panel` prints the merged block to paste (dry run included), and
  `ClinVarDraftResult.panel_provenance` carries it for a Python caller.
- **`conclusion_lay` and `conclusion_concise`** (RM302) on variants, diplotypes, pharmacogenomic variants and measure
  bins, beside `conclusion` (the detailed wording). The model is `ConclusionRegisters`. A stated register enters
  `content_signature` and survives reverse; leaving both blank keeps both the signature and the artifact digest.
  Neither enters a key; `language` is reserved.
- **`repeat_grades.csv`** (RM294), a derived table `enrich` fills for the repeats a module carries: STRchive's evidence
  grade (`Definitive`, `Refuted`, `Provisional`, …, verbatim), the disease, the catalogue record and its release. It
  compiles to `repeat_grades.parquet` and the manifest's `repeat_grades` summary; a grade whose repeat key left the
  module warns. The licence row's layer is `repeat_grade` (an old-reader break, § 1.0). Its fact columns are
  `just_dna_format.repeat_grades.REPEAT_GRADE_FACT_FIELDS`.

### 1.6 RM460's warning code for a mirrored site

A genotype that reads as an insertion at one spelling and a deletion at the other is counted under
`rsid_genotype_reads_as_two_events` in `compilation.warnings_summary` (an old-reader break, § 1.0). The code is not in
`CARRIED_WARNING_CODES`: replacing the rsID row with the intended event's coordinate clears it, so a catalog that
subtracts `compilation.carried` still shows it to the author. Where authored coordinates claim every spelling, the
sentence keeps `rsid_no_hosting_locus` (`ALL_SPELLINGS_CLAIMED_CODE`). The texts, the filled rows and the treatment
under `strict` are 0.9's.

### 1.7 Smaller changes

- **`reverse` orders an unphased genotype's alleles without regard to case**, as the compiler does, so `a/G` round-trips
  (RM302's build).
- **`regex_matches` starts its timeout at the child's ready signal** (RM471), so a loaded machine no longer records a
  trivial `provenance_regex` as not checked; the start-up has its own 60 s allowance and warning.
- **CI checks out the full history with tags**, so the tag tests run there (round 2's R4; RM478 in § 4).

### 1.8 Names added, documented

The tier references name every public definition added since `v0.9.0` (round 1's C6, a test over all three packages),
and five module-level names that walk does not see yet (RM482): `FASTA_SCHEME`, `VALID_FASTA_CONTIG_STATUS`
([ENRICHER.md](ENRICHER.md)), `StoreSetting` ([ENRICHER.md](ENRICHER.md)), `ALL_SPELLINGS_CLAIMED_CODE`
([COMPILER.md](COMPILER.md)) and `REPEAT_GRADE_FACT_FIELDS` ([SCHEMAS.md](SCHEMAS.md)).

### 1.9 What a recompile moves

`release_records.RELEASE_RECORDS["0.10.0"]`, measured at the cut against compiler 0.9.0 on the 22 reference modules
with polars 2.1.0 on both sides, records one axis moving: `manifest_fields`, because every 0.10 manifest carries the
two new keys `panel_provenance` and `repeat_grades` (null where the module states neither), declared as additions.
No `artifact.digest`, `content_signature`, parquet schema or warning moves, so `needs_recompile(stamp, "0.10.0")`
answers that a 0.9.0 artifact's content does not change on a recompile. A module that states one of 0.10's new
authored fields moves its signature by that edit, never by the recompile.

For derived tables, `needs_rederive("0.9.0", "0.10.0", table)` answers `True` for `sources.csv` (RM294's and RM350's
new licence rows) and `literature.csv` (RM471), `False` for `resolution.csv` and the rest. RM385 changes no table a
0.9 run wrote: an offline run given a FASTA answers placements 0.9 could not ask, which a plain run fills.

---

## 2. What to change

### Upgrade order

1. **Format first, everywhere a module is read** (§ 1.0): raise `just-dna-format>=0.10.0` in every reader before any
   0.10-compiled or 0.10-enriched module reaches it.
2. **Then the compiler and the enricher**, all on `>=0.10.0`. The compiler floors format 0.10 because it imports
   `just_dna_format.repeat_grades`, and the enricher floors both.
3. **`uv lock`**, regenerated, committed with the floors.
4. **Ask both release questions for what you hold**: `needs_recompile(stamp, "0.10.0")` for compiled output (§ 1.9),
   `needs_rederive(from, "0.10.0", table)` for each derived table (§ 1.1).
5. **Optional, per box:** provision a GRCh38 FASTA and its `.fai` where offline indels matter (§ 1.2); place the
   answer store, or turn it off, where several hosts share a cache base (§ 1.3); rebuild the `ipd_imgt_hla` lane where
   modules carry HLA names (§ 1.4).

### Changes, by surface

1. **If you read `warnings_summary`, `sources.csv` layers or `verification.json` checks as closed sets** (§ 1.0): add
   the new members, or raise the format floor and read the vocabularies from it.
2. **If you fail a build on compiler warnings and still run a 0.9 compiler anywhere** (§ 1.0.1): `repeat_grades.csv`
   trips `table_file_near_miss` there.
3. **If you subtract `compilation.carried` before showing warnings** (§ 1.6): `rsid_genotype_reads_as_two_events` is
   not carried, and reaches the author.
4. **If you draft panels from ClinVar in Python** (§ 1.5): carry `ClinVarDraftResult.panel_provenance` into the spec
   you write.
5. **If you list recognised table files** (§ 1.0.1): add `repeat_grades.csv`.
6. **If your runs must not touch an egress budget twice** (§ 1.3): nothing to do, the store is on; set
   `JUST_DNA_ANSWER_STORE=` where it must be off, and expect one release request per source per run.
7. **If you run enrich offline on indels** (§ 1.2): pass `--sequence-uri fasta+file:///…` with an indexed GRCh38 FASTA;
   without one, those placements stay withheld as in 0.9.

---

## 3. Per-consumer check / change lists

Written from this repository's own record of each consumer (the liaison's notes, the consumers' suggestions in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), the preview's reports); no consumer checkout was
re-read for this file.

### just-dna-registry (spec storage, catalog, serving)

The consumer most of 0.10's enricher work was built for (S156, S157, S161, S162, S163, S165, S166).

**Change**

1. **Raise the format floor on every server first** (§ 1.0): its catalog validates manifests, and the new warning codes
   reach `warnings_summary` on the first 0.10 compile.
2. **Replace the "discard on any enricher move" rule** (S161) with `needs_rederive(from, to, table)` per derived table
   (§ 1.1); keep the rule for a `None` answer.
3. **Share one FASTA-backed proxy** across its re-derive runs (S157, S166, § 1.2), and one answer store per host or
   one per worker as its layout wants (§ 1.3).
4. **Recognise `repeat_grades.csv`** at its own bump (§ 1.0.1).

**Check**

5. Its ClinVar-scale re-derive, held for this release: with the store on, a first run asks each source's release
   before its first answer, and a re-run under unchanged releases asks nothing live (§ 1.3).
6. `manifest.panel_provenance` and `manifest.repeat_grades` are new optional keys it may surface (§ 1.0.1).

### just-dna-lite (reference consumer, the annotating engine)

**Change**

1. **Raise the floors together**, format first (§ 2).

**Check**

2. Modules with `studies.csv` that state `effect_direction`, or variants that state a register, move
   `content_signature`; modules that state neither compile to the same bytes (§ 1.9).
3. A renderer may show `conclusion_lay` or `conclusion_concise` where it has room for only one wording (§ 1.5).

### just-dna-pipelines (inside just-dna-lite)

**Check**

1. Its wrapped enricher CLI gains `fasta index`, `--sequence-uri` on more commands, `--no-answer-store`, and the
   `ipd_imgt_hla` lane under `cache rebuild` (§ 1.2–1.4).
2. A pipeline that ran enrichments in parallel against one cache base shares one answer store file (§ 1.3).

### just-module-creator (the MCP authoring plugin)

**Change**

1. **Carry `ClinVarDraftResult.panel_provenance`** into the spec its ClinVar draft writes (§ 1.5), as its own note on the
   preview asked.
2. **Teach the four optional additions** (§ 1.5): `panel_provenance:` in place of `panel:`'s three fields,
   `effect_direction`, the two registers, and that `repeat_grades.csv` is derived, never authored.

**Check**

3. Its `describe`/`requirements` surfaces pick the new fields up from the models; a hand-kept table of columns does not.

---

## 4. Known issues

What 0.10 ships with, known and not fixed. Each line names its item in [ROADMAP_0_11.md](ROADMAP_0_11.md);
[RM_TOC.md](RM_TOC.md) has its state. None returns a wrong answer; each withholds, warns too little, or costs time.

- **RM472** — the answer store keeps an anchored indel's raw REST record, so a replay on a host with no sequence
  service answers could-not-ask where the live run answered.
- **RM473** — a corrupt IPD-IMGT/HLA snapshot reads as present in `cache status`, `pull` and `prepare`; `enrich` then
  withholds the HLA check with a reason about the module.
- **RM474** — the genotype-mismatch check reads `conclusion` only, never the two registers.
- **RM475** — the HLA check reads `allele_function.csv` only; HLA names in `diplotypes.csv` and `haplotypes.csv` go
  unchecked. The record names the table it read.
- **RM476** — locks held across I/O in the answer store, the FASTA identity and the sequence proxy: latency, and one
  `SQLITE_BUSY` turns the store off for the rest of the run.
- **RM477** — `layout.atomic_writer` writes every sidecar 0600, so a second account on the host cannot read a shared
  FASTA's `.refget.json` and re-hashes it (about 155 s on GRCh38). The `.fai` is already fixed.
- **RM478** — the tag tests skip on a clone without tags; nothing yet turns that skip into a failure in CI.
- **RM479** — a FASTA removed in the middle of a run raises `FileNotFoundError` where the read should withhold.
- **RM480** — the FASTA identity cache is keyed on size and mtime, so an in-place edit under a restored mtime still reads
  as bound.
- **RM481** — one mirrored site can get both "is not filled" and "so both are filled as before", counted twice under
  `rsid_genotype_reads_as_two_events`; older than 0.10.
- **RM482** — the public-name walk sees classes and functions only; constants and type aliases are documented by hand
  (§ 1.8).
- **Carried, unchanged:** with the proxy set and Hugging Face off, gene lookups on clinpgx, cpic, drug_labels and civic
  answer could-not-ask (RM459, waits on the registry's S36, [INTEGRATION_0_9 § 4](INTEGRATION_0_9.md#4-known-issues));
  placement readers that bypass `usable_loci` (RM388, parked); the enricher does not say what compile will refuse
  (RM390, parked).
