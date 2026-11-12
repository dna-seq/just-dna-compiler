# Upstream ledger — the VCF specification

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. The source is `samtools/hts-specs`, branch `master`: `VCFv4.5.tex` is
the live version, and a 4.6 would arrive there as a new file, first as a pull request. Clone as the liaison state
file's `vcf-spec` line says: sparse, without `test/`, whose `aux.*` files the NTFS mount refuses. Watched daily
on `master` (`.blueprints.toml`, `watch.vcf-spec`).

Asked for by the maintainer on 2026-11-12, relayed by the pm: "watching vcf spec and auto dropping rms to be in
line with it is Liaissons". A spec change that touches what a module points at or a consumer reads becomes an
`RMn` for the pm to size; until the person confirms in this seat's own session that it files the RM itself, it
goes to triage, which does.

## Marks

- **Read mark: `510c107`** (`master`, 2026-08-11, "Relax MM tag regexp", #859): the tree
  `docs/probes/VCF_4_5_AUDIT.md` quotes, the whole of `VCFv4.5.tex` read there on 2026-08-12/13. `master` has
  not moved since (re-read 2026-11-12).
- **The last change to `VCFv4.5.tex`: `e821e4f`** (2026-02-24, #851, `LGL`/`LGP` retyped Integer to Float). Read
  in the audit (its line 468: "No touchpoint here"), and re-read 2026-11-12 against
  `schema/src/just_dna_format/vocab.py:245`, which records only their `Number=LG`, never their type. Holds.
- **4.6: none.** No `VCFv4.6*` file on any branch, and no open pull request drafts one (2026-11-12).
- **Open pull requests touching VCF** (2026-11-12): #874 (a 4.5 test file for `Number=P` with `PSL`/`PSO`/`PSQ`,
  updated 2026-10-20), #853 (a gVCF example fix), #283 (a strict SAM/VCF draft, updated 2026-07-08), and two from
  2022 (#527, #430). Re-listed with the weekly bump; one that merges reaches the watcher.

## What we point at

The spec surface the code reads is mapped section by section in `docs/probes/VCF_4_5_AUDIT.md` (its touchpoint
table) and, for 4.4, `docs/probes/VCF_4_4_AUDIT.md`; this ledger does not copy it. The narrow entries a change is
read against first:

- `schema/src/just_dna_format/vocab.py` (`Number=` classes of the reserved FORMAT and INFO fields, the local-allele
  family included);
- the allele grammar and symbolic alleles (`@symbolic-alleles`, `@non-nucleotide-spelling`);
- `start` as the 1-based `POS` (`@start-1based`).

## Verdicts

None since the audit.

## Outbound

None.
