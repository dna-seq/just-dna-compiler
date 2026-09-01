"""Draft `repeat_alleles.csv` identity rows from the STRchive catalogue (RM165, the other half).

The band half of this source is checked and never written (`strchive.check_repeat_bands`). This is the
half that *is* written: the facts the catalogue owns and an author would otherwise transcribe by hand.

**And it is a much thinner row than the item expected, which is the finding this module carries.**
The proposal listed `chrom`/`start_hg38`/`stop_hg38`, `locus_structure`, `ref_copies` and the disease
identifiers as the identity half — and `RepeatAlleleRow` has **no column for any of them except the
trait**. That is not an oversight in the model: repeat coordinates are RM65, deferred, and the motif
structure is RM66, parked. So what a drafted row can actually carry is the gene, the motif, the trait
CURIE and the fixed `measure_kind`, with `conclusion` left as a placeholder for the human. The rest of
the catalogue's identity half is **reported and counted** rather than silently dropped — a number this
pass computes and discards is one every reader has to recompute.

What that thin row is still worth: the motif orientation is a real trap (a minus-strand locus is
published in two spellings), the MONDO id is a real transcription task, and the *list of loci* is
itself the thing an author starting a repeat module does not have. A drafted row is a locus the author
has been told exists, with its identity spelled the way the catalogue spells it and every
interpretive cell left blank.

**Never drafted: the bands.** `measure_min`/`measure_max`/`measure_tiling`, and the per-band
`direction`/`clin_sig`/`phenotype` that go with them. Measured against both corpus modules and wrong
in both: STRchive is a band coarser than `fmr1_cgg_repeat` at the premutation threshold, and its
`pathogenic_max` would invent a ceiling `htt_repeat_expansion` deliberately leaves open. The withheld
set is *derived* from the drafted one rather than listed beside it, so a column added to the model
lands on the withheld side by default.

**Appends, never mutates** (`@draft-appends`). A locus already in the table is reported
`already_present` and nothing is rewritten — matched on `(gene, repeat_unit)`, which is the identity
that survives the human filling in the bands and splitting one drafted row into four.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.draft import (
    DraftReport,
    PartialRow,
    append_partial_rows,
    authoring_requirements,
)
from just_dna_format.base import authored_field_names
from just_dna_format.binning import RepeatAlleleRow

from just_dna_enricher.licensing import (
    STRCHIVE_TERMS,
    check_declared_use,
    merge_sources_file,
    withdraw_stale_dataset,
)
from just_dna_enricher.strchive import (
    REPEAT_ALLELES_CSV,
    StrchiveCatalogue,
    StrchiveLocus,
    load_strchive_catalogue,
)


class StrchiveDraftError(RuntimeError):
    """A draft could not be attempted — an unreadable catalogue, or an unwritable spec directory."""


#: What decides whether a drafted row is the same row as one already in the table. **One constant
#: tuple for the whole batch**, because `append_partial_rows` builds its covered-set from a single
#: `match_on` and a per-row one produces signatures of different arities that match nothing
#: (`@match-on-is-per-batch`).
#:
#: `trait_efo_id` is deliberately **out** of it even though the bin-group key includes it: the trait
#: is a cell this provider fills from `mondo` and an author may legitimately clear or change, and a
#: re-draft after they did would then append the locus a second time.
_MATCH_ON: tuple[str, ...] = ("gene", "repeat_unit")

#: The one column a human must decide. `conclusion` is the sentence a reader is shown when a
#: measurement lands in this bin, and the catalogue does not have one — it has a disease description
#: for the locus, which is a different claim at a different grain. Left as the placeholder, which is
#: what makes a freshly drafted table unable to compile (`@stub-cannot-compile`).
_STUBBED: tuple[str, ...] = ("conclusion",)

#: The cells this provider is willing to state. Everything else on the model is withheld, and the
#: withheld set is derived from this one below rather than restated — so a column added to
#: `RepeatAlleleRow` in a later release is withheld by default rather than silently drafted empty.
DRAFTED_COLUMNS: tuple[str, ...] = ("gene", "repeat_unit", "measure_kind", "trait_efo_id", "unresolved")

#: What a drafted row never carries. Derived, and it is what the band half of the split means in code:
#: `measure_min`, `measure_max`, `measure_tiling` and the per-band `direction`/`clin_sig`/`phenotype`
#: are all in here, and a test asserts so by name because those are the ones the measurement was about.
WITHHELD_COLUMNS: frozenset[str] = frozenset(
    authored_field_names(RepeatAlleleRow)
) - set(DRAFTED_COLUMNS) - set(_STUBBED)

#: How a MONDO id is spelled as a `trait_efo_id`. STRchive publishes the bare numeric part.
_MONDO_PREFIX = "MONDO_"

#: How many refused loci a note names before it becomes a count — the aggregation rule this tier
#: applies everywhere, so a catalogue whose spelling has drifted does not print one sentence per locus.
_REFUSAL_LIMIT = 5


@dataclass
class StrchiveDraftResult:
    """What was drafted, and an account of every catalogue locus that was not."""

    report: DraftReport | None = None
    #: Loci that passed the gene filter — the denominator everything below is counted against.
    candidates: int = 0
    #: `reason -> count` for a locus this provider would not write a row for. Every admitted locus is
    #: either drafted or in here; `accounts_for_every_candidate` asserts it.
    withheld: dict[str, int] = field(default_factory=dict)
    #: `(gene, motif)` keys several loci claim, reported rather than resolved by file order.
    contested: list[tuple[str, str]] = field(default_factory=list)
    #: Loci carrying a fractional `ref_copies`, and loci carrying a `locus_structure`. Counted because
    #: no authored column holds either, and a number computed and dropped is one a reader recomputes.
    fractional_ref_copies: int = 0
    with_locus_structure: int = 0
    warnings: list[str] = field(default_factory=list)
    dataset: str | None = None
    skipped: bool = False

    @property
    def drafted(self) -> int:
        return len([o for o in (self.report.outcomes if self.report else []) if o.status == "added"])

    def accounts_for_every_candidate(self) -> bool:
        """Every admitted locus is either a partial row this run offered, or a counted withholding."""
        offered = len(self.report.outcomes) if self.report else 0
        return offered + sum(self.withheld.values()) == self.candidates


#: Why a locus was not drafted. Named rather than counted anonymously: each one sends the author
#: somewhere different, and a bare "12 skipped" is the aggregate that hides all three.
WITHHELD_REASONS: tuple[str, ...] = (
    "no_motif",          # the catalogue publishes no pathogenic motif, so the row has no key
    "contested_key",     # several loci share (gene, motif); picking one would depend on file order
    "incomplete_row",    # a required cell the source does not supply — derived from the model
)


def _trait_curie(locus: StrchiveLocus) -> str | None:
    """The MONDO id as a `trait_efo_id`, and `None` where the locus names more than one.

    Three ids is not an ambiguity this pass may resolve: FMR1 carries `0010383`, `0010706` and
    `0010382` — fragile X syndrome, FXTAS and FXPOI — and they are three diseases sharing one repeat,
    not three names for one. Picking the first would state a trait the author never chose, and the
    shipped `fmr1_cgg_repeat` module leaves `trait_efo_id` empty for exactly that reason.
    """
    if len(locus.mondo) != 1:
        return None
    raw = locus.mondo[0].strip()
    # STRchive publishes the bare digits today. Prefixing blindly would turn a future `MONDO:0007739`
    # into `MONDO_MONDO:0007739`, which the `trait_efo_id` validator rejects — and the row would then
    # be reported `invalid` rather than drafted, for a change in the source's spelling rather than in
    # its content. Storing a source's value verbatim stops where the encoding itself is what is being
    # translated, and a CURIE prefix is exactly that.
    stripped = raw
    for prefix in (_MONDO_PREFIX, "MONDO:"):
        if stripped.upper().startswith(prefix.upper()):
            stripped = stripped[len(prefix):]
            break
    return f"{_MONDO_PREFIX}{stripped}" if stripped else None


def _missing_required(cells: dict[str, object]) -> list[str]:
    """Required cells this row does not carry, **derived from the model's own rule**.

    Not a list beside the model: `pgx_draft` restated "no rsID and no position" while `HaplotypeRow`
    wanted rsID **or** chrom+start, and `draft --gene CYP2C9` died on an unhandled pydantic error.
    `authoring_requirements` answers requiredness in all three of its shapes, and the stubbed columns
    are subtracted because a placeholder is what this provider supplies for them.
    """
    requirements = authoring_requirements(REPEAT_ALLELES_CSV)

    def stated(name: str) -> bool:
        return str(cells.get(name) or "").strip() != ""

    missing = [n for n in requirements["always"] if n not in _STUBBED and not stated(n)]
    groups = [g for g in requirements["any_of"] if not any(n in _STUBBED for n in g)]
    if groups and not any(all(stated(n) for n in group) for group in groups):
        missing.append(" or ".join("+".join(group) for group in groups))
    return missing


def _partial(locus: StrchiveLocus, motif: str) -> tuple[PartialRow | None, list[str]]:
    """One locus at one motif spelling → the row this provider is willing to append.

    Returns `(row, missing)`: the row, or `None` with the required cells the catalogue did not supply.
    """
    cells: dict[str, object] = {
        "gene": locus.gene,
        "repeat_unit": motif,
        # Written out rather than left to the field default: both this and `unresolved` are
        # *defaulted, not optional*, and `load_csv_rows` turns an empty cell into `None` while keeping
        # the key, so a blank one fails on type instead of falling back (`@requiredness-three-shapes`).
        "measure_kind": "repeat_count",
        "unresolved": False,
        "trait_efo_id": _trait_curie(locus),
    }
    cells = {name: value for name, value in cells.items() if value is not None}
    missing = _missing_required(cells)
    if missing:
        return None, missing
    return PartialRow(
        model=RepeatAlleleRow, cells=cells, stubbed=_STUBBED, match_on=_MATCH_ON
    ), []


def draft_repeat_loci(
    spec_dir: Path,
    genes: Sequence[str] = (),
    *,
    catalogue: Path | StrchiveCatalogue | None = None,
    declared_use: str = "unstated",
    dry_run: bool = False,
) -> StrchiveDraftResult:
    """Append one identity row per STRchive locus into the module's `repeat_alleles.csv`.

    `genes` filters; empty drafts every locus in the catalogue. The filter runs **first** and is
    counted separately from the withholding, because "the catalogue has nothing for this gene" and
    "it has something and this provider would not write it" are different answers.

    Contestation is decided over the whole admitted set before any row is built, so a filter cannot
    remove the second claimant and leave the first reading as uncontested
    (`@filter-before-the-group-picks-a-winner`).
    """
    spec_dir = Path(spec_dir)
    result = StrchiveDraftResult(withheld=dict.fromkeys(WITHHELD_REASONS, 0))

    if catalogue is None:
        result.skipped = True
        result.warnings.append(
            "No STRchive catalogue was provisioned, so nothing was drafted from it. Build one with "
            "`just-dna-enricher strchive build --release <tag>`, or pass a downloaded "
            "STRchive-loci.json. Nobody-asked is not the same as the source having nothing."
        )
        return result

    # MIT grants the fetch under every declaration, so this always returns `None` — kept because the
    # gate is per source and a caller reading this file should see which answer it gives, not have to
    # infer that the question was never asked.
    refusal = check_declared_use(STRCHIVE_TERMS, declared_use)
    if refusal is not None:  # pragma: no cover - unreachable while the terms stay permissive
        raise StrchiveDraftError(refusal)

    loaded = (
        catalogue if isinstance(catalogue, StrchiveCatalogue) else load_strchive_catalogue(catalogue)
    )
    result.dataset = loaded.dataset

    wanted = {g.strip().upper() for g in genes if g.strip()}
    admitted = [
        locus for locus in loaded.loci if not wanted or locus.gene.upper() in wanted
    ]
    result.candidates = len(admitted)

    # Over the admitted set, before any row is built.
    claims: dict[tuple[str, str], list[str]] = {}
    for locus in admitted:
        for motif in locus.motifs:
            claims.setdefault((locus.gene, motif), []).append(locus.locus_id)
    contested = {key for key, ids in claims.items() if len(ids) > 1}
    result.contested = sorted(contested)

    partials: list[PartialRow] = []
    incomplete: list[str] = []
    for locus in admitted:
        result.fractional_ref_copies += int(
            locus.ref_copies is not None and not float(locus.ref_copies).is_integer()
        )
        result.with_locus_structure += int(bool(locus.locus_structure))
        # The reference spelling is the one drafted: a locus published in two orientations is one
        # locus, and writing both would put two rows in the table for one place on the genome. The
        # check reads the union so an author who wrote the other spelling still joins.
        motif = locus.motifs[0] if locus.motifs else ""
        if not motif:
            result.withheld["no_motif"] += 1
            continue
        if (locus.gene, motif) in contested:
            result.withheld["contested_key"] += 1
            continue
        row, missing = _partial(locus, motif)
        if row is None:
            result.withheld["incomplete_row"] += 1
            incomplete.append(f"{locus.locus_id} ({', '.join(missing)})")
            continue
        partials.append(row)

    if partials:
        result.report = append_partial_rows(
            spec_dir, REPEAT_ALLELES_CSV, partials, dry_run=dry_run
        )

    # Carried on the result, not logged: every caller here renders `warnings` itself, and
    # `civic_draft`/`clinvar_draft` do the same. Logging them as well printed each note twice.
    result.warnings.extend(_notes(result, incomplete))

    # **A pass that consults a source writes its `SourceRow`; one that contributed nothing writes
    # none** (`@write-the-sourcerow`). The key is what *this run covered*: a row is written when at
    # least one locus is in the module's table because of this provider — added now, or added by an
    # earlier run and recognised as `already_present`. A `--gene` filter that matched nothing, or a
    # catalogue whose every locus was withheld, leaves the module untouched, and a licence row saying
    # "this module uses STRchive" would then be a claim about a module that does not.
    covered = result.report is not None and any(
        outcome.status in {"added", "already_present"} for outcome in result.report.outcomes
    )
    if not dry_run and covered:
        merge_sources_file(
            [STRCHIVE_TERMS.row("annotation", declared_use=declared_use, dataset=result.dataset)],
            spec_dir,
            error=StrchiveDraftError,
        )
        # Widening a module from a NEWER snapshot leaves the row naming the older release, because the
        # merge above is never-clobber — right for a curator's hand-written terms, and a false claim
        # for `dataset`. The stale label is **withdrawn, never re-labelled**: a module carrying rows
        # from two releases has no honest single label, and unknown is withheld. Gated on rows
        # actually being added, since a re-draft that added none changed nothing to be honest about.
        if result.drafted:
            superseded = withdraw_stale_dataset(
                spec_dir, STRCHIVE_TERMS.source, "annotation", result.dataset,
                error=StrchiveDraftError,
            )
            if superseded is not None:
                result.warnings.append(
                    f"the licence row recorded {superseded} and this run drafted from "
                    f"{result.dataset or 'an unlabelled snapshot'}, so the release label was "
                    f"withdrawn rather than re-labelled: one column cannot name two releases."
                )
    return result


def _notes(result: StrchiveDraftResult, incomplete: Sequence[str]) -> list[str]:
    """Aggregated notes — one sentence per reason, never one per locus.

    The two counts about columns that do not exist are the point of this function. `ref_copies` is
    fractional on a large minority of loci (RM55's fractional-measure case arriving in a source rather
    than in a caller's VCF) and `locus_structure` is populated on about a quarter of them, which is
    the evidence RM66 was parked waiting for. Neither has an authored column, so both would otherwise
    be read, dropped and never mentioned.
    """
    notes: list[str] = []
    if result.contested:
        notes.append(
            f"{len(result.contested)} (gene, repeat_unit) key(s) are claimed by more than one "
            f"catalogue locus and were drafted for none of them — "
            f"{', '.join(f'{gene}/{motif}' for gene, motif in result.contested)}. Which locus a row "
            f"means is the source's own ambiguity; add the row by hand once you have decided."
        )
    if incomplete:
        notes.append(
            f"{len(incomplete)} locus/loci carry no complete identity for repeat_alleles.csv: "
            f"{', '.join(incomplete)}"
        )
    if result.fractional_ref_copies:
        notes.append(
            f"{result.fractional_ref_copies} of {result.candidates} locus/loci state a fractional "
            f"ref_copies (the reference allele is not a whole number of motif copies). No authored "
            f"column carries it, so it was read and not written — it is not rounded anywhere."
        )
    if result.with_locus_structure:
        notes.append(
            f"{result.with_locus_structure} of {result.candidates} locus/loci publish a "
            f"locus_structure — the (motif, count, type) breakdown of an interrupted repeat. No "
            f"authored column carries it either; repeat_alleles.csv keys on a single repeat_unit."
        )
    if result.report is not None:
        # **`invalid` is a third outcome and it must not be reported as "already present".** A row the
        # model refuses is a row the module does not have and this run did not add — a source whose
        # spelling has drifted lands here, and collapsing it into the no-op sentence would tell the
        # author everything is fine on the one run where nothing was written.
        refused = [o for o in result.report.outcomes if o.status == "invalid"]
        if refused:
            shown = "; ".join(
                f"{'/'.join(str(part) for part in o.key)}: "
                f"{(o.differences or {}).get('errors', (None, 'invalid'))[1]}"
                for o in refused[:_REFUSAL_LIMIT]
            )
            more = f" and {len(refused) - _REFUSAL_LIMIT} more" if len(refused) > _REFUSAL_LIMIT else ""
            notes.append(
                f"{len(refused)} locus/loci were refused by {REPEAT_ALLELES_CSV}'s own model and "
                f"were not written: {shown}{more}"
            )
        present = [o for o in result.report.outcomes if o.status == "already_present"]
        if not result.drafted and present and not refused:
            notes.append(
                f"nothing was appended: all {len(present)} candidate locus/loci are already in "
                f"{REPEAT_ALLELES_CSV}"
            )
    return notes
