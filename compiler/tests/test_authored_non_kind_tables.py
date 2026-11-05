"""The registry of authored tables that are not table kinds (RM357): `tables.AUTHORED_NON_KIND_TABLES`.

`overrides.csv`, `meta.csv` and `model_organisms.csv` are written by a human, keyed, and never lead
tables. Before RM357 each had its own loader copy and about ten lists named them by hand. Every list is
now derived from the registry, and each test here compares the registry against a set it did **not**
produce (`@registry-completeness`): the authored models the format tier's reference walks, the input
files, the draftable files, the artifact listing. A fourth such table added to one place and not the
registry fails here instead of going silently missing from a list.
"""

import shutil
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import (
    _CITING_TABLE_KINDS,
    _GENE_BEARING_TABLE_KINDS,
    _INPUT_FILES,
    _KNOWN_SPEC_FILES,
    _TABLE_DUPE_KEYS,
    _TABLE_KINDS,
    ARTIFACT_PARQUETS,
    AUTHORED_NON_KIND_TABLES,
    LEAD_PARQUETS,
    SNP_CORE_PARQUETS,
    compile_module,
    content_signature,
    load_authored_table,
    reverse_module,
    table_bindings,
    validate_spec,
)
from just_dna_compiler.draft import DRAFTABLE
from just_dna_format.base import AuthoredModel
from just_dna_format.binning import MeasureBinRow
from just_dna_format.layout import SOURCES_CSV, sidecar_spellings
from just_dna_format.reference import _ALL_MODELS, _AUTHORED_NON_KIND_MODELS
from just_dna_format.spec import StudyRow, VariantRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

_REGISTRY_CSVS = {table.csv for table in AUTHORED_NON_KIND_TABLES}
_REGISTRY_MODELS = {table.model for table in AUTHORED_NON_KIND_TABLES}
_KIND_CSVS = {csv_name for csv_name, _parquet, _model in _TABLE_KINDS}
_CORE_CSVS = set(SNP_CORE_PARQUETS)


# ── the registry against sets it did not produce ─────────────────────────────────────────────────


def test_the_registry_is_every_authored_model_that_is_neither_core_nor_a_kind() -> None:
    """The format tier's reference walk, minus the SNP core, the kinds and the abstract binning base."""
    kinds = {model for _csv, _parquet, model in _TABLE_KINDS}
    walked = {
        model
        for model in _ALL_MODELS.values()
        if isinstance(model, type) and issubclass(model, AuthoredModel) and model not in kinds
    }
    assert walked - {VariantRow, StudyRow, MeasureBinRow} == _REGISTRY_MODELS
    # The format tier cannot import the compiler, so its group is declared there; this is the equality.
    assert set(_AUTHORED_NON_KIND_MODELS.values()) == _REGISTRY_MODELS


def test_every_input_file_outside_the_core_and_the_kinds_is_a_registry_table() -> None:
    assert set(_INPUT_FILES) - {"module_spec.yaml"} - _CORE_CSVS - _KIND_CSVS == _REGISTRY_CSVS


def test_every_draftable_file_outside_the_core_the_kinds_and_the_licence_table_is_a_registry_table() -> None:
    rest = set(DRAFTABLE) - _CORE_CSVS - _KIND_CSVS - set(sidecar_spellings(SOURCES_CSV))
    assert rest == _REGISTRY_CSVS
    assert all(DRAFTABLE[table.csv] is table.model for table in AUTHORED_NON_KIND_TABLES)


def test_the_artifact_listing_ends_with_the_registry_parquets_in_registry_order() -> None:
    """Registry order is the `manifest.artifact.files` listing order, appended last."""
    tail = [parquet for table in AUTHORED_NON_KIND_TABLES for parquet in table.parquets]
    assert list(ARTIFACT_PARQUETS[-len(tail) :]) == tail
    assert {
        table.csv: table.parquets for table in AUTHORED_NON_KIND_TABLES
    }.items() <= table_bindings().items()


def test_no_registry_table_is_a_lead_table_or_feeds_the_published_gene_facet() -> None:
    parquets = {parquet for table in AUTHORED_NON_KIND_TABLES for parquet in table.parquets}
    assert not parquets & set(LEAD_PARQUETS)
    assert not _REGISTRY_CSVS & {csv_name for csv_name, _model in _GENE_BEARING_TABLE_KINDS}


def test_every_registry_table_is_keyed_known_and_cites_exactly_when_it_declares_pmid() -> None:
    assert _REGISTRY_MODELS <= set(_TABLE_DUPE_KEYS)
    assert _REGISTRY_CSVS <= _KNOWN_SPEC_FILES
    citing = {csv_name for csv_name, _model in _CITING_TABLE_KINDS}
    assert citing & _REGISTRY_CSVS == {table.csv for table in AUTHORED_NON_KIND_TABLES if table.cites}
    for table in AUTHORED_NON_KIND_TABLES:
        assert table.cites is ("pmid" in table.model.model_fields), table.csv


# ── the one loader ───────────────────────────────────────────────────────────────────────────────


def test_an_absent_table_loads_as_nothing_and_an_empty_one_is_refused(tmp_path: Path) -> None:
    for table in AUTHORED_NON_KIND_TABLES:
        assert load_authored_table(tmp_path, table.csv) == ([], [], [])
        header = ",".join(name for name in table.model.model_fields if not name.startswith("_"))
        (tmp_path / table.csv).write_text(header + "\n", encoding="utf-8")
        rows, errors, _warnings = load_authored_table(tmp_path, table.csv)
        assert rows == [] and errors == [f"{table.csv} is present but has no rows."], (table.csv, errors)


def test_a_malformed_overlay_is_not_applied_half_parsed(tmp_path: Path) -> None:
    """A parse error leaves the overlay incomplete, so `validate` reports the parse error and applies
    nothing: the parsed rows are kept only for a table that cites, and the overlay does not."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / "hfe_hemochromatosis", spec)
    (spec / "verification.json").unlink(missing_ok=True)
    subject = pl.read_csv(spec / "resolution.csv", infer_schema_length=0).row(0, named=True)["variant_key"]
    why = "re-checked by hand,curator,2026-11-04"
    (spec / "overrides.csv").write_text(
        "table,subject,member,field,operation,value,reason,decided_by,decided_at\n"
        f"resolution.csv,{subject},0,start,update,not-a-number,{why}\n"
        f"resolution.csv,{subject},0,source,bogusop,manual,{why}\n",
        encoding="utf-8",
    )
    rows, errors, _warnings = load_authored_table(spec, "overrides.csv")
    assert rows == [] and errors, errors
    result = validate_spec(spec)
    assert [e for e in result.errors if e.startswith("overrides.csv")] == errors, result.errors


# ── reverse reads every registry table back ──────────────────────────────────────────────────────


def _module_with_every_registry_table(spec: Path) -> Path:
    """hfe_hemochromatosis with one row in each registry table, so the reverse loop meets all three."""
    shutil.copytree(_EXAMPLES / "hfe_hemochromatosis", spec)
    (spec / "verification.json").unlink(missing_ok=True)
    first = pl.read_csv(spec / "resolution.csv", infer_schema_length=0).row(0, named=True)
    (spec / "overrides.csv").write_text(
        "table,subject,member,field,operation,value,reason,decided_by,decided_at\n"
        f"resolution.csv,{first['variant_key']},0,source,update,manual,re-checked by hand,curator,2026-11-04\n",
        encoding="utf-8",
    )
    (spec / "meta.csv").write_text(
        'members,conclusion\n"variants[gene=HFE]",Every HFE row in this module.\n', encoding="utf-8"
    )
    (spec / "model_organisms.csv").write_text(
        "gene,orthologue,species,model_type,lifespan_effect\nHFE,Hfe,Mus musculus,knockout,not reported\n",
        encoding="utf-8",
    )
    return spec


def test_reverse_writes_every_registry_table_back_and_the_round_trip_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _module_with_every_registry_table(tmp_path / "spec")
    first = compile_module(spec, tmp_path / "out")
    assert first.success, first.errors
    back = reverse_module(tmp_path / "out", tmp_path / "back")
    for table in AUTHORED_NON_KIND_TABLES:
        assert (back / table.csv).is_file(), table.csv
        assert load_authored_table(back, table.csv)[0] == load_authored_table(spec, table.csv)[0], table.csv
    second = compile_module(back, tmp_path / "out2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert content_signature(back) == content_signature(spec)
    assert validate_spec(back).valid
