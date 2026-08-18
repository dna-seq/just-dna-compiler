# Integrating 0.6 — what changed against the 0.5 surfaces

For the repos that consume this one: **just-dna-pipelines**, **just-dna-lite**,
**just-dna-marketplace**, **just-dna-agents**. It answers one question — *given a working 0.5
integration, what do I have to check, and what do I have to change?*

The baseline throughout is the **published `v0.5.4` tag**, not `main`. That distinction matters:
`main` already carries eleven commits of early 0.6 work (`manifest.readme`, `manifest.derived`, the
Constitution's cadence amendment), so a delta taken against `main` under-reports two manifest fields
that a downstream lib pinned to PyPI has never seen. Everything below is measured against what is
actually installable today.

**Status: 0.6.0 is cut and tagged `v0.6.0`** (2026-08-17, all three packages). This paragraph read
*"0.6 is uncut"* until then, which is the state the rest of the document was written in — so where a
section still says "in the tree", read it as shipped in `v0.6.0`. **Tagged is not published**: whether
it is installable from PyPI is a separate step and the maintainer's call, so check before promising a
field to anyone. That distinction is S34's, and it is the standing rule for every claim in this
document — *answered* and *in the tree* and *cut* and *installable* are four different states.

**Eight defects were found in 0.6.0 and are fixed in `v0.6.1`** — RM93–RM100, filed 2026-08-18 from a
pass that regenerated the tier references from source and read them against the shipped documents.
**Take 0.6.1, not 0.6.0**, and read [§ 7](#7-what-060-got-wrong-and-061-fixed) if you are pinned to
0.6.0 for any reason: four of the eight change what you should expect from a surface this document
told you to adopt. None of them changes a schema surface, so nothing in the delta below moves — the
one thing 0.6.1 *adds* is that `authoring_reference()`, `describe`, `requirements` and
`json_schemas()` now render **28 models rather than 23** (RM96), the five machine-written sidecar row
models that were outside the registry. Additive, and worth knowing if you snapshot that output.

**0.6.1 also closes RM88 and puts one ask to you.** `upload` now refuses to overwrite
`data/<name>/v<version>/` with a different artifact unless `--force`. Beside it, § 2.8 carries the one
change in this document we cannot make on our side: **decide what a module contains from
`manifest.artifact.files`, not from what is in the directory**, because the publisher never removes a
file and the discovery path fetches no manifest.

---

## 1. The headline: nothing you have breaks

Measured, not asserted — the 0.6 compiler was run over the eleven `v0.5.4` reference example specs,
byte-for-byte unmodified, and the resulting manifests compared field by field against the ones
`v0.5.4` produces from the same inputs:

| | result |
| --- | --- |
| Specs that still compile | **11 / 11** — no refusals, no new errors |
| `content_signature` moved | **0 / 11** |
| `sources.signature` moved | **0 / 11** |
| `resolution_signature` moved | **0 / 11** |
| `artifact.digest` moved | **11 / 11** |
| `schema_version` | unchanged, `"1.0"` |
| Fields removed, retyped, or promoted to required | **none** |

That shape is exactly what Principle 3 promises for a minor: new optional and stamped columns move
the *byte* identity and leave the *content* identity alone. Principle 4 already scopes byte
reproducibility to a fixed `compiler_version`, so a moved `artifact.digest` across a compiler
upgrade is the documented behaviour rather than a surprise.

Both directions of the manifest were also checked against the real files:

- A **`v0.5.4` client parses all sixteen 0.6 manifests** without error.
- A **0.6 client parses all eleven `v0.5.4` manifests** without error.
- `weights.parquet` reads in both directions (37 columns at 0.5.4, 39 at 0.6), and so does
  `studies.parquet` (19 → 20).

So a mixed deployment — an old reader against a new artifact, or the reverse — does not fault. What
an old reader does *not* get is the new information; see §3.

### The one thing you must re-pin

**Any stored `artifact.digest` from a 0.5.4 compile will not reproduce under 0.6.** If you cache
digests, gate on them, or compare a recompile against a stored value, recompile and re-pin at the
version boundary. If you key on `content_signature` — the authored-content identity — **no action**:
it did not move anywhere.

### Two checks can newly refuse an *author's* spec

Neither fired on the corpus, but both are real tightenings and both are fixes:

- **RM50 — a PMC id is refused by name.** `PMC 3110566` used to be accepted as PMID 3110566, a real
  id for an unrelated article. A cell that compiled before may refuse now.
- **RM48 — a wrong-build coordinate is an error in both modes.** A position past its contig's end, or
  a contig only the other assembly names. It is arithmetic rather than judgement, so it deliberately
  does not follow the mode ladder and `--strict` is not the switch.

These matter to **just-dna-pipelines**, which compiles other people's specs: a spec that passed CI at
0.5.4 can fail at 0.6, and that is the intended outcome.

---

## 2. The surface delta, by layer

### 2.1 `manifest.json`

Seven new top-level blocks, all optional, all absent-means-nothing-was-said:

| field | type | what it is |
| --- | --- | --- |
| `verification` | block or absent | what was checked, by whom, and whether the module was **closed**. Every field inside is marked untrusted. Absent reads as *says nothing*, never as *passed*. |
| `gene_validity` | block or absent | the ClinGen/GenCC gene–disease validity fact block (RM24) |
| `clinical_assertions` | block or absent | the ClinVar clinical-assertion fact block (RM25) |
| `readme` | entry or absent | the module's prose, attested so it can travel (S25) |
| `derived` | mapping or absent | relative paths of machine-written sidecars, for a `derived/`-split tree (RM49). Transport-only. |
| `gwas_effects` | block or absent | the GWAS Catalog effect-size fact block (RM90). **Read `units` and `without_effect_allele` before using any of it** — see below. |
| `weighting` | block or absent | what the module's authored `weight` column *means*: `scale`, `method`, `note`, all free text (RM92). Absent means the module has not said, which is **not** the same as saying its weights are comparable. |

`readme` and `derived` are on `main` already but are **not** in `v0.5.4` — if your integration is
pinned to PyPI, treat them as new too.

Five new counters under `manifest.compilation`, all `int | None`:

| field | what it counts |
| --- | --- |
| `resolution_subjects` | the denominator `fully_resolved` quantifies over, taken **after** rsID expansion (RM44) |
| `positional_rows` / `positional_rows_placed` | how much of the PGx/positional side actually joins to a VCF. Complete is `placed == rows` — parts, not a ratio (S31) |
| `expanded_keys` / `expanded_rows` | the one-to-many rsID expansion, as two numbers (S33) |

**`None` is load-bearing on all five and is not `0`.** `0` is a real answer ("this module has no
positional rows"); `None` means *this compiler did not count*, which is what every pre-0.6 manifest
honestly is. It is how you tell the eras apart without probing parquet. Do not coalesce it.

**`gwas_effects` publishes two facets you should gate on, not just count.** `units` is the set of
`effect_unit` values present: more than one member means those betas are on different scales and must
not be pooled. Measured on a real module — `hfe_hemochromatosis`, rs1800562 — that set has **12
members** across 62 traits, of which `SD units`/`SD`/`s.d.` are three spellings of one thing and
`g/dL`/`g/dl` differ only in case, while 138 of the rows carry the Catalog's uninformative `unit`.
`without_effect_allele` counts the associations the Catalog published without establishing which
allele carries the effect (it writes `rs4149056-?`): **42 of 195** there. Those rows are real evidence
and **cannot be used as a weight in any direction**. They are counted rather than filtered precisely
so that neither silently dropping them nor silently keeping them is something you can do by accident.

**`weighting` is the answer to "can I combine two modules' weights".** It exists because a consumer
reported that authored weights "construct nonsense" across a corpus, and the artifact had no way to
say so. Treat an absent block as *unknown*, and unknown as *do not aggregate across modules*.

Two consequences worth acting on:

- **`fully_resolved: true` beside `resolution_subjects: 0` is vacuously true** — it is `all()` over an
  empty list. Five of the eleven 0.5-era examples are in that state. If you badge trust on
  `resolution_mode == "strict" or fully_resolved`, read the denominator beside it. That trust rule's
  reader is a **catalog**, not a general consumer — the docs said "a consumer" and that was wrong.
- **`UNJOINABLE_PHRASE` and its substring-matching workaround stay.** Already-published artifacts
  carry neither new field, so the sentence is still the only signal on them. Keep the fallback; add
  the fields as the preferred path.

Nothing was removed and `required` is unchanged in both directions.

### 2.2 Parquet columns

Additive everywhere. The two that change a **join**:

- **`weights.parquet` gains `locus_index` and `locus_count`** (RM87). An rsID resolving onto N loci
  becomes K×N rows, and until now an expanded row was indistinguishable from an authored one — a
  consumer produced 3,762 false findings from exactly that. `locus_count` defaults to **`1`**, not
  `0`, so **`locus_count > 1` is a predicate you can apply holding a single row**. Both are
  `exclude=True`, so no `content_signature` moves. On a pre-0.6 artifact the columns are absent;
  `reverse` prefers the stored column and keeps the encounter-order recompute for older artifacts.
- **`annotations.parquet` gains `genotype`** (RM80/S29) — the column that distinguishes its rows, which
  was in no column. `annotations.parquet` now carries **and keys on** `genotype`. If you join
  annotations without it, you are matching a larger set than you mean to.

The rest, by row model:

| model / parquet | new columns |
| --- | --- |
| `VariantRow` → `weights` | `locus_index`, `locus_count` |
| `HaplotypeRow`, `PharmVariantRow` | `alts`, `authored_ident`, `variant_key` |
| `HeteroplasmyRow` | `authored_ident`, `variant_key`, `measure_tiling`, `pmid`, `source_element` |
| `MeasureBinRow`, `RepeatAlleleRow`, `ActivityPhenotypeRow` | `measure_tiling`, `pmid`, `source_element` |
| `CopyNumberRow` | `measure_tiling`, `modifier_copy_number`, `pmid`, `source_element` |
| `LiteratureRow` | `license`, `commercial_use`, `share_alike`, `redistribution`, `doi_checked` |
| `StudyRow` → `studies` | `effect_allele` (RM91) |
| `SourceRow` | `draft_digest` |

**`studies.parquet` gains `effect_allele`** (RM91), and it matters for the same reason the column on
`weights.parquet` does: `effect_size` is stated *relative to* an allele, and until 0.6 a study row
named none. If you read `StudyRow.effect_size` today you are reading a magnitude whose sign you cannot
interpret; on a pre-0.6 artifact the column is absent, and on a 0.6 one it may still be null, which
means the study did not state one — **not** that the reference allele is implied.

Three new parquets: **`gene_validity.parquet`**, **`clinical_assertions.parquet`** and
**`gwas_effects.parquet`** (RM90). All are inside `artifact.digest` — a module carrying them has a
different artifact identity, correctly — and all sit in `ARTIFACT_PARQUETS`, so a publisher or
verifier deriving its file list from that constant picks them up with no edit.

`resolution.csv` still gets **no parquet**, deliberately. That is the first consequence of the 0.6
charter amendment and it is written into SCHEMAS.md because "publish it as a parquet" is the first
repair anyone proposes.

### 2.3 Files in a spec directory

| change | detail |
| --- | --- |
| `licensing.csv` | the preferred spelling of the licence-terms sidecar. **`sources.csv` is deprecated in 0.6 and removed at 1.0** — warn-only, reads exactly as before (RM51). |
| `derived/` subdirectory | **tolerated** on input for machine-written sidecars — never required, never canonical. `reverse_module` still emits a flat tree (RM49). |
| `verification.json` | new derived file: the check records and the closure. |
| `gene_validity.csv`, `clinical_assertions.csv` | new derived fact tables. |
| `gwas_effects.csv` | new derived fact table (RM90) — GWAS Catalog effect sizes, written by the enricher. |

The rename stops at the file. **`sources.parquet` and `manifest.sources` keep their names for the
whole 0.x tail** — both are inside the digest or are published keys, and renaming either breaks a
reader. So the chain reads `licensing.csv` → `sources.parquet` → `manifest.sources`. That is a real
legibility regression and it is deliberate; a test pins it so a well-meaning follow-up cannot
"finish" the rename into a published key. **Do not rename anything on your side to match.**

Writing rule, shared by both changes: **write to the file you read**, and **both spellings present is
an error naming both paths** — never a merge, never newest-wins.

### 2.4 Python API

New public symbols worth knowing:

| symbol | tier | why you care |
| --- | --- | --- |
| `just_dna_format.alleles.split_genotype` | format | the **one** definition of the genotype split. A validated cell in, alleles in **authored order** out — never sorted. There were three private copies; a consumer re-derived the rule from prose and got it wrong twice in opposite directions. Use this instead of your own (S30). |
| `just_dna_compiler.compiler.ARTIFACT_PARQUETS` | compiler | every parquet the artifact may contain. Was private `_OUTPUT_FILES`. |
| `just_dna_compiler.compiler.LEAD_PARQUETS` | compiler | `weights` plus the nine 0.4 families — what discovery actually probes. |
| `just_dna_format.layout` | format | the sidecar names, the `derived/` constant, and one resolver. Pure `pathlib`. Four parties must agree on this layout (compiler reads, enricher writes, publisher uploads, registry re-splits) and every past disagreement was silent. |
| `just_dna_format.verification` | format | `close`, `attest`, `merge_records`, `module_binding`, `verification_block`. |
| `just_dna_format.integrity.newline_normalized_file_entry` | format | the binding's entry builder (see §2.7). |
| `just_dna_format.gwas.GwasEffectRow` | format | one published GWAS association: magnitude, **its unit**, the allele it is relative to, the trait and the study (RM90). |
| `just_dna_format.integrity.gwas_effect_signature` | format | the fact-hash for that table. `effect_unit` is **inside** it; the churning `trait` label is not. |
| `just_dna_format.manifest.Weighting` / `GwasEffects` | format | the two new manifest blocks (RM92 / RM90). |

Also on the format tier: `SYMBOLIC_ALLELE_TYPES`, `is_symbolic_allele`, `parse_symbolic_allele`,
`is_unobservable_allele`, `MISSING_ALLELE`, `UNOBSERVABLE_ALLELE`, `GENOTYPE_SEPARATORS`,
`vocab.match_vocab`, `VALID_VERIFICATION_CHECKS`, `VALID_GENE_VALIDITY`, `VALID_INHERITANCE_MODE`,
and the VCF pointer helpers (`split_field_pointer`, `vcf_field_number`, `is_multi_valued_number`).

Two vocabulary notes for 0.6's last batch. **`vocab.VALID_EFFECT_DIRECTIONS` (`{increase, decrease}`)
is not `VALID_DIRECTIONS`** — it states which way an effect allele moves the *measured trait*, while
`VariantRow.direction` states a clinical judgement (`protective|risk|neutral|unknown`). Increasing HDL
and increasing LDL are both `increase`; if you map one onto the other you will invert half your
conclusions. And **`vocab.VALID_SOURCE_LAYERS` gains `gwas_effect`** — if you validate layers against a
hard-coded set, add it.

`RECOMMENDED_EFFECT_MEASURES` **moved from `spec` to `vocab`** so a fact-table module could bind it
without importing the authored-DSL module. `spec` re-exports it, so `from just_dna_format.spec import
RECOMMENDED_EFFECT_MEASURES` still works and no importer had to change.

**One trap in an existing signature.** `verify_manifest`'s `require_marketplace` **defaults to `True`,
the marketplace policy** — so a naive call rejects every locally-compiled module, ours included, since
the reference compiler leaves `compiled_by` null by design. It is a fork, not an optional step: one
policy per install route. The guarantee that is actually load-bearing is the pinned `public_key`.

### 2.5 CLI

Five new commands. No flag was removed or retyped; the only new flag on an existing command is
`just-dna-enricher draft-panel --download/--no-download`.

| command | what it does |
| --- | --- |
| `just-dna-compiler close` | writes `VerificationDoc.closure` — a human declaring the module final. Authoring now has an end (RM73). |
| `just-dna-enricher gene-validity` | drafts `gene_validity.csv` from ClinGen / GenCC |
| `just-dna-enricher assertions` | drafts `clinical_assertions.csv` from ClinVar |
| `just-dna-enricher gwas` | fills `gwas_effects.csv` from the GWAS Catalog REST API (RM90). It **does not fill `weight`** — that is the point of it, not a limitation. `--no-study-facts` drops the per-association `_links` follows: the budget is `1 + 2N` per variant and was **measured at 382 requests for one real module**, so this is worth knowing before you script it. |
| `just-dna-enricher hint recover` | which rs-number GRCh37 dbSNP records at an hg19/GRCh37 coordinate — the diagnostic beside RM48's refusal. Reports; never fills. |

**`check-identifiers` and `check-acmg` changed their promise.** They used to say "Writes nothing".
They now record that the question was put — `gene_symbol_currency`, `trait_currency`,
`gene_locus_agreement` and `acmg_secondary_findings` — **unconditionally, with no flag**, because an
optional record is ambiguous between "not run" and "ran without the flag". They still write no
authored cell. If you scripted these expecting a read-only tree, that assumption is now false.
Relatedly, `merge_records` no longer lets a `skipped` record displace a `ran` one.

### 2.6 Warning texts, which are an API

`manifest.compilation.warnings` is a surface consumers parse (RM44), so the phrases are pinned
constants. New in 0.6:

`FRACTIONAL_MEASURE_PHRASE`, `SPANNING_MEASUREMENT_PHRASE`, `DEPRECATED_MODIFIER_PHRASE`,
`QUAL_INVERSION_PHRASE`, `MISSING_ALLELE_PHRASE`, `UNCLOSED_PHRASE`.

Two new findings in 0.6's last batch carry no pinned constant yet, so match them loosely or not at all:
a study row whose `effect_allele` is not an allele its locus can host (RM91 — *"effect_allele … is not
among the resolved alleles at this locus"*, warning in `best_effort`, **error in `strict`**), and an
over-broad GWAS sidecar (*"gwas_effects.csv carries associations for N identity(ies) no variant in this
module carries"*, warning in both modes). The first is the one that can newly refuse a `strict` compile
of a spec that used to pass — though only if the module both authors a study `effect_allele` and
resolves the locus, so nothing in the corpus fires it.

Import the constant rather than copying the sentence. `FRACTIONAL_MEASURE_PHRASE` is byte-identical
to its earlier 0.6 development spelling on purpose, but the warning that carries it went from
unconditional to **conditional** — so its *frequency* changes even though its text does not.

### 2.7 Line endings no longer count as an edit

The attestation binding now normalizes `\r\n` → `\n` before hashing (RM82), through a **separate**
entry builder. An author whose editor or `core.autocrlf` rewrote line endings used to un-close a
module without touching a cell.

**`manifest.inputs[]` and `artifact.digest` deliberately still follow raw bytes** — they answer a
different question. Do not "fix" the asymmetry. The trap worth knowing if you reimplement any of
this: `size` is inside the hashed listing, so normalizing only the hashed bytes and reporting
`stat().st_size` is a no-op that looks like a fix.

### 2.8 The publisher path (marketplace / registry)

The publisher now writes **`data/<name>/v<version>/` nested inside the flat `data/<name>/`**, which
keeps meaning *latest* (RM84). The segment is `v<version>` verbatim. Enricher-only: no schema, no
digest, no signature.

Two things to plan for, and **one ask** — the third is the only thing in this document that needs a
change on your side that we cannot make on ours.

- **Nothing prunes the versioned copies.** The collection grows one artifact set per release. That is
  known and not being fixed here.
- **The versioned path now refuses to become a different release** (RM88, 0.6.1). `upload` reads the
  published `manifest.json` at `data/<name>/v<version>/` and compares `artifact.digest`; a different
  digest refuses unless `--force`. Identical bytes are **not** a collision, so re-running a publish
  after a failed second commit still works. The flat path is deliberately **not** guarded — it means
  *latest*, and overwriting it is what it is for. If the check itself cannot run, the publish proceeds
  with a warning: nothing established a collision, so nothing asserts one.
  Note that recompiling an unchanged spec under a newer compiler moves the digest too (P4), so it will
  trip the gate — correctly, since the versioned path really would come to hold different bytes.

#### The ask: read `artifact.files`, and treat what it does not name as not part of the module

**`upload_folder` adds and replaces; it never removes.** A recompile that stops emitting a table — a
module whose `studies.csv` was deleted, so `studies.parquet` is no longer produced — leaves the
previous release's file sitting at the path beside a manifest that does not attest it. So a republish
leaves a **union of two releases**, not a replacement, and it does this on the **flat path, every
time**, version bumped or not.

**The format's answer is that this does not matter, and we would like it to become true.**
`manifest.artifact.files` states which parquets *are* the module, `artifact.digest` is a Merkle root
over exactly those, and an unattested leftover is outside both — so a reader that starts from the
manifest never sees one, and verification passes because nothing was corrupted. On that reading the
leftover is an inert fossil.

**What stops it being true is the reader.** Recorded in
[MODULE_LIFECYCLE § 6.8](MODULE_LIFECYCLE.md#68-what-a-consumer-sees-when-v2-lands) and verified in the
reference consumer's tree rather than inferred: the discovery path adds *"no manifest fetch and no
digest check"*, `verify_manifest` *"has no call sites there"*, and the scan is `fs.ls` at one level
plus `fs.exists` on **named files**. On the registry path the fossil really is inert, because there is
a per-version audit and the manifest is read. On the discovery path nothing consults the list that
would make it inert, and a leftover parquet is indistinguishable from a live one.

**The concrete failure is a shape misreport, not corruption**, and it needs two things at once: a
module whose table set *shrank* between publishes, read over discovery. A SNP-core module re-authored
as a table-only PGx module keeps a fossil `weights.parquet`, so a probe for named files still finds a
SNP core — the old release's. Nothing is mis-hashed; the module is mis-*typed*.

**So the ask is: decide what a module contains from `manifest.artifact.files`, not from what is in the
directory.** That is one read, it is the list the digest is computed over, and it closes this for good
on every module including the ones already published.

**Why we are not fixing it here**, stated so the choice is auditable rather than implied: the publisher
*could* pass `delete_patterns` and make the flat path a replacement. It was considered and declined for
this release. It leaves already-published fossils untouched (only a republish would clean them), it
does nothing for a consumer that probes rather than reads, and it is one wildcard away from being
dangerous — HuggingFace filters delete patterns with `fnmatch`, whose `*` **crosses path separators**,
so a single `*.parquet` in the publisher's allowlist would delete every archived version's parquets in
one commit. The allowlist is literal basenames today and the archive is safe by that accident. A fix
whose safety rests on an accident, and which does not close the case anyway, is the wrong half of the
answer; the manifest read is the right half.

**And the reason to upgrade the publisher at all:** the 0.5 allowlist was hand-kept, and it was not
merely refusing table-only modules — it was **dropping the data of the ones it accepted**. Measured
over the sixteen reference examples: seven refused outright, and eight of the remaining nine
published a manifest attesting parquets that were never uploaded, so the published `artifact.digest`
could not be reproduced from what arrived. **Fifteen of sixteen wrong.** `sources.parquet` was in the
dropped set every time it existed — a module published that way arrives with no licence terms.
Nothing is known to have been published through it, so this is *would publish*, not *did*. After the
fix: **16 of 16 publish and all 16 digests verify**, and the allowlist is derived from
`ARTIFACT_PARQUETS` so a new table family reaches the publisher in the commit that adds it.

---

## 3. Per-consumer check / change lists

### just-dna-lite (reference consumer, the annotating engine)

**Change**

1. Adopt `locus_count > 1` to filter or label expanded rows. This is the fix for the 3,762 false
   findings; your own mitigation (withhold any locus spelled with more than one `ref`) **misses
   same-`ref` expansions**, and one is instantiated in `reference_examples/shox_par1/` via
   `enrich --keep-par-twin`.
2. Join `annotations.parquet` on `genotype`. Without it you match a larger set than you mean to.
3. Replace any local genotype-splitting with `just_dna_format.alleles.split_genotype`. Authored
   order, never sorted.
4. Read `manifest.sources` / `sources.parquet` for licence terms as before — but if you consumed
   anything published through the old uploader, re-fetch it; the licence table was being dropped and
   your report footer would render *"Not stated"*.
5. **Decide what a module contains from `manifest.artifact.files`, not from what is in the
   directory** — the ask in §2.8. The publisher's `upload_folder` never removes, so a module whose
   table set shrank between releases leaves the previous release's parquet at the path; on the
   discovery path, which fetches no manifest, that fossil is indistinguishable from a live table and
   the module reads as the wrong *kind*. One read of the list the digest is computed over closes it,
   including on modules already published, which no publisher-side fix can reach.

**Check**

6. Re-pin any stored `artifact.digest`. `content_signature` needs nothing.
7. Where you badge trust, read `resolution_subjects` beside `fully_resolved`, and keep the
   `UNJOINABLE_PHRASE` fallback for pre-0.6 artifacts.
8. `weights.parquet` splits the genotype while the 0.4 families keep the string. That is **still
   true** — unifying it is RM81 and it is 1.0, because it retypes a published column.
9. **If you aggregate `weight` across modules, stop, or gate it on `manifest.weighting`.** This is
   your own report (S36) coming back as a surface: `weight` has no unit column, every module means
   something different by it, and until 0.6 the artifact could not say so. An absent `weighting`
   block means *the module has not said* — read that as *do not combine*, not as *safe*.
10. **`gwas_effects.parquet` is not a drop-in replacement for a weight, and must not be pooled.**
   Join it per **trait** (`trait_efo_id`), and read `manifest.gwas_effects.units` first: one real
   variant carries 12 distinct units, three of which are spellings of one. Skip or label rows with a
   null `effect_allele` — 42 of 195 on that module — because an effect relative to an unknown allele
   has no direction you can apply to a genotype.
11. If you read `StudyRow.effect_size`, read `effect_allele` beside it now that it exists (RM91).
    Null still means the study did not state one, never that the reference allele is implied.

### just-dna-marketplace (catalog / storage / serving)

**Change**

1. Handle the nested `data/<name>/v<version>/` path. A nested versioned subdirectory does not disturb
   a flat-path scan by construction, but your catalog should now be able to *name* a version.
2. Plan for unbounded growth of versioned copies — nothing prunes them.
3. **Derive a module's file set from `manifest.artifact.files`** — the ask in §2.8, and it matters
   more here than anywhere: the publisher never removes, so a path can hold a union of two releases,
   and `revalidate` is the one place that enumerates published versions and could *say so*. A listing
   diffed against `artifact.files` is the only thing that finds a fossil on a module nobody
   republishes, which no publisher-side fix can reach.
4. Surface the `verification` block. **Absent means *says nothing*, never *passed*.** Every field
   inside is marked untrusted; the closure (`closed_at`, `closed_by`) is the only record that a human
   declared the module final.
5. `verify_manifest(require_marketplace=True)` is your policy — the default is yours, and it is
   correct for you and wrong for a local compile. Pin the `public_key`; that is the load-bearing part.

**Check**

6. Consume `positional_rows` / `positional_rows_placed` and `expanded_keys` / `expanded_rows` instead
   of substring-matching warning prose. Treat `None` as *not measured*, never as `0`.
7. `derived` records relative paths for a split tree, so `FileEntry.name` can carry `derived/…`. That
   block is documented transport-only.
8. **Three** new parquets may appear in an artifact's file list. Derive from `ARTIFACT_PARQUETS`
   rather than hand-keeping a list — that is precisely the defect that broke the publisher, and
   `gwas_effects.parquet` is the first one added since the fix, so it is also the test of it.
9. Two new manifest blocks to surface on a module page: `weighting` (what the module says its weights
   mean — free text, show it verbatim) and `gwas_effects`. If you render a facet from the latter,
   render `units` and `without_effect_allele`, not just `row_count`: they are what tell a reader
   whether those effects are usable, and a row count alone reads as confidence.

### just-dna-pipelines (compiler / discovery)

**Change**

1. Import `ARTIFACT_PARQUETS` / `LEAD_PARQUETS` instead of a local copy.
2. Move drafting output to `licensing.csv`; `sources.csv` still works and warns. Adopt the write-what-
   you-read rule, and treat both-present as an error.
3. Add `just-dna-compiler close` to the authoring flow if you drive it end to end. `validate` stays
   read-only; closure is its own phase.
4. Expect `check-identifiers` / `check-acmg` to write `verification.json` records now.

**Check**

5. Re-baseline any digest-comparison CI. Specs that passed at 0.5.4 can newly fail on RM50 (a PMC id
   in a `pmid` cell) and RM48 (a wrong-build coordinate — an error in **both** modes).
6. New optional authored columns are available but nothing forces them: `measure_tiling`, the bin-row
   `pmid`, `source_element`, symbolic alleles (`<DEL:1500>`), the unobservable allele `*`, `chrM`
   folding to `MT`, and namespaced VCF pointers (`INFO/DP` vs `FORMAT/DP`).

### just-dna-agents (MCP surface)

**Change**

1. `get_spec_format` / `list_colors` / `list_icons` drift further out of date this release. The
   replacements are `authoring_reference()` and the `RECOMMENDED_*` constants — the format tier now
   also exports `RECOMMENDED_SYMBOLIC_SUBTYPES`, and the vocabularies gained
   `VALID_VERIFICATION_CHECKS`, `VALID_GENE_VALIDITY`, `VALID_INHERITANCE_MODE`,
   `VALID_MEASURE_TILINGS` and `VALID_ELEMENT_RULES`.
2. Closed vocabularies now accept `-` where a `_` goes and **store the declared spelling** — so any
   member list you echo to a model should be the canonical one, and a hyphenated answer no longer
   fails.

**Check**

3. Any hand-maintained table of table kinds or columns: two derived tables and roughly two dozen
   columns are new.

---

## 4. Deprecated in 0.6, removed at 1.0

The cadence changed this release: **deprecate in a minor, remove at the next major** (0.6 → 1.0), and
a deprecation only lands in a minor where its audience can *act* on it. Nothing below stops working
in 0.x.

| deprecated | replacement |
| --- | --- |
| `sources.csv` (the file) | `licensing.csv` |
| `CopyNumberRow.modifier_cn` (`int`) | `modifier_copy_number` (`float`), read via `effective_modifier_copy_number` |
| the `panel:` block in `module_spec.yaml` | — |
| `ensembl_cache=` (deprecated since 0.5) | an injected `resolution.csv` |

Already visible as 1.0 work, so do not design around it: **RM81** — `weights.parquet` splits the
genotype while the 0.4 families keep the string, and unifying that retypes a published column. The
minor-legal parallel-column workaround was refused as two spellings of one value in one table.

A 1.0 also now carries an obligation it did not before: **a major ships its upgrade procedure**. A
removal whose upgrade path is left to the reader to work out is not ready to ship.

---

## 5. Readiness

**Gates, run on this branch today:**

| gate | result |
| --- | --- |
| `uv run pytest` | **2722 passed, 8 skipped, 0 failed** (2568 at the 0.6.0 cut) |
| `uv run ruff check` | clean |
| Open consumer inbox (`CONSUMER_SUGGESTIONS.md`) | empty — nothing owed (S36 answered and archived 2026-08-17) |
| Open roadmap items | **none in format scope.** RM88 closed in 0.6.1; RM7 carries a `## RMn` heading but is marked **not format scope** — a `just-dna-lite` contract, listed only so it is not mistaken for ours. |
| 0.5.4 spec corpus under the 0.6 compiler | 11 / 11 compile |
| Reference corpus | 16 / 16 compile (measured here); 16 / 16 publish with verifying digests (measured in the RM89 fix round) |
| Corpus movement from the S36 batch | `artifact.digest` moved on **10 / 16** — exactly the ten carrying a `studies.parquet`, since RM91 adds a column to it. `content_signature` moved on **0 / 16**. |

One test failed when this audit started — `test_doc_links` on a dead
`ROADMAP.md#rm89-…` anchor, left behind when RM89 shipped and moved to `ROADMAP_HISTORY.md` in the
branch's last commit. Fixed in `CONSUMER_SUGGESTIONS_HISTORY.md`; the count above is after that fix.

**CI does not gate this branch on push.** `.github/workflows/ci.yml` runs on `push` to `main`,
`pull_request`, and `workflow_dispatch` — so the 160 commits here have never been through the
matrix. That shape is deliberate (a full matrix on every branch push mostly measures work in
progress), but it means *merge via a PR, or dispatch the workflow against the branch first*. This
project has been bitten once already by a green-looking CI that never ran, on the 0.5.0 release.

**RM88 — closed in 0.6.1.** Republishing without bumping `version:` overwrote a versioned path with
different bytes. The policy was the whole of the delay, not the code: refuse-unless-`--force`, decided
2026-08-18, with the comparator (`artifact.digest`) already in the manifest. The half that is *not*
closed is the one nobody here can close — the publisher never removes a file, so a path can hold a
union of two releases, and only a reader that starts from `manifest.artifact.files` is immune. That is
the ask in § 2.8.

**Verdict: ready to cut**, with three caveats that are release-management rather than code.

1. Run CI against the branch before merging — it has not run.
2. Version numbers are already `0.6.0` in all three `pyproject.toml` files while `git tag` stops at
   `v0.5.4`. Anything published from here must be a real cut; wipe `dist/` before building, since
   `uv publish` uploads everything in it.
3. The three packages version independently in principle, but this release moves all three together —
   the format tier gains models, the compiler gains columns and a command, the enricher gains three
   drafting commands and the publisher fix. There is no partial cut available here.
4. **The S36 batch (RM90–RM92) landed after this document's first draft** and is folded in above. It
   moves `artifact.digest` on the ten examples carrying a `studies.parquet` — which is inside the
   "re-pin your digests" instruction already in §1, not a new obligation — and moves no
   `content_signature` anywhere.

---

## 6. What deliberately did not change

State these to anyone who asks, because each is a repair somebody has proposed:

- **`content_signature`, `sources.signature` and `resolution_signature` do not move** across the
  version boundary. Measured at 0/11.
- **`schema_version` stays `"1.0"`.** It moves at a major.
- **`sources.parquet` and `manifest.sources` keep their names** for the whole 0.x tail, even though
  the CSV was renamed.
- **`resolution.csv` gets no parquet.**
- **`manifest.inputs[]` and `artifact.digest` still hash raw bytes**, while the attestation binding
  normalizes newlines. Two questions, two answers.
- **The one-to-many rsID expansion stays.** Filtering it is refused; `locus_count` is the read-side
  answer instead. Note that `expanded_rows - expanded_keys` is **not** the unmatchable-row count —
  that needs a per-key authored-genotype number the manifest does not carry.
- **`fully_resolved` stays `bool`.** Consumers branch on it directly, so a `None` would be a breaking
  read for all of them; the denominator went beside it instead.
- **`UNJOINABLE_PHRASE` and its test stay.** Already-published artifacts carry neither new field.
- **No module-level "evaluate me against a callset that can express the reference genotype" claim.**
  Whether a hom-ref row can ever match is a property of the file a consumer brings — a variant-only
  VCF emits no such record, a gVCF and an array do — so that is the annotator's call, not this
  format's. Restoration and imputation stay consumer-side.

## 7. What 0.6.0 got wrong, and 0.6.1 fixed

Filed 2026-08-18 as RM93–RM100 and **all shipped in `v0.6.1` the same day**. Kept here rather than
deleted with the fix, because a consumer pinned to 0.6.0 still meets every one of them and the table
below is the only place that says what to do about it. **The action for everyone else is one line:
take 0.6.1.** No schema surface moved in either direction, so § 2's delta stands unchanged; what
moved is behaviour.

| Item | Who hits it on 0.6.0 | What to do if you are pinned to 0.6.0 |
| --- | --- | --- |
| [RM93](ROADMAP_HISTORY.md#rm93--two-checks-refuse-in-compile-and-report-nothing-in-validate) | anyone using `validate` as a pre-flight for `compile` | **The one to know.** `validate` is not currently a complete pre-flight: a module with `frequencies.csv`, or a table-only module with `studies.csv`, can pass `validate --strict` and then be refused by `compile --strict`. If your pipeline gates on `validate` and treats a later `compile` failure as an infrastructure error, it will misclassify these two. Gate on `compile` into a temporary directory if you need certainty today. |
| [RM94](ROADMAP_HISTORY.md#rm94--the-p-value-re-run-publishes-its-warning-twice-into-the-manifest) | anyone reading `manifest.compilation.warnings` | A `p_value`/`p_value_num` disagreement appears **twice**, byte-identical. If you count warnings or show them to a user, dedupe on the string — which is worth doing regardless, since the field has never promised uniqueness. |
| [RM97](ROADMAP_HISTORY.md#rm97--two-clients-leak-the-transport-exception-the-other-two-document-repairing) | anyone calling the enricher against gnomAD or dbSNP | A 5xx from either escapes as a raw `httpx.HTTPStatusError` rather than as this tier's own error type, so `except GnomadError` / `except EutilsError` does not hold it and a dbSNP 5xx can abort a run. Catch `httpx.HTTPError` alongside the tier's exceptions until this lands. |
| [RM98](ROADMAP_HISTORY.md#rm98--two-passes-record-an-absence-nobody-established-under---offline) | anyone running `enrich --offline` or `gene-metrics --offline` without a cache | The artifact records `status="not_found"` — a definite negative — where nothing was consulted. **Do not read a `not_found` from an offline run with no cache as evidence the source lacks the record.** With a cache present the behaviour is correct; it is the empty-cache case that fabricates. |
| [RM95](ROADMAP_HISTORY.md#rm95--a-canonicalized-vocabulary-value-is-discarded-so-the-slip-is-stored-and-then-rejected), [RM96](ROADMAP_HISTORY.md#rm96--the-registry-an-audit-iterates-was-missing-five-of-the-models) | module authors | `measure_kind=copy-number` is accepted by `MeasureBinRow` and rejected by its subclasses; write the underscore spelling. Two unenforced/misattributed model guards, neither of which lets bad data into a surface you read. |
| [RM99](ROADMAP_HISTORY.md#rm99--three-passes-bypass-the-sidecar-resolver-so-one-family-writes-to-two-places), [RM100](ROADMAP_HISTORY.md#rm100--five-enricher-surface-defects-with-no-common-cause) | registries serving a `derived/` layout; anyone invoking the enricher as a module | Three passes write their sidecar to the spec root regardless of layout, so an `enrich` run can leave one module with both. And use the `just-dna-enricher` entry point rather than `python -m just_dna_enricher.cli`, which is missing three commands. |

**What this list is not.** None of these is a regression against 0.5.4 — RM93's two checks and RM98's
offline paths behaved this way before 0.6 as well, and RM95's vocabulary slip has been there since the
column existed. They are recorded against 0.6 because that is when someone looked. The reason they are
in this document at all is § 1's promise that nothing you have breaks: that promise is about the
*surface*, and it holds, but a consumer planning an integration deserves the behavioural caveats in the
same place as the surface delta rather than one document over.
