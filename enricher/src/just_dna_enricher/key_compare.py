"""How each keyed function compares a key with a cell, on every route (0.9, the RM430 follow-up).

The remote compare was not the local compare: the holder compared a whole cell exactly, so a gene in
another case, or inside a `;`-joined cell, answered locally and went missing remotely with nothing said
(the pm, 2026-11-18, fixed as a class). `KEY_COMPARES` is the one registry of those compares, by lane,
table and column. Each keyed function builds its local SQL from its entry, and `remote.RemoteLane.compares`
reads the same entry for the holder, so the two routes cannot compare apart. A leaf: it imports the
format tier's `gene_key` and nothing of this package, so a reader, the holder and `clients` can all read
it without one importing the other.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from just_dna_format.spelling import gene_key


@dataclass(frozen=True)
class KeyCompare:
    """How a keyed function compares a key with a cell: the one declaration its local SQL and a remote
    route read (0.9, the RM430 follow-up: the remote compare is not the local compare).

    `fold`: compared by `spelling.gene_key`, so case and surrounding space do not make two keys
    (`lower(trim(…))` in SQL, which is `gene_key` for the ASCII an HGNC symbol is spelled in).
    `separator`: the cell holds several members joined by it (`KLC1;XRCC3`), and a key matches when any
    member does. A column a keyed function declares nothing for compares the whole cell exactly.
    """

    fold: bool = False
    separator: str | None = None

    @property
    def described(self) -> str:
        """How this compares, in words, for a message: `by gene_key`, `member by member of a ';'-joined
        cell`, both, or `exactly`."""
        parts = (["by gene_key"] if self.fold else []) + (
            [f"member by member of a {self.separator!r}-joined cell"] if self.separator is not None else []
        )
        return ", ".join(parts) or "exactly"

    @property
    def exact(self) -> bool:
        """Whether this is the whole cell, compared byte for byte: what the registry's proxy compares."""
        return not self.fold and self.separator is None

    def key(self, value: object) -> str:
        """`value` as this compare reads a key: `gene_key` when folded, else the text as given."""
        return gene_key(str(value)) if self.fold else str(value)

    def members(self, cell: object) -> tuple[str, ...]:
        """The keys a stored `cell` answers to, in order, once each; none for an empty cell."""
        if cell is None:
            return ()
        text = str(cell)
        parts = text.split(self.separator) if self.separator is not None else [text]
        if self.separator is not None or self.fold:
            parts = [part for part in parts if part.strip()]
        return tuple(dict.fromkeys(self.key(part) for part in parts))

    def predicate(self, column: str, *, negated: bool = False) -> str:
        """SQL true where `column`'s cell answers to any key in one bound `VARCHAR[]` parameter (with
        `negated`, true where a stated cell answers to none). A `NULL` cell matches neither way, as SQL's
        `lower(gene) <> ?` read it before this predicate: an unstated cell is no key and no other key."""
        cell = f'CAST("{column}" AS VARCHAR)'
        member = "lower(trim(member))" if self.fold else "member"
        if self.separator is None:
            test = f"list_contains(?::VARCHAR[], {member.replace('member', cell)})"
        else:
            split = f"string_split({cell}, '{self.separator.replace(chr(39), chr(39) * 2)}')"
            test = f"list_has_any(list_transform({split}, member -> {member}), ?::VARCHAR[])"
        return f"coalesce(NOT ({test}), false)" if negated else test

    def parameter(self, values: Sequence[object]) -> list[str]:
        """The bound `VARCHAR[]` for `values` under this compare, sorted and once each."""
        return sorted({self.key(value) for value in values if str(value).strip()})


#: The compare of a column a keyed function declares nothing for: the whole cell, exactly.
EXACT = KeyCompare()

#: A gene folded by `gene_key`, the whole cell (CIViC's, CPIC's).
_FOLDED = KeyCompare(fold=True)
#: A gene folded by `gene_key`, member by member of a `;`-joined cell (ClinPGx's `gene`, the labels' `genes`).
_FOLDED_MEMBERS = KeyCompare(fold=True, separator=";")

#: lane -> table -> key column -> how it is compared, for every column a keyed function compares other
#: than exactly. A lane, table or column not here compares the whole cell exactly. Read by the keyed
#: functions' local SQL (`clinpgx`, `drug_labels`, `civic_draft`, `cpic`) and by the holder
#: (`remote.RemoteLane.compares`); a test holds each table name equal to its module's `REMOTE_*_TABLE` and
#: each separator to the module's own.
KEY_COMPARES: dict[str, dict[str, dict[str, KeyCompare]]] = {
    "clinpgx": {"annotations": {"gene": _FOLDED_MEMBERS}},
    "drug_labels": {"drug_labels": {"genes": _FOLDED_MEMBERS}},
    "civic": {"civic": {"gene": _FOLDED}},
    "cpic": {
        table: {"gene": _FOLDED}
        for table in ("genes", "alleles", "diplotypes", "recommendations", "allele_definitions")
    },
}


def lane_compare(lane: str, table: str, column: str) -> KeyCompare:
    """How `column` of `lane`'s `table` is compared with a key: its `KEY_COMPARES` entry, else `EXACT`."""
    return KEY_COMPARES.get(lane, {}).get(table, {}).get(column, EXACT)
