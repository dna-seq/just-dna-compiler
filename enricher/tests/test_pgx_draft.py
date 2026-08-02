"""The CPIC drafting provider (`just_dna_enricher.pgx_draft`, 0.5).

Payloads are trimmed from the real CPIC PostgREST responses, including the two shapes that do not map
onto this format — an IUPAC ambiguity code where a nucleotide is expected, and an activity score
written as an inequality — because coercing either of them is the mistake the provider exists to not
make. Nothing here opens a socket.
"""

from pathlib import Path

import httpx
import pytest
from just_dna_compiler.compiler import _load_csv_rows, validate_spec
from just_dna_format.pgx import AlleleFunctionRow, DiplotypeRow, HaplotypeRow

from just_dna_enricher.cpic import CpicClient
from just_dna_enricher.licensing import LicenseRefusal
from just_dna_enricher.pgx_draft import draft_gene

_YAML = (
    'schema_version: "1.0"\n'
    "module:\n  name: cyp2c19\n  title: T\n  report_title: T\n  description: d\n"
    "genome_build: GRCh38\n"
)

_ALLELES = [
    {"genesymbol": "CYP2C19", "name": "*1", "activityvalue": "1.0",
     "clinicalfunctionalstatus": "Normal function"},
    {"genesymbol": "CYP2C19", "name": "*2", "activityvalue": "0.0",
     "clinicalfunctionalstatus": "No function"},
    {"genesymbol": "CYP2C19", "name": "*17", "activityvalue": None,
     "clinicalfunctionalstatus": "Increased function"},
]
_DIPLOTYPES = [
    {"genesymbol": "CYP2C19", "diplotype": "*1/*1", "generesult": "Normal Metabolizer",
     "totalactivityscore": "2.0"},
    {"genesymbol": "CYP2C19", "diplotype": "*1/*2", "generesult": "Intermediate Metabolizer",
     "totalactivityscore": "1.0"},
    # The inequality shape: a bound, not a number.
    {"genesymbol": "CYP2C19", "diplotype": "*17/*17", "generesult": "Ultrarapid Metabolizer",
     "totalactivityscore": "≥3.0"},
]
_DEFINITIONS = [
    {"id": 1, "name": "*2", "genesymbol": "CYP2C19"},
    {"id": 2, "name": "*17", "genesymbol": "CYP2C19"},
]
_LOCATIONS = [
    {"alleledefinitionid": 1, "variantallele": "A",
     "sequence_location": {"genesymbol": "CYP2C19", "dbsnpid": "rs4244285", "position": 94781859}},
    # The IUPAC shape: `R` is "A or G", not a definite nucleotide.
    {"alleledefinitionid": 1, "variantallele": "R",
     "sequence_location": {"genesymbol": "CYP2C19", "dbsnpid": "rs58973490", "position": 94781999}},
    {"alleledefinitionid": 2, "variantallele": "T",
     "sequence_location": {"genesymbol": "CYP2C19", "dbsnpid": "rs12248560", "position": 94761900}},
]


def _client() -> CpicClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/allele"):
            return httpx.Response(200, json=_ALLELES)
        if path.endswith("/diplotype"):
            return httpx.Response(200, json=_DIPLOTYPES)
        if path.endswith("/allele_definition"):
            return httpx.Response(200, json=_DEFINITIONS)
        if path.endswith("/allele_location_value"):
            return httpx.Response(200, json=_LOCATIONS)
        return httpx.Response(404, json=[])

    return CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    return spec


def _rows(spec: Path, csv_name: str, model):
    rows, errors, _ = _load_csv_rows(spec / csv_name, model, csv_name)
    assert not errors, errors
    return rows


def test_drafting_a_gene_produces_a_module_that_validates(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = draft_gene(spec, "CYP2C19", declared_use="non_commercial", client=_client())
    assert result.added > 0
    assert validate_spec(spec).valid, validate_spec(spec).errors

    functions = {r.allele: r.function_status for r in _rows(spec, "allele_function.csv", AlleleFunctionRow)}
    assert functions == {"*1": "normal_function", "*2": "no_function", "*17": "increased_function"}

    diplotypes = {
        (r.haplotype_a, r.haplotype_b): r.phenotype
        for r in _rows(spec, "diplotypes.csv", DiplotypeRow)
    }
    assert diplotypes[("*1", "*2")] == "Intermediate Metabolizer"


def test_cpic_coordinates_are_stored_one_based_without_conversion(tmp_path: Path) -> None:
    # CPIC, PharmVar and this pipeline's own resolution independently agree on rs4244285 →
    # chr10:94781859. The instinctive `-1` is an off-by-one.
    spec = _spec(tmp_path)
    draft_gene(spec, "CYP2C19", declared_use="non_commercial", client=_client())
    by_rsid = {r.rsid: r for r in _rows(spec, "haplotypes.csv", HaplotypeRow)}
    assert by_rsid["rs4244285"].start == 94781859
    assert by_rsid["rs4244285"].haplotype_name == "*2"
    assert by_rsid["rs4244285"].allele == "A"


def test_an_iupac_ambiguity_code_is_reported_and_skipped(tmp_path: Path) -> None:
    # `R` means "A or G". Expanding it to two rows would invent two defining variants where CPIC
    # recorded one uncertainty; writing `R` would break the nucleotide grammar.
    spec = _spec(tmp_path)
    result = draft_gene(spec, "CYP2C19", declared_use="non_commercial", client=_client())
    assert any("IUPAC" in w and "rs58973490" not in w for w in result.warnings), result.warnings
    assert "rs58973490" not in {r.rsid for r in _rows(spec, "haplotypes.csv", HaplotypeRow)}


def test_an_inequality_activity_score_is_reported_not_invented(tmp_path: Path) -> None:
    # `"≥3.0"` is a bound. Guessing an upper limit for it would put a number in the module that CPIC
    # never stated.
    spec = _spec(tmp_path)
    result = draft_gene(spec, "CYP2C19", declared_use="non_commercial", client=_client())
    assert any("≥3.0" in w and "inequality" in w for w in result.warnings), result.warnings
    # …and the diplotype row itself still lands, since the phenotype is perfectly usable.
    pairs = {(r.haplotype_a, r.haplotype_b) for r in _rows(spec, "diplotypes.csv", DiplotypeRow)}
    assert ("*17", "*17") in pairs


def test_drafting_twice_is_idempotent(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    draft_gene(spec, "CYP2C19", declared_use="non_commercial", client=_client())
    before = {p.name: p.read_text(encoding="utf-8") for p in spec.glob("*.csv")}

    again = draft_gene(spec, "CYP2C19", declared_use="non_commercial", client=_client())
    assert again.added == 0
    assert {p.name: p.read_text(encoding="utf-8") for p in spec.glob("*.csv")} == before


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = draft_gene(spec, "CYP2C19", declared_use="non_commercial", client=_client(), dry_run=True)
    assert result.added > 0
    assert not list(spec.glob("*.csv"))


def test_a_commercial_declaration_refuses_before_anything_is_fetched(tmp_path: Path) -> None:
    # CPIC's terms bar sale, and the refusal belongs at acquisition: the terms are accepted by taking
    # the data, so refusing later would mean the copy already exists.
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(str(request.url))
        return httpx.Response(200, json=[])

    spec = _spec(tmp_path)
    with pytest.raises(LicenseRefusal):
        draft_gene(
            spec, "CYP2C19", declared_use="commercial",
            client=CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler))),
        )
    assert fetched == []
    assert not list(spec.glob("*.csv"))


def test_an_unstated_declaration_skips_rather_than_failing(tmp_path: Path) -> None:
    # Three states, not two. CPIC forbids sale, so `unstated` SKIPS (the user has asserted nothing and
    # the tool must not assert a purpose on their behalf) while `commercial` REFUSES. Only an explicit
    # non-commercial declaration proceeds.
    spec = _spec(tmp_path)
    skipped = draft_gene(spec, "CYP2C19", client=_client())  # default: unstated
    assert skipped.skipped and skipped.added == 0
    assert not list(spec.glob("*.csv"))
    assert any("skipped" in w for w in skipped.warnings)

    declared = draft_gene(spec, "CYP2C19", declared_use="non_commercial", client=_client())
    assert not declared.skipped and declared.added > 0
