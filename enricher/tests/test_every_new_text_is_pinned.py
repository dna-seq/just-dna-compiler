"""Every warning and log text 0.9 adds is pinned by a test asserting its stable fragment (review round 1,
item 2; `@warning-text-is-api`).

`NEW_TEXTS` is the walk's input: one entry per text the `main...0.9` diff added to a logger call, a `Finding`
or a `warnings` list, found by an AST walk over both sides of every changed module when this file was written,
and each with the fragment of it that does not move with its arguments. Three checks hold it:

* **the fragment is still the module's**: it is part of a string literal there (a `%s` in it is the module's
  own placeholder, matched in an assert by whatever the test rendered), so rewording the text turns this walk
  red, as well as the test that pins it;
* **a test pins it**: the fragment is inside an `assert` (or a `pytest.raises(match=…)`) of the test file the
  entry names, or the entry names the module constant the text is and an assert there references it. A string
  that only appears in a test file pins nothing, and an assert in another file about other words pins nothing;
* **a module wholly new in 0.9 has no text outside the list**: every emission in `NEW_MODULES` contains a
  fragment registered for it, so a new log line there owes an entry and a pin.

The third check cannot see a new text in a module older than 0.9, since no test may read git (CI's checkout
is shallow); such a text is caught at review, and this list is where it then goes. One helper is the exception:
`locations._warn_once` is new in 0.9, so every text passed to it, in any module, is a 0.9 warning the list
must name (review round 2, E). Exception texts stay out of the walk: a caller catches an exception by its type,
never by its words.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import just_dna_enricher
import pytest

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent
_TESTS = Path(__file__).resolve().parent
_LEVELS = {"debug", "info", "warning", "error", "exception", "critical"}


@dataclass(frozen=True)
class Text:
    """One text 0.9 added: its module (dotted, under `just_dna_enricher`), its stable fragment, the test file
    whose asserts pin it, and the module constant it is when it is one (a test may assert the constant)."""

    module: str
    fragment: str
    pinned_in: str
    constant: str | None = None


NEW_TEXTS: tuple[Text, ...] = (
    Text("clinvar", ": not in ", "test_remote_snapshots.py"),
    Text("lookup", "the ClinVar snapshot read over ", "test_remote_snapshots.py"),
    Text("lookup", " answered over two routes in one lookup: ", "test_remote_snapshots.py"),
    Text(
        "lookup", ": no local snapshot, and an rsID alone is never asked remotely", "test_remote_snapshots.py"
    ),
    Text("lookup", "ClinVar could not be asked remotely, clin_sig unchecked: ", "test_remote_snapshots.py"),
    Text(
        "lookup",
        "could not be asked remotely, so its answer is unchecked rather than empty",
        "test_remote_snapshots.py",
    ),
    Text("download", "Pulling the Ensembl ", "test_ensembl_groups.py"),
    Text("download", "Ensembl group ", "test_ensembl_groups.py"),
    Text("download", "Ensembl group %s: skipped — ", "test_ensembl_groups.py"),
    Text("download", "an earlier release's ", "test_ensembl_groups.py"),
    Text("download", "selected by an earlier pull, was not re-pulled", "test_ensembl_groups.py"),
    Text("download", "any group selection it held is lost", "test_ensembl_groups.py"),
    Text(
        "enrich.orchestration",
        "does not use the sequence proxy passed as `sequences`",
        "test_enrich_takes_clients.py",
        "OFFLINE_OUTRANKS_SEQUENCES",
    ),
    Text("ensembl_rsid_index_build", " rsID loci of ", "test_ensembl_rsid_index.py"),
    Text("ensembl_rsid_index_build", "Built the rsID index of ", "test_ensembl_rsid_index.py"),
    Text("ensembl_rsid_index_build", "rsID index, pass 1: ", "test_ensembl_rsid_index.py"),
    Text("ensembl_rsid_index_build", "rsID index, pass 2: bucket ", "test_ensembl_rsid_index.py"),
    Text("resolver", "No rsID index was found at ", "test_ensembl_rsid_index.py"),
    Text("resolver", " was not built from the Ensembl core at ", "test_ensembl_rsid_index.py"),
    Text("resolver", "; scanning the core.", "test_ensembl_rsid_index.py"),
    Text("resolver", "it holds no index file", "test_ensembl_rsid_index.py"),
    Text(
        "ensembl_rsid_index_build", "over other files than the Ensembl core at ", "test_ensembl_rsid_index.py"
    ),
    Text("ensembl_rsid_index_build", ", and the Ensembl core at ", "test_ensembl_rsid_index.py"),
    Text("ensembl_rsid_index_build", " cannot be pinned: ", "test_ensembl_rsid_index.py"),
    Text("remote", "a 200 that is not a lane reply (", "test_remote_snapshots.py"),
    Text("remote", "a 200 that is not the reply asked for: it answers ", "test_remote_snapshots.py"),
    Text("remote", "holds only blanks", "test_remote_snapshots.py"),
    Text("locations", "groups are not a map of name to record", "test_ensembl_groups.py"),
    Text("locations", " group is not an object; read with nothing stated", "test_ensembl_groups.py"),
    Text("locations", " do not fit; read as unstated.", "test_ensembl_groups.py"),
    Text("remote", " row(s) over ", "test_remote_snapshots.py"),
    Text("remote", ": pinned ", "test_remote_snapshots.py"),
    Text("remote", "the proxy's replies to one lookup state ", "test_remote_snapshots.py"),
    Text("remote", "; asking Hugging Face", "test_remote_snapshots.py"),
    Text("remote", "could not be read; it attests no file", "test_remote_snapshots.py"),
    Text("remote", "the proxy could not answer (", "test_remote_snapshots.py"),
    Text("remote", "the registry's proxy compares a whole cell exactly", "test_remote_snapshots.py"),
    Text("remote", "the registry's proxy answers at most ", "test_remote_snapshots.py"),
    Text(
        "sequences",
        "this read returns no bases, and the build is retried at the proxy's next read",
        "test_enrich_takes_clients.py",
    ),
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
    """`(line, literal pieces)` of every logger call, `_warn_once`, `Finding`, and `warnings` append or warn in
    `tree`. `locations._warn_once` is a logger warning said once per process (review round 2, E)."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func, text = node.func, None
        if (isinstance(func, ast.Name) and func.id == "_warn_once") or (
            isinstance(func, ast.Attribute) and func.attr == "_warn_once"
        ):
            text = node.args[0] if node.args else None
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
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


def _pins(test_file: str) -> tuple[list[str], set[str]]:
    """Every string literal inside an `assert` or a `match=` of `test_file`, and every name its asserts reference.

    Looked for in the one file the entry names, never across the suite: a short fragment is otherwise "pinned" by
    an unrelated test's assert, and deleting the real pin would leave this green."""
    literals: list[str] = []
    names: set[str] = set()
    for node in ast.walk(ast.parse((_TESTS / test_file).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assert):
            literals.extend(_literals(node))
            names.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name))
            names.update(n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute))
        elif isinstance(node, ast.keyword) and node.arg == "match":
            literals.extend(_literals(node.value))
    return literals, names


@pytest.mark.parametrize("text", NEW_TEXTS, ids=lambda t: f"{t.module}:{t.fragment}")
def test_the_fragment_is_still_its_modules_words(text: Text) -> None:
    pieces = _literals(ast.parse(_source(text.module).read_text(encoding="utf-8")))
    assert any(text.fragment in piece for piece in pieces), f"{text.module} no longer says {text.fragment!r}"


@pytest.mark.parametrize("text", NEW_TEXTS, ids=lambda t: f"{t.module}:{t.fragment}")
def test_a_test_asserts_the_fragment(text: Text) -> None:
    assert text.pinned_in != Path(__file__).name
    literals, names = _pins(text.pinned_in)
    by_constant = text.constant is not None and text.constant in names
    # A `%s` in a fragment is the module's own placeholder: in an assert it is whatever the test rendered there.
    rendered = re.compile(".+?".join(re.escape(part) for part in text.fragment.split("%s")))
    assert by_constant or any(rendered.search(piece) for piece in literals), (
        f"no assert in {text.pinned_in} says {text.fragment!r} ({text.module})"
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


def _calls_to(tree: ast.AST, name: str) -> list[int]:
    """The lines of every call to `name`, by its bare name or as an attribute."""
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
    )


def test_every_text_said_once_is_an_emission_the_list_names() -> None:
    """Review round 2, E: a text passed to `locations._warn_once` is a warning, so the walk sees it as one. The
    helper is new in 0.9, so every call of it, in any module, is a 0.9 text that owes an entry and a pin, which
    the third check cannot ask of a module older than 0.9. Exception texts stay out: a caller catches an
    exception by its type, never by its words."""
    calls: dict[str, list[int]] = {}
    unseen, unnamed = [], []
    for path in sorted(_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        lines = _calls_to(tree, "_warn_once")
        if not lines:
            continue
        parts = path.relative_to(_PACKAGE).with_suffix("").parts
        module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        calls[module] = lines
        emitted = dict(_emissions(tree))
        fragments = [text.fragment for text in NEW_TEXTS if text.module == module]
        for line in lines:
            if line not in emitted:
                unseen.append((module, line))
            elif not any(fragment in piece for fragment in fragments for piece in emitted[line]):
                unnamed.append((module, line, emitted[line]))
    assert calls, "no call of `_warn_once` was found, so this walk reads nothing"
    assert not unseen, f"the emission walk does not see these `_warn_once` calls: {unseen}"
    assert not unnamed, f"texts said once that no entry names: {unnamed}"
