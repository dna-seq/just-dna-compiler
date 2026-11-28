"""Measure the Python names added since the last cut from source in each of the three tiers."""

import ast
import re
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TAG = "v0.9.0"
_REFERENCE = {
    Path("schema/src/just_dna_format"): "SCHEMAS.md",
    Path("compiler/src/just_dna_compiler"): "COMPILER.md",
    Path("enricher/src/just_dna_enricher"): "ENRICHER.md",
}

type Definition = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
type Name = tuple[Path, str]


def _definitions(node: ast.AST, prefix: str = "") -> Iterator[tuple[str, Definition]]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not child.name.startswith("_"):
                name = prefix + child.name
                yield name, child
                if isinstance(child, ast.ClassDef):
                    yield from _definitions(child, name + ".")
        elif isinstance(child, (ast.stmt, ast.ExceptHandler, ast.match_case)):
            # A conditional definition belongs to this scope. A function's local names do not.
            yield from _definitions(child, prefix)


@pytest.fixture(scope="module")
def additions(git_output: Callable[..., str | None], release_tags: list[str]) -> dict[Name, Definition]:
    if _TAG not in release_tags:
        pytest.skip("no full history with v0.9.0 here; nothing to measure")
    packages = tuple(map(str, _REFERENCE))
    old_files = git_output("ls-tree", "-r", "--name-only", _TAG, "--", *packages)
    assert old_files
    old_paths = set(old_files.splitlines())
    files = git_output("ls-files", "--cached", "--others", "--exclude-standard", "--", *packages)
    assert files
    new: dict[Name, Definition] = {}
    occurrences: Counter[tuple[Path, str]] = Counter()
    for path in map(Path, files.splitlines()):
        current = _ROOT / path
        if path.suffix != ".py" or not current.is_file():
            continue
        source = git_output("show", f"{_TAG}:{path}") if str(path) in old_paths else ""
        assert source is not None, path
        old = dict(_definitions(ast.parse(source, filename=str(path))))
        now = dict(_definitions(ast.parse(current.read_text(encoding="utf-8"), filename=str(path))))
        package = next(root for root in _REFERENCE if path.is_relative_to(root))
        occurrences.update((package, name) for name in now)
        for name in now.keys() - old.keys():
            new[path, name] = now[name]
    # A mention of e.g. cpic_build.build_snapshot cannot cover ipd_imgt_hla_build.build_snapshot.
    result = {}
    for (path, name), node in new.items():
        package = next(root for root in _REFERENCE if path.is_relative_to(root))
        if occurrences[package, name] > 1:
            module = path.relative_to(package).with_suffix("").parts
            name = ".".join((*module, name))
        result[path, name] = node
    return result


def test_new_public_names_have_docstrings(additions: dict[Name, Definition]) -> None:
    """Every added function, class and public class member has its own nonblank source docstring."""
    missing = {f"{path}:{name}" for (path, name), node in additions.items() if not ast.get_docstring(node)}
    assert missing == set(), "\n".join(sorted(missing))


def test_new_public_names_in_tier_reference(additions: dict[Name, Definition]) -> None:
    """Document every new public definition, including CLI callbacks and helpers used by enrich().

    This includes methods and nested classes under their owning class name. A Python spelling in
    inline code or a code block in the defining tier's reference counts. Names defined in multiple
    modules of one tier need the module qualifier as well. There are no exemptions.
    """
    missing = set()
    for package, reference in _REFERENCE.items():
        page = (_ROOT / "docs" / reference).read_text(encoding="utf-8")
        fragments = re.finditer(r"```[^\n]*\n([\s\S]*?)```|`([^`\n]+)`", page)
        code = "\n".join(match.group(1) or match.group(2) or "" for match in fragments)
        for path, name in additions:
            if path.is_relative_to(package) and not re.search(rf"\b{re.escape(name)}\b", code):
                missing.add(f"{reference}: {path} ({name})")
    assert missing == set(), "\n".join(sorted(missing))
