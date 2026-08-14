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
from just_dna_enricher import gene_metrics
from just_dna_enricher.constraint_build import build_snapshot
from just_dna_enricher.frequencies import enrich_frequencies, format_faf95
from just_dna_enricher.gene_metrics import enrich_gene_metrics
from just_dna_enricher.gnomad import (
    API_CONSTRAINT_DATASET_LABEL,
    CONSTRAINT_DATASET_LABEL,
    GnomadClient,
    GnomadSettings,
)
from just_dna_enricher.net import PacingGate
from just_dna_enricher.vrs import VrsMinter, mint_resolution_rows
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import derive_vrs_allele_id, split_vrs_ids
from pydantic import ValidationError

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
    # `source` names the licensed source, not the route the row came in by (RM33); the route is
    # `dataset`'s job and the assertion below is the one that carries the meaning.
    assert {r.source for r in result.rows} == {"gnomad"}
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
    # No snapshot and no provisioning → the live-API fallback. `download=False` is what keeps this
    # network-free now that an absent snapshot is fetched from HuggingFace rather than shrugged at.
    from_api = enrich_gene_metrics(
        spec, constraint_cache=tmp_path / "absent", download=False,
        client=_mock_client(handler),
    ).rows[0]
    assert from_api.dataset == API_CONSTRAINT_DATASET_LABEL
    assert from_api.source == "gnomad"        # one licensed source, two releases

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


def test_a_missing_snapshot_is_provisioned_before_falling_back_to_the_api(
    tmp_path: Path, monkeypatch, constraint_cache: Path
) -> None:
    """The wiring: `ensure_constraint_snapshot` existed with no caller, so a plain install never got the
    v4.1 snapshot and silently used the live API's **v2.1.1** numbers instead.

    Provisioning is faked to the built fixture snapshot — the point under test is that the pass *asks*,
    and then reads what it was given rather than reaching for the API.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion,gene\nrs1,A/G,risk,x,BRCA1\n")

    asked: list[Path] = []

    def fake_ensure(cache=None):
        asked.append(cache)
        return constraint_cache

    monkeypatch.setattr(gene_metrics, "ensure_constraint_snapshot", fake_ensure)
    monkeypatch.setattr(
        gene_metrics, "resolve_constraint_reference",
        lambda cache=None: constraint_cache if asked else None,
    )

    def explode(*_args, **_kwargs):  # the API must not be reached at all
        raise AssertionError("fell through to the live API despite a provisionable snapshot")

    monkeypatch.setattr(gene_metrics.GnomadClient, "fetch_gene_constraint", explode)
    result = enrich_gene_metrics(spec, constraint_cache=None)

    assert asked == [None]
    assert [r.dataset for r in result.rows] == [CONSTRAINT_DATASET_LABEL]   # v4.1, not the API's v2.1.1


def test_offline_never_provisions(tmp_path: Path, monkeypatch) -> None:
    """`--offline` is the switch that turns provisioning off — there is no separate flag, exactly as
    for the Ensembl and ClinVar snapshots in `enrich()`."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion,gene\nrs1,A/G,risk,x,BRCA1\n")

    def explode(cache=None):
        raise AssertionError("--offline provisioned a snapshot over the network")

    monkeypatch.setattr(gene_metrics, "ensure_constraint_snapshot", explode)
    result = enrich_gene_metrics(spec, offline=True, constraint_cache=tmp_path / "absent")
    assert [r.status for r in result.rows] == ["not_found"]


def test_a_failed_provisioning_degrades_to_the_api_and_says_which_release(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """HuggingFace has gone dark mid-demo before. A provisioning failure must not sink the pass — and
    the warning has to name the consequence, which is *older numbers*, not "no numbers"."""
    gene_payload = json.loads((_ASSETS / "gnomad_gene_constraint_payload.json").read_text())
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion,gene\nrs1,A/G,risk,x,BRCA1\n")

    def boom(cache=None):
        raise RuntimeError("HF unreachable")

    monkeypatch.setattr(gene_metrics, "ensure_constraint_snapshot", boom)
    with caplog.at_level("WARNING"):
        result = enrich_gene_metrics(
            spec, constraint_cache=tmp_path / "absent",
            client=_mock_client(lambda request: httpx.Response(200, json=gene_payload)),
        )
    assert [r.dataset for r in result.rows] == [API_CONSTRAINT_DATASET_LABEL]
    message = "\n".join(r.getMessage() for r in caplog.records)
    assert "provisioning failed" in message and "v2.1.1" in message


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
    assert [r.vrs_id for r in rows[1::2]] == [None, None]  # the indel and the coordinate-less row
    # The multi-allelic row mints BOTH of its alleles: nothing is being picked, so the old refusal
    # (`_single_alt`, which returned None for any comma-joined cell) was throwing away two ids it had
    # every input for. Counters are per ALLELE — 1 + 2 minted, the indel and the no-coord row skipped.
    assert rows[2].vrs_id == ",".join(
        [derive_vrs_allele_id("11", 5227002, "T", "A"), derive_vrs_allele_id("11", 5227002, "T", "G")]
    )
    assert result.minted_stdlib == 3
    assert result.skipped_unmintable == 2


def test_a_multi_allelic_row_keeps_the_ids_it_can_mint_beside_the_ones_it_cannot() -> None:
    """A site carrying a substitution *and* an indel mints a hole, not an empty row.

    Offline, the indel has no justification path, so its member is empty — and the substitutions
    beside it keep their ids. Refusing the whole row over one unmintable allele would repeat the
    abstention this shape was built to remove, one level down.
    """
    row = ResolutionRow(variant_key="k", chrom="11", start=5227002, ref="T", alts="A,TCC,G")
    result = mint_resolution_rows([row], offline=True)

    assert split_vrs_ids(row.vrs_id) == [
        derive_vrs_allele_id("11", 5227002, "T", "A"),
        None,
        derive_vrs_allele_id("11", 5227002, "T", "G"),
    ]
    assert row.vrs_spec == "2.0"
    assert (result.minted_stdlib, result.skipped_unmintable) == (2, 1)


def test_the_mint_pass_reports_its_shortfall_not_only_its_successes() -> None:
    """A success count on a half-anonymous table reads as a clean bill.

    The counters said "minted 237" for a module where 185 alleles came out with no id, and nothing
    said the second number. That matters now in a way it did not when a VA was decorative: it is
    becoming the key these tables are joined on, so the covered *fraction* is the reliability figure a
    consumer needs, and an unstated one is the defect.

    Grouped by reason, one line each — the alternative is a per-row wall that buries every other
    finding a run produces.
    """
    rows = [
        ResolutionRow(variant_key="k1", chrom="11", start=5227002, ref="T", alts="A,G"),  # mints 2
        ResolutionRow(variant_key="k2", chrom="11", start=5226762, ref="C", alts="CA"),   # indel
        ResolutionRow(variant_key="k3", chrom="11", start=5226763, ref="G", alts="GT"),   # indel
        ResolutionRow(variant_key="k4", rsid="rs1"),                                      # no coord
    ]
    result = mint_resolution_rows(rows, offline=True)

    assert (result.alleles, result.identified) == (5, 2)
    assert not result.complete
    lines = result.coverage_warnings()
    assert "2/5" in lines[0] and "40%" in lines[0]
    # Two reasons, not four rows: the two indels share one line, and it names the remedy that works.
    assert len(lines) == 3
    assert any("2 allele(s)" in line and "--offline" in line for line in lines[1:])
    assert any("1 allele(s)" in line and "no coordinate" in line for line in lines[1:])


def test_a_fully_minted_table_reports_no_shortfall() -> None:
    """`complete` is the question a caller has, and a warning that always fires is not a warning."""
    rows = [ResolutionRow(variant_key="k", chrom="11", start=5227002, ref="T", alts="A,G")]
    result = mint_resolution_rows(rows, offline=True)

    assert result.complete and (result.alleles, result.identified) == (2, 2)
    assert result.coverage_warnings() == []


def test_a_hole_in_a_pre_existing_cell_is_not_counted_as_covered() -> None:
    """`already_present` is a per-ROW verdict, and coverage is a per-ALLELE one.

    A hand-filled cell naming one of two alleles is left alone — the pass never reaches inside a cell
    it did not write — but reporting that row as fully covered would launder the hole into a number a
    consumer trusts.
    """
    row = ResolutionRow(
        variant_key="k", chrom="11", start=5227002, ref="T", alts="A,G",
        vrs_id=f"{derive_vrs_allele_id('11', 5227002, 'T', 'A')},",
    )
    result = mint_resolution_rows([row], offline=True)

    assert result.already_present == 1
    assert (result.alleles, result.identified) == (2, 1)
    assert not result.complete


def test_a_vrs_id_cell_must_stay_aligned_with_alts() -> None:
    """The cost of a parallel array is desync, so the model refuses one at load.

    Both directions: too few ids for the alleles, and too many. The compiler's verify pass is the
    second net, for a pair that counts right and is ordered wrong.
    """
    one = derive_vrs_allele_id("11", 5227002, "T", "A")
    for alts, vrs_id in [("A,G", one), ("A", f"{one},{one}")]:
        with pytest.raises(ValidationError, match="positionally aligned with alts"):
            ResolutionRow(
                variant_key="k", chrom="11", start=5227002, ref="T", alts=alts, vrs_id=vrs_id
            )


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


# ── Alleles that name no sequence: RM5's `<DEL:…>`, RM58's `.`, RM59's `*` ──────────────────────


class _ReachableSequences:
    """A `SequenceProxy` stand-in whose proxy is always there, answering nothing.

    The crash these tests pin is **online-only**: offline, `_data_proxy()` returns `None` and
    `_mint_normalized` returns before it builds anything, so an offline run cannot see it. The
    sentinel needs no reads, because the failure is in `models.Allele(...)` — constructed *before*
    the proxy is used, outside the `try` that exists for live-service failures.
    """

    def proxy(self) -> object:
        return object()


def _online_minter() -> VrsMinter:
    return VrsMinter(sequences=_ReachableSequences())


def test_a_symbolic_allele_is_left_unminted_instead_of_aborting_the_run() -> None:
    """RM5 made `<DEL:4977>` a legal ALT and the VRS tier was never told.

    `mint` routes every non-substitution to `_mint_normalized`, which builds
    `models.LiteralSequenceExpression(sequence=alt.upper())` — whose `sequence` pattern is
    `^[A-Z*\\-]*$` — so the MT common deletion killed the whole enrich run with an unhandled
    `pydantic.ValidationError`, the same shape as the `UnsupportedBuildError` defect eight lines
    above it. Reproduced on `reference_examples/mt_common_deletion`'s own row.
    """
    minter = _online_minter()
    assert minter.mint("MT", 8470, "N", "<DEL:4977>") == (None, None)

    row = ResolutionRow(
        variant_key="MT:8470:N:<DEL:4977>", chrom="MT", start=8470, ref="N", alts="<DEL:4977>",
        source="authored", status="resolved",
    )
    result = mint_resolution_rows([row], minter=minter)

    assert row.vrs_id is None and row.vrs_spec is None
    assert (result.skipped_unmintable, result.identified, result.alleles) == (1, 0, 1)


def test_a_malformed_symbolic_allele_takes_the_same_route() -> None:
    """`is_symbolic_allele` is lenient (anything opening with `<`) precisely for this: `<FOO>` and the
    unterminated `<DEL` are not usable symbolic alleles, and they reach the same model with the same
    characters it cannot hold. A guard keyed on the strict parser would let both through."""
    minter = _online_minter()
    assert minter.mint("MT", 8470, "N", "<FOO>") == (None, None)
    assert minter.mint("MT", 8470, "N", "<DEL:1500") == (None, None)


def test_the_two_markers_that_name_no_allele_are_left_unminted() -> None:
    """`.` (RM58) raises the *identical* ValidationError; `*` (RM59) passes the model's pattern and
    would have minted a content-addressed id for a state that is not a sequence at all.

    Their reasons are kept apart, as everywhere else: `.` asserts that no alternate allele exists and
    has an authored repair, `*` records that a sample's allele could not be observed and has none.
    """
    minter = _online_minter()
    assert minter.mint("1", 11796321, "G", ".") == (None, None)
    assert minter.mint("1", 11796321, "G", "*") == (None, None)

    rows = [
        ResolutionRow(variant_key="k1", chrom="1", start=11796321, ref="G", alts="."),
        ResolutionRow(variant_key="k2", chrom="1", start=11796321, ref="G", alts="*"),
    ]
    result = mint_resolution_rows(rows, minter=minter)

    assert [row.vrs_id for row in rows] == [None, None]
    assert len(result.unmintable_reasons) == 2, "two classes, not one bucket"


def test_a_marker_in_ref_is_not_diagnosed_against_alts() -> None:
    """`.` in `ref` and `.` in `alts` are different mistakes, and only the second is repaired by
    emptying the cell — so a reason that offers that repair for the first would send the author to
    delete a perfectly good ALT. Same misdiagnosis class as D1-2, one column over.
    """
    minter = VrsMinter(offline=True)
    in_alts = minter.why_not("1", 11796321, "G", ".")
    in_ref = minter.why_not("1", 11796321, ".", "A")

    assert minter.mint("1", 11796321, ".", "A") == (None, None)
    assert in_alts != in_ref
    assert "leave the cell empty" in in_alts and "leave the cell empty" not in in_ref


def test_a_row_keeps_the_substitution_beside_its_symbolic_allele() -> None:
    """The guard is per ALLELE, like every other decision here: a site carrying `A` and `<DEL:4977>`
    names the one it can and leaves a hole for the one it cannot."""
    row = ResolutionRow(variant_key="k", chrom="MT", start=8993, ref="T", alts="G,<DEL:4977>")
    result = mint_resolution_rows([row], minter=_online_minter())

    assert split_vrs_ids(row.vrs_id) == [derive_vrs_allele_id("MT", 8993, "T", "G"), None]
    assert (result.minted_stdlib, result.skipped_unmintable) == (1, 1)


def test_the_symbolic_reason_is_permanent_and_never_points_at_the_crash() -> None:
    """D1-2: offline, the same allele was reported as an indel *"which must be justified against the
    reference sequence — re-run without --offline to mint it"*, and that re-run is the crash above.

    A symbolic allele names no sequence by construction, so the reason class is permanent — and it is
    one constant string, so two different spellings collapse into one line rather than a wall.
    """
    rows = [
        ResolutionRow(variant_key="k1", chrom="MT", start=8470, ref="N", alts="<DEL:4977>"),
        ResolutionRow(variant_key="k2", chrom="22", start=42126499, ref="N", alts="<DUP:16000>"),
        ResolutionRow(variant_key="k3", chrom="11", start=5226762, ref="C", alts="CA"),  # a real indel
    ]
    result = mint_resolution_rows(rows, offline=True)

    symbolic = [reason for reason in result.unmintable_reasons if "--offline" not in reason]
    assert len(symbolic) == 1 and result.unmintable_reasons[symbolic[0]] == 2
    assert "--offline" not in symbolic[0]

    lines = result.coverage_warnings()
    assert sum("2 allele(s)" in line for line in lines[1:]) == 1
    # The real indel keeps its own remedy: `--offline` is exactly what blocks that one.
    assert any("1 allele(s)" in line and "--offline" in line for line in lines[1:])


def test_the_symbolic_reason_outranks_the_build_it_was_authored_on() -> None:
    """A symbolic allele on a GRCh37 row is unmintable for a reason a refget table would not clear, so
    the permanent class is the one reported — `why_not` mirrors `mint`'s order for that reason."""
    minter = _online_minter()
    reason = minter.why_not("1", 11796321, "N", "<DEL:1500>", build="GRCh37")
    assert "GRCh37" not in reason and "--offline" not in reason


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
