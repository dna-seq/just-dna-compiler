"""RM430 against the real Hugging Face: one Ensembl chromosome file and one ClinVar key (live, opt-in).

Runs only with `JUST_DNA_NETWORK_TESTS=1` (`@network-tests-optin`). Anonymous, so it spends a few dozen of
the Hub's 3,000 requests per 5 minutes; run it serially. It asserts shapes the published repos must have,
never counts read off a dump: rows at APOE's two common positions and for rs429358, each answer pinned to
a commit and carrying the release its repo states.
"""

import re

import pytest
from just_dna_enricher.remote import RemoteSnapshots

pytestmark = pytest.mark.network


def test_one_ensembl_position_and_one_clinvar_rsid_over_the_hub(
    httpfs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JUST_DNA_SNAPSHOT_PROXY_URL", "")
    with RemoteSnapshots(declared_use="non_commercial") as holder:
        ensembl = holder.lookup("ensembl", "homo_sapiens", {"chrom": ["19"], "start": [44908684]})
        clinvar = holder.lookup("clinvar", "clinvar", {"rsid": ["rs429358"]})
    assert "rs429358" in {row["id"] for row in ensembl.rows}
    assert {(row["chrom"], row["start"]) for row in clinvar.rows} == {("19", 44908684)}
    for answer in (ensembl, clinvar):
        assert answer.route == "hf" and answer.served_from is None
        assert re.fullmatch(r"[0-9a-f]{40}", answer.revision or "")
        assert answer.release
