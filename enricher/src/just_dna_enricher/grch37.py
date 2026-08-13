"""The old assembly: rs-number recovery and a wrong-build diagnosis (RM48).

An author curating from older literature has hg19/GRCh37 coordinates and the module must be GRCh38.
Nothing in these four packages converts, so the conversion happens off-tool and lands as an ordinary
authored coordinate carrying no provenance at all. This module is the *online* half of the answer;
the offline half (a position past the end of its contig, a contig only one build names) lives in the
compiler, where it needs neither network nor sequence.

**Recovery, never liftover — and the reporter argued their own request down.** If the paper gives an
rs-number, liftover is unnecessary *and strictly worse*: authoring the rs-number **produces** the
independent second value `resolution._verify` cross-examines. So liftover is only reachable where
there is no rs-number and only an old coordinate — and in exactly that case the lifted coordinate
becomes the row's **sole identity with nothing to check it against**, which is a generator of
unverifiable-by-construction identities: the hazard class behind the 3,038-variant off-by-one this
tree has already paid for once. Recovering the rs-number converts an unverifiable coordinate into a
verifiable one, using machinery the enricher already has.

**No chain file, no provisioned asset, no new licence.** The roadmap's stated blocker was that
rs-number recovery needs "either an hg19-keyed dbSNP surface or a chain file … i.e. the whole
snapshot apparatus for one authoring convenience". Probed 2026-08-13 and false: Ensembl runs a
permanent GRCh37 REST service at `grch37.rest.ensembl.org`, same API shape, serving both dbSNP
variants (`/overlap/region`) and reference bases (`/sequence/region`). The same request that answers
"which rs-numbers sit here on GRCh37" also discriminates the builds outright — `7:140453135..140453137`
is `CAC` on GRCh37 and `GTT` on GRCh38.

**Live-only, skipped offline.** This is an authoring-time convenience; nothing in a compile depends
on it, and a second whole-genome variant snapshot in the old assembly is exactly the apparatus worth
not building. `--offline` reports `skipped_offline`, which is a first-class answer and never a pass.

**It reports; it writes nothing.** Filling the recovered rs-number would make resolution verify a
value against the very service that produced it (`hints.REDUNDANCY_BEARING`, and `rsid` is
`identity_bearing` in `lookup._REFUSAL_BY_COLUMN`). The author types the rs-number; a later `enrich`
resolves it through the ordinary chain and `resolution.csv`'s `source` column records which link
answered. Provenance goes there, never into an authored coordinate.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx
from tenacity import retry, retry_if_exception_type, wait_exponential_jitter

from just_dna_enricher.net import PacingGate, attempt_floor
from just_dna_enricher.sequences import RefMismatch

logger = logging.getLogger(__name__)

#: Ensembl's permanent GRCh37 service. Same paths and same payload shapes as `rest.ensembl.org`;
#: only the assembly differs, which is why `assembly_name` is asserted on every parsed feature rather
#: than assumed from the host.
GRCH37_REST_ENDPOINT = "https://grch37.rest.ensembl.org"

#: The build this module speaks for, named rather than spelled inline. Fourth build-confusion guard
#: in this package — `gnomad.FREQUENCY_GENOME_BUILD` and `pharmvar.PHARMVAR_GENOME_BUILD` are the
#: precedent, and every one of those bugs was a literal that read as decoration.
GRCH37_BUILD = "GRCh37"

#: Ensembl publishes 15 requests/second; a tenth of a second keeps a whole panel comfortably inside
#: it while a paced client is still fast enough to be interactive.
_REQUEST_INTERVAL = 0.1

#: What one recovery attempt concluded.
#:
#: **Four, and the fourth is not padding.** The decision names three — *recovered*, *none*,
#: *ambiguous* — because that is where a liftover library goes wrong: `pyliftover` fuses the last two,
#: reporting "no result" both for a position that maps nowhere and for one that maps to several. But
#: those three are all answers, and S20 established in this exact resolution path that an
#: **unreachable** source is unchecked rather than absent: `([], None)` collapsed a failed request
#: into a definite negative and put two published variants in a consumer's "fabricated" pile. So
#: `unchecked` sits beside them on the other axis. A 4xx is an answer — the GRCh37 service 400s on an
#: unknown contig and on a position past the end of one — so only a 5xx, a transport error or a
#: timeout is `unchecked`.
VALID_RECOVERY_OUTCOME: frozenset[str] = frozenset(
    {"recovered", "ambiguous", "none", "unchecked", "skipped_offline"}
)


@dataclass
class Grch37Settings:
    endpoint: str = GRCH37_REST_ENDPOINT
    timeout: float = 15.0
    interval: float = _REQUEST_INTERVAL


@dataclass
class Grch37Client:
    """Paced, retrying access to the GRCh37 REST service. Every read is three-valued.

    Hold one per session, the way `LookupClients` says to: the `PacingGate` state and the connection
    pool are both thrown away by a client built per question, and the gate is what keeps a panel-sized
    run inside Ensembl's published budget.
    """

    settings: Grch37Settings = field(default_factory=Grch37Settings)
    gate: PacingGate | None = None
    _client: httpx.Client | None = None

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(interval=self.settings.interval)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _get(self, path: str, accept: str, params: dict[str, str] | None = None) -> httpx.Response:
        assert self.gate is not None
        self.gate.wait()
        response = self._http().get(
            f"{self.settings.endpoint}{path}", params=params or {}, headers={"Accept": accept}
        )
        response.raise_for_status()
        return response

    def variants_at(self, chrom: str, start: int) -> list[dict] | None:
        """dbSNP variants overlapping `chrom:start` on GRCh37, or `None` for could-not-ask.

        `[]` is an answer — the service was reached and records nothing there — while `None` means the
        question never completed. A 4xx counts as an answer: this service 400s on a contig it does not
        have and on a position past the end of one, and both of those really are "GRCh37 has nothing
        for you here", stated by the service rather than guessed at by us.

        Only dbSNP features with an `rs` id are returned. The endpoint also serves HGMD-PUBLIC records
        (`CM112509` at 7:140453136), and an id that is not an rs-number is not what this recovers.
        """
        try:
            response = self._get(
                f"/overlap/region/human/{chrom}:{start}-{start}",
                "application/json",
                {"feature": "variation"},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                logger.warning("GRCh37 overlap for %s:%d failed (%s)", chrom, start, exc)
                return None
            logger.info("GRCh37 has no region %s:%d (%s)", chrom, start, exc)
            return []
        except (httpx.TransportError, httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("GRCh37 overlap for %s:%d could not be reached: %s", chrom, start, exc)
            return None
        return [
            feature
            for feature in response.json()
            if feature.get("assembly_name") == GRCH37_BUILD
            and feature.get("source") == "dbSNP"
            and str(feature.get("id", "")).startswith("rs")
        ]

    def reference_bases(self, chrom: str, start: int, end: int) -> str | None:
        """The GRCh37 bases over the 1-based inclusive span `chrom:start..end`. **Three-valued.**

        Bases are an answer; `""` is *also* an answer — the service was reached and has no sequence
        there — and `None` means the question never completed. Collapsing the middle case into `None`
        is precisely the S20 inversion this module's docstring cites as its design rule, and it is
        reachable with ordinary data rather than only under an outage: `20:63500000` sits inside
        GRCh38's chromosome 20 and past the end of GRCh37's, so **the wrong-build case itself** 400s
        here. Reported as "could not be asked", it would tell an author to re-run for an answer the
        service had already given.

        `start`/`end` are the 1-based VCF convention this whole codebase stores, passed through
        unconverted — the instinctive `-1` is the off-by-one that cost 3,038 rows once already.
        """
        try:
            response = self._get(
                f"/sequence/region/human/{chrom}:{start}..{end}", "text/plain"
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                logger.warning("GRCh37 sequence for %s:%d-%d failed (%s)", chrom, start, end, exc)
                return None
            logger.info("GRCh37 has no sequence at %s:%d-%d (%s)", chrom, start, end, exc)
            return ""
        except (httpx.TransportError, httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning(
                "GRCh37 sequence for %s:%d-%d could not be reached: %s", chrom, start, end, exc
            )
            return None
        return response.text.strip().upper()


@dataclass
class RsidRecovery:
    """What the GRCh37 service said about one old coordinate. Advisory; nothing is written."""

    chrom: str
    start: int
    outcome: str
    ref: str | None = None
    alts: str | None = None
    #: Every candidate, in the order the service listed them, deterministically re-sorted by id.
    #: Several are **reported, never picked** — the same rule `_lookup_rsid_candidates` follows.
    rsids: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    note: str = ""

    def __str__(self) -> str:
        where = f"{GRCH37_BUILD} {self.chrom}:{self.start}"
        if self.outcome == "recovered":
            return (
                f"{where} is {self.rsids[0]} — author that rs-number instead of the coordinate: it "
                f"names the variant without naming a build, so resolution places it on whichever one "
                f"the module declares and the compiler can then cross-examine the coordinate it "
                f"produced. A converted position is its own only witness. Reported, never written"
            )
        if self.outcome == "ambiguous":
            return (
                f"{where} carries {len(self.rsids)} dbSNP records ({', '.join(self.rsids)}) — "
                f"reported, never picked. Narrow it with --ref/--alts, or take the one your source "
                f"names"
            )
        if self.outcome == "none":
            return f"{where}: {GRCH37_BUILD} dbSNP records nothing here. {self.note}".strip()
        if self.outcome == "skipped_offline":
            return f"{where}: not looked up — this run is offline, and there is no local GRCh37 data"
        return (
            f"{where}: the GRCh37 service could not be asked, so its answer is unchecked rather than "
            f"empty — re-run before reading this as a coordinate dbSNP does not know"
        )


def recover_rsid(
    chrom: str,
    start: int,
    *,
    ref: str | None = None,
    alts: str | None = None,
    client: Grch37Client | None = None,
    offline: bool = False,
) -> RsidRecovery:
    """Which rs-number GRCh37 dbSNP records at this old coordinate.

    The match is **anchored on the authored position**: a candidate must start exactly at `start`, and
    must carry the authored `ref` (and every authored alt) when those are given. Anchoring is what
    keeps this honest — a variant that merely *overlaps* the position is a different event, and
    accepting one would hand back an rs-number for a variant the author never meant.

    The consequence to know: an indel authored in VCF's padded spelling (POS on the base *before* the
    event) will not match Ensembl's unpadded record, and comes back `none` rather than wrong. That is
    RM31's one-indel-several-spellings problem, and this reports the shorter search rather than
    reconciling frames it was not given.
    """
    query = RsidRecovery(chrom=str(chrom), start=int(start), outcome="none", ref=ref, alts=alts)
    if offline:
        query.outcome = "skipped_offline"
        return query
    owned = client is None
    client = client or Grch37Client()
    try:
        features = client.variants_at(query.chrom, query.start)
    finally:
        if owned:
            client.close()
    if features is None:
        query.outcome = "unchecked"
        return query

    wanted_ref = ref.strip().upper() if ref else None
    wanted_alts = {a.strip().upper() for a in (alts or "").split(",") if a.strip()}
    matched: list[dict] = []
    for feature in features:
        alleles = [str(a).strip().upper() for a in feature.get("alleles") or []]
        if not alleles or feature.get("start") != query.start:
            continue
        if wanted_ref is not None and alleles[0] != wanted_ref:
            continue
        if wanted_alts and not wanted_alts <= set(alleles[1:]):
            continue
        matched.append(
            {
                "rsid": str(feature["id"]),
                "start": feature.get("start"),
                "end": feature.get("end"),
                "alleles": alleles,
            }
        )
    # Sorted, never first-met: the emitted order is what a caller reads back and what a test compares,
    # and Ensembl does not promise one (Principle 7's ordering rule).
    query.candidates = sorted(matched, key=lambda c: c["rsid"])
    query.rsids = [c["rsid"] for c in query.candidates]
    if len(query.rsids) == 1:
        query.outcome = "recovered"
    elif len(query.rsids) > 1:
        query.outcome = "ambiguous"
    else:
        query.outcome = "none"
        query.note = (
            "The search is anchored on the exact position, so an indel authored in VCF's padded "
            "spelling (POS on the base before the event) can miss a record that is really there."
            if not features
            else f"{len(features)} dbSNP record(s) overlap the position, none starting at it with "
            f"the alleles given."
        )
    return query


@dataclass
class BuildDiagnosis:
    """One ref-mismatched row, and what GRCh37 says about the same coordinate.

    Only produced for rows that **already failed** the reference-base check, which is what bounds the
    cost: `verify_reference_alleles` is the filter, and a module whose refs all agree with GRCh38
    makes no request here at all.
    """

    variant_key: str
    chrom: str
    start: int
    claimed: str
    reason: str
    grch37_bases: str | None = None
    rsids: list[str] = field(default_factory=list)
    #: What the ±1 neighbour check made of the same row, carried so the summary can say which reading
    #: wins. It is not idle: on the real HFE pair (`6:26093141`, `6:26091179` authored from the GRCh37
    #: literature into a GRCh38 module) the neighbour check reports "shifted 1 base to the right" for
    #: **both**, confidently and wrongly — the true variants are 228 and 411 bases away, and a
    #: neighbouring base equal to the authored ref is a one-in-four event. Two explanations printed
    #: side by side with nothing to order them is the shape this codebase keeps fixing.
    shift_claimed: int | None = None

    def __str__(self) -> str:
        head = f"{self.variant_key} at {self.chrom}:{self.start}"
        if self.reason == "unchecked":
            return f"{head}: {GRCH37_BUILD} could not be asked, so this row's build is unchecked"
        if self.rsids:
            return (
                f"{head}: the authored ref {self.claimed!r} is the {GRCH37_BUILD} base here, and "
                f"{GRCH37_BUILD} dbSNP records {', '.join(self.rsids)} at it — author the rs-number "
                f"rather than the coordinate"
            )
        return (
            f"{head}: the authored ref {self.claimed!r} is the {GRCH37_BUILD} base at this position"
        )


@dataclass
class BuildDiagnosisResult:
    """The wrong-build pass's answer, with a reason when it did not run and what it looked at.

    An empty `diagnoses` list otherwise says two opposite things — "asked, and nothing pointed at
    another build" and "never asked" — which is the same defect `clin_sig_not_checked` exists to
    prevent. `not_checked` is `None` exactly when the pass ran.

    `examined`/`total` are the denominator, published for the reason RM44 states: a finding that
    quantifies over a subset has to say what the subset was, or a reader takes it for the whole.
    """

    diagnoses: list[BuildDiagnosis] = field(default_factory=list)
    not_checked: str | None = None
    #: How many mismatched rows were actually asked about, against how many there were. They differ
    #: only when `limit` truncated the pass.
    examined: int = 0
    total: int = 0

    @property
    def sampled(self) -> bool:
        return self.examined < self.total


#: How many mismatched rows one pass will ask about. Two paced requests per row is fine for the
#: handful a real module produces and is not fine unbounded: a panel authored wholesale on hg19
#: mismatches on *every* row, and the answer is the same one over and over — that is the premise
#: grouping-by-reason already rests on. So a bounded sample gives the identical actionable finding,
#: and `BuildDiagnosisResult.sampled` says it was a sample rather than letting the count imply a
#: census.
DEFAULT_DIAGNOSIS_LIMIT = 50


#: Reason classes, weakest evidence first, each with what it does and does not license. Grouping is
#: by *reason* and never by row — a wrong-build panel produces one finding per variant, and 2,400 of
#: those read as hopeless where "2,400 rows are GRCh37" is a one-line fix (`summarize_ref_mismatches`
#: is the shape).
_DIAGNOSIS_NOTES: dict[str, str] = {
    "single_base_match": (
        "a single base agrees with GRCh37 at this position, which is suggestive and not conclusive — "
        "one base in four agrees by chance, and VCF 4.4 §1.6.1.4 requires an ambiguous reference base "
        "to be reduced to the first alphabetically, so an authored 'A' may be a lossily reduced 'R'"
    ),
    "multi_base_match": (
        "several consecutive bases agree with GRCh37 at this position, which chance does not explain"
    ),
    "dbsnp_corroborated": (
        "the authored ref is the GRCh37 base AND GRCh37 dbSNP records a variant starting there — the "
        "strongest of the three, and the one that names the rs-number to author instead"
    ),
    "unchecked": (
        "the GRCh37 service could not be asked, so these rows are unchecked rather than cleared"
    ),
}


def diagnose_wrong_build(
    mismatches: Sequence[RefMismatch],
    *,
    client: Grch37Client | None = None,
    offline: bool = False,
    limit: int = DEFAULT_DIAGNOSIS_LIMIT,
) -> BuildDiagnosisResult:
    """Do these ref-mismatched rows read as GRCh37 coordinates in a GRCh38 module?

    **Runs only on rows the reference-base check already rejected**, which is the whole cost control:
    the expensive question is asked of a set someone else has already narrowed to the suspicious rows.

    The asymmetry is worth stating rather than implying generality: `verify_reference_alleles` skips
    any build `refget_accession` has no table for, so a `RefMismatch` only ever exists for a GRCh38
    module — which makes "the other assembly" always GRCh37 here, not a parameter.

    Three tiers of evidence, and the message says which one it has. Neither the mismatch nor this
    diagnosis is repaired: an authored `ref` and an authored coordinate are the evidence that
    something upstream went wrong, and rewriting either destroys it.
    """
    if offline:
        return BuildDiagnosisResult(not_checked="skipped_offline", total=len(mismatches))
    if not mismatches:
        return BuildDiagnosisResult(not_checked="no_ref_mismatches")
    owned = client is None
    client = client or Grch37Client()
    examined = mismatches[:limit]
    diagnoses: list[BuildDiagnosis] = []
    try:
        for mismatch in examined:
            width = len(mismatch.claimed)
            bases = client.reference_bases(
                mismatch.chrom, mismatch.start, mismatch.start + width - 1
            )
            if bases is None:
                diagnoses.append(
                    BuildDiagnosis(
                        variant_key=mismatch.variant_key, chrom=mismatch.chrom,
                        start=mismatch.start, claimed=mismatch.claimed, reason="unchecked",
                    )
                )
                continue
            if bases != mismatch.claimed:
                # GRCh37 does not explain this row either — including `""`, where GRCh37 answered that
                # it has no such place at all (a contig it lacks, or a position past the end of one).
                # Withhold: the mismatch stands on its own, and inventing a build hypothesis with no
                # evidence would be a false accusation.
                continue
            recovery = recover_rsid(
                mismatch.chrom, mismatch.start, ref=mismatch.claimed, client=client
            )
            reason = (
                "dbsnp_corroborated"
                if recovery.rsids
                else ("multi_base_match" if width > 1 else "single_base_match")
            )
            diagnoses.append(
                BuildDiagnosis(
                    variant_key=mismatch.variant_key, chrom=mismatch.chrom, start=mismatch.start,
                    claimed=mismatch.claimed, reason=reason, grch37_bases=bases,
                    rsids=list(recovery.rsids), shift_claimed=mismatch.shift,
                )
            )
    finally:
        if owned:
            client.close()
    return BuildDiagnosisResult(
        diagnoses=diagnoses, examined=len(examined), total=len(mismatches)
    )


#: The reason classes whose evidence outranks a ±1 neighbour reading. A single agreeing base does
#: not: one base in four agrees by chance either way, so where the only evidence is one base the two
#: readings really are undecided and this withholds rather than ordering them.
_SUPERSEDES_SHIFT: frozenset[str] = frozenset({"dbsnp_corroborated", "multi_base_match"})


def summarize_build_diagnoses(
    diagnoses: Sequence[BuildDiagnosis], *, examples: int = 3
) -> list[str]:
    """One line per reason class, with a count, a few named rows, and which reading wins.

    Grouped by *reason* and never by row: a panel authored from pre-GRCh38 literature produces one of
    these per variant, and the shared cause is the only actionable thing in the pile.
    """
    grouped: dict[str, list[BuildDiagnosis]] = {}
    for diagnosis in diagnoses:
        grouped.setdefault(diagnosis.reason, []).append(diagnosis)
    lines: list[str] = []
    for reason, found in grouped.items():
        named = ", ".join(
            f"{d.chrom}:{d.start}" + (f" → {d.rsids[0]}" if d.rsids else "")
            for d in found[:examples]
        )
        more = f", and {len(found) - examples} more" if len(found) > examples else ""
        shifted = [d for d in found if d.shift_claimed is not None]
        supersedes = (
            f" {len(shifted)} of these were also read as a ±1 coordinate shift, and this supersedes "
            f"that: a neighbouring base equal to the authored ref is a one-in-four coincidence, and "
            f"the true variant is hundreds of bases away rather than one."
            if shifted and reason in _SUPERSEDES_SHIFT
            else ""
        )
        lines.append(
            f"{len(found)} row(s) — {_DIAGNOSIS_NOTES[reason]} ({named}{more}).{supersedes}"
        )
    return lines
