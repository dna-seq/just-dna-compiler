"""RM304, the enricher half: the minting call records the VRS version its library implements.

`ResolutionRow.vrs_spec` is the per-row version (written since 0.5). The minter reads the version
from `ga4gh.vrs.VRS_VERSION`, stores it at the spec's minor (`"2.0.1"` → `"2.0"`, the grain the id
rule changes at), and reports an already-recorded id stated under another version as
`vrs_version_differs` — never re-minting over it and never calling it a mismatch.
"""

import os
from pathlib import Path

import ga4gh.vrs
import pytest
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher.vrs import MINTER_VRS_VERSION, VrsMinter, mint_resolution_rows
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import VRS_SPEC_VERSION, derive_vrs_allele_id, vrs_spec_release

_SICKLE = derive_vrs_allele_id("11", 5227002, "T", "A")
_major, _minor = VRS_SPEC_VERSION.split(".")
_OTHER = f"{_major}.{int(_minor) + 1}"


def test_the_minter_reads_its_version_off_the_library() -> None:
    assert MINTER_VRS_VERSION == vrs_spec_release(ga4gh.vrs.VRS_VERSION)


def test_the_library_and_the_format_tier_implement_one_rule() -> None:
    """The format tier's stdlib mints substitutions; the library mints indels. One row may hold both.

    The day a `ga4gh.vrs` upgrade implements another VRS minor, this goes red before any id moves:
    the compiler's pin (`VRS_SPEC_VERSION`) and the rows the enricher stamps would then disagree,
    and that is a declared re-id the liaison decides, never a silent one.
    """
    assert MINTER_VRS_VERSION == VRS_SPEC_VERSION


def test_a_minted_row_carries_the_version() -> None:
    row = ResolutionRow(variant_key="k", chrom="11", start=5227002, ref="T", alts="A")
    mint_resolution_rows([row], offline=True)
    assert row.vrs_id == _SICKLE
    assert row.vrs_spec == MINTER_VRS_VERSION


def test_an_id_recorded_under_another_version_is_reported_and_left_alone() -> None:
    row = ResolutionRow(
        variant_key="k", chrom="11", start=5227002, ref="T", alts="A", vrs_id=_SICKLE, vrs_spec=_OTHER
    )
    result = mint_resolution_rows([row], offline=True)
    assert (row.vrs_id, row.vrs_spec) == (_SICKLE, _OTHER)
    assert result.version_differs == {_OTHER: 1}
    assert result.mismatches == []
    lines = result.version_warnings()
    assert len(lines) == 1
    assert lines[0].startswith("vrs_version_differs")
    assert _OTHER in lines[0] and MINTER_VRS_VERSION in lines[0]


def test_an_id_recorded_with_no_version_is_unstated_and_never_stamped() -> None:
    """Merge-not-clobber: this run did not mint the id, so it may not claim the id's version."""
    row = ResolutionRow(variant_key="k", chrom="11", start=5227002, ref="T", alts="A", vrs_id=_SICKLE)
    result = mint_resolution_rows([row], offline=True)
    assert row.vrs_spec is None
    assert result.version_differs == {}
    assert result.version_warnings() == []


def test_a_table_written_without_the_column_loads_as_unstated(tmp_path: Path) -> None:
    path = tmp_path / "resolution.csv"
    path.write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,source,status\n"
        f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,0,{_SICKLE},gnomad,resolved\n"
    )
    rows, errors, _ = load_csv_rows(path, ResolutionRow, path.name)
    assert errors == []
    assert rows[0].vrs_spec is None
    result = mint_resolution_rows(rows, offline=True)
    assert rows[0].vrs_spec is None and result.version_differs == {}


@pytest.mark.integration
def test_the_pinned_insertion_mints_its_recorded_id() -> None:
    """`rs72613567` (`4-87310240-T-TA`), the ClinVar-GKM id, under VRS 2.0's repeat-unit rule.

    The ground-truth tests pin substitutions, whose id no VRS minor has moved. An insertion inside a
    repeat is where VRS 2.1 picks a different repeat-unit factor (vrs-python #637, #665), so this is
    the test that turns red when a library upgrade changes the rule.
    """
    if os.getenv("JUST_DNA_NETWORK_TESTS") != "1":
        pytest.skip("needs the live sequence service — set JUST_DNA_NETWORK_TESTS=1 to run")
    row = ResolutionRow(variant_key="rs72613567", chrom="4", start=87310240, ref="T", alts="TA")
    result = mint_resolution_rows([row], minter=VrsMinter())
    assert result.minted_normalized == 1
    assert row.vrs_id == "ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7"
    assert row.vrs_spec == MINTER_VRS_VERSION
