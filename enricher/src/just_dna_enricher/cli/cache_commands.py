"""The `cache` group: status, pull, prepare, prune and rebuild over `caches.CACHE_LANES` (RM260 split
this out of the former single-file `cli.py`).
"""

import tempfile
from collections.abc import Callable
from pathlib import Path

import huggingface_hub
import typer
from just_dna_format.snapshot import holds_snapshot_payload
from just_dna_format.snapshot import release_label as snapshot_release_label
from just_dna_format.vocab import VALID_DECLARED_USE

from just_dna_enricher import ipd_imgt_hla_build
from just_dna_enricher.caches import (
    _PINNABLE,
    CACHE_LANES,
    CacheLane,
    RebuildOutcome,
    RebuildRequest,
    _ensure_declaration,
    _gate,
    _named_only_detail,
    _rebuild_blocked,
    _rebuild_detail,
    _unpinnable,
    lane_name,
    lane_status,
    parents_from_rebuild_dir,
    prepare_caches,
    rebuild_lane,
)
from just_dna_enricher.cli._shared import _use
from just_dna_enricher.download import SnapshotNotPublished, _FollowHub, _named_groups
from just_dna_enricher.licensing import LicenseRefusal, check_declared_use
from just_dna_enricher.locations import CACHES_DIRNAME, RELEASE_FILENAME, repro_out

#: Why `cache rebuild --rehearse-download` is refused without `--dry-run` and `--publish` (RM412). Pinned
#: by a test, because a refusal's reason is what the operator acts on (`@warning-text-is-api`). The
#: flags still missing follow it as `Missing: …`.
REHEARSE_DOWNLOAD_REFUSAL = (
    "--rehearse-download rehearses a publish: it downloads and builds each lane for real, then rehearses "
    "the upload without sending it. It needs --dry-run (without it the upload would be real) and --publish "
    "(without it there is no upload to rehearse)."
)

#: Why `cache pull --groups` is refused beside any lane but `ensembl` (RM437), pinned by a test. Groups
#: are the split Ensembl release's alone, and with no `--only` the selection is every lane.
GROUPS_NEED_ENSEMBL_ONLY = (
    "--groups selects groups of the ensembl lane, so it is refused beside any other lane; with no --only "
    "every lane is selected. Pass --only ensembl."
)

# ── the caches (pre-provision, rebuild, and say what is where) ──────────────────────────────────
#
# The roster this chapter reads is `caches.CACHE_LANES`, not a table here. It was a four-tuple list in
# this file, and a list is only as complete as whoever last edited it: three lanes were missing from
# it, so `cache status` reported nine caches on a machine that has twelve and `cache pull` could not
# be asked about the other three at all. The registry is walked by a test against the `*_build`
# modules on disk, which a table in a CLI module never was (`@registry-completeness`).

#: The lanes a bare `cache rebuild` passes over, derived from the registry for `--only`'s help (RM431).
_NAMED_ONLY = ", ".join(lane.name for lane in CACHE_LANES if lane.named_only is not None)

cache_app = typer.Typer(
    add_completion=False,
    help="Pre-provision, rebuild and report the snapshot caches.",
    no_args_is_help=True,
)


ipd_imgt_hla_app = typer.Typer(no_args_is_help=True)


@ipd_imgt_hla_app.command("build")
def ipd_imgt_hla_build_(
    out: Path = typer.Option(repro_out("ipd_imgt_hla"), "--out", file_okay=False),
    pin: str = typer.Option(ipd_imgt_hla_build.DEFAULT_PIN, "--pin", help="Numeric release, e.g. 3.66.0."),
    source: Path | None = typer.Option(
        None,
        "--source",
        exists=True,
        dir_okay=False,
        help="Local Allelelist.txt beside Deleted_alleles.txt and LICENCE.md.",
    ),
    use: str = typer.Option("unstated", "--use", help="Declared use for a fetch."),
) -> None:
    """Build the per-host IPD-IMGT/HLA allele-name snapshot."""
    try:
        label = ipd_imgt_hla_build.build_snapshot(out, pin=pin, source=source, declared_use=_use(use))
    except (ipd_imgt_hla_build.IpdHlaUnavailable, LicenseRefusal, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Built {label} in {out}")


def _lane_names() -> list[str]:
    return [lane.name for lane in CACHE_LANES]


def _selected(only: list[str]) -> tuple[set[str], list[CacheLane]]:
    """Resolve `--only` against the registry, refusing a name nothing answers to.

    A hyphen is accepted where the declared member has an underscore and the **declared** member is
    what comes back — `drug-labels` and `mitomap-miss` are both spellings an operator writes, and the
    second is the one this repository's own design note uses.
    """
    wanted: set[str] = set()
    unknown: list[str] = []
    for raw in only:
        if not raw.strip():
            continue
        resolved = lane_name(raw)
        if resolved is None:
            unknown.append(raw.strip())
            continue
        wanted.add(resolved)
    if unknown:
        raise typer.BadParameter(f"unknown cache(s) {sorted(unknown)}. Known: {_lane_names()}")
    return wanted, [lane for lane in CACHE_LANES if not wanted or lane.name in wanted]


def _pairs(values: list[str], flag: str, *, must_exist: bool = False) -> dict[str, str]:
    """`lane=value` pairs for the per-lane flags, checked against the registry as they are read.

    `must_exist` is for `--source`, whose values are paths. Typer checks `exists=True` on a plain
    `Path` option and cannot on one embedded in a `lane=value` string, so the check moves here — a
    mistyped path otherwise reaches the lane's builder and surfaces as a bare `[Errno 2] No such file
    or directory` **after** everything before it in the run has already downloaded, which is a long
    way to travel for a typo (`@specific-rejection`).
    """
    out: dict[str, str] = {}
    for item in values:
        name, sep, value = item.partition("=")
        if not sep or not value:
            raise typer.BadParameter(f"{flag} takes lane=value, got {item!r}")
        resolved = lane_name(name)
        if resolved is None:
            raise typer.BadParameter(f"{flag} names no known cache: {name!r}. Known: {_lane_names()}")
        name = resolved
        if must_exist and not Path(value).expanduser().is_file():
            raise typer.BadParameter(
                f"{flag} {name}={value} is not a readable file. This is an input you supply, so "
                f"nothing will fetch it — check the path before the run starts."
            )
        if flag == "--pin" and name not in _PINNABLE:
            # Refused before the run, not as one lane's failure after the others downloaded (RM416).
            raise typer.BadParameter(_unpinnable(name))
        out[name] = value
    return out


@cache_app.command("status")
def cache_status_() -> None:
    """Say which snapshots are present, where, and which release each holds.

    Reads only: nothing is downloaded, so this is safe on a machine with no network and it is the first
    thing to run when a pass reports that a source was skipped.
    """
    # Rendered from `lane_status`, the registry's own projection, so a consumer serving the same
    # answer over HTTP reads the same function rather than re-deriving this loop (S91, RM204).
    for status in lane_status():
        lane = status.lane
        publish_note = f" — {lane.unpublished}" if lane.per_host else ""
        if status.state == "absent":
            # The lane's own command, taken from the registry rather than composed from its name:
            # two lanes are not `<name> build` (`clinpgx build-labels`, `gnomad constraint build`)
            # and a convention that holds for ten of twelve prints two commands nobody can run.
            # A lane with both routes names both (RM395): this command reads only, so it cannot see
            # whether the lane's repo has anything published, and `clinvar_gkm`'s has not.
            routes = (["`cache pull`"] if lane.ensure is not None else []) + (
                [f"`{lane.build_command}`"] if lane.build_command is not None else []
            )
            how = " or ".join(routes)
            # A lane built only when named says so, with the build where it is read (RM431): `cache
            # prepare` will not build it, and a bare `cache rebuild` writes under its own `--out`.
            provision = (
                _named_only_detail(lane, status.looked_in)
                if lane.named_only is not None
                else f"provision with {how}"
            )
            typer.secho(
                f"  {lane.name:13} absent   — {lane.serves}; {provision}{publish_note}",
                fg=typer.colors.YELLOW,
            )
            continue
        if status.state == "occupied":
            # Neither present nor absent: something is at the place the lane looks and it is not a
            # snapshot. A pull or build will be refused here (`prepare` never deletes), so the line
            # says what to do instead of pointing at a command that will decline.
            typer.secho(
                f"  {lane.name:13} occupied {status.looked_in} holds no {lane.name} snapshot; "
                f"move it aside (or `cache prune --only {lane.name}` if it is a retired file)",
                fg=typer.colors.RED,
            )
            continue
        # Present and unreadable is not the same as absent, and a provenance failure is not a data
        # failure — the snapshot is still usable, so this says so instead of hiding it.
        label = status.release or ("(unreadable release.json)" if status.release_unreadable else "")
        size = f"{(status.size_bytes or 0) / 1e6:.1f} MB"
        if status.state == "stale":
            # On disk, and refused by its readers: its parents moved under it (review round 1, item 11).
            typer.secho(
                f"  {lane.name:13} stale    {status.path}  {label}  {size} — {status.stale}; "
                f"{_rebuild_detail(lane, status.looked_in)}",
                fg=typer.colors.YELLOW,
            )
            continue
        typer.secho(
            f"  {lane.name:13} present  {status.path}  {label}  {size}{publish_note}", fg=typer.colors.GREEN
        )


def _echo_groups(lane: str, follow: _FollowHub) -> None:
    """One line per group the lane's `ensure` looked at (RM437), on the success path and the failure paths alike."""
    for group, outcome in follow.groups.items():
        plain = outcome in ("pulled", "current")
        typer.secho(
            f"  {lane} group {group}: {outcome}",
            fg=typer.colors.GREEN if plain else typer.colors.YELLOW,
            err=not plain,
        )


@cache_app.command("pull")
def cache_pull_(
    only: list[str] = typer.Option(
        [],
        "--only",
        help="Pull just these caches (repeatable). Default: every publishable one.",
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=(
            "Declared use for the licence-gated snapshots. They forbid sale, so they are SKIPPED "
            "when unstated and REFUSED when commercial — downloading is taking the data."
        ),
    ),
    groups: list[str] = typer.Option(
        [],
        "--groups",
        help=(
            "With --only ensembl: optional column groups of the split release to pull beside the core "
            "(NAME[,NAME], repeatable), names from its manifest. Each is gated by its own licence, as the "
            "gated lanes are by --use; a group once pulled is re-pulled whenever the core's release moves."
        ),
    ),
) -> None:
    """Provision local caches from their registered sources.

    The provisioning step a hosted deployment runs, so no pass ever reaches a source live per request.
    IPD-IMGT/HLA fetches a missing pinned release directly from the curators and reuses it thereafter.
    A Hub cache already here is compared with the release its repo publishes, one small read per lane
    (RM420): a cache that came from a pull of that repo and holds another release is re-pulled, and one
    built on this machine is left alone and named with both labels, since it may not be uploaded yet.
    So this is re-runnable and cheap; an interrupted pull fetches only what it lacks, and a truncated
    file is removed and refetched (RM339). When the hub cannot be read, the cache serves as it is.
    `enrich` never reads the hub for a cache that is already whole.

    A lane with nothing published says so and names its reason, which is a field on the registry
    rather than a comment: PharmVar's and PubMind's are refusals, ACMG's and MANE's are permissions
    nobody has established. Build those with `cache rebuild`.

    `--groups` (RM437) pulls optional column groups of the split Ensembl release into the lane's
    `groups/`, attested by its manifest and recorded in its pull record; readers take a group's path
    from `locations.ensembl_group_dir`. `core` is not a group, and `--groups` is refused beside any lane
    but `ensembl`, both before anything is read.
    """
    declared = _use(use)
    wanted, lanes = _selected(only)
    try:
        named_groups = list(_named_groups([name for item in groups for name in item.split(",")]))
    except ValueError as exc:  # `core`, refused by the provisioner's own rule before anything runs
        raise typer.BadParameter(str(exc), param_hint="--groups") from exc
    if named_groups and wanted != {"ensembl"}:
        raise typer.BadParameter(GROUPS_NEED_ENSEMBL_ONLY, param_hint="--groups")
    failures = 0
    # What this run left on disk and what it found unpublished, for the closing line (RM395): it
    # listed every lane with a pull route, so an unpublished lane was called available.
    on_disk: list[str] = []
    not_published: list[str] = []
    for lane in lanes:
        if lane.ensure is None:
            if lane.name in wanted:  # asked for by name, so say why it is not coming
                typer.secho(f"  {lane.name}: {lane.unpublished}", fg=typer.colors.YELLOW, err=True)
            continue
        if lane.terms is not None:
            # The terms are accepted when the data is TAKEN, and a download is taking it.
            try:
                reason = check_declared_use(lane.terms, declared)
            except LicenseRefusal as exc:
                typer.secho(f"  {lane.name}: REFUSED — {exc}", fg=typer.colors.RED, err=True)
                failures += 1
                continue
            if reason is not None:
                typer.secho(f"  {lane.name}: skipped — {reason}", fg=typer.colors.YELLOW, err=True)
                continue
        follow = _FollowHub(lane.release_label)
        # The Ensembl lane's groups (RM437): the named ones, and the declaration a recorded one is
        # re-pulled under when this run states one.
        extra = {
            **_ensure_declaration(lane, declared),
            # Only the Ensembl lane runs when groups are named (`GROUPS_NEED_ENSEMBL_ONLY`, refused above).
            **({"groups": named_groups} if named_groups else {}),
        }
        try:
            path = lane.ensure(**extra) if lane.per_host else lane.ensure(_follow_hub=follow, **extra)
        except LicenseRefusal as exc:
            typer.secho(f"  {lane.name}: REFUSED — {exc}", fg=typer.colors.RED, err=True)
            _echo_groups(lane.name, follow)
            failures += 1
            continue
        except SnapshotNotPublished as exc:
            # Asked, and absent. Not a failure and not counted as one: three lanes gained an
            # `ensure_*` before anyone created their repos, and a provisioning command that exits 1
            # on a fresh machine because a snapshot has never been published is reporting the state
            # of the world, not an error (`@unreachable-not-absent`).
            typer.secho(f"  {lane.name}: not published yet — {exc}", fg=typer.colors.YELLOW, err=True)
            not_published.append(lane.name)
            continue
        except Exception as exc:
            typer.secho(f"  {lane.name}: FAILED — {exc}", fg=typer.colors.RED, err=True)
            # A named group's failure is raised after every group was tried: the others' outcomes too.
            _echo_groups(lane.name, follow)
            failures += 1
            continue
        # Both labels, when the hub's release and the cache's were compared and the answer is news
        # (RM420): re-pulled, left alone because it was built here, or the hub could not be read.
        note = follow.note()
        quiet = follow.outcome in (None, "current", "refreshed")
        typer.secho(
            f"  {lane.name}: {path}" + (f" — {note}" if note else ""),
            fg=typer.colors.GREEN if quiet else typer.colors.YELLOW,
        )
        _echo_groups(lane.name, follow)
        on_disk.append(lane.name)
    if failures:
        raise typer.Exit(code=1)
    summary = f"on disk: {', '.join(sorted(on_disk))}" if on_disk else "nothing pulled"
    if not_published:
        summary += f"; nothing published for: {', '.join(sorted(not_published))}"
    typer.echo(summary)


@cache_app.command("prepare")
def cache_prepare_(
    only: list[str] = typer.Option(
        [],
        "--only",
        help="Prepare just these caches (repeatable). Default: every one.",
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=f"Declared use: one of {sorted(VALID_DECLARED_USE)}.",
    ),
    pin: list[str] = typer.Option(
        [],
        "--pin",
        help="lane=release, repeatable, for the lanes that are built rather than pulled.",
    ),
    source: list[str] = typer.Option(
        [],
        "--source",
        help="lane=path, repeatable: build from a file you already hold.",
    ),
) -> None:
    """Leave this machine with every cache it can have — pull what is published, build what is not.

    **The complement of `cache pull`, and the one command a deployment actually wants.** `pull`
    fetches the published snapshots and stops; four lanes are not published *for recorded reasons* —
    PharmVar's personal key, PubMind's NoDerivatives, NCBI's policy over MANE, ACMG's supplementary
    material — so a machine that only pulled is missing four caches and the checks that read them
    skip themselves. This runs each lane by the route it has.

    The registry selects the route. A published lane pulls its snapshot. A per-host lane acquires
    its tagged release from the curators. Other buildable lanes use their local builder.

    **A cache that is already present is left alone** unless it came from a pull and its repo now
    publishes another release, exactly as `cache pull` treats one (RM420), so this is idempotent and
    cheap to re-run. Re-cutting a snapshot that exists is `cache rebuild`,
    which writes somewhere else on purpose — a build straight into a live cache is visible half-done
    to anything reading it, and a short parquet still has a footer.

    The Python counterpart is `just_dna_enricher.caches.prepare_caches`, which this calls.
    """
    _, lanes = _selected(only)
    outcomes = prepare_caches(
        lanes,
        declared_use=_use(use),
        pins=_pairs(pin, "--pin"),
        sources={k: Path(v).expanduser() for k, v in _pairs(source, "--source", must_exist=True).items()},
    )
    for outcome in outcomes:
        colour = {
            True: typer.colors.GREEN,
            False: typer.colors.RED,
            None: typer.colors.YELLOW,
        }[outcome.ready]
        typer.secho(
            f"  {outcome.lane:11} {outcome.label:10} {outcome.detail}",
            fg=colour,
            err=outcome.ready is not True,
        )
    ready = [o for o in outcomes if o.ready is True]
    failed = [o for o in outcomes if o.ready is False]
    typer.echo(
        f"{len(ready)} of {len(outcomes)} cache(s) ready "
        f"({sum(o.route == 'pulled' for o in ready)} pulled, "
        f"{sum(o.route == 'built' for o in ready)} built, "
        f"{sum(o.route == 'present' for o in ready)} already there). "
        f"Run `cache status` to confirm."
    )
    if failed:
        raise typer.Exit(code=1)


@cache_app.command("prune")
def cache_prune_(
    only: list[str] = typer.Option(
        [],
        "--only",
        help="Prune just these caches (repeatable). Default: every published one.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Delete without asking. Without it this prints the plan and stops.",
    ),
) -> None:
    """Say what a published snapshot repo carries that its lane is not made of, and offer to delete it.

    **Deletion is never a side effect of publishing, and this is the command that makes that
    affordable** (RM186). A published repo accumulates: the publisher adds and does not remove, so a
    layout change leaves the old spelling in place, and `just-dna-seq/clinvar` still carries the
    159 MB single-file `clinvar.parquet` from before the per-chromosome split. Provisioning already
    refuses to download it — the glob is what defends this tier — but any consumer globbing
    `data/*.parquet`, the dataset viewer included, still gets two schemas under one relation.

    **Nothing here is a sweep.** A file is a candidate only if the lane's own glob excludes it or a
    `LayoutShift` declares it retired; `README.md`, `.gitattributes`, `release.json`, `LICENSE.txt`
    and sidecar directories are never touched. Without `--yes` this reads and prints and does nothing
    else, which is the mode to run first.
    """
    from just_dna_enricher.download import SNAPSHOT_FILE_GLOBS
    from just_dna_enricher.locations import SNAPSHOT_DATA_DIRNAME
    from just_dna_enricher.upload import PublishRefused, plan_prune, prune_repo

    _, lanes = _selected(only)
    planned = 0
    for lane in lanes:
        if lane.publish_repo is None:
            typer.secho(
                f"  {lane.name:13} skipped  — {lane.unpublished or 'published elsewhere'}",
                fg=typer.colors.YELLOW,
            )
            continue
        glob = SNAPSHOT_FILE_GLOBS.get(lane.name)
        if glob is None:
            # STRchive's snapshot is one JSON at the repo root: there is no `data/` for a file to be
            # outside of, so there is nothing this command can name. Said rather than skipped
            # silently, because "prune found nothing" and "prune cannot look" are different answers.
            typer.secho(
                f"  {lane.name:13} n/a      — this snapshot has no {SNAPSHOT_DATA_DIRNAME}/ "
                f"to be made of anything",
                fg=typer.colors.YELLOW,
            )
            continue
        try:
            plan = plan_prune(lane.publish_repo, glob)
        except Exception as exc:
            typer.secho(
                f"  {lane.name:13} FAILED   — could not read {lane.publish_repo}: {exc}",
                fg=typer.colors.RED,
                err=True,
            )
            continue
        if not plan.candidates:
            typer.secho(f"  {lane.name:13} clean    {lane.publish_repo}", fg=typer.colors.GREEN)
            continue
        planned += len(plan.candidates)
        typer.secho(
            f"  {lane.name:13} {len(plan.candidates)} file(s), {plan.total_bytes / 1e6:.1f} MB in "
            f"{lane.publish_repo}",
            fg=typer.colors.YELLOW,
        )
        for candidate in plan.candidates:
            size = "" if candidate.size is None else f" ({candidate.size / 1e6:.1f} MB)"
            typer.echo(f"      • {candidate.path}{size} — {candidate.reason}")
        if not yes:
            continue
        try:
            deleted = prune_repo(plan)
        except PublishRefused as exc:
            # The repo moved after this plan read it (RM386): nothing was deleted, and the list above
            # is no longer what the repo holds.
            typer.secho(f"      PRUNE REFUSED — {exc}", fg=typer.colors.RED, err=True)
            continue
        typer.secho(f"      deleted {deleted} file(s) from {lane.publish_repo}", fg=typer.colors.GREEN)
    if planned and not yes:
        typer.echo("Nothing was deleted. Re-run with --yes to remove the files listed above.")


@cache_app.command("rebuild")
def cache_rebuild_(
    out: Path = typer.Option(
        Path(CACHES_DIRNAME),
        "--out",
        file_okay=False,
        help=(
            "Base directory. Each lane is built into <base>/<lane>/, never in place. The default is "
            "under data/, which this workspace git-ignores wholesale."
        ),
    ),
    only: list[str] = typer.Option(
        [],
        "--only",
        help=(
            "Rebuild just these caches (repeatable). Default: every one that can be, except those built "
            f"only when named here ({_NAMED_ONLY})."
        ),
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=f"Declared use: one of {sorted(VALID_DECLARED_USE)}.",
    ),
    pin: list[str] = typer.Option(
        [],
        "--pin",
        help="lane=release, repeatable. e.g. --pin mane=1.5 --pin civic=2026-08-01.",
    ),
    source: list[str] = typer.Option(
        [],
        "--source",
        help=(
            "lane=path, repeatable: build from a file you already hold instead of downloading. "
            "Required for acmg; the offline off-switch for clinvar, constraint, clinpgx, "
            "drug_labels, pubmind and strchive. mane and civic take three files each and refuse it."
        ),
    ),
    publish: bool = typer.Option(
        False,
        "--publish",
        help="Also upload each rebuilt snapshot to its HuggingFace repo.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Download, build and upload nothing: say per lane what a run would do, the release this "
            "machine holds and, with --publish, the one published. A snapshot already built into "
            "<out>/<lane> (a run without --publish) has its upload rehearsed. The one exception is "
            "--rehearse-download, which downloads and builds for real."
        ),
    ),
    rehearse_download: bool = typer.Option(
        False,
        "--rehearse-download",
        help=(
            "With --dry-run --publish only: download and build each lane for real into <out>/<lane>, "
            "then rehearse its upload; nothing is uploaded. Refused without both. The prediction is the "
            "dry run's and no wider: an adapter that refuses on its own inputs (ACMG with no workbook, "
            "PharmVar with no key) prints `rehearsing:` and then `not run`."
        ),
    ),
) -> None:
    """Rebuild every cache this tier builds — acquire, convert, and optionally publish (RM176).

    **The one endpoint over eleven builders.** Each per-lane `X build` command stays, and this calls
    the same `download_*`/`build_*` functions they do, so there is one conversion algorithm with two
    callers rather than two that have to agree. What differs is only flag plumbing: a per-lane command
    offers the local-file inputs an operator holds, and a rebuild pass by definition holds none.

    **Every lane is built into `<base>/<lane>/`, never in place over a resolved cache.** A rebuild
    takes minutes and an `enrich` reading a half-written snapshot mid-flight would see a real but
    incomplete table — the failure a resolver cannot detect, because a short parquet is still a
    parquet. Point the caches at the new base when the run is done, or copy each directory across.

    **An outcome is three-valued.** ACMG needs a workbook that is Elsevier supplementary material,
    PharmVar a personal key, CIViC a release date to pin — none of those is a failure, and a nightly
    rebuild reporting errors for them would be reporting the licences working as designed. They are
    printed as *not run*, with the reason, and the exit code counts only real failures.
    """
    missing = [flag for flag, given in (("--dry-run", dry_run), ("--publish", publish)) if not given]
    if rehearse_download and missing:
        # Before every other check and before any lane: a refused rehearsal reads, writes and fetches
        # nothing, and `--publish` without `--dry-run` must never reach an upload.
        typer.secho(
            f"{REHEARSE_DOWNLOAD_REFUSAL} Missing: {', '.join(missing)}.", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=2)
    declared = _use(use)
    wanted, lanes = _selected(only)
    pins = _pairs(pin, "--pin")
    sources = _pairs(source, "--source", must_exist=True)

    def request_for(lane: CacheLane) -> RebuildRequest:
        return RebuildRequest(
            out_dir=out / lane.name,
            declared_use=declared,
            pin=pins.get(lane.name),
            source=Path(sources[lane.name]).expanduser() if lane.name in sources else None,
            parents=parents_from_rebuild_dir(lane, out),
            # A lane built only when named is not run unless `--only` names it (RM431).
            named=lane.name in wanted,
        )

    if rehearse_download:
        _rehearse_download(lanes, request_for, out)
        return
    if dry_run:
        _dry_run(lanes, request_for, out, publish=publish)
        return

    outcomes: list[RebuildOutcome] = []
    for lane in lanes:
        request = request_for(lane)
        outcome = rebuild_lane(lane, request)
        outcomes.append(outcome)
        colour = {
            True: typer.colors.GREEN,
            False: typer.colors.RED,
            None: typer.colors.YELLOW,
        }[outcome.built]
        typer.secho(
            f"  {lane.name:13} {outcome.label:8} {outcome.detail}",
            fg=colour,
            err=outcome.built is not True,
        )
        if outcome.built and publish:
            _publish_rebuilt(lane, outcome)

    built = [o for o in outcomes if o.built is True]
    failed = [o for o in outcomes if o.built is False]
    not_run = [o for o in outcomes if o.built is None]
    typer.echo(
        f"rebuilt {len(built)}, failed {len(failed)}, not run {len(not_run)} "
        f"of {len(outcomes)} lane(s) into {out}"
    )
    if failed:
        raise typer.Exit(code=1)


def _dry_run(
    lanes: list[CacheLane], request_for: Callable[[CacheLane], RebuildRequest], out: Path, *, publish: bool
) -> None:
    """What `cache rebuild` would do, reading only: no download, no build, no upload (RM411).

    The dry run used to run the whole rebuild and skip only the upload, so a rehearsal of
    `--only opentargets --publish` downloaded 22 GB into `<out>/opentargets/source/`. A dry run that
    writes is not one. Each lane gets the answer a real run would reach before taking any bytes, in
    the same words: *not run* from `_rebuild_blocked` (no adapter, a derived lane's parents missing)
    and *refused* or *skipped* from the declared-use gate, which the adapters run on the same terms
    `CacheLane.terms` names. Otherwise it says what would be built, from where, into which directory.

    Nothing published is compared here, only shown: the source's own newest release is not asked
    (that needs a probe per lane, parked in RM412; the liaison's table keeps it by hand). The upload's
    own checks need the built bytes, so they are rehearsed only when `<out>/<lane>` already holds a
    snapshot, from an earlier run without `--publish`. `--rehearse-download` is the opt-in that takes
    the bytes (`_rehearse_download`).
    """
    planned = 0
    for lane in lanes:
        blocked, request = _predicted(lane, request_for(lane))
        if blocked is not None:
            typer.secho(
                f"  {lane.name:13} {blocked.label:8} {blocked.detail}",
                fg=typer.colors.RED if blocked.built is False else typer.colors.YELLOW,
                err=True,
            )
            continue
        planned += 1
        typer.echo(f"  {lane.name:13} would build {_build_plan(request)}")
        typer.echo(f"      this machine: {_held_release(lane)}")
        if not publish:
            continue
        if lane.publish_repo is None:
            typer.secho(f"      not published — {lane.unpublished}", fg=typer.colors.YELLOW, err=True)
            continue
        typer.echo(f"      published at {lane.publish_repo}: {_published_release(lane.publish_repo)}")
        built = request.out_dir
        if not holds_snapshot_payload(built, payload_filename=lane.payload_filename):
            typer.echo(
                f"      the upload's checks need the built bytes: run without --publish to build into "
                f"{built}, then again with --publish --dry-run to rehearse it"
            )
            continue
        _rehearse_upload(lane, built, built_by="already at")
    typer.echo(
        f"dry run: {planned} of {len(lanes)} lane(s) would be built into {out}; nothing was downloaded, "
        "built or uploaded"
    )


def _rehearse_download(
    lanes: list[CacheLane], request_for: Callable[[CacheLane], RebuildRequest], out: Path
) -> None:
    """`cache rebuild --dry-run --publish --rehearse-download`: the real download and build, a rehearsed upload (RM412).

    The opt-in inverse of RM411, and the old dry run's behaviour asked for by name: each lane runs
    `rebuild_lane` exactly as a real run does, taking the source bytes and building into
    `<out>/<lane>` (over whatever an earlier run left there, as the real run does), and the upload is
    then rehearsed with `rehearse_reference_snapshot` (the plan and the orphan check, which read the
    repo and send nothing) where the real run would publish. Before a lane runs it prints the dry run's
    prediction (`rehearsing: …` and the release this machine holds), so the operator sees what is about
    to be taken; a lane the dry run predicts *not run*, *refused* or *skipped* prints only the real
    run's line. The prediction is the dry run's and no wider: an adapter that refuses on its own inputs
    (ACMG with no workbook) is predicted to run and then prints *not run*.

    The exit code is the real run's: 1 when a lane failed to build. An upload the rehearsal would refuse
    prints `WOULD BE REFUSED` and does not move it, as a refused publish does not move the real run's.
    """
    outcomes: list[RebuildOutcome] = []
    for lane in lanes:
        request = request_for(lane)
        predicted, resolved = _predicted(lane, request)
        if predicted is None:
            typer.echo(f"  {lane.name:13} rehearsing: {_build_plan(resolved)}")
            typer.echo(f"      this machine: {_held_release(lane)}")
        outcome = rebuild_lane(lane, request)
        outcomes.append(outcome)
        typer.secho(
            f"  {lane.name:13} {outcome.label:8} {outcome.detail}",
            fg={True: typer.colors.GREEN, False: typer.colors.RED, None: typer.colors.YELLOW}[outcome.built],
            err=outcome.built is not True,
        )
        if not outcome.built:
            continue
        if lane.publish_repo is None:
            typer.secho(f"      not published — {lane.unpublished}", fg=typer.colors.YELLOW, err=True)
            continue
        if outcome.out_dir is None:
            typer.secho(
                f"      not published — {lane.name} named no output directory", fg=typer.colors.RED, err=True
            )
            continue
        typer.echo(f"      published at {lane.publish_repo}: {_published_release(lane.publish_repo)}")
        _rehearse_upload(lane, outcome.out_dir, built_by="just built at")
    built = sum(o.built is True for o in outcomes)
    failed = sum(o.built is False for o in outcomes)
    not_run = sum(o.built is None for o in outcomes)
    typer.echo(
        f"rehearsal: rebuilt {built}, failed {failed}, not run {not_run} of {len(outcomes)} lane(s) into {out}; "
        "each lane rebuilt was fetched or read and built for real, and nothing was uploaded"
    )
    if failed:
        raise typer.Exit(code=1)


def _predicted(lane: CacheLane, request: RebuildRequest) -> tuple[RebuildOutcome | None, RebuildRequest]:
    """The outcome a real run reaches before taking any bytes, or `None`, and the request it would build from.

    `_rebuild_blocked` (no adapter, a derived lane's parents missing, an unpinnable pin) and then the
    declared-use gate on `CacheLane.terms`, which is the object each gated adapter passes (RM411).
    """
    blocked, resolved = _rebuild_blocked(lane, request)
    if blocked is None:
        blocked = _gate(lane.terms, resolved.declared_use, lane.name)
    return blocked, resolved


def _held_release(lane: CacheLane) -> str:
    """The release this machine's cache of `lane` states, `absent`, or that it states none."""
    held = lane.resolve()
    if held is None:
        return "absent"
    return lane.release_label(held) or "a snapshot stating no release"


def _build_plan(request: RebuildRequest) -> str:
    """What a lane would build, from where, into which directory: the dry run's and the rehearsal's words."""
    release = request.pin or "the lane's own release"
    if request.parents:
        origin = "from " + " and ".join(f"{name} at {path}" for name, path in request.parents.items())
    elif request.source is not None:
        origin = f"from {request.source}"
    else:
        origin = "downloading it"
    return f"{release}, {origin}, into {request.out_dir}"


def _rehearse_upload(lane: CacheLane, built: Path, *, built_by: str) -> None:
    """Rehearse the upload of the snapshot at `built` to the lane's repo: the plan and the orphan check, nothing sent."""
    from just_dna_enricher.upload import PublishRefused, rehearse_reference_snapshot

    try:
        plan = rehearse_reference_snapshot(built, lane.publish_repo, payload=lane.payload_filename)
    except (PublishRefused, PermissionError, ImportError) as exc:
        typer.secho(f"      WOULD BE REFUSED: {exc}", fg=typer.colors.RED, err=True)
        return
    typer.echo(
        f"      would upload {len(plan.files)} file(s) from the snapshot {built_by} {built} "
        f"({snapshot_release_label(built) or 'no release stated'}) to {plan.repo_id}"
    )


def _published_release(repo_id: str) -> str:
    """The release `repo_id`'s root `release.json` states, read alone: never the payload.

    Three answers kept apart (`@unreachable-not-absent`): a label, *nothing published* (the hub
    answers that the file or the repo is not there), and *could not ask*, which is never written as
    either. A repo that holds a `release.json` stating no label says so.
    """
    remote = f"datasets/{repo_id}/{RELEASE_FILENAME}"
    with tempfile.TemporaryDirectory() as scratch:
        try:
            huggingface_hub.HfFileSystem(token=None).get(remote, str(Path(scratch) / RELEASE_FILENAME))
        except FileNotFoundError:
            return "nothing published"
        except Exception as exc:  # a reporting boundary: any other failure is could-not-ask
            return f"could not ask ({type(exc).__name__})"
        return snapshot_release_label(Path(scratch)) or f"a {RELEASE_FILENAME} stating no release"


def _publish_rebuilt(lane: CacheLane, outcome: RebuildOutcome) -> None:
    """Upload one rebuilt snapshot, or say why this lane has nothing to upload to.

    A lane with no repo is not an error here: `--publish` means *publish what may be published*, and
    the registry's `unpublished` is the answer to why one is skipped. Refusing the whole run because
    PharmVar cannot be published would make the flag unusable on the set it was written for.
    """
    from just_dna_enricher.upload import PublishRefused, publish_reference_snapshot

    if lane.publish_repo is None:
        typer.secho(f"    not published — {lane.unpublished}", fg=typer.colors.YELLOW, err=True)
        return
    snapshot_dir = outcome.out_dir
    if snapshot_dir is None:
        typer.secho(
            f"    not published — {lane.name} named no output directory",
            fg=typer.colors.RED,
            err=True,
        )
        return
    try:
        plan = publish_reference_snapshot(snapshot_dir, lane.publish_repo, payload=lane.payload_filename)
    except (PublishRefused, PermissionError, ImportError) as exc:
        typer.secho(f"    PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        return
    typer.secho(f"    published → {plan.repo_id} ({len(plan.files)} files)", fg=typer.colors.GREEN)
