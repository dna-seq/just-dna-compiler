"""An indel's VRS mint reads the reference once per locus, and mints the id it minted before (RM407).

vrs-python's `normalize` wraps the data proxy in its own `SequenceProxy`, and every slice it takes while
trimming and rolling through a repeat became one `get_sequence` call, one HTTP read of seqrepo. The
registry's replay of 46 modules made 2,472 of them, about ten per indel. The minter now hands
`normalize` a window over the locus, read once, and serves every slice inside it from memory.

The reference here is synthetic: a counting data proxy over a fixed sequence on chromosome 1's real
refget accession, so the test needs no network and the two runs compare ids minted against one
sequence. The ids are equal by construction only if the window serves exactly the bases the proxy
would; that is what the equality assertion checks.
"""

import random

import pytest
from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models, normalize
from ga4gh.vrs.dataproxy import _DataProxy
from just_dna_enricher.sequences import SequenceProxy
from just_dna_enricher.vrs import VrsMinter
from just_dna_format.vrs import refget_accession

ACCESSION = refget_accession("1", "GRCh38")
LENGTH = 20_000


def _reference() -> str:
    """A fixed-seed sequence with the repeats normalization rolls through, at known 1-based positions."""
    bases = random.Random(407).choices("ACGT", k=LENGTH)
    for offset, run in ((5_000, "A" * 14), (9_000, "CA" * 12), (15_000, "TTTGTTTG" * 4)):
        bases[offset - 1 : offset - 1 + len(run)] = run
    return "".join(bases)


REFERENCE = _reference()

#: (chrom, 1-based start, ref, alt): an insertion and a deletion inside each repeat, and one indel in
#: unique sequence, so the window serves trims, rolls left and rolls right.
INDELS = [
    ("1", 5_006, "A", "AA"),
    ("1", 5_003, "AA", "A"),
    ("1", 9_004, "C", "CCA"),
    ("1", 9_010, "ACA", "A"),
    ("1", 15_005, "G", "GTTTG"),
    ("1", 12_345, REFERENCE[12_344], REFERENCE[12_344] + "GATTACA"),
]


class _CountingReference(_DataProxy):
    """A data proxy over `REFERENCE` that counts every read, as seqrepo would serve them."""

    def __init__(self) -> None:
        self.sequence_reads: list[tuple[int | None, int | None]] = []
        self.metadata_reads = 0

    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        assert identifier == f"ga4gh:{ACCESSION}", identifier
        self.sequence_reads.append((start, end))
        return REFERENCE[start or 0 : LENGTH if end is None else end]

    def get_metadata(self, identifier: str) -> dict:
        assert identifier == f"ga4gh:{ACCESSION}", identifier
        self.metadata_reads += 1
        return {"length": LENGTH, "aliases": [identifier], "alphabet": "ACGT"}

    def _get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        return self.get_sequence(identifier, start, end)

    def _get_metadata(self, identifier: str) -> dict:
        return self.get_metadata(identifier)


class _Sequences(SequenceProxy):
    """The run's own proxy class over the counting reference."""

    def __init__(self, reference: _CountingReference) -> None:
        super().__init__(offline=False)
        self._reference = reference

    def proxy(self) -> _DataProxy:
        return self._reference


def _ids_from_the_raw_proxy() -> list[str]:
    """What `normalize` mints when it reads the proxy directly, slice by slice: the ids before RM407."""
    reference = _CountingReference()
    ids = []
    for _chrom, start, ref, alt in INDELS:
        allele = models.Allele(
            location=models.SequenceLocation(
                sequenceReference=models.SequenceReference(refgetAccession=ACCESSION),
                start=start - 1,
                end=start - 1 + len(ref),
            ),
            state=models.LiteralSequenceExpression(sequence=alt),
        )
        ids.append(ga4gh_identify(normalize(allele, data_proxy=reference)))
    assert len(reference.sequence_reads) > len(INDELS), (
        "the raw path no longer reads per slice; the test proves nothing"
    )
    return ids


def test_each_indel_is_read_once_and_minted_as_before():
    reference = _CountingReference()
    minter = VrsMinter(sequences=_Sequences(reference))
    minted = [minter.mint(chrom, start, ref, alt) for chrom, start, ref, alt in INDELS]
    assert [how for _, how in minted] == ["normalized"] * len(INDELS)
    assert [vrs_id for vrs_id, _ in minted] == _ids_from_the_raw_proxy()
    assert len(reference.sequence_reads) == len(INDELS), reference.sequence_reads


def test_an_allele_minted_twice_in_a_run_is_read_once():
    reference = _CountingReference()
    minter = VrsMinter(sequences=_Sequences(reference))
    first = minter.mint(*INDELS[0])
    second = minter.mint(*INDELS[0])
    assert first == second
    assert len(reference.sequence_reads) == 1


@pytest.mark.parametrize("start", [3, LENGTH - 2])
def test_a_window_clipped_at_a_contig_end_still_mints_what_the_proxy_would(start):
    """A locus near either end gets a shorter window, never a shifted one."""
    reference = _CountingReference()
    minter = VrsMinter(sequences=_Sequences(reference))
    ref = REFERENCE[start - 1]
    vrs_id, how = minter.mint("1", start, ref, ref + "T")
    assert how == "normalized"
    raw = _CountingReference()
    allele = models.Allele(
        location=models.SequenceLocation(
            sequenceReference=models.SequenceReference(refgetAccession=ACCESSION), start=start - 1, end=start
        ),
        state=models.LiteralSequenceExpression(sequence=ref + "T"),
    )
    assert vrs_id == ga4gh_identify(normalize(allele, data_proxy=raw))
