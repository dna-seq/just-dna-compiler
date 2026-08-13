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

from collections.abc import Iterable

#: The four bases an allele column is expected to spell.
NUCLEOTIDES: frozenset[str] = frozenset("ACGT")

#: The IUPAC single-letter degenerate codes (bioinformatics.org/sms/iupac.html). `N` is here because it
#: is one of them; it is also the **only** one that occurs in real variant records — probed across
#: 4,439,382 ClinVar GRCh38 rows, where `R`/`Y`/`S`/`W`/`K`/`M`/`B`/`D`/`H`/`V` appear in neither REF nor
#: ALT even once. They are a *sequence* and *genotype* notation, not a variant-record one.
IUPAC_AMBIGUITY_CODES: frozenset[str] = frozenset("RYSWKMBDHVN")

#: VCF's MISSING marker (§1.6.1.5). In an ALT column it does not name an allele at all — it states that
#: *there are no alternate alleles*, which is a monomorphic reference record, and §1.1's own worked
#: example carries one. It is spelled out here because the difference between "an allele we cannot hold"
#: and "no allele was asserted" is the whole of `non_nucleotide_reason`'s third answer (RM58).
MISSING_ALLELE: str = "."


def non_nucleotide_reason(allele: str | None) -> str | None:
    """Why `allele` is not a nucleotide string, or `None` when it is one.

    Three answers, never fewer, and conflating any two is a mistake this codebase has already made twice
    and repaired (`cpic.unusable_allele_reason`, which now delegates here): calling a deletion notation an
    "ambiguity code" is a false claim about the data and points an author at the wrong thing.

    * `"ambiguity"` — every character is a base or an IUPAC degenerate code. The value states an
      *uncertainty*, so it can never be expanded into definite alleles: doing so would assert alleles the
      source declined to. ClinVar's 35 `A>N` records are this shape.
    * `"notation"` — not a nucleotide string at all: a symbolic allele (`<DEL>`), a repeat notation
      (`AAAGGGGCG(2)`), a typo. A **grammar gap** (RM5) rather than an uncertainty, and a future release
      may widen to hold it.
    * `"missing"` — the bare `.`, VCF's MISSING marker. **Not an allele of any kind** (RM58), so it is
      neither an uncertainty nor a grammar gap: there is nothing for a future release to widen to hold,
      because the record is asserting that no alternate allele exists. It used to fall through to
      `"notation"` alongside `<DEL>`, which is the same two-reasons-under-one-message conflation the
      first two bullets exist to keep apart, one member further on. Its consequence is different again
      and is about *identity*: `derive_variant_key` folds the cell in as though it were an allele, so a
      row writing `alts=.` and a row leaving the cell empty describe one site under two keys
      (`1:1:A:.` and `1:1:A`) with different `content_signature`s and no dedup between them. The repair
      is to leave the cell empty, and it is the only one of the three where an authored edit is both
      available and unambiguous.

    Note the fourth real shape this deliberately files under `"ambiguity"` rather than inventing a name
    for: `N` *inside* a longer allele (633 ClinVar records spell a known-length insertion whose interior
    is unknown, `TTTGG` + `NNNNNNNNNN` + `AAAA`). It is not a degenerate base standing alone, but it is
    the same statement — part of this sequence is unknown — and the consequence is identical: nothing may
    be expanded from it.
    """
    if allele is None:
        return None
    value = allele.strip().upper()
    if value == MISSING_ALLELE:
        return "missing"
    if not value or set(value) <= NUCLEOTIDES:
        return None
    return "ambiguity" if set(value) <= (NUCLEOTIDES | IUPAC_AMBIGUITY_CODES) else "notation"


def non_nucleotide_alleles(ref: str | None, alts: str | None) -> dict[str, str]:
    """`{allele: reason}` for every member of a locus that is not a nucleotide string.

    Insertion-ordered (`ref` first, then `alts` as written), so a message built from it is deterministic.
    Empty for the overwhelmingly common case, which is what lets a caller ask cheaply.

    Exists because **no `ref`/`alt`/`alts` column in the schema has a nucleotide grammar** — eleven
    columns across six models, and `vocab.validate_allele` has exactly one user, `HaplotypeRow.allele`.
    Adding one would reject `<DEL>` and `N` alongside a genuine typo, tightening the field RM5 exists to
    widen, and would stop an existing module validating (Principle 3). So the value is accepted and the
    *diagnosis* improves instead: a non-nucleotide allele makes `hosting_verdict` return a confident
    `False`, and without this the author is told their genotype contradicts their locus — true of the
    cell, false of the variant, and three steps from the actual mistake.
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
