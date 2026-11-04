"""RM304: a `vrs_id` says which VRS minted it, and a module pins the version its ids are meant under.

The per-row half is `ResolutionRow.vrs_spec`, which the enricher has written since 0.5 and nothing
read. The pin is `manifest.compilation.vrs_version`. A row whose stated version differs from the pin
is reported as `vrs_version_differs` and is never recomputed: an id minted under another VRS rule is
neither corruption nor a wrong event, so the mismatch error would claim a verdict nobody reached
(`@vrs-three-outcomes`). A row stating no version is the unknown arm and is verified as before
(`@currency-cannot-be-a-column`: a later run never writes a version into an earlier run's row).
"""

import json
from pathlib import Path

import pytest
from just_dna_compiler.compiler import _verify_vrs_ids, compile_module, reverse_module, validate_spec
from just_dna_format.findings import CodedWarning
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import ACTIONABLE_WARNING_CODES, VALID_WARNING_CODES
from just_dna_format.vrs import VRS_SPEC_VERSION, derive_vrs_allele_id, vrs_spec_release

_YAML = """\
schema_version: "1.0"
module:
  name: demo_vrs_version
  title: VRS version
  description: The pin and the per-row version
  report_title: VRS version
defaults:
  curator: tester
  method: manual
genome_build: GRCh38
"""

_VARIANTS = (
    "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "11,5227002,T,A,A/T,risk,Sickle-cell carrier,HBB\n"
    "1,11796321,G,A,A/G,risk,Reduced activity,MTHFR\n"
)

_STUDIES = (
    "chrom,start,ref,pmid,conclusion\n"
    "11,5227002,T,12345678,Sickle-cell trait in carriers\n"
    "1,11796321,G,23456789,Raised homocysteine\n"
)

_SICKLE = derive_vrs_allele_id("11", 5227002, "T", "A")
_MTHFR = derive_vrs_allele_id("1", 11796321, "G", "A")

# A version this compiler's own minting rule is not. Derived from the constant rather than spelled,
# so the test still means "another version" the day the constant moves.
_major, _minor = VRS_SPEC_VERSION.split(".")
_OTHER = f"{_major}.{int(_minor) + 1}"


def _spec(tmp_path: Path, name: str, resolution: str | None) -> Path:
    spec = tmp_path / name
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "studies.csv").write_text(_STUDIES)
    if resolution is not None:
        (spec / "resolution.csv").write_text(resolution)
    return spec


def _resolution(vrs_id: str, vrs_spec: str | None) -> str:
    """One resolved sickle row; `vrs_spec=None` writes a table with NO such column (a pre-RM304 file)."""
    if vrs_spec is None:
        return (
            "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,source,status\n"
            f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,0,{vrs_id},gnomad,resolved\n"
        )
    return (
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,vrs_spec,source,status\n"
        f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,0,{vrs_id},{vrs_spec},gnomad,resolved\n"
    )


def _row(**kw) -> ResolutionRow:
    base = {"variant_key": "k", "chrom": "11", "start": 5227002, "ref": "T", "alts": "A"}
    return ResolutionRow(**{**base, **kw})


def _codes(warnings: list) -> list[str]:
    return [w.code for w in warnings if isinstance(w, CodedWarning)]


# ── the reason ──────────────────────────────────────────────────────────────────────────────────


def test_the_reason_is_a_published_actionable_code() -> None:
    """Re-minting clears it, so it is work an author can do — never a carried limit of the tier."""
    assert "vrs_version_differs" in VALID_WARNING_CODES
    assert "vrs_version_differs" in ACTIONABLE_WARNING_CODES


def test_an_id_under_another_version_is_its_own_reason_and_never_the_mismatch_error() -> None:
    """The stored id differs from what this tier recomputes, and that is NOT corruption here.

    The control row beside it is the same id stated under this compiler's version: that one is a
    mismatch and stays an error, which is what proves the version arm is what changed the outcome.
    """
    differs_errors, differs_warnings = _verify_vrs_ids([_row(vrs_id=_MTHFR, vrs_spec=_OTHER)])
    assert differs_errors == []
    assert _codes(differs_warnings) == ["vrs_version_differs"]
    assert _OTHER in str(differs_warnings[0]) and VRS_SPEC_VERSION in str(differs_warnings[0])
    assert "does not match" not in str(differs_warnings[0])

    control_errors, _ = _verify_vrs_ids([_row(vrs_id=_MTHFR, vrs_spec=VRS_SPEC_VERSION)])
    assert any("does not match the id recomputed" in e for e in control_errors)


def test_one_line_per_stated_version_not_per_row() -> None:
    rows = [_row(variant_key=f"k{i}", vrs_id=_SICKLE, vrs_spec=_OTHER) for i in range(5)]
    errors, warnings = _verify_vrs_ids(rows)
    assert errors == []
    assert _codes(warnings) == ["vrs_version_differs"]
    assert str(warnings[0]).startswith("5 row(s)")
    assert "and 2 more" in str(warnings[0])


@pytest.mark.parametrize(
    "stated",
    [
        VRS_SPEC_VERSION,
        # the library's own spelling (`ga4gh.vrs.VRS_VERSION` is a patch release, e.g. "2.0.1"): the id
        # rule changes at the spec's minor, so a patch spelling is the same rule, never a difference
        f"{VRS_SPEC_VERSION}.1",
        f" {VRS_SPEC_VERSION} ",
    ],
)
def test_the_same_rule_spelled_with_a_patch_is_not_a_difference(stated: str) -> None:
    errors, warnings = _verify_vrs_ids([_row(vrs_id=_SICKLE, vrs_spec=stated)])
    assert (errors, warnings) == ([], [])


def test_an_unreadable_version_differs_and_is_quoted_whole() -> None:
    """A stated value this grammar cannot read is not the unknown arm (that is `None`) and not the pin."""
    errors, warnings = _verify_vrs_ids([_row(vrs_id=_SICKLE, vrs_spec="vrs two")])
    assert errors == []
    assert _codes(warnings) == ["vrs_version_differs"]
    assert "'vrs two'" in str(warnings[0])


def test_a_row_stating_no_version_is_verified_exactly_as_before() -> None:
    """The unknown arm: no version is not a different version, so the recompute still runs."""
    assert _verify_vrs_ids([_row(vrs_id=_SICKLE)]) == ([], [])
    errors, _ = _verify_vrs_ids([_row(vrs_id=_MTHFR)])
    assert any("does not match the id recomputed" in e for e in errors)


# ── through the real compile and validate paths ─────────────────────────────────────────────────


def test_compile_reports_the_reason_in_both_modes_and_validate_agrees(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "differs", _resolution(_MTHFR, _OTHER))
    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"out_{strict}", strict=strict)
        assert result.success, result.errors
        lines = [w for w in result.warnings if "vrs_version_differs" in str(w) or _OTHER in str(w)]
        assert len(lines) == 1, lines  # validate's pre-flight and compile ran it; one line survives
        manifest = json.loads((tmp_path / f"out_{strict}" / "manifest.json").read_text())
        assert manifest["compilation"]["warnings_summary"].get("vrs_version_differs") == 1
    validated = validate_spec(spec)
    assert validated.valid, validated.errors
    assert any(_OTHER in str(w) for w in validated.warnings)


def test_a_table_without_the_column_reads_as_unstated(tmp_path: Path) -> None:
    """Merge-not-clobber: a pre-RM304 `resolution.csv` is the unknown arm, never this run's version."""
    spec = _spec(tmp_path, "no_column", _resolution(_SICKLE, None))
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert not any("vrs_version_differs" in str(w) for w in result.warnings)
    tampered = _spec(tmp_path, "no_column_bad", _resolution(_MTHFR, None))
    refused = compile_module(tampered, tmp_path / "bad")
    assert not refused.success
    assert any("does not match the id recomputed" in e for e in refused.errors)


# ── the pin ─────────────────────────────────────────────────────────────────────────────────────


def test_the_manifest_pins_the_version_when_the_table_carries_an_id(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "pinned", _resolution(_SICKLE, VRS_SPEC_VERSION))
    assert compile_module(spec, tmp_path / "out").success
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["compilation"]["vrs_version"] == VRS_SPEC_VERSION


@pytest.mark.parametrize("resolution", [None, _resolution("", VRS_SPEC_VERSION)], ids=["no_table", "no_id"])
def test_no_id_means_no_pin(tmp_path: Path, resolution: str | None) -> None:
    """`None` is "nothing to pin", never a version nobody minted under."""
    spec = _spec(tmp_path, "unpinned", resolution)
    assert compile_module(spec, tmp_path / "out").success
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["compilation"]["vrs_version"] is None


def test_the_round_trip_is_a_fixed_point_with_the_column_present(tmp_path: Path) -> None:
    """compile → reverse → compile: the digest and the content signature hold with `vrs_spec` stated.

    `reverse_module` rebuilds `resolution.csv` from the parquets and no parquet carries a minted
    `vrs_id` yet, so neither the id nor its version comes back on lap 2; carrying both onto the
    artifact is RM270's (RM241's residual). Lap 1's pin is what this release can publish.
    """
    spec = _spec(tmp_path, "rt", _resolution(_SICKLE, VRS_SPEC_VERSION))
    first = compile_module(spec, tmp_path / "lap1")
    assert first.success, first.errors
    reverse_module(tmp_path / "lap1", tmp_path / "reversed")
    second = compile_module(tmp_path / "reversed", tmp_path / "lap2")
    assert second.success, second.errors
    one = json.loads((tmp_path / "lap1" / "manifest.json").read_text())
    two = json.loads((tmp_path / "lap2" / "manifest.json").read_text())
    assert one["artifact"]["digest"] == two["artifact"]["digest"]
    assert one["content_signature"] == two["content_signature"] is not None
    assert one["compilation"]["vrs_version"] == VRS_SPEC_VERSION


@pytest.mark.parametrize(
    ("stated", "release"),
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("2.0", "2.0"),
        ("2.0.1", "2.0"),
        (" 2.1 ", "2.1"),
        ("02.01", "2.1"),
        ("two", "two"),
    ],
)
def test_the_version_grammar_has_three_arms(stated: str | None, release: str | None) -> None:
    """Unstated → `None`; readable → its `major.minor`; unreadable → itself, which equals no pin."""
    assert vrs_spec_release(stated) == release
