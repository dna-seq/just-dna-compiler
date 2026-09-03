"""The cache lanes as a registry, and the one endpoint that rebuilds them — RM176.

Every snapshot this tier knows about, all but one of them built here. Each is supposed to have three
stages: **acquire** (a download, a file the operator supplies, or — since RM171 — its parent lanes
being on disk), **build** (the conversion into the snapshot a check reads), and **publish** (the
upload a deployment then pulls with `cache pull`). Before this module the three stages existed as
eleven independent CLI commands and one hand-kept four-tuple list inside `cli.py`, and the gaps that
arrangement hid were all of the same kind: something true of a lane that no code anywhere asserted.

**The count is deliberately not stated here.** It was "twelve snapshots, eleven of them built here",
which is the counted-prose failure this workspace keeps re-learning: a sentence no test reads, true
on the day it was written and quietly wrong the first time the registry grew correctly
(`@counted-prose-needs-a-fixed-field`). `test_cache_lanes.py` asserts the equality that sentence was
gesturing at, over the walked set.

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
import pathlib
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
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
    mitomap,
    mitomap_build,
    mitomap_miss_build,
    pharmvar,
    pharmvar_build,
    pubmind_build,
    strchive_build,
)
from just_dna_enricher.clinvar import clinvar_dataset_label
from just_dna_enricher.download import (
    SnapshotNotPublished,
    ensure_civic_snapshot,
    ensure_clinpgx_snapshot,
    ensure_clinvar_snapshot,
    ensure_constraint_snapshot,
    ensure_cpic_snapshot,
    ensure_drug_labels_snapshot,
    ensure_mitomap_snapshot,
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
    ACMG_CACHE_VAR,
    ACMG_SUBDIR,
    CIVIC_CACHE_VAR,
    CIVIC_SUBDIR,
    CLINPGX_CACHE_VAR,
    CLINPGX_SUBDIR,
    CLINVAR_CACHE_VAR,
    CLINVAR_SUBDIR,
    CONSTRAINT_CACHE_VAR,
    CONSTRAINT_SUBDIR,
    CPIC_CACHE_VAR,
    CPIC_SUBDIR,
    DRUG_LABELS_CACHE_VAR,
    DRUG_LABELS_SUBDIR,
    ENSEMBL_CACHE_VAR,
    ENSEMBL_SUBDIR,
    MANE_CACHE_VAR,
    MANE_SUBDIR,
    MITOMAP_CACHE_VAR,
    MITOMAP_MISS_CACHE_VAR,
    MITOMAP_MISS_SUBDIR,
    MITOMAP_SUBDIR,
    PHARMVAR_CACHE_VAR,
    PHARMVAR_SUBDIR,
    PUBMIND_CACHE_VAR,
    PUBMIND_SUBDIR,
    STRCHIVE_CACHE_VAR,
    STRCHIVE_SUBDIR,
    default_acmg_cache_dir,
    default_civic_cache_dir,
    default_clinpgx_cache_dir,
    default_clinvar_cache_dir,
    default_constraint_cache_dir,
    default_cpic_cache_dir,
    default_drug_labels_cache_dir,
    default_ensembl_cache_dir,
    default_mane_cache_dir,
    default_mitomap_cache_dir,
    default_mitomap_miss_cache_dir,
    default_pharmvar_cache_dir,
    default_pubmind_cache_dir,
    default_strchive_cache_dir,
    load_env,
    missing_credential_reason,
    read_release,
    resolve_acmg_reference,
    resolve_civic_reference,
    resolve_clinpgx_reference,
    resolve_clinvar_reference,
    resolve_constraint_reference,
    resolve_cpic_reference,
    resolve_drug_labels_reference,
    resolve_ensembl_reference,
    resolve_mane_reference,
    resolve_mitomap_miss_reference,
    resolve_mitomap_reference,
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
    DEFAULT_MITOMAP_REPO_ID,
    DEFAULT_STRCHIVE_REPO_ID,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RebuildRequest:
    """What one lane's rebuild is given. The same fields for every lane, so the loop has no branches.

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

    `parents` is where each parent lane's snapshot is, for the one lane that has any (RM171). Filled
    by the caller rather than resolved inside the adapter, because a rebuild run has an answer the
    registry cannot give: `cache rebuild` writes every lane into `out/<lane>/`, so the ClinVar the
    miss lane should join against is the one *this run* just cut, not whatever is in the live cache.
    A parent the caller does not name falls back to that lane's own resolver, which is what
    `cache prepare` and a bare `--only mitomap_miss` want.
    """

    out_dir: Path
    declared_use: str = "unstated"
    pin: str | None = None
    source: Path | None = None
    parents: dict[str, Path] = field(default_factory=dict)


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


def _dataset_label(reference: Path) -> str | None:
    """Which release a snapshot on disk holds, as `release.json`'s own `dataset` states it.

    The default for every lane, and `None` when the snapshot does not say — never a placeholder, since
    a caller must be able to tell a release from a snapshot that cannot name one.
    """
    release = read_release(reference)
    return (release or {}).get("dataset") or None


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
    #: Where this lane's snapshot lives when nobody points anywhere — the directory `resolve`
    #: looks in last. `prepare` needs it because it *writes* there, which `resolve` cannot say:
    #: a resolver returns `None` for an absent cache and an absent cache is exactly the case
    #: provisioning is for.
    default_dir: Callable[..., Path]
    #: The environment variable that overrides where this lane's snapshot is looked for (S89) — the
    #: same constant `resolve` reads, so the field cannot name a variable the resolver ignores. Every
    #: lane has one; the shared `locations.CACHE_BASE_VAR` moves all of their defaults at once and is
    #: deliberately not a lane attribute. This is the one attribute of a lane that was still a string
    #: literal inside its resolver, so a consumer generating a `.env.template`, clearing its test
    #: environment, or auditing which caches were provisioned by variable was hand-keeping a list of
    #: fourteen names — the exact thing this registry exists to make unnecessary.
    env_var: str
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
    #: How this lane's snapshot names the release it holds (RM180). The default reads `release.json`'s
    #: `dataset`, which eleven lanes write; ClinVar does not, so `cache status` printed a blank label
    #: for the one lane that moves weekly while naming the release of every lane that does not.
    #:
    #: Named `release_label` and not `label` because `RebuildOutcome.label` next door is the
    #: built/failed/not-run word, and one file with two `label`s that mean different things is how a
    #: reader learns the wrong one first.
    #:
    #: A field rather than a `if lane.name == "clinvar"` in the reporter, for the reason
    #: `build_command` is one: a convention that holds for eleven of twelve is not a convention, and
    #: the exception belongs where the lane is declared. ClinVar's is `clinvar_dataset_label`, the
    #: function `clinvar_draft` writes onto its licence row and `clinical.tautology_reason` recomputes
    #: — shared rather than mirrored, because two spellings of one label do not fail, they simply
    #: never match.
    release_label: Callable[[Path], str | None] = _dataset_label
    #: The lanes this one is **derived from** (RM171). Empty for every lane that acquires its own
    #: bytes, which is all of them but `mitomap_miss`.
    #:
    #: A field rather than knowledge inside the adapter, because three things follow from it and only
    #: one is the adapter's: the rebuild guard below (a child whose parents are not on disk reports
    #: *could not run*, never an empty result and never a failure attributed to the parent), the
    #: registry ordering (`prepare` walks this list top to bottom, so a parent has to precede its
    #: child or the first provisioning run builds the child from caches that arrive a moment later),
    #: and `cache status`, where an operator asking why an increment is empty needs to be told what it
    #: is derived from.
    parents: tuple[str, ...] = ()


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
    """The VCF half **and** the citations half, because the published artifact carries both (RM179).

    This adapter built the VCF only, and `release.json` is written by that half — so every
    `cache rebuild clinvar --publish` uploaded a file describing one release over a repo whose
    `citations/citations.parquet` was still the previous one, and the block `build_citations` merges
    in to say so went with it. That is not hypothetical: on 2026-09-03 the published ClinVar snapshot
    held records from 2026-08-29 beside citations from 2026-06-27 and said nothing, because the
    2026-09-02 rebuild published a citations-free `release.json` over the one that had described the
    pair. The publisher adds and never deletes, so the sidecar survived its own description.

    Both halves or neither, and a failure in the second is a failed lane rather than a quieter
    success: what would otherwise be on disk is exactly the mixed-vintage artifact this exists to stop
    anyone publishing. `--source` stays the VCF's off-switch; the citations file is a separate ClinVar
    download and is fetched even then, which is the one thing this costs a fully offline rebuild.
    """
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        vcf = request.source or clinvar_build.download_clinvar_vcf(
            request.out_dir / "clinvar.vcf.gz"
        )
        result = clinvar_build.build_snapshot(vcf, request.out_dir)
    except (clinvar_build.ClinVarBuildError, FileNotFoundError, ImportError, OSError) as exc:
        return RebuildOutcome("clinvar", False, str(exc))
    try:
        citations_txt, citations_sha = clinvar_build.download_var_citations(
            request.out_dir / "var_citations.txt"
        )
        citations = clinvar_build.build_citations(
            citations_txt, request.out_dir, source_sha256=citations_sha
        )
    except (clinvar_build.ClinVarBuildError, FileNotFoundError, ImportError, OSError) as exc:
        return RebuildOutcome(
            "clinvar", False,
            f"the records built ({result.record_count} over {len(result.chromosomes)} "
            f"chromosomes) but the citations half did not: {exc}. The snapshot in "
            f"{request.out_dir} carries no citations table, so publishing it would describe one "
            f"release over a repo whose citations are another — build the pair again, or add the "
            f"sidecar with `clinvar citations`.",
            None,
        )
    return RebuildOutcome(
        "clinvar", True,
        f"{result.record_count} records over {len(result.chromosomes)} chromosomes, "
        f"clinvar_file_date {result.clinvar_file_date}, "
        f"{citations.row_count} citation links",
        result.out_dir,
    )


def _rebuild_constraint(request: RebuildRequest) -> RebuildOutcome:
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        tsv = request.source or constraint_build.download_constraint_tsv(
            request.out_dir / "gnomad.v4.1.constraint_metrics.tsv"
        )
        result = constraint_build.build_snapshot(tsv, request.out_dir)
    except (
        constraint_build.ConstraintBuildError, FileNotFoundError, ImportError, OSError,
    ) as exc:
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
    # `load_env()` first, at the point the credential is read (`@credential-where-read`).
    # `PharmVarClient.__init__` loads it before reading the same variable, so a key that lives only
    # in a `.env` — which is where this workspace's does — is visible to the *builder* and was
    # invisible to this guard. The lane then reported "no key" and never built, on the one machine
    # most likely to have one. A pre-check that answers differently from the code it is guarding is
    # worse than no pre-check.
    load_env()
    if not os.environ.get(pharmvar.API_KEY_ENV):
        return RebuildOutcome(
            "pharmvar", None,
            f"{missing_credential_reason(pharmvar.API_KEY_ENV)}. PharmVar's terms §2 make the key "
            f"personal and non-transferable, so there is nothing to fall back to",
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


#: Where a checkout keeps the ACMG SF workbook, and the pattern rather than a pinned filename: the
#: list is versioned (v3.2 → v3.3 in June 2025) and a constant naming one version would stop finding
#: the asset the day the next one lands, silently, in the direction that scrapes NCBI's stale page.
ACMG_WORKBOOK_GLOB = "acmg_sf_v*.xlsx"


def _checkout_assets() -> list[pathlib.Path]:
    """Every `assets/` directory this process can plausibly be running out of, nearest first.

    Two, because `cache rebuild` is run both ways: from the checkout root (walk up from the working
    directory, which is what an operator's shell is in) and through an editable workspace install
    from somewhere else (relative to this module). A non-editable install resolves the second to a
    path inside site-packages that does not exist, and falls through — which is correct rather than
    unlucky: **`assets/` is deliberately not in the wheel.** The workbook is ACMG/Elsevier
    supplementary material, and shipping it in a published package is the redistribution question the
    registry records as unestablished for this lane. A checkout may use its own copy; a `pip install`
    supplies its own.
    """
    here = pathlib.Path(__file__).resolve()
    candidates = [parent / "assets" for parent in pathlib.Path.cwd().resolve().parents]
    candidates.insert(0, pathlib.Path.cwd().resolve() / "assets")
    candidates.extend(parent / "assets" for parent in here.parents)
    seen: set[pathlib.Path] = set()
    out: list[pathlib.Path] = []
    for path in candidates:
        if path not in seen and path.is_dir():
            seen.add(path)
            out.append(path)
    return out


def _acmg_workbook_in_the_checkout() -> tuple[pathlib.Path | None, str | None]:
    """The checkout's workbook, or `None` and the reason there is not exactly one.

    **Never picks between two.** A directory holding `acmg_sf_v3.3.xlsx` and `acmg_sf_v3.4.xlsx` has
    two answers and no stated ordering between them — "the highest version" is an ordering somebody
    would have to define, and filename sort is not it. So several is reported like none, naming them,
    and the operator says which with `--source` (`@multiplicity-is-a-finding`).
    """
    for assets in _checkout_assets():
        found = sorted(assets.glob(ACMG_WORKBOOK_GLOB))
        if len(found) == 1:
            return found[0], None
        if found:
            return None, (
                f"{assets} holds {len(found)} ACMG workbooks ({', '.join(p.name for p in found)}) "
                f"and nothing orders them — name one with --source acmg=<file.xlsx>"
            )
    return None, None


def _rebuild_acmg(request: RebuildRequest) -> RebuildOutcome:
    source, ambiguous = (request.source, None)
    if source is None:
        source, ambiguous = _acmg_workbook_in_the_checkout()
    if source is None:
        return RebuildOutcome(
            "acmg", None,
            ambiguous or (
                "needs the ACMG SF workbook (--source acmg=<file.xlsx>): it is Elsevier "
                "supplementary material, so nothing fetches it. A checkout's own "
                f"assets/{ACMG_WORKBOOK_GLOB} is used when there is one and this is not a checkout"
            ),
        )
    request = RebuildRequest(
        out_dir=request.out_dir, declared_use=request.declared_use, pin=request.pin, source=source,
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
        f"SF v{sf_list.version}: {len(sf_list.genes)} genes over {len(sf_list.findings)} rows, "
        f"from {workbook.name}",
        request.out_dir,
    )


def _rebuild_mitomap(request: RebuildRequest) -> RebuildOutcome:
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if request.source is not None:
            # The off-switch: a dump the operator already holds, and the only route with no network.
            # It carries no `Last-Modified`, so the snapshot is honestly unlabelled rather than
            # labelled from an mtime — a file's modification time is a fact about this disk.
            result = mitomap_build.build_snapshot(request.source, request.out_dir)
        else:
            fetched = mitomap_build.download_mitomap_dump(
                request.out_dir / "mitomap.dump.sql.gz"
            )
            result = mitomap_build.build_snapshot(
                fetched.path, request.out_dir,
                source_url=fetched.url, source_sha256=fetched.sha256,
                source_last_modified=fetched.last_modified,
            )
    except (mitomap.MitomapError, ImportError, OSError) as exc:
        return RebuildOutcome("mitomap", False, str(exc))
    return RebuildOutcome(
        "mitomap", True,
        f"{', '.join(f'{name} {count}' for name, count in result.rows.items())}, "
        f"{result.citation_links} citation links, dataset {result.dataset or 'unlabelled'}",
        result.out_dir,
    )


def _rebuild_mitomap_miss(request: RebuildRequest) -> RebuildOutcome:
    """The derived lane. `rebuild_lane`'s parent guard has already run, so both are on disk here.

    That split is deliberate: the adapter never answers "the parents are missing", because that
    answer is the same for every derived lane and belongs where `lane.parents` is read. What is left
    here is the join itself.
    """
    request.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = mitomap_miss_build.build_miss_snapshot(
            request.parents["mitomap"], request.parents["clinvar"], request.out_dir,
        )
    except (mitomap.MitomapError, ImportError, OSError) as exc:
        return RebuildOutcome("mitomap_miss", False, str(exc))
    return RebuildOutcome(
        "mitomap_miss", True,
        ", ".join(f"{name} {count}" for name, count in result.buckets.items())
        + f" against {result.clinvar_keys} ClinVar chrMT alleles",
        result.out_dir,
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
        env_var=ENSEMBL_CACHE_VAR,
        serves="rsID → coordinate (enrich)",
        resolve=resolve_ensembl_reference,
        default_dir=default_ensembl_cache_dir,
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
        release_label=clinvar_dataset_label,
        subdir=CLINVAR_SUBDIR,
        env_var=CLINVAR_CACHE_VAR,
        serves="clinical records (enrich, draft-panel)",
        resolve=resolve_clinvar_reference,
        default_dir=default_clinvar_cache_dir,
        rebuild=_rebuild_clinvar,
        ensure=ensure_clinvar_snapshot,
        publish_repo=DEFAULT_CLINVAR_REPO_ID,
        terms=None,
    ),
    CacheLane(
        name="constraint",
        build_command="gnomad constraint build",
        subdir=CONSTRAINT_SUBDIR,
        env_var=CONSTRAINT_CACHE_VAR,
        serves="gnomAD v4.1 gene constraint (gene-metrics)",
        resolve=resolve_constraint_reference,
        default_dir=default_constraint_cache_dir,
        rebuild=_rebuild_constraint,
        ensure=ensure_constraint_snapshot,
        publish_repo=DEFAULT_CONSTRAINT_REPO_ID,
        terms=None,
    ),
    CacheLane(
        name="clinpgx",
        build_command="clinpgx build",
        subdir=CLINPGX_SUBDIR,
        env_var=CLINPGX_CACHE_VAR,
        serves="clinical annotations (clinpgx check)",
        resolve=resolve_clinpgx_reference,
        default_dir=default_clinpgx_cache_dir,
        rebuild=_rebuild_clinpgx,
        ensure=ensure_clinpgx_snapshot,
        publish_repo=DEFAULT_CLINPGX_REPO_ID,
        terms=CLINPGX_TERMS,
    ),
    CacheLane(
        name="cpic",
        build_command="cpic build",
        subdir=CPIC_SUBDIR,
        env_var=CPIC_CACHE_VAR,
        serves="alleles/diplotypes/recommendations (pgx, draft)",
        resolve=resolve_cpic_reference,
        default_dir=default_cpic_cache_dir,
        rebuild=_rebuild_cpic,
        ensure=ensure_cpic_snapshot,
        publish_repo=DEFAULT_CPIC_REPO_ID,
        terms=CPIC_TERMS,
    ),
    CacheLane(
        name="drug_labels",
        build_command="clinpgx build-labels",
        subdir=DRUG_LABELS_SUBDIR,
        env_var=DRUG_LABELS_CACHE_VAR,
        serves="regulator drug labels (clinpgx check-labels)",
        resolve=resolve_drug_labels_reference,
        default_dir=default_drug_labels_cache_dir,
        rebuild=_rebuild_drug_labels,
        ensure=ensure_drug_labels_snapshot,
        publish_repo=DEFAULT_DRUG_LABELS_REPO_ID,
        terms=CLINPGX_TERMS,
    ),
    CacheLane(
        name="pharmvar",
        build_command="pharmvar build",
        subdir=PHARMVAR_SUBDIR,
        env_var=PHARMVAR_CACHE_VAR,
        serves="star alleles (pgx)",
        resolve=resolve_pharmvar_reference,
        default_dir=default_pharmvar_cache_dir,
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
        env_var=PUBMIND_CACHE_VAR,
        serves="literature-derived verdicts (pubmind checks)",
        resolve=resolve_pubmind_reference,
        default_dir=default_pubmind_cache_dir,
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
        env_var=CIVIC_CACHE_VAR,
        serves="curated cancer interpretations (draft-panel --source civic)",
        resolve=resolve_civic_reference,
        default_dir=default_civic_cache_dir,
        rebuild=_rebuild_civic,
        ensure=ensure_civic_snapshot,
        publish_repo=DEFAULT_CIVIC_REPO_ID,
        terms=None,
    ),
    CacheLane(
        name="strchive",
        build_command="strchive build",
        subdir=STRCHIVE_SUBDIR,
        env_var=STRCHIVE_CACHE_VAR,
        serves="repeat-locus bands (check-repeat-bands, draft-repeats)",
        resolve=resolve_strchive_reference,
        default_dir=default_strchive_cache_dir,
        rebuild=_rebuild_strchive,
        ensure=ensure_strchive_snapshot,
        publish_repo=DEFAULT_STRCHIVE_REPO_ID,
        terms=None,
    ),
    CacheLane(
        name="mitomap",
        build_command="mitomap build",
        subdir=MITOMAP_SUBDIR,
        env_var=MITOMAP_CACHE_VAR,
        serves="curated mtDNA variants, the miss lane's parent (draft-panel --source mitomap-miss)",
        resolve=resolve_mitomap_reference,
        default_dir=default_mitomap_cache_dir,
        rebuild=_rebuild_mitomap,
        ensure=ensure_mitomap_snapshot,
        publish_repo=DEFAULT_MITOMAP_REPO_ID,
        # `terms=None` even though `MITOMAP_TERMS` exists, and the field is what decides it: this
        # column is the declared-use **gate**, not the licence. CC BY 3.0 states commercial and
        # clinical use free, so `check_declared_use` would answer `None` on every declaration and a
        # gate that cannot refuse is a gate nobody should have to read. ClinVar and STRchive have
        # terms constants and a `None` here for the same reason.
        terms=None,
    ),
    CacheLane(
        name="mitomap_miss",
        build_command="mitomap miss",
        subdir=MITOMAP_MISS_SUBDIR,
        env_var=MITOMAP_MISS_CACHE_VAR,
        serves="the MITOMAP-minus-ClinVar increment (draft-panel --source mitomap-miss)",
        resolve=resolve_mitomap_miss_reference,
        default_dir=default_mitomap_miss_cache_dir,
        rebuild=_rebuild_mitomap_miss,
        ensure=None,
        publish_repo=None,
        terms=None,
        # **A fourth reason, and it is neither a refusal nor an unestablished permission.** Both
        # parents are redistributable — ClinVar is public domain, MITOMAP is CC BY 3.0 — so nothing
        # in the licensing bars publishing this. What bars it is what the artifact *is*: its
        # `release.json` pins two parent digests, and a puller who holds neither parent cannot run
        # the currency check that pin exists for, so they would be handed an increment they cannot
        # tell from a stale one. Rebuilding it locally is seconds of work against caches the machine
        # already has, and it cannot be stale by construction.
        unpublished=(
            "derived, not downloaded: this snapshot is the join of the mitomap and clinvar caches "
            "and pins both their digests, so a pulled copy would carry a currency check its holder "
            "cannot run. Rebuild it from the parents with `mitomap miss` — the licences permit "
            "publishing it, the pin is what makes it pointless"
        ),
        parents=("mitomap", "clinvar"),
    ),
    CacheLane(
        name="mane",
        build_command="mane build",
        subdir=MANE_SUBDIR,
        env_var=MANE_CACHE_VAR,
        serves="MANE transcripts, the numbering frame",
        resolve=resolve_mane_reference,
        default_dir=default_mane_cache_dir,
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
        env_var=ACMG_CACHE_VAR,
        serves="ACMG secondary findings (check-acmg)",
        resolve=resolve_acmg_reference,
        default_dir=default_acmg_cache_dir,
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


def lane_name(spelling: str) -> str | None:
    """A lane name as the registry declares it, or `None` when nothing answers to that spelling.

    Accepts a hyphen where the declared member has an underscore and **returns the declared member**,
    never the caller's spelling — the rule every closed vocabulary in this workspace follows, and the
    reason it is a function is that a caller who merely *calls* a normalizer and keeps its own string
    has done nothing (`@vocab-separator-slip`). `drug_labels` and `mitomap_miss` are the two members
    it matters for: both are commonly written with a hyphen, and `mitomap-miss` is the spelling the
    design note and `draft-panel --source` use.
    """
    folded = spelling.strip().lower().replace("-", "_")
    return folded if folded in LANES_BY_NAME else None


def parent_snapshots(
    lane: CacheLane, request: RebuildRequest
) -> tuple[dict[str, Path], list[str]]:
    """Where each parent's snapshot is, and the parents that are not anywhere.

    The caller's `request.parents` wins, then the parent lane's own resolver. Both halves are needed
    and they answer different questions: a `cache rebuild` run has just cut a fresh ClinVar into
    `out/clinvar` and the child must join *that* one, while a lone `--only mitomap_miss` has no such
    run behind it and means the caches on this machine.
    """
    found: dict[str, Path] = {}
    missing: list[str] = []
    for name in lane.parents:
        supplied = request.parents.get(name)
        if supplied is not None and Path(supplied).is_dir():
            found[name] = Path(supplied)
            continue
        parent = LANES_BY_NAME.get(name)
        resolved = parent.resolve() if parent is not None else None
        if resolved is None:
            missing.append(name)
            continue
        found[name] = resolved
    return found, missing


def parents_from_rebuild_dir(lane: CacheLane, out: Path) -> dict[str, Path]:
    """A derived lane's parents as **this rebuild run** just cut them, under `out/<parent>/`.

    Two callers — `rebuild_caches` and the `cache rebuild` command — and one derivation, because the
    two producing different answers is precisely the fork that would give a child pinned to one
    ClinVar and sitting beside another. A parent this run did not build is left out and falls back to
    the registry's resolver inside `rebuild_lane`, which is the `--only <child>` case.
    """
    return {name: out / name for name in lane.parents if (out / name).is_dir()}


def rebuild_lane(lane: CacheLane, request: RebuildRequest) -> RebuildOutcome:
    """Run one lane's three stages, or say why it did not run.

    A lane with no adapter is a `None` outcome carrying `unbuilt` — Ensembl is the only one, and its
    snapshot is provisioned rather than rebuilt, so the honest answer to "rebuild everything" is that
    this one is somebody else's build.

    **A derived lane whose parents are not on disk is the third state too, and naming the parent is
    the whole point** (RM171). The two wrong answers are both available and both silent: an empty miss
    set reads as "MITOMAP publishes nothing ClinVar lacks", which is a claim about the world derived
    from a comparison that never ran, and a `False` would file the absence as this lane failing when
    what is absent belongs to another one. The guard is here rather than in the adapter because it is
    registry-driven — it is `lane.parents` that decides, so a second derived lane inherits it.
    """
    if lane.rebuild is None:
        return RebuildOutcome(lane.name, None, lane.unbuilt or "no builder in this tier")
    resolved: dict[str, Path] = {}
    if lane.parents:
        resolved, missing = parent_snapshots(lane, request)
        if missing:
            how = "; ".join(
                f"{name} (`{LANES_BY_NAME[name].build_command}`, or `cache pull --only {name}`)"
                if LANES_BY_NAME.get(name) is not None and LANES_BY_NAME[name].build_command
                else name
                for name in missing
            )
            return RebuildOutcome(
                lane.name, None,
                f"derived from {' and '.join(lane.parents)}; not on disk: {how}. A miss set computed "
                f"without a parent would be an increment measured against a comparison that never "
                f"ran, not an empty one",
            )
        request = RebuildRequest(
            out_dir=request.out_dir, declared_use=request.declared_use, pin=request.pin,
            source=request.source, parents=resolved,
        )
    logger.info("Rebuilding the %s snapshot into %s ...", lane.name, request.out_dir)
    return lane.rebuild(request)


@dataclass(frozen=True)
class PrepareOutcome:
    """One lane's provisioning result, and **which route answered** — not merely whether it worked.

    `ready` is the tri-state: `True` the snapshot is on disk and usable, `False` the attempt failed,
    `None` this lane offers no route on this machine and that is by design rather than an error.

    `route` is the half a caller cannot reconstruct from `ready`, and it is the whole point of the
    command: `present` (already there, nothing touched), `pulled` (downloaded from HuggingFace),
    `built` (built locally because nothing publishes it), `none`. A deployment auditing its own
    caches has to be able to tell a snapshot it *fetched* from one it *made* — they are different
    artifacts with different provenance, and `release.json` says which release but not which route.
    """

    lane: str
    ready: bool | None
    route: str
    detail: str
    path: Path | None = None

    @property
    def label(self) -> str:
        return {True: self.route, False: "FAILED", None: "unavailable"}[self.ready]


def prepare_lane(lane: CacheLane, request: RebuildRequest) -> PrepareOutcome:
    """Provision one lane by whichever route it has: pull it, or build it, or say why neither.

    **The route is a property of the lane, never a flag.** A lane with an `ensure` is published, so
    pulling is right and building would spend an operator's bandwidth re-deriving bytes somebody
    already made. A lane without one is unpublished *for a recorded reason* — PharmVar's personal
    key, PubMind's absent terms, NCBI's policy, ACMG's supplementary material — and building locally
    is the only route there will ever be. Asking the caller to choose would be asking them to restate
    the licensing story as a flag.

    **A present cache is left alone**, exactly as `cache pull` leaves one alone: provisioning is
    idempotent and cheap to re-run, and re-deriving a snapshot somebody is reading is how a resolver
    comes to see a half-written table. Re-cutting one is `cache rebuild`, which writes somewhere else
    on purpose.
    """
    existing = lane.resolve()
    if existing is not None:
        return PrepareOutcome(lane.name, True, "present", f"already provisioned at {existing}", existing)

    if lane.ensure is not None:
        if lane.terms is not None:
            # The terms are accepted when the data is TAKEN, and a download is taking it.
            try:
                reason = check_declared_use(lane.terms, request.declared_use)
            except LicenseRefusal as exc:
                return PrepareOutcome(lane.name, False, "pulled", f"refused: {exc}")
            if reason is not None:
                return PrepareOutcome(lane.name, None, "none", f"skipped: {reason}")
        try:
            path = lane.ensure()
        except Exception as exc:  # noqa: BLE001 - one lane failing must not sink the rest
            # Not an error here either, and for a sharper reason than in `cache pull`: this command's
            # job is to leave the machine with a usable cache, and a repo nobody has created yet is a
            # fact about the world that no amount of retrying changes. Caught by TYPE — the name is
            # not the contract, and a string compare here would survive a rename that broke it
            # (`@client-exception-contract`).
            if isinstance(exc, SnapshotNotPublished):
                return PrepareOutcome(lane.name, None, "none", f"nothing published yet: {exc}")
            return PrepareOutcome(lane.name, False, "pulled", str(exc))
        return PrepareOutcome(lane.name, True, "pulled", f"downloaded to {path}", path)

    if lane.rebuild is None:
        return PrepareOutcome(lane.name, None, "none", lane.unbuilt or "no route in this tier")

    # Built locally, because nothing publishes it. Into a staging directory beside the target and
    # moved across only once the build has finished: the resolvers read the target by globbing, so a
    # build writing straight into it would be visible half-done, and a short parquet still has a
    # footer. The target is absent here (checked above), so the move is a plain rename.
    target = lane.default_dir()
    staging = target.parent / f"{target.name}.incoming"
    if staging.exists():
        shutil.rmtree(staging)
    outcome = rebuild_lane(lane, RebuildRequest(
        out_dir=staging, declared_use=request.declared_use, pin=request.pin, source=request.source,
        parents=request.parents,
    ))
    if outcome.built is not True:
        shutil.rmtree(staging, ignore_errors=True)
        return PrepareOutcome(
            lane.name, outcome.built, "built" if outcome.built is False else "none", outcome.detail,
        )
    if not staging.is_dir():
        # A builder that reports success and writes nothing. Not reachable through today's adapters,
        # and guarded anyway because the alternative is a raw `FileNotFoundError` out of `replace()`
        # naming a staging path the operator has never heard of — a generic rejection where a
        # specific one is a fix (`@specific-rejection`). It also keeps the contract on the visible
        # side: `built is True` means a snapshot exists, and this is where that is established.
        return PrepareOutcome(
            lane.name, False, "built",
            f"the {lane.name} builder reported success but wrote nothing to {staging}",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(target)
    return PrepareOutcome(lane.name, True, "built", f"{outcome.detail} → {target}", target)


def prepare_caches(
    lanes: list[CacheLane] | None = None,
    *,
    declared_use: str = "unstated",
    pins: dict[str, str] | None = None,
    sources: dict[str, Path] | None = None,
) -> list[PrepareOutcome]:
    """Provision every cache by its own route — the Python half of `cache prepare`.

    The counterpart to `rebuild_caches`, and a real API rather than a loop the CLI happens to own: a
    deployment's own provisioning step is Python far more often than it is a shell script, and the
    alternative is every caller re-deriving *which lane pulls and which builds* from the licensing
    story. That derivation is the command.
    """
    pins = pins or {}
    sources = sources or {}
    outcomes = []
    for lane in lanes if lanes is not None else CACHE_LANES:
        outcomes.append(prepare_lane(lane, RebuildRequest(
            out_dir=lane.default_dir(),
            declared_use=declared_use,
            pin=pins.get(lane.name),
            source=sources.get(lane.name),
        )))
    return outcomes


def rebuild_caches(
    lanes: list[CacheLane] | None = None,
    *,
    out: Path,
    declared_use: str = "unstated",
    pins: dict[str, str] | None = None,
    sources: dict[str, Path] | None = None,
) -> list[RebuildOutcome]:
    """Rebuild every lane into `out/<lane>/` — the Python half of `cache rebuild`.

    Separate from `prepare_caches` because the two answer different questions and a flag joining them
    would hide that. **Rebuild re-derives**, into a directory nothing is reading, so a deployment can
    cut a new set and adopt it deliberately. **Prepare provisions**, into the live cache locations,
    and leaves a lane that already has a snapshot alone. A caller wanting "make sure every cache
    exists" wants prepare; one wanting "cut a fresh set from today's sources" wants rebuild.
    """
    pins = pins or {}
    sources = sources or {}
    # **A derived lane joins the snapshots THIS run cut, where this run cut them** (RM171). Every lane
    # is written into `out/<lane>/`, so by the time the child's turn comes its parents are siblings on
    # disk — and joining the live cache instead would produce a child whose `release.json` pins two
    # parents that are not the ones beside it.
    return [
        rebuild_lane(lane, RebuildRequest(
            out_dir=out / lane.name,
            declared_use=declared_use,
            pin=pins.get(lane.name),
            source=sources.get(lane.name),
            parents=parents_from_rebuild_dir(lane, out),
        ))
        for lane in (lanes if lanes is not None else CACHE_LANES)
    ]
