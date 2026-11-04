"""The ClinVar-GKM lane: an offline witness for where an indel sits (RM305).

The fixture is `assets/clinvar_gkm_slice/`: 22 whole rows of the real `allele.parquet` and the 22 real
variations that define them (projected to the three columns the builder reads), plus the source's own
`manifest.json` and `index.json` as served on 2026-11-04. Its README says how each row was chosen.

The download path is driven through a real HTTP server on localhost, not a mocked client: the failure
this lane guards against is bytes that are not the file the manifest states (a partial body, or the set
overwritten in place), and a mock would hand back whatever the test said.
"""

import hashlib
import http.server
import json
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.caches import LANES_BY_NAME, RebuildRequest
from just_dna_enricher.cli import app
from just_dna_enricher.clinvar_gkm import (
    ALLELE_FILE,
    CLINVAR_GKM_SOURCE,
    VARIATION_FILE,
    ClinVarGkmClient,
    ClinVarGkmError,
    ClinVarGkmMismatch,
    ClinVarGkmUnavailable,
    ClinVarGkmWitness,
    GkmManifest,
    LaneCurrency,
    clinvar_gkm_release_label,
    lane_currency,
    parse_manifest,
)
from just_dna_enricher.clinvar_gkm_build import (
    build_snapshot,
    download_and_build,
    download_input,
)
from just_dna_enricher.currency import (
    PROBE_SOURCES,
    ReleaseProbeError,
    ReleaseUnavailable,
    default_probes,
)
from just_dna_enricher.licensing import CLINVAR_GKM_TERMS, TERMS_BY_SOURCE
from just_dna_enricher.locations import resolve_clinvar_gkm_reference
from just_dna_format.snapshot import SNAPSHOT_LICENSE_FILENAME, read_release
from typer.testing import CliRunner

SLICE = Path(__file__).resolve().parents[2] / "assets" / "clinvar_gkm_slice"

#: The two insertions RM270 minted, as LANES_0_8.md §3.5 records them (domain constants, not counts).
KNOWN = {
    "rs72613567": ("ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7", "4:87310240:T:TA", "clinvar:1247925"),
    "rs77944059": ("ga4gh:VA.ks2GTWYOW0aKfGbJ2aeQUOZxOT_xC2ts", "2:166204470:GAAAC:G", "clinvar:167657"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slice_manifest_text(allele: Path = SLICE / ALLELE_FILE, variation: Path = SLICE / VARIATION_FILE) -> str:
    """The real manifest, with the two input entries rewritten to the slice's own size and digest."""
    raw = json.loads((SLICE / "manifest.json").read_text(encoding="utf-8"))
    for entry in raw["files"]:
        path = {ALLELE_FILE: allele, VARIATION_FILE: variation}.get(entry["name"])
        if path is not None:
            entry["size"] = path.stat().st_size
            entry["sha256"] = _sha(path)
    return json.dumps(raw)


def _slice_manifest() -> GkmManifest:
    return parse_manifest(_slice_manifest_text())


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("clinvar_gkm")
    build_snapshot(SLICE / ALLELE_FILE, SLICE / VARIATION_FILE, out, manifest=_slice_manifest())
    return out


# ── a real server on localhost ──────────────────────────────────────────────────────────────────

Route = Callable[[http.server.BaseHTTPRequestHandler], tuple[int, dict[str, str], bytes]]


@contextmanager
def serve(routes: dict[str, Route]) -> Iterator[str]:
    """Serve `routes` (path → handler) on localhost; yield the base URL."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - the stdlib's name
            route = routes.get(self.path)
            if route is None:
                self.send_error(404)
                return
            status, headers, body = route(self)
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def _static(body: bytes, status: int = 200, headers: dict[str, str] | None = None) -> Route:
    return lambda _handler: (status, headers or {}, body)


# ── the slice ───────────────────────────────────────────────────────────────────────────────────


def test_the_slice_keeps_net_indels_and_accounts_for_every_allele_it_read(built: Path) -> None:
    witness = ClinVarGkmWitness.load(built)
    frame = witness.frame
    release = read_release(built)
    assert release is not None
    counts = release.slice_counts  # type: ignore[attr-defined]
    source = pl.read_parquet(SLICE / ALLELE_FILE)
    # Every allele read lands in exactly one class.
    assert counts["alleles"] == source.height
    dropped = counts["no_spdi"] + counts["off_grch38"] + counts["same_length"] + counts["no_vcf_spelling"]
    assert dropped + counts["indels"] == counts["alleles"]
    # A kept row is an indel in its own VCF spelling, independently of the SPDI the filter read.
    assert (frame["ref"].str.len_chars() != frame["alt"].str.len_chars()).all()
    assert frame["vrs_id"].n_unique() == counts["indels"]
    # The classes the README names as dropped are dropped, read off the source's own HGVS-style names:
    # a substitution, a reference-agreeing allele, a GRCh37 name (no SPDI) and the T2T accession.
    names = dict(zip(source["id"], source["name"], strict=True))
    kept = set(frame["vrs_id"])
    dropped_by_name = {
        vrs_id
        for vrs_id, name in names.items()
        if ">" in name or name.endswith("=") or name.startswith(("NC_000019.9", "NC_060946"))
    }
    assert dropped_by_name and not (dropped_by_name & kept)
    # And the indel spellings are kept: an insertion, a duplication, a deletion, a repeat-count change.
    indel_by_name = {
        vrs_id
        for vrs_id, name in names.items()
        if name.endswith(("dup", "del", "]")) or "ins" in name and "delins" not in name
    }
    assert indel_by_name and indel_by_name <= kept
    assert set(frame["chrom"]) >= {"MT", "X", "Y"}, "the contig tokens a lookup normalizes to"


def test_rs72613567_and_rs77944059_resolve_to_their_known_ids(built: Path) -> None:
    witness = ClinVarGkmWitness.load(built)
    for rsid, (vrs_id, vcf_key, variation) in KNOWN.items():
        rows = witness.lookup(rsid)
        assert [(r.vrs_id, r.vcf_key, r.clinvar_variation_id) for r in rows] == [(vrs_id, vcf_key, variation)]
        # The two primary keys find the same row as the secondary one.
        assert witness.lookup(vrs_id) == rows
        assert witness.lookup(vcf_key) == rows
        assert witness.lookup("chr" + vcf_key) == rows, "a `chr` prefix is a spelling, not a contig"


def test_one_rsid_naming_two_alleles_returns_both_and_picks_neither(built: Path) -> None:
    witness = ClinVarGkmWitness.load(built)
    rows = witness.by_rsid("rs1003713657")
    assert len({r.vrs_id for r in rows}) == 2
    two_rsids = (
        witness.frame.group_by("vrs_id").agg(pl.col("rsid").n_unique().alias("n")).filter(pl.col("n") > 1)
    )
    assert two_rsids.height == 1, "the fixture's allele carrying two rsIDs is two rows, one per rsID"
    assert witness.by_vrs_id(two_rsids["vrs_id"][0]) and len(witness.by_vrs_id(two_rsids["vrs_id"][0])) == 2


def test_not_witnessed_is_an_empty_answer_and_a_malformed_key_is_refused(built: Path) -> None:
    witness = ClinVarGkmWitness.load(built)
    assert witness.lookup("rs8176719") == [], "absent from ClinVar-GKM entirely (LANES §3.5)"
    for bad in ("4:87310240:T", "4:87310240:T:TA,TAA", "BRCA1"):
        with pytest.raises(ValueError):
            witness.lookup(bad)


def test_a_vrs_id_comparison_is_only_offered_at_the_same_minor(built: Path) -> None:
    witness = ClinVarGkmWitness.load(built)
    assert witness.vrs_version == "2.1.1"
    assert witness.ids_comparable("2.0") is False
    assert witness.ids_comparable("2.1") is True
    assert witness.ids_comparable(None) is None


def test_release_json_pins_the_release_and_both_digests(built: Path) -> None:
    release = read_release(built)
    assert release is not None
    manifest = _slice_manifest()
    assert release.dataset == clinvar_gkm_release_label(manifest.source_release)
    assert release.source_release == manifest.source_release  # type: ignore[attr-defined]
    assert release.source_sha256 == {
        name: f"sha256:{manifest.file(name).sha256}"
        for name in manifest.files
        if name in (ALLELE_FILE, VARIATION_FILE)
    }
    assert release.vrs_version == "2.1.1"  # type: ignore[attr-defined]
    assert "changelog" in release.vrs_version_basis  # type: ignore[attr-defined]
    licence = (built / SNAPSHOT_LICENSE_FILENAME).read_text(encoding="utf-8")
    assert release.license_sha256 == "sha256:" + hashlib.sha256(licence.encode("utf-8")).hexdigest()
    assert manifest.attribution and manifest.attribution in licence
    assert manifest.disclaimer and manifest.disclaimer in licence


def test_a_rebuild_of_the_same_bytes_writes_the_same_slice(built: Path, tmp_path: Path) -> None:
    again = tmp_path / "again"
    build_snapshot(SLICE / ALLELE_FILE, SLICE / VARIATION_FILE, again, manifest=_slice_manifest())
    first = pl.read_parquet(built / "data" / "clinvar_gkm-indels.parquet")
    second = pl.read_parquet(again / "data" / "clinvar_gkm-indels.parquet")
    assert first.equals(second)


def test_a_local_file_the_manifest_does_not_describe_is_refused(tmp_path: Path) -> None:
    """The real manifest describes the full 1.1 GB file, not the slice: a stale or foreign copy."""
    real = parse_manifest((SLICE / "manifest.json").read_text(encoding="utf-8"))
    with pytest.raises(ClinVarGkmMismatch, match="manifest.json states"):
        build_snapshot(SLICE / ALLELE_FILE, SLICE / VARIATION_FILE, tmp_path / "out", manifest=real)
    assert not (tmp_path / "out" / "release.json").exists()


# ── the download: whole files, verified ─────────────────────────────────────────────────────────


def test_a_partial_answer_to_a_whole_download_is_refused(tmp_path: Path) -> None:
    """R2 once answered a range request with 200 and the whole file (LANES §4). The mirror case is a
    206 and a slice where the whole file was asked for; the status alone does not fail the transport,
    so the size against the manifest must."""
    body = (SLICE / ALLELE_FILE).read_bytes()
    partial = _static(body[:4096], 206, {"Content-Range": f"bytes 0-4095/{len(body)}"})
    with serve({"/allele.parquet": partial}) as base, pytest.raises(ClinVarGkmMismatch, match="partial"):
        download_input(ALLELE_FILE, _slice_manifest(), tmp_path / ALLELE_FILE, url=f"{base}/allele.parquet")


def test_a_file_overwritten_after_the_manifest_was_read_is_refused(tmp_path: Path) -> None:
    body = bytearray((SLICE / ALLELE_FILE).read_bytes())
    body[100] ^= 0xFF  # same size, other bytes: an in-place overwrite
    with (
        serve({"/allele.parquet": _static(bytes(body))}) as base,
        pytest.raises(ClinVarGkmMismatch, match="overwritten"),
    ):
        download_input(ALLELE_FILE, _slice_manifest(), tmp_path / ALLELE_FILE, url=f"{base}/allele.parquet")


def test_the_whole_download_builds_and_a_release_landing_mid_build_is_named(tmp_path: Path) -> None:
    manifest_text = _slice_manifest_text().encode()
    index = (SLICE / "index.json").read_bytes()
    routes: dict[str, Route] = {
        "/parquet/manifest.json": _static(manifest_text),
        "/index.json": _static(index),
        "/parquet/allele.parquet": _static((SLICE / ALLELE_FILE).read_bytes()),
        "/parquet/variation.parquet": _static((SLICE / VARIATION_FILE).read_bytes()),
    }
    with serve(routes) as base:
        client = ClinVarGkmClient(
            manifest_url=f"{base}/parquet/manifest.json", index_url=f"{base}/index.json"
        )
        result = download_and_build(tmp_path / "ok", client=client)
        assert result.row_count == ClinVarGkmWitness.load(tmp_path / "ok").frame.height
        assert result.latest_release == json.loads(index)["latest_release"]
        assert result.source_lags is True, "on 2026-11-04 the set held 2026-10-24 and the line 2026-10-31"
        assert not (tmp_path / "ok" / "_downloads").exists(), "the 5 GB of inputs are not kept by default"

        # Now the source publishes mid-build: the manifest moves, and the variation file with it.
        calls = {"n": 0}
        moved = json.loads(manifest_text)
        moved["source_release"] = "2026-10-31"

        def manifest_route(_handler: http.server.BaseHTTPRequestHandler) -> tuple[int, dict[str, str], bytes]:
            calls["n"] += 1
            return 200, {}, manifest_text if calls["n"] == 1 else json.dumps(moved).encode()

        routes["/parquet/manifest.json"] = manifest_route
        routes["/parquet/variation.parquet"] = _static(b"PAR1" + b"\0" * 64 + b"PAR1")
        with pytest.raises(ClinVarGkmMismatch, match="published 2026-10-31 while this build was downloading"):
            download_and_build(tmp_path / "moved", client=client)

        # The same release overwritten in place says so, rather than naming one release twice.
        calls["n"] = 0
        overwritten = json.loads(manifest_text)
        for entry in overwritten["files"]:
            if entry["name"] == VARIATION_FILE:
                entry["sha256"] = "f" * 64
        moved.clear()
        moved.update(overwritten)
        with pytest.raises(ClinVarGkmMismatch, match="overwrote its 2026-10-24 Parquet set in place"):
            download_and_build(tmp_path / "inplace", client=client)

        # A pinned manifest is the one built: the live one moving afterwards does not change the build.
        routes["/parquet/variation.parquet"] = _static((SLICE / VARIATION_FILE).read_bytes())
        routes["/parquet/manifest.json"] = _static(json.dumps(moved).encode())
        pinned = download_and_build(
            tmp_path / "pinned", client=client, manifest=parse_manifest(manifest_text.decode())
        )
        assert pinned.source_release == "2026-10-24"


def test_an_unreachable_source_is_its_own_type_never_an_httpx_one(tmp_path: Path) -> None:
    with serve({}) as base:
        dead = base  # every path answers 404
    client = ClinVarGkmClient(manifest_url=f"{dead}/parquet/manifest.json", index_url=f"{dead}/index.json")
    with pytest.raises(ClinVarGkmUnavailable):
        client.parquet_manifest()


# ── currency: three questions, kept apart ───────────────────────────────────────────────────────


def _currency_against(built: Path, manifest: dict, index: dict) -> LaneCurrency:
    routes = {
        "/m.json": _static(json.dumps(manifest).encode()),
        "/i.json": _static(json.dumps(index).encode()),
    }
    with serve(routes) as base:
        return lane_currency(
            built, client=ClinVarGkmClient(manifest_url=f"{base}/m.json", index_url=f"{base}/i.json")
        )


def test_currency_reports_behind_drifted_and_the_sources_own_lag_apart(built: Path) -> None:
    pinned = json.loads(_slice_manifest_text())
    index = json.loads((SLICE / "index.json").read_text(encoding="utf-8"))

    same = _currency_against(built, pinned, {**index, "latest_release": pinned["source_release"]})
    assert (same.behind, same.drifted, same.source_lags) == (False, False, False)
    assert same.sentences() == []

    lagging = _currency_against(built, pinned, index)
    assert (lagging.behind, lagging.drifted, lagging.source_lags) == (False, False, True)
    assert "no Parquet exists" in " ".join(lagging.sentences())

    newer = {**pinned, "source_release": "2026-10-31"}
    ahead = _currency_against(built, newer, index)
    assert (ahead.behind, ahead.source_lags) == (True, False)
    assert ahead.drifted is None, "a different release is not drift; drift is the same label, other bytes"

    overwritten = json.loads(json.dumps(pinned))
    for entry in overwritten["files"]:
        if entry["name"] == ALLELE_FILE:
            entry["sha256"] = "0" * 64
    drifted = _currency_against(built, overwritten, index)
    assert (drifted.behind, drifted.drifted) == (False, True)
    assert ALLELE_FILE in " ".join(drifted.sentences())

    # The variation file carries the rsID and ClinVar links, so its overwrite is drift too.
    relinked = json.loads(json.dumps(pinned))
    for entry in relinked["files"]:
        if entry["name"] == VARIATION_FILE:
            entry["sha256"] = "f" * 64
    relinked_now = _currency_against(built, relinked, index)
    assert relinked_now.drifted is True
    assert VARIATION_FILE in " ".join(relinked_now.sentences())


def test_an_index_outage_withholds_the_lag_and_nothing_else(built: Path) -> None:
    """`@one-registrys-outage-may-not-speak-for-another`: the manifest answers behind and drifted."""
    pinned = _slice_manifest_text().encode()
    with serve({"/m.json": _static(pinned)}) as base:
        client = ClinVarGkmClient(manifest_url=f"{base}/m.json", index_url=f"{base}/gone.json")
        currency = lane_currency(built, client=client)
    assert (currency.behind, currency.drifted, currency.source_lags) == (False, False, None)


def test_currency_is_unchecked_offline_and_when_unreachable(built: Path) -> None:
    offline = lane_currency(built, offline=True)
    assert (offline.behind, offline.drifted, offline.source_lags) == (None, None, None)
    assert offline.unchecked == "offline"
    with serve({}) as base:
        unreachable = lane_currency(
            built, client=ClinVarGkmClient(manifest_url=f"{base}/m.json", index_url=f"{base}/i.json")
        )
    assert (
        unreachable.behind is None
        and unreachable.unchecked
        and unreachable.unchecked.startswith("unreachable")
    )


def test_the_dataset_probe_reads_the_parquet_set_and_translates_both_failures() -> None:
    assert CLINVAR_GKM_SOURCE in PROBE_SOURCES
    with serve({"/m.json": _static(_slice_manifest_text().encode()), "/bad.json": _static(b"{}")}) as base:
        good = ClinVarGkmClient(manifest_url=f"{base}/m.json")
        label = default_probes(clinvar_gkm=good)[CLINVAR_GKM_SOURCE]()
        assert label == clinvar_gkm_release_label(_slice_manifest().source_release)
        unreadable = ClinVarGkmClient(manifest_url=f"{base}/bad.json")
        with pytest.raises(ReleaseProbeError) as caught:
            default_probes(clinvar_gkm=unreadable)[CLINVAR_GKM_SOURCE]()
        assert not isinstance(caught.value, ReleaseUnavailable), "answered, unreadable: not unreachable"
        missing = ClinVarGkmClient(manifest_url=f"{base}/gone.json")
        with pytest.raises(ReleaseUnavailable):
            default_probes(clinvar_gkm=missing)[CLINVAR_GKM_SOURCE]()


# ── terms, lane, CLI ────────────────────────────────────────────────────────────────────────────


def test_the_terms_are_the_manifests_own_words_under_their_own_source_name() -> None:
    manifest = _slice_manifest()
    assert TERMS_BY_SOURCE[CLINVAR_GKM_SOURCE] is CLINVAR_GKM_TERMS
    assert CLINVAR_GKM_TERMS.license == manifest.license_id == "CC0-1.0"
    assert CLINVAR_GKM_TERMS.attribution == manifest.attribution
    assert manifest.license_scope in (CLINVAR_GKM_TERMS.notice or "")
    assert manifest.disclaimer in (CLINVAR_GKM_TERMS.notice or "")
    assert (
        CLINVAR_GKM_TERMS.share_alike,
        CLINVAR_GKM_TERMS.commercial_use,
        CLINVAR_GKM_TERMS.redistribution,
    ) == (
        False,
        True,
        True,
    )


def test_the_rebuild_adapter_refuses_one_source_file_rather_than_half_using_it(tmp_path: Path) -> None:
    lane = LANES_BY_NAME["clinvar_gkm"]
    assert lane.rebuild is not None
    outcome = lane.rebuild(RebuildRequest(out_dir=tmp_path, source=SLICE / ALLELE_FILE))
    assert outcome.built is None and "three input files" in outcome.detail


def test_the_cli_builds_from_local_files_and_looks_up_a_known_insertion(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(_slice_manifest_text(), encoding="utf-8")
    out = tmp_path / "snap"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "clinvar-gkm",
            "build",
            "--out",
            str(out),
            "--allele",
            str(SLICE / ALLELE_FILE),
            "--variation",
            str(SLICE / VARIATION_FILE),
            "--manifest",
            str(manifest),
        ],
    )
    assert result.exit_code == 0, result.output
    looked = runner.invoke(app, ["clinvar-gkm", "lookup", "rs72613567", "--snapshot", str(out)])
    assert looked.exit_code == 0, looked.output
    assert KNOWN["rs72613567"][0] in looked.output
    half = runner.invoke(
        app, ["clinvar-gkm", "build", "--out", str(tmp_path / "x"), "--allele", str(SLICE / ALLELE_FILE)]
    )
    assert half.exit_code == 1


def test_a_manifest_this_tier_cannot_read_is_a_clinvar_gkm_error_never_a_crash() -> None:
    with pytest.raises(ClinVarGkmError, match="source_release"):
        parse_manifest(json.dumps({"files": []}))
    release = {"source_release": "2026-10-24"}
    for files in (
        ["allele.parquet"],
        {"allele.parquet": 1},
        [{"name": "allele.parquet", "size": True, "sha256": "ab"}],
    ):
        with pytest.raises(ClinVarGkmError):
            parse_manifest(json.dumps({**release, "files": files}))


# ── the provisioned snapshot, when this machine holds one ───────────────────────────────────────


def test_the_provisioned_snapshot_places_the_two_known_insertions() -> None:
    found = resolve_clinvar_gkm_reference()
    if found is None:
        pytest.skip("no ClinVar-GKM snapshot provisioned on this machine")
    witness = ClinVarGkmWitness.load(found)
    for rsid, (vrs_id, vcf_key, variation) in KNOWN.items():
        assert [(r.vrs_id, r.vcf_key, r.clinvar_variation_id) for r in witness.by_rsid(rsid)] == [
            (vrs_id, vcf_key, variation)
        ]
    assert witness.lookup("rs8176719") == []


@pytest.mark.skipif(
    not os.getenv("JUST_DNA_NETWORK_TESTS"), reason="reads the live source — set JUST_DNA_NETWORK_TESTS=1"
)
def test_the_live_manifest_still_reads_and_names_a_release() -> None:
    client = ClinVarGkmClient()
    manifest = client.parquet_manifest()
    assert {ALLELE_FILE, VARIATION_FILE} <= set(manifest.files)
    assert client.current_release() == clinvar_gkm_release_label(manifest.source_release)
    assert client.latest_release() is not None
