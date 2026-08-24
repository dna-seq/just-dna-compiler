"""A sidecar writer must leave the whole file or the previous one, never half of either (S66).

The reported incident is the reason this walks the writers rather than testing one. `enrich()`
persists nothing until its tail, then writes `resolution.csv`, `verification.json` and `sources.csv`
in three consecutive statements — so one kill could truncate all three, and a run killed before the
tail discarded thirty minutes of successful per-variant network work. The truncation half is the one
that cannot report itself: `resolution.csv` is read back and *merged* by the next run under a
`subject` key, so a table cut off at row 162 of 330 is not detected as damaged, it is believed. The
three enricher branches that deliberately write **no row** for a subject nothing could answer are
what make the short file indistinguishable from a module whose author resolved less.

`test_every_sidecar_writer_is_atomic` is the guard that matters. Three of nine writers were named in
the report; the other six have the identical shape, and a fix applied only to what was reported is
the registry-shaped defect this repo keeps meeting — the next writer added by copying its neighbour
inherits whichever neighbour it copied.
"""

from __future__ import annotations

import ast
import csv
import inspect
from pathlib import Path

import pytest
from just_dna_format.layout import atomic_write_text, atomic_writer

# (module, function) for every pass that writes a whole sidecar table into a spec directory. The
# import is by name rather than by globbing `_write_*_csv` so that adding a writer without adding it
# here is a *visible* omission in this list, not a silently unwalked function.
SIDECAR_WRITERS = [
    ("just_dna_enricher.enrich", "_write_resolution_csv"),
    ("just_dna_enricher.licensing", "write_sources_csv"),
    ("just_dna_enricher.assertions", "_write_assertions_csv"),
    ("just_dna_enricher.gene_metrics", "_write_gene_metrics_csv"),
    ("just_dna_enricher.gene_validity", "_write_gene_validity_csv"),
    ("just_dna_enricher.frequencies", "_write_frequencies_csv"),
    ("just_dna_enricher.gwas", "_write_gwas_csv"),
    ("just_dna_enricher.literature", "_write_literature_csv"),
    ("just_dna_format.verification", "write_verification"),
]


def _writer_source(module_name: str, func_name: str) -> ast.FunctionDef:
    module = __import__(module_name, fromlist=[func_name])
    func = getattr(module, func_name)
    tree = ast.parse(inspect.getsource(func))
    return tree.body[0]


def _opens_for_truncating_write(node: ast.AST) -> list[str]:
    """Every `open(..., "w")` — bare, or as a `Path.open` method — inside a walked function."""
    found = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        name = None
        if isinstance(sub.func, ast.Name):
            name = sub.func.id
        elif isinstance(sub.func, ast.Attribute):
            name = sub.func.attr
        if name != "open":
            continue
        modes = [a.value for a in sub.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        modes += [
            kw.value.value
            for kw in sub.keywords
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant)
        ]
        if any("w" in m for m in modes):
            found.append(ast.unparse(sub))
    return found


@pytest.mark.parametrize(("module_name", "func_name"), SIDECAR_WRITERS)
def test_every_sidecar_writer_is_atomic(module_name: str, func_name: str) -> None:
    """No sidecar writer may truncate its target in place.

    Asserted over the walked set rather than as a count, because a floor ("at least three are
    atomic") is satisfied by exactly the state the report found.
    """
    node = _writer_source(module_name, func_name)
    truncating = _opens_for_truncating_write(node)
    assert not truncating, (
        f"{module_name}.{func_name} truncates its target in place: {truncating}. "
        "Route it through just_dna_format.layout.atomic_writer / atomic_write_text — a killed run "
        "must leave the previous table, never a short one (S66)."
    )

    source = inspect.getsource(getattr(__import__(module_name, fromlist=[func_name]), func_name))
    assert "atomic_write" in source, (
        f"{module_name}.{func_name} neither truncates nor writes atomically — it has grown a third "
        "shape this guard cannot classify. Read it before widening the rule."
    )


def test_naive_write_truncates_and_atomic_write_does_not(tmp_path: Path) -> None:
    """The failure the fix removes, demonstrated on both paths against one file.

    A writer that raises partway is the in-process stand-in for a killed process: both leave the
    handle's buffer unflushed after the target was already truncated.
    """
    target = tmp_path / "resolution.csv"
    complete = "variant_key,rsid\n1:100:A:G,rs1\n1:200:C:T,rs2\n"
    target.write_text(complete, encoding="utf-8")

    class Boom(RuntimeError):
        pass

    # The buggy shape, verbatim from what every one of these writers used to be.
    with pytest.raises(Boom), open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write("variant_key,rsid\n")
        handle.write("1:100:A:G,rs1\n")
        raise Boom("killed mid-table")

    damaged = target.read_text(encoding="utf-8")
    assert damaged != complete
    # The point of the item: what is left parses cleanly as a shorter table. Nothing downstream can
    # tell this from a module whose author resolved one variant.
    assert list(csv.DictReader(damaged.splitlines())) == [{"variant_key": "1:100:A:G", "rsid": "rs1"}]

    target.write_text(complete, encoding="utf-8")
    with pytest.raises(Boom), atomic_writer(target, newline="") as handle:
        handle.write("variant_key,rsid\n")
        handle.write("1:100:A:G,rs1\n")
        raise Boom("killed mid-table")

    assert target.read_text(encoding="utf-8") == complete, (
        "an interrupted atomic write must leave the previous table byte-for-byte"
    )
    assert list(tmp_path.glob(".*tmp*")) == [], "the partial temp file must not survive the failure"


def test_atomic_writer_emits_the_same_bytes_as_open(tmp_path: Path) -> None:
    """Routing a `csv.DictWriter` through the helper changes no emitted byte.

    `newline=""` is passed through rather than defaulted, because the sidecars are hashed inputs on
    one path and `csv.writer`'s `\\r\\n` line terminator is exactly what the attestation's newline
    normalization was built around — a helper that quietly changed it would move bindings.
    """
    rows = [{"a": "1", "b": "x"}, {"a": "2", "b": "y,z"}]

    naive = tmp_path / "naive.csv"
    with open(naive, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["a", "b"])
        writer.writeheader()
        writer.writerows(rows)

    atomic = tmp_path / "atomic.csv"
    with atomic_writer(atomic, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["a", "b"])
        writer.writeheader()
        writer.writerows(rows)

    assert atomic.read_bytes() == naive.read_bytes()
    assert b"\r\n" in atomic.read_bytes(), "the CRLF terminator csv.writer emits must survive"


def test_atomic_write_text_creates_parent_and_replaces(tmp_path: Path) -> None:
    """`write_verification`'s shape: it used to `mkdir(parents=True)` itself, and still must."""
    target = tmp_path / "derived" / "verification.json"
    assert atomic_write_text(target, '{"a": 1}\n') == target
    assert target.read_text(encoding="utf-8") == '{"a": 1}\n'

    atomic_write_text(target, '{"a": 2}\n')
    assert target.read_text(encoding="utf-8") == '{"a": 2}\n'
    assert sorted(p.name for p in target.parent.iterdir()) == ["verification.json"]
