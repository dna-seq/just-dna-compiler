"""A binning table states clinical thresholds and nothing asked where they came from (S19).

`studies.csv` is required iff `variants.csv` is present, which grounds the annotations that most
often arrive with citations already attached and leaves the most interpretive claim in the format —
a bin boundary — with no evidence and no finding. This tree's own `htt_repeat_expansion` compiled
green under `--strict` asserting four Huntington thresholds with no citation anywhere.

Every expectation is computed from the real reference examples at runtime; nothing here is a count
read off a data dump.
"""

import csv
import io
from pathlib import Path

from just_dna_compiler.compiler import (
    _BINNING_TABLE_KINDS,
    _check_binning_grounding,
    compile_module,
    validate_spec,
)
from just_dna_format.binning import HeteroplasmyRow, MeasureBinRow, RepeatAlleleRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HTT = _EXAMPLES / "htt_repeat_expansion"
_MT = _EXAMPLES / "mt_heteroplasmy"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
    "genome_build: GRCh38\n"
)


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def _finding(warnings: list[str], csv_name: str) -> str | None:
    hits = [w for w in warnings if w.startswith(f"{csv_name}:") and "grounding evidence" in w]
    assert len(hits) <= 1, f"one aggregated line per table, got {len(hits)}"
    return hits[0] if hits else None


def test_the_binning_set_is_derived_from_the_models() -> None:
    """A kind is a binning kind exactly when its model is a `MeasureBinRow` — never a kept list."""
    names = {csv_name for csv_name, _model in _BINNING_TABLE_KINDS}
    assert names == {
        "activity_phenotype.csv", "copynumbers.csv", "repeat_alleles.csv", "heteroplasmy.csv",
    }
    for _csv_name, model in _BINNING_TABLE_KINDS:
        assert issubclass(model, MeasureBinRow)


def test_the_reported_case_the_htt_thresholds_are_ungrounded_and_nothing_said_so() -> None:
    """Four clinical thresholds, `--strict`, no evidence — the module the consumer authored."""
    authored = _rows(_HTT / "repeat_alleles.csv")
    resolved = [r for r in authored if r["unresolved"] != "true"]
    assert resolved, "the fixture must state thresholds"
    assert not (_HTT / "studies.csv").exists(), "the fixture must record no evidence"

    finding = _finding(validate_spec(_HTT, strict=True).warnings, "repeat_alleles.csv")
    assert finding is not None
    assert f"{len(resolved)} of {len(resolved)} bin(s)" in finding
    # The remedy became sayable in 0.6 (RM47): a `(gene, repeat_unit)` row can now cite the boundary
    # itself through `MeasureBinRow.pmid`, so the message names one route for every kind. What it must
    # NOT do any more is repeat the old claim that nothing can point at these bins.
    assert "put the PubMed id on the bin row (`pmid`)" in finding
    assert "no study row can name one of these bins" not in finding


def test_the_unresolved_sentinel_is_not_a_threshold() -> None:
    """It asserts nothing — it is the row a consumer selects when there is no measurement."""
    authored = _rows(_HTT / "repeat_alleles.csv")
    sentinels = [r for r in authored if r["unresolved"] == "true"]
    assert sentinels, "the fixture must carry the sentinel this test is about"

    finding = _finding(validate_spec(_HTT).warnings, "repeat_alleles.csv")
    assert finding is not None
    assert f"of {len(authored)} bin(s)" not in finding, "the sentinel must be out of the denominator"


def test_validate_and_compile_agree_and_the_compile_says_it_once(tmp_path: Path) -> None:
    """`compile_module` runs `validate_spec` itself, so the sentence must be de-duplicated."""
    validated = _finding(validate_spec(_HTT).warnings, "repeat_alleles.csv")
    result = compile_module(_HTT, tmp_path / "out")
    assert result.success
    compiled = [w for w in result.warnings if "grounding evidence" in w]
    assert len(compiled) == 1
    assert compiled[0] == validated


def test_a_studies_csv_clears_it(tmp_path: Path) -> None:
    """The finding is clearable by an authored edit, which is what keeps it a warning worth printing.

    A study row must still name a variant, so this grounds the *module* and not the bound — which is
    exactly what the message says, and is the residual filed as RM47.
    """
    spec = tmp_path / "grounded"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "repeat_alleles.csv").write_text(
        (_HTT / "repeat_alleles.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert _finding(validate_spec(spec).warnings, "repeat_alleles.csv") is not None

    (spec / "studies.csv").write_text(
        'rsid,chrom,pmid,conclusion\n,4,8458085,"CAG threshold definition"\n', encoding="utf-8"
    )
    assert _finding(validate_spec(spec).warnings, "repeat_alleles.csv") is None


def test_a_heteroplasmy_module_that_cites_its_variants_stays_silent() -> None:
    """`mt_heteroplasmy` is the counterexample, and what silences it is the `studies.csv` gate.

    Its bins do carry `chrom`/`start`/`ref`/`alts` (the 0.5.1 identity columns) and its `studies.csv`
    cites the same variant, which is the pairing the extra remedy route describes — but the check
    never reaches the rows here: a module with any study rows is not nagged, so the identity is why
    the module is *actually* grounded rather than why the function is quiet. This test used to claim
    the identity did the silencing, which was never true of this fixture and hid D1-3.
    """
    bins = _rows(_MT / "heteroplasmy.csv")
    studies = _rows(_MT / "studies.csv")
    placed = {(r["chrom"], r["start"], r["ref"]) for r in bins}
    cited = {(r["chrom"], r["start"], r["ref"]) for r in studies}
    assert placed & cited, "the fixture must ground its bins through a shared variant identity"

    assert _finding(validate_spec(_MT, strict=True).warnings, "heteroplasmy.csv") is None


def _heteroplasmy_rows(*, identity: bool) -> list[HeteroplasmyRow]:
    """The `mt_heteroplasmy` bins as model rows, with or without their 0.5.1 identity columns."""
    return [
        HeteroplasmyRow(
            gene=r["gene"], reference_sequence=r["reference_sequence"], tissue=r["tissue"],
            measure_kind=r["measure_kind"], measure_min=float(r["measure_min"]),
            measure_max=float(r["measure_max"]), conclusion=r["conclusion"],
            **(
                {"chrom": r["chrom"], "start": int(r["start"]), "ref": r["ref"], "alts": r["alts"]}
                if identity
                else {}
            ),
        )
        for r in _rows(_MT / "heteroplasmy.csv")
        if r["unresolved"] != "true"
    ]


def test_naming_the_variant_does_not_ground_a_bin_when_no_study_row_exists(tmp_path: Path) -> None:
    """D1-3: the exemption the check granted a variant-keyed bin was vacuous inside its own gate.

    The function returns early unless the module records **zero** study rows, and then counted a bin
    as grounded for naming a variant "a study row can then name back" — the study row it had just
    established does not exist. So a real MELAS/NARP module stating thresholds and citing nothing was
    green and silent while the identical module on `repeat_alleles.csv` was warned.

    Both halves are exercised: the model rows (identity stamped at construction) and a whole spec
    directory through the real loader, since it is the loader that stamps `variant_key` for an author.
    """
    authored = _heteroplasmy_rows(identity=True)
    assert all(r.variant_key is not None for r in authored), "the fixture must name its variants"
    assert all(r.pmid is None for r in authored), "and cite no boundary"

    finding = _finding(_check_binning_grounding({"heteroplasmy.csv": authored}, []), "heteroplasmy.csv")
    assert finding is not None
    assert f"{len(authored)} of {len(authored)} bin(s)" in finding

    spec = tmp_path / "uncited_mt"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "heteroplasmy.csv").write_text(
        (_MT / "heteroplasmy.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert not (spec / "studies.csv").exists(), "the module must record no evidence at all"
    assert _finding(validate_spec(spec, strict=True).warnings, "heteroplasmy.csv") is not None


def test_the_same_heteroplasmy_rows_stripped_of_their_identity_get_the_extra_route() -> None:
    """The distinction is derived from the *row*, never from the table name: a heteroplasmy row
    carries a second remedy a repeat bin does not, because a study row can name the variant it is
    about.

    Since RM47 that is an **additional** route rather than the only actionable one — both kinds are
    first told to cite the boundary itself."""
    authored = _heteroplasmy_rows(identity=False)
    assert all(r.variant_key is None for r in authored), "stripped of identity, by construction"

    finding = _finding(_check_binning_grounding({"heteroplasmy.csv": authored}, []), "heteroplasmy.csv")
    assert finding is not None
    assert "put the PubMed id on the bin row (`pmid`)" in finding
    assert "alternatively, a studies.csv row naming the variant" in finding
    # The repeat table, whose rows could never name a variant, gets the first half and not the second.
    repeat_finding = _finding(
        _check_binning_grounding(
            {"repeat_alleles.csv": _repeat_rows(pmid=None)}, []
        ),
        "repeat_alleles.csv",
    )
    assert repeat_finding is not None
    assert "alternatively, a studies.csv row naming the variant" not in repeat_finding


def _repeat_rows(*, pmid: str | None) -> list[RepeatAlleleRow]:
    """The HTT bins as model rows, optionally carrying the RM47 boundary citation."""
    return [
        RepeatAlleleRow(
            gene=r["gene"], repeat_unit=r["repeat_unit"], measure_kind=r["measure_kind"],
            measure_min=float(r["measure_min"]) if r["measure_min"] else None,
            measure_max=float(r["measure_max"]) if r["measure_max"] else None,
            conclusion=r["conclusion"], pmid=pmid,
        )
        for r in _rows(_HTT / "repeat_alleles.csv")
        if r["unresolved"] != "true"
    ]


def test_a_bin_that_cites_its_boundary_is_grounded_and_stays_silent() -> None:
    """RM47's whole point: the pointer sits on the row that states the threshold.

    Demonstrated on the *old* behaviour too — the identical rows without the column still warn — so
    this proves the column clears it rather than merely asserting that it does."""
    assert _finding(
        _check_binning_grounding({"repeat_alleles.csv": _repeat_rows(pmid=None)}, []),
        "repeat_alleles.csv",
    ) is not None
    assert _finding(
        _check_binning_grounding({"repeat_alleles.csv": _repeat_rows(pmid="8458085")}, []),
        "repeat_alleles.csv",
    ) is None


def test_grounding_is_counted_per_row_not_per_table() -> None:
    """One cited bin among uncited ones narrows the numerator; it does not silence the table."""
    rows = _repeat_rows(pmid=None)
    rows[0].pmid = "8458085"
    finding = _finding(
        _check_binning_grounding({"repeat_alleles.csv": rows}, []), "repeat_alleles.csv"
    )
    assert finding is not None
    assert f"{len(rows) - 1} of {len(rows)} bin(s)" in finding


def test_a_module_that_carries_variants_is_not_told_twice(tmp_path: Path) -> None:
    """A missing `studies.csv` beside `variants.csv` is already a hard error; this must not pile on."""
    spec = tmp_path / "withvariants"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "repeat_alleles.csv").write_text(
        (_HTT / "repeat_alleles.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\nrs2857654,A/A,significant,c\n", encoding="utf-8"
    )
    result = validate_spec(spec)
    assert any("studies.csv is missing" in e for e in result.errors)
    # The warning is still true and still printed — but the error is the one that stops the compile,
    # and the two say different things: one is unsatisfiable for these rows, the other is not.
    assert _finding(result.warnings, "repeat_alleles.csv") is not None
