"""`enrich-assertions` — resolved coordinates in, `clinical_assertions.csv` out (0.6, RM25).

The number this workspace was computing and throwing away. `clinical.ClinSigFinding.confidence`
renders a star rating into a warning string and keeps nothing; `clinvar_draft.draft_gene_panel` uses
it as a *filter* (default 2 — multiple submitters, no conflicts) and keeps nothing. So a compiled
module flattened a one-star single submission and a practice guideline to the same `clin_sig`, and
every consumer that wanted the difference had to re-derive it — a recomputation is a place to drift,
which is the argument RM40/RM41 already made twice.

Structured like `enrich_frequencies`, and for its reason: it consumes `resolution.csv` rather than
`variants.csv`, because a clinical record is per *allele at a coordinate* and the resolution table is
where an rsID has already become `chrom-pos-ref-alt`. That is also what keeps it clear of the
multi-allelic-rsID problem — one rsID at one locus legitimately carries a pathogenic, a benign and an
uncertain allele (`rs33922842` in HBB), so looking clinical significance up by rsID would manufacture
disagreements out of ClinVar agreeing with itself.

**Fully offline-capable, unlike the frequency pass.** ClinVar ships as a snapshot, so this reads the
same injected parquet the resolver link and the cross-check read, provisioning it when the run is not
offline — the `enrich()` shape, and no second CLI flag. `dataset` comes from the snapshot's own
`release.json`, so a consumer can tell which ClinVar release a record was read from; a re-review is
exactly the change this table exists to make visible, and it is only visible against a stated release.

**This is not the cross-check and does not touch it.** `clinical.verify_clin_sig` compares the
*author's* `clin_sig` against ClinVar's and warns in both modes, deliberately, because failing would
make the format arbitrate a clinical dispute. This pass records what ClinVar says and adjudicates
nothing; nothing here escalates that check, and the compiler's coherence check over this table is a
position-orphan check for the same reason.
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.base import derive_variant_key
from just_dna_format.normalize import now_utc_iso
from just_dna_format.resolution import ResolutionRow
from pydantic import ValidationError

from just_dna_enricher.clinvar import lookup_clin_sig
from just_dna_enricher.download import ensure_clinvar_snapshot
from just_dna_enricher.licensing import CLINVAR_TERMS, record_source_terms, sidecar_path
from just_dna_enricher.locations import read_release, resolve_clinvar_reference

logger = logging.getLogger(__name__)

CLINVAR_SOURCE = CLINVAR_TERMS.source

#: The assembly the ClinVar snapshot is built on, as a named constant rather than a literal.
#:
#: The fourth build-confusion this workspace has paid for, so it gets the treatment the third one
#: earned (`gnomad.FREQUENCY_GENOME_BUILD`). The snapshot's lookup key is `(chrom, start, ref, alt)`
#: and carries no assembly, so a GRCh37 coordinate is a *well-formed* query returning whatever GRCh38
#: record sits at that number — a different variant's clinical call written under this module's key,
#: with no error anywhere.
ASSERTION_GENOME_BUILD = "GRCh38"

#: Label prefix for the `dataset` column, completed with the snapshot's own release date.
_DATASET_PREFIX = "clinvar"

#: The column order, derived from the model rather than hand-kept (`SOURCES_FIELDNAMES`'s rule).
#: `ClinicalAssertionRow` has no compiler-stamped fields, so every declared field is a real column.
_FIELDNAMES = list(ClinicalAssertionRow.model_fields)


class ClinicalAssertionError(RuntimeError):
    """Raised in strict mode when a resolved allele gets no clinical record, or a read fails."""


@dataclass
class ClinicalAssertionResult:
    rows: list[ClinicalAssertionRow] = field(default_factory=list)
    #: `variant_key`s that got at least one archive record.
    covered: list[str] = field(default_factory=list)
    #: Resolved alleles the archive was asked about and has no record for. A fact, not a failure.
    missing: list[str] = field(default_factory=list)
    #: Alleles left out because their assembly is not the one the snapshot is built on. Separate from
    #: `missing` because nobody asked about them — reporting them as absences would be the false
    #: negative `gnomad.covers_locus` exists to prevent one table over.
    off_build: list[str] = field(default_factory=list)
    dataset: str = ""
    mode: str = "best_effort"
    #: The pass did not run because no snapshot could be reached. A first-class answer, distinct from
    #: "ran and found nothing" and from a failure.
    skipped_no_snapshot: bool = False


def _alleles_from_resolution(
    rows: list[ResolutionRow],
) -> tuple[list[tuple[str, str | None, str, int, str, str]], list[str]]:
    """Expand resolved rows into `(variant_key, rsid, chrom, start, ref, alt)` — one entry per ALT.

    The same expansion `frequencies._alleles_from_resolution` performs, including the off-build skip,
    and deliberately not shared with it: that one filters on gnomAD's build and this one on the
    snapshot's, so a single helper would have to take the build as an argument and the two call sites
    would still have to know which constant to hand it. Two named constants beside two callers is the
    shape that made the third build confusion findable.

    Emitted in first-occurrence order and de-duplicated, so the query and the written table are
    deterministic (Principle 7).
    """
    seen: set[tuple[str, int, str, str]] = set()
    out: list[tuple[str, str | None, str, int, str, str]] = []
    off_build: list[str] = []
    for row in rows:
        if row.chrom is None or row.start is None or row.ref is None or not row.alts:
            continue
        if row.status == "not_found":
            continue
        if row.genome_build != ASSERTION_GENOME_BUILD:
            off_build.append(row.variant_key)
            continue
        for alt in (a.strip() for a in row.alts.split(",")):
            if not alt:
                continue
            coord = (row.chrom, row.start, row.ref, alt)
            if coord in seen:
                continue
            seen.add(coord)
            # `build=` is passed because `alts` is: a single-alt substitution mints a `ga4gh:VA.…`
            # here, and the default would mint a GRCh38 identity whatever the row says. The off-build
            # skip above already guarantees the two agree; passing it anyway is what keeps that true
            # if the guard is ever loosened.
            key = derive_variant_key(
                None, row.chrom, row.start, row.ref, alt, build=row.genome_build
            )
            # The rsID travels from the resolution row rather than from the archive, and that is the
            # cheaper of two honest routes: `clinvar.lookup_clin_sig` does not select it, and widening
            # a reader two other callers share — one of them a query-plan guard asserting the returned
            # dict exactly — to carry a value this table already holds would be the expensive one.
            out.append((key, row.rsid, row.chrom, row.start, row.ref, alt))
    return out, off_build


def snapshot_dataset(reference: Path | None) -> str:
    """The `dataset` label for records read from this snapshot.

    Reads the snapshot's own `release.json` — the RM38 rule that a snapshot stamps its release into
    the row, so a consumer can tell a pinned file from whatever happened to be current. A snapshot
    that cannot state its release gets `clinvar_unknown` rather than a fabricated date: an unknown
    written down as a plausible-looking value is worse than one written down as unknown.
    """
    release = read_release(reference) if reference is not None else None
    stated = str((release or {}).get("clinvar_file_date") or "").strip()
    return f"{_DATASET_PREFIX}_{stated or 'unknown'}"


def enrich_clinical_assertions(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    clinvar_cache: Path | None = None,
    download: bool = True,
    write: bool = True,
) -> ClinicalAssertionResult:
    """Fill `clinical_assertions.csv` from the coordinates already in `resolution.csv`.

    Existing rows are authoritative and merged, never clobbered — the standing rule, with its standing
    consequence: to regenerate after a machinery change, delete the file first. The merge key is
    `(variant_key, variation_id)`, which is the archive's grain: ClinVar genuinely holds several
    records for one allele under different conditions, and collapsing them would pick a condition on
    the author's behalf.

    A resolved allele the archive has no record for gets a `not_found` row, unlike the gene-validity
    pass's silence. The two differ because the sources differ: ClinVar covers the genome, so "asked
    and absent" is a fact about the allele, while a gene-curation body's silence only means nobody has
    assessed the gene yet.

    `download` provisions the published snapshot when no local one is found, exactly as `enrich()`
    does — `--offline` is the switch, and there is deliberately no second flag. With no snapshot
    reachable the pass is a no-op with a warning (`skipped_no_snapshot`), never a failure.
    """
    spec_dir = Path(spec_dir)
    resolution_path = sidecar_path(spec_dir, "resolution.csv", error=ClinicalAssertionError)
    assertions_path = sidecar_path(spec_dir, "clinical_assertions.csv", error=ClinicalAssertionError)

    if not resolution_path.exists():
        raise ClinicalAssertionError(
            f"no resolution.csv in {spec_dir} — the clinical-assertion pass reads resolved "
            f"coordinates, so run `just-dna-enricher enrich` first."
        )
    resolution_rows, errors, _ = load_csv_rows(resolution_path, ResolutionRow, resolution_path.name)
    if errors:
        raise ClinicalAssertionError(f"{resolution_path.name} is invalid: {errors[0]}")

    existing_rows: list[ClinicalAssertionRow] = []
    if assertions_path.exists():
        parsed, errors, _ = load_csv_rows(
            assertions_path, ClinicalAssertionRow, assertions_path.name
        )
        if errors:
            raise ClinicalAssertionError(f"existing {assertions_path.name} is invalid: {errors[0]}")
        existing_rows = parsed

    alleles, off_build = _alleles_from_resolution(resolution_rows)
    if off_build:
        # One counted line naming the build, not one per row: an author on GRCh37 needs to know the
        # pass declined rather than that the archive found nothing.
        logger.warning(
            "Clinical-assertion enrichment skipped %d row(s) whose genome_build is not %s: the "
            "ClinVar snapshot is %s-only and its lookup key carries no assembly, so a coordinate "
            "from another build would return a different variant's record under this module's key. "
            "Examples: %s",
            len(off_build), ASSERTION_GENOME_BUILD, ASSERTION_GENOME_BUILD, off_build[:3],
        )

    reference = resolve_clinvar_reference(clinvar_cache)
    if reference is None and not offline and download:
        # Provisioning wired the way `enrich()` wires it: best-effort, so a failure degrades to a
        # skip rather than sinking the pass.
        try:
            ensure_clinvar_snapshot(clinvar_cache)
            reference = resolve_clinvar_reference(clinvar_cache)
        except Exception as exc:
            logger.warning("ClinVar snapshot provisioning failed (%s); the pass is skipped.", exc)
    if reference is None:
        logger.warning(
            "Clinical-assertion pass skipped: no ClinVar snapshot is reachable%s. Any existing "
            "clinical_assertions.csv is kept as the pin; compiles stay reproducible from it. "
            "Provision one with `just-dna-enricher clinvar pull`.",
            " and --offline was given" if offline else "",
        )
        out = sorted(existing_rows, key=_sort_key)
        if write and existing_rows:
            _write_assertions_csv(out, assertions_path)
        return ClinicalAssertionResult(rows=out, mode=mode, skipped_no_snapshot=True,
                                       off_build=sorted(set(off_build)))

    dataset = snapshot_dataset(reference)
    # **Every in-scope allele is asked about on every run, and that is a deliberate departure from
    # `enrich_frequencies`.** That pass skips an allele any existing row covers because gnomAD costs a
    # slot of a 10-per-minute budget; this one reads a local parquet, where the same skip protects
    # nothing and costs correctness. ClinVar *grows*: skipping on `variant_key` meant a newly-published
    # record could never reach an allele the table already mentioned, and a `not_found` row — an
    # absence recorded before the first submission — became a permanent pin. Dedup happens per record
    # instead, on the `(variant_key, variation_id)` grain this table is documented to have.
    wanted = list(alleles)

    def _unusable(reason: object) -> ClinicalAssertionResult:
        """Degrade rather than sink the run, keeping any existing table as the pin.

        The rule the resolver link and the cross-check already follow for a located-but-unusable
        snapshot. **Two causes reach it, and they are the same cause**: a query that fails, and a
        record whose values this reader cannot load. Treating the second as a crash and the first as a
        skip would be an arbitrary split — both mean *this snapshot is not one this reader can use* —
        and the second is not hypothetical: the published ClinVar repo still carries a pre-split
        `clinvar.parquet` whose columns are raw VCF INFO fields, so a reader that ever globbed it
        would see ClinVar's own `Pathogenic/Likely_pathogenic` where the vocabulary is expected.
        """
        logger.warning(
            "ClinVar reference at %s is present but not usable (%s); the clinical-assertion pass "
            "is skipped this run. Rebuild it with `just-dna-enricher clinvar build`.", reference, reason,
        )
        kept = sorted(existing_rows, key=_sort_key)
        if write and existing_rows:
            _write_assertions_csv(kept, assertions_path)
        return ClinicalAssertionResult(rows=kept, mode=mode, skipped_no_snapshot=True,
                                       off_build=sorted(set(off_build)))

    try:
        records = lookup_clin_sig(reference, [(c, s, r, a) for _k, _rs, c, s, r, a in wanted])
    except Exception as exc:
        return _unusable(exc)

    fetched_at = now_utc_iso()
    seen = {(row.variant_key, row.variation_id) for row in existing_rows}
    out: list[ClinicalAssertionRow] = list(existing_rows)
    covered: list[str] = []
    missing: list[str] = []
    #: Alleles whose recorded absence this run has answered — see the withdrawal below.
    answered: set[str] = set()
    for key, rsid, chrom, start, ref, alt in wanted:
        found = records.get((chrom, start, ref, alt), [])
        if not found:
            missing.append(key)
            # A `not_found` row is a FACT — the archive was consulted and has no record for this
            # allele — and is materially different from an allele that was never queried, which has
            # no row at all. Carried under `(key, None)` so re-running against the same snapshot
            # re-states the absence rather than appending a second copy of it.
            if (key, None) in seen:
                continue
            seen.add((key, None))
            out.append(
                ClinicalAssertionRow(
                    variant_key=key, rsid=rsid, chrom=chrom, start=start, ref=ref, alt=alt,
                    genome_build=ASSERTION_GENOME_BUILD, dataset=dataset,
                    source=CLINVAR_SOURCE, status="not_found", fetched_at=fetched_at,
                )
            )
            continue
        covered.append(key)
        answered.add(key)
        for record in found:
            variation_id = _text(record.get("variation_id"))
            if (key, variation_id) in seen:
                continue
            seen.add((key, variation_id))
            # A record this reader cannot load is the snapshot being unusable, not this row being
            # interesting — same verdict as a failed query, reached above. Caught narrowly
            # (`ValidationError`, not `Exception`) so a genuine bug in the lines below still surfaces
            # as a bug instead of being reported as somebody else's bad parquet.
            try:
                out.append(
                    ClinicalAssertionRow(
                        variant_key=key,
                        rsid=rsid,
                        chrom=chrom, start=start, ref=ref, alt=alt,
                        genome_build=ASSERTION_GENOME_BUILD,
                        clin_sig=_text(record.get("clin_sig")),
                        clin_sig_raw=_text(record.get("clin_sig_raw")),
                        review_status=_text(record.get("review_status")),
                        review_stars=record.get("review_stars"),
                        condition=_text(record.get("condition")),
                        variation_id=variation_id,
                        dataset=dataset,
                        source=CLINVAR_SOURCE,
                        status="resolved",
                        fetched_at=fetched_at,
                    )
                )
            except ValidationError as exc:
                return _unusable(f"record {variation_id} at {chrom}:{start} — {exc}")

    # **A recorded absence the archive has since answered is withdrawn, not left beside the answer.**
    # This is the one place the pass removes a row it wrote earlier, and the narrowness is the point:
    # `not_found` is this pass's own bookkeeping — "the archive was consulted and has none" — and it
    # stops being true the moment a record exists. Keeping both would make the table assert an absence
    # and a presence for one allele, which is worse than either. Nothing else is touched: a `resolved`
    # row, and any row a curator wrote about an allele the archive still lacks, both survive untouched.
    if answered:
        out = [r for r in out if not (r.status == "not_found" and r.variant_key in answered)]

    out.sort(key=_sort_key)
    result = ClinicalAssertionResult(
        rows=out,
        covered=sorted(set(covered)),
        missing=sorted(set(missing)),
        off_build=sorted(set(off_build)),
        dataset=dataset,
        mode=mode,
    )
    # `off_build` is deliberately NOT part of this gate, for the reason `not_covered` is outside the
    # frequency pass's: `strict` means "a reproducible artifact", and a coordinate on another assembly
    # is reproducibly out of this snapshot's reach. Refusing would make a GRCh37 module uncompilable
    # for a reason no authored edit could fix.
    if mode == "strict" and result.missing:
        raise ClinicalAssertionError(
            f"strict clinical-assertion enrichment: {len(result.missing)} resolved allele(s) have no "
            f"ClinVar record: {result.missing}. Most variants are not in ClinVar at all, so this is "
            f"usually correct data rather than a read failure — use mode='best_effort'."
        )
    if write:
        _write_assertions_csv(out, assertions_path)
        # Same rule as every other pass that consults a source: record its terms, or the module cannot
        # account for it. ClinVar is public-domain and asks to be cited, which is what this row carries.
        record_source_terms(
            {row.source for row in out if row.source},
            "clinical_assertion",
            spec_dir,
            error=ClinicalAssertionError,
        )
    return result


def _text(value: object) -> str | None:
    """A snapshot cell → a stripped string, or `None` when it says nothing.

    DuckDB hands back `None` for a null and the model wants `None` rather than `''`, so an empty
    string is folded to `None` here: an empty cell reloads as `None` on the next compile, and a table
    that spelled the same absence two ways would hash as two facts.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sort_key(row: ClinicalAssertionRow) -> tuple:
    """Deterministic emission order (Principle 7): by locus, then allele, then archive record."""
    return (
        row.chrom or "",
        row.start if row.start is not None else -1,
        row.ref or "",
        row.alt or "",
        row.variant_key,
        row.variation_id or "",
    )


def _write_assertions_csv(rows: list[ClinicalAssertionRow], output_path: Path) -> None:
    """Write the table with a fixed column order and canonical cells (byte-stable across runs)."""
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in _FIELDNAMES})


def _cell(value: object) -> str:
    """Render one value to a canonical CSV cell, matching the compiler's reverse writer exactly."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
