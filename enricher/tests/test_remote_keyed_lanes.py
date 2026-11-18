"""The lanes RM431 makes remote-eligible, each by its keyed function's keys (0.9, RM431, on RM430's seam).

Each lane's published repo is a `LoopbackHub` serving a real snapshot's bytes; the holder is asked with
the keys the keyed function derives, and its rows go through the keyed function's own SQL. The answer
must equal the local reader's over the same snapshot: same keys, same rows, one SQL body.
"""

import hashlib
import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb
import httpx
import polars as pl
import pytest
from just_dna_enricher import (
    civic_draft,
    clinpgx,
    clinpgx_build,
    clinvar,
    clinvar_build,
    clinvar_gkm,
    constraint_build,
    cpic,
    drug_labels,
    drug_labels_build,
    gene_metrics,
    opentargets,
    remote,
    resolver,
)
from just_dna_enricher import lookup as lookup_module
from just_dna_enricher.civic_build import CIVIC_PARQUET, build_snapshot
from just_dna_enricher.clinvar_gkm import ALLELE_FILE, VARIATION_FILE, WITNESS_PARQUET, parse_manifest
from just_dna_enricher.clinvar_gkm_build import build_snapshot as build_witness
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS
from just_dna_enricher.remote import REMOTE_LANES, RemoteAnswer, RemoteSnapshots

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
OPENTARGETS_SLICE = _ASSETS / "opentargets_slice"
CIVIC_SLICE = _ASSETS / "civic_slice"
GKM_SLICE = _ASSETS / "clinvar_gkm_slice"
CLINPGX_SLICE = _ASSETS / "clinpgx_annotations_slice"
LABELS_SLICE = _ASSETS / "clinpgx_drug_labels_slice"
COMMIT = "c" * 40


@pytest.fixture(autouse=True)
def _no_ambient_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's `.env` may name a proxy; set empty rather than deleted, so it cannot refill it."""
    monkeypatch.setenv(remote.PROXY_URL_VAR, "")
    monkeypatch.setenv(remote.PROXY_TOKEN_VAR, "")


@pytest.fixture(scope="module")
def civic_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_snapshot(
        CIVIC_SLICE / "ClinicalEvidenceSummaries.tsv",
        CIVIC_SLICE / "VariantSummaries.tsv",
        CIVIC_SLICE / "MolecularProfileSummaries.tsv",
        tmp_path_factory.mktemp("civic") / "snap",
        release="01-Aug-2026",
    ).out_dir


def test_open_targets_is_remote_eligible_and_answers_by_position_not_by_rsid_alone() -> None:
    assert "opentargets" in REMOTE_LANES
    assert not REMOTE_LANES["opentargets"].needs_position


def test_open_targets_answers_remotely_as_the_local_reader_does(httpfs, loopback_hub) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["opentargets"], OPENTARGETS_SLICE, COMMIT)
    # C282Y (rs_ids a one-element list), a position with an allele whose rs_ids is empty, rs35589214's
    # two alleles, and a position the release holds nothing at.
    positions = [("chr6", 26092913), ("6", 26092960), ("8", 78193100), ("6", 1)]
    local = opentargets.lookup_variants(OPENTARGETS_SLICE, positions)
    assert any(row["rs_ids"] == [] for rows in local.values() for row in rows), "an empty list is covered"
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        answer = holder.lookup(
            "opentargets", opentargets.REMOTE_VARIANTS_TABLE, opentargets._variant_keys(positions)
        )
        assert opentargets._variants_from_rows(answer.rows, positions) == local
        ids = sorted({row["variant_id"] for rows in local.values() for row in rows})
        keys = {"variant_id": ids}
        consequences = holder.lookup("opentargets", opentargets.REMOTE_CONSEQUENCES_TABLE, keys)
        members = holder.lookup("opentargets", opentargets.REMOTE_MEMBERS_TABLE, keys)
    remote_answer = opentargets._consequences_from_rows(consequences.rows, members.rows, ids)
    local_answer = opentargets.lookup_consequences(OPENTARGETS_SLICE, ids)
    assert remote_answer == local_answer
    rows = [row for found in local_answer.values() for row in found]
    assert {type(row["canonical"]) for row in rows if row["table"] == "consequences"} == {bool}
    assert {type(row["posterior_probability"]) for row in rows if row["table"] == "credible_set_members"} == {
        float
    }


# ── CIViC ───────────────────────────────────────────────────────────────────────────────────────


def _civic_values(root: Path, column: str) -> list[str]:
    path = str(root / "data" / CIVIC_PARQUET).replace("'", "''")
    return [
        str(value)
        for (value,) in duckdb.sql(
            f"SELECT DISTINCT {column} FROM read_parquet('{path}') WHERE {column} IS NOT NULL ORDER BY 1"
        ).fetchall()
    ]


def test_civic_answers_remotely_by_gene_and_by_rsid_as_the_local_reader_does(
    httpfs, loopback_hub, civic_root: Path
) -> None:
    assert "civic" in REMOTE_LANES
    loopback_hub.publish(SNAPSHOT_REPO_IDS["civic"], civic_root, COMMIT)
    genes = [*_civic_values(civic_root, "gene")[:2], "NOT_A_GENE"]
    rsids = [*_civic_values(civic_root, "rsid")[:2], "334"]
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        by_gene = holder.lookup("civic", civic_draft.REMOTE_CIVIC_TABLE, civic_draft._civic_gene_keys(genes))
        by_rsid = holder.lookup("civic", civic_draft.REMOTE_CIVIC_TABLE, civic_draft._civic_rsid_keys(rsids))
    local_genes = civic_draft.lookup_genes(civic_root, genes)
    assert len(local_genes) == 2, "both genes are in the slice, so an empty answer cannot pass"
    assert civic_draft._genes_from_rows(by_gene.rows, genes) == local_genes
    local_rsids = civic_draft.lookup_rsids(civic_root, rsids)
    assert len(local_rsids) == 2
    assert civic_draft._rsids_from_rows(by_rsid.rows, rsids) == local_rsids


def test_a_gene_asked_in_another_case_answers_alike_on_both_routes(
    httpfs, loopback_hub, civic_root: Path
) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["civic"], civic_root, COMMIT)
    genes = [_civic_values(civic_root, "gene")[0].lower()]
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        answer = holder.lookup("civic", civic_draft.REMOTE_CIVIC_TABLE, civic_draft._civic_gene_keys(genes))
    assert civic_draft._genes_from_rows(answer.rows, genes) == civic_draft.lookup_genes(civic_root, genes)


# ── ClinVar-GKM ─────────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def gkm_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    raw = json.loads((GKM_SLICE / "manifest.json").read_text(encoding="utf-8"))
    for entry in raw["files"]:
        path = {ALLELE_FILE: GKM_SLICE / ALLELE_FILE, VARIATION_FILE: GKM_SLICE / VARIATION_FILE}.get(
            entry["name"]
        )
        if path is not None:
            entry["size"] = path.stat().st_size
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    out = tmp_path_factory.mktemp("clinvar_gkm")
    build_witness(
        GKM_SLICE / ALLELE_FILE, GKM_SLICE / VARIATION_FILE, out, manifest=parse_manifest(json.dumps(raw))
    )
    return out


def test_the_witness_table_is_named_as_a_remote_route_names_it() -> None:
    assert remote.table_name(f"data/{WITNESS_PARQUET}") == clinvar_gkm.REMOTE_WITNESS_TABLE


def test_clinvar_gkm_answers_remotely_by_position_and_by_rsid_as_the_local_reader_does(
    httpfs, loopback_hub, gkm_root: Path
) -> None:
    assert "clinvar_gkm" in REMOTE_LANES
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinvar_gkm"], gkm_root, COMMIT)
    # rs72613567's insertion (a `chr` spelling), rs77944059's deletion, and a position holding nothing.
    positions = [("chr4", 87310240), ("2", 166204470), ("4", 1)]
    rsids = ["rs1003713657", "77944059", "rs8176719"]
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        by_position = holder.lookup(
            "clinvar_gkm", clinvar_gkm.REMOTE_WITNESS_TABLE, clinvar_gkm._variant_keys(positions)
        )
        by_rsid = holder.lookup(
            "clinvar_gkm", clinvar_gkm.REMOTE_WITNESS_TABLE, clinvar_gkm._rsid_keys(rsids)
        )
    local_positions = clinvar_gkm.lookup_variants(gkm_root, positions)
    assert len(local_positions) == 2, "both indels are in the slice, so an empty answer cannot pass"
    assert clinvar_gkm._variants_from_rows(by_position.rows, positions) == local_positions
    local_rsids = clinvar_gkm.lookup_rsids(gkm_root, rsids)
    assert len(local_rsids) == 2
    assert clinvar_gkm._rsids_from_rows(by_rsid.rows, rsids) == local_rsids


# ── ClinPGx (the pm's reading 4) ────────────────────────────────────────────────────────────────


def _zipped(directory: Path, archive: Path) -> Path:
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(directory.iterdir()):
            handle.write(path, path.name)
    return archive


@pytest.fixture(scope="module")
def clinpgx_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("clinpgx")
    archive = _zipped(CLINPGX_SLICE, tmp / "summaryAnnotations.zip")
    return clinpgx_build.build_snapshot(
        archive, tmp / "snap", source_url="file://clinpgx_annotations_slice"
    ).out_dir


def _parquet_values(path: Path, column: str) -> list[str]:
    quoted = str(path).replace("'", "''")
    return [
        str(value)
        for (value,) in duckdb.sql(
            f"SELECT DISTINCT {column} FROM read_parquet('{quoted}') WHERE {column} IS NOT NULL ORDER BY 1"
        ).fetchall()
    ]


def test_the_annotations_table_is_named_as_a_remote_route_names_it() -> None:
    assert remote.table_name("data/annotations.parquet") == clinpgx.REMOTE_ANNOTATIONS_TABLE


def test_clinpgx_answers_remotely_by_rsid_and_by_gene_as_the_local_reader_does(
    httpfs, loopback_hub, clinpgx_root: Path
) -> None:
    """ClinPGx's terms forbid sale, so the holder states a use they admit, or nothing is asked."""
    assert "clinpgx" in REMOTE_LANES
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinpgx"], clinpgx_root, COMMIT)
    parquet = clinpgx_root / "data" / "annotations.parquet"
    held = _parquet_values(parquet, "rsid")
    rsids = [*held, held[0].removeprefix("rs"), "1"]
    genes = [*_parquet_values(parquet, "gene"), "NOT_A_GENE"]
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url, declared_use="non_commercial") as holder:
        by_rsid = holder.lookup("clinpgx", clinpgx.REMOTE_ANNOTATIONS_TABLE, clinpgx._rsid_keys(rsids))
        by_gene = holder.lookup("clinpgx", clinpgx.REMOTE_ANNOTATIONS_TABLE, clinpgx._gene_keys(genes))
    local_rsids = clinpgx.lookup_rsids(clinpgx_root, rsids)
    assert len(local_rsids) == len(held) + 1, (
        "every rsID held, and one asked bare, so an empty answer cannot pass"
    )
    assert clinpgx._rsids_from_rows(by_rsid.rows, rsids) == local_rsids
    local_genes = clinpgx.lookup_genes(clinpgx_root, genes)
    assert len(local_genes) == len(genes) - 1
    assert clinpgx._genes_from_rows(by_gene.rows, genes) == local_genes


def test_a_clinpgx_gene_asked_in_another_case_answers_alike_on_both_routes(
    httpfs, loopback_hub, clinpgx_root: Path
) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinpgx"], clinpgx_root, COMMIT)
    genes = [_parquet_values(clinpgx_root / "data" / "annotations.parquet", "gene")[0].lower()]
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url, declared_use="non_commercial") as holder:
        answer = holder.lookup("clinpgx", clinpgx.REMOTE_ANNOTATIONS_TABLE, clinpgx._gene_keys(genes))
    assert clinpgx._genes_from_rows(answer.rows, genes) == clinpgx.lookup_genes(clinpgx_root, genes)


# ── the drug labels (the pm's reading 4) ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def labels_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("drug-labels")
    archive = _zipped(LABELS_SLICE, tmp / "drugLabels.zip")
    return drug_labels_build.build_drug_label_snapshot(
        archive, tmp / "snap", source_url="file://clinpgx_drug_labels_slice"
    ).out_dir


def _label_genes(root: Path) -> tuple[list[str], list[str]]:
    """The genes of the slice's labels: those that are a whole cell, and those only inside a multi-gene one."""
    cells = _parquet_values(root / "data" / drug_labels.LABELS_PARQUET, "genes")
    whole = [cell for cell in cells if drug_labels.CELL_SEPARATOR not in cell]
    inside = sorted(
        {member for cell in cells for member in drug_labels._split(cell) if len(drug_labels._split(cell)) > 1}
        - set(whole)
    )
    return whole, inside


def test_the_labels_table_is_named_as_a_remote_route_names_it() -> None:
    assert remote.table_name(f"data/{drug_labels.LABELS_PARQUET}") == drug_labels.REMOTE_LABELS_TABLE


def test_drug_labels_answer_remotely_by_a_gene_named_alone_as_the_local_reader_does(
    httpfs, loopback_hub, labels_root: Path
) -> None:
    assert "drug_labels" in REMOTE_LANES
    loopback_hub.publish(SNAPSHOT_REPO_IDS["drug_labels"], labels_root, COMMIT)
    whole, _ = _label_genes(labels_root)
    cells = _parquet_values(labels_root / "data" / drug_labels.LABELS_PARQUET, "genes")
    beside = {
        member for cell in cells if len(drug_labels._split(cell)) > 1 for member in drug_labels._split(cell)
    }
    # Genes no label names beside another; a gene on a multi-gene label is the next test's.
    alone = [gene for gene in whole if gene not in beside]
    assert alone, "the slice names DPYD and SLCO1B1 only on their own"
    genes = [*alone, "NOT_A_GENE"]
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url, declared_use="non_commercial") as holder:
        answer = holder.lookup("drug_labels", drug_labels.REMOTE_LABELS_TABLE, drug_labels._gene_keys(genes))
    local = drug_labels.lookup_genes(labels_root, genes)
    assert len(local) == len(alone), "every gene is on a label in the slice, so an empty answer cannot pass"
    assert drug_labels._genes_from_rows(answer.rows, genes) == local


def test_a_gene_inside_a_multi_gene_label_answers_alike_on_both_routes(
    httpfs, loopback_hub, labels_root: Path
) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["drug_labels"], labels_root, COMMIT)
    _, inside = _label_genes(labels_root)
    assert inside, "the slice names VKORC1 only beside CYP2C9"
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url, declared_use="non_commercial") as holder:
        answer = holder.lookup("drug_labels", drug_labels.REMOTE_LABELS_TABLE, drug_labels._gene_keys(inside))
    assert drug_labels._genes_from_rows(answer.rows, inside) == drug_labels.lookup_genes(labels_root, inside)


# ── the remote compare is the local compare, on every lane (the pm, 6e52b9a1) ──────────────────────
#
# One walk over `REMOTE_LANES`. Each lane's probe asks its keyed function the same keys on the local route
# and through a holder, including a key spelled in another case than the snapshot stores it and, where the
# lane has one, a key inside a `;`-joined cell, and returns both answers. The walk asserts they are equal
# on Hugging Face, and again with the registry's proxy in front, which compares a whole cell exactly.

ENSEMBL_SPLIT = _ASSETS / "ensembl_split_multialt" / "split" / "data" / "homo_sapiens-split.parquet"
CONSTRAINT_SLICE = _ASSETS / "gnomad_v4.1_constraint_slice.tsv"
#: A loopback proxy URL: never contacted, the `MockTransport` answers it.
PROXY = "http://127.0.0.1:9"


@pytest.fixture(scope="module")
def ensembl_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("ensembl") / "snap"
    (root / "data").mkdir(parents=True)
    (root / "data" / "homo_sapiens.parquet").write_bytes(ENSEMBL_SPLIT.read_bytes())
    return root


@pytest.fixture(scope="module")
def clinvar_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("clinvar") / "snap"
    clinvar_build.build_snapshot(_ASSETS / "clinvar_GRCh38_slice.vcf.gz", root)
    return root


@pytest.fixture(scope="module")
def constraint_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return constraint_build.build_snapshot(
        CONSTRAINT_SLICE, tmp_path_factory.mktemp("constraint") / "snap"
    ).out_dir


@pytest.fixture(scope="module")
def cpic_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """CPIC's `alleles` table: two genes, one cell a joined pair, which CPIC's compare never splits."""
    root = tmp_path_factory.mktemp("cpic") / "snap"
    (root / "data").mkdir(parents=True)
    pl.DataFrame(
        {
            "gene": ["CYP2C19", "CYP2C19", "CYP2D6", "CYP2C9;VKORC1"],
            "allele": ["*1", "*17", "*4", "*2"],
            "activity_value": ["1.0", "1.5", "0.0", "0.5"],
            "clinical_function_status": [
                "Normal function",
                "Increased function",
                "No function",
                "Decreased function",
            ],
        }
    ).write_parquet(root / "data" / "alleles.parquet")
    return root


@pytest.fixture(scope="module")
def clinpgx_joined_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The ClinPGx slice with one annotation's `Gene` cell naming two genes (`SLCO1B1;KLC1`)."""
    tmp = tmp_path_factory.mktemp("clinpgx-joined")
    slice_dir = tmp / "slice"
    slice_dir.mkdir()
    for path in CLINPGX_SLICE.iterdir():
        (slice_dir / path.name).write_bytes(path.read_bytes())
    table = slice_dir / "summary_annotations.tsv"
    lines = table.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    at = next(i for i, line in enumerate(lines) if "\tSLCO1B1\t" in line)
    row = lines[at].split("\t")
    row[header.index("Gene")] = "SLCO1B1;KLC1"
    lines[at] = "\t".join(row)
    table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    archive = _zipped(slice_dir, tmp / "summaryAnnotations.zip")
    return clinpgx_build.build_snapshot(archive, tmp / "snap", source_url="file://joined").out_dir


class _Recorder:
    """A holder seen through `lookup`, keeping every answer with the table and keys it was asked."""

    def __init__(self, holder: RemoteSnapshots) -> None:
        self.holder = holder
        self.asked: list[tuple[str, dict[str, list], RemoteAnswer]] = []

    def lookup(self, lane: str, table: str, keys: dict[str, list]) -> RemoteAnswer:
        answer = self.holder.lookup(lane, table, keys)
        self.asked.append((table, keys, answer))
        return answer


def _first_cell(root: Path, table: str, column: str) -> str:
    return _parquet_values(root / "data" / f"{table}.parquet", column)[0]


def _ensembl_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    root = request.getfixturevalue("ensembl_root")
    positions = [("16", 23635706, None, None), ("chrX", 634689, None, None)]
    local = resolver.lookup_loci(root, [], positions)[1]
    assert local[positions[0]], "the slice holds rsIDs at 16:23635706, so equality is not vacuous"
    answered = lookup_module._remote_loci(
        lookup_module.VariantHint(rsid=None), "ensembl", None, positions[:1], remote_
    )
    answered_x = lookup_module._remote_loci(
        lookup_module.VariantHint(rsid=None), "ensembl", None, positions[1:], remote_
    )
    return root, local, {**answered[1], **answered_x[1]}


def _clinvar_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    root = request.getfixturevalue("clinvar_root")
    local: list[object] = []
    answered: list[object] = []
    for rsid, position in (("rs334", ("11", 5227002, "T", "A")), ("RS334", ("chr11", 5227002, "T", "A"))):
        local.append(clinvar.lookup_loci(root, [rsid], [position])[:2])
        hint = lookup_module.VariantHint(rsid=rsid)
        answered.append(lookup_module._remote_loci(hint, "clinvar", rsid, [position], remote_)[:2])
    assert local[0][0]["rs334"], "the slice holds rs334, so equality is not vacuous"
    return root, local, answered


def _constraint_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    root = request.getfixturevalue("constraint_root")
    stored = _first_cell(root, "gnomad_constraint", "gene")
    genes = [stored, stored.lower(), "NOT_A_GENE"]
    local = gene_metrics.lookup_snapshot(root, genes)
    rows = remote_.lookup("constraint", "gnomad_constraint", {"gene": genes}).rows
    for row in rows:
        row["constraint_flags"] = gene_metrics.normalize_constraint_flags(row["constraint_flags"])
    return root, local, {row["gene"]: row for row in rows}


def _clinpgx_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    root = request.getfixturevalue("clinpgx_joined_root")
    genes = ["slco1b1", "KLC1", " Cyp2c19 ", "NOT_A_GENE"]
    rsids = [_first_cell(root, "annotations", "rsid").upper()]
    local = (clinpgx.lookup_genes(root, genes), clinpgx.lookup_rsids(root, rsids))
    by_gene = remote_.lookup("clinpgx", clinpgx.REMOTE_ANNOTATIONS_TABLE, clinpgx._gene_keys(genes)).rows
    by_rsid = remote_.lookup("clinpgx", clinpgx.REMOTE_ANNOTATIONS_TABLE, clinpgx._rsid_keys(rsids)).rows
    assert "KLC1" in local[0], "the joined cell answers its second gene locally, so equality is not vacuous"
    return root, local, (clinpgx._genes_from_rows(by_gene, genes), clinpgx._rsids_from_rows(by_rsid, rsids))


def _cpic_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    root = request.getfixturevalue("cpic_root")
    client = cpic.CpicSnapshotClient(root)
    genes = ["cyp2c19", "VKORC1", "CYP2D6"]
    local = {gene: sorted((a.gene, a.allele) for a in client.alleles_for_gene(gene)) for gene in genes}
    remote_answer = {
        gene: sorted(
            (r["gene"], r["allele"]) for r in remote_.lookup("cpic", "alleles", {"gene": [gene]}).rows
        )
        for gene in genes
    }
    assert local["cyp2c19"], "a gene in another case is CPIC's gene locally, so equality is not vacuous"
    return root, local, remote_answer


def _drug_labels_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    root = request.getfixturevalue("labels_root")
    whole, inside = _label_genes(root)
    genes = [whole[0].lower(), *inside, "NOT_A_GENE"]
    rows = remote_.lookup("drug_labels", drug_labels.REMOTE_LABELS_TABLE, drug_labels._gene_keys(genes)).rows
    local = drug_labels.lookup_genes(root, genes)
    assert set(inside) <= set(local), (
        "a gene inside a joined cell answers locally, so equality is not vacuous"
    )
    return root, local, drug_labels._genes_from_rows(rows, genes)


def _opentargets_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    positions = [("chr6", 26092913), ("6", 26092960), ("8", 78193100)]
    local = opentargets.lookup_variants(OPENTARGETS_SLICE, positions)
    rows = remote_.lookup(
        "opentargets", opentargets.REMOTE_VARIANTS_TABLE, opentargets._variant_keys(positions)
    ).rows
    return OPENTARGETS_SLICE, local, opentargets._variants_from_rows(rows, positions)


def _civic_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    root = request.getfixturevalue("civic_root")
    stored = _civic_values(root, "gene")[0]
    genes = [stored.lower(), f" {stored.title()} ", "NOT_A_GENE"]
    rsids = [f"RS{_civic_values(root, 'rsid')[0].removeprefix('rs')}"]
    by_gene = remote_.lookup(
        "civic", civic_draft.REMOTE_CIVIC_TABLE, civic_draft._civic_gene_keys(genes)
    ).rows
    by_rsid = remote_.lookup(
        "civic", civic_draft.REMOTE_CIVIC_TABLE, civic_draft._civic_rsid_keys(rsids)
    ).rows
    local = (civic_draft.lookup_genes(root, genes), civic_draft.lookup_rsids(root, rsids))
    assert local[0], "a gene in another case is CIViC's gene locally, so equality is not vacuous"
    return (
        root,
        local,
        (civic_draft._genes_from_rows(by_gene, genes), civic_draft._rsids_from_rows(by_rsid, rsids)),
    )


def _clinvar_gkm_probe(request: pytest.FixtureRequest, remote_: _Recorder) -> tuple[Path, object, object]:
    root = request.getfixturevalue("gkm_root")
    positions, rsids = [("chr4", 87310240), ("2", 166204470)], ["RS1003713657", "77944059"]
    by_position = remote_.lookup(
        "clinvar_gkm", clinvar_gkm.REMOTE_WITNESS_TABLE, clinvar_gkm._variant_keys(positions)
    )
    by_rsid = remote_.lookup("clinvar_gkm", clinvar_gkm.REMOTE_WITNESS_TABLE, clinvar_gkm._rsid_keys(rsids))
    local = (clinvar_gkm.lookup_variants(root, positions), clinvar_gkm.lookup_rsids(root, rsids))
    return (
        root,
        local,
        (
            clinvar_gkm._variants_from_rows(by_position.rows, positions),
            clinvar_gkm._rsids_from_rows(by_rsid.rows, rsids),
        ),
    )


#: One probe per remote lane: `(request, holder) -> (the lane's snapshot, local answer, remote answer)`.
_PROBES: dict[str, Callable[[pytest.FixtureRequest, _Recorder], tuple[Path, object, object]]] = {
    "ensembl": _ensembl_probe,
    "clinvar": _clinvar_probe,
    "constraint": _constraint_probe,
    "clinpgx": _clinpgx_probe,
    "cpic": _cpic_probe,
    "drug_labels": _drug_labels_probe,
    "opentargets": _opentargets_probe,
    "civic": _civic_probe,
    "clinvar_gkm": _clinvar_gkm_probe,
}


def test_a_key_compare_reads_a_key_and_a_cell_one_way() -> None:
    joined = resolver.KeyCompare(fold=True, separator=";")
    assert joined.members(" KLC1; xrcc3 ;;") == ("klc1", "xrcc3")
    assert joined.parameter(["Klc1", " KLC1 ", ""]) == ["klc1"]
    assert resolver.KeyCompare(fold=True).members(" Brca1 ") == ("brca1",)
    assert resolver.EXACT.exact and resolver.EXACT.members("Brca1") == ("Brca1",)
    assert not joined.exact and not resolver.KeyCompare(separator=";").exact
    con = duckdb.connect()
    cells = ["CYP2C9;VKORC1", " vkorc1 ", "VKORC1X", None]
    found = con.execute(
        f"SELECT cell FROM (SELECT unnest(?::VARCHAR[]) AS cell) WHERE {joined.predicate('cell')} ORDER BY ALL",
        [cells, joined.parameter(["VKORC1"])],
    ).fetchall()
    assert [cell for (cell,) in found] == [" vkorc1 ", "CYP2C9;VKORC1"]


def test_every_declared_compare_is_on_a_key_column() -> None:
    declared = {c for lane in REMOTE_LANES.values() for cols in lane.compares.values() for c in cols}
    assert declared and declared <= set(remote.KEY_COLUMNS)


def test_every_remote_lane_has_a_probe() -> None:
    """`@registry-completeness`: a lane added to `REMOTE_LANES` is a lane the walks below must ask."""
    assert set(_PROBES) == set(REMOTE_LANES)


def _published_probe(request: pytest.FixtureRequest, lane: str, hub: Any) -> Path:
    """The lane's snapshot, published on the loopback hub before the probe asks it."""
    root = {
        "ensembl": "ensembl_root",
        "clinvar": "clinvar_root",
        "constraint": "constraint_root",
        "clinpgx": "clinpgx_joined_root",
        "cpic": "cpic_root",
        "drug_labels": "labels_root",
        "civic": "civic_root",
        "clinvar_gkm": "gkm_root",
    }.get(lane)
    path = OPENTARGETS_SLICE if root is None else request.getfixturevalue(root)
    hub.publish(SNAPSHOT_REPO_IDS[lane], path, COMMIT)
    return path


@pytest.mark.parametrize("lane", sorted(REMOTE_LANES))
def test_the_remote_compare_is_the_local_compare_on_every_lane(
    lane: str, request: pytest.FixtureRequest, httpfs, loopback_hub
) -> None:
    """The same keys, a key in another case and one inside a joined cell among them, answer alike on both
    routes (the pm, 6e52b9a1: the remote compare is not the local compare, fixed as a class)."""
    _published_probe(request, lane, loopback_hub)
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url, declared_use="non_commercial") as holder:
        recorder = _Recorder(holder)
        _root, local, remote_answer = _PROBES[lane](request, recorder)
    assert recorder.asked, "the probe asked the holder"
    assert remote_answer == local
    assert {answer.route.route for _table, _keys, answer in recorder.asked} == {"hf"}


def _registry_rows(root: Path, table: str, keys: dict[str, list]) -> list[dict]:
    """The registry's lane filter (its `services/lanes.py` `_parquet_rows`), over the snapshot's files.

    It compares a whole cell exactly: a list column by its elements, anything else cast to a string, a
    position as an integer, `chrom` as bare or `chr`-prefixed, and `chrom[i]` with `start[i]` paired when
    more than one of each is given."""
    files = sorted(
        str(p) for p in (root / "data").glob("*.parquet") if remote.table_name(f"data/{p.name}") == table
    )
    frame = pl.scan_parquet(files)
    schema = frame.collect_schema()
    position = next((c for c in remote.POSITION_COLUMNS if c in schema), "start")
    forms = lambda c: [str(c).removeprefix("chr"), f"chr{str(c).removeprefix('chr')}"]  # noqa: E731
    condition = None
    if "chrom" in keys and len(keys["chrom"]) == len(keys["start"]) > 1:
        condition = pl.any_horizontal(
            [
                pl.col("chrom").cast(pl.String).is_in(forms(c)) & (pl.col(position) == int(s))
                for c, s in zip(keys["chrom"], keys["start"], strict=True)
            ]
        )
        keys = {k: v for k, v in keys.items() if k not in ("chrom", "start")}
    for column, values in keys.items():
        if column == "chrom":
            clause = pl.col("chrom").cast(pl.String).is_in([f for v in values for f in forms(v)])
        elif column == "start":
            clause = pl.col(position).is_in([int(v) for v in values])
        elif isinstance(schema[column], pl.List):
            clause = (
                pl.col(column)
                .list.eval(pl.element().cast(pl.String).is_in([str(v) for v in values]))
                .list.any()
            )
        else:
            clause = pl.col(column).cast(pl.String).is_in([str(v) for v in values])
        condition = clause if condition is None else condition & clause
    return json.loads(frame.filter(condition).collect().write_json())


@pytest.mark.parametrize("lane", sorted(REMOTE_LANES))
def test_the_proxy_answers_every_lane_it_compares_alike_and_is_not_asked_where_it_cannot(
    lane: str, request: pytest.FixtureRequest, httpfs, loopback_hub
) -> None:
    """The proxy leg, walked over `REMOTE_LANES` through an `httpx.MockTransport` that compares as the
    registry does (the pm's RM431 reading 6). A key the lane compares exactly is answered by the proxy; a
    folded or joined one is not sent to it, and Hugging Face answers, so the answer equals the local one."""
    root = _published_probe(request, lane, loopback_hub)
    proxied: list[tuple[str, dict[str, list]]] = []

    def registry(http: httpx.Request) -> httpx.Response:
        _lane, table = http.url.path.split("/")[-2:]
        keys = json.loads(http.content)["keys"]
        proxied.append((table, keys))
        rows = _registry_rows(root, table, keys)
        return httpx.Response(
            200, json={"lane": lane, "table": table, "served_from": "local", "rows": rows, "truncated": False}
        )

    holder = RemoteSnapshots(
        proxy_url=PROXY, hf_base_url=loopback_hub.base_url, declared_use="non_commercial"
    )
    holder._proxy.close()
    holder._proxy = httpx.Client(transport=httpx.MockTransport(registry))
    with holder:
        recorder = _Recorder(holder)
        _root, local, remote_answer = _PROBES[lane](request, recorder)
    assert remote_answer == local
    spec = REMOTE_LANES[lane]
    expected = {
        table: "proxy" if spec.proxy_compares(table, set(keys) - {"chrom", "start"}) else "hf"
        for table, keys, _answer in recorder.asked
    }
    assert {table: answer.route.route for table, _keys, answer in recorder.asked} == expected
    assert {table for table, _keys in proxied} == {t for t, route in expected.items() if route == "proxy"}
