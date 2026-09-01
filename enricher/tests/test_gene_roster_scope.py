"""RM157: the gene set three passes take their scope from read one table while nine carry the column.

`gene_metrics.module_genes` is not a report — it is the **scope** of the constraint-metrics pass, the
gene-validity pass and the ClinGen dosage pass, all three of which call it (the second through a
re-raising wrapper, so it fails as itself). It built its list from `variants.csv` alone, so a module
whose genes live in its PGx tables had all three quietly do nothing at all: no rows, no findings, and
no line saying a question had not been put.

The workspace was already carrying two answers to one question — `pgx._module_genes` reads two PGx
tables — and the narrow one was the one three passes used. Reproduced on this repo's own corpus rather
than on a fixture, because a fixture written to the new roster cannot show the old one was narrow.

Offline throughout: the roster is table-reading and reaches no registry.
"""

from pathlib import Path

import pytest
from just_dna_enricher.gene_metrics import GeneMetricsEnrichmentError, module_genes
from just_dna_enricher.gene_validity import GeneValidityError
from just_dna_enricher.gene_validity import _module_genes as validity_genes
from just_dna_enricher.identifiers import _id_bearing_tables, authored_identifiers

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: rm157\n  title: RM157\n  description: d\n  report_title: RM157\n"
)
_HAPLOTYPES = "haplotype_name,rsid,start,allele,gene\n*2,rs4244285,94781859,A,CYP2C19\n"
_ALLELE_FUNCTION = "gene,allele,function_status\nCYP2C19,*1,normal_function\n"
_VARIANTS = "rsid,genotype,state,conclusion,gene\nrs1801133,C/T,risk,c,MTHFR\n"


def _spec(tmp_path: Path, **tables: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    for name, body in tables.items():
        (spec / name.replace("__", ".")).write_text(body, encoding="utf-8")
    return spec


def test_a_module_with_no_variants_csv_still_has_genes(tmp_path: Path) -> None:
    """The reported shape, and the one four of this repo's reference examples are in."""
    spec = _spec(tmp_path, haplotypes__csv=_HAPLOTYPES, allele_function__csv=_ALLELE_FUNCTION)
    assert module_genes(spec) == ["CYP2C19"]


@pytest.mark.parametrize(
    "example",
    ["cyp2c19_star_alleles", "apoe_epsilon", "cyp2c9_warfarin_grch37", "hfe_compound_het"],
)
def test_the_corpus_this_was_measured_on_names_genes(example: str) -> None:
    """The four shipped modules that returned `[]` here while naming six real symbols between them.

    Read off the repo rather than a fixture on purpose: this is the evidence the scope was wrong, and
    a fixture written to the widened roster could not have produced it.
    """
    spec = Path(__file__).resolve().parents[2] / "reference_examples" / example
    assert not (spec / "variants.csv").exists()
    assert module_genes(spec)


def test_the_scope_is_the_roster_and_not_a_second_answer(tmp_path: Path) -> None:
    """Derived, never restated. A second implementation here is the defect with a longer literal.

    Pinned as an equality against the roster rather than against a list of filenames, so a table kind
    that gains a `gene` column joins this pass's scope by existing (`@registry-completeness`).
    """
    spec = _spec(
        tmp_path,
        variants__csv=_VARIANTS,
        haplotypes__csv=_HAPLOTYPES,
        allele_function__csv=_ALLELE_FUNCTION,
    )
    assert module_genes(spec) == authored_identifiers(spec, "gene").ids
    assert sorted(module_genes(spec)) == ["CYP2C19", "MTHFR"]
    # ...and the roster really is wider than the one table this used to read.
    assert len(_id_bearing_tables("gene")) > 1
    assert "haplotypes.csv" in _id_bearing_tables("gene")


def test_a_table_that_will_not_parse_refuses_rather_than_narrowing_the_scope(tmp_path: Path) -> None:
    """A report may route an unreadable table to `not_read`; a *scope* may not.

    Half a gene set is a silently narrowed one — the same defect one table wider — so this pass keeps
    refusing, and in its own phrasing, which `gene_validity` re-raises as its own error type.
    """
    spec = _spec(tmp_path, haplotypes__csv="haplotype_name,rsid\n*2,rs4244285\n")
    with pytest.raises(GeneMetricsEnrichmentError, match="haplotypes.csv is invalid"):
        module_genes(spec)

    broken = _spec(
        tmp_path / "two",
        variants__csv="rsid,genotype,state,conclusion,gene\nrs1,A/G,NOT_A_STATE,c,RYR1\n",
    )
    with pytest.raises(GeneMetricsEnrichmentError, match="variants.csv is invalid"):
        module_genes(broken)
    # The borrowing pass still fails as itself rather than leaking this one's type.
    with pytest.raises(GeneValidityError, match="variants.csv is invalid"):
        validity_genes(broken)


def test_a_table_present_in_two_places_refuses_rather_than_narrowing_the_scope(
    tmp_path: Path,
) -> None:
    """The other way a table is unreadable, and the one the refusal did not cover.

    A `SidecarCollision` — the same table beside the spec *and* under `derived/` — is recorded in
    `not_read` and in nothing else, while the refusal above reads `read_errors`, which holds parse
    failures alone. So a module with two copies of `variants.csv` returned a short gene list with no
    raise and no log line, and the three passes taking their scope from here reported that the module
    names no gene: a clean-looking zero over a question nobody put.

    `unreadable` is the line already drawn for exactly this — every table that exists and could not be
    read — and refusing on it covers both shapes without a second list to keep in step.
    """
    spec = _spec(tmp_path, variants__csv="rsid,genotype,state,conclusion,gene\nrs1,A/G,significant,c,RYR1\n")
    genes = module_genes(spec)
    assert "RYR1" in genes, "the single-copy module is the baseline this compares against"

    derived = spec / "derived"
    derived.mkdir()
    (derived / "variants.csv").write_text((spec / "variants.csv").read_text(), encoding="utf-8")
    with pytest.raises(GeneMetricsEnrichmentError, match="variants.csv could not be read"):
        module_genes(spec)


def test_the_pgx_cross_checks_own_pair_is_not_this_roster() -> None:
    """`pgx._GENE_TABLES` stays two tables, and that is a different question.

    It decides whether the star-allele cross-check *applies* — a fact about that check's inputs — not
    what the module is about. Folding it into the roster would run the cross-check over modules that
    carry no star alleles at all.
    """
    from just_dna_enricher.pgx import _GENE_TABLES

    assert {name for name, _model, _attr in _GENE_TABLES} == {
        "allele_function.csv",
        "haplotypes.csv",
    }
    assert set(_id_bearing_tables("gene")) > {name for name, _m, _a in _GENE_TABLES}
