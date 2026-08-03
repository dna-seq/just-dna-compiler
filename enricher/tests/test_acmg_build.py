"""The ACMG SF workbook builder, the snapshot reader, and the stale-list demotion.

**The defect these exist for is demonstrated, not asserted.** `test_a_v33_gene_is_reported_as_wrong_
against_the_v32_page` runs the *old* behaviour — a disagreement against NCBI's page, taken at face
value — and shows it calls a correctly authored `acmg_sf=true` row a mismatch, because ACMG SF v3.3
lists `ABCD1` and the page NCBI serves is v3.2. Everything else here is the fix.

**Two real fixtures, side by side, which is the point.** `assets/ncbi_acmg_sf_v3.2.html` is the page
the scrape reads and `assets/acmg_sf_v3.3.xlsx` is ACMG's own v3.3 supplement, so the version gap is
exercised against both publishers' actual bytes rather than against a described one. The guard cases
still build their own minimal workbooks, because a fixture cannot be malformed in six ways at once —
each synthetic sheet carries exactly one of the real file's traps (prose in the Gene column, a
misspelled header, embedded newlines, trailing spaces, a reordered column).
"""

import json
from pathlib import Path

import pytest
from just_dna_format.spec import VariantRow

from just_dna_enricher.acmg import (
    KNOWN_LATEST_SF_VERSION,
    MIN_GENES,
    SNAPSHOT_CSV,
    SNAPSHOT_RELEASE,
    AcmgSfError,
    check_acmg_sf,
    load_acmg_snapshot,
    parse_acmg_page,
    parse_sf_version,
    verify_acmg_sf,
)
from just_dna_enricher.acmg_build import build_acmg_snapshot, parse_acmg_workbook

openpyxl = pytest.importorskip("openpyxl", reason="the workbook builder is a [dev] extra")

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_V32_PAGE = (_ASSETS / "ncbi_acmg_sf_v3.2.html").read_text(encoding="utf-8")
#: ACMG's v3.3 supplementary workbook (`10.1016/j.gim.2025.101454`, mmc1), committed unmodified beside
#: the v3.2 page it supersedes. 17 KB, so no LFS.
_REAL_WORKBOOK = _ASSETS / "acmg_sf_v3.3.xlsx"

#: The three genes v3.3 added over v3.2. Domain constants from the published statement, which
#: CLAUDE.md permits hardcoding — unlike a row count read off a data dump.
V33_ADDITIONS = {"ABCD1", "CYP27A1", "PLN"}

#: The real sheet's headers, typo and trailing space included. Reused so the synthetic workbooks
#: exercise the same prefix-matching the real file needs.
_HEADERS = (
    "Gene", "Gene MIM", "Disease/Phentyope", "Disorder MIM",
    "Phenotype Category", "Inheritance ", "SF List Version", "Variants to report",
)


def _workbook(tmp_path: Path, rows, *, title="ACMG SF v3.3 Gene List", headers=_HEADERS,
              banner="The ACMG Secondary Findings v3.3 list is provided here", name="wb.xlsx") -> Path:
    """A minimal sheet with the real file's layout: banner, blank row, headers, data."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = title
    sheet.append([banner])
    sheet.append([])
    sheet.append(list(headers))
    for row in rows:
        sheet.append(list(row))
    path = tmp_path / name
    book.save(path)
    return path


def _entry(gene, *, mim="123456", disease="Some condition", disorder="654321",
           category="Cancer", inheritance="AD", since="1", report="All P and LP"):
    return (gene, mim, disease, disorder, category, inheritance, since, report)


def _enough_rows(count=MIN_GENES + 5):
    """`count` distinct well-formed genes — enough to clear the MIN_GENES floor."""
    return [_entry(f"GENE{index}") for index in range(count)]


# ── the defect this whole module exists for ────────────────────────────────────────────────────────


def test_a_v33_gene_is_reported_as_wrong_against_the_v32_page():
    """The old behaviour, run on the old data: a right row called wrong.

    This is the failure `parse_acmg_page`'s five guards were built to prevent, arriving by a route no
    guard can see — the page is well-formed, complete and simply a release behind. Demonstrated on the
    real v3.2 fixture rather than asserted, so the fix below is measured against an observed defect.
    """
    page = parse_acmg_page(_V32_PAGE)
    assert page.version == "3.2"
    assert not (V33_ADDITIONS & page.genes), "the v3.2 page must not carry the v3.3 additions"

    rows = [
        VariantRow(rsid="rs1800562", genotype="A/A", state="risk", conclusion="x", gene=gene, acmg_sf=True)
        for gene in sorted(V33_ADDITIONS)
    ]
    # `check_acmg_sf` against a list that does not know it is stale: every row is a hard mismatch.
    page.version = KNOWN_LATEST_SF_VERSION  # pretend it is current, i.e. the pre-fix code path
    stale_blind = check_acmg_sf(rows, page)
    assert len(stale_blind.mismatches) == len(V33_ADDITIONS)
    assert {v.verdict for v in stale_blind.mismatches} == {"not_listed"}


def test_the_same_rows_are_unverifiable_once_the_list_admits_it_is_superseded():
    """The fix: a disagreement against a superseded list is a question, not a defect."""
    page = parse_acmg_page(_V32_PAGE)
    rows = [
        VariantRow(rsid="rs1800562", genotype="A/A", state="risk", conclusion="x", gene=gene, acmg_sf=True)
        for gene in sorted(V33_ADDITIONS)
    ]
    report = check_acmg_sf(rows, page)
    assert report.mismatches == []
    assert report.clean, "strict must not refuse on a disagreement the list cannot settle"
    assert len(report.unverifiable) == len(V33_ADDITIONS)
    assert all(f"v{KNOWN_LATEST_SF_VERSION} is published" in v.message for v in report.unverifiable)


def test_strict_refuses_on_a_real_mismatch_but_not_on_an_unverifiable_one():
    """The two halves must not collapse into each other: `strict` still has teeth on a current list."""
    page = parse_acmg_page(_V32_PAGE)
    assert page.superseded_by == KNOWN_LATEST_SF_VERSION

    # A gene on no SF list in any version — that disagreement is real whatever the version.
    junk = [VariantRow(rsid="rs1800562", genotype="A/A", state="risk", conclusion="x",
                       gene="HBB", acmg_sf=True)]
    # Against the stale page: unverifiable, so strict passes.
    verify_acmg_sf(junk, mode="strict", page_text=_V32_PAGE)

    # Against a list that is not superseded, the same row refuses.
    page.version = KNOWN_LATEST_SF_VERSION
    report = check_acmg_sf(junk, page)
    assert [v.verdict for v in report.mismatches] == ["not_listed"]


# ── the workbook parse ─────────────────────────────────────────────────────────────────────────────


def test_prose_in_the_gene_column_is_not_a_gene(tmp_path):
    """ACMG's trailing disclaimer sits in the Gene column — the same shape as the `<tr>` bug.

    Skipped only because every other cell in its row is empty; that condition is what separates a note
    from a data row whose symbol could not be read.
    """
    disclaimer = "Disclaimer: This statement is designed primarily as an educational resource " * 8
    path = _workbook(tmp_path, [*_enough_rows(), (disclaimer, None, None, None, None, None, None, None)])
    sf_list = parse_acmg_workbook(path)
    assert not any(len(gene) > 20 for gene in sf_list.genes)
    assert len(sf_list.genes) == MIN_GENES + 5


def test_an_unreadable_symbol_on_a_populated_row_refuses_rather_than_dropping_a_gene(tmp_path):
    """The other side of the same guard: refusing beats returning a list short by a gene."""
    path = _workbook(tmp_path, [*_enough_rows(), ("a gene name we cannot read", "123456", "X",
                                                 "1", "Cancer", "AD", "1", "All P and LP")])
    with pytest.raises(AcmgSfError, match="not ACMG's trailing disclaimer"):
        parse_acmg_workbook(path)


def test_a_symbol_with_no_gene_mim_refuses(tmp_path):
    path = _workbook(tmp_path, [*_enough_rows(), ("BRCA1", None, "X", "1", "Cancer", "AD", "1", "All")])
    with pytest.raises(AcmgSfError, match="no Gene MIM"):
        parse_acmg_workbook(path)


def test_a_truncated_workbook_trips_the_same_floor_as_the_page(tmp_path):
    path = _workbook(tmp_path, _enough_rows(3))
    with pytest.raises(AcmgSfError, match=f"below the {MIN_GENES} floor"):
        parse_acmg_workbook(path)


def test_a_sheet_with_no_version_refuses(tmp_path):
    path = _workbook(tmp_path, _enough_rows(), title="Gene List", banner="a list of genes")
    with pytest.raises(AcmgSfError, match="declare an 'ACMG SF vN.N' version"):
        parse_acmg_workbook(path)


def test_a_tab_and_a_banner_that_disagree_on_the_version_refuse(tmp_path):
    """A renamed tab beside unrenamed contents reports the wrong version alongside the right genes."""
    path = _workbook(tmp_path, _enough_rows(), title="ACMG SF v3.3 Gene List",
                     banner="The ACMG Secondary Findings v3.2 list is provided here")
    with pytest.raises(AcmgSfError, match="refusing rather than reporting against a version"):
        parse_acmg_workbook(path)


def test_columns_are_resolved_by_name_so_a_reorder_moves_the_reader(tmp_path):
    """Positional reads would silently shift every value; `Gene` vs `Gene MIM` is the hard case."""
    reordered = ("Variants to report", "Gene MIM", "Gene", "Disorder MIM",
                 "SF List Version", "Inheritance ", "Phenotype Category", "Disease/Phentyope")
    rows = [("All P and LP", "123456", f"GENE{i}", "654321", "1", "AD", "Cancer", "Cond")
            for i in range(MIN_GENES + 5)]
    sf_list = parse_acmg_workbook(_workbook(tmp_path, rows, headers=reordered))
    assert {f.gene for f in sf_list.findings} == {f"GENE{i}" for i in range(MIN_GENES + 5)}
    assert all(f.gene_mim == "123456" and f.variants_to_report == "All P and LP"
               for f in sf_list.findings)


def test_a_missing_column_refuses(tmp_path):
    headers = tuple(h for h in _HEADERS if h != "Phenotype Category")
    rows = [_entry(f"GENE{i}")[:4] + _entry(f"GENE{i}")[5:] for i in range(MIN_GENES + 5)]
    with pytest.raises(AcmgSfError, match="no row in the first 10"):
        parse_acmg_workbook(_workbook(tmp_path, rows, headers=headers))


def test_embedded_newlines_and_padding_are_collapsed_not_preserved(tmp_path):
    """Three real cells carry line breaks; a value written on two lines is the same value."""
    rows = [*_enough_rows(), _entry("GLA", category="Cardiovascular\nMetabolic",
                                    inheritance="XL ", disorder="204100,\n613794")]
    entry = next(f for f in parse_acmg_workbook(_workbook(tmp_path, rows)).findings if f.gene == "GLA")
    assert entry.phenotype_category == "Cardiovascular Metabolic"
    assert entry.inheritance == "XL"
    assert entry.disease_mims == ("204100", "613794")


def test_a_none_release_label_becomes_null_not_the_string(tmp_path):
    """`SF List Version` carries the literal `None` for one entry; tri-state, not a label."""
    rows = [*_enough_rows(), _entry("MYH7", since="None")]
    entry = next(f for f in parse_acmg_workbook(_workbook(tmp_path, rows)).findings if f.gene == "MYH7")
    assert entry.since_version is None


# ── the snapshot round-trip ────────────────────────────────────────────────────────────────────────


def test_the_snapshot_reads_back_to_the_same_list(tmp_path):
    """Build → read is lossless on everything a verdict or a message uses."""
    rows = [*_enough_rows(), _entry("HFE", mim="613609", disease="Hereditary hemochromatosis",
                                    category="Other", inheritance="AR", since="1",
                                    report="p.C282Y homozygotes only")]
    built = build_acmg_snapshot(_workbook(tmp_path, rows), tmp_path / "snap")
    loaded = load_acmg_snapshot(tmp_path / "snap")

    assert loaded.version == built.version
    assert loaded.genes == built.genes
    # Sheet order preserved, never set order (P7) — the CSV is byte-reproducible from the workbook.
    assert [f.gene for f in loaded.findings] == [f.gene for f in built.findings]
    assert loaded.findings == built.findings


def test_the_release_pins_the_bytes_it_was_built_from(tmp_path):
    """A snapshot with no hash of its input is a claim about ACMG's list with nothing behind it."""
    import hashlib

    workbook = _workbook(tmp_path, _enough_rows())
    build_acmg_snapshot(workbook, tmp_path / "snap", source_url="https://example.invalid/wb.xlsx")
    release = json.loads((tmp_path / "snap" / SNAPSHOT_RELEASE).read_text())

    assert release["source_sha256"] == "sha256:" + hashlib.sha256(workbook.read_bytes()).hexdigest()
    assert release["sf_version"] == "3.3"
    assert release["gene_count"] == release["row_count"] == MIN_GENES + 5
    assert release["source_url"] == "https://example.invalid/wb.xlsx"


def test_a_snapshot_directory_that_is_not_one_says_so(tmp_path):
    with pytest.raises(AcmgSfError, match="is not an ACMG SF snapshot"):
        load_acmg_snapshot(tmp_path)


def test_a_release_with_no_version_refuses(tmp_path):
    build_acmg_snapshot(_workbook(tmp_path, _enough_rows()), tmp_path / "snap")
    (tmp_path / "snap" / SNAPSHOT_RELEASE).write_text(json.dumps({"gene_count": 55}))
    with pytest.raises(AcmgSfError, match="records no sf_version"):
        load_acmg_snapshot(tmp_path / "snap")


def test_a_truncated_snapshot_csv_trips_the_floor(tmp_path):
    build_acmg_snapshot(_workbook(tmp_path, _enough_rows()), tmp_path / "snap")
    csv_path = tmp_path / "snap" / SNAPSHOT_CSV
    lines = csv_path.read_text().splitlines()
    csv_path.write_text("\n".join(lines[:5]) + "\n")
    with pytest.raises(AcmgSfError, match=f"below the {MIN_GENES}"):
        load_acmg_snapshot(tmp_path / "snap")


def test_an_injected_snapshot_makes_the_check_work_offline(tmp_path):
    """The capability the snapshot adds: `--offline` used to mean `unchecked` for every row.

    `url` is a host that cannot resolve, so a fetch would raise rather than quietly succeed — the
    snapshot preference is proven by the absence of network, not by a mock.
    """
    rows = [*_enough_rows(), _entry("HFE", disease="Hereditary hemochromatosis")]
    build_acmg_snapshot(_workbook(tmp_path, rows), tmp_path / "snap")
    variants = [VariantRow(rsid="rs1800562", genotype="A/A", state="risk", conclusion="x",
                           gene="HFE", acmg_sf=True)]

    report = verify_acmg_sf(variants, offline=True, snapshot_dir=tmp_path / "snap",
                            url="http://acmg.invalid/")
    assert report.version == "3.3"
    assert report.checked == 1
    assert [v.verdict for v in report.verdicts] == ["agree"]
    assert report.warnings == [], "a snapshot is a current list; nothing to warn about"


def test_offline_without_a_snapshot_is_still_unchecked_not_absent(tmp_path):
    variants = [VariantRow(rsid="rs1800562", genotype="A/A", state="risk", conclusion="x",
                           gene="ABCD1", acmg_sf=True)]
    report = verify_acmg_sf(variants, offline=True)
    assert [v.verdict for v in report.verdicts] == ["unchecked"]
    assert report.checked == 0
    assert report.clean


# ── the real workbook, when the author has it ─────────────────────────────────────────────────────


def test_the_real_v33_workbook_parses_to_its_published_shape():
    """Ground truth against the actual published supplement, computed rather than transcribed."""
    sf_list = parse_acmg_workbook(_REAL_WORKBOOK)
    assert sf_list.version == "3.3"
    assert sf_list.superseded_by is None, "v3.3 is the newest release this package knows of"

    page = parse_acmg_page(_V32_PAGE)
    # The whole reason the workbook exists here: it is a strict superset of the page NCBI serves.
    assert page.genes < sf_list.genes
    assert sf_list.genes - page.genes == V33_ADDITIONS
    # And each addition is labelled with the release that added it, by ACMG itself.
    assert {f.gene for f in sf_list.findings if f.since_version == "3.3"} == V33_ADDITIONS
    # Every gene-condition row keeps its inheritance and category; those columns are workbook-only.
    assert all(f.inheritance and f.phenotype_category for f in sf_list.findings)
    # ACMG scopes HFE to one genotype, and that text is carried without being applied.
    hfe = next(f for f in sf_list.findings if f.gene == "HFE")
    assert "C282Y" in (hfe.variants_to_report or "")


def test_the_real_workbook_settles_what_the_page_could_not(tmp_path):
    """End to end: the v3.3 additions go from `unverifiable` to `agree`."""
    build_acmg_snapshot(_REAL_WORKBOOK, tmp_path / "snap")
    variants = [
        VariantRow(rsid="rs1800562", genotype="A/A", state="risk", conclusion="x", gene=gene, acmg_sf=True)
        for gene in sorted(V33_ADDITIONS)
    ]
    stale = verify_acmg_sf(variants, page_text=_V32_PAGE)
    assert len(stale.unverifiable) == 3 and stale.mismatches == []

    current = verify_acmg_sf(variants, mode="strict", snapshot_dir=tmp_path / "snap")
    assert [v.verdict for v in current.verdicts] == ["agree"] * 3
    assert current.unverifiable == [] and current.warnings == []


def test_parse_sf_version_reads_both_publisher_spellings():
    assert parse_sf_version("ACMG SF v3.2") == "3.2"
    assert parse_sf_version("The ACMG Secondary Findings v3.3 list") == "3.3"
    assert parse_sf_version("no version here") is None
