"""0.2.0 additive features end-to-end through the compiler: ClinVar stats, structured provenance,
gene-panel passthrough, the `negatives` field, module logo, `icon_set`, and signed-manifest verify.

All run with resolve_with_ensembl=False (no reference/network needed)."""

import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_format.integrity import IntegrityError, sha256_file, verify_manifest
from just_dna_format.manifest import README_CANDIDATES
from just_dna_format.signing import generate_private_key_pem, public_key_b64_from_pem, sign_digest

_YAML = """\
schema_version: "1.0"
module:
  name: demo2
  title: Demo Two
  description: A demo module
  report_title: Demo Report
  icon: shield
  icon_set: awesome
  color: "#21ba45"
defaults:
  curator: tester
  method: manual
genome_build: GRCh38
panel:
  source: clinvar
  reference: "2026-06"
  reference_sha256: "sha256:deadbeef"
  genes: [BRCA1, BRCA2]
  significance: [pathogenic, likely_pathogenic]
"""

# Two clinvar rows, one pathogenic; one row carries `negatives`.
_VARIANTS = """\
rsid,chrom,start,ref,alts,genotype,weight,state,conclusion,negatives,gene,category,clinvar,pathogenic,benign
rs1801133,1,11856378,G,A,A/G,0.5,protective,ok,carries a trade-off,MTHFR,metabolism,true,false,false
rs7412,19,44908822,C,T,C/T,-0.3,risk,bad,,APOE,lipids,true,true,false
"""

_STUDIES = """\
rsid,pmid,population,p_value,conclusion,study_design
rs1801133,[PMID: 12345],EUR,0.01,assoc,GWAS
rs7412,67890,EUR,0.001,assoc,meta-analysis
"""

# A derived-fact sidecar: machine-produced, fact-hashed, byte-hashed into `manifest.derived` (S26).
# The two studies rows cite 12345/67890, so this is the citation check for one of them.
_LITERATURE = """\
pmid,doi,pmcid,exists,is_open_access,quotes_authored,quotes_found,source,status,fetched_at
12345,10.1000/demo,PMC12345,true,true,0,,pubmed,resolved,2026-08-01T20:55:37Z
"""

_PROVENANCE = {
    "generator": "agent-x",
    "model": "claude",
    "agent_version": "1.0",
    "items": [
        {"variant_key": "rs1801133", "rationale": "curated", "human_reviewed": True},
        {"variant_key": "rs7412", "confidence": 0.9},
    ],
}


def _write_spec(
    d: Path, *, provenance: bool = True, logo: bool = True, readme: bool = True
) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    if provenance:
        (d / "provenance.json").write_text(json.dumps(_PROVENANCE), encoding="utf-8")
    if logo:
        (d / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n fake-logo-bytes")
    if readme:
        (d / "README.md").write_text(
            "# demo2\n\nCandidate findings only — one association is not significant.\n",
            encoding="utf-8",
        )
    return d


def _compile(spec: Path, out: Path):
    result = compile_module(spec, out, resolve_with_ensembl=False, compiled_by="marketplace-server")
    assert result.success, result.errors
    assert result.manifest is not None
    return result.manifest


def test_clinvar_stats_counts(tmp_path: Path) -> None:
    m = _compile(_write_spec(tmp_path / "s"), tmp_path / "o")
    assert m.stats.clinvar_count == 2
    assert m.stats.pathogenic_count == 1
    assert m.stats.benign_count == 0


def test_panel_passthrough_verbatim(tmp_path: Path) -> None:
    m = _compile(_write_spec(tmp_path / "s"), tmp_path / "o")
    assert m.panel is not None
    assert m.panel.source == "clinvar"
    assert m.panel.genes == ["BRCA1", "BRCA2"]
    assert m.panel.significance == ["pathogenic", "likely_pathogenic"]
    assert m.panel.reference_sha256 == "sha256:deadbeef"
    # Panel does not materialize variants: count still reflects only variants.csv.
    assert m.stats.variant_count == 2


def test_icon_set_flows_to_manifest(tmp_path: Path) -> None:
    m = _compile(_write_spec(tmp_path / "s"), tmp_path / "o")
    assert m.display.icon == "shield"
    assert m.display.icon_set == "awesome"


def test_negatives_lands_in_weights(tmp_path: Path) -> None:
    out = tmp_path / "o"
    _compile(_write_spec(tmp_path / "s"), out)
    weights = pl.read_parquet(out / "weights.parquet")
    assert "negatives" in weights.columns
    row = weights.filter(pl.col("rsid") == "rs1801133")
    assert row["negatives"].to_list() == ["carries a trade-off"]


def test_provenance_summary_and_hash(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    assert m.provenance is not None
    assert m.provenance.item_count == 2
    assert m.provenance.generator == "agent-x"
    assert m.provenance.file == "provenance.json"
    assert (out / "provenance.json").is_file()
    assert m.provenance.sha256 == sha256_file(out / "provenance.json")


def test_logo_hashed_and_shipped(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    assert m.logo is not None
    assert m.logo.name == "logo.png"
    assert (out / "logo.png").is_file()
    assert m.logo.sha256 == sha256_file(out / "logo.png")
    # Logo is NOT an artifact file (out of digest).
    assert "logo.png" not in {f.name for f in m.artifact.files}


def test_readme_hashed_and_shipped(tmp_path: Path) -> None:
    """`manifest.readme` mirrors `logo`: shipped beside the parquet, hashed, out of the digest (S25).

    The field exists so prose can be *served and verified* by anything reading manifests — a registry,
    an installer, a mirror. Before it, a publisher's README sat on disk attested by nothing, so a
    registry that (rightly) refuses to serve files it cannot hash could not serve it at all."""
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    assert m.readme is not None
    assert m.readme.name == "README.md"
    assert (out / "README.md").is_file()
    assert m.readme.sha256 == sha256_file(out / "README.md")
    assert m.readme.size == (out / "README.md").stat().st_size
    # Prose is not content: out of artifact.files, so out of the digest.
    assert "README.md" not in {f.name for f in m.artifact.files}
    # And not an input either — `inputs[]` is the authored data, which a readme is not.
    assert "README.md" not in {f.name for f in m.inputs}


def test_readme_discovery_prefers_the_conventional_spelling(tmp_path: Path) -> None:
    """Discovery order is fixed and stated, because two candidates on disk must not pick by luck.

    `README_CANDIDATES` puts the uppercase stem first and sorts extensions (`md` before `rst`/`txt`),
    so a directory carrying several readmes resolves the same way on every machine — the deterministic
    -ordering rule the rest of this codebase applies to emitted rows applies to a discovered file too."""
    spec = _write_spec(tmp_path / "s", readme=False)
    (spec / "readme.md").write_text("lowercase\n", encoding="utf-8")
    (spec / "README.txt").write_text("plain text\n", encoding="utf-8")
    (spec / "README.md").write_text("the conventional one\n", encoding="utf-8")

    m = _compile(spec, tmp_path / "o")
    assert m.readme is not None
    assert m.readme.name == "README.md"
    assert README_CANDIDATES[0] == "README.md"
    # A non-markdown readme is still legal — the extension travels for whoever renders it.
    alt = _write_spec(tmp_path / "s2", readme=False)
    (alt / "README.rst").write_text("Title\n=====\n", encoding="utf-8")
    assert _compile(alt, tmp_path / "o2").readme.name == "README.rst"


def test_unsupported_readme_extension_rejected(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path / "s", readme=False)
    doc = spec / "README.docx"
    doc.write_bytes(b"PK\x03\x04not-really-a-docx")
    result = compile_module(
        spec, tmp_path / "o", resolve_with_ensembl=False, readme_file=doc
    )
    assert not result.success
    assert any("readme must be one of" in e for e in result.errors)


def test_optional_files_do_not_change_either_identity(tmp_path: Path) -> None:
    """Both halves of identity, not just the digest — the property S25's reporter reasoned from.

    They rejected putting `README.md` in `artifact.files` themselves, because on an immutable registry
    a corrected caveat would then cost a version number and the fixed module would collide with its
    own predecessor under a content-dedup check. That argument only holds if the readme stays out of
    `content_signature` too, so this computes both rather than asserting the digest alone."""
    full = _compile(_write_spec(tmp_path / "full"), tmp_path / "of")
    bare = _compile(
        _write_spec(tmp_path / "bare", provenance=False, logo=False, readme=False),
        tmp_path / "ob",
    )
    # provenance.json + logo.png + README.md are out of artifact.digest → identical byte identity.
    assert full.artifact.digest == bare.artifact.digest
    assert full.content_signature == bare.content_signature
    assert full.readme is not None and bare.readme is None


def test_editing_the_readme_moves_no_identity(tmp_path: Path) -> None:
    """The motivating case: fixing a typo in a caveat must be a patch, not a new version.

    Same authored data, a rewritten readme. Both identities must be byte-identical and only the
    readme's own hash may move — otherwise a publisher correcting a sentence mints a module that
    collides with its predecessor."""
    spec = _write_spec(tmp_path / "s")
    first = _compile(spec, tmp_path / "o1")
    (spec / "README.md").write_text(
        "# demo2\n\nCandidate findings only — one association is **not** significant.\n",
        encoding="utf-8",
    )
    second = _compile(spec, tmp_path / "o2")

    assert second.artifact.digest == first.artifact.digest
    assert second.content_signature == first.content_signature
    assert second.readme.sha256 != first.readme.sha256


def test_unsupported_logo_extension_rejected(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path / "s", logo=False)
    gif = spec / "logo.gif"
    gif.write_bytes(b"GIF89a")
    # An unsupported logo now surfaces as a compile error, not an uncaught exception.
    result = compile_module(spec, tmp_path / "o", resolve_with_ensembl=False, logo_file=gif)
    assert not result.success
    assert any("logo must be one of" in e for e in result.errors)


def test_derived_sidecars_are_attested_without_becoming_content(tmp_path: Path) -> None:
    """`manifest.derived` byte-hashes the sidecar CSVs so they can be served (S26).

    They were reachable by nobody: `_INPUT_FILES` excludes them on purpose (they are fact-hashed, not
    byte-hashed) and only their *parquets* are in `_OUTPUT_FILES`, so a registry serving only what the
    manifest attests could not hand back the table that produced a parquet. The two hashes answer
    different questions and this test pins both: the byte hash appears, and neither identity moves."""
    spec = _write_spec(tmp_path / "s")
    bare = _compile(spec, tmp_path / "o1")
    assert bare.derived == []  # nothing fabricated when no sidecar exists

    (spec / "literature.csv").write_text(_LITERATURE, encoding="utf-8")
    with_sidecar = _compile(spec, tmp_path / "o2")

    names = {e.name for e in with_sidecar.derived}
    assert names == {"literature.csv"}
    entry = with_sidecar.derived[0]
    assert entry.sha256 == sha256_file(spec / "literature.csv")

    # Attested, but not content: the sidecar's own parquet is in the artifact and its CSV is not.
    assert "literature.parquet" in {f.name for f in with_sidecar.artifact.files}
    assert "literature.csv" not in {f.name for f in with_sidecar.artifact.files}
    assert "literature.csv" not in {f.name for f in with_sidecar.inputs}
    # The authored data did not change, so the authored identity must not have.
    assert with_sidecar.content_signature == bare.content_signature


def test_the_byte_hash_never_displaces_the_fact_hash(tmp_path: Path) -> None:
    """The trap this field creates, pinned: a rewrite that preserves the FACTS moves the byte hash.

    That is why `derived[]` is excluded from `_INPUT_FILES` and why its docstring says the byte hash is
    transport only. A consumer reading it as identity would call a legitimate re-emission tampering —
    the exact failure the fact signatures exist to prevent, so the two must be observably independent."""
    spec = _write_spec(tmp_path / "s")
    (spec / "literature.csv").write_text(_LITERATURE, encoding="utf-8")
    first = _compile(spec, tmp_path / "o1")

    # Same facts, different bytes: a trailing blank line and a reordered column would both do it.
    (spec / "literature.csv").write_text(_LITERATURE + "\n", encoding="utf-8")
    second = _compile(spec, tmp_path / "o2")

    assert second.derived[0].sha256 != first.derived[0].sha256, "byte hash should track bytes"
    assert second.literature.signature == first.literature.signature, "facts are unchanged"
    assert second.content_signature == first.content_signature


def test_verify_catches_a_tampered_sidecar_but_tolerates_an_absent_one(tmp_path: Path) -> None:
    """Sidecars live beside the spec, so a consumer holding only the artifact has none — skip, not fail.

    Mirrors `logs`, and deliberately not `inputs`, which *raises* on a missing file. That asymmetry is
    the reporter's own requirement ("an absent one must not invalidate a module") and it is what makes
    the check usable against a module dir that was never meant to carry them."""
    spec = _write_spec(tmp_path / "s")
    (spec / "literature.csv").write_text(_LITERATURE, encoding="utf-8")
    out = tmp_path / "o"
    m = _compile(spec, out)

    # The artifact dir carries no sidecar at all: every entry is skipped, nothing fails.
    verify_manifest(out, m, check_derived=True)

    # Beside the spec, where they really live, a substitution is caught.
    (out / "literature.csv").write_text(_LITERATURE.replace("12345", "99999"), encoding="utf-8")
    with pytest.raises(IntegrityError, match="derived sidecar hash mismatch"):
        verify_manifest(out, m, check_derived=True)
    verify_manifest(out, m)  # off by default


def test_verify_manifest_checks_optional_files(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    verify_manifest(
        out, m, check_logs=True, check_provenance=True, check_logo=True, check_readme=True
    )

    (out / "provenance.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(IntegrityError, match="provenance hash mismatch"):
        verify_manifest(out, m, check_provenance=True)


def test_verify_catches_a_tampered_readme(tmp_path: Path) -> None:
    """A served readme must be *verifiable*, which is the whole reason it is a hashed `FileEntry`.

    Also pins the tri-state the other optional assets use: an absent readme is skipped rather than
    failed, since a consumer may legitimately not download one."""
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)

    (out / "README.md").write_text("substituted prose\n", encoding="utf-8")
    with pytest.raises(IntegrityError, match="readme hash mismatch"):
        verify_manifest(out, m, check_readme=True)
    # Off by default: the same tampered file passes when the caller did not ask.
    verify_manifest(out, m)

    (out / "README.md").unlink()
    verify_manifest(out, m, check_readme=True)  # absent ≠ failed


def test_signed_manifest_verifies_with_pinned_key(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    pem = generate_private_key_pem()
    m.signature = sign_digest(m.artifact.digest, pem)

    verify_manifest(out, m, public_key=public_key_b64_from_pem(pem))
    with pytest.raises(IntegrityError, match="pinned"):
        verify_manifest(out, m, public_key=public_key_b64_from_pem(generate_private_key_pem()))


def test_pinned_key_but_unsigned_manifest_fails(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    with pytest.raises(IntegrityError, match="no signature"):
        verify_manifest(out, m, public_key=public_key_b64_from_pem(generate_private_key_pem()))
