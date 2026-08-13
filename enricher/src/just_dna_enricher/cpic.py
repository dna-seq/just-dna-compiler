"""Live CPIC queries — allele function, diplotype→phenotype, and star-allele definitions (0.5).

CPIC is a PostgREST service: open, unauthenticated, and queried with `?column=eq.value&select=…`
rather than a bespoke query language. It covers the layers PharmVar does not — a diplotype's
metabolizer phenotype and the prescribing recommendations built on it — and reaches genes outside
PharmVar's fifteen.

**CPIC is not a licence escape hatch.** It merged into ClinPGx, and `cpicpgx.org/license/` now
302-redirects to the ClinPGx data usage policy, so its terms are ClinPGx's terms: CC BY-SA plus a bar
on sale. Preferring PharmVar for star alleles is a *data-authority* choice (PharmVar is the naming
authority), not a licensing one — neither source is sellable.

**Three shapes here do not map cleanly onto this workspace's models, and are surfaced rather than
coerced:**

* `allele_location_value.variantallele` uses IUPAC ambiguity codes (`R` for A-or-G at CYP2C19
  rs58973490). `HaplotypeRow.allele` requires plain nucleotides, so an ambiguous definition is
  reported and skipped — expanding `R` to two rows would invent two defining variants where CPIC
  recorded one uncertainty.
* The same column also carries **deletion/insertion and repeat notations** — `DELTCT`,
  `AAAGGGGCG(2)`, `GGA(1)` in CYP2D6 — which are *not* ambiguity codes, and were reported as if they
  were until a real CYP2D6 draft showed them. They are a grammar gap (RM5) rather than an uncertainty
  CPIC recorded, so `unusable_allele_reason` names which of the two a value is and the two are
  reported separately.
* `gene_result.activityscore` is an inequality *string* (`"≥3.0"`, `"n/a"`), not a number, so it does
  not drop into `MeasureBinRow`'s numeric `measure_min`/`measure_max`. The raw string is carried and
  the parsing left to a human, because guessing a bound from `≥3.0` means inventing the upper one.

Coordinates from `sequence_location.position` are GRCh38 and **1-based** — checked against Ensembl
for rs4986893 (chr10:94780653) — which is what this pipeline already stores. Do not convert.

**CPIC does publish a chromosome; it is on `gene`, not on `sequence_location`.** An earlier probe
looked at `sequence_location` alone (genesymbol / dbsnpid / position / chromosomelocation — no
chromosome), concluded CPIC has none, and the drafting provider therefore skipped every defining
variant CPIC gives no rsID for: 18 in CYP2C9, 14 in TPMT, 4 in NUDT15. `gene.chr` carries `chr10` for
CYP2C9, `chr6` for TPMT, `chr13` for NUDT15 (probed 2026-08-07, 132 genes). Joining it onto
`sequence_location.genesymbol` is a lookup in CPIC's own tables, not the inference the old comment
rightly refused — a star allele's defining variant is in the gene the allele belongs to, and the
location row already names that gene.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import httpx
from just_dna_format.alleles import non_nucleotide_reason
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
)

from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME
from just_dna_enricher.net import attempt_floor

logger = logging.getLogger(__name__)

DEFAULT_CPIC_ENDPOINT = "https://api.cpicpgx.org/v1"
CPIC_SOURCE = "cpic"


class CpicError(RuntimeError):
    """A CPIC request failed in a way the caller must see."""


def unusable_allele_reason(value: str) -> str | None:
    """Why `variantallele` cannot become a `HaplotypeRow.allele`, or `None` when it can.

    **Two distinct reasons, and calling both "an IUPAC ambiguity code" was wrong.** Drafting real CYP2D6
    turned up `DELTCT`, `AAAGGGGCG(2)` and `GGA(1)` beside the genuine codes (`R`, `S`), and the message
    announced all of them as ambiguity codes — a claim about the data that is simply false for a deletion
    or a repeat, and it points an author at the wrong thing. The distinction matters for what happens
    next, too: an ambiguous base is an *uncertainty CPIC recorded* and will never be expressible, while a
    structural notation is a **grammar gap** (RM5) that a future release may widen to hold.

    * `"ambiguity"` — every character is a nucleotide or an IUPAC ambiguity code (`R` = A or G).
    * `"notation"` — a deletion/insertion or repeat notation, not a nucleotide string at all.

    The classification itself moved to `just_dna_format.alleles.non_nucleotide_reason` once the compiler
    needed the same two-way split for a locus's own `ref`/`alts` (a `T>Y` locus can host no genotype, and
    the generic "cannot host" message blamed the genotype). One definition, two callers, each keeping its
    own wording — CPIC's is about a star allele's defining variant, the compiler's about a locus.
    """
    return non_nucleotide_reason(value)


#: What each `unusable_allele_reason` means, in the author's terms: what CPIC said, and what follows.
_UNUSABLE_EXPLANATION: dict[str, str] = {
    "ambiguity": (
        "an IUPAC ambiguity code rather than a definite nucleotide (`R` is A-or-G) — an uncertainty it "
        "recorded, and expanding it would invent defining variants it never stated"
    ),
    "notation": (
        "a deletion/insertion or repeat notation rather than a nucleotide string — a grammar gap (RM5) "
        "rather than an ambiguity, and a future release may widen to hold it"
    ),
    # The third reason `non_nucleotide_reason` answers since RM58. CPIC has never been observed to write
    # it, but this map is indexed directly by `_unusable_warnings`, so an unlisted member is a KeyError
    # in a warning path rather than a missing sentence — the reason it is filled in here on the same
    # commit as the classifier gains it, and not when a real `.` first arrives.
    "missing": (
        "VCF's MISSING marker rather than an allele — a claim that there is no alternate allele at all, "
        "so there is no defining variant to record and nothing a future release could widen to hold"
    ),
}


def _unusable_warnings(gene: str, by_reason: dict[str, list[str]]) -> list[str]:
    """One aggregated line per reason, with the count and a few real examples."""
    lines: list[str] = []
    for reason, entries in sorted(by_reason.items()):
        shown = ", ".join(entries[:3])
        rest = f" (+{len(entries) - 3} more)" if len(entries) > 3 else ""
        lines.append(
            f"{gene}: {len(entries)} defining allele(s) skipped — CPIC records "
            f"{_UNUSABLE_EXPLANATION[reason]}. e.g. {shown}{rest}."
        )
    return lines


@dataclass
class CpicAllele:
    """One star allele's function and activity value, as CPIC assigns them."""

    gene: str
    allele: str
    activity_value: float | None = None
    function_status: str | None = None


@dataclass
class CpicDiplotype:
    """One diplotype and the phenotype CPIC assigns it."""

    gene: str
    diplotype: str
    phenotype: str | None = None
    # Deliberately a string: CPIC writes inequalities ("≥3.0"), which no float can represent.
    activity_score: str | None = None


@dataclass
class CpicDefiningVariant:
    """One variant defining a CPIC allele, at a GRCh38 coordinate."""

    gene: str
    allele: str
    rsid: str | None
    chrom: str | None
    start: int | None
    variant_allele: str | None
    #: Why the allele cannot be held (`unusable_allele_reason`), or None when it can. Was a bare
    #: `ambiguous: bool`, which named only one of the two real cases — a `DELTCT` row is not ambiguous.
    unusable: str | None = None


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
    classification: str | None = None
    recommendation: str | None = None
    implication: str | None = None
    activity_score: str | None = None


# CPIC's recommendation `classification` → `vocab.VALID_RECOMMENDATION_STRENGTH`. `n/a` is absent on
# purpose: it is CPIC recording that it did not classify, which is an empty cell here — inventing a
# member for it would let "unclassified" read as a classification.
_CLASSIFICATION_MAP: dict[str, str] = {
    "strong": "strong",
    "moderate": "moderate",
    "optional": "optional",
    "no recommendation": "no_recommendation",
}


def map_classification(raw: str | None) -> str | None:
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


def map_function_status(raw: str | None) -> str | None:
    """CPIC's prose → `pgx.VALID_FUNCTION_STATUS`, or None when it says something else.

    The two `possible …` values collapse to `uncertain_function`: CPIC uses them for a call it is not
    confident in, which is exactly what `uncertain` means here, and inventing new vocabulary members
    for them would make every consumer's switch statement wrong.
    """
    if not raw:
        return None
    return _FUNCTION_MAP.get(raw.strip().lower())


def normalize_chrom(value: str | None) -> str | None:
    """CPIC's `gene.chr` (`chr10`, `chrX`) → this workspace's bare contig name (`10`, `X`).

    `None` for a blank or an unplaced spelling, rather than a guess — the same rule
    `chrom_from_accession` follows in the PharmVar client.
    """
    text = (value or "").strip()
    if not text:
        return None
    return text.removeprefix("chr").removeprefix("CHR").strip() or None


def _float_or_none(value: Any) -> float | None:
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
        client: httpx.Client | None = None,
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
        stop=attempt_floor(3),
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

    def row_count(self, table: str) -> int | None:
        """How many rows CPIC says a table holds, or `None` when it does not answer with a count.

        PostgREST reports it in `Content-Range` when asked with `Prefer: count=exact`. Used by the
        snapshot builder to refuse a short read: the service imposes no default limit today, but that
        is a fact about a deployment rather than a contract, and a silently truncated snapshot reads
        as "CPIC has nothing for this gene".
        """
        response = self._client.get(
            f"{self.endpoint}/{table}",
            params={"select": "count"},
            headers={"Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"},
        )
        header = response.headers.get("content-range", "")
        total = header.rsplit("/", 1)[-1] if "/" in header else ""
        return int(total) if total.isdigit() else None

    def fetch_table(self, table: str, select: str) -> list[dict[str, Any]]:
        """One whole CPIC table as raw rows — the snapshot builder's read.

        Public because the builder is a separate module and reaching for `_get` across it is the
        private-symbol reach RM41 exists to stop doing.
        """
        return self._get(table, {"select": select})

    def chrom_for_gene(self, gene: str) -> str | None:
        """The contig CPIC places a gene on, from its own `gene` table, or `None` if it names none.

        Separate request rather than a PostgREST embed: `sequence_location` has no foreign key to
        `gene` (it joins on the symbol string), so there is nothing to embed through.
        """
        rows = self._get("gene", {"symbol": f"eq.{gene}", "select": "symbol,chr"})
        return normalize_chrom(rows[0].get("chr")) if rows else None

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
        first. Returns `(variants, warnings)`; an allele the format cannot hold is reported by *which*
        of the two reasons applies (`unusable_allele_reason`), aggregated, and never coerced.
        """
        definitions = self._get(
            "allele_definition",
            {"genesymbol": f"eq.{gene}", "select": "id,name,genesymbol", "order": "name"},
        )
        if not definitions:
            return [], []
        # One extra request per gene, and it is what makes a coordinate-only defining variant usable:
        # `HaplotypeRow` wants rsid **or** chrom AND start, and 36 of CPIC's defining variants across
        # CYP2C9/TPMT/NUDT15 have a position and no rsID. See the module docstring.
        chrom = self.chrom_for_gene(gene)
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
        # Aggregated per reason, not one line per row: a real CYP2D6 draft hits 67 of these, which buries
        # every other finding in the run — the same collapse already applied to the activity scores and
        # the copy-number diplotypes. Grouped by *reason* because the two are different findings with
        # different fixes (an ambiguity is permanent, a notation is RM5).
        unusable: dict[str, list[str]] = {}
        for r in rows:
            location = r.get("sequence_location") or {}
            allele_value = (r.get("variantallele") or "").strip().upper()
            reason = unusable_allele_reason(allele_value)
            if reason is not None:
                label = by_id.get(r["alleledefinitionid"], "")
                unusable.setdefault(reason, []).append(f"{label}={allele_value}")
            out.append(
                CpicDefiningVariant(
                    gene=location.get("genesymbol") or gene,
                    allele=by_id.get(r["alleledefinitionid"], ""),
                    rsid=location.get("dbsnpid") or None,
                    # GRCh38, 1-based, matching Ensembl — no conversion. `chrom` comes from CPIC's own
                    # `gene` table: `sequence_location` really does have no chromosome column, which
                    # is what the 2026-08-03 probe saw, but `gene.chr` does and joining on the symbol
                    # the location row already carries is a lookup rather than the inference that
                    # probe rightly refused. Still `None` when CPIC leaves `chr` blank.
                    chrom=chrom,
                    start=location.get("position"),
                    variant_allele=allele_value or None,
                    unusable=reason,
                )
            )
        return out, _unusable_warnings(gene, unusable)


class CpicSnapshotClient:
    """The same four questions, answered from a built snapshot instead of the live service (RM38).

    **Duck-typed against `CpicClient`, deliberately, and not a subclass of it.** `enrich_pgx` and
    `pgx_draft.draft_gene` already take an injected client, so a reader with the same four methods needs
    no branch in either — which is what keeps "snapshot or live" out of the passes entirely. It is not a
    subclass because it shares no implementation: there is no endpoint, no pacing, no retry.

    **The vocabulary mapping happens here, not in the builder.** The parquet holds CPIC's own prose
    verbatim (`"No function"`, `"Strong"`) and `map_function_status` / `map_classification` run on the
    way out — the same functions the live client calls, so a snapshot answer and a live answer are the
    same object by construction, and a mapping fix reaches a snapshot built last month.

    Read with **duckdb**, which is a core dependency, rather than polars, which is `[dev]` and only the
    builder needs. That is the house convention (builder in polars, runtime pass in duckdb), and it is
    what keeps the declared runtime dependency set honest about what the runtime actually requires.
    """

    def __init__(self, reference: Path) -> None:
        self.reference = Path(reference)
        data_dir = self.reference / SNAPSHOT_DATA_DIRNAME
        if not data_dir.is_dir() or not any(data_dir.glob("*.parquet")):
            raise CpicError(
                f"no CPIC snapshot at {data_dir} — build one with `just-dna-enricher cpic build`"
            )
        self._data_dir = data_dir
        release_path = self.reference / RELEASE_FILENAME
        self.release: dict[str, Any] = (
            json.loads(release_path.read_text()) if release_path.is_file() else {}
        )

    @property
    def dataset(self) -> str | None:
        """Which snapshot answered — recorded onto `SourceRow.dataset`, as the gnomAD routes are.

        A consumer must be able to tell a pinned file from a live API: the two can differ by a release,
        and `dataset` is inside the fact set where `source` is not.
        """
        return self.release.get("dataset")

    def close(self) -> None:
        """No-op, so a caller can `close()` this and a live client identically."""

    def _rows(
        self, parquet: str, where: str, params: list[Any], select: str, order: str = ""
    ) -> list[dict]:
        path = self._data_dir / parquet
        if not path.is_file():
            # A snapshot built by an older builder can legitimately lack a table this one reads. An
            # empty answer, not a crash — the pass then reports "CPIC has nothing", which is wrong,
            # so say which file is missing instead of returning silence.
            raise CpicError(
                f"{parquet} is not in the CPIC snapshot at {self.reference} — it was built by an "
                f"older builder; rebuild it with `just-dna-enricher cpic build`."
            )
        pattern = str(path).replace("'", "''")
        con = duckdb.connect(":memory:")
        try:
            clause = f" ORDER BY {order}" if order else ""
            cursor = con.execute(
                f"SELECT {select} FROM read_parquet('{pattern}') WHERE {where}{clause}", params
            )
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()

    def chrom_for_gene(self, gene: str) -> str | None:
        rows = self._rows("genes.parquet", "gene = ?", [gene], "chrom")
        return rows[0]["chrom"] if rows else None

    def alleles_for_gene(self, gene: str) -> list[CpicAllele]:
        rows = self._rows(
            "alleles.parquet", "gene = ?", [gene],
            "gene, allele, activity_value, clinical_function_status", "allele",
        )
        return [
            CpicAllele(
                gene=r["gene"],
                allele=r["allele"],
                activity_value=_float_or_none(r["activity_value"]),
                function_status=map_function_status(r["clinical_function_status"]),
            )
            for r in rows
        ]

    def diplotypes_for_gene(self, gene: str) -> list[CpicDiplotype]:
        rows = self._rows(
            "diplotypes.parquet", "gene = ?", [gene],
            "gene, diplotype, phenotype, activity_score", "diplotype",
        )
        return [
            CpicDiplotype(
                gene=r["gene"],
                diplotype=r["diplotype"],
                phenotype=r["phenotype"] or None,
                activity_score=r["activity_score"] or None,
            )
            for r in rows
        ]

    def recommendations(self, gene: str, drug: str) -> list[CpicRecommendation]:
        """One gene/drug pair's recommendations across every population.

        `gene_count = 1` reproduces the live client's `len(phenotypes) != 1` filter exactly: the builder
        flattens a recommendation's `phenotypes` map to one row per gene and carries how many there
        were, because a row about CYP2C19 *and* CYP2D6 is not a statement about CYP2C19 alone.
        """
        rows = self._rows(
            "recommendations.parquet",
            "gene = ? AND drug = ? AND gene_count = 1",
            [gene, drug.strip().lower()],
            "gene, phenotype, drug, population, classification, recommendation, implication, "
            "activity_score",
        )
        out = [
            CpicRecommendation(
                gene=r["gene"],
                phenotype=r["phenotype"],
                drug=r["drug"],
                population=(r["population"] or "").strip(),
                classification=map_classification(r["classification"]),
                recommendation=(r["recommendation"] or "").strip() or None,
                implication=(r["implication"] or "").strip() or None,
                activity_score=r["activity_score"] or None,
            )
            for r in rows
        ]
        # Same deterministic order the live client emits (Principle 7).
        return sorted(out, key=lambda r: (r.population, r.phenotype))

    def defining_variants(self, gene: str) -> tuple[list[CpicDefiningVariant], list[str]]:
        """Star-allele defining variants, with the same aggregated unusable-allele warnings.

        The classification runs here rather than being stored, for the reason the whole snapshot
        follows: `unusable_allele_reason` is a *judgement this workspace makes* about CPIC's value, so
        freezing it into the parquet would pin one release's opinion into every snapshot built under it.
        """
        rows = self._rows(
            "allele_definitions.parquet", "gene = ?", [gene],
            "gene, allele, rsid, chrom, start, variant_allele",
            "allele, start, variant_allele",
        )
        out: list[CpicDefiningVariant] = []
        unusable: dict[str, list[str]] = {}
        for r in rows:
            allele_value = (r["variant_allele"] or "").strip().upper()
            reason = unusable_allele_reason(allele_value)
            if reason is not None:
                unusable.setdefault(reason, []).append(f"{r['allele']}={allele_value}")
            out.append(
                CpicDefiningVariant(
                    gene=r["gene"] or gene,
                    allele=r["allele"] or "",
                    rsid=r["rsid"] or None,
                    chrom=r["chrom"] or None,
                    start=r["start"],
                    variant_allele=allele_value or None,
                    unusable=reason,
                )
            )
        return out, _unusable_warnings(gene, unusable)
