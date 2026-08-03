"""Live CPIC queries — allele function, diplotype→phenotype, and star-allele definitions (0.5).

CPIC is a PostgREST service: open, unauthenticated, and queried with `?column=eq.value&select=…`
rather than a bespoke query language. It covers the layers PharmVar does not — a diplotype's
metabolizer phenotype and the prescribing recommendations built on it — and reaches genes outside
PharmVar's fifteen.

**CPIC is not a licence escape hatch.** It merged into ClinPGx, and `cpicpgx.org/license/` now
302-redirects to the ClinPGx data usage policy, so its terms are ClinPGx's terms: CC BY-SA plus a bar
on sale. Preferring PharmVar for star alleles is a *data-authority* choice (PharmVar is the naming
authority), not a licensing one — neither source is sellable.

**Two shapes here do not map cleanly onto this workspace's models, and are surfaced rather than
coerced:**

* `allele_location_value.variantallele` uses IUPAC ambiguity codes (`R` for A-or-G at CYP2C19
  rs58973490). `HaplotypeRow.allele` requires plain nucleotides, so an ambiguous definition is
  reported and skipped — expanding `R` to two rows would invent two defining variants where CPIC
  recorded one uncertainty.
* `gene_result.activityscore` is an inequality *string* (`"≥3.0"`, `"n/a"`), not a number, so it does
  not drop into `MeasureBinRow`'s numeric `measure_min`/`measure_max`. The raw string is carried and
  the parsing left to a human, because guessing a bound from `≥3.0` means inventing the upper one.

Coordinates from `sequence_location.position` are GRCh38 and **1-based** — checked against Ensembl
for rs4986893 (chr10:94780653) — which is what this pipeline already stores. Do not convert.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

DEFAULT_CPIC_ENDPOINT = "https://api.cpicpgx.org/v1"
CPIC_SOURCE = "cpic"
# Plain nucleotides only. Anything else from `variantallele` is an IUPAC ambiguity code.
_NUCLEOTIDES = frozenset("ACGT")


class CpicError(RuntimeError):
    """A CPIC request failed in a way the caller must see."""


@dataclass
class CpicAllele:
    """One star allele's function and activity value, as CPIC assigns them."""

    gene: str
    allele: str
    activity_value: Optional[float] = None
    function_status: Optional[str] = None


@dataclass
class CpicDiplotype:
    """One diplotype and the phenotype CPIC assigns it."""

    gene: str
    diplotype: str
    phenotype: Optional[str] = None
    # Deliberately a string: CPIC writes inequalities ("≥3.0"), which no float can represent.
    activity_score: Optional[str] = None


@dataclass
class CpicDefiningVariant:
    """One variant defining a CPIC allele, at a GRCh38 coordinate."""

    gene: str
    allele: str
    rsid: Optional[str]
    chrom: Optional[str]
    start: Optional[int]
    variant_allele: Optional[str]
    ambiguous: bool = False


@dataclass
class CpicRecommendation:
    """One CPIC prescribing recommendation: a (gene phenotype, drug, population) triple.

    Keyed by **phenotype**, not by diplotype — one recommendation covers every diplotype that shares
    the phenotype, which is why drafting joins on it rather than fetching per pair.
    """

    gene: str
    phenotype: str
    drug: str
    population: str
    classification: Optional[str] = None
    recommendation: Optional[str] = None
    implication: Optional[str] = None
    activity_score: Optional[str] = None


# CPIC's recommendation `classification` → `vocab.VALID_RECOMMENDATION_STRENGTH`. `n/a` is absent on
# purpose: it is CPIC recording that it did not classify, which is an empty cell here — inventing a
# member for it would let "unclassified" read as a classification.
_CLASSIFICATION_MAP: dict[str, str] = {
    "strong": "strong",
    "moderate": "moderate",
    "optional": "optional",
    "no recommendation": "no_recommendation",
}


def map_classification(raw: Optional[str]) -> Optional[str]:
    """CPIC's recommendation strength → this format's vocabulary, or None when it did not classify."""
    if not raw:
        return None
    return _CLASSIFICATION_MAP.get(raw.strip().lower())


# CPIC's `clinicalfunctionalstatus` prose → this workspace's `VALID_FUNCTION_STATUS` vocabulary.
# An unmapped value is carried as None rather than guessed; the raw string stays available upstream.
_FUNCTION_MAP: dict[str, str] = {
    "no function": "no_function",
    "decreased function": "decreased_function",
    "normal function": "normal_function",
    "increased function": "increased_function",
    "uncertain function": "uncertain_function",
    "unknown function": "unknown_function",
    "possible decreased function": "uncertain_function",
    "possible increased function": "uncertain_function",
}


def map_function_status(raw: Optional[str]) -> Optional[str]:
    """CPIC's prose → `pgx.VALID_FUNCTION_STATUS`, or None when it says something else.

    The two `possible …` values collapse to `uncertain_function`: CPIC uses them for a call it is not
    confident in, which is exactly what `uncertain` means here, and inventing new vocabulary members
    for them would make every consumer's switch statement wrong.
    """
    if not raw:
        return None
    return _FUNCTION_MAP.get(raw.strip().lower())


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class CpicClient:
    """PostgREST client for the CPIC API. No auth, so no key handling."""

    def __init__(
        self,
        endpoint: str = DEFAULT_CPIC_ENDPOINT,
        *,
        client: Optional[httpx.Client] = None,
        timeout: float = 60.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._owned = client is None

    def close(self) -> None:
        if self._owned:
            self._client.close()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = self._client.get(f"{self.endpoint}/{path.lstrip('/')}", params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise CpicError(f"CPIC {path} returned {type(payload).__name__}, expected a list")
        return payload

    def alleles_for_gene(self, gene: str) -> list[CpicAllele]:
        """Allele function + activity value for one gene."""
        rows = self._get(
            "allele",
            {
                "genesymbol": f"eq.{gene}",
                "select": "genesymbol,name,activityvalue,clinicalfunctionalstatus",
                "order": "name",
            },
        )
        return [
            CpicAllele(
                gene=r["genesymbol"],
                allele=r["name"],
                activity_value=_float_or_none(r.get("activityvalue")),
                function_status=map_function_status(r.get("clinicalfunctionalstatus")),
            )
            for r in rows
        ]

    def diplotypes_for_gene(self, gene: str) -> list[CpicDiplotype]:
        """Diplotype → metabolizer phenotype for one gene."""
        rows = self._get(
            "diplotype",
            {
                "genesymbol": f"eq.{gene}",
                "select": "genesymbol,diplotype,generesult,totalactivityscore",
                "order": "diplotype",
            },
        )
        return [
            CpicDiplotype(
                gene=r["genesymbol"],
                diplotype=r["diplotype"],
                phenotype=r.get("generesult") or None,
                activity_score=r.get("totalactivityscore") or None,
            )
            for r in rows
        ]

    def recommendations(self, gene: str, drug: str) -> list[CpicRecommendation]:
        """CPIC's prescribing recommendations for one gene/drug pair, across every population.

        Two hops, because CPIC keys recommendations by RxNorm id: `drug` resolves the name, then
        `recommendation` is filtered on it. `phenotypes` is a `{gene: phenotype}` map, so a
        multi-gene recommendation is kept only when it names the gene asked for — a row about
        CYP2C19 *and* CYP2D6 is not a statement about CYP2C19 alone.

        Deterministically ordered (population, phenotype) so a re-draft emits the same rows in the
        same order (Principle 7).
        """
        found = self._get("drug", {"select": "drugid,name", "name": f"eq.{drug.strip().lower()}"})
        if not found:
            return []
        rows = self._get(
            "recommendation",
            {
                "select": (
                    "drugid,phenotypes,implications,drugrecommendation,classification,"
                    "population,activityscore"
                ),
                "drugid": f"eq.{found[0]['drugid']}",
            },
        )
        out: list[CpicRecommendation] = []
        for row in rows:
            phenotypes = row.get("phenotypes") or {}
            phenotype = phenotypes.get(gene)
            if not phenotype or len(phenotypes) != 1:
                continue
            implications = row.get("implications") or {}
            out.append(
                CpicRecommendation(
                    gene=gene,
                    phenotype=phenotype,
                    drug=drug.strip().lower(),
                    population=(row.get("population") or "").strip(),
                    classification=map_classification(row.get("classification")),
                    recommendation=(row.get("drugrecommendation") or "").strip() or None,
                    implication=(implications.get(gene) or "").strip() or None,
                    activity_score=(row.get("activityscore") or None),
                )
            )
        return sorted(out, key=lambda r: (r.population, r.phenotype))

    def defining_variants(self, gene: str) -> tuple[list[CpicDefiningVariant], list[str]]:
        """Star-allele defining variants for one gene, plus warnings for what could not be used.

        Two requests rather than a nested select, because PostgREST embedding across
        `allele_definition → allele_location_value → sequence_location` needs the definition ids
        first. Returns `(variants, warnings)`; an IUPAC-ambiguous allele is reported, never coerced.
        """
        definitions = self._get(
            "allele_definition",
            {"genesymbol": f"eq.{gene}", "select": "id,name,genesymbol", "order": "name"},
        )
        if not definitions:
            return [], []
        by_id = {d["id"]: d["name"] for d in definitions}
        ids = ",".join(str(i) for i in by_id)
        rows = self._get(
            "allele_location_value",
            {
                "alleledefinitionid": f"in.({ids})",
                "select": (
                    "alleledefinitionid,variantallele,"
                    "sequence_location(genesymbol,dbsnpid,position)"
                ),
            },
        )
        out: list[CpicDefiningVariant] = []
        warnings: list[str] = []
        for r in rows:
            location = r.get("sequence_location") or {}
            allele_value = (r.get("variantallele") or "").strip().upper()
            ambiguous = bool(allele_value) and not set(allele_value) <= _NUCLEOTIDES
            if ambiguous:
                warnings.append(
                    f"{gene} {by_id.get(r['alleledefinitionid'])}: CPIC records the defining allele "
                    f"as {allele_value!r}, an IUPAC ambiguity code rather than a definite "
                    f"nucleotide — skipped rather than guessed."
                )
            out.append(
                CpicDefiningVariant(
                    gene=location.get("genesymbol") or gene,
                    allele=by_id.get(r["alleledefinitionid"], ""),
                    rsid=location.get("dbsnpid") or None,
                    # GRCh38, 1-based, matching Ensembl — no conversion. `chrom` stays None because
                    # CPIC does not publish one: `sequence_location` has genesymbol/dbsnpid/position/
                    # chromosomelocation and no chromosome column (probed 2026-08-03). Deriving it
                    # from the gene symbol would be inference, so the drafting provider must not
                    # write a bare `start` — see `pgx_draft._haplotype_rows`.
                    chrom=None,
                    start=location.get("position"),
                    variant_allele=allele_value or None,
                    ambiguous=ambiguous,
                )
            )
        return out, warnings
