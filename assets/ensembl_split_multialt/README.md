# ensembl_split_multialt — three multi-ALT indel sites, as both Ensembl snapshot repos publish them

Real bytes, copied 2026-11-05 for RM381 (`enricher/tests/test_split_snapshot_per_alt.py`). Every row at
the three positions is kept, co-located rsIDs and the old repo's non-rs records included, so a reader is
tested against the site as it really reads.

- `split/data/homo_sapiens-split.parquet`: `just-dna-seq/ensembl_variations_split`, release
  `ensembl-variation-2026_07_13-vep116.0` (the RM372 pull), rows at `11:5226773`, `16:23635706` and
  `X:634689`, every column and `row_idx` as published. One row per ALT, all ALTs of a site under one
  shared padded `ref`: `rs1555461597` is `GTT>G`, `GTT>GT`, `GTT>GTTT`; `rs267607291` is `TGG>T`,
  `TGG>TG`; SHOX's `rs1569493663` is `CAG>C`, `CAG>CAGAG`.
- `old/data/homo_sapiens-old.parquet`: `just-dna-seq/ensembl_variations` (the Oct-11 snapshot read until
  0.8), rows at `11:5226773`–`5226774`, `16:23635706`–`23635707` and `X:634689`–`634690`, the columns
  `chrom, start, end, id, ref, alt`. One row per site with a pipe-joined `alt`, jointly trimmed and one
  base right of the split repo's anchor: `rs1555461597` is `16:23635707 TT>T|TTT`, `rs267607291` is
  `11:5226774 GGG>G|GG`, `rs1569493663` is `X:634690 AGA>A|AGAGA`.

Neither directory carries a `manifest.json`, which RM372's check reads as the unknown arm.

The per-ALT spelling a caller writes for each allele is ClinVar's record in
`assets/consumer_join/clinvar_20260627_norm_slice.vcf.gz` (`RS=1555461597`, `RS=267607291`,
`RS=1569493663`), which the test reads as its oracle; the bases it left-aligns against are that fixture's `grch38_windows.fa.gz`.
