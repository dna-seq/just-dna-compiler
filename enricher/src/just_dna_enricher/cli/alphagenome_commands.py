"""The AlphaGenome surfaces: the `atlas` and `alphagenome` groups (RM260 split this out of the former
single-file `cli.py`).
"""

import os
from pathlib import Path

import typer

from just_dna_enricher.alphagenome_avi_build import KNOT_FILENAME, AlphaGenomeBuildError
from just_dna_enricher.alphagenome_avi_build import build_snapshot as build_alphagenome_snapshot
from just_dna_enricher.alphagenome_check import (
    DEFAULT_REFINEMENT_CAP,
    VariantImpactError,
    check_variant_impact,
)
from just_dna_enricher.atlas_protos import ATLAS_IMPORT_FAILURES, client_absence
from just_dna_enricher.cli._shared import _use
from just_dna_enricher.enrich import EnrichmentError
from just_dna_enricher.expression import DEFAULT_MAX_ROWS, ExpressionError, enrich_expression
from just_dna_enricher.expression import SIDECAR_NAME as EXPRESSION_SIDECAR
from just_dna_enricher.licensing import sidecar_path
from just_dna_enricher.locations import load_env, missing_credential_reason, repro_out
from just_dna_enricher.upload import DEFAULT_ALPHAGENOME_AVI_REPO_ID

# ── the AlphaGenome Atlas (RM192) ───────────────────────────────────────────────────────────────

atlas_app = typer.Typer(
    add_completion=False,
    help=(
        "The AlphaGenome Atlas — precomputed variant scores over gRPC. Needs the \\[atlas] extra "
        # `\[atlas]` escaped for Rich, which reads a bare `[word]` as a style tag and renders it as
        # nothing — this line printed "Needs the  extra" (RM221). "Vendored" was pre-RM196 text the
        # change did not sweep: the repository carries a pin, not the sources. 19 MB is the measured
        # figure in `pyproject.toml`; 22 MB was the grpcio release current at the design round.
        "(grpcio + protobuf, 19 MB); the bindings are generated from pinned Apache-2.0 "
        ".proto sources rather than committed, so `atlas generate` runs once per checkout."
    ),
    no_args_is_help=True,
)


@atlas_app.command("generate")
def atlas_generate_(
    refetch: bool = typer.Option(
        False,
        "--refetch",
        help="Re-download the pinned sources even if they are already on disk and match.",
    ),
) -> None:
    """Fetch the pinned Atlas `.proto` sources and generate the gRPC bindings from them.

    The sources are not vendored: the repository carries a commit id and a sha256 per file, and a
    file that does not match its pin is refused rather than used (RM196). Needs `grpcio-tools`,
    which is in `\\[dev]` and deliberately not in `\\[atlas]` — the runtime imports the bindings without
    it. A released wheel carries both the sources and the bindings already, so this is a checkout
    command.
    """
    from just_dna_enricher import atlas_protos

    try:
        if refetch:
            atlas_protos.fetch_protos(force=True)
        out = atlas_protos.generate()
    except atlas_protos.ProtoFetchError as exc:
        typer.secho(f"GENERATE FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except ImportError as exc:
        typer.secho(
            f"GENERATE FAILED: grpcio-tools is not installed ({exc}). It is build-time only and "
            "lives in the [dev] group: `uv sync` from a checkout, or `pip install grpcio-tools`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc
    typer.secho(f"bindings written to {out}", fg=typer.colors.GREEN)


# ── the AlphaGenome AVI snapshot (RM191) ────────────────────────────────────────────────────────

alphagenome_app = typer.Typer(
    add_completion=False,
    help=(
        "Re-encode AlphaGenome's AVI variant-impact scores into a cache lane. **Reads a file you "
        "already hold** — the artifact is 88.5 GB behind a sign-in whose eligibility clause bars "
        "classes of holder, so this never downloads."
    ),
    no_args_is_help=True,
)


@alphagenome_app.command("build")
def alphagenome_avi_build_(
    input_: Path = typer.Option(
        ...,
        "--input",
        exists=True,
        dir_okay=False,
        help=(
            "The extracted alphagenome_variant_impact_score_snvs.tsv.gz (its .tbi must be beside "
            "it). Required, and there is no default URL: acquisition is yours, under your own "
            "acceptance of the AlphaGenome Services Additional Terms."
        ),
    ),
    out: Path = typer.Option(
        repro_out("alphagenome_avi"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/alphagenome_avi-*.parquet, avi_knots.parquet, release.json, LICENSE.txt).",
    ),
    contig: list[str] = typer.Option(
        None,
        "--contig",
        help="Build only these contigs, repeatable. Omit for every contig the .tbi index knows.",
    ),
    workers: int = typer.Option(
        12,
        "--workers",
        min=1,
        help="How many contigs to read at once. Twelve ran 24 contigs in 41-46 minutes; one takes about four times as long.",
    ),
    no_hash: bool = typer.Option(
        False,
        "--no-hash",
        help="Skip the source sha256. It is a few minutes over 88.5 GB; release.json then records null, which is unknown rather than unpinned.",
    ),
) -> None:
    """Build the AVI snapshot from a local copy of the artifact.

    `raw_score` is stored as `Int32` at a scale of 10**5 — exactly lossless, since the artifact
    prints at most five decimals — and `PHRED` is **not** stored: it is a rank, a function of
    `raw_score`, and the 466 KB knot table beside the data reconstructs it while also carrying the
    per-value ambiguity interval a threshold has to be checked against.
    """
    try:
        result = build_alphagenome_snapshot(
            input_,
            out,
            contigs=list(contig) if contig else None,
            workers=workers,
            hash_source=not no_hash,
        )
    except AlphaGenomeBuildError as exc:
        typer.secho(f"BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"built {result.rows:,} rows over {len(result.contigs)} contig(s) into {out}",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        f"  {result.knots:,} knots, {result.negative_rows:,} negative scores, "
        f"{result.zero_rows:,} genuine zeros (absence is row-absence, never a zero)"
    )
    if result.dataset is None:
        typer.secho(
            "  the artifact's own timestamp could not be read, so release.json records no dataset. "
            "The Output Terms pin the applicable version to the date the Output was generated, so "
            "that date is worth recovering before the snapshot is relied on.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    typer.echo(
        "  AVI is Permissive Use — commercial and non-commercial (RM195, and the download page that "
        "says so is pinned in docs/vendor/). Sharing is the narrower question: redistribution rests "
        "on reading an open publication as prohibition 1's 'open source release', which is recorded "
        "as a reading rather than quoted from a clause."
    )


@alphagenome_app.command("check")
def alphagenome_check_(
    spec: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    reference: Path | None = typer.Option(
        None,
        "--reference",
        exists=True,
        file_okay=False,
        help="An AVI snapshot directory. Omit to use $JUST_DNA_ALPHAGENOME_AVI_CACHE.",
    ),
    threshold: float | None = typer.Option(
        None,
        "--threshold",
        help=(
            "A PHRED cut to check the module's variants against. Without one the pass is entirely "
            "offline: there is no question the local artifact cannot answer."
        ),
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Never reach the Atlas. Straddling variants are recorded as nobody-asked, not as decided.",
    ),
    refinement_cap: int = typer.Option(
        DEFAULT_REFINEMENT_CAP,
        "--refinement-cap",
        min=1,
        help="Refuse rather than refine more than this many variants over the network in one run.",
    ),
    strict: bool = typer.Option(False, "--strict", help="Carried for the report; see the docstring."),
) -> None:
    """Cross-check a module's variants against AlphaGenome's AVI scores. Reports, never repairs.

    The local snapshot answers most of it. The Atlas is asked only where the knot table says the
    local data genuinely cannot decide — a threshold falling inside a printed score's PHRED interval
    — and that set is computed offline, before any request is spent.
    """
    try:
        client = None
        if threshold is not None and not offline:
            client = _atlas_client_or_none()
        result = check_variant_impact(
            spec,
            reference=reference,
            client=client,
            threshold=threshold,
            mode="strict" if strict else "best_effort",
            offline=offline,
            refinement_cap=refinement_cap,
        )
    except VariantImpactError as exc:
        typer.secho(f"CHECK FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    for note in result.warnings:
        typer.secho(f"  {note}", fg=typer.colors.YELLOW, err=True)
    for finding in result.findings:
        typer.secho(f"  {finding}", fg=typer.colors.YELLOW)
    if result.straddling:
        typer.echo(
            f"  {len(result.straddling)} variant(s) sit inside a knot spanning PHRED "
            f"{threshold}; {len(result.refined)} refined against the Atlas"
        )
    by_reason: dict[str, int] = {}
    for _, reason in result.unanswered:
        by_reason[reason] = by_reason.get(reason, 0) + 1
    if by_reason:
        # Grouped by reason rather than listed per row (`@ref-mismatch-causes`): four histories with
        # four remedies, and a flat list of variants hides which one a reader is looking at.
        typer.echo("  no answer: " + ", ".join(f"{n} {reason}" for reason, n in sorted(by_reason.items())))
    typer.secho(
        f"checked {result.subjects} variant(s): {len(result.decided)} decided locally, "
        f"{len(result.findings)} finding(s)",
        fg=typer.colors.GREEN,
    )


def _atlas_client_or_none():
    """An Atlas client, or `None` with a sentence — never a traceback from a missing extra.

    Four absences and they are not the same: the extra is not installed, the bindings have not been
    generated, the runtime protobuf is older than the gencode (RM254), or there is no key. Each names its own remedy, and the caller degrades to the
    interval the knot table publishes rather than failing the run.
    """
    # `load_env()` before reading, at the point the credential is read (`@credential-where-read`,
    # RM212). Without it this reported "no key" on a machine whose `.env` holds one, and degraded to
    # the knot interval for rows the Atlas could have refined.
    load_env()
    key = os.environ.get("ALPHAGENOME_API_KEY") or ""
    if not key:
        typer.secho(
            f"  ALPHAGENOME_API_KEY unusable ({missing_credential_reason('ALPHAGENOME_API_KEY')}), so "
            "nothing was refined. The knot table's interval is still the honest answer for those rows.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        return None
    # Imported here, not at module level, and this is the guarded-optional-dependency exception to
    # "no inline imports" rather than a lapse: `atlas_client` imports `grpc`, so a module-level
    # import would make the [atlas] extra a requirement of the whole CLI — which is the thing RM192
    # measured its way out of. `AtlasError` comes with it for the same reason.
    try:
        from just_dna_enricher.atlas_client import AtlasError, connect
    # `RuntimeError` for the reason `alphagenome_check`'s twin carries it: a `grpcio` older than the
    # `grpcio-tools` that generated the bindings raises it at import, and this arm is where that has
    # to become "no Atlas client" rather than a traceback (RM247).
    except ATLAS_IMPORT_FAILURES:
        # The docstring above promises three absences each naming its own remedy, and this arm used
        # to fold two of them into one sentence telling the reader to do both — so the promise was
        # a claim the code did not keep. `client_absence()` decides which one it is; it lives in
        # `atlas_protos` because the module that fails to import cannot be asked why it failed.
        typer.secho(
            f"  no Atlas client, so nothing was refined: {client_absence()}",
            fg=typer.colors.YELLOW,
            err=True,
        )
        return None
    try:
        return connect(key)
    except AtlasError as exc:
        typer.secho(
            f"  the Atlas could not be reached ({exc}); nothing was refined.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        return None


def _resolve_avi_snapshot() -> Path | None:
    """Where the AVI snapshot is, asked of the lane rather than of the caller's shell.

    **A read default must not depend on the working directory.** `repro_out` is right for a builder's
    `--out` — it writes where you are — and wrong for a publish, which silently named a different
    directory depending on where the operator stood: run from `enricher/` it looked for
    `enricher/data/repro/alphagenome_avi` and refused. So the resolver comes first, which is the whole
    point of the lane having one, and the build directory is only the fallback.
    """
    from just_dna_enricher.locations import (
        SNAPSHOT_DATA_DIRNAME,
        resolve_alphagenome_avi_reference,
    )

    resolved = resolve_alphagenome_avi_reference()
    if resolved is not None:
        # `resolve` may hand back the `data/` directory; the publisher wants the snapshot root.
        return resolved.parent if resolved.name == SNAPSHOT_DATA_DIRNAME else resolved
    # `repro_out` is relative, so it means a different directory from every working directory. The
    # builder wrote into the *checkout's* `data/repro/`, so look there too — found by walking up for
    # the workspace marker rather than assuming the caller stands at the root.
    candidates = [repro_out("alphagenome_avi")]
    root = next(
        (
            d
            for d in Path.cwd().resolve().parents
            if (d / "pyproject.toml").is_file()
            and "[tool.uv.workspace]" in (d / "pyproject.toml").read_text()
        ),
        None,
    )
    if root is not None:
        candidates.append(root / repro_out("alphagenome_avi"))
    # **Absolute, always.** A resolved location that is relative carries the defect this function
    # exists to remove: it means a different directory the moment anything logs it, stores it, or
    # hands it to a subprocess with a different working directory.
    found = next((c for c in candidates if (c / SNAPSHOT_DATA_DIRNAME).is_dir()), None)
    return found.resolve() if found is not None else None


@alphagenome_app.command("expression")
def alphagenome_expression_(
    spec: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    gene: str = typer.Option(
        ...,
        "--gene",
        help=(
            "HGNC symbol. REQUIRED even with an explicit interval: the server-side gene filter is "
            "not an optimisation, and an unfiltered interval query is refused before it is sent."
        ),
    ),
    chrom: str | None = typer.Option(
        None, "--chrom", help="Contig of an explicit interval. Wins over the gene's MANE span."
    ),
    start: int | None = typer.Option(None, "--start", min=0, help="1-based start of that interval."),
    end: int | None = typer.Option(None, "--end", min=0, help="1-based end of that interval."),
    min_score: float | None = typer.Option(
        None,
        "--min-score",
        help=(
            "Keep only pairs whose magnitude reaches this. Distal scores run ~10x lower than scores "
            "at the gene, so a flat bar keeps the proximal rows and looks like it filtered on effect."
        ),
    ),
    max_rows: int = typer.Option(
        DEFAULT_MAX_ROWS,
        "--max-rows",
        min=1,
        help="Refuse rather than write more rows than this. Raising it is a deliberate act.",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="No-op with a warning: this pass reads the Atlas, not a snapshot."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be written without writing it."),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=(
            "Declared use recorded on the licence row: unstated|non-commercial|commercial. "
            "AlphaGenome Output is NON-COMMERCIAL ONLY, so an undeclared run writes nothing and "
            "says so — pass --use non-commercial."
        ),
    ),
) -> None:
    """Fill expression_effects.csv with AlphaGenome's per-gene expression effects for one gene.

    Example — and the `--use` is not decoration, an undeclared run is a no-op:

        just-dna-enricher alphagenome expression ./my_module --gene TBX1 --use non-commercial

    One row per (variant, gene): which way the variant moves that gene's predicted expression, how
    many of the 371 tissue tracks agree, and how far it sits from the gene. The interval is the
    gene's MANE span widened by the model's measured +/-512 kb attribution horizon, unless
    --chrom/--start/--end supply one; either way the gene names the server-side filter, and the MANE
    lane is still consulted for the distance, which an explicit interval cannot supply.

    A whole gene is ~3.3 M SNVs at the measured 1,091 SNVs/s — about 50 minutes — and the cost is
    printed before the query runs rather than discovered during it.
    """
    try:
        result = enrich_expression(
            spec,
            gene,
            chrom=chrom,
            start=start,
            end=end,
            min_score=min_score,
            max_rows=max_rows,
            declared_use=_use(use),
            offline=offline,
            write=not dry_run,
        )
    except (ExpressionError, EnrichmentError) as exc:
        typer.secho(f"EXPRESSION FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    for note in result.warnings:
        typer.secho(f"  {note}", fg=typer.colors.YELLOW, err=True)
    if result.skipped:
        return
    if result.interval:
        typer.echo(f"interval: {result.interval[0]}:{result.interval[1]}-{result.interval[2]}")
    # The path the pass actually wrote, not `spec / <name>` — a module keeping its sidecars under
    # `derived/` (RM49) is written there, and printing a guess sends the author to the wrong file.
    typer.secho(
        f"expression effects: {sidecar_path(spec, EXPRESSION_SIDECAR, error=ExpressionError)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        f"dataset: {result.dataset}  scored: {result.candidates}  written: {result.written}  "
        f"rows: {len(result.rows)}"
    )
    if result.withheld:
        # Grouped by reason, never a bare total: a withhold that cannot say which kind it was is the
        # absence the roster exists to prevent.
        typer.secho(
            "  withheld: " + ", ".join(f"{n} {reason}" for reason, n in sorted(result.withheld.items())),
            fg=typer.colors.YELLOW,
        )
    if result.span is None and result.written:
        typer.secho(
            "  distance_to_gene is null on every row: no MANE span was available, so this table "
            "cannot be thresholded by distance.",
            fg=typer.colors.YELLOW,
        )


@alphagenome_app.command("publish")
def alphagenome_publish_(
    snapshot: Path | None = typer.Argument(
        None,
        exists=True,
        file_okay=False,
        help=(
            "The built snapshot directory. Omit to use the resolved cache "
            "($JUST_DNA_ALPHAGENOME_AVI_CACHE, then the cache base), falling back to where "
            "`alphagenome build` writes."
        ),
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help=f"Target HF dataset. Default: {DEFAULT_ALPHAGENOME_AVI_REPO_ID}.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be uploaded. Reads the repo's file list; sends nothing.",
    ),
    message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
) -> None:
    """Publish the AVI snapshot to HuggingFace.

    **Its own command because no other one can reach this lane** (RM202). `cache rebuild --publish`
    walks lanes that have a `rebuild` adapter, and this lane cannot have one — its source is behind an
    eligibility gate, so there is nothing for an unattended rebuild to fetch. RM198 gave the lane a
    `publish_repo` and left it unreachable.

    The upload is two commits and, above 5 GB, goes through the resumable uploader (RM199): the
    payload first, then `release.json` — the description must never arrive before the bytes it
    describes.
    """
    from just_dna_enricher.upload import plan_reference_snapshot, publish_reference_snapshot

    target = repo or DEFAULT_ALPHAGENOME_AVI_REPO_ID
    if snapshot is None:
        snapshot = _resolve_avi_snapshot()
        if snapshot is None:
            typer.secho(
                "PUBLISH FAILED: no AVI snapshot found. Looked at "
                f"$JUST_DNA_ALPHAGENOME_AVI_CACHE, the cache base, and "
                f"{repro_out('alphagenome_avi').resolve()}. Build one with `alphagenome build "
                "--input <the artifact you downloaded>`, or pass the directory explicitly.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        typer.echo(f"  using {snapshot}")
    try:
        if dry_run:
            plan = plan_reference_snapshot(snapshot, target)
            typer.echo(f"would upload {len(plan.files)} file(s) to {plan.repo_id}:")
            for name in plan.files:
                size = (snapshot / name).stat().st_size if (snapshot / name).is_file() else 0
                typer.echo(f"  {name}  ({size / 1e9:.2f} GB)" if size > 1e8 else f"  {name}")
            typer.echo(
                "  release.json is sent last, in its own commit — a description that arrives "
                "before its bytes describes a snapshot nobody has."
            )
            return
        plan = publish_reference_snapshot(snapshot, target, commit_message=message)
    except (FileNotFoundError, PermissionError, ImportError, ValueError) as exc:
        typer.secho(f"PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if KNOT_FILENAME not in plan.files:
        typer.secho(
            f"  no {KNOT_FILENAME} in this snapshot — a puller would hold scores they cannot rank, "
            "because PHRED is not stored. Rebuild with `alphagenome build`.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    typer.secho(
        f"published: {snapshot} → {plan.repo_id} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )
