"""The non-diploid guardrail, made coordinate-aware (0.5.1).

Found by dogfooding a pseudoautosomal module. The check had a false positive and a false negative,
and they share a root: it ran on **authored** rows, where `chrom` is whatever the author happened to
write, so its coverage depended on authoring style rather than on the data.

* **False negative.** It lived inside `_cross_validate_variants`, which compile calls twice — once
  pre-resolution and once post, the second time taking *errors only*. So an rsID-authored MT or Y row
  was never checked at all. That is the shape every drafting provider emits.
* **False positive.** The code claimed Y was "the safe, false-positive-free half of non-PAR X/Y". PAR1
  and PAR2 recombine with X and are diploid in every karyotype, so a two-allele genotype there is
  correct and the advice to use a single allele would have made the annotation wrong.

Coordinates are real and live-verified (Ensembl, 2026-08-03): `rs6603251` maps to X:359845 *and*
Y:359845 (PAR1), `rs700442` to X:155767377 and Y:56953897 (PAR2), `rs2534636` to Y:2789135 (MSY),
`rs199474657` to MT:3243 (MELAS m.3243A>G).
"""

from pathlib import Path

import pytest

from just_dna_compiler.compiler import _check_contig_ploidy, compile_module, validate_spec
from just_dna_compiler.resolution import _expansion_warning
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import in_pseudoautosomal_region

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: ploidy\n  title: P\n  description: d\n  report_title: P\n"
)


def _variant(**kwargs) -> VariantRow:
    payload = {"genotype": "C/T", "state": "risk", "conclusion": "c", **kwargs}
    return VariantRow(**payload)


def _spec(tmp_path: Path, variants: str, studies: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(variants, encoding="utf-8")
    (spec / "studies.csv").write_text(studies, encoding="utf-8")
    return spec


# ── the PAR table itself ───────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "chrom, start, expected",
    [
        ("Y", 359845, True),        # PAR1, and the same base as X:359845
        ("X", 359845, True),        # PAR1 has identical coordinates on both contigs in GRCh38
        ("Y", 56953897, True),      # PAR2 on Y
        ("X", 155767377, True),     # PAR2 on X — a *different* coordinate from Y's
        ("Y", 2789135, False),      # male-specific region, genuinely hemizygous
        ("Y", 2781479, True),       # the last base of PAR1, inclusive
        ("Y", 2781480, False),      # the first base after it
        ("MT", 3243, None),         # no PAR on MT, and the table says so by absence
        ("7", 117559591, None),     # an autosome has no PAR question
    ],
)
def test_the_par_table_answers_three_ways(chrom, start, expected) -> None:
    assert in_pseudoautosomal_region(chrom, start) is expected


def test_a_build_without_a_par_table_withholds_rather_than_guessing() -> None:
    """Unlike `refget_accession`, which raises: that answer would corrupt an identity, this one only
    feeds a warning, where the honest degradation is to say nothing."""
    assert in_pseudoautosomal_region("Y", 359845, build="GRCh37") is None
    assert in_pseudoautosomal_region("Y", None) is None


# ── the guardrail ──────────────────────────────────────────────────────────────────────────────


def test_a_par_locus_with_a_diploid_genotype_is_correct_and_silent() -> None:
    """The false positive. Both of these are real loci, diploid in every karyotype."""
    par1 = _variant(rsid="rs6603251", chrom="Y", start=359845)
    par2 = _variant(rsid="rs700442", chrom="Y", start=56953897)
    assert _check_contig_ploidy([par1, par2]) == []


def test_a_male_specific_y_locus_still_warns() -> None:
    """Without this the fix would be indistinguishable from deleting the check."""
    (warning,) = _check_contig_ploidy([_variant(rsid="rs2534636", chrom="Y", start=2789135)])
    assert "not diploid here" in warning and "single-allele" in warning


def test_mt_never_depends_on_a_coordinate() -> None:
    """MT has no pseudoautosomal region at all, so its verdict is unconditional."""
    (warning,) = _check_contig_ploidy(
        [_variant(chrom="MT", start=3243, ref="A", alts="G", genotype="A/G")]
    )
    assert "chrom=MT" in warning
    assert _check_contig_ploidy(
        [_variant(chrom="MT", start=3243, ref="A", alts="G", genotype="G")]
    ) == []


def test_x_is_still_never_warned_about() -> None:
    """Diploid in XX samples, so warning on X would be pure noise — including outside the PAR."""
    assert _check_contig_ploidy([_variant(chrom="X", start=66605144)]) == []


def test_an_unknown_build_reports_both_readings_and_asserts_neither() -> None:
    (warning,) = _check_contig_ploidy([_variant(chrom="Y", start=359845)], "GRCh37")
    assert "GRCh37" in warning and "could not be decided" in warning
    assert "Outside PAR1/PAR2" in warning and "inside them" in warning


def test_an_unresolved_row_says_nothing() -> None:
    """No `chrom` yet, so there is no contig to judge. Not a finding, not a silence about one."""
    assert _check_contig_ploidy([_variant(rsid="rs199474657", genotype="A/G")]) == []


# ── the two passes ─────────────────────────────────────────────────────────────────────────────


_MT_BY_RSID = "rsid,genotype,state,conclusion,gene\nrs199474657,A/G,risk,MELAS m.3243A>G,MT-TL1\n"
_MT_STUDY = "rsid,pmid\nrs199474657,1738844\n"
_MT_BY_COORD = (
    "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "MT,3243,A,G,A/G,risk,MELAS m.3243A>G,MT-TL1\n"
)
_MT_COORD_STUDY = "chrom,start,ref,pmid\nMT,3243,A,1738844\n"
_RESOLUTION = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
    "rs199474657,rs199474657,MT,3243,A,G,GRCh38,0,ensembl-rest,resolved\n"
)


def test_a_hand_written_coordinate_is_still_caught_by_validate(tmp_path: Path) -> None:
    """`validate` has no resolution step, so it must keep its own pass — moving the check wholesale
    into compile would have silently emptied the standalone command."""
    spec = _spec(tmp_path, _MT_BY_COORD, _MT_COORD_STUDY)
    warnings = [w for w in validate_spec(spec).warnings if "not diploid" in w]
    assert len(warnings) == 1


def test_an_rsid_authored_row_is_caught_once_resolution_supplies_the_contig(tmp_path: Path) -> None:
    """The false negative, on the real MELAS variant. `validate` cannot see it — there is no contig
    yet — and that is honest; the compile, which resolves, must."""
    spec = _spec(tmp_path, _MT_BY_RSID, _MT_STUDY)
    (spec / "resolution.csv").write_text(_RESOLUTION, encoding="utf-8")

    assert not [w for w in validate_spec(spec).warnings if "not diploid" in w]

    # `resolve_with_ensembl` gates the whole resolution step, including the offline
    # resolution.csv path — leaving it on costs no network here because the table is injected.
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    warnings = [w for w in result.warnings if "not diploid" in w]
    assert len(warnings) == 1 and "chrom=MT" in warnings[0]


def test_a_row_both_passes_can_see_is_warned_about_once(tmp_path: Path) -> None:
    """Compile starts from `validate`'s warnings, so running the check in both places must not
    double-report a hand-written coordinate."""
    spec = _spec(tmp_path, _MT_BY_COORD, _MT_COORD_STUDY)
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    assert len([w for w in result.warnings if "not diploid" in w]) == 1


def test_a_one_to_many_par_rsid_expands_to_a_y_row_that_is_not_warned_about(tmp_path: Path) -> None:
    """The end-to-end false positive: the author wrote one rsID and never chose the Y row at all.

    `rs6603251` really does map to both contigs at the same base, so resolution produces an X row and
    a Y row. Before the fix the Y one was told its correct diploid genotype was wrong.
    """
    variants = "rsid,genotype,state,conclusion,gene\nrs6603251,C/T,risk,PAR1 locus,PLCXD1\n"
    spec = _spec(tmp_path, variants, "rsid,pmid\nrs6603251,10453733\n")
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        "rs6603251,rs6603251,X,359845,T,C,GRCh38,0,ensembl-rest,resolved\n"
        "rs6603251,rs6603251,Y,359845,T,C,GRCh38,1,ensembl-rest,resolved\n",
        encoding="utf-8",
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    # The expansion really did happen — otherwise this would pass vacuously.
    assert any("2 loci" in w for w in result.warnings), result.warnings
    assert not [w for w in result.warnings if "not diploid" in w]


# ── describing the expansion: which KIND of many is it? (RM32) ──────────────────────────────────


def _locus(chrom: str, start: int, ref: str, alts: str, index: int) -> ResolutionRow:
    return ResolutionRow(
        variant_key="k", rsid="rs1", chrom=chrom, start=start, ref=ref, alts=alts,
        genome_build="GRCh38", locus_index=index, source="ensembl-rest", status="resolved",
    )


def test_a_pseudoautosomal_expansion_is_named_as_one_place() -> None:
    """PAR1, where the two contigs share a coordinate. `rs137852556`, a real SHOX variant."""
    loci = [_locus("X", 640851, "C", "T", 0), _locus("Y", 640851, "C", "T", 1)]
    message = _expansion_warning("rs137852556", loci, "GRCh38")
    assert "pseudoautosomal" in message
    assert "2 loci (X:640851 and Y:640851) that are 1 place(s)" in message
    assert "count distinct findings by rsid" in message
    assert "hard-masks the Y PAR" in message


def test_a_par2_expansion_is_recognised_at_its_own_coordinates() -> None:
    """The two contigs do NOT share a coordinate in PAR2, so nothing about "the same base" finds this.
    `rs184115031`, a real SPRY3 variant: X:155773979 and Y:56960499."""
    loci = [_locus("X", 155773979, "A", "G", 0), _locus("Y", 56960499, "A", "G", 1)]
    message = _expansion_warning("rs184115031", loci, "GRCh38")
    assert "pseudoautosomal" in message and "X:155773979 and Y:56960499" in message


def test_a_paralogous_expansion_keeps_the_generic_message() -> None:
    """Two genuinely distinct places, which is what the expansion was built for. Claiming these were
    one place would be the same error in the other direction."""
    loci = [_locus("5", 500, "A", "T", 0), _locus("6", 600, "A", "T", 1)]
    message = _expansion_warning("rs999", loci, "GRCh38")
    assert "pseudoautosomal" not in message
    assert "maps to 2 loci in the resolution table" in message


def test_a_par_pair_beside_a_third_locus_is_not_called_a_pure_par_expansion() -> None:
    """Mixed expansions exist (a PAR locus plus a patch scaffold). Describing the whole thing as "one
    place" would understate it, so the generic message is the honest one."""
    loci = [
        _locus("X", 640851, "C", "T", 0),
        _locus("Y", 640851, "C", "T", 1),
        _locus("5", 500, "C", "T", 2),
    ]
    assert "pseudoautosomal" not in _expansion_warning("rs1", loci, "GRCh38")


def test_a_differing_allele_at_the_partner_position_is_not_one_place() -> None:
    """Same reasoning as the enricher's fusion guard: partner coordinates say "same place", not "same
    variant", and the message must not assert the stronger claim."""
    loci = [_locus("X", 640851, "C", "T", 0), _locus("Y", 640851, "C", "G", 1)]
    assert "pseudoautosomal" not in _expansion_warning("rs1", loci, "GRCh38")


def test_an_unknown_build_falls_back_to_the_generic_message() -> None:
    """PAR intervals are per-assembly (RM15), so on another build the compiler cannot claim these are
    one place — and must not."""
    loci = [_locus("X", 640851, "C", "T", 0), _locus("Y", 640851, "C", "T", 1)]
    assert "pseudoautosomal" not in _expansion_warning("rs1", loci, "GRCh37")
