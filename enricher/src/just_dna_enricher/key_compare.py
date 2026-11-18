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
    member does. `rsid` (review round 1, item 5): the key is read as an rsID, lower case and `rs`
    prefixed (`RS334` and `334` are `rs334`), and compared with the whole cell exactly, which the snapshot
    stores in that spelling; only the key is read, so the registry's proxy compares it too when sent the
    key as read (`cell_exact`). A column a keyed function declares nothing for compares the whole cell
    exactly.
    """

    fold: bool = False
    separator: str | None = None
    rsid: bool = False

    @property
    def described(self) -> str:
        """How this compares, in words, for a message: `by gene_key`, `member by member of a ';'-joined
        cell`, both, or `exactly`."""
        parts = (
            (["by gene_key"] if self.fold else [])
            + (["as an rsID (`RS334` is `rs334`)"] if self.rsid else [])
            + (
                [f"member by member of a {self.separator!r}-joined cell"]
                if self.separator is not None
                else []
            )
        )
        return ", ".join(parts) or "exactly"

    @property
    def exact(self) -> bool:
        """Whether a key as given is compared with the whole cell, byte for byte: no reading on either side."""
        return self.cell_exact and not self.rsid

    @property
    def cell_exact(self) -> bool:
        """Whether the whole cell is compared byte for byte with the key as `key` reads it: what the
        registry's proxy compares, when it is sent each key as read (`parameter`)."""
        return not self.fold and self.separator is None

    def key(self, value: object) -> str:
        """`value` as this compare reads a key: `gene_key` when folded, as an rsID when `rsid`, else as given."""
        if self.fold:
            return gene_key(str(value))
        return _rsid_token(str(value)) if self.rsid else str(value)

    def members(self, cell: object) -> tuple[str, ...]:
        """The keys a stored `cell` answers to, in order, once each; none for an empty cell."""
        if cell is None:
            return ()
        text = str(cell)
        parts = text.split(self.separator) if self.separator is not None else [text]
        if self.separator is not None or self.fold or self.rsid:
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


def _rsid_token(rsid: str) -> str:
    """An rsID as the snapshots spell one: lower case, `rs` prefixed (`RS334` and `334` are `rs334`).

    The one spelling every keyed function reads an asked rsID in (CIViC's, ClinPGx's and ClinVar-GKM's,
    through `KeyCompare(rsid=True)`), and `ClinVarGkmWitness.by_rsid`'s reading."""
    token = rsid.strip().lower()
    return token if token.startswith("rs") else f"rs{token}"


#: The compare of a column a keyed function declares nothing for: the whole cell, exactly.
EXACT = KeyCompare()

#: A gene folded by `gene_key`, the whole cell (CIViC's, CPIC's).
_FOLDED = KeyCompare(fold=True)
#: A gene folded by `gene_key`, member by member of a `;`-joined cell (ClinPGx's `gene`, the labels' `genes`).
_FOLDED_MEMBERS = KeyCompare(fold=True, separator=";")
#: An rsID read as the snapshot spells one, the cell compared whole (CIViC's, ClinPGx's, ClinVar-GKM's `rsid`).
_RSID = KeyCompare(rsid=True)

#: lane -> table -> key column -> how it is compared, for every column a keyed function compares other
#: than exactly. A lane, table or column not here compares the whole cell exactly. Read by the keyed
#: functions' local SQL (`clinpgx`, `drug_labels`, `civic_draft`, `cpic`) and by the holder
#: (`remote.RemoteLane.compares`); a test holds each table name equal to its module's `REMOTE_*_TABLE` and
#: each separator to the module's own.
KEY_COMPARES: dict[str, dict[str, dict[str, KeyCompare]]] = {
    "clinpgx": {"annotations": {"gene": _FOLDED_MEMBERS, "rsid": _RSID}},
    "drug_labels": {"drug_labels": {"genes": _FOLDED_MEMBERS}},
    "civic": {"civic": {"gene": _FOLDED, "rsid": _RSID}},
    "clinvar_gkm": {"clinvar_gkm-indels": {"rsid": _RSID}},
    "cpic": {
        table: {"gene": _FOLDED}
        for table in ("genes", "alleles", "diplotypes", "recommendations", "allele_definitions")
    },
}


def lane_compare(lane: str, table: str, column: str) -> KeyCompare:
    """How `column` of `lane`'s `table` is compared with a key: its `KEY_COMPARES` entry, else `EXACT`."""
    return KEY_COMPARES.get(lane, {}).get(table, {}).get(column, EXACT)
