# GRCh38 mitochondrial reference fixture

The FASTA contains chromosome MT (16,569 bases), cut byte-for-byte on 2026-11-27 from the local
Ensembl `Homo_sapiens.GRCh38.dna.primary_assembly.fa`, with its original header and line wrapping.
The accompanying `.fa.fai` indexes this single-contig file. MT is one of the primary assembly
contigs whose uppercased whole sequence matches the GRCh38 refget accession.

`enricher/tests/test_local_fasta.py` copies the pair to a temporary directory. It compares real MT
indels to the committed ClinVar-GKM spellings and VRS IDs, checks the MT resolution rows from
`reference_examples/mt_common_deletion`, and exercises digest caching and refusal of unreadable
contigs without changing either fixture file.
