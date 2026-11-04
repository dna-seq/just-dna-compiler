"""The pmid/doi pair on every citing table, end to end (RM336).

The schema half (`schema/tests/test_pmid_doi_pair.py`) proves the rule on each model. This half proves
what the compiler owes it: every model that cites with a `pmid` carries the rule (an equality over the
walked registry, never a list), a `pmid=NONE` row and its `doi` survive compile → reverse → compile on
`studies.csv`, a binning kind, `pharm_variants.csv` and `gwas_effects.csv`, and two preprints on one
variant are two citations rather than a duplicate.

Modules are real reference examples copied into `tmp_path`; expected values are computed from them.
"""

import csv
import io
import json
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import _CITING_TABLE_KINDS, compile_module, reverse_module, validate_spec
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.integrity import gwas_effect_signature
from just_dna_format.literature import LiteratureRow
from just_dna_format.reference import _ALL_MODELS
from just_dna_format.spec import PMID_NONE, CitationPair

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HFE = _EXAMPLES / "hfe_hemochromatosis"
_HTT = _EXAMPLES / "htt_repeat_expansion"
_SLCO1B1 = _EXAMPLES / "pgx_slco1b1_simvastatin"

#: Two bioRxiv preprint DOIs, the shape longevitymap v2's 17 DOI-only studies take.
_DOI_A = "10.1101/2025.03.01.640000"
_DOI_B = "https://doi.org/10.1101/2025.03.30.25324899"


# ── the roster ──────────────────────────────────────────────────────────────────────────────────


def test_every_model_that_cites_carries_the_pair_rule() -> None:
    """`@registry-completeness`: an equality over the walked model registry, so the next model to
    declare a `pmid` (the meta-table, the model-organism table) fails here until it carries `doi` and
    `CitationPair`, and nothing is counted or listed by hand.

    **`LiteratureRow` is the one exemption, and it is not a citing row.** Its `pmid` is the article's
    identity in digits (what is being checked), and its `doi` is the registry's answer about that
    article — `NONE` there would be a row describing no article at all. The exemption is a named
    model, so a second exemption has to be argued here rather than slipping in.
    """
    exempt = {LiteratureRow}
    with_pmid = {model for model in _ALL_MODELS.values() if "pmid" in model.model_fields} - exempt
    with_rule = {
        model
        for model in _ALL_MODELS.values()
        if issubclass(model, CitationPair) and "doi" in model.model_fields
    }
    assert with_pmid, "the walk must see the citing models for this guard to mean anything"
    assert with_pmid == with_rule
    # And the compiler's derived citing roster is inside it, model for model.
    assert {model for _csv, model in _CITING_TABLE_KINDS} <= with_rule
    # The derived fact table is reached by the walk too, not only the authored kinds.
    assert GwasEffectRow in with_rule


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────


def _copy(source: Path, dest: Path) -> Path:
    dest.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file() and path.suffix in {".csv", ".yaml", ".json"}:
            (dest / path.name).write_bytes(path.read_bytes())
    return dest


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _with_preprint_studies(tmp_path: Path, *, second_doi: str = _DOI_B) -> Path:
    """The HFE module plus two DOI-only study rows on one variant it already cites."""
    spec = _copy(_HFE, tmp_path / "hfe")
    rows = [{**row, "doi": ""} for row in _rows(spec / "studies.csv")]
    rsid = rows[0]["rsid"]
    blank = dict.fromkeys(rows[0], "")
    rows += [
        {**blank, "rsid": rsid, "pmid": PMID_NONE, "doi": _DOI_A},
        {**blank, "rsid": rsid, "pmid": PMID_NONE, "doi": second_doi},
    ]
    _write(spec / "studies.csv", rows)
    return spec


def _round_trip(spec: Path, tmp_path: Path) -> tuple[Path, Path, dict, dict]:
    out, back, again = tmp_path / "out", tmp_path / "back", tmp_path / "again"
    first = compile_module(spec, out)
    assert first.success, first.errors
    reverse_module(out, back)
    second = compile_module(back, again)
    assert second.success, second.errors
    return (
        out,
        back,
        json.loads((out / "manifest.json").read_text()),
        json.loads((again / "manifest.json").read_text()),
    )


# ── round trips ─────────────────────────────────────────────────────────────────────────────────


def test_a_preprint_study_round_trips(tmp_path: Path) -> None:
    spec = _with_preprint_studies(tmp_path)
    out, back, first, second = _round_trip(spec, tmp_path)

    authored = [(r["pmid"], r["doi"]) for r in _rows(spec / "studies.csv") if r["pmid"] == PMID_NONE]
    parquet = pl.read_parquet(out / "studies.parquet").filter(pl.col("pmid") == PMID_NONE)
    assert list(zip(parquet["pmid"], parquet["doi"], strict=True)) == authored
    reversed_ = [(r["pmid"], r["doi"]) for r in _rows(back / "studies.csv") if r["pmid"] == PMID_NONE]
    assert reversed_ == authored
    assert first["content_signature"] == second["content_signature"]
    assert first["artifact"]["digest"] == second["artifact"]["digest"]


def test_a_preprint_cited_bin_round_trips(tmp_path: Path) -> None:
    """The binning kinds go through the generic writer, so this proves the generic path carries
    `doi` rather than assuming it."""
    spec = tmp_path / "htt"
    spec.mkdir()
    (spec / "module_spec.yaml").write_bytes((_HTT / "module_spec.yaml").read_bytes())
    rows = [
        {**row, "pmid": "" if row["unresolved"] == "true" else PMID_NONE}
        | {"doi": "" if row["unresolved"] == "true" else _DOI_A}
        for row in _rows(_HTT / "repeat_alleles.csv")
    ]
    _write(spec / "repeat_alleles.csv", rows)
    out, back, first, second = _round_trip(spec, tmp_path)

    assert [(r["pmid"], r["doi"]) for r in _rows(back / "repeat_alleles.csv")] == [
        (r["pmid"], r["doi"]) for r in rows
    ]
    assert first["content_signature"] == second["content_signature"]
    # The `doi` an author filled is content, so it is inside the authored identity.
    plain = compile_module(_HTT, tmp_path / "plain")
    assert plain.success
    assert (
        json.loads((tmp_path / "plain" / "manifest.json").read_text())["content_signature"]
        != (first["content_signature"])
    )


def test_a_preprint_cited_pharm_row_round_trips(tmp_path: Path) -> None:
    spec = _copy(_SLCO1B1, tmp_path / "pharm")
    rows = [
        {
            **row,
            "pmid": PMID_NONE if row["phenotype_category"] == "Toxicity" else "",
            "doi": _DOI_A if row["phenotype_category"] == "Toxicity" else "",
        }
        for row in _rows(spec / "pharm_variants.csv")
    ]
    assert any(r["pmid"] == PMID_NONE for r in rows), "the example must carry a Toxicity row"
    _write(spec / "pharm_variants.csv", rows)
    out, back, first, second = _round_trip(spec, tmp_path)

    parquet = pl.read_parquet(out / "pharm_variants.parquet")
    assert "doi" in parquet.columns
    assert [(r["pmid"], r["doi"]) for r in _rows(back / "pharm_variants.csv")] == [
        (r["pmid"], r["doi"]) for r in rows
    ]
    assert first["content_signature"] == second["content_signature"]
    assert first["artifact"]["digest"] == second["artifact"]["digest"]


def test_a_gwas_effects_doi_reaches_the_parquet_and_an_unset_one_moves_no_signature(tmp_path: Path) -> None:
    """Half price: a derived table. An empty `doi` column must hash exactly as the table did before the
    column existed, or every published `gwas_effects` signature would move."""
    rows = _rows(_HFE / "gwas_effects.csv")
    with_column = [{**row, "doi": ""} for row in rows]
    before = gwas_effect_signature([GwasEffectRow.model_validate(_clean(r)) for r in rows])
    after = gwas_effect_signature([GwasEffectRow.model_validate(_clean(r)) for r in with_column])
    assert before == after

    spec = _copy(_HFE, tmp_path / "gwas")
    cited = next(i for i, r in enumerate(with_column) if r["pmid"])
    with_column[cited] = {**with_column[cited], "doi": _DOI_A}
    _write(spec / "gwas_effects.csv", with_column)
    out = tmp_path / "out"
    assert compile_module(spec, out).success
    parquet = pl.read_parquet(out / "gwas_effects.parquet")
    assert parquet.filter(pl.col("doi").is_not_null())["association_id"].to_list() == [
        with_column[cited]["association_id"]
    ]


def _clean(row: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in row.items() if value != ""}


# ── the duplicate-citation key ──────────────────────────────────────────────────────────────────


def _duplicate_warnings(spec: Path) -> list[str]:
    return [w for w in validate_spec(spec).warnings if "Duplicate (variant, pmid)" in w]


def test_two_preprints_on_one_variant_are_two_citations(tmp_path: Path) -> None:
    """`(variant_key, pmid)` reads every DOI-only row as `(v, NONE)`, so two different preprints on
    one variant were one key; the DOI is what tells them apart (`@a-cell-key-carries-the-value-when-
    two-rows-may-state-two-claims`)."""
    assert _duplicate_warnings(_with_preprint_studies(tmp_path / "a")) == []


def test_the_same_preprint_twice_is_still_a_duplicate(tmp_path: Path) -> None:
    warnings = _duplicate_warnings(_with_preprint_studies(tmp_path / "b", second_doi=_DOI_A))
    assert len(warnings) == 1
    assert PMID_NONE in warnings[0] and _DOI_A in warnings[0]
