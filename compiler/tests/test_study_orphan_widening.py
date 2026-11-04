"""The study-orphan widening (RM28, PROPOSAL_0_8_PT2 §5 B1 step 4).

A `studies.csv` row names a variant the module carries when that variant is a `variants.csv` row's, a
defining variant in `haplotypes.csv`, a `pharm_variants.csv` row's, or one a `meta.csv` member reaches
(the rows `build_meta` expanded it to, never a second matcher). Before the widening only `variants.csv`
counted, so a module that scores APOE as diplotypes — longevitymap v2's R-APOE-1 — drew
`study_variant_orphan` for every study on rs429358 and rs7412, the SNPs that define the ε alleles.

The lead's 2026-11-04 decision took the widening two steps further: `pharm_variants.csv` is an arm of its
own, whether or not a member reaches a row, and the check no longer waits for a `variants.csv`, so a
diplotype-only or PGx-only module is checked too (`@roster-is-as-wide-as-the-tables-it-reads`).

Every expected key set is computed from the CSV rows the test writes.
"""

import csv
import io
import shutil
from pathlib import Path

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_compiler.compiler.load import load_csv_rows
from just_dna_compiler.compiler.meta import build_meta, load_meta, member_tables, member_variant_rows
from just_dna_format.pgx import PharmVariantRow

_APOE = Path(__file__).resolve().parents[2] / "reference_examples" / "apoe_epsilon"
_CODE = "study_variant_orphan"
_PHRASE = "Studies reference variants not in variants.csv"

# One locus outside APOE, coordinate-authored, so the module has a variants.csv as v2 does: v2 carries
# hundreds of variant rows and scores APOE as diplotypes beside them.
_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "rs3184504,12,111446804,C,T,C/C,protective,Two C alleles.,SH2B3\n"
    "rs3184504,12,111446804,C,T,C/T,protective,One C allele.,SH2B3\n"
)

# Seven papers on each ε-defining SNP: v2's 14 (rsid, pmid) links, plus one study on the variants.csv
# locus that was never an orphan.
_APOE_PMIDS = ("30642433", "31413261", "32282020", "29165669", "25326637", "23099194", "28738191")
_STUDIES = "rsid,pmid\n" + "".join(
    f"{rsid},{pmid}\n" for rsid in ("rs429358", "rs7412") for pmid in _APOE_PMIDS
)
_STUDIES += "rs3184504,30642433\n"

_META_HEADER = "members,direction,conclusion,pmid\n"
# A diplotype-level citation, the RM47 pattern the meta-table's `pmid` was added for.
_META_APOE = '"diplotypes[gene=APOE, haplotype_a=e3, haplotype_b=e4]",risk,One ε4 allele.,30642433\n'


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _apoe_module(directory: Path, *, studies: str = _STUDIES, meta: str | None = None) -> Path:
    """`apoe_epsilon` (haplotypes + diplotypes + resolution) with a variants.csv beside it and studies."""
    directory.mkdir(parents=True)
    for name in ("module_spec.yaml", "haplotypes.csv", "diplotypes.csv", "resolution.csv"):
        shutil.copyfile(_APOE / name, directory / name)
    (directory / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (directory / "studies.csv").write_text(studies, encoding="utf-8")
    if meta is not None:
        (directory / "meta.csv").write_text(meta, encoding="utf-8")
    return directory


def _orphans(warnings: list[str]) -> list[str]:
    return [w for w in warnings if _PHRASE in w]


def _authored_rsids(text: str) -> set[str]:
    return {row["rsid"] for row in _rows(text) if row.get("rsid")}


def test_the_apoe_study_links_were_orphans_before_the_haplotypes_counted(tmp_path: Path) -> None:
    """The baseline the widening removes, computed rather than read off the probe: every studied rsID
    that is not a `variants.csv` row is a key the pre-widening check named. Removing `haplotypes.csv`
    and its diplotypes reproduces it on this branch, so the arm under test is the one that clears it."""
    spec = _apoe_module(tmp_path / "apoe")
    (spec / "haplotypes.csv").unlink()
    (spec / "diplotypes.csv").unlink()
    expected = _authored_rsids(_STUDIES) - _authored_rsids(_VARIANTS)
    assert expected == {"rs429358", "rs7412"}
    links = [row for row in _rows(_STUDIES) if row["rsid"] in expected]
    assert len(links) == 2 * len(_APOE_PMIDS)

    orphans = _orphans(validate_spec(spec).warnings)
    assert len(orphans) == 1, orphans
    assert all(key in orphans[0] for key in expected)
    assert "rs3184504" not in orphans[0]


def test_a_defining_variant_in_haplotypes_csv_is_not_an_orphan(tmp_path: Path) -> None:
    """APOE scored only as diplotypes: the 14 links on rs429358/rs7412 name the ε alleles' defining
    variants, which the module carries in `haplotypes.csv`."""
    spec = _apoe_module(tmp_path / "apoe")
    result = validate_spec(spec, strict=True)
    assert result.valid, result.errors
    assert _orphans(result.warnings) == []


def test_the_apoe_module_with_a_citing_meta_row_compiles_with_no_orphan(tmp_path: Path) -> None:
    """The v2 shape end to end: the studies on the defining SNPs, and a diplotype-level citation on a
    meta row. The compile inherits the pre-flight's finding, so the manifest carries no orphan code."""
    spec = _apoe_module(tmp_path / "apoe", meta=_META_HEADER + _META_APOE)
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert _CODE not in dict(result.manifest.compilation.warnings_summary)
    assert _orphans(result.warnings) == []


def test_a_study_on_a_variant_no_table_carries_still_warns(tmp_path: Path) -> None:
    """The widening covers what the module carries, nothing more: a variant in no table and reached by
    no meta member is still an orphan, and the message names it and only it."""
    stray = "rs1801133"
    studies = _STUDIES + f"{stray},30642433\n"
    spec = _apoe_module(tmp_path / "apoe", studies=studies, meta=_META_HEADER + _META_APOE)
    orphans = _orphans(validate_spec(spec).warnings)
    assert len(orphans) == 1, orphans
    assert stray in orphans[0]
    assert not any(key in orphans[0] for key in ("rs429358", "rs7412", "rs3184504"))
    # The compile reports the same sentence (`@parity-by-check`): it inherits the pre-flight's.
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert _orphans(result.warnings) == orphans


def test_a_diplotype_only_module_is_checked(tmp_path: Path) -> None:
    """A module with no `variants.csv` used to skip the check outright, so a study on a variant in no
    table passed in silence. `apoe_epsilon` as shipped (haplotypes + diplotypes, no variants.csv): the
    studies on the ε-defining SNPs are carried, the stray is the one orphan, and compile agrees."""
    stray = "rs1801133"
    studies = "rsid,pmid\n" + "".join(f"{rsid},30642433\n" for rsid in ("rs429358", "rs7412", stray))
    spec = _apoe_module(tmp_path / "apoe", studies=studies)
    (spec / "variants.csv").unlink()
    defining = _authored_rsids((spec / "haplotypes.csv").read_text(encoding="utf-8"))
    assert _authored_rsids(studies) - defining == {stray}

    orphans = _orphans(validate_spec(spec).warnings)
    assert len(orphans) == 1, orphans
    assert stray in orphans[0]
    assert not any(key in orphans[0] for key in defining)
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert _orphans(result.warnings) == orphans


# ── the pharm_variants arm and the meta arm ──────────────────────────────────────────────────────
#
# A `pharm_variants.csv` row's variant is carried whether or not a meta member reaches it (the lead,
# 2026-11-04). A meta member reaches rows of `variants.csv` and `pharm_variants.csv` only
# (`LOCUS_TABLES`), both arms of their own now, so the meta arm adds nothing today; the tests below pin
# that a member's reach changes no orphan, in either direction.

_PGX_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: orphan_probe\n"
    "  title: Orphan probe\n"
    "  description: studies against variants, pharm_variants and a meta-table selector\n"
    "  report_title: Orphan probe\n"
    "genome_build: GRCh38\n"
)
_PHARM = (
    "rsid,gene,genotype,drug,phenotype_category,annotation_id,evidence_level,conclusion\n"
    "rs9923231,VKORC1,C/C,warfarin,dosage,1447673005,1B,Normal warfarin dose.\n"
    "rs9923231,VKORC1,C/T,warfarin,dosage,1447673005,1B,Lower warfarin dose.\n"
    "rs1057910,CYP2C9,A/C,warfarin,dosage,1447673006,1A,Lower warfarin dose.\n"
)
_PGX_STUDIES = "rsid,pmid\nrs3184504,30642433\nrs9923231,31413261\nrs1057910,32282020\n"


def _pgx_module(directory: Path, meta: str | None, studies: str = _PGX_STUDIES) -> Path:
    directory.mkdir(parents=True)
    (directory / "module_spec.yaml").write_text(_PGX_YAML, encoding="utf-8")
    (directory / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (directory / "pharm_variants.csv").write_text(_PHARM, encoding="utf-8")
    (directory / "studies.csv").write_text(studies, encoding="utf-8")
    if meta is not None:
        (directory / "meta.csv").write_text(meta, encoding="utf-8")
    return directory


def test_a_pharm_variant_with_no_meta_member_is_not_an_orphan(tmp_path: Path) -> None:
    """A study on a `pharm_variants.csv` row's variant is carried with no `meta.csv` at all."""
    spec = _pgx_module(tmp_path / "m", meta=None)
    carried_by_pharm = _authored_rsids(_PGX_STUDIES) - _authored_rsids(_VARIANTS)
    assert carried_by_pharm == {"rs9923231", "rs1057910"} <= _authored_rsids(_PHARM)
    assert _orphans(validate_spec(spec).warnings) == []
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert _CODE not in dict(result.manifest.compilation.warnings_summary)


def test_a_pgx_only_module_is_checked(tmp_path: Path) -> None:
    """No `variants.csv`: the pharm variants are carried, a study on a variant in no table is the one
    orphan. Before the gate came off this module drew no orphan check at all."""
    stray = "rs1801133"
    spec = _pgx_module(tmp_path / "m", meta=None, studies=_PGX_STUDIES + f"{stray},32282020\n")
    (spec / "variants.csv").unlink()
    expected = _authored_rsids(_PGX_STUDIES) - _authored_rsids(_PHARM)
    assert expected == {"rs3184504"}  # the variants.csv locus, gone with its table
    orphans = _orphans(validate_spec(spec).warnings)
    assert len(orphans) == 1, orphans
    assert all(key in orphans[0] for key in expected | {stray})
    assert not any(key in orphans[0] for key in _authored_rsids(_PHARM))


_STRAY_STUDY = "rs1801133,30642433\n"


def test_a_selector_member_changes_no_orphan(tmp_path: Path) -> None:
    """`pharm_variants[gene=VKORC1]` reaches only rows the pharm arm already carries: the orphans with
    the member are exactly the orphans without it, and the stray study is still one."""
    meta = "members,conclusion\npharm_variants[gene=VKORC1],VKORC1 lowers the warfarin dose.\n"
    studies = _PGX_STUDIES + _STRAY_STUDY
    with_member = _orphans(validate_spec(_pgx_module(tmp_path / "m", meta=meta, studies=studies)).warnings)
    without = _orphans(validate_spec(_pgx_module(tmp_path / "base", meta=None, studies=studies)).warnings)
    assert len(without) == 1 and "rs1801133" in without[0]
    assert with_member == without


def _reach(spec: Path) -> set[str]:
    """The rsIDs of the rows the meta arm hands the check: `member_variant_rows` over `build_meta`'s
    expansion of this module's `meta.csv`, the call `validate_spec` makes."""
    pharm, errors, _ = load_csv_rows(spec / "pharm_variants.csv", PharmVariantRow, "pharm_variants.csv")
    assert errors == []
    rows, errors, _ = load_meta(spec)
    assert errors == []
    tables = member_tables([], {"pharm_variants.csv": pharm})
    return {row.rsid for row in member_variant_rows(build_meta(rows, tables, None), tables)}


def test_the_meta_arm_reaches_exactly_the_rows_its_members_matched(tmp_path: Path) -> None:
    """The meta arm adds nothing the table arms miss today, so its reach is pinned where it is computed:
    a selector reaches the rows it matched, the locus form the loci it names, a member matching
    nothing reaches nothing."""
    selector = "members,conclusion\npharm_variants[gene=VKORC1],VKORC1.\n"
    locus = "members,conclusion\npharm_variants[variant_key=rs1057910],CYP2C9.\n"
    nothing = "members,conclusion\npharm_variants[gene=CYP4F2],No such rows here.\n"
    by_gene = {
        gene: {row["rsid"] for row in _rows(_PHARM) if row["gene"] == gene} for gene in ("VKORC1", "CYP2C9")
    }
    assert _reach(_pgx_module(tmp_path / "selector", meta=selector)) == by_gene["VKORC1"]
    assert _reach(_pgx_module(tmp_path / "locus", meta=locus)) == {"rs1057910"} == by_gene["CYP2C9"]
    assert _reach(_pgx_module(tmp_path / "nothing", meta=nothing)) == set()


def test_a_member_matching_nothing_covers_nothing(tmp_path: Path) -> None:
    """A selector that matches no row reaches no variant: the orphans are exactly the no-meta ones."""
    meta = "members,conclusion\npharm_variants[gene=CYP4F2],No such rows here.\n"
    studies = _PGX_STUDIES + _STRAY_STUDY
    warnings = validate_spec(_pgx_module(tmp_path / "m", meta=meta, studies=studies)).warnings
    assert any("matches no row of pharm_variants.csv" in w for w in warnings)
    baseline = _orphans(validate_spec(_pgx_module(tmp_path / "base", meta=None, studies=studies)).warnings)
    assert len(baseline) == 1
    assert _orphans(warnings) == baseline


def test_duplicate_citations_are_checked_on_a_module_with_no_variants_csv(tmp_path: Path) -> None:
    """`duplicate_study_citation` is computed in the same pass, so it came off the gate with the orphan
    half: one (variant, pmid) written twice on a PGx-only module warns."""
    studies = _PGX_STUDIES + "rs9923231,31413261\n"
    spec = _pgx_module(tmp_path / "m", meta=None, studies=studies)
    (spec / "variants.csv").unlink()
    duplicates = [w for w in validate_spec(spec).warnings if "Duplicate (variant, pmid)" in w]
    assert len(duplicates) == 1 and "rs9923231" in duplicates[0] and "31413261" in duplicates[0]


def test_an_arm_that_loaded_no_rows_withholds_the_orphan_half(tmp_path: Path) -> None:
    """A `variants.csv` whose every row fails its model carries variants nobody could read: what the
    module carries is unknown, so the orphan half withholds rather than name every study. The load
    errors are the report; the gate used to withhold this by accident."""
    spec = _apoe_module(tmp_path / "apoe")
    for name in ("haplotypes.csv", "diplotypes.csv"):
        (spec / name).unlink()
    broken = _VARIANTS.replace(",protective,", ",not_a_state,")
    (spec / "variants.csv").write_text(broken, encoding="utf-8")
    result = validate_spec(spec)
    assert result.errors, "every variants.csv row should fail its model"
    assert _orphans(result.warnings) == []
    # One readable row is enough to know the arm: the check runs, and names the studies it misses.
    (spec / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    assert len(_orphans(validate_spec(spec).warnings)) == 1
