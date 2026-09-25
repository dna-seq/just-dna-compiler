"""The `cache` group: status, pull, prepare, prune and rebuild over `caches.CACHE_LANES` (RM260 split
this out of the former single-file `cli.py`).
"""

from pathlib import Path

import typer
from just_dna_format.vocab import VALID_DECLARED_USE

from just_dna_enricher.caches import (
    CACHE_LANES,
    CacheLane,
    RebuildOutcome,
    RebuildRequest,
    lane_name,
    lane_status,
    parents_from_rebuild_dir,
    prepare_caches,
    rebuild_lane,
)
from just_dna_enricher.cli._shared import _use
from just_dna_enricher.download import SnapshotNotPublished
from just_dna_enricher.licensing import LicenseRefusal, check_declared_use
from just_dna_enricher.locations import CACHES_DIRNAME, STRCHIVE_CATALOGUE_FILENAME

# ── the caches (pre-provision, rebuild, and say what is where) ──────────────────────────────────
#
# The roster this chapter reads is `caches.CACHE_LANES`, not a table here. It was a four-tuple list in
# this file, and a list is only as complete as whoever last edited it: three lanes were missing from
# it, so `cache status` reported nine caches on a machine that has twelve and `cache pull` could not
# be asked about the other three at all. The registry is walked by a test against the `*_build`
# modules on disk, which a table in a CLI module never was (`@registry-completeness`).

cache_app = typer.Typer(
    add_completion=False,
    help="Pre-provision, rebuild and report the snapshot caches.",
    no_args_is_help=True,
)


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
        if status.state == "absent":
            # The lane's own command, taken from the registry rather than composed from its name:
            # two lanes are not `<name> build` (`clinpgx build-labels`, `gnomad constraint build`)
            # and a convention that holds for ten of twelve prints two commands nobody can run.
            how = "`cache pull`" if lane.ensure is not None else f"`{lane.build_command}`"
            typer.secho(
                f"  {lane.name:13} absent   — {lane.serves}; provision with {how}",
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
        typer.secho(f"  {lane.name:13} present  {status.path}  {label}  {size}", fg=typer.colors.GREEN)


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
) -> None:
    """Download the published parquet snapshots from HuggingFace into the local caches.

    The provisioning step a hosted deployment runs **once**, so no pass ever reaches a source live per
    request. Already-complete caches are trusted without touching the network, so this is re-runnable
    and cheap; a truncated file is removed and refetched.

    A lane with nothing published says so and names its reason, which is a field on the registry
    rather than a comment: PharmVar's and PubMind's are refusals, ACMG's and MANE's are permissions
    nobody has established. Build those with `cache rebuild`.
    """
    declared = _use(use)
    wanted, lanes = _selected(only)
    failures = 0
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
        try:
            path = lane.ensure()
        except SnapshotNotPublished as exc:
            # Asked, and absent. Not a failure and not counted as one: three lanes gained an
            # `ensure_*` before anyone created their repos, and a provisioning command that exits 1
            # on a fresh machine because a snapshot has never been published is reporting the state
            # of the world, not an error (`@unreachable-not-absent`).
            typer.secho(f"  {lane.name}: not published yet — {exc}", fg=typer.colors.YELLOW, err=True)
            continue
        except Exception as exc:
            typer.secho(f"  {lane.name}: FAILED — {exc}", fg=typer.colors.RED, err=True)
            failures += 1
            continue
        typer.secho(f"  {lane.name}: {path}", fg=typer.colors.GREEN)
    if failures:
        raise typer.Exit(code=1)
    pullable = sorted(lane.name for lane in CACHE_LANES if lane.ensure is not None)
    typer.echo(f"caches available: {', '.join(pullable)}. Run `cache status` to confirm.")


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
    PharmVar's personal key, PubMind's absent terms, NCBI's policy over MANE, ACMG's supplementary
    material — so a machine that only pulled is missing four caches and the checks that read them
    skip themselves. This runs each lane by the route it has.

    **The route is a property of the lane, never a flag.** A published lane pulls, because building
    it would spend an operator's bandwidth re-deriving bytes somebody already made; an unpublished
    one builds, because that is the only route there will ever be. Asking for the choice would be
    asking an operator to restate the licensing story.

    **A cache that is already present is left alone**, exactly as `cache pull` leaves one alone, so
    this is idempotent and cheap to re-run. Re-cutting a snapshot that exists is `cache rebuild`,
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
    from just_dna_enricher.upload import plan_prune, prune_repo

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
        deleted = prune_repo(plan)
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
        help="Rebuild just these caches (repeatable). Default: every one that can be.",
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
        help="With --publish: show what would be uploaded, send nothing.",
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
    declared = _use(use)
    _, lanes = _selected(only)
    pins = _pairs(pin, "--pin")
    sources = _pairs(source, "--source", must_exist=True)

    outcomes: list[RebuildOutcome] = []
    for lane in lanes:
        request = RebuildRequest(
            out_dir=out / lane.name,
            declared_use=declared,
            pin=pins.get(lane.name),
            source=Path(sources[lane.name]).expanduser() if lane.name in sources else None,
            parents=parents_from_rebuild_dir(lane, out),
        )
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
            _publish_rebuilt(lane, outcome, dry_run=dry_run)

    built = [o for o in outcomes if o.built is True]
    failed = [o for o in outcomes if o.built is False]
    not_run = [o for o in outcomes if o.built is None]
    typer.echo(
        f"rebuilt {len(built)}, failed {len(failed)}, not run {len(not_run)} "
        f"of {len(outcomes)} lane(s) into {out}"
    )
    if failed:
        raise typer.Exit(code=1)


def _publish_rebuilt(lane: CacheLane, outcome: RebuildOutcome, *, dry_run: bool) -> None:
    """Upload one rebuilt snapshot, or say why this lane has nothing to upload to.

    A lane with no repo is not an error here: `--publish` means *publish what may be published*, and
    the registry's `unpublished` is the answer to why one is skipped. Refusing the whole run because
    PharmVar cannot be published would make the flag unusable on the set it was written for.
    """
    from just_dna_enricher.upload import (
        OrphanedSidecarError,
        check_publish_orphans_no_sidecar,
        plan_reference_snapshot,
        publish_reference_snapshot,
    )

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
    payload = STRCHIVE_CATALOGUE_FILENAME if lane.name == "strchive" else None
    try:
        if dry_run:
            plan = plan_reference_snapshot(snapshot_dir, lane.publish_repo, payload=payload)
            # The remote check runs here too: a dry run that skips what a publish refuses on is the
            # same defect as an allowlist that drops a file the dry run promised — it makes the
            # rehearsal a different operation from the thing (`@publisher-allowlist-derived`).
            check_publish_orphans_no_sidecar(plan)
            typer.echo(f"    would upload {len(plan.files)} file(s) to {plan.repo_id}: {plan.files}")
            return
        plan = publish_reference_snapshot(snapshot_dir, lane.publish_repo, payload=payload)
    except (FileNotFoundError, PermissionError, ImportError, OrphanedSidecarError) as exc:
        typer.secho(f"    PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        return
    typer.secho(f"    published → {plan.repo_id} ({len(plan.files)} files)", fg=typer.colors.GREEN)
