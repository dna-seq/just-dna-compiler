"""The ClinPGx snapshot builder and cross-check — network-free.

The fixture archive is built in-memory with the **real** shapes: a `LICENSE.txt` and a
`CREATED_<date>.txt` beside the TSVs, per-genotype child rows, and one variant+drug carrying three
distinct annotations at three phenotype categories (the rs4149056/simvastatin case, which is what
broke the first version of the cross-check).
"""

import io
import json
import zipfile
from pathlib import Path

import polars as pl
import pytest

from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, enrich_clinpgx
from just_dna_enricher.clinpgx_build import build_snapshot, read_created_date, read_license
from just_dna_enricher.licensing import LicenseRefusal

_LICENSE = (
    "This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International "
    "License.\nUnder no circumstances can ClinPGx data be sold for other's private or commercial use.\n"
)
# Three annotations, one variant, one drug, three categories -- the real collision.
_SUMMARY = "\t".join([
    "Clinical Annotation ID", "Variant/Haplotypes", "Gene", "Level of Evidence", "Level Override",
    "Level Modifiers", "Score", "Phenotype Category", "PMID Count", "Evidence Count", "Drug(s)",
    "Phenotype(s)", "Latest History Date (YYYY-MM-DD)", "URL", "Specialty Population",
]) + "\n" + "\n".join([
    "\t".join(["1449556772", "rs4149056", "SLCO1B1", "1A", "", "", "9", "Metabolism/PK", "5", "5",
               "simvastatin;simvastatin acid", "", "2025-01-01", "u", ""]),
    "\t".join(["1451356520", "rs4149056", "SLCO1B1", "3", "", "", "2", "Efficacy", "2", "2",
               "simvastatin", "", "2025-01-01", "u", ""]),
    "\t".join(["655384011", "rs4149056", "SLCO1B1", "1A", "", "", "9", "Toxicity", "9", "9",
               "simvastatin", "", "2025-01-01", "u", ""]),
    # a haplotype-keyed annotation: the subject is not an rsID, so `rsid` must stay null
    "\t".join(["999000111", "CYP2C19*2", "CYP2C19", "1A", "", "", "9", "Efficacy", "9", "9",
               "clopidogrel", "", "2025-01-01", "u", ""]),
]) + "\n"
_ALLELES = "Clinical Annotation ID\tGenotype/Allele\tAnnotation Text\tAllele Function\n" + "\n".join(
    f"{aid}\t{gt}\ttext for {aid} {gt}\t"
    for aid in ("1449556772", "1451356520", "655384011")
    for gt in ("CC", "CT", "TT")
) + "\n999000111\t*1/*2\thaplotype text\t\n"

_YAML = (
    'schema_version: "1.0"\n'
    "module:\n  name: slco\n  title: T\n  report_title: T\n  description: d\n"
)


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    path = tmp_path / "clinicalAnnotations.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("LICENSE.txt", _LICENSE)
        z.writestr("CREATED_2026-07-05.txt", "created\n")
        z.writestr("clinical_annotations.tsv", _SUMMARY)
        z.writestr("clinical_ann_alleles.tsv", _ALLELES)
    return path


@pytest.fixture
def snapshot(archive: Path, tmp_path: Path) -> Path:
    build_snapshot(archive, tmp_path / "snap")
    return tmp_path / "snap"


def _spec(tmp_path: Path, pharm: str, name: str = "spec") -> Path:
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML)
    (d / "pharm_variants.csv").write_text(pharm)
    return d


# ── the builder ─────────────────────────────────────────────────────────────────────────────────
def test_license_is_read_from_the_archive_not_a_table(archive: Path, tmp_path: Path) -> None:
    """The whole point of the licensing design: the terms come from the bytes the data came in."""
    result = build_snapshot(archive, tmp_path / "snap")
    with zipfile.ZipFile(archive) as z:
        assert read_license(z) == _LICENSE
        assert read_created_date(z) == "2026-07-05"
    # The hash is computed from the fixture's own text at runtime, never hardcoded.
    import hashlib
    expected = "sha256:" + hashlib.sha256(_LICENSE.encode()).hexdigest()
    assert result.license_sha256 == expected
    assert (tmp_path / "snap" / "LICENSE.txt").read_text() == _LICENSE
    assert json.loads((tmp_path / "snap" / "release.json").read_text())["license_sha256"] == expected


def test_snapshot_grain_is_annotation_times_genotype(snapshot: Path) -> None:
    frame = pl.read_parquet(snapshot / "data" / "annotations.parquet")
    assert frame.height == 10          # 3 annotations x 3 genotypes + 1 haplotype row
    assert frame["annotation_id"].n_unique() == 4
    # A haplotype subject is not an rsID and must not be mangled into one.
    hap = frame.filter(pl.col("annotation_id") == "999000111")
    assert hap["rsid"].to_list() == [None] and hap["subject"].to_list() == ["CYP2C19*2"]


def test_rebuild_is_byte_identical(archive: Path, tmp_path: Path) -> None:
    """Deterministic sort → a rebuild reproduces the parquet exactly (Principle 7)."""
    a = build_snapshot(archive, tmp_path / "a").parquet_path.read_bytes()
    b = build_snapshot(archive, tmp_path / "b").parquet_path.read_bytes()
    assert a == b


# ── the cross-check ─────────────────────────────────────────────────────────────────────────────
_FAITHFUL = (
    "rsid,gene,genotype,drug,phenotype_category,annotation_id,evidence_level,conclusion\n"
    "rs4149056,SLCO1B1,C/C,simvastatin,Metabolism/PK,1449556772,1A,c\n"
    "rs4149056,SLCO1B1,C/C,simvastatin,Efficacy,1451356520,3,c\n"
    "rs4149056,SLCO1B1,C/C,simvastatin,Toxicity,655384011,1A,c\n"
)


def test_three_annotations_for_one_variant_drug_are_not_false_conflicts(
    snapshot: Path, tmp_path: Path
) -> None:
    """Regression: keying the index on (rsid, drug, genotype) alone reported all three as stale.

    rs4149056 + simvastatin is Metabolism/PK at 1A, Efficacy at 3 AND Toxicity at 1A. Comparing an
    authored Efficacy row against whichever annotation was indexed first flagged correctly-authored
    levels — every row here is faithful to the snapshot, so any conflict is the bug.
    """
    result = enrich_clinpgx(
        _spec(tmp_path, _FAITHFUL), snapshot=snapshot, declared_use="non_commercial"
    )
    assert result.conflicts == []
    assert result.unmatched == []


def test_a_genuinely_stale_level_is_still_caught(snapshot: Path, tmp_path: Path) -> None:
    """The fix must not have made the check silent."""
    stale = _FAITHFUL.replace("Toxicity,655384011,1A", "Toxicity,655384011,4")
    result = enrich_clinpgx(
        _spec(tmp_path, stale), snapshot=snapshot, declared_use="non_commercial"
    )
    assert len(result.conflicts) == 1
    assert (result.conflicts[0].authored, result.conflicts[0].reported) == ("4", "1A")


def test_strict_refuses_a_stale_level(snapshot: Path, tmp_path: Path) -> None:
    """A currency fact, not an opinion — so unlike the allele-function check, strict escalates."""
    stale = _FAITHFUL.replace("Toxicity,655384011,1A", "Toxicity,655384011,4")
    with pytest.raises(ClinPgxEnrichmentError):
        enrich_clinpgx(
            _spec(tmp_path, stale), snapshot=snapshot, mode="strict",
            declared_use="non_commercial",
        )


def test_an_ambiguous_row_is_reported_not_guessed(snapshot: Path, tmp_path: Path) -> None:
    """No category and no id, several candidate annotations → say so rather than flip a coin."""
    vague = (
        "rsid,gene,genotype,drug,evidence_level,conclusion\n"
        "rs4149056,SLCO1B1,C/C,simvastatin,1A,c\n"
    )
    result = enrich_clinpgx(
        _spec(tmp_path, vague), snapshot=snapshot, declared_use="non_commercial"
    )
    assert result.conflicts == []
    assert any("was not checked" in w for w in result.warnings)


def test_genotype_spelling_is_normalized_across_the_two_conventions(
    snapshot: Path, tmp_path: Path
) -> None:
    """ClinPGx writes `CT`; this workspace writes `C/T`. They must match."""
    result = enrich_clinpgx(
        _spec(tmp_path, _FAITHFUL.replace("C/C", "C/T")), snapshot=snapshot,
        declared_use="non_commercial",
    )
    assert result.conflicts == [] and result.unmatched == []


def test_the_pinned_licence_hash_reaches_the_source_row(snapshot: Path, tmp_path: Path) -> None:
    import hashlib
    result = enrich_clinpgx(
        _spec(tmp_path, _FAITHFUL), snapshot=snapshot, declared_use="non_commercial"
    )
    row = result.rows[0]
    assert row.license_sha256 == "sha256:" + hashlib.sha256(_LICENSE.encode()).hexdigest()
    assert row.commercial_use is False and row.declared_use == "non_commercial"
    assert row.dataset == "clinpgx_2026-07-05"


def test_declared_use_gate_applies_offline_too(snapshot: Path, tmp_path: Path) -> None:
    """The terms were accepted when the snapshot was built; using it is the same act."""
    with pytest.raises(LicenseRefusal):
        enrich_clinpgx(
            _spec(tmp_path, _FAITHFUL, "commercial"), snapshot=snapshot,
            declared_use="commercial",
        )
    result = enrich_clinpgx(
        _spec(tmp_path, _FAITHFUL, "unstated"), snapshot=snapshot
    )  # unstated
    assert result.rows == [] and result.warnings
