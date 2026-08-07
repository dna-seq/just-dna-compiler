"""The CPIC drafting provider (`just_dna_enricher.pgx_draft`, 0.5).

Payloads are trimmed from the real CPIC PostgREST responses, including the shapes that do not map onto
this format — an IUPAC ambiguity code where a nucleotide is expected, and an activity score written as an
inequality — because coercing either of them is the mistake the provider exists to not make. The third
such shape (CYP2D6's `DELTCT` / `AAAGGGGCG(2)` notations, which are *not* ambiguity codes) is exercised
against its classifier with the real values rather than invented into a CYP2C19 fixture. Nothing here
opens a socket.
"""

from pathlib import Path

import httpx
import pytest
from just_dna_compiler.compiler import _load_csv_rows, validate_spec
from just_dna_enricher.cpic import (
    CpicClient,
    CpicDefiningVariant,
    CpicDiplotype,
    CpicError,
    CpicRecommendation,
    map_classification,
    normalize_chrom,
)
from just_dna_enricher.licensing import LicenseRefusal
from just_dna_enricher.pgx_draft import _haplotype_rows, _recommendation_rows, draft_gene
from just_dna_format.pgx import AlleleFunctionRow, DiplotypeRow, HaplotypeRow

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


# CPIC's `gene` table — where the chromosome actually lives. `sequence_location` has none, which is
# what an earlier probe saw and concluded CPIC publishes none at all; `gene.chr` does, and joining it
# on the symbol the location row already carries is what makes a coordinate-only defining variant
# draftable instead of skipped.
_GENES = [{"symbol": "CYP2C19", "chr": "chr10"}]


def _client() -> CpicClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/gene"):
            return httpx.Response(200, json=_GENES)
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


def _variant(**kw) -> CpicDefiningVariant:
    base = {'gene': "CYP2C9", 'allele': "*57", 'rsid': None, 'chrom': None, 'start': None,
                'variant_allele': "T", 'unusable': None}
    base.update(kw)
    return CpicDefiningVariant(**base)


def test_a_position_without_a_chromosome_is_skipped_not_written() -> None:
    """The crash: the guard accepted a bare `start`, but `HaplotypeRow` needs rsid, or chrom AND start.

    Still refused, and it must be — a bare position identifies no locus. What changed in 0.5.1 is that
    far fewer rows arrive this way: the chromosome those 36 real variants (18 CYP2C9, 14 TPMT, 4
    NUDT15) were missing is published on CPIC's `gene` table, so `defining_variants` now supplies it and
    the row below is the residue rather than the common case. The guard is unchanged.
    """
    rows, warnings = _haplotype_rows([_variant(start=94947907)])
    assert rows == []
    assert warnings and "no usable locus" in warnings[0]


def test_cpic_supplies_the_chromosome_from_its_gene_table(tmp_path: Path) -> None:
    """The 36 coordinate-only defining variants are drafted now, not skipped.

    Demonstrated on the old behaviour: with `gene.chr` withheld — which is what the client used to do
    unconditionally, since it never asked — the row is refused by the very guard above, and with it
    supplied the row is written and validates. Real CYP2C9 shape: a position and no rsID.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/gene"):
            return httpx.Response(200, json=[{"symbol": "CYP2C9", "chr": "chr10"}])
        if path.endswith("/allele"):
            return httpx.Response(200, json=[
                {"genesymbol": "CYP2C9", "name": "*57", "activityvalue": None,
                 "clinicalfunctionalstatus": "Uncertain function"},
            ])
        if path.endswith("/diplotype"):
            return httpx.Response(200, json=[])
        if path.endswith("/allele_definition"):
            return httpx.Response(200, json=[{"id": 9, "name": "*57", "genesymbol": "CYP2C9"}])
        if path.endswith("/allele_location_value"):
            return httpx.Response(200, json=[
                # CPIC's real shape for these: a position, no dbsnpid.
                {"alleledefinitionid": 9, "variantallele": "G",
                 "sequence_location": {"genesymbol": "CYP2C9", "dbsnpid": None,
                                       "position": 94947907}},
            ])
        return httpx.Response(404, json=[])

    client = CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    variants, _ = client.defining_variants("CYP2C9")
    assert [(v.rsid, v.chrom, v.start) for v in variants] == [(None, "10", 94947907)]

    # The old behaviour, reproduced: no chromosome, so the guard refuses and nothing is written.
    without_chrom = [_variant(allele="*57", gene="CYP2C9", start=94947907)]
    assert _haplotype_rows(without_chrom)[0] == []
    # With it, the row exists and the model accepts it.
    drafted, warnings = _haplotype_rows(variants)
    assert [(r.haplotype_name, r.chrom, r.start) for r in drafted] == [("*57", "10", 94947907)]
    assert warnings == []


def test_cpic_chrom_spelling_is_normalized_and_never_guessed() -> None:
    """`chr10` → `10`; a blank cell stays `None` rather than becoming an empty contig."""
    assert normalize_chrom("chr10") == "10"
    assert normalize_chrom("chrX") == "X"
    assert normalize_chrom("22") == "22"
    assert normalize_chrom("") is None and normalize_chrom(None) is None


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


def test_an_allele_the_format_cannot_hold_is_still_skipped() -> None:
    for value, reason in (("R", "ambiguity"), ("DELTCT", "notation")):
        rows, _ = _haplotype_rows(
            [_variant(rsid="rs1799853", variant_allele=value, unusable=reason)]
        )
        assert rows == [], value


def test_the_two_unusable_shapes_are_named_for_what_they_are() -> None:
    """`DELTCT` and `AAAGGGGCG(2)` are not ambiguity codes, and saying so was a false claim.

    Real CYP2D6 values, and the distinction decides what an author does next: an ambiguity is an
    uncertainty CPIC recorded and will never be expressible, while a deletion or repeat notation is a
    grammar gap a release could widen (RM5).
    """
    from just_dna_enricher.cpic import unusable_allele_reason

    assert unusable_allele_reason("A") is None
    assert unusable_allele_reason("AT") is None
    assert unusable_allele_reason("") is None
    assert unusable_allele_reason("R") == "ambiguity"      # A or G
    assert unusable_allele_reason("S") == "ambiguity"      # C or G
    assert unusable_allele_reason("DELTCT") == "notation"
    assert unusable_allele_reason("AAAGGGGCG(2)") == "notation"
    assert unusable_allele_reason("GGA(1)") == "notation"


def test_the_unusable_alleles_are_reported_once_per_reason_with_a_count() -> None:
    """A real CYP2D6 draft hits 67 of these; one line each buries every other finding in the run."""
    from just_dna_enricher.cpic import _unusable_warnings

    lines = _unusable_warnings(
        "CYP2D6",
        {"ambiguity": [f"*{i}=R" for i in range(5)], "notation": ["*180=DELTCT"]},
    )
    assert len(lines) == 2
    ambiguity = next(line for line in lines if "IUPAC" in line)
    assert "5 defining allele(s) skipped" in ambiguity and "(+2 more)" in ambiguity
    notation = next(line for line in lines if "RM5" in line)
    assert "1 defining allele(s) skipped" in notation and "DELTCT" in notation
    assert "IUPAC" not in notation      # the claim that was wrong


def test_variants_with_no_locus_are_reported_once_with_the_count() -> None:
    """Ten lines for CYP2D6 `*1` alone, before this — the third aggregation in this provider."""
    rows, warnings = _haplotype_rows(
        [_variant(rsid=None, chrom=None, start=42126625 + i) for i in range(4)]
    )
    assert rows == []
    assert len(warnings) == 1
    assert "4 defining variant(s) skipped" in warnings[0] and "(+1 more)" in warnings[0]


# ── CPIC prescribing recommendations (0.5.1) ────────────────────────────────────────────────────


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


# ── the allele filter (RM34) ────────────────────────────────────────────────────────────────────


def test_the_allele_filter_applies_to_all_three_tables(tmp_path: Path) -> None:
    """RM34: filtering one table and not the others leaves a module naming alleles it never defines.

    `*17` is dropped here, so its function row goes, its defining variant (`rs12248560`) goes, and every
    diplotype naming it goes — while `*1/*2` survives because `*1` is always kept.
    """
    spec = _spec(tmp_path)
    result = draft_gene(
        spec, "CYP2C19", alleles=["*2"], declared_use="non_commercial", client=_client()
    )
    assert result.added > 0

    assert {r.allele for r in _rows(spec, "allele_function.csv", AlleleFunctionRow)} == {"*1", "*2"}
    assert {r.rsid for r in _rows(spec, "haplotypes.csv", HaplotypeRow)} == {"rs4244285"}
    pairs = {(r.haplotype_a, r.haplotype_b) for r in _rows(spec, "diplotypes.csv", DiplotypeRow)}
    assert pairs == {("*1", "*1"), ("*1", "*2")}
    # The module must still be coherent: nothing names an allele `haplotypes.csv`/`allele_function.csv`
    # does not cover, which is the cross-check that would otherwise fire.
    assert validate_spec(spec).valid, validate_spec(spec).errors


def test_the_reference_allele_is_kept_even_when_not_asked_for(tmp_path: Path) -> None:
    """`*1` carries no defining variants, so keeping it costs nothing — and dropping it would make
    `*1/*2`, the commonest real diplotype, undraftable for an author who asked for `*2`."""
    spec = _spec(tmp_path)
    result = draft_gene(
        spec, "CYP2C19", alleles=["*2"], declared_use="non_commercial", client=_client()
    )
    assert "*1" in {r.allele for r in _rows(spec, "allele_function.csv", AlleleFunctionRow)}
    assert any("`*1` is always kept" in w for w in result.warnings)


def test_what_the_filter_dropped_is_stated_with_the_count(tmp_path: Path) -> None:
    """No silent caps: a filtered draft says how much of the source it left out."""
    spec = _spec(tmp_path)
    result = draft_gene(
        spec, "CYP2C19", alleles=["*2"], declared_use="non_commercial", client=_client()
    )
    line = next(w for w in result.warnings if "--allele" in w)
    assert "2 of 3 diplotype(s) drafted" in line
    assert "['*1', '*2']" in line


def test_an_unknown_allele_refuses_and_lists_what_cpic_publishes(tmp_path: Path) -> None:
    """A typo must not quietly produce a smaller module."""
    with pytest.raises(CpicError, match=r"publishes no allele"):
        draft_gene(
            _spec(tmp_path), "CYP2C19", alleles=["*2A"],
            declared_use="non_commercial", client=_client(),
        )
    try:
        draft_gene(_spec(tmp_path), "CYP2C19", alleles=["*2A"],
                   declared_use="non_commercial", client=_client())
    except CpicError as exc:
        assert "*17" in str(exc) and "*2" in str(exc)


def test_no_filter_drafts_everything_exactly_as_before(tmp_path: Path) -> None:
    """P3: the parameter is additive, so an unfiltered call is byte-identical to the old behaviour."""
    filtered = _spec(tmp_path / "with_arg")
    draft_gene(filtered, "CYP2C19", alleles=[], declared_use="non_commercial", client=_client())
    plain = _spec(tmp_path / "without")
    draft_gene(plain, "CYP2C19", declared_use="non_commercial", client=_client())
    for name in ("haplotypes.csv", "allele_function.csv", "diplotypes.csv"):
        assert (filtered / name).read_text() == (plain / name).read_text()


def test_an_unparsable_diplotype_is_reported_by_its_own_rule_not_hidden_by_the_filter() -> None:
    """CYP2D6's `*4x≥3/*95` is skipped and counted by the provider; the filter must not swallow it.

    Otherwise a run with `--allele` would report "outside the set" for rows whose real problem is
    notation the format cannot hold (RM5) — a different finding with a different fix.
    """
    from just_dna_enricher.pgx_draft import _pair_in

    assert _pair_in("*4x≥3/*95", frozenset({"*1"})) is True
    assert _pair_in("*1/*17", frozenset({"*1"})) is False


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
