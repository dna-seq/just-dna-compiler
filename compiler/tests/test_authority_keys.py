"""Injected authority-key stripping + genuine `module.version` adoption (0.4.1).

Covers the DI design from docs/proposals/PROPOSAL_0_4_1.md: a consumer injects the set of registry-owned
identity keys it stamps (`IDENTITY_AUTHORITY_KEYS`), the format's owned stripper removes them before
validation, and the validator stays strict for everything else. Plus: `version` is a genuine
advisory field (accepted, previewed against the future SemVer parser, digest-neutral), not stripped.

Since RM133 the same wiring carries a second registry-owned family, `PRESENTATION_AUTHORITY_KEYS`, and
the end of this file is the property that family exists for: a subtitle held beside the module leaves
`manifest.inputs` matching and the closure standing, where the same amendment written into the spec
drops both.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    authored_input_entries,
    close_module,
    compile_module,
    load_spec,
    reverse_module,
    validate_spec,
)
from just_dna_format import verification as verification_module
from just_dna_format.integrity import IntegrityError, verify_manifest
from just_dna_format.manifest import ModuleManifest
from just_dna_format.normalize import (
    IDENTITY_AUTHORITY_KEYS,
    PRESENTATION_AUTHORITY_KEYS,
    SHORT_DESCRIPTION_MAX_CHARS,
    strip_authority_keys,
)
from just_dna_format.spec import ModuleInfo
from just_dna_format.verification import (
    attestation_failure,
    module_binding,
    read_verification,
)

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


# ── The presentation family: a subtitle that has an amendable home (RM133) ───────

_EASY = 8  # proof-of-work bits; these cases are about the binding, not about the cost of the work


@pytest.fixture()
def cheap_proof_of_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", _EASY)


_SUBTITLE = "Iron overload risk from the two common HFE variants."


def _installed_module_dir(spec: Path, out: Path, manifest: ModuleManifest) -> Path:
    """The shape a consumer verifies: the compiled artifact with its authored inputs beside it.

    `compile_module` writes the artifact to its own directory and leaves the inputs where they were
    authored, so a `check_inputs=True` verification needs the two brought together — which is exactly
    what a registry serves and what an installer unpacks.
    """
    for entry in manifest.inputs:
        shutil.copy2(spec / entry.name, out / entry.name)
    return out


def test_a_subtitle_held_beside_the_module_leaves_the_closure_standing(
    tmp_path: Path, cheap_proof_of_work: None
) -> None:
    """The whole point of RM133, proved against the two hashes the reporter measured.

    Leg 1 is the route the item chose: the registry keeps `short_description` in its own record and
    hands us a `module:` block carrying it, `strip_authority_keys` removes it before validation, and
    nothing on disk moves — so `manifest.inputs` still matches, `verify_manifest` still passes and the
    attestation still binds. Leg 2 is the defect it routes around, and it is here because leg 1 alone
    cannot fail: an amendment written into `module_spec.yaml` — the natural-looking repair, and what a
    `short_description` field on `ModuleInfo` would have been — moves the authored bytes and drops
    both the input check and the closure, with no identity hash moving to announce it.
    """
    spec = _write_spec(tmp_path / "spec", _module_yaml())
    out = tmp_path / "out"
    compiled = compile_module(spec, out, resolve_with_ensembl=False)
    assert compiled.success, compiled.errors
    closure = close_module(spec, closed_by="A Reviewer")
    assert closure.closed, closure.errors
    doc = read_verification(closure.path)

    module_dir = _installed_module_dir(spec, out, compiled.manifest)
    verify_manifest(module_dir, compiled.manifest, require_marketplace=False, check_inputs=True)
    binding = module_binding(authored_input_entries(spec))
    assert attestation_failure(doc, binding, difficulty=_EASY) is None

    # ── Leg 1: the registry amends the subtitle, holding it beside the module.
    authored_bytes = (spec / "module_spec.yaml").read_bytes()
    stamped = load_spec(spec / "module_spec.yaml").module.model_dump(exclude_none=True) | {
        "short_description": _SUBTITLE
    }
    clean, dropped = strip_authority_keys(stamped, PRESENTATION_AUTHORITY_KEYS)
    assert dropped == ["short_description"]
    # The block our validator sees is the authored one, unchanged — the amendment never reaches it.
    assert ModuleInfo(**clean) == load_spec(spec / "module_spec.yaml").module
    assert (spec / "module_spec.yaml").read_bytes() == authored_bytes
    verify_manifest(module_dir, compiled.manifest, require_marketplace=False, check_inputs=True)
    assert (
        attestation_failure(doc, module_binding(authored_input_entries(spec)), difficulty=_EASY)
        is None
    )

    # ── Leg 2: the same amendment written into the spec, which is the measured defect.
    (spec / "module_spec.yaml").write_text(
        _module_yaml().replace("description: A demo module", f"description: {_SUBTITLE}"),
        encoding="utf-8",
    )
    assert (spec / "module_spec.yaml").read_bytes() != authored_bytes
    edited = module_binding(authored_input_entries(spec))
    assert edited != binding
    assert attestation_failure(doc, edited, difficulty=_EASY) is not None
    _installed_module_dir(spec, out, compiled.manifest)
    with pytest.raises(IntegrityError, match="input hash mismatch"):
        verify_manifest(module_dir, compiled.manifest, require_marketplace=False, check_inputs=True)
    # And the identity hashes say nothing about it — which is why the subtitle needed a home at all.
    recompiled = compile_module(spec, tmp_path / "out2", resolve_with_ensembl=False)
    assert recompiled.success, recompiled.errors
    assert recompiled.manifest.content_signature == compiled.manifest.content_signature
    assert recompiled.manifest.artifact.digest == compiled.manifest.artifact.digest


def test_an_authored_short_description_is_refused_and_an_injected_one_is_stripped(
    tmp_path: Path,
) -> None:
    """The validator validates, it does not fix — the same contract the identity family carries.

    With nothing injected an authored `short_description:` trips `extra="forbid"`, because it is
    registry-owned and a spec is not where it lives. With the key injected the spec validates and the
    value is reported as dropped, so a caller can see what it took off rather than guessing.

    **The refusal is the generic one, and this test says so rather than papering over it.** Asserting
    only that the key appears in the message would pass either way — pydantic embeds the field
    location in `extra inputs are not permitted` — which is exactly the false comfort that would hide
    the gap. `reject_authority_keys` diagnoses the identity family by name and does not yet reach this
    one, so an author who pastes a registry-served block gets a dead end where the identity keys get a
    fix. Pinning the current shape here is what makes that visible and makes this test fail loudly the
    day a specific diagnosis is added, instead of silently continuing to pass.
    """
    spec = _write_spec(
        tmp_path / "spec", _module_yaml(extra_lines=f"  short_description: {_SUBTITLE}\n")
    )
    refused = validate_spec(spec)
    assert not refused.valid
    assert any("short_description" in e for e in refused.errors)
    identity = validate_spec(_write_spec(tmp_path / "id", _module_yaml(extra_lines=_LEGACY_IDENTITY)))
    assert not identity.valid
    # The identity family earns a named reason and a way out; this one does not, yet.
    assert any("strip_authority_keys" in e for e in identity.errors)
    assert not any("strip_authority_keys" in e for e in refused.errors), (
        "if this now fails, a specific diagnosis was added — assert its reason text here instead"
    )

    accepted = validate_spec(spec, authority_keys=PRESENTATION_AUTHORITY_KEYS)
    assert accepted.valid, accepted.errors
    assert any("short_description" in i for i in accepted.info)


def test_the_two_families_compose_in_one_injected_set(tmp_path: Path) -> None:
    """One stripper, both families, and a near-miss of either still refused.

    A registry stamps identity *and* presentation, so the realistic injection is the union — and the
    strip has to stay exact across it, or the set would be a licence to drop whatever a spec happens
    to carry.
    """
    both = IDENTITY_AUTHORITY_KEYS | PRESENTATION_AUTHORITY_KEYS
    spec = _write_spec(
        tmp_path / "spec",
        _module_yaml(extra_lines=_LEGACY_IDENTITY + f"  short_description: {_SUBTITLE}\n"),
    )
    result = validate_spec(spec, authority_keys=both)
    assert result.valid, result.errors
    joined = " ".join(result.info)
    assert all(key in joined for key in sorted(both))

    typo = _write_spec(
        tmp_path / "typo", _module_yaml(extra_lines="  short_descripton: too short\n")
    )
    assert not validate_spec(typo, authority_keys=both).valid


def test_the_published_ceiling_bounds_the_registry_value_and_nothing_authored(
    tmp_path: Path,
) -> None:
    """~120 characters is a calibration the registry can read off us, not a refusal we make.

    The subtitle that prompted the item was 467 characters of `module.description`, and that spec
    still compiles untouched: bounding the authored field would refuse a merely verbose module after
    its prose was written. What the constant bounds is the new value stored beside the module.
    """
    assert len(_SUBTITLE) <= SHORT_DESCRIPTION_MAX_CHARS
    long_prose = ("Iron overload, " * 32).strip()  # the shape of the 467-character case
    assert len(long_prose) > SHORT_DESCRIPTION_MAX_CHARS * 3
    spec = _write_spec(
        tmp_path / "spec",
        _module_yaml().replace("description: A demo module", f"description: {long_prose}"),
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    assert load_spec(spec / "module_spec.yaml").module.description == long_prose
