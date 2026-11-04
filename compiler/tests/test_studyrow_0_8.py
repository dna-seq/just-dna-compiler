"""The 0.8 `StudyRow` batch (PROPOSAL_0_8_PT2 §3 items 10–17, §5 A5).

longevitymap v2 sorts, weighs and tiers its evidence by facts a `studies.csv` row could not state
before 0.8: how many were analysed and in what unit (RM325), which outcome was measured (RM326), in
which ancestry (RM328), over which age band (RM329), inside which stratum (RM330), on which LD proxy
(RM331), and in what unit an effect is stated (RM332). Each is an optional authored column, so each
owes the same proof, and this file gives it once per column group:

* the column reaches `studies.parquet` with the authored value, row for row;
* `compile → reverse → compile` writes it back and lands on the same `artifact.digest` and
  `content_signature` (Principle 7);
* a stated cell is authored content and moves `content_signature`, while a module that never writes the
  column, or writes the header with every cell empty, keeps the signature it had (P3/P8);
* the new columns come after every 0.7 column, so no 0.7 parquet column changes position.

The fixture is a copy of `reference_examples/hfe_hemochromatosis`, which carries 33 real study rows over
eleven variants and a real `resolution.csv`. The cells are generated here and read back off the CSV the
test wrote, so every expectation is computed from what was authored rather than restated.
"""

import csv
import shutil
from collections.abc import Callable
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import (
    _cross_validate_studies,
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)
from just_dna_compiler.compiler.subjects import module_subjects
from just_dna_format.base import field_first_seen, field_vocabularies
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.pgs import VALID_TRAINING_ANCESTRY, PgsRow
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.vocab import (
    OUTCOME_STRIP_CELLS,
    RECOMMENDED_PHENOTYPE_CLASSES,
    VALID_SUPERPOPULATIONS,
)
from pydantic import ValidationError

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"

#: A fill writes the new cells of one study row in place, given the row's position in the file.
Fill = Callable[[int, dict[str, str]], None]


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _write_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _spec(tmp_path: Path, name: str, columns: tuple[str, ...], fill: Fill | None) -> Path:
    """A copy of the HFE example whose `studies.csv` carries `columns`, filled by `fill` (or empty)."""
    spec = tmp_path / name
    shutil.copytree(_EXAMPLE, spec)
    # The example is closed, and its attestation binds the bytes this edit changes; the attestation is
    # not what this file is about, so the copy carries none.
    (spec / "verification.json").unlink()
    header, rows = _read_rows(spec / "studies.csv")
    for i, row in enumerate(rows):
        for column in columns:
            row[column] = ""
        if fill is not None:
            fill(i, row)
    _write_rows(spec / "studies.csv", header + list(columns), rows)
    return spec


def _authored(spec: Path, columns: tuple[str, ...]) -> list[dict[str, str | None]]:
    """The authored cells, row by row; an empty cell is the unstated `None`."""
    _, rows = _read_rows(spec / "studies.csv")
    return [{c: row.get(c) or None for c in columns} for row in rows]


def _fill_sample_size(i: int, row: dict[str, str]) -> None:
    """Three shapes in turn: a case-control count in individuals, a parental count in lives, nothing."""
    if i % 3 == 0:
        row["sample_size"] = str(1000 + 7 * i)
        row["sample_unit"] = "individuals"
        row["n_cases"] = str(100 + i)
    elif i % 3 == 1:
        row["sample_size"] = str(1_012_240 + i)
        row["sample_unit"] = "lives"


#: v2's twelve classes as RM326 spells them; the test restates them so a drift in either is caught.
_V2_CLASSES: frozenset[str] = frozenset(
    {
        "EXTREME_SURVIVAL_CC",
        "PARENTAL_LIFESPAN",
        "OWN_SURVIVAL",
        "VIABILITY_AF",
        "HEALTHSPAN",
        "MULTIVARIATE_AGEING",
        "FAMILIAL",
        "DISEASE_DEPLETION",
        "RARE_BURDEN",
        "EVOLUTIONARY",
        "MR",
        "BIOMARKER",
    }
)


def _fill_phenotype_class(i: int, row: dict[str, str]) -> None:
    """Every recommended class in turn, with every fourth row left unstated."""
    if i % 4 != 3:
        row["phenotype_class"] = sorted(_V2_CLASSES)[i % len(_V2_CLASSES)]


def _fill_ancestry(i: int, row: dict[str, str]) -> None:
    """One code, two codes (a trans-ethnic study lists both, in the authored order), or nothing."""
    row["ancestry"] = ("EUR", "EAS|EUR", "AFR", "", "EUR|AMR|SAS")[i % 5]


def _fill_age_band(i: int, row: dict[str, str]) -> None:
    """Timmers 2019's three parental bands (the last open above), a participant ceiling, and nothing."""
    band = (
        ("40", "60", "parent"),
        ("60", "80", "parent"),
        ("80", "", "parent"),
        ("", "", ""),
        ("", "62.5", "participant"),
    )
    row["age_min"], row["age_max"], row["age_of"] = band[i % len(band)]


def _fill_stratum(i: int, row: dict[str, str]) -> None:
    """Pilling's parent-sex strata, CHAMP's sex stratum, and nothing."""
    pair = (("parent_sex", "father"), ("parent_sex", "mother"), ("sex", "male"), ("", ""))
    row["stratum"], row["stratum_level"] = pair[i % len(pair)]


def _fill_proxy(i: int, row: dict[str, str]) -> None:
    """A proxy on every other row, two different ones, never the row's own rsID."""
    if i % 2 == 0:
        row["proxy_rsid"] = "rs111033563" if row["rsid"] != "rs111033563" else "rs1800562"
        if i % 4 == 2:
            row["proxy_rsid"] = "rs4970836" if row["rsid"] else row["proxy_rsid"]


#: Units by variant, so the weights join meets every case: all stating rows agree, two disagree, one
#: states and the rest do not, and none states (the variants left out of this map).
_UNITS: dict[str, tuple[str, ...]] = {
    "rs776994377": ("log-odds per allele", "log-odds per allele", "log-odds per allele"),
    "rs759524388": ("log-odds per allele", "-ln HR per allele", ""),
    "rs1800562": ("", "years of parental lifespan per allele", ""),
}


def _fill_effect_unit(i: int, row: dict[str, str]) -> None:
    units = _UNITS.get(row["rsid"])
    if units is not None:
        row["effect_unit"] = units[_nth_for_variant(i, row["rsid"])]


def _nth_for_variant(i: int, rsid: str) -> int:
    """Which of its variant's study rows row `i` is (the example lists each variant's rows together)."""
    _, rows = _read_rows(_EXAMPLE / "studies.csv")
    return sum(1 for row in rows[:i] if row["rsid"] == rsid)


#: Each column group this batch adds, with a fill that gives it distinct stated values and empty
#: cells, and how a parquet cell reads back as the CSV cell it came from.
_GROUPS: dict[str, tuple[tuple[str, ...], Fill]] = {
    "RM325": (("sample_size", "sample_unit", "n_cases"), _fill_sample_size),
    "RM326": (("phenotype_class",), _fill_phenotype_class),
    "RM328": (("ancestry",), _fill_ancestry),
    "RM329": (("age_min", "age_max", "age_of"), _fill_age_band),
    "RM330": (("stratum", "stratum_level"), _fill_stratum),
    "RM331": (("proxy_rsid",), _fill_proxy),
    "RM332": (("effect_unit",), _fill_effect_unit),
}


def _as_cell(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return "|".join(str(v) for v in value) or None
    return str(value)


# ── the generic proof, once per column group ────────────────────────────────────────────────────────


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_fixture_carries_distinct_values_and_empty_cells(tmp_path: Path, item: str) -> None:
    """The fixture earns its place, or the round trip below asserts over a uniform column."""
    columns, fill = _GROUPS[item]
    authored = _authored(_spec(tmp_path, "filled", columns, fill), columns)
    for column in columns:
        values = [cells[column] for cells in authored]
        assert None in values, column
        assert len({v for v in values if v is not None}) > 1, column


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_columns_are_0_8_and_come_after_every_0_7_column(item: str) -> None:
    columns, _ = _GROUPS[item]
    first_seen = field_first_seen(StudyRow)
    fields = list(StudyRow.model_fields)
    assert {c: first_seen[c] for c in columns} == dict.fromkeys(columns, "0.8.0")
    last_old = max(i for i, name in enumerate(fields) if first_seen[name] != "0.8.0")
    assert all(fields.index(c) > last_old for c in columns)


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_columns_reach_studies_parquet_row_for_row(tmp_path: Path, item: str) -> None:
    columns, fill = _GROUPS[item]
    spec = _spec(tmp_path, "filled", columns, fill)
    validation = validate_spec(spec, strict=True)
    assert validation.valid, validation.errors
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors

    df = pl.read_parquet(tmp_path / "out" / "studies.parquet")
    # `neg_log10_p` is the last 0.7 column; a reader by position sees every 0.7 column where it was.
    last_0_7 = df.columns.index("neg_log10_p")
    assert all(df.columns.index(c) > last_0_7 for c in columns)
    materialized = [{c: _as_cell(row[c]) for c in columns} for row in df.iter_rows(named=True)]
    authored = _authored(spec, columns)
    # Numbers come back as numbers: compare on the value, not the spelling.
    assert [{c: (float(v) if v and c in _NUMERIC else v) for c, v in r.items()} for r in materialized] == [
        {c: (float(v) if v and c in _NUMERIC else v) for c, v in r.items()} for r in authored
    ]


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_columns_survive_reverse_and_recompile_to_a_fixed_point(tmp_path: Path, item: str) -> None:
    columns, fill = _GROUPS[item]
    spec = _spec(tmp_path, "filled", columns, fill)
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")

    header, _ = _read_rows(tmp_path / "rev" / "studies.csv")
    assert set(columns) <= set(header)
    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert content_signature(tmp_path / "rev") == content_signature(spec)


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_columns_are_authored_content_and_an_unwritten_one_hashes_as_before(
    tmp_path: Path, item: str
) -> None:
    columns, fill = _GROUPS[item]
    baseline = content_signature(_EXAMPLE)
    assert content_signature(_spec(tmp_path, "empty", columns, None)) == baseline
    assert content_signature(_spec(tmp_path, "filled", columns, fill)) != baseline


#: Columns whose parquet type is a number, so the comparison above reads them as one.
_NUMERIC: frozenset[str] = frozenset({"sample_size", "n_cases", "age_min", "age_max"})


# ── RM325: sample size, its unit, and the case count ──────────────────────────────────────────────


def _study(**cells: object) -> StudyRow:
    return StudyRow(rsid="rs1800562", pmid="10381492", **cells)


def test_sample_unit_is_closed_over_individuals_and_lives() -> None:
    assert field_vocabularies(StudyRow)["sample_unit"] == {
        "name": "sample_unit",
        "options": ["individuals", "lives"],
        "closed": True,
    }
    for unit in ("individuals", "lives"):
        assert _study(sample_size=10, sample_unit=unit).sample_unit == unit
    with pytest.raises(ValidationError, match="sample_unit"):
        _study(sample_size=10, sample_unit="people")


def test_a_sample_size_with_no_unit_is_refused() -> None:
    """`@weight-has-no-unit`: parental-lifespan studies count lives, two per participant."""
    with pytest.raises(ValidationError, match="sample_unit"):
        _study(sample_size=389166)
    # A unit with no magnitude names an instrument nothing was measured on, and is harmless.
    assert _study(sample_unit="lives").sample_size is None


def test_more_cases_than_were_analysed_is_refused() -> None:
    with pytest.raises(ValidationError, match="n_cases"):
        _study(sample_size=100, sample_unit="individuals", n_cases=101)
    # Every analysed person a case is legal (a case-only design), and so is a case count alone.
    assert _study(sample_size=100, sample_unit="individuals", n_cases=100).n_cases == 100
    assert _study(n_cases=3484).sample_size is None


def test_a_negative_count_is_refused() -> None:
    for cells in ({"sample_size": -1, "sample_unit": "lives"}, {"n_cases": -1}):
        with pytest.raises(ValidationError):
            _study(**cells)


# ── RM326: the outcome a study measured ─────────────────────────────────────────────────────────


def _summary(tmp_path: Path, spec: Path, *, strict: bool) -> dict[str, int]:
    result = compile_module(spec, tmp_path / f"out_{strict}", strict=strict)
    assert result.success, result.errors
    return dict(result.manifest.compilation.warnings_summary)


def test_phenotype_class_is_open_over_v2s_twelve() -> None:
    marker = field_vocabularies(StudyRow)["phenotype_class"]
    assert marker["closed"] is False
    assert set(marker["options"]) == _V2_CLASSES
    # Open: a class outside the twelve is a row, not a refusal (three real studies fit none of them).
    assert _study(phenotype_class="NOVEL_CLASS").phenotype_class == "NOVEL_CLASS"


@pytest.mark.parametrize("strict", [False, True])
def test_a_class_outside_the_recommended_set_warns_in_both_modes(tmp_path: Path, strict: bool) -> None:
    """v2 spells three classes two ways; the long form draws the warning, the recommended one does not."""

    def drift(i: int, row: dict[str, str]) -> None:
        row["phenotype_class"] = ("FAMILIAL_LONGEVITY", "MR_MEDIATOR", "FAMILIAL", "")[i % 4]

    spec = _spec(tmp_path, "drift", ("phenotype_class",), drift)
    summary = _summary(tmp_path, spec, strict=strict)
    assert summary.get("phenotype_class_unrecognized") == 1
    validation = validate_spec(spec, strict=strict)
    # `validate_spec` returns plain strings; the code is asserted on the manifest above, the text here.
    found = [w for w in validation.warnings if "phenotype_class outside the recommended set" in w]
    assert len(found) == 1
    # Each token is named once with its row count, and a recommended token is never named.
    _, rows = _read_rows(spec / "studies.csv")
    for token in ("FAMILIAL_LONGEVITY", "MR_MEDIATOR"):
        count = sum(1 for row in rows if row["phenotype_class"] == token)
        assert f"{token!r} ({count} rows)" in found[0]
    assert "'FAMILIAL'" not in found[0]


def test_a_module_with_no_variants_csv_gets_the_class_warning_too(tmp_path: Path) -> None:
    """A citation-only `studies.csv` beside a binning table is legal (RM47); its classes are checked too."""
    spec = tmp_path / "fmr1"
    shutil.copytree(_EXAMPLE.parent / "fmr1_cgg_repeat", spec)
    (spec / "verification.json").unlink()
    assert not (spec / "variants.csv").exists()
    header, rows = _read_rows(spec / "studies.csv")
    for row in rows:
        row["phenotype_class"] = "FAMILIAL_LONGEVITY"
    _write_rows(spec / "studies.csv", [*header, "phenotype_class"], rows)
    found = [w for w in validate_spec(spec).warnings if "phenotype_class outside the recommended set" in w]
    assert len(found) == 1 and f"'FAMILIAL_LONGEVITY' ({len(rows)} rows)" in found[0]
    assert _summary(tmp_path, spec, strict=False).get("phenotype_class_unrecognized") == 1


def test_only_recommended_classes_draw_no_warning(tmp_path: Path) -> None:
    columns, fill = _GROUPS["RM326"]
    spec = _spec(tmp_path, "clean", columns, fill)
    assert "phenotype_class_unrecognized" not in _summary(tmp_path, spec, strict=False)


# ── RM328: the ancestry a study was measured in ──────────────────────────────────────────────────


def test_ancestry_is_closed_over_the_1000g_superpopulations() -> None:
    assert VALID_SUPERPOPULATIONS == {"AFR", "AMR", "EAS", "EUR", "SAS"}
    marker = field_vocabularies(StudyRow)["ancestry"]
    assert marker["closed"] is True and set(marker["options"]) == VALID_SUPERPOPULATIONS
    assert _study(ancestry="EAS|EUR").ancestry == ["EAS", "EUR"]
    assert _study(ancestry="EUR").ancestry == ["EUR"]
    # Free text stays in `population`; a code list is not a description.
    for refused in ("European", "multi", "EUR|Ashkenazi"):
        with pytest.raises(ValidationError, match="ancestry"):
            _study(ancestry=refused)


def test_the_pgs_vocabulary_is_the_same_five_plus_multi() -> None:
    """One vocabulary, not two: `training_ancestry` is derived from the superpopulations."""
    assert VALID_TRAINING_ANCESTRY == VALID_SUPERPOPULATIONS | {"multi"}
    assert set(field_vocabularies(PgsRow)["training_ancestry"]["options"]) == VALID_TRAINING_ANCESTRY
    assert PgsRow(pgs_id="PGS000906", training_ancestry="multi").training_ancestry == ["multi"]


def test_ancestry_is_a_list_column_in_studies_parquet(tmp_path: Path) -> None:
    columns, fill = _GROUPS["RM328"]
    result = compile_module(_spec(tmp_path, "filled", columns, fill), tmp_path / "out")
    assert result.success, result.errors
    assert pl.read_parquet_schema(tmp_path / "out" / "studies.parquet")["ancestry"] == pl.List(pl.Utf8)


# ── RM329: the age band an estimate covers, and whose age it is ─────────────────────────────────


def test_age_of_is_closed_over_participant_and_parent() -> None:
    marker = field_vocabularies(StudyRow)["age_of"]
    assert marker["closed"] is True and set(marker["options"]) == {"participant", "parent"}
    with pytest.raises(ValidationError, match="age_of"):
        _study(age_of="child")


def test_no_refusal_ties_the_band_together() -> None:
    """Either bound may be empty (an open band), and `age_of` stands with or without bounds."""
    assert _study(age_min=80, age_of="parent").age_max is None
    assert _study(age_max=62.5).age_of is None
    assert _study(age_of="participant").age_min is None


def test_an_age_is_a_finite_non_negative_number_of_years() -> None:
    for cells in ({"age_min": -1}, {"age_max": float("inf")}, {"age_min": float("nan")}):
        with pytest.raises(ValidationError):
            _study(**cells)


# ── RM330: the stratum an estimate was measured in ──────────────────────────────────────────────


def test_a_stratum_and_its_level_are_written_both_or_neither() -> None:
    assert _study(stratum="parent_sex", stratum_level="father").stratum_level == "father"
    for cells in ({"stratum": "sex"}, {"stratum_level": "male"}):
        with pytest.raises(ValidationError, match="stratum"):
            _study(**cells)
    # Free text: no vocabulary on either half.
    assert not {"stratum", "stratum_level"} & set(field_vocabularies(StudyRow))


# ── RM331: a study measured on an LD proxy ──────────────────────────────────────────────────────


def _one_study(tmp_path: Path, name: str, cells: dict[str, str]) -> Path:
    """The HFE example with one extra study row on rs1800562, carrying `cells`.

    rs1800562 resolves to G/A in the example's own `resolution.csv` and rs111033563 to A/C, so an
    effect allele of `C` is the proxy's and not the lead's, and `G` is the lead's and not the proxy's.
    """
    columns = tuple(c for c in sorted(cells) if c != "effect_allele")

    def fill(i: int, row: dict[str, str]) -> None:
        return None

    spec = _spec(tmp_path, name, ("effect_allele", *columns), fill)
    header, rows = _read_rows(spec / "studies.csv")
    extra = dict.fromkeys(header, "")
    extra.update({"rsid": "rs1800562", "pmid": "29227965", **cells})
    _write_rows(spec / "studies.csv", header, [*rows, extra])
    return spec


def _proxy_findings(tmp_path: Path, spec: Path, *, strict: bool) -> tuple[bool, list[str]]:
    result = compile_module(spec, tmp_path / f"out_{spec.name}_{strict}", strict=strict)
    # A refused compile carries the finding in `errors` and in the inherited validation warnings, so the
    # same sentence can arrive twice; the claim here is about distinct findings.
    found = sorted(
        {m for m in (*result.errors, *result.warnings) if "effect_allele" in m and "29227965" in m}
    )
    return result.success, found


def test_the_allele_check_reads_the_proxys_alleles_when_one_is_stated(tmp_path: Path) -> None:
    """Filed under the lead, the proxy's allele used to be checked against the lead's and refused."""
    lead_only = _one_study(tmp_path, "lead", {"effect_allele": "C"})
    ok, found = _proxy_findings(tmp_path, lead_only, strict=True)
    assert not ok and len(found) == 1  # the 0.7 behaviour, kept for a row with no proxy

    proxied = _one_study(tmp_path, "proxied", {"effect_allele": "C", "proxy_rsid": "rs111033563"})
    ok, found = _proxy_findings(tmp_path, proxied, strict=True)
    assert ok and found == []


def test_a_wrong_allele_for_the_proxy_is_refused_and_names_the_proxy(tmp_path: Path) -> None:
    spec = _one_study(tmp_path, "wrong", {"effect_allele": "G", "proxy_rsid": "rs111033563"})
    ok, found = _proxy_findings(tmp_path, spec, strict=True)
    assert not ok and len(found) == 1
    assert "proxy rs111033563" in found[0] and "A/C" in found[0]
    ok, found = _proxy_findings(tmp_path, spec, strict=False)
    assert ok and len(found) == 1


def test_an_unresolved_proxy_withholds_rather_than_refuses(tmp_path: Path) -> None:
    """No `resolution.csv` row for the proxy is unknown: never the lead's alleles, never a refusal."""
    spec = _one_study(tmp_path, "unresolved", {"effect_allele": "T", "proxy_rsid": "rs4970836"})
    ok, found = _proxy_findings(tmp_path, spec, strict=True)
    assert ok and found == []


def test_a_proxy_is_an_rsid_and_never_the_row_itself() -> None:
    assert _study(proxy_rsid="rs4970836").proxy_rsid == "rs4970836"
    for proxy in ("4970836", "rs1800562"):
        with pytest.raises(ValidationError, match="proxy_rsid"):
            _study(proxy_rsid=proxy)
    # A proxy is a proxy OF something: a row naming no variant cannot carry one.
    with pytest.raises(ValidationError, match="proxy_rsid"):
        StudyRow(pmid="29227965", proxy_rsid="rs4970836")


# ── RM332: an effect's unit, on the study row and joined onto the variant ──────────────────────


def _unanimous(units: list[str | None]) -> str | None:
    stated = {u for u in units if u}
    return stated.pop() if len(stated) == 1 else None


def _weights_column(tmp_path: Path, spec: Path, column: str) -> dict[str, set[object]]:
    """The values `weights.parquet` carries in `column`, per rsID (a locus repeats on every genotype row)."""
    result = compile_module(spec, tmp_path / f"w_{spec.name}")
    assert result.success, result.errors
    df = pl.read_parquet(tmp_path / f"w_{spec.name}" / "weights.parquet")
    out: dict[str, set[object]] = {}
    for row in df.iter_rows(named=True):
        out.setdefault(row["rsid"], set()).add(row[column])
    return out


def test_effect_unit_is_free_text_as_on_gwas_effects() -> None:
    assert (
        StudyRow.model_fields["effect_unit"].annotation
        == GwasEffectRow.model_fields["effect_unit"].annotation
    )
    assert "effect_unit" not in field_vocabularies(StudyRow)
    assert _study(effect_unit="-ln HR per allele").effect_unit == "-ln HR per allele"


def test_weights_parquet_joins_the_unit_only_when_every_stating_study_agrees(tmp_path: Path) -> None:
    columns, fill = _GROUPS["RM332"]
    spec = _spec(tmp_path, "units", columns, fill)
    _, studies = _read_rows(spec / "studies.csv")
    expected: dict[str, str | None] = {}
    for row in studies:
        if row["rsid"]:
            expected.setdefault(row["rsid"], None)
    for rsid in expected:
        expected[rsid] = _unanimous([r["effect_unit"] or None for r in studies if r["rsid"] == rsid])
    # The fixture meets all four cases, or the join is asserted over fewer than it claims.
    assert expected["rs776994377"] and expected["rs1800562"]
    assert expected["rs759524388"] is None

    joined = _weights_column(tmp_path, spec, "effect_unit")
    assert {rsid: values for rsid, values in joined.items() if rsid in expected} == {
        rsid: {unit} for rsid, unit in expected.items() if rsid in joined
    }


def test_the_joined_unit_never_reaches_variants_csv(tmp_path: Path) -> None:
    columns, fill = _GROUPS["RM332"]
    spec = _spec(tmp_path, "units", columns, fill)
    assert compile_module(spec, tmp_path / "a1").success
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    header, _ = _read_rows(tmp_path / "rev" / "variants.csv")
    assert "effect_unit" not in header
    weights = pl.read_parquet_schema(tmp_path / "a1" / "weights.parquet")
    assert list(weights)[list(weights).index("min_quality") + 1] == "effect_unit"


# ── the duplicate-citation narrowing (RM140's pattern, PT2 §3 item 16) ──────────────────────────

_DUP = "Duplicate (variant, pmid)"

#: Per narrowing column, two values a pair of rows can state. The band is three columns read cell by
#: cell, each unstated cell unknown (`@absent-is-not-different`); the stratum is one pair.
_NARROWING: dict[str, tuple[dict[str, object], dict[str, object]]] = {
    "phenotype_class": ({"phenotype_class": "PARENTAL_LIFESPAN"}, {"phenotype_class": "HEALTHSPAN"}),
    "age_min": ({"age_min": 40, "age_of": "parent"}, {"age_min": 60, "age_of": "parent"}),
    "age_max": ({"age_max": 60}, {"age_max": 80}),
    "age_of": ({"age_min": 90, "age_of": "participant"}, {"age_min": 90, "age_of": "parent"}),
    "stratum": (
        {"stratum": "parent_sex", "stratum_level": "father"},
        {"stratum": "parent_sex", "stratum_level": "mother"},
    ),
}


def _dupes(*rows: dict[str, object]) -> list[str]:
    studies = [StudyRow(rsid="rs10455872", pmid="32678081", **cells) for cells in rows]
    variants = [
        VariantRow(rsid="rs10455872", genotype="A/G", state="protective", conclusion="c"),
    ]
    _, warnings = _cross_validate_studies(studies, module_subjects({"variants.csv": variants}))
    return [w for w in warnings if _DUP in w]


@pytest.mark.parametrize("column", sorted(_NARROWING))
def test_two_rows_stating_different_values_are_not_a_duplicate(column: str) -> None:
    first, second = _NARROWING[column]
    assert _dupes(first, second) == []
    # The same pair with the column equal is still one claim written twice.
    assert len(_dupes(first, first)) == 1


@pytest.mark.parametrize("column", sorted(_NARROWING))
def test_an_unstated_column_is_not_different_and_still_warns(column: str) -> None:
    first, _ = _NARROWING[column]
    expected = [f"{_DUP}: (rs10455872, 32678081)"]
    assert _dupes(first, {}) == expected
    assert _dupes({}, first) == expected


def test_one_open_band_against_a_closed_one_with_the_same_lower_bound_still_warns() -> None:
    """Cell by cell: `80–` and `80–90` share the one bound both state, and an empty one is unknown."""
    assert (
        len(_dupes({"age_min": 80, "age_of": "parent"}, {"age_min": 80, "age_max": 90, "age_of": "parent"}))
        == 1
    )


def test_a_proxy_does_not_narrow() -> None:
    """Two rows naming two proxies of one lead are not two analyses; `proxy_rsid` is not a narrowing."""
    assert len(_dupes({"proxy_rsid": "rs4970836"}, {"proxy_rsid": "rs602633"})) == 1


def test_a_row_warns_when_it_repeats_any_earlier_sibling() -> None:
    """Distinct from the first row is not enough: the third repeats the second."""
    rows = ({"phenotype_class": "HEALTHSPAN"}, {"phenotype_class": "MR"}, {"phenotype_class": "MR"})
    assert len(_dupes(*rows)) == 1


def test_the_v2_cases_compile_without_a_duplicate_warning(tmp_path: Path) -> None:
    """Appendix 2 examples 5 and 8 through the real compile: one paper, several classes; three bands."""
    spec = tmp_path / "v2"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: v2\n  title: v2\n  description: d\n  report_title: v2\n"
    )
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs10455872,A/G,protective,c\n")
    (spec / "studies.csv").write_text(
        "rsid,pmid,phenotype_class,age_min,age_max,age_of\n"
        "rs10455872,32678081,EXTREME_SURVIVAL_CC,,,\n"
        "rs10455872,32678081,PARENTAL_LIFESPAN,,,\n"
        "rs10455872,32678081,HEALTHSPAN,,,\n"
        "rs10455872,30642433,PARENTAL_LIFESPAN,40,60,parent\n"
        "rs10455872,30642433,PARENTAL_LIFESPAN,60,80,parent\n"
        "rs10455872,30642433,PARENTAL_LIFESPAN,80,,parent\n"
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert [w for w in result.warnings if _DUP in w] == []
    assert "duplicate_study_citation" not in result.manifest.compilation.warnings_summary


def test_a_module_with_none_of_the_new_columns_warns_exactly_as_before(tmp_path: Path) -> None:
    """Every published module: each repeated row warns, with the byte-identical 0.7 message."""
    spec = _spec(tmp_path, "doubled", (), None)
    header, rows = _read_rows(spec / "studies.csv")
    _write_rows(spec / "studies.csv", header, rows + rows)
    validation = validate_spec(spec)
    found = [w for w in validation.warnings if _DUP in w]
    loaded = [StudyRow(**{k: v for k, v in row.items() if v}) for row in rows]
    assert found == [f"{_DUP}: ({s.variant_key}, {s.pmid})" for s in loaded]


# ── the locus-level derived columns on weights.parquet (PT2 §3 item 10) ─────────────────────────

#: Per variant, the (ancestry, phenotype_class) of each of its study rows in file order. Each variant
#: meets one case of each derivation; a variant left out keeps its rows unstated.
_LOCUS_CASES: dict[str, tuple[tuple[str, str], ...]] = {
    # every row EUR → true; healthspan and lifespan studied
    "rs776994377": (("EUR", "HEALTHSPAN"), ("EUR", "OWN_SURVIVAL"), ("EUR", "PARENTAL_LIFESPAN")),
    # one row states another code → false; exceptional studied twice over
    "rs759524388": (("EUR", "EXTREME_SURVIVAL_CC"), ("EAS|EUR", "FAMILIAL"), ("EUR", "")),
    # EUR and unstated → null (unknown); only a class mapped to no cell
    "rs765804978": (("EUR", "MULTIVARIATE_AGEING"), ("", "MR"), ("EUR", "BIOMARKER")),
    # another code beside an unstated one → false, Kleene: unknown AND false is false
    "rs199916850": (("AFR", "NOVEL_CLASS"), ("", ""), ("", "")),
}


def _fill_locus_cases(i: int, row: dict[str, str]) -> None:
    cases = _LOCUS_CASES.get(row["rsid"])
    if cases is not None:
        row["ancestry"], row["phenotype_class"] = cases[_nth_for_variant(i, row["rsid"])]


def _eur_only(ancestries: list[list[str] | None]) -> bool | None:
    """The expectation, stated as the contract words it: false beats unknown, unknown beats true."""
    if any(codes and set(codes) != {"EUR"} for codes in ancestries):
        return False
    if not ancestries or any(not codes for codes in ancestries):
        return None
    return True


def _locus_spec(tmp_path: Path) -> Path:
    return _spec(tmp_path, "locus", ("ancestry", "phenotype_class"), _fill_locus_cases)


def _studies_by_rsid(spec: Path) -> dict[str, list[dict[str, str]]]:
    _, rows = _read_rows(spec / "studies.csv")
    out: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row["rsid"]:
            out.setdefault(row["rsid"], []).append(row)
    return out


def test_the_strip_map_covers_recommended_classes_only() -> None:
    assert set(OUTCOME_STRIP_CELLS) <= RECOMMENDED_PHENOTYPE_CLASSES
    assert set(OUTCOME_STRIP_CELLS.values()) == {"healthspan", "lifespan", "exceptional"}
    assert OUTCOME_STRIP_CELLS == {
        "HEALTHSPAN": "healthspan",
        "PARENTAL_LIFESPAN": "lifespan",
        "OWN_SURVIVAL": "lifespan",
        "EXTREME_SURVIVAL_CC": "exceptional",
        "FAMILIAL": "exceptional",
    }


def test_eur_only_evidence_is_kleene_over_the_supporting_rows(tmp_path: Path) -> None:
    spec = _locus_spec(tmp_path)
    by_rsid = _studies_by_rsid(spec)
    expected = {
        rsid: _eur_only([row["ancestry"].split("|") if row["ancestry"] else None for row in rows])
        for rsid, rows in by_rsid.items()
    }
    # The fixture meets every arm, or the derivation is asserted over fewer than it claims.
    assert {expected[r] for r in _LOCUS_CASES} == {True, False, None}
    assert expected["rs199916850"] is False

    joined = _weights_column(tmp_path, spec, "eur_only_evidence")
    for rsid, values in joined.items():
        assert values == {expected.get(rsid)}, rsid


@pytest.mark.parametrize("cell", ["healthspan", "lifespan", "exceptional"])
def test_an_outcome_cell_is_true_when_studied_and_null_otherwise(tmp_path: Path, cell: str) -> None:
    spec = _locus_spec(tmp_path)
    classes = {cls for cls, mapped in OUTCOME_STRIP_CELLS.items() if mapped == cell}
    expected = {
        rsid: (True if any(row["phenotype_class"] in classes for row in rows) else None)
        for rsid, rows in _studies_by_rsid(spec).items()
    }
    assert True in expected.values() and None in expected.values()
    joined = _weights_column(tmp_path, spec, f"outcome_{cell}")
    for rsid, values in joined.items():
        # Never false: a locus with no study of the class is untested, not "no effect".
        assert values == {expected.get(rsid)}, rsid


def test_the_derived_columns_come_last_and_never_reach_variants_csv(tmp_path: Path) -> None:
    spec = _locus_spec(tmp_path)
    assert compile_module(spec, tmp_path / "a1").success
    schema = pl.read_parquet_schema(tmp_path / "a1" / "weights.parquet")
    derived = [
        "effect_unit",
        "eur_only_evidence",
        "outcome_healthspan",
        "outcome_lifespan",
        "outcome_exceptional",
    ]
    # RM270's pair (`vrs_id`, `vrs_spec`) is the other 0.8 append, after these: copied from
    # `resolution.csv`, and written back there by reverse, never to `variants.csv`.
    copied = ["vrs_id", "vrs_spec"]
    assert list(schema)[-len(derived) - len(copied) :] == derived + copied
    assert all(schema[c] == pl.Boolean for c in derived[1:])
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    header, _ = _read_rows(tmp_path / "rev" / "variants.csv")
    assert not set(derived + copied) & set(header)
    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == compile_module(spec, tmp_path / "a3").manifest.artifact.digest
