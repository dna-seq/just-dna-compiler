"""The cache lanes as a registry, and the one endpoint that rebuilds them — RM176.

Twelve snapshots, eleven of them built here. Each is supposed to have three stages: **acquire** (a
download, or a file the operator supplies), **build** (the conversion into the snapshot a check
reads), and **publish** (the upload a deployment then pulls with `cache pull`). Before this module
the three stages existed as eleven independent CLI commands and one hand-kept four-tuple list inside
`cli.py`, and the gaps that arrangement hid were all of the same kind: something true of a lane that
no code anywhere asserted.

* Three lanes were missing from the roster entirely, so `cache status` reported nine caches on a
  machine that has twelve and `cache pull` could not be asked about them.
* Three had a licence permitting publication and no publish command.
* One had no way to be found at all without a flag on every invocation.

**So the registry is the point, not the rebuild command.** A list is only as complete as whoever last
edited it; a registry can be walked, and `test_cache_lanes.py` walks it against the `*_build` modules
on disk. That is the shape this repository keeps re-learning (`@registry-completeness`): assert an
equality over a walked set, never a floor and never a count in prose.

**Every absence carries its reason as a field, not as a comment.** A lane with no `ensure` states why
in `unpublished`, and the three reasons are genuinely different — PharmVar's and PubMind's are
refusals (a personal key; terms nobody publishes), ACMG's and MANE's are unestablished permissions,
and Ensembl's is that it is built elsewhere. A comment saying so speaks to whoever opens this file;
a field says it in `cache status`, in `cache pull` and in `cache rebuild`, which is where somebody
actually asks the question.

**The rebuild outcome is three-valued** (`@tri-state`). Built, failed, and *could not run
unattended* — ACMG needs a workbook that is Elsevier supplementary material, PharmVar needs a
personal key, CIViC needs a release date to pin. Folding the third into "failed" would have a nightly
rebuild report errors for lanes behaving exactly as designed; folding it into "built" would be a
lie. It is printed, never silently skipped.
"""

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from just_dna_enricher import (
    acmg_build,
    civic_build,
    clinpgx_build,
    clinvar_build,
    constraint_build,
    cpic_build,
    drug_labels_build,
    mane_build,
    pharmvar,
    pharmvar_build,
    pubmind_build,
    strchive_build,
)
from just_dna_enricher.download import (
    ensure_civic_snapshot,
    ensure_clinpgx_snapshot,
    ensure_clinvar_snapshot,
    ensure_constraint_snapshot,
    ensure_cpic_snapshot,
    ensure_drug_labels_snapshot,
    ensure_snapshot,
    ensure_strchive_snapshot,
)
from just_dna_enricher.licensing import (
    CLINPGX_TERMS,
    CPIC_TERMS,
    PHARMVAR_TERMS,
    LicenseRefusal,
    SourceTerms,
    check_declared_use,
)
from just_dna_enricher.locations import (
    ACMG_SUBDIR,
    CIVIC_SUBDIR,
    CLINPGX_SUBDIR,
    CLINVAR_SUBDIR,
    CONSTRAINT_SUBDIR,
    CPIC_SUBDIR,
    DRUG_LABELS_SUBDIR,
    ENSEMBL_SUBDIR,
    MANE_SUBDIR,
    PHARMVAR_SUBDIR,
    PUBMIND_SUBDIR,
    STRCHIVE_SUBDIR,
    resolve_acmg_reference,
    resolve_civic_reference,
    resolve_clinpgx_reference,
    resolve_clinvar_reference,
    resolve_constraint_reference,
    resolve_cpic_reference,
    resolve_drug_labels_reference,
    resolve_ensembl_reference,
    resolve_mane_reference,
    resolve_pharmvar_reference,
    resolve_pubmind_reference,
    resolve_strchive_reference,
)
from just_dna_enricher.upload import (
    DEFAULT_CIVIC_REPO_ID,
    DEFAULT_CLINPGX_REPO_ID,
    DEFAULT_CLINVAR_REPO_ID,
    DEFAULT_CONSTRAINT_REPO_ID,
    DEFAULT_CPIC_REPO_ID,
    DEFAULT_DRUG_LABELS_REPO_ID,
    DEFAULT_STRCHIVE_REPO_ID,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RebuildRequest:
    """What one lane's rebuild is given. The same four for every lane, so the loop has no branches.

    `pin` is the release to build — a MANE version, a CIViC release date, a STRchive tag. A lane that
    has no notion of one ignores it; a lane that *needs* one and did not get it reports
    could-not-run rather than quietly building the moving default, because a snapshot whose reference
    was "whatever was upstream that afternoon" cannot be compared against twice.

    `source` is the acquire stage's input when the operator already holds it — ACMG's workbook, a
    ClinVar VCF, a ClinPGx archive, a STRchive catalogue. For ACMG it is the *only* way, because the
    workbook is Elsevier supplementary material and nothing may fetch it on the author's behalf; for
    the rest it is the off-switch that lets a rebuild run with no network, which is the shape
    `@off-switch-needs-a-probe` asks for. **MANE and CIViC take three input files each and accept no
    `source`**: two of three is not a build for either of them, and a flag that can only ever supply
    one would be a flag that cannot do its job.
    """

    out_dir: Path
    declared_use: str = "unstated"
    pin: str | None = None
    source: Path | None = None


@dataclass(frozen=True)
class RebuildOutcome:
    """Built / failed / could-not-run, and the reason in every case.

    `built` is the tri-state: `True` the snapshot is on disk, `False` something went wrong, `None`
    this lane cannot be rebuilt unattended and that is by design. The third is not a failure and must
    not be counted as one — a nightly rebuild reporting an error for PharmVar would be reporting the
    licence working as intended.
    """

    lane: str
    built: bool | None
    detail: str
    out_dir: Path | None = None

    @property
    def label(self) -> str:
        return {True: "built", False: "FAILED", None: "not run"}[self.built]


#: A lane's rebuild adapter: request in, outcome out. Every adapter catches its own builder's errors
#: and returns `built=False` rather than raising, because one lane failing must not sink the rest —
#: the rule `cache pull` already follows for provisioning.
RebuildAdapter = Callable[[RebuildRequest], RebuildOutcome]


@dataclass(frozen=True)
class CacheLane:
    """One snapshot, all three of its stages, and the reason for each stage it does not have."""

    name: str
    subdir: str
    serves: str
    #: The lane's own CLI command, as an operator types it. **Not derivable from `name`** — the drug
    #: labels are `clinpgx build-labels` and the constraint snapshot is `gnomad constraint build` —
    #: which is exactly why it is a field: `cache status` used to compose `f"`{name} build`"` and so
    #: printed two commands that do not exist. A string a message interpolates has to come from where
    #: the command is declared, not from a naming convention two lanes do not follow.
    build_command: str | None
    resolve: Callable[..., Path | None]
    rebuild: RebuildAdapter | None
    ensure: Callable[..., Path] | None
    #: The repo **this tier** publishes to. Ensembl's snapshot is on HuggingFace and this field is
    #: still `None` for it, which is not the omission it looks like: just-dna-pipelines cuts and
    #: uploads that slice, so a publish command here would be this repository claiming another's
    #: artifact. Pullable-without-publishable is therefore a real state, and only for a lane whose
    #: `rebuild` is also `None`.
    publish_repo: str | None
    terms: SourceTerms | None
    #: Why there is no `ensure`/`publish_repo`. Stated iff there is none — the guard asserts the
    #: biconditional, because a lane that gained a publish command and kept its excuse would go on
    #: telling operators to build their own.
    unpublished: str | None = None
    #: Why there is no `rebuild` adapter. Ensembl is the only member, and its reason is that the
    #: snapshot is built by just-dna-pipelines rather than here.
    unbuilt: str | None = None


# ── the adapters ────────────────────────────────────────────────────────────────────────────────
#
# Each calls the same `download_*` and `build_*` the lane's own CLI command calls, so there is one
# conversion algorithm with two callers rather than two implementations that have to agree. What is
# duplicated is flag plumbing, which is the half that legitimately differs: `clinvar build` offers
# `--vcf` for a file you already have, and a rebuild pass by definition does not have one.


def _gate(terms: SourceTerms | None, declared_use: str, lane: str) -> RebuildOutcome | None:
    """The declared-use gate, run before any bytes are taken. `None` means proceed.

    A refusal and a skip are different outcomes and stay different: `commercial` against a no-sale
    source is a `False` (the operator asked for something the terms forbid), while `unstated` is a
    `None` (nobody has said, so nothing was taken and nothing failed).
    """
    if terms is None:
        return None
    try:
        reason = check_declared_use(terms, declared_use)
    except LicenseRefusal as exc:
        return RebuildOutcome(lane, False, f"refused: {exc}")
    if reason is not None:
        return RebuildOutcome(lane, None, f"skipped: {reason}")
    return None


def _rebuild_clinvar(request: RebuildRequest) -> RebuildOutcome:
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        vcf = request.source or clinvar_build.download_clinvar_vcf(
            request.out_dir / "clinvar.vcf.gz"
        )
        result = clinvar_build.build_snapshot(vcf, request.out_dir)
    except (FileNotFoundError, ImportError, OSError) as exc:
        return RebuildOutcome("clinvar", False, str(exc))
    return RebuildOutcome(
        "clinvar", True,
        f"{result.record_count} records over {len(result.chromosomes)} chromosomes, "
        f"clinvar_file_date {result.clinvar_file_date}",
        result.out_dir,
    )


def _rebuild_constraint(request: RebuildRequest) -> RebuildOutcome:
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        tsv = request.source or constraint_build.download_constraint_tsv(
            request.out_dir / "gnomad.v4.1.constraint_metrics.tsv"
        )
        result = constraint_build.build_snapshot(tsv, request.out_dir)
    except (FileNotFoundError, ImportError, OSError) as exc:
        return RebuildOutcome("constraint", False, str(exc))
    return RebuildOutcome(
        "constraint", True,
        f"{result.gene_count} genes from {result.source_rows} transcript rows", result.out_dir,
    )


def _rebuild_clinpgx(request: RebuildRequest) -> RebuildOutcome:
    refused = _gate(CLINPGX_TERMS, request.declared_use, "clinpgx")
    if refused is not None:
        return refused
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        sha: str | None = None
        archive = request.source
        if archive is None:
            archive, sha = clinpgx_build.download_clinpgx_zip(
                request.out_dir / clinpgx_build.CURRENT_ARCHIVE.archive
            )
        result = clinpgx_build.build_snapshot(
            archive, request.out_dir,
            source_url=clinpgx_build.DEFAULT_CLINPGX_URL, source_sha256=sha,
        )
    except (clinpgx_build.ClinPgxArchiveError, ImportError, OSError) as exc:
        return RebuildOutcome("clinpgx", False, str(exc))
    return RebuildOutcome(
        "clinpgx", True,
        f"{result.annotation_count} annotations over {len(result.genes)} genes, "
        f"release {result.created_date}",
        result.parquet_path.parent.parent,
    )


def _rebuild_cpic(request: RebuildRequest) -> RebuildOutcome:
    refused = _gate(CPIC_TERMS, request.declared_use, "cpic")
    if refused is not None:
        return refused
    try:
        result = cpic_build.build_snapshot(request.out_dir)
    except (cpic_build.CpicBuildError, ImportError, OSError) as exc:
        return RebuildOutcome("cpic", False, str(exc))
    return RebuildOutcome(
        "cpic", True, f"{result.total_rows} rows over {result.gene_count} genes", result.out_dir,
    )


def _rebuild_pharmvar(request: RebuildRequest) -> RebuildOutcome:
    refused = _gate(PHARMVAR_TERMS, request.declared_use, "pharmvar")
    if refused is not None:
        return refused
    # **The no-key case is decided before the request, not from the failure.** PharmVar has one flat
    # `PharmVarError` and its 401 is identical for an absent, a malformed and an unrecognised key, so
    # the exception cannot tell them apart and a caller reading the message would be parsing prose.
    # The distinction still matters: no key at all is the designed third state — the key is personal
    # and non-transferable, so a machine without one is a machine PharmVar never meant to serve —
    # while a configured key that then fails is asked-and-failed, and folding that into *not run*
    # would have a nightly rebuild stay quiet about a lane that broke (`@answered-is-not-absent`).
    if not os.environ.get(pharmvar.API_KEY_ENV):
        return RebuildOutcome(
            "pharmvar", None,
            f"no ${pharmvar.API_KEY_ENV} is set, and PharmVar's terms §2 make the key personal and "
            f"non-transferable — there is nothing to fall back to",
        )
    try:
        result = pharmvar_build.build_snapshot(request.out_dir)
    except (ImportError, OSError, pharmvar.PharmVarError) as exc:
        return RebuildOutcome("pharmvar", False, str(exc))
    return RebuildOutcome(
        "pharmvar", True,
        f"{result.allele_count} alleles over {result.gene_count} genes on {result.genome_build}",
        result.out_dir,
    )


def _rebuild_civic(request: RebuildRequest) -> RebuildOutcome:
    if request.pin is None:
        return RebuildOutcome(
            "civic", None,
            "needs a release date to pin (--pin civic=<YYYY-MM-DD>): CIViC publishes dated bulk "
            "files and a build from an unnamed one cannot be re-run",
        )
    if request.source is not None:
        return RebuildOutcome(
            "civic", None,
            "takes three input files (evidence, variants, profiles) and --source can name one, so "
            "a local build goes through `civic build` — two of the three is not a build",
        )
    request.out_dir.mkdir(parents=True, exist_ok=True)
    # **The three TSVs and no VCF, which is `civic build`'s own default.** RM169 made `--submitted`
    # opt-in because the release VCF *widens the status basis* — it admits submitted-but-not-accepted
    # evidence — so a rebuild that fetched it unconditionally would produce a different snapshot from
    # the same release than the per-lane command does. Two callers, one release, two artifacts is
    # exactly the fork this endpoint exists to prevent, and the wider basis is a curation decision
    # rather than a build option.
    names = (
        civic_build.CIVIC_EVIDENCE_FILE,
        civic_build.CIVIC_VARIANT_FILE,
        civic_build.CIVIC_PROFILE_FILE,
    )
    try:
        got = {
            name: civic_build.download_civic_file(
                request.out_dir / name, civic_build.civic_release_url(request.pin, name)
            )
            for name in names
        }
        result = civic_build.build_snapshot(
            got[names[0]].path, got[names[1]].path, got[names[2]].path, request.out_dir,
            release=request.pin,
            evidence_sha256=got[names[0]].sha256,
            variant_sha256=got[names[1]].sha256,
            profile_sha256=got[names[2]].sha256,
        )
    except (civic_build.CivicBuildError, ImportError, OSError) as exc:
        return RebuildOutcome("civic", False, str(exc))
    return RebuildOutcome(
        "civic", True,
        f"{result.record_count} rows over {result.variants} variants, dataset {result.dataset}, "
        f"status basis {result.status_basis}",
        result.parquet_file.parent.parent,
    )


def _rebuild_pubmind(request: RebuildRequest) -> RebuildOutcome:
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if request.source is not None:
            result = pubmind_build.build_snapshot(request.source, request.out_dir)
        else:
            fetched = pubmind_build.download_pubmind_table(
                request.out_dir / "hg38_pubmind_db.txt.gz"
            )
            result = pubmind_build.build_snapshot(
                fetched.path, request.out_dir,
                source_url=fetched.url, source_sha256=fetched.sha256,
                source_etag=fetched.etag, source_last_modified=fetched.last_modified,
            )
    except (pubmind_build.PubMindBuildError, ImportError, OSError) as exc:
        return RebuildOutcome("pubmind", False, str(exc))
    return RebuildOutcome(
        "pubmind", True,
        f"{result.record_count} of {result.input_rows} rows kept, dataset {result.dataset}",
        result.parquet_file.parent.parent,
    )


def _rebuild_mane(request: RebuildRequest) -> RebuildOutcome:
    if request.source is not None:
        return RebuildOutcome(
            "mane", None,
            "takes three input files (summary, changed accessions, negative roster) and --source "
            "can name one, so a local build goes through `mane build` — two of the three is not a "
            "snapshot",
        )
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        # No pin is fine here and is not the CIViC case: MANE publishes the version list itself, so
        # an unpinned build discovers the current release and then pins to its versioned directory.
        # The snapshot ends up naming a release either way, which is the property CIViC's cannot.
        pinned = request.pin or mane_build.discover_current_release()
        versions = mane_build.download_mane_file(
            request.out_dir / mane_build.MANE_VERSIONS_FILENAME, mane_build.mane_versions_url(pinned)
        )
        downloads = {
            table.name: mane_build.download_mane_file(
                request.out_dir / f"MANE.GRCh38.v{pinned}.{table.source_suffix}",
                mane_build.mane_release_url(pinned, table.source_suffix),
            )
            for table in mane_build.MANE_TABLES
        }
        result = mane_build.build_snapshot(
            {name: got.path for name, got in downloads.items()}, request.out_dir,
            versions_file=versions.path, release=pinned, downloads=downloads,
        )
    except (mane_build.ManeBuildError, FileNotFoundError, ImportError, OSError) as exc:
        return RebuildOutcome("mane", False, str(exc))
    return RebuildOutcome(
        "mane", True,
        f"dataset {result.dataset}, " + ", ".join(f"{n} {c}" for n, c in result.rows.items()),
        result.out_dir,
    )


def _rebuild_strchive(request: RebuildRequest) -> RebuildOutcome:
    try:
        result = strchive_build.build_strchive_snapshot(
            request.out_dir, catalogue=request.source, release=request.pin,
        )
    except (strchive_build.StrchiveError, OSError) as exc:
        return RebuildOutcome("strchive", False, str(exc))
    if result.dataset is None:
        # Built, and honestly unlabelled. Not a failure: the catalogue is usable, and the thing it
        # cannot do — name the release a comparison ran against — is stated rather than papered over.
        return RebuildOutcome(
            "strchive", True,
            f"{result.locus_count} loci from the default branch, unlabelled (pass --pin "
            f"strchive=<tag> for a snapshot that can name its release)",
            result.catalogue_file.parent,
        )
    return RebuildOutcome(
        "strchive", True, f"{result.locus_count} loci, dataset {result.dataset}",
        result.catalogue_file.parent,
    )


def _rebuild_drug_labels(request: RebuildRequest) -> RebuildOutcome:
    refused = _gate(CLINPGX_TERMS, request.declared_use, "drug_labels")
    if refused is not None:
        return refused
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        sha: str | None = None
        archive = request.source
        if archive is None:
            archive, sha = drug_labels_build.download_drug_labels_zip(
                request.out_dir / "drugLabels.zip", drug_labels_build.DEFAULT_DRUG_LABELS_URL
            )
        result = drug_labels_build.build_drug_label_snapshot(
            archive, request.out_dir,
            source_url=drug_labels_build.DEFAULT_DRUG_LABELS_URL, source_sha256=sha,
        )
    except (drug_labels_build.DrugLabelError, ImportError, OSError) as exc:
        return RebuildOutcome("drug_labels", False, str(exc))
    return RebuildOutcome(
        "drug_labels", True,
        f"{result.label_count} labels from {', '.join(result.regulators)}, "
        f"release {result.created_date or 'undated'}",
        result.out_dir,
    )


def _rebuild_acmg(request: RebuildRequest) -> RebuildOutcome:
    if request.source is None:
        return RebuildOutcome(
            "acmg", None,
            "needs the ACMG SF workbook (--source acmg=<file.xlsx>): it is Elsevier supplementary "
            "material, so the operator supplies their own copy and nothing is fetched here",
        )
    try:
        # `.resolve()` first: `Path("./x.xlsx").as_uri()` raises on a relative path, and a
        # relative path is what an operator types — `--source acmg=./acmg_sf_v3.3.xlsx` is the
        # documented invocation, so the documented one was the one that produced a traceback.
        workbook = request.source.resolve()
        sf_list = acmg_build.build_acmg_snapshot(
            workbook, request.out_dir, source_url=workbook.as_uri()
        )
    except (acmg_build.AcmgSfError, ImportError, OSError) as exc:
        return RebuildOutcome("acmg", False, str(exc))
    return RebuildOutcome(
        "acmg", True,
        f"SF v{sf_list.version}: {len(sf_list.genes)} genes over {len(sf_list.findings)} rows",
        request.out_dir,
    )


# ── the registry ────────────────────────────────────────────────────────────────────────────────
#
# A list rather than a dict, because the order is what `cache status` prints and a deployment reads
# it top to bottom: the four snapshots an ordinary enrich reaches first, then the licence-gated PGx
# block, then the operator-built references. `@deterministic-ordering` applies to a printed roster
# for the same reason it applies to parquet rows.

CACHE_LANES: list[CacheLane] = [
    CacheLane(
        name="ensembl",
        build_command=None,
        subdir=ENSEMBL_SUBDIR,
        serves="rsID → coordinate (enrich)",
        resolve=resolve_ensembl_reference,
        rebuild=None,
        ensure=ensure_snapshot,
        publish_repo=None,
        terms=None,
        unbuilt=(
            "built by just-dna-pipelines, not here: the slice is cut from Ensembl's variation dumps "
            "by that repository's pipeline, and this tier only consumes it"
        ),
    ),
    CacheLane(
        name="clinvar",
        build_command="clinvar build",
        subdir=CLINVAR_SUBDIR,
        serves="clinical records (enrich, draft-panel)",
        resolve=resolve_clinvar_reference,
        rebuild=_rebuild_clinvar,
        ensure=ensure_clinvar_snapshot,
        publish_repo=DEFAULT_CLINVAR_REPO_ID,
        terms=None,
    ),
    CacheLane(
        name="constraint",
        build_command="gnomad constraint build",
        subdir=CONSTRAINT_SUBDIR,
        serves="gnomAD v4.1 gene constraint (gene-metrics)",
        resolve=resolve_constraint_reference,
        rebuild=_rebuild_constraint,
        ensure=ensure_constraint_snapshot,
        publish_repo=DEFAULT_CONSTRAINT_REPO_ID,
        terms=None,
    ),
    CacheLane(
        name="clinpgx",
        build_command="clinpgx build",
        subdir=CLINPGX_SUBDIR,
        serves="clinical annotations (clinpgx check)",
        resolve=resolve_clinpgx_reference,
        rebuild=_rebuild_clinpgx,
        ensure=ensure_clinpgx_snapshot,
        publish_repo=DEFAULT_CLINPGX_REPO_ID,
        terms=CLINPGX_TERMS,
    ),
    CacheLane(
        name="cpic",
        build_command="cpic build",
        subdir=CPIC_SUBDIR,
        serves="alleles/diplotypes/recommendations (pgx, draft)",
        resolve=resolve_cpic_reference,
        rebuild=_rebuild_cpic,
        ensure=ensure_cpic_snapshot,
        publish_repo=DEFAULT_CPIC_REPO_ID,
        terms=CPIC_TERMS,
    ),
    CacheLane(
        name="drug_labels",
        build_command="clinpgx build-labels",
        subdir=DRUG_LABELS_SUBDIR,
        serves="regulator drug labels (clinpgx check-labels)",
        resolve=resolve_drug_labels_reference,
        rebuild=_rebuild_drug_labels,
        ensure=ensure_drug_labels_snapshot,
        publish_repo=DEFAULT_DRUG_LABELS_REPO_ID,
        terms=CLINPGX_TERMS,
    ),
    CacheLane(
        name="pharmvar",
        build_command="pharmvar build",
        subdir=PHARMVAR_SUBDIR,
        serves="star alleles (pgx)",
        resolve=resolve_pharmvar_reference,
        rebuild=_rebuild_pharmvar,
        ensure=None,
        publish_repo=None,
        terms=PHARMVAR_TERMS,
        unpublished=(
            "refused: the bulk data is pulled under a key PharmVar's terms §2 make personal and "
            "non-transferable, and no axis SourceTerms records covers passing that on. Build your "
            "own with `pharmvar build --out <dir>`"
        ),
    ),
    CacheLane(
        name="pubmind",
        build_command="pubmind build",
        subdir=PUBMIND_SUBDIR,
        serves="literature-derived verdicts (pubmind checks)",
        resolve=resolve_pubmind_reference,
        rebuild=_rebuild_pubmind,
        ensure=None,
        publish_repo=None,
        terms=None,
        unpublished=(
            "refused: the ANNOVAR-distributed table states no data terms at all, and an "
            "unestablished permission is not a permission. Build your own with `pubmind build`"
        ),
    ),
    CacheLane(
        name="civic",
        build_command="civic build",
        subdir=CIVIC_SUBDIR,
        serves="curated cancer interpretations (draft-panel --source civic)",
        resolve=resolve_civic_reference,
        rebuild=_rebuild_civic,
        ensure=ensure_civic_snapshot,
        publish_repo=DEFAULT_CIVIC_REPO_ID,
        terms=None,
    ),
    CacheLane(
        name="strchive",
        build_command="strchive build",
        subdir=STRCHIVE_SUBDIR,
        serves="repeat-locus bands (check-repeat-bands, draft-repeats)",
        resolve=resolve_strchive_reference,
        rebuild=_rebuild_strchive,
        ensure=ensure_strchive_snapshot,
        publish_repo=DEFAULT_STRCHIVE_REPO_ID,
        terms=None,
    ),
    CacheLane(
        name="mane",
        build_command="mane build",
        subdir=MANE_SUBDIR,
        serves="MANE transcripts, the numbering frame",
        resolve=resolve_mane_reference,
        rebuild=_rebuild_mane,
        ensure=None,
        publish_repo=None,
        terms=None,
        unpublished=(
            "unestablished: NCBI states a policy rather than a licence, so whether a snapshot of "
            "these bytes may be redistributed has never been answered — which is neither CIViC's "
            "grant nor PharmVar's refusal. Build your own with `mane build --download`"
        ),
    ),
    CacheLane(
        name="acmg",
        build_command="acmg build",
        subdir=ACMG_SUBDIR,
        serves="ACMG secondary findings (check-acmg)",
        resolve=resolve_acmg_reference,
        rebuild=_rebuild_acmg,
        ensure=None,
        publish_repo=None,
        terms=None,
        unpublished=(
            "unestablished: the SF v3.3 list is ACMG/Elsevier supplementary material and nothing "
            "grants redistribution of it. Build your own with `acmg build <workbook.xlsx>`"
        ),
    ),
]

#: Keyed access for the CLI's `--only`/`--pin`/`--source` flags, derived rather than restated.
LANES_BY_NAME: dict[str, CacheLane] = {lane.name: lane for lane in CACHE_LANES}


def rebuild_lane(lane: CacheLane, request: RebuildRequest) -> RebuildOutcome:
    """Run one lane's three stages, or say why it did not run.

    A lane with no adapter is a `None` outcome carrying `unbuilt` — Ensembl is the only one, and its
    snapshot is provisioned rather than rebuilt, so the honest answer to "rebuild everything" is that
    this one is somebody else's build.
    """
    if lane.rebuild is None:
        return RebuildOutcome(lane.name, None, lane.unbuilt or "no builder in this tier")
    logger.info("Rebuilding the %s snapshot into %s ...", lane.name, request.out_dir)
    return lane.rebuild(request)
