"""The meta-table, `meta.csv` (0.8): RM28's combinations, RM323's per-locus facts, RM324's `tier`,
RM327's per-trait judgements, RM330's `sex` and the `drug` a row is about, in one table.

A row maps a **composite statement** to a finding and/or the per-locus facts. A composite statement is
one or more *members*, each an item of a single-statement table, written in one grammar:

    table[column=value, column=value]

joined by `&` at bracket depth 0 in one `members` cell. A concrete row is the selector over its table's
full key (`variants[variant_key=rs429358, genotype=C/C]`), a locus is `variants[variant_key=rs10455872]`,
a named allele is `allele_function[gene=APOE, allele=ε4]` and a tag set is
`variants[flags=legacy_longevitymap]`. The decisions behind every rule here are dated lines under RM28,
RM323, RM324, RM327 and RM330 in `ROADMAP_0_8.md`, fixed in `proposals/PROPOSAL_0_8_PT2.md` §3 items 1–8.

This module holds what needs no other table: the row model, the parser, the key, and the precedence rank
of one member against one row it matches. **Expansion** — which rows a member matches, and what the
compile writes — is the compiler's (`just_dna_compiler.compiler.meta`), because it needs the module's
other tables in hand.

Dependency-light like the rest of the format tier: `re`, `pydantic`, and the member tables' models.
"""

import re
from collections.abc import Mapping
from typing import Any, ClassVar, NamedTuple

from pydantic import Field, field_validator, model_validator

from just_dna_format.base import (
    AuthoredModel,
    authored_field_names,
    since,
    stamped_identity_field,
    vocabulary,
)
from just_dna_format.pgx import AlleleFunctionRow, DiplotypeRow, PharmVariantRow
from just_dna_format.spec import CitationPair, VariantRow, validate_pmid_cell
from just_dna_format.vocab import MULTI_SEP, check_vocab

#: The single-statement tables a member may name, in the order the compiler expands and sorts them.
#: The pm seat's setting (2026-11-04): the tables that carry a finding, plus `allele_function.csv` as
#: the home of a named allele. `haplotypes.csv` defines alleles and is not one; `studies.csv` is out by
#: the maintainer's bound.
META_MEMBER_TABLES: dict[str, type[AuthoredModel]] = {
    "variants": VariantRow,
    "diplotypes": DiplotypeRow,
    "pharm_variants": PharmVariantRow,
    "allele_function": AlleleFunctionRow,
}

#: The member tables that carry a `variant_key`, so `table[variant_key=…]` alone is a **locus-level**
#: member. A locus member ranks below a concrete row key and above any other selector.
LOCUS_TABLES: frozenset[str] = frozenset({"variants", "pharm_variants"})

#: `trait_role`'s one member (the maintainer's third addendum): empty means the trait is an effect, and
#: `mediator` marks the path to it. `outcome` was dropped as derivable.
VALID_TRAIT_ROLES: frozenset[str] = frozenset({"mediator"})

#: `sex` (RM330): the condition a consumer matches against karyotype. Closed, two members.
VALID_SEXES: frozenset[str] = frozenset({"male", "female"})

#: The columns that make a row say something. A row stating none of them is refused as empty: a member
#: set with nothing attached is a selector with no statement.
META_FINDING_COLUMNS: tuple[str, ...] = ("direction", "conclusion", "negatives")
META_FACT_COLUMNS: tuple[str, ...] = ("tier", "age_of_action", "age_of_action_confidence", "flags")

_MEMBER_PATTERN: re.Pattern[str] = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\[(.*)\]$", re.DOTALL)

#: The words for the two operators the maintainer put out of bounds, recognised at bracket depth 0 so an
#: author writing them gets the bound named rather than a parse error.
_DEPTH0_OR: re.Pattern[str] = re.compile(r"\bOR\b")
_DEPTH0_NOT: re.Pattern[str] = re.compile(r"\bNOT\b")


class MetaSelectorError(ValueError):
    """A `members` cell the grammar refuses. A `ValueError`, so pydantic reports it as a row error."""


class MetaMember(NamedTuple):
    """One parsed member: the table it names and its `column=value` conditions, in authored order."""

    table: str
    conditions: tuple[tuple[str, str], ...]

    def columns(self) -> frozenset[str]:
        return frozenset(column for column, _value in self.conditions)

    def canonical(self) -> str:
        """The member with its conditions sorted by column — one spelling per member, for the key."""
        inner = ", ".join(f"{column}={value}" for column, value in sorted(self.conditions))
        return f"{self.table}[{inner}]"


def selectable_columns(table: str) -> frozenset[str]:
    """The columns a member over `table` may name: the authored ones, plus `variant_key`.

    `variant_key` is compiler-stamped on every table that carries it, so an authored-only roster would
    refuse the canonical locus member `variants[variant_key=…]`. It is the one stamped column admitted;
    the rest (`authored_ident`, the expansion marker) describe what the compiler did, not the row.
    """
    model = META_MEMBER_TABLES[table]
    columns = set(authored_field_names(model))
    if "variant_key" in model.model_fields:
        columns.add("variant_key")
    return frozenset(columns)


def _split_depth0(cell: str) -> list[str]:
    """Split a `members` cell on `&` at bracket depth 0, refusing a bracket that does not pair."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in cell:
        if char == "[":
            depth += 1
            if depth > 1:
                raise MetaSelectorError(
                    f"members {cell!r}: a value may not contain '[' — brackets enclose a member's "
                    f"conditions, and a member cannot nest another"
                )
        elif char == "]":
            depth -= 1
            if depth < 0:
                raise MetaSelectorError(
                    f"members {cell!r}: a value may not contain ']' — it closes a member's conditions"
                )
        elif depth == 0 and char == "&":
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if depth != 0:
        raise MetaSelectorError(f"members {cell!r}: a '[' is never closed")
    parts.append("".join(current))
    return parts


def _depth0_text(cell: str) -> str:
    """The cell with every bracketed part blanked, so an operator inside a value is never seen."""
    out: list[str] = []
    depth = 0
    for char in cell:
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        elif depth == 0:
            out.append(char)
            continue
        out.append(" ")
    return "".join(out)


def _parse_condition(table: str, member_text: str, condition: str) -> tuple[str, str]:
    """One `column=value`, with every bound refused by its own message."""
    if not condition:
        raise MetaSelectorError(f"member {member_text!r}: an empty condition (a stray ',')")
    if "=" not in condition:
        if "<" in condition or ">" in condition:
            raise MetaSelectorError(
                f"member {member_text!r}: {condition!r} — numeric ranges are out of bounds; a condition "
                f"is column=value"
            )
        raise MetaSelectorError(
            f"member {member_text!r}: condition {condition!r} has no '='. A value may not contain ',', "
            f"which separates conditions"
        )
    column, value = (part.strip() for part in condition.split("=", 1))
    if column.endswith("!"):
        raise MetaSelectorError(
            f"member {member_text!r}: {condition!r} — negation is out of bounds, because negation over an "
            f"open set cannot be checked. Name the rows you mean"
        )
    if column.endswith(("<", ">")):
        raise MetaSelectorError(
            f"member {member_text!r}: {condition!r} — numeric ranges are out of bounds; a condition is "
            f"column=value"
        )
    if "." in column:
        raise MetaSelectorError(
            f"member {member_text!r}: {condition!r} — joins across tables are out of bounds. A member "
            f"selects rows of its own table; write a second member for the other table"
        )
    if "=" in value:
        raise MetaSelectorError(f"member {member_text!r}: the value in {condition!r} may not contain '='")
    if not value:
        raise MetaSelectorError(f"member {member_text!r}: {condition!r} has an empty value")
    if column not in selectable_columns(table):
        raise MetaSelectorError(
            f"member {member_text!r}: {table}.csv has no column {column!r}. Selectable: "
            f"{sorted(selectable_columns(table))}"
        )
    return column, value


def _parse_member(text: str) -> MetaMember:
    stripped = text.strip()
    if not stripped:
        raise MetaSelectorError("members: an empty member (a stray '&')")
    match = _MEMBER_PATTERN.match(stripped)
    if match is None:
        raise MetaSelectorError(f"member {stripped!r} is not table[column=value, …]")
    table, inner = match.group(1), match.group(2)
    if table == "studies":
        raise MetaSelectorError(
            f"member {stripped!r}: selectors over studies.csv are out of bounds — a study row is evidence "
            f"for a statement, not a statement. Cite it with this row's `pmid`"
        )
    if table not in META_MEMBER_TABLES:
        raise MetaSelectorError(
            f"member {stripped!r}: {table!r} is not a member table. A member names a row of one of "
            f"{sorted(META_MEMBER_TABLES)}"
        )
    if not inner.strip():
        raise MetaSelectorError(f"member {stripped!r} names no condition")
    conditions = tuple(_parse_condition(table, stripped, part.strip()) for part in inner.split(","))
    seen: set[str] = set()
    for column, _value in conditions:
        if column in seen:
            raise MetaSelectorError(
                f"member {stripped!r} names column {column!r} twice. Conditions are AND-ed, so two values "
                f"for one column match nothing; OR is a second row"
            )
        seen.add(column)
    return MetaMember(table, conditions)


def parse_members(cell: str) -> list[MetaMember]:
    """Parse a `members` cell into its members, in authored order. Raises `MetaSelectorError`.

    Bracket-aware: an `&` or `|` inside a value is data (RM253's DPYD names, a phased genotype). The
    shared `MULTI_SEP` splitter is never used on this cell. At depth 0, `|` and the words `OR`/`NOT` are
    refused by name, as the maintainer's bounds (no OR, no negation): rows are already a disjunction.
    """
    outside = _depth0_text(cell)
    if "|" in outside or _DEPTH0_OR.search(outside):
        raise MetaSelectorError(
            f"members {cell!r}: OR is out of bounds — rows are already a disjunction, so write one row "
            f"per alternative"
        )
    if _DEPTH0_NOT.search(outside) or "!" in outside:
        raise MetaSelectorError(
            f"members {cell!r}: negation is out of bounds, because negation over an open set cannot be "
            f"checked"
        )
    members = [_parse_member(part) for part in _split_depth0(cell)]
    canon = [member.canonical() for member in members]
    if len(set(canon)) != len(canon):
        raise MetaSelectorError(f"members {cell!r} names one member twice")
    return members


def split_members(cell: str) -> list[str]:
    """The members of a `members` cell, each verbatim as authored (stripped), in authored order.

    The texts a finding or the manifest quotes back to the author. Call `parse_members` first (or hold
    a row that validated): this splits without judging.
    """
    return [part.strip() for part in _split_depth0(cell)]


def normalize_members(cell: str) -> str:
    """The row key's member half: members sorted, conditions sorted within each, joined by ` & `.

    `A & B` and `B & A` are one key, as are `[gene=X, allele=Y]` and `[allele=Y, gene=X]`. The authored
    cell is kept verbatim on the row (P7: `reverse` writes back what the author wrote); this is a stamped
    column beside it.
    """
    return " & ".join(sorted(member.canonical() for member in parse_members(cell)))


def allele_bearing(member: MetaMember) -> bool | None:
    """Does this member fix an allele, so a `direction` on its row says which allele it is about?

    Three-valued (§3 item 6). `True`: a `variants`/`pharm_variants` member with a `genotype` condition,
    a `diplotypes` member naming either haplotype, or any `allele_function` member. `None`: a bare
    `variants[variant_key=…]` locus, which bears an allele only when every row of that locus states the
    same `effect_allele` — a fact of the module's data, decided at compile. `False`: anything else (a tag
    selector, a gene, a phenotype), which a `direction` row refuses.
    """
    columns = member.columns()
    if member.table == "allele_function":
        return True
    if member.table == "diplotypes":
        return bool(columns & {"haplotype_a", "haplotype_b"})
    if "genotype" in columns:
        return True
    if member.table == "variants" and columns == {"variant_key"}:
        return None
    return False


def member_rank(member: MetaMember, target: Mapping[str, Any]) -> tuple[int, int]:
    """How specific `member` is about `target`, a row of its own table it matches (its key cells).

    `(3, 0)` a **concrete row key**: the conditions name every key column the row fills (an empty
    `drug` or `clinical_context` on a diplotype need not be named). `(2, 0)` a **locus**: `variant_key`
    alone, on a table that carries one. `(1, n)` a **selector** with `n` conditions. Compared as tuples,
    which is the maintainer's order: a concrete key, then a locus, then more conditions, then fewer.
    Equal ranks are incomparable, never ordered by anything else.
    """
    model = META_MEMBER_TABLES[member.table]
    key_fields: tuple[str, ...] = model._KEY_FIELDS  # type: ignore[attr-defined]
    filled = {name for name in key_fields if target.get(name) is not None}
    columns = member.columns()
    if filled and filled <= columns:
        return (3, 0)
    if member.table in LOCUS_TABLES and columns == {"variant_key"}:
        return (2, 0)
    return (1, len(columns))


class MetaRow(CitationPair, AuthoredModel):
    """One row of `meta.csv`: a composite statement mapped to a finding and/or per-locus facts.

    The key is the normalized member set plus `trait_efo_id` plus `sex` (§3 item 4) plus `drug` (the
    lead, 2026-11-04), so `A & B` and `B & A` are one key, refused as a duplicate, while a `male` row and
    a `female` row for one member set are two statements, and so are an azathioprine row and a
    mercaptopurine row for one TPMT × NUDT15 phenotype pair (CPIC states one recommendation per
    thiopurine).

    Inherits `AuthoredModel` (reserved-namespace guard, and the shared `trait_efo_id`/`direction`
    validators).
    """

    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("members_key", "trait_efo_id", "sex", "drug")
    #: A row must state at least one finding or fact column — any ONE of these satisfies it. Declared
    #: beside `_validate_statement` so a tool listing what a row needs can see the rule (the
    #: `VariantRow` rsid-or-coordinate precedent); `conclusion` first, the one a stub offers.
    REQUIRED_ANY_OF: ClassVar[tuple[frozenset[str], ...]] = tuple(
        frozenset({name})
        for name in sorted((*META_FINDING_COLUMNS, *META_FACT_COLUMNS), key=lambda n: n != "conclusion")
    )

    members: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "The composite statement: one or more members joined by `&`, each `table[column=value, …]` "
            "over variants, diplotypes, pharm_variants or allele_function. Conditions are AND-ed; on a "
            "list column such as `flags`, `=` means contains. Inside a combination a member is "
            "existential (any row it matches). A value may not contain `[`, `]`, `,` or `=`."
        ),
    )
    members_key: str | None = stamped_identity_field(
        "The member set normalized for the row key: members sorted, conditions sorted within each. "
        "Compiler-managed: stamped from `members`, which stays verbatim.",
        first_seen="0.8.0",
    )
    trait_efo_id: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description="EFO/MONDO/OBA/HP trait the row's judgement is about. Part of the key.",
    )
    trait_role: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("trait_role", VALID_TRAIT_ROLES), **since("0.8.0")},
        description=(
            "How the member reaches the trait: empty means the trait is an effect, `mediator` marks it "
            "as the path to another (LDL cholesterol on the way to CAD). Needs `trait_efo_id`."
        ),
    )
    direction: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "The curator's judgement on the trait, the shared `direction` vocabulary. Every member of a "
            "row with a direction must fix an allele, so the judgement says which allele it is about."
        ),
    )
    conclusion: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "The finding. On a row with two or more members it replaces the findings of the rows the "
            "members match (a matching combination replaces the single-locus findings it names)."
        ),
    )
    negatives: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description="The adverse counterpart to `conclusion`, as on variants.csv.",
    )
    tier: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "Evidence tier, on the scale `module_spec.yaml` names once as `tier_scale` (refused without "
            "one). Open text: the scale is the module's, and values are not checked against it."
        ),
    )
    age_of_action: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description="When in life the effect acts, in the module's own terms (e.g. MIDLIFE, LATE).",
    )
    age_of_action_confidence: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description="How directly `age_of_action` is supported, in the module's own terms.",
    )
    flags: list[str] | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "Open, multi-valued tag list (CSV: comma/semicolon/pipe-separated), as on variants.csv, so "
            "every kind of member can carry tags (e.g. `ap:weak`, `hallmark:…`)."
        ),
    )
    pmid: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "PubMed id this row's claim is cited to, when the claim is finer than studies.csv's key "
            "(the RM47 pattern). Free-form like `StudyRow.pmid`."
        ),
    )
    doi: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "Digital Object Identifier of the work THIS row cites, kept verbatim (bare or as a doi.org "
            "URL). Optional beside a PubMed id; **mandatory when `pmid` is `NONE`**, the sentinel for "
            "a work PubMed does not index (a preprint, a book, a dataset), RM336. Same rule as "
            "`StudyRow.doi`."
        ),
    )
    sex: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("sex", VALID_SEXES), **since("0.8.0")},
        description=(
            "Scopes the whole row to one sex (male|female), matched by the consumer against karyotype. "
            "Part of the key; a row with `sex` outranks the same key without it, for that sex."
        ),
    )
    drug: str | None = Field(
        json_schema_extra=since("0.8.0"),
        default=None,
        description=(
            "Drug the row's statement is about, e.g. mercaptopurine; free text, as on diplotypes.csv and "
            "pharm_variants.csv. Scopes the whole row, so it is part of the key: one member set states "
            "one finding per drug, and a row with `drug` outranks the same key without it, for that drug. "
            "Not a member condition: `diplotypes[drug=…]` selects diplotype rows carrying that drug."
        ),
    )

    @field_validator("members")
    @classmethod
    def _validate_members(cls, v: str) -> str:
        parse_members(v)  # raises with the bound or the character it refused
        return v

    @field_validator("trait_role")
    @classmethod
    def _validate_trait_role(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_TRAIT_ROLES, "trait_role")

    @field_validator("sex")
    @classmethod
    def _validate_sex(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_SEXES, "sex")

    @field_validator("flags", mode="before")
    @classmethod
    def _split_flags(cls, v: object) -> object:
        # `VariantRow.flags`' rule: a CSV cell arrives as a string and splits on the shared separator.
        if isinstance(v, str):
            tags = [t.strip() for t in MULTI_SEP.split(v) if t.strip()]
            return tags or None
        return v

    @field_validator("pmid")
    @classmethod
    def _validate_pmid(cls, v: str | None) -> str | None:
        # `PharmVariantRow.pmid`'s rule: the one grammar every citation pointer goes through, optional
        # here. The `doi` cell and the pmid/doi pair (`NONE` makes `doi` mandatory) are `CitationPair`'s.
        return validate_pmid_cell(v, "pmid", required=False)

    @model_validator(mode="after")
    def _validate_statement(self) -> "MetaRow":
        # `members` failed its own validator if it did not parse, so this runs on a parseable cell.
        self.members_key = normalize_members(self.members)
        if not any(getattr(self, name) for name in (*META_FINDING_COLUMNS, *META_FACT_COLUMNS)):
            raise ValueError(
                f"meta row {self.members!r} states no finding and no fact — fill at least one of "
                f"{[*META_FINDING_COLUMNS, *META_FACT_COLUMNS]}; a member set with nothing attached says "
                f"nothing"
            )
        if self.trait_role is not None and self.trait_efo_id is None:
            raise ValueError(
                "trait_role says how a trait is reached, and trait_efo_id is empty — name the trait, or "
                "clear trait_role"
            )
        if self.direction is not None:
            refused = [m.canonical() for m in parse_members(self.members) if allele_bearing(m) is False]
            if refused:
                raise ValueError(
                    f"meta row {self.members!r} states a direction, and a member that fixes no allele "
                    f"cannot carry one: {refused}. A direction is about an allele — use a genotype, a haplotype, an "
                    f"allele_function member, or a bare variants[variant_key=…] locus whose rows share "
                    f"one effect_allele"
                )
        return self
