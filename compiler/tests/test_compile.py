"""Compiler tests (SPEC §13): manifest emission, gene/category stats, and integrity round-trip.

All tests run with resolve_with_ensembl=False, so no Ensembl reference/network is needed. The
Ensembl-resolving path is integration-tested separately with real reference data.
"""

import hashlib
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.integrity import IntegrityError, verify_manifest
from just_dna_format.manifest import read_manifest

_MODULE_YAML = """\
schema_version: "1.0"
module:
  name: demo_module
  title: Demo Module
  description: A demo module
  report_title: Demo Report
  icon: dna
  color: "#21ba45"
defaults:
  curator: tester
  method: manual
genome_build: GRCh38
"""

_VARIANTS_CSV = """\
rsid,chrom,start,ref,alts,genotype,weight,state,conclusion,gene,category
rs1801133,1,11856378,G,A,A/G,0.5,protective,ok,MTHFR,metabolism
rs7412,19,44908822,C,T,C/T,-0.3,risk,bad,APOE,lipids
"""

_STUDIES_CSV = """\
rsid,pmid,population,p_value,conclusion,study_design
rs1801133,12345,EUR,0.01,assoc,GWAS
rs7412,67890,EUR,0.001,assoc,meta-analysis
"""


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    (tmp_path / "module_spec.yaml").write_text(_MODULE_YAML, encoding="utf-8")
    (tmp_path / "variants.csv").write_text(_VARIANTS_CSV, encoding="utf-8")
    (tmp_path / "studies.csv").write_text(_STUDIES_CSV, encoding="utf-8")
    return tmp_path


def test_validate_spec_emits_gene_and_category_lists(spec_dir: Path) -> None:
    result = validate_spec(spec_dir)
    assert result.valid, result.errors
    assert result.stats["genes"] == ["APOE", "MTHFR"]        # sorted, None filtered
    assert result.stats["categories"] == ["lipids", "metabolism"]
    assert result.stats["variant_count"] == 2
    assert result.stats["gene_count"] == 2
    assert result.stats["study_count"] == 2


def test_validate_spec_requires_studies(tmp_path: Path) -> None:
    (tmp_path / "module_spec.yaml").write_text(_MODULE_YAML, encoding="utf-8")
    (tmp_path / "variants.csv").write_text(_VARIANTS_CSV, encoding="utf-8")
    result = validate_spec(tmp_path)
    assert not result.valid
    assert any("studies.csv is missing" in e for e in result.errors)


def test_ragged_row_with_surplus_cell_is_an_error(tmp_path: Path) -> None:
    # A data row with more cells than the header would otherwise have its surplus bucketed under
    # DictReader's `None` key and silently dropped — a shifted/extra column slipping past
    # extra="forbid". It must fail validation with a line-located diagnosis instead.
    (tmp_path / "module_spec.yaml").write_text(_MODULE_YAML, encoding="utf-8")
    (tmp_path / "studies.csv").write_text(_STUDIES_CSV, encoding="utf-8")
    (tmp_path / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\n"
        "rs1801133,A/G,protective,ok,SURPLUS_SHIFTED_VALUE\n",
        encoding="utf-8",
    )
    result = validate_spec(tmp_path)
    assert not result.valid
    assert any(
        "more values than header columns" in e and "line 2" in e for e in result.errors
    ), result.errors


def test_an_unknown_file_is_tolerated_and_changes_no_digest(spec_dir: Path, tmp_path: Path) -> None:
    """Unknown files in a spec directory are ignored — a stated contract, not an accident (S16).

    A module may carry a publisher's receipt or curation notes, whose keys cannot go in
    `module_spec.yaml` because `extra="forbid"` rejects them. The guarantee consumers need is that such
    a file is neither read nor hashed, so the digest is computed here rather than asserted: same spec,
    plus two unknown files, same digest.

    **`README.md` is the one that moved out of this class** (S25). It is now discovered, copied and
    hashed into `manifest.readme` so a registry can serve and verify it — but it is still outside
    `artifact.files`, so the digest guarantee below covers it unchanged. Both claims are asserted here
    together, because "hashed" and "moves the digest" were the same sentence until they stopped being
    the same sentence."""
    before = compile_module(spec_dir, tmp_path / "before", resolve_with_ensembl=False)
    assert before.success, before.errors

    (spec_dir / "README.md").write_text("# notes\n", encoding="utf-8")
    (spec_dir / "published.json").write_text('{"namespace": "acme"}\n', encoding="utf-8")
    after = compile_module(spec_dir, tmp_path / "after", resolve_with_ensembl=False)

    assert after.success, after.errors
    assert after.manifest.artifact.digest == before.manifest.artifact.digest
    assert after.manifest.content_signature == before.manifest.content_signature
    assert {f.name for f in after.manifest.artifact.files} == {
        f.name for f in before.manifest.artifact.files
    }
    # The readme is attested; the receipt is genuinely ignored — that is the line the contract draws.
    assert after.manifest.readme is not None and after.manifest.readme.name == "README.md"
    assert before.manifest.readme is None
    assert validate_spec(spec_dir).valid
    # Tolerated means silent: no finding names a file the compiler has no meaning for.
    assert not [w for w in after.warnings if "README" in w or "published.json" in w]


def test_a_mistyped_table_name_is_not_silently_ignored(spec_dir: Path) -> None:
    """The one case where "ignored" is the wrong answer, found while probing S16.

    A typo in a table filename drops every row in it and still compiles green. The check is a **near
    miss** rather than "any unknown csv", because warning about every unrecognised file would undo the
    tolerance the test above pins — so it must fire here and stay silent on an unrelated name."""
    (spec_dir / "varaints.csv").write_text(
        "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,typo\n", encoding="utf-8"
    )
    (spec_dir / "curation_notes.csv").write_text("note\nchecked by hand\n", encoding="utf-8")

    result = validate_spec(spec_dir)
    assert result.valid, "a near miss is a warning — the file may genuinely not be a table"
    named = [w for w in result.warnings if "varaints.csv" in w]
    assert len(named) == 1, result.warnings
    assert "variants.csv" in named[0] and "silently ignored" in named[0]
    assert not [w for w in result.warnings if "curation_notes.csv" in w], "no false positive"


def test_compile_emits_parquets_and_manifest(spec_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = compile_module(spec_dir, out, resolve_with_ensembl=False)
    assert result.success, result.errors
    for name in ("weights.parquet", "annotations.parquet", "studies.parquet", "manifest.json"):
        assert (out / name).is_file(), f"missing {name}"

    manifest = result.manifest
    assert manifest is not None
    assert manifest.identity.name == "demo_module"
    assert manifest.stats.genes == ["APOE", "MTHFR"]
    assert manifest.stats.variant_count == 2
    assert manifest.stats.weights_rows == 2
    assert manifest.compilation.compile_success is True
    assert manifest.compilation.compiler_version.startswith("just-dna-compiler")
    assert {f.name for f in manifest.artifact.files} == {
        "weights.parquet", "annotations.parquet", "studies.parquet"
    }
    # The on-disk manifest matches the returned one.
    assert read_manifest(out / "manifest.json") == manifest


def test_input_hashes_match_hashlib(spec_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    manifest = compile_module(spec_dir, out, resolve_with_ensembl=False).manifest
    assert manifest is not None
    by_name = {i.name: i for i in manifest.inputs}
    for fname in ("module_spec.yaml", "variants.csv", "studies.csv"):
        expected = "sha256:" + hashlib.sha256((spec_dir / fname).read_bytes()).hexdigest()
        assert by_name[fname].sha256 == expected


def test_local_compile_is_untrusted_but_marketplace_compile_verifies(
    spec_dir: Path, tmp_path: Path
) -> None:
    # Local compile leaves compiled_by=None -> marketplace trust check rejects it.
    local = tmp_path / "local"
    compile_module(spec_dir, local, resolve_with_ensembl=False)
    manifest = read_manifest(local / "manifest.json")
    with pytest.raises(IntegrityError, match="untrusted"):
        verify_manifest(local, manifest)
    verify_manifest(local, manifest, require_marketplace=False)  # ok without the trust gate

    # A marketplace-tagged compile passes the full check.
    served = tmp_path / "served"
    compile_module(spec_dir, served, resolve_with_ensembl=False, compiled_by="marketplace-server")
    verify_manifest(served, read_manifest(served / "manifest.json"))


def test_tampered_parquet_fails_verification(spec_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    compile_module(spec_dir, out, resolve_with_ensembl=False, compiled_by="marketplace-server")
    manifest = read_manifest(out / "manifest.json")
    (out / "weights.parquet").write_bytes(b"corrupted")
    with pytest.raises(IntegrityError):
        verify_manifest(out, manifest)
