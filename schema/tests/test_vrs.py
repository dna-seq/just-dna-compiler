"""GA4GH VRS allele identity: the stdlib minter, the refget table, and the 0.5 identity switch.

The load-bearing property is **cross-implementation agreement**: our ~20 lines of `hashlib` must
produce the same id as the reference `ga4gh.vrs` library and as the live gnomAD API, or the whole
"content-addressed identity that joins against other people's data" claim is false. So the ground
truth here is not self-generated — the two starred entries below are ids **gnomAD served over the
wire**, and the rest were computed by `ga4gh.vrs` 2.3.3. An `@integration` test re-checks the table
against the library wherever it is installed, and another re-derives the refget accessions from the
public seqrepo REST, so neither a drifting algorithm nor a mistyped accession can ship quietly.
"""

import pytest
from just_dna_format.base import derive_variant_key
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import (
    PAR_GRCh38,
    REFGET_GRCh38,
    REFGET_GRCh38_LENGTHS,
    UnsupportedBuildError,
    derive_vrs_allele_id,
    is_substitution,
    normalize_chrom,
    par_partner,
    refget_accession,
    sha512t24u,
    validate_caid,
    validate_vrs_id,
)

# (chrom, 1-based VCF pos, ref, alt) -> the ga4gh:VA id.
#   * `11:5227002 T>A` (HBB, sickle-cell) and `1:11796321 G>A` (MTHFR) were returned by the LIVE
#     gnomAD API — independent, third-party confirmation of both the algorithm and the accession.
#   * the rest were computed with `ga4gh.vrs` 2.3.3, the reference implementation.
GROUND_TRUTH: dict[tuple[str, int, str, str], str] = {
    ("1", 11796321, "G", "A"): "ga4gh:VA.SOEVGpU16hxYQtJNeRyfq0V-B0rSOGK-",   # * live gnomAD
    ("11", 5227002, "T", "A"): "ga4gh:VA.JGrSjQEcYOJ14vlkvm7sIyYSgHfpC5UG",   # * live gnomAD
    ("11", 5227002, "T", "G"): "ga4gh:VA.e5PJxIQWWaNTNNscgUsYSG6g18D7kQOc",
    ("7", 117559590, "G", "A"): "ga4gh:VA.g6hCjBY-ZKkkJuvmK3dia9Fq0zCNjU7A",
    ("13", 32340301, "A", "G"): "ga4gh:VA.dMu1HnP-6A46n3jcfOYY--MwgCrmBOkq",
    ("X", 31180437, "C", "T"): "ga4gh:VA.P1AYCH2sn7ldWrIqxBURBYrrLWcltV2H",
    ("MT", 3243, "A", "G"): "ga4gh:VA.J9tZBPJHObSDmLtUrywDERwHt2LXGIr-",
    ("22", 50818468, "T", "A"): "ga4gh:VA.k6XY-bZSooen1crqIhh5CAIg5Ub2TosL",
}


# ── the digest primitive ────────────────────────────────────────────────────────────────────────


def test_sha512t24u_is_32_unpadded_base64url_chars() -> None:
    # 24 bytes encodes to exactly 32 base64 characters with no padding — which is why VRS_ID_PATTERN
    # can pin the length and why a digest never carries '='.
    digest = sha512t24u(b"anything at all")
    assert len(digest) == 32
    assert "=" not in digest
    assert set(digest) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )


# ── minting ─────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("coord", "expected"), sorted(GROUND_TRUTH.items()))
def test_mints_the_ground_truth_id(coord: tuple, expected: str) -> None:
    assert derive_vrs_allele_id(*coord) == expected


def test_ground_truth_ids_are_all_distinct() -> None:
    # Cheap but real: the two HBB entries differ only in their ALT, so equal ids here would mean the
    # allele state is not reaching the digest at all — the same-locus collision the 0.5 key fixed.
    assert len(set(GROUND_TRUTH.values())) == len(GROUND_TRUTH)


def test_chrom_prefix_and_mt_spellings_are_equivalent() -> None:
    canonical = derive_vrs_allele_id("11", 5227002, "T", "A")
    assert derive_vrs_allele_id("chr11", 5227002, "T", "A") == canonical
    mt = derive_vrs_allele_id("MT", 3243, "A", "G")
    assert derive_vrs_allele_id("chrM", 3243, "A", "G") == mt
    assert derive_vrs_allele_id("M", 3243, "A", "G") == mt


def test_ref_is_not_part_of_the_allele_digest() -> None:
    # VRS addresses the *place and the alt*; the reference base at a position is a fact of the genome,
    # so it is not serialized. Pinned deliberately, because it is surprising and it is exactly why the
    # compiler carries a separate "inconsistent reference allele" check.
    assert derive_vrs_allele_id("11", 5227002, "T", "A") == derive_vrs_allele_id(
        "11", 5227002, "C", "A"
    )


@pytest.mark.parametrize(
    ("chrom", "start", "ref", "alt", "why"),
    [
        ("11", 5227002, "T", "TA", "insertion — needs justification against the sequence"),
        ("11", 5227002, "TA", "T", "deletion — same"),
        ("11", 5227002, "TA", "GC", "MNV — same"),
        ("11", 5227002, "T", "A,G", "multi-allelic cell names more than one allele"),
        ("11", 5227002, "T", "T", "not a variant"),
        ("11", 5227002, "T", "N", "not an ACGT base"),
        ("11", None, "T", "A", "no coordinate (an unresolved rsid row)"),
        ("GL000009.2", 100, "T", "A", "contig outside the primary assembly"),
        ("11", 0, "T", "A", "position below the 1-based origin"),
        ("MT", 16570, "T", "A", "position past the end of the contig"),
    ],
)
def test_returns_none_rather_than_guessing(
    chrom: str, start: int, ref: str, alt: str, why: str
) -> None:
    assert derive_vrs_allele_id(chrom, start, ref, alt) is None, why


def test_unsupported_build_raises_rather_than_minting_a_grch38_id() -> None:
    # The failure mode this guards against is the quiet one: minting a GRCh38 id for a GRCh37
    # coordinate would produce a well-formed identifier for the wrong place (RM15).
    with pytest.raises(UnsupportedBuildError, match="GRCh37"):
        refget_accession("11", "GRCh37")
    with pytest.raises(UnsupportedBuildError):
        derive_vrs_allele_id("11", 5227002, "T", "A", build="GRCh37")


def test_is_substitution_classifies_the_mintable_case() -> None:
    assert is_substitution("A", "G")
    assert is_substitution("a", "g")  # case-insensitive
    assert not is_substitution("A", "A")
    assert not is_substitution("A", "AG")
    assert not is_substitution("A", None)


# ── the refget table ────────────────────────────────────────────────────────────────────────────


def test_refget_table_covers_the_primary_assembly() -> None:
    expected = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}
    assert set(REFGET_GRCh38) == expected
    assert set(REFGET_GRCh38_LENGTHS) == expected
    # Every accession is a well-formed refget digest, and no two contigs share one.
    assert all(a.startswith("SQ.") and len(a) == 35 for a in REFGET_GRCh38.values())
    assert len(set(REFGET_GRCh38.values())) == len(REFGET_GRCh38)


def test_normalize_chrom_folds_the_spellings_we_accept() -> None:
    assert normalize_chrom("chr7") == "7"
    assert normalize_chrom("chrX") == "X"
    assert normalize_chrom("M") == "MT"
    assert normalize_chrom("  11 ") == "11"
    assert normalize_chrom(None) is None
    assert normalize_chrom("") is None


# ── validators ──────────────────────────────────────────────────────────────────────────────────


def test_validators_accept_well_formed_and_reject_malformed() -> None:
    good = "ga4gh:VA.JGrSjQEcYOJ14vlkvm7sIyYSgHfpC5UG"
    assert validate_vrs_id(good) == good
    assert validate_vrs_id(None) is None
    assert validate_caid("CA125138") == "CA125138"
    for bad in ("VA.JGrSjQEcYOJ14vlkvm7sIyYSgHfpC5UG", "ga4gh:VA.short", "ga4gh:XX." + "a" * 32, ""):
        with pytest.raises(ValueError, match="vrs_id"):
            validate_vrs_id(bad)
    for bad in ("125138", "CA", "ca125138"):
        with pytest.raises(ValueError, match="caid"):
            validate_caid(bad)


# ── the 0.5 identity switch, both branches ──────────────────────────────────────────────────────


def test_resolved_substitution_keys_on_its_va() -> None:
    row = VariantRow(
        chrom="11", start=5227002, ref="T", alts="A", genotype="A/T", state="risk",
        conclusion="carrier",
    )
    assert row.variant_key == GROUND_TRUTH[("11", 5227002, "T", "A")]


@pytest.mark.parametrize(
    ("kwargs", "expected", "why"),
    [
        ({"rsid": "rs334"}, "rs334", "an rsid row keeps its rsid — no coordinate to address"),
        (
            {"chrom": "11", "start": 5227002, "ref": "T"},
            "11:5227002:T",
            "position-only keeps the bare coordinate key",
        ),
        (
            {"chrom": "11", "start": 5226762, "ref": "C", "alts": "CA"},
            "11:5226762:C:CA",
            "an indel cannot be justified offline, so it keeps the coordinate key",
        ),
        (
            {"chrom": "11", "start": 5227002, "ref": "T", "alts": "A,G"},
            "11:5227002:T:A,G",
            "a multi-allelic row has no single allele to name",
        ),
    ],
)
def test_unmintable_rows_keep_the_coordinate_fallback(
    kwargs: dict, expected: str, why: str
) -> None:
    row = VariantRow(genotype="A/A", state="risk", conclusion="x", **kwargs)
    assert row.variant_key == expected, why


def test_position_level_matching_never_mints_a_va() -> None:
    # The invariant the whole switch rests on: *matching* helpers call derive_variant_key WITHOUT
    # alts, so a study at a locus still matches its variant by coordinate even though the variant now
    # keys on a VA. If this ever returned a VA, every study would orphan.
    assert derive_variant_key(None, "11", 5227002, "T") == "11:5227002:T"


def test_switch_is_stable_across_repeated_derivation() -> None:
    # Idempotency (P7): the key is frozen at load, and re-deriving from the same fields must agree —
    # this is what makes compile → reverse → recompile a fixed point.
    first = derive_variant_key(None, "11", 5227002, "T", "A")
    assert first == derive_variant_key(None, "11", 5227002, "T", "A")
    assert first.startswith("ga4gh:VA.")


# ── cross-implementation checks (network / optional dependency) ─────────────────────────────────


@pytest.mark.integration
def test_stdlib_agrees_with_the_reference_library() -> None:
    """Our stdlib digest must equal `ga4gh.vrs`'s for every ground-truth case.

    This is the test that would catch a silent divergence if either side changed its serialization —
    the failure mode that would make every `variant_key` in the ecosystem wrong at once.
    """
    ga4gh_identify = pytest.importorskip("ga4gh.core.identifiers").ga4gh_identify
    vrs_models = pytest.importorskip("ga4gh.vrs").models

    for (chrom, pos, _ref, alt), expected in GROUND_TRUTH.items():
        allele = vrs_models.Allele(
            location=vrs_models.SequenceLocation(
                sequenceReference=vrs_models.SequenceReference(
                    refgetAccession=REFGET_GRCh38[chrom]
                ),
                start=pos - 1,
                end=pos,
            ),
            state=vrs_models.LiteralSequenceExpression(sequence=alt),
        )
        assert ga4gh_identify(allele) == expected
        assert derive_vrs_allele_id(chrom, pos, _ref, alt) == expected


@pytest.mark.integration
def test_refget_table_matches_the_public_seqrepo() -> None:
    """Re-derive every accession from seqrepo's REST aliases.

    A mistyped accession would mint well-formed ids for the wrong sequence, and nothing downstream
    could detect it — so the table is checked against its source rather than trusted. Opt-in: this
    makes 25 live requests, so an ordinary offline run skips it.
    """
    import json
    import os
    import urllib.request

    if not os.getenv("JUST_DNA_NETWORK_TESTS"):
        pytest.skip("makes 25 live seqrepo requests — set JUST_DNA_NETWORK_TESTS=1 to run")

    base = "https://services.genomicmedlab.org/seqrepo/1/metadata/GRCh38:"
    for chrom, accession in sorted(REFGET_GRCh38.items()):
        with urllib.request.urlopen(base + chrom, timeout=30) as response:
            metadata = json.load(response)
        aliases = {a for a in metadata["aliases"] if a.startswith("ga4gh:SQ.")}
        assert f"ga4gh:{accession}" in aliases, f"{chrom}: {accession} not in seqrepo aliases"
        assert metadata["length"] == REFGET_GRCh38_LENGTHS[chrom]


# ── the pseudoautosomal partner mapping (RM32) ───────────────────────────────────────────────────
#
# Coordinates are live-verified against Ensembl, 2026-08-04. PAR1 is coordinate-identical on the two
# contigs in GRCh38; PAR2 is not, which is the case a "same base on X and Y" shortcut would get wrong.


@pytest.mark.parametrize(
    ("chrom", "start", "expected", "why"),
    [
        ("X", 640851, ("Y", 640851), "PAR1 maps at offset 0 — rs137852556, a real SHOX variant"),
        ("Y", 640851, ("X", 640851), "and the mapping is symmetric"),
        ("X", 155770036, ("Y", 56956556), "PAR2 does NOT share coordinates — rs748219607"),
        ("Y", 56956556, ("X", 155770036), "symmetric there too"),
        ("X", 155770003, ("Y", 56956523), "rs1347948851, a second PAR2 point on the same offset"),
        ("X", 10001, ("Y", 10001), "the first base of PAR1, inclusive"),
        ("X", 2781479, ("Y", 2781479), "and the last"),
    ],
)
def test_a_par_locus_names_its_partner(chrom, start, expected, why) -> None:
    assert par_partner(chrom, start) == expected, why


@pytest.mark.parametrize(
    ("chrom", "start", "why"),
    [
        ("X", 2781480, "the first base after PAR1 — XG spans this boundary, so it is a real case"),
        ("X", 155701382, "the base before PAR2 starts — SPRY3 spans this one"),
        ("Y", 2789135, "the male-specific region has no partner"),
        ("7", 117559591, "an autosome is not part of the question"),
        ("MT", 3243, "and neither is the mitochondrion"),
        ("X", None, "no coordinate, so nothing to map"),
    ],
)
def test_a_non_par_locus_withholds_rather_than_guessing(chrom, start, why) -> None:
    assert par_partner(chrom, start) is None, why


def test_another_build_withholds_like_the_par_predicate_does() -> None:
    """`refget_accession` raises for an unknown build because a wrong answer corrupts an identity.
    This one only decides which locus to keep, so the honest degradation is to name no partner and
    leave both — the same choice `in_pseudoautosomal_region` makes."""
    assert par_partner("X", 640851, build="GRCh37") is None


def test_the_paired_intervals_have_equal_length_on_every_contig() -> None:
    """The offset arithmetic is only well-defined because GRCh38's Y PAR is a *copy* of the X PAR.

    This guards the table rather than the function: a future build whose intervals do not pair
    one-to-one would make `par_partner` return a position outside the partner PAR, silently. Asserting
    it here means such a table fails a test instead of corrupting a locus selection.
    """
    x_regions, y_regions = PAR_GRCh38["X"], PAR_GRCh38["Y"]
    assert len(x_regions) == len(y_regions)
    for (x_low, x_high), (y_low, y_high) in zip(x_regions, y_regions, strict=True):
        assert x_high - x_low == y_high - y_low


def test_every_par_position_maps_back_to_itself() -> None:
    """A round trip over both interval endpoints and the midpoints, in both directions."""
    for contig, regions in PAR_GRCh38.items():
        for low, high in regions:
            for position in (low, (low + high) // 2, high):
                partner = par_partner(contig, position)
                assert partner is not None
                assert par_partner(*partner) == (contig, position)
