"""The computed LD pair behind a proxy-measured study (RM331, PT2 §5 D3).

`StudyRow.proxy_rsid` names the variant a study measured in place of the row's lead; the author writes
only that. r² means nothing without its population, so the pair is computed: `ld-pairs` asks Ensembl
REST's pairwise endpoint for r² between proxy and lead in the study's own `ancestry` (a 1000 Genomes
phase 3 superpopulation) and writes `ld_pairs.csv`, keyed `(proxy_rsid, variant_key, ld_population)`.

Every response here is one recorded from rest.ensembl.org on 2026-11-04 (release 116), verbatim, and
served through `httpx.MockTransport` so the client's real parsing, retry and translation run
(docs/probes/LANES_0_8.md §2 and §6):

* EUR, rs4970836 against rs646776: one row, r² and D′ as JSON strings;
* AFR, rs2075650 against rs429358 (the APOE pair): `200 []`, which is withheld, never r² = 0;
* rs999999999999: `400 {"error": "Could not fetch variation object …"}`, an answer, not an outage;
* rs1624712 (a synonym of rs646776): an HTML `500` first, then a `200` naming `rs646776`.

The spec is the longevitymap v2 case `test_study_proxy_subjects.py` already resolves offline: lead
rs646776, proxy rs4970836, the snapshot rows as the provisioned Ensembl cache carries them.
"""

import csv
import os
from collections.abc import Callable
from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module
from just_dna_enricher.enrich import enrich
from just_dna_enricher.ld_pairs import (
    LD_POPULATION_PREFIX,
    LdClient,
    LdError,
    LdUnavailable,
    enrich_ld_pairs,
)
from just_dna_enricher.licensing import read_sources_file
from just_dna_enricher.net import PacingGate
from just_dna_format.ld_pairs import LdPairRow
from just_dna_format.vocab import VALID_LD_PAIR_STATUS

_MODULE = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)

#: The recorded bodies, verbatim (2026-11-04, rest.ensembl.org, release 116).
_EUR = (
    '[{"d_prime":"0.975903","population_name":"1000GENOMES:phase_3:EUR","variation1":"rs4970836",'
    '"r2":"0.924767","variation2":"rs646776"}]'
)
_SYNONYM = (
    '[{"r2":"0.924767","variation2":"rs4970836","variation1":"rs646776",'
    '"population_name":"1000GENOMES:phase_3:EUR","d_prime":"0.975903"}]'
)
_EMPTY = "[]"
_UNKNOWN = '{"error":"Could not fetch variation object for id: rs999999999999."}'
_HTML_500 = (
    '<!doctype html>\n<html lang="en" class="vf-no-js">\n  <head>\n'
    "    <title>Error: 500 | EMBL’s European Bionformatics Institute</title>\n"
    '<h1 class="vf-intro__heading ">Error: 500</h1>\n<p class="vf-lede">There was a technical error.</p>\n'
)
_RELEASE = '{"releases":[116]}'


def _spec(tmp_path: Path, studies: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_MODULE)
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs646776,G/G,protective,c\n")
    (spec / "studies.csv").write_text(studies)
    return spec


_ONE_EUR_STUDY = "rsid,pmid,proxy_rsid,ancestry,effect_allele\nrs646776,30642433,rs4970836,EUR,A\n"


class _Ensembl:
    """A recorded Ensembl: each path answers from a queue of `(status, body, content-type)`."""

    def __init__(self, answers: dict[str, list[tuple[int, str, str]]]) -> None:
        self.answers = answers
        self.asked: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/info/data":
            return httpx.Response(200, text=_RELEASE, headers={"content-type": "application/json"})
        self.asked.append(f"{path}?{request.url.query.decode()}")
        queue = self.answers[path]
        status, body, kind = queue.pop(0) if len(queue) > 1 else queue[0]
        return httpx.Response(status, text=body, headers={"content-type": kind})


def _json(status: int, body: str) -> tuple[int, str, str]:
    return status, body, "application/json"


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> LdClient:
    return LdClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        gate=PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None),
    )


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry count is the contract; tenacity's wall-clock back-off is not."""
    monkeypatch.setattr("time.sleep", lambda _s: None)


def _rows(spec: Path) -> list[dict[str, str]]:
    with (spec / "ld_pairs.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def _sources(spec: Path) -> list[tuple[str, str, str | None]]:
    return [(r.source, r.layer, r.dataset) for r in read_sources_file(spec)]


def test_a_single_ancestry_study_gets_r2_in_its_own_superpopulation(tmp_path: Path) -> None:
    spec = _spec(tmp_path, _ONE_EUR_STUDY)
    ensembl = _Ensembl({"/ld/human/pairwise/rs4970836/rs646776": [_json(200, _EUR)]})
    result = enrich_ld_pairs(spec, client=_client(ensembl))

    # The proxy first, so `variation1` is the proxy as Ensembl names it; the population spelled by us,
    # since `?filter=LD` does not list the five superpopulations (LANES §2.2).
    assert ensembl.asked == [
        "/ld/human/pairwise/rs4970836/rs646776?population_name=1000GENOMES%3Aphase_3%3AEUR"
    ]
    [row] = result.rows
    assert (row.proxy_rsid, row.variant_key, row.ld_population) == (
        "rs4970836",
        "rs646776",
        f"{LD_POPULATION_PREFIX}EUR",
    )
    assert (row.status, row.r2, row.d_prime, row.answered_rsid) == (
        "resolved",
        0.924767,
        0.975903,
        "rs4970836",
    )
    assert (row.dataset, row.source) == ("ensembl_116", "ensembl")
    # The CSV spells the source's six decimals back exactly: str(float) is the shortest round trip.
    [written] = _rows(spec)
    assert (written["r2"], written["d_prime"]) == ("0.924767", "0.975903")


def test_the_licence_row_commits_with_the_table_at_its_own_layer(tmp_path: Path) -> None:
    spec = _spec(tmp_path, _ONE_EUR_STUDY)
    enrich_ld_pairs(
        spec, client=_client(_Ensembl({"/ld/human/pairwise/rs4970836/rs646776": [_json(200, _EUR)]}))
    )
    assert _sources(spec) == [("ensembl", "ld_pair", "ensembl_116")]


def test_an_empty_answer_is_withheld_never_written_as_zero(tmp_path: Path) -> None:
    """`200 []` comes back for two chromosomes and for the APOE pair in AFR (ASW alone says 0.0635), and
    lowering the `r2` floor does not bring a row back: below a floor, or not in LD — unknown which."""
    spec = _spec(tmp_path, "rsid,pmid,proxy_rsid,ancestry\nrs646776,30642433,rs4970836,AFR\n")
    ensembl = _Ensembl({"/ld/human/pairwise/rs4970836/rs646776": [_json(200, _EMPTY)]})
    [row] = enrich_ld_pairs(spec, client=_client(ensembl)).rows
    assert (row.status, row.r2, row.d_prime, row.answered_rsid) == ("not_reported", None, None, None)
    assert row.ld_population == f"{LD_POPULATION_PREFIX}AFR"
    [written] = _rows(spec)
    assert (written["r2"], written["d_prime"]) == ("", "")


def test_an_unknown_rsid_is_an_answer_and_not_an_outage(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "rsid,pmid,proxy_rsid,ancestry\nrs646776,30642433,rs999999999999,EUR\n")
    ensembl = _Ensembl({"/ld/human/pairwise/rs999999999999/rs646776": [_json(400, _UNKNOWN)]})
    [row] = enrich_ld_pairs(spec, client=_client(ensembl)).rows
    assert (row.status, row.r2) == ("rsid_unknown", None)
    # Asked once: a 400 is the service answering, so it is neither retried nor read as unreachable.
    assert len(ensembl.asked) == 1


def test_an_html_500_is_retried_and_a_renamed_proxy_is_recorded(tmp_path: Path) -> None:
    """The probe's flake, recorded live: an EBI HTML error page, then the answer, naming the synonym's
    current id. The row stays keyed on the rsID the author wrote; `answered_rsid` says who answered."""
    spec = _spec(tmp_path, "rsid,pmid,proxy_rsid,ancestry\nrs4970836,30642433,rs1624712,EUR\n")
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs4970836,A/A,protective,c\n")
    ensembl = _Ensembl(
        {
            "/ld/human/pairwise/rs1624712/rs4970836": [
                (500, _HTML_500, "text/html"),
                _json(200, _SYNONYM),
            ]
        }
    )
    [row] = enrich_ld_pairs(spec, client=_client(ensembl)).rows
    assert len(ensembl.asked) == 2
    assert (row.proxy_rsid, row.answered_rsid, row.r2) == ("rs1624712", "rs646776", 0.924767)


@pytest.mark.parametrize(
    "ancestry,status",
    [("EUR;EAS", "ancestry_mixed"), ("", "ancestry_unstated")],
    ids=["mixed", "unstated"],
)
def test_a_study_with_no_single_superpopulation_gets_its_row_with_r2_withheld(
    tmp_path: Path, ancestry: str, status: str
) -> None:
    """The pm's setting: the lookup never picks a panel for a mixed-ancestry study. Unknown, not zero —
    and no source was consulted, so no licence row is written either (`@write-the-sourcerow`)."""
    spec = _spec(tmp_path, f'rsid,pmid,proxy_rsid,ancestry\nrs646776,30642433,rs4970836,"{ancestry}"\n')
    ensembl = _Ensembl({})
    result = enrich_ld_pairs(spec, client=_client(ensembl))
    assert ensembl.asked == []
    [row] = result.rows
    assert (row.status, row.ld_population, row.r2, row.source, row.dataset) == (
        status,
        None,
        None,
        None,
        None,
    )
    assert _sources(spec) == []


def test_a_mixed_and_a_single_ancestry_study_of_one_pair_are_two_rows(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path,
        "rsid,pmid,proxy_rsid,ancestry\n"
        "rs646776,30642433,rs4970836,EUR\n"
        'rs646776,31413261,rs4970836,"EUR;EAS"\n',
    )
    ensembl = _Ensembl({"/ld/human/pairwise/rs4970836/rs646776": [_json(200, _EUR)]})
    result = enrich_ld_pairs(spec, client=_client(ensembl))
    assert sorted((r.ld_population or "", r.status) for r in result.rows) == [
        ("", "ancestry_mixed"),
        (f"{LD_POPULATION_PREFIX}EUR", "resolved"),
    ]


def test_a_lead_with_no_rsid_is_withheld_with_its_reason(tmp_path: Path) -> None:
    """The pairwise endpoint takes rsIDs only. A coordinate-authored lead with no back-filled rsID in
    `resolution.csv` has nothing to send, which is a reason on the row, not a silence."""
    spec = _spec(tmp_path, "chrom,start,ref,pmid,proxy_rsid,ancestry\n1,109275908,C,30642433,rs4970836,EUR\n")
    ensembl = _Ensembl({})
    [row] = enrich_ld_pairs(spec, client=_client(ensembl)).rows
    assert ensembl.asked == []
    assert (row.status, row.variant_key, row.ld_population) == (
        "lead_has_no_rsid",
        "1:109275908:C",
        f"{LD_POPULATION_PREFIX}EUR",
    )


def test_offline_asks_nothing_and_writes_nothing(tmp_path: Path) -> None:
    spec = _spec(tmp_path, _ONE_EUR_STUDY)
    ensembl = _Ensembl({})
    result = enrich_ld_pairs(spec, offline=True, client=_client(ensembl))
    assert result.skipped_offline and ensembl.asked == [] and result.rows == []
    assert result.unasked == [("rs4970836", "rs646776", f"{LD_POPULATION_PREFIX}EUR")]
    assert not (spec / "ld_pairs.csv").exists()


def test_a_rerun_asks_nothing_and_rewrites_the_same_bytes(tmp_path: Path) -> None:
    """Merge, never clobber (`@sidecar-authoritative`): a recorded pair is not asked twice."""
    spec = _spec(tmp_path, _ONE_EUR_STUDY)
    enrich_ld_pairs(
        spec, client=_client(_Ensembl({"/ld/human/pairwise/rs4970836/rs646776": [_json(200, _EUR)]}))
    )
    first = (spec / "ld_pairs.csv").read_bytes()
    again = _Ensembl({})
    result = enrich_ld_pairs(spec, client=_client(again))
    assert again.asked == [] and result.requests == 0
    assert (spec / "ld_pairs.csv").read_bytes() == first


def test_an_unreachable_ensembl_writes_no_row_for_the_pair(tmp_path: Path) -> None:
    """Could-not-ask is not absent (`@unreachable-not-absent`): no row, and the pass's own type."""
    spec = _spec(tmp_path, _ONE_EUR_STUDY)
    down = _Ensembl({"/ld/human/pairwise/rs4970836/rs646776": [_json(503, '{"error":"busy"}')]})
    with pytest.raises(LdUnavailable) as caught:
        enrich_ld_pairs(spec, client=_client(down))
    assert isinstance(caught.value, LdError)
    assert len(down.asked) >= 3, "a 503 is retried before it is translated"
    assert not (spec / "ld_pairs.csv").exists()


def _snapshot(tmp_path: Path) -> Path:
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs646776", "rs4970836"],
            "chrom": ["1", "1"],
            "start": [109275908, 109279175],
            "ref": ["C", "G"],
            "alt": ["G|T", "A|C"],
        }
    ).write_parquet(data / "chr1.parquet")
    return tmp_path / "cache"


def test_the_table_compiles_reverses_and_recompiles_to_the_same_digest(tmp_path: Path) -> None:
    """Principle 7 on the real paths: enrich offline from the snapshot, the LD pass, compile → reverse →
    compile. The derived table is outside `content_signature` and inside `artifact.digest`."""
    spec = _spec(
        tmp_path,
        "rsid,pmid,proxy_rsid,ancestry,effect_allele\n"
        "rs646776,30642433,rs4970836,EUR,A\n"
        'rs646776,31413261,rs4970836,"AFR;EUR",A\n',
    )
    enrich(spec, offline=True, ensembl_cache=_snapshot(tmp_path), clinvar_cache=tmp_path, mint_vrs=False)
    enrich_ld_pairs(
        spec, client=_client(_Ensembl({"/ld/human/pairwise/rs4970836/rs646776": [_json(200, _EUR)]}))
    )

    first = compile_module(spec, tmp_path / "out1", strict=True)
    assert first.success, first.errors
    table = pl.read_parquet(tmp_path / "out1" / "ld_pairs.parquet")
    assert table.height == 2
    assert table.filter(pl.col("status") == "resolved")["r2"].to_list() == [0.924767]
    assert first.manifest.ld_pairs is not None
    assert (first.manifest.ld_pairs.row_count, first.manifest.ld_pairs.with_r2) == (2, 1)

    reversed_dir = tmp_path / "reversed"
    reverse_module(tmp_path / "out1", reversed_dir)
    assert (reversed_dir / "ld_pairs.csv").exists() or (reversed_dir / "derived" / "ld_pairs.csv").exists()
    second = compile_module(reversed_dir, tmp_path / "out2", strict=True)
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.compilation.resolution_signature == first.manifest.compilation.resolution_signature
    assert content_signature(reversed_dir) == content_signature(spec)
    assert second.manifest.ld_pairs == first.manifest.ld_pairs
    assert pl.read_parquet(tmp_path / "out2" / "ld_pairs.parquet").equals(table)


def test_the_status_vocabulary_is_the_arms_the_pass_can_reach() -> None:
    """Each member is a sentence a reader meets on a row; a member no arm writes would be a word with
    no case, and an arm writing an undeclared one is refused by the model."""
    assert VALID_LD_PAIR_STATUS == {
        "resolved",
        "not_reported",
        "rsid_unknown",
        "ancestry_mixed",
        "ancestry_unstated",
        "lead_has_no_rsid",
    }
    with pytest.raises(ValueError):
        LdPairRow(proxy_rsid="rs1", variant_key="rs2", ld_population="x", status="zero")
    # The table exists to refuse a zero standing in for "not reported", and a population-less row
    # pretending to be an answer.
    with pytest.raises(ValueError, match="r2 is set exactly when status is resolved"):
        LdPairRow(proxy_rsid="rs1", variant_key="rs2", ld_population="x", status="not_reported", r2=0.0)
    with pytest.raises(ValueError, match="a population is named exactly when"):
        LdPairRow(proxy_rsid="rs1", variant_key="rs2", status="resolved", r2=0.5)


@pytest.mark.skipif(
    not os.getenv("JUST_DNA_NETWORK_TESTS"), reason="set JUST_DNA_NETWORK_TESTS=1 to hit Ensembl"
)
def test_live_ensembl_answers_the_longevitymap_pair_in_eur(tmp_path: Path) -> None:
    """rs646776 / rs4970836 in EUR, asked of the live service. The value is release-specific, so the
    assertion is the shape: resolved, high LD, the population spelled, the release recorded."""
    spec = _spec(tmp_path, _ONE_EUR_STUDY)
    [row] = enrich_ld_pairs(spec).rows
    assert row.status == "resolved" and row.r2 is not None and 0.9 < row.r2 <= 1.0
    assert row.ld_population == f"{LD_POPULATION_PREFIX}EUR" and row.answered_rsid == "rs4970836"
    assert row.dataset is not None and row.dataset.startswith("ensembl_")
