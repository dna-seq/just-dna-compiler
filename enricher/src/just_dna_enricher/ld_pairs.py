"""`ld-pairs` — the computed LD pair behind a study measured on a proxy (0.8, RM331).

An author writes only `StudyRow.proxy_rsid`. r² has no meaning without its population, so the pass asks
a reference for r² and D′ between proxy and lead **in the study's own `ancestry`**, and writes
`ld_pairs.csv`, keyed `(proxy_rsid, variant_key, ld_population)`. The reference is Ensembl REST's pairwise
LD endpoint over the 1000 Genomes phase 3 superpopulations (PT2 §4 question 4, accepted 2026-11-04),
probed by hand in docs/probes/LANES_0_8.md §2 before any of this was written. What the probe found, and
what each finding costs here:

* **The five superpopulations are not in Ensembl's own LD population listing**, yet the endpoint answers
  for them. So this pass spells `1000GENOMES:phase_3:<CODE>` itself from the closed `ancestry` set, and a
  `400 … population object` is a defect of that spelling (`LdError`), never a withhold.
* **`200 []` is not r² = 0.** It comes back for a pair on two chromosomes and for the APOE pair in AFR,
  and lowering the `r2` floor does not bring a row back. It is written as `not_reported`, r² empty.
* **A `400 … variation object` is an answer**: the reference does not know one of the two rsIDs. It is
  written as `rsid_unknown`, and is neither retried nor read as an outage.
* **The response renames a merged rsID** (asking rs1624712 answers as rs646776). The row stays keyed on
  what the author wrote and `answered_rsid` records the reference's name. The proxy goes first in the
  URL, so `variation1` is the proxy; the probe's two orderings both kept the order asked.
* **`r2` and `d_prime` are JSON strings**, six decimals. Parsed to floats; `str(float)` writes the same
  six digits back, so the CSV round trip is exact.
* **The service flakes**: HTML 500 pages and 37-second answers. 5xx, 429 and transport errors are
  retried, then arrive as `LdUnavailable` (`@client-exception-contract`); the timeout is long enough for
  the slow answer. 55,000 calls per hour; the pacing gate stays well under it.

**A study naming several superpopulations, or none, gets its row with r² withheld and the reason** (the
pm's setting: the lookup never picks a panel). **A lead with no rsID** (coordinate-authored, and no
back-filled rsID in `resolution.csv`) gets its row with `lead_has_no_rsid`: the endpoint takes rsIDs.
Neither consults the reference, so neither writes a licence row (`@write-the-sourcerow`).

**Merge, never clobber** (`@sidecar-authoritative`): a pair already in the file is not asked again; delete
the file to re-ask after a new release. **`--offline` asks nothing and writes nothing**: there is no LD
snapshot, and a row for a pair nobody asked about would claim an answer (`@unreachable-not-absent`).
**Could-not-ask writes no row**: when Ensembl stays down past the retries, the pairs already answered this
run are committed (each one cost a request, and the gap-fill resumes from them) and `LdUnavailable` is
raised naming the rest.
"""

import csv
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import merge_key
from just_dna_format.layout import atomic_writer, nothing_to_write
from just_dna_format.ld_pairs import LD_RESOLVED, LdPairRow
from just_dna_format.normalize import now_utc_iso
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import StudyRow
from just_dna_format.vocab import RSID_PATTERN
from tenacity import retry

from just_dna_enricher.ensembl import DEFAULT_REST_ENDPOINT, ENSEMBL_RELEASE_PREFIX, ensembl_data_release
from just_dna_enricher.licensing import (
    ENSEMBL_TERMS,
    overlaid_input_rows,
    record_table_sources,
    require_sources_file,
    sidecar_path,
    table_datasets,
)
from just_dna_enricher.net import (
    EndpointRetired,
    PacingGate,
    _jittered_backoff,
    _log_give_up,
    _log_retry,
    attempt_floor,
    raise_if_retired,
    retry_if_transient,
)

logger = logging.getLogger(__name__)

LD_PAIRS_CSV = "ld_pairs.csv"
#: The `SourceRow.layer` this pass records Ensembl's terms at.
LD_LAYER = "ld_pair"
#: The reference panel, as Ensembl names it. The superpopulation code is the study's `ancestry` member.
LD_POPULATION_PREFIX = "1000GENOMES:phase_3:"
#: The release label's prefix; the number is read from `/info/data` on the run that asks. The spelling
#: `resolution.csv`'s `source_release` gives a live answer too (RM373), so it is shared, not restated.
LD_DATASET_PREFIX = ENSEMBL_RELEASE_PREFIX
#: Ensembl asks for at most 15 requests per second; one in ten keeps a margin for a shared IP.
LD_MIN_INTERVAL = 0.1
#: The probe saw a 37-second answer; a timeout shorter than that turns a slow answer into an outage.
LD_TIMEOUT = 90.0
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_UNKNOWN_VARIATION = re.compile(r"could not fetch variation object", re.IGNORECASE)


class LdError(RuntimeError):
    """The LD pass could not do its work: a local table it cannot read, or an answer it cannot use."""


class LdUnavailable(LdError):
    """Ensembl could not be asked: a transport failure, or a 5xx/429 that outlasted the retries.

    A subclass so an `except LdError` keeps catching it, and a caller that must tell a dead source from
    bad data can, by type (`@client-exception-contract`).
    """


class LdRetired(LdUnavailable, EndpointRetired):
    """Ensembl answered HTTP 410: it retired the endpoint asked (RM354).

    A fact about the source, not an outage, and not retried. An `LdUnavailable` so every existing handler
    still catches it; the message says the endpoint moved rather than that the service was down.
    """


@dataclass(frozen=True)
class LdAnswer:
    """What the reference said about one pair: its rows, or that it does not know an rsID.

    `rows` is the JSON array as served (possibly empty); `unknown` is the reference's own message when it
    answered 400 for a variation it cannot fetch.
    """

    rows: tuple[dict, ...] = ()
    unknown: str | None = None


@dataclass
class LdClient:
    """Ensembl REST pairwise LD, with the four legs of the client contract.

    A 200 is an answer (its JSON array); a 400 naming a variation is an answer too (`LdAnswer.unknown`);
    every other 4xx (a 404 is a moved path or a wrong species, which a re-run repeats) and a 200 that is not
    a JSON array of pairs is `LdError`; 5xx (EBI serves its 500 as an HTML page), 429 and transport
    failures are retried and then `LdUnavailable`.
    """

    endpoint: str = DEFAULT_REST_ENDPOINT
    species: str = "human"
    timeout: float = LD_TIMEOUT
    client: httpx.Client | None = None
    gate: PacingGate | None = None

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(LD_MIN_INTERVAL)

    def _http(self) -> httpx.Client:
        if self.client is None:
            self.client = httpx.Client(timeout=self.timeout)
        return self.client

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    @retry(
        before_sleep=_log_retry,
        retry_error_callback=_log_give_up,
        stop=attempt_floor(4),
        wait=_jittered_backoff(base=2.0, cap=20.0),
        # A 5xx or a 429 only (RM354): a permanent 4xx answers the same on every attempt.
        retry=retry_if_transient(),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        assert self.gate is not None
        self.gate.wait()
        response = self._http().get(
            f"{self.endpoint}/{path}", params=params, headers={"Content-Type": "application/json"}
        )
        if response.status_code != 400:
            response.raise_for_status()
        return response

    def _request(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        try:
            return self._get(path, params)
        except httpx.HTTPStatusError as exc:
            raise_if_retired(exc, LdRetired, "Ensembl LD")
            if exc.response.status_code in _RETRY_STATUS:
                raise LdUnavailable(f"Ensembl could not be asked ({path}): {exc}") from exc
            # A 404/401/405 is the service answering a request this client got wrong (a moved path, a
            # wrong species): a defect, which a re-run repeats, never an outage.
            raise LdError(f"Ensembl answered {exc.response.status_code} for {path}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise LdUnavailable(f"Ensembl could not be reached ({path}): {exc}") from exc

    def pairwise(self, proxy: str, lead: str, population: str) -> LdAnswer:
        """r² and D′ between `proxy` and `lead` in `population`, as the reference serves them."""
        path = f"ld/{self.species}/pairwise/{proxy}/{lead}"
        response = self._request(path, {"population_name": population})
        if response.status_code == 400:
            try:
                payload = response.json()
            except ValueError as exc:
                raise LdError(
                    f"Ensembl refused {path} for {population} with a body that is not JSON"
                ) from exc
            message = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(message, str) and _UNKNOWN_VARIATION.search(message):
                return LdAnswer(unknown=message)
            raise LdError(f"Ensembl refused {path} for {population}: {message or payload!r}")
        payload = _json(response, path)
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise LdError(f"Ensembl answered {path} with {type(payload).__name__}, not a list of pairs")
        return LdAnswer(rows=tuple(payload))

    def release(self) -> int:
        """The Ensembl release answering, from `/info/data` (`{"releases": [116]}`)."""
        payload = _json(self._request("info/data"), "info/data")
        release = ensembl_data_release(payload)
        if release is None:
            raise LdError(f"Ensembl's /info/data states no single release: {payload!r}")
        return release


def _json(response: httpx.Response, what: str) -> object:
    """The body as JSON, or `LdError`. A 200 whose body is not JSON (a proxy interstitial) is an answer
    that cannot be read, the house's shape failure (the parent type, as `ClinVarGkmError` and
    `LitvarError` raise it), never a parse error leaking out. EBI's own error page arrives as a 500, which
    the status leg retries and reports as `LdUnavailable`."""
    try:
        return response.json()
    except ValueError as exc:
        raise LdError(f"Ensembl answered {what} with a body that is not JSON: {exc}") from exc


# ── the pass ────────────────────────────────────────────────────────────────────────────────────


#: `(proxy_rsid, variant_key, ld_population)` — `LdPairRow._KEY_FIELDS`, in that order.
PairKey = tuple[str, str, str | None]


@dataclass(frozen=True)
class _Wanted:
    key: PairKey
    lead_rsid: str | None
    status: str | None  # a withheld status decided without asking, or None for a pair to ask


@dataclass
class LdPairsResult:
    """What one `ld-pairs` run did."""

    rows: list[LdPairRow] = field(default_factory=list)
    #: Rows this run wrote, in key order: answers, and withholds decided from the study rows.
    written: list[LdPairRow] = field(default_factory=list)
    #: Pairs this run should have asked and did not: `--offline`, or Ensembl down past the retries.
    unasked: list[PairKey] = field(default_factory=list)
    #: Pairs Ensembl answered with something this pass cannot use (`LdError`): no row, named, and the
    #: run raises after committing the rest.
    unusable: list[tuple[PairKey, str]] = field(default_factory=list)
    #: Rows already in the file whose pair no study row names any more (its ancestry or proxy changed):
    #: dropped, since a derived row with no study behind it is an orphan, and counted here.
    dropped: list[PairKey] = field(default_factory=list)
    #: Pairwise requests made (each answered); the release probe is not counted.
    requests: int = 0
    dataset: str | None = None
    skipped_offline: bool = False


#: `(chrom, start, ref)` → the one rsID `resolution.csv` back-filled at that place, for a coordinate lead.
Place = tuple[str, int, str | None]


def _lead_rsid(row: StudyRow, backfilled: dict[Place, str]) -> str | None:
    """The lead's rsID to send: the study row's own, else the one resolution back-filled at its place.

    Matched on the coordinate, never on the key: a `StudyRow` keys without `alts` (`chrom:start:ref`)
    while the `VariantRow` that resolution answered for keys with them, so the two keys differ for the
    same variant.
    """
    if row.rsid is not None and RSID_PATTERN.match(row.rsid):
        return row.rsid
    if row.chrom is None or row.start is None:
        return None
    return backfilled.get((str(row.chrom), row.start, row.ref))


def _wanted(studies: list[StudyRow], backfilled: dict[Place, str]) -> list[_Wanted]:
    """One entry per distinct pair key, in first-occurrence (authored) order.

    Two studies of one pair that land on one key with different withhold reasons (one mixed, one with no
    ancestry) keep the first, as every first-occurrence tie-break here does; the study rows themselves
    still say which is which.
    """
    out: dict[PairKey, _Wanted] = {}
    for row in studies:
        if row.proxy_rsid is None or row.variant_key is None:
            continue
        codes = list(dict.fromkeys(row.ancestry or []))  # `EUR;EUR` names one superpopulation
        if len(codes) == 1:
            population: str | None = f"{LD_POPULATION_PREFIX}{codes[0]}"
            lead = _lead_rsid(row, backfilled)
            status = None if lead is not None else "lead_has_no_rsid"
        else:
            population, lead = None, None
            status = "ancestry_mixed" if codes else "ancestry_unstated"
        key = (row.proxy_rsid, row.variant_key, population)
        out.setdefault(key, _Wanted(key, lead, status))
    return list(out.values())


def _answered_row(want: _Wanted, answer: LdAnswer, dataset: str, fetched_at: str) -> LdPairRow:
    proxy, lead_key, population = want.key
    base = {
        "proxy_rsid": proxy,
        "variant_key": lead_key,
        "ld_population": population,
        "dataset": dataset,
        "source": ENSEMBL_TERMS.source,
        "fetched_at": fetched_at,
    }
    if answer.unknown is not None:
        logger.info("Ensembl does not know an rsID of %s/%s: %s", proxy, want.lead_rsid, answer.unknown)
        return LdPairRow(**base, status="rsid_unknown")
    matching = [r for r in answer.rows if r.get("population_name") == population]
    if not matching:
        return LdPairRow(**base, status="not_reported")
    if len(matching) > 1:
        raise LdError(f"Ensembl answered {len(matching)} rows for {proxy}/{want.lead_rsid} in {population}")
    pair = matching[0]
    names = (pair.get("variation1"), pair.get("variation2"))
    # The proxy is the side that is not the lead; when neither side is the lead as asked (both renamed),
    # the order asked decides, which both of the probe's orderings kept.
    answered = names[1] if names[0] == want.lead_rsid else names[0]
    try:
        r2, d_prime = float(pair["r2"]), float(pair["d_prime"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LdError(
            f"Ensembl's pair for {proxy}/{want.lead_rsid} carries no readable r2/d_prime: {pair!r}"
        ) from exc
    return LdPairRow(**base, status=LD_RESOLVED, r2=r2, d_prime=d_prime, answered_rsid=answered)


def _withheld_row(want: _Wanted, fetched_at: str) -> LdPairRow:
    proxy, lead_key, population = want.key
    assert want.status is not None
    return LdPairRow(
        proxy_rsid=proxy,
        variant_key=lead_key,
        ld_population=population,
        status=want.status,
        fetched_at=fetched_at,
    )


def _sort_key(row: LdPairRow) -> tuple[str, str, str]:
    return (row.variant_key, row.proxy_rsid, row.ld_population or "")


def _cell(value: object) -> str:
    """One canonical CSV cell, matching the compiler's `_scalar_cell` (`str(float)` is the exact round trip)."""
    return "" if value is None else str(value)


def _write(rows: list[LdPairRow], path: Path, *, before_commit: Callable[[], None] | None) -> None:
    fieldnames = list(LdPairRow.model_fields)  # derived from the model, never hand-kept
    if nothing_to_write(path, rows):
        return  # RM370: a pass that answered nothing leaves no table
    with atomic_writer(path, newline="", before_commit=before_commit) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in fieldnames})


def _ask(
    ensembl: LdClient, to_ask: list[_Wanted], result: LdPairsResult, fresh: list[LdPairRow], fetched_at: str
) -> LdUnavailable | None:
    """Ask each pair in order, appending its row to `fresh`; the outage that stopped it, or `None`.

    The release is read first, in band, so the label is the release that answered (`@a-label-read-in-band-
    beats-one-read-off-the-transfer`). The first `LdUnavailable` stops the queue: the client has already
    retried it, so the rest would only wait out the same outage one by one. Everything not asked is
    `result.unasked` and gets no row. An `LdError` for one pair (an answer this pass cannot use) costs that
    pair alone: it gets no row, is named in `result.unusable`, and the queue goes on, so the pairs already
    paid for are committed.
    """
    try:
        result.dataset = f"{LD_DATASET_PREFIX}{ensembl.release()}"
    except LdUnavailable as exc:
        result.unasked = [w.key for w in to_ask]
        return exc
    for index, want in enumerate(to_ask):
        proxy, _lead_key, population = want.key
        assert want.lead_rsid is not None and population is not None
        try:
            answer = ensembl.pairwise(proxy, want.lead_rsid, population)
        except LdUnavailable as exc:
            result.unasked = [w.key for w in to_ask[index:]]
            return exc
        except LdError as exc:
            result.requests += 1
            result.unusable.append((want.key, str(exc)))
            continue
        result.requests += 1
        try:
            fresh.append(_answered_row(want, answer, result.dataset, fetched_at))
        except LdError as exc:
            result.unusable.append((want.key, str(exc)))
    return None


def _read_studies(spec_dir: Path) -> list[StudyRow]:
    path = spec_dir / "studies.csv"
    if not path.exists():
        return []
    rows, errors, _ = load_csv_rows(path, StudyRow, "studies.csv")
    if errors:
        # The `collect_subjects` rule: an invalid study row does not stop the run, it is named once and
        # the compile refuses it anyway.
        logger.warning(
            "studies.csv has %d invalid row(s), and any LD proxy on them is not asked about (first: %s); "
            "`just-dna-compiler validate` names each.",
            len(errors),
            errors[0],
        )
    return rows


def _backfilled_rsids(spec_dir: Path) -> dict[Place, str]:
    """`(chrom, start, ref) → rsid` from the overlaid `resolution.csv`, for a coordinate-authored lead.

    A place two rows back-fill with different rsIDs is left out: picking one would send Ensembl a guess.
    """
    path = sidecar_path(spec_dir, "resolution.csv", error=LdError)
    if not path.exists():
        return {}
    rows, errors, _ = load_csv_rows(path, ResolutionRow, path.name)
    if errors:
        raise LdError(f"resolution.csv is invalid: {errors[0]}")
    rows = overlaid_input_rows(spec_dir, "resolution.csv", rows, error=LdError)
    seen: dict[Place, set[str]] = {}
    for r in rows:
        if r.rsid and RSID_PATTERN.match(r.rsid) and r.chrom is not None and r.start is not None:
            seen.setdefault((str(r.chrom), r.start, r.ref), set()).add(r.rsid)
            # A study row may leave `ref` off; the place without it answers too when unambiguous.
            seen.setdefault((str(r.chrom), r.start, None), set()).add(r.rsid)
    return {place: next(iter(ids)) for place, ids in seen.items() if len(ids) == 1}


def enrich_ld_pairs(
    spec_dir: Path,
    *,
    offline: bool = False,
    write: bool = True,
    client: LdClient | None = None,
) -> LdPairsResult:
    """Fill `ld_pairs.csv` for every study row naming a `proxy_rsid`."""
    spec_dir = Path(spec_dir)
    target = sidecar_path(spec_dir, LD_PAIRS_CSV, error=LdError)
    if write:
        # A placeholder or half-edited licence table fails now, before any request (RM231).
        require_sources_file(spec_dir, error=LdError)

    existing: dict[tuple, LdPairRow] = {}
    if target.exists():
        rows, errors, _ = load_csv_rows(target, LdPairRow, LD_PAIRS_CSV)
        if errors:
            raise LdError(f"existing {LD_PAIRS_CSV} is invalid: {errors[0]}")
        existing = {merge_key(row): row for row in rows}

    named = _wanted(_read_studies(spec_dir), _backfilled_rsids(spec_dir))
    named_keys = {w.key for w in named}
    wanted = [w for w in named if w.key not in existing]
    to_ask = [w for w in wanted if w.status is None]
    result = LdPairsResult()

    if offline:
        if to_ask:
            logger.warning(
                "LD pairs skipped: --offline and there is no LD snapshot. %d pair(s) were not asked about "
                "and get no row (unknown, not absent): %s",
                len(to_ask),
                [w.key for w in to_ask][:5],
            )
        result.rows = sorted(existing.values(), key=_sort_key)
        result.unasked = [w.key for w in to_ask]
        result.skipped_offline = True
        return result

    fetched_at = now_utc_iso()
    fresh: list[LdPairRow] = [_withheld_row(w, fetched_at) for w in wanted if w.status is not None]
    outage: LdUnavailable | None = None
    if to_ask:
        owned = client is None
        ensembl = client or LdClient()
        try:
            outage = _ask(ensembl, to_ask, result, fresh, fetched_at)
        finally:
            if owned:
                ensembl.close()

    result.written = sorted(fresh, key=_sort_key)
    # A recorded pair no study row names any more (its ancestry or proxy was edited) is an orphan: its
    # study is gone, so it is dropped and counted rather than left to be counted in the manifest.
    result.dropped = sorted(
        (k for k in existing if k not in named_keys), key=lambda k: (k[0], k[1], k[2] or "")
    )
    if result.dropped:
        logger.warning(
            "Dropped %d ld_pairs.csv row(s) whose pair no studies.csv row names any more: %s",
            len(result.dropped),
            result.dropped[:5],
        )
    merged = {k: row for k, row in existing.items() if k in named_keys}
    for row in fresh:
        merged[merge_key(row)] = row
    result.rows = sorted(merged.values(), key=_sort_key)

    if write and (fresh or result.dropped):
        answered = result.requests > 0
        _write(
            result.rows,
            target,
            before_commit=(
                # Inside the table's commit (`@licence-row-inside-the-commit`), and only when Ensembl answered
                # this run: a run that wrote withholds alone consulted no source (`@write-the-sourcerow`).
                # Labelled by the release every committed pair states, not by this run's alone (RM373).
                (
                    lambda: record_table_sources(
                        table_datasets(result.rows, release=lambda row: row.dataset),
                        LD_LAYER,
                        spec_dir,
                        error=LdError,
                        # A routine merge declares nothing, so it retires no licence row (RM383).
                        answered_every_row=False,
                    )
                )
                if answered
                else None
            ),
        )
    if result.unusable:
        raise LdError(
            f"{len(result.unusable)} pair(s) got an answer this pass cannot use and have no row "
            f"(first: {result.unusable[0][0]}: {result.unusable[0][1]}); the {len(fresh)} other row(s) of "
            f"this run {'were committed' if write else 'are in the result'}"
            + (f", and {len(result.unasked)} pair(s) were not asked: {outage}" if outage is not None else "")
        )
    if outage is not None:
        raise LdUnavailable(
            f"{outage} — {len(result.unasked)} pair(s) were not asked and have no row; "
            f"{result.requests} answered this run {'were committed' if write else 'are in the result'}, and "
            f"a re-run asks only the rest."
        ) from outage
    return result
