---
name: write-module
description: >-
  Author a just-dna annotation module (format 0.5) end to end — choose the table kinds, draft from a
  source, curate what only a human can decide, enrich, cross-check, compile, sign. Use when creating
  or extending a module spec directory (module_spec.yaml + CSVs), when picking which table kind a
  finding belongs in, or when a validate/enrich/compile step reports something you do not recognise.
  Triggers: "write a module", "author a module", "add a gene/panel/variant", "draft from ClinVar",
  "draft from CPIC", "heteroplasmy", "star alleles", "diplotypes", "module_spec.yaml", "variants.csv",
  "why does my module not compile".
---

# Writing a just-dna module

**Read [`docs/AUTHORING.md`](../../../docs/AUTHORING.md) now, in full** (~230 lines). It is the
workflow — the commands, in order, with the reasoning. This file does not repeat it; what follows is
the *gotcha* list, the rules that are not discoverable from the command output and that have each
already cost someone real work.

## The order, and the one place deviating from it deadlocks

```
scaffold ──▶ draft ──▶ curate ──▶ enrich ──▶ check ──▶ compile ──▶ sign
             (if a          (only a human)
              source has it)
```

**Curate before you enrich.** A drafted row leaves `<<REPLACE>>` in the cells only a human can decide,
and that placeholder makes *every* loader refuse the file — `enrich` included. So you cannot "enrich
first to see the alleles". You do not need to: **the draft report prints the allele pair for each
stubbed row.** Curate from that.

## Read, as the task needs

| Read | When |
|---|---|
| [`docs/AUTHORING.md`](../../../docs/AUTHORING.md) | Always, first. The command order and what each step is for. |
| [`docs/AUTHORING_TABLES.md`](../../../docs/AUTHORING_TABLES.md) | Choosing which table kind a finding belongs in, or which axes must go in a key. |
| [`docs/AUTHORING_SYMPTOMS.md`](../../../docs/AUTHORING_SYMPTOMS.md) | Anything reports a message you do not recognise. Match on the quoted phrase. |
| [`docs/RM_TOC.md`](../../../docs/RM_TOC.md) | Checking whether a limitation you hit is already tracked, before working around it in data. |
| [`docs/CONSTITUTION.md`](../../../docs/CONSTITUTION.md) | Only if you are changing the **schema** rather than authoring against it. Read it in full yourself; never delegate it. |

`SCHEMAS.md` / `COMPILER.md` / `ENRICHER.md` are package references — do not re-derive the authoring
flow from them.

---

# Gotchas

## Which cells must be filled

- **`required` is not the whole story — there are three categories, and the middle one is invisible to
  a schema dump.** A **defaulted** column (`measure_kind`, `unresolved`) is not required *and* must
  not be left empty: an empty cell arrives as `None` rather than as the field's default, and fails on
  type. Trust `just-dna-compiler requirements <kind>`, which reports all three (`required` /
  `defaulted` / `optional`) plus the one-of rules a per-field flag cannot express (the "rsid **or**
  chrom+start" kind).
- **A generated stub cannot compile until you replace it.** `<<REPLACE>>` is rejected before type
  coercion, so an unreplaced placeholder in an `int` column reads as "unreplaced template placeholder
  in column start", not as a number-parsing error.

## Coordinates and identity

- **`start` is the 1-based VCF position. Never subtract one.** It is the number Ensembl, dbSNP,
  ClinVar and gnomAD all print. The reflex to "convert to 0-based" (from BED, or from VRS's own
  interbase model) is the single most expensive mistake available here, because **nothing offline
  catches it**: `validate` passes, `compile --strict` passes, the manifest says
  `fully_resolved: true`, and every `ga4gh:VA.…` id is minted and then reported *verified* — a
  content-addressed id is a correct digest of whatever it is handed, so it certifies the wrong locus
  happily. Only `enrich`, online, can see it.
- **Prefer the rsID and let `enrich` find the coordinate.** An rsid-only row cannot carry a coordinate
  mistake, and the resolution table it produces is the independent second value the cross-check needs.
  Author coordinates when you have a reason to (no rsID, or a non-GRCh38 module), not by default.
- **Identity is filled whole or not at all** — the rsID, else the complete `chrom`/`start`/`ref`/`alts`.
  A lone `alts` on a position-only row changes *which variant the row is*: it makes the key a VRS
  `ga4gh:VA.…` instead of `chrom:start:ref`.
- **A genotype is `C/C`, not `CC`.** `CC` parses as a single two-base allele. Sources (PharmGKB) write
  the unslashed form; disambiguate using the resolved ref/alt.
- **Off GRCh38, expect less and say so.** rsIDs resolve against GRCh38 only, so a `genome_build:
  GRCh37` module resolves nothing and mints no VRS ids; its keys are build-relative coordinates that
  will not join against gnomAD/ClinVar/ClinGen. Author coordinates rather than rsIDs there. This is
  RM15, not a defect.

## The checks, and the two ways to defeat them by accident

- **Never fill a cell from the same source that checks it.** `rsid`, `chrom`, `start`, `ref`, `alts`,
  `clin_sig`, `doi`, `acmg_sf`, `function_status`, `evidence_level`, `p_value_num` are
  *redundancy-bearing*: a check compares your independently-authored value against a source, so
  filling it from that source makes the check vacuous. `hint` shows you the value and refuses to apply
  it (`applied=false`) — that refusal is the feature.
- **Never author both sides of a redundancy check.** Hand-writing `resolution.csv` *and* the
  coordinates in `variants.csv` makes `_verify` compare your convention against itself, and it agrees
  perfectly. Validate-by-redundancy assumes independence. Let `enrich` produce the sidecar.
- **`--strict` means reproducible, not correct.** It refuses when resolution left something it could
  not reproduce. It has no opinion on whether your coordinates name the variant you meant, and cannot
  have one — the compiler never fetches (Principle 2).
- **A sidecar you already have is authoritative and merged, never clobbered.** To regenerate
  `resolution.csv` / `frequencies.csv` / `gene_metrics.csv` after changing the spec you must **delete
  the file first**, or stale rows persist silently. Moving it aside and re-enriching is also the only
  way to ask whether an injected table still agrees with the sources.
- **Read "ref mismatch" as possibly being about `start`.** The check reports a coordinate shift when
  it can establish one; when it cannot (both neighbouring bases match your `ref`) it says only that
  the ref disagrees. If the same run reported a shift group, the residue almost certainly belongs to
  it. It is reported, never repaired.

## Withhold rather than assert

The house algebra is **three-valued: true / false / unknown**, and `None` is never `False`.

- **A blank cell means "not stated" and is always legitimate.** Do not write `false` to silence a
  reminder.
- **Every binning table has an `unresolved` sentinel** a consumer selects when the measurement is
  absent. Never route a missing measurement to the lowest bin.
- **Set `requires_callable=true` (with `callable_from`)** wherever the *absence* of a variant is the
  informative call: a no-call is not a reference call.
- **On licensing, unknown terms are undetermined, never permitted** — `share_alike`/`commercial_use`
  left blank do not mean allowed.

## Binning bounds

- **`measure_max` is inclusive on every kind.** A bounded domain's top value (allele fraction `1.0` is
  homoplasmy, and real) has to be reachable.
- **Whether adjacent bins may share an endpoint depends on the kind, and the two cases are opposite.**
  - **Dense — `allele_fraction`, `prs_percentile`: bounds must touch**, e.g. `0.0–0.1` then
    `0.1–0.3`. A shared endpoint is a *boundary*, not an overlap, and the higher bin owns it (lookup
    selects the row with the greatest `measure_min ≤ x`). A hole between bins warns, because on a
    continuous measure it can be arbitrarily small.
  - **Integer — `repeat_count`, `copy_number`: bounds must NOT touch**, e.g. `[27,35]` then
    `[36,39]`. Adjacent integer bins are already contiguous, so a shared endpoint is a real overlap —
    both bins claim that integer — and it is refused.
  - **`activity_score` is in neither set.** It is a consumer-summed value on a coarse grid, so
    interior holes are not meaningful (no gap warning) and bins do not touch.
- **Two bins sharing a *lower* bound refuse on every kind** — the boundary rule selects the greatest
  `measure_min ≤ x` and these two are the same, so there is nothing to order. Reachable as a sharp
  `[0.1, 0.1]` beside a range starting at `0.1`.

## PGx and star alleles

- **A clinical annotation's key is `(variant_key, drug, genotype, phenotype_category, annotation_id)`**
  — not the bare triple. One variant+drug carries several distinct annotations (rs4149056+simvastatin
  is Metabolism/PK 1A, Efficacy 3 *and* Toxicity 1A).
- **Annotations are per genotype, and can oppose each other** — rs4149056/simvastatin is "decreased"
  for CC/CT and "increased" for TT. Genotype is in the key for that reason.
- **CPIC recommendations are keyed by (phenotype, drug, *population*)**, and the populations disagree.
  `draft --drug` **refuses and lists the choices** when several exist rather than picking one, because
  defaulting would assert a clinical context you never chose.
- **`recommendation_strength` is CPIC's; `evidence_level` is PharmGKB's.** Different axes — fill only
  the one your source states.
- **A large star-allele gene needs `draft --allele`.** *n* alleles is *n(n+1)/2* diplotypes; unfiltered
  CYP2D6 is 16,290 rows, 73% `Indeterminate`. Your real bound is the allele set your caller emits.
  `*1` is always kept (it is defined by carrying no variants).
- **A star allele can be *used* without being *defined*.** If `haplotypes.csv` never defines an allele
  that `diplotypes.csv` names, a caller can never emit it and every row about it is dead. Warned, not
  blocked — leaning on an external caller's definitions is legitimate.
- **CPIC activity scores are inequality strings (`"≥3.0"`), not numbers**, so they do not drop into
  numeric bin bounds; and CPIC's `n/a` means *not scored* — an absence, so leave the cell blank.
- **A PGx module carries no `variants.csv`, and that is correct.** One CSV = one concern; never add an
  empty table to keep another company.

## Licensing

- **Every PGx upstream (ClinPGx, CPIC, PharmVar) is CC BY-SA *plus a no-sale clause*.** None is
  sellable. Do not read a bare "CC BY-SA" as permission. (`api.pharmgkb.org` was retired 2026-07-20;
  the successor is `api.clinpgx.org`.)
- **Pass `--use unstated | non-commercial | commercial`** to anything that copies rows out of a source
  (`draft`, `draft-panel`, `draft-clinpgx`, `dosage`, `pgx`, `clinpgx build/check`). A forbidding
  source is *skipped* on `unstated` and *refused* on `commercial`, at acquisition.
- **`sources.csv` is the only thing the compile gate reads.** A source you copied from by hand is
  invisible to it — write the row yourself, or the restriction simply vanishes from the module.
- **The CLI spelling and the column value differ.** `--use` accepts `non-commercial`, but the
  `declared_use` *column* takes the vocabulary member `non_commercial` (underscore). The flag
  normalizes; a cell you type by hand does not.
- **A PharmVar API key is personal** (ToS §2) — never bake one into a module, fixture, or snapshot.

## Drafting

- **Drafting appends; it never rewrites a cell.** A row whose key already exists is reported
  (`already_present` / `differs`), never overwritten. Re-run per gene as the module grows; `--dry-run`
  first.
- **Read the warnings — they are the interesting output.** Skipped rows, aggregated counts, and the
  allele pairs you need in order to write a `genotype`.
- **Sources publish alleles, not genotypes.** Whether one copy is informative follows from the
  condition's inheritance mode, which is why `genotype` is stubbed for you to decide. Same for
  `weight` / `direction` / `effect_size` (your model of the finding), `trait_efo_id` (mapping free
  text to an ontology is inference) and `conclusion` (what the module *says* — keep it hedged where
  the biology is).

## Sex chromosomes and the PAR

- **A pseudoautosomal variant is recorded once, on X**, because that is the spelling every annotation
  source uses and a standard GRCh38 analysis set hard-masks the Y PAR. Pass `--keep-par-twin` to
  `enrich` only if your reference is unmasked.
- **`chrom=Y` is not "never diploid": PAR1 and PAR2 are diploid in every karyotype.** The verdict is
  **per locus**, not per gene or per module — `XG` and `SPRY3` each straddle a boundary.

## Module structure

- **One CSV = one concern.** Compose from optional table kinds; never add a foreign domain's columns
  to every row. The SNP core (`variants.csv` + `studies.csv`) stays minimal.
- **A value every row shares belongs in `module_spec.yaml`'s `defaults:`** (`curator`, `method`). Both
  spellings are the same content to the signature, but the defaults block is the tidier module.
- **Authored row order is preserved** through compile → reverse → recompile and is load-bearing for
  `artifact.digest`. Drafted rows land at the end unless you group them.

## Known gaps — do not work around these in your data

Check [`docs/RM_TOC.md`](../../../docs/RM_TOC.md) before inventing a workaround; if it is listed, the
right move is to leave the data honest and note the limitation.

- **RM5** — symbolic / structural alleles (`<DEL>`, 5-HTTLPR, ClinPGx `del`/`ins`, CPIC's `x≥3`) are
  outside the `^[ACGT]+$` grammar. The PGx passes skip such rows rather than coerce them.
- **RM15** — multi-build support. GRCh38 is the only assembly with a refget table, so identity minting
  and rsID resolution are GRCh38-only.
