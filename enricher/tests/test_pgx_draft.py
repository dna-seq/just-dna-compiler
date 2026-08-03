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
    # Reported as a *bound*, and distinguished from CPIC's `n/a` — which means "not scored" and is an
    # absence, not an inequality. Both used to get the same (wrong) message, one line per row.
    bounds = [w for w in result.warnings if "≥3.0" in w]
    assert bounds, result.warnings
    assert "bound rather than a value" in bounds[0]
    assert "not scored" not in bounds[0]
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


# ── What drafting a real gene exposed (0.5.1) ───────────────────────────────────────────────────
# `draft --gene CYP2C19` looked fine; `--gene CYP2C9` died on an unhandled pydantic error. The
# difference is data CPIC publishes for one gene and not the other, so the tests below are built from
# the shapes rather than from a gene name.

from just_dna_enricher.cpic import CpicDefiningVariant
from just_dna_enricher.pgx_draft import _haplotype_rows


def _variant(**kw) -> CpicDefiningVariant:
    base = dict(gene="CYP2C9", allele="*57", rsid=None, chrom=None, start=None,
                variant_allele="T", ambiguous=False)
    base.update(kw)
    return CpicDefiningVariant(**base)


def test_a_position_without_a_chromosome_is_skipped_not_written() -> None:
    """The crash: the guard accepted a bare `start`, but `HaplotypeRow` needs rsid, or chrom AND
    start — and CPIC publishes no chromosome, so the row could never validate. 18 CYP2C9 defining
    variants are shaped this way (also 14 in TPMT, 4 in NUDT15); CYP2C19 has none."""
    rows, warnings = _haplotype_rows([_variant(start=94947907)])
    assert rows == []
    assert warnings and "no complete coordinate" in warnings[0]


def test_the_guard_matches_the_models_own_rule() -> None:
    """Derived from `HaplotypeRow` rather than restated: whatever the model accepts, the guard keeps.

    A guard that does not match the model it builds is not a guard — which is exactly how the crash
    got shipped."""
    cases = [
        _variant(rsid="rs1799853"),                       # rsid alone: accepted
        _variant(chrom="10", start=94947907),             # full coordinate: accepted
        _variant(start=94947907),                         # position only: refused by the model
        _variant(chrom="10"),                             # chromosome only: refused by the model
        _variant(),                                       # nothing: refused by the model
    ]
    for case in cases:
        kept = bool(_haplotype_rows([case])[0])
        try:
            HaplotypeRow(haplotype_name=case.allele, rsid=case.rsid, chrom=case.chrom,
                         start=case.start, allele=case.variant_allele, gene=case.gene)
            model_accepts = True
        except Exception:
            model_accepts = False
        assert kept == model_accepts, f"guard and model disagree for {case}"


def test_an_ambiguous_iupac_allele_is_still_skipped() -> None:
    rows, _ = _haplotype_rows([_variant(rsid="rs1799853", variant_allele="R", ambiguous=True)])
    assert rows == []


# ── CPIC prescribing recommendations (0.5.1) ────────────────────────────────────────────────────

from just_dna_enricher.cpic import CpicDiplotype, CpicRecommendation, map_classification
from just_dna_enricher.pgx_draft import _recommendation_rows


def _rec(phenotype: str, population: str, classification: str = "strong") -> CpicRecommendation:
    return CpicRecommendation(
        gene="CYP2C19", phenotype=phenotype, drug="clopidogrel", population=population,
        classification=classification, recommendation="Avoid standard dose.",
        implication="Reduced active metabolite.",
    )


_DIPS = [CpicDiplotype(gene="CYP2C19", diplotype="*2/*2", phenotype="Poor Metabolizer")]


def test_every_clinical_context_becomes_its_own_row() -> None:
    """RM29b (0.5.1) dissolved the refusal this test used to pin.

    CPIC scopes a recommendation to a clinical context and the contexts disagree. Without a column
    for it, drafting all of them collided on the duplicate-row key and drafting one asserted a
    context the author never chose, so `draft --drug` refused. `clinical_context` makes them distinct
    rows and hands the choice to the consumer, where it belongs — which indication a patient is being
    treated for is knowable at query time, not at authoring time.
    """
    recs = [_rec("Poor Metabolizer", p) for p in ("NVI", "CVI ACS PCI")]
    rows, warnings = _recommendation_rows(_DIPS, recs, population=None)
    assert {r.clinical_context for r in rows} == {"NVI", "CVI ACS PCI"}
    assert warnings == []


def test_the_contexts_are_distinct_rows_under_the_compilers_own_key() -> None:
    """The point of the column: these must not be duplicates, and the compiler decides that."""
    from just_dna_compiler.compiler import _TABLE_DUPE_KEYS

    recs = [_rec("Poor Metabolizer", "NVI", "moderate"),
            _rec("Poor Metabolizer", "CVI ACS PCI", "strong")]
    rows, _ = _recommendation_rows(_DIPS, recs, population=None)
    key = _TABLE_DUPE_KEYS[DiplotypeRow]
    assert len({key(r) for r in rows}) == len(rows) == 2
    # And they really disagree — which is why collapsing them would have lost a clinical statement.
    assert {r.recommendation_strength for r in rows} == {"strong", "moderate"}


def test_population_still_filters_for_an_author_who_wants_one_context() -> None:
    recs = [_rec("Poor Metabolizer", "NVI", "moderate"),
            _rec("Poor Metabolizer", "CVI ACS PCI", "strong")]
    rows, _ = _recommendation_rows(_DIPS, recs, population="NVI")
    assert [(r.clinical_context, r.recommendation_strength) for r in rows] == [("NVI", "moderate")]


def test_a_single_population_needs_no_choice() -> None:
    rows, warnings = _recommendation_rows(_DIPS, [_rec("Poor Metabolizer", "general")], population=None)
    assert len(rows) == 1 and warnings == []
    assert rows[0].drug == "clopidogrel" and rows[0].recommendation_strength == "strong"


def test_the_chosen_population_is_the_one_used() -> None:
    """The populations really differ — this is why the choice cannot be defaulted."""
    recs = [_rec("Poor Metabolizer", "NVI", "moderate"),
            _rec("Poor Metabolizer", "CVI ACS PCI", "strong")]
    strong, _ = _recommendation_rows(_DIPS, recs, population="CVI ACS PCI")
    moderate, _ = _recommendation_rows(_DIPS, recs, population="NVI")
    assert strong[0].recommendation_strength == "strong"
    assert moderate[0].recommendation_strength == "moderate"


def test_an_unknown_population_is_refused_with_the_real_choices() -> None:
    rows, warnings = _recommendation_rows(_DIPS, [_rec("Poor Metabolizer", "NVI")], population="nope")
    assert rows == [] and "Available" in warnings[0]


def test_a_phenotype_cpic_does_not_cover_gets_no_drug_row_and_is_reported() -> None:
    dips = _DIPS + [CpicDiplotype(gene="CYP2C19", diplotype="*1/*1", phenotype="Indeterminate")]
    rows, warnings = _recommendation_rows(dips, [_rec("Poor Metabolizer", "general")], population=None)
    assert len(rows) == 1
    assert warnings and "Indeterminate" in warnings[0]


def test_classification_maps_onto_the_vocabulary_and_drops_unclassified() -> None:
    from just_dna_format.vocab import VALID_RECOMMENDATION_STRENGTH

    for raw in ("Strong", "Moderate", "Optional", "No Recommendation"):
        assert map_classification(raw) in VALID_RECOMMENDATION_STRENGTH
    # `n/a` is CPIC saying it did not classify — an empty cell, never a vocabulary member
    assert map_classification("n/a") is None
    assert map_classification(None) is None


def test_the_conclusion_carries_cpics_own_two_halves() -> None:
    """Implication (what the genotype does) then recommendation (what to do) — transcribed, not
    summarized."""
    rows, _ = _recommendation_rows(_DIPS, [_rec("Poor Metabolizer", "general")], population=None)
    assert rows[0].conclusion == "Reduced active metabolite. Avoid standard dose."
