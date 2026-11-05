"""RM362: "which genes and loci is this module about" has one answer, and every orphan check asks it.

Before, the question had three answerers. `manifest.stats.genes` read `variants.csv` and every
gene-bearing table kind; the enricher's `module_genes` read the same roster; the study-orphan check read
`variants.csv`, `haplotypes.csv`, `pharm_variants.csv` and the rows a meta member reached; and the five
derived-row orphan checks read `variants.csv` alone, returning `[]` when it was absent. So
`apoe_klvs_meta`, whose APOE lives in its diplotype tables, was told its own `gene_metrics.csv` row for
APOE named "a gene this module never mentions" while its manifest listed APOE in `stats.genes`, and a
PGx-only module got no orphan check at all.

Reproduced on the shipped corpus rather than on a fixture written to the new roster, since only the
corpus can show the old roster was narrow. Compile and validate run for real; every expected set is
read off the module at runtime.
"""

import csv
import json
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_compiler.compiler.positional import _GENE_BEARING_TABLE_KINDS, _POSITIONAL_TABLE_KINDS
from just_dna_compiler.compiler.subjects import (
    MODULE_GENE_TABLES,
    MODULE_LOCUS_TABLES,
    module_subjects,
)
from just_dna_compiler.compiler.tables import _TABLE_KINDS
from just_dna_format.meta import LOCUS_TABLES
from just_dna_format.model_organisms import ModelOrganismRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

_DECOY_GENE = "RM362DECOY"
_DECOY_RSID = "rs999999362"
#: A coordinate no reference example sits at: chr22's last megabase holds no module row here.
_DECOY_LOCUS = ("22", 50000362, "A")


def _copy(name: str, tmp_path: Path) -> Path:
    spec = tmp_path / name
    shutil.copytree(_EXAMPLES / name, spec)
    return spec


def _write(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _gene_metrics(spec: Path, genes: list[str]) -> None:
    _write(
        spec / "gene_metrics.csv",
        ["gene", "pli", "dataset", "source", "status"],
        [
            {"gene": g, "pli": "0.1", "dataset": "gnomad_v4.1", "source": "gnomad", "status": "resolved"}
            for g in genes
        ],
    )


def _gene_validity(spec: Path, genes: list[str]) -> None:
    _write(
        spec / "gene_validity.csv",
        ["gene", "disease_id", "classification", "assertion_id", "dataset", "source", "status"],
        [
            {
                "gene": g,
                "disease_id": "MONDO:0000001",
                "classification": "definitive",
                "assertion_id": f"CGGV:rm362-{g}",
                "dataset": "clingen_gene_validity_2026-08-13",
                "source": "clingen",
                "status": "resolved",
            }
            for g in genes
        ],
    )


def _frequencies(spec: Path, loci: list[tuple[str, int, str]]) -> None:
    _write(
        spec / "frequencies.csv",
        [
            "variant_key",
            "chrom",
            "start",
            "ref",
            "alt",
            "genome_build",
            "population",
            "dataset",
            "source",
            "status",
        ],
        [
            {
                "variant_key": f"{c}:{s}:{r}",
                "chrom": c,
                "start": s,
                "ref": r,
                "alt": "N" if r != "N" else "A",
                "genome_build": "GRCh38",
                "population": "global",
                "dataset": "gnomad_v4",
                "source": "gnomad",
                "status": "not_found",
            }
            for c, s, r in loci
        ],
    )


def _clinical_assertions(spec: Path, loci: list[tuple[str, int, str]]) -> None:
    _write(
        spec / "clinical_assertions.csv",
        ["variant_key", "chrom", "start", "ref", "alt", "genome_build", "dataset", "source", "status"],
        [
            {
                "variant_key": f"{c}:{s}:{r}",
                "chrom": c,
                "start": s,
                "ref": r,
                "alt": "N" if r != "N" else "A",
                "genome_build": "GRCh38",
                "dataset": "clinvar_2026-06-27",
                "source": "clinvar",
                "status": "not_found",
            }
            for c, s, r in loci
        ],
    )


def _gwas_effects(spec: Path, rsids: list[str]) -> None:
    _write(
        spec / "gwas_effects.csv",
        ["association_id", "variant_key", "rsid", "dataset", "source", "status"],
        [
            {
                "association_id": f"{r}:not_found",
                "variant_key": r,
                "rsid": r,
                "dataset": "gwas_catalog_2026-08-17",
                "source": "gwas_catalog",
                "status": "not_found",
            }
            for r in rsids
        ],
    )


def _orphans(warnings: list[str], table: str) -> list[str]:
    return [
        w for w in warnings if w.startswith(f"{table} ") and ("never mentions" in w or "no variant in" in w)
    ]


# ── the reported instance, both directions ───────────────────────────────────────────────────────────


def test_a_diplotype_scored_module_owns_the_genes_and_loci_its_manifest_publishes(tmp_path: Path) -> None:
    """The audit probe: `apoe_klvs_meta` plus a fact row for APOE at its ε-defining locus in all five
    sidecars. Not one is an orphan: APOE is in `stats.genes`, and rs429358 is a `haplotypes.csv` row."""
    spec = _copy("apoe_klvs_meta", tmp_path)
    resolution = {
        row["rsid"]: row for row in csv.DictReader((spec / "resolution.csv").open(encoding="utf-8"))
    }
    eps = resolution["rs429358"]
    locus = (eps["chrom"], int(eps["start"]), eps["ref"])
    _gene_metrics(spec, ["APOE"])
    _gene_validity(spec, ["APOE"])
    _frequencies(spec, [locus])
    _clinical_assertions(spec, [locus])
    _gwas_effects(spec, ["rs429358"])
    result = compile_module(spec, tmp_path / "out", strict=False)
    assert result.success, result.errors
    genes = json.loads((tmp_path / "out" / "manifest.json").read_text())["stats"]["genes"]
    assert "APOE" in genes
    found = [w for w in result.warnings if "never mentions" in w or "no variant in this module" in w]
    assert found == []
    # The pre-flight runs the two gene-keyed checks too (RM211), over the same roster.
    assert [w for w in validate_spec(spec).warnings if "never mentions" in w] == []


def test_a_module_with_no_variants_csv_is_still_checked(tmp_path: Path) -> None:
    """The gained direction. `pgx_slco1b1_simvastatin` has no `variants.csv`, so every orphan check
    returned `[]` before anything was compared. A decoy row in each sidecar is now named, and only the
    decoy: the module's own SLCO1B1 / rs4149056 rows are not orphans."""
    spec = _copy("pgx_slco1b1_simvastatin", tmp_path)
    assert not (spec / "variants.csv").exists()
    pharm = list(csv.DictReader((spec / "pharm_variants.csv").open(encoding="utf-8")))
    gene, rsid = pharm[0]["gene"], pharm[0]["rsid"]
    resolution = {
        row["rsid"]: row for row in csv.DictReader((spec / "resolution.csv").open(encoding="utf-8"))
    }
    locus = (resolution[rsid]["chrom"], int(resolution[rsid]["start"]), resolution[rsid]["ref"])
    _gene_metrics(spec, [gene, _DECOY_GENE])
    _gene_validity(spec, [gene, _DECOY_GENE])
    _frequencies(spec, [locus, _DECOY_LOCUS])
    _clinical_assertions(spec, [locus, _DECOY_LOCUS])
    _gwas_effects(spec, [rsid, _DECOY_RSID])
    result = compile_module(spec, tmp_path / "out", strict=False)
    assert result.success, result.errors
    decoy_locus = ":".join(str(part) for part in _DECOY_LOCUS)
    for table, decoy in (
        ("gene_metrics.csv", _DECOY_GENE),
        ("gene_validity.csv", _DECOY_GENE),
        ("frequencies.csv", decoy_locus),
        ("clinical_assertions.csv", decoy_locus),
        ("gwas_effects.csv", _DECOY_RSID),
    ):
        found = _orphans(result.warnings, table)
        assert len(found) == 1, (table, found)
        assert f"['{decoy}']" in found[0], (table, found)
    preflight = validate_spec(spec).warnings
    assert len(_orphans(preflight, "gene_metrics.csv")) == 1
    assert len(_orphans(preflight, "gene_validity.csv")) == 1


def test_a_study_on_a_heteroplasmy_locus_is_not_an_orphan(tmp_path: Path) -> None:
    """The study-orphan check reads the same roster: a `heteroplasmy.csv` row carries a locus as much as
    a `haplotypes.csv` one does. With `variants.csv` gone from `mt_heteroplasmy`, its studies on
    m.3243A>G are carried by the heteroplasmy rows alone."""
    spec = _copy("mt_heteroplasmy", tmp_path)
    (spec / "variants.csv").unlink()
    het = {
        (r["chrom"], r["start"], r["ref"])
        for r in csv.DictReader((spec / "heteroplasmy.csv").open(encoding="utf-8"))
    }
    studies = list(csv.DictReader((spec / "studies.csv").open(encoding="utf-8")))
    assert {(r["chrom"], r["start"], r["ref"]) for r in studies} <= het
    warnings = validate_spec(spec).warnings
    assert [w for w in warnings if w.startswith("Studies reference variants not in variants.csv")] == []


# ── the guard: one roster, and the rosters that must equal it ────────────────────────────────────────


def test_the_rosters_are_derived_from_the_table_registry() -> None:
    """Equalities over the walked registry, never a list: a table kind gaining `gene` or `chrom`+`start`
    joins the module's subjects by existing."""
    gene_kinds = {name for name, _parquet, model in _TABLE_KINDS if "gene" in model.model_fields}
    locus_kinds = {
        name for name, _parquet, model in _TABLE_KINDS if {"chrom", "start"} <= set(model.model_fields)
    }
    assert set(MODULE_GENE_TABLES) == {"variants.csv", *gene_kinds}
    assert set(MODULE_LOCUS_TABLES) == {"variants.csv", *locus_kinds}
    # The positional module's two rosters are these, read off them rather than re-derived.
    assert {name for name, _ in _GENE_BEARING_TABLE_KINDS} == gene_kinds
    assert {name for name, _ in _POSITIONAL_TABLE_KINDS} == locus_kinds
    # `model_organisms.csv` carries `gene`, and its gene is the one a mouse experiment altered.
    assert "model_organisms.csv" not in MODULE_GENE_TABLES


def test_every_row_a_meta_member_can_reach_is_already_a_module_subject() -> None:
    """Why the study check no longer carries a meta arm: a member reaches rows of `LOCUS_TABLES` only,
    and each is on the locus roster, so the rows it reaches are subjects already. A locus table added to
    the meta-table without joining the roster turns this red rather than silently narrowing the check."""
    assert {f"{table}.csv" for table in LOCUS_TABLES} <= set(MODULE_LOCUS_TABLES)


def test_the_module_subjects_ignore_a_table_off_the_roster() -> None:
    """A `model_organisms.csv` row handed in is not a gene the module is about (R-ANIMAL-1)."""
    fields = ModelOrganismRow.model_fields
    assert "gene" in fields
    subjects = module_subjects({"model_organisms.csv": [type("R", (), {"gene": "Apoe"})()]})
    assert subjects.genes == ()
    assert not subjects.names_gene("Apoe")


def test_a_row_with_no_start_sits_nowhere() -> None:
    """An unplaced locus row is not a position: `19:None:None` would match every unplaced row on 19."""
    row = type(
        "R", (), {"chrom": "19", "start": None, "ref": None, "variant_key": "rs429358", "rsid": "rs429358"}
    )()
    subjects = module_subjects({"haplotypes.csv": [row]})
    assert subjects.positions == frozenset()
    assert subjects.placed == frozenset()
    assert not subjects.sits_at("19", None, None)
    assert subjects.carries("rs429358")


@pytest.mark.parametrize("example", sorted(p.parent.name for p in _EXAMPLES.glob("*/module_spec.yaml")))
def test_stats_genes_is_the_module_subjects_gene_set(example: str, tmp_path: Path) -> None:
    """`manifest.stats.genes` and the gene orphan checks are one answer on every shipped module: a
    `gene_metrics.csv` row for each published gene plus one decoy reports exactly the decoy."""
    spec = _copy(example, tmp_path)
    out = tmp_path / "out"
    first = compile_module(spec, out, strict=False)
    assert first.success, first.errors
    genes = json.loads((out / "manifest.json").read_text())["stats"]["genes"]
    _gene_metrics(spec, [*genes, _DECOY_GENE])
    result = compile_module(spec, tmp_path / "out2", strict=False)
    assert result.success, result.errors
    found = _orphans(result.warnings, "gene_metrics.csv")
    if not genes:
        # A module that names no gene withholds: nothing to call a row an orphan against.
        assert found == []
        return
    assert len(found) == 1, found
    assert f"['{_DECOY_GENE}']" in found[0]


def test_a_positioned_heteroplasmy_row_is_a_resolution_row_the_artifact_can_carry(tmp_path: Path) -> None:
    """The overlay's reachability reads the same placed loci. `reverse_module` writes a `resolution.csv`
    row for every placed row of a positional table (RM43), so a correction aimed at a heteroplasmy row's
    locus is reachable: before, lap 1 called it "no artifact of this module can carry" and lap 2, holding
    the reversed row, matched it."""
    spec = _copy("mt_heteroplasmy", tmp_path)
    (spec / "verification.json").unlink(missing_ok=True)
    het = list(csv.DictReader((spec / "heteroplasmy.csv").open(encoding="utf-8")))
    variants = list(csv.DictReader((spec / "variants.csv").open(encoding="utf-8")))
    # Keep one variant so the module carries a resolution.csv, and none at the heteroplasmy locus.
    kept = next(v for v in variants if (v["chrom"], v["start"]) != (het[0]["chrom"], het[0]["start"]))
    _write(spec / "variants.csv", list(kept), [kept])
    _write(
        spec / "resolution.csv",
        ["variant_key", "rsid", "chrom", "start", "ref", "alts", "genome_build", "source", "status"],
        [
            {
                "variant_key": kept["rsid"],
                "rsid": kept["rsid"],
                "chrom": kept["chrom"],
                "start": kept["start"],
                "ref": kept["ref"],
                "alts": kept["alts"],
                "genome_build": "GRCh38",
                "source": "cache",
                "status": "resolved",
            }
        ],
    )
    first = compile_module(spec, tmp_path / "probe", strict=False)
    assert first.success, first.errors
    key = pl.read_parquet(tmp_path / "probe" / "heteroplasmy.parquet")["variant_key"][0]
    (spec / "overrides.csv").write_text(
        "table,subject,member,field,operation,value,reason,decided_by,decided_at\n"
        f"resolution.csv,{key},0,source,update,manual,re-checked by hand,curator,2026-11-04\n",
        encoding="utf-8",
    )
    lap1 = compile_module(spec, tmp_path / "o1", strict=False)
    assert lap1.success, lap1.errors
    assert [w for w in lap1.warnings if "no artifact of this module can carry" in w] == []
    reverse_module(tmp_path / "o1", tmp_path / "spec2")
    lap2 = compile_module(tmp_path / "spec2", tmp_path / "o2", strict=False)
    assert lap2.success, lap2.errors
    assert [w for w in lap2.warnings if "no artifact of this module can carry" in w] == []
