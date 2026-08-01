"""HuggingFace snapshot provisioning — the bulk-fetch side of the resolver chain.

Two reference snapshots share one download body: the Ensembl parquet slice (popular rsIDs) and the
ClinVar parquet slice (clinically-curated GRCh38 records). Neither is a *canonical* reference — each
is a static slice with the usual pains (incompleteness, versions, reachability; HF has gone dark
mid-demo) — so each is one resolver-chain source downloaded into a cache the resolver reads directly
(`<cache>/data/*.parquet`), with a miss falling through to the next link.

`huggingface_hub` is imported lazily and guarded: it is the one HuggingFace dependency in the whole
workspace, permitted only in this network tier (the 0.5 Constitution amendment scopes the HF ban to
format + compiler). The download logic (footer-checked, atomic `.part` rename) is inherited from
just-dna-lite's pipelines byte-for-byte so no drift is born.
"""

import logging
from pathlib import Path
from typing import Optional

from just_dna_enricher.clinvar import ClinVarReferenceError
from just_dna_enricher.locations import (
    default_clinvar_cache_dir,
    default_constraint_cache_dir,
    default_ensembl_cache_dir,
)
from just_dna_enricher.resolver import EnsemblReferenceError

logger = logging.getLogger(__name__)

_PARQUET_MAGIC = b"PAR1"
_ENSEMBL_HF_PREFIX = "datasets/just-dna-seq/ensembl_variations/data"
_CLINVAR_HF_PREFIX = "datasets/just-dna-seq/clinvar/data"
_CONSTRAINT_HF_PREFIX = "datasets/just-dna-seq/gnomad_constraint/data"


class ConstraintReferenceError(FileNotFoundError):
    """Raised when the gnomAD constraint snapshot cannot be provisioned or has no usable parquet."""


def _parquet_footer_ok(path: Path) -> bool:
    """A complete parquet begins and ends with the `PAR1` magic. A truncated/interrupted download —
    the common cache-corruption mode — is missing its footer, which is what makes DuckDB blow up with
    "No magic bytes found at end of file". Reads only 4 bytes from each end."""
    if not path.is_file() or path.stat().st_size < 8:
        return False
    with path.open("rb") as fh:
        if fh.read(4) != _PARQUET_MAGIC:
            return False
        fh.seek(-4, 2)
        return fh.read(4) == _PARQUET_MAGIC


def _provision_snapshot(
    cache_dir: Path, hf_repo_prefix: str, *, label: str, error_cls: type[Exception]
) -> Path:
    """Provision a parquet cache from HuggingFace Hub, returning the cache directory.

    A non-empty cache with no truncated files is trusted without touching the network. Only an empty
    or corrupt cache (re-)downloads — a corrupt file left by an interrupted download is removed and
    refetched rather than skipped forever. The returned directory holds `data/*.parquet`, which the
    resolver reads directly (no prebuilt `.duckdb` required). Shared by the Ensembl and ClinVar
    snapshots; the two differ only in `hf_repo_prefix`, `label`, and the error type raised.
    """
    data_dir = cache_dir / "data"

    existing = list(data_dir.glob("*.parquet")) if data_dir.exists() else []
    corrupt = [p for p in existing if not _parquet_footer_ok(p)]
    if existing and not corrupt:
        return cache_dir

    for p in corrupt:
        logger.warning("Corrupt/truncated %s parquet %s — removing for re-download", label, p.name)
        p.unlink()

    logger.info("Provisioning %s parquet cache from HuggingFace Hub ...", label)
    try:
        from huggingface_hub import HfFileSystem, get_token
    except ImportError as exc:  # the one guarded optional import (CLAUDE.md)
        raise error_cls(
            f"huggingface_hub is required to download the {label} snapshot; install "
            f"just-dna-enricher (which depends on it) or point at a local cache"
        ) from exc

    data_dir.mkdir(parents=True, exist_ok=True)
    fs = HfFileSystem(token=get_token())
    remote_files = [f for f in fs.ls(hf_repo_prefix, detail=False) if f.endswith(".parquet")]
    logger.info("Found %d remote parquet files", len(remote_files))
    for remote_path in remote_files:
        filename = remote_path.rsplit("/", 1)[-1]
        local_path = data_dir / filename
        if _parquet_footer_ok(local_path):
            continue
        # Download to a temp path and rename only after the footer verifies, so an interrupted
        # download never leaves a truncated file under the real name.
        tmp_path = local_path.with_suffix(".part")
        logger.info("  Downloading %s ...", filename)
        fs.get(remote_path, str(tmp_path))
        if not _parquet_footer_ok(tmp_path):
            tmp_path.unlink(missing_ok=True)
            raise error_cls(f"Downloaded {filename} is incomplete (missing parquet footer magic)")
        tmp_path.replace(local_path)
    logger.info("Download complete: %s", cache_dir)
    return cache_dir


def ensure_snapshot(ensembl_cache: Optional[Path] = None) -> Path:
    """Provision the Ensembl parquet cache from HuggingFace Hub, returning the cache directory."""
    cache_dir = Path(ensembl_cache) if ensembl_cache is not None else default_ensembl_cache_dir()
    return _provision_snapshot(
        cache_dir, _ENSEMBL_HF_PREFIX, label="Ensembl", error_cls=EnsemblReferenceError
    )


def ensure_clinvar_snapshot(clinvar_cache: Optional[Path] = None) -> Path:
    """Provision the ClinVar parquet cache from HuggingFace Hub, returning the cache directory."""
    cache_dir = Path(clinvar_cache) if clinvar_cache is not None else default_clinvar_cache_dir()
    return _provision_snapshot(
        cache_dir, _CLINVAR_HF_PREFIX, label="ClinVar", error_cls=ClinVarReferenceError
    )


def ensure_constraint_snapshot(constraint_cache: Optional[Path] = None) -> Path:
    """Provision the gnomAD constraint parquet cache from HuggingFace Hub.

    The third caller of one download body — the plumbing generalized when ClinVar landed, so this is
    parameterization rather than new machinery.
    """
    cache_dir = (
        Path(constraint_cache) if constraint_cache is not None else default_constraint_cache_dir()
    )
    return _provision_snapshot(
        cache_dir, _CONSTRAINT_HF_PREFIX, label="gnomAD constraint",
        error_cls=ConstraintReferenceError,
    )
