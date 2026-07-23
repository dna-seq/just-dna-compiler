"""HuggingFace snapshot provisioning — the bulk-fetch side of the resolver chain.

The Ensembl parquet snapshot is *not* a canonical reference: it is a static slice of the popular
rsIDs from Ensembl's full catalog, with the same pains as any source — incompleteness, versions, and
reachability (HF has gone dark mid-demo). So it is one resolver-chain source, downloaded here into a
cache the compiler's resolver reads directly (`<cache>/data/*.parquet`), with a partial/rare rsID
falling through to live Ensembl.

`huggingface_hub` is imported lazily and guarded: it is the one HuggingFace dependency in the whole
workspace, permitted only in this network tier (the 0.5 Constitution amendment scopes the HF ban to
format + compiler). The download logic is inherited from just-dna-lite's pipelines byte-for-byte
(footer-checked, atomic `.part` rename) so no drift is born.
"""

import logging
from pathlib import Path
from typing import Optional

from just_dna_compiler.cache import default_ensembl_cache_dir
from just_dna_compiler.resolver import EnsemblReferenceError

logger = logging.getLogger(__name__)

_PARQUET_MAGIC = b"PAR1"
_HF_REPO_PREFIX = "datasets/just-dna-seq/ensembl_variations/data"


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


def ensure_snapshot(ensembl_cache: Optional[Path] = None) -> Path:
    """Provision the Ensembl parquet cache from HuggingFace Hub, returning the cache directory.

    A non-empty cache with no truncated files is trusted without touching the network. Only an empty
    or corrupt cache (re-)downloads — a corrupt file left by an interrupted download is removed and
    refetched rather than skipped forever. The returned directory holds `data/*.parquet`, which the
    compiler's resolver reads directly (no prebuilt `.duckdb` required).
    """
    cache_dir = Path(ensembl_cache) if ensembl_cache is not None else default_ensembl_cache_dir()
    data_dir = cache_dir / "data"

    existing = list(data_dir.glob("*.parquet")) if data_dir.exists() else []
    corrupt = [p for p in existing if not _parquet_footer_ok(p)]
    if existing and not corrupt:
        return cache_dir

    for p in corrupt:
        logger.warning("Corrupt/truncated Ensembl parquet %s — removing for re-download", p.name)
        p.unlink()

    logger.info("Provisioning Ensembl parquet cache from HuggingFace Hub ...")
    try:
        from huggingface_hub import HfFileSystem, get_token
    except ImportError as exc:  # the one guarded optional import (CLAUDE.md)
        raise EnsemblReferenceError(
            "huggingface_hub is required to download the Ensembl snapshot; install "
            "just-dna-enricher (which depends on it) or point --ensembl-cache at a local cache"
        ) from exc

    data_dir.mkdir(parents=True, exist_ok=True)
    fs = HfFileSystem(token=get_token())
    remote_files = [f for f in fs.ls(_HF_REPO_PREFIX, detail=False) if f.endswith(".parquet")]
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
            raise EnsemblReferenceError(
                f"Downloaded {filename} is incomplete (missing parquet footer magic)"
            )
        tmp_path.replace(local_path)
    logger.info("Download complete: %s", cache_dir)
    return cache_dir
