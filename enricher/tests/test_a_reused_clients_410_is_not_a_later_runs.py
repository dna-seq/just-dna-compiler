"""RM446: a withholding client's `retired` outlives the run that met the 410; the reason a run records must not.

`Withholding.retired` is sticky for the client's life (RM361: a retired route is a fact about the source).
A caller may reuse one client across runs, and RM404's `LookupClients` makes that the designed path, so
before this item run 1's 410 told run 2's timeout to upgrade and that a re-run would not help. Each run
now reads the client's `retired_met` before it asks and compares after; the client is never reset.
"""

import logging
from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_enricher.enrich import enrich, orchestration
from just_dna_enricher.literature import CrossrefClient
from just_dna_enricher.net import RETIRED, UNREACHABLE, PacingGate, Withholding, retired_mark, withheld_reason
from just_dna_enricher.sequences import SequenceProxy

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: rm446\n  title: RM446\n  description: d\n  report_title: RM446\n"
)
_RSID = "rs646776"
_RETIRED_WORDS = "because it retired the route"
_OUTAGE_WORDS = "the request failed, so the answer is unchecked rather than empty"


def _gone() -> httpx.Response:
    return httpx.Response(
        410, text="gone", request=httpx.Request("GET", "https://rest.ensembl.org/variation")
    )


class _Resolver(Withholding):
    """Live Ensembl as a caller's reused resolver: a 410 while `gone`, else a failed request (`None`)."""

    def __init__(self) -> None:
        self.gone = True

    def resolve_rsid(self, rsid: str):
        if self.gone:
            self.note_retired("Ensembl REST", _gone())
        return None, None

    def close(self) -> None:
        return None


def _spec(root: Path) -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        f"rsid,genotype,state,conclusion,gene\n{_RSID},A/C,risk,c,CELSR2\n", encoding="utf-8"
    )
    return spec


def _snapshot_without_the_rsid(root: Path) -> Path:
    """A snapshot that holds another rsID only, so the run asks live Ensembl for this one."""
    (root / "ens" / "data").mkdir(parents=True)
    rows = {"id": ["rs4970836"], "chrom": ["1"], "start": [109279544], "ref": ["G"], "alt": ["A"]}
    pl.DataFrame(rows).write_parquet(root / "ens" / "data" / "homo_sapiens-chr1.parquet")
    return root / "ens"


def _run(root: Path, resolver: _Resolver, caplog: pytest.LogCaptureFixture) -> str:
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher"):
        enrich(
            _spec(root),
            ensembl_cache=_snapshot_without_the_rsid(root),
            clinvar_cache=root / "no-clinvar",
            offline=False,
            download=False,
            resolver=resolver,
            use_gnomad=False,
            verify_ref=False,
            verify_rsids=False,
            verify_clinsig=False,
            verify_datasets=False,
            mint_vrs=False,
        )
    return caplog.text


def test_a_reused_resolvers_earlier_410_does_not_make_this_runs_outage_a_retirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(orchestration, "SequenceProxy", lambda **kw: SequenceProxy(offline=True))
    resolver = _Resolver()
    first = _run(tmp_path / "one", resolver, caplog)
    assert _RETIRED_WORDS in first and _OUTAGE_WORDS not in first

    resolver.gone = False  # run 2 meets only a failed request
    second = _run(tmp_path / "two", resolver, caplog)
    assert _OUTAGE_WORDS in second and _RETIRED_WORDS not in second
    assert resolver.retired, "the client still says what it met: it is never reset"

    resolver.gone = True  # a 410 met again in run 3 is that run's own
    third = _run(tmp_path / "three", resolver, caplog)
    assert _RETIRED_WORDS in third and _OUTAGE_WORDS not in third


def test_the_reason_since_a_mark_counts_only_the_410s_met_after_it() -> None:
    client = CrossrefClient(gate=PacingGate(0.0))
    replies = iter([_gone(), httpx.Response(503, text="busy"), _gone()])
    client._client = httpx.Client(transport=httpx.MockTransport(lambda request: next(replies)))
    client.exists("10.1038/ng826")
    assert withheld_reason(client) == RETIRED
    mark = retired_mark(client)
    client.exists("10.1038/ng826")
    assert withheld_reason(client) == RETIRED, "without a mark: the client's life, as RM361 has it"
    assert withheld_reason(client, since=mark) == UNREACHABLE
    client.exists("10.1038/ng826")
    assert withheld_reason(client, since=mark) == RETIRED


def test_a_client_that_counts_nothing_reads_as_before() -> None:
    """A host's own client, written before the counter, has no mark: `retired` for its life."""

    class _Hosts:
        retired = "gone"

    assert retired_mark(_Hosts()) is None
    assert withheld_reason(_Hosts(), since=None) == RETIRED
    assert withheld_reason(object(), since=None) == UNREACHABLE
