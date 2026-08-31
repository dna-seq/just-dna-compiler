"""ClinGen dosage sensitivity — the gene-level authority beside gnomAD's constraint (0.5).

gnomAD tells you how *intolerant of variation* a gene looks in a population sample; ClinGen tells you
whether a curated expert panel found evidence that losing (haploinsufficiency) or gaining
(triplosensitivity) a copy actually causes disease. Different questions, different evidence, so they
are separate rows in `gene_metrics.csv` sharing a gene and naming their own `dataset` — never merged
into one row, which would put a statistical estimate and a curated verdict under one provenance.

**Free, and that matters here.** Every pharmacogenomics upstream this workspace touches is
CC BY-SA plus a bar on sale; ClinGen is not, so a module built on dosage sensitivity stays sellable.
The `SourceRow` this pass emits records that rather than leaving it to be assumed.

**Three shapes in the source file that would break a naive reader**, all found by reading the real
file rather than its documentation:

* The ratings are **numeric codes that are not ordinal**. `{0,1,2,3}` grade increasing evidence, but
  `30` means "gene associated with autosomal recessive phenotype" and `40` means "dosage sensitivity
  unlikely". Sorting on the raw number ranks `40` above `3` — the reverse of the meaning — so the
  codes are decoded to `vocab.VALID_DOSAGE_SENSITIVITY` terms at this boundary and never stored raw.
* The triplosensitivity column carries a literal **`"Not yet evaluated"`** (210 of 1,520 genes at the
  2026-08-01 release). It is an absence, not a rating, so it becomes `None` — and it is what makes an
  `int(cell)` reader crash on one file in seven.
* The file starts with **six `#` comment lines**, the last of which is the real header, so it is
  neither a plain TSV nor a comment-free one.

Reports, never repairs, like every other check in this tier: a gene ClinGen has not curated gets no
row rather than a fabricated "no evidence" one, because "not curated" and "curated as no evidence"
are different facts and the file distinguishes them.
"""

import csv
import io
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import merge_key
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.normalize import now_utc_iso
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import DOSAGE_SENSITIVITY_BY_CODE

from just_dna_enricher.gene_metrics import _write_gene_metrics_csv, module_genes
from just_dna_enricher.licensing import CLINGEN_TERMS, merge_sources_file, sidecar_path

logger = logging.getLogger(__name__)

DEFAULT_CLINGEN_URL = "https://ftp.clinicalgenome.org/ClinGen_gene_curation_list_GRCh38.tsv"
CLINGEN_SOURCE = CLINGEN_TERMS.source
# The header line the file's comment block ends with (see the module docstring).
_HEADER_PREFIX = "#Gene Symbol"
_NOT_EVALUATED = "not yet evaluated"


class ClinGenError(RuntimeError):
    """A ClinGen fetch or parse failed in a way the caller must see."""


class ClinGenUnavailable(ClinGenError):
    """The curation list could not be fetched, so ClinGen was never actually asked (RM101).

    A subclass rather than a second exception, so every existing `except ClinGenError` still catches
    it (P3 — additive within a major). It exists because `ClinGenError` covered **two opposite
    histories**: the curation list could not be fetched (`fetch_curation_list`), or a local
    `gene_metrics.csv` this module was handed will not parse. Only the first means the source was
    asked. A caller could separate them until now only by reading `exc.__cause__` — chained from
    `httpx.HTTPError` for the fetch and raised bare for the table — which is a private detail to
    depend on, and the alternative of matching the message is worse: neither string is pinned as an
    API, so a reword would silently flip a consumer's verdict from "unchecked" to "your table is
    broken".
    """


@dataclass
class DosageRating:
    """One gene's curated dosage sensitivity, decoded."""

    gene: str
    haploinsufficiency: str | None = None
    triplosensitivity: str | None = None


@dataclass
class ClinGenResult:
    rows: list[GeneMetricsRow]
    covered: list[str]
    missing: list[str]
    dataset: str
    source_row: SourceRow | None = None
    #: The pass did not run because the deployment is offline and ClinGen is a live download (RM39).
    #: A first-class answer a caller can render — *"the dosage pass did not run because this
    #: deployment is offline"* — and distinct both from "it ran and found nothing" (`missing`) and
    #: from a failure. `FrequencyResult.skipped_offline` is the shape this copies.
    skipped_offline: bool = False


def decode_rating(cell: str | None) -> str | None:
    """One ClinGen score cell → a `VALID_DOSAGE_SENSITIVITY` term, or `None`.

    `None` for blank, for `"Not yet evaluated"`, and for any code the mapping does not know — an
    unrecognized code is a signal that ClinGen added a rating this release does not model, and
    guessing at it would be worse than recording nothing."""
    if cell is None:
        return None
    text = cell.strip()
    if not text or text.lower() == _NOT_EVALUATED:
        return None
    try:
        code = int(text)
    except ValueError:
        logger.warning("ClinGen dosage rating is not a known code, leaving it unset: %r", text)
        return None
    term = DOSAGE_SENSITIVITY_BY_CODE.get(code)
    if term is None:
        logger.warning("ClinGen dosage code %d is not in this release's mapping, leaving it unset", code)
    return term


def parse_curation_list(text: str) -> tuple[dict[str, DosageRating], str]:
    """Parse the gene-curation TSV → `{gene: DosageRating}` plus the release date it declares.

    The release line (`#01 Aug,2026`) is the only version this file carries — ClinGen publishes no
    numbered release — so it becomes the `dataset` label the same way the ClinPGx snapshot uses its
    `CREATED_<date>` marker."""
    lines = text.splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith(_HEADER_PREFIX)), None)
    if header_index is None:
        raise ClinGenError(
            f"ClinGen curation list has no {_HEADER_PREFIX!r} header line — the file layout changed"
        )
    released = next(
        (line.lstrip("#").strip() for line in lines[:header_index] if line[1:2].isdigit()),
        "unknown",
    )
    body = [lines[header_index].lstrip("#"), *lines[header_index + 1 :]]
    reader = csv.DictReader(io.StringIO("\n".join(body)), delimiter="\t")

    ratings: dict[str, DosageRating] = {}
    for record in reader:
        gene = (record.get("Gene Symbol") or "").strip()
        if not gene:
            continue
        ratings[gene] = DosageRating(
            gene=gene,
            haploinsufficiency=decode_rating(record.get("Haploinsufficiency Score")),
            triplosensitivity=decode_rating(record.get("Triplosensitivity Score")),
        )
    return ratings, released


def fetch_curation_list(url: str = DEFAULT_CLINGEN_URL, *, timeout: float = 60.0) -> str:
    """Download the gene-curation list (a few hundred KB — small enough to fetch whole)."""
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ClinGenUnavailable(
            f"could not fetch the ClinGen curation list from {url}: {exc}"
        ) from exc
    return response.text


def enrich_dosage_sensitivity(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    declared_use: str = "unstated",
    offline: bool = False,
    write: bool = True,
    curation_text: str | None = None,
    url: str = DEFAULT_CLINGEN_URL,
) -> ClinGenResult:
    """Add ClinGen dosage rows to `gene_metrics.csv` for the genes `variants.csv` names.

    Existing rows are authoritative and merged, never clobbered — the standing rule for every pass.
    A gene ClinGen has not curated is reported as missing and gets no row: unlike gnomAD's
    "looked up, genuinely absent", ClinGen's silence means *nobody has assessed this yet*, which is
    not a fact about the gene.

    **A pass that covers nothing writes no licence row either** (S77). `licensing.csv` travels to the
    registry and is read as *this module uses this source*; recording ClinGen for a module ClinGen
    curates no gene of is a false statement in a published artifact, and it fires the
    licence-disagreement warning against a conflict that does not exist. `ClinGenResult.source_row` is
    still populated, so a caller can see the terms of what was consulted — that is a different fact
    and it has a different home.

    **`offline` (RM39).** This was the one pass in the family without the flag, so it downloaded the
    curation TSV unconditionally and the only way to stop it was to inject `curation_text=` — which
    requires the caller to have fetched the thing already, i.e. to have solved the problem the
    parameter would solve. A caller running the family under one switch had to know, out of band, that
    one member ignored it, and the cost of forgetting was silent egress from a path
    [ENRICHER.md](../../docs/ENRICHER.md) documents as making none. `enrich_frequencies` is the shape
    copied: a **no-op with a warning**, reported as `skipped_offline`, never a failure. An injected
    `curation_text` still wins, because that is not egress; ClinGen has no snapshot and this
    deliberately does not add one (that is RM38's family, and a much bigger question).
    """
    spec_dir = Path(spec_dir)
    # Through the resolver, never joined by hand (RM99): a module keeping its sidecars under
    # `derived/` (RM49) has this file there, and a pass with its own literal would read the split copy
    # and write a flat one, leaving the module with both -- the collision RM49 made an error rather
    # than a preference. `@sidecar-name-and-place`: write to the file you read.
    # Sharpest here, because `gene_metrics` writes the SAME FILE: two passes reading and
    # rewriting one table, one of them through the resolver and one not, is how a single
    # `enrich` run left a module with a `derived/` copy and a root copy that each dropped the
    # other authority's rows.
    output_path = sidecar_path(spec_dir, "gene_metrics.csv", error=ClinGenError)

    if offline and curation_text is None:
        logger.warning(
            "ClinGen dosage pass skipped: --offline. The gene-curation list is a live download with "
            "no snapshot, so this pass is a no-op offline rather than a failure. Inject the file with "
            "curation_text= if you already hold it."
        )
        return ClinGenResult(
            rows=[], covered=[], missing=[], dataset="", source_row=None, skipped_offline=True
        )

    existing: dict[tuple, GeneMetricsRow] = {}
    if output_path.exists():
        rows, errors, _ = load_csv_rows(output_path, GeneMetricsRow, "gene_metrics.csv")
        if errors:
            raise ClinGenError(f"existing gene_metrics.csv is invalid: {errors[0]}")
        for row in rows:
            existing[merge_key(row)] = row

    ratings, released = parse_curation_list(curation_text or fetch_curation_list(url))
    dataset = f"clingen_dosage_{released}"
    fetched_at = now_utc_iso()

    out: list[GeneMetricsRow] = list(existing.values())
    covered: list[str] = []
    missing: list[str] = []
    # Read off the rows rather than rebuilding the merge key here — same reason the dict now reads
    # `GeneMetricsRow._KEY_FIELDS` instead of restating `(gene, dataset)` (S51).
    done = {row.gene for row in existing.values() if row.dataset == dataset}
    for gene in module_genes(spec_dir):
        if gene in done:
            continue
        rating = ratings.get(gene)
        if rating is None or (rating.haploinsufficiency is None and rating.triplosensitivity is None):
            missing.append(gene)
            continue
        covered.append(gene)
        out.append(
            GeneMetricsRow(
                gene=gene,
                dataset=dataset,
                source=CLINGEN_SOURCE,
                status="resolved",
                fetched_at=fetched_at,
                haploinsufficiency=rating.haploinsufficiency,
                triplosensitivity=rating.triplosensitivity,
            )
        )

    out.sort(key=lambda r: (r.gene, r.dataset))
    if mode == "strict" and missing:
        raise ClinGenError(
            f"strict dosage enrichment: {len(missing)} gene(s) are not in the ClinGen curation "
            f"list: {sorted(set(missing))}. ClinGen curates a subset by design (1,520 genes at "
            f"{released}), so this is usually correct rather than an error — use mode='best_effort'."
        )
    # The terms live beside the other sources in `licensing`, not here — one place per service, so the
    # endpoint and its terms cannot drift apart.
    #
    # **Built whatever happened, written only if this pass put a row in the table (S77).** The two are
    # different questions and the result carries the row either way, so a caller can see the terms of
    # what was consulted. What reaches `licensing.csv` is the narrower claim: `sources.csv` travels to
    # the registry and is read as *this module uses this source*, which is false of a module ClinGen
    # curates nothing for. The reported case is a single-variant `SIRT6` module — not on ClinGen's
    # list, so the pass looked, wrote no `gene_metrics.csv` row, and recorded an obligation anyway.
    # Two costs, and the second is the expensive one: the declaration is a false statement in a
    # published artifact, and it fires `declared_license_disagrees` against a module whose declared
    # licence never met ClinGen's, sending an author to adjudicate a conflict that does not exist.
    #
    # **The compiler cannot catch it**, which is why the guard belongs here: `_source_checks`'s orphan
    # warning exempts the `annotation` layer deliberately (RM46), so an annotation-layer row nothing
    # uses is silent by design. This pass is the only party that knows whether it contributed.
    #
    # **Derived from the rows, the way every sibling pass already does it.** `gene_metrics`,
    # `frequencies`, `assertions` and `gene_validity` all pass `{row.source for row in out}` to
    # `record_source_terms`, so an empty pass records nothing — checked, all four. `clingen.py` alone
    # built a fixed row and wrote it unconditionally, which is the same defect shape as a check that
    # cannot fail: a declaration appearing whether or not the source contributed says nothing about
    # what the module contains. `covered` rather than `out` is the predicate because `out` carries the
    # rows a *previous* run merged in, whose terms are already recorded.
    source_row = CLINGEN_TERMS.row("annotation", declared_use=declared_use, dataset=dataset)
    if write:
        _write_gene_metrics_csv(out, output_path)
        # A pass that CONTRIBUTES from a source records it, exactly as the PGx passes do. ClinGen's CC0
        # makes no difference either way: the compile gate reads `sources.csv` and nothing else, so a
        # source that fed a row and is unrecorded is one the module cannot account for — and CC0 asks
        # for attribution, which is a thing this table exists to carry.
        if covered:
            merge_sources_file([source_row], spec_dir, error=ClinGenError)
    return ClinGenResult(
        rows=out,
        covered=sorted(set(covered)),
        missing=sorted(set(missing)),
        dataset=dataset,
        source_row=source_row,
    )
