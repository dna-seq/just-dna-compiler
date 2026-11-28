"""Compare the resolution of each authored HLA allele name with the curators' release."""

import csv
import logging
from dataclasses import dataclass, replace
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_compiler.compiler.tables import _TABLE_KINDS
from just_dna_format.findings import CodedWarning
from just_dna_format.pgx import HLA_ALLELE_PATTERN, HLA_GENE_PREFIX, AlleleFunctionRow, is_hla_gene
from just_dna_format.spelling import gene_key

from just_dna_enricher.download import ensure_ipd_imgt_hla_snapshot
from just_dna_enricher.ipd_imgt_hla_build import AlleleLists, IpdHlaUnavailable, load_lists
from just_dna_enricher.licensing import (
    IPD_IMGT_HLA_TERMS,
    effective_declared_use,
    merge_sources_file,
    withdraw_stale_dataset,
)
from just_dna_enricher.locations import resolve_ipd_imgt_hla_reference
from just_dna_enricher.net import could_not_ask_reason
from just_dna_enricher.verification import examples

logger = logging.getLogger(__name__)


def authored_names(
    directory: Path, *, error: type[Exception], tables_read: list[str] | None = None
) -> set[str]:
    """Read IPD names at their authored resolution and record the tables successfully loaded."""
    names: set[str] = set()
    for filename, _, model in _TABLE_KINDS:
        if not issubclass(model, AlleleFunctionRow) or not (directory / filename).exists():
            continue
        try:
            rows, errors, _ = load_csv_rows(directory / filename, model, filename)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise error(f"{filename} could not be read: {exc}") from exc
        if errors:
            raise error(f"{filename} is invalid: {errors[0]}")
        if tables_read is not None:
            tables_read.append(filename)
        names.update(
            gene_key(row.gene)[len(HLA_GENE_PREFIX) :].upper() + row.allele
            for row in rows
            if is_hla_gene(row.gene) and HLA_ALLELE_PATTERN.fullmatch(row.allele)
        )
    return names


def _assignments(listed: set[str]) -> set[str]:
    """A shorter name can specify an expression suffix. Match it at its own resolution."""
    assignments = listed.copy()
    for name in listed:
        gene, star, allele = name.partition("*")
        parsed = HLA_ALLELE_PATTERN.fullmatch(star + allele)
        if parsed is None:  # the upstream list also contains names outside RM334's authored grammar
            continue
        fields = parsed["fields"].split(":")
        for width in range(2, len(fields)):
            prefix = gene + "*" + ":".join(fields[:width])
            assignments.add(prefix)
            assignments.add(prefix + parsed["suffix"])
    return assignments


@dataclass(frozen=True)
class HlaAssignmentCheck:
    """The assignment check's subjects and findings. Zero means all names were assigned. None withholds the count."""

    subjects: int
    findings: int | None
    detail: str
    release: str | None = None
    notice: str | None = None
    skipped: str | None = None
    licence_text: str | None = None
    assigned_summary: str | None = None


def compare(names: set[str], lists: AlleleLists) -> HlaAssignmentCheck:
    """Count deleted and unassigned names in this release after matching assignments at authored resolution."""
    assigned = names & _assignments(lists.assigned)
    deleted = (names - assigned) & lists.deleted.keys()
    absent = names - assigned - deleted
    assigned_summary = (
        f"{len(assigned)} assigned HLA allele name(s) in {lists.release}: {examples(sorted(assigned))}"
        if assigned
        else None
    )
    summary = [assigned_summary] if assigned_summary else []
    warnings: list[CodedWarning] = []
    if deleted:
        quoted = [f"{name} ({lists.deleted[name]!r})" for name in sorted(deleted)]
        warnings.append(
            CodedWarning(
                "hla_allele_deleted",
                f"{len(deleted)} deleted HLA allele name(s) in {lists.release}: {examples(quoted)}",
            )
        )
    if absent:
        warnings.append(
            CodedWarning(
                "hla_allele_not_assigned",
                f"{len(absent)} HLA allele name(s) not assigned in release {lists.release}: {examples(sorted(absent))}",
            )
        )
    for warning in warnings:
        logger.warning("%s: %s", warning.code, warning)
        summary.append(f"{warning.code}: {warning}")
    return HlaAssignmentCheck(
        len(names),
        len(deleted) + len(absent),
        "\n".join(summary),
        lists.release,
        lists.notice,
        assigned_summary=assigned_summary,
        licence_text=lists.licence_text,
    )


def check_names(
    directory: Path, names: set[str], *, offline: bool, download: bool
) -> HlaAssignmentCheck | None:
    """Check names against the local or requested snapshot. An empty roster returns None.

    A roster with no usable reference returns a check with findings=None and the reason it was skipped.
    """
    if not names:
        return None
    reference = resolve_ipd_imgt_hla_reference()
    try:
        if reference is None and download and not offline:
            declared, _ = effective_declared_use(directory, IPD_IMGT_HLA_TERMS, "unstated")
            reference = ensure_ipd_imgt_hla_snapshot(declared_use=declared)
        if reference is not None:
            return compare(names, load_lists(reference))
        reason = "offline" if offline else "no_reference"
        why = "no local snapshot"
    except (IpdHlaUnavailable, OSError) as exc:
        reason = could_not_ask_reason(exc)
        why = str(exc)
    detail = (
        f"could not ask IPD-IMGT/HLA about {len(names)} allele name(s) ({examples(sorted(names))}): {why}"
    )
    logger.warning("%s", detail)
    return HlaAssignmentCheck(len(names), None, detail, skipped=reason)


def check_module_names(directory: Path, *, offline: bool, download: bool) -> HlaAssignmentCheck | None:
    """Report the actual roster alongside its answer, including why an input could not be read."""
    tables: list[str] = []
    try:
        names = authored_names(directory, error=IpdHlaUnavailable, tables_read=tables)
    except IpdHlaUnavailable as exc:
        detail = f"Could not check HLA assignments: {exc}"
        logger.warning("%s", detail)
        return HlaAssignmentCheck(0, None, detail, skipped="unsupported")
    check = check_names(directory, names, offline=offline, download=download)
    if check is None:
        return None
    return replace(check, detail=f"Names read from {', '.join(tables)}.\n{check.detail}")


def record_attribution(
    directory: Path, release: str, notice: str, licence_text: str, *, error: type[Exception]
) -> None:
    """As with the PGx checks, credit the source at the annotation layer only when it answered."""
    required_notice = notice.strip()
    terms = replace(IPD_IMGT_HLA_TERMS, notice=required_notice)
    declared, _ = effective_declared_use(directory, terms, "unstated")
    row = terms.row("annotation", declared_use=declared, dataset=release, license_text=licence_text)
    # Merged and never clobbered: a licence row the author already wrote keeps its own notice
    # (@sidecar-authoritative); `license_sha256` pins the full tagged licence either way.
    merge_sources_file([row], directory, error=error)
    withdraw_stale_dataset(directory, terms.source, "annotation", release, error=error)
