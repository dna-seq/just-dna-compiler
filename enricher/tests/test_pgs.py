"""RM163: the PGS Catalog, the fourth registry `check-identifiers` asks.

`pgs_id` is the column `PgsRow` is keyed on and nothing ever put it to its registry. This file pins
the three things that made the item non-obvious.

**The service cannot distinguish its own negatives.** `GET /rest/score/<anything>` answers HTTP 200,
with the record when it holds one and `{}` when it does not — for a never-assigned accession and for
a string that is not an accession at all. So the verdict is read off the body, and the *malformed*
arm is settled by the format's own grammar before any request is spent.

**The two vocabularies do not meet.** `VALID_TRAINING_ANCESTRY` is 1000G superpopulations plus
`multi`; the Catalog's ancestry categories add `NR`, `ASN`, `GME` and `OTH`. A score whose
distribution names one of those has an ancestry this tier cannot spell, so a difference against it is
withheld rather than reported.

**The licence is per score.** `license` is a field on the score record and the three values measured
in the corpus are not variations on one licence — most defer to the authors, some are
academic-research-use-only, some are CC0. One constant covering the source would be a false claim for
the minority in the permissive direction.

Every offline test here runs the **real** client against `httpx.MockTransport` serving payloads
recorded from the live service into `assets/pgs_catalog/`, and computes what it expects from those
payloads at runtime. The Catalog's counts and its licence split move; an assertion quoting one would
convert a live source into a permanently failing test.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.currency import PROBE_SOURCES, ReleaseUnavailable, default_probes
from just_dna_enricher.identifiers import (
    IdentifierReport,
    check_identifiers,
    classify_pgs_accession,
    verification_records,
)
from just_dna_enricher.licensing import (
    PGS_LICENSE_CLASSES,
    PGS_TERMS,
    pgs_license_class,
    pgs_score_terms,
    read_sources_file,
)
from just_dna_enricher.net import PacingGate
from just_dna_enricher.pgs import (
    COMPARED_ANCESTRY_STAGES,
    PGS_ANCESTRY_CATEGORIES,
    PGS_DATASET_PREFIX,
    PGS_SOURCE,
    PgsCatalogClient,
    PgsCatalogUnavailable,
    ancestry_agrees,
    cohort_agrees,
    dataset_label,
    parse_release,
    score_ancestries,
    score_cohort_names,
)
from just_dna_format.pgs import VALID_TRAINING_ANCESTRY
from just_dna_format.sources import taints_commercial_use
from typer.testing import CliRunner

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "pgs_catalog"

#: Recorded 2026-09-01 from the live REST surface, unmodified. `PGS999999` is the `200 + {}` answer.
_ASSIGNED = ("PGS000001", "PGS000004", "PGS000008", "PGS000013", "PGS000116")

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: rm163\n  title: RM163\n  description: d\n  report_title: RM163\n"
)


def _payload(accession: str) -> dict:
    return json.loads((ASSETS / f"{accession}.json").read_text(encoding="utf-8"))


def _instant_gate() -> PacingGate:
    return PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)


class _Catalog:
    """The recorded REST surface, served through the real client's real transport.

    It records every path asked for, which is how the "a malformed accession is never put to the
    Catalog" claim is proved rather than asserted: an off-switch needs a probe, and the probe is the
    request that did not happen.
    """

    def __init__(self) -> None:
        self.asked: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.asked.append(path)
        if path.endswith("/info"):
            return httpx.Response(200, content=(ASSETS / "info.json").read_bytes())
        accession = path.rstrip("/").rsplit("/", 1)[-1]
        recorded = ASSETS / f"{accession}.json"
        if recorded.exists():
            return httpx.Response(200, content=recorded.read_bytes())
        # The Catalog's own negative: 200 with an empty body, whatever was asked.
        return httpx.Response(200, content=b"{}")

    def client(self) -> PgsCatalogClient:
        return PgsCatalogClient(
            client=httpx.Client(transport=httpx.MockTransport(self.handler)), gate=_instant_gate()
        )


def _spec(tmp_path: Path, pgs_csv: str, name: str = "spec") -> Path:
    spec = tmp_path / name
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "pgs.csv").write_text(pgs_csv, encoding="utf-8")
    return spec


# ── the two vocabularies, and the map between them ───────────────────────────────────────────────


def test_the_ancestry_map_lands_exactly_on_the_formats_own_vocabulary() -> None:
    """An equality over the walked set, never a subset: a member with no category behind it is a
    member this check can never vouch for, and a category mapped to a code the format does not carry
    would put an invented value into a comparison."""
    mapped = {member for member in PGS_ANCESTRY_CATEGORIES.values() if member is not None}
    assert mapped == VALID_TRAINING_ANCESTRY, sorted(mapped ^ VALID_TRAINING_ANCESTRY)


def test_every_ancestry_category_the_recorded_payloads_serve_is_in_the_map() -> None:
    """The guard against a category the Catalog invents later (`@lookup-with-a-default-hides-a-new-
    member`). Computed from the fixtures, so it grows when a re-recorded payload does."""
    observed = {
        code
        for accession in _ASSIGNED
        for stage in (_payload(accession).get("ancestry_distribution") or {}).values()
        for code in (stage.get("dist") or {})
    }
    assert observed - set(PGS_ANCESTRY_CATEGORIES) == set(), sorted(
        observed - set(PGS_ANCESTRY_CATEGORIES)
    )
    # And the premise the withhold rule rests on: the recorded corpus really does serve categories
    # the format has no member for. Without one, the withhold arm below would never be exercised.
    assert {c for c in observed if PGS_ANCESTRY_CATEGORIES[c] is None}


def test_only_the_development_and_evaluation_stages_are_compared() -> None:
    """`gwas` is the discovery study's ancestry, which is upstream of where the score was built.

    Including it would widen the published set until nothing could disagree — a check that cannot
    fail. Proved on a real payload rather than asserted: at least one recorded score has a `gwas`
    category that its own dev/eval stages do not carry.
    """
    assert "gwas" not in COMPARED_ANCESTRY_STAGES
    widened = False
    for accession in _ASSIGNED:
        payload = _payload(accession)
        distribution = payload.get("ancestry_distribution") or {}
        gwas = {
            PGS_ANCESTRY_CATEGORIES.get(code)
            for code in (distribution.get("gwas") or {}).get("dist") or {}
        } - {None}
        published, _ = score_ancestries(payload)
        widened = widened or bool(gwas - published)
    assert widened, "no recorded score has a gwas ancestry outside its dev/eval set"


def test_a_multi_ancestry_category_answers_a_positive_and_blocks_a_negative() -> None:
    """`MAE` and `MAO` are bags, not populations, and the two directions are not symmetric.

    *Multi-ancestry excluding European* and *multi-ancestry including European* each stand for two or
    more superpopulations the Catalog did not break down. `multi` is a perfectly good positive answer
    for both — a score under either really is multi-ancestry — but neither can support a **negative**,
    because an authored code the rest of the distribution does not carry may be inside the bag. `MAO`
    in particular produced a false finding against an authored `EUR`, a population it includes by
    definition.
    """
    from just_dna_enricher.pgs import _UNENUMERABLE_CATEGORIES

    bagged = [
        a for a in _ASSIGNED
        if score_ancestries(_payload(a))[1] and score_ancestries(_payload(a))[1] <= _UNENUMERABLE_CATEGORIES
    ]
    assert bagged, "no recorded score's only unresolved categories are the multi-ancestry ones"
    mapped, unresolved = score_ancestries(_payload(bagged[0]))
    # The positive survives...
    assert "multi" in mapped
    # ...and every code the published set does not name is withheld rather than reported.
    missing = [c for c in VALID_TRAINING_ANCESTRY if not ancestry_agrees(c, mapped)]
    assert missing and unresolved, (
        "the case needs a code outside the published set and a bag that could contain it"
    )
    drift, reason = _compare_ancestry_for_test(bagged[0], missing, _payload(bagged[0]))
    assert drift is None and reason is not None


def _compare_ancestry_for_test(pgs_id, authored, payload):
    from just_dna_enricher.identifiers import _compare_ancestry

    return _compare_ancestry(pgs_id, authored, payload)


# ── the three accession outcomes ─────────────────────────────────────────────────────────────────


def test_the_three_accession_states_are_distinguishable_and_each_has_its_own_reason() -> None:
    """`@answered-is-not-absent`: a verdict function with several arms owes a reason function with
    the same arms, pairwise distinct."""
    known = classify_pgs_accession("PGS000001", _payload("PGS000001"))
    unrecognised = classify_pgs_accession("PGS999999", _payload("PGS999999"))
    malformed = classify_pgs_accession("PGSXXXX", _payload("PGS999999"))

    assert {known.state, unrecognised.state, malformed.state} == {
        "known", "unrecognised", "malformed",
    }
    reasons = [str(known), str(unrecognised), str(malformed)]
    assert len(set(reasons)) == 3, reasons


def test_a_recognised_accession_says_what_it_found() -> None:
    """`@existence-not-identity`. A PGS accession is exactly the shape where a wrong-but-real id
    resolves to somebody else's score, so `True` is not an answer a curator can act on."""
    payload = _payload("PGS000001")
    status = classify_pgs_accession("PGS000001", payload)
    assert status.name == payload["name"]
    assert status.date_release == payload["date_release"]
    assert status.trait_efo_ids == tuple(t["id"] for t in payload["trait_efo"])
    assert status.variants_number == payload["variants_number"]
    message = str(status)
    for shown in (payload["name"], payload["date_release"], payload["trait_efo"][0]["id"]):
        assert shown in message


def test_the_unrecognised_message_names_the_typo_reading_first() -> None:
    """The id space is sparse — most well-formed in-range accessions were never issued — so the base
    rate runs the opposite way from dbSNP's, where `@rsid-absent-two-readings` weights the two
    equally. Naming withdrawal as a co-equal reading would send an author looking for a retirement
    notice that almost certainly does not exist."""
    message = str(classify_pgs_accession("PGS999999", _payload("PGS999999")))
    assert "mistyped or invented" in message
    assert "withdrawal is the rarer reading" in message
    assert message.index("mistyped or invented") < message.index("withdrawal is the rarer")
    # And the limit of the source is stated rather than resolved by guessing.
    assert "no supersession field" in message


def test_a_malformed_accession_is_not_reported_as_a_withdrawal() -> None:
    """It is a spelling. The Catalog's answer about it carries no information at all — 200 with an
    empty body, exactly as for a never-assigned id — so the absence must not be read as a retirement.
    """
    message = str(classify_pgs_accession("PGSXXXX", _payload("PGS999999")))
    assert "withdraw" not in message.lower()
    assert "not a well-formed PGS Catalog accession" in message


def test_the_verdict_is_read_off_the_body_and_never_off_the_status() -> None:
    """A 200 with an empty body is the Catalog's `no`, and a 404 is a failure to ask.

    Both directions, because collapsing either one is the defect: reading the status would call every
    negative a success, and raising on the empty body would turn an answered question into an
    unasked one.
    """
    catalog = _Catalog()
    with catalog.client() as client:
        assert client.score("PGS999999") == {}
        assert client.score("PGS000001")["id"] == "PGS000001"

    def _gone(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    with PgsCatalogClient(
        client=httpx.Client(transport=httpx.MockTransport(_gone)), gate=_instant_gate()
    ) as client, pytest.raises(PgsCatalogUnavailable):
        client.score("PGS000001")


# ── the roster, and the accession the schema refuses before this check can see it ────────────────


def test_a_live_and_a_never_assigned_accession_are_reported_apart(tmp_path: Path) -> None:
    """Two of the recipe's three outcomes, from one spec directory. The third cannot join them —
    see the test below."""
    spec = _spec(tmp_path, "pgs_id\nPGS000001\nPGS999999\n")
    catalog = _Catalog()
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=catalog.client(), write=False,
    )
    assert {s.pgs_id: s.state for s in report.pgs} == {
        "PGS000001": "known", "PGS999999": "unrecognised",
    }
    assert report.pgs_tables_read == ["pgs.csv"]
    assert [s.pgs_id for s in report.stale_pgs] == ["PGS999999"]
    assert not report.clean


def test_a_malformed_accession_never_reaches_the_catalog_because_the_schema_refuses_it(
    tmp_path: Path,
) -> None:
    """**The proposal's e2e recipe cannot be built as written, and this is why.**

    It asks for one spec directory carrying a live accession, a never-assigned one and `PGSXXXX`.
    `PgsRow._validate_pgs_id` refuses `PGSXXXX` at load, so the whole `pgs.csv` fails to parse and no
    accession in it is checked at all — the malformed case is caught a tier earlier than this check,
    by the format's own grammar.

    What survives is the guarantee the recipe was after: the malformed id is never put to the
    Catalog, and the table's failure is reported as a *reason a question was not put* rather than as
    a clean run. `classify_pgs_accession` keeps its `malformed` arm for the id that arrives from
    somewhere other than a parsed row.
    """
    spec = _spec(tmp_path, "pgs_id\nPGS000001\nPGSXXXX\n")
    catalog = _Catalog()
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=catalog.client(), write=False,
    )
    assert report.pgs == []
    assert report.pgs_tables_read == []
    assert "pgs.csv" in report.unreadable_tables
    assert "PGSXXXX" in report.pgs_tables_not_read["pgs.csv"]
    # The off-switch, probed rather than read: not one request was made, for either accession.
    assert catalog.asked == []


def test_a_switched_off_check_is_still_recorded_on_a_module_with_no_identifier(
    tmp_path: Path,
) -> None:
    """The corner the fourth flag moved, pinned rather than left for a reader to find.

    The command's "nothing to check" guard used to fire whenever *some* check was requested and no
    table was read, and it returns before the attestation — so a module carrying nothing minted no
    nonce. With a fourth flag the condition had to say which absence it means, and it now requires
    **all** flags on: a check the author switched off is a record they asked for, and `not_requested`
    is written on the path below. The consequence is deliberate — `--no-traits` on a module with no
    id-bearing table now attests where it once returned silently.
    """
    from just_dna_enricher.cli import app
    from just_dna_format.verification import read_verification

    spec = tmp_path / "bare"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")

    everything_on = CliRunner().invoke(app, ["check-identifiers", str(spec)])
    assert everything_on.exit_code == 0
    assert "nothing to check" in everything_on.output
    assert not (spec / "verification.json").exists(), "no nonce on a module that never asked"

    one_off = CliRunner().invoke(app, ["check-identifiers", str(spec), "--no-traits"])
    assert one_off.exit_code == 0
    checks = {r.check: r for r in read_verification(spec / "verification.json").records}
    assert checks["trait_currency"].skipped == "not_requested"
    assert checks["pgs_accession_currency"].skipped == "nothing_to_check"


def test_an_unreadable_table_still_reports_rather_than_exiting_nothing_to_check(
    tmp_path: Path,
) -> None:
    """The CLI guard's own version of the same absence, and it was wrong before this item too.

    A module whose only id-bearing table exists and will not parse read nothing, so the command
    returned "nothing to check" — never printing the unreadable-table warning and never attesting. A
    question that could not be put is exactly what a reader needs on that run.
    """
    from just_dna_enricher.cli import app

    spec = _spec(tmp_path, "pgs_id\nPGSXXXX\n")
    result = CliRunner().invoke(app, ["check-identifiers", str(spec), "--no-pgs"])
    assert result.exit_code == 0
    assert "nothing to check" not in result.output
    assert "could not be read" in result.output


# ── the two-field drift check ────────────────────────────────────────────────────────────────────


def _ancestry_case() -> tuple[str, dict, frozenset[str]]:
    """A recorded score whose dev/eval ancestries are all mappable — the only shape that can drift."""
    for accession in _ASSIGNED:
        payload = _payload(accession)
        published, unmappable = score_ancestries(payload)
        if published and not unmappable:
            return accession, payload, published
    pytest.skip("no recorded score has a fully mappable dev/eval ancestry distribution")


def test_an_authored_ancestry_the_catalog_contradicts_is_reported(tmp_path: Path) -> None:
    """The drift arm. The disagreeing code is derived from the payload, never named in the test:
    quoting one would break the day the Catalog re-curates that score."""
    accession, _payload_, published = _ancestry_case()
    disagreeing = sorted(
        code for code in VALID_TRAINING_ANCESTRY if not ancestry_agrees(code, published)
    )
    assert disagreeing, "the case needs a code the published set does not cover"
    spec = _spec(tmp_path, f"pgs_id,training_ancestry\n{accession},{disagreeing[0]}\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    drift = report.pgs_metadata.drift
    assert [(d.pgs_id, d.field_name) for d in drift] == [(accession, "training_ancestry")]
    assert [(c[0], c[1]) for c in report.pgs_metadata.compared] == [(accession, "training_ancestry")]
    assert not report.pgs_metadata.withheld
    assert disagreeing[0] in str(drift[0])


def test_an_authored_ancestry_the_catalog_agrees_with_is_silent(tmp_path: Path) -> None:
    accession, _payload_, published = _ancestry_case()
    agreeing = sorted(code for code in VALID_TRAINING_ANCESTRY if ancestry_agrees(code, published))
    assert agreeing, "the case needs a code the published set does cover"
    spec = _spec(tmp_path, f"pgs_id,training_ancestry\n{accession},{agreeing[0]}\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    assert report.pgs_metadata.drift == []
    assert [(c[0], c[1]) for c in report.pgs_metadata.compared] == [(accession, "training_ancestry")]
    assert report.clean


def test_an_ancestry_the_catalog_cannot_spell_is_withheld_rather_than_reported(
    tmp_path: Path,
) -> None:
    """The arm the item turns on. A score whose distribution carries `NR`, `ASN`, `GME` or `OTH` has
    an ancestry this format has no member for, so an authored code the published set does not carry
    might be exactly that one — and a difference we cannot stand behind is withheld."""
    case = next(
        (
            (accession, *score_ancestries(_payload(accession)))
            for accession in _ASSIGNED
            if score_ancestries(_payload(accession))[1]
        ),
        None,
    )
    assert case is not None, "no recorded score carries an unmappable ancestry category"
    accession, published, _unmappable = case
    missing = sorted(code for code in VALID_TRAINING_ANCESTRY if not ancestry_agrees(code, published))
    assert missing, "the case needs a code the published set does not cover"
    spec = _spec(tmp_path, f"pgs_id,training_ancestry\n{accession},{missing[0]}\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    comparison = report.pgs_metadata
    assert comparison.drift == []
    assert comparison.compared == []
    assert [(c[0], c[1]) for c in comparison.withheld] == [(accession, "training_ancestry")]
    assert "cannot enumerate" in next(iter(comparison.withheld.values()))


def test_an_empty_cell_is_skipped_rather_than_withheld(tmp_path: Path) -> None:
    """No authored value is no claim to disagree with. Counting it as a cell that could not be
    settled would overstate what this check was unable to do — the denominator is what was
    examined."""
    accession, _payload_, _published = _ancestry_case()
    spec = _spec(tmp_path, f"pgs_id,training_ancestry,training_cohort\n{accession},,\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    comparison = report.pgs_metadata
    assert comparison.authored == []
    assert comparison.withheld == {}
    assert comparison.compared == []
    assert report.clean


def _cohort_case() -> tuple[str, list[str]]:
    for accession in _ASSIGNED:
        names = score_cohort_names(_payload(accession))
        if names:
            return accession, names
    pytest.skip("no recorded score lists training samples")


def test_the_free_text_cohort_comparison_is_three_valued(tmp_path: Path) -> None:
    """`training_cohort` is free-form and no reliable equality exists between two people's prose, so
    the disagreement arm fires only when the authored cell shares no word at all with the record.
    A cell with nothing long enough to match on reports unknown rather than either verdict."""
    accession, names = _cohort_case()
    assert cohort_agrees(names[0], names) is True
    assert cohort_agrees("Zzyzx Nonesuch", names) is False
    assert cohort_agrees("NW", names) is None
    # A structural word matches almost every record, so it is dropped rather than allowed to vouch:
    # otherwise "Zzyzx Cohort Nonesuch" would pass on the word `Cohort` alone.
    assert cohort_agrees("Cohort Study", names) is None
    assert cohort_agrees("Zzyzx Cohort Nonesuch", names) is False

    spec = _spec(tmp_path, f"pgs_id,training_cohort\n{accession},Zzyzx Nonesuch\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    assert [(d.pgs_id, d.field_name) for d in report.pgs_metadata.drift] == [
        (accession, "training_cohort")
    ]


def test_a_score_with_no_training_samples_withholds_the_cohort_cell(tmp_path: Path) -> None:
    """The Catalog carrying nothing is not the module being wrong."""
    bare = next(
        (a for a in _ASSIGNED if not score_cohort_names(_payload(a))),
        None,
    )
    assert bare is not None, "no recorded score is missing its training samples"
    spec = _spec(tmp_path, f"pgs_id,training_cohort\n{bare},UK Biobank\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    comparison = report.pgs_metadata
    assert comparison.drift == []
    assert [(c[0], c[1]) for c in comparison.withheld] == [(bare, "training_cohort")]
    assert "lists no training samples" in next(iter(comparison.withheld.values()))


def test_the_two_columns_the_catalog_has_no_opinion_about_are_not_checked(tmp_path: Path) -> None:
    """`match_rate_floor` is an author-set floor and `research_tier` is a curator judgement. The
    Catalog publishes neither, so a check over them could not fail — `@tautology-zero` — and a check
    that cannot fail must not report a zero."""
    accession, _payload_, _published = _ancestry_case()
    spec = _spec(
        tmp_path,
        f"pgs_id,match_rate_floor,research_tier\n{accession},0.9,research_only\n",
    )
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    assert report.pgs_metadata.authored == []
    record = next(
        r for r in verification_records(report, check_traits=False, check_genes=False)
        if r.check == "pgs_metadata_agreement"
    )
    # A skip, never `ran(0, 0)`: a check that cannot fail must not report a zero, and a zero out of
    # zero reads as a clean bill.
    assert record.skipped == "nothing_to_check"
    assert "match_rate_floor and research_tier are not in this check's scope" in record.detail


def test_one_accession_on_two_rows_is_one_cell(tmp_path: Path) -> None:
    """`PgsRow` is keyed `(pgs_id, trait_efo_id)`, so a pleiotropic score is two rows under one
    accession. Counting its cell twice would inflate both halves of the record over one claim."""
    accession, _payload_, published = _ancestry_case()
    agreeing = min(code for code in VALID_TRAINING_ANCESTRY if ancestry_agrees(code, published))
    spec = _spec(
        tmp_path,
        "pgs_id,trait_efo_id,training_ancestry\n"
        f"{accession},EFO:0004458,{agreeing}\n"
        f"{accession},MONDO:0005010,{agreeing}\n",
    )
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    assert [(c[0], c[1]) for c in report.pgs_metadata.compared] == [(accession, "training_ancestry")]
    # And the accession itself is one subject, not two.
    assert [s.pgs_id for s in report.pgs] == [accession]


def test_two_rows_stating_different_values_are_two_claims(tmp_path: Path) -> None:
    """The dedupe collapses identical claims and must not collapse differing ones.

    `PgsRow` is keyed `(pgs_id, trait_efo_id)`, so one accession legitimately appears on two rows —
    and a curator who corrected the ancestry on one of them leaves two different claims under one
    accession. Keying the cell on `(pgs_id, field)` alone dropped whichever row came second, so
    whether the stale value was caught depended on row order in the file. Both orders are run here.
    """
    accession, _payload_, published = _ancestry_case()
    agreeing = min(c for c in VALID_TRAINING_ANCESTRY if ancestry_agrees(c, published))
    drifting = min(c for c in VALID_TRAINING_ANCESTRY if not ancestry_agrees(c, published))
    for order, name in (((agreeing, drifting), "good-first"), ((drifting, agreeing), "bad-first")):
        spec = _spec(
            tmp_path,
            "pgs_id,trait_efo_id,training_ancestry\n"
            f"{accession},EFO:0004458,{order[0]}\n"
            f"{accession},MONDO:0005010,{order[1]}\n",
            name=name,
        )
        report = check_identifiers(
            spec_dir=spec, check_traits=False, check_genes=False,
            pgs_client=_Catalog().client(), write=False,
        )
        assert len(report.pgs_metadata.compared) == 2, f"{name}: both claims must be put"
        assert [d.authored for d in report.pgs_metadata.drift] == [drifting], name


def test_a_source_disagreement_never_fails_the_strict_gate(tmp_path: Path) -> None:
    """`--strict` grades a *stale identifier*, never a difference between two authorities.

    `PgsDrift`'s own message tells the author to leave the cell if their curation is deliberate, so
    failing the build on it would be a gate with no way to clear it — the shape
    `@clinsig-never-escalates` and `@a-source-recuring-is-not-a-strict-matter` keep out. An
    unrecognised accession is a different kind and does still fail, which is what makes this a
    distinction rather than a softening.
    """
    from just_dna_enricher.cli import app

    accession, _payload_, published = _ancestry_case()
    drifting = min(c for c in VALID_TRAINING_ANCESTRY if not ancestry_agrees(c, published))
    drifted = _spec(
        tmp_path, f"pgs_id,training_ancestry\n{accession},{drifting}\n", name="drifted"
    )
    stale = _spec(tmp_path, "pgs_id\nPGS999999\n", name="stale")

    catalog = _Catalog()
    import just_dna_enricher.identifiers as identifiers_module

    original = identifiers_module.PgsCatalogClient
    identifiers_module.PgsCatalogClient = catalog.client
    try:
        drift_run = CliRunner().invoke(
            app, ["check-identifiers", str(drifted), "--no-traits", "--no-genes", "--strict"]
        )
        stale_run = CliRunner().invoke(
            app, ["check-identifiers", str(stale), "--no-traits", "--no-genes", "--strict"]
        )
    finally:
        identifiers_module.PgsCatalogClient = original

    assert drift_run.exit_code == 0, drift_run.output
    assert "a source disagrees with an authored cell" in drift_run.output
    assert stale_run.exit_code == 1, stale_run.output


# ── the terms, per score ─────────────────────────────────────────────────────────────────────────


def test_every_recorded_licence_string_falls_in_a_class_this_tier_has_read() -> None:
    """The premise the per-score row rests on. An unrecognised string is honest — all three axes
    unknown — but it means the classifier has fallen behind, so the corpus is checked rather than
    assumed."""
    for accession in _ASSIGNED:
        licence = _payload(accession)["license"]
        name, _licence, _rights = pgs_license_class(licence)
        assert name is not None, (accession, licence)
    # And every class the tier declares is exercised by the recorded corpus, so none of them is a
    # rule nobody has seen a payload for.
    seen = {pgs_license_class(_payload(a)["license"])[0] for a in _ASSIGNED}
    declared = {name for name, _pattern, _licence, _rights in PGS_LICENSE_CLASSES}
    assert seen == declared, sorted(seen ^ declared)


def test_an_unread_licence_string_is_unknown_on_every_axis() -> None:
    """Unknown is not permission. `None` is never `False` and it is never `True` either."""
    name, licence, rights = pgs_license_class("Some licence nobody here has read")
    assert name is None and licence is None
    assert (rights.share_alike, rights.commercial_use, rights.redistribution) == (None, None, None)


def test_an_academic_use_only_score_does_not_carry_the_generic_terms() -> None:
    """The correctness requirement, on a real payload. A single `PGS_TERMS` row would claim the
    Catalog's generic terms — unknown on every axis, which never gates — for a score whose own
    licence bars sale outright."""
    academic = [
        a for a in _ASSIGNED
        if pgs_license_class(_payload(a)["license"])[0] == "academic_research_only"
    ]
    assert academic, "no recorded score carries the academic-use-only licence"
    accession = academic[0]
    licence = _payload(accession)["license"]
    terms = pgs_score_terms(accession, licence)

    assert terms.source == f"{PGS_SOURCE}:{accession}"
    # A short NAME in `license` — the compiler compares that column against `module_spec.yaml`'s
    # declared licence by equality — and the published sentence, verbatim, in `notice`.
    assert terms.license and len(terms.license) < 60
    assert licence in (terms.notice or ""), "the source's own string, verbatim"
    assert terms.commercial_use is False
    assert terms.redistribution is False
    # ...and that is strictly more restrictive than the floor, which establishes nothing.
    assert (PGS_TERMS.commercial_use, PGS_TERMS.redistribution) == (None, None)
    row = terms.row("annotation", declared_use="unstated", license_text=licence)
    assert taints_commercial_use(row), "the annotation layer is where the gate reads it"
    assert row.license_sha256 and row.license_sha256.startswith("sha256:")


def test_the_pass_writes_a_source_row_per_score_and_a_floor_row(tmp_path: Path) -> None:
    """`@write-the-sourcerow`, and the per-score half is the item's correctness requirement.

    Run over a module carrying two scores under different licences, so the false-claim case is real
    rather than hypothetical: one row cannot describe both.
    """
    by_class = {pgs_license_class(_payload(a)["license"])[0]: a for a in _ASSIGNED}
    assert len(by_class) >= 2, "the case needs two recorded scores under different licences"
    accessions = sorted(by_class.values())[:2]
    spec = _spec(tmp_path, "pgs_id\n" + "".join(f"{a}\n" for a in accessions))
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False, pgs_client=_Catalog().client(),
    )
    written = {row.source: row for row in read_sources_file(spec)}
    assert set(written) == {PGS_SOURCE, *(f"{PGS_SOURCE}:{a}" for a in accessions)}
    for accession in accessions:
        row = written[f"{PGS_SOURCE}:{accession}"]
        assert _payload(accession)["license"] in (row.notice or "")
        assert row.layer == "annotation"
        # The release sits on the floor row alone: a release is a fact about the Catalog, and
        # stamping it per score would put N identical unchecked legs into `verify_datasets`.
        assert row.dataset is None
    floor = written[PGS_SOURCE]
    assert floor.dataset == report.pgs_release
    assert (floor.share_alike, floor.commercial_use, floor.redistribution) == (None, None, None)


def test_the_reported_rows_are_this_sources_and_the_merge_never_clobbers(tmp_path: Path) -> None:
    """Two claims the merge makes and one the field's name makes.

    `merge_sources_file` returns the whole table, so a module that also records ClinVar would put
    foreign rows on a field called `pgs_sources`; and existing rows win, so a hand-written licence
    survives a re-run and is what the caller must be shown.
    """
    accession = _ASSIGNED[0]
    spec = _spec(tmp_path, f"pgs_id\n{accession}\n")
    (spec / "licensing.csv").write_text(
        "source,layer,license,commercial_use,dataset\n"
        "clinvar,annotation,public-domain,true,clinvar_2026-06-27\n"
        f"{PGS_SOURCE}:{accession},annotation,A licence a human wrote,,\n",
        encoding="utf-8",
    )
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False, pgs_client=_Catalog().client(),
    )
    assert {row.source for row in report.pgs_sources} == {PGS_SOURCE, f"{PGS_SOURCE}:{accession}"}
    per_score = next(r for r in report.pgs_sources if r.source.endswith(accession))
    assert per_score.license == "A licence a human wrote", "existing rows win the merge"
    # ...and the foreign row is still in the file, untouched.
    assert {row.source for row in read_sources_file(spec)} == {
        "clinvar", PGS_SOURCE, f"{PGS_SOURCE}:{accession}",
    }


def test_a_run_that_asks_nothing_writes_no_source_row(tmp_path: Path) -> None:
    """`@write-the-sourcerow`'s other half: a pass that contributes nothing writes none, keyed on what
    this run covered rather than on the table being present."""
    spec = _spec(tmp_path, "pgs_id,note\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False, pgs_client=_Catalog().client(),
    )
    assert report.pgs_sources == []
    assert not (spec / "sources.csv").exists()


def test_a_release_that_has_moved_is_withdrawn_rather_than_left_standing(tmp_path: Path) -> None:
    """`merge_sources_csv` is never-clobber, so without a `withdraw_stale_dataset` companion the floor
    row would hold its first release forever — `verify_datasets` reporting it behind on every run,
    with the pass that owns the row unable to refresh it. It only ever blanks: one column cannot name
    two releases, so a row whose terms were read across a boundary records unknown."""
    accession = _ASSIGNED[0]
    spec = _spec(tmp_path, f"pgs_id\n{accession}\n")
    (spec / "licensing.csv").write_text(
        "source,layer,dataset\n"
        f"{PGS_SOURCE},annotation,{PGS_DATASET_PREFIX}1999-01-01\n",
        encoding="utf-8",
    )
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False, pgs_client=_Catalog().client(),
    )
    assert report.pgs_release and report.pgs_release != f"{PGS_DATASET_PREFIX}1999-01-01"
    floor = next(r for r in read_sources_file(spec) if r.source == PGS_SOURCE)
    assert floor.dataset is None, "withdrawn, never re-labelled"


# ── the release record, read rather than built ───────────────────────────────────────────────────


def test_the_release_is_read_from_the_catalogs_own_info_endpoint() -> None:
    payload = json.loads((ASSETS / "info.json").read_text(encoding="utf-8"))
    release = parse_release(payload)
    assert release.date == payload["latest_release"]["date"]
    assert release.scores == payload["latest_release"]["scores"]
    assert release.rest_api_version == payload["rest_api"]["version"]
    assert release.terms_of_use == payload["terms_of_use"]
    assert dataset_label(release) == PGS_DATASET_PREFIX + payload["latest_release"]["date"]
    assert dataset_label(None) is None


def test_the_label_the_pass_stamps_is_the_label_the_probe_answers(tmp_path: Path) -> None:
    """`clinvar_dataset_label`'s rule: two spellings of one release make the currency check quietly
    never match, and "never matches" renders as unreadable rather than as a bug."""
    catalog = _Catalog()
    spec = _spec(tmp_path, "pgs_id\nPGS000001\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=catalog.client(), write=False,
    )
    probe = default_probes(pgs_catalog=catalog.client())[PGS_SOURCE]
    assert report.pgs_release == probe()


def test_the_catalog_joins_the_shipped_probe_registry() -> None:
    assert PGS_SOURCE in PROBE_SOURCES
    assert frozenset(default_probes()) == PROBE_SOURCES


def test_the_probe_translates_the_clients_error_into_the_currency_one() -> None:
    """`_ask` reads the reason off `ReleaseProbeError`'s subclass, so a probe leaking the client's
    own type would abort the run instead of marking one leg unreachable."""

    def _unwell(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "upstream is unwell"})

    client = PgsCatalogClient(
        client=httpx.Client(transport=httpx.MockTransport(_unwell)), gate=_instant_gate()
    )
    with pytest.raises(ReleaseUnavailable):
        default_probes(pgs_catalog=client)[PGS_SOURCE]()


def test_an_unreadable_release_does_not_sink_the_accession_check(tmp_path: Path) -> None:
    """The release is a fact about the Catalog, not about any accession. Withheld, and the verdicts
    still stand."""

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/info"):
            return httpx.Response(503, json={"detail": "no"})
        return httpx.Response(200, content=(ASSETS / "PGS000001.json").read_bytes())

    client = PgsCatalogClient(
        client=httpx.Client(transport=httpx.MockTransport(_handler)), gate=_instant_gate()
    )
    spec = _spec(tmp_path, "pgs_id\nPGS000001\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False, pgs_client=client, write=False,
    )
    assert report.pgs_release is None
    assert [s.state for s in report.pgs] == ["known"]


def test_a_catalog_that_never_answers_is_unreachable_and_only_its_own_records_say_so(
    tmp_path: Path,
) -> None:
    """S20's distinction, and the reason this leg does **not** raise.

    `check_identifiers` puts questions to four registries and the command writes one record per
    check. Letting a `PgsCatalogUnavailable` out would make the CLI's `IdentifierUnavailable` handler
    stamp `unreachable` against `trait_currency` and `gene_symbol_currency` as well — for registries
    that answered perfectly well. The outage reaches exactly the two records it is about.
    """

    def _refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = PgsCatalogClient(
        client=httpx.Client(transport=httpx.MockTransport(_refuse)), gate=_instant_gate()
    )
    spec = _spec(tmp_path, "pgs_id\nPGS000001\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False, pgs_client=client, write=False,
    )
    assert report.pgs_not_checked is not None
    assert report.pgs_not_checked[0] == "unreachable"
    # Nothing was read, so nothing is claimed and no terms are recorded.
    assert report.pgs == [] and report.pgs_sources == []
    records = {
        r.check: r for r in verification_records(report, check_traits=False, check_genes=False)
    }
    assert records["pgs_accession_currency"].skipped == "unreachable"
    assert records["pgs_metadata_agreement"].skipped == "unreachable"
    # ...and the two registries this run never asked keep their own, different reason.
    assert records["trait_currency"].skipped == "not_requested"
    assert records["gene_symbol_currency"].skipped == "not_requested"


def test_the_calling_form_with_rows_says_unsupported_rather_than_nothing_to_check() -> None:
    """No row model a caller can hold carries a `pgs_id`, so "no row carries one" would assert a fact
    about the module that this call never established — the never-asked / asked-and-empty split the
    roster machinery exists to keep honest."""
    report = check_identifiers(variants=[], check_traits=False, check_genes=False)
    assert report.pgs_not_checked is not None and report.pgs_not_checked[0] == "unsupported"
    records = {
        r.check: r for r in verification_records(report, check_traits=False, check_genes=False)
    }
    assert records["pgs_accession_currency"].skipped == "unsupported"
    assert "pass spec_dir=" in records["pgs_accession_currency"].detail


# ── the two attestations ─────────────────────────────────────────────────────────────────────────


def test_the_two_records_have_different_subjects_and_different_denominators(
    tmp_path: Path,
) -> None:
    """Two members rather than one: currency asks whether the id still names a score and drift asks
    whether two cells beside it still match. One record over two populations would publish a findings
    count that means nothing."""
    accession, _payload_, published = _ancestry_case()
    agreeing = min(code for code in VALID_TRAINING_ANCESTRY if ancestry_agrees(code, published))
    spec = _spec(
        tmp_path,
        "pgs_id,training_ancestry\n"
        f"{accession},{agreeing}\n"
        "PGS999999,\n",
    )
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    records = {
        r.check: r for r in verification_records(report, check_traits=False, check_genes=False)
    }
    currency = records["pgs_accession_currency"]
    metadata = records["pgs_metadata_agreement"]
    assert currency.subjects == len(report.pgs)
    assert currency.findings == len(report.stale_pgs)
    assert metadata.subjects == len(report.pgs_metadata.compared)
    assert metadata.subjects != currency.subjects, (
        "the two denominators must be able to differ, or one record would have done"
    )
    assert currency.source == metadata.source == PGS_SOURCE


def test_switching_the_leg_off_is_not_requested_on_both_records() -> None:
    records = {
        r.check: r
        for r in verification_records(
            IdentifierReport(), check_traits=False, check_genes=False, check_pgs=False
        )
    }
    for check in ("pgs_accession_currency", "pgs_metadata_agreement"):
        assert records[check].skipped == "not_requested"
        assert records[check].detail and "--no-pgs" in records[check].detail


def test_withheld_cells_travel_with_the_finding_rather_than_vanishing(tmp_path: Path) -> None:
    """`@dont-discard-computed`: a reader who cannot see them reads the agreement count as covering
    every authored cell."""
    withheld_case = next(
        (a for a in _ASSIGNED if score_ancestries(_payload(a))[1]), None
    )
    assert withheld_case is not None
    published, _ = score_ancestries(_payload(withheld_case))
    missing = min(c for c in VALID_TRAINING_ANCESTRY if not ancestry_agrees(c, published))
    spec = _spec(tmp_path, f"pgs_id,training_ancestry\n{withheld_case},{missing}\n")
    report = check_identifiers(
        spec_dir=spec, check_traits=False, check_genes=False,
        pgs_client=_Catalog().client(), write=False,
    )
    record = next(
        r for r in verification_records(report, check_traits=False, check_genes=False)
        if r.check == "pgs_metadata_agreement"
    )
    assert record.skipped == "no_reference"
    assert "withheld rather than compared" in record.detail
    assert f"{withheld_case}/training_ancestry" in record.detail


def test_the_command_attests_both_records_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """The CLI path, with the network replaced at the client and nothing else mocked."""
    from just_dna_enricher import identifiers as identifiers_module
    from just_dna_enricher.cli import app
    from just_dna_format.verification import read_verification

    catalog = _Catalog()
    monkeypatch.setattr(identifiers_module, "PgsCatalogClient", catalog.client)
    spec = _spec(tmp_path, "pgs_id\nPGS000001\nPGS999999\n")
    result = CliRunner().invoke(app, ["check-identifiers", str(spec), "--no-traits", "--no-genes"])
    assert result.exit_code == 0, result.output
    document = read_verification(spec / "verification.json")
    checks = {r.check: r for r in document.records}
    assert checks["pgs_accession_currency"].findings == 1
    assert checks["pgs_metadata_agreement"].skipped == "nothing_to_check"
    assert "PGS accessions checked: 2" in result.output
    # And the terms landed beside the attestation, per score.
    assert {row.source for row in read_sources_file(spec)} == {
        PGS_SOURCE, f"{PGS_SOURCE}:PGS000001",
    }


# ── live ─────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.getenv("JUST_DNA_NETWORK_TESTS"), reason="set JUST_DNA_NETWORK_TESTS=1 to hit the network"
)
def test_the_live_surface_still_answers_200_with_an_empty_body_for_every_negative() -> None:
    """The measurement the whole design rests on, re-taken rather than quoted.

    If the Catalog ever starts answering 404 for an id it does not hold, this fails and the body-read
    rule can be revisited — which is the point of pinning it here rather than in prose.
    """
    with PgsCatalogClient() as client:
        assert client.score("PGS000001")["id"] == "PGS000001"
        assert client.score("PGS999999") == {}
        release = client.release()
    assert release.date and dataset_label(release).startswith(PGS_DATASET_PREFIX)
