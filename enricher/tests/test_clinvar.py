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
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import VALID_CLIN_SIG

from just_dna_enricher import clinvar
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.enrich import enrich
from just_dna_enricher.locations import resolve_clinvar_reference

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
    for pa, pb in zip(a, b):
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
        {"rsid": ["rs777", "rs777"], "chrom": ["5", "6"], "start": [500, 600],
         "ref": ["A", "C"], "alt": ["T", "G"]},
    )
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs777,A/T,risk,c\n")
    enrich(spec, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)
    rows = [r for r in _resolution_rows(spec) if r.variant_key == "rs777"]
    assert [r.locus_index for r in rows] == [0, 1]
    assert {(r.chrom, r.start) for r in rows} == {("5", 500), ("6", 600)}
    assert all(r.source == "clinvar" for r in rows)


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


def test_ensembl_cache_wins_when_both_present_no_digest_move(tmp_path: Path) -> None:
    cv = tmp_path / "cv"
    build_snapshot(FIXTURE, cv)
    ens = _ensembl_cache(tmp_path)
    variants = "rsid,genotype,state,conclusion\nrs334,A/T,risk,c\n"

    # Ensembl cache only.
    spec_e = _spec(tmp_path / "se", variants)
    enrich(spec_e, offline=True, ensembl_cache=ens, use_clinvar=False)
    dig_e = compile_module(spec_e, tmp_path / "oe", ensembl_cache=None)
    assert dig_e.success, dig_e.errors

    # Both caches present: the Ensembl cache wins (ClinVar sits after it), so nothing moves.
    spec_b = _spec(tmp_path / "sb", variants)
    enrich(spec_b, offline=True, ensembl_cache=ens, clinvar_cache=cv)
    dig_b = compile_module(spec_b, tmp_path / "ob", ensembl_cache=None)
    rows_b = [r for r in _resolution_rows(spec_b) if r.rsid == "rs334"]
    assert rows_b[0].source == "cache"
    assert rows_b[0].alts == "A,C,G"  # Ensembl's alleles, not ClinVar's A,G
    assert dig_b.manifest.compilation.resolution_sources == ["cache"]
    assert dig_b.manifest.artifact.digest == dig_e.manifest.artifact.digest

    # ClinVar-only WOULD move the digest (alts differ) — the reason it must sit after the cache.
    spec_c = _spec(tmp_path / "sc", variants)
    enrich(spec_c, offline=True, ensembl_cache=tmp_path / "noens", clinvar_cache=cv)
    dig_c = compile_module(spec_c, tmp_path / "oc", ensembl_cache=None)
    assert dig_c.manifest.artifact.digest != dig_e.manifest.artifact.digest
    # ...yet the authored content is identical across all three (only resolution-side identity moves).
    assert dig_c.manifest.content_signature == dig_e.manifest.content_signature
    assert dig_b.manifest.content_signature == dig_e.manifest.content_signature


# ── integration: full build against the real local VCF (skipped when absent) ────────────────────


@pytest.mark.integration
def test_build_real_vcf(tmp_path: Path) -> None:
    if not REAL_VCF.exists():
        pytest.skip(f"real ClinVar VCF absent at {REAL_VCF}")
    result = build_snapshot(REAL_VCF, tmp_path / "cv")
    assert result.record_count > 1_000_000
    reference = resolve_clinvar_reference(tmp_path / "cv")
    rsid_to_loci, _pos, _warn = clinvar.lookup_loci(reference, ["rs334"], [])
    assert rsid_to_loci["rs334"][0]["start"] == 5227002  # same coordinate convention as the slice
