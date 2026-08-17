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
from just_dna_format.layout import sidecar_write_path

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: split\n  title: Split\n  description: d\n  report_title: Split\n"
)

#: Every machine-written sidecar a pass may create, and the pass that owns it. Names come from the
#: schema's own layout module rather than a list kept here, so a new sidecar shows up as a KeyError in
#: `test_the_roster_covers_every_writable_sidecar` rather than as silence.
SIDECAR_OWNERS = {
    "resolution.csv": "enrich",
    "frequencies.csv": "enrich_frequencies",
    "gene_metrics.csv": "enrich_gene_metrics + enrich_clingen_dosage",
    "literature.csv": "enrich_literature",
    "gene_validity.csv": "enrich_gene_validity",
    "clinical_assertions.csv": "enrich_clinical_assertions",
    "gwas_effects.csv": "enrich_gwas",
    "sources.csv": "every pass that consults a source",
    # RM51's second accepted spelling of the same file. Both are listed because a module may carry
    # either, and a pass reaching for the literal would be as wrong with the new name as the old.
    "licensing.csv": "every pass that consults a source",
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
    for module in sorted(src.glob("*.py")):
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
    """Guard the premise: the roster above must not fall behind the schema's own list."""
    from just_dna_format.layout import SIDECAR_SPELLINGS

    known = {name for spellings in SIDECAR_SPELLINGS.values() for name in spellings}
    known |= set(SIDECAR_SPELLINGS)
    csvs = {name for name in known if name.endswith(".csv")}
    assert set(SIDECAR_OWNERS) >= csvs, (
        f"a sidecar the schema knows about is missing from SIDECAR_OWNERS: "
        f"{sorted(csvs - set(SIDECAR_OWNERS))}"
    )


@pytest.mark.parametrize("name", sorted(SIDECAR_OWNERS), ids=sorted(SIDECAR_OWNERS))
def test_the_resolver_follows_a_split_module_for_every_sidecar(
    split_spec: Path, name: str
) -> None:
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
