"""ClinVar reference-snapshot builder — the ``[dev]`` half of the ClinVar link.

Turns the NCBI ClinVar GRCh38 VCF (`clinvar.vcf.gz`, ~200 MB gz, 4.4M records) into a
schema-shaped, per-chromosome parquet snapshot the resolver reads (`clinvar/data/*.parquet`) — the
same on-disk layout as the Ensembl snapshot, so one DuckDB view shape serves both. One row per ALT
allele; `clin_sig` is normalized into `vocab.VALID_CLIN_SIG` while `clin_sig_raw` keeps the verbatim
`CLNSIG` (lossless, auditable). A `release.json` beside the parquet records the provenance
(`clinvar_file_date`, `source_url`, `source_sha256`, `record_count`, ...) that will feed
`GenePanelSpec.reference`/`reference_sha256` when RM4 lands.

Builder-only (`just-dna-enricher[dev]`): `polars` is a guarded import — the runtime resolver path
(`clinvar.lookup_loci`, `duckdb`) never needs it, keeping the core install polars-free (Goal 2). The
VCF-parsing idioms (`_parse_info`, `_genes`, `_norm_chrom`, the `RS=`→`rs{n}` rule, the ACGT/length
filter) are the ones proven in just-dna-lite's `v1_port.clinvar`, generalized here to keep *every*
record (this is a resolution reference, not a pathogenic gene panel).
"""

import gzip
import hashlib
import logging
import re
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Iterator, Optional

import httpx

from just_dna_format.vocab import VALID_CLIN_SIG

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None

logger = logging.getLogger(__name__)

DEFAULT_CLINVAR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
#: ClinVar publishes its literature links separately from the VCF: one row per
#: (VariationID, citation source, citation id). Ingested as its own artifact beside the snapshot
#: rather than folded into it, so an existing snapshot stays byte-identical and keeps its digest.
DEFAULT_CITATIONS_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/var_citations.txt"

# Longest ref/alt allele kept. SNVs and short indels (in VCF anchor-base form, which is still ACGT)
# are what a consumer's small-variant VCF can carry and match; ClinVar's multi-kb structural variants
# would never match a genotype call and only bloat the snapshot. Matches v1_port.clinvar.
MAX_ALLELE_LEN = 50

_ACGT_RE = re.compile(r"^[ACGT]+$")
_VALID_CHROMS = frozenset([str(i) for i in range(1, 23)] + ["X", "Y", "MT"])
# Sort order for chromosome parquet file emission (deterministic, karyotype order).
_CHROM_ORDER = [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]


def _empty_schema() -> dict:
    """The parquet schema (column order + dtypes) — fixed so a rebuild is byte-identical (Principle
    7). The resolver link reads only chrom/start/ref/alt; the rest is annotation the parquet carries
    for RM4 (never enters resolution.csv — orthogonal axes, P5). Built lazily so importing this
    module without the `[dev]` polars extra doesn't fail — only building needs it."""
    return {
        "chrom": pl.Utf8,
        "start": pl.Int64,
        "ref": pl.Utf8,
        "alt": pl.Utf8,
        "rsid": pl.Utf8,
        "variation_id": pl.Utf8,
        "allele_id": pl.Utf8,
        "gene": pl.Utf8,
        "genes": pl.Utf8,
        "clin_sig": pl.Utf8,
        "clin_sig_raw": pl.Utf8,
        "review_status": pl.Utf8,
        "review_stars": pl.Int64,
        "condition": pl.Utf8,
        "molecular_consequence": pl.Utf8,
        "variant_type": pl.Utf8,
        "origin": pl.Utf8,
    }


# ── CLNSIG → VALID_CLIN_SIG normalization ──────────────────────────────────────────────────────
# ClinVar aggregate germline classifications (verbatim tokens, lowercased) mapped onto the module
# vocabulary. A token ClinVar coins that has no module axis maps to "other" via the default; the raw
# CLNSIG is always kept in `clin_sig_raw`, so nothing is lost and the mapping stays auditable.
_CLIN_SIG_MAP: dict[str, str] = {
    "pathogenic": "pathogenic",
    "pathogenic_low_penetrance": "pathogenic",
    "likely_pathogenic": "likely_pathogenic",
    "likely_pathogenic_low_penetrance": "likely_pathogenic",
    "uncertain_significance": "uncertain_significance",
    "uncertain_risk_allele": "uncertain_significance",
    "likely_benign": "likely_benign",
    "benign": "benign",
    "drug_response": "drug_response",
    "association": "association",
    "association_not_found": "other",
    "risk_factor": "risk_factor",
    "established_risk_allele": "risk_factor",
    "likely_risk_allele": "risk_factor",
    "protective": "protective",
    "affects": "affects",
    "conflicting_classifications_of_pathogenicity": "conflicting",
    "conflicting_interpretations_of_pathogenicity": "conflicting",
    "not_provided": "not_provided",
    "no_classification_provided": "not_provided",
    "no_classification_for_the_single_variant": "not_provided",
    "no_classifications_from_unflagged_records": "not_provided",
    "no_assertion_provided": "not_provided",
    "other": "other",
    "confers_sensitivity": "other",
    "low_penetrance": "other",
}
# When a single CLNSIG carries several values (`Pathogenic/Likely_pathogenic`, joined by | or /),
# the winner is the most clinically consequential — picked by this explicit order, never set
# iteration (Principle 7: deterministic). Every member of VALID_CLIN_SIG appears exactly once.
_CLIN_SIG_SEVERITY: tuple[str, ...] = (
    "pathogenic",
    "likely_pathogenic",
    "drug_response",
    "risk_factor",
    "affects",
    "association",
    "protective",
    "conflicting",
    "uncertain_significance",
    "likely_benign",
    "benign",
    "not_provided",
    "other",
)
assert set(_CLIN_SIG_SEVERITY) == VALID_CLIN_SIG, "severity order must cover VALID_CLIN_SIG exactly"

_CLIN_SIG_SPLIT = re.compile(r"[|/,]")

# ClinVar review status → gold-star rating (the ClinVar star system).
_REVIEW_STARS: dict[str, int] = {
    "practice_guideline": 4,
    "reviewed_by_expert_panel": 3,
    "criteria_provided,_multiple_submitters,_no_conflicts": 2,
    "criteria_provided,_single_submitter": 1,
    "criteria_provided,_conflicting_classifications": 1,
    "criteria_provided,_conflicting_interpretations": 1,
    "no_assertion_criteria_provided": 0,
    "no_classification_provided": 0,
    "no_classifications_from_unflagged_records": 0,
    "no_assertion_provided": 0,
}


def _normalize_clin_sig(raw: Optional[str]) -> str:
    """Fold a raw CLNSIG value into a single `VALID_CLIN_SIG` member (most-severe wins)."""
    if not raw:
        return "not_provided"
    tokens = {
        _CLIN_SIG_MAP.get(tok.strip().lower(), "other")
        for tok in _CLIN_SIG_SPLIT.split(raw)
        if tok.strip()
    }
    for sig in _CLIN_SIG_SEVERITY:
        if sig in tokens:
            return sig
    return "other"


def _review_stars(revstat: Optional[str]) -> int:
    return _REVIEW_STARS.get((revstat or "").strip(), 0)


# ── VCF parsing (idioms leeched from just-dna-lite v1_port.clinvar, kept for all records) ───────


def _parse_info(info: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for field_ in info.split(";"):
        if "=" in field_:
            key, _, value = field_.partition("=")
            out[key] = value
    return out


def _genes(geneinfo: Optional[str]) -> list[str]:
    """GENEINFO is ``SYMBOL:id|SYMBOL2:id2`` — return the bare symbols in order."""
    if not geneinfo:
        return []
    return [pair.split(":", 1)[0] for pair in geneinfo.split("|") if pair]


def _norm_chrom(raw: str) -> Optional[str]:
    c = raw.removeprefix("chr")
    if c in ("M", "MT", "chrM"):
        c = "MT"
    return c if c in _VALID_CHROMS else None


def _molecular_consequence(mc: Optional[str]) -> Optional[str]:
    """MC is ``SO:id|consequence`` entries, comma-separated — return the first consequence label."""
    if not mc:
        return None
    first = mc.split(",", 1)[0]
    return first.split("|", 1)[1] if "|" in first else None


def _condition(clndn: Optional[str]) -> Optional[str]:
    """CLNDN preferred disease name; ClinVar underscore-encodes spaces."""
    if not clndn:
        return None
    return clndn.replace("_", " ").strip() or None


def _read_file_date(vcf_path: Path) -> Optional[str]:
    """The ClinVar release date from the ``##fileDate=YYYY-MM-DD`` header line."""
    with gzip.open(vcf_path, "rt") as handle:
        for line in handle:
            if not line.startswith("#"):
                break
            if line.startswith("##fileDate="):
                return line.split("=", 1)[1].strip()
    return None


def _iter_records(vcf_path: Path) -> Iterator[tuple[str, str, str, str, str, str]]:
    """Yield (chrom, pos, id, ref, alt_field, info) for every data line."""
    with gzip.open(vcf_path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 8:
                yield cols[0], cols[1], cols[2], cols[3], cols[4], cols[7]


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


# ── public API ──────────────────────────────────────────────────────────────────────────────────


class ClinVarBuildError(RuntimeError):
    """A ClinVar artifact could not be built from the file given."""


@dataclass
class BuildResult:
    """Outcome of a snapshot build (paths + provenance + skip stats)."""

    out_dir: Path
    parquet_files: list[Path]
    record_count: int
    clinvar_file_date: Optional[str]
    source_sha256: str
    chromosomes: list[str] = field(default_factory=list)
    skipped_non_acgt: int = 0
    skipped_too_long: int = 0
    skipped_bad_chrom: int = 0


def download_clinvar_vcf(dest: Path, url: str = DEFAULT_CLINVAR_URL) -> Path:
    """Stream the NCBI ClinVar VCF to ``dest`` (atomic ``.part`` rename), returning the path.

    Uses the core ``httpx`` (the enricher's network tier); sha256 is computed while streaming and
    logged. Provisioning-only — the resolver never calls this; it reads a prebuilt cache.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    hasher = hashlib.sha256()
    logger.info("Downloading ClinVar VCF from %s ...", url)
    with httpx.stream("GET", url, follow_redirects=True, timeout=None) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
                hasher.update(chunk)
    tmp.replace(dest)
    logger.info("Downloaded %s (sha256 %s)", dest, hasher.hexdigest())
    return dest


def download_var_citations(dest: Path, url: str = DEFAULT_CITATIONS_URL) -> Path:
    """Stream ClinVar's `var_citations.txt` to `dest`, the same way the VCF is fetched.

    A *separate* download because ClinVar publishes it separately — the VCF carries no PMIDs. That
    absence is why a drafted gene panel could not compile: `studies.csv` is mandatory ("grounding
    evidence is mandatory") and the provider had nothing to ground rows with.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    hasher = hashlib.sha256()
    logger.info("Downloading ClinVar citations from %s ...", url)
    with httpx.stream("GET", url, follow_redirects=True, timeout=None) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
                hasher.update(chunk)
    tmp.replace(dest)
    logger.info("Downloaded %s (sha256 %s)", dest, hasher.hexdigest())
    return dest


#: Where the citations table lives. A **sibling of** `data/`, never inside it: `clinvar._connect`
#: builds its view from `data/*.parquet`, so a two-column citations file dropped in there unions with
#: the 17-column variant parquet and every query breaks. (Learned the direct way.)
CITATIONS_DIRNAME = "citations"


def build_citations(citations_txt: Path, out_dir: Path) -> int:
    """`var_citations.txt` → `out_dir/citations/citations.parquet`, PubMed rows only.

    Written **beside** an existing snapshot rather than into it: the per-chromosome parquet keeps its
    bytes, so adding citations to a cache someone already built does not invalidate it. Only PubMed
    sources are kept — the format's `StudyRow.pmid` is a PMID, and a curated module citing a source
    the schema cannot express would be a row nobody can check.

    Sorted by `(variation_id, pmid)` so a rebuild is byte-identical (Principle 7).
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the ClinVar citations table; install the publisher/dev "
            "surface with `pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    frame = pl.read_csv(
        citations_txt, separator="\t", has_header=True, infer_schema_length=0,
        truncate_ragged_lines=True,
    )
    columns = {name.lstrip("#").strip(): name for name in frame.columns}
    variation = columns.get("VariationID")
    source = columns.get("citation_source")
    citation = columns.get("citation_id")
    if not (variation and source and citation):
        raise ClinVarBuildError(
            f"unexpected var_citations.txt columns: {frame.columns}. Refusing rather than guessing — "
            f"a silently mis-parsed citations table would ground module rows in the wrong papers."
        )
    kept = (
        frame.filter(pl.col(source) == "PubMed")
        .select(
            pl.col(variation).cast(pl.Utf8).alias("variation_id"),
            pl.col(citation).cast(pl.Utf8).alias("pmid"),
        )
        .unique()
        .sort(["variation_id", "pmid"])
    )
    target = Path(out_dir) / CITATIONS_DIRNAME
    target.mkdir(parents=True, exist_ok=True)
    kept.write_parquet(target / "citations.parquet")
    logger.info("Wrote %s PubMed citation link(s)", kept.height)
    return kept.height


def build_snapshot(
    vcf: Path,
    out_dir: Path,
    *,
    source_url: str = DEFAULT_CLINVAR_URL,
) -> BuildResult:
    """Convert a ClinVar VCF into the per-chromosome parquet snapshot + ``release.json``.

    One row per ACGT ALT allele (short indels kept, symbolic/structural alleles skipped and counted).
    Rows are written sorted by ``(start, ref, alt, rsid, variation_id)`` per chromosome so a rebuild
    is byte-identical (Principle 7 idempotency); ``release.json``'s ``built_at`` is the only
    per-run-varying byte and lives outside the parquet.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the ClinVar snapshot; install the publisher/dev surface "
            "with `pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    vcf = Path(vcf)
    if not vcf.exists():
        raise FileNotFoundError(f"ClinVar VCF not found at {vcf}")
    out_dir = Path(out_dir)
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    by_chrom: dict[str, list[dict]] = {}
    skipped_non_acgt = skipped_too_long = skipped_bad_chrom = 0

    for chrom_raw, pos_s, vid, ref, alt_field, info in _iter_records(vcf):
        chrom = _norm_chrom(chrom_raw)
        if chrom is None:
            skipped_bad_chrom += 1
            continue
        info_d = _parse_info(info)
        rs = info_d.get("RS")
        rsid = f"rs{rs.split('|')[0]}" if rs else None
        gene_syms = _genes(info_d.get("GENEINFO"))
        clnsig_raw = info_d.get("CLNSIG")
        shared = {
            "chrom": chrom,
            "start": int(pos_s),
            "ref": ref.strip().upper(),
            "rsid": rsid,
            "variation_id": vid or None,
            "allele_id": info_d.get("ALLELEID"),
            "gene": gene_syms[0] if gene_syms else None,
            "genes": "|".join(gene_syms) if gene_syms else None,
            "clin_sig": _normalize_clin_sig(clnsig_raw),
            "clin_sig_raw": clnsig_raw,
            "review_status": info_d.get("CLNREVSTAT"),
            "review_stars": _review_stars(info_d.get("CLNREVSTAT")),
            "condition": _condition(info_d.get("CLNDN")),
            "molecular_consequence": _molecular_consequence(info_d.get("MC")),
            "variant_type": info_d.get("CLNVC"),
            "origin": info_d.get("ORIGIN"),
        }
        ref_u = shared["ref"]
        for alt in alt_field.split(","):
            alt_u = alt.strip().upper()
            if not (_ACGT_RE.match(ref_u) and _ACGT_RE.match(alt_u)) or ref_u == alt_u:
                skipped_non_acgt += 1
                continue
            if len(ref_u) > MAX_ALLELE_LEN or len(alt_u) > MAX_ALLELE_LEN:
                skipped_too_long += 1
                continue
            by_chrom.setdefault(chrom, []).append({**shared, "alt": alt_u})

    schema = _empty_schema()
    parquet_files: list[Path] = []
    record_count = 0
    written_chroms: list[str] = []
    # Karyotype order for files; unknown-but-valid chroms (shouldn't occur) appended sorted after.
    ordered = [c for c in _CHROM_ORDER if c in by_chrom] + sorted(
        c for c in by_chrom if c not in _CHROM_ORDER
    )
    for chrom in ordered:
        df = pl.DataFrame(by_chrom[chrom], schema=schema).sort(
            ["start", "ref", "alt", "rsid", "variation_id"], nulls_last=True
        )
        path = data_dir / f"clinvar-chr{chrom}.parquet"
        df.write_parquet(path)
        parquet_files.append(path)
        record_count += df.height
        written_chroms.append(chrom)

    file_date = _read_file_date(vcf)
    source_sha256 = _sha256_file(vcf)
    _write_release_json(
        out_dir,
        clinvar_file_date=file_date,
        source_url=source_url,
        source_sha256=source_sha256,
        record_count=record_count,
    )
    logger.info(
        "Built ClinVar snapshot: %d rows across %d chromosomes → %s "
        "(skipped: non-ACGT %d, too-long %d, off-target chrom %d)",
        record_count, len(written_chroms), data_dir,
        skipped_non_acgt, skipped_too_long, skipped_bad_chrom,
    )
    return BuildResult(
        out_dir=out_dir,
        parquet_files=parquet_files,
        record_count=record_count,
        clinvar_file_date=file_date,
        source_sha256=source_sha256,
        chromosomes=written_chroms,
        skipped_non_acgt=skipped_non_acgt,
        skipped_too_long=skipped_too_long,
        skipped_bad_chrom=skipped_bad_chrom,
    )


def _write_release_json(
    out_dir: Path,
    *,
    clinvar_file_date: Optional[str],
    source_url: str,
    source_sha256: str,
    record_count: int,
) -> Path:
    """Write ``release.json`` — the provenance that feeds `GenePanelSpec.reference`/`reference_sha256`
    (RM4). `built_at` is deliberately outside the parquet so the parquet stays byte-reproducible."""
    from datetime import datetime, timezone
    import json

    release = {
        "clinvar_file_date": clinvar_file_date,
        "source_url": source_url,
        "source_sha256": source_sha256,
        "record_count": record_count,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "builder_version": _builder_version(),
    }
    path = out_dir / "release.json"
    path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
