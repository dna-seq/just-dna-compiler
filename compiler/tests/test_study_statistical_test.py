"""`StudyRow.statistical_test` — which analysis produced a study row's numbers (0.7, RM140, S75).

`study_design` describes the **study**; one study routinely reports several **analyses** of one
association. The motivating case is a single paper giving `OR 1.4, p 0.36` from an allelic Fisher's
exact test and `OR 1.42, p 0.75` from a univariate logistic regression of the same variant: two agents
building a module from it wrote rows that differed only in `p_value`, and one had taken its
`effect_size` from one analysis and its `p_value` from the other. Everything was green, because the
two numbers on a row are *asserted* to belong together and nothing recorded what either came from.

Two halves are pinned here. The **column** must survive `compile → reverse → compile` — the third and
fourth touch points (`fieldnames`, then the row dict, which fails silently) are the ones that get
missed. The **dedup check** must treat two rows naming different analyses as two claims, and must not
read an *absent* analysis as a different one: `None` is unknown, not "different".

The variant and PMID are the reporter's own case — `rs117385980`, PMID 41249831 — so the fixture is a
real association rather than a stub.
"""

from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_format.base import authored_field_names
from just_dna_format.spec import StudyRow

_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm140\n"
    "  title: RM140\n"
    "  description: which analysis produced a study row's statistics\n"
    "  report_title: RM140\n"
    "genome_build: GRCh38\n"
)

#: `rs117385980` is the SIRT6 variant the two runs disagreed on. Coordinates are not needed for this
#: column, so the row is rsID-keyed and carries no injected resolution — the dedup key is
#: `(variant_key, pmid)` either way.
_VARIANTS = (
    "rsid,genotype,state,conclusion,gene\n"
    "rs117385980,C/T,neutral,carrier of the minor allele,SIRT6\n"
)

_PMID = "41249831"

#: The two analyses of one association, verbatim from the report.
_FISHER = "Fisher's exact (allelic)"
_LOGISTIC = "univariate logistic regression"

_HEADER = "rsid,pmid,p_value,effect_size,effect_measure,statistical_test\n"


def _spec(directory: Path, *, study_rows: str, header: str = _HEADER) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_SPEC_YAML)
    (directory / "variants.csv").write_text(_VARIANTS)
    (directory / "studies.csv").write_text(header + study_rows)
    return directory


def _duplicates(result) -> list[str]:
    return [w for w in result.warnings if "Duplicate (variant, pmid)" in w]


# ── the column ──────────────────────────────────────────────────────────────────────────────────


def test_the_analysis_reaches_the_parquet_and_survives_the_round_trip(tmp_path: Path) -> None:
    """compile → reverse → compile, byte-identical, with the value still there.

    The `@three-touch-points` test. A column named in the reverse writer's `fieldnames` but missing
    from its row dict writes the *header* with an empty cell on every row — `DictWriter` fills a
    missing key silently — so the reversed spec re-validates and loses the value. Asserting the digest
    fixed point is what catches that; asserting the column is present does not.
    """
    spec = _spec(tmp_path / "spec", study_rows=f"rs117385980,{_PMID},0.36,1.42,OR,{_FISHER}\n")
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors

    studies = pl.read_parquet(tmp_path / "a1" / "studies.parquet")
    assert "statistical_test" in studies.columns
    assert studies["statistical_test"].to_list() == [_FISHER]

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    reversed_csv = (tmp_path / "rev" / "studies.csv").read_text()
    assert "statistical_test" in reversed_csv.splitlines()[0]
    assert _FISHER in reversed_csv

    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert pl.read_parquet(tmp_path / "a2" / "studies.parquet")["statistical_test"].to_list() == [
        _FISHER
    ]


def test_an_unset_analysis_leaves_the_authored_identity_alone(tmp_path: Path) -> None:
    """The P3/P8 property: an optional column nobody sets is omitted from `content_signature`.

    Two modules whose `studies.csv` differ only by the presence of the *column* — not a value — must
    hash equal. That is what makes the addition minor-legal rather than merely additive-looking, and
    it is the reason no published module's identity moves.
    """
    with_column = _spec(tmp_path / "with", study_rows=f"rs117385980,{_PMID},0.36,1.42,OR,\n")
    without = _spec(
        tmp_path / "without",
        header="rsid,pmid,p_value,effect_size,effect_measure\n",
        study_rows=f"rs117385980,{_PMID},0.36,1.42,OR\n",
    )
    a = compile_module(with_column, tmp_path / "oa")
    b = compile_module(without, tmp_path / "ob")
    assert a.success and b.success, (a.errors, b.errors)
    assert a.manifest.content_signature == b.manifest.content_signature


def test_the_authoring_surface_offers_the_column_without_being_told(tmp_path: Path) -> None:
    """Derived from the model, never a hand-kept list (`@fieldnames-from-model`).

    `authored_field_names` is what `draft` scaffolds from, so a column the model has and this list
    does not is one an author can never be offered.
    """
    assert "statistical_test" in authored_field_names(StudyRow)
    assert StudyRow.model_fields["statistical_test"].default is None


# ── the dedup check ─────────────────────────────────────────────────────────────────────────────


def test_two_analyses_of_one_association_are_two_rows_not_a_duplicate(tmp_path: Path) -> None:
    """The capability the column buys, and the reason the check had to learn about it.

    `(variant_key, pmid)` is the dedup key, and before RM140 these two rows were "the same claim
    written twice" — which is what the check's own docstring calls a duplicate. They are not: they are
    one paper's two tests of one association, with different p-values.
    """
    spec = _spec(
        tmp_path / "spec",
        study_rows=(
            f"rs117385980,{_PMID},0.36,1.42,OR,{_FISHER}\n"
            f"rs117385980,{_PMID},0.75,1.42,OR,{_LOGISTIC}\n"
        ),
    )
    assert _duplicates(validate_spec(spec, strict=True)) == []
    # Both sides of the mode ladder, which is the audit's repeat defect (`@parity-by-check`). The
    # compile is best-effort because the module names no coordinates and this fixture invents none:
    # the dedup check reads the authored rows and is identical in both modes.
    compiled = compile_module(spec, tmp_path / "out")
    assert compiled.success, compiled.errors
    assert _duplicates(compiled) == []
    assert pl.read_parquet(tmp_path / "out" / "studies.parquet")[
        "statistical_test"
    ].to_list() == [_FISHER, _LOGISTIC]


def test_an_absent_analysis_is_unknown_and_never_suppresses(tmp_path: Path) -> None:
    """`None` is not "different" — the house algebra, applied to a dedup key.

    A naive `a != b` would read a null against a stated value as a distinction and retire this check
    for every module written before the column existed. Four arrangements, and only the last one
    establishes that two rows describe separate work:

    - neither row states an analysis — unknown against unknown;
    - both state the same one — the same claim written twice, which is what the warning is for;
    - one states an analysis and the other does not, in either order — unknown against stated.
    """
    both_null = f"rs117385980,{_PMID},0.36,1.42,OR,\nrs117385980,{_PMID},0.75,1.42,OR,\n"
    same = (
        f"rs117385980,{_PMID},0.36,1.42,OR,{_FISHER}\n"
        f"rs117385980,{_PMID},0.75,1.42,OR,{_FISHER}\n"
    )
    stated_first = (
        f"rs117385980,{_PMID},0.36,1.42,OR,{_FISHER}\nrs117385980,{_PMID},0.75,1.42,OR,\n"
    )
    stated_second = (
        f"rs117385980,{_PMID},0.36,1.42,OR,\nrs117385980,{_PMID},0.75,1.42,OR,{_LOGISTIC}\n"
    )
    for name, rows in (
        ("both null", both_null),
        ("same analysis", same),
        ("stated first", stated_first),
        ("stated second", stated_second),
    ):
        spec = _spec(tmp_path / name.replace(" ", "_"), study_rows=rows)
        found = _duplicates(validate_spec(spec, strict=True))
        assert len(found) == 1, f"{name}: expected one duplicate warning, got {found}"
        assert found[0] == f"Duplicate (variant, pmid): (rs117385980, {_PMID})", name


def test_a_repeated_analysis_among_distinct_ones_still_warns(tmp_path: Path) -> None:
    """The check counts analyses, not rows: three rows, two of them the same test.

    The pair that repeats is a duplicate however many distinct siblings sit beside it, and exactly one
    warning is emitted — the third row's, not the second's.
    """
    spec = _spec(
        tmp_path / "spec",
        study_rows=(
            f"rs117385980,{_PMID},0.36,1.42,OR,{_FISHER}\n"
            f"rs117385980,{_PMID},0.75,1.42,OR,{_LOGISTIC}\n"
            f"rs117385980,{_PMID},0.40,1.40,OR,{_FISHER}\n"
        ),
    )
    assert len(_duplicates(validate_spec(spec, strict=True))) == 1


def test_the_message_is_unchanged_for_every_case_that_still_reports(tmp_path: Path) -> None:
    """`@warning-text-is-api`: a consumer greps this phrase, so RM140 moved behaviour and not bytes.

    A module with no `statistical_test` column at all — every module published before 0.7 — reports
    exactly what it reported before, with the same code and the same string.
    """
    spec = _spec(
        tmp_path / "spec",
        header="rsid,pmid,p_value\n",
        study_rows=f"rs117385980,{_PMID},0.36\nrs117385980,{_PMID},0.75\n",
    )
    result = validate_spec(spec, strict=True)
    assert _duplicates(result) == [f"Duplicate (variant, pmid): (rs117385980, {_PMID})"]
    assert result.warnings_summary.get("duplicate_study_citation") == 1
