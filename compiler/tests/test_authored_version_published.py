"""The authored `module.version` reaches the artifact, and survives its own round trip (RM103).

`normalize_version` strips every non-digit and pads to three zeros, so `version: abc` becomes
`"0.0.0"` — documented in its own docstring and pinned by a test, deliberate since RM17. The coercion
is not in question here and must not be undone: the pre-0.4 corpus is full of `v2` and `3`, and 0.6
widened it after **26 of 61** foreign modules refused on an unquoted integer.

What was in question is the *digitless* case, where there is no authorial intent to read and the
function invents one. `0.0.0` is a legal SemVer and a plausible pre-release marker, so an unreadable
string became a confident claim in `manifest.identity.version` with nothing beside it recording that
the author wrote `abc`. The compiler warned, naming both values — but a warning lives in a build log
somebody had to have kept, and the artifact is what a consumer holds.

**A sentinel was rejected and stays rejected**: every three-number string is somebody's real version,
so there is nothing to coerce *to* that could not be mistaken for one. Publishing what was read is the
only honest repair, and it is purely additive.
"""

from pathlib import Path

import pytest
import yaml
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_format.spec import ModuleInfo

_MODULE = {
    "name": "vtest",
    "title": "V Test",
    "description": "a module for the version question",
    "report_title": "V Test",
}

#: Authored spelling → the SemVer it coerces to. Every digit-bearing case is RM17 working as intended
#: and is here to pin that this item changed none of them; `abc` is the one the item is about.
_COERCED: dict[str, str] = {
    "v2": "2.0.0",
    "3": "3.0.0",
    "1.5": "1.5.0",
    "v1.2.3-beta": "1.2.3",
    "abc": "0.0.0",
}


def _spec(tmp_path: Path, version: str | None) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    module = dict(_MODULE)
    if version is not None:
        module["version"] = version
    (spec / "module_spec.yaml").write_text(
        yaml.dump(
            {
                "schema_version": "1.0",
                "module": module,
                "defaults": {"curator": "test", "method": "manual"},
                "genome_build": "GRCh38",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs1801133,C/T,risk,example,MTHFR\n", encoding="utf-8"
    )
    # Mandatory: grounding evidence is not optional, and a compile refuses without it.
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,12345678\n", encoding="utf-8")
    return spec


# ── the model still does exactly what RM17 decided ──────────────────────────────────────────────


@pytest.mark.parametrize("authored,coerced", sorted(_COERCED.items()))
def test_the_coercion_itself_is_unchanged(authored: str, coerced: str) -> None:
    """The half this item deliberately did not touch. Undoing it would break the corpus RM17 saved."""
    info = ModuleInfo(**_MODULE, version=authored)
    assert info.version == coerced
    assert info.version_coerced_from == authored


def test_an_already_canonical_version_records_no_coercion() -> None:
    """`None` is the honest answer, not the string repeated — absence means nothing was rewritten."""
    assert ModuleInfo(**_MODULE, version="1.2.3").version_coerced_from is None


# ── and the artifact now says so ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("authored,coerced", sorted(_COERCED.items()))
def test_the_manifest_publishes_what_the_author_wrote(
    tmp_path: Path, authored: str, coerced: str
) -> None:
    """The whole additive ask: the fabrication is auditable in the artifact, not only in a build log.

    Asserted against `identity.version` in the same breath, because the claim is that the two cells
    stand *beside* each other — publishing the authored string alone would answer a different
    question, and replacing the coerced one would be the refusal this item split away.
    """
    result = compile_module(_spec(tmp_path, authored), tmp_path / "out")
    assert result.success, result.errors

    identity = result.manifest.identity
    assert identity.version == coerced
    assert identity.version_coerced_from == authored


def test_a_canonical_version_leaves_the_new_field_absent(tmp_path: Path) -> None:
    """It must not become a duplicate of `version` — absent has to mean *nothing was invented*."""
    result = compile_module(_spec(tmp_path, "1.2.3"), tmp_path / "out")
    assert result.success, result.errors
    assert result.manifest.identity.version == "1.2.3"
    assert result.manifest.identity.version_coerced_from is None


def test_an_unversioned_module_publishes_neither(tmp_path: Path) -> None:
    result = compile_module(_spec(tmp_path, None), tmp_path / "out")
    assert result.success, result.errors
    assert result.manifest.identity.version is None
    assert result.manifest.identity.version_coerced_from is None


def test_the_compiler_still_warns_naming_both_values(tmp_path: Path) -> None:
    """The build-log half is not replaced by the manifest half; both say the same thing."""
    result = compile_module(_spec(tmp_path, "abc"), tmp_path / "out")
    assert result.success, result.errors
    assert any("'abc'" in w and "'0.0.0'" in w for w in result.manifest.compilation.warnings)


# ── the round trip, which is where this could have gone wrong ───────────────────────────────────


@pytest.mark.parametrize("authored", sorted(_COERCED))
def test_the_published_field_is_a_fixed_point_across_the_round_trip(
    tmp_path: Path, authored: str
) -> None:
    """The defect this item could have shipped, in the same release as the item filed about it.

    `reverse_module` takes its `version` from the caller, who has `manifest.identity.version` — the
    **coerced** string. Lap 2 then has nothing to coerce, `version_coerced_from` comes back absent,
    and a module disagrees with its own round trip on a published field: exactly RM137's shape.
    Reverse therefore re-emits the *authored* spelling, and both cells hold on both laps.
    """
    first = compile_module(_spec(tmp_path, authored), tmp_path / "a1")
    assert first.success, first.errors

    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    second = compile_module(tmp_path / "rev1", tmp_path / "a2")
    assert second.success, second.errors

    assert second.manifest.identity.version == first.manifest.identity.version
    assert (
        second.manifest.identity.version_coerced_from
        == first.manifest.identity.version_coerced_from
        == authored
    )

    # A second lap, for the reason the reference-example round trip runs one: "recompiles" and "is a
    # fixed point" are different claims, and a transform can settle only from the second iteration.
    reverse_module(tmp_path / "a2", tmp_path / "rev2")
    third = compile_module(tmp_path / "rev2", tmp_path / "a3")
    assert third.success, third.errors
    assert third.manifest.identity.version_coerced_from == authored


def test_reverse_now_carries_an_ordinary_version_it_used_to_drop(tmp_path: Path) -> None:
    """The quieter loss the same change repairs, stated as its own claim.

    Reverse emitted no `version:` at all unless a caller supplied one, so even a perfectly canonical
    authored version did not survive a round trip. Nothing hashed on it, which is why it went
    unnoticed — `module.version` is advisory and out of `artifact.digest`.
    """
    compile_module(_spec(tmp_path, "1.2.3"), tmp_path / "a1")
    reverse_module(tmp_path / "a1", tmp_path / "rev")

    block = yaml.safe_load((tmp_path / "rev" / "module_spec.yaml").read_text())["module"]

    assert block["version"] == "1.2.3"


def test_an_explicit_argument_still_beats_the_artifact(tmp_path: Path) -> None:
    """Recovery is a fallback, never an override — the caller's own value is the one that wins."""
    compile_module(_spec(tmp_path, "abc"), tmp_path / "a1")
    reverse_module(tmp_path / "a1", tmp_path / "rev", version="9.9.9")

    block = yaml.safe_load((tmp_path / "rev" / "module_spec.yaml").read_text())["module"]

    assert block["version"] == "9.9.9"


def test_a_bare_parquet_directory_still_leaves_the_key_out(tmp_path: Path) -> None:
    """Recover it or say nothing: reverse may not invent a version any more than it may a build."""
    compile_module(_spec(tmp_path, "abc"), tmp_path / "a1")
    (tmp_path / "a1" / "manifest.json").unlink()
    reverse_module(tmp_path / "a1", tmp_path / "rev")

    block = yaml.safe_load((tmp_path / "rev" / "module_spec.yaml").read_text())["module"]

    assert "version" not in block
