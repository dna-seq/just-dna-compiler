"""Every pass that writes a sidecar resolves its path the same way (RM99).

`@sidecar-name-and-place`: resolve a sidecar's name and place through the resolver, and **write to the
file you read**. RM49 shipped `licensing.sidecar_path` for exactly this, and nine `sources.csv`
writers were converted to it in one go. Three passes then kept their own `spec_dir / "<name>.csv"`
literal -- `gene_metrics`, `clingen` and `literature` -- so on a module keeping its sidecars under
`derived/` they wrote at the root while six other passes wrote under `derived/`, which is the
both-copies-present collision RM49 made an *error* rather than a preference.

The sharp part is that it was inconsistent **inside one family**: `gene_validity` -- `gene_metrics`'
sibling, sharing `module_genes` -- did use the resolver. And `gene_metrics` and `clingen` write the
*same file*, both read-merge-write, so one `enrich` run on one module produced two copies that each
dropped the other authority's rows.

So this file does not test three passes. Per-pass repair leaves the next pass free to make the same
choice, and the next pass is the one nobody is looking at -- these three were written after the rule
was. What it tests is that a pass **cannot** write outside the layout the module already has.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from just_dna_compiler.compiler import _FACT_TABLES
from just_dna_enricher.producers import DERIVED_PRODUCERS, WRITTEN_BY_EVERY_PASS
from just_dna_format.layout import sidecar_spellings, sidecar_write_path

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: split\n  title: Split\n  description: d\n  report_title: Split\n"
)

#: Every machine-written sidecar a pass may create, and the pass(es) that own it — **derived** from
#: `DERIVED_PRODUCERS` and `WRITTEN_BY_EVERY_PASS` (RM365). This was a hand-kept dict that had fallen
#: seven derived tables behind (the concordance pair, `expression_effects`, the Open Targets three and
#: `ld_pairs`) while its comment said it came from the layout module: the AST guard below checks only
#: the names in it, so a hand-joined `spec_dir / "ld_pairs.csv"` was invisible to the rule this file
#: exists to enforce.
SIDECAR_OWNERS: dict[str, str] = {
    **{csv: " + ".join(p.command for p in group) for csv, group in DERIVED_PRODUCERS.items()},
    **{
        spelling: "every pass that consults a source"
        for name in WRITTEN_BY_EVERY_PASS
        for spelling in sidecar_spellings(name)
    },
}


@pytest.fixture
def split_spec(tmp_path: Path) -> Path:
    """A module carrying its sidecars under `derived/` — the layout RM49 tolerates."""
    spec = tmp_path / "spec"
    (spec / "derived").mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs1801133,C/T,risk,x,MTHFR\n", encoding="utf-8"
    )
    # One file per TABLE, not per spelling: `sources.csv` and `licensing.csv` are two names for one
    # table (RM51), and creating both is the collision RM49 calls an error — which the resolver
    # correctly raises on. Creating only the preferred spelling is also the sharper fixture, since it
    # makes the parametrized case for `sources.csv` below prove that the deprecated name resolves to
    # the file the module actually has.
    for name in SIDECAR_OWNERS:
        if name == "sources.csv":
            continue
        (spec / "derived" / name).touch()
    return spec


def test_no_pass_joins_a_sidecar_filename_onto_spec_dir_by_hand() -> None:
    """The guard that reads the source, because it is the only one that scales to the next pass.

    A behavioural test needs a runnable pass per sidecar, and the passes that fetch are the ones this
    rule keeps being broken in. Reading for the literal costs nothing and covers every pass at once,
    including ones added after this file.
    """
    #: The one documented exception, named rather than pattern-matched away. `check_gene_loci` READS
    #: the table and falls back to the flat path only to have something to report as missing; it
    #: writes nothing, so it cannot produce the both-copies collision this rule exists to prevent.
    #: Its own comment says so. Listing it here means removing that fallback is a deliberate edit.
    read_only_fallbacks = {"identifiers.py"}

    src = Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher"
    offenders: list[str] = []
    # Recursive since RM260 split `cli.py` into a package; `generated/` is protoc output, not ours.
    for module in sorted(p for p in src.rglob("*.py") if "generated" not in p.relative_to(src).parts):
        if module.name in read_only_fallbacks:
            continue
        source = ast.parse(module.read_text(encoding="utf-8"))
        # Walked as an AST rather than line by line, so a filename inside a docstring or a comment --
        # `licensing.py` records the nine passes it converted, in prose -- is not a false positive.
        for node in ast.walk(source):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
                continue
            left, right = node.left, node.right
            if not (isinstance(left, ast.Name) and left.id == "spec_dir"):
                continue
            if isinstance(right, ast.Constant) and right.value in SIDECAR_OWNERS:
                offenders.append(f"{module.name}:{node.lineno}: spec_dir / {right.value!r}")
    assert offenders == [], (
        "a sidecar path joined by hand — use `licensing.sidecar_path`, which follows the layout the "
        "module already has (RM49/RM99):\n" + "\n".join(offenders)
    )


def test_the_roster_covers_every_writable_sidecar() -> None:
    """Guard the premise: the roster above is exactly the derived tables and the licence table's
    spellings — an equality (RM365), where a `>=` against the layout's spelled sidecars alone held
    while seven derived tables were missing from it."""
    derived = {csv for csv, _parquet, _model in _FACT_TABLES} | {"resolution.csv"}
    licence = {spelling for name in WRITTEN_BY_EVERY_PASS for spelling in sidecar_spellings(name)}
    assert set(SIDECAR_OWNERS) == derived | licence, sorted(set(SIDECAR_OWNERS) ^ (derived | licence))


@pytest.mark.parametrize("name", sorted(SIDECAR_OWNERS), ids=sorted(SIDECAR_OWNERS))
def test_the_resolver_follows_a_split_module_for_every_sidecar(split_spec: Path, name: str) -> None:
    """And the behavioural half: the resolver these passes now call really does follow `derived/`.

    Without this, the source-level guard above would be satisfied by a pass calling a resolver that
    did the wrong thing — the literal is the symptom, and this is the rule it was violating.
    """
    resolved = sidecar_write_path(split_spec, name)
    assert resolved.parent.name == "derived", f"{name} would be written outside the module's layout"
    assert resolved.exists(), "write to the file you read"


@pytest.mark.parametrize("name", sorted(SIDECAR_OWNERS), ids=sorted(SIDECAR_OWNERS))
def test_a_flat_module_still_gets_the_flat_path(tmp_path: Path, name: str) -> None:
    """Negative control: `derived/` is tolerated, not canonical, so a module with nothing to follow
    keeps the flat layout. Without this the test above would pass on a resolver that always split."""
    spec = tmp_path / "flat"
    spec.mkdir()
    resolved = sidecar_write_path(spec, name)
    assert resolved.parent == spec
