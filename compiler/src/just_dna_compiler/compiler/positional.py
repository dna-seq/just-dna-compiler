"""Positional tables: the resolution fill for rows keyed by position, the joinability check, and
the placement count.
"""

from typing import Any

from just_dna_format.base import DEFAULT_GENOME_BUILD, derive_variant_key
from just_dna_format.findings import CodedWarning
from just_dna_format.resolution import ResolutionRow
from pydantic import BaseModel

from just_dna_compiler.compiler.table_checks import _examples
from just_dna_compiler.compiler.tables import _TABLE_KINDS
from just_dna_compiler.resolution import resolve_positional_rows
from just_dna_compiler.resolution_findings import skipped_cross_build

#: The 0.4 table kinds that can name a locus, derived from the models rather than listed: a table is
#: positional exactly when it declares both `chrom` and `start`. Today that is `heteroplasmy.csv`,
#: `haplotypes.csv` and `pharm_variants.csv`. Hand-keeping this would be the `SOURCES_FIELDNAMES`
#: mistake again — a list that silently loses a member.
#:
#: **What the rest of the kinds are is two different things, and this comment used to call them one
#: (RM65).** It read "the rest are gene- or score-keyed and are not joinable by position at all, which
#: is a property of what they describe rather than a gap". True of `allele_function.csv` and `pgs.csv`,
#: which describe an allele's function and a score — neither has a place on a contig. **False of
#: `repeat_alleles.csv` and `copynumbers.csv`**, and the spec says so: VCF 4.4 §5.6 has POS and INFO
#: SVLEN specify the genomic interval a copy number is defined over, and §5.7 says a `<CNV:TR>`
#: record's POS and END *"should match the STR/VNTR reference catalog sizes for catalog-based
#: callers"*. A tandem repeat and a copy-number segment are loci with coordinates, emitted at fixed
#: published positions — so their non-joinability is a **gap in this schema**, not a property of the
#: thing described, and a consumer holding an ExpansionHunter or `<CNV:TR>` VCF has to annotate a gene
#: symbol for themselves to reach our HTT row. The columns that would close it wait for 0.7+, gated on
#: a real repeat-caller sample; what is corrected here is the claim, because a claim the spec
#: contradicts is a defect in its own right whatever release fixes the underlying gap.
_POSITIONAL_TABLE_KINDS: tuple[tuple[str, type[BaseModel]], ...] = tuple(
    (csv_name, model)
    for csv_name, _parquet, model in _TABLE_KINDS
    if {"chrom", "start"} <= set(model.model_fields)
)


#: The table kinds carrying a `gene` column, derived from `_TABLE_KINDS` the same way and for the same
#: reason: a hand-kept list goes stale the moment a kind is added, and this one feeds a **published
#: manifest number** (S57). Seven of the eight non-variant kinds make `gene` *required*, so a module
#: built on any of them knows its genes exactly while `manifest.stats.genes` used to publish `[]`.
_GENE_BEARING_TABLE_KINDS: tuple[tuple[str, type[BaseModel]], ...] = tuple(
    (csv_name, model) for csv_name, _parquet, model in _TABLE_KINDS if "gene" in model.model_fields
)


def _apply_positional_resolution(
    rows_by_csv: dict[str, list[Any]],
    resolution_table: dict[str, list[ResolutionRow]],
    genome_build: str = DEFAULT_GENOME_BUILD,
    *,
    resolve: bool = True,
) -> tuple[list[str], bool]:
    """Join the injected `resolution.csv` onto every positional 0.4-family table (RM43).

    Returns `(warnings, applied)`. **`applied` is load-bearing, not bookkeeping**: it is what lets
    `_check_positional_joinability` say *why* a row is still unplaced without asserting a reason the
    join never reached. Every gate below turns it off, and each is a different situation — no table to
    consult, no positional rows, a non-GRCh38 module, a caller that asked for no resolution — but they
    share the one consequence that matters downstream, which is that nothing was looked up.

    The compiler-side half of `resolution.resolve_positional_rows` — it picks the tables, handles the
    build gate, and collapses the per-row findings into one line per table. Rows are filled **in
    place**, so a caller that holds the lists gets the resolved rows back; run it before `_build_table`
    materializes them, and before `_check_positional_joinability`.

    Runs in `validate_spec` as well as `compile_module`, and it must: the joinability warning is
    computed from these rows in both, so filling on one side only would leave the pre-flight reporting
    a gap the compile had already closed — and that sentence carries `UNJOINABLE_PHRASE`, which a
    catalog reads as a trust signal (RM44). `resolve` is threaded from `resolve_with_ensembl` for the
    same reason: it is the master switch for resolution of every kind, so a pre-flight that ignored it
    would be the more *optimistic* of the two commands, which is the disagreement direction this
    repo's parity rule exists to prevent. Pure computation over injected bytes with no `output_dir`,
    which is the standing test for what belongs in both.

    **Skipped, with a warning, for a non-GRCh38 module**, exactly as `resolve_from_table` skips: the
    identity minting behind these keys is GRCh38-only (RM15), so joining a table the compiler cannot
    re-derive a key for would place rows against loci it has no way to check.
    """
    positional = [(csv_name, rows_by_csv.get(csv_name) or []) for csv_name, _model in _POSITIONAL_TABLE_KINDS]
    if not resolve or not resolution_table or not any(rows for _csv, rows in positional):
        return [], False
    if genome_build != DEFAULT_GENOME_BUILD:
        return [
            CodedWarning(
                "resolution_skipped_cross_build",
                skipped_cross_build(
                    what="Positional-table fill",
                    genome_build=genome_build,
                    not_joined_onto=", ".join(name for name, rows in positional if rows),
                    kept="Those rows keep the coordinates their author typed.",
                ),
            )
        ], False
    warnings: list[str] = []
    for csv_name, rows in positional:
        if not rows:
            continue
        report = resolve_positional_rows(rows, resolution_table, genome_build)
        if report.contradicted:
            warnings.append(
                CodedWarning(
                    "positional_identity_contradicted",
                    f"{csv_name}: {len(report.contradicted)} row(s) authored an identity the resolution "
                    f"table disagrees with, and are left exactly as authored — "
                    f"{_examples(report.contradicted)}",
                )
            )
    return warnings, True


#: **A downstream trust badge substring-matches this phrase, so it is a contract, not prose (S13).**
#: `compile_module` copies its warnings into `manifest.compilation.warnings`, which ships inside
#: `manifest.json` — and a catalog reindexing from a published manifest has no spec directory left to
#: re-derive anything from, so the *sentence* is the only surviving record that a table joins to
#: nothing. `just-dna-registry` 0.11.3 pins `UNJOINABLE_MARKER = "have no chrom+start"` in its facet
#: builder against exactly this, after the vacuous `fully_resolved` granted trust to modules that
#: annotate nothing. Rewording the phrase silently re-grants that trust.
#:
#: So it is named here rather than inlined: the rest of the sentence is free to improve, this fragment
#: is not, and a change to it is a deliberate act with a consumer to tell.
#:
#: **The structured repair landed in 0.6 and this still does not move (S31).**
#: `manifest.compilation.positional_rows` / `positional_rows_placed` are the counts a catalog should
#: read instead — RM44 shipped the same repair for `variants.csv` and recorded that the positional
#: count belonged with RM43, which shipped the fill without it. What that does *not* do is retire the
#: phrase: an artifact published under 0.5 carries neither field, so the sentence is still the only
#: record those manifests have, and rewording it re-grants trust to modules already in a catalog.
#: Retiring it is a decision to make once the published corpus has been recompiled, not a consequence
#: of the field existing.
UNJOINABLE_PHRASE = "have no chrom+start"


def _table_row_key(row: Any, genome_build: str) -> str | None:
    """The `variant_key` a 0.4-family row resolves under, exactly as the enricher derives it.

    All three positional models stamp the column since 0.6 (RM43) — `HaplotypeRow` had none at all
    before, and `enrich._collect_subjects` derived one inline with
    `derive_variant_key(rsid, chrom, start, ref)`, *without* `alts`, because a haplotype's defining
    allele is not the row's identity. The stamped key is that same expression, frozen at load from the
    authored columns, so this keeps agreeing with the table it reads. The fallback stays for a row
    built outside the loader and for a caller passing something older.
    """
    key = getattr(row, "variant_key", None)
    if key:
        return str(key)
    return derive_variant_key(
        getattr(row, "rsid", None),
        row.chrom,
        row.start,
        getattr(row, "ref", None),
        build=genome_build,
    )


def _check_positional_joinability(
    rows_by_csv: dict[str, list[Any]],
    resolution_table: dict[str, list[ResolutionRow]],
    genome_build: str = DEFAULT_GENOME_BUILD,
    *,
    fill_applied: bool = True,
) -> list[str]:
    """Which 0.4-family rows a consumer cannot join to a VCF by position, and why the fill left them.

    **Run AFTER `_apply_positional_resolution`, in both `validate_spec` and `compile_module`.** Until
    0.6 this reported the whole gap — resolution was SNP-core-scoped, so an rsid-authored PGx module
    compiled clean, validated, published, and had a null `chrom`/`start` on every row; the consumer
    who reported it had a 1,482-row module in that state and found out by reading parquet. RM43 closed
    that, and what is left for this check is the residue: rows the injected table does not place, or
    places at more than one locus.

    Reported as **counts per table, never a line per row**, and the second half is the interesting
    one — *why* a row is still unplaced. Three readings, and the author's next move differs:

    * the table names the key at **several** loci (or at loci the row's own allele contradicts), so
      the compiler leaves it rather than picking one — the same refusal `resolve_from_table` makes,
      and not something an enrich re-run fixes;
    * **nothing** in the table names the key at all, which an enrich run does fix;
    * the fill **never ran** (`fill_applied=False` — `--no-resolve`, a non-GRCh38 module), in which
      case the coordinates may well be right there and untried. That third branch is why the flag is a
      parameter rather than something inferred from `placeable`: the reason sentence lands in
      `manifest.compilation.warnings` beside `UNJOINABLE_PHRASE`, which is a published consumer
      surface (RM44), and asserting "the compiler looked and would not pick" about a lookup that never
      happened is a fabricated diagnosis in a document a catalog reads.

    A **partial** coordinate is counted apart because it is the more deceptive shape: `haplotypes.csv`
    drafted from CPIC carries a `start` with no `chrom` (CPIC publishes a position on
    `sequence_location` and the chromosome on `gene`), which reads as a coordinate and joins to nothing.

    **A warning in both modes, and deliberately never a `strict` error.** Rsid-only identity is legal
    by these models' own rule (`rsid`, *or* `chrom`+`start`), so escalating would make `--strict` mean
    "author coordinates into your PGx tables" — the format tightening a field it deliberately left
    open. And what remains after the fill is, by construction, something no authored edit to *this*
    table clears: it is the `not_covered` / VRS-coverage class, where refusing would make a correct
    module uncompilable for a reason its author cannot act on.
    """
    warnings: list[str] = []
    for csv_name, _model in _POSITIONAL_TABLE_KINDS:
        rows = rows_by_csv.get(csv_name) or []
        unplaced = [row for row in rows if row.chrom is None or row.start is None]
        if not unplaced:
            continue
        partial = [row for row in unplaced if row.chrom is not None or row.start is not None]
        placeable = [
            row
            for row in unplaced
            if any(
                r.chrom is not None and r.start is not None
                for r in resolution_table.get(_table_row_key(row, genome_build) or "", [])
            )
        ]
        # **`fill_applied` is tested FIRST, and the order is the whole point.** It used to sit in the
        # `elif`, behind `if not placeable`, which made the third reading unreachable on exactly the
        # modules it describes: when the fill never runs, `resolution.csv` is whatever the enricher
        # left, and on a non-GRCh38 module the enricher declines to resolve, so it holds only the
        # coordinates the author typed — meaning `placeable` is empty for precisely the rsid-only
        # rows, and the author was told "no resolution.csv row places them — run enrich first" one
        # line below a warning explaining that the fill was skipped because their module is GRCh37.
        # They had just run enrich, and on that build it can never place those rows. A remedy that
        # cannot work is worse than no remedy: it sends an author to re-run a command whose own
        # output already told them why it would not help.
        # `fill_applied` is False for four different situations and only some of them are "the table
        # was not consulted": no table at all, no positional rows, a non-GRCh38 module, and
        # `--no-resolve`. So it is conjoined with *a table being present* — with none, "run enrich"
        # is exactly the right advice and the branch below keeps it.
        if not fill_applied and resolution_table:
            named = (
                f"resolution.csv names {len(placeable)} of them and was"
                if placeable
                else "the resolution table was"
            )
            detail = f"{named} not consulted for this table — see the skip reported above"
        elif not placeable:
            detail = "no resolution.csv row places them — run `just-dna-enricher enrich` first"
        else:
            detail = (
                f"resolution.csv names {len(placeable)} of them, but at more than one locus or at "
                f"one the row's own allele contradicts, so the compiler leaves them unplaced rather "
                f"than picking"
            )
        partial_note = (
            f" {len(partial)} carr{'ies' if len(partial) == 1 else 'y'} one half of a coordinate "
            f"(a start with no chrom, or the reverse), which reads as a position and is not one."
            if partial
            else ""
        )
        warnings.append(
            CodedWarning(
                "positional_rows_unjoinable",
                f"{csv_name}: {len(unplaced)} of {len(rows)} row(s) {UNJOINABLE_PHRASE}, so this table "
                f"joins by rsID only — a VCF whose ID column is empty matches none of them. {detail}."
                f"{partial_note}",
            )
        )
    return warnings


def positional_placement(rows_by_csv: dict[str, list[Any]]) -> tuple[int, int]:
    """`(rows, placed)` across the three positional table kinds — the counts the manifest publishes.

    The structured half of `_check_positional_joinability`, which reports the same facts as prose per
    table (S31). Public because the number is what a catalog wants: until 0.6 the only record of how
    much of a PGx table joins to a VCF was `UNJOINABLE_PHRASE` inside `manifest.compilation.warnings`,
    and a downstream registry substring-matched it. Anything a consumer can only learn from a warning
    string is an unversioned interface (RM44).

    **Call it after `_apply_positional_resolution`**, so `placed` counts what the artifact actually
    carries rather than what the author typed — the fill is where an rsid-authored PGx module gets its
    coordinates, and before it the answer is the pre-RM43 one.

    A module carrying no positional table returns `(0, 0)`, which is a real answer and distinct from
    the `None` the manifest holds for a compile that never counted; see `Compilation.positional_rows`.
    """
    rows = [row for csv_name, _model in _POSITIONAL_TABLE_KINDS for row in rows_by_csv.get(csv_name) or []]
    placed = [row for row in rows if row.chrom is not None and row.start is not None]
    return len(rows), len(placed)
