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

import json
import logging
import os
from pathlib import Path

from dotenv import dotenv_values, find_dotenv, load_dotenv
from just_dna_format.snapshot import ACMG_SNAPSHOT_FILENAME as ACMG_SNAPSHOT_FILENAME
from just_dna_format.snapshot import ALPHAGENOME_KNOTS_FILENAME as ALPHAGENOME_KNOTS_FILENAME
from just_dna_format.snapshot import CITATIONS_DIRNAME as CITATIONS_DIRNAME
from just_dna_format.snapshot import RELEASE_FILENAME as RELEASE_FILENAME
from just_dna_format.snapshot import SNAPSHOT_DATA_DIRNAME as SNAPSHOT_DATA_DIRNAME
from just_dna_format.snapshot import SNAPSHOT_LICENSE_FILENAME as SNAPSHOT_LICENSE_FILENAME
from just_dna_format.snapshot import SNAPSHOT_ROOT_FILENAMES as SNAPSHOT_ROOT_FILENAMES
from just_dna_format.snapshot import SNAPSHOT_SIDECAR_DIRNAMES as SNAPSHOT_SIDECAR_DIRNAMES
from just_dna_format.snapshot import STRCHIVE_CATALOGUE_FILENAME as STRCHIVE_CATALOGUE_FILENAME
from just_dna_format.snapshot import holds_snapshot_payload as holds_snapshot_payload
from just_dna_format.snapshot import read_release as read_release
from platformdirs import user_cache_dir

logger = logging.getLogger(__name__)

APPNAME: str = "just-dna-pipelines"

# ── the snapshot layout ─────────────────────────────────────────────────────────────────────────
#
# A reference snapshot is `data/*.parquet` + optional parquet **sidecars** beside it + `LICENSE.txt` +
# `release.json`. Six parties have to agree on those names — the builder writes them, the publisher
# uploads them, the provisioner fetches them, the resolver judges the directory, the reporter prints
# the label, a pass reads the release — and every disagreement so far has been silent: `release.json`
# was uploaded and never fetched, `citations/` was built and never published. The names, the model of
# `release.json` and its reader are the format tier's contract since 0.8 (RM303,
# `just_dna_format.snapshot`); this module imports them, so `from just_dna_enricher.locations import
# RELEASE_FILENAME` keeps working for every caller, and adds only what is deployment: where a snapshot
# lives on this machine, and the pull record of one machine's copy.

#: Where a build writes when the operator names nowhere. **Never the repository root**, which is the
#: rule this constant exists to make impossible to forget: nine `--out` defaults were bare relative
#: names (`civic`, `clinvar`, `mitomap`, …), so running any of them from a checkout dropped a snapshot
#: directory beside `pyproject.toml` — the exact defect `civic reproduce` was corrected for once
#: already, and it came back nine times because the rule lived in prose and every new builder wrote its
#: own literal. `/data/` is git-ignored and build-ignored whole, so a default under it needs no
#: `.gitignore` line and can never be committed by a blind `git add`.
REPRO_DIRNAME = "data/repro"

#: Where `cache rebuild` writes the lanes it cuts. A different concept from a repro build — a cache
#: base rather than one snapshot — and named here for the same reason: so no command spells it inline.
CACHES_DIRNAME = "data/caches"


def repro_out(name: str) -> Path:
    """The default `--out` for a builder, under `data/repro/<name>/`.

    Derived rather than restated, because a rule spelled out once per command is a rule that holds
    until somebody adds the tenth command. An AST guard over the CLI asserts every `--out` default
    resolves under `data/`, so a new builder that writes its own literal fails the suite rather than
    the operator's working tree.
    """
    return Path(REPRO_DIRNAME) / name


#: The provisioner's record of what a pull of this snapshot consists of (RM339): every file under
#: `data/` and the sidecar directories the remote listing named, written **before** the first
#: download rather than after the last. That order is the fix. Each file is staged through `.part` and
#: renamed only once whole, so an interrupted pull leaves nothing but whole files, and a cache holding
#: 3 of 25 chromosomes read as complete to every resolver. A record written at the end would leave the
#: same interrupted pull looking exactly like a cache provisioned before the record existed. Written
#: first, it names the 22 files that never arrived, and `snapshot_record_missing` reports them.
#:
#: **Not in `SNAPSHOT_ROOT_FILENAMES`, on purpose.** That registry is what a publish uploads and a
#: pull fetches. This file describes one machine's copy, never the published snapshot.
PULL_RECORD_FILENAME = "pull-record.json"

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

# ── the licence-gated caches (RM38) ─────────────────────────────────────────────────────────────
#
# The three PGx sources are the only `licensing.TERMS` entries with `commercial_use=False`, and they
# were the only ones with no cache at all — which is the *same* set, and not a coincidence worth
# leaving as one: Ensembl, ClinVar and gnomAD constraint are each snapshot-first already, so a hosted
# `enrich()` never reaches them live per request, while a hosted PGx check had exactly two options,
# fetch on the operator's own credentials or skip. Two independent reasons make that wrong for a
# service (the operator's acceptance and *personal* PharmVar key stand in for every caller's, and every
# published rate figure is per-IP so a server multiplies its callers onto one allowance), and either
# alone is enough.
#
# `clinpgx` had a builder and nothing else — no resolver, no `ensure_*` — so its snapshot was orphaned
# from the plumbing and `enrich_clinpgx` skipped silently unless handed `--snapshot` by hand.
CLINPGX_SUBDIR: str = "clinpgx"
CPIC_SUBDIR: str = "cpic"
#: PharmVar's cache is **operator-built and inject-only**: it is fetched under a key PharmVar's terms §2
#: make personal and non-transferable, and no axis `SourceTerms` records covers passing that on, so the
#: permission is unestablished — and an unestablished permission is never a permission (`None` ≠ `False`,
#: the same rule as `share_alike`/`commercial_use`). Hence a `resolve_` and a builder here, and
#: deliberately no `download.ensure_pharmvar_snapshot` and no publish command.
PHARMVAR_SUBDIR: str = "pharmvar"

#: PubMind's cache is inject-only for a different reason and the difference is worth reading. PharmVar's
#: bytes arrive under a key whose terms bar passing it on; PubMind's arrive under **CC BY-NC-ND 4.0**
#: (answered 2026-09-28, RM320), which allows sharing the table as published but not the snapshot,
#: since decomposing and normalizing it makes adapted material. Same consequence either way: a builder and a `resolve_`, deliberately no
#: `download.ensure_pubmind_snapshot` and no HF repo, and a `pubmind publish` that exists in order to
#: refuse rather than being absent for somebody to helpfully add.
PUBMIND_SUBDIR: str = "pubmind"

#: CIViC's cache is operator-built like the two above, and for neither of their reasons — its content
#: is CC0, so nothing bars publishing it. What it lacks is a *published* snapshot to download, because
#: this workspace has not built one; the builder and the resolver pair up exactly as the others do,
#: and adding an `ensure_civic_snapshot` later needs no permission, only a repo.
CIVIC_SUBDIR: str = "civic"

#: The three caches that had a builder and nothing else (RM176). Each was reachable only by handing
#: its check an explicit path, so on a deployment that provisions caches centrally the check simply
#: never ran — the same defect `CLINPGX_SUBDIR` records one paragraph up, three more times. The
#: shapes differ from every cache above them and that is why they were skipped: two of these snapshots
#: hold no parquet at all.
#:
#: ACMG's is a **CSV**: `acmg_sf.csv` + `release.json`, no `data/`. The list is 81 gene-condition rows
#: and a parquet for it would be ceremony. Operator-built: ACMG publishes the SF v3.3 list as
#: Elsevier supplementary material, so the workbook is supplied by whoever holds a copy and the
#: permission to republish these bytes is unestablished — not refused like PharmVar's, not granted
#: like STRchive's.
ACMG_SUBDIR: str = "acmg_sf"

#: STRchive's is a **JSON catalogue**: `STRchive-loci.json` + `release.json`, also no `data/`. It is
#: the upstream file verbatim beside the provenance of the fetch, because a repeat catalogue is read
#: whole rather than queried. MIT-licensed, so unlike the two beside it this one may be published.
STRCHIVE_SUBDIR: str = "strchive"

#: The regulator drug labels are a **second** ClinPGx archive with its own release cadence, so they
#: get their own cache rather than a table inside `clinpgx/`: `drugLabels.zip` and
#: `summaryAnnotations.zip` do not refresh in lockstep, and one directory holding both would date the
#: pair from whichever was built last. Same CC BY-SA terms as the annotation lane, so publishable on
#: the same grounds, and `LICENSE.txt` travels with it for the same reason.
DRUG_LABELS_SUBDIR: str = "drug_labels"

#: MANE's cache is a reference table rather than an annotation source: one agreed transcript per
#: protein-coding gene, plus the list of the ones MANE deliberately has no answer for and the list of
#: the ones whose Select accession has moved. Operator-built like the three above it, and for a fourth
#: reason again — NCBI states a *policy* rather than a licence, so whether a snapshot of these bytes
#: may be published is unestablished, and an unestablished permission is not a permission. Build one
#: with `mane build --download`.
MANE_SUBDIR: str = "mane"

#: Open Targets' cache (0.8, RM333) is a **trimmed** cut of one Platform release (26.09): the GWAS
#: credible sets and their members, the locus-to-gene scores, the GWAS-left × molecular-QTL-right
#: colocalisations, and every variant's per-transcript consequences, flattened to parquet so the
#: runtime pass reads it with duckdb. The release is marked CC0, so publishing it is not barred; what
#: is missing is a repository, which is why there is no `download.ensure_opentargets_snapshot` yet.
#: Build one with `opentargets build`.
OPENTARGETS_SUBDIR: str = "opentargets"

#: MITOMAP's cache is a **parquet** snapshot cut from the source's own `pg_dump` (RM171): the two
#: curated variant tables, their citation links and the reference records, out of a 6.76 M-line file
#: whose other hundred tables this tier has no use for. CC BY 3.0 with commercial use stated free, so
#: unlike the four caches above it this one may be published — the licence grants redistribution
#: outright, and what was missing was plumbing rather than permission.
MITOMAP_SUBDIR: str = "mitomap"

#: The **derived** cache, and the only one in the registry that is not a download (RM171). Its acquire
#: stage is *both parents on disk*: it is the join of the MITOMAP snapshot against the ClinVar chrMT
#: parquet, and it exists as a snapshot rather than as a computation inside `draft` so the increment
#: has an identity a currency check can talk about. Its `release.json` pins both parents, which is
#: what makes a ClinVar rebuild without a child rebuild a detectable stale child rather than a silent
#: one. Not published: a pulled child would carry pins for parents the puller does not have.
MITOMAP_MISS_SUBDIR: str = "mitomap_miss"

#: AlphaGenome's AVI scores, re-encoded (RM191). The **only lane the tier cannot acquire for itself**:
#: the artifact is 88.5 GB behind a sign-in whose eligibility clause bars whole classes of holder
#: (ALPHAGENOME_ATLAS.md § 2.1), so `alphagenome build --input` reads a file the operator downloaded
#: and there is no `rebuild` adapter to run without one. Its licence class is also the one thing about
#: it that is *unknown* rather than permissive — RM195 — so `commercial_use` is `None` and nothing
#: publishes it.
ALPHAGENOME_AVI_SUBDIR: str = "alphagenome_avi"

#: ClinGen's ClinVar-GKM, cut to the indels (RM305): the alleles whose placement is in doubt, each with
#: its VRS id, its SPDI and its gnomAD-style VCF spelling, joined to the ClinVar variation and rsID that
#: name it. A **witness**, not a source of calls: clinical significance still comes from the `clinvar`
#: lane, and this one is read only to ask where an indel sits. CC0 over ClinGen's transformation of
#: public-domain ClinVar, so it may be published.
CLINVAR_GKM_SUBDIR: str = "clinvar_gkm"


# ── The override variables, one per lane, plus the shared base ──────────────────────────────────
# Named here rather than as a literal inside each resolver (S89, RM184), so `caches.CACHE_LANES`
# can carry the variable that steers a lane as a field — `env_var` — and a consumer generating a
# `.env.template`, clearing its test environment, or auditing which caches were provisioned by
# variable reads the registry instead of hand-keeping fourteen names. `CACHE_BASE_VAR` is the one
# variable no lane owns: it moves every lane's default directory at once. Every string here is the
# whole set — a test walks this module for `JUST_DNA_*` values and asserts the lanes claim exactly
# those, so a resolver reading a variable no lane names fails the walk.
CACHE_BASE_VAR: str = "JUST_DNA_PIPELINES_CACHE_DIR"
ENSEMBL_CACHE_VAR: str = "JUST_DNA_ENSEMBL_CACHE"
CLINVAR_CACHE_VAR: str = "JUST_DNA_CLINVAR_CACHE"
CONSTRAINT_CACHE_VAR: str = "JUST_DNA_GNOMAD_CONSTRAINT_CACHE"
CLINPGX_CACHE_VAR: str = "JUST_DNA_CLINPGX_CACHE"
CPIC_CACHE_VAR: str = "JUST_DNA_CPIC_CACHE"
PHARMVAR_CACHE_VAR: str = "JUST_DNA_PHARMVAR_CACHE"
PUBMIND_CACHE_VAR: str = "JUST_DNA_PUBMIND_CACHE"
CIVIC_CACHE_VAR: str = "JUST_DNA_CIVIC_CACHE"
ACMG_CACHE_VAR: str = "JUST_DNA_ACMG_CACHE"
STRCHIVE_CACHE_VAR: str = "JUST_DNA_STRCHIVE_CACHE"
DRUG_LABELS_CACHE_VAR: str = "JUST_DNA_DRUG_LABELS_CACHE"
MANE_CACHE_VAR: str = "JUST_DNA_MANE_CACHE"
MITOMAP_CACHE_VAR: str = "JUST_DNA_MITOMAP_CACHE"
MITOMAP_MISS_CACHE_VAR: str = "JUST_DNA_MITOMAP_MISS_CACHE"
ALPHAGENOME_AVI_CACHE_VAR: str = "JUST_DNA_ALPHAGENOME_AVI_CACHE"
CLINVAR_GKM_CACHE_VAR: str = "JUST_DNA_CLINVAR_GKM_CACHE"
OPENTARGETS_CACHE_VAR: str = "JUST_DNA_OPENTARGETS_CACHE"


_PARQUET_MAGIC = b"PAR1"


def parquet_footer_ok(path: Path) -> bool:
    """A complete parquet begins and ends with the `PAR1` magic. A truncated/interrupted download —
    the common cache-corruption mode — is missing its footer, which is what makes DuckDB blow up with
    "No magic bytes found at end of file". Reads only 4 bytes from each end.

    Here rather than in `download` because a resolver judges a recorded file by it too (RM339), and
    this module never imports the network tier."""
    if not path.is_file() or path.stat().st_size < 8:
        return False
    with path.open("rb") as fh:
        if fh.read(4) != _PARQUET_MAGIC:
            return False
        fh.seek(-4, 2)
        return fh.read(4) == _PARQUET_MAGIC


def snapshot_record_missing(cache_dir: Path) -> list[str] | None:
    """The files `cache_dir`'s pull record names that are absent or truncated, or `None` with no record.

    Three answers, and a caller branches on all three (RM339). `[]`: the pull that wrote the record
    finished, so the cache is complete. A non-empty list: a pull was planned and did not finish, so the
    cache is **not** a snapshot yet, and these are what it lacks. `None`: no record, so nothing here can
    say. That is a cache built locally, or one pulled before the record existed; the resolvers treat
    it as they always did, and the provisioner compares it with the remote listing once.

    A record that is present and unreadable is `None` with a warning. The provisioner rewrites it on
    its next pull, and refusing a whole cache over its bookkeeping would cost a reader its snapshot.
    """
    path = Path(cache_dir) / PULL_RECORD_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        files = payload["files"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Could not read %s (%s); treating the cache as unrecorded.", path, exc)
        return None
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        logger.warning("%s names no file list; treating the cache as unrecorded.", path)
        return None
    return [name for name in files if not parquet_footer_ok(Path(cache_dir) / name)]


def load_env(override: bool = False) -> str | None:
    """Load the nearest `.env` (walking up from CWD) into `os.environ`, so cache paths can be set there.
    Returns the loaded path, or None.

    **Every variable in the file is exported, so only the cache resolvers call this.** A credential is
    read with `env_value`, which exports nothing (RM301, S124).
    """
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path, override=override)
        return env_path
    return None


def env_value(var: str) -> str | None:
    """One variable, from the process environment or else the nearest `.env`, **without exporting the file**.

    This is how a credential is read where it is used (`@credential-where-read`). The precedence is
    `load_env`'s: `override=False` keeps a variable that is present, so an exported value wins over the
    file, and an exported empty string stays empty. The difference is that nothing is written into
    `os.environ`. RM301 (S124): every client used to call `load_env()`, which copied the *whole* `.env`
    into the host's environment. A host that reports which layer each of its own settings came from
    then saw every file value as an exported shell variable.

    The file is found per call, walking up from the CWD, like `load_env`. `None` means neither source
    names the variable. An empty string means one of them sets it empty.
    """
    if var in os.environ:
        return os.environ[var]
    path = find_dotenv(usecwd=True)
    if not path:
        return None
    return dotenv_values(path).get(var)


def missing_credential_reason(var: str) -> str:
    """Why `$var` is unusable — **absent** and **exported empty** are two states, not one.

    `load_env` uses ``override=False``, so a variable that is *present* is kept whatever the `.env`
    says — and an empty string is present. That makes `export FOO=` strictly stronger than deleting
    the variable, which is the opposite of what anyone expects and is the same edge the tier's own
    tests exploit deliberately (a test neutralizes a credential with `""` precisely because `delenv`
    would let the developer's `.env` refill it).

    It bites for real: a shell that ran a snippet whose placeholder was edited out — `export
    PHARMVAR_API_KEY=` — reports *no key* for the rest of the session on a machine whose `.env` holds
    a working one, and nothing in the message says why. So the two readings are named separately and
    the empty one carries its own remedy, because `unset` and "go and get a key" are different
    actions (`@rsid-absent-two-readings` is the same rule about a different absence).
    """
    value = os.getenv(var)
    if value is None and env_value(var) == "":
        return (
            f"${var} is set EMPTY in the `.env` beside the working directory. Give it a value there, "
            f"or export it"
        )
    if value is None:
        return (
            f"no ${var} is set. A `.env` beside the working directory is read automatically, so "
            f"either add it there or export it"
        )
    return (
        f"${var} is set but EMPTY, and an empty exported variable outranks a `.env`: the loader uses "
        f"override=False, so it keeps a variable that is present. Run `unset {var}` — deleting it is "
        f"what lets the file supply the real one"
    )


def default_ensembl_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/ensembl_variations` directory, matching just-dna-lite's convention."""
    return _cache_dir(ENSEMBL_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_ensembl_reference(
    ensembl_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a usable Ensembl reference without downloading.

    Precedence: explicit `ensembl_cache` → ``$JUST_DNA_ENSEMBL_CACHE`` → the just-dna-lite layout
    under ``$JUST_DNA_PIPELINES_CACHE_DIR`` / platformdirs. Prefers a prebuilt
    ``ensembl_variations.duckdb``; otherwise the directory of parquet files. Returns the resolved
    path (a ``.duckdb`` file or a directory), or ``None`` if nothing is present.
    """
    if load_dotenv_file:
        load_env()

    candidate = ensembl_cache or os.getenv(ENSEMBL_CACHE_VAR)
    search_dir = (
        Path(candidate) if candidate else default_ensembl_cache_dir(load_dotenv_file=load_dotenv_file)
    )

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
        # A pull that never finished is not a snapshot (RM339). The prebuilt `.duckdb` is a built
        # artifact and keeps its standing; only the parquet payload is judged by the pull record.
        if has_db or (has_parquet and not snapshot_record_missing(search_dir)):
            return search_dir
    return None


def _cache_dir(subdir: str, *, load_dotenv_file: bool = True) -> Path:
    """`<base>/<subdir>`, where `<base>` is `$JUST_DNA_PIPELINES_CACHE_DIR` or the platformdirs cache.

    Every snapshot shares one base so a single just-dna-lite deployment's cache serves all of them.
    Read at call time rather than at import, because a `.env` loaded by `load_env` has to be able to
    change the answer.

    **It loads the `.env` itself, and that is the fix for a whole family of "the cache is right there"
    reports.** `_resolve_parquet_cache` calls `load_env()` inside itself, but each `resolve_*_reference`
    passes `default_*_cache_dir()` as an *argument* — evaluated before the call, therefore before the
    environment is loaded. So with the base set only in `.env`, the **first** resolve in a process
    computed its default from platformdirs and returned `None`, while every later one was correct
    (the environment was loaded by then). That asymmetry is nearly invisible and produced three
    separate bug reports: `cache pull` writing into `~/.cache` while `cache status` looked in the
    configured directory and reported *absent* right after a successful pull, `draft-panel --offline`
    refusing with "no ClinVar snapshot found" for a snapshot `cache status` called present, and a test
    module whose first skip-guard silently skipped. Loading here fixes all six resolvers and both CLI
    paths at once, because this is the one function all of them go through. `override=False`, so a
    real environment variable — and a test's deliberately empty one — still wins.

    **`load_dotenv_file=False` has to reach here or it means nothing, and until 0.6.3 it did not
    (S39).** The load above is unconditional, and each resolver's default directory goes through it —
    as an *argument*, so it ran before the resolver had even looked at its own flag. A caller asking
    for no `.env` therefore got one loaded anyway, in all six resolvers, and `load_dotenv` mutates the
    whole process environment: a consumer's test that had deleted a credential from `os.environ` had it
    refilled from a developer's `.env`, because `override=False` skips a variable that is *present* and
    deleting it is exactly what lets the file win. The flag is threaded rather than the load removed —
    the unconditional load is itself the repair described above, and the True path is unchanged.
    """
    if load_dotenv_file:
        load_env()
    base = os.getenv(CACHE_BASE_VAR)
    root = Path(base) if base else Path(user_cache_dir(appname=APPNAME))
    return root / subdir


def _resolve_parquet_cache(
    explicit: Path | None,
    env_var: str,
    default_dir: Path,
    *,
    load_dotenv_file: bool = True,
    accept_bare_file: bool = False,
) -> Path | None:
    """The precedence ladder every parquet snapshot shares: explicit → `$env_var` → the default dir.

    Returns the cache **directory** when it holds `data/*.parquet` (or bare `*.parquet`) and is not an
    unfinished pull (`snapshot_record_missing`, RM339), else `None`.
    Never downloads — provisioning is `download.ensure_*` or the deployment's job. `accept_bare_file`
    additionally lets a caller point straight at one `.parquet`, which only the constraint snapshot
    (a single file) has ever wanted.

    Six snapshots now share this body; it was copied per snapshot, and the copies had already drifted
    in exactly the way a copy does — the ClinVar one silently lacked the file case its sibling had.
    """
    if load_dotenv_file:
        load_env()

    candidate = explicit or os.getenv(env_var)
    search_dir = Path(candidate) if candidate else default_dir

    if accept_bare_file and search_dir.is_file() and search_dir.suffix == ".parquet":
        return search_dir
    # A pull that never finished is not a snapshot, however whole each of its files is (RM339).
    if holds_snapshot_payload(search_dir) and not snapshot_record_missing(search_dir):
        return search_dir
    return None


def default_clinvar_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/clinvar` directory (same base as the Ensembl cache)."""
    return _cache_dir(CLINVAR_SUBDIR, load_dotenv_file=load_dotenv_file)


def default_constraint_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/gnomad_constraint` directory (same base as the other two caches)."""
    return _cache_dir(CONSTRAINT_SUBDIR, load_dotenv_file=load_dotenv_file)


def default_clinpgx_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/clinpgx` directory — the ClinPGx clinical-annotation snapshot."""
    return _cache_dir(CLINPGX_SUBDIR, load_dotenv_file=load_dotenv_file)


def default_cpic_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/cpic` directory — the CPIC allele/diplotype/recommendation snapshot."""
    return _cache_dir(CPIC_SUBDIR, load_dotenv_file=load_dotenv_file)


def default_pharmvar_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/pharmvar` directory — operator-built only (see `PHARMVAR_SUBDIR`)."""
    return _cache_dir(PHARMVAR_SUBDIR, load_dotenv_file=load_dotenv_file)


def default_pubmind_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/pubmind` directory — operator-built only (see `PUBMIND_SUBDIR`)."""
    return _cache_dir(PUBMIND_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_constraint_reference(
    constraint_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a usable gnomAD constraint snapshot without downloading.

    Explicit argument → ``$JUST_DNA_GNOMAD_CONSTRAINT_CACHE`` → ``$JUST_DNA_PIPELINES_CACHE_DIR``
    /platformdirs ``gnomad_constraint/``. Parquet only (like ClinVar, there is no prebuilt
    ``.duckdb``), and a bare ``.parquet`` may be pointed at directly since the snapshot is one file.
    """
    return _resolve_parquet_cache(
        constraint_cache,
        CONSTRAINT_CACHE_VAR,
        default_constraint_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
        accept_bare_file=True,
    )


def resolve_clinvar_reference(
    clinvar_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a usable ClinVar reference without downloading.

    Mirrors `resolve_ensembl_reference`'s precedence: explicit `clinvar_cache` →
    ``$JUST_DNA_CLINVAR_CACHE`` → ``$JUST_DNA_PIPELINES_CACHE_DIR``/platformdirs `clinvar/`. The
    ClinVar snapshot ships as parquet only (no prebuilt ``.duckdb``); a directory is returned when it
    holds ``data/*.parquet`` (or bare ``*.parquet``), else ``None``. Never downloads — provisioning is
    the enricher's `download.ensure_clinvar_snapshot` or the deployment's job.
    """
    return _resolve_parquet_cache(
        clinvar_cache,
        CLINVAR_CACHE_VAR,
        default_clinvar_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def resolve_clinpgx_reference(
    clinpgx_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a built ClinPGx snapshot without downloading (`$JUST_DNA_CLINPGX_CACHE`).

    The builder shipped a release before this existed, so the snapshot was reachable only by handing
    `enrich_clinpgx` an explicit `--snapshot`; with no path the pass skipped itself and said so, which
    on a hosted deployment is the check simply not running. Provisioning is
    `download.ensure_clinpgx_snapshot`.
    """
    return _resolve_parquet_cache(
        clinpgx_cache,
        CLINPGX_CACHE_VAR,
        default_clinpgx_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def resolve_cpic_reference(cpic_cache: Path | None = None, *, load_dotenv_file: bool = True) -> Path | None:
    """Locate a built CPIC snapshot without downloading (`$JUST_DNA_CPIC_CACHE`)."""
    return _resolve_parquet_cache(
        cpic_cache,
        CPIC_CACHE_VAR,
        default_cpic_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def resolve_pharmvar_reference(
    pharmvar_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate an **operator-built** PharmVar snapshot (`$JUST_DNA_PHARMVAR_CACHE`).

    There is deliberately no `download.ensure_pharmvar_snapshot` to pair with this — see
    `PHARMVAR_SUBDIR`. A deployment builds its own with its own key, or this returns `None` and the
    PharmVar leg degrades exactly as it does when no key is configured.
    """
    return _resolve_parquet_cache(
        pharmvar_cache,
        PHARMVAR_CACHE_VAR,
        default_pharmvar_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def default_civic_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/civic` directory — operator-built for now (see `CIVIC_SUBDIR`)."""
    return _cache_dir(CIVIC_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_civic_reference(civic_cache: Path | None = None, *, load_dotenv_file: bool = True) -> Path | None:
    """Locate an operator-built CIViC snapshot (`$JUST_DNA_CIVIC_CACHE`).

    `None` when there is none, and the drafter reads that as nobody-asked rather than as an empty
    source (`@unreachable-not-absent`). Build one with `civic build --release <date>`.
    """
    return _resolve_parquet_cache(
        civic_cache,
        CIVIC_CACHE_VAR,
        default_civic_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def resolve_pubmind_reference(
    pubmind_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate an **operator-built** PubMind snapshot (`$JUST_DNA_PUBMIND_CACHE`).

    There is deliberately no `download.ensure_pubmind_snapshot` to pair with this — see
    `PUBMIND_SUBDIR`. A deployment builds its own with `pubmind build`, or this returns `None` and the
    PubMind leg reads `unchecked` rather than absent: nobody asked is a third state beside
    asked-and-failed and asked-and-absent (`@unreachable-not-absent`).
    """
    return _resolve_parquet_cache(
        pubmind_cache,
        PUBMIND_CACHE_VAR,
        default_pubmind_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def default_mane_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/mane` directory — operator-built only (see `MANE_SUBDIR`)."""
    return _cache_dir(MANE_SUBDIR, load_dotenv_file=load_dotenv_file)


def default_opentargets_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/opentargets` directory — see `OPENTARGETS_SUBDIR`."""
    return _cache_dir(OPENTARGETS_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_opentargets_reference(
    opentargets_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a built Open Targets snapshot (`$JUST_DNA_OPENTARGETS_CACHE`), without downloading.

    `None` is nobody-asked, never "Open Targets holds nothing for this variant": the pass that reads it
    says it skipped rather than writing an empty table (`@unreachable-not-absent`). A bare `.parquet`
    is not accepted: the snapshot is several tables read by name.
    """
    return _resolve_parquet_cache(
        opentargets_cache,
        OPENTARGETS_CACHE_VAR,
        default_opentargets_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def resolve_mane_reference(mane_cache: Path | None = None, *, load_dotenv_file: bool = True) -> Path | None:
    """Locate an **operator-built** MANE snapshot (`$JUST_DNA_MANE_CACHE`).

    There is deliberately no `download.ensure_mane_snapshot` to pair with this: nothing publishes a
    MANE snapshot, and NCBI's policy neither grants nor withholds permission to (see `MANE_SUBDIR`).
    `None` when there is none, and a reader must treat that as nobody-asked rather than as a gene
    MANE has no transcript for — the snapshot's own negative roster is what answers the second
    question, and it can only answer it once the snapshot exists (`@unreachable-not-absent`).

    A bare `.parquet` is **not** accepted here, unlike the constraint snapshot: this cache is three
    tables read by filename, so a single file pointed at directly would be a snapshot missing the
    currency check and the negative roster.
    """
    return _resolve_parquet_cache(
        mane_cache,
        MANE_CACHE_VAR,
        default_mane_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def _resolve_named_cache(
    explicit: Path | None,
    env_var: str,
    default_dir: Path,
    payload: str,
    *,
    load_dotenv_file: bool = True,
) -> Path | None:
    """`_resolve_parquet_cache`'s shape for a snapshot whose payload is one **named** file.

    Two caches hold no parquet at all — ACMG's list is `acmg_sf.csv` and STRchive's catalogue is
    `STRchive-loci.json`, both at the snapshot root beside `release.json`. The precedence ladder and
    the `.env` load are the parquet resolver's, verbatim and for its reasons; only the presence test
    differs, so this is the second predicate rather than a second ladder.

    A caller may point straight at the payload file, because both of these caches were reachable that
    way before they had a resolver at all (`check-repeat-bands --catalogue STRchive-loci.json`) and
    withdrawing that would be a break dressed up as a fix. The **directory** is returned when a
    directory was found, so `release.json` stays readable; a bare file is returned as itself, and its
    holder gets no release label — which is the honest answer, since a loose file carries none.
    """
    if load_dotenv_file:
        load_env()

    candidate = explicit or os.getenv(env_var)
    search = Path(candidate) if candidate else default_dir

    if search.is_file() and search.name == payload:
        return search
    if holds_snapshot_payload(search, payload_filename=payload):
        return search
    return None


def default_acmg_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/acmg_sf` directory — operator-built only (see `ACMG_SUBDIR`)."""
    return _cache_dir(ACMG_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_acmg_reference(acmg_cache: Path | None = None, *, load_dotenv_file: bool = True) -> Path | None:
    """Locate a built ACMG SF snapshot (`$JUST_DNA_ACMG_CACHE`), without downloading.

    `None` means nobody provisioned one, and `check-acmg` reads that as leave to fall back to
    scraping NCBI's page — which serves **v3.2** while ACMG published v3.3 in June 2025, so a
    correctly authored v3.3 row is reported as wrong by the fallback. That is the whole reason this
    resolver exists: the snapshot was buildable and unreachable unless a caller passed `--sf-list` by
    hand, so the accurate list was the one path a deployment never took.
    """
    return _resolve_named_cache(
        acmg_cache,
        ACMG_CACHE_VAR,
        default_acmg_cache_dir(load_dotenv_file=load_dotenv_file),
        ACMG_SNAPSHOT_FILENAME,
        load_dotenv_file=load_dotenv_file,
    )


def default_strchive_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/strchive` directory — see `STRCHIVE_SUBDIR`."""
    return _cache_dir(STRCHIVE_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_strchive_reference(
    strchive_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a built STRchive catalogue (`$JUST_DNA_STRCHIVE_CACHE`), without downloading.

    `None` is nobody-asked rather than "STRchive lists no such locus", and `check-repeat-bands` says
    so in those words (`@unreachable-not-absent`). A directory is preferred over a bare
    `STRchive-loci.json` because only the directory carries `release.json`, and without it the check
    cannot name the release it compared against.
    """
    return _resolve_named_cache(
        strchive_cache,
        STRCHIVE_CACHE_VAR,
        default_strchive_cache_dir(load_dotenv_file=load_dotenv_file),
        STRCHIVE_CATALOGUE_FILENAME,
        load_dotenv_file=load_dotenv_file,
    )


def default_mitomap_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/mitomap` directory — see `MITOMAP_SUBDIR`."""
    return _cache_dir(MITOMAP_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_mitomap_reference(
    mitomap_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a built MITOMAP snapshot (`$JUST_DNA_MITOMAP_CACHE`), without downloading.

    `None` is nobody-asked, not "MITOMAP publishes no such variant". It is also the parent absence the
    derived miss lane reports as *could not run* rather than as an empty increment: a miss set derived
    with one parent missing would be a claim about a comparison that never happened.
    """
    return _resolve_parquet_cache(
        mitomap_cache,
        MITOMAP_CACHE_VAR,
        default_mitomap_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def default_alphagenome_avi_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/alphagenome_avi` directory — see `ALPHAGENOME_AVI_SUBDIR`."""
    return _cache_dir(ALPHAGENOME_AVI_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_alphagenome_avi_reference(
    alphagenome_avi_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a built AVI snapshot (`$JUST_DNA_ALPHAGENOME_AVI_CACHE`), without downloading.

    `None` here is *nobody-asked* in its strongest form: this lane has no acquire stage at all, so an
    absent snapshot means the operator has not run `alphagenome build` against a file they hold — not
    that a fetch failed, and not that AlphaGenome scores nothing at that position
    (`@unreachable-not-absent`).
    """
    return _resolve_parquet_cache(
        alphagenome_avi_cache,
        ALPHAGENOME_AVI_CACHE_VAR,
        default_alphagenome_avi_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def default_mitomap_miss_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/mitomap_miss` directory — see `MITOMAP_MISS_SUBDIR`."""
    return _cache_dir(MITOMAP_MISS_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_mitomap_miss_reference(
    mitomap_miss_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a built MITOMAP-miss snapshot (`$JUST_DNA_MITOMAP_MISS_CACHE`), without downloading.

    A resolver for a derived snapshot answers a narrower question than the others: it says the join
    was run and its result is on disk, never that the result is still *current*. Currency is
    `mitomap_miss_build.stale_parents`, which re-reads both parents' `release.json` and names the one
    that moved — a snapshot present and stale is a different answer from absent, and the drafter says
    which (`@currency-asks-the-source-not-the-cache`).
    """
    return _resolve_parquet_cache(
        mitomap_miss_cache,
        MITOMAP_MISS_CACHE_VAR,
        default_mitomap_miss_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def default_clinvar_gkm_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/clinvar_gkm` directory — see `CLINVAR_GKM_SUBDIR`."""
    return _cache_dir(CLINVAR_GKM_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_clinvar_gkm_reference(
    clinvar_gkm_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a built ClinVar-GKM indel snapshot (`$JUST_DNA_CLINVAR_GKM_CACHE`), without downloading.

    Present says the slice is on disk, never that it is current: the source overwrites its one Parquet
    set every week, so currency is `clinvar_gkm_build.lane_currency`, which asks the source.
    """
    return _resolve_parquet_cache(
        clinvar_gkm_cache,
        CLINVAR_GKM_CACHE_VAR,
        default_clinvar_gkm_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )


def default_drug_labels_cache_dir(*, load_dotenv_file: bool = True) -> Path:
    """The `<base>/drug_labels` directory — see `DRUG_LABELS_SUBDIR`."""
    return _cache_dir(DRUG_LABELS_SUBDIR, load_dotenv_file=load_dotenv_file)


def resolve_drug_labels_reference(
    drug_labels_cache: Path | None = None, *, load_dotenv_file: bool = True
) -> Path | None:
    """Locate a built regulator drug-label snapshot (`$JUST_DNA_DRUG_LABELS_CACHE`).

    A parquet snapshot like ClinPGx's, and a **separate** cache from it on purpose: the two archives
    are dated from their own `CREATED_*.txt` and do not refresh together (`DRUG_LABELS_SUBDIR`).
    Provisioning is `download.ensure_drug_labels_snapshot`.
    """
    return _resolve_parquet_cache(
        drug_labels_cache,
        DRUG_LABELS_CACHE_VAR,
        default_drug_labels_cache_dir(load_dotenv_file=load_dotenv_file),
        load_dotenv_file=load_dotenv_file,
    )
