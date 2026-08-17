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
  `_links.study` and `_links.efoTraits`. So a complete row costs up to two extra requests, and the
  naive shape of this pass would be `1 + 2N` requests for a variant with N associations. rs4149056
  has dozens. `_LinkCache` memoizes by resolved URL within a run, which collapses most of that because
  associations share studies heavily — and the pass reports what it actually spent rather than
  guessing.
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


@dataclass
class GwasResult:
    """What one pass did, including what it spent."""

    rows: list[GwasEffectRow] = field(default_factory=list)
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    requests_made: int = 0
    requests_saved: int = 0
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
        payload = self._get(url)
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
        return self._get(url)


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
            )
            if built is None:
                unusable += 1
                continue
            key = _merge_key(built)
            if key in seen:
                continue
            seen.add(key)
            out.append(built)

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
    )

    if write:
        _write_gwas_csv(out, output_path)
        merge_sources_file(
            [GWAS_CATALOG_TERMS.row("gwas_effect", declared_use=declared_use, dataset=release)],
            spec_dir,
            error=GwasError,
        )
    if client is None:
        catalog.close()
    return result


def _build_row(
    association: dict,
    *,
    rsid: str,
    variant_key: str,
    cache: _LinkCache,
    release: str,
    fetched_at: str,
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

    facts: dict[str, str | None] = {"pmid": None, "study_accession": None, "ancestry": None}
    study_link = _first_link(association, "study")
    if study_link:
        facts = _study_facts(cache.get(study_link))
    traits: dict[str, str | None] = {"trait": None, "trait_efo_id": None}
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
            p_value_num=_float_or_none(association.get("pvalue")),
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
