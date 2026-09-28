"""Does a `conclusion` name a genotype other than its own row's? (RM279)

`conclusion` is required free text, and nothing compared it with the other cells on its row, so a
module whose `C/C` and `A/A` conclusions were swapped compiled green under `--strict`. This reads the
one thing in the prose that can be checked without a source: a two-allele genotype spelled with the
bases the module itself states at that locus.

**The rule, and why each restriction is there.** A row is named when its conclusion spells one or more
genotypes built from the locus's own alleles and **never** its own. Each narrowing below removed a
measured false positive and nothing else, over 653,706 diploid rows (the six curated v1 ports the
reporter measured, `reference_examples/`, and the registry's cardio, cancer and pathogenic modules):

* **Only the locus's own bases.** The alleles are the union over every row at the locus (its
  genotypes, `ref`, `alts`), so *"(TG) levels"* on a C/T locus is not a genotype.
* **Never its own genotype, rather than any other one.** A correct row saying *"AA is protective, AC
  carriers less so"* names its neighbour too; the looser reading fired 24 times at about 40%.
* **Not straight after an rsID.** *"rs1042718 (C/A)"* spells the site's alleles, not a genotype.
* **Not after the word `haplotype`.** *"the haplotype CC of rs3758391 and rs4746720"* spans two sites.
* **Not the row's own `gene`.** ClinVar-templated rows read *"variant in TG"*.

What was left fired 10 times, and all 10 were real (the swapped pair, text copied from the next row,
and a strand-mixed pair). Case-sensitive on purpose: prose writes genotypes in capitals, and `ag` or
`at` in a sentence is a word.

It reports and never repairs: the conclusion may be right and the genotype wrong, and only the author
knows which (`@refutation-withholds`).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from just_dna_format.alleles import GENOTYPE_SEPARATORS, split_genotype
from just_dna_format.spec import VariantRow

_BASES = frozenset("ACGT")

#: Two bases, bare or joined by a genotype separator, standing alone — `GG-carriers` and `(TT)`
#: qualify, `-174GG` and `rs123A` do not. The separators are the leaf's, never a copy of them.
_GENOTYPE_TOKEN: re.Pattern[str] = re.compile(
    rf"(?<![A-Za-z0-9])([ACGT])[{re.escape(GENOTYPE_SEPARATORS)}]?([ACGT])(?![A-Za-z0-9])"
)

#: How far back the two context exclusions look: far enough for `rs1042718 (` and
#: `the haplotype `, short enough not to reach a previous clause.
_LOOKBACK = 24
_AFTER_RSID: re.Pattern[str] = re.compile(r"rs\d+\s*[(/]?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ConclusionMismatch:
    """One row whose conclusion names genotypes at its locus and never its own.

    `named` holds the genotypes as sorted base pairs (`AG`), and `named_rows` the indices of the other
    rows at the locus carrying one of them — which is how a swapped pair shows up as two findings
    pointing at each other."""

    row: int
    genotype: str
    named: tuple[str, ...]
    named_rows: tuple[int, ...]


def _locus(row: VariantRow) -> tuple[str, ...]:
    if row.rsid:
        return (row.rsid,)
    return (str(row.chrom), str(row.start))


def _pair(genotype: str) -> str | None:
    alleles = split_genotype(genotype)
    if len(alleles) != 2 or not all(a.upper() in _BASES for a in alleles):
        return None
    return "".join(sorted(a.upper() for a in alleles))


def _named_genotypes(row: VariantRow, alleles: frozenset[str]) -> set[str]:
    text = row.conclusion
    genes = {g.strip() for g in re.split(r"[,;|]", row.gene or "") if g.strip()}
    named: set[str] = set()
    for match in _GENOTYPE_TOKEN.finditer(text):
        first, second = match.group(1), match.group(2)
        if first not in alleles or second not in alleles:
            continue
        before = text[max(0, match.start() - _LOOKBACK) : match.start()]
        if _AFTER_RSID.search(before) or "haplotype" in before.lower():
            continue
        if match.group(0) in genes:
            continue
        named.add("".join(sorted((first, second))))
    return named


def conclusion_genotype_mismatches(rows: Sequence[VariantRow | None]) -> list[ConclusionMismatch]:
    """Every row whose conclusion names a genotype of its own locus and never its own, in row order.

    `None` entries (rows that failed validation) keep their index and are skipped, so a caller's row
    numbers stay the caller's. Only two-base diploid genotypes are judged; a haploid or symbolic row
    has no two-letter spelling to be confused with."""
    alleles: dict[tuple[str, ...], set[str]] = {}
    pairs: dict[tuple[str, ...], dict[str, list[int]]] = {}
    for index, row in enumerate(rows):
        if row is None:
            continue
        locus = _locus(row)
        bases = alleles.setdefault(locus, set())
        for allele in split_genotype(row.genotype):
            bases.add(allele.upper())
        for allele in (row.ref or "", *(row.alts or "").split(",")):
            bases.add(allele.strip().upper())
        pair = _pair(row.genotype)
        if pair is not None:
            pairs.setdefault(locus, {}).setdefault(pair, []).append(index)

    found: list[ConclusionMismatch] = []
    for index, row in enumerate(rows):
        if row is None:
            continue
        own = _pair(row.genotype)
        if own is None:
            continue
        locus = _locus(row)
        named = _named_genotypes(row, frozenset(alleles[locus] & _BASES))
        if not named or own in named:
            continue
        others = sorted(i for pair in named for i in pairs.get(locus, {}).get(pair, []) if i != index)
        found.append(ConclusionMismatch(index, row.genotype, tuple(sorted(named)), tuple(others)))
    return found
