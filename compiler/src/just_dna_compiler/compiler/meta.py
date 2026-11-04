"""The meta-table at compile (0.8): load `meta.csv`, expand every member, resolve precedence, and build
`meta.parquet` and `meta_resolved.parquet`.

The model and the grammar are the format tier's (`just_dna_format.meta`); this module needs the
module's other tables in hand, which is why it lives here. The table is loaded by the one loader every
authored table outside the table kinds shares (`load.load_authored_table`, RM357).

**Expansion reads the authored rows, after the symbolic-allele drop and before resolution**, on both
sides: `validate_spec` and `compile_module` hand it the same view, so a member matches the same rows in
the pre-flight and in the compile and every finding is one sentence on both (`@parity-by-check`). For a
`variants.csv` row the recorded key is the authored `(variant_key, genotype)`, which is the key
`weights.parquet` carries for every row resolution did not expand. An rsID that resolution expands onto
several loci is the one residual: its weights rows are coordinate-keyed, and a consumer reaches them
from the meta key through their `rsid` column (COMPILER.md § The meta-table).

**What `meta_resolved.parquet` holds.** One row per single-statement row a **one-member** meta row
reaches, per `(sex, drug)` scope, with each fact column (`tier`, `age_of_action`, `age_of_action_confidence`,
`flags`) after precedence and a `withheld` list naming the columns two incomparable, disagreeing rows
left unresolved. A row of two or more members states facts about the **combination**, so its facts stay
on its own `meta.parquet` row and never reach a member row by itself.

**`tradeoff` (RM327)** is computed there too, per allele-bearing **member** and never pooled across
members: `True` when one member has a `protective` per-trait row and a `risk` per-trait row (a
one-member row with `trait_efo_id` and a direction not withheld; a `mediator` row counts, since its
direction is still a benefit/harm judgement), and that verdict lands on every row the member reaches,
including the diplotypes an `allele_function` member reaches through the allele they carry. On one
trait at one row, the fact columns' precedence applies first, so a narrower judgement the author made
about that row (a diplotype member over the allele it contains, a genotype over its locus, a sex- or
drug-scoped row over the unscoped one) drops the broader judgement on that trait. A row two members
reach is `True` when either member is. **Never `False`**: RM327's false arm needs every trait's
judgement stated, and a module states no closed list of the traits an allele touches, so absence of an
opposing row is unknown, not a negative. Two alleles meeting at a heterozygous diplotype are two
members, so ε2 protective on one trait and ε4 risk on another is not a trade-off of either.
"""

import itertools
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple

import polars as pl
from just_dna_format.findings import CodedWarning
from just_dna_format.manifest import MetaSelectorCount
from just_dna_format.meta import (
    LOCUS_TABLES,
    META_FACT_COLUMNS,
    META_FINDING_COLUMNS,
    META_MEMBER_TABLES,
    MetaMember,
    MetaRow,
    allele_bearing,
    member_rank,
    parse_members,
    split_members,
)
from just_dna_format.spelling import comparison_key, drug_key, gene_key

from just_dna_compiler.compiler.tables import META_CSV, _polars_type

#: The order tables are expanded and `meta_resolved.parquet` is sorted in: `META_MEMBER_TABLES`' own.
_TABLE_ORDER: tuple[str, ...] = tuple(META_MEMBER_TABLES)

#: The key columns after the member set and the trait that scope a **whole row**: each is a condition a
#: consumer matches (`sex` against karyotype, `drug` against what is prescribed), and each is an axis of
#: `meta_resolved.parquet`'s grain, in this order. A row stating none applies in every scope.
_SCOPE_FIELDS: tuple[str, ...] = ("sex", "drug")

#: One scope: a value per `_SCOPE_FIELDS` axis, `None` where the scope does not condition on it.
Scope = tuple[str | None, ...]


def _scope(row: MetaRow) -> Scope:
    """The row's scope as rows are compared: each axis through its comparison key (RM363), so
    `Azathioprine` and `azathioprine` are one drug scope. `_spellings` names it back for the parquet."""
    return tuple(comparison_key(name, getattr(row, name)) for name in _SCOPE_FIELDS)


def _spellings(rows: list[MetaRow]) -> dict[tuple[int, Any], str]:
    """`(axis, scope value) -> the first authored spelling`, in `meta.csv` row order: how
    `meta_resolved.parquet` names a scope two rows wrote two ways. Deterministic, and authored."""
    spelled: dict[tuple[int, Any], str] = {}
    for row in rows:
        for axis, name in enumerate(_SCOPE_FIELDS):
            value = getattr(row, name)
            if value is not None:
                spelled.setdefault((axis, comparison_key(name, value)), value)
    return spelled


def _scope_value_order(value: str | None) -> tuple[bool, str]:
    """Per axis, `None` (no scope) first, then the values by name — so `(none, female, male)` for sex."""
    return (value is not None, value or "")


def _refines(a: Scope, b: Scope) -> bool:
    """Is scope `a` strictly narrower than `b`? Every axis `b` states, `a` states the same; `a` states more.

    `(male, None)` and `(None, azathioprine)` refine neither each other, so two rows scoped on different
    axes are incomparable where both apply; `(male, azathioprine)` refines both.
    """
    return a != b and all(bv is None or av == bv for av, bv in zip(a, b, strict=True))


def _within(row_scope: Scope, scope: Scope) -> bool:
    """Does a row scoped `row_scope` apply in `scope`? On each axis it states nothing or the same value."""
    return all(rv is None or rv == sv for rv, sv in zip(row_scope, scope, strict=True))


_MATCH_STRUCT = pl.Struct({"member": pl.Int64, "table": pl.Utf8, "key": pl.List(pl.Utf8)})


def _line(index: int) -> int:
    """The CSV line of the `index`-th data row, the loader's numbering (`meta.csv line N`)."""
    return index + 2


class MetaMatch(NamedTuple):
    """One row a member matched: which member, which table, the row's position there and its key."""

    member: int
    table: str
    index: int
    key: tuple[str | None, ...]


@dataclass
class MetaBuild:
    """Everything the compile writes from `meta.csv`, computed before anything is written."""

    rows: list[MetaRow]
    members: list[list[MetaMember]]
    texts: list[list[str]]
    matches: list[list[MetaMatch]]
    withheld: list[list[str]]
    resolved: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]

    def selector_counts(self) -> list[MetaSelectorCount]:
        """Every member of every row with its match count, in authored order, for the manifest."""
        return [
            MetaSelectorCount(
                row=index, selector=text, matches=sum(1 for m in self.matches[index] if m.member == position)
            )
            for index, texts in enumerate(self.texts)
            for position, text in enumerate(texts)
        ]


def member_tables(variants: list[Any], kind_rows: Mapping[str, list[Any]]) -> dict[str, list[Any]]:
    """The rows each member table holds, keyed by the name a member uses (`variants`, not the file)."""
    return {
        name: (variants if name == "variants" else list(kind_rows.get(f"{name}.csv") or []))
        for name in _TABLE_ORDER
    }


def _as_stored(member: MetaMember) -> MetaMember:
    """The member's conditions as the model would store them, so matching compares like with like.

    A diplotype pair is canonicalized `haplotype_a <= haplotype_b` on load (`DiplotypeRow`), so a member
    naming both halves in the other order is swapped here rather than matching nothing. The authored
    cell is untouched; only the comparison sees the swap (`@overlay-not-inside`'s third line).
    """
    if member.table != "diplotypes":
        return member
    conditions = dict(member.conditions)
    a, b = conditions.get("haplotype_a"), conditions.get("haplotype_b")
    if a is None or b is None or a <= b:
        return member
    swapped = {**conditions, "haplotype_a": b, "haplotype_b": a}
    return MetaMember(member.table, tuple((column, swapped[column]) for column, _value in member.conditions))


def _condition_holds(row: Any, column: str, value: str) -> bool:
    """`column=value` against what the model **stores**: on a list column `=` means contains."""
    stored = getattr(row, column, None)
    if stored is None:
        return False
    if isinstance(stored, list):
        return value in stored
    if isinstance(stored, bool):
        return value == ("true" if stored else "false")
    if isinstance(stored, float) and stored.is_integer():
        return value in (str(int(stored)), str(stored))
    # Through the column's comparison (RM363): `gene=apoe` selects the rows that store `APOE`, as every
    # other gene comparison in the module does. A column of no compared kind is verbatim.
    return comparison_key(column, str(stored)) == comparison_key(column, value)


def _variant_key_index(rows: list[Any]) -> dict[str | None, list[int]]:
    """Row positions by `variant_key`, in authored order — a locus member's matches without a scan."""
    index: dict[str | None, list[int]] = {}
    for position, row in enumerate(rows):
        index.setdefault(row.variant_key, []).append(position)
    return index


def _key_cells(row: Any) -> dict[str, Any]:
    return {name: getattr(row, name) for name in row._KEY_FIELDS}


def _key(row: Any) -> tuple[str | None, ...]:
    return tuple(None if value is None else str(value) for value in _key_cells(row).values())


def _matches_nothing(index: int, text: str, table: str) -> str:
    return (
        f"{META_CSV} line {_line(index)}: member {text!r} matches no row of {table}.csv. A selector that "
        f"matches nothing is almost always a typo — compare each value against what the table stores (a "
        f"diplotype pair is stored with haplotype_a <= haplotype_b, a genotype with its alleles sorted)."
    )


def _drug_disagrees(index: int, text: str, tables: str, drug: str, stated: list[str]) -> str:
    return (
        f"{META_CSV} line {_line(index)}: the row is about drug {drug!r} and member {text!r} reaches "
        f"{tables} rows about {stated}. A drug-scoped row's facts apply where {drug!r} is prescribed, so "
        f"stating them over a finding about another drug pairs two claims that are not about the same "
        f"thing. Name the drug in a member whose table carries one (`diplotypes[…, drug={drug}]`), or "
        f"correct the row's `drug`."
    )


def _member_drug_disagrees(row: MetaRow, reached: list[Any]) -> list[str]:
    """The drugs the rows a member reaches state that the meta row's `drug` is not (RM363), in row order.

    `reached` is what the row's facts land on: the member's matches, and for a one-member `allele_function`
    row the diplotypes containing the allele (`_contained`). By `drug_key`, so a spelling is never a
    disagreement. A reached row stating no drug, or a meta row stating none, is unknown and adds nothing
    (`@absent-is-not-different`)."""
    if row.drug is None:
        return []
    stated = [getattr(target, "drug", None) for target in reached]
    other = [drug for drug in stated if drug is not None and drug_key(drug) != drug_key(row.drug)]
    return list(dict.fromkeys(other))


def _diplotypes_by_gene(diplotypes: list[Any]) -> dict[str, list[int]]:
    """Diplotype positions by `gene_key`, in authored order — `_contained`'s index, built once."""
    index: dict[str, list[int]] = {}
    for position, diplotype in enumerate(diplotypes):
        index.setdefault(gene_key(diplotype.gene), []).append(position)
    return index


def _contained(allele_row: Any, diplotypes: list[Any], by_gene: dict[str, list[int]]) -> list[int]:
    """The diplotypes a named allele reaches: its gene's (by `gene_key`, RM363) that carry it on either
    homolog, in authored order. The one rule `_resolve` and the drug check both read."""
    return [
        position
        for position in by_gene.get(gene_key(allele_row.gene), [])
        if allele_row.allele in (diplotypes[position].haplotype_a, diplotypes[position].haplotype_b)
    ]


def _allele_ambiguous(index: int, text: str, stated: list[str]) -> str:
    seen = sorted(set(stated)) or ["none"]
    return (
        f"{META_CSV} line {_line(index)}: member {text!r} is a bare locus on a row stating a direction, "
        f"and that locus's variants.csv rows do not share one effect_allele (they state {seen}), so the "
        f"row does not say which allele its direction is about. The direction is withheld: "
        f"meta.parquet lists it in that row's `withheld` (the authored cell is kept for reverse). Name "
        f"the genotype in the member, or state one effect_allele on every row of the locus."
    )


class _Candidate(NamedTuple):
    """A one-member meta row reaching one target row: directly, or as an allele its diplotype contains."""

    meta: int
    via: str  # "direct" | "contained"
    rank: tuple[int, int]


def _outranks(a: _Candidate, b: _Candidate, rows: list[MetaRow]) -> bool:
    """Does `a` win over `b` for one target? A strict partial order; incomparable is `False` both ways.

    A row whose scope (`sex`, `drug`) refines another's on the same member set and trait outranks it: a
    sex-scoped row outranks the same key without a sex, a drug-scoped row the same key without a drug,
    and a row scoped on both outranks either (only rows applying in the scope being resolved are
    candidates, so two different stated values never meet). A `diplotypes` member outranks an
    `allele_function` member reaching the same diplotype through one of its alleles: the narrower condition wins across tables (the
    maintainer, 2026-11-04). Otherwise the rank decides, between candidates reaching the same way.
    """
    ra, rb = rows[a.meta], rows[b.meta]
    if (ra.members_key, ra.trait_efo_id) == (rb.members_key, rb.trait_efo_id) and _refines(
        _scope(ra), _scope(rb)
    ):
        return True
    if a.via == "direct" and b.via == "contained":
        return True
    return a.via == b.via and a.rank > b.rank


def _comparable(value: Any) -> Any:
    return tuple(sorted(set(value))) if isinstance(value, list) else value


#: The two directions that oppose each other across traits. `neutral`, `unknown` and `contested` are not
#: a benefit or a harm (RM327: `contested` means the sources disagree about the sign, not a trade-off).
_TRADEOFF_SIGNS: frozenset[str] = frozenset({"protective", "risk"})


def _tradeoff(applicable: list[_Candidate], rows: list[MetaRow], withheld: list[list[str]]) -> bool | None:
    """RM327's verdict for one `(target, scope)`: `True` when a member reaching it has both signs, else
    `None`.

    `applicable` is already the `(sex, drug)` scope's candidates. A per-trait judgement is a candidate
    with a `trait_efo_id` and a `direction`; every member carrying one is allele-bearing, because `MetaRow`
    refuses a direction on any other member and a bare locus whose rows share no `effect_allele` has its
    direction withheld here.

    1. **Precedence per trait, as the fact columns take it** (`_outranks`): among the judgements on one
       trait at this target, one that a more specific judgement on the same trait outranks is dropped —
       a sex- or drug-scoped row over the same key unscoped, a `diplotypes` member over an allele it
       contains, a concrete row key over a locus. So an author's narrower statement about this row wins.
    2. **Signs per member** (`members_key`), never pooled across members: two alleles meeting at a
       heterozygous diplotype are two members, and neither has a trade-off because of the other.
    3. A direction the compile withheld still takes part in precedence (it is a statement about the
       trait) but is unknown, so it adds no sign. Kleene with the false arm unreachable: a module states
       no closed trait list, so one sign alone is `None`, never `False`.
    """
    stating = [
        c for c in applicable if rows[c.meta].trait_efo_id is not None and rows[c.meta].direction is not None
    ]
    signs: dict[str, set[str]] = {}
    for candidate in stating:
        row = rows[candidate.meta]
        if any(
            rows[other.meta].trait_efo_id == row.trait_efo_id and _outranks(other, candidate, rows)
            for other in stating
        ):
            continue
        if "direction" in withheld[candidate.meta] or row.direction not in _TRADEOFF_SIGNS:
            continue
        signs.setdefault(row.members_key or "", set()).add(row.direction)
    return True if any(member == _TRADEOFF_SIGNS for member in signs.values()) else None


def _resolve(
    rows: list[MetaRow],
    members: list[list[MetaMember]],
    matches: list[list[MetaMatch]],
    tables: dict[str, list[Any]],
    withheld_by_row: list[list[str]],
) -> list[dict[str, Any]]:
    """`meta_resolved.parquet`'s rows: each target a one-member row reaches, per scope, after precedence.

    The scopes of one target are every combination of the values its candidates state on each axis,
    each axis with `None` beside them: `({None} ∪ sexes) × ({None} ∪ drugs)`. The product, not only the
    scopes some row states, so a consumer who is male and prescribed azathioprine finds one row for
    that pair even when only a `male` row and an `azathioprine` row exist; a scope no candidate applies
    in is skipped. A consumer builds its lookup per axis: its own value where the target has rows for
    it, else `None` (a female consumer at a target only `male` rows scope reads the `None` sex scope).
    """
    reach: dict[tuple[int, int], dict[int, _Candidate]] = {}

    def _keep(target: tuple[int, int], candidate: _Candidate) -> None:
        held = reach.setdefault(target, {})
        if candidate.meta not in held or candidate.rank > held[candidate.meta].rank:
            held[candidate.meta] = candidate

    diplotypes = tables.get("diplotypes") or []
    by_gene = _diplotypes_by_gene(diplotypes)
    for index, row_members in enumerate(members):
        if len(row_members) != 1:
            continue
        (member,) = row_members
        table = _TABLE_ORDER.index(member.table)
        for match in matches[index]:
            target = tables[member.table][match.index]
            rank = member_rank(member, _key_cells(target))
            _keep((table, match.index), _Candidate(index, "direct", rank))
            if member.table != "allele_function":
                continue
            # A named allele reaches every diplotype of its gene that contains it, so the ε2 and ε4
            # rows meet at ε2/ε4. Ranked below any diplotypes member there (`_outranks`).
            for position in _contained(target, diplotypes, by_gene):
                _keep((_TABLE_ORDER.index("diplotypes"), position), _Candidate(index, "contained", rank))

    spelled = _spellings(rows)
    resolved: list[dict[str, Any]] = []
    for table, position in sorted(reach):
        candidates = [reach[(table, position)][meta] for meta in sorted(reach[(table, position)])]
        name = _TABLE_ORDER[table]
        key = list(_key(tables[name][position]))
        axes = [
            sorted({_scope(rows[c.meta])[axis] for c in candidates} | {None}, key=_scope_value_order)
            for axis in range(len(_SCOPE_FIELDS))
        ]
        # The product of axes each sorted with `None` first is itself in that order, sex-major.
        for scope in itertools.product(*axes):
            applicable = [c for c in candidates if _within(_scope(rows[c.meta]), scope)]
            if not applicable:
                continue
            record: dict[str, Any] = {
                "table": name,
                "key": key,
                **{
                    axis_name: spelled.get((axis, value), value)
                    for axis, (axis_name, value) in enumerate(zip(_SCOPE_FIELDS, scope, strict=True))
                },
            }
            withheld: list[str] = []
            for column in META_FACT_COLUMNS:
                # Per-locus facts come from rows naming no trait. A per-trait row (`trait_efo_id`) is a
                # separate statement by the key, so its facts are about that trait and stay on its own
                # meta.parquet row; pooling them here would report two traits' tiers as a conflict.
                stating = [
                    c
                    for c in applicable
                    if rows[c.meta].trait_efo_id is None and getattr(rows[c.meta], column)
                ]
                top = [c for c in stating if not any(_outranks(o, c, rows) for o in stating)]
                values = {_comparable(getattr(rows[c.meta], column)) for c in top}
                if len(values) == 1:
                    record[column] = getattr(rows[top[0].meta], column)
                else:
                    record[column] = None
                    if values:
                        withheld.append(column)
            record["tradeoff"] = _tradeoff(applicable, rows, withheld_by_row)
            record["withheld"] = withheld
            record["meta_rows"] = [c.meta for c in applicable]
            resolved.append(record)
    return resolved


def meta_scale_errors(rows: list[MetaRow], tier_scale: str | None) -> list[str]:
    """The one refusal that needs the module but no other table: a `tier` with no `tier_scale` (RM324).

    Separate from `build_meta` so `compile_module` can ask it before `mkdir` while expanding after the
    positional fill, where its rows match the pre-flight's.
    """
    tiered = [_line(index) for index, row in enumerate(rows) if row.tier is not None]
    if not tiered or tier_scale:
        return []
    return [
        f"{META_CSV} states `tier` on line(s) {tiered} and module_spec.yaml names no `tier_scale` — a "
        f"tier with no scale beside it is a grade nobody can read. Name the scale once in "
        f"module_spec.yaml as `tier_scale:` (free text, e.g. the rubric your README defines)."
    ]


def build_meta(rows: list[MetaRow], tables: dict[str, list[Any]], tier_scale: str | None) -> MetaBuild:
    """Expand every member against `tables`, judge the rows that need the module, and resolve precedence.

    Pure computation over rows already loaded, so both `validate_spec` and `compile_module` run it, on
    the same view, and reach the same sentences. Nothing here reads or writes a file.
    """
    errors: list[str] = meta_scale_errors(rows, tier_scale)
    warnings: list[str] = []

    by_key: dict[str, dict[str | None, list[int]]] = {}
    by_gene_of: dict[str, dict[str, list[int]]] = {}
    all_members: list[list[MetaMember]] = []
    all_texts: list[list[str]] = []
    all_matches: list[list[MetaMatch]] = []
    all_withheld: list[list[str]] = []
    for index, row in enumerate(rows):
        row_members = parse_members(row.members)
        texts = split_members(row.members)
        row_matches: list[MetaMatch] = []
        withheld: list[str] = []
        for position, (authored, text) in enumerate(zip(row_members, texts, strict=True)):
            member = _as_stored(authored)
            table_rows = tables.get(member.table) or []
            locus = dict(member.conditions).get("variant_key")
            positions = (
                by_key.setdefault(member.table, _variant_key_index(table_rows)).get(locus, [])
                if locus is not None and member.table in LOCUS_TABLES
                else range(len(table_rows))
            )
            hits = [
                MetaMatch(position, member.table, k, _key(table_rows[k]))
                for k in positions
                if all(_condition_holds(table_rows[k], column, value) for column, value in member.conditions)
            ]
            if not hits:
                warnings.append(
                    CodedWarning("meta_selector_matches_nothing", _matches_nothing(index, text, member.table))
                )
            row_matches.extend(hits)
            reached = [table_rows[hit.index] for hit in hits]
            reached_tables = [member.table]
            if member.table == "allele_function" and len(row_members) == 1:
                diplotypes = tables.get("diplotypes") or []
                by_gene = by_gene_of.setdefault("diplotypes", _diplotypes_by_gene(diplotypes))
                contained = [
                    diplotypes[k] for target in reached for k in _contained(target, diplotypes, by_gene)
                ]
                reached += contained
                reached_tables += ["diplotypes"] if contained else []
            differing = _member_drug_disagrees(row, reached)
            if differing:
                warnings.append(
                    CodedWarning(
                        "meta_member_drug_disagrees",
                        _drug_disagrees(index, text, " and ".join(reached_tables), row.drug or "", differing),
                    )
                )
            if row.direction is not None and allele_bearing(member) is None:
                stated = [table_rows[hit.index].effect_allele for hit in hits]
                alleles = {allele.upper() for allele in stated if allele is not None}
                if not hits:
                    withheld.append("direction")
                elif len(alleles) != 1 or None in stated:
                    warnings.append(
                        CodedWarning(
                            "meta_member_allele_ambiguous",
                            _allele_ambiguous(index, text, [a for a in stated if a is not None]),
                        )
                    )
                    withheld.append("direction")
        all_members.append(row_members)
        all_texts.append(texts)
        all_matches.append(row_matches)
        all_withheld.append(sorted(set(withheld)))

    return MetaBuild(
        rows=rows,
        members=all_members,
        texts=all_texts,
        matches=all_matches,
        withheld=all_withheld,
        resolved=_resolve(rows, all_members, all_matches, tables, all_withheld),
        errors=errors,
        warnings=warnings,
    )


def meta_frame(build: MetaBuild, module_name: str) -> pl.DataFrame:
    """`meta.parquet`: one row per authored row, in authored order — every authored cell verbatim (what
    `reverse` writes back), the stamped key, and what the compile derived: the match count, the matches
    as `(member, table, key)` structs, whether the row replaces the findings it names, and `withheld`."""
    schema: dict[str, Any] = {"module": pl.Utf8}
    for name, field in MetaRow.model_fields.items():
        schema[name] = _polars_type(field.annotation)
    schema.update(
        {
            "match_count": pl.Int64,
            "matches": pl.List(_MATCH_STRUCT),
            "replaces": pl.Boolean,
            "withheld": pl.List(pl.Utf8),
        }
    )
    records = []
    for index, row in enumerate(build.rows):
        matches = [{"member": m.member, "table": m.table, "key": list(m.key)} for m in build.matches[index]]
        records.append(
            {
                "module": module_name,
                **{name: getattr(row, name) for name in MetaRow.model_fields},
                "match_count": len(matches),
                "matches": matches,
                # A matching combination replaces the single-locus findings it names (the maintainer,
                # 2026-11-04): exactly the rows in `matches`, so a consumer evaluates nothing (P1).
                "replaces": len(build.members[index]) > 1
                and any(getattr(row, c) for c in META_FINDING_COLUMNS),
                "withheld": build.withheld[index],
            }
        )
    return pl.DataFrame(records, schema=schema)


def meta_resolved_frame(build: MetaBuild, module_name: str) -> pl.DataFrame:
    """`meta_resolved.parquet`: one row per (single-statement row, sex, drug) a one-member row reaches.

    Sorted by member table (`META_MEMBER_TABLES` order), then the row's authored position in its table,
    then the sex scope (none, female, male), then the drug (none, then by name). `tradeoff` is RM327's
    verdict (`True` or null, never `False`). `meta_rows` are the 0-based `meta.parquet` rows that apply
    in the scope.
    """
    schema: dict[str, Any] = {
        "module": pl.Utf8,
        "table": pl.Utf8,
        "key": pl.List(pl.Utf8),
        "sex": pl.Utf8,
        "drug": pl.Utf8,
        **{name: _polars_type(MetaRow.model_fields[name].annotation) for name in META_FACT_COLUMNS},
        "tradeoff": pl.Boolean,
        "withheld": pl.List(pl.Utf8),
        "meta_rows": pl.List(pl.Int64),
    }
    records = [{"module": module_name, **record} for record in build.resolved]
    return pl.DataFrame(records, schema=schema)
