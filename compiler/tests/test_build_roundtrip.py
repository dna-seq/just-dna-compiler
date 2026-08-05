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
from pydantic import ValidationError

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


# ── RM36: the build is injected at load, not authored ───────────────────────────────────────────


def test_a_computed_key_uses_the_injected_build(tmp_path: Path) -> None:
    """`HeteroplasmyRow.variant_key` is a *property*, so there is no stored field to re-stamp.

    It passes `alts`, so it can mint a `ga4gh:VA.…` — and before the build was injected at load it
    always took the GRCh38 default, so one locus on a GRCh37 module carried two identities: the
    coordinate key from `variants.csv` and a GRCh38 VA from `heteroplasmy.csv`.
    """
    from just_dna_format.binning import HeteroplasmyRow

    kwargs = {
        "gene": "HFE", "reference_sequence": "NC_012920.1", "chrom": "6",
        "start": _C282Y["GRCh37"], "ref": "G", "alts": "A", "conclusion": "x",
        "measure_min": 0.1, "measure_max": 0.3,
    }
    assert HeteroplasmyRow(**kwargs).variant_key.startswith("ga4gh:VA.")
    told = HeteroplasmyRow(**kwargs).with_genome_build("GRCh37")
    assert told.variant_key == f"6:{_C282Y['GRCh37']}:G:A"


def test_the_injected_build_is_not_an_authored_column(tmp_path: Path) -> None:
    """The whole point of a private attribute: the build stays declared once, in the yaml.

    If it were a column (or a per-CSV service row) two files could disagree about one module-wide
    fact, and it would reach parquet and move every digest. It must also stay unwritable by an author
    — `extra="forbid"` has to keep rejecting it.
    """
    from just_dna_format.binning import HeteroplasmyRow

    assert "genome_build" not in HeteroplasmyRow.model_fields
    assert "_genome_build" not in HeteroplasmyRow.model_fields
    row = HeteroplasmyRow(
        gene="HFE", reference_sequence="NC_012920.1", conclusion="x", measure_min=0.1
    ).with_genome_build("GRCh37")
    assert "genome_build" not in row.model_dump()
    with pytest.raises(ValidationError):
        HeteroplasmyRow(
            gene="HFE", reference_sequence="NC_012920.1", conclusion="x", measure_min=0.1,
            genome_build="GRCh37",
        )


def test_loading_a_table_kind_tells_its_rows_the_build(tmp_path: Path) -> None:
    """End to end through the real loader, which is the only thing that injects it."""
    from just_dna_compiler.compiler import _load_csv_rows
    from just_dna_format.binning import HeteroplasmyRow

    path = tmp_path / "heteroplasmy.csv"
    path.write_text(
        "gene,reference_sequence,chrom,start,ref,alts,measure_min,measure_max,conclusion,unresolved\n"
        f"HFE,NC_012920.1,6,{_C282Y['GRCh37']},G,A,0.1,0.3,x,false\n",
        encoding="utf-8",
    )
    rows, errors, _ = _load_csv_rows(
        path, HeteroplasmyRow, "heteroplasmy.csv", genome_build="GRCh37"
    )
    assert not errors, errors
    assert rows[0].genome_build == "GRCh37"
    assert rows[0].variant_key == f"6:{_C282Y['GRCh37']}:G:A"


# ── content_signature is not build-independent ──────────────────────────────────────────────────


def test_content_signature_separates_two_builds(tmp_path: Path) -> None:
    """Byte-identical CSVs on two assemblies are two different modules, and must not dedup together.

    The docstring called this "build-independent", which was true of the *reference used to resolve*
    and false of the **declared assembly**. The realistic way to hit it: "lift over" a GRCh37 panel by
    editing the yaml and not the coordinates, and a registry keyed on content calls it the same module.
    """
    from just_dna_compiler.compiler import content_signature

    signatures = {}
    for build in ("GRCh37", "GRCh38"):
        spec = tmp_path / build
        spec.mkdir()
        (spec / "module_spec.yaml").write_text(
            "schema_version: '1.0'\n"
            "module:\n  name: same\n  title: T\n  description: d\n  report_title: R\n"
            f"genome_build: {build}\n",
            encoding="utf-8",
        )
        # Deliberately identical bytes in both directories — that is the whole test.
        (spec / "variants.csv").write_text(
            "chrom,start,ref,alts,genotype,state,conclusion\n"
            "6,26093141,G,A,A/A,risk,x\n", encoding="utf-8",
        )
        (spec / "studies.csv").write_text(
            "chrom,start,ref,pmid\n6,26093141,G,8696333\n", encoding="utf-8"
        )
        signatures[build] = content_signature(spec)

    assert (spec.parent / "GRCh37" / "variants.csv").read_bytes() == (
        spec.parent / "GRCh38" / "variants.csv"
    ).read_bytes(), "the fixture must differ only in the declared build"
    assert signatures["GRCh37"] != signatures["GRCh38"]


def test_the_default_build_keeps_its_existing_signature() -> None:
    """The fix is targeted by omitting the default, which is the same rule that already keeps an unset
    optional column out of the hash. Every module published to date is GRCh38, so none of them move —
    without this, `find_versions_by_content` would stop linking a 0.4 module to its own recompile."""
    from just_dna_format.integrity import content_signature as raw_signature
    from just_dna_format.spec import VariantRow

    rows = [VariantRow(
        chrom="6", start=_C282Y["GRCh38"], ref="G", alts="A",
        genotype="A/A", state="risk", conclusion="x",
    )]
    assert raw_signature({"variants.csv": rows}) == raw_signature({"variants.csv": rows}, "GRCh38")
    assert raw_signature({"variants.csv": rows}) != raw_signature({"variants.csv": rows}, "GRCh37")
