"""Enricher tests — network-free.

The cache side uses a tiny synthetic `ensembl_variations` parquet (the injectable shape the compiler
resolver reads); the live-Ensembl side uses an `httpx.MockTransport`, so nothing here opens a socket.
Coverage: offline enrich → resolution.csv → the compiler consumes it and reproduces the DuckDB
digest; `--offline` never calls the network; the V2→V1 fallback on 503; tenacity retrying a transient
error; strict failing on an unresolved variant; one-to-many expansion written as N rows.
"""

from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_format.resolution import ResolutionRow

from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.ensembl import EnsemblResolver

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_STUDIES = "rsid,pmid\nrs1801133,9545397\n"


def _spec(d: Path, variants: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(variants, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return d


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs1801133", "rs429358", "rs999", "rs999"],
            "chrom": ["1", "19", "5", "6"],
            "start": [11856377, 44908683, 500, 600],
            "ref": ["G", "T", "A", "C"],
            "alt": ["A", "C", "T", "G"],
        }
    ).write_parquet(data / "chr.parquet")
    return tmp_path / "cache"


def _rows_by_key(spec_dir: Path) -> dict[str, list[ResolutionRow]]:
    rows: dict[str, list[ResolutionRow]] = {}
    for line in (spec_dir / "resolution.csv").read_text().splitlines()[1:]:
        cells = line.split(",")
        r = ResolutionRow(
            variant_key=cells[0], rsid=cells[1] or None, chrom=cells[2] or None,
            start=int(cells[3]) if cells[3] else None, ref=cells[4] or None, alts=cells[5] or None,
            genome_build=cells[6], locus_index=int(cells[7]), source=cells[8] or None,
            status=cells[9] or None,
        )
        rows.setdefault(r.variant_key, []).append(r)
    return rows


# ── offline enrich → compiler consumes it → digest parity with the DuckDB path ────────────────


def test_offline_enrich_then_compile_matches_duckdb_digest(cache: Path, tmp_path: Path) -> None:
    variants = (
        "rsid,chrom,start,ref,genotype,state,conclusion,gene\n"
        "rs1801133,,,,A/G,risk,c1,MTHFR\n"
        ",19,44908683,T,C/T,risk,c2,APOE\n"
        "rs999,,,,A/T,risk,c3,X\n"
    )
    # Direct DuckDB compile (path 2) for the reference digest.
    spec2 = _spec(tmp_path / "spec2", variants)
    d2 = compile_module(spec2, tmp_path / "o2", ensembl_cache=cache).manifest.artifact.digest

    # Enrich offline against the same synthetic cache → resolution.csv, then compile path 1 (no cache).
    spec1 = _spec(tmp_path / "spec1", variants)
    result = enrich(spec1, offline=True, ensembl_cache=cache)
    assert result.fully_resolved
    assert (spec1 / "resolution.csv").is_file()
    r1 = compile_module(spec1, tmp_path / "o1", ensembl_cache=None)
    assert r1.success, r1.errors
    assert r1.manifest.artifact.digest == d2
    # every variant needed resolution, so the cache filled all of them
    assert r1.manifest.compilation.resolution_sources == ["cache"]


def test_expansion_written_as_multiple_rows(cache: Path, tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs999,A/T,risk,c\n")
    enrich(spec, offline=True, ensembl_cache=cache)
    rows = _rows_by_key(spec)["rs999"]
    assert [r.locus_index for r in rows] == [0, 1]
    assert {(r.chrom, r.start) for r in rows} == {("5", 500), ("6", 600)}
    assert all(r.source == "cache" and r.rsid == "rs999" for r in rows)


# ── offline guarantees zero egress ────────────────────────────────────────────────────────────


def test_offline_never_calls_network(cache: Path, tmp_path: Path) -> None:
    def _boom(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must never run
        raise AssertionError(f"offline enrich hit the network: {request.url}")

    resolver = EnsemblResolver()
    resolver._client = httpx.Client(transport=httpx.MockTransport(_boom))
    # rs_unknown is absent from the cache; offline must NOT reach for the injected resolver.
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs55555555,A/G,risk,c\n")
    result = enrich(spec, offline=True, ensembl_cache=cache, resolver=resolver)
    assert result.unresolved == ["rs55555555"]  # recorded, not fetched


# ── live Ensembl: V2 GraphQL 503 → V1 REST fallback; tenacity retries a transient error ────────


def _rest_variation_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "name": "rs1801133",
            "mappings": [
                {"seq_region_name": "1", "start": 11856377, "allele_string": "G/A", "assembly_name": "GRCh38"},
                {"seq_region_name": "1", "start": 99, "allele_string": "G/A", "assembly_name": "GRCh37"},  # filtered
            ],
        },
    )


def test_v2_graphql_503_falls_back_to_v1_rest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "graphql" in str(request.url):
            return httpx.Response(503, text="beta down")
        return _rest_variation_response()

    resolver = EnsemblResolver()
    resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
    loci, source = resolver.resolve_rsid("rs1801133")
    assert source == "ensembl-rest"
    assert loci == [{"chrom": "1", "start": 11856377, "ref": "G", "alts": "A"}]  # GRCh38 only


def test_tenacity_retries_transient_then_succeeds() -> None:
    calls = {"graphql": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "graphql" in str(request.url):
            calls["graphql"] += 1
            if calls["graphql"] == 1:
                raise httpx.ConnectError("transient", request=request)
            # second attempt: valid GraphQL variant node
            return httpx.Response(200, json={"data": {"variant": {
                "name": "rs1801133",
                "alleles": [{"allele_type": {"value": "reference"}, "reference_sequence": "G"},
                            {"allele_type": {"value": "alt"}, "reference_sequence": "A"}],
                "slice": {"location": {"region_name": "1", "start": 11856377}},
            }}})
        return _rest_variation_response()

    resolver = EnsemblResolver()
    resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
    loci, source = resolver.resolve_rsid("rs1801133")
    assert calls["graphql"] == 2  # retried the transient error
    assert source == "ensembl-graphql"
    assert loci[0]["chrom"] == "1" and loci[0]["ref"] == "G"


# ── strict mode ───────────────────────────────────────────────────────────────────────────────


def test_strict_enrich_fails_on_unresolved(cache: Path, tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs77777777,A/G,risk,c\n")
    with pytest.raises(EnrichmentError, match="unresolved"):
        enrich(spec, mode="strict", offline=True, ensembl_cache=cache)
