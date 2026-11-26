"""RM404: `enrich()` takes a caller's network clients (`clients=`) and sequence proxy (`sequences=`).

A host running modules in parallel holds one paced bundle and one sequence proxy, and until 0.9 `enrich`
built its own NCBI client and its own `SequenceProxy` per call, so neither could be shared: the registry
ran its enrichments one at a time for it (S133), and a local seqrepo could not be handed in with the
network up (S157). What these tests pin, each against the real run:

* every client the bundle carries that `enrich` reads is the one asked, and none of them is closed by
  `enrich` (the caller holds them); an explicit `resolver=`/`gnomad_client=`/`grch37_client=` wins over
  the bundle's field; a field left unset is built and closed by `enrich`, never stored on the bundle;
* a passed proxy is the only sequence source the run reads, the live link's anchor reads included;
* under `offline=True` the passed proxy is not used, and the run says so once;
* threads sharing one proxy each get the bases while its data proxy is still being built;
* a shared proxy memoizes answers only: a failure is held by the run that saw it, and its memo is bounded;
* `EnsemblSettings.batch_size` above Ensembl's ceiling or below 1, and a `batch_timeout` of zero or less, are
  refused at construction, never clamped.
"""

import logging
import re
import shutil
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.clients import LookupClients
from just_dna_enricher.clinvar_build import build_snapshot as build_clinvar
from just_dna_enricher.enrich import EnrichmentError, _write_resolution_csv, enrich
from just_dna_enricher.enrich.orchestration import OFFLINE_OUTRANKS_SEQUENCES, _RecordedEutils
from just_dna_enricher.ensembl import BatchResolver, EnsemblResolver, EnsemblSettings, RsidAnswer
from just_dna_enricher.eutils import EutilsClient, EutilsSettings
from just_dna_enricher.net import PacingGate
from just_dna_enricher.sequences import (
    _MEMO_SIZE,
    SequenceProxy,
    _held_by_one_run,
    verify_reference_alleles,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.verification import read_verification

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
#: rs1801133 is rsID-only, so the live link is asked about it; rs429358 authors both halves.
_PLACED = {"rs1801133": ("1", 11796321, "G", "A")}


_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_REFERENCE_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _spec(root: Path) -> Path:
    spec = root / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,chrom,start,ref,genotype,state,conclusion\n"
        "rs1801133,,,,A/G,risk,c\n"
        "rs429358,19,44908684,T,C/T,risk,c\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,9545397\n", encoding="utf-8")
    return spec


class _Resolver:
    """A host's resolver: `resolve_rsid` alone. `places=False` answers "no locus", so gnomAD is asked."""

    def __init__(self, places: bool = True) -> None:
        self.places = places
        self.asked: list[str] = []
        self.closed = 0

    def resolve_rsid(self, rsid: str) -> RsidAnswer:
        self.asked.append(rsid)
        if not self.places or rsid not in _PLACED:
            return [], "ensembl-rest"
        chrom, start, ref, alt = _PLACED[rsid]
        return [{"chrom": chrom, "start": start, "ref": ref, "alts": alt}], "ensembl-rest"

    def close(self) -> None:
        self.closed += 1


class _Gnomad:
    """gnomAD's last-resort link, the shape `GnomadClient.resolve_rsids` has."""

    unanswered: dict = {}

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.closed = 0

    def resolve_rsids(self, rsids: list[str]) -> dict[str, list[dict]]:
        self.asked.extend(rsids)
        out: dict[str, list[dict]] = {}
        for rsid in rsids:
            if rsid in _PLACED:
                chrom, start, ref, alt = _PLACED[rsid]
                out[rsid] = [{"chrom": chrom, "start": start, "ref": ref, "alts": alt}]
        return out

    def close(self) -> None:
        self.closed += 1


class _Grch37:
    """The GRCh37 service, asked only about a ref-mismatched row; it answers nothing, so rows are unchecked."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, int, int]] = []
        self.closed = 0

    def reference_bases(self, chrom: str, start: int, end: int) -> str | None:
        self.asked.append((chrom, start, end))
        return None

    def close(self) -> None:
        self.closed += 1


def _dbsnp_handler(asked: list[list[str]]):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "eutils.ncbi.nlm.nih.gov", f"asked {request.url}, not NCBI"
        ids = request.url.params["id"].split(",")
        asked.append(ids)
        result: dict[str, object] = {"uids": ids}
        for uid in ids:
            result[uid] = {"uid": uid, "snp_id": int(uid)}
        return httpx.Response(200, json={"result": result})

    return handler


class _CallerEutils(EutilsClient):
    """A caller's NCBI client over a recorded transport, counting `close()`."""

    closes: int = 0

    def close(self) -> None:
        self.closes += 1
        super().close()


def _caller_eutils(asked: list[list[str]]) -> _CallerEutils:
    client = _CallerEutils(settings=EutilsSettings(email=None), gate=PacingGate(0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(_dbsnp_handler(asked)))
    return client


class _Bases(SequenceProxy):
    """A proxy answering every read with one base, and counting each read; `proxy()` is a stand-in."""

    def __init__(self, base: str = "A") -> None:
        super().__init__()
        self.base = base
        self.reads = 0

    def proxy(self):
        self.reads += 1
        return self

    def subsequence(self, accession: str, start: int, end: int) -> str | None:
        self.reads += 1
        return self.base * (end - start)


def _online(spec: Path, root: Path, **kwargs):
    options = {
        "ensembl_cache": root / "no-snapshot",
        "clinvar_cache": root / "no-snapshot",
        "download": False,
        "use_gnomad": False,
        "mint_vrs": False,
        "verify_ref": False,
        "verify_rsids": False,
        "verify_clinsig": False,
        "verify_datasets": False,
    }
    options.update(kwargs)
    return enrich(spec, **options)


# ── the bundle ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("no_ambient_caches")
def test_every_bundle_client_enrich_reads_is_the_one_asked_and_none_is_closed(tmp_path: Path) -> None:
    """One run that really calls each of the four fields `enrich` reads: ensembl, gnomad, grch37, eutils."""
    spec = _spec(tmp_path)
    asked: list[list[str]] = []
    clients = LookupClients(
        ensembl=_Resolver(places=False), gnomad=_Gnomad(), grch37=_Grch37(), eutils=_caller_eutils(asked)
    )
    result = _online(
        spec,
        tmp_path,
        clients=clients,
        use_gnomad=True,
        verify_rsids=True,
        verify_ref=True,
        sequences=_Bases("A"),  # every authored and resolved ref mismatches "A", so GRCh37 is asked
    )
    assert clients.ensembl.asked == ["rs1801133"]
    assert clients.gnomad.asked == ["rs1801133"]
    assert clients.grch37.asked  # the mismatched rows, under the diagnosis limit
    assert sorted(uid for request in asked for uid in request) == ["1801133", "429358"]
    assert {r.rsid: r.rsid_status for r in result.rows} == {"rs1801133": "live", "rs429358": "live"}
    # The caller holds them: `enrich` closes none, and the NCBI client's transport is still open.
    assert (clients.ensembl.closed, clients.gnomad.closed, clients.grch37.closed) == (0, 0, 0)
    assert clients.eutils.closes == 0 and clients.eutils._client is not None


@pytest.mark.usefixtures("no_ambient_caches")
@pytest.mark.parametrize("field", ["ensembl", "gnomad", "grch37"])
def test_an_explicit_client_wins_over_the_bundles_field(tmp_path: Path, field: str) -> None:
    factory = {"ensembl": lambda: _Resolver(places=False), "gnomad": _Gnomad, "grch37": _Grch37}[field]
    kwarg = {"ensembl": "resolver", "gnomad": "gnomad_client", "grch37": "grch37_client"}[field]
    explicit, bundled = factory(), factory()
    others = {"ensembl": _Resolver(places=False), "gnomad": _Gnomad(), "grch37": _Grch37()}
    clients = LookupClients(**{**others, field: bundled})
    _online(
        _spec(tmp_path),
        tmp_path,
        clients=clients,
        use_gnomad=True,
        verify_ref=True,
        sequences=_Bases("A"),
        **{kwarg: explicit},
    )
    assert explicit.asked and not bundled.asked
    assert (explicit.closed, bundled.closed) == (0, 0)


@pytest.mark.usefixtures("no_ambient_caches")
def test_an_unset_eutils_field_is_built_and_closed_by_enrich_and_never_stored_on_the_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The non-mutating reading: `enrich` does not call `clients.ensure`, so the bundle stays as passed."""
    asked: list[list[str]] = []
    built: list[_RecordedEutils] = []

    class _Owned(_RecordedEutils):
        closes: int = 0

        def close(self) -> None:
            self.closes += 1
            super().close()

    def dbsnp_client(inner: EutilsClient | None = None) -> _RecordedEutils:
        assert inner is None, "an unset field must not reach the wrapper as a caller's client"
        client = _Owned(settings=EutilsSettings(email=None), gate=PacingGate(0.0))
        client._client = httpx.Client(transport=httpx.MockTransport(_dbsnp_handler(asked)))
        built.append(client)
        return client

    monkeypatch.setattr("just_dna_enricher.enrich.orchestration._dbsnp_client", dbsnp_client)
    clients = LookupClients(ensembl=_Resolver())
    _online(_spec(tmp_path), tmp_path, clients=clients, verify_rsids=True)
    assert clients.eutils is None
    (owned,) = built
    assert owned.closes == 1 and asked


def test_the_wrapper_fetches_each_record_once_through_the_callers_client_and_never_closes_it() -> None:
    asked: list[list[str]] = []
    caller = _caller_eutils(asked)
    wrapper = _RecordedEutils(inner=caller)
    wrapper.esummary("snp", ["1", "2"])
    wrapper.esummary("snp", ["2", "3"])
    assert asked == [["1", "2"], ["3"]]
    wrapper.close()
    assert caller.closes == 0 and caller._client is not None


# ── the sequence proxy ──────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("no_ambient_caches")
def test_the_live_link_enrich_builds_anchors_through_the_passed_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The resolver `enrich` builds reads an indel's anchor base; with a proxy passed, through that one."""

    def no_second_proxy(*_args, **_kwargs):
        raise AssertionError("a second SequenceProxy was built")

    class _Anchoring(EnsemblResolver):
        def resolve_rsids_batched(self, rsids: Sequence[str]) -> Iterator[tuple[str, RsidAnswer]]:
            for rsid in rsids:
                self._base_reader()("1", 11796321)
                yield rsid, (None, None)

    monkeypatch.setattr("just_dna_enricher.ensembl.SequenceProxy", no_second_proxy)
    monkeypatch.setattr("just_dna_enricher.enrich.orchestration.EnsemblResolver", _Anchoring)
    passed = _Bases("G")
    _online(_spec(tmp_path), tmp_path, sequences=passed)
    assert passed.reads == 1


@pytest.mark.usefixtures("no_ambient_caches")
def test_offline_outranks_a_passed_proxy_which_is_not_read_and_the_run_says_so_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    bare_root, passed_root = tmp_path / "bare", tmp_path / "passed"
    bare_root.mkdir()
    passed_root.mkdir()
    bare = _online(_spec(bare_root), bare_root, offline=True, verify_ref=True, mint_vrs=True)
    passed = _Bases("A")
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher"):
        result = _online(
            _spec(passed_root), passed_root, offline=True, verify_ref=True, mint_vrs=True, sequences=passed
        )
    assert passed.reads == 0
    assert [r.getMessage() for r in caplog.records].count(OFFLINE_OUTRANKS_SEQUENCES) == 1
    assert OFFLINE_OUTRANKS_SEQUENCES == (
        "enrich(offline=True) does not use the sequence proxy passed as `sequences`: offline outranks it, "
        "as it outranks an injected client, so this run reads no reference sequence (RM404)."
    )
    assert [r.model_dump() for r in result.rows] == [r.model_dump() for r in bare.rows]
    assert (passed_root / "spec" / "resolution.csv").read_bytes() == (
        bare_root / "spec" / "resolution.csv"
    ).read_bytes()


def test_threads_sharing_one_proxy_all_get_the_bases_while_its_data_proxy_is_being_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the build under the lock, a second reader saw the build in flight (tried, no proxy yet) and
    read `None`: the base read as unreadable for the rest of a run that shares the proxy."""
    entered, release = threading.Event(), threading.Event()

    class _DataProxy:
        def get_sequence(self, identifier: str, start: int, end: int) -> str:
            return "c" * (end - start)

    def slow_build(_uri: str) -> _DataProxy:
        entered.set()
        release.wait(5)
        return _DataProxy()

    monkeypatch.setattr("just_dna_enricher.sequences.create_dataproxy", slow_build)
    shared = SequenceProxy()
    results: dict[int, str | None] = {}

    def read(start: int) -> None:
        results[start] = shared.subsequence("SQ.test", start, start + 1)

    first = threading.Thread(target=read, args=(0,))
    first.start()
    assert entered.wait(5)
    second = threading.Thread(target=read, args=(1,))
    second.start()
    second.join(0.3)
    release.set()
    first.join(5)
    second.join(5)
    assert results == {0: "C", 1: "C"}
    assert shared.subsequence("SQ.test", 1, 2) == "C"  # and the memo holds the bases, not `None`


class _Backend:
    """`create_dataproxy` and the data proxy it builds, failing in one of three ways until `fails` is cleared.

    `build` raises in `create_dataproxy`; `raise` and `empty` build, then raise in `get_sequence` or answer
    `""`. Every build attempt and every read is recorded, so a test sees what each run asked.
    """

    def __init__(self, fails: str | None) -> None:
        self.fails = fails
        self.builds = 0
        self.reads: list[tuple[str, int, int]] = []

    def create_dataproxy(self, _uri: str) -> "_Backend":
        self.builds += 1
        if self.fails == "build":
            raise ConnectionError("seqrepo is down")
        return self

    def get_sequence(self, identifier: str, start: int, end: int) -> str:
        self.reads.append((identifier, start, end))
        if self.fails == "raise":
            raise ConnectionError("read timed out")
        return "" if self.fails == "empty" else "t" * (end - start)


@pytest.mark.usefixtures("no_ambient_caches")
@pytest.mark.parametrize("fails", ["build", "raise", "empty"])
def test_a_shared_proxy_carries_no_failure_into_the_next_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fails: str
) -> None:
    """The pm (2026-11-17): a shared proxy memoizes answers only, and the run that saw a failure holds it.

    Before, a failed build (`_tried`) or a failed read (a memoized `None`) lasted the proxy's life, so a
    host's second run read the base as unreadable without asking, and its warning's "this run" was false.
    """
    backend = _Backend(fails)
    monkeypatch.setattr("just_dna_enricher.sequences.create_dataproxy", backend.create_dataproxy)
    shared = SequenceProxy()
    first_root, second_root = tmp_path / "first", tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    # A mismatched ref asks GRCh37 for the wrong-build diagnosis, so it gets a stub as well.
    hosts = {"resolver": _Resolver(), "grch37_client": _Grch37(), "verify_ref": True}

    _online(_spec(first_root), first_root, **hosts, sequences=shared)
    first = (backend.builds, list(backend.reads))
    assert first[0] == 1, "the first run asked the service"
    if fails != "build":
        # Within the run a failed read is held: each interval is asked once, however often it is read.
        assert first[1] and len(first[1]) == len(set(first[1]))

    backend.fails = None
    _online(_spec(second_root), second_root, **hosts, sequences=shared)
    asked_again = backend.reads[len(first[1]) :]
    assert asked_again, "the second run asked again rather than reading the first run's failure"
    if fails != "build":
        # What the first run failed on, asked again; a window that answers spares the base read beside it.
        assert set(asked_again) <= set(first[1])
    # And now the answers are held for the proxy's life: a third reader asks nothing.
    seen = len(backend.reads)
    for identifier, start, end in asked_again:
        assert shared.subsequence(identifier.removeprefix("ga4gh:"), start, end) == "T" * (end - start)
    assert len(backend.reads) == seen


@pytest.mark.parametrize("fails", ["build", "raise", "empty"])
def test_one_run_asks_a_failed_read_once(monkeypatch: pytest.MonkeyPatch, fails: str) -> None:
    """The run holds its failures, so a down service costs one attempt per run, not one per read."""
    backend = _Backend(fails)
    monkeypatch.setattr("just_dna_enricher.sequences.create_dataproxy", backend.create_dataproxy)
    rows = [
        ResolutionRow(variant_key=f"k{n}", chrom="19", start=44908684, ref="T", alts="C") for n in range(3)
    ]
    shared = SequenceProxy()
    verify_reference_alleles(rows, sequences=shared)
    first = list(backend.reads)
    assert backend.builds == 1
    # Three rows on one locus: each interval the check reads is asked once, whatever came back.
    assert len(first) == len(set(first)) and (fails == "build") == (not first)
    verify_reference_alleles(rows, sequences=shared)  # a second run asks again, once
    assert backend.builds == (2 if fails == "build" else 1)
    assert backend.reads == first + first


def test_a_failed_build_says_it_is_retried_at_the_next_read(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Review round 2, I: a stock proxy read outside a run's view retries a failed build at every read, so its
    warning may not say the work "is skipped this run", which is not what happens."""
    backend = _Backend("build")
    monkeypatch.setattr("just_dna_enricher.sequences.create_dataproxy", backend.create_dataproxy)
    shared = SequenceProxy()
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.sequences"):
        assert shared.subsequence("SQ.test", 1, 2) is None
        assert shared.subsequence("SQ.test", 1, 2) is None
    assert backend.builds == 2, "each read asked for the build again"
    said = [r.getMessage() for r in caplog.records if r.name == "just_dna_enricher.sequences"]
    assert (
        said
        == [
            f"Could not reach the sequence service at {shared.uri} (seqrepo is down); this read returns no bases, "
            "and the build is retried at the proxy's next read. Without bases an indel's VRS id is left unminted "
            "and the reference-allele check is not made; a run reading through its own view asks for the build "
            "once per run."
        ]
        * 2
    )


def test_a_resolvers_own_proxy_holds_no_failure_either(monkeypatch: pytest.MonkeyPatch) -> None:
    """A host may share one resolver across runs, so its own proxy is read directly: answers only."""
    backend = _Backend("raise")
    monkeypatch.setattr("just_dna_enricher.sequences.create_dataproxy", backend.create_dataproxy)
    resolver = EnsemblResolver()
    assert resolver._base_reader()("1", 11796321) is None
    backend.fails = None
    assert resolver._base_reader()("1", 11796321) == "T"
    assert len(backend.reads) == 2


def test_a_run_asks_a_subclass_proxy_again_after_it_answered_none() -> None:
    """A subclass reads its own way, so a `None` from its `proxy()` is not held for the run."""

    class _Flaky(SequenceProxy):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def proxy(self):
            self.calls += 1
            return None if self.calls == 1 else self

    flaky = _Flaky()
    view = _held_by_one_run(flaky)
    assert view.proxy() is None
    assert view.proxy() is flaky
    assert view != _held_by_one_run(flaky), "two views are two runs, never equal by inherited fields"


def test_the_memo_is_bounded_and_evicts_the_least_recently_used(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _Backend(None)
    monkeypatch.setattr("just_dna_enricher.sequences.create_dataproxy", backend.create_dataproxy)
    monkeypatch.setattr("just_dna_enricher.sequences._MEMO_SIZE", 2)
    proxy = SequenceProxy()

    def read(start: int) -> None:
        assert proxy.subsequence("SQ.test", start, start + 1) == "T"

    for start in (0, 1, 0, 2):  # 0 is read again before 2 arrives, so 1 is the least recently used
        read(start)
    assert [start for _, start, _ in backend.reads] == [0, 1, 2]
    read(0)
    read(2)
    assert [start for _, start, _ in backend.reads] == [0, 1, 2], "0 and 2 are still held"
    read(1)
    assert [start for _, start, _ in backend.reads] == [0, 1, 2, 1], "1 was evicted, so it is asked again"


def test_the_memo_bound_is_the_constant_its_docstring_states() -> None:
    assert f"{_MEMO_SIZE:,}" in " ".join((SequenceProxy.__doc__ or "").split())


def test_threads_sharing_one_resolver_build_its_base_reader_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pm (2026-11-17): `EnsemblResolver._base_reader` is built under a lock, as the proxy's memo is.

    A host shares one resolver across threads. Without the lock, every thread arriving while the first
    was still building found no reader and built its own, each with a proxy of its own.
    """
    entered, release = threading.Event(), threading.Event()
    built: list[SequenceProxy] = []

    def slow_reader(sequences: SequenceProxy):
        built.append(sequences)
        entered.set()
        release.wait(5)
        return lambda _chrom, _pos: "A"

    monkeypatch.setattr("just_dna_enricher.ensembl._grch38_base_reader", slow_reader)
    resolver = EnsemblResolver()
    readers: list[object] = []

    def take() -> None:
        readers.append(resolver._base_reader())

    first = threading.Thread(target=take)
    first.start()
    assert entered.wait(5)
    others = [threading.Thread(target=take) for _ in range(3)]
    for thread in others:
        thread.start()
    for thread in others:
        thread.join(0.3)
    release.set()
    for thread in (first, *others):
        thread.join(5)
    assert len(built) == 1
    assert len(readers) == 4 and all(reader is readers[0] for reader in readers)


# ── the public batch capability and its settings ────────────────────────────────────────────────


def test_batch_size_above_ensembls_ceiling_is_refused_when_the_settings_are_built() -> None:
    assert EnsemblSettings(batch_size=200).batch_size == 200
    with pytest.raises(ValueError) as refused:
        EnsemblSettings(batch_size=201)
    assert str(refused.value) == (
        "EnsemblSettings.batch_size=201 is above the 200 rsIDs Ensembl takes in one "
        "POST /variation/:species; a batch size is never clamped, so pass 200 or fewer"
    )


@pytest.mark.parametrize("size", [0, -1])
def test_batch_size_below_one_is_refused_when_the_settings_are_built(size: int) -> None:
    """The other end of the same rule: 0.9 clamped a size below 1 to 1 where it was read, silently."""
    assert EnsemblSettings(batch_size=1).batch_size == 1  # the off-switch, one GET per rsID
    with pytest.raises(ValueError) as refused:
        EnsemblSettings(batch_size=size)
    assert str(refused.value) == (
        f"EnsemblSettings.batch_size={size} is below 1; a batch size is never clamped, so pass 1 (one GET "
        "per rsID) to 200"
    )


@pytest.mark.parametrize("timeout", [0.0, -5.0, float("nan")])
def test_a_batch_timeout_of_zero_or_less_is_refused_when_the_settings_are_built(timeout: float) -> None:
    assert EnsemblSettings(batch_timeout=0.5).batch_timeout == 0.5
    with pytest.raises(ValueError) as refused:
        EnsemblSettings(batch_timeout=timeout)
    assert str(refused.value) == (
        f"EnsemblSettings.batch_timeout={timeout} is not a number of seconds above 0; a timeout is never "
        "clamped, so pass one above 0"
    )


class _NoPost:
    """An `httpx` transport that fails the test if anything is sent: a refused setting asks nothing."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"a refused setting sent {request.method} {request.url}")


@pytest.mark.parametrize(
    ("field", "value", "said"),
    [
        ("batch_size", 0, "EnsemblSettings.batch_size=0 is below 1"),
        ("batch_size", -3, "EnsemblSettings.batch_size=-3 is below 1"),
        ("batch_size", 201, "EnsemblSettings.batch_size=201 is above the 200 rsIDs"),
        ("batch_timeout", 0.0, "EnsemblSettings.batch_timeout=0.0 is not a number of seconds above 0"),
    ],
)
def test_a_setting_changed_after_the_settings_were_built_is_refused_where_it_is_read(
    field: str, value: float, said: str
) -> None:
    """`EnsemblSettings` is a mutable dataclass, so a check at construction alone let `batch_size = 0` through:
    `net.batched(asked, 0)` yields no batch, and no rsID was answered or said to be unanswered (review round 1,
    item 8). The batched read refuses it, with the construction's own words, before any request."""
    settings = EnsemblSettings()
    setattr(settings, field, value)
    resolver = EnsemblResolver(settings=settings, gate=PacingGate(interval=0.0))
    resolver._client = httpx.Client(transport=httpx.MockTransport(_NoPost()))
    with pytest.raises(ValueError) as refused:
        list(resolver.resolve_rsids_batched(["rs1801133", "rs429358"]))
    assert str(refused.value).startswith(said)


def test_the_batch_capability_is_public_and_met_only_by_its_own_method_name() -> None:
    """`runtime_checkable` matches by name, so the name must not be one a different contract already has:
    gnomAD's `resolve_rsids` returns a dict, and a resolver carrying it is still asked one rsID at a time."""
    assert isinstance(EnsemblResolver(), BatchResolver)
    assert not isinstance(_Gnomad(), BatchResolver)
    assert not isinstance(_Resolver(), BatchResolver)


class _Batching(_Resolver):
    """A host's resolver with the public batch capability."""

    def __init__(self) -> None:
        super().__init__()
        self.batches: list[list[str]] = []

    def resolve_rsids_batched(self, rsids: Sequence[str]) -> Iterator[tuple[str, RsidAnswer]]:
        self.batches.append(list(rsids))
        for rsid in rsids:
            yield rsid, self.resolve_rsid(rsid)


@pytest.mark.usefixtures("no_ambient_caches")
def test_a_host_resolver_with_the_public_capability_is_asked_in_a_batch(tmp_path: Path) -> None:
    resolver = _Batching()
    result = _online(_spec(tmp_path), tmp_path, resolver=resolver)
    assert resolver.batches == [["rs1801133"]]
    placed = {row.rsid: (row.chrom, row.start) for row in result.rows}
    assert placed["rs1801133"] == ("1", 11796321)


# ── with neither new argument a run writes the same bytes as before (the CHANGELOG's claim, round 2) ──


def _written(root: Path) -> dict[str, bytes]:
    """Every file under `root` by relative path, the verification record's two clock fields masked."""
    out: dict[str, bytes] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        data = path.read_bytes()
        if path.name == "verification.json":
            data = re.sub(rb'"(produced_at|checked_at)": "[^"]*"', rb'"\1": "<clock>"', data)
        out[path.relative_to(root).as_posix()] = data
    return out


@pytest.mark.usefixtures("no_ambient_caches")
@pytest.mark.parametrize("example", ["hfe_hemochromatosis", "pathogenic_clinvar"])
def test_enrich_with_neither_new_argument_writes_what_a_call_naming_each_as_none_writes(
    example: str, ensembl_split_core, tmp_path: Path
) -> None:
    """A reference example enriched through the real path, offline, against a manifest-attested Ensembl core (so
    the rsID-index ladder runs and scans) and a ClinVar snapshot built from the slice, once with the optional clients, index
    and RM467 scopes omitted and once with their defaults explicit: every written file is the same
    bytes, `verification.json`'s clock fields aside. This cannot fail by construction while the defaults are
    `None`; it holds that they stay so. A true 0.8 baseline is another release's code and cannot run inside a
    test: it was measured at the build instead (the branch's report)."""
    core = ensembl_split_core(tmp_path / "ensembl_variations")
    clinvar = build_clinvar(_ASSETS / "clinvar_GRCh38_slice.vcf.gz", tmp_path / "clinvar").out_dir
    written: list[dict[str, bytes]] = []
    defaults = {
        "clients": None,
        "sequences": None,
        "rsid_index": None,
        "rederive_subjects": None,
        "verify_written_only": False,
    }
    for side, extra in (("default", {}), ("named", defaults)):
        target = tmp_path / side
        shutil.copytree(_REFERENCE_EXAMPLES / example, target)
        (target / "resolution.csv").unlink()
        result = enrich(
            target,
            offline=True,
            ensembl_cache=core,
            clinvar_cache=clinvar,
            download=False,
            use_gnomad=False,
            **extra,
        )
        assert result.rows, "the run resolved rows, so equal bytes are not two empty runs"
        written.append(_written(target))
    assert "resolution.csv" in written[0]
    assert written[0] == written[1]


@pytest.mark.usefixtures("no_ambient_caches")
def test_verify_written_only_skips_carried_ref_and_dbsnp_even_in_strict_mode(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    baseline = _online(spec, tmp_path, resolver=_Resolver())
    # Keep the authored pair, whose T ref disagrees with the supplied sequence.
    carried = next(row for row in baseline.rows if row.chrom == "19")
    _write_resolution_csv([carried], spec / "resolution.csv")
    asked = []
    clients = LookupClients(ensembl=_Resolver(), eutils=_caller_eutils(asked), grch37=_Grch37())
    options = {
        "clients": clients,
        "mode": "strict",
        "verify_ref": True,
        "verify_rsids": True,
        "sequences": _Bases("G"),
    }
    with pytest.raises(EnrichmentError, match="reference"):
        _online(spec, tmp_path, **options)
    asked.clear()
    result = _online(spec, tmp_path, verify_written_only=True, **options)
    assert result.ref_mismatches == []
    assert {uid for batch in asked for uid in batch} == {
        row.rsid.removeprefix("rs") for row in result.rows if row.variant_key != carried.variant_key
    }
    records = {r.check: r for r in read_verification(spec / "verification.json").records}
    expected = sum(row.variant_key != carried.variant_key for row in result.rows)
    assert records["reference_allele"].skipped is None
    assert records["reference_allele"].subjects == expected
    assert result.rsid_coordinates.not_checked == "nothing_to_check"
