"""`model_organisms.csv`, the model-organism evidence table (0.8, RM335): its one loader.

The table needs no expansion and no derived column: it compiles verbatim to `model_organisms.parquet`
through the generic `_build_table` and comes back through the generic `_write_table_csv`. What it needs is
the one loader `validate_spec` and `compile_module` both call, so the two cannot come to disagree about a
row (`@validate-refuses-all`), and the registration in `tables` (why it is not a `_TABLE_KINDS` entry is
argued at `tables.MODEL_ORGANISMS_CSV`).
"""

from pathlib import Path

from just_dna_format.model_organisms import ModelOrganismRow

from just_dna_compiler.compiler.load import load_csv_rows
from just_dna_compiler.compiler.table_checks import _validate_table_kind
from just_dna_compiler.compiler.tables import MODEL_ORGANISMS_CSV


def load_model_organisms(spec_dir: Path) -> tuple[list[ModelOrganismRow], list[str], list[str]]:
    """Read `model_organisms.csv` and answer with `(rows, errors, warnings)`; `([], [], [])` when absent.

    A present file with no rows is an error, the answer every authored table gives. The duplicate key goes
    through `_validate_table_kind`, so it reads as every other keyed table's does.

    Rows that parsed come back **with** a duplicate-key error, as `load_overlay`'s do: the pre-flight's
    citing view still needs them, or a `literature.csv` row this table cites would be reported as uncited
    in the same run as the duplicate, sending the author to the wrong file. Both callers refuse on any
    error before a parquet could be built from them.
    """
    path = Path(spec_dir) / MODEL_ORGANISMS_CSV
    if not path.is_file():
        return [], [], []
    rows, errors, warnings = load_csv_rows(path, ModelOrganismRow, MODEL_ORGANISMS_CSV)
    if errors:
        return [], errors, warnings
    if not rows:
        return [], [f"{MODEL_ORGANISMS_CSV} is present but has no rows."], warnings
    key_errors, key_warnings = _validate_table_kind(MODEL_ORGANISMS_CSV, ModelOrganismRow, rows)
    return rows, key_errors, [*warnings, *key_warnings]
