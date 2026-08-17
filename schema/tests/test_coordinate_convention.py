"""Every authored `start` column is the 1-based VCF position, and says so.

This exists because the descriptions used to say the opposite. `VariantRow.start` and the two PGx
`start`s described themselves as "0-based" while every tier that *stores*, *checks* or *mints from*
the column reads it as VCF POS. The descriptions are not commentary: `describe`, `requirements` and
`reference` print them verbatim, so they are the authoring contract, and an author who followed them
wrote `pos - 1` into every row.

The damage is silent, which is why a guard is worth its cost. A uniformly shifted module passes
`validate`, passes `compile --strict`, reports `fully_resolved: True`, and mints `ga4gh:VA.…` ids the
compiler then *verifies* — because a content-addressed id is a correct digest of whatever it was
given. Only the enricher's online reference-allele check can see it, and only for the ~3 rows in 4
where the neighbouring base differs from the authored `ref`.

So the tests below pin the *behaviour* first — what the code does with the number — and only then
require the prose to agree with it.
"""

from __future__ import annotations

import pytest
from just_dna_format.pgx import HaplotypeRow, PharmVariantRow
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.vrs import derive_vrs_allele_id, sequence_location_digest

#: Every authored model + field naming a genomic position an author fills in by hand.
AUTHORED_START_FIELDS = [
    (VariantRow, "start"),
    (StudyRow, "start"),
    (HaplotypeRow, "start"),
    (PharmVariantRow, "start"),
]


def test_authored_start_feeds_vrs_minting_as_a_vcf_position() -> None:
    """The number in `VariantRow.start` reaches `derive_vrs_allele_id` as VCF POS, not interbase.

    This is the ground truth the prose has to match. `derive_vrs_allele_id` documents its `start` as
    the 1-based VCF position and converts to interbase itself (`[p-1, p)`), so a row whose author
    subtracted one addresses the base *before* the variant.
    """
    row = VariantRow(
        rsid="rs1801133",
        chrom="1",
        start=11796321,
        ref="G",
        alts="A",
        genotype="A/G",
        state="risk",
        conclusion="One copy of the T allele (MTHFR c.665C>T).",
    )

    minted = derive_vrs_allele_id(row.chrom, row.start, row.ref, "A")
    assert minted is not None
    assert minted == derive_vrs_allele_id("1", 11796321, "G", "A")

    # The interbase span the id actually addresses is [start-1, start) — one base, at VCF POS.
    assert sequence_location_digest("1", row.start - 1, row.start) is not None

    # An author who "converted to 0-based" mints a different id: a different base, silently.
    shifted = derive_vrs_allele_id(row.chrom, row.start - 1, row.ref, "A")
    assert shifted is not None
    assert shifted != minted


@pytest.mark.parametrize("model,field", AUTHORED_START_FIELDS, ids=lambda x: getattr(x, "__name__", x))
def test_authored_start_descriptions_state_the_vcf_convention(model: type, field: str) -> None:
    """The printed authoring contract must say 1-based, and must not say 0-based.

    Both halves matter. Saying nothing leaves an author to guess against a strong 0-based habit from
    BED and from VRS itself; saying "0-based" actively instructs the shift.
    """
    description = (model.model_fields[field].description or "").lower()
    assert description, f"{model.__name__}.{field} has no description to print"
    assert "0-based" not in description, (
        f"{model.__name__}.{field} tells authors it is 0-based; every tier reads it as VCF POS"
    )
    assert "1-based" in description


def test_authored_and_resolved_start_share_one_convention() -> None:
    """`VariantRow.start` and `ResolutionRow.start` are the same number for the same variant.

    `compiler.resolution._verify` compares them directly by building a coordinate key from each, so
    a convention split between the two tiers would not merely mislead — it would make the redundancy
    check report a disagreement on every correctly-authored row.
    """
    from just_dna_format.resolution import ResolutionRow

    resolved = ResolutionRow(
        variant_key="rs1801133", rsid="rs1801133", chrom="1", start=11796321, ref="G", alts="A"
    )
    authored = VariantRow(
        rsid="rs1801133",
        chrom="1",
        start=11796321,
        ref="G",
        alts="A",
        genotype="A/G",
        state="risk",
        conclusion="One copy of the T allele (MTHFR c.665C>T).",
    )
    assert authored.start == resolved.start
    assert "1-based" in (ResolutionRow.model_fields["start"].description or "")


# ── RM96: the same convention, enforced — every model with a position carries the same lower bound ──

#: Every model in the schema with a genomic `start`, authored or machine-written. Wider than
#: `AUTHORED_START_FIELDS` above on purpose: the reason the bound exists (the parquet column is
#: unsigned, and a negative number is not a coordinate under any convention) does not care who wrote
#: the row.
ALL_START_MODELS = [
    "VariantRow",
    "StudyRow",
    "HaplotypeRow",
    "PharmVariantRow",
    "HeteroplasmyRow",
    "ResolutionRow",
    "FrequencyRow",
    "ClinicalAssertionRow",
]


def _start_models() -> list[tuple[str, type]]:
    from just_dna_format.assertions import ClinicalAssertionRow
    from just_dna_format.binning import HeteroplasmyRow
    from just_dna_format.frequency import FrequencyRow
    from just_dna_format.resolution import ResolutionRow

    found = {
        "VariantRow": VariantRow,
        "StudyRow": StudyRow,
        "HaplotypeRow": HaplotypeRow,
        "PharmVariantRow": PharmVariantRow,
        "HeteroplasmyRow": HeteroplasmyRow,
        "ResolutionRow": ResolutionRow,
        "FrequencyRow": FrequencyRow,
        "ClinicalAssertionRow": ClinicalAssertionRow,
    }
    assert sorted(found) == sorted(ALL_START_MODELS), "the roster above drifted from the imports"
    return sorted(found.items())


@pytest.mark.parametrize("name,model", _start_models(), ids=sorted(ALL_START_MODELS))
def test_every_model_with_a_position_rejects_a_negative_one(name: str, model: type) -> None:
    """`ge=0` on all eight, not on five of them (RM96).

    `HaplotypeRow`, `PharmVariantRow` and `HeteroplasmyRow` accepted `start=-5` while the other five
    refused it, for no reason a reader could derive — and the reason the bound exists applies to all
    of them equally: the parquet column is unsigned, and a negative number is not a genomic position
    under any convention this format supports.

    Read off the field constraint rather than by constructing a row, since the required fields differ
    across eight models and the constraint is what the authoring reference prints.
    """
    bounds = [m for m in model.model_fields["start"].metadata if hasattr(m, "ge")]
    assert bounds, f"{name}.start carries no lower bound; a negative coordinate would validate"
    assert bounds[0].ge == 0, f"{name}.start bounds at {bounds[0].ge}, not 0"


def test_position_zero_still_loads_because_vcf_permits_it() -> None:
    """The bound is `ge=0` and deliberately not `ge=1` — checked, not assumed.

    `start` is the 1-based VCF POS (`@start-1based`), so `0` looks like it should be excluded, and
    tightening it while adding the bound to three more models is the obvious next move. It is wrong:
    VCF 4.4 §1.6.1.2/§5.4.5 use POS 0 for a **telomeric breakend**, and the 4.4 audit recorded this
    under "checked, and *not* a finding" — `VariantRow.start`'s `ge=0` is what lets such a record
    load, and `derive_vrs_allele_id` returns `None` for `start < 1` rather than minting an id for a
    position that does not exist. Both halves are pinned here so the reasoning survives the next
    reader who notices the mismatch.
    """
    from just_dna_format.vrs import derive_vrs_allele_id

    telomeric = VariantRow(
        chrom="1",
        start=0,
        ref="N",
        alts="<DEL>",
        genotype="<DEL>/<DEL>",
        state="risk",
        conclusion="A telomeric record, POS 0 per VCF 4.4 s1.6.1.2.",
    )
    assert telomeric.start == 0
    assert derive_vrs_allele_id("1", 0, "N", "A") is None, "no id may be minted for a non-position"

    with pytest.raises(ValueError):
        VariantRow(
            chrom="1",
            start=-1,
            ref="G",
            alts="A",
            genotype="A/G",
            state="risk",
            conclusion="Not a coordinate.",
        )
