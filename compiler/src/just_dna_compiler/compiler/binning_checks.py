"""The binning and citing table kinds, and the checks that ground binning thresholds in studies."""

from typing import Any

from just_dna_format.binning import MeasureBinRow, deprecation_warnings, measurement_shape_warnings
from just_dna_format.findings import CodedWarning, restate
from just_dna_format.spec import StudyRow
from pydantic import BaseModel

from just_dna_compiler.compiler.tables import _TABLE_KINDS

#: The binning table kinds, derived from the models for the same reason `_POSITIONAL_TABLE_KINDS` is:
#: a kind is a binning kind exactly when its model is a `MeasureBinRow`, and a hand-kept list of the
#: four would silently lose the fifth.
_BINNING_TABLE_KINDS: tuple[tuple[str, type[BaseModel]], ...] = tuple(
    (csv_name, model)
    for csv_name, _parquet, model in _TABLE_KINDS
    if isinstance(model, type) and issubclass(model, MeasureBinRow)
)


#: The table kinds that **cite**, derived the same way and for the sharper version of the same reason
#: (RM132): a kind is a citation site exactly when its model declares a `pmid`, and the literature
#: cross-check reads every one of them. Today that is the four binning kinds plus `pharm_variants.csv`.
#:
#: **Hand-listing this is the failure the check cannot survive.** A citation site the cross-check does
#: not know about makes every citation from it read as a stale orphan in one direction and leaves it
#: unchecked in the other — which is the whole of RM47's recorded lesson, and the reason RM132 shipped
#: its two cross-check sites in the same release as the column rather than after it. Deriving the set
#: means the *next* citing kind is covered by declaring the column, with nothing to remember.
#:
#: Scoped to `_TABLE_KINDS` on purpose. `StudyRow.pmid` is the citation site this set is *compared
#: against* rather than a member of it, `LiteratureRow.pmid` is the subject being checked, and
#: `GwasEffectRow.pmid` is a machine-written fact table's provenance column — none of the three is an
#: authored annotation row grounding its own claim, which is what a member here is.
_CITING_TABLE_KINDS: tuple[tuple[str, type[BaseModel]], ...] = tuple(
    (csv_name, model) for csv_name, _parquet, model in _TABLE_KINDS if "pmid" in model.model_fields
)


def _check_binning_grounding(rows_by_csv: dict[str, list[Any]], studies: list[StudyRow]) -> list[str]:
    """A binning table asserting thresholds with no evidence recorded anywhere in the module (S19).

    **Grounding is enforced where it is most often automatic and silent where it is most
    interpretive.** `studies.csv` is required iff `variants.csv` is present, and a `variants.csv` row
    is frequently drafted from ClinVar with citations already attached. A bin *boundary* is the
    opposite: where 36 rather than 35 CAG becomes "reduced penetrance" is a clinical judgement drawn
    from a specific literature, it is exactly the number a reader would want to check, and until this
    check the format asked for nothing and said nothing. `reference_examples/htt_repeat_expansion`
    compiled green under `--strict` stating four thresholds with no citation anywhere, and its own
    README says "a module making a novel claim should carry its evidence" — advice the schema had no
    place to take.

    **The remedy became sayable in 0.6 (RM47).** Until then this could report an absence and never a
    *link*: `studies.csv` identified its subject by rsid or `chrom`, and an `activity_phenotype.csv` /
    `copynumbers.csv` / `repeat_alleles.csv` row is keyed `(gene, …)`, so a study row grounded the
    module and no rule could tie it to a bound. `MeasureBinRow.pmid` is now the tie — a pointer on the
    row that states the threshold — and `StudyRow`'s subject requirement was relaxed in the same
    release so the citation row describing that paper need not invent a variant to hang off. So the
    message names one remedy for every kind, and the `heteroplasmy.csv`-only branch (whose rows can
    also be pointed at by identity, which is what `reference_examples/mt_heteroplasmy` does) is now an
    *additional* route rather than the only actionable one.

    **A bin that carries a `pmid` is grounded and is not counted**, derived from the row rather than
    the table. Fires only when the module records **no** study rows at all *and* some bin cites
    nothing: once an author has written a `studies.csv`, saying more would be nagging, and on a module
    carrying `variants.csv` the missing table is already a hard error, so this never doubles it.
    A warning in both modes: the remedy is an authored edit, but `strict` means *reproducible
    artifact*, an unrelated axis (P5), and a module that cites nothing still reproduces exactly.

    **A variant identity is not evidence, and treating it as one here was vacuous (D1-3).** A second
    exemption used to sit beside the `pmid` one: a bin naming a variant was counted as grounded,
    because a study row can name that variant back. Inside this function there is no study row — the
    early return has just established that the module records none — so the exemption cleared a bin
    against a citation that does not exist, and a `heteroplasmy.csv` module stating four thresholds
    and citing nothing was green and silent while the identical module on `repeat_alleles.csv` was
    warned. That is the S19 gap, reopened for the one binning kind a real MELAS/NARP module uses.
    Identity survives as the reason `heteroplasmy.csv` is offered a **second remedy** — a study row
    really can point at those bins — never as a reason to say nothing.
    """
    if studies:
        return []
    warnings: list[str] = []
    for csv_name, model in _BINNING_TABLE_KINDS:
        rows = [r for r in rows_by_csv.get(csv_name) or [] if not r.unresolved]
        # One way a bin is grounded in a module with no studies.csv, read off the row and never off
        # the table name: its own `pmid` (RM47, every kind). A variant identity is not a second way —
        # see the D1-3 paragraph above — it only decides which remedies this kind can be offered.
        ungrounded = [r for r in rows if r.pmid is None]
        if not ungrounded:
            continue
        remedy = (
            "cite the boundary itself: put the PubMed id on the bin row (`pmid`), and describe the "
            "paper in a studies.csv row, which since 0.6 need not name a variant"
        )
        # Read off `model_fields`, **not `hasattr`**: `variant_key` became a *stamped field* in 0.6
        # (RM43) and a field is not a class attribute, so `hasattr` silently answers `False` and every
        # heteroplasmy module gets the message written for a gene-keyed table. Two lanes of this same
        # release wrote these two lines — the `pmid` route and the `model_fields` repair — and the
        # `hasattr` spelling arrived with the first because RM43 had not landed under it yet.
        if "variant_key" in model.model_fields:
            remedy += (
                "; alternatively, a studies.csv row naming the variant these bins are about grounds "
                "them — this kind carries rsid/chrom+start, so fill those in if they are empty"
            )
        else:
            # Deliberately does NOT restate the pre-RM47 claim that nothing can point at these bins.
            # It was true and it is now retired: `pmid` on the bin is exactly the route that claim said
            # did not exist, and repeating it would leave an author reading a finding no edit can clear
            # — the defect this codebase treats as a defect everywhere else. Say which route applies to
            # a gene-keyed kind, and say it in the affirmative.
            # Named in the author's own spelling: `_KEY_FIELDS` may hold a *derived* member — since
            # 0.6 `CopyNumberRow` keys on `effective_modifier_copy_number`, which is a property over
            # two columns and not a cell anyone can fill — and a remedy that tells an author to look
            # at a column that is not in their CSV is the class of finding no edit clears.
            key = ", ".join(f for f in model._KEY_FIELDS if f != "variant_key" and f in model.model_fields)
            remedy += (
                f"; for a ({key}) row the bin's own pmid is the route, because a study row can only "
                f"name a variant as its subject and never a bin, so it grounds the module while the "
                f"bin pointer grounds this threshold"
            )
        warnings.append(
            CodedWarning(
                "bins_ungrounded",
                f"{csv_name}: {len(ungrounded)} of {len(rows)} bin(s) state a threshold and the module "
                f"records no grounding evidence at all (no studies.csv rows, no bin pmid). {remedy}.",
            )
        )
    return warnings


def _check_measure_shape(rows_by_csv: dict[str, list[Any]]) -> list[str]:
    """Per binning table: what a quantised tiling cannot express about its source measurement.

    A thin loop over `binning.measurement_shape_warnings`, which owns both findings (RM55, RM56)
    because it owns the tiling semantics whose premise VCF 4.4 withdrew. Since 0.6 the RM55 half is
    **conditional** — it fires only for a kind that still has a quantised group — so a table declaring
    `measure_tiling: continuous`, or carrying a fractional bound, is silent here. The kinds are derived
    from the models via `_BINNING_TABLE_KINDS` for the same reason that tuple exists, so a sixth
    binning kind cannot silently escape the check.
    """
    warnings: list[str] = []
    for csv_name, _model in _BINNING_TABLE_KINDS:
        rows = rows_by_csv.get(csv_name) or []
        # `restate` and not an f-string: a reformatted message is a plain `str` and would arrive at
        # `classify` with no code, so the prefix is applied through the one operation that carries it.
        warnings.extend(restate(w, f"{csv_name}: {w}") for w in measurement_shape_warnings(rows))
    return warnings


def _check_binning_deprecations(rows_by_csv: dict[str, list[Any]]) -> list[str]:
    """Per binning table: a column this release still reads and an author should stop writing (RM55).

    Separate from `_check_measure_shape` because it answers a different question — that one is about
    what the *source measurement* is, this one about what the *schema* is retiring — and folding them
    would put a deprecation notice inside a function documented as a VCF-conformance finding.

    `binning.deprecation_warnings` emits at most one line per table, so a copy-number table stating
    one dosage per modifier copy number gets one sentence rather than one per row.
    """
    warnings: list[str] = []
    for csv_name, _model in _BINNING_TABLE_KINDS:
        rows = rows_by_csv.get(csv_name) or []
        warnings.extend(restate(w, f"{csv_name}: {w}") for w in deprecation_warnings(rows))
    return warnings
