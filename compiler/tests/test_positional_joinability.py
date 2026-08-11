"""The 0.4 families are materialized verbatim, so an rsid-authored one joins to no VCF (S9).

Resolution is SNP-core-scoped: `compile_module` resolves `variants.csv` and writes every other table
straight through `_build_table`. That is deliberate and stays deliberate here — what was missing is
that nothing said so, so a consumer shipped a 1,482-row pharmacogenomics module whose every row had a
null coordinate and found out by reading parquet.

Expectations are computed from the fixtures at runtime; the counts below are read off the authored
CSVs, never off a data dump.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    _POSITIONAL_TABLE_KINDS,
    _table_row_key,
    compile_module,
    validate_spec,
)
from just_dna_format.base import derive_variant_key
from just_dna_format.pgx import HaplotypeRow, PharmVariantRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_PGX = _EXAMPLES / "pgx_slco1b1_simvastatin"
_STARS = _EXAMPLES / "cyp2c19_star_alleles"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text())))


def _finding(warnings: list[str], csv_name: str) -> str | None:
    hits = [w for w in warnings if w.startswith(f"{csv_name}:") and "joins by rsID only" in w]
    assert len(hits) <= 1, f"one aggregated line per table, got {len(hits)}"
    return hits[0] if hits else None


def test_the_positional_set_is_derived_from_the_models(tmp_path: Path) -> None:
    """A table is positional exactly when it declares both `chrom` and `start` — never a kept list."""
    names = {csv_name for csv_name, _model in _POSITIONAL_TABLE_KINDS}
    assert names == {"heteroplasmy.csv", "haplotypes.csv", "pharm_variants.csv"}
    for _csv_name, model in _POSITIONAL_TABLE_KINDS:
        assert {"chrom", "start"} <= set(model.model_fields)


def test_an_rsid_authored_pgx_module_is_told_it_joins_by_rsid_only() -> None:
    """The reported case, on this tree's own example: compiles clean, no coordinate anywhere."""
    authored = _rows(_PGX / "pharm_variants.csv")
    unplaced = [r for r in authored if not (r.get("chrom") and r.get("start"))]
    assert unplaced, "the fixture must be the rsid-authored shape this check is about"

    finding = _finding(validate_spec(_PGX).warnings, "pharm_variants.csv")
    assert finding is not None
    assert f"{len(unplaced)} of {len(authored)} row(s)" in finding
    # The second count is the actionable half: the coordinates exist, in the injected table.
    assert f"resolution.csv can place {len(unplaced)} of them" in finding
    assert "one half of a coordinate" not in finding, "these rows carry no coordinate at all"


def test_a_half_coordinate_is_counted_apart_because_it_looks_like_a_position() -> None:
    """CPIC publishes a position on `sequence_location` and the chromosome on `gene`, so a drafted
    `haplotypes.csv` carries `start` with no `chrom` — which joins to nothing while looking like it
    would."""
    authored = _rows(_STARS / "haplotypes.csv")
    half = [r for r in authored if r.get("start") and not r.get("chrom")]
    assert half, "the fixture must carry the half-coordinate shape"

    finding = _finding(validate_spec(_STARS).warnings, "haplotypes.csv")
    assert finding is not None
    assert f"{len(half)} carry one half of a coordinate" in finding


def test_validate_and_compile_agree_and_the_compile_says_it_once(tmp_path: Path) -> None:
    """`compile_module` runs `validate_spec` itself, so the sentence must be de-duplicated."""
    validated = _finding(validate_spec(_PGX).warnings, "pharm_variants.csv")
    result = compile_module(_PGX, tmp_path / "out")
    assert result.success
    compiled = [w for w in result.warnings if "joins by rsID only" in w]
    assert len(compiled) == 1
    assert compiled[0] == validated


def _pharm_spec(d: Path, *, coordinates: bool, resolution: bool) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    header = "rsid,gene,genotype,drug,conclusion"
    row = "rs4149056,SLCO1B1,C/C,simvastatin,c"
    if coordinates:
        header += ",chrom,start,ref"
        row += ",12,21178615,T"
    (d / "pharm_variants.csv").write_text(f"{header}\n{row}\n", encoding="utf-8")
    if resolution:
        (d / "resolution.csv").write_text(
            "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
            "rs4149056,rs4149056,12,21178615,T,C,GRCh38,0,manual,resolved,\n",
            encoding="utf-8",
        )
    return d


def test_a_table_that_carries_its_coordinates_is_not_warned_about(tmp_path: Path) -> None:
    """The check is about rows that cannot be joined, not about the table kind."""
    spec = _pharm_spec(tmp_path / "placed", coordinates=True, resolution=True)
    assert _finding(validate_spec(spec).warnings, "pharm_variants.csv") is None


def test_without_a_resolution_table_the_message_does_not_claim_one(tmp_path: Path) -> None:
    """"The coordinates exist and are not applied" and "nothing has resolved this" are different
    situations, and the author's next move differs."""
    spec = _pharm_spec(tmp_path / "bare", coordinates=False, resolution=False)
    finding = _finding(validate_spec(spec).warnings, "pharm_variants.csv")
    assert finding is not None
    assert "no resolution.csv row places them" in finding
    assert "just-dna-enricher enrich" in finding


def test_a_gene_keyed_table_is_never_flagged(tmp_path: Path) -> None:
    """`diplotypes.csv` names a genotype pair, not a locus — it is not unjoinable, it is not positional."""
    warnings = validate_spec(_STARS).warnings
    assert _finding(warnings, "diplotypes.csv") is None
    assert _finding(warnings, "allele_function.csv") is None


def test_the_key_is_derived_the_way_the_enricher_derives_it() -> None:
    """Two spellings of one key would make this check disagree with the table it reads."""
    pharm = PharmVariantRow(rsid="rs4149056", gene="SLCO1B1", genotype="C/C", drug="simvastatin",
                            conclusion="c")
    assert _table_row_key(pharm, "GRCh38") == pharm.variant_key

    # `HaplotypeRow` carries no `variant_key` at all; `enrich._collect_subjects` derives one without
    # `alts`, because a haplotype's defining allele is not its identity.
    hap = HaplotypeRow(haplotype_name="*2", rsid="rs4244285", allele="A", gene="CYP2C19")
    assert _table_row_key(hap, "GRCh38") == derive_variant_key(
        hap.rsid, hap.chrom, hap.start, hap.ref
    )


@pytest.mark.parametrize("spec", [_PGX, _STARS], ids=lambda p: p.name)
def test_the_finding_never_escalates_under_strict(spec: Path, tmp_path: Path) -> None:
    """Rsid-only identity is legal by the model's own rule, and the remedy is a compiler change (RM43),
    not an authored edit — so refusing here would make a correct module uncompilable."""
    result = compile_module(spec, tmp_path / spec.name, strict=True)
    assert result.success, result.errors
    assert [w for w in result.warnings if "joins by rsID only" in w]
