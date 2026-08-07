"""Build the PharmVar snapshot (`[dev]`) — operator-built, inject-only, never published (RM38).

**This one is not like the other two, and the difference is the whole entry.** ClinPGx and CPIC
snapshots may be built once and published, so a deployment fetches bytes somebody else took. PharmVar's
cannot. Its API key is personal and non-transferable under terms §2, and no axis `SourceTerms` records
covers passing on bulk data pulled under one — `redistribution=True` is about the CC BY-SA grant over
the *content*, not about a clause on the *account*. An unestablished permission is never a permission
(`None` ≠ `False`, the same rule as `share_alike`/`commercial_use`), so there is deliberately no
`download.ensure_pharmvar_snapshot`, no `pharmvar publish` command, and no HF repo. An operator builds
their own with their own key, and `locations.resolve_pharmvar_reference` finds it.

**One request builds the whole thing.** `/genes?exclude-sub-alleles=true` returns all fifteen genes
with their alleles and defining variants in a single ~5 MB response (1,173 core alleles, 12,925 variant
rows, probed 2026-08-07). At 2 rps that is the difference between one call and fifteen, and it is why
this builder needs no pacing beyond the client's own gate.

**The assembly filter is load-bearing here specifically.** PharmVar publishes each variant against both
GRCh37 and GRCh38 and lists GRCh37 first; a snapshot is where a wrong coordinate stops being latent and
starts being a written number. `pharmvar.PHARMVAR_GENOME_BUILD` documents the probe — 451 of 739
rsID-keyed defining variants would have carried a GRCh37 position — and the parquet records the build
it kept, so a reader can check rather than assume.

Builder-only: `polars` is a guarded `[dev]` import; the runtime reads the parquet through DuckDB.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME
from just_dna_enricher.pharmvar import (
    PHARMVAR_GENOME_BUILD,
    PharmVarClient,
    PharmVarError,
)

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

ALLELES_PARQUET = "alleles.parquet"
VARIANTS_PARQUET = "variants.parquet"


@dataclass
class PharmVarBuildResult:
    out_dir: Path
    gene_count: int = 0
    allele_count: int = 0
    variant_count: int = 0
    dataset: str = ""
    genome_build: str = PHARMVAR_GENOME_BUILD
    genes: list[str] = field(default_factory=list)


def _schemas() -> dict[str, dict]:
    """Fixed column order + dtypes, so a rebuild is byte-identical (Principle 7)."""
    return {
        ALLELES_PARQUET: {
            "gene": pl.Utf8,
            "allele": pl.Utf8,
            # PharmVar's own prose ("no function"), verbatim. `pgx` normalizes on the way out, the
            # same transformation the live path applies, so the two answers cannot diverge.
            "function": pl.Utf8,
            "activity_value": pl.Float64,
            "evidence_level": pl.Utf8,
        },
        VARIANTS_PARQUET: {
            "gene": pl.Utf8,
            "allele": pl.Utf8,
            #: Position **within the allele's variant list**, so the snapshot preserves the emitted
            #: order the live client returns. Order feeds `artifact.digest` downstream (Principle 7),
            #: and a parquet has no inherent one to recover after a sort.
            "variant_index": pl.Int64,
            "rsid": pl.Utf8,
            "chrom": pl.Utf8,
            "start": pl.Int64,          # 1-based, GRCh38 — the VCF convention, never converted
            "ref": pl.Utf8,
            "alt": pl.Utf8,
        },
    }


def build_snapshot(
    out_dir: Path,
    *,
    client: PharmVarClient | None = None,
    include_sub_alleles: bool = False,
) -> PharmVarBuildResult:
    """Fetch PharmVar whole and write `data/*.parquet` + `release.json` under `out_dir`.

    Raises `PharmVarError` when no key is configured — unlike the runtime pass, where an absent key is
    a *skip*. Building is an explicit act with an explicit output, so failing to build has to be an
    error rather than an empty snapshot that later reads as "PharmVar defines nothing".
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the PharmVar snapshot; install the publisher/dev surface "
            "with `pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    out_dir = Path(out_dir)
    data_dir = out_dir / SNAPSHOT_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)

    owned = client is None
    pharmvar = client or PharmVarClient()
    try:
        if not pharmvar.configured:
            raise PharmVarError(
                "no PharmVar API key: set PHARMVAR_API_KEY. The key is personal to your account "
                "(terms §2), which is why this snapshot is operator-built and is never published."
            )
        by_gene = pharmvar.all_genes(include_sub_alleles=include_sub_alleles)
    finally:
        if owned:
            pharmvar.close()

    allele_records: list[dict] = []
    variant_records: list[dict] = []
    for gene in sorted(by_gene):
        for allele in sorted(by_gene[gene], key=lambda a: a.allele):
            allele_records.append(
                {
                    "gene": allele.gene or gene,
                    "allele": allele.allele,
                    "function": allele.function,
                    "activity_value": allele.activity_value,
                    "evidence_level": allele.evidence_level,
                }
            )
            for index, variant in enumerate(allele.variants):
                variant_records.append(
                    {
                        "gene": allele.gene or gene,
                        "allele": allele.allele,
                        "variant_index": index,
                        "rsid": variant.rsid,
                        "chrom": variant.chrom,
                        "start": variant.start,
                        "ref": variant.ref,
                        "alt": variant.alt,
                    }
                )

    schemas = _schemas()
    by_file = {ALLELES_PARQUET: allele_records, VARIANTS_PARQUET: variant_records}
    for name, records in by_file.items():
        pl.DataFrame(records, schema=schemas[name]).write_parquet(
            data_dir / name, compression="zstd"
        )

    digest = _content_digest(by_file)
    dataset = f"pharmvar_snapshot_{digest.removeprefix('sha256:')[:12]}"
    release = {
        # PharmVar versions per gene rather than globally, so — as for CPIC — the release id is a
        # digest over the records: it changes when, and only when, the data does.
        "content_sha256": digest,
        "dataset": dataset,
        # Recorded rather than implied. This snapshot holds coordinates on one assembly, chosen out of
        # the two PharmVar publishes, and a reader must be able to see which without re-deriving it.
        "genome_build": PHARMVAR_GENOME_BUILD,
        "gene_count": len(by_gene),
        "allele_count": len(allele_records),
        "variant_count": len(variant_records),
        "genes": sorted(by_gene),
        "redistributable": False,
        "notice": (
            "Built under a personal, non-transferable PharmVar API key (terms §2). Operator-built and "
            "inject-only: do not publish or pass on."
        ),
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    (out_dir / RELEASE_FILENAME).write_text(
        json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    logger.info(
        "PharmVar snapshot: %d gene(s), %d allele(s), %d defining variant(s) on %s → %s",
        len(by_gene), len(allele_records), len(variant_records), PHARMVAR_GENOME_BUILD, data_dir,
    )
    return PharmVarBuildResult(
        out_dir=out_dir,
        gene_count=len(by_gene),
        allele_count=len(allele_records),
        variant_count=len(variant_records),
        dataset=dataset,
        genes=sorted(by_gene),
    )


def _content_digest(by_file: dict[str, list[dict]]) -> str:
    """A digest over the snapshot's records — the release id PharmVar does not publish globally."""
    hasher = hashlib.sha256()
    for name in sorted(by_file):
        hasher.update(name.encode("utf-8"))
        hasher.update(
            json.dumps(by_file[name], sort_keys=True, default=str, ensure_ascii=False).encode(
                "utf-8"
            )
        )
    return "sha256:" + hasher.hexdigest()


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"
