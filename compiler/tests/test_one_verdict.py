"""`validate` and `compile` reach one verdict, and a refused compile writes nothing (RM367).

**The class.** A check runs on one path and not the other, or after a side effect. `validate_spec` is the
author's pre-flight for `compile_module` (`@validate-refuses-all`), so a check only the compile runs is a
green pre-flight followed by a refusal or a warning nobody saw coming; and a refusal reached after
`output_dir.mkdir()` leaves a half-written artifact behind it. Three instances were reported (a malformed
`provenance.json` refused after the parquets were written; `--no-resolve` reading, verifying and counting
the table its warning says was not read; two resolution ladders pinned compile-only "because they read
resolved rows") and the hunt found more: `validate --strict` passing an rsID-only module on GRCh37 or under
`--no-resolve` that `compile --strict` refuses, a `provenance.json` that is not UTF-8 escaping as an
exception, and the warning-only checks the compile ran over its resolved rows and the pre-flight never did.

**The guards, each an equality.** Over the reference examples and the bad fixtures below, in both modes and
with the resolution switch both ways: the verdicts are equal, and the warning codes are equal (read off
`warnings_summary`, which is classified before pydantic flattens a `CodedWarning` to `str`). A refused
compile leaves its output directory absent. `--no-resolve` with a `resolution.csv` beside the spec compiles
the artifact the same spec compiles with the table deleted. The static half — every check function each
path calls, against the roster in `check_paths` — is `test_check_paths.py`.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.base import derive_variant_key
from just_dna_format.manifest import read_manifest

_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES = _ROOT / "reference_examples"
_HFE = _EXAMPLES / "hfe_hemochromatosis"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: rm367\n  title: RM367\n  description: one verdict\n  report_title: RM367\n"
    "genome_build: {build}\n"
)
_RES_HEADER = "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
#: The real GRCh38 HFE C282Y locus.
_HFE_RES = _RES_HEADER + "rs1800562,rs1800562,6,26092913,G,A,GRCh38,0,authored,resolved\n"
_RSID_ONLY = "rsid,genotype,state,conclusion\nrs1800562,A/A,risk,c\n"
_STUDY = "rsid,pmid\nrs1800562,16199547\n"
_KEY_5_500 = derive_variant_key(None, "5", 500, "C", "G")


@dataclass(frozen=True)
class Fixture:
    name: str
    files: dict[str, str | bytes] = field(default_factory=dict)
    #: Copy this reference example first, then write `files` over it.
    base: Path | None = None
    build: str = "GRCh38"


def _vrs_tampered() -> str:
    """HFE's own `resolution.csv` with the first recorded `vrs_id` replaced by one it does not recompute to."""
    lines = (_HFE / "resolution.csv").read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    column = header.index("vrs_id")
    for number, line in enumerate(lines[1:], start=1):
        cells = line.split(",")
        if cells[column].startswith("ga4gh:VA."):
            cells[column] = "ga4gh:VA.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            lines[number] = ",".join(cells)
            break
    return "\n".join(lines) + "\n"


#: One bad input per instance the hunt found, plus the warning-only checks that ran on one path.
FIXTURES = [
    Fixture("provenance_malformed", {"provenance.json": '{"generator": 5, "items": "no"}'}, base=_HFE),
    Fixture("provenance_not_utf8", {"provenance.json": b"\xff\xfe{}"}, base=_HFE),
    Fixture("grch37_rsid_only", {"variants.csv": _RSID_ONLY, "studies.csv": _STUDY}, build="GRCh37"),
    Fixture(
        "grch37_rsid_only_with_table",
        {"variants.csv": _RSID_ONLY, "studies.csv": _STUDY, "resolution.csv": _HFE_RES},
        build="GRCh37",
    ),
    Fixture("rsid_only_no_table", {"variants.csv": _RSID_ONLY, "studies.csv": _STUDY}),
    Fixture("vrs_tampered", {"resolution.csv": _vrs_tampered()}, base=_HFE),
    Fixture(
        "locus_cannot_host_genotype",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\nrs999,,,,,C/G,risk,c\n",
            "studies.csv": "rsid,pmid\nrs999,29165669\n",
            "resolution.csv": _RES_HEADER
            + "rs999,rs999,5,500,C,G,GRCh38,0,manual,resolved\nrs999,rs999,6,600,A,T,GRCh38,1,manual,resolved\n",
        },
    ),
    Fixture(
        "rsid_coordinate_disagrees",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\nrs777,7,700,C,G,C/G,risk,c\n",
            "studies.csv": "rsid,pmid\nrs777,29165669\n",
            "resolution.csv": _RES_HEADER + "rs777,rs777,9,900,C,G,GRCh38,0,manual,resolved\n",
        },
    ),
    Fixture(
        # An rsID expanding onto two loci, one of which an authored coordinate row already states with the
        # same genotype: the expansion mints a duplicate `(variant_key, genotype)`.
        "expansion_collides_with_an_authored_row",
        {
            "variants.csv": "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs999,,,,,C/G,risk,c\n,5,500,C,G,C/G,risk,c\n",
            "studies.csv": "rsid,chrom,start,ref,pmid\nrs999,,,,29165669\n,5,500,C,29165669\n",
            "resolution.csv": _RES_HEADER
            + "rs999,rs999,5,500,C,G,GRCh38,0,manual,resolved\nrs999,rs999,6,600,C,G,GRCh38,1,manual,resolved\n",
        },
    ),
    Fixture(
        "mt_rsid_only_diploid",
        {
            "variants.csv": "rsid,genotype,state,conclusion\nrs199474657,A/G,risk,c\n",
            "studies.csv": "rsid,pmid\nrs199474657,29165669\n",
            "resolution.csv": _RES_HEADER + "rs199474657,rs199474657,MT,3243,A,G,GRCh38,0,manual,resolved\n",
        },
    ),
    Fixture(
        "frequency_orphan_and_ba1",
        {
            "frequencies.csv": "variant_key,rsid,chrom,start,ref,alt,genome_build,population,allele_count,"
            "allele_number,dataset,source,status\n"
            "rs1800562,rs1800562,6,26092913,G,A,GRCh38,global,90000,1000000,gnomad_v4.1_joint,gnomad,resolved\n"
            f"{_KEY_5_500},,5,500,C,G,GRCh38,global,3,1613660,gnomad_v4.1_joint,gnomad,resolved\n",
        },
        base=_HFE,
    ),
    Fixture(
        "clinical_assertion_orphan",
        {
            "clinical_assertions.csv": "variant_key,rsid,chrom,start,ref,alt,genome_build,clin_sig,dataset,"
            "source,status\n"
            f"{_KEY_5_500},,5,500,C,G,GRCh38,pathogenic,clinvar_2026-06-27,clinvar,resolved\n",
        },
        base=_HFE,
    ),
    Fixture(
        "gwas_effect_orphan",
        {
            "gwas_effects.csv": "association_id,variant_key,rsid,effect_allele,effect_size,dataset,source,status\n"
            "GCST000001,rs999999999,rs999999999,A,0.12,gwas_catalog_2026-06,gwas_catalog,resolved\n",
        },
        base=_HFE,
    ),
    Fixture(
        "source_row_unused",
        {
            "sources.csv": (_HFE / "sources.csv").read_text(encoding="utf-8")
            + "gnomad,frequency,ODbL-1.0,https://gnomad.broadinstitute.org/terms,,gnomAD,,true,true,true,"
            "unstated,gnomad_v4.1,,\n",
        },
        base=_HFE,
    ),
    Fixture("log_not_shipped", {"logs/run.exe": b"MZ\x00"}, base=_HFE),
]


def _spec(root: Path, fixture: Fixture) -> Path:
    spec = root / "spec"
    if fixture.base is not None:
        shutil.copytree(fixture.base, spec)
    else:
        spec.mkdir(parents=True)
        (spec / "module_spec.yaml").write_text(_YAML.format(build=fixture.build), encoding="utf-8")
    for name, body in fixture.files.items():
        path = spec / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, bytes):
            path.write_bytes(body)
        else:
            path.write_text(body, encoding="utf-8")
    return spec


def _examples() -> list[Path]:
    return sorted(p for p in _EXAMPLES.iterdir() if (p / "module_spec.yaml").is_file())


_MODES = [(strict, resolve) for strict in (False, True) for resolve in (True, False)]


def _assert_one_verdict(spec: Path, out: Path, *, strict: bool, resolve: bool) -> bool:
    validated = validate_spec(spec, strict=strict, resolve_with_ensembl=resolve)
    compiled = compile_module(spec, out, strict=strict, resolve_with_ensembl=resolve)
    assert validated.valid == compiled.success, (
        f"validate.valid={validated.valid} but compile.success={compiled.success}\n"
        f"validate errors: {validated.errors}\ncompile errors: {compiled.errors}"
    )
    assert set(validated.warnings_summary) == set(compiled.warnings_summary), (
        f"compile-only codes: {sorted(set(compiled.warnings_summary) - set(validated.warnings_summary))}; "
        f"validate-only codes: {sorted(set(validated.warnings_summary) - set(compiled.warnings_summary))}"
    )
    if not compiled.success:
        assert not out.exists(), f"a refused compile left {sorted(p.name for p in out.iterdir())} behind"
    return compiled.success


@pytest.mark.parametrize(("strict", "resolve"), _MODES, ids=lambda v: str(v))
@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.name)
def test_a_bad_fixture_gets_one_verdict(
    fixture: Fixture, strict: bool, resolve: bool, tmp_path: Path
) -> None:
    _assert_one_verdict(_spec(tmp_path, fixture), tmp_path / "out", strict=strict, resolve=resolve)


@pytest.mark.parametrize(("strict", "resolve"), _MODES, ids=lambda v: str(v))
@pytest.mark.parametrize("example", _examples(), ids=lambda p: p.name)
def test_a_reference_example_gets_one_verdict(
    example: Path, strict: bool, resolve: bool, tmp_path: Path
) -> None:
    _assert_one_verdict(example, tmp_path / "out", strict=strict, resolve=resolve)


def test_the_fixtures_refuse_where_they_were_reported_to(tmp_path: Path) -> None:
    """The discriminating half: the equality above holds for a pair that both accept everything, so the
    refusing fixtures are pinned as refusing, on both paths."""
    refused = {
        "provenance_malformed": {(s, r) for s, r in _MODES},
        "provenance_not_utf8": {(s, r) for s, r in _MODES},
        "grch37_rsid_only": {(True, True), (True, False)},
        "rsid_only_no_table": {(True, True), (True, False)},
        # Under `--no-resolve` an rsID-only row is unplaced, which `strict` refuses on its own account.
        "locus_cannot_host_genotype": {(True, True), (True, False)},
        "rsid_coordinate_disagrees": {(True, True)},
        "expansion_collides_with_an_authored_row": {(False, True), (True, True), (True, False)},
    }
    by_name = {f.name: f for f in FIXTURES}
    for name, modes in refused.items():
        for strict, resolve in _MODES:
            spec = _spec(tmp_path / f"{name}_{strict}_{resolve}", by_name[name])
            valid = validate_spec(spec, strict=strict, resolve_with_ensembl=resolve).valid
            assert valid is ((strict, resolve) not in modes), (name, strict, resolve)


# ── the off switch: `--no-resolve` with a table is the table absent ──────────────────────────────


def _with_tables() -> list[Fixture]:
    examples = [Fixture(p.name, base=p) for p in _examples() if (p / "resolution.csv").is_file()]
    return [*examples, next(f for f in FIXTURES if f.name == "vrs_tampered")]


def _artifact(out: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(out.glob("*.parquet"))}


@pytest.mark.parametrize("fixture", _with_tables(), ids=lambda f: f.name)
def test_no_resolve_compiles_what_the_spec_compiles_without_its_table(
    fixture: Fixture, tmp_path: Path
) -> None:
    """`@off-switch-needs-a-probe`: run the disabling value and compare it with the thing it disables.

    `resolve_with_ensembl=False` says the injected table is not consulted. So the artifact, the manifest's
    resolution facts and the verdict must be the ones the same spec reaches with the table deleted. Before
    RM367 the table was still overlaid, VRS-verified (a tampered id refused) and counted
    (`vrs_alleles_identified` non-zero while no id reached a parquet).
    """
    present = _spec(tmp_path / "present", fixture)
    absent = _spec(tmp_path / "absent", fixture)
    (absent / "resolution.csv").unlink()

    with_table = compile_module(present, tmp_path / "out_present", resolve_with_ensembl=False)
    without = compile_module(absent, tmp_path / "out_absent", resolve_with_ensembl=False)

    assert with_table.success == without.success, (with_table.errors, without.errors)
    assert validate_spec(present, resolve_with_ensembl=False).valid == with_table.success
    if not with_table.success:
        return
    assert _artifact(tmp_path / "out_present") == _artifact(tmp_path / "out_absent")
    a = read_manifest(tmp_path / "out_present" / "manifest.json").compilation
    b = read_manifest(tmp_path / "out_absent" / "manifest.json").compilation
    for name in (
        "vrs_alleles",
        "vrs_alleles_identified",
        "vrs_version",
        "resolution_signature",
        "resolution_sources",
        "resolution_mode",
        "fully_resolved",
    ):
        assert getattr(a, name) == getattr(b, name), name
    assert with_table.warnings_summary.get("resolution_disabled") == 1
