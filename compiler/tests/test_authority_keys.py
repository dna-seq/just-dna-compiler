"""Injected authority-key stripping + genuine `module.version` adoption (0.4.1).

Covers the DI design from docs/PROPOSAL_0_4_1.md: a consumer injects the set of registry-owned
identity keys it stamps (`IDENTITY_AUTHORITY_KEYS`), the format's owned stripper removes them before
validation, and the validator stays strict for everything else. Plus: `version` is a genuine
advisory field (accepted, previewed against the future SemVer parser, digest-neutral), not stripped.
"""

from pathlib import Path

from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_format.normalize import IDENTITY_AUTHORITY_KEYS

_VARIANTS = "rsid,genotype,state,conclusion,gene\nrs1801133,A/G,risk,MTHFR risk,MTHFR\n"
_STUDIES = "rsid,pmid\nrs1801133,9545397\n"


def _module_yaml(*, version_line: str = "", extra_lines: str = "") -> str:
    return (
        "schema_version: '1.0'\n"
        "module:\n"
        "  name: demo\n"
        "  title: Demo\n"
        "  description: A demo module\n"
        "  report_title: Demo\n"
        f"{version_line}"
        f"{extra_lines}"
    )


def _write_spec(d: Path, yaml_text: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(yaml_text, encoding="utf-8")
    (d / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return d


# ── Injected authority-key strip ────────────────────────────────────────────────

_LEGACY_IDENTITY = "  namespace: acme\n  owner: acme\n  canonical_id: acme/demo@2.0.0\n"


def test_injected_authority_keys_strip_and_validate(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path / "spec", _module_yaml(extra_lines=_LEGACY_IDENTITY))
    result = validate_spec(spec, authority_keys=IDENTITY_AUTHORITY_KEYS)
    assert result.valid, result.errors
    joined = " ".join(result.info)
    assert "namespace" in joined and "owner" in joined and "canonical_id" in joined


def test_no_injection_forbids_authority_keys(tmp_path: Path) -> None:
    # The validator validates, it does not fix: with nothing injected, the stray registry keys
    # trip extra="forbid" loudly.
    spec = _write_spec(tmp_path / "spec", _module_yaml(extra_lines=_LEGACY_IDENTITY))
    result = validate_spec(spec)
    assert not result.valid
    assert any("namespace" in e for e in result.errors)


def test_typo_still_forbidden_even_with_injection(tmp_path: Path) -> None:
    # A near-miss of an authority key (not in the injected set) must still fail — the strip is exact.
    spec = _write_spec(tmp_path / "spec", _module_yaml(extra_lines="  namespac: acme\n"))
    result = validate_spec(spec, authority_keys=IDENTITY_AUTHORITY_KEYS)
    assert not result.valid
    assert any("namespac" in e for e in result.errors)


def test_authority_keys_do_not_leak_into_manifest(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path / "spec", _module_yaml(extra_lines=_LEGACY_IDENTITY))
    result = compile_module(
        spec, tmp_path / "out", resolve_with_ensembl=False, authority_keys=IDENTITY_AUTHORITY_KEYS
    )
    assert result.success, result.errors
    # The registry still stamps identity on publish — authored copies were dropped, not honored.
    assert result.manifest.identity.namespace is None
    assert result.manifest.identity.canonical_id is None
    assert result.manifest.owner is None


# ── Genuine `module.version` adoption ────────────────────────────────────────────


def test_informal_version_is_coerced_and_the_rewrite_is_reported(tmp_path: Path) -> None:
    # RM17 (0.5): what was a read-only preview in 0.4.1 is now enforcement. The rewrite is still
    # announced — coercing silently would be the one place this codebase edits an authored value
    # without saying so.
    spec = _write_spec(tmp_path / "spec", _module_yaml(version_line="  version: v2\n"))
    result = validate_spec(spec)
    assert result.valid, result.errors
    assert any("'v2'" in w and "2.0.0" in w for w in result.warnings)


def test_clean_semver_version_is_silent(tmp_path: Path) -> None:
    # Coercion is idempotent, so an already-clean value is not "rewritten" and says nothing.
    spec = _write_spec(tmp_path / "spec", _module_yaml(version_line="  version: 1.2.3\n"))
    result = validate_spec(spec)
    assert result.valid, result.errors
    assert not any("module.version" in w for w in result.warnings)


def test_authored_semver_flows_into_manifest_identity(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path / "spec", _module_yaml(version_line="  version: 1.2.3\n"))
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    assert result.manifest.identity.version == "1.2.3"


def test_informal_version_now_reaches_manifest_identity(tmp_path: Path) -> None:
    # Changed by RM17, and the point of it: in 0.4.1 a non-SemVer `v2` was left out of Identity
    # entirely, so a module carrying the pre-0.4 corpus's spelling published with no version at all.
    # Coercion means the author's intent survives into the manifest instead of being dropped.
    spec = _write_spec(tmp_path / "spec", _module_yaml(version_line="  version: v2\n"))
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    assert result.manifest.identity.version == "2.0.0"


def test_version_coercion_is_idempotent_across_a_roundtrip(tmp_path: Path) -> None:
    # A coerced value must be a fixed point, or every recompile would report the rewrite again and
    # `Identity.version` would drift (Principle 7).
    spec = _write_spec(tmp_path / "spec", _module_yaml(version_line="  version: v2\n"))
    first = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    again = _write_spec(tmp_path / "spec2", _module_yaml(version_line="  version: 2.0.0\n"))
    second = compile_module(again, tmp_path / "out2", resolve_with_ensembl=False)
    assert first.manifest.identity.version == second.manifest.identity.version == "2.0.0"
    assert not any("module.version" in w for w in second.warnings)


def test_version_is_digest_neutral(tmp_path: Path) -> None:
    with_v = compile_module(
        _write_spec(tmp_path / "with_v", _module_yaml(version_line="  version: 3.1.4\n")),
        tmp_path / "out_with", resolve_with_ensembl=False,
    )
    without_v = compile_module(
        _write_spec(tmp_path / "without_v", _module_yaml()),
        tmp_path / "out_without", resolve_with_ensembl=False,
    )
    assert with_v.success and without_v.success
    assert with_v.manifest.artifact.digest == without_v.manifest.artifact.digest


def test_version_roundtrips_through_reverse_when_supplied(tmp_path: Path) -> None:
    # version is out-of-digest metadata (not materialized), so reverse re-emits it only when the
    # caller supplies it; the recompiled spec then accepts it and it reaches the manifest.
    compile_module(
        _write_spec(tmp_path / "spec", _module_yaml(version_line="  version: 1.2.3\n")),
        tmp_path / "out", resolve_with_ensembl=False,
    )
    reversed_dir = reverse_module(tmp_path / "out", tmp_path / "reversed", version="1.2.3")
    assert "version: 1.2.3" in (reversed_dir / "module_spec.yaml").read_text(encoding="utf-8")
    recompiled = compile_module(reversed_dir, tmp_path / "out2", resolve_with_ensembl=False)
    assert recompiled.success, recompiled.errors
    assert recompiled.manifest.identity.version == "1.2.3"
