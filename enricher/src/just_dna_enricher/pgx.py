"""`enrich-pgx` — verify a module's star-allele tables against PharmVar/CPIC, and record the terms.

The fourth enrichment pass, and the first whose *primary* output is `sources.csv` rather than facts.
It does two jobs, in the shape the tier already uses everywhere else:

1. **Verify, never repair.** An authored `allele_function.csv` says CYP2C19 `*2` has no function; this
   pass asks PharmVar and CPIC whether they agree and reports the difference. Severity follows the
   mode (`best_effort` warns, `strict` refuses), with one deliberate exception below.
2. **Record the terms.** Every source consulted emits a `SourceRow`, so the compiled module carries a
   machine-readable statement of what it was built from and under what declaration.

**Generation is deliberately not automatic.** The PGx tables are *authored* `_TABLE_KINDS`, not fact
sidecars — they carry `AuthoredModel` semantics, the reserved-namespace guard and raw-byte input
hashing. Having a network pass write them would blur exactly the authored/derived line the 0.5 rework
drew, and would hand the human author a file they never wrote but are accountable for. So `scaffold`
is a separate, explicit call that emits a starting CSV for a human to own, and the automatic pass only
ever reads.

**The function-status cross-check warns in both modes**, joining the ClinVar `clin_sig` exception.
The reason is the same one: PharmVar and CPIC genuinely disagree about some alleles — they are
different expert panels applying different evidence criteria, and CPIC assigns a clinical function
while PharmVar assigns a molecular one. Failing a compile over that would make the format arbitrate a
scientific disagreement between the two authorities it depends on. The finding names both callers so a
reader can weigh it.

Source order for the star-allele layer is **PharmVar then CPIC**, on data-authority grounds: PharmVar
is the naming authority for CYP star alleles. It is *not* a licensing preference — both are CC BY-SA
with a bar on sale, and neither makes a module sellable.
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import _load_csv_rows
from just_dna_format.pgx import AlleleFunctionRow, HaplotypeRow
from just_dna_format.sources import SourceRow

from just_dna_enricher.cpic import CpicClient, CpicError
from just_dna_enricher.licensing import (
    CPIC_TERMS,
    PHARMVAR_TERMS,
    LicenseRefusal,
    SourceTerms,
    check_declared_use,
)
from just_dna_enricher.pharmvar import PharmVarClient, PharmVarError

logger = logging.getLogger(__name__)

_SOURCES_FIELDNAMES = [
    "source", "layer", "license", "license_url", "license_sha256", "attribution", "notice",
    "share_alike", "commercial_use", "declared_use", "dataset", "fetched_at",
]


class PgxEnrichmentError(RuntimeError):
    """Raised in strict mode when the PGx cross-check finds a discrepancy it will not carry."""


@dataclass
class FunctionConflict:
    """An authored allele function that a nomenclature authority does not support."""

    gene: str
    allele: str
    authored: Optional[str]
    reported: Optional[str]
    source: str

    def __str__(self) -> str:
        return (
            f"{self.gene}{self.allele}: module says {self.authored!r}, {self.source} says "
            f"{self.reported!r}"
        )


@dataclass
class PgxResult:
    rows: list[SourceRow] = field(default_factory=list)
    conflicts: list[FunctionConflict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    declared_use: str = "unstated"


def _module_genes(spec_dir: Path) -> list[str]:
    """The genes the module is about, from its own PGx tables, in first-occurrence order.

    Scope comes from the module saying which genes it covers; querying anything else would invent
    scope the author did not ask for (the same rule the gene-metrics pass follows).
    """
    genes: list[str] = []
    for name, model, attr in (
        ("allele_function.csv", AlleleFunctionRow, "gene"),
        ("haplotypes.csv", HaplotypeRow, "gene"),
    ):
        path = spec_dir / name
        if not path.exists():
            continue
        rows, errors, _ = _load_csv_rows(path, model, name)
        if errors:
            raise PgxEnrichmentError(f"{name} is invalid: {errors[0]}")
        for row in rows:
            value = getattr(row, attr, None)
            if value and value not in genes:
                genes.append(value)
    return genes


def _authored_functions(spec_dir: Path) -> list[AlleleFunctionRow]:
    path = spec_dir / "allele_function.csv"
    if not path.exists():
        return []
    rows, errors, _ = _load_csv_rows(path, AlleleFunctionRow, "allele_function.csv")
    if errors:
        raise PgxEnrichmentError(f"allele_function.csv is invalid: {errors[0]}")
    return rows


def _normalize_allele(gene: str, allele: str) -> str:
    """`CYP2C19*2` and `*2` are the same allele — PharmVar prefixes the gene, this workspace does not."""
    return allele[len(gene):] if allele.startswith(gene) else allele


def _compare(
    authored: list[AlleleFunctionRow],
    reported: dict[tuple[str, str], Optional[str]],
    source: str,
) -> list[FunctionConflict]:
    """Authored function vs a source's, for the alleles both name. Silence where either is unknown."""
    conflicts: list[FunctionConflict] = []
    for row in authored:
        if row.function_status is None:
            continue
        theirs = reported.get((row.gene, row.allele))
        if theirs is not None and theirs != row.function_status:
            conflicts.append(
                FunctionConflict(row.gene, row.allele, row.function_status, theirs, source)
            )
    return conflicts


def enrich_pgx(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    declared_use: str = "unstated",
    use_pharmvar: bool = True,
    use_cpic: bool = True,
    write: bool = True,
    pharmvar_client: Optional[PharmVarClient] = None,
    cpic_client: Optional[CpicClient] = None,
) -> PgxResult:
    """Cross-check the module's PGx tables and record what was consulted, into `sources.csv`.

    `declared_use` is a third orthogonal axis, never folded into `mode`: `mode` says how hard to fail
    on a finding, this says who is using the data and why. A source that forbids sale is *skipped*
    when nothing was declared (conservative — the tool must not assert a purpose for the user) and
    *refuses* when `commercial` was declared (a direct contradiction).
    """
    spec_dir = Path(spec_dir)
    result = PgxResult(mode=mode, declared_use=declared_use)

    if offline:
        result.warnings.append(
            "PGx cross-check skipped: --offline. PharmVar and CPIC are live-only (no snapshot), so "
            "this pass is a no-op offline rather than a failure."
        )
        return result

    genes = _module_genes(spec_dir)
    if not genes:
        result.warnings.append(
            "PGx cross-check skipped: the module names no genes in allele_function.csv or "
            "haplotypes.csv, so there is nothing to check against."
        )
        return result
    authored = _authored_functions(spec_dir)

    # Existing rows are authoritative and are never clobbered, matching `enrich()`.
    existing_path = spec_dir / "sources.csv"
    existing: dict[tuple[str, str], SourceRow] = {}
    if existing_path.exists():
        rows, errors, _ = _load_csv_rows(existing_path, SourceRow, "sources.csv")
        if errors:
            raise PgxEnrichmentError(f"existing sources.csv is invalid: {errors[0]}")
        existing = {(r.source, r.layer): r for r in rows}

    emitted: list[SourceRow] = []

    def consult(terms: SourceTerms, enabled: bool, fetch) -> None:
        """Run one source through the declared-use gate, then its fetch. Records terms either way."""
        if not enabled:
            return
        reason = check_declared_use(terms, declared_use)  # raises LicenseRefusal on `commercial`
        if reason is not None:
            result.skipped.append(reason)
            logger.warning("%s", reason)
            return
        try:
            reported, notes = fetch()
        except (PharmVarError, CpicError) as exc:
            # One source failing must not sink the pass — the other may still answer.
            result.warnings.append(f"{terms.source} unavailable ({exc}); continuing without it.")
            return
        result.warnings.extend(notes)
        result.conflicts.extend(_compare(authored, reported, terms.source))
        emitted.append(terms.row("annotation", declared_use=declared_use))

    def _pharmvar() -> tuple[dict[tuple[str, str], Optional[str]], list[str]]:
        owned = pharmvar_client is None
        client = pharmvar_client or PharmVarClient()
        if not client.configured:
            if owned:
                client.close()
            raise PharmVarError(
                "no PharmVar API key: set PHARMVAR_API_KEY (the key is personal to your account "
                "and is never stored in a module)"
            )
        try:
            reported: dict[tuple[str, str], Optional[str]] = {}
            for gene in genes:
                for allele in client.alleles_for_gene(gene):
                    key = (allele.gene, _normalize_allele(allele.gene, allele.allele))
                    reported[key] = (allele.function or "").replace(" ", "_").lower() or None
            return reported, []
        finally:
            if owned:
                client.close()

    def _cpic() -> tuple[dict[tuple[str, str], Optional[str]], list[str]]:
        owned = cpic_client is None
        client = cpic_client or CpicClient()
        try:
            reported: dict[tuple[str, str], Optional[str]] = {}
            for gene in genes:
                for allele in client.alleles_for_gene(gene):
                    reported[(allele.gene, allele.allele)] = allele.function_status
            return reported, []
        finally:
            if owned:
                client.close()

    # PharmVar first on data-authority grounds (the naming authority for CYP star alleles), not
    # licensing — neither source is sellable.
    consult(PHARMVAR_TERMS, use_pharmvar, _pharmvar)
    consult(CPIC_TERMS, use_cpic, _cpic)

    for conflict in result.conflicts:
        logger.warning("PGx allele-function difference — %s", conflict)

    # Merge, never clobber: an existing row for the same (source, layer) wins.
    merged = dict(existing)
    for row in emitted:
        merged.setdefault((row.source, row.layer), row)
    result.rows = [merged[key] for key in sorted(merged)]

    if write and result.rows:
        _write_sources_csv(result.rows, spec_dir / "sources.csv")
    return result


def _write_sources_csv(rows: list[SourceRow], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_SOURCES_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow(
                {
                    name: (
                        ""
                        if dumped.get(name) is None
                        else ("true" if dumped[name] is True else
                              "false" if dumped[name] is False else dumped[name])
                    )
                    for name in _SOURCES_FIELDNAMES
                }
            )
