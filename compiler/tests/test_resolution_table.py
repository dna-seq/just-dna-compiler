"""The source-independent resolution table (0.5) — the pure `resolve_from_table` path, the
reverse-emitted `resolution.csv`, offline round-trip / digest parity, the fact-hash's
producer-stability, and the strict/best-effort manifest flags.

No network and no 190 MB reference: the path-2 (DuckDB) side uses a tiny synthetic
`ensembl_variations` parquet (the same injectable shape `test_resolver_unit.py` uses), and the path-1
side consumes a `resolution.csv` — hand-authored or reverse-emitted.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.resolution import resolve_from_table
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_STUDIES = "rsid,pmid\nrs1801133,9545397\n"


def _v(**kw) -> VariantRow:
    return VariantRow(genotype="A/G", state="neutral", conclusion="t", **kw)


def _spec(d: Path, variants: str, resolution: str | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(variants, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    if resolution is not None:
        (d / "resolution.csv").write_text(resolution, encoding="utf-8")
    return d


def _cache(tmp_path: Path) -> Path:
    """A synthetic injectable Ensembl reference: rs1801133 (1:1), rs429358 (for a position-only
    row → rsid), and rs999 mapping to TWO loci (a one-to-many expansion).

    Both rs999 loci are `A>T` so both can host the authored `A/T` genotype. That is deliberate: since
    0.5 a locus whose alleles cannot host the genotype is dropped from the expansion, so a fixture
    with one incompatible locus would quietly stop exercising expansion at all (and, because the
    deprecated DuckDB path applies the same filter, would still agree on the digest while testing
    nothing)."""
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs1801133", "rs429358", "rs999", "rs999"],
            "chrom": ["1", "19", "5", "6"],
            "start": [11856377, 44908683, 500, 600],
            "ref": ["G", "T", "A", "A"],
            "alt": ["A", "C", "T", "T"],
        }
    ).write_parquet(data / "chr.parquet")
    return tmp_path / "cache"


# ── resolve_from_table unit semantics (no cache, no network) ──────────────────────────────────


def test_resolve_from_table_fills_expands_and_verifies() -> None:
    v_fill = _v(rsid="rs1801133")  # rsid-only → 1:1 fill
    v_need_rsid = _v(chrom="19", start=44908683, ref="T")  # position-only → rsid fill
    v_multi = _v(rsid="rs999")  # rsid-only → expand to two coord-keyed rows
    table = {
        "rs1801133": [ResolutionRow(variant_key="rs1801133", rsid="rs1801133", chrom="1", start=11856377, ref="G", alts="A")],
        "19:44908683:T": [ResolutionRow(variant_key="19:44908683:T", rsid="rs429358", chrom="19", start=44908683, ref="T")],
        "rs999": [
            ResolutionRow(variant_key="rs999", rsid="rs999", chrom="6", start=600, ref="C", locus_index=1),
            ResolutionRow(variant_key="rs999", rsid="rs999", chrom="5", start=500, ref="A", locus_index=0),
        ],
    }
    outcome = resolve_from_table([v_fill, v_need_rsid, v_multi], table)
    patched, warnings = outcome.variants, outcome.warnings

    by_key = {p.variant_key: p for p in patched}
    # 1:1 fill keeps the frozen rsid key, fills the coordinate
    assert (by_key["rs1801133"].chrom, by_key["rs1801133"].start, by_key["rs1801133"].ref) == ("1", 11856377, "G")
    # position-only fills the rsid, keeps the frozen coordinate key (no flip)
    assert by_key["19:44908683:T"].rsid == "rs429358"
    # one-to-many expands to two distinct coord-keyed rows, ordered by locus_index (5:500 before 6:600)
    expanded = [p for p in patched if p.rsid == "rs999"]
    assert [p.variant_key for p in expanded] == ["5:500:A", "6:600:C"]
    assert any("maps to 2 loci" in w for w in warnings)


def test_resolve_from_table_warns_on_missing_and_skips_non_grch38() -> None:
    v = _v(rsid="rs1801133")
    warnings = resolve_from_table([v], {}).warnings  # empty table
    assert any("not found in resolution table" in w for w in warnings)

    skip = resolve_from_table([v], {}, genome_build="GRCh37").warnings
    assert any("GRCh38-bound" in w for w in skip)


def test_rows_with_no_rsid_are_one_counted_warning_naming_their_coordinates() -> None:
    """Coordinate-authored rows the table knows no rsID for: one line, and it names *places*.

    Two defects in the same message. It was emitted per row — 26 of them in
    `reference_examples/pathogenic_clinvar/`, out of 37 warnings, burying the nine expansion findings
    and a duplicate-citation error. And it printed `variant_key`, which since 0.5 is a
    `ga4gh:VA.…` digest for a resolved substitution, so a third of those lines read "Position
    ga4gh:VA.aseiElOGc6FKVcLTpib-L1y4s1dwiYE2" — a content-addressed identity announced as a position,
    which an author cannot find in their own CSV.
    """
    rows = [
        _v(chrom="11", start=5_227_002, ref="T", alts="A"),
        _v(chrom="11", start=5_226_931, ref="TGCCCAGG", alts="T"),
        _v(chrom="1", start=11_796_321, ref="G", alts="A"),
        _v(chrom="6", start=26_092_913, ref="G", alts="A"),
    ]
    # A substitution row's frozen key really is a VA — that is what made the old message wrong.
    assert rows[0].variant_key.startswith("ga4gh:VA.")

    warnings = resolve_from_table(rows, {}).warnings
    no_rsid = [w for w in warnings if "no rsid in the resolution table" in w]

    assert len(no_rsid) == 1, warnings
    message = no_rsid[0]
    assert "4 coordinate-authored row(s)" in message
    assert "11:5227002 T>A" in message and "11:5226931 TGCCCAGG>T" in message
    assert "ga4gh:VA." not in message
    assert "and 1 more" in message, "the tail is counted, not listed"


# ── offline round-trip / digest parity: DuckDB (path 2) vs resolution.csv (path 1) ────────────


def test_deprecated_ensembl_cache_path_warns(tmp_path: Path) -> None:
    # The DuckDB `ensembl_cache` path is deprecated (removed at 1.0) and routes to just-dna-enricher;
    # the surface still works but must announce itself.
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c1\n")
    with pytest.warns(DeprecationWarning, match="deprecated"):
        result = compile_module(spec, tmp_path / "out", ensembl_cache=_cache(tmp_path))
    assert result.success, result.errors


def test_digest_parity_and_offline_roundtrip(tmp_path: Path) -> None:
    variants = (
        "rsid,chrom,start,ref,genotype,state,conclusion,gene\n"
        "rs1801133,,,,A/G,risk,c1,MTHFR\n"          # rsid-only → 1:1 fill
        ",19,44908683,T,C/T,risk,c2,APOE\n"          # position-only → rsid fill (rsid dropped on reverse)
        "rs999,,,,A/T,risk,c3,X\n"                    # rsid-only → one-to-many expansion (rsid dropped)
    )
    spec = _spec(tmp_path / "spec", variants)

    # Path 2: resolve against the injected synthetic DuckDB reference.
    out2 = tmp_path / "out_duckdb"
    r2 = compile_module(spec, out2, ensembl_cache=_cache(tmp_path))
    assert r2.success, r2.errors
    digest_duckdb = r2.manifest.artifact.digest
    assert r2.manifest.compilation.fully_resolved is True
    assert r2.manifest.compilation.resolution_mode == "best_effort"
    assert r2.manifest.compilation.resolution_signature is None  # path 2 has no resolution.csv

    # Reverse emits variants.csv + resolution.csv (the resolved facts).
    reversed_spec = tmp_path / "reversed"
    reverse_module(out2, reversed_spec)
    assert (reversed_spec / "resolution.csv").is_file()

    # Path 1: recompile from the reverse-emitted spec with NO reference and NO network.
    out1 = tmp_path / "out_table"
    r1 = compile_module(reversed_spec, out1, ensembl_cache=None)
    assert r1.success, r1.errors

    # The core claim: identical artifact.digest — the rework is a provisioning change, not a schema
    # break, and the round-trip is fully offline (the resolved rsids dropped from variants.csv on a
    # coord-keyed row are restored from resolution.csv).
    assert r1.manifest.artifact.digest == digest_duckdb
    assert r1.manifest.compilation.fully_resolved is True
    assert r1.manifest.compilation.resolution_signature is not None
    assert r1.manifest.compilation.resolution_sources == ["reversed"]

    # The restored rsids actually match (not just the digest): every reversed variant resolved.
    w1 = pl.read_parquet(out1 / "weights.parquet")
    w2 = pl.read_parquet(out2 / "weights.parquet")
    assert set(w1["rsid"].to_list()) == set(w2["rsid"].to_list()) == {"rs1801133", "rs429358", "rs999"}


# ── the fact-hash is producer-stable and out of manifest.inputs ───────────────────────────────


def test_resolution_signature_ignores_provenance_and_order(tmp_path: Path) -> None:
    header = "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
    facts = "rs1801133,rs1801133,1,11856377,G,A,GRCh38,0,{src},resolved,{ts}\n"

    # Same fact, different provenance (source/timestamp) → identical resolution_signature.
    a = compile_module(
        _spec(tmp_path / "a", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c1\n",
              header + facts.format(src="cache", ts="2026-01-01T00:00:00Z")),
        tmp_path / "outa", ensembl_cache=None,
    )
    b = compile_module(
        _spec(tmp_path / "b", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c1\n",
              header + facts.format(src="ensembl-graphql", ts="2026-09-09T09:09:09Z")),
        tmp_path / "outb", ensembl_cache=None,
    )
    assert a.success and b.success
    assert a.manifest.compilation.resolution_signature == b.manifest.compilation.resolution_signature
    # provenance differs, so the sources list differs even though the fact-hash matches
    assert a.manifest.compilation.resolution_sources == ["cache"]
    assert b.manifest.compilation.resolution_sources == ["ensembl-graphql"]

    # A fact edit (coordinate) DOES change the signature.
    c = compile_module(
        _spec(tmp_path / "c", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c1\n",
              header + "rs1801133,rs1801133,1,11856378,G,A,GRCh38,0,cache,resolved,\n"),
        tmp_path / "outc", ensembl_cache=None,
    )
    assert c.manifest.compilation.resolution_signature != a.manifest.compilation.resolution_signature


def test_resolution_csv_absent_from_inputs_and_content_signature_unchanged(tmp_path: Path) -> None:
    positioned = (
        "rsid,chrom,start,ref,genotype,state,conclusion\n"
        "rs1801133,1,11856377,G,A/G,risk,c1\n"
    )
    resolution = (
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
        "rs1801133,rs1801133,1,11856377,G,A,GRCh38,0,manual,resolved,\n"
    )
    # Without resolution.csv
    without = compile_module(_spec(tmp_path / "wo", positioned), tmp_path / "owo", resolve_with_ensembl=False)
    # With a resolution.csv added (same authored data)
    with_ = compile_module(_spec(tmp_path / "wi", positioned, resolution), tmp_path / "owi", ensembl_cache=None)
    assert without.success and with_.success

    # content_signature is the authored-only identity — blind to resolution.csv.
    assert without.manifest.content_signature == with_.manifest.content_signature
    # resolution.csv is hashed only via resolution_signature, never as a raw-bytes manifest input.
    input_names = {e.name for e in with_.manifest.inputs}
    assert "resolution.csv" not in input_names
    assert "variants.csv" in input_names  # the canonical single-author file still is
    assert with_.manifest.compilation.resolution_signature is not None


# ── strict vs best-effort, driven entirely by the resolution table ────────────────────────────


def test_strict_and_best_effort_flags_via_table(tmp_path: Path) -> None:
    variants = (
        "rsid,genotype,state,conclusion\n"
        "rs1801133,A/G,risk,c1\n"
        "rs99999999,C/T,risk,c2\n"  # not in the partial table
    )
    partial = (
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
        "rs1801133,rs1801133,1,11856377,G,A,GRCh38,0,manual,resolved,\n"
    )
    # Each genotype above sits inside its row's own {ref} ∪ alts — `rs1801133` is G>A with genotype
    # A/G, `rs99999999` is C>T with genotype C/T. That agreement is not decoration: `strict=True`
    # below now also runs `_check_allele_membership`, so a genotype naming an allele its locus does
    # not have would fail this compile for a reason the test is not about.
    complete = partial + "rs99999999,rs99999999,2,222,C,T,GRCh38,0,manual,resolved,\n"

    # best-effort with a partial table: succeeds but is not fully resolved (the half-baked product).
    be = compile_module(_spec(tmp_path / "be", variants, partial), tmp_path / "obe", ensembl_cache=None)
    assert be.success
    assert be.manifest.compilation.resolution_mode == "best_effort"
    assert be.manifest.compilation.fully_resolved is False

    # strict with the same partial table: fails before any parquet is written.
    st = compile_module(_spec(tmp_path / "st", variants, partial), tmp_path / "ost", ensembl_cache=None, strict=True)
    assert not st.success
    assert any("unresolved genomic positions" in e for e in st.errors)
    assert not (tmp_path / "ost" / "weights.parquet").exists()

    # strict with a complete table: succeeds and is fully resolved.
    ok = compile_module(_spec(tmp_path / "ok", variants, complete), tmp_path / "ook", ensembl_cache=None, strict=True)
    assert ok.success, ok.errors
    assert ok.manifest.compilation.resolution_mode == "strict"
    assert ok.manifest.compilation.fully_resolved is True
