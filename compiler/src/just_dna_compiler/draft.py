"""Drafting — append validated rows into an authored CSV without ever clobbering one (0.5).

The mechanism half of the drafting story. A source that publishes a table (CPIC's star-allele
definitions, a ClinVar gene slice) can hand its rows to `append_rows` and they land in the authored
CSV a human then owns; the fetching half lives in `just-dna-enricher`, which is the only tier allowed
to go to the network. This module is pure: rows in, CSV appended, report out.

**It lives in the compiler because the compiler already does this.** `reverse_module` writes authored
CSVs from parquet, and `_TABLE_DUPE_KEYS` already defines what makes two rows the same row. Building a
second, parallel notion of either in the enricher is how they drift.

**Append-only, at row granularity.** A file-level "refuse if it exists" rule self-defuses after the
first gene and makes a multi-gene module unbuildable, so the granularity is the row:

* a row whose natural key is not present is **appended**;
* a row whose key IS present is **never rewritten** — it is reported as `already_present`, or as
  `differs` when the incoming cells disagree with the authored ones, and the run continues.

That is the line between this and the enricher-co-authoring idea the roadmap parks: appending rows a
source publishes leaves `content_signature` a function of the authored bytes exactly as before, while
*mutating* a cell a human wrote would make the content identity depend on a network fetch. Drift on
rows that already exist is the cross-check passes' job to report, not this module's to fix.

**Existing cells are never touched.** New rows are appended to the open file; the table is rewritten
whole only when the header must grow or when placement is delegated, and a rewrite re-reads existing
rows **as text** (`_render_existing`), so it can never reformat `1.0` into `1`. Rows gain an empty
cell in a new column — value-neutral, and `content_signature` ignores unset optional columns by
construction.

**Where a row lands: the end by default, or its group when asked** (`group_by`, 0.5.1). Appending at
the end makes a re-drafted file chronological rather than logical, so a gene's rows scatter as a
module grows; delegated insertion puts a row after the last member of its block instead. The tool
chooses *where*, never *what* — there is deliberately no `at=N`, because an index is the caller
deciding and buys nothing a text editor does not. Moving a row's line number is safe: a pure reorder
moves `artifact.digest` but leaves `content_signature` untouched (it is order-independent), the
round-trip fixed point still holds, and duplicate keys are rejected so order can disambiguate
nothing. `DraftReport.shifted` names every row whose line moved.
"""

import csv
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from just_dna_format.base import authored_field_names
from just_dna_format.base import field_category as base_field_category
from just_dna_format.binning import MeasureBinRow
from just_dna_format.layout import (
    SIDECAR_SPELLINGS,
    SOURCES_CSV,
    SidecarCollision,
    resolve_sidecar,
    sidecar_spellings,
)
from just_dna_format.sources import SourceRow
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from pydantic import BaseModel

from just_dna_compiler.compiler import (
    _TABLE_DUPE_KEYS,
    _TABLE_KINDS,
    _list_cell,
    _list_fields,
    _load_csv_rows,
    _scalar_cell,
)

#: Every authored CSV a draft can target: the SNP core, the optional table kinds, and the one fact
#: sidecar a human writes.
#:
#: `sources.csv` is the exception among the fact tables and it earns the exception (S21): the other
#: three are produced by an enricher pass, so an author never starts one by hand, while this one the
#: schema explicitly tells them to hand-write and the compile licence gate reads it and nothing else.
#: Excluding it meant `blank_template("sources.csv")` answered *"is not an authored table of this
#: format"* — a false claim, and the surface that says it is the one an author reaches for instead of
#: reading our source. Which is what the consumer who reported it ended up doing.
#: Both spellings of the licence table are keys (RM51). The map is keyed on the *filename* a caller
#: names, so leaving the new one out would make `blank_template("licensing.csv")` deny that a table the
#: compiler reads is a table of this format — the same false claim excluding `sources.csv` used to make.
DRAFTABLE: dict[str, type[BaseModel]] = {
    "variants.csv": VariantRow,
    "studies.csv": StudyRow,
    **{csv_name: model for csv_name, _, model in _TABLE_KINDS},
    **dict.fromkeys(sidecar_spellings(SOURCES_CSV), SourceRow),
}

# The SNP core's natural keys, the two `_TABLE_DUPE_KEYS` does not carry because the compiler checks
# them inline instead (`_cross_validate_variants` / `_cross_validate_studies`). Same keys, so a draft
# can never append a row the compiler would then reject as a duplicate.
_CORE_DUPE_KEYS: dict[type[BaseModel], Callable[[Any], tuple]] = {
    VariantRow: lambda r: (r.variant_key, r.genotype),
    StudyRow: lambda r: (r.variant_key, r.pmid),
    # `sources.csv`'s key is `(source, layer)` — the same one `licensing.merge_sources_csv` merges on,
    # borrowed for the same reason the two above are: a draft must not append a row the other writer
    # would treat as already present. One source legitimately appears at two layers.
    SourceRow: lambda r: (r.source, r.layer),
}


class DraftError(RuntimeError):
    """A draft could not be attempted — an unknown table kind, or an unreadable existing file."""


@dataclass
class RowOutcome:
    """What happened to one incoming row."""

    key: tuple | None
    status: str  #: added | already_present | differs | appended_unkeyed | invalid
    differences: dict[str, tuple[Any, Any]] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.status == "differs":
            shown = ", ".join(
                f"{name}: authored {authored!r} vs source {incoming!r}"
                for name, (authored, incoming) in sorted(self.differences.items())
            )
            return f"{self.key}: differs — {shown} (left unchanged)"
        return f"{self.key}: {self.status}"


@dataclass
class DraftReport:
    csv_name: str
    path: Path
    outcomes: list[RowOutcome]
    written: bool
    header_extended: list[str] = field(default_factory=list)
    #: Authored indices of rows whose *line number* moved because a new row was placed into their
    #: group. Their cells are byte-identical; only the offset changed. Empty for a plain append.
    shifted: list[int] = field(default_factory=list)

    @property
    def added(self) -> list[RowOutcome]:
        return [o for o in self.outcomes if o.status in {"added", "appended_unkeyed"}]

    @property
    def already_present(self) -> list[RowOutcome]:
        return [o for o in self.outcomes if o.status == "already_present"]

    @property
    def differs(self) -> list[RowOutcome]:
        return [o for o in self.outcomes if o.status == "differs"]

    @property
    def invalid(self) -> list[RowOutcome]:
        return [o for o in self.outcomes if o.status == "invalid"]

    def __str__(self) -> str:
        placed = f", {len(self.shifted)} existing row(s) shifted" if self.shifted else ""
        return (
            f"{self.csv_name}: {len(self.added)} added, {len(self.already_present)} already present, "
            f"{len(self.differs)} differing (left unchanged){placed}"
        )


def model_for(csv_name: str) -> type[BaseModel]:
    """The row model for an authored CSV name, or `DraftError` for one this format does not define."""
    model = DRAFTABLE.get(csv_name)
    if model is None:
        raise DraftError(
            f"{csv_name!r} is not an authored table of this format. Known: {sorted(DRAFTABLE)}"
        )
    return model


def _draft_path(spec_dir: Path, csv_name: str) -> Path:
    """Where a draft should be written: the copy the module already carries, else the name asked for.

    **Write to the file you read.** Drafting needed this rule the moment a table gained a second
    accepted spelling (RM51): `DRAFTABLE` takes both names as keys, so a caller may legitimately ask
    for `licensing.csv` on a module carrying `sources.csv`, and the literal `spec_dir / csv_name` join
    then left **two** copies behind — the collision `compile_module` refuses, arrived at by following
    the documented surface rather than by misusing it. A `derived/` copy is found for the same reason
    (RM49), so a split module gets its draft appended where the compiler will read it.

    **Deliberately narrower than `layout.sidecar_write_path`.** That one creates the *preferred*
    spelling when a module carries nothing, which is right for an enricher pass writing a machine
    table under a fixed name. Here the name is the caller's own argument, so an absent file is created
    under the name they asked for: silently redirecting `draft sources.csv` to another filename would
    answer a different question than the one put. Only the collision is repaired.

    Tables with one spelling — every table kind, `variants.csv`, `studies.csv` — take the fall-through
    and behave exactly as before.
    """
    spec_dir = Path(spec_dir)
    for canonical, spellings in SIDECAR_SPELLINGS.items():
        if csv_name not in spellings:
            continue
        try:
            existing = resolve_sidecar(spec_dir, canonical)
        except SidecarCollision as exc:
            # Appending to a module that already carries two copies would make a third claim about
            # the same table. Refuse as this surface's own error, the way every reader refuses.
            raise DraftError(str(exc)) from exc
        if existing is not None:
            return existing
        break
    return spec_dir / csv_name


def natural_key(row: BaseModel) -> tuple | None:
    """The identity that decides whether two rows are the same row, or `None` when the kind has none.

    Reuses the compiler's own `_TABLE_DUPE_KEYS` so an append can never produce a row the compiler
    would then reject as a duplicate. The binning kinds return `None` on purpose: their duplicate rule
    is *overlap*, not equality (`validate_bins`), and two bins can conflict while sharing no key — so
    they are appended and the overlap is caught at compile, where it can actually be judged."""
    for table, key_of in (*_CORE_DUPE_KEYS.items(), *_TABLE_DUPE_KEYS.items()):
        if isinstance(row, table):
            return key_of(row)
    return None


def blank_template(csv_name: str) -> str:
    """A header-only CSV for one table kind, with columns in the model's own field order.

    Generated from the model, never a hand-kept list — the same drift-proof route
    `reference.authoring_reference()` takes. Starting a new table currently means copying a header out
    of the docs, which is exactly the thing that goes stale.

    Compiler-managed columns are left out (`base.authored_field_names`): `variant_key` and
    `authored_ident` are stamped at load and never written back by `reverse_module`, so offering them
    would invite an author to fill a column the compiler overwrites — and `authored_ident` is a list,
    so a rendered cell would not even reload."""
    return ",".join(authored_field_names(model_for(csv_name))) + "\n"


def required_fields(csv_name: str) -> list[str]:
    """The columns an author must fill for this kind — everything without a default.

    Field-local only, and deliberately unchanged (it is shipped API). It does **not** answer "what
    must I fill to get a valid row": see `authoring_requirements`, which adds the columns that have a
    default but reject an empty cell, and the alternative identity groups a model validator enforces."""
    model = model_for(csv_name)
    authored = set(authored_field_names(model))
    return [
        name for name, f in model.model_fields.items() if f.is_required() and name in authored
    ]


#: Re-bound from `just_dna_format.base`, where the three-way split now lives so that this module and
#: `reference.authoring_reference` cannot answer the same question differently — they did, and the
#: reference was the one still emitting pydantic's two-way `is_required()`. Kept as a name here
#: because it is part of this module's documented surface.
field_category = base_field_category


def authoring_requirements(csv_name: str) -> dict[str, Any]:
    """What an author actually has to supply for one table kind, machine-readably.

    Three parts, because requiredness has three shapes here and only the first is visible to
    pydantic's `is_required()`:

    * `always`   — columns with no default;
    * `any_of`   — alternative identity groups, any ONE of which satisfies the row (`rsid`, or
      `chrom`+`start`). Enforced by a model validator, so no per-field flag can express it;
    * `defaulted` — `{column: rendered default}` for columns that have a default but reject an empty
      cell. A template writes these out; see `field_category`.
    """
    model = model_for(csv_name)
    categories = {name: field_category(model, name) for name in authored_field_names(model)}
    return {
        "csv": csv_name,
        "always": [n for n, c in categories.items() if c == "required"],
        "any_of": [sorted(group) for group in getattr(model, "REQUIRED_ANY_OF", ())],
        "defaulted": {
            n: _scalar_cell(model.model_fields[n].get_default(call_default_factory=True))
            for n, c in categories.items()
            if c == "defaulted"
        },
        "optional": [n for n, c in categories.items() if c == "optional"],
    }


def stub_template(csv_name: str, *, rows: int = 1) -> str:
    """A header plus `rows` stub rows: the sentinel where a human must decide, defaults written out.

    The point of the sentinel over a blank cell is that an unreplaced stub **cannot compile** —
    `vocab.reject_template_placeholders` refuses it by name and row, in both modes. A blank required
    cell would also fail, but a blank *optional* one would silently become a real row asserting
    nothing, and the binning kinds' `unresolved` sentinel could not be used for this at all: it is
    real data designed to compile.

    For a binning kind the mandatory `unresolved` companion row is emitted too, because a binning
    table without one is incomplete by contract and the author would otherwise meet that rule as a
    compile error about a row they never wrote."""
    model = model_for(csv_name)
    fieldnames = authored_field_names(model)
    requirements = authoring_requirements(csv_name)
    # Only the FIRST identity group, not the union: the groups are alternatives, so stubbing all of
    # them would tell an author to supply an rsid *and* a coordinate. First is the declaration order,
    # which puts the cheapest identity (`rsid`) in front.
    identity = list(requirements["any_of"][0]) if requirements["any_of"] else []
    stubbed = set(requirements["always"]) | set(identity)
    defaults = requirements["defaulted"]

    def cell(name: str) -> str:
        if name in defaults:
            return defaults[name]
        return TEMPLATE_PLACEHOLDER if name in stubbed else ""

    lines = [",".join(fieldnames)]
    lines.extend(",".join(cell(f) for f in fieldnames) for _ in range(rows))
    if issubclass(model, MeasureBinRow):
        lines.append(",".join(_unresolved_cell(model, f, defaults) for f in fieldnames))
    return "\n".join(lines) + "\n"


def _unresolved_cell(model: type[BaseModel], name: str, defaults: dict[str, str]) -> str:
    """One cell of the mandatory `unresolved` companion row for a binning kind.

    It carries no bounds (`_validate_range` forbids them on the sentinel) and only `conclusion` is
    left for the human — the row's whole content is "what to say when nothing was measured"."""
    if name == "unresolved":
        return "true"
    if name in ("measure_min", "measure_max"):
        return ""
    if name in defaults:
        return defaults[name]
    return TEMPLATE_PLACEHOLDER if model.model_fields[name].is_required() else ""


def _authored_dump(row: BaseModel) -> dict[str, Any]:
    """`model_dump()` restricted to the columns a human authors.

    Compiler-managed fields are dropped here rather than at each call site, so a drafted cell, a
    widened header and a difference report all agree on what the authored surface is."""
    dumped = row.model_dump()
    return {name: dumped.get(name) for name in authored_field_names(type(row))}


def _render(row: BaseModel, fieldnames: list[str], list_fields: set[str]) -> dict[str, str]:
    # `.get` (not `[]`): a pre-existing file may carry a compiler-managed column, and a new row leaves
    # it empty rather than stamping a value the compiler re-derives anyway.
    dumped = _authored_dump(row)
    return {
        name: (_list_cell(dumped.get(name)) if name in list_fields else _scalar_cell(dumped.get(name)))
        for name in fieldnames
    }


def _compare(authored: BaseModel, incoming: BaseModel) -> dict[str, tuple[Any, Any]]:
    """Which set cells the source disagrees with the author about.

    Only fields the *source* actually set are compared: a scaffold that fills three of twelve columns
    is not claiming the other nine are empty, so treating its `None`s as contradictions would report a
    disagreement on every hand-annotated row. An empty list counts as unset for the same reason.
    Compiler-managed columns are out of scope entirely — `authored_ident` differs whenever the source
    names a variant by fewer identity columns than the author did, which is not a disagreement about
    the row's content."""
    a, b = _authored_dump(authored), _authored_dump(incoming)
    return {
        name: (a.get(name), value)
        for name, value in b.items()
        if value is not None and value != [] and a.get(name) != value
    }


def append_rows(
    spec_dir: Path,
    csv_name: str,
    rows: list[BaseModel],
    *,
    group_by: Sequence[str] = (),
    dry_run: bool = False,
) -> DraftReport:
    """Append `rows` to `spec_dir/csv_name`, skipping any whose natural key is already there.

    Creates the file when absent. Returns a `DraftReport` describing every incoming row, so a caller
    can show what a run would do (`dry_run=True` writes nothing and reports the same thing).

    `group_by` turns the append into a **delegated insertion**: each new row lands after the last
    existing row sharing those columns (its gene, its haplotype) instead of at the end of the file.
    The tool picks the position; the caller never supplies an index. Existing cells are still never
    rewritten — only their line number can move, and `DraftReport.shifted` names every row it did.
    """
    spec_dir = Path(spec_dir)
    path = _draft_path(spec_dir, csv_name)
    model = model_for(csv_name)

    existing_rows: list[BaseModel] = []
    existing_header: list[str] = []
    # A zero-byte file (a bare `touch`) is treated as absent rather than as an invalid table: it has
    # no header to key against and no rows to preserve, so refusing it would only mean the author has
    # to delete a file that says nothing.
    if path.exists() and path.stat().st_size > 0:
        existing_rows, errors, _ = _load_csv_rows(path, model, csv_name)
        if errors:
            raise DraftError(
                f"existing {csv_name} does not validate, so a draft cannot be keyed against it: "
                f"{errors[0]}"
            )
        with open(path, encoding="utf-8", newline="") as handle:
            existing_header = next(csv.reader(handle), [])

    by_key: dict[tuple, BaseModel] = {}
    for row in existing_rows:
        key = natural_key(row)
        if key is not None:
            by_key.setdefault(key, row)

    outcomes: list[RowOutcome] = []
    to_write: list[BaseModel] = []
    for row in rows:
        key = natural_key(row)
        if key is None:
            outcomes.append(RowOutcome(key=None, status="appended_unkeyed"))
            to_write.append(row)
            continue
        authored = by_key.get(key)
        if authored is None:
            outcomes.append(RowOutcome(key=key, status="added"))
            by_key[key] = row  # so a duplicate inside `rows` itself is caught too
            to_write.append(row)
            continue
        differences = _compare(authored, row)
        outcomes.append(
            RowOutcome(
                key=key,
                status="differs" if differences else "already_present",
                differences=differences,
            )
        )

    # Which columns the file needs: whatever it already has, plus every column the new rows actually
    # set. A column no incoming row fills is not added — a scaffold should not widen a hand-authored
    # table with empties it has nothing to put in.
    field_order = authored_field_names(model)
    filled = {
        name
        for row in to_write
        for name, value in _authored_dump(row).items()
        if value is not None and value != []
    }
    header = existing_header or [f for f in field_order if f in filled or f in set(required_fields(csv_name))]
    extended = [f for f in field_order if f in filled and f not in header]
    fieldnames = header + extended

    if dry_run or not to_write:
        return DraftReport(csv_name, path, outcomes, written=False, header_extended=extended)

    list_fields = _list_fields(model)
    rendered = [_render(row, fieldnames, list_fields) for row in to_write]
    shifted: list[int] = []
    if extended or not existing_header or group_by:
        # The table is written whole when the header has to grow, when there is none yet (the file is
        # absent, or present but empty — a bare `touch`), or when placement is delegated and a row may
        # land mid-file. Existing rows keep their **cells**: `_render_existing` re-reads them as text,
        # so a rewrite can never reformat `1.0` to `1`; only their line number can change.
        previous = _render_existing(path, fieldnames) if existing_header else []
        merged, shifted = place_rows(previous, rendered, group_by)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(merged)
    else:
        # The common case: the header already fits, so existing bytes are literally untouched — bar a
        # final newline the file may be missing. A hand-authored CSV often has none (plenty of editors
        # do not add one), and appending straight onto it would glue the first new row to the author's
        # last one, corrupting a row this module promises never to touch.
        with open(path, "a", encoding="utf-8", newline="") as handle:
            if not _ends_with_newline(path):
                handle.write(csv.excel.lineterminator)
            csv.DictWriter(handle, fieldnames=fieldnames).writerows(rendered)

    return DraftReport(
        csv_name, path, outcomes, written=True, header_extended=extended, shifted=shifted
    )


def _ends_with_newline(path: Path) -> bool:
    """Does the file already end in a line break? (An empty file counts as terminated.)"""
    with open(path, "rb") as handle:
        if handle.seek(0, 2) == 0:
            return True
        handle.seek(-1, 2)
        return handle.read(1) in (b"\n", b"\r")


# ── Partial rows (0.5.1) ────────────────────────────────────────────────────────────────────────
# A source that publishes *most* of a row. ClinVar is the case that forced it: `VariantRow.genotype`
# is required and ClinVar publishes **alleles, not genotypes** — whether a pathogenic allele is
# informative het or hom-alt is zygosity interpretation (dominant vs recessive vs carrier) that the
# source cannot supply and a provider must not invent. So the provider writes what is published and
# leaves the rest carrying `TEMPLATE_PLACEHOLDER`, which no mode compiles.


@dataclass
class PartialRow:
    """Cells a source published, plus the columns only a human can decide.

    `match_on` is what makes a re-draft safe. A partial row cannot be keyed the usual way — its
    natural key runs through a column that is still a placeholder — so sameness is decided on the
    columns that *are* filled. Once the human replaces the stub, a re-run matches on those same
    columns and reports `already_present` instead of appending the stub again.
    """

    model: type[BaseModel]
    cells: dict[str, Any]
    stubbed: tuple[str, ...]
    match_on: tuple[str, ...]

    def rendered(self, fieldnames: list[str], list_fields: set[str]) -> dict[str, str]:
        """The CSV cells for this row: what the source gave, the placeholder where it could not."""
        out: dict[str, str] = {}
        for name in fieldnames:
            if name in self.stubbed:
                out[name] = TEMPLATE_PLACEHOLDER
                continue
            value = self.cells.get(name)
            out[name] = _list_cell(value) if name in list_fields else _scalar_cell(value)
        return out

    def validation_errors(self) -> list[str]:
        """What is wrong with the cells the source *did* publish.

        The stubbed columns are validated by omission: the row is built without them and any error
        located on one is discarded. That avoids the alternative — a per-column table of plausible
        dummy values — which would be exactly the hand-kept list this module keeps abolishing.
        """
        payload = {
            name: value
            for name, value in self.cells.items()
            if name not in self.stubbed and value is not None and value != ""
        }
        try:
            self.model.model_validate(payload)
        except Exception as exc:  # pydantic ValidationError
            return [
                f"{(error.get('loc') or ('?',))[0]}: {error.get('msg')}"
                for error in getattr(exc, "errors", list)()
                if (error.get("loc") or ("?",))[0] not in self.stubbed
            ]
        return []


def append_partial_rows(
    spec_dir: Path,
    csv_name: str,
    partials: list[PartialRow],
    *,
    group_by: Sequence[str] = (),
    dry_run: bool = False,
) -> DraftReport:
    """Append rows a source could only partly fill, leaving the rest as stubs a human must replace.

    Same promises as `append_rows`: never rewrites a cell, never removes a row, and a row already
    covered is reported rather than duplicated. The difference is only how sameness is decided — see
    `PartialRow.match_on` — because a row whose key column is a placeholder has no usable key yet.
    """
    spec_dir = Path(spec_dir)
    path = _draft_path(spec_dir, csv_name)
    model = model_for(csv_name)
    fieldnames = authored_field_names(model)
    list_fields = _list_fields(model)

    existing_header: list[str] = []
    if path.exists() and path.stat().st_size > 0:
        with open(path, encoding="utf-8", newline="") as handle:
            existing_header = next(csv.reader(handle), [])
    previous = _render_existing(path, fieldnames or existing_header) if existing_header else []
    header = existing_header or fieldnames
    fieldnames = header

    outcomes: list[RowOutcome] = []
    to_write: list[dict[str, str]] = []
    covered = [
        tuple((row.get(column) or "").strip() for column in partials[0].match_on)
        for row in previous
    ] if partials else []

    for partial in partials:
        errors = partial.validation_errors()
        signature = tuple(
            str(partial.cells.get(column) or "").strip() for column in partial.match_on
        )
        if errors:
            outcomes.append(RowOutcome(signature, "invalid", {"errors": (None, "; ".join(errors))}))
            continue
        if signature in covered:
            outcomes.append(RowOutcome(signature, "already_present"))
            continue
        covered.append(signature)
        outcomes.append(RowOutcome(signature, "added"))
        to_write.append(partial.rendered(fieldnames, list_fields))

    if dry_run or not to_write:
        return DraftReport(csv_name, path, outcomes, written=False)

    merged, shifted = place_rows(previous, to_write, group_by)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)
    return DraftReport(csv_name, path, outcomes, written=True, shifted=shifted)


# ── Delegated placement (0.5.1) ─────────────────────────────────────────────────────────────────
# Where a new row lands. Appending at the end was the first cut and stays the default, but it makes a
# re-drafted file *chronological* rather than logical: draft a gene, come back when upstream adds an
# allele, and the new rows sit hundreds of lines from their siblings. That taxes the human half of the
# human-authorable/machine-precise duality this DSL is gated on.
#
# The tool chooses **where**, never **what** — hence "delegated": there is no `at=N`, because an index
# is the caller deciding, and an index buys nothing a text editor does not already do. A row joins the
# block that shares its group columns, or goes to the end when no such block exists.
#
# Moving an existing row's *line number* is safe, and the objection that looked strongest turns out
# not to be: a pure reorder moves `artifact.digest` but leaves `content_signature` untouched (it is
# order-independent by construction), the compile → reverse → compile fixed point still holds, and
# duplicate keys are rejected outright so order can disambiguate nothing. An author reordering rows in
# an editor is already legal and already moves the digest. The report still names every shifted row,
# because that is cheap and makes the diff legible.


def group_of(cells: dict[str, str], columns: Sequence[str]) -> tuple | None:
    """The block a row belongs to, or `None` when it declares no group (then it goes to the end)."""
    values = tuple((cells.get(column) or "").strip() for column in columns)
    return values if any(values) else None


def place_rows(
    existing: list[dict[str, str]], incoming: list[dict[str, str]], group_by: Sequence[str]
) -> tuple[list[dict[str, str]], list[int]]:
    """Merge `incoming` into `existing`, each row after the last member of its group.

    Returns the final row list and the **original indices** of existing rows whose line moved. With no
    `group_by` this is a plain append and nothing shifts. Incoming rows keep their relative order
    within a group, so a provider's own ordering survives.
    """
    if not group_by:
        return existing + incoming, []
    merged = list(existing)
    original_index = {id(row): position for position, row in enumerate(existing)}
    for row in incoming:
        group = group_of(row, group_by)
        insert_at = len(merged)
        if group is not None:
            for position in range(len(merged) - 1, -1, -1):
                if group_of(merged[position], group_by) == group:
                    insert_at = position + 1
                    break
        merged.insert(insert_at, row)
    shifted = [
        original_index[id(row)]
        for position, row in enumerate(merged)
        if id(row) in original_index and original_index[id(row)] != position
    ]
    return merged, shifted


def _render_existing(path: Path, fieldnames: list[str]) -> list[dict[str, str]]:
    """Re-read the file's own cells verbatim for a header-widening rewrite.

    Deliberately re-reads the TEXT rather than re-rendering the parsed models: a rewrite triggered by
    a new column must not also reformat cells the author wrote (`1.0` → `1`, `TRUE` → `true`), which
    would turn "add a column" into a diff across every row."""
    with open(path, encoding="utf-8", newline="") as handle:
        return [{name: row.get(name, "") for name in fieldnames} for row in csv.DictReader(handle)]
