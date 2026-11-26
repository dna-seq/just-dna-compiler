# ClinVar-GKM slice (RM305 fixture)

Extracted on 2026-11-26 from ClinVar-GKM's published Parquet set on line `v1/1.2`, release `2026-11-22`
(`https://data.clinvar-gkm.org/v1/1.2/parquet/`). CC0 over ClinGen's transformation; derived from NCBI's
ClinVar. Attribute ClinVar as the data source and cite ClinVar-GKM (doi:10.5281/zenodo.18343663).

- `manifest.json` and `index.json`: the source's `parquet/manifest.json` and `v1/1.2/index.json`,
  byte for byte as served that day. The manifest's `files[]` digests are the full files', so a test that
  verifies this slice against it rewrites the two entries for the slice at test time.
- `allele.parquet` keeps all seven source columns (`id`, `type`, `name`, `digest`, `expressions`, `location`,
  `state`). The former `data` JSON column is gone. Each allele now carries `expressions` as a list of
  structures with `syntax` and `value`, and `state` as a structure with `type`, `length`, `sequence` and
  `repeatSubunitLength`. The 22 rows cover the two RM270 insertions (`rs72613567`, `rs77944059`), two
  alleles with no SPDI expression, the one T2T allele, three substitutions, a single-base and a multi-base
  reference-agreeing `ReferenceLengthExpression`, two same-length MNVs, three literal indels, two
  mitochondrial, one chrY and one chrX indel, an allele carrying two rsIDs, and the two indel alleles of
  `rs1003713657` (one rsID naming two alleles).
- `variation.parquet`: the 22 real variations whose `DefiningAlleleConstraint` names those alleles,
  **projected** to `id`, `mappings` and `constraints`, the three columns the builder reads. The other
  columns of the source file are not here.

The 2026-11-04 extraction selected the first rows of each class in source order. The 2026-11-26
extraction took the same 22 allele IDs and 22 variation IDs and kept their original order.
