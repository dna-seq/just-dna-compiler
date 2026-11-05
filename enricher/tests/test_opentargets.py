"""The Open Targets lane and its pass (RM333, RM239, RM236), over a slice cut from the real 26.09 release.

The slice (`assets/opentargets_slice/`) is `opentargets_build.subset_snapshot` run on a full build of the
release (`probes/LANES_0_8.md` § built) for the alleles of `reference_examples/hfe_hemochromatosis`, plus
rs2075650, `6_26072764_C_T` and rs35589214's two alleles at `8:78193100 C`. `subset_snapshot` keeps exactly
the rows the pass reads for those alleles, and every other allele at their loci in the allele table, so
the pass over the slice answers as it does over the whole release for that module. Every expected value below is computed at
run time from the slice's own parquet, never copied from it.
"""

import csv
import json
import os
import shutil
from pathlib import Path

import duckdb
import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, load_csv_rows, reverse_module
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.licensing import sidecar_path
from just_dna_enricher.locations import resolve_opentargets_reference
from just_dna_enricher.opentargets import OpenTargetsError, enrich_opentargets
from just_dna_enricher.opentargets_build import (
    OPENTARGETS_DATASETS,
    OpenTargetsUnavailable,
    list_parts,
    subset_snapshot,
)
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.locus_genes import ColocalisationRow, LocusToGeneRow
from just_dna_format.snapshot import SnapshotRelease, read_release, write_release
from just_dna_format.sources import SourceRow

_ROOT = Path(__file__).resolve().parents[2]
SLICE = _ROOT / "assets" / "opentargets_slice"
MODULE = _ROOT / "reference_examples" / "hfe_hemochromatosis"


#: rs2075650 (TOMM40), GRCh38 19:44892362 A>G as the release's allele table states it: a variant that
#: LEADS some of the credible sets it is in (41 of its 175 GWAS sets in 26.09), beside the HFE module's
#: rs1800562, which sits in 82 and leads none. The two shapes the member-wide tables must cover.
LEAD_ROW = {
    "variant_key": "rs2075650",
    "rsid": "rs2075650",
    "chrom": "19",
    "start": "44892362",
    "ref": "A",
    "alts": "G",
    "genome_build": "GRCh38",
    "locus_index": "0",
    "source": "authored",
    "status": "resolved",
}


def _append(path: Path, rows: list[dict]) -> None:
    with path.open(newline="") as handle:
        fieldnames = csv.DictReader(handle).fieldnames
    with path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


@pytest.fixture
def module(tmp_path: Path) -> Path:
    """The HFE example plus one lead variant: its resolution row and the Catalog's associations for it.

    The associations were read from the Catalog's v2 API on 2026-11-04 (the legacy API the `gwas` pass
    reads answers 410) and are kept in the slice as `gwas_effects_rs2075650.csv`. The variant has no
    `variants.csv` row, so a compile warns that the module's GWAS rows name a variant it does not
    annotate; that is the price of not authoring a conclusion for a test.
    """
    spec = tmp_path / "hfe"
    shutil.copytree(MODULE, spec)
    _append(spec / "resolution.csv", [LEAD_ROW])
    with (SLICE / "gwas_effects_rs2075650.csv").open(newline="") as handle:
        _append(spec / "gwas_effects.csv", list(csv.DictReader(handle)))
    return spec


def _query(sql: str) -> list[tuple]:
    data = SLICE / "data"
    con = duckdb.connect(":memory:")
    for view, name in (
        ("variants", "variants.parquet"),
        ("sets", "credible_sets.parquet"),
        ("members", "credible_set_members-*.parquet"),
        ("l2g", "l2g.parquet"),
        ("coloc", "colocalisations-*.parquet"),
        ("cons", "consequences-*.parquet"),
    ):
        con.execute(f"CREATE VIEW {view} AS SELECT * FROM read_parquet('{data / name}')")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _keys_by_variant_id(spec: Path, data: Path) -> dict[str, set[str]]:
    """The release's `variant_id` of every resolved allele in `spec`, mapped to the module keys naming it.

    Read off the module's own `resolution.csv` and the snapshot's allele table, independently of the pass.
    """
    with (spec / "resolution.csv").open(newline="") as handle:
        alleles = [
            (row["variant_key"], row["chrom"], int(row["start"]), row["ref"], alt.strip())
            for row in csv.DictReader(handle)
            if row["status"] != "not_found" and row["genome_build"] == "GRCh38"
            for alt in row["alts"].split(",")
            if alt.strip()
        ]
    variants = pl.read_parquet(data / "variants.parquet")
    out: dict[str, set[str]] = {}
    for key, chrom, position, ref, alt in alleles:
        hits = variants.filter(
            (pl.col("chrom") == chrom)
            & (pl.col("position") == position)
            & (pl.col("ref") == ref)
            & (pl.col("alt") == alt)
        )
        for variant_id in hits["variant_id"]:
            out.setdefault(variant_id, set()).add(key)
    return out


def _member_loci(spec: Path, data: Path) -> set[tuple[str, str]]:
    """`(study_locus_id, variant_key)` for every GWAS credible set a module allele is a member of."""
    keys = _keys_by_variant_id(spec, data)
    sets = pl.read_parquet(data / "credible_sets.parquet").select("study_locus_id")
    members = (
        pl.read_parquet(data / "credible_set_members-*.parquet")
        .filter(pl.col("variant_id").is_in(list(keys)))
        .join(sets, on="study_locus_id", how="semi")
    )
    return {
        (locus, key)
        for locus, variant_id in members.select("study_locus_id", "variant_id").iter_rows()
        for key in keys[variant_id]
    }


def _sources(spec: Path) -> set[tuple[str, str]]:
    path = sidecar_path(spec, "sources.csv", error=RuntimeError)
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    assert not errors
    return {(r.source, r.layer) for r in rows}


def test_the_slice_is_a_snapshot_of_the_pinned_release() -> None:
    record = read_release(SLICE)
    assert record is not None and record.dataset == "opentargets_26.09"
    assert record.genome_build == "GRCh38"
    assert record.model_dump().get("subset_of"), "the slice names the alleles it was cut for"


def test_every_set_a_module_allele_is_in_gets_its_l2g_rows_and_none_is_collapsed(module: Path) -> None:
    """One row per (study locus, gene, module variant) for every credible set the variant is a MEMBER of.

    Members, not lead-only (RM333, 2026-11-04): a variant that leads nothing still gets the L2G rows of
    every set it sits in. `@multiplicity-is-a-finding`: several study loci per variant are kept.
    """
    result = enrich_opentargets(module, snapshot=SLICE)
    member_loci = _member_loci(module, SLICE / "data")
    scores = {
        (locus, gene): score
        for locus, gene, score in _query("SELECT study_locus_id, gene_id, l2g_score FROM l2g")
    }
    expected = {
        (locus, gene, key)
        for locus, key in member_loci
        for (scored_locus, gene) in scores
        if scored_locus == locus
    }
    assert expected, "the slice must exercise the table"
    got = {(r.study_locus_id, r.gene_id, r.variant_key) for r in result.locus_to_gene}
    assert got == expected
    assert len(result.locus_to_gene) == len(got), "one row per (study locus, gene, variant_key)"
    assert all(r.l2g_score == scores[(r.study_locus_id, r.gene_id)] for r in result.locus_to_gene)
    # `lead_variant_id` stays the source's lead, which for a member that is not the lead names another variant.
    leads = dict(_query("SELECT study_locus_id, lead_variant_id FROM sets"))
    assert all(r.lead_variant_id == leads[r.study_locus_id] for r in result.locus_to_gene)
    # Several study loci per variant are kept, never resolved to one.
    loci_per_variant: dict[str, set[str]] = {}
    for row in result.locus_to_gene:
        loci_per_variant.setdefault(row.variant_key, set()).add(row.study_locus_id)
    assert max(len(v) for v in loci_per_variant.values()) > 1
    written, errors, _ = load_csv_rows(
        sidecar_path(module, "locus_to_gene.csv", error=RuntimeError), LocusToGeneRow, "locus_to_gene.csv"
    )
    assert not errors and {(r.study_locus_id, r.gene_id, r.variant_key) for r in written} == expected


def test_hfe_c282y_leads_no_set_and_gets_the_rows_of_every_set_it_is_in(module: Path) -> None:
    """The case the lane exists for: rs1800562 sits in GWAS credible sets and leads none of them."""
    result = enrich_opentargets(module, snapshot=SLICE)
    (variant_id,) = [
        vid for vid, keys in _keys_by_variant_id(module, SLICE / "data").items() if "rs1800562" in keys
    ]
    assert not _query(f"SELECT 1 FROM sets WHERE lead_variant_id = '{variant_id}'"), "C282Y leads no set"
    in_sets = {
        locus for (locus,) in _query(f"SELECT study_locus_id FROM members WHERE variant_id = '{variant_id}'")
    }
    scored = {locus for (locus,) in _query("SELECT DISTINCT study_locus_id FROM l2g")} & in_sets
    assert scored, "the slice must hold the L2G rows of C282Y's sets"
    rows = [r for r in result.locus_to_gene if r.variant_key == "rs1800562"]
    assert {r.study_locus_id for r in rows} == scored
    assert all(r.lead_variant_id != variant_id for r in rows)
    coloc = {r.study_locus_id for r in result.colocalisations if r.variant_key == "rs1800562"}
    assert coloc == {locus for (locus,) in _query("SELECT DISTINCT study_locus_id FROM coloc")} & in_sets


def test_coloc_rows_are_the_member_sets_molecular_qtl_pairs(module: Path) -> None:
    result = enrich_opentargets(module, snapshot=SLICE)
    member_loci = _member_loci(module, SLICE / "data")
    pairs = _query("SELECT study_locus_id, right_study_locus_id FROM coloc")
    expected = {
        (locus, right, key)
        for locus, right in pairs
        for (member_locus, key) in member_loci
        if member_locus == locus
    }
    assert expected
    got = {(r.study_locus_id, r.right_study_locus_id, r.variant_key) for r in result.colocalisations}
    assert got == expected and len(result.colocalisations) == len(expected)
    assert all(r.right_study_type != "gwas" for r in result.colocalisations)
    # The gene the right side measured is named, so a consumer can join coloc to an L2G row.
    assert any(r.right_gene_id for r in result.colocalisations)
    written, errors, _ = load_csv_rows(
        sidecar_path(module, "colocalisations.csv", error=RuntimeError),
        ColocalisationRow,
        "colocalisations.csv",
    )
    assert (
        not errors
        and {(r.study_locus_id, r.right_study_locus_id, r.variant_key) for r in written} == expected
    )


def test_consequences_are_one_row_per_variant_and_transcript(module: Path) -> None:
    result = enrich_opentargets(module, snapshot=SLICE)
    ids = sorted(_keys_by_variant_id(module, SLICE / "data"))
    expected = len(
        _query("SELECT * FROM cons WHERE variant_id IN (" + ", ".join(f"'{i}'" for i in ids) + ")")
    )
    assert expected and len(result.consequences) == expected
    keys = [(r.variant_key, r.transcript) for r in result.consequences]
    assert len(keys) == len(set(keys))
    assert {r.impact for r in result.consequences} <= {"HIGH", "MODERATE", "LOW", "MODIFIER"}
    assert all(r.consequence_so_ids and r.consequence_so_ids.startswith("SO_") for r in result.consequences)


def test_the_posterior_is_filled_once_and_every_other_row_is_counted_never_zeroed(module: Path) -> None:
    """RM239: exactly one value fills; no credible set, not a member, and contested each leave it empty."""
    result = enrich_opentargets(module, snapshot=SLICE)
    counts = result.posterior
    rows = result.gwas_effects
    filled = [r for r in rows if r.posterior_probability is not None]
    assert counts.filled == len(filled) > 0
    assert all(r.fine_mapping_method for r in filled)
    assert not any(r.posterior_probability == 0 for r in rows if r.posterior_probability is not None)
    # Every row lands in exactly one bucket.
    assert sum(counts.__dict__.values()) == len(rows)
    # A filled value is the slice's own membership for that study.
    studies = {r.study_accession for r in filled}
    members = {
        (study, round(pp, 12))
        for study, pp in _query(
            "SELECT s.study_id, m.posterior_probability FROM members m JOIN sets s USING (study_locus_id)"
        )
        if study in studies
    }
    assert {(r.study_accession, round(r.posterior_probability, 12)) for r in filled} <= members
    written, errors, _ = load_csv_rows(
        sidecar_path(module, "gwas_effects.csv", error=RuntimeError), GwasEffectRow, "gwas_effects.csv"
    )
    assert not errors and sum(1 for r in written if r.posterior_probability is not None) == counts.filled


def test_a_study_with_no_credible_set_is_withheld_and_counted(module: Path) -> None:
    result = enrich_opentargets(module, snapshot=SLICE)
    with_sets = {s for (s,) in _query("SELECT DISTINCT study_id FROM sets")}
    without = [r for r in result.gwas_effects if r.study_accession and r.study_accession not in with_sets]
    assert without, "the module must carry a study the release did not fine-map"
    assert all(r.posterior_probability is None for r in without)
    assert result.posterior.study_without_credible_set == sum(
        1 for r in without if r.variant_key not in result.not_in_release
    )


def test_each_written_table_carries_its_licence_row_in_the_same_run(module: Path) -> None:
    before = _sources(module)
    result = enrich_opentargets(module, snapshot=SLICE)
    added = _sources(module) - before
    expected = {
        ("opentargets", "locus_to_gene"),
        ("opentargets", "colocalisation"),
        ("opentargets", "consequence"),
    }
    if result.posterior.filled:
        expected.add(("opentargets", "gwas_effect"))
    assert added == expected


def test_no_snapshot_is_nobody_asked_and_writes_nothing(module: Path, no_ambient_caches: Path) -> None:
    before = sorted(p.name for p in module.iterdir())
    result = enrich_opentargets(module)
    assert result.skipped == "no_snapshot"
    assert sorted(p.name for p in module.iterdir()) == before


def test_strict_refuses_a_snapshot_built_from_part_of_the_release(module: Path, tmp_path: Path) -> None:
    partial = tmp_path / "partial"
    shutil.copytree(SLICE, partial)
    record = read_release(partial)
    assert record is not None
    totals = {name: count + 1 for name, count in (record.model_dump().get("parts_read") or {}).items()}
    write_release(partial, SnapshotRelease(**{**record.model_dump(exclude_none=True), "parts_total": totals}))
    with pytest.raises(OpenTargetsError, match="part of the release"):
        enrich_opentargets(module, snapshot=partial, mode="strict")
    # best_effort writes, and says so.
    assert enrich_opentargets(module, snapshot=partial).partial


def test_a_rerun_is_a_fixed_point(module: Path) -> None:
    enrich_opentargets(module, snapshot=SLICE)
    first = {p.name: p.read_text() for p in module.glob("*.csv")}
    enrich_opentargets(module, snapshot=SLICE)
    second = {p.name: p.read_text() for p in module.glob("*.csv")}

    def facts(text: str) -> list[dict]:
        return [
            {k: v for k, v in row.items() if k != "fetched_at"} for row in csv.DictReader(text.splitlines())
        ]

    assert first.keys() == second.keys()
    assert all(facts(first[name]) == facts(second[name]) for name in first)


def test_compile_reverse_compile_keeps_every_new_value(module: Path, tmp_path: Path) -> None:
    """Principle 7 over the three tables and RM239's two columns, through the real compile and reverse."""
    enrich_opentargets(module, snapshot=SLICE)
    first = compile_module(module, tmp_path / "out1")
    assert first.success, first.errors
    reverse_module(tmp_path / "out1", tmp_path / "spec2")
    second = compile_module(tmp_path / "spec2", tmp_path / "out2")
    assert second.success, second.errors
    m1 = json.loads((tmp_path / "out1" / "manifest.json").read_text())
    m2 = json.loads((tmp_path / "out2" / "manifest.json").read_text())
    assert m1["artifact"]["digest"] == m2["artifact"]["digest"]
    assert m1["content_signature"] == m2["content_signature"]
    for block in ("locus_to_gene", "colocalisations", "consequences"):
        assert m1[block]["row_count"] > 0
        assert m1[block]["signature"] == m2[block]["signature"]
    assert m1["gwas_effects"]["with_posterior"] > 0
    assert m1["gwas_effects"]["signature"] == m2["gwas_effects"]["signature"]


def test_the_slice_answers_as_the_whole_release_does(module: Path, tmp_path: Path) -> None:
    """`subset_snapshot`'s promise, checked where the whole release is provisioned (skipped elsewhere)."""
    full = resolve_opentargets_reference()
    if full is None or full.resolve() == SLICE.resolve():
        pytest.skip("the whole Open Targets snapshot is not provisioned on this machine")
    other = tmp_path / "other"
    shutil.copytree(module, other)
    on_slice = enrich_opentargets(module, snapshot=SLICE)
    on_full = enrich_opentargets(other, snapshot=full)
    for name in ("locus_to_gene", "colocalisations", "consequences"):
        assert [r.model_dump(exclude={"fetched_at"}) for r in getattr(on_slice, name)] == [
            r.model_dump(exclude={"fetched_at"}) for r in getattr(on_full, name)
        ]
    assert on_slice.posterior == on_full.posterior


def test_two_sets_of_one_study_that_disagree_withhold_the_posterior(module: Path, tmp_path: Path) -> None:
    """`@multiplicity-is-a-finding`: two values for one (variant, study) are counted, never one picked.

    The release has 1,096,671 such pairs, but none among this module's, so the slice is copied and one
    real membership is given a second set in the same study with another posterior. Everything else is
    the release's own rows.
    """
    filled = [
        r
        for r in enrich_opentargets(module, snapshot=SLICE, write=False).gwas_effects
        if r.posterior_probability
    ]
    target = filled[0]
    disagreeing = tmp_path / "disagreeing"
    shutil.copytree(SLICE, disagreeing)
    data = disagreeing / "data"
    sets = pl.read_parquet(data / "credible_sets.parquet")
    members = pl.read_parquet(data / "credible_set_members-00000.parquet")
    (variant_id,) = {v for (v,) in _query("SELECT variant_id FROM variants WHERE position = 44892362")}
    original = sets.join(members.filter(pl.col("variant_id") == variant_id), on="study_locus_id").filter(
        pl.col("study_id") == target.study_accession
    )
    assert original.height == 1
    second = "f" * 32
    pl.concat(
        [sets, original.select(sets.columns).with_columns(pl.lit(second).alias("study_locus_id"))]
    ).write_parquet(data / "credible_sets.parquet")
    pl.concat(
        [
            members,
            pl.DataFrame(
                {
                    "study_locus_id": [second],
                    "variant_id": [variant_id],
                    "posterior_probability": [target.posterior_probability / 2],
                }
            ),
        ]
    ).write_parquet(data / "credible_set_members-00000.parquet")

    result = enrich_opentargets(module, snapshot=disagreeing, write=False)
    (row,) = [r for r in result.gwas_effects if r.association_id == target.association_id]
    assert row.posterior_probability is None and row.fine_mapping_method is None
    assert result.posterior.contested >= 1


def test_two_module_keys_on_one_release_allele_withhold_its_study_loci_and_say_so(module: Path) -> None:
    """A module naming one release allele under two keys has that allele's study-locus rows withheld, both keys named."""
    _append(module / "resolution.csv", [{**LEAD_ROW, "variant_key": "19:44892362:A:G", "rsid": ""}])
    result = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert result.shared_allele_keys == ["19:44892362:A:G", "rs2075650"]
    withheld = set(result.shared_allele_keys)
    assert not any(r.variant_key in withheld for r in result.locus_to_gene + result.colocalisations)
    # Every other module variant keeps its rows: the withholding is per key, not per run.
    assert any(r.variant_key == "rs1800562" for r in result.locus_to_gene)


#: GRCh38 6:26072764 C>T, the release's `6_26072764_C_T`: a member of all 82 of C282Y's GWAS sets (and 22
#: more), leading none. In the slice so two module variants share study loci, which the old
#: `(study_locus_id, gene_id)` key could not hold.
CO_MEMBER_ROW = {
    **LEAD_ROW,
    "variant_key": "6:26072764:C:T",
    "rsid": "",
    "chrom": "6",
    "start": "26072764",
    "ref": "C",
    "alts": "T",
}


def test_two_module_variants_in_one_set_each_get_its_rows_and_survive_the_round_trip(
    module: Path, tmp_path: Path
) -> None:
    """`variant_key` is in the key: one (study locus, gene) row per member variant, through compile and reverse."""
    _append(module / "resolution.csv", [CO_MEMBER_ROW])
    result = enrich_opentargets(module, snapshot=SLICE)
    member_loci = _member_loci(module, SLICE / "data")
    by_key: dict[str, set[str]] = {}
    for locus, key in member_loci:
        by_key.setdefault(key, set()).add(locus)
    shared = by_key["rs1800562"] & by_key["6:26072764:C:T"]
    assert shared, "the two variants must share credible sets in the slice"
    keys_per_pair: dict[tuple[str, str], set[str]] = {}
    for row in result.locus_to_gene:
        keys_per_pair.setdefault((row.study_locus_id, row.gene_id), set()).add(row.variant_key)
    both = {pair for pair, keys in keys_per_pair.items() if {"rs1800562", "6:26072764:C:T"} <= keys}
    assert {locus for locus, _gene in both} == shared & {r.study_locus_id for r in result.locus_to_gene}
    # The fact columns are the set's, whichever member asked: the two rows differ in `variant_key` only.
    for locus, gene in both:
        pair_rows = [r for r in result.locus_to_gene if (r.study_locus_id, r.gene_id) == (locus, gene)]
        assert (
            len(
                {
                    json.dumps(r.model_dump(exclude={"variant_key", "fetched_at"}), sort_keys=True)
                    for r in pair_rows
                }
            )
            == 1
        )

    first = compile_module(module, tmp_path / "out1")
    assert first.success, first.errors
    reverse_module(tmp_path / "out1", tmp_path / "spec2")
    second = compile_module(tmp_path / "spec2", tmp_path / "out2")
    assert second.success, second.errors
    m1 = json.loads((tmp_path / "out1" / "manifest.json").read_text())
    m2 = json.loads((tmp_path / "out2" / "manifest.json").read_text())
    assert m1["artifact"]["digest"] == m2["artifact"]["digest"]
    assert m1["locus_to_gene"]["row_count"] == len(result.locus_to_gene)
    assert m1["colocalisations"]["row_count"] == len(result.colocalisations)
    assert m1["locus_to_gene"]["signature"] == m2["locus_to_gene"]["signature"]
    assert m1["colocalisations"]["signature"] == m2["colocalisations"]["signature"]


def test_an_overlay_correction_of_a_pair_reaches_every_members_row(module: Path, tmp_path: Path) -> None:
    """The overlay keys on `(study_locus_id, gene_id)`, not on `variant_key`: a score is the set's fact."""
    _append(module / "resolution.csv", [CO_MEMBER_ROW])
    result = enrich_opentargets(module, snapshot=SLICE)
    keys_per_pair: dict[tuple[str, str], set[str]] = {}
    for row in result.locus_to_gene:
        keys_per_pair.setdefault((row.study_locus_id, row.gene_id), set()).add(row.variant_key)
    locus, gene = min(pair for pair, keys in keys_per_pair.items() if len(keys) > 1)
    with (module / "overrides.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["table", "subject", "member", "field", "operation", "value", "reason"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "table": "locus_to_gene.csv",
                "subject": locus,
                "member": gene,
                "field": "l2g_score",
                "operation": "update",
                "value": "0.5",
                "reason": "a curator's correction of one candidate gene's score",
            }
        )
    built = compile_module(module, tmp_path / "out")
    assert built.success, built.errors
    table = pl.read_parquet(tmp_path / "out" / "locus_to_gene.parquet").filter(
        (pl.col("study_locus_id") == locus) & (pl.col("gene_id") == gene)
    )
    assert set(table["variant_key"]) == keys_per_pair[(locus, gene)]
    assert set(table["l2g_score"]) == {0.5}


def test_an_overlay_may_not_update_variant_key_and_an_insert_adds_a_second_members_row(
    module: Path, tmp_path: Path
) -> None:
    """`variant_key` is a key column the overlay does not key on: an update of it is refused, and an
    insert naming it matches on it, so a pair already present for one member takes a row for another."""
    result = enrich_opentargets(module, snapshot=SLICE)
    row = min(result.locus_to_gene, key=lambda r: (r.study_locus_id, r.gene_id))
    fieldnames = ["table", "subject", "member", "field", "operation", "value", "reason"]

    def overlay(rows: list[dict]) -> None:
        with (module / "overrides.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(
                    {
                        "table": "locus_to_gene.csv",
                        "subject": row.study_locus_id,
                        "member": row.gene_id,
                        "reason": "a curator's call",
                        **r,
                    }
                )

    overlay([{"field": "variant_key", "operation": "update", "value": "rs111033563"}])
    refused = compile_module(module, tmp_path / "refused")
    assert not refused.success
    assert any("part of locus_to_gene.csv's row key" in e for e in refused.errors)

    inserted = {"variant_key": "rs111033563", "dataset": row.dataset, "l2g_score": "0.25"}
    overlay([{"field": name, "operation": "insert", "value": value} for name, value in inserted.items()])
    built = compile_module(module, tmp_path / "out")
    assert built.success, built.errors
    table = pl.read_parquet(tmp_path / "out" / "locus_to_gene.parquet").filter(
        (pl.col("study_locus_id") == row.study_locus_id) & (pl.col("gene_id") == row.gene_id)
    )
    assert dict(zip(table["variant_key"], table["l2g_score"], strict=True)) == {
        row.variant_key: row.l2g_score,
        "rs111033563": 0.25,
    }
    # The insert is a fixed point through the round trip: lap 2 finds the row and adds nothing.
    reverse_module(tmp_path / "out", tmp_path / "spec2")
    again = compile_module(tmp_path / "spec2", tmp_path / "out2")
    assert again.success, again.errors
    m1 = json.loads((tmp_path / "out" / "manifest.json").read_text())
    m2 = json.loads((tmp_path / "out2" / "manifest.json").read_text())
    assert m1["artifact"]["digest"] == m2["artifact"]["digest"]


#: rs646776 (CELSR2/SORT1), the release's `1_109275908_C_T`: a member of far more sets than it leads.
RS646776_ROW = {
    **LEAD_ROW,
    "variant_key": "rs646776",
    "rsid": "rs646776",
    "chrom": "1",
    "start": "109275908",
    "ref": "C",
    "alts": "T",
}


def test_rs646776_gets_rows_for_every_set_it_is_a_member_of(tmp_path: Path) -> None:
    """Against a slice cut at run time from the whole release (skipped where it is not provisioned).

    Not in the committed slice: its 2,000-odd member sets carry some 300,000 coloc rows, too large to
    commit. The expected loci are read off the cut's member table and the release's L2G table, never copied.
    """
    full = resolve_opentargets_reference()
    if full is None or full.resolve() == SLICE.resolve():
        pytest.skip("the whole Open Targets snapshot is not provisioned on this machine")
    spec = tmp_path / "hfe"
    shutil.copytree(MODULE, spec)
    _append(spec / "resolution.csv", [RS646776_ROW])
    cut = tmp_path / "cut"
    subset_snapshot(full, cut, [("1", 109275908, "C", "T")])
    data = cut / "data"
    (variant_id,) = [vid for vid, keys in _keys_by_variant_id(spec, data).items() if "rs646776" in keys]
    sets = pl.read_parquet(data / "credible_sets.parquet")
    members = pl.read_parquet(data / "credible_set_members-*.parquet").filter(
        pl.col("variant_id") == variant_id
    )
    member_loci = set(members["study_locus_id"])
    led = set(sets.filter(pl.col("lead_variant_id") == variant_id)["study_locus_id"])
    assert led < member_loci, "a member of more sets than it leads"
    # Scored loci read off the WHOLE release's L2G table, so a cut that dropped some is caught too.
    scored = set(
        pl.scan_parquet(full / "data" / "l2g.parquet")
        .filter(pl.col("study_locus_id").is_in(list(member_loci)))
        .select("study_locus_id")
        .collect()["study_locus_id"]
    )
    assert scored - led, "the member-wide table holds scored sets the lead-only one did not"

    result = enrich_opentargets(spec, snapshot=cut, write=False)
    rows = [r for r in result.locus_to_gene if r.variant_key == "rs646776"]
    assert {r.study_locus_id for r in rows} == scored
    assert {r.study_locus_id for r in rows if r.lead_variant_id == variant_id} == led & scored


@pytest.mark.skipif(os.environ.get("JUST_DNA_NETWORK_TESTS") != "1", reason="network test (opt-in)")
def test_the_pinned_release_lists_its_five_datasets(tmp_path: Path) -> None:
    """The live leg: the FTP's https listing names parquet parts for every dataset the builder reads."""
    for dataset in OPENTARGETS_DATASETS:
        parts = list_parts(dataset, tmp_path)
        assert parts and all(p.startswith("part-") and p.endswith(".parquet") for p in parts)


def test_an_unreachable_ftp_is_this_lanes_error_not_httpx(tmp_path: Path) -> None:
    """`@client-exception-contract`: a transport failure leaves the builder as `OpenTargetsUnavailable`."""
    with pytest.raises(OpenTargetsUnavailable):
        list_parts("study", tmp_path, base_url="https://127.0.0.1:9")


# ── a resolution row that states no ALT (RM333, 2026-11-04) ─────────────────────────────────────────


def _blank_alts(spec: Path, key: str) -> None:
    """Rewrite `spec`'s `resolution.csv` with `key`'s `alts` empty, the authored rsID-only shape.

    Its VRS id goes too: a VA names one allele, and the compiler refuses one recorded against no ALT.
    """
    path = spec / "resolution.csv"
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames, rows = reader.fieldnames, list(reader)
    assert any(row["variant_key"] == key for row in rows)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            blank = {"alts": "", "vrs_id": "", "vrs_spec": ""}
            writer.writerow({**row, **blank} if row["variant_key"] == key else row)


def _locus_alleles(data: Path, chrom: str, position: int, ref: str) -> pl.DataFrame:
    """Every allele the snapshot holds at one `(chrom, position, ref)`, with its rsIDs."""
    return pl.read_parquet(data / "variants.parquet").filter(
        (pl.col("chrom") == chrom) & (pl.col("position") == position) & (pl.col("ref") == ref)
    )


def _facts(rows: list) -> list[dict]:
    return [r.model_dump(exclude={"fetched_at"}) for r in rows]


def test_the_slice_carries_every_allele_at_a_wanted_locus_with_its_rsids() -> None:
    """`subset_snapshot` keeps a wanted allele's siblings, so a no-ALT lookup sees the locus as the release does."""
    variants = pl.read_parquet(SLICE / "data" / "variants.parquet")
    assert variants.schema["rs_ids"] == pl.List(pl.Utf8)
    record = read_release(SLICE)
    assert record is not None
    wanted = {tuple(v.split("_", 3)) for v in record.model_dump()["subset_of"]}
    loci = {(c, int(p)) for c, p, _r, _a in wanted}
    held = set(variants.select("chrom", "position").iter_rows())
    assert held == loci, "the allele table holds the wanted positions and nothing else"
    assert variants.height > len(wanted), "some wanted locus has a sibling allele in the release"
    full = resolve_opentargets_reference()
    if full is None or full.resolve() == SLICE.resolve():
        return
    every = pl.read_parquet(full / "data" / "variants.parquet")
    if "rs_ids" not in every.columns:
        return
    on_release = every.join(
        variants.select("chrom", "position").unique(), on=["chrom", "position"], how="semi"
    ).sort("variant_id")
    assert on_release.equals(variants.sort("variant_id"))


def test_subset_snapshot_keeps_a_wanted_alleles_siblings_whole(tmp_path: Path) -> None:
    """Cut from the slice itself: wanting `6_26091590_G_T` keeps `G_A`, with its consequence rows too."""
    cut = tmp_path / "cut"
    subset_snapshot(SLICE, cut, [("6", 26091590, "G", "T")])
    variants = pl.read_parquet(cut / "data" / "variants.parquet")
    assert variants.sort("variant_id").equals(
        _locus_alleles(SLICE / "data", "6", 26091590, "G").sort("variant_id")
    )
    assert variants.height == 2
    (sibling,) = variants.filter(pl.col("alt") == "A")["variant_id"]
    on_slice = pl.read_parquet(SLICE / "data" / "consequences-00000.parquet").filter(
        pl.col("variant_id") == sibling
    )
    on_cut = pl.read_parquet(cut / "data" / "consequences-00000.parquet").filter(
        pl.col("variant_id") == sibling
    )
    assert on_slice.height and on_cut.equals(on_slice)


def test_a_row_with_no_alt_takes_the_one_allele_carrying_its_rsid(module: Path, tmp_path: Path) -> None:
    """rs1800562 with `alts` empty gets exactly the rows its authored allele gets, and is named as supplied.

    The expected rows are the pass's own answer for the same module with the allele stated, so the
    fallback is checked against the authored path rather than against a copied number.
    """
    (only,) = _locus_alleles(SLICE / "data", "6", 26092913, "G").iter_rows(named=True)
    assert only["rs_ids"] == ["rs1800562"], "one allele at the locus, carrying the rsID"
    stated = tmp_path / "stated"
    shutil.copytree(module, stated)
    authored = enrich_opentargets(stated, snapshot=SLICE, write=False)
    _blank_alts(module, "rs1800562")
    before = (module / "resolution.csv").read_bytes()

    result = enrich_opentargets(module, snapshot=SLICE)
    for name in ("locus_to_gene", "colocalisations", "consequences"):
        want = [r for r in _facts(getattr(authored, name)) if r["variant_key"] == "rs1800562"]
        assert want, f"the authored allele has {name} rows to compare against"
        assert [r for r in _facts(getattr(result, name)) if r["variant_key"] == "rs1800562"] == want
    assert "rs1800562" in result.asked and "rs1800562" not in result.not_in_release
    assert result.allele_supplied == ["rs1800562"]
    # Report, never repair: the supplied ALT is not written back.
    assert (module / "resolution.csv").read_bytes() == before


def test_a_row_with_no_alt_fills_the_posterior_through_the_supplied_allele(module: Path) -> None:
    """The fourth table: rs2075650's GWAS rows get the posterior its authored allele gets."""
    authored = enrich_opentargets(module, snapshot=SLICE, write=False)
    _blank_alts(module, "rs2075650")
    result = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert result.allele_supplied == ["rs2075650"]
    assert authored.posterior.filled > 0
    assert result.posterior == authored.posterior
    assert _facts(result.gwas_effects) == _facts(authored.gwas_effects)


def test_a_row_with_no_alt_at_a_locus_of_two_alleles_carrying_its_rsid_is_withheld(module: Path) -> None:
    """rs35589214 at 8:78193100 C: the release holds C>G and C>T, both under the rsID. Neither is picked."""
    alleles = _locus_alleles(SLICE / "data", "8", 78193100, "C")
    assert alleles.height == 2 and all("rs35589214" in ids for ids in alleles["rs_ids"].to_list())
    # First lap with the allele stated, so the key has rows a withheld lap must not shorten.
    _append(
        module / "resolution.csv",
        [
            {
                **LEAD_ROW,
                "variant_key": "rs35589214",
                "rsid": "rs35589214",
                "chrom": "8",
                "start": "78193100",
                "ref": "C",
                "alts": "T",
            }
        ],
    )
    first = enrich_opentargets(module, snapshot=SLICE)
    kept = {
        name: [r for r in _facts(getattr(first, name)) if r["variant_key"] == "rs35589214"]
        for name in ("locus_to_gene", "colocalisations", "consequences")
    }
    assert all(kept.values()), "the stated allele has rows in every table"
    _blank_alts(module, "rs35589214")

    result = enrich_opentargets(module, snapshot=SLICE)
    assert result.allele_unstated_withheld == ["rs35589214"]
    assert "rs35589214" not in result.asked and "rs35589214" not in result.allele_supplied
    assert "rs35589214" not in result.not_in_release, "withheld is not absent"
    # `@rederive-never-shortens`: the rows the stated lap wrote stay, and this lap added none.
    for name, rows in kept.items():
        assert [r for r in _facts(getattr(result, name)) if r["variant_key"] == "rs35589214"] == rows


def test_a_sibling_stating_no_rsid_is_a_candidate_not_a_refusal(module: Path) -> None:
    """rs773443949 at 6:26091590 G: the release states it on G>T and nothing on G>A, which ClinVar also
    names under it. The rsID-less allele may be the one, so the key is withheld rather than given G>T."""
    alleles = dict(_locus_alleles(SLICE / "data", "6", 26091590, "G").select("alt", "rs_ids").iter_rows())
    assert sorted(alleles) == ["A", "T"]
    assert alleles["T"] == ["rs773443949"] and alleles["A"] == []
    _append(
        module / "resolution.csv",
        [
            {
                **LEAD_ROW,
                "variant_key": "rs773443949",
                "rsid": "rs773443949",
                "chrom": "6",
                "start": "26091590",
                "ref": "G",
                "alts": "",
            }
        ],
    )
    result = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert result.allele_unstated_withheld == ["rs773443949"]
    assert not result.allele_supplied
    assert not any(
        r.variant_key == "rs773443949"
        for r in result.locus_to_gene + result.colocalisations + result.consequences
    )


def test_a_row_with_no_alt_and_an_rsid_no_allele_carries_is_not_in_the_release(module: Path) -> None:
    """Every allele at the locus carries another rsID: a definite no, the ordinary not-in-release answer."""
    alleles = _locus_alleles(SLICE / "data", "6", 26092913, "G")
    assert alleles.height >= 1 and all(ids and "rs7412" not in ids for ids in alleles["rs_ids"].to_list())
    _append(
        module / "resolution.csv",
        [
            {
                **LEAD_ROW,
                "variant_key": "6:26092913:G",
                "rsid": "rs7412",
                "chrom": "6",
                "start": "26092913",
                "ref": "G",
                "alts": "",
            }
        ],
    )
    result = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert "6:26092913:G" in result.asked and "6:26092913:G" in result.not_in_release
    assert not result.allele_unstated_withheld and not result.allele_supplied


def test_a_row_with_neither_alt_nor_rsid_is_withheld_and_counted(module: Path) -> None:
    """A position alone is not an identity (`@rsid-not-per-allele`), even where the release holds one allele."""
    assert _locus_alleles(SLICE / "data", "6", 26092913, "G").height == 1
    _append(
        module / "resolution.csv",
        [
            {
                **LEAD_ROW,
                "variant_key": "6:26092913:G",
                "rsid": "",
                "chrom": "6",
                "start": "26092913",
                "ref": "G",
                "alts": "",
            }
        ],
    )
    result = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert result.allele_unstated_no_rsid == ["6:26092913:G"]
    assert "6:26092913:G" not in result.asked and "6:26092913:G" not in result.not_in_release
    assert not any(r.variant_key == "6:26092913:G" for r in result.consequences + result.locus_to_gene)


def test_a_snapshot_without_rsids_cannot_answer_a_row_with_no_alt(module: Path, tmp_path: Path) -> None:
    """A snapshot built before `rs_ids`: nobody asked (best effort, counted), and strict refuses."""
    old = tmp_path / "old"
    shutil.copytree(SLICE, old)
    path = old / "data" / "variants.parquet"
    pl.read_parquet(path).drop("rs_ids").write_parquet(path)
    _blank_alts(module, "rs1800562")
    with pytest.raises(OpenTargetsError, match="carried rsIDs"):
        enrich_opentargets(module, snapshot=old, mode="strict", write=False)
    result = enrich_opentargets(module, snapshot=old, write=False)
    assert result.allele_unstated_unasked == ["rs1800562"]
    assert "rs1800562" not in result.asked and "rs1800562" not in result.not_in_release
    # Every authored allele is still answered on the old snapshot.
    assert any(r.variant_key == "rs2075650" for r in result.locus_to_gene)
    assert sum(result.posterior.__dict__.values()) == len(result.gwas_effects)
    # The unasked key's GWAS rows keep their values, counted as withheld rather than as not looked up.
    unasked_rows = [r for r in result.gwas_effects if r.variant_key == "rs1800562" and r.study_accession]
    assert unasked_rows and result.posterior.allele_withheld == len(unasked_rows)


def _slice_with_allele(tmp_path: Path, row: dict) -> Path:
    """A copy of the slice whose allele table holds one more row (every other byte is the release's)."""
    copy = tmp_path / "with_allele"
    shutil.copytree(SLICE, copy)
    path = copy / "data" / "variants.parquet"
    variants = pl.read_parquet(path)
    pl.concat([variants, pl.DataFrame([row], schema=variants.schema)]).write_parquet(path)
    return copy


def test_a_carrier_on_another_ref_at_the_position_withholds(module: Path, tmp_path: Path) -> None:
    """One rsID can name a SNV and an indel at one position: a carrier on another REF is a candidate too."""
    snapshot = _slice_with_allele(
        tmp_path,
        {
            "variant_id": "6_26092913_GA_G",
            "chrom": "6",
            "position": 26092913,
            "ref": "GA",
            "alt": "G",
            "rs_ids": ["rs1800562"],
        },
    )
    _blank_alts(module, "rs1800562")
    result = enrich_opentargets(module, snapshot=snapshot, write=False)
    assert result.allele_unstated_withheld == ["rs1800562"] and not result.allele_supplied
    # An rsID-less allele on another REF is not a candidate: the row's REF already excludes it.
    snapshot = _slice_with_allele(
        tmp_path / "b",
        {
            "variant_id": "6_26092913_GA_G",
            "chrom": "6",
            "position": 26092913,
            "ref": "GA",
            "alt": "G",
            "rs_ids": [],
        },
    )
    assert enrich_opentargets(module, snapshot=snapshot, write=False).allele_supplied == ["rs1800562"]


def test_one_allele_listed_under_two_ids_is_one_candidate(module: Path, tmp_path: Path) -> None:
    """The release keys some long alleles by an `OTVAR_` hash: the same (ref, alt) twice is one allele."""
    snapshot = _slice_with_allele(
        tmp_path,
        {
            "variant_id": "OTVAR_test",
            "chrom": "6",
            "position": 26092913,
            "ref": "G",
            "alt": "A",
            "rs_ids": ["rs1800562"],
        },
    )
    _blank_alts(module, "rs1800562")
    result = enrich_opentargets(module, snapshot=snapshot, write=False)
    assert result.allele_supplied == ["rs1800562"] and not result.allele_unstated_withheld


def test_the_merged_rsids_current_number_matches(module: Path) -> None:
    """A row whose rsID dbSNP merged away is matched by `rsid_current`, the number the release states."""
    _append(
        module / "resolution.csv",
        [
            {
                **LEAD_ROW,
                "variant_key": "rs000merged",
                "rsid": "rs1",
                "rsid_current": "rs1800562",
                "chrom": "6",
                "start": "26092913",
                "ref": "G",
                "alts": "",
            }
        ],
    )
    result = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert "rs000merged" in result.allele_supplied


def test_a_row_whose_rsid_is_itself_a_pick_is_withheld(module: Path) -> None:
    """`status="ambiguous"`: the back-fill picked the lowest of several rsIDs, so the rsID is no identity."""
    _blank_alts(module, "rs1800562")
    path = module / "resolution.csv"
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames, rows = reader.fieldnames, list(reader)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            if row["variant_key"] == "rs1800562":
                row = {**row, "status": "ambiguous", "rsid_alternates": "rs1800562,rs1800563"}
            writer.writerow(row)
    result = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert result.allele_unstated_withheld == ["rs1800562"] and not result.allele_supplied


def test_a_key_with_a_stated_allele_is_still_answered_beside_a_no_alt_row(module: Path) -> None:
    """A second, unanswerable row of a key does not take the key's stated allele down with it."""
    authored = enrich_opentargets(module, snapshot=SLICE, write=False)
    _append(
        module / "resolution.csv",
        [
            {
                **LEAD_ROW,
                "variant_key": "rs1800562",
                "rsid": "",
                "chrom": "6",
                "start": "26092913",
                "ref": "G",
                "alts": "",
                "locus_index": "1",
            }
        ],
    )
    result = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert result.allele_unstated_no_rsid == ["rs1800562"]
    for name in ("locus_to_gene", "consequences"):
        assert [r for r in _facts(getattr(result, name)) if r["variant_key"] == "rs1800562"] == [
            r for r in _facts(getattr(authored, name)) if r["variant_key"] == "rs1800562"
        ]
    assert result.posterior == authored.posterior


#: APOE ε, `reference_examples/apoe_epsilon`: two rsID-only rows. Its `resolution.csv` carried no `alts`
#: until the 0.8 regeneration against the split snapshot filled them, so the test empties them on its copy.
APOE = _ROOT / "reference_examples" / "apoe_epsilon"


def test_apoe_rows_with_no_alt_get_rows_against_the_whole_release(tmp_path: Path) -> None:
    """The motivating case, against the whole release (skipped where it is not provisioned with rsIDs).

    Not in the committed slice: rs429358 and rs7412 sit in some 4,400 GWAS credible sets with about
    150,000 coloc rows between them. The expected rows are read off the release at run time.
    """
    full = resolve_opentargets_reference()
    if full is None or full.resolve() == SLICE.resolve():
        pytest.skip("the whole Open Targets snapshot is not provisioned on this machine")
    variants = pl.read_parquet(full / "data" / "variants.parquet")
    if "rs_ids" not in variants.columns:
        pytest.skip("the provisioned Open Targets snapshot predates `rs_ids`; rebuild it")
    spec = tmp_path / "apoe"
    shutil.copytree(APOE, spec)
    with (spec / "resolution.csv").open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [{**r, "alts": "", "vrs_id": "", "vrs_spec": ""} for r in reader]
    with (spec / "resolution.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    assert rows and all(not r["alts"] and r["rsid"] for r in rows), "the example states no ALT"
    result = enrich_opentargets(spec, snapshot=full, write=False)
    for row in rows:
        carrying = variants.filter(
            (pl.col("chrom") == row["chrom"])
            & (pl.col("position") == int(row["start"]))
            & (pl.col("ref") == row["ref"])
            & pl.col("rs_ids").list.contains(row["rsid"])
        )
        (variant_id,) = carrying["variant_id"]
        transcripts = set(
            pl.scan_parquet(full / "data" / "consequences-*.parquet")
            .filter(pl.col("variant_id") == variant_id)
            .select("transcript")
            .collect()["transcript"]
        )
        assert transcripts
        assert {
            r.transcript for r in result.consequences if r.variant_key == row["variant_key"]
        } == transcripts
        loci = set(
            pl.scan_parquet(full / "data" / "credible_set_members-*.parquet")
            .filter(pl.col("variant_id") == variant_id)
            .select("study_locus_id")
            .collect()["study_locus_id"]
        )
        assert loci
        assert {r.study_locus_id for r in result.locus_to_gene if r.variant_key == row["variant_key"]} <= loci
        assert any(r.variant_key == row["variant_key"] for r in result.locus_to_gene)
        assert any(r.variant_key == row["variant_key"] for r in result.colocalisations)
    assert result.allele_supplied == sorted(r["variant_key"] for r in rows)


def test_an_author_corrects_the_supplied_allele_and_fills_a_withheld_site_through_the_overlay(
    module: Path, tmp_path: Path
) -> None:
    """`overrides.csv` reaches what the no-ALT fallback wrote, and what it withheld, compiled and round-tripped.

    rs1800562 (alts empty) is supplied by the release; one of its consequence rows is suppressed and
    another corrected. rs35589214 (alts empty) is withheld at a two-allele site, and the author, who
    knows the allele is C>T, inserts that allele's consequence and one of its L2G rows, values read off
    the slice.
    """
    _blank_alts(module, "rs1800562")
    _append(
        module / "resolution.csv",
        [
            {
                **LEAD_ROW,
                "variant_key": "rs35589214",
                "rsid": "rs35589214",
                "chrom": "8",
                "start": "78193100",
                "ref": "C",
                "alts": "",
            }
        ],
    )
    result = enrich_opentargets(module, snapshot=SLICE)
    assert result.allele_supplied == ["rs1800562"] and result.allele_unstated_withheld == ["rs35589214"]
    supplied = sorted(
        (r for r in result.consequences if r.variant_key == "rs1800562"), key=lambda r: r.transcript
    )
    assert len(supplied) >= 2
    gone, corrected = supplied[0], supplied[1]
    new_impact = min({"HIGH", "MODERATE", "LOW", "MODIFIER"} - {corrected.impact})
    (variant_id,) = _locus_alleles(SLICE / "data", "8", 78193100, "C").filter(pl.col("alt") == "T")[
        "variant_id"
    ]
    transcript, impact = _query(
        f"SELECT transcript, impact FROM cons WHERE variant_id = '{variant_id}' ORDER BY transcript LIMIT 1"
    )[0]
    locus, gene, score = _query(
        "SELECT l.study_locus_id, l.gene_id, l.l2g_score FROM l2g l JOIN members m USING (study_locus_id) "
        f"WHERE m.variant_id = '{variant_id}' ORDER BY l.study_locus_id, l.gene_id LIMIT 1"
    )[0]
    reason = "a curator's call"
    overlay = [
        ("consequences.csv", "rs1800562", gone.transcript, "", "suppress", ""),
        ("consequences.csv", "rs1800562", corrected.transcript, "impact", "update", new_impact),
        ("consequences.csv", "rs35589214", transcript, "dataset", "insert", result.dataset),
        ("consequences.csv", "rs35589214", transcript, "impact", "insert", impact),
        ("locus_to_gene.csv", locus, gene, "variant_key", "insert", "rs35589214"),
        ("locus_to_gene.csv", locus, gene, "dataset", "insert", result.dataset),
        ("locus_to_gene.csv", locus, gene, "l2g_score", "insert", str(score)),
    ]
    with (module / "overrides.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["table", "subject", "member", "field", "operation", "value", "reason"])
        writer.writerows([(*row, reason) for row in overlay])

    built = compile_module(module, tmp_path / "out")
    assert built.success, built.errors
    cons = pl.read_parquet(tmp_path / "out" / "consequences.parquet")
    c282y = cons.filter(pl.col("variant_key") == "rs1800562")
    assert gone.transcript not in set(c282y["transcript"])
    assert set(c282y.filter(pl.col("transcript") == corrected.transcript)["impact"]) == {new_impact}
    assert c282y.height == len(supplied) - 1
    filled = cons.filter(pl.col("variant_key") == "rs35589214")
    assert list(zip(filled["transcript"], filled["impact"], strict=True)) == [(transcript, impact)]
    l2g = pl.read_parquet(tmp_path / "out" / "locus_to_gene.parquet").filter(
        pl.col("variant_key") == "rs35589214"
    )
    assert list(zip(l2g["study_locus_id"], l2g["gene_id"], l2g["l2g_score"], strict=True)) == [
        (locus, gene, score)
    ]
    # The overlay is a fixed point through the round trip.
    reverse_module(tmp_path / "out", tmp_path / "spec2")
    again = compile_module(tmp_path / "spec2", tmp_path / "out2")
    assert again.success, again.errors
    m1 = json.loads((tmp_path / "out" / "manifest.json").read_text())
    m2 = json.loads((tmp_path / "out2" / "manifest.json").read_text())
    assert m1["artifact"]["digest"] == m2["artifact"]["digest"]
    assert m1["content_signature"] == m2["content_signature"]


def test_a_statistic_whose_method_the_release_left_empty_is_withheld_not_a_crash(
    module: Path, tmp_path: Path
) -> None:
    """RM366: both tables refuse a statistic with no method, so the pass withholds the number instead.

    26.09 states a method on every credible set and every colocalisation (measured on the full release),
    so the slice is copied and its method columns emptied. The rows the pass writes keep everything else
    the release said; only the statistics that need the missing method are left empty.
    """
    complete = enrich_opentargets(module, snapshot=SLICE, write=False)
    assert any(r.posterior_probability is not None for r in complete.gwas_effects)
    assert any(r.h4 is not None or r.clpp is not None for r in complete.colocalisations)

    blank = tmp_path / "no_method"
    shutil.copytree(SLICE, blank)
    data = blank / "data"
    sets = pl.read_parquet(data / "credible_sets.parquet")
    sets.with_columns(pl.lit(None, dtype=pl.Utf8).alias("fine_mapping_method")).write_parquet(
        data / "credible_sets.parquet"
    )
    for part in sorted(data.glob("colocalisations-*.parquet")):
        frame = pl.read_parquet(part)
        frame.with_columns(pl.lit(None, dtype=pl.Utf8).alias("method")).write_parquet(part)

    result = enrich_opentargets(module, snapshot=blank, write=False)
    assert all(r.posterior_probability is None and r.fine_mapping_method is None for r in result.gwas_effects)
    # Counted as its own reason, never as "not in the set": the variant is in it, the method is not.
    assert result.posterior.method_missing == complete.posterior.filled
    assert result.posterior.not_in_credible_set == complete.posterior.not_in_credible_set
    assert {(r.study_locus_id, r.right_study_locus_id, r.variant_key) for r in result.colocalisations} == {
        (r.study_locus_id, r.right_study_locus_id, r.variant_key) for r in complete.colocalisations
    }
    assert all(r.method is None and r.h4 is None and r.clpp is None for r in result.colocalisations)


# ── a snapshot not read whole answers nothing it did not read (RM361) ───────────────────────────────

#: The rows each source dataset feeds in the snapshot, as `(parquet glob, key column)`: what an unread
#: part of that dataset would leave out. `study` feeds only cells of a coloc row, never a whole row.
_FEEDS: dict[str, list[tuple[str, str]]] = {
    "variant": [("variants.parquet", "variant_id"), ("consequences-*.parquet", "variant_id")],
    "credible_set": [("credible_set_members-*.parquet", "variant_id")],
    "l2g_prediction": [("l2g.parquet", "study_locus_id")],
    "colocalisation": [("colocalisations-*.parquet", "study_locus_id")],
    "study": [],
}


def _facts_of(spec: Path, name: str) -> list[dict]:
    path = spec / name
    if not path.exists():
        return []
    return [
        {k: v for k, v in row.items() if k != "fetched_at"} for row in csv.DictReader(path.open(newline=""))
    ]


def _unread(tmp_path: Path, dataset: str, parts_total: dict | None) -> Path:
    """The slice as a snapshot whose `dataset` lost a part: rs1800562's rows it fed are gone, and
    `release.json` says so (`parts_total`), or says nothing at all (`None`)."""
    snapshot = tmp_path / f"unread-{dataset}"
    shutil.copytree(SLICE, snapshot)
    ids = {i for (i,) in _query("SELECT variant_id FROM variants WHERE list_contains(rs_ids, 'rs1800562')")}
    loci = {
        locus
        for (locus,) in _query(
            "SELECT study_locus_id FROM members WHERE variant_id IN ('" + "','".join(ids) + "')"
        )
    }
    for glob, column in _FEEDS[dataset]:
        for path in (snapshot / "data").glob(glob):
            frame = pl.read_parquet(path)
            frame.filter(
                ~pl.col(column).is_in(sorted(ids if column == "variant_id" else loci))
            ).write_parquet(path)
    record = read_release(snapshot)
    assert record is not None
    fields = record.model_dump(exclude_none=True)
    fields.pop("parts_total", None)
    if parts_total is not None:
        fields["parts_total"] = parts_total
    write_release(snapshot, SnapshotRelease(**fields))
    return snapshot


def test_reads_names_every_owned_table_and_every_dataset() -> None:
    from just_dna_enricher.opentargets import OWNED_TABLES, READS

    assert set(READS) == {name for name, _model, _layer in OWNED_TABLES} | {"gwas_effects.csv"}
    assert set().union(*READS.values()) == set(OPENTARGETS_DATASETS) == set(_FEEDS)


@pytest.mark.parametrize("record", ["partial", "unstated"])
@pytest.mark.parametrize("dataset", OPENTARGETS_DATASETS)
def test_a_row_in_an_unread_part_survives_a_best_effort_run(
    module: Path, tmp_path: Path, dataset: str, record: str
) -> None:
    """Before RM361 the keys an unread part held were answered as absent: their L2G, coloc and
    consequence rows were dropped and a filled posterior was nulled. Every row an earlier run wrote
    from the whole release survives a run against a snapshot missing one of its datasets' parts."""
    enrich_opentargets(module, snapshot=SLICE)
    names = ("locus_to_gene.csv", "colocalisations.csv", "consequences.csv", "gwas_effects.csv")
    before = {name: _facts_of(module, name) for name in names}
    assert all(before[name] for name in names)
    read = read_release(SLICE).model_dump()["parts_read"]
    totals = {**read, dataset: read[dataset] + 1} if record == "partial" else None
    result = enrich_opentargets(module, snapshot=_unread(tmp_path, dataset, totals))
    for name in names[:3]:
        after = _facts_of(module, name)
        assert all(row in after for row in before[name]), f"{name} lost a row from an unread {dataset} part"
    posterior = {
        (r["variant_key"], r["study_accession"], r["posterior_probability"])
        for r in before["gwas_effects.csv"]
    }
    assert posterior == {
        (r["variant_key"], r["study_accession"], r["posterior_probability"])
        for r in _facts_of(module, "gwas_effects.csv")
    }
    if dataset == "variant":
        assert "rs1800562" in result.not_read and "rs1800562" not in result.not_in_release


def test_a_snapshot_read_whole_still_answers_absent(module: Path) -> None:
    """The guard withholds only where the record cannot vouch for the read: over the whole slice a key
    the release lacks is still `not_in_release`, and nothing is `not_read`."""
    result = enrich_opentargets(module, snapshot=SLICE)
    assert result.not_read == [] and result.posterior.not_read == 0


def test_strict_refuses_a_snapshot_that_cannot_say_whether_it_is_whole(module: Path, tmp_path: Path) -> None:
    with pytest.raises(OpenTargetsError, match="does not record how many"):
        enrich_opentargets(module, snapshot=_unread(tmp_path, "study", None), mode="strict")


# ── RM373: the licence rows name the lane's release, and a later release re-labels them ────────


def _datasets(spec: Path) -> dict[str, str | None]:
    path = sidecar_path(spec, "sources.csv", error=RuntimeError)
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    assert not errors
    return {r.layer: r.dataset for r in rows if r.source == "opentargets"}


def test_rm373_every_licence_row_names_the_lanes_release_and_a_rerun_against_a_newer_one_relabels(
    module: Path, tmp_path: Path
) -> None:
    """`merge_sources_file` never clobbers, so a re-run against 26.12 used to keep saying 26.09.

    Every row the second run answers is 26.12's, so the label moves; a row it kept would withhold it.
    The posterior on `gwas_effects.csv` comes back the same, so that table is not rewritten and its
    licence row keeps naming the release that wrote it, which is still true (`@empty-work-is-a-path`).
    """
    enrich_opentargets(module, snapshot=SLICE)
    first = _datasets(module)
    assert first and set(first.values()) == {LANES_BY_NAME["opentargets"].release_label(SLICE)}

    newer = tmp_path / "opentargets_26_12"
    shutil.copytree(SLICE, newer)
    record = read_release(newer)
    assert record is not None
    write_release(newer, record.model_copy(update={"dataset": "opentargets_26.12"}))
    enrich_opentargets(module, snapshot=newer)
    assert _datasets(module) == {
        layer: first[layer] if layer == "gwas_effect" else "opentargets_26.12" for layer in first
    }


def test_rm373_a_row_this_run_did_not_answer_withholds_the_label(module: Path) -> None:
    """A kept row's release is not known: the recorded label may be a pre-0.8 first run's, kept forever."""
    enrich_opentargets(module, snapshot=SLICE)
    path = sidecar_path(module, "locus_to_gene.csv", error=RuntimeError)
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames, first = reader.fieldnames, next(reader)
    _append(path, [{**first, "variant_key": "rs999999999"}])
    assert fieldnames is not None
    enrich_opentargets(module, snapshot=SLICE)
    datasets = _datasets(module)
    assert datasets["locus_to_gene"] is None
    assert datasets["consequence"] == LANES_BY_NAME["opentargets"].release_label(SLICE)
