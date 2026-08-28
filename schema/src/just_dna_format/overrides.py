"""`overrides.csv` — the authored overlay that lies on top of a derived table (RM124, 0.7).

Every derived sidecar this workspace writes is machine-produced and, until 0.7, also hand-editable:
the enricher merges rather than clobbers, so an existing row is authoritative and a re-run adds to it
instead of replacing it. That rule exists because these tables are human-overridable by design, and
its consequence is the single most important operational fact about a second pass — **to re-derive a
sidecar you delete it first, and deleting it discards every hand-curated row along with the stale
ones.** The 2026-08-12 cost amendment (CONSTITUTION Principle 9) names the class in its own words: a
derived table that is both machine-written and human-overridable can be edited into a state that is
not merely stale but a false claim, which wants a mechanism rather than a convention.

This is the mechanism. An overlay row records a correction *beside* the derived table rather than
inside it, so the derived files become pure build products — `derived = f(source, overlay)` — and
four things follow. Nothing is hand-edited, so re-derivation is non-destructive by construction
rather than by a wrapper being careful. A difference between a fresh row and a previous one means the
source revised, full stop. The **reason** for a correction travels with the module, which is what
makes this a record rather than a knob. And the terminal state becomes detectable: an overlay row
that no longer changes anything means the source caught up.

**The key is `(table, subject, member, field)`.** `subject` names the group a derived row belongs to
and `member` discriminates within it — `locus_index` for `resolution.csv`, `population` for
`frequencies.csv`, `assertion_id` for `gene_validity.csv`, empty for a table whose subject already
identifies exactly one row. One `member` column serves every covered table; a key that differs by
table is a rule every reader re-derives, differently.

**Empty `member` on a grouped table is group-scoped for `update`, and refused for `insert` and
`suppress`.** The asymmetry is deliberate. A group-scoped correction is a coherent thing to want —
*every locus this key resolves to has the wrong `source`* — and it is recoverable if wrong. A
group-scoped suppression silently drops every locus for one `variant_key` when the author almost
certainly meant one, and it is not recoverable by reading the result, because the rows are simply
absent. An `insert` under an empty member on a grouped table is not merely destructive but
incoherent: the row it would create has no member value to carry, so nothing could ever match it
again. The destructive and the incoherent operations refuse the wildcard; an author who genuinely
wants a whole group gone writes one row per member, and the count is small by construction.

**The dead end that asymmetry leaves, stated rather than papered over.** A derived row whose member
column is *null* cannot be named by any override, because an empty `member` cell already means "the
whole group". A `gene_validity.csv` row the source published no `assertion_id` for, and a
`clinical_assertions.csv` `not_found` row — whose null `variation_id` that model's own docstring calls
a **value**, the record that the archive was consulted and holds nothing — are both reachable by a
group-scoped `update` and unreachable by a `suppress`. A sentinel spelling for null was not invented
for it: that is a second key grammar in the column whose whole purpose is that there is only one, and
the remedy an author actually has (correct the row, or re-derive the table) costs them nothing. The
refusal message names the case rather than advising the impossible.

Dependency-light like every other module here: pydantic plus the leaf vocabularies, no polars.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator, model_validator

from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.base import AuthoredModel, vocabulary
from just_dna_format.findings import CodedWarning
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.literature import LiteratureRow
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import check_vocab


@dataclass(frozen=True)
class OverlayTarget:
    """What an overlay row means when it names one derived table.

    `subject_field` is the column whose value an overlay's `subject` carries; `member_field` is the
    within-group discriminator, or `None` for a table whose subject already identifies exactly one
    row. Both are **column names on `model`**, checked by a walked test rather than trusted — a
    registry is only as good as the guard that walks it (`@registry-completeness`).
    """

    model: type[BaseModel]
    subject_field: str
    member_field: str | None


#: The derived tables an overlay may correct, and how each one is keyed.
#:
#: **Seven, and the number is the decision** — every merge-not-clobber derived sidecar, decided
#: 2026-08-28. The proposal that carries RM124 says "the six covered derived tables" and never
#: enumerates them; the roadmap entry it inherits the number from does not either. It is a miscount,
#: pinned here rather than left to be re-counted, and `test_overrides.py` asserts an **equality**
#: against the compiler's own table tuples.
#:
#: `sources.csv` / `licensing.csv` is deliberately outside. It has its own merge path
#: (`just_dna_enricher.licensing.merge_sources_file`) and it is not a table where overriding is the
#: intended feature: it is the one derived sidecar the schema explicitly tells a human to hand-write,
#: and the only one the compile licence gate reads. An overlay over it would put a second spelling of
#: the licence position beside the first.
#:
#: The member column per table, and why each is the one it is:
#:
#: * `resolution.csv` — `locus_index`. RM115 published the merge rule as `subject`, not a uniqueness
#:   constraint: one `variant_key` legitimately resolves onto several loci and a pass replaces the
#:   group whole, so the subject names a *group of rows*.
#: * `frequencies.csv` — `population`. One variant carries a row per ancestry group.
#: * `gene_metrics.csv` — `dataset`. One gene carries a row per constraint release.
#: * `gene_validity.csv` — `assertion_id`, the source's own per-curation identity. Its key has two
#:   levels (`assertion_id` else the gene's grain), so a row the source published no id for can only
#:   be reached group-scoped, by `gene`. That is a real limit rather than an oversight: spelling the
#:   five-column grain into `subject` would be the per-table key grammar this design exists to avoid.
#: * `clinical_assertions.csv` — `variation_id`. One variant carries a row per ClinVar record.
#: * `literature.csv` / `gwas_effects.csv` — none. `pmid` and `association_id` each identify one row.
OVERRIDABLE_TABLES: dict[str, OverlayTarget] = {
    "resolution.csv": OverlayTarget(ResolutionRow, "variant_key", "locus_index"),
    "frequencies.csv": OverlayTarget(FrequencyRow, "variant_key", "population"),
    "gene_metrics.csv": OverlayTarget(GeneMetricsRow, "gene", "dataset"),
    "gene_validity.csv": OverlayTarget(GeneValidityRow, "gene", "assertion_id"),
    "clinical_assertions.csv": OverlayTarget(ClinicalAssertionRow, "variant_key", "variation_id"),
    "literature.csv": OverlayTarget(LiteratureRow, "pmid", None),
    "gwas_effects.csv": OverlayTarget(GwasEffectRow, "association_id", None),
}

#: The tables an overlay may name — a closed vocabulary (Principle 6), read off the registry so the
#: two cannot disagree.
VALID_OVERRIDE_TABLES: frozenset[str] = frozenset(OVERRIDABLE_TABLES)

#: What an overlay row does to the derived table. Closed (Principle 6).
#:
#: All three are **idempotent set operations by construction**, and that is what buys the round trip
#: rather than a `previous_value` column: `update` to a value already present is a no-op, `insert` of
#: a row already keyed `(subject, member)` is a no-op, `suppress` of a row already absent is a no-op.
#: `reverse_module` emits the post-overlay derived table plus the overlay, so the overlay applies
#: twice — and the fixed point is checked by test rather than assumed.
VALID_OVERRIDE_OPERATIONS: frozenset[str] = frozenset({"update", "insert", "suppress"})

#: Per-member prose the marker carries into `authoring_reference()` — the member *name* does not
#: carry the whole rule for any of the three.
_OPERATION_MEANINGS: dict[str, str] = {
    "update": (
        "correct one field of a derived row. The only operation that may go group-scoped: an empty "
        "`member` on a grouped table corrects every row under the subject"
    ),
    "insert": (
        "supply a row the source has no answer for, written as several overlay rows sharing "
        "(table, subject, member), one per field, so the table has one shape rather than two. The "
        "row is appended at the END of its subject's group, in the order the overlay rows appear"
    ),
    "suppress": (
        "remove a derived row the author rejects. Refuses an empty `member` on a grouped table: "
        "dropping a whole group is not recoverable by reading the result"
    ),
}


class OverrideRow(AuthoredModel):
    """One authored correction to one cell (or one row) of one derived table.

    An `AuthoredModel` and not a fact model, which is the whole distinction: a human writes this,
    every other row in the seven tables it names is machine-written. So it carries the reserved-
    namespace guard and the shared field validators, and it is inside `content_signature` — a
    correction is part of what the module says.
    """

    #: `(table, subject, member, field)` — what makes two overlay rows the same overlay row, so a
    #: duplicate is caught by the compiler's ordinary duplicate-key check rather than by silently
    #: letting the later row win.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("table", "subject", "member", "field")

    table: str = Field(
        description=(
            "The derived table this row corrects, by its authored filename (e.g. 'resolution.csv'). "
            "The overlay lies on a table the module CARRIES — it never creates one."
        ),
        json_schema_extra=vocabulary("overridable_table", VALID_OVERRIDE_TABLES),
    )
    subject: str = Field(
        description=(
            "The value identifying the group of derived rows this corrects, in the named table's own "
            "subject column: `variant_key` for resolution/frequencies/clinical_assertions, `gene` for "
            "gene_metrics/gene_validity, `pmid` for literature, `association_id` for gwas_effects."
        )
    )
    member: str | None = Field(
        default=None,
        description=(
            "The within-group discriminator, in the named table's own member column — `locus_index`, "
            "`population`, `dataset`, `assertion_id` or `variation_id`. Empty for a table whose "
            "subject already identifies one row, and empty on a grouped table means group-scoped, "
            "which only `update` accepts."
        ),
    )
    field: str | None = Field(
        default=None,
        description=(
            "The column being written, for `update` and `insert`. Empty (and required empty) for "
            "`suppress`, which names a row rather than a cell. It may not name the table's own "
            "subject or member column: re-keying a row is a suppress plus an insert, not a "
            "correction."
        ),
    )
    operation: str = Field(
        description="What this row does: update|insert|suppress",
        json_schema_extra=vocabulary(
            "override_operation", VALID_OVERRIDE_OPERATIONS, notes=_OPERATION_MEANINGS
        ),
    )
    value: str | None = Field(
        default=None,
        description=(
            "The value to write, read with the target column's own type (so '5' lands in an int "
            "column as 5). Empty on an `update` clears the cell to absent, which the target model "
            "refuses where the column is required. Required empty for `suppress`."
        ),
    )
    reason: str = Field(
        description=(
            "Why this correction was made, in a sentence. REQUIRED, and that is what makes the "
            "overlay a record rather than a knob: a derived cell that disagrees with its source is a "
            "claim, and a claim with no reason beside it is indistinguishable from a mistake."
        )
    )
    decided_by: str | None = Field(
        default=None, description="Who decided it (a curator, a panel, a tool run)"
    )
    decided_at: str | None = Field(
        default=None,
        description=(
            "When it was decided — ISO-8601, canonicalized to UTC on load. A bare date is accepted "
            "and reads as midnight UTC."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _reason_is_the_point(cls, data: object) -> object:
        """A `reason` column that is **present and blank** gets its own sentence.

        `@specific-rejection`: a generic rejection is a dead end where a specific one is a fix, and
        this is the column an author is most likely to leave empty and the one the whole table exists
        for. Runs on the RAW dict, before coercion, like every other guard on an authored model.

        **Keyed on the column being present**, which is the precise reading and not a hedge. A CSV
        row always carries every header key (`_load_csv_rows` maps a blank cell to `None` and keeps
        it), so this is exactly the authoring case. A dict with no `reason` key at all is a *missing
        column*, which pydantic's own "Field required" already names correctly — and it is also the
        shape every registry guard uses when it validates one field at a time to discover what a
        model enforces, so raising there would blind them (`@registry-completeness`).
        """
        if isinstance(data, dict) and "reason" in data and not str(data["reason"] or "").strip():
            raise ValueError(
                "an override needs a `reason`. It is required on purpose: an overlay row is a "
                "recorded judgement that a derived value is wrong, and a judgement with no reason "
                "beside it cannot be told from a mistake by anyone reading the module later — "
                "including you. One sentence naming what you checked is enough."
            )
        return data

    @field_validator("table")
    @classmethod
    def _validate_table(cls, v: str) -> str:
        return check_vocab(v, VALID_OVERRIDE_TABLES, "table")

    @field_validator("operation")
    @classmethod
    def _validate_operation(cls, v: str) -> str:
        return check_vocab(v, VALID_OVERRIDE_OPERATIONS, "operation")

    @field_validator("subject", "reason")
    @classmethod
    def _require_content(cls, v: str, info: ValidationInfo) -> str:
        text = v.strip()
        if not text:
            raise ValueError(f"{info.field_name} may not be blank")
        return text

    @field_validator("member", "field")
    @classmethod
    def _strip_key_columns(cls, v: str | None) -> str | None:
        """`member` and `field` are key columns, so they are stored the way they are compared.

        `subject` was stripped and these two were not, while `apply_overrides` groups on
        `(row.member or "").strip()` and `_TABLE_DUPE_KEYS` keys on the raw value. Two rows differing
        only by a trailing space in `member` were therefore distinct to the duplicate check and one
        group to the apply, where the second silently won — no error, no warning, and the losing
        correction simply absent from the build product.

        Not reachable from an authored file today, because `load_csv_rows` strips every cell before
        the model sees it. That is a property of one caller and not of the model, and this class is
        public: a consumer building an `OverrideRow` in memory meets the raw value.
        """
        if v is None:
            return None
        return v.strip() or None

    @field_validator("decided_at", mode="before")
    @classmethod
    def _canonical_decided_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — `normalize.normalize_utc_timestamp`.

        The value reaches `overrides.parquet` and therefore `artifact.digest`, where two spellings of
        one instant would be two identities for one overlay.
        """
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))

    @model_validator(mode="after")
    def _operation_and_key_agree(self) -> "OverrideRow":
        """The rules that need `table`, `operation`, `member` and `field` in hand at once.

        Every one of them is structural — it reads the overlay row and the registry and nothing
        else — which is what makes each **stable across the round trip**. `reverse_module` emits the
        post-overlay derived table, so on the second lap every override is a no-op by construction;
        a rule that consulted the derived rows would refuse (or warn) on a module and stay silent on
        its own round trip, and `manifest.compilation.warnings` is a published field.
        """
        target = OVERRIDABLE_TABLES[self.table]
        member = (self.member or "").strip()
        field = (self.field or "").strip()

        if target.member_field is None and member:
            raise ValueError(
                f"member is not used by {self.table}: its subject column "
                f"{target.subject_field!r} already identifies exactly one row, so there is no group "
                f"to discriminate within. Leave member empty."
            )
        if target.member_field is not None and not member and self.operation != "update":
            raise ValueError(
                f"{self.operation} on {self.table} needs a member: {self.table} keys a subject onto "
                f"a GROUP of rows ordered by {target.member_field!r}, and only `update` may go "
                f"group-scoped. A group-scoped suppress drops every row under {self.subject!r} when "
                f"one was almost certainly meant, and is not recoverable by reading the result; a "
                f"group-scoped insert would create a row with no member value to match on. Write "
                f"one row per member instead — unless the row you mean carries NO "
                f"{target.member_field!r} at all, which no override can name: correct it with a "
                f"group-scoped `update`, or re-derive the table."
            )

        if self.operation == "suppress":
            if field:
                raise ValueError(
                    f"suppress names a ROW, not a cell, so field must be empty (got {field!r}). To "
                    f"correct one column, use operation=update."
                )
            if self.value is not None and self.value.strip():
                raise ValueError(
                    f"suppress writes nothing, so value must be empty (got {self.value!r})."
                )
            return self

        if not field:
            raise ValueError(f"{self.operation} needs a field naming the column it writes.")
        if field not in target.model.model_fields:
            raise ValueError(
                f"{field!r} is not a column of {self.table}. Its columns are "
                f"{sorted(target.model.model_fields)}."
            )
        if field in {target.subject_field, target.member_field}:
            raise ValueError(
                f"{field!r} is {self.table}'s own "
                f"{'subject' if field == target.subject_field else 'member'} column, which is what "
                f"an overlay row keys ON. Re-keying a derived row is a suppress plus an insert, not "
                f"a correction — writing it here would leave this overlay row matching nothing the "
                f"moment it applied."
            )
        return self


def _cell(row: BaseModel, name: str) -> str:
    """A derived row's column as the overlay spells it: absent is `""`, everything else is `str`.

    `locus_index` is the one integer a `member` ever carries, and `variation_id` the one column that
    is a number in some sources and a string in others, so the comparison is on the rendered value
    rather than on the type. Read through `getattr` rather than `model_dump()`, which honours
    `exclude=True` and would silently answer `""` for a stamped column.
    """
    value = getattr(row, name, None)
    return "" if value is None else str(value)


def _rebuild(row: BaseModel, changes: dict[str, str | None]) -> BaseModel:
    """`row` with `changes` written into it, re-validated through its own model.

    Re-validating rather than `setattr`-ing is the point: the string an author wrote lands in the
    column's own type, every field validator runs against it, and so does every cross-field one — a
    `ResolutionRow` whose `alts` is corrected without its parallel `vrs_id` is refused here, which is
    the same net a hand-edit would have gone through.
    """
    model = type(row)
    data: dict[str, Any] = {name: getattr(row, name) for name in model.model_fields}
    data.update(changes)
    return model.model_validate(data)


def _canonical_key_cell(sample: BaseModel | None, field_name: str | None, value: str) -> str:
    """`value` as the target model would actually *store* it in `field_name`.

    **The overlay's key cells are raw author text and the derived rows are canonical**, so comparing
    the two directly is comparing a spelling against a value. `FrequencyRow.population` is the case
    that proves it: `normalize_population` lowercases, so an overlay `member=AFR` matched no row of a
    table full of `afr`. Every operation went wrong differently, and the worst went wrong silently —
    an `insert` believed the row was absent and appended a duplicate, so **each `compile → reverse →
    compile` lap appended another copy** and the Principle 7 fixed point this whole design rests on
    was broken by a capital letter. Nothing caught it: `FrequencyRow` is in neither `_TABLE_DUPE_KEYS`
    nor the frequency checks. A `suppress` silently removed nothing, and an `update` warned that a row
    plainly present "is not carried".

    The canonicalization runs through the model itself rather than through a table of per-column
    rules, because a table of rules is a second copy of every validator — and `population` was only
    the first: `locus_index` is an `int`, so `"01"` has the same shape. Writing the cell onto a real
    row of the table is what makes it the model's own answer.

    Falls back to the raw value when there is no row to write onto (an empty table matches nothing
    anyway) or when the model refuses it (an unholdable value matches nothing either, and an `update`
    then reports that honestly).
    """
    if sample is None or field_name is None or not value:
        return value
    try:
        return _cell(_rebuild(sample, {field_name: value}), field_name)
    except ValidationError:
        return value


def overlay_coherence_errors(overrides: Sequence[OverrideRow]) -> list[str]:
    """The file-level rules, which no single row can answer: one operation per key group.

    A duplicate `(table, subject, member, field)` is the model's own `_KEY_FIELDS` and is caught by
    the compiler's ordinary duplicate-row check, so it is not repeated here.
    """
    errors: list[str] = []
    operations: dict[tuple[str, str, str], set[str]] = {}
    order: list[tuple[str, str, str]] = []
    for row in overrides:
        key = (row.table, row.subject, (row.member or "").strip())
        if key not in operations:
            operations[key] = set()
            order.append(key)
        operations[key].add(row.operation)
    for key in order:
        if len(operations[key]) > 1:
            table, subject, member = key
            errors.append(
                f"overrides.csv: {table} subject={subject!r} member={member!r} carries more than "
                f"one operation ({sorted(operations[key])}). An insert is written as several rows "
                f"sharing that key, one per field, so a key names one decision — mixing operations "
                f"under it has no defined order."
            )
    return errors


def apply_overrides(
    table: str,
    rows: Sequence[BaseModel],
    overrides: Sequence[OverrideRow],
) -> tuple[list[BaseModel], list[str], list[str]]:
    """Lay the overlay rows naming `table` over its derived `rows`. Returns `(rows, errors, warnings)`.

    The returned list is the table **as the module asserts it**, which is what every downstream
    reader wants: the parquet is built from it, the fact signatures and `resolution_signature` are
    over it, and `reverse_module` emits it. Overlay rows naming another table are ignored, so a
    caller passes the whole file and this picks its own out.

    **Order is load-bearing** (parquet bytes depend on it), so:

    * `update` edits a row in place and moves nothing;
    * `suppress` removes a row and reorders nothing that remains;
    * `insert` appends at the **end of its subject's group** — after the last row already carrying
      that subject, or at the end of the table when the subject has no group yet — in the order the
      overlay rows appear. Placement is a function of the overlay's own authored order, which the
      round trip already preserves, rather than of a sort over values a corrected cell could move.

    **A no-op is not a finding, and that is forced rather than tidy.** After `reverse_module` the
    derived table is post-overlay, so on the second lap update-already-equal, insert-already-present
    and suppress-already-absent are *all three* true of a perfectly healthy module. Reporting any of
    them would make a module and its own round trip disagree on `manifest.compilation.warnings`, a
    published field. An `update` matching no row is the one mismatch an overlay operation cannot
    manufacture for itself, because an update never creates a row.

    **Two warnings come out of here, and the second is a record rather than a mismatch.** A `suppress`
    removes a row and leaves no trace of the removal anywhere in the build product, so RM131 has it
    say so — counted over the *overlay's* rows and aggregated by reason, which is what keeps it from
    being the lap-1-only line the paragraph above rules out. `_suppression_warnings` argues both.

    **That is not the same as being stable across both laps, and an earlier version of this docstring
    claimed it was.** The overlay is stable; the *derived table under it* is not, for the two tables
    the compiler rebuilds from something narrower than the file it read. `literature.csv` loses its
    uncited rows before the parquet (so `reverse_module`, which rebuilds it *from* that parquet,
    cannot carry them), and `resolution.csv` has no parquet at all and is rebuilt from the SNP core.
    An `update` naming such a row therefore matches on lap 1 and reports on lap 2 — the disagreement
    this function exists to avoid, arriving through the derivation rather than through the overlay.
    Not repaired here: applying the overlay after the drop would hide it from the checks that must
    see what the module asserts, and reverse has no source for rows the artifact does not hold. The
    warning below names it as the third reading instead of pretending to two.
    """
    target = OVERRIDABLE_TABLES[table]
    mine = [row for row in overrides if row.table == table]
    result: list[BaseModel] = list(rows)
    errors: list[str] = []
    unmatched: list[tuple[str, str]] = []
    if not mine:
        return result, errors, []

    groups: dict[tuple[str, str], list[OverrideRow]] = {}
    order: list[tuple[str, str]] = []
    for row in mine:
        key = (row.subject, (row.member or "").strip())
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    for key in order:
        subject, member = key
        group = groups[key]
        operation = group[0].operation
        # Canonicalized against a row of the table being corrected, and re-read **per group** rather
        # than once: an `insert` earlier in this loop may be the only row there is to ask.
        sample = result[0] if result else None
        subject_key = _canonical_key_cell(sample, target.subject_field, subject)
        member_key = _canonical_key_cell(sample, target.member_field, member)
        matched = [
            index
            for index, row in enumerate(result)
            if _cell(row, target.subject_field) == subject_key
            and (
                target.member_field is None
                or not member
                or _cell(row, target.member_field) == member_key
            )
        ]

        if operation == "update":
            if not matched:
                unmatched.append(key)
                continue
            changes = {row.field or "": (row.value or None) for row in group}
            # Aggregated **by reason**, not per row, which matters exactly where it is easiest to
            # miss: a group-scoped update over a `variant_key` that resolves to fifty loci would
            # otherwise print one identical refusal fifty times. Insertion order is the order the
            # reasons were first met, so the report is deterministic.
            refusals: dict[str, int] = {}
            for index in matched:
                try:
                    result[index] = _rebuild(result[index], changes)
                except ValidationError as exc:
                    refusals[str(exc)] = refusals.get(str(exc), 0) + 1
            errors.extend(
                f"overrides.csv: update of {table} subject={subject!r} member={member!r} produces "
                f"a row the table refuses, on {count} of {len(matched)} row(s) it reaches: {reason}"
                for reason, count in refusals.items()
            )
        elif operation == "suppress":
            for index in reversed(matched):
                del result[index]
        else:  # insert
            if matched:
                continue  # already present — the idempotent no-op the round trip depends on
            data: dict[str, Any] = {target.subject_field: subject}
            if target.member_field is not None:
                data[target.member_field] = member
            for row in group:
                data[row.field or ""] = row.value or None
            try:
                built = target.model.model_validate(data)
            except ValidationError as exc:
                errors.append(
                    f"overrides.csv: insert into {table} subject={subject!r} member={member!r} "
                    f"does not make a valid row: {exc}. An insert supplies every column the table "
                    f"requires, one overlay row per field."
                )
                continue
            # Off the BUILT row, not off the overlay's raw `subject`: the model has just canonicalized
            # it, so this is the one place the answer needs no re-derivation. Placing an insert by a
            # spelling the table does not use would put it at the end of the table instead of at the
            # end of its group — a row-order difference, and parquet bytes follow row order.
            built_subject = _cell(built, target.subject_field)
            tail = [
                index
                for index, row in enumerate(result)
                if _cell(row, target.subject_field) == built_subject
            ]
            result.insert(tail[-1] + 1 if tail else len(result), built)

    return result, errors, _unmatched_warnings(table, unmatched) + _suppression_warnings(table, mine)


def _unmatched_warnings(table: str, unmatched: Sequence[tuple[str, str]]) -> list[str]:
    """One aggregated line for the updates that reached no row, naming all three readings of it.

    Aggregated by **reason** rather than per row, the way every repeated finding in this workspace
    is, and it names every reading because nothing here can separate them: the subject may be
    mistyped, the source may have stopped publishing the row the correction was about, or — on a
    recompile of a reversed module — the compiler may have dropped the row before the parquet, so
    reverse could not rebuild it and the correction had no target to reach. Withholding the verdict
    is the house algebra: an unknown answer is neither reported as a fault nor negated.

    The third reading was missing while only two were named, which made the message assert that a
    correction was wrong in the one case where the correction is fine and the *table* is short.
    """
    if not unmatched:
        return []
    shown = ", ".join(
        f"{subject}" + (f"[{member}]" if member else "") for subject, member in unmatched[:5]
    )
    more = "" if len(unmatched) <= 5 else f" (+{len(unmatched) - 5} more)"
    return [CodedWarning(
        "overlay_update_unmatched",
        f"overrides.csv: {len(unmatched)} update override(s) name a row {table} does not carry: "
        f"{shown}{more}. Three readings and nothing here separates them — the subject/member may be "
        f"mistyped, the source may have stopped publishing the row the correction was about, or the "
        f"compiler dropped the row before the parquet so a reversed module cannot carry it. "
        f"Neither an insert nor a suppress reports this: an insert creates the row and a suppress "
        f"is satisfied by its absence."
    )]


#: The fragment a consumer keys on to find the suppression record, for the reason every named phrase
#: in this workspace exists: a published `manifest.json` carries the prose, and matching a substring
#: is what a reader without the compiler installed can do.
SUPPRESSED_PHRASE: str = "suppress override(s) remove"


def _suppression_warnings(table: str, overrides: Sequence[OverrideRow]) -> list[str]:
    """One line per suppression REASON, with a count — the trace a suppressed row otherwise leaves.

    A `suppress` is the one overlay operation whose effect is invisible in the build product: the row
    is simply absent, with nothing anywhere saying it was removed or why. `update` leaves the changed
    cell, `insert` leaves the new row, and both are readable from the artifact alone; a suppression is
    readable only from `overrides.csv`, which a consumer holding the compiled bytes does not have.

    **Counted over the overlay's own rows, never over the rows removed**, and that is the difference
    between a stable published field and one a module disagrees with its own round trip about. After
    `reverse_module` the derived table is already post-overlay, so on the second lap the same suppress
    matches nothing and removes nothing — an effect-based count would say `12` on lap 1 and vanish on
    lap 2, moving `manifest.compilation.warnings`. The overlay file round-trips unchanged, so a count
    over it says the same number both times. A `suppress` names exactly one row, so on the first lap
    the two counts agree anyway.

    Aggregated by **reason** rather than one line per row, which is why `reason` is a required column:
    a module suppressing forty rows for one cause produces one line saying forty. Insertion order is
    the order the reasons were first met, so the report is deterministic; the count and every reason
    survive, so this is an aggregation and not a cap.

    **Actionable rather than carried**, deliberately: the author owns the overlay and deleting the row
    clears the finding. It is a record of a decision, not a defect, and it stays in the actionable set
    because it is the author's to revisit — nobody else can.
    """
    reasons: dict[str, int] = {}
    for row in overrides:
        if row.table == table and row.operation == "suppress":
            reasons[row.reason] = reasons.get(row.reason, 0) + 1
    return [
        CodedWarning(
            "overlay_rows_suppressed",
            f"overrides.csv: {count} {SUPPRESSED_PHRASE} {table} row(s) from the compiled artifact, "
            f"where nothing else records the removal: {reason}",
        )
        for reason, count in reasons.items()
    ]
