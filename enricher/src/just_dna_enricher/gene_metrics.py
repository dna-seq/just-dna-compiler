"""`enrich-gene-metrics` — the third pass: the module's genes in, `gene_metrics.csv` out.

The gene-level sibling of the frequency pass, and the one gnomAD role that works **fully offline**.
The difference is size, not principle: a frequency slice of v4.1 would be tens to hundreds of
gigabytes, while gene-level constraint is one row per gene — a few megabytes as parquet. So this pass
gets the ClinVar treatment (a `[dev]` builder plus a cached snapshot, `constraint_build`) with the
live API as the fallback, rather than the other way round.

Snapshot first, live second — the same ordering rule the resolver chain uses, and for the same reason:
a local hit costs nothing and leaves the rate limit alone for the passes that genuinely need it.

**The two routes are not interchangeable, and the table says so.** Checked against both: the bulk v4.1
file and the live `gnomad_constraint` field return different numbers for the same gene on the same
MANE transcript, because the live field serves **v2.1.1** constraint while v4.1 constraint ships only
in the bulk file. So a row records which release it came from in `dataset` — `gnomad_v4.1_constraint`
from the snapshot, `gnomad_v2.1.1_constraint` from the API — and a module that gets the API fallback
because no snapshot was provisioned can *see* that it holds older numbers rather than silently
believing they are v4.1. This is exactly the confusion `dataset` is in the fact set to prevent.

The gene set comes from the `gene` column of `variants.csv`. That is the module *saying which genes it
is about*; querying anything else would be inventing scope the author did not ask for.
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.normalize import now_utc_iso
from just_dna_format.spec import VariantRow

from just_dna_enricher.download import ensure_constraint_snapshot
from just_dna_enricher.gnomad import (
    API_CONSTRAINT_DATASET_LABEL,
    CONSTRAINT_DATASET_LABEL,
    GnomadClient,
    GnomadError,
)
from just_dna_enricher.licensing import record_source_terms, sidecar_path
from just_dna_enricher.locations import resolve_constraint_reference

logger = logging.getLogger(__name__)

_FIELDNAMES = [
    "gene", "gene_id", "transcript", "mane_select",
    "pli", "loeuf", "oe_lof", "oe_lof_lower", "lof_z", "mis_z", "syn_z", "oe_mis",
    "obs_lof", "exp_lof", "constraint_flags",
    # 0.5: ClinGen's columns. This pass never fills them, but it REWRITES THE WHOLE TABLE, so leaving
    # them out of the field list would silently strip every row `clingen.py` wrote.
    "haploinsufficiency", "triplosensitivity",
    "dataset", "source", "status", "fetched_at",
]
# The metric columns the snapshot and the live route both fill, so one writer serves both.
_METRIC_FIELDS = (
    "gene_id", "transcript", "mane_select", "pli", "loeuf", "oe_lof", "oe_lof_lower",
    "lof_z", "mis_z", "syn_z", "oe_mis", "obs_lof", "exp_lof", "constraint_flags",
)


class GeneMetricsEnrichmentError(RuntimeError):
    """Raised in strict mode when a module gene gets no constraint metrics."""


class GeneMetricsUnavailable(GeneMetricsEnrichmentError):
    """The gnomAD constraint API could not be reached, so the question was not put (RM101).

    A subclass rather than a second exception, so every existing `except GeneMetricsEnrichmentError` still
    catches it (P3 — additive within a major). It exists because this pass could fail two ways that
    want different responses and had one type for both: **the API was asked and never answered**, and a module gene genuinely has no constraint metrics under `strict`. Only this one means the
    source was asked and never answered.

    Before RM101 this case did not reach `GeneMetricsEnrichmentError` at all — a `GnomadError` travelled straight out
    through a `try/finally` with no `except`, so a caller's handler, written against the type this
    module documents, was silent for exactly the failure it was written for.
    """


@dataclass
class GeneMetricsResult:
    rows: list[GeneMetricsRow]
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    # Genes **no route was consulted about** — an offline run with no constraint snapshot, where the
    # snapshot link has no reference and the API link is gated off (RM98). Kept apart from `missing`,
    # which means gnomAD was asked and has no constraint: that is a real and common fact about small
    # or non-coding genes, and this is the absence of a question. These genes appear in `missing` too,
    # because `strict` must still refuse a run that established nothing, but no ROW is written for
    # them -- a `not_found` row here would name a release nobody opened.
    unconsulted: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    mode: str = "best_effort"


def module_genes(spec_dir: Path) -> list[str]:
    """The module's gene symbols, de-duplicated in first-occurrence order (P7: never set order)."""
    variants_path = Path(spec_dir) / "variants.csv"
    if not variants_path.exists():
        return []
    variants, errors, _ = load_csv_rows(variants_path, VariantRow, "variants.csv")
    if errors:
        raise GeneMetricsEnrichmentError(f"variants.csv is invalid: {errors[0]}")
    seen: set[str] = set()
    out: list[str] = []
    for row in variants:
        gene = (row.gene or "").strip()
        if gene and gene not in seen:
            seen.add(gene)
            out.append(gene)
    return out


def lookup_snapshot(reference: Path, genes: list[str]) -> dict[str, dict]:
    """`gene symbol -> metrics dict` from the offline constraint snapshot. Never fetches.

    Mirrors `clinvar.lookup_loci`'s shape: a batch lookup over an injected parquet directory via an
    in-memory DuckDB view, so the core install stays polars-free (polars is the builder's, `[dev]`).
    """
    if not genes:
        return {}
    parquet = _snapshot_parquet(reference)
    if parquet is None:
        return {}
    con = duckdb.connect(":memory:")
    try:
        pattern = str(parquet).replace("'", "''")
        con.execute(f"CREATE VIEW constraint_metrics AS SELECT * FROM read_parquet('{pattern}')")
        placeholders = ", ".join("?" for _ in genes)
        rows = con.execute(
            f"SELECT * FROM constraint_metrics WHERE gene IN ({placeholders}) ORDER BY gene",
            genes,
        ).fetchall()
        columns = [d[0] for d in con.description]
    finally:
        con.close()
    records = [dict(zip(columns, row, strict=True)) for row in rows]
    return {record["gene"]: record for record in records}


def _snapshot_parquet(reference: Path | None) -> str | None:
    """The glob a DuckDB view should read for a provisioned constraint snapshot, or `None`."""
    if reference is None:
        return None
    reference = Path(reference)
    if reference.is_file() and reference.suffix == ".parquet":
        return str(reference)
    for candidate in (reference / "data", reference):
        if candidate.is_dir() and any(candidate.glob("*.parquet")):
            return f"{candidate}/*.parquet"
    return None


def enrich_gene_metrics(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    constraint_cache: Path | None = None,
    dataset: str = CONSTRAINT_DATASET_LABEL,
    download: bool = True,
    write: bool = True,
    client: GnomadClient | None = None,
) -> GeneMetricsResult:
    """Fill `gene_metrics.csv` for the genes `variants.csv` mentions.

    Existing rows are authoritative and merged, never clobbered — the same rule the other two passes
    apply. `offline` restricts the chain to the snapshot, which (unlike the frequency pass) can still
    produce a complete table when one is provisioned.

    `download` provisions the published v4.1 snapshot when no local one is found, exactly as `enrich()`
    does for the Ensembl and ClinVar snapshots — `--offline` is the switch that turns it off, and there
    is deliberately no separate CLI flag for the same reason there is none there.
    """
    spec_dir = Path(spec_dir)
    # Through the resolver, never joined by hand (RM99): a module keeping its sidecars under
    # `derived/` (RM49) has this file there, and a pass with its own literal would read the split copy
    # and write a flat one, leaving the module with both -- the collision RM49 made an error rather
    # than a preference. `@sidecar-name-and-place`: write to the file you read.
    output_path = sidecar_path(spec_dir, "gene_metrics.csv", error=GeneMetricsEnrichmentError)

    # Keyed by (gene, dataset), not by gene: one gene legitimately carries a row per authority — a
    # gnomAD constraint row and a ClinGen dosage row make different statements about it. Keying on the
    # gene alone made a second authority's row look like this pass's own work and suppressed the fetch.
    existing: dict[tuple[str, str], GeneMetricsRow] = {}
    if output_path.exists():
        rows, errors, _ = load_csv_rows(output_path, GeneMetricsRow, "gene_metrics.csv")
        if errors:
            raise GeneMetricsEnrichmentError(f"existing gene_metrics.csv is invalid: {errors[0]}")
        for row in rows:
            existing[(row.gene, row.dataset)] = row

    genes = module_genes(spec_dir)
    # "Already done" means done *by this pass*, judged on the route that wrote the row rather than on
    # the dataset label (which differs between the snapshot and the API routes).
    done = {row.gene for row in existing.values() if (row.source or "").startswith("gnomad")}
    wanted = [g for g in genes if g not in done]
    fetched_at = now_utc_iso()
    out: list[GeneMetricsRow] = list(existing.values())
    covered: list[str] = []
    missing: list[str] = []

    # ── snapshot link (offline-capable, first) ─────────────────────────────────────────────────
    from_snapshot: dict[str, dict] = {}
    if wanted:
        reference = resolve_constraint_reference(constraint_cache)
        if reference is None and not offline and download:
            # **Provisioning, wired the same way `enrich()` wires the other two snapshots.**
            # `download.ensure_constraint_snapshot` existed from the day the download body was
            # generalized and had no caller, so a plain install fell straight through to the live API —
            # which serves **v2.1.1** constraint where the snapshot serves **v4.1**. The pass then
            # warned about the release difference, correctly, for a snapshot it had never tried to get.
            # Best-effort like the others: a failure degrades to the API rather than sinking the pass.
            try:
                ensure_constraint_snapshot(constraint_cache)
                reference = resolve_constraint_reference(constraint_cache)
            except Exception as exc:
                logger.warning(
                    "gnomAD constraint snapshot provisioning failed (%s); continuing with the live "
                    "API, which serves v2.1.1 rather than v4.1.", exc,
                )
        if reference is not None:
            from_snapshot = lookup_snapshot(reference, wanted)
        elif offline:
            logger.warning(
                "No gnomAD constraint snapshot found and --offline: gene metrics will be empty. "
                "Provision one with `just-dna-enricher gnomad constraint build|publish`."
            )

    # ── live API link (for what the snapshot missed, unless offline) ───────────────────────────
    from_api: dict[str, dict] = {}
    still_missing = [g for g in wanted if g not in from_snapshot]
    if still_missing and not offline:
        owned = client is None
        gnomad = client or GnomadClient()
        try:
            from_api = gnomad.fetch_gene_constraint(still_missing)
        except GnomadError as exc:
            raise GeneMetricsUnavailable(
                f"the gnomAD constraint API could not be reached: {exc}"
            ) from exc
        finally:
            if owned:
                gnomad.close()

    # Which release a `not_found` row is reporting absence *from*: the last route actually consulted.
    absent_from = dataset if offline else API_CONSTRAINT_DATASET_LABEL
    # **Was either route consulted at all?** (RM98.) The snapshot link needs a resolved `reference`,
    # the API link needs `not offline` — so an offline run with no snapshot opens neither, and the
    # pass has already logged that gene metrics "will be empty". It then wrote a `not_found` row per
    # gene stamped with a `gnomad_v4.1_constraint` release it never opened, asserting that a specific
    # gnomAD release was consulted and has no constraint for the gene. `@unreachable-not-absent`: the
    # comment below already draws exactly this distinction, and the code crossed it.
    constraint_routes_consulted = reference is not None or not offline
    unconsulted: list[str] = []
    for gene in wanted:
        payload = from_snapshot.get(gene)
        # The label follows the ROUTE, never the caller's `dataset` argument alone — the snapshot and
        # the API are different releases (see the module docstring), so one label for both would put
        # two different facts under one name.
        # `source` names the **licensed source**, not the route: `gnomad-constraint`/`gnomad-api` were
        # link names, and the compiler compares this column against `sources.csv` by string, so a route
        # here made every gene-metrics module warn that a source with no terms recorded had contributed
        # (RM33, the same overloading found in `resolution.csv`). The route is not lost — it is what
        # `dataset` carries, which is where this file already says the release distinction lives, and
        # `dataset` is inside the fact set while `source` is provenance.
        source, row_dataset = "gnomad", dataset
        if payload is None:
            payload = from_api.get(gene)
            row_dataset = API_CONSTRAINT_DATASET_LABEL
        if payload is None:
            missing.append(gene)
            # A `not_found` row is a fact — the gene was looked up and gnomAD has no constraint for
            # it, which is genuinely true for many small or non-coding genes — and is different from
            # a gene that was never queried (no row at all).
            if not constraint_routes_consulted:
                unconsulted.append(gene)
                continue
            out.append(
                GeneMetricsRow(
                    gene=gene, dataset=absent_from, source="gnomad", status="not_found",
                    fetched_at=fetched_at,
                )
            )
            continue
        covered.append(gene)
        out.append(
            GeneMetricsRow(
                gene=gene, dataset=row_dataset, source=source, status="resolved",
                fetched_at=fetched_at,
                **{k: payload.get(k) for k in _METRIC_FIELDS},
            )
        )
    if from_api:
        logger.warning(
            "%d gene(s) fell back to the live gnomAD API, which serves v2.1.1 constraint rather than "
            "v4.1 (labelled %s). Provision the v4.1 snapshot with `just-dna-enricher gnomad "
            "constraint build|publish` for current numbers.",
            len(from_api), API_CONSTRAINT_DATASET_LABEL,
        )

    out.sort(key=lambda r: (r.gene, r.dataset))
    if unconsulted:
        # Warned in BOTH modes. The pass already logs "gene metrics will be empty" above; what this
        # adds is that the emptiness is now honest -- before RM98 it went on to write one `not_found`
        # row per gene anyway, stamped with a release it had just said it could not open.
        logger.warning(
            "%d gene(s) were not asked of any gnomAD route: no constraint snapshot is present and "
            "the live API is disabled%s, so no row is written for them -- their absence from "
            "gene_metrics.csv means unchecked, never 'gnomAD has no constraint for this gene'. %s. "
            "Provision a snapshot with `just-dna-enricher gnomad constraint build|publish`.",
            len(unconsulted),
            " (--offline)" if offline else "",
            ", ".join(sorted(unconsulted)),
        )

    result = GeneMetricsResult(
        rows=out,
        covered=sorted(set(covered)),
        missing=sorted(set(missing)),
        unconsulted=sorted(set(unconsulted)),
        sources=sorted({r.source for r in out if r.source}),
        mode=mode,
    )
    if mode == "strict" and result.missing:
        raise GeneMetricsEnrichmentError(
            f"strict gene-metrics enrichment: {len(result.missing)} gene(s) have no gnomAD "
            f"constraint: {result.missing}. Many genes genuinely have none (small, non-coding, or "
            f"newly named), so this is often correct data — add the rows by hand, check the symbols "
            f"against current HGNC names, or use mode='best_effort'."
            + (
                f" Of these, {len(result.unconsulted)} were never asked at all "
                f"({result.unconsulted}): no snapshot and no live link, so nothing is known about "
                f"them either way."
                if result.unconsulted
                else ""
            )
        )
    if write:
        _write_gene_metrics_csv(out, output_path)
        # As above: the pass consulted gnomAD, so the module records gnomAD's terms. `clingen.py` writes
        # its own row for the dosage columns it adds to this same table.
        record_source_terms(
            {row.source for row in out if row.source},
            "gene_metrics",
            spec_dir,
            error=GeneMetricsEnrichmentError,
        )
    return result


def _write_gene_metrics_csv(rows: list[GeneMetricsRow], output_path: Path) -> None:
    """Write the table with a fixed column order and canonical cells (byte-stable across runs).

    Every metric here is a float by nature, so unlike the frequency table there is no integer form to
    fall back on — `_cell` gives them one canonical rendering, and the round-trip test proves it.
    """
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in _FIELDNAMES})


def _cell(value: object) -> str:
    """Render one value to a canonical CSV cell, matching the compiler's reverse writer exactly.

    `None` → empty; `bool` → `true`/`false` (so an explicit `False` stays distinct from unset); an
    integer-valued float → a bare int (`1.0` → `1`, keeping the CSV human-readable and reloading to
    the same value); everything else → `str()`, which for a float is the shortest representation that
    reloads to the identical double — exact and deterministic, so the enricher-written and the
    reverse-written table spell the same number the same way (Principle 7).

    (`bool` is checked before `float` because `bool` is an `int`, not a `float`.)
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
