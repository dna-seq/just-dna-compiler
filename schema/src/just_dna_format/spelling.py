"""One comparison rule per kind of value (RM363, `@one-normalizer-two-spellings`).

A gene symbol, a drug name, a DOI and a chromosome are each written more than one way by the people and
sources that fill a module, and each is compared or keyed in more than one place. The defect this module
exists to prevent is the second place comparing by a different rule than the first: the 0.8 audit found
`Apoe` matched as APOE by the PGx duplicate checks and missed by the meta-table's expansion, `chr12`
folded to `12` on `variants.csv` and kept on `studies.csv`, and a DOI ending in `.` read as one citation
by the literature pass and as two by the duplicate-citation check.

Two shapes, and which one a kind takes is decided by what it already did:

- **Folded on input** — `chrom`. `VariantRow` has stored the member (`12`, `MT`) since 0.5, and every
  coordinate key is built from the stored cell, so every model declaring `chrom` declares it as
  `ChromCell` and stores the member too. Only a spelling of a primary-assembly contig is folded; any other
  value is kept as written, so a model that never refused a scaffold still does not (Principle 3) and
  `VariantRow`'s refusal still quotes what the author wrote.
- **Compared through a key, stored verbatim** — `gene`, `drug`, `doi`. What a cell says is the author's
  (`@verbatim-except-order`); what two cells are compared by is `comparison_key`, looked up by column
  name in `COMPARISON_KEYS`. A test walks every model and asserts the set of fields of these kinds equals
  the registry, and an AST walk asserts no site compares one raw.

`trait_efo_id` (`EFO_0004340` / `EFO:0004340`), haplotype and allele names, `sex` (a closed vocabulary,
stored as its member) and rsIDs (`^rs\\d+$`, one spelling) are compared verbatim everywhere: one rule each,
not two, so none is an instance of the class.

Format tier: imports only `vrs`, so `base` can use `ChromCell` without a cycle.
"""

import re
from collections.abc import Callable, Iterable
from typing import Annotated, Any

from pydantic import AfterValidator

from just_dna_format.vrs import normalize_chrom

#: The primary-assembly contigs a `chrom` cell may name, as stored (`chr`-less, `MT` for the mitochondrion).
VALID_CHROMOSOMES: frozenset[str] = frozenset({str(i) for i in range(1, 23)} | {"X", "Y", "MT"})

#: A DOI is `10.<registrant>/<suffix>` (Crockford/Handle grammar). Real sources present it bare
#: (`10.1234/abc.def`) or wrapped in a URL (`https://doi.org/10.1234/abc`); a cell carrying one token is
#: accepted and kept verbatim, mirroring the PMID contract. Wider than a PMID: it also covers
#: preprints/books/datasets with no PubMed id (docs/USE_CASES.md §4a, RM11).
DOI_PATTERN: re.Pattern[str] = re.compile(r"10\.\d{4,9}/\S+")

#: Punctuation a DOI token picks up from the prose around it and never ends in.
_DOI_TRAILING = ".,;"


def fold_chrom(value: str | None) -> str | None:
    """A `chrom` cell as stored: a spelling of a primary-assembly contig becomes its member (`chr12` →
    `12`, `chrM` → `MT`); anything else is returned as written, refused or kept by the model's own rule."""
    if value is None:
        return None
    folded = normalize_chrom(value)
    return folded if folded in VALID_CHROMOSOMES else value


#: The type of every `chrom` field: the fold runs on input, so the stored cell is the key.
ChromCell = Annotated[str | None, AfterValidator(fold_chrom)]


def gene_key(gene: str) -> str:
    """A gene symbol as two cells compare it: case and surrounding space do not make two genes (RM351,
    RM356). `Cyp2c19` and `CYP2C19` are one gene to every check, key and selector."""
    return gene.strip().casefold()


def drug_key(drug: str) -> str:
    """A drug name as two cells compare it: `Azathioprine` and `azathioprine` are one drug, one key and
    one `(sex, drug)` scope. A separate function from `gene_key` although the body is the same, because
    the two are different claims about different vocabularies and either may need to move alone."""
    return drug.strip().casefold()


def doi_token(raw: str) -> str | None:
    """The DOI a free-form cell names, as two cells compare it, or `None` when it names none.

    The token is lower-cased (DOIs are case-insensitive) and loses trailing `.`, `,` and `;`, which a DOI
    pasted from prose carries and a registered DOI does not end in. The `None` arm is for text that is not
    a validated `doi` cell — a registry's answer, a free-text field."""
    match = DOI_PATTERN.search(raw)
    return match.group(0).rstrip(_DOI_TRAILING).casefold() if match else None


def doi_key(doi: str) -> str:
    """A `doi` cell's key: `doi_token` when it carries one, else the stripped cell lower-cased.

    A validated `doi` cell always carries a token (`validate_doi_cell`), so the fallback is reached only by
    a caller keying text the model did not validate."""
    token = doi_token(doi)
    return token if token is not None else doi.strip().casefold()


#: The comparison of each compared kind, by column name. A column absent here compares verbatim.
#: `chrom` is folded on input, so its key is the fold (a fixed point on a stored cell) and a selector's
#: `chrom=chr12` meets a stored `12`.
COMPARISON_KEYS: dict[str, Callable[[str], Any]] = {
    "gene": gene_key,
    "modifier_gene": gene_key,
    "drug": drug_key,
    "doi": doi_key,
    "chrom": fold_chrom,
}


def comparison_key(column: str, value: Any) -> Any:
    """`value` of `column` as any two cells of it are compared: through `COMPARISON_KEYS`, else as is.
    `None` stays `None` — an unstated cell is never equal to a stated one by normalization."""
    if value is None:
        return None
    key = COMPARISON_KEYS.get(column)
    return key(str(value)) if key is not None else value


def distinct_spellings(values: Iterable[str | None], column: str) -> list[str]:
    """The distinct values of `column` by its comparison, each in its first spelling, sorted.

    For a published list (`manifest.stats.genes`): `APOE` and `Apoe` are one gene, named as it was first
    written, and the list is sorted so its order cannot drift."""
    first: dict[Any, str] = {}
    for value in values:
        if value:
            first.setdefault(comparison_key(column, value), value)
    return sorted(first.values())
