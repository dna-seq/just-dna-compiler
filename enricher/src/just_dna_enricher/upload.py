"""HuggingFace upload — publisher surface of the network tier.

Two publish shapes share one create-or-update pathway (``ensure_repo``):

* **module** — a compiled module's artifacts (**every parquet the artifact carries** + manifest.json,
  and a logo and readme if present) to ``datasets/<repo>/data/<name>/``, matching the layout
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
from pathlib import Path

from just_dna_compiler.compiler import ARTIFACT_PARQUETS, LEAD_PARQUETS
from just_dna_format.identity import is_valid_version
from just_dna_format.manifest import LOGO_EXTENSIONS, README_CANDIDATES
from pydantic import BaseModel, Field

from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_LICENSE_FILENAME,
    SNAPSHOT_SIDECAR_DIRNAMES,
    load_env,
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


def _hf_api(repo_id: str, token: str | None = None):
    """Resolve a write token and return an authenticated ``HfApi``.

    **`load_env()` first, because `HF_TOKEN` is a credential like any other.** `get_token()` reads the
    real environment and `~/.cache/huggingface/token`, and neither is a `.env` — so a workspace that
    keeps its token there, as this one does, got *"No HuggingFace token found"* from a publish while
    every other credential path in the tier read the same file without being asked. The load happens
    where the credential is read rather than as a side effect of some other call
    (`@credential-where-read`), and an exported variable still wins: `load_env` uses
    ``override=False``.

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
    load_env()
    resolved_token = token or get_token()
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


class PublishCollisionError(RuntimeError):
    """The versioned path already holds a *different* release, and no `--force` was given (RM88).

    Its own type rather than a `FileNotFoundError`, because the CLI has to tell it apart from the
    three refusals `plan_upload` raises: those say the local module is not publishable, this one says
    the local module is fine and the remote already has that version.
    """


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
    files: list[str] = Field(description="Basenames that will be uploaded")


def _module_version(module_dir: Path) -> tuple[str | None, str | None]:
    """Read ``identity.version`` out of the compiled manifest — ``(version, reason_it_is_unknown)``.

    Exactly one member is ever set, which is the point: a bare `None` version cannot say whether the
    manifest was missing, unparseable, silent about the version, or carrying something that is not a
    version, and those are four different things for an author to do something about.

    **The one field is read out of the JSON rather than through ``read_manifest``, deliberately.**
    Validating the whole ``ModuleManifest`` to reach one string means an unrelated defect — a hyphen in
    ``identity.name``, an ``icon_set`` outside the vocabulary — withholds a version that is right there
    and perfectly legible, and the resulting refusal names neither the field nor the value. The
    SemVer rule is not restated here either: ``is_valid_version`` is the same predicate
    ``Identity.version``'s own validator calls, and it is what keeps a stray ``/`` or ``..`` out of a
    path segment.

    Never raises: ``manifest.json`` is in ``_ALLOW_PATTERNS`` and is not required, so this publisher
    has always accepted a module directory without one, and neither RM84 nor RM89 is a licence to
    tighten what it accepts. The attestation check in ``plan_upload`` withholds for the same reason a
    version does — an unreadable manifest is an unknown, and an unknown is never a finding.
    """
    path = module_dir / _MANIFEST_FILENAME
    if not path.is_file():
        return None, f"no {_MANIFEST_FILENAME} in the module directory"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, f"{_MANIFEST_FILENAME} could not be read as JSON"
    identity = document.get("identity") if isinstance(document, dict) else None
    version = identity.get("version") if isinstance(identity, dict) else None
    if version is None:
        return None, f"{_MANIFEST_FILENAME} states no identity.version"
    if not isinstance(version, str) or not is_valid_version(version):
        return None, f"{_MANIFEST_FILENAME}'s identity.version is not MAJOR.MINOR.PATCH: {version!r}"
    return version, None


def _artifact_digest(module_dir: Path) -> str | None:
    """``manifest.artifact.digest`` for a compiled module, or ``None`` when the manifest cannot say.

    Tri-state, and read field by field out of the JSON, for the same two reasons as its neighbours:
    an unreadable manifest is *unknown* rather than *no digest*, and validating the whole
    ``ModuleManifest`` to reach one string would let an unrelated model defect withhold a value that
    is right there and legible.
    """
    path = module_dir / _MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    artifact = document.get("artifact") if isinstance(document, dict) else None
    digest = artifact.get("digest") if isinstance(artifact, dict) else None
    return digest if isinstance(digest, str) and digest else None


def _attested_parquets(module_dir: Path) -> list[str] | None:
    """The parquets ``manifest.artifact.files`` names, or ``None`` when the manifest cannot say.

    Tri-state, like ``_module_version`` beside it and for the same reason: a missing or unreadable
    manifest is *unknown*, not *attests nothing*, and an unknown withholds rather than refusing. Read
    field by field out of the JSON rather than through ``read_manifest`` — an unrelated model defect
    must not be able to turn a legible file list into a failed publish.
    """
    path = module_dir / _MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    artifact = document.get("artifact") if isinstance(document, dict) else None
    entries = artifact.get("files") if isinstance(artifact, dict) else None
    if not isinstance(entries, list):
        return None
    return [
        entry["name"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    ]


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

    **What it refuses is three positive rules, not one required list (RM89).** The old rule demanded
    the three SNP-core parquets, which RM2 made optional four releases ago, so seven of the sixteen
    reference examples could not be published at all. In their place, ordered most specific first so a
    refusal names the actual fault:

    1. **The plan carries everything the artifact attests.** `manifest.artifact.files` states a name,
       a sha256 and a size per parquet, and `artifact.digest` is a Merkle root over exactly those — so
       a file attested and not sent makes the published manifest a false claim about bytes that are not
       there. This is the general guard, and it is a self-check as much as a module check: it fires if
       this publisher's allowlist ever falls behind the compiler's output list again.
    2. **`weights.parquet` never travels alone.** A SNP core compiles to all three, so a missing
       `annotations`/`studies` beside it is an interrupted compile.
    3. **At least one lead table.** A directory with a manifest, a readme and no annotation rows is not
       a module; publishing one is the silent failure a bare widening of the old rule would have
       produced, and it is what discovery would then be unable to see.
    """
    resolved_repo = repo_id or DEFAULT_REPO_ID
    present = [f for f in _ALLOW_PATTERNS if (module_dir / f).exists()]
    attested = _attested_parquets(module_dir)
    unsent = [] if attested is None else [f for f in attested if f not in present]
    if unsent:
        raise FileNotFoundError(
            f"{name}: {_MANIFEST_FILENAME} attests {unsent} but the upload would not carry "
            f"{'it' if len(unsent) == 1 else 'them'} — `artifact.digest` is computed over the "
            f"attested files, so what arrives could not be verified against the manifest that "
            f"describes it. Re-compile {module_dir} if the file is missing."
        )
    if "weights.parquet" in present:
        half = [f for f in _EXPECTED_WITH_WEIGHTS if f not in present]
        if half:
            raise FileNotFoundError(
                f"{name}: missing compiled artifact(s) {half} in {module_dir} beside "
                f"weights.parquet — a SNP core compiles to all three, so this directory is a "
                f"half-finished compile. Re-run `just-dna-enricher enrich-and-compile` "
                f"or `just-dna-compiler compile`."
            )
    if not any(f in LEAD_PARQUETS for f in present):
        raise FileNotFoundError(
            f"{name}: no annotation table in {module_dir} — a module carries at least one of "
            f"{list(LEAD_PARQUETS)}. Compile the module first (e.g. "
            f"`just-dna-enricher enrich-and-compile` or `just-dna-compiler compile`)."
        )
    flat = f"data/{name}"
    version, reason = _module_version(module_dir)
    return UploadPlan(
        module=name,
        repo_id=resolved_repo,
        path_in_repo=flat,
        versioned_path_in_repo=None if version is None else f"{flat}/v{version}",
        version_unknown_reason=reason,
        files=present,
    )


def _versioned_digest_conflict(api, plan: "UploadPlan", local_digest: str | None) -> str | None:
    """The remote `artifact.digest` already at the versioned path when it **differs** — else ``None``.

    RM88's comparator, and the four outcomes are the whole of the gate:

    - **no versioned path** (the module states no version) — nothing addressable to collide with;
    - **the path is not there** — the first publish of this version, which is the normal case;
    - **it is there and the digests agree** — the same release arriving twice. This must *proceed*,
      and it is the case a naive existence check would break: `upload_module` writes two commits and
      documents a re-run as the recovery when the second fails, so refusing on presence alone would
      refuse exactly the retry the design depends on;
    - **it is there and the digests differ** — the collision. `None` is not returned, and the caller
      refuses unless `--force`.

    **An unknown proceeds, with a warning, and that is a decision rather than an oversight.** If the
    remote manifest cannot be read — a flake, a repo that answers but has no manifest at that path —
    nothing established a collision, so nothing may assert one; the house algebra withholds. Failing
    *closed* here would make every network hiccup demand `--force`, which trains an author to pass it
    by default and turns a gate into one people route around. That is the failure the policy decision
    was explicitly trying to avoid, so it must not be reintroduced by the error path.

    Reads the remote `manifest.json` rather than comparing per-file hashes: `artifact.digest` is a
    Merkle root over exactly the attested files, so one small download answers the question that a
    tree listing could only answer for whatever happens to be LFS-backed.
    """
    if plan.versioned_path_in_repo is None or local_digest is None:
        return None
    remote_manifest = f"{plan.versioned_path_in_repo}/{_MANIFEST_FILENAME}"
    try:
        from huggingface_hub import hf_hub_download

        if not api.file_exists(
            repo_id=plan.repo_id, filename=remote_manifest, repo_type="dataset"
        ):
            return None
        local_copy = hf_hub_download(
            repo_id=plan.repo_id,
            filename=remote_manifest,
            repo_type="dataset",
            token=api.token,
        )
        published = json.loads(Path(local_copy).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — every failure here is the same unknown; see the docstring
        logger.warning(
            "Could not read the published manifest at %s (%s); publishing without the "
            "already-published check. Nothing established a collision, so nothing asserts one.",
            remote_manifest, exc,
        )
        return None
    artifact = published.get("artifact") if isinstance(published, dict) else None
    remote_digest = artifact.get("digest") if isinstance(artifact, dict) else None
    if not isinstance(remote_digest, str) or not remote_digest:
        return None
    return None if remote_digest == local_digest else remote_digest


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

    **The two writes are two commits, not one.** `upload_folder` commits per call, so a reader can
    briefly see the flat path refreshed while the versioned copy is not there yet; the flat path goes
    first because it is the one anything reads today. Making it atomic means `create_commit` over an
    explicit operation list, which is a different shape from the allow-pattern plumbing every publish
    here uses, and it was not worth holding the fix for. If the second call fails the first has already
    landed — `data/<name>/` is the new release and the versioned copy is absent until a re-run, which
    is idempotent.

    **The versioned path refuses to be overwritten with different bytes (RM88).** Before either
    write, the published `manifest.json` at `data/<name>/v<version>/` is read and its
    `artifact.digest` compared with this module's. A different digest is a `PublishCollisionError`
    unless `force=True`. The flat path is deliberately **not** guarded: it means *latest*, so
    overwriting it is what it is for, and the whole point of the versioned copy is that it does not.

    The policy is refuse-unless-`--force` rather than warn-and-proceed or refuse-outright, decided
    2026-08-18. The flag's existence is itself the claim that overwriting is sometimes right — a
    curator re-cutting a draft release is a real workflow, and a gate with no override becomes a gate
    people route around.

    **Recompiling under a newer compiler also moves the digest**, and will trip this. That is correct
    rather than a false positive: P4 scopes byte-reproducibility to a fixed `compiler_version`, so the
    versioned path really would come to hold different bytes than the ones it was published with. The
    refusal says so, because "I changed nothing" is the first thing its first user will think.

    Raises PermissionError if no token is available and ImportError if huggingface_hub is absent.
    """
    plan = plan_upload(module_dir, name, repo_id)
    api = ensure_repo(plan.repo_id, token)
    published_digest = None if force else _versioned_digest_conflict(
        api, plan, _artifact_digest(module_dir)
    )
    if published_digest is not None:
        raise PublishCollisionError(
            f"{name}: {plan.versioned_path_in_repo}/ is already published with a different artifact "
            f"({published_digest[:19]}… there, {_artifact_digest(module_dir)[:19]}… here), so this "
            f"upload would replace the bytes that version names. Bump `version:` in "
            f"module_spec.yaml and re-compile to publish this as a new release, or pass --force to "
            f"overwrite it deliberately. Note that recompiling an unchanged spec under a newer "
            f"compiler moves the digest too — if that is what happened, this refusal is still "
            f"protecting the bytes the published version was cut from."
        )
    api.upload_folder(
        folder_path=str(module_dir),
        path_in_repo=plan.path_in_repo,
        repo_id=plan.repo_id,
        repo_type="dataset",
        allow_patterns=_ALLOW_PATTERNS,
        commit_message=commit_message or f"Add {name} module",
    )
    if plan.versioned_path_in_repo is not None:
        segment = plan.versioned_path_in_repo.rsplit("/", 1)[-1]
        api.upload_folder(
            folder_path=str(module_dir),
            path_in_repo=plan.versioned_path_in_repo,
            repo_id=plan.repo_id,
            repo_type="dataset",
            allow_patterns=_ALLOW_PATTERNS,
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
            raise FileNotFoundError(
                f"no {payload} in {snapshot_dir} — build the snapshot first "
                f"(e.g. `just-dna-enricher strchive build`)"
            )
        files = [payload]
        for name in (RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME):
            if (snapshot_dir / name).is_file():
                files.append(name)
        return SnapshotPlan(repo_id=resolved_repo, files=files)
    data_dir = snapshot_dir / SNAPSHOT_DATA_DIRNAME
    parquet = sorted(p.name for p in data_dir.glob("*.parquet")) if data_dir.is_dir() else []
    if not parquet:
        raise FileNotFoundError(
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
    for name in (RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME):
        if (snapshot_dir / name).is_file():
            files.append(name)
    return SnapshotPlan(repo_id=resolved_repo, files=files)


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
    api.upload_folder(
        folder_path=str(snapshot_dir),
        path_in_repo="",
        repo_id=plan.repo_id,
        repo_type="dataset",
        # Derived from the plan rather than restated as a pattern list. The two had to agree and did
        # not: `--dry-run` printed a file the patterns then dropped, which is the failure mode that
        # lost `citations/` and `LICENSE.txt` in the first place. One list, computed once, so what a
        # dry run promises is exactly what an upload sends (`@publisher-allowlist-derived`).
        allow_patterns=list(plan.files),
        commit_message=commit_message or f"Publish reference snapshot ({len(plan.files)} files)",
    )
    return plan
