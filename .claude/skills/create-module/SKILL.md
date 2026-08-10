---
name: create-module
description: >-
  Author a just-dna annotation module (format 0.5) end to end against the published packages —
  scaffold, draft from a source, curate what only a human can decide, enrich, cross-check, compile,
  sign. Self-contained: assumes only `pip install just-dna-enricher` and no checkout of the format
  repository. Use when creating or extending a module spec directory (module_spec.yaml + CSVs), when
  picking which table kind a finding belongs in, or when validate/enrich/compile reports something you
  do not recognise. Triggers: "write a module", "author a module", "create a just-dna module", "add a
  gene/panel/variant", "draft from ClinVar", "draft from CPIC", "heteroplasmy", "star alleles",
  "diplotypes", "module_spec.yaml", "variants.csv", "why does my module not compile".
---

# Creating a just-dna module

A module is a directory of human-authored CSVs plus `module_spec.yaml`, compiled into a parquet
artifact with a `manifest.json`. It carries **annotation only** — lookup tables mapping a genotype or a
measured quantity to a phenotype. It never holds a sample, a genotype under test, or a measured value:
the consumer supplies the measurement at query time.

This file is the whole guide. Two companions ship beside it:

| Read | When |
|---|---|
| `references/TABLES.md` | Choosing which table kind a finding belongs in, or which axes must go in a key. |
| `references/SYMPTOMS.md` | Anything reports a message you do not recognise. Match on the quoted phrase. |

## Install

```bash
pip install just-dna-enricher     # pulls just-dna-compiler and just-dna-format
```

Three packages in dependency tiers, and which one you need depends on what you are doing.

| Package | Gives you | Deps |
|---|---|---|
| `just-dna-format` | the schema models, integrity/signature helpers. No CLI. | pydantic, cryptography |
| `just-dna-compiler` | `just-dna-compiler` — validate, compile, reverse, sign, verify, scaffold, describe | + polars, pyyaml, typer |
| `just-dna-enricher` | `just-dna-enricher` — the **only** tier that fetches: resolution, drafting, cross-checks | + httpx, duckdb, huggingface-hub, ga4gh.vrs |

Python ≥ 3.13. Authoring a module wants the enricher; verifying a downloaded one needs only the
format tier.

**Never ask a schema question from memory — ask the tool.** Column lists, vocabularies and
requirements are generated from the live pydantic models, so `describe` / `requirements` /
`reference` cannot drift from what the compiler accepts. Nothing in this file restates them.

### Environment

A `.env` found by walking up from the working directory is loaded automatically.

| Variable | For |
|---|---|
| `JUST_DNA_PIPELINES_CACHE_DIR` | base for all three snapshot caches (else a platform cache dir) |
| `JUST_DNA_ENSEMBL_CACHE` / `JUST_DNA_CLINVAR_CACHE` / `JUST_DNA_GNOMAD_CONSTRAINT_CACHE` | override one cache path |
| `NCBI_API_KEY` | tightens PubMed/dbSNP pacing from 1/3 s to 1/10 s |
| `JUST_DNA_CONTACT_EMAIL` | sent to NCBI/Europe PMC as the polite-pool contact; omitted when unset |
| `PHARMVAR_API_KEY` | the PharmVar leg of `pgx`. **The key is personal under PharmVar's ToS §2 — never bake it into a module, fixture or snapshot.** |

## Answer three questions first — each one closes off wrong turns later

1. **What is each row's subject?** A variant? A diplotype pair? A measured quantity? That picks the
   table kind, and a module includes **only** the kinds it uses — never an empty `variants.csv` to keep
   another table company. → `references/TABLES.md`
2. **Are the coordinates GRCh38, and are they VCF positions?** Two separate questions, and the second
   has bitten harder. `start` is the **1-based VCF position** — the number Ensembl, dbSNP, ClinVar and
   gnomAD all show you. Paste it; never convert it. See *The mistake nothing offline can catch* below.
   On build: if `genome_build` is anything but GRCh38, the variant key falls back to a **build-relative
   coordinate** that will not join against gnomAD, ClinVar or ClinGen. The compiler warns; heed it.
3. **What is the source, and may you use it this way?** Every PGx upstream (ClinPGx, CPIC, PharmVar) is
   CC BY-SA **plus a no-sale clause**, so none is sellable — do not read a bare "CC BY-SA" as
   permission. Pass `--use unstated | non-commercial | commercial` to every command that copies rows
   out of a source; a forbidding source is *skipped* on `unstated` and *refused* on `commercial`, at
   acquisition. The terms land in `sources.csv`, which is the only thing the compile gate reads — so a
   source you copied from by hand is invisible to it, and you must add the row yourself.

## The order, and the one place deviating from it deadlocks

```
scaffold ──▶ draft ──▶ curate ──▶ enrich ──▶ check ──▶ compile ──▶ sign
             (if a          (only a human)
              source has it)
```

**Curate before you enrich.** A drafted row leaves `<<REPLACE>>` in the cells only a human can decide,
and that placeholder makes *every* loader refuse the file — `enrich` included. That is deliberate:
forward resolution is allele-aware, and a placeholder genotype would silently skip the allele filter on
exactly the one-to-many rsIDs that need it. So you cannot "enrich first to see the alleles".

You do not need to: **the draft report prints the allele pair for each stubbed row.** Curate from that.

## 1 — Start the spec

```bash
just-dna-compiler scaffold spec/ --kind variants.csv --kind studies.csv --name my_module
```

Re-runnable and never overwrites, so run it again with a different `--kind` to add a table later. Then
replace every `<<REPLACE>>` in `module_spec.yaml`, which comes out like this:

```yaml
schema_version: '1.0'
module:
  title: <<REPLACE>>          # required
  description: <<REPLACE>>    # required
  report_title: <<REPLACE>>   # required
  name: my_module             # required — lowercase, underscores, no spaces
  icon: database              # icon within icon_set
  icon_set: fomantic          # 'fomantic' or 'awesome'
  color: '#6435c9'
  # version: v2               # advisory human marker; the publishing version lives elsewhere
defaults:                     # optional; folded into every row before hashing
  curator: ai-module-creator
  method: literature-review
genome_build: GRCh38
# panel:                      # optional provenance for a module derived from a gene panel
#   source: clinvar
#   reference: '2026-06-27'
#   reference_sha256: 'sha256:…'
#   genes: [HFE]
#   significance: [pathogenic, likely_pathogenic]
# authorship: [...]           # optional per-version contributor entries (who/role)
# license: CC-BY-SA-4.0       # advisory declaration for the module as a whole
```

Learning a table you have not authored before:

```bash
just-dna-compiler requirements heteroplasmy.csv   # required / defaulted / optional, and any one-of rule
just-dna-compiler describe     heteroplasmy.csv   # full JSON: every column, its vocabulary, its pick-list
just-dna-compiler template     heteroplasmy.csv   # just the header (requirements go to stderr)
just-dna-compiler stub         heteroplasmy.csv --rows 3   # header plus placeholder rows
just-dna-compiler reference --summary             # every model at once
```

`requirements` prints all three categories, which is the point of it:

```
variants.csv
  always:    genotype, state, conclusion
  one of:    rsid
  one of:    chrom + start
  optional:  rsid, chrom, start, ref, alts, weight, …
```

**`required` is not the whole story — there are three categories, and the middle one is invisible to a
schema dump.** A **defaulted** column (`measure_kind`, `unresolved`) is not required *and* must not be
left empty: an empty cell arrives as `None` rather than as the field's default, and fails on type.
`requirements` reports it as `default: measure_kind=allele_fraction (never leave empty)`. It also
reports the one-of rules — the "rsid **or** chrom+start" kind — which no per-field flag can express.

**A generated stub cannot compile until you replace it.** `<<REPLACE>>` is rejected before type
coercion, so an unreplaced placeholder in an `int` column reads as "unreplaced template placeholder in
column start", not as a number-parsing error. That is the design: a half-filled table fails loudly on
exactly the rows still to do, rather than compiling into a module that asserts nothing.

## 2 — Draft from a source, if one publishes the table

```bash
just-dna-enricher draft-panel spec/ --gene HFE --use non-commercial            # ClinVar → variants.csv (+ studies.csv)
just-dna-enricher draft spec/ --gene CYP2C19 --drug clopidogrel --use non-commercial  # CPIC → the 3 PGx tables
just-dna-enricher draft-clinpgx spec/ --snapshot cp/ --drug simvastatin --use non-commercial
```

`draft-panel` downloads the published ClinVar snapshot when you have no local one; add `--snapshot cv/
--offline` to use one you built. Its `--min-review-stars` defaults to 2 (multiple submitters, no
conflicts) and `--max-citations 3` drafts study rows from ClinVar's literature links — which is what
makes the panel compilable, since a variant row needs grounding evidence.

`draft-clinpgx` is inject-only and downloads nothing: build the snapshot first with
`just-dna-enricher clinpgx build --out cp/ --use non-commercial`.

**Drafting appends and never rewrites a cell.** A row whose key already exists is reported
(`already_present` / `differs`), never overwritten — drift on existing rows is `pgx` / `clinpgx check`'s
job to report, not drafting's to fix. Re-run per gene as the module grows; `--dry-run` first.

**Read the warnings. They are the interesting output**: skipped rows, aggregated counts, and the allele
pairs you need for step 3. Two you will see on a real ClinVar panel and should not chase: *"N row(s) on
non-diploid contigs were written with a single-allele genotype"* is the provider filling a cell where
nothing was open to decide (those rows read as homoplasmic/hemizygous; a heteroplasmic *level* is a
different question and belongs in `heteroplasmy.csv`), and *"N ClinVar citation(s) skipped: the id
ClinVar filed under PubMed is not a PMID"* is a defect in the source, not in your module — a few hundred
of ClinVar's citation ids are nine digits where a PMID is eight. Both are counted rather than listed.

**Pin the release you drafted from.** If you write a `panel:` block naming the source and the snapshot
(`reference`, `reference_sha256` — the snapshot's `release.json` carries `clinvar_file_date` and
`source_sha256`), `enrich` recognises that its ClinVar cross-check would be comparing your `clin_sig`
against the file it came out of, skips it, and says so instead of reporting a zero it could not have
avoided. Leave the block out and the check runs as usual, which is what you want the moment a human has
touched those calls.

## 3 — Curate what only a human can decide

Nothing automated fills these, on purpose:

| Cell | Why it is yours |
|---|---|
| `genotype` | Sources publish **alleles, not genotypes**. Whether one copy is informative follows from the condition's inheritance mode. Write it from the allele pair the draft reported. **Except on a non-diploid contig**, where only one genotype is expressible and `draft-panel` therefore writes it for you: MT always, chrY outside the pseudoautosomal regions. Those rows arrive complete, and the draft says so in one line. |
| `state` (when stubbed) | The record is `uncertain_significance` or otherwise undecided, and no vocabulary member means "undecided" — `neutral` says benign, `risk` says a direction. If you can justify neither, drop the row rather than pick one to make the compile pass. |
| `weight`, `direction`, `effect_size` | Your model of the finding. ClinVar publishes no effect statistic. |
| `trait_efo_id` | A source's condition is free text / MedGen. Mapping it to an ontology is inference. |
| `conclusion` | What the module *says*. Keep it hedged where the biology is (penetrance, tissue, co-factors). |

To write a genotype you need the alleles. Ask, without writing anything:

```bash
just-dna-enricher hint variant --rsid rs1801133          # locus, ref, alts — and "[redundancy_bearing]"
just-dna-enricher hint variant --rsid rs334 --ambiguity  # warn when the answer is not unique
just-dna-enricher hint variant --chrom 1 --start 11796321 --ref G --alts A   # allele-exact by coordinate
just-dna-enricher hint citation --pmid 7647779           # does it exist, and what DOI does it carry
just-dna-enricher hint trait EFO_0004541                 # current | obsolete | absent
just-dna-enricher hint gene MTHFR                        # approved | retired | unknown
```

The offline half is on the compiler, and it takes rows rather than identifiers:

```bash
just-dna-compiler hint variants.csv --file variants.csv   # what is wrong, what the model rewrites,
                                                          # what is left to you. Writes nothing.
```

### Never fill a cell from the same source that checks it

`rsid`, `chrom`, `start`, `ref`, `alts`, `clin_sig`, `doi`, `acmg_sf`, `function_status`,
`evidence_level` and `p_value_num` are *redundancy-bearing*: a check compares your independently
authored value against a source, so filling it from that source makes the check vacuous. Worse, for an
rsid-only row the coordinate check does not run at all, so the row moves from honestly unverified to
apparently verified. `hint` shows you the value and refuses to apply it — tagged `[redundancy_bearing]`
in the plain output, `"applied": false` with a `refusal` and a `note` under `--json`. **That refusal is
the feature, not a limitation.**

### The mistake nothing offline can catch

Worth its own heading because it has happened at scale, to a careful author, on 3,038 variants across
four modules that all passed every gate.

**`start` is the 1-based VCF position. Copy it as printed; never subtract one.** The reflex to convert
to 0-based — from BED, or from VRS's own interbase model — is the single most expensive mistake
available here, because here is what does *not* happen: `validate` passes, `compile --strict` passes,
the manifest says `fully_resolved: true`, and every `ga4gh:VA.…` id is minted and then reported
**verified**. A content-addressed id is a correct digest of whatever it is handed, so it certifies the
wrong locus without hesitating. The module is internally consistent, reproducible, signed — and about
the wrong bases.

Two things conspire, and knowing them tells you what to do:

- **Never author both sides of a redundancy check.** Hand-writing `resolution.csv` *and* the
  coordinates in `variants.csv` makes the coordinate cross-check compare your convention against
  itself, and it agrees perfectly. Validate-by-redundancy only works because two *independently*
  produced values must agree. Let `enrich` produce the sidecar.
- **`--strict` means reproducible, not correct.** It refuses when resolution left something it could
  not reproduce. It has no opinion on whether your coordinates name the variant you meant, and cannot
  have one: the compiler never fetches, so it has no reference sequence to ask.

The only thing that catches it is `just-dna-enricher enrich`, online, which compares your `ref` against
the actual genome and reports **`ref mismatch: N row(s) — coordinate shifted 1 base…`**. Read that line
as being about `start`, not `ref`. It is a floor, not a total: it can only see rows where the
neighbouring base differs from your `ref`, roughly three in four.

**Prefer the rsID and let `enrich` find the coordinate.** An rsid-only row cannot carry a coordinate
mistake, and the resolution table it produces is the independent second value the cross-check needs.
Author coordinates when you have a reason to — no rsID, or a non-GRCh38 module — not by default.

If you already have a `resolution.csv` you did not generate and want to know whether it is right, move
it aside and re-enrich; comparing the two is the check, and no command does it for you.

## 4 — Enrich (the only tier that fetches)

```bash
just-dna-enricher enrich spec/                  # → resolution.csv (rsid ↔ coordinate, VRS ids, ref check)
just-dna-enricher enrich spec/ --offline        # caches only, zero egress
just-dna-enricher frequencies spec/             # → frequencies.csv   (gnomAD, paced ~6s/batch)
just-dna-enricher gene-metrics spec/            # → gene_metrics.csv  (gnomAD constraint)
just-dna-enricher dosage spec/                  # → ClinGen dosage rows onto gene_metrics.csv
just-dna-enricher literature spec/              # → literature.csv    (PMID/DOI/quotes)
```

`enrich` runs several links in order (Ensembl cache → ClinVar snapshot → live Ensembl → gnomAD), each
of which can be turned off (`--no-clinvar`, `--no-gnomad`), and folds in three checks you can also
disable: `--verify-ref`, `--verify-clinsig`, `--verify-rsids`. Snapshots are provisioned from
HuggingFace when absent and `--offline` is not set.

**An existing sidecar is authoritative and merged, never clobbered.** To regenerate `resolution.csv` /
`frequencies.csv` / `gene_metrics.csv` after changing the spec you must **delete the file first**, or
stale rows persist silently. Moving it aside and re-enriching is also the only way to ask whether an
injected table still agrees with the sources.

## 5 — Cross-check what you asserted against what the sources say

```bash
just-dna-enricher check-identifiers spec/            # trait CURIEs (OLS4) and gene symbols (HGNC) still current
just-dna-enricher check-acmg spec/ --sf-list acmg/   # acmg_sf vs the ACMG SF list
just-dna-enricher pgx spec/                          # function_status vs PharmVar and CPIC
just-dna-enricher clinpgx check spec/ --snapshot cp/ # pharm_variants.csv vs the ClinPGx snapshot
```

Every check **reports, never repairs** — rewriting an authored value would destroy the evidence of the
upstream mistake. `--strict` escalates a finding to a refusal; `--best-effort` (the default) warns and
carries on. Two deliberately never escalate — the `clin_sig` and allele-function cross-checks — because
failing would make the format arbitrate between expert panels.

`check-acmg` needs `--sf-list` to give a real answer: NCBI's page serves SF **v3.2** while ACMG has
published **v3.3**, so without a snapshot every disagreement comes back `unverifiable` rather than as a
finding. Build it once from ACMG's workbook — `just-dna-enricher acmg build <workbook.xlsx> --out
acmg/` — and the check also stops needing the network.

## 6 — Compile, verify, publish

```bash
just-dna-compiler validate spec/ --strict
just-dna-compiler compile  spec/ out/ --strict
just-dna-compiler keygen --out key.pem              # prints the public key `verify` pins
just-dna-compiler sign    out/ --private-key key.pem
just-dna-compiler verify  out/ --no-require-marketplace --public-key <base64>
```

`validate` refuses everything `compile` refuses that does not need resolved rows, so a green pre-flight
should mean a green compile. **Pass it the same mode as the compile you intend to run** — several checks
warn under `--best-effort` (the default) and refuse under `--strict`, so a modeless pre-flight answers
for the other compile. `--strict` means *reproducible artifact*: it refuses when resolution left
something it could not reproduce. It is orthogonal to `--use`, which is about who may use the data, and
it is not a statement that the module is *right*.

`enrich-and-compile spec/ out/` does steps 4 and 6 in one call (`--frequencies` / `--gene-metrics` to
add those passes).

`keygen` writes an unencrypted PKCS#8 key — it bootstraps a key, it is not a key-management system. A
real publishing key belongs in whatever secret store you already run.

If you changed the schema rather than the data, prove the round-trip:

```bash
just-dna-compiler reverse out/ rev/
just-dna-compiler signature spec/ && just-dna-compiler signature rev/
```

The two `content_signature` values must match — that is the fixed point the format guarantees. It holds
wherever you wrote a value: `curator` and `method` can live on the row or in `module_spec.yaml`'s
`defaults:`, and `reverse` re-emits them in the other place, so the signature folds `defaults:` into
each row before hashing and the two spellings are one content. Writing a shared value once under
`defaults:` is still the tidier module; it just no longer changes the identity.

---

# Gotchas

## Coordinates and identity

- **`start` is the 1-based VCF position. Never subtract one.** (Above, at length.)
- **Identity is filled whole or not at all** — the rsID, else the complete `chrom`/`start`/`ref`/`alts`.
  A lone `alts` on a position-only row changes *which variant the row is*: it makes the key a VRS
  `ga4gh:VA.…` id instead of `chrom:start:ref`.
- **An rsID row's `variant_key` stays the rsID — VRS ids are not the key.** The key is the rsID when
  you wrote one, the `ga4gh:VA.…` id only for a coordinate-authored substitution, and the coordinate
  otherwise. Enrichment never re-keys a row. The VRS ids you are looking for are in `resolution.csv`'s
  `vrs_id`, **one per ALT, positionally aligned with `alts`** — an empty member there is a site whose
  id could not be minted (an indel offline), not a hole to fill by hand.
- **A genotype is `C/C`, not `CC`.** `CC` parses as a single two-base allele. Sources (ClinPGx) write
  the unslashed form; disambiguate using the resolved ref/alt.
- **Off GRCh38, expect less and say so.** rsIDs resolve against GRCh38 only, so a `genome_build:
  GRCh37` module resolves nothing and mints no VRS ids; its keys are build-relative coordinates that
  will not join against gnomAD/ClinVar/ClinGen. Author coordinates rather than rsIDs there. This is a
  known limitation, not a defect.
- **An rsID is position-level, not per-allele.** One rsID can legitimately span pathogenic, benign and
  uncertain alleles at one locus, and a paralogous one maps to several genuinely distinct places
  (reported as `expanded to N rows` — expected, do not delete rows to suppress it).

## Weight, state and direction

- **A `risk` weight is negative.** `weight` is a contribution to a wellness-style score, not a hazard
  ratio, so `state='risk'` or `direction='risk'` wants `weight < 0` and `protective` wants `weight > 0`.
  Getting the sign backwards is a warning, not an error, so it compiles — check it rather than trusting
  a green run.
- **`direction` is not a magnitude.** Its members are the same axis as `state`
  (`neutral`/`protective`/`risk`/`unknown`), not `increase`/`decrease`. Ask
  `just-dna-compiler describe variants.csv` before writing any vocabulary cell from intuition.
- **`direction` is authored or it is empty — nothing computes it for you.** `state` is the required
  legacy axis and `direction`/`stat_significance`/`clin_sig` are the orthogonal ones that replaced it;
  the compiler copies whatever you wrote into the artifact and never fills a blank from `state`, since
  that would be asserting a claim you did not make (`state='significant'` names no direction at all).
  So a module that carries only `state` compiles fine and ships an empty `direction` column, and a
  consumer keying on `direction` sees nothing. If you want the newer axis read, write it — on every row
  it applies to, not on some. Reading back: `VariantRow.effective_direction` returns the authored value
  else the `state`-derived fallback, and `just_dna_format.derive.direction_from_state(state, weight)` is
  that fallback as a plain function, for a consumer working from the parquet rather than the models.

## The checks, and the two ways to defeat them by accident

- **Never fill a cell from the same source that checks it** (the redundancy-bearing list, above).
- **Never author both sides of a redundancy check** — `resolution.csv` plus the coordinates it verifies.
- **`--strict` means reproducible, not correct.**
- **A sidecar you already have is authoritative and merged, never clobbered.** Delete it to regenerate.
- **Read "ref mismatch" as possibly being about `start`.** The check reports a coordinate shift when it
  can establish one; when it cannot (both neighbouring bases match your `ref`) it says only that the ref
  disagrees. If the same run reported a shift group, the residue almost certainly belongs to it. All of
  it is reported, never repaired, and none of it runs `--offline`.

## Withhold rather than assert

The house algebra is **three-valued: true / false / unknown**, and `None` is never `False`.

- **A blank cell means "not stated" and is always legitimate.** Do not write `false` to silence a
  reminder.
- **Every binning table has an `unresolved` sentinel** a consumer selects when the measurement is
  absent. Never route a missing measurement to the lowest bin.
- **Set `requires_callable=true` (with `callable_from`)** wherever the *absence* of a variant is the
  informative call: a no-call is not a reference call.
- **On licensing, unknown terms are undetermined, never permitted** — `share_alike` / `commercial_use`
  left blank do not mean allowed.
- **`unchecked` / `unknown` in a report means the question was never put**, which is not the same as a
  negative answer. A check that could not run is not a check that passed.

## Binning bounds

- **`measure_max` is inclusive on every kind.** A bounded domain's top value (allele fraction `1.0` is
  homoplasmy, and real) has to be reachable. Use `min == max` for a sharp value and a null bound for
  open-ended.
- **Whether adjacent bins may share an endpoint depends on the kind, and the two cases are opposite.**
  - **Dense — `allele_fraction`, `prs_percentile`: bounds must touch**, e.g. `0.0–0.1` then `0.1–0.3`.
    A shared endpoint is a *boundary*, not an overlap, and the higher bin owns it (lookup selects the
    row with the greatest `measure_min ≤ x`). A hole between bins warns, because on a continuous
    measure it can be arbitrarily small.
  - **Integer — `repeat_count`, `copy_number`: bounds must NOT touch**, e.g. `[27,35]` then `[36,39]`.
    Adjacent integer bins are already contiguous, so a shared endpoint is a real overlap — both bins
    claim that integer — and it is refused.
  - **`activity_score` is in neither set.** It is a consumer-summed value on a coarse grid, so interior
    holes are not meaningful (no gap warning) and bins do not touch.
- **Two bins sharing a *lower* bound refuse on every kind** — the boundary rule selects the greatest
  `measure_min ≤ x` and these two are the same, so there is nothing to order. Reachable as a sharp
  `[0.1, 0.1]` beside a range starting at `0.1`.
- Bins are grouped by the kind's key columns **plus** `trait_efo_id`. If two different variants collide
  in a heteroplasmy table, give each its own variant identity — that is what the key is for.

## PGx and star alleles

- **A clinical annotation's key is `(variant_key, drug, genotype, phenotype_category, annotation_id)`**
  — not the bare triple. One variant+drug carries several distinct annotations (rs4149056+simvastatin
  is Metabolism/PK 1A, Efficacy 3 *and* Toxicity 1A).
- **Annotations are per genotype, and can oppose each other** — rs4149056/simvastatin is "decreased"
  for CC/CT and "increased" for TT. Genotype is in the key for that reason.
- **CPIC recommendations are keyed by (phenotype, drug, *population*)**, and the populations disagree —
  the same Poor Metabolizer diplotype is `strong` in one clinical context and `moderate` in another.
  `draft --drug` **refuses and lists the choices** when several exist rather than picking one, because
  defaulting would assert a clinical context you never chose. Narrow with `--population`.
- **`recommendation_strength` is CPIC's; `evidence_level` is PharmGKB/ClinPGx's.** Different axes — fill
  only the one your source states.
- **A large star-allele gene needs `draft --allele`.** *n* alleles is *n(n+1)/2* diplotypes; unfiltered
  CYP2D6 is 16,290 rows, 73% `Indeterminate`. Your real bound is the allele set your caller emits. The
  filter covers all three PGx tables, `*1` is always kept (it is defined by carrying no variants), and
  it takes a single `--gene` because a star name is gene-scoped.
- **A star allele can be *used* without being *defined*.** If `haplotypes.csv` never defines an allele
  that `diplotypes.csv` or `allele_function.csv` names, a caller can never emit it and every row about
  it is dead. Warned, not blocked — leaning on an external caller's definitions is legitimate.
- **CPIC activity scores are inequality strings (`"≥3.0"`), not numbers**, so they do not drop into
  numeric bin bounds; and CPIC's `n/a` means *not scored* — an absence, so leave the cell blank.
- **A PGx module carries no `variants.csv`, and that is correct.** One CSV = one concern; never add an
  empty table to keep another company.

## Licensing

- **Every PGx upstream (ClinPGx, CPIC, PharmVar) is CC BY-SA *plus a no-sale clause*.** None is
  sellable. Do not read a bare "CC BY-SA" as permission — read the surrounding terms. (PharmGKB's API
  was retired on 2026-07-20; the successor is ClinPGx, paths and formats unchanged. CPIC is not an
  unrestricted alternative — its licence page redirects to the same ClinPGx data-usage policy.)
- **Pass `--use unstated | non-commercial | commercial`** to anything that copies rows out of a source
  (`draft`, `draft-panel`, `draft-clinpgx`, `dosage`, `pgx`, `clinpgx build/check`). A forbidding source
  is *skipped* on `unstated` and *refused* on `commercial`, at acquisition — nothing is even fetched.
- **`sources.csv` is the only thing the compile gate reads.** A source you copied from by hand is
  invisible to it — write the row yourself, or the restriction simply vanishes from the module. Only
  the *annotation* layer taints; a coordinate is a fact, so a fact-layer row carries attribution rather
  than a prohibition. Most-restrictive-wins, module-wide.
- **The CLI spelling and the column value differ.** `--use` accepts `non-commercial`, but the
  `declared_use` *column* takes the vocabulary member `non_commercial` (underscore). The flag
  normalizes; a cell you type by hand does not.
- **There is no `--non-commercial` compile flag, by design.** A flag cannot survive `reverse`, so a
  third compile would refuse. The declaration has to be data.

## Sex chromosomes and the PAR

- **A pseudoautosomal variant is recorded once, on X**, because that is the spelling every annotation
  source uses and a standard GRCh38 analysis set hard-masks the Y PAR. Pass `--keep-par-twin` to
  `enrich` only if your reference is unmasked.
- **`chrom=Y` is not "never diploid": PAR1 and PAR2 are diploid in every karyotype.** The verdict is
  **per locus**, not per gene or per module — `XG` and `SPRY3` each straddle a boundary.
- **`chrom=MT` is not diploid.** Use a single allele (`G`) for a homoplasmic or hemizygous call.

## Module structure

- **One CSV = one concern.** Compose from optional table kinds; never add a foreign domain's columns to
  every row. The SNP core (`variants.csv` + `studies.csv`) stays minimal, and `studies.csv` is required
  **iff** `variants.csv` is present. At least one recognised table must exist.
- **A value every row shares belongs in `module_spec.yaml`'s `defaults:`** (`curator`, `method`). Both
  spellings are the same content to the signature; the defaults block is the tidier module.
- **Authored row order is preserved** through compile → reverse → recompile and is load-bearing for
  `artifact.digest`. Drafted rows land in their gene's block or at the end; a re-run leaves anything
  already there exactly as it is.
- **Write CSVs with a CSV writer, not by splitting on commas.** Several `conclusion` values contain
  commas, and a column shift usually surfaces as a bizarre validation error three columns away.

## Known gaps — do not work around these in your data

Messages sometimes cite an `RMn` — a tracked item in the upstream project's roadmap. That marker means
**known and deliberate**: leave the data honest and note the limitation rather than inventing a
workaround.

- **RM5** — symbolic and structural alleles (`<DEL>`, 5-HTTLPR, ClinPGx `del`/`ins`, CPIC's `x≥3` and
  `DELTCT` notations) are outside the `^[ACGT]+$` grammar. The PGx passes skip such rows and count them
  rather than coercing them. Distinct from CPIC's IUPAC ambiguity codes (`R`), which record an
  uncertainty that was never expressible.
- **RM15** — multi-build support. GRCh38 is the only assembly with a refget table, so VRS identity
  minting and rsID resolution are GRCh38-only.

---

# The command surface

## `just-dna-compiler` (offline, never fetches)

| Command | Does |
|---|---|
| `scaffold <dir> --kind K --name N` | create `module_spec.yaml` + a stub CSV per kind. Never overwrites. `--rows`, `--dry-run` |
| `template <kind>` / `stub <kind>` | header-only CSV / header plus placeholder rows |
| `requirements <kind>` | always / one-of / never-empty-defaults / optional. `--json` |
| `describe <kind>` | full JSON: columns, vocabularies, pick-lists, requirements |
| `reference` | every model at once. `--summary`, `--schemas` |
| `hint <kind> --file F` | inspect authored rows; report wrong / rewritten / left-to-you. Writes nothing |
| `validate <dir>` | full pre-flight, exit 1 if invalid. `--strict/--best-effort` — pass the mode you will compile with |
| `compile <dir> <out>` | parquet + `manifest.json`. `--strict`, `--compression`, `--compiled-by` |
| `signature <dir>` | the content signature of the raw authored data — no compile, no reference |
| `reverse <artifact> <out>` | artifact → authored spec DSL. `--resolution/--no-resolution`, `--genome-build` |
| `keygen --out key.pem` | Ed25519 key; prints the public key `verify` pins |
| `sign <dir> --private-key K` | signs `artifact.digest`, writes the signature into the manifest |
| `verify <dir>` | re-hash every file, recompute the digest, check the signature. `--public-key`, `--no-require-marketplace`, `--check-inputs/-logs/-provenance/-logo` |

## `just-dna-enricher` (the only tier that fetches)

| Command | Does |
|---|---|
| `enrich <dir>` | → `resolution.csv`. `--strict`, `--offline`, `--no-clinvar`, `--no-gnomad`, `--no-vrs`, `--no-verify-ref/-clinsig/-rsids`, `--keep-par-twin`, `--ensembl-cache`, `--clinvar-cache` |
| `frequencies <dir>` | → `frequencies.csv` from gnomAD. `--populations`, `--dataset`. Online only |
| `gene-metrics <dir>` | → `gene_metrics.csv` constraint. Snapshot first, live API (v2.1.1) as fallback |
| `dosage <dir>` | ClinGen dosage rows onto `gene_metrics.csv`. `--use`, `--url` |
| `literature <dir>` | → `literature.csv`. `--fulltext/--no-fulltext`, `--doi/--no-doi` |
| `draft <dir> --gene G` | CPIC → the three PGx tables. `--drug`, `--allele`, `--population`, `--use`, `--dry-run` |
| `draft-panel <dir> --gene G` | ClinVar → `variants.csv` + `studies.csv`. `--snapshot`, `--offline`, `--clin-sig`, `--min-review-stars`, `--max-citations`, `--use`, `--dry-run` |
| `draft-clinpgx <dir> --snapshot S` | ClinPGx → `pharm_variants.csv`. `--gene`, `--drug`, `--min-evidence-level`, `--use`, `--dry-run` |
| `check-identifiers <dir>` | trait CURIEs (OLS4), gene symbols (HGNC). `--no-traits`, `--no-genes` |
| `check-acmg <dir>` | `acmg_sf` vs the ACMG SF list. `--sf-list` (strongly preferred), `--offline`, `--url` |
| `pgx <dir>` | `function_status` vs PharmVar + CPIC. `--no-pharmvar`, `--no-cpic`, `--use` |
| `clinpgx check <dir> --snapshot S` | `pharm_variants.csv` vs the ClinPGx snapshot, offline-capable |
| `hint variant\|citation\|trait\|gene` | look up one identifier. Writes nothing. `--json`, `--offline`, `--ambiguity`, `--frequencies` |
| `vrs mint <dir>` | stamp `ga4gh:VA.…` ids onto `resolution.csv` (substitutions offline, indels online) |
| `enrich-and-compile <dir> <out>` | steps 4 + 6. `--frequencies`, `--gene-metrics` |
| `template <kind>` | the compiler's, mirrored |

Snapshot builders (dev/publisher surface, mostly needing the `polars` extra):
`clinvar build|citations|publish`, `clinpgx build`, `acmg build`, `gnomad constraint`, `upload`.

Every pass takes `--strict` / `--best-effort`, and every pass that can degrade takes `--offline`.
`--offline` is the only switch; an explicit `--*-cache` path is the inject-only escape hatch and is
never second-guessed.

## Python, when the CLI is not enough

`just-dna-format` ships no CLI (a Typer dependency would breach its pydantic-plus-cryptography floor),
so a few things are import-only:

```python
from just_dna_format import alleles, reference, vocab
from just_dna_format.base import derive_variant_key
from just_dna_format.integrity import verify_manifest
from just_dna_format.manifest import read_manifest

reference.authoring_reference()             # what `just-dna-compiler reference` prints, as a dict
manifest = read_manifest(module_dir / "manifest.json")
verify_manifest(module_dir, manifest, require_marketplace=False)   # raises IntegrityError
alleles.parsimony_reduce({"CAG", "C"})      # the indel reduction — public so a consumer can apply it
derive_variant_key(rsid, chrom, start, ref, alts=None, build="GRCh38")  # rsid → VA id → coordinate
vocab.VALID_STATES                          # every closed vocabulary, as a frozenset
```

Pass a row's own `build` to `derive_variant_key` whenever the module is not GRCh38 — the default
silently mints GRCh38 identity.

The row models live in `just_dna_format.spec` (`VariantRow`, `StudyRow`), `.pgx`, `.binning`, `.pgs`,
`.frequency`, `.literature`, `.sources`, `.resolution`. `just_dna_format.identity` is unrelated to
variant identity — it holds module naming, versions and canonical ids.

# When something looks wrong

`references/SYMPTOMS.md` maps the actual message text → cause → what to do. Start there before reading
code; most of those entries are traps that cost someone a day already.
