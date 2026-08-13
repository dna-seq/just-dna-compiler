"""What is left unjoinable after the positional fill, and how the module is told (S9, then RM43).

This check shipped in 0.5.3 as *legibility*: resolution was SNP-core-scoped, `compile_module` wrote
every other table straight through `_build_table`, and a consumer shipped a 1,482-row pharmacogenomics
module whose every row had a null coordinate and found out by reading parquet. RM43 closed the gap
itself — `_apply_positional_resolution` runs first now, in both `validate_spec` and `compile_module` —
so what this file pins is the **residue**: a row the injected table does not place, or places at more
than one locus, plus the two contracts that outlive the repair (the derived positional set, and
`UNJOINABLE_PHRASE` as a published string).

The fixtures moved with the behaviour. The two reference examples used to be the demonstration that
the gap existed; they now demonstrate it is closed, and the modules that still warn are ones with no
injected answer — which is the honest remaining case.

Expectations are computed from the fixtures at runtime; the counts below are read off the authored
CSVs, never off a data dump.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    _POSITIONAL_TABLE_KINDS,
    UNJOINABLE_PHRASE,
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


@pytest.mark.parametrize("spec", [_PGX, _STARS], ids=lambda p: p.name)
def test_a_module_whose_table_answers_is_no_longer_warned_about(spec: Path) -> None:
    """The two examples the check was written against. Both are rsid-authored with a `resolution.csv`
    beside them, so after RM43 the coordinates arrive and there is nothing left to report — saying
    otherwise would tell an author to fix something the compiler has already done."""
    assert _finding(validate_spec(spec).warnings, "pharm_variants.csv") is None
    assert _finding(validate_spec(spec).warnings, "haplotypes.csv") is None


def test_a_half_coordinate_is_counted_apart_because_it_looks_like_a_position(
    tmp_path: Path,
) -> None:
    """CPIC publishes a position on `sequence_location` and the chromosome on `gene`, so a drafted
    `haplotypes.csv` carries `start` with no `chrom` — which joins to nothing while looking like it
    would. The fill completes it where the table answers; where nothing does, it is still the more
    deceptive shape and is still counted apart."""
    spec = _pharm_spec(tmp_path / "half", coordinates=False, resolution=False)
    (spec / "pharm_variants.csv").write_text(
        "rsid,gene,genotype,drug,conclusion,start\n"
        "rs4149056,SLCO1B1,C/C,simvastatin,c,21178615\n",
        encoding="utf-8",
    )
    finding = _finding(validate_spec(spec).warnings, "pharm_variants.csv")
    assert finding is not None
    assert "1 carries one half of a coordinate" in finding


def test_validate_and_compile_agree_and_the_compile_says_it_once(tmp_path: Path) -> None:
    """`compile_module` runs `validate_spec` itself, so the sentence must be de-duplicated — and both
    must run the fill, or the pre-flight names a gap the compile has already closed."""
    spec = _pharm_spec(tmp_path / "bare", coordinates=False, resolution=False)
    validated = _finding(validate_spec(spec).warnings, "pharm_variants.csv")
    assert validated is not None
    result = compile_module(spec, tmp_path / "out")
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

    # `HaplotypeRow` stamps the column since 0.6 (RM43); before that it had none at all and
    # `enrich._collect_subjects` derived one inline. The stamped value must be that same expression —
    # without `alts`, because a haplotype's defining allele is not its identity.
    hap = HaplotypeRow(haplotype_name="*2", rsid="rs4244285", allele="A", gene="CYP2C19")
    assert _table_row_key(hap, "GRCh38") == derive_variant_key(
        hap.rsid, hap.chrom, hap.start, hap.ref
    )
    assert hap.variant_key == derive_variant_key(hap.rsid, hap.chrom, hap.start, hap.ref)


def test_the_finding_never_escalates_under_strict(tmp_path: Path) -> None:
    """Rsid-only identity is legal by the model's own rule, and what survives the fill is by
    construction something no authored edit to this table clears — so refusing here would make a
    correct module uncompilable for a reason its author cannot act on."""
    spec = _pharm_spec(tmp_path / "bare", coordinates=False, resolution=False)
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert [w for w in result.warnings if "joins by rsID only" in w]


def test_the_unjoinable_phrase_survives_into_the_manifest(tmp_path: Path) -> None:
    """The sentence is a contract: a catalog substring-matches it to decide a trust badge (S13).

    Reindexing happens from a *published manifest*, where the spec directory is long gone, so the
    warning text is the only surviving record that a table joins to nothing — and `fully_resolved` is
    vacuously true for exactly these modules, so the badge would otherwise be granted. Pinned in both
    places it has to hold: the phrase is emitted verbatim, and it reaches
    `manifest.compilation.warnings` rather than only the caller's return value.
    """
    bare = _pharm_spec(tmp_path / "bare", coordinates=False, resolution=False)
    result = compile_module(bare, tmp_path / "out")
    assert result.success
    assert any(UNJOINABLE_PHRASE in w for w in result.warnings)
    assert any(UNJOINABLE_PHRASE in w for w in result.manifest.compilation.warnings)

    # …and it stays out of a module whose rows carry their coordinates, or the badge would be denied
    # to modules that deserve it — including, since RM43, the ones the compiler placed itself.
    placed = _pharm_spec(tmp_path / "placed", coordinates=True, resolution=True)
    placed_result = compile_module(placed, tmp_path / "out-placed")
    assert not [w for w in placed_result.manifest.compilation.warnings if UNJOINABLE_PHRASE in w]

    filled = _pharm_spec(tmp_path / "filled", coordinates=False, resolution=True)
    filled_result = compile_module(filled, tmp_path / "out-filled")
    assert not [w for w in filled_result.manifest.compilation.warnings if UNJOINABLE_PHRASE in w]


def test_a_skipped_fill_is_reported_even_when_nothing_was_placeable(tmp_path: Path) -> None:
    """The branch order, which used to make the third reading unreachable on its own modules (D2).

    `fill_applied=False` sat in an `elif` behind `if not placeable`, and on a non-GRCh38 module those
    two conditions coincide: the enricher declines to resolve off GRCh38, so `resolution.csv` holds
    only the coordinates the author typed, so nothing places the rsid-only rows. The author was told
    *"no resolution.csv row places them — run `just-dna-enricher enrich` first"* one line below a
    warning saying the fill was skipped **because** their module is GRCh37 — advising a command they
    had just run and which can never place those rows on that build.

    So the fill's own status is now tested first. A remedy that cannot work is worse than no remedy.
    """
    spec = _pharm_spec(tmp_path / "g37", coordinates=False, resolution=True)
    (spec / "module_spec.yaml").write_text(_YAML + "genome_build: GRCh37\n", encoding="utf-8")
    # The injected row is on the module's own build, so it is a legitimate table — it simply is not
    # consulted, because the compiler is GRCh38-bound (RM15).
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
        "rs4149056,rs4149056,12,21284127,T,C,GRCh37,0,manual,resolved,\n",
        encoding="utf-8",
    )
    finding = _finding(validate_spec(spec).warnings, "pharm_variants.csv")
    assert finding is not None
    assert "was not consulted for this table" in finding
    assert "just-dna-enricher enrich" not in finding


def test_the_ordinary_no_table_case_still_recommends_enrich(tmp_path: Path) -> None:
    """The reorder must not swallow the case where re-running enrich genuinely is the fix."""
    spec = _pharm_spec(tmp_path / "bare38", coordinates=False, resolution=False)
    finding = _finding(validate_spec(spec).warnings, "pharm_variants.csv")
    assert finding is not None and "just-dna-enricher enrich" in finding
