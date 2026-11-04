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
reaches, per `sex` scope, with each fact column (`tier`, `age_of_action`, `age_of_action_confidence`,
`flags`) after precedence and a `withheld` list naming the columns two incomparable, disagreeing rows
left unresolved. A row of two or more members states facts about the **combination**, so its facts stay
on its own `meta.parquet` row and never reach a member row by itself.

**`tradeoff` (RM327)** is computed there too, per allele-bearing **member** and never pooled across
members: `True` when one member has a `protective` per-trait row and a `risk` per-trait row (a
one-member row with `trait_efo_id` and a direction not withheld; a `mediator` row counts, since its
direction is still a benefit/harm judgement), and that verdict lands on every row the member reaches,
including the diplotypes an `allele_function` member reaches through the allele they carry. On one
trait at one row, the fact columns' precedence applies first, so a narrower judgement the author made
about that row (a diplotype member over the allele it contains, a genotype over its locus, a sex-scoped
row over the unscoped one) drops the broader judgement on that trait. A row two members reach is `True`
when either member is. **Never `False`**: RM327's false arm needs every trait's
judgement stated, and a module states no closed list of the traits an allele touches, so absence of an
opposing row is unknown, not a negative. Two alleles meeting at a heterozygous diplotype are two
members, so ε2 protective on one trait and ε4 risk on another is not a trade-off of either.
"""

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

from just_dna_compiler.compiler.tables import META_CSV, _polars_type

#: The order tables are expanded and `meta_resolved.parquet` is sorted in: `META_MEMBER_TABLES`' own.
_TABLE_ORDER: tuple[str, ...] = tuple(META_MEMBER_TABLES)

#: `None` (no sex scope) sorts first, then the scopes in name order.
_SEX_ORDER: dict[str | None, int] = {None: 0, "female": 1, "male": 2}

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
    return str(stored) == value


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

    A sex-scoped row outranks the same key without a sex (for that sex — only rows of the sex being
    resolved are candidates). A `diplotypes` member outranks an `allele_function` member reaching the
    same diplotype through one of its alleles: the narrower condition wins across tables (the
    maintainer, 2026-11-04). Otherwise the rank decides, between candidates reaching the same way.
    """
    ra, rb = rows[a.meta], rows[b.meta]
    if (
        ra.sex is not None
        and rb.sex is None
        and (ra.members_key, ra.trait_efo_id) == (rb.members_key, rb.trait_efo_id)
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
    """RM327's verdict for one `(target, sex)`: `True` when a member reaching it has both signs, else `None`.

    `applicable` is already the sex scope's candidates. A per-trait judgement is a candidate with a
    `trait_efo_id` and a `direction`; every member carrying one is allele-bearing, because `MetaRow`
    refuses a direction on any other member and a bare locus whose rows share no `effect_allele` has its
    direction withheld here.

    1. **Precedence per trait, as the fact columns take it** (`_outranks`): among the judgements on one
       trait at this target, one that a more specific judgement on the same trait outranks is dropped —
       a sex-scoped row over the same key unscoped, a `diplotypes` member over an allele it contains, a
       concrete row key over a locus. So an author's narrower statement about this row wins.
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
    """`meta_resolved.parquet`'s rows: each target a one-member row reaches, per sex scope, after precedence."""
    reach: dict[tuple[int, int], dict[int, _Candidate]] = {}

    def _keep(target: tuple[int, int], candidate: _Candidate) -> None:
        held = reach.setdefault(target, {})
        if candidate.meta not in held or candidate.rank > held[candidate.meta].rank:
            held[candidate.meta] = candidate

    diplotypes = tables.get("diplotypes") or []
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
            for position, diplotype in enumerate(diplotypes):
                if diplotype.gene == target.gene and target.allele in (
                    diplotype.haplotype_a,
                    diplotype.haplotype_b,
                ):
                    _keep((_TABLE_ORDER.index("diplotypes"), position), _Candidate(index, "contained", rank))

    resolved: list[dict[str, Any]] = []
    for table, position in sorted(reach):
        candidates = [reach[(table, position)][meta] for meta in sorted(reach[(table, position)])]
        name = _TABLE_ORDER[table]
        key = list(_key(tables[name][position]))
        scopes = sorted({rows[c.meta].sex for c in candidates}, key=lambda sex: _SEX_ORDER[sex])
        if None not in scopes:
            scopes = [None, *scopes]
        for sex in scopes:
            applicable = [c for c in candidates if rows[c.meta].sex in (None, sex)]
            if not applicable:
                continue
            record: dict[str, Any] = {"table": name, "key": key, "sex": sex}
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
    """`meta_resolved.parquet`: one row per (single-statement row, sex scope) a one-member row reaches.

    Sorted by member table (`META_MEMBER_TABLES` order), then the row's authored position in its table,
    then the scope (none, female, male). `tradeoff` is RM327's verdict (`True` or null, never `False`).
    `meta_rows` are the 0-based `meta.parquet` rows that reached it.
    """
    schema: dict[str, Any] = {
        "module": pl.Utf8,
        "table": pl.Utf8,
        "key": pl.List(pl.Utf8),
        "sex": pl.Utf8,
        **{name: _polars_type(MetaRow.model_fields[name].annotation) for name in META_FACT_COLUMNS},
        "tradeoff": pl.Boolean,
        "withheld": pl.List(pl.Utf8),
        "meta_rows": pl.List(pl.Int64),
    }
    records = [{"module": module_name, **record} for record in build.resolved]
    return pl.DataFrame(records, schema=schema)
