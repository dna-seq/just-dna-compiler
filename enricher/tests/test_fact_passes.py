"""The two sidecar passes (frequency, gene metrics) plus VRS minting into `resolution.csv`.

Covers the behaviours that make these passes safe to re-run and safe to trust: determinism of the
written files, existing rows never being clobbered, `--offline` performing genuinely zero network
calls, and the fact that the two gene-constraint routes are labelled as the different releases they
actually are.
"""

import csv
import json
from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import derive_vrs_allele_id

from just_dna_enricher.constraint_build import build_snapshot
from just_dna_enricher.frequencies import enrich_frequencies, format_faf95
from just_dna_enricher.gene_metrics import enrich_gene_metrics
from just_dna_enricher.gnomad import (
    API_CONSTRAINT_DATASET_LABEL,
    CONSTRAINT_DATASET_LABEL,
    GnomadClient,
    GnomadSettings,
    PacingGate,
)
from just_dna_enricher.vrs import VrsMinter, mint_resolution_rows

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "rs334,11,5227002,T,A,A/T,risk,Sickle-cell carrier,HBB\n"
    "rs1801133,1,11796321,G,A,A/G,risk,Reduced activity,MTHFR\n"
)


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        f"{derive_vrs_allele_id('11', 5227002, 'T', 'A')},rs334,11,5227002,T,A,GRCh38,0,cache,resolved\n"
        f"{derive_vrs_allele_id('1', 11796321, 'G', 'A')},rs1801133,1,11796321,G,A,GRCh38,0,cache,resolved\n"
    )
    return spec


class _NoNetwork(httpx.BaseTransport):
    """A transport that fails loudly. `--offline` must never reach it."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"offline run attempted a network call to {request.url}")


def _mock_client(handler) -> GnomadClient:
    client = GnomadClient(settings=GnomadSettings())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _frequency_handler(request: httpx.Request) -> httpx.Response:
    """Serve the recorded payload for whichever aliases the batch asked for."""
    recorded = json.loads((_ASSETS / "gnomad_v4.1_variant_payload.json").read_text())["data"]
    query = json.loads(request.content)["query"]
    data = {}
    for index, line in enumerate(ln for ln in query.splitlines() if "variant(" in ln):
        if "11-5227002-T-A" in line:
            data[f"v{index}"] = recorded["sickle"]
        elif "1-11796321-G-A" in line:
            data[f"v{index}"] = recorded["mthfr"]
        else:
            data[f"v{index}"] = None
    return httpx.Response(200, json={"data": data})


# ── the frequency pass ──────────────────────────────────────────────────────────────────────────


def test_frequency_pass_writes_one_row_per_allele_and_group(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = enrich_frequencies(spec, client=_mock_client(_frequency_handler))

    rows = {(r.variant_key, r.population): r for r in result.rows}
    assert len(result.covered) == 2
    assert not result.missing

    sickle_key = derive_vrs_allele_id("11", 5227002, "T", "A")
    globally = rows[(sickle_key, "global")]
    # AC/AN are stored as integers; the frequency is derived, never a stored column.
    assert globally.allele_count > 0 and globally.allele_number > 0
    assert globally.allele_frequency == globally.allele_count / globally.allele_number
    assert "allele_frequency" not in (spec / "frequencies.csv").read_text().splitlines()[0]
    # faf95 sits on exactly one group's row across the whole allele.
    with_faf = [p for (k, p), r in rows.items() if k == sickle_key and r.faf95 is not None]
    assert len(with_faf) == 1


def test_frequency_pass_is_deterministic(tmp_path: Path) -> None:
    """Two runs from scratch produce byte-identical files, apart from the advisory timestamp."""
    def run(name: str) -> list[list[str]]:
        spec = _spec(tmp_path / name)
        enrich_frequencies(spec, client=_mock_client(_frequency_handler))
        with (spec / "frequencies.csv").open(newline="") as handle:
            reader = csv.DictReader(handle)
            return [[v for k, v in row.items() if k != "fetched_at"] for row in reader]

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert run("a") == run("b")


def test_existing_frequency_rows_are_authoritative(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    key = derive_vrs_allele_id("11", 5227002, "T", "A")
    (spec / "frequencies.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alt,genome_build,population,allele_count,allele_number,"
        "homozygote_count,hemizygote_count,faf95,dataset,vrs_id,caid,source,status,fetched_at\n"
        f"{key},rs334,11,5227002,T,A,GRCh38,global,1,2,,,,hand_curated,,,manual,resolved,\n"
    )
    result = enrich_frequencies(spec, client=_mock_client(_frequency_handler))
    kept = [r for r in result.rows if r.variant_key == key]
    assert [r.source for r in kept] == ["manual"]      # not refetched, not overwritten
    assert kept[0].dataset == "hand_curated"


def test_frequency_offline_is_a_no_op_with_zero_egress(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    client = GnomadClient()
    client._client = httpx.Client(transport=_NoNetwork())
    result = enrich_frequencies(spec, offline=True, client=client)
    assert result.skipped_offline
    assert result.rows == []
    assert not (spec / "frequencies.csv").exists()


def test_populations_filter_keeps_one_row_per_allele(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = enrich_frequencies(
        spec, populations=["global"], client=_mock_client(_frequency_handler)
    )
    assert {r.population for r in result.rows} == {"global"}
    assert len(result.rows) == 2  # one per allele


def test_faf95_round_trips_through_its_canonical_cell() -> None:
    # The one stored float: its written form must reload to the identical double (P7).
    for value in (0.04815774000000001, 0.0482, 1e-9, 0.0, 1.0):
        assert float(format_faf95(value)) == value
    assert format_faf95(None) == ""


def test_unknown_allele_records_not_found_rather_than_silence(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        "9:9:A:G,,9,9,A,G,GRCh38,0,cache,resolved\n"
    )
    result = enrich_frequencies(spec, client=_mock_client(_frequency_handler))
    assert len(result.missing) == 1
    assert [r.status for r in result.rows] == ["not_found"]


# ── the gene-metrics pass ───────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def constraint_cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("cache")
    build_snapshot(_ASSETS / "gnomad_v4.1_constraint_slice.tsv", out)
    return out


def test_gene_metrics_from_the_snapshot_offline(tmp_path: Path, constraint_cache: Path) -> None:
    """The one gnomAD pass that completes with zero egress when a snapshot is provisioned."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\n"
        "rs1,A/G,risk,x,BRCA1\n"
        "rs2,A/G,risk,x,MYH7\n"
        "rs3,A/G,risk,x,BRCA1\n"   # duplicate gene → one row, not two
    )
    result = enrich_gene_metrics(spec, offline=True, constraint_cache=constraint_cache)
    assert [r.gene for r in result.rows] == ["BRCA1", "MYH7"]
    assert {r.source for r in result.rows} == {"gnomad-constraint"}
    assert {r.dataset for r in result.rows} == {CONSTRAINT_DATASET_LABEL}
    brca1 = next(r for r in result.rows if r.gene == "BRCA1")
    assert brca1.gene_id == "ENSG00000012048"
    assert brca1.mane_select is True
    assert brca1.oe_lof_lower <= brca1.oe_lof <= brca1.loeuf


def test_snapshot_and_api_are_labelled_as_the_different_releases_they_are(
    tmp_path: Path, constraint_cache: Path
) -> None:
    """The live API serves v2.1.1 constraint; the bulk file serves v4.1. They must not share a label.

    Checked against both real sources: same gene, same MANE transcript, different numbers. Recording
    them under one `dataset` would put two different facts under one name — and `dataset` is inside
    the fact set precisely to stop that.
    """
    gene_payload = json.loads((_ASSETS / "gnomad_gene_constraint_payload.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=gene_payload)

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion,gene\nrs1,A/G,risk,x,BRCA1\n")
    # No snapshot → the live-API fallback.
    from_api = enrich_gene_metrics(
        spec, constraint_cache=tmp_path / "absent", client=_mock_client(handler)
    ).rows[0]
    assert from_api.source == "gnomad-api"
    assert from_api.dataset == API_CONSTRAINT_DATASET_LABEL

    (spec / "gene_metrics.csv").unlink()
    from_snapshot = enrich_gene_metrics(spec, offline=True, constraint_cache=constraint_cache).rows[0]
    assert from_snapshot.dataset == CONSTRAINT_DATASET_LABEL

    assert from_api.dataset != from_snapshot.dataset
    assert from_api.loeuf != from_snapshot.loeuf  # genuinely different numbers, not a labelling nicety


def test_gene_metrics_offline_without_a_snapshot_records_not_found(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion,gene\nrs1,A/G,risk,x,BRCA1\n")
    result = enrich_gene_metrics(spec, offline=True, constraint_cache=tmp_path / "absent")
    assert result.missing == ["BRCA1"]
    assert [r.status for r in result.rows] == ["not_found"]


def test_gene_metrics_round_trips_through_its_csv(tmp_path: Path, constraint_cache: Path) -> None:
    """Every metric is a float, so the canonical cell format has to be exactly reloadable (P7)."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs1,A/G,risk,x,BRCA1\nrs2,A/G,risk,x,MYH7\n"
    )
    written = enrich_gene_metrics(spec, offline=True, constraint_cache=constraint_cache).rows
    with (spec / "gene_metrics.csv").open(newline="") as handle:
        reloaded = [GeneMetricsRow(**{k: (v or None) for k, v in r.items()})
                    for r in csv.DictReader(handle)]
    for before, after in zip(written, reloaded, strict=True):
        assert before.model_dump() == after.model_dump()


# ── VRS minting into the resolution table ───────────────────────────────────────────────────────


def test_minting_stamps_substitutions_with_no_network() -> None:
    rows = [
        ResolutionRow(variant_key="k1", chrom="11", start=5227002, ref="T", alts="A"),
        ResolutionRow(variant_key="k2", chrom="11", start=5226762, ref="C", alts="CA"),  # indel
        ResolutionRow(variant_key="k3", chrom="11", start=5227002, ref="T", alts="A,G"),  # multi
        ResolutionRow(variant_key="k4", rsid="rs1"),                                      # no coord
    ]
    result = mint_resolution_rows(rows, offline=True)
    assert rows[0].vrs_id == derive_vrs_allele_id("11", 5227002, "T", "A")
    assert rows[0].vrs_spec == "2.0"
    assert [r.vrs_id for r in rows[1:]] == [None, None, None]
    assert result.minted_stdlib == 1
    assert result.skipped_unmintable == 3


def test_minting_never_overwrites_an_existing_id() -> None:
    existing = derive_vrs_allele_id("1", 11796321, "G", "A")
    row = ResolutionRow(
        variant_key="k", chrom="11", start=5227002, ref="T", alts="A", vrs_id=existing
    )
    result = mint_resolution_rows([row], offline=True)
    assert row.vrs_id == existing            # a hand-corrected id survives a re-run
    assert result.already_present == 1


def test_source_reported_id_is_cross_checked_not_trusted() -> None:
    row = ResolutionRow(variant_key="k", chrom="11", start=5227002, ref="T", alts="A")
    wrong = derive_vrs_allele_id("1", 11796321, "G", "A")
    result = mint_resolution_rows([row], offline=True, source_ids={"k": wrong})
    assert row.vrs_id == derive_vrs_allele_id("11", 5227002, "T", "A")  # ours wins
    assert len(result.mismatches) == 1


def test_offline_minter_makes_no_data_proxy() -> None:
    minter = VrsMinter(offline=True)
    assert minter.mint("11", 5226762, "C", "CA") == (None, None)
    assert minter._data_proxy() is None


@pytest.mark.integration
def test_indel_normalization_is_representation_independent() -> None:
    """Two equivalent spellings of one insertion must mint the same id.

    This is what "normalized" actually buys, and the only way to see it is with real sequence: at
    chr1:55039968 the reference has a `CC` run, so inserting a `C` anchored on either base of the run
    is the same biological event written two ways. Equal ids prove justification really ran.
    """
    import os

    if not os.getenv("JUST_DNA_NETWORK_TESTS"):
        pytest.skip("needs the live sequence service — set JUST_DNA_NETWORK_TESTS=1 to run")

    minter = VrsMinter()
    left, how_left = minter.mint("1", 55039968, "C", "CC")
    right, how_right = minter.mint("1", 55039969, "C", "CC")
    assert how_left == how_right == "normalized"
    assert left is not None and left == right


def test_polars_can_read_what_the_frequency_pass_writes(tmp_path: Path) -> None:
    """A cheap guard that the emitted CSV is well-formed for the compiler's downstream reader."""
    spec = _spec(tmp_path)
    enrich_frequencies(spec, client=_mock_client(_frequency_handler))
    frame = pl.read_csv(spec / "frequencies.csv")
    assert frame.height > 0
    assert {"variant_key", "population", "allele_count", "allele_number"} <= set(frame.columns)
    with (spec / "frequencies.csv").open(newline="") as handle:
        rows = [FrequencyRow(**{k: (v or None) for k, v in r.items()}) for r in csv.DictReader(handle)]
    assert len(rows) == frame.height
