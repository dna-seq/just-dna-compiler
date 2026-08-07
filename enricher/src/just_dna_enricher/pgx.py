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

**Snapshot first, live second, and `--offline` means the first only (RM38).** Both sources were
live-only, so `--offline` was a no-op that warned and returned, and a *hosted* enricher had exactly two
options: fetch a licence-gated source per request on the operator's own credentials, or skip the check.
Each leg now resolves a built snapshot first (`locations.resolve_{cpic,pharmvar}_reference`, or an
explicit path) and falls back to the live service only when there is none and the run is online. No
second flag: `--offline` is the switch and an explicit cache path is the inject-only escape hatch.

The route is **recorded, not implied** — `PgxResult.routes` says which answered, and a snapshot stamps
its release into `SourceRow.dataset`, the way the two gnomAD constraint routes already do. A consumer
must be able to tell a pinned file from a live API, because the two can differ by a release.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.pgx import AlleleFunctionRow, HaplotypeRow
from just_dna_format.sources import SourceRow

from just_dna_enricher.cpic import CpicClient, CpicError, CpicSnapshotClient
from just_dna_enricher.licensing import (
    CPIC_TERMS,
    PHARMVAR_TERMS,
    SourceTerms,
    check_declared_use,
    write_sources_csv,
)
from just_dna_enricher.locations import resolve_cpic_reference, resolve_pharmvar_reference
from just_dna_enricher.pharmvar import PharmVarClient, PharmVarError, PharmVarSnapshotClient

logger = logging.getLogger(__name__)


class PgxEnrichmentError(RuntimeError):
    """Raised in strict mode when the PGx cross-check finds a discrepancy it will not carry."""


@dataclass
class FunctionConflict:
    """An authored allele function that a nomenclature authority does not support."""

    gene: str
    allele: str
    authored: str | None
    reported: str | None
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
    #: `source -> "snapshot" | "live"` for each leg that actually answered (RM38). A first-class
    #: answer rather than a log line: on a hosted deployment "did this reach PharmVar live?" is the
    #: question the whole cache exists to make answerable, and a caller renders it.
    routes: dict[str, str] = field(default_factory=dict)
    #: Legs that could run neither offline nor live, and why. Distinct from `skipped` (a licensing
    #: refusal) and from a `warning` (the source answered and something was odd) — tri-state, as
    #: everywhere: "did not run" is not "ran and found nothing".
    skipped_offline: list[str] = field(default_factory=list)


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
        rows, errors, _ = load_csv_rows(path, model, name)
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
    rows, errors, _ = load_csv_rows(path, AlleleFunctionRow, "allele_function.csv")
    if errors:
        raise PgxEnrichmentError(f"allele_function.csv is invalid: {errors[0]}")
    return rows


def _normalize_allele(gene: str, allele: str) -> str:
    """`CYP2C19*2` and `*2` are the same allele — PharmVar prefixes the gene, this workspace does not."""
    return allele.removeprefix(gene)


def _compare(
    authored: list[AlleleFunctionRow],
    reported: dict[tuple[str, str], str | None],
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
    cpic_cache: Path | None = None,
    pharmvar_cache: Path | None = None,
    pharmvar_client: PharmVarClient | PharmVarSnapshotClient | None = None,
    cpic_client: CpicClient | CpicSnapshotClient | None = None,
) -> PgxResult:
    """Cross-check the module's PGx tables and record what was consulted, into `sources.csv`.

    `declared_use` is a third orthogonal axis, never folded into `mode`: `mode` says how hard to fail
    on a finding, this says who is using the data and why. A source that forbids sale is *skipped*
    when nothing was declared (conservative — the tool must not assert a purpose for the user) and
    *refuses* when `commercial` was declared (a direct contradiction).

    `offline` is real as of 0.5.1: each leg resolves a built snapshot first and only reaches the live
    service when there is none and the run is online. Offline with no snapshot is a **skip with a
    reason** (`skipped_offline`), never a silent pass and never a failure — a source the deployment
    cannot reach is not a finding about the module.
    """
    spec_dir = Path(spec_dir)
    result = PgxResult(mode=mode, declared_use=declared_use)

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
        rows, errors, _ = load_csv_rows(existing_path, SourceRow, "sources.csv")
        if errors:
            raise PgxEnrichmentError(f"existing sources.csv is invalid: {errors[0]}")
        existing = {(r.source, r.layer): r for r in rows}

    emitted: list[SourceRow] = []

    def consult(terms: SourceTerms, enabled: bool, resolve, read) -> None:
        """Gate one source on the declared use, pick its route, read it. Records terms either way.

        `resolve` returns `(client, owned, route)` or `None` when neither a snapshot nor a live route
        is available — which is a *skip with a reason*, not a failure.
        """
        if not enabled:
            return
        reason = check_declared_use(terms, declared_use)  # raises LicenseRefusal on `commercial`
        if reason is not None:
            result.skipped.append(reason)
            logger.warning("%s", reason)
            return
        try:
            resolved = resolve()
        except (PharmVarError, CpicError) as exc:
            result.warnings.append(f"{terms.source} unavailable ({exc}); continuing without it.")
            return
        if resolved is None:
            note = (
                f"{terms.source}: skipped — --offline and no built snapshot. Build one with "
                f"`just-dna-enricher {terms.source} build`, or point at it with "
                f"$JUST_DNA_{terms.source.upper()}_CACHE."
            )
            result.skipped_offline.append(note)
            logger.warning("%s", note)
            return
        client, owned, route = resolved
        try:
            reported, notes = read(client)
        except (PharmVarError, CpicError) as exc:
            # One source failing must not sink the pass — the other may still answer.
            result.warnings.append(f"{terms.source} unavailable ({exc}); continuing without it.")
            return
        finally:
            if owned:
                client.close()
        result.routes[terms.source] = route
        result.warnings.extend(notes)
        result.conflicts.extend(_compare(authored, reported, terms.source))
        emitted.append(
            terms.row(
                "annotation",
                declared_use=declared_use,
                dataset=getattr(client, "dataset", None),
            )
        )

    def _injected(client) -> tuple[object, bool, str] | None:
        """An injected client's route — and `None` when `offline` forbids using it.

        **`offline` wins over an injection, and the type is what decides.** An injected client is the
        inject-only escape hatch, but a *live* one under `--offline` would egress from a run documented
        as making none, which is the whole failure RM38 exists to close. A snapshot client is exempt
        because reading a local parquet is not egress. Not decided on `configured`: a live client with a
        perfectly good key is exactly the one that must not be used here.
        """
        if client is None:
            return None
        is_snapshot = isinstance(client, CpicSnapshotClient | PharmVarSnapshotClient)
        if offline and not is_snapshot:
            return None
        return client, False, "snapshot" if is_snapshot else "injected"

    def _resolve_pharmvar():
        if pharmvar_client is not None:
            resolved = _injected(pharmvar_client)
            # "No key" is still the caller's answer to hear: a keyless client would 401 every gene, and
            # the CPIC leg must survive that. `PharmVarSnapshotClient.configured` is True, so a
            # snapshot passes unchanged.
            if resolved is not None and not pharmvar_client.configured:
                raise PharmVarError(
                    "no PharmVar API key: set PHARMVAR_API_KEY (the key is personal to your account "
                    "and is never stored in a module)"
                )
            return resolved
        reference = resolve_pharmvar_reference(pharmvar_cache)
        if reference is not None:
            return PharmVarSnapshotClient(reference), True, "snapshot"
        if offline:
            return None
        client = PharmVarClient()
        if not client.configured:
            client.close()
            raise PharmVarError(
                "no PharmVar API key: set PHARMVAR_API_KEY (the key is personal to your account "
                "and is never stored in a module), or build a snapshot with "
                "`just-dna-enricher pharmvar build`"
            )
        return client, True, "live"

    def _resolve_cpic():
        if cpic_client is not None:
            return _injected(cpic_client)
        reference = resolve_cpic_reference(cpic_cache)
        if reference is not None:
            return CpicSnapshotClient(reference), True, "snapshot"
        if offline:
            return None
        return CpicClient(), True, "live"

    def _read_pharmvar(client) -> tuple[dict[tuple[str, str], str | None], list[str]]:
        reported: dict[tuple[str, str], str | None] = {}
        for gene in genes:
            for allele in client.alleles_for_gene(gene):
                key = (allele.gene, _normalize_allele(allele.gene, allele.allele))
                reported[key] = (allele.function or "").replace(" ", "_").lower() or None
        return reported, []

    def _read_cpic(client) -> tuple[dict[tuple[str, str], str | None], list[str]]:
        reported: dict[tuple[str, str], str | None] = {}
        for gene in genes:
            for allele in client.alleles_for_gene(gene):
                reported[(allele.gene, allele.allele)] = allele.function_status
        return reported, []

    # PharmVar first on data-authority grounds (the naming authority for CYP star alleles), not
    # licensing — neither source is sellable.
    consult(PHARMVAR_TERMS, use_pharmvar, _resolve_pharmvar, _read_pharmvar)
    consult(CPIC_TERMS, use_cpic, _resolve_cpic, _read_cpic)

    for conflict in result.conflicts:
        logger.warning("PGx allele-function difference — %s", conflict)

    # Merge, never clobber: an existing row for the same (source, layer) wins.
    merged: dict[tuple[str, str], SourceRow] = dict(existing)
    for row in emitted:
        merged.setdefault((row.source, row.layer), row)
    result.rows = [merged[key] for key in sorted(merged)]

    if write and result.rows:
        write_sources_csv(result.rows, spec_dir / "sources.csv")
    return result
