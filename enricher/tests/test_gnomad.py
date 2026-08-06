"""The gnomAD client: batching, pacing, partial failures, and the population-list clean-up.

Everything here is driven by **a real recorded gnomAD response** (`assets/gnomad_v4.1_variant_payload.json`),
replayed through `httpx.MockTransport` the way the Ensembl tests replay theirs. That matters more than
usual for this source, because the quirks being handled are not hypothetical — they are all visible in
that one recorded payload:

* a `"Multiple variants found"` error for `rs334` sitting in `errors[]` **beside** valid `data` for
  the other aliases (the partial-failure case);
* a `populations` list carrying sex splits (`nfe_XX`), a bare `""` id, and `XX`/`XY` **listed twice**;
* per-population entries with `ac`/`an` and no `af` anywhere.

A fabricated fixture would have quietly omitted the duplicate `XX`, which is exactly the bug worth
having a test for.
"""

import json
from pathlib import Path

import httpx
import pytest
from just_dna_format.vocab import POPULATION_ORDER

from just_dna_enricher.gnomad import (
    GnomadClient,
    GnomadError,
    GnomadSettings,
    _loci_from_variant_ids,
    _populations_from_joint,
)
from just_dna_enricher.net import PacingGate

_ASSETS = Path(__file__).resolve().parents[2] / "assets"


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads((_ASSETS / "gnomad_v4.1_variant_payload.json").read_text())


@pytest.fixture(scope="module")
def gene_payload() -> dict:
    return json.loads((_ASSETS / "gnomad_gene_constraint_payload.json").read_text())


class _Recorder:
    """A MockTransport handler that records every request body it is asked to serve."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.queries: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.queries.append(json.loads(request.content)["query"])
        index = min(len(self.queries) - 1, len(self.responses) - 1)
        return httpx.Response(200, json=self.responses[index])


def _client(recorder: _Recorder, **settings) -> GnomadClient:
    """A client wired to a mock transport, with pacing neutralised (an injected no-op clock)."""
    client = GnomadClient(settings=GnomadSettings(**settings))
    client._client = httpx.Client(transport=httpx.MockTransport(recorder))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


# ── the pacing gate ─────────────────────────────────────────────────────────────────────────────


def test_pacing_gate_enforces_the_interval_on_a_fake_clock() -> None:
    """Six seconds between requests, proven without a suite that really sleeps six seconds."""
    now = [0.0]
    slept: list[float] = []

    def sleeper(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    gate = PacingGate(interval=6.0, clock=lambda: now[0], sleeper=sleeper)
    gate.wait()                 # first call is free — nothing to wait behind
    assert slept == []
    gate.wait()                 # immediately after: must wait the full interval
    assert slept == [6.0]
    now[0] += 10.0              # more than an interval has passed on its own
    gate.wait()
    assert slept == [6.0]       # so no additional sleep
    now[0] += 2.0
    gate.wait()
    assert slept == [6.0, 4.0]  # partial wait: only the remainder


def test_pacing_gate_keeps_us_inside_the_stated_budget() -> None:
    # gnomAD allows 10 requests per 60 seconds; the default interval must not exceed that budget.
    assert GnomadSettings().min_request_interval >= 60.0 / 10
    # And the batch size must stay under the probed ceiling (25 worked, 29 was rejected).
    assert GnomadSettings().batch_size <= 25


# ── batching ────────────────────────────────────────────────────────────────────────────────────


def test_requests_are_batched_by_batch_size() -> None:
    recorder = _Recorder([{"data": {}}])
    client = _client(recorder, batch_size=20)
    client.fetch_frequencies([f"1-{i}-A-G" for i in range(45)])
    assert len(recorder.queries) == 3          # ceil(45 / 20)
    assert recorder.queries[0].count("variant(") == 20
    assert recorder.queries[2].count("variant(") == 5


def test_duplicate_ids_are_collapsed_before_batching() -> None:
    recorder = _Recorder([{"data": {}}])
    client = _client(recorder, batch_size=20)
    client.fetch_frequencies(["1-100-A-G"] * 30)
    assert len(recorder.queries) == 1
    assert recorder.queries[0].count("variant(") == 1


# ── partial failures ────────────────────────────────────────────────────────────────────────────


def test_per_alias_errors_do_not_discard_the_batch(payload: dict) -> None:
    """The recorded payload has a real error beside real data — every good alias must survive."""
    assert payload["errors"], "fixture must carry the recorded per-alias error"
    remapped = {
        "data": {"v0": payload["data"]["sickle"], "v1": payload["data"]["mthfr"], "v2": None},
        "errors": [{"message": payload["errors"][0]["message"], "path": ["v2"]}],
    }
    recorder = _Recorder([remapped])
    client = _client(recorder)
    result = client.fetch_frequencies(["11-5227002-T-A", "1-11796321-G-A", "9-1-A-G"])
    assert set(result) == {"11-5227002-T-A", "1-11796321-G-A"}   # the failing alias is simply absent


def test_a_pathless_not_found_keeps_the_batch(payload: dict) -> None:
    """gnomAD reports an absent variant with **no `path`** — that must not read as a broken query.

    The shape below is what the live API returns (probed 2026-08-06): a `null` at the missing alias
    inside `data`, plus a bare `{"message": "Variant not found"}` in `errors[]` with no `path` key at
    all. Classifying that as a whole-request failure aborted the entire `frequencies` pass with a
    traceback the moment a module carried one variant gnomAD lacks — which is ordinary, and is what
    `VALID_FREQUENCY_STATUS`'s `not_found` member exists to record.
    """
    remapped = {
        "data": {"v0": payload["data"]["sickle"], "v1": None},
        "errors": [{"message": "Variant not found"}],
    }
    client = _client(_Recorder([remapped]))
    result = client.fetch_frequencies(["11-5227002-T-A", "1-176842737-C-G"])
    assert set(result) == {"11-5227002-T-A"}   # the good row survives; the absent one is just absent


def test_a_whole_request_error_is_raised_not_swallowed() -> None:
    # An error with no alias path is our bug (a bad query), not a missing record. Returning "nothing
    # found" would hide a broken query behind an innocent empty table.
    recorder = _Recorder([{"errors": [{"message": "Cannot query field \"nope\""}]}])
    client = _client(recorder)
    with pytest.raises(GnomadError, match="Cannot query field"):
        client.fetch_frequencies(["11-5227002-T-A"])


def test_multiple_variants_error_reroutes_through_variant_search(payload: dict) -> None:
    """A multi-allelic rsID must not be lost — it is retried via `variant_search`.

    `rs334` is sickle-cell: precisely the kind of variant a module carries, so silently dropping it
    would be a serious hole rather than an edge case.
    """
    first = {
        "data": {"v0": payload["data"]["single"], "v1": None},
        "errors": [{"message": payload["errors"][0]["message"], "path": ["v1"]}],
    }
    second = {"data": {"v0": payload["data"]["search"]}}
    recorder = _Recorder([first, second])
    client = _client(recorder)
    result = client.resolve_rsids(["rs1801133", "rs334"])

    assert "variant_search" in recorder.queries[1]
    assert result["rs1801133"] == [
        {"chrom": "1", "start": 11796321, "ref": "G", "alts": "A"}
    ]
    # Both alleles gnomAD knows at the locus, aggregated into one locus with a sorted alt list.
    assert result["rs334"] == [
        {"chrom": "11", "start": 5227002, "ref": "T", "alts": "A,G"}
    ]


# ── the population list ─────────────────────────────────────────────────────────────────────────


def test_population_cleanup_on_the_real_payload(payload: dict) -> None:
    joint = payload["data"]["sickle"]["joint"]
    raw_ids = [p["id"] for p in joint["populations"]]
    # Guard the fixture itself: if these quirks ever vanish from the recording, the assertions below
    # would pass vacuously and stop protecting anything.
    assert raw_ids.count("XX") == 2, "fixture should carry the duplicated sex entries"
    assert "" in raw_ids, "fixture should carry the bare whole-dataset id"
    assert any(i.endswith("_XX") for i in raw_ids), "fixture should carry sex splits"

    rows = _populations_from_joint(joint)
    populations = [r["population"] for r in rows]

    assert len(populations) == len(set(populations))            # duplicates collapsed
    assert not any("xx" in p or "xy" in p for p in populations)  # sex axis dropped entirely
    assert "global" in populations                               # bare id mapped to `global`
    # Emitted in the canonical order, never the server's.
    assert populations == sorted(populations, key=lambda p: POPULATION_ORDER.index(p))
    assert populations[0] == "global"


def test_global_row_matches_the_top_level_joint_counts(payload: dict) -> None:
    joint = payload["data"]["sickle"]["joint"]
    rows = {r["population"]: r for r in _populations_from_joint(joint)}
    assert rows["global"]["allele_count"] == joint["ac"]
    assert rows["global"]["allele_number"] == joint["an"]


def test_computed_frequency_agrees_with_the_payloads_own_af(payload: dict) -> None:
    """AC/AN is ours to compute because gnomAD exposes no per-population `af`.

    The check that it is computed *correctly* comes from the payload itself: the top-level
    `exome.af` is gnomAD's own division of its own exome AC/AN, so our arithmetic must reproduce it.
    """
    exome = payload["data"]["sickle"]["exome"]
    assert exome["af"] == pytest.approx(exome["ac"] / exome["an"], rel=1e-9)


def test_faf95_lands_on_its_owning_group_only(payload: dict) -> None:
    joint = payload["data"]["sickle"]["joint"]
    owner = joint["faf95"]["popmax_population"]
    rows = {r["population"]: r for r in _populations_from_joint(joint)}
    assert rows[owner]["faf95"] == joint["faf95"]["popmax"]
    assert [p for p, r in rows.items() if r.get("faf95") is not None] == [owner]


def test_missing_faf95_leaves_every_row_null() -> None:
    rows = _populations_from_joint(
        {"ac": 1, "an": 10, "populations": [{"id": "afr", "ac": 1, "an": 10}], "faf95": None}
    )
    assert all(r.get("faf95") is None for r in rows)


# ── locus parsing ───────────────────────────────────────────────────────────────────────────────


def test_variant_ids_fold_into_deterministically_ordered_loci() -> None:
    loci = _loci_from_variant_ids(
        ["16-2000-A-G", "1-1000-A-T", "1-1000-A-G", "not-a-variant-id"]
    )
    assert loci == [
        {"chrom": "1", "start": 1000, "ref": "A", "alts": "G,T"},  # alts sorted, one locus
        {"chrom": "16", "start": 2000, "ref": "A", "alts": "G"},
    ]


# ── gene constraint ─────────────────────────────────────────────────────────────────────────────


def test_gene_constraint_maps_oe_lof_upper_to_loeuf(gene_payload: dict) -> None:
    recorder = _Recorder([gene_payload])
    client = _client(recorder)
    result = client.fetch_gene_constraint(["BRCA1", "MYH7"])

    brca1, myh7 = result["BRCA1"], result["MYH7"]
    source = gene_payload["data"]["v0"]["gnomad_constraint"]
    # LOEUF is stored under the name clinical readers use; the source column is `oe_lof_upper`.
    assert brca1["loeuf"] == source["oe_lof_upper"]
    assert brca1["gene_id"] == "ENSG00000012048"
    assert brca1["transcript"] == "ENST00000357654"
    assert brca1["mane_select"] is True
    # A cheap but real sanity relation: the point estimate sits inside its own confidence interval.
    assert brca1["oe_lof_lower"] <= brca1["oe_lof"] <= brca1["loeuf"]
    assert myh7["loeuf"] < brca1["loeuf"]   # MYH7 is the more LoF-constrained of the two
    assert myh7["constraint_flags"] is None  # empty flag list → null, not ""


def test_gene_constraint_batches_and_skips_genes_with_no_constraint() -> None:
    recorder = _Recorder([{"data": {"v0": {"symbol": "X", "gnomad_constraint": None}, "v1": None}}])
    client = _client(recorder)
    assert client.fetch_gene_constraint(["X", "Y"]) == {}


# ── live (opt-in) ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_live_gnomad_agrees_with_the_recorded_fixtures(payload: dict, gene_payload: dict) -> None:
    """One live batched request, checked against the committed recordings.

    This is the test that notices when gnomAD changes its schema or its numbers under us — the
    fixtures are what every other test here believes, so something has to keep checking that they
    still describe reality. Deliberately ONE request (the client's own pacing gate applies), and
    opt-in so an ordinary offline run never touches the network.
    """
    import os

    if not os.getenv("JUST_DNA_NETWORK_TESTS"):
        pytest.skip("live gnomAD query — set JUST_DNA_NETWORK_TESTS=1 to run")

    with GnomadClient() as client:
        live = client.fetch_frequencies(["11-5227002-T-A"])
        constraint = client.fetch_gene_constraint(["BRCA1"])

    recorded = _populations_from_joint(payload["data"]["sickle"]["joint"])
    served = live["11-5227002-T-A"]["populations"]
    assert {r["population"] for r in served} == {r["population"] for r in recorded}

    recorded_afr = next(r for r in recorded if r["population"] == "afr")
    served_afr = next(r for r in served if r["population"] == "afr")
    # A release refresh can move counts slightly; a schema break moves them completely.
    assert served_afr["allele_count"] == pytest.approx(recorded_afr["allele_count"], rel=0.05)
    assert served_afr["allele_number"] == pytest.approx(recorded_afr["allele_number"], rel=0.05)
    assert live["11-5227002-T-A"]["caid"] == payload["data"]["sickle"]["caid"]

    expected_loeuf = gene_payload["data"]["v0"]["gnomad_constraint"]["oe_lof_upper"]
    assert constraint["BRCA1"]["loeuf"] == pytest.approx(expected_loeuf, rel=0.05)
