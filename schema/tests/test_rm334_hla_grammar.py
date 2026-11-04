"""The HLA nomenclature grammar on `allele_function.csv` (0.8, RM334).

An HLA allele has no table of its own: `allele_function.csv`, keyed `(gene, allele)`, holds it. Where
`gene` starts with `HLA-`, `allele` is an IPD-IMGT/HLA name, and that is a grammar rather than a free
name: `*`, then two to four colon-separated numeric fields of at least two digits each, then an
optional expression suffix (`N`, `L`, `S`, `C`, `A`, `Q`). The field count is the resolution the name
states, so no column states it, and a name with fewer than two fields is refused (PROPOSAL_0_8_PT2 §3
item 22).

Every other gene keeps the permissive haplotype-name rule (`*4`, `e4`, `Se`): the check reads `gene`,
never the shape of `allele`, so a star allele that happens to contain colons is not pulled in either.

A malformed name is a **refusal**, at the model, so `validate_spec` and `compile` refuse it alike.
Principle 3 allowed that only because the published-module scan of 2026-11-04 found no published
`allele_function.csv` row with an `HLA-` gene (the reference examples and every version in the
registry's prod catalogue; INTEGRATION_0_8 records the numbers). The examples half of the scan is
re-run here, against the files, so a reference example that later gains an HLA row is checked by the
same rule.
"""

import csv
import re
from pathlib import Path

import pytest
from just_dna_format.pgx import HLA_ALLELE_PATTERN, AlleleFunctionRow
from pydantic import ValidationError

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

#: Two, three and four fields, and a suffix on a four-field name: the cases PT2 §5 A4 names, plus a
#: three-digit field (IPD-IMGT/HLA has run past `:99` in several genes) and each expression suffix.
_ACCEPTED: tuple[tuple[str, str], ...] = (
    ("HLA-DRB1", "*15:01"),
    ("HLA-B", "*57:01:01"),
    ("HLA-A", "*02:01:01:02N"),
    ("HLA-A", "*01:101"),
    *(("HLA-C", f"*04:09{suffix}") for suffix in "NLSCAQ"),
)

#: Each refused for a different reason: no `*`; the pre-2010 colon-less spelling; a suffix outside the
#: set; one field only (no stated resolution); five fields; a one-digit field; the gene repeated inside
#: the allele; a trailing colon.
_REFUSED: tuple[tuple[str, str], ...] = (
    ("HLA-DRB1", "15:01"),
    ("HLA-DRB1", "*1501"),
    ("HLA-DRB1", "*15:01X"),
    ("HLA-DRB1", "*15"),
    ("HLA-A", "*02:01:01:02:01"),
    ("HLA-B", "*5:01"),
    ("HLA-B", "HLA-B*57:01"),
    ("HLA-B", "*57:01:"),
)


@pytest.mark.parametrize("gene,allele", _ACCEPTED, ids=lambda v: str(v))
def test_a_well_formed_hla_name_is_accepted_and_stored_verbatim(gene: str, allele: str) -> None:
    row = AlleleFunctionRow(gene=gene, allele=allele)
    assert row.allele == allele


@pytest.mark.parametrize("gene,allele", _REFUSED, ids=lambda v: str(v))
def test_a_malformed_hla_name_is_refused_naming_the_expected_shape(gene: str, allele: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        AlleleFunctionRow(gene=gene, allele=allele)
    message = str(excinfo.value)
    # The words that make the refusal a fix rather than a dead end (`@specific-rejection`), pinned on a
    # boundary: the registry whose grammar it is, the shape, an example, and the value that was given.
    assert re.search(r"\bIPD-IMGT/HLA\b", message)
    assert re.search(r"\btwo to four colon-separated numeric fields\b", message)
    assert "*15:01" in message
    assert repr(allele) in message
    assert gene in message


@pytest.mark.parametrize(
    "gene,allele",
    [
        ("CYP2D6", "*4"),
        ("CYP2C19", "*17"),
        ("APOE", "e4"),
        ("FUT2", "se428"),
        # A non-HLA gene with an HLA-shaped or malformed-HLA-shaped name: the gene decides, not the name.
        ("CYP2D6", "*15:01X"),
        ("KIR2DL1", "*0010101"),
    ],
)
def test_a_gene_outside_hla_keeps_the_permissive_name_rule(gene: str, allele: str) -> None:
    assert AlleleFunctionRow(gene=gene, allele=allele).allele == allele


def test_the_grammar_is_the_whole_name_not_a_prefix_of_it() -> None:
    """`fullmatch` semantics: a pattern that only anchored the start would accept `*15:01 typo`."""
    assert HLA_ALLELE_PATTERN.fullmatch("*15:01")
    assert not HLA_ALLELE_PATTERN.fullmatch("*15:01 typo")
    with pytest.raises(ValidationError):
        AlleleFunctionRow(gene="HLA-DRB1", allele="*15:01:01:01Nx")


def test_every_reference_example_hla_allele_function_row_follows_the_grammar() -> None:
    """The examples half of the published-module scan, kept running.

    On 2026-11-04 no reference example carried an `HLA-` row in `allele_function.csv`; the assertion is
    that every such row validates, so it holds over that empty set and keeps holding over the next
    example that adds one.
    """
    for path in sorted(_EXAMPLES.glob("*/allele_function.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["gene"].startswith("HLA-"):
                    assert HLA_ALLELE_PATTERN.fullmatch(row["allele"]), (path, row["allele"])
