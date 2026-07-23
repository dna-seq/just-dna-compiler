"""content_signature — a stable, name-/Ensembl-independent content identity for registry dedup.

Unlike `artifact.digest` (compiled-parquet bytes, which move on recompile against a different Ensembl
reference), the content signature is computed from the RAW authored data rows, normalized and
deterministically sorted. It must therefore survive: a module rename / metadata edit (the "strip"
path), CSV reformatting and row reordering, and additive schema growth — while still *distinguishing*
genuinely different data.
"""

from pathlib import Path

from just_dna_compiler.compiler import compile_module, content_signature

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: {name}\n  title: {name}\n  description: d\n  report_title: {name}\n"
)
_STUDIES = "rsid,pmid\nrs1801133,9545397\nrs4988235,10820117\n"
_VARIANTS = (
    "rsid,genotype,state,conclusion,gene\n"
    "rs1801133,A/G,risk,MTHFR risk,MTHFR\n"
    "rs4988235,C/T,protective,LCT persistence,MCM6\n"
)
_PGX = (
    "rsid,gene,drug,response,evidence_level,conclusion\n"
    "rs9923231,VKORC1,warfarin,reduced dose requirement,1A,lower warfarin dose\n"
)


def _spec(d: Path, *, name: str = "demo", variants: str = _VARIANTS, studies: str = _STUDIES,
          pgx: str | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML.format(name=name), encoding="utf-8")
    (d / "variants.csv").write_text(variants, encoding="utf-8")
    (d / "studies.csv").write_text(studies, encoding="utf-8")
    if pgx is not None:
        (d / "pharm_variants.csv").write_text(pgx, encoding="utf-8")
    return d


def test_signature_is_name_and_metadata_independent(tmp_path: Path) -> None:
    a = content_signature(_spec(tmp_path / "a", name="demo"))
    b = content_signature(_spec(tmp_path / "b", name="totally_different_name"))
    assert a == b  # only module_spec.yaml differs → same content


def test_signature_ignores_reformatting_and_row_order(tmp_path: Path) -> None:
    base = content_signature(_spec(tmp_path / "base"))
    # reordered rows + reordered columns + extra whitespace/quoting → same normalized content
    reformatted = (
        "state , gene, rsid ,genotype,conclusion\n"
        'protective,MCM6,rs4988235,C/T,"LCT persistence"\n'
        "risk,MTHFR,rs1801133,A/G,MTHFR risk\n"
    )
    other = content_signature(_spec(tmp_path / "other", variants=reformatted))
    assert other == base


def test_signature_changes_when_data_changes(tmp_path: Path) -> None:
    base = content_signature(_spec(tmp_path / "base"))
    changed = content_signature(
        _spec(tmp_path / "changed", variants=_VARIANTS.replace("MTHFR risk", "MTHFR RISK!!"))
    )
    assert changed != base


def test_signature_covers_table_kinds_only_module(tmp_path: Path) -> None:
    # A PGx-only module (no variants.csv/studies.csv) still gets a signature.
    d = tmp_path / "pgx"
    d.mkdir()
    (d / "module_spec.yaml").write_text(_YAML.format(name="pgx"), encoding="utf-8")
    (d / "pharm_variants.csv").write_text(_PGX, encoding="utf-8")
    sig = content_signature(d)
    assert sig.startswith("sha256:")


def test_manifest_carries_signature_matching_standalone(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    assert result.manifest.content_signature == content_signature(spec)
    # distinct from the parquet artifact digest
    assert result.manifest.content_signature != result.manifest.artifact.digest


def test_signature_dedups_where_digest_cannot(tmp_path: Path) -> None:
    # Same data, different module name. The name is materialized into the parquet (`module` column),
    # so `artifact.digest` DIFFERS — which is exactly why the digest can't dedup across rename/strip.
    # content_signature (name-independent) MATCHES, enabling the dedup the digest misses.
    s1 = compile_module(_spec(tmp_path / "s1", name="one"), tmp_path / "o1", resolve_with_ensembl=False)
    s2 = compile_module(_spec(tmp_path / "s2", name="two"), tmp_path / "o2", resolve_with_ensembl=False)
    assert s1.manifest.content_signature == s2.manifest.content_signature
    assert s1.manifest.artifact.digest != s2.manifest.artifact.digest
