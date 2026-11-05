"""Every check names its witness (RM292, 0.8): the roster, the records it fills, and what it withholds.

The 2026-09-27 postmortem (blindspot B2) found that every check positioned to see the indel anchor
error either compared a source with itself or was tolerant by design, and nothing in a record could
say which. RM292's answer is a field on the check registry — the source a check reads and the source it
reads it against — asserted by an equality over the roster, so a new check cannot ship without stating
its witness. These tests pin the three halves:

* **The roster is an equality** with the vocabulary's emitting members, parsed from `vocab.py`'s own
  RESERVED comments rather than restated here, so a member with no witness is red rather than silent.
* **The constructors fill both sides from it** and refuse a check the roster does not hold, a `source`
  outside the witness it declares, and a tolerant check's record that leaves its abstentions uncounted.
* **The writer resolves `authored` against the module's licence table**, three-valued: nothing recorded
  from the witness keeps `authored`; a drafter's digest still matching makes the values that source's
  copy (`self_consistent`); anything in between withholds.

Network-free throughout: every `enrich()` here runs `offline=True`.
"""

import re
import shutil
from pathlib import Path

import pytest
from just_dna_enricher.enrich import enrich
from just_dna_enricher.verification import (
    CHECK_WITNESSES,
    CheckWitness,
    _checked_source,
    ran,
    record_verification,
    resolve_witnesses,
    skipped,
)
from just_dna_format import verification as verification_module
from just_dna_format import vocab
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.sources import SourceRow
from just_dna_format.verification import read_verification
from just_dna_format.vocab import AUTHORED_SOURCE, VALID_VERIFICATION_CHECKS

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_VOCAB = Path(vocab.__file__).resolve()
_EASY = 8


class _Boom(Exception):
    """The caller's own error type."""


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", _EASY)


def _reserved_members() -> set[str]:
    """Members `vocab.py` marks RESERVED — read from the source, never restated here."""
    lines = _VOCAB.read_text(encoding="utf-8").split("\n")
    return {m.group(1) for line in lines if (m := re.match(r'\s+"(\w+)",\s+# RESERVED', line))}


def _module(tmp_path: Path, name: str = "hfe_hemochromatosis") -> Path:
    spec = tmp_path / name
    shutil.copytree(_EXAMPLES / name, spec)
    (spec / VERIFICATION_JSON).unlink(missing_ok=True)
    return spec


# ── the roster ───────────────────────────────────────────────────────────────────────────────────


def test_the_roster_states_a_witness_for_exactly_the_checks_that_can_be_put() -> None:
    """The equality RM292 asks for. Both directions are entailed: a member with no entry is a check
    that could ship without stating its witness, and an entry naming no member is a witness for a
    question nobody can record. Reserved members have no emitter and so no witness to state."""
    assert _reserved_members(), "the RESERVED parse found nothing; the comment idiom moved"
    expected = set(VALID_VERIFICATION_CHECKS) - _reserved_members()
    assert set(CHECK_WITNESSES) == expected, sorted(set(CHECK_WITNESSES) ^ expected)


@pytest.mark.parametrize("check", sorted(CHECK_WITNESSES))
def test_every_entry_states_both_sides(check: str) -> None:
    entry = CHECK_WITNESSES[check]
    assert isinstance(entry, CheckWitness)
    assert entry.checked.strip(), check
    assert entry.witness and all(w.strip() for w in entry.witness), check
    assert entry.reason.strip(), f"{check}: a witness stated without the reason it is that witness"


def test_a_check_the_roster_does_not_hold_cannot_be_recorded(monkeypatch) -> None:
    """The mechanism behind the equality: the constructors read the roster, so dropping an entry makes
    every emitter of that check fail at once, rather than write a record with no witness."""
    monkeypatch.delitem(CHECK_WITNESSES, "reference_allele")
    with pytest.raises(KeyError, match="reference_allele"):
        ran("reference_allele", subjects=1, findings=0, source="seqrepo")
    with pytest.raises(KeyError, match="reference_allele"):
        skipped("reference_allele", "offline", source="seqrepo")


def test_the_constructors_fill_both_sides_and_the_derived_independence() -> None:
    record = ran("reference_allele", subjects=3, findings=1, source="seqrepo")
    assert (record.checked_source, record.witness_source) == (AUTHORED_SOURCE, "seqrepo")
    assert record.independence == "independent"
    skip = skipped("reference_allele", "offline", source="seqrepo")
    assert (skip.checked_source, skip.witness_source) == (AUTHORED_SOURCE, "seqrepo")


def test_a_source_outside_the_declared_witness_is_refused() -> None:
    """`source` and `witness_source` say one thing two ways on a single-authority check, so the
    constructor refuses the pair that disagrees — the drift a hand-kept roster would otherwise allow."""
    with pytest.raises(ValueError, match="witness"):
        ran("reference_allele", subjects=1, findings=0, source="ensembl")


def test_a_witness_override_must_be_part_of_the_declared_one() -> None:
    """A multi-authority check names the authorities that actually answered, never a new one."""
    record = ran("allele_function", subjects=2, findings=0, source="pharmvar", witness_source="pharmvar")
    assert record.witness_source == "pharmvar"
    with pytest.raises(ValueError, match="witness"):
        ran("allele_function", subjects=2, findings=0, witness_source="clinvar")


def test_a_tolerant_check_must_publish_its_abstentions() -> None:
    """`@tautology-zero` for a tolerance: a check the roster says abstains on a class may not record a
    run without the count of that class, or its zero reads as agreement."""
    assert CHECK_WITNESSES["rsid_coordinate_agreement"].tolerance, "the RM31 tolerance lost its entry"
    with pytest.raises(ValueError, match="undecided"):
        ran("rsid_coordinate_agreement", subjects=2, findings=0, source="ensembl")
    record = ran("rsid_coordinate_agreement", subjects=2, findings=0, source="ensembl", undecided=0)
    assert record.undecided == 0
    # And the converse: a check with no tolerance has no class to count, so a count there is a claim.
    with pytest.raises(ValueError, match="undecided"):
        ran("reference_allele", subjects=1, findings=0, source="seqrepo", undecided=0)


@pytest.mark.parametrize("check", sorted(c for c, w in CHECK_WITNESSES.items() if w.checked in w.witness))
def test_a_check_reading_its_witness_own_value_is_self_consistent_by_construction(check: str) -> None:
    """The currency checks: a value a source published, asked of that same source later. What they
    establish is that the source still says it — never independent evidence for the claim."""
    record = skipped(check, "not_requested")
    assert record.independence == "self_consistent", check


# ── the writer resolves `authored` against the licence table ─────────────────────────────────────


def test_a_module_recording_nothing_from_the_witness_keeps_authored(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    [record] = resolve_witnesses([ran("reference_allele", subjects=1, findings=0, source="seqrepo")], spec)
    assert record.checked_source == AUTHORED_SOURCE
    assert record.independence == "independent"


def test_a_licence_row_naming_the_witness_with_no_digest_withholds(tmp_path: Path) -> None:
    """`hfe_hemochromatosis` records a ClinVar `annotation` row and no drafter digest: the module drew
    on ClinVar, and nothing establishes which `clin_sig` cells are ClinVar's copies. Unknown is
    withheld — neither `authored` (a claim that they are not copies) nor `clinvar`."""
    spec = _module(tmp_path)
    [record] = resolve_witnesses(
        [ran("clinical_significance", subjects=1, findings=0, source="clinvar")], spec
    )
    assert record.checked_source is None
    assert record.independence is None
    assert record.witness_source == "clinvar"


def test_an_unreadable_licence_table_withholds_every_authored_side(tmp_path: Path) -> None:
    """An unreadable table established nothing either way: not "nothing was drafted", which is what
    the gentle reader's `[]` would have said here and is the false half."""
    spec = _module(tmp_path)
    (spec / "sources.csv").write_text("source,layer\nclinvar,not-a-layer\n", encoding="utf-8")
    [record] = resolve_witnesses([ran("reference_allele", subjects=1, findings=0, source="seqrepo")], spec)
    assert record.checked_source is None and record.independence is None


def test_a_self_consistent_check_is_not_resolved_away(tmp_path: Path) -> None:
    """Only `authored` is a question for the licence table; a currency check's sides are the roster's."""
    spec = _module(tmp_path)
    [record] = resolve_witnesses([skipped("dataset_currency", "not_requested")], spec)
    assert record.independence == "self_consistent"


def test_every_record_enrich_writes_states_its_witness(tmp_path: Path) -> None:
    """The equality over a real run: every check `enrich()` attested is a roster entry, and every
    record carries the witness that entry declares (or, where the run answered fewer authorities, a
    part of it). The `checked_source` is the roster's or the one the licence table resolved."""
    spec = _module(tmp_path)
    enrich(spec, offline=True, download=False)
    records = read_verification(spec / VERIFICATION_JSON).records
    assert records
    assert {r.check for r in records} <= set(CHECK_WITNESSES)
    for record in records:
        entry = CHECK_WITNESSES[record.check]
        assert record.witness_source is not None, record.check
        assert set(record.witness_source.split("+")) <= set(entry.witness), record.check
        assert record.checked_source in {entry.checked, record.witness_source, None}, record.check
    by_check = {r.check: r for r in records}
    assert by_check["reference_allele"].independence == "independent"
    assert by_check["dataset_currency"].independence == "self_consistent"
    # The ClinVar annotation row with no digest, through the real writer this time.
    assert by_check["clinical_significance"].independence is None


def test_the_writer_resolves_before_it_attests(tmp_path: Path) -> None:
    """`record_verification` is the one seam every command writes through, so it is where the
    resolution lives — a pass cannot attest an `authored` the licence table contradicts."""
    spec = _module(tmp_path)
    doc = record_verification(
        [ran("clinical_significance", subjects=1, findings=0, source="clinvar")], spec, error=_Boom
    )
    assert doc is not None
    [record] = [r for r in doc.records if r.check == "clinical_significance"]
    assert record.checked_source is None


# ── the review's cases: a digest beside a witness row, a carried record, several witnesses ───────


def _licence(*pairs: tuple[str, str]) -> list[SourceRow]:
    return [SourceRow(source=source, layer=layer) for source, layer in pairs]


def test_a_digest_for_another_source_beside_a_witness_row_withholds() -> None:
    """A digest covers the whole table as the LAST drafter left it — rows an earlier draft from the
    witness put there included. So a single holding PubMind digest beside a ClinVar annotation row does
    not make the cells PubMind's; it withholds."""
    entry = CHECK_WITNESSES["clinical_significance"]
    held = {"pubmind": True, "clinvar": False}.get
    both = _licence(("clinvar", "annotation"), ("pubmind", "annotation"))
    assert _checked_source(entry, "clinvar", both, held) is None
    # With no ClinVar row, the PubMind copy is what the cells are, and it is not the witness.
    assert _checked_source(entry, "clinvar", _licence(("pubmind", "annotation")), held) == "pubmind"
    # And the witness's own holding digest is the self-consistent case.
    assert _checked_source(entry, "clinvar", both, {"clinvar": True}.get) == "clinvar"
    # A resolution-layer row is a looked-up coordinate, not a copied claim.
    assert _checked_source(entry, "clinvar", _licence(("clinvar", "resolution")), held) == AUTHORED_SOURCE


def test_a_carried_record_is_re_settled_against_the_licence_table_as_it_now_stands(tmp_path: Path) -> None:
    """The licence table is outside the authored binding, so a record kept from an earlier run must be
    settled again: one that said `authored` before a ClinVar row was recorded cannot keep saying it."""
    spec = _module(tmp_path)
    licence = spec / "sources.csv"
    original = licence.read_text(encoding="utf-8")
    licence.unlink()
    record_verification(
        [ran("clinical_significance", subjects=1, findings=0, source="clinvar")], spec, error=_Boom
    )
    first = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}
    assert first["clinical_significance"].checked_source == AUTHORED_SOURCE

    licence.write_text(original, encoding="utf-8")
    record_verification([skipped("dataset_currency", "not_requested")], spec, error=_Boom)
    carried = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}
    assert carried["clinical_significance"].checked_source is None
    assert carried["clinical_significance"].independence is None
