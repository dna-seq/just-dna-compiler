"""gnomAD's callset has a hole, and an absence inside it is not a fact (0.5.1).

`enrich_frequencies` used to record `status="not_found"` for every allele gnomAD returned nothing for,
with the comment "gnomAD was asked and does not have this allele". For a **Y pseudoautosomal** locus
that is false. gnomAD hard-masks the Y PAR — those bases duplicate the X PAR and reads cannot be placed
there — so it never looked, and its silence is not an absence.

Probed live 2026-08-04, twice, because a single-variant miss cannot tell "absent" from "not covered":

* `region(chrom:"X", 640000-641500)` serves **880** variants; the identical interval on Y serves **0**.
* `variant(variantId:"X-640851-C-T")` resolves; `Y-640851-C-T` returns `Variant not found`.

The locus is real either way — `rs137852556` is a pathogenic SHOX variant that dbSNP maps to X:640851
*and* Y:640851 — so before the PAR selection landed, a one-to-many expansion handed this pass ten Y
loci and it wrote ten false absences. This is the house `None` ≠ `False` rule, one level above
`FrequencyRow.allele_frequency`, whose own docstring already argues that an `AN` of 0 means "no
information" rather than "frequency zero".
"""

import json
import logging
from pathlib import Path

import httpx
import pytest
from just_dna_format.frequency import FrequencyRow
from just_dna_format.vocab import VALID_FREQUENCY_STATUS
from just_dna_format.vrs import derive_vrs_allele_id

from just_dna_enricher.frequencies import enrich_frequencies
from just_dna_enricher.gnomad import GnomadClient, GnomadSettings, covers_locus
from just_dna_enricher.net import PacingGate

_ASSETS = Path(__file__).resolve().parents[2] / "assets"

# rs137852556, SHOX, PAR1 — the same base on both contigs in GRCh38.
_X_KEY = derive_vrs_allele_id("X", 640851, "C", "T")
_Y_KEY = derive_vrs_allele_id("Y", 640851, "C", "T")


# ── the coverage predicate ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("chrom", "start", "expected", "why"),
    [
        ("Y", 640851, False, "PAR1 on Y — masked out of the callset"),
        ("Y", 56960499, False, "PAR2 on Y, at its own coordinate — masked too"),
        ("X", 640851, True, "the X spelling of the same place IS covered, and serves 880 in 1.5 kb"),
        ("X", 155773979, True, "X PAR2 likewise"),
        ("Y", 2789135, True, "the male-specific region is covered — masking is PAR-only"),
        ("11", 5227002, True, "an autosome, obviously"),
        ("Y", None, True, "no coordinate: nothing says this is the masked region"),
    ],
)
def test_the_coverage_predicate_masks_only_the_y_par(chrom, start, expected, why) -> None:
    assert covers_locus(chrom, start) is expected, why


def test_an_unknown_build_withholds_a_coverage_claim() -> None:
    """PAR intervals are per-assembly (RM15), so on another build this cannot vouch for coverage
    either way — and an unknown must not be spent asserting that a locus IS covered."""
    assert covers_locus("Y", 640851, build="GRCh37") is None


# ── the pass ────────────────────────────────────────────────────────────────────────────────────


def _mock_client(handler) -> GnomadClient:
    client = GnomadClient(settings=GnomadSettings())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _spec(tmp_path: Path, *, keep_y: bool = True) -> Path:
    """A module whose resolution table carries both contigs of one real PAR locus.

    That is what `--keep-par-twin` produces, and what every PAR module produced before the selection
    landed — so it is exactly the input that provoked the false absence.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\n"
        "rs137852556,C/T,risk,ClinVar: pathogenic,SHOX\n"
    )
    rows = [
        f"{_X_KEY},rs137852556,X,640851,C,T,GRCh38,0,ensembl-rest,resolved",
    ]
    if keep_y:
        rows.append(f"{_Y_KEY},rs137852556,Y,640851,C,T,GRCh38,1,ensembl-rest,resolved")
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        + "\n".join(rows) + "\n"
    )
    return spec


def _handler(request: httpx.Request) -> httpx.Response:
    """gnomAD's real behaviour: the X spelling resolves, the Y spelling is simply not there."""
    recorded = json.loads((_ASSETS / "gnomad_v4.1_variant_payload.json").read_text())["data"]
    query = json.loads(request.content)["query"]
    data = {}
    asked: list[str] = []
    for index, line in enumerate(ln for ln in query.splitlines() if "variant(" in ln):
        asked.append(line)
        # The recorded sickle payload stands in for "a covered locus with real counts"; only the
        # covered/not-covered distinction is under test here, not the numbers.
        data[f"v{index}"] = recorded["sickle"] if "X-640851" in line else None
    _handler.asked = asked  # type: ignore[attr-defined]
    return httpx.Response(200, json={"data": data})


def test_a_y_par_locus_is_recorded_as_not_covered(tmp_path: Path) -> None:
    result = enrich_frequencies(_spec(tmp_path), client=_mock_client(_handler))
    by_status: dict[str, set[str]] = {}
    for row in result.rows:
        by_status.setdefault(row.status, set()).add(row.variant_key)

    assert by_status["not_covered"] == {_Y_KEY}
    assert _X_KEY in by_status["resolved"]
    # The defect, stated as an assertion: the Y locus must NOT be recorded as an absence.
    assert _Y_KEY not in by_status.get("not_found", set())


def test_an_uncovered_locus_is_not_counted_as_missing(tmp_path: Path) -> None:
    """`missing` means "asked and absent" and feeds the strict gate. Folding an unaskable locus into it
    would make a pseudoautosomal module fail `strict` for a reason no authored edit could fix."""
    result = enrich_frequencies(_spec(tmp_path), client=_mock_client(_handler))
    assert result.uncovered == [_Y_KEY]
    assert _Y_KEY not in result.missing


def test_strict_mode_does_not_refuse_over_an_uncovered_locus(tmp_path: Path) -> None:
    result = enrich_frequencies(_spec(tmp_path), mode="strict", client=_mock_client(_handler))
    assert result.uncovered == [_Y_KEY]


def test_an_uncovered_locus_is_never_even_asked_about(tmp_path: Path) -> None:
    """gnomAD allows 10 requests per IP per minute, so a question with no possible answer is a slot
    spent for nothing — and asking is what produced the false absence in the first place."""
    enrich_frequencies(_spec(tmp_path), client=_mock_client(_handler))
    asked = "\n".join(_handler.asked)  # type: ignore[attr-defined]
    assert "X-640851-C-T" in asked
    assert "Y-640851-C-T" not in asked


def test_a_genuine_absence_is_still_recorded_as_a_fact(tmp_path: Path) -> None:
    """Without this the fix would be indistinguishable from deleting the `not_found` branch. A covered
    locus gnomAD has no allele for is a real finding about a real callset."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs137852556,C/T,risk,c,SHOX\n"
    )
    # An X-PAR locus gnomAD covers but (per the handler) has no record of.
    key = derive_vrs_allele_id("X", 641037, "C", "A")
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        f"{key},rs137852552,X,641037,C,A,GRCh38,0,ensembl-rest,resolved\n"
    )
    result = enrich_frequencies(spec, client=_mock_client(_handler))
    assert [r.status for r in result.rows] == ["not_found"]
    assert result.missing == [key] and not result.uncovered


def test_the_report_names_the_reason_once(tmp_path: Path, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.frequencies"):
        enrich_frequencies(_spec(tmp_path), client=_mock_client(_handler))
    lines = [r.getMessage() for r in caplog.records if "not_covered" in r.getMessage()]
    assert len(lines) == 1
    assert "Y:640851 C>T" in lines[0]
    assert "hard-masks" in lines[0] and "unknown, not a zero" in lines[0]


def test_selecting_the_x_spelling_leaves_nothing_uncovered(tmp_path: Path) -> None:
    """The two halves of RM32 meeting: once the resolver records only the X locus, the frequency pass
    has no masked locus to reason about at all."""
    result = enrich_frequencies(_spec(tmp_path, keep_y=False), client=_mock_client(_handler))
    assert not result.uncovered
    assert {r.status for r in result.rows} == {"resolved"}


# ── the vocabulary ──────────────────────────────────────────────────────────────────────────────


def test_the_status_column_is_a_closed_vocabulary_now() -> None:
    """It was free text on a fact table until 0.5.1."""
    assert VALID_FREQUENCY_STATUS == {"resolved", "not_found", "not_covered"}
    valid = {"variant_key": "x", "population": "global", "dataset": "gnomad_v4.1_joint"}
    for member in VALID_FREQUENCY_STATUS:
        assert FrequencyRow(**valid, status=member).status == member
    # `ambiguous` is a resolution-table member and has no meaning for one allele in one population.
    with pytest.raises(ValueError, match=r"status must be one of"):
        FrequencyRow(**valid, status="ambiguous")
    # Absent stays absent — a hand-written table need not carry provenance at all.
    assert FrequencyRow(**valid).status is None
