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

#: Anything opening with `<`. Deliberately lenient: it is the *shape* test, so `<FOO>`, `<*>` and the
#: unterminated `<DEL` can each be told apart from a typo'd nucleotide string and diagnosed as what
#: they are. It was `^<[^<>]*>$` for one round, which let the likeliest typo of all — a missing closing
#: bracket — past the guard `hosting_verdict` added for exactly this, back into arithmetic over a token
#: that has no sequence. Nothing legal in an allele column begins with `<`.
_SYMBOLIC_SHAPE: re.Pattern[str] = re.compile(r"^<")

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
    """Whether `value` is *shaped* like a symbolic allele — it opens with `<`, whatever follows.

    The lenient half of the pair. `parse_symbolic_allele` answers whether it is a **usable** one; this
    answers whether the author was reaching for one at all, which is what a diagnosis needs: `<FOO>`,
    `<*>` and the unterminated `<DEL` are none of them usable here, and telling their author which
    beats a generic rejection.

    Deliberately not "opens **and closes**": requiring the `>` let a missing closing bracket — the
    likeliest typo there is — read as an ordinary allele string, so it slipped past the guard
    `hosting_verdict` keeps for exactly this and reached arithmetic over characters that spell no
    sequence. Nothing legal in an allele column begins with `<`, so the looser test costs nothing.
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

    * `"unknown_type"` — it opens with `<` but is not one of the five first-level types, or does not
      parse at all. `<FOO>`, the unterminated `<DEL`, and VCF's own `<*>` are this: none of them names
      a structural event the format can hold, so there is nothing to hang a length on.
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

#: VCF's MISSING marker (§1.6.1.5). In an ALT column it does not name an allele at all — it states that
#: *there are no alternate alleles*, which is a monomorphic reference record, and §1.1's own worked
#: example carries one. It is spelled out here because the difference between "an allele we cannot hold"
#: and "no allele was asserted" is the whole of `non_nucleotide_reason`'s `"missing"` answer (RM58).
MISSING_ALLELE: str = "."


# ── The allele that could not be observed (0.6, RM59) ──────────────────────────────────────────
#
# VCF 4.4 §1.6.1.5: an ALT allele may be *"the '*' symbol (allele missing due to overlapping
# deletion)"*. It is what any modern joint-called VCF puts at a site some deletion called elsewhere
# overlaps, so `ALT=A,*` with `GT=0/2` is **ordinary consumer data** rather than an exotic spelling.
#
# **This is not RM5's axis, and `*` must never be routed through the symbolic-allele machinery above.**
# The separation is the whole content of the item, and the file already states half of it: `<*>` is
# kept out of `SYMBOLIC_ALLELE_TYPES` for exactly this reason. Every symbolic allele names a *variant*
# whose sequence the grammar cannot spell — `<DEL:1500>` has an event, a place and a length. `*` names
# no variant at all: it says *this sample's allele could not be seen here*, which is an
# **observability** claim, and observability is the callability axis (`VariantRow.requires_callable` /
# `callable_from`). Two axes under one syntax is the overloaded-field anti-pattern P5 exists to stop,
# and the consequences differ concretely: an unusable symbolic allele is a grammar gap a release can
# widen, while `*` is a permanent statement about the *sample* that no release will turn into a
# sequence. So it gets its own predicate, its own reason class, and no length.

#: VCF's "allele missing due to overlapping deletion". Named rather than spelled inline because three
#: tiers compare against it and a bare `"*"` in a condition reads like a wildcard or a typo.
UNOBSERVABLE_ALLELE: str = "*"


def is_unobservable_allele(value: str | None) -> bool:
    """Whether `value` is VCF's `*` — *this sample's allele could not be observed at this position*.

    Deliberately an exact match on the one token, with none of `is_symbolic_allele`'s leniency. That
    function is loose (anything opening with `<`) because a malformed symbolic allele is a real authoring
    mistake worth diagnosing; `*` is a single character with no interior to get wrong, so there is no
    near-miss to be generous about and a looser test could only start claiming things that are not this.

    It **is** asked about `ref`, and an earlier draft of this note claimed otherwise.
    `hosting_verdict` builds its locus set as `{ref} | alts` and strips the whole set, so a `ref` of
    `*` is discarded like any other member. That is not an endorsement of writing one — a reference
    allele is the sequence a record is anchored to, and a `*` there anchors nothing — but the predicate
    is a *test*, not a policy, and a locus left with nothing observable is reported as undecided rather
    than treated as a contradiction.
    """
    return value is not None and value.strip() == UNOBSERVABLE_ALLELE


#: The two separators a genotype cell may use: `/` unphased, `|` phased. Named here because the split
#: below and every reader that reasons about phase have to mean the same two characters.
GENOTYPE_SEPARATORS: str = "/|"

_GENOTYPE_SEP: re.Pattern[str] = re.compile(f"[{re.escape(GENOTYPE_SEPARATORS)}]")


def split_genotype(genotype: str) -> list[str]:
    """The alleles a genotype cell names, in the order they were written (S30).

    **Never sorted.** `weights.parquet` stores exactly this list, so a consumer that sorts is giving one
    artifact two spellings of a genotype and will match a phased row a weights-led module would not. The
    order is the authored order and nothing else is read into it: whether a pipe *addresses* a homolog is
    a separate question the format does not answer (RM63 — phase is recorded, not addressable), and the
    answer does not change what this function returns.

    Public because it was being re-derived. The rule lives in three places that must agree — the
    validator's grammar, the compiler's materializer, and every consumer that reads a 0.4-family table —
    and the third had only prose to work from: a consumer reimplemented it, twice, in opposite directions,
    with no failing run either time to tell them which was right. A reimplementation that is slightly
    wrong raises nothing; it just matches a quietly larger set. So this is the leaf they call instead,
    the same way `derive.direction_from_state` is the leaf for a derivation the format owns the rule for.

    **The contract is "a validated genotype cell in, alleles out", and the input half is load-bearing.**
    Empty fragments are dropped, which makes the split total over any string — `|A|G` yields
    `['A', 'G']` — and `AuthoredModel._validate_genotype` **refuses** that cell (VCF 4.4's optional
    leading phasing indicator is one of RM67's two recorded divergences). Dropping empties is right for a
    cell the models have already accepted, and it is not a widening of what they accept: this function
    decides nothing about legality, so do not reach for it as a validator.

    Hemizygous cells are one allele (`'G'` → `['G']`), which is how every haploid contig in the corpus is
    authored, and symbolic or unobservable members come back verbatim (`'*/T'` → `['*', 'T']`) — this is
    a split, not a grammar.
    """
    return [allele for allele in _GENOTYPE_SEP.split(genotype) if allele]


def non_nucleotide_reason(allele: str | None) -> str | None:
    """Why `allele` is not a nucleotide string, or `None` when it is one.

    Five answers, never fewer, and conflating any two is a mistake this codebase has already made twice
    and repaired (`cpic.unusable_allele_reason`, which now delegates here): calling a deletion notation an
    "ambiguity code" is a false claim about the data and points an author at the wrong thing.

    * `"ambiguity"` — every character is a base or an IUPAC degenerate code. The value states an
      *uncertainty*, so it can never be expanded into definite alleles: doing so would assert alleles the
      source declined to. ClinVar's 35 `A>N` records are this shape.
    * `"symbolic"` — a **well-formed symbolic/structural allele** (`<DEL:1500>`, `<CNV:TR:30>`), which
      the grammar holds since 0.6. Not a nucleotide string, and not a defect either: it names a real
      variant whose sequence is deliberately unspelled, so nothing can be compared against it
      character by character and every comparison against a spelled allele is *undecided*.
    * `"unobservable"` — VCF's `*` (RM59). Not a defect and not a gap: it is a well-formed statement
      that *this sample's allele could not be observed here*, so it names no sequence to compare and
      never will. Kept apart from `"notation"` because the two carry opposite consequences — a grammar
      gap is a release away, and this one is permanent by construction.
    * `"missing"` — the bare `.`, VCF's MISSING marker. **Not an allele of any kind** (RM58), so it is
      neither an uncertainty nor a grammar gap: there is nothing for a future release to widen to hold,
      because the record is asserting that no alternate allele exists. Its consequence is different
      again and is about *identity*: `derive_variant_key` folds the cell in as though it were an allele,
      so a row writing `alts=.` and a row leaving the cell empty describe one site under two keys
      (`1:1:A:.` and `1:1:A`) with different `content_signature`s and no dedup between them. The repair
      is to leave the cell empty, and it is the only one of the five where an authored edit is both
      available and unambiguous.
    * `"notation"` — none of the above: a repeat notation (`AAAGGGGCG(2)`), a deletion spelling like
      `DELTCT`, a typo, or an angle-bracketed name outside the closed five (`<FOO>`). A **grammar gap**
      rather than an uncertainty.

    **`.` and `*` are the two answers that name no allele at all, and neither may absorb the other.**
    They arrived one lane apart and the temptation to merge them is real, because both are punctuation
    standing where a sequence goes and neither will ever become spellable. The claims are opposite:
    `.` asserts that **no alternate allele exists** — a monomorphic record, a statement about the
    *variant* — while `*` asserts that an allele **could not be observed** — a statement about the
    *sample's call*, which is the callability axis. So their consequences differ in kind. `.` is an
    identity defect with a clean authored repair (leave the cell empty). `*` is not a defect at all:
    the cell is correct, nothing needs editing, and what follows is that a consumer must withhold
    rather than read the call as reference. Merging them would either accuse a correct `*` row or
    silence a real `.` collision.

    This used to answer `"notation"` for `<DEL>` too, and that stopped being true when RM5 shipped:
    the reading it carried — *a grammar gap a future release may widen* — is now false for the five
    structural types, and a message built from it sends an author to wait for a release that already
    happened. `*` is the same shape of correction one axis over: it read as `"notation"` until RM59,
    which told an author of a perfectly ordinary joint-called site to wait for a grammar that can never
    arrive, because there is no sequence for a grammar to hold.

    Three of these answers were split out of `"notation"` in the same release, from different
    directions, and the set is worth keeping in view: `"symbolic"` left because RM5 gave the five
    structural types a home, so *a grammar gap a future release may widen* became false for them;
    `"missing"` left because `.` was never a gap at all; `"unobservable"` left because `*` is a fact
    about a sample rather than about the variant. All three were the same
    two-reasons-under-one-message conflation the first bullets exist to keep apart — found three times,
    in one release, in one function.

    Note the further real shape this deliberately files under `"ambiguity"` rather than inventing a name
    for: `N` *inside* a longer allele (633 ClinVar records spell a known-length insertion whose interior
    is unknown, `TTTGG` + `NNNNNNNNNN` + `AAAA`). It is not a degenerate base standing alone, but it is
    the same statement — part of this sequence is unknown — and the consequence is identical: nothing may
    be expanded from it.
    """
    if allele is None:
        return None
    value = allele.strip().upper()
    # The two markers that name no allele at all, tested together and answered apart — see the docstring:
    # `.` says no alternate allele exists, `*` says one could not be observed.
    if value == MISSING_ALLELE:
        return "missing"
    if is_unobservable_allele(value):
        return "unobservable"
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
