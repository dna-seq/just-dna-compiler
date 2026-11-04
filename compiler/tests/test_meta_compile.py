"""`meta.csv` through the real compile and reverse paths (0.8: RM28, RM323, RM324, RM327's rows, RM330's `sex`).

The compiler expands every member into the rows it matches, so a consumer evaluates no rule (P1), and
writes two parquets: `meta.parquet`, one row per authored row with its selector verbatim and what it
matched, and `meta_resolved.parquet`, one row per single-statement row a one-member meta row reaches,
with each fact column after precedence and the columns two incomparable, disagreeing matches withheld
(`proposals/PROPOSAL_0_8_PT2.md` §3 item 8).

Every expected value below is read off the fixture the test writes, never off a data dump: which rows
a selector should match is computed from the CSV rows themselves.
"""

import csv
import io
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module, validate_spec

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: meta_probe\n"
    "  title: Meta probe\n"
    "  description: the meta-table over APOE, KL-VS, LPA and a CPIC gene pair\n"
    "  report_title: Meta probe\n"
    "genome_build: GRCh38\n"
)
_TIER_SCALE = "tier_scale: longevitymap_v2\n"

# Coordinate-authored, so every row has a position with no resolution table injected.
_VARIANTS = """rsid,chrom,start,ref,alts,genotype,state,conclusion,gene,flags,effect_allele
rs10455872,6,160589086,A,G,A/A,neutral,No LPA risk allele.,LPA,legacy_longevitymap,G
rs10455872,6,160589086,A,G,A/G,risk,One LPA risk allele.,LPA,legacy_longevitymap,G
rs10455872,6,160589086,A,G,G/G,risk,Two LPA risk alleles.,LPA,legacy_longevitymap,G
rs9536314,13,33054000,T,G,T/T,neutral,No KL-VS allele.,KL,legacy_longevitymap,G
rs9536314,13,33054000,T,G,G/T,protective,One KL-VS allele.,KL,legacy_longevitymap,G
rs3184504,12,111446804,C,T,C/C,protective,Two C alleles.,SH2B3,,C
rs3184504,12,111446804,C,T,C/T,protective,One C allele.,SH2B3,,T
"""

_STUDIES = "rsid,pmid\nrs10455872,30642433\nrs9536314,32282020\nrs3184504,31413261\n"

_DIPLOTYPES = """gene,haplotype_a,haplotype_b,trait_efo_id,direction,phenotype,conclusion
APOE,ε2,ε4,MONDO:0004975,risk,APOE ε2/ε4,Opposing alleles.
APOE,ε3,ε4,MONDO:0004975,risk,APOE ε3/ε4,One ε4.
APOE,ε4,ε4,MONDO:0004975,risk,APOE ε4/ε4,Two ε4.
APOE,ε3,ε3,MONDO:0004975,neutral,APOE ε3/ε3,Reference.
KL,KL-VS,ref,MONDO:0004975,protective,KL-VS heterozygote,One KL-VS haplotype.
TPMT,*3A,*3A,,,Poor Metabolizer,TPMT poor metabolizer.
TPMT,*1,*1,,,Normal Metabolizer,TPMT normal metabolizer.
NUDT15,*3,*3,,,Poor Metabolizer,NUDT15 poor metabolizer.
NUDT15,*1,*1,,,Normal Metabolizer,NUDT15 normal metabolizer.
"""

_ALLELE_FUNCTION = "gene,allele\nAPOE,ε2\nAPOE,ε4\n"

_META_HEADER = (
    "members,trait_efo_id,trait_role,direction,conclusion,negatives,tier,age_of_action,"
    "age_of_action_confidence,flags,pmid,doi,sex\n"
)
_LEGACY = "variants[flags=legacy_longevitymap],,,,,,D,,,,,,\n"
_LPA_LOCUS = "variants[variant_key=rs10455872],,,,,,A,MIDLIFE,,,,,\n"
_E4 = '"allele_function[gene=APOE, allele=ε4]",,,,,,A,LATE,DIRECT,ap:weak,30642433,,\n'
_E2 = '"allele_function[gene=APOE, allele=ε2]",,,,,,A,LATE,DIRECT_WEAK,protect:presence,31413261,,\n'
_KLVS_E4 = (
    '"diplotypes[gene=KL, haplotype_a=KL-VS, haplotype_b=ref] & diplotypes[gene=APOE, haplotype_b=ε4]",'
    'MONDO:0004975,,protective,"ε4 with one KL-VS copy: buffered.",,C,,,,32282020,,\n'
)
_TPMT_NUDT15 = (
    '"diplotypes[gene=TPMT, phenotype=Poor Metabolizer] & diplotypes[gene=NUDT15, phenotype=Poor Metabolizer]",'
    ',,,"Poor metabolizer of both: reduce the thiopurine dose sharply.",,,,,,,,\n'
)
_META = _META_HEADER + _LEGACY + _LPA_LOCUS + _E4 + _E2 + _KLVS_E4 + _TPMT_NUDT15


def _module(
    directory: Path, meta: str = _META, *, tier_scale: bool = True, variants: str = _VARIANTS
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_YAML + (_TIER_SCALE if tier_scale else ""), encoding="utf-8")
    (directory / "variants.csv").write_text(variants, encoding="utf-8")
    (directory / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    (directory / "diplotypes.csv").write_text(_DIPLOTYPES, encoding="utf-8")
    (directory / "allele_function.csv").write_text(_ALLELE_FUNCTION, encoding="utf-8")
    (directory / "meta.csv").write_text(meta, encoding="utf-8")
    return directory


def _compile(spec: Path, out: Path, **kwargs):
    result = compile_module(spec, out, **kwargs)
    assert result.success, result.errors
    return result


def _csv_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def _resolved(out: Path) -> pl.DataFrame:
    return pl.read_parquet(out / "meta_resolved.parquet")


def _resolved_row(out: Path, table: str, key: list[str | None], sex: str | None = None) -> dict:
    df = _resolved(out)
    rows = [
        r for r in df.iter_rows(named=True) if r["table"] == table and r["key"] == key and r["sex"] == sex
    ]
    assert len(rows) == 1, (table, key, sex, df)
    return rows[0]


def _codes(result) -> dict[str, int]:
    return dict(result.manifest.compilation.warnings_summary)


# ── the key ──────────────────────────────────────────────────────────────────────────────────────


def test_a_and_b_against_b_and_a_is_a_duplicate_key(tmp_path: Path) -> None:
    meta = (
        _META_HEADER
        + '"variants[variant_key=rs9536314] & variants[variant_key=rs10455872]",,,,Both.,,,,,,,,\n'
        + '"variants[variant_key=rs10455872] & variants[variant_key=rs9536314]",,,,Both again.,,,,,,,,\n'
    )
    result = validate_spec(_module(tmp_path / "spec", meta))
    assert not result.valid
    assert any("meta.csv: duplicate row for key" in e for e in result.errors), result.errors
    assert not compile_module(tmp_path / "spec", tmp_path / "out").success


def test_the_same_members_for_two_sexes_are_two_rows_not_a_duplicate(tmp_path: Path) -> None:
    meta = _META_HEADER + _E4 + _E4.replace(",,\n", ",,male\n").replace(",A,LATE", ",B,LATE")
    assert validate_spec(_module(tmp_path / "spec", meta)).valid


# ── precedence ───────────────────────────────────────────────────────────────────────────────────


def test_a_locus_row_outranks_the_legacy_tag_selector(tmp_path: Path) -> None:
    """`variants[flags=legacy_longevitymap]` tier D against `variants[variant_key=rs10455872]` tier A."""
    _compile(_module(tmp_path / "spec"), tmp_path / "out")
    variants = _csv_rows(tmp_path / "spec" / "variants.csv")
    legacy = [r for r in variants if "legacy_longevitymap" in r["flags"]]
    assert legacy, "the fixture must carry legacy rows"
    for row in legacy:
        resolved = _resolved_row(tmp_path / "out", "variants", [row["rsid"], row["genotype"]])
        expected = "A" if row["rsid"] == "rs10455872" else "D"
        assert resolved["tier"] == expected, row
        assert resolved["withheld"] == []
    # The locus row stated `age_of_action`; the tag selector stated none, so nothing was withheld.
    assert _resolved_row(tmp_path / "out", "variants", ["rs10455872", "A/G"])["age_of_action"] == "MIDLIFE"
    assert _resolved_row(tmp_path / "out", "variants", ["rs9536314", "G/T"])["age_of_action"] is None


def test_two_one_condition_selectors_that_disagree_withhold_the_column(tmp_path: Path) -> None:
    """ADARB1's edge in the audit: `gene=…` and `flags=…` are both one condition, so neither wins."""
    meta = _META_HEADER + _LEGACY + "variants[gene=KL],,,,,,C,,,,,,\n"
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    row = _resolved_row(tmp_path / "out", "variants", ["rs9536314", "G/T"])
    assert row["tier"] is None
    assert row["withheld"] == ["tier"]
    # The more specific two-condition row settles it.
    meta += '"variants[gene=KL, flags=legacy_longevitymap]",,,,,,B,,,,,,\n'
    _compile(_module(tmp_path / "spec2", meta), tmp_path / "out2")
    row = _resolved_row(tmp_path / "out2", "variants", ["rs9536314", "G/T"])
    assert (row["tier"], row["withheld"]) == ("B", [])


def test_e2_e4_allele_rows_disagree_and_withhold_until_a_diplotype_row_settles_it(tmp_path: Path) -> None:
    _compile(_module(tmp_path / "spec"), tmp_path / "out")
    key = ["APOE", "ε2", "ε4", "MONDO:0004975", None, None]
    row = _resolved_row(tmp_path / "out", "diplotypes", key)
    # tier (A, A) and age_of_action (LATE, LATE) agree; the confidence (DIRECT, DIRECT_WEAK) does not.
    assert (row["tier"], row["age_of_action"]) == ("A", "LATE")
    assert row["age_of_action_confidence"] is None
    assert row["withheld"] == ["age_of_action_confidence", "flags"]
    # An ε4-only diplotype is reached by one allele row and inherits its facts.
    e4e4 = _resolved_row(tmp_path / "out", "diplotypes", ["APOE", "ε4", "ε4", "MONDO:0004975", None, None])
    assert (e4e4["age_of_action_confidence"], e4e4["flags"], e4e4["withheld"]) == ("DIRECT", ["ap:weak"], [])

    settle = '"diplotypes[gene=APOE, haplotype_a=ε2, haplotype_b=ε4]",,,,,,,,INFERRED,opposing,,,\n'
    _compile(_module(tmp_path / "spec2", _META + settle), tmp_path / "out2")
    row = _resolved_row(tmp_path / "out2", "diplotypes", key)
    assert (row["age_of_action_confidence"], row["flags"], row["withheld"]) == ("INFERRED", ["opposing"], [])
    assert (row["tier"], row["age_of_action"]) == (
        "A",
        "LATE",
    )  # unstated on the diplotype row: not different


def test_a_sex_scoped_row_outranks_the_same_key_for_that_sex_only(tmp_path: Path) -> None:
    meta = _META_HEADER + _E4 + _E4.replace(",,\n", ",,male\n").replace(",A,LATE", ",B,LATE")
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    assert _resolved_row(tmp_path / "out", "allele_function", ["APOE", "ε4"])["tier"] == "A"
    assert _resolved_row(tmp_path / "out", "allele_function", ["APOE", "ε4"], "male")["tier"] == "B"
    assert not [r for r in _resolved(tmp_path / "out").iter_rows(named=True) if r["sex"] == "female"]


# ── combinations ─────────────────────────────────────────────────────────────────────────────────


def _meta_row(out: Path, members: str) -> dict:
    rows = [r for r in pl.read_parquet(out / "meta.parquet").iter_rows(named=True) if r["members"] == members]
    assert len(rows) == 1
    return rows[0]


def test_a_combination_lists_the_rows_it_replaces(tmp_path: Path) -> None:
    """KL-VS × ε4: one row, an existential selector, replacing what it names."""
    _compile(_module(tmp_path / "spec"), tmp_path / "out")
    members = next(csv.reader(io.StringIO(_KLVS_E4)))[0]
    row = _meta_row(tmp_path / "out", members)
    diplotypes = _csv_rows(tmp_path / "spec" / "diplotypes.csv")
    expected = [
        {
            "member": 0,
            "table": "diplotypes",
            "key": [d["gene"], d["haplotype_a"], d["haplotype_b"], d["trait_efo_id"] or None, None, None],
        }
        for d in diplotypes
        if d["gene"] == "KL" and d["haplotype_a"] == "KL-VS" and d["haplotype_b"] == "ref"
    ] + [
        {
            "member": 1,
            "table": "diplotypes",
            "key": [d["gene"], d["haplotype_a"], d["haplotype_b"], d["trait_efo_id"] or None, None, None],
        }
        for d in diplotypes
        if d["gene"] == "APOE" and d["haplotype_b"] == "ε4"
    ]
    assert row["matches"] == expected
    assert row["match_count"] == len(expected) == 4
    assert row["replaces"] is True
    # A combination's facts are about the combination: they never reach a member row on its own.
    kl = _resolved(tmp_path / "out").filter(pl.col("table") == "diplotypes")
    assert not [r for r in kl.iter_rows(named=True) if r["key"][0] == "KL"]


def test_cpic_tpmt_by_nudt15_is_one_phenotype_pair_row(tmp_path: Path) -> None:
    _compile(_module(tmp_path / "spec"), tmp_path / "out")
    members = next(csv.reader(io.StringIO(_TPMT_NUDT15)))[0]
    row = _meta_row(tmp_path / "out", members)
    diplotypes = _csv_rows(tmp_path / "spec" / "diplotypes.csv")
    poor = [d for d in diplotypes if d["phenotype"] == "Poor Metabolizer"]
    assert [m["key"][:3] for m in row["matches"]] == [
        [d["gene"], d["haplotype_a"], d["haplotype_b"]] for d in poor
    ]
    assert [m["member"] for m in row["matches"]] == [0, 1]
    assert row["replaces"] is True


def test_a_facts_only_one_member_row_replaces_nothing(tmp_path: Path) -> None:
    _compile(_module(tmp_path / "spec"), tmp_path / "out")
    assert _meta_row(tmp_path / "out", "variants[flags=legacy_longevitymap]")["replaces"] is False


# ── warnings ─────────────────────────────────────────────────────────────────────────────────────


def test_a_selector_matching_nothing_warns_and_the_manifest_records_every_count(tmp_path: Path) -> None:
    meta = _META + "variants[variant_key=rs99999999],,,,,,B,,,,,,\n"
    result = _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    assert _codes(result).get("meta_selector_matches_nothing") == 1
    assert any("matches no row of variants.csv" in w for w in result.warnings)
    counts = {(s.row, s.selector): s.matches for s in result.manifest.meta_selectors}
    assert counts[(6, "variants[variant_key=rs99999999]")] == 0
    variants = _csv_rows(tmp_path / "spec" / "variants.csv")
    assert counts[(0, "variants[flags=legacy_longevitymap]")] == sum(
        "legacy_longevitymap" in r["flags"] for r in variants
    )
    assert counts[(4, "diplotypes[gene=APOE, haplotype_b=ε4]")] == 3
    # The validate pre-flight says the same sentence, once.
    assert _codes(result)["meta_selector_matches_nothing"] == 1
    assert sum("matches no row of variants.csv" in w for w in validate_spec(tmp_path / "spec").warnings) == 1


def test_a_locus_whose_rows_disagree_on_effect_allele_withholds_the_direction(tmp_path: Path) -> None:
    ambiguous = "variants[variant_key=rs3184504],EFO_0004305,,protective,,,,,,,,,\n"
    uniform = "variants[variant_key=rs10455872],EFO_0001645,mediator,risk,,,,,,,,,\n"
    result = _compile(_module(tmp_path / "spec", _META_HEADER + ambiguous + uniform), tmp_path / "out")
    assert _codes(result).get("meta_member_allele_ambiguous") == 1
    assert any("do not share one effect_allele" in w for w in result.warnings)
    meta = pl.read_parquet(tmp_path / "out" / "meta.parquet").to_dicts()
    assert meta[0]["direction"] == "protective"  # the authored cell survives for reverse
    assert meta[0]["withheld"] == ["direction"]
    assert meta[1]["withheld"] == []
    # A one-member row stating a finding is a statement beside the row it names, never a replacement.
    assert [row["replaces"] for row in meta] == [False, False]


# ── refusals that need the module ────────────────────────────────────────────────────────────────


def test_a_tier_with_no_tier_scale_is_refused(tmp_path: Path) -> None:
    result = validate_spec(_module(tmp_path / "spec", tier_scale=False))
    assert not result.valid
    assert any("names no `tier_scale`" in e for e in result.errors), result.errors
    assert not compile_module(tmp_path / "spec", tmp_path / "out").success
    # Without a tier, the same module needs no scale.
    no_tier = _META_HEADER + _TPMT_NUDT15
    assert validate_spec(_module(tmp_path / "spec2", no_tier, tier_scale=False)).valid


def test_meta_alone_is_not_a_module(tmp_path: Path) -> None:
    """A module of only meta rows has nothing to select, so meta.csv does not satisfy composition."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML + _TIER_SCALE, encoding="utf-8")
    (spec / "meta.csv").write_text(_META_HEADER + _LEGACY, encoding="utf-8")
    result = validate_spec(spec)
    assert any("module has no recognized table" in e for e in result.errors), result.errors


def test_a_present_but_empty_meta_csv_is_refused(tmp_path: Path) -> None:
    result = validate_spec(_module(tmp_path / "spec", _META_HEADER))
    assert any("meta.csv is present but has no rows" in e for e in result.errors), result.errors


# ── the round trip and determinism ───────────────────────────────────────────────────────────────


def test_compile_reverse_compile_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _module(tmp_path / "spec")
    first = _compile(spec, tmp_path / "out1")
    reverse_module(tmp_path / "out1", tmp_path / "reversed")
    assert _csv_rows(tmp_path / "reversed" / "meta.csv") == _csv_rows(spec / "meta.csv")
    second = _compile(tmp_path / "reversed", tmp_path / "out2")
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert content_signature(tmp_path / "reversed") == content_signature(spec)
    assert second.manifest.tier_scale == first.manifest.tier_scale == "longevitymap_v2"


def test_meta_rows_are_inside_content_signature(tmp_path: Path) -> None:
    base = content_signature(_module(tmp_path / "a"))
    edited = content_signature(_module(tmp_path / "b", _META.replace(",D,", ",C,")))
    assert base != edited


def test_two_compiles_are_byte_identical(tmp_path: Path) -> None:
    spec = _module(tmp_path / "spec")
    first = _compile(spec, tmp_path / "out1")
    second = _compile(spec, tmp_path / "out2")
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    for name in ("meta.parquet", "meta_resolved.parquet"):
        assert (tmp_path / "out1" / name).read_bytes() == (tmp_path / "out2" / name).read_bytes()


def test_meta_resolved_is_ordered_by_table_then_authored_row_then_sex(tmp_path: Path) -> None:
    meta = _META + _E4.replace(",,\n", ",,male\n").replace(",A,LATE", ",B,LATE")
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    df = _resolved(tmp_path / "out")
    tables = ["variants", "diplotypes", "pharm_variants", "allele_function"]
    order = [(tables.index(r["table"]), r["sex"] or "") for r in df.iter_rows(named=True)]
    assert [t for t, _s in order] == sorted(t for t, _s in order)
    variants = [tuple(r["key"]) for r in df.iter_rows(named=True) if r["table"] == "variants"]
    authored = [(r["rsid"], r["genotype"]) for r in _csv_rows(tmp_path / "spec" / "variants.csv")]
    assert variants == [k for k in authored if k in set(variants)]


@pytest.mark.parametrize("name", ["meta.parquet", "meta_resolved.parquet"])
def test_both_parquets_are_in_the_artifact_listing(tmp_path: Path, name: str) -> None:
    _compile(_module(tmp_path / "spec"), tmp_path / "out")
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert name in {f["name"] for f in manifest["artifact"]["files"]}
