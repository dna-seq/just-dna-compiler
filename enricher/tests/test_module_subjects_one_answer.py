"""RM362: the enricher's scopes and the compiler's orphan checks ask one question, and get one answer.

A pass writes a fact row for a gene or a locus it took to be the module's; the compile then checks the
row against what it takes the module to carry. When the two read different tables, a row the pass wrote
on purpose comes back as "a gene this module never mentions" (`apoe_klvs_meta`, APOE), or a row the
pass could never have written is not checked at all (a module without `variants.csv`).

Both sides now read `just_dna_compiler.compiler.subjects`. The guard is behavioural and walks every
shipped module: the fact rows each pass would ask about (its own scope function, run for real) plus one
decoy go into the sidecars, the module is compiled, and the orphan findings must name the decoy and
nothing else. A roster narrowed on either side turns a module red here. Offline throughout.
"""

import csv
import json
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    MODULE_GENE_TABLES,
    MODULE_LOCUS_TABLES,
    ModuleSubjects,
    compile_module,
    load_csv_rows,
)
from just_dna_enricher.enrich.subjects import SUBJECT_TABLES, study_proxy_rsids
from just_dna_enricher.gene_metrics import _NOT_THE_MODULES_GENES, module_genes
from just_dna_enricher.gwas import _module_subjects as gwas_subjects
from just_dna_enricher.identifiers import _id_bearing_tables
from just_dna_format.resolution import ResolutionRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_ALL = sorted(p.parent.name for p in _EXAMPLES.glob("*/module_spec.yaml"))

_DECOY_GENE = "RM362DECOY"
_DECOY_RSID = "rs999999362"
_DECOY_LOCUS = ("22", 50000362, "A")


def _write(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _orphans(warnings: list[str], table: str) -> list[str]:
    return [
        w for w in warnings if w.startswith(f"{table} ") and ("never mentions" in w or "no variant in" in w)
    ]


def test_the_gene_scope_reads_the_compilers_gene_roster() -> None:
    """The tables `module_genes` reads are `MODULE_GENE_TABLES`, as an equality: the exclusion is the
    difference between every gene-bearing authored table and that roster, never a list of its own."""
    assert set(_id_bearing_tables("gene")) - _NOT_THE_MODULES_GENES == set(MODULE_GENE_TABLES)


def test_each_gene_table_has_its_own_model() -> None:
    """`module_genes` files a row under its table by the row's model, so two tables sharing a model would
    file one table's genes under the other's name."""
    models = list(_id_bearing_tables("gene").values())
    assert len(set(models)) == len(models)


def test_the_resolution_subjects_are_the_compilers_locus_roster() -> None:
    """`collect_subjects` asks about the module's loci plus a study's LD proxy, and nothing else: its
    tables less `studies.csv` are `MODULE_LOCUS_TABLES`. A positional kind added to the compiler without
    a subject block here (or the reverse) turns this red."""
    assert set(SUBJECT_TABLES) - {"studies.csv"} == set(MODULE_LOCUS_TABLES)


@pytest.mark.parametrize("example", _ALL)
def test_every_scope_and_every_orphan_check_give_one_answer(example: str, tmp_path: Path) -> None:
    spec = tmp_path / example
    shutil.copytree(_EXAMPLES / example, spec)
    first = compile_module(spec, tmp_path / "out", strict=False)
    assert first.success, first.errors
    published = json.loads((tmp_path / "out" / "manifest.json").read_text())["stats"]["genes"]

    # Genes: the enricher's scope is the published set, split as a registry is asked (S72 keeps a
    # composite cell whole in `stats.genes`; the pass asks about its parts).
    genes = module_genes(spec)
    assert set(genes) == set(ModuleSubjects(genes=tuple(published)).gene_symbols)

    # Loci: the rows the frequency pass asks gnomAD about are the resolution rows on its build, less a
    # study's LD proxy (RM331). Identities: the rsIDs the GWAS pass asks the Catalog about.
    loci: list[tuple[str, int, str]] = []
    resolution = spec / "resolution.csv"
    if resolution.exists():
        rows, errors, _ = load_csv_rows(resolution, ResolutionRow, "resolution.csv")
        assert not errors
        proxies = study_proxy_rsids(spec)
        loci = sorted(
            {
                (r.chrom, r.start, r.ref)
                for r in rows
                if r.variant_key not in proxies
                and r.chrom
                and r.start is not None
                and r.genome_build == "GRCh38"
            }
        )
    rsids = gwas_subjects(spec)

    _write(
        spec / "gene_metrics.csv",
        ["gene", "pli", "dataset", "source", "status"],
        [
            {"gene": g, "pli": "0.1", "dataset": "gnomad_v4.1", "source": "gnomad", "status": "resolved"}
            for g in [*genes, _DECOY_GENE]
        ],
    )
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
                "alt": "N",
                "genome_build": "GRCh38",
                "population": "global",
                "dataset": "gnomad_v4",
                "source": "gnomad",
                "status": "not_found",
            }
            for c, s, r in [*loci, _DECOY_LOCUS]
        ],
    )
    _write(
        spec / "gwas_effects.csv",
        ["association_id", "variant_key", "rsid", "dataset", "source", "status"],
        [
            {
                "association_id": f"{rsid}:not_found",
                "variant_key": key,
                "rsid": rsid,
                "dataset": "gwas_catalog_2026-08-17",
                "source": "gwas_catalog",
                "status": "not_found",
            }
            for rsid, key in [*rsids, (_DECOY_RSID, _DECOY_RSID)]
        ],
    )
    result = compile_module(spec, tmp_path / "out2", strict=False)
    assert result.success, result.errors

    decoy_locus = ":".join(str(part) for part in _DECOY_LOCUS)
    expected = {
        # A module naming no gene / placing no locus / carrying no identity withholds the check.
        "gene_metrics.csv": [_DECOY_GENE] if genes else None,
        "frequencies.csv": [decoy_locus] if loci else None,
        "gwas_effects.csv": [_DECOY_RSID] if rsids else None,
    }
    for table, decoys in expected.items():
        found = _orphans(result.warnings, table)
        if decoys is None:
            continue
        assert len(found) == 1, (table, found)
        assert f": {decoys}" in found[0], (table, found)
