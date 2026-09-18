"""A published wheel's intra-workspace floor must name the version of the tier it imports.

`uv.lock` records the intra-workspace edges as *editable* with no specifier, so a checkout is right
whatever the `pyproject.toml` files say — the floors are load-bearing only in the wheels, which is
exactly where nobody looks. That is how `0.7.0` came to import `just_dna_format.overrides` (a module
0.6.6 does not have) while declaring `just-dna-format>=0.6.6`: a `pip install
just-dna-compiler==0.7.0` beside a resident 0.6.6 resolves, then dies at import.

**The rule is `floor == the dependency's current version`, and it was `floor == my own version`
until 2026-09-19.** Those coincide only while all three packages move together, and this project does
not always move them together: `v0.6.3` and `v0.6.4` were **enricher-only patches**, with
`just-dna-format` and `just-dna-compiler` left at `0.6.1` and the enricher declaring
`just-dna-format>=0.6.1` — the floor naming its dependency, correctly. The guard was written the day
a floor-lag incident was repaired and took the cadence of the three cuts before it for an invariant,
which also carried a `test_every_member_carries_the_same_version` that outlawed a shape this
repository had already shipped twice. The restated rule catches the original incident exactly as well
— `format` is at `0.7.0`, `compiler` declares `>=0.6.6`, the floor names a version its dependency is
not at — and costs nothing when a single tier is patched alone.

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


def test_an_intra_workspace_floor_names_its_dependencys_current_version():
    """A wheel's floor is the only thing standing between a consumer and an ImportError.

    The edges are discovered from the dependency lists rather than enumerated, so `enricher ->
    compiler` is covered by the same walk that covers `compiler -> format`.

    The expected value is the **dependency's** version, never the depender's. A tier patched on its
    own keeps importing the tier below at the version that tier is actually at, and pinning the floor
    to the depender's number would name a release nobody cut.
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
    expected = {edge: projects[edge[1]]["project"]["version"] for edge in edges}
    assert edges == expected, (
        "an intra-workspace floor does not name its dependency's current version, so a published "
        "wheel would accept a dependency older than the modules it imports"
    )
