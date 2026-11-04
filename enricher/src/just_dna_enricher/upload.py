"""HuggingFace upload — publisher surface of the network tier.

Two publish shapes share one create-or-update pathway (``ensure_repo``):

* **module** — a compiled module's ``manifest.json`` and **every file it declares** (the attested
  parquets, the logo, the readme, ``provenance.json`` and each log; RM347, RM353) to
  ``datasets/<repo>/data/<name>/``, matching the layout
  just-dna-lite's discovery scans, **and** to ``data/<name>/v<version>/`` when the manifest states a
  version, so the discovery path can address a particular release rather than only "whatever is there
  now" (``upload_module``; RM84).
* **reference snapshot** — a built ClinVar (or Ensembl) parquet snapshot + ``release.json`` to the
  root of a dataset repo, matching the ``download.ensure_*_snapshot`` layout
  (``publish_reference_snapshot``).

Both require a HuggingFace token with write access (``hf auth login`` or ``HF_TOKEN``). This is the
**dev/publisher** half of the enricher's HuggingFace use: snapshot *download* is a runtime enrich
path (``download.ensure_snapshot``); *upload* is for authors republishing modules (e.g. the Gen-I
``v1-port`` recreation) or publishing a rebuilt reference. Install as ``just-dna-enricher[dev]``.

Extracted from ``just_dna_pipelines.v1_port.publish`` (just-dna-lite); ``create_repo`` was added here
(the origin assumed the repo pre-existed) so a brand-new dataset repo can be created on first push.
"""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatch, fnmatchcase
from glob import escape as glob_escape
from pathlib import Path, PurePosixPath
from typing import Any

from just_dna_compiler.compiler import ARTIFACT_PARQUETS, LEAD_PARQUETS
from just_dna_format.identity import is_valid_version
from just_dna_format.integrity import sha256_bytes, sha256_file
from just_dna_format.manifest import (
    LOGO_EXTENSIONS,
    README_CANDIDATES,
    TOOLCHAIN_DIFFERS,
    recorded_toolchain,
    toolchains_differ,
)
from pydantic import BaseModel, Field

from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_ROOT_FILENAMES,
    SNAPSHOT_SIDECAR_DIRNAMES,
    env_value,
    missing_credential_reason,
)

# Named once because two things now have to agree about it: the allowlist that uploads the file, and
# the reader below that takes the module's version out of it.
_MANIFEST_FILENAME = "manifest.json"
# **A manifest field whose bytes nobody uploads is a field that does not travel** — the same gap as
# ClinVar's `citations/` and the ClinPGx `LICENSE.txt` below, and the reason `manifest.readme` (S25) is
# named here in the same commit that adds it. The candidate list is imported rather than spelled out:
# the compiler discovers a readme from `README_CANDIDATES` and this publisher must accept exactly the
# set the compiler can produce, or an author who wrote `README.rst` publishes a manifest attesting a
# file the repo does not carry. **The logo half is derived the same way (RM105).** It was the hand-
# spelled pair `logo.png`/`logo.jpg` while `manifest.LOGO_EXTENSIONS` is `{png, jpg, jpeg}` and
# `_collect_logo` picks the first in `sorted()` order — so `jpeg` wins, and a spec dir holding one
# shipped a manifest attesting bytes the published repo did not carry. `verify_manifest(check_logo=True)`
# does not catch it either: an absent file is not a failure there.
#
# **The parquet half is derived from the compiler's own list, never restated here (S35, RM89).** It
# used to be the hand-kept triple `weights`/`annotations`/`studies`, written when a module *meant* a
# SNP core; RM2 made the SNP core optional four releases ago and the constant stayed. Measured on
# 2026-08-17 against the sixteen reference examples: seven could not be published at all and eight
# published an artifact whose `manifest.artifact.files` attests, by name and sha256, six kinds of
# parquet this allowlist dropped — so the digest a consumer recomputes over what arrived cannot match
# the digest the manifest states. `sources.parquet` is the worst of them, because the licence terms and
# attribution a downstream report is obliged to render are in it.
#
# **Since RM353 this list is the fallback, not the plan.** A module whose manifest states its
# `artifact.files` is published as exactly what that manifest declares (`_declared_files`), which is
# how `provenance.json` — named and hashed in `manifest.provenance` and in no list here — came to
# travel. The list below answers only when the manifest cannot say, because a directory without a
# readable manifest has always been publishable.
_ALLOW_PATTERNS = [
    *ARTIFACT_PARQUETS,
    _MANIFEST_FILENAME,
    *(f"logo.{ext}" for ext in sorted(LOGO_EXTENSIONS)),
    *README_CANDIDATES,
]
# `weights.parquet` is the one lead table the compiler never emits alone: a SNP core always produces
# all three, so either of the others missing beside it is an interrupted compile rather than a module
# shape. Scoped to the weights-led case deliberately — a `pharm_variants`-led module legitimately has
# neither, which is what made the old blanket rule refuse seven of sixteen.
_EXPECTED_WITH_WEIGHTS = ("annotations.parquet", "studies.parquet")
# A reference snapshot is `data/*.parquet` + its optional parquet sidecars + `release.json` — the
# `ensure_*_snapshot` layout, defined once in `locations` so the publisher and the provisioner cannot
# disagree about it. **The sidecars were the gap this closes:** ClinVar's `citations/` was built and
# never published, so anyone who *downloaded* the snapshot instead of building it had no PMIDs — and a
# drafted gene panel cannot compile without them, because `studies.csv` is mandatory.
#
# **`LICENSE.txt` was the second gap, and it is worse than the sidecars were.** ClinPGx ships its terms
# *inside* the archive the data came from, and the builder extracts them precisely so a holder of the
# snapshot can read what governs the bytes without going back to the archive — the whole pinned-licence
# design (`license_sha256`) rests on that file travelling with them. It was not in these patterns, so
# publishing a share-alike snapshot dropped it silently. Absent is normal (only ClinPGx has one).
#
# **These patterns are no longer a constant, and that is the third repair in the same family.** The
# list and `plan_reference_snapshot`'s file list were two statements of one thing, so `--dry-run`
# could promise a file the upload then dropped — which is exactly how the two gaps above went
# unnoticed for a release each. `publish_reference_snapshot` now derives the allowlist from the plan
# it just computed, so there is one list and a dry run is a promise (`@publisher-allowlist-derived`).

logger = logging.getLogger(__name__)

DEFAULT_REPO_ID = "just-dna-seq/annotators"
DEFAULT_CLINVAR_REPO_ID = "just-dna-seq/clinvar"
DEFAULT_CONSTRAINT_REPO_ID = "just-dna-seq/gnomad_constraint"
# The two licence-gated snapshots that may be published (RM38): both record `redistribution=True`, and
# CC BY-SA grants sharing under share-alike plus attribution. **PharmVar has no entry here on purpose** —
# its bulk data is pulled under a personal, non-transferable key and no recorded axis covers passing
# that on, so an unestablished permission stays a refusal.
DEFAULT_CLINPGX_REPO_ID = "just-dna-seq/clinpgx"
DEFAULT_CPIC_REPO_ID = "just-dna-seq/cpic"
#: CIViC's snapshot repo (RM152/RM153). CC0 content, so unlike PubMind's there is nothing to refuse
#: and unlike PharmVar's nothing to withhold — the only reason none exists yet is that nobody has run
#: the command.
DEFAULT_CIVIC_REPO_ID = "just-dna-seq/civic"
#: STRchive's snapshot repo (RM176). MIT, so redistribution is granted outright — the reason there was
#: no publish command is that this lane grew from a check rather than from a cache, not that anything
#: barred one. Its snapshot holds no parquet, which is why `plan_reference_snapshot` had to learn about
#: a payload before this constant could mean anything.
DEFAULT_STRCHIVE_REPO_ID = "just-dna-seq/strchive"
#: The regulator drug labels — a **second** ClinPGx archive, and so a second repo rather than a table
#: inside `clinpgx/`. The two downloads do not refresh in lockstep and each is dated from its own
#: `CREATED_*.txt`, so one repo holding both would date the pair from whichever was published last.
#: Same CC BY-SA terms as the annotation lane, hence the same grounds and the same `LICENSE.txt`.
DEFAULT_DRUG_LABELS_REPO_ID = "just-dna-seq/clinpgx_drug_labels"
#: MITOMAP's curated mtDNA variant tables, cut from the source's published `pg_dump` (RM171). CC BY
#: 3.0 with commercial and clinical use stated free, so redistribution is granted outright and the
#: attribution duty travels in the snapshot's own `SourceRow`. The **derived** miss lane has no repo
#: on purpose: it pins the digests of two parents, and a puller who does not hold those parents would
#: be handed an increment its own currency check cannot verify.
DEFAULT_MITOMAP_REPO_ID = "just-dna-seq/mitomap"

#: AlphaGenome AVI (RM198). Publishable on a **recorded reading** rather than a quoted clause: RM195
#: pinned the page that makes AVI Permissive Use, and `redistribution=True` carries the maintainer's
#: reading that an open publication falls inside prohibition 1's "open source release" carve-out.
#: What makes that defensible in practice is that the snapshot carries the Use restrictions as
#: `LICENSE.txt`, so a puller receives the terms with the bytes.
DEFAULT_ALPHAGENOME_AVI_REPO_ID = "just-dna-seq/alphagenome_avi"

#: ClinVar-GKM's indel witness (RM305). CC0 over ClinGen's transformation of public-domain ClinVar, so
#: redistribution is granted; ClinVar's attribution and disclaimer travel as the snapshot's `LICENSE.txt`.
DEFAULT_CLINVAR_GKM_REPO_ID = "just-dna-seq/clinvar_gkm"


def _hf_api(repo_id: str, token: str | None = None):
    """Resolve a write token and return an authenticated ``HfApi``.

    **`HF_TOKEN` is read from the `.env` too, because it is a credential like any other.** `get_token()`
    reads the real environment and `~/.cache/huggingface/token`, and neither is a `.env` — so a
    workspace that keeps its token there, as this one does, got *"No HuggingFace token found"* from a
    publish while every other credential path in the tier read the same file without being asked. It is
    read where it is used (`@credential-where-read`) through `env_value`, so an exported variable still
    wins and nothing else in the file is exported (RM301).

    Raises PermissionError if no token is available and ImportError if huggingface_hub is absent
    (a guarded lazy import, so a download-only install that somehow lacks the wheel fails clearly).
    """
    try:
        from huggingface_hub import HfApi, get_token
    except ImportError as exc:
        raise ImportError(
            "huggingface_hub is required to publish to HuggingFace; install just-dna-enricher "
            "(or just-dna-enricher[dev] for the publisher surface)"
        ) from exc
    resolved_token = token or env_value("HF_TOKEN") or get_token()
    if not resolved_token:
        raise PermissionError(
            f"No HuggingFace token found: {missing_credential_reason('HF_TOKEN')}. Or authenticate "
            f"with `hf auth login`. Whichever route, it needs write access to {repo_id}."
        )
    return HfApi(token=resolved_token)


def ensure_repo(repo_id: str, token: str | None = None):
    """Create-or-update: ensure the dataset repo exists, returning the authenticated ``HfApi``.

    ``create_repo(..., exist_ok=True)`` is a no-op when the repo already exists, so create and update
    are one pathway. The returned api is reused by the caller's ``upload_folder`` so only one
    ``HfApi`` is constructed per publish.
    """
    api = _hf_api(repo_id, token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
    return api


@dataclass(frozen=True)
class LayoutShift:
    """A retirement declared by the commit that causes it, so the publish carries out the migration.

    **The rule (maintainer, 2026-09-03).** A change that retires one published file and introduces
    another must also carry a *conditioned* update to the publication procedure: if the new file is
    absent from the repo and the old one is present, upload the new and delete the old. The condition
    is a predicate over the **remote**, so it fires exactly once per repo and is a no-op forever after
    — nothing is deleted on a repo that has already moved, and re-running a publish cannot re-delete.

    This is the *only* deletion a publish performs. General cleanup is `cache prune`, which prints
    what it would remove and asks; a deletion nobody declared is not a side effect a publish may have.
    What makes this one safe is not that it is small but that it is *named*: the pair is in the commit
    that changed the layout, where a reviewer sees both halves at once.

    Deleting is recoverable in a way this repository's `@snapshot-accumulates` note did not credit —
    a HuggingFace dataset repo is git-backed, and a superseded revision still resolves (three of them
    were read off the hub while auditing this on 2026-09-03). The reason to declare rather than sweep
    is not that bytes are lost; it is that a retired file goes on answering 200 to whoever still asks
    for it, which is how a lane's default archive stayed frozen for a year (`CLINPGX_ARCHIVES`).
    """

    #: The repo this is about. Keyed on the repo rather than on the lane name, because the publisher
    #: is handed a `repo_id` and knows nothing about lanes — a lane→repo map here would be a second
    #: copy of `CacheLane.publish_repo`, and `caches` already imports this module, so it cannot be
    #: imported back.
    repo_id: str
    #: Repo-relative path of the file being retired. One name, never a glob: a migration that deletes
    #: a *pattern* is a prune wearing a declaration.
    retires: str
    #: A repo-relative glob the new layout writes. The migration fires only when the remote has none
    #: of these — that absence is what makes "this repo has not moved yet" a fact rather than a guess.
    introduces: str
    #: Why, in one line, for the operator who sees the deletion in a commit message.
    reason: str


#: Every declared shift, oldest first. Empty is the normal state: an entry is written by the change
#: that retires a file and stays afterwards, because a repo re-created or cloned later is exactly the
#: state it exists for.
#:
#: **The known one is already past its own condition, and it stays literal rather than widened.**
#: `just-dna-seq/clinvar` carries the single-file-era `data/clinvar.parquet` *and* today's
#: `data/clinvar-chr*.parquet`, because the publish that introduced the per-chromosome layout predated
#: this rule — so this entry will not fire against that repo, and the 159 MB remnant is `cache prune`'s
#: to remove. Loosening the predicate to "retire the old whenever the new is present" would sweep it,
#: and would also make every publish a prune until the file is gone, which is the thing deletion-by-
#: declaration exists not to be.
LAYOUT_SHIFTS: tuple[LayoutShift, ...] = (
    LayoutShift(
        repo_id=DEFAULT_CLINVAR_REPO_ID,
        retires="data/clinvar.parquet",
        introduces="data/clinvar-chr*.parquet",
        reason=(
            "the single-file snapshot was replaced by one parquet per chromosome; the flat file's "
            "columns are the raw VCF INFO fields, so a reader globbing data/*.parquet gets two "
            "schemas under one relation"
        ),
    ),
)


def layout_shifts_to_apply(repo_files: Iterable[str], repo_id: str) -> list[LayoutShift]:
    """The declared shifts whose condition the remote currently satisfies. Reads; decides nothing else.

    Separate from the publish so it can be asserted directly: the whole safety of this mechanism is
    that the predicate is false the moment it has run once, and that is a property of this function
    rather than of the caller that acts on it.
    """
    remote = list(repo_files)
    due: list[LayoutShift] = []
    for shift in LAYOUT_SHIFTS:
        if shift.repo_id != repo_id:
            continue
        if shift.retires not in remote:
            continue  # already retired, or never there
        if any(fnmatch(name, shift.introduces) for name in remote):
            continue  # the repo has already moved: not this one's job
        due.append(shift)
    return due


class PublishRefused(Exception):
    """A publish refused on what it would send — the publisher's one error family (RM368).

    Every refusal this module raises is a subclass, so a caller catches the family once and tells the
    members apart by type: the local module or snapshot is not publishable (`ModuleNotPublishable`,
    `SnapshotNotPublishable`), a planned file changed before it was sent (`PlanChangedError`), the
    remote already holds something else (`PublishCollisionError`, `ToolchainDiffersError`,
    `OrphanedSidecarError`). Two things stay outside it because they say nothing about what would be
    sent: a missing write token (`PermissionError`) and a missing `huggingface_hub` (`ImportError`).

    **A base class, so a caller's `except` order is load-bearing** (`@client-exception-contract`): a
    handler for a member goes before the handler for the family, as the CLI's do.
    """


class ModuleNotPublishable(PublishRefused, FileNotFoundError):
    """The module directory is not publishable as it stands (`plan_upload`'s refusals, RM368).

    It used to be a bare `FileNotFoundError`, which a caller could not tell from a missing directory.
    **It is still one within 0.8** — a second base kept so an existing `except FileNotFoundError`
    keeps catching it; catch `PublishRefused` or this type instead.
    """


class SnapshotNotPublishable(PublishRefused, FileNotFoundError):
    """The snapshot directory has nothing built to publish (`plan_reference_snapshot`, RM368).

    Still a `FileNotFoundError` within 0.8, for the reason `ModuleNotPublishable` is.
    """


class PlanChangedError(PublishRefused):
    """A planned file's bytes are not the ones the plan read and checked (RM368).

    The send reads each planned file once more and sends exactly the bytes it hashed; a file whose hash
    is not the plan's (a recompile landing between the check and the send, an edit) or that cannot be
    read any more refuses the publish before anything is committed.
    """


class OrphanedSidecarError(PublishRefused, RuntimeError):
    """The publish would overwrite a `release.json` describing sidecars it is not carrying (RM185).

    Its own type for the reason `PublishCollisionError` is one: the CLI has to tell it from the
    refusals `plan_*` raises. Those say the local snapshot is not publishable; this one says the local
    snapshot is fine and the *remote* holds bytes this publish would silently stop describing.

    **The incident.** A ClinVar snapshot is two halves on two cadences — the per-chromosome parquet and
    `citations/citations.parquet` — and `release.json` describes both because `build_citations` merges
    a block into it. A rebuild that built only the VCF half published a citations-free `release.json`
    over a repo whose sidecar it had not replaced, and the publisher adds without deleting: the
    sidecar outlived its own description, and the published artifact carried records from one ClinVar
    release beside citations from another while saying nothing. RM179 fixed the lane; this is the
    general shape, refused at the boundary where any lane could repeat it.
    """


class PublishCollisionError(PublishRefused, RuntimeError):
    """The versioned path already holds a *different* release, and no `--force` was given (RM88).

    Its own type rather than a `ModuleNotPublishable`, because the CLI has to tell it apart from the
    refusals `plan_upload` raises: those say the local module is not publishable, this one says the
    local module is fine and the remote already has that version.

    `reason` is `None` on the plain collision — nothing recorded says why the bytes differ — and a
    subclass sets it when something does (`ToolchainDiffersError`).
    """

    reason: str | None = None


class ToolchainDiffersError(PublishCollisionError):
    """The plain collision's one explained case: the two manifests recorded different toolchains (RM342).

    From polars 2 the parquet footer names the polars release that wrote it, so an unchanged spec
    recompiled beside another polars mints another digest. That is not corruption, and the maintainer's
    decision (2026-11-04) is that it is never reported as the plain mismatch. The publish still
    refuses unless `--force`: the versioned path's bytes stay the ones that version was cut as
    (Principle 4), and the reason changes what the refusal says, not whether it refuses.

    **A subclass, so every handler of `PublishCollisionError` still refuses.** A sibling type would
    turn a handled refusal into an uncaught one in any caller that catches only the collision; the
    cost is that a caller wanting the distinction must catch this type first
    (`@client-exception-contract`), which the CLI does. Tell the two apart by type or by `reason`,
    never by the message.

    **The reason names a co-occurring difference, not a proven cause.** A content edit recompiled under
    another polars raises this too, which is why `content_unchanged` rides beside it: `True` when both
    manifests carry one `content_signature` (the toolchain alone can account for the digest), `False`
    when the content moved as well, `None` when either side states none.
    """

    reason: str | None = TOOLCHAIN_DIFFERS

    def __init__(
        self,
        message: str,
        *,
        published_toolchain: dict[str, str],
        local_toolchain: dict[str, str],
        content_unchanged: bool | None,
    ) -> None:
        super().__init__(message)
        self.published_toolchain = published_toolchain
        self.local_toolchain = local_toolchain
        self.content_unchanged = content_unchanged


class UploadPlan(BaseModel):
    """What an upload would send (also the dry-run result)."""

    module: str = Field(description="Module directory name under the collection")
    repo_id: str = Field(description="Target HuggingFace dataset repo (owner/name)")
    path_in_repo: str = Field(description="Path inside the dataset repo (data/<module>)")
    versioned_path_in_repo: str | None = Field(
        default=None,
        description="Second path, data/<module>/v<version>, or null when no version could be read",
    )
    version_unknown_reason: str | None = Field(
        default=None,
        description="Why no versioned path is planned; null when the version was read",
    )
    files: list[str] = Field(
        description=(
            "Paths, relative to the module directory, that will be uploaded: the attested artifact "
            "files, manifest.json, then the logo, readme, provenance document and each log the "
            "manifest declares (e.g. logs/authoring.log)"
        )
    )
    sha256: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Each planned file's sha256 as the plan read it, manifest.json included. The upload sends "
            "exactly these bytes and refuses a file whose bytes no longer hash to its entry (RM368)"
        ),
    )


#: The `ModuleManifest` fields that declare a file in the module directory, which the publisher sends,
#: hashes and guards (RM353, RM368). Four are `FileEntry`-shaped; `provenance` is a summary carrying
#: `file` and `sha256`. `test_the_publisher_reads_every_field_that_names_a_file` asserts that these and
#: `SPEC_SIDE_FILE_FIELDS` are exactly the fields that reach a `FileEntry` or a `Provenance`.
DECLARED_FILE_FIELDS: tuple[str, ...] = ("artifact", "logo", "readme", "provenance", "logs")
#: Fields that name a file the publisher does not send, each with the reason.
SPEC_SIDE_FILE_FIELDS: dict[str, str] = {
    "inputs": "the authored inputs sit beside the spec, and a compile does not copy them into the module",
    "derived": "the derived sidecars sit beside the spec, and a compile does not copy them into the module",
}


@dataclass(frozen=True)
class _ManifestRead:
    """One read of `manifest.json`: the parsed object, why there is none, and the hash of the bytes."""

    document: dict | None
    unread_reason: str | None
    sha256: str | None


def _manifest_document(module_dir: Path) -> _ManifestRead:
    """The compiled ``manifest.json`` as a plain JSON object, why there is none, and its bytes' hash.

    **The one reader of the manifest (RM355).** Every helper below reads fields out of the object this
    returns, and every entry point — the plan, the publish and the publish's guard — calls it once and
    hands the object on, so the version a plan states and the files it lists come from one read of
    one file. **The hash is of the same bytes the object was parsed from (RM368)**, so the plan's
    `sha256["manifest.json"]` is the manifest the guard checked, and the send can tell when the file on
    disk is no longer that one.

    At most one of ``document`` and ``unread_reason`` is set. The reason is the one
    ``version_unknown_reason`` reports when the document cannot be read, which is why it is returned
    rather than collapsed into ``None``: absent and unparseable are two different things for an author
    to do something about. A document that parses to something other than an object states no
    ``identity.version``, which is what it is reported as.

    Never raises: ``manifest.json`` is in ``_ALLOW_PATTERNS`` and is not required, so this publisher
    has always accepted a module directory without one, and neither RM84 nor RM89 is a licence to
    tighten what it accepts. Every caller answers a missing document the same way: unknown.
    """
    path = module_dir / _MANIFEST_FILENAME
    if not path.is_file():
        return _ManifestRead(None, f"no {_MANIFEST_FILENAME} in the module directory", None)
    try:
        raw = path.read_bytes()
    except OSError:
        return _ManifestRead(None, f"{_MANIFEST_FILENAME} could not be read as JSON", None)
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _ManifestRead(None, f"{_MANIFEST_FILENAME} could not be read as JSON", sha256_bytes(raw))
    if not isinstance(document, dict):
        return _ManifestRead(None, f"{_MANIFEST_FILENAME} states no identity.version", sha256_bytes(raw))
    return _ManifestRead(document, None, sha256_bytes(raw))


def _module_version(document: dict | None, unread_reason: str | None) -> tuple[str | None, str | None]:
    """``identity.version`` out of the manifest ``_manifest_document`` read — ``(version, reason)``.

    Exactly one member is ever set, which is the point: a bare `None` version cannot say whether the
    manifest was missing, unparseable, silent about the version, or carrying something that is not a
    version, and those are four different things for an author to do something about. The first two
    are the reader's reason, passed through.

    **The one field is read out of the JSON rather than through ``read_manifest``, deliberately.**
    Validating the whole ``ModuleManifest`` to reach one string means an unrelated defect — a hyphen in
    ``identity.name``, an ``icon_set`` outside the vocabulary — withholds a version that is right there
    and perfectly legible, and the resulting refusal names neither the field nor the value. The
    SemVer rule is not restated here either: ``is_valid_version`` is the same predicate
    ``Identity.version``'s own validator calls, and it is what keeps a stray ``/`` or ``..`` out of a
    path segment.
    """
    if document is None:
        return None, unread_reason
    identity = document.get("identity")
    version = identity.get("version") if isinstance(identity, dict) else None
    if version is None:
        return None, f"{_MANIFEST_FILENAME} states no identity.version"
    if not isinstance(version, str) or not is_valid_version(version):
        return None, f"{_MANIFEST_FILENAME}'s identity.version is not MAJOR.MINOR.PATCH: {version!r}"
    return version, None


def _literal_patterns(paths: Iterable[str]) -> list[str]:
    """Each path as an `fnmatch` pattern that selects that path and nothing else (RM347, RM353).

    The hub matches `allow_patterns` and `delete_patterns` with `fnmatch`, so a name is a pattern
    whether anyone meant it as one or not: `data/chr[1].parquet` unescaped is a character class that
    selects `data/chr1.parquet` and never itself. Every list of names this module hands the hub goes
    through here, because a publish sends what its plan names and a deletion removes what its plan
    names, and neither plan contains a glob.
    """
    return [glob_escape(path) for path in paths]


def _named_entry(entry: object) -> tuple[str, str | None] | None:
    """``(name, sha256)`` of one ``FileEntry``-shaped manifest entry, or ``None`` when it names no file.

    **The one filter over file entries (RM355).** An entry names a file when it is an object whose
    ``name`` is a string that is not blank (RM368: a whitespace-only name named a file here and none on
    disk). A ``sha256`` that is not a string is ``None`` here; whether that is the unknown arm or a
    malformed field is ``_declarations``' question, asked before anything reads this.
    """
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    sha256 = entry.get("sha256")
    return name, sha256 if isinstance(sha256, str) else None


def _shape(value: object) -> str:
    return f"{type(value).__name__} {value!r}"


@dataclass(frozen=True)
class _Declarations:
    """Every file entry the manifest declares, as ``(field path, raw entry)``, plus the fields whose
    shape no compiler writes (RM368)."""

    entries: tuple[tuple[str, object], ...]
    malformed: tuple[str, ...]
    #: The raw `artifact.files` entries, or `None` when the manifest cannot say (the field is absent).
    attested: tuple[object, ...] | None


def _declarations(document: dict) -> _Declarations:
    """Walk ``DECLARED_FILE_FIELDS`` once: the entries each field declares, and what is malformed.

    **Present and unreadable is the refusal; absent is the unknown arm**
    (`@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal`). A field that is
    missing or ``null`` declares nothing, and a missing ``artifact.files`` is the "manifest cannot say"
    the plan falls back on. A field present in a shape the compiler never writes — ``artifact.files``
    an object, ``logs`` a string, a ``sha256`` a number — used to read as absent too, and each dropped
    a gate: the attestation check, or the hash check on that file. Those are now listed here and the
    plan refuses on them, quoting each.

    An entry that names no file stays outside ``malformed``: an attested one is refused separately
    (``_unnamed_attested``), an optional one declares nothing (RM355).
    """
    entries: list[tuple[str, object]] = []
    malformed: list[str] = []
    attested: tuple[object, ...] | None = None
    for field in DECLARED_FILE_FIELDS:
        value = document.get(field)
        if value is None:
            continue
        if field == "logs":
            if not isinstance(value, list):
                malformed.append(f"logs is {_shape(value)}, not a list")
                continue
            entries.extend((f"logs[{i}]", entry) for i, entry in enumerate(value))
            continue
        if not isinstance(value, dict):
            malformed.append(f"{field} is {_shape(value)}, not an object")
            continue
        if field == "artifact":
            files = value.get("files")
            if files is None:
                continue
            if not isinstance(files, list):
                malformed.append(f"artifact.files is {_shape(files)}, not a list")
                continue
            attested = tuple(files)
            entries.extend((f"artifact.files[{i}]", entry) for i, entry in enumerate(files))
        elif field == "provenance":
            entries.append((field, {"name": value.get("file"), "sha256": value.get("sha256")}))
        else:
            entries.append((field, value))
    for path, entry in entries:
        sha256 = entry.get("sha256") if isinstance(entry, dict) else None
        if _named_entry(entry) is not None and sha256 is not None and not isinstance(sha256, str):
            malformed.append(f"{path}.sha256 is {_shape(sha256)}, not a string")
    return _Declarations(tuple(entries), tuple(malformed), attested)


def _unnamed_attested(document: dict) -> list[object]:
    """The ``artifact.files`` entries that name no file — present, and unreadable as a file entry.

    The filter drops them from every list, and the plan refuses on them, quoting each: the attested
    list is the one ``artifact.digest`` is computed over, so an entry that cannot be sent is a digest
    no upload can satisfy, and dropping it quietly would publish that false claim
    (``@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal``). That is any entry
    that is not an object with a non-blank string ``name``: an empty or blank name, a missing one, a
    number, a bare string. The compiler never writes one; a hand edit does.
    """
    return [entry for entry in _declarations(document).attested or () if _named_entry(entry) is None]


def _attested_parquets(document: dict) -> list[str] | None:
    """The files ``manifest.artifact.files`` names, or ``None`` when the manifest cannot say.

    Tri-state, like ``_module_version`` beside it and for the same reason: a missing manifest or a
    missing ``artifact.files`` is *unknown*, not *attests nothing*, and an unknown withholds rather than
    refusing. Read field by field out of the JSON rather than through ``read_manifest`` — an unrelated
    model defect must not be able to turn a legible file list into a failed publish.
    """
    attested = _declarations(document).attested
    if attested is None:
        return None
    return [named[0] for entry in attested if (named := _named_entry(entry)) is not None]


def _declared_files(document: dict) -> list[tuple[str, str | None]]:
    """Every file the manifest declares in the module directory, as ``(name, sha256)``, in plan order.

    **One reader for both the plan and the guard (RM353).** The fields are ``DECLARED_FILE_FIELDS``:
    ``artifact.files``, ``logo``, ``readme``, ``provenance`` and ``logs``. ``provenance`` is a summary
    carrying ``file`` and ``sha256``, which is why it was the one no allowlist held — `provenance.json`
    was named and hashed in every manifest that had one and never uploaded. ``inputs`` and ``derived``
    are not here (``SPEC_SIDE_FILE_FIELDS``).

    Every entry passes the one filter, ``_named_entry``, that ``_attested_parquets`` reads through too
    (RM355). A malformed field contributes nothing here, and the plan has already refused on it.
    """
    return [
        named for _, entry in _declarations(document).entries if (named := _named_entry(entry)) is not None
    ]


def _hub_ignore_patterns() -> list[str]:
    """``upload_folder``'s own default ignore list, read from the hub rather than restated.

    A guarded lazy import, like ``_hf_api``'s: importing ``huggingface_hub.hf_api`` costs every CLI
    start about 0.3 s, and only a publish needs it. Without the wheel nothing can be uploaded either,
    so an empty list refuses nothing that would have been sent.
    """
    try:
        from huggingface_hub.hf_api import DEFAULT_IGNORE_PATTERNS
    except ImportError:
        return []
    return list(DEFAULT_IGNORE_PATTERNS)


def _declared_refusal_reason(module_dir: Path, name: str) -> str | None:
    """Why a name the manifest declares is not uploaded although the manifest names it, else ``None``.

    Every declared field documents its name as a path *relative to the module dir*, and the compiler
    only ever writes one; a hand-edited manifest can still say ``../x``, ``/etc/x``, or name a symlink
    whose target is elsewhere. The lexical half is read on the name as the manifest spells it (POSIX,
    the spelling the compiler writes); the resolved half is what catches the symlink, which no
    spelling shows. Written for ``manifest.logs`` (RM347) and read for every declared file since RM353.

    **A hidden path is refused on the compiler's own terms, not a second rule.** RM338's discovery skips
    a hidden path for every kind except ``*.log``, which ships hidden or not as it always has; so a
    hidden ``.log`` the manifest names is uploaded, and any other hidden name (``.env``, an editor's or
    an agent's settings) is one the compiler never writes and a hand edit put there. **Whatever the
    hub's own default ignore list names is refused regardless** (``.git``, ``.cache/huggingface``):
    tool state, never a module file. Since RM368 the publish sends through ``create_commit``, which
    applies no ignore list, so this refusal is what keeps such a path out, not the hub.
    """
    spelled = PurePosixPath(name)
    if spelled.is_absolute():
        return "it is an absolute path"
    if ".." in spelled.parts:
        return "it climbs out with '..'"
    if any(fnmatchcase(name, pattern) for pattern in _hub_ignore_patterns()):
        return "the hub's default ignore list names it (tool state, never a module file)"
    if spelled.suffix != ".log" and any(part.startswith(".") for part in spelled.parts):
        return "it is on a hidden path, which the compiler ships only for a *.log"
    root = module_dir.resolve()
    try:
        resolved = (module_dir / name).resolve()
    except (OSError, ValueError) as exc:  # a NUL byte, a symlink loop: never a reason to fail the plan
        return f"it cannot be resolved ({exc})"
    if not resolved.is_relative_to(root):
        return f"it resolves outside {root} (a symlink)"
    return None


def _sendable(module_dir: Path, names: Iterable[str]) -> tuple[list[str], dict[str, str]]:
    """Split declared names into ``(sendable, {refused name: reason})`` — inside the module, on disk.

    A name on disk that passes ``_declared_refusal_reason`` is sendable. A refused name carries its
    reason; a name absent from disk is in neither, because what that means depends on the field — an
    attested parquet missing is a refusal, a missing log or logo is normal.
    """
    sendable: list[str] = []
    refused: dict[str, str] = {}
    for name in names:
        reason = _declared_refusal_reason(module_dir, name)
        if reason is not None:
            refused[name] = reason
        elif (module_dir / name).is_file() and name not in sendable:
            sendable.append(name)
    return sendable, refused


def plan_upload(
    module_dir: Path,
    name: str,
    repo_id: str | None = None,
) -> UploadPlan:
    """Resolve the upload plan and validate the compiled artifacts are present.

    Two destinations, both planned here (RM84): the flat `data/<name>/`, which is what the reference
    consumer's discovery scans and therefore has to keep working and keep meaning *latest*, and
    `data/<name>/v<version>/` **inside it** — nested rather than a sibling, because the flat path is
    the one deployed readers are pointed at — which is the only thing on that path that can name a
    particular release. A module with no readable version gets the flat path alone, never a `vNone`
    directory, and `version_unknown_reason` says which of the four reasons applies. The reason is a
    field rather than a log line for the reason every other withheld answer here is
    (`clin_sig_not_checked`, `skipped_offline`): a caller that has to parse prose to learn what
    happened has not been told.

    **The files are what the manifest declares (RM353, `@publisher-allowlist-derived`).** When
    `manifest.artifact.files` is legible, the plan is `manifest.json` plus every file the manifest
    names in the module directory — the attested parquets, the logo, the readme, `provenance.json` and
    each log — and nothing else: a parquet an earlier compile left behind, or a logo the manifest does
    not name, would arrive unattested, and a stale parquet this publish put on the flat path would read
    to discovery as part of the module. (One already on the remote stays; a publish deletes only what
    it declares.) Each declared file sent must still hash to the sha256 the manifest states, or the
    plan refuses: the manifest is the guard's comparator, so it has to be true of the bytes. A
    declared optional file that leaves the module directory is skipped with a warning
    naming the reason; one absent from disk is skipped quietly, since every optional file is optional
    (`verify` skips an absent log or logo the same way). **When the manifest cannot say** — absent,
    unparseable, or with no `artifact.files` list — the plan falls back to `_ALLOW_PATTERNS` found on
    disk: an unknown withholds, and a directory with no manifest has always been publishable.

    **What it refuses, in order, most specific first so a refusal names the actual fault** — each a
    `ModuleNotPublishable` (RM368):

    - **A declared field in a shape the compiler never writes** (`artifact.files` that is not a list,
      a `sha256` that is not a string, …), quoting each. Absent is unknown and withholds; present and
      unreadable used to read as absent too and dropped the gate that field feeds.
    - **An attested entry naming no file** — anything but an object with a non-blank string `name`.
    - **Every attested artifact file is sent.** `artifact.digest` is a Merkle root over exactly the
      files `manifest.artifact.files` names, so an attested file missing from disk, or one whose name
      leaves the module directory, would make the published manifest a false claim about bytes that
      are not there.
    - **A declared file whose bytes are not the ones declared** (the sha256 differs).
    - **`weights.parquet` never travels alone.** A SNP core compiles to all three, so a missing
      `annotations`/`studies` beside it is an interrupted compile.
    - **At least one lead table.** A directory with a manifest, a readme and no annotation rows is not
      a module; publishing one is the silent failure a bare widening of the old rule would have
      produced, and it is what discovery would then be unable to see.

    **The plan is one reading of the disk (RM368).** Every planned file is hashed once, here, into
    `UploadPlan.sha256` — `manifest.json` from the very bytes it was parsed from — and the upload sends
    exactly those bytes or refuses (`_verified_payload`).
    """
    read = _manifest_document(module_dir)
    return _plan_from_document(module_dir, name, repo_id, read)


def _plan_from_document(
    module_dir: Path,
    name: str,
    repo_id: str | None,
    read: _ManifestRead,
) -> UploadPlan:
    """``plan_upload`` over a manifest already read, so a publish reads it once for the plan and its
    guard (RM355)."""
    resolved_repo = repo_id or DEFAULT_REPO_ID
    document = read.document or {}
    declarations = _declarations(document)
    if declarations.malformed:
        raise ModuleNotPublishable(
            f"{name}: {_MANIFEST_FILENAME} declares "
            f"{'a field' if len(declarations.malformed) == 1 else 'fields'} in a shape the compiler "
            f"never writes: {'; '.join(declarations.malformed)} — read as absent, "
            f"{'it' if len(declarations.malformed) == 1 else 'each'} would drop a check on what is "
            f"sent. Re-compile {module_dir}."
        )
    attested = _attested_parquets(document)
    declared = [declared_name for declared_name, _ in _declared_files(document)]
    if attested is None:
        files = [f for f in _ALLOW_PATTERNS if (module_dir / f).is_file()]
        optional = declared
    else:
        unnamed = _unnamed_attested(document)
        if unnamed:
            raise ModuleNotPublishable(
                f"{name}: {_MANIFEST_FILENAME}'s artifact.files carries "
                f"{'an entry' if len(unnamed) == 1 else f'{len(unnamed)} entries'} naming no file: "
                f"{unnamed!r} — `artifact.digest` is computed over every attested entry, so no upload "
                f"could carry what it covers. The compiler never writes such an entry; re-compile "
                f"{module_dir}."
            )
        artifact_files, refused = _sendable(module_dir, attested)
        unsent = [f for f in attested if f not in artifact_files]
        if unsent:
            reasons = "".join(f" ({f}: {refused[f]})" for f in unsent if f in refused)
            raise ModuleNotPublishable(
                f"{name}: {_MANIFEST_FILENAME} attests {unsent} but the upload would not carry "
                f"{'it' if len(unsent) == 1 else 'them'}{reasons} — `artifact.digest` is computed over "
                f"the attested files, so what arrived could not be verified against the manifest that "
                f"describes it. Re-compile {module_dir} if the file is missing."
            )
        files = [*artifact_files, _MANIFEST_FILENAME]
        optional = [f for f in declared if f not in attested]
    sendable, refused = _sendable(module_dir, optional)
    for refused_name, reason in refused.items():
        logger.warning(
            "%s names %r, which is not uploaded: %s.",
            _MANIFEST_FILENAME,
            refused_name,
            reason,
        )
    files.extend(f for f in sendable if f not in files)
    # Every planned file hashed once, here (RM368): the manifest from the bytes it was parsed from, the
    # rest now. The upload sends these bytes or refuses, so the plan, the check and the send are one
    # reading of the disk rather than three.
    planned = {f: _planned_hash(module_dir, f, read) for f in files}
    # The bytes sent are the bytes declared: a file edited after the compile would arrive under a
    # manifest stating a different sha256, and the versioned-path guard — which compares the two
    # manifests — would wave it through (RM353). A declaration with no hash is not checked.
    hashes = _declared_hashes(document)
    moved = [f for f in files if f in hashes and planned[f] != hashes[f]]
    if moved:
        raise ModuleNotPublishable(
            f"{name}: {moved} on disk {'is' if len(moved) == 1 else 'are'} not the bytes "
            f"{_MANIFEST_FILENAME} declares (the sha256 differs), so the published manifest would "
            f"describe files the repository does not hold. Re-compile {module_dir} so the manifest "
            f"states what is there."
        )
    if "weights.parquet" in files:
        half = [f for f in _EXPECTED_WITH_WEIGHTS if f not in files]
        if half:
            raise ModuleNotPublishable(
                f"{name}: missing compiled artifact(s) {half} in {module_dir} beside "
                f"weights.parquet — a SNP core compiles to all three, so this directory is a "
                f"half-finished compile. Re-run `just-dna-enricher enrich-and-compile` "
                f"or `just-dna-compiler compile`."
            )
    if not any(f in LEAD_PARQUETS for f in files):
        raise ModuleNotPublishable(
            f"{name}: no annotation table in {module_dir} — a module carries at least one of "
            f"{list(LEAD_PARQUETS)}. Compile the module first (e.g. "
            f"`just-dna-enricher enrich-and-compile` or `just-dna-compiler compile`)."
        )
    flat = f"data/{name}"
    version, reason = _module_version(read.document, read.unread_reason)
    return UploadPlan(
        module=name,
        repo_id=resolved_repo,
        path_in_repo=flat,
        versioned_path_in_repo=None if version is None else f"{flat}/v{version}",
        version_unknown_reason=reason,
        files=files,
        sha256=planned,
    )


def _planned_hash(module_dir: Path, name: str, read: _ManifestRead) -> str:
    """The sha256 a planned file has now — the manifest's from the one read the plan parsed."""
    if name == _MANIFEST_FILENAME and read.sha256 is not None:
        return read.sha256
    return sha256_file(module_dir / name)


def _verified_payload(module_dir: Path, plan: UploadPlan) -> list[tuple[str, bytes]]:
    """Every planned file's bytes, read once more and each checked against the plan's hash (RM368).

    What is sent is these bytes, never a second read: the guard compared the plan, and a recompile, an
    edit or a deletion between the check and the send would otherwise ship bytes nothing checked. A
    file that no longer hashes to its plan entry, or can no longer be read, refuses the publish before
    any commit, naming each.
    """
    payload: list[tuple[str, bytes]] = []
    changed: list[str] = []
    for name in plan.files:
        path = module_dir / name
        data = path.read_bytes() if path.is_file() else None
        if data is None or sha256_bytes(data) != plan.sha256.get(name):
            changed.append(name if data is not None else f"{name} (gone)")
            continue
        payload.append((name, data))
    if changed:
        raise PlanChangedError(
            f"{plan.module}: {changed} changed after the plan was read and checked, so the upload "
            f"would send bytes nothing checked. Nothing was committed; re-run the publish once "
            f"{module_dir} has stopped changing (a compile still writing to it, an edit)."
        )
    return payload


def _artifact_digest(document: dict) -> str | None:
    """``manifest.artifact.digest``, or ``None`` when the manifest cannot say."""
    artifact = document.get("artifact")
    digest = artifact.get("digest") if isinstance(artifact, dict) else None
    return digest if isinstance(digest, str) and digest else None


def _content_unchanged(published: Any, local: Any) -> bool | None:
    """Whether the two manifests carry one `content_signature`, `None` when either states none."""
    left = published.get("content_signature") if isinstance(published, dict) else None
    right = local.get("content_signature") if isinstance(local, dict) else None
    if not isinstance(left, str) or not left or not isinstance(right, str) or not right:
        return None
    return left == right


def _toolchain_text(toolchain: dict[str, str]) -> str:
    """`polars 2.1.0, python 3.13.1`: a recorded toolchain as a refusal prints it."""
    return ", ".join(f"{library} {release}" for library, release in sorted(toolchain.items()))


def _declared_hashes(document: dict) -> dict[str, str]:
    """Each declared file's sha256 by name — the declarations a hash is known for."""
    return {name: sha256 for name, sha256 in _declared_files(document) if sha256 is not None}


def _manifest_differences(local: dict, published: dict) -> list[str]:
    """The dotted paths at which two manifests differ, outside what the declared-file arm compares.

    The digest and every declared file's name and hash are `_versioned_conflict`'s own arms, with
    their unknown rule (a declaration with no legible hash does not disagree), so their fields are
    skipped here — `provenance`'s other keys (`generator`, `item_count`, …) are compared. Everything
    else in the manifest is part of what the version names: a new title, a new `compiled_at`.
    """
    differing: list[str] = []

    def walk(left: object, right: object, path: str) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                walk(left.get(key), right.get(key), f"{path}.{key}" if path else key)
        elif left != right:
            differing.append(path)

    for key in sorted(local.keys() | published.keys()):
        left, right = local.get(key), published.get(key)
        if key == "provenance" and isinstance(left, dict) and isinstance(right, dict):
            walk(
                {k: v for k, v in left.items() if k not in ("file", "sha256")},
                {k: v for k, v in right.items() if k not in ("file", "sha256")},
                key,
            )
        elif key not in DECLARED_FILE_FIELDS:
            walk(left, right, key)
    return differing


def _versioned_conflict(api, plan: "UploadPlan", local: dict | None) -> tuple[str, dict] | None:
    """How the release already at the versioned path **differs** from this one — else ``None``.

    Returned beside the published manifest it read, so the caller can compare the recorded
    toolchains (RM342) without a second download.

    RM88's comparator, widened by RM353 and RM368, and these outcomes are the whole of the gate:

    - **no versioned path** (the module states no version) — nothing addressable to collide with;
    - **the path is not there** — the first publish of this version, which is the normal case;
    - **it is there and says the same** — the same release arriving twice. This must *proceed*, and it
      is the case a naive existence check would break: `upload_module` writes two commits and
      documents a re-run as the recovery when the second fails, so refusing on presence alone would
      refuse exactly the retry the design depends on;
    - **it is there and says something else** — the collision, returned as a sentence naming what
      differs, and the caller refuses unless `--force`.

    **"Says the same" is the manifest itself (RM368), compared in three arms** so the refusal names
    the actual difference: the artifact digest; every declared file's hash (RM353 — the digest is a
    Merkle root over the attested parquets and excludes logs, provenance, logo and readme by design);
    and every other field of the manifest (`_manifest_differences`), since the published manifest is
    replaced by the upload too, and a second publish of one version under a new title used to replace
    it with no arm noticing. A remote manifest whose bytes hash to the plan's own is the same release
    without a field compared. A declaration with no legible hash on either side is not compared: an
    unknown cannot disagree.

    **An unknown proceeds, with a warning, and that is a decision rather than an oversight.** If the
    remote manifest cannot be read — a flake, a repo that answers but has no manifest at that path —
    nothing established a collision, so nothing may assert one; the house algebra withholds. Failing
    *closed* here would make every network hiccup demand `--force`, which trains an author to pass it
    by default and turns a gate into one people route around. That is the failure the policy decision
    was explicitly trying to avoid, so it must not be reintroduced by the error path.

    Reads the remote `manifest.json` rather than listing per-file hashes: the manifest states every
    declared file's sha256, so one small download answers the question that a tree listing could
    only answer for whatever happens to be LFS-backed.
    """
    if plan.versioned_path_in_repo is None or local is None:
        return None
    remote_manifest = f"{plan.versioned_path_in_repo}/{_MANIFEST_FILENAME}"
    try:
        from huggingface_hub import hf_hub_download

        if not api.file_exists(repo_id=plan.repo_id, filename=remote_manifest, repo_type="dataset"):
            return None
        local_copy = hf_hub_download(
            repo_id=plan.repo_id,
            filename=remote_manifest,
            repo_type="dataset",
            token=api.token,
        )
        raw = Path(local_copy).read_bytes()
        published = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        logger.warning(
            "Could not read the published manifest at %s (%s); proceeding without the "
            "already-published check. Nothing established a collision, so nothing asserts one.",
            remote_manifest,
            exc,
        )
        return None
    if not isinstance(published, dict) or sha256_bytes(raw) == plan.sha256.get(_MANIFEST_FILENAME):
        return None
    local_digest, remote_digest = _artifact_digest(local), _artifact_digest(published)
    if local_digest is not None and remote_digest is not None and local_digest != remote_digest:
        return (
            f"a different artifact ({remote_digest[:19]}… there, {local_digest[:19]}… here). Note that "
            f"recompiling an unchanged spec under a newer compiler moves the digest too — if that is "
            f"what happened, this refusal is still protecting the bytes the published version was cut "
            f"from"
        ), published
    local_declared, remote_declared = _declared_files(local), _declared_files(published)
    here = {n: h for n, h in local_declared if h is not None}
    there = {n: h for n, h in remote_declared if h is not None}
    # A name declared with no legible hash on either side is an unknown, and an unknown cannot disagree.
    unhashed = {n for n, h in [*local_declared, *remote_declared] if h is None}
    differing = [
        f"{n} ({'changed' if n in here and n in there else 'declared only here' if n in here else 'declared only there'})"
        for n in sorted((here.keys() | there.keys()) - unhashed)
        if here.get(n) != there.get(n)
    ]
    same_data = local_digest is not None and local_digest == remote_digest
    if differing:
        return (
            f"{'the same compiled data but ' if same_data else ''}different declared files: "
            f"{', '.join(differing)}. Logs, provenance, the logo and the readme are outside "
            f"`artifact.digest`, so the data agreeing does not make these the files that version was "
            f"published with"
        ), published
    fields = _manifest_differences(local, published)
    if not fields:
        return None
    return (
        f"{'the same compiled data and declared files but ' if same_data else ''}a different "
        f"{_MANIFEST_FILENAME}, at {', '.join(fields)}. The manifest is replaced by the upload too, so "
        f"what that version says about itself would change"
    ), published


def _refuse_a_collision(api, plan: UploadPlan, document: dict | None, name: str) -> None:
    """Raise the versioned-path collision, if there is one — the one check the real run and the
    rehearsal share (RM368)."""
    conflict = _versioned_conflict(api, plan, document)
    if conflict is None:
        return
    sentence, published = conflict
    collision = (
        f"{name}: {plan.versioned_path_in_repo}/ is already published with {sentence}. This upload "
        f"would replace what that version names. Bump `version:` in module_spec.yaml and "
        f"re-compile to publish this as a new release, or pass --force to overwrite it deliberately."
    )
    # `_versioned_conflict` answers only with a local manifest in hand, so `document` is a dict here.
    # The toolchain explains a moved digest only; a declared file that differs is the plain collision.
    local_digest, remote_digest = _artifact_digest(document or {}), _artifact_digest(published)
    artifacts_differ = None not in (local_digest, remote_digest) and local_digest != remote_digest
    if artifacts_differ and toolchains_differ(published, document) is True:
        published_toolchain = recorded_toolchain(published) or {}
        local_toolchain = recorded_toolchain(document) or {}
        content_unchanged = _content_unchanged(published, document)
        content = {
            True: "the content_signature is the same on both sides, so the toolchain alone can "
            "account for the moved digest",
            False: "the content_signature differs as well, so the content changed too and the "
            "toolchain does not account for all of it",
            None: "one side states no content_signature, so whether the content changed is unknown",
        }[content_unchanged]
        raise ToolchainDiffersError(
            f"{collision} The two manifests record different toolchains "
            f"({_toolchain_text(published_toolchain)} there, {_toolchain_text(local_toolchain)} "
            f"here); {content}. The refusal still protects the bytes the published version was "
            f"cut from.",
            published_toolchain=published_toolchain,
            local_toolchain=local_toolchain,
            content_unchanged=content_unchanged,
        )
    raise PublishCollisionError(collision)


def _read_only_api(token: str | None = None):
    """An ``HfApi`` for reading a published repo — a token when there is one, anonymous otherwise.

    A rehearsal must not need write access to say what a publish would do, and reading a public repo
    needs none (the snapshot dry run's reader, ``check_publish_orphans_no_sidecar``, does the same).
    """
    try:
        from huggingface_hub import HfApi, get_token
    except ImportError as exc:
        raise ImportError(
            "huggingface_hub is required to check a publish against the published repo"
        ) from exc
    return HfApi(token=token or env_value("HF_TOKEN") or get_token())


def _commit_operations(prefix: str, payload: list[tuple[str, bytes]]) -> list[Any]:
    """One add per planned file under ``prefix``, carrying the verified bytes themselves."""
    try:
        from huggingface_hub import CommitOperationAdd
    except ImportError as exc:
        raise ImportError("huggingface_hub is required to publish to HuggingFace") from exc
    return [
        CommitOperationAdd(path_in_repo=f"{prefix}/{name}", path_or_fileobj=data) for name, data in payload
    ]


def rehearse_upload(
    module_dir: Path,
    name: str,
    repo_id: str | None = None,
    token: str | None = None,
    force: bool = False,
) -> UploadPlan:
    """What `upload_module` would do, short of writing: the plan, and the versioned-path check (RM368).

    The dry run. It runs every check the real run runs — the plan's refusals and, when the module
    states a version and `force` is not set, the collision check against the published manifest, read
    with a read-only client — and raises what the real run would raise. It creates no repo and commits
    nothing. A hub it cannot reach is the real run's unknown: a warning, and the plan.

    `plan_upload` alone stays the offline half, for a caller that wants the plan with no remote read.
    """
    read = _manifest_document(module_dir)
    plan = _plan_from_document(module_dir, name, repo_id, read)
    if not force and plan.versioned_path_in_repo is not None and read.document is not None:
        _refuse_a_collision(_read_only_api(token), plan, read.document, name)
    return plan


def upload_module(
    module_dir: Path,
    name: str,
    repo_id: str | None = None,
    token: str | None = None,
    commit_message: str | None = None,
    force: bool = False,
) -> UploadPlan:
    """Upload the compiled module to a HuggingFace dataset collection.

    Ensures the dataset repo exists (create-or-update), then writes the same files to the flat path
    and — when the manifest states a version — to the versioned subdirectory under it.

    **What is sent is the plan's bytes (RM368).** The plan hashed every file it names; after the
    collision check, each is read once more, checked against that hash, and sent as those bytes through
    `create_commit` — never re-read from the directory by the hub. A file that changed in between (a
    recompile still writing, an edit) is a `PlanChangedError` before either commit.

    **The two writes are two commits, not one.** Each `create_commit` is its own commit, so a reader can
    briefly see the flat path refreshed while the versioned copy is not there yet; the flat path goes
    first because it is the one anything reads today. One commit carrying both paths' operations is
    now a one-line change and was not taken here: two commits is the documented behaviour, and a
    re-run, which is idempotent, is the documented recovery when the second fails.

    **The versioned path refuses to be overwritten with different bytes (RM88, RM353, RM368).** Before
    either write, the published `manifest.json` at `data/<name>/v<version>/` is read and compared with
    this module's: its `artifact.digest`, the sha256 of every file it declares, and every other field
    (`_versioned_conflict`). A difference is a `PublishCollisionError` unless `force=True`. The flat
    path is deliberately **not** guarded: it means *latest*, so overwriting it is what it is for, and
    the whole point of the versioned copy is that it does not.

    The policy is refuse-unless-`--force` rather than warn-and-proceed or refuse-outright, decided
    2026-08-18. The flag's existence is itself the claim that overwriting is sometimes right — a
    curator re-cutting a draft release is a real workflow, and a gate with no override becomes a gate
    people route around.

    **Recompiling under a newer compiler also moves the digest**, and will trip this. That is correct
    rather than a false positive: P4 pins byte-reproducibility to `compiler_version`, the recorded
    toolchain and the resolved reference, so the versioned path really would come to hold different
    bytes than the ones it was published with. The refusal says so, because "I changed nothing" is the
    first thing its first user will think.

    **When the artifacts differ and both manifests recorded a toolchain and the two differ, the refusal
    is a `ToolchainDiffersError` (RM342)**, which names both toolchains. Either side unrecorded (a
    manifest compiled before 0.8), the same toolchain on both, or a difference in declared files or
    other fields alone, keeps the plain `PublishCollisionError`.

    Raises PermissionError if no token is available and ImportError if huggingface_hub is absent.
    """
    read = _manifest_document(module_dir)
    plan = _plan_from_document(module_dir, name, repo_id, read)
    api = ensure_repo(plan.repo_id, token)
    if not force:
        _refuse_a_collision(api, plan, read.document, name)
    payload = _verified_payload(module_dir, plan)
    api.create_commit(
        repo_id=plan.repo_id,
        repo_type="dataset",
        operations=_commit_operations(plan.path_in_repo, payload),
        commit_message=commit_message or f"Add {name} module",
    )
    if plan.versioned_path_in_repo is not None:
        segment = plan.versioned_path_in_repo.rsplit("/", 1)[-1]
        api.create_commit(
            repo_id=plan.repo_id,
            repo_type="dataset",
            operations=_commit_operations(plan.versioned_path_in_repo, payload),
            commit_message=commit_message or f"Add {name} module {segment}",
        )
    return plan


class SnapshotPlan(BaseModel):
    """What a reference-snapshot publish would send (also the dry-run result)."""

    repo_id: str = Field(description="Target HuggingFace dataset repo (owner/name)")
    files: list[str] = Field(description="Repo-relative paths that will be uploaded")


def plan_reference_snapshot(
    snapshot_dir: Path,
    repo_id: str | None = None,
    *,
    payload: str | None = None,
) -> SnapshotPlan:
    """Resolve a snapshot publish plan and validate the built artifacts are present.

    `payload` names a snapshot whose content is **one file at the root** rather than
    `data/*.parquet` — STRchive's `STRchive-loci.json` is the case, and ACMG's `acmg_sf.csv` is the
    shape's second member. The parameter is the caller's, deliberately: a lane knows the name of the
    file it builds, and putting a roster of lane filenames in the publisher would make this function
    the fourth place that has to learn about a new snapshot kind.

    A `payload` snapshot is refused when the file is missing, exactly as a parquet one is when
    `data/` is empty — the refusal is the same claim either way, that there is nothing built here to
    publish.
    """
    resolved_repo = repo_id or DEFAULT_CLINVAR_REPO_ID
    if payload is not None:
        if not (snapshot_dir / payload).is_file():
            raise SnapshotNotPublishable(
                f"no {payload} in {snapshot_dir} — build the snapshot first "
                f"(e.g. `just-dna-enricher strchive build`)"
            )
        # Same registry as the parquet branch below, and for the same reason: this branch had its own
        # copy of the pair, so a payload-only lane that gained a root file would have dropped it
        # exactly the way the parquet branch dropped `LICENSE.txt`.
        files = [payload]
        files.extend(name for name in SNAPSHOT_ROOT_FILENAMES if (snapshot_dir / name).is_file())
        return SnapshotPlan(repo_id=resolved_repo, files=files)
    data_dir = snapshot_dir / SNAPSHOT_DATA_DIRNAME
    parquet = sorted(p.name for p in data_dir.glob("*.parquet")) if data_dir.is_dir() else []
    if not parquet:
        raise SnapshotNotPublishable(
            f"no {SNAPSHOT_DATA_DIRNAME}/*.parquet in {snapshot_dir} — build the snapshot first "
            f"(e.g. `just-dna-enricher clinvar build`)"
        )
    files = [f"{SNAPSHOT_DATA_DIRNAME}/{name}" for name in parquet]
    # Sidecars, when the snapshot has them. Only ClinVar does, and only when `clinvar citations` was
    # run, so absence is normal rather than a reason to refuse.
    for sidecar in SNAPSHOT_SIDECAR_DIRNAMES:
        directory = snapshot_dir / sidecar
        if directory.is_dir():
            files.extend(f"{sidecar}/{p.name}" for p in sorted(directory.glob("*.parquet")))
    # Walked from `locations.SNAPSHOT_ROOT_FILENAMES`, never listed here. A file this function does
    # not name is a file the publish silently drops, and the snapshot still looks complete on the
    # other side — which is how a share-alike snapshot went out without its terms
    # (`@publisher-allowlist-derived`). Absence stays normal: only ClinPGx carries a licence and only
    # the AVI lane carries a knot table.
    for name in SNAPSHOT_ROOT_FILENAMES:
        if (snapshot_dir / name).is_file():
            files.append(name)
    return SnapshotPlan(repo_id=resolved_repo, files=files)


def check_publish_orphans_no_sidecar(plan: SnapshotPlan, api=None, token: str | None = None) -> None:
    """Refuse a publish that would leave a remote sidecar undescribed. Reads the repo; writes nothing.

    **The remote tree, not the remote `release.json`.** The block is a *description* of the bytes and
    the bytes are what a puller gets, so the description is the half that can already be missing —
    which is exactly the state `just-dna-seq/clinvar` was found in on 2026-09-03: the citations parquet
    present, the block gone. A guard reading the block would have passed the second bad publish as
    happily as the first.

    Scoped to publishes that carry `release.json`, because a publish that carries none overwrites no
    provenance. A repo that does not exist yet lists nothing and passes — that is a first publish, not
    an orphan.

    `api` is the caller's when it has one (a publish has just built an authenticated client and there
    is no reason to build a second); a dry run passes none and gets an anonymous reader, since listing
    a public repo needs no token and a dry run must not require write access to say what a publish
    would do.
    """
    if RELEASE_FILENAME not in plan.files:
        return
    if api is None:
        api = _read_only_api(token)
    try:
        remote = list(api.list_repo_files(repo_id=plan.repo_id, repo_type="dataset"))
    except Exception as exc:
        # Nobody has published here yet, or the listing failed. Neither is an orphan, and a publish
        # that cannot read the repo will fail on its own terms a moment later with a better message.
        logger.info(
            "Could not list %s (%s); publishing without the sidecar check.", plan.repo_id, type(exc).__name__
        )
        return
    carried = {path.split("/", 1)[0] for path in plan.files if "/" in path}
    for sidecar in SNAPSHOT_SIDECAR_DIRNAMES:
        if sidecar in carried:
            continue
        orphaned = sorted(f for f in remote if f.startswith(f"{sidecar}/") and f.endswith(".parquet"))
        if not orphaned:
            continue
        raise OrphanedSidecarError(
            f"{plan.repo_id} carries {', '.join(orphaned)}, and this publish would replace "
            f"{RELEASE_FILENAME} without carrying {sidecar}/ — so the published artifact would hold "
            f"two vintages and describe one. Build the missing half into the snapshot before "
            f"publishing (for ClinVar: `just-dna-enricher clinvar citations --out <snapshot>`), or "
            f"publish from a directory that has it."
        )


def rehearse_reference_snapshot(
    snapshot_dir: Path,
    repo_id: str | None = None,
    *,
    payload: str | None = None,
    token: str | None = None,
) -> SnapshotPlan:
    """What `publish_reference_snapshot` would do, short of writing: the plan and the orphan check.

    The dry run of every snapshot publish command (RM368). A rehearsal that skips the check the real
    publish refuses on is a different operation — two commands ran the orphan check in their dry run
    and the rest did not, so their `--dry-run` promised a publish the real run could refuse. Reads the
    published repo's file list; uploads nothing.
    """
    plan = plan_reference_snapshot(snapshot_dir, repo_id, payload=payload)
    check_publish_orphans_no_sidecar(plan, token=token)
    return plan


class PruneCandidate(BaseModel):
    """One remote file `cache prune` would remove, and the reason it is nameable as removable."""

    path: str = Field(description="Repo-relative path")
    size: int | None = Field(default=None, description="Bytes, when the listing stated one")
    reason: str = Field(description="Why this file is not part of the snapshot the lane publishes")


class PrunePlan(BaseModel):
    """What a prune would delete from one repo. The dry run and the deletion read the same object."""

    repo_id: str
    candidates: list[PruneCandidate] = Field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(c.size or 0 for c in self.candidates)


def plan_prune(repo_id: str, filename_glob: str, api=None) -> PrunePlan:
    """What the published repo carries that this lane's snapshot is not made of. Reads; deletes nothing.

    **Two sources of a name, and neither is a guess.** A file under `data/` that the lane's own glob
    excludes is not part of the snapshot by the same definition provisioning uses — `_provision_snapshot`
    already refuses to download it and warns when it finds one locally. And a file a `LayoutShift`
    declares retired is nameable even where the glob cannot see it: for the four lanes whose glob is
    `*.parquet` the exclusion set is empty by construction, so declaration is the only way a retired
    file there is ever identified.

    Everything else is left alone, including files this tier never wrote — `README.md`,
    `.gitattributes`, `release.json`, `LICENSE.txt`, and any sidecar directory. A pruner that removed
    what it did not recognise would be the sweep this design exists to avoid.
    """
    if api is None:
        try:
            from huggingface_hub import HfApi, get_token
        except ImportError as exc:
            raise ImportError("huggingface_hub is required to inspect a published repo") from exc
        api = HfApi(token=env_value("HF_TOKEN") or get_token())
    entries = list(api.list_repo_tree(repo_id=repo_id, repo_type="dataset", recursive=True, expand=True))
    sizes = {getattr(e, "path", ""): getattr(e, "size", None) for e in entries}
    remote = [path for path in sizes if path]

    candidates: dict[str, PruneCandidate] = {}
    prefix = f"{SNAPSHOT_DATA_DIRNAME}/"
    for path in sorted(remote):
        if not (path.startswith(prefix) and path.endswith(".parquet")):
            continue
        if fnmatch(path[len(prefix) :], filename_glob):
            continue
        candidates[path] = PruneCandidate(
            path=path,
            size=sizes.get(path),
            reason=f"under {SNAPSHOT_DATA_DIRNAME}/ but outside this snapshot ({filename_glob})",
        )
    for shift in LAYOUT_SHIFTS:
        if shift.repo_id != repo_id or shift.retires not in sizes:
            continue
        # A declared retirement wins the reason slot: it says *when* and *why* the file stopped being
        # part of the snapshot, which "outside the glob" does not.
        candidates[shift.retires] = PruneCandidate(
            path=shift.retires,
            size=sizes.get(shift.retires),
            reason=f"declared retired — {shift.reason}",
        )
    return PrunePlan(repo_id=repo_id, candidates=[candidates[k] for k in sorted(candidates)])


def prune_repo(plan: PrunePlan, token: str | None = None, commit_message: str | None = None) -> int:
    """Delete a prune plan's files. Called only after the caller has shown the plan and been told yes.

    Returns the number of paths deleted. Deleting is a commit on a git-backed repo, so a superseded
    revision still resolves — but that is a reason to be able to undo a mistake, never a reason to
    remove something nobody looked at, which is why this takes a plan rather than a repo id.
    """
    if not plan.candidates:
        return 0
    api = _hf_api(plan.repo_id, token)
    api.delete_files(
        repo_id=plan.repo_id,
        # Each a literal: `delete_files` matches with `fnmatch`, and a listed `data/x[1].parquet`
        # unescaped would delete `data/x1.parquet`, a file nobody was shown (RM353).
        delete_patterns=_literal_patterns(c.path for c in plan.candidates),
        repo_type="dataset",
        commit_message=commit_message
        or (f"Prune {len(plan.candidates)} file(s) that are not part of this snapshot"),
    )
    return len(plan.candidates)


def publish_reference_snapshot(
    snapshot_dir: Path,
    repo_id: str | None = None,
    token: str | None = None,
    commit_message: str | None = None,
    *,
    payload: str | None = None,
) -> SnapshotPlan:
    """Create-or-update a dataset repo and upload a built reference snapshot to its root.

    Uploads ``data/*.parquet`` + any parquet sidecars (ClinVar's ``citations/``) + ``release.json``, so
    the tree matches ``download.ensure_*_snapshot`` and a provisioned snapshot is the same artifact a
    built one is — PMIDs included, which is what a drafted gene panel needs to compile.
    Raises PermissionError if no token is available and ImportError if huggingface_hub is absent.
    """
    plan = plan_reference_snapshot(snapshot_dir, repo_id, payload=payload)
    api = ensure_repo(plan.repo_id, token)
    check_publish_orphans_no_sidecar(plan, api)
    # A declared retirement rides in the same commit as the upload that replaces it (RM186). Listed
    # once and reused: `check_publish_orphans_no_sidecar` has already read the repo, but its answer is
    # about sidecars, and a second listing is cheaper to reason about than a shared cache of a remote
    # state two checks disagree about the meaning of.
    try:
        remote = list(api.list_repo_files(repo_id=plan.repo_id, repo_type="dataset"))
    except Exception as exc:
        logger.info(
            "Could not list %s (%s); no declared retirement can apply.", plan.repo_id, type(exc).__name__
        )
        remote = []
    due = layout_shifts_to_apply(remote, plan.repo_id)
    if due:
        logger.info(
            "Retiring %s from %s in this commit: %s",
            ", ".join(shift.retires for shift in due),
            plan.repo_id,
            "; ".join(shift.reason for shift in due),
        )

    # **One `upload_folder`, and the size branch is gone** (RM199, revised 2026-09-11).
    #
    # This used to pick `upload_large_folder` above 5 GB, because `upload_folder` was a single
    # non-resumable commit and 32 GB in one of those starts over on any failure. `huggingface_hub`
    # 1.x settled it the other way: **`upload_folder` is itself multi-commit now**, and
    # `upload_large_folder` emits a `FutureWarning` telling callers to stop using it. Found the way
    # deprecations should be — the warning appeared in a real publish.
    #
    # Two things fall out. The threshold and its two constants are gone, and so is the refusal this
    # function used to raise when a declared retirement met the large path: `upload_folder` takes
    # `delete_patterns`, so RM186's arrival-and-departure stays on one call and there is no longer a
    # collision to refuse. What remains upstream's rather than ours is that a *large* upload is
    # several commits either way — so the one-commit guarantee holds for the payloads that fit in one
    # and is the Hub's business for the payloads that do not.
    #
    # **The description still goes last** (RM199's real content). `release.json` is what a puller reads to learn
    # which release it holds, so it must never arrive before the bytes it describes: a publish that
    # lands the description and then fails leaves a snapshot that *reads as* provisioned and is not.
    # That is `@a-publish-may-not-orphan-the-bytes-it-stops-describing` from the other direction, and
    # it costs one extra commit on a path that is already several.
    payload_files = [f for f in plan.files if f != RELEASE_FILENAME]
    description = [f for f in plan.files if f == RELEASE_FILENAME]

    api.upload_folder(
        folder_path=str(snapshot_dir),
        path_in_repo="",
        repo_id=plan.repo_id,
        repo_type="dataset",
        # The retirement is a `delete_patterns` on the same call, so the new file arriving and the old
        # one leaving are one operation rather than a window in which the repo has neither or both.
        # `retires` is one name, never a glob, and made literal so the hub cannot read it as one (RM353).
        delete_patterns=_literal_patterns(shift.retires for shift in due) or None,
        # Derived from the plan rather than restated as a pattern list. The two had to agree and did
        # not: `--dry-run` printed a file the patterns then dropped, which is the failure mode that
        # lost `citations/` and `LICENSE.txt` in the first place. One list, computed once, so what a
        # dry run promises is exactly what an upload sends (`@publisher-allowlist-derived`) — each
        # name made literal, since the hub reads a pattern and `data/chr[1].parquet` is one (RM353).
        allow_patterns=_literal_patterns(payload_files),
        commit_message=commit_message
        or (
            f"Publish reference snapshot ({len(payload_files)} files)"
            + (f", retiring {', '.join(s.retires for s in due)}" if due else "")
        ),
    )

    if description:
        api.upload_folder(
            folder_path=str(snapshot_dir),
            path_in_repo="",
            repo_id=plan.repo_id,
            repo_type="dataset",
            allow_patterns=_literal_patterns(description),
            commit_message=f"Describe the snapshot ({RELEASE_FILENAME})",
        )
    return plan
