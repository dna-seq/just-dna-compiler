"""Authoring surfaces: `draft`, `template`, `check-identifiers` and the `vrs` group (RM260 split this out
of the former single-file `cli.py`).
"""

from pathlib import Path

import typer
from just_dna_compiler.draft import DraftError, authoring_requirements, blank_template
from just_dna_format.manifest import VerificationRecord

from just_dna_enricher.cli._shared import _DRAFT_PRECONDITION_ERRORS, _attest_on_the_way_out, _use, app
from just_dna_enricher.cpic import CpicError
from just_dna_enricher.enrich import EnrichmentError
from just_dna_enricher.identifiers import IdentifierCheckError, IdentifierUnavailable, check_identifiers
from just_dna_enricher.identifiers import pgs_withheld_sentences as identifier_pgs_withheld
from just_dna_enricher.identifiers import unreachable_records as identifier_unreachable
from just_dna_enricher.identifiers import verification_records as identifier_records
from just_dna_enricher.licensing import sidecar_path
from just_dna_enricher.pgx_draft import draft_gene
from just_dna_enricher.verification import record_verification, skipped
from just_dna_enricher.vrs import MintResult


@app.command("draft")
def draft_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    gene: list[str] = typer.Option(..., "--gene", help="Gene to draft from CPIC (repeatable)."),
    drug: list[str] = typer.Option(
        [],
        "--drug",
        help="Also draft CPIC's prescribing recommendations for this drug (repeatable).",
    ),
    allele: list[str] = typer.Option(
        [],
        "--allele",
        help=(
            "Draft only these star alleles, in all three tables (repeatable; `*1` is always kept). "
            "A caller emits a bounded allele set, and n alleles is n(n+1)/2 pairs — CYP2D6 is 16,290 "
            "diplotypes unfiltered. Requires a single --gene, since a star name is gene-scoped."
        ),
    ),
    population: str | None = typer.Option(
        None,
        "--population",
        help="Draft only this CPIC clinical context (e.g. 'NVI'). Default: every context, as rows.",
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=(
            "Declared use: unstated | non-commercial | commercial. CPIC forbids sale, so a draft is "
            "SKIPPED when unstated and REFUSED when commercial."
        ),
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Draft from a built CPIC snapshot only; never reach CPIC live.",
    ),
    cpic_cache: Path | None = typer.Option(None, "--cpic-cache", help="Explicit CPIC snapshot dir."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be added; write nothing."),
) -> None:
    """Draft PGx tables for one or more genes from CPIC — appends rows, never overwrites one.

    Re-runnable and additive, so a multi-gene module is built up a gene at a time. A row whose key is
    already in the file is reported, never replaced: what CPIC now says about a row you already wrote
    is a finding for `pgx`, not an edit for this command to make.
    """
    declared = _use(use)
    if allele and len(gene) != 1:
        # `*2` in CYP2C9 and `*2` in CYP2C19 are different alleles of different genes, so one set
        # applied across several genes would filter each by a name that means something else there.
        # Drafting is per-gene and re-runnable by design — run the command once per gene.
        typer.secho(
            f"--allele needs exactly one --gene (got {len(gene)}): a star-allele name means a "
            f"different allele in each gene. Draft one gene at a time; the command is additive.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    total_added = 0
    for name in gene:
        try:
            result = draft_gene(
                spec_dir,
                name,
                drugs=drug,
                alleles=allele,
                population=population,
                declared_use=declared,
                dry_run=dry_run,
                offline=offline,
                cpic_cache=cpic_cache,
            )
        except (CpicError, *_DRAFT_PRECONDITION_ERRORS) as exc:
            typer.secho(f"DRAFT FAILED ({name}): {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        if result.skipped:
            for warning in result.warnings:
                typer.secho(f"  skipped: {warning}", fg=typer.colors.YELLOW, err=True)
            continue
        typer.secho(f"{name}:", fg=typer.colors.GREEN)
        for report in result.reports:
            typer.echo(f"  {report}")
            for outcome in report.differs:
                typer.secho(f"    {outcome}", fg=typer.colors.YELLOW)
        for warning in result.warnings:
            typer.secho(f"  warning: {warning}", fg=typer.colors.YELLOW, err=True)
        total_added += result.added
    verb = "would add" if dry_run else "added"
    typer.echo(f"{verb} {total_added} row(s) across {len(gene)} gene(s) in {spec_dir}")


@app.command("template")
def template_(
    kind: str = typer.Argument(..., help="Authored CSV to emit a header for, e.g. repeat_alleles.csv"),
) -> None:
    """Print a header-only CSV for one authored table kind, generated from the live models.

    Kept working here, but `just-dna-compiler template` is canonical: this needs no network, and an
    author who installed only the tier that owns the CSV shape should not have to add the network
    tier to get a header. See `just-dna-compiler stub` for a template with rows to replace.
    """
    try:
        typer.echo(blank_template(kind), nl=False)
        reqs = authoring_requirements(kind)
    except DraftError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"required: {', '.join(reqs['always'])}", fg=typer.colors.BLUE, err=True)
    for group in reqs["any_of"]:
        typer.secho(f"and one of: {' + '.join(group)}", fg=typer.colors.BLUE, err=True)
    if reqs["defaulted"]:
        # Without this line the command gave actively wrong advice: these columns are not "required",
        # so they were never listed, yet an empty cell arrives as None and fails on type.
        shown = ", ".join(f"{k}={v}" for k, v in reqs["defaulted"].items())
        typer.secho(f"must not be left empty (defaults): {shown}", fg=typer.colors.YELLOW, err=True)


@app.command("check-identifiers")
def check_identifiers_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Exit 1 if any identifier is stale."),
    traits: bool = typer.Option(True, "--traits/--no-traits", help="Check trait_efo_id against OLS4."),
    genes: bool = typer.Option(True, "--genes/--no-genes", help="Check gene symbols against HGNC."),
    pgs: bool = typer.Option(
        True,
        "--pgs/--no-pgs",
        help="Check pgs_id against the PGS Catalog, and the two authored cells beside it.",
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=(
            "Declared use: unstated | non-commercial | commercial. A PGS score licensed for academic "
            "research only bars sale, so a module citing one compiles ONLY with a declaration — and "
            "this flag is the one the compile's own refusal tells you to re-run with."
        ),
    ),
) -> None:
    """Report obsolete trait terms, retired gene symbols and unrecognised PGS accessions (online).

    **Writes no authored cell, and records that the question was put.** Unlike the rsID check (whose
    verdict lands on resolution.csv), these are module-level identifiers with no sidecar column to
    record, and filling one from the registry being asked about it would make the comparison vacuous
    — see `hints.REDUNDANCY_BEARING`. What this does write is `verification.json`: an attestation that
    the five checks ran and over how many rows, never a value. A consumer holding the artifact has no
    other way to tell "asked and clean" from "never asked" (RM45/RM72).

    The PGS leg also writes `sources.csv` (RM163), and that is not an exception to the sentence above:
    the Catalog's `license` is a field on each score record and it varies, so a module carrying an
    academic-research-use-only score must not compile claiming the generic terms. The rows are the
    terms, never a value in an authored cell.
    """
    try:
        # `spec_dir=` rather than loading the rows here (RM41). This command was the workspace's own
        # evidence that the row-taking form leaves every caller reaching for a private loader.
        report = check_identifiers(
            spec_dir=spec_dir,
            check_traits=traits,
            check_genes=genes,
            check_pgs=pgs,
            declared_use=use,
        )
    except ValueError as exc:
        # A module whose rows will not load: nothing is attested, because there are no bytes for an
        # attestation to bind to and no question was reached.
        typer.secho(f"{exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except IdentifierUnavailable as exc:
        # The registry never answered, which is `unreachable` rather than an absence (S20) — and it is
        # the run on which a reader most needs the record, since the report is empty. `check-acmg`
        # records the same thing through `AcmgListUnavailable`; without this the promise two lines up
        # would be false exactly when it matters.
        #
        # This read `except httpx.HTTPError` until RM101, and it only ever fired because
        # `OntologyClient` leaked its transport library's exception — the very defect RM97 set out to
        # end. So the leak was not merely unnoticed here, it was **load-bearing**: repairing the
        # client without this line would have turned the attestation off silently, on exactly the run
        # the comment above says needs it most. The comment already named the right shape one clause
        # over; the type now matches it.
        _attest_on_the_way_out(
            identifier_unreachable(check_traits=traits, check_genes=genes, check_pgs=pgs, detail=str(exc)),
            spec_dir,
        )
        typer.secho(f"IDENTIFIER CHECK FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except IdentifierCheckError as exc:
        # **After the `IdentifierUnavailable` arm, and the order is load-bearing** — that class is a
        # subclass of this one, so catching the parent first would swallow every unreachable-registry
        # run into this message (`@client-exception-contract`). What reaches here is the PGS leg's
        # licence write failing on the module's own layout, which is neither a stale identifier nor a
        # source that would not answer.
        #
        # Nothing is attested, and that is deliberate rather than an omission: the registries *did*
        # answer, so `unreachable` would be a false record, and the attestation is written through the
        # same sidecar resolver that has just refused — so it would fail again for the same reason and
        # replace this sentence with a worse one.
        typer.secho(f"CHECKED, BUT THE TERMS WERE NOT RECORDED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    # **The guard is the roster, not a filename.** This command opened with `if not (spec_dir /
    # "variants.csv").exists(): return "nothing to check"`, on the reasoning that such a module "has no
    # gene, trait_efo_id or row for these checks to have an opinion about". Nine tables carry each
    # column and four of them are the PGx kinds a module with no `variants.csv` is built out of, so
    # that sentence was false and the command exited 0 having asked nothing — S86's unreadable zero
    # surviving one level above the function that repaired it, on this repo's own
    # `cyp2c19_star_alleles`, which names CYP2C19 on every row it has.
    #
    # No attestation here, which is the one half of the old guard that was right: with no id-bearing
    # table present there is no question to record having put, and minting a nonce would create a
    # `verification.json` on a module that never asked for one. Both checks switched off is a
    # different state and keeps its existing path below, where it is recorded as `not_requested`.
    #
    # **And it must not fire while a table was present and unreadable.** That is the same defect one
    # step further out: a module whose only id-bearing table will not parse read *nothing*, so both
    # halves of the condition were true and the command exited 0 with "nothing to check" — never
    # printing the unreadable-table warning below, and never attesting. The reason a question was not
    # put is exactly what a reader needs on that run.
    #
    # **`and`, not `or`, across the three flags** — a check the author switched off is a record they
    # asked for, and `not_requested` is written on the path below. The guard is for the module that
    # carries no identifier at all, which is a different absence from one the author chose.
    if (
        traits
        and genes
        and pgs
        and not (report.trait_tables_read or report.gene_tables_read or report.pgs_tables_read)
        and not report.unreadable_tables
    ):
        typer.secho(
            "no table carrying trait ids, gene symbols or PGS accessions — nothing to check",
            fg=typer.colors.YELLOW,
        )
        return
    # **The count names the tables it is out of (S86).** `traits checked: 0` used to say two things —
    # the module declares no trait, and its traits are in a table the roster never read — and a reader
    # took the second for the first, which is how a retired CURIE ships with every gate green.
    typer.echo(
        f"traits checked: {len(report.traits)}"
        f" (from {len(report.trait_tables_read)} table(s): {', '.join(report.trait_tables_read) or 'none'})"
        f"  genes checked: {len(report.genes)}"
        f" (from {len(report.gene_tables_read)} table(s): {', '.join(report.gene_tables_read) or 'none'})"
        f"  PGS accessions checked: {len(report.pgs)}"
        f" (from {len(report.pgs_tables_read)} table(s): {', '.join(report.pgs_tables_read) or 'none'})"
    )
    if report.pgs:
        # The comparison's own three numbers, never recomputed here: compared, drifted, withheld. A
        # count beside a check is one that can disagree with it, and then the terminal and the
        # attestation give two accounts of one run.
        comparison = report.pgs_metadata
        typer.echo(
            f"  PGS metadata cells compared: {len(comparison.compared)} of "
            f"{len(comparison.authored)} authored"
            f" ({len(comparison.drift)} disagree, {len(comparison.withheld)} withheld)"
            + (f"  [PGS Catalog release {report.pgs_release}]" if report.pgs_release else "")
        )
    for name, why in sorted(report.unreadable_tables.items()):
        # Only the tables that exist and would not parse. An absent optional table is every module's
        # normal shape and would bury this line in noise.
        typer.secho(
            f"  {name} carries identifiers and could not be read ({why}) — its ids were NOT checked",
            fg=typer.colors.YELLOW,
            err=True,
        )
    for finding in [
        *report.stale_traits,
        *report.stale_genes,
        *report.gene_loci,
        *report.stale_pgs,
        *report.pgs_metadata.drift,
    ]:
        typer.secho(f"  {finding}", fg=typer.colors.YELLOW, err=True)
    for sentence in identifier_pgs_withheld(report.pgs_metadata):
        # Never silently, for `gene_loci_not_checked`'s reason one axis over: a cell this check looked
        # at and could not settle is neither a finding nor a clean comparison, and a reader who cannot
        # see it reads the agreement count as covering every authored cell.
        typer.secho(f"  {sentence}", fg=typer.colors.YELLOW)
    if report.gene_loci_not_checked:
        # Never silently: an empty conflict list means "nothing disagreed" and "never compared", and
        # a reader who cannot tell them apart is being told a check passed that was never put (S24).
        typer.secho(
            f"  gene/chromosome agreement not checked: {report.gene_loci_not_checked}",
            fg=typer.colors.YELLOW,
        )
    # One call for all five records: the proof-of-work binds the whole document, so a per-check write
    # would pay it five times for one guarantee. Before the strict exit below, because the check DID
    # run — the exit code is presentation, and an attestation withheld on it would make the record
    # depend on which flag the author passed.
    try:
        record_verification(
            identifier_records(report, check_traits=traits, check_genes=genes, check_pgs=pgs),
            spec_dir,
            error=EnrichmentError,
        )
    except EnrichmentError as exc:
        # The check did not fail — the report is above and it is complete. What failed is the
        # attestation, so the message says which, in the `vrs mint` shape.
        typer.secho(f"CHECKED, BUT NOT ATTESTED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if report.clean:
        # **"Current" out of nothing is the same unreadable zero one level up (S86).** With both
        # checks off, or with every id-bearing table absent, `report.clean` is vacuously true and the
        # green line asserted a pass over a question nobody put. It says what it read instead.
        looked_at = len(report.trait_tables_read) + len(report.gene_tables_read) + len(report.pgs_tables_read)
        if not report.traits and not report.genes and not report.pgs:
            typer.secho(
                "no identifiers were checked"
                + (
                    f" — {looked_at} table(s) read and none carries a trait id, gene symbol or PGS accession"
                    if looked_at
                    else " — no table carrying identifiers was read"
                ),
                fg=typer.colors.YELLOW,
            )
        elif report.metadata_disagrees:
            # **Checked, and something differs — but the exit code stays 0 even under `--strict`.**
            # Every identifier the registries were asked about is current; what disagrees is a
            # curated cell against a source's own summary, which is the shape the strict gate
            # deliberately does not arbitrate (`@a-source-recuring-is-not-a-strict-matter`). The
            # green line is withheld all the same, because a difference was reported above.
            typer.secho(
                "all identifiers current, but a source disagrees with an authored cell above",
                fg=typer.colors.YELLOW,
            )
        else:
            typer.secho("all identifiers current", fg=typer.colors.GREEN)
    else:
        # **The verdict's own reasons, in both modes.** Every finding behind them is already printed
        # above, so this is the one line that says which of them the exit code turns on — and under
        # `--best-effort` it is the only place the run states that it failed at all. `tables_unreadable`
        # is why this branch is now reachable with nothing stale: a table carrying ids that will not
        # parse was reported above and then exited 0 under `--strict` beneath *all identifiers current*
        # (RM235).
        typer.secho(f"identifier check: {report.clean}", fg=typer.colors.RED)
        if strict:
            raise typer.Exit(code=1)


# ── VRS allele ids ──────────────────────────────────────────────────────────────────────────────

vrs_app = typer.Typer(
    add_completion=False,
    help="GA4GH VRS allele identity for an already-resolved module.",
    no_args_is_help=True,
)


def _mint_record(result: MintResult) -> VerificationRecord:
    """What a minting run can honestly attest about `vrs_allele_id` (RM45).

    The member names the **cross-check** — a source's own `ga4gh:VA.…` against the one minted here —
    and its input is `mint_resolution_rows(source_ids=…)`, a map this command has nothing to fill
    from: `resolution.csv` records the ids the tier minted and never where an id came from, so the
    question was not put. That is a skip, not a clean pass. Recording `subjects` as the alleles the
    run *named* would say the opposite of what happened, which is the F4 shape — an attestation
    asserting a comparison nobody made — and it is the reading a coverage figure invites, since this
    pass does end with a number out of a number.

    The coverage counts still travel, in `detail`: they are what the run did do, and they are grouped
    by reason class by `MintResult` rather than listed per allele. They are not this record's
    numbers, though — the compiler publishes them, as `manifest.compilation.vrs_alleles` and
    `vrs_alleles_identified`, which is where a consumer already reads them.
    """
    detail = (
        "no source-reported allele id accompanies this resolution.csv, so nothing was compared "
        f"against the ids minted here; {result.identified}/{result.alleles} allele(s) now carry one"
    )
    gaps = result.coverage_warnings()[1:]
    if gaps:
        detail += ". Not named: " + "; ".join(line.strip() for line in gaps)
    return skipped("vrs_allele_id", "nothing_to_check", detail=detail)


@vrs_app.command("mint")
def vrs_mint_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Substitutions only: indels need the reference sequence, which means a network call.",
    ),
) -> None:
    """Stamp ga4gh:VA.… allele ids onto resolution.csv (substitutions offline, indels online)."""
    from just_dna_compiler.compiler import load_csv_rows
    from just_dna_format.resolution import ResolutionRow

    from just_dna_enricher.enrich import _write_resolution_csv
    from just_dna_enricher.vrs import mint_resolution_rows

    path = sidecar_path(spec_dir, "resolution.csv", error=EnrichmentError)
    if not path.exists():
        typer.secho(f"no resolution.csv in {spec_dir} — run `enrich` first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    rows, errors, _ = load_csv_rows(path, ResolutionRow, path.name)
    if errors:
        typer.secho(f"{path.name} is invalid: {errors[0]}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    result = mint_resolution_rows(rows, offline=offline)
    _write_resolution_csv(rows, path)
    typer.secho(f"minted: {path}", fg=typer.colors.GREEN)
    typer.echo(
        f"stdlib: {result.minted_stdlib}  normalized: {result.minted_normalized}  "
        f"unmintable: {result.skipped_unmintable}  already present: {result.already_present}"
    )
    typer.echo(f"coverage: {result.identified}/{result.alleles} allele(s) carry a ga4gh:VA. id")
    for line in result.coverage_warnings():
        typer.secho(f"  warning: {line}", fg=typer.colors.YELLOW, err=True)
    for mismatch in result.mismatches:
        typer.secho(f"  mismatch: {mismatch}", fg=typer.colors.YELLOW, err=True)
    try:
        record_verification([_mint_record(result)], spec_dir, error=EnrichmentError)
    except EnrichmentError as exc:
        # The mint did **not** fail — the ids are on disk and the line above says so. What failed is
        # the attestation, and the only way this raises is a module carrying `verification.json` in
        # both legal places, which is a defect in the module's layout rather than in this run. Naming
        # the mint here would tell the author the opposite of what happened.
        typer.secho(f"MINTED, BUT NOT ATTESTED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
