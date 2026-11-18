"""The lanes RM431 makes remote-eligible, each by its keyed function's keys (0.9, RM431, on RM430's seam).

Each lane's published repo is a `LoopbackHub` serving a real snapshot's bytes; the holder is asked with
the keys the keyed function derives, and its rows go through the keyed function's own SQL. The answer
must equal the local reader's over the same snapshot: same keys, same rows, one SQL body.
"""

from pathlib import Path

import pytest
from just_dna_enricher import opentargets, remote
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS
from just_dna_enricher.remote import REMOTE_LANES, RemoteSnapshots

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
OPENTARGETS_SLICE = _ASSETS / "opentargets_slice"
COMMIT = "c" * 40


@pytest.fixture(autouse=True)
def _no_ambient_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's `.env` may name a proxy; set empty rather than deleted, so it cannot refill it."""
    monkeypatch.setenv(remote.PROXY_URL_VAR, "")
    monkeypatch.setenv(remote.PROXY_TOKEN_VAR, "")


def test_open_targets_is_remote_eligible_and_answers_by_position_not_by_rsid_alone() -> None:
    assert "opentargets" in REMOTE_LANES
    assert not REMOTE_LANES["opentargets"].needs_position


def test_open_targets_answers_remotely_as_the_local_reader_does(httpfs, loopback_hub) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["opentargets"], OPENTARGETS_SLICE, COMMIT)
    # C282Y (rs_ids a one-element list), a position with an allele whose rs_ids is empty, rs35589214's
    # two alleles, and a position the release holds nothing at.
    positions = [("chr6", 26092913), ("6", 26092960), ("8", 78193100), ("6", 1)]
    local = opentargets.lookup_variants(OPENTARGETS_SLICE, positions)
    assert any(row["rs_ids"] == [] for rows in local.values() for row in rows), "an empty list is covered"
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        answer = holder.lookup(
            "opentargets", opentargets.REMOTE_VARIANTS_TABLE, opentargets._variant_keys(positions)
        )
        assert opentargets._variants_from_rows(answer.rows, positions) == local
        ids = sorted({row["variant_id"] for rows in local.values() for row in rows})
        keys = {"variant_id": ids}
        consequences = holder.lookup("opentargets", opentargets.REMOTE_CONSEQUENCES_TABLE, keys)
        members = holder.lookup("opentargets", opentargets.REMOTE_MEMBERS_TABLE, keys)
    remote_answer = opentargets._consequences_from_rows(consequences.rows, members.rows, ids)
    local_answer = opentargets.lookup_consequences(OPENTARGETS_SLICE, ids)
    assert remote_answer == local_answer
    rows = [row for found in local_answer.values() for row in found]
    assert {type(row["canonical"]) for row in rows if row["table"] == "consequences"} == {bool}
    assert {type(row["posterior_probability"]) for row in rows if row["table"] == "credible_set_members"} == {
        float
    }
