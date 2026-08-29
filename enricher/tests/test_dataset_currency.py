"""RM85 — a module is told when the source it was drafted from has published since.

The three states this check exists to keep apart are asserted as three states, not as two plus a
default: **current**, **behind** (with the gap named), and **unchecked** because nobody could ask. The
third is the whole item — a check that reported a clean bill for a source it never reached would be S4
wearing the badge of the mechanism S4 built.

Every case here drives the real comparison against an injected probe. The one live leg — reading
NCBI's own VCF header over the wire — is opt-in (`JUST_DNA_NETWORK_TESTS=1`) like every other network
test in this tier.
"""

from __future__ import annotations

import gzip
import os
from collections.abc import Callable

import httpx
import pytest
from just_dna_enricher.clinvar import CLINVAR_DATASET_PREFIX
from just_dna_enricher.currency import (
    HEADER_PROBE_BYTES,
    PROBE_SOURCES,
    ClinVarReleaseClient,
    ReleaseProbeError,
    ReleaseUnavailable,
    check_dataset_currency,
    default_probes,
    summarize_currency,
)
from just_dna_enricher.net import PacingGate
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import VALID_VERIFICATION_SKIPS


def _row(source: str = "clinvar", dataset: str | None = "clinvar_2026-06-27",
         layer: str = "annotation") -> SourceRow:
    return SourceRow(source=source, layer=layer, dataset=dataset)


def _probe(label: str | None) -> Callable[[], str | None]:
    return lambda: label


def _instant_gate() -> PacingGate:
    return PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)


def _refuses() -> str | None:
    raise ReleaseUnavailable("ClinVar release probe failed: connection refused")


class _NeverAsked:
    """A probe registry whose members raise if anything invokes them.

    The off-switch probe, in the shape the house rule demands: a flag whose *disabling* value is only
    read and never exercised is a flag that does nothing. Asserting the record says `offline` would
    pass even if the request had been made and its answer thrown away.
    """

    def __init__(self) -> None:
        self.asked: list[str] = []

    def probe(self) -> str | None:
        raise AssertionError("the probe was invoked on a run that must not touch the network")

    def registry(self) -> dict[str, Callable[[], str | None]]:
        return {"clinvar": self.probe, "clinpgx": self.probe}


# ── the three states ─────────────────────────────────────────────────────────────────────────────


def test_a_module_on_the_release_its_source_still_publishes_reads_as_current() -> None:
    check = check_dataset_currency(
        [_row(dataset="clinvar_2026-06-27")],
        probes={"clinvar": _probe("clinvar_2026-06-27")},
    )
    assert check.not_checked is None
    assert check.subjects == 1
    assert check.behind == []
    assert check.compared[0].behind is False


def test_a_source_that_has_published_since_is_reported_with_the_gap() -> None:
    """The finding names both labels: which release the rows came from, and which is current now."""
    check = check_dataset_currency(
        [_row(dataset="clinvar_2026-06-27")],
        probes={"clinvar": _probe("clinvar_2026-08-25")},
    )
    assert check.subjects == 1
    behind = check.behind
    assert [c.recorded for c in behind] == ["clinvar_2026-06-27"]
    assert [c.current for c in behind] == ["clinvar_2026-08-25"]
    assert behind[0].behind is True
    assert "clinvar_2026-06-27 → clinvar_2026-08-25" in " ".join(summarize_currency(check))


def test_a_source_that_could_not_be_reached_is_unchecked_and_never_current() -> None:
    """`None` is not `False`: an unreachable source has not been shown to stand still.

    The dangerous reading is the one this asserts against — `behind is False` would publish "your
    release is still the current one" about a source nobody managed to ask.
    """
    check = check_dataset_currency([_row()], probes={"clinvar": _refuses})
    assert check.subjects == 0
    assert check.behind == []
    assert check.not_checked == "unreachable"
    leg = check.unchecked[0]
    assert leg.behind is None and leg.unchecked == "unreachable"
    assert leg.behind is not False


def test_the_three_states_are_told_apart_by_the_same_call() -> None:
    """One run, three sources, three different answers — the discrimination, in one assertion.

    Asserted together because each of the three passes trivially on its own: a check that always
    answered `unchecked` would satisfy the third test above, and one that never did would satisfy the
    first two.
    """
    check = check_dataset_currency(
        [
            _row(source="clinvar", dataset="clinvar_2026-06-27"),
            _row(source="clinpgx", dataset="clinpgx_2026-07-05"),
            _row(source="cpic", dataset="cpic_2026-05-01"),
        ],
        probes={
            "clinvar": _probe("clinvar_2026-08-25"),
            "clinpgx": _probe("clinpgx_2026-07-05"),
            "cpic": _refuses,
        },
    )
    assert {c.source: c.behind for c in check.compared} == {"clinvar": True, "clinpgx": False}
    assert {c.source: c.behind for c in check.unchecked} == {"cpic": None}
    assert check.subjects == 2 and len(check.behind) == 1


# ── the denominator, and the zero that must not be reported ──────────────────────────────────────


def test_a_check_that_could_not_run_reports_no_zero() -> None:
    """`@tautology-zero`: with nothing asked, the record is a skip, not `ran(0, 0)`.

    `subjects == 0` beside `not_checked is None` would be the pass claiming it compared nothing and
    found nothing wrong, which is the answered-absence collapse the whole verification block exists
    to prevent.
    """
    check = check_dataset_currency([_row()], probes={"clinvar": _refuses})
    assert check.not_checked is not None
    assert check.not_checked in VALID_VERIFICATION_SKIPS


def test_an_unaskable_source_is_not_counted_into_the_denominator() -> None:
    """Coverage of an unstated fraction is the defect; the shortfall goes in the sentence instead."""
    check = check_dataset_currency(
        [
            _row(source="clinvar", dataset="clinvar_2026-06-27"),
            _row(source="cpic", dataset="cpic_2026-05-01"),
        ],
        probes={"clinvar": _probe("clinvar_2026-06-27"), "cpic": _refuses},
    )
    assert check.subjects == 1, "an unreachable leg was counted as a comparison"
    assert any("unchecked (unreachable)" in line for line in summarize_currency(check))


def test_a_module_recording_no_release_has_nothing_to_check() -> None:
    """Not a skip egress or a flag would clear — the module makes no claim about any release."""
    check = check_dataset_currency([_row(dataset=None), _row(source="cpic", dataset="  ")])
    assert check.not_checked == "nothing_to_check"
    assert check.subjects == 0 and check.unchecked == ()


def test_a_source_this_tier_cannot_ask_is_unsupported_rather_than_current() -> None:
    check = check_dataset_currency([_row(source="gwas_catalog", dataset="gwas_catalog_2026-08-01")])
    assert check.not_checked == "unsupported"
    assert check.unchecked[0].behind is None


def test_a_source_that_answers_without_naming_a_release_is_unchecked() -> None:
    """Read and unreadable are different absences, and neither of them is "still current"."""
    check = check_dataset_currency([_row()], probes={"clinvar": _probe(None)})
    assert check.not_checked == "no_reference"
    assert check.unchecked[0].behind is None


def test_a_digest_label_is_uncomparable_against_a_stated_one_rather_than_behind() -> None:
    """The two `clinvar_dataset_label` forms name one release space and cannot be equated.

    Reporting this as `behind` would send an author to re-draft a module that may well be on the very
    release the probe just named.
    """
    check = check_dataset_currency(
        [_row(dataset=f"{CLINVAR_DATASET_PREFIX}sha256:abc123")],
        probes={"clinvar": _probe("clinvar_2026-08-25")},
    )
    assert check.behind == []
    assert check.unchecked[0].unchecked == "no_reference"


def test_two_digest_labels_do_compare() -> None:
    """Same form, so equality means something — the rule is *same kind*, not *never a digest*."""
    check = check_dataset_currency(
        [_row(dataset=f"{CLINVAR_DATASET_PREFIX}sha256:abc123")],
        probes={"clinvar": _probe(f"{CLINVAR_DATASET_PREFIX}sha256:def456")},
    )
    assert [c.behind for c in check.compared] == [True]


# ── one request per source, and the off switch ───────────────────────────────────────────────────


def test_one_source_at_two_layers_costs_one_probe_and_gets_one_answer() -> None:
    calls: list[int] = []

    def counting() -> str | None:
        calls.append(1)
        return "clinvar_2026-08-25"

    check = check_dataset_currency(
        [_row(layer="annotation"), _row(layer="resolution")], probes={"clinvar": counting}
    )
    assert len(calls) == 1
    assert {c.current for c in check.compared} == {"clinvar_2026-08-25"}
    assert check.subjects == 2


def test_an_offline_run_never_invokes_a_probe_and_reports_unchecked() -> None:
    """`--offline` is where the tri-state bites, and the probe proves it rather than the label."""
    registry = _NeverAsked()
    check = check_dataset_currency(
        [_row(), _row(source="clinpgx", dataset="clinpgx_2026-07-05")],
        probes=registry.registry(),
        offline=True,
    )
    assert check.not_checked == "offline"
    assert check.subjects == 0
    assert [leg.behind for leg in check.unchecked] == [None, None]


def test_the_check_writes_nothing(tmp_path) -> None:
    """It reads and reports; repairing a stale label is a re-draft, which is a different command."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "sources.csv").write_text("source,layer,dataset\nclinvar,annotation,clinvar_2026-06-27\n")
    before = {p.name: p.read_bytes() for p in sorted(spec.iterdir())}
    check = check_dataset_currency([_row()], probes={"clinvar": _probe("clinvar_2026-08-25")})
    assert check.behind, "the case has to report a gap, or the assertion below proves nothing"
    assert {p.name: p.read_bytes() for p in sorted(spec.iterdir())} == before


# ── the registry, and the client's contract ──────────────────────────────────────────────────────


def test_the_shipped_probe_set_is_exactly_what_the_registry_builds() -> None:
    """An equality over a walked set, never a floor: a second list is a registry that goes stale."""
    assert frozenset(default_probes()) == PROBE_SOURCES


def test_an_injected_registry_may_answer_for_a_source_this_tier_ships_no_probe_for() -> None:
    """The injection point widens the check; the shipped set is a default, not a gate."""
    assert "clinpgx" not in PROBE_SOURCES
    check = check_dataset_currency(
        [_row(source="clinpgx", dataset="clinpgx_2026-01-01")],
        probes={"clinpgx": _probe("clinpgx_2026-07-05")},
    )
    assert [c.behind for c in check.compared] == [True]


def _clinvar_client(handler: Callable[[httpx.Request], httpx.Response]) -> ClinVarReleaseClient:
    return ClinVarReleaseClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)), gate=_instant_gate()
    )


def _vcf(file_date: str | None) -> bytes:
    header = "##fileformat=VCFv4.1\n"
    if file_date is not None:
        header += f"##fileDate={file_date}\n"
    header += "#CHROM\tPOS\tID\tREF\tALT\n1\t100\trs1\tA\tG\n"
    return gzip.compress(header.encode("utf-8"))


def test_the_live_probe_spells_the_label_the_way_the_snapshot_records_it() -> None:
    """The probe and `clinvar_dataset_label` must produce the same string for the same release.

    Two spellings would not fail — they would simply never match, and the check would quietly report
    every ClinVar module as behind forever.
    """
    client = _clinvar_client(lambda _r: httpx.Response(200, content=_vcf("2026-08-25")))
    assert client.current_release() == f"{CLINVAR_DATASET_PREFIX}2026-08-25"


def test_a_header_with_no_file_date_answers_none_rather_than_a_guess() -> None:
    client = _clinvar_client(lambda _r: httpx.Response(200, content=_vcf(None)))
    assert client.current_release() is None


def test_a_body_that_is_not_gzip_is_unread_rather_than_unreachable(caplog) -> None:
    """A mirror serving an HTML error page with a 200 answered; we could not read what it said."""
    client = _clinvar_client(lambda _r: httpx.Response(200, content=b"<html>go away</html>"))
    with caplog.at_level("WARNING"):
        assert client.current_release() is None
    assert "not a gzip stream" in caplog.text


def test_the_probe_stops_reading_once_it_has_the_header() -> None:
    """A 200 MB download is the failure mode; the stream is abandoned after the probe window."""
    served: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        def body():
            for _ in range(64):
                served.append(1)
                yield b"\x00" * 65_536

        return httpx.Response(200, content=body())

    client = _clinvar_client(handler)
    client.current_release()
    # The window, in whole chunks, plus the one that crosses it — computed rather than copied off a
    # run, so the ceiling moves with `HEADER_PROBE_BYTES` instead of pinning today's number.
    assert sum(served) <= -(-HEADER_PROBE_BYTES // 65_536), "the probe read past its window"
    assert sum(served) < 64, "the probe read the whole body"


@pytest.mark.parametrize(
    "handler",
    [
        pytest.param(lambda r: httpx.Response(503, json={"detail": "unwell"}), id="server-error"),
        pytest.param(
            lambda r: (_ for _ in ()).throw(httpx.ConnectError("connection refused", request=r)),
            id="transport",
        ),
    ],
)
def test_both_legs_of_the_probe_arrive_as_this_tiers_own_type(monkeypatch, handler) -> None:
    """`@client-exception-contract`: retry, then translate, both legs — never an `httpx` type."""
    import time

    monkeypatch.setattr(time, "sleep", lambda _s: None)
    client = _clinvar_client(handler)
    with pytest.raises(ReleaseUnavailable) as caught:
        client.current_release()
    assert not isinstance(caught.value, httpx.HTTPError)
    assert caught.value.__cause__ is not None


def test_the_unavailability_type_is_a_subclass_so_an_existing_handler_keeps_firing() -> None:
    """P3: `except ReleaseProbeError` must keep catching what it caught."""
    assert issubclass(ReleaseUnavailable, ReleaseProbeError)


@pytest.mark.skipif(
    os.environ.get("JUST_DNA_NETWORK_TESTS") != "1",
    reason="network tests are opt-in (JUST_DNA_NETWORK_TESTS=1)",
)
def test_ncbi_states_a_release_the_probe_can_read() -> None:
    """The one live leg: the header really is where NCBI states the date, and it is in reach."""
    client = ClinVarReleaseClient()
    try:
        label = client.current_release()
    finally:
        client.close()
    assert label is not None and label.startswith(CLINVAR_DATASET_PREFIX)


# ── wired into `enrich()` ────────────────────────────────────────────────────────────────────────

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def _spec(tmp_path, dataset: str = "clinvar_2026-06-27"):
    """A module recording that its annotations were drafted from one ClinVar release.

    No `variants.csv` row needs resolving: the currency check is about the module's own provenance
    claim, and giving the resolver work to do would only make the test slower and its failure noisier.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text("rsid,genotype\n", encoding="utf-8")
    (spec / "studies.csv").write_text("rsid,pmid\n", encoding="utf-8")
    (spec / "sources.csv").write_text(
        "source,layer,license,declared_use,dataset\n"
        f"clinvar,annotation,public-domain,unstated,{dataset}\n",
        encoding="utf-8",
    )
    return spec


def _records(spec) -> dict:
    from just_dna_format.layout import VERIFICATION_JSON, sidecar_write_path
    from just_dna_format.verification import read_verification

    doc = read_verification(sidecar_write_path(spec, VERIFICATION_JSON))
    return {r.check: r for r in doc.records}


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    """The attestation mines a nonce; 8 bits keeps these cases from paying for real difficulty."""
    from just_dna_format import verification as verification_module

    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", 8)


def test_enrich_records_the_gap_and_the_module_is_left_alone(tmp_path, caplog) -> None:
    """The finding reaches the run's report, the attestation, and nothing else.

    `write=False` so the assertion below is over the whole directory: a real run legitimately writes
    `resolution.csv` and `verification.json`, and the claim being made here is narrower and sharper —
    *this check* takes nothing into the module and repairs nothing.
    """
    from just_dna_enricher.enrich import enrich

    spec = _spec(tmp_path)
    before = {p.name: p.read_bytes() for p in sorted(spec.iterdir())}
    with caplog.at_level("WARNING"):
        result = enrich(
            spec, offline=False, write=False, download=False, use_gnomad=False,
            verify_ref=False, verify_clinsig=False, verify_rsids=False,
            release_probes={"clinvar": _probe("clinvar_2026-08-25")},
        )
    assert [c.recorded for c in result.dataset_currency.behind] == ["clinvar_2026-06-27"]
    assert "have been superseded" in caplog.text
    assert {p.name: p.read_bytes() for p in sorted(spec.iterdir())} == before


def test_the_attestation_carries_the_comparison_with_its_denominator(tmp_path) -> None:
    from just_dna_enricher.enrich import enrich

    spec = _spec(tmp_path)
    enrich(
        spec, offline=False, download=False, use_gnomad=False,
        verify_ref=False, verify_clinsig=False, verify_rsids=False,
        release_probes={"clinvar": _probe("clinvar_2026-08-25")},
    )
    record = _records(spec)["dataset_currency"]
    assert (record.subjects, record.findings, record.skipped) == (1, 1, None)
    assert "clinvar_2026-06-27 → clinvar_2026-08-25" in record.detail


def test_a_module_still_on_the_current_release_is_recorded_as_compared_and_clean(tmp_path) -> None:
    """`ran(1, 0)` — a real comparison that found nothing, which is a different record from a skip."""
    from just_dna_enricher.enrich import enrich

    spec = _spec(tmp_path)
    enrich(
        spec, offline=False, download=False, use_gnomad=False,
        verify_ref=False, verify_clinsig=False, verify_rsids=False,
        release_probes={"clinvar": _probe("clinvar_2026-06-27")},
    )
    record = _records(spec)["dataset_currency"]
    assert (record.subjects, record.findings, record.skipped) == (1, 0, None)


def test_offline_attests_unchecked_and_never_invokes_the_probe(tmp_path) -> None:
    """The tri-state where it bites, proved by the probe never being called (`@off-switch-needs-a-probe`)."""
    from just_dna_enricher.enrich import enrich

    spec = _spec(tmp_path)
    registry = _NeverAsked()
    result = enrich(spec, offline=True, release_probes=registry.registry())
    record = _records(spec)["dataset_currency"]
    assert record.skipped == "offline"
    assert (record.subjects, record.findings) == (0, 0)
    assert result.dataset_currency.behind == []
    assert all(leg.behind is None for leg in result.dataset_currency.unchecked)


def test_the_off_switch_attests_not_requested_and_asks_nobody(tmp_path) -> None:
    """`not_requested` and `offline` are different facts and only one is cleared by egress."""
    from just_dna_enricher.enrich import enrich

    spec = _spec(tmp_path)
    registry = _NeverAsked()
    result = enrich(
        spec, offline=False, download=False, use_gnomad=False,
        verify_ref=False, verify_clinsig=False, verify_rsids=False,
        verify_datasets=False, release_probes=registry.registry(),
    )
    assert result.dataset_currency is None
    assert _records(spec)["dataset_currency"].skipped == "not_requested"


def test_strict_refuses_over_a_superseded_release(tmp_path) -> None:
    """Severity follows the mode, and the refusal names both labels and the way out."""
    from just_dna_enricher.enrich import EnrichmentError, enrich

    spec = _spec(tmp_path)
    with pytest.raises(EnrichmentError) as caught:
        enrich(
            spec, mode="strict", offline=False, download=False, use_gnomad=False,
            verify_ref=False, verify_clinsig=False, verify_rsids=False,
            release_probes={"clinvar": _probe("clinvar_2026-08-25")},
        )
    assert "have been superseded" in str(caught.value)
    assert "clinvar_2026-08-25" in str(caught.value)
    # A refused strict run commits nothing — the transaction's promise, asserted on the bytes.
    assert not (spec / "resolution.csv").exists()


def test_strict_never_escalates_a_source_nobody_could_reach(tmp_path) -> None:
    """`--offline --strict` must stay possible: nothing an author edits clears a failed request.

    The `unreachable_rsids` rule, and the reason the gate is over `behind` alone. Driven both ways —
    an offline run and a probe that raises — because they reach the skip by different routes and only
    one of them would be caught by reading the `offline` flag.
    """
    from just_dna_enricher.enrich import enrich

    spec = _spec(tmp_path)
    offline_run = enrich(spec, mode="strict", offline=True, release_probes=_NeverAsked().registry())
    assert offline_run.dataset_currency.not_checked == "offline"

    unreachable = enrich(
        spec, mode="strict", offline=False, download=False, use_gnomad=False,
        verify_ref=False, verify_clinsig=False, verify_rsids=False,
        release_probes={"clinvar": _refuses},
    )
    assert unreachable.dataset_currency.not_checked == "unreachable"


def test_a_module_recording_no_dataset_attests_nothing_to_check(tmp_path) -> None:
    """`ran(0, 0)` here would be the pass claiming it compared nothing and found nothing wrong."""
    from just_dna_enricher.enrich import enrich

    spec = _spec(tmp_path, dataset="")
    enrich(
        spec, offline=False, download=False, use_gnomad=False,
        verify_ref=False, verify_clinsig=False, verify_rsids=False,
        release_probes={"clinvar": _probe("clinvar_2026-08-25")},
    )
    record = _records(spec)["dataset_currency"]
    assert record.skipped == "nothing_to_check"
    assert (record.subjects, record.findings) == (0, 0)


def test_the_cli_prints_the_gap_and_says_when_it_could_not_ask(tmp_path, monkeypatch) -> None:
    """The phrases an author greps for, pinned — a warning's text is an API."""
    import just_dna_enricher.enrich as enrich_module
    from just_dna_enricher.cli import app
    from typer.testing import CliRunner

    spec = _spec(tmp_path)
    real = enrich_module.enrich

    def moved(spec_dir, **kwargs):
        # `download=False` as well as the probe: the CLI has no flag for it, and a run that tries to
        # provision a snapshot would make this case depend on whether the runner has egress.
        kwargs["release_probes"] = {"clinvar": _probe("clinvar_2026-08-25")}
        kwargs["download"] = False
        return real(spec_dir, **kwargs)

    monkeypatch.setattr(enrich_module, "enrich", moved)
    monkeypatch.setattr("just_dna_enricher.cli.enrich", moved)
    result = CliRunner().invoke(app, ["enrich", str(spec), "--no-verify-rsids"])
    assert result.exit_code == 0, result.output
    assert "dataset moved on: clinvar (annotation): drafted from clinvar_2026-06-27, now " \
           "clinvar_2026-08-25" in result.output

    offline = CliRunner().invoke(app, ["enrich", str(spec), "--offline"])
    assert offline.exit_code == 0, offline.output
    assert "dataset currency not checked: offline" in offline.output
