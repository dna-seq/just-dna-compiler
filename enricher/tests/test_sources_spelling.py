"""Every terms-emitting pass writes to the licence file the module already has (RM51).

The compiler half of the alias is in `compiler/tests/test_sidecar_spelling.py`. This is the writer's
half, and it is the one that matters most: a pass that always created the current spelling would, on a
module carrying the deprecated one, leave two copies behind — and *both present* is a refusal. That
collision is reachable by following the documented workflow (download a module, re-enrich it), not by
misusing anything, which is why "write to the file you read" is the load-bearing rule rather than a
tidiness preference.

Nine passes used to spell `spec_dir / "sources.csv"` by hand. They go through one resolver now, so
these tests drive that resolver through the enricher's own public functions rather than re-deriving a
path themselves.
"""

from pathlib import Path

import pytest
from just_dna_enricher.licensing import (
    ENSEMBL_TERMS,
    merge_sources_file,
    record_source_terms,
    sources_path,
)
from just_dna_format.layout import LICENSING_CSV, SOURCES_CSV
from just_dna_format.sources import SourceRow


class _PassError(RuntimeError):
    """Stands in for any one pass's own exception type."""


def _rows(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines()[1:] if line.strip()]


def test_a_fresh_module_gets_the_current_spelling(tmp_path: Path) -> None:
    """With nothing to preserve, a pass creates the name 1.0 will keep — which is the whole point.

    Landing the alias in a minor is only worth anything if new modules carry the new name, so that
    the major has to remove a spelling rather than add one.
    """
    written = record_source_terms(["ensembl"], "resolution", tmp_path, error=_PassError)
    assert written

    assert (tmp_path / LICENSING_CSV).is_file()
    assert not (tmp_path / SOURCES_CSV).exists()


def test_a_module_on_the_old_spelling_is_appended_to_in_place(tmp_path: Path) -> None:
    """No second file appears — the pass follows the module rather than the calendar."""
    existing = tmp_path / SOURCES_CSV
    existing.write_text(",".join(SourceRow.model_fields) + "\n")

    record_source_terms(["ensembl"], "resolution", tmp_path, error=_PassError)

    assert not (tmp_path / LICENSING_CSV).exists()
    assert _rows(existing), "the row was recorded into the file that already existed"


def test_re_running_a_pass_does_not_produce_the_collision(tmp_path: Path) -> None:
    """The regression this rule exists for, demonstrated end to end.

    Two passes in sequence against a module on the deprecated spelling must leave exactly one file.
    If the writer preferred the new name, the second call here would already be reading one file and
    writing another.
    """
    (tmp_path / SOURCES_CSV).write_text(",".join(SourceRow.model_fields) + "\n")

    record_source_terms(["ensembl"], "resolution", tmp_path, error=_PassError)
    record_source_terms(["gnomad"], "frequency", tmp_path, error=_PassError)

    present = sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".csv")
    assert present == [SOURCES_CSV]
    assert len(_rows(tmp_path / SOURCES_CSV)) == 2


def test_merging_never_clobbers_a_hand_written_row_under_either_spelling(tmp_path: Path) -> None:
    """The reason a collision cannot be merged away: these rows are edited by hand and that survives.

    A curator's `declared_use` is exactly the kind of override "newest wins" would discard, so the
    non-clobbering guarantee is asserted under the new spelling too rather than assumed to carry over.
    """
    hand_written = SourceRow(
        source=ENSEMBL_TERMS.source, layer="resolution", declared_use="non_commercial"
    )
    path = tmp_path / LICENSING_CSV
    merge_sources_file([hand_written], tmp_path, error=_PassError)
    assert path.is_file()

    record_source_terms(["ensembl"], "resolution", tmp_path, error=_PassError)

    assert "non_commercial" in path.read_text()


def test_both_spellings_present_fails_as_the_pass_own_error(tmp_path: Path) -> None:
    """A schema-tier `ValueError` escaping here would surface as a traceback, not as a diagnosis.

    Each pass catches its own exception type at the CLI boundary, so the resolver's refusal is
    re-raised as that type — with both paths still named in the message.
    """
    (tmp_path / SOURCES_CSV).write_text(",".join(SourceRow.model_fields) + "\n")
    (tmp_path / LICENSING_CSV).write_text(",".join(SourceRow.model_fields) + "\n")

    with pytest.raises(_PassError) as caught:
        sources_path(tmp_path, error=_PassError)
    assert SOURCES_CSV in str(caught.value) and LICENSING_CSV in str(caught.value)

    with pytest.raises(_PassError):
        record_source_terms(["ensembl"], "resolution", tmp_path, error=_PassError)
