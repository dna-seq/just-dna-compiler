"""RM268: the live REST rung anchors a one-sided indel, or withholds it — never writes `ref='-'`.

The mapping payloads are the shapes `rest.ensembl.org/variation/human/<rsid>` answered on 2026-09-27,
and the anchor bases are GRCh38 reference bases read from Ensembl's sequence endpoint the same day
(`9:133257521` is `T`, `2:201232808..201232814` is `TAGTAAG`, `7:94431047` is `A`). Domain constants,
not counts: the expected anchored rows follow from them by the VCF left-anchor rule.
"""

import httpx
from just_dna_enricher.ensembl import EnsemblResolver, _loci_from_graphql, _loci_from_rest
from just_dna_enricher.sequences import _left_align
from just_dna_format.vocab import ALLELE_PATTERN

_GRCH38_BASES = {("9", 133257521): "T", ("2", 201232808): "T", ("7", 94431047): "A"}


def _read_base(chrom: str, pos: int) -> str | None:
    return _GRCH38_BASES.get((chrom, pos))


def _unreadable(_chrom: str, _pos: int) -> str | None:
    return None


def _mapping(chrom: str, start: int, end: int, allele_string: str) -> dict:
    return {
        "assembly_name": "GRCh38",
        "seq_region_name": chrom,
        "start": start,
        "end": end,
        "allele_string": allele_string,
    }


# rs8176719, the ABO O1 insertion S117 turned on: REST `start` is the base AFTER the interbase point.
_INSERTION = _mapping("9", 133257522, 133257521, "-/C")
# rs3834129, a one-sided deletion over [start, end].
_DELETION = _mapping("2", 201232809, 201232814, "AGTAAG/-")
# rs3917, several insertions at one interbase point.
_MULTI_INSERTION = _mapping("7", 94431048, 94431047, "-/G/GCTGTCC/GT")


def test_an_insertion_is_anchored_on_the_base_before_it() -> None:
    loci, withheld, _ = _loci_from_rest({"mappings": [_INSERTION]}, _read_base)
    # The VCF spelling ClinVar and dbSNP use for rs8176719.
    assert loci == [{"chrom": "9", "start": 133257521, "ref": "T", "alts": "TC"}]
    assert withheld == 0


def test_a_one_sided_deletion_is_anchored_on_the_base_before_it() -> None:
    loci, withheld, _ = _loci_from_rest({"mappings": [_DELETION]}, _read_base)
    assert loci == [{"chrom": "2", "start": 201232808, "ref": "TAGTAAG", "alts": "T"}]
    assert withheld == 0


def test_every_allele_of_a_multi_allelic_insertion_is_anchored() -> None:
    loci, _, _ = _loci_from_rest({"mappings": [_MULTI_INSERTION]}, _read_base)
    assert loci == [{"chrom": "7", "start": 94431047, "ref": "A", "alts": "AG,AGCTGTCC,AGT"}]


def test_every_written_allele_is_in_the_allele_grammar() -> None:
    """The defect's signature was a `ref` the authored grammar refuses; no anchored locus carries one."""
    loci, _, _ = _loci_from_rest({"mappings": [_INSERTION, _DELETION, _MULTI_INSERTION]}, _read_base)
    alleles = [locus["ref"] for locus in loci] + [a for locus in loci for a in locus["alts"].split(",")]
    assert alleles and all(ALLELE_PATTERN.fullmatch(allele) for allele in alleles)


def test_an_already_anchored_string_passes_through_without_a_base_read() -> None:
    """rs121908745 and rs113993960 answer two-sided strings; nothing to anchor, so nothing is read."""

    def must_not_read(chrom: str, pos: int) -> str | None:
        raise AssertionError(f"read a base for an anchored allele string at {chrom}:{pos}")

    payload = {
        "mappings": [
            _mapping("7", 117559587, 117559592, "ATCATC/ATC"),
            _mapping("7", 117559591, 117559594, "TCTT/T/TCTTCTT"),
        ]
    }
    loci, withheld, _ = _loci_from_rest(payload, must_not_read)
    assert loci == [
        {"chrom": "7", "start": 117559587, "ref": "ATCATC", "alts": "ATC"},
        {"chrom": "7", "start": 117559591, "ref": "TCTT", "alts": "T,TCTTCTT"},
    ]
    assert withheld == 0


def test_an_unreadable_anchor_withholds_the_locus_and_counts_it() -> None:
    loci, withheld, _ = _loci_from_rest(
        {"mappings": [_INSERTION, _mapping("1", 11856377, 11856377, "G/A")]}, _unreadable
    )
    assert loci == [{"chrom": "1", "start": 11856377, "ref": "G", "alts": "A"}]  # the SNV is untouched
    assert withheld == 1


def _rest_only(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if "graphql" in str(request.url):
            return httpx.Response(200, json={"data": {"variant": None}})
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def test_resolve_rsid_answers_the_anchored_locus() -> None:
    resolver = EnsemblResolver()
    resolver._read_base = _read_base
    resolver._client = httpx.Client(transport=_rest_only({"mappings": [_INSERTION]}))
    assert resolver.resolve_rsid("rs8176719") == (
        [{"chrom": "9", "start": 133257521, "ref": "T", "alts": "TC"}],
        "ensembl-rest",
    )


def test_an_answer_with_every_locus_withheld_is_unchecked_not_empty() -> None:
    """The fourth outcome: `None` loci WITH a source. `[]` would read as "Ensembl has no locus"."""
    resolver = EnsemblResolver()
    resolver._read_base = _unreadable
    resolver._client = httpx.Client(transport=_rest_only({"mappings": [_INSERTION]}))
    assert resolver.resolve_rsid("rs8176719") == (None, "ensembl-rest")


def test_a_one_sided_graphql_node_is_handed_to_rest() -> None:
    """GraphQL's indel coordinate convention is unprobed, so its one-sided node is withheld as `[]`,
    which `resolve_rsid` already treats as "try REST"."""
    node = {
        "name": "rs8176719",
        "alleles": [
            {"allele_type": {"value": "reference"}, "reference_sequence": "-"},
            {"allele_type": {"value": "insertion"}, "reference_sequence": "C"},
        ],
        "slice": {"location": {"region_name": "9", "start": 133257522}},
    }
    assert _loci_from_graphql(node) == []

    def handler(request: httpx.Request) -> httpx.Response:
        if "graphql" in str(request.url):
            return httpx.Response(200, json={"data": {"variant": node}})
        return httpx.Response(200, json={"mappings": [_INSERTION]})

    resolver = EnsemblResolver()
    resolver._read_base = _read_base
    resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
    loci, source = resolver.resolve_rsid("rs8176719")
    assert source == "ensembl-rest" and loci[0]["ref"] == "T"


# ── RM273: the registry's anchor is HGVS's 3'-most point; a written row is left-aligned ───────────
#
# GRCh38 bases read from Ensembl's sequence endpoint on 2026-09-27, 1-based inclusive.
_CHR4 = (87310220, "TGGGTGTTCTGTGCTGTACTTACTTCTGTAG")
_CHR2 = (166204460, "CCAAGGTAAAGAAACAAACAAAAAATAAATG")


def _window_over(chrom_seqs: dict[str, tuple[int, str]]):
    def read_window(chrom: str, start: int, end: int) -> str | None:
        first, seq = chrom_seqs[chrom]
        if start < first or end >= first + len(seq):
            return None
        return seq[start - first : end - first + 1]

    return read_window


def _apply(first: int, seq: str, pos: int, ref: str, alt: str) -> str:
    """The haplotype a VCF record spells over a reference window: the event equality check."""
    i = pos - first
    assert seq[i : i + len(ref)] == ref
    return seq[:i] + alt + seq[i + len(ref) :]


def test_rs72613567_is_moved_to_vcf_spelling() -> None:
    clipped = lambda c, s, e: _window_over({"4": _CHR4})(c, max(s, _CHR4[0]), e)  # noqa: E731
    assert _left_align("4", 87310241, "A", "AA", clipped) == ("4", 87310240, "T", "TA")
    assert _apply(*_CHR4, 87310241, "A", "AA") == _apply(*_CHR4, 87310240, "T", "TA")


def test_an_unreadable_window_withholds_rather_than_guessing() -> None:
    assert _left_align("4", 87310241, "A", "AA", lambda _c, _s, _e: None) is None


def test_rs77944059_deletion_moves_to_the_leftmost_equivalent() -> None:
    """RM273 named 166204473 as the left-aligned spelling; the reference says 166204470."""
    read = lambda c, s, e: _window_over({"2": _CHR2})(c, max(s, _CHR2[0]), e)  # noqa: E731
    left = _left_align("2", 166204477, "ACAAA", "A", read)
    assert left == ("2", 166204470, "GAAAC", "G")
    haplotype = _apply(*_CHR2, 166204477, "ACAAA", "A")
    assert _apply(*_CHR2, 166204470, "GAAAC", "G") == haplotype
    assert _apply(*_CHR2, 166204473, "ACAAA", "A") == haplotype  # also equivalent, just not leftmost


def test_an_already_left_aligned_row_is_unchanged() -> None:
    read = lambda c, s, e: _window_over({"4": _CHR4})(c, max(s, _CHR4[0]), e)  # noqa: E731
    assert _left_align("4", 87310240, "T", "TA", read) == ("4", 87310240, "T", "TA")
