"""Every pulled lane's repository is spelled once, in `locations.SNAPSHOT_REPO_IDS` (RM384).

Before RM384 each pulled lane's repository was written twice, as a `DEFAULT_*_REPO_ID` in `upload.py`
and again inside its fsspec prefix in `download.py`, and nothing tied the pair. The Ensembl lane had
only the second spelling, private, so a consumer pinning `ManifestCompilation.ensembl_reference`
(`org/repo@<rev>`) spelled the string or stripped `datasets/` and `/data` off a private prefix (S130).
The rename RM372 made by hand is the one a pair lets go wrong.

The map is the one spelling now: each prefix, each publisher default and each lane's `publish_repo` is
derived from it. These tests assert equalities over the walked registry, with the expected side
spelled independently of the derivation, and an AST walk over every source tree refuses a repo id
written as a literal anywhere else.
"""

import ast
from pathlib import Path

import just_dna_compiler
import just_dna_enricher
import just_dna_format
from just_dna_enricher import download as dl
from just_dna_enricher import locations, upload
from just_dna_enricher.caches import CACHE_LANES
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS

#: The one pulled lane whose snapshot has no `data/` directory: STRchive's payload is a JSON catalogue
#: at the repo root, so it has a repo id and no `data/` prefix (and no glob, for the same reason).
_ROOT_PAYLOAD_LANES = frozenset({"strchive"})


def test_the_map_holds_every_pulled_lane() -> None:
    """A lane this tier can pull has a repository, and a repository here names a lane that is pulled."""
    pulled = {lane.name for lane in CACHE_LANES if lane.ensure is not None}
    assert set(SNAPSHOT_REPO_IDS) == pulled


def test_the_ensembl_repository_has_a_public_name() -> None:
    """The S130 case: the `org/repo` half of `ensembl_reference`'s `org/repo@<rev>`, read off the map."""
    assert SNAPSHOT_REPO_IDS["ensembl"] == "just-dna-seq/ensembl_variations_split"


def test_each_prefix_is_its_repository_under_data() -> None:
    """Every `data/`-shaped lane's prefix is `datasets/<repo id>/data`; only a root-payload lane has none."""
    assert set(dl.SNAPSHOT_REPO_PREFIXES) == set(SNAPSHOT_REPO_IDS) - _ROOT_PAYLOAD_LANES, (
        "a lane whose snapshot is a data/ directory has a prefix; STRchive's payload sits at the repo root"
    )
    for lane, prefix in dl.SNAPSHOT_REPO_PREFIXES.items():
        assert prefix == f"datasets/{SNAPSHOT_REPO_IDS[lane]}/data", lane


def test_a_root_payload_lane_is_fetched_from_its_repository_root() -> None:
    assert dl._STRCHIVE_HF_REPO == f"datasets/{SNAPSHOT_REPO_IDS['strchive']}"


def test_every_publish_repo_is_its_lanes_repository() -> None:
    """The third spelling: `CacheLane.publish_repo` is where this tier publishes, and that is where it pulls."""
    published = {lane.name: lane.publish_repo for lane in CACHE_LANES if lane.publish_repo is not None}
    assert published == {name: SNAPSHOT_REPO_IDS[name] for name in published}


def test_every_lane_publisher_default_is_its_lanes_repository() -> None:
    """Each `DEFAULT_<LANE>_REPO_ID` alias (P3) equals its own lane's entry; `DEFAULT_REPO_ID` is modules', no lane's.

    Per alias, not a subset: `DEFAULT_DRUG_LABELS_REPO_ID = SNAPSHOT_REPO_IDS["clinpgx"]` is a value of
    the map and would publish the drug labels into the ClinPGx repo.
    """
    aliases = {
        name.removeprefix("DEFAULT_").removesuffix("_REPO_ID").lower(): value
        for name, value in vars(upload).items()
        if name.startswith("DEFAULT_") and name.endswith("_REPO_ID") and name != "DEFAULT_REPO_ID"
    }
    assert aliases
    assert aliases == {lane: SNAPSHOT_REPO_IDS[lane] for lane in aliases}
    assert upload.DEFAULT_REPO_ID not in SNAPSHOT_REPO_IDS.values()


# ── the class guard: a repository is spelled once ───────────────────────────────────────────────


def _prose_ids(tree: ast.AST) -> set[int]:
    """`id()` of every bare string statement (a docstring, or prose standing as one): prose, not a spelling."""
    return {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def _definition_ids(tree: ast.AST, names: frozenset[str]) -> set[int]:
    """`id()` of every string inside a module-level assignment to one of `names`: the one place it is spelled."""
    allowed: set[int] = set()
    for node in getattr(tree, "body", []):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if any(isinstance(target, ast.Name) and target.id in names for target in targets):
            allowed |= {id(sub) for sub in ast.walk(node) if isinstance(sub, ast.Constant)}
    return allowed


#: Where each repo id may be written as a literal: the map, and the module repo's own constant.
_DEFINITIONS = {
    Path(locations.__file__).resolve(): frozenset({"SNAPSHOT_REPO_IDS"}),
    Path(upload.__file__).resolve(): frozenset({"DEFAULT_REPO_ID"}),
}


def test_no_repository_is_spelled_outside_its_definition() -> None:
    """An AST walk over all three source trees: a repo id inside any non-prose string literal is a restatement.

    The CLI's `--repo` help text was the instance the walk found beyond the prefixes: four commands
    wrote `Default: just-dna-seq/<repo>.` by hand where the alphagenome command already interpolated
    its constant. The walk matches the **organisation** (`just-dna-seq/`), not only whole repo ids, so
    a repo composed from pieces (`"just-dna-seq/" + lane`, `f"just-dna-seq/{lane}"`) is refused too.
    """
    repos = {repo.split("/", 1)[0] + "/" for repo in {*SNAPSHOT_REPO_IDS.values(), upload.DEFAULT_REPO_ID}}
    roots = {
        Path(pkg.__file__).resolve().parent for pkg in (just_dna_format, just_dna_compiler, just_dna_enricher)
    }
    offenders: list[str] = []
    for root in sorted(roots):
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            skip = _prose_ids(tree) | _definition_ids(tree, _DEFINITIONS.get(path.resolve(), frozenset()))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or id(node) in skip:
                    continue
                spelled = sorted(repo for repo in repos if repo in node.value)
                if spelled:
                    offenders.append(
                        f"{path.relative_to(root.parent)}:{node.lineno} spells {', '.join(spelled)}"
                    )
    assert offenders == []
