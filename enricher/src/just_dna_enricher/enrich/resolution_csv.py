"""The `resolution.csv` writer and the column list it derives from the model (RM260 split this out
of the former single-file `enrich.py`).
"""

import csv
from collections.abc import Callable, Collection, Sequence
from pathlib import Path

from just_dna_format.layout import atomic_writer
from just_dna_format.resolution import ResolutionRow

from just_dna_enricher.enrich.outcome import EnrichmentError

#: Derived from the model, never restated beside it (`@fieldnames-from-model`). This was a hand-kept
#: literal in sync with `ResolutionRow` by coincidence, paired with a per-column dict literal in the
#: writer below — the shape `SOURCES_FIELDNAMES` had when it lost `redistribution`. Here the loss
#: would have been quieter: `DictWriter` raises nothing for a model field the dict simply omits, so
#: the next optional column on `ResolutionRow` would have been dropped by every enrich run, and a
#: fact column among them would have made `resolution_signature` disagree between a hand-filled
#: table and an enricher-filled one. `ResolutionRow` carries no compiler-stamped fields, so
#: `model_fields` is exactly the written surface.
_FIELDNAMES: list[str] = list(ResolutionRow.model_fields)


def _carried_records(
    path: Path,
    recorded: Sequence[ResolutionRow],
    preserve: Collection[int],
    fresh: Sequence[ResolutionRow],
) -> tuple[list[str], str | None, dict[int, str]]:
    """Keep each carried CSV record in its original column order, quoting and line endings."""
    with path.open(encoding="utf-8", newline="") as handle:
        lines = handle.readlines()
    reader = csv.reader(lines)
    fields = [name.strip() for name in next(reader)]
    header = "".join(lines[: reader.line_num])
    previous = iter(recorded)
    raw: dict[int, str] = {}
    start = reader.line_num
    for cells in reader:
        if cells:  # DictReader skips empty physical records in the validated input.
            row = next(previous)
            if id(row) in preserve:
                raw[id(row)] = "".join(lines[start : reader.line_num])
        start = reader.line_num
    # Historical headers may omit newer columns. Append only columns the fresh rows need;
    # DictReader supplies None for those trailing cells on the original, shorter records.
    for name, field in ResolutionRow.model_fields.items():
        if name in fields or all(getattr(row, name) == field.default for row in fresh):
            continue
        if field.default is not None:
            # A blank trailing cell is None, not the default supplied by an absent column.
            raise EnrichmentError(
                f"Selected re-derivation needs {name}, absent from the recorded header. "
                "A full --rederive can write this column on every row."
            )
        fields.append(name)
        header = None
    return fields, header, raw


def _write_resolution_csv(
    rows: list[ResolutionRow],
    output_path: Path,
    *,
    recorded: Sequence[ResolutionRow] = (),
    preserve: Collection[int] = (),
    before_commit: Callable[[], None] | None = None,
) -> None:
    """Write `resolution.csv` with a fixed column order and canonical cells.

    **This file is a pure build product since 0.7 (RM124).** Hand-editing it is not expected and
    nothing preserves such an edit — a correction to a derived row belongs in `overrides.csv` beside
    the spec, where the compiler applies it on every build and it travels with the reason it was
    made. That is what makes deleting this file and re-running cost nothing: the author's judgements
    are not in here to lose. The re-run itself is unchanged, and still gap-fills rather than re-asking
    every subject; what changed is that leaving a recorded row alone now risks nothing.

    **Written even with no row, the one sidecar `layout.nothing_to_write` does not gate (RM370).**
    Every pass downstream of `enrich` (`frequencies`, `assertions`, `opentargets enrich`, `vrs`) reads
    this table and refuses without it, telling the author to run `enrich` first. An empty table is
    therefore not a claim about a source — it names none, and no licence row lands with it — but the
    record that `enrich` ran and placed nothing, which those passes then answer as nothing to ask.
    """
    fields, header, raw = _FIELDNAMES, None, {}
    if preserve:
        fields, header, raw = _carried_records(
            output_path, recorded, preserve, [r for r in rows if id(r) not in preserve]
        )
        # A valid final record can lack a terminator. Only the last position can carry
        # that spelling without joining two records. The API still returns sorted rows.
        unterminated = next((key for key, record in raw.items() if not record.endswith(("\r", "\n"))), None)
        if unterminated is not None:
            rows = sorted(rows, key=lambda row: id(row) == unterminated)
    with atomic_writer(output_path, newline="", before_commit=before_commit) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if header is None:
            writer.writeheader()
        else:
            f.write(header)
        for r in rows:
            if id(r) in raw:
                f.write(raw[id(r)])
                continue
            # Generic over the fields for the reason `_FIELDNAMES` gives: a per-column dict literal is
            # a hand-kept column list one edit later. `None` is the empty cell; every other value is
            # written as the model holds it (`start`/`locus_index` are ints and render as such).
            writer.writerow({name: _resolution_cell(getattr(r, name)) for name in fields})


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
