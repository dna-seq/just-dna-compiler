"""A site annotated for some of its genotypes and not the rest (S32).

A consumer joins on `(variant, genotype)`, so a genotype with no row is a subject with no answer. The
report that produced this found a curated 520-site module authoring no homozygous-alternate genotype at
208 of them, with the reporting subject homozygous at 74 — every one silently unreported, and no tool
said so.

What is pinned here is mostly **scope**, because the scope is the design: this check is one aggregated
line or it is noise on every module ever drafted. The corpus cases are asserted by their exact sites,
so a future widening that starts reporting single-genotype sites fails here rather than in someone's
build log.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import _check_genotype_coverage, validate_spec
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _variant(genotype: str, **kwargs: object) -> VariantRow:
    fields: dict[str, object] = {"state": "risk", "conclusion": "x", "genotype": genotype}
    fields.update(kwargs)
    return VariantRow(**fields)  # type: ignore[arg-type]


def _findings(variants: list[VariantRow], table: dict[str, list[ResolutionRow]] | None = None):
    return _check_genotype_coverage(variants, table or {})


def test_a_site_with_one_genotype_is_a_rule_not_a_gap() -> None:
    """The scope decision the whole check rests on.

    `pathogenic_clinvar` authors exactly one genotype at 326 of its 327 sites — the ordinary shape of a
    drafted-then-curated module, and a legitimate one: a rule that fires on the risk genotype and says
    nothing otherwise is a rule. Reporting those would put a line on almost every module in existence.
    """
    assert (
        _findings([_variant("A/G", chrom="1", start=100, ref="G", alts="A", rsid=None)]) == []
    )


def test_the_missing_homozygous_alternate_is_the_reported_case() -> None:
    """The consumer's defect: het authored, hom-alt not, so a homozygous subject matches nothing."""
    rows = [
        _variant("A/G", chrom="1", start=100, ref="G", alts="A"),
        _variant("G/G", chrom="1", start=100, ref="G", alts="A"),
    ]
    findings = _findings(rows)
    assert len(findings) == 1
    assert "homozygous alternate" in findings[0]
    assert "1:100:G A/A" in findings[0]


def test_an_authored_hom_ref_row_is_never_itself_reported() -> None:
    """Those rows are correct — on array or gVCF data they are the ones carrying the answer.

    The reporter's own argument, and the reason presence is not a finding: only *absence* is.
    """
    complete = [
        _variant("A/A", chrom="1", start=100, ref="G", alts="A"),
        _variant("A/G", chrom="1", start=100, ref="G", alts="A"),
        _variant("G/G", chrom="1", start=100, ref="G", alts="A"),
    ]
    assert _findings(complete) == []


def test_an_alt_alt_pair_is_never_demanded() -> None:
    """RM35's lesson: a check whose rules cannot be jointly satisfied warns forever.

    At a two-alternate site `A/T` is expressible and requiring it would make a complete table
    unreachable. Author the reference homozygote, both heterozygotes and both alternate homozygotes and
    the site is complete — with `A/T` absent.
    """
    rows = [
        _variant(gt, chrom="1", start=100, ref="G", alts="A,T")
        for gt in ("G/G", "A/G", "G/T", "A/A", "T/T")
    ]
    assert _findings(rows) == []


def test_a_symbolic_or_hemizygous_site_is_skipped_without_a_contig_list() -> None:
    """MT and non-PAR Y stay out for free: those contigs author one allele per cell, and a cell that is
    not a diploid nucleotide pair has no genotype space to be incomplete in."""
    haploid = [
        _variant("G", chrom="MT", start=3243, ref="A", alts="G"),
        _variant("A", chrom="MT", start=3243, ref="A", alts="G"),
    ]
    symbolic = [
        _variant("<DEL:1500>/A", chrom="1", start=100, ref="A", alts="<DEL:1500>"),
        _variant("A/A", chrom="1", start=100, ref="A", alts="<DEL:1500>"),
    ]
    unobservable = [
        _variant("*/T", chrom="1", start=100, ref="C", alts="T"),
        _variant("C/T", chrom="1", start=100, ref="C", alts="T"),
    ]
    assert _findings(haploid) == []
    assert _findings(symbolic) == []
    assert _findings(unobservable) == []


def test_the_reference_allele_comes_from_the_injected_table_when_no_row_authors_one() -> None:
    """An rsid-authored module carries no coordinate, and its site key *is* the rsID — which is the key
    `resolution.csv` is written under. Without this half the check would be blind on exactly the
    modules a drafting provider produces."""
    rows = [_variant("A/A", rsid="rs1800562"), _variant("A/G", rsid="rs1800562")]
    # Two alleles are enumerable without a reference, so the gap is *found* either way — what the
    # table decides is whether it can be named. Unnamed, the message says so rather than guessing.
    unnamed = _findings(rows)
    assert len(unnamed) == 1
    assert "cannot be said" in unnamed[0]

    table = {
        "rs1800562": [
            ResolutionRow(variant_key="rs1800562", rsid="rs1800562", chrom="6", start=26092913, ref="G", alts="A")
        ]
    }
    findings = _findings(rows, table)
    assert len(findings) == 1
    assert "reference homozygote" in findings[0]
    assert "rs1800562 G/G" in findings[0]


def test_two_alleles_are_enumerable_with_no_reference_and_three_are_not() -> None:
    """With two alleles the three pairs follow without knowing which is the reference, so the finding
    is made by spelling. With three and no reference there is no way to enumerate without inventing an
    alt/alt pair, so the site is skipped rather than guessed at."""
    two = [_variant("A/A", rsid="rs1"), _variant("A/G", rsid="rs1")]
    findings = _findings(two)
    assert len(findings) == 1
    assert "cannot be said" in findings[0]
    assert "rs1 G/G" in findings[0]

    three = [_variant("A/G", rsid="rs2"), _variant("G/T", rsid="rs2")]
    assert _findings(three) == []


def test_one_site_missing_two_genotypes_is_not_reported_as_two_sites() -> None:
    """`hfe_hemochromatosis` is the real instance: one two-alternate locus missing both heterozygotes.

    A bare count read as sites would say this module has a gap at two loci when it has one.
    """
    rows = [
        _variant("A/A", chrom="6", start=26091590, ref="G", alts="A"),
        _variant("T/T", chrom="6", start=26091590, ref="G", alts="T"),
    ]
    het = [f for f in _findings(rows) if "heterozygous" in f]
    assert len(het) == 1
    assert "2 genotype(s) at 1 site(s)" in het[0]


@pytest.mark.parametrize(
    "module,expected",
    [
        ("grch37_build", {"6:26093141:G G/G"}),
        (
            "hfe_hemochromatosis",
            {"6:26091590:G A/G", "6:26091590:G G/T", "6:26091590:G G/G", "rs1800562 G/G"},
        ),
        ("pathogenic_clinvar", {"11:5225715:G C/C", "11:5225715:G T/T", "11:5225715:G G/G"}),
    ],
)
def test_the_corpus_findings_are_exactly_these(module: str, expected: set[str]) -> None:
    """Our own modules, and each is a true statement about them — `pathogenic_clinvar` really does
    leave a homozygote for either HBB allele unreported.

    Asserted as set equality on the *sites*, so both a widening and a narrowing of scope fail here.
    """
    warnings = [w for w in validate_spec(_EXAMPLES / module).warnings if "have no row:" in w]
    found = {
        example.strip()
        for warning in warnings
        for example in warning.split("e.g. ", 1)[1].split(";")
    }
    assert found == expected


def test_the_rest_of_the_corpus_is_silent() -> None:
    """Every other reference example authors one genotype per site, which is not this finding.

    Computed rather than listed: a new example that trips the check has to be looked at, not adjusted
    around.
    """
    noisy = {
        d.name
        for d in sorted(_EXAMPLES.iterdir())
        if (d / "module_spec.yaml").is_file()
        and any("have no row:" in w for w in validate_spec(d).warnings)
    }
    assert noisy == {"grch37_build", "hfe_hemochromatosis", "pathogenic_clinvar"}
