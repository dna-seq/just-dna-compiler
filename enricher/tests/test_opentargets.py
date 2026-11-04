"""The Open Targets lane and its pass (RM333, RM239, RM236), over a slice cut from the real 26.09 release.

The slice (`assets/opentargets_slice/`) is `opentargets_build.subset_snapshot` run on a full build of the
release (`probes/LANES_0_8.md` § built) for the alleles of `reference_examples/hfe_hemochromatosis`.
`subset_snapshot` keeps exactly the rows the pass reads for those alleles, so the pass over the slice
answers as it does over the whole release for that module. Every expected value below is computed at
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
