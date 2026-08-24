"""`enrich-frequencies` — the second pass: coordinates in, `frequencies.csv` out.

Structured like `enrich()`, and deliberately a *separate pass* rather than more work inside it. The
resolution pass answers "where is this variant"; this one answers "how common is it" — different
question, different output file, different failure mode, and a module may want one without the other.

It consumes `resolution.csv` rather than `variants.csv`, because a frequency is per *allele at a
coordinate*: the resolution table is where an rsID has already become `chrom-pos-ref-alt`, which is
exactly the key gnomAD wants. That also sidesteps the multi-allelic-rsID problem entirely — a problem
the resolver link has to solve, and this pass never meets.

**This is the first online-only link in the whole chain.** There is no offline snapshot to fall back
on and there will not be one: the v4.1 sites VCFs are 58 GB (exomes) and 742 GB (genomes), so a
frequency slice is not a thing that ships. `--offline` therefore makes this pass a no-op with a
warning rather than a failure. That is not a hole in reproducibility: once `frequencies.csv` is
written it *is* the pin, and every later compile reads it offline and deterministically.
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import derive_variant_key, merge_key
from just_dna_format.frequency import FrequencyRow
from just_dna_format.layout import atomic_writer
from just_dna_format.normalize import now_utc_iso
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import population_sort_key

from just_dna_enricher.gnomad import (
    FREQUENCY_DATASET_LABEL,
    FREQUENCY_GENOME_BUILD,
    GnomadClient,
    GnomadError,
    covers_locus,
)
from just_dna_enricher.licensing import record_source_terms, sidecar_path

logger = logging.getLogger(__name__)

_FIELDNAMES = [
    "variant_key", "rsid", "chrom", "start", "ref", "alt", "genome_build",
    "population", "allele_count", "allele_number", "homozygote_count", "hemizygote_count",
    "faf95", "dataset", "vrs_id", "caid", "source", "status", "fetched_at",
]


class FrequencyEnrichmentError(RuntimeError):
    """Raised in strict mode when a resolved variant gets no frequency."""


class FrequencyUnavailable(FrequencyEnrichmentError):
    """gnomAD could not be reached, so no frequency question was put at all (RM101).

    A subclass rather than a second exception, so every existing `except FrequencyEnrichmentError` still
    catches it (P3 — additive within a major). It exists because this pass could fail two ways that
    want different responses and had one type for both: **gnomAD was asked and never answered**, and a resolved variant genuinely has no frequency under `strict`.
    Only this one means the source was asked and never answered.

    Before RM101 this case did not reach `FrequencyEnrichmentError` at all — a `GnomadError` travelled straight
    out through a `try/finally` with no `except`, so a caller's handler, written against the type
    this module documents, was silent for exactly the failure it was written for.
    """


@dataclass
class FrequencyResult:
    rows: list[FrequencyRow]
    covered: list[str] = field(default_factory=list)     # variant_keys that got at least one row
    missing: list[str] = field(default_factory=list)     # resolved alleles gnomAD did not know
    # Alleles gnomAD does not COVER — kept apart from `missing` because they are a different answer.
    # `missing` means asked and absent; these were never askable, so counting them as absences would
    # report an unknown as a negative (see `gnomad.covers_locus`).
    uncovered: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    skipped_offline: bool = False


def format_faf95(value: float | None) -> str:
    """Render `faf95` to a canonical cell — the one stored float in the table.

    Every other number here is an integer count precisely so CSV round-trips are exact; `faf95` has no
    integer form. `str()` is the right tool and a fixed `%.12g` would be a mistake: since Python 3.1,
    `str(float)` produces the *shortest string that reloads to the identical double*, which is both
    exactly lossless and deterministic across platforms for IEEE-754. A fixed-precision format would
    be deterministic but would silently truncate, and it would disagree with the compiler's reverse
    writer (`_scalar_cell`), leaving the same number spelled two ways depending on who last wrote the
    file.
    """
    if value is None:
        return ""
    return str(value)


def _alleles_from_resolution(
    rows: list[ResolutionRow],
) -> tuple[list[tuple[str, str, int, str, str]], list[str]]:
    """Expand resolved rows into `(variant_key, chrom, start, ref, alt)` — one entry per ALT.

    Returns `(alleles, off_build)`, the second being the `variant_key`s left out because their assembly
    is not the one gnomAD serves.

    A multi-allelic `alts` cell becomes several entries, each re-keyed to *its own* allele identity via
    `derive_variant_key`, because that is the key the compiler's weights rows carry after expansion.
    Emitted in first-occurrence order, de-duplicated, so the request order (and so the written table)
    is deterministic.

    **A row on another build is skipped, and that is a correctness fix rather than an optimization.**
    gnomAD's variant id is `chrom-pos-ref-alt` and carries no assembly, so a GRCh37 coordinate is a
    well-formed request that returns whatever GRCh38 variant sits at that number: the pass would have
    written a **different variant's** counts under this module's key, with no error anywhere. The same
    row also reached `derive_variant_key` without a `build`, so it minted a GRCh38 `ga4gh:VA.…` for a
    GRCh37 coordinate — the same false content-addressed identity the reverse and enrich paths were
    producing, from a third place.
    """
    seen: set[tuple[str, int, str, str]] = set()
    out: list[tuple[str, str, int, str, str]] = []
    off_build: list[str] = []
    for row in rows:
        if row.chrom is None or row.start is None or row.ref is None or not row.alts:
            continue
        if row.status == "not_found":
            continue
        if row.genome_build != FREQUENCY_GENOME_BUILD:
            off_build.append(row.variant_key)
            continue
        for alt in (a.strip() for a in row.alts.split(",")):
            if not alt:
                continue
            coord = (row.chrom, row.start, row.ref, alt)
            if coord in seen:
                continue
            seen.add(coord)
            key = derive_variant_key(
                None, row.chrom, row.start, row.ref, alt, build=row.genome_build
            )
            out.append((key, row.chrom, row.start, row.ref, alt))
    return out, off_build


def _variant_id(chrom: str, start: int, ref: str, alt: str) -> str:
    """gnomAD's `chrom-pos-ref-alt` id (its chromosomes carry no `chr` prefix, like ours)."""
    return f"{chrom}-{start}-{ref}-{alt}"


def enrich_frequencies(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    populations: list[str] | None = None,
    dataset: str = FREQUENCY_DATASET_LABEL,
    write: bool = True,
    client: GnomadClient | None = None,
) -> FrequencyResult:
    """Fill `frequencies.csv` from the coordinates already in `resolution.csv`.

    `populations` restricts the emitted ancestry groups (e.g. `["global"]` keeps the table to one row
    per allele — the human-legibility escape hatch for a module that wants the number, not the
    breakdown). `None` keeps every group the source reports.

    Existing rows are authoritative and are merged, never clobbered — the same rule `enrich()` applies
    to `resolution.csv`, and it is what makes a hand-corrected number survive a re-run. Note the same
    consequence, too: to regenerate after a machinery change you must delete the file first.
    """
    spec_dir = Path(spec_dir)
    # Both through the shared resolver: the module may keep either table under `derived/` (RM49), and
    # a pass that read one layout and wrote the other would leave two copies behind.
    resolution_path = sidecar_path(spec_dir, "resolution.csv", error=FrequencyEnrichmentError)
    frequencies_path = sidecar_path(spec_dir, "frequencies.csv", error=FrequencyEnrichmentError)

    if not resolution_path.exists():
        raise FrequencyEnrichmentError(
            f"no resolution.csv in {spec_dir} — the frequency pass reads resolved coordinates, so run "
            f"`just-dna-enricher enrich` first."
        )
    resolution_rows, errors, _ = load_csv_rows(resolution_path, ResolutionRow, resolution_path.name)
    if errors:
        raise FrequencyEnrichmentError(f"resolution.csv is invalid: {errors[0]}")

    existing: dict[tuple, FrequencyRow] = {}
    if frequencies_path.exists():
        rows, errors, _ = load_csv_rows(frequencies_path, FrequencyRow, "frequencies.csv")
        if errors:
            raise FrequencyEnrichmentError(f"existing frequencies.csv is invalid: {errors[0]}")
        for row in rows:
            existing[merge_key(row)] = row

    alleles, off_build = _alleles_from_resolution(resolution_rows)
    if off_build:
        # One counted line, not one per row, and it names the build rather than the count alone: an
        # author on GRCh37 needs to know the pass declined rather than found nothing.
        logger.warning(
            "Frequency enrichment skipped %d row(s) whose genome_build is not %s: gnomAD v4 is "
            "%s-only and its variant id carries no assembly, so querying a coordinate from another "
            "build would return a different variant's counts under this module's key. Examples: %s",
            len(off_build), FREQUENCY_GENOME_BUILD, FREQUENCY_GENOME_BUILD, off_build[:3],
        )
    wanted_populations = {p.strip().lower() for p in populations} if populations else None

    if offline:
        logger.warning(
            "Frequency enrichment skipped: --offline and gnomAD has no offline snapshot (the v4.1 "
            "sites VCFs are 58 GB exomes / 742 GB genomes). Any existing frequencies.csv is kept as "
            "the pin; compiles stay reproducible from it."
        )
        out = sorted(existing.values(), key=_sort_key)
        if write and existing:
            _write_frequencies_csv(out, frequencies_path)
        return FrequencyResult(
            rows=out, sources=sorted({r.source for r in out if r.source}), mode=mode,
            skipped_offline=True,
            missing=sorted({key for key, *_ in alleles} - {r.variant_key for r in out}),
        )

    # Only fetch what no existing row already covers — a re-run after adding two variants costs one
    # request, not a full refetch of a table that is already right.
    # Read off the rows, never by unpacking the merge key positionally: the key is
    # `FrequencyRow._KEY_FIELDS` now, so a member added there would silently reshape this tuple (S51).
    covered_keys = {row.variant_key for row in existing.values()}
    wanted = [a for a in alleles if a[0] not in covered_keys]
    # A locus gnomAD does not cover is not asked about at all. Two reasons, and the second is the
    # important one: the request would spend a slot of a 10-per-minute budget to learn nothing, and
    # gnomAD's silence about a locus it never looked at is indistinguishable from a real absence — so
    # asking is how the false `not_found` got written in the first place.
    to_fetch = [a for a in wanted if covers_locus(a[1], a[2]) is not False]
    uncovered = [a for a in wanted if covers_locus(a[1], a[2]) is False]
    fetched: dict[str, dict] = {}
    if to_fetch:
        owned = client is None
        gnomad = client or GnomadClient()
        try:
            fetched = gnomad.fetch_frequencies(
                [_variant_id(chrom, start, ref, alt) for _, chrom, start, ref, alt in to_fetch]
            )
        except GnomadError as exc:
            raise FrequencyUnavailable(f"gnomAD could not be reached: {exc}") from exc
        finally:
            if owned:
                gnomad.close()

    fetched_at = now_utc_iso()
    out: list[FrequencyRow] = list(existing.values())
    covered: list[str] = []
    missing: list[str] = []
    for key, chrom, start, ref, alt in to_fetch:
        payload = fetched.get(_variant_id(chrom, start, ref, alt))
        if not payload or not payload.get("populations"):
            missing.append(key)
            # A `not_found` row is a FACT — "gnomAD was asked and does not have this allele" — and is
            # materially different both from a variant that was never queried (no row at all) and from
            # one at a locus gnomAD does not cover (`not_covered`, below). Reaching this branch means
            # the locus IS in the callset and the allele is absent from those samples.
            out.append(
                FrequencyRow(
                    variant_key=key, chrom=chrom, start=start, ref=ref, alt=alt,
                    population="global", dataset=dataset, source="gnomad", status="not_found",
                    fetched_at=fetched_at,
                )
            )
            continue
        covered.append(key)
        for entry in payload["populations"]:
            if wanted_populations is not None and entry["population"] not in wanted_populations:
                continue
            out.append(
                FrequencyRow(
                    variant_key=key, rsid=payload.get("rsid"), chrom=chrom, start=start,
                    ref=ref, alt=alt, dataset=dataset,
                    vrs_id=payload.get("vrs_id"), caid=payload.get("caid"),
                    source="gnomad", status="resolved", fetched_at=fetched_at, **entry,
                )
            )

    # Recorded rather than omitted: an author looking at the table should be able to see that gnomAD has
    # no answer here, instead of wondering why the row is absent. One aggregated line, not one per row.
    for key, chrom, start, ref, alt in uncovered:
        out.append(
            FrequencyRow(
                variant_key=key, chrom=chrom, start=start, ref=ref, alt=alt,
                population="global", dataset=dataset, source="gnomad", status="not_covered",
                fetched_at=fetched_at,
            )
        )
    if uncovered:
        logger.warning(
            "%d allele(s) sit outside gnomAD's callset and were recorded as not_covered, not asked "
            "about and not counted as absent (%s). gnomAD hard-masks the Y pseudoautosomal region — "
            "those bases duplicate the X PAR — so it has no frequency to give there; the X spelling of "
            "the same place does. This is an unknown, not a zero.",
            len(uncovered),
            ", ".join(f"{chrom}:{start} {ref}>{alt}" for _, chrom, start, ref, alt in uncovered),
        )

    out.sort(key=_sort_key)
    result = FrequencyResult(
        rows=out,
        covered=sorted(set(covered)),
        missing=sorted(set(missing)),
        uncovered=sorted({key for key, *_ in uncovered}),
        sources=sorted({r.source for r in out if r.source}),
        mode=mode,
    )
    # `result.uncovered` is deliberately NOT part of this gate. `strict` means "a reproducible
    # artifact", and a locus outside gnomAD's callset is perfectly reproducible — it will be outside it
    # on every run. Refusing would make a pseudoautosomal module uncompilable under `strict` for a
    # reason no authored edit could fix, which is the opposite of what a strict failure is for.
    if mode == "strict" and result.missing:
        raise FrequencyEnrichmentError(
            f"strict frequency enrichment: {len(result.missing)} resolved allele(s) have no gnomAD "
            f"frequency: {result.missing}. gnomAD genuinely lacks rare/private alleles, so this is "
            f"often correct data rather than a fetch failure — add the rows by hand or use "
            f"mode='best_effort'."
        )
    if write:
        _write_frequencies_csv(out, frequencies_path)
        # Same rule as every other pass that consults a source: record its terms, or the module cannot
        # account for it. gnomAD is CC0 and asks for attribution, which is what this row carries.
        record_source_terms(
            {row.source for row in out if row.source},
            "frequency",
            spec_dir,
            error=FrequencyEnrichmentError,
        )
    return result


def _sort_key(row: FrequencyRow) -> tuple:
    """Deterministic emission order: by allele, then by the canonical ancestry-group order."""
    return (row.variant_key, row.alt or "", population_sort_key(row.population))


def _write_frequencies_csv(rows: list[FrequencyRow], output_path: Path) -> None:
    """Write the table with a fixed column order and canonical cells (byte-stable across runs)."""
    with atomic_writer(output_path, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "variant_key": row.variant_key,
                    "rsid": row.rsid or "",
                    "chrom": row.chrom or "",
                    "start": row.start if row.start is not None else "",
                    "ref": row.ref or "",
                    "alt": row.alt or "",
                    "genome_build": row.genome_build,
                    "population": row.population,
                    "allele_count": row.allele_count if row.allele_count is not None else "",
                    "allele_number": row.allele_number if row.allele_number is not None else "",
                    "homozygote_count": (
                        row.homozygote_count if row.homozygote_count is not None else ""
                    ),
                    "hemizygote_count": (
                        row.hemizygote_count if row.hemizygote_count is not None else ""
                    ),
                    "faf95": format_faf95(row.faf95),
                    "dataset": row.dataset,
                    "vrs_id": row.vrs_id or "",
                    "caid": row.caid or "",
                    "source": row.source or "",
                    "status": row.status or "",
                    "fetched_at": row.fetched_at or "",
                }
            )
