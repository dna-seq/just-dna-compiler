"""Authoring hints — answer questions about authored cells without ever writing one (0.5).

The third piece of the authoring surface, beside `draft` (append rows into an existing table) and
`scaffold` (create tables from nothing). This one **writes nothing at all**: CSV text in, a report
out. Applying anything is the human's move, or `draft.append_rows`'.

**Why a hint may not simply fill the cell it knows the answer to.** COMPILER.md's Class 2,
validate-by-redundancy, is "where most real authoring bugs are caught", and every check in it
compares *two independently-authored things*. Fill `chrom`/`start` from Ensembl and the compiler's
rsid↔coordinate check compares Ensembl against Ensembl; fill `doi` from PubMed and
`literature._doi_conflicts` compares PubMed against PubMed. The check does not merely become
tautological — for an rsid-only row `resolution._verify` never runs at all, so the row moves from
*honestly unverified* to *verified against whatever filled it*, and the compile now reports success.
Auto-filling does not bend a convention; it deletes a validation class.

The codebase already made this argument once, for one field, in `literature`: Crossref is asked about
the **authored** DOI in preference to the derived one, because checking the registry's own DOI "would
be circular — it exists by construction". This module generalizes that to every cell.

So hints are partitioned by what the value *is*, not by where it came from:

* **normalized** — a re-spelling of the author's own cell by a rule the model already applies on
  load. Safe to render, and arguably must be: the model does it anyway, silently. `DiplotypeRow`
  swaps `haplotype_a`/`haplotype_b` without saying so.
* **derived** — computed from other authored cells on the same row. Not rendered: it adds no
  information and spends a redundancy (`p_value` → `p_value_num` is cross-checked at compile).
* **advisory** — an external fact. Reported, never rendered, whether or not a checker consumes it
  today; `refusal` names why.

`csv_out` therefore differs from the input only by `normalized` alterations, and every difference is
listed. Nothing here needs the network: that half lives in the enricher, which supplies the advisory
facts through the same report shape.
"""

import csv
import io
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from just_dna_format.base import authored_field_names, field_category, field_vocabularies
from just_dna_format.binning import MeasureBinRow, deprecation_warnings, validate_bins
from just_dna_format.layout import sidecar_spellings
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from pydantic import BaseModel

from just_dna_compiler.compiler import _FACT_TABLES, _list_cell, _list_fields, _scalar_cell
from just_dna_compiler.draft import (
    DRAFTABLE,
    DraftError,
    authoring_requirements,
    model_for,
    natural_key,
)

#: `csv name -> row model` for the tables a **machine** produces: the fact sidecars and
#: `resolution.csv`. The read-only counterpart to `draft.DRAFTABLE`, which is authored kinds only and
#: refuses these by design — so a tool asked "what is in `frequencies.csv`" had no public way to answer
#: (S47). Every consumer that wanted one was reaching for `compiler._FACT_TABLES`, which is private and
#: free to move in a patch, or hand-keeping the same seven lines and being the one that missed the
#: eighth table.
#:
#: **Derived from `_FACT_TABLES`, never restated** — a hand-kept parallel map is the defect this
#: closes, so re-introducing one here to publish it would be absurd. A test asserts the keys against
#: `_FACT_TABLES` plus `resolution.csv`, so a new fact table fails CI rather than becoming silently
#: undescribable.
#:
#: **Both spellings of the licence table are keys**, exactly as `DRAFTABLE` does it and for the same
#: reason: the map is keyed on the filename a *caller* names, and a caller holding a module that
#: carries `licensing.csv` must not be told it is not a table of this format. `sources.csv` is
#: deliberately in both maps — it is the one fact table a human legitimately writes.
#:
#: `verification.json` is **not** here: it is the attestation document, not a fact table — no parquet,
#: no `_FACT_TABLES` row, and not a CSV at all.
DERIVED_TABLE_MODELS: dict[str, type[BaseModel]] = {
    "resolution.csv": ResolutionRow,
    **{
        spelling: model
        for csv_name, _parquet, model in _FACT_TABLES
        for spelling in sidecar_spellings(csv_name)
    },
}


def derived_model_for(csv_name: str) -> type[BaseModel]:
    """The row model for a machine-produced CSV, or `DraftError` for a name this format does not read.

    The counterpart to `draft.model_for`, which answers for authored kinds only. Between them they
    cover every CSV the compiler reads, and a tool that dispatches on a filename needs both: an author
    reading `resolution.csv` or `frequencies.csv` — files they must read and must never hand-finish —
    was getting *"not an authored table of this format"*, which is true and useless (S47).

    Raises `DraftError` rather than returning `None` so the failure matches `model_for`'s, on the house
    rule that a generic rejection is a dead end where a specific one is a fix: the message names the
    authored route, because asking this function for `variants.csv` is the likely mistake and the
    answer to it is one call away.
    """
    model = DERIVED_TABLE_MODELS.get(csv_name)
    if model is None:
        if csv_name in DRAFTABLE:
            raise DraftError(
                f"{csv_name!r} is an authored table, not a machine-produced one — "
                f"use model_for({csv_name!r}) instead."
            )
        raise DraftError(
            f"{csv_name!r} is not a machine-produced table of this format. "
            f"Known: {sorted(DERIVED_TABLE_MODELS)}"
        )
    return model


#: How an alteration relates to what the author wrote. `frozenset[str]` + validation, never an Enum
#: (Principle 6), and the three are ordered by how much they add: nothing, arithmetic, the world.
ALTERATION_KINDS: frozenset[str] = frozenset({"normalized", "derived", "advisory"})

#: Why a hint is not rendered into `csv_out`. Only `advisory`/`derived` alterations carry one.
REFUSAL_REASONS: frozenset[str] = frozenset(
    {
        "redundancy_bearing",  # a Class-2 check compares this cell against a source
        "identity_bearing",    # writing it would re-key the row (variant_key / authored_ident)
        "intent_bearing",      # only the author knows (effect_allele, which paper, which trait)
        "derived_not_stored",  # the compiler materializes it; storing it duplicates a fact
        "attestation_bearing", # the cell asserts that a HUMAN read something (provenance_quote)
    }
)

#: The cells whose content is an attestation, so a machine filling one states something false rather
#: than something unverifiable. A *fifth* reason rather than a reading of `redundancy_bearing`, because
#: the two failures differ in kind and the difference is the whole point: filling `doi` from the
#: registry that checks it makes a Class-2 comparison **vacuous**, and every other entry on that map is
#: that shape. Filling `provenance_quote` from a fulltext a tool has just fetched is a **false claim of
#: provenance** — the column's meaning is "a curator read this passage in this paper", and no lookup can
#: make that true. Both cells are also redundancy-bearing (see `REDUNDANCY_BEARING`); this names the
#: sharper reason a provider must refuse on.
ATTESTATION_BEARING: frozenset[str] = frozenset({"provenance_quote", "provenance_regex"})

#: Severity of a finding. Hints never fail a build — the checks that do already exist in the
#: compiler and the enricher, each with the severity the charter assigns it.
FINDING_LEVELS: frozenset[str] = frozenset({"error", "warning", "info"})

#: The authored cells a Class-2 check cross-examines, and the check that reads each. A hint about one
#: of these is advisory by construction. Kept beside the partition it enforces so a new check that
#: forgets to register lands here rather than silently becoming fillable.
REDUNDANCY_BEARING: dict[str, str] = {
    "rsid": "compiler.resolution._verify (rsid vs coordinate) + identifiers.check_rsids",
    "chrom": "compiler.resolution._verify (rsid vs coordinate)",
    "start": "compiler.resolution._verify (rsid vs coordinate)",
    "ref": "enricher.sequences.verify_reference_alleles (authored ref vs the genome)",
    "alts": "compiler allele-membership check; alts is a resolution fact in artifact.digest",
    "doi": "enricher.literature._doi_conflicts (authored doi vs the registry's)",
    # The other citation identifier, registered when the PMCID → PMID lookup landed (RM50). Same
    # argument as `doi`, one registry over: `literature.exists` asks PubMed whether the **authored**
    # pmid resolves, so filling it from NCBI's id converter would compare NCBI with itself. The
    # converter therefore reports the id as an advisory and never writes it.
    "pmid": "enricher.literature (authored pmid vs PubMed's record: LiteratureRow.exists)",
    "clin_sig": "enricher.clinical.verify_clin_sig (authored call vs ClinVar's)",
    "function_status": "enricher.pgx.enrich_pgx (authored function vs PharmVar and CPIC)",
    "evidence_level": "enricher.clinpgx (authored level vs the ClinPGx snapshot)",
    "p_value_num": "compiler p_value ↔ p_value_num agreement",
    "acmg_sf": "enricher.acmg.check_acmg_sf (authored flag vs the ACMG SF list)",
    # Both compared against the Europe PMC fulltext by `enricher.literature._study_quote_found` to
    # produce `LiteratureRow.quotes_found`, so they qualify under this map's own definition and were
    # simply missing — the drift its docstring predicts. They additionally carry
    # `attestation_bearing`, which is the reason a provider must refuse on: see ATTESTATION_BEARING.
    # **A retrieved fulltext also degrades what `quotes_found` proves.** The check is only independent
    # evidence while the author read the paper and the tool read it separately; once a machine has
    # fetched the text, a hit demonstrates that the quote pairs with the PMID — worth having, since it
    # still catches a quote filed against the wrong paper — but no longer that the claim is in the
    # article, because nothing establishes a human ever looked.
    "provenance_quote": "enricher.literature._study_quote_found (authored passage vs the fulltext)",
    "provenance_regex": "enricher.literature._study_quote_found (authored pattern vs the fulltext)",
}


@dataclass(frozen=True)
class Alteration:
    """One cell that differs between an input row and the emitted one, or that a source disagrees with.

    `applied` is the whole contract: it is True only for `normalized`, and `csv_out` reflects exactly
    the applied ones. A caller can therefore diff the report instead of trusting the prose."""

    row: int
    column: str
    before: str
    after: str
    kind: str
    applied: bool
    source: str = "model"
    refusal: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Finding:
    """Something worth telling the author about a cell or a row. Never fails a build.

    **Two coordinates, because the two audiences count differently** (S18). `row` is a 0-based index
    into the *data* rows, which is what a caller indexing `csv_out` or a parsed list needs. `line` is
    the 1-based line number **in the file, counting the header**, which is what the author's editor
    shows and what `validate_spec`/`compile_module` already report (`line 2 [source]: …`). Neither was
    stated, and the only way to learn which one `row` was, was to author a broken row and count — on a
    short table an off-by-one still lands on a real row, so it misdirects instead of obviously breaking.

    `line` is set by whatever builds the finding, since only that code knows whether the input carried
    a header at all; `inspect_rows` fills it for every row-scoped finding. It stays `None` for a
    table-scoped finding, exactly as `row` does."""

    row: int | None
    column: str | None
    level: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class FieldOptions:
    """The values a column accepts, for a picker.

    `notes` is the per-member prose for the vocabularies whose member *name* cannot carry the whole
    rule, `None` for the rest — a picker offering `largest` beside `largest_alt` has nowhere else to
    say which of them counts the reference element. It rides here because it rides on the marker
    (`base.vocabulary`), so the surface an author reaches when their row was rejected knows what
    `describe` and the whole-schema reference know."""

    column: str
    vocabulary: str
    options: list[str]
    closed: bool
    notes: dict[str, str] | None = None


@dataclass
class HintReport:
    """CSV text in, the same CSV out plus everything known about it.

    Invariants, all pinned by tests: `csv_out` has the same row count and order as the input; only
    `normalized` alterations are applied; every applied change appears in `alterations`."""

    csv_name: str
    header: list[str]
    rows_in: int
    csv_out: list[str]
    alterations: list[Alteration] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    options: list[FieldOptions] = field(default_factory=list)
    requirements: dict[str, Any] = field(default_factory=dict)

    @property
    def applied(self) -> list[Alteration]:
        return [a for a in self.alterations if a.applied]

    @property
    def advisory(self) -> list[Alteration]:
        return [a for a in self.alterations if not a.applied]

    @property
    def unchanged(self) -> bool:
        return not self.applied

    def to_json(self) -> str:
        """The machine form. Lists keep insertion order — a report that reorders is not diffable."""
        return json.dumps(
            {
                "csv_name": self.csv_name,
                "header": self.header,
                "rows_in": self.rows_in,
                "csv_out": self.csv_out,
                "alterations": [asdict(a) for a in self.alterations],
                "findings": [asdict(f) for f in self.findings],
                "options": [asdict(o) for o in self.options],
                "requirements": self.requirements,
            },
            indent=2,
        )

    def __str__(self) -> str:
        return (
            f"{self.csv_name}: {self.rows_in} row(s), {len(self.applied)} normalized, "
            f"{len(self.advisory)} advisory, {len(self.findings)} finding(s)"
        )


def describe_table(csv_name: str) -> dict[str, Any]:
    """Everything a tool needs to help someone fill one table kind, without any input from them.

    Columns with their types, requiredness and allowed values; the alternative identity groups; the
    natural key two rows are the same row by. All generated from the live models.

    **Whatever the whole-schema `authoring_reference()` says about a column, this says too** — this
    is the command an author filling *one* table runs, so a fact that reaches only the other surface
    reaches the reader least likely to be reading it. Two were missing, both because this column dict
    is assembled here rather than shared with the other surface, and a guard compared only
    `field_category`. The **per-member prose** a closed vocabulary can carry: `source_element`'s eight
    members printed with no way to tell which of them counts the reference element, which is the one
    question the vocabulary was added to answer (D1-4). And **`category`**: `required` alone is
    pydantic's two-way answer, false for `MeasureBinRow.measure_kind` and `unresolved`, which an
    author must still write out carrying their defaults. `required` stays beside it — a published key
    is not removed, and it is insufficient rather than wrong."""
    model = model_for(csv_name)
    vocabularies = field_vocabularies(model)
    requirements = authoring_requirements(csv_name)
    return {
        "csv": csv_name,
        "model": model.__name__,
        "columns": [
            {
                "name": name,
                "required": model.model_fields[name].is_required(),
                "category": field_category(model, name),
                "description": model.model_fields[name].description,
                **(
                    {
                        "vocabulary": vocabularies[name]["name"],
                        "options": vocabularies[name]["options"],
                        "closed": vocabularies[name]["closed"],
                        **(
                            {"notes": dict(vocabularies[name]["notes"])}
                            if vocabularies[name].get("notes")
                            else {}
                        ),
                    }
                    if name in vocabularies
                    else {}
                ),
                "redundancy_bearing": REDUNDANCY_BEARING.get(name),
            }
            for name in authored_field_names(model)
        ],
        "requirements": requirements,
    }


def field_options(csv_name: str) -> list[FieldOptions]:
    """The pick-lists for one table kind — the "valid options to select from" half of authoring."""
    return [
        FieldOptions(
            column=column,
            vocabulary=marker["name"],
            options=marker["options"],
            closed=marker["closed"],
            notes=dict(marker["notes"]) if marker.get("notes") else None,
        )
        for column, marker in field_vocabularies(model_for(csv_name)).items()
    ]


def inspect_rows(csv_name: str, csv_text: str) -> HintReport:
    """Inspect authored CSV text: validate each cell, preview the model's own normalizations, and
    report duplicate keys and bin incoherence. Pure — nothing on disk is read or written.

    `csv_text` may carry a header or not; without one the model's authored column order is assumed,
    which is what a caller pasting a single row from a template has.
    """
    model = model_for(csv_name)
    fieldnames = authored_field_names(model)
    rows, header, header_lines, ragged = _parse(csv_text, fieldnames)

    report = HintReport(
        csv_name=csv_name,
        header=header,
        rows_in=len(rows),
        csv_out=[],
        options=field_options(csv_name),
        requirements=authoring_requirements(csv_name),
    )

    # Reported BEFORE the per-row validation whose message it explains: a shifted row's type error
    # names the column to the right of the real mistake, so the author has to see the field count
    # first or they go and "fix" a cell that was correct.
    _report_ragged(ragged, len(header), report)

    emitted: list[dict[str, str]] = []
    parsed: list[BaseModel | None] = []
    for index, raw in enumerate(rows):
        cells = dict(raw)
        # The stub columns are handed to `_validate_row` rather than left implicit in the call order:
        # both layers see the same cell, and this is what lets the second one stay quiet about it.
        stubbed = _check_placeholders(index, cells, report)
        instance = _validate_row(index, cells, model, report, stubbed=stubbed)
        parsed.append(instance)
        if instance is not None:
            cells = _apply_normalizations(index, cells, instance, model, header, report)
        emitted.append(cells)

    _flag_advisory_columns(emitted, model, report)
    _check_duplicate_keys(parsed, report)
    _check_bins(parsed, model, report)

    # Every row-scoped finding gains its file line number in one place, rather than each producer
    # remembering to pass it — the header offset is known here and nowhere else.
    report.findings = [
        f if f.row is None else replace(f, line=f.row + header_lines + 1) for f in report.findings
    ]
    report.csv_out = [",".join(header)] + [_render_line(cells, header) for cells in emitted]
    return report


def _report_ragged(ragged: list[tuple[int, int]], declared: int, report: HintReport) -> None:
    """Say that a row's field count differs from the header's, and name the likely cause.

    An **error** for a surplus field and a **warning** for a shortfall, which is the asymmetry of what
    each does to the data: a surplus shifts every later column and *discards* the overflow, so the row
    now says things the author did not write, while a shortfall only pads with empties — wrong, but
    recoverable and often just a trailing comma. Both name both counts, because "8 where 7 were
    declared" is the fact that makes the type error one column over make sense."""
    for index, found in ragged:
        surplus = found > declared
        report.findings.append(
            Finding(
                index,
                None,
                "error" if surplus else "warning",
                f"{found} field(s) where the header declares {declared}"
                + (
                    " — every column from the extra one onward is shifted and the overflow is dropped, "
                    "so a type error may be reported against a cell you wrote correctly. The usual "
                    "cause is an unquoted comma in a free-text column (conclusion, phenotype); quote "
                    'the value ("a, b") or remove the comma.'
                    if surplus
                    else " — the missing cells are read as empty, which is indistinguishable from "
                    "cells you meant to leave blank. Check for a dropped or trailing comma."
                ),
            )
        )


def _parse(csv_text: str, fieldnames: list[str]) -> tuple[list[dict[str, str]], list[str], int, list[tuple[int, int]]]:
    """Split CSV text into rows, tolerating a missing header line.

    Returns `(rows, header, header_lines, ragged)`. `header_lines` is 1 when a header was consumed and
    0 otherwise, which is what turns a row index into a file line number. `ragged` is
    `[(row_index, field_count)]` for every row whose field count differs from the header's — the
    counts are collected here, where they are known, and turned into findings by `inspect_rows`.

    **A ragged row used to be absorbed in silence, and the silence was the defect** (S18). The
    comprehension below pads a short row with `""` — indistinguishable from cells the author left
    empty — and for a long row it drops everything past `len(header)` while shifting each column from
    the offending one onward. The usual cause is an unquoted comma in prose, so the shift lands in a
    free-text column and the *type* error surfaces one column to the right, against a cell the author
    wrote correctly. Padding and truncating are kept (a hint must still describe a broken file rather
    than refuse it), but the mismatch is now reported."""
    lines = [line for line in csv_text.splitlines() if line.strip()]
    if not lines:
        return [], fieldnames, 0, []
    first = next(csv.reader([lines[0]]))
    has_header = set(first) <= set(fieldnames) and len(set(first)) == len(first)
    header = first if has_header else fieldnames
    body = lines[1:] if has_header else lines
    split = [next(csv.reader([line])) for line in body]
    rows = [
        {name: (values[i] if i < len(values) else "") for i, name in enumerate(header)}
        for values in split
    ]
    ragged = [
        (index, len(values)) for index, values in enumerate(split) if len(values) != len(header)
    ]
    return rows, header, (1 if has_header else 0), ragged


def _check_placeholders(index: int, cells: dict[str, str], report: HintReport) -> list[str]:
    """One finding per cell still carrying the placeholder, and the columns it named.

    The return value is consumed by `_validate_row`: the model's own `mode="before"` guard sees the
    same cells and raises a row-level `ValueError` listing every one of them, so without it a stub
    is reported twice — once here with its column, once there without."""
    stubbed = [column for column, value in cells.items() if value.strip() == TEMPLATE_PLACEHOLDER]
    for column in stubbed:
        report.findings.append(
            Finding(index, column, "error", f"{column} is still a template stub — replace it")
        )
    return stubbed


def _validate_row(
    index: int,
    cells: dict[str, str],
    model: type[BaseModel],
    report: HintReport,
    *,
    stubbed: list[str],
) -> BaseModel | None:
    """Build the row, turning each validation error into a per-cell finding rather than an exception.

    **A stub cell is reported once, by the check that knows which column it is** (D4-2). Two other
    layers see the same cell and say the same thing less usefully, and both are dropped here:

    * an authored model guards its raw input with `vocab.reject_template_placeholders`, which raises
      one row-level error naming every placeholder path. That is precisely what makes a generated
      stub unable to compile, which is its job; as a *hint* it is a strictly weaker restatement,
      carrying no `loc`, hence a `Finding` with no `column`, hence no `line 2 [genotype]` in the CLI.
      A freshly drafted 109-row panel printed two lines per defect.
    * a table whose model is not an `AuthoredModel` — `sources.csv`/`licensing.csv` — carries no such
      guard, so the placeholder reaches the field validators and comes back as a type or vocabulary
      error quoting the stub token (`layer must be one of [...], got: '<<REPLACE>>'`). Same defect
      through a different door, and the same answer: the cell is unfilled, and that is the whole of
      what an author can act on. Once it is filled with something wrong, the error returns.

    The suppression is narrow in both directions. Row-level errors key on `stubbed` being non-empty
    rather than on the message alone, so a placeholder error nothing reported per cell would still be
    shown — the aim is no duplicates, not fewer findings — and that guard is exact rather than
    approximate here: both layers apply the identical `strip() == TEMPLATE_PLACEHOLDER` test to the
    same flat dict of cells (the `!= ""` filter below cannot drop a stub, which is never empty), so a
    non-empty `stubbed` means every path the model's message lists was already reported with its
    column. Located errors are dropped only on a column that *is* a stub, which is `draft.PartialRow`'s
    rule for the same situation. And the row is still validated rather than skipped: the raw guard
    runs first and aborts the rest today, but that is a fact about the current validator order, not a
    decision — if it ever changes, the errors it stops masking surface here rather than being
    swallowed by a shortcut."""
    payload = {k: v for k, v in cells.items() if v != ""}
    try:
        return model.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError
        for error in getattr(exc, "errors", list)():
            location = error.get("loc") or (None,)
            column = location[0] if isinstance(location[0], str) else None
            message = str(error.get("msg", "")).removeprefix("Value error, ")
            if column is not None and column in stubbed:
                continue
            if column is None and stubbed and TEMPLATE_PLACEHOLDER in message:
                continue
            report.findings.append(Finding(index, column, "error", message))
        if not getattr(exc, "errors", None):
            report.findings.append(Finding(index, None, "error", str(exc)))
        return None


def _apply_normalizations(
    index: int,
    cells: dict[str, str],
    instance: BaseModel,
    model: type[BaseModel],
    header: list[str],
    report: HintReport,
) -> dict[str, str]:
    """Render the validated row back and record every cell the model itself rewrote.

    This is the one class that *is* applied, because it has already happened: the model rewrote the
    value on load whether or not anyone was told. `DiplotypeRow` reorders a haplotype pair and
    `PharmVariantRow` recanonicalizes a genotype; surfacing that before the author is surprised by it
    adds no external information and spends no redundancy."""
    list_fields = _list_fields(model)
    dumped = instance.model_dump()
    updated = dict(cells)
    for column in header:
        if column not in model.model_fields:
            continue
        # `dumped` for the model's own field, else the attribute — a stamped positional column
        # (`variant_key`/`authored_ident`/`alts`, RM43) is `exclude=True` and so absent from
        # `model_dump()`, and falling back to `None` there would report the compiler as having
        # *blanked* a cell the author wrote when what it did was overwrite it with the stamped value.
        value = dumped[column] if column in dumped else getattr(instance, column, None)
        rendered = _list_cell(value) if column in list_fields else _scalar_cell(value)
        before = cells.get(column, "")
        if before.strip() == "" or rendered == before:
            continue
        updated[column] = rendered
        report.alterations.append(
            Alteration(
                row=index,
                column=column,
                before=before,
                after=rendered,
                kind="normalized",
                applied=True,
                note="the model applies this on load; shown so it is not a surprise",
            )
        )
    return updated


def _flag_advisory_columns(
    rows: list[dict[str, str]], model: type[BaseModel], report: HintReport
) -> None:
    """Explain, once per column, which cells are deliberately left to the author.

    Keyed on the *model's* columns rather than the ones the input happens to carry: an rsid-only row
    has no `chrom` column at all, and that is exactly the case worth explaining — a lookup could
    supply the coordinate and deliberately does not. Reported with `row=None` because the reason is a
    property of the column; repeating it per row would bury the real findings under boilerplate."""
    authored = set(authored_field_names(model))
    for column, checker in REDUNDANCY_BEARING.items():
        if column not in authored:
            continue
        if any(row.get(column, "").strip() for row in rows):
            continue  # the author filled it somewhere; nothing is being withheld
        report.findings.append(
            Finding(
                None,
                column,
                "info",
                f"{column} is left to the author on purpose: {checker} compares it against a "
                f"source, and filling it from that same source would make the check vacuous",
            )
        )


def _check_duplicate_keys(parsed: list[BaseModel | None], report: HintReport) -> None:
    """Two rows the compiler would reject as the same row. Uses the compiler's own key."""
    seen: dict[tuple, int] = {}
    for index, instance in enumerate(parsed):
        if instance is None:
            continue
        key = natural_key(instance)
        if key is None:
            continue
        if key in seen:
            report.findings.append(
                Finding(index, None, "error", f"duplicate of row {seen[key]} — same key {key}")
            )
            continue
        seen[key] = index


def _check_bins(
    parsed: list[BaseModel | None], model: type[BaseModel], report: HintReport
) -> None:
    """Overlap, coverage gaps and the tiling notices, via the schema tier's own `validate_bins`.

    An overlap raises there and a gap is returned as a warning, so both are caught: the highest-value
    hint for the binning family, and it needs nothing but the rows in hand. Since 0.6 that function
    also reports how the group's tiling was decided — inferred from a fractional value, or declared
    `quantised` beside one — and conflicting declarations raise like an overlap does.

    The deprecation notice rides here too, attached to its column, because this is the surface an
    author reaches for while writing the file rather than after (`deprecation_warnings` emits it once
    per table, not once per row)."""
    if not issubclass(model, MeasureBinRow):
        return
    rows = [r for r in parsed if r is not None]
    if not rows:
        return
    try:
        for warning in validate_bins(rows):
            report.findings.append(Finding(None, None, "warning", warning))
    except ValueError as exc:
        report.findings.append(Finding(None, None, "error", str(exc)))
    for warning in deprecation_warnings(rows):
        report.findings.append(Finding(None, "modifier_cn", "warning", warning))
    if not any(getattr(r, "unresolved", False) for r in rows):
        report.findings.append(
            Finding(
                None,
                "unresolved",
                "warning",
                "no unresolved sentinel row: a consumer with no measurement would match nothing. "
                "The contract is that a missing measurement selects this row, never the lowest bin",
            )
        )


def _render_line(cells: dict[str, str], header: list[str]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow([cells.get(name, "") for name in header])
    return buf.getvalue()
