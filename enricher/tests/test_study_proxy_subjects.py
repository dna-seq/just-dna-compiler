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

from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module
from just_dna_enricher.enrich import enrich
from just_dna_enricher.enrich.subjects import collect_subjects
from just_dna_enricher.gwas import _module_subjects
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
