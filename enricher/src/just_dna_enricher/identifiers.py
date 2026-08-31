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
from pathlib import Path
from typing import Any

import httpx
from just_dna_compiler.compiler import load_csv_rows, load_spec_variants
from just_dna_compiler.draft import DRAFTABLE
from just_dna_format.base import AuthoredModel
from just_dna_format.layout import SidecarCollision, resolve_sidecar
from just_dna_format.manifest import VerificationRecord
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import MULTI_SEP
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
)

from just_dna_enricher.eutils import EutilsClient, EutilsError, is_missing
from just_dna_enricher.licensing import overlaid_input_rows
from just_dna_enricher.net import PacingGate, attempt_floor, dedupe
from just_dna_enricher.verification import examples, ran, skipped

logger = logging.getLogger(__name__)

DEFAULT_OLS4_BASE = "https://www.ebi.ac.uk/ols4/api"
DEFAULT_HGNC_BASE = "https://rest.genenames.org"

# CURIE prefix → (OLS4 ontology id, the FULL IRI prefix its terms sit under, local id appended).
#
# The IRI prefix is stored whole rather than assembled from the CURIE prefix, because those two are
# not the same string in general — Orphanet is the counter-example that forced this: `ORPHA:558` is a
# term at `…/ORDO/Orphanet_558`, so composing `stem + PREFIX + "_" + local` would have queried
# `…/ORDO/ORPHA_558`. That yields HTTP 200 with zero terms, which is indistinguishable from "this id
# does not exist" — the failure would have looked like a finding about the module rather than a bug
# here. EFO mints its own namespace, the OBO ontologies share a PURL, Orphanet has its own.
_ONTOLOGY_IRI: dict[str, tuple[str, str]] = {
    "EFO": ("efo", "http://www.ebi.ac.uk/efo/EFO_"),
    "MONDO": ("mondo", "http://purl.obolibrary.org/obo/MONDO_"),
    "HP": ("hp", "http://purl.obolibrary.org/obo/HP_"),
    "OBA": ("oba", "http://purl.obolibrary.org/obo/OBA_"),
    # Both spellings are in real use for Orphanet; neither matches the IRI's own `Orphanet_`.
    "ORPHA": ("ordo", "http://www.orpha.net/ORDO/Orphanet_"),
    "ORPHANET": ("ordo", "http://www.orpha.net/ORDO/Orphanet_"),
}
_CURIE = re.compile(r"^([A-Za-z]+)[:_](\w+)$")


class IdentifierCheckError(RuntimeError):
    """A currency lookup failed outright (transport or an unusable response)."""


class IdentifierUnavailable(IdentifierCheckError):
    """A source this pass asks was not reachable, so the question could not be put (RM101).

    A subclass rather than a second exception, for `AcmgListUnavailable`'s reason: every existing
    `except IdentifierCheckError` still catches it, and the two histories this module can fail with
    stop being one type. Only this one means a source was *asked*; an invalid local `variants.csv` is
    the plain parent, and a caller separating them had to read `__cause__` to do it.

    It carries no `skip` member, unlike `AcmgListUnavailable`, and the reason is not that nothing
    attests — `check-identifiers` does, and getting this wrong once is how the first draft of this
    class shipped a false docstring. The difference is *where the member is decided*. `acmg` raises
    from several places that mean different skips, so the raiser is the only thing that knows which;
    here every raise means the same one, and `unreachable_records()` already owns it for all three
    checks at once. Putting it on the exception would be a second place to keep the same fact.
    """


# ── findings ────────────────────────────────────────────────────────────────────────────────────


@dataclass
class RsidStatus:
    """What dbSNP currently says about one authored rsID."""

    rsid: str
    state: str                       # live | merged | absent | withdrawn
    current: str | None = None    # the surviving rsID, when merged

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
    label: str | None = None
    replaced_by: str | None = None

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
    current: str | None = None
    hgnc_id: str | None = None
    #: HGNC's cytogenetic band, e.g. `16q12.2`, `Xp22.33`, `mitochondria`. Kept verbatim; the
    #: chromosome is derived from it rather than stored, so there is one place the parse can be wrong.
    location: str | None = None

    @property
    def chromosome(self) -> str | None:
        """The contig the band names, or `None` when HGNC gave none or it cannot be read.

        Band syntax is `<chrom><arm><band>`, so the contig is everything before the first `p`/`q` —
        except `mitochondria`, which HGNC spells out and this codebase calls `MT`. Alternate-reference
        loci (`19q13.42 alternate reference locus`) keep their leading band, so the split still works.
        `None` for anything unparsed, because a guess here becomes a false accusation about a row."""
        if not self.location:
            return None
        raw = self.location.strip()
        if raw.lower().startswith("mitochondri"):
            return "MT"
        head = re.split(r"[pq]", raw, maxsplit=1)[0].strip()
        return head if re.fullmatch(r"(?:[1-9]|1[0-9]|2[0-2]|X|Y)", head) else None

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
class GeneLocusConflict:
    """An authored `gene` whose HGNC chromosome is not the chromosome the row's variant sits on.

    The relationship is false while both halves are individually true — the rsID resolves, the symbol
    is approved — which is why nothing caught it before (S24). It is the signature of a generated
    citation: a real gene name beside an invented rs number, which resolves anyway because dbSNP is
    dense enough that almost any seven-digit number hits something. Four of one reporter's seven rows
    were this, each pairing a real symbol with a variant on another chromosome.
    """

    gene: str
    gene_chrom: str
    variant_key: str
    variant_chrom: str

    def __str__(self) -> str:
        return (
            f"{self.variant_key} is on chromosome {self.variant_chrom}, but HGNC puts {self.gene} on "
            f"chromosome {self.gene_chrom} — the row pairs a gene with a variant that is not in it. "
            f"Check the identifier against the source you took it from; a real symbol beside an "
            f"invented rsID is what a machine-written summary produces."
        )


@dataclass
class IdentifierReport:
    rsids: list[RsidStatus] = field(default_factory=list)
    traits: list[TraitStatus] = field(default_factory=list)
    genes: list[GeneStatus] = field(default_factory=list)
    #: Rows whose `gene` and resolved chromosome disagree. Reported, never repaired — which of the two
    #: is wrong is not something this tier can know.
    gene_loci: list[GeneLocusConflict] = field(default_factory=list)
    #: Why the comparison above did not run, or `None` when it did. An empty conflict list otherwise
    #: says two opposite things — "compared everything, nothing disagreed" and "never compared" — the
    #: same reason `EnrichmentResult.clin_sig_not_checked` exists.
    gene_loci_not_checked: str | None = None
    #: How many rows the comparison above actually judged — the denominator `gene_loci` is out of.
    #: It comes from the check rather than from a caller recounting `variants` (RM72): a row whose gene
    #: HGNC does not place, or whose variant has no known chromosome, was never compared, and counting
    #: it would publish a coverage figure larger than the question that was put. A PAR-exempt row
    #: **is** counted: it was compared and found not to contradict itself.
    gene_loci_compared: int = 0
    #: Which authored tables the trait roster was actually built from, and which were not, with the
    #: reason (S86). Empty lists are honest: `traits == []` with `trait_tables_read == []` is a
    #: different statement from `traits == []` after reading nine tables, and only the second is a
    #: clean bill. Same rule as `gene_loci_not_checked` above and `unconsulted_rsids` one tier down —
    #: a question never put is not an answer, and `0` must never have to mean both.
    trait_tables_read: list[str] = field(default_factory=list)
    trait_tables_not_read: dict[str, str] = field(default_factory=dict)
    #: The same pair for gene symbols. The gene half of the roster was narrow for the same reason and
    #: was filed with it: a `gene` on a binning or PGx row was never checked either.
    gene_tables_read: list[str] = field(default_factory=list)
    gene_tables_not_read: dict[str, str] = field(default_factory=dict)

    @property
    def unreadable_tables(self) -> dict[str, str]:
        """Tables that exist and would not parse, across both columns — never merely absent ones.

        The actionable half: an absent optional table is the normal shape of every module, while one
        that is present and unreadable means ids the module carries went unchecked.
        """
        return {
            name: why
            for source in (self.trait_tables_not_read, self.gene_tables_not_read)
            for name, why in source.items()
            if why != "not present"
        }

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
        return not (self.stale_rsids or self.stale_traits or self.stale_genes or self.gene_loci)


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


def check_rsids(rsids: list[str], *, client: EutilsClient | None = None) -> list[RsidStatus]:
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
    except EutilsError as exc:
        # dbSNP is a *different* module's client, so `EutilsError` is not this module's type
        # and `except IdentifierCheckError` around `check_rsids` never fired for a 5xx.
        raise IdentifierUnavailable(f"dbSNP could not be reached: {exc}") from exc
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
    gate: PacingGate | None = None
    _client: httpx.Client | None = None

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
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=1.0, max=10.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _request(self, url: str, params: dict | None = None) -> httpx.Response:
        assert self.gate is not None
        self.gate.wait()
        return self._http().get(url, params=params)

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        """One GET, with `httpx` translated away — `@client-exception-contract`, RM97's leftover.

        RM97 repaired `gnomad._post` and `eutils._get` and this client kept the unrepaired shape, so
        a 5xx from OLS4 or HGNC arrived as a raw `httpx.HTTPStatusError`: `raise_for_status()` sat in
        the *callers* (`trait`, `_hgnc`) with `HTTPStatusError` in neither retry list, and the
        transport leg is re-raised bare on purpose for the decorator, so it escaped raw too once
        `reraise=True` exhausted the attempts. The guard that should have caught this walked eight
        named modules and `identifiers` was not one of them — `@registry-completeness`.

        **A 404 is returned, not raised.** It is this client's normal "no such term / symbol" answer
        and both callers read it as `absent`; translating it into an error would turn an answered
        question into an unasked one, which is the distinction this tier draws everywhere else.
        """
        try:
            response = self._request(url, params)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise IdentifierUnavailable(f"{url} could not be reached: {exc}") from exc
        if response.status_code == 404:
            return response
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise IdentifierUnavailable(f"{url} answered {response.status_code}: {exc}") from exc
        return response

    def trait(self, curie: str) -> TraitStatus:
        """Existence, obsolescence and the replacement term for one ontology CURIE."""
        match = _CURIE.match(curie.strip())
        if match is None:
            return TraitStatus(curie=curie, state="unchecked")
        prefix, local = match.group(1).upper(), match.group(2)
        route = _ONTOLOGY_IRI.get(prefix)
        if route is None:
            return TraitStatus(curie=curie, state="unchecked")
        ontology, iri_prefix = route
        response = self._get(
            f"{self.ols4_base.rstrip('/')}/ontologies/{ontology}/terms",
            {"iri": f"{iri_prefix}{local}"},
        )
        if response.status_code == 404:
            return TraitStatus(curie=curie, state="absent")
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
                hgnc_id=approved[0].get("hgnc_id"), location=approved[0].get("location"),
            )
        previous = self._hgnc(f"prev_symbol/{symbol}")
        if previous:
            return GeneStatus(
                symbol=symbol, state="retired", current=previous[0].get("symbol"),
                hgnc_id=previous[0].get("hgnc_id"), location=previous[0].get("location"),
            )
        return GeneStatus(symbol=symbol, state="unknown")

    def _hgnc(self, path: str) -> list[dict]:
        response = self._get(f"{self.hgnc_base.rstrip('/')}/fetch/{path}")
        if response.status_code == 404:
            return []
        return (response.json().get("response") or {}).get("docs") or []


def _curie_from_iri(iri: str | None) -> str | None:
    """`http://purl.obolibrary.org/obo/MONDO_0005010` → `MONDO_0005010`."""
    if not iri:
        return None
    return iri.rstrip("/").rsplit("/", 1)[-1]


# ── the pass ────────────────────────────────────────────────────────────────────────────────────


def module_trait_ids(variants: list[VariantRow]) -> list[str]:
    """Every ontology CURIE the module's **`variants.csv` rows** name, in first-occurrence order.

    `trait_efo_id` is a multi-valued cell (comma/semicolon/pipe-separated), so one row can name
    several traits.

    **This is the roster of one table, and eleven authored tables carry the column.** Kept as-is
    because a caller holding rows is the only thing it can serve, and widened where the tables are
    actually reachable: `authored_identifiers` below takes a spec directory and reads all of them.
    A caller passing `variants=` gets this narrow roster and is told so (S86).
    """
    out: list[str] = []
    for variant in variants:
        if not variant.trait_efo_id:
            continue
        out.extend(part.strip() for part in MULTI_SEP.split(variant.trait_efo_id) if part.strip())
    return dedupe(out)


def _id_bearing_tables(column: str) -> dict[str, type[BaseModel]]:
    """`{filename: model}` for every **authored** table whose model declares `column`.

    **Derived from `DRAFTABLE`, never restated** (`@registry-completeness`). The defect this repairs
    is a roster that named one table while eleven carry the column, so a hand-kept list here would be
    the same bug with a longer literal in it: a table kind added later must join this set by existing,
    not by someone remembering. `DRAFTABLE` is the filename→model map the authoring surfaces already
    share, and it is built from `_TABLE_KINDS`, so it carries every optional kind by construction.

    `MeasureBinRow` is deliberately absent and nothing is missed: it is the abstract base, and its four
    concrete subclasses are each their own `DRAFTABLE` entry. A test asserts this set equals the walk
    over `_ALL_MODELS` minus that base, which is what would catch a kind that never reached `DRAFTABLE`.

    **Authored only.** `GeneMetricsRow`, `GeneValidityRow` and `GwasEffectRow` carry these columns too
    and are excluded: they are machine-written from a source, so a stale id in one is the *source's*
    currency and belongs to the pass that wrote it — checking it here would report a finding no author
    can act on, and `dataset_currency` is the surface that asks that question.
    """
    return {
        name: model
        for name, model in DRAFTABLE.items()
        if isinstance(model, type)
        and issubclass(model, AuthoredModel)
        and column in model.model_fields
    }


@dataclass
class IdentifierRoster:
    """The ids an authored spec names, with the tables that were and were not read (S86).

    `not_read` is the point of the type. A bare roster cannot distinguish *this module declares no
    trait* from *this module's traits are in a table nobody read*, and both render as `0 checked,
    0 clean, 0 flagged` — which reads as a clean run and let a module ship a retired CURIE with every
    gate green. Same three-valued rule as `gene_loci_not_checked` two fields down in the report, and
    as `unconsulted_rsids` one tier down: a question never put is not an answer.
    """

    ids: list[str] = field(default_factory=list)
    #: Filenames actually opened and parsed, sorted. The denominator behind `ids`.
    read: list[str] = field(default_factory=list)
    #: `{filename: why}` for a table that carries the column and was not read — it is absent from the
    #: spec (the common and benign case), or it could not be parsed (which is not benign at all, and
    #: is why the reason is carried rather than the file merely omitted).
    not_read: dict[str, str] = field(default_factory=dict)

    @property
    def unreadable(self) -> dict[str, str]:
        """Only the tables that exist and failed to parse — the half worth warning about."""
        return {name: why for name, why in self.not_read.items() if why != "not present"}


def authored_identifiers(spec_dir: Path, column: str) -> IdentifierRoster:
    """Every value of `column` across every authored table that declares it, and what was read.

    The roster `check_identifiers` runs on when it is given a spec directory. Rows are loaded with the
    same `load_csv_rows` the compiler uses, so a table this cannot parse is reported as unread rather
    than skipped silently — the distinction the whole item is about.

    Multi-valued cells are split on `MULTI_SEP` for **both** columns. A `gene` cell is single-valued in
    practice, and splitting it costs nothing and cannot mis-read one: a symbol contains no separator.
    """
    roster = IdentifierRoster()
    for name, model in sorted(_id_bearing_tables(column).items()):
        try:
            table = resolve_sidecar(spec_dir, name) or spec_dir / name
        except SidecarCollision as exc:
            roster.not_read[name] = str(exc)
            continue
        if not table.exists():
            roster.not_read[name] = "not present"
            continue
        rows, errors, _ = load_csv_rows(table, model, table.name)
        if errors:
            # Read-only pass: an unparseable table is a *reason a question was not put*, never a
            # failure of this check. Dying here would say nothing about the ids the module does carry.
            roster.not_read[name] = f"could not be read ({errors[0]})"
            continue
        roster.read.append(name)
        for row in rows:
            value = getattr(row, column, None)
            if not value:
                continue
            roster.ids.extend(part.strip() for part in MULTI_SEP.split(value) if part.strip())
    roster.ids = dedupe(roster.ids)
    return roster


def check_identifiers(
    variants: list[VariantRow] | None = None,
    *,
    spec_dir: Path | None = None,
    check_traits: bool = True,
    check_genes: bool = True,
    client: OntologyClient | None = None,
) -> IdentifierReport:
    """Ontology-term and gene-symbol currency for one module's authored identifiers.

    rsIDs are deliberately **not** done here: they are checked inside `enrich()`, because their verdict
    lands on `resolution.csv` columns rather than being a standalone report. See `check_rsids`.

    **Pass either `variants` or `spec_dir` (RM41)** — the row-taking form is right for an in-process
    caller that already holds the rows, and `spec_dir=` is the shape every other pass in this tier has.
    Exactly one, never both: two answers in mind, and silently preferring one is a guess.
    """
    if (variants is None) == (spec_dir is None):
        raise ValueError(
            "pass exactly one of variants= (rows you already hold) or spec_dir= (a module spec "
            "directory, loaded with the module's declared genome_build)"
        )
    if variants is None:
        # **An absent `variants.csv` is a module shape, not an error** — the format has never made the
        # table mandatory, and the four PGx kinds a module can be built entirely out of are among the
        # nine this pass now reads. Loading unconditionally raised `variants.csv is invalid: ... not
        # found` on every one of them, so the roster S86 widened could not be reached from a spec
        # directory at all: the CLI's own guard was returning before this line and hiding it. These
        # rows are wanted for exactly one thing — placing a gene symbol against the chromosome its
        # variant resolves to — and a module with none simply has nothing to place, which
        # `_gene_locus_conflicts` reports as its own reason rather than as a silent zero.
        #
        # Present-and-unparseable still raises. That is a module whose rows exist and cannot be read,
        # which is the author's to fix and not a shape.
        if (Path(spec_dir) / "variants.csv").exists():
            variants, errors, _ = load_spec_variants(Path(spec_dir))
            if errors:
                raise ValueError(f"variants.csv is invalid: {errors[0]}")
        else:
            variants = []
    report = IdentifierReport()
    # **The roster is every authored table carrying the column, not `variants.csv` alone (S86).** It
    # read one table while eleven declare `trait_efo_id`/`gene`, so a module whose traits live in
    # `studies.csv` — where `StudyRow` has carried the column since 0.3 — reported `0 checked, 0 clean,
    # 0 flagged` and shipped a retired CURIE with every gate green. `0` said two things at once: *this
    # module declares no trait* and *its traits are in a table nobody read*.
    #
    # A caller passing `variants=` still gets the narrow roster, because rows in hand are all it has;
    # `tables_not_read` then records that, so the narrow case is stated rather than silently equal to
    # the wide one.
    if spec_dir is not None:
        trait_roster = authored_identifiers(Path(spec_dir), "trait_efo_id")
        gene_roster = authored_identifiers(Path(spec_dir), "gene")
    else:
        trait_roster = IdentifierRoster(
            ids=module_trait_ids(variants),
            read=["variants.csv"],
            not_read={
                name: "rows were passed in, so only variants.csv was available"
                for name in sorted(_id_bearing_tables("trait_efo_id"))
                if name != "variants.csv"
            },
        )
        gene_roster = IdentifierRoster(
            ids=dedupe(v.gene for v in variants if v.gene),
            read=["variants.csv"],
            not_read={
                name: "rows were passed in, so only variants.csv was available"
                for name in sorted(_id_bearing_tables("gene"))
                if name != "variants.csv"
            },
        )
    traits = trait_roster.ids if check_traits else []
    genes = gene_roster.ids if check_genes else []
    # Recorded whether or not anything was found, and **before** the early return below: a roster that
    # came back empty is exactly the case where a reader needs to know which tables were behind it.
    if check_traits:
        report.trait_tables_read = trait_roster.read
        report.trait_tables_not_read = trait_roster.not_read
    if check_genes:
        report.gene_tables_read = gene_roster.read
        report.gene_tables_not_read = gene_roster.not_read
    for column, roster in (("trait_efo_id", trait_roster), ("gene", gene_roster)):
        for name, why in sorted(roster.unreadable.items()):
            # An absent table is the normal case and says nothing; one that exists and will not parse
            # means the check silently skipped ids the module really does carry.
            logger.warning(
                "%s carries %s and could not be read (%s), so its identifiers were not checked. "
                "The counts below are out of the tables that were.", name, column, why,
            )
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
    if check_genes:
        (
            report.gene_loci,
            report.gene_loci_compared,
            report.gene_loci_not_checked,
        ) = _gene_locus_conflicts(variants, report.genes, Path(spec_dir) if spec_dir else None)
    return report


def _variant_chromosomes(
    variants: list[VariantRow], spec_dir: Path | None
) -> tuple[dict[str, str], str | None]:
    """`{variant_key: chrom}` for every row whose chromosome is known, and why it may be empty.

    An authored `chrom` is used directly; for an rsID-only row the chromosome exists only after
    resolution, so an injected `resolution.csv` beside the spec is read — the same table the compiler
    consumes and `enrich()` treats as authoritative. Nothing is fetched here: this pass already spends
    its network budget on HGNC, and reaching for Ensembl would make a *currency* check depend on a
    resolver.
    """
    known = {v.variant_key: v.chrom for v in variants if v.chrom}
    if spec_dir is None:
        return known, None if known else "no coordinates authored and no spec directory to look beside"
    # Read-only, so a collision here is a reason the comparison could not run rather than a failure —
    # same shape as every other `gene_loci_not_checked` reason, and it must stay a reason: this check
    # reports on the module's rows, and dying on its layout would say nothing about them.
    try:
        table = resolve_sidecar(spec_dir, "resolution.csv") or spec_dir / "resolution.csv"
    except SidecarCollision as exc:
        return known, str(exc)
    if not table.exists():
        return known, None if known else "no coordinates authored and no resolution.csv beside the spec"
    rows, errors, _ = load_csv_rows(table, ResolutionRow, table.name)
    if errors:
        return known, f"resolution.csv could not be read ({errors[0]})"
    # The overlay, so this check reports on what the module asserts (RM136). Read-only, like the
    # load above, and a broken overlay is a *reason the comparison could not run* rather than a
    # failure — the same shape every other `gene_loci_not_checked` reason has, and it must stay that
    # shape: dying on the module's layout would say nothing about its rows.
    try:
        rows = overlaid_input_rows(spec_dir, "resolution.csv", rows, error=ValueError)
    except ValueError as exc:
        return known, f"overrides.csv could not be applied ({exc})"
    for row in rows:
        if row.chrom and row.variant_key not in known:
            known[row.variant_key] = row.chrom
    return known, None


def _gene_locus_conflicts(
    variants: list[VariantRow], genes: list[GeneStatus], spec_dir: Path | None
) -> tuple[list[GeneLocusConflict], int, str | None]:
    """Compare each row's `gene` against the chromosome its variant resolves to (S24).

    Returns the conflicts, **how many rows were actually compared**, and why the comparison did not
    run. The middle number is the attestation's denominator and is counted here rather than by the
    caller (RM72): only this loop knows which rows had both halves.

    **Chromosome granularity only, deliberately, and the stronger version is wrong.** A row may
    legitimately name a nearest or implicated gene for a variant outside the gene body, and the
    mechanism can be genuinely distal — `rs1421085` sits in an FTO intron and acts on *IRX3*/*IRX5*
    megabases away, so a row could reasonably name any of the three. An interval check would fire on
    correct rows and be switched off within a week. Chromosome disagreement has almost no legitimate
    cause, costs one comparison, and catches the whole fabrication class.

    Three-valued as everywhere else: a symbol HGNC does not carry, a band that will not parse, and a
    row with no known chromosome all **withhold** rather than accuse. The one deliberate exemption is a
    pseudoautosomal locus, which is one place on two contigs — `XG` and `SPRY3` straddle a PAR boundary,
    so an X-vs-Y disagreement there is a spelling, not a contradiction.
    """
    if not variants:
        # Placed before the gene check because it is the more specific fact. Since the roster widened,
        # a module carrying no `variants.csv` reaches here with symbols in hand — read off its
        # `haplotypes.csv` or `diplotypes.csv` — and nothing to place them against. Returning
        # `compared=0` with `None` beside it would be the `ran(0, 0)` this pass's attestation
        # explicitly refuses to write.
        return [], 0, (
            "the module carries no variants.csv rows, so no gene symbol could be placed against a "
            "variant's chromosome"
        )
    if not genes:
        # Named apart from the line below, which is a claim about HGNC: with no authored gene, HGNC
        # was never asked, and reporting it as an unhelpful answer would be the same "the source did
        # not say" / "there was nothing to ask" conflation this tier separates everywhere else.
        return [], 0, "no row names a gene, so there was nothing to place on a chromosome"
    chrom_of_gene = {g.symbol: g.chromosome for g in genes if g.chromosome}
    if not chrom_of_gene:
        return [], 0, "HGNC returned no usable chromosome for any authored gene"
    chrom_of_variant, reason = _variant_chromosomes(variants, spec_dir)
    if not chrom_of_variant:
        return [], 0, reason or "no row has a known chromosome"

    conflicts: list[GeneLocusConflict] = []
    compared = 0
    for row in variants:
        gene_chrom = chrom_of_gene.get(row.gene or "")
        row_chrom = chrom_of_variant.get(row.variant_key)
        if not gene_chrom or not row_chrom:
            continue
        compared += 1
        if gene_chrom == row_chrom:
            continue
        if {gene_chrom, row_chrom} == {"X", "Y"}:
            continue        # a PAR locus is one place on two contigs — see `vrs.par_partner`
        conflicts.append(
            GeneLocusConflict(
                gene=row.gene, gene_chrom=gene_chrom,
                variant_key=row.variant_key, variant_chrom=row_chrom,
            )
        )
    return conflicts, compared, None


# ── the attestation (RM72) ──────────────────────────────────────────────────────────────────────


def verification_records(
    report: IdentifierReport, *, check_traits: bool, check_genes: bool
) -> list[VerificationRecord]:
    """The three checks this pass puts, as records `verification.json` can carry (RM72).

    Three records rather than one, because they are three questions over three different subject
    sets: the trait CURIEs the module names, the gene symbols it names, and the rows where a symbol
    and a chromosome could both be established. One record averaging them would be a number nothing
    could act on — the same argument `literature._verification_records` makes for its own three.

    **Every count is read off `report`, and nothing is recounted here.** The denominator belongs to
    the check that produced it; a count recomputed beside a check is one that can disagree with it,
    and then the document's two halves contradict each other.

    **A switched-off check is `not_requested`, an empty subject set is `nothing_to_check`, and a
    comparison whose input was missing is `no_reference` — never `ran(0, 0)`.** A zero out of zero
    reads as a clean bill, which is the whole confusion RM45 exists to end. Only the first of those
    three is cleared by re-running with a different flag, which is why the skip vocabulary keeps them
    apart rather than folding them into one absence.

    This pass fetches nothing on the caller's behalf beyond OLS4 and HGNC, so there is no `offline`
    branch to record: the command has no such flag, and inventing one here would name a state the run
    cannot be in.
    """
    records = [_trait_record(report, check_traits), _gene_symbol_record(report, check_genes)]
    records.append(_gene_locus_record(report, check_genes))
    return records


def unreachable_records(
    *, check_traits: bool, check_genes: bool, detail: str
) -> list[VerificationRecord]:
    """The same three checks, for a run whose registry never answered.

    A request that failed is `unreachable`, never an absence — S20's distinction, and the reason the
    twin command records it too. Without this the command would advertise *records that the question
    was put* and then write nothing on precisely the run where a reader most needs to know the
    question went unanswered.

    Derived from `verification_records` over an empty report rather than restated: the flag a caller
    set is still the truer reason for a check they switched off (a source being down does not make
    `--no-traits` a network problem), and the source names come from the one place that assigns them.
    """
    return [
        record if record.skipped == "not_requested"
        else skipped(record.check, "unreachable", detail=detail, source=record.source)
        for record in verification_records(
            IdentifierReport(), check_traits=check_traits, check_genes=check_genes
        )
    ]


def _trait_record(report: IdentifierReport, check_traits: bool) -> VerificationRecord:
    if not check_traits:
        return skipped("trait_currency", "not_requested", detail="--no-traits", source="ols4")
    if not report.traits:
        return skipped(
            "trait_currency", "nothing_to_check",
            detail="no row carries a trait_efo_id, so there was no term to ask OLS4 about",
            source="ols4",
        )
    # A CURIE whose prefix is outside `_ONTOLOGY_IRI` is answered `unchecked` without a request ever
    # being sent, and `stale_traits` excludes it — so counting it as a subject would put a term nobody
    # asked about into the denominator and never into the numerator, and the clean sentence would
    # claim OLS4 vouched for a term it was never shown. Same rule as `gene_loci_compared` and
    # `AcmgReport.checked`: the denominator is what was examined.
    unresolvable = [t for t in report.traits if t.state == "unchecked"]
    asked = [t for t in report.traits if t.state != "unchecked"]
    if not asked:
        return skipped(
            "trait_currency", "unsupported",
            detail=(
                f"all {len(unresolvable)} authored trait term(s) use a CURIE prefix this check "
                f"cannot resolve: " + examples([t.curie for t in unresolvable])
            ),
            source="ols4",
        )
    stale = report.stale_traits
    detail = (
        f"{len(stale)} of {len(asked)} authored trait term(s) are obsolete or absent: "
        + examples([t.curie for t in stale])
        if stale
        else f"every one of {len(asked)} authored trait term(s) is current in OLS4"
    )
    if unresolvable:
        detail += (
            f"; {len(unresolvable)} further term(s) use a CURIE prefix this check cannot resolve "
            f"({examples([t.curie for t in unresolvable])}) and are outside this denominator"
        )
    return ran(
        "trait_currency",
        subjects=len(asked),
        findings=len(stale),
        source="ols4",
        detail=detail,
    )


def _gene_symbol_record(report: IdentifierReport, check_genes: bool) -> VerificationRecord:
    if not check_genes:
        return skipped("gene_symbol_currency", "not_requested", detail="--no-genes", source="hgnc")
    if not report.genes:
        return skipped(
            "gene_symbol_currency", "nothing_to_check",
            detail="no row names a gene, so there was no symbol to ask HGNC about",
            source="hgnc",
        )
    stale = report.stale_genes
    detail = (
        f"{len(stale)} of {len(report.genes)} authored gene symbol(s) are retired or unknown to "
        f"HGNC: " + examples([g.symbol for g in stale])
        if stale
        else f"every one of {len(report.genes)} authored gene symbol(s) is HGNC-approved"
    )
    return ran(
        "gene_symbol_currency",
        subjects=len(report.genes),
        findings=len(stale),
        source="hgnc",
        detail=detail,
    )


def _gene_locus_record(report: IdentifierReport, check_genes: bool) -> VerificationRecord:
    """The gene↔chromosome comparison, whose skip reason the report already carries in prose.

    `gene_loci_not_checked` is the sentence and it stays the sentence — the closed member is what a
    consumer branches on, and the reasons this check declines all reduce to one of them: an input the
    comparison needed was not there (`no_reference`), or there was nothing to compare
    (`nothing_to_check`). Mapping is done here rather than in the CLI so no caller has to pick a
    vocabulary member from a message.
    """
    if not check_genes:
        return skipped(
            "gene_locus_agreement", "not_requested",
            detail="--no-genes: the comparison joins HGNC's cytoband, which was not fetched",
            source="hgnc",
        )
    if not report.genes:
        # Checked before the prose reason, because "nothing to ask" and "asked and got nothing back"
        # are the two absences this vocabulary exists to keep apart.
        return skipped(
            "gene_locus_agreement", "nothing_to_check",
            detail=report.gene_loci_not_checked or "no row names a gene",
            source="hgnc",
        )
    if report.gene_loci_not_checked:
        return skipped(
            "gene_locus_agreement", "no_reference",
            detail=report.gene_loci_not_checked, source="hgnc",
        )
    if not report.gene_loci_compared:
        return skipped(
            "gene_locus_agreement", "nothing_to_check",
            detail=(
                "no row has both a gene HGNC places on a chromosome and a chromosome of its own "
                "(authored, or resolved in an injected resolution.csv)"
            ),
            source="hgnc",
        )
    detail = (
        f"{len(report.gene_loci)} of {report.gene_loci_compared} comparable row(s) pair a gene with "
        f"a variant on another chromosome: "
        + examples([f"{c.variant_key}/{c.gene}" for c in report.gene_loci])
        if report.gene_loci
        else f"the gene and the chromosome agree on all {report.gene_loci_compared} comparable row(s)"
    )
    return ran(
        "gene_locus_agreement",
        subjects=report.gene_loci_compared,
        findings=len(report.gene_loci),
        source="hgnc",
        detail=detail,
    )
