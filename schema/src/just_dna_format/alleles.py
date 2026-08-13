"""Reference-free allele algebra: comparing two spellings of one variant (0.5, RM31).

One indel has several valid spellings. ClinVar publishes a SHOX 2 bp deletion as `X:634689 CAG>C` — the
deleted bases with a padding base in front — while Ensembl publishes the same event as
`X:634690 AGAG>AG`, anchored one base earlier inside the repeat. Both are correct, and comparing the
allele **strings** says they are different variants, which is what made `rs1569493663` resolve to
`not_found` in `reference_examples/shox_par1/`.

**What can be decided without a reference sequence, and what cannot.** Two spellings of one indel differ
only in how much shared flanking sequence they carry and where they are anchored. Strip the flank and the
*event* is what remains: how many bases were removed and which, how many added and which. That is
computable from the strings alone. What is **not** computable is where the event sits when it lies inside
a repeat — left-alignment needs the reference — so two spellings whose events are the same length but
different content may be one variant rotated within a repeat, or two different variants, and this module
says so rather than guessing.

That gives three outcomes, not two, which is the house algebra (`None` is never `False`):

* the reduced allele sets **match** — the same event, so a genotype written for one spelling fits the
  other;
* the reduced **length profiles differ** — a positive contradiction, and a confident one: left-alignment
  moves an indel, it never changes how many bases the event adds or removes;
* the lengths agree and the content does not — **unknown**, which is the residual the reference would
  settle. The enricher can (it has seqrepo); the compiler, by charter, cannot.

**Frame-free on purpose.** No position is passed in, and none is needed: a genotype naming two alleles
carries its own frame, because the two strings share whatever flank their record used. That matters
because the row this was built for records **no coordinate at all** — `clinvar_draft` prefers the rsID and
the model forbids `ref`/`alts` without a coordinate, so the authored genotype `C/CAG` is spelled in
ClinVar's frame in a row that never stated it. A position-anchored normalization would have had nothing to
anchor against on the authored side.

Lives in the format tier because it is allele grammar (pure stdlib, no deps) and because the compiler and
the enricher must agree on it exactly — `genotype_fits` is shared three ways and digest parity between the
two resolvers is a documented guarantee.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

#: The four bases an allele column is expected to spell.
NUCLEOTIDES: frozenset[str] = frozenset("ACGT")

#: The IUPAC single-letter degenerate codes (bioinformatics.org/sms/iupac.html). `N` is here because it
#: is one of them; it is also the **only** one that occurs in real variant records — probed across
#: 4,439,382 ClinVar GRCh38 rows, where `R`/`Y`/`S`/`W`/`K`/`M`/`B`/`D`/`H`/`V` appear in neither REF nor
#: ALT even once. They are a *sequence* and *genotype* notation, not a variant-record one.
IUPAC_AMBIGUITY_CODES: frozenset[str] = frozenset("RYSWKMBDHVN")

# ── Symbolic / structural alleles (0.6, RM5) ───────────────────────────────────────────────────
#
# VCF 4.4 §1.4.5/§5: an ALT allele may be an angle-bracketed symbolic name when the exact sequence is
# not known. The **first level is a closed five**; subtypes are colon-separated and "implementations
# are free to define their own", with `CNV:TR`, `DUP:TANDEM`, `DEL:ME` and `INS:ME` recommended. That
# closed five is exactly what this format holds, and nothing above it: the standard's `##ALT=<ID=…,
# Description="…">` declaration mechanism — which would let a module name any allele it likes — was
# **rejected**, because it is unasked extendability in the one layer a human has to read.
#
# Spelling the bases out stays the default. The standard says so ("when the exact sequence is known,
# the variant can be represented as a non-symbolic ALT allele"), which is why 5-HTTLPR — a ~43 bp
# indel whose sequence is known — is authored as a plain indel here rather than as `<S>`/`<L>`.
#
#: The five first-level structural types. CLOSED (Principle 6 — a `frozenset` plus a validator, never
#: an `Enum`). `<*>` (VCF's unspecified allele) is deliberately absent: it names no variant, it makes
#: an *observability* claim, which is a different axis from this one.
SYMBOLIC_ALLELE_TYPES: frozenset[str] = frozenset({"DEL", "INS", "DUP", "INV", "CNV"})

#: The subtypes VCF 4.4 recommends. OPEN, unlike the first level — the standard leaves subtypes to the
#: implementation, so an unfamiliar one is accepted and only the first-level type is gated. Kept as a
#: tuple in the spec's own order so a message built from it is deterministic.
RECOMMENDED_SYMBOLIC_SUBTYPES: tuple[str, ...] = ("CNV:TR", "DUP:TANDEM", "DEL:ME", "INS:ME")

#: Anything angle-bracketed, whatever is inside it. Deliberately lenient: it is the *shape* test, so a
#: `<FOO>` or a `<*>` can be told apart from a typo'd nucleotide string and diagnosed as what it is.
_SYMBOLIC_SHAPE: re.Pattern[str] = re.compile(r"^<[^<>]*>$")

#: `<TYPE[:SUBTYPE…][:LENGTH]>`. A subtype must start with a letter and a length is all digits, so the
#: trailing field is unambiguously one or the other — which is what lets the length ride inside the
#: token instead of in a column beside it.
_SYMBOLIC_TOKEN: re.Pattern[str] = re.compile(
    r"^<([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)*)(?::([0-9]+))?>$"
)


@dataclass(frozen=True)
class SymbolicAllele:
    """A parsed symbolic allele: the closed first-level type, its subtypes, and its length.

    **The length rides inside the token (`<DEL:1500>`, `<CNV:TR:30>`) rather than in a column beside
    it, and that was decided rather than defaulted.** VCF carries it as `INFO/SVLEN`, which this DSL
    has no equivalent of, so the two candidate homes were a new authored column or the allele string.
    The column loses, three ways:

    * **SVLEN is `Number=A` — one value per ALT.** A scalar column cannot describe `alts=<DEL:5>,
      <DUP:9>`, and a *parallel array* column is the shape `ResolutionRow.vrs_id` needed two separate
      desync guards for. Inside the token there is nothing to desync: each allele carries its own.
    * **Three of the columns that hold an allele have no row to hang it on.** `genotype` names two
      alleles at once, and `HaplotypeRow.allele`/`VariantRow.effect_allele` are single cells whose row
      is about something else. A per-row length answers none of them.
    * **An authored column is full cost** (Constitution, 0.6 amendment): a human types it, on every
      table that can carry an allele, forever. The token costs nothing an author does not already read.

    Case is preserved as written and normalized only here — `type` and `subtypes` are upper-cased,
    matching how `hosting_verdict` compares alleles, while `text` keeps the author's spelling so no
    cell is silently rewritten.
    """

    text: str
    type: str
    subtypes: tuple[str, ...]
    length: int | None

    @property
    def kind(self) -> str:
        """The colon-joined type, e.g. `DEL` or `CNV:TR` — the length dropped."""
        return ":".join((self.type, *self.subtypes))


def is_symbolic_allele(value: str | None) -> bool:
    """Whether `value` is *shaped* like a symbolic allele — angle-bracketed, whatever is inside.

    The lenient half of the pair. `parse_symbolic_allele` answers whether it is a **usable** one; this
    answers whether the author was reaching for one at all, which is what a diagnosis needs: `<FOO>`
    and `<*>` are not usable here and telling their author so beats a generic rejection.
    """
    return value is not None and bool(_SYMBOLIC_SHAPE.match(value.strip()))


def parse_symbolic_allele(value: str | None) -> SymbolicAllele | None:
    """Parse a well-formed symbolic allele, or `None` when `value` is not one.

    `None` covers three different things on purpose — not angle-bracketed at all, angle-bracketed but
    malformed, and a first-level type outside `SYMBOLIC_ALLELE_TYPES` — because a *parser* answers one
    question. Which of the three it is, and what follows, is `symbolic_allele_defect`'s job.

    A length of `0` parses (the grammar is digits) and is *not* rejected here: it is a well-formed
    token stating an unusable length, and separating well-formedness from usability is what lets the
    schema accept a row the compiler then judges.

    >>> parse_symbolic_allele("<DEL:1500>").kind
    'DEL'
    >>> parse_symbolic_allele("<CNV:TR:30>").kind
    'CNV:TR'
    >>> parse_symbolic_allele("<CNV:TR:30>").length
    30
    >>> parse_symbolic_allele("<DEL>").length is None
    True
    >>> parse_symbolic_allele("<FOO:12>") is None
    True
    """
    if value is None:
        return None
    text = value.strip()
    match = _SYMBOLIC_TOKEN.match(text)
    if match is None:
        return None
    fields = [field.upper() for field in match.group(1).split(":")]
    if fields[0] not in SYMBOLIC_ALLELE_TYPES:
        return None
    length = match.group(2)
    return SymbolicAllele(
        text=text,
        type=fields[0],
        subtypes=tuple(fields[1:]),
        length=int(length) if length is not None else None,
    )


def symbolic_allele_defect(value: str | None) -> str | None:
    """Why a symbolic allele cannot be used as written, or `None` when it can (or is not one).

    Two defects, kept apart because the author does something different about each, and because
    lumping two reasons under one message is a mistake this codebase has already made and unwound
    twice (`cpic.unusable_allele_reason`, `_spelling_clauses`):

    * `"unknown_type"` — angle-bracketed but not one of the five first-level types, or not
      parseable at all. `<FOO>`, `<DEL`, and VCF's own `<*>` are this: nothing names a structural
      event the format can hold, so there is nothing to widen a length onto.
    * `"no_length"` — a real structural type carrying no usable length (absent, or `0`). Well-formed,
      and still an unusable *rule*: a `<DEL>` with no length cannot be sized, matched against a call,
      or told apart from any other deletion at the same position.

    A nucleotide string, an ambiguity code and a repeat notation all return `None` — they are not
    symbolic alleles, and `non_nucleotide_reason` is what classifies those.
    """
    if not is_symbolic_allele(value):
        return None
    parsed = parse_symbolic_allele(value)
    if parsed is None:
        return "unknown_type"
    if parsed.length is None or parsed.length <= 0:
        return "no_length"
    return None


def non_nucleotide_reason(allele: str | None) -> str | None:
    """Why `allele` is not a nucleotide string, or `None` when it is one.

    Three answers, never one, and conflating them is a mistake this codebase has already made once and
    repaired (`cpic.unusable_allele_reason`, which now delegates here): calling a deletion notation an
    "ambiguity code" is a false claim about the data and points an author at the wrong thing.

    * `"ambiguity"` — every character is a base or an IUPAC degenerate code. The value states an
      *uncertainty*, so it can never be expanded into definite alleles: doing so would assert alleles the
      source declined to. ClinVar's 35 `A>N` records are this shape.
    * `"symbolic"` — a **well-formed symbolic/structural allele** (`<DEL:1500>`, `<CNV:TR:30>`), which
      the grammar holds since 0.6. Not a nucleotide string, and not a defect either: it names a real
      variant whose sequence is deliberately unspelled, so nothing can be compared against it
      character by character and every comparison against a spelled allele is *undecided*.
    * `"notation"` — not a nucleotide string and not a symbolic allele either: a repeat notation
      (`AAAGGGGCG(2)`), a deletion spelling like `DELTCT`, a typo, or an angle-bracketed name outside
      the closed five (`<FOO>`). A **grammar gap** rather than an uncertainty.

    This used to answer `"notation"` for `<DEL>` too, and that stopped being true when RM5 shipped:
    the reading it carried — *a grammar gap a future release may widen* — is now false for the five
    structural types, and a message built from it sends an author to wait for a release that already
    happened.

    Note the third real shape this deliberately files under `"ambiguity"` rather than inventing a name
    for: `N` *inside* a longer allele (633 ClinVar records spell a known-length insertion whose interior
    is unknown, `TTTGG` + `NNNNNNNNNN` + `AAAA`). It is not a degenerate base standing alone, but it is
    the same statement — part of this sequence is unknown — and the consequence is identical: nothing may
    be expanded from it.
    """
    if allele is None:
        return None
    value = allele.strip().upper()
    if not value or set(value) <= NUCLEOTIDES:
        return None
    if parse_symbolic_allele(value) is not None:
        return "symbolic"
    return "ambiguity" if set(value) <= (NUCLEOTIDES | IUPAC_AMBIGUITY_CODES) else "notation"


def non_nucleotide_alleles(ref: str | None, alts: str | None) -> dict[str, str]:
    """`{allele: reason}` for every member of a locus that is not a nucleotide string.

    Insertion-ordered (`ref` first, then `alts` as written), so a message built from it is deterministic.
    Empty for the overwhelmingly common case, which is what lets a caller ask cheaply.

    Exists because **no `ref`/`alt`/`alts` column in the schema has a nucleotide grammar** — eleven
    columns across six models. Adding one would reject `N` alongside a genuine typo, and would stop an
    existing module validating (Principle 3). So the value is accepted and the *diagnosis* improves
    instead: a non-nucleotide allele makes `hosting_verdict` return a confident `False`, and without
    this the author is told their genotype contradicts their locus — true of the cell, false of the
    variant, and three steps from the actual mistake.

    **`vocab.validate_allele` has TWO users, not one.** This docstring said "exactly one user,
    `HaplotypeRow.allele`" from 0.5 until RM5 shipped, and CLAUDE.md repeated it; the second is
    `VariantRow.effect_allele` (`spec.py`). The count matters because it is what an author of a
    grammar change reads to size the blast radius, and the shared diploid grammar
    `AuthoredModel._validate_genotype` is a third site again — used by `VariantRow` (required) and
    `PharmVariantRow` (optional).
    """
    found: dict[str, str] = {}
    for allele in [ref, *(alts.split(",") if alts else [])]:
        reason = non_nucleotide_reason(allele)
        if reason is not None and allele is not None:
            found.setdefault(allele.strip().upper(), reason)
    return found


def parsimony_reduce(alleles: Iterable[str]) -> frozenset[str]:
    """Strip the flanking sequence every allele shares, leaving the event each one represents.

    Right first, then left — the VCF trimming convention — and stopping before any member is consumed
    past empty, so the shortest allele bounds the trim. An allele fully consumed becomes `""`, which is
    the honest rendering of "this allele is the absence of what the others carry".

    A collection with fewer than two distinct members is returned unchanged: a single allele has nothing
    to be relative to, so there is no flank to identify. That is why a *homozygous* genotype on an indel
    cannot be reconciled this way — see `event_profile`.

    >>> sorted(parsimony_reduce(["C", "CAG"]))          # ClinVar's spelling of a SHOX deletion
    ['', 'AG']
    >>> sorted(parsimony_reduce(["AGAG", "AG"]))        # Ensembl's spelling of the same deletion
    ['', 'AG']
    >>> sorted(parsimony_reduce(["C", "T"]))            # a substitution has no shared flank
    ['C', 'T']
    """
    members = [a.strip().upper() for a in alleles if a and a.strip()]
    if len({*members}) < 2:
        return frozenset(members)
    while all(m for m in members) and len({m[-1] for m in members}) == 1:
        members = [m[:-1] for m in members]
        if any(not m for m in members):
            break
    while all(m for m in members) and len({m[0] for m in members}) == 1:
        members = [m[1:] for m in members]
        if any(not m for m in members):
            break
    return frozenset(members)


def event_profile(alleles: Iterable[str]) -> frozenset[int] | None:
    """The length of each reduced allele — what left-alignment cannot change.

    Returns `None` when the collection cannot be reduced at all (fewer than two distinct alleles), which
    is a different answer from "the profile is empty" and must not be read as one: it means the *frame*
    is unknown, so nothing about the event can be stated. A homozygous indel genotype (`C/C`) lands here.

    Length is the load-bearing invariant. Sliding an indel within a repeat changes its position and can
    rotate the inserted/deleted string, but the number of bases added or removed is a property of the
    event itself. So profiles that differ prove two different variants, while equal profiles with
    different content are exactly the case a reference would have to settle.
    """
    reduced = parsimony_reduce(alleles)
    if len(reduced) < 2:
        return None
    return frozenset(len(member) for member in reduced)
