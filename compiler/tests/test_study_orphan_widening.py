"""The study-orphan widening (RM28, PROPOSAL_0_8_PT2 §5 B1 step 4).

A `studies.csv` row names a variant the module carries when that variant is a `variants.csv` row's, a
defining variant in `haplotypes.csv`, or one a `meta.csv` member reaches (the rows `build_meta`
expanded it to, never a second matcher). Before the widening only `variants.csv` counted, so a module
that scores APOE as diplotypes — longevitymap v2's R-APOE-1 — drew `study_variant_orphan` for every
study on rs429358 and rs7412, the SNPs that define the ε alleles.

Every expected key set is computed from the CSV rows the test writes.
"""

import csv
import io
import shutil
from pathlib import Path

from just_dna_compiler.compiler import compile_module, validate_spec

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


# ── the meta arm ─────────────────────────────────────────────────────────────────────────────────
#
# A `variants.csv` row a meta member matches is already covered by the first arm, and a diplotype or
# `allele_function` member reaches its variants through `haplotypes.csv`, the second. What only the
# meta arm covers is a `pharm_variants.csv` row a member reaches: that table is a member table and
# carries a `variant_key`, but is not itself an arm.

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


def _pgx_module(directory: Path, meta: str | None) -> Path:
    directory.mkdir(parents=True)
    (directory / "module_spec.yaml").write_text(_PGX_YAML, encoding="utf-8")
    (directory / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (directory / "pharm_variants.csv").write_text(_PHARM, encoding="utf-8")
    (directory / "studies.csv").write_text(_PGX_STUDIES, encoding="utf-8")
    if meta is not None:
        (directory / "meta.csv").write_text(meta, encoding="utf-8")
    return directory


def test_a_pharm_variant_with_no_meta_member_is_still_an_orphan(tmp_path: Path) -> None:
    """The contract's arms are `variants.csv`, `haplotypes.csv` and the meta-table: a
    `pharm_variants.csv` row no member reaches is outside all three, as before."""
    orphans = _orphans(validate_spec(_pgx_module(tmp_path / "m", meta=None)).warnings)
    expected = _authored_rsids(_PGX_STUDIES) - _authored_rsids(_VARIANTS)
    assert expected == {"rs9923231", "rs1057910"}
    assert len(orphans) == 1
    assert all(key in orphans[0] for key in expected)


def test_a_selector_member_covers_the_variants_of_the_rows_it_matched(tmp_path: Path) -> None:
    """`pharm_variants[gene=VKORC1]` is a selector, expanded by `build_meta`: the variants of the rows
    it matched stop being orphans, and a pharm variant it did not match stays one."""
    meta = "members,conclusion\npharm_variants[gene=VKORC1],VKORC1 lowers the warfarin dose.\n"
    spec = _pgx_module(tmp_path / "m", meta=meta)
    matched = {row["rsid"] for row in _rows(_PHARM) if row["gene"] == "VKORC1"}
    unmatched = {row["rsid"] for row in _rows(_PHARM)} - matched
    assert matched == {"rs9923231"} and unmatched == {"rs1057910"}

    orphans = _orphans(validate_spec(spec).warnings)
    assert len(orphans) == 1, orphans
    assert all(key in orphans[0] for key in unmatched)
    assert not any(key in orphans[0] for key in matched)
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert _orphans(result.warnings) == orphans


def test_a_locus_member_covers_its_pharm_variant(tmp_path: Path) -> None:
    """`pharm_variants[variant_key=…]` is the locus form, looked up by key rather than scanned; it
    covers that locus the same way."""
    meta = (
        "members,conclusion\n"
        "pharm_variants[variant_key=rs9923231],VKORC1.\n"
        "pharm_variants[variant_key=rs1057910],CYP2C9.\n"
    )
    assert _orphans(validate_spec(_pgx_module(tmp_path / "m", meta=meta)).warnings) == []


def test_a_member_matching_nothing_covers_nothing(tmp_path: Path) -> None:
    """A selector that matches no row reaches no variant: the orphans are exactly the no-meta ones."""
    meta = "members,conclusion\npharm_variants[gene=CYP4F2],No such rows here.\n"
    spec = _pgx_module(tmp_path / "m", meta=meta)
    warnings = validate_spec(spec).warnings
    assert any("matches no row of pharm_variants.csv" in w for w in warnings)
    baseline = _orphans(validate_spec(_pgx_module(tmp_path / "base", meta=None)).warnings)
    assert _orphans(warnings) == baseline
