"""`reverse_module` writes back every `module_spec.yaml` field the artifact carries (RM241).

The corpus sweep in `test_reference_examples_roundtrip.py` compares the manifest's authored projection
across laps, but the corpus sets `weighting`, `license` and `authorship` once each and `panel` and
`authority_precedence` nowhere, so a field no example uses would pass it by never being exercised.
This file sets every one of them on a copy of a real example, and walks the spec models so a field
added later has to be placed on one side of the registry before the suite goes green.
"""

import shutil
from pathlib import Path

import yaml
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.compiler.reverse import REVERSE_EXCLUDED, REVERSE_RECONSTRUCTED
from just_dna_format.integrity import sha256_file
from just_dna_format.spec import Defaults, ModuleInfo, ModuleSpecConfig

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"


def _walked_spec_fields() -> set[str]:
    """Every field of the spec's top level and of its two nested blocks, as dotted paths."""
    fields = set(ModuleSpecConfig.model_fields)
    fields |= {f"module.{name}" for name in ModuleInfo.model_fields}
    fields |= {f"defaults.{name}" for name in Defaults.model_fields}
    return fields


def test_every_spec_field_is_either_reconstructed_or_excluded_with_a_reason() -> None:
    walked = _walked_spec_fields()
    assert walked == REVERSE_RECONSTRUCTED | set(REVERSE_EXCLUDED)
    assert not REVERSE_RECONSTRUCTED & set(REVERSE_EXCLUDED)
    assert all(len(reason.split()) >= 5 for reason in REVERSE_EXCLUDED.values())


def _every_field_spec(tmp_path: Path) -> Path:
    """A copy of a real example with every optional spec field set, none to its default."""
    spec_dir = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, spec_dir)
    spec = yaml.safe_load((spec_dir / "module_spec.yaml").read_text(encoding="utf-8"))
    spec["module"].update(
        {
            "version": "v2",  # informal, so `version_coerced_from` is exercised too
            "icon": "flask",
            "icon_set": "awesome",
            "color": "#123abc",
        }
    )
    spec["defaults"] = {"curator": "a-named-curator", "method": "expert-panel"}
    spec["license"] = "CC-BY-4.0"
    spec["authorship"] = [
        {"who": "A Curator", "role": "created", "kind": ["human"], "at": "2026-09-30"},
        {"who": "an-agent", "role": "edited", "kind": ["ai"]},
    ]
    spec["authority_precedence"] = ["clinvar", "pubmind"]
    spec["panel"] = {
        "source": "clinvar",
        "reference": "2026-06",
        "genes": ["HFE"],
        "significance": ["pathogenic", "likely_pathogenic"],
    }
    (spec_dir / "module_spec.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    return spec_dir


def _projection(manifest) -> dict[str, object]:
    return {
        "display": manifest.display.model_dump(),
        "genome_build": manifest.genome_build,
        "version": (manifest.identity.version, manifest.identity.version_coerced_from),
        "curator": manifest.curator,
        "method": manifest.method,
        "license": manifest.license,
        "weighting": manifest.weighting.model_dump() if manifest.weighting else None,
        "authorship": [entry.model_dump() for entry in manifest.authorship],
        "authority_precedence": list(manifest.authority_precedence),
        "panel": manifest.panel.model_dump() if manifest.panel else None,
        "readme": (manifest.readme.name, manifest.readme.sha256) if manifest.readme else None,
    }


def test_every_authored_field_survives_two_laps(tmp_path: Path) -> None:
    spec_dir = _every_field_spec(tmp_path)
    first = compile_module(spec_dir, tmp_path / "a1")
    assert first.success, first.errors
    # The fixture really does set everything, or the comparison below proves nothing about it.
    projection = _projection(first.manifest)
    assert all(value not in (None, [], (None, None)) for value in projection.values()), projection

    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    second = compile_module(tmp_path / "rev1", tmp_path / "a2")
    assert second.success, second.errors
    reverse_module(tmp_path / "a2", tmp_path / "rev2")
    third = compile_module(tmp_path / "rev2", tmp_path / "a3")
    assert third.success, third.errors

    assert _projection(second.manifest) == projection
    assert _projection(third.manifest) == projection
    for later in (second, third):
        assert later.manifest.artifact.digest == first.manifest.artifact.digest
        assert later.manifest.content_signature == first.manifest.content_signature


def test_the_readme_is_copied_byte_for_byte_and_matches_its_record(tmp_path: Path) -> None:
    compiled = compile_module(_EXAMPLE, tmp_path / "a1")
    assert compiled.success, compiled.errors
    record = compiled.manifest.readme
    assert record is not None

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    copied = tmp_path / "rev" / record.name
    assert copied.read_bytes() == (_EXAMPLE / record.name).read_bytes()
    assert sha256_file(copied) == record.sha256


def test_a_readme_that_disagrees_with_its_record_is_not_copied(tmp_path: Path) -> None:
    compiled = compile_module(_EXAMPLE, tmp_path / "a1")
    assert compiled.success, compiled.errors
    record = compiled.manifest.readme
    assert record is not None
    shipped = tmp_path / "a1" / record.name
    shipped.write_text(shipped.read_text(encoding="utf-8") + "\nedited after the compile\n", encoding="utf-8")

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert not (tmp_path / "rev" / record.name).exists()


def test_an_explicit_argument_still_wins_over_the_manifest(tmp_path: Path) -> None:
    compiled = compile_module(_EXAMPLE, tmp_path / "a1")
    assert compiled.success, compiled.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev", title="Another title", icon="star", color="#000000")
    module = yaml.safe_load((tmp_path / "rev" / "module_spec.yaml").read_text(encoding="utf-8"))["module"]
    assert (module["title"], module["icon"], module["color"]) == ("Another title", "star", "#000000")
    # Everything not passed still comes from the manifest, not from the name-derived fallback.
    assert module["description"] == compiled.manifest.display.description


def test_a_bare_parquet_directory_keeps_the_old_fallbacks(tmp_path: Path) -> None:
    compiled = compile_module(_EXAMPLE, tmp_path / "a1")
    assert compiled.success, compiled.errors
    (tmp_path / "a1" / "manifest.json").unlink()

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    spec = yaml.safe_load((tmp_path / "rev" / "module_spec.yaml").read_text(encoding="utf-8"))
    name = spec["module"]["name"]
    assert spec["module"]["title"] == name.replace("_", " ").title()
    assert (spec["module"]["icon"], spec["module"]["color"]) == ("database", "#6435c9")
    assert "icon_set" not in spec["module"]
    assert not {"license", "weighting", "authorship", "authority_precedence", "panel"} & set(spec)
