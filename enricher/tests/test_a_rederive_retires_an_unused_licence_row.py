"""RM383: after a re-derivation, a derived layer's licence row for a source no committed row names is retired.

Measured regenerating `reference_examples/mt_common_deletion` against the split Ensembl snapshot: the two
point variants were back-filled from ClinVar before and from the Ensembl snapshot after, and `enrich
--rederive` left the old `clinvar,resolution` row in `licensing.csv` though no resolution row named ClinVar
any more. `sources.csv` travels with the module and means *this module uses this source*
(`@write-the-sourcerow`), so the compile warned `source_row_unused` about a row the pass itself wrote.

`--rederive` is the declaration: it re-answers every row, so the committed table is the pass's whole
answer, and a row of the pass's own (a source with a terms constant, at the pass's layer) that no
committed row names is retired inside the table's commit, with a log line naming it. A plain enrich
merges and never retires (merge-not-clobber). The fixture is the example itself, with an Ensembl cache
holding the two loci exactly as the split release does.
"""

import ast
import logging
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import _load_csv_rows, compile_module
from just_dna_enricher import licensing
from just_dna_enricher.enrich import enrich
from just_dna_format.layout import SOURCES_CSV, preferred_spelling
from just_dna_format.sources import SourceRow

#: "No snapshot" means no ambient one either: a developer's cache base would answer for a missing lane.
pytestmark = pytest.mark.usefixtures("no_ambient_caches")

_EXAMPLE = Path(__file__).parents[2] / "reference_examples" / "mt_common_deletion"
_LICENCE_CSV = preferred_spelling(SOURCES_CSV)
#: The split release's two loci (`homo_sapiens-chrMT.parquet`, ensembl-variation-2026_07_13-vep116.0).
_ENSEMBL = {
    "id": ["rs199474657", "rs199476133"],
    "chrom": ["MT", "MT"],
    "start": [3243, 8993],
    "ref": ["A", "T"],
    "alt": ["G", "G"],
}


def _module(tmp_path: Path) -> Path:
    spec = tmp_path / "mt_common_deletion"
    shutil.copytree(_EXAMPLE, spec)
    return spec


def _cache(tmp_path: Path) -> Path:
    (tmp_path / "ens" / "data").mkdir(parents=True)
    pl.DataFrame(_ENSEMBL).write_parquet(tmp_path / "ens" / "data" / "homo_sapiens-chrMT.parquet")
    return tmp_path / "ens"


def _enrich(spec: Path, ensembl: Path, **kwargs):
    options = {
        "offline": True,
        "ensembl_cache": ensembl,
        "clinvar_cache": spec.parent / "no-clinvar",
        "clinvar_gkm_cache": spec.parent / "no-gkm",
        "download": False,
        "use_gnomad": False,
        "verify_ref": False,
        "verify_rsids": False,
        "verify_clinsig": False,
        "verify_datasets": False,
        "mint_vrs": False,
    }
    options.update(kwargs)
    return enrich(spec, **options)


def _licence(spec: Path) -> set[tuple[str, str]]:
    rows, errors, _ = _load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert errors == []
    return {(r.source, r.layer) for r in rows}


def test_a_rederive_retires_the_licence_row_no_committed_row_names(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    spec = _module(tmp_path)
    assert ("clinvar", "resolution") in _licence(spec)
    with caplog.at_level(logging.INFO, logger="just_dna_enricher"):
        _enrich(spec, _cache(tmp_path), rederive=True)
    assert ("clinvar", "resolution") not in _licence(spec)
    assert ("ensembl", "resolution") in _licence(spec)
    assert any("clinvar,resolution" in r.getMessage() and "RM383" in r.getMessage() for r in caplog.records)
    compiled = compile_module(spec, tmp_path / "out")
    assert compiled.success, compiled.errors
    assert not [w for w in compiled.warnings if "source_row_unused" in str(getattr(w, "code", w))]


def test_a_plain_enrich_never_retires_a_row(tmp_path: Path) -> None:
    """Merge-not-clobber: only the run that re-answered every row may say a source answers none."""
    spec = _module(tmp_path)
    (spec / "resolution.csv").unlink()
    _enrich(spec, _cache(tmp_path))
    assert {("clinvar", "resolution"), ("ensembl", "resolution")} <= _licence(spec)


def test_a_rederive_that_could_ask_nothing_retires_nothing(tmp_path: Path) -> None:
    """Keyed on the committed table: a subject nobody could ask keeps its rows, and they name ClinVar.

    An rsID-only subject, so that with no cache and `--offline` no link is consulted and the recorded
    ClinVar placement is carried forward (`@rederive-never-shortens`).
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text((_EXAMPLE / "module_spec.yaml").read_text(), encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs199474657,G,risk,c,MT-TL1\n", encoding="utf-8"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs199474657,1977311\n", encoding="utf-8")
    shutil.copy(_EXAMPLE / _LICENCE_CSV, spec / _LICENCE_CSV)
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status\n"
        "rs199474657,rs199474657,MT,3243,A,G,GRCh38,0,clinvar,clinvar,resolved\n",
        encoding="utf-8",
    )
    _enrich(spec, tmp_path / "no-ensembl", rederive=True)
    assert ("clinvar", "resolution") in _licence(spec)


def test_a_curators_row_for_a_source_with_no_terms_constant_is_never_retired(tmp_path: Path) -> None:
    """The relabel's own filter: only a row the pass writes (a source in TERMS_BY_SOURCE) is the pass's."""
    spec = _module(tmp_path)
    path = spec / _LICENCE_CSV
    rows, _, _ = _load_csv_rows(path, SourceRow, _LICENCE_CSV)
    # The example's first row need not be at the `resolution` layer (RM379 puts its concordance rows
    # first), so the curator's row is copied from one that is.
    template = next(row for row in rows if row.layer == "resolution")
    hand = template.model_copy(update={"source": "our_lab", "dataset": None})
    assert "our_lab" not in licensing.TERMS_BY_SOURCE
    licensing.write_sources_csv([*rows, hand], path)
    _enrich(spec, _cache(tmp_path), rederive=True)
    assert ("our_lab", "resolution") in _licence(spec)


def test_every_record_table_sources_call_states_whether_it_answered_every_row() -> None:
    """The guard, over a walked set: every caller says, by keyword, whether its commit is the whole answer."""
    unstated: list[str] = []
    calls = 0
    root = Path(licensing.__file__).parent
    for path in sorted(p for p in root.rglob("*.py") if "generated" not in p.relative_to(root).parts):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            if name != "record_table_sources":
                continue
            calls += 1
            if "answered_every_row" not in {kw.arg for kw in node.keywords}:
                unstated.append(f"{path.relative_to(root)}:{node.lineno}")
    assert calls, "the walk found no call at all, so it is reading the wrong tree"
    assert unstated == []
