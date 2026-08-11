"""Enricher tests — network-free.

The cache side uses a tiny synthetic `ensembl_variations` parquet (the injectable shape the compiler
resolver reads); the live-Ensembl side uses an `httpx.MockTransport`, so nothing here opens a socket.
Coverage: offline enrich → resolution.csv → the compiler consumes it and reproduces the DuckDB
digest; `--offline` never calls the network; the V2→V1 fallback on 503; tenacity retrying a transient
error; strict failing on an unresolved variant; one-to-many expansion written as N rows.
"""

import csv
import shutil
from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_compiler.compiler import _load_csv_rows, compile_module
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.gnomad import GnomadClient
from just_dna_enricher.net import PacingGate
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow, taints_commercial_use
from just_dna_format.vrs import derive_vrs_allele_id

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
            # Both rs999 loci are `A>T` so both can host the authored `A/T` genotype. Deliberate:
            # forward resolution is allele-aware since 0.5, so a locus the genotype rules out is left
            # out of the table — a fixture with one incompatible locus would quietly stop exercising
            # expansion at all while still passing an `is it there` assertion.
            "id": ["rs1801133", "rs429358", "rs999", "rs999"],
            "chrom": ["1", "19", "5", "6"],
            "start": [11856377, 44908683, 500, 600],
            "ref": ["G", "T", "A", "A"],
            "alt": ["A", "C", "T", "T"],
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
    # Enrich offline against the synthetic cache → resolution.csv, then compile path 1 (no cache).
    spec1 = _spec(tmp_path / "spec1", variants)
    result = enrich(spec1, offline=True, ensembl_cache=cache)
    assert result.fully_resolved
    assert (spec1 / "resolution.csv").is_file()

    # Direct DuckDB compile (path 2) for the reference digest, handed the **same non-resolution
    # inputs** — including the `sources.csv` the enricher now records for the links it consulted
    # (RM33). Parity is a claim about resolution: a module that carries an extra fact table genuinely
    # has a different content identity, because `sources.parquet` is an artifact file. Copying it is
    # what isolates the claim instead of quietly weakening it to a weights-only comparison.
    spec2 = _spec(tmp_path / "spec2", variants)
    shutil.copy(spec1 / "sources.csv", spec2 / "sources.csv")
    d2 = compile_module(spec2, tmp_path / "o2", ensembl_cache=cache).manifest.artifact.digest
    r1 = compile_module(spec1, tmp_path / "o1", ensembl_cache=None)
    assert r1.success, r1.errors
    assert r1.manifest.artifact.digest == d2
    # every variant needed resolution, so the cache filled all of them
    assert r1.manifest.compilation.resolution_sources == ["cache"]


def test_each_link_records_the_authority_it_speaks_for(cache: Path, tmp_path: Path) -> None:
    """RM33: the row keeps the link that answered *and* names the licensed source behind it.

    `cache` is the Ensembl snapshot, so its authority is `ensembl` — the two columns are not synonyms
    and the point is that the row now carries both. `authored` has none, because the module's own bytes
    are not a licensed source.
    """
    variants = (
        "rsid,chrom,start,ref,genotype,state,conclusion,gene\n"
        "rs1801133,,,,A/G,risk,c1,MTHFR\n"
        ",19,44908683,T,C/T,risk,c2,APOE\n"
    )
    spec = _spec(tmp_path / "spec", variants)
    enrich(spec, offline=True, ensembl_cache=cache)
    by_key = _rows_by_key(spec)
    filled = by_key["rs1801133"][0]
    assert (filled.source, filled.authority) == ("cache", "ensembl")

    # The pass that consulted a source records its terms — at the `resolution` layer, the member of
    # VALID_SOURCE_LAYERS that nothing used to write.
    rows, errors, _ = _load_csv_rows(spec / "sources.csv", SourceRow, "sources.csv")
    assert not errors
    recorded = {(r.source, r.layer) for r in rows}
    assert ("ensembl", "resolution") in recorded
    ensembl = next(r for r in rows if r.source == "ensembl")
    assert ensembl.attribution and ensembl.commercial_use is True
    # A fact layer cannot taint a module: a coordinate is not expression.
    assert not taints_commercial_use(ensembl)


def test_a_hand_written_authority_is_never_overwritten(cache: Path, tmp_path: Path) -> None:
    """Same rule as an existing `vrs_id`: the enricher fills what is empty, never what is stated."""
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status\n"
        "rs1801133,rs1801133,1,11796321,G,A,GRCh38,0,manual,ensembl,resolved\n"
    )
    enrich(spec, offline=True, ensembl_cache=cache)
    row = _rows_by_key(spec)["rs1801133"][0]
    assert (row.source, row.authority) == ("manual", "ensembl")


#: The SHOX deletion at the heart of RM31, and every spelling in play is a spelling of *this* deletion.
#: The reference reads `C A G A G` from X:634689, so ClinVar publishes `634689 CAG>C`, Ensembl publishes
#: `634690 AGAG>AG`, and writing the same 2 bp AG deletion one base further right gives `634691 GAG>G`.
#: A drafted module carries ClinVar's frame in its genotype (`C/CAG`) and no coordinate at all.
_SHOX_RSID = "rs1569493663"


def _indel_cache(tmp_path: Path, name: str, start: int, ref: str, alt: str) -> Path:
    data = tmp_path / name / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {"id": [_SHOX_RSID], "chrom": ["X"], "start": [start], "ref": [ref], "alt": [alt]}
    ).write_parquet(data / "chr.parquet")
    return tmp_path / name


def test_one_indel_spelled_two_ways_now_resolves(tmp_path: Path) -> None:
    """RM31 end to end: the pair that used to come back `not_found` resolves, with no authored edit.

    Ensembl's spelling of the deletion against ClinVar's spelling of the genotype — the exact pair from
    `reference_examples/shox_par1/`, where this resolved to `not_found` and the message blamed a dbSNP
    merge that does not exist.
    """
    cache = _indel_cache(tmp_path, "ensembl_spelling", 634690, "AGAG", "AG")
    spec = _spec(tmp_path / "spec", f"rsid,genotype,state,conclusion\n{_SHOX_RSID},C/CAG,risk,c\n")
    result = enrich(spec, offline=True, ensembl_cache=cache)
    assert result.fully_resolved, result.unresolved
    row = _rows_by_key(spec)[_SHOX_RSID][0]
    assert (row.chrom, row.start, row.ref, row.alts) == ("X", 634690, "AGAG", "AG")
    assert row.status == "resolved"


def test_a_spelling_that_cannot_be_reconciled_is_kept_and_reported(tmp_path: Path, caplog) -> None:
    """Undecidable is not a contradiction: the locus is kept, and the message says what was not decided.

    The right-shifted spelling (`634691 GAG>G`) is the same deletion again, and reduces to the event `GA`
    where ClinVar's reduces to `AG` — same size, different content, which is exactly what a repeat-region
    disagreement looks like and exactly what string algebra cannot settle. The old message asserted "a
    different variant sharing the rsID", which was flatly wrong for the case that found the item, so
    nothing here may assert either reading.
    """
    cache = _indel_cache(tmp_path, "right_shifted", 634691, "GAG", "G")
    spec = _spec(tmp_path / "rot", f"rsid,genotype,state,conclusion\n{_SHOX_RSID},C/CAG,risk,c\n")
    with caplog.at_level("WARNING"):
        result = enrich(spec, offline=True, ensembl_cache=cache)
    assert result.fully_resolved                       # kept, not dropped
    assert _rows_by_key(spec)[_SHOX_RSID][0].start == 634691
    message = "\n".join(record.getMessage() for record in caplog.records)
    assert "could not be decided" in message and "KEPT" in message
    assert "different variant sharing the rsID" not in message


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


# ── S20: an unreachable Ensembl is unchecked, never absent ────────────────────────────────────


def test_a_transport_failure_returns_none_where_an_empty_answer_returns_a_list() -> None:
    """The whole of S20 in one assertion pair: the two states that used to be `([], None)`.

    A published rsID on a run where egress breaks must not be reported with the same value as one
    Ensembl genuinely has no locus for — that value is what made a real variant read as fabricated.
    """
    def dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("egress down", request=request)

    unreachable = EnsemblResolver()
    unreachable._client = httpx.Client(transport=httpx.MockTransport(dead))
    loci, source = unreachable.resolve_rsid("rs6567160")

    def empty(request: httpx.Request) -> httpx.Response:
        if "graphql" in str(request.url):
            return httpx.Response(200, json={"data": {"variant": None}})
        return httpx.Response(200, json={"name": "rs2000000000", "mappings": []})

    answered = EnsemblResolver()
    answered._client = httpx.Client(transport=httpx.MockTransport(empty))
    empty_loci, empty_source = answered.resolve_rsid("rs2000000000")

    assert loci is None and source is None           # could not ask
    assert empty_loci == [] and empty_source == "ensembl-rest"   # asked, nothing there
    assert loci is not empty_loci                    # and they are no longer the same value


def test_a_4xx_is_an_answer_and_a_5xx_is_a_failure() -> None:
    """Ensembl 400s on rsIDs it cannot resolve (`rs3216883`, merged per dbSNP), so a 4xx is a
    negative answer. Only the cases where nothing came back are unchecked."""
    def status(code: int) -> EnsemblResolver:
        resolver = EnsemblResolver()
        resolver._client = httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(code))
        )
        return resolver

    assert status(400).resolve_rsid("rs3216883") == ([], "ensembl-rest")
    assert status(404).resolve_rsid("rs2000000000") == ([], "ensembl-rest")
    assert status(503).resolve_rsid("rs1801133") == (None, None)


def test_an_unreachable_rsid_writes_no_not_found_row(cache: Path, tmp_path: Path) -> None:
    """The artifact half. `not_found` says a source was asked and does not have this rsID; on a
    failed request nobody established that, so the row is not written at all — the same treatment
    the non-GRCh38 branch already gave the same shape of non-answer."""
    def dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("egress down", request=request)

    resolver = EnsemblResolver()
    resolver._client = httpx.Client(transport=httpx.MockTransport(dead))
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs6567160,C/T,risk,c\n")
    # `clinvar_cache` and `download=False` are load-bearing, not decoration: without them this call
    # provisions the real 87 MB ClinVar snapshot into the developer's cache — which is `enrich()`
    # working as designed, and is not what a resolver unit test is asking about.
    result = enrich(
        spec, ensembl_cache=cache, clinvar_cache=tmp_path, resolver=resolver,
        use_gnomad=False, download=False,
    )

    assert result.unreachable_rsids == ["rs6567160"]      # named, not merely absent from a set
    assert result.unresolved == ["rs6567160"]             # still unresolved: strict still refuses
    assert [row for row in result.rows if row.status == "not_found"] == []
    assert not result.fully_resolved


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


def test_the_mint_result_survives_the_call_instead_of_being_logged_away(
    cache: Path, tmp_path: Path
) -> None:
    """RM40: `enrich()` computed the coverage counters and threw them away.

    They are the same two numbers `compile_module` later stamps into
    `manifest.compilation.vrs_alleles` / `vrs_alleles_identified`, so a consumer reading coverage
    **before** a compile — which is what a publish dry run is — had to re-implement the counting, and
    had to get two non-obvious rules right to agree with the manifest a publish would produce. And
    `unmintable_reasons`, the actionable half, survived only as a log line.

    `None` when the pass did not run, never a coverage of zero — the house tri-state.
    """
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    result = enrich(spec, offline=True, ensembl_cache=cache, clinvar_cache=tmp_path / "no_clinvar")
    assert result.vrs is not None
    # Per ALT slot, not per row — and the denominator is what makes a shortfall legible at all.
    assert result.vrs.alleles == 1 and result.vrs.identified == 1
    assert result.vrs.complete is True and result.vrs.coverage_warnings() == []
    # It is the object the compiler stamps, so the numbers a consumer reads here are the manifest's.
    assert result.vrs.minted_stdlib == 1

    off = _spec(tmp_path / "spec2", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    skipped = enrich(
        off, offline=True, ensembl_cache=cache, clinvar_cache=tmp_path / "no_clinvar",
        mint_vrs=False,
    )
    assert skipped.vrs is None


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


# ── multi-allelic snapshot rows: pipe-joined `alt` cells ─────────────────────────────────────────
@pytest.fixture
def multiallelic_cache(tmp_path: Path) -> Path:
    """A cache whose multi-allelic site is stored the way the real snapshot stores it.

    The shipped Ensembl snapshot records a multi-allelic locus as ONE row whose `alt` is
    **pipe-joined** (`rs4244285` is `10:94781859 G>A|C|T`), not one row per alt. Every other link in
    the chain emits commas, so this shape only ever appears via the cache — which is why the whole
    unit suite missed it.
    """
    data = tmp_path / "mcache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs4244285", "rs12248560"],
            "chrom": ["10", "10"],
            "start": [94781859, 94761900],
            "ref": ["G", "C"],
            "alt": ["A|C|T", "A|T"],
        }
    ).write_parquet(data / "chr.parquet")
    return tmp_path / "mcache"


def test_multiallelic_snapshot_row_resolves(multiallelic_cache: Path, tmp_path: Path) -> None:
    """Regression: a pipe-joined `alt` cell made every genotype look unhostable.

    `genotype_fits` splits alts on commas, so `A|C|T` collapsed to one opaque "allele", no authored
    genotype was ever a subset of `{ref} ∪ alts`, and the allele-aware filter dropped **every** locus
    — a perfectly ordinary `A/G` at `rs4244285` resolved to `not_found`. Both alleles here genuinely
    exist at the locus (`G` is ref, `A` is an alt), so the only way this fails is the separator bug.
    """
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs4244285,A/G,risk,c\n")
    result = enrich(spec, offline=True, ensembl_cache=multiallelic_cache,
                    clinvar_cache=tmp_path / "no_clinvar")
    assert result.unresolved == []
    row = result.rows[0]
    assert (row.chrom, row.start, row.ref) == ("10", 94781859, "G")
    # Normalized to the one canonical shape every other link emits, sorted for determinism (P7).
    assert row.alts == "A,C,T"


def test_multiallelic_reverse_backfill_matches_one_allele(
    multiallelic_cache: Path, tmp_path: Path
) -> None:
    """The mirror bug: reverse compared the authored alt to the whole joined cell with `!=`."""
    spec = _spec(
        tmp_path / "spec",
        "chrom,start,ref,alts,genotype,state,conclusion\n10,94781859,G,A,A/G,risk,c\n",
    )
    result = enrich(spec, offline=True, ensembl_cache=multiallelic_cache,
                    clinvar_cache=tmp_path / "no_clinvar")
    assert result.rows[0].rsid == "rs4244285"


# ── PGx tables participate in resolution (a PGx module carries no variants.csv) ──────────────────
def _pgx_spec(d: Path, *, pharm: str | None = None, haplotypes: str | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    if pharm is not None:
        (d / "pharm_variants.csv").write_text(pharm, encoding="utf-8")
    if haplotypes is not None:
        (d / "haplotypes.csv").write_text(haplotypes, encoding="utf-8")
    return d


def test_pharm_variants_resolve_without_a_variants_csv(
    multiallelic_cache: Path, tmp_path: Path
) -> None:
    """A PharmGKB module composes from pharm_variants.csv alone — it must still get coordinates."""
    spec = _pgx_spec(
        tmp_path / "spec",
        pharm=("rsid,gene,genotype,drug,conclusion\n"
               "rs4244285,CYP2C19,A/G,clopidogrel,reduced activation\n"),
    )
    result = enrich(spec, offline=True, ensembl_cache=multiallelic_cache,
                    clinvar_cache=tmp_path / "no_clinvar")
    assert result.unresolved == []
    assert [(r.rsid, r.chrom, r.start) for r in result.rows] == [("rs4244285", "10", 94781859)]


def test_haplotype_defining_variants_resolve(multiallelic_cache: Path, tmp_path: Path) -> None:
    """A star-allele module's defining variants are rsIDs too, and were equally invisible before."""
    spec = _pgx_spec(
        tmp_path / "spec",
        haplotypes=("haplotype_name,rsid,allele,gene\n"
                    "*2,rs4244285,A,CYP2C19\n*17,rs12248560,T,CYP2C19\n"),
    )
    result = enrich(spec, offline=True, ensembl_cache=multiallelic_cache,
                    clinvar_cache=tmp_path / "no_clinvar")
    assert result.unresolved == []
    assert {r.rsid for r in result.rows} == {"rs4244285", "rs12248560"}


def test_a_variant_named_by_two_tables_is_resolved_once(
    multiallelic_cache: Path, tmp_path: Path
) -> None:
    """Dedup by variant_key, and `variants.csv` wins — it is the table carrying `alts`, a fact
    column, so letting a PGx row win would move an already-compiled module's artifact.digest."""
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs4244285,A/G,risk,c\n")
    (spec / "pharm_variants.csv").write_text(
        "rsid,gene,genotype,drug,conclusion\nrs4244285,CYP2C19,A/G,clopidogrel,c\n",
        encoding="utf-8",
    )
    result = enrich(spec, offline=True, ensembl_cache=multiallelic_cache,
                    clinvar_cache=tmp_path / "no_clinvar")
    assert len([r for r in result.rows if r.rsid == "rs4244285"]) == 1


def test_haplotype_allele_filters_a_one_to_many_rsid(tmp_path: Path) -> None:
    """A haplotype's defining `allele` is a one-allele membership test, so it uses the same shared
    predicate as a genotype — a locus that cannot carry the allele is left out."""
    data = tmp_path / "hcache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(   # one rsid, two loci; only the first can host allele `T`
        {
            "id": ["rs999", "rs999"],
            "chrom": ["5", "6"],
            "start": [500, 600],
            "ref": ["A", "A"],
            "alt": ["T", "C"],
        }
    ).write_parquet(data / "chr.parquet")
    spec = _pgx_spec(
        tmp_path / "spec",
        haplotypes="haplotype_name,rsid,allele,gene\n*2,rs999,T,GENE\n",
    )
    result = enrich(spec, offline=True, ensembl_cache=tmp_path / "hcache",
                    clinvar_cache=tmp_path / "no_clinvar")
    assert [(r.chrom, r.start) for r in result.rows] == [("5", 500)]


def test_heteroplasmy_rows_resolve_like_the_other_tables(multiallelic_cache: Path, tmp_path: Path) -> None:
    """The third table that can ask for a coordinate, and it was left out of the 0.5 round.

    Its coordinates are optional exactly as the PGx ones are, so an rsid-authored heteroplasmy module
    resolved to an empty table and the compiler's positional-joinability warning would have named a
    gap no tool could close.
    """
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "heteroplasmy.csv").write_text(
        "rsid,gene,reference_sequence,measure_kind,measure_min,measure_max,conclusion\n"
        "rs4244285,CYP2C19,NC_012920.1,allele_fraction,0.0,0.1,c\n",
        encoding="utf-8",
    )
    result = enrich(spec, offline=True, ensembl_cache=multiallelic_cache,
                    clinvar_cache=tmp_path / "no_clinvar")

    assert result.unresolved == []
    assert [(r.rsid, r.chrom, r.start) for r in result.rows] == [("rs4244285", "10", 94781859)]


def test_a_heteroplasmy_row_keys_the_way_variants_csv_does(multiallelic_cache: Path, tmp_path: Path) -> None:
    """`HeteroplasmyRow.variant_key` mints *with* `alts` (unlike the PGx models), so a row naming the
    same locus as a `variants.csv` row must dedupe against it — and `variants.csv` must still win,
    since it is the table carrying `alts`, a resolution fact that decides the compiled bytes."""
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs4244285,A/G,risk,c\n")
    (spec / "heteroplasmy.csv").write_text(
        "rsid,gene,reference_sequence,measure_kind,measure_min,measure_max,conclusion\n"
        "rs4244285,CYP2C19,NC_012920.1,allele_fraction,0.0,0.1,c\n",
        encoding="utf-8",
    )
    result = enrich(spec, offline=True, ensembl_cache=multiallelic_cache,
                    clinvar_cache=tmp_path / "no_clinvar")

    assert len([r for r in result.rows if r.rsid == "rs4244285"]) == 1
    # the SNP row's `alts` survived, which is the thing dedup order exists to protect
    assert result.rows[0].alts == "A,C,T"
