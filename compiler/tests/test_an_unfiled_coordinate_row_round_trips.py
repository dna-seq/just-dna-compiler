"""RM451: a coordinate row the module's table never filed comes back from reverse as nothing, not as an invented row.

`resolution_loci` was `None` both where a row's own cells answer and where the table filed nothing, so reverse
rebuilt a table row from the cells of a row authored after the last enrich, and the second lap read a row the
first did not (`resolution_signature` moved). Found restoring `pathogenic_clinvar`'s `11:5226762 C>CAAAG`
(RM449's remedy, the lead's 0.8.9 run); a two-row module with no mirrored site shows the same.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.compiler.reverse import reconstructed_projection

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "pathogenic_clinvar"
_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: rm451\n  title: RM451\n  description: d\n  report_title: RM451\n"
)


def _lap(spec: Path, root: Path) -> tuple:
    first = compile_module(spec, root / "a1")
    assert first.success, first.errors
    reverse_module(root / "a1", root / "rev1")
    second = compile_module(root / "rev1", root / "a2")
    assert second.success, second.errors
    return first, second


def test_a_coordinate_row_the_table_never_filed_laps_to_a_fixed_point(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
        "rs1801133,,,,,A/G,risk,c,MTHFR\n,1,1000,C,T,C/T,risk,d,X\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        "rsid,chrom,start,ref,pmid\nrs1801133,,,,29165669\n,1,1000,C,29165669\n", encoding="utf-8"
    )
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status\n"
        "rs1801133,rs1801133,1,11796321,G,A,GRCh38,0,cache,ensembl,resolved\n",
        encoding="utf-8",
    )
    first, second = _lap(spec, tmp_path)
    assert reconstructed_projection(first.manifest) == reconstructed_projection(second.manifest)
    reversed_keys = [
        line.split(",")[0] for line in (tmp_path / "rev1" / "resolution.csv").read_text().splitlines()[1:]
    ]
    assert reversed_keys == ["rs1801133"], "nothing invented for the row the table never filed"


def test_a_module_that_read_no_table_still_rebuilds_nothing_and_laps(tmp_path: Path) -> None:
    """The other `None`: a module with no `resolution.csv` gets no table back (RM364), and no `[]` either."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n,1,1000,C,T,C/T,risk,d,X\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text("rsid,chrom,start,ref,pmid\n,1,1000,C,29165669\n", encoding="utf-8")
    first, second = _lap(spec, tmp_path)
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert reconstructed_projection(first.manifest) == reconstructed_projection(second.manifest)


@pytest.mark.skipif(not _EXAMPLE.is_dir(), reason="the pathogenic_clinvar example is not in this checkout")
def test_pathogenic_clinvar_before_its_restored_row_was_enriched_laps(tmp_path: Path) -> None:
    """The lead's restore as it stood before its enrich pass: the row authored, the table not yet filing it.

    Built from the committed example by taking the row's own table entry out, as bytes (line endings kept).
    """
    spec = tmp_path / "pathogenic_clinvar"
    shutil.copytree(_EXAMPLE, spec)
    assert b",11,5226762,C,CAAAG," in (spec / "variants.csv").read_bytes(), (
        "the restored row (RM449) is authored"
    )
    table = (spec / "resolution.csv").read_bytes()
    lines = table.splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith(b"11:5226762:C:CAAAG,")]
    assert len(kept) == len(lines) - 1, "the example's table files the restored row once"
    (spec / "resolution.csv").write_bytes(b"".join(kept))
    first, second = _lap(spec, tmp_path)
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.content_signature == second.manifest.content_signature
    assert reconstructed_projection(first.manifest) == reconstructed_projection(second.manifest)
