"""The enricher's half of RM45: passes record what they checked, and the record survives the next run.

The merge is what makes several commands share one document — `enrich` writes three checks, a later
`check-identifiers` writes its own, and neither may erase the other's. That is the same load-merge-write
discipline `licensing.record_source_terms` has, for the same reason: a count of call sites goes stale,
one function does not.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import authored_input_entries, compile_module
from just_dna_enricher.enrich import _verification_records
from just_dna_enricher.verification import producer_label, ran, record_verification, skipped
from just_dna_format import verification as verification_module
from just_dna_format.layout import DERIVED_SUBDIR, VERIFICATION_JSON
from just_dna_format.verification import (
    attestation_failure,
    module_binding,
    read_verification,
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_EASY = 8


class _Boom(Exception):
    """The caller's own error type, which is what `record_verification` must raise."""


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", _EASY)


def _module(tmp_path: Path, name: str = "hfe_hemochromatosis") -> Path:
    spec = tmp_path / name
    shutil.copytree(_EXAMPLES / name, spec)
    return spec


def test_a_run_with_no_checks_writes_nothing(tmp_path: Path) -> None:
    """An empty attestation would assert that a module was checked and nothing was found."""
    spec = _module(tmp_path)
    assert record_verification([], spec, error=_Boom) is None
    assert not (spec / VERIFICATION_JSON).exists()


def test_the_document_is_bound_to_the_module_as_it_stands(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    doc = record_verification([ran("rsid_currency", subjects=12, findings=0)], spec, error=_Boom)
    assert doc is not None
    assert doc.module_hash == module_binding(authored_input_entries(spec))
    assert doc.producer == producer_label()
    assert read_verification(spec / VERIFICATION_JSON) == doc


def test_a_second_pass_adds_its_check_without_erasing_the_first(tmp_path: Path) -> None:
    """Two commands, one document. The first run's answer is not 'never asked' after the second."""
    spec = _module(tmp_path)
    record_verification([ran("rsid_currency", subjects=12, findings=1)], spec, error=_Boom)
    record_verification(
        [skipped("gene_symbol_currency", "offline", detail="HGNC needs egress")], spec, error=_Boom
    )

    by_check = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}
    assert set(by_check) == {"rsid_currency", "gene_symbol_currency"}
    assert by_check["rsid_currency"].findings == 1
    assert by_check["gene_symbol_currency"].skipped == "offline"


def test_re_running_one_check_replaces_its_own_record(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    record_verification([ran("rsid_currency", subjects=12, findings=1)], spec, error=_Boom)
    record_verification([ran("rsid_currency", subjects=12, findings=0)], spec, error=_Boom)

    records = read_verification(spec / VERIFICATION_JSON).records
    assert len(records) == 1 and records[0].findings == 0


def test_the_pass_writes_to_the_file_it_reads(tmp_path: Path) -> None:
    """A split module must not gain a second copy at the root — that is the refusal, self-inflicted."""
    spec = _module(tmp_path)
    (spec / DERIVED_SUBDIR).mkdir()
    record_verification([ran("rsid_currency", subjects=1, findings=0)], spec, error=_Boom)
    shutil.move(spec / VERIFICATION_JSON, spec / DERIVED_SUBDIR / VERIFICATION_JSON)

    record_verification([ran("rsid_currency", subjects=2, findings=0)], spec, error=_Boom)
    assert not (spec / VERIFICATION_JSON).exists()
    assert read_verification(spec / DERIVED_SUBDIR / VERIFICATION_JSON).records[0].subjects == 2


def test_two_copies_raise_the_callers_own_error(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    (spec / DERIVED_SUBDIR).mkdir()
    record_verification([ran("rsid_currency", subjects=1, findings=0)], spec, error=_Boom)
    shutil.copy(spec / VERIFICATION_JSON, spec / DERIVED_SUBDIR / VERIFICATION_JSON)

    with pytest.raises(_Boom, match="two places"):
        record_verification([ran("rsid_currency", subjects=2, findings=0)], spec, error=_Boom)


def test_an_unreadable_document_is_replaced_rather_than_fatal(tmp_path: Path) -> None:
    """A pass that could not re-attest without a manual delete would be worse than a lost record."""
    spec = _module(tmp_path)
    (spec / VERIFICATION_JSON).write_text("not json at all")
    doc = record_verification([ran("rsid_currency", subjects=3, findings=0)], spec, error=_Boom)
    assert doc is not None and [r.check for r in doc.records] == ["rsid_currency"]


def test_the_record_written_is_the_one_the_compiler_accepts(tmp_path: Path) -> None:
    """The end-to-end seam, inside this workspace: enricher writes, compiler stamps."""
    spec = _module(tmp_path)
    record_verification(
        [ran("clinical_significance", subjects=7, findings=1, source="clinvar", release="2026-06-27")],
        spec,
        error=_Boom,
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    block = result.manifest.verification
    assert block is not None
    assert [(r.check, r.subjects, r.findings, r.release) for r in block.checks] == [
        ("clinical_significance", 7, 1, "2026-06-27")
    ]


def test_editing_the_module_after_recording_invalidates_the_record(tmp_path: Path) -> None:
    """Same fact from this side: the binding is over the authored bytes, so an edit perishes it."""
    spec = _module(tmp_path)
    doc = record_verification([ran("rsid_currency", subjects=1, findings=0)], spec, error=_Boom)
    assert doc is not None
    assert attestation_failure(doc, module_binding(authored_input_entries(spec))) is None

    (spec / "variants.csv").write_text((spec / "variants.csv").read_text() + "\n")
    assert attestation_failure(doc, module_binding(authored_input_entries(spec))) is not None


# ── the records `enrich()` itself builds, per check ──────────────────────────────────────────────


def test_the_build_diagnosis_denominator_is_what_it_examined_not_what_existed() -> None:
    """`_verification_records` must publish `examined`, never `total` (RM48 + RM45).

    The wrong-build pass is deliberately bounded (`DEFAULT_DIAGNOSIS_LIMIT`), so on a panel authored
    wholesale on hg19 it asks about a sample. Recording `total` would claim rows it chose not to ask
    about — the denominator has to be what was actually compared, and `sampled` is why the two differ
    at all.
    """
    from just_dna_enricher.grch37 import BuildDiagnosis, BuildDiagnosisResult
    from just_dna_enricher.sequences import RefCheck

    diagnosis = BuildDiagnosis(
        variant_key="6:26093141:G", chrom="6", start=26093141, claimed="G",
        reason="dbsnp_corroborated", rsids=["rs1800562"],
    )
    build = BuildDiagnosisResult(diagnoses=[diagnosis], examined=50, total=328)
    records = _records_for(RefCheck([], 12), build)
    record = records["genome_build_agreement"]
    assert (record.subjects, record.findings) == (50, 1)
    assert record.skipped is None
    assert "50 of 328" in (record.detail or ""), "a sample must say it was one"


def test_no_ref_mismatch_means_nothing_to_check_not_a_clean_build() -> None:
    """An empty diagnosis list with no mismatches is *no row was in scope*, never *no wrong builds*.

    Recording it as a run with zero findings would assert that every coordinate was checked against the
    other assembly, which is exactly the claim the pass declines to make.
    """
    from just_dna_enricher.grch37 import BuildDiagnosisResult
    from just_dna_enricher.sequences import RefCheck

    records = _records_for(
        RefCheck([], 12), BuildDiagnosisResult(not_checked="no_ref_mismatches")
    )
    assert records["genome_build_agreement"].skipped == "nothing_to_check"
    # And the reference-allele check beside it DID run, over its own denominator.
    assert (records["reference_allele"].subjects, records["reference_allele"].findings) == (12, 0)


def test_offline_separates_the_two_reasons_a_build_check_can_be_absent() -> None:
    """`offline` is cleared by egress; `nothing_to_check` by nothing at all. Different remedies."""
    from just_dna_enricher.grch37 import BuildDiagnosisResult
    from just_dna_enricher.sequences import RefCheck

    records = _records_for(
        RefCheck([], 0, "offline"),
        BuildDiagnosisResult(not_checked="skipped_offline"),
        offline=True,
        verify_rsids=True,
    )
    assert records["genome_build_agreement"].skipped == "offline"
    assert records["reference_allele"].skipped == "offline"
    assert records["rsid_currency"].skipped == "offline"


# ── review regressions ──────────────────────────────────────────────────────────────────────────


def _records_for(ref_check, build, **over):
    """Every record `enrich()` would write, keyed by check, with a neutral baseline for the rest."""
    kwargs = {
        "offline": False,
        "verify_ref": True,
        "ref_check": ref_check,
        "build": build,
        "verify_clinsig": False,
        "clin_sig_compared": None,
        "clin_sig_conflicts": [],
        "clin_sig_skip": "not_requested",
        "clin_sig_detail": None,
        "clinvar_ref": None,
        "verify_rsids": False,
        "rsid_subjects": 0,
        "stale_rsids": [],
        **over,
    }
    return {r.check: r for r in _verification_records(**kwargs)}


def test_a_build_record_never_claims_refs_agreed_when_no_ref_was_compared() -> None:
    """Two records in one document must not contradict each other (S20's class).

    `diagnose_wrong_build([])` answers `no_ref_mismatches` for an empty list whatever produced it — a
    genuinely clean ref check, *or* a ref check that never ran. Reading that as "no authored ref
    disagreed" turns an unasked question into a confident negative, which is precisely the fingerprint
    S20 taught this tree not to publish. Whatever stopped the ref check has to reach the build record.
    """
    from just_dna_enricher.grch37 import BuildDiagnosisResult
    from just_dna_enricher.sequences import RefCheck

    for ref_check, verify_ref in (
        (RefCheck([], 0, "unreachable"), True),
        (RefCheck([], 0, "not_requested"), False),
        (RefCheck([], 0, "offline"), True),
    ):
        records = _records_for(
            ref_check,
            BuildDiagnosisResult(not_checked="no_ref_mismatches"),
            verify_ref=verify_ref,
        )
        build = records["genome_build_agreement"]
        assert build.skipped == ref_check.not_checked, (
            f"the build record must inherit the ref check's reason, got {build.skipped!r}"
        )
        assert "no authored ref disagreed" not in (build.detail or ""), (
            "claims the refs agreed when none was compared"
        )


def test_nothing_to_check_still_reached_when_the_ref_check_really_ran_clean() -> None:
    """The honest case must survive the fix: refs were compared and none disagreed."""
    from just_dna_enricher.grch37 import BuildDiagnosisResult
    from just_dna_enricher.sequences import RefCheck

    records = _records_for(RefCheck([], 12), BuildDiagnosisResult(not_checked="no_ref_mismatches"))
    build = records["genome_build_agreement"]
    assert build.skipped == "nothing_to_check"
    assert "no authored ref disagreed" in (build.detail or "")


def test_the_clinvar_release_label_is_the_shared_one(tmp_path) -> None:
    """One spelling of the release, or `manifest.verification` and `manifest.sources` disagree.

    `clinvar_dataset_label` prefixes `clinvar_` and falls back to the source digest when the VCF header
    stated no date; a hand-read `clinvar_file_date` does neither, so the same snapshot gets two names
    and a snapshot that CAN state its release records `None`.
    """
    import json

    from just_dna_enricher.clinvar import clinvar_dataset_label
    from just_dna_enricher.enrich import _clinvar_release

    dated = tmp_path / "dated"
    dated.mkdir()
    (dated / "release.json").write_text(json.dumps({"clinvar_file_date": "2026-06-27"}))
    assert _clinvar_release(dated) == clinvar_dataset_label(dated)

    # No file date, but the bytes it was built from name the release exactly.
    digest_only = tmp_path / "digest_only"
    digest_only.mkdir()
    (digest_only / "release.json").write_text(json.dumps({"source_sha256": "a" * 64}))
    assert _clinvar_release(digest_only) == clinvar_dataset_label(digest_only)
    assert _clinvar_release(digest_only) is not None, "it can name its release; None hides that"
