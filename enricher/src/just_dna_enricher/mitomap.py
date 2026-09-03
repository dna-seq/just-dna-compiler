"""MITOMAP's published `pg_dump`, and the grammar its `status` column is written in (RM171).

The source is one 63 MB gzipped SQL dump with 6.7 million lines and no licence text inside it. Two of
its tables are curated mtDNA disease-variant catalogues — `mmutation` (602 rows, protein-coding and
control region) and `rtmutation` (494 rows, rRNA and tRNA) — with the same fourteen-ish columns and
the same `status` column, and the repository's one mtDNA module draws from the *second* of them.

**`status` is two tokens and a prose tail, and only one of the two tokens is mappable.** A
confirmation token (`Reported`, `Cfrm`, `Conflicting reports`, and `Unclear` in the sibling) followed
by an optional bracketed rating (`[P]`, `[LP]`, `[VUS]`, `[LB]`, `[B]`). MITOMAP legends both, and the
legend for the first says in as many words that it is *not* an assignment of pathogenicity — it is a
literature-count criterion. So the confirmation token never reaches `normalize_clin_sig`, and mapping
`Cfrm` onto `pathogenic` would write a judgement the source explicitly declines to make. The bracket
is somebody else's instrument entirely: the ClinGen mtDNA VCEP's five-class rating, scored per
McCormick 2020, over exactly the classes `VALID_CLIN_SIG` already carries. That half is a
normalization, and it goes through the one shared normalizer rather than a second map here
(`@one-normalizer-two-spellings`).

**`[VUS*]` is withheld, and the withhold is the considered position rather than a gap.** A tenth of
the bracketed `mmutation` rows write the star, and 13 more in `rtmutation` do. It is not the legend's
footnote marker (that is a diamond, printed inside the bracket), it is not one of the five documented
classes, and it is not APOGEE's `[VUS+]`/`[VUS-]`, which leak into `rtmutation` on one row each from a
seven-tier in-silico predictor that happens to share three letters. Nobody wrote down what it means.
So `vcep_clin_sig` answers `None` for it and every other unlisted bracket, and the count of what was
withheld is carried rather than folded into `VUS`. Collapsing the star would invent a meaning; and it
cannot be left to the normalizer's own default, because that default is `other`, a *definite* member
of the vocabulary rather than an unknown (`@lookup-with-a-default-hides-a-new-member`).

**The `:` deletions mint no identity here and that is Principle 2, not an oversight.** MITOMAP spells
a deletion right-anchored, `refna="TA"` against `regna=":"`, which needs an rCRS base at
`position - 1` to become a VCF allele — and this tier does not fetch a reference sequence. They are
counted as unmintable, by reason, and never guessed at.
"""

import gzip
import logging
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from just_dna_enricher.clin_sig import normalize_clin_sig

logger = logging.getLogger(__name__)

#: The licensed source name, as `SourceRow.source` spells it and as `licensing.MITOMAP_TERMS` does.
SOURCE_NAME = "mitomap"

#: The dump tables this tier reads. Named as a constant rather than typed at three call sites,
#: because a negative finding about "the source" is only as wide as the table it was measured on
#: (`@probe-names-the-table`) and the snapshot has to be able to say which tables it holds.
#:
#: Both variant tables, deliberately. `reference_examples/mt_heteroplasmy` carries two variants and
#: both live in `rtmutation`; neither is in `mmutation`. An `mmutation`-only lane would draft nothing
#: the one existing mtDNA module needs, and shipping one table and finding the sibling later is
#: exactly how RM164 happened.
VARIANT_TABLES: tuple[str, ...] = ("mmutation", "rtmutation")
#: The link tables joining a variant row to `reference`, one per variant table and named the same way.
LINK_TABLES: dict[str, str] = {name: f"{name}_reference" for name in VARIANT_TABLES}
#: The citation table both link tables point into, and the per-table curation dates the dump carries
#: in band. `edit_date` is the only statement inside these bytes about when each table was last
#: touched; `Last-Modified` on the download is a fact about the *file*, and the two answer different
#: questions, so both are recorded.
REFERENCE_TABLE = "reference"
EDIT_DATE_TABLE = "edit_date"

#: Every table `read_dump_tables` is asked for by the builder. Derived from the four above so a new
#: variant table brings its link table with it rather than being added to a second list.
DUMP_TABLES: tuple[str, ...] = (
    *VARIANT_TABLES, *LINK_TABLES.values(), REFERENCE_TABLE, EDIT_DATE_TABLE,
)

#: `edit_date.table_name` for each variant table. The dump abbreviates (`mMut`, `rtMut`), so this is a
#: translation of the source's own spelling and not a naming convention that can be derived.
EDIT_DATE_NAMES: dict[str, str] = {"mmutation": "mMut", "rtmutation": "rtMut"}

#: The ClinGen mtDNA VCEP classes MITOMAP's bracket may carry, as MITOMAP abbreviates them. The five
#: the legend documents, and nothing else — the membership test is what keeps `[VUS*]`, `[VUS+]` and
#: `[VUS-]` out of `clin_sig`.
MITOMAP_VCEP_CLASSES: frozenset[str] = frozenset({"P", "LP", "VUS", "LB", "B"})

#: MITOMAP's own confirmation tokens, longest first so `Conflicting reports` is not read as a prefix
#: match failure. **None of these maps onto `clin_sig`**: the legend states that the token counts
#: independent literature reports and is not an assignment of pathogenicity. `Unclear` is
#: `rtmutation`'s fourth member and is absent from `mmutation`.
MITOMAP_CONFIRMATION_TOKENS: tuple[str, ...] = ("Conflicting reports", "Reported", "Cfrm", "Unclear")

#: Why a row's published alleles cannot be spelled as a VCF `(ref, alt)` pair. Named rather than
#: counted anonymously, because each sends a reader somewhere different: the first needs an rCRS base
#: this tier may not fetch, the second is prose in an allele column, the third is not an event.
ALLELE_DEFECTS: tuple[str, ...] = (
    "right_anchored_deletion",  # regna is ":" — the VCF form needs the base at position-1
    "non_nucleotide",           # "24bp_deletion", or an absent cell
    "ref_equals_alt",           # no event to key
)

_BRACKET = re.compile(r"\[([^\]]*)\]")
_NUCLEOTIDES = re.compile(r"^[ACGT]+$")
#: A PMID is a bare run of digits and **nothing else** in the cell. Deliberately stricter than
#: `spec.extract_pmids`, which pulls a digit run out of free text: MITOMAP's `reference.nlmid` holds
#: one identifier per cell, and the one cell in 6,770 that is not a PMID
#: (`01930224-202601000-00006`, an Ovid article id) starts with eight digits that a substring search
#: would happily cite as somebody else's paper (`@pmid-vs-pmcid` is the same failure one registry
#: over).
_PMID = re.compile(r"^[0-9]{1,8}$")


class MitomapError(RuntimeError):
    """A MITOMAP dump could not be read, or a snapshot could not be built from one."""


class MitomapUnavailable(MitomapError):
    """The dump could not be fetched. A *pass*, not a defect in the bytes.

    Its own subclass because a caller's recovery differs: an unreadable dump on disk is something to
    fix, while a download that did not answer is something to retry or to route around with a local
    copy (`@client-exception-contract`).
    """


# ── the dump ────────────────────────────────────────────────────────────────────────────────────

#: Postgres' COPY text escapes. `\\N` is the null marker and is handled before this map is consulted,
#: because it is a whole-field sentinel rather than a character escape.
_COPY_ESCAPES = {
    "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "\\": "\\",
}


def _unescape(field: str) -> str | None:
    """One COPY text field → its value, or `None` for the null marker.

    Written out rather than delegated to a SQL parser, because the whole point of reading the dump
    directly is that this tier does not take a database dependency to read four tables out of it.
    """
    if field == "\\N":
        return None
    if "\\" not in field:
        return field
    out: list[str] = []
    index = 0
    while index < len(field):
        char = field[index]
        if char == "\\" and index + 1 < len(field) and field[index + 1] in _COPY_ESCAPES:
            out.append(_COPY_ESCAPES[field[index + 1]])
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _copy_header(line: str) -> tuple[str, list[str]] | None:
    """`COPY mitomap.mmutation (id, locus, …) FROM stdin;` → `("mmutation", [columns])`."""
    if not line.startswith("COPY mitomap."):
        return None
    head = line[len("COPY mitomap."):]
    name, _, rest = head.partition(" ")
    if "(" not in rest:
        return None
    columns = [c.strip().strip('"') for c in rest.split("(", 1)[1].split(")")[0].split(",")]
    return name, columns


def read_dump_tables(
    dump: Path, wanted: Iterable[str] = DUMP_TABLES
) -> dict[str, list[dict[str, str | None]]]:
    """Stream a MITOMAP `pg_dump` and return the named tables as lists of row dicts.

    One pass over the gzip stream, keeping only the tables asked for — the dump is 6.76 million lines
    and the six this tier wants are about 14,000 of them, so the alternative (parse everything, filter
    after) would hold the whole database in memory to answer a question about 0.2% of it.

    A table named in `wanted` that the dump does not contain is **reported by its absence from the
    result**, never as an empty list: an empty table and a table the dump stopped publishing are
    different facts, and the caller refuses on the second (`@unreachable-not-absent`).
    """
    dump = Path(dump)
    if not dump.is_file():
        raise MitomapError(f"no MITOMAP dump at {dump}")
    targets = set(wanted)
    out: dict[str, list[dict[str, str | None]]] = {}
    current: str | None = None
    columns: list[str] = []
    try:
        with gzip.open(dump, "rt", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if current is not None:
                    if line.startswith("\\."):
                        current = None
                        continue
                    values = [_unescape(v) for v in line.rstrip("\n").split("\t")]
                    out[current].append(dict(zip(columns, values, strict=False)))
                    continue
                header = _copy_header(line)
                if header is not None and header[0] in targets:
                    current, columns = header
                    out[current] = []
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise MitomapError(f"could not read the MITOMAP dump at {dump}: {exc}") from exc
    return out


# ── the status grammar ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MitomapStatus:
    """One `status` cell, split into the three things it can carry.

    `confirmation` is MITOMAP's own literature-count token and `bracket` is the ClinGen VCEP's rating;
    they sit on different axes and only the second is ever mapped. `qualifier` is whatever prose the
    cell carries beyond the two — 34 of 602 `mmutation` rows have some — and it is **kept verbatim
    rather than dropped**, because the informative groups in it are a statement about a genotype
    (`in combo with …`) or about identity (`alt locus at 9487del15`), and both are things the author
    reading a drafted row needs to see.
    """

    raw: str
    confirmation: str | None
    bracket: str | None
    qualifier: str | None

    @property
    def rated(self) -> bool:
        """Whether the bracket is one of the five documented VCEP classes."""
        return self.bracket in MITOMAP_VCEP_CLASSES


def parse_status(raw: str | None) -> MitomapStatus:
    """Split a `status` cell into confirmation token, bracketed rating and prose residue.

    The bracket is taken wherever it appears, including on the two rows whose confirmation token is
    replaced by an alternative-alignment note (`alt loc to 9480del15 [LP]`). That is deliberate: the
    bracket is the VCEP's call about the allele, the note is MITOMAP's caveat about which alignment
    the allele is written in, and dropping a published classification because the row also carries a
    caveat would be reading the caveat as a retraction. The caveat travels as `qualifier` instead.
    """
    text = (raw or "").strip()
    if not text:
        return MitomapStatus(raw="", confirmation=None, bracket=None, qualifier=None)
    match = _BRACKET.search(text)
    bracket = match.group(1).strip() if match else None
    residue = (text[: match.start()] + " " + text[match.end():]) if match else text
    confirmation = None
    for token in MITOMAP_CONFIRMATION_TOKENS:
        if residue.strip().startswith(token):
            confirmation = token
            residue = residue.strip()[len(token):]
            break
    qualifier = residue.strip(" -/;,:") or None
    return MitomapStatus(
        raw=text, confirmation=confirmation, bracket=bracket or None, qualifier=qualifier
    )


def vcep_clin_sig(status: MitomapStatus) -> str | None:
    """The row's `clin_sig`, or `None` where MITOMAP published no class this tier may map.

    Three-valued by construction and the middle case is the one that matters: a row with no bracket
    said nothing, a row with `[VUS*]` said something nobody has defined, and both withhold. Only a
    bracket in `MITOMAP_VCEP_CLASSES` reaches `normalize_clin_sig`, so the normalizer's `other`
    default can never turn an undocumented token into a definite call.

    The confirmation token is never consulted here, and that is the point rather than an omission.
    """
    if not status.rated:
        return None
    return normalize_clin_sig(status.bracket)


def withheld_bracket(status: MitomapStatus) -> str | None:
    """The bracket this row carries that is *not* a documented class, for counting.

    `[VUS*]` on both tables, `[VUS+]`/`[VUS-]` on one `rtmutation` row each. Returned rather than
    tallied internally, so the count lands in the snapshot's own provenance instead of a log line
    nobody reads (`@dont-discard-computed`).
    """
    if status.bracket is None or status.rated:
        return None
    return status.bracket


# ── alleles and citations ───────────────────────────────────────────────────────────────────────


def allele_defect(refna: str | None, regna: str | None) -> str | None:
    """Why this row's alleles cannot be spelled as VCF `(ref, alt)`, or `None` when they can.

    One predicate with two callers — the miss build and the drafter — because a second copy is the one
    about to disagree, and the number of rows an adoption *cannot* reach is a published figure rather
    than an implementation detail.
    """
    ref = (refna or "").strip().upper()
    alt = (regna or "").strip().upper()
    if alt == ":" or ref == ":":
        return "right_anchored_deletion"
    if not _NUCLEOTIDES.match(ref) or not _NUCLEOTIDES.match(alt):
        return "non_nucleotide"
    if ref == alt:
        return "ref_equals_alt"
    return None


def allele_key(position: str | int | None, refna: str | None, regna: str | None) -> tuple | None:
    """The join key `(start, ref, alt)`, upper-cased, or `None` where the alleles do not spell one.

    `chrom` is not in it: both sides of this join are chrMT by construction, and a constant in a key
    is a column that can only ever be right. The caller states the contig once, where the frame is
    built.
    """
    if allele_defect(refna, regna) is not None or position is None:
        return None
    try:
        start = int(str(position).strip())
    except ValueError:
        return None
    return start, (refna or "").strip().upper(), (regna or "").strip().upper()


def nlmid_pmid(value: str | None) -> str | None:
    """`reference.nlmid` as a PMID, or `None` where the cell holds something else.

    **The whole column was walked before this lane claimed to carry every citation**, which the
    strategy note left owed on a sample of four: of 6,770 reference rows, 397 state no `nlmid` at all
    and one states `01930224-202601000-00006`, an Ovid article id. Every other populated cell is a
    bare run of five to eight digits. That is a *shape* result and not an existence one — whether each
    of those digits names a real PubMed record is a network question this tier does not ask here.
    """
    text = (value or "").strip()
    if not text or not _PMID.match(text):
        return None
    return text


#: An `allele` name that states a variable number of copies — MITOMAP writes `(n)`, as in
#: `T961delT+ / -C(n)ins`. Exactly one row in the two tables does today, and it is the shape rather
#: than the count that matters: the source's own two encodings of that record disagree about
#: definiteness, since the allele *columns* flatten it to a single `T`→`CC`.
_INDEFINITE_LENGTH = re.compile(r"\(n\)", re.IGNORECASE)


def indefinite_length(allele: str | None) -> bool:
    """Whether the `allele` name describes a variable-length event the allele columns cannot state.

    **Reported, never repaired** (`@multiplicity-is-a-finding`). The row keeps MITOMAP's own
    `(refna, regna)` — dropping it would discard a published call, and rewriting it would need a rule
    for what `(n)` means that MITOMAP has not given. What a caller does with this is warn, on a row
    the author has to curate by hand anyway.
    """
    return bool(_INDEFINITE_LENGTH.search(allele or ""))


def single_gene(locus: str | None) -> str | None:
    """`locus` as a gene symbol, or `None` where the cell names something that is not one gene.

    Three shapes are refused and each for its own reason. `MT-ATP8/6` is two overlapping genes, and
    picking one would state a gene attribution MITOMAP did not make. `MT-CR` is the control region —
    a named locus, not a gene, and `VariantRow.gene` is a gene column. `MT-TS1 precursor` names a
    transcript stage rather than the gene alone. Withholding is free here: `gene` is optional on the
    row, and a wrong symbol is worse than an absent one (`@refutation-withholds`).
    """
    text = (locus or "").strip()
    if not text or "/" in text or " " in text:
        return None
    if text.upper() in {"MT-CR", "MT-NC", "NONCODING"}:
        return None
    return text


def variant_rows(
    tables: dict[str, list[dict[str, str | None]]]
) -> Iterator[tuple[str, dict[str, str | None]]]:
    """Every curated variant row across the tables that are present, tagged with its table name.

    The table name travels with the row all the way into the snapshot, so a finding about MITOMAP is
    always a finding about a named table (`@probe-names-the-table`) and a reader can tell an
    `mmutation` claim from an `rtmutation` one without re-deriving it from the locus.
    """
    for table in VARIANT_TABLES:
        for row in tables.get(table, []):
            yield table, row
