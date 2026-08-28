"""Has the source a module was drafted from published since? (RM85)

`SourceRow.dataset` already records **which release** a module's rows came from — that is what the
tautology skip reads, and what `withdraw_stale_dataset` blanks when a module ends up mixing two. What
nothing did was *act* on it. A module drafted from ClinVar inherits ClinVar's weekly cadence and needs
a source-refresh pass; one built from a paper inherits the literature's and needs an evidence pass;
and neither an author who has forgotten nor a curator who inherited the module was ever told which.

So this is a comparison, not a column: the recorded label against the label the source publishes
**now**. It needs the network, which is why it is an enricher check (the validation-ceiling rule) and
not a compiler one, and it **reads and never writes** — the column-shaped repair (a second field
saying what this module was made from and what would age it) was refused one table over in RM71, on
the grounds that it restates `dataset` and then rots where `dataset` is maintained.

**It is `--rederive`'s cheap neighbour.** Both ask *has the world moved*: `--rederive` re-asks every
source about every subject and reports the rows that changed, which costs a full run; this asks about
the release **label** alone and costs one request per source. So the label check is what tells an
author whether the expensive one is worth running, and the two compose rather than overlap.

**Tri-state, and `--offline` is where it bites.** A source that could not be asked is `unchecked` —
never *up to date*. That distinction is the whole value here: a check that reported a clean bill for a
source nobody reached would be the S4 defect wearing the badge of the mechanism built to end it. So
`behind` is `True` / `False` / `None`, the unaskable legs are named in the record's `detail` rather
than counted into the denominator, and with no leg answering the pass records a skip instead of a
zero.

**Comparability is tri-state too.** `clinvar_dataset_label` has two forms — `clinvar_2026-08-25` from
the VCF header, and `clinvar_sha256:…` for a snapshot built from a VCF whose header stated no date.
The two name the same release space and cannot be tested for equality across forms, so a recorded
digest against a live date is *uncomparable*, not *behind*. Withheld, and named.

**One probe ships, deliberately.** ClinVar is the source the whole item is about and the only one this
tier can ask for a release label in the same namespace it records — `PROBE_SOURCES` is the registry,
and every source outside it is honestly `unsupported` rather than quietly current. Adding a probe is
adding a member; nothing else here changes.
"""

import logging
import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import httpx
from just_dna_format.sources import SourceRow
from tenacity import retry, retry_if_exception_type, wait_exponential_jitter

from just_dna_enricher.clinvar import CLINVAR_DATASET_PREFIX
from just_dna_enricher.clinvar_build import DEFAULT_CLINVAR_URL, file_date_from_header
from just_dna_enricher.net import PacingGate, attempt_floor
from just_dna_enricher.verification import examples

logger = logging.getLogger(__name__)


class ReleaseProbeError(RuntimeError):
    """A release probe failed in a way its caller must be able to tell from a real answer."""


class ReleaseUnavailable(ReleaseProbeError):
    """The source could not be asked at all — a failed request, never "it publishes nothing".

    A subclass, not a second type (P3): an existing `except ReleaseProbeError` keeps firing, while a
    caller that needs to separate *unreachable* from *unreadable* can. `@client-exception-contract`,
    which also makes a handler's `except` order load-bearing — the narrow arm goes first.
    """


#: How many compressed bytes of the ClinVar VCF are read before the stream is abandoned. The header is
#: a few kilobytes of highly compressible text and the file is ~200 MB, so this is the difference
#: between a probe and a download. Generous rather than tight: a header that grew past the window
#: would report "the source stated no release", and withholding a label we could have read is the one
#: wrong answer available here.
HEADER_PROBE_BYTES = 262_144

#: NCBI asks for no particular pacing on the FTP-over-HTTPS mirror, but this tier paces every service
#: it touches and one probe per run is well inside any budget.
CLINVAR_MIN_INTERVAL = 0.5

#: The form a label takes when a source could only be pinned by digest. Two labels compare only when
#: they are the same *kind*: a digest and a stated release name one release space between them and
#: equality across the two forms means nothing.
_DIGEST_MARKER = "sha256:"


def _label_kind(label: str) -> str:
    """`"digest"` or `"stated"` — which form a `dataset` label is written in."""
    return "digest" if _DIGEST_MARKER in label else "stated"


@dataclass
class ClinVarReleaseClient:
    """What release ClinVar publishes *now*, read from the live VCF's own header.

    The label is built with `CLINVAR_DATASET_PREFIX` + the `##fileDate=` value, through the same
    reader `clinvar_build` uses on a downloaded file — so a probe result and a snapshot's recorded
    `dataset` are the same string when they are the same release. A second spelling here would make
    the check quietly never match, which is the failure `clinvar_dataset_label` exists to prevent one
    function over.

    **It streams and abandons rather than asking for a byte range.** A `Range` header is the obvious
    move and depends on the server honouring it; a server that ignores one answers `200` with the
    whole 200 MB body and the probe silently becomes a download. Reading the first
    `HEADER_PROBE_BYTES` off a normal stream and closing it needs no such promise.

    `@client-exception-contract`: retry, then translate, **both legs** — a persistent 5xx and an
    exhausted transport failure both arrive as `ReleaseUnavailable`, never as an `httpx` type.
    """

    url: str = DEFAULT_CLINVAR_URL
    timeout: float = 30.0
    client: httpx.Client | None = None
    gate: PacingGate | None = None

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(CLINVAR_MIN_INTERVAL)

    def _http(self) -> httpx.Client:
        if self.client is None:
            self.client = httpx.Client(timeout=self.timeout)
        return self.client

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=1.0, max=15.0),
        retry=retry_if_exception_type(
            (httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)
        ),
        reraise=True,
    )
    def _header_bytes(self) -> bytes:
        """The first `HEADER_PROBE_BYTES` compressed bytes, or fewer if the body is shorter."""
        assert self.gate is not None
        self.gate.wait()
        chunks: list[bytes] = []
        taken = 0
        with self._http().stream("GET", self.url) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                chunks.append(chunk)
                taken += len(chunk)
                if taken >= HEADER_PROBE_BYTES:
                    break
        return b"".join(chunks)[:HEADER_PROBE_BYTES]

    def current_release(self) -> str | None:
        """`clinvar_<fileDate>`, or `None` when what came back stated no release date.

        `None` is the withhold and is *not* the same as raising: the source answered, and what it said
        carries no label to compare against. The caller records those two as different reasons.
        """
        try:
            raw = self._header_bytes()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise ReleaseUnavailable(f"ClinVar release probe failed: {exc}") from exc
        date = file_date_from_header(_gunzip_prefix(raw))
        return f"{CLINVAR_DATASET_PREFIX}{date}" if date else None

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None


def _gunzip_prefix(raw: bytes) -> str:
    """Decompress as much of a truncated gzip stream as it will give, as text.

    A partial member is the normal case here — the stream was abandoned mid-file on purpose — and
    `zlib` is happy to hand back the prefix it managed. Bytes that are not gzip at all (an error page
    served with a 200, a mirror that returns HTML) yield nothing rather than an exception the caller
    would have to read as unreachability: the source answered, and we could not read what it said.
    """
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        text = decompressor.decompress(raw)
    except zlib.error as exc:
        logger.warning(
            "The ClinVar release probe read %d byte(s) that are not a gzip stream (%s); the current "
            "release is unread rather than absent.", len(raw), exc,
        )
        return ""
    return text.decode("utf-8", errors="replace")


#: A probe answers "which release does this source publish right now", spelled the way this workspace
#: records that source's `SourceRow.dataset`. `None` means the source answered and named none;
#: `ReleaseUnavailable` means it could not be asked at all.
ReleaseProbe = Callable[[], str | None]


def default_probes(*, clinvar: ClinVarReleaseClient | None = None) -> dict[str, ReleaseProbe]:
    """The probes this tier ships, keyed by the `SourceRow.source` they answer for.

    A registry rather than a chain of `if source == …`: what a reader needs is the set of sources that
    *can* be asked, and `PROBE_SOURCES` below is derived from this function so the two cannot disagree.
    """
    client = clinvar if clinvar is not None else ClinVarReleaseClient()
    return {"clinvar": client.current_release}


#: The sources this tier can ask, derived from `default_probes` rather than restated beside it — a
#: second list is a registry that goes stale the first time a probe is added (`@registry-completeness`).
PROBE_SOURCES: frozenset[str] = frozenset(default_probes(clinvar=ClinVarReleaseClient()))


@dataclass(frozen=True)
class DatasetCurrency:
    """One `(source, layer)` row's recorded release, against what its source publishes now."""

    source: str
    layer: str
    #: What `SourceRow.dataset` says — never blank; a row without one is not a subject at all.
    recorded: str
    #: What the source says now, or `None` when nothing could be established.
    current: str | None = None
    #: A `VALID_VERIFICATION_SKIPS` member when this leg could not be settled, `None` when it was.
    unchecked: str | None = None

    @property
    def behind(self) -> bool | None:
        """Tri-state: `True` the source has published since, `False` still current, `None` unknown.

        `None` is never `False`. A leg nobody could ask, and a pair of labels written in two different
        forms, both land here — and a caller that read this as "up to date" would publish exactly the
        reassurance this check exists to withhold.
        """
        if self.unchecked is not None or self.current is None:
            return None
        return self.recorded != self.current

    def __str__(self) -> str:
        if self.unchecked is not None:
            return f"{self.source} ({self.layer}): {self.recorded} vs unchecked ({self.unchecked})"
        if self.current is None:
            return f"{self.source} ({self.layer}): {self.recorded} vs unchecked"
        if self.behind:
            return f"{self.source} ({self.layer}): drafted from {self.recorded}, now {self.current}"
        return f"{self.source} ({self.layer}): {self.recorded} is current"


@dataclass(frozen=True)
class CurrencyCheck:
    """What the pass compared, what it could not, and why — the denominator travelling with the finding.

    `compared` is the honest subject set: the legs that were asked **and answered comparably**. A leg
    nobody could reach is in `unchecked` and counted nowhere, because counting it would claim a
    comparison that was never made — the coverage lie the reference-allele pass shipped once already.
    """

    compared: tuple[DatasetCurrency, ...] = ()
    unchecked: tuple[DatasetCurrency, ...] = ()
    #: A `VALID_VERIFICATION_SKIPS` member when the whole pass could not run, `None` when it did.
    not_checked: str | None = None

    @property
    def subjects(self) -> int:
        """How many recorded releases were actually compared against a stated current one."""
        return len(self.compared)

    @property
    def behind(self) -> list[DatasetCurrency]:
        """The legs whose source has published since — the findings, in recorded order."""
        return [c for c in self.compared if c.behind]


#: Precedence for the reason recorded when **no** leg could be settled. Deliberately the opposite
#: order to the wrong-build pass's, and for a reason that does not contradict it: there, one row
#: satisfied two conditions at once and reporting the transient one falsely promised that a re-run
#: would answer it. Here the reasons belong to *different* sources and the record's `detail` names
#: every one of them, so nothing is hidden by leading with the reason an author can act on.
_SKIP_PRECEDENCE: tuple[str, ...] = ("offline", "unreachable", "no_reference", "unsupported")


def check_dataset_currency(
    rows: Sequence[SourceRow],
    *,
    probes: Mapping[str, ReleaseProbe] | None = None,
    offline: bool = False,
) -> CurrencyCheck:
    """Compare every recorded `dataset` against the release its source publishes now.

    Reads and writes nothing: it takes the rows a caller already loaded and returns what it found, so
    a run that reports a gap leaves the spec directory byte-for-byte as it was. Repairing a stale
    label is a re-draft, which is an author's decision and a different command.

    One request per *source*, not per row: two layers of one source share a probe result, because
    "what does ClinVar publish now" has one answer whatever a module used it for.

    `probes` is injected, the way `resolver` and `gnomad_client` are one module over, and it is what
    the tests drive: the shipped registry is built only once a leg could actually be asked, so an
    offline run opens no client at all.
    """
    subjects = [row for row in rows if (row.dataset or "").strip()]
    if not subjects:
        # Not a skip that a flag or egress would clear: the module records no release, so there is no
        # claim to have an opinion about. `nothing_to_check` is exactly that member.
        return CurrencyCheck(not_checked="nothing_to_check")

    if offline:
        # Returned before the registry is built, so an offline run opens no client at all — the
        # off-switch has to be provable by the probe never being invoked, not by the reason it wrote.
        # Every recorded release is `unchecked`: an offline run has not established that any source
        # stands still, and saying otherwise is the one thing this check may never do.
        return CurrencyCheck(
            (),
            tuple(
                DatasetCurrency(row.source, row.layer, (row.dataset or "").strip(),
                                unchecked="offline")
                for row in subjects
            ),
            not_checked="offline",
        )

    # The **effective** registry decides who can be asked, never `PROBE_SOURCES`: an injected registry
    # is entitled to answer for a source this tier ships no probe for, and testing the shipped set
    # here would make the injection point unable to widen the check.
    registry = probes if probes is not None else default_probes()
    #: `source -> (label, reason)` — one probe result per source, reused across its layers. Cached
    #: rather than re-asked so a module recording ClinVar at two layers costs one request, and so the
    #: two layers can never be told different things about one source.
    answered: dict[str, tuple[str | None, str | None]] = {}
    compared: list[DatasetCurrency] = []
    unchecked: list[DatasetCurrency] = []

    for row in subjects:
        recorded = (row.dataset or "").strip()
        if row.source not in answered:
            answered[row.source] = _ask(registry, row.source)
        label, reason = answered[row.source]
        if reason is not None:
            unchecked.append(
                DatasetCurrency(row.source, row.layer, recorded, unchecked=reason)
            )
        elif label is None or _label_kind(label) != _label_kind(recorded):
            # Read and unreadable are different absences. A source that stated no release, and a
            # source whose stated release is written in the other of the two label forms, both leave
            # nothing to compare — which is `no_reference`, and emphatically not "still current".
            unchecked.append(
                DatasetCurrency(row.source, row.layer, recorded, current=label,
                                unchecked="no_reference")
            )
        else:
            compared.append(DatasetCurrency(row.source, row.layer, recorded, current=label))

    if compared:
        return CurrencyCheck(tuple(compared), tuple(unchecked))
    reasons = {leg.unchecked for leg in unchecked}
    reason = next((member for member in _SKIP_PRECEDENCE if member in reasons), "unreachable")
    return CurrencyCheck((), tuple(unchecked), not_checked=reason)


def _ask(probes: Mapping[str, ReleaseProbe], source: str) -> tuple[str | None, str | None]:
    """One source's current release as `(label, reason)` — exactly one of the two is `None`.

    A probe that raises is a source that could not be *asked*; one that returns `None` is a source
    that answered and named no release. The caller keeps those apart because their remedies are
    different, and neither of them is "up to date".
    """
    probe = probes.get(source)
    if probe is None:
        return None, "unsupported"
    try:
        return probe(), None
    except ReleaseUnavailable as exc:
        logger.warning(
            "Could not ask %s which release it publishes (%s); its recorded dataset is unchecked "
            "rather than current.", source, exc,
        )
        return None, "unreachable"


def summarize_currency(check: CurrencyCheck) -> list[str]:
    """One sentence per *reason*, never one per row — the aggregation rule this tree shares.

    Returns the sentences a record's `detail` and the CLI's report are both built from, so what an
    author reads on the terminal and what the attestation carries cannot drift.
    """
    lines: list[str] = []
    behind = check.behind
    if behind:
        lines.append(
            f"{len(behind)} recorded release(s) have been superseded: "
            + examples([f"{c.source} {c.recorded} → {c.current}" for c in behind])
        )
    by_reason: dict[str, list[DatasetCurrency]] = {}
    for leg in check.unchecked:
        by_reason.setdefault(leg.unchecked or "unreachable", []).append(leg)
    for reason in sorted(by_reason):
        legs = by_reason[reason]
        lines.append(
            f"{len(legs)} recorded release(s) unchecked ({reason}): "
            + examples([f"{c.source} {c.recorded}" for c in legs])
        )
    return lines
