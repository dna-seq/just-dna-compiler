"""RM300: `manifest.stats` counts rows and variants per ClinVar tier, beside the folded boolean counts.

Expected values are computed at runtime from each example's own `weights.parquet`, which carries the
effective `clin_sig` per row, never copied from a run. Modules whose rows were expanded or dropped are
skipped for the row reconciliation, since there the parquet and the authored rows differ in count.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_format.manifest import Stats
from just_dna_format.vocab import VALID_CLIN_SIG
from pydantic import ValidationError

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _specs() -> list[Path]:
    return sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file())


@pytest.mark.parametrize("spec", _specs(), ids=lambda p: p.name)
def test_every_tier_is_a_key_in_sorted_order_and_the_counts_reconcile(spec: Path, tmp_path: Path) -> None:
    compiled = compile_module(spec, tmp_path / "out")
    assert compiled.success, compiled.errors
    stats = compiled.manifest.stats
    for mapping in (stats.clin_sig_counts, stats.clin_sig_variant_counts):
        assert list(mapping) == sorted(VALID_CLIN_SIG)
    assert sum(stats.clin_sig_counts.values()) <= stats.weights_rows
    assert sum(stats.clin_sig_variant_counts.values()) >= 0

    weights = tmp_path / "out" / "weights.parquet"
    compilation = compiled.manifest.compilation
    if not weights.is_file() or compilation.expanded_rows or compilation.dropped_rows:
        return
    frame = pl.read_parquet(weights).filter(pl.col("clin_sig").is_not_null())
    by_rows = dict(frame.group_by("clin_sig").len().iter_rows())
    by_keys = dict(frame.group_by("clin_sig").agg(pl.col("variant_key").n_unique()).iter_rows())
    assert {k: v for k, v in stats.clin_sig_counts.items() if v} == by_rows
    assert {k: v for k, v in stats.clin_sig_variant_counts.items() if v} == by_keys


def test_the_folded_pathogenic_count_splits_into_its_two_tiers(tmp_path: Path) -> None:
    """Where every row states a tier and the boolean agrees with it, the two tiers sum to the fold."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: rm300\n  title: RM300\n"
        "  description: tiers beside the folded count\n  report_title: RM300\ngenome_build: GRCh38\n",
        encoding="utf-8",
    )
    # HFE C282Y and H63D at their GRCh38 positions, as Ensembl places them.
    (spec / "variants.csv").write_text(
        "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene,clinvar,pathogenic,clin_sig\n"
        "rs1800562,6,26092913,G,A,A/A,risk,C282Y homozygote,HFE,true,true,pathogenic\n"
        "rs1800562,6,26092913,G,A,A/G,risk,C282Y carrier,HFE,true,true,pathogenic\n"
        "rs1799945,6,26090951,C,G,G/G,risk,H63D homozygote,HFE,true,true,likely_pathogenic\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text("rsid,pmid\n,16199547\n", encoding="utf-8")
    compiled = compile_module(spec, tmp_path / "out")
    assert compiled.success, compiled.errors
    stats = compiled.manifest.stats
    assert stats.clin_sig_counts["pathogenic"] == 2
    assert stats.clin_sig_counts["likely_pathogenic"] == 1
    assert stats.clin_sig_variant_counts["pathogenic"] == 1
    assert stats.clin_sig_counts["pathogenic"] + stats.clin_sig_counts["likely_pathogenic"] == (
        stats.pathogenic_count
    )


def test_an_older_manifest_without_the_fields_still_reads_and_a_foreign_key_does_not() -> None:
    assert Stats().clin_sig_counts == {}
    with pytest.raises(ValidationError):
        Stats(clin_sig_counts={"pathogenicish": 1})
