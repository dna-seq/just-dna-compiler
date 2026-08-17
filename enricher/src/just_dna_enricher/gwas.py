"""The NHGRI-EBI GWAS Catalog pass — published effect sizes as a derived fact table (0.6, RM90).

Fills `gwas_effects.csv` for the variants `variants.csv` names, from the Catalog's REST API. What it
does **not** do is fill `weight`: a consumer asked for exactly that and it is barred — MODULE_LIFECYCLE
§ Stage 3 names `weight`/`direction`/`effect_size` in the cells no tool fills, and every check in this
tier reports rather than repairs. The effect lands in its own table beside the authored column, and a
consumer chooses between them wholesale.

**Everything below was established by probing the real API on 2026-08-17**, not from its
documentation, and three findings shaped the pass:

* **The association payload is thin.** It carries the effect, the p-value and the risk allele, and
  nothing else — `pmid`, `study_accession`, `ancestry`, `trait` and `trait_efo_id` all sit behind
  `_links.study` and `_links.efoTraits`. So a complete row costs two extra requests, and the pass
  costs `1 + 2N` per variant with N associations.

  **`_LinkCache` memoizes by resolved URL, and the measurement corrected the prediction that
  motivated it.** The expectation was that associations share studies heavily, so caching would
  collapse most of the cost. Run against `reference_examples/hfe_hemochromatosis`, it saved
  **nothing**: rs1800562 alone carries 189 associations and each names its *own* study, so the real
  figure was 382 requests and 0 cache hits. The cache stays — it costs a dict and it does pay on a
  module whose variants share literature — but the honest budget is `1 + 2N`, and `--no-study-facts`
  exists because of that measurement rather than in anticipation of it. The pass reports both halves
  so an operator sees the real number instead of this docstring's guess.
* **`riskAlleleName` is `rs4149056-C`, or `rs4149056-?` when the study never established which allele
  carries the effect** — 2 of the first 3 associations for that variant. `-?` becomes `None`, never a
  guess, and the row is still written: an effect relative to an unknown allele is real evidence that
  cannot be used as a weight, and dropping it would hide that from a consumer who needs to know.
* **`betaUnit` is free text and frequently uninterpretable** — `umol/l` on one association and `unit`
  on two others for the same variant. It is stored verbatim including the useless values, because
  "these betas are on unknown and possibly different scales" is the fact a consumer must have.

**Rate limits are NOT established.** EBI publishes no numeric budget that could be found, which makes
this pass unlike `gnomad.py`, whose 10-requests-per-60-seconds is real, documented and load-bearing.
The gate here is a conservative default rather than a transcribed limit, and it is spelled that way so
nobody later "corrects" it against a number that does not exist.
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.normalize import now_utc_iso
from just_dna_format.sources import SourceRow
from just_dna_format.spec import VariantRow
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, wait_exponential_jitter

from just_dna_enricher.licensing import (
    GWAS_CATALOG_TERMS,
    merge_sources_file,
    sidecar_path,
)
from just_dna_enricher.net import PacingGate, attempt_floor

logger = logging.getLogger(__name__)

DEFAULT_GWAS_ENDPOINT = "https://www.ebi.ac.uk/gwas/rest/api"
GWAS_SOURCE = GWAS_CATALOG_TERMS.source

#: Derived from the model, never hand-kept — a parallel list is how `SOURCES_FIELDNAMES` lost a column.
_FIELDNAMES: list[str] = list(GwasEffectRow.model_fields)

#: What the Catalog writes when a study did not establish which allele carries the effect.
_UNKNOWN_ALLELE = "?"

#: What it writes for a number the study did not report. An ABSENCE, not a value we cannot hold.
_NOT_REPORTED = "NR"

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
    one type; `associations_for` catches it and reports the empty answer, which the pass records as
    `not_found`. What must never happen is the reverse — a transport failure read as "no
    associations", which would write a confident negative about a variant nobody could ask about.
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
    #: Associations the Catalog served that this pass could not key on, so they are in no row. Counted
    #: because `strict` reads it (RM100) and because "we dropped some" is not a thing to leave in a log.
    unusable: int = 0
    skipped_offline: bool = False


@dataclass
class _LinkCache:
    """Memoize `_links` follows by resolved URL, and count what the memoization saved.

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
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _get(self, url: str) -> dict:
        """One paced GET. Retries transport/timeout, translates everything else.

        Both legs are translated (`@client-exception-contract`): a transport error that survives the
        retries and an HTTP status error are equally the caller's problem and equally not `httpx`'s
        vocabulary to express.
        """
        self.gate.wait()
        try:
            response = self._http().get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError, httpx.TimeoutException):
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise GwasNotFound(f"GWAS Catalog has no record at {url}") from exc
            raise GwasError(f"GWAS Catalog returned {exc.response.status_code} for {url}") from exc
        except httpx.HTTPError as exc:
            raise GwasError(f"GWAS Catalog request failed for {url}: {exc}") from exc
        except ValueError as exc:
            raise GwasError(f"GWAS Catalog returned unparseable JSON for {url}: {exc}") from exc

    def associations_for(self, rsid: str) -> list[dict]:
        """Every association the Catalog holds for one rsID.

        **Three outcomes, not two** — the S20 shape. A non-empty list is an answer; `[]` is *also* an
        answer (the Catalog was reached and holds nothing for this variant, which the caller records
        as `not_found`); and a raised `GwasError` means it could not be asked, which is unchecked
        rather than empty. Fusing the last two would turn a failed request into a definite negative.
        """
        url = f"{self.endpoint}/singleNucleotidePolymorphisms/{rsid}/associations"
        try:
            payload = self._get(url)
        except GwasNotFound:
            # The Catalog holds only variants with a published association, so it 404s on a rare
            # clinical variant rather than returning an empty list. That is the empty ANSWER.
            return []
        embedded = payload.get("_embedded") or {}
        associations = embedded.get("associations")
        if associations is None:
            # A 200 with neither `_embedded.associations` nor an empty list is a shape we do not
            # model. Raising beats returning `[]`, which would record a definite "no associations".
            raise GwasError(
                f"GWAS Catalog response for {rsid} carries no `_embedded.associations` — the API "
                f"shape has changed and this pass would otherwise record a false negative"
            )
        return list(associations)

    def follow(self, url: str) -> dict:
        """A linked sub-resource, or `{}` when the Catalog has none.

        A 404 here withholds the study/trait facts for one association rather than sinking the pass:
        the association itself is still a real published effect, and dropping it because its study
        record moved would lose evidence over metadata.
        """
        try:
            return self._get(url)
        except GwasNotFound:
            logger.warning("GWAS Catalog has no record at %s; that association keeps null study facts", url)
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


def _effect_from(association: dict) -> tuple[float | None, str | None, str | None]:
    """`(size, measure, unit)` from the two mutually exclusive fields the Catalog publishes.

    `orPerCopyNum` and `betaNum` are separate keys — unlike the download TSV's single ambiguous
    "OR or BETA" column — so the mapping is exact rather than a guess. An OR carries no unit, which
    is why `unit` is null on that branch instead of being filled with something.
    """
    odds = _float_or_none(association.get("orPerCopyNum"))
    if odds is not None:
        return odds, "OR", None
    beta = _float_or_none(association.get("betaNum"))
    if beta is None:
        return None, None, None
    unit = association.get("betaUnit")
    return beta, "beta", (str(unit).strip() or None) if unit else None


def _first_link(association: dict, name: str) -> str | None:
    link = ((association.get("_links") or {}).get(name) or {}).get("href")
    return str(link).split("{")[0] if link else None


def _study_facts(payload: dict) -> dict[str, str | None]:
    """`pmid`, `study_accession` and `ancestry` out of a study payload."""
    publication = payload.get("publicationInfo") or {}
    ancestries = payload.get("ancestries") or []
    groups = [
        str(g.get("ancestralGroup") or "").strip()
        for a in ancestries
        for g in (a.get("ancestralGroups") or [])
    ]
    named = sorted({g for g in groups if g})
    return {
        "pmid": str(publication.get("pubmedId")).strip() if publication.get("pubmedId") else None,
        "study_accession": str(payload.get("accessionId")).strip() or None
        if payload.get("accessionId")
        else None,
        "ancestry": ", ".join(named) or None,
    }


def _trait_facts(payload: dict) -> dict[str, str | None]:
    """The reported trait label and its EFO id(s), joined when a study reports several."""
    embedded = (payload.get("_embedded") or {}).get("efoTraits") or []
    traits = [t for t in embedded if isinstance(t, dict)]
    if not traits and payload.get("trait"):
        traits = [payload]
    labels = [str(t.get("trait") or "").strip() for t in traits]
    ids = [str(t.get("shortForm") or "").strip() for t in traits]
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
    """
    return ("id", row.association_id)


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


def _write_gwas_csv(rows: list[GwasEffectRow], output_path: Path) -> None:
    """Write the table with a fixed column order and canonical cells (byte-stable across runs)."""
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in _FIELDNAMES})


def _module_subjects(spec_dir: Path) -> list[tuple[str, str]]:
    """`(rsid, variant_key)` for every variant in the module that has an rsID.

    The Catalog is queried by rsID and has no coordinate entry point worth using here, so a
    coordinate-only row simply has no subject — reported by the caller rather than silently skipped.
    """
    variants_path = spec_dir / "variants.csv"
    if not variants_path.exists():
        return []
    rows, errors, _ = load_csv_rows(variants_path, VariantRow, "variants.csv")
    if errors:
        raise GwasError(f"variants.csv is invalid: {errors[0]}")
    seen: dict[str, str] = {}
    for row in rows:
        if row.rsid:
            seen.setdefault(row.rsid, row.variant_key or row.rsid)
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
        release = dataset or f"gwas_catalog_{now_utc_iso()[:10]}"
        fetched_at = now_utc_iso()

        seen = {_merge_key(row) for row in existing_rows}
        out: list[GwasEffectRow] = list(existing_rows)
        covered: list[str] = []
        missing: list[str] = []
        unusable = 0
        direct_requests = 0
        underflows: list[str] = []

        for rsid, variant_key in subjects:
            associations = catalog.associations_for(rsid)
            direct_requests += 1
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
                    release=release,
                    fetched_at=fetched_at,
                    underflows=underflows,
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

        out.sort(key=_sort_key)
        result = GwasResult(
            rows=out,
            covered=covered,
            missing=missing,
            requests_made=direct_requests + cache.misses,
            requests_saved=cache.hits,
            p_value_underflows=len(underflows),
            unusable=unusable,
        )

        if write:
            _write_gwas_csv(out, output_path)
            merge_sources_file(
                [GWAS_CATALOG_TERMS.row("gwas_effect", declared_use=declared_use, dataset=release)],
                spec_dir,
                error=GwasError,
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
    # artifact is missing something the Catalog published.
    if mode == "strict" and (result.unusable or result.p_value_underflows):
        raise GwasError(
            f"strict GWAS enrichment: {result.unusable} association(s) were served without an "
            f"id this pass can key on and {result.p_value_underflows} carried a p-value below "
            f"float64's range, so the artifact does not hold everything the Catalog published. "
            f"Both are the Catalog's shape rather than an authoring mistake -- use "
            f"mode='best_effort' to record what is holdable and read the warnings."
        )
    return result


def _build_row(
    association: dict,
    *,
    rsid: str,
    variant_key: str,
    cache: _LinkCache,
    release: str,
    fetched_at: str,
    underflows: list[str],
    study_facts: bool = True,
) -> GwasEffectRow | None:
    """One `GwasEffectRow` from one association payload, or `None` when it carries no usable id.

    `ValidationError` is caught narrowly and reported as a skip rather than allowed to escape as a
    pydantic traceback: a CLI printing one has told the operator nothing they can act on.
    """
    association_id = association.get("associationId") or association.get("id")
    if association_id is None:
        self_link = _first_link(association, "association") or _first_link(association, "self")
        association_id = self_link.rstrip("/").rpartition("/")[2] if self_link else None
    if not association_id:
        return None

    loci = association.get("loci") or []
    risk_alleles = [
        allele
        for locus in loci
        for allele in (locus.get("strongestRiskAlleles") or [])
        if isinstance(allele, dict)
    ]
    allele_name = risk_alleles[0].get("riskAlleleName") if risk_alleles else None
    reported_rsid, effect_allele = _parse_risk_allele(allele_name)
    size, measure, unit = _effect_from(association)

    queryable_p, underflowed = _queryable_p_value(association.get("pvalue"))
    if underflowed:
        underflows.append(str(association_id))

    facts: dict[str, str | None] = {"pmid": None, "study_accession": None, "ancestry": None}
    traits: dict[str, str | None] = {"trait": None, "trait_efo_id": None}
    if study_facts:
        study_link = _first_link(association, "study")
        if study_link:
            facts = _study_facts(cache.get(study_link))
        trait_link = _first_link(association, "efoTraits")
        if trait_link:
            traits = _trait_facts(cache.get(trait_link))

    try:
        return GwasEffectRow(
            association_id=str(association_id),
            variant_key=variant_key,
            rsid=reported_rsid or rsid,
            effect_allele=effect_allele,
            effect_size=size,
            effect_measure=measure,
            effect_unit=unit,
            effect_direction=(association.get("betaDirection") or None),
            standard_error=_float_or_none(association.get("standardError")),
            confidence_interval=(str(association.get("range")).strip() or None)
            if association.get("range")
            else None,
            risk_allele_frequency=_float_or_none(association.get("riskFrequency")),
            p_value=str(association["pvalue"]) if association.get("pvalue") is not None else None,
            p_value_num=queryable_p,
            trait=traits["trait"],
            trait_efo_id=traits["trait_efo_id"],
            pmid=facts["pmid"],
            study_accession=facts["study_accession"],
            ancestry=facts["ancestry"],
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
