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

import ast
import re
import subprocess
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


def _modules_at(tag: str, member: str, top: str) -> set[str] | None:
    """Every importable module of `top` as that git tag has it, or `None` if the tag does not exist."""
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", tag, f"{member}/src/{top}/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if listing.returncode != 0:
        return None
    prefix = f"src/{top}/"
    return {
        path.split(prefix, 1)[1][: -len(".py")].replace("/", ".")
        for path in listing.stdout.split()
        if path.endswith(".py")
    }


def test_a_cross_tier_import_exists_in_the_version_its_floor_names() -> None:
    """The floor must name a release that actually contains the modules this tier imports from it.

    **The floor rule above is necessary and not sufficient, and this is the test that says so.** It
    compares a declaration against the *local tree*, where every module exists by construction; it
    cannot see that `just_dna_enricher.resolver` imports `just_dna_compiler.resolution_findings`, a
    module RM244 created after `0.7.0` was published, while the floor says `>=0.7.0`. Caught by
    installing the wheel into a clean venv and importing it — `ModuleNotFoundError` — which is the
    same failure the floor rule was written for (`0.7.0`'s compiler importing
    `just_dna_format.overrides` under a `>=0.6.6` floor) arriving by a route that rule does not watch.

    A floor naming the dependency's **current** version is vacuous here: the two are being cut
    together and the tree is the truth. A floor naming an **older** release is a claim about a
    published artifact, so it is checked against that artifact — `git ls-tree` at the tag, which is
    the same trick `docs/` uses to read a release boundary off a tag rather than off a date.
    """
    projects = _projects()
    tops = {"just-dna-format": "just_dna_format", "just-dna-compiler": "just_dna_compiler"}
    members = {
        tomllib.loads((ROOT / member / "pyproject.toml").read_text(encoding="utf-8"))["project"][
            "name"
        ]: member
        for member in MEMBERS
    }
    problems: list[str] = []
    for name, data in projects.items():
        top = tops.get(name) or f"just_dna_{name.rsplit('-', 1)[-1]}"
        for requirement in data["project"].get("dependencies", []):
            match = _REQUIREMENT.match(requirement)
            if match is None or match["name"] not in projects:
                continue
            dependency, floor = match["name"], match["version"]
            published = _modules_at(f"v{floor}", members[dependency], tops[dependency])
            if published is None:
                # No such tag: the floor names a version being cut in this very commit, which is the
                # one case where the tree IS the artifact. Deliberately not extended to "the floor
                # equals the dependency's current version" — that was the first cut of this test and
                # it skipped the exact defect it was written for, because the compiler sat at 0.7.0
                # locally with two modules added since the v0.7.0 tag.
                continue
            source = ROOT / members[name] / "src" / top
            for module_file in sorted(source.rglob("*.py")):
                tree = ast.parse(module_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ImportFrom) or not node.module:
                        continue
                    wanted = tops[dependency]
                    if not node.module.startswith(wanted + "."):
                        continue
                    if node.module.split(wanted + ".", 1)[1] not in published:
                        problems.append(
                            f"{module_file.name}:{node.lineno} imports {node.module}, absent from "
                            f"{dependency} {floor} — the floor {name} declares"
                        )
    assert not problems, "\n".join(sorted(set(problems)))
