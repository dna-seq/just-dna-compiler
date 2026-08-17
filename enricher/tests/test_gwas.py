"""The GWAS Catalog pass (0.6, RM90).

Every payload below is the **real shape** the REST API returned on 2026-08-17 for `rs1801133` and
`rs4149056`, trimmed to the keys the pass reads. That matters more than usual here: the three things
this pass has to get right — the `-?` risk allele, the free-text `betaUnit`, and the fact that
`pmid`/`ancestry`/`trait` live behind `_links` rather than in the association — are all properties of
the real payload that its documentation does not state.

The client is injected, so these run the real parsing, merging and writing code with no network and
no sleeping.
"""

import csv
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.gwas import (
    GwasCatalogClient,
    GwasError,
    GwasNotFound,
    _parse_risk_allele,
    enrich_gwas,
)
from just_dna_enricher.licensing import sources_path
from just_dna_enricher.net import PacingGate
from just_dna_format.gwas import GwasEffectRow

_YAML = """\
schema_version: "1.0"
module:
  name: gwas_pass
  title: GWAS pass
  description: fixture
  report_title: GWAS pass
genome_build: GRCh38
"""

_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "rs4149056,12,21178615,T,C,C/T,risk,SLCO1B1 reduced function,SLCO1B1\n"
)

_STUDIES = "rsid,pmid\nrs4149056,16199547\n"

#: Real associations for rs4149056. Association 13069 reports a beta in `umol/l` and names its risk
#: allele; 55421052 reports one in `unit` and the Catalog wrote `rs4149056-?` for the allele.
_ASSOCIATIONS = [
    {
        "associationId": "13069",
        "orPerCopyNum": None,
        "betaNum": 0.05,
        "betaUnit": "umol/l",
        "betaDirection": "increase",
        "range": "[0.03-0.07]",
        "standardError": None,
        "riskFrequency": "0.15",
        "pvalue": 7.0e-13,
        "loci": [{"strongestRiskAlleles": [{"riskAlleleName": "rs4149056-C"}]}],
        "_links": {
            "study": {"href": "https://example.test/studies/GCST000001"},
            "efoTraits": {"href": "https://example.test/traits/13069"},
        },
    },
    {
        "associationId": "55421052",
        "orPerCopyNum": None,
        "betaNum": 0.3017178,
        "betaUnit": "unit",
        "betaDirection": "increase",
        "range": "[0.21-0.39]",
        "standardError": 0.0467972,
        "riskFrequency": "NR",
        "pvalue": 1.0e-10,
        "loci": [{"strongestRiskAlleles": [{"riskAlleleName": "rs4149056-?"}]}],
        "_links": {
            "study": {"href": "https://example.test/studies/GCST000001"},
            "efoTraits": {"href": "https://example.test/traits/55421052"},
        },
    },
]

_STUDY_PAYLOAD = {
    "accessionId": "GCST000001",
    "publicationInfo": {"pubmedId": 16199547},
    "ancestries": [{"ancestralGroups": [{"ancestralGroup": "European"}]}],
}

_TRAIT_PAYLOADS = {
    "https://example.test/traits/13069": {
        "_embedded": {"efoTraits": [{"trait": "Bilirubin levels", "shortForm": "EFO_0004570"}]}
    },
    "https://example.test/traits/55421052": {
        "_embedded": {"efoTraits": [{"trait": "Statin-induced myopathy", "shortForm": "EFO_0009999"}]}
    },
}


class _FakeClient:
    """Serves the recorded payloads and counts every request, so the tests can assert the budget."""

    def __init__(self, associations=None, *, fail_on: str | None = None) -> None:
        self.associations = _ASSOCIATIONS if associations is None else associations
        self.fail_on = fail_on
        self.calls: list[str] = []

    def associations_for(self, rsid: str) -> list[dict]:
        self.calls.append(f"assoc:{rsid}")
        if self.fail_on == "associations":
            raise GwasError("simulated outage")
        return list(self.associations)

    def follow(self, url: str) -> dict:
        self.calls.append(url)
        if "studies" in url:
            return dict(_STUDY_PAYLOAD)
        return dict(_TRAIT_PAYLOADS.get(url, {}))

    def close(self) -> None:  # pragma: no cover - the pass only closes clients it made
        raise AssertionError("the pass must not close a client it did not create")


def _spec(tmp_path: Path, *, variants: str = _VARIANTS) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(variants)
    (spec / "studies.csv").write_text(_STUDIES)
    return spec


# ── the risk-allele parse, which is where a silent wrong answer would come from ──────────────────


def test_a_named_risk_allele_is_split_from_its_rsid() -> None:
    assert _parse_risk_allele("rs4149056-C") == ("rs4149056", "C")


def test_an_unknown_risk_allele_becomes_null_never_a_literal_question_mark() -> None:
    """The Catalog's `-?` means the study never established which allele carries the effect.

    Storing `'?'` would make it look like an allele and let a consumer try to match on it; storing
    the reference allele would be a fabrication. Null is the only honest answer, and the row is still
    written so the consumer can see the association exists and cannot be weighted.
    """
    assert _parse_risk_allele("rs4149056-?") == ("rs4149056", None)


def test_a_name_with_no_separator_yields_no_allele() -> None:
    assert _parse_risk_allele("rs4149056") == ("rs4149056", None)
    assert _parse_risk_allele(None) == (None, None)


# ── the pass ────────────────────────────────────────────────────────────────────────────────────


def test_the_pass_records_both_associations_with_their_own_units(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = enrich_gwas(spec, client=_FakeClient(), dataset="gwas_catalog_2026-08-01")
    assert len(result.rows) == 2
    by_id = {r.association_id: r for r in result.rows}
    assert by_id["13069"].effect_unit == "umol/l"
    assert by_id["13069"].effect_allele == "C"
    assert by_id["55421052"].effect_unit == "unit"
    assert by_id["55421052"].effect_allele is None
    assert {r.effect_measure for r in result.rows} == {"beta"}


def test_not_reported_becomes_absence_not_zero(tmp_path: Path) -> None:
    """`riskFrequency: "NR"` is the source declining to report, and a stored 0.0 would be a claim."""
    spec = _spec(tmp_path)
    result = enrich_gwas(spec, client=_FakeClient(), dataset="d")
    by_id = {r.association_id: r for r in result.rows}
    assert by_id["13069"].risk_allele_frequency == 0.15
    assert by_id["55421052"].risk_allele_frequency is None


def test_the_study_and_trait_links_are_followed_and_memoized(tmp_path: Path) -> None:
    """Both associations share one study, so the second follow must be a cache hit.

    This is the request budget the pass exists to keep honest: the naive shape is `1 + 2N` requests
    per variant, and the saving is reported rather than assumed.
    """
    client = _FakeClient()
    result = enrich_gwas(_spec(tmp_path), client=client, dataset="d")
    assert result.rows[0].pmid == "16199547"
    assert result.rows[0].study_accession == "GCST000001"
    assert result.rows[0].ancestry == "European"
    assert {r.trait_efo_id for r in result.rows} == {"EFO_0004570", "EFO_0009999"}
    # One associations call + one study + two traits = 4 distinct URLs; the shared study is fetched once.
    assert client.calls.count("https://example.test/studies/GCST000001") == 1
    assert result.requests_saved == 1
    assert result.requests_made == 4


def test_a_variant_with_no_association_gets_a_not_found_row(tmp_path: Path) -> None:
    """Unlike the gene-validity pass's silence, and the difference is real.

    A curating body's silence means nobody has assessed the gene. The Catalog's empty answer means no
    genome-wide association has been *published* for this variant — a fact about the variant, and one
    a consumer weighing an authored weight against the literature wants.
    """
    result = enrich_gwas(_spec(tmp_path), client=_FakeClient(associations=[]), dataset="d")
    assert len(result.rows) == 1
    assert result.rows[0].status == "not_found"
    assert result.missing == ["rs4149056"]
    assert result.covered == []


def test_the_pass_is_merge_not_clobber_and_keyed_per_association(tmp_path: Path) -> None:
    """Per record, not per variant.

    A coarse "skip any rsID already present" would pin the module to whatever the Catalog held on the
    first run — and the Catalog grows as papers publish, which is exactly the case that cannot
    tolerate it. Here a hand-edited row survives untouched while a newly published association is
    still added.
    """
    spec = _spec(tmp_path)
    enrich_gwas(spec, client=_FakeClient(associations=[_ASSOCIATIONS[0]]), dataset="d")
    hand_edited = (spec / "gwas_effects.csv").read_text().replace(
        "Bilirubin levels", "Bilirubin levels (checked by hand)"
    )
    (spec / "gwas_effects.csv").write_text(hand_edited)

    result = enrich_gwas(spec, client=_FakeClient(), dataset="d")
    by_id = {r.association_id: r for r in result.rows}
    assert len(result.rows) == 2
    assert by_id["13069"].trait == "Bilirubin levels (checked by hand)"   # not clobbered
    assert "55421052" in by_id                                            # the new one still arrived


def test_emission_is_deterministic(tmp_path: Path) -> None:
    """Principle 7 needs a stable order, and the source's payload order is not one."""
    first = enrich_gwas(_spec(tmp_path / "a"), client=_FakeClient(), dataset="d")
    reversed_client = _FakeClient(associations=list(reversed(_ASSOCIATIONS)))
    second = enrich_gwas(_spec(tmp_path / "b"), client=reversed_client, dataset="d")
    assert [r.association_id for r in first.rows] == [r.association_id for r in second.rows]


def test_the_written_csv_reloads_through_the_compilers_reader(tmp_path: Path) -> None:
    """The two producers must agree: what this pass writes, the compiler must read back unchanged.

    `_cell` exists to render the way the compiler's reverse writer renders, and a drift between them
    would only show up as a moved digest after a round trip.
    """
    from just_dna_compiler.compiler import load_csv_rows

    spec = _spec(tmp_path)
    result = enrich_gwas(spec, client=_FakeClient(), dataset="d")
    reloaded, errors, _ = load_csv_rows(spec / "gwas_effects.csv", GwasEffectRow, "gwas_effects.csv")
    assert not errors, errors
    assert [r.model_dump() for r in reloaded] == [r.model_dump() for r in result.rows]


def test_the_header_is_derived_from_the_model(tmp_path: Path) -> None:
    """A hand-kept field list is how `SOURCES_FIELDNAMES` lost a column."""
    spec = _spec(tmp_path)
    enrich_gwas(spec, client=_FakeClient(), dataset="d")
    with open(spec / "gwas_effects.csv", newline="") as handle:
        header = next(csv.reader(handle))
    assert header == list(GwasEffectRow.model_fields)


def test_the_pass_writes_its_licence_row(tmp_path: Path) -> None:
    """Every pass that consults a source writes its `SourceRow` — and the compile gate keys on that
    file and nothing else, so a pass that skipped it would leave the module ungated.

    The path is *resolved*, never joined: the licence table has two accepted spellings (RM51) and may
    sit under `derived/` (RM49). This test asserted `spec / "sources.csv"` first and failed, which is
    the same mistake `sidecar_path` exists to stop a pass from making.
    """
    spec = _spec(tmp_path)
    enrich_gwas(spec, client=_FakeClient(), dataset="d")
    written = sources_path(spec, error=GwasError).read_text()
    assert "gwas_catalog" in written
    assert "gwas_effect" in written


def test_unknown_commercial_terms_are_recorded_as_unknown_not_as_permission(tmp_path: Path) -> None:
    """EBI's terms do not settle commercial use, so the cell stays empty.

    A `false` would gate a module that nothing forbids; a `true` would assert a permission nobody
    granted. `taints_commercial_use` requires an explicit `False`, so an empty cell warns rather than
    refusing — which is the correct outcome for terms this source states in prose.
    """
    from just_dna_compiler.compiler import load_csv_rows
    from just_dna_format.sources import SourceRow, taints_commercial_use

    spec = _spec(tmp_path)
    enrich_gwas(spec, client=_FakeClient(), dataset="d")
    path = sources_path(spec, error=GwasError)
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    assert not errors, errors
    row = next(r for r in rows if r.source == "gwas_catalog")
    assert row.commercial_use is None
    assert row.redistribution is True
    assert not taints_commercial_use(row)


def test_offline_is_a_no_op_not_a_failure(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = enrich_gwas(spec, offline=True)
    assert result.skipped_offline
    assert not (spec / "gwas_effects.csv").exists()


def test_a_module_with_no_rsid_fetches_nothing(tmp_path: Path) -> None:
    """The Catalog is queried by rsID, so a coordinate-only module has no subjects at all."""
    spec = _spec(
        tmp_path,
        variants=(
            "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
            "12,21178615,T,C,C/T,risk,SLCO1B1 reduced function,SLCO1B1\n"
        ),
    )
    (spec / "studies.csv").write_text("chrom,start,ref,pmid\n12,21178615,T,16199547\n")
    client = _FakeClient()
    result = enrich_gwas(spec, client=client, dataset="d")
    assert client.calls == []
    assert result.rows == []


def test_an_invalid_existing_file_raises_rather_than_being_overwritten(tmp_path: Path) -> None:
    """Merging into a table that did not load would silently drop what was already recorded."""
    spec = _spec(tmp_path)
    (spec / "gwas_effects.csv").write_text("association_id,nonsense\n1,2\n")
    with pytest.raises(GwasError, match="is invalid"):
        enrich_gwas(spec, client=_FakeClient(), dataset="d")


def test_a_transport_failure_surfaces_as_this_passs_own_error(tmp_path: Path) -> None:
    """A client leaking its transport library's exception has no contract."""
    with pytest.raises(GwasError):
        enrich_gwas(_spec(tmp_path), client=_FakeClient(fail_on="associations"), dataset="d")


# ── the two bugs the live run found, which no recorded fixture had provoked ──────────────────────


def test_a_404_is_the_empty_answer_not_an_outage(tmp_path: Path) -> None:
    """The Catalog holds only variants with a published association, so it **404s** on a rare one.

    Found by running the pass against `reference_examples/hfe_hemochromatosis`, whose first variant
    is `rs111033563`. The pass treated the 404 as a transport failure and died on it — meaning it
    could never have completed on any clinically-authored module, which is most of them. A 404 on
    this path is the Catalog answering "no record", and the only thing that must not happen is the
    reverse: a real outage read as "no associations", which would write a confident negative.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        if "rs111033563" in str(request.url):
            return httpx.Response(404, json={"error": "Not Found"})
        return httpx.Response(200, json={"_embedded": {"associations": []}})

    client = GwasCatalogClient(gate=PacingGate(0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    assert client.associations_for("rs111033563") == []
    assert client.associations_for("rs1800562") == []
    # The typed distinction still exists one level down, which is what lets the two callers treat a
    # 404 differently: `associations_for` reports the empty answer, `follow` withholds the study
    # facts for one association and keeps the effect.
    with pytest.raises(GwasNotFound):
        client._get("https://www.ebi.ac.uk/x/rs111033563/y")
    assert client.follow("https://www.ebi.ac.uk/x/rs111033563/y") == {}


def test_a_p_value_below_float64_range_withholds_the_number_and_keeps_the_row(
    tmp_path: Path,
) -> None:
    """The Catalog publishes `pvalue: 0.0` for p-values past float64's range, and `p_value_num` is
    `gt=0` because such a value is an underflow rather than a probability.

    Found on real data: rs1800562 carries several. The pass let the resulting `ValidationError` drop
    the **whole association**, losing a real published effect over one derived column. The number is
    withheld; the verbatim string keeps what the source said; the row survives.
    """
    underflowing = [
        {
            **_ASSOCIATIONS[0],
            "associationId": "64091035",
            "pvalue": 0.0,
        }
    ]
    result = enrich_gwas(_spec(tmp_path), client=_FakeClient(associations=underflowing), dataset="d")
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.p_value_num is None
    assert row.p_value == "0.0"
    assert row.effect_size == 0.05          # the association itself is intact
    assert result.p_value_underflows == 1


def test_skipping_study_facts_costs_one_request_per_variant(tmp_path: Path) -> None:
    """`--no-study-facts`, which exists because the measurement contradicted the prediction.

    Caching was expected to collapse the `1 + 2N` budget; on a real module it saved nothing, because
    rs1800562's 189 associations each name their own study. The opt-out keeps the effects — which is
    what the table is for — and drops the metadata behind the links.
    """
    client = _FakeClient()
    result = enrich_gwas(_spec(tmp_path), client=client, dataset="d", study_facts=False)
    assert result.requests_made == 1
    assert [c for c in client.calls if c.startswith("http")] == []
    assert len(result.rows) == 2
    assert result.rows[0].effect_unit is not None      # the effect survived
    assert all(r.pmid is None for r in result.rows)    # the linked facts did not
