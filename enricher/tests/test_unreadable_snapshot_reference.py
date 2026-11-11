"""RM432: a snapshot reader handed a reference it cannot read raises, never answers "nothing found".

`gene_metrics.lookup_snapshot` returned `{}` and `civic_refutation.civic_snapshot_rows` returned `[]` for a
reference with no parquet behind it, the same value a lookup that ran and matched nothing returns. A caller
could not tell the two apart (`@unreachable-not-absent`). Both now raise the built-in `FileNotFoundError`,
naming the path; `{}`/`[]` keep meaning "read, and nothing matched". The three callers inside the tier catch
it and report could-not-read: the gene-metrics pass treats the snapshot as not consulted, the refutation
check is skipped, and the citations pass says it maps variants from the curated table alone.
"""

import logging
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import civic_citations, gene_metrics
from just_dna_enricher.civic_citations import plan_subjects
from just_dna_enricher.civic_refutation import civic_snapshot_rows, compare_refutations
from just_dna_enricher.gene_metrics import enrich_gene_metrics, lookup_snapshot
from just_dna_enricher.locations import SNAPSHOT_DATA_DIRNAME


def _not_a_snapshot(tmp_path: Path) -> Path:
    """A directory shaped like a snapshot with no parquet in it: the mistyped or half-provisioned path."""
    empty = tmp_path / "not_a_snapshot"
    (empty / SNAPSHOT_DATA_DIRNAME).mkdir(parents=True)
    return empty


# ── the two readers ─────────────────────────────────────────────────────────────────────────────────


def test_the_constraint_reader_raises_on_a_reference_it_cannot_read(tmp_path: Path) -> None:
    missing = _not_a_snapshot(tmp_path)
    with pytest.raises(FileNotFoundError) as caught:
        lookup_snapshot(missing, ["BRCA1"])
    assert str(missing) in str(caught.value)
    with pytest.raises(FileNotFoundError):
        lookup_snapshot(tmp_path / "never_existed", ["BRCA1"])


def test_the_constraint_reader_still_answers_empty_when_it_read_and_matched_nothing(tmp_path: Path) -> None:
    data = tmp_path / "snap" / SNAPSHOT_DATA_DIRNAME
    data.mkdir(parents=True)
    pl.DataFrame({"gene": ["TP53"], "constraint_flags": [None]}).write_parquet(data / "x.parquet")
    assert lookup_snapshot(tmp_path / "snap", ["NOTAGENE"]) == {}


def test_the_civic_reader_raises_on_a_reference_it_cannot_read(tmp_path: Path) -> None:
    missing = _not_a_snapshot(tmp_path)
    with pytest.raises(FileNotFoundError) as caught:
        civic_snapshot_rows(missing)
    assert str(missing) in str(caught.value)
    with pytest.raises(FileNotFoundError):
        civic_snapshot_rows(tmp_path / "never_existed.parquet")


# ── the three callers: could-not-read, never empty ──────────────────────────────────────────────────


def test_the_gene_metrics_pass_reads_an_unreadable_snapshot_as_not_consulted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Offline, with a snapshot that was located and then could not be read, nothing was consulted: no
    `not_found` row stamped with a release nobody opened, and the gene is named as never asked."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion,gene\nrs1,A/G,risk,x,BRCA1\n")
    gone = _not_a_snapshot(tmp_path)
    monkeypatch.setattr(gene_metrics, "resolve_constraint_reference", lambda _cache: gone)
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.gene_metrics"):
        result = enrich_gene_metrics(spec, offline=True, constraint_cache=tmp_path / "cache")
    assert result.rows == []
    assert result.unconsulted == ["BRCA1"]
    assert any("could not be read" in r.getMessage() and str(gone) in r.getMessage() for r in caplog.records)


def test_the_refutation_check_is_skipped_and_says_the_snapshot_could_not_be_read(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    gone = _not_a_snapshot(tmp_path)
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.civic_refutation"):
        assert compare_refutations([], [], reference=gone) is None
    assert any("could not be read" in r.getMessage() and str(gone) in r.getMessage() for r in caplog.records)


def test_the_citations_pass_says_it_mapped_from_the_curated_table_alone(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A mistyped `--civic-snapshot` used to fall back to the curated table for every variant, silently, so
    the operator believed the snapshot had been read."""
    gone = _not_a_snapshot(tmp_path)
    with caplog.at_level(logging.WARNING, logger=civic_citations.__name__):
        assert plan_subjects([], [], reference=gone) == ([], 0)
    messages = [r.getMessage() for r in caplog.records]
    assert any("could not be read" in m and str(gone) in m and "curated" in m for m in messages), messages
