"""What the three meta-table reference examples state, read off their compiled parquets (0.8, PT2 §6).

`test_reference_examples_roundtrip.py` already proves every example compiles under `--strict`, reverses
and recompiles to the same digest. That sweep cannot see whether the meta-table *did what the README
says*: a precedence rule that silently stopped ranking would still round-trip. So each example's README
states its expected values, and this file asserts them against the real compile path.

Every expected value is computed from the example's own CSVs at run time: which diplotypes a selector
should reach, which loci the legacy tag covers, which phenotypes CPIC's drafter wrote. Only the values
the author chose (a tier letter, a confidence word) are read off `meta.csv` rather than restated.
"""

import csv
import io
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_format.meta import parse_members

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_APOE = _EXAMPLES / "apoe_klvs_meta"
_PLEIO = _EXAMPLES / "pleiotropy_tradeoff"
_CPIC = _EXAMPLES / "cpic_gene_pairs"


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def _compiled(spec: Path, out: Path):
    result = compile_module(spec, out, strict=True)
    assert result.success, result.errors
    return result


def _meta_by_members(out: Path) -> dict[str, dict]:
    return {row["members"]: row for row in pl.read_parquet(out / "meta.parquet").iter_rows(named=True)}


_RESOLVED_CACHE: dict[Path, dict[tuple, list[dict]]] = {}


def _resolved(out: Path, table: str, key: list[str | None]) -> dict:
    """The unscoped `meta_resolved.parquet` row for one target (no sex, no drug); the parquet is read
    once per artifact."""
    if out not in _RESOLVED_CACHE:
        index: dict[tuple, list[dict]] = {}
        for r in pl.read_parquet(out / "meta_resolved.parquet").iter_rows(named=True):
            index.setdefault((r["table"], tuple(r["key"]), r["sex"], r["drug"]), []).append(r)
        _RESOLVED_CACHE[out] = index
    rows = _RESOLVED_CACHE[out].get((table, tuple(key), None, None), [])
    assert len(rows) == 1, (table, key)
    return rows[0]


def _expected_matches(members: str, diplotypes: list[dict[str, str]]) -> list[dict]:
    """What `meta.parquet` should list for a row of `diplotypes` members, computed from the CSV rows."""
    return [
        {"member": position, "table": "diplotypes", "key": _diplotype_key(d)}
        for position, member in enumerate(parse_members(members))
        for d in diplotypes
        if all(d[column] == value for column, value in member.conditions)
    ]


def _authored(spec: Path, members: str) -> dict[str, str]:
    (row,) = [r for r in _rows(spec / "meta.csv") if r["members"] == members]
    return row


def _diplotype_key(row: dict[str, str]) -> list[str | None]:
    """`DiplotypeRow`'s key as `meta.parquet` records it: gene, the pair, trait, drug, context."""
    return [row["gene"], row["haplotype_a"], row["haplotype_b"], row.get("trait_efo_id") or None, None, None]


def _codes(result) -> dict[str, int]:
    return dict(result.manifest.compilation.warnings_summary)


# ── apoe_klvs_meta ───────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def apoe(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("apoe") / "out"
    return _compiled(_APOE, out), out


def test_apoe_the_legacy_tag_is_beaten_only_where_a_locus_row_exists(apoe) -> None:
    _result, out = apoe
    legacy = _authored(_APOE, "variants[flags=legacy_longevitymap]")["tier"]
    locus_rows = {
        dict(parse_members(r["members"])[0].conditions)["variant_key"]: r["tier"]
        for r in _rows(_APOE / "meta.csv")
        if r["members"].startswith("variants[variant_key=")
    }
    tagged = [r for r in _rows(_APOE / "variants.csv") if "legacy_longevitymap" in r["flags"]]
    assert {r["rsid"] for r in tagged} - set(locus_rows), "the example must keep a legacy locus nobody beat"
    assert set(locus_rows) & {r["rsid"] for r in tagged}, "and one a locus row beats"
    for row in tagged:
        resolved = _resolved(out, "variants", [row["rsid"], row["genotype"]])
        assert resolved["tier"] == locus_rows.get(row["rsid"], legacy), row
        assert resolved["withheld"] == []
        if row["rsid"] in locus_rows:
            stated = _authored(_APOE, f"variants[variant_key={row['rsid']}]")
            assert (resolved["age_of_action"], resolved["age_of_action_confidence"]) == (
                stated["age_of_action"],
                stated["age_of_action_confidence"],
            )


def test_apoe_the_e2_e4_diplotype_settles_what_it_states_and_only_that(apoe) -> None:
    _result, out = apoe
    e4 = _authored(_APOE, "allele_function[gene=APOE, allele=ε4]")
    e2 = _authored(_APOE, "allele_function[gene=APOE, allele=ε2]")
    settle = _authored(_APOE, "diplotypes[gene=APOE, haplotype_a=ε2, haplotype_b=ε4]")
    assert e4["age_of_action_confidence"] != e2["age_of_action_confidence"], "the alleles must disagree"
    assert e4["flags"] != e2["flags"]
    (pair,) = [
        d for d in _rows(_APOE / "diplotypes.csv") if (d["haplotype_a"], d["haplotype_b"]) == ("ε2", "ε4")
    ]
    resolved = _resolved(out, "diplotypes", _diplotype_key(pair))
    # A diplotypes member outranks an allele_function member reaching the same diplotype through an
    # allele it contains (the containment arm of the precedence), for the column it states.
    assert resolved["age_of_action_confidence"] == settle["age_of_action_confidence"]
    # The columns the two alleles agree on reach the diplotype; unstated on it is not different.
    assert (resolved["tier"], resolved["age_of_action"]) == (e4["tier"], e4["age_of_action"])
    # It states no flags, so the alleles' disagreement on flags still stands: withheld, never picked.
    assert settle["flags"] == ""
    assert resolved["flags"] is None
    assert resolved["withheld"] == ["flags"]


def test_apoe_a_one_allele_diplotype_inherits_that_alleles_facts(apoe) -> None:
    _result, out = apoe
    named = {
        allele: _authored(_APOE, f"allele_function[gene=APOE, allele={allele}]") for allele in ("ε2", "ε4")
    }
    checked = 0
    for d in _rows(_APOE / "diplotypes.csv"):
        carried = {d["haplotype_a"], d["haplotype_b"]} & set(named)
        if d["gene"] != "APOE" or len(carried) != 1:
            continue
        (allele,) = carried
        resolved = _resolved(out, "diplotypes", _diplotype_key(d))
        for column in ("tier", "age_of_action", "age_of_action_confidence"):
            assert resolved[column] == named[allele][column], (d, column)
        assert resolved["flags"] == [named[allele]["flags"]]
        assert resolved["withheld"] == []
        checked += 1
    assert checked, "the example must carry a diplotype holding exactly one named allele"


def test_apoe_kl_vs_by_e4_replaces_exactly_the_rows_it_names(apoe) -> None:
    _result, out = apoe
    (members,) = [r["members"] for r in _rows(_APOE / "meta.csv") if " & " in r["members"]]
    row = _meta_by_members(out)[members]
    expected = _expected_matches(members, _rows(_APOE / "diplotypes.csv"))
    assert {m["member"] for m in expected} == {0, 1}
    assert row["matches"] == expected
    assert row["replaces"] is True
    # A combination's facts are about the combination: its meta row never reaches a member row, so no
    # meta_resolved row lists it, and its tier never lands on a diplotype it matched.
    combination = [r["members"] for r in _rows(_APOE / "meta.csv")].index(members)
    resolved = pl.read_parquet(out / "meta_resolved.parquet")
    assert not [r for r in resolved.iter_rows(named=True) if combination in r["meta_rows"]]
    combined_tier = _authored(_APOE, members)["tier"]
    for match in expected:
        hits = [r for r in resolved.iter_rows(named=True) if r["key"] == match["key"]]
        assert all(r["tier"] != combined_tier for r in hits), match


def test_apoe_the_study_links_on_rs429358_and_rs7412_are_not_orphans(apoe) -> None:
    """APOE is scored only as diplotypes, so its SNPs are no `variants.csv` row; haplotypes.csv carries them."""
    result, _out = apoe
    variants = {r["rsid"] for r in _rows(_APOE / "variants.csv")}
    studied = {r["rsid"] for r in _rows(_APOE / "studies.csv")}
    assert {"rs429358", "rs7412"} <= studied - variants
    assert "study_variant_orphan" not in _codes(result)


def test_apoe_the_tier_scale_reaches_the_manifest(apoe) -> None:
    result, _out = apoe
    assert result.manifest.tier_scale == "longevitymap_v2"


# ── pleiotropy_tradeoff ──────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def pleio(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("pleio") / "out"
    return _compiled(_PLEIO, out), out


def _signs(spec: Path) -> dict[str, set[str]]:
    """Each locus member's stated directions, read off meta.csv."""
    signs: dict[str, set[str]] = {}
    for row in _rows(spec / "meta.csv"):
        if row["direction"]:
            locus = dict(parse_members(row["members"])[0].conditions)["variant_key"]
            signs.setdefault(locus, set()).add(row["direction"])
    return signs


def _effect_alleles(spec: Path) -> dict[str, set[str]]:
    alleles: dict[str, set[str]] = {}
    for row in _rows(spec / "variants.csv"):
        alleles.setdefault(row["rsid"], set()).add(row["effect_allele"])
    return alleles


def test_pleiotropy_tradeoff_is_true_null_and_never_false(pleio) -> None:
    result, out = pleio
    signs = _signs(_PLEIO)
    alleles = _effect_alleles(_PLEIO)
    uniform = {rsid for rsid, stated in alleles.items() if len(stated) == 1 and "" not in stated}
    assert {"protective", "risk"} in signs.values(), "the example must carry an opposing pair"
    assert any(s == {"protective"} for rsid, s in signs.items() if rsid in uniform), "and a one-sign member"
    assert set(signs) - uniform, "and an allele-ambiguous locus"
    for row in _rows(_PLEIO / "variants.csv"):
        resolved = _resolved(out, "variants", [row["rsid"], row["genotype"]])
        opposed = row["rsid"] in uniform and signs[row["rsid"]] == {"protective", "risk"}
        assert resolved["tradeoff"] is (True if opposed else None), row
    assert pl.read_parquet(out / "meta_resolved.parquet")["tradeoff"].to_list().count(False) == 0


def test_pleiotropy_the_ambiguous_locus_warns_once_and_withholds_its_direction(pleio) -> None:
    result, out = pleio
    alleles = _effect_alleles(_PLEIO)
    ambiguous = {rsid for rsid, stated in alleles.items() if len(stated) != 1 or "" in stated}
    authored = _rows(_PLEIO / "meta.csv")
    expected = [
        r["members"]
        for r in authored
        if dict(parse_members(r["members"])[0].conditions)["variant_key"] in ambiguous
    ]
    assert _codes(result).get("meta_member_allele_ambiguous") == len(expected) > 0
    meta = _meta_by_members(out)
    for row in pl.read_parquet(out / "meta.parquet").iter_rows(named=True):
        want = ["direction"] if row["members"] in expected else []
        assert row["withheld"] == want, row["members"]
    # The authored cell survives for reverse; only the compiled reading withholds it.
    for members in expected:
        assert meta[members]["direction"] == next(r["direction"] for r in authored if r["members"] == members)


# ── cpic_gene_pairs ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def cpic(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("cpic") / "out"
    return _compiled(_CPIC, out), out


def test_cpic_each_phenotype_pair_matches_every_drafted_diplotype_of_both_phenotypes(cpic) -> None:
    _result, out = cpic
    diplotypes = _rows(_CPIC / "diplotypes.csv")
    meta = _meta_by_members(out)
    authored = _rows(_CPIC / "meta.csv")
    assert len(meta) == len(authored)
    for row in authored:
        expected = _expected_matches(row["members"], diplotypes)
        compiled = meta[row["members"]]
        assert compiled["matches"] == expected
        assert {m["member"] for m in expected} == {0, 1}, (
            "a pair whose phenotype was not drafted matches nothing"
        )
        assert compiled["replaces"] is True
        assert compiled["conclusion"] == row["conclusion"]
    # The selector is existential: some phenotype is carried by more than one drafted diplotype.
    assert any(compiled["match_count"] > len(parse_members(m)) for m, compiled in meta.items())
    # No one-member row, so nothing reaches meta_resolved.
    assert pl.read_parquet(out / "meta_resolved.parquet").height == 0


def test_cpic_the_licence_row_is_cpics_own_terms() -> None:
    (cpic,) = [r for r in _rows(_CPIC / "licensing.csv") if r["source"] == "cpic"]
    assert (cpic["share_alike"], cpic["commercial_use"], cpic["declared_use"]) == (
        "true",
        "false",
        "non_commercial",
    )
