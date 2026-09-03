"""RM160 — citations recovered from CIViC's API, and the canary that re-asks about them.

Every payload here is a **recorded real response** from `assets/civic_api_slice/` (see its README for
what each one is for and why), served through an `httpx.MockTransport` so the suite never fetches
(`@network-tests-optin`). Every expected value is derived from those files at runtime: no count is
copied out of a data dump into an assertion, and where a shape the corpus does not contain is needed —
a citation whose every item was rejected — the payload is **filtered** from those same real rows
rather than invented, which is the rule `test_civic_refutation` follows one module over.

The three things this file exists to pin, all of them non-negotiable:

* an `accepted` row and a `submitted` row are not the same row once both are in the file;
* `--offline` records `skipped`/`offline` and never `ran, findings=0` — *nobody asked* and *the source
  has nothing more* are different facts;
* a second run over an unchanged API appends nothing.
"""

import json
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.civic_api import (
    CIVIC_STATUS_UNIT,
    CivicApiClient,
    CivicApiError,
    CivicApiUnavailable,
    _parse_item,
)
from just_dna_enricher.civic_citations import (
    CIVIC_API_DATASET,
    CIVIC_CITATION_ADDED,
    CIVIC_CITATION_LAYER,
    CIVIC_STATUS_MOVED,
    RecoveredCitation,
    check_evidence_status_currency,
    draft_civic_citations,
    plan_subjects,
    read_module,
    read_studies,
    recorded_civic_citations,
)
from just_dna_enricher.civic_identities import CIVIC_NAME_IDENTITIES
from just_dna_enricher.civic_refutation import civic_snapshot_rows
from just_dna_enricher.net import PacingGate
from just_dna_format.sources import SourceRow
from just_dna_format.spec import VariantRow

SLICE = Path(__file__).resolve().parents[2] / "assets" / "civic_api_slice"

#: The motivating record: two items, one accepted and one submitted, and the submitted one is the
#: only reachable evidence for the identity question the whole item started from.
MOTIVATING_VARIANT = 1955

#: The volume record — 37 items, five of them citing one paper.
WIDE_VARIANT = 844

#: The only recorded variant carrying a rejected item.
REJECTING_VARIANT = 1939

_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm160\n"
    "  title: RM160\n"
    "  description: citations recovered from CIViC's API\n"
    "  report_title: RM160\n"
    "genome_build: GRCh38\n"
)


def _body(variant_id: int) -> dict:
    return json.loads((SLICE / f"evidence_{variant_id}.json").read_text(encoding="utf-8"))


def _nodes(variant_id: int) -> list[dict]:
    return _body(variant_id)["data"]["evidenceItems"]["nodes"]


def _instant_gate() -> PacingGate:
    """A gate that never sleeps, so a test costs no wall-clock."""
    return PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)


def _client(bodies: dict[int, dict]) -> CivicApiClient:
    """A client answering from recorded bodies, keyed by the variant id the query really asks for."""

    def handler(request: httpx.Request) -> httpx.Response:
        variables = json.loads(request.content)["variables"]
        variant_id = variables["id"]
        if variant_id not in bodies:
            return httpx.Response(404, json={"errors": [{"message": "not recorded"}]})
        return httpx.Response(200, json=bodies[variant_id])

    return CivicApiClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)), gate=_instant_gate()
    )


def _spec(directory: Path, *, variants: str = "", studies: str = "", resolution: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_SPEC_YAML)
    if variants:
        (directory / "variants.csv").write_text(variants)
    if studies:
        (directory / "studies.csv").write_text(studies)
    if resolution:
        (directory / "resolution.csv").write_text(resolution)
    return directory


def _authored(chrom: str, start: int, ref: str, alt: str, rsid: str | None = None) -> tuple[str, str]:
    """`(variants.csv, resolution.csv)` for one row at a coordinate, as CSV text."""
    row = VariantRow(
        rsid=rsid, chrom=chrom, start=start, ref=ref, alts=alt,
        genotype=f"{alt}/{alt}", state="risk", conclusion="authored for this test",
    )
    variants = (
        "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
        f"{rsid or ''},{chrom},{start},{ref},{alt},{alt}/{alt},risk,authored for this test\n"
    )
    resolution = (
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        f"{row.variant_key},{rsid or ''},{chrom},{start},{ref},{alt},GRCh38,0,authored,resolved\n"
    )
    return variants, resolution


# ── the client ──────────────────────────────────────────────────────────────────────────────────


def test_a_recorded_response_parses_into_the_items_it_carries() -> None:
    """Every field echoed, the status lower-cased, and nothing else converted."""
    client = _client({MOTIVATING_VARIANT: _body(MOTIVATING_VARIANT)})
    items = client.evidence_items(MOTIVATING_VARIANT)
    recorded = _nodes(MOTIVATING_VARIANT)

    assert [item.evidence_id for item in items] == [node["id"] for node in recorded]
    assert [item.status for item in items] == [node["status"].lower() for node in recorded]
    assert {item.pmid for item in items} == {
        node["source"]["citationId"] for node in recorded
        if node["source"]["sourceType"] == "PUBMED"
    }
    # The whole point of the lane: the two items on this variant differ in exactly this, and the
    # submitted one is the citation no dated file carries.
    assert {item.status for item in items} == {"accepted", "submitted"}


def test_the_client_pages_and_a_second_ask_is_not_a_second_request() -> None:
    """`hasNextPage` is followed, and one client answers a repeated question from its own cache.

    The pages are the recorded 37-item response split in two, so the rows are real and the split is
    the only thing constructed. A reader that took the first page would report a variant with 34
    hidden citations as having a handful, which is the defect this asserts against.
    """
    whole = _body(WIDE_VARIANT)
    nodes = whole["data"]["evidenceItems"]["nodes"]
    half = len(nodes) // 2
    requests: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        after = json.loads(request.content)["variables"]["after"]
        requests.append(after)
        first = after is None
        page = dict(whole["data"]["evidenceItems"])
        page["nodes"] = nodes[:half] if first else nodes[half:]
        page["pageInfo"] = {"hasNextPage": first, "endCursor": "cursor" if first else None}
        return httpx.Response(200, json={"data": {"evidenceItems": page}})

    client = CivicApiClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)), gate=_instant_gate()
    )
    items = client.evidence_items(WIDE_VARIANT)
    assert [item.evidence_id for item in items] == [node["id"] for node in nodes]
    assert requests == [None, "cursor"]

    client.evidence_items(WIDE_VARIANT)
    assert requests == [None, "cursor"], "a cached variant must not be asked about twice"


def test_a_short_read_warns_against_the_payloads_own_total(caplog) -> None:
    """`totalCount` sits in the same payload as the nodes, so a truncated read is checkable."""
    whole = _body(WIDE_VARIANT)
    listing = dict(whole["data"]["evidenceItems"])
    listing["nodes"] = listing["nodes"][:1]
    listing["pageInfo"] = {"hasNextPage": False, "endCursor": None}
    client = CivicApiClient(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _r: httpx.Response(200, json={"data": {"evidenceItems": listing}})
            )
        ),
        gate=_instant_gate(),
    )
    with caplog.at_level("WARNING"):
        items = client.evidence_items(WIDE_VARIANT)
    assert len(items) == 1
    assert str(listing["totalCount"]) in caplog.text
    # The served items are still returned: a partial answer is not no answer.
    assert items[0].evidence_id == listing["nodes"][0]["id"]


def test_offline_refuses_before_any_transport_is_touched() -> None:
    """`@off-switch-needs-a-probe`: run the disabling value, do not read it.

    The transport fails the test if it is reached, so this proves the switch is a refusal rather than
    a filter applied to an answer that was already fetched.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("--offline reached the network")

    client = CivicApiClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        gate=_instant_gate(),
        offline=True,
    )
    assert client.offline is True
    with pytest.raises(CivicApiUnavailable):
        client.evidence_items(MOTIVATING_VARIANT)


def test_a_graphql_error_is_this_tiers_error_and_not_the_unavailability_subclass() -> None:
    """The service answered; what failed is the query. A caller must be able to tell those apart."""
    client = CivicApiClient(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _r: httpx.Response(200, json={"errors": [{"message": "no such field"}]})
            )
        ),
        gate=_instant_gate(),
    )
    with pytest.raises(CivicApiError) as caught:
        client.evidence_items(MOTIVATING_VARIANT)
    assert not isinstance(caught.value, CivicApiUnavailable)


def test_an_unknown_status_raises_rather_than_defaulting() -> None:
    """`@lookup-with-a-default-hides-a-new-member`, on the vocabulary every count here keys on."""
    node = dict(_nodes(MOTIVATING_VARIANT)[0])
    node["status"] = "PROVISIONAL"
    with pytest.raises(CivicApiError, match="status"):
        _parse_item(node, MOTIVATING_VARIANT)


def test_a_non_pubmed_citation_withholds_the_pmid() -> None:
    """An ASCO/ASH `citationId` is a real id in another namespace, and `pmid` withholds rather than
    borrowing it (`@pmid-vs-pmcid`)."""
    node = dict(_nodes(MOTIVATING_VARIANT)[0])
    node["source"] = dict(node["source"], sourceType="ASCO", citationId="12345")
    assert _parse_item(node, MOTIVATING_VARIANT).pmid is None


def test_a_citation_two_items_disagree_about_withholds_its_status() -> None:
    """Unknown is withheld, never picked. Built from two real items with two real statuses."""
    items = [_parse_item(node, WIDE_VARIANT) for node in _nodes(WIDE_VARIANT)]
    accepted = next(item for item in items if item.status == "accepted")
    submitted = next(item for item in items if item.status == "submitted")
    subject = plan_subjects([], [], reference=None, requested=[WIDE_VARIANT])[0][0]
    disagreeing = RecoveredCitation(
        subject=subject,
        pmid=accepted.pmid or "1",
        items=(accepted, submitted),
    )
    assert disagreeing.status is None
    agreeing = RecoveredCitation(disagreeing.subject, disagreeing.pmid, (accepted,))
    assert agreeing.status == "accepted"


# ── drafting ────────────────────────────────────────────────────────────────────────────────────


def test_the_motivating_citation_is_recovered_and_a_second_run_adds_nothing(tmp_path) -> None:
    """Variant 1955's submitted evidence reaches `studies.csv`, and drafting is idempotent.

    `--variant-id` is the route, because neither the snapshot nor the curated identity table can
    place this record — being unplaceable is why its citations were unreachable in the first place.
    The rows it writes name no variant, which `StudyRow` has permitted since RM47.
    """
    spec = _spec(tmp_path / "spec", studies="rsid,pmid\n")
    client = _client({MOTIVATING_VARIANT: _body(MOTIVATING_VARIANT)})

    result = draft_civic_citations(
        spec, variants=[], resolution_rows=[], reference=None,
        requested=[MOTIVATING_VARIANT], client=client,
    )
    recorded = [
        node for node in _nodes(MOTIVATING_VARIANT) if node["source"]["sourceType"] == "PUBMED"
    ]
    expected = {node["source"]["citationId"]: node["status"].lower() for node in recorded}
    assert result.added == len(expected)

    studies = read_studies(spec)
    assert {row.pmid: row.confidence for row in studies if row.confidence} == expected
    assert {row.confidence_unit for row in studies if row.confidence} == {CIVIC_STATUS_UNIT}
    # The one that matters: the submitted item is in the file and is *labelled* submitted.
    assert "submitted" in set(expected.values())
    # No timestamp in the prose — the pin lives on the SourceRow, and a moment is not a claim.
    assert all("T0" not in (row.conclusion or "") for row in studies)

    again = draft_civic_citations(
        spec, variants=[], resolution_rows=[], reference=None,
        requested=[MOTIVATING_VARIANT], client=_client({MOTIVATING_VARIANT: _body(MOTIVATING_VARIANT)}),
    )
    assert again.added == 0
    assert read_studies(spec) == studies


def test_the_drafted_rows_carry_their_pin_on_the_source_row(tmp_path) -> None:
    """When the API was asked and on what basis, as fields on `(civic, literature)`.

    `literature` rather than `annotation` on purpose: `(civic, annotation)` is the snapshot drafter's
    slot, and a second surface of one source may not claim it.
    """
    spec = _spec(tmp_path / "spec", studies="rsid,pmid\n")
    result = draft_civic_citations(
        spec, variants=[], resolution_rows=[], reference=None,
        requested=[MOTIVATING_VARIANT], client=_client({MOTIVATING_VARIANT: _body(MOTIVATING_VARIANT)}),
    )
    row = next(r for r in result.sources if r.layer == CIVIC_CITATION_LAYER)
    assert row.source == "civic"
    assert row.dataset == CIVIC_API_DATASET
    assert row.fetched_at, "a drafted row with no ask time is a claim about a moment nobody wrote down"
    # Every column the model declares round-trips through the file the pass wrote.
    written = [r for r in _sources(spec) if r.layer == CIVIC_CITATION_LAYER]
    assert [r.dataset for r in written] == [CIVIC_API_DATASET]


def _sources(spec: Path) -> list[SourceRow]:
    from just_dna_compiler.compiler import load_csv_rows

    path = next(p for p in (spec / "licensing.csv", spec / "sources.csv") if p.exists())
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    assert not errors, errors
    return rows


def test_a_run_that_appends_nothing_writes_no_source_row(tmp_path) -> None:
    """The converse of `@write-the-sourcerow`: a pass contributing nothing records nothing.

    A `sources.csv` row travels to a registry meaning *this module uses this source*, so a row from a
    run that added no citation is a false statement in a published artifact.
    """
    spec = _spec(tmp_path / "spec", studies="rsid,pmid\n")
    result = draft_civic_citations(
        spec, variants=[], resolution_rows=[], reference=None, requested=[],
        client=_client({}),
    )
    assert result.added == 0 and result.sources == []
    assert not (spec / "licensing.csv").exists() and not (spec / "sources.csv").exists()


def test_offline_records_every_subject_as_not_asked_and_writes_nothing(tmp_path) -> None:
    """`ran, findings=0` is the answer this must never give (`@unreachable-not-absent`)."""
    spec = _spec(tmp_path / "spec", studies="rsid,pmid\n")

    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("--offline reached the network")

    client = CivicApiClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        gate=_instant_gate(),
        offline=True,
    )
    result = draft_civic_citations(
        spec, variants=[], resolution_rows=[], reference=None,
        requested=[MOTIVATING_VARIANT], client=client, offline=True,
    )
    assert result.added == 0
    assert result.unreachable == {MOTIVATING_VARIANT: "offline"}
    assert result.asked == 0
    assert read_studies(spec) == []


def test_a_rejected_only_citation_is_withheld_and_counted(tmp_path) -> None:
    """CIViC's editors threw it out; a module must not carry it as though the source stood behind it.

    The payload is the recorded 1939 response **filtered** to its rejected item — real rows, and the
    only construction is which of them are served.
    """
    whole = _body(REJECTING_VARIANT)
    listing = dict(whole["data"]["evidenceItems"])
    rejected = [node for node in listing["nodes"] if node["status"] == "REJECTED"]
    assert rejected, "the fixture must carry a rejected item for this case to exist"
    listing["nodes"] = rejected
    listing["totalCount"] = len(rejected)
    listing["pageInfo"] = {"hasNextPage": False, "endCursor": None}

    spec = _spec(tmp_path / "spec", studies="rsid,pmid\n")
    result = draft_civic_citations(
        spec, variants=[], resolution_rows=[], reference=None,
        requested=[REJECTING_VARIANT],
        client=_client({REJECTING_VARIANT: {"data": {"evidenceItems": listing}}}),
    )
    assert result.added == 0
    assert result.withheld["rejected_by_source"] == len(
        {node["source"]["citationId"] for node in rejected}
    )


def test_a_rejected_item_beside_a_live_one_does_not_decide_the_row(tmp_path) -> None:
    """PMID 28256701 on variant 1939 is cited by an accepted item and a rejected one.

    The live items decide the status; the rejected one neither withholds it nor becomes it.
    """
    spec = _spec(tmp_path / "spec", studies="rsid,pmid\n")
    draft_civic_citations(
        spec, variants=[], resolution_rows=[], reference=None,
        requested=[REJECTING_VARIANT],
        client=_client({REJECTING_VARIANT: _body(REJECTING_VARIANT)}),
    )
    nodes = _nodes(REJECTING_VARIANT)
    contested = {
        node["source"]["citationId"]
        for node in nodes
        if node["status"] == "REJECTED"
    } & {
        node["source"]["citationId"]
        for node in nodes
        if node["status"] != "REJECTED"
    }
    assert contested, "the fixture must carry a paper cited by a rejected AND a live item"
    by_pmid = {row.pmid: row.confidence for row in read_studies(spec)}
    for pmid in contested:
        live = {node["status"].lower() for node in nodes
                if node["source"]["citationId"] == pmid and node["status"] != "REJECTED"}
        assert by_pmid[pmid] == (live.pop() if len(live) == 1 else None)


# ── the two identity routes ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def snapshot(tmp_path) -> Path:
    """The real builder over `assets/civic_slice/`, on the wider basis."""
    from just_dna_enricher.civic_build import build_snapshot

    civic = Path(__file__).resolve().parents[2] / "assets" / "civic_slice"
    return build_snapshot(
        civic / "ClinicalEvidenceSummaries.tsv",
        civic / "VariantSummaries.tsv",
        civic / "MolecularProfileSummaries.tsv",
        tmp_path / "snap",
        release="01-Aug-2026",
        vcf=civic / "civic_accepted_and_submitted.vcf",
    ).out_dir


def test_an_authored_row_reaches_a_variant_id_through_the_snapshot(snapshot, tmp_path) -> None:
    """The ordinary route, through the same resolved-coordinate plan the refutation leg uses."""
    row = next(
        r for r in civic_snapshot_rows(snapshot)
        if r.get("chrom") and r.get("start") is not None and r.get("ref") and r.get("alt")
    )
    variants_csv, resolution_csv = _authored(
        str(row["chrom"]), int(row["start"]), str(row["ref"]), str(row["alt"])
    )
    spec = _spec(tmp_path / "spec", variants=variants_csv, resolution=resolution_csv,
                 studies="rsid,pmid\n")
    variants, resolution = read_module(spec, genome_build="GRCh38")
    subjects, unmapped = plan_subjects(variants, resolution, reference=snapshot)
    assert unmapped == 0
    assert [(s.variant_id, s.route) for s in subjects] == [
        (int(row["variant_id"]), "snapshot_coordinate")
    ]


def test_a_variant_with_no_published_identity_reaches_one_through_the_curated_table(
    snapshot, tmp_path
) -> None:
    """The route that exists because the snapshot cannot carry these rows at all.

    Every identity in `civic_identities` was read out of a CIViC variant's own `name`, for a record
    CIViC publishes no identifier for — so the coordinate the module writes is reachable from the
    curated table and from nothing else.
    """
    placed = {
        (str(r["chrom"]), int(r["start"]), str(r["ref"]), str(r["alt"]))
        for r in civic_snapshot_rows(snapshot)
        if r.get("chrom") and r.get("start") is not None and r.get("ref") and r.get("alt")
    }
    identity = next(
        row for row in CIVIC_NAME_IDENTITIES
        if (row.chrom, row.start, row.ref, row.alt) not in placed
    )
    variants_csv, resolution_csv = _authored(
        identity.chrom, identity.start, identity.ref, identity.alt, rsid=identity.rsid
    )
    spec = _spec(tmp_path / "spec", variants=variants_csv, resolution=resolution_csv,
                 studies="rsid,pmid\n")
    variants, resolution = read_module(spec, genome_build="GRCh38")
    subjects, unmapped = plan_subjects(variants, resolution, reference=snapshot)
    assert unmapped == 0
    assert [(s.variant_id, s.route) for s in subjects] == [
        (identity.variant_id, "curated_name_identity")
    ]

    # And a drafted citation off that route carries the module's own identity cells, so a re-run
    # matches on the same signature.
    subject = subjects[0]
    result = draft_civic_citations(
        spec, variants=variants, resolution_rows=resolution, reference=snapshot,
        client=_client({subject.variant_id: _body(MOTIVATING_VARIANT)}),
    )
    assert result.added
    drafted = [row for row in read_studies(spec) if row.confidence]
    assert {(row.rsid, row.chrom, row.start, row.ref) for row in drafted} == {
        (identity.rsid, identity.chrom, identity.start, identity.ref)
    }


# ── the canary ──────────────────────────────────────────────────────────────────────────────────


def _drafted_module(tmp_path: Path, snapshot: Path) -> tuple[Path, int]:
    """A module whose citations were drafted from a recorded response, through the curated route."""
    placed = {
        (str(r["chrom"]), int(r["start"]), str(r["ref"]), str(r["alt"]))
        for r in civic_snapshot_rows(snapshot)
        if r.get("chrom") and r.get("start") is not None and r.get("ref") and r.get("alt")
    }
    identity = next(
        row for row in CIVIC_NAME_IDENTITIES
        if (row.chrom, row.start, row.ref, row.alt) not in placed
    )
    variants_csv, resolution_csv = _authored(
        identity.chrom, identity.start, identity.ref, identity.alt, rsid=identity.rsid
    )
    spec = _spec(tmp_path / "spec", variants=variants_csv, resolution=resolution_csv,
                 studies="rsid,pmid\n")
    variants, resolution = read_module(spec, genome_build="GRCh38")
    draft_civic_citations(
        spec, variants=variants, resolution_rows=resolution, reference=snapshot,
        client=_client({identity.variant_id: _body(WIDE_VARIANT)}),
    )
    return spec, identity.variant_id


def test_an_unchanged_answer_is_a_check_that_ran_and_found_nothing(snapshot, tmp_path) -> None:
    """The baseline: drafted, re-asked against the same payload, nothing moved."""
    spec, variant_id = _drafted_module(tmp_path, snapshot)
    variants, resolution = read_module(spec, genome_build="GRCh38")
    check = check_evidence_status_currency(
        variants, resolution, read_studies(spec), reference=snapshot,
        client=_client({variant_id: _body(WIDE_VARIANT)}),
    )
    assert check.skip is None and check.subjects == 1
    assert check.findings == []
    assert check.recorded == 1


def test_a_status_that_moved_is_named_with_the_variant_it_moved_on(snapshot, tmp_path) -> None:
    """An item accepted since the draft, reported and not repaired."""
    spec, variant_id = _drafted_module(tmp_path, snapshot)
    text = (spec / "studies.csv").read_text()
    # Re-write one recorded status to the OTHER status the same payload really carries, so the move
    # under test is between two states CIViC actually publishes.
    statuses = {node["status"].lower() for node in _nodes(WIDE_VARIANT)}
    was, now = "submitted", "accepted"
    assert {was, now} <= statuses
    assert f",{now},{CIVIC_STATUS_UNIT}" in text
    (spec / "studies.csv").write_text(
        text.replace(f",{now},{CIVIC_STATUS_UNIT}", f",{was},{CIVIC_STATUS_UNIT}", 1)
    )

    variants, resolution = read_module(spec, genome_build="GRCh38")
    check = check_evidence_status_currency(
        variants, resolution, read_studies(spec), reference=snapshot,
        client=_client({variant_id: _body(WIDE_VARIANT)}),
    )
    moved = [f for f in check.findings if f.code == CIVIC_STATUS_MOVED]
    assert len(moved) == 1
    assert moved[0].recorded == was and moved[0].current == now
    assert str(variant_id) in moved[0].restate()
    assert "not changed" in moved[0].restate(), "the check reports; it never repairs"
    # And the row really was left alone.
    assert any(row.confidence == was for row in read_studies(spec))


def test_a_citation_added_since_the_draft_is_its_own_finding(snapshot, tmp_path) -> None:
    """A different sentence with a different remedy, so a different code."""
    spec, variant_id = _drafted_module(tmp_path, snapshot)
    lines = (spec / "studies.csv").read_text().splitlines()
    # Drop one drafted row, which is what "CIViC has a citation this module does not" looks like.
    (spec / "studies.csv").write_text("\n".join(lines[:-1]) + "\n")

    variants, resolution = read_module(spec, genome_build="GRCh38")
    check = check_evidence_status_currency(
        variants, resolution, read_studies(spec), reference=snapshot,
        client=_client({variant_id: _body(WIDE_VARIANT)}),
    )
    added = [f for f in check.findings if f.code == CIVIC_CITATION_ADDED]
    assert len(added) == 1
    assert "civic citations" in added[0].restate()


def test_offline_skips_the_canary_rather_than_reporting_a_clean_run(snapshot, tmp_path) -> None:
    """`skipped`/`offline`, never `ran, findings=0`."""
    spec, _variant_id = _drafted_module(tmp_path, snapshot)
    variants, resolution = read_module(spec, genome_build="GRCh38")
    check = check_evidence_status_currency(
        variants, resolution, read_studies(spec), reference=snapshot, offline=True
    )
    assert check.skip == "offline" and check.subjects == 0 and check.findings == []
    assert "offline" in check.detail() and str(check.recorded) in check.detail()


def test_a_module_with_no_api_drafted_citation_is_not_checked_against_itself(tmp_path) -> None:
    """The tautology guard: a study row this lane did not write is not a subject.

    A citation drafted from the *snapshot* carries no `confidence_unit`, so re-asking about it would
    be the check answering a question nobody put — and a module hand-authored from CIViC's website is
    in the same position. `nothing_to_check` says so rather than reporting a confident zero.
    """
    spec = _spec(tmp_path / "spec", studies="rsid,pmid,conclusion\nrs1800562,16199547,CIViC says so\n")
    assert recorded_civic_citations(read_studies(spec)) == {}
    check = check_evidence_status_currency([], [], read_studies(spec), reference=None)
    assert check.skip == "nothing_to_check" and check.recorded == 0


def test_a_row_that_cannot_be_mapped_back_is_named_rather_than_counted_as_agreement(
    tmp_path,
) -> None:
    """A module-level citation grounds the module and names no variant, so nothing can re-ask it.

    That is a real limit of the `--variant-id` route and it is published as one: `no_reference` plus
    the count, never a silent pass.
    """
    spec = _spec(tmp_path / "spec", studies="rsid,pmid\n")
    draft_civic_citations(
        spec, variants=[], resolution_rows=[], reference=None,
        requested=[MOTIVATING_VARIANT], client=_client({MOTIVATING_VARIANT: _body(MOTIVATING_VARIANT)}),
    )
    check = check_evidence_status_currency([], [], read_studies(spec), reference=None)
    assert check.skip == "no_reference"
    assert check.not_re_askable == check.recorded > 0
    assert "could be mapped back" in check.detail()
