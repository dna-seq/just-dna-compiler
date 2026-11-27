"""The registry covers each logger call, Finding, _warn_once and warnings append/warn in the package.

Each occurrence consumes one registry row. Only rows with a named test owe an assert there.
A caller catches exceptions by type. Their messages and CLI output are outside the emission walk.
Earlier pins on wording supplied by helpers or exceptions still owe their module literal and test assert.
"""

import ast
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from functools import cache
from pathlib import Path

import just_dna_enricher
import pytest
from just_dna_enricher.atlas_protos import OUT_DIR

from enricher.tests.emitted_texts import EMITTED_TEXTS, NEW_TEXTS, Carried, Forwarded, Text

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent
_TESTS = Path(__file__).resolve().parent
_LEVELS = {"debug", "info", "warning", "error", "exception", "critical"}


def _source(module: str) -> Path:
    if not module:
        return _PACKAGE / "__init__.py"
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


@cache
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


@pytest.mark.parametrize("module", sorted({text.module for text in EMITTED_TEXTS}))
def test_the_fragments_are_still_their_modules_words(module: str) -> None:
    tree = ast.parse(_source(module).read_text(encoding="utf-8"))
    words: dict[str | None, list[str]] = {None: _literals(tree)}
    for statement in tree.body:
        # A reference to a named constant must still emit its words even if a stale copy survives elsewhere.
        match statement:
            case ast.Assign(targets=targets, value=value):
                for target in targets:
                    if isinstance(target, ast.Name):
                        words[target.id] = _literal(value)
            case ast.AnnAssign(target=ast.Name(id=name), value=value) if value is not None:
                words[name] = _literal(value)
    registered = {
        (text.fragment, text.constant)
        for text in EMITTED_TEXTS
        if text.module == module and not isinstance(text, Forwarded)
    }
    found = {
        (fragment, constant)
        for fragment, constant in registered
        if any(fragment in piece for piece in words.get(constant, []))
    }
    assert found == registered, f"{module} no longer says {registered - found}"


@pytest.mark.parametrize("text", NEW_TEXTS, ids=lambda t: f"{t.module}:{t.fragment}")
def test_a_test_asserts_the_fragment(text: Text) -> None:
    assert text.pinned_in is not None and text.pinned_in != Path(__file__).name
    literals, names = _pins(text.pinned_in)
    by_constant = text.constant is not None and text.constant in names
    # A `%s` in a fragment is the module's own placeholder: in an assert it is whatever the test rendered there.
    rendered = re.compile(".+?".join(re.escape(part) for part in text.fragment.split("%s")))
    assert by_constant or any(rendered.search(piece) for piece in literals), (
        f"no assert in {text.pinned_in} says {text.fragment!r} ({text.module})"
    )


def _modules() -> Iterator[tuple[str, ast.Module]]:
    for path in sorted(_PACKAGE.rglob("*.py")):
        if path.is_relative_to(OUT_DIR):  # protoc output, including its package initializers
            continue
        parts = path.relative_to(_PACKAGE).with_suffix("").parts
        module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        yield module, ast.parse(path.read_text(encoding="utf-8"))


def _matches(text: Text, pieces: list[str]) -> bool:
    if isinstance(text, Forwarded):
        return pieces == [text.fragment]
    if text.constant is not None:
        return pieces == [text.constant]
    return any(text.fragment in piece for piece in pieces) and (
        text.context is None or any(text.context in piece for piece in pieces)
    )


def _entry_for(pieces: list[str], entries: list[Text]) -> Text | None:
    matches = (text for text in entries if _matches(text, pieces))
    # "Ensembl group %s: skipped" is more specific than "Ensembl group ".
    return max(matches, key=lambda text: len(text.fragment) + len(text.context or ""), default=None)


def _occurrences(fragments: Iterable[str]) -> Iterator[tuple[str, int]]:
    """Two calls with identical wording still owe two entries, even if their lines move."""
    seen: Counter[str] = Counter()
    for fragment in fragments:
        seen[fragment] += 1
        yield fragment, seen[fragment]


def _entries_by_module() -> dict[str, list[Text]]:
    entries: dict[str, list[Text]] = defaultdict(list)
    for text in EMITTED_TEXTS:
        if not isinstance(text, Carried):
            entries[text.module].append(text)
    return entries


def test_every_module_emits_the_registered_texts() -> None:
    entries = _entries_by_module()
    registered = {
        (module, occurrence)
        for module, texts in entries.items()
        for occurrence in _occurrences(text.description for text in texts)
    }
    emitted = {}
    for module, tree in _modules():
        sites = sorted(_emissions(tree))
        descriptions = []
        for line, pieces in sites:
            entry = _entry_for(pieces, entries[module])
            if entry is not None:
                descriptions.append(entry.description)
            else:
                descriptions.append(f"unregistered at line {line}: {pieces!r}")
        for occurrence, site in zip(_occurrences(descriptions), sites, strict=True):
            emitted[module, occurrence] = site
    assert emitted.keys() == registered, (
        f"emitted without an entry: {[(key, emitted[key]) for key in sorted(emitted.keys() - registered)]}\n"
        f"registered without an emission: {sorted(registered - emitted.keys())}"
    )


def _calls_to(tree: ast.AST, name: str) -> list[tuple[int, list[str]]]:
    """`(line, literal pieces of the first argument)` of every call to `name`, by its bare name or as an attribute.

    Each call keeps its own pieces, so two calls on one line are two entries, never one."""
    return sorted(
        (node.lineno, _literal(node.args[0]) or [ast.unparse(node.args[0])] if node.args else [])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
    )


def test_every_text_said_once_is_an_emission_the_list_names() -> None:
    """Review round 2, E: a text passed to `locations._warn_once` is a warning, so the walk sees it as one. The
    helper dates to 0.9. Every call owes a pin as well as an entry."""
    entries = _entries_by_module()
    calls: dict[str, list[tuple[int, list[str]]]] = {}
    unseen, unpinned = [], []
    for module, tree in _modules():
        said_once = _calls_to(tree, "_warn_once")
        if not said_once:
            continue
        calls[module] = said_once
        emitted = _emissions(tree)
        for line, pieces in said_once:
            entry = _entry_for(pieces, entries[module])
            if (line, pieces) not in emitted:
                unseen.append((module, line))
            elif entry is None or entry.pinned_in is None:
                unpinned.append((module, line, pieces))
    assert calls, "no call of `_warn_once` was found, so this walk reads nothing"
    assert not unseen, f"the emission walk does not see these `_warn_once` calls: {unseen}"
    assert not unpinned, f"texts said once without a pinned entry: {unpinned}"
