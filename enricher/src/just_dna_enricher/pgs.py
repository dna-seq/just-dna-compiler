"""The PGS Catalog — the registry behind `pgs.csv`'s accession, and the terms behind each score (RM163).

`PgsRow` is keyed on `pgs_id`, and until now that was the one authored identifier in the format no
pass ever put to its registry. This module is the client and the source-shape knowledge behind the
fourth registry in `identifiers.py`; the statuses, the comparison and the two attestations live there,
beside dbSNP's, OLS4's and HGNC's.

**Read the body, never the status.** Measured against the live REST surface on 2026-09-01:
`GET /rest/score/PGS000001` returns the record, `GET /rest/score/PGS999999` — a never-assigned id —
returns **HTTP 200 with `{}`**, and `GET /rest/score/PGSXXXX`, which is not even a well-formed
accession, returns **HTTP 200 with `{}` as well**. So the status code carries no existence information
at all and every negative looks identical from the outside. `@existence-not-identity`: a lookup that
answers "does this exist" has to say *what* it found, which is why a recognised accession carries the
score's name, release date and traits rather than a bare `True`.

**A 404 is therefore a failure here, not an answer**, and that is the opposite of `OntologyClient`'s
rule one module over. OLS4 and HGNC say "no such term" with a 404; this service says it with an empty
body on a 200, so a 404 from it means the request went somewhere unexpected — a moved path, a proxy,
a maintenance page — and reading that as "the Catalog does not hold this score" would turn an
infrastructure problem into a permanent negative about an author's row.

**The id space is sparse, and that decides how the absence is worded.** 6,982 scores span a range
reaching PGS019960 — roughly a third of it assigned — and a random sample of 40 well-formed in-range
ids returned 12 records and 28 empty bodies. So an unrecognised accession is overwhelmingly one that
was never issued rather than one that was withdrawn. `@rsid-absent-two-readings` earns its
equal-weight treatment because dbSNP's id space is densely assigned and merges are frequent; here the
base rate runs the other way, so the message names the typo reading first and withdrawal as the rarer
one. The Catalog publishes no supersession field at all, and that is stated as a limit of the source
rather than resolved by guessing.

**The release record is read, not built.** `/rest/info` publishes `latest_release` — date, score
count, publication and trait counts — beside the REST API's own version, so the currency question this
item wanted needed no builder and no snapshot. `dataset_label` spells that release the way
`SourceRow.dataset` records it, and `currency.default_probes` asks for it with the same function, so a
probe result and a recorded label are the same string when they are the same release.
"""

import json
import logging
import re
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, wait_exponential_jitter

from just_dna_enricher.net import PacingGate, attempt_floor

logger = logging.getLogger(__name__)

#: The REST root. No key, no authentication.
PGS_REST_BASE = "https://www.pgscatalog.org/rest"

#: How `sources.csv` spells this source, and the key `currency.default_probes` answers under.
PGS_SOURCE = "pgs_catalog"

#: The `SourceRow.dataset` prefix, in `CLINVAR_DATASET_PREFIX`'s shape and for its reason: the probe
#: and the recorded label are built by one function, so they cannot be two spellings of one release.
PGS_DATASET_PREFIX = "pgs_catalog_"

#: EBI publishes no rate limit for this service. The same fifth of a second `OntologyClient` uses for
#: OLS4 and HGNC — a courtesy rather than a budget, and enough that a module with fifty scores does
#: not open fifty connections as fast as it can.
_REQUEST_INTERVAL = 0.2


class PgsCatalogError(RuntimeError):
    """The PGS Catalog answered something this tier cannot use."""


class PgsCatalogUnavailable(PgsCatalogError):
    """The Catalog could not be asked at all — a failed request, never "it holds no such score".

    A subclass rather than a second type, for `ReleaseUnavailable`'s reason (P3): an existing
    `except PgsCatalogError` keeps firing, and a caller that needs to separate *unreachable* from
    *unreadable* can.

    **`identifiers` catches this rather than re-raising it**, and that is worth knowing before writing
    a handler for it. `check-identifiers` puts questions to four registries and writes one record per
    check, so letting this out as an `IdentifierUnavailable` would make the command stamp `unreachable`
    against OLS4's and HGNC's records too — for services that answered. The failure lands on
    `IdentifierReport.pgs_not_checked` and only the two PGS records read it. `currency._pgs_release` is
    the one caller that does translate, into `ReleaseUnavailable`, because a `ReleaseProbe`'s contract
    is an exception and its reason is read off the subclass.
    """


@dataclass(frozen=True)
class CatalogRelease:
    """What `/rest/info` says the Catalog published most recently."""

    #: `latest_release.date`, e.g. `2026-08-26`. `None` when the payload states none.
    date: str | None = None
    #: `latest_release.scores` — how many scores that release holds.
    scores: int | None = None
    #: The REST API's own version, which moves independently of the data release.
    rest_api_version: str | None = None
    #: Where the Catalog points for terms. Read rather than assumed, so a moved page is visible.
    terms_of_use: str | None = None


def parse_release(payload: dict) -> CatalogRelease:
    """`/rest/info` → the release it names. Pure, so it is testable against a recorded payload."""
    latest = payload.get("latest_release") or {}
    rest = payload.get("rest_api") or {}
    scores = latest.get("scores")
    return CatalogRelease(
        date=(latest.get("date") or None),
        scores=int(scores) if isinstance(scores, int | str) and str(scores).isdigit() else None,
        rest_api_version=(rest.get("version") or None),
        terms_of_use=(payload.get("terms_of_use") or None),
    )


def dataset_label(release: CatalogRelease | None) -> str | None:
    """`pgs_catalog_2026-08-26`, or `None` when the Catalog named no release.

    One function for the `SourceRow.dataset` stamp and for `currency`'s probe, which is
    `clinvar_dataset_label`'s rule: a second spelling would make the currency check quietly never
    match, and "never matches" renders as *unreadable* rather than as a bug.
    """
    if release is None or not release.date:
        return None
    return f"{PGS_DATASET_PREFIX}{release.date}"


# ── the ancestry vocabularies, and where they do not meet ────────────────────────────────────────

#: A PGS Catalog ancestry category → the `VALID_TRAINING_ANCESTRY` member it names, or `None` where
#: the format has no member for it.
#:
#: **Total over the categories the Catalog serves, with the unmappable ones written out rather than
#: left to a default** (`@lookup-with-a-default-hides-a-new-member`). A `.get(code)` returning `None`
#: for both *"this is Greater Middle Eastern, which the format cannot express"* and *"the Catalog has
#: invented a category since this was written"* would hide the second behind the first, so an absent
#: key is logged where a `None` value is not.
#:
#: `VALID_TRAINING_ANCESTRY` is 1000G superpopulation codes plus `multi`, and it is deliberately not
#: gnomAD's population list — so five of these map straight across, the two multi-ancestry categories
#: both land on `multi`, and four have no member at all. `NR` is the Catalog's own *not reported*,
#: which is an absence and not a category.
PGS_ANCESTRY_CATEGORIES: dict[str, str | None] = {
    "AFR": "AFR",
    "AMR": "AMR",
    "EAS": "EAS",
    "EUR": "EUR",
    "SAS": "SAS",
    "MAE": "multi",   # multi-ancestry, excluding European
    "MAO": "multi",   # multi-ancestry, including European
    "ASN": None,      # "additional Asian ancestries" — broader than EAS and than SAS, so neither
    "GME": None,      # Greater Middle Eastern — no 1000G superpopulation covers it
    "OTH": None,      # additional diverse ancestries
    "NR": None,       # not reported: an absence, not a population
}

#: Categories whose members this tier cannot **enumerate**, even where it has a name for them.
#:
#: `MAE` and `MAO` are bags: *multi-ancestry excluding European* and *multi-ancestry including
#: European* each stand for two or more superpopulations the Catalog did not break down. So `multi` is
#: the right positive answer for both — a score under either really is multi-ancestry — and neither
#: can support a **negative**: an authored `AFR` that the rest of the distribution does not carry may
#: be sitting inside the bag. Without this, `MAO` in particular produced a false finding against an
#: authored `EUR`, which is a population it explicitly includes.
#:
#: Separate from the `None` entries above because the two are different facts. A `None` category has
#: no member at all; these have one and still cannot be exhausted, and folding them together would
#: lose the positive answer.
_UNENUMERABLE_CATEGORIES: frozenset[str] = frozenset({"MAE", "MAO"})

#: Which stages of `ancestry_distribution` the drift check reads, and it is a decision rather than a
#: convenience. The Catalog publishes three: `gwas` (the ancestry of the discovery study the variant
#: effects came from), `dev` (the samples the score was developed on) and `eval` (the samples it was
#: evaluated in). `training_ancestry` exists so a consumer can refuse an out-of-ancestry application,
#: which is a question about where the score was *built and tested* — so `gwas` is upstream of it and
#: is excluded. Including it would widen the published set until nothing could ever disagree, which is
#: a check that cannot fail (`@tautology-zero`).
COMPARED_ANCESTRY_STAGES: tuple[str, ...] = ("dev", "eval")


def score_ancestries(payload: dict) -> tuple[frozenset[str], frozenset[str]]:
    """`(the format codes this score's dev/eval ancestries name, the categories that block a negative)`.

    Both halves are returned because the second is what makes the comparison honest. A category blocks
    a negative for either of two reasons, and they are different facts kept in one answer because the
    caller does the same thing with both: `NR`, `ASN`, `GME` and `OTH` name an ancestry this format has
    no member for, and `MAE`/`MAO` name a *bag* of superpopulations the Catalog did not break down. In
    both cases an authored code the first half does not contain may be exactly the one behind the
    category, so the caller withholds rather than reporting a difference it cannot stand behind.

    A `MAE`/`MAO` category still contributes `multi` to the first half: it is a perfectly good positive
    answer, and only the negative is unsafe.

    Every stratum with a positive share counts, however small. A threshold would be a second judgement
    about what "the score was validated in" means, on top of the stage choice above.
    """
    distribution = payload.get("ancestry_distribution") or {}
    mapped: set[str] = set()
    unresolved: set[str] = set()
    for stage in COMPARED_ANCESTRY_STAGES:
        stratum = (distribution.get(stage) or {}).get("dist") or {}
        for code, share in stratum.items():
            if not isinstance(share, int | float) or share <= 0:
                continue
            if code not in PGS_ANCESTRY_CATEGORIES:
                # `warning`, matching `pgs_license_class`'s unread-licence line: both are the same
                # defect class, and INFO is invisible in practice — a guard nobody reads is not one.
                logger.warning(
                    "The PGS Catalog served ancestry category %r, which PGS_ANCESTRY_CATEGORIES does "
                    "not carry; it is treated as unresolved and withholds rather than accusing.", code,
                )
                unresolved.add(code)
                continue
            member = PGS_ANCESTRY_CATEGORIES[code]
            if member is None or code in _UNENUMERABLE_CATEGORIES:
                unresolved.add(code)
            if member is not None:
                mapped.add(member)
    return frozenset(mapped), frozenset(unresolved)


def ancestry_agrees(authored: str, published: frozenset[str]) -> bool:
    """Whether one authored `training_ancestry` member is covered by what the Catalog publishes.

    `multi` is the only member that is not a population, so it is the only one with a rule of its own:
    it is covered by either of the Catalog's two multi-ancestry categories, and also by a published
    set naming two or more superpopulations, which is what multi-ancestry means. Anything else is a
    plain membership test.
    """
    if authored == "multi":
        return "multi" in published or len(published - {"multi"}) >= 2
    return authored in published


# ── the free-text half ───────────────────────────────────────────────────────────────────────────

#: Words too short to carry meaning in a cohort name. Tokens below this length match by accident —
#: `UK` alone appears inside dozens of unrelated strings — so they are dropped from the comparison
#: rather than allowed to vouch for a cell.
_MIN_COHORT_TOKEN = 3

#: Words that describe **what** a cohort is rather than **which** one it is. They match almost every
#: record — "Melbourne Collaborative Cohort Study" carries three of them — so letting one vouch for an
#: authored cell would make the comparison a check that cannot fail (`@tautology-zero`) while looking
#: like one that passes. Deliberately tiny and deliberately structural: a word that could identify a
#: cohort (`Biobank`, `Karolinska`, `Finnish`) is not in here, and the day one is, the check has begun
#: guessing rather than matching.
_GENERIC_COHORT_WORDS: frozenset[str] = frozenset(
    {
        "cohort", "cohorts", "study", "studies", "project", "group", "groups", "consortium",
        "sample", "samples", "participants", "population", "populations", "the", "and", "for",
        "from", "with", "data", "dataset", "based",
    }
)

_TOKEN = re.compile(r"[^0-9a-z]+")


def score_cohort_names(payload: dict) -> list[str]:
    """Everything `samples_training` says about who the score was trained on, first-occurrence order.

    Cohort short names, full names and alternate names, plus the per-sample ancestry prose the
    Catalog carries beside them (`ancestry_broad`, `ancestry_free`, `ancestry_country`,
    `ancestry_additional`) — because `training_cohort`'s own examples are `FIN` and `Ashkenazi`, which
    are ancestries rather than cohorts, and comparing them against cohort names alone would accuse
    every correct row that used one.

    Empty when the record lists no training samples, which the caller reads as *nothing to compare*
    rather than as a disagreement.
    """
    parts: list[str] = []
    for sample in payload.get("samples_training") or []:
        if not isinstance(sample, dict):
            continue
        for key in ("ancestry_broad", "ancestry_free", "ancestry_country", "ancestry_additional"):
            value = sample.get(key)
            if value:
                parts.append(str(value))
        for cohort in sample.get("cohorts") or []:
            if not isinstance(cohort, dict):
                continue
            for key in ("name_short", "name_full", "name_others"):
                value = cohort.get(key)
                if value:
                    parts.append(str(value))
    seen: set[str] = set()
    return [p for p in parts if not (p in seen or seen.add(p))]


def cohort_agrees(authored: str, published: list[str]) -> bool | None:
    """Whether an authored `training_cohort` shares any real word with what the record says.

    Three-valued: `True` agrees, `False` shares nothing, **`None` means the question could not be
    put** — the authored cell carries no word this can test with. Short tokens are dropped because two
    letters hit by accident inside unrelated prose, and the structural words in
    `_GENERIC_COHORT_WORDS` are dropped because they hit on purpose: a match by accident is a clean
    bill nobody earned.

    **Deliberately a weak test, and the weakness is the point.** `training_cohort` is free-form by
    design — `'FIN'`, `'Ashkenazi'`, `'UK Biobank NW-EUR'` — and no reliable equality exists between
    prose a curator wrote and prose the Catalog wrote. A comparison that cannot be made reliable is
    one that reports unknown, so `False` is reserved for the case where no reading is available at
    all: not one word of the authored cell appears anywhere in the record's own account of its
    training samples. Substring rather than whole-word matching, so `FIN` is vouched for by
    `Finnish` — insisting on token equality would accuse a correct row.
    """
    haystack = " ".join(published).lower()
    tokens = [
        t
        for t in _TOKEN.split(authored.lower())
        if len(t) >= _MIN_COHORT_TOKEN and t not in _GENERIC_COHORT_WORDS
    ]
    if not tokens:
        return None
    return any(token in haystack for token in tokens)


# ── the client ───────────────────────────────────────────────────────────────────────────────────


class PgsCatalogClient:
    """One score record, or the Catalog's own release, paced and with a per-run cache.

    A class rather than a function because the pacing gate and the cache are per-run state, the same
    reason `ClingenAlleleClient` is one. `@client-exception-contract`: retry, then translate, **both
    legs** — a persistent 5xx and an exhausted transport failure both arrive as
    `PgsCatalogUnavailable`, never as an `httpx` type.
    """

    def __init__(
        self,
        *,
        base: str = PGS_REST_BASE,
        client: httpx.Client | None = None,
        gate: PacingGate | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout
        self._client = client
        self._owned = client is None
        self._gate = gate if gate is not None else PacingGate(_REQUEST_INTERVAL)
        self._scores: dict[str, dict] = {}

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout, follow_redirects=True,
                headers={"Accept": "application/json"},
            )
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owned:
            self._client.close()
            self._client = None

    def __enter__(self) -> "PgsCatalogClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def score(self, pgs_id: str) -> dict:
        """One score record, or `{}` when the Catalog holds none under that accession.

        The empty dict is the Catalog's own answer and is cached like any other: a module naming the
        same accession on two rows costs one request, and the two rows can never be told different
        things.
        """
        key = (pgs_id or "").strip()
        if key not in self._scores:
            self._scores[key] = self._get(f"{self.base}/score/{key}")
        return self._scores[key]

    def info(self) -> dict:
        """`/rest/info` verbatim — the release record plus the REST API's own version."""
        return self._get(f"{self.base}/info")

    def release(self) -> CatalogRelease:
        """The release `/rest/info` names. Raises `PgsCatalogUnavailable` if it cannot be asked."""
        return parse_release(self.info())

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=1.0, max=10.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _request(self, url: str) -> httpx.Response:
        # Paced inside the retried function on purpose: a retry then spends a slot of the budget
        # rather than bursting past it.
        self._gate.wait()
        return self._http().get(url)

    def _get(self, url: str) -> dict:
        """One GET returning a JSON object, with `httpx` translated away on both legs.

        The transport leg is re-raised bare inside `_request` so the decorator can match it, which
        means the translation has to happen here or the exception escapes raw the moment the attempts
        run out. A non-JSON body — a maintenance page served with a 200 — is `PgsCatalogUnavailable`
        too: the Catalog answered and what it said cannot be read, which is not an absence.
        """
        try:
            response = self._request(url)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise PgsCatalogUnavailable(f"{url} could not be reached: {exc}") from exc
        if response.status_code >= 400:
            # Including 404. This service says "no such score" with an empty body on a 200, so a 404
            # here means the request went somewhere unexpected rather than that the score is absent.
            raise PgsCatalogUnavailable(f"{url} answered {response.status_code}")
        try:
            payload = json.loads(response.text)
        except ValueError as exc:
            raise PgsCatalogUnavailable(f"{url} did not answer JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise PgsCatalogUnavailable(f"{url} answered {type(payload).__name__}, not an object")
        return payload
