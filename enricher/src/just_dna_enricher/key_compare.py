"""How each keyed function compares a key with a cell, on every route (0.9, the RM430 follow-up).

The remote compare was not the local compare: the holder compared a whole cell exactly, so a gene in
another case, or inside a `;`-joined cell, answered locally and went missing remotely with nothing said
(the pm, 2026-11-18, fixed as a class). `KEY_COMPARES` is the one registry of those compares, by lane,
table and column. Each keyed function builds its local SQL from its entry, and `remote.RemoteLane.compares`
reads the same entry for the holder, so the two routes cannot compare apart. A leaf: it imports the
format normalizers and nothing of this package, so a reader, the holder and `clients` can all read
it without one importing the other.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from sys import maxunicode

from just_dna_format.spelling import drug_key, fold_chrom, gene_key
from just_dna_format.vrs import normalize_chrom


@dataclass(frozen=True)
class KeyCompare:
    """How a keyed function compares a key with a cell: the one declaration its local SQL and a remote
    route read (0.9, the RM430 follow-up: the remote compare is not the local compare).

    `fold`: compared by `spelling.gene_key`, so case and surrounding space do not make two keys
    (the SQL character mapping is derived from that function).
    `separator`: the cell holds several members joined by it (`KLC1;XRCC3`), and a key matches when any
    member does. `rsid` (review round 1, item 5): the key is read as an rsID, lower case and `rs`
    prefixed (`RS334` and `334` are `rs334`), and compared with the whole cell exactly, which the snapshot
    stores in that spelling; only the key is read, so the registry's proxy compares it too when sent the
    key as read (`cell_exact`). `normalize` reads a key for a column already stored in its comparison spelling.
    A column a keyed function declares nothing for compares the whole cell
    exactly.
    """

    fold: bool = False
    separator: str | None = None
    rsid: bool = False
    normalize: Callable[[str], str] | None = None

    @property
    def described(self) -> str:
        """How this compares, in words, for a message: `by gene_key`, `member by member of a ';'-joined
        cell`, both, or `exactly`."""
        parts = (
            (["by gene_key"] if self.fold else [])
            + (["as an rsID (`RS334` is `rs334`)"] if self.rsid else [])
            + (["with the key normalized"] if self.normalize is not None else [])
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
        return self.cell_exact and not self.rsid and self.normalize is None

    @property
    def cell_exact(self) -> bool:
        """Whether the whole cell is compared byte for byte with the key as `key` reads it: what the
        registry's proxy compares, when it is sent each key as read (`parameter`)."""
        return not self.fold and self.separator is None

    def key(self, value: object) -> str:
        """Read a stated key using the declared gene, rsID or column-specific normalization."""
        if self.fold:
            return gene_key(str(value))
        if self.normalize is not None:
            return self.normalize(str(value))
        return _rsid_token(str(value)) if self.rsid else str(value)

    def members(self, cell: object) -> tuple[str, ...]:
        """The keys a stored `cell` answers to, in order, once each; none for an empty cell."""
        if cell is None:
            return ()
        text = str(cell)
        parts = text.split(self.separator) if self.separator is not None else [text]
        if not self.exact:
            parts = [part for part in parts if part.strip()]
        return tuple(dict.fromkeys(self.key(part) for part in parts))

    def predicate(self, column: str, *, negated: bool = False) -> str:
        """SQL true where `column`'s cell answers to any key in one bound `VARCHAR[]` parameter (with
        `negated`, true where a stated cell answers to none). A `NULL` cell matches neither way, as SQL's
        `lower(gene) <> ?` read it before this predicate: an unstated cell is no key and no other key."""
        cell = f'CAST("{column}" AS VARCHAR)'
        member = cell if self.separator is None else "member"
        if self.fold:
            member = _gene_sql(member)
        if self.separator is None:
            # A gene panel may ask for thousands of symbols. IN hashes the probe set.
            test = f"{member} IN (SELECT unnest(?::VARCHAR[]))"
        else:
            split = f"string_split({cell}, '{self.separator.replace(chr(39), chr(39) * 2)}')"
            test = f"list_has_any(list_transform({split}, member -> {member}), ?::VARCHAR[])"
        return f"({cell} IS NOT NULL AND NOT ({test}))" if negated else test

    def spellings(self, values: Sequence[str]) -> dict[str, list[str]]:
        """Map each comparison key to its distinct requested spellings, keeping their input order."""
        asked: dict[str, list[str]] = {}
        for value in dict.fromkeys(values):
            if value and value.strip():
                asked.setdefault(self.key(value), []).append(value)
        return asked

    def parameter(self, values: Sequence[object]) -> list[str]:
        """The bound `VARCHAR[]` for `values` under this compare, sorted and once each."""
        return sorted({self.key(value) for value in values if value is not None and str(value).strip()})


@cache
def _gene_alphabet() -> tuple[str, str]:
    """SQL literals for gene_key's trim characters and character folds, from this Python's Unicode data.

    Case folding maps one code point to a string, independently of its neighbours. A whitespace
    character trims at the ends but stays verbatim inside a name, so it is absent from the fold map.
    """
    whitespace: list[str] = []
    folds: dict[str, str] = {}
    for point in range(maxunicode + 1):
        char = chr(point)
        key = gene_key(char)
        if not key:
            whitespace.append(char)
        elif key != char:
            folds[char] = key

    def literal(text: str) -> str:
        return "'" + text.replace("'", "''") + "'"

    # Each source is a single character. Folded values may have several (ß → ss).
    sources = literal("".join(folds))
    # No case fold introduces a line break. Two strings keep the SQL parser from building
    # a separate expression for every code point on every query.
    values = literal("\n".join(folds.values()))
    return literal("".join(whitespace)), f"map(string_split({sources}, ''), string_split({values}, chr(10)))"


def _gene_sql(cell: str) -> str:
    """A standalone DuckDB expression for gene_key, including Python whitespace and Unicode casefold."""
    whitespace, folds = _gene_alphabet()
    trimmed = f"trim({cell}, {whitespace})"
    # Gene symbols are normally ASCII. Keep the per-character lookup for the exceptional row.
    letters = f"string_split({trimmed}, '')"
    folded = f"list_transform({letters}, ch -> coalesce(list_extract(map_extract({folds}, ch), 1), ch))"
    return f"CASE WHEN strlen({cell}) = length({cell}) THEN lower({trimmed}) ELSE array_to_string({folded}, '') END"


def _contig(value: str) -> str:
    """Fold a primary contig and preserve a scaffold's own identifier."""
    return fold_chrom(value) or value


def _bare_contig(value: str) -> str:
    """Read a contig on a snapshot that stores all its contigs without the chr prefix."""
    return normalize_chrom(value) or ""


def _witness_contig(chrom: str) -> str:
    """The ClinVar-GkM witness stores contig names in upper case."""
    token = chrom.strip()
    if token[:3].lower() == "chr":
        token = token[3:]
    token = token.upper()
    return "MT" if token == "M" else token


def _ensembl_id(value: str) -> str:
    """Read rsIDs as rsIDs, leaving other Ensembl identifiers (such as COSV IDs) verbatim."""
    token = _rsid_token(value)
    return token if token[2:].isascii() and token[2:].isdigit() else value


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

_CHROM = KeyCompare(normalize=_contig)
_BARE_CHROM = KeyCompare(normalize=_bare_contig)

#: Snapshot lookup keys by lane, payload table and column. The remote holder reads the
#: same declarations for the subset of these keys supported by its protocol.
KEY_COMPARES: dict[str, dict[str, dict[str, KeyCompare]]] = {
    "ensembl": {"homo_sapiens": {"id": KeyCompare(normalize=_ensembl_id), "chrom": _CHROM, "start": EXACT}},
    "clinvar": {
        "clinvar": {
            "rsid": _RSID,
            "chrom": _CHROM,
            "start": EXACT,
            "ref": EXACT,
            "alt": EXACT,
            "gene": _FOLDED,
        },
        "citations": {"variation_id": EXACT},
    },
    "constraint": {"gnomad_constraint": {"gene": _FOLDED}},
    "mane": {"summary": {"symbol": _FOLDED}},
    "pharmvar": {"alleles": {"gene": _FOLDED}, "variants": {"gene": _FOLDED}},
    "pubmind": {"pubmind": {"chrom": _BARE_CHROM, "start": EXACT, "ref": EXACT, "alt": EXACT}},
    "opentargets": {
        "variants": {"chrom": _BARE_CHROM, "position": EXACT, "ref": EXACT, "alt": EXACT},
        "consequences": {"variant_id": KeyCompare(normalize=str.strip)},
        "credible_set_members": {"variant_id": KeyCompare(normalize=str.strip)},
    },
    "clinpgx": {"annotations": {"gene": _FOLDED_MEMBERS, "rsid": _RSID}},
    "drug_labels": {"drug_labels": {"genes": _FOLDED_MEMBERS}},
    "civic": {"civic": {"gene": _FOLDED, "rsid": _RSID}},
    "clinvar_gkm": {
        "clinvar_gkm-indels": {"rsid": _RSID, "chrom": KeyCompare(normalize=_witness_contig), "pos": EXACT}
    },
    "cpic": {
        **{table: {"gene": _FOLDED} for table in ("genes", "alleles", "diplotypes", "allele_definitions")},
        "recommendations": {"gene": _FOLDED, "drug": KeyCompare(normalize=drug_key)},
    },
}


def lane_compare(lane: str, table: str, column: str) -> KeyCompare:
    """How `column` of `lane`'s `table` is compared with a key: its `KEY_COMPARES` entry, else `EXACT`."""
    return KEY_COMPARES.get(lane, {}).get(table, {}).get(column, EXACT)
