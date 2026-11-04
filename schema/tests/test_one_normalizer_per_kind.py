"""One value, one normalizer (RM363, `@one-normalizer-two-spellings`).

A gene symbol, a drug name, a DOI and a chromosome are each written more than one way, and each is
compared or keyed in more than one place. The defect class is a second place that compares them by a
different rule than the first: `Apoe` matched as a gene by one PGx check and missed by the meta-table's
expansion, `chr12` folded on `variants.csv` and kept on `studies.csv`, a DOI with a trailing `.` one
citation to the literature pass and two to the duplicate check.

The mechanism is `just_dna_format.spelling`: one comparison per kind, keyed by column name, and one
input fold for `chrom`. The guards below are equalities over walked sets, so a new field of a kind, a new
comparison site or a re-typed normalizer turns red rather than silently adding a second rule.
"""

import ast
import re
from pathlib import Path
from typing import get_args

import pytest
from just_dna_format.pgx import DiplotypeRow, HaplotypeRow, PharmVariantRow
from just_dna_format.reference import _ALL_MODELS
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.spelling import (
    COMPARISON_KEYS,
    VALID_CHROMOSOMES,
    comparison_key,
    distinct_spellings,
    doi_key,
    drug_key,
    fold_chrom,
    gene_key,
)
from pydantic import AfterValidator, BaseModel

_ROOT = Path(__file__).resolve().parents[2]
_SOURCES = {tier: _ROOT / tier / "src" for tier in ("schema", "compiler", "enricher")}

#: A field holding a value of a compared kind, by name. A field whose name says it is one of these
#: kinds and that `COMPARISON_KEYS` does not register is the next instance of the class.
_KIND_NAME = re.compile(r"(^|_)(gene|drug|doi)$|^chrom$")


def _models() -> list[type[BaseModel]]:
    return list(_ALL_MODELS.values())


# ── the registry is exactly the walked set ─────────────────────────────────────────────────────────


def test_every_field_of_a_compared_kind_is_registered() -> None:
    walked = {
        name
        for model in _models()
        for name, field in model.model_fields.items()
        if _KIND_NAME.search(name) and str in get_args(field.annotation) + (field.annotation,)
    }
    assert walked, "the walk found no field of a compared kind: the pattern or the registry moved"
    assert walked == set(COMPARISON_KEYS)


def test_every_chrom_field_folds_on_input() -> None:
    with_chrom = {
        (model.__name__, name) for model in _models() for name in model.model_fields if name == "chrom"
    }
    folding = {
        (model.__name__, name)
        for model in _models()
        for name, field in model.model_fields.items()
        if any(isinstance(m, AfterValidator) and m.func is fold_chrom for m in field.metadata)
    }
    assert with_chrom, "no model declares `chrom`: the walk is broken"
    assert folding == with_chrom


# ── the comparisons ─────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("column", "one", "other"),
    [
        ("gene", "APOE", " Apoe "),
        ("modifier_gene", "CYP2C19", "cyp2c19"),
        ("drug", "azathioprine", "Azathioprine"),
        ("doi", "10.1101/2024.01.01.123456", "https://doi.org/10.1101/2024.01.01.123456."),
        ("doi", "10.1038/S41586-020-2308-7", "10.1038/s41586-020-2308-7;"),
        ("doi", "10.1101/2025.03.01.640000", "(10.1101/2025.03.01.640000)"),
        ("doi", "10.1000/abc", '"10.1000/abc";'),
        ("chrom", "12", "chr12"),
    ],
)
def test_two_spellings_of_one_value_compare_equal(column: str, one: str, other: str) -> None:
    assert comparison_key(column, one) == comparison_key(column, other)


def test_a_column_of_no_registered_kind_compares_verbatim() -> None:
    assert comparison_key("haplotype_name", "*4A") != comparison_key("haplotype_name", "*4a")
    assert comparison_key("gene", None) is None


def test_the_doi_key_is_the_literature_passs_token() -> None:
    # The two bodies this replaced disagreed on exactly this cell (the audit's measured pair).
    assert doi_key("10.1101/2024.01.01.123456.") == "10.1101/2024.01.01.123456"
    assert doi_key("doi:10.1000/X,") == "10.1000/x"
    # A bracket the DOI opens is part of it; only an unbalanced closer is the prose around it.
    assert doi_key("10.1016/S0140-6736(17)30058-2.") == "10.1016/s0140-6736(17)30058-2"


def test_distinct_spellings_keeps_the_first_and_sorts() -> None:
    assert distinct_spellings(["CYP2C19", "APOE", "Apoe", "cyp2c19"], "gene") == ["APOE", "CYP2C19"]


# ── stored values ───────────────────────────────────────────────────────────────────────────────────


def _diplotype(**overrides: str) -> DiplotypeRow:
    return DiplotypeRow(
        **{"gene": "Tpmt", "haplotype_a": "*1", "haplotype_b": "*3A", "conclusion": "x", **overrides}
    )


def test_gene_and_drug_are_stored_verbatim() -> None:
    row = _diplotype(drug="Azathioprine")
    assert (row.gene, row.drug) == ("Tpmt", "Azathioprine")
    assert (gene_key(row.gene), drug_key(row.drug)) == ("tpmt", "azathioprine")


@pytest.mark.parametrize(
    "build",
    [
        lambda chrom: StudyRow(chrom=chrom, start=111446804, ref="C", pmid="30642433"),
        lambda chrom: HaplotypeRow(
            gene="CYP2C19", haplotype_name="*2", chrom=chrom, start=94781859, ref="G", allele="A"
        ),
        lambda chrom: PharmVariantRow(
            gene="CYP2C19", chrom=chrom, start=94781859, ref="G", drug="x", conclusion="x"
        ),
        lambda chrom: VariantRow(
            chrom=chrom, start=111446804, ref="C", alts="T", genotype="C/C", state="neutral", conclusion="x"
        ),
    ],
    ids=["StudyRow", "HaplotypeRow", "PharmVariantRow", "VariantRow"],
)
def test_a_chr_prefixed_contig_is_stored_as_the_member(build) -> None:
    assert build("chr12").chrom == "12"
    assert build("chrM").chrom == "MT"
    assert build("12").chrom == "12"


def test_a_contig_off_the_primary_assembly_is_kept_verbatim_where_nothing_refused_it() -> None:
    # The fold widens nothing and tightens nothing: a model that never refused a scaffold still does
    # not, and keeps the authored spelling, while `VariantRow` refuses it naming what was written.
    assert StudyRow(chrom="chrUn_KI270302v1", start=1, ref="C", pmid="30642433").chrom == "chrUn_KI270302v1"
    with pytest.raises(ValueError, match="chrUn_KI270302v1"):
        VariantRow(
            chrom="chrUn_KI270302v1", start=1, ref="C", genotype="C/C", state="neutral", conclusion="x"
        )


def test_fold_chrom_is_a_fixed_point_over_the_vocabulary() -> None:
    assert {fold_chrom(c) for c in VALID_CHROMOSOMES} == set(VALID_CHROMOSOMES)
    assert {fold_chrom(f"chr{c}") for c in VALID_CHROMOSOMES} == set(VALID_CHROMOSOMES) | {"MT"}


# ── the sites: AST walks over every tier ────────────────────────────────────────────────────────────

#: The names a comparison key is applied through. A compared attribute inside a call to one of these is
#: already normalized.
_KEY_CALLS = frozenset(
    {"gene_key", "drug_key", "doi_key", "doi_token", "comparison_key", "distinct_spellings"}
)

#: The attributes whose raw comparison is the defect. `chrom` is folded on input, so a stored `chrom`
#: already is its key and compares raw.
_COMPARED = frozenset(name for name in COMPARISON_KEYS if name != "chrom")

#: Sites comparing a source's own records among themselves — one spelling, one source, never an authored
#: cell against anything — each with the reason. An equality, so a site fixed or added moves it.
_ONE_SOURCE_SITES: dict[tuple[str, str], str] = {
    ("enricher/src/just_dna_enricher/acmg.py", "f.gene == gene"): "ACMG SF findings against their own list",
    ("enricher/src/just_dna_enricher/acmg.py", "{f.gene for f in findings}"): "the ACMG SF list's own genes",
    ("enricher/src/just_dna_enricher/acmg.py", "len({f.gene for f in findings}) < MIN_GENES"): (
        "the ACMG SF list's own genes"
    ),
    ("enricher/src/just_dna_enricher/strchive_draft.py", "(locus.gene, motif) in contested"): (
        "STRchive's loci against their own contested set"
    ),
    (
        "enricher/src/just_dna_enricher/acmg_build.py",
        "{f.gene for f in findings}",
    ): "the ACMG SF list's own genes",
    (
        "enricher/src/just_dna_enricher/cli/acmg_commands.py",
        "{f.gene for f in sf_list.findings if f.since_version == sf_list.version}",
    ): "the ACMG SF list's own genes",
    ("enricher/src/just_dna_enricher/strchive.py", "index.setdefault((locus.gene, motif), [])"): (
        "STRchive's loci indexed by their own gene"
    ),
    ("enricher/src/just_dna_enricher/strchive_draft.py", "claims.setdefault((locus.gene, motif), [])"): (
        "STRchive's loci grouped by their own gene"
    ),
}


def _inside_key_call(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    while node in parents:
        node = parents[node]
        if isinstance(node, ast.Call):
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else ""
            )
            if name in _KEY_CALLS:
                return True
    return False


def _raw(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    return any(
        isinstance(sub, ast.Attribute) and sub.attr in _COMPARED and not _inside_key_call(sub, parents)
        for sub in ast.walk(node)
    )


def _comparison_sites(path: Path) -> set[str]:
    """Every place in one file that compares or keys a compared attribute without its key function."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if all(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops):
                continue
            if any(_raw(side, parents) for side in (node.left, *node.comparators)):
                found.add(ast.unparse(node))
        elif isinstance(node, (ast.SetComp, ast.DictComp)):
            element = node.elt if isinstance(node, ast.SetComp) else node.key
            if _raw(element, parents):
                found.add(ast.unparse(node))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("setdefault", "add", "get")
            and node.args
            and _raw(node.args[0], parents)
        ):
            found.add(ast.unparse(node))
    return found


def test_no_site_compares_a_compared_kind_raw() -> None:
    found = {
        (str(path.relative_to(_ROOT)), site)
        for tier in ("compiler", "enricher")
        for path in sorted(_SOURCES[tier].rglob("*.py"))
        for site in _comparison_sites(path)
    }
    assert found == set(_ONE_SOURCE_SITES)


_OWNER = _SOURCES["schema"] / "just_dna_format" / "spelling.py"

#: A hand-rolled normalizer: a case fold applied straight to a value named as a compared kind.
_FOLDS = frozenset({"lower", "upper", "casefold"})


def _hand_rolled(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _FOLDS
        ):
            continue
        receiver = node.func.value
        while isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Attribute):
            receiver = receiver.func.value  # through `.strip()` and friends
        name = receiver.attr if isinstance(receiver, ast.Attribute) else getattr(receiver, "id", "")
        if _KIND_NAME.search(name) and name != "chrom" and path != _OWNER:
            found.add(f"{path.relative_to(_ROOT)}: {ast.unparse(node)}")
    return found


def test_no_tier_re_types_a_normalizer() -> None:
    found = set().union(*(_hand_rolled(p) for src in _SOURCES.values() for p in sorted(src.rglob("*.py"))))
    assert found == set()


def test_the_doi_pattern_is_read_only_by_the_doi_rule() -> None:
    """`DOI_PATTERN.search` outside the module that owns the DOI rule is a second DOI normalizer."""
    owners = {_OWNER, _SOURCES["schema"] / "just_dna_format" / "spec.py"}
    found = {
        str(path.relative_to(_ROOT))
        for src in _SOURCES.values()
        for path in sorted(src.rglob("*.py"))
        if path not in owners
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Attribute)
        and node.attr in ("search", "finditer", "match", "fullmatch", "findall")
        and isinstance(node.value, ast.Name)
        and node.value.id == "DOI_PATTERN"
    }
    assert found == set()
