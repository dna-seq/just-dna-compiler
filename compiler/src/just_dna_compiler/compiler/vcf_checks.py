"""VCF-conformance warnings: QUAL inversion, VCF's MISSING marker used as an allele, and the
`vcf_*` pointer columns.
"""

from typing import Any

from just_dna_format.alleles import non_nucleotide_reason
from just_dna_format.base import DEFAULT_GENOME_BUILD, derive_variant_key
from just_dna_format.findings import CodedWarning
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import (
    VALID_ELEMENT_RULES,
    VCF_COLLIDING_KEYS,
    VCF_COLLISION_REASONS,
    VCF_NUMBER_MEANINGS,
    VCF_POINTER_COMPANIONS,
    VCF_POINTER_FIELDS,
    is_multi_valued_number,
    split_field_pointer,
    vcf_field_number,
)

from just_dna_compiler.compiler.binning_checks import _BINNING_TABLE_KINDS
from just_dna_compiler.compiler.tables import _TABLE_KINDS

#: The fragment of the RM57 warning that names the finding, for the same reason the two phrases in
#: `binning` are named: a manifest carries the prose and no field.
QUAL_INVERSION_PHRASE = "QUAL means the opposite thing on the record this row is read from"


#: The one VCF column whose Phred-scaled assertion changes sign with the record (§1.6.1.6). Matched on
#: the bare token: a `quality_from` cell is `|`-alternated and may carry an `INFO/`-style namespace,
#: neither of which changes which field is named.
_INVERTING_QUALITY_FIELD = "QUAL"


def _quality_fields(pointer: str | None) -> list[str]:
    """The field tokens a pointer cell names, upper-cased and with any namespace stripped.

    A pointer is `|`-alternated, so `DP|QUAL` names two fields and both must be looked at; and a
    qualified spelling (`INFO/DP`) names the same field as its bare form, which is what the trailing
    `rsplit` is for. Case is folded because this feeds a *warning* — being generous about the spelling
    of the thing being warned about is the right direction to be wrong in.
    """
    if not pointer:
        return []
    return [part.rsplit("/", 1)[-1].strip().upper() for part in pointer.split("|") if part.strip()]


def _check_quality_inversion(variants: list[VariantRow]) -> list[str]:
    """A `requires_callable` row whose quality floor is stated against `QUAL` (RM57).

    §1.6.1.6 defines QUAL as *"−10log10 prob(variant)"* where ALT is `.` and *"−10log10 prob(no
    variant)"* otherwise — **the sign of the assertion flips with the record**. A QUAL of 60 on a variant
    record means the variant is almost certainly real; the same 60 on a monomorphic reference record
    means the position is almost certainly *variant*, which is the opposite of a clean reference call.

    `requires_callable` marks the rows where the *absence* of the variant is the informative call, and a
    consumer evaluating one reads the reference record — a gVCF `<*>` block (§5.5) or a monomorphic
    `ALT=.` record — which is exactly where QUAL is inverted. So `requires_callable=true,
    quality_from=QUAL, min_quality=30` asks the consumer to require evidence that the position *is*
    variant before asserting that it is not, and raising the floor makes the answer more confidently
    wrong rather than safer. `min_quality` is monotone in one direction only, so nothing else catches it.

    **A warning in both modes, and refusing the combination was considered and rejected.** A validator
    here would encode one reading of a field whose meaning depends on a record this tier will never see,
    and it would refuse the legitimate case — the same row read against a *variant* record elsewhere in
    the same file, where the floor means what its author intended. Aggregated to one line with examples,
    because a gene panel can carry hundreds of `requires_callable` rows and a line each would bury every
    other finding the run produces.
    """
    offenders = [
        v
        for v in variants
        if v.requires_callable is True and _INVERTING_QUALITY_FIELD in _quality_fields(v.quality_from)
    ]
    if not offenders:
        return []
    shown = ", ".join(str(v.variant_key) for v in offenders[:3])
    rest = f" (+{len(offenders) - 3} more)" if len(offenders) > 3 else ""
    return [
        CodedWarning(
            "quality_floor_inverted",
            f"variants.csv: {len(offenders)} row(s) set requires_callable=true and state their min_quality "
            f"floor against QUAL. {QUAL_INVERSION_PHRASE}: VCF §1.6.1.6 makes QUAL -10log10 prob(no "
            f"variant) on a variant record but -10log10 prob(variant) where ALT is '.', so on the reference "
            f"record a consumer must read to prove this absence, a HIGH QUAL says the position is probably "
            f"variant — and the higher the floor, the more confidently wrong the result. State the floor "
            f"against a per-sample confidence field instead (GQ), or against the reference block's MIN_DP. "
            f"e.g. {shown}{rest}.",
        )
    ]


#: The fragment of the RM58 warning that names the finding. Same reason as the phrases above.
MISSING_ALLELE_PHRASE = "is VCF's MISSING marker, not an allele"


#: Every authored table that declares an `alts` column, derived from the models rather than named: the
#: SNP core plus whichever table kinds carry one. A name list here would lose a kind the way
#: `SOURCES_FIELDNAMES` lost a column.
_ALTS_BEARING_KINDS: tuple[str, ...] = tuple(
    csv_name for csv_name, _parquet, model in _TABLE_KINDS if "alts" in model.model_fields
)


def _check_missing_allele_marker(
    variants: list[VariantRow],
    rows_by_csv: dict[str, list[Any]],
    genome_build: str = DEFAULT_GENOME_BUILD,
) -> list[str]:
    """An `alts` cell spelling VCF's MISSING marker, which splits the row's identity (RM58).

    `.` in ALT means *there are no alternate alleles* — a monomorphic reference record, which §1.1's own
    first worked example carries. No `ref`/`alts` column has a nucleotide grammar (deliberately: adding
    one would tighten the field RM5 exists to widen and would stop existing modules validating), so the
    cell loads, and `derive_variant_key` then folds it in as though it named an allele. The result is
    that a row writing `alts=.` and a row leaving the cell empty describe **one site under two keys** —
    `1:1:A:.` and `1:1:A` — with different `content_signature`s and no dedup between them. That is the
    only VCF-conformance finding in this batch that reaches identity, and until now nothing said a word
    about it: `alleles.non_nucleotide_reason` filed `.` under `"notation"` beside `<DEL>`, and the sites
    that consult it only run when a hosting verdict has already failed, which a monomorphic row never
    reaches.

    **A diagnosis, not a grammar** — the value is still accepted, exactly as `<DEL>` and `N` are. The
    remedy is an authored edit and an unambiguous one (leave the cell empty), which is what separates
    this from RM55/RM56 next door; it is still a warning in both modes, because `strict` means
    *reproducible artifact* and a module spelling `.` reproduces perfectly. Reported per table with a
    count and, where the split is real, the two keys side by side: on an rsid-authored row both keys are
    the rsid, so the cell is wrong without the identity consequence following, and claiming otherwise
    would be a false statement about that row.
    """
    warnings: list[str] = []
    tables: list[tuple[str, list[Any]]] = [("variants.csv", list(variants))]
    tables.extend((csv_name, rows_by_csv.get(csv_name) or []) for csv_name in _ALTS_BEARING_KINDS)
    for csv_name, rows in tables:
        offenders = [
            row
            for row in rows
            if any(
                non_nucleotide_reason(a) == "missing" for a in (getattr(row, "alts", None) or "").split(",")
            )
        ]
        if not offenders:
            continue
        # The identity split needs a coordinate, and **a row with no identity at all is not a split**.
        # Two shapes reach here without one and both must take the no-split branch. An rsid
        # short-circuits `derive_variant_key`, so both spellings of such a row key identically. And a
        # gene-only `heteroplasmy.csv` row — the pre-0.5 shape, still legal — has `variant_key is None`
        # while `derive_variant_key(None, None, None, None)` returns the *string* `'None:None:None'`, so
        # comparing the two always differs and the message read "e.g. None rather than None:None:None"
        # about a row that names no variant. Guard on the identity, never on the comparison.
        split: list[tuple[Any, str]] = []
        for row in offenders:
            key = getattr(row, "variant_key", None)
            if key is None:
                continue
            without = derive_variant_key(
                getattr(row, "rsid", None),
                getattr(row, "chrom", None),
                getattr(row, "start", None),
                getattr(row, "ref", None),
                build=genome_build,
            )
            if key != without:
                split.append((row, str(without)))
        if split:
            row, without = split[0]
            detail = (
                f"{len(split)} of them key differently from the same row with an empty cell (e.g. "
                f"{row.variant_key} rather than {without}), so this module and one authoring the same "
                f"site with the cell left empty carry two identities for one site, and neither "
                f"content_signature dedups against the other"
            )
        else:
            detail = (
                "no row's identity is affected — an rsid-keyed row keys the same either way, and a "
                "gene-keyed row names no variant at all — so the cell is simply claiming an allele "
                "that does not exist"
            )
        warnings.append(
            CodedWarning(
                "missing_allele_marker_in_alts",
                f"{csv_name}: {len(offenders)} row(s) write '.' in alts, which {MISSING_ALLELE_PHRASE} — "
                f"it states that the record has no alternate allele (VCF §1.6.1.5), so it is not the same "
                f"kind of thing as a symbolic allele like <DEL>. {detail}. Leave the cell empty instead.",
            )
        )
    return warnings


def _check_vcf_pointers(variants: list[VariantRow], rows_by_csv: dict[str, list[Any]]) -> list[str]:
    """A VCF pointer that does not identify the field it points at (RM53), or that points at a list
    without saying which element (RM54).

    **A VCF field is not identified by its name.** It is identified by *namespace* — INFO and FORMAT
    are two reserved-key tables that collide on `DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and, since 4.4,
    `CN` — and described by *cardinality* (`Number`, which says how many values come back and what
    each one is of). Both readings of a colliding key are usually type-compatible, so nothing detects
    the confusion: a consumer reads a well-formed number of the wrong kind and bins it without error.
    `reference_examples/mt_heteroplasmy` shipped `source_field=AF` meaning this person's heteroplasmy
    fraction, where the spec's `AF` is the cohort frequency of the same ALT — one of those tells a
    carrier they are asymptomatic on the strength of how rare the variant is in a reference panel.

    **Two findings, both warnings in both modes.** The pointer grammar was widened rather than
    replaced, so a bare key is still legal and still means *unqualified* (P3); escalating under
    `strict` would refuse modules that compile today, and `strict` means *reproducible artifact*
    anyway — an unqualified pointer reproduces perfectly, it is only ambiguous (P5). The remedy for
    both is a one-cell authored edit, which is what separates them from the `not_covered` class.

    **What it declines to say.** The cardinality half reads `vocab.VCF_FIELD_NUMBER`, a transcription
    of the spec's own reserved-key tables, and answers `None` for anything not in them — a caller's
    private key (`REPCN` is ExpansionHunter's, not the spec's) has no cardinality this tier is
    entitled to assert, and asserting one would be a source convention wearing a fact (P2). Unknown
    withholds. It also answers `None` for a *bare* key whose two namespaces disagree (`CN` is `A`
    under INFO and `1` under FORMAT), which is exactly the case the collision half already names.

    **The mirror case — an element rule on a field the spec calls single-valued — is deliberately
    *not* reported.** It looks like the obvious second half of the cardinality check and it would fire
    on the correct authoring of the flagship case: a caller that packs several values into one cell
    declares that cell `Number=1, Type=String`, which is exactly what ExpansionHunter's `REPCN`
    (`17/42`) is. Separating "one value" from "several values in one string" turns on `Type`, which
    this tier does not model and which no `Number` can answer. Where it cannot decide, it withholds
    rather than accusing a correct row.

    **The two halves quantify over different column sets, and that is not an oversight.** The
    namespace question belongs to every pointer column (`VCF_POINTER_FIELDS`) — the decision names
    `callable_from=DP` as the same error `source_field=AF` is, one column over. The cardinality
    question is only askable where a column exists to answer it, and 0.6 built one companion
    (`VCF_POINTER_COMPANIONS`); telling an author to fill a column the schema does not have would be
    a finding no edit could clear, which this codebase treats as a defect wherever else it appears.

    Aggregated by reason rather than by row: a panel pointing every bin at one field would otherwise
    print the same sentence hundreds of times, and two reasons under one message is the other half of
    that mistake."""
    tables: list[tuple[str, list[Any]]] = [("variants.csv", variants)]
    tables.extend((csv_name, rows_by_csv.get(csv_name) or []) for csv_name, _model in _BINNING_TABLE_KINDS)
    # (csv, pointer column, bare key) -> rows, and (csv, element column, atom, Number) -> rows.
    collisions: dict[tuple[str, str, str], int] = {}
    unselected: dict[tuple[str, str, str, str], int] = {}
    for csv_name, rows in tables:
        for row in rows:
            declared = type(row).model_fields
            for pointer_field in VCF_POINTER_FIELDS:
                if pointer_field not in declared:
                    continue
                pointer = getattr(row, pointer_field, None)
                if not pointer:
                    continue
                companions = [
                    element
                    for element, target in VCF_POINTER_COMPANIONS.items()
                    if target == pointer_field and element in declared
                ]
                selected = any(getattr(row, element, None) is not None for element in companions)
                for namespace, key in split_field_pointer(pointer):
                    if namespace is None and key in VCF_COLLIDING_KEYS:
                        seat = (csv_name, pointer_field, key)
                        collisions[seat] = collisions.get(seat, 0) + 1
                    if selected or not companions:
                        continue
                    number = vcf_field_number(namespace, key)
                    if is_multi_valued_number(number):
                        atom = key if namespace is None else f"{namespace}/{key}"
                        slot = (csv_name, companions[0], atom, number or "")
                        unselected[slot] = unselected.get(slot, 0) + 1
    warnings: list[str] = []
    if collisions:
        where = "; ".join(
            f"{csv_name} {pointer_field}={key} ({n} row(s))"
            for (csv_name, pointer_field, key), n in sorted(collisions.items())
        )
        keys = sorted({key for _csv, _field, key in collisions})
        reasons = " ".join(f"{key}: {VCF_COLLISION_REASONS[key]}." for key in keys)
        warnings.append(
            CodedWarning(
                "vcf_pointer_key_collision",
                f"{sum(collisions.values())} VCF pointer cell(s) name a key that INFO and FORMAT both "
                f"define, so the pointer does not say which field it means: {where}. {reasons} Qualify "
                f"the pointer — INFO/{keys[0]} or FORMAT/{keys[0]} — a bare key stays legal and keeps "
                f"meaning unqualified, which is why this is a warning and not a refusal.",
            )
        )
    if unselected:
        where = "; ".join(
            f"{csv_name} {VCF_POINTER_COMPANIONS[element_field]}={atom} (Number={number}, "
            f"{VCF_NUMBER_MEANINGS.get(number, 'a value list')}; {n} row(s), {element_field} empty)"
            for (csv_name, element_field, atom, number), n in sorted(unselected.items())
        )
        warnings.append(
            CodedWarning(
                "vcf_pointer_unselected_element",
                f"{sum(unselected.values())} VCF pointer cell(s) point at a field the spec defines as "
                f"multi-valued and state no element rule, so the pointer names a list rather than a "
                f"number: {where}. Set the companion column to one of "
                f"{sorted(VALID_ELEMENT_RULES)} — on a Number=R field the reference is element zero, "
                f"which is why each ranging rule comes in a pair (largest counts it, largest_alt does "
                f"not).",
            )
        )
    return warnings
