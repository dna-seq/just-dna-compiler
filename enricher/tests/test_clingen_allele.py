"""The ClinGen Allele Registry leg (RM153) — three outcomes, and which build a coordinate came from.

No network: the parser is exercised against payloads shaped like the registry's real ones, and the
client against a stub transport. Live lookups are opt-in like every other network test.
"""

import httpx
import pytest

from just_dna_enricher.clingen_allele import (
    VALID_CAID_OUTCOME,
    AlleleIdentity,
    ClingenAlleleClient,
    _parse,
    anchor_indel,
)

#: Shaped like the real payload for CA341482, including the three sibling builds and the build-less
#: transcript-relative entry that sits beside them.
_PAYLOAD = {
    "genomicAlleles": [
        {
            "referenceGenome": "GRCh38",
            "chromosome": "2",
            "coordinates": [{"allele": "T", "end": 29209798, "referenceAllele": "C", "start": 29209797}],
        },
        {
            "referenceGenome": "GRCh37",
            "chromosome": "2",
            "coordinates": [{"allele": "T", "end": 29432664, "referenceAllele": "C", "start": 29432663}],
        },
        {
            "referenceGenome": "NCBI36",
            "chromosome": "2",
            "coordinates": [{"allele": "T", "end": 29286168, "referenceAllele": "C", "start": 29286167}],
        },
    ],
    "externalRecords": {"dbSNP": [{"rs": 113994087}]},
}


def test_the_coordinate_is_taken_from_grch38_and_never_from_whichever_came_first():
    """The payload lists three builds side by side; reading index 0 would place a row on hg18.

    `@assembly-first-wins` — a source publishing both assemblies lists the wrong one first often
    enough that filtering on the assembly field is the rule rather than a precaution.
    """
    got = _parse("CA341482", _PAYLOAD)
    assert got.coordinate == ("2", 29209798, "C", "T")
    assert got.coordinate[1] != 29432664, "that is the GRCh37 position"
    assert got.coordinate[1] != 29286168, "that is the NCBI36 position"


def test_the_registrys_interbase_end_is_this_formats_one_based_start():
    """The registry is interbase: `start` is 0-based, `end` is the 1-based last affected base.

    For a substitution that `end` is the VCF POS this format's `start` column means
    (`@start-1based`), which is why `end` is read and `start` deliberately is not. Cross-checked
    against the independent GRCh38 HGVS for the same allele, `NC_000002.12:g.29209798C>T`.
    """
    assert _parse("CA341482", _PAYLOAD).coordinate[1] == 29209798
    reordered = dict(_PAYLOAD, genomicAlleles=list(reversed(_PAYLOAD["genomicAlleles"])))
    assert _parse("CA341482", reordered).coordinate[1] == 29209798, "order must not matter"


def test_an_rsid_is_returned_beside_the_coordinate_and_is_the_preferred_route():
    got = _parse("CA341482", _PAYLOAD)
    assert got.rsid == "rs113994087"
    assert got.outcome == "resolved" and got.placeable


def test_a_payload_with_no_placeable_identity_is_an_absence_not_a_failure():
    """An indel the registry cannot express as a substitution, and no dbSNP record."""
    got = _parse("CA645524645", {"genomicAlleles": [], "externalRecords": {}})
    assert got.outcome == "no_identity"
    assert not got.placeable and got.rsid is None and got.coordinate is None


def _indel_payload(ref: str, alt: str, start: int = 10142013) -> dict:
    return {
        "genomicAlleles": [
            {
                "referenceGenome": "GRCh38",
                "chromosome": "3",
                "coordinates": [
                    {"allele": alt, "end": start, "referenceAllele": ref, "start": start}
                ],
            }
        ],
        "externalRecords": {},
    }


def test_a_one_sided_indel_is_neither_resolved_nor_absent_until_it_is_anchored():
    """Three states would not be enough here: the registry HAS the allele, we cannot yet write it.

    `no_identity` would be a lie about the registry and `resolved` a lie about the row, so the outcome
    waits in `needs_anchor` and `placeable` stays false — a half-stated allele is not a position
    (`@identity-whole-or-none`).
    """
    got = _parse("CA1", _indel_payload("", "G"))
    assert got.outcome == "needs_anchor"
    assert not got.placeable and got.coordinate is None
    assert got.unanchored == ("3", 10142013, "", "G")

    deletion = _parse("CA2", _indel_payload("A", ""))
    assert deletion.outcome == "needs_anchor"
    assert deletion.unanchored == ("3", 10142013, "A", "")


def test_a_payload_stating_neither_allele_is_a_real_absence():
    assert _parse("CA3", _indel_payload("", "")).outcome == "no_identity"


def test_anchoring_produces_the_left_aligned_vcf_representation():
    """The shape VCF requires and Picard/GATK produce: both sides carry the preceding base.

    Checked against a real registry record — CA645524645 is `NC_000003.12:g.10142013dup`, an inserted
    `G` at a position whose reference base is `G`, so the row is `G>GG`. A duplication and an
    insertion of the same base are the same VCF row, which is why that record is the useful control.
    """
    read = lambda chrom, pos: {10142013: "G", 10142177: "C"}.get(pos)
    assert anchor_indel(("3", 10142013, "", "G"), read) == ("3", 10142013, "G", "GG")
    assert anchor_indel(("3", 10142177, "A", ""), read) == ("3", 10142177, "CA", "C")


def test_a_lowercase_reference_base_is_normalized():
    """Soft-masked reference sequence is lowercase, and `ref` is compared case-sensitively."""
    assert anchor_indel(("3", 1, "", "G"), lambda c, p: "a") == ("3", 1, "A", "AG")


def test_an_unreadable_anchor_is_withheld_rather_than_guessed():
    """A guessed anchor is a wrong `ref` on a right position — the mismatch class RefMismatch reports."""
    assert anchor_indel(("3", 10142013, "", "G"), lambda c, p: None) is None
    assert anchor_indel(("3", 10142013, "", "G"), lambda c, p: "") is None


def test_an_event_at_the_start_of_a_contig_has_no_anchor_and_says_so():
    assert anchor_indel(("3", 0, "A", ""), lambda c, p: "G") is None


# ── the client's three outcomes ───────────────────────────────────────────────────────────────────


def _client(handler) -> ClingenAlleleClient:
    return ClingenAlleleClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_offline_is_nobody_asked_and_never_an_absence():
    """`--offline` is the switch, and its answer is a first-class state rather than a pass."""
    got = ClingenAlleleClient(offline=True).resolve("CA341482")
    assert got.outcome == "skipped_offline"
    assert not got.placeable, "and it must never read as placeable"


def test_a_transport_failure_is_unchecked_rather_than_an_absence():
    """The S20 defect: collapsing a failed request into an established negative.

    A variant the registry could not be asked about is unplaced, not unplaceable, and a later run may
    place it. Reporting it as `no_identity` would make a network blip permanent.
    """
    def boom(request):
        raise httpx.ConnectError("no route to host")

    assert _client(boom).resolve("CA341482").outcome == "unchecked"


def test_a_404_is_the_registry_answering():
    """A 4xx is an answer — the registry has no such allele — where a 5xx is a failure to ask."""
    assert _client(lambda r: httpx.Response(404)).resolve("CA0").outcome == "no_identity"
    assert _client(lambda r: httpx.Response(503)).resolve("CA0").outcome == "unchecked"


def test_every_outcome_the_client_can_produce_is_in_the_declared_set():
    """A vocabulary is only as good as the walk that checks it (`@registry-completeness`)."""
    import json

    produced = {
        ClingenAlleleClient(offline=True).resolve("CA1").outcome,
        _client(lambda r: httpx.Response(404)).outcome if False else _client(lambda r: httpx.Response(404)).resolve("CA1").outcome,
        _client(lambda r: httpx.Response(503)).resolve("CA1").outcome,
        _client(lambda r: httpx.Response(200, text=json.dumps(_PAYLOAD))).resolve("CA1").outcome,
    }
    assert produced <= VALID_CAID_OUTCOME
    assert produced == {"skipped_offline", "no_identity", "unchecked", "resolved"}


def test_one_caid_is_looked_up_once_however_many_rows_name_it():
    """The cache is per client, because a CAID recurs across evidence rows on the same variant."""
    import json

    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text=json.dumps(_PAYLOAD))

    client = _client(handler)
    for _ in range(4):
        assert client.resolve("CA341482").rsid == "rs113994087"
    assert len(calls) == 1


@pytest.mark.parametrize("caid", ["", "   "])
def test_a_blank_caid_is_an_absence_and_never_a_request(caid):
    def boom(request):  # pragma: no cover - must not be reached
        raise AssertionError("a blank CAID must not be looked up")

    assert _client(boom).resolve(caid).outcome == "no_identity"
