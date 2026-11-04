"""CPIC's deletion, insertion and repeat-count notation, spelled as a VCF caller spells it (RM253).

CPIC's `variantallele` column carries three notations beside plain bases: `DEL<bases>` (`DELTCT`),
`INS<bases>` (`INSCGGG`) and a repeat count `UNIT(n)` (UGT1A1's `TA(8)`). None is a nucleotide string,
so the drafter skipped every one, and UGT1A1 `*28`, the allele the atazanavir and irinotecan labels key
on, shipped undefined.

**The spelling is the one callers write (decided 2026-11-04 on measured VCFs).** DeepVariant, DRAGEN,
GATK, Clair3 and the imputation servers all write `*28` as the ordinary indel `C>CAT` at GRCh38
`2:233760233`, VCF-anchored and left-normalized; none writes a symbolic allele or a repeat count there.
So each notation becomes an anchored REF/ALT pair, left-aligned with the same `_left_align` the CIViC
drafter uses (RM273), and a module keys the spelling a caller emits.

**Where CPIC's position sits, measured on the snapshot against the reference:**

* `DEL<bases>` — the position is the **first deleted base**: every such row's bases match the
  reference starting there. The anchor is the base before it.
* `INS<bases>` — the position is the **base the insertion follows**: NUDT15 `*14` (`INSCGGG` at
  `13:48037826`) is Ensembl's `48037826 G>GCGGG`, and TPMT `*42` (`INST` at `6:18149032`) left-aligns
  to the same event Ensembl writes one base right.
* `UNIT(n)` — the position is the **first base of the run**; the reference count is read from the
  reference, never assumed, and the count CPIC gives its reference allele agrees with it at every
  repeat locus in the snapshot.

**A `DEL` paired with an `INS` at one locus is a delins.** RYR1 writes `c.13994_13995delTCinsCT` as
`DELTC` on its `Reference` allele and `INSCT` on the variant. Read one row at a time, the reference
allele would be spelled as a deletion it does not carry; read by locus, the pair is the substitution
`TC>CT` (Ensembl calls rs193922862 exactly that) and the `DEL` half is the reference state.

**What it will not do.** It never guesses a base it could not read: an unreadable reference (offline,
an unreachable service, a contig with no refget accession) withholds the row with its reason, and so
does a reference that does not carry what the notation says. A bare `DEL` states no bases and stays
skipped, as decided. A value listing alternatives (`GAGTCG(3) OR GAGTCG(4)`) is an uncertainty CPIC
recorded, the same kind of statement as an IUPAC code, and stays skipped too.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from just_dna_enricher.sequences import _left_align

#: `read_window(chrom, start, end)` → the reference bases over 1-based inclusive `[start, end]`, or
#: `None`. The shape `_left_align` reads, so one reader serves both.
ReadWindow = Callable[[str, int, int], str | None]

_DELETION = re.compile(r"^DEL([ACGT]+)$")
_INSERTION = re.compile(r"^INS([ACGT]+)$")
_REPEAT = re.compile(r"^([ACGT]+)\((\d+)\)$")
#: CPIC lists alternatives with `OR` (`GAGTCG(3) OR GAGTCG(4)`) or `;` (MT-RNR1's `DELINSCC; DELINSCCC`).
_ALTERNATIVES = re.compile(r"\sOR\s|;")
#: How far right a repeat run is read before the count is withheld (bases). A run longer than this is
#: far longer than any run CPIC writes, and a count clipped by the window would be a wrong count.
_RUN_WINDOW = 160

#: Why a notation was not spelled. Every member has a sentence in `NOT_SPELLED_EXPLANATION`; a test
#: asserts the two key sets are equal, so a new reason cannot reach a warning as a `KeyError`.
NOT_SPELLED_REASONS: frozenset[str] = frozenset(
    {"lengthless_deletion", "alternatives", "unrecognized", "reference_unreadable", "reference_disagrees"}
)

NOT_SPELLED_EXPLANATION: dict[str, str] = {
    "lengthless_deletion": (
        "a bare `DEL`, which names no bases and so has nothing to spell; it stays skipped by the RM253 "
        "decision"
    ),
    "alternatives": (
        "alternatives (`X OR Y`, or a `;`-separated list) — an uncertainty CPIC recorded, like an IUPAC "
        "code, and spelling one of them would state a definition CPIC did not"
    ),
    "unrecognized": "a notation that is neither `DEL<bases>`, `INS<bases>` nor `UNIT(n)`",
    "reference_unreadable": (
        "a notation that needs reference bases to spell (the anchor, or the run to count), and the "
        "reference could not be read this run (offline, an unreachable sequence service, or a contig "
        "with no refget accession) — withheld rather than guessed; re-run with sequence access"
    ),
    "reference_disagrees": (
        "a notation the GRCh38 reference does not bear out at CPIC's position (the deleted bases are "
        "not there, or the repeat run does not start there) — withheld, since spelling it would "
        "invent an event"
    ),
}


@dataclass(frozen=True)
class Notation:
    """One parsed CPIC notation. `count` is set for a repeat only."""

    kind: str  # "deletion" | "insertion" | "repeat"
    bases: str  # the deleted or inserted bases, or the repeat unit
    count: int | None = None


@dataclass(frozen=True)
class Spelled:
    """A VCF-anchored, left-normalized allele. `ref == alt` is the reference state at that locus."""

    chrom: str
    start: int
    ref: str
    alt: str

    @property
    def is_reference(self) -> bool:
        return self.ref == self.alt


def parse_notation(value: str) -> Notation | str:
    """A CPIC notation → its `Notation`, or the reason it has none (a `NOT_SPELLED_REASONS` member)."""
    value = value.strip().upper()
    if value == "DEL":
        return "lengthless_deletion"
    if _ALTERNATIVES.search(value):
        return "alternatives"
    if m := _DELETION.match(value):
        return Notation("deletion", m[1])
    if m := _INSERTION.match(value):
        return Notation("insertion", m[1])
    if m := _REPEAT.match(value):
        return Notation("repeat", m[1], int(m[2]))
    return "unrecognized"


def delins_partner(entries: list[tuple[str, str]], reference_names: frozenset[str]) -> str | None:
    """The reference bases of a delins site, or `None` when the locus is not one.

    `entries` is every `(allele, variantallele)` CPIC states at one locus, across **all** of the gene's
    alleles (never a filtered subset: whether a locus is a delins cannot depend on which alleles an
    author asked for). The locus is a delins only when the values are `DEL<bases>` and `INS<bases>`
    and nothing else, every `DEL` names the same bases, there is an `INS`, and the `DEL` sits on the
    gene's **reference allele** (`reference_names`). That last condition is what makes the `DEL` the
    reference state rather than a second variant: RYR1's `DELTC` is on `Reference`. A locus where the
    deletion and the insertion are two variant alleles, or where the reference is written as plain
    bases or a bare `DEL`, is read one row at a time.
    """
    parsed = [(allele, parse_notation(value)) for allele, value in entries]
    if not all(isinstance(p, Notation) and p.kind in ("deletion", "insertion") for _, p in parsed):
        return None
    deletions = [(allele, p) for allele, p in parsed if isinstance(p, Notation) and p.kind == "deletion"]
    inserted = [p for _, p in parsed if isinstance(p, Notation) and p.kind == "insertion"]
    if not inserted or len({p.bases for _, p in deletions}) != 1:
        return None
    if not all(allele in reference_names for allele, _ in deletions):
        return None
    return deletions[0][1].bases


def spell(
    notation: Notation,
    chrom: str,
    start: int,
    read_window: ReadWindow,
    *,
    delins_ref: str | None = None,
) -> Spelled | str:
    """Spell one notation at CPIC's `start`, or return why it cannot be spelled.

    `delins_ref` is the locus's reference bases when the locus is a delins (`delins_partner`): the
    insertion is then the substitution `delins_ref>bases` and the deletion is the reference state.
    """
    if delins_ref is not None and notation.kind in ("deletion", "insertion"):
        here = read_window(chrom, start, start + len(delins_ref) - 1)
        if here is None or len(here) != len(delins_ref):
            return "reference_unreadable"
        if here.upper() != delins_ref:
            return "reference_disagrees"
        alt = delins_ref if notation.kind == "deletion" else notation.bases
        if alt == delins_ref:
            return Spelled(chrom, start, delins_ref, delins_ref)
        return _normalized(chrom, start, delins_ref, alt, read_window)

    if notation.kind == "deletion":
        here = read_window(chrom, start - 1, start + len(notation.bases) - 1)
        if here is None or len(here) != len(notation.bases) + 1:
            return "reference_unreadable"
        here = here.upper()
        if here[1:] != notation.bases:
            return "reference_disagrees"
        return _normalized(chrom, start - 1, here, here[0], read_window)

    if notation.kind == "insertion":
        anchor = read_window(chrom, start, start)
        if not anchor:
            return "reference_unreadable"
        anchor = anchor.upper()
        return _normalized(chrom, start, anchor, anchor + notation.bases, read_window)

    # A repeat: count the reference's own copies of the unit from `start`, then insert or delete the
    # difference after the base before the run.
    unit = notation.bases
    if notation.count is None:  # pragma: no cover - `parse_notation` sets it for every repeat
        return "unrecognized"
    # CPIC's position is the run's first base, so a whole copy of the unit just before it means the
    # position sits inside the run and the rightward count below would come out short — an indel of
    # the wrong size, published without a word. Withheld instead.
    before = read_window(chrom, start - len(unit), start - 1)
    if before is None or len(before) != len(unit):
        return "reference_unreadable"
    if before.upper() == unit:
        return "reference_disagrees"
    run = read_window(chrom, start - 1, start - 1 + _RUN_WINDOW)
    if run is None or len(run) < len(unit) + 1:
        return "reference_unreadable"
    run = run.upper()
    anchor, body = run[0], run[1:]
    copies = 0
    while body[copies * len(unit) : (copies + 1) * len(unit)] == unit:
        copies += 1
    if copies == 0:
        return "reference_disagrees"
    if (copies + 1) * len(unit) > len(body):
        return "reference_unreadable"  # the run reaches the window's edge: the count would be clipped
    count = notation.count
    if count > copies:
        return _normalized(chrom, start - 1, anchor, anchor + unit * (count - copies), read_window)
    if count < copies:
        return _normalized(chrom, start - 1, anchor + unit * (copies - count), anchor, read_window)
    # The reference count: the reference state, written at the anchor the variants at this run share,
    # so a consumer reads one locus for every count. Placed by left-aligning a one-unit insertion.
    placed = _normalized(chrom, start - 1, anchor, anchor + unit, read_window)
    if isinstance(placed, str):
        return placed
    return Spelled(chrom, placed.start, placed.ref, placed.ref)


def _normalized(chrom: str, pos: int, ref: str, alt: str, read_window: ReadWindow) -> Spelled | str:
    placed = _left_align(chrom, pos, ref, alt, read_window)
    if placed is None:
        return "reference_unreadable"
    return Spelled(*placed)
