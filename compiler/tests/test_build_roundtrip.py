"""`genome_build` must survive `compile → reverse → compile` (CONSTITUTION Principle 7).

`genome_build` is authored `module_spec.yaml` metadata that reaches the artifact through
`manifest.json` and **no parquet column**, and `reverse_module` used to hardcode `"GRCh38"` into both
the re-emitted spec and the re-emitted `resolution.csv`. For every GRCh38 module — which is all of
`reference_examples/` — that is indistinguishable from reading the real value, which is why a green
suite never noticed.

For a `genome_build: GRCh37` module it is not a lost label, it is a false claim. 0.5 fixed the forward
path so a GRCh37 module keys on its coordinate instead of minting a GRCh38 VRS allele id
(`_restamp_for_build`); reverse then relabelled the module GRCh38, and the recompile minted the VA
after all. So the round trip *moved the identity to another assembly* — `artifact.digest` changed, and
the new key asserted an allele at a GRCh38 position the module never named.

Real coordinates throughout: HFE C282Y (`rs1800562`) is chr6:26,093,141 on GRCh37 and chr6:26,092,913
on GRCh38, and 8696333 is the PMID that reported it.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_format.manifest import read_manifest

_C282Y = {"GRCh37": 26_093_141, "GRCh38": 26_092_913}


def _spec(d: Path, build: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(
        "schema_version: '1.0'\n"
        "module:\n"
        f"  name: hfe_{build.lower()}\n"
        f"  title: HFE on {build}\n"
        "  description: HFE C282Y authored on this build's coordinates.\n"
        "  report_title: Report\n"
        f"genome_build: {build}\n",
        encoding="utf-8",
    )
    pos = _C282Y[build]
    (d / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
        f"6,{pos},G,A,A/A,risk,C282Y homozygote,HFE\n",
        encoding="utf-8",
    )
    (d / "studies.csv").write_text(
        f"chrom,start,ref,pmid\n6,{pos},G,8696333\n", encoding="utf-8"
    )
    return d


def _key(artifact: Path) -> str:
    keys = pl.read_parquet(artifact / "weights.parquet")["variant_key"].to_list()
    assert len(keys) == 1
    return keys[0]


@pytest.mark.parametrize("build", ["GRCh37", "GRCh38"])
def test_build_survives_the_round_trip(tmp_path: Path, build: str) -> None:
    """The declared build, the digest, and the identity key are all fixed points, on either build."""
    first = compile_module(_spec(tmp_path / "spec", build), tmp_path / "a1")
    assert first.success, first.errors
    assert read_manifest(tmp_path / "a1" / "manifest.json").genome_build == build

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert f"genome_build: {build}" in (tmp_path / "rev" / "module_spec.yaml").read_text()
    reversed_result = validate_spec(tmp_path / "rev")
    assert reversed_result.valid, reversed_result.errors

    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert read_manifest(tmp_path / "a2" / "manifest.json").genome_build == build
    assert _key(tmp_path / "a1") == _key(tmp_path / "a2")
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.content_signature == second.manifest.content_signature


def test_the_two_builds_key_differently(tmp_path: Path) -> None:
    """GRCh38 mints a VA; GRCh37 has no refget table, so it must fall through to the coordinate.

    This is the property the reverse bug destroyed, stated directly: minting is GRCh38-only (RM15), and
    a build with no table must produce a *coordinate* key rather than a GRCh38-flavoured identity.
    """
    grch38 = compile_module(_spec(tmp_path / "s38", "GRCh38"), tmp_path / "o38")
    grch37 = compile_module(_spec(tmp_path / "s37", "GRCh37"), tmp_path / "o37")
    assert grch38.success and grch37.success
    assert _key(tmp_path / "o38").startswith("ga4gh:VA.")
    assert _key(tmp_path / "o37") == f"6:{_C282Y['GRCh37']}:G:A"


def test_reversing_a_grch37_artifact_as_grch38_relocates_its_identity(tmp_path: Path) -> None:
    """The old behaviour, demonstrated rather than asserted to have been fixed.

    `genome_build="GRCh38"` is passed explicitly here, which is exactly what the hardcoded value did.
    The recompile then mints a `ga4gh:VA.…` — a GRCh38 allele identity for a GRCh37 position — and the
    digest moves. Keeping this case in the suite is what makes the fix a regression test rather than a
    claim: if reverse ever stops consulting the artifact's build, the parametrized test above fails and
    this one still passes, which locates the bug precisely.
    """
    first = compile_module(_spec(tmp_path / "spec", "GRCh37"), tmp_path / "a1")
    assert first.success, first.errors

    reverse_module(tmp_path / "a1", tmp_path / "rev", genome_build="GRCh38")
    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors

    assert _key(tmp_path / "a1") == f"6:{_C282Y['GRCh37']}:G:A"
    assert _key(tmp_path / "a2").startswith("ga4gh:VA.")
    assert first.manifest.artifact.digest != second.manifest.artifact.digest


def test_a_bare_parquet_dir_falls_back_rather_than_inventing(tmp_path: Path) -> None:
    """No manifest, no build — reverse assumes the format's own default and says so by writing it.

    The fallback has to stay explicit: `reverse_module` is documented to work on a parquet directory
    alone (it already invents the title there), and the honest assumption for a directory that records
    nothing is `ModuleSpecConfig`'s default.
    """
    compile_module(_spec(tmp_path / "spec", "GRCh37"), tmp_path / "a1")
    bare = tmp_path / "bare"
    bare.mkdir()
    for parquet in (tmp_path / "a1").glob("*.parquet"):
        (bare / parquet.name).write_bytes(parquet.read_bytes())

    reverse_module(bare, tmp_path / "rev")
    assert "genome_build: GRCh38" in (tmp_path / "rev" / "module_spec.yaml").read_text()


def test_reversed_resolution_csv_carries_the_module_build(tmp_path: Path) -> None:
    """`resolution.csv`'s own `genome_build` column was hardcoded too, and `resolve_from_table`
    filters rows on it — so a mislabelled reversed table is also an unjoinable one."""
    compile_module(_spec(tmp_path / "spec", "GRCh37"), tmp_path / "a1")
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    lines = (tmp_path / "rev" / "resolution.csv").read_text().strip().splitlines()
    header, row = lines[0].split(","), lines[1].split(",")
    assert row[header.index("genome_build")] == "GRCh37"
