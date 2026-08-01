"""Enricher tests — network-free.

The cache side uses a tiny synthetic `ensembl_variations` parquet (the injectable shape the compiler
resolver reads); the live-Ensembl side uses an `httpx.MockTransport`, so nothing here opens a socket.
Coverage: offline enrich → resolution.csv → the compiler consumes it and reproduces the DuckDB
digest; `--offline` never calls the network; the V2→V1 fallback on 503; tenacity retrying a transient
error; strict failing on an unresolved variant; one-to-many expansion written as N rows.
"""

import csv
from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import derive_vrs_allele_id

from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.gnomad import GnomadClient
from just_dna_enricher.net import PacingGate

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
    """Parse the written resolution.csv back into models, by column NAME.

    Deliberately not by cell index: positional parsing silently mis-assigns every column to the right
    of an additive change (0.5's `vrs_id`/`vrs_spec`/`caid` did exactly that here, landing `vrs_spec`
    in `status`), which is a test breaking on a legal additive schema growth rather than on a defect.
    """
    rows: dict[str, list[ResolutionRow]] = {}
    with (spec_dir / "resolution.csv").open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            r = ResolutionRow(**{k: (v or None) for k, v in record.items() if k != "genome_build"},
                              genome_build=record["genome_build"])
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


# ── the gnomAD link sits LAST in the chain ────────────────────────────────────────────────────


class _CountingTransport(httpx.BaseTransport):
    """Counts requests and answers every gnomAD query with a fixed payload."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(200, json=self.payload)


def _gnomad_client(transport: httpx.BaseTransport) -> GnomadClient:
    client = GnomadClient()
    client._client = httpx.Client(transport=transport)
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def test_gnomad_link_never_overrides_an_earlier_link(cache: Path, tmp_path: Path) -> None:
    """A variant the Ensembl cache already knows keeps `source="cache"` and the cache's `alts`.

    This is the ordering guarantee the whole link placement rests on. `alts` is a fact column, so
    whichever link wins a variant decides its compiled bytes; gnomAD reports only the alleles observed
    *in gnomAD*, so letting it win would narrow an already-compiled module's alts and move its
    `artifact.digest`. Going last makes the link strictly additive.
    """
    # gnomAD would answer with a DIFFERENT alt for the same rsid, so a wrong ordering is visible.
    transport = _CountingTransport({"data": {"v0": {"variant_id": "1-11856377-G-C"}}})
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    result = enrich(spec, ensembl_cache=cache, clinvar_cache=tmp_path / "no_clinvar",
                    gnomad_client=_gnomad_client(transport))

    row = next(r for r in result.rows if r.rsid == "rs1801133")
    assert row.source == "cache"
    assert row.alts == "A"          # the cache's allele, not gnomAD's "C"
    assert transport.calls == 0     # nothing was left for gnomAD to resolve, so it was never called


def test_gnomad_link_fills_only_what_nothing_else_could(cache: Path, tmp_path: Path) -> None:
    transport = _CountingTransport({"data": {"v0": {"variant_id": "7-100-A-G"}}})
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs88888888,A/G,risk,c\n")
    # `resolver=` is a live-Ensembl stub that finds nothing, so the chain reaches gnomAD.
    stub = EnsemblResolver()
    stub._client = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(404)))
    result = enrich(spec, ensembl_cache=cache, clinvar_cache=tmp_path / "no_clinvar",
                    resolver=stub, gnomad_client=_gnomad_client(transport))

    row = next(r for r in result.rows if r.rsid == "rs88888888")
    assert row.source == "gnomad"
    assert (row.chrom, row.start, row.ref, row.alts) == ("7", 100, "A", "G")
    assert transport.calls == 1


def test_offline_enrich_makes_no_gnomad_call(cache: Path, tmp_path: Path) -> None:
    class _Exploding(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"offline enrich reached the network: {request.url}")

    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs77777777,A/G,risk,c\n")
    result = enrich(spec, offline=True, ensembl_cache=cache,
                    clinvar_cache=tmp_path / "no_clinvar",
                    gnomad_client=_gnomad_client(_Exploding()))
    assert result.unresolved == ["rs77777777"]


def test_enrich_mints_vrs_ids_onto_resolved_rows(cache: Path, tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    enrich(spec, offline=True, ensembl_cache=cache, clinvar_cache=tmp_path / "no_clinvar")
    row = _rows_by_key(spec)["rs1801133"][0]
    # The cache places rs1801133 at 1:11856377 G>A — a substitution, so it mints offline.
    assert row.vrs_id == derive_vrs_allele_id("1", 11856377, "G", "A")
    assert row.vrs_spec == "2.0"


def test_unqueryable_clinvar_cache_degrades_instead_of_crashing(
    cache: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A located-but-foreign ClinVar parquet must not sink an enrichment the other links can finish.

    This is a real failure mode, not a hypothetical: a cache directory left behind by a different
    tool (or an older builder) holds parquet with different columns, the DuckDB query raises, and
    before this the whole `enrich()` call died — even though the Ensembl cache had the answer.
    """
    clinvar_dir = tmp_path / "foreign_clinvar" / "data"
    clinvar_dir.mkdir(parents=True)
    # Right shape (a directory of parquet), wrong schema — exactly the real-world case.
    pl.DataFrame({"rs": ["rs1801133"], "unrelated": [1]}).write_parquet(clinvar_dir / "x.parquet")

    # One rsid the Ensembl cache knows and one it does not — so the ClinVar link is genuinely
    # consulted for the second, and its failure has something to spoil.
    spec = _spec(
        tmp_path / "spec",
        "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\nrs77777777,A/G,risk,c\n",
    )
    with caplog.at_level("WARNING"):
        result = enrich(spec, offline=True, ensembl_cache=cache,
                        clinvar_cache=tmp_path / "foreign_clinvar")

    resolved = next(r for r in result.rows if r.rsid == "rs1801133")
    assert resolved.chrom == "1" and resolved.source == "cache"   # the Ensembl link still answered
    assert result.unresolved == ["rs77777777"]                    # the ClinVar miss is just a miss
    assert any("not queryable" in message for message in caplog.messages)
