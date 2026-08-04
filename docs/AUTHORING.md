# Authoring a just-dna module (0.5)

A module is a directory of human-authored CSVs plus `module_spec.yaml`. It carries **annotation only**
— lookup tables mapping a genotype or a measured quantity to a phenotype. It never holds a sample, a
genotype under test, or a measured value: the consumer supplies the measurement at query time.

Read [CONSTITUTION.md](CONSTITUTION.md) before changing the *schema*. This guide is about
using it. Companions: [AUTHORING_TABLES.md](AUTHORING_TABLES.md) (which table kind), [AUTHORING_SYMPTOMS.md](AUTHORING_SYMPTOMS.md) (message → cause → action).

> Invoke it as a skill with `/write-module`; `.claude/skills/write-module/SKILL.md` dispatches here
> so there is one copy of the workflow, not two.

## Answer three questions first — each one closes off wrong turns later

1. **What is each row's subject?** A variant? A diplotype pair? A measured quantity? That picks the
   table kind, and a module includes **only** the kinds it uses — never an empty `variants.csv` to keep
   another table company. → [AUTHORING_TABLES.md](AUTHORING_TABLES.md)
2. **Are the coordinates GRCh38?** If `genome_build` is anything else, `variant_key` falls back to a
   **build-relative coordinate** and will not join against gnomAD, ClinVar or ClinGen. The compiler
   warns; heed it. Publish GRCh38 coordinates unless you have a reason not to.
3. **What is the source, and may you use it this way?** Every PGx upstream (ClinPGx, CPIC, PharmVar) is
   CC BY-SA **plus a no-sale clause**, so none is sellable — do not read a bare "CC BY-SA" as
   permission. Pass `--use unstated | non-commercial | commercial` to the commands that copy rows out
   of a source (`draft`, `draft-panel`, `draft-clinpgx`, `dosage`, `pgx`, `clinpgx build/check`); a
   forbidding source is *skipped* on `unstated` and *refused* on `commercial`, at acquisition. The terms
   land in `sources.csv`, which is the only thing the compile gate reads — so a source you copied from
   by hand is invisible to it, and you must add the row yourself.

## The order, and the one place deviating from it deadlocks

```
scaffold ──▶ draft ──▶ curate ──▶ enrich ──▶ check ──▶ compile ──▶ sign
             (if a           (only a human)
              source has it)
```

**Curate before you enrich.** A drafted row leaves `<<REPLACE>>` in the cells only a human can decide,
and that placeholder makes *every* loader refuse the file — including `enrich`. That is deliberate:
forward resolution is allele-aware, and a placeholder genotype would silently skip the allele filter on
exactly the one-to-many rsIDs that need it. So you cannot "enrich first to see the alleles".

You do not need to: **the draft report prints the allele pair for each stubbed row.** Curate from that.

## 1 — Start the spec

```bash
just-dna-compiler scaffold spec/ --kind variants.csv --kind studies.csv --name my_module
```
Re-runnable and never overwrites, so run it again with a different `--kind` to add a table later. Then
replace every `<<REPLACE>>` in `module_spec.yaml`.

Learning a table you have not authored before:
```bash
just-dna-compiler requirements heteroplasmy.csv   # required / defaulted / optional, and any one-of rule
just-dna-compiler describe    heteroplasmy.csv    # every column, its vocabulary, its pick-list
just-dna-compiler template    heteroplasmy.csv    # just the header
just-dna-compiler reference --summary             # every model at once
```
**`required` is not the whole story.** A `defaulted` column (`measure_kind`, `unresolved`) is not
required *and* must not be left empty — an empty cell arrives as `None` and fails on type. Trust
`requirements`, which reports all three categories.

Or copy the nearest [reference example](../reference_examples/) and edit. That is usually faster,
and each README says what it was built to exercise.

## 2 — Draft from a source, if one publishes the table

```bash
just-dna-enricher draft-panel spec/ --gene HFE --use non-commercial   # ClinVar → variants.csv
#   the snapshot is downloaded if you have none; add --snapshot cv/ --offline to use one you built
just-dna-enricher draft spec/ --gene CYP2C19 --drug clopidogrel --use non-commercial # CPIC → the 3 PGx tables
just-dna-enricher draft-clinpgx spec/ --snapshot cp/ --drug simvastatin --use non-commercial
```
Drafting **appends and never rewrites a cell**. A row whose key already exists is reported
(`already_present` / `differs`), never overwritten — drift on existing rows is `enricher pgx`'s job to
report, not drafting's to fix. Re-run per gene as the module grows; `--dry-run` first.

Read the warnings. They are the interesting output: skipped rows, aggregated counts, and the allele
pairs you need for step 3.

## 3 — Curate what only a human can decide

Nothing automated fills these, on purpose:

| Cell | Why it is yours |
|----------------------|------------------------------------------------------------------------------|
| `genotype` | Sources publish **alleles, not genotypes**. Whether one copy is informative follows from the condition's inheritance mode. Write it from the allele pair the draft reported. |
| `weight`, `direction`, `effect_size` | Your model of the finding. ClinVar publishes no effect statistic. |
| `trait_efo_id` | A source's `condition` is free text / MedGen. Mapping it to an ontology is inference. |
| `conclusion` | What the module *says*. Keep it hedged where the biology is (penetrance, tissue, co-factors). |

To write a genotype you need the alleles. Ask, without writing anything:
```bash
just-dna-enricher hint variant --rsid rs1801133      # locus, ref, alts — and "[redundancy_bearing]"
just-dna-enricher hint variant --rsid rs334 --ambiguity   # warn when the answer is not unique
just-dna-enricher hint citation --pmid 7647779       # does the PMID exist, and what DOI does it carry
just-dna-enricher hint trait EFO_0004541             # current | obsolete | absent
just-dna-enricher hint gene MTHFR                    # approved | retired | unknown
```

**Never fill a cell from the same source that checks it.** `rsid`, `chrom`, `start`, `ref`, `alts`,
`clin_sig`, `doi`, `acmg_sf`, `function_status`, `evidence_level` and `p_value_num` are
*redundancy-bearing*: a check compares your independently-authored value against a source, and filling
it from that source makes the check vacuous — worse, for an rsid-only row the coordinate check does not
run at all, so the row moves from honestly unverified to apparently verified. `hint` shows you the value
and comes back `applied=false` with the reason. That refusal is the feature, not a limitation.

## 4 — Enrich (the only tier that fetches)

```bash
just-dna-enricher enrich spec/                    # → resolution.csv (rsid ↔ coordinate, VRS ids)
just-dna-enricher enrich spec/ --offline          # caches only, zero egress
just-dna-enricher frequencies spec/               # → frequencies.csv   (gnomAD, paced)
just-dna-enricher gene-metrics spec/              # → gene_metrics.csv  (constraint)
just-dna-enricher dosage spec/                    # → ClinGen dosage rows
just-dna-enricher literature spec/                # → literature.csv    (PMID/DOI/quotes)
```
An existing sidecar is **authoritative and merged, never clobbered**. To regenerate after changing the
spec you must **delete the file first**, or stale rows silently persist.

## 5 — Cross-check what you asserted against what the sources say

```bash
just-dna-enricher check-identifiers spec/   # rsIDs, trait CURIEs, gene symbols still current
just-dna-enricher check-acmg spec/ --sf-list acmg/   # acmg_sf vs the ACMG SF list (v3.3)
just-dna-enricher pgx spec/                 # function_status vs PharmVar and CPIC
just-dna-enricher clinpgx check spec/ --snapshot cp/
```
Every check **reports, never repairs**. `--strict` escalates a finding to a refusal; `best_effort`
warns and carries on. Two deliberately never escalate — the `clin_sig` and allele-function
cross-checks — because failing would make the format arbitrate between expert panels.

`check-acmg` needs `--sf-list` to give a real answer: NCBI's page serves SF **v3.2** and ACMG published
**v3.3**, so without a snapshot every disagreement comes back `unverifiable` rather than as a finding.
Build it once from the committed workbook — `just-dna-enricher acmg build assets/acmg_sf_v3.3.xlsx
--out acmg/` — and the check also stops needing the network.

## 6 — Compile, verify, publish

```bash
just-dna-compiler validate spec/
just-dna-compiler compile  spec/ out/ --strict
just-dna-compiler keygen --out key.pem       # prints the public key `verify` pins
just-dna-compiler sign    out/ --private-key key.pem
just-dna-compiler verify  out/ --no-require-marketplace --public-key <base64>
```
`--strict` means *reproducible artifact*: it refuses when resolution left something it could not
reproduce. It is orthogonal to `--use`, which is about who may use the data.

If you changed the schema (not just data), prove the round-trip:
```bash
just-dna-compiler reverse out/ rev/ && just-dna-compiler signature spec/ && just-dna-compiler signature rev/
```
The two `content_signature` values must match — that is Principle 7's fixed point.

## Standing rules worth memorising

- **One CSV = one concern.** Compose from optional table kinds; never add a foreign domain's columns to
  every row.
- **Identity is filled whole or not at all** — the rsID, else the complete `chrom`/`start`/`ref`/`alts`.
  A partial coordinate silently changes *which variant the row is*.
- **Withhold rather than assert.** Every binning table carries an `unresolved` sentinel a consumer
  selects when the measurement is absent — never the lowest bin. Set `requires_callable=true` (with
  `callable_from`) wherever the *absence* of a variant is the informative call: a no-call is not a
  reference call. Leave a cell **blank** rather than `false` when you do not know.
- **A blank cell means "not stated" and is always legitimate.** Do not write `false` to silence a
  reminder.

## When something looks wrong

[AUTHORING_SYMPTOMS.md](AUTHORING_SYMPTOMS.md) maps the actual message text → cause → what to do. Start there before reading
code; most of those entries are traps that cost someone a day already.

Known limitations you may hit and should **not** try to work around in your data: **the batch of five
found by dogfooding has all shipped**, so what follows is behaviour to expect rather than defects to route
around. One indel spelled two ways now resolves, and the reduction is public
(`just_dna_format.alleles`) if you need to apply it to your own calls. `sources.csv` understands that a
resolution *link* is not a source name. A continuous binning table can be tiled — write bounds that
**touch**, e.g. `0.0–0.1` then `0.1–0.3`, and the higher bin owns the shared endpoint. A large star-allele
gene is drafted with `draft --allele`. And a pseudoautosomal variant is recorded once, on X, because that
is the spelling every annotation source uses — pass `--keep-par-twin` to `enrich` if your reference is not
analysis-set masked and you want the Y copy too. The rationale for each is in
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md); the still-open items in [ROADMAP.md](ROADMAP.md) are design
questions rather than traps.
