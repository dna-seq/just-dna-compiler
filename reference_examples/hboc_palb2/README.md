# `hboc_palb2` — every derived producer, and the corpus's first attestation

**What this probes:** *the whole enricher pipeline on one module.* Before this, no reference example
carried `verification.json`, `gene_validity.csv`, `clinical_assertions.csv`, `frequencies.csv` or
`gene_metrics.csv` — five of the eleven zero-rows in the plan's uniformity table, four of them things
0.6 built. This module has all of them, produced in the documented order:

```
draft-panel → enrich → frequencies → gene-metrics → gene-validity → assertions → literature → compile
```

PALB2 at ClinVar's **3-star** floor (reviewed by an expert panel) is 16 variants — small enough to
author honestly and large enough that the aggregation rules matter.

## The one authorial decision, and where the information for it lives

`clinvar_draft` writes `genotype` as `<<REPLACE>>` on every row, deliberately: ClinVar publishes
**alleles**, not genotypes, and zygosity is inheritance-mode interpretation the source does not state.
PALB2 is autosomal dominant, so the actionable genotype for a pathogenic allele is the heterozygote,
and that single decision was applied to all sixteen rows.

The alleles to build it from are **not in the file**. A drafted row is rsID-only — identity whole or
not at all — so `rs118203998` arrives with empty `ref`/`alts`, and the pair is stated once, in
`draft-panel`'s warning stream:

```
warning:   genotype for rs118203998: ClinVar publishes G>T — an allele pair from {G, T}
```

That is the right information in the wrong place for the next step: it is stdout, one line per row,
and the author's next action is an edit to a file that does not contain it. At 16 rows this is a
transcription exercise; at the 761 rows the same command drafts for PALB2 at the 2-star floor it is
not one.

## What it broke

### 1 — five of seven checking passes attest nothing, and twelve of seventeen vocabulary members are unreachable

The chain above ran `literature` (10 citations checked for existence and DOI agreement),
`gene-validity` (ClinGen curation for PALB2), `assertions`, `frequencies` and `gene-metrics`. The
attestation this module ships records **four** records, all from `enrich`:

```
clinical_significance   subj  0  find 0  skip tautology
genome_build_agreement  subj  0  find 0  skip nothing_to_check
reference_allele        subj 18  find 0  skip None
rsid_currency           subj 16  find 0  skip None
```

`record_verification` has exactly **two** callers in the workspace — `enrich()` and
`enrich_clinpgx()`. So of `VALID_VERIFICATION_CHECKS`' seventeen members, five can ever be emitted:

| emitted | never emitted by anything |
|---|---|
| `clinical_significance`, `genome_build_agreement`, `pgx_evidence_level`, `reference_allele`, `rsid_currency` | `acmg_secondary_findings`, `allele_function`, `citation_existence`, `citation_identifier`, `dosage_sensitivity`, `gene_disease_validity`, `gene_locus_agreement`, `gene_symbol_currency`, `provenance_quote`, `rsid_coordinate_agreement`, `trait_currency`, `vrs_allele_id` |

Every one of the twelve names a check the workspace really performs — `literature` answers
`citation_existence` and `citation_identifier`, `check-identifiers` answers `gene_symbol_currency`,
`trait_currency` and `gene_locus_agreement`, `check-acmg` answers `acmg_secondary_findings`, `dosage`
answers `dosage_sensitivity`, `pgx` answers `allele_function`, `vrs mint` answers `vrs_allele_id`.
They run, they report to stdout, and the record dies with the process, which is the exact sentence
RM45's own module docstring opens with as the thing it exists to fix.

And it is a **claim**, not a gap. `verification.py`'s docstring says:

> **One proof-of-work per call, which means one per command.** … A separate command
> (`check-identifiers`, `literature`) **writes once of its own**, and the merge below is what keeps
> the two runs' records in one document instead of overwriting each other.

`merge_records` is built and tested for a multi-command document that no two commands produce. This
is the *"a snapshot's `ensure_*` must actually be CALLED — check the pass, not just the function"*
shape, with the vocabulary and the merge in place of the provisioning function.

### 2 — `hint` reports every template stub twice

On the freshly drafted file, `just-dna-compiler hint variants.csv` returns **219 findings for 109
rows** (the ATM+PALB2 draft) — two errors per stubbed cell:

```
error: line 2 [genotype] genotype is still a template stub — replace it
error: line 2 unreplaced template placeholder '<<REPLACE>>' in VariantRow row: genotype. …
```

One comes from `hint`'s own per-column check and one from the model's `mode="before"` validator. Both
are correct and they are the same finding. This is the aggregation lesson CPIC taught four times,
arriving through a different door: not a loop over a source table, but two layers reporting the same
cell.

## What was probed and held

- **RM4's tautology skip, on the module it was designed for.** The panel was drafted from
  `clinvar_2026-06-27` and the licence row records that release, so `enrich` skips the `clin_sig`
  cross-check **and names the hole in the same breath**: *"Two things that leaves unseen: a cell
  edited by hand since the draft, and rows added from another release. Re-run with `--strict` to look
  every row up…"* The attestation records it as `skipped: tautology`, which is a first-class answer
  rather than a silent pass.
- **RM31's hosting verdict on real disagreeing data.** `rs180177102` is `CA>C` in ClinVar and
  `CAA>C` in Ensembl at `16:23634953`; the locus is left out of `resolution.csv` with the reason
  stated — *"The event sizes differ, which re-anchoring cannot change, so this is a different variant
  sharing the rsID rather than another spelling."* Two rsIDs in this panel do that.
- **RM45's staleness and determinism.** Editing one authored byte drops the block with a warning
  naming both hashes and saying the manifest *"records no verification for this compile, which says
  nothing rather than claiming a pass"*. Re-running `enrich` with nothing changed reproduces
  `module_hash`, `signature`, `nonce` and `difficulty` **byte for byte** — only `produced_at` and
  `checked_at` move — so the proof-of-work is deterministic as designed and a re-run does not churn
  the file.
- **Every derived block reaches the manifest**: `frequency`, `gene_metrics`, `gene_validity`,
  `clinical_assertions`, `literature`, `sources` and `verification` are all present.
- **The one-to-many expansion and the VRS verify ladder.** Two rsIDs expand to two loci each, each
  keyed by its coordinate with the count in the message; the one MNV
  (`AGGAAGCTCTGC>TCTGA`) is reported as *unverifiable* — "minted upstream by the enricher, not
  recomputable here; carried unverified" — a warning in both modes, which is the tier's-limit half
  of the three-outcome rule and not a mode ladder.
- **The round trip is a fixed point** on all three signatures, and `reverse` says the attestation
  cannot be carried.

## Not run

**RM4's `withdraw_stale_dataset`** needs two ClinVar releases, and only one snapshot is provisioned
here. Building a second from the same VCF under a different label would fabricate the provenance the
mechanism exists to protect, so the probe is recorded as not run rather than faked.
