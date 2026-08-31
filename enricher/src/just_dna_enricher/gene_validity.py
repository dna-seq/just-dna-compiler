"""`enrich-gene-validity` — the module's genes in, `gene_validity.csv` out (0.6, RM24).

The question `gene_metrics.csv` cannot answer. Constraint says how intolerant of variation a gene
*looks*; dosage sensitivity says whether losing a copy causes disease. Neither says whether variation
in this gene causes **this** disease, which is what a curated gene-validity assertion is for — and it
is the claim a clinical module most often rests on without recording.

Two submitters ship here, and they are different kinds of thing rather than two copies of one:

* **ClinGen** publishes expert-panel curations — one assertion per (gene, disease, mode of
  inheritance), each from a named Gene Curation Expert Panel working to a numbered SOP.
* **GenCC** publishes an *aggregate* of nineteen submitters (ClinGen among them, plus Orphanet,
  PanelApp, several laboratories). The same gene–disease pair routinely carries several submitters at
  different strengths, and that disagreement is the data — so `submitter` is part of the key, not a
  note. Reducing it to one row would be the bare-triple mistake the ClinPGx cross-check paid for once.

**Both vocabularies are mapped at this boundary**, never stored verbatim: ClinGen writes `Disputed`
where GenCC writes `Disputed Evidence`, and ClinGen writes `AD` where GenCC writes
`Autosomal dominant`. A consumer filtering on one spelling would silently miss the other's rows. The
verbatim wording survives in `classification_raw`, so the mapping stays auditable — the same shape
`clin_sig`/`clin_sig_raw` already has, and the same builders-store-verbatim/readers-map rule ClinGen's
dosage codes follow.

**Neither has an offline snapshot, so `--offline` makes this pass a no-op with a warning** (ClinGen's
file is ~1 MB, GenCC's ~28 MB — small enough to fetch whole and too incidental to publish a snapshot
for). `clingen.enrich_dosage_sensitivity` is the shape copied, injected text and all.

**HPO ships no route here, and both reasons were established by probe rather than assumed.** Its
release declares `terms:license https://hpo.jax.org/app/license`; that URL answers **HTTP 404** with a
JavaScript shell, and OBO Foundry records the licence as a bare label `hpo` with no SPDX id — so its
terms cannot be established from any machine-readable source, and an unestablished permission is not a
permission. Separately, `genes_to_phenotype.txt` is gene × HP feature × frequency, a different grain
from this table entirely, and `genes_to_disease.txt`'s `association_type`
(MENDELIAN/POLYGENIC/UNKNOWN, 8,288 of 15,944 rows UNKNOWN) is a **mechanism class, not an evidence
grade** — putting it in `classification` would overload the axis. The row shape holds an HPO row
perfectly well; what is missing is a link this tier may take the data over.
"""

import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import merge_key
from just_dna_format.gene_validity import (
    GeneValidityRow,
    superseded_groups,
    undecidable_groups,
)
from just_dna_format.layout import atomic_writer
from just_dna_format.normalize import normalize_utc_timestamp, now_utc_iso

from just_dna_enricher.gene_metrics import GeneMetricsEnrichmentError, module_genes
from just_dna_enricher.licensing import CLINGEN_TERMS, GENCC_TERMS, record_source_terms, sidecar_path

logger = logging.getLogger(__name__)

#: ClinGen's gene–disease validity export. A CSV with a four-line preamble, a `+++`-delimited header,
#: and a second `+++` line before the data — neither a plain CSV nor a comment-prefixed one.
DEFAULT_CLINGEN_VALIDITY_URL = "https://search.clinicalgenome.org/kb/gene-validity/download"

#: GenCC's full submission export — every submitter's assertions in one CSV, ~28 MB.
DEFAULT_GENCC_URL = "https://search.thegencc.org/download/action/submissions-export-csv"

CLINGEN_SOURCE = CLINGEN_TERMS.source
GENCC_SOURCE = GENCC_TERMS.source

#: Which submitters this pass can reach, by the name that joins `sources.csv.source`.
VALID_VALIDITY_SOURCES: frozenset[str] = frozenset({CLINGEN_SOURCE, GENCC_SOURCE})

_CLINGEN_HEADER_FIRST_CELL = "GENE SYMBOL"
_CLINGEN_RELEASE_PREFIX = "FILE CREATED:"

#: Submitter wording → `vocab.VALID_GENE_VALIDITY`. Keyed on the lowercased, whitespace-collapsed
#: value so a submitter's capitalization drift cannot break it, and holding **both** spellings of the
#: three verdicts the two sources phrase differently (`Disputed` / `Disputed Evidence`).
#:
#: A wording this map does not know maps to `None` with a warning, exactly as `clingen.decode_rating`
#: handles an unrecognized dosage code: an unknown value means the source published a classification
#: this release does not model, and guessing at where it sits on the ladder would be worse than
#: recording nothing. `classification_raw` keeps it visible either way.
CLASSIFICATION_BY_WORDING: dict[str, str] = {
    "definitive": "definitive",
    "strong": "strong",
    "moderate": "moderate",
    "limited": "limited",
    "supportive": "supportive",
    "disputed": "disputed",
    "disputed evidence": "disputed",
    "refuted": "refuted",
    "refuted evidence": "refuted",
    "no known disease relationship": "no_known_disease_relationship",
    "no reported evidence": "no_known_disease_relationship",
    "animal model only": "animal_model_only",
}

#: Submitter wording → `vocab.VALID_INHERITANCE_MODE`. ClinGen's two-letter codes and GenCC's HPO term
#: labels are the same facts spelled two ways; both are keys here so the column means one thing.
#:
#: `UD`/`Unknown` become `undetermined` — a **stated** finding, an expert panel having looked and not
#: settled it, which is why the vocabulary carries a member for it instead of the cell being emptied.
INHERITANCE_BY_WORDING: dict[str, str] = {
    "ad": "autosomal_dominant",
    "autosomal dominant": "autosomal_dominant",
    "autosomal dominant inheritance": "autosomal_dominant",
    "ar": "autosomal_recessive",
    "autosomal recessive": "autosomal_recessive",
    "autosomal recessive inheritance": "autosomal_recessive",
    "xl": "x_linked",
    "x-linked": "x_linked",
    "x-linked inheritance": "x_linked",
    "xld": "x_linked_dominant",
    "x-linked dominant": "x_linked_dominant",
    "x-linked dominant inheritance": "x_linked_dominant",
    "xlr": "x_linked_recessive",
    "x-linked recessive": "x_linked_recessive",
    "x-linked recessive inheritance": "x_linked_recessive",
    "yl": "y_linked",
    "y-linked": "y_linked",
    "y-linked inheritance": "y_linked",
    "mt": "mitochondrial",
    "mitochondrial": "mitochondrial",
    "mitochondrial inheritance": "mitochondrial",
    "sd": "semidominant",
    "semidominant": "semidominant",
    "semidominant inheritance": "semidominant",
    "ud": "undetermined",
    "unknown": "undetermined",
    "undetermined": "undetermined",
    "unknown inheritance": "undetermined",
}

#: The column order, **derived from the model** rather than hand-kept — the `SOURCES_FIELDNAMES` rule,
#: applied at the first opportunity since it was written down. A literal list is how `sources.csv` lost
#: `redistribution` for a whole release, and `GeneValidityRow` has no compiler-stamped fields, so every
#: declared field is a column a pass or a curator may fill. Declaration order is the reading order.
_FIELDNAMES = list(GeneValidityRow.model_fields)


class GeneValidityError(RuntimeError):
    """A gene-validity fetch or parse failed in a way the caller must see."""


class GeneValidityUnavailable(GeneValidityError):
    """A submitter's export could not be fetched, so it was never actually asked (RM101).

    The same split `ClinGenUnavailable` draws, and it is here because this module has the identical
    shape: `GeneValidityError` covers both "could not fetch the gene-validity export" and "the
    existing `gene_validity.csv` is invalid", and only the first means a source was asked. Found by
    walking the passes rather than by a report — S37 named ClinGen's instance and this one is its
    twin, which is why the repair is a walked registry and not two hand-picked sites.
    """


@dataclass
class ValidityAssertion:
    """One parsed assertion, before it is scoped to a module's genes."""

    gene: str
    gene_id: str | None = None
    disease_id: str | None = None
    disease_label: str | None = None
    moi: str | None = None
    classification: str | None = None
    classification_raw: str | None = None
    classification_date: str | None = None
    submitter: str | None = None
    assertion_id: str | None = None
    report_url: str | None = None


@dataclass
class GeneValidityResult:
    rows: list[GeneValidityRow]
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    dataset: str = ""
    source: str = ""
    #: Cell values this release could not interpret, de-duplicated and prefixed by their column —
    #: a classification or inheritance wording the maps do not know, or a curation date that is not a
    #: readable timestamp. Reported rather than logged per row: at 30,410 GenCC submissions one
    #: unknown wording would otherwise print thousands of lines saying one thing, which is the
    #: aggregation rule this tier has needed four times already.
    #:
    #: Every one of them costs a **cell**, never a row and never the pass: the assertion is kept with
    #: that column empty, which is this codebase's answer to an unknown everywhere else.
    unmapped: list[str] = field(default_factory=list)
    #: Gene-disease claims where a later curation replaced an earlier one, and both rows are kept
    #: (RM108). Rendered as `gene/disease/moi/submitter`. **Never a reason to fail the pass, in either
    #: mode**: a curating body re-curating is the source working, not the module being wrong.
    superseded: list[str] = field(default_factory=list)
    #: Claims carrying several curations that nothing orders — a tie on `classification_date`, or a
    #: member stating none. Reported apart from `superseded` because it asks the reader for a
    #: different thing: the archive did not say enough to tell, rather than the archive having moved
    #: on. The house algebra withholds here rather than picking a winner from an identifier.
    undecidable: list[str] = field(default_factory=list)
    #: The pass did not run because the deployment is offline and neither submitter has a snapshot.
    skipped_offline: bool = False


def map_classification(wording: str | None, *, unmapped: set[str] | None = None) -> str | None:
    """A submitter's own classification wording → a `VALID_GENE_VALIDITY` member, or `None`.

    `None` for blank and for a wording this release does not model; the caller collects the unknown
    into `unmapped` so it is reported once with a count rather than per row.
    """
    text = " ".join((wording or "").split()).lower()
    if not text:
        return None
    mapped = CLASSIFICATION_BY_WORDING.get(text)
    if mapped is None and unmapped is not None:
        unmapped.add(f"classification={wording!r}")
    return mapped


def read_curation_date(raw: str | None, *, unmapped: set[str] | None = None) -> str | None:
    """A submitter's curation date → the canonical UTC spelling, or `None` when it cannot be read.

    The two submitters spell one instant two ways — ClinGen `2024-03-14T16:00:00.000Z`, GenCC
    `2018-03-30 13:31:56` — which `normalize_utc_timestamp` reconciles, and which is why the column is
    canonicalized rather than stored verbatim: two spellings in a fact column hash as two facts.

    It is applied **here** rather than left to the model's validator because the validator *raises*,
    and this column is one cell of one row of an export with 30,000 of them from nineteen independent
    submitters. One unreadable date would otherwise cost the whole pass, with a bare pydantic
    traceback. A date that cannot be read is an unknown: withhold the cell, keep the assertion, and
    report the value once — exactly what an unrecognised classification wording already does.
    """
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return normalize_utc_timestamp(text)
    except ValueError:
        if unmapped is not None:
            unmapped.add(f"classification_date={raw!r}")
        return None


def map_inheritance(wording: str | None, *, unmapped: set[str] | None = None) -> str | None:
    """A submitter's own mode-of-inheritance wording → a `VALID_INHERITANCE_MODE` member, or `None`."""
    text = " ".join((wording or "").split()).lower()
    if not text:
        return None
    mapped = INHERITANCE_BY_WORDING.get(text)
    if mapped is None and unmapped is not None:
        unmapped.add(f"moi={wording!r}")
    return mapped


def parse_clingen_validity(
    text: str, *, unmapped: set[str] | None = None
) -> tuple[list[ValidityAssertion], str]:
    """Parse ClinGen's gene-validity CSV → `(assertions, release label)`.

    The file's layout is the reason this is not two lines of `csv.DictReader`: four preamble rows
    (title, `FILE CREATED: …`, the webpage), then a `+++` separator, then the real header, then a
    second `+++` separator, then the data. Anchoring on the header's first cell rather than on a row
    index means a fifth preamble line does not silently shift every column.

    `FILE CREATED:` is the only version the file carries — ClinGen publishes no numbered release for
    it — so it becomes the `dataset` label, exactly as `clingen.parse_curation_list` uses that file's
    own date line.
    """
    rows = list(csv.reader(io.StringIO(text)))
    header_index = next(
        (i for i, row in enumerate(rows) if row and row[0].strip() == _CLINGEN_HEADER_FIRST_CELL),
        None,
    )
    if header_index is None:
        raise GeneValidityError(
            f"ClinGen gene-validity export has no {_CLINGEN_HEADER_FIRST_CELL!r} header cell — the "
            f"file layout changed. Refusing rather than guessing at the column order."
        )
    released = next(
        (
            row[0].split(":", 1)[1].strip()
            for row in rows[:header_index]
            if row and row[0].strip().startswith(_CLINGEN_RELEASE_PREFIX)
        ),
        "unknown",
    )
    header = [cell.strip() for cell in rows[header_index]]
    out: list[ValidityAssertion] = []
    for row in rows[header_index + 1 :]:
        if not row or row[0].startswith("+++") or len(row) != len(header):
            continue
        record = dict(zip(header, (cell.strip() for cell in row), strict=True))
        gene = record.get("GENE SYMBOL") or ""
        if not gene:
            continue
        report_url = record.get("ONLINE REPORT") or None
        out.append(
            ValidityAssertion(
                gene=gene,
                gene_id=record.get("GENE ID (HGNC)") or None,
                disease_id=record.get("DISEASE ID (MONDO)") or None,
                disease_label=record.get("DISEASE LABEL") or None,
                moi=map_inheritance(record.get("MOI"), unmapped=unmapped),
                classification=map_classification(record.get("CLASSIFICATION"), unmapped=unmapped),
                classification_raw=record.get("CLASSIFICATION") or None,
                classification_date=read_curation_date(
                    record.get("CLASSIFICATION DATE"), unmapped=unmapped
                ),
                # The curating panel, not "ClinGen": a module reading this column wants to know which
                # expert panel ruled, and every row here would otherwise say the same word.
                submitter=record.get("GCEP") or None,
                assertion_id=_clingen_assertion_id(report_url),
                report_url=report_url,
            )
        )
    return out, released


def _clingen_assertion_id(report_url: str | None) -> str | None:
    """ClinGen's stable assertion id, taken from the report URL's last path segment.

    The export publishes the id only inside that URL (`…/gene-validity/CGGV:assertion_92de3832-…`),
    so this is a read of the source's own value rather than a synthesised one — which is the line
    between carrying an identity and inventing one.
    """
    if not report_url:
        return None
    tail = report_url.rstrip("/").rsplit("/", 1)[-1].strip()
    return tail or None


def parse_gencc(
    text: str, *, unmapped: set[str] | None = None
) -> tuple[list[ValidityAssertion], str]:
    """Parse GenCC's submission export → `(assertions, release label)`.

    GenCC publishes no release identifier at all, so the label is derived from the latest
    `submitted_run_date` the file carries — the same class of answer ClinGen's `FILE CREATED:` gives,
    read from the data because the file states nothing else. `unknown` when even that is absent, which
    is honest rather than a fabricated date.

    Every row is one submitter's assertion and they are all kept. The `submitted_as_*` columns are the
    submitter's own pre-harmonization wording; the unprefixed ones are GenCC's normalization onto
    MONDO/HPO, which is what this table wants — the harmonization is GenCC's published work, not an
    inference of ours.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "gene_symbol" not in reader.fieldnames:
        raise GeneValidityError(
            "GenCC export has no 'gene_symbol' column — the file layout changed. Refusing rather "
            "than guessing at the column order."
        )
    out: list[ValidityAssertion] = []
    run_dates: set[str] = set()
    for record in reader:
        gene = (record.get("gene_symbol") or "").strip()
        if not gene:
            continue
        run_date = (record.get("submitted_run_date") or "").strip()
        if run_date:
            run_dates.add(run_date)
        out.append(
            ValidityAssertion(
                gene=gene,
                gene_id=(record.get("gene_curie") or "").strip() or None,
                disease_id=(record.get("disease_curie") or "").strip() or None,
                disease_label=(record.get("disease_title") or "").strip() or None,
                moi=map_inheritance(record.get("moi_title"), unmapped=unmapped),
                classification=map_classification(
                    record.get("classification_title"), unmapped=unmapped
                ),
                classification_raw=(record.get("classification_title") or "").strip() or None,
                classification_date=read_curation_date(
                    record.get("submitted_as_date"), unmapped=unmapped
                ),
                submitter=(record.get("submitter_title") or "").strip() or None,
                assertion_id=(record.get("uuid") or "").strip() or None,
                report_url=(record.get("submitted_as_public_report_url") or "").strip() or None,
            )
        )
    return out, (max(run_dates) if run_dates else "unknown")


def fetch_validity_export(url: str, *, timeout: float = 180.0) -> str:
    """Download a submitter's whole export.

    One request for the whole file rather than a per-gene query, because neither submitter offers one
    and both files are small enough to hold (1 MB and 28 MB). The timeout is generous for the same
    reason: GenCC's export is a single 28 MB response and a 60-second budget times out on a slow link
    while the request is perfectly healthy.
    """
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeneValidityUnavailable(
            f"could not fetch the gene-validity export from {url}: {exc}"
        ) from exc
    return response.text


def enrich_gene_validity(
    spec_dir: Path,
    *,
    source: str = CLINGEN_SOURCE,
    mode: str = "best_effort",
    offline: bool = False,
    write: bool = True,
    export_text: str | None = None,
    url: str | None = None,
) -> GeneValidityResult:
    """Add curated gene–disease assertions to `gene_validity.csv` for the genes `variants.csv` names.

    Existing rows are authoritative and merged, never clobbered — the standing rule for every pass,
    and the standing consequence with it: to regenerate after a machinery change, delete the file
    first. Two rows are the same row when `_merge_key` says so: the source's own `assertion_id` where
    it publishes one, else `(gene, disease_id, moi, submitter, dataset)` — the source's own grain
    rather than a convenience, because ClinGen carries 59 (gene, disease) pairs whose two rows differ
    only by mode of inheritance, and GenCC carries the same pair from several submitters at different
    strengths.

    **A gene the submitter has not curated gets no row**, and is reported in `missing`. That follows
    `clingen.enrich_dosage_sensitivity` exactly and for its reason: a curating body's silence means
    nobody has assessed the gene yet, which is not a fact about the gene, and writing a `not_found`
    row would state one. It is also why `strict` is a *report*, not a refusal to have looked — both
    submitters curate a subset by design.

    `offline` makes the pass a no-op with a warning (`skipped_offline`), never a failure: neither
    submitter ships a snapshot. An injected `export_text` still wins, because handing over bytes you
    already hold is not egress.
    """
    spec_dir = Path(spec_dir)
    if source not in VALID_VALIDITY_SOURCES:
        raise GeneValidityError(
            f"unknown gene-validity source {source!r}; this tier can reach "
            f"{sorted(VALID_VALIDITY_SOURCES)}. HPO is deliberately absent — see this module's "
            f"docstring for the two reasons, both established by probe."
        )
    output_path = sidecar_path(spec_dir, "gene_validity.csv", error=GeneValidityError)

    if offline and export_text is None:
        logger.warning(
            "Gene-validity pass skipped: --offline. Neither ClinGen nor GenCC publishes a snapshot, "
            "so this pass is a no-op offline rather than a failure. Inject the export with "
            "export_text= if you already hold it."
        )
        return GeneValidityResult(rows=[], skipped_offline=True, source=source)

    existing_rows: list[GeneValidityRow] = []
    if output_path.exists():
        parsed, errors, _ = load_csv_rows(output_path, GeneValidityRow, output_path.name)
        if errors:
            raise GeneValidityError(f"existing {output_path.name} is invalid: {errors[0]}")
        existing_rows = parsed

    unmapped: set[str] = set()
    text = export_text if export_text is not None else fetch_validity_export(
        url or (DEFAULT_CLINGEN_VALIDITY_URL if source == CLINGEN_SOURCE else DEFAULT_GENCC_URL)
    )
    if source == CLINGEN_SOURCE:
        assertions, released = parse_clingen_validity(text, unmapped=unmapped)
        dataset = f"clingen_gene_validity_{released}"
    else:
        assertions, released = parse_gencc(text, unmapped=unmapped)
        dataset = f"gencc_submissions_{released}"

    by_gene: dict[str, list[ValidityAssertion]] = {}
    for assertion in assertions:
        by_gene.setdefault(assertion.gene, []).append(assertion)

    fetched_at = now_utc_iso()
    seen = {_merge_key(row) for row in existing_rows}
    out: list[GeneValidityRow] = list(existing_rows)
    covered: list[str] = []
    missing: list[str] = []
    for gene in _module_genes(spec_dir):
        found = by_gene.get(gene, [])
        if not found:
            missing.append(gene)
            continue
        covered.append(gene)
        for assertion in found:
            row = GeneValidityRow(
                gene=assertion.gene,
                gene_id=assertion.gene_id,
                disease_id=assertion.disease_id,
                disease_label=assertion.disease_label,
                moi=assertion.moi,
                classification=assertion.classification,
                classification_raw=assertion.classification_raw,
                classification_date=assertion.classification_date,
                submitter=assertion.submitter,
                assertion_id=assertion.assertion_id,
                report_url=assertion.report_url,
                dataset=dataset,
                source=source,
                status="resolved",
                fetched_at=fetched_at,
            )
            key = _merge_key(row)
            if key in seen:
                continue
            seen.add(key)
            out.append(row)

    out.sort(key=_sort_key)
    if unmapped:
        # One line naming the count and the distinct wordings, not one per row: 30,410 GenCC rows would
        # otherwise print thousands of copies of the same finding. Grouped by the *value* that was not
        # recognised, which is the thing a reader has to act on.
        logger.warning(
            "%d submitter value(s) could not be interpreted by this release and were left unset — "
            "the assertion is kept, only the cell is empty (a classification's verbatim wording also "
            "survives in classification_raw): %s",
            len(unmapped), sorted(unmapped),
        )
    # **Currency is derived, never written** (RM108). ClinGen's `assertion_id` embeds the curation
    # timestamp, so a re-curated assertion arrives under a different id, misses `_merge_key` and is
    # appended beside the row it replaces — correctly, because both are true records. What was missing
    # is that nobody said so. A `superseded` column was refused: the row that would have to be marked
    # is the one already in the file, and merge-not-clobber forbids this pass editing it, so the
    # marker would be right on every run except the one that created the ambiguity.
    #
    # Reported in BOTH modes and raising in neither. The rule is the same one this pass already
    # applies to `missing` a few lines down — `strict` is a report, not a refusal to have looked —
    # and the stronger form of it: a finding no edit to the spec directory could clear is not a
    # `strict` matter, and the only edit available here is deleting a row, which falsifies the record.
    superseded = [_currency_label(g) for g in superseded_groups(out)]
    undecidable = [_currency_label(g) for g in undecidable_groups(out)]
    if superseded:
        logger.warning(
            "%d gene-disease claim(s) carry a later curation, so an earlier row is superseded and "
            "kept: %s. Nothing is deleted — the newest classification_date reads as current, and the "
            "compiled manifest publishes that one. A curating body re-curating is not an error.",
            len(superseded), superseded[:5] + (["..."] if len(superseded) > 5 else []),
        )
    if undecidable:
        logger.warning(
            "%d gene-disease claim(s) carry several curations that nothing orders: %s. Two rows share "
            "a classification_date, or one states none, so no row is called current and none "
            "superseded — every classification stays published. Withheld deliberately.",
            len(undecidable), undecidable[:5] + (["..."] if len(undecidable) > 5 else []),
        )
    result = GeneValidityResult(
        rows=out,
        covered=sorted(set(covered)),
        missing=sorted(set(missing)),
        dataset=dataset,
        source=source,
        unmapped=sorted(unmapped),
        superseded=superseded,
        undecidable=undecidable,
    )
    if mode == "strict" and result.missing:
        raise GeneValidityError(
            f"strict gene-validity enrichment: {len(result.missing)} gene(s) have no {source} "
            f"assertion: {result.missing}. Both submitters curate a subset by design, so this is "
            f"usually correct rather than an error — use mode='best_effort'."
        )
    if write:
        _write_gene_validity_csv(out, output_path)
        # The pass consulted a source, so the module records its terms. Both are CC0 and neither can
        # taint anything at this layer — which is exactly why the row is worth writing: what it carries
        # is the attribution both submitters ask for, and a source recorded nowhere is a source the
        # module cannot account for.
        record_source_terms(
            {row.source for row in out if row.source},
            "gene_validity",
            spec_dir,
            error=GeneValidityError,
        )
    return result


def _module_genes(spec_dir: Path) -> list[str]:
    """The module's gene symbols, failing as *this* pass rather than as the one it borrows from.

    `gene_metrics.module_genes` is the right function — the gene set is "what `variants.csv` says this
    module is about", and a second copy would be a second answer — but it reports an invalid
    `variants.csv` as a `GeneMetricsEnrichmentError`, which no caller of this pass is catching. The CLI
    command then printed a pydantic traceback where a diagnosis belongs, on the commonest authoring
    mistake there is. Same re-raise `licensing.sidecar_path` performs for `SidecarCollision`, and for
    the same reason: a pass must fail as itself.
    """
    try:
        return module_genes(spec_dir)
    except GeneMetricsEnrichmentError as exc:
        raise GeneValidityError(str(exc)) from exc


def _currency_label(group: tuple) -> str:
    """A currency group as one readable token, skipping the parts the source left empty.

    `gene/disease/moi/submitter`, which is `CURRENCY_GROUP_FIELDS` in its declared order — read off
    the tuple that function built rather than re-derived, so the label cannot describe a different
    grouping from the one that produced it.
    """
    return "/".join(str(part) for part in group if part)


def _merge_key(row: GeneValidityRow) -> tuple:
    """What makes two assertions the same assertion.

    `assertion_id` when the source published one — it is the source's own answer to this question, and
    it survives a re-worded disease label. Otherwise the source's grain: gene, disease, mode of
    inheritance, submitter, release. Never `(gene, disease)` alone, which collapses 59 real ClinGen
    curations, and never without `submitter`, which collapses the disagreement GenCC exists to publish.

    Read off `GeneValidityRow._KEY_FIELDS` / `_KEY_FALLBACK_FIELDS` rather than restated here, so
    this pass and the published `hints.key_fields("gene_validity.csv")` cannot drift apart (S51).
    """
    return merge_key(row)


def _sort_key(row: GeneValidityRow) -> tuple:
    """Deterministic emission order (Principle 7): gene, then disease, then inheritance, then submitter.

    Every component is rendered to a string so a null sorts beside a value instead of raising — a row
    whose source published no disease CURIE is legal, and an ordering that crashed on one would make
    the emitted table depend on which rows happened to be complete.
    """
    return (
        row.gene,
        row.disease_id or "",
        row.moi or "",
        row.submitter or "",
        row.assertion_id or "",
        row.dataset,
    )


def _write_gene_validity_csv(rows: list[GeneValidityRow], output_path: Path) -> None:
    """Write the table with a fixed column order and canonical cells (byte-stable across runs).

    **This file is a pure build product since 0.7 (RM124).** Hand-editing it is not expected and
    nothing preserves such an edit — a correction to a derived row belongs in `overrides.csv` beside
    the spec, where the compiler applies it on every build and it travels with the reason it was
    made. That is what makes deleting this file and re-running cost nothing: the author's judgements
    are not in here to lose. The re-run itself is unchanged, and still gap-fills rather than re-asking
    every subject; what changed is that leaving a recorded row alone now risks nothing.

    An overlay row reaches one assertion by its `assertion_id`, which this table's own merge key uses
    when the source published one. A row keyed only on the gene's grain can be corrected
    group-scoped, by `gene`, and not more finely than that.
    """
    with atomic_writer(output_path, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in _FIELDNAMES})


def _cell(value: object) -> str:
    """Render one value to a canonical CSV cell, matching the compiler's reverse writer exactly.

    Every column here is a string or null, so this is the two easy branches of `_scalar_cell` — kept
    as its own function anyway, because a column added later must be rendered the way the reverse
    writer would render it or the two spellings would differ after a round trip.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
