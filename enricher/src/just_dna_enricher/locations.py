"""
Ensembl reference cache resolution — mirrors just-dna-lite's on-disk layout so a marketplace or
standalone compile can **reuse an existing just-dna-lite deployment's cache** (disk economy, no
re-download), pointed via `.env`.

Layout (identical to `just-dna-pipelines`)::

    <base>/ensembl_variations/data/*.parquet
    <base>/ensembl_variations/ensembl_variations.duckdb    # optional prebuilt view

where ``<base>`` is ``$JUST_DNA_PIPELINES_CACHE_DIR`` (the same var just-dna-lite uses), or the
platformdirs user cache for ``"just-dna-pipelines"``. ``$JUST_DNA_ENSEMBL_CACHE`` (a ``.duckdb``
file or a directory) overrides everything for explicit pointing.

This module **never downloads**: if no cache is present, resolution returns ``None`` and the
resolver skips with a warning. Provisioning the reference is the deployment's job.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from platformdirs import user_cache_dir

APPNAME: str = "just-dna-pipelines"

# ── the snapshot layout ─────────────────────────────────────────────────────────────────────────
#
# A reference snapshot is `data/*.parquet` + optional parquet **sidecars** beside it + `release.json`.
# Four parties have to agree on those names — the builder writes them, the publisher uploads them, the
# provisioner fetches them, the reader queries them — and every disagreement so far has been silent:
# `release.json` was uploaded and never fetched (so a provisioned snapshot could not say which release
# it was), and `citations/` was built and never published (so anyone who downloaded rather than built
# had no PMIDs, and a drafted gene panel could not compile for them — `studies.csv` is mandatory).
# One definition, imported by all four.

#: The records: what the readers glob.
SNAPSHOT_DATA_DIRNAME = "data"

#: ClinVar's literature links. A **sibling of** `data/`, never inside it: the readers build their view
#: from `data/*.parquet`, so a two-column citations file dropped in there unions with the 17-column
#: variant parquet and every query breaks. (Learned the direct way — and again, from the other end, when
#: a stale single-file `clinvar.parquet` in a published repo did the same thing.)
CITATIONS_DIRNAME = "citations"

#: Optional parquet sidecars a snapshot may carry. Shared by the publisher (which takes a directory and
#: cannot know which snapshot kind it is) and the provisioner, so a sidecar cannot be publishable but
#: unfetchable. Absent is normal: only ClinVar has one, and only when `clinvar citations` was run.
SNAPSHOT_SIDECAR_DIRNAMES: tuple[str, ...] = (CITATIONS_DIRNAME,)

#: The provenance beside the data. It describes **every** part of the snapshot, which is why the
#: citations builder merges its own block in rather than leaving a mixed-vintage artifact whose
#: `release.json` documents half of it: ClinVar publishes `var_citations.txt` on its own cadence, so the
#: records and the citations in one snapshot need not come from the same release.
RELEASE_FILENAME = "release.json"
ENSEMBL_SUBDIR: str = "ensembl_variations"
DUCKDB_NAME: str = "ensembl_variations.duckdb"
# ClinVar reference snapshot — a second, complementary reference beside Ensembl (clinically-curated
# GRCh38 records, ~200 MB gz), stored under `<base>/clinvar/data/*.parquet` in the same layout so one
# DuckDB view shape serves both.
CLINVAR_SUBDIR: str = "clinvar"
# gnomAD gene-constraint snapshot — the third reference, and by far the smallest (one row per gene,
# single-digit MB as parquet, versus ClinVar's ~200 MB and an Ensembl slice). Small enough to ship
# offline is exactly why gene constraint gets a snapshot while allele frequency cannot.
CONSTRAINT_SUBDIR: str = "gnomad_constraint"


def load_env(override: bool = False) -> Optional[str]:
    """Load the nearest `.env` (walking up from CWD), so cache paths can be set there.
    Returns the loaded path, or None."""
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path, override=override)
        return env_path
    return None


def default_ensembl_cache_dir() -> Path:
    """The `<base>/ensembl_variations` directory, matching just-dna-lite's convention."""
    base = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
    root = Path(base) if base else Path(user_cache_dir(appname=APPNAME))
    return root / ENSEMBL_SUBDIR


def resolve_ensembl_reference(
    ensembl_cache: Optional[Path] = None, *, load_dotenv_file: bool = True
) -> Optional[Path]:
    """Locate a usable Ensembl reference without downloading.

    Precedence: explicit `ensembl_cache` → ``$JUST_DNA_ENSEMBL_CACHE`` → the just-dna-lite layout
    under ``$JUST_DNA_PIPELINES_CACHE_DIR`` / platformdirs. Prefers a prebuilt
    ``ensembl_variations.duckdb``; otherwise the directory of parquet files. Returns the resolved
    path (a ``.duckdb`` file or a directory), or ``None`` if nothing is present.
    """
    if load_dotenv_file:
        load_env()

    candidate = ensembl_cache or os.getenv("JUST_DNA_ENSEMBL_CACHE")
    search_dir = Path(candidate) if candidate else default_ensembl_cache_dir()

    # Explicit pointing at a specific DuckDB file.
    if search_dir.is_file() and search_dir.suffix == ".duckdb":
        return search_dir

    # Otherwise return the cache directory if it holds a prebuilt db or parquet data; the
    # connection layer decides whether the db is usable and falls back to parquet if not.
    if search_dir.is_dir():
        data_dir = search_dir / "data"
        has_db = (search_dir / DUCKDB_NAME).is_file()
        has_parquet = (data_dir.is_dir() and any(data_dir.glob("*.parquet"))) or any(
            search_dir.glob("*.parquet")
        )
        if has_db or has_parquet:
            return search_dir
    return None


def default_clinvar_cache_dir() -> Path:
    """The `<base>/clinvar` directory (same base as the Ensembl cache)."""
    base = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
    root = Path(base) if base else Path(user_cache_dir(appname=APPNAME))
    return root / CLINVAR_SUBDIR


def default_constraint_cache_dir() -> Path:
    """The `<base>/gnomad_constraint` directory (same base as the other two caches)."""
    base = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
    root = Path(base) if base else Path(user_cache_dir(appname=APPNAME))
    return root / CONSTRAINT_SUBDIR


def resolve_constraint_reference(
    constraint_cache: Optional[Path] = None, *, load_dotenv_file: bool = True
) -> Optional[Path]:
    """Locate a usable gnomAD constraint snapshot without downloading.

    Same precedence ladder as the other two: explicit argument → ``$JUST_DNA_GNOMAD_CONSTRAINT_CACHE``
    → ``$JUST_DNA_PIPELINES_CACHE_DIR``/platformdirs ``gnomad_constraint/``. Parquet only (like
    ClinVar, there is no prebuilt ``.duckdb``). Never downloads.
    """
    if load_dotenv_file:
        load_env()

    candidate = constraint_cache or os.getenv("JUST_DNA_GNOMAD_CONSTRAINT_CACHE")
    search_dir = Path(candidate) if candidate else default_constraint_cache_dir()

    if search_dir.is_file() and search_dir.suffix == ".parquet":
        return search_dir
    if search_dir.is_dir():
        data_dir = search_dir / "data"
        has_parquet = (data_dir.is_dir() and any(data_dir.glob("*.parquet"))) or any(
            search_dir.glob("*.parquet")
        )
        if has_parquet:
            return search_dir
    return None


def resolve_clinvar_reference(
    clinvar_cache: Optional[Path] = None, *, load_dotenv_file: bool = True
) -> Optional[Path]:
    """Locate a usable ClinVar reference without downloading.

    Mirrors `resolve_ensembl_reference`'s precedence: explicit `clinvar_cache` →
    ``$JUST_DNA_CLINVAR_CACHE`` → ``$JUST_DNA_PIPELINES_CACHE_DIR``/platformdirs `clinvar/`. The
    ClinVar snapshot ships as parquet only (no prebuilt ``.duckdb``); a directory is returned when it
    holds ``data/*.parquet`` (or bare ``*.parquet``), else ``None``. Never downloads — provisioning is
    the enricher's `download.ensure_clinvar_snapshot` or the deployment's job.
    """
    if load_dotenv_file:
        load_env()

    candidate = clinvar_cache or os.getenv("JUST_DNA_CLINVAR_CACHE")
    search_dir = Path(candidate) if candidate else default_clinvar_cache_dir()

    if search_dir.is_dir():
        data_dir = search_dir / "data"
        has_parquet = (data_dir.is_dir() and any(data_dir.glob("*.parquet"))) or any(
            search_dir.glob("*.parquet")
        )
        if has_parquet:
            return search_dir
    return None
