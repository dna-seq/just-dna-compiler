"""RM310: every lane's rebuild adapter returns an outcome when its builder fails, and never raises.

`cache rebuild` and `rebuild_caches` loop over the lanes with no per-lane backstop, so an adapter
that lets an error through leaves every later lane unbuilt and unreported. CPIC did: its client's
`CpicError` (a transport failure or a 5xx) passed through `_rebuild_cpic`'s handler.

The lanes are walked off `CACHE_LANES`. The table below says, per lane, which call to make fail and
with which of the builder's documented types, and a set-equality guard makes a new lane with an
adapter fail here until someone states its errors.
"""

from pathlib import Path

import pytest
from just_dna_enricher import (
    acmg_build,
    civic_build,
    clinpgx_build,
    clinvar_build,
    constraint_build,
    cpic,
    cpic_build,
    drug_labels_build,
    mane_build,
    mitomap,
    mitomap_build,
    mitomap_miss_build,
    pharmvar,
    pharmvar_build,
    pubmind_build,
    strchive_build,
)
from just_dna_enricher.caches import CACHE_LANES, RebuildRequest

#: lane → (module, the first builder call the adapter makes, the error that call is documented to raise).
#: A lane appears once per error family its builder can raise; CPIC's two are the incident.
_FAILURES: dict[str, list[tuple[object, str, Exception]]] = {
    "clinvar": [(clinvar_build, "download_clinvar_vcf", clinvar_build.ClinVarBuildError("x"))],
    "constraint": [(constraint_build, "download_constraint_tsv", constraint_build.ConstraintBuildError("x"))],
    "clinpgx": [(clinpgx_build, "download_clinpgx_zip", clinpgx_build.ClinPgxArchiveError("x"))],
    "cpic": [
        (cpic_build, "build_snapshot", cpic_build.CpicBuildError("x")),
        (cpic_build, "build_snapshot", cpic.CpicError("CPIC answered 503")),
    ],
    "drug_labels": [(drug_labels_build, "download_drug_labels_zip", drug_labels_build.DrugLabelError("x"))],
    "pharmvar": [(pharmvar_build, "build_snapshot", pharmvar.PharmVarError("x"))],
    "pubmind": [(pubmind_build, "download_pubmind_table", pubmind_build.PubMindBuildError("x"))],
    "civic": [(civic_build, "download_civic_file", civic_build.CivicBuildError("x"))],
    "strchive": [(strchive_build, "build_strchive_snapshot", strchive_build.StrchiveError("x"))],
    "mitomap": [(mitomap_build, "download_mitomap_dump", mitomap.MitomapError("x"))],
    "mitomap_miss": [(mitomap_miss_build, "build_miss_snapshot", mitomap.MitomapError("x"))],
    "mane": [(mane_build, "download_mane_file", mane_build.ManeBuildError("x"))],
    "acmg": [(acmg_build, "build_acmg_snapshot", acmg_build.AcmgSfError("x"))],
}

_ADAPTED = {lane.name: lane for lane in CACHE_LANES if lane.rebuild is not None}


def test_every_lane_with_an_adapter_has_its_errors_stated() -> None:
    assert set(_FAILURES) == set(_ADAPTED)


@pytest.mark.parametrize(
    ("lane_name", "module", "call", "error"),
    [(name, *failure) for name, failures in _FAILURES.items() for failure in failures],
    ids=lambda v: v if isinstance(v, str) else type(v).__name__,
)
def test_a_failing_builder_is_a_failed_outcome_never_a_raise(
    lane_name: str,
    module: object,
    call: str,
    error: Exception,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(module, call, fail)
    # Past every designed skip, so the adapter reaches the call: a use the licence gates accept, a
    # key for PharmVar, a pin for the pinned lanes, a workbook for ACMG, parents for the derived lane.
    monkeypatch.setenv(pharmvar.API_KEY_ENV, "a-key-the-stub-never-sends")
    workbook = tmp_path / "acmg_sf_v3.3.xlsx"
    workbook.write_bytes(b"")
    request = RebuildRequest(
        out_dir=tmp_path / lane_name,
        declared_use="non_commercial",
        pin="2026-01-01" if lane_name != "mane" else "1.4",
        source=workbook if lane_name == "acmg" else None,
        parents={"mitomap": tmp_path / "mitomap", "clinvar": tmp_path / "clinvar"},
    )
    outcome = _ADAPTED[lane_name].rebuild(request)
    assert outcome.built is False, outcome
    assert str(error) in outcome.detail
