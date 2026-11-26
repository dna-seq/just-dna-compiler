"""A run takes one view before selecting a SequenceProxy read method (RM463).

Walk the installed source tree, including reads inside a returned closure. A function that
only forwards its argument leaves the choice of view to the reader. Rebinding the argument
itself is safe when the wrap is unconditional. A dataclass also takes its annotated fields as
constructor arguments, so its readers inherit the bindings left by __post_init__.
"""

import ast
from pathlib import Path

import just_dna_enricher
import pytest


def _takes_proxy(annotation: ast.expr | None, names: set[str]) -> bool:
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return _takes_proxy(ast.parse(annotation.value, mode="eval").body, names)
    if annotation is None:
        return False
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name) and node.id in names:
            return True
        if isinstance(node, ast.Attribute) and node.attr == "SequenceProxy":
            return True
    return False


class _Reads(ast.NodeVisitor):
    def __init__(self, function: ast.FunctionDef | ast.AsyncFunctionDef, raw: set[str]) -> None:
        self.function = function
        self.raw = raw
        self.findings: list[str] = []

    def _raw_receiver(self, value: ast.expr) -> bool:
        if isinstance(value, ast.BoolOp):
            return any(self._raw_receiver(option) for option in value.values)
        if isinstance(value, ast.IfExp):
            return self._raw_receiver(value.body) or self._raw_receiver(value.orelse)
        return isinstance(value, (ast.Name, ast.Attribute)) and ast.unparse(value) in self.raw

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in {"proxy", "subsequence"} and self._raw_receiver(node.value):
            self.findings.append(f"{self.function.name} selects {ast.unparse(node)} before held_by_one_run")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign | ast.AnnAssign) -> None:
        if node.value is None:
            return
        self.visit(node.value)  # The RHS still sees the old binding.
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            self.visit(target)
            if not isinstance(target, (ast.Name, ast.Attribute)):
                continue
            name = ast.unparse(target)
            if self._raw_receiver(node.value):
                self.raw.add(name)
            elif (
                node in self.function.body
                and isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func).split(".")[-1] == "held_by_one_run"
            ):
                self.raw.discard(name)

    visit_AnnAssign = visit_Assign

    def scan(self) -> list[str]:
        for statement in self.function.body:
            self.visit(statement)
        return self.findings


def _field_reads(cls: ast.ClassDef, names: set[str]) -> list[str]:
    """Check readers of injected fields, including the minter's generated constructor."""
    raw = {
        f"self.{field.target.id}"
        for field in cls.body
        if isinstance(field, ast.AnnAssign)
        and isinstance(field.target, ast.Name)
        and _takes_proxy(field.annotation, names)
    }
    if not raw:
        return []
    methods = [node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    findings = []
    for method in methods:
        if method.name == "__post_init__":
            findings.extend(_Reads(method, raw).scan())
    for method in methods:
        if method.name != "__post_init__":
            findings.extend(_Reads(method, raw.copy()).scan())
    return findings


def _check_readers(source: str, filename: str) -> None:
    tree = ast.parse(source, filename)
    names = {"SequenceProxy"}
    names.update(
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name == "SequenceProxy" and alias.asname
    )
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            findings.extend(_field_reads(node, names))
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        raw = {
            arg.arg
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)
            if _takes_proxy(arg.annotation, names)
        }
        if raw:
            findings.extend(_Reads(node, raw).scan())
    assert not findings, f"{filename}: " + ", ".join(findings)


def test_every_sequence_proxy_reader_wraps_before_reading() -> None:
    package = Path(just_dna_enricher.__file__).parent
    for path in sorted(package.rglob("*.py")):
        _check_readers(path.read_text(), str(path.relative_to(package)))


def test_the_walk_rejects_an_unwrapped_reader() -> None:
    sample = "def read(shared: SequenceProxy):\n    return shared.subsequence('SQ.test', 0, 1)"
    with pytest.raises(AssertionError, match="read selects shared.subsequence before held_by_one_run"):
        _check_readers(sample, "sample.py")


@pytest.mark.parametrize(
    "body",
    [
        "shared.proxy()\n    shared = held_by_one_run(shared)",
        "held_by_one_run(shared)\n    return shared.proxy()",
        "if flag:\n        shared = held_by_one_run(shared)\n    return shared.proxy()",
        "raw = shared\n    view = held_by_one_run(shared)\n    return raw.proxy()",
    ],
)
def test_a_wrap_must_cover_the_read(body: str) -> None:
    with pytest.raises(AssertionError, match="before held_by_one_run"):
        _check_readers(f"def read(*, shared: sequences.SequenceProxy | None):\n    {body}", "sample.py")


def test_the_walk_checks_a_dataclass_reader_after_initialization() -> None:
    sample = """@dataclass
class Reader:
    shared: SequenceProxy

    def __post_init__(self):
        self.shared = held_by_one_run(self.shared)

    def read(self):
        return self.shared.proxy()
"""
    _check_readers(sample, "sample.py")
    with pytest.raises(AssertionError, match=r"read selects self\.shared\.proxy"):
        _check_readers(sample.replace("held_by_one_run(self.shared)", "self.shared"), "sample.py")
