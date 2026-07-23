"""just-dna-enricher — the network tier that fills the source-independent resolution table.

The only package in the workspace allowed to fetch (CONSTITUTION Goal 2 + the 0.5 amendment):
`just-dna-format` and `just-dna-compiler` stay strictly inject-only. The enricher *produces*
`resolution.csv` (cache → HF snapshot → live Ensembl, with a V2→V1 fallback and retries); the
compiler *consumes* it. Import the public surface from the submodules where it lives
(`just_dna_enricher.enrich`, `.ensembl`, `.download`) rather than re-exporting here.
"""
