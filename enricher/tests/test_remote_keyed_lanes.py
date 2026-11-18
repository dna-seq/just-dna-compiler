"""The lanes RM431 makes remote-eligible, each by its keyed function's keys (0.9, RM431, on RM430's seam).

Each lane's published repo is a `LoopbackHub` serving a real snapshot's bytes; the holder is asked with
the keys the keyed function derives, and its rows go through the keyed function's own SQL. The answer
must equal the local reader's over the same snapshot: same keys, same rows, one SQL body.
"""

import hashlib
import json
import zipfile
from pathlib import Path

import duckdb
import pytest
from just_dna_enricher import civic_draft, clinpgx, clinpgx_build, clinvar_gkm, opentargets, remote
from just_dna_enricher.civic_build import CIVIC_PARQUET, build_snapshot
from just_dna_enricher.clinvar_gkm import ALLELE_FILE, VARIATION_FILE, WITNESS_PARQUET, parse_manifest
from just_dna_enricher.clinvar_gkm_build import build_snapshot as build_witness
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS
from just_dna_enricher.remote import REMOTE_LANES, RemoteSnapshots

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
OPENTARGETS_SLICE = _ASSETS / "opentargets_slice"
CIVIC_SLICE = _ASSETS / "civic_slice"
GKM_SLICE = _ASSETS / "clinvar_gkm_slice"
CLINPGX_SLICE = _ASSETS / "clinpgx_annotations_slice"
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "RM431: a remote route compares a gene exactly and the local reader by gene_key (case-folded), so a "
        "key in another case than CIViC stores it is answered locally only. The holder's comparison is "
        "RM430's choice; the pm placed cpic's as the remote taking the local case-folding (2026-11-18), and this "
        "marker turns into a failure the day a remote route folds case, so it is removed then."
    ),
)
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


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "RM431 follow-up: a remote route compares the whole `gene` cell exactly and the local reader each "
        "member by gene_key, so a gene asked in another case than ClinPGx stores it (and a gene inside a "
        "`;`-joined cell, 399 of 16,117 rows on the 2026-08 snapshot) is answered locally only. The holder's "
        "comparison is RM430's; this marker turns into a failure the day a remote route folds case, so it is "
        "removed then."
    ),
)
def test_a_clinpgx_gene_asked_in_another_case_answers_alike_on_both_routes(
    httpfs, loopback_hub, clinpgx_root: Path
) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinpgx"], clinpgx_root, COMMIT)
    genes = [_parquet_values(clinpgx_root / "data" / "annotations.parquet", "gene")[0].lower()]
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url, declared_use="non_commercial") as holder:
        answer = holder.lookup("clinpgx", clinpgx.REMOTE_ANNOTATIONS_TABLE, clinpgx._gene_keys(genes))
    assert clinpgx._genes_from_rows(answer.rows, genes) == clinpgx.lookup_genes(clinpgx_root, genes)
