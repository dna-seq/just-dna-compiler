"""RM362, amended 2026-11-04: a carried identity's resolved placement is a position the module sits at.

`module_subjects` took each row's position from its own authored `chrom:start:ref` only. An indel has
several valid spellings, so a row authored at one spelling (a right-shifted CPIC haplotype allele) and a
`resolution.csv` placing the same rsID at another (Ensembl's left-aligned one) gave two positions for one
place, and every check asking "does the module sit here" answered from the authored one. The frequency
pass asks gnomAD about the resolution row, so its own row came back "a coordinate no variant in the
module sits at" (NUDT15 `rs1457579126` in `cpic_gene_pairs`, found merging RM364).

The house rule is `@membership-union`: a key's membership is the union of every locus it resolves to.
So every usable locus the module's **own injected** `resolution.csv` files a carried identity under, on
the module's build, joins the row's position. The same mechanism answers BA1's "is this pathogenic
variant common here" and the study join behind `weights.parquet`'s study facts.

Fixtures mirror the NUDT15 shape on synthetic rsIDs, so nothing here depends on RM364's restored row.
Compile and validate run for real; expected sets are read off the module at runtime.
"""

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
import yaml
from just_dna_compiler.compiler import compile_module, load_csv_rows, load_spec_variants, validate_spec
from just_dna_compiler.compiler.positional import _apply_positional_resolution
from just_dna_compiler.compiler.subjects import (
    MODULE_LOCUS_TABLES,
    identity_placements,
    module_subjects,
    row_positions,
)
from just_dna_compiler.compiler.tables import _TABLE_KINDS, study_coordinate_key
from just_dna_format.base import DEFAULT_GENOME_BUILD
from just_dna_format.pgx import HaplotypeRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_ALL = sorted(p.parent.name for p in _EXAMPLES.glob("*/module_spec.yaml"))

#: The NUDT15 shape: CPIC spells the deletion's allele right-shifted, Ensembl left-aligns it.
_HAP_RSID = "rs999362001"
_AUTHORED = ("13", 48040982, None)
_RESOLVED = ("13", 48040978, "AA")

#: The SNP-core shape: an rsID authored beside a coordinate the table spells elsewhere.
_VAR_RSID = "rs999362002"
_VAR_AUTHORED = ("16", 23600002, "C")
_VAR_RESOLVED = ("16", 23600000, "C")

_FREQ_HEADER = [
    "variant_key",
    "rsid",
    "chrom",
    "start",
    "ref",
    "alt",
    "genome_build",
    "population",
    "allele_count",
    "allele_number",
    "dataset",
    "source",
    "status",
]


def _read(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _append(path: Path, rows: list[dict]) -> None:
    header, existing = _read(path)
    for row in rows:
        for column in row:
            if column not in header:
                header.append(column)
    _write(path, header, [*existing, *rows])


def _resolution_row(rsid: str, locus: tuple[str, int, str | None], alts: str, **over: str) -> dict:
    chrom, start, ref = locus
    return {
        "variant_key": rsid,
        "rsid": rsid,
        "chrom": chrom,
        "start": str(start),
        "ref": ref or "",
        "alts": alts,
        "genome_build": "GRCh38",
        "locus_index": "0",
        "source": "cache",
        "authority": "ensembl",
        "status": "resolved",
        **over,
    }


def _frequency_row(locus: tuple[str, int, str | None], alt: str, *, count: int = 3) -> dict:
    chrom, start, ref = locus
    return {
        "variant_key": f"{chrom}:{start}:{ref}:{alt}",
        "rsid": "",
        "chrom": chrom,
        "start": str(start),
        "ref": ref or "",
        "alt": alt,
        "genome_build": "GRCh38",
        "population": "global",
        "allele_count": str(count),
        "allele_number": "1000",
        "dataset": "gnomad_v4.1_joint",
        "source": "gnomad",
        "status": "resolved",
    }


def _nudt15_shape(tmp_path: Path, **resolution_over: str) -> Path:
    """`cpic_gene_pairs` plus one haplotype row at a right-shifted spelling, its rsID placed by
    `resolution.csv` at the left-aligned one, and a frequency row at the left-aligned one."""
    spec = tmp_path / "cpic_gene_pairs"
    shutil.copytree(_EXAMPLES / "cpic_gene_pairs", spec)
    chrom, start, _ = _AUTHORED
    _append(
        spec / "haplotypes.csv",
        [
            {
                "haplotype_name": "*1",
                "rsid": _HAP_RSID,
                "chrom": chrom,
                "start": str(start),
                "allele": "A",
                "gene": "NUDT15",
            }
        ],
    )
    _append(spec / "resolution.csv", [_resolution_row(_HAP_RSID, _RESOLVED, "A", **resolution_over)])
    _write(spec / "frequencies.csv", _FREQ_HEADER, [_frequency_row(_RESOLVED, "A")])
    return spec


def _frequency_orphans(warnings: list[str]) -> list[str]:
    return [w for w in warnings if w.startswith("frequencies.csv ") and "no variant in" in w]


def _resolved_label() -> str:
    return ":".join(str(part) for part in _RESOLVED)


def test_a_frequency_row_at_the_resolved_spelling_is_not_an_orphan(tmp_path: Path) -> None:
    spec = _nudt15_shape(tmp_path)
    result = compile_module(spec, tmp_path / "out", strict=False)
    assert result.success, result.errors
    assert not any(_resolved_label() in w for w in _frequency_orphans(result.warnings)), _frequency_orphans(
        result.warnings
    )


def test_validate_and_compile_give_the_same_frequency_orphans(tmp_path: Path) -> None:
    """Parity by check (`@parity-by-check`): the pre-flight asks with the same table under the same gate."""
    spec = _nudt15_shape(tmp_path)
    compiled = compile_module(spec, tmp_path / "out", strict=False)
    validated = validate_spec(spec, strict=False)
    assert set(_frequency_orphans(compiled.warnings)) == set(_frequency_orphans(validated.warnings))


@pytest.mark.parametrize(
    "arm",
    [
        pytest.param({"status": "not_found"}, id="not_found-is-no-placement"),
        pytest.param({"genome_build": "GRCh37"}, id="another-build-is-no-placement"),
    ],
)
def test_a_resolution_row_that_places_nothing_contributes_no_position(arm: dict, tmp_path: Path) -> None:
    """Three-valued: a row recording that the source has no placement, or a placement on another
    assembly, is not a place the module sits at. The orphan still fires."""
    spec = _nudt15_shape(tmp_path, **arm)
    result = compile_module(spec, tmp_path / "out", strict=False)
    assert result.success, result.errors
    assert any(_resolved_label() in w for w in _frequency_orphans(result.warnings))


def test_no_resolve_consults_no_table(tmp_path: Path) -> None:
    """`--no-resolve` is the master switch for every use of `resolution.csv` (`@flag-means-same`)."""
    spec = _nudt15_shape(tmp_path)
    result = compile_module(spec, tmp_path / "out", strict=False, resolve_with_ensembl=False)
    assert result.success, result.errors
    assert any(_resolved_label() in w for w in _frequency_orphans(result.warnings))


def _snp_core_shape(tmp_path: Path) -> Path:
    """`hboc_palb2` plus one pathogenic variant authored with an rsID beside a coordinate the table
    places one spelling over, a coordinate-only study at the table's spelling, and a common frequency
    there."""
    spec = tmp_path / "hboc_palb2"
    shutil.copytree(_EXAMPLES / "hboc_palb2", spec)
    chrom, start, ref = _VAR_AUTHORED
    _append(
        spec / "variants.csv",
        [
            {
                "rsid": _VAR_RSID,
                "chrom": chrom,
                "start": str(start),
                "ref": ref,
                "alts": "T",
                "genotype": "C/T",
                "state": "risk",
                "conclusion": "RM362 placement fixture",
                "gene": "PALB2",
                "clin_sig": "pathogenic",
            }
        ],
    )
    _append(spec / "resolution.csv", [_resolution_row(_VAR_RSID, _VAR_RESOLVED, "T")])
    r_chrom, r_start, r_ref = _VAR_RESOLVED
    _append(
        spec / "studies.csv",
        [
            {
                "rsid": "",
                "chrom": r_chrom,
                "start": str(r_start),
                "ref": r_ref,
                "pmid": "17200668",
                "effect_unit": "RM362 units per allele",
            }
        ],
    )
    header, rows = _read(spec / "frequencies.csv")
    rows.append({k: v for k, v in _frequency_row(_VAR_RESOLVED, "T", count=400).items() if k in header})
    _write(spec / "frequencies.csv", header, rows)
    return spec


def test_ba1_reaches_a_pathogenic_variant_through_its_resolved_spelling(tmp_path: Path) -> None:
    spec = _snp_core_shape(tmp_path)
    result = compile_module(spec, tmp_path / "out", strict=False)
    assert result.success, result.errors
    ba1 = [w for w in result.warnings if "BA1" in w and w.startswith(_VAR_RSID)]
    assert len(ba1) == 1, ba1


def test_ba1_reports_a_variant_once_when_both_spellings_carry_a_frequency(tmp_path: Path) -> None:
    """Two spellings of one place are one claim: a frequency at each gives one finding, at the
    strongest evidence."""
    spec = _snp_core_shape(tmp_path)
    header, rows = _read(spec / "frequencies.csv")
    rows.append({k: v for k, v in _frequency_row(_VAR_AUTHORED, "T", count=200).items() if k in header})
    _write(spec / "frequencies.csv", header, rows)
    result = compile_module(spec, tmp_path / "out", strict=False)
    assert result.success, result.errors
    ba1 = [w for w in result.warnings if "BA1" in w and w.startswith(_VAR_RSID)]
    assert len(ba1) == 1, ba1
    assert "is 0.4," in ba1[0], ba1


def test_no_resolve_keeps_ba1_and_the_study_join_on_the_authored_spelling(tmp_path: Path) -> None:
    spec = _snp_core_shape(tmp_path)
    result = compile_module(spec, tmp_path / "out", strict=False, resolve_with_ensembl=False)
    assert result.success, result.errors
    assert not [w for w in result.warnings if "BA1" in w and w.startswith(_VAR_RSID)]
    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet").filter(pl.col("rsid") == _VAR_RSID)
    assert weights["effect_unit"].to_list() == [None] * weights.height


def test_strict_refuses_the_contradiction_the_study_join_reaches(tmp_path: Path) -> None:
    """The one `weights.parquet` change is for a variant whose authored coordinate the table
    contradicts, and `strict` refuses that module (`rsid_coordinate_disagrees`), so no strict artifact
    moves."""
    spec = _snp_core_shape(tmp_path)
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert not result.success
    assert any(_VAR_RSID in e and "resolution table maps it to" in e for e in result.errors), result.errors


def test_a_study_at_the_resolved_spelling_supports_the_variant(tmp_path: Path) -> None:
    """`weights.parquet`'s study facts join a study to a variant by the orphan check's rule, so a
    coordinate-only study at the table's spelling feeds the variant it is about."""
    spec = _snp_core_shape(tmp_path)
    result = compile_module(spec, tmp_path / "out", strict=False)
    assert result.success, result.errors
    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet").filter(pl.col("rsid") == _VAR_RSID)
    assert weights.height >= 1
    assert set(weights["effect_unit"].to_list()) == {"RM362 units per allele"}
    # And the study-orphan check, the rule the join shares, does not name it either.
    study_key = study_coordinate_key(*_VAR_RESOLVED)
    assert not any(
        w.startswith("Studies reference variants not in") and study_key in w for w in result.warnings
    )


def test_an_unhostable_locus_of_an_expanded_rsid_is_still_one_the_module_sits_at(tmp_path: Path) -> None:
    """`@membership-union` is the union BEFORE hosting: an rsID-only variant resolving to three loci, one
    of which cannot host its genotype, expands onto the other two, each compiled row keyed by its own
    coordinate. The frequency pass still asks about every table row, so the third locus is reached
    through the rows' rsID, never their rewritten keys."""
    spec = tmp_path / "hboc_palb2"
    shutil.copytree(_EXAMPLES / "hboc_palb2", spec)
    rsid = "rs999362004"
    hostable, sibling, unhostable = ("16", 23600100, "C"), ("16", 23600150, "C"), ("16", 23600200, "G")
    _append(
        spec / "variants.csv",
        [
            {
                "rsid": rsid,
                "genotype": "C/T",
                "state": "risk",
                "conclusion": "RM362 expansion fixture",
                "gene": "PALB2",
            }
        ],
    )
    _append(
        spec / "resolution.csv",
        [
            _resolution_row(rsid, hostable, "T"),
            _resolution_row(rsid, sibling, "T", locus_index="1"),
            _resolution_row(rsid, unhostable, "A", locus_index="2"),
        ],
    )
    header, rows = _read(spec / "frequencies.csv")
    rows.append({k: v for k, v in _frequency_row(unhostable, "A").items() if k in header})
    _write(spec / "frequencies.csv", header, rows)
    result = compile_module(spec, tmp_path / "out", strict=False)
    assert result.success, result.errors
    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet").filter(pl.col("rsid") == rsid)
    assert set(weights["start"].to_list()) == {hostable[1], sibling[1]}, "the fixture must expand onto two"
    assert rsid not in set(weights["variant_key"].to_list()), "the expanded rows must be re-keyed"
    label = ":".join(str(part) for part in unhostable)
    assert not any(label in w for w in _frequency_orphans(result.warnings)), _frequency_orphans(
        result.warnings
    )


def test_a_row_placed_at_its_own_locus_sits_there_only() -> None:
    """A 1:N expansion copy sits at its own locus, not at its siblings': per-row attribution (BA1, the
    study join) must not hand one locus's evidence to the copy at another. `module_subjects` still
    takes the union."""
    loci = [
        ResolutionRow(
            variant_key="rs999362003",
            rsid="rs999362003",
            chrom="1",
            start=100,
            ref="A",
            alts="G",
            locus_index=0,
            status="resolved",
        ),
        ResolutionRow(
            variant_key="rs999362003",
            rsid="rs999362003",
            chrom="1",
            start=900,
            ref="A",
            alts="G",
            locus_index=1,
            status="resolved",
        ),
    ]
    table = {"rs999362003": loci}
    copy = VariantRow(
        rsid="rs999362003",
        chrom="1",
        start=100,
        ref="A",
        alts="G",
        genotype="A/G",
        state="risk",
        conclusion="x",
    )
    assert identity_placements(copy, table, DEFAULT_GENOME_BUILD) == {"1:100:A", "1:900:A"}
    subjects = module_subjects({"variants.csv": [copy]}, resolution=table, genome_build=DEFAULT_GENOME_BUILD)
    assert subjects.sits_at("1", 900, "A")
    assert row_positions(copy, table, DEFAULT_GENOME_BUILD) == {"1:100:A"}
    # A row with no `ref` that the table places where it stands is still placed there.
    refless = copy.model_copy(update={"ref": None})
    assert row_positions(refless, table, DEFAULT_GENOME_BUILD) == {"1:100:None"}
    # Its own spelling elsewhere and ONE other placement: the same place, so both.
    one = {"rs999362003": loci[1:]}
    moved = copy.model_copy(update={"start": 101})
    assert row_positions(moved, one, DEFAULT_GENOME_BUILD) == {"1:101:A", "1:900:A"}
    # Several other placements: which one the row means is unknown, so its own only.
    assert row_positions(moved, table, DEFAULT_GENOME_BUILD) == {"1:101:A"}
    # No table, and off GRCh38: nothing joins.
    assert row_positions(moved, None, DEFAULT_GENOME_BUILD) == {"1:101:A"}
    assert row_positions(moved, one, "GRCh37") == {"1:101:A"}


def _carried_resolution_loci(spec: Path, identities: frozenset[str]) -> set[str]:
    """Computed off the raw table, independently of the mechanism: every placement row on GRCh38 whose
    key is a carried identity."""
    path = spec / "resolution.csv"
    if not path.exists():
        return set()
    rows, errors, _ = load_csv_rows(path, ResolutionRow, "resolution.csv")
    assert not errors
    return {
        study_coordinate_key(r.chrom, r.start, r.ref) or ""
        for r in rows
        if r.variant_key in identities
        and r.genome_build == "GRCh38"
        and r.status != "not_found"
        and r.chrom is not None
        and r.start is not None
    }


def _subjects_as_compiled(spec: Path) -> tuple:
    """`module_subjects` asked the way the compile asks it: over `variants.csv` and the positional
    kinds after the fill, with the module's own table."""
    build = (
        yaml.safe_load((spec / "module_spec.yaml").read_text()).get("genome_build") or DEFAULT_GENOME_BUILD
    )
    table: dict[str, list[ResolutionRow]] = {}
    path = spec / "resolution.csv"
    if path.exists():
        rows, _errors, _ = load_csv_rows(path, ResolutionRow, "resolution.csv")
        for r in rows:
            table.setdefault(r.variant_key, []).append(r)
    by_table: dict[str, list] = {}
    variants_path = spec / "variants.csv"
    if variants_path.exists():
        by_table["variants.csv"], _, _ = load_spec_variants(spec)
    for name, _parquet, model in _TABLE_KINDS:
        if name in MODULE_LOCUS_TABLES and (spec / name).exists():
            by_table[name], _, _ = load_csv_rows(spec / name, model, name, genome_build=build)
    _apply_positional_resolution(by_table, table, build)
    return module_subjects(by_table, resolution=table, genome_build=build), build


@pytest.mark.parametrize("example", _ALL)
def test_the_resolved_positions_are_the_carried_identities_resolution_loci(
    example: str, tmp_path: Path
) -> None:
    """The guard, as an equality over every shipped module: the GRCh38 placements `resolution.csv`
    files under an identity a module row carries are exactly the positions `module_subjects` took from
    resolution. A narrowed lookup (the rsID only, the key only) or a widened one (every row of the
    table, proxies included) turns a module red here."""
    spec = tmp_path / example
    shutil.copytree(_EXAMPLES / example, spec)
    subjects, build = _subjects_as_compiled(spec)
    expected = _carried_resolution_loci(spec, subjects.identities) if build == "GRCh38" else set()
    assert subjects.resolved_positions == expected
    assert subjects.resolved_positions <= subjects.positions


def test_the_guard_sees_the_nudt15_shape(tmp_path: Path) -> None:
    """The red case for the guard: the fixture's left-aligned spelling is one of the resolved positions,
    and not one of the authored ones."""
    spec = _nudt15_shape(tmp_path)
    subjects, _build = _subjects_as_compiled(spec)
    label = study_coordinate_key(*_RESOLVED)
    assert label in subjects.resolved_positions
    assert label in _carried_resolution_loci(spec, subjects.identities)
    authored_only = module_subjects(
        {
            "haplotypes.csv": [
                r for r in load_csv_rows(spec / "haplotypes.csv", HaplotypeRow, "haplotypes.csv")[0]
            ]
        }
    )
    assert label not in authored_only.positions
