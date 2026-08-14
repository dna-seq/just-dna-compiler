"""The PGx pass and the licensing gate — network-free.

Live PharmVar/CPIC calls go through `httpx.MockTransport`, so nothing here opens a socket. The
payload fixtures are trimmed from **real** responses recorded on 2026-08-02, including the shapes
that caused trouble: PharmVar's per-reference-sequence variant rows (only the `NC_` one is genomic)
and CPIC's IUPAC ambiguity codes.
"""

import csv
from pathlib import Path

import httpx
import pytest
from just_dna_compiler.compiler import _load_csv_rows
from just_dna_enricher.cpic import CpicClient, map_function_status
from just_dna_enricher.licensing import (
    CLINPGX_TERMS,
    CPIC_TERMS,
    ENSEMBL_TERMS,
    PHARMVAR_TERMS,
    LicenseRefusal,
    SourceTerms,
    _cell,
    check_declared_use,
    write_sources_csv,
)
from just_dna_enricher.pgx import enrich_pgx
from just_dna_enricher.pharmvar import (
    API_KEY_ENV,
    API_KEY_HEADER,
    PharmVarClient,
    PharmVarError,
    chrom_from_accession,
    parse_allele,
)
from just_dna_format import verification as verification_module
from just_dna_format.manifest import VerificationRecord
from just_dna_format.sources import SourceRow
from just_dna_format.layout import SOURCES_CSV, VERIFICATION_JSON, preferred_spelling
from just_dna_format.verification import read_verification
from pydantic import ValidationError

#: The licence sidecar's current filename, derived rather than named: it gained a second
#: spelling in 0.6 (RM51) and the older one retires at 1.0, so a literal here would pin a test
#: to whichever spelling happened to be current when it was written.
_LICENCE_CSV = preferred_spelling(SOURCES_CSV)


@pytest.fixture(autouse=True)
def _no_ambient_pharmvar_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize a developer's real `PHARMVAR_API_KEY` for every test in this module.

    `PharmVarClient(api_key=None)` does **not** mean "no key" — the constructor falls through to
    `os.environ`, so an explicit `None` is indistinguishable from "not passed". Without this, a
    machine that has legitimately configured a key builds a *configured* client where the test
    intended a keyless one, PharmVar answers the `MockTransport` happily, and the assertions about
    degrading-without-a-key fail. The suite passed on CI and only ever broke for whoever had a key,
    which is the wrong way round. `test_eutils.py` already does this for `NCBI_API_KEY`.

    Set to empty rather than deleted, deliberately: `locations.load_env()` reloads the repo's `.env`
    into `os.environ` from any test that resolves a cache path, and `load_dotenv(override=False)`
    skips a key that is merely *present* — so an empty value survives that reload where a deleted one
    would be silently restored. Both readers treat empty as absent (`api_key or environ.get(...)`).
    """
    monkeypatch.setenv(API_KEY_ENV, "")


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pass attests now (RM45), and the real proof-of-work is ~0.5s of hashing per call.

    Eight bits keeps every test in this module honest about the *document* while paying for none of
    the difficulty — the same fixture `test_verification_record.py` carries, for the same reason.
    """
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", 8)


_YAML = (
    'schema_version: "1.0"\n'
    "module:\n  name: cyp\n  title: T\n  report_title: T\n  description: d\n"
)
# One deliberate error: *2 has no function, not normal function.
_ALLELE_FUNCTION = (
    "gene,allele,function_status\n"
    "CYP2C19,*1,normal_function\n"
    "CYP2C19,*2,normal_function\n"
)

# Trimmed from the real /genes/CYP2C19 response. `*2`'s variant appears three times, once per
# reference sequence; only the NC_ row carries a genomic coordinate.
_PHARMVAR_GENE = {
    "geneSymbol": "CYP2C19",
    "alleles": [
        {
            "geneSymbol": "CYP2C19", "alleleName": "CYP2C19*1", "alleleType": "Core",
            "function": "normal function", "variants": [],
        },
        {
            "geneSymbol": "CYP2C19", "alleleName": "CYP2C19*2", "alleleType": "Core",
            "function": "no function",
            # The real payload's shape, and the fixture used to be missing half of it. PharmVar emits
            # one row per reference sequence — transcript, then **GRCh37**, then GRCh38 — and lists
            # GRCh37 first, which is what made the first-wins merge store the wrong coordinate for 451
            # of 739 real defining variants. A one-assembly fixture could not see that; this one can.
            "variants": [
                {"rsId": "rs4244285", "referenceSequence": "NM_000769.4",
                 "referenceCollections": ["RefSeqTranscript"],
                 "hgvs": "NM_000769.4:c.681G>A"},
                {"rsId": "rs4244285", "referenceSequence": "NC_000010.10",
                 "referenceCollections": ["GRCh37"],
                 "hgvs": "NC_000010.10:g.96541616G>A"},
                {"rsId": "rs4244285", "referenceSequence": "NC_000010.11",
                 "referenceCollections": ["GRCh38"],
                 "hgvs": "NC_000010.11:g.94781859G>A"},
            ],
        },
        {   # a sub-allele — excluded by default, the core star is the identity
            "geneSymbol": "CYP2C19", "alleleName": "CYP2C19*2.001", "alleleType": "Sub",
            "function": "no function", "variants": [],
        },
    ],
}
_CPIC_ALLELES = [
    {"genesymbol": "CYP2C19", "name": "*1", "activityvalue": None,
     "clinicalfunctionalstatus": "Normal function"},
    {"genesymbol": "CYP2C19", "name": "*2", "activityvalue": None,
     "clinicalfunctionalstatus": "No function"},
]


def _spec(tmp_path: Path) -> Path:
    d = tmp_path / "spec"
    d.mkdir(parents=True)
    (d / "module_spec.yaml").write_text(_YAML)
    (d / "allele_function.csv").write_text(_ALLELE_FUNCTION)
    return d


def _pharmvar_client(recorder: list[httpx.Request] | None = None) -> PharmVarClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        if request.headers.get(API_KEY_HEADER) != "test-key":
            return httpx.Response(401, json={"errorMessage": "API Key is invalid or missing"})
        return httpx.Response(200, json=_PHARMVAR_GENE)

    return PharmVarClient(
        api_key="test-key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def _cpic_client() -> CpicClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_CPIC_ALLELES)

    return CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


# ── the terms themselves ────────────────────────────────────────────────────────────────────────
def test_no_pgx_source_permits_sale() -> None:
    """The finding that drove the design: CC BY-SA does NOT mean sellable here.

    All three layer a contractual bar on sale on top of the CC grant, so swapping ClinPGx for CPIC or
    PharmVar does not escape it. Pinned so a future edit cannot quietly flip one to `True`.
    """
    for terms in (CLINPGX_TERMS, CPIC_TERMS, PHARMVAR_TERMS):
        assert terms.license == "CC-BY-SA-4.0"
        assert terms.share_alike is True
        assert terms.commercial_use is False, f"{terms.source} must not be marked sellable"
    assert ENSEMBL_TERMS.commercial_use is True   # the contrast case


@pytest.mark.parametrize(
    "declared,expect",
    [("non_commercial", "proceed"), ("unstated", "skip"), ("commercial", "raise")],
)
def test_declared_use_gate(declared: str, expect: str) -> None:
    if expect == "raise":
        with pytest.raises(LicenseRefusal):
            check_declared_use(PHARMVAR_TERMS, declared)
        return
    reason = check_declared_use(PHARMVAR_TERMS, declared)
    assert (reason is None) == (expect == "proceed")


def test_unknown_terms_are_skipped_not_refused_and_not_used() -> None:
    """Unknown is neither permission nor a finding of prohibition — every declaration skips."""
    unknown = SourceTerms(source="mystery", commercial_use=None)
    for declared in ("unstated", "non_commercial", "commercial"):
        reason = check_declared_use(unknown, declared)
        assert reason is not None and "could not be established" in reason


def test_permissive_source_proceeds_under_any_declaration() -> None:
    for declared in ("unstated", "non_commercial", "commercial"):
        assert check_declared_use(ENSEMBL_TERMS, declared) is None


def test_every_declared_column_survives_a_write_read_cycle(tmp_path: Path) -> None:
    """`sources.csv` must carry every field of the row it was written from.

    The regression this pins: `SOURCES_FIELDNAMES` was a hand-kept literal that omitted
    `redistribution`, so a row stating `redistribution=True` reloaded as `None` — *unknown*, which in
    this codebase is deliberately not the same claim — and `merge_sources_file` dropped it again on
    every merge. Asserting field-by-field equality rather than naming the one column that was missing
    makes the next omission fail too. The old behaviour is demonstrated below by writing the same rows
    through the literal list that used to be there.
    """
    rows = [
        PHARMVAR_TERMS.row("annotation", declared_use="non_commercial", license_text="terms v1"),
        ENSEMBL_TERMS.row("resolution", declared_use="unstated"),
    ]
    path = tmp_path / _LICENCE_CSV
    write_sources_csv(rows, path)
    reloaded, errors, _ = _load_csv_rows(path, SourceRow, _LICENCE_CSV)
    assert not errors
    assert [r.model_dump() for r in reloaded] == [r.model_dump() for r in rows]
    # …and the axis RM27 is designed to read is a real value, not the absence of one.
    assert [r.redistribution for r in reloaded] == [True, True]

    stale = ["source", "layer", "license", "license_url", "license_sha256", "attribution",
             "notice", "share_alike", "commercial_use", "declared_use", "dataset", "fetched_at"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=stale)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in stale})
    dropped, _, _ = _load_csv_rows(path, SourceRow, _LICENCE_CSV)
    assert [r.redistribution for r in dropped] == [None, None]


def test_license_sha256_pins_the_terms_to_the_text() -> None:
    """A licence read from the payload is hashed; one that was not read stays null, never faked."""
    read = PHARMVAR_TERMS.row("annotation", declared_use="non_commercial", license_text="terms v1")
    changed = PHARMVAR_TERMS.row("annotation", declared_use="non_commercial", license_text="terms v2")
    unread = PHARMVAR_TERMS.row("annotation", declared_use="non_commercial")
    assert read.license_sha256 and read.license_sha256.startswith("sha256:")
    assert read.license_sha256 != changed.license_sha256
    assert unread.license_sha256 is None


# ── the clients ─────────────────────────────────────────────────────────────────────────────────
def test_pharmvar_parses_only_the_genomic_reference_sequence() -> None:
    """A variant repeats per reference sequence; only `NC_` is a genomic coordinate."""
    allele = parse_allele(_PHARMVAR_GENE["alleles"][1])
    assert allele.allele == "CYP2C19*2" and allele.function == "no function"
    # Three source rows — transcript, GRCh37, GRCh38 — one variant.
    assert len(allele.variants) == 1
    v = allele.variants[0]
    assert (v.rsid, v.chrom, v.start, v.ref, v.alt) == ("rs4244285", "10", 94781859, "G", "A")


def test_pharmvar_takes_the_coordinate_from_grch38_not_the_first_nc_row() -> None:
    """PharmVar lists GRCh37 first, and first-wins stored it. rs4244285 is 96541616 on GRCh37.

    Demonstrated on the old behaviour rather than asserted about it: dropping the assembly filter
    (`build=""` matches no `referenceCollections` entry, so nothing is taken; `build="GRCh37"` is the
    coordinate the unfiltered merge used to return) shows both halves of the fix.
    """
    payload = _PHARMVAR_GENE["alleles"][1]
    grch37 = parse_allele(payload, build="GRCh37").variants[0]
    grch38 = parse_allele(payload, build="GRCh38").variants[0]
    assert grch37.start == 96541616 and grch38.start == 94781859
    assert grch37.rsid == grch38.rsid == "rs4244285"     # same variant, two frames
    # 227 bp apart at this locus — silently wrong, never absent, which is the dangerous shape.
    assert grch37.start != grch38.start

    # And a build the payload does not carry yields no position at all rather than a guessed one,
    # while keeping the identity: the row is honestly unplaced, not fabricated.
    unplaced = parse_allele(payload, build="GRCh39").variants[0]
    assert unplaced.rsid == "rs4244285" and unplaced.start is None and unplaced.chrom is None


def test_pharmvar_positions_are_one_based() -> None:
    """Matches Ensembl and CPIC for rs4244285; the instinctive -1 would be an off-by-one."""
    allele = parse_allele(_PHARMVAR_GENE["alleles"][1])
    assert allele.variants[0].start == 94781859


def test_accession_mapping_refuses_to_guess() -> None:
    assert chrom_from_accession("000010") == "10"
    assert chrom_from_accession("000023") == "X"
    assert chrom_from_accession("000024") == "Y"
    assert chrom_from_accession("012920") is None    # MT/unplaced — None rather than a guess


def test_pharmvar_uses_the_documented_header_and_never_leaks_the_key() -> None:
    recorder: list[httpx.Request] = []
    client = _pharmvar_client(recorder)
    client.alleles_for_gene("CYP2C19")
    assert recorder[0].headers[API_KEY_HEADER] == "test-key"
    assert "X-API-KEY" not in recorder[0].headers     # the wrong name that 401s identically
    assert "test-key" not in str(recorder[0].url)     # never in the query string


def test_pharmvar_401_is_a_clear_error_not_a_retry_storm() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"errorMessage": "API Key is invalid or missing"})

    client = PharmVarClient(
        api_key="bad", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(PharmVarError) as exc:
        client.alleles_for_gene("CYP2C19")
    assert "PHARMVAR_API_KEY" in str(exc.value)
    assert "bad" not in str(exc.value)                # the key itself is never echoed


def test_sub_alleles_are_excluded_by_default() -> None:
    alleles = _pharmvar_client().alleles_for_gene("CYP2C19")
    assert {a.allele for a in alleles} == {"CYP2C19*1", "CYP2C19*2"}   # *2.001 dropped


def test_cpic_function_prose_maps_onto_the_closed_vocabulary() -> None:
    assert map_function_status("No function") == "no_function"
    assert map_function_status("Possible Decreased Function") == "uncertain_function"
    assert map_function_status("something new") is None     # unmapped → None, never guessed


# ── the pass ────────────────────────────────────────────────────────────────────────────────────
def test_pass_refuses_a_commercial_declaration_and_fetches_nothing(tmp_path: Path) -> None:
    recorder: list[httpx.Request] = []
    with pytest.raises(LicenseRefusal):
        enrich_pgx(
            _spec(tmp_path), declared_use="commercial",
            pharmvar_client=_pharmvar_client(recorder), cpic_client=_cpic_client(),
        )
    assert recorder == []          # refused at acquisition — nothing was taken
    assert not (tmp_path / "spec" / _LICENCE_CSV).exists()


def test_pass_skips_when_nothing_is_declared(tmp_path: Path) -> None:
    """Conservative default: the tool must not assert a purpose on the user's behalf."""
    recorder: list[httpx.Request] = []
    result = enrich_pgx(
        _spec(tmp_path), declared_use="unstated",
        pharmvar_client=_pharmvar_client(recorder), cpic_client=_cpic_client(),
    )
    assert recorder == []
    assert result.rows == [] and len(result.skipped) == 2


def test_pass_cross_checks_and_records_terms(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = enrich_pgx(
        spec, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    # Both authorities independently contradict the authored *2 — and agree with each other.
    assert {(c.source, c.allele, c.reported) for c in result.conflicts} == {
        ("pharmvar", "*2", "no_function"),
        ("cpic", "*2", "no_function"),
    }
    # ...and the correctly-authored *1 is silent.
    assert all(c.allele != "*1" for c in result.conflicts)
    # Never repaired: the authored file is untouched.
    assert "CYP2C19,*2,normal_function" in (spec / "allele_function.csv").read_text()

    assert {r.source for r in result.rows} == {"pharmvar", "cpic"}
    assert all(r.layer == "annotation" for r in result.rows)
    assert all(r.declared_use == "non_commercial" for r in result.rows)
    assert (spec / _LICENCE_CSV).is_file()


def test_offline_with_no_snapshot_makes_zero_requests_and_says_why(tmp_path: Path) -> None:
    """`--offline` was a no-op that warned; now it is snapshot-only, and the guarantee is the same.

    An **injected live client is not a loophole**: `offline` outranks the injection, because a live
    client under a flag documented as making no egress is exactly the failure RM38 closes. With no
    snapshot to fall back to, each leg lands in `skipped_offline` — which is a third state, not a
    warning and not a silent pass.
    """
    recorder: list[httpx.Request] = []
    result = enrich_pgx(
        _spec(tmp_path), offline=True, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(recorder), cpic_client=_cpic_client(),
        cpic_cache=tmp_path / "absent", pharmvar_cache=tmp_path / "absent",
    )
    assert recorder == [] and result.rows == [] and result.routes == {}
    assert len(result.skipped_offline) == 2
    assert {"pharmvar", "cpic"} == {w.split(":")[0] for w in result.skipped_offline}


def test_existing_sources_rows_are_never_clobbered(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    (spec / _LICENCE_CSV).write_text(
        "source,layer,license,commercial_use,declared_use\n"
        "pharmvar,annotation,HAND-EDITED,false,non_commercial\n"
    )
    result = enrich_pgx(
        spec, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    kept = next(r for r in result.rows if r.source == "pharmvar")
    assert kept.license == "HAND-EDITED"        # human row wins, exactly as in enrich()


def test_one_source_failing_does_not_sink_the_pass(tmp_path: Path) -> None:
    """PharmVar without a key must not cost the CPIC cross-check."""
    keyless = PharmVarClient(api_key=None, client=httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_PHARMVAR_GENE))
    ))
    result = enrich_pgx(
        _spec(tmp_path), declared_use="non_commercial",
        pharmvar_client=keyless, cpic_client=_cpic_client(),
    )
    assert [r.source for r in result.rows] == ["cpic"]
    assert any("PharmVar API key" in w or "PHARMVAR_API_KEY" in w for w in result.warnings)
    assert {c.source for c in result.conflicts} == {"cpic"}


# ── the attestation (RM45, D4-1) ────────────────────────────────────────────────────────────────
def _record(spec: Path) -> VerificationRecord:
    """The one `allele_function` record the pass wrote, read back from the file it wrote."""
    doc = read_verification(spec / VERIFICATION_JSON)
    return next(r for r in doc.records if r.check == "allele_function")


def test_the_cross_check_records_what_it_compared(tmp_path: Path) -> None:
    """The pass consulted two authorities about two alleles; the module now says so.

    Until this landed the finding reached stdout and a `PgxResult` field and died with the process,
    so a module whose star alleles had been checked against PharmVar and CPIC and one where the
    check never ran compiled to identical manifests — the sentence RM45 opens with.
    """
    spec = _spec(tmp_path)
    result = enrich_pgx(
        spec, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    record = _record(spec)
    assert record.skipped is None
    # Both authorities name both authored alleles, so both claims were really compared.
    assert record.subjects == result.compared == 2
    # ONE allele is in dispute — reported twice, once per authority. Counting conflicts would say 2.
    assert record.findings == 1 and len(result.conflicts) == 2
    # Two authorities answer one check and `source` is a single join key into the licensing table, so
    # it names one only when one is implicated; the sentence carries both.
    assert record.source is None
    # The route travels with the name — an injected client here, a snapshot or the live service in
    # a real run, and a pinned release beside it where the source states one.
    assert "pharmvar (injected)" in record.detail and "cpic (injected)" in record.detail


def test_two_authorities_disputing_one_allele_is_one_finding_not_two(tmp_path: Path) -> None:
    """The naive count is not merely imprecise — the model refuses the record it builds.

    `VerificationRecord` rejects `findings > subjects` ("a finding is one of the rows the check was
    evaluated over"), and one authored allele contradicted by both PharmVar and CPIC is exactly that
    shape. Demonstrated on the failing construction rather than asserted about it.
    """
    spec = _spec(tmp_path)
    (spec / "allele_function.csv").write_text(
        "gene,allele,function_status\nCYP2C19,*2,normal_function\n"
    )
    result = enrich_pgx(
        spec, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    assert len(result.conflicts) == 2 and result.compared == 1
    with pytest.raises(ValidationError):
        VerificationRecord(
            check="allele_function", subjects=result.compared, findings=len(result.conflicts)
        )
    record = _record(spec)
    assert (record.subjects, record.findings) == (1, 1)


def test_a_claim_no_authority_lists_is_not_counted_as_compared(tmp_path: Path) -> None:
    """`subjects` is alleles an authority named back, never authored rows.

    `*17` is a real CYP2C19 allele that neither fixture payload carries, which is the ordinary case:
    a source is a point-in-time slice and a curator may state a function for an allele it does not
    list. Counting that row would publish a comparison that was never put — and the shortfall has to
    be visible, so the sentence names it.
    """
    spec = _spec(tmp_path)
    (spec / "allele_function.csv").write_text(
        _ALLELE_FUNCTION + "CYP2C19,*17,increased_function\n"
    )
    enrich_pgx(
        spec, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    record = _record(spec)
    assert record.subjects == 2
    assert (
        "1 authored claim(s) name an allele no consulted authority states a function for"
        in record.detail
    )


def test_a_module_stating_no_function_is_nothing_to_check_even_when_both_answered(
    tmp_path: Path,
) -> None:
    """Zero out of zero would read as agreement, and both authorities did answer here.

    A module may define its haplotypes and state no function for any of them — `function_status` is
    optional. There is then no authored claim for an authority to disagree with, which is a different
    fact from every claim having been upheld.
    """
    spec = _spec(tmp_path)
    (spec / "allele_function.csv").unlink()
    (spec / "haplotypes.csv").write_text(
        "gene,haplotype_name,rsid,allele\nCYP2C19,*2,rs4244285,A\n"
    )
    result = enrich_pgx(
        spec, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    assert set(result.routes) == {"pharmvar", "cpic"}      # both answered
    record = _record(spec)
    assert record.skipped == "nothing_to_check" and record.subjects == 0


def test_a_run_that_reached_no_authority_never_reads_as_clean(tmp_path: Path) -> None:
    """Offline with no snapshot: the check did not run, and the record says which absence it was."""
    spec = _spec(tmp_path)
    enrich_pgx(
        spec, offline=True, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
        cpic_cache=tmp_path / "absent", pharmvar_cache=tmp_path / "absent",
    )
    record = _record(spec)
    assert record.skipped == "offline" and record.subjects == 0
    # Both legs are named: a reason naming one leg says nothing about the other.
    assert "pharmvar" in record.detail and "cpic" in record.detail


def test_a_licence_refusal_is_not_a_connectivity_problem(tmp_path: Path) -> None:
    """`not_permitted` rather than `offline`: this one is cleared by a declaration, not by egress.

    The pass ran online with two working clients and consulted neither, because nothing was declared
    and both sources forbid sale. Folding that into `offline` would send a reader hunting a network
    problem that does not exist — which is why the vocabulary keeps the two apart.
    """
    spec = _spec(tmp_path)
    enrich_pgx(
        spec, declared_use="unstated",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    record = _record(spec)
    assert record.skipped == "not_permitted" and record.subjects == 0
    assert "--use non-commercial" in record.detail


def test_a_leg_the_caller_switched_off_is_not_the_reason_the_other_was_absent(
    tmp_path: Path,
) -> None:
    """One leg off, the other with nothing provisioned — the record names the actionable absence.

    Precedence exists because both legs record an outcome and the record carries one reason. A
    `not_requested` here would describe the caller's own choice and hide the leg that could have
    answered, which is the half the author can act on.

    The reason is `no_reference` and not `unreachable`: a keyless PharmVar was never *asked*. Nothing
    was provisioned that could answer — no snapshot, and no usable live route — and the remedy is a
    key or a built snapshot, where `unreachable` would send the reader to retry a request that was
    never made.
    """
    spec = _spec(tmp_path)
    keyless = PharmVarClient(api_key=None, client=httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_PHARMVAR_GENE))
    ))
    enrich_pgx(spec, declared_use="non_commercial", use_cpic=False, pharmvar_client=keyless)
    record = _record(spec)
    assert record.skipped == "no_reference"
    # One authority is implicated, so the join key is filled.
    assert record.source == "pharmvar"
    assert "PHARMVAR_API_KEY" in record.detail


def test_a_source_that_was_asked_and_gave_no_answer_is_unreachable(tmp_path: Path) -> None:
    """The other half of the pair: the request was made, and it produced no answer.

    A key that PharmVar rejects resolves a perfectly good client — the leg has something to ask with,
    so it asks, and the 401 comes back from the request itself. That is the branch `unreachable`
    describes, and keeping it distinct from `no_reference` is the whole point: one reader re-runs,
    the other provisions.
    """
    spec = _spec(tmp_path)
    rejected = PharmVarClient(api_key="stale-key", client=httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(401, json={"errorMessage": "API Key is invalid or missing"})
        )
    ))
    enrich_pgx(spec, declared_use="non_commercial", use_cpic=False, pharmvar_client=rejected)
    record = _record(spec)
    assert record.skipped == "unreachable" and record.source == "pharmvar"


def test_a_module_with_no_pgx_table_is_not_attested_at_all(tmp_path: Path) -> None:
    """The check does not *apply*, which is not the same as having failed to run.

    `clinpgx` refuses to attest this case for a reason that holds here too: a module carrying neither
    PGx table has no star allele for PharmVar or CPIC to have an opinion about, so a record would
    mine a nonce and publish a `manifest.verification` block about a question the module cannot pose.
    `nothing_to_check` stays for a table that is present with nothing in scope — the case above.
    """
    spec = _spec(tmp_path)
    (spec / "allele_function.csv").unlink()
    result = enrich_pgx(
        spec, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    assert result.warnings and "names no genes" in result.warnings[0]
    assert not (spec / VERIFICATION_JSON).exists()


def test_a_dry_run_writes_no_attestation(tmp_path: Path) -> None:
    """`write=False` means no files, and an attestation is a file."""
    spec = _spec(tmp_path)
    enrich_pgx(
        spec, declared_use="non_commercial", write=False,
        pharmvar_client=_pharmvar_client(), cpic_client=_cpic_client(),
    )
    assert not (spec / VERIFICATION_JSON).exists()
