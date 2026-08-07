"""ClinVar reference builder + resolver-link tests (network-free).

The build side runs against a small committed slice of the real ClinVar GRCh38 VCF
(``assets/clinvar_GRCh38_slice.vcf.gz``); expected values are parsed from that same VCF at runtime,
never hardcoded. The resolver/chain side uses synthetic parquet caches (the established pattern in
``test_enrich``) so multi-loci and cross-cache scenarios are deterministic. A full build against the
real local VCF is ``@integration`` (skipped when absent).
"""

import gzip
import re
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import _load_csv_rows, compile_module
from just_dna_enricher import clinvar
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.enrich import enrich
from just_dna_enricher.locations import resolve_clinvar_reference
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import VALID_CLIN_SIG

FIXTURE = Path(__file__).parents[2] / "assets" / "clinvar_GRCh38_slice.vcf.gz"
REAL_VCF = Path("/data/just-dna-cache/clinvar/clinvar_GRCh38.vcf.gz")

_EXPECTED_COLUMNS = {
    "chrom", "start", "ref", "alt", "rsid", "variation_id", "allele_id", "gene", "genes",
    "clin_sig", "clin_sig_raw", "review_status", "review_stars", "condition",
    "molecular_consequence", "variant_type", "origin",
}

_ACGT = re.compile(r"^[ACGT]+$")
_VALID_CHROMS = frozenset([str(i) for i in range(1, 23)] + ["X", "Y", "MT"])

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────


def _parse_fixture_alleles(vcf: Path) -> set[tuple[str, int, str, str]]:
    """Independent parse of the fixture: the (chrom, pos, ref, alt) ACGT alleles the builder emits.

    This is the runtime ground truth — the builder's output must equal this set, not a hardcoded one.
    """
    out: set[tuple[str, int, str, str]] = set()
    with gzip.open(vcf, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            chrom = cols[0].removeprefix("chr")
            if chrom in ("M", "MT"):
                chrom = "MT"
            if chrom not in _VALID_CHROMS:
                continue
            pos, ref, alt_field = int(cols[1]), cols[3].upper(), cols[4]
            for alt in alt_field.split(","):
                alt = alt.upper()
                if (
                    _ACGT.match(ref) and _ACGT.match(alt) and ref != alt
                    and len(ref) <= 50 and len(alt) <= 50
                ):
                    out.add((chrom, pos, ref, alt))
    return out


def _read_all(out_dir: Path) -> pl.DataFrame:
    parts = sorted((out_dir / "data").glob("*.parquet"))
    return pl.concat([pl.read_parquet(p) for p in parts])


def _spec(d: Path, variants: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(variants, encoding="utf-8")
    (d / "studies.csv").write_text("rsid,pmid\nrs334,29165669\n", encoding="utf-8")
    return d


def _resolution_rows(spec: Path) -> list[ResolutionRow]:
    rows, errors, _ = _load_csv_rows(spec / "resolution.csv", ResolutionRow, "resolution.csv")
    assert not errors, errors
    return rows


def _ensembl_cache(tmp_path: Path) -> Path:
    """Synthetic Ensembl cache: rs334 with alts A|C|G (all dbSNP alleles) — deliberately a superset
    of ClinVar's submitted A,G, so the winning source visibly changes the compiled `alts`."""
    data = tmp_path / "ens" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs334", "rs334", "rs334"],
            "chrom": ["11", "11", "11"],
            "start": [5227002, 5227002, 5227002],
            "ref": ["T", "T", "T"],
            "alt": ["A", "C", "G"],
        }
    ).write_parquet(data / "chr.parquet")
    return tmp_path / "ens"


def _synthetic_clinvar(tmp_path: Path, rows: dict) -> Path:
    data = tmp_path / "cvsyn" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(rows).write_parquet(data / "chr.parquet")
    return tmp_path / "cvsyn"


# ── build correctness (against the committed real slice) ───────────────────────────────────────


def test_build_columns_and_facts(tmp_path: Path) -> None:
    result = build_snapshot(FIXTURE, tmp_path / "cv")
    df = _read_all(tmp_path / "cv")

    assert set(df.columns) == _EXPECTED_COLUMNS
    # Emitted alleles equal the independent parse (runtime ground truth), and every row is accounted.
    emitted = {(r["chrom"], r["start"], r["ref"], r["alt"]) for r in df.iter_rows(named=True)}
    assert emitted == _parse_fixture_alleles(FIXTURE)
    assert df.height == result.record_count

    # clin_sig is folded into the module vocabulary; the raw value is preserved verbatim.
    assert set(df["clin_sig"].to_list()) <= VALID_CLIN_SIG
    conflicting = df.filter(pl.col("variation_id") == "1043045")
    assert conflicting.height == 1
    assert conflicting["clin_sig"][0] == "conflicting"
    assert conflicting["clin_sig_raw"][0] == "Conflicting_classifications_of_pathogenicity"

    # multi-gene GENEINFO → first symbol in `gene`, all symbols in `genes`.
    multigene = df.filter(pl.col("variation_id") == "3388928")
    assert multigene["gene"][0] == "SAMD11"
    assert multigene["genes"][0] == "SAMD11|LOC107985728"

    # a record with no RS= yields a null rsid (not the string "None").
    no_rs = df.filter(pl.col("variation_id") == "3385321")
    assert no_rs["rsid"][0] is None

    # off-by-one guard: start == VCF POS (1-based), passed through unchanged.
    rs334 = df.filter(pl.col("rsid") == "rs334")
    assert set(rs334["start"].to_list()) == {5227002}
    assert set(rs334["alt"].to_list()) == {"A", "G"}

    assert result.clinvar_file_date == "2026-06-27"
    assert result.source_sha256 and len(result.source_sha256) == 64


def test_build_is_byte_identical_on_rebuild(tmp_path: Path) -> None:
    build_snapshot(FIXTURE, tmp_path / "a")
    build_snapshot(FIXTURE, tmp_path / "b")
    a = sorted((tmp_path / "a" / "data").glob("*.parquet"))
    b = sorted((tmp_path / "b" / "data").glob("*.parquet"))
    assert [p.name for p in a] == [p.name for p in b]
    for pa, pb in zip(a, b, strict=True):
        assert pa.read_bytes() == pb.read_bytes()  # parquet is reproducible (release.json's built_at is not)


# ── resolver link ────────────────────────────────────────────────────────────────────────────


def test_clinvar_lookup_loci_rs334(tmp_path: Path) -> None:
    build_snapshot(FIXTURE, tmp_path / "cv")
    reference = resolve_clinvar_reference(tmp_path / "cv")
    assert reference is not None
    rsid_to_loci, _pos, _warn = clinvar.lookup_loci(reference, ["rs334"], [])
    assert list(rsid_to_loci) == ["rs334"]
    # rs334's two ClinVar records (T>A, T>G) collapse to one locus, alts aggregated + sorted.
    assert rsid_to_loci["rs334"] == [{"chrom": "11", "start": 5227002, "ref": "T", "alts": "A,G"}]


def test_one_to_many_clinvar_expansion(tmp_path: Path) -> None:
    cv = _synthetic_clinvar(
        tmp_path,
        # Both loci `A>T`, so both can host the authored `A/T` — forward resolution is allele-aware
        # since 0.5 and would otherwise drop the second, testing nothing.
        {"rsid": ["rs777", "rs777"], "chrom": ["5", "6"], "start": [500, 600],
         "ref": ["A", "A"], "alt": ["T", "T"]},
    )
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs777,A/T,risk,c\n")
    enrich(spec, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)
    rows = [r for r in _resolution_rows(spec) if r.variant_key == "rs777"]
    assert [r.locus_index for r in rows] == [0, 1]
    assert {(r.chrom, r.start) for r in rows} == {("5", 500), ("6", 600)}
    assert all(r.source == "clinvar" for r in rows)


def test_a_record_the_genotype_cannot_host_is_left_out_of_the_table(tmp_path: Path) -> None:
    """Forward resolution is allele-aware, exactly as the reverse back-fill already was.

    One rsID routinely names several *different* records — in the committed HBB example `rs281864532`
    is `G>GT`, `GT>G` and `GTT>G` at one position — and the module's own genotype says which it means.
    Recording the others hands the compiler a locus it can only drop, and a dropped locus makes the
    compile unreproducible from the injected table, which `--strict` refuses. So the enricher selects;
    it does not repair, and every skipped record is reported.
    """
    cv = _synthetic_clinvar(
        tmp_path,
        {"rsid": ["rs777", "rs777", "rs777"], "chrom": ["5", "5", "5"],
         "start": [500, 500, 500], "ref": ["G", "GT", "GTT"], "alt": ["GT", "G", "G"]},
    )
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs777,G/GT,risk,c\n")
    enrich(spec, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)

    rows = [r for r in _resolution_rows(spec) if r.variant_key == "rs777"]
    # {G,GT} hosts G>GT and GT>G; GTT>G is a two-base deletion the genotype cannot name.
    assert {(r.ref, r.alts) for r in rows} == {("G", "GT"), ("GT", "G")}
    assert [r.locus_index for r in rows] == [0, 1]

    # ...and the module then compiles under strict, with no locus for the compiler to drop.
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors


# ── chain: clinvar fills, and sits AFTER the Ensembl cache (digest stability) ──────────────────


def test_enrich_clinvar_only_then_compile(tmp_path: Path) -> None:
    cv = tmp_path / "cv"
    build_snapshot(FIXTURE, cv)
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs334,A/T,risk,c\n")
    enrich(spec, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)

    rows = [r for r in _resolution_rows(spec) if r.rsid == "rs334"]
    assert len(rows) == 1
    assert rows[0].source == "clinvar"
    assert (rows[0].chrom, rows[0].start, rows[0].alts) == ("11", 5227002, "A,G")

    result = compile_module(spec, tmp_path / "o1", ensembl_cache=None)
    assert result.success, result.errors
    assert result.manifest.compilation.resolution_sources == ["clinvar"]

    # A second enrich is idempotent — the existing rows are authoritative, rewritten identically.
    before = (spec / "resolution.csv").read_text()
    enrich(spec, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)
    assert (spec / "resolution.csv").read_text() == before


def test_ensembl_cache_wins_when_both_present(tmp_path: Path) -> None:
    """With both caches provisioned the Ensembl one answers, so the resolved facts are its facts.

    **Compares `resolution_signature`, not `artifact.digest`, and that is the point of this docstring.**
    It asserted digest equality across two *separately enriched* specs and was intermittently red —
    passing or failing on whether the two `enrich()` calls landed in the same wall-clock second. Every
    sidecar carries a `fetched_at`, that column reaches `sources.parquet`, and the parquet is inside the
    Merkle root, so two runs that found byte-identical facts still mint two artifact identities.

    Making them equal is not achievable here and would not be worth it: it needs each *source* to
    publish its own last-modified time so the stamp could describe the data rather than the fetch, which
    is unenforceable against upstreams that mostly do not offer one. So the test asserts what it
    actually means — the facts and the authored content agree — and leaves the artifact digest to say
    what it correctly says, that these are two artifacts built at two moments.
    """
    cv = tmp_path / "cv"
    build_snapshot(FIXTURE, cv)
    ens = _ensembl_cache(tmp_path)
    variants = "rsid,genotype,state,conclusion\nrs334,A/T,risk,c\n"

    # Ensembl cache only.
    spec_e = _spec(tmp_path / "se", variants)
    enrich(spec_e, offline=True, ensembl_cache=ens, use_clinvar=False)
    dig_e = compile_module(spec_e, tmp_path / "oe", ensembl_cache=None)
    assert dig_e.success, dig_e.errors

    # Both caches present: the Ensembl cache wins, because ClinVar sits after it in the chain.
    spec_b = _spec(tmp_path / "sb", variants)
    enrich(spec_b, offline=True, ensembl_cache=ens, clinvar_cache=cv)
    dig_b = compile_module(spec_b, tmp_path / "ob", ensembl_cache=None)
    rows_b = [r for r in _resolution_rows(spec_b) if r.rsid == "rs334"]
    assert rows_b[0].source == "cache"
    assert rows_b[0].alts == "A,C,G"  # Ensembl's alleles, not ClinVar's A,G
    assert dig_b.manifest.compilation.resolution_sources == ["cache"]
    # The fact hash is the right instrument: producer-independent by construction, so it answers
    # "are these the same resolved facts" without answering "were they fetched at the same instant".
    assert (
        dig_b.manifest.compilation.resolution_signature
        == dig_e.manifest.compilation.resolution_signature
    )

    # ClinVar-only genuinely resolves different facts (alts differ) — the reason it sits after the cache.
    spec_c = _spec(tmp_path / "sc", variants)
    enrich(spec_c, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)
    dig_c = compile_module(spec_c, tmp_path / "oc", ensembl_cache=None)
    assert (
        dig_c.manifest.compilation.resolution_signature
        != dig_e.manifest.compilation.resolution_signature
    )
    # ...yet the authored content is identical across all three (only resolution-side identity moves).
    assert dig_c.manifest.content_signature == dig_e.manifest.content_signature
    assert dig_b.manifest.content_signature == dig_e.manifest.content_signature


# ── integration: full build against the real local VCF (skipped when absent) ────────────────────


# ── allele-aware reverse back-fill + ambiguity marking (Tier 0/1/3) ────────────────────────────


def test_reverse_backfill_is_allele_aware_and_flags_ambiguity(tmp_path: Path) -> None:
    # At 1:100:A there are two alleles: A>T (a genuine dbSNP merge: rs1000 AND rs1001) and A>G (rs9).
    # At 1:200:C the insertion C>CAT has no rsID. A coordinate-only authoring of each must:
    #   A>T   → ambiguous: deterministic pick rs1000 + rsid_alternates=rs1000,rs1001 (never rs9)
    #   A>G   → resolved rs9 (allele-exact; not contaminated by the A>T rsIDs)
    #   C>CAT → rsid null (don't guess an allele-blind rsID), source=authored
    cv = _synthetic_clinvar(
        tmp_path,
        {"rsid": ["rs1000", "rs1001", "rs9", None], "chrom": ["1", "1", "1", "1"],
         "start": [100, 100, 100, 200], "ref": ["A", "A", "A", "C"], "alt": ["T", "T", "G", "CAT"]},
    )
    variants = (
        "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
        ",1,100,A,T,A/T,risk,pathogenic\n"
        ",1,100,A,G,A/G,risk,pathogenic\n"
        ",1,200,C,CAT,C/CAT,risk,pathogenic\n"
    )
    spec = _spec(tmp_path / "spec", variants)
    enrich(spec, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)
    by_alt = {r.alts: r for r in _resolution_rows(spec)}

    assert by_alt["T"].status == "ambiguous"
    assert by_alt["T"].rsid == "rs1000"                       # deterministic pick (lowest id)
    assert by_alt["T"].rsid_alternates == "rs1000,rs1001"     # full candidate list, inspectable
    assert by_alt["G"].status == "resolved" and by_alt["G"].rsid == "rs9"  # allele-exact, no contamination
    assert by_alt["G"].rsid_alternates is None
    assert by_alt["CAT"].rsid is None and by_alt["CAT"].source == "authored"  # never guessed


def test_reverse_roundtrip_is_a_fixpoint(tmp_path: Path) -> None:
    # With deterministic, allele-exact back-fill, compile→reverse→compile→reverse→compile is a true
    # fixpoint for artifact.digest AND the (provisional) resolution_signature — the drift that the
    # allele-blind pick used to cause is gone.
    cv = tmp_path / "cv"
    build_snapshot(FIXTURE, cv)
    spec = _spec(
        tmp_path / "spec",
        "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
        "rs334,,,,,A/T,risk,pathogenic\n"
        ",11,5226762,C,CAAAG,C/CAAAG,risk,pathogenic\n",   # the un-rs'd insertion from finding 7
    )
    enrich(spec, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)
    r1 = compile_module(spec, tmp_path / "o1", ensembl_cache=None)
    assert r1.success, r1.errors

    from just_dna_compiler.compiler import reverse_module
    reverse_module(tmp_path / "o1", tmp_path / "rev1", write_resolution=True)
    r2 = compile_module(tmp_path / "rev1", tmp_path / "o2", ensembl_cache=None)
    reverse_module(tmp_path / "o2", tmp_path / "rev2", write_resolution=True)
    r3 = compile_module(tmp_path / "rev2", tmp_path / "o3", ensembl_cache=None)

    assert r2.manifest.artifact.digest == r3.manifest.artifact.digest
    assert r2.manifest.compilation.resolution_signature == r3.manifest.compilation.resolution_signature
    # the un-rs'd insertion stays coordinate-only (no allele-blind rsID borrowed from the SNV) and is
    # keyed by its own allele (chrom:start:ref:alts), so it no longer collides with a co-located variant
    ins = [r for r in _resolution_rows(spec) if r.variant_key == "11:5226762:C:CAAAG"]
    assert ins and all(r.rsid is None for r in ins)


@pytest.mark.integration
def test_build_real_vcf(tmp_path: Path) -> None:
    if not REAL_VCF.exists():
        pytest.skip(f"real ClinVar VCF absent at {REAL_VCF}")
    result = build_snapshot(REAL_VCF, tmp_path / "cv")
    assert result.record_count > 1_000_000
    reference = resolve_clinvar_reference(tmp_path / "cv")
    rsid_to_loci, _pos, _warn = clinvar.lookup_loci(reference, ["rs334"], [])
    assert rsid_to_loci["rs334"][0]["start"] == 5227002  # same coordinate convention as the slice


# ── the citations sidecar and its provenance ────────────────────────────────────────────────────
#
# ClinVar publishes `var_citations.txt` separately from the VCF and on its own cadence, so a snapshot
# can legitimately carry records from one release and citations from another. Now that the table is
# *published with the snapshot*, an artifact whose `release.json` documented only the VCF would be
# mixed-vintage and silent about it — the same class of confusion `dataset` is inside the fact set to
# prevent for the two gene-constraint routes.

_CITATIONS_TSV = (
    "#AlleleID\tVariationID\trs\tnsv\tcitation_source\tcitation_id\torganization_ids\n"
    "15041\t2\t397704705\t\tPubMed\t20613862\t1,3\n"
    "15041\t2\t397704705\t\tPubMed\t20613861\t1\n"
    "15042\t3\t\t\tPubMedBookArticle\t99999999\t1\n"   # not PubMed → dropped
)


def _citations_txt(tmp_path: Path) -> Path:
    path = tmp_path / "var_citations.txt"
    path.write_text(_CITATIONS_TSV, encoding="utf-8")
    return path


def test_citations_build_writes_the_sidecar_and_keeps_only_pubmed(tmp_path: Path) -> None:
    from just_dna_enricher.clinvar_build import build_citations

    snapshot = tmp_path / "cv"
    build_snapshot(FIXTURE, snapshot)
    result = build_citations(_citations_txt(tmp_path), snapshot)

    assert result.row_count == 2                      # the PubMedBookArticle row is not a PMID
    # The input is hashed even when no caller supplied a digest: the bytes are on disk, so recording
    # "unknown" would be an unknown we chose not to establish.
    assert result.source_sha256 and len(result.source_sha256) == 64
    table = pl.read_parquet(snapshot / clinvar.CITATIONS_DIRNAME / "citations.parquet")
    assert table.columns == ["variation_id", "pmid"]
    assert set(table["pmid"].to_list()) == {"20613862", "20613861"}
    # Beside `data/`, never inside it — a two-column table under the reader's glob breaks every query.
    assert not (snapshot / "data" / "citations.parquet").exists()


def test_citations_provenance_is_merged_not_overwritten(tmp_path: Path) -> None:
    """The records' provenance must survive: `build_snapshot` owns the VCF keys, this owns its own."""
    import json

    from just_dna_enricher.clinvar_build import build_citations

    snapshot = tmp_path / "cv"
    built = build_snapshot(FIXTURE, snapshot)
    before = json.loads((snapshot / "release.json").read_text())

    result = build_citations(
        _citations_txt(tmp_path), snapshot, source_url="http://example/var_citations.txt",
        source_sha256="abc123",
    )
    after = json.loads((snapshot / "release.json").read_text())

    assert result.release_updated
    assert after["source_sha256"] == before["source_sha256"] == built.source_sha256
    assert after["record_count"] == before["record_count"]
    citations = after["citations"]
    assert citations["row_count"] == 2
    assert citations["source_sha256"] == "abc123"
    assert citations["source_url"] == "http://example/var_citations.txt"


def test_citations_beside_a_snapshot_with_no_release_json_starts_one(tmp_path: Path) -> None:
    """Partial provenance beats none: `build_citations` is documented as usable beside an existing
    snapshot, including one from a builder that wrote no `release.json`."""
    import json

    from just_dna_enricher.clinvar_build import build_citations

    snapshot = tmp_path / "cv"
    build_snapshot(FIXTURE, snapshot)
    (snapshot / "release.json").unlink()
    assert build_citations(_citations_txt(tmp_path), snapshot).release_updated
    assert set(json.loads((snapshot / "release.json").read_text())) == {"citations"}


def test_an_unreadable_release_json_is_left_alone_and_reported(tmp_path: Path, caplog) -> None:
    """Report, never repair: overwriting it would destroy the only statement of where the data is from."""
    from just_dna_enricher.clinvar_build import build_citations

    snapshot = tmp_path / "cv"
    build_snapshot(FIXTURE, snapshot)
    (snapshot / "release.json").write_text("{not json", encoding="utf-8")
    with caplog.at_level("WARNING"):
        result = build_citations(_citations_txt(tmp_path), snapshot)
    assert not result.release_updated
    assert (snapshot / "release.json").read_text() == "{not json"       # untouched
    assert "unreadable" in "\n".join(r.getMessage() for r in caplog.records)
    # …and the citations table itself was still written: the provenance failure is not a data failure.
    assert (snapshot / clinvar.CITATIONS_DIRNAME / "citations.parquet").is_file()
