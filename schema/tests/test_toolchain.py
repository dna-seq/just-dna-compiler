"""RM342: `compilation.toolchain` and the three-valued comparison every digest reader shares.

The publish collision check and the release sweep both ask one question of two manifests: were they
written by different toolchains? The answer is tri-state, and an older manifest that recorded nothing is
the unknown arm, never a "same".
"""

from typing import Any

import pytest
from just_dna_format.manifest import (
    Compilation,
    ModuleManifest,
    recorded_toolchain,
    toolchains_differ,
)


def _manifest(toolchain: Any) -> dict[str, Any]:
    compilation: dict[str, Any] = {"compiler_version": "just-dna-compiler 0.8.0"}
    if toolchain is not None:
        compilation["toolchain"] = toolchain
    return {"compilation": compilation}


_A = {"polars": "2.1.0", "python": "3.13.1"}


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (_A, _A, False),
        (_A, {**_A, "polars": "1.39.0"}, True),
        (_A, {**_A, "python": "3.12.0"}, True),
        # Either side unrecorded: a manifest compiled before 0.8.
        (None, _A, None),
        (_A, None, None),
        (None, None, None),
        # A library one side names and the other does not is absent, never different...
        (_A, {**_A, "pyarrow": "18.0.0"}, None),
        # ...but a shared library at two releases is a difference whatever else is unknown (Kleene).
        ({**_A, "polars": "1.39.0"}, {**_A, "pyarrow": "18.0.0"}, True),
        # Present and not a map of strings reads as not recorded.
        ({}, _A, None),
        ({"polars": 2}, _A, None),
        ("polars 2.1.0", _A, None),
    ],
)
def test_toolchains_differ_is_three_valued(before: Any, after: Any, expected: bool | None) -> None:
    assert toolchains_differ(_manifest(before), _manifest(after)) is expected


def test_a_manifest_that_is_not_a_mapping_records_no_toolchain() -> None:
    assert recorded_toolchain(None) is None
    assert recorded_toolchain({"compilation": None}) is None
    assert toolchains_differ(None, _manifest(_A)) is None


def test_an_older_manifest_reads_with_no_toolchain_and_a_new_one_round_trips_it() -> None:
    """Optional and additive: a manifest without the key parses as `None`, and one with it survives
    a JSON round trip unchanged."""
    assert Compilation().toolchain is None
    base = {
        "identity": {"name": "rm342"},
        "display": {"title": "t", "description": "d", "report_title": "r"},
        "artifact": {"digest": "sha256:" + "0" * 64},
    }
    old = ModuleManifest.model_validate(base)
    assert old.compilation.toolchain is None

    new = ModuleManifest.model_validate({**base, "compilation": {"toolchain": _A}})
    again = ModuleManifest.model_validate_json(new.model_dump_json())
    assert again.compilation.toolchain == _A
    assert recorded_toolchain(again.model_dump(mode="json")) == _A
