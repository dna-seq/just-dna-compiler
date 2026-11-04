"""The `resolution.csv` writer and the column list it derives from the model (RM260 split this out
of the former single-file `enrich.py`).
"""

import csv
from collections.abc import Callable
from pathlib import Path

from just_dna_format.layout import atomic_writer, nothing_to_write
from just_dna_format.resolution import ResolutionRow

#: Derived from the model, never restated beside it (`@fieldnames-from-model`). This was a hand-kept
#: literal in sync with `ResolutionRow` by coincidence, paired with a per-column dict literal in the
#: writer below — the shape `SOURCES_FIELDNAMES` had when it lost `redistribution`. Here the loss
#: would have been quieter: `DictWriter` raises nothing for a model field the dict simply omits, so
#: the next optional column on `ResolutionRow` would have been dropped by every enrich run, and a
#: fact column among them would have made `resolution_signature` disagree between a hand-filled
#: table and an enricher-filled one. `ResolutionRow` carries no compiler-stamped fields, so
#: `model_fields` is exactly the written surface.
_FIELDNAMES: list[str] = list(ResolutionRow.model_fields)


def _write_resolution_csv(
    rows: list[ResolutionRow], output_path: Path, *, before_commit: Callable[[], None] | None = None
) -> None:
    """Write `resolution.csv` with a fixed column order and canonical cells.

    **This file is a pure build product since 0.7 (RM124).** Hand-editing it is not expected and
    nothing preserves such an edit — a correction to a derived row belongs in `overrides.csv` beside
    the spec, where the compiler applies it on every build and it travels with the reason it was
    made. That is what makes deleting this file and re-running cost nothing: the author's judgements
    are not in here to lose. The re-run itself is unchanged, and still gap-fills rather than re-asking
    every subject; what changed is that leaving a recorded row alone now risks nothing.
    """
    if nothing_to_write(output_path, rows):
        return  # RM370: a pass that answered nothing leaves no table
    with atomic_writer(output_path, newline="", before_commit=before_commit) as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for r in rows:
            # Generic over the fields for the reason `_FIELDNAMES` gives: a per-column dict literal is
            # a hand-kept column list one edit later. `None` is the empty cell; every other value is
            # written as the model holds it (`start`/`locus_index` are ints and render as such).
            writer.writerow({name: _resolution_cell(getattr(r, name)) for name in _FIELDNAMES})


def _resolution_cell(value: object) -> str:
    """`None` is the empty cell, a boolean `true`/`false`, everything else its `str`.

    The boolean spelling is the compiler's `_scalar_cell`'s, the writer `reverse` uses for this same
    table, so the tri-state `left_aligned` (RM270) reads back the same from either. Spelled here rather
    than imported: `just_dna_compiler.compiler.tables` is not in the compiler release this package's
    floor names (`test_workspace_versions`).
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
