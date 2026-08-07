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
    API_KEY_HEADER,
    PharmVarClient,
    PharmVarError,
    chrom_from_accession,
    parse_allele,
)
from just_dna_format.sources import SourceRow

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
            "variants": [
                {"rsId": "rs4244285", "referenceSequence": "NM_000769.4",
                 "hgvs": "NM_000769.4:c.681G>A"},
                {"rsId": "rs4244285", "referenceSequence": "NC_000010.11",
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
    path = tmp_path / "sources.csv"
    write_sources_csv(rows, path)
    reloaded, errors, _ = _load_csv_rows(path, SourceRow, "sources.csv")
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
    dropped, _, _ = _load_csv_rows(path, SourceRow, "sources.csv")
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
    assert len(allele.variants) == 1          # the transcript row merged into the genomic one
    v = allele.variants[0]
    assert (v.rsid, v.chrom, v.start, v.ref, v.alt) == ("rs4244285", "10", 94781859, "G", "A")


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
    assert not (tmp_path / "spec" / "sources.csv").exists()


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
    assert (spec / "sources.csv").is_file()


def test_offline_is_a_noop_not_a_failure(tmp_path: Path) -> None:
    recorder: list[httpx.Request] = []
    result = enrich_pgx(
        _spec(tmp_path), offline=True, declared_use="non_commercial",
        pharmvar_client=_pharmvar_client(recorder), cpic_client=_cpic_client(),
    )
    assert recorder == [] and result.rows == [] and result.warnings


def test_existing_sources_rows_are_never_clobbered(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    (spec / "sources.csv").write_text(
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
