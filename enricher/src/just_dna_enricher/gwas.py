"""The NHGRI-EBI GWAS Catalog pass — published effect sizes as a derived fact table (0.6, RM90).

Fills `gwas_effects.csv` for the variants `variants.csv` names, from the Catalog's REST API **v2**
(RM354). What it does **not** do is fill `weight`: a consumer asked for exactly that and it is barred —
MODULE_LIFECYCLE § Stage 3 names `weight`/`direction`/`effect_size` in the cells no tool fills, and
every check in this tier reports rather than repairs. The effect lands in its own table beside the
authored column, and a consumer chooses between them wholesale.

**The legacy API is gone.** `/gwas/rest/api/singleNucleotidePolymorphisms/<rsid>/associations`, which
this pass read from 0.6 until 2026-11-04, answers HTTP 410 on every path with "This legacy GWAS
Catalog REST API is no longer available". A 410 now raises `GwasRetired`, never the plain could-not-ask
`GwasError`, because a source that moved and a source that is down are cleared by different things.

**Everything below was established by probing v2 on 2026-11-04** (`/gwas/rest/api/v2/associations?
rs_id=`), not from its migration guide, and these findings shaped the pass:

* **The association is fat now, and the request budget collapsed with it.** `pubmed_id`,
  `accession_id` and `efo_traits` sit on the association itself, so the legacy `1 + 2N` per variant
  (a study and a trait link per association, measured at 382 requests for one real module) is gone.
  Ancestry is the one fact still behind a request — `/studies/<accession>/ancestries` — so the cost is
  one request per page plus one per **distinct** study, and `_LinkCache` keyed on that URL now pays.
* **It pages, 20 per page by default.** rs4149056 carries 386 associations. The pass asks for large
  pages and follows `_links.next` until there is none, so a server that caps the size loses nothing,
  and every page is counted in the request total.
* **The empty answer is a 200 with no `_embedded` key at all**, `page.totalElements: 0` — for an rsID
  the Catalog has never heard of as much as for a rare clinical one. The legacy API 404'd there
  instead, so the meaning of a 404 flipped: on the v2 search path it is a wrong path, never an answer.
* **The effect is one composite string**, `"0.05 umol/l increase"` (or `"-"` when the association is
  an odds ratio, which sits in `or_per_copy_num`). The legacy `betaNum` / `betaUnit` /
  `betaDirection` come out of it by one grammar; a string outside it is withheld whole and counted.
  The unit is kept verbatim between the number and the direction — one study writes U+2009 in it.
* **`snp_effect_allele` is `rs4149056-C`, or `rs4149056-?` when the study never established which
  allele carries the effect** — the legacy `riskAlleleName` grammar, unchanged. `-?` becomes `None`,
  never a guess, and the row is still written: an effect relative to an unknown allele is real
  evidence that cannot be used as a weight.
* **The unit is free text and frequently uninterpretable** — `umol/l` on one association and `unit`
  on many others for the same variant. It is stored verbatim including the useless values, because
  "these betas are on unknown and possibly different scales" is the fact a consumer must have.
* **v2 publishes no standard error.** `standard_error` stays null on every row this pass writes.
* **The p-value has its curated pair back.** `p_value` is `0.0` past float64's range, as before, but
  `pvalue_mantissa`/`pvalue_exponent` beside it still say `3e-493`; the verbatim string is built
  from the pair, and the queryable number is read from that same string.

**Rate limits are NOT established.** EBI publishes no numeric budget that could be found, which makes
this pass unlike `gnomad.py`, whose 10-requests-per-60-seconds is real, documented and load-bearing.
The gate here is a conservative default rather than a transcribed limit, and it is spelled that way so
nobody later "corrects" it against a number that does not exist.
"""

import csv
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_compiler.compiler import load_csv_rows, load_spec_variants
from just_dna_format.base import merge_key
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.layout import atomic_writer, nothing_to_write
from just_dna_format.normalize import now_utc_iso
from just_dna_format.sources import SourceRow
from pydantic import ValidationError
from tenacity import retry, wait_exponential_jitter

from just_dna_enricher.enrich import (
    EnrichmentError,
    collect_subjects,
    spec_genome_build,
)
from just_dna_enricher.licensing import (
    GWAS_CATALOG_TERMS,
    record_table_sources,
    require_sources_file,
    sidecar_path,
    table_datasets,
)
from just_dna_enricher.net import (
    EndpointRetired,
    PacingGate,
    attempt_floor,
    raise_if_retired,
    release_dataset,
    retry_if_transient,
    stated_release,
)

logger = logging.getLogger(__name__)

DEFAULT_GWAS_ENDPOINT = "https://www.ebi.ac.uk/gwas/rest/api/v2"
#: Where the Catalog states its release (`{"date": "2026-10-29", "ensemblbuild": "116", …}`, read by hand
#: on 2026-11-05). The v2 API states none, so a row's `dataset` is read from here (RM373).
DEFAULT_GWAS_STATS_URL = "https://www.ebi.ac.uk/gwas/api/search/stats"
#: The bare lane a row's `dataset` carries when the Catalog stated no release (`release_dataset`).
GWAS_LANE = "gwas_catalog"
GWAS_SOURCE = GWAS_CATALOG_TERMS.source

#: Derived from the model, never hand-kept — a parallel list is how `SOURCES_FIELDNAMES` lost a column.
_FIELDNAMES: list[str] = list(GwasEffectRow.model_fields)

#: What the Catalog writes when a study did not establish which allele carries the effect.
_UNKNOWN_ALLELE = "?"

#: What it writes for a number the study did not report. An ABSENCE, not a value we cannot hold.
_NOT_REPORTED = "NR"

#: What v2 writes in a composite string field (`beta`, `range`) that has no value — an odds-ratio
#: association's `beta`, say. v2's own null, distinct from a study's `NR`, and also an absence.
_V2_NO_VALUE = "-"

#: v2's `beta`: `<number> [<unit>] <increase|decrease>`. The unit is everything between, verbatim —
#: recorded with a U+2009 in it, which a split-and-join would have rewritten.
_BETA_GRAMMAR = re.compile(r"^(?P<size>\S+)(?:\s+(?P<unit>.*?))?\s+(?P<direction>increase|decrease)$")

#: Associations per page asked for. v2 defaults to 20; the pass still follows `_links.next`.
_PAGE_SIZE = 1000

#: Seconds between requests. **Not a transcribed limit** — see the module docstring. Conservative
#: because the pass can issue several requests per variant and EBI publishes no budget to respect.
DEFAULT_REQUEST_INTERVAL = 1.0


class GwasError(RuntimeError):
    """A GWAS Catalog fetch or parse failed in a way the caller must see.

    Every transport and parse failure is translated into this before it leaves the module. A client
    that leaks `httpx.HTTPError` has no contract — the caller would have to import the transport
    library to catch it, and a swap of transport would silently become a breaking change.
    """


class GwasNotFound(GwasError):
    """The Catalog answered, and it has no record of this variant at all (HTTP 404).

    **A subclass rather than a flag, because this is an answer and not a failure.** Found by running
    the pass against a real module: the Catalog holds only variants with a published genome-wide
    association, so `rs111033563` — a rare clinical HFE variant — 404s rather than returning an empty
    list. The first version of this pass treated that as an outage and died on the first rare variant
    in the module, which is every clinically-authored module.

    It stays inside `GwasError` so a caller that does not care about the distinction still catches
    one type. **Since v2 (RM354) only `follow` treats it as an answer** — one study's ancestry
    withheld. The v2 search answers a variant it holds nothing for with a 200 and zero elements, and
    its only measured 404 was a path that does not exist, so `association_pages` lets this propagate:
    reading it as "no associations" would write a confident negative about a variant nobody could ask
    about.
    """


class GwasRetired(GwasError, EndpointRetired):
    """The Catalog answered HTTP 410 Gone: it retired the endpoint this client asked (RM354).

    **A fact about the source, not an outage.** The legacy REST API began answering 410 on every path
    with "This legacy GWAS Catalog REST API is no longer available", and the generic status arm
    turned that into a plain `GwasError` — the same could-not-ask an outage raises — so a source
    that had moved read as one that was down, and nothing said to upgrade. The message carries the
    URL and the source's own text, which names where it went.

    Not retried: a 410 is an `HTTPStatusError`, which is outside the retry predicate by construction,
    and asking again changes nothing. A subclass of `GwasError` so every existing `except GwasError`
    still catches it; nothing in the tier catches `GwasNotFound` before `GwasError` on a path that
    could see a 410, and `follow`'s `except GwasNotFound` does not match it, so it propagates.
    """


@dataclass
class GwasResult:
    """What one pass did, including what it spent."""

    rows: list[GwasEffectRow] = field(default_factory=list)
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    requests_made: int = 0
    requests_saved: int = 0
    p_value_underflows: int = 0
    #: Associations whose composite effect string (`beta`) is outside the grammar this pass reads, so
    #: their effect columns are withheld whole. Counted for `strict`, like `unusable` (RM354).
    unparsed_effects: int = 0
    #: Associations the Catalog served that this pass could not key on, so they are in no row. Counted
    #: because `strict` reads it (RM100) and because "we dropped some" is not a thing to leave in a log.
    unusable: int = 0
    skipped_offline: bool = False


@dataclass
class _LinkCache:
    """Memoize the per-study follow by URL, and count what the memoization saved.

    On v2 the only follow left is a study's ancestries, so this pays whenever two associations share
    a study (rs4149056: 386 associations, 371 studies). On the legacy API it paid nothing at all.

    The counting is not decoration. The pass's cost is dominated by these follows, the budget it is
    spending is somebody else's, and a number this workspace computes and discards is one every
    operator has to recompute — so the pass reports both halves and the CLI prints them.
    """

    fetch: object
    store: dict[str, dict] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    def get(self, url: str) -> dict:
        if url in self.store:
            self.hits += 1
            return self.store[url]
        self.misses += 1
        payload = self.fetch(url)
        self.store[url] = payload
        return payload


@dataclass
class GwasCatalogClient:
    """Thin REST client for the Catalog, paced and retried.

    `endpoint` and `gate` are injectable so a test can drive the real parsing code against recorded
    payloads without a network or a real sleep — the same shape `EnsemblResolver` and the gnomAD
    client use.
    """

    endpoint: str = DEFAULT_GWAS_ENDPOINT
    stats_url: str = DEFAULT_GWAS_STATS_URL
    timeout: float = 30.0
    gate: PacingGate = field(default_factory=lambda: PacingGate(DEFAULT_REQUEST_INTERVAL))
    _client: httpx.Client | None = None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(multiplier=0.5, max=8.0),
        # Transport, 5xx and 429 since RM354: a v2 pass makes ~190 requests on one module, and one
        # passing 503 sank all of them. A permanent 4xx is never retried.
        retry=retry_if_transient(),
        reraise=True,
    )
    def _request(self, url: str) -> dict:
        """The retrying half, kept separate so the translation sits **outside** the retry (RM208).

        Every leg is translated in `_get`, not here. Before RM354 the status and body legs were
        translated in this body, which was right while the predicate retried transport only — a
        status was a first-and-final attempt by construction. Now a 5xx and a 429 are retried, so
        translating a status here would make it a first-and-final attempt again
        (`test_retry_is_reachable.py`), and every leg moved out together.
        """
        self.gate.wait()
        response = self._http().get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()

    def _get(self, url: str) -> dict:
        """Every way this client can fail, spelled as `GwasError` and its subclasses.

        After the retry has spent its attempts: a 404 is `GwasNotFound`, a 410 `GwasRetired`, any
        other status, an exhausted transport failure or a body that is not JSON a plain `GwasError`.
        The transport leg is the one the retry hands back — `reraise=True` gives the last failure to
        this `except` — and it becomes the tier's own type here instead of escaping as `httpx`'s.
        """
        try:
            return self._request(url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise GwasNotFound(f"GWAS Catalog has no record at {url}") from exc
            raise_if_retired(exc, GwasRetired, "The GWAS Catalog")
            raise GwasError(f"GWAS Catalog returned {exc.response.status_code} for {url}") from exc
        except httpx.HTTPError as exc:
            raise GwasError(f"GWAS Catalog request failed for {url}: {exc}") from exc
        except ValueError as exc:
            raise GwasError(f"GWAS Catalog returned unparseable JSON for {url}: {exc}") from exc

    def release(self) -> str | None:
        """The release date the Catalog states, or `None` when it could not be read or states none (RM373).

        Asked once per run. A failure is the unknown arm, logged, never an error: the associations are
        the run's work, and a release that could not be read is withheld from their label, never
        replaced by the day the run happened.
        """
        try:
            payload = self._get(self.stats_url)
        except GwasError as exc:
            logger.warning("GWAS Catalog did not state its release (%s); the rows name none.", exc)
            return None
        date = payload.get("date") if isinstance(payload, dict) else None
        return date.strip() if isinstance(date, str) and date.strip() else None

    def association_pages(self, rsid: str) -> list[list[dict]]:
        """Every page of the Catalog's associations for one rsID, one list per request made.

        Pages rather than a flat list so the pass can count what it spent (`@dont-discard-computed`).
        **Three outcomes, not two** — the S20 shape. Associations are an answer; a single empty page
        is *also* an answer (the Catalog was reached and holds nothing for this variant, which the
        caller records as `not_found`); and a raised `GwasError` means it could not be asked, which is
        unchecked rather than empty. Fusing the last two would turn a failed request into a definite
        negative — which is why a 404 here raises (see `GwasNotFound`).
        """
        url: str | None = str(
            httpx.URL(f"{self.endpoint}/associations", params={"rs_id": rsid, "size": _PAGE_SIZE})
        )
        pages: list[list[dict]] = []
        asked: set[str] = set()
        while url:
            if url in asked:
                raise GwasError(f"GWAS Catalog paging for {rsid} links back to {url}; refusing to loop")
            asked.add(url)
            payload = self._get(url)
            associations = (payload.get("_embedded") or {}).get("associations")
            if associations is None:
                # v2's empty answer is a 200 with no `_embedded` key and a page block saying zero.
                # Anything else without associations is a shape this pass does not model, and
                # returning `[]` for it would record a definite "no associations".
                if (payload.get("page") or {}).get("totalElements") == 0:
                    pages.append([])
                    break
                raise GwasError(
                    f"GWAS Catalog response for {rsid} carries no `_embedded.associations` and does "
                    f"not say it is empty — the API shape has changed and this pass would otherwise "
                    f"record a false negative"
                )
            pages.append(list(associations))
            nxt = (((payload.get("_links") or {}).get("next")) or {}).get("href")
            url = str(nxt).split("{")[0] if nxt else None  # a HAL link may be a URI template
        return pages

    def study_ancestries_url(self, accession: str) -> str:
        """Where v2 keeps one study's ancestries. Built from the accession: v2 associations carry no
        `_links.study`, only `self`, `loci` and `snp`."""
        return f"{self.endpoint}/studies/{accession}/ancestries"

    def follow(self, url: str) -> dict:
        """A linked sub-resource, or `{}` when the Catalog has none.

        A 404 here withholds the ancestry for one association rather than sinking the pass: the
        association itself is still a real published effect, and dropping it because its study record
        moved would lose evidence over metadata. A 410 is not caught: `GwasRetired` is the source
        moving, and swallowing it here would null every row's ancestry and say nothing.
        """
        try:
            return self._get(url)
        except GwasNotFound:
            logger.warning("GWAS Catalog has no record at %s; that association keeps a null ancestry", url)
            return {}


def _parse_risk_allele(name: str | None) -> tuple[str | None, str | None]:
    """`('rs4149056-C')` → `('rs4149056', 'C')`; `('rs4149056-?')` → `('rs4149056', None)`.

    The `?` is the Catalog saying the study never established which allele carries the effect, so it
    becomes a null rather than a stored `'?'` — the house algebra, and the difference between a
    consumer that knows it cannot weight this row and one that tries to match an allele called `?`.
    """
    if not name:
        return None, None
    rsid, sep, allele = name.rpartition("-")
    if not sep:
        return name.strip() or None, None
    allele = allele.strip()
    if not allele or allele == _UNKNOWN_ALLELE:
        return rsid.strip() or None, None
    return rsid.strip() or None, allele.upper()


def _allele_for(names: list, rsid: str) -> tuple[str | None, str | None]:
    """`(rsid, effect allele)` from the `snp_effect_allele` entry naming the variant asked about.

    A multi-SNP association lists one entry per SNP (`['rs1-A', 'rs2-G']`), and the first is not
    necessarily this module's variant: taking it would state rs1's allele against rs2's row. So the
    entry is matched on its rsID, and when none matches the allele is withheld — never borrowed.
    """
    parsed = [_parse_risk_allele(str(name)) for name in names if name]
    for reported, allele in parsed:
        if reported and reported.lower() == rsid.lower():
            return reported, allele
    return None, None


def _float_or_none(value: object) -> float | None:
    """A number the source reported, or `None` for one it did not.

    `'NR'` is the Catalog's not-reported marker and an **absence**, so it becomes null — distinct
    from a reported zero, and distinct from a value we could not hold (there is no such case on these
    columns). An unparseable cell is also an absence here rather than a failure: one malformed number
    must not sink a 40-row export, and the caller aggregates the count by reason.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == _NOT_REPORTED:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _queryable_p_value(raw: object) -> tuple[float | None, bool]:
    """`(p_value_num, underflowed)` — the queryable p-value, or a withheld one.

    **Found by running the pass against a real module.** The Catalog reports `pvalue: 0.0` for
    p-values past float64's range (subnormal below ~1e-308, exactly `0.0` below ~5e-324), and
    `GwasEffectRow.p_value_num` is `gt=0` for the reason SCHEMAS states: such a value is an underflow
    rather than a probability, and storing it would publish a confident zero. Correct — but the first
    version of this pass let the resulting `ValidationError` drop the **whole association**, losing a
    real published effect because one derived column could not be expressed.

    So the number is withheld and the row is kept, with the verbatim `p_value` string carrying what
    the source actually said. That is the same split `StudyRow` already makes, and it is precisely
    the catalogue-scale case the 0.5 mantissa/exponent decision anticipated without needing to
    reopen it: a module cites tens of associations, and the ones that underflow keep their evidence
    in the string.
    """
    value = _float_or_none(raw)
    if value is None:
        return None, False
    if not 0 < value <= 1:
        return None, True
    return value, False


#: `(size, measure, unit, direction)` — the effect columns of one association.
_Effect = tuple[float | None, str | None, str | None, str | None]

_NO_EFFECT: _Effect = (None, None, None, None)


def _effect_from(association: dict) -> _Effect | None:
    """The effect columns, or `None` when v2's `beta` string is outside the grammar (RM354).

    An odds ratio sits in `or_per_copy_num` as a number and carries no unit — `unit` stays null on
    that branch instead of being filled with something. A beta sits in the composite `beta` string,
    `<number> [<unit>] <increase|decrease>`, where the legacy API served `betaNum`, `betaUnit` and
    `betaDirection` apart; `"-"` is v2's own no-value and means no beta at all.

    **A string outside the grammar is withheld whole, never read in part.** A number without the unit
    it is in is not a smaller answer but a different one, and a unit guessed from a malformed tail is
    a fabrication. The caller counts it, and `strict` refuses on the count.
    """
    odds = _float_or_none(association.get("or_per_copy_num"))
    if odds is not None:
        return odds, "OR", None, None
    raw = association.get("beta")
    text = str(raw).strip() if raw is not None else ""
    if not text or text == _V2_NO_VALUE or text.upper() == _NOT_REPORTED:
        return _NO_EFFECT
    match = _BETA_GRAMMAR.match(text)
    if match is None:
        # A bare number is the one other shape a study can publish: a magnitude with neither unit nor
        # direction stated. Anything else is unread.
        size = _float_or_none(text) if len(text.split()) == 1 else None
        return (size, "beta", None, None) if size is not None else None
    size = _float_or_none(match["size"])
    if size is None:
        return None
    return size, "beta", (match["unit"] or None), match["direction"]


def _p_value_text(association: dict) -> str | None:
    """The p-value as the Catalog curated it: `<mantissa>e<exponent>` when v2 serves the pair.

    v2's float `p_value` is `0.0` past float64's range and `2.9999999999999997e-29` for `3e-29`; the
    pair beside it is what the study reported. Falls back to the float's string where the pair is
    absent, which is the legacy pass's verbatim rule.
    """
    mantissa, exponent = association.get("pvalue_mantissa"), association.get("pvalue_exponent")
    numeric = (int, float)
    if (
        isinstance(mantissa, numeric)
        and isinstance(exponent, int)
        and not isinstance(mantissa, bool)
        and not isinstance(exponent, bool)
    ):
        shown = int(mantissa) if float(mantissa).is_integer() else mantissa
        return f"{shown}e{exponent}"
    raw = association.get("p_value")
    return str(raw) if raw is not None else None


def _verbatim_or_none(value: object) -> str | None:
    """A free-text cell kept verbatim, with v2's own `-` no-value read as the absence it is.

    `NR` is left alone here: on `range` it is the study's own "[NR]"-style statement, which the column
    description promises to keep.
    """
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text == _V2_NO_VALUE else text


def _first_link(association: dict, name: str) -> str | None:
    link = ((association.get("_links") or {}).get(name) or {}).get("href")
    return str(link).split("{")[0] if link else None


def _ancestry(payload: dict) -> str | None:
    """The study's ancestral groups from v2's `/studies/<accession>/ancestries`, every stage, sorted.

    `NR` is the study not reporting one, an absence, so a study whose every group is `NR` has a null
    ancestry rather than the string "NR".
    """
    entries = (payload.get("_embedded") or {}).get("ancestries") or []
    groups = {
        str(g.get("ancestral_group") or "").strip()
        for entry in entries
        if isinstance(entry, dict)
        for g in (entry.get("ancestral_groups") or [])
        if isinstance(g, dict)
    }
    named = sorted(g for g in groups if g and g.upper() != _NOT_REPORTED)
    return ", ".join(named) or None


def _trait_facts(association: dict) -> dict[str, str | None]:
    """The EFO trait label(s) and id(s) v2 carries on the association, joined in the same order.

    `trait` is the EFO label (`efo_trait`), the same thing the legacy efoTraits link served, kept
    parallel to `trait_efo_id`. v2's `reported_trait` is the study's own wording and is not read.
    """
    traits = [t for t in (association.get("efo_traits") or []) if isinstance(t, dict)]
    labels = [str(t.get("efo_trait") or "").strip() for t in traits]
    ids = [str(t.get("efo_id") or "").strip() for t in traits]
    return {
        "trait": ", ".join(x for x in labels if x) or None,
        "trait_efo_id": ", ".join(x for x in ids if x) or None,
    }


def _merge_key(row: GwasEffectRow) -> tuple:
    """What makes two rows the same row: the Catalog's own association id.

    **Per record, not per variant.** Skipping every rsID an existing row mentions is the shape that
    made a re-run useless once — a variant gains associations as papers publish, and a coarse skip
    would pin the module to whatever the Catalog held the first time. The archive here is remote and
    growing, which is precisely the case that does not tolerate it.

    Read off `GwasEffectRow._KEY_FIELDS` rather than restated, so this pass and the published
    `hints.key_fields("gwas_effects.csv")` cannot drift apart (S51).
    """
    return merge_key(row)


def _sort_key(row: GwasEffectRow) -> tuple:
    """Deterministic emission order (Principle 7). Every component is a string so a null sorts
    beside a value rather than raising — a row whose study published no accession is legal."""
    return (
        row.variant_key,
        row.trait_efo_id or "",
        row.study_accession or "",
        row.association_id,
    )


def _cell(value: object) -> str:
    """Render one value to a canonical CSV cell, matching the compiler's `_scalar_cell` exactly.

    Kept as its own function rather than inlined, because a column added later must be rendered the
    way the reverse writer renders it or the two spellings differ after a round trip.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_gwas_csv(
    rows: list[GwasEffectRow], output_path: Path, *, before_commit: Callable[[], None] | None = None
) -> None:
    """Write the table with a fixed column order and canonical cells (byte-stable across runs).

    **This file is a pure build product since 0.7 (RM124).** Hand-editing it is not expected and
    nothing preserves such an edit — a correction to a derived row belongs in `overrides.csv` beside
    the spec, where the compiler applies it on every build and it travels with the reason it was
    made. That is what makes deleting this file and re-running cost nothing: the author's judgements
    are not in here to lose. The re-run itself is unchanged, and still gap-fills rather than re-asking
    every subject; what changed is that leaving a recorded row alone now risks nothing.
    """
    if nothing_to_write(output_path, rows):
        return  # RM370: a pass that answered nothing leaves no table
    with atomic_writer(output_path, newline="", before_commit=before_commit) as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in _FIELDNAMES})


def _module_subjects(spec_dir: Path) -> list[tuple[str, str]]:
    """`(rsid, variant_key)` for every row in the module that names an rsID.

    The Catalog is queried by rsID and has no coordinate entry point worth using here, so a
    coordinate-only row simply has no subject — reported by the caller rather than silently skipped.

    **Every table allowed to ask, through `enrich.collect_subjects` (RM158).** This read
    `variants.csv` alone while five authored models carry `rsid`, which is the defect `Subject` was
    built to end one pass over: resolution read the same one table until RM43, so a PGx module — which
    by design carries no `variants.csv` — enriched to an empty `resolution.csv`. The answer was
    already in this package and this pass did not use it, so a module whose rsIDs live in
    `haplotypes.csv` or `pharm_variants.csv` got no associations and no line saying none had been
    asked for. Reusing the collector rather than restating its loop also inherits its precedence:
    `variants.csv` first, first occurrence winning, so a variant named by two tables keeps the
    identity the SNP row minted.

    `studies.csv` carries `rsid` too and is deliberately not a subject: a study row *references* the
    variant it grounds, which the module already carries as a row of its own, so admitting it would
    add no rsID and change which table an identity came from. Its `proxy_rsid` (RM331) is a resolution
    subject but not one of these: an association for an LD proxy is not an association for the module's
    variant, so this pass asks without proxies.
    """
    variants, errors, _ = load_spec_variants(spec_dir)
    if errors and (spec_dir / "variants.csv").exists():
        raise GwasError(f"variants.csv is invalid: {errors[0]}")
    try:
        subjects = collect_subjects(
            spec_dir, variants, spec_genome_build(spec_dir), include_study_proxies=False
        )
    except EnrichmentError as exc:
        # A pass owes its caller its own exception type — the same re-raise `gene_validity` performs
        # around `module_genes`, and for the same reason: nothing up this stack catches the other
        # pass's error, so the CLI would print a traceback where a diagnosis belongs.
        raise GwasError(str(exc)) from exc
    seen: dict[str, str] = {}
    for subject in subjects:
        if subject.rsid:
            seen.setdefault(subject.rsid, subject.variant_key)
    return sorted(seen.items())


def enrich_gwas(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    write: bool = True,
    client: GwasCatalogClient | None = None,
    dataset: str | None = None,
    declared_use: str = "unstated",
    study_facts: bool = True,
) -> GwasResult:
    """Record the Catalog's published effect sizes for this module's variants.

    Existing rows are authoritative and merged, never clobbered — the standing rule for every pass,
    with the standing consequence: to regenerate after a machinery change, delete the file first.

    `offline` makes the pass a no-op with a warning rather than a failure: the Catalog publishes a
    bulk download, but this pass reads the REST API, and there is no snapshot for it to fall back on.
    An injected `client` still wins, because handing over a transport you already hold is not egress.

    A variant the Catalog holds nothing for gets a **`not_found` row**, unlike
    `enrich_gene_validity`'s silence, and the difference is real rather than stylistic: a curating
    body's silence means nobody has assessed the gene, whereas the Catalog's empty answer means no
    genome-wide association has been published for this variant — which *is* a fact about it, and one
    a consumer weighing an authored weight against the literature wants to see.

    `mode` is the severity ladder the CLI's `--strict` sets, and it is deliberately **not** about
    `missing`: see the block above the raise at the end of this function for why the Catalog's empty
    answer is a fact rather than a shortfall, and what `strict` reads instead.
    """
    spec_dir = Path(spec_dir)
    output_path = sidecar_path(spec_dir, "gwas_effects.csv", error=GwasError)
    if write:
        # Fail on a placeholder or half-edited licence table now, before the fetch (S98, RM231).
        require_sources_file(spec_dir, error=GwasError)

    if offline and client is None:
        logger.warning(
            "GWAS pass skipped: --offline. This pass reads the Catalog's REST API and has no "
            "snapshot to fall back on, so it is a no-op offline rather than a failure."
        )
        return GwasResult(skipped_offline=True)

    existing_rows: list[GwasEffectRow] = []
    if output_path.exists():
        parsed, errors, _ = load_csv_rows(output_path, GwasEffectRow, output_path.name)
        if errors:
            raise GwasError(f"existing {output_path.name} is invalid: {errors[0]}")
        existing_rows = parsed

    subjects = _module_subjects(spec_dir)
    if not subjects:
        logger.warning(
            "GWAS pass has no subjects: no row in variants.csv carries an rsID, and the Catalog is "
            "queried by rsID. Nothing was fetched and nothing was written."
        )
        return GwasResult(rows=existing_rows)

    owned = client is None
    # `try/finally`, like every sibling pass (RM100). The close used to be a bare
    # `if client is None: catalog.close()` after ~80 lines of fetching and writing, so any
    # exception in between -- a `GwasError`, a sidecar collision, a write failure -- leaked the
    # httpx client. `frequencies`, `gene_metrics` and `enrich` all had this shape already.
    try:
        catalog = client or GwasCatalogClient()
        cache = _LinkCache(fetch=catalog.follow)
        # The Catalog's own release (RM373), never the day this run happened to ask.
        release = dataset or release_dataset(GWAS_LANE, catalog.release())
        fetched_at = now_utc_iso()

        seen = {_merge_key(row) for row in existing_rows}
        out: list[GwasEffectRow] = list(existing_rows)
        covered: list[str] = []
        missing: list[str] = []
        unusable = 0
        direct_requests = 0
        underflows: list[str] = []

        unparsed: list[str] = []

        for rsid, variant_key in subjects:
            pages = catalog.association_pages(rsid)
            direct_requests += len(pages)
            associations = [association for page in pages for association in page]
            if not associations:
                missing.append(rsid)
                row = GwasEffectRow(
                    association_id=f"{rsid}:not_found",
                    variant_key=variant_key,
                    rsid=rsid,
                    dataset=release,
                    source=GWAS_SOURCE,
                    status="not_found",
                    fetched_at=fetched_at,
                )
                if _merge_key(row) not in seen:
                    seen.add(_merge_key(row))
                    out.append(row)
                continue
            covered.append(rsid)
            for association in associations:
                built = _build_row(
                    association,
                    rsid=rsid,
                    variant_key=variant_key,
                    cache=cache,
                    study_url=catalog.study_ancestries_url,
                    release=release,
                    fetched_at=fetched_at,
                    underflows=underflows,
                    unparsed=unparsed,
                    study_facts=study_facts,
                )
                if built is None:
                    unusable += 1
                    continue
                key = _merge_key(built)
                if key in seen:
                    continue
                seen.add(key)
                out.append(built)

        if underflows:
            # Aggregated by reason, once. On a well-studied variant this fires dozens of times, and the
            # rows are all still there — only the queryable number is withheld.
            logger.warning(
                "GWAS pass withheld p_value_num on %d association(s) whose p-value the Catalog reports "
                "below float64's range (it publishes 0.0); the verbatim p_value string is kept and the "
                "associations are recorded in full.",
                len(underflows),
            )
        if unusable:
            # Aggregated by reason, once — a per-row warning over a well-studied variant's dozens of
            # associations is a wall nobody reads.
            logger.warning(
                "GWAS pass skipped %d association(s) the Catalog published without an id this pass "
                "could key on; every usable association was still recorded.",
                unusable,
            )

        if unparsed:
            # Aggregated by reason, once, like the two above.
            logger.warning(
                "GWAS pass withheld the effect columns of %d association(s) whose `beta` string is "
                "outside the grammar it reads (`<number> [<unit>] <increase|decrease>`); the rows are "
                "recorded with every other column.",
                len(unparsed),
            )

        out.sort(key=_sort_key)
        result = GwasResult(
            rows=out,
            covered=covered,
            missing=missing,
            requests_made=direct_requests + cache.misses,
            requests_saved=cache.hits,
            p_value_underflows=len(underflows),
            unusable=unusable,
            unparsed_effects=len(unparsed),
        )

        if write:
            # The licence row lands inside the table's commit (S98, RM231).
            _write_gwas_csv(
                out,
                output_path,
                # Labelled by the release every committed row states, not by this run's alone (RM373).
                before_commit=lambda: record_table_sources(
                    table_datasets(out, release=lambda row: stated_release(row.dataset, GWAS_LANE)),
                    "gwas_effect",
                    spec_dir,
                    error=GwasError,
                    # A routine merge declares nothing, so it retires no licence row (RM383).
                    answered_every_row=False,
                    declared_use=declared_use,
                ),
            )
    finally:
        if owned:
            catalog.close()

    # **What `mode` means here, and why it is not `missing`** (RM100). The parameter was
    # accepted and never read while the CLI advertised `--strict` as a severity ladder, so the
    # flag was inert. Every sibling pass escalates on `result.missing`, and that would be wrong
    # here for the reason this pass's own docstring gives: the Catalog holding nothing for a
    # variant is a FACT about the variant, recorded as a `not_found` row, and true of most
    # variants. Escalating it would refuse nearly every module and say nothing.
    #
    # What `strict` does escalate is the pass failing to hold what the source DID say: an
    # association served without an id to key on, and a p-value below float64 whose queryable
    # number is therefore withheld. Both are already warned about in `best_effort`, aggregated
    # by reason; `strict` means a reproducible artifact, and both of these are places where the
    # artifact is missing something the Catalog published. RM354 adds the third of the kind: an
    # effect string this pass could not read, whose columns were withheld.
    if mode == "strict" and (result.unusable or result.p_value_underflows or result.unparsed_effects):
        raise GwasError(
            f"strict GWAS enrichment: {result.unusable} association(s) were served without an "
            f"id this pass can key on, {result.p_value_underflows} carried a p-value below "
            f"float64's range and this pass could not read the effect of "
            f"{result.unparsed_effects}, so the artifact does not hold everything the Catalog published. "
            f"All three are the Catalog's shape rather than an authoring mistake -- use "
            f"mode='best_effort' to record what is holdable and read the warnings."
        )
    return result


def _build_row(
    association: dict,
    *,
    rsid: str,
    variant_key: str,
    cache: _LinkCache,
    study_url: Callable[[str], str],
    release: str,
    fetched_at: str,
    underflows: list[str],
    unparsed: list[str],
    study_facts: bool = True,
) -> GwasEffectRow | None:
    """One `GwasEffectRow` from one v2 association payload, or `None` when it carries no usable id.

    `ValidationError` is caught narrowly and reported as a skip rather than allowed to escape as a
    pydantic traceback: a CLI printing one has told the operator nothing they can act on.
    """
    association_id = association.get("association_id")
    if association_id is None:
        self_link = _first_link(association, "self")
        association_id = self_link.rstrip("/").rpartition("/")[2] if self_link else None
    if association_id is None or not str(association_id).strip():
        return None

    reported_rsid, effect_allele = _allele_for(association.get("snp_effect_allele") or [], rsid)
    effect = _effect_from(association)
    if effect is None:
        unparsed.append(str(association_id))
        effect = _NO_EFFECT
    size, measure, unit, direction = effect

    p_value = _p_value_text(association)
    queryable_p, underflowed = _queryable_p_value(p_value)
    if underflowed:
        underflows.append(str(association_id))

    accession = _verbatim_or_none(association.get("accession_id"))
    pmid = association.get("pubmed_id")  # a string on v2; `_verbatim_or_none` reads its `-` as absent
    ancestry = None
    if study_facts and accession:
        ancestry = _ancestry(cache.get(study_url(accession)))
    traits = _trait_facts(association)

    try:
        return GwasEffectRow(
            association_id=str(association_id),
            variant_key=variant_key,
            rsid=reported_rsid or rsid,
            effect_allele=effect_allele,
            effect_size=size,
            effect_measure=measure,
            effect_unit=unit,
            effect_direction=direction,
            # v2 publishes no standard error on an association; withheld, never derived from the CI.
            standard_error=None,
            confidence_interval=_verbatim_or_none(association.get("range")),
            risk_allele_frequency=_float_or_none(association.get("risk_frequency")),
            p_value=p_value,
            p_value_num=queryable_p,
            trait=traits["trait"],
            trait_efo_id=traits["trait_efo_id"],
            pmid=_verbatim_or_none(pmid),
            study_accession=accession,
            ancestry=ancestry,
            dataset=release,
            source=GWAS_SOURCE,
            status="resolved",
            fetched_at=fetched_at,
        )
    except ValidationError as exc:
        logger.warning("GWAS association %s could not be recorded: %s", association_id, exc)
        return None


def gwas_source_row(*, declared_use: str = "unstated", dataset: str | None = None) -> SourceRow:
    """The licence row this pass writes. Exposed so a caller can record the terms without fetching."""
    return GWAS_CATALOG_TERMS.row("gwas_effect", declared_use=declared_use, dataset=dataset)
