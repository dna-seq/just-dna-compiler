"""Each declared snapshot key answers under the spelling its reader accepts (RM454)."""

import csv
from pathlib import Path

import duckdb
import pytest
from just_dna_enricher import clinvar_build, key_compare
from just_dna_enricher.ensembl_rsid_index_build import build_rsid_index
from just_dna_enricher.remote import RemoteSnapshots, SnapshotRouteUnavailable
from just_dna_enricher.resolver import lookup_loci
from just_dna_format.spelling import gene_key

_ASSETS = Path(__file__).resolve().parents[2] / "assets"


@pytest.fixture(scope="module")
def fixture_keys(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """One real key of each kind, from the ClinVar, PharmGKB and Open Targets slices."""
    root = tmp_path_factory.mktemp("clinvar_keys")
    clinvar_build.build_snapshot(_ASSETS / "clinvar_GRCh38_slice.vcf.gz", root)
    with duckdb.connect() as con:
        cursor = con.execute(
            "SELECT rsid, chrom, start, ref, alt, variation_id FROM read_parquet(?) "
            "WHERE rsid IS NOT NULL AND variation_id IS NOT NULL ORDER BY ALL LIMIT 1",
            [str(root / "data" / "*.parquet")],
        )
        keys = {d[0]: str(v) for d, v in zip(cursor.description, cursor.fetchone(), strict=True)}
        keys["variant_id"] = con.execute(
            "SELECT min(variant_id) FROM read_parquet(?)",
            [str(_ASSETS / "opentargets_slice" / "data" / "variants.parquet")],
        ).fetchone()[0]
    with (_ASSETS / "clinpgx_annotations_slice" / "summary_annotations.tsv").open() as f:
        annotation = next(row for row in csv.DictReader(f, delimiter="\t") if row["Gene"] == "SLCO1B1")
    keys.update(gene=annotation["Gene"], drug=annotation["Drug(s)"])
    return keys


@pytest.mark.parametrize(
    ("lane", "table", "column"),
    [
        (lane, table, column)
        for lane, tables in key_compare.KEY_COMPARES.items()
        for table, columns in tables.items()
        for column in columns
    ],
)
def test_every_declared_compare_matches_a_fixture_key(
    lane: str, table: str, column: str, fixture_keys: dict[str, str]
) -> None:
    compare = key_compare.KEY_COMPARES[lane][table][column]
    assert compare.parameter([None]) == []
    # Long s casefolds to s but lower() leaves it alone. Keep it in the stored member,
    # where folding only the caller's spelling cannot rescue the lookup.
    if column in {"gene", "genes", "symbol"}:
        gene = fixture_keys["gene"]
        stored = f"\t{gene.replace('S', 'ſ')}\u00a0"
        canonical, raw = gene_key(gene), f" {gene.title()}\t"
        if compare.separator:
            stored = f"KLC1{compare.separator}{stored}"
    elif column in {"rsid", "id"}:
        stored = canonical = fixture_keys["rsid"]
        raw = f"\t{canonical.upper()} "
    elif column == "chrom":
        stored = canonical = fixture_keys["chrom"]
        raw = f"\tchr{canonical.lower()} "
    elif column == "drug":
        stored = canonical = fixture_keys["drug"]
        raw = f" {canonical.title()}\t"
    elif column == "variant_id":
        stored = canonical = fixture_keys["variant_id"]
        raw = f" {canonical}\t"
    else:
        assert compare.exact
        stored = canonical = raw = fixture_keys["start" if column in {"pos", "position"} else column]
    with duckdb.connect() as con:
        sql = f"SELECT cell FROM (SELECT unnest(?::VARCHAR[]) AS cell) WHERE {compare.predicate('cell')}"
        for key in [canonical, raw]:
            found = con.execute(sql, [[stored, None], compare.parameter([None, key])]).fetchall()
            assert found == [(stored,)]


def test_folded_sql_uses_the_formats_unicode_key() -> None:
    """Case folding may expand one character. Interior whitespace remains significant."""
    cells = ["\u2003Straße\t", " STRASSE ", "Stra ße", "\tİ", "I\u0307", "Σ", "ς", None]
    compare = key_compare.lane_compare("constraint", "gnomad_constraint", "gene")
    sql = f"SELECT cell FROM unnest(?::VARCHAR[]) WITH ORDINALITY t(cell, i) WHERE {compare.predicate('cell')} ORDER BY i"
    with duckdb.connect() as con:
        for raw in cells[:-1]:
            expected = [cell for cell in cells if cell is not None and gene_key(cell) == gene_key(raw)]
            assert [
                cell for (cell,) in con.execute(sql, [cells, compare.parameter([raw])]).fetchall()
            ] == expected


def test_rsid_spelling_reaches_the_pinned_index(
    tmp_path: Path, ensembl_split_core, no_ambient_caches
) -> None:
    core = ensembl_split_core(tmp_path / "core")
    index = build_rsid_index(core, tmp_path / "index").out_dir
    rsid = "rs1555461597"
    expected = lookup_loci(core, [rsid], [])[0][rsid]
    aliases = [f"\t{rsid.upper()} ", rsid[2:]]
    got, _, warnings = lookup_loci(core, aliases, [], rsid_index=index)
    assert got == dict.fromkeys(aliases, expected)
    assert not warnings


@pytest.mark.parametrize(("lane", "table"), [("constraint", "gnomad_constraint"), ("clinvar", "clinvar")])
def test_a_proxy_only_folded_gene_lookup_withholds_the_answer(lane: str, table: str) -> None:
    with (
        RemoteSnapshots(proxy_url="http://127.0.0.1:9", huggingface=False) as holder,
        pytest.raises(SnapshotRouteUnavailable) as refused,
    ):
        holder.lookup(lane, table, {"gene": ["A1BG"]})
    assert refused.value.route is None
    assert str(refused.value) == (
        f"{lane}: no remote route was asked: the registry's proxy compares a whole cell exactly, and "
        f"{lane}/{table} compares gene by gene_key, as its local reader does, so the proxy is not asked, "
        "and Hugging Face is off"
    )
