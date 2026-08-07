"""Build the CPIC snapshot (`[dev]`) — the whole PostgREST database as five parquet tables (RM38).

CPIC is open and unauthenticated, so this cache is not about *access*. It is about a **host** not
spending one shared per-IP allowance on every caller's request, and about the terms being accepted
once, by the operator who built the snapshot, rather than implicitly on each incoming request. That is
RM38's argument, and it is the same one for ClinPGx; PharmVar adds a third reason (a personal key) that
these two do not have.

**The whole database fits, comfortably.** Probed live on 2026-08-07: 132 genes, 1,361 alleles, 1,337
allele definitions over 3,120 location values, 2,115 recommendations across 324 drugs, and 112,754
diplotypes — the last being the only large one, and four narrow string columns of it is under a
megabyte of zstd parquet. There is no gene filter here for that reason: a snapshot that covers only the
genes the operator thought of is a snapshot that silently answers "CPIC has nothing" for the next one.

**Verbatim, and mapped at read time.** The vocabulary translations (`clinicalfunctionalstatus` →
`VALID_FUNCTION_STATUS`, `classification` → `VALID_RECOMMENDATION_STRENGTH`) are *not* applied here.
They live in `cpic.map_function_status` / `map_classification`, which the snapshot client calls on the
way out — so a mapping fix reaches an already-built snapshot, and a live answer and a snapshot answer
are the same object by construction rather than by inspection. Storing a source's value verbatim is the
house rule; the one documented exception is an encoding that lies about its own order (ClinGen's dosage
codes), and CPIC's prose does not.

**`recommendation.phenotypes` is a JSON map, so it is flattened one row per gene named.** The live
client keeps a recommendation only when it names exactly one gene — a row about CYP2C19 *and* CYP2D6 is
not a statement about CYP2C19 alone — so `gene_count` travels with each flattened row and the reader
applies the identical rule. Flattening without it would silently promote multi-gene rows.

Builder-only: `polars` is a guarded `[dev]` import, and the runtime pass reads the parquet through
DuckDB, which is core. Builder in polars, runtime in duckdb — the house convention.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.cpic import DEFAULT_CPIC_ENDPOINT, CpicClient, normalize_chrom
from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: `parquet basename -> (endpoint, select, sort keys)`. One file per CPIC table this workspace reads,
#: named for what it holds rather than for CPIC's table, since `allele_definitions` is a join of two.
GENES_PARQUET = "genes.parquet"
ALLELES_PARQUET = "alleles.parquet"
DIPLOTYPES_PARQUET = "diplotypes.parquet"
DEFINING_PARQUET = "allele_definitions.parquet"
RECOMMENDATIONS_PARQUET = "recommendations.parquet"


class CpicBuildError(RuntimeError):
    """The CPIC snapshot could not be built."""


@dataclass
class CpicBuildResult:
    out_dir: Path
    row_counts: dict[str, int] = field(default_factory=dict)
    gene_count: int = 0
    dataset: str = ""

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())


def _schemas() -> dict[str, dict]:
    """Fixed column order + dtypes per table, so a rebuild is byte-identical (Principle 7)."""
    return {
        GENES_PARQUET: {
            "gene": pl.Utf8,
            "chrom": pl.Utf8,          # normalized off `gene.chr` — `chr10` → `10`
            "ensembl_id": pl.Utf8,
            "hgnc_id": pl.Utf8,
            "lookup_method": pl.Utf8,
        },
        ALLELES_PARQUET: {
            "gene": pl.Utf8,
            "allele": pl.Utf8,
            "activity_value": pl.Float64,
            # CPIC's prose, verbatim. `cpic.map_function_status` runs on the way out.
            "clinical_function_status": pl.Utf8,
        },
        DIPLOTYPES_PARQUET: {
            "gene": pl.Utf8,
            "diplotype": pl.Utf8,
            "phenotype": pl.Utf8,
            # Deliberately Utf8: CPIC writes inequalities ("≥3.0") no float can hold.
            "activity_score": pl.Utf8,
        },
        DEFINING_PARQUET: {
            "gene": pl.Utf8,
            "allele": pl.Utf8,
            "rsid": pl.Utf8,
            "chrom": pl.Utf8,
            "start": pl.Int64,         # GRCh38, 1-based — the VCF convention, never converted
            "variant_allele": pl.Utf8,
        },
        RECOMMENDATIONS_PARQUET: {
            "gene": pl.Utf8,
            "phenotype": pl.Utf8,
            "drug": pl.Utf8,
            "population": pl.Utf8,
            "classification": pl.Utf8,   # verbatim ("Strong"); mapped at read time
            "recommendation": pl.Utf8,
            "implication": pl.Utf8,
            "activity_score": pl.Utf8,
            #: How many genes the source row's `phenotypes` map named. The live client keeps only
            #: `== 1`; carrying the count lets the reader apply the same rule instead of a looser one.
            "gene_count": pl.Int64,
        },
    }


def _sorted(records: list[dict], keys: list[str]) -> list[dict]:
    """Deterministic order, nulls last, so a rebuild is byte-identical (Principle 7)."""
    return sorted(records, key=lambda r: tuple((r.get(k) is None, r.get(k)) for k in keys))


def _fetch_all(client: CpicClient, table: str, select: str) -> list[dict[str, Any]]:
    """One whole CPIC table, with the row count checked against what the service says it holds.

    PostgREST imposes no default limit here — the 112,754-row `diplotype` table comes back in one
    6.5 MB response — but "no limit today" is a fact about a deployment, not a contract, and a silently
    truncated snapshot is the worst possible failure: it reads as "CPIC has nothing for this gene".
    So the exact count is requested alongside and a short read refuses.
    """
    rows = client.fetch_table(table, select)
    expected = client.row_count(table)
    if expected is not None and len(rows) != expected:
        raise CpicBuildError(
            f"CPIC {table}: fetched {len(rows)} row(s) but the service reports {expected}. The "
            f"endpoint has started paginating; the snapshot would be silently incomplete."
        )
    return rows


def build_snapshot(
    out_dir: Path, *, endpoint: str = DEFAULT_CPIC_ENDPOINT, client: CpicClient | None = None
) -> CpicBuildResult:
    """Fetch CPIC whole and write `data/*.parquet` + `release.json` under `out_dir`.

    `built_at` is the only per-run byte and it lives in `release.json`, outside the parquet, exactly as
    in the ClinVar and constraint builders.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the CPIC snapshot; install the publisher/dev surface with "
            "`pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    out_dir = Path(out_dir)
    data_dir = out_dir / SNAPSHOT_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)

    owned = client is None
    cpic = client or CpicClient(endpoint)
    try:
        genes = _fetch_all(cpic, "gene", "symbol,chr,ensemblid,hgncid,lookupmethod")
        alleles = _fetch_all(
            cpic, "allele", "genesymbol,name,activityvalue,clinicalfunctionalstatus"
        )
        diplotypes = _fetch_all(
            cpic, "diplotype", "genesymbol,diplotype,generesult,totalactivityscore"
        )
        definitions = _fetch_all(cpic, "allele_definition", "id,name,genesymbol")
        locations = _fetch_all(
            cpic,
            "allele_location_value",
            "alleledefinitionid,variantallele,sequence_location(genesymbol,dbsnpid,position)",
        )
        recommendations = _fetch_all(
            cpic,
            "recommendation",
            "drugid,phenotypes,implications,drugrecommendation,classification,population,"
            "activityscore",
        )
        drugs = _fetch_all(cpic, "drug", "drugid,name")
    finally:
        if owned:
            cpic.close()

    chrom_by_gene = {
        (row.get("symbol") or ""): normalize_chrom(row.get("chr")) for row in genes
    }
    gene_records = _sorted(
        [
            {
                "gene": row.get("symbol"),
                "chrom": chrom_by_gene.get(row.get("symbol") or ""),
                "ensembl_id": row.get("ensemblid") or None,
                "hgnc_id": row.get("hgncid") or None,
                "lookup_method": row.get("lookupmethod") or None,
            }
            for row in genes
            if row.get("symbol")
        ],
        ["gene"],
    )
    allele_records = _sorted(
        [
            {
                "gene": row.get("genesymbol"),
                "allele": row.get("name"),
                "activity_value": _float_or_none(row.get("activityvalue")),
                "clinical_function_status": row.get("clinicalfunctionalstatus") or None,
            }
            for row in alleles
            if row.get("genesymbol") and row.get("name")
        ],
        ["gene", "allele"],
    )
    diplotype_records = _sorted(
        [
            {
                "gene": row.get("genesymbol"),
                "diplotype": row.get("diplotype"),
                "phenotype": row.get("generesult") or None,
                "activity_score": row.get("totalactivityscore") or None,
            }
            for row in diplotypes
            if row.get("genesymbol") and row.get("diplotype")
        ],
        ["gene", "diplotype"],
    )

    # The `allele_definition → allele_location_value → sequence_location` join, flattened. The gene's
    # chromosome comes from the `gene` table, which is where CPIC keeps it (see `cpic.py`) — the
    # location row names only the symbol.
    allele_by_id = {row["id"]: row for row in definitions}
    defining_records: list[dict] = []
    for row in locations:
        definition = allele_by_id.get(row.get("alleledefinitionid"))
        if definition is None:
            continue
        location = row.get("sequence_location") or {}
        gene = location.get("genesymbol") or definition.get("genesymbol")
        defining_records.append(
            {
                "gene": gene,
                "allele": definition.get("name"),
                "rsid": location.get("dbsnpid") or None,
                "chrom": chrom_by_gene.get(gene or ""),
                "start": location.get("position"),
                "variant_allele": (row.get("variantallele") or "").strip().upper() or None,
            }
        )
    defining_records = _sorted(defining_records, ["gene", "allele", "start", "variant_allele"])

    drug_by_id = {row.get("drugid"): (row.get("name") or "").strip().lower() for row in drugs}
    recommendation_records: list[dict] = []
    for row in recommendations:
        phenotypes = row.get("phenotypes") or {}
        implications = row.get("implications") or {}
        scores = row.get("activityscore") or {}
        drug = drug_by_id.get(row.get("drugid"))
        if not drug:
            continue
        for gene, phenotype in phenotypes.items():
            if not phenotype:
                continue
            recommendation_records.append(
                {
                    "gene": gene,
                    "phenotype": phenotype,
                    "drug": drug,
                    "population": (row.get("population") or "").strip(),
                    "classification": row.get("classification") or None,
                    "recommendation": (row.get("drugrecommendation") or "").strip() or None,
                    "implication": (implications.get(gene) or "").strip() or None,
                    "activity_score": _score_text(scores.get(gene)),
                    "gene_count": len(phenotypes),
                }
            )
    recommendation_records = _sorted(
        recommendation_records, ["gene", "drug", "population", "phenotype"]
    )

    schemas = _schemas()
    by_file = {
        GENES_PARQUET: gene_records,
        ALLELES_PARQUET: allele_records,
        DIPLOTYPES_PARQUET: diplotype_records,
        DEFINING_PARQUET: defining_records,
        RECOMMENDATIONS_PARQUET: recommendation_records,
    }
    counts: dict[str, int] = {}
    for name, records in by_file.items():
        pl.DataFrame(records, schema=schemas[name]).write_parquet(
            data_dir / name, compression="zstd"
        )
        counts[name] = len(records)

    digest = _content_digest(by_file)
    dataset = _dataset_label(digest)
    release = {
        "source_url": endpoint,
        # CPIC publishes no release id, so the snapshot is identified by *content*: a digest over the
        # rows it holds. Deterministic (the records are sorted), and unlike a build date it changes
        # exactly when the data does — which is what makes `dataset` a fact a module can be compared on.
        "content_sha256": digest,
        "dataset": dataset,
        "row_counts": counts,
        "gene_count": len(gene_records),
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    (out_dir / RELEASE_FILENAME).write_text(
        json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    logger.info(
        "CPIC snapshot: %d genes, %d alleles, %d diplotypes, %d defining variants, "
        "%d recommendations → %s",
        len(gene_records), len(allele_records), len(diplotype_records), len(defining_records),
        len(recommendation_records), data_dir,
    )
    return CpicBuildResult(
        out_dir=out_dir, row_counts=counts, gene_count=len(gene_records), dataset=dataset
    )


def _score_text(value: Any) -> str | None:
    """CPIC's per-gene activity score, as a string. It writes inequalities, so never a float."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _content_digest(by_file: dict[str, list[dict]]) -> str:
    """A digest over the snapshot's records — the release id CPIC does not publish.

    Over the *records* rather than the parquet bytes, so it is independent of the compression a future
    polars might choose; `sort_keys` and the already-sorted record order make it reproducible.
    """
    hasher = hashlib.sha256()
    for name in sorted(by_file):
        hasher.update(name.encode("utf-8"))
        hasher.update(
            json.dumps(by_file[name], sort_keys=True, default=str, ensure_ascii=False).encode(
                "utf-8"
            )
        )
    return "sha256:" + hasher.hexdigest()


def _dataset_label(content_sha256: str) -> str:
    """The `dataset` cell a `SourceRow` built from this snapshot carries.

    `cpic_snapshot_<digest>` rather than `cpic`, because the *route* matters exactly as it does for the
    two gnomAD constraint routes: a consumer must be able to tell whether a pinned file or a live API
    gave the answer, and the two can differ by a release. CPIC publishes no release id, so the digest
    over the records stands in for one — it changes when, and only when, the data does.
    """
    return f"cpic_snapshot_{content_sha256.removeprefix('sha256:')[:12]}"


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"

