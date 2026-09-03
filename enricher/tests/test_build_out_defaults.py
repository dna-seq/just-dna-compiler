"""No command writes into the repository root when the operator names nowhere.

The rule is old and it was in prose: *"Nothing a command generates goes in the repository root"*, filed
after `civic reproduce` wrote `civic-reproduce/` there and needed its own `.gitignore` line to say so.
Prose did not hold. Nine `--out` defaults were bare relative names — `civic`, `clinvar`, `pubmind`,
`gnomad_constraint`, `mane`, `strchive`, `acmg_sf`, `mitomap`, `mitomap_miss` — so running any builder
from a checkout dropped a snapshot directory beside `pyproject.toml`, and four more builders required
`--out` with no default at all, which is how the docs came to tell an operator to write `--out
./clinpgx` into the repo root.

**Walked, never listed** (`@registry-completeness`). The guard reads the CLI's own syntax tree and
finds every `typer.Option` bound to `--out`, so a builder added next year is in the set the day it is
written. Asserting a floor ("at least nine are under data/") would pass forever while the tenth
command wrote wherever it liked; the assertion is an equality over what the walk found.
"""

import ast
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher" / "cli.py"

#: `--out` on a command that names an **input** rather than a destination. One entry, and it carries
#: its reason: `clinvar citations` is handed a snapshot that already exists and adds a sidecar to it,
#: so there is nothing to default to and requiring the path is correct.
INPUT_SHAPED_OUT: frozenset[str] = frozenset({"clinvar_citations_"})


def _out_options() -> dict[str, ast.expr]:
    """`{function name: the default expression}` for every `--out` option the CLI declares."""
    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    found: dict[str, ast.expr] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for arg, default in zip(
            node.args.args[len(node.args.args) - len(node.args.defaults) :],
            node.args.defaults,
            strict=True,
        ):
            if not (
                isinstance(default, ast.Call)
                and isinstance(default.func, ast.Attribute)
                and default.func.attr == "Option"
            ):
                continue
            flags = [a.value for a in default.args if isinstance(a, ast.Constant)]
            if "--out" in flags and arg.arg in {"out", "out_dir"}:
                found[node.name] = default.args[0] if default.args else ast.Constant(None)
    return found


def test_every_out_default_is_derived_rather_than_written_as_a_literal():
    """A destination default comes from `repro_out`, which is the only place the rule is spelled.

    A literal is what let nine of these drift: each builder wrote its own, and the one that was
    corrected (`civic reproduce`) stayed corrected while every new sibling repeated the defect.
    """
    options = _out_options()
    assert options, "the walk found no --out options at all, so it is not walking the CLI"

    literals = {}
    for name, default in options.items():
        if name in INPUT_SHAPED_OUT:
            continue
        derived = isinstance(default, ast.Call) and (
            # `repro_out("civic")` — a builder's destination.
            (isinstance(default.func, ast.Name) and default.func.id == "repro_out")
            # `Path(CACHES_DIRNAME)` — a named constant from `locations`, not a path spelled here.
            or (
                isinstance(default.func, ast.Name)
                and default.func.id == "Path"
                and default.args
                and isinstance(default.args[0], ast.Name)
            )
        )
        if not derived:
            literals[name] = ast.unparse(default)
    assert literals == {}, (
        f"these --out defaults spell a path inline instead of naming one from `locations`: {literals}"
    )


def test_the_input_shaped_exemptions_are_exactly_the_ones_named():
    """The exemption list is asserted as an equality, so it cannot quietly grow.

    A command that requires `--out` because it names an existing directory is legitimate. A command
    that requires it because nobody chose a default is the defect this file exists for, and the two
    are indistinguishable from the option alone — so the exemptions are enumerated and checked.
    """
    options = _out_options()
    required = {
        name
        for name, default in options.items()
        if isinstance(default, ast.Constant) and default.value is Ellipsis
    }
    assert required == INPUT_SHAPED_OUT


def test_repro_out_lands_under_the_ignored_data_tree():
    """`/data/` is git-ignored whole, which is why a default under it needs no `.gitignore` line."""
    from just_dna_enricher.locations import REPRO_DIRNAME, repro_out

    assert repro_out("anything").parts[0] == "data"
    assert REPRO_DIRNAME.startswith("data/")
    ignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    assert "/data/" in ignore.split("\n"), "the tree these defaults write into must stay ignored"
