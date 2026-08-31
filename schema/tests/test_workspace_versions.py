"""The three packages version together, and a published wheel must say so.

`just-dna-format`, `just-dna-compiler` and `just-dna-enricher` are cut as one number, and each tier
imports the one below it. `uv.lock` records the intra-workspace edges as *editable* with no
specifier, so a checkout is right whatever the `pyproject.toml` files say — the floors are load-
bearing only in the wheels, which is exactly where nobody looks. That is how `0.7.0` came to import
`just_dna_format.overrides` (a module 0.6.6 does not have) while declaring `just-dna-format>=0.6.6`:
a `pip install just-dna-compiler==0.7.0` beside a resident 0.6.6 resolves, then dies at import.

Asserted as an equality over the walked workspace rather than as a floor check per package
(`@registry-completeness`): a fourth member, or a fourth edge between existing ones, joins the guard
by existing instead of by somebody remembering to add a line.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: Read from the workspace table, never listed here — a new member must not be able to slip the guard.
MEMBERS: tuple[str, ...] = tuple(
    tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"]
)
_REQUIREMENT = re.compile(r"^\s*(?P<name>[A-Za-z0-9._-]+)\s*(?P<op>[<>=!~]+)\s*(?P<version>[^,;\s]+)")


def _projects() -> dict[str, dict]:
    """`distribution name -> parsed pyproject`, for every workspace member."""
    parsed = {}
    for member in MEMBERS:
        data = tomllib.loads((ROOT / member / "pyproject.toml").read_text())
        parsed[data["project"]["name"]] = data
    return parsed


def test_every_member_carries_the_same_version():
    """One cut, one number. Three packages that version independently would need three records."""
    versions = {name: data["project"]["version"] for name, data in _projects().items()}
    assert len(set(versions.values())) == 1, f"the workspace is mid-bump or split: {versions}"


def test_an_intra_workspace_floor_names_the_version_being_cut():
    """A wheel's floor is the only thing standing between a consumer and an ImportError.

    The edges are discovered from the dependency lists rather than enumerated, so `enricher ->
    compiler` is covered by the same walk that covers `compiler -> format`.
    """
    projects = _projects()
    edges: dict[tuple[str, str], str] = {}
    for name, data in projects.items():
        for requirement in data["project"].get("dependencies", []):
            match = _REQUIREMENT.match(requirement)
            assert match is not None, f"{name} declares an unparsable requirement: {requirement!r}"
            if match["name"] in projects:
                assert match["op"] == ">=", (
                    f"{name} pins {match['name']} with {match['op']!r}; the house spelling is a "
                    f">= floor moved with the cut"
                )
                edges[(name, match["name"])] = match["version"]

    assert edges, "no intra-workspace dependency found; the walk is reading the wrong files"
    expected = {edge: projects[edge[0]]["project"]["version"] for edge in edges}
    assert edges == expected, (
        "an intra-workspace floor lags the version being cut, so a published wheel would accept a "
        "dependency older than the modules it imports"
    )
