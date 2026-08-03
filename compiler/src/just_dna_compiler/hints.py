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
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from just_dna_format.base import authored_field_names, field_vocabularies
from just_dna_format.binning import MeasureBinRow, validate_bins
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from pydantic import BaseModel

from just_dna_compiler.compiler import _list_cell, _list_fields, _scalar_cell
from just_dna_compiler.draft import authoring_requirements, model_for, natural_key

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
    }
)

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
    "clin_sig": "enricher.clinical.verify_clin_sig (authored call vs ClinVar's)",
    "function_status": "enricher.pgx.enrich_pgx (authored function vs PharmVar and CPIC)",
    "evidence_level": "enricher.clinpgx (authored level vs the ClinPGx snapshot)",
    "p_value_num": "compiler p_value ↔ p_value_num agreement",
    "acmg_sf": "enricher.acmg.check_acmg_sf (authored flag vs the ACMG SF list)",
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
    refusal: Optional[str] = None
    note: str = ""


@dataclass(frozen=True)
class Finding:
    """Something worth telling the author about a cell or a row. Never fails a build."""

    row: Optional[int]
    column: Optional[str]
    level: str
    message: str


@dataclass(frozen=True)
class FieldOptions:
    """The values a column accepts, for a picker."""

    column: str
    vocabulary: str
    options: list[str]
    closed: bool


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
    natural key two rows are the same row by. All generated from the live models."""
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
                "description": model.model_fields[name].description,
                **(
                    {
                        "vocabulary": vocabularies[name]["name"],
                        "options": vocabularies[name]["options"],
                        "closed": vocabularies[name]["closed"],
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
    rows, header = _parse(csv_text, fieldnames)

    report = HintReport(
        csv_name=csv_name,
        header=header,
        rows_in=len(rows),
        csv_out=[],
        options=field_options(csv_name),
        requirements=authoring_requirements(csv_name),
    )

    emitted: list[dict[str, str]] = []
    parsed: list[Optional[BaseModel]] = []
    for index, raw in enumerate(rows):
        cells = dict(raw)
        _check_placeholders(index, cells, report)
        instance = _validate_row(index, cells, model, csv_name, report)
        parsed.append(instance)
        if instance is not None:
            cells = _apply_normalizations(index, cells, instance, model, header, report)
        emitted.append(cells)

    _flag_advisory_columns(emitted, model, report)
    _check_duplicate_keys(parsed, report)
    _check_bins(parsed, model, report)

    report.csv_out = [",".join(header)] + [_render_line(cells, header) for cells in emitted]
    return report


def _parse(csv_text: str, fieldnames: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    """Split CSV text into rows, tolerating a missing header line."""
    lines = [line for line in csv_text.splitlines() if line.strip()]
    if not lines:
        return [], fieldnames
    first = next(csv.reader([lines[0]]))
    has_header = set(first) <= set(fieldnames) and len(set(first)) == len(first)
    header = first if has_header else fieldnames
    body = lines[1:] if has_header else lines
    rows = [
        {name: (values[i] if i < len(values) else "") for i, name in enumerate(header)}
        for values in (next(csv.reader([line])) for line in body)
    ]
    return rows, header


def _check_placeholders(index: int, cells: dict[str, str], report: HintReport) -> None:
    for column, value in cells.items():
        if value.strip() == TEMPLATE_PLACEHOLDER:
            report.findings.append(
                Finding(index, column, "error", f"{column} is still a template stub — replace it")
            )


def _validate_row(
    index: int, cells: dict[str, str], model: type[BaseModel], csv_name: str, report: HintReport
) -> Optional[BaseModel]:
    """Build the row, turning each validation error into a per-cell finding rather than an exception."""
    payload = {k: v for k, v in cells.items() if v != ""}
    try:
        return model.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError
        for error in getattr(exc, "errors", lambda: [])():
            location = error.get("loc") or (None,)
            column = location[0] if isinstance(location[0], str) else None
            report.findings.append(
                Finding(index, column, "error", str(error.get("msg", "")).removeprefix("Value error, "))
            )
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
        value = dumped.get(column)
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


def _check_duplicate_keys(parsed: list[Optional[BaseModel]], report: HintReport) -> None:
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
    parsed: list[Optional[BaseModel]], model: type[BaseModel], report: HintReport
) -> None:
    """Overlap and coverage gaps, via the schema tier's own `validate_bins`.

    An overlap raises there and a gap is returned as a warning, so both are caught: the highest-value
    hint for the binning family, and it needs nothing but the rows in hand."""
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
