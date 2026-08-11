"""Identifier currency — dbSNP merge/withdrawal states, EFO obsolescence, HGNC symbol retirement.

Every payload is recorded from the live service. The dbSNP recording is the important one, because it
pins the finding that shaped the whole design: `rs11273140` (withdrawn after a clustering error) and
`rs2000000000` (never assigned) come back **byte-identical**. No live endpoint separates them, so the
check must name both readings and assert neither — and a test has to hold that line, or a later
"improvement" will quietly start guessing "typo".
"""

import json
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.eutils import EutilsClient, EutilsSettings
from just_dna_enricher.identifiers import (
    _ONTOLOGY_IRI,
    OntologyClient,
    RsidStatus,
    check_identifiers,
    check_rsids,
    classify_rsid,
    module_trait_ids,
)
from just_dna_enricher.net import PacingGate
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import VALID_RSID_STATUS

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_DBSNP = json.loads((_ASSETS / "dbsnp_esummary_payload.json").read_text())
_OLS4 = json.loads((_ASSETS / "ols4_terms_payload.json").read_text())
_HGNC = json.loads((_ASSETS / "hgnc_fetch_payload.json").read_text())

_LIVE = "rs334"           # sickle-cell; current
_MERGED = "rs3216883"     # merged into rs3051860
_WITHDRAWN = "rs11273140"  # retracted after a clustering error
_NEVER = "rs2000000000"   # never assigned


def _eutils() -> EutilsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_DBSNP)

    client = EutilsClient(settings=EutilsSettings(email=None))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _ontology() -> OntologyClient:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "ols4" in url:
            iri = request.url.params.get("iri", "")
            curie = iri.rstrip("/").rsplit("/", 1)[-1]
            return httpx.Response(200, json=_OLS4.get(curie, {}))
        # HGNC: /fetch/<field>/<value>
        key = url.split("/fetch/", 1)[1]
        return httpx.Response(200, json=_HGNC.get(key, {"response": {"numFound": 0, "docs": []}}))

    client = OntologyClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _variant(**kw) -> VariantRow:
    base = {"genotype": "A/T", "state": "risk", "conclusion": "c"}
    return VariantRow(**{**base, **kw})


# ── dbSNP: the three states ─────────────────────────────────────────────────────────────────────


def test_the_three_states_are_classified_from_the_recorded_payload() -> None:
    records = _DBSNP["result"]
    live = classify_rsid(_LIVE, records["334"])
    merged = classify_rsid(_MERGED, records["3216883"])

    assert (live.state, live.current) == ("live", None)
    assert live.is_current
    assert (merged.state, merged.current) == ("merged", "rs3051860")
    assert not merged.is_current
    # `withdrawn` is in the vocabulary but is NOT reachable from the live API — see the test below.
    assert set(VALID_RSID_STATUS) == {"live", "merged", "absent", "withdrawn"}
    assert not live.is_fatal and not merged.is_fatal


def test_withdrawn_and_never_assigned_are_indistinguishable_and_stay_that_way() -> None:
    """The load-bearing finding. If these two ever classify differently, something started guessing.

    Equality is asserted on the *recorded responses themselves* before the classification, so the test
    documents the API's behaviour rather than merely our reading of it.
    """
    records = _DBSNP["result"]
    withdrawn_record = {k: v for k, v in records["11273140"].items() if k != "uid"}
    never_record = {k: v for k, v in records["2000000000"].items() if k != "uid"}
    assert withdrawn_record == never_record, "dbSNP distinguishes them — the design can be revisited"

    withdrawn = classify_rsid(_WITHDRAWN, records["11273140"])
    never = classify_rsid(_NEVER, records["2000000000"])
    assert withdrawn.state == never.state == "absent"
    assert withdrawn.current is None and never.current is None


def test_the_absent_message_names_both_readings_and_asserts_neither() -> None:
    message = str(classify_rsid(_WITHDRAWN, _DBSNP["result"]["11273140"]))
    assert "never assigned" in message and "withdrawn" in message
    assert "indistinguishable" in message
    # It must not conclude. A message that said "typo" would send an author to fix the wrong thing.
    assert "is a typo" not in message


def test_withdrawn_is_a_real_state_that_the_live_api_cannot_produce() -> None:
    """Kept in the vocabulary deliberately, even though nothing automated emits it.

    Two reasons it earns a slot rather than being dropped: a curator who has established a retraction
    can record it in `resolution.csv` and have the tooling honour it, and a future source that *can*
    tell a retraction from a never-assigned id starts producing it without a vocabulary change — which
    Principle 3 would otherwise make a one-way door.

    It is not interchangeable with `absent`: absent has benign causes and refuses only under strict,
    while withdrawn refuses in both modes.
    """
    withdrawn = RsidStatus(rsid=_WITHDRAWN, state="withdrawn")
    absent = classify_rsid(_WITHDRAWN, _DBSNP["result"]["11273140"])

    assert withdrawn.is_fatal and not absent.is_fatal
    assert "WITHDRAWN" in str(withdrawn)
    assert "both modes" in str(withdrawn)

    # The automated path still cannot reach it — that is the finding, not an oversight.
    states = {classify_rsid(r, rec).state for r, rec in
              zip(("rs334", "rs3216883", _WITHDRAWN, _NEVER),
                  (_DBSNP["result"][k] for k in ("334", "3216883", "11273140", "2000000000")),
                  strict=True)}
    assert "withdrawn" not in states


def test_a_withdrawn_rsid_refuses_in_both_modes(tmp_path: Path) -> None:
    """The severity difference from `absent`, driven through a real compile.

    A curator records the retraction in `resolution.csv`; `best_effort` must refuse anyway, because a
    retracted variant may leave the annotation describing nothing.
    """
    from just_dna_compiler.compiler import compile_module

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: d\n  title: D\n  description: d\n  report_title: D\n"
    )
    (spec / "variants.csv").write_text(
        f"rsid,chrom,start,ref,alts,genotype,state,conclusion\n{_WITHDRAWN},1,100,A,T,A/T,risk,c\n"
    )
    (spec / "studies.csv").write_text(f"rsid,pmid\n{_WITHDRAWN},29165669\n")
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,"
        "rsid_alternates,rsid_current,rsid_status,fetched_at\n"
        f"{_WITHDRAWN},{_WITHDRAWN},1,100,A,T,GRCh38,0,manual,resolved,,,withdrawn,\n"
    )
    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"out{int(strict)}", strict=strict)
        assert not result.success, f"withdrawn must refuse with strict={strict}"
        assert any("WITHDRAWN" in e for e in result.errors)


def test_the_merged_message_refuses_to_rewrite_the_identity() -> None:
    """The stale-identifier collision, stated where an author will actually read it."""
    message = str(classify_rsid(_MERGED, _DBSNP["result"]["3216883"]))
    assert "rs3051860" in message
    assert "never rewritten" in message
    assert "variant_key" in message


def test_check_rsids_batches_and_strips_the_rs_prefix() -> None:
    """esummary keys on the numeric uid, so `rs334` must go out as `334` or nothing matches."""
    client = _eutils()
    statuses = check_rsids([_LIVE, _MERGED, _WITHDRAWN, _NEVER, _LIVE], client=client)

    assert [s.rsid for s in statuses] == [_LIVE, _MERGED, _WITHDRAWN, _NEVER]  # deduped, ordered
    assert [s.state for s in statuses] == ["live", "merged", "absent", "absent"]


def test_a_live_rsid_is_not_reported_as_merged() -> None:
    """`snp_id` is an int and the uid a string; comparing them raw makes every rsID look merged."""
    assert _DBSNP["result"]["334"]["snp_id"] == 334        # int, in the recorded payload
    assert classify_rsid(_LIVE, _DBSNP["result"]["334"]).state == "live"


# ── the verdict lands on the resolution row, and never replaces the label ───────────────────────


def test_enrich_stamps_the_status_without_substituting_the_rsid(tmp_path: Path, monkeypatch) -> None:
    from just_dna_enricher import enrich as enrich_module

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: d\n  title: D\n  description: d\n  report_title: D\n"
    )
    (spec / "variants.csv").write_text(
        f"rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
        f"{_MERGED},1,100,A,T,A/T,risk,c\n"
    )
    (spec / "studies.csv").write_text(f"rsid,pmid\n{_MERGED},29165669\n")

    monkeypatch.setattr(
        enrich_module, "check_rsids", lambda rsids, **kw: check_rsids(rsids, client=_eutils())
    )
    result = enrich_module.enrich(
        spec, offline=False, download=False, use_clinvar=False, use_gnomad=False,
        mint_vrs=False, verify_ref=False, verify_clinsig=False,
    )

    row = result.rows[0]
    assert row.rsid == _MERGED, "the authored label must survive untouched"
    assert row.rsid_status == "merged"
    assert row.rsid_current == "rs3051860"
    assert [s.rsid for s in result.stale_rsids] == [_MERGED]
    # ...and it round-trips through the written CSV.
    written = (spec / "resolution.csv").read_text()
    assert "rsid_current" in written.splitlines()[0]
    assert "rs3051860" in written


def test_the_new_columns_stay_out_of_the_fact_set() -> None:
    """Time-varying external state: a dbSNP merge must not move `resolution_signature`."""
    from just_dna_format.integrity import resolution_signature
    from just_dna_format.resolution import RESOLUTION_FACT_FIELDS

    assert "rsid_current" not in RESOLUTION_FACT_FIELDS
    assert "rsid_status" not in RESOLUTION_FACT_FIELDS

    base = {"variant_key": "rs3216883", "rsid": "rs3216883", "chrom": "1", "start": 100, "ref": "A", "alts": "T"}
    before = [ResolutionRow(**base)]
    after = [ResolutionRow(**base, rsid_status="merged", rsid_current="rs3051860")]
    assert resolution_signature(before) == resolution_signature(after)


def test_offline_skips_the_rsid_check(tmp_path: Path) -> None:
    """NCBI is the only oracle for merges, so there is nothing to consult offline."""
    from just_dna_enricher.enrich import enrich

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: d\n  title: D\n  description: d\n  report_title: D\n"
    )
    (spec / "variants.csv").write_text(
        f"rsid,chrom,start,ref,alts,genotype,state,conclusion\n{_MERGED},1,100,A,T,A/T,risk,c\n"
    )
    (spec / "studies.csv").write_text(f"rsid,pmid\n{_MERGED},29165669\n")

    result = enrich(spec, offline=True, verify_clinsig=False)
    assert result.stale_rsids == []
    assert result.rows[0].rsid_status is None


# ── EFO / OLS4 ──────────────────────────────────────────────────────────────────────────────────


def test_the_obsolete_trait_that_paid_for_this_check_before_it_was_built() -> None:
    """`EFO_0001645` was the canonical CAD example across spec.py, vocab.py, the docs and a fixture —
    and it is obsolete, replaced by a MONDO term. Probing for this check is what found it."""
    status = _ontology().trait("EFO_0001645")
    assert status.state == "obsolete"
    assert status.replaced_by == "MONDO_0005010"
    assert "obsolete" in str(status) and "MONDO_0005010" in str(status)


def test_a_current_trait_is_silent() -> None:
    status = _ontology().trait("EFO_0004340")
    assert status.state == "current"
    assert status.label == "body mass index"


def test_a_colon_curie_resolves_like_an_underscore_one() -> None:
    """`MONDO:0005010` and `MONDO_0005010` are the same term written two ways."""
    client = _ontology()
    assert client.trait("MONDO:0005010").state == client.trait("MONDO_0005010").state == "current"


def test_an_unknown_prefix_abstains_rather_than_reporting_absent() -> None:
    """Claiming a term does not exist because we do not know where to look would be a lie."""
    status = _ontology().trait("SNOMED:12345")
    assert status.state == "unchecked"
    assert "does not know how to resolve" in str(status)


def test_orphanet_terms_resolve_under_both_spellings() -> None:
    """Orphanet is written `ORPHA:558` and `Orphanet:558` in the wild; both name one term."""
    client = _ontology()
    for curie in ("ORPHA:558", "Orphanet:558", "ORPHA_558"):
        status = client.trait(curie)
        assert status.state == "current", curie
        assert status.label == "Marfan syndrome"


def test_the_orphanet_iri_is_not_composed_from_the_curie_prefix() -> None:
    """The trap ORDO exposed: `ORPHA:558` lives at `…/ORDO/Orphanet_558`, so building the IRI as
    `stem + PREFIX + "_" + local` queries `ORPHA_558` — which OLS4 answers 200-with-zero-terms, i.e.
    indistinguishable from "this id does not exist". The bug would have surfaced as a false finding
    about the module rather than as an error here, so the requested IRI itself is asserted."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.params.get("iri", ""))
        return httpx.Response(200, json=_OLS4.get("Orphanet_558", {}))

    client = OntologyClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    client.trait("ORPHA:558")
    assert requested == ["http://www.orpha.net/ORDO/Orphanet_558"]
    assert "ORPHA_558" not in requested[0]


def test_every_registered_ontology_composes_a_reachable_iri() -> None:
    """Each route's IRI prefix must end in the term separator, or the composed IRI silently loses it
    and every lookup in that ontology reports `absent`."""
    for prefix, (ontology, iri_prefix) in _ONTOLOGY_IRI.items():
        assert iri_prefix.endswith("_"), prefix
        assert iri_prefix.startswith("http"), prefix
        assert ontology.islower(), prefix


def test_multi_valued_trait_cells_fan_out() -> None:
    variants = [
        _variant(rsid="rs1", trait_efo_id="EFO_0004340;MONDO_0005010"),
        _variant(rsid="rs2", trait_efo_id="EFO_0004340"),          # duplicate collapses
    ]
    assert module_trait_ids(variants) == ["EFO_0004340", "MONDO_0005010"]


# ── HGNC ────────────────────────────────────────────────────────────────────────────────────────


def test_a_retired_symbol_reports_its_approved_replacement() -> None:
    status = _ontology().gene("MLL")
    assert status.state == "retired"
    assert status.current == "KMT2A"
    assert status.hgnc_id == "HGNC:7132"
    assert "previous symbol" in str(status)


def test_an_approved_symbol_is_silent() -> None:
    status = _ontology().gene("BRCA1")
    assert status.state == "approved"
    assert status.current == "BRCA1"


def test_an_unknown_symbol_is_neither_approved_nor_retired() -> None:
    status = _ontology().gene("NOTAGENE")
    assert status.state == "unknown"
    assert "neither an approved nor a previous" in str(status)


def test_the_exact_endpoints_are_used_not_the_fuzzy_search() -> None:
    """`search/BRCA1` returns 19 hits including ABRAXAS1, which would make every symbol ambiguous."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        key = url.split("/fetch/", 1)[1]
        return httpx.Response(200, json=_HGNC.get(key, {"response": {"numFound": 0, "docs": []}}))

    client = OntologyClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    client.gene("BRCA1")

    assert requested and all("/fetch/" in url for url in requested)
    assert not any("/search/" in url for url in requested)


def test_prev_symbol_is_only_consulted_when_the_symbol_lookup_misses() -> None:
    """An approved symbol costs one request, not two."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        key = str(request.url).split("/fetch/", 1)[1]
        requested.append(key)
        return httpx.Response(200, json=_HGNC.get(key, {"response": {"numFound": 0, "docs": []}}))

    client = OntologyClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)

    client.gene("BRCA1")
    assert requested == ["symbol/BRCA1"]
    requested.clear()
    client.gene("MLL")
    assert requested == ["symbol/MLL", "prev_symbol/MLL"]


# ── the module-level pass ───────────────────────────────────────────────────────────────────────


def test_check_identifiers_reports_both_axes(tmp_path: Path) -> None:
    variants = [
        _variant(rsid="rs1", gene="MLL", trait_efo_id="EFO_0001645"),
        _variant(rsid="rs2", gene="BRCA1", trait_efo_id="EFO_0004340"),
    ]
    report = check_identifiers(variants, client=_ontology())

    assert not report.clean
    assert [t.curie for t in report.stale_traits] == ["EFO_0001645"]
    assert [g.symbol for g in report.stale_genes] == ["MLL"]


def test_a_clean_module_reports_clean() -> None:
    variants = [_variant(rsid="rs1", gene="BRCA1", trait_efo_id="EFO_0004340")]
    assert check_identifiers(variants, client=_ontology()).clean


# ── live probes (opt-in) ────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not __import__("os").environ.get("JUST_DNA_NETWORK_TESTS"),
    reason="set JUST_DNA_NETWORK_TESTS=1 to run live identifier probes",
)
def test_live_registries_still_behave_as_recorded() -> None:
    """Guards the recordings — including the indistinguishability finding, which is the one most
    likely to be silently invalidated by a dbSNP release."""
    statuses = {s.rsid: s for s in check_rsids([_LIVE, _MERGED, _WITHDRAWN, _NEVER])}
    assert statuses[_LIVE].state == "live"
    assert (statuses[_MERGED].state, statuses[_MERGED].current) == ("merged", "rs3051860")
    assert statuses[_WITHDRAWN].state == statuses[_NEVER].state == "absent"

    with OntologyClient() as client:
        assert client.trait("EFO_0001645").state == "obsolete"
        assert client.trait("EFO_0004340").state == "current"
        assert client.gene("MLL").current == "KMT2A"
        assert client.gene("BRCA1").state == "approved"


# ── S24: the gene named and the chromosome resolved ─────────────────────────────────────────────
#
# Four of one reporter's seven rows paired a real gene symbol with an rsID on another chromosome —
# the signature of a machine-written summary, where real names are quoted beside invented rs numbers
# that resolve anyway because dbSNP is dense. Every existing check passes on each half alone.
_GENE_BANDS = {
    "CADM2": "3p12.1", "NEGR1": "1p31.1", "EXOC3L2": "19q13.32",
    "FOXO3": "6q21", "FTO": "16q12.2", "XG": "Xp22.33",
}


def _hgnc_with_locations() -> OntologyClient:
    def handler(request: httpx.Request) -> httpx.Response:
        symbol = str(request.url).rsplit("/", 1)[-1]
        band = _GENE_BANDS.get(symbol)
        if band is None or "prev_symbol" in str(request.url):
            return httpx.Response(200, json={"response": {"numFound": 0, "docs": []}})
        return httpx.Response(200, json={"response": {"numFound": 1, "docs": [
            {"symbol": symbol, "status": "Approved", "hgnc_id": f"HGNC:{len(symbol)}",
             "location": band}
        ]}})

    client = OntologyClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _row(rsid: str, gene: str, chrom: str | None = None, start: int | None = None) -> VariantRow:
    return VariantRow(
        rsid=rsid, gene=gene, chrom=chrom, start=start,
        ref="C" if chrom else None, alts="T" if chrom else None,
        genotype="C/T", state="risk", conclusion="c",
    )


def test_a_gene_on_another_chromosome_than_its_variant_is_reported() -> None:
    """The four real pairings from the report, each individually valid and jointly false."""
    variants = [
        _row("rs13010010", "CADM2", "2", 100),    # CADM2 is on 3
        _row("rs2252481", "NEGR1", "6", 100),     # NEGR1 is on 1
        _row("rs10180596", "EXOC3L2", "2", 100),  # EXOC3L2 is on 19
        _row("rs36071874", "FOXO3", "1", 100),    # FOXO3 is on 6
        _row("rs1421085", "FTO", "16", 53767042),  # the true pairing, and it must stay silent
    ]
    report = check_identifiers(variants=variants, check_traits=False, client=_hgnc_with_locations())

    assert {c.gene for c in report.gene_loci} == {"CADM2", "NEGR1", "EXOC3L2", "FOXO3"}
    assert report.gene_loci_not_checked is None
    assert not report.clean
    assert "is not in it" in str(report.gene_loci[0])


def test_the_check_is_chromosome_level_and_not_an_interval() -> None:
    """`rs1421085` sits in an FTO intron and acts on IRX3/IRX5 megabases away, so a row may name any
    of the three. An interval check would fire on correct rows; this one must not."""
    report = check_identifiers(
        variants=[_row("rs1421085", "FTO", "16", 1)],   # nowhere near the gene body, same contig
        check_traits=False, client=_hgnc_with_locations(),
    )
    assert report.gene_loci == [] and report.clean


def test_an_unknown_symbol_or_missing_chromosome_withholds_rather_than_accuses() -> None:
    """Three-valued: no HGNC record, and no known chromosome for the row, both withhold — and say so,
    because an empty conflict list otherwise means both 'compared' and 'never compared'."""
    unknown = check_identifiers(
        variants=[_row("rs1", "NOTAGENE", "1", 100)],
        check_traits=False, client=_hgnc_with_locations(),
    )
    assert unknown.gene_loci == []
    assert unknown.gene_loci_not_checked == "HGNC returned no usable chromosome for any authored gene"

    unresolved = check_identifiers(
        variants=[_row("rs13010010", "CADM2")],     # rsID only: no chromosome anywhere yet
        check_traits=False, client=_hgnc_with_locations(),
    )
    assert unresolved.gene_loci == []
    assert unresolved.gene_loci_not_checked is not None


def test_the_resolved_chromosome_is_read_from_an_injected_resolution_table(tmp_path: Path) -> None:
    """The reporter's actual shape — an rsID-only row, where the chromosome exists only after
    resolution. `resolution.csv` beside the spec is the same table the compiler consumes."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: d\n  title: D\n  description: d\n  report_title: D\n"
    )
    (spec / "variants.csv").write_text(
        "rsid,gene,genotype,state,conclusion\nrs2252481,NEGR1,C/T,risk,c\n"
    )
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,"
        "rsid_alternates,rsid_current,rsid_status,fetched_at\n"
        "rs2252481,rs2252481,6,100,C,T,GRCh38,0,manual,resolved,,,,\n"
    )
    report = check_identifiers(spec_dir=spec, check_traits=False, client=_hgnc_with_locations())

    assert [c.gene for c in report.gene_loci] == ["NEGR1"]
    assert report.gene_loci[0].variant_chrom == "6" and report.gene_loci[0].gene_chrom == "1"


def test_a_pseudoautosomal_gene_is_not_a_conflict() -> None:
    """One place on two contigs: XG straddles the PAR1 boundary, so an X/Y disagreement there is a
    spelling rather than a contradiction (RM32)."""
    report = check_identifiers(
        variants=[_row("rs311103", "XG", "Y", 2691222)],
        check_traits=False, client=_hgnc_with_locations(),
    )
    assert report.gene_loci == []
