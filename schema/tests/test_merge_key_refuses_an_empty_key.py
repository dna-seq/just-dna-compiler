"""`merge_key` refuses an empty `_KEY_FIELDS` the way it refuses a missing one (RM213).

The function's docstring has always said what the failure must be: *a caller reaching here for an
unkeyed kind has a bug, and a silent `()` would merge every row into one.* It raised `AttributeError`
for a model **declaring no key** and returned `()` for one declaring an **empty** key — and
`MeasureBinRow` declares exactly that, as a base-class default meaning *subclasses set this*.

Measured before the repair: two `MeasureBinRow`s differing in every column returned equal keys. Latent
rather than live, because `measure_bins.csv` is authored and `merge_key` serves the machine-produced
sidecars — but a promise a docstring makes is a claim, and the next kind to inherit that default and
forget to override it would have found the collapse in a merge pass instead of here.

**`hints.table_key` is deliberately unchanged.** It reads the same falsy value as *no declared key* and
returns `None`, which is the right answer to its own question — does this table publish a key a
consumer can join on? This function asks what two rows' identity **is**, and there is no empty answer
to that.
"""

import pytest
from just_dna_format.base import merge_key
from just_dna_format.binning import ActivityPhenotypeRow, MeasureBinRow
from just_dna_format.spec import VariantRow

_COMMON = {"measure_kind": "activity_score", "conclusion": "a conclusion"}


def test_an_empty_key_raises_rather_than_collapsing() -> None:
    row = MeasureBinRow(measure_min=1, **_COMMON)

    with pytest.raises(AttributeError) as excinfo:
        merge_key(row)

    message = str(excinfo.value)
    assert "MeasureBinRow" in message, message
    assert "_KEY_FIELDS" in message, message


def test_the_collapse_it_prevents_is_real() -> None:
    """Pin the failure mode itself, so the repair cannot be reverted into a passing test.

    Before RM213 both of these returned `()` and compared equal. If a future change makes
    `merge_key` answer for this kind again, the two rows below are what it has to distinguish.
    """
    one = MeasureBinRow(measure_min=1, **_COMMON)
    other = MeasureBinRow(measure_min=99, **{**_COMMON, "conclusion": "an entirely different one"})

    for row in (one, other):
        with pytest.raises(AttributeError):
            merge_key(row)


def test_every_subclass_still_has_its_own_identity() -> None:
    """The default exists so subclasses override it, and they do — this is the control."""
    row = ActivityPhenotypeRow(measure_min=1, gene="CYP2D6", **_COMMON)

    assert merge_key(row) == ("CYP2D6",)


def test_a_normally_keyed_model_is_untouched() -> None:
    """Nothing about the ordinary path moved."""
    row = VariantRow(rsid="rs1801133", genotype="C/T", state="risk", conclusion="x")

    assert merge_key(row) == (row.variant_key, row.genotype)
