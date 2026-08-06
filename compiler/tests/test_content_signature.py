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


# ── RM37: where a value was written is not part of the content ──────────────────────────────────

_YAML_WITH_DEFAULTS = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: demo\n  description: d\n  report_title: demo\n"
    "defaults:\n  curator: {curator}\n  method: {method}\n"
)
_CURATOR = "gwas-catalog-import"
_METHOD = "GWAS Catalog p<5e-8; GRCh38 forward-strand validated"


def _per_row(d: Path) -> Path:
    """The value on every row, `defaults:` left at the built-in values."""
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML.format(name="demo"), encoding="utf-8")
    (d / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene,curator,method\n"
        f"rs1801133,A/G,risk,MTHFR risk,MTHFR,{_CURATOR},{_METHOD}\n"
        f"rs4988235,C/T,protective,LCT persistence,MCM6,{_CURATOR},{_METHOD}\n",
        encoding="utf-8",
    )
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return d


def _in_defaults(d: Path) -> Path:
    """The same value stated once under `defaults:`, cells left blank — what `reverse` emits."""
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(
        _YAML_WITH_DEFAULTS.format(curator=_CURATOR, method=_METHOD), encoding="utf-8"
    )
    (d / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return d


def test_a_default_and_a_per_row_cell_are_the_same_content(tmp_path: Path) -> None:
    """RM37: `curator`/`method` in `defaults:` or on every row is one value written two ways.

    Hashing the cell alone made them different content, which is what moved `content_signature`
    across `compile → reverse → compile`: reverse re-emits the value in the *other* place.
    """
    assert content_signature(_per_row(tmp_path / "rows")) == content_signature(
        _in_defaults(tmp_path / "defaults")
    )


def test_the_round_trip_that_moved_the_signature_now_holds(tmp_path: Path) -> None:
    """The actual RM37 reproduction: compile → reverse → compile on a per-row-authored module.

    Every signature must hold from the first compile, not merely stabilize on the second — which is
    what "a fixed point" means, and what the old behaviour only managed from the second onward.
    """
    from just_dna_compiler.compiler import reverse_module

    spec = _per_row(tmp_path / "spec")
    first = compile_module(spec, tmp_path / "out1", resolve_with_ensembl=False)
    assert first.success, first.errors

    reverse_module(tmp_path / "out1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "out2", resolve_with_ensembl=False)
    assert second.success, second.errors

    assert second.manifest.content_signature == first.manifest.content_signature
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    # And the standalone reader agrees with both manifests.
    assert content_signature(tmp_path / "rev") == first.manifest.content_signature


def test_naming_the_built_in_default_leaves_the_signature_untouched(tmp_path: Path) -> None:
    """The normalization that keeps the change targeted, mirroring `genome_build`'s.

    A module that says nothing about `curator`/`method`, and one that spells out the built-in values,
    are the same content as each other — and as every module compiled before RM37, which is why no
    existing signature moves.
    """
    silent = _spec(tmp_path / "silent")
    spelled = tmp_path / "spelled"
    spelled.mkdir()
    (spelled / "module_spec.yaml").write_text(
        _YAML_WITH_DEFAULTS.format(curator="ai-module-creator", method="literature-review"),
        encoding="utf-8",
    )
    (spelled / "variants.csv").write_text(
        _VARIANTS.replace(
            "rsid,genotype,state,conclusion,gene\n",
            "rsid,genotype,state,conclusion,gene,curator,method\n",
        )
        .replace("MTHFR risk,MTHFR\n", "MTHFR risk,MTHFR,ai-module-creator,literature-review\n")
        .replace("LCT persistence,MCM6\n", "LCT persistence,MCM6,ai-module-creator,literature-review\n"),
        encoding="utf-8",
    )
    (spelled / "studies.csv").write_text(_STUDIES, encoding="utf-8")

    assert content_signature(spelled) == content_signature(silent)


def test_a_different_curator_is_still_different_content(tmp_path: Path) -> None:
    """Resolving defaults must not flatten a real distinction into agreement."""
    a = _in_defaults(tmp_path / "a")
    b = tmp_path / "b"
    b.mkdir()
    (b / "module_spec.yaml").write_text(
        _YAML_WITH_DEFAULTS.format(curator="someone-else", method=_METHOD), encoding="utf-8"
    )
    (b / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (b / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    assert content_signature(a) != content_signature(b)
