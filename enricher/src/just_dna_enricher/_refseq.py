"""Versioned GRCh38 RefSeq accessions shared by the enricher’s sequence readers and builders."""

#: Nuclear accessions distinguish GRCh38 from GRCh37 in the CIViC build.
GRCH38_REFSEQ_ACCESSIONS: dict[str, str] = {
    f"NC_{i:06d}.{v}": c
    for i, v, c in zip(
        range(1, 25),
        (11, 12, 12, 12, 10, 12, 14, 11, 12, 11, 10, 12, 11, 9, 10, 10, 11, 10, 10, 11, 9, 11, 11, 10),
        [str(n) for n in range(1, 23)] + ["X", "Y"],
        strict=True,
    )
}

#: All primary contigs, including the mitochondrial sequence shared by both builds.
GRCH38_ACCESSIONS: dict[str, str] = {**GRCH38_REFSEQ_ACCESSIONS, "NC_012920.1": "MT"}
