"""Live Ensembl resolution — for the rare rsIDs the frozen snapshot slice misses.

One backend: the **REST** variation API (rest.ensembl.org), a bare rsID → its GRCh38 mappings. Paced
under Ensembl's published budget (`PacingGate`, once per attempt) and retried by `tenacity` on a
transport error, a timeout, a 5xx or a 429, waiting at least what the answer's `Retry-After` asked for;
a wait longer than `net.RETRY_AFTER_CEILING` is not slept, and nothing is asked until it passes. All
network lives here (never in format/compiler). GRCh38 only.

**There was a second, and it is gone (2026-11-04).** A beta **GraphQL** leg (`beta.ensembl.org/api/
graphql/variation`, its query leeched from ensembl-mcp) was POSTed before every REST request. Probed by
hand that day: the endpoint answers **301** to `www.ensembl.org/api/graphql/variation`; there the query's
shape no longer validates (`Cannot query field 'region_name' on type 'Location'`, HTTP 400); and a bare
rsID is `VARIANT_ID_NOT_FOUND` even in a valid query, since that API wants a composite
`region:pos:rsid` id. It could not answer a bare rsID on any day it was asked, so it cost a request per
rsID and returned nothing. `ensembl-graphql` survives only as a `resolution.csv` `source` value a row
written before 0.8 may carry.
"""

import logging
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import httpx
from just_dna_format.vocab import ALLELE_PATTERN
from just_dna_format.vrs import refget_accession
from tenacity import retry, wait_exponential_jitter

from just_dna_enricher.clingen_allele import anchor_indel
from just_dna_enricher.net import (
    PacingGate,
    Withholding,
    attempt_floor,
    retry_after_seconds,
    retry_if_transient_within,
    wait_retry_after,
)
from just_dna_enricher.sequences import SequenceProxy

logger = logging.getLogger(__name__)

DEFAULT_REST_ENDPOINT = "https://rest.ensembl.org"
#: The one status REST answers "no such variation" with: a 400 naming the rsID (`rs3216883`). Every
#: other status (a 429 throttle, a 403, a 404 path, a 410 retired route, any 5xx) answered nothing
#: about the rsID, so it is could-not-ask, never the empty answer (RM361).
_REST_NO_RECORD_STATUS = 400
_ASSEMBLY = "GRCh38"
#: How an Ensembl data release is labelled wherever a live answer records one: `ensembl_116`. The
#: number is `/info/data`'s; the LD pass (`ld_pairs.LD_DATASET_PREFIX`) and resolution share the spelling.
ENSEMBL_RELEASE_PREFIX = "ensembl_"


def ensembl_data_release(payload: object) -> int | None:
    """The one release `/info/data` states (`{"releases": [116]}`), or `None` when it states not exactly one."""
    releases = payload.get("releases") if isinstance(payload, dict) else None
    if not isinstance(releases, list) or len(releases) != 1:
        return None
    (release,) = releases
    return release if isinstance(release, int) and not isinstance(release, bool) else None


#: Ensembl publishes 15 requests/second per IP (and ~55,000 per rolling hour, `x-ratelimit-*` on every
#: answer); a tenth of a second keeps a run inside both, the interval `grch37` uses for the same service.
_REQUEST_INTERVAL = 0.1


@dataclass
class EnsemblSettings:
    rest_endpoint: str = DEFAULT_REST_ENDPOINT
    species: str = "human"
    timeout: float = 15.0
    interval: float = _REQUEST_INTERVAL


class EnsemblError(RuntimeError):
    """A live Ensembl query failed on all backends (after retries + fallback)."""


class RsidResolver(Protocol):
    """What `enrich(resolver=)` requires of an injected resolver: `resolve_rsid`, and nothing else.

    `EnsemblResolver` is one; a host may inject its own (a shared, paced one, or a test fake). Every
    method `enrich` calls beyond this one is an **optional capability**, checked against its own named
    Protocol before the call (`RestWitness`), so a resolver written against an older enricher keeps
    working and the capability it lacks is reported as not asked rather than raised as an
    `AttributeError` mid-run. The one optional attribute, `non_nucleotide_rsids` (RM272), is read with
    an empty default. `close` is called only on a resolver `enrich` built itself.
    """

    def resolve_rsid(self, rsid: str) -> tuple[list[dict] | None, str | None]: ...


@runtime_checkable
class RestWitness(Protocol):
    """The optional capability the placement witness asks (RM267): REST's own mapping of an rsID.

    Added in 0.8, after hosts were already injecting resolvers. A resolver without it leaves Ensembl
    REST not asked for the run, counted, with one warning naming why.
    """

    def resolve_rsid_rest(self, rsid: str) -> tuple[list[dict] | None, str | None]: ...


@dataclass
class EnsemblResolver(Withholding):
    """Resolve a bare rsID to its GRCh38 loci via live Ensembl REST."""

    settings: EnsemblSettings = field(default_factory=EnsemblSettings)
    _client: httpx.Client | None = None
    # One GRCh38 base at a 1-based position, or `None` — what anchors a one-sided REST indel (RM268).
    # Private like `_client`, so a patch adds no constructor surface; a test sets it the same way.
    _read_base: Callable[[str, int], str | None] | None = None
    # rsIDs this resolver answered with no placeable locus because every mapping carried no nucleotide
    # allele (RM271), collected so a caller can name them (RM272). Accumulates across calls.
    non_nucleotide_rsids: set[str] = field(default_factory=set)
    # One gate per resolver, so a host holding one resolver (just-dna-marketplace shares one across
    # threads; the gate is thread-safe) paces every request it makes. Injectable for a test's clock.
    gate: PacingGate | None = None
    # The gate's clock reading before which nothing is asked: set when a throttle's `Retry-After`
    # outlived the retries, so the server's "not before" is honoured across rsIDs. Under its own lock,
    # because a host shares one resolver across threads and a stale reset would drop a fresh hold.
    _resume_at: float | None = None
    _hold_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(interval=self.settings.interval)

    def _base_reader(self) -> Callable[[str, int], str | None]:
        if self._read_base is None:
            self._read_base = _grch38_base_reader(SequenceProxy())
        return self._read_base

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def resolve_rsid(self, rsid: str) -> tuple[list[dict] | None, str | None]:
        """Return `([{chrom, start, ref, alts}, ...], source)` for a bare rsID.

        Asks REST (`resolve_rsid_rest`); the retired GraphQL leg is no longer asked first (module
        docstring). `source` is `ensembl-rest` — recorded per row so the manifest can report provenance.

        **Three outcomes, because two of them used to be one (S20).** A non-empty list is an answer;
        `[]` is *also* an answer — Ensembl was reached and has no GRCh38 locus for this rsID — and
        **`None` means Ensembl could not be asked at all**, so its answer is unchecked rather than
        empty. Fusing the last two into `([], None)` made a failed request read as a definite negative,
        and `loci: []` plus "Ensembl has no locus" is exactly the fingerprint of a fabricated rsID: a
        consumer checking which ids in a machine-written document were real put two published variants
        in the fabricated pile on a flaky run. This is the tri-state rule the rest of the tree keeps —
        an unreachable source reports unknown, never the negative.

        A **400 is an answer**, not a failure: Ensembl 400s on rsIDs it cannot resolve (`rs3216883`,
        which dbSNP reports as merged). Every other status — a 429 throttle, a 403, a 404, a 410, a
        5xx — and a transport error or a timeout return `None` (RM361: until then every 4xx was the
        empty answer, and a throttled run wrote `not_found` for live rsIDs). An empty answer now carries its source too, so a
        caller can record *which* link said nothing; that omission was the only trace the old code
        left, and it was a missing element in a set nobody diffs.

        **`None` with a source is the fourth outcome (RM268): Ensembl answered, and nothing it said
        could be placed.** REST spells an insertion or a deletion with one side `-` at an interbase
        `start`, and such a locus is written only once the reference base before the event has been
        read and prefixed to every allele. When that base cannot be read, the locus is withheld, and an
        answer whose every locus was withheld is unchecked rather than empty, exactly like a request
        that failed; the source is returned so a caller can say which of the two happened.
        """
        return self.resolve_rsid_rest(rsid)

    def resolve_rsid_rest(self, rsid: str) -> tuple[list[dict] | None, str | None]:
        """`resolve_rsid`'s V1 half on its own: REST's `/variation` mapping, with the same four outcomes.

        The placement witness (RM267) asks this, not `resolve_rsid`: its question is where REST's own
        mapping puts the rsID, through RM268's anchor, and an injected resolver's `resolve_rsid` may
        answer from any surface. It is an optional capability of an injected one (`RestWitness`).
        """
        assert self.gate is not None
        with self._hold_lock:
            held = self._resume_at is not None and self.gate.clock() < self._resume_at
        if held:
            logger.info("V1 REST for %s not asked: Ensembl's Retry-After has not passed", rsid)
            return None, None
        try:
            loci, withheld, unplaceable = self._rest_rsid(rsid)
        except httpx.HTTPStatusError as exc:
            asked = retry_after_seconds(exc)
            if asked is not None:
                # The retries are spent or the wait was too long to sleep: honour it for every rsID after.
                resume_at = self.gate.clock() + asked
                with self._hold_lock:
                    self._resume_at = max(self._resume_at or resume_at, resume_at)
            # Only a 400 is "no record" (RM361): a 5xx or a 429 after the retries, a 403, a 404 path or a
            # 410 retired route answered nothing about the rsID (`@unreachable-not-absent`).
            if exc.response.status_code != _REST_NO_RECORD_STATUS:
                self.note_retired("Ensembl REST", exc)
                logger.warning("V1 REST for %s failed: %s", rsid, exc)
                return None, None
            logger.info("V1 REST has no record for %s (%s)", rsid, exc)
            return [], "ensembl-rest"
        except (httpx.HTTPError, EnsemblError) as exc:
            logger.warning("V1 REST for %s could not be reached: %s", rsid, exc)
            return None, None
        if withheld:
            logger.info(
                "V1 REST for %s: %d one-sided indel locus/loci withheld, the anchor base could not be "
                "read (RM268)",
                rsid,
                withheld,
            )
            if not loci:
                return None, "ensembl-rest"
        if unplaceable:
            # RM271. A mapping with no nucleotide allele (`dbSNP_novariation`, an `N` run) is not a
            # locus. Permanent, unlike an unreadable anchor, so an rsID left with none is the existing
            # answered-empty `[]`, and the words say it is Ensembl's own "no variation here".
            if not loci:
                self.non_nucleotide_rsids.add(rsid)
            log = logger.warning if not loci else logger.info
            log(
                "V1 REST for %s: %d mapping(s) carry no nucleotide allele (e.g. dbSNP_novariation) and "
                "are not loci (RM271)%s",
                rsid,
                unplaceable,
                "; no placeable locus is left, so it is written as not found" if not loci else "",
            )
        return loci, "ensembl-rest"

    def data_release(self) -> str | None:
        """The data release REST answers from, as a label (`ensembl_116`), or `None` when it will not say.

        `/info/data` (`{"releases": [116]}`, read by hand on 2026-11-04), never `/info/rest`, which states
        the REST software's own version (`15.12`) and moves on a different clock from the data (RM373).
        Asked once by the run that used the live link, so the label is the release of that run's answers.
        A transport failure is retried; a status error, a body that is not JSON or one naming no single
        release is `None` with a log line: the rows are written, and only the release goes unrecorded.
        """
        try:
            payload = self._rest_info_data()
        except (httpx.HTTPError, EnsemblError) as exc:
            logger.warning("Ensembl REST did not state its data release (%s); recorded as unknown.", exc)
            return None
        release = ensembl_data_release(payload)
        if release is None:
            logger.warning(
                "Ensembl REST's /info/data states no single release (%r); recorded as unknown.", payload
            )
            return None
        return f"{ENSEMBL_RELEASE_PREFIX}{release}"

    @retry(
        stop=attempt_floor(3),
        wait=wait_retry_after(wait_exponential_jitter(multiplier=0.5, max=8.0)),
        retry=retry_if_transient_within(),
        reraise=True,
    )
    def _rest_info_data(self) -> dict:
        assert self.gate is not None
        self.gate.wait()
        resp = self._http().get(
            f"{self.settings.rest_endpoint}/info/data",
            params={"content-type": "application/json"},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return _json(resp)

    # ── V1: legacy REST ───────────────────────────────────────────────────────────────────────
    # A 5xx and a 429 are retried too (RM354's predicate): REST is the rung a run leans on, and the
    # placement witness (RM267) reads a request that never got an answer as "not asked" only after a
    # second try could not change it.
    @retry(
        stop=attempt_floor(3),
        wait=wait_retry_after(wait_exponential_jitter(multiplier=0.5, max=8.0)),
        retry=retry_if_transient_within(),
        reraise=True,
    )
    def _rest_rsid(self, rsid: str) -> tuple[list[dict], int, int]:
        assert self.gate is not None
        self.gate.wait()
        resp = self._http().get(
            f"{self.settings.rest_endpoint}/variation/{self.settings.species}/{rsid}",
            params={"content-type": "application/json"},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return _loci_from_rest(_json(resp), self._base_reader())


def _grch38_base_reader(sequences: SequenceProxy) -> Callable[[str, int], str | None]:
    """A `read_base` for `anchor_indel`: `None` off the refget table (a patch contig) or when unreadable."""

    def read_base(chrom: str, pos: int) -> str | None:
        accession = refget_accession(chrom)
        if accession is None or pos < 1:
            return None
        return sequences.subsequence(accession, pos - 1, pos)

    return read_base


def _json(response: httpx.Response) -> dict:
    """The body as JSON, or `EnsemblError` — so `resolve_rsid` can treat it as a leg that failed.

    A 200 carrying HTML (Ensembl's maintenance page, a proxy interstitial) raised a bare
    `json.JSONDecodeError` here, which the request's handler does not catch: `enrich` — which wraps
    the call in `try/finally` with no `except` — aborted mid-loop instead of recording the subject as
    unreachable. Typed, the request withholds.
    """
    try:
        payload = response.json()
    except ValueError as exc:
        raise EnsemblError(f"{response.url} did not answer JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise EnsemblError(f"{response.url} answered {type(payload).__name__}, not an object")
    return payload


def _placeable_alleles(ref: str | None, alts: Iterable[str]) -> tuple[str, list[str]] | None:
    """The nucleotide half of an Ensembl allele set, or `None` when there is no locus to write (RM271).

    Both Ensembl rungs serve allele strings that are not bases: REST's literal `dbSNP_novariation`, the
    VCF dump's empty alt and `<.>` (dbSNP records no variation at that mapping), IUPAC placeholders
    such as `<Y>`, and `N` runs, including an `N`-masked chrY `ref`. A `ref` outside the allele grammar
    withholds the locus; an alt outside it is dropped; a locus with no alt left is withheld. One
    predicate for every read of either rung, so the two cannot drift.
    """
    if ref is None or not ALLELE_PATTERN.match(ref):
        return None
    kept = [alt for alt in alts if ALLELE_PATTERN.match(alt)]
    return (ref, kept) if kept else None


def _loci_from_rest(
    payload: dict, read_base: Callable[[str, int], str | None]
) -> tuple[list[dict], int, int]:
    """Parse Ensembl REST /variation mappings into GRCh38 loci, deterministically ordered.

    Returns the loci, the number of mappings withheld because a one-sided indel could not be
    anchored (RM268), and the number withheld because no nucleotide allele is left (RM271). REST states an insertion as `-/C` with `start = end + 1` and a deletion as
    `AGTAAG/-` over `[start, end]`; in both the base before the event sits at `start - 1`, which is
    `anchor_indel`'s convention (the interbase point is the preceding base). Every allele is prefixed
    with that base, so a mixed string such as `-/G/GT` anchors whole; a string with no `-`
    (`ATCATC/ATC`, `TCTT/T/TCTTCTT`) is already anchored and passes through untouched.
    """
    loci: list[dict] = []
    withheld = 0
    unplaceable = 0
    for m in payload.get("mappings", []):
        if m.get("assembly_name") != _ASSEMBLY:
            continue
        alleles = str(m.get("allele_string", "")).split("/")
        chrom = m.get("seq_region_name")
        start = m.get("start")
        if chrom is None or start is None or not alleles or not alleles[0]:
            continue
        chrom, start = str(chrom), int(start)
        if "-" in alleles:
            anchored = _anchor_rest_alleles(chrom, start, alleles, read_base)
            if anchored is None:
                withheld += 1
                continue
            start, alleles = anchored
        placed = _placeable_alleles(alleles[0], alleles[1:])
        if placed is None:
            unplaceable += 1
            continue
        ref, alts = placed
        loci.append({"chrom": chrom, "start": start, "ref": ref, "alts": ",".join(alts)})
    ordered = sorted(loci, key=lambda locus: (locus["chrom"], locus["start"], locus["ref"]))
    return ordered, withheld, unplaceable


def _anchor_rest_alleles(
    chrom: str, start: int, alleles: list[str], read_base: Callable[[str, int], str | None]
) -> tuple[int, list[str]] | None:
    """A one-sided REST allele list → `(anchor position, anchored alleles)`, or `None` when unreadable."""
    sides = ["" if allele == "-" else allele for allele in alleles]
    anchored: list[str] = []
    for side in sides:
        # The first side is the reference itself, so its anchored form is the anchored `ref`.
        placed = anchor_indel((chrom, start - 1, sides[0], side), read_base)
        if placed is None:
            return None
        anchored.append(placed[3])
    return start - 1, anchored
