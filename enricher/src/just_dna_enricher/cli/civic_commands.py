"""The `civic` group: build, citations, publish and reproduce (RM260 split this out of the former
single-file `cli.py`).
"""

from pathlib import Path

import typer

from just_dna_enricher.cli._shared import _DRAFT_PRECONDITION_ERRORS
from just_dna_enricher.locations import repro_out

# ── the PubMind snapshot (build only; publish exists in order to refuse) — RM134 § A ────────────

civic_app = typer.Typer(
    add_completion=False,
    help=(
        "Build the CIViC snapshot from a dated bulk release. CC0, so unlike the PubMind snapshot "
        "this one may be published."
    ),
    no_args_is_help=True,
)


@civic_app.command("build")
def civic_build_(
    release: str | None = typer.Option(
        None,
        "--release",
        help=(
            "Dated CIViC release to download, e.g. 01-Aug-2026. A DATED release, never the nightly: "
            "a snapshot that cannot name its input is one nothing can reproduce."
        ),
    ),
    evidence: Path | None = typer.Option(
        None,
        "--evidence",
        exists=True,
        dir_okay=False,
        help="Local ClinicalEvidenceSummaries.tsv. Use instead of --release to build offline.",
    ),
    variants: Path | None = typer.Option(
        None,
        "--variants",
        exists=True,
        dir_okay=False,
        help="Local VariantSummaries.tsv.",
    ),
    profiles: Path | None = typer.Option(
        None,
        "--profiles",
        exists=True,
        dir_okay=False,
        help="Local MolecularProfileSummaries.tsv.",
    ),
    out: Path = typer.Option(
        repro_out("civic"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/civic.parquet + release.json).",
    ),
    submitted: bool = typer.Option(
        False,
        "--submitted",
        help=(
            "Also read the release's civic_accepted_and_submitted.vcf, so evidence a curator entered "
            "but no editor signed off joins the snapshot. Over 01-Aug-2026 that widens the direction "
            "corpus from 507 rows on 270 variants to 1149 on 397, adding 642 submitted rows and 127 "
            "variants, and every row carries the status CIViC gave it. Dated and pinnable like the "
            "TSVs, so the build stays reproducible."
        ),
    ),
    vcf: Path | None = typer.Option(
        None,
        "--vcf",
        exists=True,
        dir_okay=False,
        help="Local civic_accepted_and_submitted.vcf. Use with the local TSV flags to build offline.",
    ),
) -> None:
    """Reduce a dated CIViC release to the parquet snapshot the direction-axis drafter reads.

    **The bulk release, not the GraphQL API, and the two are not interchangeable.** Every row of
    `ClinicalEvidenceSummaries.tsv` is status `accepted`; the API defaults to `NON_REJECTED` and
    serves roughly 2.35x as many evidence items. A snapshot has to be reproducible from a pinned
    input, so this reads the dated files and records the basis in `release.json`.

    **`--submitted` widens that basis without leaving the dated release (RM169).** CIViC publishes
    `<date>-civic_accepted_and_submitted.vcf` beside the TSVs, so unreviewed evidence is pinnable too
    and no API read is needed. The TSVs stay primary — the VCF cannot carry a variant with no GRCh37
    coordinate, which is exactly the class whose identity had to be read out of its name — and the VCF
    supplies the curation status, the submitted evidence, and the identity for the 112 variants
    `VariantSummaries.tsv` (itself accepted-only) does not describe. Those rows are stamped
    `identity_derivation="vcf_csq"`, and nothing is placed from the VCF's own GRCh37 position.

    **There is no `--use` flag.** CIViC is CC0 on every axis, so a declared-use gate would permit
    every build unconditionally, and a flag feeding a gate that never gates is a flag that does
    nothing (`@acquisition-gate-is-not-a-read-gate`).
    """
    from just_dna_enricher.civic_build import (
        CIVIC_EVIDENCE_FILE,
        CIVIC_PROFILE_FILE,
        CIVIC_VARIANT_FILE,
        build_snapshot,
        civic_release_url,
        download_civic_file,
    )
    from just_dna_enricher.civic_vcf import CIVIC_VCF_FILE

    if vcf is not None and submitted:
        raise typer.BadParameter(
            "pass --vcf to read a local VCF or --submitted to download the release's one, not both. "
            "Two sources for one input is a build whose provenance nothing can state."
        )
    local = (evidence, variants, profiles)
    if release is None and not all(local):
        raise typer.BadParameter(
            "pass --release to download a dated release, or all three of --evidence, --variants "
            "and --profiles to build from local files. Two of the three is not a build: the "
            "evidence file carries the claims, the variant file the identities, and the profile "
            "file is what tells a combination genotype from a dangling reference."
        )
    shas: dict[str, str | None] = {}
    vcf_path = vcf
    if all(local):
        evidence_path, variant_path, profile_path = local
    else:
        out.mkdir(parents=True, exist_ok=True)
        paths = []
        for filename in (CIVIC_EVIDENCE_FILE, CIVIC_VARIANT_FILE, CIVIC_PROFILE_FILE):
            got = download_civic_file(out / filename, civic_release_url(release, filename))
            shas[filename] = got.sha256
            paths.append(got.path)
        evidence_path, variant_path, profile_path = paths
        if submitted:
            got = download_civic_file(out / CIVIC_VCF_FILE, civic_release_url(release, CIVIC_VCF_FILE))
            shas[CIVIC_VCF_FILE] = got.sha256
            vcf_path = got.path

    result = build_snapshot(
        evidence_path,
        variant_path,
        profile_path,
        out,
        release=release,
        evidence_sha256=shas.get(CIVIC_EVIDENCE_FILE),
        variant_sha256=shas.get(CIVIC_VARIANT_FILE),
        profile_sha256=shas.get(CIVIC_PROFILE_FILE),
        vcf=vcf_path,
        vcf_sha256=shas.get(CIVIC_VCF_FILE),
    )
    typer.echo(f"Wrote {result.parquet_file} ({result.record_count} rows, {result.variants} variants)")
    typer.echo(f"  status basis: {result.status_basis}")
    if result.status_counts:
        typer.echo("  " + " · ".join(f"{k} {v}" for k, v in sorted(result.status_counts.items())))
    typer.echo(f"  dataset: {result.dataset or 'unknown (no --release named)'}")
    typer.echo(f"  read {result.input_rows} evidence rows; dropped:")
    for reason, count in result.dropped.items():
        typer.echo(f"    {reason:24s} {count}")
    typer.echo(f"  identity: {result.identity_derivations}")
    if result.withheld_direction:
        typer.echo(
            f"  {result.withheld_direction} row(s) kept with no direction: the source refuted a "
            f"claim rather than making one, and a refutation is not the opposite claim."
        )
    if result.dropped["unresolvable_identity"]:
        typer.echo(
            f"  {result.dropped['unresolvable_identity']} row(s) dropped for carrying neither an "
            f"rsID nor a GRCh38 accession; {result.unresolvable_with_caid} of those variants do "
            f"carry a ClinGen CAID, so they stay addressable by a later identity pass."
        )


@civic_app.command("citations")
def civic_citations_(
    spec: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory."),
    snapshot: Path | None = typer.Option(
        None,
        "--snapshot",
        exists=True,
        file_okay=False,
        help="CIViC snapshot to map authored rows through. Default: the provisioned cache.",
    ),
    variant_id: list[int] = typer.Option(
        [],
        "--variant-id",
        help=(
            "Ask about a CIViC variant id directly, repeatable. Its citations ground the MODULE "
            "rather than a variant, which is the only route to a record CIViC publishes no identity "
            "for — variant 1955 is the case this exists for."
        ),
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Do not fetch. Every subject is recorded as not-asked; no row is written.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Report what would be appended, write nothing.",
    ),
) -> None:
    """Append the citations a CIViC variant carries that the dated bulk release cannot reach (RM160).

    **Why this is not part of `civic build`.** The builder reads a dated release and is byte-
    reproducible from it; `civic reproduce` proves it by building twice. The wider basis RM169 adopted
    comes from a VCF, and a VCF record needs a POS — so submitted evidence attached to a variant with
    no GRCh37 coordinate is published on exactly one surface, the GraphQL API, which has no release to
    pin. The read is also **one request per variant by construction**, because `evidenceItems` takes a
    single `variantId`. Batching it into the builder is the first repair anyone proposes and it is
    exactly the reproducibility bargain this shape refused.

    A recovered citation lands in `studies.csv`; `literature.csv` is derived from those PMIDs by the
    `literature` command, and an article row nothing cites is dropped from the artifact. CIViC's own
    curation status rides in `confidence`/`confidence_unit`, unconverted, so an accepted row and a
    submitted row are not the same row. Appending only — a second run over an unchanged API adds
    nothing — and `enrich` re-asks later and reports what has moved since.

    CIViC is CC0, so there is no `--use` flag: a declared-use gate would permit every call
    unconditionally, and a flag feeding a gate that never gates is a flag that does nothing.
    """
    from just_dna_enricher.civic_citations import (
        CivicCitationsError,
        draft_civic_citations,
        read_module,
    )
    from just_dna_enricher.enrich import spec_genome_build
    from just_dna_enricher.locations import resolve_civic_reference

    reference = snapshot if snapshot is not None else resolve_civic_reference()
    try:
        variants, resolution = read_module(spec, genome_build=spec_genome_build(spec))
        result = draft_civic_citations(
            spec,
            variants=variants,
            resolution_rows=resolution,
            reference=reference,
            requested=variant_id,
            offline=offline,
            dry_run=dry_run,
        )
    except (CivicCitationsError, *_DRAFT_PRECONDITION_ERRORS) as exc:
        typer.secho(f"CIVIC CITATIONS FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"  {len(result.subjects)} CIViC variant(s) in scope, {result.asked} asked; "
        f"{result.citations_seen} PubMed citation(s) seen"
    )
    if result.unmapped_rows:
        typer.echo(
            f"  {result.unmapped_rows} authored row(s) resolved to a locus no CIViC variant matched "
            f"— name one with --variant-id if CIViC publishes no identity for it"
        )
    for reason, count in result.withheld.items():
        if count:
            typer.echo(f"  withheld {reason:22s} {count}")
    if result.confidence_withheld:
        typer.echo(
            f"  {result.confidence_withheld} row(s) written with no confidence: CIViC states more "
            f"than one status for the items citing that paper"
        )
    for report in result.reports:
        typer.echo(f"  {report}")
    for warning in result.warnings:
        typer.secho(f"  warning: {warning}", fg=typer.colors.YELLOW, err=True)
    verb = "would add" if dry_run else "added"
    breakdown = ", ".join(f"{r.csv_name} {len(r.added)}" for r in result.reports) or "nothing"
    typer.secho(f"{verb}: {breakdown} — in {spec}", fg=typer.colors.GREEN)


@civic_app.command("publish")
def civic_publish_(
    snapshot_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Built snapshot directory (data/civic.parquet + release.json).",
    ),
    repo_id: str | None = typer.Option(
        None,
        "--repo",
        help="Target HF dataset (owner/name). Default: just-dna-seq/civic.",
    ),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be uploaded without contacting HuggingFace.",
    ),
) -> None:
    """Upload a built CIViC snapshot to a HuggingFace dataset repo (publisher/dev).

    **This one does not refuse, and the contrast with `pubmind publish` is the point.** CIViC's content
    is CC0 1.0 — a public-domain dedication with no share-alike, no bar on sale and attribution
    requested rather than required — so there is no permission to establish before passing the bytes
    on. PubMind's command exists in order to say no because its terms are unstated; PharmVar's cache is
    unpublishable because its terms forbid it. Nothing here is in either position.

    What the snapshot carries is a *derivation* of CIViC's release, not a copy of it: the germline
    direction rows, placed on GRCh38 through identifiers CIViC itself publishes. `release.json` records
    which dated release it came from and the `accepted` status basis, so a consumer can tell what they
    are looking at without re-deriving it.

    **The ClinGen Allele Registry's answers are NOT in here**, and that is deliberate rather than an
    oversight: the registry states no terms, and a lookup performed at draft time is a read, while
    baking its responses into a published file would be redistribution of bytes nobody has established
    we may pass on. The snapshot carries the CAID; resolving it stays the consumer's own fetch.
    """
    from just_dna_enricher.upload import (
        DEFAULT_CIVIC_REPO_ID,
        plan_reference_snapshot,
        publish_reference_snapshot,
    )

    repo_id = repo_id or DEFAULT_CIVIC_REPO_ID
    if dry_run:
        plan = plan_reference_snapshot(snapshot_dir, repo_id)
        typer.echo(f"Would upload to {plan.repo_id}:")
        for f in plan.files:
            typer.echo(f"  • {f}")
        return
    try:
        plan = publish_reference_snapshot(snapshot_dir, repo_id, commit_message=commit_message)
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"Published {len(plan.files)} file(s) to {plan.repo_id}", fg=typer.colors.GREEN)


@civic_app.command("reproduce")
def civic_reproduce_(
    release: str = typer.Option(
        "01-Aug-2026",
        "--release",
        help="Dated CIViC release to reproduce, e.g. 01-Aug-2026.",
    ),
    out: Path = typer.Option(
        repro_out("civic_reproduce"),
        "--out",
        file_okay=False,
        help=(
            "Working directory. The release files and two independent builds land here. The default "
            "is under data/, which this workspace git-ignores wholesale."
        ),
    ),
    keep: bool = typer.Option(
        False,
        "--keep",
        help="Leave the downloaded release files in place for inspection.",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Skip the reference cross-check. The build and determinism checks still run.",
    ),
    submitted: bool = typer.Option(
        False,
        "--submitted",
        help=(
            "Reproduce the wider basis: also download the release's "
            "civic_accepted_and_submitted.vcf and build with it, so the submitted rows and their "
            "coordinates go through every check below rather than only the accepted ones."
        ),
    ),
) -> None:
    """Build the CIViC snapshot from a dated release and check it, end to end.

    **Five checks, and the third is the one worth the network.** The first two are about us; the third
    is about whether the coordinates we produced are real.

    1. **The release downloads and its bytes are recorded** — a sha256 per file, so a rerun that
       disagrees is a finding about the source rather than a mystery.
    2. **Two independent builds are byte-identical** (Principle 7). A parquet has no inherent row
       order, so this is the check that the sort is doing its job.
    3. **Every placed coordinate is cross-checked against the GRCh38 reference sequence.** This is the
       external validation: the snapshot's positions come from RefSeq accessions inside ClinVar HGVS,
       and this asks an unrelated service (refget/seqrepo) whether the reference base at each of those
       positions is what we wrote. A wrong-build or off-by-one placement fails here and nowhere else.
    4. **The drop registry closes** — every input row kept or counted, an equality over a walked set.
    5. **The published file list is exactly what the publisher would upload.**

    Exits non-zero if any check fails, so it is usable in CI.
    """
    from just_dna_format.resolution import ResolutionRow

    from just_dna_enricher.civic_build import (
        CIVIC_COLUMNS,
        CIVIC_EVIDENCE_FILE,
        CIVIC_PROFILE_FILE,
        CIVIC_VARIANT_FILE,
        build_snapshot,
        civic_release_url,
        download_civic_file,
    )
    from just_dna_enricher.civic_vcf import CIVIC_VCF_FILE
    from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME
    from just_dna_enricher.sequences import SequenceProxy, verify_reference_alleles
    from just_dna_enricher.upload import DEFAULT_CIVIC_REPO_ID, plan_reference_snapshot

    failures: list[str] = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        typer.secho(
            f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}",
            fg=typer.colors.GREEN if ok else typer.colors.RED,
        )
        if not ok:
            failures.append(label)

    out.mkdir(parents=True, exist_ok=True)
    typer.echo(f"CIViC release {release}")

    # 1 ── the release, with its bytes recorded
    typer.echo("\n1. Downloading the dated release")
    paths, shas = [], {}
    wanted = [CIVIC_EVIDENCE_FILE, CIVIC_VARIANT_FILE, CIVIC_PROFILE_FILE]
    if submitted:
        # Hashed like every other input, because the whole point of reading it from the dated release
        # rather than the API is that its bytes can be pinned.
        wanted.append(CIVIC_VCF_FILE)
    for filename in wanted:
        got = download_civic_file(out / filename, civic_release_url(release, filename))
        paths.append(got.path)
        shas[filename] = got.sha256
        typer.echo(f"     {filename:38s} {got.sha256[:16]}…  {got.path.stat().st_size:>9,} bytes")
    check(all(shas.values()), "every input file hashed")
    vcf_path = paths.pop() if submitted else None

    # 2 ── two builds, byte for byte
    typer.echo("\n2. Building twice")
    first = build_snapshot(
        *paths,
        out / "build-a",
        release=release,
        evidence_sha256=shas[CIVIC_EVIDENCE_FILE],
        variant_sha256=shas[CIVIC_VARIANT_FILE],
        profile_sha256=shas[CIVIC_PROFILE_FILE],
        vcf=vcf_path,
        vcf_sha256=shas.get(CIVIC_VCF_FILE),
    )
    second = build_snapshot(*paths, out / "build-b", release=release, vcf=vcf_path)
    typer.echo(f"     {first.record_count} rows on {first.variants} variants ({first.status_basis})")
    if first.status_counts:
        typer.echo("     " + " · ".join(f"{k} {v}" for k, v in sorted(first.status_counts.items())))
    check(
        first.parquet_file.read_bytes() == second.parquet_file.read_bytes(),
        "a rebuild is byte-identical (P7)",
    )

    # 4 ── the accounting (run before the slow check, so a broken build fails fast)
    total_dropped = sum(first.dropped.values())
    check(
        first.record_count + total_dropped == first.input_rows,
        "the drop registry accounts for every input row",
        f"{first.input_rows} = {first.record_count} kept + {total_dropped} dropped",
    )
    for reason, count in first.dropped.items():
        typer.echo(f"     dropped {reason:24s} {count:>6,}")

    # 5 ── what would be published
    plan = plan_reference_snapshot(first.out_dir, DEFAULT_CIVIC_REPO_ID)
    expected = {f"data/{first.parquet_file.name}", RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME}
    check(
        set(plan.files) == expected,
        "the publish plan is data + release.json + LICENSE",
        ", ".join(sorted(plan.files)),
    )

    frame = pl.read_parquet(first.parquet_file) if (pl := _polars()) else None
    if frame is not None:
        check(list(frame.columns) == list(CIVIC_COLUMNS), "the emitted column order is the fixed one")

    # 3 ── the external check, and the reason this command needs a network
    typer.echo("\n3. Cross-checking placed coordinates against the GRCh38 reference")
    if offline or frame is None:
        typer.secho(
            "     SKIPPED (--offline) — a check that did not run is not a check that passed",
            fg=typer.colors.YELLOW,
        )
    else:
        placed = frame.filter(pl.col("chrom").is_not_null() & pl.col("ref").is_not_null())
        rows = [
            ResolutionRow(
                variant_key=f"{r['chrom']}:{r['start']}:{r['ref']}",
                status="resolved",
                chrom=r["chrom"],
                start=r["start"],
                ref=r["ref"],
            )
            for r in placed.iter_rows(named=True)
        ]
        result = verify_reference_alleles(rows, sequences=SequenceProxy())
        if result.not_checked:
            typer.secho(
                f"     SKIPPED — {result.not_checked}. A check that could not run is not a check "
                f"that passed.",
                fg=typer.colors.YELLOW,
            )
        else:
            # `subjects` rather than `len(rows)`: a row the service answered nothing about is outside
            # the denominator rather than inside it with a clean bill, and reporting the wider number
            # would claim coverage the check did not have.
            check(
                not result.mismatches,
                "every placed ref matches the GRCh38 reference sequence",
                f"{result.subjects} of {len(rows)} coordinate(s) read, {len(result.mismatches)} mismatch(es)",
            )
            for m in result.mismatches[:5]:
                typer.secho(f"     {m}", fg=typer.colors.RED)

    if not keep:
        for path in paths:
            path.unlink(missing_ok=True)

    typer.echo("")
    if failures:
        typer.secho(
            f"REPRODUCTION FAILED: {len(failures)} check(s) — {'; '.join(failures)}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    typer.secho(f"Reproduced {release}: {first.record_count} rows, all checks passed", fg=typer.colors.GREEN)


def _polars():
    """polars if the [dev] extra is present, else `None` — the builder needs it, a reader does not."""
    try:
        import polars

        return polars
    except ImportError:  # pragma: no cover - only where [dev] is absent
        return None
