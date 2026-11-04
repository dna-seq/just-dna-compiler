"""A study's LD proxy is a resolution subject, so the compiler can check the proxy's alleles (RM331, 0.8).

`StudyRow.proxy_rsid` names the variant a study measured when it stood in for the row's lead variant,
and the compiler checks `effect_allele` against the PROXY's resolved alleles. That check has nothing to
read unless the proxy has a `resolution.csv` row, and a proxy is usually not a module variant (the
longevitymap v2 case, rs4970836 for the lead rs646776, is not). So `collect_subjects` admits each
stated proxy as a subject — after every table that names a module variant, so a proxy that is also one
keeps the identity its own row minted — and the GWAS pass, which asks the Catalog about the module's
own variants, leaves them out.

The snapshot rows are rs646776 and rs4970836 exactly as the provisioned Ensembl snapshot carries them
(chr1, `alt` pipe-joined as the snapshot writes it, `@snapshot-pipe-alt`), written to a one-file cache
so the run is offline and deterministic.
"""

import ast
import json
import logging
from pathlib import Path

import httpx
import just_dna_enricher.enrich.subjects as subjects_module
import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.compiler.reverse import RESOLUTION_SOURCE_TABLES
from just_dna_enricher.enrich import enrich
from just_dna_enricher.enrich.subjects import SUBJECT_TABLES, collect_subjects, study_proxy_rsids
from just_dna_enricher.frequencies import enrich_frequencies
from just_dna_enricher.gnomad import GnomadClient, GnomadSettings
from just_dna_enricher.gwas import _module_subjects
from just_dna_enricher.net import PacingGate
from just_dna_format.spec import VariantRow

_MODULE = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def _spec(tmp_path: Path, effect_allele: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_MODULE)
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs646776,G/G,protective,c\n")
    (spec / "studies.csv").write_text(
        "rsid,pmid,proxy_rsid,ancestry,effect_allele\n"
        f"rs646776,30642433,rs4970836,EUR,{effect_allele}\n"
        # The lead itself as a proxy elsewhere would be refused at the model; a second study of the
        # lead with no proxy is the ordinary row, and asks for nothing new.
        "rs646776,31413261,,EUR,G\n"
    )
    return spec


def _cache(tmp_path: Path) -> Path:
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs646776", "rs4970836"],
            "chrom": ["1", "1"],
            "start": [109275908, 109279175],
            "ref": ["C", "G"],
            "alt": ["G|T", "A|C"],
        }
    ).write_parquet(data / "chr1.parquet")
    return tmp_path / "cache"


def _variants(spec: Path) -> list[VariantRow]:
    return [VariantRow(rsid="rs646776", genotype="G/G", state="protective", conclusion="c")]


def test_a_stated_proxy_is_a_subject_after_the_module_variants(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "G")
    subjects = collect_subjects(spec, _variants(spec))
    assert [(s.variant_key, s.origin) for s in subjects] == [
        ("rs646776", "variants.csv"),
        ("rs4970836", "studies.csv"),
    ]
    proxy = subjects[1]
    # No constraint: the compiler's check is what judges `effect_allele` against the proxy, and a
    # constraint here would drop the very loci that check needs to see.
    assert (proxy.rsid, proxy.chrom, proxy.constraint) == ("rs4970836", None, None)


def test_a_proxy_that_is_also_a_module_variant_keeps_the_variants_subject(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "G")
    (spec / "studies.csv").write_text("rsid,pmid,proxy_rsid\nrs4970836,30642433,rs646776\n")
    subjects = collect_subjects(spec, _variants(spec))
    assert [(s.variant_key, s.origin) for s in subjects] == [("rs646776", "variants.csv")]


def test_the_gwas_pass_does_not_ask_the_catalog_about_proxies(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "G")
    assert collect_subjects(spec, _variants(spec), include_study_proxies=False)[-1].origin == "variants.csv"
    assert _module_subjects(spec) == [("rs646776", "rs646776")]


def test_enrich_resolves_the_proxy_and_the_compile_checks_its_alleles(tmp_path: Path) -> None:
    """The whole path: the proxy gets a row, a second run keeps it, and the compile reads it."""
    spec = _spec(tmp_path, "T")
    cache = _cache(tmp_path)
    for _ in range(2):  # the second run must not drop the proxy's row as out of scope
        result = enrich(spec, offline=True, ensembl_cache=cache, clinvar_cache=tmp_path, mint_vrs=False)
        placed = {r.rsid: (r.chrom, r.start, r.ref, r.alts) for r in result.rows if r.chrom}
        assert placed["rs4970836"] == ("1", 109279175, "G", "A,C")
        assert "rs646776" in placed

    # `T` is an allele of the lead (C/G/T) and not of the proxy (G/A/C): filed under the lead it used to
    # pass silently with the wrong meaning; read against the proxy it is refused, naming the proxy.
    refused = compile_module(spec, tmp_path / "strict", strict=True)
    assert not refused.success
    assert any("via proxy rs4970836" in e and "(A/C/G)" in e for e in refused.errors), refused.errors

    (spec / "studies.csv").write_text(
        (spec / "studies.csv").read_text().replace("rs4970836,EUR,T", "rs4970836,EUR,A")
    )
    accepted = compile_module(spec, tmp_path / "ok", strict=True)
    assert accepted.success, accepted.errors


def test_an_invalid_study_row_does_not_stop_the_run(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """studies.csv only adds proxies: a bad row is named once, and the good rows' proxies are still asked."""
    spec = _spec(tmp_path, "G")
    (spec / "studies.csv").write_text(
        "rsid,pmid,proxy_rsid,sample_size\n"
        "rs646776,30642433,rs4970836,\n"
        "rs646776,31413261,rs602633,389166\n"  # a size with no unit: refused at the model
    )
    with caplog.at_level(logging.WARNING):
        subjects = collect_subjects(spec, _variants(spec))
    assert [s.variant_key for s in subjects] == ["rs646776", "rs4970836"]
    assert any("studies.csv has 1 invalid row(s)" in r.getMessage() for r in caplog.records)


def test_the_frequency_pass_does_not_ask_gnomad_about_a_proxy(tmp_path: Path) -> None:
    """The proxy's resolution row serves the allele check only; it is not one of the module's loci."""
    spec = _spec(tmp_path, "G")
    enrich(spec, offline=True, ensembl_cache=_cache(tmp_path), clinvar_cache=tmp_path, mint_vrs=False)
    resolved = pl.read_csv(spec / "resolution.csv", infer_schema=False)
    assert set(resolved["rsid"]) >= {"rs646776", "rs4970836"}
    assert study_proxy_rsids(spec) == {"rs4970836"}

    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        lines = [ln for ln in json.loads(request.content)["query"].splitlines() if "variant(" in ln]
        asked.extend(lines)
        return httpx.Response(200, json={"data": {f"v{i}": None for i in range(len(lines))}})

    client = GnomadClient(settings=GnomadSettings())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    enrich_frequencies(spec, client=client, write=False)
    assert any("1-109275908-C-G" in line for line in asked), asked
    assert not any("109279175" in line for line in asked), asked


def test_a_proxys_resolution_row_survives_compile_reverse_compile(tmp_path: Path) -> None:
    """P7 on the proxy (RM331): reverse rebuilt `resolution.csv` from the weights and positional parquets
    only, and neither carries a proxy's coordinates. So lap 2 lost the proxy's row, `resolution_signature`
    moved, and the proxy allele check went silent on the reversed spec. The proxy's resolved loci now
    ride on `studies.parquet` and reverse re-emits them."""
    spec = _spec(tmp_path, "A")
    enrich(spec, offline=True, ensembl_cache=_cache(tmp_path), clinvar_cache=tmp_path, mint_vrs=False)
    first = compile_module(spec, tmp_path / "a1", strict=True)
    assert first.success, first.errors

    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    reversed_rows = pl.read_csv(tmp_path / "rev1" / "resolution.csv", infer_schema=False)
    proxy = reversed_rows.filter(pl.col("variant_key") == "rs4970836")
    assert proxy.select("rsid", "chrom", "start", "ref", "alts").rows() == [
        ("rs4970836", "1", "109279175", "G", "A,C")
    ]
    second = compile_module(tmp_path / "rev1", tmp_path / "a2", strict=True)
    assert second.success, second.errors
    assert second.manifest.compilation.resolution_signature == first.manifest.compilation.resolution_signature
    assert second.manifest.artifact.digest == first.manifest.artifact.digest

    # The check still reads the proxy after the reverse: a wrong allele is refused, naming the proxy.
    studies = pl.read_csv(tmp_path / "rev1" / "studies.csv", infer_schema=False)
    assert studies.filter(pl.col("proxy_rsid") == "rs4970836")["effect_allele"].to_list() == ["A"]
    studies.with_columns(
        pl.when(pl.col("proxy_rsid") == "rs4970836")
        .then(pl.lit("T"))
        .otherwise(pl.col("effect_allele"))
        .alias("effect_allele")
    ).write_csv(tmp_path / "rev1" / "studies.csv")
    refused = compile_module(tmp_path / "rev1", tmp_path / "a3", strict=True)
    assert any("via proxy rs4970836" in e for e in refused.errors), refused.errors


def test_every_table_enrich_asks_a_coordinate_for_is_one_reverse_rebuilds_it_from() -> None:
    """`@registry-completeness` across the round trip: a table whose rows `collect_subjects` admits as
    resolution subjects writes `resolution.csv` rows, and `compile → reverse → compile` keeps them only if
    reverse rebuilds them from some parquet. The proxy was the table that had no such parquet. Walked
    from the code on the enricher side (every `Subject(...)` origin), so a sixth table cannot join
    without this naming it."""
    source = Path(subjects_module.__file__).read_text(encoding="utf-8")
    origins: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Subject":
            arg = (
                node.args[7]
                if len(node.args) > 7
                else next(k.value for k in node.keywords if k.arg == "origin")
            )
            assert isinstance(arg, ast.Constant), (
                "a Subject's origin is a table name, spelled where it is built"
            )
            origins.add(arg.value)
    assert origins == set(SUBJECT_TABLES)
    assert set(SUBJECT_TABLES) == set(RESOLUTION_SOURCE_TABLES)
