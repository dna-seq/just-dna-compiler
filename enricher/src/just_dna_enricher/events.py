"""Whether two spellings of a position name one event: the one tri-state judge (RM267, RM375).

**The class this module closes.** An indel can be written at several anchors inside its repeat, and
two releases of one source, or two sources, or an author and a source, routinely pick different ones:
the old Ensembl snapshot wrote NUDT15's `rs761191455` as `13:48041104 G>GG`, the new one as
`13:48041103 T>TG`, and a CPIC-drafted `haplotypes.csv` authored the first. Every place that compared two
such spellings decided the question its own way: by exact `start` (the compiler's positional fill and
its SNP-core `_verify`), by `len(ref) == 1` read as "substitution" (`resolver.coordinate_verdict`, which
an insertion's one-base anchor satisfies), or by VRS ids that are absent on every offline indel
(`outcome._same_events`, which then read "unknown" as "different"). This is where the question is
answered for all of them, three-valued: `True` (one event), `False` (two), `None` (nothing this run
holds can tell). `None` is never a weak `False` (`@tautology-zero`).

**Two entry points, one ladder.**

* `same_event` takes two whole alleles. The spellings are identical; or both are substitutions, which
  have one spelling once their shared flank is trimmed; or both mint a VRS id (the id is over the fully
  justified allele, so it needs no tolerance); or both left-align against the reference window. Else
  undecided.
* `names_event` takes an **authored** coordinate, which may be partial — a haplotype row authors a
  `start` and perhaps a `ref`, never an ALT — against one allele of a resolved locus. A whole authored
  allele goes through `same_event`. A partial one names the event when its `start` (and its `ref`,
  where it states one) is one of the event's anchors: a substitution's own or trimmed spelling, or
  every spelling an indel slides through inside its repeat (`sequences.indel_spellings`, which reads
  the reference). It is a **different** event only where that answer is sharp: a substitution, which
  cannot slide, or an indel whose every spelling the reference showed, with the authored position
  outside every base those spellings touch. A position inside the event's footprint that is no VCF
  anchor (an HGVS-style position) and a padded `ref` are undecided, as is anything with no reference
  read.

The enricher alone may call these: the compiler holds no reference (P2), so it reads the verdict the
enricher recorded (`ResolutionRow.authored_event`) and never judges two spellings itself
(`@a-recorded-judgement-is-a-fact`, `@validation-ceiling`).
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from just_dna_format.alleles import parsimony_reduce
from just_dna_format.resolution import authored_coordinate_key
from just_dna_format.vocab import ALLELE_PATTERN
from just_dna_format.vrs import normalize_chrom

from just_dna_enricher.sequences import _LEFT_ALIGN_WINDOW, _left_align, indel_spellings

Mint = Callable[[str, int, str, str], str | None]
ReadWindow = Callable[[str, int, int], str | None]


def no_mint(chrom: str, start: int, ref: str, alt: str) -> None:
    """The minter of a caller holding no sequence service: every id is unknown, never a guess."""
    return None


#: `ResolutionRow.authored_event`'s members (`vocab.VALID_AUTHORED_EVENT_VERDICTS`), by the answer.
AUTHORED_EVENT_VERDICT: dict[bool | None, str] = {
    True: "same_event",
    False: "different_event",
    None: "undecided",
}


@dataclass(frozen=True)
class Allele:
    """One allele of one placement, in VCF spelling."""

    chrom: str
    start: int
    ref: str
    alt: str

    def __str__(self) -> str:
        return f"{self.chrom}:{self.start} {self.ref}>{self.alt}"

    @property
    def spelling(self) -> tuple[str, int, str, str]:
        return (self.chrom, self.start, self.ref, self.alt)


def _trimmed(allele: Allele) -> tuple[int, str, str]:
    """`(start, ref, alt)` with the shared flank trimmed, right then left (`parsimony_reduce`'s rule)."""
    ref, alt, start = allele.ref, allele.alt, allele.start
    while ref and alt and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    while ref and alt and ref[0] == alt[0]:
        ref, alt, start = ref[1:], alt[1:], start + 1
    return start, ref, alt


def _kind(allele: Allele) -> tuple[str, int, str]:
    """What left-alignment cannot change: the event's type, its length, and a substitution's bases.

    An indel's payload is left out on purpose — sliding it inside a repeat rotates it (`AG` reads as
    `GA` one base on), so only its length pairs two spellings of one event.
    """
    reduced = parsimony_reduce([allele.ref, allele.alt])
    _, ref, alt = _trimmed(allele)
    if "" in reduced and len(reduced) == 2:
        (payload,) = reduced - {""}
        return ("insertion" if len(allele.alt) > len(allele.ref) else "deletion", len(payload), "")
    return ("substitution", len(alt), alt) if len(ref) == len(alt) else ("complex", len(ref) - len(alt), alt)


def same_event(first: Allele, second: Allele, *, mint: Mint, read_window: ReadWindow | None) -> bool | None:
    """Whether two whole spellings are one event — `True`, `False`, or `None` when nothing here can tell.

    The module docstring gives the ladder. `None` is a respelling this run had no sequence to settle,
    and it is counted apart.
    """
    if first.spelling == second.spelling:
        return True
    kind = _kind(first)
    if kind[0] == "substitution" and kind == _kind(second):
        return _trimmed(first) == _trimmed(second)
    ids = (mint(*first.spelling), mint(*second.spelling))
    if ids[0] is not None and ids[1] is not None:
        return ids[0] == ids[1]
    if read_window is not None:
        left = (
            _left_align(*first.spelling, read_window=read_window),
            _left_align(*second.spelling, read_window=read_window),
        )
        if left[0] is not None and left[1] is not None:
            return left[0] == left[1]
    return None


def alleles_of(loci: Iterable[Mapping[str, object]]) -> list[Allele]:
    """Every nucleotide allele the loci name, one per ALT. A symbolic or empty ALT names no placement."""
    out: list[Allele] = []
    for locus in loci:
        chrom, start, ref = locus.get("chrom"), locus.get("start"), str(locus.get("ref") or "").upper()
        if chrom is None or start is None or not ALLELE_PATTERN.match(ref):
            continue
        for alt in str(locus.get("alts") or "").split(","):
            alt = alt.strip().upper()
            if alt and alt != ref and ALLELE_PATTERN.match(alt):
                out.append(Allele(str(chrom), int(start), ref, alt))  # type: ignore[arg-type]
    return out


def kleene_any(answers: Iterable[bool | None]) -> bool | None:
    """`True` if any answer is, else `None` if any is unknown, else `False` (and `False` for none)."""
    seen = list(answers)
    return True if True in seen else None if None in seen else False


def kleene_all(answers: Iterable[bool | None]) -> bool | None:
    """`False` if any answer is, else `None` if any is unknown, else `True`."""
    seen = list(answers)
    return False if False in seen else None if None in seen else True


def _anchors_name(start: int, ref: str | None, event: Allele, read_window: ReadWindow | None) -> bool | None:
    """Whether a partial authored coordinate (a `start`, perhaps a `ref`) is one of the event's anchors."""
    padded = ref is not None and len(ref) > 1
    kind = _kind(event)[0]
    if kind in ("substitution", "complex"):
        trimmed = _trimmed(event)
        anchors = {(event.start, event.ref), (trimmed[0], trimmed[1])}
        if any(start == s and (ref is None or ref.upper() == r) for s, r in anchors):
            return True
        # A substitution cannot slide, so another position is another event; a complex event and a
        # padded `ref` have spellings this cannot enumerate without an ALT.
        return False if kind == "substitution" and not padded else None
    spellings = indel_spellings(*event.spelling, read_window) if read_window is not None else None
    if spellings is None:
        return None
    if any(start == s[1] and (ref is None or ref.upper() == s[2]) for s in spellings):
        return True
    last = spellings[-1]
    # The bases the event touches: a deletion's anchor and the bases it removes; an insertion's anchor
    # and the base after it, between which it sits (an HGVS insertion names both).
    deletion = len(last[2]) > len(last[3])
    footprint_end = last[1] + (len(last[2]) - len(last[3]) if deletion else 1)
    if padded or spellings[0][1] <= start <= footprint_end:
        return None
    return False


def names_event(
    chrom: str | None,
    start: int,
    ref: str | None,
    alts: str | None,
    event: Allele,
    *,
    mint: Mint,
    read_window: ReadWindow | None,
) -> bool | None:
    """Whether an authored coordinate spells the same event as one resolved allele. See the module note.

    `chrom` may be `None` (a CPIC-drafted half-coordinate): the authored `start` is then read on the
    event's own contig, which is the only place the compiler would complete it to.
    """
    if chrom is not None and normalize_chrom(chrom) != normalize_chrom(event.chrom):
        return False
    whole = (
        alleles_of([{"chrom": event.chrom, "start": start, "ref": ref, "alts": alts}]) if ref and alts else []
    )
    if whole:
        return kleene_any(same_event(a, event, mint=mint, read_window=read_window) for a in whole)
    return _anchors_name(start, ref, event, read_window)


def authored_event(
    authored: tuple[str | None, int | None, str | None, str | None],
    locus: Mapping[str, object],
    *,
    mint: Mint,
    read_window: ReadWindow | None,
) -> tuple[str, str] | None:
    """`(authored_event, judged_coordinate)` for one locus written for a subject that authored a coordinate.

    `None` (two empty cells) where there is nothing to judge: the subject authored no `start`, or the
    authored cells the compiler compares (`chrom`, `start`, and `ref` where authored) equal the locus's,
    so the compiler sees agreement on its own. Otherwise the verdict the compiler reads, over the
    locus's ALTs: the authored coordinate names the locus when it spells any of its events (a
    multi-allelic site's anchor is shared), and a locus with no nucleotide ALT is undecided. Beside it,
    the coordinate it judged (`authored_coordinate_key`), which binds the verdict: the compiler applies
    it only to a row still authoring that coordinate.
    """
    chrom, start, ref, alts = authored
    if start is None:
        return None
    locus_chrom, locus_start, locus_ref = locus.get("chrom"), locus.get("start"), locus.get("ref")
    if (
        (chrom is None or normalize_chrom(chrom) == normalize_chrom(str(locus_chrom)))
        and start == locus_start
        and (not ref or ref.upper() == str(locus_ref or "").upper())
    ):
        return None
    events = alleles_of([locus])
    answer = (
        kleene_any(
            names_event(chrom, start, ref, alts, e, mint=mint, read_window=read_window) for e in events
        )
        if events
        else None
    )
    return AUTHORED_EVENT_VERDICT[answer], authored_coordinate_key(chrom, start, ref)


def counterparts(allele: Allele, other: Sequence[Allele]) -> list[Allele]:
    """The alleles on the other side a respelling of `allele` could be: the same contig, within the window
    an indel can slide in, the same kind of event (an insertion or deletion of the same length, or a
    substitution to the same bases). Shared by the placement witness (RM267) and the drift (RM375)."""
    kind = _kind(allele)
    return [
        o
        for o in other
        if o.chrom == allele.chrom and abs(o.start - allele.start) <= _LEFT_ALIGN_WINDOW and _kind(o) == kind
    ]


def same_allele_sets(
    before: Sequence[Allele], after: Sequence[Allele], *, mint: Mint, read_window: ReadWindow | None
) -> bool | None:
    """Whether two answers for one subject name the same events, allele for allele (RM375).

    Every allele on either side is judged against the other side's alleles of its own kind (a
    respelling never changes the kind): the same event as one of them, or a different event from all
    of them, or undecided. An allele with no counterpart of its kind at all is a change in the answer
    when it is a **substitution**, whose spelling and hosting are both decided without a reference, so
    a run with one and a run without would have kept it alike. An unmatched **indel** is undecided: the
    hosting filter settles an indel locus by the reference (RM274) and RM270 splits a locus only when it
    can read one, so an offline table and an online one legitimately keep different indel ALTs of the
    same source answer (`rs746071566`'s three offline, one online). That costs sharpness, never truth: a
    source that really gained or dropped an indel ALT reads undecided rather than moved.
    """
    if not before and not after:
        return None
    return kleene_all(
        (
            covers(before, after, mint=mint, read_window=read_window),
            covers(after, before, mint=mint, read_window=read_window),
        )
    )


def covers(
    side: Sequence[Allele], other: Sequence[Allele], *, mint: Mint, read_window: ReadWindow | None
) -> bool | None:
    """Whether every allele of `side` is the same event as one of `other`'s: one direction of the judge.

    `same_allele_sets` is both directions; the `--rederive` drift reads them apart (RM394), because a
    source that kept every recorded event and named one more **gained** an allele, which is neither a
    respelling nor a move. The per-allele rule is the one `same_allele_sets` states: no counterpart is
    `False` for a substitution and undecided for an indel. An empty `side` is covered.
    """
    answers: list[bool | None] = []
    for allele in side:
        matches = counterparts(allele, other)
        if not matches:
            answers.append(False if _kind(allele)[0] == "substitution" else None)
            continue
        answers.append(kleene_any(same_event(allele, o, mint=mint, read_window=read_window) for o in matches))
    return kleene_all(answers)
