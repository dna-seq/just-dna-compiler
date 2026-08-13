"""rs-number recovery from an old coordinate, and the wrong-build diagnosis (RM48, online half).

Every payload replayed here is a **real recorded response** from `grch37.rest.ensembl.org`, taken at
7:140453136 — BRAF V600E's hg19 position — because the quirks being handled are all visible in that
one region and a fabricated fixture would have omitted every one of them:

* seven features overlap a single base, and only one of them *starts* there as a substitution;
* one is an HGMD-PUBLIC record (`CM112509`) with no rs-number at all;
* four dbSNP records do start at the position, differing only in how far right they extend, which is
  what makes the position-only query genuinely ambiguous rather than merely under-specified.

The reference bases are real too: `7:140453135..140453137` is `CAC` on GRCh37 and `GTT` on GRCh38,
which is what lets one request discriminate the builds outright.

No credential is involved anywhere in this module — the GRCh37 service is unauthenticated — so the
`.env`-neutralizing fixture the keyed clients need has no counterpart here.
"""

import httpx
import pytest
from just_dna_enricher.grch37 import (
    GRCH37_BUILD,
    VALID_RECOVERY_OUTCOME,
    BuildDiagnosis,
    Grch37Client,
    diagnose_wrong_build,
    recover_rsid,
    summarize_build_diagnoses,
)
from just_dna_enricher.net import PacingGate
from just_dna_enricher.sequences import RefMismatch

#: The real `/overlap/region/human/7:140453136-140453136?feature=variation` payload, trimmed to the
#: fields this module reads and otherwise verbatim (recorded 2026-08-13).
_BRAF_OVERLAP = [
    {
        "id": "rs397516897", "start": 140453134, "end": 140453136,
        "alleles": ["TCA", "-"], "assembly_name": "GRCh37", "source": "dbSNP",
    },
    {
        "id": "rs121913377", "start": 140453135, "end": 140453136,
        "alleles": ["CA", "AT", "GT", "TT"], "assembly_name": "GRCh37", "source": "dbSNP",
    },
    {
        "id": "CM112509", "start": 140453136, "end": 140453136,
        "alleles": ["HGMD_MUTATION"], "assembly_name": "GRCh37", "source": "HGMD-PUBLIC",
    },
    {
        "id": "rs113488022", "start": 140453136, "end": 140453136,
        "alleles": ["A", "C", "G", "T"], "assembly_name": "GRCh37", "source": "dbSNP",
    },
    {
        "id": "rs121913227", "start": 140453136, "end": 140453137,
        "alleles": ["AC", "CG", "CT", "TG", "TT"], "assembly_name": "GRCh37", "source": "dbSNP",
    },
    {
        "id": "rs2128998293", "start": 140453136, "end": 140453138,
        "alleles": ["ACT", "CTC"], "assembly_name": "GRCh37", "source": "dbSNP",
    },
    {
        "id": "rs2128998296", "start": 140453136, "end": 140453139,
        "alleles": ["ACTG", "TTTA"], "assembly_name": "GRCh37", "source": "dbSNP",
    },
]

#: GRCh37 6:26093141 is `G` (HFE C282Y's hg19 reference base); GRCh38 has `A` there, and the real
#: variant is 228 bases away at 6:26092913. Both checked live, 2026-08-13.
_HFE_GRCH37_BASE = "G"


def _client(handler, *, interval: float = 0.0) -> Grch37Client:
    """A client whose transport is a recording and whose gate never really sleeps."""
    client = Grch37Client(gate=PacingGate(interval=interval, sleeper=lambda _s: None))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def _overlap_handler(payload=None, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/overlap/region/human/" in request.url.path
        if status != 200:
            return httpx.Response(status, json={"error": "boom"})
        return httpx.Response(200, json=_BRAF_OVERLAP if payload is None else payload)

    return handler


class TestRecoveryOutcomes:
    """Four outcomes, and the fourth is not padding.

    The decision names three — *recovered*, *none*, *ambiguous* — because that is where a liftover
    library goes wrong: `pyliftover` fuses the last two, answering "no result" both for a position
    that maps nowhere and for one that maps to several. Those three are all **answers**, and S20
    established in this same resolution path that an unreachable source is *unchecked* rather than
    absent. So `unchecked` sits beside them on the other axis, and this class pins all four.
    """

    def test_an_allele_exact_query_recovers_exactly_one(self) -> None:
        recovery = recover_rsid(
            "7", 140453136, ref="A", alts="T", client=_client(_overlap_handler())
        )
        assert recovery.outcome == "recovered"
        assert recovery.rsids == ["rs113488022"]

    def test_a_position_only_query_is_ambiguous_and_names_every_candidate(self) -> None:
        """Four dbSNP records start at that base. Reported, never picked."""
        recovery = recover_rsid("7", 140453136, client=_client(_overlap_handler()))
        assert recovery.outcome == "ambiguous"
        assert recovery.rsids == [
            "rs113488022", "rs121913227", "rs2128998293", "rs2128998296"
        ]

    def test_a_reachable_service_with_nothing_there_answers_none(self) -> None:
        recovery = recover_rsid("7", 140453136, client=_client(_overlap_handler(payload=[])))
        assert recovery.outcome == "none"
        assert recovery.rsids == []
        assert "padded spelling" in recovery.note, "an indel spelling gap is the likeliest cause"

    def test_a_4xx_is_an_answer_not_a_failure(self) -> None:
        """The service 400s on an unknown contig and on a position past the end of one, and both of
        those really are "GRCh37 has nothing for you here" — stated by the service, not guessed."""
        recovery = recover_rsid("7", 140453136, client=_client(_overlap_handler(status=400)))
        assert recovery.outcome == "none"

    def test_a_5xx_is_unchecked_rather_than_absent(self) -> None:
        recovery = recover_rsid("7", 140453136, client=_client(_overlap_handler(status=503)))
        assert recovery.outcome == "unchecked"
        assert "unchecked rather than" in str(recovery)

    def test_a_transport_failure_is_unchecked_too(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host")

        assert recover_rsid("7", 140453136, client=_client(handler)).outcome == "unchecked"

    def test_offline_is_a_first_class_answer_and_makes_no_request(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise AssertionError("offline must not reach the network")

        recovery = recover_rsid("7", 140453136, client=_client(handler), offline=True)
        assert recovery.outcome == "skipped_offline"
        assert recovery.rsids == []

    def test_every_outcome_it_can_produce_is_in_the_vocabulary(self) -> None:
        produced = {
            recover_rsid("7", 140453136, client=_client(_overlap_handler()), offline=offline).outcome
            for offline in (True, False)
        } | {
            recover_rsid("7", 140453136, ref="A", alts="T", client=_client(_overlap_handler())).outcome,
            recover_rsid("7", 140453136, client=_client(_overlap_handler(payload=[]))).outcome,
            recover_rsid("7", 140453136, client=_client(_overlap_handler(status=503))).outcome,
        }
        assert produced <= VALID_RECOVERY_OUTCOME
        assert produced == {"recovered", "ambiguous", "none", "unchecked", "skipped_offline"}


class TestWhatRecoveryRefusesToMatch:
    def test_a_record_that_merely_overlaps_is_not_the_variant_asked_about(self) -> None:
        """`rs397516897` and `rs121913377` span the position without starting at it.

        Anchoring on the authored position is what keeps this honest: handing back an rs-number for a
        variant that merely overlaps would name an event the author never meant.
        """
        recovery = recover_rsid("7", 140453136, client=_client(_overlap_handler()))
        assert "rs397516897" not in recovery.rsids
        assert "rs121913377" not in recovery.rsids

    def test_a_non_dbsnp_record_is_not_an_rs_number(self) -> None:
        """HGMD-PUBLIC's `CM112509` starts at exactly that base and is still not what this recovers."""
        recovery = recover_rsid("7", 140453136, client=_client(_overlap_handler()))
        assert all(r.startswith("rs") for r in recovery.rsids)
        assert "CM112509" not in recovery.rsids

    def test_a_wrong_reference_allele_excludes_a_candidate(self) -> None:
        assert recover_rsid(
            "7", 140453136, ref="C", client=_client(_overlap_handler())
        ).rsids == []

    def test_an_alt_the_record_does_not_carry_excludes_it(self) -> None:
        """`rs113488022` names A>C/G/T, so an authored `A>AT` is a different event."""
        assert recover_rsid(
            "7", 140453136, ref="A", alts="AT", client=_client(_overlap_handler())
        ).rsids == []

    def test_a_feature_from_another_assembly_is_ignored(self) -> None:
        """The host implies the build; the payload is asserted anyway, because one day it may not."""
        foreign = [{**_BRAF_OVERLAP[3], "assembly_name": "GRCh38"}]
        assert recover_rsid(
            "7", 140453136, client=_client(_overlap_handler(payload=foreign))
        ).rsids == []


class TestTheWrongBuildDiagnosis:
    """Only rows the reference check already rejected, and three tiers of evidence.

    The tiers matter because the weakest one really is weak: one base in four agrees by chance, and
    VCF 4.4 §1.6.1.4 requires an ambiguous reference base to be reduced to the first alphabetically,
    so an authored `A` may be a lossily reduced `R`. Saying "this is GRCh37" on that evidence alone
    would be a false accusation dressed as a finding.
    """

    def _mismatch(self, claimed: str = "G", *, shift: int | None = None) -> RefMismatch:
        return RefMismatch(
            variant_key="6:26093141:G", chrom="6", start=26093141, claimed=claimed,
            actual="A", shift=shift,
        )

    def _handler(self, bases: str, overlap=None):
        def handler(request: httpx.Request) -> httpx.Response:
            if "/sequence/region/" in request.url.path:
                return httpx.Response(200, text=bases)
            return httpx.Response(200, json=overlap if overlap is not None else [])

        return handler

    def test_a_single_base_match_is_reported_as_suggestive_only(self) -> None:
        result = diagnose_wrong_build(
            [self._mismatch()], client=_client(self._handler(_HFE_GRCH37_BASE))
        )
        (diagnosis,) = result.diagnoses
        assert diagnosis.reason == "single_base_match"
        (line,) = summarize_build_diagnoses(result.diagnoses)
        assert "one base in four agrees by chance" in line
        assert "§1.6.1.4" in line, "the competing explanation must travel with the hypothesis"

    def test_a_multi_base_match_is_not_explained_by_chance(self) -> None:
        result = diagnose_wrong_build(
            [self._mismatch("GATC")], client=_client(self._handler("GATC"))
        )
        assert result.diagnoses[0].reason == "multi_base_match"

    def test_a_dbsnp_record_at_the_position_is_the_strongest_tier_and_names_the_rsid(self) -> None:
        record = [{
            "id": "rs1800562", "start": 26093141, "end": 26093141,
            "alleles": ["G", "A"], "assembly_name": "GRCh37", "source": "dbSNP",
        }]
        result = diagnose_wrong_build(
            [self._mismatch()], client=_client(self._handler(_HFE_GRCH37_BASE, record))
        )
        (diagnosis,) = result.diagnoses
        assert diagnosis.reason == "dbsnp_corroborated"
        assert diagnosis.rsids == ["rs1800562"]
        assert "rs1800562" in summarize_build_diagnoses(result.diagnoses)[0]

    def test_a_grch37_base_that_disagrees_too_yields_no_hypothesis(self) -> None:
        """GRCh37 does not explain this row either, so nothing is claimed — the mismatch stands alone."""
        result = diagnose_wrong_build([self._mismatch()], client=_client(self._handler("C")))
        assert result.diagnoses == []
        assert result.not_checked is None, "the pass ran; only its answer was negative"

    def test_an_unreachable_service_leaves_the_row_unchecked_rather_than_cleared(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="bad gateway")

        result = diagnose_wrong_build([self._mismatch()], client=_client(handler))
        assert [d.reason for d in result.diagnoses] == ["unchecked"]
        assert "unchecked rather than cleared" in summarize_build_diagnoses(result.diagnoses)[0]

    def test_a_4xx_from_the_sequence_endpoint_is_an_answer_not_a_failure(self) -> None:
        """And the wrong-build case itself reaches it, which is why this is not a corner.

        `20:63500000` is inside GRCh38's chromosome 20 (64,444,167) and past the end of GRCh37's
        (63,025,520), so the service 400s: it has no such place. That is an answer — GRCh37 does not
        explain the row — and rendering it as "could not be asked" would tell an author to re-run for
        a verdict already given, which is the S20 inversion in the same resolution path.
        """
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/sequence/region/" in request.url.path
            return httpx.Response(400, json={"error": "Cannot request a slice whose start …"})

        mismatch = RefMismatch("k", "20", 63_500_000, "G", "A")
        result = diagnose_wrong_build([mismatch], client=_client(handler))
        assert result.diagnoses == []
        assert result.not_checked is None, "the pass ran and reached a verdict"

    def test_an_empty_answer_reads_as_bases_and_never_as_a_missing_read(self) -> None:
        """The distinction lives on the client, so it is pinned there too."""
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "no such region"})

        assert _client(handler).reference_bases("20", 63_500_000, 63_500_000) == ""

        def failing(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="unavailable")

        assert _client(failing).reference_bases("20", 63_500_000, 63_500_000) is None

    def test_the_strong_tiers_supersede_a_neighbour_shift_reading(self) -> None:
        """The real HFE pair is why this exists.

        Authored from the GRCh37 literature into a GRCh38 module, `6:26093141` and `6:26091179` are
        both read by the ±1 neighbour check as "shifted 1 base to the right" — confidently, and
        wrongly: the true variants are 228 and 411 bases away. Two explanations printed side by side
        with nothing to order them is the shape this codebase keeps fixing.
        """
        record = [{
            "id": "rs1800562", "start": 26093141, "end": 26093141,
            "alleles": ["G", "A"], "assembly_name": "GRCh37", "source": "dbSNP",
        }]
        result = diagnose_wrong_build(
            [self._mismatch(shift=1)], client=_client(self._handler(_HFE_GRCH37_BASE, record))
        )
        (line,) = summarize_build_diagnoses(result.diagnoses)
        assert "supersedes that" in line
        assert "one-in-four coincidence" in line

    def test_a_single_base_match_does_NOT_supersede_a_shift(self) -> None:
        """Both readings rest on one agreeing base, so ordering them would invent a verdict."""
        result = diagnose_wrong_build(
            [self._mismatch(shift=1)], client=_client(self._handler(_HFE_GRCH37_BASE))
        )
        assert "supersedes" not in summarize_build_diagnoses(result.diagnoses)[0]


class TestWhyItDidNotRun:
    """An empty list otherwise says both "asked, nothing points elsewhere" and "never asked"."""

    def test_offline_says_so_and_makes_no_request(self) -> None:
        result = diagnose_wrong_build(
            [RefMismatch("k", "6", 26093141, "G", "A")], offline=True
        )
        assert result.not_checked == "skipped_offline"
        assert result.diagnoses == []

    def test_nothing_to_diagnose_is_its_own_reason(self) -> None:
        result = diagnose_wrong_build([])
        assert result.not_checked == "no_ref_mismatches"

    def test_a_bounded_pass_says_it_was_a_sample(self) -> None:
        """A panel authored wholesale on hg19 mismatches on every row and answers the same each time.

        Two paced requests per row is fine for a handful and is not fine unbounded, so the pass is
        capped — and it publishes the denominator rather than letting the count imply a census (RM44).
        """
        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            return httpx.Response(200, text="C") if "/sequence/" in request.url.path else (
                httpx.Response(200, json=[])
            )

        mismatches = [RefMismatch(f"k{n}", "6", 26093141 + n, "G", "A") for n in range(20)]
        result = diagnose_wrong_build(mismatches, client=_client(handler), limit=5)
        assert (result.examined, result.total) == (5, 20)
        assert result.sampled
        assert len(requested) == 5, "it must stop asking, not merely stop reporting"

    def test_an_unbounded_pass_reports_no_sample(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="C") if "/sequence/" in request.url.path else (
                httpx.Response(200, json=[])
            )

        result = diagnose_wrong_build(
            [RefMismatch("k", "6", 26093141, "G", "A")], client=_client(handler)
        )
        assert (result.examined, result.total) == (1, 1)
        assert not result.sampled

    def test_a_run_that_happened_records_no_reason(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="C") if "/sequence/" in request.url.path else (
                httpx.Response(200, json=[])
            )

        result = diagnose_wrong_build(
            [RefMismatch("k", "6", 26093141, "G", "A")], client=_client(handler)
        )
        assert result.not_checked is None


class TestGrouping:
    def test_a_whole_panel_of_one_cause_is_one_line(self) -> None:
        """Grouped by reason, never by row — the `summarize_ref_mismatches` shape."""
        diagnoses = [
            BuildDiagnosis(f"k{n}", "6", 26093141 + n, "G", "single_base_match")
            for n in range(40)
        ]
        (line,) = summarize_build_diagnoses(diagnoses)
        assert line.startswith("40 row(s)")
        assert "and 37 more" in line

    def test_two_causes_are_two_lines(self) -> None:
        diagnoses = [
            BuildDiagnosis("a", "6", 1, "G", "single_base_match"),
            BuildDiagnosis("b", "6", 2, "GATC", "multi_base_match"),
        ]
        assert len(summarize_build_diagnoses(diagnoses)) == 2


class TestPolitenessAndPacing:
    def test_every_request_goes_through_the_gate(self) -> None:
        """Ensembl publishes 15 requests/second and enforces it by blocking the caller's IP.

        Proven on an injectable clock rather than by really waiting: the gate hands out slots one
        interval apart, so N requests reserve N slots.
        """
        slept: list[float] = []
        client = Grch37Client(
            gate=PacingGate(interval=2.0, clock=lambda: 0.0, sleeper=slept.append)
        )
        client._client = httpx.Client(transport=httpx.MockTransport(_overlap_handler()))
        for _ in range(3):
            client.variants_at("7", 140453136)
        # The first caller takes the slot it is standing on and waits for nothing; the next two are
        # spaced one interval apart. A gate that recorded a zero-length sleep first would be measuring
        # its own bookkeeping rather than the pace.
        assert slept == [2.0, 4.0]

    def test_a_client_builds_its_own_gate_at_the_published_interval(self) -> None:
        """Nobody should have to remember to pass one; a gate omitted is a budget not enforced."""
        client = Grch37Client()
        assert client.gate is not None
        assert client.gate.interval == client.settings.interval


@pytest.mark.integration
def test_the_live_service_recovers_a_real_hg19_coordinate() -> None:
    """7:140453136 is BRAF V600E on hg19, and GRCh37 dbSNP records rs113488022 there.

    The end-to-end proof that no chain file is needed: one unauthenticated request against a permanent
    public service turns an old coordinate into the rs-number an author should write instead. Opt-in.
    """
    import os

    if not os.getenv("JUST_DNA_NETWORK_TESTS"):
        pytest.skip("reads the live GRCh37 service — set JUST_DNA_NETWORK_TESTS=1 to run")

    recovery = recover_rsid("7", 140453136, ref="A", alts="T")
    assert recovery.outcome == "recovered"
    assert recovery.rsids == ["rs113488022"]

    client = Grch37Client()
    try:
        # The same coordinates read `CAC` on GRCh37 and `GTT` on GRCh38 — one request discriminates
        # the builds outright, which is what the diagnosis rests on.
        assert client.reference_bases("7", 140453135, 140453137) == "CAC"
        assert client.reference_bases("6", 26093141, 26093141) == _HFE_GRCH37_BASE
    finally:
        client.close()
    assert GRCH37_BUILD == "GRCh37"
