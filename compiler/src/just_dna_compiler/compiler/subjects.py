"""What a module is about: its genes, its loci and its variant identities, answered once (RM362).

"Which genes and loci is this module about" had several answerers that read different tables.
`manifest.stats.genes` and the enricher's gene scope read `variants.csv` plus every gene-bearing table
kind; the study-orphan check read `variants.csv`, `haplotypes.csv`, `pharm_variants.csv` and the rows a
meta member reached; and the five derived-row orphan checks read `variants.csv` alone and returned
nothing when it was absent. A diplotype-scored APOE module was then told its own `gene_metrics.csv` row
named "a gene this module never mentions" while its manifest listed APOE, and a PGx-only module was never
checked at all.

Every one of them now asks `module_subjects`, over the rosters below. Each orphan check still reads the
facet it always read (a gene, a `chrom:start:ref` position, or a `variant_key`/`rsid` identity), because
the join is a property of what its sidecar's source publishes; only the tables behind the facet moved.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from just_dna_format.vocab import MULTI_SEP

from just_dna_compiler.compiler.tables import _TABLE_KINDS, study_coordinate_key

VARIANTS_CSV: str = "variants.csv"

#: The tables whose `gene` is a gene the module is about: `variants.csv` and every table kind declaring `gene`,
#: derived from `_TABLE_KINDS` so a kind gaining the column joins by existing. The one statement of the predicate:
#: `positional._GENE_BEARING_TABLE_KINDS` is this roster's table kinds with their models. An authored table that is
#: not a table kind (`tables.AUTHORED_NON_KIND_TABLES`) is never on it: `model_organisms.csv`'s `gene` is the gene
#: a mouse experiment altered, not one the module's findings are about. **PUBLIC**, because the enricher's gene
#: scope is derived from it (a private name reached across a package is the RM41 shape).
MODULE_GENE_TABLES: tuple[str, ...] = (
    VARIANTS_CSV,
    *(name for name, _parquet, model in _TABLE_KINDS if "gene" in model.model_fields),
)

#: The tables whose rows name a locus the module carries: `variants.csv` and every positional table kind (`chrom`
#: and `start` both declared; `positional._POSITIONAL_TABLE_KINDS` is read off this). The same set
#: `reverse.RESOLUTION_SOURCE_TABLES` rebuilds `resolution.csv` from, less a study's LD proxy, which is a locus the
#: module asks about for an allele check and does not annotate. A `meta.csv` member reaches rows of
#: `meta.LOCUS_TABLES` only, each on this roster, so the rows a member reaches are subjects already (a test asserts
#: the inclusion).
MODULE_LOCUS_TABLES: tuple[str, ...] = (
    VARIANTS_CSV,
    *(name for name, _parquet, model in _TABLE_KINDS if {"chrom", "start"} <= set(model.model_fields)),
)


@dataclass(frozen=True)
class ModuleSubjects:
    """The answer, in the three facets the checks join on, plus whether each is known at all.

    `genes` is every `gene` cell as written, in first-occurrence order of the tables handed in: the set
    `manifest.stats.genes` publishes (sorted there), composite cells included, because a composite may
    name the locus and splitting it would guess (S72, `composite_gene_cell`). `gene_symbols` is each cell
    split on `MULTI_SEP`, the symbols a registry is asked about. A gene row matches on either.

    `genes_unknown` / `loci_unknown` withhold: a roster table that is present and loaded no row makes the
    module's subjects unknown, and naming every fact row an orphan would bury the load errors that are
    the real report (the study check's `carried_unknown`, generalized).
    """

    genes: tuple[str, ...] = ()
    positions: frozenset[str] = frozenset()
    identities: frozenset[str] = frozenset()
    #: The `variant_key` of every locus row that has a position (`chrom` and `start`): the subjects
    #: `reverse_module` writes a `resolution.csv` row for, so an artifact of this module can carry one.
    placed: frozenset[str] = frozenset()
    genes_unknown: bool = False
    loci_unknown: bool = False

    @cached_property
    def gene_symbols(self) -> tuple[str, ...]:
        """Each gene cell split on `MULTI_SEP`, de-duplicated in first-occurrence order (P7)."""
        out: dict[str, None] = {}
        for cell in self.genes:
            for part in MULTI_SEP.split(cell):
                if part.strip():
                    out.setdefault(part.strip(), None)
        return tuple(out)

    @cached_property
    def _gene_names(self) -> frozenset[str]:
        return frozenset(self.genes) | frozenset(self.gene_symbols)

    def names_gene(self, gene: str | None) -> bool:
        """Whether a gene is one this module mentions, as a cell or as a part of one."""
        return gene is not None and gene in self._gene_names

    def sits_at(self, chrom: str | None, start: int | None, ref: str | None) -> bool:
        """Whether some module row sits at this `chrom:start:ref`, alt ignored (a position-level join)."""
        return bool(chrom) and start is not None and study_coordinate_key(chrom, start, ref) in self.positions

    def carries(self, *ids: str | None) -> bool:
        """Whether any of these identities (`variant_key` or `rsid`) is one a module row carries."""
        return any(i is not None and i in self.identities for i in ids)


def module_subjects(
    rows_by_table: Mapping[str, Sequence[Any]], *, unreadable: Iterable[str] = ()
) -> ModuleSubjects:
    """The genes, positions and identities the module's rows name, over the two rosters above.

    `rows_by_table` maps a CSV name to its rows, in the order the caller wants first occurrence read
    (`{"variants.csv": variants, **kind_rows}`); a table off the rosters is ignored, which is how a
    non-kind table's `gene` stays out without each caller remembering it. The rows are read as handed
    in, so a positional row the resolution fill has placed contributes its filled position: the compile
    hands in post-fill rows and resolved variants, the pre-flight its post-fill view.

    `unreadable` names tables that are present and loaded no row; one on a roster withholds that facet.
    """
    unread = set(unreadable)
    genes: dict[str, None] = {}
    positions: set[str] = set()
    identities: set[str] = set()
    placed: set[str] = set()
    for table, rows in rows_by_table.items():
        if table in MODULE_GENE_TABLES:
            for row in rows:
                gene = getattr(row, "gene", None)
                if gene:
                    genes.setdefault(gene, None)
        if table in MODULE_LOCUS_TABLES:
            for row in rows:
                chrom, start = getattr(row, "chrom", None), getattr(row, "start", None)
                key = getattr(row, "variant_key", None)
                # A row with no `start` sits nowhere: `19:None:None` would match every unplaced row on 19.
                if chrom and start is not None:
                    positions.add(study_coordinate_key(chrom, start, getattr(row, "ref", None)))
                    if key:
                        placed.add(key)
                for identity in (key, getattr(row, "rsid", None)):
                    if identity:
                        identities.add(identity)
    return ModuleSubjects(
        genes=tuple(genes),
        positions=frozenset(positions),
        identities=frozenset(identities),
        placed=frozenset(placed),
        genes_unknown=bool(unread & set(MODULE_GENE_TABLES)),
        loci_unknown=bool(unread & set(MODULE_LOCUS_TABLES)),
    )
