"""`meta.csv` through the real compile and reverse paths (0.8: RM28, RM323, RM324, RM327, RM330's `sex`).

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


# A PMID no table but meta.csv cites; `studies.csv` names three others.
_META_ONLY_PMID = "19117549"
_SH2B3_CITED = f"variants[variant_key=rs3184504],,,,,,B,,,,{_META_ONLY_PMID},,\n"


def test_a_literature_row_cited_only_by_meta_is_never_called_uncited_beside_a_duplicate(
    tmp_path: Path,
) -> None:
    """RM357: a refused `meta.csv` keeps its rows for the other checks, so its error is its own.

    On a clean compile the literature row is kept, since the meta row cites it. With the same row
    written twice, the one finding is the duplicate in `meta.csv`; before RM357 the loader dropped
    every row on that error and the literature check then sent the author to `literature.csv`.
    """
    spec = _module(tmp_path / "spec", _META + _SH2B3_CITED)
    (spec / "literature.csv").write_text(f"pmid\n{_META_ONLY_PMID}\n", encoding="utf-8")
    _compile(spec, tmp_path / "out")
    assert pl.read_parquet(tmp_path / "out" / "literature.parquet")["pmid"].to_list() == [_META_ONLY_PMID]

    (spec / "meta.csv").write_text(
        _META + _SH2B3_CITED + _SH2B3_CITED.replace(",B,", ",C,"), encoding="utf-8"
    )
    result = validate_spec(spec)
    assert any("meta.csv: duplicate row for key" in e for e in result.errors), result.errors
    assert not [w for w in result.warnings if "no study, bin or pharm row" in w], result.warnings


def test_a_row_that_will_not_parse_keeps_the_rows_that_did_for_the_citing_view(tmp_path: Path) -> None:
    """RM357, the parse arm: one malformed row is that row's error, never every other row's citation.

    The rows that parsed stay in the citing view because `meta.csv` cites. The malformed row's own
    citation, if it had one, could still read as uncited: its `pmid` was never read.
    """
    # Another locus, so no duplicate key; `sex`, the last column, is a closed vocabulary.
    malformed = "variants[variant_key=rs9536314],,,,,,B,,,,,,nobody\n"
    spec = _module(tmp_path / "spec", _META + _SH2B3_CITED + malformed)
    (spec / "literature.csv").write_text(f"pmid\n{_META_ONLY_PMID}\n", encoding="utf-8")
    result = validate_spec(spec)
    assert any(e.startswith("meta.csv line") and "sex" in e for e in result.errors), result.errors
    assert not [w for w in result.warnings if "no study, bin or pharm row" in w], result.warnings


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


def test_a_member_over_a_resolution_filled_column_matches_on_both_sides(tmp_path: Path) -> None:
    """Parity: the pre-flight expands over the positional tables AFTER the fill, so the compile must too.

    An rsID-authored pharm row has no `chrom` until `resolution.csv` fills it; a member selecting on that
    column matched in `validate` and not in `compile` while the compile expanded before the fill.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML + _TIER_SCALE, encoding="utf-8")
    (spec / "pharm_variants.csv").write_text(
        "rsid,drug,genotype,conclusion\nrs9923231,warfarin,C/T,Reduced dose.\n", encoding="utf-8"
    )
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        "rs9923231,rs9923231,16,31096368,C,T,GRCh38,0,authored,resolved\n",
        encoding="utf-8",
    )
    (spec / "meta.csv").write_text(_META_HEADER + "pharm_variants[chrom=16],,,,,,A,,,,,,\n", encoding="utf-8")
    assert not any("matches no row" in w for w in validate_spec(spec).warnings)
    result = _compile(spec, tmp_path / "out")
    assert "meta_selector_matches_nothing" not in _codes(result)
    assert [s.matches for s in result.manifest.meta_selectors] == [1]


def test_a_diplotype_member_written_in_the_other_order_matches_the_stored_pair(tmp_path: Path) -> None:
    """The model stores `haplotype_a <= haplotype_b`; a member naming both halves is compared that way."""
    meta = _META_HEADER + '"diplotypes[gene=APOE, haplotype_a=ε4, haplotype_b=ε2]",,,,,,,,INFERRED,,,,\n'
    result = _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    assert "meta_selector_matches_nothing" not in _codes(result)
    row = _resolved_row(tmp_path / "out", "diplotypes", ["APOE", "ε2", "ε4", "MONDO:0004975", None, None])
    assert row["age_of_action_confidence"] == "INFERRED"
    # The authored cell is kept verbatim for reverse.
    assert pl.read_parquet(tmp_path / "out" / "meta.parquet")["members"].to_list() == [
        "diplotypes[gene=APOE, haplotype_a=ε4, haplotype_b=ε2]"
    ]


def test_two_traits_tiers_are_two_statements_not_a_conflict(tmp_path: Path) -> None:
    """A per-trait row's facts are about its trait; only trait-less rows set a row's per-locus facts."""
    meta = (
        _META_HEADER
        + "variants[variant_key=rs10455872],EFO_0001645,,,,,A,,,,,,\n"
        + "variants[variant_key=rs10455872],EFO_0004611,,,,,B,,,,,,\n"
    )
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    row = _resolved_row(tmp_path / "out", "variants", ["rs10455872", "A/G"])
    assert (row["tier"], row["withheld"], row["meta_rows"]) == (None, [], [0, 1])
    _compile(_module(tmp_path / "spec2", meta + _LPA_LOCUS), tmp_path / "out2")
    row = _resolved_row(tmp_path / "out2", "variants", ["rs10455872", "A/G"])
    assert (row["tier"], row["withheld"]) == ("A", [])


# ── tradeoff (RM327): computed per allele-bearing member, on meta_resolved.parquet ───────────────
#
# A per-trait judgement is a one-member row with `trait_efo_id` and `direction`. `tradeoff` is computed
# **per allele-bearing member** (PROPOSAL_0_8_PT2 §3 item 9: "true when an allele-bearing member has both
# a `protective` and a `risk` per-trait row") and lands on every row that member reaches. Kleene, with
# the false arm unreachable: a module states no closed list of the traits an allele touches, so "every
# trait's judgement is present and none opposes another" is never knowable, and the column is `true` or
# null, never `false`.

# Real ontology terms for the audit's example 4 (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` § 4): SH2B3
# rs3184504's C allele, protective on hypothyroidism and coronary artery disease, risk on sepsis and
# cancer.
_HYPOTHYROIDISM = "EFO_0004705"
_CAD = "EFO_0001645"
_SEPSIS = "HP:0100806"
_CANCER = "MONDO:0004992"
_AD = "MONDO:0004975"

_SH2B3_CC = "variants[variant_key=rs3184504, genotype=C/C]"
_LPA_AG = "variants[variant_key=rs10455872, genotype=A/G]"


def _row(
    members: str,
    trait: str | None,
    direction: str | None,
    *,
    role: str = "",
    sex: str = "",
    conclusion: str = "",
) -> str:
    """One meta.csv line in `_META_HEADER`'s order: members, trait_efo_id, trait_role, direction, … sex."""
    cells = [members, trait or "", role, direction or "", conclusion, "", "", "", "", "", "", "", sex]
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(cells)
    return buffer.getvalue()


def _tradeoffs(out: Path) -> list[bool | None]:
    return _resolved(out)["tradeoff"].to_list()


def test_example_4_sh2b3_c_c_is_a_tradeoff(tmp_path: Path) -> None:
    """The audit's example 4: two protective traits, two risk traits, one member — `tradeoff` true."""
    meta = (
        _META_HEADER
        + _row(_SH2B3_CC, _HYPOTHYROIDISM, "protective")
        + _row(_SH2B3_CC, _CAD, "protective")
        + _row(_SH2B3_CC, _SEPSIS, "risk")
        + _row(_SH2B3_CC, _CANCER, "risk")
    )
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    row = _resolved_row(tmp_path / "out", "variants", ["rs3184504", "C/C"])
    assert row["tradeoff"] is True
    # A member with per-trait rows only still has its row at the grain, every fact empty and unwithheld.
    assert row["meta_rows"] == [0, 1, 2, 3]
    assert (row["tier"], row["age_of_action"], row["flags"], row["withheld"]) == (None, None, None, [])
    # The C/T row is a different member; nothing reached it.
    assert not _resolved(tmp_path / "out").filter(pl.col("key") == ["rs3184504", "C/T"]).height


def test_a_member_with_only_protective_rows_is_null_never_false(tmp_path: Path) -> None:
    meta = _META_HEADER + _row(_SH2B3_CC, _HYPOTHYROIDISM, "protective") + _row(_SH2B3_CC, _CAD, "protective")
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    assert _resolved_row(tmp_path / "out", "variants", ["rs3184504", "C/C"])["tradeoff"] is None


# (trait, direction, trait_role) per row of ONE member → the member's `tradeoff`.
_TRUTH_TABLE: list[tuple[str, list[tuple[str | None, str | None, str]], bool | None]] = [
    ("protective and risk on two traits", [(_CAD, "protective", ""), (_SEPSIS, "risk", "")], True),
    ("one protective trait", [(_CAD, "protective", "")], None),
    ("two risk traits", [(_CAD, "risk", ""), (_SEPSIS, "risk", "")], None),
    ("no direction stated", [(_CAD, None, "")], None),
    ("protective beside neutral", [(_CAD, "protective", ""), (_SEPSIS, "neutral", "")], None),
    ("protective beside contested", [(_CAD, "protective", ""), (_SEPSIS, "contested", "")], None),
    ("protective beside unknown", [(_CAD, "protective", ""), (_SEPSIS, "unknown", "")], None),
    ("a mediator counts", [(_CAD, "protective", ""), ("EFO_0006925", "risk", "mediator")], True),
    ("both mediators count", [(_CAD, "protective", "mediator"), (_SEPSIS, "risk", "mediator")], True),
    ("a direction with no trait is no per-trait row", [(None, "risk", ""), (_CAD, "protective", "")], None),
    (
        "three traits, one opposing",
        [(_CAD, "protective", ""), (_SEPSIS, "protective", ""), (_CANCER, "risk", "")],
        True,
    ),
]


@pytest.mark.parametrize(
    "rows, expected",
    [(rows, expected) for _name, rows, expected in _TRUTH_TABLE],
    ids=[n for n, *_ in _TRUTH_TABLE],
)
def test_the_kleene_truth_table(tmp_path: Path, rows, expected) -> None:
    # A row naming no direction still needs a statement to be a row, so it carries a conclusion.
    meta = _META_HEADER + "".join(
        _row(_LPA_AG, trait, direction, role=role, conclusion="" if direction else "Stated.")
        for trait, direction, role in rows
    )
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    assert _resolved_row(tmp_path / "out", "variants", ["rs10455872", "A/G"])["tradeoff"] is expected


def test_a_uniform_locus_reaches_every_genotype_row_and_an_ambiguous_one_withholds(tmp_path: Path) -> None:
    """A bare locus bears its shared `effect_allele`; the verdict lands on every row it reaches.

    rs10455872's rows share `effect_allele` G, so its judgements are about G and reach A/A as well (the
    verdict is the member's, about the allele it names). rs3184504's rows disagree on `effect_allele`, so
    each direction there is withheld and cannot make a trade-off.
    """
    meta = (
        _META_HEADER
        + _row("variants[variant_key=rs10455872]", _CAD, "risk")
        + _row("variants[variant_key=rs10455872]", _AD, "protective")
        + _row("variants[variant_key=rs3184504]", _CAD, "risk")
        + _row("variants[variant_key=rs3184504]", _AD, "protective")
    )
    result = _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    assert dict(result.manifest.compilation.warnings_summary).get("meta_member_allele_ambiguous") == 2
    df = _resolved(tmp_path / "out")
    by_locus: dict[str, set[bool | None]] = {}
    for record in df.iter_rows(named=True):
        by_locus.setdefault(record["key"][0], set()).add(record["tradeoff"])
    lpa = [
        r for r in csv.DictReader((tmp_path / "spec" / "variants.csv").open()) if r["rsid"] == "rs10455872"
    ]
    assert df.filter(pl.col("key").list.first() == "rs10455872").height == len(lpa)
    assert by_locus == {"rs10455872": {True}, "rs3184504": {None}}


def test_the_verdict_is_per_member_never_pooled_across_two_alleles(tmp_path: Path) -> None:
    """ε2 protective on one trait and ε4 risk on another is two alleles, not one allele's trade-off.

    Both reach the ε2/ε4 diplotype (an allele reaches every diplotype carrying it). Pooled, that row would
    read as a trade-off; per member it does not. Once ε4 itself carries both signs, every diplotype
    carrying ε4 does.
    """
    e2 = "allele_function[gene=APOE, allele=ε2]"
    e4 = "allele_function[gene=APOE, allele=ε4]"
    meta = _META_HEADER + _row(e2, _AD, "protective") + _row(e4, _CAD, "risk")
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    assert set(_tradeoffs(tmp_path / "out")) == {None}

    meta += _row(e4, _HYPOTHYROIDISM, "protective")
    _compile(_module(tmp_path / "spec2", meta), tmp_path / "out2")
    df = _resolved(tmp_path / "out2")
    carrying = {
        tuple(r["key"][:3]): r["tradeoff"]
        for r in df.iter_rows(named=True)
        if r["table"] == "diplotypes" and r["key"][0] == "APOE"
    }
    assert carrying == {(gene, a, b): (True if "ε4" in (a, b) else None) for gene, a, b in carrying}
    assert any(carrying.values()) and ("APOE", "ε2", "ε4") in carrying
    assert _resolved_row(tmp_path / "out2", "allele_function", ["APOE", "ε4"])["tradeoff"] is True
    assert _resolved_row(tmp_path / "out2", "allele_function", ["APOE", "ε2"])["tradeoff"] is None


def test_a_narrower_judgement_on_one_trait_drops_the_broader_one_at_that_row(tmp_path: Path) -> None:
    """The fact columns' precedence, applied per trait before the signs are read.

    ε4 is protective on one trait and risk on another, so every diplotype carrying it inherits a
    trade-off — until a diplotype row states its own judgement on the risk trait: a `diplotypes` member
    outranks the allele it contains, so at that diplotype ε4's risk is dropped. Likewise a genotype row's
    judgement outranks its locus's on the same trait.
    """
    e4 = "allele_function[gene=APOE, allele=ε4]"
    e3e4 = "diplotypes[gene=APOE, haplotype_a=ε3, haplotype_b=ε4]"
    meta = _META_HEADER + _row(e4, _HYPOTHYROIDISM, "protective") + _row(e4, _CAD, "risk")
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    key = ["APOE", "ε3", "ε4", _AD, None, None]
    assert _resolved_row(tmp_path / "out", "diplotypes", key)["tradeoff"] is True

    _compile(_module(tmp_path / "spec2", meta + _row(e3e4, _CAD, "neutral")), tmp_path / "out2")
    assert _resolved_row(tmp_path / "out2", "diplotypes", key)["tradeoff"] is None
    # ε4/ε4 has no row of its own on CAD, so it keeps the allele's trade-off.
    assert _resolved_row(tmp_path / "out2", "diplotypes", ["APOE", "ε4", "ε4", _AD, None, None])["tradeoff"]

    locus = "variants[variant_key=rs10455872]"
    meta = _META_HEADER + _row(locus, _CAD, "risk") + _row(locus, _AD, "protective")
    meta += _row(_LPA_AG, _CAD, "protective")
    _compile(_module(tmp_path / "spec3", meta), tmp_path / "out3")
    assert _resolved_row(tmp_path / "out3", "variants", ["rs10455872", "A/G"])["tradeoff"] is None
    assert _resolved_row(tmp_path / "out3", "variants", ["rs10455872", "G/G"])["tradeoff"] is True


def test_a_sex_scoped_row_replaces_the_unscoped_judgement_for_that_sex(tmp_path: Path) -> None:
    """The key's sex precedence applies per member and trait: a `male` row on a trait outranks the
    unscoped row on that trait, for males only."""
    meta = (
        _META_HEADER
        + _row(_LPA_AG, _CAD, "protective")
        + _row(_LPA_AG, _SEPSIS, "risk")
        + _row(_LPA_AG, _SEPSIS, "protective", sex="male")
        + _row(_LPA_AG, _CANCER, "risk", sex="female")
    )
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    key = ["rs10455872", "A/G"]
    assert _resolved_row(tmp_path / "out", "variants", key)["tradeoff"] is True
    assert _resolved_row(tmp_path / "out", "variants", key, "male")["tradeoff"] is None
    assert _resolved_row(tmp_path / "out", "variants", key, "female")["tradeoff"] is True


def test_tradeoff_is_a_nullable_boolean_and_never_false(tmp_path: Path) -> None:
    meta = (
        _META_HEADER
        + _row(_SH2B3_CC, _CAD, "protective")
        + _row(_SH2B3_CC, _SEPSIS, "risk")
        + _row(_LPA_AG, _CAD, "protective")
        + "variants[flags=legacy_longevitymap],,,,,,D,,,,,,\n"
    )
    _compile(_module(tmp_path / "spec", meta), tmp_path / "out")
    df = _resolved(tmp_path / "out")
    assert df.schema["tradeoff"] == pl.Boolean
    assert False not in df["tradeoff"].to_list()
    assert set(df["tradeoff"].to_list()) == {True, None}


def test_the_round_trip_and_two_compiles_reproduce_tradeoff_byte_for_byte(tmp_path: Path) -> None:
    meta = (
        _META_HEADER
        + _row(_SH2B3_CC, _HYPOTHYROIDISM, "protective")
        + _row(_SH2B3_CC, _SEPSIS, "risk", role="mediator")
        + _row(_LPA_AG, _CAD, "protective", sex="female")
    )
    spec = _module(tmp_path / "spec", meta)
    first = _compile(spec, tmp_path / "out1")
    again = _compile(spec, tmp_path / "out1b")
    assert first.manifest.artifact.digest == again.manifest.artifact.digest
    assert (tmp_path / "out1" / "meta_resolved.parquet").read_bytes() == (
        tmp_path / "out1b" / "meta_resolved.parquet"
    ).read_bytes()

    reverse_module(tmp_path / "out1", tmp_path / "reversed")
    assert "tradeoff" not in (tmp_path / "reversed" / "meta.csv").read_text(encoding="utf-8").splitlines()[0]
    second = _compile(tmp_path / "reversed", tmp_path / "out2")
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert _tradeoffs(tmp_path / "out2") == _tradeoffs(tmp_path / "out1")
    assert True in _tradeoffs(tmp_path / "out1")


def test_tradeoff_is_not_authorable_on_meta_csv(tmp_path: Path) -> None:
    """The derived column has no authored twin: a `tradeoff` column in meta.csv is refused by name."""
    header = _META_HEADER.rstrip("\n") + ",tradeoff\n"
    meta = header + _row(_SH2B3_CC, _CAD, "protective").rstrip("\n") + ",true\n"
    result = compile_module(_module(tmp_path / "spec", meta), tmp_path / "out")
    assert not result.success
    assert any("'tradeoff' is a verdict the compiler computes" in e for e in result.errors), result.errors
