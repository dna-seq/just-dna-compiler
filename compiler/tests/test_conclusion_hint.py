"""RM279: a `variants.csv` conclusion that names another genotype at its locus and never its own.

The positive cases are rows from the curated v1 ports a consumer measured (D14), quoted: the defect is
in the prose, so a synthetic sentence would test the regex rather than the rule. The negative cases are
the four false-positive shapes the measurement removed, each pinned by the text that produced it.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.hints import Finding, inspect_rows

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HEADER = ["rsid", "genotype", "state", "conclusion", "gene"]


def _csv(rows: list[tuple[str, str, str, str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_HEADER)
    writer.writerows(rows)
    return buf.getvalue()


def _conclusion_findings(text: str) -> list[Finding]:
    return [f for f in inspect_rows("variants.csv", text).findings if f.column == "conclusion"]


# coronary rs17514846 — the C/C and A/A conclusions are swapped in the source module.
_SWAPPED = [
    ("rs17514846", "A/C", "neutral", "AC genotype carriers have a moderate risk of CAD.", "FURIN"),
    ("rs17514846", "C/C", "neutral", "AA genotype is associated with increased CAD risk.", "FURIN"),
    ("rs17514846", "A/A", "neutral", "CC genotype is not associated with increased risk.", "FURIN"),
]


def test_a_swapped_pair_is_two_findings_naming_each_other() -> None:
    findings = _conclusion_findings(_csv(_SWAPPED))
    assert {f.row for f in findings} == {1, 2}
    by_row = {f.row: f.message for f in findings}
    assert "names genotype A/A (on line 4)" in by_row[1]
    assert "names genotype C/C (on line 3)" in by_row[2]
    assert all(f.level == "warning" and f.line == f.row + 2 for f in findings)


def test_a_row_carrying_its_neighbours_text_is_named() -> None:
    """thrombophilia rs1799963: the A/A row reuses the heterozygote's sentence."""
    rows = [
        ("rs1799963", "G/G", "neutral", "GG genotype is not associated with increased risk.", "F2"),
        ("rs1799963", "A/G", "risk", "GA carriers have 2.8x risk of thrombosis [PMID 23900608].", "F2"),
        ("rs1799963", "A/A", "risk", "GA carriers have 6.74x risk of thrombosis [PMID 23900608].", "F2"),
    ]
    findings = _conclusion_findings(_csv(rows))
    assert [f.row for f in findings] == [2]
    assert "A/G (on line 3)" in findings[0].message


def test_a_correct_row_naming_its_neighbour_too_is_quiet() -> None:
    """The looser reading ("names any other genotype") fired here, and on 13 more like it."""
    rows = [
        ("rs2943634", "A/A", "protective", "AA genotype is protective, AC carriers less so.", "IRS1"),
        ("rs2943634", "A/C", "neutral", "AC carriers sit between AA and CC.", "IRS1"),
        ("rs2943634", "C/C", "risk", "CC-carriers have higher risk of ischemic stroke.", "IRS1"),
    ]
    assert _conclusion_findings(_csv(rows)) == []


@pytest.mark.parametrize(
    "rsid,genotype,alleles_row,conclusion,gene",
    [
        # Letters that are not this locus's bases: the reporter's first version flagged this.
        ("rs1", "C/T", "T/T", "raised plasma triglyceride (TG) levels", "APOA5"),
        # An allele description straight after an rsID.
        ("rs1042718", "A/A", "C/C", "rs1042718 (C/A) and rs1042719 (G/C) are in LD.", "ADRB2"),
        # A haplotype spanning two sites.
        ("rs3758391", "C/T", "T/T", "The haplotype CC of rs3758391 and rs4746720 was higher.", "SIRT1"),
        # The row's own gene symbol, as a ClinVar-templated row writes it.
        ("rs377652873", "A/A", "G/T", "ClinVar Likely pathogenic variant in TG", "TG"),
    ],
    ids=["not-this-locus", "after-an-rsid", "haplotype", "own-gene-symbol"],
)
def test_the_measured_false_positive_shapes_are_quiet(
    rsid: str, genotype: str, alleles_row: str, conclusion: str, gene: str
) -> None:
    rows = [
        (rsid, genotype, "risk", conclusion, gene),
        (rsid, alleles_row, "neutral", "no genotype named here", gene),
    ]
    assert _conclusion_findings(_csv(rows)) == []


def test_a_lowercase_pair_is_a_word_not_a_genotype() -> None:
    rows = [
        ("rs1", "A/A", "risk", "at least one study reports an effect", "X"),
        ("rs1", "T/T", "neutral", "no effect", "X"),
    ]
    assert _conclusion_findings(_csv(rows)) == []


def test_every_shipped_reference_example_is_quiet() -> None:
    """Real data: none of the shipped examples states a conclusion for the wrong genotype."""
    tables = sorted(_EXAMPLES.rglob("variants.csv"))
    assert tables, "no reference example carries a variants.csv"
    loud = {str(t.relative_to(_EXAMPLES)): _conclusion_findings(t.read_text()) for t in tables}
    assert {k: v for k, v in loud.items() if v} == {}
