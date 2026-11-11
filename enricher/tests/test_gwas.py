"""The GWAS Catalog pass (0.6, RM90; on REST API v2 since RM354).

Every payload below is what the **v2** REST API returned on 2026-11-04 for `rs4149056`, copied whole
for each association rather than trimmed, plus the `/studies/<accession>/ancestries` answers for the
studies they name. The legacy API these tests were first recorded from answers HTTP 410 for every
path since the Catalog retired it, which is RM354. Two of the associations (13069 and 55421052) are
the ones the legacy recording carried: v2 kept the Catalog's association ids, which is what lets a
re-run merge into a table the legacy pass filled.

What these payloads carry that the documentation does not state, and the tests pin: the `-?` risk
allele, an effect spelled as one composite string (`"0.05 umol/l increase"`) with the unit in the
middle, a 200 with no `_embedded` key at all for a variant the Catalog holds nothing for, and a
p-value of `0.0` beside a mantissa/exponent pair that still says what it was.

The client is the real one on an `httpx.MockTransport`, so these run the real request, paging,
parsing, merging and writing code with no network and no sleeping.
"""

import copy
import csv
import os
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher.gwas import (
    _PAGE_SIZE,
    DEFAULT_GWAS_ENDPOINT,
    GwasCatalogClient,
    GwasError,
    GwasNotFound,
    GwasRetired,
    _parse_risk_allele,
    enrich_gwas,
)
from just_dna_enricher.licensing import sources_path
from just_dna_enricher.net import PacingGate
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.sources import SourceRow

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


def _links(association_id: int) -> dict:
    base = f"{DEFAULT_GWAS_ENDPOINT}/associations/{association_id}"
    return {
        "self": {"href": base},
        "loci": {"href": f"{base}/loci"},
        "snp": {"href": f"{DEFAULT_GWAS_ENDPOINT}/single-nucleotide-polymorphisms/rs4149056"},
    }


#: Real v2 associations for rs4149056, 2026-11-04. 13069 is a beta in `umol/l` with a named allele;
#: 55421052 a beta in `unit` whose allele the Catalog wrote as `rs4149056-?`; 55907397 and 55906837
#: share study GCST009733, which is what the ancestry cache pays on; 11824 is an odds ratio.
_ASSOCIATIONS: list[dict] = [
    {
        "association_id": 13069,
        "risk_frequency": "0.15",
        "pvalue_description": "in log(tbil)",
        "pvalue_mantissa": 7,
        "pvalue_exponent": -13,
        "multi_snp_haplotype": False,
        "snp_interaction": False,
        "range": "[0.03-0.07]",
        "beta": "0.05 umol/l increase",
        "p_value": 7e-13,
        "efo_traits": [{"efo_id": "EFO_0004570", "efo_trait": "bilirubin measurement"}],
        "reported_trait": ["Bilirubin levels"],
        "accession_id": "GCST000386",
        "locations": ["12:21178615"],
        "mapped_genes": ["SLCO1B1"],
        "bg_efo_traits": [],
        "pubmed_id": "19414484",
        "first_author": "Johnson AD",
        "ci_lower": 0.03,
        "ci_upper": 0.07,
        "snp_effect_allele": ["rs4149056-C"],
        "snp_allele": [{"rs_id": "rs4149056", "effect_allele": "C"}],
        "_links": _links(13069),
    },
    {
        "association_id": 55421052,
        "risk_frequency": "NR",
        "pvalue_description": "",
        "pvalue_mantissa": 1,
        "pvalue_exponent": -10,
        "multi_snp_haplotype": False,
        "snp_interaction": False,
        "range": "[0.21-0.39]",
        "beta": "0.3017178 unit increase",
        "p_value": 1e-10,
        "efo_traits": [
            {"efo_id": "EFO_0010370", "efo_trait": "lysophosphatidylethanolamine 20:4 measurement"}
        ],
        "reported_trait": ["Metabolite levels"],
        "accession_id": "GCST009391",
        "locations": ["12:21178615"],
        "mapped_genes": ["SLCO1B1"],
        "bg_efo_traits": [],
        "pubmed_id": "23823483",
        "first_author": "Rhee EP",
        "ci_lower": 0.21,
        "ci_upper": 0.39,
        "snp_effect_allele": ["rs4149056-?"],
        "snp_allele": [{"rs_id": "rs4149056", "effect_allele": "?"}],
        "_links": _links(55421052),
    },
    {
        "association_id": 55907397,
        "risk_frequency": "0.18",
        "pvalue_description": "",
        "pvalue_mantissa": 2,
        "pvalue_exponent": -11,
        "multi_snp_haplotype": False,
        "snp_interaction": False,
        "range": "[0.42-0.76]",
        "beta": "0.588 unit increase",
        "p_value": 2e-11,
        "efo_traits": [{"efo_id": "EFO_0005116", "efo_trait": "urinary metabolite measurement"}],
        "reported_trait": ["Urinary metabolite levels in chronic kidney disease"],
        "accession_id": "GCST009733",
        "locations": ["12:21178615"],
        "mapped_genes": ["SLCO1B1"],
        "bg_efo_traits": [{"efo_id": "MONDO_0005300", "efo_trait": "chronic kidney disease"}],
        "pubmed_id": "31959995",
        "first_author": "Schlosser P",
        "ci_lower": 0.42,
        "ci_upper": 0.76,
        "snp_effect_allele": ["rs4149056-C"],
        "snp_allele": [{"rs_id": "rs4149056", "effect_allele": "C"}],
        "_links": _links(55907397),
    },
    {
        "association_id": 55906837,
        "risk_frequency": "0.18",
        "pvalue_description": "",
        "pvalue_mantissa": 4,
        "pvalue_exponent": -32,
        "multi_snp_haplotype": False,
        "snp_interaction": False,
        "range": "[0.57-0.79]",
        "beta": "0.677 unit increase",
        "p_value": 4e-32,
        "efo_traits": [{"efo_id": "EFO_0005116", "efo_trait": "urinary metabolite measurement"}],
        "reported_trait": ["Urinary metabolite levels in chronic kidney disease"],
        "accession_id": "GCST009733",
        "locations": ["12:21178615"],
        "mapped_genes": ["SLCO1B1"],
        "bg_efo_traits": [{"efo_id": "MONDO_0005300", "efo_trait": "chronic kidney disease"}],
        "pubmed_id": "31959995",
        "first_author": "Schlosser P",
        "ci_lower": 0.57,
        "ci_upper": 0.79,
        "snp_effect_allele": ["rs4149056-C"],
        "snp_allele": [{"rs_id": "rs4149056", "effect_allele": "C"}],
        "_links": _links(55906837),
    },
    {
        "association_id": 11824,
        "risk_frequency": "0.13",
        "pvalue_description": "",
        "pvalue_mantissa": 2,
        "pvalue_exponent": -9,
        "multi_snp_haplotype": False,
        "snp_interaction": False,
        "range": "[2.60-7.70]",
        "or_per_copy_num": 4.5,
        "or_value": "4.5",
        "beta": "-",
        "p_value": 2e-09,
        "efo_traits": [{"efo_id": "GO_0036273", "efo_trait": "response to statin"}],
        "reported_trait": ["Response to statin therapy"],
        "accession_id": "GCST000213",
        "locations": ["12:21178615"],
        "mapped_genes": ["SLCO1B1"],
        "bg_efo_traits": [],
        "pubmed_id": "18650507",
        "first_author": "Link E",
        "ci_lower": 2.6,
        "ci_upper": 7.7,
        "snp_effect_allele": ["rs4149056-C"],
        "snp_allele": [{"rs_id": "rs4149056", "effect_allele": "C"}],
        "_links": _links(11824),
    },
]


def _ancestries(*groups: tuple[str, list[str]]) -> dict:
    """The `/studies/<accession>/ancestries` shape, one entry per (type, ancestral groups)."""
    return {
        "_embedded": {
            "ancestries": [
                {"type": kind, "ancestral_groups": [{"ancestral_group": g} for g in names]}
                for kind, names in groups
            ]
        }
    }


#: Real ancestries, 2026-11-04 — trimmed to the keys the pass reads (sample sizes and countries are
#: not columns). GCST009733 really does publish `NR` for both stages.
_ANCESTRIES: dict[str, dict] = {
    "GCST000386": _ancestries(("initial", ["Other"])),
    "GCST009391": _ancestries(("initial", ["European"])),
    "GCST009733": _ancestries(("initial", ["NR"]), ("replication", ["NR"])),
    "GCST000213": _ancestries(("initial", ["European"]), ("replication", ["European"])),
}

#: The real empty answer: a 200 with **no `_embedded` key at all**, only the page block saying zero.
_EMPTY_PAGE = {
    "_links": {"self": {"href": f"{DEFAULT_GWAS_ENDPOINT}/associations?rs_id=rs111033563"}},
    "page": {"size": 1000, "totalElements": 0, "totalPages": 0, "number": 0},
}

#: The real 410 body, served as `text/plain` on every legacy path since the Catalog retired it.
_RETIRED_TEXT = (
    "This legacy GWAS Catalog REST API is no longer available.\n"
    "For general programmatic access, see: https://www.ebi.ac.uk/gwas/docs/programmatic-access/\n"
    "For V2 migration, see: https://www.ebi.ac.uk/gwas/docs/news/rest-api-v2-migration-guide\n"
)


def _page(associations: list[dict], *, page_size: int | None = None) -> Callable[[httpx.Request], dict]:
    """Serve `associations` the way v2 pages them: `page`/`size` from the query, `next` while more."""

    def serve(request: httpx.Request) -> dict:
        size = page_size or int(request.url.params.get("size", "20"))
        number = int(request.url.params.get("page", "0"))
        if not associations:
            return copy.deepcopy(_EMPTY_PAGE)
        chunk = associations[number * size : (number + 1) * size]
        total_pages = -(-len(associations) // size)
        links = {"self": {"href": str(request.url)}}
        if number + 1 < total_pages:
            nxt = request.url.copy_merge_params({"page": str(number + 1), "size": str(size)})
            links["next"] = {"href": str(nxt)}
        return {
            "_embedded": {"associations": copy.deepcopy(chunk)},
            "_links": links,
            "page": {
                "size": size,
                "totalElements": len(associations),
                "totalPages": total_pages,
                "number": number,
            },
        }

    return serve


class _Recorded:
    """A real `GwasCatalogClient` over a transport that serves the recorded payloads.

    `calls` lists every request path+query, so a test asserts the request budget from what was
    actually asked rather than from the pass's own arithmetic.
    """

    def __init__(
        self,
        associations: list[dict] | None = None,
        *,
        status: int | None = None,
        page_size: int | None = None,
    ) -> None:
        self.calls: list[str] = []
        serve_page = _page(_ASSOCIATIONS if associations is None else associations, page_size=page_size)

        def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(f"{request.url.path}?{request.url.query.decode()}")
            if status is not None:
                return httpx.Response(status, json={"detail": "upstream is unwell"})
            path = request.url.path
            if path.endswith("/associations"):
                return httpx.Response(200, json=serve_page(request))
            if path.endswith("/ancestries"):
                accession = path.split("/")[-2]
                return httpx.Response(200, json=copy.deepcopy(_ANCESTRIES.get(accession, {})))
            return httpx.Response(404, json={"status": 404, "error": "Not Found", "path": path})

        self.client = GwasCatalogClient(gate=PacingGate(0.0))
        self.client._client = httpx.Client(transport=httpx.MockTransport(handler))

    def ancestry_calls(self) -> list[str]:
        return [c for c in self.calls if "/ancestries" in c]


def _client(*args, **kwargs) -> GwasCatalogClient:
    return _Recorded(*args, **kwargs).client


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


def _by_id(result) -> dict[str, GwasEffectRow]:
    return {r.association_id: r for r in result.rows}


def test_the_pass_records_every_association_with_its_own_unit(tmp_path: Path) -> None:
    """v2 spells the effect as one string — `"0.05 umol/l increase"` — and the three columns the
    legacy API served separately come out of it: the number, the unit verbatim, the direction."""
    spec = _spec(tmp_path)
    result = enrich_gwas(spec, client=_client(), dataset="gwas_catalog_2026-11-04")
    by_id = _by_id(result)
    assert set(by_id) == {str(a["association_id"]) for a in _ASSOCIATIONS}
    assert (by_id["13069"].effect_size, by_id["13069"].effect_unit) == (0.05, "umol/l")
    assert by_id["13069"].effect_direction == "increase"
    assert by_id["13069"].effect_allele == "C"
    assert by_id["55421052"].effect_unit == "unit"
    assert by_id["55421052"].effect_allele is None
    assert {r.effect_measure for r in result.rows if r.association_id != "11824"} == {"beta"}


def test_an_odds_ratio_is_dimensionless_and_carries_no_direction(tmp_path: Path) -> None:
    """v2 writes `beta: "-"` beside `or_per_copy_num` — the `-` is its spelling of no value."""
    row = _by_id(enrich_gwas(_spec(tmp_path), client=_client(), dataset="d"))["11824"]
    assert (row.effect_size, row.effect_measure) == (4.5, "OR")
    assert row.effect_unit is None
    assert row.effect_direction is None


def test_the_study_facts_v2_serves_inline_are_mapped(tmp_path: Path) -> None:
    """`pubmed_id`, `accession_id` and `efo_traits` sit on the association itself in v2."""
    row = _by_id(enrich_gwas(_spec(tmp_path), client=_client(), dataset="d"))["13069"]
    source = _ASSOCIATIONS[0]
    assert row.pmid == source["pubmed_id"]
    assert row.study_accession == source["accession_id"]
    assert row.trait_efo_id == source["efo_traits"][0]["efo_id"]
    assert row.trait == source["efo_traits"][0]["efo_trait"]
    assert row.confidence_interval == source["range"]
    # v2 publishes no standard error anywhere on an association: withheld, never derived from the CI.
    assert row.standard_error is None


def test_not_reported_becomes_absence_not_zero(tmp_path: Path) -> None:
    """`risk_frequency: "NR"` is the source declining to report, and a stored 0.0 would be a claim."""
    by_id = _by_id(enrich_gwas(_spec(tmp_path), client=_client(), dataset="d"))
    assert by_id["13069"].risk_allele_frequency == 0.15
    assert by_id["55421052"].risk_allele_frequency is None
    # A study whose every ancestral group is `NR` reported none, so the cell is empty, not "NR".
    assert by_id["55907397"].ancestry is None
    assert by_id["11824"].ancestry == "European"


def test_the_ancestry_follow_is_memoized_per_study(tmp_path: Path) -> None:
    """Ancestry is the one fact v2 still keeps behind a request, one per distinct study.

    55907397 and 55906837 share GCST009733, so the second follow must be a cache hit, and the request
    budget is reported from what was asked rather than assumed.
    """
    recorded = _Recorded()
    result = enrich_gwas(_spec(tmp_path), client=recorded.client, dataset="d")
    studies = {a["accession_id"] for a in _ASSOCIATIONS}
    assert len(recorded.ancestry_calls()) == len(studies)
    assert result.requests_saved == len(_ASSOCIATIONS) - len(studies)
    assert result.requests_made == len(recorded.calls)
    assert _by_id(result)["13069"].ancestry == "Other"


def test_a_variant_with_no_association_gets_a_not_found_row(tmp_path: Path) -> None:
    """Unlike the gene-validity pass's silence, and the difference is real.

    A curating body's silence means nobody has assessed the gene. The Catalog's empty answer means no
    genome-wide association has been *published* for this variant — a fact about the variant, and one
    a consumer weighing an authored weight against the literature wants.
    """
    result = enrich_gwas(_spec(tmp_path), client=_client(associations=[]), dataset="d")
    assert len(result.rows) == 1
    assert result.rows[0].status == "not_found"
    assert result.missing == ["rs4149056"]
    assert result.covered == []


def test_v2s_empty_answer_has_no_embedded_key_and_is_still_an_answer() -> None:
    """The shape guard that would have refused every rare variant on v2.

    The legacy API answered an empty variant with a 404, and a 200 without `_embedded.associations`
    meant the shape had changed. v2 answers the empty variant with a 200 that has **no `_embedded`
    key at all** and `page.totalElements: 0` — recorded live for `rs111033563`. Read with the legacy
    guard, every clinically-authored module would refuse on its first rare variant.
    """
    assert _client(associations=[]).association_pages("rs111033563") == [[]]


def test_a_200_with_no_associations_and_a_nonzero_total_is_a_shape_change() -> None:
    """The guard keeps its other half: a page claiming elements and carrying none is not empty."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"page": {"totalElements": 3, "number": 0, "size": 1000}})

    client = GwasCatalogClient(gate=PacingGate(0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GwasError, match="shape"):
        client.association_pages("rs4149056")


def test_every_page_is_read_and_counted(tmp_path: Path) -> None:
    """v2 pages its answer — 20 by default, and rs4149056 carries 386. The pass asks for large pages
    but follows `_links.next` until there is none, so a server that caps the size loses nothing."""
    recorded = _Recorded(page_size=2)
    result = enrich_gwas(_spec(tmp_path), client=recorded.client, dataset="d", study_facts=False)
    pages = [c for c in recorded.calls if "/associations" in c]
    assert len(pages) == -(-len(_ASSOCIATIONS) // 2)
    assert {r.association_id for r in result.rows} == {str(a["association_id"]) for a in _ASSOCIATIONS}
    assert result.requests_made == len(pages)


def test_the_pass_is_merge_not_clobber_and_keyed_per_association(tmp_path: Path) -> None:
    """Per record, not per variant.

    A coarse "skip any rsID already present" would pin the module to whatever the Catalog held on the
    first run — and the Catalog grows as papers publish, which is exactly the case that cannot
    tolerate it. Here a hand-edited row survives untouched while a newly published association is
    still added.
    """
    spec = _spec(tmp_path)
    enrich_gwas(spec, client=_client(associations=[_ASSOCIATIONS[0]]), dataset="d")
    hand_edited = (
        (spec / "gwas_effects.csv")
        .read_text()
        .replace("bilirubin measurement", "bilirubin measurement (checked by hand)")
    )
    (spec / "gwas_effects.csv").write_text(hand_edited)

    result = enrich_gwas(spec, client=_client(), dataset="d")
    by_id = _by_id(result)
    assert len(result.rows) == len(_ASSOCIATIONS)
    assert by_id["13069"].trait == "bilirubin measurement (checked by hand)"  # not clobbered
    assert "55421052" in by_id  # the new one still arrived


def test_a_table_the_legacy_pass_filled_merges_without_duplicating(tmp_path: Path) -> None:
    """v2 kept the Catalog's association ids, so a re-run over a legacy-filled table adds nothing twice.

    The row below is what the legacy pass wrote for 13069 (its ids came from `associationId`); v2
    serves the same association as the integer `13069`. Were the id spaces different, every module
    filled before RM354 would double its rows on the first re-run.
    """
    spec = _spec(tmp_path)
    legacy = GwasEffectRow(
        association_id="13069",
        variant_key="rs4149056",
        rsid="rs4149056",
        effect_size=0.05,
        effect_measure="beta",
        effect_unit="umol/l",
        dataset="gwas_catalog_2026-08-17",
        source="gwas_catalog",
        status="resolved",
    )
    enrich_gwas(spec, client=_client(associations=[]), dataset="d")  # licence row + not_found
    (spec / "gwas_effects.csv").unlink()
    with open(spec / "gwas_effects.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(GwasEffectRow.model_fields))
        writer.writeheader()
        writer.writerow({k: ("" if v is None else v) for k, v in legacy.model_dump().items()})
    result = enrich_gwas(spec, client=_client(), dataset="d")
    ids = [r.association_id for r in result.rows]
    assert ids.count("13069") == 1
    assert _by_id(result)["13069"].dataset == "gwas_catalog_2026-08-17"  # the recorded row stood


def test_emission_is_deterministic(tmp_path: Path) -> None:
    """Principle 7 needs a stable order, and the source's payload order is not one."""
    first = enrich_gwas(_spec(tmp_path / "a"), client=_client(), dataset="d")
    reversed_client = _client(associations=list(reversed(_ASSOCIATIONS)))
    second = enrich_gwas(_spec(tmp_path / "b"), client=reversed_client, dataset="d")
    assert [r.association_id for r in first.rows] == [r.association_id for r in second.rows]


def test_the_written_csv_reloads_through_the_compilers_reader(tmp_path: Path) -> None:
    """The two producers must agree: what this pass writes, the compiler must read back unchanged.

    `_cell` exists to render the way the compiler's reverse writer renders, and a drift between them
    would only show up as a moved digest after a round trip.
    """
    from just_dna_compiler.compiler import load_csv_rows

    spec = _spec(tmp_path)
    result = enrich_gwas(spec, client=_client(), dataset="d")
    reloaded, errors, _ = load_csv_rows(spec / "gwas_effects.csv", GwasEffectRow, "gwas_effects.csv")
    assert not errors, errors
    assert [r.model_dump() for r in reloaded] == [r.model_dump() for r in result.rows]


def test_the_header_is_derived_from_the_model(tmp_path: Path) -> None:
    """A hand-kept field list is how `SOURCES_FIELDNAMES` lost a column."""
    spec = _spec(tmp_path)
    enrich_gwas(spec, client=_client(), dataset="d")
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
    enrich_gwas(spec, client=_client(), dataset="d")
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
    enrich_gwas(spec, client=_client(), dataset="d")
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
    recorded = _Recorded()
    result = enrich_gwas(spec, client=recorded.client, dataset="d")
    assert recorded.calls == []
    assert result.rows == []


def test_an_invalid_existing_file_raises_rather_than_being_overwritten(tmp_path: Path) -> None:
    """Merging into a table that did not load would silently drop what was already recorded."""
    spec = _spec(tmp_path)
    (spec / "gwas_effects.csv").write_text("association_id,nonsense\n1,2\n")
    with pytest.raises(GwasError, match="is invalid"):
        enrich_gwas(spec, client=_client(), dataset="d")


def test_a_server_failure_surfaces_as_this_passs_own_error(tmp_path: Path) -> None:
    """A client leaking its transport library's exception has no contract."""
    with pytest.raises(GwasError):
        enrich_gwas(_spec(tmp_path), client=_client(status=503), dataset="d")


# ── a source that moved (RM354) ─────────────────────────────────────────────────────────────────


def test_a_410_is_a_retired_endpoint_not_an_outage(tmp_path: Path) -> None:
    """The legacy API answers 410 Gone on every path, and that is a fact about the source.

    Before RM354 it fell into the generic status arm as a plain `GwasError` — the could-not-ask the
    pass also raises for an outage — so a source that had MOVED read as one that was down, and a
    re-run tomorrow would have looked like the fix. The retired-endpoint error names the URL and
    quotes the source's own text, and it is asked once: a 410 is not retried.
    """
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(410, text=_RETIRED_TEXT, headers={"Content-Type": "text/plain"})

    client = GwasCatalogClient(gate=PacingGate(0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GwasRetired) as caught:
        enrich_gwas(_spec(tmp_path), client=client, dataset="d")
    assert isinstance(caught.value, GwasError)  # a caller catching the family still catches it
    assert len(calls) == 1, "a 410 must not be retried"
    assert calls[0] in str(caught.value)
    assert "rest-api-v2-migration-guide" in str(caught.value)
    assert not (tmp_path / "spec" / "gwas_effects.csv").exists()


def test_a_410_on_the_ancestry_follow_is_not_withheld_as_a_missing_study(tmp_path: Path) -> None:
    """`follow` withholds one row's ancestry on a 404. A 410 is the source moving, and swallowing it
    there would null the ancestry of every row and say nothing."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/ancestries"):
            return httpx.Response(410, text=_RETIRED_TEXT)
        return httpx.Response(200, json=_page(_ASSOCIATIONS)(request))

    client = GwasCatalogClient(gate=PacingGate(0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GwasRetired):
        enrich_gwas(_spec(tmp_path), client=client, dataset="d")


def test_a_404_on_the_search_path_is_could_not_ask_not_an_empty_answer() -> None:
    """The semantics of a 404 flipped with the API, measured on 2026-11-04.

    The legacy API was resource-shaped — `/singleNucleotidePolymorphisms/<rsid>/associations` — and
    404'd on a rare clinical variant, so a 404 there was the Catalog answering "no record". v2 is a
    search, `/associations?rs_id=`, and answers an unknown rsID with a 200 and zero elements; the
    only 404 it gave was for a path that does not exist. Reading that as "no associations" would
    write a confident `not_found` for every variant the day the path moves again.

    `follow` keeps its 404 arm: one study's ancestry withheld, the association kept.
    """
    client = _client(status=404)
    with pytest.raises(GwasError) as caught:
        client.association_pages("rs111033563")
    assert not isinstance(caught.value, GwasRetired)
    assert _client(status=404).follow(f"{DEFAULT_GWAS_ENDPOINT}/studies/GCST000000/ancestries") == {}
    with pytest.raises(GwasNotFound):
        _client(status=404)._get(f"{DEFAULT_GWAS_ENDPOINT}/studies/GCST000000/ancestries")


# ── what v2's composite strings hide ────────────────────────────────────────────────────────────


def _one(association: dict, tmp_path: Path, **kwargs) -> tuple[GwasEffectRow, object]:
    result = enrich_gwas(_spec(tmp_path), client=_client(associations=[association]), dataset="d", **kwargs)
    return result.rows[0], result


def test_a_multi_snp_associations_allele_is_the_queried_variants_never_the_first_listed(
    tmp_path: Path,
) -> None:
    """A multi-SNP association lists one `snp_effect_allele` per SNP, in the source's order. Taking the
    first would state another variant's allele against this module's row; no match withholds it."""
    two = {**_ASSOCIATIONS[0], "snp_effect_allele": ["rs1-A", "rs4149056-G"]}
    row, _ = _one(two, tmp_path / "a")
    assert (row.rsid, row.effect_allele) == ("rs4149056", "G")
    other = {**_ASSOCIATIONS[0], "snp_effect_allele": ["rs1-A"]}
    row, _ = _one(other, tmp_path / "b")
    assert (row.rsid, row.effect_allele) == ("rs4149056", None)


def test_v2s_dash_is_an_absent_pmid_and_keeps_the_row(tmp_path: Path) -> None:
    row, result = _one({**_ASSOCIATIONS[0], "pubmed_id": "-"}, tmp_path)
    assert row.pmid is None
    assert result.unusable == 0


def test_a_passing_5xx_is_retried_and_a_persistent_one_is_could_not_ask(tmp_path: Path) -> None:
    """A v2 pass makes one request per page and per study; one passing 503 must not sink them all."""
    served: list[int] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        if not served:
            served.append(503)
            return httpx.Response(503, text="busy")
        served.append(200)
        return httpx.Response(200, json=_page(_ASSOCIATIONS)(request))

    client = GwasCatalogClient(gate=PacingGate(0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(flaky))
    result = enrich_gwas(_spec(tmp_path / "a"), client=client, dataset="d", study_facts=False)
    assert served[:2] == [503, 200]
    assert len(result.rows) == len(_ASSOCIATIONS)
    with pytest.raises(GwasError) as caught:
        enrich_gwas(_spec(tmp_path / "b"), client=_client(status=503), dataset="d")
    assert not isinstance(caught.value, (GwasRetired, GwasNotFound))


def test_a_unit_with_a_thin_space_is_kept_verbatim(tmp_path: Path) -> None:
    """Recorded on rs4149056: one study wrote its unit with U+2009. Splitting on whitespace and
    re-joining would store a unit the source never wrote."""
    association = {**_ASSOCIATIONS[0], "beta": "0.11 mg dl-1 decrease"}
    row, _ = _one(association, tmp_path)
    assert (row.effect_size, row.effect_unit, row.effect_direction) == (0.11, "mg dl-1", "decrease")


def test_a_beta_with_no_unit_or_direction_keeps_the_number(tmp_path: Path) -> None:
    row, _ = _one({**_ASSOCIATIONS[0], "beta": "0.05 increase"}, tmp_path / "a")
    assert (row.effect_size, row.effect_unit, row.effect_direction) == (0.05, None, "increase")
    row, _ = _one({**_ASSOCIATIONS[0], "beta": "0.05"}, tmp_path / "b")
    assert (row.effect_size, row.effect_unit, row.effect_direction) == (0.05, None, None)


def test_an_effect_string_outside_the_grammar_is_withheld_and_counted(tmp_path: Path) -> None:
    """A string this pass cannot read is withheld whole — a number without the unit it is in is not a
    smaller answer, it is a different one — and counted, and `strict` refuses on the count."""
    association = {**_ASSOCIATIONS[0], "beta": "0.05 umol/l up"}
    row, result = _one(association, tmp_path / "a")
    assert (row.effect_size, row.effect_measure, row.effect_unit, row.effect_direction) == (
        None,
        None,
        None,
        None,
    )
    assert result.unparsed_effects == 1
    with pytest.raises(GwasError, match="could not read"):
        _one(association, tmp_path / "b", mode="strict")


def test_a_p_value_below_float64_range_withholds_the_number_and_keeps_the_row(
    tmp_path: Path,
) -> None:
    """The Catalog publishes `p_value: 0.0` for p-values past float64's range, and `p_value_num` is
    `gt=0` because such a value is an underflow rather than a probability.

    Found on real data under the legacy API: the pass let the resulting `ValidationError` drop the
    **whole association**. v2 adds what the legacy payload lacked — the mantissa/exponent pair beside
    the `0.0` — so the verbatim string now says what the study reported (`3e-493`, association
    119912762, recorded) where it used to say `0.0`. The queryable number is still withheld.
    """
    underflowing = {
        **_ASSOCIATIONS[0],
        "association_id": 119912762,
        "pvalue_mantissa": 3,
        "pvalue_exponent": -493,
        "p_value": 0.0,
    }
    row, result = _one(underflowing, tmp_path)
    assert row.p_value_num is None
    assert row.p_value == "3e-493"
    assert row.effect_size == 0.05  # the association itself is intact
    assert result.p_value_underflows == 1


def test_the_p_value_string_is_the_curated_pair_not_the_floats_repr(tmp_path: Path) -> None:
    """v2's float for 3e-29 is `2.9999999999999997e-29`. The pair is what the Catalog curated, and the
    queryable number is read from the same string so the two columns cannot disagree."""
    association = {
        **_ASSOCIATIONS[0],
        "pvalue_mantissa": 3,
        "pvalue_exponent": -29,
        "p_value": 2.9999999999999997e-29,
    }
    row, _ = _one(association, tmp_path)
    assert row.p_value == "3e-29"
    assert row.p_value_num == float(row.p_value)


def test_skipping_study_facts_costs_only_the_association_pages(tmp_path: Path) -> None:
    """`--no-study-facts`, which exists because the legacy measurement contradicted the prediction.

    On v2 the flag skips the one follow left — the study's ancestry. Everything v2 serves inline
    (pmid, accession, trait, EFO id) costs nothing and is filled either way.
    """
    recorded = _Recorded()
    result = enrich_gwas(_spec(tmp_path), client=recorded.client, dataset="d", study_facts=False)
    assert result.requests_made == 1
    assert recorded.ancestry_calls() == []
    assert len(result.rows) == len(_ASSOCIATIONS)
    assert all(r.ancestry is None for r in result.rows)  # the linked fact did not
    assert all(r.pmid for r in result.rows)  # the inline ones did


def _rows(spec: Path) -> list[dict]:
    """The written table as dicts — the file is what a later run reads, so the file is what is checked."""
    with open(spec / "gwas_effects.csv", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_a_no_study_facts_row_is_never_back_filled_by_a_later_run(tmp_path: Path) -> None:
    """S50: the cheap run is a permanent choice for the rows it writes, not a per-run trade.

    The merge is keyed on `association_id` and the skip happens before the row is built, so a row
    written without study facts keeps its linked column (ancestry, since v2) null forever. Deleting
    the file is the only recovery, and that is what the docs and the CLI help say. Run as the
    three-step sequence the reporter measured rather than asserted from the code, because the whole
    point is that step 2 looks like it should work.
    """
    spec = _spec(tmp_path)

    enrich_gwas(spec, client=_client(), dataset="d", study_facts=False)
    thin = _rows(spec)
    assert thin, "the cheap run must still write the effects"
    assert all(not row["ancestry"] for row in thin)

    enrich_gwas(spec, client=_client(), dataset="d", study_facts=True)
    assert [row["ancestry"] for row in _rows(spec)] == [row["ancestry"] for row in thin]

    (spec / "gwas_effects.csv").unlink()
    enrich_gwas(spec, client=_client(), dataset="d", study_facts=True)
    reported = {a["accession_id"] for a in _ASSOCIATIONS} - {"GCST009733"}  # that study wrote NR
    assert {row["study_accession"] for row in _rows(spec) if row["ancestry"]} == reported


# ── RM428: a Catalog that refuses the page size it is asked for ──────────────────────────────────

_BAD_REQUEST = {"status": 400, "error": "Bad Request"}


def _refusing(
    *, ceiling: int | None, refuse_later_pages: bool = False, page_size: int | None = None
) -> tuple[GwasCatalogClient, list[str]]:
    """A Catalog that answers a `size` above `ceiling` (any `size` at all when `None`) with a bare 400.

    The body is the one recorded live on 2026-11-10 for `size=501`: it does not name the limit.
    """
    calls: list[str] = []
    serve = _page(_ASSOCIATIONS, page_size=page_size)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.url.path}?{request.url.query.decode()}")
        size = request.url.params.get("size")
        if refuse_later_pages and request.url.params.get("page", "0") != "0":
            return httpx.Response(400, json=_BAD_REQUEST)
        if size is not None and (ceiling is None or int(size) > ceiling):
            return httpx.Response(400, json=_BAD_REQUEST)
        return httpx.Response(200, json=serve(request))

    client = GwasCatalogClient(gate=PacingGate(0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client, calls


def test_rm428_the_page_size_asked_for_is_within_the_ceiling_measured_live(tmp_path: Path) -> None:
    """A Catalog that refuses anything above 500 still answers the first request whole."""
    client, calls = _refusing(ceiling=500)
    result = enrich_gwas(_spec(tmp_path), client=client, dataset="d", study_facts=False)
    assert {r.association_id for r in result.rows} == {str(a["association_id"]) for a in _ASSOCIATIONS}
    assert len(calls) == 1, calls


def test_rm428_a_refused_first_page_is_asked_once_more_without_a_size(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The next drop of the ceiling: the first request's 400 is asked again with no `size`, so the
    Catalog's own default page decides; the refusal is counted as a request and warned once per run."""
    variants = _VARIANTS + "rs2,1,100,A,G,A/G,risk,second,GENE2\n"
    client, calls = _refusing(ceiling=None)
    with caplog.at_level("WARNING", logger="just_dna_enricher.gwas"):
        result = enrich_gwas(
            _spec(tmp_path, variants=variants), client=client, dataset="d", study_facts=False
        )
    assert {r.association_id for r in result.rows} == {str(a["association_id"]) for a in _ASSOCIATIONS}
    sized = [c for c in calls if "size=" in c]
    assert len(sized) == 2, "one refused request per rsID, and no more"
    assert all("page=" not in c for c in sized), "only a first request is ever re-asked"
    assert result.requests_made == len(calls), "the refused requests are spent too, and counted"
    refusals = [r for r in caplog.records if "refused" in r.getMessage()]
    assert len(refusals) == 1, "one warning per run, not one per rsID"
    assert str(_PAGE_SIZE) in refusals[0].getMessage()


def test_rm428_a_second_400_stays_could_not_ask(tmp_path: Path) -> None:
    """A Catalog refusing the unsized request too is not asked a third time, and nothing is written."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(400, json=_BAD_REQUEST)

    client = GwasCatalogClient(gate=PacingGate(0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GwasError) as caught:
        enrich_gwas(_spec(tmp_path), client=client, dataset="d", study_facts=False)
    assert not isinstance(caught.value, (GwasNotFound, GwasRetired))
    assert len(calls) == 2
    assert not (tmp_path / "spec" / "gwas_effects.csv").exists()


def test_rm428_a_400_on_a_later_page_is_never_re_asked(tmp_path: Path) -> None:
    """By the second page the size was accepted, so a 400 there is something else: could not ask."""
    client, calls = _refusing(ceiling=_PAGE_SIZE, refuse_later_pages=True, page_size=2)
    client_pages = client.association_pages
    with pytest.raises(GwasError):
        client_pages("rs4149056")
    assert [("page=" in c) for c in calls] == [False, True], calls


@pytest.mark.network
def test_live_rm428_the_catalog_accepts_the_page_size_this_pass_asks_for() -> None:
    """The guard that can see the ceiling move: the server decides it, and moved it once in a week.

    Only the live service answers the 400, so no recording can pin the number; this asks with
    `_PAGE_SIZE` and expects a 200.
    """
    url = httpx.URL(
        f"{DEFAULT_GWAS_ENDPOINT}/associations", params={"rs_id": "rs1421085", "size": _PAGE_SIZE}
    )
    response = httpx.get(url, headers={"Accept": "application/json"}, timeout=30.0)
    assert response.status_code == 200, (
        f"size={_PAGE_SIZE} answered {response.status_code}: {response.text[:200]}"
    )


# ── live (RM354's hand-run, kept as a test) ──────────────────────────────────────────────────────

NETWORK = os.environ.get("JUST_DNA_NETWORK_TESTS") == "1"


@pytest.mark.skipif(not NETWORK, reason="set JUST_DNA_NETWORK_TESTS=1 to run the live GWAS Catalog leg")
def test_live_the_legacy_api_is_retired_and_v2_answers() -> None:
    """Both halves of RM354 against the real Catalog: the legacy path raises the retired-endpoint
    error, and v2 serves association 13069 with the facts these recordings carry."""
    client = GwasCatalogClient()
    try:
        with pytest.raises(GwasRetired, match="410"):
            client._get(
                "https://www.ebi.ac.uk/gwas/rest/api/singleNucleotidePolymorphisms/rs4149056/associations"
            )
        associations = [a for page in client.association_pages("rs4149056") for a in page]
        assert len(associations) > 20, "more than one default page: the paging must have run"
        live = next(a for a in associations if str(a.get("association_id")) == "13069")
        recorded = _ASSOCIATIONS[0]
        for key in ("beta", "accession_id", "pubmed_id", "efo_traits", "snp_effect_allele"):
            assert live[key] == recorded[key], key
        assert client.association_pages("rs111033563") == [[]]
    finally:
        client.close()


# ── RM373: a row is labelled by the Catalog's own release, never by the day it was asked ────────


#: `https://www.ebi.ac.uk/gwas/api/search/stats`, read by hand on 2026-11-05 (trimmed).
_STATS = {"date": "2026-10-29", "ensemblbuild": "116", "dbsnpbuild": "156", "genebuild": "GRCh38.p14"}


def _with_stats(stats: dict | None) -> GwasCatalogClient:
    client = _client()
    recorded = client._client._transport

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search/stats"):
            return httpx.Response(200, json=stats) if stats is not None else httpx.Response(503)
        return recorded.handle_request(request)

    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def _licence_dataset(spec: Path) -> str | None:
    path = sources_path(spec, error=RuntimeError)
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    assert errors == []
    (row,) = [r for r in rows if r.source == "gwas_catalog"]
    return row.dataset


def test_rm373_rows_carry_the_catalogs_stated_release(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = enrich_gwas(spec, client=_with_stats(_STATS))
    assert {r.dataset for r in result.rows} == {"gwas_catalog_2026-10-29"}
    assert _licence_dataset(spec) == "gwas_catalog_2026-10-29"


def test_rm373_a_catalog_that_states_no_release_is_withheld_never_dated_by_the_run(tmp_path: Path) -> None:
    """`release_dataset`'s rule (RM361): the bare lane says no release was stated; the licence row names none."""
    spec = _spec(tmp_path)
    result = enrich_gwas(spec, client=_with_stats(None))
    assert {r.dataset for r in result.rows} == {"gwas_catalog"}
    assert _licence_dataset(spec) is None
