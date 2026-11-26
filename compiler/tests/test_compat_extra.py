"""The `compat` extras pull polars' compatibility runtime at the core polars floor (0.9.0).

A host without the CPU features polars' default runtime needs installs `just-dna-compiler[compat]` or
`just-dna-enricher[compat]`. The compiler's extra is `polars[rtcompat]` at the same floor as its core
`polars` dependency, and the enricher's extra is the compiler's, so one number is written twice and held
equal here rather than remembered.
"""

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

_ROOT = Path(__file__).resolve().parents[2]


def _project(package: str) -> dict:
    return tomllib.loads((_ROOT / package / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _named(requirements: list[str], name: str) -> Requirement:
    found = [Requirement(r) for r in requirements if Requirement(r).name == name]
    assert len(found) == 1, f"expected one {name} requirement, found {found}"
    return found[0]


def test_the_compilers_compat_extra_is_polars_rtcompat_at_the_core_floor() -> None:
    project = _project("compiler")
    core = _named(project["dependencies"], "polars")
    compat = _named(project["optional-dependencies"]["compat"], "polars")
    assert compat.extras == {"rtcompat"}
    assert compat.specifier == core.specifier


def test_the_enrichers_compat_extra_is_the_compilers() -> None:
    enricher = _project("enricher")
    compat = _named(enricher["optional-dependencies"]["compat"], "just-dna-compiler")
    assert compat.extras == {"compat"}
    assert compat.specifier == _named(enricher["dependencies"], "just-dna-compiler").specifier
