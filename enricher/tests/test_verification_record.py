"""The enricher's half of RM45: passes record what they checked, and the record survives the next run.

The merge is what makes several commands share one document — `enrich` writes its four checks, a later
`literature` writes its three, and neither may erase the other's. That is the same load-merge-write
discipline `licensing.record_source_terms` has, for the same reason: a count of call sites goes stale,
one function does not.

**That second command was hypothetical when this file was written**, and it showed: the merge cases
below synthesise the second pass by hand, because `literature` reported its three checks to stdout and
let the record die with the process. `test_two_real_commands_land_in_one_document` is the same claim
put to two commands that exist, which is the only version of it that can catch a pass writing to the
wrong place or clobbering the other's block.
"""

import shutil
from pathlib import Path

import httpx
import pytest
from just_dna_compiler.compiler import authored_input_entries, compile_module
from just_dna_enricher import identifiers as identifiers_module
from just_dna_enricher.cli import app
from just_dna_enricher.enrich import _verification_records, enrich
from just_dna_enricher.identifiers import OntologyClient
from just_dna_enricher.literature import enrich_literature
from just_dna_enricher.net import PacingGate
from just_dna_enricher.resolver import PairCheck
from just_dna_enricher.verification import producer_label, ran, record_verification, skipped
from just_dna_format import verification as verification_module
from just_dna_format.layout import DERIVED_SUBDIR, VERIFICATION_JSON
from just_dna_format.verification import (
    attestation_failure,
    module_binding,
    read_verification,
)
from typer.testing import CliRunner

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
    # Every reference example is closed since 0.6 (RM73), so a fresh copy already carries a document.
    # Removed here because the claim is about this pass creating one, not about the corpus.
    (spec / VERIFICATION_JSON).unlink(missing_ok=True)
    assert record_verification([], spec, error=_Boom) is None
    assert not (spec / VERIFICATION_JSON).exists()


def test_a_run_leaves_a_closed_module_closed(tmp_path: Path) -> None:
    """The never-clobber trap, one column over from `SourceRow.dataset` and `draft_digest`.

    This pass rebuilds the document rather than editing it, so a field it did not know about is
    dropped by default — and the default here would be silent and in the wrong direction: enrichment
    writes only derived sidecars, which are outside the binding, so the ordinary case is that nothing
    an author closed has changed. Un-closing it on every run would train an author to stop closing.
    """
    spec = _module(tmp_path)  # the reference examples ship closed (RM73)
    before = read_verification(spec / VERIFICATION_JSON).closure
    assert before is not None

    doc = record_verification([ran("rsid_currency", subjects=12, findings=0)], spec, error=_Boom)
    assert doc.closure == before
    assert attestation_failure(doc, module_binding(authored_input_entries(spec))) is None


def test_a_run_after_an_authored_edit_drops_the_closure_rather_than_re_binding_it(
    tmp_path: Path,
) -> None:
    """The other half, and the one that matters: only the author may make this claim.

    Carrying the closure across an edit would have this pass assert *a human declared these bytes
    final* about bytes that human never saw — the machine closing the phase behind their back, which
    is exactly what the deliberate-act decision rules out. Dropped, never re-stamped.
    """
    spec = _module(tmp_path)
    variants = spec / "variants.csv"
    variants.write_text(variants.read_text().replace("hemochromatosis", "haemochromatosis"))

    doc = record_verification([ran("rsid_currency", subjects=12, findings=0)], spec, error=_Boom)
    assert doc.closure is None
    assert attestation_failure(doc, module_binding(authored_input_entries(spec))) is None


def test_the_document_is_bound_to_the_module_as_it_stands(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    doc = record_verification([ran("rsid_currency", subjects=12, findings=0)], spec, error=_Boom)
    assert doc is not None
    assert doc.module_hash == module_binding(authored_input_entries(spec))
    assert doc.producer == producer_label()
    assert read_verification(spec / VERIFICATION_JSON) == doc


def test_a_second_pass_adds_its_check_without_erasing_the_first(tmp_path: Path) -> None:
    """The merge mechanism itself, with the two record shapes side by side.

    Synthetic on purpose — it pins `ran` beside `skipped` in one document, which no pair of real
    commands is guaranteed to produce. The real two-command case is the test below it.
    """
    spec = _module(tmp_path)
    record_verification([ran("rsid_currency", subjects=12, findings=1)], spec, error=_Boom)
    record_verification(
        [skipped("gene_symbol_currency", "offline", detail="HGNC needs egress")], spec, error=_Boom
    )

    by_check = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}
    assert set(by_check) == {"rsid_currency", "gene_symbol_currency"}
    assert by_check["rsid_currency"].findings == 1
    assert by_check["gene_symbol_currency"].skipped == "offline"


def test_enrich_then_literature_land_in_one_document(tmp_path: Path) -> None:
    """`enrich` then `literature`, on one module, offline — seven records, none erased.

    The claim the module docstring of `just_dna_enricher.verification` makes, put to two commands that
    both write. Until `literature` was wired in there was no second writer at all, so the merge could
    only ever be exercised against a hand-built document; running the two in sequence is what would
    catch a pass resolving the sidecar path differently or replacing the file wholesale.

    Offline is the honest way to run it here: every record comes out a skip, which is itself the point
    — a run with no egress has to say *which* questions it could not put, and both commands do. Note
    that `provenance_quote` is `nothing_to_check` rather than `offline`: this module's citations carry
    no quote, so egress would not change the answer, and the reason that survives a re-run is the one
    recorded.
    """
    spec = _module(tmp_path)
    enrich(spec, offline=True, download=False)
    after_enrich = {r.check for r in read_verification(spec / VERIFICATION_JSON).records}

    enrich_literature(spec, offline=True)
    records = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}

    literature_checks = {"citation_existence", "citation_identifier", "provenance_quote"}
    assert literature_checks <= set(records)
    assert after_enrich <= set(records), "the second command must not erase the first's block"
    assert set(records) == after_enrich | literature_checks
    assert records["citation_existence"].skipped == "offline"
    assert records["citation_identifier"].skipped == "offline"
    assert records["provenance_quote"].skipped == "nothing_to_check"
    # One producer line and one nonce for the whole document, however many commands contributed.
    doc = read_verification(spec / VERIFICATION_JSON)
    assert doc.producer == producer_label() and doc.module_hash == module_binding(
        authored_input_entries(spec)
    )


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
        "pairs": PairCheck(not_checked="nothing_to_check"),
        "ensembl_ref": None,
        "currency": None,
        "refutation_findings": [],
        "refutation_subjects": None,
        "refutation_skip": "no_reference",
        "refutation_detail": "no_snapshot",
        "refutation_basis": None,
        "civic_ref": None,
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


def test_the_pair_denominator_excludes_what_the_reference_could_not_place() -> None:
    """The rsid↔coordinate record publishes what it compared, and says what it did not (RM45).

    A pair whose rsID the snapshot has no record of is a question never put. Counting it as a subject
    would put an unasked row inside a clean denominator — the same defect `_vrs_coverage` exists for,
    one check over — so it lands outside the count and inside the sentence.
    """
    from just_dna_enricher.grch37 import BuildDiagnosisResult
    from just_dna_enricher.sequences import RefCheck

    pairs = PairCheck(disagreements=["rs429358 authored at 19:999:T"], subjects=2, unknown=["rs1799945"])
    record = _records_for(
        RefCheck([], 0, "offline"), BuildDiagnosisResult(not_checked="skipped_offline"), pairs=pairs
    )["rsid_coordinate_agreement"]

    assert (record.subjects, record.findings) == (2, 1)
    assert record.skipped is None
    assert "rs1799945" in (record.detail or ""), "the unplaced pair has to be named"
    assert "rs429358" in (record.detail or "")


def test_a_pair_check_that_could_not_run_never_reads_as_one_that_did() -> None:
    """Every `not_checked` reason lands as a skip with its own sentence — F4's defect, pre-empted."""
    from just_dna_enricher.grch37 import BuildDiagnosisResult
    from just_dna_enricher.sequences import RefCheck

    details: set[str] = set()
    for reason in ("unsupported", "nothing_to_check", "offline", "no_reference"):
        record = _records_for(
            RefCheck([], 12),
            BuildDiagnosisResult(not_checked="no_ref_mismatches"),
            pairs=PairCheck(not_checked=reason),
        )["rsid_coordinate_agreement"]
        assert record.skipped == reason
        assert (record.subjects, record.findings) == (0, 0)
        details.add(record.detail or "")
    assert len(details) == 4, f"four reasons, four sentences — got {sorted(details)}"


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


# ── `vrs mint`, and the merge two real commands now exercise (D4-1) ─────────────────────────────
def test_vrs_mint_records_that_it_compared_nothing_rather_than_that_it_passed(
    tmp_path: Path,
) -> None:
    """A minting run ends with a number out of a number, and that number is not a comparison.

    What `vrs_allele_id` names is the cross-check — a source's own `ga4gh:VA.…` against the locally
    minted one — whose input is `mint_resolution_rows(source_ids=…)`. `resolution.csv` records ids
    and never where an id came from, so this command has nothing to fill that map from and the
    question was not put. Recording coverage as `subjects` would assert a comparison nobody made,
    which is the F4 shape; the coverage still travels, in `detail`, grouped by reason class.
    """
    spec = _module(tmp_path, "mt_common_deletion")
    result = CliRunner().invoke(app, ["vrs", "mint", str(spec), "--offline"])
    assert result.exit_code == 0, result.output

    by_check = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}
    record = by_check["vrs_allele_id"]
    assert record.skipped == "nothing_to_check"
    assert (record.subjects, record.findings) == (0, 0)
    assert "no source-reported allele id" in (record.detail or "")
    # The module's own coverage, and the gap named by reason class rather than per allele. This
    # example's MT common deletion is authored as `<DEL:4977>` — a **symbolic** allele (RM5), not an
    # indel: it names no sequence at all, so no run of any kind can mint an id for it, which is a
    # permanent reason class rather than the indel's "needs the reference sequence, so run online".
    # This assertion read "indel/MNV" when it was written, against a classification D1-2 was
    # concurrently correcting in the same batch; the merge is what caught the disagreement.
    assert "symbolic/structural allele" in (record.detail or "")
    assert "indel/MNV" not in (record.detail or ""), "a symbolic allele is not an indel (D1-2)"
    # The reference example arrives carrying an `enrich` attestation, and it survives: that is what
    # the merge is for, and until now no two real commands ever produced one document.
    assert "reference_allele" in by_check


def test_pgx_then_vrs_mint_land_in_one_document(tmp_path: Path) -> None:
    """`merge_records` was built and tested for a document no two commands produced (D4-1).

    `pgx` and `vrs mint` write different checks about one module, from separate processes in real
    use. Neither may erase the other's, and both are single-record runs, so a naive write would have
    left whichever ran last as the module's whole attestation.
    """
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    for argv in (
        ["pgx", str(spec), "--offline"],
        ["vrs", "mint", str(spec), "--offline"],
    ):
        result = CliRunner().invoke(app, argv)
        assert result.exit_code == 0, result.output

    by_check = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}
    assert {"allele_function", "vrs_allele_id"} <= set(by_check)
    # Offline with nothing declared: PharmVar and CPIC both forbid sale, so the pass consulted
    # neither — and that is a permission, not a network problem.
    assert by_check["allele_function"].skipped == "not_permitted"


# ── the two check commands (RM72) ───────────────────────────────────────────────────────────────


_HGNC_BANDS = {"HFE": "6p22.2"}


@pytest.fixture
def hgnc(monkeypatch):
    """HGNC over a mock transport, so the real `check_identifiers` path runs with no egress.

    The client is what is faked, never the pass: `check_identifiers` builds its own
    (`client or OntologyClient()`), so replacing the name in its module is what lets the command —
    argument parsing, report, records, write — run exactly as it does in production.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        symbol = str(request.url).rsplit("/", 1)[-1]
        band = _HGNC_BANDS.get(symbol)
        if band is None or "prev_symbol" in str(request.url):
            return httpx.Response(200, json={"response": {"numFound": 0, "docs": []}})
        return httpx.Response(200, json={"response": {"numFound": 1, "docs": [
            {"symbol": symbol, "status": "Approved", "hgnc_id": "HGNC:4886", "location": band}
        ]}})

    def build() -> OntologyClient:
        client = OntologyClient()
        client._client = httpx.Client(transport=httpx.MockTransport(handler))
        client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
        return client

    monkeypatch.setattr(identifiers_module, "OntologyClient", build)


def _acmg_snapshot(tmp_path: Path) -> Path:
    from just_dna_enricher.acmg_build import build_acmg_snapshot

    out = tmp_path / "acmg"
    build_acmg_snapshot(Path(__file__).resolve().parents[2] / "assets" / "acmg_sf_v3.3.xlsx", out)
    return out


def test_check_identifiers_records_the_three_questions_it_put(tmp_path: Path, hgnc) -> None:
    """Wired in RM72. Until then the command reported to stdout and let the record die.

    `--no-traits` is passed so the run needs HGNC alone, and it doubles as the `not_requested`
    case: a check the caller switched off is cleared by a flag, never by egress, so it must not read
    as the same absence as a source that could not be reached.
    """
    spec = _module(tmp_path, "grch37_build")
    result = CliRunner().invoke(app, ["check-identifiers", str(spec), "--no-traits"])
    assert result.exit_code == 0, result.output

    by_check = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}
    assert by_check["trait_currency"].skipped == "not_requested"
    symbols = by_check["gene_symbol_currency"]
    loci = by_check["gene_locus_agreement"]
    assert (symbols.subjects, symbols.findings, symbols.skipped) == (1, 0, None)
    # Three authored rows, every one of them carrying both a gene and a chromosome.
    assert (loci.subjects, loci.findings, loci.skipped) == (3, 0, None)
    assert (symbols.source, loci.source) == ("hgnc", "hgnc")


def test_check_identifiers_records_nothing_to_check_apart_from_not_requested(
    tmp_path: Path, hgnc
) -> None:
    """A module authoring no trait CURIE has nothing to ask OLS4 — which is not the same absence.

    Both spellings live in one document here on purpose: `not_requested` is a caller's choice and
    `nothing_to_check` is a property of the module, and a consumer branches on the difference.
    """
    spec = _module(tmp_path)
    result = CliRunner().invoke(app, ["check-identifiers", str(spec)])
    assert result.exit_code == 0, result.output

    doc = read_verification(spec / VERIFICATION_JSON)
    by_check = {r.check: r for r in doc.records}
    assert by_check["trait_currency"].skipped == "nothing_to_check"
    assert by_check["gene_symbol_currency"].subjects == 1  # HFE, and it is current
    # Every reference example is closed (RM73) and this command writes only a derived sidecar, so the
    # author's closure must come through untouched — a new writer that un-closed a module would train
    # an author to stop closing.
    assert doc.closure is not None


def test_check_identifiers_attests_when_the_registry_never_answers(tmp_path: Path, monkeypatch) -> None:
    """The run where the record matters most is the one with no report to print.

    A promise to *record that the question was put* has to hold when the question went unanswered, or
    it is false exactly where a reader needs it. The command exits 1 and says which registry failed;
    the document says `unreachable`, which is not the same as an absence (S20).
    """
    def refuse(*_args, **_kwargs):
        raise httpx.ConnectError("connection refused")

    def build() -> OntologyClient:
        client = OntologyClient()
        client._client = httpx.Client(transport=httpx.MockTransport(refuse))
        client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
        return client

    monkeypatch.setattr(identifiers_module, "OntologyClient", build)
    spec = _module(tmp_path, "grch37_build")
    result = CliRunner().invoke(app, ["check-identifiers", str(spec), "--no-traits"])
    assert result.exit_code == 1

    by_check = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}
    assert by_check["gene_symbol_currency"].skipped == "unreachable"
    assert by_check["gene_locus_agreement"].skipped == "unreachable"
    # A flag the caller set is still the truer reason: a registry being down does not make
    # `--no-traits` a network problem, and only one of the two is cleared by re-running.
    assert by_check["trait_currency"].skipped == "not_requested"


def test_check_acmg_on_a_module_with_no_variants_csv_is_not_attested_at_all(tmp_path: Path) -> None:
    """The check does not APPLY, which is not a skip — `enrich_clinpgx`'s rule, one command over.

    `acmg_sf` is a `variants.csv` column and **only** that, so with no such file there is no claim for
    this check to have an opinion about. Recording one would mine a nonce and put a
    `verification.json` on a module that never asked for one; `nothing_to_check` stays for a table
    that is there and carries no row in scope.

    **`check-identifiers` used to be asserted here beside it and no longer belongs (RM155/RM156).**
    `gene` and `trait_efo_id` are carried by nine authored tables each, four of them the PGx kinds
    this very module is built out of, so on this spec that command now reads three tables, finds
    CYP2C19, and attests — the question really was put. The rule it keeps is the one below: no
    id-bearing table, no attestation.
    """
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    assert not (spec / "variants.csv").exists()
    (spec / VERIFICATION_JSON).unlink(missing_ok=True)

    result = CliRunner().invoke(app, ["check-acmg", str(spec), "--offline"])
    assert result.exit_code == 0, result.output
    assert not (spec / VERIFICATION_JSON).exists()


def test_check_identifiers_is_not_attested_when_no_table_carries_an_identifier(
    tmp_path: Path,
) -> None:
    """The same rule, keyed on the roster rather than on one filename (RM156).

    A module carrying no table that declares `trait_efo_id` or `gene` has had no question put to it,
    so there is nothing to record having asked — and this reaches no registry, because the command
    returns before a client is built.
    """
    spec = tmp_path / "bare"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\n"
        "module:\n  name: bare\n  title: Bare\n  description: d\n  report_title: Bare\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["check-identifiers", str(spec)])
    assert result.exit_code == 0, result.output
    assert "nothing to check" in result.output
    assert not (spec / VERIFICATION_JSON).exists()


def test_check_acmg_records_the_list_it_read_and_the_rows_it_asked_about(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    result = CliRunner().invoke(
        app, ["check-acmg", str(spec), "--offline", "--sf-list", str(_acmg_snapshot(tmp_path))]
    )
    assert result.exit_code == 0, result.output

    record = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}[
        "acmg_secondary_findings"
    ]
    assert record.skipped is None and record.source == "acmg"
    # HFE is on the list and the example leaves the column blank throughout: every row is a note.
    assert record.findings == 0 and record.subjects > 0
    assert record.release and "note" in (record.detail or "")


def test_an_offline_re_run_does_not_downgrade_the_answer_the_document_holds(tmp_path: Path) -> None:
    """RM72(c), end to end and over unchanged authored bytes.

    Under the old unconditional newest-wins this second command rewrote a true
    `subjects=13, findings=0` verdict to `subjects=0, skipped=offline` — an answer turned into "never
    asked" by a run that learned nothing and changed nothing. Demonstrated on that rule before it was
    changed: with `merge_records` restored to a plain `dict.update`, the last two assertions fail
    with `skipped == 'offline'`.
    """
    spec = _module(tmp_path)
    snapshot = _acmg_snapshot(tmp_path)
    assert CliRunner().invoke(
        app, ["check-acmg", str(spec), "--offline", "--sf-list", str(snapshot)]
    ).exit_code == 0
    answered = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}[
        "acmg_secondary_findings"
    ]
    assert answered.skipped is None and answered.subjects > 0

    # The same module, untouched, checked again with no list to check against.
    result = CliRunner().invoke(app, ["check-acmg", str(spec), "--offline"])
    assert result.exit_code == 0, result.output

    kept = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}[
        "acmg_secondary_findings"
    ]
    assert kept.skipped is None
    assert (kept.subjects, kept.findings, kept.release) == (
        answered.subjects, answered.findings, answered.release
    )


def test_an_answer_over_bytes_that_moved_gives_way_to_this_runs_skip(tmp_path: Path) -> None:
    """The condition on that protection, and it is what keeps the fix from being a regression.

    A record earns its place by describing *this* module. Once `variants.csv` has changed it is about
    rows that no longer exist, so a fresh "could not ask" is the more honest of the two — the same
    test the closure already applies, and the behaviour `literature` relies on when a module's
    citations change.
    """
    spec = _module(tmp_path)
    snapshot = _acmg_snapshot(tmp_path)
    assert CliRunner().invoke(
        app, ["check-acmg", str(spec), "--offline", "--sf-list", str(snapshot)]
    ).exit_code == 0

    rows = (spec / "variants.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    (spec / "variants.csv").write_text("".join(rows[:-1]), encoding="utf-8")

    assert CliRunner().invoke(app, ["check-acmg", str(spec), "--offline"]).exit_code == 0
    kept = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}[
        "acmg_secondary_findings"
    ]
    assert kept.skipped == "offline"


def test_a_merge_does_not_restamp_the_record_it_carried_across(tmp_path: Path) -> None:
    """`producer` is per-record, so an older run's attribution survives a newer run's write (S71).

    The reported shape: a module carried a `clinical_significance` record put by 0.6.4, a later pass
    merged new records in, and the document then reported `producer: just-dna-enricher 0.6.6` for the
    whole file — including the record that release did not produce. The merge itself was right and is
    the point: `merge_records` deliberately keeps the older `ran` rather than letting this run's
    silence delete it, so the only thing that moved was the attribution.

    The older record is written by hand rather than by running an old release, which is the only way
    to have one: what is being pinned is that `record_verification` carries a foreign `producer`
    through untouched, not that any particular version string is produced.
    """
    spec = _module(tmp_path)
    old = ran("clinical_significance", subjects=141_616, findings=20, source="clinvar").model_copy(
        update={"producer": "just-dna-enricher 0.6.4", "checked_at": "2026-08-10T00:00:00Z"}
    )
    record_verification([old], spec, error=_Boom)
    record_verification([ran("rsid_currency", subjects=12, findings=1)], spec, error=_Boom)

    doc = read_verification(spec / VERIFICATION_JSON)
    by_check = {r.check: r for r in doc.records}
    assert set(by_check) == {"clinical_significance", "rsid_currency"}

    assert by_check["clinical_significance"].producer == "just-dna-enricher 0.6.4", (
        "the merge restamped a record it did not produce — the S71 defect"
    )
    assert by_check["rsid_currency"].producer == producer_label()
    # The document-level field is the honest one for what it now means: who last wrote the file.
    assert doc.producer == producer_label()


def test_producer_is_outside_the_fact_set_so_adding_it_moved_no_signature() -> None:
    """A new field on a record whose fact-hash is published has to be shown not to move it.

    `producer` is producer noise in exactly the sense `checked_at` is — *who* ran a check is a fact
    about the run, not about the module — so it stays out of `VERIFICATION_FACT_FIELDS`, and every
    `verification.signature` already published is unaffected.
    """
    from just_dna_format.verification import VERIFICATION_FACT_FIELDS, verification_signature

    assert "producer" not in VERIFICATION_FACT_FIELDS
    record = ran("reference_allele", subjects=30, findings=0, source="ensembl", release="113")
    assert verification_signature([record]) == verification_signature(
        [record.model_copy(update={"producer": None})]
    )


def test_a_record_written_before_this_field_reads_as_not_recorded(tmp_path: Path) -> None:
    """`None` is the honest value for an older record, and it is not any particular release.

    The three-valued rule the rest of the file follows: a document from 0.6.6 or earlier cannot say
    who put its checks, and defaulting it to the reading version would manufacture the exact false
    attribution this item is about.
    """
    from just_dna_format.manifest import VerificationRecord

    assert VerificationRecord(check="rsid_currency", subjects=1, findings=0).producer is None


def _conflict(key: str, authored: str, clinvar: str, *, opposed: bool):
    from just_dna_enricher.clinical import ClinSigConflict

    return ClinSigConflict(
        variant_key=key, genotype="A/G", chrom="1", start=1, ref="A", alt="G",
        authored=authored, authority_clin_sig=clinvar, review_stars=2, review_status="criteria_provided",
        condition=None, opposed=opposed,
    )


def test_the_clin_sig_check_now_names_the_rows_it_disagreed_with(tmp_path: Path) -> None:
    """`clinical_significance` was the only check whose findings survived nowhere (S70).

    Of the five `enrich()` records, `reference_allele` and `rsid_coordinate_agreement` carry a
    `detail`, and `rsid_currency` stamps its verdict onto the resolution rows themselves. This one
    passed `subjects`, `findings`, `source` and `release` and no detail — so a record reading
    `findings: 20, detail: null` left an author able neither to defend the twenty nor correct them,
    and re-running to see the log again costs the full ClinVar comparison.

    Grouped on `opposed`, which is the distinction the conflict already draws and the one that decides
    what to do about it.
    """
    from just_dna_enricher.enrich import _clin_sig_detail

    conflicts = [
        _conflict("1:100:A:G", "pathogenic", "benign", opposed=True),
        _conflict("1:200:A:G", "pathogenic", "likely_pathogenic", opposed=False),
        _conflict("1:300:A:G", "benign", "uncertain_significance", opposed=False),
    ]
    detail = _clin_sig_detail(conflicts)

    assert "1 opposed" in detail and "2 differing" in detail
    # Both values, so an author can see which side to check without re-running the comparison.
    assert "1:100:A:G (pathogenic vs benign)" in detail
    assert _clin_sig_detail([]) is None, "no conflicts is no detail, not an empty sentence"


def test_the_detail_aggregates_rather_than_listing_every_row() -> None:
    """It uses the shared `examples` rule, so 618,629 subjects cannot put a list in the message."""
    from just_dna_enricher.enrich import _clin_sig_detail
    from just_dna_enricher.verification import DETAIL_LIMIT

    many = [_conflict(f"1:{i}:A:G", "pathogenic", "benign", opposed=True) for i in range(40)]
    detail = _clin_sig_detail(many)
    assert "40 opposed" in detail
    assert f"and {40 - DETAIL_LIMIT} more" in detail
    assert detail.count("vs benign") == DETAIL_LIMIT


def test_every_check_member_has_an_emitter_or_says_it_is_reserved() -> None:
    """The claim `verification.py`'s docstring makes, as a walked set rather than a sentence.

    That paragraph has now been wrong three times — once naming a writer that did not exist, once
    missing two that did, and once carrying a total (*"fifteen of the seventeen"*) that went stale the
    moment a member landed. A number in prose is a registry nothing iterates, so the claim moves here:
    every emission site in the tier is discovered by walking the sources for a `ran(...)`/`skipped(...)`
    whose first argument is a literal, and the result must equal the vocabulary minus the members whose
    comment beside them says RESERVED.

    An EQUALITY, not a floor: a floor cannot see a member that lost its only emitter in a refactor,
    which is the direction the last three defects all ran.
    """
    import ast
    import pkgutil

    import just_dna_enricher
    from just_dna_format.vocab import VALID_VERIFICATION_CHECKS

    root = Path(just_dna_enricher.__path__[0])
    emitted: set[str] = set()
    for info in pkgutil.iter_modules(just_dna_enricher.__path__):
        source = (root / f"{info.name}.py").read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in {"ran", "skipped"} or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                emitted.add(first.value)

    #: Named rather than silently subtracted, so each one is a decision a reader can dispute — and
    #: each says RESERVED beside itself in `VALID_VERIFICATION_CHECKS`, with the reason.
    #: The 2026-09-01 source-adoption round put five names here ahead of their passes and every one
    #: of them has now left: RM163's two with `check-identifiers`' fourth registry, RM165's with
    #: `check-repeat-bands`, RM167's with `litvar coverage`, and RM166's `regulator_label_agreement`
    #: with `clinpgx check-labels`. What remains are the two long-standing members, both of which say
    #: RESERVED beside themselves in `VALID_VERIFICATION_CHECKS` with the reason.
    reserved = {
        "gene_disease_validity",
        "dosage_sensitivity",
    }
    assert emitted == VALID_VERIFICATION_CHECKS - reserved, sorted(
        emitted.symmetric_difference(VALID_VERIFICATION_CHECKS - reserved)
    )
