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

**A position is every spelling the module's own resolution gives a carried identity (2026-11-04).** An
indel has several valid spellings, so a row authored at one (CPIC's right-shifted NUDT15 allele) and a
`resolution.csv` placing the same rsID at another (Ensembl's left-aligned one) are one place written
twice. The frequency pass asks gnomAD about the resolution row, so reading the authored spelling alone
named the pass's own row an orphan. `identity_placements` is the one lookup, the `@membership-union`
rule: every usable locus (`resolution.usable_loci`, the fill's predicate) the injected table files under
the row's `variant_key` or `rsid`, on the module's build. Only the injected table counts (Principle 2),
and only where the fill would read it: GRCh38, resolution on. `module_subjects` takes the union;
`row_positions` is the per-row answer for a check that attributes a finding to one row.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from just_dna_format.base import DEFAULT_GENOME_BUILD
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spelling import gene_key
from just_dna_format.vocab import MULTI_SEP

from just_dna_compiler.compiler.tables import _TABLE_KINDS, study_coordinate_key
from just_dna_compiler.resolution import usable_loci

#: The injected `resolution.csv`, keyed by `variant_key` as every compile path holds it.
ResolutionTable = Mapping[str, Sequence[ResolutionRow]]

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

    `genes` is every `gene` cell, one per gene however it is written (`spelling.gene_key`, RM363) and in
    its first spelling, in first-occurrence order of the tables handed in: the set
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
    #: The positions taken from `resolution.csv` (`identity_placements` over every locus row), each
    #: also in `positions`: kept apart so a test can compare them with the table as an equality.
    resolved_positions: frozenset[str] = frozenset()

    @cached_property
    def gene_symbols(self) -> tuple[str, ...]:
        """Each gene cell split on `MULTI_SEP`, de-duplicated by `gene_key` in first-occurrence order (P7)."""
        out: dict[str, str] = {}
        for cell in self.genes:
            for part in MULTI_SEP.split(cell):
                if part.strip():
                    out.setdefault(gene_key(part), part.strip())
        return tuple(out.values())

    @cached_property
    def _gene_names(self) -> frozenset[str]:
        return frozenset(gene_key(name) for name in (*self.genes, *self.gene_symbols))

    def names_gene(self, gene: str | None) -> bool:
        """Whether a gene is one this module mentions, as a cell or as a part of one, compared as
        `spelling.gene_key` compares a gene (RM363)."""
        return gene is not None and gene_key(gene) in self._gene_names

    def sits_at(self, chrom: str | None, start: int | None, ref: str | None) -> bool:
        """Whether some module row sits at this `chrom:start:ref`, alt ignored (a position-level join)."""
        key = position_key(chrom, start, ref)
        return key is not None and key in self.positions

    def carries(self, *ids: str | None) -> bool:
        """Whether any of these identities (`variant_key` or `rsid`) is one a module row carries."""
        return any(i is not None and i in self.identities for i in ids)


def position_key(chrom: str | None, start: int | None, ref: str | None) -> str | None:
    """The `chrom:start:ref` both sides of a position join are keyed by, or `None` without a `start`
    (a row with no `start` sits nowhere: `19:None:None` would match every unplaced row on 19)."""
    if not chrom or start is None:
        return None
    return study_coordinate_key(chrom, start, ref)


def _own_position(row: Any) -> str | None:
    return position_key(getattr(row, "chrom", None), getattr(row, "start", None), getattr(row, "ref", None))


def _placement_rows(row: Any, resolution: ResolutionTable | None, genome_build: str) -> list[ResolutionRow]:
    """The usable table rows filed under this row's `variant_key` or `rsid` (see `identity_placements`)."""
    if not resolution or genome_build != DEFAULT_GENOME_BUILD:
        return []
    out: list[ResolutionRow] = []
    for identity in dict.fromkeys((getattr(row, "variant_key", None), getattr(row, "rsid", None))):
        if identity:
            out.extend(
                locus
                for locus in usable_loci(resolution.get(identity), genome_build)
                if locus.start is not None
            )
    return out


def identity_placements(row: Any, resolution: ResolutionTable | None, genome_build: str) -> frozenset[str]:
    """Every `chrom:start:ref` the module's own `resolution.csv` places this row's identity at.

    The identity is the row's `variant_key` and its `rsid`, both looked up: the table is keyed by the
    authored key, which an expanded `variants.csv` row no longer carries while it keeps the rsID. A
    table row that places nothing (`not_found`, no `chrom`, another build) contributes nothing, by
    `usable_loci`, the predicate both fills use. Empty with no table and on a non-GRCh38 module, where
    the fills decline to join (RM15), so a caller passes `None` under `--no-resolve`.
    """
    return frozenset(
        key
        for locus in _placement_rows(row, resolution, genome_build)
        if (key := position_key(locus.chrom, locus.start, locus.ref)) is not None
    )


def row_positions(row: Any, resolution: ResolutionTable | None, genome_build: str) -> frozenset[str]:
    """Where this one row sits, for a check that attributes a finding to a row (BA1, the study join
    behind `weights.parquet`): its own position, plus the table's placement when that is one other place.

    * The table places the row where it stands (same `chrom:start`, and the same `ref` where the row
      states one): its own locus only, so one copy of a 1:N expansion is never handed a sibling's
      evidence.
    * The table places the identity at exactly one other position: that too. It is the same place in
      another spelling (an indel left-aligned against a right-shifted authored allele).
    * Several other positions, or none: its own only. Which of several the row means is unknown, and
      the house algebra withholds rather than hand it all of them. `module_subjects` still takes the
      union, because "does the module sit here" asks about the module, not about one row.
    """
    own = _own_position(row)
    placed = _placement_rows(row, resolution, genome_build)
    chrom, start, ref = getattr(row, "chrom", None), getattr(row, "start", None), getattr(row, "ref", None)
    if any(
        locus.chrom == chrom and locus.start == start and (ref is None or locus.ref == ref)
        for locus in placed
    ):
        return frozenset({own}) if own is not None else frozenset()
    others = {
        key for locus in placed if (key := position_key(locus.chrom, locus.start, locus.ref)) is not None
    }
    mine = {own} if own is not None else set()
    return frozenset(mine | others) if len(others) == 1 else frozenset(mine)


def module_subjects(
    rows_by_table: Mapping[str, Sequence[Any]],
    *,
    unreadable: Iterable[str] = (),
    resolution: ResolutionTable | None = None,
    genome_build: str = DEFAULT_GENOME_BUILD,
) -> ModuleSubjects:
    """The genes, positions and identities the module's rows name, over the two rosters above.

    `rows_by_table` maps a CSV name to its rows, in the order the caller wants first occurrence read
    (`{"variants.csv": variants, **kind_rows}`); a table off the rosters is ignored, which is how a
    non-kind table's `gene` stays out without each caller remembering it. The rows are read as handed
    in, so a positional row the resolution fill has placed contributes its filled position: the compile
    hands in post-fill rows and resolved variants, the pre-flight its post-fill view.

    `unreadable` names tables that are present and loaded no row; one on a roster withholds that facet.

    `resolution` is the module's injected table, or `None` where no resolution may be consulted
    (`--no-resolve`): each locus row's `identity_placements` joins `positions` (the union, as
    `@membership-union` compares), so a fact row at the table's spelling of a carried identity is not an
    orphan. `genome_build` is the module's.
    """
    unread = set(unreadable)
    genes: dict[str, str] = {}
    positions: set[str] = set()
    identities: set[str] = set()
    placed: set[str] = set()
    resolved: set[str] = set()
    for table, rows in rows_by_table.items():
        if table in MODULE_GENE_TABLES:
            for row in rows:
                gene = getattr(row, "gene", None)
                if gene:
                    genes.setdefault(gene_key(gene), gene)
        if table in MODULE_LOCUS_TABLES:
            for row in rows:
                key = getattr(row, "variant_key", None)
                own = _own_position(row)
                if own is not None:
                    positions.add(own)
                    if key:
                        placed.add(key)
                resolved.update(identity_placements(row, resolution, genome_build))
                for identity in (key, getattr(row, "rsid", None)):
                    if identity:
                        identities.add(identity)
    return ModuleSubjects(
        genes=tuple(genes.values()),
        positions=frozenset(positions | resolved),
        identities=frozenset(identities),
        placed=frozenset(placed),
        genes_unknown=bool(unread & set(MODULE_GENE_TABLES)),
        loci_unknown=bool(unread & set(MODULE_LOCUS_TABLES)),
        resolved_positions=frozenset(resolved),
    )
