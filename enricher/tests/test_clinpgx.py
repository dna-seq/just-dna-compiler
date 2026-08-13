"""The ClinPGx snapshot builder and cross-check — network-free.

The fixture archive is built in-memory with the **real** shapes: a `LICENSE.txt` and a
`CREATED_<date>.txt` beside the TSVs, per-genotype child rows, and one variant+drug carrying three
distinct annotations at three phenotype categories (the rs4149056/simvastatin case, which is what
broke the first version of the cross-check).
"""

import json
import zipfile
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, enrich_clinpgx
from just_dna_enricher.clinpgx_build import build_snapshot, read_created_date, read_license
from just_dna_enricher.licensing import LicenseRefusal
from just_dna_format import verification as verification_module
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.verification import read_verification

_LICENSE = (
    "This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International "
    "License.\nUnder no circumstances can ClinPGx data be sold for other's private or commercial use.\n"
)
# Three annotations, one variant, one drug, three categories -- the real collision.
_SUMMARY = "Clinical Annotation ID\tVariant/Haplotypes\tGene\tLevel of Evidence\tLevel Override\tLevel Modifiers\tScore\tPhenotype Category\tPMID Count\tEvidence Count\tDrug(s)\tPhenotype(s)\tLatest History Date (YYYY-MM-DD)\tURL\tSpecialty Population" + "\n" + "1449556772\trs4149056\tSLCO1B1\t1A\t\t\t9\tMetabolism/PK\t5\t5\tsimvastatin;simvastatin acid\t\t2025-01-01\tu\t\n1451356520\trs4149056\tSLCO1B1\t3\t\t\t2\tEfficacy\t2\t2\tsimvastatin\t\t2025-01-01\tu\t\n655384011\trs4149056\tSLCO1B1\t1A\t\t\t9\tToxicity\t9\t9\tsimvastatin\t\t2025-01-01\tu\t\n999000111\tCYP2C19*2\tCYP2C19\t1A\t\t\t9\tEfficacy\t9\t9\tclopidogrel\t\t2025-01-01\tu\t" + "\n"
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


# ── what the pass records about itself (RM45) ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    """8 bits instead of 20: these cases are about what is recorded, not about the work."""
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", 8)


def _records(spec_dir: Path) -> dict:
    return {r.check: r for r in read_verification(spec_dir / VERIFICATION_JSON).records}


def test_a_run_that_compared_levels_records_what_it_compared(
    snapshot: Path, tmp_path: Path
) -> None:
    """The denominator comes from the pass, so the manifest cannot claim more than was looked up."""
    spec = _spec(tmp_path, _FAITHFUL)
    result = enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")

    record = _records(spec)["pgx_evidence_level"]
    assert record.skipped is None
    assert record.subjects == result.compared > 0
    assert record.findings == len(result.conflicts) == 0
    assert record.source == "clinpgx" and record.release == result.dataset


def test_a_stale_level_is_recorded_as_a_finding(snapshot: Path, tmp_path: Path) -> None:
    stale = _FAITHFUL.replace("Toxicity,655384011,1A", "Toxicity,655384011,4")
    spec = _spec(tmp_path, stale)
    enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")

    record = _records(spec)["pgx_evidence_level"]
    assert (record.subjects, record.findings) == (3, 1)


def test_an_ambiguous_row_counts_as_compared_and_not_as_a_finding(
    snapshot: Path, tmp_path: Path
) -> None:
    """It WAS looked up; the answer was "cannot tell". That is a comparison, not an absence of one.

    Recording it as unexamined would understate the denominator and make the pass look like it skipped
    a row it actually paid for.
    """
    vague = (
        "rsid,gene,genotype,drug,evidence_level,conclusion\n"
        "rs4149056,SLCO1B1,C/C,simvastatin,1A,c\n"
    )
    spec = _spec(tmp_path, vague)
    enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")

    record = _records(spec)["pgx_evidence_level"]
    assert (record.subjects, record.findings, record.skipped) == (1, 0, None)


def test_a_licensing_skip_is_not_spelled_offline(snapshot: Path, tmp_path: Path) -> None:
    """`not_permitted` is cleared by a declaration, so calling it `offline` misdirects the reader."""
    spec = _spec(tmp_path, _FAITHFUL, "unstated")
    enrich_clinpgx(spec, snapshot=snapshot)  # declared_use defaults to unstated

    record = _records(spec)["pgx_evidence_level"]
    assert record.skipped == "not_permitted"
    assert record.subjects == 0 and record.detail


def test_no_snapshot_records_the_skip_rather_than_a_clean_pass(
    tmp_path: Path, monkeypatch
) -> None:
    """The case the whole item is about: nothing ran, and the record has to say so.

    Without a record here the module is indistinguishable from one whose levels were all confirmed —
    `result.conflicts` is `[]` either way, which is the first assertion below.

    Reached with no cache and `offline` rather than by passing a bad `snapshot=`: an explicit path is
    the inject-only escape hatch and is never second-guessed, so a missing one raises instead of
    skipping. The env var is neutralized with `""` and not deleted, for the reason the suite's
    credential rule gives — `load_dotenv(override=False)` would restore a deleted key from `.env`.
    """
    monkeypatch.setenv("JUST_DNA_CLINPGX_CACHE", "")
    spec = _spec(tmp_path, _FAITHFUL)
    result = enrich_clinpgx(spec, declared_use="non_commercial", offline=True)
    assert result.conflicts == []  # the misleading half, on its own

    record = _records(spec)["pgx_evidence_level"]
    assert record.skipped == "offline" and record.subjects == 0


def test_a_module_with_no_pgx_table_attests_nothing_at_all(tmp_path: Path, snapshot: Path) -> None:
    """Not applicable is not the same as applicable-and-skipped, and only the second is worth a record.

    A module with no `pharm_variants.csv` has no PGx claim for this check to have an opinion about, so
    recording "skipped" would answer a question nobody asked — and it would do it by mining a nonce and
    creating a `verification.json` on a module that has nothing to do with ClinPGx. The skip vocabulary
    is for a check that COULD have run on this module; `nothing_to_check` stays reachable for a table
    that is present with no row in scope.
    """
    spec = tmp_path / "bare"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")

    assert not (spec / VERIFICATION_JSON).exists()


def test_two_passes_over_one_module_keep_both_records(snapshot: Path, tmp_path: Path) -> None:
    """The merge is what makes several commands share one attestation.

    A second command must not erase the first's answer — a run that did not put a question has said
    nothing about it, and dropping the earlier record would turn that into "never asked".
    """
    from just_dna_enricher.verification import ran, record_verification

    spec = _spec(tmp_path, _FAITHFUL)
    enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")
    record_verification(
        [ran("rsid_currency", subjects=4, findings=0, source="dbsnp")],
        spec,
        error=ClinPgxEnrichmentError,
    )

    records = _records(spec)
    assert set(records) == {"pgx_evidence_level", "rsid_currency"}
    assert records["pgx_evidence_level"].subjects == 3


def test_the_strict_refusal_attests_nothing(snapshot: Path, tmp_path: Path) -> None:
    """A raised pass produced no artifact, so there is nothing to record a check against."""
    stale = _FAITHFUL.replace("Toxicity,655384011,1A", "Toxicity,655384011,4")
    spec = _spec(tmp_path, stale)
    with pytest.raises(ClinPgxEnrichmentError):
        enrich_clinpgx(spec, snapshot=snapshot, mode="strict", declared_use="non_commercial")
    assert not (spec / VERIFICATION_JSON).exists()
