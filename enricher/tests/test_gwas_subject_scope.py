"""RM158: the GWAS pass asked its Catalog about `variants.csv` rsIDs while five tables carry one.

The third instance of one shape in one sweep, and the one where the answer already existed in this
package. `enrich.Subject` and `collect_subjects` were built for exactly this — resolution read
`variants.csv` alone until RM43, so a PGx module, which by design carries none, enriched to an empty
`resolution.csv` — and the GWAS pass restated the narrow loop instead of calling them. A module whose
rsIDs live in `haplotypes.csv` or `pharm_variants.csv` therefore got no associations and no line
saying none had been asked for.

Offline: subject collection is table-reading and reaches no Catalog.
"""

from pathlib import Path

import pytest
from just_dna_enricher.enrich import collect_subjects
from just_dna_enricher.gwas import GwasError, _module_subjects
from just_dna_enricher.identifiers import _id_bearing_tables

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: rm158\n  title: RM158\n  description: d\n  report_title: RM158\n"
)
_HAPLOTYPES = "haplotype_name,rsid,start,allele,gene\n*2,rs4244285,94781859,A,CYP2C19\n"
_VARIANTS = "rsid,genotype,state,conclusion,gene\nrs1801133,C/T,risk,c,MTHFR\n"


def _spec(tmp_path: Path, **tables: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    for name, body in tables.items():
        (spec / name.replace("__", ".")).write_text(body, encoding="utf-8")
    return spec


def test_an_rsid_that_lives_only_in_a_pgx_table_is_a_subject(tmp_path: Path) -> None:
    """The reported shape: a real rsID the Catalog can answer for, never asked about."""
    spec = _spec(tmp_path, haplotypes__csv=_HAPLOTYPES)
    assert [rsid for rsid, _key in _module_subjects(spec)] == ["rs4244285"]


def test_the_subject_set_is_the_collectors_and_not_a_second_loop(tmp_path: Path) -> None:
    """Derived, never restated — the collector already answers "which rows ask about a variant".

    Pinned as an equality against `collect_subjects` so a table it learns to read joins this pass by
    existing, and `variants.csv`'s precedence is inherited rather than re-implemented.
    """
    spec = _spec(tmp_path, variants__csv=_VARIANTS, haplotypes__csv=_HAPLOTYPES)
    subjects = collect_subjects(spec, [], "GRCh38")
    assert {rsid for rsid, _key in _module_subjects(spec)} >= {s.rsid for s in subjects if s.rsid}
    assert sorted(rsid for rsid, _key in _module_subjects(spec)) == ["rs1801133", "rs4244285"]
    # ...and `rsid` really is carried by more than the one table this used to read.
    assert len(_id_bearing_tables("rsid")) > 1


def test_variants_csv_keeps_its_precedence(tmp_path: Path) -> None:
    """A variant named by two tables keeps the identity the SNP row minted, first occurrence winning.

    Inherited from the collector rather than asserted about this pass in isolation: letting a PGx row
    win would move an already compiled module's identity, which is why that ordering exists.
    """
    both = "haplotype_name,rsid,start,allele,gene\n*2,rs1801133,11856378,A,MTHFR\n"
    spec = _spec(tmp_path, variants__csv=_VARIANTS, haplotypes__csv=both)
    keys = dict(_module_subjects(spec))
    assert keys["rs1801133"] == "rs1801133"          # one subject, not two
    assert len(_module_subjects(spec)) == 1


def test_a_module_with_neither_table_has_no_subjects(tmp_path: Path) -> None:
    """Empty stays empty and stays quiet — the caller reports it, this does not invent one."""
    assert _module_subjects(_spec(tmp_path)) == []


def test_a_broken_variants_csv_still_fails_as_this_pass(tmp_path: Path) -> None:
    """The pass owes its caller its own exception type, through the borrowed collector too."""
    spec = _spec(
        tmp_path,
        variants__csv="rsid,genotype,state,conclusion,gene\nrs1,A/G,NOT_A_STATE,c,RYR1\n",
    )
    with pytest.raises(GwasError, match="variants.csv is invalid"):
        _module_subjects(spec)
