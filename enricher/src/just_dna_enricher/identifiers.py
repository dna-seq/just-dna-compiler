"""Identifier currency — are the labels a module keys on still the ones its registries serve?

Three registries, one shape: ask whether an authored identifier is current, and report what the
registry says instead. **Nothing here repairs anything**, and for rsIDs that is not a stylistic
preference but a hard requirement — see `check_rsids`.

This is the generalization of COMPILER.md's *"is the source stale?"* blind spot from datasets to
identifiers. The compiler cannot see the world move; a dbSNP merge, an EFO term retirement and an HGNC
symbol rename all leave a module perfectly well-formed and quietly out of date.

**dbSNP: three states, and one of them means two opposite things.** Probed rather than assumed:

| State | `esummary db=snp` |
|---|---|
| live | `snp_id` == requested, `merged_sort='0'` |
| merged | `snp_id` != requested, `merged_sort='1'` |
| absent | `{'uid': …, 'error': 'cannot get document summary'}` |

The `absent` response for `rs11273140` — an rsID *withdrawn* after a clustering error — is
**byte-identical** to the one for `rs2000000000`, which was never assigned. For an author these mean
opposite things (fix the typo, versus the variant itself was retracted and the annotation resting on
it may be worthless), and no live endpoint separates them: `esearch` has no withdrawn filter, and
`latest_release/misc/rs_unsupported_b157.txt` looks like a withdrawn registry but is a one-off
build-157 ClinVar-parsing incident list that does not contain `rs11273140`. So the message names both
readings and asserts neither. Guessing "typo" would send an author to fix the wrong thing.

**NCBI is the oracle, not Ensembl.** Ensembl REST resolves *some* merges (`rs77121243` → `rs334`) and
returns HTTP 400 on others (`rs3216883`, which dbSNP correctly reports as merged into `rs3051860`), so
Ensembl alone would misclassify a merged rsID as unresolvable.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import MULTI_SEP
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from just_dna_enricher.eutils import EutilsClient, is_missing
from just_dna_enricher.net import PacingGate, dedupe

logger = logging.getLogger(__name__)

DEFAULT_OLS4_BASE = "https://www.ebi.ac.uk/ols4/api"
DEFAULT_HGNC_BASE = "https://rest.genenames.org"

# CURIE prefix → the IRI stem the ontology publishes its terms under. EFO mints its own namespace;
# everything else this format accepts lives on an OBO PURL. Kept as data rather than string surgery
# because getting it wrong yields a 200 with zero terms, which reads exactly like "does not exist".
_ONTOLOGY_IRI: dict[str, tuple[str, str]] = {
    "EFO": ("efo", "http://www.ebi.ac.uk/efo/"),
    "MONDO": ("mondo", "http://purl.obolibrary.org/obo/"),
    "HP": ("hp", "http://purl.obolibrary.org/obo/"),
    "OBA": ("oba", "http://purl.obolibrary.org/obo/"),
}
_CURIE = re.compile(r"^([A-Za-z]+)[:_](\w+)$")


class IdentifierCheckError(RuntimeError):
    """A currency lookup failed outright (transport or an unusable response)."""


# ── findings ────────────────────────────────────────────────────────────────────────────────────


@dataclass
class RsidStatus:
    """What dbSNP currently says about one authored rsID."""

    rsid: str
    state: str                       # live | merged | absent | withdrawn
    current: Optional[str] = None    # the surviving rsID, when merged

    @property
    def is_current(self) -> bool:
        return self.state == "live"

    @property
    def is_fatal(self) -> bool:
        """Whether this refuses in **both** modes rather than only under `strict`.

        Only `withdrawn` does. A merged rsID still resolves to the right locus (the module is dated,
        not wrong) and an absent one may be a typo, a very new id, or API lag — all leave the
        annotation itself intact. A withdrawn one is dbSNP repudiating the variant, so the annotation
        may be describing nothing.

        Nothing in this module produces `withdrawn` today: a retraction is byte-identical to a
        never-assigned id through every live endpoint, so `classify_rsid` reports `absent` and names
        both readings. The state exists for a curator who has established the retraction by hand, and
        for a future source that can tell them apart.
        """
        return self.state == "withdrawn"

    def __str__(self) -> str:
        if self.state == "merged":
            return (
                f"{self.rsid} has been merged into {self.current} — the locus is unchanged, so the "
                f"module is dated rather than wrong. Reported, never rewritten: `weights.parquet` "
                f"carries the rsID as identity, so updating it here would migrate the module's "
                f"`variant_key` by network lookup and break the round-trip fixed point. Fix it with "
                f"an authored edit, or author the coordinate instead (a VRS allele id cannot drift)."
            )
        if self.state == "absent":
            return (
                f"dbSNP has no record of {self.rsid} — it was either never assigned (a typo in the "
                f"identifier) or has been withdrawn (the variant itself was retracted, and the "
                f"annotation resting on it may be worthless). These are indistinguishable through the "
                f"API, so this message asserts neither; check the identifier against the source you "
                f"took it from."
            )
        if self.state == "withdrawn":
            return (
                f"{self.rsid} has been WITHDRAWN from dbSNP — the variant itself was retracted, so the "
                f"annotation resting on it may be describing nothing. Unlike a merged or absent rsid "
                f"this refuses in both modes: re-key the row onto a coordinate, or remove it."
            )
        return f"{self.rsid} is current in dbSNP"


@dataclass
class TraitStatus:
    """What the ontology currently says about one authored trait id."""

    curie: str
    state: str                       # current | obsolete | absent | unchecked
    label: Optional[str] = None
    replaced_by: Optional[str] = None

    def __str__(self) -> str:
        if self.state == "obsolete":
            replacement = (
                f", replaced by {self.replaced_by}" if self.replaced_by
                else " with no replacement recorded"
            )
            return f"{self.curie} ({self.label!r}) is obsolete{replacement}"
        if self.state == "absent":
            return (
                f"{self.curie} is not a term in its ontology — check the prefix and the numeric id "
                f"(a wrong prefix and a wrong id look identical from here)"
            )
        if self.state == "unchecked":
            return f"{self.curie} uses a prefix this check does not know how to resolve"
        return f"{self.curie} is current"


@dataclass
class GeneStatus:
    """What HGNC currently says about one authored gene symbol."""

    symbol: str
    state: str                       # approved | retired | unknown
    current: Optional[str] = None
    hgnc_id: Optional[str] = None

    def __str__(self) -> str:
        if self.state == "retired":
            return (
                f"{self.symbol} is a previous symbol; HGNC's approved symbol is {self.current} "
                f"({self.hgnc_id}). Sources keyed on the current symbol — gnomAD constraint among "
                f"them — will not match the authored one."
            )
        if self.state == "unknown":
            return (
                f"{self.symbol} is neither an approved nor a previous HGNC symbol — a typo, or a "
                f"locus/cluster name that HGNC does not carry"
            )
        return f"{self.symbol} is the approved HGNC symbol"


@dataclass
class IdentifierReport:
    rsids: list[RsidStatus] = field(default_factory=list)
    traits: list[TraitStatus] = field(default_factory=list)
    genes: list[GeneStatus] = field(default_factory=list)

    @property
    def stale_rsids(self) -> list[RsidStatus]:
        return [r for r in self.rsids if r.state != "live"]

    @property
    def stale_traits(self) -> list[TraitStatus]:
        return [t for t in self.traits if t.state in {"obsolete", "absent"}]

    @property
    def stale_genes(self) -> list[GeneStatus]:
        return [g for g in self.genes if g.state != "approved"]

    @property
    def clean(self) -> bool:
        return not (self.stale_rsids or self.stale_traits or self.stale_genes)


# ── dbSNP ───────────────────────────────────────────────────────────────────────────────────────


def classify_rsid(rsid: str, record: dict[str, Any]) -> RsidStatus:
    """One esummary record → `live` / `merged` / `absent`.

    Split out from the batch so the state machine is testable against the recorded payload directly.
    `snp_id` comes back as an int and the uid as a string, so both sides are normalized before
    comparison — comparing them raw would classify every live rsID as merged.
    """
    if is_missing(record):
        return RsidStatus(rsid=rsid, state="absent")
    requested = rsid.removeprefix("rs")
    served = record.get("snp_id")
    merged = str(record.get("merged_sort") or "0") == "1"
    if served is not None and str(served) != requested:
        return RsidStatus(rsid=rsid, state="merged", current=f"rs{served}")
    if merged:
        # dbSNP flagged a merge but served the requested id back — record it rather than silently
        # calling it live, since the two signals disagree.
        logger.info("%s: merged_sort=1 but snp_id is the requested id; treated as live", rsid)
    return RsidStatus(rsid=rsid, state="live")


def check_rsids(rsids: list[str], *, client: Optional[EutilsClient] = None) -> list[RsidStatus]:
    """Current/merged/absent for each authored rsID, batched through `esummary db=snp`.

    **Report, never repair — and here that is load-bearing rather than tidy.** `weights.parquet`
    carries both `variant_key` and `rsid`, and for an rsid-authored row they are the same label.
    Writing the merged-into id back would not be a one-time digest move but an *identity migration
    performed by a network lookup*: reverse would emit the new rsID into `variants.csv`, the next
    compile would key on it, and `variant_key` itself would change with no authored edit anywhere.
    The module's identity would drift and the round-trip would stop being a fixed point (Principle 7).
    """
    wanted = dedupe(r for r in rsids if r)
    if not wanted:
        return []
    owned = client is None
    eutils = client or EutilsClient()
    try:
        records = eutils.esummary("snp", [r.removeprefix("rs") for r in wanted])
    finally:
        if owned:
            eutils.close()
    return [classify_rsid(rsid, records.get(rsid.removeprefix("rs"), {})) for rsid in wanted]


# ── ontology terms (OLS4) and gene symbols (HGNC) ───────────────────────────────────────────────


@dataclass
class OntologyClient:
    """OLS4 + HGNC lookups. One class because both are unbatched GET-per-id REST services.

    Neither publishes a documented rate limit, so the gate is a courtesy rather than a budget — but it
    is here rather than absent, because a module with two hundred genes would otherwise open two
    hundred connections as fast as it could.
    """

    ols4_base: str = DEFAULT_OLS4_BASE
    hgnc_base: str = DEFAULT_HGNC_BASE
    min_request_interval: float = 0.2
    timeout: float = 30.0
    gate: Optional[PacingGate] = None
    _client: Optional[httpx.Client] = None

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(self.min_request_interval)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout, follow_redirects=True,
                headers={"Accept": "application/json"},
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "OntologyClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1.0, max=10.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _get(self, url: str, params: Optional[dict] = None) -> httpx.Response:
        assert self.gate is not None
        self.gate.wait()
        return self._http().get(url, params=params)

    def trait(self, curie: str) -> TraitStatus:
        """Existence, obsolescence and the replacement term for one ontology CURIE."""
        match = _CURIE.match(curie.strip())
        if match is None:
            return TraitStatus(curie=curie, state="unchecked")
        prefix, local = match.group(1).upper(), match.group(2)
        route = _ONTOLOGY_IRI.get(prefix)
        if route is None:
            return TraitStatus(curie=curie, state="unchecked")
        ontology, stem = route
        response = self._get(
            f"{self.ols4_base.rstrip('/')}/ontologies/{ontology}/terms",
            {"iri": f"{stem}{prefix}_{local}"},
        )
        if response.status_code == 404:
            return TraitStatus(curie=curie, state="absent")
        response.raise_for_status()
        terms = (response.json().get("_embedded") or {}).get("terms") or []
        if not terms:
            return TraitStatus(curie=curie, state="absent")
        term = terms[0]
        if term.get("is_obsolete"):
            return TraitStatus(
                curie=curie, state="obsolete", label=term.get("label"),
                replaced_by=_curie_from_iri(term.get("term_replaced_by")),
            )
        return TraitStatus(curie=curie, state="current", label=term.get("label"))

    def gene(self, symbol: str) -> GeneStatus:
        """Approved / retired / unknown for one gene symbol.

        Uses the **exact** `fetch/` endpoints, never `search/`: `search/BRCA1` is fuzzy and returns 19
        hits including `ABRAXAS1`, which would make every symbol look ambiguous. `fetch/symbol` answers
        currency; `fetch/prev_symbol` answers retirement, and is only consulted when the first misses.
        """
        approved = self._hgnc(f"symbol/{symbol}")
        if approved:
            return GeneStatus(
                symbol=symbol, state="approved", current=approved[0].get("symbol"),
                hgnc_id=approved[0].get("hgnc_id"),
            )
        previous = self._hgnc(f"prev_symbol/{symbol}")
        if previous:
            return GeneStatus(
                symbol=symbol, state="retired", current=previous[0].get("symbol"),
                hgnc_id=previous[0].get("hgnc_id"),
            )
        return GeneStatus(symbol=symbol, state="unknown")

    def _hgnc(self, path: str) -> list[dict]:
        response = self._get(f"{self.hgnc_base.rstrip('/')}/fetch/{path}")
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return (response.json().get("response") or {}).get("docs") or []


def _curie_from_iri(iri: Optional[str]) -> Optional[str]:
    """`http://purl.obolibrary.org/obo/MONDO_0005010` → `MONDO_0005010`."""
    if not iri:
        return None
    return iri.rstrip("/").rsplit("/", 1)[-1]


# ── the pass ────────────────────────────────────────────────────────────────────────────────────


def module_trait_ids(variants: list[VariantRow]) -> list[str]:
    """Every ontology CURIE the module names, de-duplicated in first-occurrence order.

    `trait_efo_id` is a multi-valued cell (comma/semicolon/pipe-separated), so one row can name
    several traits.
    """
    out: list[str] = []
    for variant in variants:
        if not variant.trait_efo_id:
            continue
        out.extend(part.strip() for part in MULTI_SEP.split(variant.trait_efo_id) if part.strip())
    return dedupe(out)


def check_identifiers(
    variants: list[VariantRow],
    *,
    check_traits: bool = True,
    check_genes: bool = True,
    client: Optional[OntologyClient] = None,
) -> IdentifierReport:
    """Ontology-term and gene-symbol currency for one module's authored identifiers.

    rsIDs are deliberately **not** done here: they are checked inside `enrich()`, because their verdict
    lands on `resolution.csv` columns rather than being a standalone report. See `check_rsids`.
    """
    report = IdentifierReport()
    traits = module_trait_ids(variants) if check_traits else []
    genes = dedupe(v.gene for v in variants if v.gene) if check_genes else []
    if not traits and not genes:
        return report

    owned = client is None
    ontology = client or OntologyClient()
    try:
        report.traits = [ontology.trait(curie) for curie in traits]
        report.genes = [ontology.gene(symbol) for symbol in genes]
    finally:
        if owned:
            ontology.close()
    return report
