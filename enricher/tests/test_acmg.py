"""ACMG SF list parse + `acmg_sf` cross-check, against the real NCBI page.

The fixture is the live page as served on 2026-08-03, unedited — every malformation the parser guards
against is one this file actually contains, so the guards are exercised by real bytes rather than by
markup invented to trip them.
"""

import re
from pathlib import Path

import pytest
from just_dna_enricher.acmg import (
    EXPECTED_HEADERS,
    AcmgListUnavailable,
    AcmgSfError,
    check_acmg_sf,
    fetch_acmg_page,
    parse_acmg_page,
    verification_record,
    verify_acmg_sf,
)
from just_dna_format.spec import VariantRow

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_PAGE = (_ASSETS / "ncbi_acmg_sf_v3.2.html").read_text(encoding="utf-8")
_WORKBOOK = _ASSETS / "acmg_sf_v3.3.xlsx"


@pytest.fixture(scope="module")
def sf_list():
    """NCBI's page — v3.2, which this package now knows is superseded.

    Right for every parse test and for the outcomes that do not depend on membership (`unstated`,
    `blank`, `unchecked`). **Wrong** for the disagreement outcomes, which against a superseded list are
    deliberately demoted to `unverifiable` — those use `current_list`. Keeping both fixtures is what
    stops the demotion from quietly hollowing out the check: three tests here asserted `not_listed`
    against this page and had to move, which is the demotion doing its job.
    """
    return parse_acmg_page(_PAGE)


@pytest.fixture(scope="module")
def current_list():
    """ACMG's own v3.3 supplement — the newest release, so a disagreement against it is a real one."""
    from just_dna_enricher.acmg_build import parse_acmg_workbook

    return parse_acmg_workbook(_WORKBOOK)


def _variant(gene, acmg_sf=None, rsid="rs1800562"):
    return VariantRow(
        rsid=rsid, genotype="A/A", state="risk", conclusion="x", gene=gene, acmg_sf=acmg_sf
    )


# ── the parse ──────────────────────────────────────────────────────────────────────────────────


def test_the_naive_row_split_loses_genes_which_is_why_the_parser_counts_cells(sf_list):
    """Demonstrate the bug the cell-based parse exists to avoid, on the real page.

    Splitting the table on `<tr>` is the obvious implementation and it silently returns a *short*
    list — the failure mode that would make correctly authored `acmg_sf=true` rows look wrong. This
    asserts the naive result really is short, and names what it drops, so the guard is not
    cargo-culted.
    """
    table = re.search(r"<table[^>]*>(.*?)</table>", _PAGE, re.DOTALL).group(1)
    naive = set()
    for row in re.findall(r"<tr>(.*?)(?=<tr>|\Z)", table, re.DOTALL):
        link = re.search(r'href="/(?:gtr/)?genes?/\d+/?"\s*>\s*([A-Za-z0-9_.\-]+)\s*</a>', row)
        if link:
            naive.add(link.group(1))

    assert naive < sf_list.genes, "the naive split should be a strict subset, not equal"
    assert sf_list.genes - naive == {"TP53", "COL3A1", "TPM1"}


def test_the_real_page_parses_to_its_declared_version_and_a_gene_per_row(sf_list):
    assert sf_list.version == "3.2"
    assert sf_list.dataset == "acmg_sf_v3.2"
    # One gene link per gene-condition row, and strictly fewer genes than rows: the list is keyed on
    # the pair, so several genes are listed for more than one condition.
    assert len(sf_list.findings) == 94
    assert len(sf_list.genes) == 81
    assert all(f.gene and f.gene_id > 0 for f in sf_list.findings)


def test_a_gene_listed_for_two_conditions_keeps_both_entries(sf_list):
    entries = sf_list.entries_for("TRDN")
    assert {e.disease for e in entries} == {
        "Catecholaminergic polymorphic ventricular tachycardia 5",
        "Long QT syndrome",
    }
    # The second has no MIM on the page at all — an absent id, not a zero.
    assert {e.disease_mims for e in entries} == {("615441",), ()}


def test_a_multi_concept_cell_keeps_every_id_rather_than_the_first(sf_list):
    """SDHB's row names two MIMs and two MedGen concepts, and links to a MedGen *search*."""
    (entry,) = sf_list.entries_for("SDHB")
    assert entry.disease == "Hereditary paraganglioma-pheochromocytoma syndrome"
    assert entry.disease_mims == ("115310", "171300")
    assert entry.medgen_ids == ("C1861848", "C0031511")


def test_the_gene_link_is_read_through_all_three_url_shapes(sf_list):
    """`/gtr/genes/324`, `/gtr/genes/4089/` and `/gene/3949` all appear; all must resolve."""
    by_gene = {f.gene: f.gene_id for f in sf_list.findings}
    assert by_gene["APC"] == 324  # /gtr/genes/324
    assert by_gene["SMAD4"] == 4089  # /gtr/genes/4089/  (trailing slash)
    assert by_gene["LDLR"] == 3949  # /gene/3949        (a different NCBI resource)


def test_acmg_scopes_hfe_to_one_genotype_and_the_parse_keeps_that_text(sf_list):
    """The list itself is not purely gene-level, and the entry text is where that survives."""
    (entry,) = sf_list.entries_for("HFE")
    assert "C282Y homozygotes only" in entry.disease


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda t: t.replace("ACMG SF v3.2", "ACMG SF vNEXT"), "declares no"),
        (lambda t: t.replace(EXPECTED_HEADERS[2], "Gene"), "re-laid out"),
        # Drop one cell from the first data row: the count stops dividing by four.
        (lambda t: t.replace("<td>Adenomatous polyposis coli", "Adenomatous polyposis coli", 1), "not a multiple"),
    ],
)
def test_a_changed_page_refuses_rather_than_returning_a_short_list(mutate, expected):
    with pytest.raises(AcmgSfError, match=expected):
        parse_acmg_page(mutate(_PAGE))


def test_a_gene_cell_that_lost_its_link_refuses(sf_list):
    """Zero links in a gene cell is exactly a silently-dropped gene, so it is fatal."""
    broken = _PAGE.replace('<a href="/gtr/genes/7157">TP53</a>', "TP53", 1)
    with pytest.raises(AcmgSfError, match="0 gene links"):
        parse_acmg_page(broken)


def test_a_truncated_response_trips_the_floor():
    head = _PAGE[: _PAGE.find("<table")] + "<table>" + "".join(
        f"<tr><th>{h}</th></tr>" for h in EXPECTED_HEADERS
    )
    # A header-only table: every guard past the header must still refuse rather than return nothing.
    with pytest.raises(AcmgSfError):
        parse_acmg_page(head + "</table>")


# ── the check ──────────────────────────────────────────────────────────────────────────────────


def test_the_four_stated_outcomes(current_list):
    variants = [
        _variant("HFE", True),  # listed, claimed  -> agree
        _variant("HBB", False),  # unlisted, denied -> agree
        _variant("HBB", True),  # unlisted, claimed -> not_listed
        _variant("BRCA1", False),  # listed, denied   -> denied
    ]
    report = check_acmg_sf(variants, current_list)
    assert [v.verdict for v in report.verdicts] == ["agree", "agree", "not_listed", "denied"]
    assert [v.row for v in report.mismatches] == [3, 4]
    assert not report.clean
    assert "BRCA1" in report.mismatches[1].message
    # The `denied` message must say what to do instead, because the honest fix is usually "blank".
    assert "blank rather than false" in report.mismatches[1].message


def test_a_blank_cell_is_never_a_defect_even_on_a_listed_gene(sf_list):
    report = check_acmg_sf([_variant("HFE"), _variant("HBB")], sf_list)
    assert [v.verdict for v in report.verdicts] == ["unstated", "blank"]
    assert report.clean and not report.mismatches
    assert len(report.notes) == 1
    assert "blank means 'not stated'" in report.notes[0].message


def test_a_row_with_no_gene_is_unchecked_not_absent(sf_list):
    report = check_acmg_sf([_variant(None, True), _variant("HFE", True)], sf_list)
    assert [v.verdict for v in report.verdicts] == ["unchecked", "agree"]
    assert report.checked == 1 and len(report.verdicts) == 2
    assert report.clean


def test_offline_reports_unchecked_rather_than_not_on_the_list():
    variants = [_variant("HFE", True), _variant("HBB", True)]
    report = verify_acmg_sf(variants, offline=True)
    assert report.version is None
    assert {v.verdict for v in report.verdicts} == {"unchecked"}
    # The claim that would be *wrong* to make offline is that the second row is a mismatch.
    assert report.mismatches == []
    assert report.warnings and "offline" in report.warnings[0]


def test_strict_refuses_on_a_mismatch_and_best_effort_does_not(tmp_path):
    """Against a **current** list. The stale-page variant of this is in `test_acmg_build.py`."""
    from just_dna_enricher.acmg_build import build_acmg_snapshot

    build_acmg_snapshot(_WORKBOOK, tmp_path / "snap")
    variants = [_variant("HBB", True)]
    report = verify_acmg_sf(variants, mode="best_effort", snapshot_dir=tmp_path / "snap")
    assert len(report.mismatches) == 1
    with pytest.raises(AcmgSfError, match="strict acmg_sf check"):
        verify_acmg_sf(variants, mode="strict", snapshot_dir=tmp_path / "snap")


def test_strict_does_not_refuse_on_a_note(sf_list):
    """A blank cell must not become a strict failure — that is `None` collapsing into `False`."""
    report = verify_acmg_sf([_variant("HFE")], mode="strict", page_text=_PAGE)
    assert report.notes and report.clean


def test_findings_group_by_gene_because_that_is_what_they_are_about(current_list):
    """One sentence per gene, not per row — found by running the real HFE example through the CLI."""
    from just_dna_enricher.acmg import AcmgReport

    variants = [_variant("HBB", True) for _ in range(12)] + [_variant("APOE", True)]
    report = check_acmg_sf(variants, current_list)
    assert len(report.mismatches) == 13
    grouped = AcmgReport.by_gene(report.mismatches)
    assert [(gene, len(rows)) for gene, rows, _ in grouped] == [("HBB", 12), ("APOE", 1)]
    # First-occurrence order, and the row numbers survive so a human can find them.
    assert grouped[0][1] == list(range(1, 13))


# ── what the pass attests (RM72) ────────────────────────────────────────────────────────────────


def test_the_record_counts_the_rows_the_question_could_be_asked_about(current_list):
    """`subjects` is `report.checked`, which already excludes a row naming no gene.

    Counting every verdict would publish a comparison for rows nobody compared — the shape the
    reference-allele pass fell into on an unbuilt assembly.
    """
    variants = [_variant("HBB", True), _variant("HFE", True), _variant(None, True)]
    report = check_acmg_sf(variants, current_list)
    record = verification_record(report)

    assert record.subjects == report.checked == 2 < len(report.verdicts)
    assert record.findings == len(report.mismatches) == 1
    assert record.skipped is None
    assert (record.source, record.release) == ("acmg", current_list.version)
    assert "HBB" in (record.detail or "")


def test_a_disagreement_no_list_can_settle_is_named_rather_than_counted(sf_list):
    """The sharp edge of `findings = mismatches`, and why the sentence beside it is load-bearing.

    Against a superseded list every disagreement is demoted to `unverifiable`, so `mismatches` is
    empty *by construction* and a bare `findings=0` would read as a clean bill on a module with real
    disagreements. The count travels in `detail`, and `release` names the list that could not settle
    them.
    """
    report = check_acmg_sf([_variant("HBB", True)], sf_list)
    record = verification_record(report)

    assert report.unverifiable and not report.mismatches
    assert record.findings == 0
    assert f"{len(report.unverifiable)} disagreement(s) could not be settled" in (record.detail or "")
    assert record.release == sf_list.version


def test_offline_with_no_list_is_a_skip_and_not_a_run_over_nothing():
    """`ran(0, 0)` reads as "the check ran and had nothing in scope", which is the opposite of true."""
    record = verification_record(verify_acmg_sf([_variant("HFE", True)], offline=True))
    assert record.skipped == "offline" and record.subjects == 0
    assert "acmg_sf went unchecked" in (record.detail or "")


def test_a_module_naming_no_gene_has_nothing_to_check(current_list):
    report = check_acmg_sf([_variant(None, True)], current_list)
    record = verification_record(report)
    assert record.skipped == "nothing_to_check"
    # `release` is a property of a comparison, and none was made — so it names the list in the
    # sentence instead of in the field.
    assert record.release is None and current_list.version in (record.detail or "")


def test_only_an_unreadable_list_is_a_skip_and_a_strict_refusal_is_not(tmp_path):
    """Two ways of raising, and only one of them means the question was never put.

    A caller that attested off the base exception would record "never asked" for the `strict`
    refusal — the one run where the list *was* read and the question answered badly. The subclass is
    what keeps those apart, and this pins that the refusal stays outside it.
    """
    from just_dna_enricher.acmg_build import build_acmg_snapshot

    broken = _PAGE.replace("ACMG SF v3.2", "", 1)
    with pytest.raises(AcmgListUnavailable) as unreadable:
        parse_acmg_page(broken)
    assert unreadable.value.skip == "no_reference"

    build_acmg_snapshot(_WORKBOOK, tmp_path / "snap")
    with pytest.raises(AcmgSfError) as refusal:
        verify_acmg_sf([_variant("HBB", True)], mode="strict", snapshot_dir=tmp_path / "snap")
    assert not isinstance(refusal.value, AcmgListUnavailable)


def test_an_unreachable_page_is_unreachable_rather_than_no_reference(monkeypatch):
    """A request that never completed is not a source that answered with nothing (S20's distinction)."""
    import httpx

    def boom(*_a, **_kw):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(httpx, "get", boom)
    with pytest.raises(AcmgListUnavailable) as exc:
        fetch_acmg_page("https://example.invalid/acmg")
    assert exc.value.skip == "unreachable"


def test_the_real_reference_examples_hold_up(sf_list):
    """Dogfood: the two SNP-core examples in the repo, checked as a consumer would."""
    from just_dna_compiler.compiler import _load_csv_rows

    root = Path(__file__).resolve().parents[2] / "reference_examples"
    hfe, errors, _ = _load_csv_rows(root / "hfe_hemochromatosis" / "variants.csv", VariantRow, "v")
    assert not errors
    report = check_acmg_sf(hfe, sf_list)
    # HFE is on the list and the example leaves the column blank throughout: all notes, no defects.
    assert report.clean
    assert len(report.notes) == len(hfe) > 0
