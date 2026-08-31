"""`compile --strict` refuses a coordinate the enricher already diagnosed as another assembly's (0.7, S78).

`strict` means **reproducible**, never *right*: the compiler has no reference, so it cannot check a
coordinate, and a whole file shifted by one base still passes. That line does not move here.
`genome_build_agreement` is the exception on **internal-consistency** grounds — a recorded finding
there says the module's rows are on a different assembly than the `genome_build` it declares, which is
one authored file contradicting another rather than the module disagreeing with an outside archive.
Every other recorded finding keeps warning, because the archive is the stale side often enough that
failing a build would have the format arbitrate someone else's dispute.

The judgement is the enricher's, made against a GRCh37 service the compiler may never call (P2). What
changed is that it stops being discarded at the tier boundary: the gate keys on a record already
written, and the compiler adds no reference, no network and no opinion.

The fixture is the reporter's own case. `rs61849494` is `10:51613269 G/A` on GRCh37 and
`10:45982565 C/T` on GRCh38 — 5.6 Mb apart and strand-flipped, which is what makes a pasted coordinate
produce a module that is internally consistent and about the wrong locus.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    BUILD_AGREEMENT_CHECK,
    build_disagreement_error,
    compile_module,
    validate_spec,
)
from just_dna_enricher.verification import record_verification
from just_dna_format.manifest import Verification, VerificationRecord

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: build\n"
    "  title: Build\n"
    "  description: a coordinate pasted from a GRCh37 paper\n"
    "  report_title: Build\n"
    "genome_build: GRCh38\n"
)

#: The authored row, verbatim from the report — a GRCh37 coordinate in a GRCh38 module.
_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
    "rs61849494,10,51613269,G,A,A/G,alt,Pasted verbatim from a GRCh37 paper.\n"
)

_RESOLUTION = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
    "10:51613269:G:A,rs61849494,10,51613269,G,A,GRCh38,0,ensembl-rest,resolved\n"
)


def _spec(directory: Path, *, records: list[VerificationRecord] | None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (directory / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (directory / "studies.csv").write_text("rsid,pmid\nrs61849494,12345678\n", encoding="utf-8")
    (directory / "resolution.csv").write_text(_RESOLUTION, encoding="utf-8")
    if records is not None:
        record_verification(records, directory, error=RuntimeError)
    return directory


def _diagnosed(findings: int = 1, subjects: int = 1) -> VerificationRecord:
    """What `enrich` writes when the GRCh37 service corroborates the old-assembly reading."""
    return VerificationRecord(
        check=BUILD_AGREEMENT_CHECK,
        subjects=subjects,
        findings=findings,
        source="ensembl-grch37",
        detail="Old-assembly coordinate — 1 row(s) — 10:51613269 → rs61849494",
    )


def _clean(check: str) -> VerificationRecord:
    return VerificationRecord(check=check, subjects=1, findings=0, source="seqrepo")


# ── the gate ────────────────────────────────────────────────────────────────────────────────────


def test_strict_refuses_a_recorded_wrong_build_and_writes_nothing(tmp_path: Path) -> None:
    """The item: a green strict artifact about the wrong locus becomes a refusal.

    The output directory's absence is asserted because a refusal that has already created it is a
    different promise — this gate sits ahead of `output_dir.mkdir()` for the same reason the licence
    gate does, and that placement is the thing a later edit would quietly break.
    """
    spec = _spec(tmp_path / "spec", records=[_diagnosed(), _clean("reference_allele")])

    out = tmp_path / "out"
    compiled = compile_module(spec, out, strict=True)

    assert not compiled.success
    assert BUILD_AGREEMENT_CHECK in compiled.errors[0]
    assert not out.exists(), "a refusal created the output directory"


def test_best_effort_still_builds_and_still_says_so(tmp_path: Path) -> None:
    """`best_effort` means proceed, and it did not stop meaning that.

    The reporter's own position: `best_effort` exists for good reasons — an unreachable Ensembl must
    not be a failure — so the mode ladder is where this belongs. The finding is still reported, by the
    warning that already existed, so the mode changes the severity and nothing else.
    """
    spec = _spec(tmp_path / "spec", records=[_diagnosed(), _clean("reference_allele")])

    compiled = compile_module(spec, tmp_path / "out")

    assert compiled.success, compiled.errors
    assert any("verification.json records" in w for w in compiled.warnings)
    assert compiled.warnings_summary["verification_findings_recorded"] == 1


def test_the_pre_flight_refuses_exactly_what_the_compile_refuses(tmp_path: Path) -> None:
    """The parity rule, asserted by equality — this file has closed that gap four times now.

    Pure computation over an injected sidecar with no `output_dir`, so the check belongs on both
    sides by the rule's own test, and a differently-worded pre-flight refusal would still send an
    author hunting.
    """
    spec = _spec(tmp_path / "spec", records=[_diagnosed()])

    validated = validate_spec(spec, strict=True)
    compiled = compile_module(spec, tmp_path / "out", strict=True)

    assert not validated.valid
    assert validated.errors == compiled.errors


# ── what it must NOT do ─────────────────────────────────────────────────────────────────────────


def test_no_attestation_is_silent_rather_than_a_refusal(tmp_path: Path) -> None:
    """An unverified module is the ordinary case, and refusing there would fail nearly every module.

    This is the discriminating half. Without it the gate passes for an implementation that refuses on
    the *absence* of evidence, which would break every module that has never been enriched — and would
    be the opposite of the tri-state rule, reading unknown as wrong.
    """
    spec = _spec(tmp_path / "spec", records=None)

    compiled = compile_module(spec, tmp_path / "out", strict=True)

    assert compiled.success, compiled.errors
    assert validate_spec(spec, strict=True).valid


def test_a_check_that_ran_and_found_nothing_is_not_a_refusal(tmp_path: Path) -> None:
    """`findings=0` is a clean bill, and `subjects` being non-zero is what makes it one.

    The other way this gate could be written wrong: keying on the record's *presence* rather than on
    its findings would refuse every module the enricher ever looked at.
    """
    spec = _spec(
        tmp_path / "spec",
        records=[
            VerificationRecord(
                check=BUILD_AGREEMENT_CHECK, subjects=1, findings=0, source="ensembl-grch37"
            )
        ],
    )

    assert compile_module(spec, tmp_path / "out", strict=True).success


def test_a_skipped_check_is_unknown_and_never_refuses(tmp_path: Path) -> None:
    """`skipped` is the third state, and `--offline` is where it bites.

    An offline run records `genome_build_agreement` as skipped, with no subjects and no findings. That
    is *nobody asked*, not *nothing wrong*, and a gate reading it as either is broken — refusing would
    make `--offline` enrichment poison a module, and it already reports `findings=0`.
    """
    spec = _spec(
        tmp_path / "spec",
        records=[
            VerificationRecord(
                check=BUILD_AGREEMENT_CHECK,
                subjects=0,
                findings=0,
                skipped="offline",
                source="ensembl-grch37",
            )
        ],
    )

    assert compile_module(spec, tmp_path / "out", strict=True).success


@pytest.mark.parametrize(
    "check", ["reference_allele", "clinical_significance", "rsid_currency", "citation_existence"]
)
def test_every_other_recorded_finding_still_only_warns(tmp_path: Path, check: str) -> None:
    """The strict line does not move, and this is the assertion that holds it there.

    A recorded finding on any other check is the module disagreeing with an outside archive, where the
    archive is the stale side often enough that failing a build would have the format arbitrate
    someone else's dispute — the same reasoning that keeps the ClinVar cross-check a warning under
    `strict`. `reference_allele` is the one worth naming: it is the check that *produces* the
    wrong-build diagnosis's input, and it still does not refuse on its own, because a mismatched ref
    has three causes and only one of them is an assembly.
    """
    spec = _spec(
        tmp_path / "spec",
        records=[VerificationRecord(check=check, subjects=10, findings=3, source="seqrepo")],
    )

    compiled = compile_module(spec, tmp_path / "out", strict=True)

    assert compiled.success, compiled.errors
    assert any("verification.json records" in w for w in compiled.warnings)


# ── the predicate itself ────────────────────────────────────────────────────────────────────────


def test_the_predicate_reads_findings_over_the_one_check() -> None:
    """Unit-level, so the three-way shape is pinned without a spec around it."""
    assert build_disagreement_error(None) is None

    def _block(*records: VerificationRecord) -> Verification:
        return Verification(
            module_hash="sha256:" + "0" * 64,
            verification_signature="sha256:" + "1" * 64,
            checks=list(records),
        )

    assert build_disagreement_error(_block()) is None
    assert build_disagreement_error(_block(_clean(BUILD_AGREEMENT_CHECK))) is None
    assert build_disagreement_error(_block(_diagnosed(findings=0))) is None
    # Counts come from the record rather than being recomputed, and both reach the message.
    message = build_disagreement_error(_block(_diagnosed(findings=4, subjects=9)))
    assert message is not None
    assert "4 row(s) of 9" in message
