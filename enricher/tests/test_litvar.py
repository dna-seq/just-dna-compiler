"""RM167 — the tier a locus is answerable at, and the three outcomes the source itself supplies.

Everything below replays **real payloads recorded from LitVar2 and the ClinGen Allele Registry on
2026-09-01** (`assets/litvar_slice/`), through the real client and the real pass, and **every expected
count is recomputed from the fixture at run time**. None of the numbers in the proposal document is
hard-coded here: 3,945 and 328 are what the source served on one day, and quoting one into an
assertion would turn a live index into a permanently failing test. What is pinned is the *arithmetic*
and the *tiering*, which are this lane's contract.

The one live test is opt-in behind `JUST_DNA_NETWORK_TESTS`, and it carries the bound: the four
candidate alleles the CIViC legacy-insertion probe produced have no node at all, which is the proof
that this surface answers *which papers discuss an identified allele* and not *which allele a name
meant*.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.clingen_allele import ClingenAlleleClient
from just_dna_enricher.litvar import (
    COVERAGE_REASON_TIER,
    VALID_COVERAGE_REASON,
    VALID_COVERAGE_TIER,
    LitvarClient,
    LitvarUnavailable,
    LocusCoverage,
    check_literature_coverage,
    coverage_reason,
    module_loci,
    parse_repr_lines,
    rsid_bearing_tables,
    verification_records,
)
from just_dna_enricher.net import PacingGate

SLICE = Path(__file__).resolve().parents[2] / "assets" / "litvar_slice"
INDEX: dict[str, dict] = json.loads((SLICE / "index.json").read_text(encoding="utf-8"))

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: rm167\n  title: RM167\n  description: d\n  report_title: RM167\n"
)


def _body(url: str) -> str:
    return (SLICE / INDEX[url]["file"]).read_text(encoding="utf-8")


def _recorded_pmids(node_id: str) -> frozenset[int]:
    """The PMID set a recorded `publications` response holds, read straight off the fixture."""
    for url, entry in INDEX.items():
        if url.endswith("/publications") and node_id.replace("@", "%40").replace(
            "#", "%23"
        ) in url:
            payload = json.loads((SLICE / entry["file"]).read_text(encoding="utf-8"))
            return frozenset(payload["pmids"])
    raise AssertionError(f"no recorded publications response for {node_id}")


def _replay(request: httpx.Request) -> httpx.Response:
    """Serve a recorded response, or refuse loudly — a silent 404 would look like an absent variant."""
    url = str(request.url)
    entry = INDEX.get(url)
    if entry is None:
        raise AssertionError(f"the suite asked for a URL nothing was recorded for: {url}")
    return httpx.Response(entry["status"], text=(SLICE / entry["file"]).read_text(encoding="utf-8"))


def _instant_gate() -> PacingGate:
    return PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)


def _clients(
    handler=_replay, registry_handler=None
) -> tuple[LitvarClient, ClingenAlleleClient]:
    index = LitvarClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)), gate=_instant_gate()
    )
    registry = ClingenAlleleClient(
        client=httpx.Client(transport=httpx.MockTransport(registry_handler or handler))
    )
    registry._gate = _instant_gate()
    return index, registry


def _spec(tmp_path: Path, **tables: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    for name, body in tables.items():
        (spec / name.replace("__", ".")).write_text(body, encoding="utf-8")
    return spec


def _cover(spec: Path, **kwargs):
    index, registry = _clients(**kwargs)
    return check_literature_coverage(spec, client=index, registry=registry)


# ── the payload that is not JSON ────────────────────────────────────────────────────────────────


def test_the_gene_search_payload_is_python_repr_and_json_cannot_read_it() -> None:
    """`.json()` on this endpoint raises. Demonstrated on the real bytes, not asserted about them."""
    text = _body("https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/search/gene/HFE")
    with pytest.raises(ValueError):
        json.loads(text)
    rows = parse_repr_lines(text)
    assert rows, "the recorded gene payload is empty; this test is reading nothing"
    # Every non-blank line becomes exactly one record: a parser that silently dropped one would make
    # a short answer indistinguishable from a complete one.
    assert len(rows) == len([line for line in text.splitlines() if line.strip()])


def test_the_gene_search_tiers_are_derived_from_the_record_rather_than_from_the_id(
    tmp_path: Path,
) -> None:
    """`search/gene` carries no `flag_*` at all, so the tier comes from the keys each record has.

    The split is the reason to look at this endpoint: an id under a gene with a protein string in the
    last slot is a **text mention**, not a variant, and joining on one is `@existence-not-identity`.
    """
    text = _body("https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/search/gene/HFE")
    rows = parse_repr_lines(text)
    index, _registry = _clients()
    nodes = index.gene_nodes("HFE")

    assert {node.node_id for node in nodes} == {row["_id"] for row in rows}
    # Recomputed from the fixture, never copied out of the proposal.
    expected = {
        "clingen": {row["_id"] for row in rows if row.get("clingen_id")},
        "rsid": {row["_id"] for row in rows if row.get("rsid") and not row.get("clingen_id")},
        "gene": {
            row["_id"]
            for row in rows
            if not row.get("rsid") and not row.get("clingen_id") and row["_id"].endswith("#")
        },
        "mention": {
            row["_id"]
            for row in rows
            if not row.get("rsid") and not row.get("clingen_id") and not row["_id"].endswith("#")
        },
    }
    for tier, ids in expected.items():
        assert {node.node_id for node in nodes if node.tier == tier} == ids
    # The mention tail is the bulk of it, which is the thing a reader must not mistake for coverage.
    assert len(expected["mention"]) > len(expected["clingen"])


def test_nothing_in_this_lane_calls_json_on_a_response() -> None:
    """The structural half: `httpx`'s `.json()` raises on one of the five endpoints, so it is banned.

    An AST walk rather than a `grep`, and it fails the moment a sixth method reaches for the
    convenience — which is exactly how the defect would come back.
    """
    source = (
        Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher" / "litvar.py"
    ).read_text(encoding="utf-8")
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "json"
    ]
    assert calls == [], "litvar.py calls .json() — one endpoint serves Python repr() and it raises"


def test_the_parser_is_a_literal_reader_and_never_eval() -> None:
    """A payload that is Python source is the shape where `eval` looks convenient. It is not used.

    Proved on behaviour, not on the source: a line that is a *call* rather than a literal is refused,
    which `eval` would have executed.
    """
    with pytest.raises(Exception) as caught:
        parse_repr_lines("__import__('os').getcwd()\n")
    assert "not a Python literal" in str(caught.value)


# ── the three outcomes ──────────────────────────────────────────────────────────────────────────


def test_an_allele_node_answers_and_the_position_only_residue_is_counted_separately(
    tmp_path: Path,
) -> None:
    """APOE rs429358 — the case the whole item turns on.

    The module names the C allele, the index holds one allele node for it, and the two counts differ
    by more than a factor of ten. Reporting the position node's count as *the* answer would overstate
    the allele; folding the residue into it would lose the fact that most of the locus's literature is
    not allele-resolved at all. Both numbers, plus the residue, side by side.
    """
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs429358,19,44908684,T,C,C/T,risk,c\n"
        ),
    )
    report = _cover(spec)
    (locus,) = report.loci
    position = _recorded_pmids("litvar@rs429358##")
    allele = _recorded_pmids("litvar@CA127512#rs429358##")

    assert (locus.tier, locus.asked_tier, locus.reason) == (
        "allele", "allele", "allele_node_matched",
    )
    assert locus.matched_caids == ("CA127512",)
    assert locus.allele_pmids == len(allele)
    assert locus.position_pmids == len(position)
    # The residue is a set difference, not a subtraction: the allele node's papers are a subset of the
    # position node's here, and at other loci they are not.
    assert locus.position_only_pmids == len(position - allele)
    assert locus.allele_pmids < locus.position_pmids, (
        "the fixture no longer exercises the case this test is about"
    )
    assert not locus.degraded


def test_a_locus_with_no_allele_node_is_answered_at_position_tier(tmp_path: Path) -> None:
    """rs9366637: the index holds a position node and no ClinGen id at all.

    That is an answer — the literature at this locus is not allele-resolved by the source — and it is
    a *degraded* one, because the module asked at allele level. It is not an absence and not a zero.
    """
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs9366637,6,26098474,C,T,C/T,risk,c\n"
        ),
    )
    (locus,) = _cover(spec).loci
    assert (locus.tier, locus.reason) == ("position", "no_allele_node_at_locus")
    assert locus.allele_pmids is None, "a position answer must not be reported as the allele's"
    assert locus.position_pmids == len(_recorded_pmids("litvar@rs9366637##"))
    # No allele node claims anything here, so every paper on the position node is residue.
    assert locus.position_only_pmids == locus.position_pmids
    assert locus.degraded


def test_an_absent_rsid_is_the_third_outcome_and_not_a_zero_pmid_allele_answer(
    tmp_path: Path,
) -> None:
    """rs776994377 — a real rsID from this repository's own HFE module that LitVar holds nothing for.

    `autocomplete` answers 200 with `[]`, which is the index saying *no*. Recording that as an allele
    answer of zero papers would be a claim about an allele node that does not exist.
    """
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs776994377,6,26090951,G,C,C/C,risk,c\n"
        ),
    )
    (locus,) = _cover(spec).loci
    assert (locus.tier, locus.reason) == ("absent", "no_node_for_rsid")
    assert (locus.allele_pmids, locus.position_pmids, locus.position_only_pmids) == (
        None, None, None,
    )
    assert not locus.degraded, "an absence is not an allele question answered at position level"


def test_allele_nodes_that_name_other_alleles_withhold_the_allele_answer(tmp_path: Path) -> None:
    """rs146519482 carries two allele nodes, G>C and G>T. A module naming G>A matches neither.

    `@refutation-withholds`: the answer is withheld at allele level and reported at position level
    with the tier named, never approximated by handing over the position count as the allele's.
    """
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs146519482,6,26091475,G,A,A/G,risk,c\n"
        ),
    )
    (locus,) = _cover(spec).loci
    assert (locus.tier, locus.reason) == ("position", "allele_nodes_name_other_alleles")
    assert locus.allele_pmids is None
    assert set(locus.caids_at_locus) == {"CA354214", "CA346923"}
    assert locus.degraded


def test_a_multi_caid_locus_takes_the_residue_over_every_allele_node_not_just_the_matched_one(
    tmp_path: Path,
) -> None:
    """The residue is *papers no allele node claims*, so it comes off the union of all of them.

    rs146519482's two nodes overlap the position node differently; taking the matched node alone would
    report papers as unresolved that the sibling allele node does claim.
    """
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs146519482,6,26091475,G,C,C/G,risk,c\n"
        ),
    )
    (locus,) = _cover(spec).loci
    position = _recorded_pmids("litvar@rs146519482##")
    matched = _recorded_pmids("litvar@CA354214#rs146519482##")
    sibling = _recorded_pmids("litvar@CA346923#rs146519482##")

    assert (locus.tier, locus.matched_caids) == ("allele", ("CA354214",))
    assert locus.allele_pmids == len(matched)
    assert locus.position_only_pmids == len(position - (matched | sibling))
    # The distinction this test exists for: the union really is narrower than the matched node alone.
    assert len(position - matched) > len(position - (matched | sibling))


def test_a_module_that_names_no_allele_asks_a_position_level_question(tmp_path: Path) -> None:
    """The asked tier is a property of the module's rows.

    Without it every locus of a purely positional module would be counted as a shortfall, when the
    position node answered exactly the question that was put.
    """
    spec = _spec(
        tmp_path,
        studies__csv="rsid,pmid\nrs429358,25741868\n",
    )
    (locus,) = _cover(spec).loci
    assert (locus.asked_tier, locus.tier, locus.reason) == (
        "position", "position", "row_names_no_allele",
    )
    assert not locus.degraded
    assert verification_records(_cover(spec))[0].findings == 0


# ── the fourth state: could not ask ─────────────────────────────────────────────────────────────


def test_an_unreachable_registry_is_unchecked_rather_than_a_position_level_answer(
    tmp_path: Path,
) -> None:
    """The collapse `@answered-is-not-absent` names, one tier out.

    LitVar lists CAIDs at this locus and the registry never says what they are, so *none of them is
    this module's allele* was never established. Reporting position level would publish an unasked
    question as an answer.
    """
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs429358,19,44908684,T,C,C/T,risk,c\n"
        ),
    )
    report = _cover(
        spec, registry_handler=lambda request: httpx.Response(503, json={"detail": "down"})
    )
    (locus,) = report.loci
    assert (locus.tier, locus.reason) == ("unchecked", "registry_unreachable")
    assert locus.allele_pmids is None and locus.position_pmids is None
    # And it stays out of the denominator: a locus nothing was learned about is not a subject.
    assert report.answered == []
    assert verification_records(report)[0].skipped == "unreachable"


def test_an_unreachable_index_is_unchecked_and_says_which_source_was_not_reached(
    tmp_path: Path,
) -> None:
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs429358,19,44908684,T,C,C/T,risk,c\n"
        ),
    )
    report = _cover(spec, handler=lambda request: httpx.Response(503, json={"detail": "down"}))
    (locus,) = report.loci
    assert (locus.tier, locus.reason) == ("unchecked", "index_unreachable")


def test_offline_asks_nothing_and_records_a_skip_rather_than_an_absence(tmp_path: Path) -> None:
    """`--offline` is nobody-asked, which is a different fact from *the index holds nothing*."""
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs429358,19,44908684,T,C,C/T,risk,c\n"
        ),
    )
    report = check_literature_coverage(spec, offline=True)
    (locus,) = report.loci
    assert (locus.tier, locus.reason) == ("unchecked", "offline")
    (record,) = verification_records(report)
    # A skip carries no denominator — `VerificationRecord` refuses one — so the count of loci that
    # were *not* asked about lives in `detail`, where a reader can see it was not zero.
    assert record.skipped == "offline" and record.subjects == 0
    assert "1 locus" in record.detail


# ── the client's own contract ───────────────────────────────────────────────────────────────────


def test_a_400_saying_variant_not_found_is_an_answer_and_any_other_400_is_not() -> None:
    """The discriminator is the body, never the status — a malformed query is also a 400.

    Both halves, because reading the status alone would turn a client bug into a permanent negative
    about a variant, and reading nothing would turn an answered absence into an outage.
    """
    absent = LitvarClient(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    400, json={"detail": "Variant not found: litvar@rs1##"}
                )
            )
        ),
        gate=_instant_gate(),
    )
    assert absent.autocomplete("rs1") == []
    assert absent.pmids("litvar@rs1##") == frozenset()

    broken = LitvarClient(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(400, json={"detail": "malformed query"})
            )
        ),
        gate=_instant_gate(),
    )
    with pytest.raises(LitvarUnavailable):
        broken.autocomplete("rs1")


def test_autocomplete_is_a_prefix_search_so_a_neighbouring_rsid_never_answers() -> None:
    """`?query=rs429358` really returns `rs42935848` as well — a real node for a different variant.

    Taking `[0]` off that list is how a lookup answers confidently about the wrong thing
    (`@existence-not-identity`). The filter is exact, and the fixture carries the trap.
    """
    index, _registry = _clients()
    hits = index.autocomplete("rs429358")
    assert len({node.rsid for node in hits}) > 1, "the fixture no longer carries the prefix trap"
    node = index.position_node("rs429358")
    assert node is not None and node.rsid == "rs429358"


def test_one_locus_reached_from_two_tables_is_one_request(tmp_path: Path) -> None:
    """The per-run cache. A module naming the same rsID in three tables must not ask three times."""
    seen: list[str] = []

    def counting(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _replay(request)

    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs429358,19,44908684,T,C,C/T,risk,c\n"
        ),
        studies__csv="rsid,pmid\nrs429358,25741868\n",
        haplotypes__csv="haplotype_name,rsid,chrom,start,ref,allele,gene\ne4,rs429358,19,44908684,T,C,APOE\n",
    )
    _cover(spec, handler=counting)
    assert len(seen) == len(set(seen)), sorted(url for url in seen if seen.count(url) > 1)


# ── the reasons, the roster and the record ──────────────────────────────────────────────────────


def test_every_tier_has_arms_and_every_arm_has_its_own_sentence() -> None:
    """A verdict function with several arms owes a reason function with the same arms, pairwise
    distinct (`@answered-is-not-absent`). Walked, so an arm added without a sentence fails here."""
    assert set(COVERAGE_REASON_TIER) == VALID_COVERAGE_REASON
    assert set(COVERAGE_REASON_TIER.values()) == VALID_COVERAGE_TIER

    sentences = {
        reason: coverage_reason(
            LocusCoverage(
                rsid="rs1",
                asked_tier="allele",
                tier=COVERAGE_REASON_TIER[reason],
                reason=reason,
                caids_at_locus=("CA1",),
                matched_caids=("CA1",),
            )
        )
        for reason in sorted(VALID_COVERAGE_REASON)
    }
    assert len(set(sentences.values())) == len(sentences), sorted(sentences.values())


def test_the_locus_roster_is_every_rsid_bearing_authored_table(tmp_path: Path) -> None:
    """Derived from `DRAFTABLE`, never restated — a table kind added later joins by existing.

    An equality over the walked set (`@registry-completeness`), not a floor.
    """
    from just_dna_compiler.draft import DRAFTABLE
    from just_dna_format.base import AuthoredModel

    walked = {
        name
        for name, model in DRAFTABLE.items()
        if isinstance(model, type)
        and issubclass(model, AuthoredModel)
        and "rsid" in model.model_fields
    }
    assert set(rsid_bearing_tables()) == walked

    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs429358,19,44908684,T,C,C/T,risk,c\n"
        ),
        haplotypes__csv=(
            "haplotype_name,rsid,chrom,start,ref,allele,gene\n"
            "e4,rs7412,19,44908822,C,C,APOE\n"
        ),
    )
    roster = module_loci(spec)
    # Both tables contributed, and the allele columns came off the models rather than a list here.
    assert set(roster.rsids) == {"rs429358", "rs7412"}
    assert set(roster.alleles["rs429358"]) == {"C", "T"}
    assert roster.alleles["rs7412"] == ["C"]
    assert set(roster.read) >= {"variants.csv", "haplotypes.csv"}


def test_a_caid_recorded_in_resolution_csv_answers_without_a_registry_lookup(
    tmp_path: Path,
) -> None:
    """RM153 puts the module's own allele identity in `resolution.csv`; that is the shortest route.

    The registry transport refuses every request here, so a pass that reached for it would land on
    `registry_unreachable` rather than an allele answer.
    """
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs429358,19,44908684,T,C,C/T,risk,c\n"
        ),
        resolution__csv=(
            "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,caid,source,status\n"
            "rs429358,rs429358,19,44908684,T,C,GRCh38,0,CA127512,manual,resolved\n"
        ),
    )
    report = _cover(
        spec, registry_handler=lambda request: httpx.Response(503, json={"detail": "down"})
    )
    (locus,) = report.loci
    assert (locus.tier, locus.matched_caids) == ("allele", ("CA127512",))
    assert "resolution.csv" in report.tables_read


def test_the_record_names_the_tier_and_counts_the_degraded_loci(tmp_path: Path) -> None:
    """A coverage answer that does not say which tier answered is the defect this item is about.

    `findings` is the loci where an allele-level question came back position-level; an absence is an
    answered zero and is not one of those. `subjects` is what was answered, so a locus nothing was
    learned about never lands in the denominator.
    """
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
            "rs429358,19,44908684,T,C,C/T,risk,c\n"
            "rs9366637,6,26098474,C,T,C/T,risk,c\n"
            "rs776994377,6,26090951,G,C,C/C,risk,c\n"
        ),
    )
    report = _cover(spec)
    (record,) = verification_records(report)

    tiers = {locus.rsid: locus.tier for locus in report.loci}
    assert tiers == {"rs429358": "allele", "rs9366637": "position", "rs776994377": "absent"}
    assert record.check == "literature_coverage"
    assert record.source == "litvar"
    assert record.subjects == len(report.answered) == 3
    assert record.findings == len(report.degraded) == 1
    for word in ("allele tier", "position tier", "absent"):
        assert word in record.detail
    assert "rs9366637" in record.detail
    assert str(report.position_only_residue) in record.detail
    # The residue is the sum over the loci that have one, not over the loci.
    assert report.position_only_residue == sum(
        locus.position_only_pmids or 0 for locus in report.loci
    )


def test_a_module_naming_no_rsid_records_nothing_to_check(tmp_path: Path) -> None:
    """A skip, not a zero: `0 loci, 0 findings` would read as a clean pass over an unasked question."""
    spec = _spec(tmp_path)
    report = check_literature_coverage(spec)
    (record,) = verification_records(report)
    assert report.loci == []
    assert record.skipped == "nothing_to_check"


# ── live ────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.getenv("JUST_DNA_NETWORK_TESTS"), reason="set JUST_DNA_NETWORK_TESTS=1 to hit LitVar"
)
def test_live_the_index_still_tiers_apoe_and_still_holds_nothing_for_the_civic_insertions() -> None:
    """Two live facts, and the second is the bound this lane ships with.

    The first is the shape, not the number: rs429358 has a position node and an allele node beside it,
    and the allele node is the smaller. The second is the refusal — the four candidate alleles the
    CIViC legacy-insertion probe worked out by hand have registered CAIDs and **no LitVar node**,
    because PubTator3 mines titles and abstracts and those alleles live in a table inside a paywalled
    paper. If a node ever appears for one of them this test fails, which is the right outcome: the
    documented bound would have moved and the documentation would need to say so.
    """
    index = LitvarClient()
    node = index.position_node("rs429358")
    assert node is not None
    caids = (index.node(node.node_id) or {}).get("clingen_ids") or []
    assert caids, "rs429358 lost its allele tier"
    allele = index.allele_node(str(caids[0]))
    assert allele is not None
    assert 0 < len(index.pmids(allele.node_id)) < len(index.pmids(node.node_id))

    for caid in ("CA2586965638", "CA2501268513", "CA2573048346", "CA2499307076"):
        assert index.allele_node(caid) is None, (
            f"{caid} now has a LitVar node — the bound in this lane's documentation has moved"
        )
