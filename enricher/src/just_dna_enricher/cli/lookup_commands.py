"""Read-only lookups: the `hint` and `litvar` groups (RM260 split this out of the former single-file
`cli.py`).
"""

import json
from pathlib import Path

import typer

from just_dna_enricher.enrich import EnrichmentError
from just_dna_enricher.grch37 import GRCH37_BUILD
from just_dna_enricher.litvar import LitvarClient, LitvarError, check_literature_coverage, coverage_reason
from just_dna_enricher.litvar import verification_records as litvar_records
from just_dna_enricher.lookup import (
    as_report_rows,
    lookup_citation,
    lookup_gene,
    lookup_old_assembly,
    lookup_trait,
    lookup_variant,
)
from just_dna_enricher.verification import record_verification

# ── Authoring lookups (0.5): questions about a value, never an edit to one ───────────────────────
hint_app = typer.Typer(help="Look up what is known about a variant or citation. Writes nothing.")


def _echo_hint(hint: object) -> None:
    """Findings to stderr, advisory answers to stdout — so a pipe carries the answers alone."""
    colours = {"error": typer.colors.RED, "warning": typer.colors.YELLOW, "info": typer.colors.BLUE}
    for row in as_report_rows(hint):
        typer.echo(f"{row['column']}\t{row['value']}\t[{row['refusal']}, from {row['source']}]")
    for finding in getattr(hint, "findings", []):
        typer.secho(f"  {finding.level}: {finding.message}", fg=colours[finding.level], err=True)


@hint_app.command("variant")
def hint_variant_(
    rsid: str | None = typer.Option(None, "--rsid", help="dbSNP id to look up."),
    chrom: str | None = typer.Option(None, "--chrom", help="Chromosome (with --start)."),
    start: int | None = typer.Option(None, "--start", help="1-based position (with --chrom)."),
    ref: str | None = typer.Option(None, "--ref", help="Reference allele, for an allele-exact lookup."),
    alts: str | None = typer.Option(None, "--alts", help="Alt allele(s), comma-separated."),
    ambiguity: bool = typer.Option(False, "--ambiguity", help="Warn when the answer is not unique."),
    frequencies: bool = typer.Option(False, "--frequencies", help="Add gnomAD populations (paced: ~6s)."),
    offline: bool = typer.Option(False, "--offline", help="Snapshots only; never touch the network."),
    ensembl_cache: Path | None = typer.Option(None, "--ensembl-cache", help="Explicit Ensembl cache."),
    clinvar_cache: Path | None = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot."),
    pubmind_cache: Path | None = typer.Option(
        None,
        "--pubmind-cache",
        help="Explicit PubMind snapshot (see `pubmind build`); $JUST_DNA_PUBMIND_CACHE otherwise.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit the full machine answer."),
) -> None:
    """Validity, coordinates, alleles, populations and clinical calls for one variant.

    Nothing is decided for you: a one-to-many rsID returns every locus and a position matching
    several rsIDs returns every candidate. The coordinate is reported, never written into
    `variants.csv` — resolution puts it in `resolution.csv`, which is where it belongs.
    """
    if rsid is None and (chrom is None or start is None):
        typer.secho("give --rsid, or --chrom and --start", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    hint = lookup_variant(
        rsid=rsid,
        chrom=chrom,
        start=start,
        ref=ref,
        alts=alts,
        ambiguity=ambiguity,
        frequencies=frequencies,
        offline=offline,
        ensembl_cache=ensembl_cache,
        clinvar_cache=clinvar_cache,
        pubmind_cache=pubmind_cache,
    )
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "rsid": hint.rsid,
                    "rsid_status": str(hint.rsid_status) if hint.rsid_status else None,
                    "loci": hint.loci,
                    "rsid_candidates": hint.rsid_candidates,
                    "populations": hint.populations,
                    "clin_sig": hint.clin_sig,
                    "pubmind": hint.pubmind,
                    "vrs_id": hint.vrs_id,
                    "ambiguous": hint.ambiguous,
                    "advisory": as_report_rows(hint),
                    "findings": [f"{f.level}: {f.message}" for f in hint.findings],
                },
                indent=2,
                default=str,
            )
        )
        return
    for locus in hint.loci:
        typer.echo(f"locus\t{locus['chrom']}:{locus['start']}\t{locus.get('ref')}>{locus.get('alts')}")
    for candidate in hint.rsid_candidates:
        typer.echo(f"rsid_candidate\t{candidate}")
    for population in hint.populations:
        af = population.get("allele_frequency")
        # The allele leads the row (S108, RM255): a multi-allelic locus answers with one row per
        # ancestry group *per allele*, and without it two different claims render identically.
        typer.echo(
            f"population\t{population.get('allele')}\t{population.get('population')}"
            f"\tAC={population.get('allele_count')}"
            f"\tAN={population.get('allele_number')}\tAF={'' if af is None else f'{af:.6g}'}"
        )
    # One line per PubMind record, never a rolled-up verdict: several records can describe one
    # position and their calls are allowed to differ, which is the finding rather than untidiness.
    for record in hint.pubmind:
        typer.echo(
            f"pubmind\t{record.get('clin_sig')}\t{record.get('pvid')}"
            f"\tconfidence={record.get('confidence')}\tderivation={record.get('derivation')}"
        )
    _echo_hint(hint)


@hint_app.command("recover")
def hint_recover_(
    chrom: str = typer.Option(..., "--chrom", help="Chromosome of the old coordinate."),
    start: int = typer.Option(..., "--start", help=f"1-based {GRCH37_BUILD} position."),
    ref: str | None = typer.Option(None, "--ref", help="Reference allele, to narrow the answer."),
    alts: str | None = typer.Option(None, "--alts", help="Alt allele(s), comma-separated."),
    offline: bool = typer.Option(False, "--offline", help="Skip the lookup and say so."),
    as_json: bool = typer.Option(False, "--json", help="Emit the full machine answer."),
) -> None:
    """Which rs-number GRCh37 dbSNP records at an hg19/GRCh37 coordinate.

    For a paper that predates GRCh38. Author the **rs-number**, not a converted position: an
    rs-number resolves into a coordinate the compiler can cross-examine, where a lifted-over position
    becomes the row's only witness to itself. Nothing is written — the rs-number is the row's
    identity, and a machine filling one migrates `variant_key` with no authored edit anywhere.
    """
    hint = lookup_old_assembly(chrom=chrom, start=start, ref=ref, alts=alts, offline=offline)
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "chrom": hint.recovery.chrom,
                    "start": hint.recovery.start,
                    "genome_build": GRCH37_BUILD,
                    "outcome": hint.recovery.outcome,
                    "rsids": hint.recovery.rsids,
                    "candidates": hint.recovery.candidates,
                    "advisory": as_report_rows(hint),
                    "findings": [f"{f.level}: {f.message}" for f in hint.findings],
                },
                indent=2,
                default=str,
            )
        )
        return
    for candidate in hint.recovery.candidates:
        typer.echo(
            f"candidate\t{candidate['rsid']}\t{GRCH37_BUILD} {hint.recovery.chrom}:"
            f"{candidate['start']}-{candidate['end']}\t{'/'.join(candidate['alleles'])}"
        )
    _echo_hint(hint)


@hint_app.command("citation")
def hint_citation_(
    pmid: str | None = typer.Option(None, "--pmid", help="PubMed id to check."),
    doi: str | None = typer.Option(None, "--doi", help="DOI to check (the one you authored)."),
    pmcid: str | None = typer.Option(
        None, "--pmcid", help="PubMed Central id (PMC…) to resolve to the PubMed id tables key on."
    ),
    offline: bool = typer.Option(False, "--offline", help="Skip the check and say so."),
    as_json: bool = typer.Option(False, "--json", help="Emit the full machine answer."),
) -> None:
    """Does this citation exist, and **is it the paper you meant**?

    A paywall hides the fulltext, never the PubMed record, so existence is answerable for paywalled
    work; Crossref covers what PubMed does not index at all. Every answer is tri-state — `unknown`
    means the registry could not be asked, which is not the same as "no such paper".

    **Existence is not identity.** PMIDs are densely allocated, so a recalled or invented number is
    very likely to be a real record for a different article, and `pmid_exists` alone cannot catch a
    fabricated citation. The title, journal, year and first author come back in the same response and
    are printed for exactly that comparison (S12).

    **`--pmcid` goes the other way.** Every `pmid` in the schema keys on the PubMed id — `studies.csv`,
    a binning row's and a `pharm_variants.csv` row's alike — and a curator holding only a `PMC…` id
    had no route to it: the schema refused the cell and named no remedy. This resolves it and then asks PubMed which paper that is. The id is **reported,
    never written**: filling `pmid` from NCBI would make the existence check compare NCBI with itself.
    """
    if pmid is None and doi is None and pmcid is None:
        typer.secho("give --pmid, --doi or --pmcid", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    hint = lookup_citation(pmid=pmid, doi=doi, pmcid=pmcid, offline=offline)
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "pmid": hint.pmid,
                    "doi": hint.doi,
                    "pmid_exists": hint.pmid_exists,
                    "doi_exists": hint.doi_exists,
                    "registry_doi": hint.registry_doi,
                    "pmcid": hint.pmcid,
                    "open_access": hint.open_access,
                    "abstract_available": hint.abstract_available,
                    "title": hint.title,
                    "journal": hint.journal,
                    "year": hint.year,
                    "first_author": hint.first_author,
                    "advisory": as_report_rows(hint),
                    "findings": [f"{f.level}: {f.message}" for f in hint.findings],
                },
                indent=2,
                default=str,
            )
        )
        return
    for label, value in (("pmid_exists", hint.pmid_exists), ("doi_exists", hint.doi_exists)):
        typer.echo(f"{label}\t{'unknown' if value is None else value}")
    if hint.pmcid:
        typer.echo(f"pmcid\t{hint.pmcid}")
    # Printed unconditionally when known: the whole point is that a caller reading prose can compare
    # what the record says against the paper they had in mind.
    for label, value in (
        ("title", hint.title),
        ("journal", hint.journal),
        ("year", hint.year),
        ("first_author", hint.first_author),
    ):
        if value:
            typer.echo(f"{label}\t{value}")
    _echo_hint(hint)


@hint_app.command("trait")
def hint_trait_(curie: str = typer.Argument(..., help="Trait CURIE, e.g. EFO_0004340")) -> None:
    """Is this trait id current, obsolete, or unknown?"""
    typer.echo(str(lookup_trait(curie)))


@hint_app.command("gene")
def hint_gene_(symbol: str = typer.Argument(..., help="Gene symbol, e.g. MTHFR")) -> None:
    """Is this gene symbol approved or retired?"""
    typer.echo(str(lookup_gene(symbol)))


# ── LitVar2 / PubTator3 (RM167) ─────────────────────────────────────────────────────────────────

litvar_app = typer.Typer(
    help=(
        "Which papers a variant-literature index holds for a module's alleles, and at which tier. "
        "Reports only; writes no authored cell and no table row."
    )
)


@litvar_app.command("coverage")
def litvar_coverage_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    offline: bool = typer.Option(
        False, "--offline", help="No network; every locus is recorded as unchecked."
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Only the tier summary, not a line per locus."),
) -> None:
    """Report LitVar's literature coverage per locus, naming the tier that answered.

    **It answers *which papers discuss an allele that is already identified*. It does not answer
    *which allele a name meant*** — those read as the same question and are not. Measured against the
    two hardest records in this repository (CIViC 1955 and 2131, four candidate alleles with
    registered CAIDs), the index returns no node for any of them, because PubTator3 mines titles and
    abstracts and those alleles live in a table inside a paywalled paper. Do not reach for this to
    recover an identity.

    Writes no row and no `sources.csv` entry: nothing here reaches a module's tables, so the module
    does not *use* this source. What it does write is `verification.json` — an attestation that the
    question was put, over how many loci, and at which tier each was answered.
    """
    try:
        report = check_literature_coverage(spec_dir, offline=offline)
    except (ValueError, LitvarError) as exc:
        typer.secho(f"LITERATURE COVERAGE FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if not report.loci:
        # No attestation, for `check-identifiers`' reason: with no rsID-bearing row there is no
        # question to record having put, and minting a nonce would create a `verification.json` on a
        # module that never asked for one.
        typer.secho("no authored table names an rsID — nothing to ask LitVar about", fg=typer.colors.YELLOW)
        return
    typer.echo(
        f"loci: {len(report.loci)}"
        f" (from {len(report.tables_read)} table(s): {', '.join(report.tables_read) or 'none'})"
    )
    for name, why in sorted(report.tables_not_read.items()):
        if why != "not present":
            typer.secho(
                f"  {name} names rsIDs and could not be read ({why}) — its loci were NOT asked about",
                fg=typer.colors.YELLOW,
                err=True,
            )
    if not quiet:
        for locus in report.loci:
            typer.echo(f"  {coverage_reason(locus)}")
            if locus.tier == "allele":
                # Both numbers, side by side and labelled. 328 and 3,945 are both true about
                # rs429358 and only one of them is about the allele in the module.
                typer.echo(
                    f"    allele-resolved: {locus.allele_pmids} paper(s); position node: "
                    f"{locus.position_pmids}; on the position node and no allele node: "
                    f"{locus.position_only_pmids}"
                )
            elif locus.tier == "position":
                typer.echo(
                    f"    position node: {locus.position_pmids} paper(s); of those, "
                    f"{locus.position_only_pmids} sit on no allele node"
                )
    for tier in ("allele", "position", "absent", "unchecked"):
        typer.echo(f"{tier}: {len(report.at(tier))}")
    typer.echo(f"papers on a position node that no allele node claims: {report.position_only_residue}")
    if report.degraded:
        typer.secho(
            f"allele-level questions answered position-level: "
            f"{', '.join(locus.rsid for locus in report.degraded)}",
            fg=typer.colors.YELLOW,
        )
    try:
        record_verification(litvar_records(report), spec_dir, error=EnrichmentError)
    except EnrichmentError as exc:
        typer.secho(f"CHECKED, BUT NOT ATTESTED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@litvar_app.command("gene")
def litvar_gene_(
    gene: str = typer.Argument(..., help="Gene symbol, e.g. HFE"),
) -> None:
    """List every node LitVar holds under a gene symbol, grouped by tier. Writes nothing.

    This is the endpoint that serves line-delimited Python `repr()` rather than JSON, and the tier
    split is the reason to look: of 588 HFE nodes on 2026-09-01, 220 are rsID-only, 69 carry a
    ClinGen allele id, exactly one is the gene node, and the remaining 298 are unnormalized protein
    strings — text a miner saw, not an identity anything should join on.
    """
    try:
        nodes = LitvarClient().gene_nodes(gene)
    except LitvarError as exc:
        typer.secho(f"LITVAR GENE LOOKUP FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if not nodes:
        typer.secho(f"LitVar holds no node under {gene}", fg=typer.colors.YELLOW)
        return
    for tier in ("clingen", "rsid", "gene", "mention"):
        at_tier = [node for node in nodes if node.tier == tier]
        papers = sum(node.pmid_count or 0 for node in at_tier)
        typer.echo(f"{tier}: {len(at_tier)} node(s), {papers} paper-node link(s)")
    typer.secho(
        "a `mention` node is an unnormalized protein string under a gene id — it names no allele, "
        "and nothing here should be joined on as an identity",
        fg=typer.colors.YELLOW,
    )
