"""Every warning and log text 0.9 adds is pinned by a test asserting its stable fragment (review round 1,
item 2; `@warning-text-is-api`).

`NEW_TEXTS` is the walk's input: one entry per text the `main...0.9` diff added to a logger call, a `Finding`
or a `warnings` list, found by an AST walk over both sides of every changed module when this file was written,
and each with the fragment of it that does not move with its arguments. Three checks hold it:

* **the fragment is still the module's**: it is part of a string literal there, so rewording the text turns
  this walk red, as well as the test that pins it;
* **a test pins it**: the fragment is inside an `assert` (or a `pytest.raises(match=…)`) of another test
  file, or the entry names the module constant the text is and a test asserts that constant. A string that
  only appears in a test file pins nothing;
* **a module wholly new in 0.9 has no text outside the list**: every emission in `NEW_MODULES` contains a
  fragment registered for it, so a new log line there owes an entry and a pin.

The third check cannot see a new text in a module older than 0.9, since no test may read git (CI's checkout
is shallow); such a text is caught at review, and this list is where it then goes.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

import just_dna_enricher
import pytest

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent
_TESTS = Path(__file__).resolve().parent
_LEVELS = {"debug", "info", "warning", "error", "exception", "critical"}


@dataclass(frozen=True)
class Text:
    """One text 0.9 added: its module (dotted, under `just_dna_enricher`), its stable fragment, and the module
    constant it is when it is one (a test may assert the constant rather than the words)."""

    module: str
    fragment: str
    constant: str | None = None


NEW_TEXTS: tuple[Text, ...] = (
    # clinvar / lookup: a remote miss names what was searched
    Text("clinvar", ": not in "),
    Text("lookup", "the ClinVar snapshot read over "),
    Text("lookup", " answered over two routes in one lookup: "),
    Text("lookup", ": no local snapshot, and an rsID alone is never asked remotely"),
    Text("lookup", "ClinVar could not be asked remotely, clin_sig unchecked: "),
    Text("lookup", "could not be asked remotely, so its answer is unchecked rather than empty"),
    # download: the Ensembl groups (RM437)
    Text("download", "Pulling the Ensembl "),
    Text("download", "Ensembl group "),
    Text("download", ": skipped — "),
    Text("download", "an earlier release's "),
    Text("download", "selected by an earlier pull, was not re-pulled"),
    # enrich: offline outranks a passed proxy (RM404)
    Text(
        "enrich.orchestration",
        "does not use the sequence proxy passed as `sequences`",
        "OFFLINE_OUTRANKS_SEQUENCES",
    ),
    # the rsID index (RM431)
    Text("ensembl_rsid_index_build", "Sorted "),
    Text("ensembl_rsid_index_build", "Built the rsID index of "),
    Text("ensembl_rsid_index_build", "rsID index, pass 1: "),
    Text("ensembl_rsid_index_build", "rsID index, pass 2: bucket "),
    Text("resolver", "No rsID index was found at "),
    Text("resolver", " was not built from the Ensembl core at "),
    Text("resolver", " could not be read ("),
    # the manifest's group records (review round 1, item 3)
    Text("locations", "groups are not a map of name to record"),
    Text("locations", " group is not an object; read with nothing stated"),
    Text("locations", " do not fit; read as unstated."),
    # the remote holder (RM430)
    Text("remote", " row(s) over "),
    Text("remote", ": pinned "),
    Text("remote", "the proxy's replies to one lookup state "),
    Text("remote", "; asking Hugging Face"),
    Text("remote", "could not be read; it attests no file"),
    Text("remote", "the proxy could not answer ("),
    Text("remote", "the registry's proxy compares a whole cell exactly"),
    Text("remote", "the registry's proxy answers at most "),
)

#: The modules wholly new in 0.9: every text they emit is one `NEW_TEXTS` names.
NEW_MODULES = ("remote", "key_compare", "ensembl_rsid_index_build", "clients")


def _source(module: str) -> Path:
    path = _PACKAGE.joinpath(*module.split("."))
    return path.with_suffix(".py") if path.with_suffix(".py").is_file() else path / "__init__.py"


def _literal(node: ast.AST) -> list[str]:
    """The literal pieces of a string expression: a constant, or the constant parts of an f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [value.value for value in node.values if isinstance(value, ast.Constant)]
    return []


def _literals(tree: ast.AST) -> list[str]:
    return [piece for node in ast.walk(tree) for piece in _literal(node)]


def _emissions(tree: ast.Module) -> list[tuple[int, list[str]]]:
    """`(line, literal pieces)` of every logger call, `Finding`, and `warnings` append or warn in `tree`."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func, text = node.func, None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if (
                func.attr in _LEVELS
                and func.value.id in ("logger", "logging")
                or (func.attr == "append" and "warning" in func.value.id)
                or (func.attr == "warn" and func.value.id == "warnings")
            ):
                text = node.args[0] if node.args else None
        elif isinstance(func, ast.Name) and func.id == "Finding":
            text = (
                node.args[3]
                if len(node.args) > 3
                else next((k.value for k in node.keywords if k.arg == "message"), None)
            )
        if text is not None:
            found.append((node.lineno, _literal(text) or [ast.unparse(text)]))
    return found


def _pinned() -> tuple[list[str], set[str]]:
    """Every string literal inside a test's `assert` or `match=`, and every name an `assert` references."""
    literals: list[str] = []
    names: set[str] = set()
    for path in sorted(_TESTS.glob("test_*.py")):
        if path.resolve() == Path(__file__).resolve():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Assert):
                literals.extend(_literals(node))
                names.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name))
                names.update(n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute))
            elif isinstance(node, ast.keyword) and node.arg == "match":
                literals.extend(_literals(node.value))
    return literals, names


_PINS = _pinned()


@pytest.mark.parametrize("text", NEW_TEXTS, ids=lambda t: f"{t.module}:{t.fragment}")
def test_the_fragment_is_still_its_modules_words(text: Text) -> None:
    pieces = _literals(ast.parse(_source(text.module).read_text(encoding="utf-8")))
    assert any(text.fragment in piece for piece in pieces), f"{text.module} no longer says {text.fragment!r}"


@pytest.mark.parametrize("text", NEW_TEXTS, ids=lambda t: f"{t.module}:{t.fragment}")
def test_a_test_asserts_the_fragment(text: Text) -> None:
    literals, names = _PINS
    by_constant = text.constant is not None and text.constant in names
    assert by_constant or any(text.fragment in piece for piece in literals), (
        f"no test asserts {text.fragment!r} ({text.module})"
    )


@pytest.mark.parametrize("module", NEW_MODULES)
def test_a_module_new_in_0_9_emits_no_text_the_list_does_not_name(module: str) -> None:
    fragments = [text.fragment for text in NEW_TEXTS if text.module == module]
    tree = ast.parse(_source(module).read_text(encoding="utf-8"))
    unnamed = [
        (line, pieces)
        for line, pieces in _emissions(tree)
        if not any(fragment in piece for fragment in fragments for piece in pieces)
    ]
    assert not unnamed, f"{module} emits texts no entry names: {unnamed}"
